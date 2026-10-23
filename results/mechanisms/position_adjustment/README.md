# Position-adjustment vs rational sizing (mech4, task 3/4)

CPU only, no model calls, no GPU. Reads only already-saved trajectory/benchmark files.

## What this checks

Does the agent's day-to-day CHANGE in portfolio exposure (`target_exposure_pct`-style, here the
post-trade book `exposure` field) track what a simple Kelly-style rational sizing rule would
prescribe, given the rational expected return and volatility that day? And does that tracking
differ between quiet and eventful days, the way the project's established sigma-forecast result
does (over-react on quiet days, under-react on eventful days)?

## Corpus used (per the research workspace's `results/agentlevel_20261012/SYNTHESIS.md` and the already-audited file list in
its `results/agentlevel_20261012/code/daytoday/dtd_common.py`)

Only the **BASE** policy (Qwen3.5-9B tool agent, default prompt, thinking on, book + tool memory
carried 12-15 days) is used — never the `antibias` / `rational_prompt` / `sft` (`sftfix`, trained
memory-chain adapter) / `TWIN_RL_A` arms, which are a different experiment's treatment arms. The
six BASE run-files loaded:

| window | file | trajectories | agent-days |
|---|---|---|---|
| val_calm | `data/mechanisms/position_adjustment/base5d_val_calm.json` | 60 | 720 |
| val_stress | `data/mechanisms/position_adjustment/base5d_val_stress.json` | 60 | 720 |
| test_calm | `data/mechanisms/position_adjustment/base5d_test_calm.json` | 80 | 1200 |
| test_crash | `data/mechanisms/position_adjustment/base5d_test_crash.json` | 80 | 1200 |
| test_bear | `data/mechanisms/position_adjustment/base5d_test_bear.json` | 80 | 1200 |
| test_crash (replicate) | `data/mechanisms/position_adjustment/BASE_crash_R2.json` | 80 | 1200 |

Total: **440 trajectories, 6240 agent-days**. Each trajectory = one (ticker, twin-seed) pair, 2
twin trajectories per stock, 11-15 consecutive trading days per trajectory.

`exposure` in these files is the post-trade book exposure as a 0-1 fraction (the research workspace's `repro/tool_traj.py`);
it is multiplied by 100 throughout to read as a percent, matching the `target_exposure_pct` scale
the task describes.

## Step 0 — a confound found before running the regression: the rational benchmark does not cover
four of the five windows

`data/mechanisms/position_adjustment/events_all.parquet` and `nonevent_days.parquet` (the source of `m`,
`lsig`, `u`) only span **2025-10-02 to 2026-09-17**. Verified directly (not assumed): joining each
window's (ticker, day) pairs against both files gives

| window | trading dates | ticker-days | matched to rational (m/lsig) | hit rate |
|---|---|---|---|---|
| val_calm | 2023-10-02 start | 360 | 0 | 0% |
| val_stress | 2024-07-22 start | 360 | 0 | 0% |
| **test_calm** | **2026-01-05 start** | **600** | **377** | **62.8%** |
| test_crash | 2025-04-01 start | 600 | 0 | 0% |
| test_bear | 2022-05-02 start | 600 | 0 | 0% |
| test_crash replicate | 2025-04-01 start | 600 | 0 | 0% |

Overall hit rate across all 6240 BASE agent-days: **12.1% (754/6240)**, entirely concentrated in
`test_calm`. The 377 matched ticker-days split 264 from `events_all` (news-event days) + 113 from
`nonevent_days` (no-news days); checked that the two source files never both match the same
(ticker, day) (overlap = 0, so no double-counting / no arbitrary tie-break needed).

**Consequence, stated plainly rather than forced**: the regression, ratio and quiet/eventful split
below can only be computed on the **test_calm window** (40 held-out stocks, 2 twin trajectories
each, 15 days, Jan 2026) — 80 trajectories, 1200 agent-days, 1120 consecutive-day gaps, of which
**692 gaps have a rational join on BOTH day t and day t-1** and enter the regression. The
val_calm/val_stress/test_bear/test_crash windows contribute 0 usable rows for this particular
comparison; they are listed above for transparency but not used below. This is a corpus-coverage
limitation (the rational benchmark was built for a different date range than most of the agent
windows), not a result about the agent.

## Rational target rule

```
sigma_from_lsig(lsig) = exp(lsig)                     # rcf_20261011's lsig is already a 5-day log-sigma, verified: exp(lsig) == stored "sigma" column
rational_target_pct[t] = clip(k * m[t] / sigma_from_lsig(lsig[t])**2, 0, 100)
delta_rational[t] = rational_target[t] - rational_target[t-1]     # same k, same clip
```

`m`, `lsig`, `u` are joined from `events_all.parquet` (preferred) or `nonevent_days.parquet` (no
news that day) by `(ticker, day)`; `events_all.event_id` was checked to equal `TICKER_date` for
every row (assertion in the code, not just a sample).

**k**: chosen so that `std(k*m/sigma^2)` *before clipping*, over the 754 joined agent-days, equals
`std(agent exposure_pct)` over the same days — a documented scale choice for a side-by-side
comparison, not a claim about the "true" risk-aversion coefficient. `k_base = 283.6`. Out of 754
valid rows, clipping binds on 10 days (target would be < 0) and 30 days (target would be > 100);
the rest are interior.

**Robustness to k**: because `b` and the std-ratio depend linearly on k, they are also reported at
k/2 and 2k; the Spearman rank correlation of the deltas is reported as the k-invariant check (it is
not perfectly invariant only because clipping can re-order a handful of boundary points — see table
below).

| k | b (overall) | std ratio (overall) | Spearman rho (overall), n=692 |
|---|---|---|---|
| k/2 = 141.8 | +0.377 | 10.80 | -0.152 |
| k_base = 283.6 | +0.222 | 6.71 | -0.165 |
| 2k = 567.2 | +0.111 | 3.35 | -0.165 |

The rank correlation stays small and **negative** at every k — the headline conclusion (no positive
tracking) is not an artefact of the k choice.

## Headline numbers (test_calm window only, n as stated)

Mincer-Zarnowitz regression `delta_exposure = a + b * delta_rational`, OLS with three SE flavors
(heteroskedasticity-robust HC1; cluster-robust by ticker; cluster-robust by decision date — closed
form, no scipy/statsmodels needed since neither is installed in this venv):

| subset | n (gaps) | n tickers / n dates | b | SE(b) HC1 / ticker-cluster / date-cluster | a | std(delta_agent) | std(delta_rational) | ratio | Spearman rho |
|---|---|---|---|---|---|---|---|---|---|
| **overall** (all |u|) | 692 | 26 / 14 | **+0.222** | 0.241 / 0.290 / 0.279 | -1.23 | 14.93 | 2.23 | **6.71x** | **-0.165** |
| **quiet, |u|<1** | 532 | 26 / 14 | +0.318 | 0.262 / 0.304 / 0.276 | -1.24 | 14.85 | 2.28 | 6.51x | -0.167 |
| **eventful, |u|>=2** | 16 | 5 / 6 | +0.316 | 1.029 / 1.001 / 0.923 | +3.68 | 16.40 | 1.74 | 9.41x | 0.000 |
| mid, 1<=|u|<2 (not part of the established split, shown for context) | 144 | — | — | — | — | — | — | — | — |

(`m/lsig` matched on 754 of 1200 test_calm agent-days; `u`-bucket counts among those 754:
580 quiet, 154 mid, 20 eventful.)

### Reading this, stated as plainly as the numbers allow

- **Magnitude**: the agent's day-to-day exposure changes are **~6.7x more dispersed** than the
  rational rule's own day-to-day changes (std ratio), in the same direction as (but a much smaller
  number than) the project's already-established 71x finding for log-sigma revisions — confirming
  the qualitative over-churning story extends to exposure, but with its own, much smaller,
  magnitude. This is not interchangeable with the 71x number: it's a different quantity (exposure
  level change vs log-sigma change) on a different, much smaller, joined sample (n=692 gaps vs
  n=5715 in the sigma audit) and a different rational benchmark (Kelly m/sigma^2 here vs a
  price-feature regression there).
- **Calibration (b)**: b = +0.22 overall, with a cluster SE of ~0.29 — **not significantly different
  from 0** (let alone from 1). Unlike the sigma-forecast result, where the evidence-tracking part
  had roughly the right average size (slope 1.15) and the problem was almost pure noise plus a
  big-day shortfall, here the point estimate itself is small and statistically indistinguishable
  from "no linear relationship." The Spearman rank correlation is small and **negative** (-0.165,
  n=692), reinforcing that this is not merely a scale problem (b<1) but a near-absence of tracking.
- **Quiet vs eventful**: the planned asymmetry test (over-react quiet / under-react eventful,
  as found for sigma) **does not show up here, but the eventful subsample is too thin to
  conclude anything either way**: n=16 gaps, only 5 distinct tickers and 6 distinct decision dates,
  with a date-cluster SE on b of 0.92 (as large as b itself) and a 95%-ish range that easily spans
  0 to several multiples of b. The point estimates (b=0.32 quiet vs b=0.32 eventful, rho=-0.17 vs
  0.00) happen to look similar, but given n=16 this is **not evidence that the quiet/eventful split
  found for sigma revisions fails to replicate for exposure changes** — it is evidence that this
  particular corpus (one 15-day window, 40 stocks) does not contain enough big-surprise days to run
  that specific test with any power. Stated plainly: **this sub-test is inconclusive, not negative.**
- **Levels, as a diagnostic (not the task's headline ask)**: same-day agent exposure_pct vs rational
  target_pct, n=754: Pearson r = 0.003, Spearman rho = 0.24. So even the *levels* track only loosely
  (and non-linearly/rank-wise at best) — consistent with the day-to-day *changes* tracking poorly
  too; this isn't a case where levels agree but changes are just noisier.

## Worked examples

Three test_calm trajectories (distinct tickers, g=0 = first twin), chosen because each has several
quiet (|u|<1) AND at least one eventful (|u|>=2) gap, to show both regimes. Full tables for all
three are in `data.json/worked_examples`; the clearest case, ELV, in full:

**ELV (test_calm, trajectory g=0)** — day, agent exposure %, rational target %, agent Δ, rational Δ,
u (that day's standardized surprise):

| day | agent exposure % | rational target % | agent Δ | rational Δ | u |
|---|---|---|---|---|---|
| 2026-01-05 | 99.71 | 4.27 | — | — | 0.60 |
| 2026-01-06 | 20.23 | 3.10 | -79.48 | -1.17 | -0.09 |
| 2026-01-07 | 23.96 | 4.61 | +3.73 | +1.51 | 0.27 |
| 2026-01-08 | 24.36 | 2.60 | +0.40 | -2.01 | 0.34 |
| 2026-01-09 | 5.80 | 4.44 | -18.57 | +1.85 | 0.04 |
| 2026-01-12 | 8.74 | 7.33 | +2.94 | +2.89 | -0.64 |
| 2026-01-13 | 8.65 | 11.16 | -0.09 | +3.83 | -0.21 |
| 2026-01-14 | 48.91 | 9.01 | **+40.26** | -2.14 | -0.16 |
| 2026-01-15 | 36.67 | 7.95 | -12.23 | -1.06 | -0.86 |
| 2026-01-16 | 26.82 | 10.30 | -9.85 | +2.34 | -0.00 |
| 2026-01-20 | 36.04 | 10.52 | +9.22 | +0.22 | -3.17 |
| 2026-01-21 | 78.89 | 9.24 | **+42.85** | -1.28 | -2.09 |
| 2026-01-22 | 79.00 | 9.11 | +0.11 | -0.13 | -1.87 |
| 2026-01-23 | 39.47 | 11.39 | **-39.52** | +2.28 | -1.91 |
| 2026-01-26 | 43.83 | 7.99 | +4.36 | -3.40 | -2.50 |

On the quiet stretch 01-06 to 01-16 (|u| mostly < 1), the rational target barely moves
(|Δ| ≤ ~3.8 pct pts throughout) while the agent swings by up to 79 points in a single day
(01-06), including a +40-point jump on 01-14 that has no rational counterpart (rational Δ that
day is -2.14, opposite sign). On the three most eventful days in this trajectory (01-20/21/23,
|u| ≈ 1.9-3.2), the rational model barely revises its target either (Δ of +0.22, -1.28, +2.28), but
the agent now swings even harder (+9, +43, -40) — including an outright sign flip on 01-23 (agent
-39.5 vs rational +2.3). This single trajectory illustrates the headline numbers directly: large,
poorly-signed agent swings on both quiet and eventful days, with no visible asymmetry favoring
bigger moves specifically on the eventful days.

The other two worked examples (ALB, FERG — full tables in `data.json`) are smaller-exposure, more
range-bound trajectories where the agent's swings are a few points rather than tens of points, but
still generally larger than and uncorrelated in sign with the rational Δ on both quiet and
eventful days — i.e. the same qualitative pattern, just at lower absolute exposure.

## Sample-size summary (as required)

- BASE trajectories loaded (all 6 run-files): **440**, agent-days: **6240**.
- Usable window (test_calm, the only one with a rational join): **80 trajectories, 1200 agent-days**.
- Consecutive-day gaps in the usable window: **1120**; gaps with a rational join on both days:
  **692** (26 distinct tickers, 14 distinct decision dates) — this is the n behind every regression
  / ratio / rank-correlation number above.
- Eventful subset (|u|>=2): **n=16** gaps, 5 tickers, 6 dates — flagged above as underpowered.

## Reproduce

From the repository root:

```
finagent mech-position            # writes data.json
finagent mech-position --check    # rebuilds and compares with the shipped data.json
```
`src/finagent/mechanisms/position_adjustment.py` is a port of the exact script used to produce `data.json`
(the research workspace's `results/mech4_20261023/position_adjustment/build.py`, the same computation with only the paths changed);
it reproduces all 348 numeric values of the workspace `data.json` exactly, and `tests/test_mechanisms_position_adjustment.py`
checks that the rebuild equals the shipped file byte for byte. It has no
dependency beyond pandas/numpy/pyarrow — scipy and statsmodels are not installed in this venv, so
OLS and its robust/cluster SEs are closed-form: `beta = (X'X)^-1 X'y`, and SEs use the standard
White (HC1) / one-way-cluster sandwich `(X'X)^-1 (sum_g s_g s_g') (X'X)^-1` with a small-sample dof
correction.

Inputs: `data/mechanisms/position_adjustment/base5d_{val_calm,val_stress,test_calm,test_crash,test_bear}.json`,
`data/mechanisms/position_adjustment/BASE_crash_R2.json`,
`data/mechanisms/position_adjustment/{events_all,nonevent_days}.parquet` (byte-identical copies; source path in the research workspace and
sha256 of each in `data/mechanisms/position_adjustment/README.md`).
Output: `data.json` (this directory) — method/parameters, full coverage table, headline stats for
overall/quiet/eventful/mid, k-sensitivity table, level-correlation diagnostic, and the three worked
examples' full day-by-day tables.
