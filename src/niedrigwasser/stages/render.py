from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from collections.abc import Iterable, Mapping
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402
import matplotlib.ticker as mtick  # noqa: E402
import numpy as np  # noqa: E402
import polars as pl  # noqa: E402

from niedrigwasser.aggregate import select_index_stations
from niedrigwasser.daily_share import daily_below_share
from niedrigwasser.i18n import geschwister_katalog
from niedrigwasser.store import StageLog, connect, write_stage_parquet
from niedrigwasser.topology import incremental_areas
from niedrigwasser.trend import DECADES
from niedrigwasser.water_year import day_of_water_year, water_year_start

WINDOW = (1992, 2025)

# Feste Bin-Kanten fuer das days_below-Histogramm der Dekaden: 0-200 in
# 10er-Schritten plus ein Ueberlauf-Bin fuer alles >200 (bis 365 moeglich).
HIST_BIN_EDGES = list(range(0, 201, 10)) + [366]

_MONTH_ORDER = [(11, "Nov"), (12, "Dez"), (1, "Jan"), (2, "Feb"), (3, "Mär"),
                (4, "Apr"), (5, "Mai"), (6, "Jun"), (7, "Jul"), (8, "Aug"),
                (9, "Sep"), (10, "Okt")]

_METRIC_KEY = {"index_days": "days", "index_deficit": "deficit", "index_ssi": "ssi"}

SOURCE_LINE = "Quelle: NIWIS (BfG/LAWA), Datenlizenzen je Station"


def _iso_utc(epoch_seconds: float) -> str:
    """Unix-Sekunden -> ISO-8601 in UTC, sekundengenau (Format wie bisher)."""
    return dt.datetime.fromtimestamp(epoch_seconds, dt.timezone.utc).isoformat(
        timespec="seconds"
    )


def generated_timestamp(
    inputs: Iterable[Path], env: Mapping[str, str] | None = None
) -> str:
    """Deterministischer Zeitstempel fuer meta.generated (ISO-8601, UTC).

    Reihenfolge:
    1. ``SOURCE_DATE_EPOCH`` (Standard von reproducible-builds.org) -- expliziter
       Override fuer CI- und Repro-Builds.
    2. Sonst die juengste Modifikationszeit der gelesenen Eingabe-Artefakte. Das
       sind die DuckDB und die von den Vorstufen geschriebenen Parquet-/CSV-
       Staende, die render konsumiert -- bewusst NICHT die eigenen Ausgaben
       dieser Stufe (data/interim/render/, out/figures/, site/), die render bei
       jedem Lauf neu schreibt und die den Zeitstempel sonst bei jedem Lauf
       verstellen wuerden. Damit ist ein Rebuild bei unveraenderten Daten
       bit-identisch, ohne dass eine Umgebungsvariable gesetzt werden muss;
       neue Daten (= neue mtimes der Vorstufen-Artefakte) heben ihn an.
    3. Wallclock -- nur als Notnagel, wenn keine der Eingaben existiert.
    """
    environ = os.environ if env is None else env
    raw = environ.get("SOURCE_DATE_EPOCH")
    if raw is not None and raw.strip():
        try:
            epoch = int(raw.strip())
        except ValueError as exc:
            raise ValueError(
                f"SOURCE_DATE_EPOCH muss eine ganze Zahl (Unix-Sekunden) sein, "
                f"war aber {raw!r}"
            ) from exc
        return _iso_utc(epoch)
    mtimes = [p.stat().st_mtime for p in inputs if p.exists()]
    if mtimes:
        return _iso_utc(max(mtimes))
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

# Gebietsflaeche Deutschlands, gerundet (Destatis, Gebietsflaeche 31.12.2022:
# 357.592 km2). Dient nur als Fallback-Schranke fuer den Auslandsanteil der
# Coverage, wenn config/basin_domestic_area.csv fehlt.
GERMANY_AREA_KM2 = 357_600


def _foreign_area(primary_stations: pl.DataFrame, basin_areas_path: Path,
                  coverage_km2: float, log: StageLog) -> tuple[float, bool]:
    """Auslandsanteil der Gewichtungsmasse in km2.

    Belegte Variante: Summe (catchment_km2 - domestic_km2) ueber die in
    config/basin_domestic_area.csv gefuehrten Basin-Auslaesse, soweit sie im
    primary-Set enthalten sind. Die domestic-Werte sind laut Recherche
    (docs/recherche-auslandsanteil.md) teils obere Schranken, der abgeleitete
    Auslandsanteil ist damit stets eine UNTERE Schranke.

    Fallback ohne CSV: max(0, coverage - GERMANY_AREA_KM2) -- quellenfreie,
    ebenfalls untere Schranke.
    """
    if basin_areas_path.exists():
        basin = pl.read_csv(basin_areas_path).select(
            "station_id", "catchment_km2", "domestic_km2"
        )
        matched = basin.join(
            primary_stations.select("station_id", "catchment_area"),
            on="station_id", how="inner",
        )
        if matched.height:
            # Gegenprobe: weicht die recherchierte EZG-Flaeche von der
            # NIWIS-Stammdatenflaeche ab, ist eine der beiden veraltet.
            for row in matched.iter_rows(named=True):
                db_area = row["catchment_area"]
                if db_area and abs(float(row["catchment_km2"]) - float(db_area)) / float(db_area) > 0.01:
                    log.info(
                        f"WARN basin_domestic_area: {row['station_id']} "
                        f"catchment_km2={row['catchment_km2']} weicht >1% von "
                        f"NIWIS-Stammdaten ({db_area}) ab"
                    )
            foreign = float(
                matched.select(
                    (pl.col("catchment_km2") - pl.col("domestic_km2")).clip(lower_bound=0).sum()
                ).item()
            )
            log.info(
                f"Auslandsanteil aus {basin_areas_path}: {foreign:.0f} km2 "
                f"ueber {matched.height} Basin-Auslaesse (untere Schranke)"
            )
            return foreign, True
        log.info(
            f"basin_domestic_area: keine der {basin.height} Zeilen im primary-Set "
            f"-- Fallback auf coverage - {GERMANY_AREA_KM2} km2"
        )
    else:
        log.info(
            f"basin_domestic_area fehlt ({basin_areas_path}) -- Fallback auf "
            f"coverage - {GERMANY_AREA_KM2} km2"
        )
    return max(0.0, coverage_km2 - GERMANY_AREA_KM2), True


def _month_start_ticks() -> tuple[list[int], list[str]]:
    # Referenz-Wasserjahr ohne Schaltjahresanteil (2022/2023 sind beide
    # normale Jahre), damit die Tick-Positionen nicht durch den 29. Februar
    # verschoben werden. Der Schalttag selbst wird in daily_share bereits auf
    # Tag 365 gefaltet (siehe daily_share.py).
    ref_start = water_year_start(2023)
    ticks, labels = [], []
    for month, label in _MONTH_ORDER:
        year = ref_start.year if month >= 11 else ref_start.year + 1
        ticks.append(day_of_water_year(dt.date(year, month, 1)))
        labels.append(label)
    return ticks, labels


def _primary_stations(con, interim: Path, sinks_path: Path) -> pl.DataFrame:
    stations = con.execute(
        "SELECT station_id, name, river, lat, lon, catchment_area, downstream_id FROM stations"
    ).pl()
    areas = incremental_areas(stations.select("station_id", "catchment_area", "downstream_id"))
    stations = stations.join(areas, on="station_id", how="left")

    usable_stations = pl.read_parquet(interim / "screen" / "usable_stations.parquet").select(
        "station_id", "is_near_natural"
    )
    stations_sel = stations.join(usable_stations, on="station_id", how="inner")

    sinks = pl.read_csv(sinks_path)
    return select_index_stations(stations_sel, sinks, include_nested=False, natural_only=False)


def _build_heatmap(daily: pl.DataFrame, out_path: Path, log: StageLog) -> dict:
    years = list(range(WINDOW[0], WINDOW[1] + 1))
    window = daily.filter(pl.col("water_year").is_between(*WINDOW))

    by_year: dict[int, dict[int, tuple[float, int]]] = {y: {} for y in years}
    for row in window.select("water_year", "doy", "share", "n_stations").iter_rows():
        wy, doy, share, n = row
        by_year[wy][doy] = (share, n)

    values: list[list[float]] = []
    n_stations: list[list[int]] = []
    missing = 0
    for y in years:
        d = by_year[y]
        row_vals: list[float] = []
        row_n: list[int] = []
        for doy in range(1, 366):
            entry = d.get(doy)
            if entry is None:
                missing += 1
                entry = (0.0, 0)
            row_vals.append(round(float(entry[0]), 3))
            row_n.append(int(entry[1]))
        values.append(row_vals)
        n_stations.append(row_n)
    if missing:
        log.info(f"heatmap: {missing} fehlende (Jahr,Tag)-Werte auf 0.0/n=0 gesetzt")

    arr = np.array(values)
    fig, ax = plt.subplots(figsize=(11, 8))
    im = ax.imshow(arr, aspect="auto", cmap="YlOrRd", vmin=0, vmax=1, origin="upper")

    ax.set_yticks(range(0, len(years), 2))
    ax.set_yticklabels([years[i] for i in range(0, len(years), 2)])
    ax.set_ylabel("Wasserjahr")

    ticks, labels = _month_start_ticks()
    ax.set_xticks([t - 1 for t in ticks])
    ax.set_xticklabels(labels)
    ax.set_xlabel("Tag im Wasserjahr (Nov–Okt)")

    ax.set_title("Anteil Stationen unter Q95 je Tag und Wasserjahr")
    cbar = fig.colorbar(im, ax=ax)
    cbar.set_label("Anteil unter Q95")
    cbar.ax.yaxis.set_major_formatter(mtick.PercentFormatter(xmax=1))

    fig.text(0.01, 0.01, SOURCE_LINE, fontsize=7)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)

    return {"years": years, "values": values, "n_stations": n_stations}


def _build_ridgeline(metrics: pl.DataFrame, out_path: Path, decade_labels: list[str]) -> None:
    colors = ["#4575b4", "#fdae61", "#d73027"]
    bins = list(range(0, 366, 15))

    fig, ax = plt.subplots(figsize=(9, 5))
    for (start, end), color, label in zip(DECADES, colors, decade_labels):
        vals = (
            metrics.filter(pl.col("water_year").is_between(start, end))
            ["days_below"].drop_nulls().to_numpy()
        )
        ax.hist(vals, bins=bins, density=True, alpha=0.55, color=color,
                label=f"{label} (n={len(vals)})")

    ax.set_xlabel("Tage unter Q95 pro Stationsjahr")
    ax.set_ylabel("Dichte")
    ax.set_title("Verteilung der Tage unter Q95 pro Stationsjahr nach Dekade")
    ax.legend()
    fig.text(0.01, 0.01, SOURCE_LINE, fontsize=7)
    fig.tight_layout(rect=(0, 0.02, 1, 1))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150)
    plt.close(fig)


def _decade_histogram(metrics: pl.DataFrame) -> dict:
    counts = []
    for start, end in DECADES:
        vals = (
            metrics.filter(pl.col("water_year").is_between(start, end))
            ["days_below"].drop_nulls().to_numpy()
        )
        c, _ = np.histogram(vals, bins=HIST_BIN_EDGES)
        counts.append(c.tolist())
    return {"bin_edges": HIST_BIN_EDGES, "counts": counts}


def _decade_stats(decade_stats_df: pl.DataFrame) -> dict:
    order = [f"{s}-{e}" for s, e in DECADES]
    days = decade_stats_df.filter(pl.col("metric") == "days_below")
    by_decade = {row["decade"]: row for row in days.iter_rows(named=True)}
    stats: dict[str, list] = {"mean": [], "median": [], "p90": [], "share_zero": []}
    for key in order:
        row = by_decade.get(key)
        for stat in stats:
            v = row[stat] if row else None
            stats[stat].append(round(float(v), 3) if v is not None else None)
    return stats


def _index_section(path: Path, years: list[int]) -> dict:
    df = (
        pl.read_parquet(path)
        .filter(pl.col("water_year").is_between(*WINDOW))
        .sort("water_year")
    )
    by_year = {row["water_year"]: row for row in df.iter_rows(named=True)}
    out: dict[str, list] = {"days": [], "deficit": [], "ssi": []}
    for y in years:
        row = by_year.get(y)
        out["days"].append(round(float(row["index_days"]), 3) if row and row["index_days"] is not None else None)
        out["deficit"].append(round(float(row["index_deficit"]), 3) if row and row["index_deficit"] is not None else None)
        out["ssi"].append(round(float(row["index_ssi"]), 4) if row and row["index_ssi"] is not None else None)
    return out


def _trends_section(national_trends: pl.DataFrame) -> dict:
    out = {}
    for variant in ["primary", "natural"]:
        entry = {}
        for row in national_trends.filter(pl.col("variant") == variant).iter_rows(named=True):
            key = _METRIC_KEY.get(row["metric"])
            if key is None:
                continue
            entry[key] = {
                "p": round(float(row["p_value"]), 4) if row["p_value"] is not None else None,
                "sen": round(float(row["sens_slope"]), 4) if row["sens_slope"] is not None else None,
                "dir": row["trend"],
            }
        out[variant] = entry
    return out


def _stations_section(out_dir: Path, con, interim: Path) -> list[dict]:
    trends_csv = out_dir / "station_trends.csv"
    if not trends_csv.exists():
        return []
    station_trends = pl.read_csv(trends_csv)
    stations_meta = con.execute(
        "SELECT station_id, name, river, lat, lon, catchment_area FROM stations"
    ).pl()
    usable = pl.read_parquet(interim / "screen" / "usable_stations.parquet").select(
        "station_id", "is_near_natural"
    )
    joined = station_trends.join(stations_meta, on="station_id", how="left").join(
        usable, on="station_id", how="left"
    )

    # days_below-Jahresserie 1992-2025 je Station (fehlende Jahre als null) —
    # Datenbasis fuer die Sparkline der Stations-Detailansicht.
    metrics = pl.read_parquet(interim / "metrics" / "station_year_metrics.parquet").select(
        "station_id", "water_year", "days_below"
    )
    series_map: dict[str, dict[int, int]] = {}
    for sid, wy, days in metrics.iter_rows():
        series_map.setdefault(sid, {})[wy] = int(days) if days is not None else None
    series_years = list(range(WINDOW[0], WINDOW[1] + 1))

    out = []
    for row in joined.iter_rows(named=True):
        per_year = series_map.get(row["station_id"], {})
        out.append({
            "id": row["station_id"],
            "name": row["name"],
            "river": row["river"],
            "lat": row["lat"],
            "lon": row["lon"],
            "area_km2": round(float(row["catchment_area"]), 1) if row["catchment_area"] is not None else None,
            "days_trend": row["days_below_trend"],
            "days_p": round(float(row["days_below_p"]), 4) if row["days_below_p"] is not None else None,
            # Benjamini-Hochberg-korrigierter p-Wert (Multiplizitaet ueber alle
            # Pegel). Leer, wenn der Trendtest fuer die Station nicht rechenbar war.
            "days_p_fdr": round(float(row["days_below_p_fdr"]), 4) if row.get("days_below_p_fdr") is not None else None,
            "days_sen": round(float(row["days_below_sen"]), 4) if row["days_below_sen"] is not None else None,
            "nm7q_trend": row["nm7q_trend"],
            "nm7q_p": round(float(row["nm7q_p"]), 4) if row["nm7q_p"] is not None else None,
            "nm7q_p_fdr": round(float(row["nm7q_p_fdr"]), 4) if row.get("nm7q_p_fdr") is not None else None,
            # 4 signifikante Stellen: traegt -10.04 wie 7.6e-05 (Wertespanne der Pegel)
            "nm7q_sen": float(f"{float(row['nm7q_sen']):.4g}") if row["nm7q_sen"] is not None else None,
            "min_year": row["min_year"],
            "natural": bool(row["is_near_natural"]) if row["is_near_natural"] is not None else False,
            "series": [per_year.get(y) for y in series_years],
        })
    return out


def run(args: argparse.Namespace) -> int:
    log = StageLog(stage="render", log_dir=Path(args.log_dir))
    try:
        interim = Path(args.interim_dir)
        out_dir = Path(args.out_dir)
        con = connect(Path(args.db))

        primary_stations = _primary_stations(con, interim, Path(args.sinks))
        log.info(f"primary-Set: {primary_stations.height} Stationen")

        discharge = con.execute("SELECT station_id, date, q FROM discharge_daily").pl()
        thresholds = con.execute("SELECT station_id, q95 FROM station_thresholds").pl()
        usable_years = pl.read_parquet(
            interim / "screen" / "usable_station_years.parquet"
        ).select("station_id", "water_year")

        daily = daily_below_share(
            discharge, thresholds,
            primary_stations.select("station_id", "a_incremental"),
            usable_years,
        )
        log.counts("daily_share", rows_in=discharge.height, rows_out=daily.height)
        write_stage_parquet(daily, interim, "render", "daily_share")

        heatmap_data = _build_heatmap(daily, out_dir / "figures" / "heatmap.png", log)

        metrics_all = pl.read_parquet(interim / "metrics" / "station_year_metrics.parquet")
        decade_labels = [f"{s}–{e}" for s, e in DECADES]
        _build_ridgeline(metrics_all, out_dir / "figures" / "ridgeline.png", decade_labels)

        decades_hist = _decade_histogram(metrics_all)
        decade_stats_df = pl.read_parquet(interim / "trend" / "decade_stats.parquet")
        decades_stats = _decade_stats(decade_stats_df)

        agg_dir = interim / "aggregate"
        years = list(range(WINDOW[0], WINDOW[1] + 1))
        national_index = {
            "years": years,
            "primary": _index_section(agg_dir / "national_index_primary.parquet", years),
            "natural": _index_section(agg_dir / "national_index_natural.parquet", years),
        }

        national_trends = pl.read_parquet(interim / "trend" / "national_trends.parquet")
        trends = _trends_section(national_trends)

        stations_json = _stations_section(out_dir, con, interim)

        coverage_km2 = float(primary_stations["a_incremental"].sum())
        # Die tatsaechlich gewichtete Flaeche ist jahresabhaengig (nicht jede
        # Station hat in jedem Jahr Daten). coverage_km2 ist das Maximum,
        # coverage_km2_min das schwaechste Jahr des Fensters.
        coverage_year = pl.read_parquet(
            agg_dir / "national_index_primary.parquet"
        ).filter(pl.col("water_year").is_between(*WINDOW))["coverage_area_km2"].drop_nulls()
        coverage_km2_min = float(coverage_year.min()) if coverage_year.len() else coverage_km2

        site_text_path = Path(getattr(args, "site_text", "site/text.de.json"))
        # Katalog der zweiten Sprache: ueber die Namenskonvention abgeleitet,
        # nicht ueber ein eigenes CLI-Argument (siehe i18n.geschwister_katalog).
        # None heisst "keine zweite Sprachfassung", nicht "Fehler".
        site_text_zweitsprache = geschwister_katalog(site_text_path)

        basin_areas_path = Path(getattr(args, "basin_areas", "config/basin_domestic_area.csv"))
        foreign_km2, foreign_is_lower_bound = _foreign_area(
            primary_stations, basin_areas_path, coverage_km2, log
        )

        # Eingabe-Artefakte dieser Stufe -- Quelle des deterministischen
        # meta.generated (siehe generated_timestamp). Reine Leseseite: alles,
        # was render selbst schreibt, steht hier absichtlich nicht drin.
        generated_inputs = [
            Path(args.db),
            interim / "screen" / "usable_stations.parquet",
            interim / "screen" / "usable_station_years.parquet",
            interim / "metrics" / "station_year_metrics.parquet",
            agg_dir / "national_index_primary.parquet",
            agg_dir / "national_index_natural.parquet",
            interim / "trend" / "national_trends.parquet",
            interim / "trend" / "decade_stats.parquet",
            out_dir / "station_trends.csv",
            Path(args.sinks),
            basin_areas_path,
            # Markup- und Basemap-Quelle des --embed-Builds (site_embed.embed_site).
            # Bewusst unabhaengig davon, ob --embed gesetzt ist: meta.generated soll
            # denselben Wert haben, egal ob nur data.json oder auch index.html
            # geschrieben wird -- sonst haengt der Zeitstempel am Aufruf-Flag.
            Path(getattr(args, "site_template", "site/template.html")),
            Path(getattr(args, "site_geo", "site/geo.json")),
            site_text_path,
        ]
        # Der Katalog der zweiten Sprache ist genauso Eingabe wie der erste:
        # eine Uebersetzungsaenderung muss meta.generated anheben, sonst traegt
        # die englische Seite den Zeitstempel eines Standes, den sie nicht hat.
        if site_text_zweitsprache is not None:
            generated_inputs.append(site_text_zweitsprache)

        meta = {
            "generated": generated_timestamp(generated_inputs),
            "window": list(WINDOW),
            "n_stations_primary": primary_stations.height,
            "coverage_km2": round(coverage_km2, 1),
            "coverage_km2_min": round(coverage_km2_min, 1),
            "coverage_foreign_km2": round(foreign_km2, 1),
            "coverage_foreign_is_lower_bound": foreign_is_lower_bound,
            "source": "NIWIS (BfG/LAWA), Datenlizenzen je Station",
        }

        data = {
            "meta": meta,
            "heatmap": heatmap_data,
            "national_index": national_index,
            "trends": trends,
            "decades": {
                "labels": decade_labels,
                "days_below_hist": decades_hist,
                "stats": decades_stats,
            },
            "stations": stations_json,
        }

        site_path = Path(args.site_data)
        site_path.parent.mkdir(parents=True, exist_ok=True)
        site_path.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8"
        )
        log.info(f"site-data geschrieben: {site_path} ({site_path.stat().st_size} bytes)")

        if getattr(args, "embed", False):
            from niedrigwasser.site_embed import embed_alle_sprachen

            # Beide Sprachfassungen, Ableitung der zweiten und Aufraeumen einer
            # veralteten liegen in embed_alle_sprachen() -- nicht hier. Sonst
            # gaebe es diesen Bauweg vollstaendig und scripts/build_site.py nur
            # halb, und wer das Skript benutzt, bekaeme eine frische deutsche
            # neben einer veralteten englischen Seite.
            #
            # Die Kreuzpruefung zwischen den Sprachkatalogen (Schluessel-, id-
            # und Platzhalter-Paritaet, __locale__-Vollstaendigkeit) laeuft
            # eine Ebene tiefer in embed_site() selbst (siehe dort und
            # niedrigwasser.i18n.lade_kataloge_fuer_pruefung), damit sie auch
            # dann greift, wenn jemand nur eine einzelne Seite baut.
            vorgabe = getattr(args, "site_html_en", None)
            embed_alle_sprachen(
                Path(args.site_template), site_path, Path(args.site_html),
                geo_path=Path(getattr(args, "site_geo", "site/geo.json")),
                text_path=site_text_path,
                out_path_zweit=Path(vorgabe) if vorgabe else None,
                melde=log.info,
            )

        con.close()
        return 0
    finally:
        log.close()
