"""Fill the Finnhub company-news gaps with single-day calls (2026-11-02).

Why: Finnhub's company-news endpoint returns at most ~250 items per call (the newest ones). The October pulls used multi-day
windows, so for busy names each window kept only its last days (see data/README.md, 已知问题 "Finnhub 公司新闻有抓取上限").
A single day of one ticker fits under the cap for every name but NVDA on its busiest days, so every day that is not known to be
complete is fetched again on its own.

Which days are fetched (plan, written to _inventory/news_fill_plan_<date>.json):
  * the free tier reaches back one year: on 2026-11-02 the API returned nothing before 2025-11-07, so the plan starts there;
  * the Dow-30 monthly pull (news/dow30_raw, 2025-09-29..2026-03-31) has no per-call record of how many items the API returned, so
    its per-month truncation cannot be judged (the files hold fewer items than the API returned); every day of its range is refetched
    for the 30 names;
  * the October pull (raw/news_finnhub/fetch_state.json) records n per call: a call with n < 150 was not capped and its window
    [a, b] is complete; a capped call is complete only from its oldest returned item on. Every day of 2025-11-07..2026-09-18 that no
    complete span covers in full is refetched.
Calls go through the same endpoint, fields and spacing as the October pull (results/rcf_20261011/scripts/finnhub_lib.py): 1.1 s
between calls, 429 -> wait and retry, the token read from keys.txt at call time and never written anywhere; every call is appended
to raw/news_finnhub/finnhub_calls.jsonl; items are merged by id into raw/news_finnhub/raw/<TK>.json; the call is recorded in
fetch_state.json with tag "s5" (min / max item time, n, trunc = n >= 150).

    python _scripts/fill_finnhub_news.py --plan-only
    nohup python _scripts/fill_finnhub_news.py > _inventory/news_fill_20261102.log 2>&1 &     (resumable: done (ticker, day) pairs are skipped)
"""
from __future__ import annotations
import argparse, datetime as dt, json, os, sys, threading, time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

import requests

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "raw/news_finnhub/raw"; STATE = ROOT / "raw/news_finnhub/fetch_state.json"; LEDGER = ROOT / "raw/news_finnhub/finnhub_calls.jsonl"
DOW_DIR = ROOT / "news/dow30_raw"
KEYS_FILE = Path("/srv/shared_home/lmz/ai/keys.txt")
FIELDS = ("id", "datetime", "headline", "summary", "source", "url", "related")
TAG = "s5"
FLOOR = dt.date(2025, 11, 7)          # the free tier's reach on 2026-11-02 (2025-11-05 -> 0 items, 2025-11-07 -> 76)
END = dt.date(2026, 9, 18)
DOW_PULL_END = dt.date(2026, 3, 31)
TRUNC_N = 150
U = dt.timezone.utc
WORKERS = 1                 # one call at a time: two workers at 1.3 s spacing drew 429s in bursts on 2026-11-02
MIN_GAP_S = 1.15            # between call starts
_LOCK = threading.Lock(); _RATE = threading.Lock(); _last = [0.0]


def _pace():
    with _RATE:
        wait = _last[0] + MIN_GAP_S - time.time()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()


def read_key() -> str:
    for line in KEYS_FILE.read_text().splitlines():
        if line.lower().startswith("finhub key"):
            v = line.split(":", 1)[1] if ":" in line else line[len("finhub key"):]
            return v.strip().lstrip("=").strip()
    raise SystemExit("no Finnhub key line")


def day0(s: str) -> int:
    return int(dt.datetime.fromisoformat(s).replace(tzinfo=U).timestamp())


def complete_spans(calls: list[dict]) -> list[tuple[int, int]]:
    """UTC spans known to be complete from the October pull's calls (and from earlier s5 calls)."""
    iv = []
    for c in calls:
        if c.get("n") is None:
            continue
        lo, hi = day0(c["a"]), day0(c["b"]) + 86400
        if c["n"] >= TRUNC_N:
            if c.get("min") is None:
                continue
            lo = c["min"]
        iv.append((lo, hi))
    iv.sort(); out = []
    for lo, hi in iv:
        if out and lo <= out[-1][1]:
            out[-1] = (out[-1][0], max(out[-1][1], hi))
        else:
            out.append((lo, hi))
    return out


def plan(state: dict, universe: list[str]) -> dict[str, list[str]]:
    dow = {p.stem for p in DOW_DIR.glob("*.json")}
    days = [FLOOR + dt.timedelta(d) for d in range((END - FLOOR).days + 1)]
    P = {}
    for tk in universe:
        spans = complete_spans([c for c in state.get(tk, {}).get("calls", []) if c.get("tag") != TAG])
        need = []
        for d in days:
            if tk in dow and d <= DOW_PULL_END:
                need.append(d.isoformat()); continue
            a = day0(d.isoformat()); b = a + 86400
            if not any(lo <= a and b <= hi for lo, hi in spans):
                need.append(d.isoformat())
        P[tk] = need
    return P


def merge_items(tk: str, items: list[dict]) -> int:
    p = RAW_DIR / f"{tk}.json"
    old = json.loads(p.read_text()) if p.exists() else []
    seen = {x["id"] for x in old}; n_new = 0
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"]); old.append(it); n_new += 1
    old.sort(key=lambda x: (x["datetime"] or 0, x["id"]))
    tmp = p.with_suffix(".tmp"); tmp.write_text(json.dumps(old, ensure_ascii=False)); tmp.replace(p)
    return n_new


def call(tok: str, tk: str, a: str, b: str) -> list[dict] | None:
    status = None
    for attempt in range(4):
        _pace()
        try:
            r = requests.get("https://finnhub.io/api/v1/company-news", params={"symbol": tk, "from": a, "to": b, "token": tok}, timeout=30)
            status = r.status_code
        except Exception as e:                                      # noqa: BLE001  (never log str(e): it may carry the URL with the token)
            with _LOCK, LEDGER.open("a") as f:
                f.write(json.dumps({"t": time.time(), "tk": tk, "from": a, "to": b, "status": -1, "err": type(e).__name__, "n": None, "tag": TAG}) + "\n")
            time.sleep(10); continue
        if status == 429:
            with _LOCK, LEDGER.open("a") as f:
                f.write(json.dumps({"t": time.time(), "tk": tk, "from": a, "to": b, "status": 429, "n": None, "tag": TAG}) + "\n")
            time.sleep(30 * (attempt + 1)); continue
        break
    items = None
    if status == 200:
        try:
            batch = r.json()
            if isinstance(batch, list):
                items = [{k: it.get(k) for k in FIELDS} for it in batch]
        except Exception:                                           # noqa: BLE001
            items = None
    with _LOCK, LEDGER.open("a") as f:
        f.write(json.dumps({"t": time.time(), "tk": tk, "from": a, "to": b, "status": status, "n": None if items is None else len(items), "tag": TAG}) + "\n")
    return items


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--plan-only", action="store_true"); ap.add_argument("--tickers", default=None)
    args = ap.parse_args()
    universe = [l.strip() for l in (ROOT / "_inventory/universe_95.txt").read_text().splitlines() if l.strip()]
    if args.tickers:
        universe = [t for t in args.tickers.split(",") if t in universe]
    state = json.loads(STATE.read_text())
    P = plan(state, universe)
    stamp = dt.date.today().strftime("%Y%m%d")
    summary = {"date": str(dt.date.today()), "floor": FLOOR.isoformat(), "end": END.isoformat(), "calls_planned": sum(len(v) for v in P.values()),
               "by_ticker": {k: len(v) for k, v in P.items()},
               "by_month": {}}
    for v in P.values():
        for d in v:
            summary["by_month"][d[:7]] = summary["by_month"].get(d[:7], 0) + 1
    summary["by_month"] = dict(sorted(summary["by_month"].items()))
    (ROOT / f"_inventory/news_fill_plan_{stamp}.json").write_text(json.dumps({**summary, "days": P}, indent=0))
    print(json.dumps({k: v for k, v in summary.items() if k != "by_ticker"}, indent=1)); print("top:", sorted(summary["by_ticker"].items(), key=lambda x: -x[1])[:10])
    if args.plan_only:
        return
    tok = read_key(); t0 = time.time(); prog = {"calls": 0, "new": 0, "fails": 0, "stop": False}

    def done_days(tk: str) -> set:
        """Days already fetched whose items are present: a day whose raw file holds fewer items dated that UTC day than the call
        returned is fetched again (guards against a lost merge)."""
        calls = [c for c in state.get(tk, {}).get("calls", []) if c.get("tag") == TAG and c.get("n") is not None]
        if not calls:
            return set()
        p = RAW_DIR / f"{tk}.json"; raw = json.loads(p.read_text()) if p.exists() else []
        by_day = {}
        for x in raw:
            if x.get("datetime"):
                k = dt.datetime.fromtimestamp(x["datetime"], U).date().isoformat(); by_day[k] = by_day.get(k, 0) + 1
        ok, redo = set(), []
        for c in calls:
            if by_day.get(c["a"], 0) >= c["n"]:
                ok.add(c["a"])
            else:
                redo.append(c["a"])
        if redo:
            print(f"{tk}: {len(redo)} fetched days hold fewer items than returned; fetching again", flush=True)
            state[tk]["calls"] = [c for c in state[tk]["calls"] if not (c.get("tag") == TAG and c["a"] in set(redo))]
        return ok

    def work(tk: str):
        have = done_days(tk)
        for d in P[tk]:
            if d in have or prog["stop"]:
                continue
            items = call(tok, tk, d, d)
            with _LOCK:
                if items is None:
                    prog["fails"] += 1
                    if prog["fails"] >= 10:
                        prog["stop"] = True; print("too many failed calls; stopping", flush=True)
                    continue
                prog["fails"] = 0
                ts = [x["datetime"] for x in items if x["datetime"]]
                rec = {"a": d, "b": d, "tag": TAG, "n": len(items), "min": min(ts) if ts else None, "max": max(ts) if ts else None, "trunc": len(items) >= TRUNC_N}
                n_new = merge_items(tk, items)
                state.setdefault(tk, {"calls": []})["calls"].append(rec)
                tmp = STATE.with_suffix(".tmp"); tmp.write_text(json.dumps(state, indent=0)); tmp.replace(STATE)
                prog["calls"] += 1; prog["new"] += n_new
                if prog["calls"] % 50 == 0:
                    print(f"{prog['calls']} calls, {prog['new']} new items, {time.time() - t0:.0f}s, last {tk} {d} n={len(items)}", flush=True)

    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        list(ex.map(work, [tk for tk in P if P[tk]]))
    print(f"done: {prog['calls']} calls, {prog['new']} new items, {time.time() - t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
