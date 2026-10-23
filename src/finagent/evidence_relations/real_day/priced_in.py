"""Family 2, already_priced_in: does the forecast move more for a headline that does NOT correlate with the day's
own price move than for one that does, for equally salient headlines?

For each day, the COMPANY NEWS section of the ORIG harness prompt is reduced to exactly ONE headline line (so the
only difference between the two prompt variants is which headline is shown, not how many), under two conditions:

  (a) same_day_real: the most recent REAL headline of that ticker published on day t itself before D(t)
      (finagent.evidence_relations.real_day.common.news_items_before_D, the existing point-in-time feed — not
      reimplemented here). This is the "plausibly explains the move" condition: the price move the agent also sees
      is already the realised consequence of this headline.
  (b) spliced_independent: a REAL headline of the SAME ticker, published on a DIFFERENT calendar date BEFORE day t
      (never after t — see the fix note below), read directly from data/pit_cache/<ticker>/.../news_ticker.json
      (bypassing the point-in-time cutoff of day t specifically, on purpose — the model could plausibly have seen
      this headline on some earlier day, just not as "today's news" on day t; this is a constructed counterfactual,
      not a point-in-time-correct reading for day t, and is labelled as such in every row and in README.md). Its
      title/summary/source are shown verbatim; its DISPLAYED time_published is overridden to the exact display slot
      condition (a) used (logged in both `original_time_published` and `displayed_time_published`), so the two
      prompt variants differ in nothing but the headline's content.

  FIX (ported from 1_overreaction, found there by independent verification on 2026-10-20): the first build
  let "other day" include headlines published AFTER day t, which in 26.4% of that project's constructed days
  (52/197) spliced in a real headline from LATER than t — including genuine future company events (e.g. a CEO
  succession headline, an actual trial readout) up to 153 days after t. That confounds the "not yet reflected in
  the price" hypothesis with a real, as-of-day-t-unknowable event, which is a point-in-time leak, not a merely-
  unrelated headline. This port carries the fix from the start: the candidate pool for (b) is restricted to
  time_published strictly before day t's calendar date, and build_family() below asserts 0 rows ever get a
  post-day-t splice (see verify_no_future_leak()).

Candidate selection for (b) (OURS, documented): among the ticker's other-day headlines, keep those whose title
length is within max(20, 0.5 * len(title_a)) characters of condition (a)'s title (a "roughly comparable length"
filter; relaxed to the full other-day set if that is empty, logged as `length_filter_relaxed`). Within that set,
prefer the subset whose simple keyword polarity (common.keyword_polarity, documented as approximate) matches
condition (a)'s polarity (a "nice-to-have" sentiment match per the brief; relaxed to the full length-filtered set
if no same-polarity candidate exists, logged as `sentiment_filter_relaxed`). One candidate is then drawn uniformly
at random from the surviving set with a seeded numpy Generator (common.rng_for), over the set sorted by
(time_published, id) so the draw is reproducible regardless of on-disk JSON order.

Ground truth claimed (ORDINAL, not a hard number — see README.md): condition (b) is hypothesised to move the
forecast MORE than condition (a), for headlines of comparable salience. This is a testable hypothesis about model
behaviour (over-reaction to a headline that is not actually corroborated by the concurrent price move), not a
derived fact; it is recorded as a hypothesis, never as a label to score against.

A day is skipped (logged with a reason, never silently dropped) when there is no same-day headline before D(t), or
when the ticker has no earlier-day headline at all to splice from.

Ported from 1_overreaction/repro/evidence_relations/real_day_priced_in.py (the already-fixed version).
"""
from __future__ import annotations

from finagent.evidence_relations.real_day import common as C


def _same_day_items(d: dict) -> list[dict]:
    items = C.news_items_before_D(d)
    tday = d["t"].replace("-", "")
    return [i for i in items if i["time_published"][:8] == tday]


def verify_no_future_leak(rows: list[dict]) -> int:
    """Count of spliced_independent rows whose original_time_published is dated on or after day t — must be 0
    (the fix this module carries from the start; see the module docstring)."""
    n = 0
    for r in rows:
        if r["condition"] != "spliced_independent":
            continue
        tday = r["t"].replace("-", "")
        if r["original_time_published"][:8] >= tday:
            n += 1
    return n


def build_family(day_pool: list[dict]) -> dict:
    rows, skipped = [], []
    for d in day_pool:
        same_day = _same_day_items(d)
        if not same_day:
            skipped.append({"day_id": d["day_id"], "reason": "no same-day headline before D(t)"})
            continue
        h_a = max(same_day, key=lambda i: i["time_published"])
        title_a, source_a = h_a.get("title") or "", h_a.get("source") or ""
        tp_a = h_a["time_published"]
        pol_a = C.keyword_polarity(title_a + ". " + (h_a.get("summary") or ""))

        tday = d["t"].replace("-", "")
        others = [i for i in C.raw_news_ticker(d["ticker"])
                  if i["time_published"][:8] < tday and (i.get("title") or "") and i.get("title") != title_a]
        if not others:
            skipped.append({"day_id": d["day_id"], "reason": "no earlier-day headline for this ticker in data/pit_cache"})
            continue

        max_dev = max(20, 0.5 * len(title_a))
        length_filtered = [i for i in others if abs(len(i.get("title") or "") - len(title_a)) <= max_dev]
        length_filter_relaxed = not length_filtered
        pool_b = length_filtered or others

        pol_filtered = [i for i in pool_b if C.keyword_polarity((i.get("title") or "") + ". " + (i.get("summary") or "")) == pol_a]
        sentiment_filter_relaxed = not pol_filtered
        pool_final = pol_filtered or pool_b
        pool_final = sorted(pool_final, key=lambda i: (i["time_published"], i.get("id", 0)))

        rng = C.rng_for("already_priced_in", d["index"], 0)
        h_b = pool_final[int(rng.integers(0, len(pool_final)))]
        title_b, source_b = h_b.get("title") or "", h_b.get("source") or ""

        base_prompt = C.harness_prompt_orig(d)
        line_a = C.company_news_line(tp_a, title_a, source_a)
        line_b = C.company_news_line(tp_a, title_b, source_b)        # same displayed slot as (a), spliced content
        prompt_a = C.replace_company_news(base_prompt, line_a)
        prompt_b = C.replace_company_news(base_prompt, line_b)
        if prompt_a == prompt_b:
            raise RuntimeError(f"{d['day_id']}: the two conditions produced an identical prompt")

        common_fields = {
            "family": "already_priced_in", "day_id": d["day_id"], "ticker": d["ticker"], "t": d["t"],
            "split": d["split"], "pool": d["pool"], "day_type": d["day_type"],
            "ground_truth": "ordinal_hypothesis: condition b should move the forecast more than condition a",
            "length_filter_relaxed": length_filter_relaxed, "sentiment_filter_relaxed": sentiment_filter_relaxed,
            "pair_id": d["day_id"],
        }
        rows.append({**common_fields, "condition": "same_day_real",
                     "headline_time_published": tp_a, "headline_title": title_a, "headline_source": source_a,
                     "headline_keyword_polarity": pol_a, "spliced": False,
                     "prompt": prompt_a, "prompt_chars": len(prompt_a), "prompt_sha256": C.sha256_text(prompt_a)})
        rows.append({**common_fields, "condition": "spliced_independent",
                     "headline_time_published": tp_a, "headline_title": title_b, "headline_source": source_b,
                     "headline_keyword_polarity": C.keyword_polarity(title_b + ". " + (h_b.get("summary") or "")),
                     "spliced": True, "original_time_published": h_b["time_published"],
                     "displayed_time_published": tp_a,
                     "prompt": prompt_b, "prompt_chars": len(prompt_b), "prompt_sha256": C.sha256_text(prompt_b)})

    n_future_leak = verify_no_future_leak(rows)
    if n_future_leak:
        raise RuntimeError(f"already_priced_in: {n_future_leak} spliced_independent row(s) leaked a post-day-t "
                           "headline (the 2026-10-20 fix regressed)")
    return {"rows": rows, "n_days": len(day_pool), "n_rows": len(rows), "n_days_constructed": len(rows) // 2,
            "n_skipped": len(skipped), "skipped": skipped, "n_future_leak": n_future_leak}


def main(argv: list[str] | None = None) -> int:
    import json
    result = build_family(C.load_day_pool())
    print(json.dumps({"n_days": result["n_days"], "n_rows": result["n_rows"], "n_skipped": result["n_skipped"],
                      "n_future_leak": result["n_future_leak"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
