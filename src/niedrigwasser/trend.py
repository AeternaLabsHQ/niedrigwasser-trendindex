"""Trend-Modul: TFPW-MK + Sen, Dekaden-Statistik, nicht-stationaere GEV.

Reine Funktionen (kein I/O) — Aufrufer ist ``niedrigwasser.stages.trend``.
"""
from __future__ import annotations

import math
from collections.abc import Sequence

import numpy as np
import polars as pl
import pymannkendall as mk
from scipy.optimize import minimize
from scipy.stats import chi2, false_discovery_control

MIN_MK_N = 10
DECADES = [(1992, 2001), (2002, 2013), (2014, 2025)]
XI_BOUND = 0.5
EULER_MASCHERONI = 0.5772156649015329


def mk_trend(values: list[float]) -> dict:
    """TFPW-Mann-Kendall-Trendtest + Sen-Slope.

    Bei n < ``MIN_MK_N`` liefert der Test keine sinnvolle Aussage; es wird
    ``{"trend": "insufficient", ...}`` zurueckgegeben statt zu crashen. Bei
    einer konstanten Reihe (Varianz 0) ist die Autokorrelation der
    TFPW-Vorwitterung undefiniert (0/0) — das wird abgefangen statt eine
    RuntimeWarning/NaN durchzureichen.
    """
    n = len(values)
    if n < MIN_MK_N:
        return {"trend": "insufficient", "p_value": None, "sens_slope": None, "n": n}
    arr = np.asarray(values, dtype=float)
    if np.ptp(arr) < 1e-12:
        return {"trend": "no trend", "p_value": 1.0, "sens_slope": 0.0, "n": n}
    res = mk.trend_free_pre_whitening_modification_test(values)
    slope = mk.sens_slope(values).slope
    return {"trend": res.trend, "p_value": float(res.p), "sens_slope": float(slope), "n": n}


def bh_adjust(pvals: Sequence[float | None]) -> list[float | None]:
    """Benjamini-Hochberg-Korrektur ueber eine Testfamilie; None bleibt None.

    Adjustiert nur die vorhandenen p-Werte (None = kein Test gerechnet, z.B.
    trend="insufficient" bei n < MIN_MK_N) und setzt sie positionstreu zurueck.
    Jede Kennzahl bildet ihre eigene Familie - days_below und nm7q duerfen
    nicht gemeinsam korrigiert werden.
    """
    idx = [i for i, p in enumerate(pvals) if p is not None]
    out: list[float | None] = [None] * len(pvals)
    if not idx:
        return out
    adj = false_discovery_control([pvals[i] for i in idx], method="bh")
    for i, a in zip(idx, adj):
        out[i] = float(min(a, 1.0))
    return out


def decade_stats(metrics: pl.DataFrame, col: str) -> pl.DataFrame:
    """Dekaden-Statistik (mean/median/p90/share_zero) ueber alle Station-Jahre.

    Dekaden: 1992-2001, 2002-2013, 2014-2025 (Grenzen inklusiv).
    """
    rows = []
    for start, end in DECADES:
        sub = metrics.filter(pl.col("water_year").is_between(start, end))
        vals = sub[col].drop_nulls()
        n = vals.len()
        if n == 0:
            rows.append({
                "decade": f"{start}-{end}", "n": 0,
                "mean": None, "median": None, "p90": None, "share_zero": None,
            })
            continue
        share_zero = float((vals == 0).sum()) / n
        rows.append({
            "decade": f"{start}-{end}", "n": n,
            "mean": float(vals.mean()), "median": float(vals.median()),
            "p90": float(vals.quantile(0.9)), "share_zero": share_zero,
        })
    return pl.DataFrame(rows)


def _gev_neg_log_lik(mu, sigma: float, xi: float, x: np.ndarray,
                      xi_bound: float | None = XI_BOUND) -> float:
    if sigma <= 0 or (xi_bound is not None and abs(xi) > xi_bound):
        return 1e10
    z = 1.0 + xi * (x - mu) / sigma
    if np.any(z <= 0):
        return 1e10
    if abs(xi) < 1e-8:
        t = (x - mu) / sigma
        ll = -np.log(sigma) - t - np.exp(-t)
    else:
        ll = -np.log(sigma) - (1.0 + 1.0 / xi) * np.log(z) - z ** (-1.0 / xi)
    if not np.all(np.isfinite(ll)):
        return 1e10
    return float(-np.sum(ll))


def _obj_stationary(params: np.ndarray, x: np.ndarray, xi_bound: float | None) -> float:
    mu, log_sigma, xi = params
    return _gev_neg_log_lik(mu, math.exp(log_sigma), xi, x, xi_bound=xi_bound)


def _obj_nonstationary(params: np.ndarray, x: np.ndarray, t: np.ndarray,
                        xi_bound: float | None) -> float:
    mu0, mu1, log_sigma, xi = params
    mu = mu0 + mu1 * t
    return _gev_neg_log_lik(mu, math.exp(log_sigma), xi, x, xi_bound=xi_bound)


def fit_gev_nonstationary(values: list[float], xi_bound: float | None = XI_BOUND) -> dict:
    """MLE fuer stationaere GEV(mu, sigma, xi) und nicht-stationaere
    GEV(mu0 + mu1*t, sigma, xi); Likelihood-Ratio-Test der Trend-Komponente.

    ``xi_bound`` beschraenkt |xi| ueber eine Penalty in der Zielfunktion
    (Default 0.5) — bei nur ~35 Jahreswerten ist ein frei laufendes xi
    numerisch fragil. ``xi_bound=None`` deaktiviert die Schranke (unrestringierter
    Fit) — Aufrufer sollten dann beide Varianten (bounded/free) gegenueberstellen,
    statt der bounded-Punktschaetzung blind zu vertrauen. Bei
    Konvergenzversagen: ``{"error": ...}`` statt Crash.
    """
    x = np.asarray(values, dtype=float)
    n = len(x)
    if n < 10:
        return {"error": f"zu wenige Werte fuer GEV-Fit (n={n} < 10)"}
    t = np.arange(n, dtype=float)

    mean = float(x.mean())
    std = float(x.std(ddof=1)) if n > 1 else 1.0
    std = max(std, 1e-6)
    sigma0 = max(std * math.sqrt(6) / math.pi, 1e-6)
    mu0_start = mean - EULER_MASCHERONI * sigma0
    xi0 = 0.1

    opts = {"xatol": 1e-8, "fatol": 1e-8, "maxiter": 8000, "maxfev": 8000}

    res_s = minimize(
        _obj_stationary, x0=[mu0_start, math.log(sigma0), xi0],
        args=(x, xi_bound), method="Nelder-Mead", options=opts,
    )
    res_ns = minimize(
        _obj_nonstationary, x0=[mu0_start, 0.0, math.log(sigma0), xi0],
        args=(x, t, xi_bound), method="Nelder-Mead", options=opts,
    )

    if not res_s.success or not res_ns.success:
        return {"error": "GEV-Fit nicht konvergiert"}
    if (not np.isfinite(res_s.fun) or not np.isfinite(res_ns.fun)
            or res_s.fun >= 1e9 or res_ns.fun >= 1e9):
        return {"error": "GEV-Fit nicht konvergiert"}

    mu0, mu1, log_sigma, xi = res_ns.x
    sigma = math.exp(log_sigma)

    ll_ns = -float(res_ns.fun)
    ll_s = -float(res_s.fun)
    lr = max(2.0 * (ll_ns - ll_s), 0.0)
    p_value = float(chi2.sf(lr, df=1))

    return {
        "mu0": float(mu0), "mu1": float(mu1), "sigma": float(sigma), "xi": float(xi),
        "ll_ns": ll_ns, "ll_s": ll_s, "lr": lr, "p_value": p_value,
    }


def empirical_weibull_rp(values: list[float], value: float) -> float:
    """Empirisches Wiederkehrintervall von ``value`` in ``values`` nach der
    Weibull-Plotting-Position: RP = (n+1) / r, wobei r der Rang von
    ``value`` in absteigender Sortierung ist (r=1 fuer den groessten Wert).
    Verteilungsfreie Referenz, unabhaengig vom GEV-Fit."""
    n = len(values)
    r = sum(1 for v in values if v >= value)
    return (n + 1) / r


def _gev_cdf(value: float, mu: float, sigma: float, xi: float) -> float:
    z = 1.0 + xi * (value - mu) / sigma
    if abs(xi) < 1e-8:
        tt = (value - mu) / sigma
        return math.exp(-math.exp(-tt))
    if z <= 0:
        return 0.0 if xi > 0 else 1.0
    return math.exp(-z ** (-1.0 / xi))


def return_period_shift(fit: dict, n_years: int, value: float) -> dict:
    """Wiederkehrintervall von ``value`` unter mu(t) am Anfang (t=0) vs.
    Ende (t=n_years-1) der Zeitreihe: ``{"rp_start", "rp_end"}``."""
    if "error" in fit:
        return {"error": fit["error"]}
    mu0, mu1, sigma, xi = fit["mu0"], fit["mu1"], fit["sigma"], fit["xi"]
    mu_start = mu0
    mu_end = mu0 + mu1 * (n_years - 1)

    def _rp(mu: float) -> float:
        cdf = _gev_cdf(value, mu, sigma, xi)
        surv = max(1.0 - cdf, 1e-12)
        return 1.0 / surv

    return {"rp_start": _rp(mu_start), "rp_end": _rp(mu_end)}
