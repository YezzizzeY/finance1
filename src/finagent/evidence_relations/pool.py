"""The day pool (CPU only, no model calls): the TRAIN / TEST_CORE / TEST_FULL split of every candidate day that
carries a registered PRICE TOOL READINGS block, now that data/pit_cache holds all 96 tickers (not just the six
pilot ones).

Built on finagent.days.candidates() (the same 250 candidates finagent.days already verifies: a day_id in
data/selection/s1_spec.json with a block in data/selection/grounding_blocks.json and a valid saved anchor) instead
of re-deriving the candidate rule. Every candidate's ticker is already inside the 96-ticker data/pit_cache set (a
project-wide fact this module re-checks, not assumes, in build_pools() below).

day_type, with the same constants finagent.days uses (setup/experiment.toml [days] big_z=2.0, ordinary_z=1.0):
  big        |z| >= big_z
  ordinary   |z| < ordinary_z
  mid        everything else (here, 1 <= |z| < 2); kept in the candidate list, dropped from every pool below.

Pools (ported from 1_overreaction/repro/agent_trading_days/pool.py; see
data/evidence_relations/day_pool/README.md for the full write-up and the source-vs-port count comparison):

  TRAIN      universe_split == "train", day_type in {big, ordinary}: 1 big + 59 ordinary. Each row carries
             sample_weight = 0.5/n_big (the 1 big row) or 0.5/n_ordinary (the 59 ordinary rows), so that sampling
             TRAIN rows proportional to sample_weight gives 50% big / 50% ordinary expected mass despite the
             1-vs-59 count imbalance. This re-weights what already exists; it does not fix the scarcity itself —
             every "big" weighted draw still comes from the one same underlying day (same ticker, same date).
  TEST_CORE  universe_split == "heldout", day_type in {big, ordinary}: every heldout big day (12, no draw needed)
             plus an equal-sized (12) seeded draw of heldout ordinary days (draw_test_core, below): candidates
             sorted by day_id, numpy default_rng(TEST_CORE_SEED).permutation, skip a day whose ticker or calendar
             date is already taken. finagent.days.draw() is never called or edited here: it stays pinned to its own
             n=3+3 / seed 20261018 pilot draw.
  TEST_FULL  universe_split == "heldout", day_type in {big, ordinary}: every one of them (12 + 125 = 137).
             TEST_CORE is a subset of TEST_FULL by construction (every TEST_CORE day carries in_test_core=True
             inside TEST_FULL; never written out a second time).

Ticker disjointness between TRAIN and TEST_FULL/TEST_CORE is asserted here, not assumed: both are filtered on
universe_split, a field finagent.days.candidates() reads straight out of data/selection/s1_spec.json, and other
work built on that field already treats every "heldout" ticker as one the model side of this project has never
trained on.

    finagent evidence-pool               rebuild the pool and print its counts
    finagent evidence-pool --out DIR     also write DIR/pool.jsonl (default: data/evidence_relations/day_pool/)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from finagent import config, days, readings
from finagent.evidence_relations import ROOT

OUT_DIR = ROOT / "day_pool"

TEST_CORE_SEED = 20261020            # ported from 1_overreaction/repro/agent_trading_days/pool.py's TEST_CORE_SEED

EXPECTED_COUNTS = {
    ("train", "big"): 1, ("train", "ordinary"): 59, ("train", "mid"): 17,
    ("heldout", "big"): 12, ("heldout", "ordinary"): 125, ("heldout", "mid"): 36,
}


def day_type(z: float) -> str:
    c = config.EXPERIMENT["days"]
    az = abs(z)
    if az >= c["big_z"]:
        return "big"
    if az < c["ordinary_z"]:
        return "ordinary"
    return "mid"


def enrich(d: dict) -> dict:
    """A finagent.days.candidates() row with day_type added. Unlike the ported source, no anchor_file is added here:
    finagent.config.anchor_file(day_id) already derives it from day_id alone, so pool_row() computes it directly."""
    e = dict(d)
    e["day_type"] = day_type(d["z"])
    return e


def draw_test_core(big: list[dict], ordinary: list[dict], seed: int = TEST_CORE_SEED) -> list[dict]:
    """ALL of `big` plus an equal-sized seeded sample of `ordinary`: candidates sorted by day_id, numpy
    default_rng(seed).permutation of the ordinary candidates, skipping a day whose ticker or date is already taken
    (by a chosen big day, or by an already-chosen ordinary day in this same draw) — the same mechanics as
    finagent.days.draw(), written fresh here (that function stays pinned to its own n=3+3 / seed 20261018 pilot
    draw and must not be reused or edited)."""
    big = sorted(big, key=lambda c: c["day_id"])
    ordinary = sorted(ordinary, key=lambda c: c["day_id"])
    tks = {c["ticker"] for c in big}
    dates = {c["t"] for c in big}
    chosen: list[dict] = []
    rng = np.random.default_rng(seed)
    for j in rng.permutation(len(ordinary)):
        c = ordinary[j]
        if c["ticker"] in tks or c["t"] in dates:
            continue
        chosen.append(c); tks.add(c["ticker"]); dates.add(c["t"])
        if len(chosen) == len(big):
            break
    if len(chosen) < len(big):
        raise RuntimeError(f"only drew {len(chosen)} ordinary day(s) for test_core, need {len(big)}")
    return big + chosen


def build_pools() -> dict:
    """{"train": [...], "test_core": [...], "test_full": [...], "counts": {...}}. Every day dict is the enriched
    candidates() row (day_type added; sample_weight added on train rows; in_test_core added on test_full rows).
    test_core's dicts are the SAME objects as the matching test_full dicts (not copies), so in_test_core set on
    test_full is visible from test_core too."""
    cands = [enrich(d) for d in days.candidates()]

    by_group: dict[tuple[str, str], list[dict]] = {}
    for d in cands:
        by_group.setdefault((d["universe_split"], d["day_type"]), []).append(d)

    counts = {k: len(by_group.get(k, [])) for k in EXPECTED_COUNTS}
    for k, want in EXPECTED_COUNTS.items():
        got = counts[k]
        if got != want:
            raise RuntimeError(f"day_type count changed for {k}: expected {want}, now {got} -- re-derive the pool "
                               "design, do not silently continue")

    train_days = by_group.get(("train", "big"), []) + by_group.get(("train", "ordinary"), [])
    n_big, n_ord = counts[("train", "big")], counts[("train", "ordinary")]
    w_big, w_ord = 0.5 / n_big, 0.5 / n_ord
    for d in train_days:
        d["sample_weight"] = w_big if d["day_type"] == "big" else w_ord

    held_big = by_group.get(("heldout", "big"), [])
    held_ord = by_group.get(("heldout", "ordinary"), [])
    test_full = held_big + held_ord
    test_core = draw_test_core(held_big, held_ord)
    core_ids = {d["day_id"] for d in test_core}
    for d in test_full:
        d["in_test_core"] = d["day_id"] in core_ids

    train_tk = {d["ticker"] for d in train_days}
    test_tk = {d["ticker"] for d in test_full}
    if train_tk & test_tk:
        raise RuntimeError(f"ticker overlap between train and test pools: {sorted(train_tk & test_tk)}")

    # every candidate's ticker must already be inside the 96-ticker data/pit_cache set this pool depends on downstream
    missing_cache = sorted({d["ticker"] for d in cands} - {p.name for p in config.PIT_CACHE.iterdir() if p.is_dir()})
    if missing_cache:
        raise RuntimeError(f"{len(missing_cache)} candidate ticker(s) have no data/pit_cache entry: {missing_cache[:5]}")

    full_ids = {d["day_id"] for d in test_full}
    if not core_ids <= full_ids:
        raise RuntimeError("test_core has a day_id not in test_full")
    if len(test_core) != 2 * len(held_big):
        raise RuntimeError("test_core is not an equal-sized big/ordinary split")

    return {"train": train_days, "test_core": test_core, "test_full": test_full,
            "counts": {"n_candidates": len(cands), "by_universe_split_and_type": {f"{a}/{b}": v for (a, b), v in counts.items()},
                       "n_train": len(train_days), "n_test_core": len(test_core), "n_test_full": len(test_full),
                       "n_test_full_only": len(test_full) - len(test_core),
                       "train_tickers": sorted(train_tk), "test_tickers": sorted(test_tk)}}


def pool_row(d: dict, split: str) -> dict:
    return {"day_id": d["day_id"], "ticker": d["ticker"], "t": d["t"], "split": split, "day_type": d["day_type"],
            "z": d["z"], "r1_pct": d["r1_pct"], "sample_weight": d.get("sample_weight"),
            "in_test_core": bool(d.get("in_test_core", False)),
            "anchor_sha256": hashlib.sha256(config.anchor_file(d["day_id"]).read_bytes()).hexdigest(),
            "block_sha256": hashlib.sha256(readings.registered_block(d["day_id"]).encode("utf-8")).hexdigest(),
            "universe_split": d["universe_split"]}


def write_pool_jsonl(pools: dict, out_dir: Path = OUT_DIR) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = ([pool_row(d, "train") for d in sorted(pools["train"], key=lambda d: d["day_id"])]
            + [pool_row(d, "test") for d in sorted(pools["test_full"], key=lambda d: d["day_id"])])
    if len(rows) != len(pools["train"]) + len(pools["test_full"]):
        raise RuntimeError("row count != union(train, test_full); a day_id got duplicated")
    if len({r["day_id"] for r in rows}) != len(rows):
        raise RuntimeError("duplicate day_id in pool.jsonl")
    path = out_dir / "pool.jsonl"
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    w_sum: dict[str, float] = {}
    for r in rows:
        if r["sample_weight"] is not None:
            w_sum[r["day_type"]] = w_sum.get(r["day_type"], 0.0) + r["sample_weight"]
    return {"n_rows": len(rows), "path": str(path), "sample_weight_sum_by_day_type": w_sum}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent evidence-pool",
                                 description="Rebuild the day pool (TRAIN/TEST_CORE/TEST_FULL) and write pool.jsonl.")
    ap.add_argument("--out", type=Path, default=OUT_DIR, help=f"output folder (default: {OUT_DIR})")
    a = ap.parse_args(argv)
    pools = build_pools()
    info = write_pool_jsonl(pools, a.out)
    print(json.dumps(pools["counts"], indent=1))
    print(json.dumps(info, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
