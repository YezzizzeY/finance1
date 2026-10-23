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

Trading day 2026-05-07 — MRK

CLOSE 111.50   (last 10 closes: 2026-04-24:111.10 2026-04-27:109.44 2026-04-28:109.24 2026-04-29:110.16 2026-04-30:108.40 2026-05-01:111.36 2026-05-04:112.30 2026-05-05:112.34 2026-05-06:112.75 2026-05-07:111.50)

ACCOUNT
- cash 94944.60
- shares held 45
- position value 5017.42
- total assets 99962.02
- position 5.0% of total assets
- one percentage point of exposure = 9.0 shares at today's close

COMPANY NEWS (past 7 days, most recent 10)
- [20260508T063708] Merck : Statement on Daiichi Sankyo Update to Manufacturing and Supply Plan - Merck.com (Finnhub)
- [20260507T140954] Merck Announces Publication Of Paper Describing Unique Manufacturing Methods For Enlicitide Decanoate Oral PCSK9 Inhibitor (Benzinga)
- [20260507T140500] Merck Scientists Publish Landmark Paper on Novel Method for Large-Scale Biocatalytic Synthesis of Investigational Oral PCSK9 Inhibitor, Enlicitide Decanoate (Yahoo)
- [20260507T080000] Merck Becomes Sole Testing Provider for Genetix Biotherapeutics’ FDA-Approved Gene Therapies (Yahoo)
- [20260507T003212] Salesforce AI Win With Merck Highlights Real World Platform Adoption (Yahoo)
- [20260506T145520] Analyst Raises Merck (MRK) Price Target by $1 After Beating Q1 Estimates (Yahoo)
- [20260506T101610] Is Merck (MRK) Still Attractive After Recent Pullback And Conflicting Valuation Signals (Yahoo)
- [20260506T090000] Merck Animal Health Selects Salesforce’s Agentforce Life Sciences for Customer Engagement to Transform Animal Care and Enhance Support Experiences for Employees (Yahoo)
- [20260506T075104] Here Are Wednesday’s Top Wall Street Analyst Research Calls: Advanced Micro Devices, American Eagle Outfitters, GlobalFoundries, IAC, Merck, Palantir Technologies, Reddit, and More (Yahoo)
- [20260505T131734] Merck Stock Looks Undervalued as KEYTRUDA Growth and Pipeline Offset Near-Term Headwinds (Yahoo)

FISCAL POLICY NEWS
- (none)

MONETARY POLICY NEWS
- (none)

INSIDER TRANSACTIONS (filed before today)
- (none)

YOUR LAST 4 DECISIONS
- 2026-05-05: Buy 45 @ 112.34 -> exposure 5.1%, assets 100000
- 2026-05-06: Hold 0 @ 112.75 -> exposure 5.1%, assets 100018

PRICE TOOL READINGS (computed for you from the daily price history through today's close; each line is exactly what the named tool returns today)
- get_trend_signal: {"signal": "bearish", "ema8": 111.77, "ema21": 113.23, "ema55": 113.86, "spread_8_55_pct": 1.83, "close": 111.49819946289062}
- get_rsi (period 14): {"rsi": 34.2, "period": 14, "signal": "neutral"}
- get_mean_reversion_signal: {"signal": "neutral", "z_score_50d": -1.18, "bollinger_upper": 120.68, "bollinger_lower": 106.45, "bollinger_position": 0.35, "close": 111.49819946289062}
- get_macd: {"macd": -1.51, "signal": -1.522, "histogram": 0.011, "cross": "bullish"}
- get_price_stats: {"close": 111.49819946289062, "date": "2026-05-07", "high_52w": 123.33302108292563, "low_52w": 70.23517108691551, "pct_from_52w_high": -9.6, "pct_from_52w_low": 58.75, "drawdown_from_peak_pct": -8.83, "ret_5d_pct": 2.86, "ret_20d_pct": -8.46, "ret_60d_pct": -3.43, "ret_250d_pct": 49.88}
- get_support_resistance: {"close": 111.49819946289062, "resistance_above": [117.28, 116.19, 113.8], "support_below": [107.13]}
- get_volatility_stats: {"ann_vol_10d_pct": 22.6, "ann_vol_20d_pct": 26.7, "ann_vol_60d_pct": 24.2, "parkinson_vol_10d_pct": 23.5, "atr_14": 2.95, "atr_14_pct_of_price": 2.65, "vol_zscore_vs_63d": 0.53, "regime": "normal", "abs_move_yesterday_pct": 1.12, "note": "big moves cluster: after a large move the next few days are usually larger than average"}

Decide today's action and write decision.json.

FILES IN THIS FOLDER (point-in-time: nothing in them is dated after the information above)
- prices.csv: daily open, high, low, close, volume of MRK through today's close (2026-05-07), at today's price level
- news.csv: MRK company news published before 09:00 New York time on the next trading day (time, headline, summary)
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
