"""Where everything is: repository folders, the data files, setup/*.toml and the host settings.

Data paths default to <repo>/data (FINAGENT_DATA_DIR moves the whole folder), new runs go to <repo>/runs (FINAGENT_RUNS_DIR).
Host-specific values (ports, binaries, workspace root) come from the env file FINAGENT_HOST_ENV (absolute, or relative to the
repository; default setup/host.example.env); an environment variable FINAGENT_<KEY> overrides key KEY of the file.
`python -m finagent.config` prints the host settings as shell `export` lines (setup/scripts/host_env.sh reads them).
"""
from __future__ import annotations

import os
import shlex
import string
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path

import tomllib

ROOT = Path(__file__).resolve().parents[2]
if not (ROOT / "setup" / "experiment.toml").is_file():
    raise SystemExit(f"finagent: {ROOT / 'setup'} is missing; install the package editable from a clone (pip install -e .)")
CONFIGS = ROOT / "setup"
RECORDS = ROOT / "records"
RESULTS = ROOT / "results"
RAW = RECORDS / "raw"                                       # the run folders, after `finagent unpack`
DATA = Path(os.environ.get("FINAGENT_DATA_DIR") or ROOT / "data")
RUNS = Path(os.environ.get("FINAGENT_RUNS_DIR") or ROOT / "runs")
PROMPTS = DATA / "prompts"
EVIDENCE_RELATIONS_DATA = DATA / "evidence_relations"          # day_pool/, real_day_perturbations/, synthetic/, tool_redundancy/ (inputs)
EVIDENCE_RELATIONS_RESULTS = RESULTS / "evidence_relations"    # reference_models/ (an analysis output, not an input)


def _toml(name: str) -> dict:
    with open(CONFIGS / name, "rb") as f:
        return tomllib.load(f)


EXPERIMENT = _toml("experiment.toml")
MODELS: dict[str, dict] = _toml("models.toml")
ARMS: tuple[str, ...] = tuple(EXPERIMENT["runs"]["arms"])
FRAMEWORKS: tuple[str, ...] = tuple(EXPERIMENT["runs"]["frameworks"])

# ------------------------------------------------------------------------------------------------ data files
DAYS_FILE = DATA / EXPERIMENT["days"]["file"]
PANEL = DATA / "panel" / "us_daily_stratos_20260924.parquet"
PIT_CACHE = DATA / "pit_cache"
NEWS_WINDOW = "2025-09-29_2026-09-24_news_v2"
ANCHORS = DATA / "anchors"
GROUNDING_BLOCKS = DATA / "selection" / "grounding_blocks.json"
S1_SPEC = DATA / "selection" / "s1_spec.json"
GROUNDING_SESSIONS = DATA / "grounding_sessions"


def rel(p: Path) -> str:
    """p relative to the repository when it lies inside it, else as given."""
    try:
        return str(Path(p).resolve().relative_to(ROOT))
    except ValueError:
        return str(p)


def news_cache_dir(ticker: str) -> Path:
    """The point-in-time cache of one stock (prices, news feeds, insider rows, corporate actions, manifest)."""
    return PIT_CACHE / ticker / NEWS_WINDOW


def anchor_file(day_id: str) -> Path:
    return ANCHORS / f"{day_id}.json.gz"


def grounding_session_file(day_id: str) -> Path:
    return GROUNDING_SESSIONS / day_id / "FULL_G_0.json.gz"


# ------------------------------------------------------------------------------------------------ host settings
HOST_ENV_FILE = ROOT / (os.environ.get("FINAGENT_HOST_ENV") or "setup/host.example.env")     # relative to the repository
RECORDED_HOST_ENV = CONFIGS / "host.recorded.env"                                           # the host that ran the pilot
OVERRIDE_PREFIX = "FINAGENT_"                                                               # FINAGENT_<KEY> overrides KEY
_pinned: list[tuple[Path, dict[str, str]]] = []                                             # set inside host_env()


def read_env_file(path: Path, env_wins: bool = True) -> dict[str, str]:
    """KEY=VALUE lines (# comments); ${NAME} expands earlier keys, the environment or REPO_ROOT; an environment variable
    FINAGENT_<KEY> replaces the value of KEY (unless env_wins is False)."""
    known = {**os.environ, "REPO_ROOT": str(ROOT)}
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition("=")
        key, override = key.strip(), OVERRIDE_PREFIX + key.strip()
        try:
            out[key] = (os.environ[override] if env_wins and override in os.environ
                        else string.Template(value.strip()).substitute(known))
        except KeyError as e:
            raise KeyError(f"{path}: {key} uses ${{{e.args[0]}}}, which is not set") from None
        except ValueError as e:
            raise ValueError(f"{path}: {key}: {e} (write a literal $ as $$)") from None
        known[key] = out[key]
    return out


@lru_cache(maxsize=1)
def host_settings() -> dict[str, str]:
    """The host settings of this process (read once, on first use)."""
    return read_env_file(HOST_ENV_FILE)


@contextmanager
def host_env(path: Path):
    """Inside the block, host() answers from env file `path` alone (no environment overrides). verify regenerates and
    re-audits the shipped coding runs this way with RECORDED_HOST_ENV, the paths and ports they were made with."""
    _pinned.append((path, read_env_file(path, env_wins=False)))
    try:
        yield
    finally:
        _pinned.pop()


def host(key: str) -> str:
    path, settings = _pinned[-1] if _pinned else (HOST_ENV_FILE, host_settings())
    if key not in settings:
        raise KeyError(f"{key} is not set in {path}" + ("" if _pinned else f" (or as {OVERRIDE_PREFIX}{key} in the environment)"))
    return settings[key]


def port(kind: str, model: str) -> int:
    """The local port of a model's vLLM server (kind 'VLLM') or relay (kind 'RELAY')."""
    return int(host(f"{kind}_PORT_{model.upper()}"))


if __name__ == "__main__":
    try:
        print("\n".join(f"export {k}={shlex.quote(v)}" for k, v in host_settings().items()))
    except (KeyError, ValueError) as e:
        raise SystemExit(f"finagent.config: {e.args[0]}") from None
