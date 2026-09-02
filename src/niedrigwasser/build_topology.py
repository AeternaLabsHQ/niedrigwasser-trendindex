from __future__ import annotations

import math

import polars as pl

from niedrigwasser.topology import incremental_areas, validate_topology

_EARTH_RADIUS_KM = 6371.0088
# Zwei aufeinanderfolgende Stationen desselben (normalisierten) Flussnamens,
# die > 150 km Luftlinie auseinanderliegen, sind vermutlich keine echte
# Fluss-Fortsetzung, sondern eine Namenskollision zweier unterschiedlicher
# physischer Gewaesser (z. B. mehrere "Schwarzbach"/"Kinzig"/"Nahe" in
# Deutschland) — dann wird keine Kante gesetzt.
_MAX_CHAIN_DISTANCE_KM = 150.0


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * _EARTH_RADIUS_KM * math.asin(min(1.0, math.sqrt(a)))


def chain_within_river(stations: pl.DataFrame) -> pl.DataFrame:
    # EZG waechst flussabwaerts monoton — robuster als river_km,
    # dessen Zaehlrichtung je Bundesland variiert.
    has_coords = "lat" in stations.columns and "lon" in stations.columns
    df = stations.with_columns(
        pl.col("river").str.strip_chars().str.to_lowercase().alias("_river_norm")
    ).sort("_river_norm", "catchment_area")

    ids = df["station_id"].to_list()
    rivers = df["_river_norm"].to_list()
    lats = df["lat"].to_list() if has_coords else [None] * len(ids)
    lons = df["lon"].to_list() if has_coords else [None] * len(ids)

    downstream: list[str | None] = [None] * len(ids)
    for i in range(len(ids) - 1):
        # river=null -> keine Verkettung (kein sinnvoller Gruppenschluessel)
        if rivers[i] is None or rivers[i] != rivers[i + 1]:
            continue
        if has_coords:
            if None in (lats[i], lons[i], lats[i + 1], lons[i + 1]):
                continue  # fehlende Koordinaten -> kein Distanz-Guard moeglich, konservativ keine Kante
            dist = _haversine_km(lats[i], lons[i], lats[i + 1], lons[i + 1])
            if dist >= _MAX_CHAIN_DISTANCE_KM:
                continue  # vermutlich Flussnamens-Kollision, keine Kante
        downstream[i] = ids[i + 1]

    return df.with_columns(pl.Series("downstream_id", downstream, dtype=pl.Utf8)).drop(
        "_river_norm"
    )


def apply_overrides(stations: pl.DataFrame, overrides: pl.DataFrame) -> pl.DataFrame:
    known = set(stations["station_id"].to_list())
    bad = [
        s for s in overrides["station_id"].to_list() +
        [d for d in overrides["downstream_id"].to_list() if d is not None]
        if s not in known
    ]
    if bad:
        raise ValueError(f"Overrides referenzieren unbekannte Stationen: {sorted(set(bad))}")
    ov = overrides.select(
        "station_id", pl.col("downstream_id").alias("_ov_downstream")
    ).with_columns(pl.lit(True).alias("_has_ov"))
    return (
        stations.join(ov, on="station_id", how="left")
        .with_columns(
            pl.when(pl.col("_has_ov").fill_null(False))
            .then(pl.col("_ov_downstream"))
            .otherwise(pl.col("downstream_id"))
            .alias("downstream_id")
        )
        .drop("_ov_downstream", "_has_ov")
    )


def build_topology(stations: pl.DataFrame, overrides: pl.DataFrame) -> pl.DataFrame:
    out = apply_overrides(chain_within_river(stations), overrides)
    validate_topology(out)
    incremental_areas(out)  # wirft TopologyError bei negativer Flaeche
    return out
