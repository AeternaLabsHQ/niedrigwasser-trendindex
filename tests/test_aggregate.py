import polars as pl

from niedrigwasser.aggregate import _weighted, national_index, select_index_stations

STATIONS = pl.DataFrame({
    "station_id": ["A", "B", "C"],
    "catchment_area": [1000.0, 500.0, 200.0],
    "a_incremental": [600.0, 300.0, 100.0],
    "is_near_natural": [True, False, True],
})
SINKS = pl.DataFrame({"station_id": ["C"], "category": ["nested"],
                      "note": ["Testfall"]})


def _metrics(rows):
    return pl.DataFrame(
        rows,
        schema={"station_id": pl.Utf8, "water_year": pl.Int64,
                "days_below": pl.Int64, "deficit_volume_m3": pl.Float64,
                "ssi": pl.Float64},
        orient="row",
    )


def test_select_excludes_nested_and_natural():
    sel = select_index_stations(STATIONS, SINKS, include_nested=False, natural_only=False)
    assert sel["station_id"].to_list() == ["A", "B"]
    sel_nat = select_index_stations(STATIONS, SINKS, include_nested=False, natural_only=True)
    assert sel_nat["station_id"].to_list() == ["A"]
    sel_all = select_index_stations(STATIONS, SINKS, include_nested=True, natural_only=False)
    assert sel_all["station_id"].to_list() == ["A", "B", "C"]


def test_national_index_weighted_mean():
    sel = select_index_stations(STATIONS, SINKS, include_nested=False, natural_only=False)
    m = _metrics([("A", 2000, 10, 0.0, 1.0), ("B", 2000, 40, 0.0, -1.0)])
    out = national_index(m, sel)
    row = out.row(0, named=True)
    # Gewichte 600/900 und 300/900
    assert abs(row["index_days"] - (10 * 2 / 3 + 40 * 1 / 3)) < 1e-9
    assert abs(row["index_ssi"] - (1.0 * 2 / 3 - 1.0 * 1 / 3)) < 1e-9
    assert row["n_stations"] == 2
    assert row["coverage_area_km2"] == 900.0


def test_renormalization_on_missing_station_year():
    sel = select_index_stations(STATIONS, SINKS, include_nested=False, natural_only=False)
    m = _metrics([("A", 2000, 10, 0.0, 1.0), ("B", 2000, 40, 0.0, -1.0),
                  ("A", 2001, 20, 0.0, 0.5)])  # B fehlt 2001
    out = national_index(m, sel).sort("water_year")
    r2001 = out.row(1, named=True)
    assert r2001["index_days"] == 20.0        # nur A, Gewicht renormiert auf 1
    assert r2001["n_stations"] == 1
    assert r2001["coverage_area_km2"] == 600.0


def test_deficit_normalized_to_mm():
    sel = select_index_stations(STATIONS, SINKS, include_nested=False, natural_only=False)
    # A: 1000 km² EZG, Defizitvolumen 1e9 m³ -> 1e9 / 1e9 m Wassersaeule = 1000 mm
    m = _metrics([("A", 2000, 0, 1.0e9, 0.0)])
    out = national_index(m, sel)
    assert abs(out.row(0, named=True)["index_deficit"] - 1000.0) < 1e-9


def test_ssi_null_renormalized_separately():
    sel = select_index_stations(STATIONS, SINKS, include_nested=False, natural_only=False)
    m = pl.DataFrame({"station_id": ["A", "B"], "water_year": [2000, 2000],
                      "days_below": [10, 40], "deficit_volume_m3": [0.0, 0.0],
                      "ssi": [2.0, None]})
    out = national_index(m, sel)
    row = out.row(0, named=True)
    assert row["index_ssi"] == 2.0           # nur A traegt ssi
    assert abs(row["index_days"] - (10 * 2 / 3 + 40 * 1 / 3)) < 1e-9  # days weiter beide


def test_weighted_all_null_liefert_null():
    df = pl.DataFrame(
        {"water_year": [2000, 2000], "ssi": [None, None], "a_incremental": [10.0, 20.0]},
        schema_overrides={"ssi": pl.Float64},
    )
    out = df.group_by("water_year").agg(_weighted("ssi", "a_incremental").alias("v"))
    assert out["v"][0] is None  # bisher: NaN


def test_national_index_all_null_ssi_liefert_null():
    sel = select_index_stations(STATIONS, SINKS, include_nested=False, natural_only=False)
    m = pl.DataFrame({"station_id": ["A", "B"], "water_year": [2000, 2000],
                      "days_below": [10, 40], "deficit_volume_m3": [0.0, 0.0],
                      "ssi": [None, None]}, schema_overrides={"ssi": pl.Float64})
    out = national_index(m, sel)
    row = out.row(0, named=True)
    assert row["index_ssi"] is None          # kein NaN in den Index-Parquets
    assert abs(row["index_days"] - (10 * 2 / 3 + 40 * 1 / 3)) < 1e-9  # days unberuehrt
