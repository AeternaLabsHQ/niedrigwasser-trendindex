from __future__ import annotations

import polars as pl

from niedrigwasser.pooling import pooled_spells
from niedrigwasser.water_year import water_year_expr


def _year_grid(df: pl.DataFrame) -> pl.DataFrame:
    """Volles Kalenderraster je (station_id, water_year); fehlende Tage -> q null."""
    spans = (
        df.select("station_id", "water_year")
        .unique()
        .with_columns(
            pl.date(pl.col("water_year") - 1, 11, 1).alias("_start"),
            pl.date(pl.col("water_year"), 10, 31).alias("_end"),
        )
        .select(
            "station_id", "water_year",
            pl.date_ranges(pl.col("_start"), pl.col("_end")).alias("date"),
        )
        .explode("date")
    )
    return spans.join(df, on=["station_id", "water_year", "date"], how="left")


def station_year_metrics(
    daily: pl.DataFrame, thresholds: pl.DataFrame, inter_event: int = 5
) -> pl.DataFrame:
    df = (
        daily.with_columns(water_year_expr("date").alias("water_year"))
        .join(thresholds.select("station_id"), on="station_id", how="semi")
    )
    grid = _year_grid(df.select("station_id", "water_year", "date", "q")).join(
        thresholds.select("station_id", "q95"), on="station_id", how="left"
    ).sort("station_id", "water_year", "date")

    below = (pl.col("q").is_not_null() & (pl.col("q") < pl.col("q95"))).alias("below")
    grid = grid.with_columns(
        below,
        pl.col("q")
        .rolling_mean_by("date", window_size="7d", min_samples=7)
        .over("station_id", "water_year")
        .alias("_nm7q_daily"),
    )

    base = grid.group_by("station_id", "water_year").agg(
        pl.col("below").sum().alias("days_below"),
        (
            pl.when(pl.col("below"))
            .then((pl.col("q95") - pl.col("q")) * 86400.0)
            .otherwise(0.0)
        ).sum().alias("deficit_volume_m3"),
        pl.col("_nm7q_daily").min().alias("nm7q"),
        pl.col("below").alias("_below_series"),
    )

    def _max_spell(series: pl.Series) -> int:
        spells = pooled_spells(series.to_list(), inter_event=inter_event)
        return max((length for _, length in spells), default=0)

    return (
        base.with_columns(
            pl.col("_below_series")
            .map_elements(_max_spell, return_dtype=pl.Int64)
            .alias("max_spell")
        )
        .drop("_below_series")
        .sort("station_id", "water_year")
    )
