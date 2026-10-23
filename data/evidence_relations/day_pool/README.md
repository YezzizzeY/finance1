# Day pool

The TRAIN / TEST_CORE / TEST_FULL split of every candidate day that carries a registered PRICE TOOL READINGS
block, over all 96 `data/pit_cache` tickers. Built on `finagent.days.candidates()` (the same 250 candidates
`finagent days` already verifies — a `day_id` in `data/selection/s1_spec.json` with a block in
`data/selection/grounding_blocks.json` and a valid saved anchor), not a re-derivation of the candidate rule.
Code: `src/finagent/evidence_relations/pool.py`. Ported from
`1_overreaction/repro/agent_trading_days/pool.py`.

## day_type

Same constants as `finagent.days` (`setup/experiment.toml` `[days]` `big_z=2.0`, `ordinary_z=1.0`):

- **big**: `|z| >= 2.0`
- **ordinary**: `|z| < 1.0`
- **mid**: everything else (`1.0 <= |z| < 2.0`). Mid days are dropped from every pool below. They stay in the
  full 250-day candidate list; nothing here deletes them, this dataset simply does not use them.

Measured on the 250 candidates (`build_pools()` asserts these exact numbers and refuses to continue silently if
they change):

| universe_split | big | ordinary | mid | total |
|---|---|---|---|---|
| train | 1 | 59 | 17 | 77 |
| heldout | 12 | 125 | 36 | 173 |

## The three pools

**TRAIN** = every `universe_split == "train"` candidate with `day_type` in `{big, ordinary}`. 60 days: 1 big, 59
ordinary. The train ticker partition has exactly ONE "big" (`|z| >= 2`) day in the entire 250-candidate pool —
not a bug here, a fact about which days happen to have both a valid saved anchor and a registered block among the
"train" tickers (produced by earlier, already-verified work this module only reads). Each TRAIN row carries a
`sample_weight` field (`0.5/n_big` for the 1 big row, `0.5/n_ordinary` for the 59 ordinary rows) so that a
training loop sampling TRAIN days proportional to `sample_weight` gets 50% of its expected sampling mass from
"big" days and 50% from "ordinary" days, despite the 1-vs-59 count imbalance. This re-weights what already
exists; it does not fix the scarcity: every "big" weighted draw still comes from the one same underlying day.

**TEST_CORE** = from `universe_split == "heldout"`, `day_type` in `{big, ordinary}`: all 12 big days, plus 12
ordinary days drawn to match (`draw_test_core`, seed `TEST_CORE_SEED = 20261020`). 24 days, 12/12.

**TEST_FULL** = every `universe_split == "heldout"` candidate with `day_type` in `{big, ordinary}`. 137 days: 12
big, 125 ordinary. TEST_CORE is a subset of TEST_FULL by construction (every TEST_CORE day is flagged
`in_test_core = true` inside TEST_FULL; never written out a second time).

`finagent.days.draw()` (the pilot's own 6-day draw, seed 20261018) is never called or edited here.

## Ticker disjointness

TRAIN and TEST_CORE/TEST_FULL are filtered on `universe_split`, a field `finagent.days.candidates()` reads
straight out of `data/selection/s1_spec.json`. `build_pools()` asserts the two ticker sets are disjoint (they
are: 0 overlap) and, specific to this port, that every candidate's ticker is present in the 96-ticker
`data/pit_cache` set — the fact this whole extension depends on.

## Counts: source vs. this port

| | source (1_overreaction, 96-ticker `pit_cache_v2`) | this port (finance1, 96-ticker `data/pit_cache`) |
|---|---:|---:|
| candidates | 250 | 250 |
| TRAIN (big / ordinary) | 60 (1 / 59) | 60 (1 / 59) |
| TEST_CORE (big / ordinary) | 24 (12 / 12) | 24 (12 / 12) |
| TEST_FULL (big / ordinary) | 137 (12 / 125) | 137 (12 / 125) |
| TRAIN + TEST_FULL total | 197 | 197 |
| `pool.jsonl` rows, field-for-field vs. source's `assembled/pool.jsonl` | — | identical (197/197 day_ids, 0 field differences, including every `anchor_sha256`/`block_sha256`) |

The exact same 197 day_ids, splits, weights and hashes as `data/datasets/agent_trading_days/assembled/pool.jsonl`
— expected, since both read the same `s1_spec.json`/`grounding_blocks.json`/anchors (already copied into
`finance1/data/` before this extension existed) and apply the same rule; the point of this port is that finance1
can now *regenerate* that file itself, from its own 96-ticker `data/pit_cache`, rather than only copying it.

## File layout

```
day_pool/
  pool.jsonl     one row per day (train + test_full; test_core is flagged inside test_full)
  README.md
```

## Regenerate

```
cd finance1
.venv/bin/finagent evidence-pool
```

CPU only, no GPU, no model calls; a few seconds (250 saved anchors loaded, no network). Deterministic:
`candidates()` and the fixed `TEST_CORE_SEED = 20261020` draw give the same pool every time; re-running is safe
and produces a byte-identical `pool.jsonl` (checked by running it twice and diffing — see the report).
