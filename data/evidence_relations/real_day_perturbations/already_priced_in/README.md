# already_priced_in

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

- days checked: 197
- days constructed (both conditions present): 197
- days skipped: 0 (reasons in skipped.json)
- rows: 394
- rows with a post-day-t splice (must be 0): 0

## Source-vs-port

| | source (6-ticker-pilot day pool, fixed version) | this port (96-ticker data/pit_cache) |
|---|---:|---:|
| days checked | 197 | 197 |
| days skipped | 0 | 0 |
| rows | 394 | 394 |
| post-day-t splice rows | 0 of 197 | 0 of 197 |
