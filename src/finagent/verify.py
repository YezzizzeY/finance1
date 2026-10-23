"""`finagent verify` ties every shipped byte to the code; `finagent unpack` extracts the run records it reads.

  L0  the repository alone: data/ and the record archives against their sha256 lists; the prompts, readings blocks, arm
      rewrites and tool outputs against what the original code produced (tests/fixtures/, records/infra/checks/);
      data/mechanisms/ against its own sha256 list
  L1  the unpacked records (records/raw): each record against runs.jsonl, the run plan and its own logs; outcomes from the
      panel; a replay of every harness tool call; the Codex configs and command lines; results/ recomputed byte for byte;
      the four mechanism analyses, their page and the good-thinking theory document rebuilt byte for byte (these read
      data/mechanisms/, data/panel/ and docs/good_thinking/, not the records, but are results like the others)
  L2  the leakage audit of the coding-agent runs and of the audit canary, re-run with the original host's settings
Each check returns (ok, detail); `finagent verify [--level L0|L1|L2|all]` prints one row per check and exits 1 on a failure.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import re
import shutil
import tarfile
import time
from collections import Counter
from collections.abc import Callable
from datetime import datetime
from functools import cache
from pathlib import Path

from finagent import analysis, arms, config, days, promptgen, readings, records
from finagent.analysis import figures
from finagent.coding import audit, codex, workspace
from finagent.data.anchors import load_anchor, state_from_json
from finagent.data.outcomes import Outcomes
from finagent.data.pit import news_cache
from finagent.harness import agent, session, toolbox
from finagent.harness.prompts import REMINDER, SYSTEM, build_day_payload, harness_prompt, render_prompt, sha256
from finagent.mechanisms import page as mech_page
from finagent.mechanisms import position_adjustment, proximity, salience, theory_doc, thinking

LEVELS = ("L0", "L1", "L2")
FIXTURES = config.ROOT / "tests" / "fixtures"
RAW = config.RAW                                                 # `finagent unpack` puts the run folders here
MEMBERS = config.RECORDS / "MEMBERS.sha256"                      # every file of every archive, as raw/... under records/
RELAY_LOGS = config.RECORDS / "infra" / "relay"                  # <model>/requests.jsonl
BUILD_CHECKS = config.RECORDS / "infra" / "checks"
CUT = session.TOOL_RESULT_CHARS

Check = Callable[[], tuple[bool, str]]
CHECKS: list[tuple[str, str, Check]] = []                        # (level, name, check) in run order


def check(level: str, name: str):
    """Register a check under level and name."""
    def add(fn: Check) -> Check:
        CHECKS.append((level, name, fn))
        return fn
    return add


# ================================================================================================== helpers
def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_sums(path: Path) -> dict[str, str]:
    """{relative path: sha256} of a sha256sum file."""
    return {name: digest for digest, _, name in (ln.partition("  ") for ln in path.read_text().splitlines())}


def sum_problems(root: Path, sums: dict[str, str]) -> list[str]:
    """The listed paths under root that are missing or whose sha256 differs."""
    return [name for name, digest in sums.items() if not (root / name).is_file() or file_sha256(root / name) != digest]


def files_under(root: Path) -> set[str]:
    return {p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()}


def same_bytes(path: Path, text: str) -> bool:
    return path.is_file() and path.read_bytes() == text.encode("utf-8")


def listed(items, label: str) -> str:
    """'; <label>: a, b, c (+n more)' for a non-empty collection, else ''."""
    items = sorted(map(str, items))
    if not items:
        return ""
    return f"; {label}: " + ", ".join(items[:3]) + (f" (+{len(items) - 3} more)" if len(items) > 3 else "")


def tally(c: Counter) -> str:
    return ", ".join(f"{k} {v}" for k, v in sorted(c.items()))


@cache
def fixture(name: str):
    """A file of tests/fixtures/ (outputs and hashes recorded from the original code)."""
    path = FIXTURES / name
    with (gzip.open(path, "rt", encoding="utf-8") if path.suffix == ".gz" else open(path, encoding="utf-8")) as f:
        return json.load(f)


@cache
def pilot_days() -> dict[str, dict]:
    return {d["day_id"]: d for d in days.load()}


def as_of(day: dict) -> datetime:
    return datetime.strptime(day["t"], "%Y-%m-%d")


def close_price(day: dict) -> float:
    return news_cache(day["ticker"]).candles(as_of(day))[0]["close"]


@cache
def _anchor(day_id: str) -> dict:
    return load_anchor(day_id)["state"]


def fresh_state(day_id: str) -> dict:
    """A fresh copy of the day's saved starting state (as data.anchors.anchor_state, with the file read once)."""
    return state_from_json(_anchor(day_id))


@cache
def prompt_files() -> dict[str, str]:
    return promptgen.prompt_files()


def example(day_id: str, arm: str) -> str:
    """The harness day prompt of (day, arm), as in data/prompts/examples/."""
    return prompt_files()[f"examples/{day_id}/{arm}/harness_prompt.txt"]


@cache
def given_files(day_id: str, arm: str) -> dict[str, str]:
    """The workspace files a coding run of (day, arm) is given."""
    return workspace.workspace_files(pilot_days()[day_id], arm)


def call_tool(day: dict, arm: str, name: str, args: dict, state: dict) -> str:
    """A tool's output as a harness session of `arm` on `day` receives it, before the cut: the toolbox on a fresh view of the
    stock's cache, then the arm's rewrite of a block tool's output."""
    _, rewrite = agent.arm_hooks(agent.new_context(arm, day))
    return rewrite(name, toolbox.run_tool(news_cache(day["ticker"]).view(), as_of(day), name, dict(args), state))


@cache
def planned() -> dict[str, dict]:
    """run_id -> the row of records.runs of every planned run of the pilot."""
    return {r["run_id"]: r for r in records.runs(list(pilot_days().values()))}


@cache
def shipped_records() -> dict[str, dict]:
    """run_id -> record.json of the 300 run folders in records/raw (the smoke folders sit one level deeper)."""
    return {p.parent.name: json.loads(p.read_text(encoding="utf-8")) for p in sorted(RAW.glob("*/record.json"))}


def shipped(framework: str) -> dict[str, dict]:
    return {rid: r for rid, r in shipped_records().items() if r["framework"] == framework}


def relay_log(model: str) -> Path:
    return RELAY_LOGS / model / "requests.jsonl"


# ================================================================================================== L0: the repository alone
@check("L0", "data files")
def data_files() -> tuple[bool, str]:
    """data/MANIFEST.sha256 covers every input the pilot reads; data/prompts/ (checked by "prompts folder" below,
    against `finagent prompts`'s own regeneration), data/evidence_relations/ (not an input the pilot reads,
    verified on its own, not by `finagent verify` -- see docs/EVIDENCE_RELATIONS.md) and data/mechanisms/ (its own
    manifest, checked by "mechanism data" below) live under data/ too but are out of this check's scope, same as
    before they were nested here."""
    sums = read_sums(config.DATA / "MANIFEST.sha256")
    bad = sum_problems(config.DATA, sums)
    extra = {p for p in files_under(config.DATA) - set(sums)
             if p not in {"README.md", "MANIFEST.sha256"}
             and not p.startswith(("prompts/", "evidence_relations/", "mechanisms/"))}
    return not bad and not extra, (f"{len(sums) - len(bad)} of {len(sums)} files match data/MANIFEST.sha256"
                                   + listed(bad, "differ") + listed(extra, "not listed"))


@check("L0", "record archives")
def record_archives() -> tuple[bool, str]:
    sums = read_sums(config.RECORDS / "SHA256SUMS")
    bad = sum_problems(config.RECORDS, sums)
    extra = {p for p in files_under(config.RECORDS) if not p.startswith("raw/")} - set(sums) - {"SHA256SUMS"}
    n_archives = sum(name.startswith("archives/") for name in sums)
    return not bad and not extra, (f"{len(sums) - len(bad)} of {len(sums)} files ({n_archives} archives, runs.jsonl, infra/) "
                                   "match records/SHA256SUMS" + listed(bad, "differ") + listed(extra, "not listed"))


@check("L0", "prompt texts")
def prompt_texts() -> tuple[bool, str]:
    want = fixture("expected_hashes.json")
    texts = {"harness_system": SYSTEM, "coding_system": workspace.coding_system_text(), "agent_prompt": workspace.AGENT_PROMPT,
             "permissions": codex.PERMISSIONS_TEXT, "reminder": REMINDER}
    bad = [k for k, text in texts.items() if {"chars": len(text), "sha256": sha256(text)} != want["texts"][k]]
    tools = toolbox.build_tools()
    tools_sha = sha256(json.dumps(tools, sort_keys=True))
    ok = not bad and len(tools) == want["n_tools"] and tools_sha == want["tools_sha256"]
    return ok, (f"{len(texts) - len(bad)} of {len(texts)} texts match (system {sha256(SYSTEM)[:8]}, coding system "
                f"{sha256(texts['coding_system'])[:8]}); {len(tools)} tool schemas {tools_sha[:8]}" + listed(bad, "differ"))


@check("L0", "example prompts")
def example_prompts() -> tuple[bool, str]:
    want = fixture("expected_hashes.json")["examples"]
    got = {k.removeprefix("examples/"): sha256(v) for k, v in prompt_files().items() if k.startswith("examples/")}
    bad = [k for k in want if got.get(k) != want[k]] + sorted(set(got) - set(want))
    return not bad, (f"{len(want) - len(bad)} of {len(want)} rebuilt workspace files and day prompts (6 days x 4 arms) "
                     "match the original hashes" + listed(bad, "differ"))


@check("L0", "prompts folder")
def prompts_folder() -> tuple[bool, str]:
    files = prompt_files()
    bad = [rel for rel, text in files.items() if not same_bytes(config.PROMPTS / rel, text)]
    extra = files_under(config.PROMPTS) - set(files) - {"README.md"}
    return not bad and not extra, (f"{len(files) - len(bad)} of {len(files)} files in data/prompts/ equal `finagent prompts`"
                                   + listed(bad, "differ") + listed(extra, "not generated"))


@check("L0", "grounding sessions")
def grounding_sessions() -> tuple[bool, str]:
    bad = []
    for did in pilot_days():
        first = records.load_gz(config.grounding_session_file(did))["trace"][0]
        if (first["system"], first["user"]) != (SYSTEM, example(did, "ORIG")):
            bad.append(did)
    n = len(pilot_days())
    return not bad, (f"{n - len(bad)} of {n} saved grounding sessions (FULL_G_0) have the ORIG system prompt and day prompt"
                     + listed(bad, "differ"))


@check("L0", "readings blocks")
def readings_blocks() -> tuple[bool, str]:
    want = fixture("expected_hashes.json")["days"]
    bad, n_arms = [], 0
    for did, d in pilot_days().items():
        reg = readings.registered_blocks()[did]
        block = readings.compute_block(news_cache(d["ticker"]), d["t"])
        by_arm = {arm: sha256(arms.rewrite_block(block, arm)) for arm in config.ARMS}
        n_arms += sum(by_arm[arm] == want[did]["block_sha256_by_arm"][arm] for arm in config.ARMS)
        hashes = {sha256(block), reg["sha256"], d["check"]["block_sha256"]}
        if block != reg["block"] or hashes != {want[did]["block_sha256"]} or by_arm != want[did]["block_sha256_by_arm"]:
            bad.append(did)
    n = len(pilot_days())
    return not bad, (f"{n - len(bad)} of {n} blocks recomputed from data/ equal the registered ones; {n_arms} of "
                     f"{n * len(config.ARMS)} arm forms match" + listed(bad, "differ"))


@check("L0", "day selection")
def day_selection() -> tuple[bool, str]:
    want = fixture("expected_hashes.json")["days"]
    same = json.dumps(days.build(), indent=1) == config.DAYS_FILE.read_text()
    bad = []
    for did, d in pilot_days().items():
        w = want[did]
        recorded = (d["ticker"], d["t"], d["D"], news_cache(d["ticker"]).decision_time(as_of(d)), d["anchor_sha256"])
        if recorded != (w["ticker"], w["t"], w["decision_time"], w["decision_time"], w["anchor_sha256"]):
            bad.append(did)
    return same and not bad, (f"rebuilt from data/selection and data/anchors: {'identical to' if same else 'DIFFERS from'} "
                              f"data/days.json; {len(want) - len(bad)} of {len(want)} days have the original t, D(t) and "
                              "anchor sha256" + listed(bad, "differ"))


@check("L0", "arm rewrites")
def arm_rewrites() -> tuple[bool, str]:
    ds = list(pilot_days().values())
    got = arms.check_all(ds, {(d["day_id"], arm): example(d["day_id"], arm) for d in ds for arm in config.ARMS})
    want = fixture("expected_hashes.json")["rewrite_check"]
    same = got == json.loads((BUILD_CHECKS / "rewrite_check.json").read_text())
    ok = got["pass"] and same and {k: got[k] for k in want} == want
    return ok, (f"{got['n_checks']} checks, {got['n_with_problems']} with problems; every row "
                f"{'equals' if same else 'DIFFERS from'} records/infra/checks/rewrite_check.json")


@check("L0", "golden tool outputs")
def golden_tool_outputs() -> tuple[bool, str]:
    g = fixture("golden_tools.json.gz")
    ds, bad = pilot_days(), Counter()
    for c in g["calls"]:
        state = fresh_state(c["day_id"])["tb_state"]
        out = call_tool(ds[c["day_id"]], c["arm"], c["tool"], c["args"], state)
        state_ok = state == c.get("state_after", fresh_state(c["day_id"])["tb_state"])
        bad[c["tool"]] += (out, out[:CUT]) != (c["output_raw"], c["output_cut"]) or not state_ok
    n_steps = 0
    for s in g["sequences"]:
        state = fresh_state(s["day_id"])["tb_state"]
        for c in s["calls"]:
            n_steps += 1
            out = call_tool(ds[s["day_id"]], s["arm"], c["tool"], c["args"], state)
            bad["sequence " + c["tool"]] += (out, out[:CUT]) != (c["output_raw"], c["output_cut"])
        bad["sequence state"] += state != s["state_after"]
    for e in g["submit_echoes"]:
        book, price = fresh_state(e["day_id"])["portfolio"], close_price(ds[e["day_id"]])
        bad["submit_decision"] += session.submit_reply(e["args"], book, price) != e["echo"]
    bad = +bad
    per = len(g["calls"]) // len({(c["day_id"], c["arm"]) for c in g["calls"]})
    return not bad, (f"{len(g['calls'])} calls ({per} per day and arm), {len(g['sequences'])} stateful sequences ({n_steps} calls), "
                     f"{len(g['submit_echoes'])} submit replies: {sum(bad.values())} differences"
                     + (f" ({tally(bad)})" if bad else ""))


@check("L0", "mechanism data")
def mechanism_data() -> tuple[bool, str]:
    """data/mechanisms/MANIFEST.sha256 covers every file there but itself and the README.md files: the two session
    corpora (newsagent, q3news_s1), the grounding sessions and the copied inputs of the four mechanism analyses."""
    root = config.MECHANISMS_DATA
    sums = read_sums(root / "MANIFEST.sha256")
    bad = sum_problems(root, sums)
    extra = {p for p in files_under(root) - set(sums) if p != "MANIFEST.sha256" and not p.endswith("README.md")}
    folders = Counter(name.split("/")[0] + ("/" + name.split("/")[1] if name.startswith("sessions/") else "")
                      for name in sums)
    return not bad and not extra, (f"{len(sums) - len(bad)} of {len(sums)} files match data/mechanisms/MANIFEST.sha256 "
                                   f"({tally(folders)})" + listed(bad, "differ") + listed(extra, "not listed"))


# ================================================================================================== L1: the unpacked records
@check("L1", "unpacked files")
def unpacked_files() -> tuple[bool, str]:
    sums = read_sums(MEMBERS)
    bad = sum_problems(config.RECORDS, sums)
    extra = {f"raw/{p}" for p in files_under(RAW)} - set(sums)
    return not bad and not extra, (f"{len(sums) - len(bad)} of {len(sums)} files in records/raw match records/MEMBERS.sha256"
                                   + listed(bad, "differ") + listed(extra, "not in an archive"))


@check("L1", "record index")
def record_index() -> tuple[bool, str]:
    lines = (config.RECORDS / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    by_id = {json.loads(ln)["run_id"]: ln for ln in lines}
    bad = []
    for rid, line in by_id.items():
        f = RAW / rid / "record.json"
        text = f.read_text(encoding="utf-8") if f.is_file() else ""
        if not text or json.dumps(json.loads(text)) != line or json.dumps(json.loads(line), indent=1) != text:
            bad.append(rid)
    extra = set(shipped_records()) - set(by_id)
    ok = not bad and not extra and len(by_id) == len(lines)
    return ok, (f"{len(lines) - len(bad)} of {len(lines)} lines of runs.jsonl equal their run folder's record.json"
                + listed(bad, "differ") + listed(extra, "folders without a line"))


@check("L1", "run plan")
def run_plan() -> tuple[bool, str]:
    plan, recs = planned(), shipped_records()
    bad = [rid for rid, r in plan.items() if rid not in recs or {k: recs[rid][k] for k in r} != r
           or recs[rid]["model_served"] != [config.MODELS[r["model"]]["model_reported"]]]
    extra = set(recs) - set(plan)
    design = (f"{len(config.MODELS)} models x {len(config.FRAMEWORKS)} frameworks x {len(pilot_days())} days x "
              f"{sum(config.EXPERIMENT['runs']['per_arm'].values())} runs")
    return not bad and not extra, (f"{len(plan) - len(bad)} of {len(plan)} planned runs ({design}) have a record with the planned "
                                   "arm, k and seed, served as models.toml's model_reported"
                                   + listed(bad, "differ") + listed(extra, "unplanned"))


def rebuilt_harness(rec: dict) -> dict:
    """The record of a shipped harness run rebuilt from its session.json.gz (every field but finished_epoch)."""
    s = records.load_gz(RAW / rec["run_id"] / "session.json.gz")
    extra = records.serving_fields(rec["model"], "harness", rec.get("served_max_model_len"), rec.get("gpu_index"))
    day = pilot_days()[rec["day_id"]]
    return agent.make_record(s["run"], day, s["step"], s["trace"], s["ctx"], s["error"], rec["wall_s"], extra)


def rebuilt_coding(rec: dict) -> dict:
    """The record of a shipped coding run rebuilt by codex.make_record (every field but finished_epoch): its planned row,
    decision.json, events.jsonl, the relay log, the given workspace and the recorded host's CODEX_HOME; the wall time, exit
    code and audit verdict (re-audited at L2) as recorded."""
    rd, ws = RAW / rec["run_id"], rec["workspace_name"]
    with config.host_env(config.RECORDED_HOST_ENV):
        home = workspace.run_folders(ws)["codex_home"].relative_to(config.host("PROJECT_DIR"))
    files = {k: {"chars": len(v)} for k, v in given_files(rec["day_id"], rec["arm"]).items()}
    extra = records.serving_fields(rec["model"], "coding_agent", rec.get("served_max_model_len"), rec.get("gpu_index"))
    logs = {"work": rd / "workspace", "events": rd / "events.jsonl", "relay": relay_log(rec["model"])}
    return codex.make_record(planned()[rec["run_id"]], ws, logs, files, str(home), rec["wall_s"], rec["exit_code"],
                             rec["timed_out"], rec["leakage"], workspace.AGENT_PROMPT, extra)


@check("L1", "records rebuilt")
def records_rebuilt() -> tuple[bool, str]:
    rebuild = {"harness": rebuilt_harness, "coding_agent": rebuilt_coding}
    bad = [rid for rid, rec in shipped_records().items()
           if list(rebuild[rec["framework"]](rec).items()) != [(k, v) for k, v in rec.items() if k != "finished_epoch"]]
    n = len(shipped_records())
    return not bad, (f"{n - len(bad)} of {n} records rebuilt, every field and its order: harness from session.json.gz, coding "
                     "from decision.json, events.jsonl, the relay log and the given workspace" + listed(bad, "differ"))


@check("L1", "coding workspaces")
def coding_workspaces() -> tuple[bool, str]:
    given = {(rid, name): text for rid, rec in shipped("coding_agent").items()
             for name, text in given_files(rec["day_id"], rec["arm"]).items()}
    bad = [f"{rid}/{name}" for (rid, name), text in given.items() if not same_bytes(RAW / rid / "workspace" / name, text)]
    return not bad, (f"{len(given) - len(bad)} of {len(given)} given files (task.md, prices.csv, news.csv, account.json) "
                     "equal the rebuilt ones" + listed(bad, "differ"))


@check("L1", "realised outcomes")
def realised_outcomes() -> tuple[bool, str]:
    ds = pilot_days()
    out = Outcomes({d["ticker"] for d in ds.values()})
    want = {did: {"real5_pct": out.realised(d["ticker"], d["t"])[1], "rv5": out.realised_var5(d["ticker"], d["t"])}
            for did, d in ds.items()}
    recs = shipped("harness")
    bad = [rid for rid, r in recs.items() if r["outcome_not_shown"] != want[r["day_id"]]]
    return not bad, (f"{len(recs) - len(bad)} of {len(recs)} harness records carry the 5-day return and realised variance "
                     "recomputed from the panel" + listed(bad, "differ"))


def replay(rec: dict) -> Counter:
    """Re-run a shipped harness session's recorded tool calls, in order, on the run's own fresh anchor state, arm and cache view;
    counts of what equals the recording (prompt, tool and submit results, cache log, arm counters)."""
    s = records.load_gz(RAW / rec["run_id"] / "session.json.gz")
    d = pilot_days()[rec["day_id"]]
    st = fresh_state(d["day_id"])
    view = news_cache(d["ticker"]).view()
    ctx = agent.new_context(rec["arm"], d)
    prompt_hook, rewrite = agent.arm_hooks(ctx)
    payload = build_day_payload(view, d["t"], {**st["portfolio"]}, st["memory"])          # as session.day_step
    prompt = prompt_hook(render_prompt(payload, d["ticker"]))
    first = s["trace"][0]
    c = Counter(prompt=(first["system"], first["user"]) == (SYSTEM, prompt) and prompt == harness_prompt(d, rec["arm"]))
    for e in (e for e in s["trace"] if "tool" in e):
        if e["tool"] == "submit_decision":
            got = session.submit_reply(e["args"], st["portfolio"], payload["bars"][0]["close"])
        else:
            got = rewrite(e["tool"], toolbox.run_tool(view, as_of(d), e["tool"], dict(e["args"]), st["tb_state"]))[:CUT]
        c["calls"] += 1
        c["calls_same"] += got == e["result"]
    c["cache_log"] = json.dumps(view.log) == json.dumps(s["cache_log"])
    counters = (ctx["prompts_rendered"], ctx["block_tool_calls"], ctx["block_tool_outputs_rewritten"])
    c["counters"] = counters == (rec["block_inserted"], rec["block_tool_calls"], rec["block_tool_outputs_rewritten"])
    return c


@check("L1", "harness replay")
def harness_replay() -> tuple[bool, str]:
    total, bad = Counter(), []
    recs = shipped("harness")
    for rid, rec in recs.items():
        c = replay(rec)
        total += c
        if not (c["prompt"] and c["cache_log"] and c["counters"]) or c["calls_same"] != c["calls"]:
            bad.append(rid)
    return not bad, (f"{len(recs) - len(bad)} of {len(recs)} sessions replayed: {total['calls_same']} of {total['calls']} "
                     f"recorded tool and submit results, {total['prompt']} prompts, {total['cache_log']} news-cache logs, "
                     f"{total['counters']} arm counters identical" + listed(bad, "differ"))


@check("L1", "codex configs")
def codex_configs() -> tuple[bool, str]:
    recs = shipped("coding_agent")
    bad = []
    with config.host_env(config.RECORDED_HOST_ENV):
        for rid, rec in recs.items():
            m, ws = rec["model"], rec["workspace_name"]
            f = workspace.run_folders(ws)
            text = codex.codex_config(m, ws, f["home"], f["tmp"], codex.context_window(m, rec.get("served_max_model_len")))
            if not same_bytes(RAW / rid / "codex_config.toml", text):
                bad.append(rid)
    return not bad, (f"{len(recs) - len(bad)} of {len(recs)} codex_config.toml regenerated byte for byte "
                     "(setup/host.recorded.env)" + listed(bad, "differ"))


def first_execve(strace: Path) -> tuple[list[str], int]:
    """(argv, number of environment variables) of the first line of a strace log: the start of the sandbox."""
    with open(strace, errors="replace") as f:
        call = audit.CALL_RX.match(audit.LINE_RX.match(f.readline().rstrip("\n")).group(2))
    env = re.search(r"/\* (\d+) vars \*/", call.group(2))
    return audit.strace_strings(call.group(2))[1:], int(env.group(1)) if env else -1


@check("L1", "codex commands")
def codex_commands() -> tuple[bool, str]:
    recs = shipped("coding_agent")
    bad = []
    with config.host_env(config.RECORDED_HOST_ENV):
        pilot_sandbox = str(Path(config.host("PROJECT_DIR")) / "repro" / "codexpilot" / "sandbox.py")   # sandbox.py in the pilot
        for rid, rec in recs.items():
            f = workspace.run_folders(rec["workspace_name"])
            argv = codex.codex_command(rec["model"], f, config.host("CODEX_REAL_BIN"), rec["agent_prompt"])[len(codex.STRACE) + 2:]
            argv[1] = pilot_sandbox
            if first_execve(RAW / rid / "strace.txt") != (argv, len(codex.codex_env(f))):
                bad.append(rid)
    return not bad, (f"{len(recs) - len(bad)} of {len(recs)} sandbox + codex exec command lines (write roots, relay port, prompt) "
                     "and agent environments regenerated equal to strace.txt's first execve (setup/host.recorded.env)"
                     + listed(bad, "differ"))


@check("L1", "analysis outputs")
def analysis_outputs() -> tuple[bool, str]:
    outputs = analysis.build(RAW)
    bad = [name for name, text in outputs.items() if not same_bytes(config.RESULTS / name, text)]
    return not bad, (f"{len(outputs) - len(bad)} of {len(outputs)} files in results/ recomputed byte for byte from the records"
                     + listed(bad, "differ"))


@check("L1", "figures")
def figure_files() -> tuple[bool, str]:
    svgs = figures.figures(figures.Page(config.RESULTS / "describe_reasoning_models.json"))
    bad = [name for name, text in svgs.items() if not same_bytes(config.RESULTS / "figures" / name, text)]
    return not bad, (f"{len(svgs) - len(bad)} of {len(svgs)} charts in results/figures redrawn byte for byte"
                     + listed(bad, "differ"))


def mechanism_rebuilt(name: str, text: str, detail: str) -> tuple[bool, str]:
    """results/mechanisms/<name>/data.json against a fresh build."""
    path = config.MECHANISMS_RESULTS / name / "data.json"
    same = same_bytes(path, text)
    return same, f"{config.rel(path)} {'rebuilt byte for byte' if same else 'DIFFERS from a rebuild'}: {detail}"


@check("L1", "mechanism salience")
def mechanism_salience() -> tuple[bool, str]:
    d = salience.build()
    n, cp = d["n_sessions_used"], d["step3_copied_vs_not_copied"]["newsagent_FULL_plus_NO_NEWS_combined"]["copied"]
    return mechanism_rebuilt("salience", salience.dumps(d), f"{n['newsagent_total']} newsagent sessions, {cp['n']} "
                             "copy the annualised number")


@check("L1", "mechanism proximity")
def mechanism_proximity() -> tuple[bool, str]:
    d = proximity.build()
    acc, fe = d["sample_accounting"], d["step2_results"]["within_day_fixed_effects_level_test"]["fe_regression"]
    return mechanism_rebuilt("proximity", proximity.dumps(d), f"{acc['n_usable_part1_2']} usable sessions, "
                             f"{acc['n_days_with_both_is_last_groups']} matched days, day fixed effects p={fe['p']:.2f}")


@check("L1", "mechanism position")
def mechanism_position() -> tuple[bool, str]:
    d = position_adjustment.build()
    ratio = d["headline"]["overall"]["std_ratio"]
    return mechanism_rebuilt("position_adjustment", position_adjustment.dumps(d),
                             f"{ratio['n']} day-to-day changes, std ratio agent / rational {ratio['ratio']:.2f}")


@check("L1", "mechanism thinking")
def mechanism_thinking() -> tuple[bool, str]:
    d = thinking.build()
    o = d["rates"]["overall"]
    return mechanism_rebuilt("thinking", thinking.dumps(d), f"{o['n']:,} reasoning texts, relationship language "
                             f"{o['pct_relationship']}% (strict2 {o['pct_relationship_strict2']}%)")


@check("L1", "mechanism page")
def mechanism_page() -> tuple[bool, str]:
    data = mech_page.load()
    same = same_bytes(mech_page.OUT_FILE, mech_page.build(data))
    return same, (f"{config.rel(mech_page.OUT_FILE)} {'redrawn byte for byte' if same else 'DIFFERS from a redraw'} from "
                  f"the four data.json; {mech_page.check_typed_numbers(data)} numbers typed in its text agree with them")


@check("L1", "theory document")
def theory_document() -> tuple[bool, str]:
    files = theory_doc.build()
    bad = [config.rel(p) for p, data in files.items() if not (p.is_file() and p.read_bytes() == data)]
    n = len(theory_doc.appendix_rows(theory_doc.load())[0])
    return not bad, (f"{len(files) - len(bad)} of {len(files)} files (.docx, Markdown) rebuilt byte for byte from "
                     f"docs/good_thinking/good_thinking_theory.json ({n} literature entries)" + listed(bad, "differ"))


# ================================================================================================== L2: the leakage audit
def reaudit(run_dir: Path) -> tuple[dict, dict]:
    """(record, new verdict) of a saved coding run, audited with the original host's settings."""
    rec = json.loads((run_dir / "record.json").read_text(encoding="utf-8"))
    with config.host_env(config.RECORDED_HOST_ENV):
        return rec, audit.reaudit(run_dir, pilot_days()[rec["day_id"]], relay_log(rec["model"]))


@check("L2", "coding audit")
def coding_audit() -> tuple[bool, str]:
    runs = audit.coding_run_dirs(RAW)
    bad, flagged = [], Counter()
    for rd in runs:
        rec, new = reaudit(rd)
        flagged[rec["model"]] += new["flag"]
        if new != rec["leakage"]:
            bad.append(rd.name)
    return not bad, (f"{len(runs) - len(bad)} of {len(runs)} verdicts (flag, reasons, counts) identical; flagged "
                     f"{sum(flagged.values())}: {tally(+flagged)}" + listed(bad, "differ"))


@check("L2", "audit canary")
def audit_canary() -> tuple[bool, str]:
    runs = [rd for stage in ("smoke_orig", "smoke_runs") for rd in audit.coding_run_dirs(RAW / stage)]
    bad, canary = [], None
    for rd in runs:
        rec, new = reaudit(rd)
        if new != rec["leakage"]:
            bad.append(rd.name)
        if rd.name.startswith("CANARY__"):
            canary = new
    [want] = json.loads((BUILD_CHECKS / "audit_canary.json").read_text())
    reasons = " ".join(canary["reasons"]) if canary else ""
    caught = [k.rstrip(":") for k in ("path:", "project folders", "network:", "date:") if k in reasons]
    ok = not bad and canary is not None and canary["reasons"] == want["reasons"] and len(caught) == 4
    return ok, (f"{len(runs) - len(bad)} of {len(runs)} smoke-stage coding runs re-audited identically; the canary is flagged "
                f"on {', '.join(caught) or 'nothing'} as in records/infra/checks/audit_canary.json" + listed(bad, "differ"))


# ================================================================================================== commands
def run_check(name: str, fn: Check) -> tuple[str, bool, str]:
    """(name, ok, detail); an exception is a failure."""
    try:
        ok, detail = fn()
    except Exception as e:                                                    # noqa: BLE001  (reported in the table)
        ok, detail = False, f"error: {type(e).__name__}: {e}"
    return name, ok, detail


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent verify", description="Check data, prompts, records, analysis and the audit "
                                 "against the code (exit 1 on a failure).")
    ap.add_argument("--level", choices=[*LEVELS, "all"], default="all",
                    help="L0: the repository alone; L1: records and results; L2: the audit (L1 and L2 need `finagent unpack`)")
    a = ap.parse_args(argv)
    levels = LEVELS if a.level == "all" else (a.level,)
    missing = [lv for lv in levels if lv != "L0" and not RAW.is_dir()]
    todo = [(lv, name, fn) for lv, name, fn in CHECKS if lv in levels and lv not in missing]
    width = max(len(name) for _, name, _ in CHECKS)
    print(f"{'level':5}  {'check':{width}}  {'result':6}  {'time':>6}  detail")
    n_fail, t_all = 0, time.time()
    for level, name, fn in todo:
        t0 = time.time()
        _, ok, detail = run_check(name, fn)
        n_fail += not ok
        print(f"{level:5}  {name:{width}}  {'pass' if ok else 'FAIL':6}  {time.time() - t0:5.1f}s  {detail}", flush=True)
    for lv in missing:
        n_fail += 1
        print(f"{lv:5}  {'records/raw':{width}}  {'FAIL':6}  {'':6}  missing: run `finagent unpack` first (or --level L0)")
    n = len(todo) + len(missing)
    print(f"\n{n - n_fail} of {n} checks passed ({', '.join(levels)}) in {time.time() - t_all:.1f} s")
    return 1 if n_fail else 0


def unpack(argv: list[str] | None = None) -> int:
    """`finagent unpack`: check the archives against records/SHA256SUMS, extract them into records/raw and check every file
    against records/MEMBERS.sha256."""
    ap = argparse.ArgumentParser(prog="finagent unpack", description="Extract records/archives/*.tar.xz into records/raw and "
                                 "verify every file hash (exit 1 on a difference).")
    ap.add_argument("--clean", action="store_true", help="remove records/raw first")
    a = ap.parse_args(argv)
    sums = read_sums(config.RECORDS / "SHA256SUMS")
    archives = sorted(name for name in sums if name.endswith(".tar.xz"))
    bad = sum_problems(config.RECORDS, {name: sums[name] for name in archives})
    if bad:
        print("archives that differ from records/SHA256SUMS: " + ", ".join(bad))
        return 1
    if a.clean and RAW.exists():
        shutil.rmtree(RAW)
    t0 = time.time()
    for name in archives:
        with tarfile.open(config.RECORDS / name, "r:xz") as tar:
            if any(not m.name.startswith("raw/") for m in tar.getmembers()):
                raise SystemExit(f"{name}: a member lies outside raw/")
            tar.extractall(config.RECORDS, filter="data")
    ok, detail = unpacked_files()
    print(f"extracted {len(archives)} archives into {RAW} in {time.time() - t0:.1f} s; {detail}"
          + ("" if ok else "\n(`finagent unpack --clean` starts from an empty records/raw)"))
    return 0 if ok else 1
