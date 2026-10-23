"""The prose of results/mechanisms/salience/data.json, kept verbatim from the research workspace's
results/mech4_20261023/salience/data.json (after its 2026-10-23 independent check). Only two kinds of change:
the file paths inside SIGMA_SCALE and RV5_DEFINITION are placeholders that salience.py fills with this repository's
paths, and GROUNDING_REASON is a template filled with the counts of the grounding rescan. Every number quoted in the
headline texts is re-checked against the computed values by salience._check_prose before data.json is written.
"""
from __future__ import annotations

TASK = (
    'SALIENCE: does the size of a conspicuous annualised-volatility number the agent sees '
    '(get_volatility_stats tool output) predict its 5-day expected_vol_pct forecast beyond what the rational '
    'benchmark (events_all.parquet sigma) justifies?'
)
PRIMARY_MODEL = 'Qwen3.5-9B'
PRIMARY_EXCLUDED = (
    'FULL_T06_* files (label FULL_T06, temperature=0.6 robustness arm, 500 files) -- a separate temperature '
    'sweep, not part of the main k=0..3 FULL/NO_NEWS comparison this analysis targets.'
)
PRIMARY_FILTER = (
    'session kept only if submit_decision has all of '
    '{action,shares,target_exposure_pct,p_up,expected_return_pct,expected_vol_pct,confidence,reasoning} AND '
    'get_volatility_stats was called >=1 time in the trace (last call used if >1).'
)
SECONDARY_MODEL = 'Qwen3-8B (thinking on)'
SECONDARY_NOTE = (
    'Most q3news sessions never call get_volatility_stats (different tool-use behaviour under thinking-on), '
    'so the usable N here is far smaller than newsagent; used only as a secondary robustness check on the '
    'step-2 regression sign/magnitude, not in the headline n.'
)
GROUNDING_MODEL = 'Qwen3-8B'
GROUNDING_REASON = (    # filled from the rescan of every grounding session (salience._grounding_census)
    "Verified directly by inspecting every session's trace: in this corpus the price-tool readings are "
    "injected as static text in the user prompt (grounding='price-tool-readings block injected'), so the "
    "agent's tool_calls contain only submit_decision in the overwhelming majority of sessions "
    "({n_only_submit:,}/{n_files:,}); a full rescan (corrected 2026-10-23 after independent verification) found "
    "{n_risk_budget:,}/{n_files:,} sessions additionally call get_risk_budget (a different tool, also never "
    "get_volatility_stats). get_volatility_stats specifically is never invoked as a tool anywhere in this corpus "
    "({n_vol_stats:,}/{n_files:,}). The task's own inclusion rule ('get_volatility_stats was called at least "
    "once') therefore yields exactly {n_usable} usable sessions here, confirmed on all {n_files} session files, "
    "not inferred from a sample. This corpus cannot test tool-output copying by construction and is reported as "
    "skipped, not substituted with a weaker proxy."
)
JOIN_METHOD = (
    'day_id (TICKER_date) looked up as event_id in events_all.parquet first; misses fell back to '
    'nonevent_days.parquet joined on ticker+t (sigma = exp(lsig) there). Checked explicitly which corpus '
    'day_ids are events_all misses (6/250 newsagent day_ids: CSGP_2026-03-31, ED_2026-03-12, GLW_2026-03-12, '
    'GWW_2026-06-16, IDXX_2026-08-04, PG_2026-03-12) and confirmed all 6 are present in nonevent_days.'
)
SIGMA_SCALE = (
    'No numeric conversion needed, and this is verified rather than assumed: {rule_json} '
    "field 'operationalization.target_and_bins' states R5 = 100*ln(C[t+5]/C[t]) (the realised 5-day log "
    'return, in percent) and sigma = exp(lsig), both evaluated at close t, with u=(R5-m)/sigma. So '
    "events_all.sigma IS ALREADY the rational model's standard deviation of the 5-day percent log return -- "
    "same units (percent) and same horizon (5 trading days) as the agent's submitted expected_vol_pct. Used "
    'directly, unscaled, as rational_sigma5_pct in the regression below.'
)
RV5_DEFINITION = (
    'rv5_realised_pct = sqrt(sum of the 5 squared daily log returns in percent, close t to close t+5) from '
    "{panel}, matching the project's own rv5 definition in the research workspace's "
    "repro/rsize/rules_doc.py ('sqrt of the sum of the 5 squared daily log returns (percent)')."
)
RV5_VALIDATION = (
    'For AAPL_2026-03-19, summing the 5 panel daily log returns from 2026-03-19 to 2026-03-26 reproduces '
    'events_all.R5 = 1.566235 to 6 decimal places (1.5662345352...), confirming date alignment and '
    'close-price series match between the panel and the benchmark.'
)
RV5_WHY = (
    'events_all.R5 is a SIGNED 5-day return, not a volatility measure; sqrt(sum of squared daily returns) is '
    "the more faithful realised-volatility proxy and is exactly the quantity this project's own code already "
    'calls rv5 -- used instead of the noisier |R5| single-path proxy for the accuracy metric in step 3.'
)
STEP2_SPEC = (
    'expected_vol_pct ~ a + b1*rational_sigma5_pct   [model 1]   and expected_vol_pct ~ a + '
    'b1*rational_sigma5_pct + b2*ann_vol_20d_pct   [model 2]. Closed-form OLS via numpy normal equations (no '
    'scipy/statsmodels in the venv -- confirmed absent). SE = classical OLS (homoskedastic) standard errors; '
    'se_hc1 = heteroskedasticity-robust (HC1 sandwich) SE also reported as a robustness check. p-values use a '
    'normal approximation to the t-distribution (fine given dof in the hundreds).'
)
STEP2_HEADLINE = (
    'In the primary corpus (newsagent FULL, n=694), b1 (rational 5-day sigma) is strongly significant (0.566, '
    'SE 0.069, t=8.17) and model 1 R2=0.0880. Adding ann_vol_20d_pct (model 2) moves b2 to -0.0073 (SE '
    '0.0205, t=-0.36, not significant) and R2 to only 0.0881 -- delta R2 = 0.00017, i.e. essentially no '
    'additional linear explanatory power from the annualised headline number once the rational benchmark is '
    'in the regression. The same near-zero, non-significant b2 pattern holds in NO_NEWS (b2=+0.0047, SE '
    '0.0210) and in the much smaller q3news FULL cross-check (b2=-0.0433, SE 0.1016). CONCLUSION: the '
    'AGGREGATE linear test finds no detectable smooth anchoring effect of ann_vol_20d_pct on top of the '
    'rational sigma. This does not mean salience-copying is absent -- see step 3, which finds a concentrated, '
    'rare, discrete failure mode that a linear-in-the-whole-sample regression is not well suited to detect.'
)
STEP3_DEFINITION = (
    'looks_copied = |expected_vol_pct - ann_vol_20d_pct| / ann_vol_20d_pct <= 0.15 (within 15% of the '
    'annualised headline figure -- effectively requires the agent to have reported ~7x too much vol relative '
    'to the correct sqrt-time-scaled 5-day figure, since ann_vol_20d_pct / 7.1 is roughly what a correct '
    '5-day conversion would give).'
)
STEP3_METRIC = (
    'abs(ln(expected_vol_pct / rv5_realised_pct)) -- absolute log-ratio error against the panel-computed '
    'realised 5-day vol (see realised_5d_vol_method); restricted to sessions with rv5_realised_pct > 0.'
)
STEP3_HEADLINE = (
    'The looks-copied group is RARE (FULL: 15/694 = 2.16%; NO_NEWS: 12/751 = 1.60%; combined: 27/1445 = '
    '1.87%) but has dramatically worse forecast accuracy: mean abs-log-ratio-error combined = 1.73 (SE 0.126) '
    'for the copied group vs 0.62 (SE 0.012) for everyone else -- a difference of 1.11 (SE 0.127, t=8.78), '
    'huge and precisely estimated despite n=27 because the effect size is large (e^1.73≈5.6x vs e^0.62≈1.9x '
    'typical multiplicative miss). Consistent in FULL alone (diff=1.10, SE 0.172, t=6.39, n_copied=15) and '
    'NO_NEWS alone (diff=1.13, SE 0.195, t=5.82, n_copied=12). CAVEAT: n_copied is small in every split '
    '(12-27); the point estimate of the group SIZE is noisy even though the point estimate of the accuracy '
    'GAP is not (because within-group variance, not n, sets that SE).'
)
STEP3_RECONCILIATION = (
    "Step 2's regression found no smooth linear anchoring effect; step 3 finds a strong, real effect "
    'concentrated in a small (~2%) subgroup that nearly literally copies the annualised number. These are not '
    'contradictory: salience-copying here looks like a rare DISCRETE failure (full copy or no copy), not a '
    "graded bias that shifts everyone's forecast a little -- a linear regression averaged over ~98% "
    'unaffected sessions will correctly find ~zero slope even when a sharp, large, real failure mode exists '
    'in the tail.'
)
STEP5_HEADLINE = (
    'Neither the regression b2 (FULL -0.0073 vs NO_NEWS +0.0047, diff -0.0120, SE 0.0293, t=-0.41) nor the '
    'looks-copied RATE (FULL 2.16% vs NO_NEWS 1.60%, diff +0.56pp, SE 0.71pp, z=0.79, p~0.43) differs '
    'significantly between arms. Both comparisons are LOW-POWERED (b2 itself is indistinguishable from 0 in '
    "both arms; the copying rate is based on only 12-15 events per arm), so this is best read as 'no evidence "
    "of a difference', not 'confirmed no difference'. At face value it is consistent with the project's "
    'established finding that price-tool salience operates largely independently of whether news is also in '
    'context -- the literal-copy failure mode shows up at a similar (small) rate whether or not news competes '
    'for attention.'
)
STEP5_PROP_NOTE = (
    "two-proportion z-test on the 'looks-copied' (within 15% of ann_vol_20d_pct) rate; small k makes this "
    'low-powered.'
)
PRIMARY_ARMS = ['FULL (label FULL, k=0..3)', 'NO_NEWS (k=0..3)']
LIMITATIONS = [
    'The grounding_20261012/A_main corpus could not be used at all for this mechanism (0/2000 sessions '
    'call get_volatility_stats); the salience-copying question remains untested in that price-grounded '
    'setting.',
    'q3news_S1 cross-check N is small (155 FULL / 139 NO_NEWS) because most sessions in that corpus never '
    'call get_volatility_stats; its regression coefficients are noisy (wide SEs) and should be read as '
    'directionally consistent with newsagent, not as independent confirmation at comparable precision.',
    "The 'looks-copied' group size (12-27 sessions depending on split) is too small to further stratify "
    'by ticker, volatility regime, or k without very wide uncertainty; this is reported as an open '
    'question, not resolved here.',
    "Model 2's b1 estimate is unstable across corpora (0.57-0.62 in newsagent vs 0.06-0.40 in q3news, "
    "overlapping confidence given q3news's wide SE of ~0.85) -- NOT claimed as a cross-model finding, "
    'just noted.',
    'This analysis treats each (day_id, k) rollout as an independent observation for OLS/SE purposes; '
    'days contribute up to 4 correlated rollouts (same ticker/day, different sampling draws), so '
    'classical SEs here are a lower bound on the true SE under day-level clustering. Reported both '
    'classical and HC1-robust SEs; neither corrects for within-day clustering specifically. This does not '
    'change the sign of any headline conclusion (b2~0 either way) but means the step-3 group-size CIs '
    'would widen somewhat under day clustering.',
]

EXAMPLES = [
    {
        'kind': 'a_anchoring_on_annualised',
        'day_id': 'V_2026-06-01',
        'ticker': 'V',
        'day': '2026-06-01',
        'model': 'Qwen3.5-9B',
        'arm': 'FULL',
        'k': 3,
        'note': (
            "Model names the figure 'annualized' (get_volatility_stats ann_vol_20d_pct=16.4) and ~20 lines "
            "later calls it 'approximately 16% annually', then submits expected_vol_pct=16.4 -- the exact "
            'annualised number -- as the 5-day forecast. Rational 5-day sigma for this day was 3.37%; '
            'realised 5-day vol (panel) was 3.74%.'
        ),
        'quotes': [
            '**Volatility**: 16.4% annualized (20-day), regime "low", recent move was 1.11%',
            'Volatility remains subdued at approximately 16% annually.',
        ],
    },
    {
        'kind': 'a_anchoring_on_annualised',
        'day_id': 'HAL_2026-03-20',
        'ticker': 'HAL',
        'day': '2026-03-20',
        'model': 'Qwen3.5-9B',
        'arm': 'FULL',
        'k': 1,
        'note': (
            "Model reads 'Recent volatility is elevated (33.5-36.5% annualized)' from the tool output, "
            "restates it as 'elevated volatility in the 30% range' right before the forecast, and submits "
            'expected_vol_pct=30.0 -- close to ann_vol_20d_pct=30.1, not to a correctly-scaled 5-day figure. '
            'Rational 5-day sigma was 4.67%; realised 5-day vol (panel) was 5.34%.'
        ),
        'quotes': [
            'Recent volatility is elevated (33.5-36.5% annualized), but regime is "normal"',
            'My forecast anticipates modest gains around 0.8% with elevated volatility in the 30% range, '
            "reflecting the stock's current dynamic price environment.",
        ],
    },
    {
        'kind': 'a_anchoring_paired_same_day_k3',
        'day_id': 'HWM_2026-03-27',
        'ticker': 'HWM',
        'day': '2026-03-27',
        'model': 'Qwen3.5-9B',
        'arm': 'FULL',
        'k': 3,
        'note': (
            'Same ticker/day as the k=1 rollout below (HWM_2026-03-27), where get_volatility_stats reported '
            "'Volatility: 31-34% annualized, normal regime'. This rollout (k=3) anchors on that annualised "
            'band and submits expected_vol_pct=27.0 (looks-copied: within 15% of ann_vol_20d_pct=31.3). '
            'Rational 5-day sigma=5.62%; realised 5-day vol=6.24%.'
        ),
        'quotes': [
            'I anticipate volatility between 25-30%, suggesting cautious optimism about near-term price '
            'dynamics.',
        ],
    },
    {
        'kind': 'c_positive_contrast_correct_conversion',
        'day_id': 'BAC_2026-03-17',
        'ticker': 'BAC',
        'day': '2026-03-17',
        'model': 'Qwen3.5-9B',
        'arm': 'FULL',
        'k': 1,
        'note': (
            'Model explicitly de-annualises ann_vol_20d_pct=28.4 with the sqrt(time) rule '
            '(28.4/sqrt(252)=1.77%/day, *sqrt(5)=3.95%) and submits expected_vol_pct=4.0, matching its own '
            'correct arithmetic almost exactly.'
        ),
        'quotes': [
            'expected_vol_pct: Volatility is high at 28.4% annualized, so 5-day vol would be roughly sqrt(5) '
            '* daily vol. Daily vol ≈ 28.4%/sqrt(252) ≈ 1.77%. 5-day vol ≈ 1.77% * sqrt(5) ≈ 3.95%',
        ],
    },
    {
        'kind': 'c_positive_contrast_paired_same_day_k1',
        'day_id': 'HWM_2026-03-27',
        'ticker': 'HWM',
        'day': '2026-03-27',
        'model': 'Qwen3.5-9B',
        'arm': 'FULL',
        'k': 1,
        'note': (
            'Same ticker/day as the k=3 rollout above; this rollout (k=1) correctly applies the sqrt(5) '
            'scaling to the same 31-34% annualised reading and submits expected_vol_pct=13.0 (within the '
            '12-15% it computed). Shows the literal-copy failure is a per-rollout sampling event, not a fixed '
            'property of the ticker/day.'
        ),
        'quotes': [
            'expected_vol_pct: With 31-34% annualized volatility, 5-day vol is roughly sqrt(5) times daily, '
            'or about 12-15% one-standard-deviation',
        ],
    },
    {
        'kind': 'b_bonus_trace_answer_mismatch',
        'day_id': 'MSCI_2026-06-11',
        'ticker': 'MSCI',
        'day': '2026-06-11',
        'model': 'Qwen3.5-9B',
        'arm': 'FULL',
        'k': 1,
        'note': (
            'First pass mis-derives daily vol (uses sqrt(1/20) instead of sqrt(1/252)), reaches 14.3% for the '
            '5-day figure and rejects it as implausible. Second pass restates the metric definition correctly '
            "and redoes the conversion properly, landing on 4.07% -- yet two sentences later writes 'let me "
            "estimate expected_vol_pct around 6-8% to be conservative' and finally submits "
            'expected_vol_pct=6.5, ~60% above its own correctly-computed number. Trace (4.07%) and submitted '
            'answer (6.5%) do not match.'
        ),
        'quotes': [
            'Wait, expected_vol_pct is the one-standard-deviation size of the 5-day return in percent. Given '
            'annualized vol of ~28.9% over 20 days, daily vol would be ~sqrt(1/20)*28.9% = ~6.4% per day. '
            'Over 5 days, volatility accumulates as sqrt(5)*6.4% ≈ 14.3%. But that seems high.',
            'Actually, the expected_vol_pct parameter is "one-standard-deviation size of the 5-day return, '
            'percent (not annualised, not daily)". So if daily return has std dev of X%, 5-day return would '
            'have std dev of X% * sqrt(5).\n\nGiven 20-day annualized vol of 28.9%, daily vol ≈ 28.9% / '
            'sqrt(252) ≈ 1.82% per day. Over 5 days: 1.82% * sqrt(5) ≈ 4.07%.',
        ],
    },
]

# the numbers each example note quotes, at the precision shown there; salience.build_examples checks them against the
# computed session record (ann_vol_20d_pct, expected_vol_pct: 1 decimal; rational sigma and realised rv5: 2 decimals)
EXAMPLE_EXPECT = {
    ("V_2026-06-01", 3): {"ann_vol_20d_pct": "16.4", "expected_vol_pct": "16.4", "rational_sigma5_pct": "3.37",
                          "rv5_realised_pct": "3.74"},
    ("HAL_2026-03-20", 1): {"ann_vol_20d_pct": "30.1", "expected_vol_pct": "30.0", "rational_sigma5_pct": "4.67",
                            "rv5_realised_pct": "5.34"},
    ("HWM_2026-03-27", 3): {"ann_vol_20d_pct": "31.3", "expected_vol_pct": "27.0", "rational_sigma5_pct": "5.62",
                            "rv5_realised_pct": "6.24"},
    ("BAC_2026-03-17", 1): {"ann_vol_20d_pct": "28.4", "expected_vol_pct": "4.0"},
    ("HWM_2026-03-27", 1): {"expected_vol_pct": "13.0"},
    ("MSCI_2026-06-11", 1): {"expected_vol_pct": "6.5"},
}
