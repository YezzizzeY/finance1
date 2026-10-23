#!/usr/bin/env bash
# The runner environment (run loop, harness, API clients, relay): a Python 3.12 venv at <repo>/.venv with the pilot's exact pins
# (setup/requirements/runner.txt) and this package; then the host checks a coding-agent run needs: strace, libseccomp, Landlock ABI 4
# (the sandbox self-test: outside writes, TCP, UDP and DNS must be blocked).
#   setup/scripts/setup_runner_env.sh              (PYTHON=python3.12 by default)
set -euo pipefail
source "$(dirname "$0")/host_env.sh"

venv="$REPO_ROOT/.venv"
"${PYTHON:-python3.12}" -m venv "$venv"
"$venv/bin/python" -m pip install -r "$REPO_ROOT/setup/requirements/runner.txt"
"$venv/bin/python" -m pip install -e "$REPO_ROOT[test]"
"$venv/bin/python" -m finagent --help > /dev/null

command -v strace > /dev/null || { echo "strace is missing (apt install strace)" >&2; exit 1; }
"$SANDBOX_PYTHON" -c 'import ctypes.util, sys; sys.exit(ctypes.util.find_library("seccomp") is None)' \
  || { echo "libseccomp is missing (apt install libseccomp2)" >&2; exit 1; }
probe="$(mktemp -d)"
trap 'rm -rf "$probe"' EXIT
result="$("$SANDBOX_PYTHON" "$REPO_ROOT/src/finagent/coding/sandbox.py" --selftest "$probe")"
echo "sandbox self-test: $result"
[[ "$result" == *'"pass": true'* ]] || { echo "the sandbox self-test failed (Linux >= 6.7 with Landlock ABI 4 is needed)" >&2; exit 1; }
