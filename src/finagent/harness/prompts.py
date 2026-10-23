"""The texts the harness model sees: the system prompt, the day prompt, the reminder and the tool list.

SYSTEM is built exactly as in the pilot: the single-agent fund-manager prompt (v1), its v2 sizing rules, the 5-day forecast
paragraph, and the news-testbed sentence (company news before 09:00 New York time on the next trading day is shown).
The day prompt (render_prompt) is the 'v2' layout of build_day_payload: close, account, company / fiscal / monetary news,
insider rows, the last decisions; harness_prompt() adds the day's readings block in the arm's form before the final line.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime

from finagent import arms, readings
from finagent.data.anchors import anchor_state
from finagent.data.pit import news_cache
from finagent.harness import toolbox

NEWS_CAP = 10          # news items per feed in the prompt
INSIDER_CAP = 10
MEMORY_DAYS = 4        # last decisions shown

SYSTEM_V1 = """You are a fund manager trading a single US stock with a fixed cash account.

Each user message gives you one trading day's information, point-in-time: nothing
in it is dated on or after that day's close except the day's own OHLCV bar.

Decide one action for the day: Buy, Sell or Hold, and the number of shares.
Rules of the account:
- You may only hold long positions; shares held cannot go below zero.
- A buy costs shares x close price and must fit the available cash.
- Orders execute at that day's close price.
You may call the tools to pull more data than the summary contains.
Finish every day by calling submit_decision exactly once."""

# v2 asks for the exposure target next to the share count and echoes the exposure the order produces.
SYSTEM_V2 = SYSTEM_V1.replace(
    "Finish every day by calling submit_decision exactly once.",
    """Size the position as a share of total assets, not as a fixed dollar ticket.
submit_decision takes the exposure you are targeting (target_exposure_pct) together with
the share count that implements it, and replies with the exposure your order actually
produces. If that differs from your target, call it again with a corrected share count —
the last call is the one that executes.
Finish every day with submit_decision.""")

SYSTEM_5D = SYSTEM_V2 + """
With every submit_decision also state your forecast for the NEXT 5 TRADING DAYS:
p_up (probability that the close 5 trading days from now is above today's close, 0-1), expected_return_pct
(the mean 5-day return you expect, percent, may be negative) and
expected_vol_pct (your one-standard-deviation estimate of the 5-day return, in percent: the typical size of the
move over the next 5 trading days; not annualised and not a single-day figure)."""

# The news testbed shows company news after the close, which makes one sentence of the prompt false; it is replaced.
NEWS_SYSTEM_OLD = ("Each user message gives you one trading day's information, point-in-time: nothing\n"
                   "in it is dated on or after that day's close except the day's own OHLCV bar.")
NEWS_SYSTEM_NEW = ("Each user message gives you one trading day's information, point-in-time: nothing\n"
                   "in it is dated on or after that day's close except the day's own OHLCV bar and company\n"
                   "news published before 09:00 New York time on the next trading day, before that session opens.")


def news_system(system: str) -> str:
    """`system` with NEWS_SYSTEM_OLD replaced by NEWS_SYSTEM_NEW (exactly one occurrence)."""
    if system.count(NEWS_SYSTEM_OLD) != 1:
        raise RuntimeError("the system prompt does not contain the sentence to replace exactly once")
    return system.replace(NEWS_SYSTEM_OLD, NEWS_SYSTEM_NEW)


SYSTEM = news_system(SYSTEM_5D)
TOOLS_SHA256 = "32860efa8289496f18a62e2eeb332a009871efd5cb22d76e60f31ebb8a3ef52a"   # of json.dumps(tools, sort_keys=True)

REMINDER = ("You stopped without calling submit_decision, so nothing is recorded for today. "
            "Call submit_decision now with action, shares or target_exposure_pct, p_up, "
            "expected_return_pct, expected_vol_pct and reasoning.")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def harness_tools() -> list[dict]:
    """The 32 tool schemas, checked against the pilot's hash."""
    tools = toolbox.build_tools()
    if len(tools) != 32 or sha256(json.dumps(tools, sort_keys=True)) != TOOLS_SHA256:
        raise RuntimeError("the harness tool list differs from the pilot's (32 tools)")
    return tools


# ------------------------------------------------------------------------------------------------ day prompt
def build_day_payload(cache, date: str, portfolio: dict, memory: list[dict]) -> dict:
    """The day's data blocks: bars (newest first), news per feed, insider rows, the book and the last decisions."""
    as_of = datetime.strptime(date, "%Y-%m-%d")
    bars = cache.candles(as_of)
    news = {feed: cache.news_items(feed, as_of, NEWS_CAP) for feed in ("ticker", "economy_fiscal", "economy_monetary")}
    insider = cache.insider_trades(as_of, INSIDER_CAP)
    return {"date": date, "bars": bars, "news": news, "insider": insider,
            "portfolio": portfolio, "memory": memory}


def render_prompt(p: dict, ticker: str) -> str:
    price = p["bars"][0]["close"]
    recent = " ".join(f"{b['date']}:{b['close']:.2f}" for b in p["bars"][:10][::-1])

    def news_block(items):
        return "\n".join(f"- [{i['time_published']}] {i['title']} ({i['source']})" for i in items) or "- (none)"
    trades = "\n".join(
        f"- {t['transaction_date']} {t.get('executive','?')} ({t.get('executive_title','')[:40]}) "
        f"{'buy' if t.get('acquisition_or_disposal') == 'A' else 'sell'} {t.get('shares','?')} @ {t.get('share_price','?')}"
        for t in p["insider"]) or "- (none)"
    # each past decision carries the exposure it produced, so the running frame is percent of assets
    mem = "\n".join(
        f"- {m['date']}: {m['action']} {m['shares']} @ {m['price']:.2f} "
        f"-> exposure {m.get('exposure_pct', 0):.1f}%, assets {m['total_assets']:.0f}"
        for m in p["memory"]) or "- (no prior decisions)"
    pos = p["portfolio"]
    total = pos["cash"] + pos["shares"] * price
    account = (f"""ACCOUNT
- cash {pos['cash']:.2f}
- shares held {pos['shares']}
- position value {pos['shares'] * price:.2f}
- total assets {total:.2f}
- position {pos['shares'] * price / total * 100:.1f}% of total assets
- one percentage point of exposure = {total * 0.01 / price:.1f} shares at today's close""")
    return f"""Trading day {p['date']} — {ticker}

CLOSE {price:.2f}   (last 10 closes: {recent})

{account}

COMPANY NEWS (past 7 days, most recent {NEWS_CAP})
{news_block(p['news']['ticker'])}

FISCAL POLICY NEWS
{news_block(p['news']['economy_fiscal'])}

MONETARY POLICY NEWS
{news_block(p['news']['economy_monetary'])}

INSIDER TRANSACTIONS (filed before today)
{trades}

YOUR LAST {MEMORY_DAYS} DECISIONS
{mem}

Decide today's action and call submit_decision."""


def day_payload(day: dict) -> dict:
    """The payload of a pilot day from its saved anchor state."""
    st = anchor_state(day["day_id"])
    return build_day_payload(news_cache(day["ticker"]).view(), day["t"], {**st["portfolio"]}, st["memory"])


def day_prompt(day: dict) -> str:
    """The day prompt without the readings block (what the session renders before the arm hook)."""
    return render_prompt(day_payload(day), day["ticker"])


def harness_prompt(day: dict, arm: str) -> str:
    """The first user message of a harness run of (day, arm)."""
    return readings.insert_block(day_prompt(day), arms.rewrite_block(readings.registered_block(day["day_id"]), arm))
