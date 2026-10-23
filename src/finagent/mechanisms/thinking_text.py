"""Prose and hand-check constants for finagent.mechanisms.thinking (results/mechanisms/thinking/data.json).

Everything here is either (a) explanatory text carried over verbatim from the verified source write-up, (b) a
human hand-check judgment recorded at the time (a person read the sampled sessions; those counts are data, not
something code can recompute), or (c) a verbatim example excerpt from a real session (thinking.build() checks
that every excerpt is literally present in that session's reasoning text). Sentences that quote a number the code
computes are rendered from the computed value (see the render_* functions) instead of being typed in.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

TASK = ("mech4 (4 of 4): does FULL/NO_NEWS session reasoning text actually weigh evidence and reason about "
        "relationships between pieces of evidence, or just list tool outputs and jump to a number?")

NEWSAGENT_FILES_USED = ("plain FULL_<k>.json.gz and NO_NEWS_<k>.json.gz only (k=0..3); FULL_T06_* temperature-variant "
                        "files excluded as out of scope for this task.")
Q3_FILES_USED = "same file-selection rule as above."

# ------------------------------------------------------------------------------------------------ patterns
MATCHING_METHOD = (
    "Case-insensitive, word-boundary-wrapped literal substring match (python re, \\b<escaped phrase>\\b) applied to "
    "the full concatenated reasoning text of the session, plus the one named regex for the 'both X and Y "
    "suggest/confirm/support' construction. Word-boundary wrapping was added after an initial pass without it "
    "produced false hits (e.g. 'minor' matching inside 'Minority', 'however, the' matching the 'the' prefix of "
    "\"there's\"); all reported numbers use the word-boundary-fixed version.")

TEXT_UNIT_ANALYZED = (
    "Per session: all trace[i]['reasoning'] strings (the per-turn chain-of-thought text, type=='turn' entries) "
    "concatenated in trace order, PLUS the final submit_decision tool call's own 'reasoning' argument string "
    "appended at the end (joined with blank lines). This is broader than 'turn reasoning only' because the "
    "submit_decision reasoning argument is also model-generated justification text and can itself contain "
    "weighing/relating language (and sometimes is the ONLY place it appears, e.g. terse sessions). This choice is "
    "documented so the corpus-level rates are reproducible.")

EDIT_LOG = [
    "2026-10-23: removed the duplicate-typo phrase 'while the the' (a literal typo of 'while the X the Y' with no "
    "wildcard, so it never matched any real text; found during independent verification; removing it does not "
    "change any reported count since it contributed zero matches)."]

# ------------------------------------------------------------------------------------------------ hand-check
# The hand-check is a one-pass human reading of a random sample (seed 20261023) of 20 marker-positive and 20
# marker-negative sessions. These counts are the reader's judgments as recorded at the time.
HC_WEIGHING_SHOWN = 16           # positive-sample sessions whose weighing match was judged
HC_WEIGHING_GENUINE = 12
HC_WEIGHING_FALSE_POSITIVE = 4
HC_RELATIONSHIP_SHOWN = 17       # positive-sample sessions whose relationship match was judged
HC_RELATIONSHIP_GENUINE_STRICT = 4
HC_RELATIONSHIP_FALSE_POSITIVE_STRICT = 13

HC_METHOD = (
    "Random sample (seed=20261023) of 20 sessions flagged positive (has_weighing or has_relationship true, drawn "
    "from the pooled 4000-session corpus) and 20 sessions flagged negative (has_neither true), read by the analyst "
    "with surrounding context (first occurrence, +/-160 chars) for the positive sample and the full reasoning text "
    "for the negative sample. This is approximate text matching, same spirit as the project's existing "
    "keyword_polarity precedent -- it is NOT a validated classifier, and the numbers below are a rough, one-pass "
    "human judgment call, not an inter-rater-reliability study.")

HC_BUG = (
    "Initial substring matching (no word boundaries) produced literal false hits: 'minor' matched inside "
    "'Minority' (a news headline about a 'Minority Stake'), and 'however, the' matched the 'the' that begins "
    "\"there's\" in 'However, there's also...'. Fixed by wrapping every literal phrase in \\b...\\b before the "
    "hand-check reported below was finalized.")

HCW_JUDGED_GENUINE_QUOTE = (
    "A WEIGHING match was judged genuine if the matched phrase assesses how much a piece of EXTERNAL "
    "INFORMATION/evidence (price action, a news item, a technical signal, the overall picture) matters -- per the "
    "task's own definition. It was judged NOT genuine (false positive) when the matched word instead described the "
    "magnitude of the trader's OWN position size or the size of the contemplated trade/action (e.g. 'significant "
    "exposure', 'minor tactical adjustment', 'maintaining a significant presence') -- that is a real, specific, "
    "recurring confusion the keyword list cannot resolve on its own.")

HCR_JUDGED_GENUINE_STRICT_QUOTE_HEAD = (
    "Under the TASK'S STRICT definition (explicitly relates TWO PIECES OF EVIDENCE TO EACH OTHER -- e.g. one signal "
    "confirms/contradicts/is-redundant-with another), only sessions where two distinct evidence items (two "
    "technical signals, or a news item and a technical signal, etc.) were explicitly tied together were counted "
    "genuine.")


def _pct(x: float) -> str:
    """75.0 -> '75', 23.5 -> '23.5' (how the source text writes a percentage)."""
    return f"{x:g}"


def _r(x: float, digits: int = 1) -> str:
    """x rounded half-up on its decimal digits, as the source text rounds a stored value for display
    (62.05 -> '62.1', 73.45 -> '73.5'; Python's round() gives 62.0 for the binary double nearest 62.05)."""
    q = Decimal(1).scaleb(-digits)
    return str(Decimal(repr(x)).quantize(q, rounding=ROUND_HALF_UP))


def _int(n: int) -> str:
    return f"{n:,}"


def render_weighing_note(n_significant: int, n_sessions: int, wilson: list[float]) -> str:
    fp, shown, ok = HC_WEIGHING_FALSE_POSITIVE, HC_WEIGHING_SHOWN, HC_WEIGHING_GENUINE
    return (f"{fp} of {shown} ({_pct(round(100 * fp / shown, 1))}%) of matches were about position/trade size, not "
            f"about weighing a piece of evidence. 'significant' alone accounts for "
            f"~{_r(100 * n_significant / n_sessions, 0)}% of all raw weighing-flagged sessions corpus-wide "
            f"({n_significant}/{n_sessions}); it is also the single most ambiguous phrase for exactly this reason. "
            f"'minor'/'significant' are the only two phrases moved to a documented 'weak' subset for a stricter "
            f"sensitivity rate (see rates.weighing). 95% Wilson CI on {ok}/{shown}: [{wilson[0]}%, {wilson[1]}%] -- "
            f"the sample is small ({shown} cases); treat {_pct(round(100 * ok / shown, 1))}% as 'roughly three in "
            f"four', not a precise figure.")


def render_relationship_strict_quote(wilson: list[float]) -> str:
    ok, shown = HC_RELATIONSHIP_GENUINE_STRICT, HC_RELATIONSHIP_SHOWN
    return (f"{HCR_JUDGED_GENUINE_STRICT_QUOTE_HEAD} 95% Wilson CI on {ok}/{shown}: [{wilson[0]}%, {wilson[1]}%] -- "
            f"the sample is small ({shown} cases); treat {_pct(round(100 * ok / shown, 1))}% as 'roughly one in "
            f"four, could plausibly be anywhere from one in ten to one in two', not a precise figure.")


def render_dominant_false_positive(hits: dict[str, int], union: int, n_sessions: int, n_relationship: int) -> str:
    """hits: sessions per phrase for 'aligns with', 'align with', 'aligned with'; union: sessions with any of them.

    The percentage in the source sentence, 45.0, is union / sessions with a raw relationship marker (1,624/3,608);
    it was labelled 'of the 4,000-session corpus' there (1,624/4,000 is 40.6%). Both shares are written out here.
    """
    a, b, c = hits["aligns with"], hits["align with"], hits["aligned with"]
    return (f"'aligns with' / 'align with' / 'aligned with' ({_int(a)} + {_int(b)} + {_int(c)} raw hits on the three "
            f"separate phrases; a session can match more than one, so the DISTINCT-SESSION union is {_int(union)} "
            f"sessions = {_r(100 * union / n_relationship)}% of the {_int(n_relationship)} sessions with a raw "
            f"relationship marker ({_r(100 * union / n_sessions)}% of the {_int(n_sessions)}-session corpus), "
            f"not the naive sum of {_int(a + b + c)} -- corrected 2026-10-23 after independent verification) is "
            f"overwhelmingly used as 'my DECISION aligns with signal X' (one evidence item justifying one action), not "
            f"'evidence A relates to evidence B'. Of the {HC_RELATIONSHIP_SHOWN} sampled relationship-flagged "
            f"excerpts, essentially all of the {HC_RELATIONSHIP_FALSE_POSITIVE_STRICT} judged "
            f"false-positive-for-the-strict-definition were this pattern, or a bare arithmetic self-check ('14 shares, "
            f"which matches/confirms the target 68% exposure').")


def render_loose_note(pct_relationship: float, pct_relationship_strict2: float) -> str:
    return (f"Under a LOOSER reading that also credits a decision stated as consistent with/aligned with the available "
            f"evidence (closer to the task's literal inclusion of 'in line with' as an example phrase), roughly 8-9 of "
            f"the {HC_RELATIONSHIP_SHOWN} would count, i.e. ~50%. Given this spread "
            f"({_pct(round(100 * HC_RELATIONSHIP_GENUINE_STRICT / HC_RELATIONSHIP_SHOWN, 1))}% strict vs ~50% loose), "
            f"the raw relationship rate ({_r(pct_relationship)}% of sessions) should NOT be read as '90% of "
            f"sessions show real inter-evidence reasoning' -- it should be read as an upper bound inflated mostly by "
            f"decision-justification language. The strict2 rate ({_r(pct_relationship_strict2)}%, excluding both "
            f"the generic transition words AND the alignment phrases) is the more defensible headline number; see "
            f"rates.relationship.")


# ------------------------------------------------------------------------------------------------ rates / tests / trend
FIELD_MEANING = (
    "pct_X = % of sessions with >=1 match from the RAW/full pattern list. pct_X_strict excludes the 'weak' phrases "
    "documented in patterns.weighing_weak_subset_excluded_in_strict / relationship_weak_subset_excluded_in_strict. "
    "pct_relationship_strict2 additionally excludes the 'aligns with' family (see "
    "precision_handcheck.relationship_judgment). All _ci95 fields are Wilson 95% confidence intervals on the RAW "
    "proportion, computed in closed form (no scipy available in this environment; statsmodels also unavailable -- "
    "confirmed by import check before starting).")

SIG_METHOD = ("Two-proportion z-test, pooled SE, normal approximation p-value (math.erfc closed form, no scipy). "
              "diff_pct = pct(FULL) - pct(NO_NEWS).")


def render_sig_headline(rel_raw: dict, rel_s2: dict, w_raw: dict, w_strict: dict) -> str:
    return (f"FULL arm shows MORE relationship language than NO_NEWS at every strictness level (raw "
            f"{rel_raw['diff_pct']:+}pp, strict2 {rel_s2['diff_pct']:+}pp, both p<0.0001) and more weighing language "
            f"too once the noisy 'significant'/'minor' phrases are excluded (strict {w_strict['diff_pct']:+}pp, "
            f"p<0.0001; the raw weighing gap of {w_raw['diff_pct']:+}pp is NOT significant, "
            f"p={w_raw['p_two_sided']:.2f} -- the generic phrases mask the real signal here).")


OLS_RAW_NOTE = (
    "OLS of has_relationship(0/1) RAW flag on n_distinct_tools, closed-form, homoskedastic SE; descriptive trend not "
    "a causal claim. Confounded by the 'however, the' generic-transition phrase being common even in short, "
    "low-tool sessions -- see strict2 version below for a cleaner read.")

OLS_STRICT2_NOTE = (
    "Same OLS but on the stricter has_relationship_strict2 flag (excludes generic transition words AND the 'aligns "
    "with/align with/aligned with' decision-justification phrases). Linear fit is a poor description (true pattern "
    "is non-monotonic, see by_tool_bucket) but sign/magnitude still useful as a summary: still a rough "
    "rise-then-plateau, not a flat or falling line.")


def render_trend_headline(ols_raw: dict, ols_s2: dict, buckets: dict) -> str:
    b = {k: _r(v["pct_relationship_strict2"]) for k, v in buckets.items()}
    return (f"The RAW relationship rate falls with more distinct tools called (slope "
            f"{ols_raw['slope_per_extra_tool']}/tool, t={_r(ols_raw['slope_t_stat'])}) -- but this is an "
            f"artifact: short/low-tool sessions lean on the generic word 'however, the' a lot. Once that noise is "
            f"removed (strict2), the trend REVERSES and is positive and highly significant (slope "
            f"+{_r(ols_s2['slope_per_extra_tool'], 3)}/tool, t={_r(ols_s2['slope_t_stat'])}): genuine "
            f"relationship language is more common in sessions that called more distinct tools, consistent with the "
            f"task's hypothesis that more available signals creates more opportunity to relate them. The relationship "
            f"is not linear though -- see by_n_distinct_tools_bucket.pct_relationship_strict2: 0-1 tools={b['0-1']}%, "
            f"2 tools={b['2']}%, 3-4 tools={b['3-4']}%, 5-6 tools={b['5-6']}% (peak), 7+ tools={b['7+']}% (falls "
            f"back). So: rises sharply through ~5-6 tools, then drops off at the highest tool counts (possibly "
            f"turn/token-budget pressure in the longest sessions crowding out synthesis, or habituation/boilerplate in "
            f"very long sessions) -- this is a real, not-fully-explained non-monotonicity, reported as an open "
            f"question rather than smoothed over.")


# ------------------------------------------------------------------------------------------------ check 4
C4_DEFINITION = (
    "FULL-arm session where news is present in the day's prompt AND the word news/headline appears somewhere in the "
    "reasoning text AND get_volatility_stats was called; 'connects' = at least one sentence in the reasoning "
    "contains a news-term, a volatility-term, AND a weighing/relationship marker all together.")

C4_SPLIT = (
    "Reasoning text is frequently bullet-point style with no terminal periods, so period-only splitting "
    "under-segments it. Exact rule (added 2026-10-23 after independent verification found the original wording "
    "ambiguous -- reproducing the numbers below requires this precise algorithm, not a guess): (1) first split the "
    "full reasoning text on newline characters; (2) split each resulting line further on sentence-ending "
    "punctuation (. ! ?) followed by whitespace; (3) drop empty fragments; the ordered list of surviving fragments "
    "is the 'sentence' unit used everywhere in this check. 'Same sentence' = both a news-term and a volatility-term, "
    "plus a weighing/relationship marker, fall inside one such fragment. '2-sentence window' = an ADJACENT PAIR of "
    "consecutive fragments (fragment i and fragment i+1), not a 3-fragment window centred on a match -- scanned "
    "over every adjacent pair in the session.")

C4W_DEFINITION = (
    "Same eligibility, but 'connects' relaxed to: a news-term and a volatility-term co-occur within ANY 2 "
    "consecutive sentences (not just the same single sentence) together with a weighing/relationship marker "
    "somewhere in that 2-sentence window. Looser and noisier (picks up some cases where the two mentions are merely "
    "adjacent, not actually tied together), reported as a sensitivity bound, not a replacement for the primary "
    "same-sentence number.")


def render_c4w_interpretation(rate_same: float, n: int, rate_window: float) -> str:
    return (f"The true rate of explicit news<->volatility connection is somewhere between the conservative "
            f"same-sentence estimate ({rate_same}%, n={n}) and this looser window estimate ({rate_window}%) -- most of "
            f"the gap is sessions that discuss news and separately discuss volatility as two items in an adjacent "
            f"bullet list without an explicit connecting clause, which on reading is closer to 'mentioned both, not "
            f"related' than to 'related'. Treat {rate_same}% as the best single estimate of genuinely explicit "
            f"connection and {rate_window}% as a generous upper bound.")


# ------------------------------------------------------------------------------------------------ examples
def render_examples_note(n_neither_q3: int, q3_tool_counts: dict[int, int]) -> str:
    zero, two = q3_tool_counts.get(0, 0), q3_tool_counts.get(2, 0)
    return (f"All 4 pure-listing examples come from newsagent_20261011 (Qwen3.5-9B). q3news_20261012_S1 (Qwen3-8B, "
            f"thinking-on) has ZERO sessions meeting the '>=3 distinct tools AND zero weighing/relationship markers' "
            f"criterion ({zero} of its {n_neither_q3} raw-flagged 'neither' sessions called 0 tools, {two} called 2) "
            f"-- itself a finding: for that model, every session that explored more extensively (3+ tools) hit at "
            f"least one keyword marker (though per the hand-check, that does not mean every one was genuine relating; "
            f"see precision_handcheck).")


# Verbatim excerpts. `session` is (corpus key, ticker-day folder, file name); thinking.build() resolves it to the
# session file under data/mechanisms/sessions/ and checks that every excerpt is literally in its reasoning text.
PURE_LISTING = [
    {
        "label": "pure_listing_1",
        "session": ("newsagent_20261011", "MMM_2026-06-18", "FULL_3.json.gz"),
        "then_jumps_to": "Decision: Add to position to reach 100% exposure (599+647=1246 shares).",
        "verbatim_excerpt": (
            "**Technical Analysis:**\n- Trend signal: **BULLISH** (EMA 8: 158.5, EMA 21: 155.12, EMA 55: 152.24)\n"
            "- RSI: 69.3 (neutral, approaching overbought at 70)\n- MACD: Bullish (MACD: 3.081, Signal: 2.587, "
            "Histogram: 0.494) - bullish crossover but no fresh cross\n- Support/Resistance: Next resistance at "
            "163.01, support at 146.56, 148.4, 151.72\n\n**Volatility:**\n- Vol regime: LOW (-3.29 z-score vs 63-day)\n"
            "- ATR: "
            "2.75% of price\n- Volatility is compressed, suggesting potential for expansion\n\n**Price Context:**\n- "
            "Down 8.6% from 52-week high (175.71)\n- Up 15.85% from 52-week low (138.62)\n- Current: 160.60\n- "
            "Drawdown from peak: -7.13%\n\n**Recent News Sentiment:**\n- Mixed but cautious: Some sources see a "
            "technical breakout setup, but others highlight concerns about litigation, balance sheet, and \"not "
            "enough margin of safety\"\n- Most recent articles are cautious but acknowledge the turnaround is working"),
        "why_flagged_neither": (
            "Zero weighing/relationship keyword hits anywhere in the full concatenated reasoning for this session. "
            "Each indicator (trend, RSI, MACD, support/resistance, volatility, news) is reported as an independent "
            "bullet with no sentence tying any two of them together or saying one matters more than another."),
    },
    {
        "label": "pure_listing_2",
        "session": ("newsagent_20261011", "NEE_2026-09-11", "NO_NEWS_0.json.gz"),
        # the source data.json dropped the word "remains" here ("Position at 99.9% exposure."); this is the session's
        # actual submit_decision text, so the excerpt is verbatim like all the others
        "then_jumps_to": (
            "Position remains at 99.9% exposure. Price at $82.31 is below EMA8/21/55 trend (bearish signal) but above "
            "key support at $80.75. RSI 41.3 is neutral, not oversold. 5-day and 20-day returns are negative (-2.08%, "
            "-4.3%). Volume is 92% of 20-day average (below average). Volatility regime is low. No fundamental "
            "catalysts or earnings catalyst in view. Holding current position until price tests support at $80.75 or "
            "breaks above $84.38 resistance."),
        "verbatim_excerpt": (
            "**Technical Analysis:**\n1. **Trend Signal**: Bearish - EMA8 (82.94) is above current price, and EMA21 "
            "(83.85) and EMA55 (85.57) are also above, with a 3.07% spread between 8 and 55 EMAs\n2. **Mean "
            "Reversion**: Neutral - Price is at 0.22 bollinger band position, z-score of -1.61 (somewhat below mean "
            "but not oversold)\n3. **RSI**: 41.3 - Neutral, not oversold\n4. **MACD**: -0.971 line, -0.986 signal, "
            "+0.015 histogram - slight bullish divergence but still bearish\n5. **Volume**: Today's volume (9.88M) is "
            "below 20-day average (10.69M), ratio 0.92 - normal/weak\n6. **Volatility**: Low regime (-1.02 z-score), "
            "ATR 1.46% of price\n7. **Support/Resistance**: Support at $80.75, resistance at $84.38, $87.52, $89.19"),
        "why_flagged_neither": (
            "10 distinct tools called (the most of any bucket), 7-point numbered list of independent indicators, final "
            "paragraph restates each number again with no comparison between them -- a clean example of information "
            "gathered in bulk but never explicitly weighed or cross-referenced."),
    },
    {
        "label": "pure_listing_3",
        "session": ("newsagent_20261011", "UAL_2026-06-30", "NO_NEWS_1.json.gz"),
        "then_jumps_to": (
            "I'll proceed with a Hold strategy at current 220 shares, preserving the strong momentum while staying "
            "flexible to emerging market signals. The technical indicators suggest maintaining the position makes "
            "sense given the bullish trend."),
        "verbatim_excerpt": (
            "**Technical Analysis:**\n1. **Trend**: Bullish (EMA 8/21/55 all aligned upward)\n2. **Mean Reversion**: "
            "Overbought (z-score 2.25, Bollinger position 0.91)\n3. **RSI**: 76.3 (overbought)\n4. **MACD**: Bullish "
            "(8.479 line above 6.65 signal)\n5. **Price Stats**: \n   - 52-week high: $138.77 (only 2% away)\n   - "
            "5-day return: +11.88%\n   - 20-day return: +21.68%\n   - Very strong momentum but approaching "
            "resistance ($138.44)\n\n**Key Observations:**\n- The stock has rallied significantly from ~$115-120 in "
            "early June to current $135.99\n- Strong bullish trend but overbought conditions\n- Approaching 52-week "
            "high ($138.77) and immediate resistance ($138.44)\n- Volume today (5.08M) is below 20-day average "
            "(5.76M)\n- High volatility regime (55.2% annualized)\n\n**Decision Considerations:**\n- Trend is strongly "
            "bullish but price is overbought\n- Only ~2% from 52-week high, resistance at $138.44 is close\n- The "
            "recent news is quiet (no company news)\n- Overbought RSI (76.3) suggests potential pullback\n\nGiven the "
            "overbought conditions and proximity to resistance, I should consider either:\n1. Holding current "
            "position"),
        "why_flagged_neither": (
            "Note 'rallied significantly' appears but does NOT match the keyword list, because the list contains "
            "'significant' (adjective) not 'significantly' (adverb) and word-boundary matching correctly does not "
            "treat the adverb as a hit; this is a deliberate scope limit, not a bug -- see README limitations. Eight "
            "indicators listed as independent bullets, then a hold decision justified only by re-citing 'bullish "
            "trend' alone, not by weighing the overbought signals against it."),
    },
    {
        "label": "pure_listing_4",
        "session": ("newsagent_20261011", "JPM_2026-09-17", "FULL_3.json.gz"),
        "then_jumps_to": (
            "Position at 99.8% exposure, neutral technical signals across trend, mean reversion, RSI, and MACD. Stock "
            "at support level (~348.69) with tight consolidation range. Volatility regime low, no directional bias. "
            "Maintaining current exposure appropriate."),
        "verbatim_excerpt": (
            "**Technical Analysis:**\n1. **Trend Signal:** Neutral - EMA8 (352.14) > EMA21 (353.99)? Actually looking "
            "closer, EMA8 is 352.14 and EMA21 is 353.99, so EMA8 < EMA21 which suggests bearish short-term, but EMA55 "
            "is 348.01 below current price. Overall neutral.\n\n2. **Mean Reversion:** Neutral - z-score -0.49, price "
            "is slightly above Bollinger lower band (348.16), position at 0.09 (close to middle). Not oversold or "
            "overbought.\n\n3. **RSI:** 43.7 - neutral, slightly below 50.\n\n4. **MACD:** -0.625, signal 0.644, "
            "histogram -1.269 - bearish crossover with negative histogram, no fresh cross.\n\n5. "
            "**Support/Resistance:** Next support at 348.69 (very close - just 0.62 below current), resistance at "
            "360.05.\n\n6. **Price Stats:** \n   - 5-day return: -1.2%\n   - 20-day return: -2.23%\n   - Drawdown "
            "from peak: -4.35%\n   - 52-week high: 366.5 (4.7% below)\n\n7. **Volatility:** \n   - 20-day "
            "annualized: 14.6% (low regime)\n   - Volatility z-score: -1.17 (below average)\n   - ATR: 6.99 (2.0% of "
            "price)\n   - Note: \"big moves cluster\"\n\n8. **News Sentiment:** All neutral (0.0 average sentiment "
            "over past 7 days)"),
        "why_flagged_neither": (
            "News (FULL arm, 7 real headlines) and 8 technical readings are each listed and labeled 'neutral' "
            "independently; the model never states whether the news is already captured by the 0.0 average "
            "news-sentiment score, or whether any one of the 8 signals should carry more weight than another -- it "
            "reports all 8 as flatly 'neutral' and holds."),
    },
]

GENUINE = [
    {
        "label": "genuine_1_best",
        "session": ("newsagent_20261011", "ACN_2026-03-24", "FULL_3.json.gz"),
        "matched_phrases": ["outweigh", "combined with", "despite the"],
        "verbatim_quote": (
            "I'll hold flat (0 shares) because the trend is clearly bearish, volatility is high, and there's no strong "
            "reversal signal yet despite the somewhat oversold RSI. The negative news (Mizuho downgrade, pullback) "
            "combined with bearish technicals outweigh the positive fundamental news at this moment."),
        "why_genuine": (
            "Explicitly combines TWO evidence items (negative news + bearish technicals) and states that their "
            "combination outweighs a THIRD, separately-named piece of evidence (positive fundamental news) -- genuine "
            "multi-item weighing, not just a list."),
    },
    {
        "label": "genuine_2",
        "session": ("newsagent_20261011", "MMM_2026-06-18", "NO_NEWS_1.json.gz"),
        "matched_phrases": ["significant"],
        "verbatim_quote": (
            "I'm weighing the bullish technical indicators against the overextended price action. The mean reversion "
            "signal and proximity to Bollinger bands suggest caution."),
        "why_genuine": (
            "Uses the literal verb 'weighing ... against' to explicitly set two evidence clusters (bullish trend "
            "signals vs. overextended/overbought price action) against each other before deciding -- note the "
            "session was flagged via a different, weaker keyword ('significant') elsewhere in the text; this sentence "
            "is the clearer real evidence of genuine weighing in the same session."),
    },
    {
        "label": "genuine_3",
        "session": ("newsagent_20261011", "HON_2026-08-06", "FULL_0.json.gz"),
        "matched_phrases": ["main driver"],
        "verbatim_quote": (
            "Key concerns:\n- The aerospace business (the main driver) had disappointing debut as standalone\n- Stock "
            "crashed after earnings\n- However, the bull case remains intact according to news"),
        "why_genuine": (
            "Explicitly identifies WHICH business segment is the 'main driver' of the overall result (weighing one "
            "piece of fundamental information above others), then relates that negative read to a separate, more "
            "positive overall-news read via 'However'."),
    },
    {
        "label": "genuine_4",
        "session": ("newsagent_20261011", "UBER_2026-06-04", "FULL_0.json.gz"),
        "matched_phrases": ["mixed signals"],
        "verbatim_quote": (
            "The news is heavily negative on AI spending/restructuring with job cuts (23% of people team), but also "
            "has mixed signals on robotaxis investment."),
        "why_genuine": (
            "States that two sub-components of the SAME evidence type (news) point in different directions, i.e. "
            "explicitly characterizes the relationship (mixed/conflicting) between two news items rather than just "
            "listing both."),
    },
    {
        "label": "genuine_5_q3news_crossmodel",
        "session": ("q3news_20261012_S1", "CVX_2026-05-18", "NO_NEWS_3.json.gz"),
        "matched_phrases": ["contradict"],
        "verbatim_quote": (
            "Also, checking the mean reversion signal. If the stock is overbought, maybe it's a good time to sell. But "
            "the trend signal might contradict that."),
        "why_genuine": (
            "Explicitly reasons about whether one technical signal (trend) would contradict the implication of "
            "another (mean reversion) -- genuine relationship reasoning between two named evidence items, from the "
            "second model (Qwen3-8B, cross-model check)."),
    },
    {
        "label": "genuine_6",
        "session": ("newsagent_20261011", "TRV_2026-08-27", "FULL_0.json.gz"),
        "matched_phrases": ["outweighs"],
        "verbatim_quote": (
            "Maintaining current exposure as upside case (probability ~55% for 5-day upside, modest positive return "
            "expected) outweighs immediate adjustment need."),
        "why_genuine": (
            "Explicit weighing language comparing the (probabilistic) upside case against the case for an immediate "
            "position change; terse but unambiguous."),
    },
    {
        "label": "genuine_7_news_vol_connection",
        "session": ("newsagent_20261011", "CB_2026-03-11", "FULL_0.json.gz"),
        "matched_phrases": ["while the"],
        "verbatim_quote": (
            "While the news-driven volatility is evident, the trend and RSI indicators point to potential "
            "stabilization."),
        "why_genuine": (
            "From the check-4 same-sentence sample: explicitly ties the news evidence to the measured volatility "
            "('news-driven volatility'), then relates that combination to a third, separate signal cluster "
            "(trend+RSI)."),
    },
]


# ------------------------------------------------------------------------------------------------ limitations
def render_limitations(o: dict, c4: dict) -> list[str]:
    """o: rates.overall; c4: check4 block (with window2_sensitivity)."""
    w2 = c4["window2_sensitivity"]
    return [
        "This is approximate keyword/phrase matching on ~4000 free-text reasoning traces, not a validated NLP "
        "classifier -- treat every rate here as directional, not exact, and prefer the strict/strict2 variants and the "
        "hand-check precision numbers over the raw percentages when the two disagree.",
        "WEIGHING false positives: roughly 1 in 4 of hand-checked 'significant'/'minor' matches described the trader's "
        "own position or trade SIZE, not the importance of a piece of external evidence; the keyword cannot "
        "distinguish these cases.",
        # kept verbatim from the source write-up (its "~46%" predates the 2026-10-23 union correction; the exact
        # union share is in precision_handcheck.relationship_judgment.dominant_false_positive_pattern)
        "RELATIONSHIP false positives (for the task's strict 'relates two evidence items to each other' definition): "
        "the single largest relationship category, 'aligns with'/'align with'/'aligned with' (~46% of all raw "
        "relationship-flagged sessions touch this family), is overwhelmingly a decision-justification tic ('my "
        "decision aligns with signal X') rather than genuine cross-evidence reasoning. Hand-check strict precision for "
        "relationship-flagged sessions was only ~23.5% (4/17); a looser, still-defensible reading got to ~50%. Report "
        "both the raw (90.2%) and strict2 (57.4%) rates; do not quote the raw number alone as 'relationship reasoning "
        "rate'.",
        f"A genuine qualitative counter-example was found in a session classified 'neither' by the keyword rule "
        f"(JPM_2026-09-17/FULL_3): 'Given the news about Iran war oil forecast being dropped (which could be negative "
        f"for earnings) but also the housing commitment being positive, the sentiment is neutral overall' -- this IS a "
        f"tacit weighing of two news items reaching a netted-out conclusion, but uses no listed keyword. The "
        f"{_r(o['pct_neither'])}% raw 'neither' / pure-listing rate is therefore a slight OVER-estimate of true "
        f"pure-listing behavior (misses this kind of unworded netting-out); conversely the "
        f"{_r(o['pct_neither_strict'])}% strict-neither rate is likely an UNDER-estimate of true pure listing in "
        f"the other direction, since many of its 'weighing/relationship' credits are the weak phrases. The true "
        f"pure-listing rate is bounded within roughly [{_r(o['pct_neither'], 0)}%, {_r(o['pct_neither_strict'], 0)}%] "
        f"and we cannot pin it down more precisely with this method.",
        f"Check 4 (explicit news<->volatility connection) is highly sensitive to window size: {c4['rate_pct']}% (same "
        f"sentence, n={c4['n_eligible']}) vs {w2['rate_pct']}% (2-sentence window, same n) -- report as a range, not a "
        f"point estimate.",
        "'Significantly' (adverb) and other inflections beyond the literal listed forms are deliberately NOT matched "
        "(word-boundary exact phrase match only); this is a documented scope choice, not an oversight, and means the "
        "true keyword-coverage rate for magnitude language is a bit higher than reported if adverb forms were "
        "included -- not re-run here to keep the exact pattern list auditable and simple.",
        "No scipy or statsmodels available in the project .venv (checked at the start); all statistics (proportions, "
        "Wilson CIs, two-proportion z-tests, OLS slope+SE) are closed-form numpy/math, not library calls. This does "
        "not change any result, just how it was computed.",
        "FULL_T06_* files (a temperature-variant arm, 500 files per corpus) exist alongside the plain FULL/NO_NEWS "
        "files but were excluded as out of scope for this specific task's corpus definition.",
    ]
