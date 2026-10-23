# Provenance

Where each input in `data/` came from, which script built it, and the hashes that tie each step to the next.
Script paths such as `repro/newsagent/build.py` and folders such as `results/rcf_20261011/` belong to the
original research repository; they are named for traceability and are not part of this release. Every
hash below was re-checked against the original files on 2026-10-19.

```
Hugging Face stratos-org/ohlcv-750 @ 786615b8 ──normalise──► panel ──bars_of──► pit_cache/*/prices.json ─┐
Finnhub company-news (free tier) ──filter, time-fix──► pit_cache/*/news_ticker.json ──────────────────────┤
hand-curated split list ──► pit_cache/*/corporate_actions.json ──────────────────────────────────────────┤
                                                                                                          ▼
                            rational_model.json ──► s1_spec.json ──► Qwen3-8B anchor sessions (anchors/)
                                                    grounding_blocks.json ──► grounding_sessions/
                                                    s1_spec + grounding_blocks + anchors ──► days.json
```

## Prices

1. **Vendor snapshot.** Hugging Face dataset [`stratos-org/ohlcv-750`](https://huggingface.co/datasets/stratos-org/ohlcv-750),
   file `data/ohlcv.parquet` at revision `786615b8ed255260f77c07cdf279151ae99efc2d` (commit "Automated OHLCV
   update: 2026-09-25 10:16 UTC (609,567 rows, 767 tickers)", head of `main` until 2026-10-06). Its LFS sha256
   `e2492fbf0ae3f2f1c6cd018051f1c496de504fe56524c842bf12d53509aa50b1` (21,145,514 bytes) equals the shipped
   `data/panel/source/stratos_ohlcv_750_20260925.parquet`, downloaded on 2026-09-25 at about 14:54 UTC. The
   download was not scripted. The card describes daily split- and dividend-adjusted bars for about 763
   equities on ASX, NZX and US (S&P 500) markets, updated after each close; it names no upstream vendor.
2. **Normalised panel.** `repro/goal_external_panel.py` (`normalize`, `main`) keeps `market == "US"`
   (403,476 of 609,567 rows), renames the columns to `Ticker, Date, Open, High, Low, Close, Volume`, parses
   `Date`, refuses duplicate ticker-dates, missing or non-positive prices and any bar after 2026-09-24, sorts
   by ticker and date, and writes `data/panel/us_daily_stratos_20260924.parquet` (sha256 `da057dda…b3d6`;
   507 tickers, 2023-07-17 to 2026-09-24). Its manifest records both hashes and an overlap check of AAPL
   closes in 2026-01/02 against an older panel (39 days, median price ratio 0.99908, median daily-return
   difference 0.0008 bp).
   Re-check: `normalize` applied to the shipped snapshot gives a table equal to the shipped panel, and
   writing it with pyarrow 25.0.1 under the pandas version string of the original write (3.0.6, stored in
   the Parquet metadata) reproduces `da057dda…` byte for byte.
3. **Per-ticker bars.** `repro/newsagent/build.py` (`bars_of`) writes each ticker's 802 panel rows to
   `pit_cache/<TK>/…/prices.json` (re-check: equal to the panel rows for all six tickers, volumes as
   integers). Levels are the vendor's, adjusted as of 2026-09-24.
4. **Corporate actions.** `repro/newsagent/corpactions.py` holds a hand-curated event list, each event with
   the news items that announce it and a check of the price ratio against an older panel. On a decision day
   t the bars are shown multiplied by the factors of the events after t, which undoes later splits; later
   dividends are not undone. Of the six pilot tickers only CRWD has an event (4-for-1 split, ex-date
   2026-07-02, before its day 2026-08-27), so every pilot prompt shows the panel levels unchanged.

## News

1. **Vendor.** Finnhub `GET /api/v1/company-news` on the free tier; headlines and summaries are written by the
   original publishers. Items the agents can reach, by source: Yahoo 5,015, Benzinga 1,343, SeekingAlpha 344,
   CNBC 185, MarketWatch 163, Finnhub 68, Fintel 33, ChartMill 24, DowJones 16 (7,191 cache items).
2. **Raw pulls.**
   - 2026-10-10: `results/rcf_20261011/scripts/fetch_news.py` (stages 1-4, through `finnhub_lib.company_news`,
     1,475 calls logged in `logs/finnhub_calls.jsonl`) wrote `data/news/raw/<TK>.json` with `id, datetime,
     headline, summary, source, url, related`. sha256: MCHP `410ea7b8…`, HOOD `5168f83f…`, CRWD `232e0869…`,
     VST `55e301e3…`, CB `910d172f…`, MRK `7a6d7e59…`.
   - 2026-09-25: `repro/fetch_dow30_news.py` (monthly windows) wrote `results/_panel/dow30/news/MRK.json`
     (sha256 `acd0ed4b…`), which supplies 689 of MRK's 1,491 cache items, including the earliest ones.
   Every item id in the six caches occurs in one of these raw files.
3. **Filtering.** `results/rcf_20261011/scripts/build_events.py` (relevance pattern, first-report test by
   Jaccard similarity, masking) wrote `data/news_items_flagged.parquet` (sha256 `d4348ef3…`, 264,453 rows) and
   `data/coverage.json` (`ff213826…`).
4. **Time correction and caches.** `repro/newsagent/timefix.py` corrects Finnhub's timestamps per source (true
   UTC, local wall time, +5 h, or date only); `repro/newsagent/build.py` (`item_table`, `main`, 2026-10-11)
   keeps relevant items, recomputes the first-report flag in corrected time, drops items whose headline or
   summary mentions a date after the first decision time that could show them, and writes `news_ticker.json` (times in America/New_York) and `manifest.json`
   (`decision_time` D(t) = 09:00 ET on the next trading day of the panel calendar, coverage windows,
   `files_sha256` of the other six files). The build's intermediate files are pinned in `s1_spec.json`
   `data_sha256` (`items_index.parquet` `996872a5…`, `time_validation.json` `3b95c582…`,
   `corporate_actions.json` `75a4b9fa…`); all three still match.
5. `insider.json`, `news_economy_fiscal.json` and `news_economy_monetary.json` are empty lists in every cache.

## The evidence_relations extension's additional pit_cache tickers

`data/pit_cache/` holds 96 tickers, not the six above: the other 90 exist only for `data/evidence_relations/`
(day pool, real-day perturbations, tool-redundancy matrix), which needed a much larger ticker universe than
the six-day pilot to walk real history exhaustively rather than sample it. Their provenance is the *same*
pipeline as the six above, not a different sourcing story: the same Hugging Face `stratos-org/ohlcv-750`
revision for prices, the same Finnhub company-news free-tier pull and the same `repro/newsagent/timefix.py` +
`build.py` time correction and point-in-time cut for news, the same hand-curated corporate-actions process —
all built in the same `pit_cache_v2` run as the six pilot tickers' caches, by the sibling
`1_overreaction` project, and copied byte-identical into this repository's `data/pit_cache/`
(checked per file against that project's own `pit_cache_v2` manifests; the six pilot tickers' caches were
separately re-checked unchanged by this copy — see `data/evidence_relations/day_pool/README.md` and
`data/evidence_relations/tool_redundancy/README.md` for the full source-vs-port tables). Nothing about where the data comes from, who
owns it or on what terms differs for these 90 tickers; see [DATA_LICENSE.md](../DATA_LICENSE.md)'s "Daily
prices" and "News headlines and summaries" rows, which already cover `data/pit_cache/*/` without restricting
to a ticker list.

## Registered selection files and model sessions

| File | Built by | Inputs and settings | Recorded hashes |
|---|---|---|---|
| `selection/rational_model.json` | `repro/twin/data.py` (2026-10-09) | linear models of the 5-day mean, sd and up-probability on features of the displayed prices, with date fixed effects | gives `s1_spec.json` its per-day prior `m`, `lsig` |
| `selection/s1_spec.json` | `repro/q3news/sample.py` `write_registered` (2026-10-12) | 250 ticker-days in 2026-03-03 … 2026-09-17 drawn with seed 20261011; harness, server and seed settings of the anchor stage | sidecar `.sha256`; `harness.system_sha256` = the harness system prompt `e992af5a…`; `harness.tools_sha256` = the 32 tool schemas `32860efa…` |
| `anchors/<day_id>.json.gz` (250) | `repro/q3news/s1_stage.py` → `newsagent/runner.py` `Stage.run_anchor` (2026-10-12) | `Qwen/Qwen3-8B` @ `b968826d…` on vLLM 0.29.0, temperature 1.0, top-p 0.95, 2,048 tokens per turn, thinking on, seed 4,000,000 + 1000·i + 17; trading days t-2 and t-1 from 100,000 cash | each file's `spec_sha256` = `s1_spec.json` (`70aac990…`); the six used in `days.json` `anchor_sha256` |
| `selection/grounding_blocks.json` | `repro/grounding/spec.py` with `grounding/block.py` `compute_block` (2026-10-12) | the readings block (7 price-tool readings) of 255 days, computed from the caches' bars through t | sidecar `.sha256`; each block's `sha256` = sha256 of its text |
| `grounding_sessions/<day_id>/FULL_G_0.json.gz` | the grounding test A run, `results/grounding_20261012/A_main` (spec sha256 `b142e239…`) | Qwen3-8B sessions branched from the same anchors, arm FULL_G, k = 0 | used only to check that the pilot's ORIG prompts equal these saved prompts byte for byte |
| `days.json` | `repro/codexpilot/days.py` `build` (2026-10-18) | candidates = days in both registered files with valid anchors; 3 days with \|z\| ≥ 2 and 3 with \|z\| < 1, drawn with seed 20261018 | sha256 of `grounding_blocks.json`, `s1_spec.json` and the six anchors; each block recomputed and found identical |

## What cannot be downloaded or regenerated again

- **News text.** Finnhub's free tier reaches back about one year: the pull of 2026-10-10 returned nothing
  before 2025-10-15, so MRK's items from 2025-09-29 are already out of reach, and every item the pilot uses
  (the latest D(t) is 2026-08-28) will be by about 2027-08. Finnhub also returns at most about 250 items per
  call and may change ids or text. The caches are therefore shipped as they are.
- **Price levels.** The dataset is rewritten several times a day and its adjusted levels shift with each
  new dividend or split. Revision `786615b8…` can still be downloaded from the dataset history (checked
  2026-10-19), but nothing guarantees it will stay; the snapshot is shipped.
- **Anchors and saved sessions.** They are sampled model outputs from a batched vLLM server with prefix
  caching, so they cannot be regenerated byte for byte; they are shipped frozen.
- **Registered files.** `s1_spec.json`, `grounding_blocks.json` and `days.json` are deterministic given their
  inputs, but those include intermediate tables of the original repository that are not shipped
  (`ticker_days.parquet`, `items_index.parquet`, the price-display panel behind `rational_model.json`).
  `days.json` and the six pilot days' blocks can be recomputed from the shipped data; the other 249 blocks
  and `s1_spec.json` cannot.
