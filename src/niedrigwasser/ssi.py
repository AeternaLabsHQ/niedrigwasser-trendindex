from __future__ import annotations

import warnings

import numpy as np
import polars as pl
from scipy import stats

from niedrigwasser.water_year import water_year_expr

MIN_REF_YEARS = 10


def summer_mean(daily: pl.DataFrame) -> pl.DataFrame:
    return (
        daily.with_columns(water_year_expr("date").alias("water_year"))
        .filter(pl.col("date").dt.month().is_between(5, 10) & pl.col("q").is_not_null())
        .group_by("station_id", "water_year")
        .agg(pl.col("q").mean().alias("summer_mean"))
        .sort("station_id", "water_year")
    )


def _empirical_ssi(ref: np.ndarray, values: np.ndarray) -> np.ndarray:
    n = len(ref)
    # Rang jedes Werts gegen die Referenzverteilung (Weibull-Plotting-Position)
    ranks = np.searchsorted(np.sort(ref), values, side="right").astype(float)
    p = np.clip(ranks / (n + 1), 1 / (n + 1), n / (n + 1))
    return stats.norm.ppf(p)


def _fit_ssi(ref: np.ndarray, values: np.ndarray) -> tuple[np.ndarray, str]:
    candidates = []
    for name, dist in (("gamma", stats.gamma), ("lognorm", stats.lognorm)):
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                params = dist.fit(ref, floc=0)
                if not all(np.isfinite(params)):
                    continue
                ks = stats.kstest(ref, dist.cdf, args=params)
            if np.isfinite(ks.statistic) and np.isfinite(ks.pvalue):
                candidates.append((ks.statistic, ks.pvalue, name, dist, params))
        except Exception:
            continue
    candidates.sort(key=lambda c: c[0])
    if candidates and candidates[0][1] >= 0.05:
        _, _, name, dist, params = candidates[0]
        try:
            cdf_vals = dist.cdf(values, *params)
            if np.all(np.isfinite(cdf_vals)):
                p = np.clip(cdf_vals, 1e-6, 1 - 1e-6)
                return stats.norm.ppf(p), name
        except Exception:
            pass
    return _empirical_ssi(ref, values), "empirical"


def ssi_for_station(values: pl.DataFrame, ref_start: int, ref_end: int) -> pl.DataFrame:
    wy = values["water_year"].to_numpy()
    x = values["summer_mean"].to_numpy().astype(float)
    ref_mask = (wy >= ref_start) & (wy <= ref_end)
    ref = x[ref_mask]
    if len(ref) < MIN_REF_YEARS:
        return values.select("water_year").with_columns(
            pl.lit(None, dtype=pl.Float64).alias("ssi"),
            pl.lit("insufficient_ref").alias("ssi_method"),
        )
    ssi, method = _fit_ssi(ref, x)
    return pl.DataFrame({"water_year": wy, "ssi": ssi}).with_columns(
        pl.lit(method).alias("ssi_method")
    )


def compute_ssi(
    daily: pl.DataFrame, ref_start: int = 1992, ref_end: int = 2011
) -> pl.DataFrame:
    sm = summer_mean(daily)
    frames = []
    for (station,), grp in sm.group_by("station_id", maintain_order=True):
        frames.append(
            ssi_for_station(grp, ref_start, ref_end).with_columns(
                pl.lit(station).alias("station_id")
            )
        )
    return (
        pl.concat(frames).select("station_id", "water_year", "ssi", "ssi_method")
        .sort("station_id", "water_year")
    )
