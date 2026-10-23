"""Run records and the pilot's counts: runs, valid decisions, failures, leakage exclusions, token use, GPU-hours.

load_records() reads the run folders (records/raw by default); flag_kind() is the leakage-flag classification used by the
usable rule and its sensitivity check; counts() is the content of results/pilot_counts.json (port of pilot_report.py).
"""
from __future__ import annotations

import datetime as dt
import json
import re
import statistics as stt
from collections import defaultdict
from pathlib import Path

from finagent import config
from finagent.records import runs

INFRA = config.RECORDS / "infra"
FW_LABEL = {"harness": "harness", "coding_agent": "Codex CLI"}

# Codex 0.162.1 puts its bundled helpers (rg) on the command PATH from this folder of its package ("pathDir" of the package's
# codex-package.json), wherever the package is installed
CODEX_TOOL_DIR = "/codex-path/"

# The first start of the Qwen3-8B server (records/infra/logs/pilot_log.txt, 14:51:55) left no launch record: another user's job took the free memory
# before vLLM's own check and the server exited at start-up; it was retried on GPU 2.
FAILED_STARTS = [{"key": "qwen3_8b", "gpu_index": 0, "from": "2026-10-18 14:51:55", "to": "2026-10-18 14:52:36",
                  "note": "exited during start-up (free memory taken by another user's process); retried on GPU 2"}]


def load_records(raw: Path = config.RAW) -> dict[str, dict]:
    """run_id -> record.json of every run folder of the five models under raw/, in run_id order."""
    out = {}
    for f in sorted(Path(raw).glob("*/record.json")):
        r = json.loads(f.read_text(encoding="utf-8"))
        if r["model"] in config.MODELS:
            out[r["run_id"]] = r
    return out


def flag_kind(x: dict) -> str | None:
    """None if not flagged; 'codex_bundled_tool_only' if the only reason is that a model command executed a helper binary that Codex
    itself puts on the command PATH (its bundled ripgrep; the files searched were in the workspace); otherwise 'other'.
    The registered rule excludes every flagged run; the sensitivity check re-admits only the first kind."""
    lk = x.get("leakage") or {}
    if not lk.get("flag"):
        return None
    rs = lk.get("reasons") or []
    n = (lk.get("counts") or {}).get("paths_outside", 0)
    if len(rs) == 1 and rs[0].startswith("path:") and 0 < n <= 8:
        items = re.findall(r"\{'pid': \d+, 'call': '([a-z0-9]+)', 'path': '([^']*)'", rs[0])
        if len(items) == n and all(c == "execve" and CODEX_TOOL_DIR in pth for c, pth in items):
            return "codex_bundled_tool_only"
    return "other"


def gpu_hours(infra: Path = INFRA) -> dict:
    """Wall-clock hours each of our vLLM servers held a GPU, start to stop: launch/pilot1_* (main run), pilot2_* (rerun of 24
    Qwen3-8B Codex runs), qwen38_launches.jsonl (one line per Qwen3.8-27B launch; its one launch also served its 2 smoke runs,
    see logs/qwen38_log.txt), plus the failed start above. The smoke-stage launches of the other two models are not counted."""
    launches = [(f.name, json.loads(f.read_text())) for f in sorted((infra / "launch").glob("pilot*_launch_*.json"))]
    with open(infra / "launch" / "qwen38_launches.jsonl", encoding="utf-8") as f:
        launches += [("qwen38_launches.jsonl", {"key": "qwen38_27b", **json.loads(ln)}) for ln in f if ln.strip()]
    sessions = []
    for name, st in launches:
        end = st.get("stopped")
        sessions.append({"file": name, "key": st["key"], "gpu_index": st["gpu"]["index"],
                         "gpu_memory_utilization": st["gpu"]["util"], "hours": round((end - st["started"]) / 3600, 3) if end else None})
    for x in FAILED_STARTS:
        a, b = (dt.datetime.strptime(x[k], "%Y-%m-%d %H:%M:%S") for k in ("from", "to"))
        sessions.append({"file": None, "key": x["key"], "gpu_index": x["gpu_index"], "gpu_memory_utilization": None,
                         "hours": round((b - a).total_seconds() / 3600, 3), "note": x["note"]})
    return {"sessions": sessions, "total_gpu_hours_held": round(sum(s["hours"] or 0 for s in sessions), 3)}


def relay_usage(log: Path, workspaces: set[str]) -> dict:
    """Requests and tokens of one model's Codex runs, from its relay request log (lines matched by the run header)."""
    tok = {"requests": 0, "input": 0, "output": 0, "reasoning": 0, "cached": 0, "errors": 0, "status": defaultdict(int)}
    with open(log, encoding="utf-8") as f:
        lines = [json.loads(ln) for ln in f if ln.strip()]
    for q in lines:
        if q.get("run") not in workspaces:
            continue
        tok["requests"] += 1
        tok["status"][str(q.get("status"))] += 1
        tok["errors"] += q.get("status") != 200
        u = q.get("usage") or {}
        tok["input"] += u.get("input_tokens") or u.get("prompt_tokens") or 0
        tok["output"] += u.get("output_tokens") or u.get("completion_tokens") or 0
        tok["reasoning"] += (u.get("output_tokens_details") or {}).get("reasoning_tokens") or 0
        tok["cached"] += (u.get("input_tokens_details") or {}).get("cached_tokens") or 0
    tok["status"] = dict(tok["status"])
    return tok


def _cell(plan: list[dict], recs: dict, infra: Path) -> dict:
    """The counts of one model x framework; plan: its planned runs."""
    c = {"planned": len(plan), "finished": 0, "valid": 0, "invalid": 0, "flagged_excluded": 0, "error_runs": 0, "timed_out": 0,
         "usable": 0, "tok_in": 0, "tok_out": 0, "tok_reasoning": 0, "tok_cached": 0, "failures": [], "flag_reasons": [],
         "block_tool_calls": 0, "block_tool_outputs_rewritten": 0}
    served, tool_calls, wall, finish = set(), [], [], []
    for r in plan:
        x = recs.get(r["run_id"])
        if x is None:
            c["failures"].append({"run_id": r["run_id"], "why": "no record (not run or crashed)"})
            continue
        valid, flag = bool(x.get("decision_valid")), bool((x.get("leakage") or {}).get("flag"))
        c["finished"] += 1
        c["valid"] += valid
        c["invalid"] += not valid
        c["flagged_excluded"] += flag
        c["usable"] += valid and not flag
        c["error_runs"] += x.get("error") is not None
        c["timed_out"] += bool(x.get("timed_out"))
        tool_calls.append(x.get("n_tool_calls") or 0)
        wall.append(x.get("wall_s") or 0)
        t = x.get("tokens") or {}
        for key, field in (("tok_in", "input"), ("tok_out", "output"), ("tok_reasoning", "reasoning"), ("tok_cached", "cached")):
            c[key] += t.get(field) or 0
        c["block_tool_calls"] += x.get("block_tool_calls") or 0
        c["block_tool_outputs_rewritten"] += x.get("block_tool_outputs_rewritten") or 0
        served.update(x.get("model_served") or [])
        finish += x.get("finish_per_request") or []
        if not valid or x.get("error"):
            c["failures"].append({"run_id": r["run_id"], "valid": valid, "error": x.get("error"), "note": x.get("decision_note"),
                                  "timed_out": x.get("timed_out")})
        if flag:
            c["flag_reasons"].append({"run_id": r["run_id"], "kind": flag_kind(x), "reasons": x["leakage"].get("reasons")})
    c["served"] = sorted(served)
    c["mean_tool_calls"] = round(stt.mean(tool_calls), 2) if tool_calls else None
    c["median_wall_s"] = round(stt.median(wall), 1) if wall else None
    c["sum_wall_s"] = round(sum(wall), 1)
    m, fw = plan[0]["model"], plan[0]["framework"]
    if fw == "harness":                       # one request per assistant turn; "length" = the turn hit the per-turn token cap
        c["requests"] = len(finish)
        c["requests_cut_by_token_cap"] = finish.count("length")
        c["max_tokens_per_turn"] = config.MODELS[m]["harness"]["max_tokens"]
    else:
        workspaces = {recs[r["run_id"]]["workspace_name"] for r in plan if r["run_id"] in recs}
        c["relay"] = relay_usage(infra / "relay" / m / "requests.jsonl", workspaces)
    return c


def counts(recs: dict, days: list[dict], models: tuple[str, ...], infra: Path = INFRA) -> dict:
    """Per model x framework (in `models` order): planned against finished runs, validity, exclusions, failures, tokens, timing."""
    plan = runs(days)
    cells = []
    for m in models:
        for fw in config.FRAMEWORKS:
            c = _cell([r for r in plan if r["model"] == m and r["framework"] == fw], recs, infra)
            cells.append({"model": config.MODELS[m]["label"], "model_key": m, "framework": fw,
                          "framework_label": FW_LABEL[fw], **c})
    kinds = defaultdict(lambda: defaultdict(int))
    for x in recs.values():
        k = flag_kind(x)
        if k:
            kinds[f"{config.MODELS[x['model']]['label']} / {FW_LABEL[x['framework']]}"][k] += 1
    return {"n_planned": len(plan), "n_finished": len(recs),
            "totals": {k: sum(c[k] for c in cells) for k in ("planned", "finished", "valid", "invalid", "flagged_excluded",
                                                             "error_runs", "timed_out", "usable")},
            "flag_kinds": {k: dict(v) for k, v in kinds.items()}, "gpu": gpu_hours(infra), "cells": cells}
