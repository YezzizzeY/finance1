"""finagent.mechanisms.proximity: build() reproduces the shipped results/mechanisms/proximity/data.json byte for byte and
deterministically; the closed-form statistics hit their reference values; the claims the prose makes hold."""
from __future__ import annotations

import json
import math
import re

import pytest

from finagent import config
from finagent.mechanisms import proximity
from finagent.mechanisms import proximity_stats as st

SHIPPED = config.RESULTS / "mechanisms" / "proximity" / "data.json"


@pytest.fixture(scope="module")
def built() -> dict:
    return proximity.build()


def test_build_reproduces_shipped_data_json(built):
    assert proximity.dumps(built) == SHIPPED.read_text(encoding="utf-8")
    assert built == json.loads(SHIPPED.read_text(encoding="utf-8"))


def test_main_is_deterministic(built, tmp_path):
    for name in ("a", "b"):
        assert proximity.main(["--out", str(tmp_path / name)]) == 0
    a, b = (tmp_path / "a" / "data.json").read_bytes(), (tmp_path / "b" / "data.json").read_bytes()
    assert a == b == SHIPPED.read_bytes() == proximity.dumps(built).encode("utf-8")


def test_sample_accounting_adds_up(built):
    s = built["sample_accounting"]
    assert s["files_attempted"] == s["n_usable_part1_2"] + sum(s["skip_reasons"].values()) == 1000
    assert s["n_usable_part1_2"] == s["n_is_last_true"] + s["n_is_last_false"] == 754
    assert len(s["matched_day_ids"]) == s["n_days_with_both_is_last_groups"] == 128
    s2 = built["step2_results"]
    assert s2["is_last_true"]["n"] + s2["is_last_false"]["n"] == s["n_sessions_in_those_matched_days"] == 420
    fe = s2["within_day_fixed_effects_level_test"]["fe_regression"]
    assert (fe["n_obs"], fe["n_days"], fe["df"]) == (420, 128, 418)
    assert all(e["file"].startswith(proximity.SESSIONS_REL + "/") for x in built["examples"] for e in x["sessions"])


def test_statistics_reference_values(built):
    assert round(st.student_t_pvalue_two_sided(2.228, 10), 4) == 0.0500
    assert round(st.student_t_pvalue_two_sided(1.96, 1000), 4) == 0.0503
    assert st.student_t_pvalue_two_sided(0.0, 50) == pytest.approx(1.0)
    assert abs(st.binomial_test_exact(15, 20) - 0.04139) < 5e-6
    lo, hi = st.wilson_ci(15, 20)
    assert lo < 0.75 < hi
    for key in ("is_last_true", "is_last_false"):         # t of the slope equals the t implied by Pearson r
        f = built["step2_results"][key]
        assert f["slope"] / f["slope_se"] == pytest.approx(f["r"] * math.sqrt(f["df"] / (1 - f["r"] ** 2)), rel=1e-9)


def test_fixed_effects_note_holds_at_the_correct_df(built):
    """The 2026-10-23 note: with df = n - days - 1 (291) instead of n - 2 (418) the level test stays far from significant."""
    fe = built["step2_results"]["within_day_fixed_effects_level_test"]["fe_regression"]
    df = fe["n_obs"] - fe["n_days"] - 1
    se = fe["se"] * math.sqrt(fe["df"] / df)
    assert df == 291 and se > fe["se"]
    assert st.student_t_pvalue_two_sided(fe["coef_is_last"] / se, df) > 0.5
    assert "291" in built["_notes_added_2026-10-23"][0]


def test_a_broken_prose_claim_stops_the_build():
    proximity._check("anything", 1, 1)
    with pytest.raises(RuntimeError):
        proximity._check("anything", 1, 2)


def test_outputs_carry_no_host_paths_or_removed_names():
    removed = bytes.fromhex("6465657066756e64").decode()
    host_path = re.compile(r"(?<![\w.])/(srv|home|tmp|Users|root|mnt)/")
    files = [SHIPPED, SHIPPED.with_name("README.md"), config.DATA / "mechanisms" / "proximity" / "README.md",
             config.ROOT / "src" / "finagent" / "mechanisms" / "proximity.py",
             config.ROOT / "src" / "finagent" / "mechanisms" / "proximity_stats.py"]
    for f in files:
        text = f.read_text(encoding="utf-8")
        assert removed not in text.lower() and not host_path.search(text), f
