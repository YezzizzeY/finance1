"""Leakage audit of a coding-agent run: a flagged run is excluded from the analysis and counted.

Sources, all logged during the run:
  strace   `strace -f -y` of the whole agent process tree (execve, open/openat/openat2, chdir, connect, bind, clone/fork). The
           model's commands are the processes below the codex process (not its threads), each counted from the execve of
           `bash -c|-lc <command>` on (Codex's own process-setup and shell-snapshot execs excluded), with all their descendants.
  events   `codex exec --json`: every command with its output, file changes and other tool calls.
  relay    the model's relay log: a request without the run header during the run is a command calling the relay.
Flags (each with its evidence):
  path     a command opens or executes a path outside the run's workspace, home, tmp, CODEX_HOME, the agent python env
           (AGENT_PYENV, libraries only) and the system directories; or a tool call names such a path. Accesses inside
           PRIVATE_ROOT (the project folders) are counted separately.
  network  a command calls connect()/bind() on an IP socket (blocked by the sandbox, but the attempt counts), a command contains
           a URL or a network client (curl, wget, nc, ssh, pip install, git clone/fetch, requests/urllib/httpx/socket use), or
           the relay saw a request without the run header during the run.
  date     a date after day t is touched: a date > t in a path or URL used by a command or tool; a news timestamp (YYYYMMDDTHHMM)
           at or after D(t) in any command output; an output line with an ISO date > t and at least three price-like numbers
           (a price row). Other dates > D(t) in outputs (a computed horizon end, say) are counted as future_date_mentions only.

    finagent audit [--raw DIR] [--relay-dir DIR] [--host-env FILE]   re-audit saved runs, compare with their records
"""
from __future__ import annotations

import argparse
import json
import os
import re
from collections import Counter, defaultdict
from pathlib import Path

from finagent import config, days
from finagent.coding import workspace

SYSTEM_PREFIXES = ("/usr/", "/lib/", "/lib64/", "/lib32/", "/bin/", "/sbin/", "/etc/", "/proc/", "/sys/", "/dev/", "/run/",
                   "/var/lib/", "/var/cache/fontconfig/")
# directory stats / opens of path parents; WS_ROOT and its ancestors are added at audit time
SYSTEM_EXACT = {"/", "/usr", "/lib", "/lib64", "/bin", "/sbin", "/etc", "/proc", "/sys", "/dev", "/run", "/tmp", "/var"}
LINE_RX = re.compile(r"^(\d+) (.*)$")
CALL_RX = re.compile(r"^([a-z0-9_]+)\((.*)\)\s+= (-?\d+|\?)(.*)$", re.S)
STR_RX = re.compile(r'"((?:[^"\\]|\\.)*)"')
FD_DECOR_RX = re.compile(r"^(?:AT_FDCWD|\d+)<([^>]*)>")
NET_CMD_RX = re.compile(r"https?://|\bcurl\b|\bwget\b|\bnc\b|\bncat\b|\bssh\b|\bscp\b|pip3? install|git (?:clone|fetch|pull)|"
                        r"\brequests\.|\burllib\b|\bhttpx\b|\bsocket\.|yfinance|\baiohttp\b|127\.0\.0\.1|localhost", re.I)
ISO_RX = re.compile(r"(?<!\d)(20\d\d)-(\d\d)-(\d\d)(?!\d)")
COMPACT_TS_RX = re.compile(r"(?<!\d)(20\d\d)(\d\d)(\d\d)T(\d{4,6})(?!\d)")
COMPACT_DATE_RX = re.compile(r"(?<!\d)(20\d\d)(\d\d)(\d\d)(?!\d)")
PRICE_NUM_RX = re.compile(r"(?<![\d.])\d{1,6}\.\d{2,}(?![\d.])")
NO_RUN_HEADER = "NO_RUN_HEADER"                                               # = relay.NO_RUN_HEADER


# ================================================================================================== strace
def parse_strace(path: Path) -> list[dict]:
    """[{pid, name, args, ret, tail}] in file order, unfinished / resumed pairs joined."""
    out, pending = [], {}
    if not path.exists():
        return out
    with open(path, errors="replace") as f:
        for raw in f:
            m = LINE_RX.match(raw.rstrip("\n"))
            if not m:
                continue
            pid, rest = int(m.group(1)), m.group(2)
            if rest.startswith("+++") or rest.startswith("---"):
                continue
            if rest.endswith("<unfinished ...>"):
                pending[pid] = rest[: -len("<unfinished ...>")]
                continue
            if rest.startswith("<... "):
                j = rest.find("resumed>")
                rest = pending.pop(pid, "") + rest[j + len("resumed>"):] if j >= 0 else rest
            c = CALL_RX.match(rest)
            if not c:
                continue
            out.append({"pid": pid, "name": c.group(1), "args": c.group(2), "ret": c.group(3), "tail": c.group(4)})
    return out


def strace_strings(args: str) -> list[str]:
    """The quoted strings of a call's arguments, escapes decoded (execve: the path, then argv)."""
    return [bytes(s, "utf-8").decode("unicode_escape", "replace") if "\\" in s else s for s in STR_RX.findall(args)]


def _resolve(ev: dict) -> str | None:
    """The absolute path of an open/openat/execve/chdir event (strace -y decorations)."""
    a = ev["args"]
    s = strace_strings(a)
    if not s:
        return None
    p = s[0]
    if p.startswith("/"):
        return os.path.normpath(p)
    base = None
    if ev["name"] in ("openat", "openat2"):
        m = FD_DECOR_RX.match(a)
        base = m.group(1) if m else None
    return os.path.normpath(os.path.join(base, p)) if base else p


def process_tree(evs: list[dict]) -> tuple[dict, set]:
    """parent[pid] and the threads (pids created with CLONE_THREAD)."""
    parent, threads = {}, set()
    for e in evs:
        if e["name"] in ("clone", "clone3", "fork", "vfork") and e["ret"].isdigit():
            child = int(e["ret"]); parent[child] = e["pid"]
            if "CLONE_THREAD" in e["args"]:
                threads.add(child)
    return parent, threads


def descendants(roots: set, parent: dict) -> set:
    kids = defaultdict(set)
    for c, p in parent.items():
        kids[p].add(c)
    out, todo = set(roots), list(roots)
    while todo:
        x = todo.pop()
        for c in kids[x]:
            if c not in out:
                out.add(c); todo.append(c)
    return out


def has_started_ancestor(pid: int, started: set, parent: dict) -> bool:
    seen = 0
    p = parent.get(pid)
    while p is not None and seen < 10000:
        if p in started:
            return True
        p = parent.get(p); seen += 1
    return False


def command_events(evs: list[dict]) -> list[dict]:
    """The events of the model's commands only (see the module docstring)."""
    parent, threads = process_tree(evs)
    agent = None
    for e in evs:
        if e["name"] == "execve" and e["ret"] == "0" and any(x.endswith("/codex") for x in strace_strings(e["args"])[:1]):
            agent = e["pid"]; break
    if agent is None:
        return []
    group = {agent}
    changed = True
    while changed:                                                            # the codex process and all its threads
        changed = False
        for c, p in parent.items():
            if p in group and c in threads and c not in group:
                group.add(c); changed = True
    # Codex runs a model command as: clone -> execve(/proc/self/exe --codex-run-as-process-setup ...) (its own setup) ->
    # [execve(/bin/bash -c <snapshot prelude>)] -> execve(/bin/bash -c|-lc <the command>). The command starts at that last execve.
    below = descendants(group, parent) - group
    out, started = [], set()
    for e in evs:
        pid = e["pid"]
        if pid not in below:
            continue
        if pid not in started and e["name"] == "execve" and e["ret"] == "0":
            argv = strace_strings(e["args"])[1:]
            if (len(argv) >= 3 and os.path.basename(argv[0]) == "bash" and argv[1] in ("-c", "-lc")
                    and "__CODEX_SNAPSHOT" not in argv[2] and not has_started_ancestor(pid, started, parent)):
                started.add(pid)
        if pid in started or has_started_ancestor(pid, started, parent):
            out.append(e)
    return out


def allowed_path(p: str, roots: list[str], exact: set[str]) -> bool:
    if p in exact or any(p == r or p.startswith(r.rstrip("/") + "/") for r in roots):
        return True
    return p.startswith(SYSTEM_PREFIXES)


# ================================================================================================== events
def codex_texts(events_file: Path) -> dict:
    """Commands, their outputs, the paths named by file changes and tool calls, and the tool calls of a --json event log."""
    cmds, outs, paths, tools = [], [], [], []
    if not events_file.exists():
        return {"commands": cmds, "outputs": outs, "paths": paths, "tool_calls": tools}
    for ln in open(events_file, errors="replace"):
        try:
            e = json.loads(ln)
        except json.JSONDecodeError:
            continue
        it = e.get("item") or {}
        if e.get("type") != "item.completed":
            continue
        t = it.get("type")
        if t == "command_execution":
            cmds.append(it.get("command") or ""); outs.append(it.get("aggregated_output") or "")
        elif t == "file_change":
            for ch in it.get("changes") or []:
                paths.append(ch.get("path") or "")
        elif t in ("mcp_tool_call", "web_search", "tool_call", "function_call", "custom_tool_call", "view_image"):
            tools.append(json.dumps(it)[:2000])
            for k in ("path", "image_path", "url", "query"):
                if isinstance(it.get(k), str):
                    paths.append(it[k])
    return {"commands": cmds, "outputs": outs, "paths": paths, "tool_calls": tools}


def _dates(text: str) -> set[str]:
    return {f"{y}-{m}-{d}" for y, m, d in ISO_RX.findall(text)} | {f"{y}-{m}-{d}" for y, m, d in COMPACT_DATE_RX.findall(text)}


# ================================================================================================== audit
def allowed_roots(rid: str) -> list[str]:
    """Where a command of run `rid` may go: workspace, home, tmp, CODEX_HOME (resolved) and the agent python env."""
    f = workspace.run_folders(rid)
    return [str(f[k].resolve()) for k in ("work", "home", "tmp", "codex_home")] + [config.host("AGENT_PYENV")]


def system_exact() -> set[str]:
    ws_root = Path(config.host("WS_ROOT"))
    return SYSTEM_EXACT | {str(ws_root)} | {str(x) for x in ws_root.parents}


def audit_run(log_dir: Path, day: dict, rid: str, relay_log: Path | None, t_start: float, t_end: float) -> dict:
    """The verdict on run `rid` of `day` from the logs in log_dir (strace.txt, events.jsonl) and the model's relay log."""
    t = day["t"]; D = day["D"]                                          # D = 'YYYYMMDDTHHMMSS' (09:00 New York, next trading day)
    ws = workspace.run_folders(rid)["work"]
    roots, exact = allowed_roots(rid), system_exact()
    reasons, ev_paths, ev_net = [], [], []
    evs = parse_strace(log_dir / "strace.txt")
    cev = command_events(evs)
    n_open = 0
    for e in cev:
        if e["name"] in ("open", "openat", "openat2", "execve", "chdir"):
            p = _resolve(e)
            if p is None:
                continue
            n_open += 1
            if not p.startswith("/"):
                continue
            if not allowed_path(p, roots, exact):
                ev_paths.append({"pid": e["pid"], "call": e["name"], "path": p, "ret": e["ret"]})
            if any(x > t for x in _dates(p)):
                reasons.append(f"date: path with a date after {t}: {p}")
        elif e["name"] in ("connect", "bind") and ("AF_INET" in e["args"]):
            ev_net.append({"pid": e["pid"], "call": e["name"], "target": e["args"][:200], "ret": e["ret"] + e["tail"][:60]})
    tx = codex_texts(log_dir / "events.jsonl")
    for p in tx["paths"]:
        pp = os.path.normpath(p if p.startswith("/") else os.path.join(str(ws), p))
        if not allowed_path(pp, roots, exact) or pp.startswith(("/proc/", "/sys/", "/dev/", "/etc/")):
            ev_paths.append({"tool_path": p})
        if any(x > t for x in _dates(p)):
            reasons.append(f"date: tool path with a date after {t}: {p}")
    net_cmds = [c[:300] for c in tx["commands"] if NET_CMD_RX.search(c)]
    for c in tx["commands"]:
        for u in re.findall(r"https?://\S+", c):
            if any(x > t for x in _dates(u)):
                reasons.append(f"date: URL with a date after {t}: {u[:200]}")
    late_ts, price_rows, mentions = [], [], set()
    D_date = f"{D[:4]}-{D[4:6]}-{D[6:8]}"
    for o in tx["outputs"]:
        for y, m, d, hm in COMPACT_TS_RX.findall(o):
            ts = f"{y}{m}{d}T{hm}"
            if ts.ljust(15, "0") >= D:
                late_ts.append(ts)
        for line in o.splitlines():
            ds = [f"{y}-{m}-{d}" for y, m, d in ISO_RX.findall(line)]
            if any(x > t for x in ds) and len(PRICE_NUM_RX.findall(line)) >= 3:
                price_rows.append(line[:200])
            mentions |= {x for x in ds if x > D_date}
    if late_ts:
        reasons.append(f"date: news timestamps at or after D(t) {D} in outputs: {sorted(set(late_ts))[:10]}")
    if price_rows:
        reasons.append(f"date: price rows dated after {t} in outputs: {price_rows[:5]}")
    relay_strays = []
    if relay_log and relay_log.exists():
        for ln in open(relay_log):
            try:
                q = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if q.get("run") == NO_RUN_HEADER and t_start <= q.get("t0", 0) <= t_end:
                relay_strays.append(q.get("path"))
    if ev_paths:
        private = config.host("PRIVATE_ROOT")
        proj = [x for x in ev_paths if str(x.get("path") or x.get("tool_path", "")).startswith(private)]
        reasons.append(f"path: {len(ev_paths)} accesses outside the workspace and system dirs"
                       + (f" ({len(proj)} in the project folders)" if proj else "") + f": {ev_paths[:8]}")
    if ev_net:
        reasons.append(f"network: {len(ev_net)} IP socket connect/bind attempts by commands: {ev_net[:5]}")
    if net_cmds:
        reasons.append(f"network: commands with a network client or URL: {net_cmds[:5]}")
    if relay_strays:
        reasons.append(f"network: {len(relay_strays)} relay requests without the run header during the run")
    strace_ok = (log_dir / "strace.txt").exists() and len(evs) > 0
    if not strace_ok:
        reasons.append("audit: no strace log (cannot verify file access)")
    return {"flag": bool(reasons), "reasons": reasons,
            "counts": {"strace_events": len(evs), "command_events": len(cev), "command_file_events": n_open,
                       "commands": len(tx["commands"]), "tool_calls": len(tx["tool_calls"]), "paths_outside": len(ev_paths),
                       "net_attempts": len(ev_net), "net_commands": len(net_cmds), "relay_strays": len(relay_strays),
                       "future_date_mentions": len(mentions)},
            "future_date_mentions": sorted(mentions)[:20], "allowed_roots": roots}


# ================================================================================================== re-audit of saved runs
def reaudit(run_dir: Path, day: dict, relay_log: Path | None) -> dict:
    """The audit of a saved run folder (its record.json, strace.txt, events.jsonl), with this process's host settings (the
    recorded host's for the shipped runs). The run's window for relay strays is [finished_epoch - wall_s, finished_epoch]: the
    run's length, ending when its record was written (seconds after the agent exited)."""
    rec = json.loads((run_dir / "record.json").read_text())
    t_end = rec["finished_epoch"]
    return audit_run(run_dir, day, rec["workspace_name"], relay_log, t_end - rec["wall_s"], t_end)


def coding_run_dirs(raw: Path) -> list[Path]:
    return sorted(p.parent for p in raw.glob("*/record.json") if "__coding_agent__" in p.parent.name)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent audit", description="Re-audit saved coding-agent runs and compare each verdict "
                                 "with the one in its record.json (exit 1 on a difference).")
    ap.add_argument("--raw", type=Path, default=config.RAW, help="folder of run folders (default: records/raw)")
    ap.add_argument("--relay-dir", type=Path, default=None,
                    help="relay logs <dir>/<model>/requests.jsonl (default: records/infra/relay for the shipped records, "
                         "else <raw>/../relay)")
    ap.add_argument("--host-env", type=Path, default=None,
                    help="host settings the runs were made with (default: setup/host.recorded.env for the shipped records, "
                         "else FINAGENT_HOST_ENV)")
    ap.add_argument("--json", type=Path, default=None, help="also write every run's new verdict and comparison here")
    a = ap.parse_args(argv)
    shipped = a.raw.resolve().is_relative_to(config.RAW.resolve())              # records/raw or a smoke folder inside it
    relay_dir = a.relay_dir or (config.RECORDS / "infra" / "relay" if shipped else a.raw.parent / "relay")
    host_file = a.host_env or (config.RECORDED_HOST_ENV if shipped else config.HOST_ENV_FILE)
    runs = coding_run_dirs(a.raw)
    if not runs:
        print(f"no coding-agent runs under {a.raw} (records: `finagent unpack` first)")
        return 1
    by_day = {d["day_id"]: d for d in days.load()}
    recs = {rd: json.loads((rd / "record.json").read_text()) for rd in runs}
    missing = sorted({str(relay_dir / r["model"] / "requests.jsonl") for r in recs.values()
                      if not (relay_dir / r["model"] / "requests.jsonl").is_file()})
    if missing:
        print("relay log missing (pass --relay-dir): " + ", ".join(missing))
        return 1
    tally, out, differ = Counter(), {}, []
    with config.host_env(host_file):
        for rd, rec in recs.items():
            new = reaudit(rd, by_day[rec["day_id"]], relay_dir / rec["model"] / "requests.jsonl")
            same = new == rec["leakage"]
            tally[(rec["model"], "runs")] += 1; tally[(rec["model"], "flagged")] += new["flag"]; tally[(rec["model"], "same")] += same
            out[rec["run_id"]] = {"identical": same, "leakage": new}
            if not same:
                differ.append(rec["run_id"])
    print(f"{'model':<12} {'runs':>5} {'flagged':>8} {'identical to record':>20}")
    for m in dict.fromkeys(k for k, _ in tally):
        print(f"{m:<12} {tally[(m, 'runs')]:>5} {tally[(m, 'flagged')]:>8} {tally[(m, 'same')]:>20}")
    print(f"{len(runs) - len(differ)} of {len(runs)} verdicts identical (flag, reasons, counts, mentions, allowed roots; host "
          f"settings {config.rel(host_file)})" + "".join(f"\n  differs: {x}" for x in differ))
    if a.json:
        a.json.write_text(json.dumps(out, indent=1))
    return 1 if differ else 0
