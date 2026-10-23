# Data

`data/` holds every input the presentation pilot reads, in full and byte-identical to the original files:
307 files, 50.9 MB for the pilot's own six tickers. `data/MANIFEST.sha256` lists the sha256 of every file in
`data/` (937 files, 171.4 MB in total), and `finagent verify`'s "data files" check reads all 937 entries, not
just the pilot's 307: it hashes every file in `data/` (the six pilot tickers and the 90 `evidence_relations`
ones alike) against the manifest and fails on any extra, untracked file too. Lineage back
to the vendors is in [PROVENANCE.md](PROVENANCE.md), terms of use in [DATA_LICENSE.md](../DATA_LICENSE.md).
Hashes below are shortened to 16 hex digits where the manifest has the full value.

**The other 630 files, 120.5 MB: `evidence_relations`'s 90 extra `pit_cache` tickers.** `data/pit_cache/`
holds 96 tickers' point-in-time caches on disk, not six: the pilot itself reads only the six below, and the
other 90 exist solely so that `data/evidence_relations/` (day pool, real-day perturbations, tool-redundancy
matrix — [docs/EVIDENCE_RELATIONS.md](EVIDENCE_RELATIONS.md)) can walk real price and news history for a
much larger ticker universe than the six-day pilot needed. They are built, vendored and licensed by the
identical pipeline described below and in [PROVENANCE.md](PROVENANCE.md) — same Finnhub company-news pull,
same stratos OHLCV panel, same `pit_cache_v2` build — just more tickers; nothing about the sourcing differs
for ticker 7 through 96. They are not otherwise described file-by-file in this page, which stays scoped to
the six pilot tickers' own inputs; their own counts and hashes are in `data/MANIFEST.sha256` and in each
`data/evidence_relations/` subfolder's source-vs-port table.

## Files

| File | Size (bytes) | sha256 | Read by | Content and origin |
|---|---:|---|---|---|
| `days.json` | 6,898 | `25da016c2c321f0f…` | `finagent.days`, and through it every run | The six pilot days (ticker, t, D(t), anchor days, seed base, day type), the selection rule and its pool, and the hashes of its inputs. Built by the original `days.py` (seed 20261018). |
| `panel/us_daily_stratos_20260924.parquet` | 14,133,561 | `da057ddadc875f825363e6efe8965819b1d736a657b6e927a3743591e255d3b6` | `finagent.data.outcomes` | US daily OHLCV, 507 tickers, 403,476 rows, 2023-07-17 to 2026-09-24. Gives the realised 5-day return and volatility of each run; never shown to a model. Normalised from the snapshot below. |
| `panel/us_daily_stratos_20260924.parquet.manifest.json` | 791 | `c5c710b05cb9c647…` | — | Source URL, source and output sha256, row counts, overlap check against an older panel. |
| `panel/source/stratos_ohlcv_750_20260925.parquet` | 21,145,514 | `e2492fbf0ae3f2f1c6cd018051f1c496de504fe56524c842bf12d53509aa50b1` | — (provenance) | Hugging Face `stratos-org/ohlcv-750`, `data/ohlcv.parquet` at revision `786615b8ed255260f77c07cdf279151ae99efc2d`; 609,567 rows, ASX, NZX, US and crypto. |
| `pit_cache/<TK>/2025-09-29_2026-09-24_news_v2/` | 7,704,804 (42 files) | per ticker below | `finagent.data.pit`, `finagent.data.corpactions`, the 32 harness tools, the coding-agent workspace | Point-in-time cache of one stock: everything a model can see for a day comes from here, cut at close t (bars) and at D(t) (news). |
| `anchors/<day_id>.json.gz` | 6,993,171 (250 files) | per file in the manifest | `finagent.data.anchors` (the six pilot days), `finagent.days` (all 250, for the anchor-validity rule) | Saved Qwen3-8B anchor sessions on days t-2 and t-1 of every candidate day: full traces (with token ids, outcomes and headlines), the resulting portfolio `state`, `anchor_valid`. A pilot run starts from the `state` of its day. |
| `selection/s1_spec.json` | 372,322 | `70aac99094712fc75a424cddc2559f1c9dc500dd74896ba8882652e91dd48829` | `finagent.days` | Registered 250-day sample of the anchor stage: per-day ticker, t, D(t), seeds, prior `m` / `lsig` and outcomes (not used to select), harness and server settings with their hashes. No headlines. |
| `selection/s1_spec.json.sha256` | 79 | `d09d058975af5e30…` | — | `sha256sum` sidecar of the file above. |
| `selection/grounding_blocks.json` | 430,272 | `61ac6d1645f8877dd46ee10eea0454ddce54d36fd79f69b821a624cd1f91db35` | `finagent.readings`, `finagent.days`, `finagent.arms` | Registered readings block of 255 days: the 7 price-tool readings inserted into the prompt, with the sha256 of each block's text. |
| `selection/grounding_blocks.json.sha256` | 88 | `56db5bc38f2f3f00…` | — | `sha256sum` sidecar of the file above. |
| `selection/rational_model.json` | 11,810 | `f4fa33299d4c688c47ed100ccb25f3b699e4c8dd12ce7189af25ba6fc90e4b03` | — (provenance) | Coefficients of the rational prior (5-day mean, sd, up-probability) behind `s1_spec.json`'s `m` and `lsig`, hence behind each day's z. |
| `grounding_sessions/<day_id>/FULL_G_0.json.gz` | 86,826 (6 files) | below | `finagent.verify` | Earlier saved Qwen3-8B sessions of the six days; the pilot's ORIG harness prompt and system prompt must equal their first turn byte for byte. |

### Point-in-time caches

Each cache folder has seven files. `prices.json` holds the 802 daily bars 2023-07-17 to 2026-09-24 (the
tools only ever return bars up to close t); `news_ticker.json` the company news with corrected publication
times in America/New_York; `manifest.json` the build notes, D(t) for every trading day and `files_sha256`
of the other six files; `corporate_actions.json` the split list used to show bars at day t's level.
`insider.json`, `news_economy_fiscal.json` and `news_economy_monetary.json` are empty lists
(sha256 `4f53cda18c2baa0c…`), so the prompt's insider and macro sections read "(none)".

| Ticker | Day | `prices.json` | `news_ticker.json` (items) | `manifest.json` | `corporate_actions.json` | Folder |
|---|---|---|---|---|---|---:|
| MCHP | 2026-08-07 | 120,783 `c8f5d3c590cf179b` | 539,619 (529) `9153d4875c96a895` | 28,126 `a3c7442ad73869d4` | 374 `30cdde375d61acdf` | 688,908 |
| HOOD | 2026-04-14 | 120,729 `aa2cc1a39886913f` | 2,132,787 (2,377) `a2de79251479abf2` | 28,085 `65bfd3cc87ff2bd1` | 374 `0d8e579e525f5e35` | 2,281,981 |
| CRWD | 2026-08-27 | 117,424 `93216780a9a085ec` | 1,668,328 (1,738) `e7d720c5e7fa46f9` | 28,127 `eda08376b6e8477d` | 761 `77c926fdf22ef7e2` | 1,814,646 |
| VST | 2026-05-06 | 122,338 `2879b69eb35e0caa` | 580,505 (630) `56681b5ff1480905` | 28,082 `90e57b81ea68acf2` | 372 `aa9da9885b9395c0` | 731,303 |
| CB | 2026-04-22 | 121,972 `77eeb991baa2b25d` | 402,861 (426) `af67b9801c792666` | 28,079 `1a24badc4d926fba` | 371 `ff104a8dfa3c993e` | 553,289 |
| MRK | 2026-05-07 | 122,238 `a59a64c8eef5d97d` | 1,483,767 (1,491) `0e9ae003c3ba628c` | 28,293 `8e6fd5f3cccd24a8` | 373 `9f48c669cf377d4c` | 1,634,677 |

Of these items, those published before each day's D(t) are reachable by the agents: 496, 1,155, 1,540, 400,
284 and 1,031 in the order above.

### Anchors and saved sessions of the six pilot days

| Day | Anchor (bytes, sha256) | Saved session `FULL_G_0` (bytes, sha256) |
|---|---|---|
| MCHP_2026-08-07 | 21,405 `692dd3ce82308235` | 19,658 `df34b98057ad8b42` |
| HOOD_2026-04-14 | 35,858 `f6933562b66d6829` | 12,283 `f74b9f953f1be5e7` |
| CRWD_2026-08-27 | 29,665 `cd647a6980046c72` | 11,533 `3db73e8a6fdde871` |
| VST_2026-05-06 | 26,761 `662cb37aabd8c904` | 11,584 `59fae6f6d5254827` |
| CB_2026-04-22 | 34,254 `65a4e82c932aca8b` | 19,773 `9cf6038a3290d9e8` |
| MRK_2026-05-07 | 24,822 `0581761c16348885` | 11,995 `70fbd9c38119b676` |

The other 244 anchors are read only when the day selection is re-run.

## Hashes recorded inside the data

The copies were checked against the original files and against every hash the files record about each
other (379 checks, 0 failures):

- `days.json`: `anchor_sha256` of the six anchors; `sources` sha256 of `grounding_blocks.json` and `s1_spec.json`.
- the two `.sha256` sidecars;
- each cache `manifest.json`: `files_sha256` of the other six files in its folder (36 hashes);
- the panel manifest: `source_sha256` (the snapshot) and `output_sha256` (the panel);
- `grounding_blocks.json`: each of the six pilot blocks' `sha256` equals the sha256 of its text and
  `days.json` `check.block_sha256`;
- each pilot anchor's `spec_sha256` equals the sha256 of `s1_spec.json`.

## Data embedded in code

A few inputs live in the code rather than in `data/`: the system prompt texts and the reminder
(`finagent.harness.prompts`), the readings-block tool list (`finagent.readings`), the corporate-action
event list (`finagent.data.corpactions`) and the earnings calendar of the earnings tool, which holds AAPL
report dates only (`finagent.harness.toolbox`).

## Licensing in brief

Prices: Hugging Face dataset without a stated license. News: Finnhub and the original publishers, shipped
only for exact non-commercial reproduction. Anchors, saved sessions and registered files: produced by this
project and licensed CC BY 4.0; they hold outputs of Qwen3-8B (weights under Apache-2.0; the outputs are this
project's material) and quote news headlines, which keep their owners' terms. Details and the removal policy:
[DATA_LICENSE.md](../DATA_LICENSE.md).
