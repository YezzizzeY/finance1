# Tools of the harness

The harness offers 32 function tools with every request: 31 data and account tools, and `submit_decision`.
The schemas are in [`data/prompts/tools.json`](../data/prompts/tools.json) (sha256 of `json.dumps(tools, sort_keys=True)` =
`32860efa8289496f18a62e2eeb332a009871efd5cb22d76e60f31ebb8a3ef52a`), and the code is in
[`src/finagent/harness/toolbox.py`](../src/finagent/harness/toolbox.py). The coding agent has none of these
tools: it gets files ([PROTOCOL § Framework 2](PROTOCOL.md#framework-2-codex-cli)).

**Point in time.** Each tool reads only the stock's own point-in-time cache, with as-of date = day t:

- **Bars:** through close t, at day t's price level. No tool takes a date argument.
- **News:** published before D(t).
- **Insider rows:** dated before t.
- **State:** the account, notes, trades and the two anchor decisions of the run (`state`).

**Output.** Each tool returns a JSON string. The arm's rewrite is applied first, then the result is cut at
2,500 characters ([PROTOCOL § Arms](PROTOCOL.md#arms)). `finagent verify` replays 1,896 calls on every day and
in every arm (79 calls per day and arm, including argument variants), plus 24 stateful sequences, against
outputs recorded from the original code.

## The 32 tools

- **Parameters:** all are optional unless marked \*. The default is in brackets.
- **Arms:** the arms that rewrite the output. "Block" marks the seven tools whose readings are in the prompt.
- **Calls:** calls in the 150 shipped harness runs (`session.json.gz` traces): 810 calls in all,
  including the 150 `submit_decision` calls.
- **Technical readings:** the indicator choices and windows (EMA 8 / 21 / 55, 20-day Bollinger bands with a
  50-day z-score, RSI 14, the 63-day volatility z-score) are widely used technical-analysis settings; the code is
  our own.

| Tool | Parameters | Returns | Arms | Calls |
|---|---|---|---|---:|
| **Market data** | | | | |
| `get_daily_candles` | `days` (20) | daily bars `{date, open, high, low, close, volume}`, newest first | – | 31 |
| `get_weekly_candles` | `weeks` (12) | ISO-week bars `{week, start, end, open, high, low, close, volume}`, newest first | – | 6 |
| `get_monthly_candles` | `months` (12) | month bars, newest first | – | 1 |
| `get_returns` | `days` (20) | daily log returns in %, cumulative return, up and down day counts | – | 41 |
| `get_price_stats` | – | close, date, 52-week high and low and the distance to them, drawdown from the 252-day peak, 5/20/60/250-day returns | block; PLACEBO | 2 |
| **Technical readings** | | | | |
| `get_trend_signal` | – | `signal` (bullish / bearish / neutral from EMA 8 > 21 > 55), the three EMAs, spread 8–55 in %, close | block; NOLABEL, PLACEBO | 1 |
| `get_mean_reversion_signal` | – | `signal` (oversold / overbought when \|z\| > 2), 50-day z-score, 20-day Bollinger bands and position, close | block; NOLABEL, PLACEBO | 1 |
| `get_rsi` | `period` (14) | `rsi`, `period`, `signal` (< 30 oversold, > 70 overbought) | block; NOLABEL, PLACEBO | 1 |
| `get_macd` | – | MACD(12, 26, 9) line, `signal` line (numeric), histogram, `cross` (bullish / bearish / none) | block; NOLABEL, PLACEBO | 2 |
| `get_volatility_stats` | – | `ann_vol_10d_pct`, `ann_vol_20d_pct`, `ann_vol_60d_pct`, `parkinson_vol_10d_pct` (all annualised), `atr_14`, `atr_14_pct_of_price`, `vol_zscore_vs_63d`, `regime` (high / low / normal), `abs_move_yesterday_pct`, a fixed `note` | block; NOLABEL, UNIT5D, PLACEBO | 12 |
| `get_support_resistance` | – | close, up to 3 pivot resistances above and supports below (last 60 sessions) | block; PLACEBO | 1 |
| `get_volume_analysis` | – | today's volume, 20-day mean, ratio, 20-day price–volume correlation, `signal` (surge / quiet / normal) | – | 40 |
| **Risk and sizing** | | | | |
| `get_risk_budget` | `target_vol_pct` (15, annualised) | `trailing_vol_20d_pct` (**annualised**), maximum exposure for the target, current exposure and ex-ante risk, gap, shares to close it | – | 74 |
| `get_kelly_sizing` | `expected_return_pct`\*, `expected_vol_pct`\*, `risk_aversion` (32) | fractional-Kelly exposure (0 to 100 %), full Kelly, the inputs | – | 31 |
| `get_drawdown_stats` | – | total and peak assets, drawdown, P&L since the start, sessions so far | – | 15 |
| **Events** | | | | |
| `get_earnings_calendar` | `ticker` ("AAPL") | last and next report, trading days until the next one (within 35 days of it) | – | 47 |
| `get_event_risk` | `ticker` ("AAPL") | the stock's next-session moves after past report dates, mean absolute reaction against a mean day | – | 61 |
| **News** | | | | |
| `get_news` | `feed` ("ticker"), `days` (7), `limit` (20), `only_ticker` (true) | `{t, title, summary (first 300 characters), sentiment}`, newest first | – | 43 |
| `search_news` | `query`\*, `days` (30), `limit` (15) | number of matches; `{feed, t, title, summary (200 characters)}` | – | 7 |
| `get_news_stats` | `days` (14) | count and mean sentiment per day of items that mention the stock | – | 24 |
| `get_macro_news` | `days` (7), `limit` (10) | fiscal and monetary headlines | – | 1 |
| **Insider** | | | | |
| `get_insider_trades` | `days` (90), `limit` (20) | transactions dated before t | – | 0 |
| `get_insider_summary` | `days` (90) | buy and sell counts and shares, distinct insiders, `signal` | – | 1 |
| **Account** | | | | |
| `get_portfolio` | – | cash, shares, position value, total assets, exposure, shares per point of exposure, P&L | – | 37 |
| `get_trade_history` | `days` (10) | the last executed orders, newest first | – | 1 |
| `simulate_order` | `action`, `shares`, `target_exposure_pct` | the order that would execute (clamped to cash and shares held), resulting exposure and cash | – | 54 |
| **Memory** | | | | |
| `memory_read` | `days` (10) | past decisions with the stated p_up, mu, sigma, the next session's return, `sigma_vs_realized` (over / under / ok) | – | 42 |
| `memory_write` | `note`\* | `{saved, notes_total}` (notes cut at 500 characters) | – | 7 |
| `memory_search` | `query`\* | up to 10 notes and past reasonings that contain the query | – | 3 |
| `get_calibration_ledger` | – | scored sessions, sigma bias ("you overstate volatility" …), mean log sigma error, direction hit rate | – | 50 |
| `get_lessons` | – | worst session, exposure on the biggest moves against the average, a one-line lesson | – | 22 |
| **Decision** | | | | |
| `submit_decision` | `action`, `shares`, `target_exposure_pct` (integer), `p_up`, `expected_return_pct`, `expected_vol_pct`, `confidence`, `reasoning` | not executed: the session loop answers `recorded: <Action> <n> @ <close> -> exposure <x>% of assets`, plus a hint when the target is missed by more than 2 points | – | 150 |

One more call in the records was to a misspelled tool: Qwen3.8-27B called `get_memory_read` once.

## Quirks

These are kept on purpose, because every tool output must stay byte-identical to what the pilot's models
received.

- **The earnings tools know only AAPL.** The calendar holds AAPL report dates only, and the `ticker`
  argument defaults to `"AAPL"`.
  - For the six pilot stocks, both tools return no report ("next date not yet announced"), even on days
    whose news reports earnings (VST reported on 2026-05-07).
  - Called without a ticker, `get_earnings_calendar` reports AAPL's next report. On the HOOD and CB days
    it counts the trading days to that report in the stock's own bar dates after t (12 and 6), which
    reveals bar dates but no prices.
  - `get_event_risk` without a ticker reports *this* stock's moves after AAPL's report dates.
  - All 108 calls in the shipped runs (47 + 61) passed the stock's own ticker.
- **Any headline that contains "apple" counts as mentioning the stock.** This affects the `only_ticker`
  filter of `get_news` and the counts of `get_news_stats`.
- **Memory and calibration score a 1-day move.** `memory_read`, `get_calibration_ledger` and `get_lessons`
  compare each stated sigma with the next session's move, while the forecast asked for is 5-day. The
  `get_kelly_sizing` description still says "for the next session". In a pilot run, the memory holds the
  two anchor decisions of days t-2 and t-1, so for example `get_calibration_ledger` on VST says "you
  overstate volatility".
- **An annualised volatility is still available under UNIT5D.**
  - `get_risk_budget` reports `trailing_vol_20d_pct` in annual units, and no arm rewrites it. On VST it is
    39.4, the ORIG `ann_vol_20d_pct`.
  - The `get_volatility_stats` description says "Annualised" in every arm.
  - Under UNIT5D, a direct call of `get_volatility_stats` returns the 5-day equivalents, as the block does.
- **NOLABEL keeps two signals.** It removes the labels of the five readings listed under Arms. The
  `signal` of `get_volume_analysis` and `get_insider_summary` stays, and `get_macd.signal` is a number,
  not a label.
- **Arguments are read loosely.** Integer arguments go through `int()`, so `"5"` works.
  - Undeclared arguments are ignored, except `ticker`, which `get_news` and `get_news_stats` honour
    although their schemas do not list it.
  - `days` in `get_trade_history` and `memory_read` counts entries, not calendar days.
  - `target_exposure_pct` is an integer in `submit_decision` and a number in `simulate_order`.
- **Errors are answers.** A failing tool returns `{"error": "<Type>: <message>"}` (for example
  `get_rsi {"period": 0}` gives a `ZeroDivisionError`), and an unknown name returns
  `{"error": "unknown tool <name>"}`. The arm rewrite skips any output that holds `"error"`.
  `get_intraday_candles` is not offered, but it answers with an error that points to `get_daily_candles`.
- **The insider and macro feeds are empty** for all six stocks, so those tools return empty lists, and the
  prompt's sections read "(none)".
- **How the volatility is computed.** Annualised vol is the population sd of daily log returns × √252.
  Parkinson vol uses the 10-day mean of ln(high/low)² / (4 ln 2). ATR is the 14-day mean true range.
  The volatility regime compares the latest 21-day vol with the mean ± 1 sd of the last 63 such values.
