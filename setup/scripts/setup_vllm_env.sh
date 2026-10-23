#!/usr/bin/env bash
# The vLLM serving environment of the three local models: a Python 3.12 venv at VLLM_ENV holding exactly the 203 distributions
# of the pilot's (setup/requirements/vllm.txt: vllm 0.29.0, torch 2.13.0 with CUDA 13 wheels, ...).
#   setup/scripts/setup_vllm_env.sh                (PYTHON=python3.12 by default)
set -euo pipefail
source "$(dirname "$0")/host_env.sh"

"${PYTHON:-python3.12}" -m venv "$VLLM_ENV"
"$VLLM_ENV/bin/python" -m pip install --no-deps -r "$REPO_ROOT/setup/requirements/vllm.txt"
"$VLLM_ENV/bin/python" -m pip check
"$VLLM_ENV/bin/vllm" --version
