# Vendor data added on 2026-10-30

Scripts, checks and file hashes for the market, fundamentals and macro data bought or fetched on
2026-10-30 from Databento and Index One. **The data files themselves are not in this repository**: both
vendors license them for our own use only, so they cannot be redistributed. Anyone with their own
accounts can rebuild every table with the scripts here and check it against the hashes.

| Folder or file | What it holds |
|---|---|
| `scripts/` | download (`fetch_*.py`), assembly (`build_*.py`) and check (`verify_20261030.py`) scripts; API keys are read at run time from a local key file and are not stored anywhere |
| `verify_20261030.json` | cross-source checks: daily returns of each new price table against the project's existing daily panels, CIK agreement, filing-time coverage |
| `manifests/` | SHA-256 of every local file, folder by folder |
| `DATA_README.zh-CN.md` | the local data folder's description (Chinese): tables, row counts, checks, known issues |

Summary of the checks (share of stock-days whose daily returns differ by less than 0.2%):
1-minute bars vs the existing daily panel 98.05%; full-market daily 98.70%; Index One adjusted daily 99.92%
(stratos panel) and 99.84% (ext2017 panel); CIK 500 of 500 identical.
