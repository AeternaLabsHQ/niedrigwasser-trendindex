from datetime import date

import polars as pl

from niedrigwasser.daily_share import daily_below_share


def _discharge(rows):
    return pl.DataFrame(
        rows,
        schema={"station_id": pl.Utf8, "date": pl.Date, "q": pl.Float64},
        orient="row",
    )


def _thresholds(rows):
    return pl.DataFrame(
        rows, schema={"station_id": pl.Utf8, "q95": pl.Float64}, orient="row"
    )


def _weights(rows):
    return pl.DataFrame(
        rows, schema={"station_id": pl.Utf8, "a_incremental": pl.Float64}, orient="row"
    )


def _usable_years(rows):
    return pl.DataFrame(
        rows, schema={"station_id": pl.Utf8, "water_year": pl.Int64}, orient="row"
    )


def test_weighted_share_two_stations():
    # A (Gewicht 2) unter Schwelle, B (Gewicht 1) darueber -> share = 2/3
    discharge = _discharge(
        [("A", date(2024, 11, 1), 3.0), ("B", date(2024, 11, 1), 10.0)]
    )
    thresholds = _thresholds([("A", 5.0), ("B", 5.0)])
    weights = _weights([("A", 2.0), ("B", 1.0)])
    usable = _usable_years([("A", 2025), ("B", 2025)])

    out = daily_below_share(discharge, thresholds, weights, usable)

    assert out.height == 1
    row = out.row(0, named=True)
    assert row["water_year"] == 2025
    assert row["doy"] == 1
    assert abs(row["share"] - 2 / 3) < 1e-9
    assert row["n_stations"] == 2


def test_missing_station_on_day_renormalizes():
    # Tag 1: A + B; Tag 2: nur A (B fehlt komplett) -> Renormierung nur auf A
    discharge = _discharge(
        [
            ("A", date(2024, 11, 1), 3.0),   # below
            ("B", date(2024, 11, 1), 10.0),  # above
            ("A", date(2024, 11, 2), 3.0),   # below, B fehlt an diesem Tag
        ]
    )
    thresholds = _thresholds([("A", 5.0), ("B", 5.0)])
    weights = _weights([("A", 2.0), ("B", 1.0)])
    usable = _usable_years([("A", 2025), ("B", 2025)])

    out = daily_below_share(discharge, thresholds, weights, usable).sort("doy")

    assert out.height == 2
    day1 = out.row(0, named=True)
    day2 = out.row(1, named=True)
    assert abs(day1["share"] - 2 / 3) < 1e-9
    assert day1["n_stations"] == 2
    assert day2["share"] == 1.0  # nur A traegt bei, renormiert auf 1
    assert day2["n_stations"] == 1


def test_station_year_not_usable_excluded():
    # C hat Daten, ist aber fuer dieses Wasserjahr nicht in usable_years
    discharge = _discharge(
        [
            ("A", date(2024, 11, 1), 3.0),   # below
            ("C", date(2024, 11, 1), 100.0),  # above, sollte nicht zaehlen
        ]
    )
    thresholds = _thresholds([("A", 5.0), ("C", 5.0)])
    weights = _weights([("A", 2.0), ("C", 1.0)])
    usable = _usable_years([("A", 2025)])  # C fehlt

    out = daily_below_share(discharge, thresholds, weights, usable)

    assert out.height == 1
    row = out.row(0, named=True)
    assert row["share"] == 1.0
    assert row["n_stations"] == 1


def test_leap_day_mapped_to_365_via_max():
    # Wasserjahr 2024 (Nov 2023 - Okt 2024) enthaelt den 29.02.2024 -> 366 Tage
    # doy 365 = 30.10.2024, doy 366 = 31.10.2024
    discharge = _discharge(
        [
            ("A", date(2024, 10, 30), 3.0),   # below, nur A -> share 1.0, n=1
            ("A", date(2024, 10, 31), 10.0),  # above
            ("B", date(2024, 10, 31), 10.0),  # above -> share 0.0, n=2
        ]
    )
    thresholds = _thresholds([("A", 5.0), ("B", 5.0)])
    weights = _weights([("A", 1.0), ("B", 1.0)])
    usable = _usable_years([("A", 2024), ("B", 2024)])

    out = daily_below_share(discharge, thresholds, weights, usable)

    assert out.height == 1
    row = out.row(0, named=True)
    assert row["water_year"] == 2024
    assert row["doy"] == 365
    assert row["share"] == 1.0  # max(1.0, 0.0)
    assert row["n_stations"] == 2  # max(1, 2)


def test_day_without_any_station_missing_from_output():
    discharge = _discharge(
        [
            ("A", date(2024, 11, 1), 3.0),
            ("A", date(2024, 11, 3), 3.0),  # 2. Nov fehlt komplett
        ]
    )
    thresholds = _thresholds([("A", 5.0)])
    weights = _weights([("A", 1.0)])
    usable = _usable_years([("A", 2025)])

    out = daily_below_share(discharge, thresholds, weights, usable).sort("doy")

    assert out["doy"].to_list() == [1, 3]
