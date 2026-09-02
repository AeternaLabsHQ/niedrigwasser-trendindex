from __future__ import annotations

import polars as pl


class TopologyError(ValueError):
    def __init__(self, msg: str, offenders: list[str] | None = None):
        super().__init__(msg)
        self.offenders = offenders or []


def validate_topology(stations: pl.DataFrame) -> None:
    ids = stations["station_id"].to_list()
    if len(ids) != len(set(ids)):
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        raise TopologyError(f"Doppelte station_id: {dupes}", dupes)

    known = set(ids)
    down = dict(zip(ids, stations["downstream_id"].to_list()))
    ghosts = sorted({d for d in down.values() if d is not None and d not in known})
    if ghosts:
        raise TopologyError(f"downstream_id zeigt auf unbekannte Stationen: {ghosts}", ghosts)

    # Zyklenerkennung: jedem Pfad flussabwaerts folgen
    for start in ids:
        seen: set[str] = set()
        node: str | None = start
        while node is not None:
            if node in seen:
                raise TopologyError(f"Zyklus im Stationsgraph ab '{start}'", [start])
            seen.add(node)
            node = down[node]


def incremental_areas(stations: pl.DataFrame) -> pl.DataFrame:
    validate_topology(stations)
    upstream_sum = (
        stations.drop_nulls("downstream_id")
        .group_by("downstream_id")
        .agg(pl.col("catchment_area").sum().alias("upstream_area"))
        .rename({"downstream_id": "station_id"})
    )
    out = (
        stations.join(upstream_sum, on="station_id", how="left")
        .with_columns(pl.col("upstream_area").fill_null(0.0))
        .with_columns((pl.col("catchment_area") - pl.col("upstream_area")).alias("a_incremental"))
        .select("station_id", "a_incremental")
    )
    neg = out.filter(pl.col("a_incremental") < 0)
    if neg.height > 0:
        offenders = neg["station_id"].to_list()
        raise TopologyError(
            f"Negative inkrementelle Flaeche (Topologiefehler) bei: {offenders}", offenders
        )
    return out
