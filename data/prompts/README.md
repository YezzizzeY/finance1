# prompts/

Every text the models saw, written by `finagent prompts` from `data/` (`finagent prompts --check` confirms the files are exact).
Files hold the text byte for byte, so `sha256sum` gives the hashes listed in `docs/` and checked by `finagent verify`.

| file | what it is |
|---|---|
| `harness_system.txt` | system prompt of the harness (sha256 `e992af5a…`) |
| `tools.json` | the 32 tool schemas sent with every harness request (sha256 of `json.dumps(tools, sort_keys=True)`: `32860efa…`) |
| `reminder.txt` | user message sent once if the harness model stops without `submit_decision` |
| `coding_system.txt` | the system text as rewritten for the coding agent (top of every `task.md`, sha256 `84691352…`) |
| `agent_prompt.txt` | the coding agent's only instruction (the `codex exec` prompt) |
| `permissions.txt` | Codex developer instructions describing the sandbox |
| `examples/<day>/{prices.csv,news.csv,account.json}` | the coding workspace files of the day (identical in every arm) |
| `examples/<day>/<ARM>/harness_prompt.txt` | first user message of a harness run (readings block in the arm's form) |
| `examples/<day>/<ARM>/task.md` | `task.md` of a coding-agent run |

Arms: `ORIG` (unchanged readings), `NOLABEL` (categorical labels removed), `UNIT5D` (annualised volatility shown as 5-day
equivalents), `PLACEBO` (keys reordered). Days: 3 big-move (`MCHP_2026-08-07`, `HOOD_2026-04-14`, `CRWD_2026-08-27`) and
3 ordinary (`VST_2026-05-06`, `CB_2026-04-22`, `MRK_2026-05-07`).
