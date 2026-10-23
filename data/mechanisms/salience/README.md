# Salience inputs

Inputs read only by `src/finagent/mechanisms/salience.py` (output: `results/mechanisms/salience/`), copied with
`cp -a` byte for byte from the research workspace. Source paths are relative to the workspace root. The two session
corpora this analysis also reads, `../sessions/newsagent/` and `../sessions/q3news_s1/`, and the daily panel
`../../panel/us_daily_stratos_20260924.parquet` (`config.PANEL`, the same sha256 as the workspace's
`results/_panel/us_daily_stratos_20260924.parquet`) are shared and not copied again here.

| File here | Source in the workspace | Bytes | sha256 |
|---|---|---:|---|
| `rcf_20261011/rule.json` | `results/rcf_20261011/rule.json` | 11,688 | `350ca6bf49b77682ee301da1f30a4aa5489b1778da0eca3aa0a6662036ecb789` |
| `rcf_20261011/events_all.parquet` | `results/rcf_20261011/data/events_all.parquet` | 2,270,578 | `317f6aaa8da6ef55ad19c669cc7c7c2c93c74ebd26da59f8b15c5cc5d343523b` |
| `rcf_20261011/nonevent_days.parquet` | `results/rcf_20261011/data/nonevent_days.parquet` | 306,643 | `83c753d3686af35a1374556367e02afa40a33d697d105804ba97291f8feee11d` |
| `grounding_A_main/<day_id>/{FULL_G,NO_NEWS_G}_<k>.json.gz` (2,000 files, 250 days × 2 arms × k=0..3) | `results/grounding_20261012/A_main/sessions/<day_id>/` (only the `.json.gz` session files; the `.meta.json` sidecars are not read and not copied) | 26,922,431 in all | `7c6b10fc072cee38d0f202fea410c91817a991e6cd9ce3f5ca8d70c30380204f` (digest of all 2,000 files, see below) |

`rule.json` matches the workspace's own sidecar `results/rcf_20261011/rule.json.sha256`. The grounding digest is the
sha256 of the `sha256sum` lines of all 2,000 files in byte-sorted path order; the same command gives the same digest
in the workspace folder:

```sh
cd data/mechanisms/salience/grounding_A_main && find . -name '*.json.gz' | LC_ALL=C sort | xargs sha256sum | sha256sum
```

What each one is used for:

- `rule.json`: its `operationalization.target_and_bins` defines `R5 = 100 ln(C[t+5]/C[t])` and `sigma = exp(lsig)` at
  close t, so `events_all.sigma` is already the rational 5-day sigma in percent (checked by the code, not just cited).
- `events_all.parquet`, then `nonevent_days.parquet` as fallback (`sigma = exp(lsig)`): the rational 5-day sigma for
  each `day_id`; `events_all.R5` also checks that the panel's dates line up (AAPL_2026-03-19).
- `grounding_A_main/`: scanned in full. No session calls `get_volatility_stats` (the price readings sit in the prompt),
  so it gives 0 usable sessions; the scan also gives the skip counts and tool counts in `data.json`.
