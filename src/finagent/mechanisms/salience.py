"""SALIENCE: does the conspicuous annualised volatility number of get_volatility_stats (ann_vol_20d_pct, about 7x the
5-day scale) predict the agent's submitted 5-day expected_vol_pct beyond the rational 5-day sigma?

Three steps, as in the original analysis: (2) OLS of expected_vol_pct on the rational sigma, then with ann_vol_20d_pct
added; (3) the rare "looks-copied" sessions (expected_vol_pct within 15% of ann_vol_20d_pct) against everyone else on
|ln(expected_vol_pct / realised rv5)|; (5) FULL (news) against NO_NEWS, for b2 and for the copy rate. Six verbatim
example quotes are re-read from the raw session files and must be found there word for word.

Ported from the research workspace's results/mech4_20261023/salience/scripts/{extract,analyze,finalize,
build_data_json}.py: the same filters, the same file order and the same numpy/pandas operations, so every number comes
out bit-identical. build() returns the full data.json content; main() writes results/mechanisms/salience/data.json.

Inputs, all under config.DATA (data/mechanisms/salience/README.md has their sources and sha256):
  mechanisms/sessions/newsagent/<day_id>/{FULL,NO_NEWS}_<k>.json.gz        primary corpus, Qwen3.5-9B
  mechanisms/sessions/q3news_s1/<day_id>/{FULL,NO_NEWS}_<k>.json.gz        cross-check, Qwen3-8B with thinking on
  mechanisms/salience/grounding_A_main/<day_id>/{FULL_G,NO_NEWS_G}_<k>.json.gz   scanned; 0 usable sessions
  mechanisms/salience/rcf_20261011/{events_all,nonevent_days}.parquet, rule.json  the rational 5-day sigma
  panel/us_daily_stratos_20260924.parquet (config.PANEL)                    closes for the realised 5-day vol rv5
"""
from __future__ import annotations

import argparse
import gzip
import json
import math
import os
import re
from pathlib import Path

import numpy as np
import pandas as pd

from finagent import config
from finagent.mechanisms import salience_text as T

SESSIONS = config.DATA / "mechanisms" / "sessions"
NEWSAGENT = SESSIONS / "newsagent"
Q3NEWS = SESSIONS / "q3news_s1"
INPUTS = config.DATA / "mechanisms" / "salience"
GROUNDING = INPUTS / "grounding_A_main"
RCF = INPUTS / "rcf_20261011"
EVENTS_ALL = RCF / "events_all.parquet"
NONEVENT_DAYS = RCF / "nonevent_days.parquet"
RULE_JSON = RCF / "rule.json"
OUT_DIR = config.RESULTS / "mechanisms" / "salience"
OUT_FILE = OUT_DIR / "data.json"

SUBMIT_FIELDS = ["action", "shares", "target_exposure_pct", "p_up", "expected_return_pct", "expected_vol_pct",
                 "confidence", "reasoning"]
VOL_FIELDS = ["ann_vol_10d_pct", "ann_vol_20d_pct", "ann_vol_60d_pct", "parkinson_vol_10d_pct"]
COPY_TOLERANCE = 0.15            # looks_copied: |expected_vol_pct - ann_vol_20d_pct| / ann_vol_20d_pct <= 0.15
VALIDATION_DAY = ("AAPL", "2026-03-19")


# ------------------------------------------------------------------------------------------------ session scan
def _load(path: Path) -> dict:
    with gzip.open(path, "rt") as f:
        return json.load(f)


def _tool_calls(trace: list, name: str) -> list[tuple[int, object, dict | None]]:
    """(trace index, args, parsed result) of every tool record of `name`, in trace order."""
    out = []
    for i, e in enumerate(trace):
        if isinstance(e, dict) and e.get("tool") == name:
            res, parsed = e.get("result"), None
            if isinstance(res, str):
                try:
                    parsed = json.loads(res)
                except Exception:
                    parsed = None
            elif isinstance(res, dict):
                parsed = res
            out.append((i, e.get("args"), parsed))
    return out


def extract_session(d: dict) -> tuple[dict | None, str | None]:
    """The fields this analysis needs from one loaded session, or (None, why it is not usable)."""
    trace = d.get("trace") or []
    submits = _tool_calls(trace, "submit_decision")
    if not submits:
        return None, "no_submit_decision"
    _, sub_args, _ = submits[-1]
    if not isinstance(sub_args, dict):
        return None, "submit_args_not_dict"
    if not all(f in sub_args for f in SUBMIT_FIELDS):
        return None, "submit_missing_fields"
    vol_calls = _tool_calls(trace, "get_volatility_stats")
    if not vol_calls:
        return None, "no_vol_stats_call"
    _, _, v_res = vol_calls[-1]                       # the last call, if there are several
    if not isinstance(v_res, dict):
        return None, "vol_stats_unparsable"
    if not all(f in v_res for f in VOL_FIELDS):
        return None, "vol_stats_missing_fields"
    try:
        expected_vol_pct = float(sub_args["expected_vol_pct"])
        for f in ("confidence", "p_up", "expected_return_pct"):
            float(sub_args[f])
    except Exception:
        return None, "submit_numeric_cast_fail"
    return {"ann_vol_20d_pct": v_res.get("ann_vol_20d_pct"), "expected_vol_pct": expected_vol_pct}, None


def plain_arm(stem: str) -> str | None:
    """newsagent / q3news file stem -> arm; the FULL_T06 temperature-robustness files are not scanned."""
    if stem.startswith("FULL_T06"):
        return None
    if stem.startswith("FULL_"):
        return "FULL"
    if stem.startswith("NO_NEWS_"):
        return "NO_NEWS"
    return None


def grounding_arm(stem: str) -> str | None:
    if stem.startswith("FULL_G_"):
        return "FULL"
    if stem.startswith("NO_NEWS_G_"):
        return "NO_NEWS"
    return None


def scan_corpus(root: Path, arm_of, census: dict | None = None) -> tuple[list[dict], dict[str, int], int]:
    """Every usable session of a corpus in sorted (day_id, file name) order, the skip reasons with their counts, and
    the number of FULL_T06 files left out. With `census`, also counts the tools each scanned session calls."""
    recs, skips, n_t06 = [], {}, 0
    for dd in sorted(os.listdir(root)):
        ddir = root / dd
        if not ddir.is_dir() or "_" not in dd:
            continue
        ticker, day = dd.split("_", 1)
        for fn in sorted(os.listdir(ddir)):
            if not fn.endswith(".json.gz"):
                continue
            stem = fn[: -len(".json.gz")]
            arm = arm_of(stem)
            if arm is None:
                n_t06 += stem.startswith("FULL_T06")
                continue
            m = re.search(r"_(\d+)$", stem)
            k = int(m.group(1)) if m else None
            try:
                d = _load(ddir / fn)
            except Exception as ex:
                skips[f"load_error:{ex}"] = skips.get(f"load_error:{ex}", 0) + 1
                continue
            if census is not None:
                _count_tools(d, census)
            rec, err = extract_session(d)
            if rec is None:
                skips[err] = skips.get(err, 0) + 1
                continue
            recs.append({"arm": arm, "day_id": dd, "ticker": ticker, "day": day, "k": k, **rec})
    return recs, skips, n_t06


def _count_tools(d: dict, census: dict) -> None:
    tools = [e["tool"] for e in d.get("trace", []) if isinstance(e, dict) and "tool" in e]
    census["n_files"] += 1
    census["n_only_submit"] += set(tools) == {"submit_decision"}
    census["n_risk_budget"] += "get_risk_budget" in tools
    census["n_vol_stats"] += "get_volatility_stats" in tools


# ------------------------------------------------------------------------------------------------ benchmark and rv5
class Benchmark:
    """The rational 5-day sigma of a day (events_all first, nonevent_days as fallback) and the realised 5-day vol."""

    def __init__(self, tickers):
        ev = pd.read_parquet(EVENTS_ALL)
        ne = pd.read_parquet(NONEVENT_DAYS).copy()
        self.ev_sigma = dict(zip(ev["event_id"], ev["sigma"]))
        self.ev_R5 = dict(zip(ev["event_id"], ev["R5"]))
        ne["day_id"] = ne["ticker"] + "_" + ne["t"].astype(str)
        ne["sigma_ne"] = np.exp(ne["lsig"])
        self.ne_sigma = dict(zip(ne["day_id"], ne["sigma_ne"]))
        panel = pd.read_parquet(config.PANEL, columns=["Ticker", "Date", "Close"])
        panel = panel[panel["Ticker"].isin(sorted(set(tickers)))].copy()
        panel["Date"] = pd.to_datetime(panel["Date"])
        panel = panel.sort_values(["Ticker", "Date"]).reset_index(drop=True)
        self.px = {}
        for tk, g in panel.groupby("Ticker"):
            g = g.reset_index(drop=True)
            self.px[tk] = {"dates": g["Date"].dt.strftime("%Y-%m-%d").to_numpy(), "close": g["Close"].to_numpy()}

    def sigma(self, day_id: str) -> tuple[float | None, str]:
        if day_id in self.ev_sigma:
            return self.ev_sigma[day_id], "events_all"
        if day_id in self.ne_sigma:
            return self.ne_sigma[day_id], "nonevent_days"
        return None, "miss"

    def _closes(self, ticker: str, day: str) -> np.ndarray | None:
        info = self.px.get(ticker)
        if info is None:
            return None
        idx = np.where(info["dates"] == day)[0]
        if len(idx) == 0 or idx[0] + 5 >= len(info["close"]):
            return None
        closes = info["close"][idx[0]:idx[0] + 6]
        if np.any(closes <= 0) or np.any(~np.isfinite(closes)):
            return None
        return closes

    def log_returns_pct(self, ticker: str, day: str) -> np.ndarray | None:
        closes = self._closes(ticker, day)
        return None if closes is None else 100.0 * np.diff(np.log(closes))

    def rv5(self, ticker: str, day: str) -> float | None:
        """sqrt of the sum of the 5 squared daily log returns (percent), close t to close t+5."""
        lr = self.log_returns_pct(ticker, day)
        return None if lr is None else float(np.sqrt(np.sum(lr ** 2)))


def enrich(recs: list[dict], bm: Benchmark) -> list[dict]:
    for r in recs:
        r["rational_sigma5_pct"], r["sigma_join_source"] = bm.sigma(r["day_id"])
        r["rv5_realised_pct"] = bm.rv5(r["ticker"], r["day"])
    return recs


# ------------------------------------------------------------------------------------------------ statistics
def ols_fit(X: np.ndarray, y: np.ndarray) -> dict:
    """Closed-form OLS with an intercept (added here): classical and HC1-robust standard errors."""
    n = X.shape[0]
    Xc = np.column_stack([np.ones(n), X])
    p = Xc.shape[1]
    XtX_inv = np.linalg.inv(Xc.T @ Xc)
    beta = XtX_inv @ Xc.T @ y
    resid = y - Xc @ beta
    rss = float(resid @ resid)
    tss = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - rss / tss if tss > 0 else float("nan")
    dof = n - p
    sigma2 = rss / dof if dof > 0 else float("nan")
    se = np.sqrt(np.diag(sigma2 * XtX_inv))
    meat = Xc.T @ np.diag(resid ** 2) @ Xc
    cov_hc1 = (n / dof) * XtX_inv @ meat @ XtX_inv if dof > 0 else np.full((p, p), np.nan)
    se_hc1 = np.sqrt(np.diag(cov_hc1))
    return {"n": n, "p": p, "beta": beta.tolist(), "se": se.tolist(), "se_hc1_robust": se_hc1.tolist(), "r2": r2,
            "rss": rss, "dof": dof}


def p_two_sided_normal(stat: float) -> float:
    """Two-sided p-value under a normal approximation (no scipy; dof is in the hundreds here)."""
    return min(1.0, 2 * (0.5 * (1 - math.erf(abs(stat) / math.sqrt(2)))))


def regression_block(df: pd.DataFrame) -> dict:
    """Model 1: expected_vol_pct ~ a + b1*sigma; model 2 adds b2*ann_vol_20d_pct."""
    sub = df.dropna(subset=["expected_vol_pct", "rational_sigma5_pct", "ann_vol_20d_pct"])
    y = sub["expected_vol_pct"].to_numpy(dtype=float)
    sigma_r = sub["rational_sigma5_pct"].to_numpy(dtype=float)
    annv = sub["ann_vol_20d_pct"].to_numpy(dtype=float)
    m1 = ols_fit(sigma_r.reshape(-1, 1), y)
    m2 = ols_fit(np.column_stack([sigma_r, annv]), y)

    def named(m, names):
        out = {}
        for i, nm in enumerate(names):
            t = m["beta"][i] / m["se"][i] if m["se"][i] > 0 else None
            out[nm] = {"coef": m["beta"][i], "se": m["se"][i], "se_hc1": m["se_hc1_robust"][i], "t": t,
                       "p_approx_normal": p_two_sided_normal(t) if t is not None else None}
        return out

    n1, n2 = ["intercept", "b1_rational_sigma5"], ["intercept", "b1_rational_sigma5", "b2_ann_vol_20d_pct"]
    return {
        "n": int(m1["n"]),
        "model1_sigma_only": {"names": n1, "coefs": named(m1, n1), "r2": m1["r2"], "dof": m1["dof"]},
        "model2_sigma_plus_annvol20": {"names": n2, "coefs": named(m2, n2), "r2": m2["r2"], "dof": m2["dof"]},
        "delta_r2": m2["r2"] - m1["r2"],
    }


def _with_rv5(df: pd.DataFrame) -> pd.DataFrame:
    sub = df.dropna(subset=["expected_vol_pct", "ann_vol_20d_pct", "rv5_realised_pct"]).copy()
    return sub[sub["rv5_realised_pct"] > 0]


def _looks_copied(sub: pd.DataFrame) -> pd.Series:
    return (sub["expected_vol_pct"] - sub["ann_vol_20d_pct"]).abs() / sub["ann_vol_20d_pct"] <= COPY_TOLERANCE


def copied_analysis(df: pd.DataFrame) -> dict:
    """Looks-copied against not-copied sessions on |ln(expected_vol_pct / rv5)|, with a Welch-style SE of the gap."""
    sub = _with_rv5(df)
    sub["looks_copied"] = _looks_copied(sub)
    sub["ln_ratio_abs_err"] = (np.log(sub["expected_vol_pct"] / sub["rv5_realised_pct"])).abs()
    out = {"n_total_with_rv5": int(len(sub))}
    for grp_name, grp_val in [("copied", True), ("not_copied", False)]:
        g = sub[sub["looks_copied"] == grp_val]
        n = len(g)
        out[grp_name] = {"n": int(n), "pct_of_total": 100.0 * n / len(sub) if len(sub) else None,
                         "mean_abs_ln_ratio_error": float(g["ln_ratio_abs_err"].mean()) if n > 0 else None,
                         "se": float(g["ln_ratio_abs_err"].std(ddof=1) / math.sqrt(n)) if n > 1 else None}
    c, nc = out["copied"], out["not_copied"]
    if c["n"] > 1 and nc["n"] > 1:
        diff = c["mean_abs_ln_ratio_error"] - nc["mean_abs_ln_ratio_error"]
        se_diff = math.sqrt(c["se"] ** 2 + nc["se"] ** 2)
        out["diff_copied_minus_not"] = {"diff": diff, "se": se_diff, "t": diff / se_diff if se_diff > 0 else None}
    return out


def copy_rate_test(df_full: pd.DataFrame, df_nonews: pd.DataFrame) -> dict:
    """Two-proportion z-test (pooled SE) on the looks-copied rate, FULL against NO_NEWS."""
    def k_n(df):
        sub = _with_rv5(df)
        return int(_looks_copied(sub).sum()), len(sub)
    (k1, n1), (k2, n2) = k_n(df_full), k_n(df_nonews)
    p1, p2 = k1 / n1, k2 / n2
    p_pool = (k1 + k2) / (n1 + n2)
    se_pool = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    z = (p1 - p2) / se_pool if se_pool > 0 else None
    return {
        "FULL": {"k_copied": k1, "n": n1, "rate": p1},
        "NO_NEWS": {"k_copied": k2, "n": n2, "rate": p2},
        "diff_FULL_minus_NO_NEWS": p1 - p2,
        "se_diff": se_pool,
        "z": z,
        "p_two_sided_normal_approx": 2 * 0.5 * (1 - math.erf(abs(z) / math.sqrt(2))) if z is not None else None,
        "note": T.STEP5_PROP_NOTE,
    }


# ------------------------------------------------------------------------------------------------ examples
def _submit_turn(path: Path) -> tuple[str, dict]:
    """The reasoning of the turn that called the (last) submit_decision, and that call's arguments."""
    trace = _load(path)["trace"]
    sub_idx = None
    for i, e in enumerate(trace):
        if isinstance(e, dict) and e.get("tool") == "submit_decision":
            sub_idx = i
    reasoning = None
    for i in range(sub_idx - 1, -1, -1):
        e = trace[i]
        if isinstance(e, dict) and "tool_calls" in e:
            if "submit_decision" in [tc.get("name") for tc in (e.get("tool_calls") or [])]:
                reasoning = e.get("reasoning")
                break
    return reasoning, trace[sub_idx]["args"]


_FMT = {"ann_vol_20d_pct": "{:.1f}", "expected_vol_pct": "{:.1f}", "rational_sigma5_pct": "{:.2f}",
        "rv5_realised_pct": "{:.2f}"}


def build_examples(recs: list[dict]) -> list[dict]:
    """Each example quote must occur verbatim in its session's submit-turn reasoning; each number its note quotes
    (EXPECT) must equal the computed one at the shown precision."""
    by_key = {(r["day_id"], r["arm"], r["k"]): r for r in recs}
    out = []
    for ex in T.EXAMPLES:
        path = NEWSAGENT / ex["day_id"] / f"{ex['arm']}_{ex['k']}.json.gz"
        reasoning, sub_args = _submit_turn(path)
        for q in ex["quotes"]:
            assert q in reasoning, f"quote not found verbatim in {config.rel(path)}: {q[:80]!r}"
        rec = by_key[(ex["day_id"], ex["arm"], ex["k"])]
        for field, shown in T.EXAMPLE_EXPECT[(ex["day_id"], ex["k"])].items():
            got = _FMT[field].format(rec[field])
            assert got == shown and shown in ex["note"], f"{ex['day_id']} k={ex['k']} {field}: {got} vs note {shown}"
        out.append({"kind": ex["kind"], "day_id": ex["day_id"], "ticker": ex["ticker"], "day": ex["day"],
                    "model": ex["model"], "arm": ex["arm"], "k": ex["k"], "session_file": config.rel(path),
                    "quotes": ex["quotes"], "submitted_expected_vol_pct": sub_args.get("expected_vol_pct"),
                    "note": ex["note"]})
    return out


# ------------------------------------------------------------------------------------------------ checks of the prose
def _check_inputs(bm: Benchmark, newsagent_days: list[str], n_t06: int) -> None:
    """The facts the method texts state: rule.json's definitions, the events_all misses, the rv5 date alignment."""
    rule = json.loads(RULE_JSON.read_text())["operationalization"]["target_and_bins"]
    for s in ("R5 = 100 ln(C[t+5]/C[t])", "sigma = exp(lsig)", "at close t", "u = (R5 - m)/sigma"):
        assert s in rule, f"rule.json target_and_bins no longer says {s!r}"
    misses = sorted(d for d in newsagent_days if d not in bm.ev_sigma)
    assert all(d in bm.ne_sigma for d in misses)
    assert f"{len(misses)}/{len(newsagent_days)} newsagent day_ids: {', '.join(misses)})" in T.JOIN_METHOD
    assert f"all {len(misses)} are present in nonevent_days" in T.JOIN_METHOD
    tk, day = VALIDATION_DAY
    s = float(np.sum(bm.log_returns_pct(tk, day)))
    dates = bm.px[tk]["dates"]
    i0 = int(np.where(dates == day)[0][0])
    r5 = bm.ev_R5[f"{tk}_{day}"]
    assert round(s, 6) == round(r5, 6)
    assert (f"from {day} to {dates[i0 + 5]} reproduces events_all.R5 = {r5:.6f} to 6 decimal places "
            f"({f'{s:.12f}'[:12]}...)") in T.RV5_VALIDATION
    assert f"{n_t06} files)" in T.PRIMARY_EXCLUDED


def _check_prose(d: dict, census: dict) -> None:
    """Every number the headline and limitation texts quote, re-derived from the computed values."""
    s2, s3, s5 = d["step2_regression_ols"], d["step3_copied_vs_not_copied"], d["step5_full_vs_nonews_salience_effect"]
    rf, rn, rq = s2["newsagent_FULL_primary"], s2["newsagent_NO_NEWS"], s2["q3news_S1_FULL_crosscheck"]

    def c(reg, model, name):
        return reg[model]["coefs"][name]
    b1f = c(rf, "model1_sigma_only", "b1_rational_sigma5")
    b2f, b2n, b2q = (c(r, "model2_sigma_plus_annvol20", "b2_ann_vol_20d_pct") for r in (rf, rn, rq))
    want = {T.STEP2_HEADLINE: [
        f"(newsagent FULL, n={rf['n']})", f"({b1f['coef']:.3f}, SE {b1f['se']:.3f}, t={b1f['t']:.2f})",
        f"model 1 R2={rf['model1_sigma_only']['r2']:.4f}",
        f"moves b2 to {b2f['coef']:.4f} (SE {b2f['se']:.4f}, t={b2f['t']:.2f}, not significant)",
        f"R2 to only {rf['model2_sigma_plus_annvol20']['r2']:.4f}", f"delta R2 = {rf['delta_r2']:.5f}",
        f"NO_NEWS (b2={b2n['coef']:+.4f}, SE {b2n['se']:.4f})", f"(b2={b2q['coef']:+.4f}, SE {b2q['se']:.4f})"]}

    cps = {k: s3[k] for k in ("newsagent_FULL", "newsagent_NO_NEWS", "newsagent_FULL_plus_NO_NEWS_combined")}
    full, nonews, comb = cps.values()
    ncop = [g["copied"]["n"] for g in cps.values()]
    want[T.STEP3_HEADLINE] = [
        *(f"{lab}: {g['copied']['n']}/{g['n_total_with_rv5']} = {g['copied']['pct_of_total']:.2f}%"
          for lab, g in zip(("FULL", "NO_NEWS", "combined"), cps.values())),
        f"combined = {comb['copied']['mean_abs_ln_ratio_error']:.2f} (SE {comb['copied']['se']:.3f})",
        f"vs {comb['not_copied']['mean_abs_ln_ratio_error']:.2f} (SE {comb['not_copied']['se']:.3f})",
        "a difference of {diff:.2f} (SE {se:.3f}, t={t:.2f})".format(**comb["diff_copied_minus_not"]),
        f"despite n={comb['copied']['n']}",
        *(f"e^{m:.2f}≈{math.exp(m):.1f}x" for m in (comb["copied"]["mean_abs_ln_ratio_error"],
                                                   comb["not_copied"]["mean_abs_ln_ratio_error"])),
        *("{lab} alone (diff={diff:.2f}, SE {se:.3f}, t={t:.2f}, n_copied={n})".format(
            lab=lab, n=g["copied"]["n"], **g["diff_copied_minus_not"])
          for lab, g in (("FULL", full), ("NO_NEWS", nonews))),
        f"({min(ncop)}-{max(ncop)})"]

    b2c, pt = s5["b2_comparison"], s5["copy_rate_two_proportion_test"]
    kc = [pt["FULL"]["k_copied"], pt["NO_NEWS"]["k_copied"]]
    want[T.STEP5_HEADLINE] = [
        f"(FULL {b2c['FULL']['b2']:+.4f} vs NO_NEWS {b2c['NO_NEWS']['b2']:+.4f}, diff "
        f"{b2c['diff_FULL_minus_NO_NEWS']:+.4f}, SE {b2c['se_diff']:.4f}, t={b2c['t']:.2f})",
        f"(FULL {100 * pt['FULL']['rate']:.2f}% vs NO_NEWS {100 * pt['NO_NEWS']['rate']:.2f}%, diff "
        f"{100 * pt['diff_FULL_minus_NO_NEWS']:+.2f}pp, SE {100 * pt['se_diff']:.2f}pp, z={pt['z']:.2f}, "
        f"p~{pt['p_two_sided_normal_approx']:.2f})", f"only {min(kc)}-{max(kc)} events per arm"]

    n = d["n_sessions_used"]
    b1m2 = c(rf, "model2_sigma_plus_annvol20", "b1_rational_sigma5")
    q1, q2 = c(rq, "model1_sigma_only", "b1_rational_sigma5"), c(rq, "model2_sigma_plus_annvol20", "b1_rational_sigma5")
    lim = d["limitations_and_open_questions"]
    want[lim[0]] = [f"({census['n_vol_stats']}/{census['n_files']} sessions call get_volatility_stats)"]
    want[lim[1]] = [f"({n['q3news_S1_FULL_crosscheck']} FULL / {n['q3news_S1_NO_NEWS_crosscheck']} NO_NEWS)"]
    want[lim[2]] = [f"({min(ncop)}-{max(ncop)} sessions depending on split)"]
    want[lim[3]] = [f"({b1f['coef']:.2f}-{b1m2['coef']:.2f} in newsagent vs {q1['coef']:.2f}-{q2['coef']:.2f} in "
                    f"q3news, overlapping confidence given q3news's wide SE of ~{q2['se']:.2f})"]
    for text, parts in want.items():
        for part in parts:
            assert part in text, f"prose no longer matches the computed value: {part!r}"


# ------------------------------------------------------------------------------------------------ assembly
def _clean(obj):
    """NaN/inf -> None, numpy scalars -> Python, keys sorted at every level (the original wrote sort_keys=True)."""
    if isinstance(obj, dict):
        return {k: _clean(obj[k]) for k in sorted(obj)}
    if isinstance(obj, (list, tuple)):
        return [_clean(v) for v in obj]
    if isinstance(obj, (float, np.floating)):
        v = float(obj)
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(obj, np.integer):
        return int(obj)
    return obj


def build() -> dict:
    newsagent, skips_news, n_t06 = scan_corpus(NEWSAGENT, plain_arm)
    q3news, skips_q3, _ = scan_corpus(Q3NEWS, plain_arm)
    census = {"n_files": 0, "n_only_submit": 0, "n_risk_budget": 0, "n_vol_stats": 0}
    grounding, skips_g, _ = scan_corpus(GROUNDING, grounding_arm, census)
    assert census["n_vol_stats"] == 0 and not grounding, "a grounding session now calls get_volatility_stats"

    everything = newsagent + q3news + grounding
    bm = Benchmark(r["ticker"] for r in everything)
    for recs in (newsagent, q3news, grounding):
        enrich(recs, bm)
    newsagent_days = sorted(p.name for p in NEWSAGENT.iterdir() if p.is_dir())
    _check_inputs(bm, newsagent_days, n_t06)

    n_total = len(everything)
    n_hit = sum(r["rational_sigma5_pct"] is not None for r in everything)
    n_hit_ev = sum(r["sigma_join_source"] == "events_all" for r in everything)
    n_hit_ne = sum(r["sigma_join_source"] == "nonevent_days" for r in everything)
    n_rv5 = sum(r["rv5_realised_pct"] is not None for r in everything)

    df_news_full = pd.DataFrame([r for r in newsagent if r["arm"] == "FULL"])
    df_news_nonews = pd.DataFrame([r for r in newsagent if r["arm"] == "NO_NEWS"])
    df_q3_full = pd.DataFrame([r for r in q3news if r["arm"] == "FULL"])
    n_news_full, n_news_nonews = len(df_news_full), len(df_news_nonews)
    n_q3_full = len(df_q3_full)
    n_q3_nonews = sum(r["arm"] == "NO_NEWS" for r in q3news)

    reg_full, reg_nonews, reg_q3_full = (regression_block(df) for df in (df_news_full, df_news_nonews, df_q3_full))
    b2 = {}
    for arm, reg in (("FULL", reg_full), ("NO_NEWS", reg_nonews)):
        cf = reg["model2_sigma_plus_annvol20"]["coefs"]["b2_ann_vol_20d_pct"]
        b2[arm] = {"b2": cf["coef"], "se": cf["se"], "n": reg["n"]}
    diff_b2 = b2["FULL"]["b2"] - b2["NO_NEWS"]["b2"]
    se_diff_b2 = math.sqrt(b2["FULL"]["se"] ** 2 + b2["NO_NEWS"]["se"] ** 2)

    data = {
        "task": T.TASK,
        "n_sessions_used": {
            "newsagent_FULL_primary": n_news_full,
            "newsagent_NO_NEWS": n_news_nonews,
            "newsagent_total": n_news_full + n_news_nonews,
            "q3news_S1_FULL_crosscheck": n_q3_full,
            "q3news_S1_NO_NEWS_crosscheck": n_q3_nonews,
            "grounding_A_main_usable": len(grounding),
        },
        "corpora": {
            "primary": {
                "name": config.rel(NEWSAGENT), "model": T.PRIMARY_MODEL, "arms_scanned": T.PRIMARY_ARMS,
                "excluded_from_scan": T.PRIMARY_EXCLUDED, "usability_filter": T.PRIMARY_FILTER,
                "n_usable": n_news_full + n_news_nonews, "n_skipped_and_why": skips_news,
                "n_files_scanned_total": n_news_full + n_news_nonews + sum(skips_news.values()),
            },
            "secondary_crosscheck": {
                "name": config.rel(Q3NEWS), "model": T.SECONDARY_MODEL, "n_usable": n_q3_full + n_q3_nonews,
                "n_skipped_and_why": skips_q3, "note": T.SECONDARY_NOTE,
            },
            "skipped_entirely": {
                "name": f"{config.rel(GROUNDING)} (FULL_G / NO_NEWS_G)", "model": T.GROUNDING_MODEL,
                "n_usable": len(grounding), "n_skipped_and_why": skips_g,
                "reason": T.GROUNDING_REASON.format(n_usable=len(grounding), **census),
            },
        },
        "rational_benchmark_join": {
            "method": T.JOIN_METHOD,
            "join_hit_rate": {"n_session_rows": n_total, "n_hit_total": n_hit, "hit_rate": n_hit / n_total,
                              "n_hit_via_events_all": n_hit_ev, "n_hit_via_nonevent_days_fallback": n_hit_ne},
            "sigma_scale_conversion": T.SIGMA_SCALE.format(rule_json=config.rel(RULE_JSON)),
        },
        "realised_5d_vol_method": {
            "definition": T.RV5_DEFINITION.format(panel=config.rel(config.PANEL)),
            "validation": T.RV5_VALIDATION,
            "n_sessions_with_rv5_computed": n_rv5,
            "why_rv5_not_abs_R5": T.RV5_WHY,
        },
        "step2_regression_ols": {
            "spec": T.STEP2_SPEC,
            "newsagent_FULL_primary": reg_full,
            "newsagent_NO_NEWS": reg_nonews,
            "q3news_S1_FULL_crosscheck": reg_q3_full,
            "headline_finding": T.STEP2_HEADLINE,
        },
        "step3_copied_vs_not_copied": {
            "definition": T.STEP3_DEFINITION,
            "accuracy_metric": T.STEP3_METRIC,
            "newsagent_FULL": copied_analysis(df_news_full),
            "newsagent_NO_NEWS": copied_analysis(df_news_nonews),
            "newsagent_FULL_plus_NO_NEWS_combined": copied_analysis(pd.DataFrame(newsagent)),
            "headline_finding": T.STEP3_HEADLINE,
            "reconciliation_with_step2": T.STEP3_RECONCILIATION,
        },
        "step5_full_vs_nonews_salience_effect": {
            "b2_comparison": {"FULL": b2["FULL"], "NO_NEWS": b2["NO_NEWS"], "diff_FULL_minus_NO_NEWS": diff_b2,
                              "se_diff": se_diff_b2, "t": diff_b2 / se_diff_b2 if se_diff_b2 else None},
            "copy_rate_two_proportion_test": copy_rate_test(df_news_full, df_news_nonews),
            "headline_finding": T.STEP5_HEADLINE,
        },
        "examples": build_examples(newsagent),
        "limitations_and_open_questions": T.LIMITATIONS,
    }
    data = _clean(data)
    _check_prose(data, census)
    return data


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="finagent mech-salience", description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", type=Path, default=OUT_FILE, help=f"output file (default {config.rel(OUT_FILE)})")
    ap.add_argument("--check", action="store_true", help="compare with --out instead of writing it (exit 1 if different)")
    args = ap.parse_args(argv)
    text = dumps(build())
    if args.check:
        same = args.out.is_file() and args.out.read_bytes() == text.encode("utf-8")
        print(f"{'same' if same else 'DIFFERENT':9s}  {config.rel(args.out)}")
        return 0 if same else 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text, encoding="utf-8")
    print(f"wrote {config.rel(args.out)} ({len(text.encode('utf-8'))} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
