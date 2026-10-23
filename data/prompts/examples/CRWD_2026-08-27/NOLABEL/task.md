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

Trading day 2026-08-27 — CRWD

CLOSE 227.96   (last 10 closes: 2026-08-14:216.95 2026-08-17:213.90 2026-08-18:212.92 2026-08-19:201.63 2026-08-20:190.34 2026-08-21:191.95 2026-08-24:190.68 2026-08-25:185.38 2026-08-26:189.18 2026-08-27:227.96)

ACCOUNT
- cash 70335.40
- shares held 160
- position value 36473.60
- total assets 106809.00
- position 34.1% of total assets
- one percentage point of exposure = 4.7 shares at today's close

COMPANY NEWS (past 7 days, most recent 10)
- [20260828T081428] CrowdStrike, Marriott, American Express And More On CNBC’s ‘Final Trades’ (Benzinga)
- [20260828T063736] Nvidia's Guide Ignites a Broad AI Bid Ahead of Warsh's Jackson Hole Debut (ChartMill)
- [20260827T222442] CrowdStrike jumps 20%, Okta nearly 29% as AI demand drives blockbuster gains (CNBC)
- [20260827T191259] CrowdStrike CEO George Kurtz goes one-on-one with Jim Cramer (CNBC)
- [20260827T184542] CrowdStrike CEO: AI exposes dangerous cyber gaps that legacy tools can’t handle (CNBC)
- [20260827T162540] CrowdStrike CEO Says Every Customer Is Worried About 'Agentic Threats' (Benzinga)
- [20260827T154826] CrowdStrike Just Hacked The AI Boom: The Cybersecurity ETF Trade Taking Shape (Benzinga)
- [20260827T152852] Citigroup Maintains Buy on CrowdStrike Holdings, Raises Price Target to $260 (Benzinga)
- [20260827T145031] CrowdStrike’s AI-Fueled Plot Twist Has These ETFs Flying 38% Higher (Benzinga)
- [20260827T143206] Mizuho Maintains Outperform on CrowdStrike Holdings, Raises Price Target to $250 (Benzinga)

FISCAL POLICY NEWS
- (none)

MONETARY POLICY NEWS
- (none)

INSIDER TRANSACTIONS (filed before today)
- (none)

YOUR LAST 4 DECISIONS
- 2026-08-25: Buy 159 @ 185.38 -> exposure 29.5%, assets 100000
- 2026-08-26: Buy 1 @ 189.18 -> exposure 30.1%, assets 100604

PRICE TOOL READINGS (computed for you from the daily price history through today's close; each line is exactly what the named tool returns today)
- get_trend_signal: {"ema8": 202.83, "ema21": 202.55, "ema55": 190.73, "spread_8_55_pct": 6.35, "close": 227.9600067138672}
- get_rsi (period 14): {"rsi": 56.5, "period": 14}
- get_mean_reversion_signal: {"z_score_50d": 2.03, "bollinger_upper": 234.68, "bollinger_lower": 180.47, "bollinger_position": 0.88, "close": 227.9600067138672}
- get_macd: {"macd": 1.709, "signal": 3.097, "histogram": -1.388}
- get_price_stats: {"close": 227.9600067138672, "date": "2026-08-27", "high_52w": 229.0800018310547, "low_52w": 85.68000030517578, "pct_from_52w_high": -0.49, "pct_from_52w_low": 166.06, "drawdown_from_peak_pct": 0.0, "ret_5d_pct": 19.76, "ret_20d_pct": 23.08, "ret_60d_pct": 18.58, "ret_250d_pct": 106.3}
- get_support_resistance: {"close": 227.9600067138672, "resistance_above": [], "support_below": [181.0, 185.3, 201.75]}
- get_volatility_stats: {"ann_vol_10d_pct": 105.4, "ann_vol_20d_pct": 81.2, "ann_vol_60d_pct": 64.0, "parkinson_vol_10d_pct": 56.1, "atr_14": 11.42, "atr_14_pct_of_price": 5.01, "vol_zscore_vs_63d": 3.51, "abs_move_yesterday_pct": 18.65, "note": "big moves cluster: after a large move the next few days are usually larger than average"}

Decide today's action and write decision.json.

FILES IN THIS FOLDER (point-in-time: nothing in them is dated after the information above)
- prices.csv: daily open, high, low, close, volume of CRWD through today's close (2026-08-27), at today's price level
- news.csv: CRWD company news published before 09:00 New York time on the next trading day (time, headline, summary)
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
