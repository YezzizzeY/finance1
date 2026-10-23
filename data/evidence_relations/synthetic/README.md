# evidence_relations / synthetic

A synthetic multi-signal Bayesian benchmark extending the Gao-style AR(1) replication (`ar1_forecasting` in
the sibling `1_overreaction` project) with a second evidence channel whose redundancy with the first
is a controlled, known parameter `c`, so the Bayes-optimal use of the second signal is closed form and
checkable exactly. This track is self-contained: its own RNG, no dependency on this repository's `data/`
(price panel, news caches, days) or any other `finagent` module's data. Full derivations, every design
decision and all build-time self-checks are in [`DESIGN.md`](DESIGN.md); this file is a short orientation plus
the source-vs-port comparison and the determinism proof.

Ported from `1_overreaction/repro/evidence_relations/{generate,bayes,prompts,build}.py`, onto
`src/finagent/evidence_relations/{synthetic,bayes}.py`, with the same `BASE_SEED` and seed tree, so a
regeneration here is checkable row for row against that project's own shipped
`data/datasets/evidence_relations/synthetic/`.

## What is in the data

Same AR(1) process as `ar1_forecasting` (`x_t = rho*x_{t-1}+eps_t`, `eps_t ~ N(0,20^2)`), `rho` in
`{0.0, 0.4, 0.8}`. At every round, alongside the usual 40-point history, the model is also given two noisy
signals about the upcoming change, `Signal A` and `Signal B`, each labeled with its own stated noise level
(`tau`). The signals' *true* correlation `c` (how redundant they are with each other) is known to the
generator but never told to the model -- exactly like `rho` and `sigma` are known to the generator but never
stated in the prompt.

Three variants, 30 conditions total, 153,600 rows total (train 76,800 / val 38,400 / test 38,400):

| variant | what it tests | conditions | rows |
|---|---|---|---|
| `base` | redundancy discount: `c` in `{0.0, 0.5, 0.95}` x `tau` in `{10, 40}` x 3 `rho` | 18 | 92,160 |
| `stale` | zero-weighting a repeated (no-new-information) signal | 6 | 30,720 |
| `contradiction` | precision-weighted resolution when the two signals disagree | 6 | 30,720 |

## The three things being tested, in one line each

1. **Redundancy discount** (`base`): as the two signals become more redundant (`c` closer to 1), the
   Bayes-optimal forecast shrinks the pair's combined influence toward the history-only forecast -- but always
   splits whatever weight it does give them exactly 50/50 between Signal A and Signal B, because both have the
   same stated noise level.
2. **Staleness** (`stale`): a signal that is a verbatim repeat of an earlier round's value (no fresh draw) gets
   exactly zero additional weight -- not approximately, exactly, because the AR(1) innovations are i.i.d.
   across rounds.
3. **Conflict + asymmetric precision** (`contradiction`): when the two signals are forced to disagree in sign,
   and have *different* stated noise levels, the Bayes-optimal resolution weights the lower-noise (more
   precise) signal more heavily, in the exact ratio the closed-form formula predicts.

## Closed-form formulas (verbatim from DESIGN.md S3; sigma=20 fixed, both measured for `theta=eps_{t+1}`)

General (tau1 may differ from tau2):
```
det = (sigma^2+tau1^2)(sigma^2+tau2^2) - (sigma^2+c*tau1*tau2)^2
w1  = sigma^2 * tau2 * (tau2 - c*tau1) / det
w2  = sigma^2 * tau1 * (tau1 - c*tau2) / det
E[theta|S1,S2]   = w1*S1 + w2*S2
Var[theta|S1,S2] = sigma^2 - sigma^4*(tau1^2+tau2^2-2*c*tau1*tau2)/det
```
Symmetric (tau1=tau2=tau; base and stale variants' fresh rounds):
```
E[theta|S1,S2]   = sigma^2*(S1+S2) / (2*sigma^2 + tau^2*(1+c))
Var[theta|S1,S2] = sigma^2*tau^2*(1+c) / (2*sigma^2 + tau^2*(1+c))
w1 = w2          = sigma^2 / (2*sigma^2 + tau^2*(1+c))
```
One signal only (stale rounds -- the other signal is dropped entirely, weight 0):
```
E[theta|S1]   = sigma^2*S1 / (sigma^2+tau1^2)
Var[theta|S1] = sigma^2*tau1^2 / (sigma^2+tau1^2)
```
Then `bayes_optimal_delta1 = (rho-1)*x_t + E[theta|...]`, `bayes_optimal_posterior_var = Var[theta|...]`.

## Fields (one JSON object per round, in `{train,val,test}.jsonl`, shipped xz-compressed)

`id, split, variant, rho, c, tau_setting, tau1, tau2, tau, realization, round, t_index, history (40 floats),
x_t, x_next, true_eps_next (hidden from prompt), s1, s2, weight_s1, weight_s2, bayes_optimal_delta1,
bayes_optimal_posterior_var, stale_round, stale_source_round, contradiction_flip_applied, prompt_variants
{base, position_swapped}, sft_target`.

## Shipping format: compressed, not raw

The decompressed JSONL is large (~660 MB total: every row repeats the ~900-byte prompt-instruction
boilerplate in both `prompt_variants.base` and `prompt_variants.position_swapped`), and that repetition
compresses heavily. This repository ships `{train,val,test}.jsonl.xz` instead of the raw files:

| file | decompressed bytes | compressed bytes | ratio |
|---|---:|---:|---:|
| `train.jsonl(.xz)` | 330,884,418 | 6,764,920 | 48.9x |
| `val.jsonl(.xz)` | 165,262,933 | 3,431,376 | 48.2x |
| `test.jsonl(.xz)` | 165,422,680 | 3,421,592 | 48.3x |
| **total** | **661,570,031** | **13,617,888 (13.0 MB)** | **48.6x** |

(`xz`, `FORMAT_XZ`, `CHECK_CRC64`, preset 9 -- `src/finagent/evidence_relations/synthetic.py`'s `compress_xz`.)

**Source of truth.** The generator (`synthetic.py` + `bayes.py`, with the fixed `BASE_SEED = 20261020`) is the
source of truth: it is what every count and check in this README and in DESIGN.md is reported from, and
`finagent evidence-synthetic`'s default action regenerates from it (no decompression needed). The shipped
`.xz` files are a compressed cache of exactly that output, kept so the data can be inspected or used without
regenerating:

```sh
xz -d -k -c data/evidence_relations/synthetic/test.jsonl.xz | head -1 | python3 -m json.tool   # quick look, no regeneration
```

`finagent evidence-synthetic --check` proves the two agree: it regenerates the dataset fresh, in memory, and
compares the result byte for byte against the shipped `.xz` files (decompressed content) and against
`build_summary.json`'s recorded checks and hashes -- so "regenerate" and "decompress the shipped archive" are
not an either/or, they are required to produce identical bytes, and this is checked, not assumed.

## Verification (this port against the source build)

Both built from the same code (ported unchanged) and the same `BASE_SEED = 20261020`:

| | source (`1_overreaction/.../synthetic/`) | this port (`data/evidence_relations/synthetic/`) |
|---|---|---|
| total rows | 153,600 | 153,600 |
| train / val / test rows | 76,800 / 38,400 / 38,400 | 76,800 / 38,400 / 38,400 |
| conditions | 30 | 30 |
| unique realizations | 3,840 / 3,840 | 3,840 / 3,840 |
| `train.jsonl` decompressed bytes | 330,884,418 | 330,884,418 |
| `val.jsonl` decompressed bytes | 165,262,933 | 165,262,933 |
| `test.jsonl` decompressed bytes | 165,422,680 | 165,422,680 |
| `n_stale_rounds` | 8,916 | 8,916 |
| `n_contradiction_rounds` / flip rate | 30,720 / 0.6286 | 30,720 / 0.6286 |
| `delta_var_c0_informative` / `_noisy` | 35.5556 / 53.3333 | 35.5556 / 53.3333 |
| `position_swap_information_equivalent` | true | true |
| `train.jsonl` sha256 | `ee5c5d2c…d8aef` | `ee5c5d2c…d8aef` |
| `val.jsonl` sha256 | `87b0a569…ff0812` | `87b0a569…ff0812` |
| `test.jsonl` sha256 | `86f885df…93bcc` | `86f885df…93bcc` |

The decompressed sha256 (of the full, uncompressed JSONL content: `xz -d -c <file>.jsonl.xz | sha256sum`,
also recorded in `build_summary.json["decompressed_sha256"]`) is **byte-for-byte identical** to the
corresponding entry of the source project's own `data/datasets/evidence_relations/synthetic/MANIFEST.sha256`
for all three splits -- not merely matching aggregate counts: every byte of every one of the 153,600 JSON
lines (key order, float formatting, prompt text, all 30 conditions) is identical between this port and the
source. A row-level diff (`crosscheck.py`, a shrunk-realization-count run of both the source's and this port's
`build_condition` against the same seeds, done separately as an additional check) over 4,800 sampled rows
across all three variants found zero mismatches, consistent with the full-file hash match.

**Independent re-derivation of the Bayes-optimal formula** (DESIGN.md "Independent re-derivation"): for a
sample of rows across all three variants, `w1`/`w2`/`Var[theta|S]` were recomputed from scratch with
`numpy.linalg.solve` on the 2x2 `Sigma = Cov([S1,S2])` matrix directly -- a different code path from the
expanded closed-form algebra in `bayes.py` -- and compared against the shipped row's `weight_s1`, `weight_s2`
and `bayes_optimal_posterior_var`. Max absolute difference over the sample: `< 1e-9` (float64 precision noise).

## Determinism

The full generator was run twice, to two different output directories, from the same code and `BASE_SEED`.
`cmp -s` on every pair of output files (the three **compressed** `.jsonl.xz`, `MANIFEST.sha256` and
`build_summary.json`) reported no differences:

```
run 1 (data/evidence_relations/synthetic/):  sha256sum train.jsonl.xz val.jsonl.xz test.jsonl.xz MANIFEST.sha256 build_summary.json
run 2 (scratch directory):              same command
diff: empty (every file byte-identical, including the xz-compressed bytes)
```

See `MANIFEST.sha256` in this directory for the exact hashes, and `build_summary.json` for
`decompressed_sha256` (what `xz -d -c <file>.jsonl.xz | sha256sum` must reproduce) and `compressed_sha256`
(the `.jsonl.xz` files' own hashes, i.e. `MANIFEST.sha256`'s content in another form).

## Regenerate

```sh
finagent evidence-synthetic                   # writes {train,val,test}.jsonl.xz + MANIFEST.sha256 + build_summary.json here
finagent evidence-synthetic --out DIR          # write elsewhere
finagent evidence-synthetic --check            # regenerate in memory only, compare with the shipped files
```
