from datetime import date, timedelta

import polars as pl

from niedrigwasser.thresholds import compute_thresholds


def _year(station: str, wy: int, values):
    start = date(wy - 1, 11, 1)
    days = [start + timedelta(days=i) for i in range(len(values))]
    return pl.DataFrame({"station_id": [station] * len(values), "date": days,
                         "q": values}).with_columns(pl.col("date").cast(pl.Date))


def test_q95_is_5th_percentile():
    # WY 2000: Werte 1..365 -> 5. Perzentil (linear) = 1 + 0.05*364 = 19.2
    df = _year("A", 2000, [float(i) for i in range(1, 366)])
    out = compute_thresholds(df, ref_start=2000, ref_end=2000)
    row = out.row(0, named=True)
    assert abs(row["q95"] - 19.2) < 1e-9
    assert row["mnq"] == 1.0
    assert row["ref_period_start"] == 2000 and row["ref_period_end"] == 2000


def test_mnq_is_mean_of_annual_minima():
    df = pl.concat([_year("A", 2000, [10.0] * 100 + [2.0]),
                    _year("A", 2001, [10.0] * 100 + [4.0])])
    out = compute_thresholds(df, ref_start=2000, ref_end=2001)
    assert out.row(0, named=True)["mnq"] == 3.0


def test_years_outside_ref_ignored_and_no_data_no_row():
    df = pl.concat([_year("A", 2000, [float(i) for i in range(1, 366)]),
                    _year("A", 2020, [999.0] * 200),   # ausserhalb Referenz
                    _year("B", 2020, [1.0] * 200)])    # B hat keine Referenzdaten
    out = compute_thresholds(df, ref_start=2000, ref_end=2011)
    assert out["station_id"].to_list() == ["A"]
    assert abs(out.row(0, named=True)["q95"] - 19.2) < 1e-9


def test_nulls_excluded():
    # 50 nulls + 316 non-null values = 366 days (exactly WY 2000)
    # Q95 of values 1..316 = 1 + 0.05*(316-1) = 1 + 15.75 = 16.75
    df = _year("A", 2000, [None] * 50 + [float(i) for i in range(1, 317)])
    out = compute_thresholds(df, ref_start=2000, ref_end=2000)
    assert abs(out.row(0, named=True)["q95"] - 16.75) < 1e-9
