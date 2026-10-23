"""Shared helpers for the real_day_perturbations families: real headline/number surgery on the day pool's own ORIG
harness prompts, built entirely from finagent's existing, already-verified data and code (finagent.readings,
finagent.arms, finagent.harness.prompts, finagent.data.pit.news_cache) — nothing here reimplements prompt
rendering, block parsing or point-in-time cutoffs. Ported from
1_overreaction/repro/evidence_relations/real_day_common.py.

Day pool: EXACTLY the day pool of data/evidence_relations/day_pool/pool.jsonl (same day_ids, same split boundaries),
reconstructed via finagent.evidence_relations.pool.build_pools() — not redrawn here. The two are cross-checked
against each other at load time (same set of day_ids), so this module cannot silently drift from the pool.

Determinism: one numpy SeedSequence per (family, day_index, purpose), spawned from a single BASE_SEED with an
explicit spawn_key tuple — the same convention finagent.evidence_relations.pool already uses for its own seeded
draw (draw_test_core's numpy default_rng). Every number shown in a README or a report is rounded to a fixed number
of decimals before printing (round_disp).
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path

import numpy as np

from finagent import arms, config, readings
from finagent.data.pit import news_cache
from finagent.evidence_relations import ROOT
from finagent.evidence_relations import pool as POOL
from finagent.harness.prompts import NEWS_CAP, harness_prompt

BASE_SEED = 20261020                          # same seed epoch as evidence_relations.pool.TEST_CORE_SEED
FAMILY_INDEX = {"redundancy_copies": 0, "already_priced_in": 1, "stale_news": 2, "position_swap_conflict": 3}

DATA_ROOT = ROOT / "real_day_perturbations"

NEWS_HEADER = f"COMPANY NEWS (past 7 days, most recent {NEWS_CAP})\n"
NEWS_FOOTER = "\n\nFISCAL POLICY NEWS"
FINAL_HARNESS = readings.FINAL                 # "\n\nDecide today's action and call submit_decision."

# ---------------------------------------------------------------------------------------------- keyword polarity
# A deliberately small, documented, approximate bag-of-words lexicon (OURS, ported unchanged from the source). Not
# a sentiment model: counts whole words (regex \b[a-z']+\b, lower-cased) in title+summary, returns
# sign(n_pos - n_neg) in {-1, 0, 1}. Used only where the brief calls for "simple keyword polarity, approximate".
POS_WORDS = frozenset("""
beats beat surge surges surged soar soars soared rally rallies rallied jumps jump jumped gain gains gained
raises raise raised upgrade upgrades upgraded outperform buy bullish record strong growth climbs climb climbed
optimistic upside tops boosts boost boosted higher wins win winning expands expansion exceeds exceeded
""".split())
NEG_WORDS = frozenset("""
falls fall fell drop drops dropped plunge plunges plunged miss misses missed cuts cut downgrade downgrades
downgraded underperform sell bearish weak weakness loss losses declines decline declined warns warning warned
lawsuit investigation recall slump slumps slumped tumbles tumble tumbled lower halts halted probe fraud
shortfall layoffs layoff
""".split())
_WORD_RX = re.compile(r"[a-z']+")


def keyword_polarity(text: str) -> int:
    words = _WORD_RX.findall((text or "").lower())
    n_pos = sum(1 for w in words if w in POS_WORDS)
    n_neg = sum(1 for w in words if w in NEG_WORDS)
    return 0 if n_pos == n_neg else (1 if n_pos > n_neg else -1)


# ---------------------------------------------------------------------------------------------- numeric helpers
def round_disp(x, nd: int = 4):
    """Round a Python/NumPy float to ``nd`` decimals for display; -0.0 -> 0.0. Deterministic, no randomness."""
    v = float(np.round(np.asarray(x, dtype=np.float64), nd))
    return v + 0.0


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def rng_for(family: str, day_index: int, purpose: int = 0) -> np.random.Generator:
    """One independent PCG64 stream per (family, day_index, purpose); same convention as evidence_relations.pool."""
    ss = np.random.SeedSequence(BASE_SEED, spawn_key=(FAMILY_INDEX[family], int(day_index), int(purpose)))
    return np.random.Generator(np.random.PCG64(ss))


# ---------------------------------------------------------------------------------------------- day pool
def load_day_pool() -> list[dict]:
    """The 197 days of data/evidence_relations/day_pool/pool.jsonl, re-derived from
    finagent.evidence_relations.pool.build_pools() (not read back from pool.jsonl as the only source: same
    candidates(), same TEST_CORE_SEED), sorted by day_id for a fixed, reproducible index. Cross-checked against the
    existing pool.jsonl's day_id set so this cannot silently diverge from it."""
    pools = POOL.build_pools()
    core_ids = {d["day_id"] for d in pools["test_core"]}
    by_id = {d["day_id"]: d for d in pools["train"] + pools["test_full"]}

    pool_jsonl = POOL.OUT_DIR / "pool.jsonl"
    if not pool_jsonl.exists():
        raise RuntimeError(f"{pool_jsonl} is missing; run `finagent evidence-pool` first")
    jsonl_rows = {}
    with open(pool_jsonl) as f:
        for line in f:
            r = json.loads(line)
            jsonl_rows[r["day_id"]] = r
    if set(jsonl_rows) != set(by_id):
        raise RuntimeError("day pool re-derived here does not match data/evidence_relations/day_pool/pool.jsonl's day_id "
                           f"set (only here: {sorted(set(by_id) - set(jsonl_rows))[:5]}, only in pool.jsonl: "
                           f"{sorted(set(jsonl_rows) - set(by_id))[:5]})")

    out = []
    for i, day_id in enumerate(sorted(by_id)):
        d = by_id[day_id]
        r = jsonl_rows[day_id]
        pool_name = "train" if d["universe_split"] == "train" else ("test_core" if day_id in core_ids else "test_full_only")
        out.append({"index": i, "day_id": day_id, "ticker": d["ticker"], "t": d["t"], "universe_split": d["universe_split"],
                    "pool": pool_name, "split": r["split"], "day_type": r["day_type"], "z": r["z"], "r1_pct": r["r1_pct"]})
    return out


# ---------------------------------------------------------------------------------------------- prompt text surgery
def harness_prompt_orig(d: dict) -> str:
    p = harness_prompt({"day_id": d["day_id"], "ticker": d["ticker"], "t": d["t"]}, "ORIG")
    if not p.endswith(FINAL_HARNESS):
        raise RuntimeError(f"{d['day_id']}: ORIG harness prompt does not end with the final instruction line")
    return p


def registered_block(d: dict) -> str:
    return readings.registered_block(d["day_id"])


def insert_before_final(prompt_text: str, extra: str) -> str:
    """Insert ``extra`` (already starting with its own blank-line separator) just before the final instruction
    line, exactly where finagent.readings.insert_block puts the PRICE TOOL READINGS block."""
    if not prompt_text.endswith(FINAL_HARNESS):
        raise RuntimeError("prompt does not end with the final instruction line")
    return prompt_text[: -len(FINAL_HARNESS)] + extra + FINAL_HARNESS


def company_news_line(time_published: str, title: str, source: str) -> str:
    """Exactly finagent.harness.prompts.render_prompt's news_block format for one item: '- [time] title (source)'."""
    return f"- [{time_published}] {title} ({source})"


def replace_company_news(prompt_text: str, line_or_none: str | None) -> str:
    """Replace the COMPANY NEWS section's item list (between the fixed header and footer strings
    finagent.harness.prompts.render_prompt always renders) with exactly one line, or '- (none)'. Asserts the
    anchors occur exactly once, the same safety check finagent.readings.insert_block uses for its own splice."""
    if prompt_text.count(NEWS_HEADER) != 1:
        raise RuntimeError("COMPANY NEWS header not found exactly once")
    start = prompt_text.index(NEWS_HEADER) + len(NEWS_HEADER)
    rest = prompt_text[start:]
    if rest.count(NEWS_FOOTER) == 0:
        raise RuntimeError("COMPANY NEWS footer not found")
    end = start + rest.index(NEWS_FOOTER)
    new_body = line_or_none if line_or_none else "- (none)"
    return prompt_text[:start] + new_body + prompt_text[end:]


def swap_block_lines(block: str, tool_a: str, tool_b: str) -> str:
    """The registered PRICE TOOL READINGS block with the two named tool lines' positions swapped; every line's own
    text (prefix + JSON) is untouched. Uses finagent.arms.parse_block, not a reimplementation of block parsing."""
    parsed = arms.parse_block(block)                    # [(prefix, name, json_str), ...] in registered order
    names = [p[1] for p in parsed]
    ia, ib = names.index(tool_a), names.index(tool_b)
    reordered = list(parsed)
    reordered[ia], reordered[ib] = reordered[ib], reordered[ia]
    lines = [readings.HEADER] + [pre + js for pre, name, js in reordered]
    return "\n".join(lines)


def splice_block(prompt_text: str, orig_block: str, new_block: str) -> str:
    if prompt_text.count(orig_block) != 1:
        raise RuntimeError("original block not found exactly once in prompt")
    return prompt_text.replace(orig_block, new_block, 1)


# ---------------------------------------------------------------------------------------------- point-in-time news
def news_items_before_D(d: dict) -> list[dict]:
    """Every item of the ticker's own feed with time_published < D(t), newest-cutoff but otherwise unfiltered —
    finagent.data.pit.NewsCache.window, the harness's own point-in-time cutoff method, used directly (not the
    7-day-lookback news_items() the prompt itself shows): this is families 2/3's pool of real "before D(t)"
    headlines to pick the most recent one from, which can be older than 7 days."""
    cache = news_cache(d["ticker"]).view()
    as_of = datetime.strptime(d["t"], "%Y-%m-%d")
    D = cache.decision_time(as_of)
    items = cache.window("ticker", "0", D)
    return sorted(items, key=lambda i: (i["time_published"], i.get("id", 0)))


_NEWS_TICKER_CACHE: dict[str, list[dict]] = {}


def raw_news_ticker(ticker: str) -> list[dict]:
    """The ticker's full news_ticker.json (data/pit_cache), sorted (time_published, id) ascending, cached in memory
    per ticker. Read directly (not through NewsCache): families 2/3 deliberately splice across days, bypassing the
    point-in-time cutoff NewsCache enforces, which is why this reads the raw file instead."""
    if ticker not in _NEWS_TICKER_CACHE:
        items = json.loads((config.news_cache_dir(ticker) / "news_ticker.json").read_text())
        items = sorted(items, key=lambda i: (i["time_published"], i.get("id", 0)))
        _NEWS_TICKER_CACHE[ticker] = items
    return _NEWS_TICKER_CACHE[ticker]


# ---------------------------------------------------------------------------------------------- output plumbing
def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, sort_keys=True) + "\n")


def write_manifest(dirpath: Path) -> Path:
    """sha256  ./relative/path for every file under dirpath except MANIFEST.sha256 itself, sorted by path — same
    format as data/MANIFEST.sha256 (checkable with 'sha256sum -c MANIFEST.sha256' run from inside dirpath)."""
    dirpath = Path(dirpath)
    out = dirpath / "MANIFEST.sha256"
    files = sorted(p for p in dirpath.rglob("*") if p.is_file() and p.name != "MANIFEST.sha256")
    lines = [f"{sha256_file(p)}  ./{p.relative_to(dirpath).as_posix()}" for p in files]
    out.write_text("\n".join(lines) + ("\n" if lines else ""))
    return out
