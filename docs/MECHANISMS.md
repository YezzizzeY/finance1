# Mechanisms: four checks on saved agent sessions

Earlier work in this project found that an LLM trading agent over-reacts: it revises its forecasts and its position
far more than a rational model would. The four analyses here ask *why*, using sessions that were already run and saved.
They are CPU only, make no model calls and are not part of the five-model presentation pilot.

| | Question | Data | Answer in one line |
|---|---|---|---|
| 1. Salience | Does the big annualised volatility number on screen pull the 5-day volatility forecast? | 1,445 Qwen3.5-9B sessions (+ 294 Qwen3-8B as a cross-check) | Not on average; but about 2% of sessions copy the annual number outright, and those forecasts are far off. |
| 2. Proximity | Does a number get more weight just because its tool was called last, right before the decision? | 754 Qwen3.5-9B sessions, 420 of them on 128 days with both orders | No effect found, and the test had enough data to see one. |
| 3. Position adjustment | Do day-to-day position changes follow a rational sizing rule? | 692 day-to-day changes of 80 multi-day trajectories (January 2026) | No: the agent's changes are about 6.7 times as spread out as the rule's, and not aligned with them. |
| 4. Thinking | Does the reasoning text weigh evidence and relate pieces of evidence, or just list tool outputs? | 4,000 sessions, two models | Relating language is more common when news is in the prompt, but under a strict reading only about one match in four is real relating. |

Code: `src/finagent/mechanisms/`. Inputs: [`data/mechanisms/`](../data/mechanisms/README.md) (7,011 files, each hashed in
its manifest). Outputs: `results/mechanisms/<analysis>/data.json`, with a README.md per analysis that gives every
number, table and quote; a page in Chinese that shows all four (`results/mechanisms/page/mechanisms.html`).

## The data

- **`data/mechanisms/sessions/newsagent/`**: Qwen3.5-9B tool-agent sessions on 250 real ticker-days. Each day was run in
  the FULL arm (company news in the prompt, all tools available; runs k = 0..3) and the NO_NEWS arm (no news; k = 0..3),
  plus two FULL runs at temperature 0.6 (`FULL_T06_*`, not used here). A session file holds the whole conversation:
  the prompt, every reasoning turn, every tool call with its result, and the submitted decision (5-day expected return,
  5-day volatility, position).
- **`data/mechanisms/sessions/q3news_s1/`**: 250 ticker-days, 125 of them shared with `newsagent/`, with the same arms, run with Qwen3-8B (thinking on).
- **`data/mechanisms/salience/grounding_A_main/`**: 2,000 Qwen3-8B sessions in which the price readings are written into
  the prompt instead of being fetched by a tool.
- **Rational benchmark** (`events_all.parquet`, `nonevent_days.parquet`, `rule.json`): for each (stock, day), the
  rational model's expected 5-day return m, its 5-day standard deviation sigma = exp(lsig), and the day's surprise
  u = (realised 5-day return − m) / sigma.
- **Trajectories** (`data/mechanisms/position_adjustment/`): BASE-policy Qwen3.5-9B agents that trade one stock for
  12-15 consecutive days, carrying their book and memory from day to day, in five market windows.

## 1. Salience: does the conspicuous annual number get copied?

`get_volatility_stats` reports volatility on an annual scale (for example 30%). The agent has to submit a 5-day
volatility, which is about 7 times smaller (30% × √(5/252) ≈ 4.2%). Does the size of the annual number push the
forecast up, beyond what the rational 5-day sigma justifies?

**Method.** Sessions that call `get_volatility_stats` and submit a valid decision: 694 FULL and 751 NO_NEWS (Qwen3.5-9B),
155 and 139 (Qwen3-8B). (1) Least-squares regression of the submitted 5-day volatility on the rational sigma, then
with the annual number added. (2) Split off the sessions whose forecast is within 15% of the annual number ("looks
copied") and compare forecast errors, |ln(forecast / realised 5-day volatility)|, with the realised volatility computed
from the price panel. (3) Compare FULL with NO_NEWS.

**Results.**
- No smooth pull: once the rational sigma is in the regression, the annual number adds nothing (coefficient −0.007,
  t = −0.36; the explained variance rises by 0.017 percentage points). The same holds in NO_NEWS and in the Qwen3-8B
  cross-check.
- A rare, all-or-nothing failure: 27 of 1,445 sessions (1.9%) submit (almost) the annual number itself. Their mean
  error is 1.73 against 0.62 for everyone else (about 5.6 times off against 1.9 times; difference 1.11, SE 0.13,
  t = 8.8). Each example quote is checked word for word against its session file.
- News does not change it: the copy rate is 2.2% with news and 1.6% without (z = 0.79, p ≈ 0.43).

**Caveats.** The copy group is small (12 to 27 sessions), so its rate is noisy and cannot be split further; the gap in
accuracy is solid. "No difference between FULL and NO_NEWS" is a low-powered result, not a confirmed equality. The
grounding corpus cannot test this at all: no session there calls `get_volatility_stats` (0 of 2,000), so it is reported
as skipped, not replaced by a weaker proxy. Standard errors treat the up to 4 runs of a day as independent, so they are
a lower bound.

## 2. Proximity: does calling a tool last give its number more weight?

**Method.** A natural experiment inside the FULL sessions. Every run of the same day sees exactly the same annual
volatility number (checked on all 250 days), but the agent itself decides whether `get_volatility_stats` is its last
call before `submit_decision`. Of 1,000 FULL sessions, 754 are usable (one volatility call, one final decision); 128 days
have runs in both orders (420 sessions). Tests: the slope of forecast on the annual number in each group, a day fixed
effects test of the level, a paired per-day test, the ratio forecast / annual number, and the slope test on all 754.

**Results.** No effect of position on any of them: slope difference −0.011 (SE 0.021, p = 0.59); day fixed effects
coefficient −0.12 percentage points (SE 0.36, p = 0.73); paired days p = 0.55; ratio 0.224 when last against 0.223
when not; the full pool gives p = 0.67. With 420 matched sessions this is a well-powered null, not a missing test.

**Caveats.** Sessions that call the volatility tool last are shorter (7.05 against 8.32 tool calls, p < 0.001), so a
future positive finding would have to control for session length. The planned second test (does the answer follow the
later of two volatility tools?) cannot be run: `get_volatility_stats` and `get_risk_budget` compute the same 20-day
number with the same formula and gave identical values in all 32 sessions that call both. The day fixed effects
standard error used n − 2 degrees of freedom instead of about n − 129; with the right number the result is still far
from significant (noted in `data.json`).

## 3. Position adjustment: do position changes follow a rational rule?

**Method.** For each day of a trajectory, a Kelly-style rational target exposure, clip(k × m / sigma², 0, 100), with
m and sigma from the rational benchmark and k set so that the rule's exposures have the same spread as the agent's. Then
the day-to-day change of the agent's exposure against the change of the rational target: regression slope (with
standard errors robust to clustering by stock and by date), rank correlation, and the ratio of their standard
deviations; overall, on quiet days (|u| < 1) and on eventful days (|u| ≥ 2).

**Results.** The rational benchmark covers only one of the five windows (test_calm, January 2026), so everything rests
on its 692 day-to-day changes (26 stocks, 14 dates). The agent's changes have **6.7 times** the standard deviation of
the rule's (14.9 against 2.2 percentage points). They are not aligned with them either: slope +0.22 (cluster SE about
0.29, not different from 0), rank correlation −0.16. Even the same-day levels barely agree (Pearson 0.00, Spearman 0.24).

**Caveats.** The eventful subset is too small to test the quiet/eventful asymmetry found for volatility forecasts:
16 changes, 5 stocks, 6 dates, with a standard error about three times the slope (0.92 against 0.32, clustered by date), so that part is inconclusive, not
negative. The ratio scales with the choice of k: 3.4 at 2k and 10.8 at k/2 (the rank correlation, −0.15 to −0.16,
does not depend on k). The 6.7 is a different quantity from the project's earlier 71-times figure for volatility
revisions and cannot be compared with it directly.

## 4. Thinking: weighing and relating, or listing?

**Method.** The full reasoning text of 4,000 sessions (1,000 FULL and 1,000 NO_NEWS per model) is scanned for 74
*weighing* phrases ("outweighs", "more important", ...) and 72 *relationship* phrases plus one pattern ("confirms",
"contradicts", "already priced in", "aligns with", ...), whole words only. Three tiers: raw; strict (without the most
generic words such as "significant" and "however, the"); strict2 (also without the "aligns with" family). A hand check
read 20 flagged and 20 unflagged sessions. A separate check asks whether sessions that use both news and the volatility
tool ever connect the two in one sentence.

**Results.**
- With news in the prompt there is more of both: relationship language (strict2) 63.2% with news against 51.7% without
  (+11.5 points, z = 7.3); weighing (strict) 10.7% against 5.7% (z = 5.8).
- But most raw matches are not real relating. Raw, 90.2% of sessions have a relationship marker; read by hand, only
  4 of 17 matches (23.5%, Wilson 95% interval 9.6% to 47.3%) relate two pieces of evidence to each other. Most are "my
  decision aligns with signal X". The "aligns with" family alone touches 1,625 sessions, 45.0% of the 3,608 with a
  marker. Weighing matches hold up better: 12 of 16 (75%, 50.5% to 89.8%).
- News and volatility are almost never connected: 26 of 916 eligible sessions (2.8%) do it in one sentence, 20.9% if
  two adjacent sentences count.
- Genuine relating (strict2) rises with the number of tools called, from 40.6% (0-1 tools) to 73.5% (5-6 tools), then
  falls to 62.1% (7 or more); the fall is not explained.

**Caveats.** This is keyword matching, not a validated classifier. The hand-check samples are small (16 and 17 cases),
so their rates are rough. The share of pure listing can only be bounded, between about 3% and 26%. The text can differ
from what actually drove the decision, so the text measures are a supplement to behavioural tests, not a substitute.

## The page and the theory document

- **`results/mechanisms/page/mechanisms.html`** (`finagent mech-page`): the four results in Chinese, with charts,
  tables and real excerpts. It is byte-identical to the research workspace's page. Its text also quotes 72 numbers that
  were typed by hand; the build checks each against the four `data.json` files and stops if one disagrees.
- **`docs/good_thinking/good_thinking_20261023.docx`** and **[`GOOD_THINKING.md`](GOOD_THINKING.md)**
  (`finagent mech-theory-doc`, in Chinese): what "good thinking" should mean, from the literature. Each piece of
  information should move the judgment only by its weight given what is already known (log likelihood ratio), and
  relations (repeated, already priced in, stale, redundant, synergistic, conflicting) are differences between that
  conditional weight and the weight alone. It lists measurement methods and a 44-entry literature appendix, each
  entry re-checked by a second reader (38 confirmed, 5 details corrected, 1 claim overturned), built from
  `docs/good_thinking/good_thinking_theory.json`.

## Rerun and check

```sh
make mechanisms                # all four analyses, the page and the theory document (CPU, about 30 s)
finagent mech-thinking --check # any one of them: rebuild, compare with the shipped file, exit 1 if different
finagent verify                # includes "mechanism data" (L0) and the six rebuild checks (L1)
```

Every output is deterministic: two runs, with different hash seeds, give byte-identical files. The .docx is a stored
(uncompressed) zip with fixed timestamps, because deflate output differs between zlib builds.

## Faithfulness to the research workspace

The four analyses were ported from the workspace scripts and re-run on byte-identical copies of the inputs. Every
numeric field of the workspace `data.json` files is reproduced exactly: 183 of 183 (salience), 132 of 132
(proximity), 348 of 348 (position adjustment), 293 of 293 (thinking). The other differences are in text (the prose
fields of `data.json`, the READMEs and the theory document), and four of them correct a number written in that text
(1,624 to 1,625, 73 to 72, 1988 to 2,000, 22 to 69):

- paths now name this repository's files;
- thinking (a text field of `data.json`): the sentence on the "aligns with" family said 1,624 sessions = 45.0% "of the
  4,000-session corpus". The analysis's own text gives 1,625 (the checker that produced 1,624 built the text slightly
  differently and found 1,387 instead of 1,388 for "aligns with"), and 45.0% is the share of the 3,608 marked sessions
  (40.6% of all 4,000); the sentence now says both;
- thinking: one of the 15 excerpts had dropped a word ("Position remains at 99.9% exposure"); it now matches its
  session, and the build checks every excerpt;
- thinking README: 72 relationship phrases (+1 pattern), as in both `data.json` files, not 73;
- salience README: the q3news cross-check corpus was given as 1988 files; the scan reads 2,000 of them (294 usable;
  the folder's other 500 are `FULL_T06`, which the scan skips);
- theory document: two table cells (sections 3 and 6) called the redundancy matrix "22 个字段的冗余矩阵". The
  matrix (`data/evidence_relations/tool_redundancy/pearson_matrix.csv`) has 69 fields; 22 is the size of its largest
  near-duplicate cluster. Both cells now say "69 个字段的冗余矩阵", so `word/document.xml` of the .docx differs from
  the workspace's in that phrase (its other five parts are byte-identical). `docs/good_thinking/good_thinking_theory.json`
  stays byte-identical to the workspace copy; its `measurable_test_cn` fields, which the document does not print,
  still say 22.
