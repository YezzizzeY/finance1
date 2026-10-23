"""One harness run: the day's session for one (model, day, arm, k), written as session.json.gz + record.json.

The run starts from the saved anchor state of the day, on a fresh view of the stock's point-in-time cache, with the 32 tools.
The arm enters through two hooks of the session: the readings block in the arm's form is inserted before the prompt's final line,
and every output of one of the seven block tools is rewritten into the arm's form, before the tool-result cut.
"""
from __future__ import annotations

import time
import traceback
from concurrent.futures import ThreadPoolExecutor

from finagent import arms, config, readings, records
from finagent.data.anchors import anchor_state
from finagent.data.outcomes import Outcomes
from finagent.data.pit import news_cache
from finagent.harness import providers, session
from finagent.harness.prompts import SYSTEM, harness_prompt, harness_tools


def new_context(arm: str, day: dict) -> dict:
    """The run's context: the arm's block, hook counters and (filled by the chat) the request log."""
    return {"arm": arm, "date": day["t"], "ticker": day["ticker"],
            "block": arms.rewrite_block(readings.registered_block(day["day_id"]), arm),
            "prompts_rendered": 0, "block_tool_calls": 0, "block_tool_outputs_rewritten": 0, "requests": []}


def arm_hooks(ctx: dict):
    """(prompt_hook, tool_output_hook) of the session, counting what they change in ctx."""
    def prompt_hook(prompt: str) -> str:
        ctx["prompts_rendered"] += 1
        return readings.insert_block(prompt, ctx["block"])

    def tool_output_hook(name: str, out: str) -> str:
        if name not in arms.BLOCK_TOOLS:
            return out
        new = arms.rewrite_output(name, out, ctx["arm"])
        ctx["block_tool_calls"] += 1; ctx["block_tool_outputs_rewritten"] += new != out
        return new
    return prompt_hook, tool_output_hook


def _tokens(reqs: list[dict]) -> dict:
    def total(k):
        return sum(r.get(k) or 0 for r in reqs) if any(r.get(k) is not None for r in reqs) else None
    return {"input": total("input"), "output": total("output"), "reasoning": total("reasoning"), "cached": total("cached"),
            "requests": len(reqs)}


def make_record(r: dict, day: dict, step: dict | None, trace: list[dict], ctx: dict, err: str | None, wall_s: float,
                extra: dict | None = None) -> dict:
    """The record of a finished session; verify rebuilds every shipped harness record from its session.json.gz with it."""
    prompt_ok = bool(trace) and trace[0].get("user") == harness_prompt(day, r["arm"]) and trace[0].get("system") == SYSTEM
    dec = (step or {}).get("decision") or None
    decision, valid = records.parse_decision(dec)
    calls = [e["tool"] for e in trace if "tool" in e]
    served = sorted({q.get("model") for q in ctx["requests"] if q.get("model")})
    return {**r, "model_id": config.MODELS[r["model"]]["model_id"], "model_served": served, "framework_label": "harness",
            "decision": decision, "decision_raw": dec, "decision_valid": valid, "n_tool_calls": len(calls), "tool_names": calls,
            "n_turns": sum(1 for e in trace if "turn" in e), "tokens": _tokens(ctx["requests"]),
            "wall_s": round(wall_s, 1), "prompt_identical_to_builder": prompt_ok, "block_inserted": ctx["prompts_rendered"],
            "block_tool_calls": ctx["block_tool_calls"], "block_tool_outputs_rewritten": ctx["block_tool_outputs_rewritten"],
            "finish_per_request": [q.get("finish") for q in ctx["requests"]],
            "leakage": {"flag": False, "reasons": [],
                        "note": "harness: only the point-in-time toolbox; no file or network access"},
            "outcome_not_shown": {"real5_pct": (step or {}).get("real5"), "rv5": (step or {}).get("rv5")},
            "error": err, **(extra or {})}


def run(r: dict, day: dict, outcomes: Outcomes, store: records.RunStore, extra: dict | None = None) -> dict:
    """Run r (a row of records.runs) on its day and write it to the store; extra: fields appended to the record
    (records.serving_fields)."""
    tools = harness_tools()
    st = anchor_state(day["day_id"])
    view = news_cache(day["ticker"]).view()
    ctx = new_context(r["arm"], day)
    chat = providers.make_chat(r["model"], ctx)
    prompt_hook, tool_output_hook = arm_hooks(ctx)
    trace, err, tb, step = [], None, None, None
    t0 = time.time()
    try:
        step = session.day_step(chat, outcomes, day["ticker"], view, tools, st, day["t"], r["seed"], trace=trace,
                                prompt_hook=prompt_hook, tool_output_hook=tool_output_hook)
    except Exception as e:                                                    # noqa: BLE001  (recorded, the batch goes on)
        err = f"{type(e).__name__}: {e}"; tb = traceback.format_exc()[-3000:]
    wall = time.time() - t0
    records.dump_gz({"run": r, "step": step, "trace": trace, "ctx": ctx, "cache_log": view.log, "error": err, "traceback": tb},
                    store.run_dir(r["run_id"]) / "session.json.gz")
    rec = make_record(r, day, step, trace, ctx, err, wall, extra)
    store.write(rec)
    return rec


def run_batch(run_list: list[dict], days: dict[str, dict], store: records.RunStore, workers: int, extra: dict | None = None) -> list[dict]:
    """The runs not yet done in the store, `workers` sessions at a time; days: {day_id: day}."""
    outcomes = Outcomes({days[r["day_id"]]["ticker"] for r in run_list})
    todo = [r for r in run_list if not store.done(r["run_id"])]
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(todo) or 1))) as ex:
        return list(ex.map(lambda r: run(r, days[r["day_id"]], outcomes, store, extra), todo))
