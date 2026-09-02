import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

import polars as pl
import pytest

from niedrigwasser.i18n import I18nFehler
from niedrigwasser.stages.render import GERMANY_AREA_KM2, generated_timestamp, run
from niedrigwasser.store import connect


def _daily_rows(station_id: str, start: date, end: date, q: float) -> list[dict]:
    rows = []
    d = start
    while d <= end:
        rows.append({"station_id": station_id, "date": d, "q": q, "quality_flag": None})
        d += timedelta(days=1)
    return rows


def _seed(db: Path, interim: Path, out_dir: Path, sinks_path: Path,
          basin_areas_path: Path | None = None) -> None:
    con = connect(db)
    # A -> B (B ist Auslass). A ist naturnah, B nicht.
    stations_df = pl.DataFrame({
        "station_id": ["A", "B"],
        "name": ["Station A", "Station B"],
        "river": ["Fluss1", "Fluss1"],
        "lat": [50.0, 50.1],
        "lon": [8.0, 8.1],
        "catchment_area": [100.0, 150.0],
        "downstream_id": ["B", None],
        "gauge_datum": [None, None],
        "source": ["x", "x"],
        "river_km": [None, None],
        "gkz": [None, None],
        "license": [None, None],
    })
    con.execute("INSERT INTO stations SELECT * FROM stations_df")

    thresholds_df = pl.DataFrame({
        "station_id": ["A", "B"],
        "q95": [2.0, 2.0],
        "mnq": [1.0, 1.0],
        "ref_period_start": [1992, 1992],
        "ref_period_end": [2011, 2011],
    })
    con.execute("INSERT INTO station_thresholds SELECT * FROM thresholds_df")

    # Wasserjahr 2000: A durchgehend unter Schwelle (q=1 < q95=2), B durchgehend darueber.
    wy_start = date(1999, 11, 1)
    wy_end = date(2000, 10, 31)
    discharge_df = pl.DataFrame(
        _daily_rows("A", wy_start, wy_end, 1.0) + _daily_rows("B", wy_start, wy_end, 3.0)
    )
    con.execute("INSERT INTO discharge_daily SELECT * FROM discharge_df")
    con.close()

    usable_stations = pl.DataFrame({
        "station_id": ["A", "B"],
        "n_usable_years": [30, 30],
        "flags": [[], []],
        "is_near_natural": [True, False],
    })
    (interim / "screen").mkdir(parents=True)
    usable_stations.write_parquet(interim / "screen" / "usable_stations.parquet")

    usable_station_years = pl.DataFrame({
        "station_id": ["A", "B"],
        "water_year": [2000, 2000],
        "summer_days_present": [184, 184],
        "total_days_present": [366, 366],
        "summer_coverage": [1.0, 1.0],
        "data_completeness": [1.0, 1.0],
    })
    usable_station_years.write_parquet(interim / "screen" / "usable_station_years.parquet")

    # station_year_metrics: ein paar Jahre je Dekade fuer Histogramm/Ridgeline.
    years = [1992, 1997, 2001, 2002, 2008, 2013, 2014, 2020, 2025]
    days_below = [5, 10, 15, 20, 25, 30, 35, 40, 45]
    metrics = pl.DataFrame({
        "station_id": ["A"] * len(years),
        "water_year": years,
        "days_below": days_below,
        "max_spell": days_below,
        "deficit_volume_m3": [float(d) * 1000.0 for d in days_below],
        "nm7q": [1.5] * len(years),
        "ssi": [-0.5] * len(years),
        "data_completeness": [1.0] * len(years),
    })
    (interim / "metrics").mkdir(parents=True)
    metrics.write_parquet(interim / "metrics" / "station_year_metrics.parquet")

    # aggregate: national_index_primary/natural fuer 1992-2025 (34 Jahre).
    idx_years = list(range(1992, 2026))
    n = len(idx_years)
    agg_dir = interim / "aggregate"
    agg_dir.mkdir(parents=True)
    for variant in ["primary", "natural"]:
        idx = pl.DataFrame({
            "water_year": idx_years,
            "index_days": [float(i % 30) for i in range(n)],
            "index_deficit": [float(i) * 0.5 for i in range(n)],
            "index_ssi": [float(i) * -0.01 for i in range(n)],
            "n_stations": [2] * n,
            "coverage_area_km2": [250.0] * n,
        })
        idx.write_parquet(agg_dir / f"national_index_{variant}.parquet")

    # trend: national_trends + decade_stats
    trend_dir = interim / "trend"
    trend_dir.mkdir(parents=True)
    national_trends = pl.DataFrame({
        "variant": ["primary", "primary", "primary", "natural", "natural", "natural"],
        "metric": ["index_days", "index_deficit", "index_ssi"] * 2,
        "trend": ["increasing", "no trend", "decreasing"] * 2,
        "p_value": [0.01, 0.5, 0.02] * 2,
        "sens_slope": [0.3, 0.0, -0.1] * 2,
        "n": [34] * 6,
    })
    national_trends.write_parquet(trend_dir / "national_trends.parquet")

    decade_rows = []
    for metric in ["days_below", "deficit_mm", "nm7q"]:
        for decade, n_, mean, median, p90, sz in [
            ("1992-2001", 2, 7.5, 7.5, 9.9, 0.0),
            ("2002-2013", 3, 24.3, 25.0, 29.5, 0.0),
            ("2014-2025", 3, 40.0, 40.0, 44.5, 0.0),
        ]:
            decade_rows.append({
                "metric": metric, "decade": decade, "n": n_,
                "mean": mean, "median": median, "p90": p90, "share_zero": sz,
            })
    pl.DataFrame(decade_rows).write_parquet(trend_dir / "decade_stats.parquet")

    out_dir.mkdir(parents=True)
    station_trends = pl.DataFrame({
        "station_id": ["A", "B"],
        "n_years": [30, 28],
        "days_below_trend": ["increasing", "no trend"],
        "days_below_p": [0.01, 0.4],
        "days_below_sen": [0.2, 0.0],
        "nm7q_trend": ["decreasing", "no trend"],
        "nm7q_p": [0.02, 0.6],
        "nm7q_sen": [-0.1, 0.0],
        "min_year": [2018, 2003],
        # FDR-korrigierte p-Werte (Benjamini-Hochberg); B mit Null-Werten,
        # damit die None-Sicherheit der Rundung mitgeprueft wird.
        "days_below_p_fdr": [0.02, None],
        "nm7q_p_fdr": [0.03, None],
    })
    station_trends.write_csv(out_dir / "station_trends.csv")

    sinks_path.write_text("station_id,category,note\n", encoding="utf-8")

    if basin_areas_path is not None:
        # Auslandsanteile: A liegt im primary-Set (100 - 60 = 40 km2 Ausland),
        # C nicht -> darf nicht mitgezaehlt werden.
        basin_areas_path.write_text(
            "station_id,basin,catchment_km2,domestic_km2,source,note\n"
            "A,Fluss1,100,60,testquelle,test\n"
            "C,Fluss9,500,100,testquelle,nicht im primary-Set\n",
            encoding="utf-8",
        )


def test_render_stage_end_to_end(tmp_path: Path):
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    out_dir = tmp_path / "out"
    sinks_path = tmp_path / "sink_categories.csv"
    basin_areas_path = tmp_path / "basin_domestic_area.csv"
    site_data = tmp_path / "site" / "data.json"
    _seed(db, interim, out_dir, sinks_path, basin_areas_path)

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        out_dir=str(out_dir), site_data=str(site_data), sinks=str(sinks_path),
        basin_areas=str(basin_areas_path),
    ))
    assert rc == 0

    # Parquet
    daily_share_path = interim / "render" / "daily_share.parquet"
    assert daily_share_path.exists()
    daily_share = pl.read_parquet(daily_share_path)
    assert daily_share.filter(pl.col("water_year") == 2000).height == 365
    # A ist immer unter der Schwelle, B nie. a_incremental: A=100 (100-0),
    # B=50 (150-100, da A -> B) -> share = 100 / 150.
    row = daily_share.filter((pl.col("water_year") == 2000) & (pl.col("doy") == 100))
    assert row["share"][0] == 100.0 / 150.0

    # PNGs
    heatmap_png = out_dir / "figures" / "heatmap.png"
    ridgeline_png = out_dir / "figures" / "ridgeline.png"
    assert heatmap_png.exists() and heatmap_png.stat().st_size > 5000
    assert ridgeline_png.exists() and ridgeline_png.stat().st_size > 5000

    # site/data.json
    assert site_data.exists()
    data = json.loads(site_data.read_text(encoding="utf-8"))

    assert data["meta"]["window"] == [1992, 2025]
    assert data["meta"]["n_stations_primary"] == 2
    assert data["meta"]["coverage_km2"] == 150.0
    # Coverage-Spanne ueber die Jahre aus national_index_primary (Seed: konstant 250).
    assert data["meta"]["coverage_km2_min"] == 250.0
    # Auslandsanteil: nur der im primary-Set enthaltene Auslass A zaehlt
    # (100 - 60 = 40); C steht zwar in der CSV, ist aber keine primary-Station.
    assert data["meta"]["coverage_foreign_km2"] == 40.0
    assert data["meta"]["coverage_foreign_is_lower_bound"] is True

    heatmap = data["heatmap"]
    assert len(heatmap["years"]) == 34
    assert heatmap["years"][0] == 1992
    assert heatmap["years"][-1] == 2025
    assert len(heatmap["values"]) == len(heatmap["years"])
    assert all(len(row) == 365 for row in heatmap["values"])
    # water_year 2000 ist Index 8 (1992..2000 -> 9 Eintraege, Index 8).
    assert heatmap["values"][8][99] == round(100.0 / 150.0, 3)
    # Jahre ohne Daten (z.B. 1992) sind auf 0.0 zurueckgefallen.
    assert all(v == 0.0 for v in heatmap["values"][0])

    ni = data["national_index"]
    assert len(ni["years"]) == 34
    assert len(ni["primary"]["days"]) == 34
    assert len(ni["natural"]["ssi"]) == 34

    trends = data["trends"]
    assert set(trends.keys()) == {"primary", "natural"}
    assert trends["primary"]["days"]["dir"] == "increasing"
    assert trends["primary"]["days"]["p"] == 0.01

    decades = data["decades"]
    assert decades["labels"] == ["1992–2001", "2002–2013", "2014–2025"]
    assert len(decades["days_below_hist"]["counts"]) == 3
    assert len(decades["days_below_hist"]["bin_edges"]) == len(decades["days_below_hist"]["counts"][0]) + 1
    assert decades["stats"]["median"] == [7.5, 25.0, 40.0]

    stations = {s["id"]: s for s in data["stations"]}
    assert set(stations.keys()) == {"A", "B"}
    assert stations["A"]["name"] == "Station A"
    assert stations["A"]["natural"] is True
    assert stations["B"]["natural"] is False
    assert stations["A"]["days_trend"] == "increasing"

    # NM7Q-Trend fuer das Stations-Detail-Panel
    assert stations["A"]["nm7q_trend"] == "decreasing"
    assert stations["A"]["nm7q_p"] == 0.02
    assert stations["A"]["nm7q_sen"] == -0.1
    assert stations["B"]["nm7q_sen"] == 0.0

    # FDR-korrigierte p-Werte fuer Methodik-Absatz und Detailpanel
    assert stations["A"]["days_p_fdr"] == 0.02
    assert stations["A"]["nm7q_p_fdr"] == 0.03
    assert stations["B"]["days_p_fdr"] is None
    assert stations["B"]["nm7q_p_fdr"] is None

    # days_below-Jahresserie 1992-2025 (Sparkline-Datenbasis) + EZG-Flaeche
    assert stations["A"]["area_km2"] == 100.0
    assert stations["B"]["area_km2"] == 150.0
    series_a = stations["A"]["series"]
    assert len(series_a) == 34
    assert series_a[0] == 5          # 1992
    assert series_a[-1] == 45        # 2025
    assert series_a[1] is None       # 1993: kein Metrics-Eintrag -> null
    assert series_a[2002 - 1992] == 20
    # B hat keine Metrics-Zeilen -> komplette Null-Serie
    assert all(v is None for v in stations["B"]["series"])

    log_path = tmp_path / "logs" / "render.log"
    assert log_path.exists()
    log_text = log_path.read_text(encoding="utf-8")
    assert "Stage 'render' gestartet" in log_text
    assert "Stage beendet" in log_text


def test_render_stage_foreign_area_fallback(tmp_path: Path):
    """Ohne basin_domestic_area.csv faellt der Auslandsanteil auf die triviale
    Schranke coverage - Flaeche Deutschlands zurueck (hier 0, da coverage klein)."""
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    out_dir = tmp_path / "out"
    sinks_path = tmp_path / "sink_categories.csv"
    site_data = tmp_path / "site" / "data.json"
    _seed(db, interim, out_dir, sinks_path)

    rc = run(argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        out_dir=str(out_dir), site_data=str(site_data), sinks=str(sinks_path),
        basin_areas=str(tmp_path / "gibt-es-nicht.csv"),
    ))
    assert rc == 0

    data = json.loads(site_data.read_text(encoding="utf-8"))
    assert data["meta"]["coverage_foreign_km2"] == max(0.0, 150.0 - GERMANY_AREA_KM2)
    assert data["meta"]["coverage_foreign_is_lower_bound"] is True
    log_text = (tmp_path / "logs" / "render.log").read_text(encoding="utf-8")
    assert "Fallback" in log_text


def _render_args(tmp_path: Path, db: Path, interim: Path, out_dir: Path,
                 sinks_path: Path, site_data: Path) -> argparse.Namespace:
    # site_template/site_geo/site_text bewusst auf nicht existierende tmp-Pfade:
    # sonst zoegen die getattr-Defaults die echten Repo-Dateien
    # (site/template.html, site/geo.json, site/text.de.json) in die mtime-Quelle
    # von meta.generated und die Tests haengen am Zustand des
    # Arbeitsverzeichnisses.
    return argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        out_dir=str(out_dir), site_data=str(site_data), sinks=str(sinks_path),
        basin_areas=str(tmp_path / "gibt-es-nicht.csv"),
        site_template=str(tmp_path / "kein-template.html"),
        site_geo=str(tmp_path / "kein-geo.json"),
        site_text=str(tmp_path / "kein-text.de.json"),
    )


def _set_mtimes(root: Path, epoch: int) -> None:
    """Alle Dateien unter root auf einen festen mtime setzen -- macht den
    mtime-Fallback von meta.generated im Test exakt vorhersagbar."""
    for p in root.rglob("*"):
        if p.is_file():
            os.utime(p, (epoch, epoch))


def test_render_generated_uses_source_date_epoch(tmp_path: Path, monkeypatch):
    """SOURCE_DATE_EPOCH ueberschreibt meta.generated deterministisch (UTC-ISO)."""
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    out_dir = tmp_path / "out"
    sinks_path = tmp_path / "sink_categories.csv"
    site_data = tmp_path / "site" / "data.json"
    _seed(db, interim, out_dir, sinks_path)

    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1700000000")
    rc = run(_render_args(tmp_path, db, interim, out_dir, sinks_path, site_data))
    assert rc == 0

    data = json.loads(site_data.read_text(encoding="utf-8"))
    assert data["meta"]["generated"] == "2023-11-14T22:13:20+00:00"


def test_render_generated_falls_back_to_input_mtime(tmp_path: Path, monkeypatch):
    """Ohne SOURCE_DATE_EPOCH kommt meta.generated aus der juengsten mtime der
    Eingaben, nicht aus der Wallclock.

    Der Test setzt die Eingabe-mtimes hart auf einen festen Epoch und prueft den
    EXAKTEN ISO-String: ein Gleichheitsvergleich zweier Laeufe allein wuerde bei
    der alten Wallclock-Variante durchrutschen, sobald beide Laeufe in dieselbe
    Sekunde fallen. Der Byte-Vergleich bleibt als Zusatz erhalten.
    """
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    out_dir = tmp_path / "out"
    sinks_path = tmp_path / "sink_categories.csv"
    site_data = tmp_path / "site" / "data.json"
    _seed(db, interim, out_dir, sinks_path)
    _set_mtimes(tmp_path, 1600000000)

    args = _render_args(tmp_path, db, interim, out_dir, sinks_path, site_data)
    assert run(args) == 0
    first_bytes = site_data.read_bytes()
    assert json.loads(first_bytes.decode("utf-8"))["meta"]["generated"] == (
        "2020-09-13T12:26:40+00:00"
    )

    assert run(args) == 0
    second_bytes = site_data.read_bytes()
    assert json.loads(second_bytes.decode("utf-8"))["meta"]["generated"] == (
        "2020-09-13T12:26:40+00:00"
    )
    assert first_bytes == second_bytes


def test_generated_timestamp_rejects_invalid_source_date_epoch():
    """Unbrauchbares SOURCE_DATE_EPOCH scheitert hart und nennt die Variable."""
    with pytest.raises(ValueError, match="SOURCE_DATE_EPOCH"):
        generated_timestamp([], {"SOURCE_DATE_EPOCH": "gestern"})


def _locale_stub() -> dict:
    """Vollstaendiger __locale__-Block (Task 7 Schritt 4: pruefe_locale-Test-Fixture).

    Werte sind beliebig, es zaehlt nur, dass alle LOCALE_PFLICHTFELDER da sind.
    """
    return {
        "decimal": ",",
        "thousands": ".",
        "percentSpaceNoBreak": "&nbsp;",
        "percentSpaceBreaking": " ",
        "months": ["Jan"],
        "monthsDate": ["Jan."],
        "dateFormat": "{d}. {m}.",
        "dateRange": "{a}–{b}. {m}.",
        "pLess": "p &lt; 0,001",
        "pLessValue": "&lt; 0,001",
    }


def _embed_render_args(tmp_path: Path, db: Path, interim: Path, out_dir: Path,
                       sinks_path: Path, site_data: Path, site_dir: Path) -> argparse.Namespace:
    """Wie _render_args, aber mit --embed und echten (Test-)Site-Dateien.

    Anders als _render_args() zeigen site_template/site_geo/site_text hier
    bewusst auf tatsaechlich vorhandene Dateien -- der Build-Pfad unter Test
    IST der Embed-Pfad, der beide Kataloge lesen muss.
    """
    return argparse.Namespace(
        db=str(db), interim_dir=str(interim), log_dir=str(tmp_path / "logs"),
        out_dir=str(out_dir), site_data=str(site_data), sinks=str(sinks_path),
        basin_areas=str(tmp_path / "gibt-es-nicht.csv"),
        site_template=str(site_dir / "template.html"),
        site_html=str(site_dir / "index.html"),
        site_geo=str(site_dir / "geo.json"),
        site_text=str(site_dir / "text.de.json"),
        embed=True,
    )


def _seed_und_site_dir(tmp_path: Path):
    """Gemeinsames Setup der drei Embed-Verdrahtungstests (Task 7 Schritt 4)."""
    db = tmp_path / "t.duckdb"
    interim = tmp_path / "interim"
    out_dir = tmp_path / "out"
    sinks_path = tmp_path / "sink_categories.csv"
    site_data = tmp_path / "site" / "data.json"
    site_dir = tmp_path / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    _seed(db, interim, out_dir, sinks_path)
    (site_dir / "template.html").write_text(
        '<div data-i18n="a"><span id="k-x">0</span></div>'
        '<script id="d" type="application/json">/*__DATA__*/</script>',
        encoding="utf-8",
    )
    return db, interim, out_dir, sinks_path, site_data, site_dir


def test_render_stage_embed_bricht_bei_id_abweichung_ab(tmp_path: Path):
    """Task 7 Schritt 4: pruefe_kataloge muss im Build laufen, nicht nur im Test.

    Ein englischer Katalogwert mit umbenanntem Datenplatzhalter (id) liesse
    die Kennzahl auf der Seite leer -- ohne diese Verdrahtung faellt das erst
    einem Leser auf.
    """
    db, interim, out_dir, sinks_path, site_data, site_dir = _seed_und_site_dir(tmp_path)
    (site_dir / "text.de.json").write_text(
        json.dumps({"a": '<span id="k-x">Wert</span>', "__locale__": _locale_stub()}),
        encoding="utf-8",
    )
    (site_dir / "text.en.json").write_text(
        json.dumps({"a": '<span id="k-y">Value</span>', "__locale__": _locale_stub()}),
        encoding="utf-8",
    )

    with pytest.raises(I18nFehler, match="Datenplatzhalter"):
        run(_embed_render_args(tmp_path, db, interim, out_dir, sinks_path, site_data, site_dir))

    assert not (site_dir / "index.html").exists()


def test_render_stage_embed_bricht_bei_platzhalter_abweichung_ab(tmp_path: Path):
    """Task 7 Schritt 4: Platzhalter-Paritaet (t()-Platzhalter, nicht id) muss

    ebenso im Build laufen. Ein umbenannter {platzhalter} stuende sonst
    woertlich als '{peak}' sichtbar auf der ausgelieferten Seite.
    """
    db, interim, out_dir, sinks_path, site_data, site_dir = _seed_und_site_dir(tmp_path)
    (site_dir / "text.de.json").write_text(
        json.dumps({"a": "Wert {peak}", "__locale__": _locale_stub()}),
        encoding="utf-8",
    )
    (site_dir / "text.en.json").write_text(
        json.dumps({"a": "Value {spitze}", "__locale__": _locale_stub()}),
        encoding="utf-8",
    )

    with pytest.raises(I18nFehler, match="Platzhalter"):
        run(_embed_render_args(tmp_path, db, interim, out_dir, sinks_path, site_data, site_dir))

    assert not (site_dir / "index.html").exists()


def test_render_stage_embed_ohne_englischen_katalog_baut_trotzdem(tmp_path: Path):
    """Task 7 Schritt 4: der englische Katalog ist optional.

    pruefe_kataloge greift konstruktionsbedingt erst ab zwei Katalogen --
    fehlt site/text.en.json, heisst das 'keine englische Ausgabe', nicht
    'Fehler'. Der Build muss trotzdem durchlaufen.
    """
    db, interim, out_dir, sinks_path, site_data, site_dir = _seed_und_site_dir(tmp_path)
    (site_dir / "text.de.json").write_text(
        json.dumps({"a": '<span id="k-x">Wert</span>', "__locale__": _locale_stub()}),
        encoding="utf-8",
    )
    assert not (site_dir / "text.en.json").exists()

    rc = run(_embed_render_args(tmp_path, db, interim, out_dir, sinks_path, site_data, site_dir))
    assert rc == 0

    html = (site_dir / "index.html").read_text(encoding="utf-8")
    assert '<div><span id="k-x">Wert</span></div>' in html


# --- Zweite Sprachausgabe (Fix-Runde 2 zu Task 8) --------------------------
#
# Bis hierher belegte KEIN Test, dass render --embed die zweite Sprachfassung
# ueberhaupt schreibt. Der einzige Beleg war eine Log-Zeile von Hand.


def _zweisprachiges_site_dir(tmp_path: Path):
    """Setup wie _seed_und_site_dir, aber mit zwei gueltigen Katalogen."""
    db, interim, out_dir, sinks_path, site_data, site_dir = _seed_und_site_dir(tmp_path)
    (site_dir / "text.de.json").write_text(
        json.dumps({"a": '<span id="k-x">Wert</span>', "__locale__": _locale_stub()}),
        encoding="utf-8",
    )
    (site_dir / "text.en.json").write_text(
        json.dumps({"a": '<span id="k-x">Value</span>', "__locale__": _locale_stub()}),
        encoding="utf-8",
    )
    return db, interim, out_dir, sinks_path, site_data, site_dir


def test_render_stage_embed_schreibt_beide_sprachfassungen(tmp_path: Path):
    """Der Erfolgsfall der zweiten Sprachausgabe -- und zugleich der Beleg,
    dass ihr Default-Ausgabepfad nicht ins Repo zeigt.

    _embed_render_args setzt site_html_en absichtlich NICHT. Mit einem
    Literal-Default ("site/index.en.html") schriebe dieser Testlauf in die
    echte Repo-Datei, und hier im tmp_path entstuende nichts. Der Pfad muss
    aus site_html abgeleitet werden, also neben der ersten Sprachfassung
    landen.
    """
    db, interim, out_dir, sinks_path, site_data, site_dir = _zweisprachiges_site_dir(tmp_path)

    args = _embed_render_args(tmp_path, db, interim, out_dir, sinks_path, site_data, site_dir)
    assert not hasattr(args, "site_html_en")
    assert run(args) == 0

    deutsch = site_dir / "index.html"
    englisch = site_dir / "index.en.html"
    assert deutsch.exists()
    assert englisch.exists(), "zweite Sprachfassung nicht neben der ersten gelandet"

    de_html = deutsch.read_text(encoding="utf-8")
    en_html = englisch.read_text(encoding="utf-8")
    assert '<span id="k-x">Wert</span>' in de_html
    assert '<span id="k-x">Value</span>' in en_html
    # Inhaltsanker, nicht nur Ungleichheit: Jede Fassung traegt genau ihren
    # eigenen Text und nicht den der anderen.
    assert "Value" not in de_html
    assert "Wert" not in en_html


def test_render_stage_embed_beachtet_site_html_en(tmp_path: Path):
    """Ist --site-html-en gesetzt, geht die zweite Fassung genau dorthin."""
    db, interim, out_dir, sinks_path, site_data, site_dir = _zweisprachiges_site_dir(tmp_path)

    args = _embed_render_args(tmp_path, db, interim, out_dir, sinks_path, site_data, site_dir)
    ziel = tmp_path / "anderswo" / "englisch.html"
    ziel.parent.mkdir()
    args.site_html_en = str(ziel)

    assert run(args) == 0
    assert ziel.exists()
    assert '<span id="k-x">Value</span>' in ziel.read_text(encoding="utf-8")
    # Der abgeleitete Default darf dann nicht zusaetzlich bedient werden.
    assert not (site_dir / "index.en.html").exists()


def test_render_stage_embed_nimmt_zweiten_katalog_in_generated_inputs(tmp_path: Path,
                                                                      monkeypatch):
    """Eine Uebersetzungsaenderung muss meta.generated anheben.

    Sonst traegt die englische Seite den Zeitstempel eines Standes, den sie
    nicht hat. Geprueft ueber die mtime-Quelle: text.en.json ist die juengste
    Eingabe: liegt sie nicht in generated_inputs, bleibt meta.generated auf dem
    aelteren Wert stehen.
    """
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    db, interim, out_dir, sinks_path, site_data, site_dir = _zweisprachiges_site_dir(tmp_path)

    _set_mtimes(tmp_path, 1600000000)
    os.utime(site_dir / "text.en.json", (1600003600, 1600003600))

    args = _embed_render_args(tmp_path, db, interim, out_dir, sinks_path, site_data, site_dir)
    assert run(args) == 0

    data = json.loads(site_data.read_text(encoding="utf-8"))
    assert data["meta"]["generated"] == "2020-09-13T13:26:40+00:00"


def test_render_stage_embed_entfernt_veraltete_zweitsprache(tmp_path: Path):
    """Fehlt der Geschwisterkatalog, darf keine alte zweite Fassung liegen bleiben.

    Sie waere von nichts mehr gedeckt: Der Export kopierte sie mit,
    build_embed.py baute daraus ein gate-sauberes Fragment, und der
    Herkunfts-Hash zeigte korrekt auf eine veraltete Quelle -- nur vergleicht
    ihn nichts. Plausibel, unauffaellig, falsch.
    """
    db, interim, out_dir, sinks_path, site_data, site_dir = _seed_und_site_dir(tmp_path)
    (site_dir / "text.de.json").write_text(
        json.dumps({"a": '<span id="k-x">Wert</span>', "__locale__": _locale_stub()}),
        encoding="utf-8",
    )
    assert not (site_dir / "text.en.json").exists()
    veraltet = site_dir / "index.en.html"
    veraltet.write_text("<p>Stand von gestern</p>", encoding="utf-8")

    args = _embed_render_args(tmp_path, db, interim, out_dir, sinks_path, site_data, site_dir)
    assert run(args) == 0

    assert (site_dir / "index.html").exists()
    assert not veraltet.exists(), "veraltete zweite Sprachfassung blieb liegen"
    log_text = (tmp_path / "logs" / "render.log").read_text(encoding="utf-8")
    assert "kein Katalog text.en.json" in log_text
    assert "veraltete zweite Sprachfassung entfernt" in log_text
