"""The salience mechanism analysis: build() reproduces the shipped results/mechanisms/salience/data.json byte for
byte, a fresh process (other hash seed) writes the same bytes, and the pieces behave as the original scripts did.
CPU only, about 20 s: it reads the 6,000 saved session files the analysis scans (2,000 per corpus; the 1,000 FULL_T06
files are skipped by name) twice, once in this process and once in the subprocess."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys

import numpy as np
import pytest

from finagent import config
from finagent.mechanisms import salience as S


@pytest.fixture(scope="module")
def built() -> dict:
    return S.build()


def test_build_reproduces_shipped_data_json(built):
    assert S.dumps(built) == S.OUT_FILE.read_text(encoding="utf-8")


def test_main_is_deterministic_in_a_fresh_process(tmp_path):
    out = tmp_path / "data.json"
    env = {**os.environ, "PYTHONHASHSEED": "4242"}
    subprocess.run([sys.executable, "-m", "finagent.mechanisms.salience", "--out", str(out)], check=True, env=env,
                   cwd=config.ROOT, capture_output=True)
    assert out.read_bytes() == S.OUT_FILE.read_bytes()


def test_headline_counts(built):
    n = built["n_sessions_used"]
    assert (n["newsagent_FULL_primary"], n["newsagent_NO_NEWS"]) == (694, 751)
    assert (n["q3news_S1_FULL_crosscheck"], n["q3news_S1_NO_NEWS_crosscheck"]) == (155, 139)
    assert n["grounding_A_main_usable"] == 0
    assert built["corpora"]["primary"]["n_files_scanned_total"] == 2000
    assert sum(built["corpora"]["skipped_entirely"]["n_skipped_and_why"].values()) == 2000
    join = built["rational_benchmark_join"]["join_hit_rate"]
    assert (join["n_hit_total"], join["n_session_rows"], join["n_hit_via_nonevent_days_fallback"]) == (1739, 1739, 42)
    s3 = built["step3_copied_vs_not_copied"]
    splits = ("newsagent_FULL", "newsagent_NO_NEWS", "newsagent_FULL_plus_NO_NEWS_combined")
    assert [s3[k]["copied"]["n"] for k in splits] == [15, 12, 27]
    assert len(built["examples"]) == 6


def test_output_has_no_host_paths_or_non_json_numbers():
    text = S.OUT_FILE.read_text(encoding="utf-8")
    assert "NaN" not in text and "Infinity" not in text
    assert str(config.ROOT) not in text and not re.search(r'"/(srv|home|tmp)/', text)
    for ex in json.loads(text)["examples"]:
        assert (config.ROOT / ex["session_file"]).is_file()


def test_ols_fit_matches_lstsq():
    rng = np.random.default_rng(0)
    X = rng.normal(size=(200, 2))
    y = 1.5 + X @ np.array([0.7, -0.2]) + rng.normal(scale=0.5, size=200)
    m = S.ols_fit(X, y)
    beta = np.linalg.lstsq(np.column_stack([np.ones(200), X]), y, rcond=None)[0]
    assert np.allclose(m["beta"], beta) and m["dof"] == 197 and 0 < m["r2"] < 1


def test_extract_session_skip_reasons():
    full = {"action": "Hold", "shares": 0, "target_exposure_pct": 0, "p_up": 0.5, "expected_return_pct": 0.1,
            "expected_vol_pct": 3.2, "confidence": 0.5, "reasoning": "r"}
    vol = json.dumps({"ann_vol_10d_pct": 20, "ann_vol_20d_pct": 22.5, "ann_vol_60d_pct": 25,
                      "parkinson_vol_10d_pct": 21})
    sub = {"tool": "submit_decision", "args": full}
    assert S.extract_session({"trace": []}) == (None, "no_submit_decision")
    partial = {"tool": "submit_decision", "args": {"action": "Hold"}}
    assert S.extract_session({"trace": [partial]}) == (None, "submit_missing_fields")
    assert S.extract_session({"trace": [sub]}) == (None, "no_vol_stats_call")
    rec, err = S.extract_session({"trace": [{"tool": "get_volatility_stats", "result": vol}, sub]})
    assert err is None and rec == {"ann_vol_20d_pct": 22.5, "expected_vol_pct": 3.2}
