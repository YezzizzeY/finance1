# Company-news gap fill of 2026-11-02

Scripts, checks and file hashes for the refetch that closed the gaps in the project's wider company-news
folder (95 tickers, 2025-09-29 … 2026-09-18). **No news text is in this folder**: the headlines and
summaries belong to their publishers and to Finnhub (see [`DATA_LICENSE.md`](../../DATA_LICENSE.md)).
Anyone with a Finnhub key can rerun the scripts; what the free tier still returns shrinks by one day
per day (on 2026-11-02 it returned nothing before 2025-11-07).

**What was wrong.** Finnhub's `company-news` endpoint returns at most about 250 items per call, the
newest ones. The pull of 2026-10-10 split each ticker's history into windows of a few days; for busy
names a window still held more than 250 items, so only its last days survived and the earlier days of
that window were lost outright. The Dow-30 pull of 2026-09-25 used monthly windows and lost more. In the
rebuilt tables before the fill, NVDA had no news at all on 93 of the 108 trading days of
2025-10-06 … 2026-03-11 and on 7 trading days of 2026-03-19 … 2026-09-17; AMZN, MSFT and AAPL had 40, 27
and 26 empty training days.

**What was done.**

1. `scripts/fill_finnhub_news.py` planned one call per (ticker, day) for every day not known to be
   complete (a call that returned fewer than 150 items covers its whole window; a capped call is complete
   only from its oldest item on; the Dow-30 monthly pull has no per-call counts, so all its days were
   refetched) and ran the 4,469 calls one at a time, 1.15 s apart. 79,934 items came back, 21,336 of them
   (ticker, article) pairs the tables did not have; 286 ticker-days returned nothing. Every call is logged
   with its item count and oldest / newest timestamp.
2. `scripts/rebuild_news_tables.py` rebuilt the two news tables with the rules of the original pipeline
   copied verbatim (`scripts/news_lib.py`: relevance, price-move masking, 48-hour Jaccard 0.5 first-report
   rule; the per-source publication-time correction with its three validation tests; first-report
   recomputed in corrected time order; first decision time; items naming a later date dropped). It also
   writes `day_coverage.parquet`: for each ticker and UTC day, whether that day lies inside a span known to
   be complete.

**Result** (`checks/news_rebuild_20261102.json`):

| | before | after |
|---|---|---|
| rows (ticker × article) | 264,006 | 285,342 |
| rows kept (relevant, time-correctable, no future date) | 120,987 | 129,228 |
| NVDA rows kept | 6,980 | 12,234 |
| NVDA empty training days (108 trading days) | 93 | 19 |
| NVDA empty test days (126 trading days) | 7 | 0 |
| AMZN / MSFT / AAPL empty training days | 40 / 27 / 26 | 8 / 8 / 7 |
| ticker-days inside a known-complete span, from 2025-11-07 | — | 100% |

All three publication-time tests pass. The remaining empty days are all before 2025-11-07, which the free
tier no longer serves. 76 single days returned 150 items or more (NVDA 70, AMZN 4, MSFT 2; the plan's `trunc` flag is set at 150, conservatively);
only 3 of them, all NVDA (2026-03-17, 06-01, 06-09), hit the 250-item cap. On those 3 days the oldest item returned lies at
00:37 … 04:49 UTC, so only the late-evening hours (New York time) of the previous day are missing; on the other 73 days the
oldest item is near 00:00 UTC and nothing was cut. The API cannot split a day further.

| Folder or file | What it holds |
|---|---|
| `scripts/fill_finnhub_news.py` | the single-day refetch (plan + calls + merge); the API key is read at run time from a local key file and never written anywhere |
| `scripts/rebuild_news_tables.py`, `scripts/news_lib.py` | the rebuild and the verbatim rule library it imports |
| `scripts/coverage_by_ticker.py` | the per-ticker coverage table of the whole data folder |
| `checks/news_fill_plan_20261102.json` | which ticker-days were refetched and why (counts per ticker and month) |
| `checks/news_fill_20261102.log` | progress log of the run (counts only) |
| `checks/news_rebuild_20261102.json` | before / after comparison, time-rule counts, coverage shares |
| `checks/COVERAGE_BY_TICKER.md` | per-ticker date ranges and counts of every data source after the fill (96 main tickers) |
| `manifests/news.sha256` | SHA-256 of the rebuilt `news/` folder |
| `manifests/raw_news_finnhub.sha256` | SHA-256 of the raw Finnhub pulls after the merge (99 files) |
| `DATA_README.zh-CN.md` | the local data folder's description (Chinese) as of 2026-11-02 |

The pilot's own point-in-time caches (`data/pit_cache/*/news_v2`) were **not** changed by this fill; they
keep the pull described in [`PROVENANCE.md`](../PROVENANCE.md).
