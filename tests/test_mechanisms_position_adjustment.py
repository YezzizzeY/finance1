"""results/mechanisms/position_adjustment: the rebuild equals the shipped data.json byte for byte and is deterministic,
the inputs are the recorded copies, the headline numbers and the coverage facts quoted in the prose hold, and the
closed-form statistics agree with independent computations. No network, CPU only (about a second per build)."""
from __future__ import annotations

import gzip
import hashlib
import json

import numpy as np
import pandas as pd
import pytest

from finagent import config
from finagent.mechanisms import position_adjustment as PA

INPUT_SHA256 = {
    "base5d_val_calm.json": "697228552aa5dc1721131ada509dab8b3d3761da2fc8ac7298ede8fe891aa7f6",
    "base5d_val_stress.json": "e8812ac5039dc81cc271560af7fc2b9020ac997f305cb3ac3ca0e074f2232998",
    "base5d_test_calm.json": "4c1176ba74c54e158785803f034cf9f7d8d133e1eb01dde04dd6c9d575ee0e8c",
    "base5d_test_crash.json": "451b6cb65467abe00ea9f44a76b09f8c5a1aa2798f9af68617a62cca77f4d276",
    "base5d_test_bear.json": "e3475f8ce135d8eb56d5f09ef7af75baed29feda44b0a08ed3998e037854b86d",
    "BASE_crash_R2.json": "1a38ed934a273d71705d56cabee595800ebd58244e2f76db97fd252801369398",
    "events_all.parquet": "317f6aaa8da6ef55ad19c669cc7c7c2c93c74ebd26da59f8b15c5cc5d343523b",
    "nonevent_days.parquet": "83c753d3686af35a1374556367e02afa40a33d697d105804ba97291f8feee11d",
}


@pytest.fixture(scope="module")
def built() -> dict:
    return PA.build()


@pytest.fixture(scope="module")
def fr() -> dict:
    return PA.frames()


def test_inputs_are_the_recorded_copies():
    names = {p.name for p in PA.input_paths().values()}
    assert names == set(INPUT_SHA256)
    for name, digest in INPUT_SHA256.items():
        assert hashlib.sha256((PA.DATA_DIR / name).read_bytes()).hexdigest() == digest, name
        assert digest in (PA.DATA_DIR / "README.md").read_text(), name


def test_build_reproduces_shipped_data_json(built):
    assert PA.dumps(built) == PA.OUT_FILE.read_text()


def test_build_is_deterministic(built):
    assert PA.dumps(PA.build()) == PA.dumps(built)


def test_main_writes_the_same_bytes(tmp_path, monkeypatch, capsys):
    shipped = PA.OUT_FILE.read_bytes()
    monkeypatch.setattr(PA, "OUT_DIR", tmp_path)
    monkeypatch.setattr(PA, "OUT_FILE", tmp_path / "data.json")
    assert PA.main([]) == 0
    first = (tmp_path / "data.json").read_bytes()
    assert PA.main([]) == 0
    assert (tmp_path / "data.json").read_bytes() == first == shipped
    assert PA.main(["--check"]) == 0
    (tmp_path / "data.json").write_text("{}\n")
    assert PA.main(["--check"]) == 1


def test_headline_numbers(built):
    assert built["n_trajectories_total"] == 440 and built["n_agent_days_total"] == 6240
    assert built["usable_windows"] == ["test_calm"]
    assert built["n_trajectories_usable_window"] == 80 and built["n_agent_days_usable_window"] == 1200
    assert built["n_consecutive_day_gaps"] == 1120 and built["n_gaps_with_rational_join_both_days"] == 692
    assert built["events_all_nonevent_overlap_check"] == 0
    assert built["method"]["k_base"] == pytest.approx(283.6009, abs=1e-4)
    h = built["headline"]
    assert h["overall"]["regression"]["n"] == 692
    assert h["overall"]["regression"]["b"] == pytest.approx(0.22170, abs=1e-5)
    assert h["overall"]["std_ratio"]["ratio"] == pytest.approx(6.70530, abs=1e-5)
    assert h["overall"]["spearman_rank_corr"]["rho"] == pytest.approx(-0.16485, abs=1e-5)
    assert h["quiet_abs_u_lt_1"]["regression"]["n"] == 532
    assert h["eventful_abs_u_ge_2"]["regression"]["n"] == 16
    assert h["mid_1_to_2_for_reference_only"]["regression"]["n"] == 144
    assert h["overall"]["regression"]["se_cluster_ticker"]["n_clusters"] == 26
    assert h["overall"]["regression"]["se_cluster_day"]["n_clusters"] == 14
    assert built["u_bucket_counts_among_rational_matched_agent_days"] == {
        "eventful_abs_u_ge_2": 20, "mid_1_to_2": 154, "quiet_abs_u_lt_1": 580, "total_matched_agent_days": 754}
    cov = {r["window"]: (r["n_ticker_days"], r["n_matched"]) for r in built["rational_join_coverage_by_window"]}
    assert cov == {"val_calm": (360, 0), "val_stress": (360, 0), "test_calm": (600, 377), "test_crash": (600, 0),
                   "test_bear": (600, 0), "test_crash_R2": (600, 0)}
    assert [(e["ticker"], e["g"]) for e in built["worked_examples"]] == [("ELV", 0), ("ALB", 0), ("FERG", 0)]
    # k scales b by 1/k and the std ratio by 1/k wherever clipping does not bind differently
    ks = built["k_sensitivity"]
    assert ks["k_double"]["b"] == pytest.approx(ks["k_base"]["b"] / 2, rel=1e-12)
    assert ks["k_base"]["b"] == h["overall"]["regression"]["b"]


def test_provenance_paths_are_repository_relative(built):
    for path in built["base_files_loaded"].values():
        assert path.startswith("data/mechanisms/position_adjustment/")
        assert (config.ROOT / path).is_file()
    assert "data/mechanisms/position_adjustment/events_all.parquet" in built["limitation"]


def test_coverage_facts_quoted_in_the_prose(fr):
    """The dates and counts the limitation text and the README state, recomputed from the data."""
    rat, agent = fr["rat"], fr["agent"]
    assert (rat["day"].min(), rat["day"].max()) == ("2025-10-02", "2026-09-17")
    span = agent.groupby("window")["day"].agg(["min", "max"])
    assert span.loc["val_calm", "min"] == "2023-10-02" and span.loc["val_stress", "min"] == "2024-07-22"
    assert span.loc["test_crash", "min"] == "2025-04-01" and span.loc["test_crash_R2", "min"] == "2025-04-01"
    assert span.loc["test_bear", "min"] == "2022-05-02"
    assert tuple(span.loc["test_calm"]) == ("2026-01-05", "2026-01-26")
    calm = agent[agent["window"] == "test_calm"]
    assert calm["ticker"].nunique() == 40 and set(calm.groupby("ticker")["g"].nunique()) == {2}
    src = calm.drop_duplicates(["ticker", "day"])["src"].value_counts().to_dict()
    assert src == {"events_all": 264, "nonevent": 113}
    assert (fr["n_clipped_lo"], fr["n_clipped_hi"]) == (10, 30)
    assert fr["n_source_rows"] == {"events_all": 15134, "nonevent_days": 6035}
    use = fr["use"]
    both = use[use["delta_rational"].notna() & use["delta_exposure"].notna()]
    eventful = both[both["u_abs"] >= PA.EVENTFUL_MIN]
    assert (eventful["ticker"].nunique(), eventful["day"].nunique()) == (5, 6)


def test_ols_robust_against_independent_computation():
    rng = np.random.default_rng(0)
    n = 60
    x = rng.normal(size=n)
    y = 0.5 + 2.0 * x + rng.normal(size=n)
    tick = np.repeat(np.arange(6), 10)
    day = np.tile(np.arange(10), 6)
    r = PA.ols_robust(y, x, tick, day)
    X = np.column_stack([np.ones(n), x])
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    assert (r["a"], r["b"]) == pytest.approx(tuple(beta), rel=1e-10)
    e = y - X @ beta
    bread = np.linalg.inv(X.T @ X)
    hc1 = np.sqrt(np.diag(bread @ (X * e[:, None] ** 2).T @ X @ bread) * n / (n - 2))
    assert (r["se_hc1"]["a"], r["se_hc1"]["b"]) == pytest.approx(tuple(hc1), rel=1e-10)
    s = np.stack([(X[tick == c] * e[tick == c, None]).sum(axis=0) for c in range(6)])
    cl = np.sqrt(np.diag(bread @ s.T @ s @ bread) * (6 / 5) * ((n - 1) / (n - 2)))
    assert (r["se_cluster_ticker"]["a"], r["se_cluster_ticker"]["b"]) == pytest.approx(tuple(cl), rel=1e-10)
    assert r["se_cluster_ticker"]["n_clusters"] == 6 and r["se_cluster_day"]["n_clusters"] == 10


def test_spearman_and_std_ratio():
    x = [1.0, 2.0, 2.0, 3.0, np.nan, 5.0]
    y = [10.0, 20.0, 30.0, 25.0, 1.0, 50.0]
    got = PA.spearman(x, y)
    want = np.corrcoef([1.0, 2.5, 2.5, 4.0, 5.0], [1.0, 2.0, 4.0, 3.0, 5.0])[0, 1]     # average ranks, NaN row dropped
    assert got["n"] == 5 and got["rho"] == pytest.approx(want, rel=1e-12)
    assert PA.spearman([1.0, 2.0], [2.0, 1.0]) == {"rho": None, "n": 2}
    sr = PA.std_ratio([0.0, 2.0, 4.0], [0.0, 1.0, 2.0])
    assert sr["ratio"] == pytest.approx(2.0) and sr["n"] == 3


def test_no_forbidden_platform_name():
    """The name of the early public trading platform appears nowhere in this analysis' files (names or contents,
    parquet values decoded)."""
    bad = bytes.fromhex("6465657066756e64")
    files = [PA.__file__, __file__, *sorted(PA.DATA_DIR.iterdir()), *sorted(PA.OUT_DIR.iterdir())]
    for f in map(str, files):
        assert bad not in f.lower().encode(), f
        raw = open(f, "rb").read()
        if f.endswith(".gz"):
            raw = gzip.decompress(raw)
        assert bad not in raw.lower(), f
        if f.endswith(".parquet"):
            df = pd.read_parquet(f)
            text = " ".join(map(str, df.columns)) + " " + " ".join(
                df[c].astype(str).str.cat(sep=" ") for c in df.columns if df[c].dtype == object or str(df[c].dtype).startswith("str"))
            assert bad.decode() not in text.lower(), f
