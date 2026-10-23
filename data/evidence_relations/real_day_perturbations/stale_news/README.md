# stale_news

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

- days checked: 197
- days constructed (both conditions present): 197
- days skipped: 0 (reasons in skipped.json)
- rows: 394

## Source-vs-port

| | source (6-ticker-pilot day pool) | this port (96-ticker data/pit_cache) |
|---|---:|---:|
| days checked | 197 | 197 |
| days skipped | 0 | 0 |
| rows | 394 | 394 |
