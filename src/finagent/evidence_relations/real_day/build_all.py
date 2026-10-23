"""Builds all four real_day_perturbations families and writes them under data/evidence_relations/real_day_perturbations/
(or a given output root). CPU only, no GPU, no model calls. Re-runnable: calling main() twice with two different
output roots must produce byte-identical trees.

    finagent evidence-real-day               rebuild and write data/evidence_relations/real_day_perturbations/
    finagent evidence-real-day --out DIR     write to DIR instead

Ported from 1_overreaction/repro/evidence_relations/real_day_build_all.py.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from finagent.evidence_relations.real_day import common as C
from finagent.evidence_relations.real_day import priced_in as F2
from finagent.evidence_relations.real_day import redundancy as F1
from finagent.evidence_relations.real_day import stale as F3
from finagent.evidence_relations.real_day import swap as F4

FAMILIES = [
    ("redundancy_copies", F1),
    ("already_priced_in", F2),
    ("stale_news", F3),
    ("position_swap_conflict", F4),
]

README_BODY = {
    "redundancy_copies": """# redundancy_copies

One day-arm per (day, n_copies), n_copies in {{0, 1, 2, 4}}. The base prompt is the day pool's own ORIG harness
prompt for that day (finagent.harness.prompts.harness_prompt), byte-identical at n_copies=0. For n_copies>0, a
labelled "REDUNDANCY CHECK" block is appended, just before the final instruction line, with n_copies lines that
are deterministic re-expressions of ONE number already shown in that day's PRICE TOOL READINGS block:
`get_price_stats.ret_5d_pct` (chosen because it shares the forecast's own 5-trading-day horizon).

Transforms (fixed order, each a pure function of the source number X alone):
1. `redundancy_1dp`      round(X, 1)                            — re-rounded to 1 decimal place
2. `redundancy_int`      round(X, 0)                             — re-rounded to the nearest whole percent
3. `redundancy_bps`      round(X * 100, 0)                       — the same number in basis points
4. `redundancy_fraction` round(X / 100, 4)                       — the same number as a decimal fraction

## Ground truth claimed: EXACT, zero-shift

Every added line is checked, for every one of the {n_rows} rows, to be a pure function of X alone
(`redundancy.verify_pure_function`; `verified_pure_function_of_source` is true on every row — the build raises if
any row fails this). Because the added lines carry zero information beyond X, a rational forecaster's output
must be identical across n_copies in {{0, 1, 2, 4}}. This is a derivation, not an estimate, and it holds by
construction rather than by assumption about the model.

## Counts

- days: {n_days}
- rows (days x 4 arms): {n_rows}
- rows failing the pure-function check: 0 (the build aborts otherwise)

## Source-vs-port

| | source (1_overreaction, 6-ticker-pilot day pool) | this port (finance1, 96-ticker data/pit_cache) |
|---|---:|---:|
| days | 197 | {n_days} |
| rows | 788 | {n_rows} |
""",
    "already_priced_in": """# already_priced_in

One pair per constructible day: `same_day_real` vs `spliced_independent`. The COMPANY NEWS section of the day's
ORIG harness prompt is reduced to exactly one headline line (everything else of the prompt, including the day's
own price move in CLOSE/ACCOUNT/PRICE TOOL READINGS, is untouched and identical between the two conditions) —

- `same_day_real`: the most recent REAL headline of the ticker published on day t itself, before D(t)
  (point-in-time correct, `real_day.common.news_items_before_D`).
- `spliced_independent`: a REAL headline of the SAME ticker from a calendar date BEFORE day t (read directly from
  `data/pit_cache`, bypassing day t's own point-in-time cutoff ON PURPOSE — the model could plausibly have seen
  this headline on some earlier day, just not as "today's news"; headlines from AFTER day t are excluded
  entirely, so this never leaks a real future event). **This is a constructed, not point-in-time-correct-for-
  day-t, splice**: every row of this condition carries `spliced: true`, `original_time_published` (the
  headline's true, earlier date) and `displayed_time_published` (the slot it is shown in, copied from
  `same_day_real`'s own slot so the two prompts differ in nothing but headline content).
  Candidate choice: length-filtered (±max(20, 50%) chars of the real headline's title), then polarity-matched
  where possible (`real_day.common.keyword_polarity`, documented as approximate), then drawn with a seeded numpy
  Generator (`real_day.common.rng_for`) for reproducibility.

## The already_priced_in fix (ported from the start, not reintroduced)

The first build of this family, in the source project (1_overreaction), let "other day" include
headlines published AFTER day t, which in 26.4% of its constructed days (52/197) spliced in a real headline from
LATER than t — including genuine future company events. That confounds the hypothesis with a real,
as-of-day-t-unknowable event, i.e. a point-in-time leak. The fix (2026-10-20, in the source) restricts the
candidate pool for `spliced_independent` to `time_published` strictly before day t's calendar date. **This port
carries the fix from the start** (`priced_in.py` never had the bug), and `build_family()` additionally asserts
`n_future_leak == 0` on every run — every `spliced_independent` row's `original_time_published` is checked to be
dated strictly before day t.

## Ground truth claimed: ORDINAL hypothesis, not a hard label

Condition `spliced_independent` is hypothesised to move the forecast MORE than `same_day_real`, for headlines of
comparable salience — because the same-day headline's content is already the realised cause of the price move
the agent also observes, while the spliced headline is, by construction, unrelated to today's move and so is
not "already priced in" by it. This is recorded here as a testable hypothesis about model behaviour, never as a
derived number to score against. The length/polarity matching is a documented approximation of "comparable
salience", not a guarantee of it.

## Counts

- days checked: {n_days}
- days constructed (both conditions present): {n_constructed}
- days skipped: {n_skipped} (reasons in skipped.json)
- rows: {n_rows}
- rows with a post-day-t splice (must be 0): {n_future_leak}

## Source-vs-port

| | source (6-ticker-pilot day pool, fixed version) | this port (96-ticker data/pit_cache) |
|---|---:|---:|
| days checked | 197 | {n_days} |
| days skipped | 0 | {n_skipped} |
| rows | 394 | {n_rows} |
| post-day-t splice rows | 0 of 197 | {n_future_leak} of {n_constructed} |
""",
    "stale_news": """# stale_news

One pair per constructible day: `fresh_new` vs `stale_reinjected`. Same single-headline-line technique as
already_priced_in —

- `fresh_new`: the most recent REAL headline before D(t) (point-in-time correct), shown with its own real
  timestamp.
- `stale_reinjected`: a REAL headline of the SAME ticker, same source as `fresh_new` where possible, whose TRUE
  publication date is 10-20 calendar days before t. Shown verbatim except its DISPLAYED time_published is
  overridden to `fresh_new`'s own slot (`original_time_published` vs `displayed_time_published` logged on every
  row), so the only difference between the two prompts is the headline's content.

**The one real risk, handled explicitly**: a stale headline is only ever a real item whose own `time_published`
is checked to fall inside [t-20d, t-10d]; nothing here infers staleness from the mere absence of a closer item,
and a day with no real item in that window is skipped and logged, never backfilled from outside it.

## Ground truth claimed: DERIVED, with one documented approximation

By day t, a headline published 10-20 days earlier has already been in the public information set for at least
10 days and so is already reflected in the price action through close t that the agent also observes; re-showing
it as if new should therefore move the forecast LESS than a genuinely new headline of comparable length. The one
approximation: "comparable title length" stands in for "comparable salience", which is not otherwise measured.

## Counts

- days checked: {n_days}
- days constructed (both conditions present): {n_constructed}
- days skipped: {n_skipped} (reasons in skipped.json)
- rows: {n_rows}

## Source-vs-port

| | source (6-ticker-pilot day pool) | this port (96-ticker data/pit_cache) |
|---|---:|---:|
| days checked | 197 | {n_days} |
| days skipped | 0 | {n_skipped} |
| rows | 394 | {n_rows} |
""",
    "position_swap_conflict": """# position_swap_conflict

One pair per constructible day: two prompt variants that differ only in which of two already-present,
contradicting signals appears first / more prominently, holding every line's own content fixed.

- **Tier 1 (technical_block_lines, exact)**: two of the four categorical PRICE TOOL READINGS labels
  (`get_trend_signal.signal`, `get_rsi.signal`, `get_mean_reversion_signal.signal`, `get_macd.cross`) already
  disagree in sign under a documented polarity map (bullish/oversold = +1, bearish/overbought = -1). The first
  such pair (in registered block order) has its two LINES swapped in position
  (`real_day.common.swap_block_lines`, built on `finagent.arms.parse_block` — no block-parsing logic is
  reimplemented); every line's own text and every other line's position is unchanged.
- **Tier 2 (price_vs_headline_sentiment_fallback, approximate)**: used only when Tier 1 finds no pair. The day's
  own 1-day price direction (sign of r1_pct) versus the most recent pre-D(t) headline's simple keyword polarity
  (documented as approximate), when they disagree in sign. Rendered as two short, clearly labelled synthetic
  lines (SIGNAL A / SIGNAL B) in one of the two orders, appended once, with identical text in both orders.

## Ground truth claimed: NO-FLIP

A rational forecaster's output must not depend on which of two equal-content signals is listed first. Tier 1 is
an exact derivation (the two tool outputs are real, untouched data; only their order changes). Tier 2 is
approximate in one place only: whether the keyword-polarity label is a fair read of the headline's direction.

## Counts

- days checked: {n_days}
- days with a Tier-1 (exact) pair: {n_tier1}
- days with a Tier-2 (approximate) fallback pair: {n_tier2}
- days skipped (no pair found by either tier): {n_skipped} (reasons in skipped.json)
- rows: {n_rows}

## Source-vs-port

| | source (6-ticker-pilot day pool) | this port (96-ticker data/pit_cache) |
|---|---:|---:|
| days checked | 197 | {n_days} |
| days skipped | 114 | {n_skipped} |
| rows | 166 | {n_rows} |
""",
}

TOP_README = """# real_day_perturbations

Real-day evidence-relationship perturbations built on the evidence_relations day pool
(data/evidence_relations/day_pool/pool.jsonl, {n_days} days; see finagent.evidence_relations.real_day.common.load_day_pool)
and data/pit_cache's point-in-time price/news cache (now all 96 tickers, not just the pilot's six). CPU only, no
GPU, no model calls; every file here is produced by pure, deterministic code from already-verified inputs
(finagent.readings, finagent.arms, finagent.harness.prompts, finagent.evidence_relations.pool) plus data/pit_cache's
news_ticker.json, read directly. Code: src/finagent/evidence_relations/real_day/*.py. Ported from
1_overreaction/repro/evidence_relations/real_day_*.py (the already_priced_in family in its fixed, 2026-10-20
form — see that family's README.md section below for the fix itself).

Four families, each under its own directory with its own README.md (what ground truth is claimed — zero-shift,
ordinal, or no-flip — and how confidently) and its own MANIFEST.sha256:

| family | ground truth | confidence | rows (source -> port) | days skipped (source -> port) |
|---|---|---|---|---|
| redundancy_copies | expected shift is zero | exact derivation | 788 -> {n1} | 0 -> 0 |
| already_priced_in | ordinal (b moves forecast more than a) | documented hypothesis | 394 -> {n2} | 0 -> {s2} |
| stale_news | stale moves forecast less than fresh | derived, one approximation | 394 -> {n3} | 0 -> {s3} |
| position_swap_conflict | no flip from order alone | exact (tier 1) / approximate (tier 2) | 166 -> {n4} | 114 -> {s4} |

## Regenerate

```
cd finance1
.venv/bin/finagent evidence-real-day
```

Deterministic: the day pool is re-derived (not redrawn), every random choice uses a seeded numpy
`SeedSequence(BASE_SEED, spawn_key=(family, day_index, purpose))` Generator, and every generator is a pure function
of the read-only inputs above. `sha256sum -c MANIFEST.sha256` (run from inside this directory) checks every file
here against this manifest; running `finagent evidence-real-day` again produces a byte-identical tree (checked by
running it twice to two different output roots and diffing — see data/README.md's evidence_relations section).

## Days that could not be constructed

See each family's `skipped.json` for the full list with reasons. Tallied reasons:
{skip_tally}

## Scope

Each row carries a full, self-contained HARNESS prompt variant (`prompt`, the text
finagent.harness.prompts.harness_prompt would render for that arm, plus one `prompt_sha256` per row). The
coding-agent workspace files that finagent's coding framework also produces are NOT additionally materialised
here, since the testable claim in every family is about the forecast a prompt elicits, not about the coding-agent
framework.
"""


def _write_family(name: str, result: dict, out_root: Path) -> dict:
    fam_dir = out_root / name
    C.write_jsonl(fam_dir / "data.jsonl", result["rows"])
    (fam_dir / "skipped.json").write_text(json.dumps(result["skipped"], indent=1, sort_keys=True) + "\n")
    stats = {
        "n_days": result["n_days"], "n_rows": result["n_rows"],
        "n_constructed": result.get("n_days_constructed", result["n_days"] - result["n_skipped"]),
        "n_skipped": result["n_skipped"],
    }
    if name == "already_priced_in":
        stats["n_future_leak"] = result["n_future_leak"]
    if name == "position_swap_conflict":
        stats["n_tier1"] = sum(1 for r in result["rows"] if r.get("tier") == "technical_block_lines") // 2
        stats["n_tier2"] = sum(1 for r in result["rows"] if r.get("tier") == "price_vs_headline_sentiment_fallback") // 2
    (fam_dir / "README.md").write_text(README_BODY[name].format(**stats))
    C.write_manifest(fam_dir)
    return stats


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent evidence-real-day",
                                 description="Rebuild the four real_day_perturbations families.")
    ap.add_argument("--out", type=Path, default=C.DATA_ROOT, help=f"output root (default: {C.DATA_ROOT})")
    a = ap.parse_args(argv)
    out_root = a.out
    out_root.mkdir(parents=True, exist_ok=True)
    day_pool = C.load_day_pool()

    all_stats = {}
    all_skipped = []
    for name, mod in FAMILIES:
        result = mod.build_family(day_pool)
        all_stats[name] = _write_family(name, result, out_root)
        for s in result["skipped"]:
            all_skipped.append({"family": name, **s})

    tally: dict[str, int] = {}
    for s in all_skipped:
        tally[s["reason"]] = tally.get(s["reason"], 0) + 1
    skip_tally = "\n".join(f"- ({n}x) {reason}" for reason, n in sorted(tally.items(), key=lambda kv: -kv[1])) or "- none"

    (out_root / "README.md").write_text(TOP_README.format(
        n_days=len(day_pool),
        n1=all_stats["redundancy_copies"]["n_rows"], n2=all_stats["already_priced_in"]["n_rows"],
        n3=all_stats["stale_news"]["n_rows"], n4=all_stats["position_swap_conflict"]["n_rows"],
        s2=all_stats["already_priced_in"]["n_skipped"], s3=all_stats["stale_news"]["n_skipped"],
        s4=all_stats["position_swap_conflict"]["n_skipped"], skip_tally=skip_tally,
    ))
    C.write_manifest(out_root)

    summary = {"n_days": len(day_pool), "families": all_stats, "n_skipped_total": len(all_skipped),
               "skip_reason_tally": tally, "out_root": str(out_root)}
    print(json.dumps(summary, indent=1, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
