# Environment

The host and software the presentation pilot ran on (2026-10-18). Every value was read from that host or
from the shipped records; the Hugging Face and GitHub facts were looked up on 2026-10-19 without a token.

## Host

| Item | Value |
|---|---|
| OS | Ubuntu 24.04.4 LTS, glibc 2.39 |
| Kernel | Linux 6.8.0-110-generic x86_64 (`#110-Ubuntu SMP PREEMPT_DYNAMIC`) |
| CPU, memory | 2 × Intel Xeon Platinum 8352V (72 cores, 144 threads), 1 TB RAM |
| GPUs | 4 × NVIDIA RTX A6000, 49,140 MiB each, driver 590.48.01 (CUDA 13.1); Ampere, no native FP8 |
| Time zone | `Asia/Hong_Kong` from `/etc/timezone`, `TZ` unset. Codex writes the time zone and the run date into every model request. |
| Proxy | `http(s)_proxy` set on the host: `requests` (harness API calls) follows it, the aiohttp relay does not (`trust_env=False`), the vLLM servers run with it blanked |

## Sandbox and tracing of the coding-agent runs

| Item | Value |
|---|---|
| Linux security modules | `lockdown,capability,landlock,yama,apparmor` |
| Landlock | ABI 4 (kernel 6.7 or later); the sandbox uses ABI 4's TCP connect and bind rules |
| seccomp | libseccomp2 2.5.5-1ubuntu3.1 (`libseccomp.so.2.5.5`), loaded through `ctypes`; blocks UDP and raw IP sockets, `AF_PACKET`, `io_uring_setup` |
| Sandbox launcher | system `/usr/bin/python3` 3.12.3, standard library only |
| strace | 6.8 (`6.8-0ubuntu2`); `kernel.yama.ptrace_scope = 1` |
| User namespaces | `kernel.apparmor_restrict_unprivileged_userns = 1`, so Codex's bundled bubblewrap sandbox cannot start; Codex runs with `sandbox_mode = "danger-full-access"` inside our Landlock + seccomp sandbox |

Sandbox self-test before the batch (`records/infra/checks/build_check.json`): writing inside the workspace
allowed; writing outside it, in `/tmp`, TCP to the internet or to local ssh, UDP and DNS all blocked;
reading outside the workspace allowed.

## Python environments

| Environment | Original location | Python | Pins | Role |
|---|---|---|---|---|
| runner | `1_overreaction/.venv` (uv 0.8.22) | 3.12.3 | [`setup/requirements/runner.txt`](../setup/requirements/runner.txt), 26 packages | run loop, harness, DeepSeek and Kimi clients, Codex relay |
| agent | `/srv/shared_home/lmz/cxpw/pyenv` (`python3 -m venv`) | 3.12.3 | [`setup/requirements/agent-env.txt`](../setup/requirements/agent-env.txt): numpy 2.5.4, pandas 3.0.6 | first `python3` on the Codex agent's `PATH` |
| vLLM | `0_model_server/.venv-vllm` (uv 0.8.22, PyPI wheels) | 3.12.3 | [`setup/requirements/vllm.txt`](../setup/requirements/vllm.txt), all 203 distributions | serves the three local models |

The runner virtualenv holds 139 distributions; `runner.txt` keeps the ones the pilot imports at run time and
their dependencies. Packages imported only on dead code paths or used by other projects (for example
`mcp`, `pydantic`, `yfinance`) are left out.

## vLLM serving

| Item | Value |
|---|---|
| Versions | vllm 0.29.0, torch 2.13.0 (CUDA 13 wheels), transformers 5.17.0, tokenizers 0.23.2, triton 3.7.1, flashinfer-python 0.6.18, compressed-tensors 0.17.0, safetensors 0.8.0, huggingface-hub 1.31.0 |
| Attention backend | `FLASH_ATTN` (FlashAttention 2) in every launch, chosen automatically from `FLASH_ATTN, FLASHINFER, TRITON_ATTN, FLEX_ATTENTION` |
| Precision | bfloat16; Qwen3.8-27B-FP8 runs its FP8 weights through `MarlinFP8ScaledMMLinearKernel` (weight-only FP8 on Ampere) |
| Caching | prefix caching on (vLLM default, `enable_prefix_caching=True` in every engine config); no `--seed` flag, each harness request carries its own seed |
| Batch launches | Qwen3-8B: GPU 2 at 0.54 memory utilisation for the main batch, GPU 0 at 0.94 for the rerun of 24 Codex runs; Qwen3.5-9B: GPU 0 at 0.70; Qwen3.8-27B-FP8: GPU 0 at 0.94 (`records/infra/launch/`) |

The serve command line of each model, with all flags and environment variables, is in its launch record
and in `setup/models.toml`.

## Model weights

The weights are not shipped. Each folder is the Hugging Face repository at one revision;
`setup/weights/<key>.sha256` holds the sha256 of every file (`sha256sum -c` from inside the folder).

| Key | Repository | Revision | Files | Size | License |
|---|---|---|---:|---:|---|
| `qwen3_8b` | `Qwen/Qwen3-8B` | `b968826d9c46dd6066d109eabc6255188de91218` | 14 | 16.40 GB | Apache-2.0 |
| `qwen35_9b` | `Qwen/Qwen3.5-9B` | `c202236235762e1c871ad0ccb60c8ee5ba337b9a` | 16 | 19.33 GB | Apache-2.0 |
| `qwen38_27b` | `Qwen/Qwen3.8-27B-FP8` | `017b9c7af6b5689d5dd426a76e0bc077eb5ca20a` | 81 | 30.89 GB | Apache-2.0 |

- **Qwen3-8B** (downloaded 2026-10-08): revision recorded in the download metadata of all 14 files.
  Confirmed: the 6 LFS files match the revision's LFS sha256 and the 8 others its git blob ids; the
  repository's `.gitattributes` was not downloaded. The five shard hashes also equal the older
  `Qwen3-8B.local_sha256.txt`.
- **Qwen3.5-9B** (downloaded 2026-09-21): no revision was recorded. Identified afterwards: all 16 local
  files equal the tree of `c2022362…` (5 by LFS sha256, 11 by git blob id). The commit before it,
  `ef3d031a…`, differs in `README.md` only, and `c2022362…` is still the head of `main`, so the weights,
  tokenizer and chat template are those of both commits.
- **Qwen3.8-27B-FP8** (downloaded 2026-09-23): revision recorded in the download metadata of all 81 files.
  Confirmed: 67 LFS files by sha256, 14 others by git blob id.

Chat templates: Qwen3-8B's is inside `tokenizer_config.json` (sha256 `d5d09f07…8101`), Qwen3.5-9B's
`chat_template.jinja` is `a4aee8af…f715`, Qwen3.8-27B-FP8's is `c3cf9e34…1041`.

## API models

| Key | Endpoint | Model sent | Model reported |
|---|---|---|---|
| `deepseek` | `https://api.deepseek.com` | `deepseek-reasoner` | `deepseek-flash` in all 60 records (an alias resolved by DeepSeek; it cannot be pinned) |
| `kimi` | `https://api.moonshot.ai/v1` | `kimi-k3` | `kimi-k3` |

Keys are read from `DEEPSEEK_API_KEY` and `MOONSHOT_API_KEY`.

## Codex CLI

| Item | Value |
|---|---|
| Version | `codex-cli 0.162.1`, target `x86_64-unknown-linux-musl`, standalone package layout 1 (`codex-package.json`) |
| Release | GitHub `openai/codex`, tag `rust-v0.162.1`, published 2026-10-09T19:44:51Z |
| Asset | [`codex-package-x86_64-unknown-linux-musl.tar.gz`](https://github.com/openai/codex/releases/download/rust-v0.162.1/codex-package-x86_64-unknown-linux-musl.tar.gz), 162,905,879 bytes |
| Asset sha256 | `a676f5722aae0d86cbe3764332f08eab1fdd89dc0a300b3ad4ffbf48611fa3e3` (published in the release's `codex-package_SHA256SUMS`, itself `828b09736925c615d115fc77b328a6cacd7e23d80c278612d98859fbe4f46108`, and as the GitHub asset digest) |
| Installer | the release's `install.sh` (sha256 `150e3cf675682efeaac115aa3747add3f27887896d04ce6d0b56478d8b428bf6`); `CODEX_RELEASE=0.162.1` pins the version. It downloads the asset above, checks it against `codex-package_SHA256SUMS`, unpacks it with `tar -xzf` into `$CODEX_HOME/packages/standalone/releases/0.162.1-x86_64-unknown-linux-musl/` and links `~/.local/bin/codex` to `…/current/bin/codex`. |
| How it got onto the host | Codex's own auto-update to 0.162.1 on 2026-10-10 19:29 (+08:00) (`packages/standalone/auto-update-version`); the archive's files are dated 2026-10-09 17:58 UTC |

Hashes of the installed package (44 files, 452 MB):

| File | Bytes | sha256 |
|---|---:|---|
| `bin/codex` | 294,415,048 | `628e35487d888a28f0427fc37501da529dd3d81fcbad7a2c3421c1e8670d92e1` |
| `bin/codex-code-mode-host` | 74,036,112 | `ec71830690a7c0024916ee0c99fbdc635bc6e747ff665ea4f03a8389bbcb6b30` |
| `codex-path/rg` | 5,408,904 | `e62198eb19b136b88c330af83647b5a962cb99b6b1f066758568f12de1974849` |
| `codex-resources/bwrap` | 529,776 | `01fb705f067bd5365b63d8ad2323a61c8d007733ca5e649437e086f3fb9935d8` |
| `codex-package.json` | 205 | `f05ebff6db98bd613dd5654461985090c6416b41ad67902243d83a53b305ac05` |

Codex puts `codex-path/` (its bundled ripgrep) on the command `PATH`; 7 of the 10 flagged coding-agent runs
are flagged only for running that `rg`. Not checked here: that the release asset unpacks to exactly these
bytes (the 163 MB asset was not downloaded), so an install should check both the archive digest and
`bin/codex`.
