from datetime import date

import polars as pl

from niedrigwasser.water_year import (
    day_of_water_year,
    water_year,
    water_year_end,
    water_year_expr,
    water_year_start,
)


def test_water_year_boundaries():
    assert water_year(date(2024, 10, 31)) == 2024
    assert water_year(date(2024, 11, 1)) == 2025
    assert water_year(date(2025, 10, 31)) == 2025
    assert water_year(date(2025, 1, 15)) == 2025


def test_water_year_start_end():
    assert water_year_start(2025) == date(2024, 11, 1)
    assert water_year_end(2025) == date(2025, 10, 31)


def test_day_of_water_year():
    assert day_of_water_year(date(2024, 11, 1)) == 1
    assert day_of_water_year(date(2024, 12, 31)) == 61
    assert day_of_water_year(date(2025, 10, 31)) == 365
    # Wasserjahr 2024 enthält den 29.02.2024 -> 366 Tage
    assert day_of_water_year(date(2024, 10, 31)) == 366


def test_water_year_expr_matches_scalar():
    dates = [date(2024, 10, 31), date(2024, 11, 1), date(2025, 6, 1)]
    df = pl.DataFrame({"date": dates})
    out = df.with_columns(water_year_expr("date").alias("wy"))
    assert out["wy"].to_list() == [water_year(d) for d in dates]
