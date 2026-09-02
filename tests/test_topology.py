import polars as pl
import pytest

from niedrigwasser.topology import TopologyError, incremental_areas, validate_topology


def _stations(rows):
    return pl.DataFrame(
        rows, schema={"station_id": pl.Utf8, "catchment_area": pl.Float64,
                      "downstream_id": pl.Utf8}, orient="row",
    )


def test_incremental_chain():
    # Quelle -> Mitte -> Muendung, wie Rhein-Pegelkette
    df = _stations([("up", 100.0, "mid"), ("mid", 250.0, "down"), ("down", 400.0, None)])
    out = incremental_areas(df).sort("station_id")
    got = dict(zip(out["station_id"].to_list(), out["a_incremental"].to_list()))
    assert got == {"up": 100.0, "mid": 150.0, "down": 150.0}
    # Summe = tatsaechlich abgedeckte Flaeche = groesstes Einzugsgebiet
    assert sum(got.values()) == 400.0


def test_incremental_confluence():
    # Zwei Zufluesse muenden in denselben Unterlieger
    df = _stations([("a", 100.0, "c"), ("b", 80.0, "c"), ("c", 300.0, None)])
    out = incremental_areas(df)
    got = dict(zip(out["station_id"].to_list(), out["a_incremental"].to_list()))
    assert got["c"] == 120.0


def test_negative_incremental_raises():
    # Unterlieger kleiner als Summe der Oberlieger -> Topologiefehler
    df = _stations([("a", 100.0, "c"), ("b", 80.0, "c"), ("c", 150.0, None)])
    with pytest.raises(TopologyError) as exc:
        incremental_areas(df)
    assert "c" in exc.value.offenders


def test_unknown_downstream_raises():
    df = _stations([("a", 100.0, "ghost")])
    with pytest.raises(TopologyError):
        validate_topology(df)


def test_cycle_raises():
    df = _stations([("a", 100.0, "b"), ("b", 120.0, "a")])
    with pytest.raises(TopologyError):
        validate_topology(df)


def test_duplicate_station_raises():
    df = _stations([("a", 100.0, None), ("a", 100.0, None)])
    with pytest.raises(TopologyError):
        validate_topology(df)
