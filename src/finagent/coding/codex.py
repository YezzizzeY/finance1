"""Codex CLI runs (`codex exec --json`, version 0.162.1): the per-run config.toml, one sandboxed run, batches, the audit canary.

A run gets a fresh workspace (workspace.py) and its own CODEX_HOME holding only config.toml, so ~/.codex is never read (no user
MCP servers, rules or skills). Codex talks the Responses API (the only wire API of 0.162) to the model's relay (relay.py), the
only TCP port its sandbox allows; the relay forwards to our vLLM server or to the model's API and holds the API key.
Codex's own sandbox needs unprivileged user namespaces, so Codex runs with sandbox_mode "danger-full-access" inside sandbox.py
(Landlock + seccomp: writes only in work/, home/, tmp/ and CODEX_HOME, TCP only to the relay, no UDP or raw sockets), and its
permission text is replaced by Codex's own workspace-write text with "Network access is restricted" (PERMISSIONS_TEXT), so the
model is told the policy that is actually enforced. strace -f of the whole tree, the --json events, the sandbox log and the relay
log are kept in the run folder; audit.py flags the run, and the record carries the verdict.
The output folder `out` of a batch holds raw/ (the store), relay/<model>/ (relay logs) and infra/ (relay state and stdout).
"""
from __future__ import annotations

import functools
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests

from finagent import config, records
from finagent.coding import audit, workspace

# adapted from Codex 0.162.1's own workspace-write permission text (openai/codex, Apache-2.0: docs/Apache-2.0.txt)
PERMISSIONS_TEXT = ("<permissions instructions>\nFilesystem sandboxing defines which files can be read or written. `sandbox_mode` is "
                    "`workspace-write`: The sandbox permits reading files, and editing files in `cwd` and `writable_roots`. Editing "
                    "files in other directories requires approval. Network access is restricted.\nApproval policy is currently "
                    "never. Do not provide the `sandbox_permissions` for any reason, commands will be rejected.\n"
                    "</permissions instructions>")
STRACE = ["strace", "-f", "-qq", "-y", "-s", "300", "-e",
          "trace=execve,open,openat,openat2,chdir,connect,bind,clone,clone3,fork,vfork"]
SANDBOX = Path(__file__).with_name("sandbox.py")
SRC = Path(__file__).resolve().parents[2]                                      # makes finagent importable for the relay
RUN_HEADER = "X-Cxp-Run"                                                       # tells the relay which run a request belongs to
RUNNER_PROBE = "RUNNER_PROBE"                                                  # run header of the runner's own relay probes
RELAY_ENV = ("PATH", "HOME", "LANG", "LC_ALL", "SSL_CERT_FILE", "SSL_CERT_DIR")   # passed on to a relay (plus its API key)
CODING = config.EXPERIMENT["coding_agent"]


@functools.cache
def codex_real_bin() -> str:
    """The resolved CODEX_BIN, after checking that it is the pinned version."""
    b = os.path.realpath(config.host("CODEX_BIN"))
    v = subprocess.run([b, "--version"], capture_output=True, text=True).stdout.strip()
    if v != CODING["codex_version"]:
        raise RuntimeError(f"codex version {v!r} != {CODING['codex_version']!r} ({b}; setup/scripts/install_codex.sh installs it)")
    return b


# ================================================================================================== relays
def relay_upstream(model: str) -> str:
    m = config.MODELS[model]
    return f"http://{config.EXPERIMENT['vllm']['host']}:{config.port('VLLM', model)}" if m["provider"] == "vllm" else m["codex"]["base_url"]


def relay_up(model: str) -> bool:
    try:
        # the probe carries its own run header, so a probe made when one run starts is never counted as a header-less (stray)
        # relay request inside another run that is still going
        requests.get(f"http://127.0.0.1:{config.port('RELAY', model)}/v1/models", timeout=10, headers={RUN_HEADER: RUNNER_PROBE})
        return True
    except requests.RequestException:
        return False


def relay_state(out: Path, model: str) -> Path:
    return out / "infra" / f"relay_{model}.json"


def relay_log(out: Path, model: str) -> Path:
    return out / "relay" / model / "requests.jsonl"


_RELAY_LOCK = threading.Lock()


def ensure_relay(model: str, out: Path) -> dict:
    """Start the model's relay once. Serialised: in the pilot's first batch two of 6 runs starting together each launched a relay;
    the second could not bind the port, and its pid in the state file made every later run refuse the live relay."""
    with _RELAY_LOCK:
        return _ensure_relay(model, out)


def _ensure_relay(model: str, out: Path) -> dict:
    f, port = relay_state(out, model), config.port("RELAY", model)
    if relay_up(model):
        st = json.loads(f.read_text()) if f.exists() else {}
        if not st or not os.path.exists(f"/proc/{st.get('pid')}"):
            raise RuntimeError(f"port {port} answers but is not our relay (stop that process, or set RELAY_PORT_{model.upper()} "
                               "in the host env file)")
        return st
    m = config.MODELS[model]
    env = {k: os.environ[k] for k in RELAY_ENV if k in os.environ}
    env["PYTHONPATH"] = str(SRC)
    args = [config.host("RUNNER_PYTHON") or sys.executable, "-m", "finagent.coding.relay", "--port", str(port),
            "--upstream", relay_upstream(model), "--log-dir", str(relay_log(out, model).parent)]
    if m.get("api_key_env"):
        key = os.environ.get(m["api_key_env"])
        if not key:
            raise RuntimeError(f"set {m['api_key_env']} in the environment to run {m['label']} as a coding agent")
        env[m["api_key_env"]] = key                                           # only in the relay's environment
        args += ["--key-env", m["api_key_env"]]
    if m["codex"].get("relay_max_concurrent"):
        args += ["--max-concurrent", str(m["codex"]["relay_max_concurrent"])]
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(out / "infra" / f"relay_{model}.out", "a") as log:
        proc = subprocess.Popen(args, cwd=str(config.ROOT), env=env, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                start_new_session=True)
    st = {"key": model, "pid": proc.pid, "port": port, "upstream": relay_upstream(model), "started": time.time()}
    f.write_text(json.dumps(st, indent=1))
    for _ in range(30):
        if relay_up(model):
            return st
        time.sleep(1)
    raise RuntimeError(f"relay {model} did not come up (see {out / 'infra' / f'relay_{model}.out'})")


def stop_relay(model: str, out: Path) -> dict:
    f = relay_state(out, model)
    if not f.exists():
        return {"key": model, "state": "never started"}
    st = json.loads(f.read_text()); pid = st["pid"]
    try:
        cmd = open(f"/proc/{pid}/cmdline").read()
    except OSError:
        return {"key": model, "state": "not running"}
    if "finagent.coding.relay" not in cmd or str(st["port"]) not in cmd:
        raise RuntimeError(f"pid {pid} is not our relay")
    os.kill(pid, signal.SIGTERM)
    return {"key": model, "pid": pid, "state": "stopped"}


# ================================================================================================== one run
def toml_str(s: str) -> str:
    return json.dumps(s)                                                      # a JSON string literal is a valid TOML basic string


def context_window(model: str, served_max_model_len: int | None = None) -> int:
    """Codex's model_context_window: models.toml's, capped at the served --max-model-len of a vLLM model when known."""
    w = config.MODELS[model]["codex"]["context_window"]
    return min(w, served_max_model_len) if served_max_model_len else w


def codex_config(model: str, rid: str, home: Path, tmp: Path, window: int | None = None) -> str:
    """The run's config.toml. The text is the pilot's byte for byte, header comment included (verify L1 regenerates the recorded
    files), so it still names the pilot's source file."""
    m = config.MODELS[model]
    env = {"PATH": config.host("AGENT_PATH"), "HOME": str(home), "TMPDIR": str(tmp), "LANG": "C.UTF-8"}
    env_toml = ", ".join(f"{k} = {toml_str(v)}" for k, v in env.items())
    return f"""# codexpilot_20261018 coding-agent run {rid} ({m['label']}); written by repro/codexpilot/coding_agent.py
model = {toml_str(m['model_id'])}
model_provider = "cxp"
model_context_window = {window or context_window(model)}
model_reasoning_effort = {toml_str(m['codex']['reasoning_effort'])}
approval_policy = "never"
sandbox_mode = "danger-full-access"
include_permissions_instructions = false
developer_instructions = {toml_str(PERMISSIONS_TEXT)}
check_for_update_on_startup = false
web_search = "disabled"
show_raw_agent_reasoning = true

[features]
# a plain coding agent: shell commands and files only (no sub-agents, goals, plugin / app marketplaces, image or browser tools;
# with plugins on, codex's start-up ran `git ls-remote https://github.com/openai/plugins.git`)
multi_agent = false
goals = false
plugins = false
apps = false
remote_plugin = false
tool_suggest = false
image_generation = false
browser_use = false
computer_use = false
shell_snapshot = false

[skills.bundled]
enabled = false

[model_providers.cxp]
name = {toml_str(m['label'] + ' via the local relay')}
base_url = "http://127.0.0.1:{config.port('RELAY', model)}/v1"
wire_api = "responses"
requires_openai_auth = false
http_headers = {{ "{RUN_HEADER}" = {toml_str(rid)} }}

[shell_environment_policy]
inherit = "none"
set = {{ {env_toml} }}

[analytics]
enabled = false
"""


def codex_command(model: str, f: dict[str, Path], codex_bin: str, prompt: str) -> list[str]:
    """strace -> sandbox.py -> codex exec, for the run folders f (workspace.run_folders)."""
    return STRACE + ["-o", str(f["base"] / "strace.txt"), config.host("SANDBOX_PYTHON"), str(SANDBOX),
                     "--write", str(f["work"]), "--write", str(f["home"]), "--write", str(f["tmp"]), "--write", str(f["codex_home"]),
                     "--connect-port", str(config.port("RELAY", model)), "--log", str(f["base"] / "sandbox_log.jsonl"), "--",
                     codex_bin, "exec", "--json", "--skip-git-repo-check", "-C", str(f["work"]), prompt]


def codex_env(f: dict[str, Path]) -> dict[str, str]:
    """The whole environment of the agent process tree."""
    return {"HOME": str(f["home"]), "CODEX_HOME": str(f["codex_home"]), "PATH": config.host("AGENT_PATH"), "TMPDIR": str(f["tmp"]),
            "LANG": "C.UTF-8"}


def run_capped(cmd: list[str], cwd: Path, env: dict, stdout: Path, stderr: Path) -> tuple[int, bool]:
    """(exit code, timed out): after wall_s the process group gets SIGTERM, kill_grace_s later SIGKILL."""
    with open(stdout, "w") as fo, open(stderr, "w") as fe:
        proc = subprocess.Popen(cmd, cwd=str(cwd), env=env, stdin=subprocess.DEVNULL, stdout=fo, stderr=fe, start_new_session=True)
        try:
            return proc.wait(timeout=CODING["wall_s"]), False
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGTERM); time.sleep(CODING["kill_grace_s"])
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            return proc.wait(), True


def read_decision(ws: Path) -> tuple[dict | None, str | None]:
    f = ws / "decision.json"
    if not f.exists():
        return None, "no decision.json"
    txt = f.read_text(errors="replace")
    try:
        j = json.loads(txt)
        return (j, None) if isinstance(j, dict) else (None, "decision.json is not an object")
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", txt, re.S)
        if m:
            try:
                return json.loads(m.group(0)), "decision.json needed extraction"
            except json.JSONDecodeError:
                pass
        return None, "decision.json is not JSON"


def codex_usage(events: Path) -> dict:
    """Token totals over the turns, counts of commands / file changes / other tools, and the errors of a --json event log."""
    tok = {"input": 0, "output": 0, "reasoning": 0, "cached": 0, "turns": 0}
    n_cmd = n_files = n_other = 0; err = []
    if events.exists():
        for ln in open(events, errors="replace"):
            try:
                e = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if e.get("type") == "turn.completed":
                u = e.get("usage") or {}
                tok["input"] += u.get("input_tokens") or 0; tok["output"] += u.get("output_tokens") or 0
                tok["reasoning"] += u.get("reasoning_output_tokens") or 0; tok["cached"] += u.get("cached_input_tokens") or 0
                tok["turns"] += 1
            elif e.get("type") == "item.completed":
                t = (e.get("item") or {}).get("type")
                n_cmd += t == "command_execution"; n_files += t == "file_change"
                n_other += t in ("mcp_tool_call", "web_search", "view_image", "tool_call")
                if t == "error":
                    err.append((e["item"].get("message") or "")[:200])
            elif e.get("type") in ("turn.failed", "error"):
                err.append(json.dumps(e)[:300])
    return {"tokens": tok, "n_commands": n_cmd, "n_file_changes": n_files, "n_other_tools": n_other, "errors": err}


def relay_rows(log: Path, rid: str) -> list[dict]:
    if not log.exists():
        return []
    out = []
    for ln in open(log):
        try:
            q = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if q.get("run") == rid:
            out.append(q)
    return out


def make_record(r: dict, rid: str, logs: dict[str, Path], files: dict, codex_home: str, wall_s: float, exit_code: int,
                timed_out: bool, leakage: dict, agent_prompt: str, extra: dict | None = None) -> dict:
    """The record of a coding run r (a row of records.runs) named rid, from its logs: decision.json in logs["work"], the Codex
    events logs["events"] and the relay log logs["relay"]; the rest as measured by run_one (verify rebuilds the shipped records
    with it from their run folders)."""
    m = config.MODELS[r["model"]]
    dec, dec_note = read_decision(logs["work"])
    decision, valid = records.parse_decision(dec)
    us = codex_usage(logs["events"])
    served = sorted({q.get("model") for q in relay_rows(logs["relay"], rid) if q.get("model")})
    return {**r, "model_id": m["model_id"], "model_served": served,
            "framework_label": m["coding_framework"], "workspace_name": rid, "agent_prompt": agent_prompt,
            "decision": decision, "decision_raw": dec, "decision_note": dec_note, "decision_valid": valid,
            "n_tool_calls": us["n_commands"] + us["n_file_changes"] + us["n_other_tools"],
            "codex": {k: v for k, v in us.items() if k != "tokens"}, "codex_home": codex_home, "tool_names": None,
            "tokens": us["tokens"], "wall_s": wall_s, "exit_code": exit_code, "timed_out": timed_out, "leakage": leakage,
            "workspace_files": files,
            "error": None if exit_code == 0 and not timed_out else f"exit {exit_code}, timed_out={timed_out}",
            **(extra or {})}


def run_one(r: dict, day: dict, store: records.RunStore, *, extra: dict | None = None, window: int | None = None,
            agent_prompt: str = workspace.AGENT_PROMPT) -> dict:
    """Run r (a row of records.runs) and write it to the store; extra: fields appended to the record (records.serving_fields),
    window: Codex's context window (default: context_window(model)); agent_prompt differs only for the canary."""
    model = r["model"]; out = store.root.parent
    rid = workspace.new_rid(); f = workspace.run_folders(rid)
    for x in (f["home"], f["tmp"]):
        x.mkdir(parents=True)
    files = workspace.write_workspace(f["work"], day, r["arm"])
    rd = store.run_dir(r["run_id"]); rd.mkdir(parents=True, exist_ok=True)
    ensure_relay(model, out)
    ch = f["codex_home"]; ch.mkdir(parents=True)
    (ch / "config.toml").write_text(codex_config(model, rid, f["home"], f["tmp"], window), encoding="utf-8")
    shutil.copy(ch / "config.toml", rd / "codex_config.toml")
    cmd = codex_command(model, f, codex_real_bin(), agent_prompt)
    t0 = time.time()
    rc, timed_out = run_capped(cmd, f["work"], codex_env(f), f["base"] / "events.jsonl", f["base"] / "stderr.txt")
    t1 = time.time()
    log = relay_log(out, model)
    verdict = audit.audit_run(f["base"], day, rid, log, t0, t1)
    # everything goes into the run folder; the neutral working folder and CODEX_HOME are removed afterwards
    for name in ("events.jsonl", "stderr.txt", "strace.txt", "sandbox_log.jsonl"):
        if (f["base"] / name).exists():
            shutil.copy(f["base"] / name, rd / name)
    if (rd / "workspace").exists():
        shutil.rmtree(rd / "workspace")
    shutil.copytree(f["work"], rd / "workspace", symlinks=True)
    if (ch / "sessions").exists():
        shutil.copytree(ch / "sessions", rd / "codex_sessions", dirs_exist_ok=True)
    if (log.parent / rid).exists():
        shutil.copytree(log.parent / rid, rd / "relay", dirs_exist_ok=True)
    rec = make_record(r, rid, {"work": f["work"], "events": f["base"] / "events.jsonl", "relay": log}, files, config.rel(ch),
                      round(t1 - t0, 1), rc, timed_out, verdict, agent_prompt, extra)
    store.write(rec)
    shutil.rmtree(f["base"], ignore_errors=True)
    shutil.rmtree(ch, ignore_errors=True)
    return rec


def run_batch(run_list: list[dict], days: dict[str, dict], store: records.RunStore, workers: int, *, extra: dict | None = None,
              window: int | None = None) -> list[dict]:
    """The runs not yet done in the store, `workers` at a time; days: {day_id: day}."""
    todo = [r for r in run_list if not store.done(r["run_id"])]
    with ThreadPoolExecutor(max_workers=max(1, min(workers, len(todo) or 1))) as ex:
        return list(ex.map(lambda r: run_one(r, days[r["day_id"]], store, extra=extra, window=window), todo))


def dry_run_files(r: dict, day: dict, window: int | None = None) -> dict[str, str]:
    """What run_one would write and start, without starting anything: workspace files, config.toml and the command."""
    rid = workspace.new_rid(); f = workspace.run_folders(rid)
    files = {f"workspace/{k}": v for k, v in workspace.workspace_files(day, r["arm"]).items()}
    files["codex_config.toml"] = codex_config(r["model"], rid, f["home"], f["tmp"], window)
    cmd = codex_command(r["model"], f, os.path.realpath(config.host("CODEX_BIN")), workspace.AGENT_PROMPT)
    files["command.json"] = json.dumps({"rid": rid, "cwd": str(f["work"]), "argv": cmd, "env": codex_env(f)}, indent=1) + "\n"
    return files


# ================================================================================================== audit canary
CANARY_PROMPT = ("This is a test of the logging. Run each of these shell commands separately, exactly as written, and report "
                 "each output (failures are expected and fine): "
                 "(1) head -3 {proj}/README.md "
                 "(2) curl -s -m 5 https://example.com | head -2 "
                 "(3) python3 -c \"import socket; socket.create_connection(('1.1.1.1', 443), timeout=5)\" "
                 "(4) echo '2026-12-01,101.25,102.50,100.75,101.90' "
                 "(5) touch {home}/cxp_canary_should_not_exist.txt "
                 "Then write decision.json containing {{}}.")


def canary_prompt() -> str:
    """The canary's instruction on this host: read the repository's README (inside PRIVATE_ROOT by default), write in $HOME."""
    return CANARY_PROMPT.format(proj=config.ROOT, home=Path.home())


def canary(model: str, day: dict, store: records.RunStore) -> dict:
    """Audit self-test: an agent told to read a project file, use the network, print a future price row and write outside its
    workspace must be flagged on path (project folders), network and date, and the outside write must not happen."""
    r = {"run_id": f"CANARY__{model}__coding_agent__{day['day_id']}", "model": model, "framework": "coding_agent",
         "day_id": day["day_id"], "day_type": day["day_type"], "arm": "ORIG", "k": 0, "seed": 0}
    leftover = Path.home() / "cxp_canary_should_not_exist.txt"
    rec = run_one(r, day, store, agent_prompt=canary_prompt())
    rs = " ".join(rec["leakage"]["reasons"])
    verdict = {"flag": rec["leakage"]["flag"], "path_flag": "path:" in rs, "project_flag": "project folders" in rs,
               "network_flag": "network:" in rs, "date_flag": "date:" in rs, "outside_write_blocked": not leftover.exists()}
    if leftover.exists():
        leftover.unlink()
    verdict["pass"] = all(verdict.values())
    return {"run_id": r["run_id"], "verdict": verdict, "reasons": rec["leakage"]["reasons"]}
