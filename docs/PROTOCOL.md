# Protocol

The full design of the presentation pilot (workflow id `codexpilot_20261018`), which ran on 2026-10-18.
Each value below is a constant in [`setup/`](../setup) or in the code, or it is read from the shipped
records, and the file is named where that helps. The texts the models saw are in [`data/prompts/`](../data/prompts/README.md),
and the tools are in [TOOLS.md](TOOLS.md).

**Contents.** [Question](#question) · [Models](#models) · [Framework 1: the harness](#framework-1-the-harness) ·
[Framework 2: Codex CLI](#framework-2-codex-cli) · [Days](#days) · [Arms](#arms) · [Runs, seeds and order](#runs-seeds-and-order) ·
[Validity, audit and exclusion](#validity-audit-and-exclusion) · [Measures](#measures)

## Question

Does rewriting how the same price information is presented change an LLM trading agent's 5-day volatility
and return forecasts? Does the effect differ by model and by agent framework? The pilot is descriptive.
It fixes its measures before looking at the numbers, but it tests nothing: 6 days are too few for that.

## Models

Five models whose reasoning output is visible. Their settings are in [`setup/models.toml`](../setup/models.toml).

| Key | Model | Served by | Model id sent → reported | Harness request | Codex reasoning effort / context window |
|---|---|---|---|---|---|
| `qwen3_8b` | Qwen3-8B | our vLLM 0.29.0, `Qwen/Qwen3-8B` @ `b968826d` | `Qwen/Qwen3-8B` → same | temperature 1.0, top-p 0.95, a seed per turn, thinking on, 2,048 tokens per turn | `high` (the chat template ignores it) / 32,768 |
| `qwen35_9b` | Qwen3.5-9B | our vLLM 0.29.0, `Qwen/Qwen3.5-9B` @ `c2022362` | `Qwen/Qwen3.5-9B` → same | as Qwen3-8B, 2,048 tokens per turn | `high` (ignored by the template) / 65,536 |
| `qwen38_27b` | Qwen3.8-27B-FP8 | our vLLM 0.29.0, `Qwen/Qwen3.8-27B-FP8` @ `017b9c7a` | `Qwen/Qwen3.8-27B-FP8` → same | as Qwen3-8B, 8,192 tokens per turn; every raw answer kept | `xhigh` (the template rejects `high`) / 65,536 |
| `deepseek` | DeepSeek | `api.deepseek.com` | `deepseek-reasoner` → `deepseek-flash` | 8,192 tokens per turn; no temperature, top-p or seed | `high` / 1,000,000 |
| `kimi` | Kimi K3 | `api.moonshot.ai` | `kimi-k3` → same | 16,384 tokens per turn, `reasoning_effort` `high`, at most 4 requests in flight; no temperature (the API accepts only 1), top-p or seed | `high` / 1,048,576 |

- **Reasoning is passed back to DeepSeek and Kimi K3.** Each turn's `reasoning_content` is sent again on
  the assistant message that carries its tool calls. The vLLM history holds only the content and the tool calls.
- **The Qwen3.8-27B-FP8 cap was raised to 8,192.** Its harness smoke run at 2,048 had 2 of 5 turns cut,
  so the batch used 8,192 (`records/infra/logs/qwen38_log.txt`).
- **The pilot also ran Sonnet in both frameworks; it is excluded from this release because its reasoning is not visible.**
- The vLLM serve flags and weight hashes are in [ENVIRONMENT.md](ENVIRONMENT.md). The Qwen3.5-9B
  revision was not recorded at run time. It was identified afterwards from the hashes of the local files.

## Framework 1: the harness

Our multi-turn trading agent. It uses chat completions with 32 function tools
(`finagent.harness`).

**Messages.** Each session opens with two messages.

- **System:** [`data/prompts/harness_system.txt`](../data/prompts/harness_system.txt), 1,552 characters, sha256 `e992af5a…`.
  It covers the account rules and point-in-time information, sizing as a share of total assets,
  `submit_decision` with a target exposure, and the 5-day forecast (`p_up`, `expected_return_pct`,
  and `expected_vol_pct`, the one-standard-deviation 5-day move in percent, "not annualised and not a
  single-day figure").
- **User:** the day prompt (3,013 to 3,653 characters; [`data/prompts/examples/<day>/<ARM>/harness_prompt.txt`](../data/prompts/examples)).
  Its sections, in order:
  1. `Trading day <t> — <TK>`
  2. the close and the last 10 closes
  3. `ACCOUNT`: cash, shares, position value, total assets, position %, and the shares per point of exposure
  4. `COMPANY NEWS` (past 7 days, the 10 most recent headlines with their sources, published before D(t))
  5. fiscal and monetary policy news, and insider transactions (empty for these six stocks)
  6. `YOUR LAST 4 DECISIONS` (two in practice)
  7. the **PRICE TOOL READINGS** block in the arm's form ([Arms](#arms))
  8. `Decide today's action and call submit_decision.`

**Tools.** The 32 tool schemas ([`data/prompts/tools.json`](../data/prompts/tools.json), sha256 of
`json.dumps(tools, sort_keys=True)` = `32860efa…`) are sent with every request, with `tool_choice` `auto`.
Each tool sees only the stock's own data, through close t for bars and before D(t) for news.

**Loop** (`finagent.harness.session`, constants in `setup/experiment.toml [harness]`):

- **Turns.** At most 10 assistant turns. A turn that the token cap cuts without a tool call is sent
  again with the next seed, and it counts toward the 10.
- **Reminder.** The first turn without a tool call and without a decision gets the reminder
  ([`data/prompts/reminder.txt`](../data/prompts/reminder.txt)). If the loop ends without a decision and no reminder
  was used, one last reminder request follows, so a session makes at most 11 requests. No shipped run
  needed a reminder.
- **Tool results.** Each result is cut at 2,500 characters, after the arm rewrite.
- **Decision.** `submit_decision` is not executed. It is answered with
  `recorded: <Action> <n> @ <close> -> exposure <x>% of assets`, plus a hint when the order misses the
  stated target by more than 2 points. The session ends after the first turn whose calls are all
  `submit_decision`. The last submission is the decision, and its order is applied at the close after the
  session.
- **Starting state.** Each run is one session on day t, started from a fresh copy of the day's anchor
  state ([Days](#days)).

## Framework 2: Codex CLI

Codex CLI 0.162.1 (`codex exec --json`) works as a coding agent in a fresh point-in-time folder
(`finagent.coding`). It has no trading tools. It reads files and runs its own code.

**Workspace** `<WS_ROOT>/<12 random letters>/work`, with `home/` and `tmp/` beside it. The workspace and
`task.md` files are in [`data/prompts/examples/`](../data/prompts/examples):

| File | Content |
|---|---|
| `prices.csv` | `date,open,high,low,close,volume`: every daily bar from 2023-07-17 through close t, at day t's price level (689 to 783 rows) |
| `news.csv` | `time,headline,summary`: every company-news item published before D(t), oldest first (284 to 1,540 rows) |
| `account.json` | the `ACCOUNT` block and the last decisions as JSON |
| `task.md` | `ROLE AND RULES`, then the harness system prompt with its tool sentences rewritten for files and `decision.json` ([`data/prompts/coding_system.txt`](../data/prompts/coding_system.txt), sha256 `84691352…`), then the same day prompt with the same readings block, and finally the list of files, `HOW TO WORK` and the fields of `decision.json` (5,980 to 6,620 characters) |

The agent's only instruction is [`data/prompts/agent_prompt.txt`](../data/prompts/agent_prompt.txt): *"Your task is
described in task.md in the current folder. Read it and do it. Finish by writing decision.json in the
current folder."*

**Configuration.** Each run gets its own `CODEX_HOME`, holding only `config.toml`; a copy is in every run
folder. Its settings:

- the model and its context window, and `model_reasoning_effort` ([Models](#models));
- `approval_policy = "never"`, `web_search = "disabled"`, `show_raw_agent_reasoning = true`;
- sub-agents, goals, plugins, apps, image, browser and computer tools, shell snapshots, bundled skills
  and analytics all off;
- a provider `cxp` with `wire_api = "responses"`, pointing at the model's local relay with the run's
  `X-Cxp-Run` header;
- a shell environment of exactly `PATH`, `HOME`, `TMPDIR` and `LANG=C.UTF-8`.

`include_permissions_instructions = false`. In its place, the developer instructions are
[`data/prompts/permissions.txt`](../data/prompts/permissions.txt), Codex's own workspace-write text, which states
the policy that is actually enforced.

**Sandbox and logging.** The command is `strace -f … sandbox.py --write work home tmp CODEX_HOME --connect-port <relay> -- codex exec --json --skip-git-repo-check -C <work> "<agent prompt>"`.

- **What the sandbox allows.** `sandbox.py` uses Landlock ABI 4 and seccomp. It allows writes only in
  those four folders and TCP only to the relay. It blocks UDP, raw sockets and `io_uring`. Reads are
  allowed everywhere.
- **Why Codex runs with `sandbox_mode = "danger-full-access"`.** Codex's own bubblewrap sandbox cannot
  start on the host, so Codex runs in that mode inside `sandbox.py`.
- **What is logged.** strace covers exec, open, chdir, connect, bind, clone and fork.
- **The relay** (`finagent.coding.relay`) forwards bodies byte for byte to the vLLM server or the API,
  adds the API key, and logs every request.
- **Limits.** A run has a 1,800 s wall cap and no turn limit.

**What Codex itself sends** (all 1,009 request bodies in the records):

- its built-in instructions;
- the permissions text;
- an `<environment_context>` with the working folder, the run date 2026-10-18, the host's time zone
  `Asia/Hong_Kong`, and a permission profile reading "disabled / unrestricted";
- the agent prompt;
- its four fallback tools `exec_command`, `write_stdin`, `request_user_input` and `view_image`.

No request carries a temperature, a top-p, an output cap or a seed. Server defaults apply.

**Decision.** `decision.json` is read with `json.loads`. If that fails, the first `{…}` in the file is
used and the record notes the extraction. The validity rule is the same as in the harness.

## Days

Six decision days t (`data/days.json`, rebuilt by `finagent days`).

- **Candidates.** The candidates are the 250 days of the registered anchor-stage sample
  (`data/selection/s1_spec.json`) that have a registered readings block and valid anchor sessions: 13
  big-move days and 184 ordinary ones.
- **Day type.** z is the day's 1-day log return divided by the prior daily sd, exp(lsig)/√5, using
  information through close t only. A day with |z| ≥ 2 is big-move, and one with |z| < 1 is ordinary.
- **The draw.** Each group is sorted by day id and permuted with `numpy.random.default_rng(20261018)`:
  big-move days first, then ordinary, with one generator. A ticker or date already taken is skipped.
- **Decision time.** D(t) is 09:00 New York time on the next trading day. News published before D(t)
  is visible.

| Day | Type | t | D(t) | z | 1-day return | Start: cash, shares | Prior 5-day sd | Realised 5-day vol | Realised 5-day return |
|---|---|---|---|---:|---:|---|---:|---:|---:|
| `MCHP_2026-08-07` | big | 2026-08-07 | 2026-08-10 09:00 | +3.34 | +13.01% | 94,798.36, 67 | 8.72% | 5.33% | −6.52% |
| `HOOD_2026-04-14` | big | 2026-04-14 | 2026-04-15 09:00 | +2.16 | +9.85% | 70,707.83, 423 | 10.19% | 12.15% | +9.28% |
| `CRWD_2026-08-27` | big | 2026-08-27 | 2026-08-28 09:00 | +4.62 | +18.65% | 70,335.40, 160 | 9.03% | 12.74% | −5.70% |
| `VST_2026-05-06` | ordinary | 2026-05-06 | 2026-05-07 09:00 | −0.51 | −1.31% | 61,931.86, 237 | 5.79% | 7.34% | −9.91% |
| `CB_2026-04-22` | ordinary | 2026-04-22 | 2026-04-23 09:00 | −0.87 | −1.18% | 99,015.20, 3 | 3.02% | 3.82% | +0.10% |
| `MRK_2026-05-07` | ordinary | 2026-05-07 | 2026-05-08 09:00 | −0.54 | −1.12% | 94,944.60, 45 | 4.67% | 1.60% | +0.99% |

The z, return and prior values come from `data/days.json`, the realised outcomes from `results/describe.json`,
and the start values from `data/prompts/examples/<day>/account.json`.

**Anchor state.** Each day starts from the book that Qwen3-8B built in two anchor sessions on days t-2
and t-1, starting with 100,000 in cash (`data/anchors/<day_id>.json.gz`, hashes in `days.json`). This
state supplies the account and the last two decisions shown in the prompt. Each run starts from a fresh
copy.

**Realised outcomes**, which no agent ever sees, come from the price panel: the 5-day log return and
√(Σ squared daily log returns over t+1 … t+5), in percent (`finagent.data.outcomes`).

## Arms

The same seven readings (`finagent.readings.BLOCK_CALLS`) are shown in four forms (`finagent.arms`):
`get_trend_signal`, `get_rsi` (period 14), `get_mean_reversion_signal`, `get_macd`, `get_price_stats`,
`get_support_resistance` and `get_volatility_stats`.

| Arm | Runs per day | Rewrite | Block lines changed |
|---|---:|---|---:|
| ORIG | 2 (k = 0, 1) | none: the registered block (`data/selection/grounding_blocks.json`) | 0 of 7 |
| NOLABEL | 1 | delete the categorical labels and keep every number: `signal` of trend, RSI and mean reversion, `cross` of MACD, `regime` of volatility | 5 of 7 |
| UNIT5D | 1 | `get_volatility_stats` only: the four annualised fields are replaced in place by value × √(5/252), rounded to one decimal, under new names (`vol_5d_equiv_from_{10d,20d,60d}_pct`, `parkinson_vol_5d_equiv_from_10d_pct`) | 1 of 7 |
| PLACEBO | 1 | the keys of every reading in a fixed shuffled order (`default_rng(20261018 + crc32(tool name))`, never the original order); values untouched | 7 of 7 |

The volatility line of `VST_2026-05-06` in each arm:

```
ORIG     {"ann_vol_10d_pct": 45.0, "ann_vol_20d_pct": 39.4, "ann_vol_60d_pct": 47.8, "parkinson_vol_10d_pct": 39.0, "atr_14": 6.56, …, "regime": "low", …}
NOLABEL  {"ann_vol_10d_pct": 45.0, "ann_vol_20d_pct": 39.4, "ann_vol_60d_pct": 47.8, "parkinson_vol_10d_pct": 39.0, "atr_14": 6.56, …}
UNIT5D   {"vol_5d_equiv_from_10d_pct": 6.3, "vol_5d_equiv_from_20d_pct": 5.5, "vol_5d_equiv_from_60d_pct": 6.7, "parkinson_vol_5d_equiv_from_10d_pct": 5.5, …}
PLACEBO  {"note": …, "vol_zscore_vs_63d": -1.08, "parkinson_vol_10d_pct": 39.0, "atr_14_pct_of_price": 4.15, "ann_vol_20d_pct": 39.4, "regime": "low", …}
```

**Where the rewrite applies.**

- **The prompt's readings block,** in both frameworks.
- **In the harness, the output of every call to one of the seven tools,** whatever its arguments, before
  the 2,500-character cut. Outputs that are not JSON objects, or that hold an `"error"`, are left alone.
- **In Codex,** only the block in `task.md`. `prices.csv` is the same in every arm, so an agent can
  compute any reading itself.

Of the 20 block-tool calls in the 150 harness sessions, 8 were rewritten: 7 by DeepSeek, 1 by Kimi K3
(`results/pilot_counts.json`).

**What no arm touches:**

- tool descriptions (the `get_volatility_stats` schema still says "Annualised");
- `get_risk_budget`'s `trailing_vol_20d_pct`, which is annualised;
- the `signal` of `get_volume_analysis` and `get_insider_summary`;
- `prices.csv` and `news.csv`.

**The CPU check.** `finagent verify` re-runs the rewrite check: 456 checks with 0 problems. Re-serialising
the ORIG outputs is byte-identical, and each arm changes exactly what is listed above.

## Runs, seeds and order

- **Runs.** model × framework × day × arm × k gives 30 runs per model and framework, and 300 in all.
  Run ids are `<model>__<framework>__<day_id>__<arm>__<k>`; the agent never sees them.
- **Seed.** The seed is `branch_seed_base` of the day + 600 + 10 × arm index + k, with ORIG 0, NOLABEL 1,
  UNIT5D 2 and PLACEBO 3. Only vLLM requests use it: turn n sends seed + 1000·n, and the final reminder
  sends seed + 99. API requests and every Codex request carry no seed.
- **Order and concurrency** (`setup/experiment.toml [concurrency]`). The run list goes model →
  framework → day → arm → k. Harness batches run 30 runs in flight on vLLM, 10 for DeepSeek and 4 for
  Kimi K3. Codex batches run 6, or 4 for Kimi K3. The API models ran one after another in a background
  thread while the local models were served one after another. A model's two batches ran side by side,
  except Qwen3.8-27B-FP8 and Kimi K3 (harness first).

What ran when, on 2026-10-18 (`records/infra/logs/`):

| Time | Batch |
|---|---|
| 14:37 to 14:46, 20:14 to 20:16 | smoke stage: one ORIG run per model and framework on VST (`records/archives/smoke.tar.xz`) |
| 14:54 to 14:57 | Qwen3-8B harness (30 runs, 178 s); Qwen3-8B Codex stopped at 14:56 after 6 runs (relay-start race) |
| 14:55 to 14:59 | DeepSeek harness (79 s) and Codex (223 s) |
| 14:59 to 15:26 | Qwen3.5-9B harness (559 s) and Codex (1,619 s) |
| 15:28 to 15:33 | Qwen3-8B Codex, the 24 remaining runs (298 s) |
| 20:17 to 20:32 | Kimi K3 harness (318 s), then Codex (590 s) |
| 20:24 to 20:31 | Qwen3.8-27B-FP8 smoke runs at 2,048 tokens per turn |
| 20:33 to 21:40 | Qwen3.8-27B-FP8 harness (911 s), then Codex (3,141 s) |

## Validity, audit and exclusion

**Valid decision** (`finagent.records.parse_decision`). The decision is valid when `expected_vol_pct` is
a number above 0 and `expected_return_pct` is a number. Strings such as `"3.5%"` are accepted.

**Leakage audit** of every Codex run (`finagent.coding.audit`). It reads the strace of the whole process
tree, the `--json` events, the sandbox log and the relay log. A run is flagged if a model command does any
of the following:

- **path:** opens or executes a path outside its workspace, home, tmp, `CODEX_HOME`, the agent's Python
  environment and the system folders;
- **network:** attempts a connect or bind on an IP socket, uses a network client or URL, or calls the
  relay without the run header;
- **date:** touches a date after t: in a path or URL, as a news timestamp at or after D(t) in its output,
  or as a price row dated after t.

Harness runs are never flagged. Their tools serve only point-in-time data, and every news item they hand
out is logged (`session.json.gz` `cache_log`).

**Exclusion rule** (fixed before the runs). A run is usable when its decision is valid and the audit did
not flag it. As a sensitivity check (`results/describe_tables.md`, sensitivity A), the 7 runs flagged only
for running Codex's own bundled `rg` are re-admitted.

| Cell | Invalid | Flagged | Usable |
|---|---:|---:|---:|
| Qwen3-8B / Codex | 3 (2 without `decision.json`, 1 not JSON) | 1 (bundled `rg`) | 26 |
| Qwen3.5-9B / Codex | 1 | 0 | 29 |
| Qwen3.8-27B-FP8 / Codex | 0 | 2 (a failed open of `/tmp/analyze.py`) | 28 |
| DeepSeek / Codex | 0 | 7 (6 bundled `rg`, 1 failed open of `/tmp/analyze.py`) | 23 |
| Kimi K3 / Codex | 0 | 0 | 30 |
| every harness cell | 0 | 0 | 30 |

286 of 300 runs are usable. No run timed out or failed (`results/pilot_counts.json`). The audit canary,
a DeepSeek coding run told to break each rule, is flagged on path, project folders, network and date, and
its outside write was blocked (`records/infra/checks/audit_canary.json`).

## Measures

These were fixed before the numbers were looked at. They are stated in full in `results/describe.json`
`definitions` and at the end of [`results/describe_reasoning_models.md`](../results/describe_reasoning_models.md).
Volatility is compared in logs: ln(`expected_vol_pct`).

**Shifts and noise**

| Measure | Definition |
|---|---|
| ORIG noise | per day with both ORIG runs usable, \|ln(vol₀ / vol₁)\| (and \|ret₀ − ret₁\| for the return), averaged over days |
| σ² | mean((o₀ − o₁)²) / 2 over the ORIG pairs of the cell |
| arm shift | per day, the arm run minus the mean of that day's usable ORIG runs, averaged over days; SE = √(1.5 σ² / n) |
| shift minus PLACEBO | per day with a usable ORIG run, arm run and PLACEBO run: arm − PLACEBO, averaged over days; SE = √(2 σ² / n) |
| 2 SE mark (\*) | \|mean\| > 2 SE; crude, with σ from 4 to 6 pairs |

**Annualised figures**

| Measure | Definition |
|---|---|
| A | the day's four annualised readings in the ORIG block: `ann_vol_10d_pct`, `ann_vol_20d_pct`, `ann_vol_60d_pct`, `parkinson_vol_10d_pct` |
| pasted, strict | `expected_vol_pct` lies in [0.9 min A, 1.1 max A] |
| pasted, broad | `expected_vol_pct` > median(A) · (5/252)^¼, which is closer in log to the annual scale than to the 5-day scale |
| reasoning output | the provider's reasoning field only, never the final answer: each turn's `reasoning` / `reasoning_content` in the harness, and the reasoning items of the relay's raw streams in Codex (Kimi K3 returns summary text there) |
| mention, exact | the reasoning contains one of the four values of A as written, as a standalone number |
| mention, any | exact, or a standalone number in the strict range with an annual keyword in the 60 characters before it (the primary rule) |
| still submits | among runs that mention an annualised figure, the share whose final forecast is pasted |

**Accuracy and work**

| Measure | Definition |
|---|---|
| accuracy | e = ln(`expected_vol_pct` / realised 5-day vol); mean \|e\| and the bias (mean e) over usable runs; SE = sd of the 6 day means / √6 |
| baselines | (a) the readings' `ann_vol_20d_pct` × √(5/252); (b) the S1 rational prior sigma5 = exp(lsig) from `days.json` |
| computed a vol | Codex only: the run's commands mention python, `prices.csv` and a dispersion function (std, var, stdev) |
| tool calls | mean `n_tool_calls` over finished runs: harness tool calls including `submit_decision`; Codex commands, file changes and other tool items |
