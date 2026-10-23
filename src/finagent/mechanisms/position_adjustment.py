"""results/mechanisms/position_adjustment: do the agent's day-to-day exposure changes track what a Kelly-style
rational sizing rule implies, and does the tracking differ between quiet (|u|<1) and eventful (|u|>=2) days?

CPU only, no model calls. Ported from the research workspace's results/mech4_20261023/position_adjustment/build.py
(same joins, same k choice, same statistics, same worked-example selection); only the paths changed: every input is
read from data/mechanisms/position_adjustment/ (byte-identical copies, sources and sha256 in that folder's
README.md) and the output goes to results/mechanisms/position_adjustment/data.json.

  * Corpus: the BASE policy only (Qwen3.5-9B tool agent, default prompt), the six run-files of the audited day-to-day
    inventory -- base5d_{val_calm,val_stress,test_calm,test_crash,test_bear}.json plus the 2026-10-11 crash replicate
    (BASE_crash_R2.json). Twin-trajectory index g = (seed - 50000) % 100; exposure (a 0-1 fraction of the post-trade
    book) is multiplied by 100.
  * Rational benchmark: m, lsig, u joined by (ticker, day) from events_all.parquet (news-event days) or
    nonevent_days.parquet (no-news days); the two never cover the same (ticker, day). Only windows with a join hit
    rate above 5% are used (in practice test_calm alone: the benchmark covers 2025-10-02 to 2026-09-17).
  * rational_target_pct[t] = clip(k * m[t] / exp(lsig[t])**2, 0, 100), with k chosen so the std of the unclipped
    k*m/sigma^2 equals the std of the agent's exposure_pct on the joined days; k/2 and 2k as sensitivity.
  * delta_exposure and delta_rational over consecutive positions of one trajectory; OLS delta_exposure = a + b *
    delta_rational with HC1 and one-way cluster-robust (ticker, decision date) standard errors in closed form,
    Spearman rank correlation, and the ratio of the two standard deviations; overall, quiet, eventful and mid.

    finagent mech-position            write results/mechanisms/position_adjustment/data.json
    finagent mech-position --check    rebuild and compare with the shipped data.json (exit 1 if different)
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from finagent import config

DATA_DIR = config.DATA / "mechanisms" / "position_adjustment"
OUT_DIR = config.RESULTS / "mechanisms" / "position_adjustment"
OUT_FILE = OUT_DIR / "data.json"
DATA_LABEL = "data/mechanisms/position_adjustment"   # provenance prefix written into data.json (repository-relative)

# window -> run-file inside DATA_DIR (BASE policy; same six files and order as the workspace build)
BASE_FILES = {
    "val_calm": "base5d_val_calm.json",
    "val_stress": "base5d_val_stress.json",
    "test_calm": "base5d_test_calm.json",
    "test_crash": "base5d_test_crash.json",
    "test_bear": "base5d_test_bear.json",
    "test_crash_R2": "BASE_crash_R2.json",
}
EVENTS_FILE = "events_all.parquet"
NONEVENT_FILE = "nonevent_days.parquet"

QUIET_MAX = 1.0       # quiet: |u| < 1
EVENTFUL_MIN = 2.0    # eventful: |u| >= 2
USABLE_HIT_RATE = 0.05
MIN_ROWS = 5

METHOD = {
    "scope": "BASE policy only (Qwen3.5-9B tool agent, default prompt); files listed in base_files_loaded below",
    "rational_rule": "rational_target_pct[t] = clip(k * m[t] / exp(lsig[t])**2, 0, 100); delta_rational[t] = "
                     "rational_target[t] - rational_target[t-1] using the same k/clip",
    "k_choice": "k chosen so std(unclipped k*m/sigma^2) over the joined, usable sample equals std(agent exposure_pct) "
                "over that same sample; sensitivity to k reported via k_half/k_double and via Spearman rank "
                "correlation of the deltas, which is scale-invariant",
    "quiet_threshold": "|u| < 1.0 (u = standardized surprise from events_all/nonevent_days, at day t)",
    "eventful_threshold": "|u| >= 2.0",
}

LIMITATION = (
    "The rational-benchmark corpus (data/mechanisms/position_adjustment/events_all.parquet and nonevent_days.parquet) "
    "only covers calendar dates 2025-10-02 to 2026-09-17. Four of the five BASE trajectory windows (val_calm "
    "2023-10-02, val_stress 2024-07-22, test_crash 2025-04-01, test_bear 2022-05-02, plus the test_crash replicate) "
    "fall entirely outside that range and get a 0% rational join -- confirmed by direct check, not assumed. Only "
    "the test_calm window (2026-01-05 to 2026-01-26, 40 held-out stocks, 2 twin trajectories each) overlaps the "
    "benchmark's coverage, so ALL regression/ratio/rank numbers above come from that one window only. This is a "
    "real corpus-coverage constraint, not a bug: it is reported here rather than forcing a cross-window result."
)

K_NAMES = ("k_base", "k_half", "k_double")


# ------------------------------------------------------------------------------------------------ inputs
def input_paths() -> dict[str, Path]:
    """Every input file of the analysis, by name (the six run-files and the two benchmark parquets)."""
    out = {w: DATA_DIR / f for w, f in BASE_FILES.items()}
    out["events_all"] = DATA_DIR / EVENTS_FILE
    out["nonevent_days"] = DATA_DIR / NONEVENT_FILE
    return out


def load_run(window: str, path: Path) -> pd.DataFrame:
    """One run-file -> one row per agent-day: window, ticker, twin index g, position, day, exposure_pct, submitted."""
    d = json.loads(Path(path).read_text())
    rows = []
    for t in d["trajs"]:
        g = (int(t["seed"]) - 50_000) % 100          # twin-trajectory index (day-to-day inventory convention)
        for i, s in enumerate(t["steps"]):
            rows.append({"window": window, "ticker": t["ticker"], "g": g, "pos": i, "day": s["day"],
                         "exposure_pct": float(s.get("exposure") or 0.0) * 100.0,
                         "submitted": bool(s.get("submitted"))})
    return pd.DataFrame(rows)


def load_agent() -> pd.DataFrame:
    agent = pd.concat([load_run(w, DATA_DIR / f) for w, f in BASE_FILES.items()], ignore_index=True)
    agent["date"] = pd.to_datetime(agent["day"])
    return agent.sort_values(["window", "ticker", "g", "pos"]).reset_index(drop=True)


def load_benchmark() -> tuple[pd.DataFrame, int, dict]:
    """(rational table keyed by (ticker, day) with m, lsig, u, src; events/nonevent (ticker, day) overlap; source
    row counts). events_all.event_id must equal TICKER_date on every row."""
    ev = pd.read_parquet(DATA_DIR / EVENTS_FILE)[["event_id", "ticker", "t", "m", "lsig", "u"]].copy()
    ev["day"] = pd.to_datetime(ev["t"]).dt.strftime("%Y-%m-%d")
    ev["day_id"] = ev["ticker"] + "_" + ev["day"]
    if not (ev["event_id"] == ev["day_id"]).all():
        raise ValueError("events_all: event_id is not TICKER_date on every row")
    ev_dedup = ev.drop_duplicates(subset=["ticker", "day"])
    if len(ev_dedup) != len(ev):
        raise ValueError("events_all: duplicate (ticker, day)")

    ne = pd.read_parquet(DATA_DIR / NONEVENT_FILE)[["ticker", "t", "m", "lsig", "u"]].copy()
    ne["day"] = pd.to_datetime(ne["t"]).dt.strftime("%Y-%m-%d")
    ne_dedup = ne.drop_duplicates(subset=["ticker", "day"])
    if len(ne_dedup) != len(ne):
        raise ValueError("nonevent_days: duplicate (ticker, day)")

    key_ev = set(zip(ev_dedup["ticker"], ev_dedup["day"]))
    key_ne = set(zip(ne_dedup["ticker"], ne_dedup["day"]))
    overlap = len(key_ev & key_ne)

    rat = pd.concat([
        ev_dedup[["ticker", "day", "m", "lsig", "u"]].assign(src="events_all"),
        ne_dedup[["ticker", "day", "m", "lsig", "u"]].assign(src="nonevent"),
    ], ignore_index=True)
    # a (ticker, day) in both files would keep the events_all row (overlap is 0, so this never binds)
    rat = rat.sort_values("src").drop_duplicates(subset=["ticker", "day"], keep="first")
    return rat, overlap, {"events_all": len(ev), "nonevent_days": len(ne)}


# ------------------------------------------------------------------------------------------------ statistics
def ols_robust(y, x, cluster_a, cluster_b) -> dict:
    """OLS y = a + b x with HC1 and two one-way cluster-robust sandwich SEs (closed form, small-sample corrected)."""
    y = np.asarray(y, float)
    x = np.asarray(x, float)
    m = np.isfinite(y) & np.isfinite(x)
    y, x = y[m], x[m]
    ca = np.asarray(cluster_a)[m]
    cb = np.asarray(cluster_b)[m]
    n = len(y)
    X = np.column_stack([np.ones(n), x])
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ X.T @ y
    resid = y - X @ beta

    def sandwich(groups):
        codes, _ = pd.factorize(groups)
        G = codes.max() + 1
        meat = np.zeros((2, 2))
        for gidx in range(G):
            sel = codes == gidx
            s = X[sel].T @ resid[sel]
            meat += np.outer(s, s)
        V = XtX_inv @ meat @ XtX_inv
        dof_corr = (G / (G - 1)) * ((n - 1) / (n - 2)) if G > 1 and n > 2 else np.nan
        return V * dof_corr, G

    V_hc1 = (XtX_inv @ (X.T @ np.diag(resid ** 2) @ X) @ XtX_inv) * (n / (n - 2)) if n > 2 else np.full((2, 2), np.nan)
    V_ca, G_a = sandwich(ca)
    V_cb, G_b = sandwich(cb)
    se_hc1 = np.sqrt(np.diag(V_hc1))
    se_ca = np.sqrt(np.diag(V_ca))
    se_cb = np.sqrt(np.diag(V_cb))
    return {"a": float(beta[0]), "b": float(beta[1]), "n": int(n),
            "se_hc1": {"a": float(se_hc1[0]), "b": float(se_hc1[1])},
            "se_cluster_ticker": {"a": float(se_ca[0]), "b": float(se_ca[1]), "n_clusters": int(G_a)},
            "se_cluster_day": {"a": float(se_cb[0]), "b": float(se_cb[1]), "n_clusters": int(G_b)}}


def spearman(x, y) -> dict:
    """Spearman rank correlation (average ranks for ties) over the rows where both are finite."""
    x = np.asarray(x, float)
    y = np.asarray(y, float)
    m = np.isfinite(x) & np.isfinite(y)
    x, y = x[m], y[m]
    if m.sum() < 3:
        return {"rho": None, "n": int(m.sum())}
    rx = pd.Series(x).rank().to_numpy()
    ry = pd.Series(y).rank().to_numpy()
    return {"rho": float(np.corrcoef(rx, ry)[0, 1]), "n": int(m.sum())}


def std_ratio(agent_d, rat_d) -> dict:
    agent_d = np.asarray(agent_d, float)
    rat_d = np.asarray(rat_d, float)
    m = np.isfinite(agent_d) & np.isfinite(rat_d)
    a, r = agent_d[m], rat_d[m]
    sa, sr = float(np.std(a, ddof=1)), float(np.std(r, ddof=1))
    return {"std_agent": sa, "std_rational": sr, "ratio": sa / sr if sr else None, "n": int(m.sum())}


def block(df: pd.DataFrame) -> dict:
    return {"regression": ols_robust(df["delta_exposure"], df["delta_rational"], df["ticker"], df["day"]),
            "spearman_rank_corr": spearman(df["delta_exposure"], df["delta_rational"]),
            "std_ratio": std_ratio(df["delta_exposure"], df["delta_rational"])}


def block_or_note(df: pd.DataFrame) -> dict:
    return block(df) if len(df) >= MIN_ROWS else {"note": "too few rows", "n": int(len(df))}


# ------------------------------------------------------------------------------------------------ the analysis
def frames() -> dict:
    """Every intermediate the output is built from (agent-day table, coverage, usable-window table, k, ...)."""
    agent = load_agent()
    n_traj_total = agent.groupby(["window", "ticker", "g"]).ngroups
    n_days_total = len(agent)
    rat, overlap, n_source_rows = load_benchmark()

    cover_rows = []
    for w in BASE_FILES:
        pairs = agent.loc[agent["window"] == w, ["ticker", "day"]].drop_duplicates()
        merged = pairs.merge(rat, on=["ticker", "day"], how="left")
        hit = merged["m"].notna().sum()
        cover_rows.append({"window": w, "n_ticker_days": len(pairs), "n_matched": int(hit),
                           "hit_rate": float(hit / len(pairs)) if len(pairs) else None})
    coverage = pd.DataFrame(cover_rows)

    agent = agent.merge(rat, on=["ticker", "day"], how="left")
    match_rate_all = float(agent["m"].notna().mean())
    usable_windows = coverage.loc[coverage["hit_rate"] > USABLE_HIT_RATE, "window"].tolist()

    use = agent[agent["window"].isin(usable_windows)].copy()
    sigma_rat = np.exp(use["lsig"])
    m_over_s2 = use["m"] / (sigma_rat ** 2)
    joined = use["m"].notna()
    k_base = float(use.loc[joined, "exposure_pct"].std() / m_over_s2[joined].std())
    ks = {"k_base": k_base, "k_half": k_base / 2, "k_double": k_base * 2}
    for name in K_NAMES:
        use[f"rat_target_{name}"] = (ks[name] * use["m"] / (sigma_rat ** 2)).clip(lower=0.0, upper=100.0)
    use["rat_target"] = use["rat_target_k_base"]
    n_clipped_lo = int((k_base * m_over_s2 < 0).sum())
    n_clipped_hi = int((k_base * m_over_s2 > 100).sum())

    use = use.sort_values(["window", "ticker", "g", "pos"]).reset_index(drop=True)
    grp = use.groupby(["window", "ticker", "g"])
    use["exposure_prev"] = grp["exposure_pct"].shift(1)
    use["pos_prev"] = grp["pos"].shift(1)
    use["consec"] = use["pos_prev"] == use["pos"] - 1
    use["delta_exposure"] = np.where(use["consec"], use["exposure_pct"] - use["exposure_prev"], np.nan)
    for name in K_NAMES:
        prev = grp[f"rat_target_{name}"].shift(1)
        use[f"delta_rational_{name}"] = np.where(use["consec"], use[f"rat_target_{name}"] - prev, np.nan)
    use["delta_rational"] = use["delta_rational_k_base"]
    use["u_abs"] = use["u"].abs()

    return {"agent": agent, "coverage": coverage, "rat": rat, "overlap": overlap, "n_source_rows": n_source_rows,
            "n_traj_total": n_traj_total, "n_days_total": n_days_total, "match_rate_all": match_rate_all,
            "usable_windows": usable_windows, "use": use, "ks": ks,
            "n_clipped_lo": n_clipped_lo, "n_clipped_hi": n_clipped_hi}


def _r2(v):
    return None if pd.isna(v) else round(float(v), 2)


def traj_table(use: pd.DataFrame, window: str, ticker: str, g: int) -> list[dict]:
    d = use[(use["window"] == window) & (use["ticker"] == ticker) & (use["g"] == g)].sort_values("pos")
    return [{"day": r["day"], "agent_exposure_pct": _r2(r["exposure_pct"]), "rational_target_pct": _r2(r["rat_target"]),
             "u": _r2(r["u"]), "delta_agent": _r2(r["delta_exposure"]), "delta_rational": _r2(r["delta_rational"])}
            for _, r in d.iterrows()]


def worked_examples(use: pd.DataFrame, both: pd.DataFrame, n: int = 3) -> list[dict]:
    """Trajectories with >= 1 eventful and >= 3 quiet gaps, most eventful gaps first (then most quiet), one per
    ticker, the first n."""
    cand = both.groupby(["window", "ticker", "g"]).agg(n_quiet=("u_abs", lambda s: (s < QUIET_MAX).sum()),
                                                       n_event=("u_abs", lambda s: (s >= EVENTFUL_MIN).sum()),
                                                       n=("u_abs", "size")).reset_index()
    cand = cand[(cand["n_event"] >= 1) & (cand["n_quiet"] >= 3)].sort_values(["n_event", "n_quiet"], ascending=False)
    cand = cand.drop_duplicates(subset=["ticker"])
    return [{"window": row["window"], "ticker": row["ticker"], "g": int(row["g"]),
             "n_quiet_gaps": int(row["n_quiet"]), "n_eventful_gaps": int(row["n_event"]),
             "table": traj_table(use, row["window"], row["ticker"], row["g"])}
            for _, row in cand.head(n).iterrows()]


def clean(o):
    """numpy scalars -> Python, non-finite floats -> None, every dict's keys sorted (the workspace wrote sort_keys)."""
    if isinstance(o, dict):
        return {str(k): clean(o[k]) for k in sorted(o, key=str)}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, np.bool_):
        return bool(o)
    if isinstance(o, (np.floating, np.integer)):
        o = o.item()
    if isinstance(o, float) and not math.isfinite(o):
        return None
    return o


def build() -> dict:
    """The full content of results/mechanisms/position_adjustment/data.json."""
    f = frames()
    use, ks = f["use"], f["ks"]
    both = use[use["delta_rational"].notna() & use["delta_exposure"].notna()].copy()
    quiet = both[both["u_abs"] < QUIET_MAX]
    eventful = both[both["u_abs"] >= EVENTFUL_MIN]
    mid = both[(both["u_abs"] >= QUIET_MAX) & (both["u_abs"] < EVENTFUL_MIN)]

    k_sens = {}
    for name in ("k_half", "k_base", "k_double"):
        sub = use[[f"delta_rational_{name}", "delta_exposure", "ticker", "day", "u_abs"]].rename(
            columns={f"delta_rational_{name}": "delta_rational"})
        sub = sub[sub["delta_rational"].notna() & sub["delta_exposure"].notna()]
        reg = ols_robust(sub["delta_exposure"], sub["delta_rational"], sub["ticker"], sub["day"])
        k_sens[name] = {"k": ks[name], "b": reg["b"], "a": reg["a"],
                        "spearman_rho": spearman(sub["delta_exposure"], sub["delta_rational"])["rho"],
                        "std_ratio": std_ratio(sub["delta_exposure"], sub["delta_rational"])["ratio"], "n": reg["n"]}

    lvl = use[use["rat_target"].notna() & use["exposure_pct"].notna()]
    level_corr = {"pearson": float(np.corrcoef(lvl["exposure_pct"], lvl["rat_target"])[0, 1]),
                  "spearman": spearman(lvl["exposure_pct"], lvl["rat_target"])["rho"], "n": int(len(lvl))}
    u_buckets = {
        "quiet_abs_u_lt_1": int((use["u_abs"] < QUIET_MAX).sum()),
        "mid_1_to_2": int(((use["u_abs"] >= QUIET_MAX) & (use["u_abs"] < EVENTFUL_MIN)).sum()),
        "eventful_abs_u_ge_2": int((use["u_abs"] >= EVENTFUL_MIN).sum()),
        "total_matched_agent_days": int(use["u"].notna().sum()),
    }

    result = {
        "method": {**METHOD, "k_base": ks["k_base"]},
        "base_files_loaded": {w: f"{DATA_LABEL}/{p}" for w, p in BASE_FILES.items()},
        "n_trajectories_total": int(f["n_traj_total"]),
        "n_agent_days_total": int(f["n_days_total"]),
        "rational_join_coverage_by_window": f["coverage"].to_dict(orient="records"),
        "rational_join_overall_hit_rate": f["match_rate_all"],
        "events_all_nonevent_overlap_check": f["overlap"],
        "usable_windows": f["usable_windows"],
        "n_trajectories_usable_window": int(use.groupby(["window", "ticker", "g"]).ngroups),
        "n_agent_days_usable_window": int(len(use)),
        "n_consecutive_day_gaps": int(use["consec"].sum()),
        "n_gaps_with_rational_join_both_days": int(use["delta_rational"].notna().sum()),
        "headline": {
            "overall": block(both),
            "quiet_abs_u_lt_1": block_or_note(quiet),
            "eventful_abs_u_ge_2": block_or_note(eventful),
            "mid_1_to_2_for_reference_only": block_or_note(mid),
        },
        "k_sensitivity": k_sens,
        "level_correlation_same_day": level_corr,
        "u_bucket_counts_among_rational_matched_agent_days": u_buckets,
        "worked_examples": worked_examples(use, both),
        "limitation": LIMITATION,
    }
    return clean(result)


def dumps(obj: dict) -> str:
    return json.dumps(obj, indent=1, ensure_ascii=False) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent mech-position",
                                 description="Agent exposure changes vs a Kelly-style rational rule, quiet vs eventful "
                                             "days -> results/mechanisms/position_adjustment/data.json")
    ap.add_argument("--check", action="store_true",
                    help="rebuild and compare with the shipped data.json instead of writing it (exit 1 if different)")
    args = ap.parse_args(argv)
    text = dumps(build())
    if args.check:
        same = OUT_FILE.is_file() and OUT_FILE.read_text() == text
        print(f"{'same' if same else 'DIFFERENT':9s}  {config.rel(OUT_FILE)}")
        return 0 if same else 1
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(text)
    print(f"wrote {config.rel(OUT_FILE)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
