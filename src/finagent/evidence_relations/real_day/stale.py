"""Family 3, stale_news: a headline already available 10-20 days before day t, re-injected as if it just appeared,
versus a genuinely new headline from just before D(t).

For each day, the COMPANY NEWS section of the ORIG harness prompt is reduced to exactly ONE headline line (same
technique as priced_in.py), under two conditions:

  fresh_new: the most recent REAL headline of the ticker published before D(t) (common.news_items_before_D,
      unmodified — its own real time_published is shown).
  stale_reinjected: a REAL headline of the SAME ticker, from the SAME source as fresh_new where possible, whose
      TRUE publication date is 10-20 calendar days before t (checked against the raw time_published of an item
      that genuinely exists in data/pit_cache/<ticker>/.../news_ticker.json — never an assumption from absence of
      data; see "the one real risk" below). Its title/summary/source are shown verbatim; its DISPLAYED
      time_published is overridden to fresh_new's own time_published (logged in `original_time_published` vs
      `displayed_time_published`), so the two prompt variants again differ in nothing but the headline's content,
      exactly as in priced_in.py.

Candidate selection for the stale headline (OURS): among items with the same source as fresh_new and
time_published date in [t-20d, t-10d] inclusive, pick the one whose title length is closest to fresh_new's title
(ties broken by earlier date, then lower id — fully deterministic, no RNG needed here). If no same-source
candidate exists in that window, the source constraint is relaxed to any source (logged as `source_filter_relaxed`).

The one real risk, handled explicitly: a "stale" headline is only ever a headline whose time_published timestamp
is itself real and inside [t-20d, t-10d]; nothing here infers "it must have been available" from the mere absence
of a closer item. A day where the window holds no real item at all is skipped and logged with that reason — it is
never filled in with something outside the window.

Ground truth claimed (DERIVED, with one documented approximation — see README.md): the stale headline's content
entered the public information set 10-20 days before t, so by day t it is already reflected in the price action
the agent also observes (the bars through close t); re-showing it with today's timestamp should therefore move
the forecast LESS than a genuinely new headline of comparable length. The approximation is "comparable length" as
a proxy for comparable salience — content salience itself is not measured.

A day is skipped (logged with a reason) when there is no headline at all before D(t) (no fresh_new), or when no
real headline exists for the ticker in the [t-20d, t-10d] window (no stale candidate).

Ported from 1_overreaction/repro/evidence_relations/real_day_stale.py (unchanged math).
"""
from __future__ import annotations

from datetime import datetime, timedelta

from finagent.evidence_relations.real_day import common as C

LOW_DAYS, HIGH_DAYS = 20, 10


def build_family(day_pool: list[dict]) -> dict:
    rows, skipped = [], []
    for d in day_pool:
        items = C.news_items_before_D(d)
        if not items:
            skipped.append({"day_id": d["day_id"], "reason": "no headline at all before D(t) for this ticker/day"})
            continue
        h_fresh = max(items, key=lambda i: i["time_published"])
        title_fresh, source_fresh, tp_fresh = h_fresh.get("title") or "", h_fresh.get("source") or "", h_fresh["time_published"]

        t_date = datetime.strptime(d["t"], "%Y-%m-%d")
        lo = (t_date - timedelta(days=LOW_DAYS)).strftime("%Y%m%d")
        hi = (t_date - timedelta(days=HIGH_DAYS)).strftime("%Y%m%d")
        window = [i for i in C.raw_news_ticker(d["ticker"])
                  if lo <= i["time_published"][:8] <= hi and (i.get("title") or "") and i.get("title") != title_fresh]
        if not window:
            skipped.append({"day_id": d["day_id"], "reason": f"no real headline for this ticker in [t-{LOW_DAYS}d, "
                                                               f"t-{HIGH_DAYS}d] = [{lo}, {hi}]"})
            continue

        same_source = [i for i in window if i.get("source") == source_fresh]
        source_filter_relaxed = not same_source
        pool_stale = same_source or window
        h_stale = min(pool_stale, key=lambda i: (abs(len(i.get("title") or "") - len(title_fresh)), i["time_published"], i.get("id", 0)))
        title_stale, source_stale = h_stale.get("title") or "", h_stale.get("source") or ""
        if h_stale["time_published"][:8] < lo or h_stale["time_published"][:8] > hi:
            raise RuntimeError(f"{d['day_id']}: chosen stale headline's own time_published is outside the checked window")

        base_prompt = C.harness_prompt_orig(d)
        line_fresh = C.company_news_line(tp_fresh, title_fresh, source_fresh)
        line_stale = C.company_news_line(tp_fresh, title_stale, source_stale)   # displayed slot = fresh_new's own slot
        prompt_fresh = C.replace_company_news(base_prompt, line_fresh)
        prompt_stale = C.replace_company_news(base_prompt, line_stale)
        if prompt_fresh == prompt_stale:
            raise RuntimeError(f"{d['day_id']}: the two conditions produced an identical prompt")

        common_fields = {
            "family": "stale_news", "day_id": d["day_id"], "ticker": d["ticker"], "t": d["t"],
            "split": d["split"], "pool": d["pool"], "day_type": d["day_type"],
            "ground_truth": "stale_reinjected_should_move_the_forecast_less_than_fresh_new",
            "source_filter_relaxed": source_filter_relaxed, "window_days": [LOW_DAYS, HIGH_DAYS],
            "pair_id": d["day_id"],
        }
        rows.append({**common_fields, "condition": "fresh_new",
                     "headline_time_published": tp_fresh, "headline_title": title_fresh, "headline_source": source_fresh,
                     "prompt": prompt_fresh, "prompt_chars": len(prompt_fresh), "prompt_sha256": C.sha256_text(prompt_fresh)})
        rows.append({**common_fields, "condition": "stale_reinjected",
                     "headline_time_published": tp_fresh, "headline_title": title_stale, "headline_source": source_stale,
                     "original_time_published": h_stale["time_published"], "displayed_time_published": tp_fresh,
                     "days_before_t": (t_date - datetime.strptime(h_stale["time_published"][:8], "%Y%m%d")).days,
                     "prompt": prompt_stale, "prompt_chars": len(prompt_stale), "prompt_sha256": C.sha256_text(prompt_stale)})
    return {"rows": rows, "n_days": len(day_pool), "n_rows": len(rows), "n_days_constructed": len(rows) // 2,
            "n_skipped": len(skipped), "skipped": skipped}


def main(argv: list[str] | None = None) -> int:
    import json
    result = build_family(C.load_day_pool())
    print(json.dumps({"n_days": result["n_days"], "n_rows": result["n_rows"], "n_skipped": result["n_skipped"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
