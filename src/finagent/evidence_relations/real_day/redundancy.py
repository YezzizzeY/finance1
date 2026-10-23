"""Family 1, redundancy_copies: append 0/1/2/4 deterministic re-expressions of ONE number already shown in the
day's registered PRICE TOOL READINGS block, and check the forecast should not move as copies increase.

Reading used: get_price_stats.ret_5d_pct (X), the block's own 5-day return figure — chosen because it is at the
same horizon as the forecast the trading-day task asks for (p_up / expected_return_pct / expected_vol_pct over
"the next 5 trading days"), so a redundant re-statement of it is the most on-topic possible distractor.

Transforms (OURS; each a pure function of X alone, no other input, verified below for every row):
  T1 rounded_1dp       round(X, 1)                              "re-rounded to 1 decimal place"
  T2 rounded_int       round(X, 0)                               "re-rounded to the nearest whole percent"
  T3 basis_points       round(X * 100, 0)                        "the same number in basis points (1% = 100 bps)"
  T4 decimal_fraction   round(X / 100, 4)                        "the same number as a decimal fraction, not a percent"
Arms (n_copies in {0, 1, 2, 4}) take the first n_copies transforms in this fixed order. n_copies=0 is the day
pool's own ORIG harness prompt, byte-identical, with nothing appended.

Ground truth claimed (EXACT, see README.md): the four added lines carry zero information beyond what X already
states, so a rational forecaster's output must be identical across n_copies in {0, 1, 2, 4}. This is a
derivation, not an estimate: it holds by construction, checked line by line against X. Ported from
1_overreaction/repro/evidence_relations/real_day_redundancy.py (unchanged math).
"""
from __future__ import annotations

import json

from finagent import arms
from finagent.evidence_relations.real_day import common as C

N_COPIES = (0, 1, 2, 4)
READING_TOOL, READING_FIELD = "get_price_stats", "ret_5d_pct"


def transforms(x: float) -> list[dict]:
    t1 = C.round_disp(x, 1)
    t2 = int(C.round_disp(x, 0))
    t3 = int(C.round_disp(x * 100, 0))
    t4 = C.round_disp(x / 100, 4)
    return [
        {"name": "redundancy_1dp", "formula": "round(X, 1)", "value": t1,
         "line": f"- redundancy_1dp: the same 5-day return figure above, re-rounded to 1 decimal place: {t1}%"},
        {"name": "redundancy_int", "formula": "round(X, 0)", "value": t2,
         "line": f"- redundancy_int: the same 5-day return figure above, re-rounded to the nearest whole percent: {t2}%"},
        {"name": "redundancy_bps", "formula": "round(X * 100, 0)", "value": t3,
         "line": f"- redundancy_bps: the same 5-day return figure above, re-expressed in basis points (1% = 100 bps): {t3} bps"},
        {"name": "redundancy_fraction", "formula": "round(X / 100, 4)", "value": t4,
         "line": f"- redundancy_fraction: the same 5-day return figure above, re-expressed as a decimal fraction "
                  f"rather than a percent: {t4}"},
    ]


def verify_pure_function(x: float, added: list[dict]) -> list[str]:
    """Recompute each transform from X alone and assert it equals the line's stored value; returns problems (empty = ok)."""
    want = transforms(x)
    probs = []
    for w, got in zip(want, added):
        if w["value"] != got["value"] or w["line"] != got["line"]:
            probs.append(f"{got.get('name')}: recomputed {w['value']} != stored {got['value']}")
    return probs


def build_family(day_pool: list[dict]) -> dict:
    rows, problems = [], []
    for d in day_pool:
        block = C.registered_block(d)
        fields = {name: json.loads(js) for pre, name, js in arms.parse_block(block)}
        x = float(fields[READING_TOOL][READING_FIELD])
        all_lines = transforms(x)
        base_prompt = C.harness_prompt_orig(d)
        for n in N_COPIES:
            added = all_lines[:n]
            if n == 0:
                variant_prompt = base_prompt
            else:
                header = ("\n\nREDUNDANCY CHECK (deterministic re-expressions of "
                           f"{READING_TOOL}.{READING_FIELD} already shown in PRICE TOOL READINGS above; "
                           "no new information)\n")
                variant_prompt = C.insert_before_final(base_prompt, header + "\n".join(a["line"] for a in added))
            probs = verify_pure_function(x, added)
            if probs:
                problems.append({"day_id": d["day_id"], "n_copies": n, "problems": probs})
            rows.append({
                "family": "redundancy_copies", "day_id": d["day_id"], "ticker": d["ticker"], "t": d["t"],
                "split": d["split"], "pool": d["pool"], "day_type": d["day_type"],
                "n_copies": n,
                "source_reading": f"{READING_TOOL}.{READING_FIELD}", "source_value": C.round_disp(x, 4),
                "added_lines": added,
                "verified_pure_function_of_source": not probs,
                "ground_truth": "expected_shift_is_zero",
                "prompt": variant_prompt,
                "prompt_chars": len(variant_prompt),
                "prompt_sha256": C.sha256_text(variant_prompt),
            })
    if problems:
        raise RuntimeError(f"redundancy_copies: {len(problems)} row(s) failed the pure-function check: {problems[:3]}")
    return {"rows": rows, "n_days": len(day_pool), "n_rows": len(rows), "n_skipped": 0, "skipped": []}


def main(argv: list[str] | None = None) -> int:
    result = build_family(C.load_day_pool())
    print(json.dumps({"n_days": result["n_days"], "n_rows": result["n_rows"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
