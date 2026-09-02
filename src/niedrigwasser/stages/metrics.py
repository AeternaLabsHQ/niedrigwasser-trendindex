from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from niedrigwasser.metrics import station_year_metrics
from niedrigwasser.ssi import compute_ssi
from niedrigwasser.store import StageLog, connect, write_stage_parquet
from niedrigwasser.thresholds import compute_thresholds


def run(args: argparse.Namespace) -> int:
    stage_name = f"metrics-{args.out_suffix}" if args.out_suffix else "metrics"
    log = StageLog(stage=stage_name, log_dir=Path(args.log_dir))
    try:
        con = connect(Path(args.db))
        daily = con.execute(
            "SELECT station_id, date, q FROM discharge_daily"
        ).pl()
        log.counts("discharge_daily", rows_in=daily.height, rows_out=daily.height)

        thresholds = compute_thresholds(daily, args.ref_start, args.ref_end)
        log.info(f"Stationen mit Threshold: {thresholds.height}")

        metrics = station_year_metrics(daily, thresholds, inter_event=args.inter_event)
        ssi = compute_ssi(daily, args.ref_start, args.ref_end)
        metrics = metrics.join(
            ssi.select("station_id", "water_year", "ssi"),
            on=["station_id", "water_year"], how="left",
        )

        usable = pl.read_parquet(
            Path(args.interim_dir) / "screen" / "usable_station_years.parquet"
        ).select("station_id", "water_year", "data_completeness")
        joined = metrics.join(usable, on=["station_id", "water_year"], how="inner").select(
            "station_id", "water_year", "days_below", "max_spell",
            "deficit_volume_m3", "nm7q", "ssi", "data_completeness",
        ).sort("station_id", "water_year")
        log.counts("screening_join", rows_in=metrics.height, rows_out=joined.height)

        usable_stations = pl.read_parquet(
            Path(args.interim_dir) / "screen" / "usable_stations.parquet"
        ).select("station_id")
        out = joined.join(usable_stations, on="station_id", how="inner")
        log.counts("station_filter_25y", rows_in=joined.height, rows_out=out.height)

        interim = Path(args.interim_dir)
        write_stage_parquet(thresholds, interim, stage_name, "station_thresholds")
        write_stage_parquet(out, interim, stage_name, "station_year_metrics")

        if args.out_suffix:
            log.info("Sensitivitaetslauf: DuckDB-Load uebersprungen")
        else:
            con.execute("DELETE FROM station_thresholds")
            con.execute("INSERT INTO station_thresholds SELECT * FROM thresholds")
            con.execute("DELETE FROM station_year_metrics")
            con.execute("INSERT INTO station_year_metrics SELECT * FROM out")
        con.close()
        return 0
    finally:
        log.close()
