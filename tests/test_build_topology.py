import polars as pl
import pytest

from niedrigwasser.build_topology import apply_overrides, build_topology, chain_within_river


def _st(rows):
    return pl.DataFrame(
        rows,
        schema={"station_id": pl.Utf8, "river": pl.Utf8,
                "catchment_area": pl.Float64, "river_km": pl.Float64},
        orient="row",
    )


def _st_geo(rows):
    return pl.DataFrame(
        rows,
        schema={"station_id": pl.Utf8, "river": pl.Utf8,
                "catchment_area": pl.Float64, "lat": pl.Float64, "lon": pl.Float64},
        orient="row",
    )


def test_chain_within_river_orders_by_area():
    df = _st([("m", "Inn", 5000.0, 100.0), ("o", "Inn", 1000.0, 300.0),
              ("x", "Isar", 500.0, 50.0)])
    out = chain_within_river(df)
    d = dict(zip(out["station_id"].to_list(), out["downstream_id"].to_list()))
    assert d == {"o": "m", "m": None, "x": None}


def test_chain_normalizes_river_names():
    df = _st([("a", " Inn", 100.0, 1.0), ("b", "inn ", 200.0, 2.0)])
    out = chain_within_river(df)
    d = dict(zip(out["station_id"].to_list(), out["downstream_id"].to_list()))
    assert d == {"a": "b", "b": None}


def test_apply_overrides_connects_mouth():
    df = _st([("inn_m", "Inn", 26000.0, 0.0), ("don_1", "Donau", 50000.0, 2200.0)])
    chained = chain_within_river(df)
    ov = pl.DataFrame({"station_id": ["inn_m"], "downstream_id": ["don_1"],
                       "note": ["Inn muendet in Donau"]})
    out = apply_overrides(chained, ov)
    d = dict(zip(out["station_id"].to_list(), out["downstream_id"].to_list()))
    assert d["inn_m"] == "don_1"


def test_apply_overrides_unknown_id_raises():
    df = _st([("a", "Inn", 100.0, 1.0)])
    ov = pl.DataFrame({"station_id": ["ghost"], "downstream_id": [None], "note": ["x"]})
    with pytest.raises(ValueError):
        apply_overrides(chain_within_river(df), ov)


def test_chain_within_river_breaks_edge_on_name_collision():
    # Zwei physisch unterschiedliche Fluesse namens "Schwarzbach", weit auseinander
    # (Saarland vs. Baden-Wuerttemberg, > 150 km Luftlinie) -> keine automatische Kante.
    df = _st_geo([
        ("sl", "Schwarzbach", 1152.0, 49.26, 7.32),   # Einoed, Saarland
        ("by", "Schwarzbach", 45.0, 48.14, 11.58),     # synthetisch weit entfernt (Muenchen-Raum)
    ])
    out = chain_within_river(df)
    d = dict(zip(out["station_id"].to_list(), out["downstream_id"].to_list()))
    assert d == {"sl": None, "by": None}


def test_chain_within_river_connects_close_same_river_stations():
    # Gleicher Fluss, plausible Distanz (< 150 km) -> normale Kette.
    df = _st_geo([
        ("m", "Inn", 5000.0, 48.06, 12.23),
        ("o", "Inn", 1000.0, 47.86, 12.11),
    ])
    out = chain_within_river(df)
    d = dict(zip(out["station_id"].to_list(), out["downstream_id"].to_list()))
    assert d == {"o": "m", "m": None}


def test_chain_within_river_missing_coord_breaks_edge():
    # Ein Stationspaar mit fehlender Koordinate (lat/lon None) darf ohne
    # funktionierenden Distanz-Guard keine automatische Kante bekommen.
    df = _st_geo([
        ("m", "Inn", 5000.0, 48.06, 12.23),
        ("o", "Inn", 1000.0, None, None),
    ])
    out = chain_within_river(df)
    d = dict(zip(out["station_id"].to_list(), out["downstream_id"].to_list()))
    assert d == {"o": None, "m": None}


def test_chain_within_river_null_river_not_chained():
    df = _st_geo([
        ("a", None, 100.0, 50.0, 10.0),
        ("b", None, 200.0, 50.1, 10.1),
    ])
    out = chain_within_river(df)
    assert out["downstream_id"].to_list() == [None, None]


def test_build_topology_validates():
    # Donau-Pegel kleiner als Inn-Muendung -> negative A_inc -> TopologyError
    from niedrigwasser.topology import TopologyError
    df = _st([("inn_m", "Inn", 26000.0, 0.0), ("don_1", "Donau", 20000.0, 2200.0)])
    ov = pl.DataFrame({"station_id": ["inn_m"], "downstream_id": ["don_1"], "note": ["x"]})
    with pytest.raises(TopologyError):
        build_topology(df, ov)
