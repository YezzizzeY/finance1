"""results/evidence_relations/reference_models: three deterministic, non-LLM reference forecasters run over
data/evidence_relations/synthetic's test split, to give a concrete, quantified picture of what three qualitatively
different ways of combining two noisy signals look like as *behaviour*, before any real model is tested on the
same benchmark. Ported from 1_overreaction/repro/evidence_relations/reference_models/run_models.py and
its three model files (bayes_optimal.py, counting_naive.py, salience_follower.py), merged into this one module.

    bayes_optimal       the "correct" archetype: imports the exact closed-form formulas from
                         evidence_relations/bayes.py (DESIGN.md S3) -- the same formulas the dataset's own
                         bayes_optimal_delta1 / bayes_optimal_posterior_var columns were built from
    counting_naive       theta_hat = (s1+s2)/2 -- averages, not sums (see predict_counting_naive's docstring
                         for why sum would be a different, strictly worse failure mode)
    salience_follower     theta_hat = s1 if |s1|>=|s2| else s2 -- follows whichever signal's number is larger
                         in magnitude

All three predict the full one-step change delta1_hat = (rho-1)*x_t + theta_hat, the same AR-term
decomposition the dataset's own bayes_optimal_delta1 column uses, so every MAE number isolates only how the
three archetypes combine s1/s2 -- the common (rho-1)*x_t term cancels identically out of every model's error
against the true delta1 = x_next - x_t, so error = theta_hat - true_eps_next exactly, for all three models.

No randomness anywhere: all three forecasters are deterministic functions of columns already fixed by
evidence_relations/synthetic's generator, so there is no seed to fix -- reproducibility means byte-identical
output on every rerun (pure functions, fixed-order pandas groupbys on a fixed-order input, fixed-precision
rounding on write), proved by running this twice and diffing.

    finagent evidence-reference-models                 read data/evidence_relations/synthetic/test.jsonl.xz (the
                                                         shipped archive), run the three forecasters, write
                                                         results.csv + build_checks.json + MANIFEST.sha256 to
                                                         results/evidence_relations/reference_models/
    finagent evidence-reference-models --regenerate     read the test split from a fresh regeneration of the
                                                         generator instead of the shipped archive (the two must
                                                         agree -- see evidence-synthetic --check)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import lzma
from pathlib import Path

import numpy as np
import pandas as pd

from finagent.evidence_relations import ROOT as EVIDENCE_ROOT
from finagent.evidence_relations import RESULTS_ROOT
from finagent.evidence_relations import bayes as B
from finagent.evidence_relations import synthetic as S

SIGMA = S.SIGMA  # same sigma as data/evidence_relations/synthetic DESIGN.md S1, S3.1

# Columns needed from each row of test.jsonl. `history` and `prompt_variants` (the bulk of each line's bytes)
# are deliberately never materialised.
FIELDS = ["id", "variant", "rho", "c", "tau_setting", "tau1", "tau2", "x_t", "x_next", "true_eps_next", "s1",
         "s2", "weight_s1", "weight_s2", "bayes_optimal_delta1", "stale_round", "contradiction_flip_applied"]

MODEL_NAMES = ["bayes_optimal", "counting_naive", "salience_follower"]
REPORT_DP = 4  # fixed decimal places for every number in results.csv


# ================================================================================================== the three archetypes
def predict_bayes_optimal(df: pd.DataFrame) -> np.ndarray:
    """theta_hat = E[eps_{t+1} | signals shown]: one_signal (stale rounds) or two_signal_general (otherwise,
    which is correct, not an approximation, for non-stale rows -- it algebraically reduces to the symmetric
    formula when tau1==tau2, true of every base/stale row; there is only one real formula, DESIGN.md S3.2/S3.3
    is a documented special case of it)."""
    s1 = df["s1"].to_numpy(dtype=np.float64)
    s2 = df["s2"].to_numpy(dtype=np.float64)
    tau1 = df["tau1"].to_numpy(dtype=np.float64)
    tau2 = df["tau2"].to_numpy(dtype=np.float64)
    c = df["c"].to_numpy(dtype=np.float64)
    stale = df["stale_round"].to_numpy(dtype=bool)

    theta_hat = np.empty(len(df), dtype=np.float64)
    fresh = ~stale
    if fresh.any():
        mean, _var, _w1, _w2 = B.two_signal_general(s1[fresh], s2[fresh], tau1[fresh], tau2[fresh], c[fresh], SIGMA)
        theta_hat[fresh] = mean
    if stale.any():
        mean, _var = B.one_signal(s1[stale], tau1[stale], SIGMA)
        theta_hat[stale] = mean
    return theta_hat


def predict_counting_naive(df: pd.DataFrame) -> np.ndarray:
    """theta_hat = (s1+s2)/2 -- averaged, not summed. s1 and s2 are both noisy estimates of the *same*
    quantity theta (S1=theta+u1, S2=theta+u2), not two additive pieces of a total: summing would centre the
    estimate near 2*theta, a different (and strictly worse-behaved) failure mode than the one this archetype
    is meant to probe. Averaging keeps theta_hat centred on theta (matching that bayes_optimal's w1+w2 <= 1,
    never ~2) while still being "count both signals equally, every time" -- never reads tau1, tau2, c or
    stale_round, which is the point: it keeps "counting" a signal that is increasingly a noisy copy of the
    other one as if it were fresh, independent evidence."""
    s1 = df["s1"].to_numpy(dtype=np.float64)
    s2 = df["s2"].to_numpy(dtype=np.float64)
    return (s1 + s2) / 2.0


def predict_salience_follower(df: pd.DataFrame) -> np.ndarray:
    """theta_hat = s1 if |s1|>=|s2| else s2 -- the "go with whichever number grabbed your attention"
    archetype; never reads tau1, tau2, c or stale_round. Tie-break (|s1|==|s2| exactly): Signal A wins, an
    arbitrary but fixed rule. s1/s2 are already rounded to 2 decimals, so exact ties do occur in practice (see
    build_checks.json's salience_tie_count)."""
    s1 = df["s1"].to_numpy(dtype=np.float64)
    s2 = df["s2"].to_numpy(dtype=np.float64)
    return np.where(np.abs(s1) >= np.abs(s2), s1, s2)


PREDICT = {"bayes_optimal": predict_bayes_optimal, "counting_naive": predict_counting_naive,
          "salience_follower": predict_salience_follower}


def predict_delta1(name: str, df: pd.DataFrame) -> np.ndarray:
    """Full one-step-ahead change forecast: (rho-1)*x_t + theta_hat -- the same AR term every archetype adds,
    so they differ only in how they combine s1/s2, not in how they use the history/rho."""
    theta_hat = PREDICT[name](df)
    rho = df["rho"].to_numpy(dtype=np.float64)
    x_t = df["x_t"].to_numpy(dtype=np.float64)
    return (rho - 1.0) * x_t + theta_hat


# ================================================================================================== test-set loading
def load_test_set_from_jsonl_bytes(data: bytes) -> pd.DataFrame:
    rows = []
    for line in data.decode("utf-8").splitlines():
        if not line:
            continue
        full = json.loads(line)
        rows.append({k: full[k] for k in FIELDS})
    df = pd.DataFrame(rows)
    df["stale_round"] = df["stale_round"].astype(bool)
    return df


def load_test_set(synthetic_dir: Path, regenerate: bool) -> pd.DataFrame:
    if regenerate:
        jsonl_bytes, _xz_bytes, _summary = S.build(write_to=None)
        return load_test_set_from_jsonl_bytes(jsonl_bytes["test"])
    path = synthetic_dir / "test.jsonl.xz"
    if not path.is_file():
        raise SystemExit(f"{path} is missing; run `finagent evidence-synthetic` first, or pass --regenerate")
    return load_test_set_from_jsonl_bytes(lzma.decompress(path.read_bytes()))


# ================================================================================================== checks and table
def add_predictions(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    true_delta1 = df["x_next"].to_numpy(dtype=np.float64) - df["x_t"].to_numpy(dtype=np.float64)
    df["true_delta1"] = true_delta1
    for name in MODEL_NAMES:
        pred = predict_delta1(name, df)
        df[f"pred_{name}"] = pred
        df[f"error_{name}"] = pred - true_delta1
        df[f"abs_error_{name}"] = np.abs(pred - true_delta1)
    return df


def cross_check_bayes_optimal(df: pd.DataFrame) -> dict:
    """Confirm predict_bayes_optimal reproduces the dataset's own bayes_optimal_delta1 column (built
    independently, from the same formulas, at generation time). Reports both the post-rounding match (what
    lands in results.csv) and the pre-rounding raw difference, since the two can disagree by exactly 0.01 on a
    few rows that sit within floating-point noise of an exact x.xx5 rounding boundary (round-half-to-even can
    pick either neighbour depending on the last float64 bit) -- not a formula discrepancy. The raw difference
    is bounded by 0.005 (DESIGN.md's own stated 2-decimal rounding bound), which is the real confirmation."""
    stored = df["bayes_optimal_delta1"].to_numpy(dtype=np.float64)
    raw = df["pred_bayes_optimal"].to_numpy(dtype=np.float64)
    ours_rounded = np.round(raw, 2)
    diff_rounded = ours_rounded - stored
    diff_raw = raw - stored
    return {"n_rows": int(len(df)), "n_exact_match_after_round2": int(np.sum(diff_rounded == 0.0)),
            "n_mismatch_after_round2": int(np.sum(diff_rounded != 0.0)),
            "max_abs_diff_after_round2": round(float(np.max(np.abs(diff_rounded))), 6),
            "max_abs_diff_before_round2": round(float(np.max(np.abs(diff_raw))), 6),
            "mean_abs_diff_before_round2": round(float(np.mean(np.abs(diff_raw))), 6)}


def tie_count(df: pd.DataFrame) -> int:
    s1 = df["s1"].to_numpy(dtype=np.float64)
    s2 = df["s2"].to_numpy(dtype=np.float64)
    return int(np.sum(np.abs(s1) == np.abs(s2)))


def _stats_block(sub: pd.DataFrame) -> dict:
    out = {"n": int(len(sub))}
    for name in MODEL_NAMES:
        err = sub[f"error_{name}"].to_numpy(dtype=np.float64)
        out[f"mae_{name}"] = float(np.mean(np.abs(err)))
        out[f"bias_{name}"] = float(np.mean(err))
        out[f"rmse_{name}"] = float(np.sqrt(np.mean(err ** 2)))
    return out


def build_results_table(df: pd.DataFrame) -> pd.DataFrame:
    """Tidy long table: one row per (variant, c, tau_setting, stale_round) combination actually present, plus
    pooled rows ('ALL' in the pooled dimension) for the headline comparisons: base variant MAE vs c (pooled
    over tau_setting and rho), base variant by (c, rho) pooled over tau_setting (the rho-invariance check), and
    each variant's overall MAE."""
    records = []
    group_cols = ["variant", "c", "tau_setting", "tau1", "tau2", "stale_round"]
    for key, sub in df.groupby(group_cols, sort=True):
        rec = dict(zip(group_cols, key))
        rec["rho"] = "ALL"
        rec["level"] = "condition"
        rec.update(_stats_block(sub))
        records.append(rec)

    for c_val, sub in df[df["variant"] == "base"].groupby("c", sort=True):
        rec = {"variant": "base", "c": c_val, "tau_setting": "ALL", "tau1": "ALL", "tau2": "ALL",
              "stale_round": "ALL", "rho": "ALL", "level": "base_c_pooled"}
        rec.update(_stats_block(sub))
        records.append(rec)

    for (c_val, rho_val), sub in df[df["variant"] == "base"].groupby(["c", "rho"], sort=True):
        rec = {"variant": "base", "c": c_val, "tau_setting": "ALL", "tau1": "ALL", "tau2": "ALL",
              "stale_round": "ALL", "rho": rho_val, "level": "rho_check"}
        rec.update(_stats_block(sub))
        records.append(rec)

    for variant_val, sub in df.groupby("variant", sort=True):
        rec = {"variant": variant_val, "c": "ALL", "tau_setting": "ALL", "tau1": "ALL", "tau2": "ALL",
              "stale_round": "ALL", "rho": "ALL", "level": "variant_pooled"}
        rec.update(_stats_block(sub))
        records.append(rec)

    out = pd.DataFrame.from_records(records)
    front = ["level", "variant", "c", "tau1", "tau2", "tau_setting", "stale_round", "rho", "n"]
    metric_cols = [c for c in out.columns if c not in front]
    out = out[front + sorted(metric_cols)]
    for col in metric_cols:
        out[col] = out[col].round(REPORT_DP)
    return out


# ================================================================================================== manifest / CLI
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def write_manifest(out_dir: Path) -> None:
    names = sorted(p.name for p in out_dir.iterdir() if p.is_file() and p.name != "MANIFEST.sha256")
    with open(out_dir / "MANIFEST.sha256", "w", encoding="utf-8", newline="\n") as f:
        for name in names:
            f.write(f"{sha256_file(out_dir / name)}  {name}\n")


def run(synthetic_dir: Path, out_dir: Path, regenerate: bool) -> dict:
    df = load_test_set(synthetic_dir, regenerate)
    df = add_predictions(df)
    checks = {"bayes_optimal_cross_check": cross_check_bayes_optimal(df), "salience_tie_count": tie_count(df),
             "n_rows_total": int(len(df)),
             "n_rows_by_variant": {k: int(v) for k, v in df["variant"].value_counts().sort_index().items()}}
    results = build_results_table(df)

    out_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(out_dir / "results.csv", index=False)
    with open(out_dir / "build_checks.json", "w", encoding="utf-8", newline="\n") as f:
        json.dump(checks, f, indent=2, sort_keys=True)
        f.write("\n")
    return checks


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent evidence-reference-models", description="Run bayes_optimal, "
                                 "counting_naive and salience_follower over data/evidence_relations/synthetic's test "
                                 "split and write results.csv + build_checks.json + MANIFEST.sha256.")
    ap.add_argument("--synthetic-dir", type=Path, default=EVIDENCE_ROOT / "synthetic",
                    help="where test.jsonl.xz is read from (default: data/evidence_relations/synthetic/)")
    ap.add_argument("--out", type=Path, default=RESULTS_ROOT / "reference_models",
                    help="target folder (default: results/evidence_relations/reference_models/)")
    ap.add_argument("--regenerate", action="store_true",
                    help="read the test split from a fresh regeneration of the generator instead of the shipped .xz")
    a = ap.parse_args(argv)
    checks = run(a.synthetic_dir, a.out, a.regenerate)
    write_manifest(a.out)
    print(json.dumps(checks, indent=2, sort_keys=True))
    print(f"wrote {a.out / 'results.csv'}, build_checks.json, MANIFEST.sha256")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
