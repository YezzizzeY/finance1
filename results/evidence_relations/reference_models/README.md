# evidence_relations / reference_models

Three deterministic, non-LLM reference forecasters run over `data/evidence_relations/synthetic/test.jsonl`
(38,400 rows; read-only, never modified), to give a concrete, quantified picture of what three qualitatively different ways of
combining two noisy signals look like as *behaviour*, before any real model is tested on the same benchmark.
Code: `src/finagent/evidence_relations/reference_models.py` (all three forecasters, orchestration and the CLI);
ported from `1_overreaction/repro/evidence_relations/reference_models/run_models.py` and its three
per-model files.

## The three archetypes

| name | rule | reads tau/c? |
|---|---|---|
| `bayes_optimal` | exact closed-form MMSE combination (DESIGN.md S3), via `evidence_relations.bayes` | yes (and `stale_round`) |
| `counting_naive` | `theta_hat = (s1+s2)/2` -- averages, not sums (see `predict_counting_naive`'s docstring for why sum would be a different, strictly worse failure mode) | no |
| `salience_follower` | `theta_hat = s1 if |s1|>=|s2| else s2` -- follows whichever signal's number is larger in magnitude | no |

All three predict the full one-step change `delta1_hat = (rho-1)*x_t + theta_hat`, the same AR-term
decomposition the dataset's own `bayes_optimal_delta1` column uses, so every MAE number below isolates *only*
how the three archetypes combine `s1`/`s2` -- the common `(rho-1)*x_t` term cancels identically out of every
model's error against the true `delta1 = x_next - x_t`, so `error = theta_hat - true_eps_next` exactly, for all
three models. Every round forecasts a fresh, independent `eps_{t+1}`, so there is no earlier forecast of the
same target to regress against; comparing `delta1_hat` to the true `delta1` directly is the right-shaped
comparison, and is what `results.csv` reports.

## Cross-check: does `predict_bayes_optimal` reproduce the dataset's own ground truth?

Yes, to within floating-point rounding-tie noise (see `build_checks.json`):

- Raw (pre-rounding) difference from the stored `bayes_optimal_delta1` column: **0.005 max, 0.0025 mean**,
  across all 38,400 rows -- exactly DESIGN.md's own stated 2-decimal rounding-error bound, i.e. the formula is
  identical.
- After rounding both to 2 decimals: **38,332 / 38,400 (99.82%) match exactly**; the remaining 68 rows differ
  by exactly ±0.01, every one sitting within 6e-12 of an exact `x.xx5` rounding boundary -- a benign tie-break
  artifact (round-half-to-even can pick either neighbour depending on the last float64 bit), not a formula
  discrepancy, and it only occurs in the `noisy` (tau=40) conditions.

## Headline result: MAE vs c (base variant, pooled over tau and rho)

| c | n | MAE bayes_optimal | MAE counting_naive | MAE salience_follower |
|---|---|---|---|---|
| 0.00 | 7,680 | 9.1542 | 14.0657 | 25.6701 |
| 0.50 | 7,680 | 10.2068 | 17.2807 | 25.0316 |
| 0.95 | 7,680 | 10.6099 | 19.6257 | 21.8094 |
| **change, 0→0.95** | | **+15.9%** | **+39.5%** | **−15.0%** |

The three predictions, checked against these numbers:

1. **"bayes_optimal should be flat-ish and lowest"** -- **lowest: confirmed** at every `c`. **Flat-ish:
   confirmed with a correction.** It is not flat -- its own MAE rises ~16% from `c=0` to `c=0.95` -- but this
   is *not* a sign of suboptimality: `Var[theta|S1,S2]` itself genuinely increases with `c` (DESIGN.md S3.3),
   because a more redundant second signal carries less true new information, so the best *any* estimator can
   do gets worse too. `bayes_optimal`'s rise (+15.9%) is far smaller than `counting_naive`'s (+39.5%), so
   "flat-ish relative to the alternatives, not flat in absolute terms" is the accurate statement.
2. **"counting_naive should get worse as c increases because it double-counts redundant info"** -- **confirmed
   cleanly**: monotonically increasing, +39.5% from `c=0` to `c=0.95`, the single largest relative degradation
   of the three archetypes. Mechanism, exactly as predicted: averaging two signals whose noise terms become
   more correlated does not reduce noise variance the way averaging two *independent* noisy copies does
   (`Var(error) = tau^2(1+c)/2` -- `counting_naive` uses the *same* fixed 50/50 weights `bayes_optimal` uses
   only at `tau1=tau2`, applied at every `c`, including the ones where the optimal choice is to shrink the
   pair's total weight, which it never does).
3. **"salience_follower should be indifferent to c since it never uses both signals"** -- **corrected, not
   confirmed.** It is the *most* c-sensitive archetype in the table: its MAE *falls* 15.0% from `c=0` to
   `c=0.95` (the opposite direction from "indifferent"), and this holds within each tau setting separately
   (informative: 9.05→8.18; noisy: 42.29→35.44), so it is not a pooling artifact. Mechanism:
   "indifferent to c" would be true if c only affected *how the two signals are combined* -- but
   `salience_follower`'s *selection* step (which signal is bigger) also depends on `c`, because at high `c` the
   two signals' noise terms are nearly identical (`u1≈u2` as `c→1`), so whichever one gets picked is
   a similarly-good estimate of `theta`; at `c=0` the two noise draws are independent, so "biggest in
   magnitude" more often means "got an unlucky large *noise* draw on top of theta", which is exactly the case
   this archetype handles worst. Redundancy, perversely, makes a signal-blind, magnitude-chasing rule *less*
   bad here, not neutral to it.

## Stale-signal variant: does treating a repeated signal as fresh cost more than dropping it?

| tau_setting | stale_round | n | MAE bayes_optimal | MAE counting_naive | MAE salience_follower |
|---|---|---|---|---|---|
| informative (tau=10) | fresh | 2,746 | 5.2395 | 5.6085 | 9.0692 |
| informative (tau=10) | **stale** | 1,094 | 7.0899 | **12.5983** | **17.5530** |
| noisy (tau=40) | fresh | 2,689 | 13.0952 | 22.9932 | 42.4464 |
| noisy (tau=40) | **stale** | 1,151 | 14.0172 | **25.8897** | **48.0788** |

`bayes_optimal`'s error on stale rounds rises only because it correctly falls back to a *single*-signal
posterior (more uncertainty, not more error from bad information): +35% (informative) / +7% (noisy).
`counting_naive` and `salience_follower` both get hit far harder (+125% and +94% respectively, informative;
+13% and +13%, noisy) because neither archetype has any mechanism to notice that `s2` is a verbatim repeat and
keeps treating it as fresh evidence worth half the vote (`counting_naive`) or a candidate for "biggest number"
(`salience_follower`) -- exactly the failure mode `stale_round` is designed to expose.

## Contradiction variant: precision-weighting under forced disagreement

| regime (tau1, tau2) | n | MAE bayes_optimal | MAE counting_naive | MAE salience_follower |
|---|---|---|---|---|
| A informative, B noisy (10, 40) | 3,840 | **7.4447** | 23.8610 | 43.2790 |
| A noisy, B informative (40, 10) | 3,840 | **22.3351** | **17.6683** | 35.6829 |
| pooled | 7,680 | 14.8899 | 20.7647 | 39.4809 |

Pooled, `bayes_optimal` is still lowest, as in `base`/`stale`. **But within the "A noisy, B informative" regime
alone, `bayes_optimal` (22.3351) is *worse* than `counting_naive` (17.6683)** -- a genuine reversal. Cause:
DESIGN.md's forced-disagreement rule always flips **Signal B**'s sign when needed, never Signal A's, so Signal
A is always the row's "honest", never-corrupted signal, while Signal B is sometimes adversarially flipped away
from the truth. `bayes_optimal` (correctly, per the stated resolution rule) puts most of its weight on
whichever signal is *stated* as more precise, blind to which one got flipped. When the precise signal happens
to be A (never flipped), that weighting pays off (MAE 7.44, the best number in the whole study). When the
precise signal happens to be B (sometimes flipped), the same weighting rule now puts most of its trust in the
signal most likely to have been deliberately corrupted -- and pays for it (MAE 22.34). `bayes_optimal`'s
*bias* in this regime is only +0.7182 (tiny relative to its 22.34 MAE): a **variance** story (big swings both
ways from the adversarial flips), not a directional one.

## rho-invariance check (base variant, pooled over tau, by c x rho)

| c | rho=0.0 | rho=0.4 | rho=0.8 | spread |
|---|---|---|---|---|
| 0.00 | 9.0974 | 9.2816 | 9.0836 | 0.20 (2.2%) |
| 0.50 | 10.0576 | 10.2138 | 10.3491 | 0.29 (2.9%) |
| 0.95 | 10.5632 | 10.5051 | 10.7615 | 0.26 (2.5%) |

Confirms DESIGN.md S1.1's claim: `bayes_optimal`'s MAE depends on `(c, tau)`, not on `rho` (the within-`c`
spread across `rho` is an order of magnitude smaller than the across-`c` differences in the headline table,
with no consistent direction -- consistent with realization-sampling noise, not a systematic rho effect). Full
per-(c,rho) table for all three models is in `results.csv` (`level == "rho_check"`).

## All numbers

`results.csv` -- one row per (variant, c, tau1, tau2, tau_setting, stale_round) condition (`level ==
"condition"`), plus three pooled views used above (`level in {"base_c_pooled", "rho_check",
"variant_pooled"}`). Columns: `n`, and for each of the three models, `mae_*` (mean absolute error of
`delta1_hat` vs true `delta1`), `bias_*` (mean signed error), `rmse_*`. All float columns rounded to 4
decimals. `build_checks.json` has the cross-check numbers above plus `salience_tie_count` (19/38,400 rows where
`|s1|==|s2|` exactly at the stored 2-decimal precision -- `predict_salience_follower`'s tie-break rule decides
those 19, negligibly).

## Source-vs-port comparison

Built from this port's own regenerated `data/evidence_relations/synthetic/test.jsonl.xz` (identical, byte for byte, to the source
project's `test.jsonl` -- see `data/evidence_relations/synthetic/README.md` "Verification"), so every number above is identical to
`1_overreaction`'s `data/datasets/evidence_relations/reference_models/README.md`:

| check | source | this port |
|---|---|---|
| `n_rows_total` | 38,400 | 38,400 |
| `bayes_optimal_cross_check.n_exact_match_after_round2` | 38,332 | 38,332 |
| `bayes_optimal_cross_check.max_abs_diff_before_round2` | 0.005 | 0.005 |
| `salience_tie_count` | 19 | 19 |
| MAE `bayes_optimal` at c=0/0.5/0.95 | 9.1542 / 10.2068 / 10.6099 | 9.1542 / 10.2068 / 10.6099 |
| MAE `counting_naive` at c=0/0.5/0.95 | 14.0657 / 17.2807 / 19.6257 | 14.0657 / 17.2807 / 19.6257 |
| MAE `salience_follower` at c=0/0.5/0.95 | 25.6701 / 25.0316 / 21.8094 | 25.6701 / 25.0316 / 21.8094 |
| `counting_naive` change 0→0.95 | +39.5% | +39.5% |
| `salience_follower` change 0→0.95 | −15.0% | −15.0% |

The counter-intuitive `salience_follower` finding (MAE *falls* as redundancy rises, the opposite of
"indifferent to c") holds identically in this port's regenerated numbers, confirming it is a property of the
archetype and the data-generating process, not an artifact of one run.

## Determinism

Every forecaster is a pure, deterministic function of already-fixed columns of `test.jsonl` (itself read-only,
untouched) -- there is no randomness anywhere in this pipeline, so there is no seed to fix. "Reproducible" here
means byte-identical output on every rerun, checked directly: `finagent evidence-reference-models` was run
twice and the two `results.csv` / `build_checks.json` pairs were diffed (`cmp -s`): empty. See
`MANIFEST.sha256` in this directory.

## Regenerate

```sh
finagent evidence-reference-models                 # reads data/evidence_relations/synthetic/test.jsonl.xz (the shipped archive)
finagent evidence-reference-models --regenerate     # reads a fresh regeneration of the generator instead
```
Writes `results.csv`, `build_checks.json` and `MANIFEST.sha256` in this directory. Reads only from
`data/evidence_relations/synthetic/`; writes only in this directory; never calls any model, uses no GPU.
