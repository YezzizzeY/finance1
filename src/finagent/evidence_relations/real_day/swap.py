"""Family 4, position_swap_conflict: when two signals already in the day's data point in opposite directions, does
swapping which one is more prominent (appears first), holding content fixed, flip the forecast?

Tier 1 (EXACT, preferred): two of the four categorical PRICE TOOL READINGS labels already disagree in sign.
Polarity map (OURS; documented, not the tools' own semantics — rsi/mean-reversion "overbought"/"oversold" are
mean-reversion readings, read here as a directional lean for this purpose only):
    get_trend_signal.signal           bullish=+1  bearish=-1  neutral=0
    get_macd.cross                    bullish=+1  bearish=-1  none=0
    get_rsi.signal                    oversold=+1 overbought=-1 neutral=0
    get_mean_reversion_signal.signal  oversold=+1 overbought=-1 neutral=0
The four tools are checked in their registered block order (get_trend_signal, get_rsi, get_mean_reversion_signal,
get_macd); the FIRST pair (in that enumeration order) whose polarities have opposite non-zero sign is the one
swapped. order_A is the registered block, unmodified. order_B swaps only those two lines' positions
(finagent.evidence_relations.real_day.common.swap_block_lines); every line's own text, and every other line's
position, is untouched.

Tier 2 (APPROXIMATE fallback, used only when Tier 1 finds no pair): the day's own 1-day price direction (sign of
r1_pct, already in the data: the CLOSE line's realised move) versus the most recent headline before D(t)'s simple
keyword polarity (common.keyword_polarity, documented as approximate). Used only when that polarity is non-zero
and opposite in sign to the price direction. Because these are not two adjacent lines of one block, they are
rendered as two short, clearly-labelled synthetic lines (SIGNAL A / SIGNAL B) appended just before the final
instruction, in one of the two orders — the two lines' own text is identical across order_A and order_B, only
their order differs.

Ground truth claimed (NO-FLIP, see README.md): a rational forecaster's output is invariant to which signal is
listed first, since both variants carry exactly the same content. Tier 1 is an exact derivation (real tool
output, nothing invented). Tier 2 additionally assumes the keyword-polarity label is a reasonable read of the
headline's direction, which is the one place this ground truth is only approximate rather than exact.

A day is skipped (logged with a reason) when Tier 1 finds no opposite-sign pair among the four fields AND Tier 2
finds no headline, or a headline whose polarity is zero or same-signed as the price direction.

Ported from 1_overreaction/repro/evidence_relations/real_day_swap.py (unchanged math).
"""
from __future__ import annotations

import json

from finagent import arms
from finagent.evidence_relations.real_day import common as C

POLARITY = {
    "get_trend_signal": {"bullish": 1, "bearish": -1, "neutral": 0},
    "get_macd": {"bullish": 1, "bearish": -1, "none": 0},
    "get_rsi": {"oversold": 1, "overbought": -1, "neutral": 0},
    "get_mean_reversion_signal": {"oversold": 1, "overbought": -1, "neutral": 0},
}
FIELD = {"get_trend_signal": "signal", "get_macd": "cross", "get_rsi": "signal", "get_mean_reversion_signal": "signal"}
TOOL_ORDER = ("get_trend_signal", "get_rsi", "get_mean_reversion_signal", "get_macd")       # enumeration order


def _find_tier1_pair(fields: dict) -> tuple[str, str] | None:
    pol = {tool: POLARITY[tool].get(fields[tool].get(FIELD[tool]), 0) for tool in TOOL_ORDER}
    for i, a in enumerate(TOOL_ORDER):
        for b in TOOL_ORDER[i + 1:]:
            if pol[a] * pol[b] < 0:
                return a, b
    return None


def build_family(day_pool: list[dict]) -> dict:
    rows, skipped = [], []
    for d in day_pool:
        block = C.registered_block(d)
        fields = {name: json.loads(js) for pre, name, js in arms.parse_block(block)}
        base_prompt = C.harness_prompt_orig(d)
        pair = _find_tier1_pair(fields)

        if pair is not None:
            tool_a, tool_b = pair
            swapped_block = C.swap_block_lines(block, tool_a, tool_b)
            prompt_b = C.splice_block(base_prompt, block, swapped_block)
            if prompt_b == base_prompt:
                raise RuntimeError(f"{d['day_id']}: tier-1 swap did not change the prompt")
            common = {"family": "position_swap_conflict", "day_id": d["day_id"], "ticker": d["ticker"], "t": d["t"],
                      "split": d["split"], "pool": d["pool"], "day_type": d["day_type"], "tier": "technical_block_lines",
                      "signal_a": {"tool": tool_a, "field": FIELD[tool_a], "value": fields[tool_a].get(FIELD[tool_a])},
                      "signal_b": {"tool": tool_b, "field": FIELD[tool_b], "value": fields[tool_b].get(FIELD[tool_b])},
                      "ground_truth": "no_flip_from_order_alone", "pair_id": d["day_id"]}
            rows.append({**common, "condition": "order_A_registered",
                         "order": [tool_a, tool_b],
                         "prompt": base_prompt, "prompt_chars": len(base_prompt), "prompt_sha256": C.sha256_text(base_prompt)})
            rows.append({**common, "condition": "order_B_swapped",
                         "order": [tool_b, tool_a],
                         "prompt": prompt_b, "prompt_chars": len(prompt_b), "prompt_sha256": C.sha256_text(prompt_b)})
            continue

        items = C.news_items_before_D(d)
        if not items:
            skipped.append({"day_id": d["day_id"], "reason": "no technical-indicator contradiction among "
                            "trend/rsi/mean-reversion/macd, and no headline before D(t) for the keyword-polarity fallback"})
            continue
        h = max(items, key=lambda i: i["time_published"])
        headline_text = (h.get("title") or "") + ". " + (h.get("summary") or "")
        pol_headline = C.keyword_polarity(headline_text)
        price_dir = 1 if d["r1_pct"] > 0 else (-1 if d["r1_pct"] < 0 else 0)
        if pol_headline == 0 or price_dir == 0 or pol_headline * price_dir >= 0:
            skipped.append({"day_id": d["day_id"], "reason": "no technical-indicator contradiction, and the most-recent "
                            f"headline's keyword polarity ({pol_headline}) does not oppose the day's price-direction "
                            f"sign ({price_dir})"})
            continue

        dirword = "UP" if price_dir > 0 else "DOWN"
        polword = "POSITIVE" if pol_headline > 0 else "NEGATIVE"
        line_price = (f"- SIGNAL A (price direction, from the CLOSE history above): {dirword} {d['r1_pct']:+.2f}% "
                      "over the most recent 1-day move")
        line_news = (f"- SIGNAL B (most recent company-news headline sentiment, simple keyword polarity, approximate): "
                     f"{polword} -- \"{h.get('title') or ''}\"")
        header = "\n\nCONFLICTING SIGNALS (both already stated above; restated together only for this check)\n"
        prompt_a = C.insert_before_final(base_prompt, header + line_price + "\n" + line_news)
        prompt_b = C.insert_before_final(base_prompt, header + line_news + "\n" + line_price)
        common = {"family": "position_swap_conflict", "day_id": d["day_id"], "ticker": d["ticker"], "t": d["t"],
                  "split": d["split"], "pool": d["pool"], "day_type": d["day_type"], "tier": "price_vs_headline_sentiment_fallback",
                  "signal_a": {"kind": "price_direction", "value": price_dir, "r1_pct": d["r1_pct"]},
                  "signal_b": {"kind": "headline_keyword_polarity", "value": pol_headline, "headline_title": h.get("title") or ""},
                  "ground_truth": "no_flip_from_order_alone_approximate", "pair_id": d["day_id"]}
        rows.append({**common, "condition": "order_A_price_first",
                     "prompt": prompt_a, "prompt_chars": len(prompt_a), "prompt_sha256": C.sha256_text(prompt_a)})
        rows.append({**common, "condition": "order_B_news_first",
                     "prompt": prompt_b, "prompt_chars": len(prompt_b), "prompt_sha256": C.sha256_text(prompt_b)})
    return {"rows": rows, "n_days": len(day_pool), "n_rows": len(rows), "n_days_constructed": len(rows) // 2,
            "n_skipped": len(skipped), "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    result = build_family(C.load_day_pool())
    print(json.dumps({"n_days": result["n_days"], "n_rows": result["n_rows"], "n_skipped": result["n_skipped"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
