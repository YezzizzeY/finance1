# Design decisions: `evidence_relations/synthetic` -- a two-signal Bayesian extension of the AR(1) replication

Ported, unchanged math and unchanged seeds, from `1_overreaction/repro/evidence_relations/{generate,
bayes,prompts,build}.py` and `data/datasets/evidence_relations/synthetic/DESIGN.md` of the sibling project
`1_overreaction`. This benchmark is **not** part of that project's own Gao-paper replication and
claims no textual support from any paper; every design choice below is **this benchmark's own** or an
**extension** of `ar1_forecasting`'s AR(1) process, carried over for this port on the same terms as the source.
Code here: `src/finagent/evidence_relations/{synthetic,bayes}.py`.

## S0. What this benchmark adds

A model is asked to forecast the one-step change of a zero-mean AR(1) series from 40 lagged levels, same as
`ar1_forecasting`, plus a **second evidence channel**: two noisy signals about the upcoming change, whose
redundancy with each other is a controlled, known parameter `c`. Because the signal-generating process is
fully specified (Gaussian, known variances, known correlation), the Bayes-optimal use of the two signals is
closed form (S3) and can be checked exactly against the dataset's own `bayes_optimal_delta1` /
`bayes_optimal_posterior_var` fields.

## S1. Base process (reused from `ar1_forecasting`, not re-derived)

`x_t = rho*x_{t-1} + eps_t`, `eps_t ~ i.i.d. N(0, sigma^2)`, `sigma = 20`, long-run mean 0. This process and its
exact seeding convention are reused unchanged:

- **Stationary start**: for every `rho` used here (all `< 1`), `x_0 ~ N(0, sigma^2/(1-rho^2))`, so every shown
  window is stationary from its first point.
- **Precision discipline**: the recursion runs in float64; every value that reaches the prompt, and everything
  computed from it (signals, Bayes-optimal targets), uses the **rounded, shown** 2-decimal values, not the
  hidden full-precision ones. Rounding error is at most 0.005.
- **Timeline**: 40 shown history points, then up to 40 rounds. Round `r` (1..40) has last observation `x_t` at
  series index `t = 38 + r`. Only **one** step ahead is ever forecast (`Delta_1`, never `Delta_2`), so a
  realization needs series indices `0..79` (length 80).

**S1.1. Subset of rho.** `rho in {0.0, 0.4, 0.8}`: no persistence, weak persistence, strong-but-stationary
persistence. This spans the three qualitatively different regimes without needing every value `ar1_forecasting`
itself sweeps, since the new axes here (`c`, `tau`, 3 variants) already multiply the condition count 5x relative
to a single-rho design, and `rho` enters `bayes_optimal_delta1` purely through the additive, unconditional
`(rho-1)*x_t` term (S7 confirms the two-signal posterior does not otherwise depend on it).

## S2. Seeding (same convention as the rest of finagent's seeded generators, own seed tree)

One independent NumPy PCG64 stream per **(purpose, variant-group, split, rho, c, tau)** combination:

```
SeedSequence(BASE_SEED, spawn_key=(purpose_idx, group_idx, split_idx, rho_idx, c_idx, tau_idx))
```

- `BASE_SEED = 20261020` (the source project's build date; kept unchanged by the port so a regeneration here is
  checkable, row for row, against the already-built `data/datasets/evidence_relations/synthetic/` of the sibling
  project -- confirmed in S9 below). This is a **separate** `SeedSequence` call from anything else in this
  repository or in `1_overreaction`: `SeedSequence` derives cryptographically independent children from
  `(entropy, spawn_key)`, so no accidental collision with another module's stream is possible.
- `purpose_idx`: 0 = AR(1) series simulation, 1 = the two signals' correlated noise `(u1,u2)`, 2 = the
  stale-round Bernoulli flags (stale variant only).
- `group_idx`: 0 = base, 1 = stale, 2 = contradiction (S5).
- `split_idx`: train=0, val=1, test=2.
- `rho_idx`: 0,1,2 for rho in (0.0, 0.4, 0.8). `c_idx`: 0,1,2 for c in (0.0, 0.5, 0.95) (base variant only; fixed
  to index 0 / value 0.0 for stale and contradiction). `tau_idx`: 0,1 for the two tau settings
  (informative/noisy for base and stale; the two asymmetric-precision regimes for contradiction, S5.3).
- **Every (variant, split, rho, c, tau) condition draws its own independent AR(1) realizations** -- not common
  shocks reused across conditions, keeping the 30 conditions statistically independent of each other.
- **Proof of no overlap** (train/val/test, and across all 30 conditions): the build hashes every simulated
  realization (`row.tobytes()` on the full-precision series) into one global set and asserts zero collisions.
  Result on this port's build: **3,840 unique realizations out of 3,840 generated (0 duplicates)** -- the exact
  product of 30 conditions x (64+32+32) realizations per condition, identical to the source build (S9).

## S3. Bayes-optimal combination of two noisy signals (full derivation)

### S3.1 Setup

Let `theta = eps_{t+1}`, the AR(1) innovation for the round being forecast. Because `eps_{t+1}` is independent
of the history `x_{t-39..t}` and of rho by construction (it is the *next* innovation, not yet realized), its
prior is the **unconditional** one: `theta ~ N(0, sigma^2)`, regardless of rho or x_t.

Two noisy signals: `S1 = theta + u1`, `S2 = theta + u2`, with `u1 ~ N(0,tau1^2)`, `u2 ~ N(0,tau2^2)`,
`corr(u1,u2) = c`, and `theta` independent of `(u1,u2)`. (In the prompt, `S1` is always called "Signal A" and
`S2` is always called "Signal B".)

### S3.2 General solution (tau1 may differ from tau2)

`Cov(theta,[S1,S2]) = [sigma^2, sigma^2]` and

```
Sigma = Cov([S1,S2]) = [[sigma^2+tau1^2,            sigma^2+c*tau1*tau2],
                        [sigma^2+c*tau1*tau2,        sigma^2+tau2^2    ]]
```

`E[theta|S] = Cov(theta,S) Sigma^{-1} S`, `Var[theta|S] = Var(theta) - Cov(theta,S) Sigma^{-1} Cov(S,theta)`.
Inverting the 2x2 `Sigma` (`det = (sigma^2+tau1^2)(sigma^2+tau2^2) - (sigma^2+c*tau1*tau2)^2`):

```
w1 = sigma^2 * tau2 * (tau2 - c*tau1) / det
w2 = sigma^2 * tau1 * (tau1 - c*tau2) / det

E[theta | S1, S2]   = w1*S1 + w2*S2
Var[theta | S1, S2] = sigma^2 - sigma^4 * (tau1^2 + tau2^2 - 2*c*tau1*tau2) / det
```

`w1 > w2` whenever `tau1 < tau2` (the lower-noise signal gets more weight).

**Check (c=0, independent, standard Bayesian precision weighting).** At `c=0`:
`det = sigma^2*tau1^2 + sigma^2*tau2^2 + tau1^2*tau2^2`, and dividing `w1`'s numerator/denominator by
`sigma^2*tau1^2*tau2^2` gives `w1 = (1/tau1^2) / (1/sigma^2 + 1/tau1^2 + 1/tau2^2)` -- exactly the textbook
precision-weighted posterior mean. Confirmed numerically against `bayes.two_signal_general` below (S7) **and**
against an independent from-scratch re-derivation using `numpy.linalg.solve` on the 2x2 `Sigma` directly,
without any of the simplified closed-form algebra above (see "Independent re-derivation" below) -- the two
agree to float64 precision on every sampled row.

### S3.3 Symmetric case tau1 = tau2 = tau (the base and stale variants)

Substituting `tau1=tau2=tau`: `det = tau^2(1-c) * (2*sigma^2 + tau^2*(1+c))`, and the two signals' coefficients
become identical (`w1=w2`, by symmetry):

```
E[theta | S1, S2]   = sigma^2 * (S1+S2) / (2*sigma^2 + tau^2*(1+c))
Var[theta | S1, S2] = sigma^2 * tau^2*(1+c) / (2*sigma^2 + tau^2*(1+c))
w1 = w2             = sigma^2 / (2*sigma^2 + tau^2*(1+c))
```

**This weight split (w1=w2) is exactly 50/50 for every c** -- redundancy changes how much *total* weight the
pair of signals gets relative to the AR(1)-only forecast (through the denominator), not how that weight splits
between Signal A and Signal B. "Which signal do you weight more" is only discriminating in the contradiction
variant (S5.3), where tau1 != tau2 by construction.

**Check (c=1, S2 fully redundant).** `Var = sigma^2*tau^2/(sigma^2+tau^2)`, exactly the one-signal posterior
variance (S3.4) -- correct, because `corr(u1,u2)=1` with equal variances forces `u1=u2` almost surely.

**Check (c=0, two independent measurements).** `Var = sigma^2*tau^2/(2*sigma^2+tau^2)`, matching the textbook
posterior precision `1/sigma^2 + 2/tau^2`.

### S3.4 One-signal corollary (the stale-signal rule, S5.2)

If a signal carries **zero** correlation with the current `theta` -- genuinely dropped, not merely `c=0` --
the general formula with `Cov(theta,S2)=0` and `Cov(S1,S2)=0` collapses to the standard one-signal update:

```
E[theta | S1]   = sigma^2 * S1 / (sigma^2 + tau1^2)
Var[theta | S1] = sigma^2 * tau1^2 / (sigma^2 + tau1^2)
```

i.e. **weight exactly 0 on S2**. The generating process re-draws `eps_{t+1}` fresh every round (i.i.d.
innovations), so a value copied verbatim from a past round is independent of the *current* round's innovation,
and the textbook zero-weight-on-an-uninformative-observation result applies exactly.

### S3.5 Optimal additional variance reduction from adding S2, as a function of c

`Delta_Var(c) = Var[theta|S1] - Var[theta|S1,S2]` for the symmetric case:

```
Delta_Var(c) = sigma^4 * tau^2 * (1-c) / [ (sigma^2+tau^2) * (2*sigma^2 + tau^2*(1+c)) ]
```

Linear in `(1-c)` holding tau fixed. `Delta_Var(c=0) = sigma^4*tau^2/[(sigma^2+tau^2)(2*sigma^2+tau^2)]`
(textbook reduction from a second independent measurement); `Delta_Var(c=1) = 0` exactly (fully redundant).
With `sigma=20`: `Delta_Var(0, tau=10) = 35.5556`, `Delta_Var(0, tau=40) = 53.3333`,
`Delta_Var(0.999999, tau=10) ~ 3.2e-05` (checked at `c=0.999999` rather than `1` to show the approach to zero
numerically; at exactly `c=1` it is `0.0`) -- the `delta_var_c0_informative`, `delta_var_c0_noisy`,
`delta_var_c_to_1_informative`, `delta_var_is_zero_at_c1_exact` entries of `build_summary.json["checks"]`,
identical to the source build.

### Independent re-derivation (this port, not in the source)

As an independent cross-check of S3.2 (not merely re-running `bayes.two_signal_general` and trusting it), the
port's own verification script builds `Sigma` and `Cov(theta,S)` directly as NumPy arrays for a sample of rows
drawn from every variant, solves `w = Cov(theta,S) @ np.linalg.inv(Sigma)` with `numpy.linalg.solve` (a
completely different code path: a 2x2 matrix solve, not the expanded closed-form algebra), and compares `w1`,
`w2` and `Var[theta|S]` against the shipped row's `weight_s1`, `weight_s2` and `bayes_optimal_posterior_var`.
Agreement is to float64 precision (`< 1e-9` abs. difference) on every sampled row, across all three variants
and both tau regimes of `contradiction`. See "Verification" in README.md for the exact numbers.

## S4. Prompt design

Reuses the `ar1_forecasting` history format unchanged: 40 `[value, change]` pairs, oldest to newest, first
pair's change is `None`.

**S4.1 What the model is told, and what it is not told.** Each signal line states its own **noise level**
(`tau1`, `tau2`): `"Signal A: <v> (noise level: <tau1>)"`, `"Signal B: <v> (noise level: <tau2>)"`. The model is
**never** told `c` (the redundancy/correlation between the two signals), `sigma`, or `rho`. The closed-form
formulas in S3 all require `c` as an input, so a model that is only ever shown `tau1,tau2` cannot compute the
*exact* Bayes-optimal answer by plugging numbers into a formula at inference time -- it can only approach it by
learning, from many rounds, how much two same-looking numbers should be discounted when they tend to move
together.

**S4.2 Output format.** One free-text sentence (which signal the model weights more heavily and why) followed
by a strict JSON object on its own line: `{"delta1": <number>}`.

## S5. Variants

### S5.1 Base variant: the c x tau x rho factorial

Full factorial of 3 rho x 3 c x 2 tau = **18 conditions**. `c in {0.0, 0.5, 0.95}` (independent / partially
redundant / near-fully redundant -- `0.95` rather than exactly `1.0` keeps `Delta_Var(c)` a small positive
number rather than exactly 0). `tau in {0.5*sigma, 2*sigma} = {10.0, 40.0}` ("informative" / "noisy"). Both
signals share the same `tau` in this variant (S3.3's symmetric case applies).

### S5.2 Stale-signal variant

3 rho x 2 tau = **6 conditions** (fixed `c=0.0`: the *fresh* draws in this variant are independent, so any
effect measured is attributable to staleness alone, not baseline redundancy). In each realization, for rounds
`r>=2`, a Bernoulli(`p=0.30`) flag (own RNG stream, `purpose_idx=2`) decides whether `S2` at round `r` is a
**verbatim repeat** of round `r-1`'s `S2` (no fresh draw -- the row's `s2` field is set to the literal previous
value) rather than a fresh draw. Round 1 is never stale. Each row carries `stale_round` (bool) and, when true,
`stale_source_round` (always `r-1`). Every round `r>=2` of this variant's prompt (stale or not) also states,
truthfully, *"In the previous round, Signal B's value was `<v>`."* -- fresh rounds state the (different) true
previous value, stale rounds state a value equal to the current `Signal B` line exactly; `stale_round` /
`stale_source_round` are scoring-only metadata, never in the prompt text. Ground truth: a stale `S2` gets
`weight_s2 = 0.0` exactly, and `bayes_optimal_posterior_var` equals the one-signal formula, not the two-signal
one. Build-time checks confirm both (S7). Count on this port's build: **8,916 stale rounds** out of the
variant's rounds with `r>=2` (identical to the source: `8,916 / 29,952 = 29.8%`, matching Bernoulli(0.30)
within sampling noise -- identical because the port uses the same `BASE_SEED` and the same seed tree).

### S5.3 Contradiction variant

3 rho x 2 precision-regimes = **6 conditions**. Unlike S5.1/S5.2, `tau1 != tau2` by construction: the two
regimes are `(tau1,tau2) = (10.0, 40.0)` ("A informative, B noisy") and `(40.0, 10.0)` ("A noisy, B
informative"), covering both directions. Underlying noise draws use `c=0.0` (independent `u1,u2`); on top of
that, **every row in this variant is forced to have `sign(s1) != sign(s2)`**: after drawing the honest
`(u1,u2)`, if the two signals would have agreed in sign, `S2`'s sign is flipped (`s2 := -(theta+u2)`); if they
already disagreed, nothing changes. The per-row `contradiction_flip_applied` flag records which happened. The
flip was necessary in **62.86% of the 30,720 contradiction rows** on this port's build (identical to source).
**Resolution rule**: the Bayes-optimal response is the *same* S3.2 formula evaluated on whatever numbers are
shown -- the generator does not special-case the flip. Because `tau1 != tau2`, the general formula's `w1 !=
w2`, and the lower-tau signal's coefficient is always the larger one (e.g. `tau1=10, tau2=40, c=0`:
`w1=0.7619, w2=0.0476`, ratio `16:1 = tau2^2/tau1^2`, matching S3.2's `c=0` check).

## S6. Position/salience variant

Every row carries two prompt texts under `prompt_variants`, `base` and `position_swapped`, with **identical
statistical content**: the same `Signal A` value/tau and the same `Signal B` value/tau, in both. They differ
only in presentation: `position_swapped` introduces Signal B first, lists the two signal lines in reverse
order, and rewords the task sentence; the output-format instruction is unchanged. Signal **identity** is never
swapped -- "Signal A" always means `s1`/`S1` and "Signal B" always means `s2`/`S2` in both variants, so
`bayes_optimal_delta1`, `weight_s1`, `weight_s2` and `sft_target` are identical between the two prompt texts of
the same row. **Check**: the build extracts every `"Signal [AB]: <num> (noise level: <num>)"` occurrence from
both variants of every row with a regex, sorts them, and asserts the two sorted lists are equal --
`position_swap_information_equivalent: true` over all 153,600 rows (S7).

## S7. Build-time self-checks (all passed on this port's build; `build_summary.json["checks"]`)

| Check | Result (port) | Result (source) |
|---|---|---|
| `base_posterior_var_constant_within_condition` | true | true |
| `base_weights_always_equal` | true | true |
| `delta_var_c0_informative` / `delta_var_c0_noisy` | 35.5556 / 53.3333 | 35.5556 / 53.3333 |
| `delta_var_c_to_1_informative` / `delta_var_is_zero_at_c1_exact` | 3.2e-05 / 0.0 | 3.2e-05 / 0.0 |
| `n_stale_rounds` / `stale_weight_s2_always_zero` / `stale_var_matches_one_signal_formula` | 8,916 / true / true | 8,916 / true / true |
| `stale_s2_equals_prev_round_s2` | true | true |
| `n_contradiction_rounds` / `contradiction_always_opposite_sign` / `contradiction_flip_rate` | 30,720 / true / 0.6286 | 30,720 / true / 0.6286 |
| `position_swap_information_equivalent` | true | true |
| global realization dedup | 3,840 / 3,840 unique | 3,840 / 3,840 unique |

Every check is identical to the source build, row for row, because the port reuses `BASE_SEED = 20261020` and
the identical seed tree, formulas and rounding rules (confirmed directly: see "Verification" in README.md for
the row-count and decompressed-byte-count match against the source's `build_summary.json`).

## S8. Determinism (mandatory; proved, not assumed)

The full build was run twice from this port's code, to two different output directories, from the same
`BASE_SEED`. Every pair of output files was compared byte for byte: the three `.jsonl.xz` archives (the
**compressed** bytes, not just their decompressed content), `MANIFEST.sha256`, and `build_summary.json`'s
`checks`/`total_rows`/`decompressed_sha256`/`compressed_sha256` fields -- **no differences** (see README.md
"Determinism" for the exact commands and hashes). The `.xz` compression is itself deterministic because the
build fixes its format (`FORMAT_XZ`), integrity check (`CHECK_CRC64`) and preset (9) explicitly, and the XZ
container format carries no embedded timestamp or filesystem metadata (unlike gzip), so compressing the same
bytes twice with the same settings yields the same compressed bytes (verified directly, independent of the
full build, with a round-trip micro-test). No `Date.now()`-equivalent, no unseeded randomness, and no dict/set
iteration affects output order anywhere in the generator: every loop is over an explicit, fixed-order sequence,
and every random draw comes from a `numpy.random.Generator(PCG64(SeedSequence(...)))` built from an explicit
integer `spawn_key` tuple, never from the module-level `numpy.random` global state and never reseeded from
wall-clock time.

## S9. Sample size and port fidelity

Realization counts: train 64, val/test 32 per condition (S1.1, S9 of the source design) -- unchanged by the
port. Per split: train 76,800 rows (30 conditions x 64 realizations x 40 rounds), val 38,400, test 38,400,
total 153,600.

**Port fidelity.** Because this port reuses the source's exact `BASE_SEED`, seed tree, rounding rules and
formulas, its regenerated `{train,val,test}.jsonl` are **byte-for-byte identical** to
`1_overreaction`'s own shipped `data/datasets/evidence_relations/synthetic/{train,val,test}.jsonl`
(confirmed directly: identical decompressed byte counts -- 330,884,418 / 165,262,933 / 165,422,680 -- and
identical `build_summary.json["checks"]` values; see README.md "Verification" for the full source-vs-port
table, including a row-level diff of a sample of rows across all three variants and sha256 of the full
decompressed content against the source files).

## S10. Shipping format (port-specific: this repository ships compressed, the source ships raw)

The source project ships raw `.jsonl` (330.9 / 165.3 / 165.4 MB, ~660 MB total): every row repeats the full
~900-byte prompt-instruction boilerplate (`INTRO_PAIRS`, `OUTPUT_INSTRUCTION`, the signal-intro sentences) in
both `prompt_variants.base` and `prompt_variants.position_swapped`, so the text compresses heavily. This
repository ships the xz-compressed files instead (`train.jsonl.xz`, `val.jsonl.xz`, `test.jsonl.xz`), at a
measured **~48.9x** ratio overall (330,884,418 -> 6,764,920 bytes for `train`; see README.md for the exact
per-file ratios), **13.0 MB total** rather than ~660 MB, with `evidence-synthetic`'s default action
regenerating fresh from the generator (so nothing needs to be decompressed to reproduce the dataset) and
`--check` decompressing the shipped archives and comparing them, byte for byte, against a fresh in-memory
regeneration (see README.md "Source of truth").

## Files

- `{train,val,test}.jsonl.xz`: xz-compressed JSONL, one JSON object per round after decompression. Fields:
  `id`, `split`, `variant` (`base`/`stale`/`contradiction`), `rho`, `c`, `tau_setting` (string label), `tau1`,
  `tau2`, `tau` (alias for `tau1`, kept for schema compatibility with a single-`tau` field list), `realization`,
  `round`, `t_index`, `history` (40 floats), `x_t`, `x_next`, `true_eps_next` (hidden from the prompt), `s1`,
  `s2`, `weight_s1`, `weight_s2` (the row's actual MMSE coefficients, S3), `bayes_optimal_delta1`,
  `bayes_optimal_posterior_var`, `stale_round`, `stale_source_round`, `contradiction_flip_applied`,
  `prompt_variants` (`base`, `position_swapped`), `sft_target`.
- `MANIFEST.sha256`: sha256 of every file in this folder (`sha256sum -c MANIFEST.sha256`), i.e. of the
  **compressed** `.xz` files, `README.md`, `DESIGN.md` and `build_summary.json`.
- `build_summary.json`: exact counts, compressed/decompressed byte sizes and sha256, and S7 check results from
  the build that produced the committed files -- including `decompressed_sha256`, the sha256 of what
  `xz -d -c <file>.jsonl.xz` must reproduce (S10's "documented sha256 of the decompressed content").

## Conditions table (exact counts, identical to the source)

| variant | conditions | realizations/condition (train+val+test) | rounds/realization | rows/condition | total rows |
|---|---|---|---|---|---|
| base | 18 (3 rho x 3 c x 2 tau) | 64+32+32=128 | 40 | 5,120 | 92,160 |
| stale | 6 (3 rho x 2 tau, c fixed to 0.0) | 128 | 40 | 5,120 | 30,720 |
| contradiction | 6 (3 rho x 2 precision regimes, c fixed to 0.0) | 128 | 40 | 5,120 | 30,720 |
| **total** | **30** | | | | **153,600** |

Per split: train 76,800 rows, val 38,400, test 38,400. Decompressed file sizes: `train.jsonl` 330,884,418
bytes, `val.jsonl` 165,262,933 bytes, `test.jsonl` 165,422,680 bytes (identical to the source). Compressed
(`.xz`, shipped) sizes and the full sha256 table are in README.md.

## How to regenerate

```sh
finagent evidence-synthetic                   # writes {train,val,test}.jsonl.xz + MANIFEST.sha256 + build_summary.json
finagent evidence-synthetic --check           # regenerates in memory, compares with the shipped .xz (no files written)
```

Byte-identical on every rerun (S8); `sha256sum -c MANIFEST.sha256` after rebuilding checks the compressed files,
and `build_summary.json`'s `decompressed_sha256` checks the decompressed content.

## What "Bayes-optimal" means operationally here

For every row, `bayes_optimal_delta1 = round2( (rho-1)*x_t + E[eps_{t+1} | signals shown] )` and
`bayes_optimal_posterior_var = round2( Var[eps_{t+1} | signals shown] )`, where the conditional moments use the
**exact** closed-form formulas of S3 (general S3.2 for the contradiction variant's asymmetric tau, symmetric
S3.3 for the base variant, one-signal S3.4 for stale rounds), evaluated at the **row's own, true** generative
parameters `(rho, c, tau1, tau2, sigma=20)` -- not estimated from data, not approximated. A model that matched
it exactly would be acting as a perfect Bayesian given everything the signals and history jointly reveal about
`eps_{t+1}`, including the correct (and non-trivial, since it is never stated) discount for redundancy,
staleness, or asymmetric precision under conflict.
