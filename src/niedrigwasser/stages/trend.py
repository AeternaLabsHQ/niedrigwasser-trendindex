from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from niedrigwasser.store import StageLog, connect, write_stage_parquet
from niedrigwasser.trend import (
    bh_adjust,
    decade_stats,
    empirical_weibull_rp,
    fit_gev_nonstationary,
    mk_trend,
    return_period_shift,
)

WINDOW = (1992, 2025)
MIN_YEARS = 25
GEV_TARGET_YEAR = 2018
ALPHA = 0.05
VARIANTS = ["primary", "natural", "allsinks", "allsinks_natural"]
NATIONAL_METRICS = ["index_days", "index_deficit", "index_ssi"]


def _station_trends(metrics: pl.DataFrame) -> pl.DataFrame:
    df = metrics.filter(pl.col("water_year").is_between(*WINDOW))
    rows = []
    for (station,), grp in df.group_by("station_id", maintain_order=True):
        g = grp.sort("water_year")
        n_years = g.height
        if n_years < MIN_YEARS:
            continue

        days_g = g.filter(pl.col("days_below").is_not_null())
        days_vals = [float(v) for v in days_g["days_below"].to_list()]
        days_res = mk_trend(days_vals)

        nm7q_g = g.filter(pl.col("nm7q").is_not_null())
        nm7q_vals = [float(v) for v in nm7q_g["nm7q"].to_list()]
        nm7q_res = mk_trend(nm7q_vals)
        if nm7q_g.height:
            # Tie-Break bei mehreren Jahren mit identischem NM7Q-Minimum:
            # fruehestes Jahr gewinnt (zweites Sortkriterium water_year, aufsteigend).
            min_year = int(nm7q_g.sort(["nm7q", "water_year"])["water_year"][0])
        else:
            min_year = None

        rows.append({
            "station_id": station, "n_years": n_years,
            "days_below_trend": days_res["trend"],
            "days_below_p": days_res["p_value"],
            "days_below_sen": days_res["sens_slope"],
            "nm7q_trend": nm7q_res["trend"],
            "nm7q_p": nm7q_res["p_value"],
            "nm7q_sen": nm7q_res["sens_slope"],
            "min_year": min_year,
        })
    station_trends = pl.DataFrame(rows) if rows else pl.DataFrame(
        schema={
            "station_id": pl.String, "n_years": pl.Int64,
            "days_below_trend": pl.String, "days_below_p": pl.Float64, "days_below_sen": pl.Float64,
            "nm7q_trend": pl.String, "nm7q_p": pl.Float64, "nm7q_sen": pl.Float64,
            "min_year": pl.Int64,
        }
    )
    # Multiplizitaets-Korrektur (Benjamini-Hochberg, FDR): je Kennzahl eine
    # eigene Testfamilie ueber alle Stationen - days_below und nm7q werden
    # NICHT gemeinsam korrigiert. Die Roh-p-Werte und die bestehende
    # Signifikanzlogik bleiben unangetastet; _p_fdr ist eine Zusatzspalte.
    return station_trends.with_columns(
        pl.Series("days_below_p_fdr",
                  bh_adjust(station_trends["days_below_p"].to_list()), dtype=pl.Float64),
        pl.Series("nm7q_p_fdr",
                  bh_adjust(station_trends["nm7q_p"].to_list()), dtype=pl.Float64),
    )


def _national_trends(indices: dict[str, pl.DataFrame]) -> pl.DataFrame:
    # Die national_index_*-Parquets enthalten auch das Wasserjahr 1991; der
    # WINDOW-Filter (Trend-Scope 1992-2025) schneidet es weg. Grund ist die
    # Datenlage: NIWIS liefert ab 1.1.1991, das Wasserjahr 1991 beginnt aber am
    # 1.11.1990 -- ihm fehlen November und Dezember 1990, es hat 304 statt 365
    # Tage und ist mit vollen Jahren nicht vergleichbar.
    # F1: der Schnitt aendert den Trend sichtbar (ohne ihn zieht der 1991-Wert
    # den TFPW-MK v.a. bei index_ssi ins "no trend") -- das ist seine Wirkung,
    # nicht seine Begruendung.
    rows = []
    for variant, idx in indices.items():
        idx_sorted = idx.filter(pl.col("water_year").is_between(*WINDOW)).sort("water_year")
        for metric in NATIONAL_METRICS:
            # Luecken-Guard wie bei den Stationstrends: null und NaN raus,
            # bevor gecastet wird (v == v ist der NaN-Check ohne Import).
            vals = [float(v) for v in idx_sorted[metric].to_list()
                    if v is not None and v == v]
            res = mk_trend(vals)
            rows.append({
                "variant": variant, "metric": metric,
                "trend": res["trend"], "p_value": res["p_value"],
                "sens_slope": res["sens_slope"], "n": res["n"],
            })
    return pl.DataFrame(rows)


def _decade_stats_all(metrics: pl.DataFrame, stations: pl.DataFrame) -> pl.DataFrame:
    m = metrics.join(
        stations.select("station_id", "catchment_area"), on="station_id", how="left",
    ).with_columns(
        (pl.col("deficit_volume_m3") / (pl.col("catchment_area") * 1e6) * 1000.0)
        .alias("deficit_mm")
    )
    parts = []
    for col in ["days_below", "deficit_mm", "nm7q"]:
        d = decade_stats(m, col).with_columns(pl.lit(col).alias("metric"))
        parts.append(d)
    return pl.concat(parts).select("metric", "decade", "n", "mean", "median", "p90", "share_zero")


def _gev_deficit(primary_idx: pl.DataFrame) -> pl.DataFrame:
    # WINDOW-Filter (siehe _national_trends): Fit-Basis ist 1992-2025 (34
    # Werte), nicht die im Parquet zusaetzlich enthaltenen 1991er-Daten.
    idx_sorted = primary_idx.filter(pl.col("water_year").is_between(*WINDOW)).sort("water_year")
    # Luecken-Guard (siehe _national_trends): null/NaN gehen nicht in den Fit.
    # Die Kovariate t des Fits ist danach 0..n-1 ueber die verbleibenden Werte,
    # nicht das Wasserjahr - eine Luecke mitten in der Reihe staucht die
    # Zeitachse leicht (in den Realdaten ist die Reihe lueckenlos).
    values = [float(v) for v in idx_sorted["index_deficit"].to_list()
              if v is not None and v == v]
    n_years = len(values)

    # Zwei Fits gegenueberstellen: bounded (xi in [-0.5,0.5], numerisch
    # stabil bei n=34) und free (unrestringiert, zeigt wie stark die
    # Punktschaetzung vom Bound getragen wird). Der LR-Test (Trend-Frage)
    # ist robust gegenueber beiden; die Wiederkehrintervall-Punktschaetzung
    # (rp_*) ist es bei n=34 nicht - siehe Report.
    fit_bounded = fit_gev_nonstationary(values)
    fit_free = fit_gev_nonstationary(values, xi_bound=None)

    target = idx_sorted.filter(pl.col("water_year") == GEV_TARGET_YEAR)
    row: dict = {
        "n_years": n_years,
        "target_year": GEV_TARGET_YEAR,
        "value": None,
        "error": fit_bounded.get("error"),
        "mu0": fit_bounded.get("mu0"), "mu1": fit_bounded.get("mu1"),
        "sigma": fit_bounded.get("sigma"), "xi": fit_bounded.get("xi"),
        "ll_ns": fit_bounded.get("ll_ns"), "ll_s": fit_bounded.get("ll_s"),
        "lr": fit_bounded.get("lr"), "p_value": fit_bounded.get("p_value"),
        "rp_start": None, "rp_end": None,
        "error_free": fit_free.get("error"),
        "xi_free": fit_free.get("xi"), "mu1_free": fit_free.get("mu1"),
        "p_value_free": fit_free.get("p_value"),
        "rp_start_free": None, "rp_end_free": None,
        "rp_empirical": None,
    }
    raw = target["index_deficit"][0] if target.height else None
    if raw is not None and raw == raw:  # v == v: NaN-Check ohne Import
        value = float(raw)
        row["value"] = value
        row["rp_empirical"] = empirical_weibull_rp(values, value)
        if "error" not in fit_bounded:
            shift = return_period_shift(fit_bounded, n_years=n_years, value=value)
            row["rp_start"] = shift.get("rp_start")
            row["rp_end"] = shift.get("rp_end")
        if "error" not in fit_free:
            shift_free = return_period_shift(fit_free, n_years=n_years, value=value)
            row["rp_start_free"] = shift_free.get("rp_start")
            row["rp_end_free"] = shift_free.get("rp_end")
    return pl.DataFrame([row])


def run(args: argparse.Namespace) -> int:
    stage_name = f"trend-{args.agg_suffix}" if args.agg_suffix else "trend"
    log = StageLog(stage=stage_name, log_dir=Path(args.log_dir))
    try:
        interim = Path(args.interim_dir)
        agg_dir = interim / (f"aggregate-{args.agg_suffix}" if args.agg_suffix else "aggregate")
        metrics_suffix = getattr(args, "metrics_suffix", "")
        metrics_dir = interim / (f"metrics-{metrics_suffix}" if metrics_suffix else "metrics")

        metrics = pl.read_parquet(metrics_dir / "station_year_metrics.parquet")

        con = connect(Path(args.db))
        stations = con.execute("SELECT station_id, catchment_area FROM stations").pl()
        con.close()

        indices = {
            variant: pl.read_parquet(agg_dir / f"national_index_{variant}.parquet")
            for variant in VARIANTS
        }

        station_trends = _station_trends(metrics)
        log.counts("station_trends", rows_in=metrics["station_id"].n_unique(),
                   rows_out=station_trends.height)
        for label, trend_col, direction in [
            ("days_below steigend", "days_below_trend", "increasing"),
            ("nm7q fallend", "nm7q_trend", "decreasing"),
        ]:
            p_col = trend_col.replace("_trend", "_p")
            hits = station_trends.filter(pl.col(trend_col) == direction)
            n_raw = hits.filter(pl.col(p_col) < ALPHA).height
            n_fdr = hits.filter(pl.col(f"{p_col}_fdr") < ALPHA).height
            log.info(
                f"Multiplizitaet ({label}, alpha={ALPHA}): roh {n_raw}/{station_trends.height} "
                f"signifikant, nach Benjamini-Hochberg-FDR {n_fdr}/{station_trends.height}"
            )

        national_trends = _national_trends(indices)
        log.info(f"national_trends: {national_trends.height} Zeilen (Variante x Metrik, "
                 f"Fenster {WINDOW[0]}-{WINDOW[1]})")

        decades = _decade_stats_all(metrics, stations)
        log.info(f"decade_stats: {decades.height} Zeilen")

        gev = _gev_deficit(indices["primary"])
        gev_row = gev.row(0, named=True)
        if gev_row["error"]:
            log.info(f"GEV-Fit bounded (index_deficit, primary): FEHLER - {gev_row['error']}")
        else:
            log.info(
                f"GEV-Fit bounded (index_deficit, primary): xi={gev_row['xi']:.4f} "
                f"mu1={gev_row['mu1']:.4f} p_value={gev_row['p_value']:.4f} "
                f"rp_start={gev_row['rp_start']} rp_end={gev_row['rp_end']}"
            )
        if gev_row["error_free"]:
            log.info(f"GEV-Fit free (index_deficit, primary): FEHLER - {gev_row['error_free']}")
        else:
            log.info(
                f"GEV-Fit free (index_deficit, primary): xi_free={gev_row['xi_free']:.4f} "
                f"p_value_free={gev_row['p_value_free']:.4f} "
                f"rp_start_free={gev_row['rp_start_free']} rp_end_free={gev_row['rp_end_free']}"
            )
        log.info(
            f"Empirisches Weibull-RP (WY {GEV_TARGET_YEAR}, Wert={gev_row['value']}): "
            f"{gev_row['rp_empirical']}"
        )

        write_stage_parquet(national_trends, interim, stage_name, "national_trends")
        write_stage_parquet(decades, interim, stage_name, "decade_stats")
        write_stage_parquet(gev, interim, stage_name, "gev_deficit")

        if args.agg_suffix:
            log.info("Sensitivitaetslauf: station_trends.csv wird nicht ueberschrieben")
        else:
            out_dir = Path(args.out_dir)
            out_dir.mkdir(parents=True, exist_ok=True)
            station_trends.write_csv(out_dir / "station_trends.csv")

        return 0
    finally:
        log.close()
