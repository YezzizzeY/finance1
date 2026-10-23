# data/mechanisms

Inputs of the four mechanism analyses (salience, proximity, position adjustment, thinking): saved agent sessions,
saved multi-day trajectories and the rational-benchmark tables they are compared with. Every file is a byte-identical
copy of a file in the research workspace (`1_overreaction`, source paths below are relative to it); nothing here was
produced by this repository's code. 7,011 data files, 107.9 MB, plus the five README.md files.

`MANIFEST.sha256` holds the sha256 of each of the 7,011 files (this README, the four other README.md files and the
manifest itself excluded). `finagent verify`'s "mechanism data" check (L0) hashes them all and fails on a missing,
changed or unlisted file:

```sh
cd data/mechanisms && sha256sum -c --quiet MANIFEST.sha256
```

Code: `src/finagent/mechanisms/`. Results: [`results/mechanisms/`](../../results/mechanisms/). The four questions,
the method and the findings: [`docs/MECHANISMS.md`](../../docs/MECHANISMS.md).

| Path | Files | Bytes | What it is | Source in the workspace | Read by |
|---|---:|---:|---|---|---|
| `sessions/newsagent/<TICKER>_<date>/` | 2,500 | 37,729,810 | Qwen3.5-9B tool-agent sessions on 250 real ticker-days: `FULL_<k>` (news and tools, k = 0..3), `NO_NEWS_<k>` (no news in the prompt), `FULL_T06_<k>` (FULL at temperature 0.6, k = 0, 1) | `results/newsagent_20261011/raw/sessions/` | salience, proximity, thinking |
| `sessions/q3news_s1/<TICKER>_<date>/` | 2,500 | 35,364,055 | the same 250 days and arms, Qwen3-8B with thinking on | `results/q3news_20261012/S1/sessions/` | salience (cross-check), thinking |
| `salience/grounding_A_main/<TICKER>_<date>/` | 2,000 | 26,922,431 | Qwen3-8B sessions with the price readings in the prompt: `FULL_G_<k>`, `NO_NEWS_G_<k>` (k = 0..3); the `.meta.json` sidecars were not copied | `results/grounding_20261012/A_main/sessions/` | salience (scanned; 0 usable sessions) |
| `salience/rcf_20261011/rule.json` | 1 | 11,688 | the rational benchmark's rule: R5 = 100 ln(C[t+5]/C[t]), sigma = exp(lsig), u = (R5 − m)/sigma | `results/rcf_20261011/rule.json` | salience |
| `salience/rcf_20261011/events_all.parquet` | 1 | 2,270,578 | rational benchmark on news-event days: m, lsig, sigma, u per (ticker, day); 15,134 rows | `results/rcf_20261011/data/events_all.parquet` | salience |
| `salience/rcf_20261011/nonevent_days.parquet` | 1 | 306,643 | the same on days without news; 6,035 rows | `results/rcf_20261011/data/nonevent_days.parquet` | salience |
| `position_adjustment/base5d_<window>.json` | 5 | 2,199,725 | BASE-policy Qwen3.5-9B multi-day trajectories (book and tool memory carried 12-15 days), windows val_calm, val_stress, test_calm, test_crash, test_bear | `results/base5d_<window>.json` | position adjustment |
| `position_adjustment/BASE_crash_R2.json` | 1 | 527,427 | a replicate of the test_crash window | `results/newmethods_20261011/eval/tool/BASE/crash.json` | position adjustment |
| `position_adjustment/{events_all,nonevent_days}.parquet` | 2 | 2,577,221 | the same two benchmark tables as under `salience/rcf_20261011/` (identical bytes, kept twice so each analysis folder is complete) | `results/rcf_20261011/data/` | position adjustment |

Each session file is the gzip of one saved session (`trace` with the system prompt, the day prompt, every model turn
with its reasoning, every tool call with its arguments and result, and the submitted decision; plus validity flags and
token counts). The FULL prompts quote company-news headlines and the tool results quote prices, so these files carry
the same third-party text as `data/pit_cache/` ([DATA_LICENSE.md](../../DATA_LICENSE.md)).

Every one of the 7,011 files was compared with its workspace original by sha256 when this folder was assembled: all are
identical, and the three session folders hold exactly the workspace's `.json.gz` files, no more and no fewer.

Which files each analysis reads, with digests of the subsets: [`salience/README.md`](salience/README.md),
[`proximity/README.md`](proximity/README.md), [`position_adjustment/README.md`](position_adjustment/README.md),
[`thinking/README.md`](thinking/README.md).
