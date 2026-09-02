from __future__ import annotations

import argparse
from pathlib import Path

import polars as pl

from niedrigwasser.aggregate import national_index, select_index_stations
from niedrigwasser.store import StageLog, connect, write_stage_parquet
from niedrigwasser.topology import incremental_areas

VARIANTS = [
    ("primary", False, False),
    ("natural", False, True),
    ("allsinks", True, False),
    ("allsinks_natural", True, True),
]


def run(args: argparse.Namespace) -> int:
    stage_name = f"aggregate-{args.out_suffix}" if args.out_suffix else "aggregate"
    log = StageLog(stage=stage_name, log_dir=Path(args.log_dir))
    try:
        con = connect(Path(args.db))
        stations = con.execute(
            "SELECT station_id, catchment_area, downstream_id FROM stations"
        ).pl()
        log.counts("stations", rows_in=stations.height, rows_out=stations.height)

        # a_incremental auf der vollstaendigen Netz-Topologie berechnen (auch
        # Stationen, die das Screening nicht ueberleben, tragen zur
        # inkrementellen Flaeche ihrer Unterlieger bei).
        areas = incremental_areas(stations)
        stations = stations.join(areas, on="station_id", how="left")

        interim = Path(args.interim_dir)
        screen_dir = f"screen-{args.screen_suffix}" if args.screen_suffix else "screen"
        usable_stations = pl.read_parquet(
            interim / screen_dir / "usable_stations.parquet"
        ).select("station_id", "is_near_natural")
        # inner join: nur Screening-Ueberlebende tragen zum Index bei.
        stations_sel = stations.join(usable_stations, on="station_id", how="inner")
        log.counts("screening_join", rows_in=stations.height, rows_out=stations_sel.height)

        sinks = pl.read_csv(args.sinks)

        metrics_dir = f"metrics-{args.metrics_suffix}" if args.metrics_suffix else "metrics"
        metrics = pl.read_parquet(interim / metrics_dir / "station_year_metrics.parquet")

        out_dir = f"aggregate-{args.out_suffix}" if args.out_suffix else "aggregate"

        for variant, include_nested, natural_only in VARIANTS:
            variant_stations = select_index_stations(
                stations_sel, sinks, include_nested=include_nested, natural_only=natural_only,
            )
            idx = national_index(metrics, variant_stations)
            write_stage_parquet(idx, interim, out_dir, f"national_index_{variant}")

            years = (
                f"{idx['water_year'].min()}-{idx['water_year'].max()}"
                if idx.height else "-"
            )
            coverage = (
                f"{idx['coverage_area_km2'].min():.0f}-{idx['coverage_area_km2'].max():.0f}"
                if idx.height else "-"
            )
            log.info(
                f"Variante {variant}: n_stations={variant_stations.height} "
                f"jahre={years} coverage_km2={coverage}"
            )

            if not args.out_suffix and variant == "primary":
                primary_out = idx.select(
                    "water_year", "index_days", "index_deficit", "index_ssi",
                    "n_stations", "coverage_area_km2",
                )
                con.execute("DELETE FROM national_index")
                con.execute("INSERT INTO national_index SELECT * FROM primary_out")

                out_path = Path("out") / "national_index.csv"
                out_path.parent.mkdir(parents=True, exist_ok=True)
                primary_out.write_csv(out_path)

        con.close()
        return 0
    finally:
        log.close()
