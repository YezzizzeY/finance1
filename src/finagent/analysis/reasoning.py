"""The five-model page: describe_reasoning_models.{json,md} and examples_reasoning_models.json (port of describe_reasoning.py).

Adds to describe.py's rules (reused unchanged) what the models' reasoning output says: whether it mentions an annualised figure,
whether such runs still submit it as the 5-day vol, each edit arm's shift against PLACEBO, and six hand-picked excerpts. The
rules added in this stage are RULES below. The page text (HEAD, NOTES, the closing paragraph) is the original's, verbatim: it
names the original module paths (repro/codexpilot/describe*.py = finagent.analysis.describe / reasoning here).
"""
from __future__ import annotations

import gzip
import json
import math
import re
import statistics as stt
from collections import defaultdict
from pathlib import Path

from finagent.analysis import describe as DS
from finagent.analysis.report import FW_LABEL, flag_kind

LABEL = {"qwen3_8b": "Qwen3-8B", "qwen35_9b": "Qwen3.5-9B", "qwen38_27b": "Qwen 27B (Qwen3.8-27B-FP8)",
         "deepseek": "DeepSeek (reasoner)", "kimi": "Kimi K3"}
ARMS = ("ORIG",) + DS.ARMS3
NUM = re.compile(r"(?<![\w.])(\d{1,3}(?:\.\d+)?)(?![\w])")
KW = re.compile(r"annual|ann[._ ]{0,2}vol|yearly|per year|parkinson", re.I)

# The page text, verbatim from the original (describe_reasoning_models.md is byte-identical to it). RULES are the definitions
# added in this stage, fixed before the numbers were looked at; the page quotes them in full.
RULES = """\
Definitions added in this stage (fixed before the numbers were looked at):
  reasoning output  the provider's reasoning field only, never the final answer:
                    harness   every turn's `reasoning` / `reasoning_content` in the session trace (for Kimi and Qwen 27B checked
                              equal to the stored raw responses, ctx.raw_responses / ctx.raw_choices);
                    Codex     every reasoning item of the relay's raw SSE streams (response.output_item.done, item type
                              reasoning: content reasoning_text + summary summary_text; Kimi returns its reasoning as summary
                              text), checked equal to Codex's own rollout reasoning items in every run
  mentions an annualised figure
                    exact     the reasoning contains one of the day's four annualised readings (ann_vol_10d/20d/60d_pct,
                              parkinson_vol_10d_pct of the ORIG block) written with its decimal as in the readings (e.g. 75.9), as
                              a standalone number (no letter, digit, '.' or '_' joined to it)
                    any       exact, or a standalone number in [0.9 min(A), 1.1 max(A)] (the strict paste range) with an annual
                              keyword (annual / annualis / annualiz / ann_vol / ann. vol / ann vol / yearly / per year / parkinson)
                              in the 60 characters before it; catches rounded quotes ("ann. vol ~75-90%") and the model's own
                              annualised computations. Primary rule: any.
  still submits it  among runs whose reasoning mentions an annualised figure (any), the share whose final expected_vol_pct is pasted
                    (strict; broad in the second number), with the paste rules of describe.py
  shift minus PLACEBO  per day with a usable ORIG run, the arm run and the PLACEBO run: (arm - ORIG mean) - (PLACEBO - ORIG mean)
                    = arm - PLACEBO, averaged over those days; under no effect one day has variance 2 sigma^2 (sigma^2 from the
                    ORIG pairs as in describe.py), SE = sqrt(2 sigma^2 / n), marked outside noise when |mean| > 2 SE
  tool calls        mean n_tool_calls over finished runs (harness: tool calls incl. submit_decision; Codex: commands + file changes
                    + other tool items), as in pilot_report.md; the mean over usable runs is stored too
  computed a vol    describe.computed_vol on the Codex runs' commands (python + prices.csv + std / var / stdev), usable runs

"""
HEAD = """# Five reasoning models: description (codexpilot_20261018)

This is a tiny exploratory pilot: 6 days, 5 runs per day (ORIG x2, NOLABEL, UNIT5D, PLACEBO), and two frameworks (our 32-tool
harness and Codex CLI 0.162.1). This page covers the five models whose APIs return a reasoning field: Qwen3-8B, Qwen3.5-9B,
Qwen 27B (Qwen3.8-27B-FP8), DeepSeek (deepseek-reasoner) and Kimi K3. That is 300 runs. Sonnet is left out, because its thinking
is hidden in both frameworks. **Nothing here is a test.**

* **Source.** Saved records only (CPU, no model call), by `repro/codexpilot/describe_reasoning.py`. For the three earlier models,
  all six cells match `describe.json` exactly (usable runs, shifts, pastes, accuracy, tool calls, computed in code).
* **Files.** `describe_reasoning_models.json` has 1,004 records {model, framework, metric, value, n}. The excerpts are in
  `examples_reasoning_models.json` (X1 to X6 below).
* **Usable runs** = a valid decision and not flagged by the leakage audit (the registered rule). Out of 30 per cell, the excluded
  runs are: DeepSeek / Codex 7 flagged; Qwen3-8B / Codex 1 flagged and 3 invalid; Qwen3.5-9B / Codex 1 invalid; Qwen 27B /
  Codex 2 flagged (an attempted write to /tmp, blocked by the sandbox).

**Settings that differ between rows** (all taken from the run records):

* **Harness token cap per turn.** 2,048 for Qwen3-8B and Qwen3.5-9B, which had 7 of 37 and 14 of 47 turns cut. 8,192 for Qwen 27B
  and DeepSeek, and 16,384 for Kimi; none of their turns was cut.
* **Reasoning effort.**
  * Kimi was sent "high" in both frameworks. Moonshot's Chat Completions endpoint may ignore that field, and then the harness ran at
    Kimi's default, "max".
  * Qwen 27B ran at "xhigh" in Codex, because its chat template rejects "high". The harness got the template default, which is also
    xhigh.
* **Visible reasoning.**
  * Kimi's Codex reasoning arrives as summary text, from Moonshot's Responses API.
  * Kimi writes much less reasoning than the others: 1,864 characters per run in the harness and 3,574 in Codex. DeepSeek writes
    8,000 to 9,600 and Qwen 27B 15,800 to 17,400.
"""
NOTES = """## What the tables show

1. **Only the two small Qwen models ever submit an annualised figure as the 5-day vol.** That happened in 9 strict (12 broad) of
   their 115 usable runs. Qwen 27B, DeepSeek and Kimi did it in 0 of 171 runs, in both frameworks.

2. **Every model mentions the annualised figure in its reasoning. They differ in whether they convert it.**
   * The reasoning mentions one in 65 of the 115 small-Qwen runs and in 136 of the 171 runs of the three larger models.
   * Of the 65 small-Qwen runs, 6 still submit it (8 broad), about 1 in 10. X1 reads the 10-day annualised 12.6 as "the 5-day
     volatility". X2 writes 52 and then ticks off "5-day one-sd in percent".
   * Of the 136 larger-model runs, none submits it: they convert, for example "45% × sqrt(5/252) ≈ 6.35%" (X3).
   * Four small-Qwen broad pastes had no mention in the reasoning field at all. For example, in Qwen3.5-9B / harness / CB /
     NOLABEL the final answer itself says "Volatility elevated at 14.6% annualized".

3. **UNIT5D removes the mention only where the readings are the only source.**
   * In Codex, 0 of the 28 UNIT5D runs mention an annualised figure. In the harness, the two small Qwens mention one in 0 of 12.
   * In the harness, DeepSeek still mentions one in 6 of 6 UNIT5D runs, Qwen 27B in 5 of 6 and Kimi in 1 of 6. These models call
     `get_risk_budget` (DeepSeek in 29 of 30 runs, Qwen 27B 28 of 30, Kimi 16 of 30). That tool reports the trailing 20-day vol in
     annual units, and the arm does not rewrite it (X5).
   * So in the harness the UNIT5D arm does not keep the annual number away from models that use tools. They converted it
     correctly anyway.

4. **The shifts compared with PLACEBO, the fairer yardstick, are mostly within noise.**
   * **Qwen 27B.** In the harness all three arms, the placebo included, sit 0.11 to 0.15 above ORIG in ln(vol). That is a generic
     text-change shift, so each edit minus the placebo is +0.01 to +0.03. In Codex the NOLABEL mark (+0.10\\*) also disappears
     against the placebo (+0.01).
   * **Kimi, harness.** UNIT5D lowers the vol forecast against the placebo (-0.22\\*). It is at or below zero on all 6 days, and
     largest on MRK (-0.68) and CB (-0.34).
     * On MRK the two ORIG runs submitted 5.5 and 4.5; ORIG run 0 used ATR × √5 = 5.9 %.
     * The UNIT5D run read the 5-day equivalent (3.4 %), also read the calibration tool ("you overstate volatility") and submitted
       2.8 (X4).
     * The realised vol was 1.6 %.
   * **Kimi, Codex.** No vol shift (all |shift| ≤ 0.04). UNIT5D lowers the return forecast against the placebo by 0.75 pp\\*, at or
     below zero on 6 of 6 days.
   * **DeepSeek.** NOLABEL minus PLACEBO is -0.17\\* in the harness, driven by one day (CRWD, -0.69). UNIT5D minus PLACEBO is
     -0.22\\* in Codex, over 3 days only. Both come largely from DeepSeek's own placebo shift (+0.13 and +0.10).
   * **The small Qwens.** The marks (Qwen3.5-9B / harness NOLABEL minus PLACEBO: +0.50\\* in vol, +3.38 pp\\* in return) come from the
     pastes and from one HOOD run (see `pilot_report.md`).
   * **Overall,** 6 of the 40 "minus PLACEBO" comparisons carry a \\*. The rule is crude (2 SE, with sigma from 4 to 6 pairs), so
     some marks are expected by chance. None of them is a result.

5. **Noise sets what can be seen.** The ORIG run-to-run difference in ln(vol) is:
   * 0.09 in Kimi / Codex and Qwen 27B / Codex;
   * 0.14 to 0.16 in DeepSeek and Kimi / harness;
   * 0.28 in Qwen 27B / harness;
   * 0.35 to 0.70 in the small Qwens.

   Shifts of about 0.1 can show only in the low-noise cells.

6. **Accuracy.**
   * Qwen 27B, DeepSeek and Kimi are all at 0.39 to 0.41 mean |ln(forecast / realised)| in both frameworks.
   * That is below both baselines: 0.48 for the readings' 20-day vol in 5-day units, and 0.43 for the S1 prior.
   * The day-level SE is 0.08 to 0.15, so these six cells cannot be told apart.
   * The small Qwens are at 0.54 to 0.67, mostly because of the pastes.
   * Every cell's bias is positive: its forecasts are too high on average.

7. **Work done.**
   * **Harness tool calls per run:** Qwen 27B 9.1 against about 1 for the small Qwens; DeepSeek 12.1 and Kimi 3.7.
   * **Codex runs that computed a vol from prices.csv:** DeepSeek 23/23, Qwen3.5-9B 25/29, Qwen 27B 23/28 (X6), Kimi 19/30 and
     Qwen3-8B 0/26.
   * Computing in code did not stop the Qwen3.5-9B pastes (pilot C2). Kimi and DeepSeek never pasted, whether they computed or not.

**Limits.**

* **Size.** Only 6 days, with one run per edit arm per day.
* **The mention rule.** It is plain text matching on the reasoning field.
  * I checked its hits by hand in DeepSeek / harness / UNIT5D, Qwen 27B / harness / UNIT5D and Kimi / Codex / ORIG. No hit rests on
    the 15 % portfolio target vol alone.
  * The exact rule is a lower bound. The "any" rule also counts rounded quotes and the model's own annualised computations.
  * A missing mention can simply mean the model did not write its thinking out. This matters most for Kimi, whose reasoning is
    short.
* **Mixed settings.** The token caps and possibly Kimi's effort differ between rows and frameworks (see above). The arm shifts are
  within one model and framework, so these differences do not bias them, but they affect comparisons across rows.

## Excerpts

Each excerpt names the model, framework, day and arm, and gives the final 5-day vol (realised 5-day vol in brackets, never shown to
the agent).

* **X1. Qwen3-8B / Codex / CB / ORIG run 1, submitted 15.0 (3.8).** *"…the 5-day volatility is around 12.6%… volatility of 15%."*
  12.6 is the annualised 10-day reading.
* **X2. Qwen3.5-9B / Codex / CRWD / ORIG run 0, submitted 52.0 (12.7).** *"- Ann vol 10d: 105.4%"* … *"52% expected volatility"* …
  *"- expected_vol_pct: 5-day one-sd in percent ✓"*
* **X3. Kimi K3 / Codex / VST / ORIG run 1, submitted 7.0 (7.3).** *"ann vol 45% → 5-day sd = 45% × sqrt(5/252) ≈ 45% × 0.141 ≈
  6.35%."*
* **X4. Kimi K3 / harness / MRK / UNIT5D, submitted 2.8 (1.6).** *"Vol 5-day equiv ~3.4-3.8%."* … *"Typical 5-day vol ~3.4% but
  I've been overstating. Set expected_vol ~2.8%."* The same day's ORIG runs submitted 5.5 and 4.5.
* **X5. DeepSeek / harness / MCHP / UNIT5D, submitted 11.0 (5.3).** *"Trailing 20d vol 74.1% annualized"* (from get_risk_budget)
  … *"74*sqrt(5/252) = 74*0.1409 = 10.4%… I'll say 11."*
* **X6. Qwen 27B / Codex / CRWD / ORIG run 0, submitted 14.0 (12.7).** Its own script printed *"implied 5d 1sd from 10d daily vol:
  16.80%"* and *"…from 20d daily vol: 12.46%"*. It then reasoned: *"I'll use 14%."*
"""
TAIL = ("The rules reused from the pilot (usable, ORIG noise, arm shift, the 2 SE mark, pasted strict / broad, realised 5-day "
        "vol, accuracy, computed a vol in code) are in the docstring of `repro/codexpilot/describe.py`. To rebuild: "
        "`PYTHONPATH=. .venv/bin/python -m repro.codexpilot.describe_reasoning`.\n")


# ------------------------------------------------------------------------------------------------ reasoning text
def reasoning_items(run_dir: Path, framework: str) -> list[str]:
    """The provider's reasoning field of every turn: the harness session trace, or the reasoning items of Codex's relay streams."""
    if framework == "harness":
        with gzip.open(run_dir / "session.json.gz") as f:
            return [t.get("reasoning") or "" for t in json.load(f)["trace"] if "reasoning" in t]
    out = []
    for p in sorted((run_dir / "relay").glob("*_resp.txt")):
        with open(p, encoding="utf-8", errors="replace") as f:
            for ln in f:
                if not ln.startswith("data: "):
                    continue
                try:
                    e = json.loads(ln[6:])
                except json.JSONDecodeError:
                    continue
                it = e.get("item") or {}
                if e.get("type") == "response.output_item.done" and it.get("type") == "reasoning":
                    out.append(" ".join([c.get("text", "") for c in (it.get("content") or [])] +
                                        [c.get("text", "") for c in (it.get("summary") or [])]))
    return out


def mention(text: str, d: dict) -> dict:
    """Does the text mention one of the day's annualised readings (exact), or a number in the paste range after a keyword (any)?"""
    a = d["ann"]
    lo, hi = 0.9 * min(a), 1.1 * max(a)
    exact, kw, hits = False, False, []
    for mm in NUM.finditer(text):
        tok = mm.group(1)
        v = float(tok)
        if "." in tok and any(abs(v - z) < 1e-9 for z in a):
            exact = True
            hits.append(mm.start())
        elif lo <= v <= hi and KW.search(text[max(0, mm.start() - 60):mm.start()]):
            kw = True
            hits.append(mm.start())
    return {"exact": exact, "any": exact or kw, "hits": hits}


# ------------------------------------------------------------------------------------------------ per cell
def per_day(runs: list[dict]) -> tuple[dict, list, list]:
    """Per day: each edit arm's (d ln vol, d return) against the ORIG mean; and the ORIG pair differences (vol, return)."""
    by = defaultdict(dict)
    for x in runs:
        by[x["day_id"]][(x["arm"], x["k"])] = x["decision"]
    pv, pr, days = [], [], {}
    for did, arms in sorted(by.items()):
        o = [v for (a, _), v in arms.items() if a == "ORIG"]
        if len(o) == 2:
            pv.append(math.log(o[0]["expected_vol_pct"] / o[1]["expected_vol_pct"]))
            pr.append(o[0]["expected_return_pct"] - o[1]["expected_return_pct"])
        if not o:
            continue
        lv0 = stt.mean(math.log(v["expected_vol_pct"]) for v in o)
        r0 = stt.mean(v["expected_return_pct"] for v in o)
        days[did] = {a: (math.log(arms[(a, 0)]["expected_vol_pct"]) - lv0, arms[(a, 0)]["expected_return_pct"] - r0)
                     for a in DS.ARMS3 if (a, 0) in arms}
    return days, pv, pr


def vs_placebo(days: dict, pv: list, pr: list) -> dict:
    """NOLABEL and UNIT5D minus PLACEBO, per day and averaged, with SE = sqrt(2 sigma^2 / n) and the 2 SE mark."""
    out = {}
    s2 = {0: stt.mean(z * z for z in pv) / 2 if pv else None, 1: stt.mean(z * z for z in pr) / 2 if pr else None}
    for a in ("NOLABEL", "UNIT5D"):
        for i, key in ((0, "lnvol"), (1, "ret")):
            xs = [dd[a][i] - dd["PLACEBO"][i] for dd in days.values() if a in dd and "PLACEBO" in dd]
            if not xs:
                out[f"{a}_minus_PLACEBO_{key}"] = None
                continue
            m = stt.mean(xs)
            se = math.sqrt(2 * s2[i] / len(xs)) if s2[i] else None
            out[f"{a}_minus_PLACEBO_{key}"] = {"mean": round(m, 3), "n_days": len(xs), "se": round(se, 3) if se else None,
                                              "outside_noise": bool(se and abs(m) > 2 * se), "per_day": [round(z, 3) for z in xs]}
    return out


def cell(m: str, f: str, recs: dict, info: dict, raw: Path) -> dict:
    """Everything the page reports for one model x framework."""
    allr = sorted((x for x in recs.values() if x["model"] == m and x["framework"] == f), key=lambda x: x["run_id"])
    runs = [x for x in allr if DS.usable(x, False)]
    base = DS.cell_stats(runs, allr, info, raw)
    days, pv, pr = per_day(runs)
    rs = {x["run_id"]: reasoning_items(raw / x["run_id"], f) for x in runs}
    men = {rid: mention("\n".join(t), info[recs[rid]["day_id"]]) for rid, t in rs.items()}
    pst = {x["run_id"]: DS.pasted(x["decision"]["expected_vol_pct"], info[x["day_id"]]) for x in runs}
    ment = {"any": {}, "exact": {}}
    for rule in ("any", "exact"):
        for a in ("ALL",) + ARMS:
            ids = [x["run_id"] for x in runs if a == "ALL" or x["arm"] == a]
            mi = [r for r in ids if men[r][rule]]
            ment[rule][a] = {"n_runs": len(ids), "n_mention": len(mi),
                             "n_mention_pasted_strict": sum(pst[r][0] for r in mi),
                             "n_mention_pasted_broad": sum(pst[r][1] for r in mi),
                             "n_pasted_broad_without_mention": sum(pst[r][1] and not men[r][rule] for r in ids)}
    rb = {a: (sum("get_risk_budget" in (x.get("tool_names") or []) for x in runs if a == "ALL" or x["arm"] == a),
              sum(1 for x in runs if a == "ALL" or x["arm"] == a)) for a in ("ALL",) + ARMS} if f == "harness" else None
    return {"model": m, "framework": f, "label": f"{LABEL[m]} / {FW_LABEL[f]}", "base": base, "risk_budget": rb,
            "vs_placebo": vs_placebo(days, pv, pr), "mention": ment,
            "n_valid": sum(bool(x.get("decision_valid")) for x in allr),
            "n_flagged": sum(flag_kind(x) is not None for x in allr),
            "n_runs_with_reasoning_text": sum(any(t.strip() for t in v) for v in rs.values()),
            "reasoning_chars_mean": round(stt.mean(sum(map(len, v)) for v in rs.values()), 0)}


# ------------------------------------------------------------------------------------------------ records, tables
def to_records(cells: list[dict], info: dict) -> list[dict]:
    """describe_reasoning_models.json: one {model, framework, metric, value, n} per number."""
    R = []

    def add(c, metric, value, n):
        R.append({"model": LABEL[c["model"]], "framework": FW_LABEL[c["framework"]], "metric": metric, "value": value, "n": n})

    for c in cells:
        b, s = c["base"], c["base"]["shifts"]
        add(c, "runs_finished", b["n_finished"], None)
        add(c, "runs_valid", c["n_valid"], b["n_finished"])
        add(c, "runs_flagged_excluded", c["n_flagged"], b["n_finished"])
        add(c, "runs_usable", b["n_usable"], b["n_finished"])
        add(c, "orig_run_to_run_abs_diff_lnvol", s["orig_rr_abs_dlnvol"], s["n_orig_pairs"])
        add(c, "orig_run_to_run_abs_diff_return_pp", s["orig_rr_abs_dret"], s["n_orig_pairs"])
        for a in DS.ARMS3:
            for key, name in (("v", "lnvol"), ("r", "return_pp")):
                z = s[f"{a}_{key}"]
                add(c, f"shift_{a}_{name}", z and z["mean"], z and z["n_days"])
                add(c, f"shift_{a}_{name}_se", z and z["se"], z and z["n_days"])
                add(c, f"shift_{a}_{name}_outside_noise", z and z["outside_noise"], z and z["n_days"])
        for k, z in c["vs_placebo"].items():
            name = k.replace("_ret", "_return_pp")
            add(c, f"shift_{name}", z and z["mean"], z and z["n_days"])
            add(c, f"shift_{name}_se", z and z["se"], z and z["n_days"])
            add(c, f"shift_{name}_outside_noise", z and z["outside_noise"], z and z["n_days"])
        n = b["n_usable"]
        add(c, "pasted_annualised_strict_share", round(b["pasted_strict_n"] / n, 3), n)
        add(c, "pasted_annualised_broad_share", round(b["pasted_broad_n"] / n, 3), n)
        for a in ARMS:
            pa = b["per_arm"][a]
            add(c, f"pasted_annualised_strict_share_{a}", round(pa["pasted_strict"] / pa["n"], 3) if pa["n"] else None, pa["n"])
            add(c, f"pasted_annualised_broad_share_{a}", round(pa["pasted_broad"] / pa["n"], 3) if pa["n"] else None, pa["n"])
        add(c, "runs_with_reasoning_text_share", round(c["n_runs_with_reasoning_text"] / n, 3), n)
        add(c, "reasoning_chars_per_run_mean", c["reasoning_chars_mean"], n)
        for rule in ("any", "exact"):
            for a in ("ALL",) + ARMS:
                z = c["mention"][rule][a]
                sfx = "" if a == "ALL" else f"_{a}"
                add(c, f"reasoning_mentions_annualised_{rule}_share{sfx}",
                    round(z["n_mention"] / z["n_runs"], 3) if z["n_runs"] else None, z["n_runs"])
                add(c, f"among_mention_{rule}_submits_annualised_strict_share{sfx}",
                    round(z["n_mention_pasted_strict"] / z["n_mention"], 3) if z["n_mention"] else None, z["n_mention"])
                add(c, f"among_mention_{rule}_submits_annualised_broad_share{sfx}",
                    round(z["n_mention_pasted_broad"] / z["n_mention"], 3) if z["n_mention"] else None, z["n_mention"])
                add(c, f"pasted_broad_without_mention_{rule}{sfx}", z["n_pasted_broad_without_mention"], z["n_runs"])
        if c["risk_budget"]:
            for a, (k, nn) in c["risk_budget"].items():
                add(c, "harness_called_get_risk_budget_share" + ("" if a == "ALL" else f"_{a}"), round(k / nn, 3) if nn else None, nn)
        add(c, "mean_tool_calls_or_commands_finished", b["mean_tool_calls_finished"], b["n_finished"])
        add(c, "mean_tool_calls_or_commands_usable", b["mean_tool_calls_usable"], n)
        cv = b["computed_vol_in_code"]
        if cv:
            add(c, "computed_vol_from_prices_csv_share", round(cv["n"] / cv["of"], 3), cv["of"])
        add(c, "mean_abs_ln_vol_forecast_over_realised5d", b["acc_mean_abs_log_err"], n)
        add(c, "mean_ln_vol_forecast_over_realised5d_bias", b["acc_bias_log"], n)
        add(c, "mean_abs_ln_vol_err_se_over_days", b["acc_se_over_days"], len(b["acc_day_means"]))
        for a in ARMS:
            add(c, f"mean_abs_ln_vol_forecast_over_realised5d_{a}", b["per_arm"][a]["mean_abs_log_err"], b["per_arm"][a]["n"])
    for k, bl in DS.baselines(info).items():
        R.append({"model": f"baseline: {k}", "framework": "-", "metric": "mean_abs_ln_vol_forecast_over_realised5d",
                  "value": bl["mean_abs_log_err"], "n": len(info)})
        R.append({"model": f"baseline: {k}", "framework": "-", "metric": "mean_ln_vol_forecast_over_realised5d_bias",
                  "value": bl["bias_log"], "n": len(info)})
    return R


fs = DS.fmt_shift                                                               # a shift table cell


def frac(a, b):
    return f"{a}/{b}" if b else "-"


def rb_cell(rb):
    if not rb:
        return "-"
    return f"{rb['ALL'][0]}/{rb['ALL'][1]} ({rb['UNIT5D'][0]}/{rb['UNIT5D'][1]})"


def tables(cells: list[dict], info: dict) -> str:
    L = ["Volatility forecast: ORIG noise and within-day shifts in ln(expected_vol_pct); days in brackets; * = |mean| > 2 SE.", "",
         "| model / framework | usable / finished | ORIG run-to-run abs diff (pairs) | NOLABEL | UNIT5D | PLACEBO | NOLABEL - PLACEBO | UNIT5D - PLACEBO |",
         "|" + "---|" * 8]
    for c in cells:
        s, v = c["base"]["shifts"], c["vs_placebo"]
        L.append(f"| {c['label']} | {c['base']['n_usable']}/{c['base']['n_finished']} | {s['orig_rr_abs_dlnvol']:.2f} ({s['n_orig_pairs']}) | "
                 f"{fs(s['NOLABEL_v'])} | {fs(s['UNIT5D_v'])} | {fs(s['PLACEBO_v'])} | {fs(v['NOLABEL_minus_PLACEBO_lnvol'])} | "
                 f"{fs(v['UNIT5D_minus_PLACEBO_lnvol'])} |")
    L += ["", "Return forecast: the same in expected_return_pct, percentage points.", "",
          "| model / framework | ORIG run-to-run abs diff | NOLABEL | UNIT5D | PLACEBO | NOLABEL - PLACEBO | UNIT5D - PLACEBO |",
          "|" + "---|" * 7]
    for c in cells:
        s, v = c["base"]["shifts"], c["vs_placebo"]
        L.append(f"| {c['label']} | {s['orig_rr_abs_dret']:.2f} | {fs(s['NOLABEL_r'])} | {fs(s['UNIT5D_r'])} | {fs(s['PLACEBO_r'])} | "
                 f"{fs(v['NOLABEL_minus_PLACEBO_ret'])} | {fs(v['UNIT5D_minus_PLACEBO_ret'])} |")
    L += ["", "Annualised figure submitted as the 5-day vol: strict (broad), out of the usable runs of that arm.", "",
          "| model / framework | all | ORIG | NOLABEL | UNIT5D | PLACEBO |", "|---|---|---|---|---|---|"]
    for c in cells:
        b = c["base"]
        pa = b["per_arm"]
        L.append(f"| {c['label']} | {b['pasted_strict_n']} ({b['pasted_broad_n']}) of {b['n_usable']} | " +
                 " | ".join(f"{pa[a]['pasted_strict']} ({pa[a]['pasted_broad']}) of {pa[a]['n']}" for a in ARMS) + " |")
    L += ["", "Reasoning output mentions an annualised figure (rule any; exact-value rule in brackets), and how many of those runs "
          "still submit it as the 5-day vol (strict / broad).", "",
          "| model / framework | runs with reasoning text | mention any (exact) | ORIG | NOLABEL | UNIT5D | PLACEBO | of those, submit it strict / broad | broad pastes without a mention | harness: called get_risk_budget, all (UNIT5D) |",
          "|" + "---|" * 10]
    for c in cells:
        A, E = c["mention"]["any"], c["mention"]["exact"]
        n = c["base"]["n_usable"]
        L.append(f"| {c['label']} | {c['n_runs_with_reasoning_text']}/{n} | {A['ALL']['n_mention']} ({E['ALL']['n_mention']}) of {n} | " +
                 " | ".join(f"{A[a]['n_mention']} ({E[a]['n_mention']}) of {A[a]['n_runs']}" for a in ARMS) +
                 f" | {A['ALL']['n_mention_pasted_strict']} / {A['ALL']['n_mention_pasted_broad']} of {A['ALL']['n_mention']} | "
                 f"{A['ALL']['n_pasted_broad_without_mention']} | {rb_cell(c['risk_budget'])} |")
    L += ["", "Work done and accuracy.", "",
          "| model / framework | mean tool calls / commands (finished; usable) | computed a vol from prices.csv | mean abs ln(forecast / realised 5d vol) (bias) [SE over days] | ORIG | NOLABEL | UNIT5D | PLACEBO |",
          "|" + "---|" * 8]
    for c in cells:
        b = c["base"]
        cv, pa = b["computed_vol_in_code"], b["per_arm"]
        L.append(f"| {c['label']} | {b['mean_tool_calls_finished']:.1f}; {b['mean_tool_calls_usable']:.1f} | "
                 f"{'-' if not cv else frac(cv['n'], cv['of'])} | {b['acc_mean_abs_log_err']:.2f} ({b['acc_bias_log']:+.2f}) "
                 f"[{b['acc_se_over_days']:.2f}] | " + " | ".join(f"{pa[a]['mean_abs_log_err']:.2f}" if pa[a]['mean_abs_log_err'] is not None
                                                                   else "-" for a in ARMS) + " |")
    for k, bl in DS.baselines(info).items():
        L.append(f"| baseline: {k} | | | {bl['mean_abs_log_err']:.2f} ({bl['bias_log']:+.2f}) | | | | |")
    return "\n".join(L)


def page(cells: list[dict], info: dict) -> str:
    """describe_reasoning_models.md."""
    return (HEAD + "\n## Tables\n\n" + tables(cells, info) + "\n\n" + NOTES + "\n## Rules added in this stage\n\n```\n" + RULES +
            "```\n\n" + TAIL)


# ------------------------------------------------------------------------------------------------ excerpts
# Chosen by hand after the tables, to illustrate the reasoning-vs-answer rows: two runs that mention an annualised figure and submit
# it (the two small Qwen models), two that mention it and convert it (Kimi; DeepSeek in UNIT5D, where the figure comes from the
# unrewritten get_risk_budget), the Kimi UNIT5D day with the largest shift, and one Qwen 27B Codex run that computed the vol in code.
# Every segment is checked to occur verbatim in the run's saved texts (reasoning; for X6 also the command output).
EXCERPTS = [
    ("X1", "qwen3_8b__coding_agent__CB_2026-04-22__ORIG__1", "reasoning",
     ["Considering the volatility stats, the 5-day volatility is around 12.6%, and the expected return might be slightly negative. "
      "The p_up for the next 5 days being above today's close could be around 0.4, with an expected return of -0.5% and volatility "
      "of 15%."],
     "12.6 is the annualised 10-day reading (ann_vol_10d_pct), read as a 5-day figure; its 5-day equivalent is 1.8."),
    ("X2", "qwen35_9b__coding_agent__CRWD_2026-08-27__ORIG__0", "reasoning",
     ["- Ann vol 10d: 105.4% (extremely high!)",
      "Forecast for next 5 trading days: 46% probability of finishing above current close, -1.5% expected return, 52% expected volatility",
      "- expected_vol_pct: 5-day one-sd in percent ✓"],
     "It checks the field definition after writing 52 and does not notice the unit."),
    ("X3", "kimi__coding_agent__VST_2026-05-06__ORIG__1", "reasoning",
     ["5-day vol estimate: ann vol 45% → 5-day sd = 45% × sqrt(5/252) ≈ 45% × 0.141 ≈ 6.35%."],
     "Mentions the annualised figure and converts it (Kimi's Codex reasoning arrives as summary text)."),
    ("X4", "kimi__harness__MRK_2026-05-07__UNIT5D__0", "reasoning",
     ["Vol 5-day equiv ~3.4-3.8%.", "Typical 5-day vol ~3.4% but I've been overstating. Set expected_vol ~2.8%."],
     "Same day ORIG runs submitted 5.5 and 4.5; ORIG run 0 used ATR x sqrt(5) ('5-day vol ≈ 2.65*sqrt(5)=5.9%'). 'Overstating' comes "
     "from the harness tool get_calibration_ledger, which this run called."),
    ("X5", "deepseek__harness__MCHP_2026-08-07__UNIT5D__0", "reasoning",
     ["Trailing 20d vol 74.1% annualized — very high.",
      "20d annualized 74% → 5-day = 74*sqrt(5/252) = 74*0.1409 = 10.4%. That's already the trailing. Given high vol regime and "
      "understating tendency, maybe use 11-12%. I'll say 11."],
     "UNIT5D shows only 5-day equivalents in the readings; 74.1 is get_risk_budget's trailing_vol_20d_pct, which the arm does not rewrite."),
    ("X6", "qwen38_27b__coding_agent__CRWD_2026-08-27__ORIG__0", "command output + reasoning",
     ["implied 5d 1sd from 10d daily vol: 16.80%", "implied 5d 1sd from 20d daily vol: 12.46%",
      "5-day 1σ: about 12.5% (20-day implied) to about 16.8% (10-day implied); I'll use 14%."],
     "Its own script on prices.csv printed the two 5-day figures (first two quotes), then the reasoning picked a value between them."),
]


def text_pool(run_dir: Path, framework: str) -> str:
    """Everything an excerpt may quote: the reasoning, plus the tool results (harness) or command outputs (Codex)."""
    parts = reasoning_items(run_dir, framework)
    if framework == "harness":
        with gzip.open(run_dir / "session.json.gz") as f:
            parts += [str(t.get("result")) for t in json.load(f)["trace"] if "tool" in t]
    else:
        for p in sorted((run_dir / "codex_sessions").rglob("*.jsonl")):
            with open(p, encoding="utf-8") as f:
                for ln in f:
                    q = json.loads(ln).get("payload") or {}
                    if q.get("type") == "function_call_output":
                        o = q.get("output")
                        parts.append(o if isinstance(o, str) else json.dumps(o))
    return "\n".join(parts)


def excerpts(recs: dict, info: dict, raw: Path) -> list[dict]:
    """examples_reasoning_models.json; every segment must occur verbatim in its run's saved texts."""
    out = []
    for xid, rid, src, segs, note in EXCERPTS:
        x = recs[rid]
        run_dir, d = raw / rid, info[x["day_id"]]
        pool = text_pool(run_dir, x["framework"])
        for s in segs:
            if s not in pool:
                raise ValueError(f"excerpt {xid}: segment not found in {rid}: {s!r}")
        ex = " … ".join(f'"{s}"' for s in segs)
        if len(ex) >= 400:
            raise ValueError(f"excerpt {xid} is {len(ex)} characters (limit 400)")
        dec = x["decision"]
        st, br = DS.pasted(dec["expected_vol_pct"], d)
        out.append({"id": xid, "model": LABEL[x["model"]], "framework": FW_LABEL[x["framework"]], "day": x["day_id"], "arm": x["arm"],
                    "run_index": x["k"], "run_id": rid, "source": src, "excerpt": ex, "excerpt_chars": len(ex),
                    "final_answer": {k: dec[k] for k in ("action", "shares", "p_up", "expected_return_pct", "expected_vol_pct")},
                    "final_vol_is_annualised_strict_broad": [st, br],
                    "reasoning_mentions_annualised_any": mention("\n".join(reasoning_items(run_dir, x["framework"])), d)["any"],
                    "day_annualised_readings": d["ann"], "realised_5d_vol_pct_not_shown": round(d["rvol5"], 2), "note": note})
    return out


# ------------------------------------------------------------------------------------------------ consistency with describe.json
def check_against_describe(cells: list[dict], described: dict) -> int:
    """Checks that each cell's numbers equal the same cell of describe.json; returns the number of cells compared."""
    old = {(c["model"], c["framework"]): c for c in described["cells"]}
    n = 0
    for c in cells:
        o = old.get((c["model"], c["framework"]))
        if o is None:
            continue
        for k in ("n_usable", "pasted_strict_n", "pasted_broad_n", "acc_mean_abs_log_err", "acc_bias_log", "mean_tool_calls_finished",
                  "computed_vol_in_code", "shifts"):
            if o[k] != c["base"][k]:
                raise ValueError(f"{c['label']}: {k} differs from describe.json")
        n += 1
    return n


def build(recs: dict, info: dict, raw: Path) -> tuple[list[dict], str, list[dict], list[dict]]:
    """(cells, page markdown, metric records, excerpts) for the five models, in describe.MODEL_ORDER."""
    cells = [cell(m, f, recs, info, raw) for m in DS.MODEL_ORDER for f in DS.FW_ORDER]
    return cells, page(cells, info), to_records(cells, info), excerpts(recs, info, raw)
