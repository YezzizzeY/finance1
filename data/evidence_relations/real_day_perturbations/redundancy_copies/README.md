# redundancy_copies

One day-arm per (day, n_copies), n_copies in {0, 1, 2, 4}. The base prompt is the day pool's own ORIG harness
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

Every added line is checked, for every one of the 788 rows, to be a pure function of X alone
(`redundancy.verify_pure_function`; `verified_pure_function_of_source` is true on every row — the build raises if
any row fails this). Because the added lines carry zero information beyond X, a rational forecaster's output
must be identical across n_copies in {0, 1, 2, 4}. This is a derivation, not an estimate, and it holds by
construction rather than by assumption about the model.

## Counts

- days: 197
- rows (days x 4 arms): 788
- rows failing the pure-function check: 0 (the build aborts otherwise)

## Source-vs-port

| | source (1_overreaction, 6-ticker-pilot day pool) | this port (finance1, 96-ticker data/pit_cache) |
|---|---:|---:|
| days | 197 | 197 |
| rows | 788 | 788 |
