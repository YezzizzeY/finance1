# SALIENCE: does the size of the annualised volatility number predict the agent's 5-day forecast, beyond the rational benchmark?

Question: `get_volatility_stats` returns `ann_vol_10d_pct` / `ann_vol_20d_pct` / `ann_vol_60d_pct` /
`parkinson_vol_10d_pct`, all on an **annualised** scale (roughly 7x the 5-day scale `expected_vol_pct` should be
on). Does the agent's submitted `expected_vol_pct` track the headline annualised number (`ann_vol_20d_pct`) more
than the rational benchmark justifies?

All numbers below are reproduced by `src/finagent/mechanisms/salience.py` against the raw session files; nothing here is
hand-typed except the prose. Full numeric results, the regression coefficients, and all six verbatim quotes with
metadata are in `data.json`.

## Corpora

| corpus | model | usable sessions | why |
|---|---|---|---|
| `data/mechanisms/sessions/newsagent`, **FULL** arm, k=0..3 (primary) | Qwen3.5-9B | 694 | valid submit_decision + >=1 `get_volatility_stats` call |
| same, **NO_NEWS** arm, k=0..3 | Qwen3.5-9B | 751 | same filter |
| `data/mechanisms/sessions/q3news_s1`, FULL/NO_NEWS (cross-check) | Qwen3-8B, thinking on | 155 / 139 | same filter; most q3news sessions never call `get_volatility_stats` at all, so usable N is much smaller than the corpus size (1988 files) |
| `data/mechanisms/salience/grounding_A_main`, FULL_G/NO_NEWS_G | Qwen3-8B | **0 — skipped** | checked every one of the 2000 session traces: tool_calls contains only `submit_decision` in 1,998/2,000; 2/2,000 additionally call `get_risk_budget` (never `get_volatility_stats`). `get_volatility_stats` specifically is never invoked anywhere in this corpus (0/2,000). In this corpus the price-tool readings are injected as static text in the user prompt rather than retrieved by a tool call, so the task's own inclusion rule ("`get_volatility_stats` called at least once") yields zero usable sessions by construction. Reported as skipped, not substituted with a weaker proxy (e.g. scanning the prompt text for the same numbers would test a different mechanism). |

`FULL_T06_*` files (temperature=0.6, label `FULL_T06`, 500 files in newsagent) are a separate temperature-robustness
arm and are excluded from the k=0..3 FULL/NO_NEWS scan described above.

## Rational benchmark join

`day_id` (`TICKER_date`) is looked up as `event_id` in `data/mechanisms/salience/rcf_20261011/events_all.parquet` first,
falling back to `nonevent_days.parquet` (joined on `ticker+t`, `sigma = exp(lsig)`) for misses. **Join hit rate:
1739/1739 = 100%** across all session rows used in this analysis (1697 via `events_all`, 42 via the fallback).
The 6/250 newsagent day_ids missing from `events_all` (CSGP_2026-03-31, ED_2026-03-12, GLW_2026-03-12,
GWW_2026-06-16, IDXX_2026-08-04, PG_2026-03-12) were checked individually and are all present in
`nonevent_days.parquet`.

**Scale conversion for `rational_sigma5_equivalent`: none needed.** `data/mechanisms/salience/rcf_20261011/rule.json`,
field `operationalization.target_and_bins`, states: `R5 = 100 ln(C[t+5]/C[t])` (realised 5-day log return, in
percent) and `sigma = exp(lsig)`, both at close `t`, with `u = (R5-m)/sigma`. So `events_all.sigma` is *already*
the rational model's standard deviation of the 5-day percent log return — the same units (percent) and the same
horizon (5 trading days) as the agent's `expected_vol_pct`. It is used unscaled as `rational_sigma5_pct`.

## Realised 5-day volatility (`rv5`, used for the accuracy metric in step 3)

`rv5 = sqrt(sum of the 5 squared daily log returns, in percent)` from close `t` to close `t+5`, computed from
`data/panel/us_daily_stratos_20260924.parquet` (`config.PANEL`). This matches the project's own `rv5` definition already in
the research workspace's `repro/rsize/rules_doc.py` ("sqrt of the sum of the 5 squared daily log returns (percent)"). Validated against the
benchmark: for `AAPL_2026-03-19`, summing the 5 panel daily log returns reproduces `events_all.R5 = 1.566235` to
6 decimal places, confirming date alignment. `rv5` (not `|R5|`) is used because `R5` is a *signed* return, not a
volatility; `|R5|` would be a much noisier single-path proxy for the same thing `rv5` measures directly.

## Step 2 — OLS: does the annualised number carry information the rational benchmark doesn't?

Model 1: `expected_vol_pct ~ a + b1*rational_sigma5_pct`. Model 2: adds `b2*ann_vol_20d_pct`. Closed-form OLS via
numpy (no scipy/statsmodels in the venv — checked, both absent). Classical OLS SE reported; HC1-robust SE also
computed as a check (in `data.json`, both move the conclusion by nothing).

| corpus / arm | n | b1 (SE) | model-1 R² | b2 (SE) | model-2 R² | Δ R² |
|---|---|---|---|---|---|---|
| newsagent **FULL** (primary) | 694 | 0.566 (0.069) | 0.0880 | **−0.0073 (0.0205)**, t=−0.36 | 0.0881 | **+0.00017** |
| newsagent **NO_NEWS** | 751 | 0.572 (0.069) | — | +0.0047 (0.0210), t=0.22 | 0.0844 | +0.00006 |
| q3news S1 **FULL** (cross-check, small n) | 155 | 0.059 (0.298) | 0.0003 | −0.0433 (0.1016), t=−0.43 | 0.0014 | +0.00119 |

**b2 is small and not statistically distinguishable from 0 in every corpus/arm.** Adding the annualised headline
number to a regression that already has the rational benchmark buys essentially no extra R² anywhere
(Δ R² ≤ 0.0012). **Taken at face value, the aggregate linear test does not detect a smooth, sample-wide anchoring
effect of `ann_vol_20d_pct`.**

## Step 3 — copied vs. not-copied subgroup (this is where the effect actually is)

Definition: `looks_copied` = `|expected_vol_pct − ann_vol_20d_pct| / ann_vol_20d_pct ≤ 0.15`. Accuracy metric:
`|ln(expected_vol_pct / rv5)|` (lower = better-calibrated magnitude), restricted to sessions with `rv5 > 0`.

| group | newsagent FULL (n=694) | newsagent NO_NEWS (n=751) | combined (n=1445) |
|---|---|---|---|
| looks-copied: n (%) | 15 (2.16%) | 12 (1.60%) | 27 (1.87%) |
| looks-copied: mean \|ln ratio err\| (SE) | 1.70 (0.17) | 1.76 (0.19) | 1.73 (0.13) |
| not-copied: n (%) | 679 (97.8%) | 739 (98.4%) | 1418 (98.1%) |
| not-copied: mean \|ln ratio err\| (SE) | 0.60 (0.017) | 0.63 (0.017) | 0.62 (0.012) |
| difference (SE), t | 1.10 (0.17), t=6.39 | 1.13 (0.19), t=5.82 | **1.11 (0.13), t=8.78** |

The copied group is **rare (~2% of sessions)** but **forecasts much worse**: a mean absolute log-ratio error of
1.73 vs 0.62 means the typical copied-group miss is roughly e^1.73≈5.6x off vs e^0.62≈1.9x for everyone else. The
difference is large and precise (t=8.78 combined) because within-group variance, not the small n, sets the SE of
the *difference in means*; the SE on the *group size* itself (12-27) is the genuinely small-sample part — treat the
2.16%/1.60% copying-rate estimates as noisy, the 1.11-point accuracy gap as solid.

**Reconciling steps 2 and 3**: these are not in tension. Step 2's regression is a smooth, sample-wide linear
test and correctly reports ~0 slope when ~98% of sessions are unaffected. Step 3 shows the real effect is a
**rare, discrete, near-total copy** (expected_vol_pct lands within 15% of the literal annualised figure, which
requires reporting ~7x too much vol relative to a correct sqrt-time 5-day conversion) rather than a graded bias
that nudges everyone's forecast upward a little. A linear-in-the-whole-sample test is the wrong tool to detect a
rare, large, binary failure — the task's step 3 design (explicit subgroup split) is what actually surfaces it.

## Step 5 — does the effect differ between FULL (news) and NO_NEWS?

- Regression b2: FULL −0.0073 (0.0205) vs NO_NEWS +0.0047 (0.0210); diff −0.0120 (SE 0.0293), t=−0.41 — not
  significant, but b2 is indistinguishable from 0 in both arms to begin with.
- Copying **rate**: FULL 2.16% (15/694) vs NO_NEWS 1.60% (12/751); diff +0.56pp (SE 0.71pp), two-proportion
  z=0.79, p≈0.43 (normal approx) — not significant.

**Neither comparison finds a difference between arms, but both are low-powered** (12-15 copied events per arm).
This is "no evidence of a difference," not "confirmed no difference." At face value it is consistent with the
project's established finding that price-tool salience operates largely independently of whether news is also
competing for attention in context — the literal-copy failure shows up at a similarly small rate either way.

## Examples (verbatim, verified against the raw `.json.gz` files)

All six quotes below were re-extracted directly from the gzip session files and checked with `assert quote in
raw_reasoning_text` before being written to `data.json` — see `build_examples` in `src/finagent/mechanisms/salience.py`. Full metadata (day_id,
ticker, model, arm, k, file path, submitted `expected_vol_pct`) is in `data.json.examples`.

**(a) clear anchoring on the annualised number — V_2026-06-01, FULL k=3** (submitted `expected_vol_pct=16.4`,
literally equal to `ann_vol_20d_pct=16.4`; rational 5-day sigma was 3.37%, realised 5-day vol 3.74%):
> **Volatility**: 16.4% annualized (20-day), regime "low", recent move was 1.11%
> ...
> Volatility remains subdued at approximately 16% annually.

**(a) second — HAL_2026-03-20, FULL k=1** (submitted `expected_vol_pct=30.0` ≈ `ann_vol_20d_pct=30.1`; rational
5-day sigma 4.67%, realised 5.34%):
> Recent volatility is elevated (33.5-36.5% annualized), but regime is "normal"
> ...
> My forecast anticipates modest gains around 0.8% with elevated volatility in the 30% range, reflecting the stock's current dynamic price environment.

**(c) positive contrast, correct conversion — BAC_2026-03-17, FULL k=1** (submitted `expected_vol_pct=4.0`):
> expected_vol_pct: Volatility is high at 28.4% annualized, so 5-day vol would be roughly sqrt(5) * daily vol. Daily vol ≈ 28.4%/sqrt(252) ≈ 1.77%. 5-day vol ≈ 1.77% * sqrt(5) ≈ 3.95%

**Paired same-day contrast — HWM_2026-03-27** (both rollouts see "31-34% annualized"): k=1 converts correctly
and submits **13.0** ("5-day vol is roughly sqrt(5) times daily, or about 12-15% one-standard-deviation"); k=3,
a different sampled rollout of the *same ticker/day*, anchors on the annualised band instead and submits **27.0**
("I anticipate volatility between 25-30%"). Shows the failure is a per-rollout sampling event, not a fixed
property of the ticker/day.

**(b) bonus — trace/answer mismatch, MSCI_2026-06-11, FULL k=1** (submitted `expected_vol_pct=6.5`): within the
*same* session the model first mis-derives the daily vol (divides by sqrt(20) instead of sqrt(252)), gets 14.3%
and rejects it as implausible, then correctly restates the metric definition and redoes the math to 4.07% —
but still submits 6.5%, ~60% above its own correctly-computed number:
> Wait, expected_vol_pct is the one-standard-deviation size of the 5-day return in percent. Given annualized vol of ~28.9% over 20 days, daily vol would be ~sqrt(1/20)*28.9% = ~6.4% per day. Over 5 days, volatility accumulates as sqrt(5)*6.4% ≈ 14.3%. But that seems high.
> ...
> Actually, the expected_vol_pct parameter is "one-standard-deviation size of the 5-day return, percent (not annualised, not daily)". So if daily return has std dev of X%, 5-day return would have std dev of X% * sqrt(5).
>
> Given 20-day annualized vol of 28.9%, daily vol ≈ 28.9% / sqrt(252) ≈ 1.82% per day. Over 5 days: 1.82% * sqrt(5) ≈ 4.07%.

## Limitations / open questions (see `data.json.limitations_and_open_questions`)

- Grounding corpus untested for this mechanism (0 usable sessions, by construction — see above).
- q3news cross-check N is small (155/139) and its coefficients are noisy; read as directionally consistent, not
  as independent confirmation at comparable precision.
- The copied-group size (12-27) is too small to stratify further (by ticker, regime, k) without very wide
  uncertainty — not attempted here.
- SEs treat each (day_id, k) rollout as independent; up to 4 rollouts share a ticker/day, so classical SEs here
  are a lower bound under day-level clustering. Reported effect signs/magnitudes (b2≈0, copy-group gap large)
  are unlikely to flip under clustering, but the step-3 group-size CIs would widen somewhat.

## How to reproduce

```sh
finagent mech-salience           # -> results/mechanisms/salience/data.json (about 10 s); --check compares instead
.venv/bin/python -m pytest -q tests/test_mechanisms_salience.py
```

`src/finagent/mechanisms/salience.py` is a port of the research workspace's four scripts
(`results/mech4_20261023/salience/scripts/`), with every path taken from `finagent.config` and the inputs listed in
[`data/mechanisms/salience/README.md`](../../../data/mechanisms/salience/README.md):

1. `scan_corpus` / `extract_session` (was `extract.py`) — scans the three corpora's session `.json.gz` files in sorted
   order, keeps sessions with a valid `submit_decision` and >=1 `get_volatility_stats` call, and takes the last
   `get_volatility_stats` result and the `submit_decision` args; for the grounding corpus it also counts which tools
   each session calls.
2. `Benchmark`, `regression_block`, `copied_analysis` (was `analyze.py`) — joins the rational benchmark
   (`events_all.parquet` → `nonevent_days.parquet` fallback), computes realised `rv5` from the daily panel, runs the
   OLS models (hand-rolled closed-form, numpy normal equations) and the copied-vs-not-copied comparison.
3. `build_examples`, `copy_rate_test` (was `finalize.py`) — re-opens the raw `.json.gz` files of the six example
   sessions, asserts each quoted fragment is found verbatim in that raw text, and runs the FULL-vs-NO_NEWS copy-rate
   two-proportion z-test.
4. `build` (was `build_data_json.py`) — assembles `data.json` (keys sorted, indent=1, NaN/Infinity scrubbed to
   `null`). The prose is kept verbatim in `salience_text.py`; before writing, every number the prose quotes is
   re-derived from the computed values and checked.

The same file order and the same numpy/pandas operations as the original give bit-identical numbers: all 183 numeric
values of the workspace `data.json` are reproduced exactly. Only path strings differ (they now name this
repository's files), and two runs give byte-identical output.
