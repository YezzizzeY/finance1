"""Unit tests against the golden fixtures (tests/fixtures/README.md): what the original pilot code produced for the same inputs.

Tool outputs per tool, the harness session loop and its requests per model and scenario, the providers' retry rules, and the
Codex config text per model. No network: every model reply comes from the fixture (conftest.FakeTransport).
"""
from __future__ import annotations

import json
from functools import cache
from pathlib import Path

import pytest

from finagent import config, records, verify
from finagent.coding import codex, workspace
from finagent.data.outcomes import Outcomes
from finagent.harness import agent, providers, session
from finagent.harness.prompts import SYSTEM, harness_tools

TOOLS = verify.fixture("golden_tools.json.gz")
SESSIONS = verify.fixture("golden_session.json.gz")
REQUESTS = verify.fixture("golden_requests.json")
CODEX = verify.fixture("golden_codex_configs.json")
RECORD_TIMING = ("wall_s", "finished_epoch")
# set by the installed requests / urllib3 (and brotli, zstd), not by our code
TRANSPORT_HEADERS = ("User-Agent", "Accept-Encoding")


@cache
def outcomes() -> Outcomes:
    return Outcomes({d["ticker"] for d in verify.pilot_days().values()})


# ================================================================================================== tools
@pytest.mark.parametrize("tool", sorted({c["tool"] for c in TOOLS["calls"]}))
def test_tool_outputs(tool):
    days = verify.pilot_days()
    for c in (c for c in TOOLS["calls"] if c["tool"] == tool):
        state = verify.fresh_state(c["day_id"])["tb_state"]
        out = verify.call_tool(days[c["day_id"]], c["arm"], tool, c["args"], state)
        where = (c["day_id"], c["arm"], c["args"])
        assert out == c["output_raw"], where
        assert out[:verify.CUT] == c["output_cut"], where
        assert state == c.get("state_after", verify.fresh_state(c["day_id"])["tb_state"]), where


@pytest.mark.parametrize("seq", TOOLS["sequences"], ids=lambda s: f"{s['day_id']}-{s['arm']}")
def test_stateful_sequence(seq):
    day, state = verify.pilot_days()[seq["day_id"]], verify.fresh_state(seq["day_id"])["tb_state"]
    for c in seq["calls"]:
        assert verify.call_tool(day, seq["arm"], c["tool"], c["args"], state) == c["output_raw"], (c["tool"], c["args"])
    assert state == seq["state_after"]


def test_submit_replies():
    for e in TOOLS["submit_echoes"]:
        day = verify.pilot_days()[e["day_id"]]
        reply = session.submit_reply(e["args"], verify.fresh_state(e["day_id"])["portfolio"], verify.close_price(day))
        assert reply == e["echo"], (e["day_id"], e["args"])


# ================================================================================================== harness sessions
def golden_runs() -> list:
    runs = SESSIONS["sessions"] + SESSIONS["edge_cases"] + REQUESTS["conversations"]
    return [pytest.param(g, id=f"{g['model']}-{g.get('scenario', 'conversation')}-{g['day_id']}-{g['arm']}") for g in runs]


def without_transport_headers(request: dict) -> dict:
    return {**request, "headers": {k: v for k, v in request["headers"].items() if k not in TRANSPORT_HEADERS}}


@pytest.mark.parametrize("g", golden_runs())
def test_harness_session(g, fake_http, tmp_path):
    fake_http.load([e["response"] for e in g["exchanges"]])
    store = records.RunStore(tmp_path / "raw")
    with config.host_env(config.RECORDED_HOST_ENV):
        agent.run(g["run"], verify.pilot_days()[g["day_id"]], outcomes(), store,
                  records.serving_fields(g["model"], "harness", 65536, 0))
    assert [without_transport_headers(q) for q in fake_http.sent] == \
        [without_transport_headers(e["request"]) for e in g["exchanges"]]
    run_dir = store.run_dir(g["run"]["run_id"])
    rec = json.loads((run_dir / "record.json").read_text())
    assert [(k, v) for k, v in rec.items() if k not in RECORD_TIMING] == list(g["record"].items())
    ses = records.load_gz(run_dir / "session.json.gz")
    for q in ses["ctx"]["requests"]:
        del q["s"]
    for q in ses["ctx"].get("raw_responses", []):
        del q["t"]
    assert {k: ses[k] for k in g["session"]} == g["session"]


class VirtualClock:
    """time for providers.py: only sleep() advances it."""

    def __init__(self):
        self.now, self.sleeps = 1.8e9, []

    def time(self) -> float:
        return self.now

    def sleep(self, s: float) -> None:
        self.sleeps.append(s)
        self.now += s


@pytest.mark.parametrize("r", REQUESTS["retries"], ids=lambda r: f"{r['model']}-{r['scenario']}")
def test_provider_retries(r, fake_http, monkeypatch):
    clock = VirtualClock()
    monkeypatch.setattr(providers, "time", clock)
    fake_http.load(r["replies"], r["repeat_last"])
    ctx = {"requests": []}
    with config.host_env(config.RECORDED_HOST_ENV):
        chat = providers.make_chat(r["model"], ctx)
        try:
            outcome = {"finish_reason": chat([{"role": "system", "content": SYSTEM}, {"role": "user", "content": "golden"}],
                                             harness_tools(), 1).get("finish_reason")}
        except Exception as e:                                                # noqa: BLE001  (the outcome under test)
            outcome = {"raised": f"{type(e).__name__}: {e}"}
    assert outcome == r["outcome"]
    assert (len(fake_http.sent), clock.sleeps) == (r["n_requests"], r["sleeps"])
    assert [{k: v for k, v in q.items() if k != "s"} for q in ctx["requests"]] == r["request_entries"]
    assert len(ctx.get("raw_responses", [])) == r["n_raw_responses"]


# ================================================================================================== Codex config
@pytest.mark.parametrize("c", CODEX["configs"], ids=lambda c: c["model"])
def test_codex_config(c):
    with config.host_env(config.RECORDED_HOST_ENV):
        f = workspace.run_folders(c["rid"])
        assert (str(f["home"]), str(f["tmp"]), config.host("AGENT_PATH")) == (c["home"], c["tmp"], c["agent_path"])
        assert config.port("RELAY", c["model"]) == c["relay_port"]
        text = codex.codex_config(c["model"], c["rid"], Path(c["home"]), Path(c["tmp"]), c["context_window"])
    assert text == c["codex_config_text"] == c["recorded_text"]
