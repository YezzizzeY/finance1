| model / framework | usable | ORIG run-to-run abs diff ln(vol) (pairs) | NOLABEL d ln(vol) | UNIT5D d ln(vol) | PLACEBO d ln(vol) | ORIG run-to-run abs diff return, pp | NOLABEL d return | UNIT5D d return | PLACEBO d return | pasted annualised, strict (broad) | mean tool calls / commands | computed a vol in code | abs log error vs realised 5d vol (bias) [SE over days] |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3-8B / harness | 30 | 0.64 (6) | +0.12 (6) | -0.47 (6) | -0.43 (6) | 2.02 | +1.93* (6) | -0.96 (6) | +0.96 (6) | 4/30 (4) | 1.0 | - | 0.67 (+0.38) [0.22] |
| Qwen3-8B / Codex CLI | 26 | 0.35 (4) | -0.41* (6) | -0.29* (6) | -0.46* (4) | 1.62 | +0.23 (6) | +0.34 (6) | +0.96 (4) | 1/26 (1) | 2.2 | 0/26 | 0.55 (+0.08) [0.11] |
| Qwen3.5-9B / harness | 30 | 0.40 (6) | +0.63* (6) | -0.19 (6) | +0.12 (6) | 1.33 | +2.78* (6) | -0.22 (6) | -0.60 (6) | 2/30 (5) | 1.1 | - | 0.65 (+0.36) [0.16] |
| Qwen3.5-9B / Codex CLI | 29 | 0.70 (6) | -0.40 (6) | -0.29 (6) | -0.18 (5) | 3.57 | -0.53 (6) | -0.69 (6) | +0.04 (5) | 2/29 (2) | 10.0 | 25/29 | 0.54 (+0.19) [0.10] |
| Qwen3.8-27B / harness | 30 | 0.28 (6) | +0.13 (6) | +0.15 (6) | +0.11 (6) | 0.98 | +0.53 (6) | +0.23 (6) | +0.33 (6) | 0/30 (0) | 9.1 | - | 0.40 (+0.03) [0.08] |
| Qwen3.8-27B / Codex CLI | 28 | 0.09 (6) | +0.10* (5) | +0.05 (6) | +0.03 (5) | 1.18 | +0.30 (5) | +0.61 (6) | -0.13 (5) | 0/28 (0) | 5.9 | 23/28 | 0.41 (+0.07) [0.12] |
| DeepSeek / harness | 30 | 0.14 (6) | -0.04 (6) | +0.02 (6) | +0.13* (6) | 1.02 | -0.33 (6) | +0.07 (6) | -0.36 (6) | 0/30 (0) | 12.1 | - | 0.40 (+0.13) [0.13] |
| DeepSeek / Codex CLI | 23 | 0.14 (4) | +0.03 (4) | -0.10 (3) | +0.10 (5) | 0.85 | +0.45 (4) | +0.33 (3) | +0.24 (5) | 0/23 (0) | 8.1 | 23/23 | 0.39 (+0.03) [0.11] |
| Kimi K3 / harness | 30 | 0.16 (6) | +0.08 (6) | -0.14* (6) | +0.08 (6) | 0.72 | -0.26 (6) | +0.23 (6) | -0.34 (6) | 0/30 (0) | 3.7 | - | 0.40 (+0.17) [0.15] |
| Kimi K3 / Codex CLI | 30 | 0.09 (6) | -0.01 (6) | -0.03 (6) | +0.01 (6) | 0.67 | +0.18 (6) | -0.40 (6) | +0.35 (6) | 0/30 (0) | 4.6 | 19/30 | 0.40 (+0.09) [0.12] |
| baseline: readings ann_vol_20d x sqrt(5/252) | 6 days | | | | | | | | | | | | 0.48 (+0.03) |
| baseline: S1 rational prior sigma5 | 6 days | | | | | | | | | | | | 0.43 (+0.10) |

Sensitivity A: the 7 runs flagged only for Codex's bundled ripgrep re-admitted (rows that change).

| model / framework | usable | ORIG noise ln(vol) | NOLABEL | UNIT5D | PLACEBO | ORIG noise return | NOLABEL | UNIT5D | PLACEBO |
|---|---|---|---|---|---|---|---|---|---|
| Qwen3-8B / Codex CLI | 27 | 0.36 (5) | -0.37* (6) | -0.26 (6) | -0.46* (4) | 2.30 | +0.64 (6) | +0.76 (6) | +0.96 (4) |
| DeepSeek / Codex CLI | 29 | 0.13 (6) | +0.02 (6) | -0.10 (5) | +0.07 (6) | 0.71 | +0.48 (6) | +0.21 (5) | +0.26 (6) |

Sensitivity B: runs whose 5-day vol is on the annualised scale (broad rule) dropped before the shifts are computed.

| model / framework | runs kept | ORIG noise ln(vol) | NOLABEL | UNIT5D | PLACEBO |
|---|---|---|---|---|---|
| Qwen3-8B / harness | 26 | 0.24 (4) | -0.18 (4) | -0.23* (6) | -0.20* (6) |
| Qwen3-8B / Codex CLI | 25 | 0.35 (4) | -0.03 (5) | +0.01 (5) | +0.05 (3) |
| Qwen3.5-9B / harness | 25 | 0.35 (5) | -0.04 (3) | -0.13 (6) | -0.04 (5) |
| Qwen3.5-9B / Codex CLI | 27 | 0.58 (4) | -0.24 (6) | -0.14 (6) | -0.10 (5) |
| Qwen3.8-27B / harness | 30 | 0.28 (6) | +0.13 (6) | +0.15 (6) | +0.11 (6) |
| Qwen3.8-27B / Codex CLI | 28 | 0.09 (6) | +0.10* (5) | +0.05 (6) | +0.03 (5) |
| DeepSeek / harness | 30 | 0.14 (6) | -0.04 (6) | +0.02 (6) | +0.13* (6) |
| DeepSeek / Codex CLI | 23 | 0.14 (4) | +0.03 (4) | -0.10 (3) | +0.10 (5) |
| Kimi K3 / harness | 30 | 0.16 (6) | +0.08 (6) | -0.14* (6) | +0.08 (6) |
| Kimi K3 / Codex CLI | 30 | 0.09 (6) | -0.01 (6) | -0.03 (6) | +0.01 (6) |

Pasted annualised figures by arm, strict (broad), out of usable runs of that arm.

| model / framework | ORIG | NOLABEL | UNIT5D | PLACEBO |
|---|---|---|---|---|
| Qwen3-8B / harness | 2 (2) of 12 | 2 (2) of 6 | 0 (0) of 6 | 0 (0) of 6 |
| Qwen3-8B / Codex CLI | 1 (1) of 10 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 4 |
| Qwen3.5-9B / harness | 0 (1) of 12 | 2 (3) of 6 | 0 (0) of 6 | 0 (1) of 6 |
| Qwen3.5-9B / Codex CLI | 2 (2) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 5 |
| Qwen3.8-27B / harness | 0 (0) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 6 |
| Qwen3.8-27B / Codex CLI | 0 (0) of 12 | 0 (0) of 5 | 0 (0) of 6 | 0 (0) of 5 |
| DeepSeek / harness | 0 (0) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 6 |
| DeepSeek / Codex CLI | 0 (0) of 9 | 0 (0) of 5 | 0 (0) of 4 | 0 (0) of 5 |
| Kimi K3 / harness | 0 (0) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 6 |
| Kimi K3 / Codex CLI | 0 (0) of 12 | 0 (0) of 6 | 0 (0) of 6 | 0 (0) of 6 |

Days: realised outcome (never shown to any agent) and the two baselines.

| day | type | realised 5d vol % | realised 5d return % | ann_vol_20d | 20d in 5-day units | S1 prior sigma5 |
|---|---|---|---|---|---|---|
| MCHP_2026-08-07 | big | 5.33 | -6.52 | 74.1 | 10.44 | 8.72 |
| HOOD_2026-04-14 | big | 12.15 | +9.28 | 62.7 | 8.83 | 10.19 |
| CRWD_2026-08-27 | big | 12.74 | -5.70 | 81.2 | 11.44 | 9.03 |
| VST_2026-05-06 | ordinary | 7.34 | -9.91 | 39.4 | 5.55 | 5.79 |
| CB_2026-04-22 | ordinary | 3.82 | +0.10 | 14.6 | 2.06 | 3.02 |
| MRK_2026-05-07 | ordinary | 1.60 | +0.99 | 26.7 | 3.76 | 4.67 |
