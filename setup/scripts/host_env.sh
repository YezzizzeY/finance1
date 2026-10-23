# Sourced by the other scripts: exports REPO_ROOT and the host settings of $FINAGENT_HOST_ENV (absolute, or relative to the
# repository; default setup/host.example.env), parsed by finagent.config itself (`python -m finagent.config`), so the scripts
# and finagent always see the same values. Needs Python >= 3.11 (PYTHON=python3.12 by default); finagent need not be installed.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"   # setup/scripts/host_env.sh -> up two levels to the repo root
export REPO_ROOT
_host_exports="$(PYTHONPATH="$REPO_ROOT/src" "${PYTHON:-python3.12}" -B -m finagent.config)" || return 1
eval "$_host_exports"
unset _host_exports
