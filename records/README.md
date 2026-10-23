# Run records

Everything the 300 runs of the presentation pilot left behind, plus the logs and checks of the
infrastructure that ran them. Run folders are the original output with one path renamed (see "Path rename"
below); they are packed
into eleven reproducible `.tar.xz` archives (12.6 MB packed, 436 MB unpacked, 4,443 files).

| Path | Content |
|---|---|
| `runs.jsonl` | 300 lines, one per run, in the original order. Each line is the run's `record.json` as one JSON line (`json.dumps`, byte-identical). |
| `archives/<model>__<framework>.tar.xz` | the 30 run folders of one model × framework cell, as `raw/<run_id>/…` |
| `archives/smoke.tar.xz` | the smoke-stage runs and the audit canary, as `raw/smoke_orig/…`, `raw/smoke_runs/…` and their two `.jsonl` indexes |
| `infra/` | vLLM launches and serve logs, relay launches and request logs, run logs, API probes, build checks |
| `MEMBERS.sha256` | sha256 of every file inside every archive, with the path it unpacks to under `records/` |
| `SHA256SUMS` | sha256 of every other file under `records/` |

## Unpack and verify

```sh
finagent unpack                     # extracts every archive into records/raw/ and checks MEMBERS.sha256
```

By hand, from `records/`:

```sh
sha256sum -c SHA256SUMS
for a in archives/*.tar.xz; do tar -xJf "$a"; done
sha256sum -c --quiet MEMBERS.sha256
```

`records/raw/` is git-ignored. Unpacked, `raw/<run_id>/` mirrors the original `raw/<run_id>/`, and
`raw/smoke_orig/`, `raw/smoke_runs/` mirror the original `smoke_orig/`, `smoke_runs/` folders.

| Archive | Runs | Files | Unpacked | Packed |
|---|---:|---:|---:|---:|
| `qwen3_8b__harness` | 30 | 60 | 0.47 MB | 0.40 MB |
| `qwen3_8b__coding_agent` | 30 | 634 | 41.0 MB | 1.08 MB |
| `qwen35_9b__harness` | 30 | 60 | 0.53 MB | 0.47 MB |
| `qwen35_9b__coding_agent` | 30 | 933 | 122.8 MB | 2.29 MB |
| `qwen38_27b__harness` | 30 | 60 | 1.57 MB | 1.49 MB |
| `qwen38_27b__coding_agent` | 30 | 768 | 98.2 MB | 2.20 MB |
| `deepseek__harness` | 30 | 60 | 0.37 MB | 0.31 MB |
| `deepseek__coding_agent` | 30 | 820 | 98.9 MB | 1.98 MB |
| `kimi__harness` | 30 | 60 | 0.24 MB | 0.20 MB |
| `kimi__coding_agent` | 30 | 678 | 47.7 MB | 1.20 MB |
| `smoke` | 8 + 11 | 310 | 24.0 MB | 0.97 MB |

The archives were built with GNU tar 1.35 and xz 5.8.3; rebuilding them from the original folders gives
the same bytes:

```sh
tar --sort=name --mtime=@0 --owner=0 --group=0 --numeric-owner --mode=a=rX,u+w --format=gnu \
    -cf - raw/<model>__<framework>__* | xz -9e -T1 > archives/<model>__<framework>.tar.xz
```

File contents are unchanged apart from the path rename below; modification times are set to 0 and modes to
0644 / 0755.

## Path rename (2026-10-23)

After the pilot, the experiment folder on the host was renamed to `1_overreaction`. Its former name was replaced
by `1_overreaction` everywhere it occurred: in `strace.txt` and `record.json` of the 150 coding-agent runs, the
smoke-stage runs and their indexes, `runs.jsonl`, four infrastructure logs, and `setup/host.recorded.env`. It is a
single fixed string replaced by another. One more edit: in the smoke-stage audit canary, which deliberately
reads a file outside its workspace, the project name in the first line it read is replaced by `[redacted]`
(13 occurrences in 5 files). No other byte changed; the re-audit (verify L2) reads the renamed
paths from `setup/host.recorded.env`, so records and host settings agree. The archives were then repacked with
the recipe above, and `MEMBERS.sha256` and `SHA256SUMS` recomputed.

## Run folder anatomy

Run ids are `<model>__<framework>__<day_id>__<arm>__<k>`. Sizes are totals over the 150 runs of a
framework, with the median per run.

**Harness run**

| File | Content | Total | Median |
|---|---|---:|---:|
| `record.json` | the run's record: decision, validity, tool calls, tokens, timing, leakage verdict | 0.31 MB | 2.0 kB |
| `session.json.gz` | the full session: `trace` (system and user prompts per turn), `step` (model outputs, reasoning, tool calls and results), `ctx` (rendered prompts, raw API responses, the arm's rewritten tool outputs), `cache_log` (ids and times of every news item handed to the model) | 2.88 MB | 11.4 kB |

**Coding-agent run (Codex CLI)**

| File | Content | Total | Median |
|---|---|---:|---:|
| `record.json` | the run's record, as above, plus the Codex summary and the audit result (`leakage`) | 0.41 MB | 2.7 kB |
| `codex_config.toml` | the `config.toml` written for the run | 0.28 MB | 1.8 kB |
| `events.jsonl` | the `codex exec --json` event stream | 14.8 MB | 32.4 kB |
| `codex_sessions/YYYY/MM/DD/rollout-*.jsonl` | Codex's own session file, including its built-in instructions | 22.1 MB | 127.7 kB |
| `relay/NNNNN_req.json`, `NNNNN_resp.txt` | every request body the relay forwarded to the model, and the raw response | 218.3 MB | 1.21 MB |
| `strace.txt` | `strace -f` of the whole process tree (exec, open, chdir, connect, bind, clone, fork) | 100.5 MB | 457.9 kB |
| `sandbox_log.jsonl` | the sandbox launcher's log of the command it started | 0.06 MB | 0.4 kB |
| `workspace/` | the given `task.md`, `prices.csv`, `news.csv`, `account.json`; the agent's `decision.json` and any scripts it wrote | 52.2 MB | 355.8 kB |
| `stderr.txt` | Codex's standard error | 0.01 MB | 0.0 kB |

Paths inside the records are those of the original host (for example the agent's working folder
`/srv/shared_home/lmz/cxpw/<12 letters>/work`). They are part of what the agents saw and are kept;
`setup/host.recorded.env` lists them.

## Which runs count

A run enters the analysis when its decision is valid (`decision_valid`: positive volatility and a numeric
return forecast) and the audit did not flag it (`leakage.flag` is false). Harness runs can only reach the
point-in-time tools and are never flagged. 286 of the 300 runs count:

| Cell | Invalid decision | Flagged by the audit | Counted |
|---|---:|---:|---:|
| Qwen3-8B, Codex | 3 | 1 | 26 |
| Qwen3.5-9B, Codex | 1 | 0 | 29 |
| Qwen3.8-27B-FP8, Codex | 0 | 2 | 28 |
| DeepSeek, Codex | 0 | 7 | 23 |
| Kimi K3, Codex | 0 | 0 | 30 |
| every harness cell | 0 | 0 | 30 each |

Flagged runs stay in the records; the audit's reasons are in each `record.json`.

## Smoke runs and the canary (`smoke.tar.xz`)

- `raw/smoke_orig/`: one ORIG run per model and framework on `VST_2026-05-06`, made before the batch
  (Qwen3-8B, Qwen3.5-9B, DeepSeek, Kimi; 8 runs). Index: `raw/smoke_orig.jsonl` (8 rows).
- `raw/smoke_runs/`: build-stage test runs on other days and arms (Qwen3-8B, Qwen3.5-9B, DeepSeek), the two
  Qwen3.8-27B-FP8 smoke runs (2,048 tokens per turn, before its batch at 8,192), and
  `CANARY__deepseek__coding_agent__VST_2026-05-06`, a coding-agent run told to break the rules (read
  outside the workspace, open the network, write a future-dated price row) to show that the audit flags
  each kind; its verdict is `infra/checks/audit_canary.json`. Index: `raw/smoke_runs.jsonl` (12 rows;
  the row `qwen3_8b__coding_agent__CRWD_2026-08-27__ORIG__0` has no saved folder in the original output).

## infra/

| Folder | Files |
|---|---|
| `checks/` | `prompt_check.json` (66 prompt and workspace hashes), `rewrite_check.json` (456 arm-rewrite checks), `harness_wrapper_check.json`, `build_check.json`, `smoke_check.json`, `smoke_check_kimi.json`, `kimi_counts.json`, `audit_canary.json` |
| `launch/` | vLLM launch records (`launch_*.json`, `pilot1_*`, `pilot2_*`, `smoke_launch_*`, `start_*.out`: command line, GPU, port, environment), `qwen38_launches.jsonl`, `qwen38_gpu_poll.jsonl` |
| `serve/` | vLLM server logs of the three local models |
| `relay/` | relay launch records (`relay_<model>.json`, `.out`) and `<model>/requests.jsonl`: one row per request through the relay (run header, path, sizes, status, usage; no headers or keys) |
| `logs/` | `pilot_log.txt` (the batch timeline), `smoke_log.txt`, `qwen38_log.txt`, `qwen38_log_runs.txt` |
| `probes/` | the four Kimi API probes that fixed its request parameters |

## What was left out, and what was edited

The original run also covered a sixth model whose reasoning is not visible; its 60 runs, 4 smoke runs, its
canary and every line or entry about it are left out of the release. Nine files therefore differ from the
original; every other file is byte-identical. Each edit only removes entries, except that two counts in
`smoke_check.json` (`n_smoke_runs`, `n_pass`: 8 → 6) are recomputed over the remaining entries.

| File | Original sha256 (prefix) | Edit |
|---|---|---|
| `runs.jsonl` | `a1a0e96becc4c616` (`raw.jsonl`) | 60 of 360 lines removed |
| `raw/smoke_runs.jsonl`, `raw/smoke_orig.jsonl` (in `smoke.tar.xz`) | `9e5a3f6e25ad6d13`, `7b0cb617260fb75b` | 4 and 3 lines removed |
| `infra/checks/audit_canary.json` | `372a69fb0dfe57a3` | 1 of 2 elements removed |
| `infra/checks/build_check.json` | `54db8b28e8d8f4c0` | entries removed from `audit_canary`, `smoke_runs`, `combos_with_a_valid_unflagged_smoke_run` |
| `infra/checks/smoke_check.json` | `0622f5c364cc97e0` | 2 entries removed from `smoke` and from `rewrite_on_build_stage_runs_of_other_arms`; the excluded framework's field (null in every remaining entry) removed |
| `infra/checks/smoke_check_kimi.json` | `d7aec1b0c81ef684` | the same null field removed |
| `infra/logs/pilot_log.txt`, `smoke_log.txt` | `ef8e56860dc8dd80`, `ea16fd2feca6a01c` | 4 and 6 lines removed; the counts in their `summary:` and `smoke stage:` lines still include the removed runs |

The JSON files keep the original formatting (`json.dumps(…, indent=1)`). Also not shipped:

- `relay/<model>/<id>/` body folders of the original output: every one that belongs to a shipped run is
  already inside that run folder; the rest are the runner's `/v1/models` probes (`RUNNER_PROBE`,
  `NO_RUN_HEADER`, still listed in `requests.jsonl`) and one early build-stage run without a folder.
- process-id files, the code and summary snapshots taken before Kimi was added, `tmp/` (sockets and
  compiler caches), `scratch/`, the console copies of the logs above (`*_stdout*.txt`, same lines), and the
  original summary and report files, which `results/` regenerates from these records.
