"""Analysis of the presentation pilot: every file in results/ recomputed from the run records (CPU only, no model call).

    finagent analyze                         records/raw (after `finagent unpack`) -> the six files of results/
    finagent analyze --check                 write nothing; exit 1 unless every output equals the file in results/
    finagent analyze --raw DIR --out DIR2    new runs (e.g. runs/pilot/raw): the measures of every model x framework cell
                                             present, by the same rules (describe.json, describe_tables.md and the metric
                                             records describe_reasoning_models.json); the page, its excerpts and the run
                                             counts belong to the shipped records and are not written

describe.py holds the rules, reasoning.py the five-model page, report.py the run counts, figures.py the charts.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from finagent import config, days
from finagent.analysis import describe, reasoning, report

MEASURES = ("describe.json", "describe_tables.md", "describe_reasoning_models.json")


def load(raw: Path) -> tuple[dict, dict]:
    """(records, day info with realised outcomes) of the run folders under raw/."""
    recs = report.load_records(raw)
    if not recs:
        raise SystemExit(f"no run records under {raw} (run `finagent unpack` first, or pass --raw)")
    info = describe.day_info(days.load())
    describe.add_realised(info)
    return recs, info


def build(raw: Path = config.RAW) -> dict[str, str]:
    """results/ file name -> content, from the 300 shipped run folders under raw/."""
    recs, info = load(raw)
    described = describe.describe(recs, info, raw)
    cells, page, metrics, examples = reasoning.build(recs, info, raw)
    n = reasoning.check_against_describe(cells, described)
    if n != len(described["cells"]):
        raise ValueError(f"only {n} of {len(described['cells'])} cells compared with describe.json")
    counts = report.counts(recs, days.load(), describe.MODEL_ORDER)
    return {"describe.json": json.dumps(described, indent=1),
            "describe_tables.md": describe.tables(described) + "\n",
            "describe_reasoning_models.json": json.dumps(metrics, indent=1, ensure_ascii=False),
            "describe_reasoning_models.md": page,
            "examples_reasoning_models.json": json.dumps(examples, indent=1, ensure_ascii=False),
            "pilot_counts.json": json.dumps(counts, indent=1)}


def measures(raw: Path) -> dict[str, str]:
    """The MEASURES files for the cells present under raw/ (any subset of cells, days and arms), by the same rules."""
    recs, info = load(raw)
    described = describe.describe(recs, info, raw)
    cells = [reasoning.cell(c["model"], c["framework"], recs, info, raw) for c in described["cells"]]
    reasoning.check_against_describe(cells, described)
    return dict(zip(MEASURES, (json.dumps(described, indent=1), describe.tables(described) + "\n",
                               json.dumps(reasoning.to_records(cells, info), indent=1, ensure_ascii=False))))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent analyze", description="Recompute results/ from the run records, or the measures "
                                 "of new runs (--raw DIR --out DIR2).")
    ap.add_argument("--raw", type=Path, default=config.RAW, help="folder of the run folders (default: records/raw)")
    ap.add_argument("--out", type=Path, default=config.RESULTS, help="where to write (default: results/)")
    ap.add_argument("--check", action="store_true", help="compare with the files in --out instead of writing them")
    a = ap.parse_args(argv)
    if a.raw.resolve() == config.RAW.resolve():
        outputs = build(a.raw)
    elif a.out.resolve() == config.RESULTS.resolve():
        raise SystemExit("--raw other than records/raw: new runs. Pass --out <folder> for their measures (results/ holds the "
                         "shipped ones).")
    else:
        outputs = measures(a.raw)
    differ = 0
    for name, text in outputs.items():
        data, path = text.encode("utf-8"), a.out / name
        if a.check:
            same = path.exists() and path.read_bytes() == data
            differ += not same
            print(f"{'same' if same else 'DIFFERENT':9s}  {name}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
            print(f"{hashlib.sha256(data).hexdigest()}  {path}")
    return 1 if differ else 0
