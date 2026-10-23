# real_day_perturbations

Real-day evidence-relationship perturbations built on the evidence_relations day pool
(data/evidence_relations/day_pool/pool.jsonl, 197 days; see finagent.evidence_relations.real_day.common.load_day_pool)
and data/pit_cache's point-in-time price/news cache (now all 96 tickers, not just the pilot's six). CPU only, no
GPU, no model calls; every file here is produced by pure, deterministic code from already-verified inputs
(finagent.readings, finagent.arms, finagent.harness.prompts, finagent.evidence_relations.pool) plus data/pit_cache's
news_ticker.json, read directly. Code: src/finagent/evidence_relations/real_day/*.py. Ported from
1_overreaction/repro/evidence_relations/real_day_*.py (the already_priced_in family in its fixed, 2026-10-20
form — see that family's README.md section below for the fix itself).

Four families, each under its own directory with its own README.md (what ground truth is claimed — zero-shift,
ordinal, or no-flip — and how confidently) and its own MANIFEST.sha256:

| family | ground truth | confidence | rows (source -> port) | days skipped (source -> port) |
|---|---|---|---|---|
| redundancy_copies | expected shift is zero | exact derivation | 788 -> 788 | 0 -> 0 |
| already_priced_in | ordinal (b moves forecast more than a) | documented hypothesis | 394 -> 394 | 0 -> 0 |
| stale_news | stale moves forecast less than fresh | derived, one approximation | 394 -> 394 | 0 -> 0 |
| position_swap_conflict | no flip from order alone | exact (tier 1) / approximate (tier 2) | 166 -> 166 | 114 -> 114 |

## Regenerate

```
cd finance1
.venv/bin/finagent evidence-real-day
```

Deterministic: the day pool is re-derived (not redrawn), every random choice uses a seeded numpy
`SeedSequence(BASE_SEED, spawn_key=(family, day_index, purpose))` Generator, and every generator is a pure function
of the read-only inputs above. `sha256sum -c MANIFEST.sha256` (run from inside this directory) checks every file
here against this manifest; running `finagent evidence-real-day` again produces a byte-identical tree (checked by
running it twice to two different output roots and diffing — see data/README.md's evidence_relations section).

## Days that could not be constructed

See each family's `skipped.json` for the full list with reasons. Tallied reasons:
- (41x) no technical-indicator contradiction, and the most-recent headline's keyword polarity (1) does not oppose the day's price-direction sign (1)
- (35x) no technical-indicator contradiction, and the most-recent headline's keyword polarity (0) does not oppose the day's price-direction sign (-1)
- (34x) no technical-indicator contradiction, and the most-recent headline's keyword polarity (0) does not oppose the day's price-direction sign (1)
- (4x) no technical-indicator contradiction, and the most-recent headline's keyword polarity (-1) does not oppose the day's price-direction sign (-1)

## Scope

Each row carries a full, self-contained HARNESS prompt variant (`prompt`, the text
finagent.harness.prompts.harness_prompt would render for that arm, plus one `prompt_sha256` per row). The
coding-agent workspace files that finagent's coding framework also produces are NOT additionally materialised
here, since the testable claim in every family is about the forecast a prompt elicits, not about the coding-agent
framework.
