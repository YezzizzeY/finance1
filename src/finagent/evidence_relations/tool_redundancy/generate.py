"""An empirical tool-redundancy matrix for the 31 non-submit toolbox tools.

Walks every one of the 96 data/pit_cache tickers day by day over the one news-covered year
(2025-09-29..2026-09-24, finagent.config.NEWS_WINDOW's own window), calls finagent.harness.toolbox.run_tool for
each of the 23 non-stateful tools (see EXCLUDED_TOOLS below) through finagent.data.pit.news_cache exactly as the
harness itself would (same point-in-time cutoffs, same default-ticker behaviour), flattens every numeric field
each tool returns, and writes the pooled raw feature table (analyze.py turns it into the correlation matrix).

No model calls, no network calls, CPU only. The only randomness anywhere in this script is NONE: every ticker and
every trading day in the window is used (an exhaustive walk, not a sample), so there is nothing to seed.

    finagent evidence-tools generate [--workers N] [--out DIR]

Determinism: every input is a static on-disk file; every tool call is a pure function of (cache, as_of, args,
state) with a fresh state per (ticker, day); rows are merged back in a fixed ticker-then-date order regardless of
which worker process finished first. Running this script twice produces byte-identical output files.

Ported from 1_overreaction/repro/evidence_relations/tool_redundancy_generate.py, onto finagent's own
toolbox and 96-ticker data/pit_cache instead of that project's repro.toolbox / pit_cache_v2.
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path

import pandas as pd

from finagent import config
from finagent.data.pit import news_cache
from finagent.evidence_relations import ROOT
from finagent.harness import toolbox

OUT_DIR = ROOT / "tool_redundancy"

# Tools skipped because their numeric output depends on account/session state (a simulated portfolio or trade
# history we are not replaying here), not on price/news:
EXCLUDED_TOOLS = {"memory_read", "memory_write", "memory_search", "simulate_order",
                  "get_portfolio", "get_trade_history", "get_calibration_ledger", "get_lessons"}

AVAILABLE_TOOLS = [spec["function"]["name"] for _, spec in toolbox.TOOLS]
INCLUDED_TOOLS = [t for t in AVAILABLE_TOOLS if t not in EXCLUDED_TOOLS]
if len(AVAILABLE_TOOLS) != 31:
    raise RuntimeError(f"expected 31 available tools, got {len(AVAILABLE_TOOLS)}: {AVAILABLE_TOOLS}")
if len(INCLUDED_TOOLS) != 23:
    raise RuntimeError(f"expected 23 included tools, got {len(INCLUDED_TOOLS)}: {INCLUDED_TOOLS}")

NEWS_WINDOW_LO, NEWS_WINDOW_HI = config.NEWS_WINDOW.removesuffix("_news_v2").split("_")   # "2025-09-29", "2026-09-24"


# One fixed argument dict passed to every tool call, every ticker, every day -- so that any variation we measure
# in a tool's output reflects the underlying price/news data, never a query-parameter choice. Values are taken
# from toolbox.py's own convention for exercising every tool, extended with the day's ticker.
def fixed_args(ticker: str) -> dict:
    return {"query": "earnings", "note": "test", "expected_return_pct": 0.3, "expected_vol_pct": 1.5,
            "action": "buy", "target_exposure_pct": 40, "ticker": ticker}


# --------------------------------------------------------------------------- flattening
def flatten_numeric(obj, prefix: str = "") -> dict:
    """Recurse into dicts only; a numeric (int/float, not bool) leaf becomes one column `prefix` -> value. Lists
    and strings are not flattened here (see derive_extra for the handful of tools whose signal lives in a list;
    everything else with a list field simply does not contribute that field, documented in README.md)."""
    out = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            key = f"{prefix}.{k}" if prefix else k
            if isinstance(v, dict):
                out.update(flatten_numeric(v, key))
            elif isinstance(v, bool):
                continue
            elif isinstance(v, (int, float)):
                out[key] = float(v)
            # lists, strings, None: not a numeric scalar, skipped
    return out


def derive_extra(tool: str, parsed) -> dict:
    """A small, explicit, documented set of derived scalars for tools whose payload is a raw list (no dict-level
    numeric field at all) or whose signal is a variable-length list. Every key here ends in '__derived' so it is
    never mistaken for a field the tool literally returns. See tool_redundancy/README.md."""
    out = {}
    if tool in ("get_daily_candles", "get_weekly_candles", "get_monthly_candles"):
        assert isinstance(parsed, list)
        out["count__derived"] = float(len(parsed))
        if parsed:
            head = parsed[0]  # newest period first, by construction of the tool itself
            for f in ("open", "high", "low", "close", "volume"):
                if f in head:
                    out[f"head0_{f}__derived"] = float(head[f])
    elif tool == "get_insider_trades":
        assert isinstance(parsed, list)
        out["count__derived"] = float(len(parsed))
        if parsed:
            head = parsed[0]
            if head.get("shares") is not None:
                out["head0_shares__derived"] = float(head["shares"])
            if head.get("price") is not None:
                out["head0_price__derived"] = float(head["price"])
    elif tool == "get_news":
        assert isinstance(parsed, list)
        out["count__derived"] = float(len(parsed))
    elif tool == "get_macro_news":
        assert isinstance(parsed, dict)
        for feed in ("economy_fiscal", "economy_monetary"):
            out[f"{feed}_count__derived"] = float(len(parsed.get(feed, [])))
    elif tool == "get_support_resistance":
        assert isinstance(parsed, dict)
        close = parsed.get("close")
        res = parsed.get("resistance_above") or []
        sup = parsed.get("support_below") or []
        if close is not None and res:
            out["nearest_resistance_pct__derived"] = float((res[-1] / close - 1) * 100)
        if close is not None and sup:
            out["nearest_support_pct__derived"] = float((sup[-1] / close - 1) * 100)
    elif tool == "get_news_stats":
        assert isinstance(parsed, dict)
        daily = parsed.get("daily") or []
        if daily:
            vals = [r["avg_sentiment"] for r in daily if r.get("avg_sentiment") is not None]
            if vals:
                out["mean_sentiment_recent__derived"] = float(sum(vals) / len(vals))
    return out


# --------------------------------------------------------------------------- one ticker
def eligible_dates(cache) -> list[str]:
    all_dates = sorted(b["date"] for b in cache.prices)
    win = [d for d in all_dates if NEWS_WINDOW_LO <= d <= NEWS_WINDOW_HI]
    dt_keys = set(cache.decision.keys())
    return [d for d in win if d in dt_keys]


def process_ticker(ticker: str) -> list[dict]:
    cache = news_cache(ticker)
    dates = eligible_dates(cache)
    args = fixed_args(ticker)
    rows = []
    for d in dates:
        as_of = datetime.strptime(d, "%Y-%m-%d")
        state = toolbox.new_state()                 # fresh account/session state every call: an independent
                                                      # (ticker, day) snapshot, not a trajectory
        row = {"ticker": ticker, "date": d}
        for tool in INCLUDED_TOOLS:
            out = toolbox.run_tool(cache, as_of, tool, args, state)
            try:
                parsed = json.loads(out)
            except json.JSONDecodeError:
                parsed = None
            if isinstance(parsed, dict):
                for k, v in flatten_numeric(parsed, tool).items():
                    row[k] = v
            for k, v in derive_extra(tool, parsed).items():
                row[f"{tool}.{k}"] = v
        rows.append(row)
    return rows


# --------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent evidence-tools generate")
    ap.add_argument("--workers", type=int, default=32)
    ap.add_argument("--tickers", type=int, default=0, help="0 = all 96 (default); else first N sorted tickers")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    a = ap.parse_args(argv)

    out_dir = a.out
    out_dir.mkdir(parents=True, exist_ok=True)

    tickers = sorted(p.name for p in config.PIT_CACHE.iterdir() if p.is_dir())
    if len(tickers) != 96:
        raise RuntimeError(f"expected 96 tickers in data/pit_cache, found {len(tickers)}")
    if a.tickers:
        tickers = tickers[: a.tickers]

    t0 = time.time()
    if a.workers > 1:
        import multiprocessing as mp
        with mp.Pool(a.workers) as pool:
            per_ticker_rows = pool.map(process_ticker, tickers)   # order preserved == input order
    else:
        per_ticker_rows = [process_ticker(tk) for tk in tickers]
    elapsed = time.time() - t0

    rows: list[dict] = []
    for tk, trows in zip(tickers, per_ticker_rows):
        rows.extend(trows)                      # already date-ascending per ticker; tickers in sorted order
    df = pd.DataFrame(rows)
    meta_cols = ["ticker", "date"]
    numeric_cols = sorted(c for c in df.columns if c not in meta_cols)
    df = df[meta_cols + numeric_cols]

    manifest_extra = {
        "n_tickers": len(tickers), "tickers": tickers,
        "n_rows": len(df), "n_numeric_cols": len(numeric_cols),
        "included_tools": INCLUDED_TOOLS, "excluded_tools": sorted(EXCLUDED_TOOLS),
        "news_window": [NEWS_WINDOW_LO, NEWS_WINDOW_HI],
        "elapsed_sec": round(elapsed, 1), "workers": a.workers,
    }
    print(json.dumps(manifest_extra, indent=2)[:2000])

    df.to_parquet(out_dir / "raw_features.parquet", index=False)
    (out_dir / "_generate_meta.json").write_text(json.dumps(manifest_extra, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
