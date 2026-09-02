from datetime import date, timedelta

import polars as pl

from niedrigwasser.screening import (
    station_year_completeness,
    usable_station_years,
    usable_stations,
)


def _full_year(station: str, wy: int, gap_summer_days: int = 0) -> pl.DataFrame:
    """Komplettes Wasserjahr mit q=10.0; optional die ersten N Juli-Tage als null."""
    start = date(wy - 1, 11, 1)
    end = date(wy, 10, 31)
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    q = []
    gap = {date(wy, 7, 1) + timedelta(days=i) for i in range(gap_summer_days)}
    for d in days:
        q.append(None if d in gap else 10.0)
    return pl.DataFrame(
        {"station_id": [station] * len(days), "date": days, "q": q}
    ).with_columns(pl.col("date").cast(pl.Date))


def test_completeness_full_year():
    df = _full_year("A", 2020)
    out = station_year_completeness(df)
    row = out.row(by_predicate=(pl.col("station_id") == "A"), named=True)
    assert row["water_year"] == 2020
    assert row["summer_days_present"] == 184
    assert row["summer_coverage"] == 1.0
    assert row["data_completeness"] == 1.0


def test_usable_station_years_threshold():
    # 10 fehlende Sommertage -> 174/184 = 0.9457 < 0.95 -> raus
    # 9 fehlende -> 175/184 = 0.9511 >= 0.95 -> bleibt
    df = pl.concat([_full_year("A", 2020, gap_summer_days=10),
                    _full_year("A", 2021, gap_summer_days=9)])
    out = usable_station_years(station_year_completeness(df))
    assert out["water_year"].to_list() == [2021]


def test_winter_gaps_do_not_affect_summer_filter():
    df = _full_year("A", 2020)
    # kompletten Januar auf null setzen
    df = df.with_columns(
        pl.when(pl.col("date").dt.month() == 1).then(None).otherwise(pl.col("q")).alias("q")
    )
    out = usable_station_years(station_year_completeness(df))
    assert out.height == 1
    assert out["data_completeness"][0] < 1.0


def test_usable_stations_min_years():
    frames = [_full_year("A", wy) for wy in range(1992, 2017)]      # 25 Jahre
    frames += [_full_year("B", wy) for wy in range(1992, 2016)]     # 24 Jahre
    comp = station_year_completeness(pl.concat(frames))
    st = usable_stations(usable_station_years(comp))
    assert st["station_id"].to_list() == ["A"]
    assert st["n_usable_years"][0] == 25
