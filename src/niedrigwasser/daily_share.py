from __future__ import annotations

import polars as pl

from niedrigwasser.water_year import water_year_expr


def daily_below_share(
    discharge: pl.DataFrame,
    thresholds: pl.DataFrame,
    weights: pl.DataFrame,
    usable_years: pl.DataFrame,
) -> pl.DataFrame:
    """Tagesgenauer flaechengewichteter Unterschreitungsanteil ueber alle Stationen.

    share(t) = Sum(w_i * 1(q_i < q95_i)) / Sum(w_i)
    ueber Stationen mit non-null q am Tag t, beschraenkt auf (station, water_year)
    aus usable_years. Schalttag (doy 366) wird auf doy 365 gemappt (max ueber
    share und n_stations).
    """
    df = (
        discharge.filter(pl.col("q").is_not_null())
        .join(thresholds.select("station_id", "q95"), on="station_id", how="inner")
        .join(weights.select("station_id", "a_incremental"), on="station_id", how="inner")
        .with_columns(water_year_expr("date").alias("water_year"))
        .join(
            usable_years.select("station_id", "water_year"),
            on=["station_id", "water_year"],
            how="semi",
        )
        .with_columns(
            (
                pl.col("date") - pl.date(pl.col("water_year") - 1, 11, 1)
            ).dt.total_days().cast(pl.Int64).alias("doy")
            + 1,
            (pl.col("q") < pl.col("q95")).alias("below"),
        )
    )

    daily = df.group_by("water_year", "doy").agg(
        (
            (pl.col("a_incremental") * pl.col("below").cast(pl.Float64)).sum()
            / pl.col("a_incremental").sum()
        ).alias("share"),
        pl.len().alias("n_stations"),
    )

    return (
        daily.with_columns(pl.min_horizontal(pl.col("doy"), 365).alias("doy"))
        .group_by("water_year", "doy")
        .agg(
            pl.col("share").max().alias("share"),
            pl.col("n_stations").max().alias("n_stations"),
        )
        .sort("water_year", "doy")
    )
