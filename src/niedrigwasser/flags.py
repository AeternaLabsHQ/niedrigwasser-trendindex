from __future__ import annotations

from pathlib import Path

import polars as pl

VALID_FLAGS = {"reservoir", "transfer", "mining", "erosion"}
# Flags, die eine Station aus dem naturnahen Subset ausschliessen.
# 'erosion' ist nur ein Hinweis (relevant fuer W, nicht Q) und schliesst nicht aus.
EXCLUDING_FLAGS = {"reservoir", "transfer", "mining"}


def load_station_flags(path: Path) -> pl.DataFrame:
    df = pl.read_csv(path, schema={"station_id": pl.Utf8, "flag": pl.Utf8, "note": pl.Utf8})
    unknown = df.filter(~pl.col("flag").is_in(list(VALID_FLAGS)))
    if unknown.height > 0:
        raise ValueError(f"Unbekannte Flags: {unknown['flag'].unique().to_list()}")
    return df


def apply_flags(
    stations: pl.DataFrame, flags: pl.DataFrame, excluding: set[str] | None = None,
) -> pl.DataFrame:
    """Ergaenzt 'stations' um 'flags' und 'is_near_natural'.

    'excluding' bestimmt, welche Flags eine Station aus dem naturnahen Subset
    ausschliessen; None nutzt EXCLUDING_FLAGS (Default-Verhalten).
    """
    excluding = EXCLUDING_FLAGS if excluding is None else excluding
    unknown = set(excluding) - VALID_FLAGS
    if unknown:
        raise ValueError(f"Unbekannte Flags: {sorted(unknown)}")

    per_station = flags.group_by("station_id").agg(
        pl.col("flag").alias("flags"),
        pl.col("flag").is_in(list(excluding)).any().alias("_excluded"),
    )
    return (
        stations.join(per_station, on="station_id", how="left")
        .with_columns(
            pl.col("flags").fill_null(pl.lit([], dtype=pl.List(pl.Utf8))),
            (~pl.col("_excluded").fill_null(False)).alias("is_near_natural"),
        )
        .drop("_excluded")
    )
