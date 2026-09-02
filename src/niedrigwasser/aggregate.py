from __future__ import annotations

import polars as pl


def select_index_stations(
    stations: pl.DataFrame, sinks: pl.DataFrame,
    include_nested: bool, natural_only: bool,
) -> pl.DataFrame:
    nested_ids = sinks.filter(pl.col("category") == "nested")["station_id"].implode()
    out = stations
    if not include_nested:
        out = out.filter(~pl.col("station_id").is_in(nested_ids))
    if natural_only:
        out = out.filter(pl.col("is_near_natural"))
    return out


def _weighted(col: str, weight: str) -> pl.Expr:
    # Gewichtetes Mittel; wenn alle Werte null sind, null statt 0/0=NaN liefern.
    w = pl.col(weight).filter(pl.col(col).is_not_null())
    return (
        pl.when(w.sum() > 0)
        .then((pl.col(col) * pl.col(weight)).sum() / w.sum())
        .otherwise(None)
    )


def national_index(metrics: pl.DataFrame, stations_sel: pl.DataFrame) -> pl.DataFrame:
    df = metrics.join(
        stations_sel.select("station_id", "catchment_area", "a_incremental"),
        on="station_id", how="inner",
    ).with_columns(
        (pl.col("deficit_volume_m3") / (pl.col("catchment_area") * 1e6) * 1000.0)
        .alias("deficit_mm")
    )
    return (
        df.group_by("water_year")
        .agg(
            _weighted("days_below", "a_incremental").alias("index_days"),
            _weighted("deficit_mm", "a_incremental").alias("index_deficit"),
            _weighted("ssi", "a_incremental").alias("index_ssi"),
            pl.len().alias("n_stations"),
            pl.col("a_incremental").sum().alias("coverage_area_km2"),
        )
        .sort("water_year")
    )
