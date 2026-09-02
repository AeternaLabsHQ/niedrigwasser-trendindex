import numpy as np
import polars as pl
from scipy.stats import genextreme, gumbel_r

from niedrigwasser.trend import (
    _gev_cdf,
    _gev_neg_log_lik,
    bh_adjust,
    decade_stats,
    empirical_weibull_rp,
    fit_gev_nonstationary,
    mk_trend,
    return_period_shift,
)


def test_bh_adjust_bekannte_werte():
    # BH auf [0.01,0.02,0.03,0.04]: p_i * n/rang, monotonisiert -> alle 0.04
    adj = bh_adjust([0.01, 0.02, 0.03, 0.04, None])
    assert adj[4] is None
    assert all(abs(a - 0.04) < 1e-12 for a in adj[:4])


def test_bh_adjust_leer_und_nur_none():
    assert bh_adjust([]) == []
    assert bh_adjust([None, None]) == [None, None]


def test_mk_trend_detects_linear_trend():
    # linearer Trend + kleines deterministisches Rauschen (reiner linearer
    # Trend hat Varianz 0 nach Detrending -> TFPW-Autokorrelation undefiniert)
    noise = [0.3, -0.2, 0.1, -0.4, 0.2] * 6
    values = [float(v) + n for v, n in zip(range(30), noise)]
    res = mk_trend(values)
    assert res["trend"] == "increasing"
    assert res["p_value"] < 0.01
    assert res["sens_slope"] > 0
    assert res["n"] == 30


def test_mk_trend_insufficient():
    res = mk_trend([1.0, 2.0, 3.0, 2.0, 1.0])
    assert res["trend"] == "insufficient"
    assert res["p_value"] is None
    assert res["sens_slope"] is None
    assert res["n"] == 5


def test_decade_stats_buckets():
    # Stationsjahre: je 2 Werte pro Dekade an den Grenzen 2001/2002 und 2013/2014,
    # damit die Bucket-Zuordnung eindeutig geprueft wird.
    metrics = pl.DataFrame({
        "water_year": [1992, 2001, 2002, 2013, 2014, 2025],
        "val": [0.0, 0.0, 10.0, 10.0, 5.0, 15.0],
    })
    out = decade_stats(metrics, "val").sort("decade")
    d1 = out.filter(pl.col("decade") == "1992-2001").row(0, named=True)
    d2 = out.filter(pl.col("decade") == "2002-2013").row(0, named=True)
    d3 = out.filter(pl.col("decade") == "2014-2025").row(0, named=True)
    assert d1["n"] == 2
    assert d1["mean"] == 0.0
    assert d1["share_zero"] == 1.0
    assert d2["n"] == 2
    assert d2["mean"] == 10.0
    assert d2["share_zero"] == 0.0
    assert d3["n"] == 2
    assert d3["mean"] == 10.0


def test_gev_recovers_stationary():
    rng = np.random.default_rng(42)
    true_mu, true_sigma = 50.0, 8.0
    values = gumbel_r.rvs(loc=true_mu, scale=true_sigma, size=60, random_state=rng)
    fit = fit_gev_nonstationary(values.tolist())
    assert "error" not in fit
    assert fit["p_value"] > 0.05
    assert abs(fit["mu0"] - true_mu) < 6.0


def test_gev_detects_trend():
    rng = np.random.default_rng(7)
    true_mu0, true_mu1, true_sigma = 30.0, 1.5, 6.0
    n = 60
    values = [
        gumbel_r.rvs(loc=true_mu0 + true_mu1 * t, scale=true_sigma, random_state=rng)
        for t in range(n)
    ]
    fit = fit_gev_nonstationary(values)
    assert "error" not in fit
    assert fit["p_value"] < 0.05
    assert fit["mu1"] > 0.0


def test_return_period_shift_direction():
    fit = {"mu0": 30.0, "mu1": 1.0, "sigma": 6.0, "xi": 0.0}
    res = return_period_shift(fit, n_years=20, value=80.0)
    assert res["rp_end"] < res["rp_start"]


def test_mk_trend_zero_variance_no_crash():
    res = mk_trend([5.0] * 15)
    assert res["trend"] == "no trend"
    assert res["p_value"] == 1.0
    assert res["sens_slope"] == 0.0
    assert res["n"] == 15


def test_gev_loglik_and_cdf_match_scipy_xi_positive():
    # scipy.stats.genextreme parametrisiert mit c = -xi (Coles-Konvention).
    mu, sigma, xi = 10.0, 3.0, 0.3
    x = np.array([9.0, 11.5, 14.0])
    ours_ll = -_gev_neg_log_lik(mu, sigma, xi, x, xi_bound=None)
    theirs_ll = genextreme.logpdf(x, c=-xi, loc=mu, scale=sigma).sum()
    assert np.isclose(ours_ll, theirs_ll, atol=1e-8)
    for v in [8.5, 10.0, 13.0]:
        assert np.isclose(
            _gev_cdf(v, mu, sigma, xi),
            genextreme.cdf(v, c=-xi, loc=mu, scale=sigma),
            atol=1e-10,
        )


def test_gev_loglik_and_cdf_match_scipy_xi_negative():
    mu, sigma, xi = 10.0, 3.0, -0.3
    x = np.array([9.0, 10.5, 12.0])
    ours_ll = -_gev_neg_log_lik(mu, sigma, xi, x, xi_bound=None)
    theirs_ll = genextreme.logpdf(x, c=-xi, loc=mu, scale=sigma).sum()
    assert np.isclose(ours_ll, theirs_ll, atol=1e-8)
    for v in [8.0, 10.0, 12.5]:
        assert np.isclose(
            _gev_cdf(v, mu, sigma, xi),
            genextreme.cdf(v, c=-xi, loc=mu, scale=sigma),
            atol=1e-10,
        )


def test_gev_support_violation_penalized():
    mu, sigma, xi = 10.0, 3.0, 0.3
    # untere Stuetzgrenze mu - sigma/xi = 0 -> x=-5 verletzt z>0.
    x = np.array([-5.0, 11.0])
    assert _gev_neg_log_lik(mu, sigma, xi, x, xi_bound=None) == 1e10


def test_empirical_weibull_rp_extremes():
    values = list(range(1, 35))  # 34 Werte, 1..34
    # groesster Wert (Rang 1 absteigend) -> RP = (34+1)/1 = 35
    assert empirical_weibull_rp(values, 34) == 35.0
    # kleinster Wert (Rang 34 absteigend, da alle >= 1) -> RP = 35/34
    assert np.isclose(empirical_weibull_rp(values, 1), 35 / 34)
