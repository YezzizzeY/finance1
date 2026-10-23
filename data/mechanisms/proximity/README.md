# Proximity analysis: inputs

The proximity analysis (`src/finagent/mechanisms/proximity.py`, output `results/mechanisms/proximity/`) needs no
input of its own. It reads only part of the shared session corpus, so nothing was copied into this folder.

| What it reads | Copied from (research workspace) | Files |
|---|---|---|
| `data/mechanisms/sessions/newsagent/<TICKER>_<date>/FULL_[0-9].json.gz` | `results/newsagent_20261011/raw/sessions/<TICKER>_<date>/FULL_[0-9].json.gz` | 1,000 (250 days x k = 0..3) |

The other files in that folder (`FULL_T06_*`, `NO_NEWS_*`) are not read. Each of the 1,000 files was compared with
its workspace original by sha256: all 1,000 are byte-identical.

Combined digest of the 1,000 files: write one line `<sha256>  <path relative to data/mechanisms/sessions/newsagent>`
per file, sorted by path, then take the sha256 of the joined text (UTF-8):

    20849d7ab1483bd382176c54b6c6b2e8193f04249695b127c743681143759d1c

The six sessions quoted in `data.json` under `examples`:

| File (under `data/mechanisms/sessions/newsagent/`) | sha256 |
|---|---|
| `HAL_2026-03-20/FULL_1.json.gz` | `f7c6d7cc846e5962fead2f7b8f07ecf6bc810e1daf85a68d61e76521e31f73f4` |
| `HAL_2026-03-20/FULL_2.json.gz` | `2418d228c1f6d0ca2d5ec209bb5b59c8005705a980dc6d0b5d7ca3c656d5d6c6` |
| `STX_2026-06-17/FULL_1.json.gz` | `62b16e6abc0d945b858e1a06c80565b909872c4d2765110f988f5c360e61e99e` |
| `STX_2026-06-17/FULL_2.json.gz` | `246952dd4b1a37212d3ca8cf88448e01b5b1de81dbe9cced837e537f6495f2af` |
| `ACN_2026-03-24/FULL_3.json.gz` | `fbe6f2e6db1a8811f941013f51142a7c31873046b1c24dbb30e1f67422ad9860` |
| `AAPL_2026-03-19/FULL_1.json.gz` | `a60f842783711939b0d90e7743481126ea439601e97c3d8dc466a5b924b5ef7e` |

The step-3 claim that `get_volatility_stats` and `get_risk_budget` use the same 20-day formula is checked against
`src/finagent/harness/toolbox.py`, which is part of the repository.
