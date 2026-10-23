"""The run list, decision parsing and the per-run record (shared by both frameworks).

Runs: model x framework x day x arm x k (ORIG k = 0, 1; one run of each other arm), 30 per model x framework.
run_id = <model>__<framework>__<day_id>__<arm>__<k> names our folders only; the agent never sees it.
Seed = branch_seed_base of the day + seed_offset + arm_seed_step x arm index + k (setup/experiment.toml [runs]), so no two
runs share a sampling stream (only vLLM uses it).
A finished run leaves <store>/<run_id>/record.json and one line in <store>.jsonl (raw/ + raw.jsonl in the pilot).
"""
from __future__ import annotations

import gzip
import json
import math
import os
import threading
import time
from pathlib import Path

from finagent import config

_LINES_LOCK = threading.Lock()                                                 # line files are shared by concurrent batches
DECISION_FIELDS = ("action", "shares", "target_exposure_pct", "p_up", "expected_return_pct", "expected_vol_pct", "confidence")


def runs(days: list[dict], models=None, frameworks=None) -> list[dict]:
    """Every run of the design in run order: model -> framework -> day -> arm -> k."""
    r = config.EXPERIMENT["runs"]
    out = []
    for m in models or config.MODELS:
        for fw in frameworks or config.FRAMEWORKS:
            for d in days:
                for ai, arm in enumerate(config.ARMS):
                    for k in range(r["per_arm"][arm]):
                        out.append({"run_id": f"{m}__{fw}__{d['day_id']}__{arm}__{k}", "model": m, "framework": fw,
                                    "day_id": d["day_id"], "day_type": d["day_type"], "arm": arm, "k": k,
                                    "seed": int(d["branch_seed_base"]) + r["seed_offset"] + r["arm_seed_step"] * ai + k})
    return out


def parse_number(v):
    """A decision field as a finite float, else None. Lenient on purpose (strings such as '3.5%' accepted): this is how the
    record reads a submitted forecast, unlike the harness's own strict harness.session.finite_float."""
    if isinstance(v, bool) or v is None:
        return None
    try:
        x = float(v)
    except (TypeError, ValueError, OverflowError):
        if isinstance(v, str):
            try:
                x = float(v.strip().rstrip("%").strip())
            except ValueError:
                return None
        else:
            return None
    return x if math.isfinite(x) else None


def parse_decision(dec) -> tuple[dict, bool]:
    """The decision fields as submitted (numbers as floats), and whether the forecast is usable (positive vol, numeric return)."""
    if not isinstance(dec, dict):
        return {k: None for k in DECISION_FIELDS}, False
    out = {"action": (str(dec.get("action")).strip().capitalize() if dec.get("action") is not None else None)}
    for k in DECISION_FIELDS[1:]:
        out[k] = parse_number(dec.get(k))
    ok = out["expected_vol_pct"] is not None and out["expected_vol_pct"] > 0 and out["expected_return_pct"] is not None
    return out, ok


def serving_fields(model: str, framework: str, served_max_model_len: int, gpu_index: int) -> dict:
    """Extra record fields of a model with record_serving = true (Qwen3.8-27B): served context, GPU and the harness token cap."""
    m = config.MODELS[model]
    if not m.get("record_serving"):
        return {}
    out = {"served_max_model_len": served_max_model_len, "gpu_index": gpu_index}
    if framework == "harness":
        out["max_tokens_per_turn"] = m["harness"]["max_tokens"]
    return out


class RunStore:
    """Run folders <root>/<run_id>/ and the line file <root>.jsonl (one record per finished run). Resumable: done() runs skip."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.lines = self.root.with_suffix(".jsonl")

    def run_dir(self, run_id: str) -> Path:
        return self.root / run_id

    def done(self, run_id: str) -> bool:
        return (self.run_dir(run_id) / "record.json").exists()

    def write(self, rec: dict) -> None:
        d = self.run_dir(rec["run_id"])
        d.mkdir(parents=True, exist_ok=True)
        rec.setdefault("finished_epoch", time.time())
        tmp = d / "record.json.part"
        tmp.write_text(json.dumps(rec, indent=1, default=str))
        os.replace(tmp, d / "record.json")
        with _LINES_LOCK, open(self.lines, "a") as f:
            f.write(json.dumps(rec, default=str) + "\n")


def dump_gz(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, default=float)
    os.replace(tmp, path)


def load_gz(path: Path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)
