"""`finagent serve`: our vLLM server of a local model on 127.0.0.1:<VLLM_PORT_<KEY>>, started, stopped by exact pid, or checked.

Flags, extra environment and weights per model come from setup/models.toml, the serving policy from experiment.toml [vllm]:
  GPU    the card with the most free memory (host setting GPU fixes one), --gpu-memory-utilization = floor((free - reserve) /
         total, 2) (GPU_UTIL fixes it), refused below min_gpu_util; a model with need_free_mib waits for a card that free
  start  retried when another job takes the measured free memory first; a model with max_model_len_fallbacks is retried with the
         next shorter --max-model-len when its KV cache cannot hold one full-length request
  env    an allow-list of the caller's environment (never an API key) plus the cache dirs, a short TMPDIR (vLLM's ZMQ socket
         path must stay under 107 bytes), [vllm].env and the model's env
start() writes <out>/infra/launch_<key>.json (pid, GPU, command, served --max-model-len) and appends to serve_<key>.log; stop()
sends SIGTERM to that pid after checking it is our `vllm serve` on our port, then SIGKILL to it and to its children if needed.

    finagent serve start|stop <model> [--out runs/pilot]      finagent serve status [--out runs/pilot]
"""
from __future__ import annotations

import argparse
import json
import math
import os
import signal
import subprocess
import time
from pathlib import Path

import requests

from finagent import config

V = config.EXPERIMENT["vllm"]
PASS_ENV = ("HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TERM", "SHELL", "LD_LIBRARY_PATH", "CUDA_HOME")
CACHE_ENV = {"TORCHINDUCTOR_CACHE_DIR": "inductor", "TRITON_CACHE_DIR": "triton", "XDG_CACHE_HOME": "xdg", "HF_HOME": "hf"}
GPU_POLL_S, GPU_WAIT_MAX_S = 300, 3 * 3600                                     # waiting for need_free_mib
DEFAULT_OUT = config.RUNS / "pilot"


def local_models() -> list[str]:
    return [k for k, m in config.MODELS.items() if m["provider"] == "vllm"]


def launch_file(key: str, out: Path) -> Path:
    return out / "infra" / f"launch_{key}.json"


def log_file(key: str, out: Path) -> Path:
    return out / "infra" / f"serve_{key}.log"


def url(key: str) -> str:
    return f"http://{V['host']}:{config.port('VLLM', key)}"


# ================================================================================================== GPUs
def gpus() -> list[dict]:
    out = subprocess.run(["nvidia-smi", "--query-gpu=index,uuid,memory.free,memory.used,memory.total", "--format=csv,noheader,nounits"],
                         capture_output=True, text=True, check=True).stdout
    rows = []
    for ln in out.strip().splitlines():
        i, u, f, us, t = [x.strip() for x in ln.split(",")]
        rows.append({"index": int(i), "uuid": u, "free_mib": int(f), "used_mib": int(us), "total_mib": int(t)})
    return rows


def cards() -> list[dict]:
    """The cards we may serve on: GPU (an index or uuid) when set, else all."""
    want = config.host("GPU")
    out = [g for g in gpus() if not want or want in (str(g["index"]), g["uuid"])]
    if not out:
        raise RuntimeError(f"no GPU {want!r}")
    return out


def pick_gpu() -> dict:
    """The card with the most free memory, with its memory utilisation (GPU_UTIL, or computed from its free memory)."""
    best = max(cards(), key=lambda g: g["free_mib"])
    util = config.host("GPU_UTIL")
    best["util"] = float(util) if util else math.floor((best["free_mib"] - V["gpu_reserve_mib"]) / best["total_mib"] * 100) / 100
    if best["util"] < V["min_gpu_util"]:
        raise RuntimeError(f"no GPU with enough free memory: best {best} -> util {best['util']} < {V['min_gpu_util']}")
    return best


def wait_for_gpu(key: str, out: Path) -> None:
    """Wait (polling every GPU_POLL_S, at most GPU_WAIT_MAX_S) until a card has the model's need_free_mib free."""
    need = config.MODELS[key]["vllm"].get("need_free_mib")
    t0 = time.time()
    while need:
        best = max(cards(), key=lambda g: g["free_mib"])
        if best["free_mib"] >= need:
            return
        if time.time() - t0 + GPU_POLL_S > GPU_WAIT_MAX_S:
            raise RuntimeError(f"no GPU had {need} MiB free during {GPU_WAIT_MAX_S / 3600:.0f} h")
        log_file(key, out).parent.mkdir(parents=True, exist_ok=True)
        with open(log_file(key, out), "a") as f:
            f.write(f"===== waiting: best GPU {best['index']} has {best['free_mib']} MiB free < {need}\n")
        time.sleep(GPU_POLL_S)


# ================================================================================================== server
def up(key: str) -> bool:
    """The port answers and serves the model."""
    try:
        ids = [m["id"] for m in requests.get(url(key) + "/v1/models", timeout=5).json()["data"]]
        return config.MODELS[key]["model_id"] in ids
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return False


def port_answers(key: str) -> bool:
    try:
        requests.get(url(key) + "/v1/models", timeout=3)
        return True
    except requests.RequestException:
        return False


def served_max_model_len(key: str) -> int | None:
    """max_model_len as the running server reports it (None when the server does not say)."""
    try:
        data = requests.get(url(key) + "/v1/models", timeout=5).json()["data"]
        return next((m.get("max_model_len") for m in data if m["id"] == config.MODELS[key]["model_id"]), None)
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def serve_flags(key: str, max_model_len: int | None = None) -> list[str]:
    """models.toml's flags, with --max-model-len replaced when given."""
    flags = list(config.MODELS[key]["vllm"]["flags"])
    if max_model_len:
        flags[flags.index("--max-model-len") + 1] = str(max_model_len)
    return flags


def serve_command(key: str, gpu_util: float, max_model_len: int | None = None) -> list[str]:
    m = config.MODELS[key]; venv = Path(config.host("VLLM_ENV"))
    return ([str(venv / "bin" / "python"), str(venv / "bin" / "vllm"), "serve", str(Path(config.host("MODEL_DIR")) / m["vllm"]["weights"]),
             "--served-model-name", m["model_id"], "--port", str(config.port("VLLM", key)), "--host", V["host"],
             "--gpu-memory-utilization", f"{gpu_util:.2f}"] + serve_flags(key, max_model_len))


def serve_env(key: str, gpu_uuid: str) -> dict[str, str]:
    """The server's whole environment: PASS_ENV of ours, never anything else (no API keys, no proxies, no CUDA_VISIBLE_DEVICES)."""
    cache, tmp = Path(config.host("VLLM_CACHE_DIR")), config.host("VLLM_SHORT_TMP")
    env = {k: os.environ[k] for k in PASS_ENV if k in os.environ}
    env.update({"PATH": f"{Path(config.host('VLLM_ENV')) / 'bin'}:{os.environ.get('PATH', '/usr/bin:/bin')}",
                "CUDA_VISIBLE_DEVICES": gpu_uuid, "TMPDIR": tmp, **{k: str(cache / d) for k, d in CACHE_ENV.items()}})
    env.update(V["env"])
    env.update(config.MODELS[key]["vllm"]["env"])
    return env


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    try:                                                                      # an exited child not yet reaped (zombie) is not alive
        state = open(f"/proc/{pid}/stat").read().rsplit(")", 1)[1].split()[0]
        return state not in ("Z", "X")
    except (OSError, IndexError):
        return False


def running(key: str, out: Path) -> dict | None:
    """The launch record of our live server of `key` in `out`, if any."""
    f = launch_file(key, out)
    if not f.exists():
        return None
    st = json.loads(f.read_text())
    return st if "stopped" not in st and alive(st["pid"]) else None


def wait_up(key: str, pid: int) -> None:
    """Wait (ready_wait_s at most) until the server with this pid serves the model, e.g. one still loading."""
    t0 = time.time()
    while not up(key):
        if not alive(pid) or time.time() - t0 > V["ready_wait_s"]:
            raise RuntimeError(f"the vLLM server of {key} (pid {pid}) is not serving")
        time.sleep(10)


def start_once(key: str, out: Path, max_model_len: int | None = None) -> dict:
    if port_answers(key):
        raise RuntimeError(f"port {config.port('VLLM', key)} already answers; not starting a second server (stop it, or use it "
                           "with `finagent run --use-running-server`)")
    other = [k for k in local_models() if k != key and running(k, out)]
    if other:
        raise RuntimeError(f"server {other} still running: the local models are served one after the other")
    g = pick_gpu()
    for d in CACHE_ENV.values():
        os.makedirs(Path(config.host("VLLM_CACHE_DIR")) / d, exist_ok=True)
    os.makedirs(config.host("VLLM_SHORT_TMP"), exist_ok=True)
    m = config.MODELS[key]
    cmd = serve_command(key, g["util"], max_model_len)
    launch_file(key, out).parent.mkdir(parents=True, exist_ok=True)
    with open(log_file(key, out), "a") as log:
        log.write(f"===== start {time.ctime()} {key} gpu {g['index']} {g['uuid']} free {g['free_mib']} util {g['util']}\n"); log.flush()
        proc = subprocess.Popen(cmd, cwd=config.host("MODEL_DIR"), env=serve_env(key, g["uuid"]), stdout=log, stderr=subprocess.STDOUT,
                                stdin=subprocess.DEVNULL, start_new_session=True)
    flags = serve_flags(key, max_model_len)
    st = {"key": key, "model": m["model_id"], "pid": proc.pid, "gpu": g, "cmd": cmd, "port": config.port("VLLM", key),
          "max_model_len": int(flags[flags.index("--max-model-len") + 1]), "started": time.time(), "extra_env": m["vllm"]["env"]}
    launch_file(key, out).write_text(json.dumps(st, indent=1))
    t0 = time.time()
    while time.time() - t0 < V["ready_wait_s"]:
        if proc.poll() is not None:
            raise RuntimeError(f"vLLM exited with {proc.returncode}; see {log_file(key, out)}")
        if up(key):
            st["ready_after_s"] = round(time.time() - t0, 1)
            launch_file(key, out).write_text(json.dumps(st, indent=1))
            return st
        time.sleep(10)
    raise RuntimeError(f"vLLM not ready after {V['ready_wait_s']} s (pid {proc.pid} left running; stop it with `finagent serve stop {key}`)")


def _log_tail(key: str, out: Path) -> str:
    return log_file(key, out).read_text(errors="replace")[-30000:]


def start(key: str, out: Path) -> dict:
    """start_once(), retried after another job took the free memory (start_attempts) and, for a model with
    max_model_len_fallbacks, with the next shorter --max-model-len when the KV cache cannot hold one full-length request."""
    wait_for_gpu(key, out)
    lengths = config.MODELS[key]["vllm"].get("max_model_len_fallbacks") or [None]
    for n in lengths:
        for attempt in range(V["start_attempts"]):
            try:
                return start_once(key, out, n)
            except RuntimeError as e:
                if "vLLM exited" not in str(e):
                    raise
                tail = _log_tail(key, out)
                if "less than desired GPU memory utilization" in tail and attempt + 1 < V["start_attempts"]:
                    with open(log_file(key, out), "a") as f:
                        f.write(f"===== attempt {attempt + 1} lost the free memory to another process; re-measuring\n")
                    time.sleep(30)
                    continue
                if n is not None and ("max seq len" in tail or "KV cache" in tail and "larger than the available" in tail):
                    break                                                     # the next shorter --max-model-len
                raise
    raise RuntimeError(f"vLLM {key} could not start at any --max-model-len of {lengths}")


def children(pid: int) -> list[int]:
    out, todo = [], [pid]
    while todo:
        p = todo.pop()
        try:
            kids = open(f"/proc/{p}/task/{p}/children").read().split()
        except OSError:
            kids = []
        for k in kids:
            out.append(int(k)); todo.append(int(k))
    return out


def stop(key: str, out: Path, wait_s: int = 180) -> dict:
    f = launch_file(key, out)
    if not f.exists():
        return {"key": key, "state": "never started"}
    st = json.loads(f.read_text())
    pid = st["pid"]
    if not alive(pid):
        return {"key": key, "pid": pid, "state": "not running"}
    cmdline = open(f"/proc/{pid}/cmdline").read().replace("\0", " ")
    if os.stat(f"/proc/{pid}").st_uid != os.getuid() or "serve" not in cmdline or f"--port {st['port']}" not in cmdline:
        raise RuntimeError(f"pid {pid} is not our vLLM server on port {st['port']}: {cmdline[:200]}")
    kids = children(pid)
    os.kill(pid, signal.SIGTERM)
    t0 = time.time()
    while alive(pid) and time.time() - t0 < wait_s:
        time.sleep(2)
    if alive(pid):
        os.kill(pid, signal.SIGKILL)
    time.sleep(3)
    killed = []
    for k in kids:
        if alive(k):
            try:
                if os.stat(f"/proc/{k}").st_uid == os.getuid():
                    os.kill(k, signal.SIGKILL); killed.append(k)
            except (ProcessLookupError, FileNotFoundError):
                pass
    st["stopped"] = time.time(); st["children_killed_after_term"] = killed
    f.write_text(json.dumps(st, indent=1))
    return {"key": key, "pid": pid, "state": "stopped", "children_killed": killed}


def status(out: Path) -> dict:
    res = {}
    for k in local_models():
        f = launch_file(k, out)
        st = json.loads(f.read_text()) if f.exists() else None
        res[k] = {"launch": {x: st.get(x) for x in ("pid", "port", "max_model_len", "started", "stopped")} if st else None,
                  "pid_alive": alive(st["pid"]) if st else False, "serving": up(k)}
    return res


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent serve", description="Start, stop or check our vLLM server of a local model "
                                 "(127.0.0.1:VLLM_PORT_<KEY>).", epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("start", "stop", "status"), help="start or stop one model's server, or show all of them")
    ap.add_argument("model", nargs="?", choices=local_models(), help="the local model (start and stop)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output folder whose infra/ holds the launch record and log")
    a = ap.parse_args(argv)
    if a.action == "status":
        print(json.dumps(status(a.out), indent=1))
        return 0
    if not a.model:
        ap.error(f"{a.action} needs a model")
    print(json.dumps(start(a.model, a.out) if a.action == "start" else stop(a.model, a.out), indent=1))
    return 0
