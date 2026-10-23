"""The 31 tools of the harness and submit_decision: schemas (build_tools) and execution (run_tool).

Every tool takes (cache, as_of, args, state) and returns a JSON string; nothing it returns postdates as_of: bars are the cache's
tool_bars (through close t, at day t's price level), news is cut at the decision time D(t), insider rows at transaction date < t,
and an earnings date is revealed only inside ANNOUNCE_DAYS of it. `state` is the toolbox state that persists across the sessions
of an episode (book, memory, notes, trades). The tool bodies are the original ones, unchanged; two quirks are kept on purpose:
EARNINGS holds AAPL dates only and the earnings tools default to ticker "AAPL"; _mentions also matches "apple" in a title.
The memory and calibration tools score a stated sigma against the next session's (1-day) move.
"""
from __future__ import annotations

import copy
import json
import math
import re
import statistics as st
from collections.abc import Callable
from datetime import datetime, timedelta

INITIAL_CASH = 100_000.0
TARGET_VOL = 15.0            # percent, annualised; get_risk_budget's default target
ANN = math.sqrt(252)

# AAPL reports after the close on these dates. A company publishes the date ~4 weeks
# ahead, so the tool reveals the next one only inside ANNOUNCE_DAYS of it.
EARNINGS = {"AAPL": ["2023-11-02", "2024-02-01", "2024-05-02", "2024-08-01", "2024-10-31",
                     "2025-01-30", "2025-05-01", "2025-07-31", "2025-10-30",
                     "2026-01-29", "2026-04-30", "2026-07-30"]}
ANNOUNCE_DAYS = 35


# --------------------------------------------------------------------------- helpers
def _d(s: str) -> datetime:
    return datetime.strptime(s[:10], "%Y-%m-%d")


def _bars(cache, as_of: datetime) -> list[dict]:
    """Oldest first, date <= as_of, at as_of's price level."""
    return cache.tool_bars(as_of)


def _closes(bars: list[dict]) -> list[float]:
    return [b["close"] for b in bars]


def _rets(closes: list[float]) -> list[float]:
    return [math.log(closes[i] / closes[i - 1]) * 100 for i in range(1, len(closes))]


def _sd(v: list[float]) -> float:
    return st.pstdev(v) if len(v) > 1 else 0.0


def _ema(v: list[float], span: int) -> list[float]:
    k = 2 / (span + 1); out = [v[0]]
    for x in v[1:]:
        out.append(out[-1] + k * (x - out[-1]))
    return out


def _default_ticker(cache) -> str:
    return cache.ticker


def _news(cache, feed: str, as_of: datetime, days: int) -> list[dict]:
    """[as_of - days, D(t)), newest first."""
    return cache.tool_news(feed, as_of, days)


def _mentions(item: dict, ticker: str) -> bool:
    if any(t.get("ticker") == ticker for t in item.get("ticker_sentiment", []) or []):
        return True
    return bool(re.search(rf"\b{ticker}\b|apple", item.get("title", ""), re.I))


def _portfolio_view(state: dict, price: float) -> dict:
    p = state["portfolio"]; total = p["cash"] + p["shares"] * price
    return {"cash": round(p["cash"], 2), "shares": p["shares"], "position_value": round(p["shares"] * price, 2),
            "total_assets": round(total, 2), "exposure_pct": round(p["shares"] * price / total * 100, 1) if total else 0.0,
            "shares_per_exposure_point": round(total * 0.01 / price, 2)}


def new_state(portfolio: dict | None = None) -> dict:
    """Everything that persists across sessions inside one episode."""
    return {"portfolio": portfolio or {"cash": INITIAL_CASH, "shares": 0}, "start_assets": INITIAL_CASH,
            "memory": [], "notes": [], "trades": []}


# --------------------------------------------------------------------------- market data
def get_daily_candles(cache, as_of, args, state):
    n = int(args.get("days", 20))
    return json.dumps(_bars(cache, as_of)[-n:][::-1])


def get_weekly_candles(cache, as_of, args, state):
    n = int(args.get("weeks", 12)); bars = _bars(cache, as_of); weeks: dict[str, list] = {}
    for b in bars:
        weeks.setdefault(_d(b["date"]).strftime("%G-W%V"), []).append(b)
    out = [{"week": k, "start": v[0]["date"], "end": v[-1]["date"], "open": v[0]["open"],
            "high": max(x["high"] for x in v), "low": min(x["low"] for x in v), "close": v[-1]["close"],
            "volume": sum(x["volume"] for x in v)} for k, v in weeks.items()]
    return json.dumps(out[-n:][::-1])


def get_monthly_candles(cache, as_of, args, state):
    n = int(args.get("months", 12)); bars = _bars(cache, as_of); months: dict[str, list] = {}
    for b in bars:
        months.setdefault(b["date"][:7], []).append(b)
    out = [{"month": k, "open": v[0]["open"], "high": max(x["high"] for x in v), "low": min(x["low"] for x in v),
            "close": v[-1]["close"], "volume": sum(x["volume"] for x in v)} for k, v in months.items()]
    return json.dumps(out[-n:][::-1])


def get_intraday_candles(cache, as_of, args, state):
    return json.dumps({"error": "intraday bars are not in this dataset; only daily OHLCV is available",
                       "hint": "use get_daily_candles"})


def get_returns(cache, as_of, args, state):
    n = int(args.get("days", 20)); bars = _bars(cache, as_of); c = _closes(bars); r = _rets(c)
    out = [{"date": bars[i + 1]["date"], "ret_pct": round(r[i], 2)} for i in range(len(r))][-n:]
    cum = (c[-1] / c[-n - 1] - 1) * 100 if len(c) > n else None
    return json.dumps({"daily": out[::-1], "cumulative_pct": round(cum, 2) if cum is not None else None,
                       "up_days": sum(1 for x in out if x["ret_pct"] > 0), "down_days": sum(1 for x in out if x["ret_pct"] < 0)})


def get_price_stats(cache, as_of, args, state):
    bars = _bars(cache, as_of); c = _closes(bars); hi = [b["high"] for b in bars]; lo = [b["low"] for b in bars]
    last = c[-1]; w252 = c[-252:]
    peak = max(w252)
    return json.dumps({"close": last, "date": bars[-1]["date"],
                       "high_52w": max(hi[-252:]), "low_52w": min(lo[-252:]),
                       "pct_from_52w_high": round((last / max(hi[-252:]) - 1) * 100, 2),
                       "pct_from_52w_low": round((last / min(lo[-252:]) - 1) * 100, 2),
                       "drawdown_from_peak_pct": round((last / peak - 1) * 100, 2),
                       "ret_5d_pct": round((last / c[-6] - 1) * 100, 2) if len(c) > 5 else None,
                       "ret_20d_pct": round((last / c[-21] - 1) * 100, 2) if len(c) > 20 else None,
                       "ret_60d_pct": round((last / c[-61] - 1) * 100, 2) if len(c) > 60 else None,
                       "ret_250d_pct": round((last / c[-251] - 1) * 100, 2) if len(c) > 250 else None})


# --------------------------------------------------------------------------- derived technicals
# The indicator choices and windows are widely used technical-analysis settings.
def get_trend_signal(cache, as_of, args, state):
    c = _closes(_bars(cache, as_of)); e8, e21, e55 = (_ema(c, k)[-1] for k in (8, 21, 55))
    adx_like = abs(e8 - e55) / e55 * 100
    sig = "bullish" if e8 > e21 > e55 else "bearish" if e8 < e21 < e55 else "neutral"
    return json.dumps({"signal": sig, "ema8": round(e8, 2), "ema21": round(e21, 2), "ema55": round(e55, 2),
                       "spread_8_55_pct": round(adx_like, 2), "close": c[-1]})


def get_mean_reversion_signal(cache, as_of, args, state):
    c = _closes(_bars(cache, as_of)); w = c[-20:]; sma = st.mean(w); sd = _sd(w)
    upper, lower = sma + 2 * sd, sma - 2 * sd
    w50 = c[-50:]; z = (c[-1] - st.mean(w50)) / (_sd(w50) or 1)
    sig = "oversold" if z < -2 else "overbought" if z > 2 else "neutral"
    return json.dumps({"signal": sig, "z_score_50d": round(z, 2), "bollinger_upper": round(upper, 2),
                       "bollinger_lower": round(lower, 2), "bollinger_position": round((c[-1] - lower) / ((upper - lower) or 1), 2), "close": c[-1]})


def get_rsi(cache, as_of, args, state):
    p = int(args.get("period", 14)); c = _closes(_bars(cache, as_of)); d = [c[i] - c[i - 1] for i in range(1, len(c))][-p:]
    g = sum(x for x in d if x > 0) / p; l = -sum(x for x in d if x < 0) / p
    rsi = 100 - 100 / (1 + g / l) if l else 100.0
    return json.dumps({"rsi": round(rsi, 1), "period": p, "signal": "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"})


def get_macd(cache, as_of, args, state):
    c = _closes(_bars(cache, as_of)); macd = [a - b for a, b in zip(_ema(c, 12), _ema(c, 26))]; sig = _ema(macd, 9)
    return json.dumps({"macd": round(macd[-1], 3), "signal": round(sig[-1], 3), "histogram": round(macd[-1] - sig[-1], 3),
                       "cross": "bullish" if macd[-1] > sig[-1] and macd[-2] <= sig[-2] else "bearish" if macd[-1] < sig[-1] and macd[-2] >= sig[-2] else "none"})


def get_volatility_stats(cache, as_of, args, state):
    bars = _bars(cache, as_of); c = _closes(bars); r = _rets(c)
    park = [(math.log(b["high"] / b["low"]) * 100) ** 2 / (4 * math.log(2)) for b in bars]
    tr = [max(bars[i]["high"] - bars[i]["low"], abs(bars[i]["high"] - bars[i - 1]["close"]), abs(bars[i]["low"] - bars[i - 1]["close"])) for i in range(1, len(bars))]
    v21 = [_sd(r[i - 21:i]) * ANN for i in range(21, len(r) + 1)]
    vol_ma63 = st.mean(v21[-63:]) if len(v21) >= 63 else st.mean(v21)
    vol_sd63 = _sd(v21[-63:]) if len(v21) >= 63 else _sd(v21)
    return json.dumps({"ann_vol_10d_pct": round(_sd(r[-10:]) * ANN, 1), "ann_vol_20d_pct": round(_sd(r[-20:]) * ANN, 1),
                       "ann_vol_60d_pct": round(_sd(r[-60:]) * ANN, 1),
                       "parkinson_vol_10d_pct": round(math.sqrt(st.mean(park[-10:])) * ANN, 1),
                       "atr_14": round(st.mean(tr[-14:]), 2), "atr_14_pct_of_price": round(st.mean(tr[-14:]) / c[-1] * 100, 2),
                       "vol_zscore_vs_63d": round((v21[-1] - vol_ma63) / (vol_sd63 or 1), 2),
                       "regime": "high" if v21[-1] > vol_ma63 + vol_sd63 else "low" if v21[-1] < vol_ma63 - vol_sd63 else "normal",
                       "abs_move_yesterday_pct": round(abs(r[-1]), 2),
                       "note": "big moves cluster: after a large move the next few days are usually larger than average"})


def get_support_resistance(cache, as_of, args, state):
    bars = _bars(cache, as_of)[-60:]; hi = [b["high"] for b in bars]; lo = [b["low"] for b in bars]; c = bars[-1]["close"]
    piv_hi = sorted({round(hi[i], 2) for i in range(2, len(hi) - 2) if hi[i] == max(hi[i - 2:i + 3])}, reverse=True)
    piv_lo = sorted({round(lo[i], 2) for i in range(2, len(lo) - 2) if lo[i] == min(lo[i - 2:i + 3])})
    return json.dumps({"close": c, "resistance_above": [x for x in piv_hi if x > c][-3:], "support_below": [x for x in piv_lo if x < c][-3:]})


def get_volume_analysis(cache, as_of, args, state):
    bars = _bars(cache, as_of); v = [b["volume"] for b in bars]; c = _closes(bars)
    ma20 = st.mean(v[-20:]); r = _rets(c)[-20:]; dv = [v[i] - v[i - 1] for i in range(len(v) - 20, len(v))]
    corr = (st.correlation(r, dv[-len(r):]) if len(r) > 2 else 0.0)
    return json.dumps({"volume_today": v[-1], "volume_ma20": round(ma20), "ratio_to_ma20": round(v[-1] / ma20, 2),
                       "price_volume_corr_20d": round(corr, 2), "signal": "surge" if v[-1] > 1.5 * ma20 else "quiet" if v[-1] < 0.6 * ma20 else "normal"})


# --------------------------------------------------------------------------- risk & sizing
def get_risk_budget(cache, as_of, args, state):
    target = float(args.get("target_vol_pct", TARGET_VOL)); bars = _bars(cache, as_of); r = _rets(_closes(bars))
    v = _sd(r[-20:]) * ANN; price = bars[-1]["close"]; pv = _portfolio_view(state, price)
    cap = min(100.0, target / v * 100) if v else 100.0
    return json.dumps({"target_vol_pct": target, "trailing_vol_20d_pct": round(v, 1),
                       "max_exposure_pct_for_target": round(cap, 1),
                       "current_exposure_pct": pv["exposure_pct"],
                       "current_ex_ante_risk_pct": round(pv["exposure_pct"] / 100 * v, 1),
                       "gap_to_budget_pct_points": round(cap - pv["exposure_pct"], 1),
                       "shares_to_reach_budget": round((cap - pv["exposure_pct"]) * pv["shares_per_exposure_point"])})


def get_kelly_sizing(cache, as_of, args, state):
    mu = float(args.get("expected_return_pct", 0)) / 100; sg = float(args.get("expected_vol_pct", 1)) / 100
    gamma = float(args.get("risk_aversion", 32))
    f = max(0.0, min(1.0, mu / (gamma * sg * sg))) if sg else 0.0
    return json.dumps({"kelly_fraction_pct": round(f * 100, 1), "full_kelly_pct": round(mu / (sg * sg) * 100, 1) if sg else None,
                       "risk_aversion": gamma, "inputs": {"mu_pct": mu * 100, "sigma_pct": sg * 100}})


def get_drawdown_stats(cache, as_of, args, state):
    trades = state["trades"]; bars = _bars(cache, as_of); price = bars[-1]["close"]
    total = state["portfolio"]["cash"] + state["portfolio"]["shares"] * price
    eq = [t["total_assets"] for t in trades] + [total]; peak = max(eq) if eq else total
    return json.dumps({"total_assets": round(total, 2), "peak_assets": round(peak, 2),
                       "drawdown_pct": round((total / peak - 1) * 100, 2), "pnl_since_start_pct": round((total / state["start_assets"] - 1) * 100, 2),
                       "sessions_in_episode": len(trades)})


# --------------------------------------------------------------------------- events
def get_earnings_calendar(cache, as_of, args, state):
    tk = args.get("ticker", "AAPL"); dates = EARNINGS.get(tk, [])
    past = [d for d in dates if _d(d) <= as_of]; nxt = [d for d in dates if _d(d) > as_of]
    upcoming = nxt[0] if nxt and (_d(nxt[0]) - as_of).days <= ANNOUNCE_DAYS else None
    return json.dumps({"ticker": tk, "last_report": past[-1] if past else None,
                       "next_report": upcoming, "trading_days_until_next": (
                           sum(1 for b in cache.prices if as_of < _d(b["date"]) <= _d(upcoming)) if upcoming else None),
                       "note": "reports after the close; the reaction lands on the next session" if upcoming else "next date not yet announced"})


def get_event_risk(cache, as_of, args, state):
    tk = args.get("ticker", "AAPL"); bars = _bars(cache, as_of); idx = {b["date"]: i for i, b in enumerate(bars)}
    c = _closes(bars); moves = []
    for d in EARNINGS.get(tk, []):
        i = idx.get(d)
        if i is not None and i + 1 < len(bars):
            moves.append({"report": d, "next_session_move_pct": round((c[i + 1] / c[i] - 1) * 100, 2)})
    r = _rets(c); base = st.mean(abs(x) for x in r) if r else 0
    return json.dumps({"past_earnings_reactions": moves[-8:], "avg_abs_reaction_pct": round(st.mean(abs(m["next_session_move_pct"]) for m in moves), 2) if moves else None,
                       "avg_abs_daily_move_pct": round(base, 2), "up_count": sum(m["next_session_move_pct"] > 0 for m in moves), "down_count": sum(m["next_session_move_pct"] < 0 for m in moves)})


# --------------------------------------------------------------------------- news
def get_news(cache, as_of, args, state):
    feed = args.get("feed", "ticker"); days = int(args.get("days", 7)); limit = int(args.get("limit", 20))
    only = args.get("only_ticker", True) if feed == "ticker" else False
    items = [i for i in _news(cache, feed, as_of, days) if not only or _mentions(i, args.get("ticker", _default_ticker(cache)))]
    return json.dumps([{"t": i["time_published"][:13], "title": i["title"], "summary": (i.get("summary") or "")[:300],
                        "sentiment": i.get("overall_sentiment_label")} for i in items[:limit]], ensure_ascii=False)


def search_news(cache, as_of, args, state):
    q = args.get("query", ""); days = int(args.get("days", 30)); limit = int(args.get("limit", 15)); pat = re.compile(re.escape(q), re.I)
    hits = []
    for feed in cache.news:
        for i in _news(cache, feed, as_of, days):
            if pat.search(i["title"]) or pat.search(i.get("summary") or ""):
                hits.append({"feed": feed, "t": i["time_published"][:13], "title": i["title"], "summary": (i.get("summary") or "")[:200]})
    hits.sort(key=lambda h: h["t"], reverse=True)
    return json.dumps({"query": q, "matches": len(hits), "items": hits[:limit]}, ensure_ascii=False)


def get_news_stats(cache, as_of, args, state):
    days = int(args.get("days", 14)); tk = args.get("ticker", _default_ticker(cache)); items = _news(cache, "ticker", as_of, days)
    by_day: dict[str, list] = {}
    for i in items:
        if _mentions(i, tk):
            by_day.setdefault(i["time_published"][:8], []).append(i.get("overall_sentiment_score") or 0.0)
    rows = [{"date": f"{k[:4]}-{k[4:6]}-{k[6:]}", "count": len(v), "avg_sentiment": round(st.mean(v), 3)} for k, v in sorted(by_day.items(), reverse=True)]
    return json.dumps({"ticker": tk, "days": days, "daily": rows, "total": sum(r["count"] for r in rows)})


def get_macro_news(cache, as_of, args, state):
    days = int(args.get("days", 7)); limit = int(args.get("limit", 10))
    out = {feed: [{"t": i["time_published"][:13], "title": i["title"]} for i in _news(cache, feed, as_of, days)[:limit]]
           for feed in ("economy_fiscal", "economy_monetary") if feed in cache.news}
    return json.dumps(out, ensure_ascii=False)


# --------------------------------------------------------------------------- insider
def get_insider_trades(cache, as_of, args, state):
    days = int(args.get("days", 90)); limit = int(args.get("limit", 20)); lo = as_of - timedelta(days=days)
    rows = [t for t in cache.insider if lo <= _d(t["transaction_date"]) < as_of]
    rows.sort(key=lambda t: t["transaction_date"], reverse=True)
    return json.dumps([{"date": t["transaction_date"], "who": t.get("executive"), "title": (t.get("executive_title") or "")[:40],
                        "side": "buy" if t.get("acquisition_or_disposal") == "A" else "sell", "shares": t.get("shares"), "price": t.get("share_price")} for t in rows[:limit]], ensure_ascii=False)


def get_insider_summary(cache, as_of, args, state):
    days = int(args.get("days", 90)); lo = as_of - timedelta(days=days)
    rows = [t for t in cache.insider if lo <= _d(t["transaction_date"]) < as_of]
    buys = [t for t in rows if t.get("acquisition_or_disposal") == "A"]; sells = [t for t in rows if t.get("acquisition_or_disposal") != "A"]
    sh = lambda ts: sum(float(t.get("shares") or 0) for t in ts)
    return json.dumps({"days": days, "buy_count": len(buys), "sell_count": len(sells), "buy_shares": sh(buys), "sell_shares": sh(sells),
                       "net_shares": sh(buys) - sh(sells), "distinct_insiders": len({t.get("executive") for t in rows}),
                       "signal": "net buying" if sh(buys) > sh(sells) else "net selling" if sells else "none"})


# --------------------------------------------------------------------------- account
def get_portfolio(cache, as_of, args, state):
    price = _bars(cache, as_of)[-1]["close"]; pv = _portfolio_view(state, price)
    pv["pnl_since_start_pct"] = round((pv["total_assets"] / state["start_assets"] - 1) * 100, 2)
    return json.dumps(pv)


def get_trade_history(cache, as_of, args, state):
    n = int(args.get("days", 10))
    return json.dumps(state["trades"][-n:][::-1])


def simulate_order(cache, as_of, args, state):
    """Preview the exposure an order would leave, without recording anything."""
    price = _bars(cache, as_of)[-1]["close"]; p = dict(state["portfolio"]); total = p["cash"] + p["shares"] * price
    act = (args.get("action") or "hold").strip().lower()
    if "target_exposure_pct" in args and args["target_exposure_pct"] is not None:
        want = max(0, min(100, float(args["target_exposure_pct"]))); target_sh = round(total * want / 100 / price)
        delta = target_sh - p["shares"]
    else:
        delta = int(args.get("shares") or 0) * (1 if act == "buy" else -1 if act == "sell" else 0)
    delta = max(-p["shares"], min(delta, int(p["cash"] // price)))
    new_sh = p["shares"] + delta; new_exp = new_sh * price / total * 100
    return json.dumps({"would_execute": f"{'buy' if delta > 0 else 'sell' if delta < 0 else 'hold'} {abs(delta)} @ {price:.2f}",
                       "resulting_exposure_pct": round(new_exp, 1), "resulting_cash": round(p["cash"] - delta * price, 2)})


# --------------------------------------------------------------------------- memory
def memory_read(cache, as_of, args, state):
    """Past decisions annotated with what happened next. The outcome column is
    the one thing the upstream decision_memory never had."""
    n = int(args.get("days", 10)); bars = _bars(cache, as_of); idx = {b["date"]: i for i, b in enumerate(bars)}; c = _closes(bars)
    out = []
    for m in state["memory"][-n:]:
        i = idx.get(m["date"]); nxt = (c[i + 1] / c[i] - 1) * 100 if i is not None and i + 1 < len(c) else None
        row = {"date": m["date"], "action": m.get("action"), "exposure_pct": m.get("exposure_pct"),
               "stated_p_up": m.get("p_up"), "stated_mu_pct": m.get("mu"), "stated_sigma_pct": m.get("sigma"),
               "next_session_ret_pct": round(nxt, 2) if nxt is not None else None,
               "reasoning": (m.get("reasoning") or "")[:200]}
        if nxt is not None and m.get("sigma"):
            row["sigma_vs_realized"] = "over" if m["sigma"] > abs(nxt) * 1.5 else "under" if m["sigma"] < abs(nxt) / 1.5 else "ok"
        out.append(row)
    return json.dumps(out[::-1], ensure_ascii=False)


def memory_write(cache, as_of, args, state):
    note = (args.get("note") or "").strip()[:500]
    if note:
        state["notes"].append({"date": as_of.strftime("%Y-%m-%d"), "note": note})
    return json.dumps({"saved": bool(note), "notes_total": len(state["notes"])})


def memory_search(cache, as_of, args, state):
    q = (args.get("query") or "").lower(); hits = []
    for nte in state["notes"]:
        if q in nte["note"].lower():
            hits.append({"kind": "note", **nte})
    for m in state["memory"]:
        if q in (m.get("reasoning") or "").lower():
            hits.append({"kind": "decision", "date": m["date"], "action": m.get("action"), "reasoning": (m.get("reasoning") or "")[:200]})
    return json.dumps({"query": q, "hits": hits[-10:]}, ensure_ascii=False)


def get_calibration_ledger(cache, as_of, args, state):
    """How the agent's own past forecasts compared with what happened. This is
    the reflection step done with arithmetic instead of another LLM call."""
    bars = _bars(cache, as_of); idx = {b["date"]: i for i, b in enumerate(bars)}; c = _closes(bars)
    sig_err, dir_hits, n = [], [], 0
    for m in state["memory"]:
        i = idx.get(m["date"])
        if i is None or i + 1 >= len(c):
            continue
        nxt = (c[i + 1] / c[i] - 1) * 100; n += 1
        if m.get("sigma"):
            sig_err.append(math.log(max(m["sigma"], 0.05)) - math.log(max(abs(nxt), 0.05)))
        if m.get("p_up") is not None and m["p_up"] != 0.5:
            dir_hits.append((m["p_up"] > 0.5) == (nxt > 0))
    return json.dumps({"scored_sessions": n,
                       "sigma_bias": ("you overstate volatility" if sig_err and st.mean(sig_err) > 0.3 else "you understate volatility" if sig_err and st.mean(sig_err) < -0.3 else "sigma roughly calibrated") if sig_err else "no sigma stated yet",
                       "mean_log_sigma_error": round(st.mean(sig_err), 2) if sig_err else None,
                       "direction_hit_rate": round(sum(dir_hits) / len(dir_hits), 2) if dir_hits else None, "direction_calls": len(dir_hits),
                       "reminder": "a hit rate near 0.5 over many calls means direction is not predictable from your inputs; size on risk instead"})


def get_lessons(cache, as_of, args, state):
    """Mechanical after-action review of the episode so far: which sessions cost
    the most, and whether the book was heavy on the big-move days."""
    bars = _bars(cache, as_of); idx = {b["date"]: i for i, b in enumerate(bars)}; c = _closes(bars); rows = []
    for m in state["memory"]:
        i = idx.get(m["date"])
        if i is not None and i + 1 < len(c) and m.get("exposure_pct") is not None:
            nxt = (c[i + 1] / c[i] - 1) * 100
            rows.append({"date": m["date"], "exposure_pct": m["exposure_pct"], "next_ret_pct": round(nxt, 2), "pnl_contrib_pct": round(m["exposure_pct"] / 100 * nxt, 2)})
    if not rows:
        return json.dumps({"lessons": [], "note": "no scored sessions yet"})
    worst = min(rows, key=lambda r: r["pnl_contrib_pct"]); big = sorted(rows, key=lambda r: -abs(r["next_ret_pct"]))[:3]
    e_big = st.mean(r["exposure_pct"] for r in big); e_all = st.mean(r["exposure_pct"] for r in rows)
    return json.dumps({"worst_session": worst, "exposure_on_biggest_moves_pct": round(e_big, 1), "average_exposure_pct": round(e_all, 1),
                       "lesson": "book was heavier than average on the biggest moves" if e_big > e_all + 5 else "book was lighter on the biggest moves" if e_big < e_all - 5 else "no exposure timing pattern",
                       "sessions": rows[-10:]})


# --------------------------------------------------------------------------- registry
def _spec(name: str, desc: str, props: dict, required: list[str] | None = None) -> dict:
    return {"type": "function", "function": {"name": name, "description": desc,
            "parameters": {"type": "object", "properties": props, **({"required": required} if required else {})}}}


I, N, S, B = {"type": "integer"}, {"type": "number"}, {"type": "string"}, {"type": "boolean"}

# (function, schema) of the 31 tools offered to the model, in the order of the tool list
TOOLS: list[tuple[Callable, dict]] = [
    # market
    (get_daily_candles, _spec("get_daily_candles", "Daily OHLCV bars, newest first. The prompt shows only the last 10 closes; this adds open/high/low/volume and more history.", {"days": I})),
    (get_weekly_candles, _spec("get_weekly_candles", "Weekly OHLCV bars aggregated from daily, newest first.", {"weeks": I})),
    (get_monthly_candles, _spec("get_monthly_candles", "Monthly OHLCV bars aggregated from daily, newest first.", {"months": I})),
    (get_returns, _spec("get_returns", "Daily log returns in percent for the last N sessions, with cumulative return and up/down day counts.", {"days": I})),
    (get_price_stats, _spec("get_price_stats", "Where the price sits: 52-week high/low, drawdown from peak, 5/20/60/250-day returns.", {})),
    # technicals
    (get_trend_signal, _spec("get_trend_signal", "EMA 8/21/55 trend read: bullish / bearish / neutral.", {})),
    (get_mean_reversion_signal, _spec("get_mean_reversion_signal", "Bollinger band position and 50-day z-score: oversold / overbought / neutral.", {})),
    (get_rsi, _spec("get_rsi", "RSI for a given period (default 14).", {"period": I})),
    (get_macd, _spec("get_macd", "MACD(12,26,9) line, signal, histogram and any fresh cross.", {})),
    (get_volatility_stats, _spec("get_volatility_stats", "Annualised trailing volatility at 10/20/60 days, Parkinson (high-low) vol, ATR, vol regime vs the last 63 days.", {})),
    (get_support_resistance, _spec("get_support_resistance", "Nearest pivot-based support and resistance levels from the last 60 sessions.", {})),
    (get_volume_analysis, _spec("get_volume_analysis", "Today's volume vs 20-day average and the recent price-volume correlation.", {})),
    # risk & sizing
    (get_risk_budget, _spec("get_risk_budget", "Given a target annualised portfolio volatility (default 15%), the maximum exposure the current trailing vol allows, your current ex-ante risk, and the share count that closes the gap.", {"target_vol_pct": N})),
    (get_kelly_sizing, _spec("get_kelly_sizing", "Fractional-Kelly exposure implied by your own expected return and volatility for the next session, at a given risk aversion (default 32).", {"expected_return_pct": N, "expected_vol_pct": N, "risk_aversion": N}, ["expected_return_pct", "expected_vol_pct"])),
    (get_drawdown_stats, _spec("get_drawdown_stats", "Episode P&L, peak assets and current drawdown.", {})),
    # events
    (get_earnings_calendar, _spec("get_earnings_calendar", "Last and next earnings report dates and trading days until the next one, once the company has announced it.", {"ticker": S})),
    (get_event_risk, _spec("get_event_risk", "How the stock moved on the session after each past earnings report, versus an ordinary day.", {"ticker": S})),
    # news
    (get_news, _spec("get_news", "Headlines with summaries and sentiment. feed: ticker | economy_fiscal | economy_monetary. The prompt shows 10 titles from the last 7 days; the ticker feed holds ~250 in that window, most about other companies, so only_ticker filters to items that mention the stock.", {"feed": S, "days": I, "limit": I, "only_ticker": B})),
    (search_news, _spec("search_news", "Keyword search over all news feeds for the last N days (default 30).", {"query": S, "days": I, "limit": I}, ["query"])),
    (get_news_stats, _spec("get_news_stats", "Per-day count and average sentiment of items mentioning the stock: a news-attention gauge.", {"days": I})),
    (get_macro_news, _spec("get_macro_news", "Recent fiscal-policy and monetary-policy headlines.", {"days": I, "limit": I})),
    # insider
    (get_insider_trades, _spec("get_insider_trades", "Insider transactions filed before today, within the last N days (default 90).", {"days": I, "limit": I})),
    (get_insider_summary, _spec("get_insider_summary", "Net insider buying vs selling over the last N days.", {"days": I})),
    # account
    (get_portfolio, _spec("get_portfolio", "Cash, shares, exposure as percent of assets, P&L since the start of the episode.", {})),
    (get_trade_history, _spec("get_trade_history", "Your executed orders this episode, newest first.", {"days": I})),
    (simulate_order, _spec("simulate_order", "Preview what exposure an order would leave, without submitting it. Give either shares+action or target_exposure_pct.", {"action": S, "shares": I, "target_exposure_pct": N})),
    # memory
    (memory_read, _spec("memory_read", "Your past decisions with the return that followed each one and whether your stated volatility was over or under what happened.", {"days": I})),
    (memory_write, _spec("memory_write", "Save a note for your future sessions (a rule you want to keep, an observation to check later).", {"note": S}, ["note"])),
    (memory_search, _spec("memory_search", "Search your notes and past reasoning by keyword.", {"query": S}, ["query"])),
    (get_calibration_ledger, _spec("get_calibration_ledger", "How your stated volatility and direction forecasts compared with realised moves so far this episode.", {})),
    (get_lessons, _spec("get_lessons", "After-action review of the episode: worst session, and whether the book was heavy on the biggest-move days.", {})),
]

SUBMIT = _spec("submit_decision",
               "Record the day's decision and your forecast for the next 5 trading days. Echoes the exposure the order produces; you may resubmit. The last submission wins.",
               {"action": S, "shares": I, "target_exposure_pct": I,
                "p_up": {"type": "number", "description": "probability the close 5 trading days from now is above today's close, 0-1"},
                "expected_return_pct": {"type": "number", "description": "mean 5-day return you expect, percent"},
                "expected_vol_pct": {"type": "number", "description": "one-standard-deviation size of the 5-day return, percent (not annualised, not daily)"},
                "confidence": {"type": "number", "description": "0-1, how much information you have for this forecast (how much you would stake on it being accurate)"}, "reasoning": S})

# callable by name although not offered (it answers with an error that points to get_daily_candles)
_FN: dict[str, Callable] = {spec["function"]["name"]: fn for fn, spec in TOOLS} | {"get_intraday_candles": get_intraday_candles}


def build_tools() -> list[dict]:
    """The 32 OpenAI-format tool schemas sent with every request; submit_decision is last."""
    return copy.deepcopy([spec for _, spec in TOOLS] + [SUBMIT])


def run_tool(cache, as_of: datetime, name: str, args: dict, state: dict) -> str:
    fn = _FN.get(name)
    if fn is None:
        return json.dumps({"error": f"unknown tool {name}"})
    try:
        return fn(cache, as_of, args or {}, state)
    except Exception as e:                       # a tool error must not kill the session
        return json.dumps({"error": f"{type(e).__name__}: {e}"})
