"""Day selection (CPU only): 6 decision days of the Qwen3-8B S1 sample with a registered readings block, 3 big-move and 3 ordinary.

Candidates: day ids in grounding_blocks.json AND s1_spec.json whose saved anchor is valid on both anchor days.
Size of today's move: z = r1 / (sigma5 / sqrt(5)), the spec's own z_today (r1 = day t's 1-day return, sigma5 = the rational 5-day
prior sd at close t); both use information through close t only, the outcome fields next to them are never read.
  big |z| >= 2, ordinary |z| < 1 (days with 1 <= |z| < 2 are not used, so the two groups are clearly apart)
Draw: each group's candidates sorted by day id, permuted with numpy default_rng(SEED) (big first, then ordinary, one generator),
taken in that order, skipping a day whose ticker or date is already taken, until 3 + 3. Cross-checks are stored with each day:
r1 from the cache's bars, the trailing 60-day sd, and the registered block recomputed by the toolbox (must be byte-identical).

    finagent days               rebuild the selection and compare it byte for byte with data/days.json
    finagent days --write PATH  also write the rebuilt file
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics as st
from datetime import datetime
from pathlib import Path

import numpy as np

from finagent import config, readings
from finagent.data.anchors import load_anchor
from finagent.data.pit import news_cache

# Where the inputs lived in the original project; days.json records these paths (the files themselves are under data/).
ORIGINAL_PATHS = {"grounding_blocks": "results/grounding_20261012/grounding_blocks.json",
                  "s1_spec": "results/q3news_20261012/s1_spec.json",
                  "anchors": "results/q3news_20261012/S1/anchors"}


def sha_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def candidates() -> list[dict]:
    blocks = readings.registered_blocks()
    spec = json.loads(config.S1_SPEC.read_text())
    out = []
    for d in spec["days"]:
        did = d["day_id"]
        if did not in blocks:
            continue
        if not all(load_anchor(did)["anchor_valid"]):
            continue
        pr = d["prior_and_outcome_not_used_in_selection"]
        sigma5 = math.exp(pr["lsig"])
        out.append({"day_id": did, "ticker": d["ticker"], "t": d["t"], "D": d["D"], "anchor_days": d["anchor_days"],
                    "branch_seed_base": d["branch_seed_base"], "universe_split": d.get("universe_split"),
                    "z": float(pr["z_today"]), "r1_pct": float(pr["r1"]), "sigma5_prior_pct": sigma5,
                    "daily_sd_prior_pct": sigma5 / math.sqrt(5)})
    return sorted(out, key=lambda x: x["day_id"])


def draw(cands: list[dict]) -> list[dict]:
    c = config.EXPERIMENT["days"]
    rng = np.random.default_rng(config.EXPERIMENT["seed"])
    big = [x for x in cands if abs(x["z"]) >= c["big_z"]]
    ordn = [x for x in cands if abs(x["z"]) < c["ordinary_z"]]
    taken, tks, dates = [], set(), set()
    for group, n, kind in ((big, c["n_big"], "big"), (ordn, c["n_ordinary"], "ordinary")):
        got = 0
        for j in rng.permutation(len(group)):
            x = group[j]
            if x["ticker"] in tks or x["t"] in dates:
                continue
            taken.append({**x, "day_type": kind}); tks.add(x["ticker"]); dates.add(x["t"]); got += 1
            if got == n:
                break
        if got < n:
            raise RuntimeError(f"only {got} {kind} days")
    return taken


def cross_check(d: dict) -> dict:
    cache = news_cache(d["ticker"])
    bars = cache.tool_bars(datetime.strptime(d["t"], "%Y-%m-%d"))
    c = [b["close"] for b in bars]
    if bars[-1]["date"][:10] != d["t"]:
        raise RuntimeError(f"{d['day_id']}: last bar {bars[-1]['date']} is not day t")
    r1_simple = (c[-1] / c[-2] - 1) * 100
    lr = [math.log(c[i] / c[i - 1]) * 100 for i in range(1, len(c))]
    sd60 = st.pstdev(lr[-61:-1])                                       # the 60 days before today
    reg = readings.registered_blocks()[d["day_id"]]
    now = readings.compute_block(cache, d["t"])
    return {"r1_simple_from_bars_pct": r1_simple, "r1_log_from_bars_pct": lr[-1], "sd60_daily_pct": sd60,
            "z_vs_sd60": lr[-1] / sd60 if sd60 else None, "block_sha256": reg["sha256"],
            "block_recomputed_identical": now == reg["block"], "block_problems": readings.block_problems(reg["block"], d["t"]),
            "n_bars_through_t": len(bars), "first_bar": bars[0]["date"][:10], "last_bar": bars[-1]["date"][:10]}


def build() -> dict:
    """The days.json object (selection, cross-checks, source hashes)."""
    c = config.EXPERIMENT["days"]
    cands = candidates()
    chosen = draw(cands)
    for d in chosen:
        d["check"] = cross_check(d)
        d["anchor_file"] = f"{ORIGINAL_PATHS['anchors']}/{d['day_id']}.json.gz"
        d["anchor_sha256"] = sha_file(config.anchor_file(d["day_id"]))
        if not d["check"]["block_recomputed_identical"] or d["check"]["block_problems"]:
            raise RuntimeError(f"{d['day_id']}: registered block not reproducible: {d['check']}")
    return {"workflow": config.EXPERIMENT["workflow"], "seed": config.EXPERIMENT["seed"],
            "rule": {"candidates": "grounding_blocks.json day ids in s1_spec.json with valid saved S1 anchors",
                     "z": "r1 / (exp(lsig) / sqrt(5)) = the spec's z_today (information through close t only)",
                     "big": f"|z| >= {c['big_z']}", "ordinary": f"|z| < {c['ordinary_z']}",
                     "draw": "per group sorted by day id, numpy default_rng(SEED).permutation (big first, then ordinary, one "
                             "generator), skip a ticker or date already taken"},
            "pool": {"n_candidates": len(cands), "n_big": sum(abs(x["z"]) >= c["big_z"] for x in cands),
                     "n_ordinary": sum(abs(x["z"]) < c["ordinary_z"] for x in cands)},
            "sources": {"grounding_blocks": {"path": ORIGINAL_PATHS["grounding_blocks"], "sha256": sha_file(config.GROUNDING_BLOCKS)},
                        "s1_spec": {"path": ORIGINAL_PATHS["s1_spec"], "sha256": sha_file(config.S1_SPEC)}},
            "days": chosen}


def load() -> list[dict]:
    """The 6 pilot days (data/days.json "days")."""
    return json.loads(config.DAYS_FILE.read_text())["days"]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent days", description="Rebuild the day selection and compare it with data/days.json.")
    ap.add_argument("--write", type=Path, help="also write the rebuilt days.json here")
    a = ap.parse_args(argv)
    text = json.dumps(build(), indent=1)
    if a.write:
        a.write.write_text(text)
    o = json.loads(text)
    print(f"pool {o['pool']}")
    for d in o["days"]:
        c = d["check"]
        print(f"{d['day_type']:9s} {d['day_id']:18s} z={d['z']:+.2f} r1={d['r1_pct']:+.2f}% daily_sd={d['daily_sd_prior_pct']:.2f}% "
              f"(bars: r1 {c['r1_simple_from_bars_pct']:+.2f}%, z vs 60d sd {c['z_vs_sd60']:+.2f}) block ok={c['block_recomputed_identical']}")
    same = text == config.DAYS_FILE.read_text()
    print(f"identical to {config.DAYS_FILE}: {same}")
    return 0 if same else 1
