from __future__ import annotations

import polars as pl

from niedrigwasser.water_year import water_year_expr

SUMMER_MONTHS = (5, 6, 7, 8, 9, 10)
SUMMER_DAYS = 184  # Mai-Okt: 31+30+31+31+30+31, kein Schaltjahreseinfluss


def station_year_completeness(discharge: pl.DataFrame) -> pl.DataFrame:
    df = discharge.with_columns(water_year_expr("date").alias("water_year"))
    is_summer = pl.col("date").dt.month().is_in(list(SUMMER_MONTHS))
    has_q = pl.col("q").is_not_null()
    year_len = (
        pl.when((pl.col("water_year") % 4 == 0) &
                ((pl.col("water_year") % 100 != 0) | (pl.col("water_year") % 400 == 0)))
        .then(366).otherwise(365)
    )
    return (
        df.group_by("station_id", "water_year")
        .agg(
            (is_summer & has_q).sum().alias("summer_days_present"),
            has_q.sum().alias("total_days_present"),
        )
        .with_columns(
            (pl.col("summer_days_present") / SUMMER_DAYS).alias("summer_coverage"),
            (pl.col("total_days_present") / year_len).alias("data_completeness"),
        )
        .sort("station_id", "water_year")
    )


def usable_station_years(
    completeness: pl.DataFrame, min_summer_coverage: float = 0.95
) -> pl.DataFrame:
    return completeness.filter(pl.col("summer_coverage") >= min_summer_coverage)


def usable_stations(usable_years: pl.DataFrame, min_years: int = 25) -> pl.DataFrame:
    return (
        usable_years.group_by("station_id")
        .agg(pl.len().alias("n_usable_years"))
        .filter(pl.col("n_usable_years") >= min_years)
        .sort("station_id")
    )
