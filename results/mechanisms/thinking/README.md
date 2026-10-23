# Mechanism 4 of 4: does the reasoning text actually weigh/relate evidence, or just list it?

Question: in sessions where the model has genuinely multiple pieces of evidence available
(news headlines + price/technical tools), does its reasoning TEXT ever explicitly assess
how much a piece of information matters (WEIGHING), or explicitly relate two pieces of
evidence to each other -- confirms, contradicts, already reflects, is redundant with
(RELATIONSHIP) -- or does it just list tool outputs independently and jump to a number?

This is **not** about whether the final numeric answer matches a number computed earlier
in the trace (a different, already-documented finding). It is only about whether the
reasoning text itself contains weighing/relating language.

All numbers below are reproducible from `data.json`. Full code: `src/finagent/mechanisms/thinking.py`
(prose and hand-check constants in `thinking_text.py`), run with
`finagent mech-thinking`, which rewrites this folder's `data.json` byte for byte
(see "Reproducing this" below). The original analysis ran in an environment where
**scipy and statsmodels were NOT installed** (checked with `import` before
starting) -- all statistics are closed-form (Wilson CI, pooled two-proportion z-test, OLS
slope/SE) using only `math`.

## Corpora and method

- `data/mechanisms/sessions/newsagent/<TICKER>_<date>/{FULL,NO_NEWS}_<k>.json.gz`
  (Qwen3.5-9B) and `data/mechanisms/sessions/q3news_s1/.../{FULL,NO_NEWS}_<k>.json.gz`
  (Qwen3-8B, thinking on) -- only the plain `FULL_<k>`/`NO_NEWS_<k>` files (k=0..3), 1000
  FULL + 1000 NO_NEWS sessions per corpus = **4000 sessions total**. `FULL_T06_*`
  (a temperature-variant arm, 500 files/corpus) exists but is out of scope here.
- Per session, "full reasoning text" = every `trace[i]['reasoning']` string (the per-turn
  chain-of-thought, in trace order) **plus** the final `submit_decision` tool call's own
  `reasoning` argument, concatenated. The submit_decision reasoning is included because it
  is also model-generated justification text, and for terse sessions it is sometimes the
  only place weighing/relating language appears.
- Distinct tools called = count of distinct tool names in `tool` trace entries, excluding
  `submit_decision` itself.
- News-present-in-prompt = the day's `user` prompt's `COMPANY NEWS` block contains at
  least one `- [timestamp]` bullet (not just `(none)`).

## Pattern sets (exact, as used)

**WEIGHING** (assesses how much ONE piece of information matters): `more important`,
`less important`, `most important`, `doesn't change`, `does not change`, `won't change`,
`wouldn't change`, `already reflect(s)`, `already priced (in)`, `not much new`,
`nothing new`, `outweigh(s/ed)`, `largely`, `marginal(ly)`, `doesn't/does not add much`,
`carr(y/ies) more/less weight`, `weigh(s) more/less (heavily)`, `more/less weight than`,
`bigger/biggest factor`, `key/main/primary driver`, `overshadow(s/ed)`, `negligible`,
`material`, `immaterial`, `material factor`, `dominant factor`, `limited/minimal/
significant/substantial impact`, `takes/take precedence`, `tips/tip the balance`,
`secondary concern/factor`, `primary concern`, `weigh against/in favor`, `more/less
credible/reliable`, `stronger/weaker signal`, `carries weight`, `bigger concern`, `more/
less telling`, `matters more/less`, `the bigger risk/driver`, `significant`, `minor`.
(Full list with no truncation: see `data.json -> patterns.weighing_phrases`, 74 phrases -- the 60 figure in an earlier draft of this paragraph undercounted; the data.json list is authoritative and is what every reported number was computed from.)

**RELATIONSHIP** (explicitly relates two pieces of evidence to EACH OTHER): `consistent
with`, `in line with`, `confirm(s/ed/ing)`, `corroborat(es/ing/e)`, `contradict(s/ing)`,
`conflicts/conflicting with`, `contrary to`, `on the other hand`, `however(,) the`,
`despite the`, `while the`, `align(s/ed) with`, `echo(es/ing)`, `reinforce(s/ing/the)`,
`support(s) the`, `back(s/ed by) up`, `mirror(s/ing)`, `at odds (with)`, `inconsistent
with`, `diverg(es/ing) from`, `in tension with`, `offset(s/ting)`, `counterbalance(s/ing)`,
`reflects the`, `mixed signals/picture`, `jibes with`, `match(es/ing) the`, `in contrast
to`, `unlike the`, `together/combined/paired with`, `whereas the`, `even though the`,
`notwithstanding the`, `adds to the case`, `builds on the`, `undercut(s/ting)`,
`undermine(s/ing)`, `lines up with`, `squares with`. Plus one regex for a variable-length
construction: `\bboth\b[^.?!]{0,80}\b(?:suggest|suggests|indicate|indicates|point to|
points to|confirm|confirms|support|supports)\b`.
(Full list: `data.json -> patterns.relationship_phrases`, 72 phrases + 1 regex -- corrected 2026-10-23; also removed one inert duplicate-typo entry, 'while the the', which matched no real text and changed no count.)

Matching: case-insensitive, **word-boundary wrapped** (`\b<phrase>\b`) literal substring
search over the full concatenated text. Word-boundary wrapping was added as a bug fix
after the first pass, before any rate was finalized, because naive substring matching
produced real false hits: `minor` matched inside the word `Minority` (a headline about a
"Minority Stake"), and `however, the` matched the `the`-prefix of `there's` in "However,
there's also...". All reported numbers use the fixed matcher.

**This is approximate text matching** (same spirit as the project's existing
`keyword_polarity` precedent) -- it is not a validated classifier. See the hand-check
below for how much to trust it.

## Hand-check precision (20 positive + 20 negative, read by hand)

**WEIGHING matches** (16 of the 20 positive-sample sessions had a weighing match shown):
**12/16 judged genuine (75%, 95% Wilson CI [50.5%, 89.8%] -- a small sample, read this as "roughly three in four", not a precise figure)** -- the matched word really was assessing how much a piece
of external evidence (a price move, a news item, an indicator reading) matters. **4/16
(25%) were false positives**: the matched word ("significant"/"minor") was describing the
trader's own **position size or trade size**, not a piece of information -- e.g.
"maintaining a significant presence in the stock", "a minor tactical adjustment". The
keyword cannot tell these apart; `significant` alone drives 2,702/4,000 (68%) of all raw
weighing hits corpus-wide, so this confound matters a lot for the raw rate.

**RELATIONSHIP matches** (17 of the 20 positive-sample sessions had a relationship match
shown): under the task's **strict** definition (two evidence items explicitly related to
each other), only **4/17 judged genuine (23.5%, 95% Wilson CI [9.6%, 47.3%] -- a small sample, read this as "roughly one in four, plausibly anywhere from one in ten to one in two", not a precise figure)**. The dominant false-positive pattern,
accounting for essentially all of the other 13, was `aligns with`/`align with`/`aligned
with` used as "**my decision** aligns with signal X" (one evidence item justifying one
action -- not two evidence items related to each other), or a bare arithmetic self-check
("14 shares, which matches the target 68% exposure"). Under a looser reading that also
credits "decision stated as consistent with the evidence" (closer to the task's own
listed example "in line with"), roughly 8-9/17 (~50%) would count. Because `aligns with` + `align with` + `aligned with` together touch 1,625 distinct
sessions -- 45.0% of the 3,608 sessions with a raw relationship marker, 40.6% of all 4,000
(the union of the three phrases, not the
naive sum of their 1,833 raw hits, which double-counts sessions matching more than one
phrase; corrected 2026-10-23) -- **the raw 90.2% relationship rate should not be read as
"90% of sessions show real inter-evidence reasoning."** We report three tiers throughout:
- **raw**: full pattern list as specified.
- **strict**: excludes the two weakest, most generic phrases (`significant`, `minor` for
  weighing; `however, the`/`however the`/`while the`/`despite the` for relationship --
  these are common transition/intensifier words with low signal).
- **strict2** (relationship only): also excludes the `aligns with` family.

Negative sample (20 sessions flagged `has_neither`, i.e. truly zero keyword hits): read
in full. 19/20 looked like genuine pure-listing (independent bullets for trend/RSI/MACD/
volatility/news, then a decision that re-cites the same bullets without comparing them).
**One counter-example found**: `JPM_2026-09-17/FULL_3` says "Given the news about Iran
war oil forecast being dropped (which could be negative for earnings) but also the
housing commitment being positive, the sentiment is neutral overall" -- this *is* a tacit
weighing-and-netting of two news items, but uses no listed keyword. So the raw 3.3%
"neither" rate is a slight **over-estimate** of true pure listing (misses unworded
netting-out language); conversely the 26.1% strict-neither rate is an **under-estimate**
in the other direction (many of its "has a marker" sessions only have the weak phrases).
True pure-listing rate is bounded in roughly [3%, 26%] and this method cannot pin it down
further.

## Headline rates (n=4000 sessions; Wilson 95% CIs in `data.json`)

| | raw | strict | strict2 (rel. only) |
|---|---|---|---|
| >=1 weighing marker | 70.4% | 8.2% | -- |
| >=1 relationship marker | 90.2% | 72.1% | 57.4% |
| neither (pure listing) | 3.3% | 26.1% | -- |

By arm (FULL = news+tools, NO_NEWS = tools only):

| | FULL (n=2000) | NO_NEWS (n=2000) | diff | z | p |
|---|---|---|---|---|---|
| relationship, raw | 92.7% | 87.7% | +5.0pp | 5.32 | <0.0001 |
| relationship, strict2 | 63.2% | 51.7% | +11.5pp | 7.32 | <0.0001 |
| weighing, raw | 71.2% | 69.7% | +1.5pp | 1.04 | 0.30 (n.s.) |
| weighing, strict | 10.7% | 5.7% | +5.1pp | 5.83 | <0.0001 |

**FULL arm reliably shows more relationship AND more weighing language than NO_NEWS once
the noisy generic phrases are stripped out** -- the raw weighing gap looks flat (masked by
"significant" swamping both arms equally), but the strict version shows a real, highly
significant gap. This is consistent with the news arm giving the model a genuinely
separate evidence type (headlines) to weigh against/relate to the price-tool readings.

By number of distinct tools called (bucketed):

| tools | n | relationship, raw | relationship, strict2 |
|---|---|---|---|
| 0-1 | 1184 | 96.1% | 40.6% |
| 2 | 128 | 99.2% | 57.0% |
| 3-4 | 525 | 99.6% | 67.6% |
| 5-6 | 403 | 90.1% | 73.5% (peak) |
| 7+ | 1760 | 82.8% | 62.1% |

The raw-rate OLS trend is *negative* (slope -0.017/tool, t=-13.2) -- but this is an
artifact of the generic `however, the` phrase being common even in short sessions. The
**strict2 OLS trend is positive and highly significant** (slope +0.024/tool, t=11.0):
genuine relationship language rises with more distinct tools called, as the task
hypothesized -- but the real shape (see table) is **non-monotonic**: it rises sharply
through ~5-6 tools, then drops at 7+ tools. We do not have a confirmed explanation for the
7+ drop-off (candidates: turn/token-budget pressure in the longest sessions crowding out
synthesis, or boilerplate/habituation in very long sessions) -- flagged as an open
question, not resolved here.

## Check 4: FULL-arm sessions using both news and get_volatility_stats -- do they connect?

Eligible population: FULL-arm session where news is present in the prompt, the word
"news"/"headline" appears somewhere in the reasoning, AND `get_volatility_stats` was
called. **n = 916**. "Connects" = at least one single sentence contains a news-term, a
volatility-term (`volatil*`), AND a weighing/relationship marker, all together.

**Exact "sentence" definition (needed to reproduce the numbers below byte for byte, added
after independent verification found the first wording ambiguous):** reasoning text is
often bullet-point style with no terminal periods, so period-only splitting under-segments
it. The algorithm is: (1) split the full reasoning text on newlines first; (2) split each
resulting line further on `. ! ?` followed by whitespace; (3) drop empty fragments. The
surviving ordered fragments are the "sentence" units. "2-sentence window" below means an
ADJACENT PAIR of consecutive fragments (i, i+1), scanned over every such pair in the
session -- not a 3-fragment window centred on a match. See `data.json ->
check4_news_volatility_connection.sentence_splitting_algorithm` for the same text.

- **Same-sentence rate: 26/916 = 2.84%** (95% CI [1.9%, 4.1%]) -- the conservative,
  primary estimate.
- **2-sentence-window sensitivity: 191/916 = 20.9%** -- relaxing to "co-occur within 2
  consecutive sentences" picks up ~7x more cases, but many of those are just two adjacent
  bullet-list items (news bullet, then a separate volatility bullet) without an actual
  connecting clause -- on reading, closer to "mentioned both, never related" than to
  "related". Report as a range: the true explicit-connection rate is somewhere in
  [2.8%, 20.9%], almost certainly closer to the low end.
- Example of a genuine same-sentence hit: *"While the news-driven volatility is evident,
  the trend and RSI indicators point to potential stabilization."* (`CB_2026-03-11/FULL_0`)
- Example of a near-miss (relates news to "technical signals" broadly, not specifically
  to the word "volatility", so not counted): *"I'll cross-reference this news with
  current technical signals to identify any emerging opportunities or risks."*
  (`GM_2026-08-21/FULL_3`)

**Conclusion for check 4: explicit, literal connecting of a news headline to the
get_volatility_stats reading is rare** (under 3% on the strict reading, under 21% even on
a generous one) among the 916 sessions where both were genuinely available and used.

## Example quotes (all verbatim, see `data.json -> examples` for file paths + full context)

Pure listing (3+ distinct tools, zero weighing/relationship markers in the whole session):

> **Technical Analysis:**\n1. **Trend Signal:** Neutral ... 2. **Mean Reversion:** Neutral
> ... 3. **RSI:** 43.7 - neutral ... 4. **MACD:** ... bearish crossover ... 5. **Support/
> Resistance:** ... 6. **Price Stats:** ... 7. **Volatility:** ... 8. **News Sentiment:**
> All neutral (0.0 average sentiment over past 7 days).
>
> *(then, verbatim)* Position at 99.8% exposure, neutral technical signals across trend,
> mean reversion, RSI, and MACD. Stock at support level (~348.69) with tight consolidation
> range. Volatility regime low, no directional bias. Maintaining current exposure
> appropriate.
> -- `data/mechanisms/sessions/newsagent/JPM_2026-09-17/FULL_3.json.gz` (9 tools, FULL arm, news present)

Genuine weighing + relating (best real example found, matched via "outweigh"/"combined
with"/"despite the"):

> I'll hold flat (0 shares) because the trend is clearly bearish, volatility is high, and
> there's no strong reversal signal yet despite the somewhat oversold RSI. The negative
> news (Mizuho downgrade, pullback) combined with bearish technicals outweigh the positive
> fundamental news at this moment.
> -- `data/mechanisms/sessions/newsagent/ACN_2026-03-24/FULL_3.json.gz`

3 more genuine examples (matched via "weighing...against", "main driver", "contradict"
respectively) are in `data.json -> examples.genuine_weighing_or_relating`, including one
from the q3news/Qwen3-8B cross-model corpus.

## Open questions (explicitly not resolved here)

1. Why does genuine (strict2) relationship language peak at 5-6 distinct tools and then
   fall at 7+? Not established -- flagged, not forced.
2. The true pure-listing rate is bounded in [3%, 26%] by this method, not pinned to a
   single number -- the keyword approach is too coarse to do better without a much more
   expensive manual read of all 4000 sessions.
3. q3news_20261012_S1 has **zero** sessions meeting "3+ distinct tools AND zero markers"
   (18 of its 19 raw-neither sessions called 0 tools; 1 called 2) -- whether this reflects
   a real model difference (Qwen3-8B-thinking almost always emits *some* weak marker once
   it explores beyond 2 tools) or is itself a keyword-list artifact is not established;
   both are plausible and we do not pick one without more evidence.

## Reproducing this

`finagent mech-thinking` (about 20 seconds, CPU only, no model calls) rewrites
`results/mechanisms/thinking/data.json`; running it twice gives byte-identical files, and
`tests/test_mechanisms_thinking.py` checks that it reproduces the shipped file exactly. The code
is self-contained Python using only `gzip`, `json`, `re`, `math` (no scipy/
statsmodels). Steps: (1) walk both
corpora's session directories, keep only `FULL_<k>.json.gz`/`NO_NEWS_<k>.json.gz`; (2)
build "full reasoning text" per session as defined above; (3) apply the word-boundary
phrase lists + the one regex; (4) compute proportions, Wilson CIs, and pooled
two-proportion z-tests in closed form; (5) OLS of a 0/1 flag on tool count via the
covariance/variance closed form, with homoskedastic SE. The exact pattern lists are in
`data.json -> patterns` so the whole pipeline is auditable without re-reading this file.

## Port notes (finance1)

Ported from the workspace write-up `results/mech4_20261023/thinking/` (data.json + README.md).
Every numeric field of `data.json` (293 of them) is identical to the source. Only these text
fields differ, each for a stated reason:

- Path fields (`corpora.*.path`, `examples.*.file`) point at this repository's copies under
  `data/mechanisms/sessions/` (byte-identical to the source session files).
- `precision_handcheck.relationship_judgment.dominant_false_positive_pattern`: the source
  said the "aligns with" union is 1,624 sessions = 45.0% "of the 4,000-session corpus". With
  this analysis's own text unit (the one every other count uses, e.g. 1,388 sessions for
  `aligns with`) the union is 1,625; 1,624 came from a check that built the text slightly
  differently (it found 1,387 for `aligns with`). 45.0% is that union's share of the 3,608
  relationship-flagged sessions; of all 4,000 it is 40.6%. The sentence now states both.
- `examples.pure_listing_3plus_tools_zero_markers[1].then_jumps_to` (NEE_2026-09-11/NO_NEWS_0):
  the source dropped one word; the session's text reads "Position remains at 99.9% exposure.
  ...". The code checks that every example excerpt is literally in its session's reasoning text.
- This README: the relationship list has 72 phrases (+1 regex), as `data.json` shows; the
  source README said 73 (the count before the inert 'while the the' entry was removed).
