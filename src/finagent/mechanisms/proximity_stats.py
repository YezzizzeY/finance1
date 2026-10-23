"""Closed-form statistics for the proximity analysis (numpy + stdlib only; scipy and statsmodels are not dependencies).

Ported unchanged in arithmetic from the original analysis' helper module, so that every number in
results/mechanisms/proximity/data.json comes out bit-for-bit the same:

  ols_simple             simple OLS y = a + b*x, SE from residual variance (df = n - 2)
  fisher_r_ci            Pearson r 95% interval via the Fisher z-transform, SE = 1/sqrt(n - 3)
  student_t_*            Student-t tail via the regularized incomplete beta function (Lentz continued fraction,
                         the classical Numerical-Recipes algorithm)
  diff_of_slopes_ztest   z-test on the difference of two independent slopes, SE_diff = sqrt(se1^2 + se2^2)
  ci_overlap             whether two +/- 1.96 SE slope intervals overlap
  binomial_test_exact    exact two-sided binomial test (the scipy.stats.binomtest / R binom.test definition)
  wilson_ci              Wilson score interval for a binomial proportion
"""
from __future__ import annotations

import math

import numpy as np

Z95 = 1.959963984540054


# ------------------------------------------------------------------ regularized incomplete beta (Lentz continued fraction)
def _betacf(a, b, x, max_iter=200, eps=3.0e-12):
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-30:
        d = 1e-30
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-30:
            d = 1e-30
        c = 1.0 + aa / c
        if abs(c) < 1e-30:
            c = 1e-30
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def betainc(a, b, x):
    """Regularized incomplete beta function I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def student_t_sf(t, df):
    """One-sided upper tail P(T > |t|) of Student-t with df degrees of freedom."""
    t = abs(t)
    x = df / (df + t * t)
    return 0.5 * betainc(df / 2.0, 0.5, x)


def student_t_pvalue_two_sided(t, df):
    return 2.0 * student_t_sf(t, df)


def norm_cdf(z):
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def norm_sf_two_sided(z):
    return 2.0 * (1.0 - norm_cdf(abs(z)))


# ------------------------------------------------------------------ simple OLS y = a + b*x
def ols_simple(x, y):
    x = np.asarray(x, dtype=float)
    y = np.asarray(y, dtype=float)
    n = len(x)
    xbar = x.mean()
    ybar = y.mean()
    sxx = np.sum((x - xbar) ** 2)
    sxy = np.sum((x - xbar) * (y - ybar))
    b = sxy / sxx
    a = ybar - b * xbar
    resid = y - (a + b * x)
    df = n - 2
    s2 = np.sum(resid ** 2) / df if df > 0 else float("nan")
    se_b = math.sqrt(s2 / sxx) if df > 0 else float("nan")
    se_a = math.sqrt(s2 * (1.0 / n + xbar ** 2 / sxx)) if df > 0 else float("nan")
    r = sxy / math.sqrt(sxx * np.sum((y - ybar) ** 2))
    r2 = r * r
    t_b = b / se_b if se_b > 0 else float("nan")
    p_b = student_t_pvalue_two_sided(t_b, df) if df > 0 else float("nan")
    return dict(n=int(n), slope=float(b), slope_se=float(se_b), intercept=float(a),
                intercept_se=float(se_a), r=float(r), r2=float(r2), df=int(df),
                t_slope=float(t_b), p_slope=float(p_b))


def fisher_r_ci(r, n):
    """95% interval of a Pearson r via the Fisher z-transform."""
    if n <= 3:
        return [float("nan"), float("nan")]
    z = math.atanh(max(min(r, 0.999999), -0.999999))
    se = 1.0 / math.sqrt(n - 3)
    return [float(math.tanh(z - Z95 * se)), float(math.tanh(z + Z95 * se))]


def diff_of_slopes_ztest(b1, se1, b2, se2):
    diff = b1 - b2
    se_diff = math.sqrt(se1 ** 2 + se2 ** 2)
    z = diff / se_diff if se_diff > 0 else float("nan")
    p = norm_sf_two_sided(z) if se_diff > 0 else float("nan")
    return dict(diff=float(diff), se_diff=float(se_diff), z=float(z), p_two_sided=float(p),
                ci95_lo=float(diff - Z95 * se_diff), ci95_hi=float(diff + Z95 * se_diff))


def ci_overlap(b1, se1, b2, se2, z=1.96):
    lo1, hi1 = b1 - z * se1, b1 + z * se1
    lo2, hi2 = b2 - z * se2, b2 + z * se2
    return not (hi1 < lo2 or hi2 < lo1)


def binomial_test_exact(k, n, p=0.5):
    """Exact two-sided binomial p-value: the sum of every pmf value <= pmf(k) * (1 + 1e-7)."""
    def pmf(i):
        return math.comb(n, i) * (p ** i) * ((1 - p) ** (n - i))
    p_obs = pmf(k)
    tol = 1.0 + 1e-7
    total = 0.0
    for i in range(n + 1):
        if pmf(i) <= p_obs * tol:
            total += pmf(i)
    return min(total, 1.0)


def wilson_ci(k, n, z=Z95):
    if n == 0:
        return [float("nan"), float("nan")]
    phat = k / n
    denom = 1 + z ** 2 / n
    center = phat + z ** 2 / (2 * n)
    half = z * math.sqrt(phat * (1 - phat) / n + z ** 2 / (4 * n ** 2))
    return [float((center - half) / denom), float((center + half) / denom)]


def mean_se(values):
    """(mean, standard error with ddof=1, n)."""
    a = np.asarray(values, dtype=float)
    n = len(a)
    return float(a.mean()), (float(a.std(ddof=1) / math.sqrt(n)) if n > 1 else float("nan")), n
