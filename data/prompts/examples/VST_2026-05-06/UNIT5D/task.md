ROLE AND RULES
You are a fund manager trading a single US stock with a fixed cash account.

This task gives you one trading day's information, point-in-time: nothing
in it is dated on or after that day's close except the day's own OHLCV bar and company
news published before 09:00 New York time on the next trading day, before that session opens.

Decide one action for the day: Buy, Sell or Hold, and the number of shares.
Rules of the account:
- You may only hold long positions; shares held cannot go below zero.
- A buy costs shares x close price and must fit the available cash.
- Orders execute at that day's close price.
You may read the files in this folder and write and run code to analyse them.
Size the position as a share of total assets, not as a fixed dollar ticket.
decision.json takes the exposure you are targeting (target_exposure_pct) together with
the share count that implements it (one percentage point of exposure in shares is given in
the ACCOUNT block). The file you leave in decision.json is the order that executes.
Finish the day by writing decision.json.
In decision.json also state your forecast for the NEXT 5 TRADING DAYS:
p_up (probability that the close 5 trading days from now is above today's close, 0-1), expected_return_pct
(the mean 5-day return you expect, percent, may be negative) and
expected_vol_pct (your one-standard-deviation estimate of the 5-day return, in percent: the typical size of the
move over the next 5 trading days; not annualised and not a single-day figure).

====================================================================================================

Trading day 2026-05-06 — VST

CLOSE 158.07   (last 10 closes: 2026-04-23:156.63 2026-04-24:164.12 2026-04-27:166.35 2026-04-28:160.89 2026-04-29:153.57 2026-04-30:157.62 2026-05-01:155.06 2026-05-04:160.63 2026-05-05:160.16 2026-05-06:158.07)

ACCOUNT
- cash 61931.86
- shares held 237
- position value 37462.27
- total assets 99394.13
- position 37.7% of total assets
- one percentage point of exposure = 6.3 shares at today's close

COMPANY NEWS (past 7 days, most recent 10)
- [20260507T081647] Vistra swings to quarterly profit on rising power demand (Finnhub)
- [20260507T071622] Vistra : 2026 First Quarter Presentation (Finnhub)
- [20260507T070000] Vistra Reports First Quarter 2026 Results (Yahoo)
- [20260506T165000] The Smartest Energy Stocks to Buy With $1,000 Right Now (Yahoo)
- [20260506T152827] Is It Too Late To Consider Vistra (VST) After Its Multi Year Surge In Returns (Yahoo)
- [20260506T145804] Oklo Milestone Lifts These Nuclear Stocks Ahead Of Earnings (Yahoo)
- [20260506T101600] All Eyes on Vistra's Q1 Earnings: What Lies Ahead for the Stock? (Yahoo)
- [20260505T132942] Why Vistra (VST) Is Gaining From AI-Driven Power Demand (Yahoo)
- [20260505T103500] Utilities in Focus: 3 Stocks That Could Lead This Earnings Cycle (Yahoo)
- [20260505T031107] Do Vistra’s Higher Dividends Reveal Its True Capital Allocation Priorities (VST)? (Yahoo)

FISCAL POLICY NEWS
- (none)

MONETARY POLICY NEWS
- (none)

INSIDER TRANSACTIONS (filed before today)
- (none)

YOUR LAST 4 DECISIONS
- 2026-05-04: Buy 237 @ 160.63 -> exposure 38.1%, assets 100000
- 2026-05-05: Hold 0 @ 160.16 -> exposure 38.0%, assets 99889

PRICE TOOL READINGS (computed for you from the daily price history through today's close; each line is exactly what the named tool returns today)
- get_trend_signal: {"signal": "neutral", "ema8": 158.75, "ema21": 158.53, "ema55": 159.64, "spread_8_55_pct": 0.56, "close": 158.06863403320312}
- get_rsi (period 14): {"rsi": 42.7, "period": 14, "signal": "neutral"}
- get_mean_reversion_signal: {"signal": "neutral", "z_score_50d": -0.16, "bollinger_upper": 167.24, "bollinger_lower": 151.04, "bollinger_position": 0.43, "close": 158.06863403320312}
- get_macd: {"macd": 0.217, "signal": 0.256, "histogram": -0.039, "cross": "bearish"}
- get_price_stats: {"close": 158.06863403320312, "date": "2026-05-06", "high_52w": 218.90834935343653, "low_52w": 132.86377706411287, "pct_from_52w_high": -27.79, "pct_from_52w_low": 18.97, "drawdown_from_peak_pct": -27.16, "ret_5d_pct": 2.93, "ret_20d_pct": 1.54, "ret_60d_pct": 3.62, "ret_250d_pct": 14.05}
- get_support_resistance: {"close": 158.06863403320312, "resistance_above": [168.18, 162.3, 159.98], "support_below": [152.87, 153.91, 154.57]}
- get_volatility_stats: {"vol_5d_equiv_from_10d_pct": 6.3, "vol_5d_equiv_from_20d_pct": 5.5, "vol_5d_equiv_from_60d_pct": 6.7, "parkinson_vol_5d_equiv_from_10d_pct": 5.5, "atr_14": 6.56, "atr_14_pct_of_price": 4.15, "vol_zscore_vs_63d": -1.08, "regime": "low", "abs_move_yesterday_pct": 1.31, "note": "big moves cluster: after a large move the next few days are usually larger than average"}

Decide today's action and write decision.json.

FILES IN THIS FOLDER (point-in-time: nothing in them is dated after the information above)
- prices.csv: daily open, high, low, close, volume of VST through today's close (2026-05-06), at today's price level
- news.csv: VST company news published before 09:00 New York time on the next trading day (time, headline, summary)
- account.json: your account and your last decisions
- task.md: this file

HOW TO WORK
You may read these files and write and run code in this folder. Network access is disabled and you can write only inside this
folder. Use only the information in this folder.

Finish by writing decision.json in this folder: one JSON object with these fields (the fields of submit_decision)
- action: "Buy", "Sell" or "Hold"
- shares: integer number of shares to buy or sell (0 for Hold)
- target_exposure_pct: the exposure you are targeting, percent of total assets
- p_up: probability that the close 5 trading days from now is above today's close, 0-1
- expected_return_pct: the mean 5-day return you expect, percent (may be negative)
- expected_vol_pct: your one-standard-deviation estimate of the 5-day return, percent (5-day one-sd; not annualised and not a
  single-day figure)
- confidence: 0-1, how much information you have for this forecast (how much you would stake on it being accurate)
- reasoning: one or two sentences
