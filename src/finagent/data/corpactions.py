"""Point-in-time price levels: undo the corporate actions that happened after the decision day.

The stratos panel is adjusted backwards to 2026-09-24, so every bar already includes later splits. On decision day t the bars are
shown multiplied by the display factor S(t) = product of the factors of the listed non-dividend actions with an ex-date after t
(prices x S, volumes / S). Dividends are not undone. Of the six pilot stocks only CRWD has an event (4-for-1 split, ex-date
2026-07-02, before its day), so S = 1 on every pilot day. Events come from each cache's corporate_actions.json.
"""
from __future__ import annotations


def display_factor(events: list[dict], t: str) -> tuple[float, bool]:
    """(S(t), known): product of the factors of the events with ex-date after t; an unknown factor counts as 1 and known=False."""
    f, known = 1.0, True
    for e in events:
        if e["ex_date"] > t:
            if e["factor"] is None:
                known = False
            else:
                f *= float(e["factor"])
    return f, known


def scale_bar(b: dict, f: float) -> dict:
    if f == 1.0:
        return b
    return {**b, "open": b["open"] * f, "high": b["high"] * f, "low": b["low"] * f, "close": b["close"] * f,
            "volume": int(round(b["volume"] / f))}
