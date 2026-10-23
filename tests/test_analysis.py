"""`finagent analyze --raw DIR --out DIR2` on new runs: the measures of one cell alone equal that cell in results/ (needs the
unpacked records)."""
from __future__ import annotations

import json

import pytest

from finagent import analysis, config
from finagent.analysis.reasoning import LABEL
from finagent.analysis.report import FW_LABEL


@pytest.mark.parametrize("model, framework", [("kimi", "coding_agent"), ("qwen3_8b", "harness")])
def test_measures_of_one_cell(model, framework, tmp_path):
    if not config.RAW.is_dir():
        pytest.skip("records/raw is missing: run `finagent unpack` first")
    for run in config.RAW.glob(f"{model}__{framework}__*"):
        (tmp_path / run.name).symlink_to(run)
    out = analysis.measures(tmp_path)
    got, want = (json.loads(text) for text in (out["describe.json"], (config.RESULTS / "describe.json").read_text()))
    assert [(c["model"], c["framework"]) for c in got["cells"]] == [(model, framework)]
    assert got["cells"][0] == next(c for c in want["cells"] if (c["model"], c["framework"]) == (model, framework))
    assert (got["days"], got["baselines"]) == (want["days"], want["baselines"])
    metrics = json.loads((config.RESULTS / "describe_reasoning_models.json").read_text())
    cell = [r for r in metrics if (r["model"], r["framework"]) == (LABEL[model], FW_LABEL[framework])]
    assert [r for r in json.loads(out["describe_reasoning_models.json"]) if not r["model"].startswith("baseline")] == cell
