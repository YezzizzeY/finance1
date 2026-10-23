# Data

Every input the presentation pilot reads, byte-identical to the original files (937 files, 171.4 MB — the pilot
itself uses only six of the 96 `pit_cache/` tickers; the other 90 are the evidence-relations extension's point-in-time
caches, [`evidence_relations/`](#evidence_relations) below). `MANIFEST.sha256` holds the sha256 of each of them (this
README and the manifest itself excluded):

```sh
cd data && sha256sum -c --quiet MANIFEST.sha256
```

What each file is, who reads it, where it came from and under what terms: [`docs/DATA.md`](../docs/DATA.md),
[`docs/PROVENANCE.md`](../docs/PROVENANCE.md), [`DATA_LICENSE.md`](../DATA_LICENSE.md).

| Path | Files | Size | Content |
|---|---:|---:|---|
| `days.json` | 1 | 6.9 kB | the six pilot days: ticker, decision date t, decision time D(t), anchor file and hash, selection rule |
| `pit_cache/<TK>/2025-09-29_2026-09-24_news_v2/` | 96 × 7 | 128.1 MB | point-in-time cache per ticker: daily bars, company news, corporate actions, manifest. The pilot's six (MCHP, HOOD, CRWD, VST, CB, MRK) plus 90 more copied byte-identical from the same build (`pit_cache_v2`) for the evidence-relations day pool and tool-redundancy matrix |
| `panel/us_daily_stratos_20260924.parquet` (+ `.manifest.json`) | 2 | 14.1 MB | US daily OHLCV panel, 507 tickers, 2023-07-17 to 2026-09-24; source of the realised 5-day outcomes |
| `panel/source/stratos_ohlcv_750_20260925.parquet` | 1 | 21.1 MB | the Hugging Face snapshot the panel was normalised from |
| `anchors/<day_id>.json.gz` | 250 | 7.0 MB | saved Qwen3-8B anchor sessions (days t-2 and t-1) of every candidate day; six of them start the pilot runs |
| `selection/` | 5 | 0.8 MB | `s1_spec.json` and `grounding_blocks.json` (with their `.sha256` sidecars) used to draw the days, and `rational_model.json`, the prior model behind the spec's baseline |
| `grounding_sessions/<day_id>/FULL_G_0.json.gz` | 6 | 87 kB | earlier saved sessions whose prompts the ORIG prompts must equal byte for byte |

**[`prompts/`](prompts/README.md)** (72 files) is not one of the pilot's inputs above — it is every text the models
saw, *written by* `finagent prompts` from the data above, and checked by `finagent prompts --check` (byte equality
with a fresh regeneration), not by `MANIFEST.sha256`. **[`evidence_relations/`](#evidence_relations)** below is a
second, independent, CPU-only extension with its own verification, not part of the pilot or of `finagent verify`.

## evidence_relations

How well an agent combines, discounts or ignores pieces of evidence — two independent families, both CPU only,
no GPU, no model calls, both ported from the already-verified `1_overreaction/repro/evidence_relations`
build. Code: `src/finagent/evidence_relations/`. Four of its five pieces live here, under `data/evidence_relations/`,
as inputs/benchmark definitions alongside the rest of this folder; the fifth, `reference_models/`, is an analysis
output and lives under [`results/evidence_relations/`](../results/evidence_relations/) instead, matching how
`results/` already holds the five-model pilot's other analysis outputs.

| Folder | What it is | Rows / size |
|---|---|---|
| [`evidence_relations/day_pool/`](evidence_relations/day_pool/README.md) | the TRAIN/TEST_CORE/TEST_FULL split of every candidate day, over all 96 `pit_cache` tickers | 197 days |
| [`evidence_relations/real_day_perturbations/`](evidence_relations/real_day_perturbations/README.md) | four families of real-headline/real-number prompt perturbations with a known ground truth (zero-shift, ordinal, no-flip) | 1,742 rows |
| [`evidence_relations/tool_redundancy/`](evidence_relations/tool_redundancy/README.md) | an empirical correlation matrix of the 23 non-stateful toolbox tools' outputs, over all 96 tickers | 23,777 (ticker, day) rows |
| [`evidence_relations/synthetic/`](evidence_relations/synthetic/README.md) | a synthetic two-signal Bayesian benchmark with a known-redundancy second evidence channel; self-contained, no dependency on `data/` | 153,600 rows (train/val/test) |
| [`../results/evidence_relations/reference_models/`](../results/evidence_relations/reference_models/README.md) | three deterministic, non-LLM reference forecasters run on `evidence_relations/synthetic/test.jsonl` | 38,400 rows scored |

### Regenerate

```
cd finance1
.venv/bin/finagent evidence-pool                 # evidence_relations/day_pool/ (fast)
.venv/bin/finagent evidence-real-day              # evidence_relations/real_day_perturbations/ (fast)
.venv/bin/finagent evidence-tools --workers 32    # evidence_relations/tool_redundancy/ (the slow one: ~2 min on 48+ cores)
.venv/bin/finagent evidence-synthetic             # evidence_relations/synthetic/
.venv/bin/finagent evidence-reference-models      # ../results/evidence_relations/reference_models/
```

or `make evidence-pool evidence-real-day evidence-tools evidence-synthetic evidence-reference-models`.

### Determinism

Every generator here was run twice (two independent output roots, `day_pool` and `real_day_perturbations` via
`tests/test_evidence_relations.py::test_build_all_is_deterministic`; `tool_redundancy` via a full two-run,
96-ticker, 48-worker pass) and the outputs diffed. Every data file came back byte-identical; the only files that
differ at all are `tool_redundancy/_generate_meta.json` and its `MANIFEST.sha256` (the `elapsed_sec` wall-clock
field the generator records for itself — not a data value, and the same convention the source project uses).

### Source-vs-port

Each subfolder's own README.md carries a source-vs-port table for its own counts, all checked against
`1_overreaction`'s already-shipped `data/datasets/evidence_relations/` and `data/datasets/agent_trading_days/`.
Every count this repository's track (`day_pool/`, `real_day_perturbations/`, `tool_redundancy/`) measured matches
the source exactly, including the `already_priced_in` family's 2026-10-20 point-in-time-leak fix (0 of 197 rows
splice a headline dated on or after day t) and the tool-redundancy matrix's 42 fully-independent tool pairs
(the identical set of pairs, not just the same count).

Full design, the real-day ground-truth claims at their exact precision, and the tool-redundancy methodology:
[`docs/EVIDENCE_RELATIONS.md`](../docs/EVIDENCE_RELATIONS.md).
