"""The four arms: the same price readings presented four ways (information unchanged), and the CPU check of the rewrites.

The readings are the seven JSON tool outputs of the PRICE TOOL READINGS block; an arm rewrites the object and serialises it again
with json.dumps defaults (what the toolbox uses, so re-serialising ORIG is byte-identical: the check asserts it).
  ORIG     unchanged
  NOLABEL  delete the categorical labels, keep every number: get_trend_signal.signal, get_rsi.signal,
           get_mean_reversion_signal.signal, get_macd.cross, get_volatility_stats.regime
           (get_macd.signal is the numeric signal line and stays; get_volatility_stats.note is a fixed sentence, not a label)
  UNIT5D   the annualised volatility fields of get_volatility_stats replaced in place by their 5-day equivalents,
           value * sqrt(5/252), one decimal, under new names (UNIT_KEYS)
  PLACEBO  the keys of every reading in a fixed shuffled order (numpy default_rng(SEED + crc32(tool name)).permutation of the
           tool's key list), values untouched; the same order on every day and in every call
The rewrite applies to the block lines of the prompt and, in the harness, to the output of every call of one of the seven tools
(any arguments) before the tool-result cut. Other tools are never rewritten; tool descriptions are not touched.
"""
from __future__ import annotations

import json
import math
import zlib
from datetime import datetime

import numpy as np

from finagent import config, readings
from finagent.data.pit import news_cache
from finagent.harness import toolbox

SEED = config.EXPERIMENT["seed"]
BLOCK_TOOLS = tuple(name for name, _ in readings.BLOCK_CALLS)              # the seven tools of the readings block, in block order
LABEL_KEYS = {"get_trend_signal": ("signal",), "get_rsi": ("signal",), "get_mean_reversion_signal": ("signal",),
              "get_macd": ("cross",), "get_volatility_stats": ("regime",)}
UNIT_FACTOR = math.sqrt(5 / 252)
UNIT_KEYS = {"ann_vol_10d_pct": "vol_5d_equiv_from_10d_pct", "ann_vol_20d_pct": "vol_5d_equiv_from_20d_pct",
             "ann_vol_60d_pct": "vol_5d_equiv_from_60d_pct", "parkinson_vol_10d_pct": "parkinson_vol_5d_equiv_from_10d_pct"}


def _perm(tool: str, keys: list[str]) -> list[str]:
    rng = np.random.default_rng(SEED + zlib.crc32(tool.encode()))
    order = [keys[j] for j in rng.permutation(len(keys))]
    if order == keys and len(keys) > 1:                 # never the original order (a placebo must change the text)
        order = keys[1:] + keys[:1]
    return order


def rewrite_obj(tool: str, obj: dict, arm: str) -> dict:
    if arm == "ORIG" or tool not in BLOCK_TOOLS or not isinstance(obj, dict) or "error" in obj:
        return obj
    if arm == "NOLABEL":
        drop = LABEL_KEYS.get(tool, ())
        return {k: v for k, v in obj.items() if k not in drop}
    if arm == "UNIT5D":
        if tool != "get_volatility_stats":
            return obj
        out = {}
        for k, v in obj.items():
            if k in UNIT_KEYS and isinstance(v, (int, float)) and not isinstance(v, bool):
                out[UNIT_KEYS[k]] = round(v * UNIT_FACTOR, 1)
            else:
                out[k] = v
        return out
    if arm == "PLACEBO":
        order = _perm(tool, list(obj.keys()))
        return {k: obj[k] for k in order}
    raise ValueError(arm)


def rewrite_output(tool: str, text: str, arm: str) -> str:
    """One tool output string (as the toolbox returns it) in the arm's form."""
    if arm == "ORIG" or tool not in BLOCK_TOOLS:
        return text
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return text
    if not isinstance(obj, dict):
        return text
    return json.dumps(rewrite_obj(tool, obj, arm))


def parse_block(block: str) -> list[tuple[str, str, str]]:
    """[(line prefix '- name (args): ', tool name, output json)] of a readings block."""
    lines = block.split("\n")
    if lines[0] != readings.HEADER:
        raise ValueError("not a readings block")
    out = []
    for ln in lines[1:]:
        pre, js = ln.split(": ", 1) if ": " in ln else (ln, "")
        name = pre[2:].split(" ")[0]
        out.append((pre + ": ", name, js))
    return out


def rewrite_block(block: str, arm: str) -> str:
    if arm == "ORIG":
        return block
    lines = [readings.HEADER] + [pre + rewrite_output(name, js, arm) for pre, name, js in parse_block(block)]
    return "\n".join(lines)


# ================================================================================================== CPU check
def _num(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def check_pair(tool: str, orig_text: str, arm: str, new_text: str) -> list[str]:
    """Problems of one rewritten output (empty = the rewrite is exactly the registered one)."""
    probs = []
    a = json.loads(orig_text)
    b = json.loads(new_text)
    if arm == "ORIG":
        if new_text != orig_text:
            probs.append("ORIG changed the text")
        if json.dumps(a) != orig_text:
            probs.append("json re-serialisation is not byte-identical")
        return probs
    if tool not in BLOCK_TOOLS:
        return [] if new_text == orig_text else ["a non-block tool was rewritten"]
    if arm == "NOLABEL":
        drop = set(LABEL_KEYS.get(tool, ()))
        if set(a) - set(b) != drop & set(a):
            probs.append(f"deleted keys {set(a) - set(b)} != labels {drop}")
        if set(b) - set(a):
            probs.append(f"new keys {set(b) - set(a)}")
        for k in drop & set(a):
            if _num(a[k]):
                probs.append(f"deleted key {k} was numeric")
        for k in b:
            if json.dumps(b[k]) != json.dumps(a[k]):
                probs.append(f"value of {k} changed")
        if list(b) != [k for k in a if k not in drop]:
            probs.append("key order changed")
        for k, v in b.items():
            if isinstance(v, str) and k != "note" and k != "date":
                probs.append(f"a categorical string is left: {k}={v}")
    elif arm == "UNIT5D":
        if tool != "get_volatility_stats":
            return [] if new_text == orig_text else ["UNIT5D changed a tool other than get_volatility_stats"]
        exp_keys = [UNIT_KEYS.get(k, k) for k in a]
        if list(b) != exp_keys:
            probs.append(f"keys {list(b)} != {exp_keys}")
        for k, v in a.items():
            nk = UNIT_KEYS.get(k, k)
            if k in UNIT_KEYS:
                want = round(v * UNIT_FACTOR, 1)
                if b.get(nk) != want:
                    probs.append(f"{nk}={b.get(nk)} != round({v} x sqrt(5/252), 1) = {want}")
                back = b.get(nk, 0) / UNIT_FACTOR                     # information kept up to the rounding of the new value
                if abs(back - v) > 0.05 / UNIT_FACTOR + 0.05 + 1e-9:
                    probs.append(f"{nk} does not convert back to {v} within rounding ({back:.2f})")
            elif json.dumps(b.get(nk)) != json.dumps(v):
                probs.append(f"value of {k} changed")
        if not any(k in a for k in UNIT_KEYS):
            probs.append("no annualised field found")
    elif arm == "PLACEBO":
        if sorted(a) != sorted(b):
            probs.append("key sets differ")
        for k in a:
            if json.dumps(a[k]) != json.dumps(b.get(k)):
                probs.append(f"value of {k} changed")
        if len(a) > 1 and list(a) == list(b):
            probs.append("order unchanged")
        if list(b) != _perm(tool, list(a)):
            probs.append("order is not the registered permutation")
    return probs


def check_prompt_diff(orig_prompt: str, arm_prompt: str, orig_block: str, arm_block: str) -> list[str]:
    """The arm's prompt equals ORIG's except inside the block lines."""
    if orig_prompt.count(orig_block) != 1 or arm_prompt.count(arm_block) != 1:
        return ["block not found exactly once"]
    a, b = orig_prompt.split(orig_block), arm_prompt.split(arm_block)
    return [] if a == b else ["prompt differs outside the block"]


def check_all(days: list[dict], prompts: dict | None = None) -> dict:
    """Every arm x day block line, the prompt diff (prompts: {(day_id, arm): text}) and extra tool calls with other arguments."""
    rows, n_bad = [], 0
    for d in days:
        b = readings.registered_block(d["day_id"])
        for arm in config.ARMS:
            nb = rewrite_block(b, arm)
            for (pre, name, js), (pre2, _, js2) in zip(parse_block(b), parse_block(nb)):   # pre holds the name
                pr = check_pair(name, js, arm, js2) + ([] if pre == pre2 else ["line prefix changed"])
                n_bad += bool(pr)
                rows.append({"day_id": d["day_id"], "arm": arm, "where": "block", "tool": name, "problems": pr,
                             "chars_orig": len(js), "chars_new": len(js2)})
            if prompts and (d["day_id"], arm) in prompts:
                pr = check_prompt_diff(prompts[(d["day_id"], "ORIG")], prompts[(d["day_id"], arm)], b, nb)
                n_bad += bool(pr)
                rows.append({"day_id": d["day_id"], "arm": arm, "where": "prompt", "problems": pr})
        # tool calls with other arguments, through the unchanged toolbox (what a session would receive)
        cache = news_cache(d["ticker"]).view()
        as_of = datetime.strptime(d["t"], "%Y-%m-%d")
        st = toolbox.new_state({"cash": 1.0, "shares": 0})
        calls = [(n, {}) for n in BLOCK_TOOLS] + [("get_rsi", {"period": 7}), ("get_rsi", {"period": 21}),
                                                  ("get_risk_budget", {}), ("get_returns", {"days": 5})]
        for name, args in calls:
            out = toolbox.run_tool(cache, as_of, name, dict(args), st)
            for arm in config.ARMS:
                new = rewrite_output(name, out, arm)
                pr = check_pair(name, out, arm, new) if name in BLOCK_TOOLS or arm == "ORIG" else \
                    ([] if new == out else ["a non-block tool was rewritten"])
                n_bad += bool(pr)
                rows.append({"day_id": d["day_id"], "arm": arm, "where": "tool_call", "tool": name, "args": args, "problems": pr})
    return {"n_checks": len(rows), "n_with_problems": n_bad, "pass": n_bad == 0, "rows": rows}
