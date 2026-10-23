# Limitations

What the pilot can and cannot show, and where the release departs from an ideal reproduction. Each item
names its evidence. [REPRODUCING § Expected differences](REPRODUCING.md#expected-differences) gives the
practical side of the reproduction items.

## Design and analysis

- **The pilot is small.**
  - It covers 6 days (3 big-move, 3 ordinary), with one run per edit arm per day and two ORIG runs.
  - Each cell's noise σ comes from 4 to 6 ORIG pairs, and a shift is marked when it exceeds 2 SE.
  - Of the 40 edit-minus-PLACEBO comparisons, 6 carry the mark. Some marks are expected by chance, and none
    is corrected for multiple comparisons. The results page calls none of them a result.
- **The placebo moves the forecasts too.** In Qwen3.8-27B-FP8 / harness, all three edits, the placebo
  included, raise ln(vol) by 0.11 to 0.15 against ORIG, and DeepSeek / harness has a placebo shift of
  +0.13. Comparing with ORIG alone would therefore mistake a generic change of text for an effect of the
  edit (`results/describe_reasoning_models.md`, note 4).
- **One trading day per run.** A run is a single session on day t, started from the book that Qwen3-8B
  built on days t-2 and t-1 (`data/anchors/`). There is no multi-day episode, and the order is not
  followed up.
- **The mention rule is text matching on the reasoning field.**
  - The exact rule is a lower bound.
  - The "any" rule also counts rounded quotes and the model's own annualised computations.
  - A missing mention can mean that the model did not write its thinking out. This matters most for
    Kimi K3, whose reasoning averages 1,864 characters per run in the harness and 3,574 in Codex
    (DeepSeek: 7,976 and 9,610).
  - Kimi K3's Codex reasoning arrives as summary text from Moonshot's Responses API.
- **The accuracy comparison covers 6 days.** The two baselines are scored on the same days, and the SE
  over days (0.08 to 0.15 for the three larger models) is larger than most differences between cells.

## Settings that differ between rows

The arm shifts are measured within one model and framework, so these differences do not bias them. They
do make comparisons across rows harder (`setup/models.toml`).

- **Harness token caps per turn.**
  - Qwen3-8B and Qwen3.5-9B had 2,048 tokens, and the cap cut 7 of 37 and 14 of 47 of their requests.
  - Qwen3.8-27B-FP8 and DeepSeek had 8,192, and Kimi K3 had 16,384; none of their requests was cut
    (`results/pilot_counts.json`).
- **Reasoning effort.**
  - Kimi K3 was sent `high` in both frameworks. Moonshot's chat-completions endpoint may ignore that
    field, in which case the harness ran at Kimi's default. `records/infra/probes/kimi_probe_effort.json`
    shows the reasoning tokens changing with the effort setting, but the probe does not record which
    endpoint it used.
  - Qwen3.8-27B-FP8 ran at `xhigh` in Codex, because its chat template rejects `high`. The Qwen3-8B and
    Qwen3.5-9B templates ignore the field.
- **Codex sampling.** Codex sends no temperature, top-p, output cap or seed (1,009 of 1,009 request
  bodies). Each server's defaults therefore apply, and they differ: Qwen3.8-27B-FP8 uses its own
  generation config (temperature 1.0, top-p 0.95, top-k 20), and Qwen3-8B runs with vLLM's defaults
  (`--generation-config vllm`).
- **Codex knows none of these models.** Every coding run logged "Model metadata for `<model>` not found.
  Defaulting to fallback metadata". Codex then offers its fallback tools (`exec_command`, `write_stdin`,
  `request_user_input`, `view_image`). Its built-in instructions still mention `apply_patch`, which is not
  among them. For the Qwen models, vLLM converts Codex's developer messages to system messages
  (`records/infra/serve/`). Not checked: whether vLLM renders the reasoning items that Codex sends back
  into the Qwen prompts.
- **Context windows.** The Codex window is 32,768 tokens for Qwen3-8B, 65,536 for the other two local
  models, and about 1 M for the two API models.

## Reproduction

- **Reruns are not byte-identical.** vLLM batches requests with prefix caching on. The API calls carry
  no seed. `deepseek-reasoner` is an alias that the API resolved to `deepseek-flash`, and it may change.
- **Codex's request text depends on the host.** Every request carries the random working folder, the
  run date (2026-10-18) and the host's time zone (`Asia/Hong_Kong`), as well as a new installation id
  per run. All 1,009 request bodies contain the date and the time zone.
- **Serving changed within one cell.** Six Qwen3-8B Codex runs ran on the first server (GPU 2,
  utilisation 0.54), alongside the Qwen3-8B harness batch. The other 24 were rerun on a second server
  (GPU 0, utilisation 0.94), after the relay-start race of the first batch
  (`records/infra/logs/pilot_log.txt`, `results/pilot_counts.json` `gpu`).
- **The Qwen3.5-9B weights revision was not recorded at run time.** It was identified afterwards: all 16
  local files match `c2022362…` ([ENVIRONMENT.md](ENVIRONMENT.md)). This model was also served without
  `HF_HUB_OFFLINE`.
- **The relay code changed between batches.** From the Kimi K3 batch on, the relay log has a
  `client_closed_early` field (120 of 195 Kimi rows). The logs of the earlier relays have no such field
  (`records/infra/relay/`). This release does not test whether the change affected what an agent received.
- **Two build checks have no shipped generator.** `harness_wrapper_check.json` was written by an ad-hoc
  script that was not saved. The canary run was started by hand, because the original code had no
  command for it; it can now be made with `finagent smoke --canary`. The script behind the two Kimi
  effort probes is also missing.
- **Some log counts include the excluded model.** The `summary:` and `smoke stage:` lines of
  `records/infra/logs/` still count its runs ([records/README.md](../records/README.md)).

## Information available to the agents

- **The sandbox allows reads everywhere.** Landlock blocks writes outside the run's folders and every
  connection except the relay, but reads stay allowed (`records/infra/checks/build_check.json`:
  `read_outside: allowed`). On the original host, a coding agent could therefore have read any file. The
  audit flags every such access instead. The 10 flagged runs are excluded:
  - 7 ran Codex's bundled `rg`, which Codex puts on the command `PATH`;
  - 3 tried to open `/tmp/analyze.py`, and the open failed.

  Apart from these, the audit found no access outside the run's folders and the system directories.
- **Agents see two statements of the sandbox.** Our developer text says workspace-write with restricted
  network. Codex's own `<environment_context>` reports the permission profile as "disabled" with an
  "unrestricted" file system. The enforced policy is ours.
- **The agent's `PATH` includes the host's `/usr/local/bin:/usr/bin:/bin`.** Host tools and the system
  `python3` are reachable next to the agent's numpy/pandas environment.
- **Harness tools are point-in-time by construction and are not traced.** The news items they hand out
  are logged per session (`cache_log`).
  - The one way a harness tool reaches past t is the earnings calendar's AAPL default. On the HOOD and
    CB days, it counts trading dates up to AAPL's next report (12 and 6). That reveals bar dates, not
    prices.
  - All 108 earnings-tool calls in the shipped runs passed the stock's own ticker ([TOOLS.md](TOOLS.md#quirks)).
- **UNIT5D does not remove every annual number from the harness.** `get_risk_budget` reports the
  annualised 20-day vol, and the `get_volatility_stats` description says "Annualised" in every arm.
  DeepSeek, Qwen3.8-27B-FP8 and Kimi K3 still mention an annualised figure in 6, 5 and 1 of their 6
  UNIT5D harness runs.
- **The memory and calibration tools score a 1-day move** for a 5-day forecast. Their verdicts, for
  example "you overstate volatility", are based on the two anchor decisions.
- **Prices are vendor-adjusted.** The bars are split- and dividend-adjusted as of 2026-09-24. The cache
  undoes later splits but not later dividends, so day t's levels can differ slightly from the levels
  quoted that day ([PROVENANCE.md](PROVENANCE.md#prices)).

## Data and release

- **No license for the shipped prices and news.** The price dataset states no license, and no license
  is held for the news text. Both are shipped only for exact non-commercial reproduction. Finnhub's free
  tier no longer returns part of the news ([DATA_LICENSE.md](../DATA_LICENSE.md)).
- **The records keep the original host's paths and identifiers.** They are part of what the agents
  saw, so they are not rewritten ([records/README.md](../records/README.md)).
- **The results page is fixed text.** Its notes and excerpts were written from the numbers and are kept
  verbatim, so they still name the original module paths, and they refer to the original
  `pilot_report.md` (and its note C2), which is not shipped. `finagent analyze` rebuilds this page from
  the shipped records only. It needs all ten cells and checks every excerpt against them. New runs get
  the same measures, without the page, from `finagent analyze --raw <runs> --out <folder>`.
