#!/usr/bin/env python3
"""Workspace-write sandbox without user namespaces (Landlock + seccomp) around a coding agent; standard library only.

Codex's own Linux sandbox runs bubblewrap, which needs unprivileged user namespaces; where AppArmor blocks them
(kernel.apparmor_restrict_unprivileged_userns = 1) every sandboxed command fails. This launcher enforces the same policy with
kernel features that need no privileges and are inherited by every child process, then executes the command:
  * no_new_privs;
  * Landlock (ABI >= 4): writes (create, write, truncate, remove, rename, link, make dir/fifo/socket/device) only beneath the
    --write paths; reading and executing stay allowed everywhere (as in workspace-write; reads are audited, not blocked);
    TCP bind denied, TCP connect only to the --connect-port ports (the local relay to the model);
  * seccomp (libseccomp): socket() for AF_INET / AF_INET6 with SOCK_DGRAM or SOCK_RAW, any AF_PACKET socket and io_uring_setup
    fail with EPERM (no UDP, no raw packets, no io_uring path around the socket filter).
Every invocation is appended (time, pid, argv) to --log when given; the command keeps this process's pid and environment.

    sandbox.py --write DIR [--write DIR ...] [--connect-port P ...] [--log FILE] -- command ...
    sandbox.py --selftest DIR       (writes inside DIR, tries outside writes and network; prints a JSON verdict)
"""
from __future__ import annotations

import ctypes
import ctypes.util
import json
import os
import subprocess
import sys
import time

SYS_LANDLOCK_CREATE_RULESET, SYS_LANDLOCK_ADD_RULE, SYS_LANDLOCK_RESTRICT_SELF = 444, 445, 446
PR_SET_NO_NEW_PRIVS = 38
LANDLOCK_CREATE_RULESET_VERSION = 1
RULE_PATH_BENEATH, RULE_NET_PORT = 1, 2
FS = {"EXECUTE": 1 << 0, "WRITE_FILE": 1 << 1, "READ_FILE": 1 << 2, "READ_DIR": 1 << 3, "REMOVE_DIR": 1 << 4, "REMOVE_FILE": 1 << 5,
      "MAKE_CHAR": 1 << 6, "MAKE_DIR": 1 << 7, "MAKE_REG": 1 << 8, "MAKE_SOCK": 1 << 9, "MAKE_FIFO": 1 << 10, "MAKE_BLOCK": 1 << 11,
      "MAKE_SYM": 1 << 12, "REFER": 1 << 13, "TRUNCATE": 1 << 14}
WRITE_RIGHTS = 0
for _k in ("WRITE_FILE", "REMOVE_DIR", "REMOVE_FILE", "MAKE_CHAR", "MAKE_DIR", "MAKE_REG", "MAKE_SOCK", "MAKE_FIFO", "MAKE_BLOCK",
           "MAKE_SYM", "REFER", "TRUNCATE"):
    WRITE_RIGHTS |= FS[_k]
FILE_WRITE_RIGHTS = FS["WRITE_FILE"] | FS["TRUNCATE"]      # rights that apply to a single (non-directory) file
NET_BIND_TCP, NET_CONNECT_TCP = 1 << 0, 1 << 1
DEV_WRITABLE = ("/dev/null", "/dev/zero", "/dev/full", "/dev/tty", "/dev/ptmx", "/dev/pts", "/dev/shm", "/dev/random", "/dev/urandom")

libc = ctypes.CDLL(None, use_errno=True)


class RulesetAttr(ctypes.Structure):
    _fields_ = [("handled_access_fs", ctypes.c_uint64), ("handled_access_net", ctypes.c_uint64)]


class PathBeneathAttr(ctypes.Structure):
    _pack_ = 1
    _fields_ = [("allowed_access", ctypes.c_uint64), ("parent_fd", ctypes.c_int32)]


class NetPortAttr(ctypes.Structure):
    _fields_ = [("allowed_access", ctypes.c_uint64), ("port", ctypes.c_uint64)]


def _err(what: str):
    e = ctypes.get_errno()
    raise OSError(e, f"{what}: {os.strerror(e)}")


def landlock_abi() -> int:
    return libc.syscall(SYS_LANDLOCK_CREATE_RULESET, None, ctypes.c_size_t(0), ctypes.c_uint32(LANDLOCK_CREATE_RULESET_VERSION))


def apply_landlock(write_paths: list[str], connect_ports: list[int]) -> None:
    abi = landlock_abi()
    if abi < 4:
        raise RuntimeError(f"Landlock ABI {abi} < 4 (TCP rules need ABI 4)")
    attr = RulesetAttr(WRITE_RIGHTS, NET_BIND_TCP | NET_CONNECT_TCP)
    fd = libc.syscall(SYS_LANDLOCK_CREATE_RULESET, ctypes.byref(attr), ctypes.c_size_t(ctypes.sizeof(attr)), ctypes.c_uint32(0))
    if fd < 0:
        _err("landlock_create_ruleset")
    for p in list(write_paths) + [d for d in DEV_WRITABLE if os.path.exists(d)]:
        pfd = os.open(p, os.O_PATH | os.O_CLOEXEC)
        try:
            rights = WRITE_RIGHTS if os.path.isdir(p) else FILE_WRITE_RIGHTS
            pb = PathBeneathAttr(rights, pfd)
            if libc.syscall(SYS_LANDLOCK_ADD_RULE, fd, RULE_PATH_BENEATH, ctypes.byref(pb), ctypes.c_uint32(0)) != 0:
                _err(f"landlock_add_rule {p}")
        finally:
            os.close(pfd)
    for port in connect_ports:
        na = NetPortAttr(NET_CONNECT_TCP, int(port))
        if libc.syscall(SYS_LANDLOCK_ADD_RULE, fd, RULE_NET_PORT, ctypes.byref(na), ctypes.c_uint32(0)) != 0:
            _err(f"landlock_add_rule port {port}")
    if libc.prctl(PR_SET_NO_NEW_PRIVS, 1, 0, 0, 0) != 0:
        _err("prctl(NO_NEW_PRIVS)")
    if libc.syscall(SYS_LANDLOCK_RESTRICT_SELF, fd, ctypes.c_uint32(0)) != 0:
        _err("landlock_restrict_self")
    os.close(fd)


class ScmpArgCmp(ctypes.Structure):
    _fields_ = [("arg", ctypes.c_uint), ("op", ctypes.c_int), ("datum_a", ctypes.c_uint64), ("datum_b", ctypes.c_uint64)]


def apply_seccomp() -> None:
    lib = ctypes.CDLL(ctypes.util.find_library("seccomp") or "libseccomp.so.2", use_errno=True)
    lib.seccomp_init.restype = ctypes.c_void_p
    lib.seccomp_rule_add_array.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int, ctypes.c_uint, ctypes.POINTER(ScmpArgCmp)]
    lib.seccomp_load.argtypes = [ctypes.c_void_p]
    lib.seccomp_syscall_resolve_name.argtypes = [ctypes.c_char_p]
    ACT_ALLOW, ACT_EPERM = 0x7FFF0000, 0x00050000 | 1
    CMP_EQ, CMP_MASKED_EQ = 4, 7
    AF_INET, AF_INET6, AF_PACKET = 2, 10, 17
    SOCK_DGRAM, SOCK_RAW = 2, 3
    ctx = lib.seccomp_init(ACT_ALLOW)
    if not ctx:
        raise RuntimeError("seccomp_init failed")
    nr_socket = lib.seccomp_syscall_resolve_name(b"socket")

    def add(nr, cmps):
        arr = (ScmpArgCmp * len(cmps))(*cmps)
        r = lib.seccomp_rule_add_array(ctypes.c_void_p(ctx), ACT_EPERM, nr, len(cmps), arr)
        if r != 0:
            raise RuntimeError(f"seccomp_rule_add_array -> {r}")
    for fam in (AF_INET, AF_INET6):
        for typ in (SOCK_DGRAM, SOCK_RAW):
            add(nr_socket, [ScmpArgCmp(0, CMP_EQ, fam, 0), ScmpArgCmp(1, CMP_MASKED_EQ, 0xF, typ)])
    add(nr_socket, [ScmpArgCmp(0, CMP_EQ, AF_PACKET, 0)])
    nr_uring = lib.seccomp_syscall_resolve_name(b"io_uring_setup")
    if nr_uring >= 0:
        r = lib.seccomp_rule_add_array(ctypes.c_void_p(ctx), ACT_EPERM, nr_uring, 0, None)
        if r != 0:
            raise RuntimeError(f"seccomp io_uring rule -> {r}")
    if lib.seccomp_load(ctypes.c_void_p(ctx)) != 0:
        raise RuntimeError("seccomp_load failed")


def parse(argv: list[str]) -> dict:
    a = {"write": [], "ports": [], "log": None, "cmd": []}
    i = 0
    while i < len(argv):
        x = argv[i]
        if x == "--":
            a["cmd"] = argv[i + 1:]
            break
        if x == "--write":
            a["write"].append(os.path.realpath(argv[i + 1]))
        elif x == "--connect-port":
            a["ports"].append(int(argv[i + 1]))
        elif x == "--log":
            a["log"] = argv[i + 1]
        else:
            raise SystemExit(f"unknown option {x!r} (the command follows --)")
        i += 2
    return a


def run(argv: list[str]) -> None:
    a = parse(argv)
    if not a["cmd"]:
        raise SystemExit("no command")
    if a["log"]:
        with open(a["log"], "a") as f:
            f.write(json.dumps({"t": time.time(), "pid": os.getpid(), "argv": a["cmd"]}) + "\n")
    apply_landlock(a["write"], a["ports"])
    apply_seccomp()
    os.execvp(a["cmd"][0], a["cmd"])


SELFTEST_PROBE = r"""
import os, socket, json
r = {}
def t(name, fn):
    try:
        fn(); r[name] = "allowed"
    except Exception as e:
        r[name] = "blocked: " + type(e).__name__
t("write_inside", lambda: open(os.path.join(%r, "probe_ok.txt"), "w").write("x"))
t("write_outside_home", lambda: open(os.path.expanduser("~/.cxp_sandbox_probe_should_fail"), "w").write("x"))
t("write_tmp", lambda: open("/tmp/cxp_sandbox_probe_should_fail", "w").write("x"))
t("read_outside", lambda: open("/etc/hostname").read())
t("tcp_internet", lambda: socket.create_connection(("1.1.1.1", 443), timeout=5).close())
t("tcp_local_ssh", lambda: socket.create_connection(("127.0.0.1", 22), timeout=5).close())
t("udp_socket", lambda: socket.socket(socket.AF_INET, socket.SOCK_DGRAM).close())
t("dns", lambda: socket.getaddrinfo("example.com", 443))
print(json.dumps(r))
"""
SELFTEST_MUST_BLOCK = ("write_outside_home", "write_tmp", "tcp_internet", "tcp_local_ssh", "udp_socket", "dns")


def selftest(d: str) -> dict:
    """Runs the probes in a sandboxed child (writes allowed in d only, no TCP port); returns which actions were blocked."""
    d = os.path.realpath(d)
    out = subprocess.run([sys.executable, __file__, "--write", d, "--", sys.executable, "-c", SELFTEST_PROBE % d],
                         capture_output=True, text=True)
    try:
        res = json.loads(out.stdout.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        res = {"error": out.stderr[-800:]}
    for p in (os.path.expanduser("~/.cxp_sandbox_probe_should_fail"), "/tmp/cxp_sandbox_probe_should_fail"):
        if os.path.exists(p):
            res["LEFTOVER_" + p] = True
            os.remove(p)
    res["pass"] = (res.get("write_inside") == "allowed" and res.get("read_outside") == "allowed"
                   and all(str(res.get(k, "")).startswith("blocked") for k in SELFTEST_MUST_BLOCK))
    res["landlock_abi"] = landlock_abi()
    return res


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--selftest":
        print(json.dumps(selftest(sys.argv[2])))
    else:
        run(sys.argv[1:])
