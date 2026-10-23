"""Closed-form Bayes-optimal (MMSE) combination of two noisy signals about a common Gaussian unknown. Full
derivation in evidence_relations/synthetic/DESIGN.md S3. Verbatim formulas implemented here, ported unchanged
(same variable names, same algebra) from 1_overreaction/repro/evidence_relations/bayes.py:

Model: theta ~ N(0, sigma^2)              [theta = eps_{t+1}, the AR(1) innovation; prior is unconditional
                                            because eps_{t+1} is independent of the history and of rho]
       S1 = theta + u1,  u1 ~ N(0, tau1^2)
       S2 = theta + u2,  u2 ~ N(0, tau2^2),  corr(u1, u2) = c
       theta independent of (u1, u2).

General (tau1 may differ from tau2), DESIGN.md S3.2:
    det   = (sigma^2+tau1^2)(sigma^2+tau2^2) - (sigma^2 + c*tau1*tau2)^2
    w1    = sigma^2 * tau2 * (tau2 - c*tau1) / det
    w2    = sigma^2 * tau1 * (tau1 - c*tau2) / det
    E[theta | S1,S2]   = w1*S1 + w2*S2
    Var[theta | S1,S2] = sigma^2 - sigma^4 * (tau1^2 + tau2^2 - 2*c*tau1*tau2) / det

Symmetric case tau1=tau2=tau (the base and stale variants), DESIGN.md S3.3 -- a closed-form special case of
the general formula, reproduced directly for auditability:
    E[theta | S1,S2]   = sigma^2 * (S1+S2) / (2*sigma^2 + tau^2*(1+c))
    Var[theta | S1,S2] = sigma^2 * tau^2*(1+c) / (2*sigma^2 + tau^2*(1+c))
    w1 = w2 = sigma^2 / (2*sigma^2 + tau^2*(1+c))                      [always EQUAL by symmetry: with equal
        stated noise levels the Bayes-optimal split between Signal A and Signal B is 50/50 regardless of c --
        c changes how much total weight the pair gets, not how it splits]

One signal only (S2 carries zero information about the current theta -- the stale-signal corollary,
DESIGN.md S3.4), equivalent to the general/symmetric formula with the OTHER signal's contribution removed
entirely (not merely "c=0" -- dropped):
    E[theta | S1]   = sigma^2 * S1 / (sigma^2 + tau1^2)
    Var[theta | S1] = sigma^2 * tau1^2 / (sigma^2 + tau1^2)

Additional variance reduction from using S2 given S1 is already used, as a function of c, for the symmetric
tau1=tau2=tau case (DESIGN.md S3.5):
    Delta_Var(c) = Var[theta|S1] - Var[theta|S1,S2]
                 = sigma^4 * tau^2 * (1-c) / [ (sigma^2+tau^2) * (2*sigma^2 + tau^2*(1+c)) ]
    Delta_Var(0) = sigma^4*tau^2 / [(sigma^2+tau^2)(2*sigma^2+tau^2)]   (textbook two-independent-measurements
                                                                          reduction)
    Delta_Var(1) = 0                                                   (S2 fully redundant)
"""
from __future__ import annotations

import numpy as np


def one_signal(s1: np.ndarray, tau1: float, sigma: float):
    denom = sigma ** 2 + tau1 ** 2
    mean = sigma ** 2 * s1 / denom
    var = sigma ** 2 * tau1 ** 2 / denom
    return mean, var


def two_signal_general(s1: np.ndarray, s2: np.ndarray, tau1: float, tau2: float, c: float, sigma: float):
    det = (sigma ** 2 + tau1 ** 2) * (sigma ** 2 + tau2 ** 2) - (sigma ** 2 + c * tau1 * tau2) ** 2
    w1 = sigma ** 2 * tau2 * (tau2 - c * tau1) / det
    w2 = sigma ** 2 * tau1 * (tau1 - c * tau2) / det
    mean = w1 * s1 + w2 * s2
    var = sigma ** 2 - sigma ** 4 * (tau1 ** 2 + tau2 ** 2 - 2 * c * tau1 * tau2) / det
    return mean, var, w1, w2


def two_signal_symmetric(s1: np.ndarray, s2: np.ndarray, tau: float, c: float, sigma: float):
    denom = 2 * sigma ** 2 + tau ** 2 * (1 + c)
    mean = sigma ** 2 * (s1 + s2) / denom
    var = sigma ** 2 * tau ** 2 * (1 + c) / denom
    w = sigma ** 2 / denom
    return mean, var, w, w


def delta_var_from_c(c: float, tau: float, sigma: float) -> float:
    return sigma ** 4 * tau ** 2 * (1 - c) / ((sigma ** 2 + tau ** 2) * (2 * sigma ** 2 + tau ** 2 * (1 + c)))


def draw_correlated_noise(n_real: int, n_rounds: int, tau1: float, tau2: float, c: float, rng: np.random.Generator):
    """u1 ~ N(0,tau1^2), u2 ~ N(0,tau2^2), corr(u1,u2)=c, via u1=tau1*z1, u2=tau2*(c*z1+sqrt(1-c^2)*z2) with
    z1,z2 i.i.d. N(0,1). Cov(u1,u2) = tau1*tau2*c for any tau1,tau2 (Var(z1)=1 so Cov(tau1*z1, tau2*c*z1) =
    tau1*tau2*c; the z2 term is uncorrelated with z1). Two independent standard-normal draws from one
    Generator call, so one rng advances it by exactly 2*n_real*n_rounds numbers regardless of tau1, tau2, c."""
    z1 = rng.standard_normal((n_real, n_rounds))
    z2 = rng.standard_normal((n_real, n_rounds))
    u1 = tau1 * z1
    u2 = tau2 * (c * z1 + np.sqrt(1.0 - c ** 2) * z2)
    return u1, u2
