# evidence_relations: design

`data/evidence_relations/` (the four inputs/benchmark pieces) and `results/evidence_relations/` (the
`reference_models/` analysis output) ask a different question from the five-model pilot above: not "does
the model react too much or too little to one piece of information", but **"when the model sees more than one
piece of evidence, does it combine them correctly — discounting redundant evidence, weighting by reliability,
ignoring stale repeats — or does it just count pieces and follow whichever number looks biggest?"** It is a
second, independent extension of this repository: CPU only, no GPU, no model calls, not part of `finagent
verify`'s L0-L3 and not read by the pilot itself. Code: `src/finagent/evidence_relations/`. Every number on this
page comes from code (closed-form math or an exhaustive walk of real data), never from a model's output or from
assertion, and every generator was run twice to prove byte-identical, deterministic output (each subfolder's own
README.md has the diff).

Ported from the already-verified, already-run `1_overreaction/repro/evidence_relations` build: same
math, same seeds, independently re-derived and re-checked here, not copied blind. Four pieces:

| | folder | rows | self-contained? |
|---|---|---|---|
| synthetic benchmark | [`data/evidence_relations/synthetic/`](../data/evidence_relations/synthetic/README.md) | 153,600 | yes — own RNG, no dependency on `data/` |
| reference models | [`results/evidence_relations/reference_models/`](../results/evidence_relations/reference_models/README.md) | 38,400 scored | reads `synthetic/test.jsonl` only |
| real-day perturbations | [`data/evidence_relations/real_day_perturbations/`](../data/evidence_relations/real_day_perturbations/README.md) | 1,742 | built on `data/pit_cache` (96 tickers) and `day_pool/` |
| tool-redundancy matrix | [`data/evidence_relations/tool_redundancy/`](../data/evidence_relations/tool_redundancy/README.md) | 23,777 (ticker, day) | built on `data/pit_cache` (96 tickers) |

## 1. The synthetic two-signal Bayesian benchmark

### 1.1 Generative model

Same AR(1) process as the sibling `1_overreaction` project's own replication: `x_t = rho*x_{t-1} +
eps_t`, `eps_t ~ i.i.d. N(0, sigma^2)`, `sigma = 20`, `rho in {0.0, 0.4, 0.8}` (no persistence / weak / strong but
stationary), stationary start (`x_0 ~ N(0, sigma^2/(1-rho^2))`). A model is shown 40 lagged `[value, change]`
points and asked to forecast the next one-step change, `delta1 = x_next - x_t`.

What this benchmark adds on top: at every round, alongside the usual history, the model is also given two
noisy signals about the upcoming change, Signal A and Signal B, each stated with its own noise level `tau`. The
signals' *true* correlation with each other, `c`, is known to the generator but never told to the model — exactly
like `rho` and `sigma` are known to the generator but never stated in the prompt. Because the signal-generating
process is fully specified, the Bayes-optimal use of the two signals is closed form and can be checked exactly.

### 1.2 Closed-form Bayes-optimal combination

Let `theta = eps_{t+1}` (independent of the history and of `rho` by construction, so its prior is unconditional:
`theta ~ N(0, sigma^2)`). Two signals `S1 = theta + u1`, `S2 = theta + u2`, `u1 ~ N(0,tau1^2)`, `u2 ~
N(0,tau2^2)`, `corr(u1,u2) = c`. Standard Gaussian conditioning on `Sigma = Cov([S1,S2])` gives, in general
(`tau1` may differ from `tau2`; `det = (sigma^2+tau1^2)(sigma^2+tau2^2) - (sigma^2+c*tau1*tau2)^2`):

```
w1 = sigma^2 * tau2 * (tau2 - c*tau1) / det
w2 = sigma^2 * tau1 * (tau1 - c*tau2) / det
E[theta|S1,S2]   = w1*S1 + w2*S2
Var[theta|S1,S2] = sigma^2 - sigma^4*(tau1^2+tau2^2-2*c*tau1*tau2)/det
```

In the symmetric case `tau1=tau2=tau` (the `base` and `stale` variants), the two weights collapse to exactly
50/50 for every `c` — redundancy changes how much *total* weight the pair gets relative to the history-only
forecast, never how that weight splits between the two signals:

```
E[theta|S1,S2]   = sigma^2*(S1+S2) / (2*sigma^2 + tau^2*(1+c))
Var[theta|S1,S2] = sigma^2*tau^2*(1+c) / (2*sigma^2 + tau^2*(1+c))
w1 = w2          = sigma^2 / (2*sigma^2 + tau^2*(1+c))
```

A signal that carries zero correlation with the current round's `theta` — not merely `c=0`, genuinely dropped —
gets exactly zero weight, the standard one-signal posterior:

```
E[theta|S1]   = sigma^2*S1 / (sigma^2+tau1^2)
Var[theta|S1] = sigma^2*tau1^2 / (sigma^2+tau1^2)
```

Then `bayes_optimal_delta1 = (rho-1)*x_t + E[theta|...]`, `bayes_optimal_posterior_var = Var[theta|...]`. Full
derivation, the asymmetric (`tau1 != tau2`) contradiction-variant solution, every build-time self-check and the
exact seed tree: [`data/evidence_relations/synthetic/DESIGN.md`](../data/evidence_relations/synthetic/DESIGN.md) (adapted
in this port from the source project's own `DESIGN.md`, re-read and re-checked against this port's code, not
copied verbatim).

**Independent re-derivation.** Rather than trust a direct re-run of the ported `bayes.py`, this port separately
rebuilt `Sigma` and `Cov(theta,S)` as NumPy arrays for a sample of rows across all three variants and solved
`w = Cov(theta,S) @ Sigma^{-1}` with `numpy.linalg.solve` — a different code path from the closed-form algebra
above. Maximum absolute difference from the shipped `weight_s1`/`weight_s2`/`bayes_optimal_posterior_var`:
`< 1e-9` (float64 precision noise), on every sampled row.

### 1.3 Three variants, 30 conditions, 153,600 rows

| variant | what it tests | conditions | rows |
|---|---|---|---|
| `base` | redundancy discount: `c` in `{0.0, 0.5, 0.95}` x `tau` in `{10, 40}` x 3 `rho` | 18 | 92,160 |
| `stale` | zero-weighting a verbatim-repeated signal | 6 | 30,720 |
| `contradiction` | precision-weighted resolution when the two signals are forced to disagree in sign | 6 | 30,720 |

Train/val/test (76,800 / 38,400 / 38,400) use disjoint AR(1) realizations: 3,840 unique out of 3,840 generated,
zero collisions. Every row also carries a `position_swapped` prompt variant with identical statistical content
(Signal A and B's values and noise levels unchanged; only their order and wording differ) for a presentation
invariance check — `position_swap_information_equivalent: true` over all 153,600 rows.

### 1.4 Port verification

This port's regenerated `{train,val,test}.jsonl` are **byte-identical** (sha256 match, not just matching
statistics) to the source project's own shipped files, and `build_summary.json`'s decompressed-content check
confirms the shipped `.xz` archives decompress to the same bytes the generator produces fresh. Counts: 30
conditions, 153,600 total rows, `n_stale_rounds` 8,916, `n_contradiction_rounds` 30,720 with a forced-flip rate
of 0.6286 — all identical to the source. Full table:
[`data/evidence_relations/synthetic/README.md`](../data/evidence_relations/synthetic/README.md) "Verification".

## 2. Reference models: three non-LLM archetypes, as a baseline

Before any real model is tested, three deterministic, non-LLM forecasters were run on `synthetic/test.jsonl`
(38,400 rows) to show what three qualitatively different ways of combining two noisy signals look like as
*behaviour*: `bayes_optimal` (the exact closed-form combination above), `counting_naive` (`theta_hat =
(s1+s2)/2`, fixed 50/50 regardless of redundancy), and `salience_follower` (`theta_hat = s1 if |s1|>=|s2| else
s2`, follows whichever number is larger in magnitude).

| c | n | MAE bayes_optimal | MAE counting_naive | MAE salience_follower |
|---|---|---|---|---|
| 0.00 | 7,680 | 9.1542 | 14.0657 | 25.6701 |
| 0.50 | 7,680 | 10.2068 | 17.2807 | 25.0316 |
| 0.95 | 7,680 | 10.6099 | 19.6257 | 21.8094 |
| **change, 0→0.95** | | **+15.9%** | **+39.5%** | **−15.0%** |

`bayes_optimal` stays lowest at every redundancy level, and rises only ~16% from `c=0` to `c=0.95` — a rise
driven by `Var[theta|S1,S2]` itself genuinely increasing with `c` (a more redundant second signal carries less
true new information), not by suboptimality. `counting_naive` gets monotonically worse (+39.5%) because it keeps
giving a fixed 50/50 weight to two signals whose noise terms become more correlated, instead of shrinking the
pair's total weight the way `bayes_optimal` does. `salience_follower` is, counter to the naive prediction, the
*most* c-sensitive archetype — its error *falls* 15.0% as redundancy rises, because at high `c` the two signals'
noise draws converge (`u1≈u2`), so picking "whichever is bigger" increasingly means picking a similarly-good
estimate rather than an unlucky large noise draw. On the `stale` variant, both naive archetypes treat a
verbatim-repeated signal as fresh evidence and pay for it (+94% to +125% MAE, informative tau); `bayes_optimal`
only loses what information is genuinely missing (+35%). On the `contradiction` variant there is one genuine,
documented reversal: within the "A noisy, B informative" regime alone, `bayes_optimal` (22.3351) is *worse* than
`counting_naive` (17.6683), because the forced-disagreement rule always flips Signal B's sign, never Signal A's,
so trusting whichever signal is *stated* as more precise sometimes means trusting the one more likely to have
been adversarially corrupted. Full tables, the rho-invariance check and the cross-check against the dataset's own
`bayes_optimal_delta1` column: [`results/evidence_relations/reference_models/README.md`](../results/evidence_relations/reference_models/README.md).

## 3. Real-day perturbations: four families, real headlines and real numbers

Built on the day pool (`data/evidence_relations/day_pool/`, the TRAIN/TEST_CORE/TEST_FULL split of 197 days over all
96 `data/pit_cache` tickers) and real point-in-time price/news history — not synthetic text. Each family states
its own ground truth at its own precision: **exact** (a closed-form or definitional claim that must hold with
no exceptions), **ordinal** (a documented hypothesis about which of two prompts should move a forecast more, not
by how much), or **approximate** (a derivation that holds up to one stated approximation).

| family | rows | ground truth | precision |
|---|---|---|---|
| `redundancy_copies` | 788 | re-expressing one real reading 0/1/2/4 times should not move the forecast | exact |
| `already_priced_in` | 394 | a headline from an earlier day should move the forecast *more* than the same headline already reflected in today's price | ordinal (documented hypothesis) |
| `stale_news` | 394 | a 10-20-day-old headline redisplayed as new should move the forecast *less* than a genuinely fresh one | approximate (one derived approximation) |
| `position_swap_conflict` | 166 (of 280 constructible; 114 skipped, no contradiction found — logged with reasons) | order of two genuinely conflicting signals alone should not flip the forecast | exact (tier 1) / approximate (tier 2) |

**The `already_priced_in` fix.** The first build of this family let the "different day" headline come from *any*
other day, including after day t; in 52 of 197 rows (26.4%) this spliced a real future event — up to 153 days
later — into the prompt, leaking information rather than showing an unrelated past headline. Fixed on 2026-10-20
to draw only from days strictly before t. This port reproduces that fixed version, not the leaking one, and
independently re-confirms it: a `verify_no_future_leak` assertion runs on every build, and this port's own build
found 0 of 197 rows with a post-day-t spliced headline. The other three families were unaffected by the bug.

Every row carries a full, self-contained harness prompt (`finagent.harness.prompts.harness_prompt`'s own
rendering) and its sha256, so a claim can be checked against the exact text a model would see. Full per-family
derivations, the days that could not be constructed and why:
[`data/evidence_relations/real_day_perturbations/README.md`](../data/evidence_relations/real_day_perturbations/README.md)
and each family's own subfolder README.

## 4. Tool-redundancy matrix: measured, not asserted

How correlated are the harness's own tools' outputs with each other, computed by actually calling
`finagent.harness.toolbox`'s tool functions — the same functions the pilot's agents call — walked day by day
over real point-in-time price and news history, for all 96 `data/pit_cache` tickers (not just the pilot's six).
No model calls, no hand-waving about which tools "must" overlap.

**Scope.** `finagent.harness.toolbox.TOOLS` lists 31 non-submit tools; 8 are excluded here because their numeric
output depends on account/session state (`get_calibration_ledger`, `get_lessons`, `get_portfolio`,
`get_trade_history`, `memory_read`, `memory_search`, `memory_write`, `simulate_order`) rather than on price or
news. The remaining 23 tools were each called with one fixed argument dict and a fresh account state, for every
(ticker, day): 23,777 (ticker, day) rows, 98 raw numeric (tool, field) columns, 69 kept after dropping 29
all-null/constant columns, 2,346 pairwise correlations (2,064 cross-tool), collapsing to 136 unique tool x tool
pairs.

**Result.** 0 of 136 tool pairs are fully redundant (every field pair |r|>=0.9); 42 are fully independent (every
field pair |r|<0.2 both ways) — the candidate set for "genuinely independent signal" examples elsewhere in this
project; the remaining 94 are mixed. The largest near-duplicate cluster (connected components at |Pearson
r|>=0.9) has 22 fields — all variants of "today's closing price" and its short averages (daily/weekly/monthly
candle opens/highs/lows/closes, Bollinger bands, trend-signal EMAs, price-stats close and 52-week high,
support/resistance close) — and spans **7** distinct tools (`get_daily_candles`, `get_mean_reversion_signal`,
`get_monthly_candles`, `get_price_stats`, `get_support_resistance`, `get_trend_signal`, `get_weekly_candles`),
confirmed by counting the cluster's own tool-name prefixes in `clusters.csv`.

**A correction made during this port, stated plainly rather than carried forward.** An earlier description of
this cluster (including the request that led to this document) said it spans "~10 tools" with 22 fields. The 22
fields figure is right; the ~10-tools figure is not — it traces back to this project's own earlier top-level
`data/datasets/evidence_relations/README.md` prose, which was imprecise. This port checked the actual cluster
membership (`clusters.csv`) rather than carry the imprecise figure forward: counting distinct tool-name prefixes
in the 22-field cluster gives 7, not 10, and that is what `data/evidence_relations/tool_redundancy/README.md` reports.
No data value was changed to make the number come out to 10.

**Pooled independence is not the same as per-ticker independence.** The 42-pair "fully independent" verdict is
computed pooling all 96 tickers together. Checked directly against this port's own `per_ticker_matrix.parquet`:
restricting to the field pairs behind those 42 tool pairs, per-ticker Pearson correlation ranges from about
**−0.97 to +0.95** across individual tickers — i.e. for at least one stock, a pooled-independent tool pair can
still be strongly correlated (or anti-correlated). Anyone using one of these 42 pairs as a worked "independent
information" example for a *specific* ticker should check `per_ticker_matrix.parquet` for that ticker first,
not rely on the pooled verdict alone.

Full tables, the numeric-field convention (which JSON fields count as a column, and why), and the top-20
correlated pairs: [`data/evidence_relations/tool_redundancy/README.md`](../data/evidence_relations/tool_redundancy/README.md).

## What this is not yet

A benchmark and a set of measured/closed-form baselines, not a trained method and not a real-model result. None
of the five models in the pilot above (or any other model) has been run against any piece of this
evidence-relations extension yet — the synthetic benchmark's prompts, the real-day perturbations' prompts, and the
tool-redundancy matrix's independent-pair candidates are all built and checked, ready for that as the next step.

## Reproduce

```sh
cd finance1
finagent evidence-pool                        # day pool -> data/evidence_relations/day_pool/
finagent evidence-real-day                     # four real_day_perturbations families
finagent evidence-tools --workers 32           # tool-redundancy matrix (the slow one, ~2 min on 48+ cores)
finagent evidence-synthetic                    # synthetic two-signal benchmark
finagent evidence-synthetic --check            # regenerate in memory, compare with the shipped .xz
finagent evidence-reference-models             # bayes_optimal / counting_naive / salience_follower
```

or `make evidence-pool evidence-real-day evidence-tools evidence-synthetic evidence-reference-models`. Every
generator is deterministic and CPU only; each subfolder's own README.md records the two-run diff that proves it.
