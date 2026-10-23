# Proximity / recency: does calling position (not magnitude) predict reliance?

Analysis 2 of 4 in the mechanism set (`results/mechanisms/`). Question: independent of how large/salient a
number is, does its **position** in the tool-call sequence — specifically, how close it sits
to the final `submit_decision` — predict how much weight the agent gives it?

All numbers below are reproducible from `data.json` in this folder. This file explains how
they were computed. The code is `src/finagent/mechanisms/proximity.py` (statistics in
`src/finagent/mechanisms/proximity_stats.py`); `finagent mech-proximity`
rewrites `data.json` byte for byte from the session files.

## Corpus and natural experiment

`data/mechanisms/sessions/newsagent/<TICKER>_<date>/FULL_{0,1,2,3}.json.gz` — the FULL
(news+tools) arm, **temperature = 1.0 runs only** (the `FULL_T06_*` temperature-0.6 files were
excluded, per the task spec). 250 ticker-days × up to 4 k-runs = 1000 session files.

At temperature 1.0, the agent itself freely decides which tools to call and in what order. For
the same ticker-day, some k-runs call `get_volatility_stats` as the very last tool before
`submit_decision`; other k-runs (same day, same information available, since the tool's output
is a deterministic function of the point-in-time price history) call it earlier and do other
tool calls afterward. This gives a natural within-day, within-information experiment on
calling-position alone.

**Verified structural fact:** `ann_vol_20d_pct` from `get_volatility_stats` is byte-identical
across every k-run of the same `day_id` (checked all 250 days with ≥1 usable session — 0 days
show any variation). So within a matched day, the *magnitude* the agent is given is exactly
fixed, and only calling position (and free generation) varies.

## Extraction rules

- A trace entry is a "tool-call record" if it has a `tool` key (this excludes the separate
  `turn` entries that just list which tools the model decided to call in a batch).
- `is_last = True` for `get_volatility_stats` iff it is the tool-call record immediately
  preceding the `submit_decision` tool-call record — i.e., zero other tool-call records sit
  between them, in trace list order.
- Usable session: `valid == True`; exactly one `get_volatility_stats` call; exactly one
  `submit_decision` call, which is the session's final tool-call record; `submit_decision.args`
  has a numeric `expected_vol_pct`; the `get_volatility_stats` result (a JSON string — parsed
  with `json.loads`) has `ann_vol_20d_pct`.
- 1000 files attempted → 9 invalid, 234 never call `get_volatility_stats`, 3 call it more than
  once (excluded to keep "exactly one call" unambiguous) → **754 usable sessions**, spanning all
  250 days. 187 are `is_last=True`, 567 are `is_last=False`.
- Of the 250 days, **128 days have at least one session in each `is_last` group** (420 sessions
  total: 162 `is_last=True`, 258 `is_last=False`). This matched-day subset is the primary sample
  for the position test, since it is the part of the data where magnitude is provably held fixed
  across the comparison.

## Step 2: does position change the magnitude→reliance slope (or level)?

Three complementary tests, all closed-form (no scipy/statsmodels in the project `.venv` — see
Stats methods below):

1. **Slope comparison.** Within the 128 matched days, simple OLS of `expected_vol_pct` on
   `ann_vol_20d_pct`, fit separately in the `is_last=True` and `is_last=False` subsamples.
   Compare slopes with a Welch-style z-test (`SE_diff = sqrt(se1²+se2²)`).
2. **Within-day fixed-effects level test.** Because `ann_vol_20d_pct` is day-constant, day-demean
   both `expected_vol_pct` and the `is_last` dummy and regress; this isolates the pure *level*
   effect of position holding the true number exactly fixed per day. Reported alongside a plain
   unweighted paired per-day mean-difference t-test (one observation per day: mean(True) −
   mean(False)) as a simpler cross-check.
3. **Reliance-ratio check.** Mean of `expected_vol_pct / ann_vol_20d_pct` (and its log) by group.

**Result (see `step2_results` in data.json): no detectable effect of position, on every cut.**
- Matched-day slopes: `is_last=True` b=0.0439 (SE 0.0167, n=162, r=0.203, p=0.0095 vs 0);
  `is_last=False` b=0.0550 (SE 0.0124, n=258, r=0.267, p<0.0001 vs 0). Both slopes are
  individually significant (agents do track the tool's magnitude, as expected), but the
  **difference between them is not**: diff=−0.011, SE=0.021, z=−0.54, p=0.59; 95% CIs
  [0.011,0.077] and [0.031,0.079] overlap heavily.
- Day-FE level test: coefficient on `is_last` = −0.12 percentage points (SE 0.36), p=0.73.
- Paired per-day t-test (n=128 days): mean difference = −0.23 pp (SE 0.39), p=0.55.
- Reliance ratio: 0.2235 (SE 0.0137) when last vs 0.2227 (SE 0.0092) when not last —
  indistinguishable.
- Robustness: repeating the slope test on the full unmatched pool of 754 sessions (not just the
  128 matched days) gives the same conclusion (diff=−0.0085, p=0.67).

This is a reasonably powered null (n=420 in the matched design, n=754 overall), not an absence
of testing. We state it plainly rather than looking for a sub-cut where it reaches significance.

## Step 3: does the answer track whichever of two tools was called *later*?

**This specific planned test does not work on the real data, and we say so rather than forcing
a result.** The task's suggested pair — `get_volatility_stats.ann_vol_20d_pct` vs.
`get_risk_budget.trailing_vol_20d_pct` — turns out to be the **same number** reported twice:
both are computed by the identical formula, `_sd(returns[-20:]) * sqrt(252)`, applied to the
same point-in-time price history (`src/finagent/harness/toolbox.py`, `get_volatility_stats` ~line 174-182 and
`get_risk_budget` ~line 207-212). In all **n=32** sessions where both tools were each called
exactly once, the two reported values were **exactly equal** (32/32 = 100%), confirmed both by
reading the source and by diffing the actual outputs. There is no second, independent number for
the agent's answer to be "closer to" — the test's premise does not hold for this pair.

We checked the rest of the registered toolset (`src/finagent/harness/toolbox.py`, 31 tools total) for any other
pair of genuinely different, comparable-scale volatility-relevant outputs from two separate
tools. The only other candidate, `get_event_risk.avg_abs_daily_move_pct`, co-occurs with
`get_volatility_stats` in only 11/1000 sessions (too few to test) and uses a different
definition/window (mean absolute daily return over the tool's full available history, vs. a
20-day realized standard deviation) — substituting it would introduce a scale confound of
exactly the kind the task asked us to avoid forcing. We report the tie finding (n=32, 100%
identical) as the honest result of this step instead of manufacturing a substitute comparison.

## Confound discussion (step 5)

The task's flagged threat: maybe the agent calls `get_volatility_stats` last *specifically when
it intends to rely on it most* — a different causal story than position itself causing weight.

- **Does the number's own magnitude predict whether it's called last?** No. Mean
  `ann_vol_20d_pct` is 37.4% (SE 1.47, n=187) when last vs. 35.6% (SE 0.82, n=567) when not —
  z=1.09, p=0.28. Extremeness of the number does not predict calling position.
- **Does the reliance ratio differ by position** (the direct form of the "intends to rely on it
  more" story)? No — see step 2's ratio check: 0.2235 vs 0.2227, not distinguishable.
- **A different, real confound we did find:** total tool calls per session (excluding
  `submit_decision`) is systematically *lower* when `get_volatility_stats` is called last — 7.05
  (SE 0.070) vs. 8.32 (SE 0.050), z=−14.6, p≈0. This is partly mechanical (calling it last caps
  how many more calls can follow in that session) but it also means `is_last` is confounded with
  "this was a shorter, more decisive session" in general, not purely with calling-position. We
  could not rule this out as an independent channel from position itself.

**Net assessment:** the specific intent-driven story the task flagged is not supported by the
two checks we could run directly. The session-length confound is real but does not change the
headline here, since the position effect we looked for was null on every cut anyway. It is worth
flagging explicitly because a *future* test that does find a positive position effect on this
corpus would need to separately control for session length before attributing it to position
per se.

## Examples (verbatim, see `examples` in data.json)

- **same_day_pair_A** (`HAL_2026-03-20`, `FULL_1` vs `FULL_2`): both see
  `ann_vol_20d_pct=30.1`. `FULL_1` (`is_last=True`) submits `expected_vol_pct=30` (ratio ≈1.00
  to the raw tool number); `FULL_2` (`is_last=False`, `simulate_order` called after the vol tool)
  submits `expected_vol_pct=5.5` (ratio ≈0.18, near the corpus-typical ~0.22). In isolation this
  looks like a "last ⇒ more weight" case.
- **same_day_pair_B_opposite_direction** (`STX_2026-06-17`, `FULL_1` vs `FULL_2`): the **opposite**
  pattern. `FULL_1` (`is_last=True`) submits `expected_vol_pct=8.5` against
  `ann_vol_20d_pct=65.7` (ratio 0.13); `FULL_2` (`is_last=False`, with `get_risk_budget` called
  after the vol tool) submits `expected_vol_pct=28` (ratio 0.43) and its reasoning explicitly
  cites the later-called risk-budget output ("Risk budget severely exceeded (99.8% vs 23%
  max)"). Having both directions represented in real data is exactly what the aggregate null
  predicts — a single example from either pair would have been misleading on its own.
- **part3_tie_illustration_1/2** (`ACN_2026-03-24` `FULL_3`, `AAPL_2026-03-19` `FULL_1`): the
  `get_volatility_stats` and `get_risk_budget` outputs are identical (42.9/42.9 and 20.9/20.9
  respectively) and the agent's own reasoning cites the shared number directly ("High volatility
  (42.9% ann)"), concretely showing why step 3's planned comparison has no second number to use.

## Stats methods (no scipy/statsmodels in the project `.venv`)

All in a from-scratch `src/finagent/mechanisms/proximity_stats.py`, numpy + stdlib only, each validated against known
reference values before use:
- **OLS**: textbook closed-form slope/intercept/SE from residual variance; cross-checked that
  `t_slope` equals the `t` derived from Pearson `r` (the standard algebraic identity).
- **Student-t p-values**: regularized incomplete beta function via a Lentz continued fraction
  (the same classical algorithm scipy's own `betainc`/`t.sf` are built on) — validated against
  known critical values (t=2.228, df=10 → p=0.0500; t=1.96, df=1000 → p=0.0503).
- **Pearson r 95% CI**: Fisher z-transform, SE=1/√(n−3).
- **Difference of two independent slopes**: Welch-style z-test, SE_diff=√(se1²+se2²).
- **Binomial test** (for step 3, unused since n_usable=0 — see above): exact two-sided test via
  `math.comb`, same definition as `scipy.stats.binomtest`/R `binom.test` — validated against a
  known value (k=15, n=20, p=.5 → p=0.04139, matches scipy to 5 decimals).
- **Wilson score interval** for the binomial proportion.

## Files

- `data.json` — full numeric results, sample accounting, confound checks, and the 5 verbatim
  example sessions (tool-call order, raw tool-result JSON, and the exact `submit_decision`
  reasoning string, copy-pasted from the real `.json.gz` files, no paraphrasing).
- `README.md` — this file.
