from __future__ import annotations

import polars as pl

from niedrigwasser.water_year import water_year_expr


def compute_thresholds(
    daily: pl.DataFrame, ref_start: int = 1992, ref_end: int = 2011
) -> pl.DataFrame:
    ref = (
        daily.with_columns(water_year_expr("date").alias("water_year"))
        .filter(
            pl.col("water_year").is_between(ref_start, ref_end)
            & pl.col("q").is_not_null()
        )
    )
    q95 = ref.group_by("station_id").agg(
        pl.col("q").quantile(0.05, interpolation="linear").alias("q95")
    )
    mnq = (
        ref.group_by("station_id", "water_year")
        .agg(pl.col("q").min().alias("nq"))
        .group_by("station_id")
        .agg(pl.col("nq").mean().alias("mnq"))
    )
    return (
        q95.join(mnq, on="station_id")
        .with_columns(
            pl.lit(ref_start).alias("ref_period_start"),
            pl.lit(ref_end).alias("ref_period_end"),
        )
        .sort("station_id")
    )
