"""Turn raw_features.parquet (one row per ticker x day, one column per (tool, field)) into the pairwise
correlation matrix and the summary tables tool_redundancy/README.md describes. Pure pandas/numpy, no randomness,
deterministic given the same input file.

    finagent evidence-tools analyze [--out DIR]

Ported from 1_overreaction/repro/evidence_relations/tool_redundancy_analyze.py (unchanged math).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from finagent.evidence_relations.tool_redundancy.generate import OUT_DIR

MIN_N_FOR_SUMMARY = 1000     # pairs need at least this many joint non-null observations to enter the
                             # top-correlated / near-independent tables (not the full matrix, which keeps every
                             # pair with n >= 2)
CLUSTER_THRESHOLD = 0.9      # |pearson r| at/above this puts two columns in the same cluster
NEAR_INDEPENDENT_THRESHOLD = 0.2   # |r| below this, in BOTH pearson and spearman


def tool_of(col: str) -> str:
    return col.split(".", 1)[0]


class UnionFind:
    def __init__(self, items):
        self.parent = {x: x for x in items}

    def find(self, x):
        while self.parent[x] != x:
            x = self.parent[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[ra] = rb


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="finagent evidence-tools analyze")
    ap.add_argument("--out", type=Path, default=OUT_DIR)
    a = ap.parse_args(argv)
    out_dir = a.out

    df = pd.read_parquet(out_dir / "raw_features.parquet")
    meta_cols = ["ticker", "date"]
    numeric_cols = [c for c in df.columns if c not in meta_cols]

    # ---- drop degenerate (zero- or near-zero-variance, or all-null) columns ----
    dropped = []
    kept = []
    for c in numeric_cols:
        s = df[c]
        n_valid = int(s.notna().sum())
        std = float(s.std(skipna=True)) if n_valid > 1 else 0.0
        if n_valid < 2 or not np.isfinite(std) or std < 1e-12:
            dropped.append({"column": c, "tool": tool_of(c), "n_valid": n_valid,
                            "std": std if np.isfinite(std) else None,
                            "reason": "all-null" if n_valid < 2 else "zero-variance (constant value every call)"})
        else:
            kept.append(c)
    kept = sorted(kept)
    dropped_df = pd.DataFrame(dropped).sort_values(["tool", "column"]).reset_index(drop=True)
    dropped_df.to_csv(out_dir / "dropped_degenerate_columns.csv", index=False)

    sub = df[kept].astype(float)

    # ---- pooled correlation matrices ----
    pearson = sub.corr(method="pearson", min_periods=2)
    spearman = sub.corr(method="spearman", min_periods=2)
    notna = sub.notna().astype(int)
    joint_n = notna.T.dot(notna)   # n[i,j] = count of rows where both column i and j are non-null

    pairs = []
    for i, a_col in enumerate(kept):
        for b_col in kept[i + 1:]:
            n = int(joint_n.loc[a_col, b_col])
            pr = float(pearson.loc[a_col, b_col]) if n >= 2 else None
            sr = float(spearman.loc[a_col, b_col]) if n >= 2 else None
            pairs.append({
                "col_a": a_col, "col_b": b_col, "tool_a": tool_of(a_col), "tool_b": tool_of(b_col),
                "field_a": a_col.split(".", 1)[1], "field_b": b_col.split(".", 1)[1],
                "same_tool": tool_of(a_col) == tool_of(b_col), "n": n,
                "pearson_r": round(pr, 4) if pr is not None else None,
                "spearman_r": round(sr, 4) if sr is not None else None,
            })
    pair_df = pd.DataFrame(pairs).sort_values(["col_a", "col_b"]).reset_index(drop=True)
    pair_df.to_parquet(out_dir / "matrix.parquet", index=False)
    pearson.round(4).to_csv(out_dir / "pearson_matrix.csv")
    spearman.round(4).to_csv(out_dir / "spearman_matrix.csv")

    # ---- cross-tool summary tables (the ask: which TOOLS are redundant with each other) ----
    cross = pair_df[~pair_df["same_tool"] & pair_df["pearson_r"].notna() & (pair_df["n"] >= MIN_N_FOR_SUMMARY)].copy()
    cross["abs_pearson_r"] = cross["pearson_r"].abs()

    top20 = cross.sort_values("abs_pearson_r", ascending=False).head(20).drop(columns=["abs_pearson_r"])
    top20.to_csv(out_dir / "top_correlated_pairs.csv", index=False)

    near_indep = cross[(cross["pearson_r"].abs() < NEAR_INDEPENDENT_THRESHOLD) &
                        (cross["spearman_r"].abs() < NEAR_INDEPENDENT_THRESHOLD)].copy()
    near_indep = near_indep.sort_values(["abs_pearson_r", "n"], ascending=[True, False]).drop(columns=["abs_pearson_r"])
    near_indep.to_csv(out_dir / "near_independent_pairs.csv", index=False)

    # ---- clustering: connected components at |pearson r| >= CLUSTER_THRESHOLD, any pair (incl. same-tool) ----
    uf = UnionFind(kept)
    n_edges = 0
    for i, a_col in enumerate(kept):
        for b_col in kept[i + 1:]:
            n = int(joint_n.loc[a_col, b_col])
            if n >= 2:
                r = pearson.loc[a_col, b_col]
                if pd.notna(r) and abs(r) >= CLUSTER_THRESHOLD:
                    uf.union(a_col, b_col)
                    n_edges += 1
    groups: dict[str, list[str]] = {}
    for c in kept:
        groups.setdefault(uf.find(c), []).append(c)
    clusters = sorted((sorted(members) for members in groups.values() if len(members) > 1),
                       key=lambda m: (-len(m), m[0]))
    cluster_rows = [{"cluster_id": i, "size": len(members), "members": ";".join(members)}
                     for i, members in enumerate(clusters)]
    pd.DataFrame(cluster_rows).to_csv(out_dir / "clusters.csv", index=False)

    # ---- per-ticker correlation, for the kept cross-tool pairs that matter (top-correlated + near-independent
    #      candidates), "also per-ticker if cheap" ----
    watch_cols = sorted(set(top20["col_a"]) | set(top20["col_b"]) | set(near_indep["col_a"]) | set(near_indep["col_b"]))
    per_ticker_rows = []
    for tk, g in df.groupby("ticker", sort=True):
        gsub = g[watch_cols].astype(float)
        pear_t = gsub.corr(method="pearson", min_periods=2)
        spear_t = gsub.corr(method="spearman", min_periods=2)
        notna_t = gsub.notna().astype(int)
        joint_t = notna_t.T.dot(notna_t)
        for i, a_col in enumerate(watch_cols):
            for b_col in watch_cols[i + 1:]:
                n = int(joint_t.loc[a_col, b_col])
                if n < 2:
                    continue
                per_ticker_rows.append({
                    "ticker": tk, "col_a": a_col, "col_b": b_col, "n": n,
                    "pearson_r": round(float(pear_t.loc[a_col, b_col]), 4) if pd.notna(pear_t.loc[a_col, b_col]) else None,
                    "spearman_r": round(float(spear_t.loc[a_col, b_col]), 4) if pd.notna(spear_t.loc[a_col, b_col]) else None,
                })
    pd.DataFrame(per_ticker_rows).sort_values(["col_a", "col_b", "ticker"]).reset_index(drop=True).to_parquet(
        out_dir / "per_ticker_matrix.parquet", index=False)

    # ---- tool-level summary: for every pair of DIFFERENT tools, how many of their field x field pairs are
    #      near-duplicate (|pearson r|>=0.9) vs near-independent (|r|<0.2 in both) vs in between, plus the single
    #      strongest |r| between them ----
    tool_pair_rows = []
    for (ta, tb), g in cross.groupby(["tool_a", "tool_b"], sort=True):
        n_fields = len(g)
        n_redundant = int((g["pearson_r"].abs() >= CLUSTER_THRESHOLD).sum())
        n_indep = int(((g["pearson_r"].abs() < NEAR_INDEPENDENT_THRESHOLD) &
                        (g["spearman_r"].abs() < NEAR_INDEPENDENT_THRESHOLD)).sum())
        best = g.loc[g["abs_pearson_r"].idxmax()]
        tool_pair_rows.append({
            "tool_a": ta, "tool_b": tb, "n_field_pairs": n_fields,
            "n_redundant_ge_0_9": n_redundant, "n_near_independent_lt_0_2": n_indep,
            "max_abs_pearson_r": round(float(best["abs_pearson_r"]), 4),
            "max_r_field_a": best["field_a"], "max_r_field_b": best["field_b"],
            "verdict": ("redundant" if n_redundant == n_fields else
                        "independent" if n_indep == n_fields else "mixed"),
        })
    tool_pair_df = pd.DataFrame(tool_pair_rows).sort_values(
        ["verdict", "max_abs_pearson_r"], ascending=[True, False]).reset_index(drop=True)
    tool_pair_df.to_csv(out_dir / "tool_pair_summary.csv", index=False)

    summary = {
        "n_rows": int(len(df)), "n_tickers": int(df["ticker"].nunique()),
        "n_numeric_cols_total": len(numeric_cols), "n_cols_kept": len(kept), "n_cols_dropped": len(dropped),
        "n_pairs_total": int(len(pair_df)), "n_pairs_cross_tool_with_min_n": int(len(cross)),
        "n_clusters_ge2": len(clusters), "cluster_edge_count_ge_0_9": n_edges,
        "n_top20": int(len(top20)), "n_near_independent": int(len(near_indep)),
        "n_tool_pairs": int(len(tool_pair_df)),
        "n_tool_pairs_fully_redundant": int((tool_pair_df["verdict"] == "redundant").sum()),
        "n_tool_pairs_fully_independent": int((tool_pair_df["verdict"] == "independent").sum()),
        "n_tool_pairs_mixed": int((tool_pair_df["verdict"] == "mixed").sum()),
        "min_n_for_summary": MIN_N_FOR_SUMMARY, "cluster_threshold": CLUSTER_THRESHOLD,
        "near_independent_threshold": NEAR_INDEPENDENT_THRESHOLD,
    }
    (out_dir / "_analyze_meta.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
