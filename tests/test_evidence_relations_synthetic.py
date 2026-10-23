"""data/evidence_relations/synthetic + bayes + results/evidence_relations/reference_models: the closed-form formulas (against an independent
from-scratch re-derivation, not just against themselves), the generator's self-consistency rules at a shrunk
scale (fast; the full 153,600-row build is exercised by `finagent evidence-synthetic` itself, not by pytest),
and the three reference forecasters on a small hand-built frame with known answers.
"""
from __future__ import annotations

import lzma

import numpy as np
import pandas as pd
import pytest

from finagent.evidence_relations import bayes, reference_models, synthetic


# ================================================================================================== bayes.py: independent re-derivation
def _solve_from_scratch(s1, s2, tau1, tau2, c, sigma):
    """E[theta|S1,S2] and Var[theta|S1,S2] via a direct 2x2 Gaussian-conditioning solve (numpy.linalg.solve on
    Sigma = Cov([S1,S2])), a different code path from bayes.py's expanded closed-form algebra."""
    sigma2 = sigma ** 2
    cov_theta_s = np.array([sigma2, sigma2])
    sigma_mat = np.array([[sigma2 + tau1 ** 2, sigma2 + c * tau1 * tau2],
                          [sigma2 + c * tau1 * tau2, sigma2 + tau2 ** 2]])
    w = np.linalg.solve(sigma_mat, cov_theta_s)  # w == Sigma^{-1} @ cov_theta_s, since Sigma is symmetric
    mean = w[0] * s1 + w[1] * s2
    var = sigma2 - cov_theta_s @ w
    return mean, var, w[0], w[1]


@pytest.mark.parametrize("s1,s2,tau1,tau2,c", [
    (5.0, -3.0, 10.0, 10.0, 0.0), (5.0, -3.0, 10.0, 10.0, 0.5), (5.0, -3.0, 10.0, 10.0, 0.95),
    (12.3, -7.1, 10.0, 40.0, 0.0), (12.3, -7.1, 40.0, 10.0, 0.0), (0.0, 0.0, 10.0, 40.0, 0.0),
])
def test_two_signal_general_matches_independent_solve(s1, s2, tau1, tau2, c):
    want = _solve_from_scratch(s1, s2, tau1, tau2, c, bayes.SIGMA if hasattr(bayes, "SIGMA") else 20.0)
    mean, var, w1, w2 = bayes.two_signal_general(np.array(s1), np.array(s2), tau1, tau2, c, 20.0)
    assert abs(float(mean) - want[0]) < 1e-9
    assert abs(float(var) - want[1]) < 1e-9
    assert abs(float(w1) - want[2]) < 1e-9
    assert abs(float(w2) - want[3]) < 1e-9


def test_two_signal_symmetric_is_the_tau1_eq_tau2_special_case():
    s1, s2, tau, sigma = np.array(5.0), np.array(-3.0), 10.0, 20.0
    for c in (0.0, 0.5, 0.95):
        mean_g, var_g, w1_g, w2_g = bayes.two_signal_general(s1, s2, tau, tau, c, sigma)
        mean_s, var_s, w1_s, w2_s = bayes.two_signal_symmetric(s1, s2, tau, c, sigma)
        assert abs(float(mean_g) - float(mean_s)) < 1e-9
        assert abs(float(var_g) - float(var_s)) < 1e-9
        assert w1_g == pytest.approx(w2_g)  # symmetric tau => always equal weight, DESIGN.md S3.3
        assert (float(w1_s), float(w2_s)) == pytest.approx((float(w1_g), float(w2_g)))


def test_delta_var_from_c_limits():
    sigma, tau = 20.0, 10.0
    textbook_c0 = sigma ** 4 * tau ** 2 / ((sigma ** 2 + tau ** 2) * (2 * sigma ** 2 + tau ** 2))
    assert bayes.delta_var_from_c(0.0, tau, sigma) == pytest.approx(textbook_c0)
    assert bayes.delta_var_from_c(1.0, tau, sigma) == 0.0
    assert bayes.delta_var_from_c(0.999999, tau, sigma) < 1e-4


def test_one_signal_is_general_formula_with_the_other_signal_dropped():
    """S3.4: a stale S2 is not 'c close to 1', it is 'S2 carries zero covariance with theta and with S1'."""
    s1, tau1, sigma = np.array(7.5), 10.0, 20.0
    mean1, var1 = bayes.one_signal(s1, tau1, sigma)
    # Reconstructing the 2x2 solve with Cov(theta,S2)=0 and Cov(S1,S2)=0 directly (not via two_signal_general,
    # whose c parameter cannot express "S2 dropped" -- this checks S3.4's claim with its own matrix).
    sigma2 = sigma ** 2
    sigma_mat = np.array([[sigma2 + tau1 ** 2, 0.0], [0.0, 1.0]])  # S2's own variance is irrelevant: weight is 0
    cov_theta_s = np.array([sigma2, 0.0])
    w = np.linalg.solve(sigma_mat, cov_theta_s)
    mean2 = w[0] * float(s1) + w[1] * 999.0  # w[1] must be ~0, so an arbitrary S2 value must not matter
    var2 = sigma2 - cov_theta_s @ w
    assert abs(w[1]) < 1e-9
    assert abs(float(mean1) - mean2) < 1e-9
    assert abs(float(var1) - var2) < 1e-9


# ================================================================================================== synthetic.py: generator self-consistency (shrunk scale)
@pytest.fixture
def shrunk_realizations(monkeypatch):
    """N_REALIZATIONS small enough to build every condition in well under a second, for a self-consistency
    check of the generator's rules (not a substitute for the full, 153,600-row `finagent evidence-synthetic`
    build, which is run and cross-checked against the source project separately -- see README.md)."""
    monkeypatch.setitem(synthetic.N_REALIZATIONS, "train", 3)
    monkeypatch.setitem(synthetic.N_REALIZATIONS, "val", 2)
    monkeypatch.setitem(synthetic.N_REALIZATIONS, "test", 2)


def test_conditions_count_and_shape():
    conds = list(synthetic.conditions())
    assert len(conds) == 30
    by_variant = {}
    for variant, rho, rho_idx, c, c_idx, tau1, tau2, tau_idx, tau_setting in conds:
        by_variant[variant] = by_variant.get(variant, 0) + 1
    assert by_variant == {"base": 18, "stale": 6, "contradiction": 6}


def test_build_rows_self_checks_pass_at_shrunk_scale(shrunk_realizations):
    all_rows_by_split, n_unique = synthetic.build_rows()
    n_conditions = len(list(synthetic.conditions()))
    expected_realizations = sum(synthetic.N_REALIZATIONS.values()) * n_conditions
    assert n_unique == expected_realizations  # the global dedup assert inside build_condition never fired
    checks = synthetic.self_checks(all_rows_by_split)
    for key in ("base_posterior_var_constant_within_condition", "base_weights_always_equal",
               "stale_weight_s2_always_zero", "stale_var_matches_one_signal_formula",
               "stale_s2_equals_prev_round_s2", "contradiction_always_opposite_sign",
               "position_swap_information_equivalent"):
        assert checks[key] is True, key
    assert checks["delta_var_is_zero_at_c1_exact"] == 0.0


def test_build_xz_roundtrip_and_hashes_at_shrunk_scale(shrunk_realizations):
    jsonl_bytes, xz_bytes, summary = synthetic.build(write_to=None)
    for split in synthetic.SPLITS:
        assert lzma.decompress(xz_bytes[split]) == jsonl_bytes[split]
        assert summary["decompressed_sha256"][f"{split}.jsonl"] == synthetic.sha256_bytes(jsonl_bytes[split])
        assert summary["compressed_sha256"][f"{split}.jsonl.xz"] == synthetic.sha256_bytes(xz_bytes[split])
    assert "build_seconds" not in summary  # wall-clock timing must never affect the determinism-checked summary


def test_build_is_deterministic_at_shrunk_scale(shrunk_realizations):
    _jsonl_a, xz_a, summary_a = synthetic.build(write_to=None)
    _jsonl_b, xz_b, summary_b = synthetic.build(write_to=None)
    assert xz_a == xz_b
    assert summary_a == summary_b


def test_prompt_position_swap_is_information_equivalent():
    history = list(range(40))
    variants = synthetic.build_variants(history, s1=5.5, s2=-3.25, tau1=10.0, tau2=40.0, prev_s2=1.0)
    assert "Signal A: 5.5" in variants["base"]
    assert "Signal A: 5.5" in variants["position_swapped"]
    assert variants["base"].index("Signal A") < variants["base"].index("Signal B")
    assert variants["position_swapped"].index("Signal B") < variants["position_swapped"].index("Signal A")


# ================================================================================================== reference_models.py
def _toy_frame():
    return pd.DataFrame({
        "rho": [0.4, 0.4, 0.0],
        "x_t": [10.0, 10.0, 0.0],
        "s1": [6.0, 6.0, 8.0],
        "s2": [6.0, -6.0, 8.0],
        "tau1": [10.0, 10.0, 10.0],
        "tau2": [10.0, 10.0, 10.0],
        "c": [0.0, 0.0, 0.0],
        "stale_round": [False, False, True],
    })


def test_predict_bayes_optimal_matches_bayes_module():
    df = _toy_frame()
    got = reference_models.predict_bayes_optimal(df)
    mean_fresh, _v, _w1, _w2 = bayes.two_signal_general(np.array([6.0, 6.0]), np.array([6.0, -6.0]), 10.0, 10.0,
                                                        0.0, reference_models.SIGMA)
    mean_stale, _v = bayes.one_signal(np.array(8.0), 10.0, reference_models.SIGMA)
    assert got[0] == pytest.approx(mean_fresh[0])
    assert got[1] == pytest.approx(mean_fresh[1])
    assert got[2] == pytest.approx(float(mean_stale))


def test_predict_counting_naive_averages_not_sums():
    df = _toy_frame()
    got = reference_models.predict_counting_naive(df)
    assert list(got) == pytest.approx([6.0, 0.0, 8.0])


def test_predict_salience_follower_picks_larger_magnitude_and_a_wins_ties():
    df = pd.DataFrame({"s1": [3.0, -3.0, 5.0], "s2": [-9.0, 9.0, 5.0]})
    got = reference_models.predict_salience_follower(df)
    assert list(got) == [-9.0, 9.0, 5.0]  # row 3: exact tie |5|==|5| -> Signal A (s1) wins


def test_predict_delta1_adds_the_same_ar_term_for_every_model():
    df = _toy_frame()
    rho, x_t = df["rho"].to_numpy(), df["x_t"].to_numpy()
    for name in reference_models.MODEL_NAMES:
        theta_hat = reference_models.PREDICT[name](df)
        delta1 = reference_models.predict_delta1(name, df)
        assert np.allclose(delta1, (rho - 1.0) * x_t + theta_hat)
