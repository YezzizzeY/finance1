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

Trading day 2026-08-07 — MCHP

CLOSE 84.69   (last 10 closes: 2026-07-27:77.90 2026-07-28:75.71 2026-07-29:71.37 2026-07-30:75.01 2026-07-31:74.29 2026-08-03:75.22 2026-08-04:80.67 2026-08-05:77.79 2026-08-06:74.36 2026-08-07:84.69)

ACCOUNT
- cash 94798.36
- shares held 67
- position value 5674.23
- total assets 100472.59
- position 5.6% of total assets
- one percentage point of exposure = 11.9 shares at today's close

COMPANY NEWS (past 7 days, most recent 10)
- [20260810T045700] Microchip's Data Center Revenue Grew 98% Last Quarter. Here's Why It's Guiding to $1 Billion for the Year. (Yahoo)
- [20260808T161024] Is Microchip Technology (MCHP) Fairly Valued On Strong Earnings And Data Center Growth? (Yahoo)
- [20260808T011208] Why Microchip Technology (MCHP) Is Up 14.0% After Strong Q1 Results And New PCIe Gen 6 Push (Yahoo)
- [20260807T183228] UBS Maintains Buy on Microchip Technology, Lowers Price Target to $120 (Benzinga)
- [20260807T155908] Citigroup Maintains Buy on Microchip Technology, Lowers Price Target to $95 (Benzinga)
- [20260807T131300] MCHP Q1 Earnings Beat Estimates, Revenues Rise on Demand Recovery (Yahoo)
- [20260807T124404] Microchip Technology Stock Jumps, Leads SOX Index Higher (Yahoo)
- [20260807T094400] Buy MPWR and MCHP With Solid Short-Term Price and Long-Term EPS Upside (Yahoo)
- [20260807T092232] Truist Securities Maintains Hold on Microchip Technology, Lowers Price Target to $90 (Benzinga)
- [20260807T083000] Microchip Technology Incorporated Q1 2027 Earnings Call Summary (Yahoo)

FISCAL POLICY NEWS
- (none)

MONETARY POLICY NEWS
- (none)

INSIDER TRANSACTIONS (filed before today)
- (none)

YOUR LAST 4 DECISIONS
- 2026-08-05: Buy 64 @ 77.79 -> exposure 5.0%, assets 100000
- 2026-08-06: Buy 3 @ 74.36 -> exposure 5.0%, assets 99780

PRICE TOOL READINGS (computed for you from the daily price history through today's close; each line is exactly what the named tool returns today)
- get_trend_signal: {"ema8": 78.53, "ema21": 80.41, "ema55": 84.02, "spread_8_55_pct": 6.53, "close": 84.69000244140625}
- get_rsi (period 14): {"rsi": 54.6, "period": 14}
- get_mean_reversion_signal: {"z_score_50d": -0.34, "bollinger_upper": 88.62, "bollinger_lower": 71.02, "bollinger_position": 0.78, "close": 84.69000244140625}
- get_macd: {"macd": -2.598, "signal": -3.289, "histogram": 0.691}
- get_price_stats: {"close": 84.69000244140625, "date": "2026-08-07", "high_52w": 105.38109475045205, "low_52w": 47.56606428835759, "pct_from_52w_high": -19.63, "pct_from_52w_low": 78.05, "drawdown_from_peak_pct": -17.54, "ret_5d_pct": 14.0, "ret_20d_pct": -4.4, "ret_60d_pct": -12.88, "ret_250d_pct": 40.6}
- get_support_resistance: {"close": 84.69000244140625, "resistance_above": [92.02, 90.85, 85.66], "support_below": [72.58, 78.0, 81.6]}
- get_volatility_stats: {"ann_vol_10d_pct": 89.6, "ann_vol_20d_pct": 74.1, "ann_vol_60d_pct": 64.8, "parkinson_vol_10d_pct": 49.4, "atr_14": 4.66, "atr_14_pct_of_price": 5.51, "vol_zscore_vs_63d": 1.68, "abs_move_yesterday_pct": 13.01, "note": "big moves cluster: after a large move the next few days are usually larger than average"}

Decide today's action and write decision.json.

FILES IN THIS FOLDER (point-in-time: nothing in them is dated after the information above)
- prices.csv: daily open, high, low, close, volume of MCHP through today's close (2026-08-07), at today's price level
- news.csv: MCHP company news published before 09:00 New York time on the next trading day (time, headline, summary)
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
