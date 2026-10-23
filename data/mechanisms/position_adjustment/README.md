# Inputs of the position-adjustment analysis

Byte-identical copies (`cp -a`) of files in the research workspace (`1_overreaction`); the source paths below are
relative to that workspace. Read by `src/finagent/mechanisms/position_adjustment.py`, which writes
`results/mechanisms/position_adjustment/data.json`.

| file | source in the research workspace | what it is | sha256 |
|---|---|---|---|
| `base5d_val_calm.json` | `results/base5d_val_calm.json` | BASE tool-agent trajectories, val_calm window (60 trajectories) | `697228552aa5dc1721131ada509dab8b3d3761da2fc8ac7298ede8fe891aa7f6` |
| `base5d_val_stress.json` | `results/base5d_val_stress.json` | BASE trajectories, val_stress window (60) | `e8812ac5039dc81cc271560af7fc2b9020ac997f305cb3ac3ca0e074f2232998` |
| `base5d_test_calm.json` | `results/base5d_test_calm.json` | BASE trajectories, test_calm window (80) | `4c1176ba74c54e158785803f034cf9f7d8d133e1eb01dde04dd6c9d575ee0e8c` |
| `base5d_test_crash.json` | `results/base5d_test_crash.json` | BASE trajectories, test_crash window (80) | `451b6cb65467abe00ea9f44a76b09f8c5a1aa2798f9af68617a62cca77f4d276` |
| `base5d_test_bear.json` | `results/base5d_test_bear.json` | BASE trajectories, test_bear window (80) | `e3475f8ce135d8eb56d5f09ef7af75baed29feda44b0a08ed3998e037854b86d` |
| `BASE_crash_R2.json` | `results/newmethods_20261011/eval/tool/BASE/crash.json` | BASE replicate of the test_crash window (80) | `1a38ed934a273d71705d56cabee595800ebd58244e2f76db97fd252801369398` |
| `events_all.parquet` | `results/rcf_20261011/data/events_all.parquet` | rational benchmark on news-event days (m, lsig, u; 15,134 rows) | `317f6aaa8da6ef55ad19c669cc7c7c2c93c74ebd26da59f8b15c5cc5d343523b` |
| `nonevent_days.parquet` | `results/rcf_20261011/data/nonevent_days.parquet` | rational benchmark on no-news days (6,035 rows) | `83c753d3686af35a1374556367e02afa40a33d697d105804ba97291f8feee11d` |

Check: `sha256sum -c` against the column above, or `finagent mech-position --check` for the
whole analysis.
