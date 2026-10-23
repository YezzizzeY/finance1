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

Trading day 2026-04-14 — HOOD

CLOSE 79.09   (last 10 closes: 2026-03-31:69.30 2026-04-01:70.11 2026-04-02:68.90 2026-04-06:69.78 2026-04-07:69.65 2026-04-08:71.83 2026-04-09:70.12 2026-04-10:69.19 2026-04-13:71.67 2026-04-14:79.09)

ACCOUNT
- cash 70707.83
- shares held 423
- position value 33455.07
- total assets 104162.90
- position 32.1% of total assets
- one percentage point of exposure = 13.2 shares at today's close

COMPANY NEWS (past 7 days, most recent 10)
- [20260415T085800] Robinhood Gets Good News From the SEC. Why the Stock Is Jumping. (Yahoo)
- [20260415T080302] Robinhood stock jumps as SEC scraps $25K pattern day trader rule (Yahoo)
- [20260415T073705] End of ‘Pattern Day Trader’ Rule Could Turbocharge Retail Stock Trading (Yahoo)
- [20260415T072750] Stocks making the biggest moves premarket: Bank of America, Morgan Stanley, Robinhood & more (CNBC)
- [20260415T063551] Social Buzz: Wallstreetbets Stocks Mixed Pre-Bell Wednesday; Robinhood Markets to Advance, Micron Technology to Decline (Yahoo)
- [20260415T060000] How Retail Investors are navigating volatility (Yahoo)
- [20260414T212232] Meta, Broadcom, IonQ, D-Wave Quantum And Robinhood: Why These 5 Stocks Are On Investors' Radars Today (Benzinga)
- [20260414T160612] Robinhood shares jump following raised price target (CNBC)
- [20260414T133655] Why Robinhood shares are seen to double (Yahoo)
- [20260414T123100] Cantor Fitzgerald Says Robinhood and Coinbase Are Best Positioned for Prediction Market Growth (Yahoo)

FISCAL POLICY NEWS
- (none)

MONETARY POLICY NEWS
- (none)

INSIDER TRANSACTIONS (filed before today)
- (none)

YOUR LAST 4 DECISIONS
- 2026-04-10: Buy 413 @ 69.19 -> exposure 28.6%, assets 100000
- 2026-04-13: Buy 10 @ 71.67 -> exposure 30.0%, assets 101024

PRICE TOOL READINGS (computed for you from the daily price history through today's close; each line is exactly what the named tool returns today)
- get_trend_signal: {"signal": "bearish", "ema8": 72.25, "ema21": 72.38, "ema55": 80.6, "spread_8_55_pct": 10.37, "close": 79.08999633789062}
- get_rsi (period 14): {"rsi": 65.3, "period": 14, "signal": "neutral"}
- get_mean_reversion_signal: {"signal": "neutral", "z_score_50d": 0.69, "bollinger_upper": 77.68, "bollinger_lower": 64.57, "bollinger_position": 1.11, "close": 79.08999633789062}
- get_macd: {"macd": -1.411, "signal": -2.663, "histogram": 1.252, "cross": "none"}
- get_price_stats: {"close": 79.08999633789062, "date": "2026-04-14", "high_52w": 153.86000061035156, "low_52w": 39.209999084472656, "pct_from_52w_high": -48.6, "pct_from_52w_low": 101.71, "drawdown_from_peak_pct": -48.12, "ret_5d_pct": 13.55, "ret_20d_pct": 5.02, "ret_60d_pct": -28.33, "ret_250d_pct": 79.18}
- get_support_resistance: {"close": 79.08999633789062, "resistance_above": [84.75, 80.75, 79.57], "support_below": [72.25, 72.79, 75.55]}
- get_volatility_stats: {"ann_vol_10d_pct": 57.9, "ann_vol_20d_pct": 62.7, "ann_vol_60d_pct": 72.5, "parkinson_vol_10d_pct": 52.7, "atr_14": 4.32, "atr_14_pct_of_price": 5.46, "vol_zscore_vs_63d": -0.22, "regime": "normal", "abs_move_yesterday_pct": 9.85, "note": "big moves cluster: after a large move the next few days are usually larger than average"}

Decide today's action and write decision.json.

FILES IN THIS FOLDER (point-in-time: nothing in them is dated after the information above)
- prices.csv: daily open, high, low, close, volume of HOOD through today's close (2026-04-14), at today's price level
- news.csv: HOOD company news published before 09:00 New York time on the next trading day (time, headline, summary)
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
