"""The point-in-time data of one stock: daily bars, news feeds, insider rows and the decision time D(t) of every trading day.

One cutoff for everything the agent reads about day t: bars through close t (at day t's price level, see corpactions), news
published before D(t) = 09:00 New York time on the next trading day. Times are 'YYYYMMDDTHHMMSS' New York strings, so every cut is
a string comparison.
  prompt block  news_items(): stamp(t - 7 days) <= time_published[:13] and time_published < D(t), newest first, capped
  news tools    tool_news():  t - days <= time_published < D(t), newest first
Each session reads through its own view(); every news read is logged (the ids and times of all candidates, before the tools' own
filtering, limit and the tool-result cut) in view.log, which the run saves as cache_log.
"""
from __future__ import annotations

import bisect
import copy
import json
import threading
from datetime import datetime, timedelta
from pathlib import Path

from finagent import config
from finagent.data.corpactions import display_factor, scale_bar

# Load order of the feeds: the directory order of the pilot's caches, which search_news and the cache log follow.
FEEDS = ("economy_fiscal", "ticker", "economy_monetary")
PROMPT_DAYS = 7                      # look-back of the prompt's news block
TP_FMT = "%Y%m%dT%H%M%S"


def _stamp(moment: datetime) -> str:
    return moment.strftime("%Y%m%dT%H%M")


class NewsCache:
    def __init__(self, cache_dir: Path):
        self.dir = Path(cache_dir)
        man = json.loads((self.dir / "manifest.json").read_text())
        if man.get("build") != "v2" or not man["window"].endswith("_news_v2"):
            raise RuntimeError(f"{cache_dir} is not a build-v2 news cache")
        self.ticker = man["ticker"]
        self.decision = man["decision_time"]
        self.news = {feed: json.loads((self.dir / f"news_{feed}.json").read_text()) for feed in FEEDS}
        self.insider = json.loads((self.dir / "insider.json").read_text())
        self.prices = json.loads((self.dir / "prices.json").read_text())
        self.ca_events = json.loads((self.dir / "corporate_actions.json").read_text())["events"]
        # oldest-first items and their time keys per feed, for bisection (the feed files are newest first)
        self._asc = {feed: sorted(items, key=lambda i: (i["time_published"], i.get("id", 0))) for feed, items in self.news.items()}
        self._keys = {feed: [i["time_published"] for i in items] for feed, items in self._asc.items()}
        self.log: list[dict] = []

    def view(self) -> NewsCache:
        """A per-session copy sharing the (read-only) data, with its own log."""
        v = copy.copy(self)
        v.log = []
        return v

    # ---------------------------------------------------------------------------------------------------- prices
    def price_factor(self, day: str) -> float:
        return display_factor(self.ca_events, day)[0]

    def candles(self, trading_date: datetime) -> list[dict]:
        """Bars through trading_date, newest first, at that day's price level (the prompt's CLOSE line)."""
        cutoff = trading_date.strftime("%Y-%m-%d")
        out = sorted((b for b in self.prices if b["date"] <= cutoff), key=lambda b: b["date"], reverse=True)
        f = self.price_factor(cutoff)
        return out if f == 1.0 else [scale_bar(b, f) for b in out]

    def tool_bars(self, as_of: datetime) -> list[dict]:
        """Bars through as_of, oldest first, at as_of's price level: what every price tool reads."""
        sel = sorted((b for b in self.prices if datetime.strptime(b["date"][:10], "%Y-%m-%d") <= as_of), key=lambda b: b["date"])
        f = self.price_factor(as_of.strftime("%Y-%m-%d"))
        return sel if f == 1.0 else [scale_bar(b, f) for b in sel]

    # ---------------------------------------------------------------------------------------------------- news
    def decision_time(self, as_of: datetime) -> str:
        t = as_of.strftime("%Y-%m-%d")
        if t not in self.decision:
            raise KeyError(f"{self.ticker}: no decision time for {t} (not a trading day of the cache)")
        return self.decision[t]

    def window(self, feed: str, lo_key: str, D: str) -> list[dict]:
        """Items of a feed with lo_key <= time_published < D, oldest first (lo_key compared on its own prefix length)."""
        keys = self._keys.get(feed, [])
        a = bisect.bisect_left(keys, lo_key); b = bisect.bisect_left(keys, D)
        return self._asc.get(feed, [])[a:b]

    def news_items(self, feed: str, trading_date: datetime, limit: int | None) -> list[dict]:
        """The prompt block of one feed: items from t - PROMPT_DAYS days (to the minute) to D(t), newest first."""
        if feed not in self.news:
            raise KeyError(f"no cached news feed for {feed!r}")
        t = trading_date.strftime("%Y-%m-%d"); D = self.decision_time(trading_date)
        lo = _stamp(trading_date - timedelta(days=PROMPT_DAYS))
        cand = [i for i in self.window(feed, lo, D) if lo <= i["time_published"][:13]]
        cand.sort(key=lambda i: i["time_published"], reverse=True)
        out = cand[:limit] if limit else cand
        # "arm" is the news arm of the testbed the caches come from; the pilot always shows all news ("FULL")
        self.log.append({"where": "prompt", "feed": feed, "date": t, "D": D, "arm": "FULL",
                         "ids": [i.get("id") for i in out], "tps": [i["time_published"] for i in out]})
        return out

    def tool_news(self, feed: str, as_of: datetime, days: int) -> list[dict]:
        """What the news tools read: [as_of - days, D(t)), newest first."""
        t = as_of.strftime("%Y-%m-%d"); D = self.decision_time(as_of)
        lo = (as_of - timedelta(days=days)).strftime(TP_FMT)
        cand = self.window(feed, lo, D)
        cand.sort(key=lambda i: i["time_published"], reverse=True)
        self.log.append({"where": "tool", "feed": feed, "date": t, "D": D, "days": days, "arm": "FULL",
                         "ids": [i.get("id") for i in cand], "tps": [i["time_published"] for i in cand]})
        return cand

    def insider_trades(self, trading_date: datetime, limit: int | None) -> list[dict]:
        """Insider rows with a transaction date before trading_date, newest first (the prompt block)."""
        sel = [r for r in self.insider if datetime.strptime(r["transaction_date"], "%Y-%m-%d") < trading_date]
        sel.sort(key=lambda r: r["transaction_date"], reverse=True)
        return sel[:limit] if limit else sel


_CACHES: dict[str, NewsCache] = {}
_LOCK = threading.Lock()                                                       # many sessions start at once


def news_cache(ticker: str) -> NewsCache:
    """The process-wide cache of one stock (take a view() per session)."""
    with _LOCK:
        if ticker not in _CACHES:
            _CACHES[ticker] = NewsCache(config.news_cache_dir(ticker))
        return _CACHES[ticker]
