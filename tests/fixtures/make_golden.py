"""Regenerate the golden fixtures of this folder from the ORIGINAL pilot code (provenance; see README.md).

It imports the original project (its `repro/` code and `results/` data), which this repository replaces, so the tests never
run it. From the repository root (the script itself sets NEWSAGENT=1 TOOL_HORIZON=5d CUDA_VISIBLE_DEVICES= and puts $ORIG on
sys.path before importing the original code):

    $ORIG/.venv/bin/python -B tests/fixtures/make_golden.py $ORIG tests/fixtures

Offline by construction: requests' transport adapter is replaced by a scripted fake that records every exchange, socket
connects are refused, API keys are the dummy value DUMMY and the key-file readers raise, time runs on a virtual clock, and run
records are written to a temporary folder. Two runs write byte-identical files.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import socket
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import requests

ARMS = ("ORIG", "NOLABEL", "UNIT5D", "PLACEBO")
TIMING_FIELDS = ("wall_s", "finished_epoch")
TICKER = "<ticker>"            # placeholder in VARIANTS: the day's own ticker
ON_TARGET = "<on_target>"      # placeholder in ECHO_ARGS: today's exposure in percent, rounded (an on-target submission)
DUMMY_KEY = "DUMMY"

# argument variants beyond the default {}: every parameter of every tool, string-typed numbers, a tool error and an ignored
# argument on a block tool (the arm rewrite applies to every call of a block tool, whatever its arguments)
VARIANTS = {
    "get_daily_candles": [{"days": 5}, {"days": 60}, {"days": "5"}],
    "get_weekly_candles": [{"weeks": 4}],
    "get_monthly_candles": [{"months": 24}],
    "get_returns": [{"days": 5}],
    "get_rsi": [{"period": 7}, {"period": 14}, {"period": 21}, {"period": 0}],
    "get_volatility_stats": [{"days": 10}],
    "get_risk_budget": [{"target_vol_pct": 10}, {"target_vol_pct": 25}],
    "get_kelly_sizing": [{"expected_return_pct": 1.5, "expected_vol_pct": 6},
                         {"expected_return_pct": 1.5, "expected_vol_pct": 6, "risk_aversion": 16},
                         {"expected_return_pct": -0.4, "expected_vol_pct": 0}],
    "get_earnings_calendar": [{"ticker": TICKER}],
    "get_event_risk": [{"ticker": TICKER}],
    "get_news": [{"feed": "ticker"}, {"feed": "economy_fiscal"}, {"feed": "economy_monetary"}, {"days": 30}, {"limit": 5},
                 {"only_ticker": False}, {"feed": "ticker", "days": 3, "limit": 15, "only_ticker": True}],
    "search_news": [{"query": "earnings"}, {"query": "guidance"}, {"query": ""},
                    {"query": "earnings", "days": 7, "limit": 5}],
    "get_news_stats": [{"days": 30}],
    "get_macro_news": [{"days": 30}, {"limit": 3}],
    "get_insider_trades": [{"days": 365}, {"limit": 5}],
    "get_insider_summary": [{"days": 365}],
    "get_trade_history": [{"days": 5}],
    "simulate_order": [{"action": "Buy", "shares": 10}, {"action": "Sell", "shares": 3}, {"action": "Hold", "shares": 0},
                       {"target_exposure_pct": 40}, {"action": "Buy", "shares": 1000000}],
    "memory_read": [{"days": 3}, {"days": "30"}],
    "memory_write": [{"note": "x"}, {"note": ""}],
    "memory_search": [{"query": "buy"}, {"query": ""}],
}
UNKNOWN_CALLS = [("get_memory_read", {"days": "30"})]          # a misspelt tool one recorded session called
SEQUENCE = [("memory_write", {"note": "trim after big moves"}), ("memory_write", {"note": "second note"}),
            ("memory_search", {"query": "trim"}), ("memory_search", {"query": ""}), ("memory_read", {"days": 3}),
            ("simulate_order", {"action": "Buy", "shares": 10}), ("get_portfolio", {}), ("get_trade_history", {}),
            ("get_volatility_stats", {})]
ECHO_ARGS = [{"action": "Hold", "shares": 0}, {"action": "Hold", "shares": 0, "target_exposure_pct": ON_TARGET},
             {"action": "Hold", "shares": 0, "target_exposure_pct": 90}, {"action": "Buy", "shares": 10},
             {"action": "Buy", "shares": 10, "target_exposure_pct": 0},
             {"action": "Sell", "shares": 3, "target_exposure_pct": ON_TARGET}, {"action": "sell", "shares": "1000000"},
             {"action": "Buy", "shares": 1000000, "target_exposure_pct": 100}, {"action": "Hold", "target_exposure_pct": "50%"},
             {}]

DECISION = {"action": "Hold", "shares": 0, "target_exposure_pct": 30, "p_up": 0.55, "expected_return_pct": 0.8,
            "expected_vol_pct": 4.5, "confidence": 0.6, "reasoning": "golden decision"}


def turn(*calls, reasoning="", content=None, finish=None) -> dict:
    """One scripted model turn: tool calls as (name, arguments dict or raw argument string)."""
    finish = finish or ("tool_calls" if calls else "stop")
    return {"calls": list(calls), "reasoning": reasoning, "content": content, "finish": finish}


SUBMIT = ("submit_decision", DECISION)
SESSION_TURNS = [
    turn(("get_volatility_stats", {}), ("get_price_stats", {}), ("get_news", {"limit": 3}),
         reasoning="Volatility and news first."),
    turn(("simulate_order", {"action": "Buy", "shares": 5}), ("memory_write", {"note": "re-check volatility after the event"}),
         ("get_portfolio", {}), reasoning="Size the order."),
    turn(("submit_decision", {**DECISION, "action": "Buy", "shares": 5, "target_exposure_pct": 60}), ("get_risk_budget", {}),
         reasoning="Submit, then check the budget."),
    turn(SUBMIT, reasoning="Resubmit; the last submission wins."),
]
EDGE_TURNS = {
    "turn_cut_by_token_cap": [turn(reasoning="A long thought cut by the cap.", finish="length"), turn(SUBMIT)],
    "reminder_after_no_call": [turn(content="I would hold today."), turn(SUBMIT)],
    "gives_up_after_reminder": [turn(content="Holding."), turn(content="Still holding.")],
    "final_reminder_after_ten_turns": [turn(("get_portfolio", {})) for _ in range(10)] + [turn(SUBMIT)],
    "malformed_arguments": [turn(("get_rsi", "{not json"), ("memory_read", "[1, 2]"), ("get_returns", "")),
                            turn(("submit_decision", '"Hold"'))],
}
REQUEST_TURNS = [turn(("get_volatility_stats", {}), ("get_rsi", {"period": 14}), reasoning="Read volatility and RSI first."),
                 turn(SUBMIT, reasoning="Decide.")]
RETRY_SCENARIOS = {
    "ok": ([200], False),
    "busy_then_ok": ([429, 503, 200], False),
    "client_error_then_ok": ([400, 200], False),
    "client_error_three_times": ([400, 400, 400], False),
    "connection_error_then_ok": (["ConnectionError", 200], False),
    "unavailable_until_give_up": ([503], True),
}
REQUEST_MODELS = ("qwen3_8b", "qwen35_9b", "qwen38_27b", "deepseek", "kimi")


# ================================================================================================== offline plumbing
class VirtualClock:
    """time.time and time.sleep on a clock that only sleeping advances; every sleep is recorded."""

    def __init__(self, start: float = 1_800_000_000.0):
        self.now, self.sleeps = start, []

    def install(self) -> None:
        time.time = lambda: self.now
        time.sleep = self.sleep

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


class FakeHTTP:
    """The transport under requests: answers each request with the next scripted reply and records the exchange."""

    def __init__(self):
        self.replies, self.exchanges, self.repeat_last = [], [], False

    def load(self, replies: list[dict], repeat_last: bool = False) -> None:
        self.replies, self.exchanges, self.repeat_last = list(replies), [], repeat_last

    def send(self, request, timeout=None, **_):
        reply = self.replies[0] if self.repeat_last and len(self.replies) == 1 else self.replies.pop(0)
        headers = {k: "<redacted>" if k.lower() == "authorization" else v for k, v in request.headers.items()}
        body = request.body.decode() if isinstance(request.body, bytes) else request.body
        self.exchanges.append(entry(request=entry(method=request.method, url=request.url, headers=headers, timeout=timeout,
                                                  body=body), response=reply))
        if "error" in reply:
            raise requests.ConnectionError("golden: connection refused")
        r = requests.Response()
        r.status_code, r._content, r.encoding = reply["status"], reply["body"].encode(), "utf-8"
        r.url, r.request = request.url, request
        r.headers["Content-Type"] = "application/json"
        return r


def refuse_connect(*_):
    raise OSError("make_golden: network is disabled")


def no_key(*_):
    raise RuntimeError("make_golden: key files are never read")


def load_original(orig: Path) -> SimpleNamespace:
    """The original modules, imported with every route to the network, an API key or the original results closed."""
    os.environ.update(NEWSAGENT="1", TOOL_HORIZON="5d", CUDA_VISIBLE_DEVICES="", CXP_DEEPSEEK_API_KEY=DUMMY_KEY)
    for k in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY", "TOOL_PROMPT",
              "CXP_QWEN38_MAX_LEN"):
        os.environ.pop(k, None)
    socket.socket.connect = refuse_connect
    socket.socket.connect_ex = refuse_connect
    sys.path.insert(0, str(orig))
    from repro import codexpilot as P
    from repro import tool_traj as tt
    from repro import toolbox
    from repro.codexpilot import coding_agent as CA
    from repro.codexpilot import days as DY
    from repro.codexpilot import harness_agent as HA
    from repro.codexpilot import plan as PL
    from repro.codexpilot import prompt as PR
    from repro.codexpilot import rewrite as RW
    from repro.codexpilot import run_qwen38 as RQ
    from repro.newsagent import common as C
    P.KEYS_FILE = Path("/nonexistent")
    P.deepseek_key = P.kimi_key = no_key
    HA._KIMI["key"] = DUMMY_KEY
    http, clock = FakeHTTP(), VirtualClock()
    requests.adapters.HTTPAdapter.send = lambda self, request, **kw: http.send(request, **kw)
    clock.install()
    days = DY.load()["days"]
    return SimpleNamespace(P=P, tt=tt, toolbox=toolbox, CA=CA, HA=HA, PL=PL, PR=PR, RW=RW, RQ=RQ, C=C, http=http, clock=clock,
                           days=days, U=HA.universe({d["ticker"] for d in days}))


def sha(text: str | bytes) -> str:
    return hashlib.sha256(text if isinstance(text, bytes) else text.encode()).hexdigest()


def entry(**fields) -> dict:
    """A fixture record with its keys sorted; captured objects inside it keep the key order the original code produced."""
    return dict(sorted(fields.items()))


def harness_ctx(M, d: dict, arm: str) -> dict:
    """The per-session context harness_agent.run_openai installs (it switches the arm rewrite on)."""
    return {"arm": arm, "date": d["t"], "ticker": d["ticker"], "block": M.RW.rewrite_block(M.PR.registered_block(d), arm),
            "prompts_rendered": 0, "block_tool_calls": 0, "block_tool_outputs_rewritten": 0, "requests": [], "ds_reasoning": {}}


# ================================================================================================== scripted model
def reply_body(kind: str, model_id: str, n: int, t: dict) -> str:
    """The JSON text a provider (MODELS kind) answers for scripted turn `t` as its n-th reply, shaped like the real server's."""
    api = kind != "vllm"
    calls = [{**({"index": j} if api else {}), "id": f"call_{n}_{j}", "type": "function",
              "function": {"name": name, "arguments": args if isinstance(args, str) else json.dumps(args)}}
             for j, (name, args) in enumerate(t["calls"])]
    msg = {"role": "assistant", "content": t["content"]}
    if calls or not api:
        msg["tool_calls"] = calls
    msg["reasoning_content" if api else "reasoning"] = t["reasoning"]
    choice = {"index": 0, "message": msg, "finish_reason": t["finish"]}
    if not api:
        choice["token_ids"] = [n + 1, n + 2, n + 3]
        return json.dumps({"id": f"chatcmpl-golden-{n}", "object": "chat.completion", "model": model_id, "choices": [choice],
                           "prompt_token_ids": list(range(10 * n, 10 * n + 5)),
                           "usage": {"prompt_tokens": 5, "completion_tokens": 3, "total_tokens": 8}})
    usage = {"prompt_tokens": 1000 + n, "completion_tokens": 200 + n, "total_tokens": 1200 + 2 * n,
             "completion_tokens_details": {"reasoning_tokens": 150 + n}}
    if kind == "deepseek":
        usage.update(prompt_cache_hit_tokens=512, prompt_cache_miss_tokens=488 + n)
    else:
        usage.update(cached_tokens=256, prompt_tokens_details={"cached_tokens": 256, "cache_write_tokens": 128})
    return json.dumps({"id": f"chatcmpl-golden-{n}", "object": "chat.completion", "model": model_id, "choices": [choice],
                       "usage": usage})


def served_id(M, model: str) -> str:
    """The model name the provider reports (DeepSeek serves its alias deepseek-reasoner as deepseek-flash)."""
    return "deepseek-flash" if model == "deepseek" else M.P.MODELS[model]["model_id"]


def run_harness(M, model: str, d: dict, arm: str, turns: list[dict]) -> dict:
    """One harness run through the unchanged harness_agent.run_openai against scripted model turns."""
    r = next(x for x in M.PL.runs([d]) if (x["model"], x["framework"], x["arm"], x["k"]) == (model, "harness", arm, 0))
    kind = M.P.MODELS[model]["kind"]
    M.http.load([entry(status=200, body=reply_body(kind, served_id(M, model), n, t)) for n, t in enumerate(turns)])
    with tempfile.TemporaryDirectory() as tmp:
        M.P.RUNS = Path(tmp) / "raw"
        M.HA.run_openai(r, d, M.U)
        run = M.P.RUNS / r["run_id"]
        record = json.loads((run / "record.json").read_text())
        session = M.C.load_gz(run / "session.json.gz")
    if M.http.replies:
        raise RuntimeError(f"{r['run_id']}: {len(M.http.replies)} scripted replies were not requested")
    for q in session["ctx"]["requests"]:
        q.pop("s")
    for q in session["ctx"].get("raw_responses", []):
        q.pop("t")
    return {"exchanges": M.http.exchanges, "record": {k: v for k, v in record.items() if k not in TIMING_FIELDS}, "run": r,
            "session": session}


# ================================================================================================== 1. expected hashes
def expected_hashes(M) -> dict:
    """Prompt, tool and input hashes, each cross-checked against the original registrations before it is written."""
    out_dir = M.P.OUT
    check = json.loads((out_dir / "prompt_check.json").read_text())
    texts = {"harness_system": M.PR.system_prompt(), "coding_system": M.PR.coding_system_text(),
             "agent_prompt": M.PR.AGENT_PROMPT, "permissions": M.CA.PERMISSIONS_TEXT, "reminder": M.tt.REMINDER}
    if (sha(texts["harness_system"]), sha(texts["coding_system"])) != (check["system_sha256"], check["coding_system_sha256"]):
        raise RuntimeError("system prompts differ from prompt_check.json")
    tools = M.HA.tools_checked()
    from_check, blocks, days = {}, json.loads(M.P.GROUNDING_BLOCKS.read_text()), {}
    for d in M.days:
        e = check["days"][d["day_id"]]
        from_check.update({f"{d['day_id']}/{k}": v for k, v in e["file_sha256"].items()})
        for arm, a in e["arms"].items():
            from_check[f"{d['day_id']}/{arm}/harness_prompt.txt"] = a["harness_prompt_sha256"]
            from_check[f"{d['day_id']}/{arm}/task.md"] = a["task_md_sha256"]
        block = blocks[d["day_id"]]
        cache = M.PR.cache_of(d["ticker"])
        anchor = (M.P.PROJ / d["anchor_file"]).read_bytes()
        if sha(block["block"]) != block["sha256"] or sha(anchor) != d["anchor_sha256"]:
            raise RuntimeError(f"{d['day_id']}: block or anchor hash differs from its registration")
        if cache.decision_time(datetime.strptime(d["t"], "%Y-%m-%d")) != d["D"]:
            raise RuntimeError(f"{d['day_id']}: decision time differs from days.json")
        by_arm = entry(**{arm: sha(M.RW.rewrite_block(block["block"], arm)) for arm in ARMS})
        days[d["day_id"]] = entry(anchor_sha256=d["anchor_sha256"], block_sha256=block["sha256"], block_sha256_by_arm=by_arm,
                                  decision_time=d["D"], t=d["t"], ticker=d["ticker"])
    examples = {str(p.relative_to(out_dir / "examples")): sha(p.read_bytes())
                for p in sorted((out_dir / "examples").rglob("*")) if p.is_file()}
    if examples != from_check or len(examples) != 66:
        raise RuntimeError("examples/ files differ from the hashes in prompt_check.json")
    prompts = {(d["day_id"], arm): M.PR.harness_prompt(d, arm) for d in M.days for arm in ARMS}
    rc, rc_saved = M.RW.check_all(M.days, prompts), json.loads((out_dir / "rewrite_check.json").read_text())
    if (rc["n_checks"], rc["n_with_problems"]) != (rc_saved["n_checks"], rc_saved["n_with_problems"]):
        raise RuntimeError("rewrite check differs from rewrite_check.json")
    return entry(days=entry(**days), examples=examples, n_tools=len(tools),
                 rewrite_check=entry(n_checks=rc["n_checks"], n_with_problems=rc["n_with_problems"]),
                 texts=entry(**{k: entry(chars=len(v), sha256=sha(v)) for k, v in texts.items()}),
                 tools_sha256=sha(json.dumps(tools, sort_keys=True)))


# ================================================================================================== 2. golden tools
def tool_calls(M, d: dict) -> list[tuple[str, dict]]:
    """Every non-submit tool with {} and its VARIANTS, in toolbox order, then UNKNOWN_CALLS."""
    names = [t["function"]["name"] for t in M.toolbox.build_tools("full") if t["function"]["name"] != "submit_decision"]
    calls = [(n, a) for n in names for a in [{}] + VARIANTS.get(n, [])]
    return [(n, {k: d["ticker"] if v == TICKER else v for k, v in a.items()}) for n, a in calls] + UNKNOWN_CALLS


def call_tool(M, d: dict, arm: str, name: str, args: dict, state: dict) -> dict:
    """One tool call exactly as one_session makes it: the installed run_tool wrapper (arm rewrite), then the result cut."""
    M.HA.TL.ctx = harness_ctx(M, d, arm)
    try:
        raw = M.toolbox.run_tool(M.PR.cache_of(d["ticker"]).view("FULL", d["t"]), datetime.strptime(d["t"], "%Y-%m-%d"), name,
                                 dict(args), state)
    finally:
        M.HA.TL.ctx = None
    return entry(args=args, output_cut=raw[:M.tt.TOOL_RESULT_CHARS], output_raw=raw, tool=name)


def submit_echo(M, d: dict, args: dict) -> str:
    """The reply one_session gives to submit_decision(args): a one-turn harness run."""
    run = run_harness(M, "qwen3_8b", d, "ORIG", [turn(("submit_decision", args))])
    return next(e["result"] for e in run["session"]["trace"] if e.get("tool") == "submit_decision")


def on_target(M, d: dict) -> int:
    """Today's exposure of the anchor book in percent, rounded: a target_exposure_pct the echo calls on target."""
    st = M.PR.anchor_state(d)
    price = M.PR.cache_of(d["ticker"]).tool_bars(datetime.strptime(d["t"], "%Y-%m-%d"))[-1]["close"]
    p = st["portfolio"]
    return round(p["shares"] * price / (p["cash"] + p["shares"] * price) * 100)


def golden_tools(M) -> dict:
    """Every tool call variant on a fresh anchor state, the stateful sequences and the submit_decision echoes."""
    M.HA.install()
    calls, sequences, echoes = [], [], []
    for d in M.days:
        for name, args in tool_calls(M, d):
            for arm in ARMS:
                state = M.PR.anchor_state(d)["tb_state"]
                fresh = json.dumps(state)
                e = entry(arm=arm, day_id=d["day_id"], **call_tool(M, d, arm, name, args, state))
                calls.append(e if json.dumps(state) == fresh else entry(**e, state_after=state))
        for arm in ARMS:
            state = M.PR.anchor_state(d)["tb_state"]
            sequences.append(entry(arm=arm, calls=[call_tool(M, d, arm, n, a, state) for n, a in SEQUENCE], day_id=d["day_id"],
                                   state_after=state))
        target = on_target(M, d)
        for args in ECHO_ARGS:
            a = {k: target if v == ON_TARGET else v for k, v in args.items()}
            echoes.append(entry(args=a, day_id=d["day_id"], echo=submit_echo(M, d, a)))
    return entry(calls=calls, sequences=sequences, submit_echoes=echoes, tool_result_chars=M.tt.TOOL_RESULT_CHARS)


# ================================================================================================== 3. golden requests
def retry_case(M, model: str, statuses: list, repeat_last: bool) -> dict:
    """One provider call (harness_agent.chat) against a sequence of HTTP outcomes, on the virtual clock."""
    m = M.P.MODELS[model]
    url = m["kind"] if m["kind"] != "vllm" else f"http://127.0.0.1:{m['port']}"          # as run_openai builds it
    ok = reply_body(m["kind"], served_id(M, model), 0, turn(SUBMIT))
    replies = [entry(error=s) if isinstance(s, str) else entry(status=s, body=ok if s == 200 else f'{{"error": "golden {s}"}}')
               for s in statuses]
    M.http.load(replies, repeat_last)
    M.clock.sleeps = []
    ctx = harness_ctx(M, M.days[0], "ORIG")
    M.HA.TL.ctx = ctx
    try:
        ch = M.HA.chat(url, m["model_id"], [{"role": "system", "content": M.tt.SYSTEM}, {"role": "user", "content": "golden"}],
                       M.HA.tools_checked(), 1)
        outcome = entry(finish_reason=ch.get("finish_reason"))
    except Exception as e:                                                    # noqa: BLE001  (the outcome being recorded)
        outcome = entry(raised=f"{type(e).__name__}: {e}")
    finally:
        M.HA.TL.ctx = None
    return entry(model=model, n_requests=len(M.http.exchanges), n_raw_responses=len(ctx.get("raw_responses", [])),
                 outcome=outcome, repeat_last=repeat_last, replies=replies,
                 request_entries=[{k: v for k, v in q.items() if k != "s"} for q in ctx["requests"]], sleeps=M.clock.sleeps)


def golden_requests(M) -> dict:
    """One short conversation per model (the exact HTTP requests) and the retry rules of the three provider clients."""
    d = next(x for x in M.days if x["day_id"] == "VST_2026-05-06")
    conversations = []
    for model in REQUEST_MODELS:
        if model == "qwen38_27b":                                             # run_qwen38 batch --max-tokens 8192
            M.RQ.STATE["max_tokens"] = 8192
            M.RQ.install_extras(0)
        run = run_harness(M, model, d, "UNIT5D", REQUEST_TURNS)
        conversations.append(entry(arm="UNIT5D", day_id=d["day_id"], model=model, **run))
    retries = [entry(scenario=name, **retry_case(M, model, statuses, repeat))
               for model in ("qwen3_8b", "deepseek", "kimi") for name, (statuses, repeat) in RETRY_SCENARIOS.items()]
    return entry(conversations=conversations, retries=retries)


# ================================================================================================== 4. golden sessions
def golden_session(M) -> dict:
    """Full scripted harness runs: every day for ORIG and UNIT5D, plus the session loop's edge cases on one day."""
    sessions = [entry(arm=arm, day_id=d["day_id"], model="qwen3_8b", scenario="tools_then_submit",
                      **run_harness(M, "qwen3_8b", d, arm, SESSION_TURNS)) for d in M.days for arm in ("ORIG", "UNIT5D")]
    d = next(x for x in M.days if x["day_id"] == "VST_2026-05-06")
    edges = [entry(arm="ORIG", day_id=d["day_id"], model="qwen3_8b", scenario=name,
                   **run_harness(M, "qwen3_8b", d, "ORIG", turns)) for name, turns in EDGE_TURNS.items()]
    return entry(edge_cases=edges, sessions=sessions)


# ================================================================================================== 5. codex configs
def golden_codex_configs(M) -> dict:
    """codex_config() inputs, output and the recorded file for the first ORIG run of each model; all 150 must regenerate."""
    configs, n_same = [], 0
    for run in sorted(M.P.OUT.glob("raw/*__coding_agent__*")):
        key = run.name.split("__")[0]
        if key not in REQUEST_MODELS:
            continue
        rid = json.loads((run / "record.json").read_text())["workspace_name"]
        home, tmp = M.P.WS_ROOT / rid / "home", M.P.WS_ROOT / rid / "tmp"
        text, recorded = M.CA.codex_config(key, rid, home, tmp), (run / "codex_config.toml").read_text()
        n_same += text == recorded
        if run.name == f"{key}__coding_agent__{M.days[0]['day_id']}__ORIG__0":
            m = M.P.MODELS[key]
            configs.append(entry(agent_path=M.P.AGENT_PATH, codex_config_text=text, context_window=M.CA.CONTEXT_WINDOW[key],
                                 home=str(home), label=m["label"], model=key, model_id=m["model_id"],
                                 reasoning_effort=m.get("codex_reasoning_effort", "high"), recorded_text=recorded,
                                 relay_port=M.P.RELAY_PORTS[key], rid=rid, run_id=run.name, tmp=str(tmp),
                                 ws_root=str(M.P.WS_ROOT)))
    if n_same != 150 or len(configs) != len(REQUEST_MODELS):
        raise RuntimeError(f"codex_config() reproduces {n_same} of the 150 recorded configs")
    return entry(configs=sorted(configs, key=lambda e: REQUEST_MODELS.index(e["model"])), n_recorded_identical=n_same)


# ================================================================================================== output
def write(path: Path, obj) -> None:
    """Indented UTF-8 JSON; a .gz file is gzipped without a file name or time stamp, so the bytes are reproducible."""
    data = (json.dumps(obj, indent=1, ensure_ascii=False) + "\n").encode()
    if path.suffix == ".gz":
        with open(path, "wb") as f, gzip.GzipFile(filename="", mode="wb", fileobj=f, mtime=0, compresslevel=9) as gz:
            gz.write(data)
    else:
        path.write_bytes(data)
    print(f"{path.name}: {path.stat().st_size:,} bytes")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("orig", type=Path, help="the original project folder")
    ap.add_argument("out", type=Path, help="this folder (tests/fixtures)")
    a = ap.parse_args()
    M = load_original(a.orig.resolve())
    write(a.out / "expected_hashes.json", expected_hashes(M))
    write(a.out / "golden_tools.json.gz", golden_tools(M))
    write(a.out / "golden_session.json.gz", golden_session(M))
    write(a.out / "golden_codex_configs.json", golden_codex_configs(M))
    write(a.out / "golden_requests.json", golden_requests(M))              # last: it installs run_qwen38's extras


if __name__ == "__main__":
    main()
