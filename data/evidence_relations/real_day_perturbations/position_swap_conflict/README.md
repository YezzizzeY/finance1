# position_swap_conflict

One pair per constructible day: two prompt variants that differ only in which of two already-present,
contradicting signals appears first / more prominently, holding every line's own content fixed.

- **Tier 1 (technical_block_lines, exact)**: two of the four categorical PRICE TOOL READINGS labels
  (`get_trend_signal.signal`, `get_rsi.signal`, `get_mean_reversion_signal.signal`, `get_macd.cross`) already
  disagree in sign under a documented polarity map (bullish/oversold = +1, bearish/overbought = -1). The first
  such pair (in registered block order) has its two LINES swapped in position
  (`real_day.common.swap_block_lines`, built on `finagent.arms.parse_block` — no block-parsing logic is
  reimplemented); every line's own text and every other line's position is unchanged.
- **Tier 2 (price_vs_headline_sentiment_fallback, approximate)**: used only when Tier 1 finds no pair. The day's
  own 1-day price direction (sign of r1_pct) versus the most recent pre-D(t) headline's simple keyword polarity
  (documented as approximate), when they disagree in sign. Rendered as two short, clearly labelled synthetic
  lines (SIGNAL A / SIGNAL B) in one of the two orders, appended once, with identical text in both orders.

## Ground truth claimed: NO-FLIP

A rational forecaster's output must not depend on which of two equal-content signals is listed first. Tier 1 is
an exact derivation (the two tool outputs are real, untouched data; only their order changes). Tier 2 is
approximate in one place only: whether the keyword-polarity label is a fair read of the headline's direction.

## Counts

- days checked: 197
- days with a Tier-1 (exact) pair: 50
- days with a Tier-2 (approximate) fallback pair: 33
- days skipped (no pair found by either tier): 114 (reasons in skipped.json)
- rows: 166

## Source-vs-port

| | source (6-ticker-pilot day pool) | this port (96-ticker data/pit_cache) |
|---|---:|---:|
| days checked | 197 | 197 |
| days skipped | 114 | 114 |
| rows | 166 | 166 |
