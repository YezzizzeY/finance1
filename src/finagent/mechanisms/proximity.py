"""Proximity / recency (mechanism analysis 2 of 4): does a number's position in the tool-call sequence (how close it sits
to the final submit_decision) predict how much weight the agent gives it, independent of the number's magnitude?

Corpus: data/mechanisms/sessions/newsagent/<TICKER>_<date>/FULL_{0,1,2,3}.json.gz, the FULL arm at temperature 1.0
(FULL_T06_* files are left out), 250 ticker-days x up to 4 k-runs = 1000 session files. get_volatility_stats is a
deterministic function of the point-in-time price history, so every k-run of a day sees the same ann_vol_20d_pct; the
agent alone decides whether the call is the last one before submit_decision. That gives a same-day natural experiment
on calling position:

  extraction   tool-call records are trace entries with a "tool" key; a usable session is valid, calls
               get_volatility_stats exactly once (its JSON result has ann_vol_20d_pct) and submit_decision exactly once
               as its last tool call, with a numeric expected_vol_pct; is_last = no other tool call sits between the
               two (754 usable sessions; 128 days have both is_last groups, 420 sessions)
  step 2       OLS of expected_vol_pct on ann_vol_20d_pct in each is_last subsample of the matched days, the
               difference-of-slopes z-test, a day-demeaned (day fixed effects) level test, a paired per-day t-test,
               the mean expected/tool ratio by group, and the same slope test on the full unmatched pool
  step 3       get_volatility_stats.ann_vol_20d_pct against get_risk_budget.trailing_vol_20d_pct in the sessions that
               call each exactly once: the two are the same number (same formula, src/finagent/harness/toolbox.py),
               so the planned "closer to the later tool" test has nothing to compare
  confounds    does the number's magnitude predict position (z-test of group means), and session length by group
  examples     six real sessions in four examples, tool results and submit_decision arguments as stored

Ported from the original analysis scripts (extract / analyze / build_outputs, closed-form statistics in
finagent.mechanisms.proximity_stats); results/mechanisms/proximity/data.json is reproduced exactly. The prose fields
are constants; the counts they quote (0 of 250 days with a varying ann_vol_20d_pct, 11 of 1000 sessions that also call
get_event_risk, 31 registered tools, 32 of 32 identical step-3 pairs, which example session is last) are recomputed
and checked on every build.

    finagent mech-proximity              rebuild results/mechanisms/proximity/data.json
    finagent mech-proximity --out DIR    write DIR/data.json instead
    finagent mech-proximity --check      compare with the shipped data.json instead (exit 1 if different)
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np

from finagent import config
from finagent.mechanisms import proximity_stats as st

SESSIONS = config.DATA / "mechanisms" / "sessions" / "newsagent"
SESSIONS_REL = "data/mechanisms/sessions/newsagent"           # how data.json names the corpus (repository-relative)
OUT_DIR = config.RESULTS / "mechanisms" / "proximity"
DATA_JSON = OUT_DIR / "data.json"
FILE_GLOB = "*/FULL_[0-9].json.gz"                            # temperature 1.0 only; FULL_T06_* (0.6) do not match
TOOLBOX_REL = "src/finagent/harness/toolbox.py"
VOL, RISK, EVENT, SUBMIT = "get_volatility_stats", "get_risk_budget", "get_event_risk", "submit_decision"

# claims the constant prose below makes about the corpus and the toolset; build() recomputes each one
EXPECTED = dict(files=1000, days=250, days_vol_varies=0, vol_and_event_risk=11, tools=31, part3_pairs=32)

# (label, [(day_id, k)], is_last of each session) of the four examples (six sessions); is_last is checked for the pairs
EXAMPLES = [
    ("same_day_pair_A", [("HAL_2026-03-20", 1), ("HAL_2026-03-20", 2)], [True, False]),
    ("same_day_pair_B_opposite_direction", [("STX_2026-06-17", 1), ("STX_2026-06-17", 2)], [True, False]),
    ("part3_tie_illustration_1", [("ACN_2026-03-24", 3)], [False]),
    ("part3_tie_illustration_2", [("AAPL_2026-03-19", 1)], [False]),
]


# ------------------------------------------------------------------ extraction
def _load(path: Path) -> dict:
    with gzip.open(path, "rt") as f:
        return json.load(f)


def _parse_result(r):
    """Tool results are stored as JSON strings (sometimes already a dict)."""
    if isinstance(r, dict):
        return r
    if isinstance(r, str):
        try:
            return json.loads(r)
        except Exception:
            return None
    return None


def _tool_entries(trace: list) -> list[tuple]:
    """(index in trace, tool name, args, parsed result) of every trace entry that is a tool-call record (has "tool")."""
    return [(i, e["tool"], e.get("args"), _parse_result(e.get("result")))
            for i, e in enumerate(trace) if isinstance(e, dict) and "tool" in e]


def session_files() -> list[Path]:
    """The 1000 FULL temperature-1.0 session files, in the order of their repository-relative path."""
    return sorted(SESSIONS.glob(FILE_GLOB), key=lambda p: p.relative_to(SESSIONS).as_posix())


def extract() -> dict:
    """Walk every session file once: the part 1/2 records, the part 3 records, the skip reasons, and corpus counts."""
    files = session_files()
    records, records3, skip = [], [], {}

    def skipped(reason):
        skip[reason] = skip.get(reason, 0) + 1

    vol_and_event = 0
    for fp in files:
        d = _load(fp)
        names = [e["tool"] for e in d.get("trace", []) if "tool" in e]
        vol_and_event += VOL in names and EVENT in names         # co-occurrence over all files, valid or not
        if not d.get("valid", True):
            skipped("invalid")
            continue
        tools = _tool_entries(d.get("trace", []))
        if not tools:
            skipped("no_tools")
            continue
        submit_idx = [j for j, t in enumerate(tools) if t[1] == SUBMIT]
        if len(submit_idx) != 1:
            skipped("submit_not_1")
            continue
        submit_pos = submit_idx[0]
        if submit_pos != len(tools) - 1:
            skipped("submit_not_last")
            continue
        submit_args = tools[submit_pos][2]
        if not isinstance(submit_args, dict) or "expected_vol_pct" not in submit_args:
            skipped("submit_bad_args")
            continue
        expected_vol = submit_args.get("expected_vol_pct")
        vol_calls = [j for j, t in enumerate(tools) if t[1] == VOL]
        meta = dict(day_id=d.get("day_id"), k=d.get("k"), n_tool_calls_total=len(tools) - 1)   # minus submit_decision

        # part 1/2: exactly one get_volatility_stats call
        if len(vol_calls) == 1:
            jpos = vol_calls[0]
            res = tools[jpos][3]
            if isinstance(res, dict) and "ann_vol_20d_pct" in res and isinstance(expected_vol, (int, float)):
                records.append(dict(meta, ann_vol_20d_pct=res["ann_vol_20d_pct"], expected_vol_pct=expected_vol,
                                    is_last=(jpos == submit_pos - 1)))
            else:
                skipped("vol_result_bad")
        elif not vol_calls:
            skipped("no_vol_call")
        else:
            skipped("vol_called_multiple")

        # part 3: get_volatility_stats and get_risk_budget each exactly once
        rb_calls = [j for j, t in enumerate(tools) if t[1] == RISK]
        if len(vol_calls) == 1 and len(rb_calls) == 1 and isinstance(expected_vol, (int, float)):
            jv, jr = vol_calls[0], rb_calls[0]
            res_v, res_r = tools[jv][3], tools[jr][3]
            if (isinstance(res_v, dict) and "ann_vol_20d_pct" in res_v
                    and isinstance(res_r, dict) and "trailing_vol_20d_pct" in res_r):
                vol_v, vol_r = res_v["ann_vol_20d_pct"], res_r["trailing_vol_20d_pct"]
                later_is_v = jv > jr
                records3.append(dict(meta, expected_vol_pct=expected_vol, values_identical=(vol_v == vol_r),
                                     later_val=vol_v if later_is_v else vol_r, earlier_val=vol_r if later_is_v else vol_v))
    return dict(files=len(files), records=records, records3=records3, skip_reasons=skip, vol_and_event_risk=vol_and_event)


# ------------------------------------------------------------------ analysis
def _xy(group):
    return [r["ann_vol_20d_pct"] for r in group], [r["expected_vol_pct"] for r in group]


def _slope_fit(group, full=True):
    o = st.ols_simple(*_xy(group))
    if not full:
        return dict(n=o["n"], slope=o["slope"], slope_se=o["slope_se"], r=o["r"], p_slope=o["p_slope"])
    return dict(n=o["n"], slope=o["slope"], slope_se=o["slope_se"], intercept=o["intercept"], r=o["r"], r2=o["r2"],
                r_ci95=st.fisher_r_ci(o["r"], o["n"]), p_slope=o["p_slope"], df=o["df"])


def _diff(a, b):
    return st.diff_of_slopes_ztest(a["slope"], a["slope_se"], b["slope"], b["slope_se"])


def _ratio_stats(group):
    arr = np.array([r["expected_vol_pct"] / r["ann_vol_20d_pct"] for r in group if r["ann_vol_20d_pct"] > 0])
    n = len(arr)
    logs = np.log(arr)
    return dict(n=n, mean_ratio=float(arr.mean()), se_ratio=float(arr.std(ddof=1) / math.sqrt(n)),
                mean_log_ratio=float(logs.mean()), se_log_ratio=float(logs.std(ddof=1) / math.sqrt(n)))


def _within_day_level_test(day_group: dict) -> dict:
    """Day fixed effects (day-demeaned OLS of expected_vol_pct on the is_last dummy; df as reported = n - 2) and the
    unweighted paired per-day t-test on mean(is_last) - mean(not last)."""
    dy, dx, per_day = [], [], []
    for rs in day_group.values():
        ys = np.array([r["expected_vol_pct"] for r in rs], dtype=float)
        xs = np.array([1.0 if r["is_last"] else 0.0 for r in rs], dtype=float)
        dy.extend((ys - ys.mean()).tolist())
        dx.extend((xs - xs.mean()).tolist())
        yt = [r["expected_vol_pct"] for r in rs if r["is_last"]]
        yf = [r["expected_vol_pct"] for r in rs if not r["is_last"]]
        if yt and yf:
            per_day.append(float(np.mean(yt) - np.mean(yf)))
    fe = st.ols_simple(dx, dy)
    m, se, n = st.mean_se(per_day)
    t = m / se
    return dict(fe_regression=dict(n_obs=fe["n"], n_days=len(day_group), coef_is_last=fe["slope"], se=fe["slope_se"],
                                   t=fe["t_slope"], p=fe["p_slope"], df=fe["df"]),
                paired_per_day_unweighted=dict(n_days_with_both=n, mean_diff_true_minus_false=m, se=se, t=t, df=n - 1,
                                               p=st.student_t_pvalue_two_sided(t, n - 1)))


def _part3(records3: list[dict]) -> dict:
    """The planned log-distance test: is expected_vol_pct closer to the later-called tool's number? Pairs with identical
    numbers cannot say, nor can exact log-distance ties; the binomial test runs on what is left (nothing, here)."""
    rows = []
    for r in records3:
        if r["values_identical"] or min(r["expected_vol_pct"], r["later_val"], r["earlier_val"]) <= 0:
            continue
        d_later = abs(math.log(r["expected_vol_pct"]) - math.log(r["later_val"]))
        d_earlier = abs(math.log(r["expected_vol_pct"]) - math.log(r["earlier_val"]))
        rows.append(dict(closer_to_later=d_later < d_earlier, tie=d_later == d_earlier))
    usable = [r for r in rows if not r["tie"]]
    k = sum(r["closer_to_later"] for r in usable)
    out = dict(n_pairs=len(records3), n_identical=sum(r["values_identical"] for r in records3), n_usable=len(usable))
    if usable:
        out.update(k_closer_to_later=k, binomial_p=st.binomial_test_exact(k, len(usable)),
                   wilson_ci95=st.wilson_ci(k, len(usable)))
    return out


def _group_compare(recs: list[dict], field: str, with_n: bool) -> dict:
    """Mean and SE of a field by is_last group on the full pool, with a two-sample z-test."""
    mt, set_, nt = st.mean_se([r[field] for r in recs if r["is_last"]])
    mf, sef, nf = st.mean_se([r[field] for r in recs if not r["is_last"]])
    z = (mt - mf) / math.sqrt(set_ ** 2 + sef ** 2)
    true, false = dict(mean=mt, se=set_), dict(mean=mf, se=sef)
    if with_n:
        true["n"], false["n"] = nt, nf
    return dict(is_last_true_mean_se=true, is_last_false_mean_se=false, z=float(z),
                p_two_sided=float(st.norm_sf_two_sided(z)))


def _session_snapshot(day_id: str, k: int) -> dict:
    rel = f"{day_id}/FULL_{k}.json.gz"
    d = _load(SESSIONS / rel)
    tools = [(e["tool"], e.get("args"), e.get("result")) for e in d["trace"] if isinstance(e, dict) and "tool" in e]
    snap = dict(file=f"{SESSIONS_REL}/{rel}", day_id=d.get("day_id"), ticker=d.get("ticker"), day=d.get("day"),
                k=d.get("k"), tool_call_order=[t[0] for t in tools], get_volatility_stats_result=None,
                get_risk_budget_result=None, submit_decision_args=None)
    for name, args, res in tools:                   # the raw stored strings; the last call of each tool wins
        if name == VOL:
            snap["get_volatility_stats_result"] = res
        if name == RISK:
            snap["get_risk_budget_result"] = res
        if name == SUBMIT:
            snap["submit_decision_args"] = args
    return snap


def _check(name: str, got, want) -> None:
    if got != want:
        raise RuntimeError(f"proximity: {name} is {got!r}, the data.json prose says {want!r}; update the prose first")


def _check_claims(ex: dict, by_day: dict, part3: dict, examples: list[dict]) -> None:
    from finagent.harness import toolbox
    _check("files attempted", ex["files"], EXPECTED["files"])
    _check("days with a usable session", len(by_day), EXPECTED["days"])
    _check("days whose ann_vol_20d_pct varies across k-runs",
           sum(len({r["ann_vol_20d_pct"] for r in rs}) > 1 for rs in by_day.values()), EXPECTED["days_vol_varies"])
    _check("sessions calling both get_volatility_stats and get_event_risk", ex["vol_and_event_risk"],
           EXPECTED["vol_and_event_risk"])
    _check("registered tools", len(toolbox.TOOLS), EXPECTED["tools"])
    _check("step-3 pairs", part3["n_pairs"], EXPECTED["part3_pairs"])
    _check("step-3 identical pairs", part3["n_identical"], part3["n_pairs"])
    _check("step-3 usable pairs", part3["n_usable"], 0)
    is_last = {(r["day_id"], r["k"]): r["is_last"] for r in ex["records"]}
    for (label, sessions, want), block in zip(EXAMPLES, examples):
        if label.startswith("same_day_pair"):
            _check(f"{label} is_last", [is_last.get(s) for s in sessions], want)
        else:
            s = block["sessions"][0]
            _check(f"{label} tool values equal", json.loads(s["get_volatility_stats_result"])["ann_vol_20d_pct"],
                   json.loads(s["get_risk_budget_result"])["trailing_vol_20d_pct"])


def _sanitize(o):
    """NaN/inf -> None, and every dict with its keys sorted (the order data.json has always had)."""
    if isinstance(o, float):
        return None if (math.isnan(o) or math.isinf(o)) else o
    if isinstance(o, dict):
        return {k: _sanitize(o[k]) for k in sorted(o)}
    if isinstance(o, (list, tuple)):
        return [_sanitize(v) for v in o]
    return o


def build() -> dict:
    """The full content of results/mechanisms/proximity/data.json."""
    ex = extract()
    recs = ex["records"]
    by_day = defaultdict(list)
    for r in recs:
        by_day[r["day_id"]].append(r)
    matched_days, matched = [], []
    for day, rs in by_day.items():
        if any(r["is_last"] for r in rs) and any(not r["is_last"] for r in rs) and len(rs) >= 2:
            matched_days.append(day)
            matched.extend(rs)
    m_true = [r for r in matched if r["is_last"]]
    m_false = [r for r in matched if not r["is_last"]]
    fit_true, fit_false = _slope_fit(m_true), _slope_fit(m_false)
    all_true = _slope_fit([r for r in recs if r["is_last"]], full=False)
    all_false = _slope_fit([r for r in recs if not r["is_last"]], full=False)
    day_group = defaultdict(list)
    for r in matched:
        day_group[r["day_id"]].append(r)
    part3 = _part3(ex["records3"])
    examples = [dict(label=label, description=DESCRIPTIONS[label], sessions=[_session_snapshot(*s) for s in sessions])
                for label, sessions, _ in EXAMPLES]
    _check_claims(ex, by_day, part3, examples)

    confound = dict(PROSE["confound_discussion"])
    confound["check_1_does_magnitude_predict_position"] = dict(
        PROSE["check_1"], **_group_compare(recs, "ann_vol_20d_pct", with_n=True))
    confound["check_2_does_reliance_ratio_differ"] = PROSE["check_2"]
    confound["check_3_session_length_confound"] = dict(
        PROSE["check_3"], **_group_compare(recs, "n_tool_calls_total", with_n=False))

    data = {
        "_notes_added_2026-10-23": NOTES,
        "task": PROSE["task"],
        "corpus": PROSE["corpus"],
        "extraction_rules": PROSE["extraction_rules"],
        "sample_accounting": dict(
            files_attempted=ex["files"],
            skip_reasons=ex["skip_reasons"],
            n_usable_part1_2=len(recs),
            n_is_last_true=sum(1 for r in recs if r["is_last"]),
            n_is_last_false=sum(1 for r in recs if not r["is_last"]),
            n_distinct_days_represented=len(by_day),
            n_days_with_both_is_last_groups=len(matched_days),
            n_sessions_in_those_matched_days=len(matched),
            matched_day_ids=sorted(matched_days),
            key_structural_fact=PROSE["key_structural_fact"],
        ),
        "step2_results": dict(
            method=PROSE["step2_method"],
            is_last_true=fit_true,
            is_last_false=fit_false,
            difference_of_slopes_test=_diff(fit_true, fit_false),
            slope_ci95_overlap=st.ci_overlap(fit_true["slope"], fit_true["slope_se"],
                                             fit_false["slope"], fit_false["slope_se"]),
            within_day_fixed_effects_level_test=_within_day_level_test(day_group),
            mean_ratio_expected_vol_over_tool_value=dict(is_last_true=_ratio_stats(m_true),
                                                         is_last_false=_ratio_stats(m_false)),
            robustness_full_unmatched_pool=dict(is_last_true=all_true, is_last_false=all_false,
                                                diff_of_slopes_ztest=_diff(all_true, all_false)),
            headline=PROSE["step2_headline"],
        ),
        "step3_results": dict(
            planned_test=PROSE["step3_planned_test"],
            does_not_work=part3["n_usable"] == 0,
            reason=PROSE["step3_reason"],
            n_sessions_both_tools_once_each=part3["n_pairs"],
            n_identical=part3["n_identical"],
            identical_rate=f"{part3['n_identical']}/{part3['n_pairs']} = "
                           f"{100 * part3['n_identical'] / part3['n_pairs']:.0f}%",
        ),
        "confound_discussion": confound,
        "examples": examples,
        "stats_methods": PROSE["stats_methods"],
    }
    return _sanitize(data)


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent mech-proximity", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_DIR, help="folder for data.json (default: results/mechanisms/proximity)")
    ap.add_argument("--check", action="store_true", help="compare with --out/data.json instead of writing it (exit 1 if different)")
    args = ap.parse_args(argv)
    obj = build()
    if args.check:
        same = (args.out / "data.json").is_file() and (args.out / "data.json").read_bytes() == dumps(obj).encode("utf-8")
        print(f"{'same' if same else 'DIFFERENT':9s}  {config.rel(args.out / 'data.json')}")
        return 0 if same else 1
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "data.json").write_text(dumps(obj), encoding="utf-8")
    s2 = obj["step2_results"]
    print(f"proximity: {obj['sample_accounting']['n_usable_part1_2']} usable sessions, "
          f"{obj['sample_accounting']['n_days_with_both_is_last_groups']} matched days; slope difference "
          f"p={s2['difference_of_slopes_test']['p_two_sided']:.2f}, day fixed effects "
          f"p={s2['within_day_fixed_effects_level_test']['fe_regression']['p']:.2f} -> {config.rel(args.out / 'data.json')}")
    return 0


# ------------------------------------------------------------------ prose (constants, as in the original data.json)
NOTES = [
    "Independent verification found the day-fixed-effects regression's reported standard error used residual degrees "
    "of freedom = n-2 (418) rather than n minus the 128 day-dummy parameters (approx. 291). Recomputing with the correct "
    "df widens the SE slightly but does not change the conclusion: the coefficient (-0.122, originally reported SE "
    "0.360) is nowhere close to significant either way (p=0.73 at df=418; still far from significant at the smaller "
    "correct df). No headline number or conclusion changes."
]

PROSE = dict(
    task="Proximity/recency: does a number's position in the tool-call sequence (distance from submit_decision) "
         "predict how much weight the agent gives it, independent of the number's magnitude?",
    corpus=f"{SESSIONS_REL}, FULL arm, temperature=1.0 runs only (file pattern FULL_{{0,1,2,3}}.json.gz; the FULL_T06_* "
           "temperature-0.6 files were excluded per the task spec), 250 ticker-days x up to 4 k-runs = 1000 session "
           "files attempted.",
    extraction_rules=dict(
        is_last_definition="Among trace entries that are literal tool-call records (have a \"tool\" key -- this "
                           "excludes the separate \"turn\" entries that just list which tools the model decided to "
                           "call), get_volatility_stats is is_last=True iff it is the entry immediately preceding the "
                           "submit_decision tool-call entry, i.e. zero other tool-call entries sit between them.",
        usable_session_filter="d[\"valid\"] is True; trace parses; exactly one get_volatility_stats call; exactly one "
                              "submit_decision call and it is the final tool-call entry; submit_decision.args has a "
                              "numeric expected_vol_pct; get_volatility_stats's result JSON has ann_vol_20d_pct.",
        tool_result_parsing="Tool \"result\" fields are JSON-encoded strings; parsed with json.loads before reading "
                            "fields.",
    ),
    key_structural_fact="ann_vol_20d_pct is IDENTICAL across every k-run of the same day_id (checked all 250 days with "
                        ">=1 usable session: 0 days show any variation). This is expected -- the tool is a "
                        "deterministic function of the as_of price history, which is the same for every k-run of a "
                        "given ticker-day -- and it is what makes the matched-day design a clean natural experiment: "
                        "within a matched day, MAGNITUDE is held exactly fixed and only calling POSITION (and the "
                        "free-running generation) differs across k-runs.",
    step2_method="Within the 128 matched days (420 sessions), regress expected_vol_pct on ann_vol_20d_pct separately in "
                 "the is_last=True and is_last=False subsamples (simple OLS, closed-form, SE from residual variance). "
                 "Also run a day-fixed-effects regression (day-demean both variables then regress) and a plain paired "
                 "per-day mean-difference t-test, both of which exploit the fact that ann_vol_20d_pct is day-constant "
                 "to isolate the pure LEVEL effect of position, holding magnitude exactly fixed. Difference of the two "
                 "slopes tested with a Welch-style z-test (SE_diff = sqrt(se1^2+se2^2); scipy/statsmodels are not "
                 "installed in this venv, so p-values use a from-scratch Student-t CDF built on the regularized "
                 "incomplete-beta continued-fraction algorithm, validated against known reference values -- see "
                 "stats_methods below).",
    step2_headline="NO detectable position effect on reliance, by every cut tried: slope difference p=0.59 (matched "
                   "days) / p=0.67 (full unmatched pool); day-fixed-effects level test p=0.73; paired per-day t-test "
                   "p=0.55; the mean expected_vol_pct / ann_vol_20d_pct ratio is 0.223 (SE 0.014, n=162) when last vs "
                   "0.223 (SE 0.009, n=258) when not last -- indistinguishable. This is a genuine, reasonably powered "
                   "null (n=420 across 128 independently-matched days), not an absence of testing.",
    step3_planned_test="Compare, in log space, whether submitted expected_vol_pct sits closer to a LATER-called tool's "
                       "volatility number than an EARLIER-called one, using get_volatility_stats.ann_vol_20d_pct vs "
                       "get_risk_budget.trailing_vol_20d_pct as the task's suggested pair.",
    step3_reason="get_risk_budget.trailing_vol_20d_pct is computed by the identical formula as "
                 f"get_volatility_stats.ann_vol_20d_pct (_sd(returns[-20:]) * sqrt(252), see {TOOLBOX_REL}) on the "
                 "same as_of price history. In all n=32 sessions where both tools were each called exactly once, the "
                 "two reported numbers were EXACTLY equal (to the 1-decimal rounding both tools use). There is "
                 "therefore no pair of genuinely different numbers for the agent's answer to be \"closer to one than "
                 "the other\" -- the test is vacuous by construction, not underpowered. We checked the rest of the "
                 f"registered toolset ({TOOLBOX_REL}, 31 tools) for any other pair of distinct, comparable-scale "
                 "volatility-relevant outputs from two different tools: the only other candidate, "
                 "get_event_risk.avg_abs_daily_move_pct, co-occurs with get_volatility_stats in only 11/1000 sessions "
                 "(too few) and is on a different scale/definition (mean absolute daily return over the full history "
                 "vs. a 20-day realized stdev), which would introduce exactly the kind of forced, misleading "
                 "comparison the task asked us to avoid. We report the tie finding itself (n=32, 32/32 identical) "
                 "rather than substitute a confounded pair.",
    confound_discussion=dict(
        threat="Does the agent call get_volatility_stats LAST specifically WHEN it intends to rely on it most (a "
               "different causal story than \"position itself causes weight\")?",
        overall_assessment="The confound that the task flagged (intent-driven calling order) is not supported by the "
                           "two direct checks we could run (magnitude does not predict position; reliance ratio does "
                           "not differ by position). A second, different confound (session length/thoroughness) is "
                           "real and sizeable, but is moot for THIS result because the position effect itself was "
                           "null on every cut. We flag it because a future test with a positive finding on this "
                           "corpus would need to address it.",
    ),
    check_1=dict(
        description="Is ann_vol_20d_pct itself more extreme when the tool happens to be called last? (full unmatched "
                    "pool, n=754)",
        verdict="No (p=0.28) -- the magnitude of the number does not predict whether it gets called last.",
    ),
    check_2=dict(
        description="If the agent calls it last \"because it intends to rely on it most,\" the ratio "
                    "expected_vol_pct/ann_vol_20d_pct should be HIGHER when is_last=True. It is not: 0.223 "
                    "(is_last=True) vs 0.223 (is_last=False), see step2_results.",
        verdict="No detectable difference -- this specific version of the confound story is not supported by the data.",
    ),
    check_3=dict(
        description="Total tool calls per session (excluding submit_decision) differs sharply by is_last group: "
                    "sessions where get_volatility_stats is called last are systematically SHORTER sessions.",
        verdict="YES, real and large (p<1e-15) -- mechanically true in part because \"called last\" caps how many "
                "more calls can follow, but it also means is_last is confounded with \"this was a shorter, more "
                "decisive session\" in general, not purely with calling-position. We could not rule this out as an "
                "independent channel. It does not change the headline here (the effect we looked for was null "
                "anyway), but it means a different, positive-finding dataset using the same is_last design would "
                "still need to separately control for session length before attributing an effect to position per "
                "se.",
    ),
    stats_methods=dict(
        note="scipy and statsmodels are not installed in the project .venv; all statistics below are closed-form / "
             "numpy, implemented in src/finagent/mechanisms/proximity_stats.py.",
        ols="Simple OLS slope/intercept/SE from residual variance (textbook formulas), validated by the identity "
            "t_slope == t_r.",
        student_t_cdf="Regularized incomplete beta function via Lentz continued fraction (the classical "
                      "Numerical-Recipes algorithm scipy itself is built on); validated against known critical values "
                      "(t=2.228,df=10 -> p=0.0500; t=1.96,df=1000 -> p=0.0503).",
        fisher_z="Pearson r 95% CI via Fisher z-transform, SE=1/sqrt(n-3).",
        diff_of_slopes="Welch-style z-test on the difference of two independent slope estimates, "
                       "SE_diff=sqrt(se1^2+se2^2).",
        binomial_test="Exact two-sided binomial test via math.comb (same definition as scipy.stats.binomtest / R "
                      "binom.test), validated against a known value (k=15,n=20,p=.5 -> p=0.04139).",
        wilson_ci="Wilson score interval for a binomial proportion.",
    ),
)

DESCRIPTIONS = {
    "same_day_pair_A":
        "HAL_2026-03-20: FULL_1 calls get_volatility_stats as the LAST tool before submit_decision (is_last=True); "
        "FULL_2 calls simulate_order AFTER get_volatility_stats (is_last=False). Both see the identical "
        "ann_vol_20d_pct=30.1. In FULL_1 (last) the agent submits expected_vol_pct=30, almost exactly the raw tool "
        "number (ratio 1.00). In FULL_2 (not last) it submits expected_vol_pct=5.5 (ratio 0.18, close to the "
        "corpus-typical ~0.22). Taken alone this looks like a proximity effect in the \"last = more weight\" direction.",
    "same_day_pair_B_opposite_direction":
        "STX_2026-06-17: FULL_1 calls get_volatility_stats LAST before submit_decision (is_last=True) and submits "
        "expected_vol_pct=8.5 against ann_vol_20d_pct=65.7 (ratio 0.13). FULL_2 calls get_volume_analysis, "
        "get_support_resistance and get_risk_budget AFTER get_volatility_stats (is_last=False) and submits "
        "expected_vol_pct=28 (ratio 0.43) -- FARTHER from submit, yet CLOSER (proportionally) to the tool number, and "
        "its reasoning explicitly cites the get_risk_budget call made after get_volatility_stats (\"Risk budget "
        "severely exceeded (99.8% vs 23% max)\"). This is the opposite direction from pair A: it shows the within-day "
        "sign is not stable, consistent with the null result below rather than with either session being a "
        "confirming case on its own.",
    "part3_tie_illustration_1":
        "ACN_2026-03-24, FULL_3: get_volatility_stats is called, then get_risk_budget. ann_vol_20d_pct (from "
        "get_volatility_stats) = 42.9 and trailing_vol_20d_pct (from get_risk_budget) = 42.9 -- IDENTICAL to one "
        "decimal, because both tools run the exact same formula (_sd(returns[-20:]) * ANN) on the exact same as_of "
        f"price history (verified in {TOOLBOX_REL} lines ~174-182 and ~207-212). The submitted reasoning cites this "
        "single shared number directly: \"High volatility (42.9% ann)\". There is no second, independent number for "
        "the agent to be \"closer to\" -- the premise behind result 3 does not hold in this toolset.",
    "part3_tie_illustration_2":
        "AAPL_2026-03-19, FULL_1: same structural tie on a different ticker/day -- get_risk_budget.trailing_vol_20d_pct "
        "= 20.9 and get_volatility_stats.ann_vol_20d_pct = 20.9, exactly equal. Confirms the tie in example 3 is not a "
        "coincidence of one ticker.",
}


if __name__ == "__main__":
    raise SystemExit(main())
