"""`finagent run` and `finagent smoke`: cells of the pilot (model x framework) into an output folder, resumably.

  <out>/raw/<run_id>/   one folder per finished run (record.json and the run's logs)   <out>/raw.jsonl   one record per line
  <out>/relay/<model>/  the coding agents' relay logs                                  <out>/infra/      relay / vLLM state, logs
  <out>/run_log.txt     start and end of every batch
A run whose record.json exists is skipped, so an interrupted command resumes when it is run again. Every per-model setting
(token caps, kept raw answers, Qwen3.8-27B's extra record fields, concurrency) comes from setup/.
Order as in the pilot: the API models one after the other in a background thread while the local models are served one after
the other (vLLM started, the model's batches, relay and server stopped). A model's harness and coding-agent batches run side by
side, except for the models in [concurrency].sequential (harness first).
"""
from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import threading
import time
import traceback
from pathlib import Path

from finagent import config, days, records, serve
from finagent.coding import codex, sandbox
from finagent.harness import agent
from finagent.harness.prompts import SYSTEM, harness_prompt

CONCURRENCY = config.EXPERIMENT["concurrency"]
_LOG_LOCK = threading.Lock()


def log(out: Path, msg: str) -> None:
    line = f"{time.strftime('%Y-%m-%d %H:%M:%S')} {msg}"
    out.mkdir(parents=True, exist_ok=True)
    with _LOG_LOCK, open(out / "run_log.txt", "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def guarded(out: Path, what: str, fn) -> None:
    """fn() with its start, end (runs, valid, flagged) or failure in the run log; a failure does not stop the other batches."""
    t0 = time.time(); log(out, f"start {what}")
    try:
        recs = fn() or []
        log(out, f"done {what}: {len(recs)} runs in {time.time() - t0:.0f} s, valid {sum(bool(r.get('decision_valid')) for r in recs)}, "
                 f"flagged {sum(bool((r.get('leakage') or {}).get('flag')) for r in recs)}")
    except Exception as e:                                                    # noqa: BLE001  (logged; the other batches go on)
        log(out, f"FAILED {what}: {type(e).__name__}: {e}\n{traceback.format_exc()[-2000:]}")


# ================================================================================================== the local server
def ensure_server(model: str, out: Path, use_running: bool) -> dict:
    """{max_model_len, gpu_index, started} of the model's vLLM server: ours from `out` if it runs, a server already listening
    on the port with use_running, else a new one (started = True: stopped again afterwards)."""
    st = serve.running(model, out)
    if st:
        serve.wait_up(model, st["pid"])
        return {"max_model_len": st["max_model_len"], "gpu_index": st["gpu"]["index"], "started": False}
    if use_running:
        if not serve.up(model):
            raise RuntimeError(f"no server of {model} answers at {serve.url(model)}")
        return {"max_model_len": serve.served_max_model_len(model), "gpu_index": None, "started": False}
    log(out, f"{model}: starting vLLM")
    st = serve.start(model, out)
    log(out, f"{model}: vLLM ready on GPU {st['gpu']['index']} (pid {st['pid']}, --max-model-len {st['max_model_len']})")
    return {"max_model_len": st["max_model_len"], "gpu_index": st["gpu"]["index"], "started": True}


@contextlib.contextmanager
def model_up(model: str, out: Path, use_running: bool, coding: bool):
    """The model's server (None for an API model) for the duration of its batches; afterwards its relay and the server we
    started are stopped (by exact pid)."""
    srv = ensure_server(model, out, use_running) if config.MODELS[model]["provider"] == "vllm" else None
    try:
        yield srv
    finally:
        if coding:
            try:
                log(out, f"{model}: relay {codex.stop_relay(model, out)}")
            except Exception as e:                                            # noqa: BLE001
                log(out, f"{model}: relay stop failed: {e}")
        if srv and srv["started"]:
            log(out, f"{model}: vLLM {serve.stop(model, out)}")


# ================================================================================================== batches
def run_model(model: str, runs: list[dict], by_day: dict[str, dict], out: Path, use_running: bool) -> None:
    store = records.RunStore(out / "raw")
    todo = {fw: [r for r in runs if r["model"] == model and r["framework"] == fw and not store.done(r["run_id"])]
            for fw in config.FRAMEWORKS}
    todo = {fw: rl for fw, rl in todo.items() if rl}
    if not todo:
        log(out, f"{model}: nothing to run")
        return
    with model_up(model, out, use_running, "coding_agent" in todo) as srv:
        served = srv["max_model_len"] if srv else None

        def batch(fw: str, rl: list[dict]):
            extra = records.serving_fields(model, fw, served, srv["gpu_index"]) if srv else {}
            workers = CONCURRENCY[fw][model]
            if fw == "harness":
                return agent.run_batch(rl, by_day, store, workers, extra)
            return codex.run_batch(rl, by_day, store, workers, extra=extra, window=codex.context_window(model, served))
        threads = [threading.Thread(target=guarded, args=(out, f"{model} {fw} ({len(rl)} runs)", lambda fw=fw, rl=rl: batch(fw, rl)))
                   for fw, rl in todo.items()]
        sequential = model in CONCURRENCY["sequential"]
        for t in threads:
            t.start()
            if sequential:
                t.join()
        for t in threads:
            t.join()


def run_all(runs: list[dict], by_day: dict[str, dict], out: Path, use_running: bool) -> None:
    def one(model: str) -> None:
        try:
            run_model(model, runs, by_day, out, use_running)
        except Exception as e:                                                # noqa: BLE001  (logged; the other models go on)
            log(out, f"FAILED {model}: {type(e).__name__}: {e}\n{traceback.format_exc()[-2000:]}")
    models = list(dict.fromkeys(r["model"] for r in runs))
    api = threading.Thread(target=lambda: [one(m) for m in models if config.MODELS[m]["provider"] != "vllm"])
    api.start()
    for m in models:
        if config.MODELS[m]["provider"] == "vllm":
            one(m)
    api.join()


# ================================================================================================== plan, dry run, host checks
def harness_dry_run_files(r: dict, day: dict) -> dict[str, str]:
    """The harness run's system prompt, first user message and request settings."""
    m = config.MODELS[r["model"]]
    url = (f"http://{config.EXPERIMENT['vllm']['host']}:{config.port('VLLM', r['model'])}/v1/chat/completions"
           if m["provider"] == "vllm" else m["harness"]["endpoint"])
    settings = {"provider": m["provider"], "url": url, "model_id": m["model_id"],
                "seed": r["seed"] if m["provider"] == "vllm" else None, "harness": m["harness"]}
    return {"system.txt": SYSTEM, "prompt.txt": harness_prompt(day, r["arm"]), "settings.json": json.dumps(settings, indent=1) + "\n"}


def dry_run(runs: list[dict], by_day: dict[str, dict], out: Path) -> None:
    """Write what every run would get into <out>/dry_run/<run_id>/ and print the plan; no model, relay or server is contacted."""
    store, root = records.RunStore(out / "raw"), out / "dry_run"
    for r in runs:
        day = by_day[r["day_id"]]
        files = (harness_dry_run_files(r, day) if r["framework"] == "harness"
                 else codex.dry_run_files(r, day, codex.context_window(r["model"])))
        for name, text in files.items():
            p = root / r["run_id"] / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(text, encoding="utf-8")
    print(f"{'model':<12} {'framework':<13} {'runs':>5} {'done':>5} {'to run':>7}")
    for m in dict.fromkeys(r["model"] for r in runs):
        for fw in config.FRAMEWORKS:
            rl = [r for r in runs if r["model"] == m and r["framework"] == fw]
            if rl:
                done = sum(store.done(r["run_id"]) for r in rl)
                print(f"{m:<12} {fw:<13} {len(rl):>5} {done:>5} {len(rl) - done:>7}")
    print(f"inputs of {len(runs)} runs written to {root}")
    for line in host_checks(runs):
        print(line)


def vllm_version(env: Path) -> str | None:
    """The vllm version installed in the venv `env` (its dist-info folder), or None."""
    found = sorted(env.glob("lib/python3*/site-packages/vllm-*.dist-info"))
    return found[-1].name.removeprefix("vllm-").removesuffix(".dist-info") if found else None


def host_checks(runs: list[dict]) -> list[str]:
    """What this host still lacks for the runs (nothing is started; API keys are only checked for presence)."""
    checks = []
    cells = {(r["model"], r["framework"]) for r in runs}
    for model in dict.fromkeys(r["model"] for r in runs):
        m = config.MODELS[model]
        if m["provider"] == "vllm":
            env, want = Path(config.host("VLLM_ENV")), config.EXPERIMENT["vllm"]["version"]
            checks.append((f"vllm {want} in VLLM_ENV", (env / "bin" / "vllm").exists() and vllm_version(env) == want))
            checks.append((f"{model} weights in MODEL_DIR", (Path(config.host("MODEL_DIR")) / m["vllm"]["weights"]).is_dir()))
        else:
            checks.append((f"{m['api_key_env']} set", bool(os.environ.get(m["api_key_env"]))))
    if any(fw == "coding_agent" for _, fw in cells):
        try:
            codex.codex_real_bin(); ok = True
        except (OSError, RuntimeError):
            ok = False
        checks += [(f"{config.EXPERIMENT['coding_agent']['codex_version']} at CODEX_BIN", ok),
                   ("strace on PATH", shutil.which("strace") is not None),
                   ("SANDBOX_PYTHON", Path(config.host("SANDBOX_PYTHON")).exists()),
                   ("Landlock ABI >= 4", sandbox.landlock_abi() >= 4),
                   ("agent python env (AGENT_PYENV)", (Path(config.host("AGENT_PYENV")) / "bin" / "python").exists())]
    return [f"  host check  {'ok     ' if ok else 'MISSING'}  {what}" for what, ok in dict(checks).items()]


def require_keys(runs: list[dict]) -> None:
    """Refuse to start when an API model's key is missing (each of its harness runs would otherwise be recorded as failed)."""
    missing = sorted({config.MODELS[r["model"]].get("api_key_env") for r in runs} - {None} - set(k for k in os.environ if os.environ[k]))
    if missing:
        raise SystemExit(f"set {', '.join(missing)} in the environment first")


# ================================================================================================== command line
def _common_args(ap: argparse.ArgumentParser, default_out: Path) -> None:
    ap.add_argument("--model", required=True, help=f"model key(s), comma-separated, or 'all' ({', '.join(config.MODELS)})")
    ap.add_argument("--framework", default="all", help=f"framework(s), comma-separated, or 'all' (default: {', '.join(config.FRAMEWORKS)})")
    ap.add_argument("--out", type=Path, default=default_out, help=f"output folder (default: {config.rel(default_out)})")
    ap.add_argument("--use-running-server", action="store_true",
                    help="a local model's server already listens on its VLLM_PORT_<KEY>: use it, neither start nor stop one")
    ap.add_argument("--dry-run", action="store_true", help="write every run's inputs to <out>/dry_run and print the plan only")


def _keys(text: str, allowed, what: str) -> list[str]:
    keys = list(allowed) if text == "all" else [x for x in text.split(",") if x]
    bad = [k for k in keys if k not in allowed]
    if bad:
        raise SystemExit(f"unknown {what}: {', '.join(bad)} (choose from {', '.join(allowed)})")
    return keys


def _finish(runs: list[dict], out: Path) -> int:
    store = records.RunStore(out / "raw")
    n = sum(store.done(r["run_id"]) for r in runs)
    log(out, f"{n} of {len(runs)} selected runs have a record in {out / 'raw'}")
    return 0 if n == len(runs) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent run", description="Run model x framework cells of the pilot into --out "
                                 "(resumable).", epilog=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    _common_args(ap, serve.DEFAULT_OUT)
    ap.add_argument("--days", default="all", help="day ids, comma-separated (default: all 6)")
    ap.add_argument("--arms", default="all", help=f"arms, comma-separated (default: all of {', '.join(config.ARMS)})")
    a = ap.parse_args(argv)
    by_day = {d["day_id"]: d for d in days.load()}
    want_days, want_arms = set(_keys(a.days, by_day, "day")), set(_keys(a.arms, config.ARMS, "arm"))
    runs = [r for r in records.runs(list(by_day.values()), _keys(a.model, config.MODELS, "model"),
                                    _keys(a.framework, config.FRAMEWORKS, "framework"))
            if r["day_id"] in want_days and r["arm"] in want_arms]
    if a.dry_run:
        dry_run(runs, by_day, a.out)
        return 0
    require_keys(runs)
    log(a.out, f"run: {len(runs)} runs -> {a.out / 'raw'}")
    run_all(runs, by_day, a.out, a.use_running_server)
    return _finish(runs, a.out)


def smoke_selection(runs: list[dict], models: list[str], frameworks: list[str], day: str | None) -> list[dict]:
    """One run per model x framework: the ORIG k = 0 run on `day`, or (no day) the pilot's rotation over day and arm."""
    sel = []
    for i, (m, fw) in enumerate((m, fw) for m in models for fw in frameworks):
        cand = [r for r in runs if r["model"] == m and r["framework"] == fw]
        sel.append(next(r for r in cand if r["day_id"] == day and r["arm"] == "ORIG" and r["k"] == 0) if day
                   else cand[(7 * i) % len(cand)])
    return sel


def smoke(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent smoke", description="One smoke run per model x framework (or the audit canary) "
                                 "into <out>/raw, before a batch.")
    _common_args(ap, config.RUNS / "smoke")
    ap.add_argument("--day", default=None, help="run the ORIG k=0 run of this ordinary day (default: the pilot's rotation)")
    ap.add_argument("--canary", action="store_true",
                    help="instead: the audit canary (coding agent) per model on --day (default: the first ordinary day); "
                         "it must be flagged on path, network and date, and its outside write must be blocked")
    a = ap.parse_args(argv)
    by_day = {d["day_id"]: d for d in days.load()}
    if a.day and (a.day not in by_day or by_day[a.day]["day_type"] != "ordinary"):
        raise SystemExit(f"{a.day} is not one of the ordinary pilot days")
    models, frameworks = _keys(a.model, config.MODELS, "model"), _keys(a.framework, config.FRAMEWORKS, "framework")
    if a.canary and a.framework != "all":
        raise SystemExit("--canary is a coding-agent run; drop --framework")
    if a.canary:
        day = by_day[a.day or next(d for d, x in by_day.items() if x["day_type"] == "ordinary")]
        return canaries(models, day, a.out, a.use_running_server, a.dry_run)
    runs = smoke_selection(records.runs(list(by_day.values()), models, frameworks), models, frameworks, a.day)
    if a.dry_run:
        dry_run(runs, by_day, a.out)
        return 0
    require_keys(runs)
    log(a.out, f"smoke: {[r['run_id'] for r in runs]} -> {a.out / 'raw'}")
    run_all(runs, by_day, a.out, a.use_running_server)
    return _finish(runs, a.out)


def canaries(models: list[str], day: dict, out: Path, use_running: bool, dry: bool) -> int:
    """The audit canary of each model, one after the other; verdicts in <out>/audit_canary.json."""
    if dry:
        print(f"audit canary of {', '.join(models)} on {day['day_id']} -> {out / 'raw'}; prompt:\n"
              + codex.canary_prompt())
        for line in host_checks([{"model": m, "framework": "coding_agent"} for m in models]):
            print(line)
        return 0
    require_keys([{"model": m} for m in models])
    store, verdicts = records.RunStore(out / "raw"), []
    for m in models:
        with model_up(m, out, use_running, coding=True):
            verdicts.append(codex.canary(m, day, store))
        log(out, f"canary {m}: {verdicts[-1]['verdict']}")
    (out / "audit_canary.json").write_text(json.dumps(verdicts, indent=1))
    return 0 if all(v["verdict"]["pass"] for v in verdicts) else 1
