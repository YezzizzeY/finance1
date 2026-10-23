# Reproducing

There are four levels. L0 to L2 need only this repository and a CPU. They tie every shipped byte to the
code and recompute every reported number. L3 reruns the experiment and needs a prepared host.

| Level | Command | Expected output | Time |
|---|---|---|---|
| L0 | `finagent verify --level L0` | `10 of 10 checks passed (L0)` | ~15 s |
| L1 | `finagent unpack` then `finagent verify --level L1` | `4443 of 4443 files … match`, `11 of 11 checks passed (L1)` | ~10 s + ~12 s |
| L2 | `finagent verify --level L2` | `2 of 2 checks passed (L2)` | ~6 s |
| L3 | `finagent run --model <key> --framework <framework>` | 30 new run folders in `runs/pilot/raw/` | 1 min to 1 h per cell in the pilot |

The times were measured on the original host (2 × Xeon Platinum 8352V); L0 to L2 use no GPU.

**Contents.** [Install](#install) · [L0](#l0-the-repository) · [L1](#l1-records-and-results) · [L2](#l2-the-audit) ·
[L3](#l3-new-runs) · [Expected differences](#expected-differences)

## Install

You need Python 3.12 with its `venv` module (on Ubuntu 24.04: `sudo apt install python3.12-venv`) and
about 0.5 GB of disk for the unpacked records. From the repository root:

```sh
python3.12 -m venv .venv && source .venv/bin/activate
pip install -r setup/requirements/runner.txt -e ".[test]"     # or: make setup
```

`setup/requirements/runner.txt` pins the exact versions of the environment that ran the pilot. The install must
be editable, because `finagent` finds `data/`, `records/` and `results/` relative to the checkout. With
access to PyPI, the install takes about 25 s. `finagent --help` lists the ten commands, and
`finagent <command> --help` shows the options of each.

## L0: the repository

```sh
finagent verify --level L0
```

| Check | What is compared |
|---|---|
| data files | the 937 files of `data/` against `data/MANIFEST.sha256` (307 are the pilot's own six tickers; 630 more are the 90 extra `evidence_relations/` tickers, hashed by this same check even though the pilot itself never reads them) |
| record archives | the 11 archives, `runs.jsonl` and `infra/` against `records/SHA256SUMS` (60 files) |
| prompt texts | the 5 fixed texts and the 32 tool schemas against the original hashes (system `e992af5a`, coding system `84691352`, tools `32860efa`) |
| example prompts | the 66 workspace files and day prompts (6 days × 4 arms), rebuilt from `data/`, against the original hashes |
| prompts folder | the 72 files in `data/prompts/` against `finagent prompts` |
| grounding sessions | the ORIG system and day prompts against the first turn of 6 earlier saved sessions |
| readings blocks | the 6 readings blocks recomputed from the bars against the registered ones, and their 24 arm forms |
| day selection | the draw rebuilt from `data/selection/` and `data/anchors/` against `data/days.json` |
| arm rewrites | 456 rewrite checks, each row against `records/infra/checks/rewrite_check.json` |
| golden tool outputs | 1,896 tool calls, 24 stateful sequences and 60 `submit_decision` replies against outputs recorded from the original code (`tests/fixtures/`) |

You can also check the hashes without `finagent`:

```sh
(cd data && sha256sum -c --quiet MANIFEST.sha256)
(cd records && sha256sum -c --quiet SHA256SUMS)
```

## L1: records and results

```sh
finagent unpack                 # 11 archives -> records/raw/, then 4443 of 4443 files against records/MEMBERS.sha256
finagent verify --level L1
finagent analyze --check        # "same" for each of the 6 files in results/
```

| Check | What is compared |
|---|---|
| unpacked files | the 4,443 files in `records/raw/` against `records/MEMBERS.sha256` |
| record index | each of the 300 lines of `runs.jsonl` against its run folder's `record.json` |
| run plan | the 300 planned runs (model, framework, day, arm, k, seed) against the records, and each record's served model name against `model_reported` in `setup/models.toml` |
| records rebuilt | every record rebuilt from the raw logs by the code that wrote it, every field and its order: harness runs from `session.json.gz`, coding runs from `decision.json`, `events.jsonl`, the relay log and the workspace |
| coding workspaces | the 600 given files (`task.md`, `prices.csv`, `news.csv`, `account.json`) against the rebuilt ones |
| realised outcomes | the 5-day return and realised variance of the 150 harness records, recomputed from the price panel |
| harness replay | the recorded tool calls of all 150 sessions, run through the toolbox: 810 tool and submit results, prompts, news-cache logs and arm counters |
| codex configs | the 150 `codex_config.toml` files, regenerated from the records and `setup/host.recorded.env` |
| codex commands | the 150 sandbox and `codex exec` command lines (write roots, relay port, log path, prompt) and the size of the agent's environment, regenerated the same way, against the first `execve` in each `strace.txt` |
| analysis outputs | the 6 files in `results/`, recomputed byte for byte |
| figures | the 5 charts in `results/figures/`, redrawn byte for byte |

`finagent analyze` writes `results/`, and `finagent figures` redraws the charts from it.
[`results/README.md`](../results/README.md) explains each output.

## L2: the audit

```sh
finagent verify --level L2
finagent audit                  # = make audit
```

The audit is re-run on all 150 coding-agent runs, and their flag, reasons and counts must be identical
(10 flagged: DeepSeek 7, Qwen3.8-27B 2, Qwen3-8B 1). It is also re-run on the 11 smoke-stage runs, which
include the canary. `finagent audit` prints one row per model, then `150 of 150 verdicts identical`.

The audit judges paths, so it must use the original host's folders: for the shipped records (`records/raw`
and the smoke folders in it) both commands read `setup/host.recorded.env`. For other run folders
`finagent audit` uses `FINAGENT_HOST_ENV`, or `--host-env FILE`.

Everything at once: `make verify` unpacks the records first if needed and prints
`23 of 23 checks passed (L0, L1, L2)`. `make test` runs every check as a test (`pytest -q`), with the
golden-fixture unit tests, in about 45 s.

## L3: new runs

### Host requirements

| Need | Why | Pilot host |
|---|---|---|
| Linux x86_64, kernel ≥ 6.7 with Landlock ABI 4 | the coding-agent sandbox (writes and TCP rules) | Ubuntu 24.04.4, kernel 6.8.0 |
| `strace`, with `kernel.yama.ptrace_scope` ≤ 1 | the audit's trace of every coding run | strace 6.8 |
| libseccomp (`libseccomp.so.2`) and a system Python 3.12 | `sandbox.py` (standard library and ctypes only) | libseccomp2 2.5.5, `/usr/bin/python3` 3.12.3 |
| Python 3.12 | the runner, and the agent's own environment | 3.12.3 |
| NVIDIA GPU, about 48 GB, and a driver for CUDA 13 (torch 2.13.0 in `setup/requirements/vllm.txt` uses CUDA 13 wheels) | the three local models; Qwen3.8-27B-FP8 waits for 38,912 MiB free | RTX A6000, 49,140 MiB, driver 590.48.01 |
| Disk: about 67 GB of weights (16.40 + 19.33 + 30.89 GB), plus the vLLM environment (several GB) and the Codex download (163 MB) | local models, Codex | – |
| Ubuntu packages: `python3.12-venv`, `strace`, `libseccomp2`, `curl` | the venvs, the trace, the sandbox, `install_codex.sh` | – |
| `DEEPSEEK_API_KEY`, `MOONSHOT_API_KEY` | the two API models | – |

Versions and hashes of everything are in [ENVIRONMENT.md](ENVIRONMENT.md).

### 1. Host settings

```sh
cp setup/host.example.env ~/finagent-host.env      # edit the paths, ports and GPU
export FINAGENT_HOST_ENV=~/finagent-host.env
```

| Key | Meaning |
|---|---|
| `WS_ROOT` | parent of the per-run folders `<WS_ROOT>/<12 letters>/work`. The agent sees this path as its working folder, so keep it short and neutral |
| `AGENT_PYENV`, `AGENT_PATH` | the agent's Python environment and its `PATH`. The pilot's `PATH` also held `/usr/local/bin:/usr/bin:/bin` |
| `CODEX_PACKAGE_DIR`, `CODEX_BIN` | where `install_codex.sh` unpacks Codex 0.162.1, and its binary |
| `CODEX_HOME_ROOT` | one `CODEX_HOME` per run, under `runs/<rid>/` |
| `SANDBOX_PYTHON`, `RUNNER_PYTHON` | the interpreter of `sandbox.py` (system Python) and of the relay (empty: the current interpreter) |
| `PRIVATE_ROOT` | folders the audit counts separately as "project folders" when an agent opens a path in them |
| `VLLM_ENV`, `MODEL_DIR`, `VLLM_CACHE_DIR`, `VLLM_SHORT_TMP` | the vLLM environment, the weights, the caches, and a short TMPDIR (vLLM's socket path must stay under 107 bytes) |
| `GPU`, `GPU_UTIL` | empty: the card with the most free memory, with utilisation from its free memory |
| `VLLM_PORT_*`, `RELAY_PORT_*` | 127.0.0.1 ports of the vLLM servers (18580 to 18582) and the relays (18590 to 18595) |

An environment variable `FINAGENT_<KEY>` (for example `FINAGENT_GPU=1`) overrides key `<KEY>` of the file.
API keys are never read from it.

### 2. Environments, Codex and weights

```sh
setup/scripts/setup_runner_env.sh              # .venv with setup/requirements/runner.txt + this package; strace, libseccomp, sandbox self-test
setup/scripts/setup_agent_env.sh               # AGENT_PYENV: numpy 2.5.4 and pandas 3.0.6 only (setup/requirements/agent-env.txt)
setup/scripts/install_codex.sh                 # Codex 0.162.1 (musl build); checks the release archive and bin/codex sha256
setup/scripts/setup_vllm_env.sh                # VLLM_ENV: the 203 pinned distributions of setup/requirements/vllm.txt (vllm 0.29.0)
setup/scripts/download_weights.sh qwen3_8b     # HF repo @ revision from setup/models.toml, then every file against setup/weights/
setup/scripts/download_weights.sh qwen35_9b
setup/scripts/download_weights.sh qwen38_27b
export DEEPSEEK_API_KEY=… MOONSHOT_API_KEY=…
```

The sandbox self-test in `setup_runner_env.sh` must report `"pass": true`. Writes outside the workspace,
TCP, UDP and DNS must be blocked, and a write inside must work.

Keys stay in the environment of the runner and the relay. The agent's commands never see them, the
vLLM server gets an allow-listed environment without them, and no log records them. If the host uses a
proxy, `no_proxy` must include `127.0.0.1`. The relay ignores proxy settings, so the coding-agent cells of
DeepSeek and Kimi K3 need direct HTTPS access to `api.deepseek.com` and `api.moonshot.ai` (their harness
cells go through the proxy).

### 3. Dry run, smoke runs, canary

```sh
finagent run --model all --dry-run            # plan of the 300 runs, their inputs in runs/pilot/dry_run/<run_id>/, host checks
finagent smoke --model kimi                   # one run per framework into runs/smoke/raw
finagent smoke --model kimi --canary          # the audit canary: must be flagged on path, network and date
```

A dry run contacts nothing.

- **Harness runs:** it writes `system.txt`, `prompt.txt` and `settings.json` (endpoint, request settings,
  seed).
- **Coding runs:** it writes `workspace/`, `codex_config.toml` and `command.json` (the exact command line
  and environment).
- **Host checks:** each line reads `ok` or `MISSING`.

The prompts and workspace files equal `data/prompts/examples/` byte for byte, for example
`diff runs/pilot/dry_run/kimi__harness__VST_2026-05-06__UNIT5D__0/prompt.txt data/prompts/examples/VST_2026-05-06/UNIT5D/harness_prompt.txt`.

### 4. Run the cells

```sh
finagent run --model <key> --framework harness|coding_agent [--days …] [--arms …]
finagent run --model all                      # the whole pilot, in the pilot's order
```

- **Local models.** `finagent run` starts the model's vLLM server, runs its batches and stops the server
  again. `--use-running-server` uses a server already listening on the model's port. You can also manage
  servers with `finagent serve start|stop|status <key>`.
- **Resuming.** A run whose `record.json` exists is skipped, so an interrupted command resumes when run
  again.
- **Settings.** Every per-model setting comes from `setup/models.toml`, so there are no per-model
  scripts: the Qwen3.8-27B-FP8 cap of 8,192 tokens and its kept raw answers come from there too.

What each cell took in the pilot (from `records/infra/logs/` and `results/pilot_counts.json`):

| Cell | Command | Batch wall time | Requests | Input tokens (cached) | Output tokens |
|---|---|---:|---:|---:|---:|
| Qwen3-8B / harness | `--model qwen3_8b --framework harness` | 178 s | 37 | 159,661 | 56,212 |
| Qwen3-8B / Codex | `--model qwen3_8b --framework coding_agent` | 298 s (24 runs) + 6 runs earlier | 138 | 1,056,369 (954,416) | 59,697 |
| Qwen3.5-9B / harness | `--model qwen35_9b --framework harness` | 559 s | 47 | 211,734 | 66,483 |
| Qwen3.5-9B / Codex | `--model qwen35_9b --framework coding_agent` | 1,619 s | 282 | 5,307,990 (4,591,488) | 238,188 |
| Qwen3.8-27B-FP8 / harness | `--model qwen38_27b --framework harness` | 911 s | 93 | 552,680 | 178,677 |
| Qwen3.8-27B-FP8 / Codex | `--model qwen38_27b --framework coding_agent` | 3,141 s | 201 | 2,870,264 (2,082,304) | 265,919 |
| DeepSeek / harness | `--model deepseek --framework harness` | 79 s | 117 | 819,968 (708,736) | 92,018 |
| DeepSeek / Codex | `--model deepseek --framework coding_agent` | 223 s | 229 | 3,121,667 (2,843,520) | 153,600 |
| Kimi K3 / harness | `--model kimi --framework harness` | 318 s | 68 | 278,693 (220,672) | 35,387 |
| Kimi K3 / Codex | `--model kimi --framework coding_agent` | 590 s | 159 | 1,397,218 (1,147,392) | 64,636 |

The local models held 2.037 GPU-hours in all.

**Output** (`--out`, default `runs/pilot/`):

- `raw/<run_id>/` (the run folder, laid out as in [`records/README.md`](../records/README.md)) and
  `raw.jsonl`;
- `relay/<model>/requests.jsonl` and the request bodies;
- `infra/` (vLLM and relay launches and logs);
- `run_log.txt`.

Re-audit new coding runs with `finagent audit --raw runs/pilot/raw`, which reads the relay logs from
`runs/pilot/relay`.

Compute the pilot's measures for new runs, by the same rules, for whatever cells, days and arms are present:

```sh
finagent analyze --raw runs/pilot/raw --out runs/pilot/results
```

It writes `describe.json`, `describe_tables.md` and the metric records `describe_reasoning_models.json`
(shifts against ORIG and against PLACEBO, ORIG noise, pastes, mentions, accuracy, tool calls), in the
formats of `results/`. The page, its excerpts and the run counts describe the shipped records only, so
they are not written.

## Expected differences

A rerun uses the same prompts, tools, workspaces, configs and sandbox. Its outputs still differ, for
these reasons:

| Source | Effect | In the pilot |
|---|---|---|
| vLLM sampling | Each harness request carries a seed, but requests are batched (up to 36 in flight per model) and prefix caching is on, so the same seed need not give the same tokens | prefix caching on in every launch, no `--seed` flag |
| API models | DeepSeek and Kimi K3 calls carry no seed, and the providers can change the model behind a name | `deepseek-reasoner` was served as `deepseek-flash` in all 60 DeepSeek records |
| Codex's own prompt text | Codex writes the working folder (random per run), the run date and the host's time zone into every request; `CODEX_HOME` gets a new installation id per run | `/srv/shared_home/lmz/cxpw/<12 letters>/work`, `2026-10-18`, `Asia/Hong_Kong` |
| Codex sampling | Codex sends no temperature, top-p, output cap or seed, so the server's defaults apply, and they differ between models | Qwen3.8-27B-FP8's `generation_config.json` applies (temperature 1.0, top-p 0.95, top-k 20) |
| The agent's toolset | `AGENT_PATH` exposes the host's binaries next to the agent's Python | `/usr/local/bin:/usr/bin:/bin` |
| Hardware and serving | GPU type, memory utilisation and the KV cache size change batching | RTX A6000; FP8 weights run weight-only through the Marlin kernel |
| Paths in the records | new records carry your `WS_ROOT` and other host paths; audit them with your host file | `setup/host.recorded.env` |

Pinning the date and time zone (for example `TZ=Asia/Hong_Kong` and a faked clock) and a fixed `WS_ROOT`
bring the Codex request text closer to the pilot's, but `finagent` does not do this.
[LIMITATIONS.md](LIMITATIONS.md) lists what these differences mean for the results.

## evidence_relations: a separate, self-contained extension

`data/evidence_relations/` (the four inputs/benchmark pieces) and `results/evidence_relations/` (the
`reference_models/` analysis output) are not part of L0-L3 above: this is a CPU-only, deterministic extension
that does not read `data/`'s price panel or news caches for its synthetic half, and is verified on its own,
not by `finagent verify`.

**Synthetic two-signal Bayesian benchmark and its reference forecasters** (own RNG, no dependency on `data/`
at all):

```sh
finagent evidence-synthetic                    # regenerate data/evidence_relations/synthetic/{train,val,test}.jsonl.xz
finagent evidence-synthetic --check             # regenerate in memory, compare with the shipped .xz (both must agree)
finagent evidence-reference-models              # bayes_optimal/counting_naive/salience_follower -> results/evidence_relations/reference_models/
```

**Source of truth**: the generator (`src/finagent/evidence_relations/{synthetic,bayes}.py`, fixed
`BASE_SEED = 20261020`) is what every count in `data/evidence_relations/synthetic/{README,DESIGN}.md` is reported
from; the shipped `.xz` files are a compressed cache of exactly that output (regeneration needs no
decompression, and `--check` proves the two agree rather than assuming it -- see
[`data/evidence_relations/synthetic/README.md`](../data/evidence_relations/synthetic/README.md) "Source of truth" and
"Determinism"). Full derivations and the source-vs-port comparison against
`1_overreaction/repro/evidence_relations/` are in
[`data/evidence_relations/synthetic/DESIGN.md`](../data/evidence_relations/synthetic/DESIGN.md).

The real-day half (day pool, real-day prompt perturbations, tool-redundancy matrix) is built from `data/`'s
96-ticker point-in-time caches through this repository's own `finagent.days` / `finagent.readings` /
`finagent.harness.toolbox`; see `data/evidence_relations/day_pool/README.md`,
`data/evidence_relations/real_day_perturbations/README.md`
and `data/evidence_relations/tool_redundancy/README.md` for its own build and verification commands (`finagent evidence-pool`,
`evidence-real-day`, `evidence-tools`).
