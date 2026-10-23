"""What happened after each decision day, from the stratos panel: never shown to an agent, stored with each harness run.

realised(ticker, t)       (r1, r5): simple 1-day and 5-day returns after close t, percent
realised_var5(ticker, t)  the 5-day realised variance: sum of the 5 squared daily log returns after close t, percent^2
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from finagent import config


class Outcomes:
    def __init__(self, tickers):
        p = pd.read_parquet(config.PANEL, columns=["Ticker", "Date", "Close"])
        p = p[p.Ticker.isin(list(tickers))].copy()
        p["Date"] = pd.to_datetime(p["Date"])
        self.px = p.pivot(index="Date", columns="Ticker", values="Close").sort_index()

    def realised(self, ticker: str, t: str) -> tuple[float | None, float | None]:
        i = self.px.index.get_loc(pd.Timestamp(t)); s = self.px[ticker]
        r5 = float((s.iloc[i + 5] / s.iloc[i] - 1) * 100) if i + 5 < len(s) else None
        r1 = float((s.iloc[i + 1] / s.iloc[i] - 1) * 100) if i + 1 < len(s) else None
        return r1, r5

    def realised_var5(self, ticker: str, t: str) -> float | None:
        i = self.px.index.get_loc(pd.Timestamp(t)); s = self.px[ticker]
        if i + 5 >= len(s):
            return None
        lr = np.diff(np.log(s.iloc[i:i + 6].values)) * 100
        return float((lr ** 2).sum())
