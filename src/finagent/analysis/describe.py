"""The describe-stage rules of the pilot and describe.json / describe_tables.md for the five models (port of describe.py).

Every rule below (usable, ORIG noise, arm shift, the 2 SE mark, pasted strict / broad, realised 5-day vol, accuracy, computed in
code) is reused unchanged by finagent.analysis.reasoning. The original describe.json also held the cells of the excluded model
(docs/PROTOCOL.md § Models); this one holds the five models only, and its cells for the three models that file covered are equal
to the original ones. A cell without records (new runs of some cells only) is left out.
"""
from __future__ import annotations

import json
import math
import re
import statistics as stt
from collections import defaultdict
from pathlib import Path

from finagent import config
from finagent.analysis.report import flag_kind
from finagent.arms import UNIT_FACTOR, UNIT_KEYS
from finagent.data.outcomes import Outcomes

MODEL_ORDER = ("qwen3_8b", "qwen35_9b", "qwen38_27b", "deepseek", "kimi")       # row order of every results table
FW_ORDER = config.FRAMEWORKS
ARMS3 = config.ARMS[1:]                                                          # the three edit arms (ORIG first)
ANN_KEYS = tuple(UNIT_KEYS)                                                      # the four annualised readings UNIT5D rewrites
F5 = UNIT_FACTOR                                                                 # sqrt(5/252)
DISPERSION = re.compile(r"\bstd\b|\.std\(|np\.std|\.var\(|stdev")

DEFINITIONS = """\
(fixed before the numbers were looked at in this stage):
  usable            decision_valid and not leakage-flagged (registered rule); sensitivity: the 7 runs flagged only for Codex's own
                    bundled ripgrep re-admitted (report.flag_kind)
  ORIG noise        per day with both ORIG runs usable: |ln(vol_0 / vol_1)| and |ret_0 - ret_1|, averaged over days
  arm shift         per day: arm run minus the mean of that day's usable ORIG runs, ln(expected_vol_pct) and expected_return_pct,
                    averaged over days (signed); days without a usable ORIG run or without the arm run drop out
  within noise      sigma^2 is estimated from the ORIG pairs as mean((o0 - o1)^2) / 2; one day's shift has variance 1.5 sigma^2
                    (one arm run minus a mean of two), so the signed mean over n days has SE = sqrt(1.5 sigma^2 / n). A shift is
                    marked outside noise when |mean| > 2 SE. Crude: sigma comes from <= 6 pairs, the Qwen errors are heavy-tailed.
  pasted annualised strict: expected_vol_pct lies in [0.9 min(A), 1.1 max(A)], A = the day's four annualised readings
                    (ann_vol_10d/20d/60d_pct, parkinson_vol_10d_pct of the ORIG block). broad: expected_vol_pct is above the
                    geometric midpoint of the two scales, median(A) * (5/252)^(1/4), i.e. closer in log to the annual scale than to
                    the 5-day scale. Applied to every arm (UNIT5D shows no annualised number in the block, but get_risk_budget
                    still reports one and the coding agents can compute one).
  realised 5d vol   sqrt(sum of squared daily log returns over t+1..t+5) in percent (data.outcomes.realised_var5, the value saved
                    as outcome_not_shown.rv5 in the harness records; the same day value is used for the coding-agent runs)
  accuracy          per run e = ln(expected_vol_pct / realised 5d vol); reported: mean |e| and mean e (bias), over usable runs
  baselines         (a) the readings' own ann_vol_20d_pct * sqrt(5/252); (b) the S1 rational prior sigma5 = exp(lsig)
  computed in code  coding agents only: the run's model commands (Codex command_execution items), joined, mention python,
                    prices.csv and a dispersion function (std / var / stdev)"""


def cell_label(m: str, f: str) -> str:
    return f"{config.MODELS[m]['label']} / {'harness' if f == 'harness' else config.MODELS[m]['coding_framework']}"


def day_info(days: list[dict]) -> dict:
    """Per day: the four annualised readings of its registered ORIG block, the 20-day one and the S1 prior sigma5."""
    blocks = json.loads(config.GROUNDING_BLOCKS.read_text())
    out = {}
    for d in days:
        vs = json.loads(re.search(r"get_volatility_stats: (\{.*\})", blocks[d["day_id"]]["block"]).group(1))
        out[d["day_id"]] = {"ticker": d["ticker"], "t": d["t"], "day_type": d["day_type"], "ann": [vs[k] for k in ANN_KEYS],
                            "ann20": vs["ann_vol_20d_pct"], "prior5": d["sigma5_prior_pct"]}
    return out


def add_realised(info: dict) -> None:
    """Adds rvol5 (realised 5-day vol, %) and real5 (5-day return, %) of each day, from the panel: the values the harness records
    store as outcome_not_shown (verify L1 'realised outcomes' checks that they are equal)."""
    out = Outcomes({d["ticker"] for d in info.values()})
    for d in info.values():
        d["rvol5"], d["real5"] = math.sqrt(out.realised_var5(d["ticker"], d["t"])), out.realised(d["ticker"], d["t"])[1]


def pasted(v: float, d: dict) -> tuple[bool, bool]:
    """(strict, broad): is a submitted 5-day vol an annualised figure of the day?"""
    a = d["ann"]
    strict = 0.9 * min(a) <= v <= 1.1 * max(a)
    broad = v > stt.median(a) * F5 ** 0.5
    return strict, broad


def usable(x: dict, admit_rg: bool) -> bool:
    if not x.get("decision_valid"):
        return False
    k = flag_kind(x)
    return k is None or (admit_rg and k == "codex_bundled_tool_only")


def shifts(runs: list[dict]) -> dict:
    """runs: usable runs of one cell. ORIG noise and the arms' signed mean shifts with the noise check."""
    by = defaultdict(dict)
    for x in runs:
        by[x["day_id"]][(x["arm"], x["k"])] = x["decision"]
    pairs_v, pairs_r, sh = [], [], {a: {"v": [], "r": []} for a in ARMS3}
    for arms in by.values():
        o = [v for (a, _), v in arms.items() if a == "ORIG"]
        if len(o) == 2:
            pairs_v.append(math.log(o[0]["expected_vol_pct"] / o[1]["expected_vol_pct"]))
            pairs_r.append(o[0]["expected_return_pct"] - o[1]["expected_return_pct"])
        if not o:
            continue
        lv0 = stt.mean(math.log(v["expected_vol_pct"]) for v in o)
        r0 = stt.mean(v["expected_return_pct"] for v in o)
        for a in ARMS3:
            if (a, 0) in arms:
                sh[a]["v"].append(math.log(arms[(a, 0)]["expected_vol_pct"]) - lv0)
                sh[a]["r"].append(arms[(a, 0)]["expected_return_pct"] - r0)
    res = {"n_orig_pairs": len(pairs_v),
           "orig_rr_abs_dlnvol": round(stt.mean(abs(z) for z in pairs_v), 3) if pairs_v else None,
           "orig_rr_abs_dret": round(stt.mean(abs(z) for z in pairs_r), 3) if pairs_r else None}
    s2v = stt.mean(z * z for z in pairs_v) / 2 if pairs_v else None
    s2r = stt.mean(z * z for z in pairs_r) / 2 if pairs_r else None
    for a in ARMS3:
        for key, s2 in (("v", s2v), ("r", s2r)):
            xs = sh[a][key]
            if not xs:
                res[f"{a}_{key}"] = None
                continue
            m = stt.mean(xs)
            se = math.sqrt(1.5 * s2 / len(xs)) if s2 else None
            res[f"{a}_{key}"] = {"mean": round(m, 3), "n_days": len(xs), "se": round(se, 3) if se else None,
                                 "outside_noise": bool(se and abs(m) > 2 * se), "per_day": [round(z, 3) for z in xs]}
    return res


def coding_text(run_dir: Path) -> str:
    """The commands a Codex run's model executed (command_execution items of events.jsonl), one per line."""
    out = []
    with open(run_dir / "events.jsonl", encoding="utf-8") as f:
        for ln in f:
            e = json.loads(ln)
            it = e.get("item") or {}
            if e.get("type") == "item.completed" and it.get("type") == "command_execution":
                out.append(it.get("command") or "")
    return "\n".join(out)


def computed_vol(run_dir: Path) -> bool:
    t = coding_text(run_dir)
    return "python" in t and "prices.csv" in t and bool(DISPERSION.search(t))


def day_means(vals: list, err: list) -> dict:
    """mean |log error| per day (the 6 days, not the runs, are the units that make accuracy noisy)"""
    g = defaultdict(list)
    for (x, _), e in zip(vals, err):
        g[x["day_id"]].append(abs(e))
    return {k: stt.mean(v) for k, v in sorted(g.items())}


def cell_stats(runs: list[dict], all_runs: list[dict], info: dict, raw: Path) -> dict:
    """runs: the usable runs of one model x framework; all_runs: its finished runs; raw: the folder holding the run folders."""
    vals = [(x, x["decision"]["expected_vol_pct"]) for x in runs]
    flags = [pasted(v, info[x["day_id"]]) for x, v in vals]
    strict, broad = [s for s, _ in flags], [b for _, b in flags]
    err = [math.log(v / info[x["day_id"]]["rvol5"]) for x, v in vals]
    per_arm = {}
    for a in ("ORIG",) + ARMS3:
        idx = [i for i, (x, _) in enumerate(vals) if x["arm"] == a]
        per_arm[a] = {"n": len(idx), "pasted_strict": sum(strict[i] for i in idx), "pasted_broad": sum(broad[i] for i in idx),
                      "mean_abs_log_err": round(stt.mean(abs(err[i]) for i in idx), 3) if idx else None}
    nonpaste = [x for x, b in zip(runs, broad) if not b]
    ret_err = [x["decision"]["expected_return_pct"] - info[x["day_id"]]["real5"] for x in runs]
    tc = [x.get("n_tool_calls") or 0 for x in all_runs]
    tcu = [x.get("n_tool_calls") or 0 for x in runs]
    comp = None
    if runs and runs[0]["framework"] == "coding_agent":
        cv = [computed_vol(raw / x["run_id"]) for x in runs]
        comp = {"n": sum(cv), "of": len(runs),
                "pasted_broad_among_computed": sum(b for b, c in zip(broad, cv) if c),
                "mean_abs_log_err_computed": round(stt.mean(abs(e) for e, c in zip(err, cv) if c), 3) if any(cv) else None,
                "mean_abs_log_err_not_computed": round(stt.mean(abs(e) for e, c in zip(err, cv) if not c), 3) if not all(cv) else None}
    dm = day_means(vals, err)
    return {"n_usable": len(runs), "n_finished": len(all_runs), "computed_vol_in_code": comp,
            "pasted_strict_share": round(sum(strict) / len(runs), 3), "pasted_broad_share": round(sum(broad) / len(runs), 3),
            "pasted_strict_n": sum(strict), "pasted_broad_n": sum(broad),
            "mean_tool_calls_finished": round(stt.mean(tc), 2), "mean_tool_calls_usable": round(stt.mean(tcu), 2),
            "acc_mean_abs_log_err": round(stt.mean(abs(e) for e in err), 3), "acc_bias_log": round(stt.mean(err), 3),
            "acc_median_abs_log_err": round(stt.median(abs(e) for e in err), 3),
            "acc_day_means": {k: round(v, 3) for k, v in dm.items()},
            "acc_se_over_days": round(stt.stdev(dm.values()) / math.sqrt(len(dm)), 3) if len(dm) > 1 else None,
            "acc_mean_abs_log_err_nonpasted_broad": round(stt.mean(abs(math.log(x["decision"]["expected_vol_pct"] /
                                                     info[x["day_id"]]["rvol5"])) for x in nonpaste), 3) if nonpaste else None,
            "ret_mean_abs_err": round(stt.mean(abs(e) for e in ret_err), 2),
            "per_arm": per_arm, "shifts": shifts(runs), "shifts_without_broad_pastes": shifts(nonpaste)}


def baselines(info: dict) -> dict:
    """Accuracy of the two forecasts that need no agent: the readings' 20-day vol in 5-day units and the S1 prior."""
    out = {}
    for name, f in (("readings ann_vol_20d x sqrt(5/252)", lambda d: d["ann20"] * F5), ("S1 rational prior sigma5", lambda d: d["prior5"])):
        e = [math.log(f(d) / d["rvol5"]) for d in info.values()]
        out[name] = {"mean_abs_log_err": round(stt.mean(abs(z) for z in e), 3), "bias_log": round(stt.mean(e), 3),
                     "per_day": {k: round(f(d), 2) for k, d in info.items()}}
    return out


def describe(recs: dict, info: dict, raw: Path) -> dict:
    """The describe.json object: definitions, days, baselines, the cells and the rows that change when rg-only runs re-enter."""
    res = {"definitions": DEFINITIONS, "days": info, "baselines": baselines(info), "cells": [], "cells_rg_readmitted": []}
    for admit, key in ((False, "cells"), (True, "cells_rg_readmitted")):
        for m in MODEL_ORDER:
            for f in FW_ORDER:
                allr = [x for x in recs.values() if x["model"] == m and x["framework"] == f]
                runs = [x for x in allr if usable(x, admit)]
                if not runs or admit and len(runs) == len([x for x in allr if usable(x, False)]):
                    continue
                res[key].append({"model": m, "framework": f, "label": cell_label(m, f), **cell_stats(runs, allr, info, raw)})
    return res


# ---------------------------------------------------------------------------------------------------- tables
def fmt_shift(s: dict | None, digits: int = 2) -> str:
    if not s:
        return "-"
    return f"{s['mean']:+.{digits}f}{'*' if s['outside_noise'] else ''} ({s['n_days']})"


def f2(x: float | None) -> str:
    return "-" if x is None else f"{x:.2f}"


def tables(res: dict) -> str:
    """describe_tables.md: the main table, the two sensitivity tables, pastes by arm and the days."""
    L = ["| model / framework | usable | ORIG run-to-run abs diff ln(vol) (pairs) | NOLABEL d ln(vol) | UNIT5D d ln(vol) | "
         "PLACEBO d ln(vol) | ORIG run-to-run abs diff return, pp | NOLABEL d return | UNIT5D d return | PLACEBO d return | "
         "pasted annualised, strict (broad) | mean tool calls / commands | computed a vol in code | "
         "abs log error vs realised 5d vol (bias) [SE over days] |", "|" + "---|" * 14]
    for c in res["cells"]:
        s, cv = c["shifts"], c["computed_vol_in_code"]
        L.append(f"| {c['label']} | {c['n_usable']} | {f2(s['orig_rr_abs_dlnvol'])} ({s['n_orig_pairs']}) | "
                 f"{fmt_shift(s['NOLABEL_v'])} | {fmt_shift(s['UNIT5D_v'])} | {fmt_shift(s['PLACEBO_v'])} | "
                 f"{f2(s['orig_rr_abs_dret'])} | {fmt_shift(s['NOLABEL_r'])} | {fmt_shift(s['UNIT5D_r'])} | {fmt_shift(s['PLACEBO_r'])} | "
                 f"{c['pasted_strict_n']}/{c['n_usable']} ({c['pasted_broad_n']}) | {c['mean_tool_calls_finished']:.1f} | "
                 f"{'-' if not cv else str(cv['n']) + '/' + str(cv['of'])} | "
                 f"{c['acc_mean_abs_log_err']:.2f} ({c['acc_bias_log']:+.2f}) [{f2(c['acc_se_over_days'])}] |")
    for k, b in res["baselines"].items():
        L.append(f"| baseline: {k} | 6 days | | | | | | | | | | | | {b['mean_abs_log_err']:.2f} ({b['bias_log']:+.2f}) |")
    L += ["", "Sensitivity A: the 7 runs flagged only for Codex's bundled ripgrep re-admitted (rows that change).", "",
          "| model / framework | usable | ORIG noise ln(vol) | NOLABEL | UNIT5D | PLACEBO | ORIG noise return | NOLABEL | UNIT5D | PLACEBO |",
          "|" + "---|" * 10]
    for c in res["cells_rg_readmitted"]:
        s = c["shifts"]
        L.append(f"| {c['label']} | {c['n_usable']} | {f2(s['orig_rr_abs_dlnvol'])} ({s['n_orig_pairs']}) | {fmt_shift(s['NOLABEL_v'])} | "
                 f"{fmt_shift(s['UNIT5D_v'])} | {fmt_shift(s['PLACEBO_v'])} | {f2(s['orig_rr_abs_dret'])} | {fmt_shift(s['NOLABEL_r'])} | "
                 f"{fmt_shift(s['UNIT5D_r'])} | {fmt_shift(s['PLACEBO_r'])} |")
    L += ["", "Sensitivity B: runs whose 5-day vol is on the annualised scale (broad rule) dropped before the shifts are computed.", "",
          "| model / framework | runs kept | ORIG noise ln(vol) | NOLABEL | UNIT5D | PLACEBO |", "|" + "---|" * 6]
    for c in res["cells"]:
        s = c["shifts_without_broad_pastes"]
        L.append(f"| {c['label']} | {c['n_usable'] - c['pasted_broad_n']} | "
                 f"{f2(s['orig_rr_abs_dlnvol'])} ({s['n_orig_pairs']}) | "
                 f"{fmt_shift(s['NOLABEL_v'])} | {fmt_shift(s['UNIT5D_v'])} | {fmt_shift(s['PLACEBO_v'])} |")
    L += ["", "Pasted annualised figures by arm, strict (broad), out of usable runs of that arm.", "",
          "| model / framework | ORIG | NOLABEL | UNIT5D | PLACEBO |", "|---|---|---|---|---|"]
    for c in res["cells"]:
        pa = c["per_arm"]
        L.append(f"| {c['label']} | " + " | ".join(f"{pa[a]['pasted_strict']} ({pa[a]['pasted_broad']}) of {pa[a]['n']}"
                                                   for a in ("ORIG",) + ARMS3) + " |")
    L += ["", "Days: realised outcome (never shown to any agent) and the two baselines.", "",
          "| day | type | realised 5d vol % | realised 5d return % | ann_vol_20d | 20d in 5-day units | S1 prior sigma5 |",
          "|---|---|---|---|---|---|---|"]
    for k, d in res["days"].items():
        L.append(f"| {k} | {d['day_type']} | {d['rvol5']:.2f} | {d['real5']:+.2f} | {d['ann20']:.1f} | {d['ann20'] * F5:.2f} | "
                 f"{d['prior5']:.2f} |")
    return "\n".join(L)
