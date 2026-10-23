# Five reasoning models: description (codexpilot_20261018)

This is a tiny exploratory pilot: 6 days, 5 runs per day (ORIG x2, NOLABEL, UNIT5D, PLACEBO), and two frameworks (our 32-tool
harness and Codex CLI 0.162.1). This page covers the five models whose APIs return a reasoning field: Qwen3-8B, Qwen3.5-9B,
Qwen 27B (Qwen3.8-27B-FP8), DeepSeek (deepseek-reasoner) and Kimi K3. That is 300 runs. Sonnet is left out, because its thinking
is hidden in both frameworks. **Nothing here is a test.**

* **Source.** Saved records only (CPU, no model call), by `repro/codexpilot/describe_reasoning.py`. For the three earlier models,
  all six cells match `describe.json` exactly (usable runs, shifts, pastes, accuracy, tool calls, computed in code).
* **Files.** `describe_reasoning_models.json` has 1,004 records {model, framework, metric, value, n}. The excerpts are in
  `examples_reasoning_models.json` (X1 to X6 below).
* **Usable runs** = a valid decision and not flagged by the leakage audit (the registered rule). Out of 30 per cell, the excluded
  runs are: DeepSeek / Codex 7 flagged; Qwen3-8B / Codex 1 flagged and 3 invalid; Qwen3.5-9B / Codex 1 invalid; Qwen 27B /
  Codex 2 flagged (an attempted write to /tmp, blocked by the sandbox).

**Settings that differ between rows** (all taken from the run records):

* **Harness token cap per turn.** 2,048 for Qwen3-8B and Qwen3.5-9B, which had 7 of 37 and 14 of 47 turns cut. 8,192 for Qwen 27B
  and DeepSeek, and 16,384 for Kimi; none of their turns was cut.
* **Reasoning effort.**
  * Kimi was sent "high" in both frameworks. Moonshot's Chat Completions endpoint may ignore that field, and then the harness ran at
    Kimi's default, "max".
  * Qwen 27B ran at "xhigh" in Codex, because its chat template rejects "high". The harness got the template default, which is also
    xhigh.
* **Visible reasoning.**
  * Kimi's Codex reasoning arrives as summary text, from Moonshot's Responses API.
  * Kimi writes much less reasoning than the others: 1,864 characters per run in the harness and 3,574 in Codex. DeepSeek writes
    8,000 to 9,600 and Qwen 27B 15,800 to 17,400.

## Tables

Volatility forecast: ORIG noise and within-day shifts in ln(expected_vol_pct); days in brackets; * = |mean| > 2 SE.

| model / framework | usable / finished | ORIG run-to-run abs diff (pairs) | NOLABEL | UNIT5D | PLACEBO | NOLABEL - PLACEBO | UNIT5D - PLACEBO |
|---|---|---|---|---|---|---|---|
| Qwen3-8B / harness | 30/30 | 0.64 (6) | +0.12 (6) | -0.47 (6) | -0.43 (6) | +0.56 (6) | -0.04 (6) |
| Qwen3-8B / Codex CLI | 26/30 | 0.35 (4) | -0.41* (6) | -0.29* (6) | -0.46* (4) | +0.09 (4) | +0.15 (4) |
| Qwen3.5-9B / harness | 30/30 | 0.40 (6) | +0.63* (6) | -0.19 (6) | +0.12 (6) | +0.50* (6) | -0.31 (6) |
| Qwen3.5-9B / Codex CLI | 29/30 | 0.70 (6) | -0.40 (6) | -0.29 (6) | -0.18 (5) | +0.04 (5) | +0.10 (5) |
| Qwen 27B (Qwen3.8-27B-FP8) / harness | 30/30 | 0.28 (6) | +0.13 (6) | +0.15 (6) | +0.11 (6) | +0.01 (6) | +0.03 (6) |
| Qwen 27B (Qwen3.8-27B-FP8) / Codex CLI | 28/30 | 0.09 (6) | +0.10* (5) | +0.05 (6) | +0.03 (5) | +0.01 (4) | +0.01 (5) |
| DeepSeek (reasoner) / harness | 30/30 | 0.14 (6) | -0.04 (6) | +0.02 (6) | +0.13* (6) | -0.17* (6) | -0.12 (6) |
| DeepSeek (reasoner) / Codex CLI | 23/30 | 0.14 (4) | +0.03 (4) | -0.10 (3) | +0.10 (5) | -0.06 (4) | -0.22* (3) |
| Kimi K3 / harness | 30/30 | 0.16 (6) | +0.08 (6) | -0.14* (6) | +0.08 (6) | -0.00 (6) | -0.22* (6) |
| Kimi K3 / Codex CLI | 30/30 | 0.09 (6) | -0.01 (6) | -0.03 (6) | +0.01 (6) | -0.01 (6) | -0.04 (6) |

Return forecast: the same in expected_return_pct, percentage points.

| model / framework | ORIG run-to-run abs diff | NOLABEL | UNIT5D | PLACEBO | NOLABEL - PLACEBO | UNIT5D - PLACEBO |
|---|---|---|---|---|---|---|
| Qwen3-8B / harness | 2.02 | +1.93* (6) | -0.96 (6) | +0.96 (6) | +0.97 (6) | -1.92 (6) |
| Qwen3-8B / Codex CLI | 1.62 | +0.23 (6) | +0.34 (6) | +0.96 (4) | +1.18 (4) | +1.35 (4) |
| Qwen3.5-9B / harness | 1.33 | +2.78* (6) | -0.22 (6) | -0.60 (6) | +3.38* (6) | +0.38 (6) |
| Qwen3.5-9B / Codex CLI | 3.57 | -0.53 (6) | -0.69 (6) | +0.04 (5) | +0.38 (5) | +0.39 (5) |
| Qwen 27B (Qwen3.8-27B-FP8) / harness | 0.98 | +0.53 (6) | +0.23 (6) | +0.33 (6) | +0.20 (6) | -0.10 (6) |
| Qwen 27B (Qwen3.8-27B-FP8) / Codex CLI | 1.18 | +0.30 (5) | +0.61 (6) | -0.13 (5) | +0.60 (4) | +1.10 (5) |
| DeepSeek (reasoner) / harness | 1.02 | -0.33 (6) | +0.07 (6) | -0.36 (6) | +0.03 (6) | +0.43 (6) |
| DeepSeek (reasoner) / Codex CLI | 0.85 | +0.45 (4) | +0.33 (3) | +0.24 (5) | +0.03 (4) | -0.33 (3) |
| Kimi K3 / harness | 0.72 | -0.26 (6) | +0.23 (6) | -0.34 (6) | +0.08 (6) | +0.57 (6) |
| Kimi K3 / Codex CLI | 0.67 | +0.18 (6) | -0.40 (6) | +0.35 (6) | -0.17 (6) | -0.75* (6) |

Annualised figure submitted as the 5-day vol: strict (broad), out of the usable runs of that arm.

| model / framework | all | ORIG | NOLABEL | UNIT5D | PLACEBO |
|---|---|---|---|---|---|
| Qwen3-8B / harness | 4 (4) of 30 | 2 (2) of 12 | 2 (2) of 6 | 0 (0) of 6 | 0 (0) of 6 |
| Qwen3-8B / Codex CLI | 1 (1) of 26 | 1 (1) of 10 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 4 |
| Qwen3.5-9B / harness | 2 (5) of 30 | 0 (1) of 12 | 2 (3) of 6 | 0 (0) of 6 | 0 (1) of 6 |
| Qwen3.5-9B / Codex CLI | 2 (2) of 29 | 2 (2) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 5 |
| Qwen 27B (Qwen3.8-27B-FP8) / harness | 0 (0) of 30 | 0 (0) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 6 |
| Qwen 27B (Qwen3.8-27B-FP8) / Codex CLI | 0 (0) of 28 | 0 (0) of 12 | 0 (0) of 5 | 0 (0) of 6 | 0 (0) of 5 |
| DeepSeek (reasoner) / harness | 0 (0) of 30 | 0 (0) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 6 |
| DeepSeek (reasoner) / Codex CLI | 0 (0) of 23 | 0 (0) of 9 | 0 (0) of 5 | 0 (0) of 4 | 0 (0) of 5 |
| Kimi K3 / harness | 0 (0) of 30 | 0 (0) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 6 |
| Kimi K3 / Codex CLI | 0 (0) of 30 | 0 (0) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 6 |

Reasoning output mentions an annualised figure (rule any; exact-value rule in brackets), and how many of those runs still submit it as the 5-day vol (strict / broad).

| model / framework | runs with reasoning text | mention any (exact) | ORIG | NOLABEL | UNIT5D | PLACEBO | of those, submit it strict / broad | broad pastes without a mention | harness: called get_risk_budget, all (UNIT5D) |
|---|---|---|---|---|---|---|---|---|---|
| Qwen3-8B / harness | 30/30 | 15 (15) of 30 | 9 (9) of 12 | 2 (2) of 6 | 0 (0) of 6 | 4 (4) of 6 | 3 / 3 of 15 | 1 | 0/30 (0/6) |
| Qwen3-8B / Codex CLI | 26/26 | 9 (7) of 26 | 2 (2) of 10 | 4 (3) of 6 | 0 (0) of 6 | 3 (2) of 4 | 1 / 1 of 9 | 0 | - |
| Qwen3.5-9B / harness | 30/30 | 22 (22) of 30 | 12 (12) of 12 | 5 (5) of 6 | 0 (0) of 6 | 5 (5) of 6 | 1 / 3 of 22 | 2 | 1/30 (0/6) |
| Qwen3.5-9B / Codex CLI | 29/29 | 19 (18) of 29 | 10 (9) of 12 | 5 (5) of 6 | 0 (0) of 6 | 4 (4) of 5 | 1 / 1 of 19 | 1 | - |
| Qwen 27B (Qwen3.8-27B-FP8) / harness | 30/30 | 29 (29) of 30 | 12 (12) of 12 | 6 (6) of 6 | 5 (5) of 6 | 6 (6) of 6 | 0 / 0 of 29 | 0 | 28/30 (6/6) |
| Qwen 27B (Qwen3.8-27B-FP8) / Codex CLI | 28/28 | 22 (22) of 28 | 12 (12) of 12 | 5 (5) of 5 | 0 (0) of 6 | 5 (5) of 5 | 0 / 0 of 22 | 0 | - |
| DeepSeek (reasoner) / harness | 30/30 | 29 (23) of 30 | 11 (8) of 12 | 6 (4) of 6 | 6 (6) of 6 | 6 (5) of 6 | 0 / 0 of 29 | 0 | 29/30 (6/6) |
| DeepSeek (reasoner) / Codex CLI | 23/23 | 18 (11) of 23 | 9 (6) of 9 | 4 (2) of 5 | 0 (0) of 4 | 5 (3) of 5 | 0 / 0 of 18 | 0 | - |
| Kimi K3 / harness | 30/30 | 14 (5) of 30 | 7 (3) of 12 | 3 (2) of 6 | 1 (0) of 6 | 3 (0) of 6 | 0 / 0 of 14 | 0 | 16/30 (2/6) |
| Kimi K3 / Codex CLI | 30/30 | 24 (11) of 30 | 12 (5) of 12 | 6 (2) of 6 | 0 (0) of 6 | 6 (4) of 6 | 0 / 0 of 24 | 0 | - |

Work done and accuracy.

| model / framework | mean tool calls / commands (finished; usable) | computed a vol from prices.csv | mean abs ln(forecast / realised 5d vol) (bias) [SE over days] | ORIG | NOLABEL | UNIT5D | PLACEBO |
|---|---|---|---|---|---|---|---|
| Qwen3-8B / harness | 1.0; 1.0 | - | 0.67 (+0.38) [0.22] | 0.75 | 0.91 | 0.43 | 0.47 |
| Qwen3-8B / Codex CLI | 2.2; 2.4 | 0/26 | 0.55 (+0.08) [0.11] | 0.63 | 0.55 | 0.42 | 0.56 |
| Qwen3.5-9B / harness | 1.1; 1.1 | - | 0.65 (+0.36) [0.16] | 0.52 | 1.03 | 0.41 | 0.76 |
| Qwen3.5-9B / Codex CLI | 10.0; 10.0 | 25/29 | 0.54 (+0.19) [0.10] | 0.61 | 0.66 | 0.41 | 0.38 |
| Qwen 27B (Qwen3.8-27B-FP8) / harness | 9.1; 9.1 | - | 0.40 (+0.03) [0.08] | 0.38 | 0.42 | 0.40 | 0.44 |
| Qwen 27B (Qwen3.8-27B-FP8) / Codex CLI | 5.9; 5.7 | 23/28 | 0.41 (+0.07) [0.12] | 0.40 | 0.53 | 0.38 | 0.37 |
| DeepSeek (reasoner) / harness | 12.1; 12.1 | - | 0.40 (+0.13) [0.13] | 0.38 | 0.44 | 0.38 | 0.40 |
| DeepSeek (reasoner) / Codex CLI | 8.1; 7.7 | 23/23 | 0.39 (+0.03) [0.11] | 0.36 | 0.47 | 0.40 | 0.34 |
| Kimi K3 / harness | 3.7; 3.7 | - | 0.40 (+0.17) [0.15] | 0.42 | 0.38 | 0.36 | 0.41 |
| Kimi K3 / Codex CLI | 4.6; 4.6 | 19/30 | 0.40 (+0.09) [0.12] | 0.39 | 0.38 | 0.38 | 0.45 |
| baseline: readings ann_vol_20d x sqrt(5/252) | | | 0.48 (+0.03) | | | | |
| baseline: S1 rational prior sigma5 | | | 0.43 (+0.10) | | | | |

## What the tables show

1. **Only the two small Qwen models ever submit an annualised figure as the 5-day vol.** That happened in 9 strict (12 broad) of
   their 115 usable runs. Qwen 27B, DeepSeek and Kimi did it in 0 of 171 runs, in both frameworks.

2. **Every model mentions the annualised figure in its reasoning. They differ in whether they convert it.**
   * The reasoning mentions one in 65 of the 115 small-Qwen runs and in 136 of the 171 runs of the three larger models.
   * Of the 65 small-Qwen runs, 6 still submit it (8 broad), about 1 in 10. X1 reads the 10-day annualised 12.6 as "the 5-day
     volatility". X2 writes 52 and then ticks off "5-day one-sd in percent".
   * Of the 136 larger-model runs, none submits it: they convert, for example "45% × sqrt(5/252) ≈ 6.35%" (X3).
   * Four small-Qwen broad pastes had no mention in the reasoning field at all. For example, in Qwen3.5-9B / harness / CB /
     NOLABEL the final answer itself says "Volatility elevated at 14.6% annualized".

3. **UNIT5D removes the mention only where the readings are the only source.**
   * In Codex, 0 of the 28 UNIT5D runs mention an annualised figure. In the harness, the two small Qwens mention one in 0 of 12.
   * In the harness, DeepSeek still mentions one in 6 of 6 UNIT5D runs, Qwen 27B in 5 of 6 and Kimi in 1 of 6. These models call
     `get_risk_budget` (DeepSeek in 29 of 30 runs, Qwen 27B 28 of 30, Kimi 16 of 30). That tool reports the trailing 20-day vol in
     annual units, and the arm does not rewrite it (X5).
   * So in the harness the UNIT5D arm does not keep the annual number away from models that use tools. They converted it
     correctly anyway.

4. **The shifts compared with PLACEBO, the fairer yardstick, are mostly within noise.**
   * **Qwen 27B.** In the harness all three arms, the placebo included, sit 0.11 to 0.15 above ORIG in ln(vol). That is a generic
     text-change shift, so each edit minus the placebo is +0.01 to +0.03. In Codex the NOLABEL mark (+0.10\*) also disappears
     against the placebo (+0.01).
   * **Kimi, harness.** UNIT5D lowers the vol forecast against the placebo (-0.22\*). It is at or below zero on all 6 days, and
     largest on MRK (-0.68) and CB (-0.34).
     * On MRK the two ORIG runs submitted 5.5 and 4.5; ORIG run 0 used ATR × √5 = 5.9 %.
     * The UNIT5D run read the 5-day equivalent (3.4 %), also read the calibration tool ("you overstate volatility") and submitted
       2.8 (X4).
     * The realised vol was 1.6 %.
   * **Kimi, Codex.** No vol shift (all |shift| ≤ 0.04). UNIT5D lowers the return forecast against the placebo by 0.75 pp\*, at or
     below zero on 6 of 6 days.
   * **DeepSeek.** NOLABEL minus PLACEBO is -0.17\* in the harness, driven by one day (CRWD, -0.69). UNIT5D minus PLACEBO is
     -0.22\* in Codex, over 3 days only. Both come largely from DeepSeek's own placebo shift (+0.13 and +0.10).
   * **The small Qwens.** The marks (Qwen3.5-9B / harness NOLABEL minus PLACEBO: +0.50\* in vol, +3.38 pp\* in return) come from the
     pastes and from one HOOD run (see `pilot_report.md`).
   * **Overall,** 6 of the 40 "minus PLACEBO" comparisons carry a \*. The rule is crude (2 SE, with sigma from 4 to 6 pairs), so
     some marks are expected by chance. None of them is a result.

5. **Noise sets what can be seen.** The ORIG run-to-run difference in ln(vol) is:
   * 0.09 in Kimi / Codex and Qwen 27B / Codex;
   * 0.14 to 0.16 in DeepSeek and Kimi / harness;
   * 0.28 in Qwen 27B / harness;
   * 0.35 to 0.70 in the small Qwens.

   Shifts of about 0.1 can show only in the low-noise cells.

6. **Accuracy.**
   * Qwen 27B, DeepSeek and Kimi are all at 0.39 to 0.41 mean |ln(forecast / realised)| in both frameworks.
   * That is below both baselines: 0.48 for the readings' 20-day vol in 5-day units, and 0.43 for the S1 prior.
   * The day-level SE is 0.08 to 0.15, so these six cells cannot be told apart.
   * The small Qwens are at 0.54 to 0.67, mostly because of the pastes.
   * Every cell's bias is positive: its forecasts are too high on average.

7. **Work done.**
   * **Harness tool calls per run:** Qwen 27B 9.1 against about 1 for the small Qwens; DeepSeek 12.1 and Kimi 3.7.
   * **Codex runs that computed a vol from prices.csv:** DeepSeek 23/23, Qwen3.5-9B 25/29, Qwen 27B 23/28 (X6), Kimi 19/30 and
     Qwen3-8B 0/26.
   * Computing in code did not stop the Qwen3.5-9B pastes (pilot C2). Kimi and DeepSeek never pasted, whether they computed or not.

**Limits.**

* **Size.** Only 6 days, with one run per edit arm per day.
* **The mention rule.** It is plain text matching on the reasoning field.
  * I checked its hits by hand in DeepSeek / harness / UNIT5D, Qwen 27B / harness / UNIT5D and Kimi / Codex / ORIG. No hit rests on
    the 15 % portfolio target vol alone.
  * The exact rule is a lower bound. The "any" rule also counts rounded quotes and the model's own annualised computations.
  * A missing mention can simply mean the model did not write its thinking out. This matters most for Kimi, whose reasoning is
    short.
* **Mixed settings.** The token caps and possibly Kimi's effort differ between rows and frameworks (see above). The arm shifts are
  within one model and framework, so these differences do not bias them, but they affect comparisons across rows.

## Excerpts

Each excerpt names the model, framework, day and arm, and gives the final 5-day vol (realised 5-day vol in brackets, never shown to
the agent).

* **X1. Qwen3-8B / Codex / CB / ORIG run 1, submitted 15.0 (3.8).** *"…the 5-day volatility is around 12.6%… volatility of 15%."*
  12.6 is the annualised 10-day reading.
* **X2. Qwen3.5-9B / Codex / CRWD / ORIG run 0, submitted 52.0 (12.7).** *"- Ann vol 10d: 105.4%"* … *"52% expected volatility"* …
  *"- expected_vol_pct: 5-day one-sd in percent ✓"*
* **X3. Kimi K3 / Codex / VST / ORIG run 1, submitted 7.0 (7.3).** *"ann vol 45% → 5-day sd = 45% × sqrt(5/252) ≈ 45% × 0.141 ≈
  6.35%."*
* **X4. Kimi K3 / harness / MRK / UNIT5D, submitted 2.8 (1.6).** *"Vol 5-day equiv ~3.4-3.8%."* … *"Typical 5-day vol ~3.4% but
  I've been overstating. Set expected_vol ~2.8%."* The same day's ORIG runs submitted 5.5 and 4.5.
* **X5. DeepSeek / harness / MCHP / UNIT5D, submitted 11.0 (5.3).** *"Trailing 20d vol 74.1% annualized"* (from get_risk_budget)
  … *"74*sqrt(5/252) = 74*0.1409 = 10.4%… I'll say 11."*
* **X6. Qwen 27B / Codex / CRWD / ORIG run 0, submitted 14.0 (12.7).** Its own script printed *"implied 5d 1sd from 10d daily vol:
  16.80%"* and *"…from 20d daily vol: 12.46%"*. It then reasoned: *"I'll use 14%."*

## Rules added in this stage

```
Definitions added in this stage (fixed before the numbers were looked at):
  reasoning output  the provider's reasoning field only, never the final answer:
                    harness   every turn's `reasoning` / `reasoning_content` in the session trace (for Kimi and Qwen 27B checked
                              equal to the stored raw responses, ctx.raw_responses / ctx.raw_choices);
                    Codex     every reasoning item of the relay's raw SSE streams (response.output_item.done, item type
                              reasoning: content reasoning_text + summary summary_text; Kimi returns its reasoning as summary
                              text), checked equal to Codex's own rollout reasoning items in every run
  mentions an annualised figure
                    exact     the reasoning contains one of the day's four annualised readings (ann_vol_10d/20d/60d_pct,
                              parkinson_vol_10d_pct of the ORIG block) written with its decimal as in the readings (e.g. 75.9), as
                              a standalone number (no letter, digit, '.' or '_' joined to it)
                    any       exact, or a standalone number in [0.9 min(A), 1.1 max(A)] (the strict paste range) with an annual
                              keyword (annual / annualis / annualiz / ann_vol / ann. vol / ann vol / yearly / per year / parkinson)
                              in the 60 characters before it; catches rounded quotes ("ann. vol ~75-90%") and the model's own
                              annualised computations. Primary rule: any.
  still submits it  among runs whose reasoning mentions an annualised figure (any), the share whose final expected_vol_pct is pasted
                    (strict; broad in the second number), with the paste rules of describe.py
  shift minus PLACEBO  per day with a usable ORIG run, the arm run and the PLACEBO run: (arm - ORIG mean) - (PLACEBO - ORIG mean)
                    = arm - PLACEBO, averaged over those days; under no effect one day has variance 2 sigma^2 (sigma^2 from the
                    ORIG pairs as in describe.py), SE = sqrt(2 sigma^2 / n), marked outside noise when |mean| > 2 SE
  tool calls        mean n_tool_calls over finished runs (harness: tool calls incl. submit_decision; Codex: commands + file changes
                    + other tool items), as in pilot_report.md; the mean over usable runs is stored too
  computed a vol    describe.computed_vol on the Codex runs' commands (python + prices.csv + std / var / stdev), usable runs

```

The rules reused from the pilot (usable, ORIG noise, arm shift, the 2 SE mark, pasted strict / broad, realised 5-day vol, accuracy, computed a vol in code) are in the docstring of `repro/codexpilot/describe.py`. To rebuild: `PYTHONPATH=. .venv/bin/python -m repro.codexpilot.describe_reasoning`.
