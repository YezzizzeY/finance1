#!/usr/bin/env bash
# The Python environment the coding agents get first on their PATH: a Python 3.12 venv at AGENT_PYENV (the pilot's was
# <WS_ROOT>/pyenv) with numpy and pandas only, at the exact versions of setup/requirements/agent-env.txt.
#   setup/scripts/setup_agent_env.sh               (PYTHON=python3.12 by default)
set -euo pipefail
source "$(dirname "$0")/host_env.sh"

"${PYTHON:-python3.12}" -m venv "$AGENT_PYENV"
"$AGENT_PYENV/bin/python" -m pip install --no-deps -r "$REPO_ROOT/setup/requirements/agent-env.txt"
"$AGENT_PYENV/bin/python" -c 'import sys, numpy, pandas; print(f"agent env {sys.prefix}: Python {sys.version.split()[0]}, numpy {numpy.__version__}, pandas {pandas.__version__}")'
