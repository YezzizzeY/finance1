"""The evidence_relations extension: day pool counts, the four real_day_perturbations families, and a small
tool_redundancy smoke test (the full 96-ticker walk is exercised by `finagent evidence-tools`, not by every test
run). No network, no model calls -- all against data/pit_cache (96 tickers) and data/selection/.
"""
from __future__ import annotations

import json

from finagent.evidence_relations import pool
from finagent.evidence_relations.real_day import common as C
from finagent.evidence_relations.real_day import build_all, priced_in, redundancy, stale, swap
from finagent.evidence_relations.tool_redundancy import generate as TRG


def test_pool_counts():
    pools = pool.build_pools()
    assert pools["counts"]["n_candidates"] == 250
    assert pools["counts"]["n_train"] == 60
    assert pools["counts"]["n_test_core"] == 24
    assert pools["counts"]["n_test_full"] == 137
    assert sum(d["day_type"] == "big" for d in pools["train"]) == 1
    assert sum(d["day_type"] == "ordinary" for d in pools["train"]) == 59
    assert sum(d["day_type"] == "big" for d in pools["test_core"]) == 12
    assert sum(d["day_type"] == "ordinary" for d in pools["test_core"]) == 12
    assert sum(d["day_type"] == "big" for d in pools["test_full"]) == 12
    assert sum(d["day_type"] == "ordinary" for d in pools["test_full"]) == 125
    train_tk = {d["ticker"] for d in pools["train"]}
    test_tk = {d["ticker"] for d in pools["test_full"]}
    assert not train_tk & test_tk


def test_pool_jsonl_roundtrip(tmp_path):
    pools = pool.build_pools()
    info = pool.write_pool_jsonl(pools, tmp_path)
    assert info["n_rows"] == 197
    rows = [json.loads(line) for line in (tmp_path / "pool.jsonl").read_text().splitlines()]
    assert len(rows) == 197
    assert len({r["day_id"] for r in rows}) == 197


def test_day_pool_matches_written_pool_jsonl():
    """load_day_pool() cross-checks itself against data/evidence_relations/day_pool/pool.jsonl; this just exercises it."""
    days = C.load_day_pool()
    assert len(days) == 197
    assert {d["index"] for d in days} == set(range(197))


def test_redundancy_copies_counts():
    result = redundancy.build_family(C.load_day_pool())
    assert result["n_rows"] == 788
    assert result["n_skipped"] == 0
    assert all(r["verified_pure_function_of_source"] for r in result["rows"])


def test_already_priced_in_fix_holds():
    """The 2026-10-20 fix: 0 of 197 spliced_independent rows may splice a headline dated on/after day t."""
    result = priced_in.build_family(C.load_day_pool())
    assert result["n_rows"] == 394
    assert result["n_skipped"] == 0
    assert result["n_future_leak"] == 0
    assert priced_in.verify_no_future_leak(result["rows"]) == 0


def test_stale_news_counts():
    result = stale.build_family(C.load_day_pool())
    assert result["n_rows"] == 394
    assert result["n_skipped"] == 0


def test_position_swap_conflict_counts():
    result = swap.build_family(C.load_day_pool())
    assert result["n_rows"] == 166
    assert result["n_skipped"] == 114


def test_build_all_is_deterministic(tmp_path):
    out1, out2 = tmp_path / "a", tmp_path / "b"
    s1 = build_all.main(["--out", str(out1)])
    s2 = build_all.main(["--out", str(out2)])
    assert s1 == 0 and s2 == 0
    for p1 in sorted(out1.rglob("*")):
        if p1.is_file():
            p2 = out2 / p1.relative_to(out1)
            assert p2.read_bytes() == p1.read_bytes(), f"{p1.relative_to(out1)} differs between two runs"


def test_tool_redundancy_included_tools():
    assert len(TRG.AVAILABLE_TOOLS) == 31
    assert len(TRG.INCLUDED_TOOLS) == 23
    assert set(TRG.INCLUDED_TOOLS) | TRG.EXCLUDED_TOOLS == set(TRG.AVAILABLE_TOOLS)


def test_tool_redundancy_process_ticker_smoke():
    """One ticker's full walk: every included tool runs and returns parseable JSON for every eligible day."""
    ticker = sorted(p.name for p in __import__("finagent").config.PIT_CACHE.iterdir() if p.is_dir())[0]
    rows = TRG.process_ticker(ticker)
    assert len(rows) > 200    # ~248 trading days in the news window
    assert all(r["ticker"] == ticker for r in rows)
