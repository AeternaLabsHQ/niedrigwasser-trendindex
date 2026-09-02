from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from niedrigwasser.flags import apply_flags, load_station_flags
from niedrigwasser.screening import (
    station_year_completeness,
    usable_station_years,
    usable_stations,
)
from niedrigwasser.store import StageLog, connect, write_stage_parquet


def run(args: argparse.Namespace) -> int:
    stage_name = f"screen-{args.out_suffix}" if args.out_suffix else "screen"
    # kommaseparierte Liste -> Menge; leer/None = Default-Ausschlussflags.
    excluding = (
        {f.strip() for f in args.exclude_flags.split(",") if f.strip()}
        if args.exclude_flags else None
    )
    log = StageLog(stage=stage_name, log_dir=Path(args.log_dir))
    try:
        con = connect(Path(args.db))
        discharge = con.execute("SELECT * FROM discharge_daily").pl()
        stations = con.execute("SELECT * FROM stations").pl()
        con.close()

        comp = station_year_completeness(discharge)
        usable_years = usable_station_years(comp)
        log.counts("station_years", rows_in=comp.height, rows_out=usable_years.height)

        st_usable = usable_stations(usable_years)
        log.counts("usable_stations", rows_in=stations.height, rows_out=st_usable.height)

        flags = load_station_flags(Path(args.flags))
        st_out = apply_flags(
            stations.join(st_usable, on="station_id", how="inner"), flags, excluding,
        )
        n_flagged = st_out.filter(pl.col("flags").list.len() > 0).height
        n_natural = st_out.filter(pl.col("is_near_natural")).height
        log.info(f"geflaggt={n_flagged} naturnah={n_natural}")

        interim = Path(args.interim_dir)
        write_stage_parquet(comp, interim, stage_name, "completeness")
        write_stage_parquet(usable_years, interim, stage_name, "usable_station_years")
        write_stage_parquet(st_out, interim, stage_name, "usable_stations")
        if args.out_suffix:
            log.info(f"Sensitivitaetslauf: Outputs nach interim/{stage_name}/")
        return 0
    finally:
        log.close()
