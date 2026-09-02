from datetime import date, timedelta

import numpy as np
import polars as pl

from niedrigwasser.ssi import compute_ssi, summer_mean


def _daily(station: str, wy: int, summer_value: float) -> pl.DataFrame:
    start = date(wy - 1, 11, 1)
    n = (date(wy, 10, 31) - start).days + 1
    days = [start + timedelta(days=i) for i in range(n)]
    q = [summer_value if 5 <= d.month <= 10 else 99.0 for d in days]
    return pl.DataFrame({"station_id": [station] * n, "date": days,
                         "q": q}).with_columns(pl.col("date").cast(pl.Date))


def test_summer_mean():
    df = _daily("A", 2000, 7.0)
    out = summer_mean(df)
    assert out.row(0, named=True)["summer_mean"] == 7.0


def test_ssi_median_year_near_zero_and_monotone():
    rng = np.random.default_rng(42)
    ref_vals = rng.gamma(shape=4.0, scale=2.5, size=20)  # WY 1992..2011
    frames = [_daily("A", 1992 + i, float(v)) for i, v in enumerate(ref_vals)]
    frames.append(_daily("A", 2018, float(ref_vals.min() * 0.3)))  # Extremjahr
    out = compute_ssi(pl.concat(frames), ref_start=1992, ref_end=2011)
    s = dict(zip(out["water_year"].to_list(), out["ssi"].to_list()))
    # Extremjahr klar negativ und kleinster SSI-Wert
    assert s[2018] < -1.0
    assert s[2018] == min(s.values())
    # Referenzperiode grob standardisiert: Mittel nahe 0
    ref_ssi = [s[wy] for wy in range(1992, 2012)]
    assert abs(float(np.mean(ref_ssi))) < 0.3
    assert out["ssi_method"][0] in ("gamma", "lognorm", "empirical")


def test_ssi_insufficient_ref():
    frames = [_daily("B", 2000 + i, 5.0 + i) for i in range(5)]  # nur 5 Referenzjahre
    out = compute_ssi(pl.concat(frames), ref_start=2000, ref_end=2011)
    assert out["ssi"].null_count() == out.height
    assert set(out["ssi_method"].to_list()) == {"insufficient_ref"}


def test_ssi_constant_ref_falls_back_to_empirical():
    # konstante Referenzwerte -> Verteilungsfit degeneriert -> empirical, kein Crash
    frames = [_daily("C", 1992 + i, 5.0) for i in range(15)]
    frames.append(_daily("C", 2020, 1.0))
    out = compute_ssi(pl.concat(frames), ref_start=1992, ref_end=2006)
    row_2020 = out.filter(pl.col("water_year") == 2020).row(0, named=True)
    assert row_2020["ssi"] is not None and row_2020["ssi"] < 0
