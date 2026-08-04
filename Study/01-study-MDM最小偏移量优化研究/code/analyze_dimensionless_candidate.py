"""Post-analysis for the dimensionless Vector-MLP candidate outputs.

Reads the compact + local outputs written by run_dimensionless_candidate.py and produces
the seed-level pooled J1 (per seed over 5 folds = 45k samples), 3-seed means, per-n J1,
and comparisons against the sealed E3b/E4a/P2 control numbers, for the report.

Usage: python -X utf8 code/analyze_dimensionless_candidate.py
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CODE_DIR = Path(__file__).resolve().parent
STUDY_ROOT = CODE_DIR.parent
sys.path.insert(0, str(CODE_DIR))

CAND = STUDY_ROOT / "artifacts" / "candidate" / "dimensionless_vector_mlp"
LOCAL = CAND / "local_outputs"
E3B = STUDY_ROOT / "artifacts" / "formal" / "E3b_vector_mlp"
E4 = STUDY_ROOT / "artifacts" / "formal" / "E4_robustness"
P2D = STUDY_ROOT / "artifacts" / "formal" / "extended_validation" / "p2_generalization_v2"


def seed_pooled(df_sel):
    """Per-seed pooled J1 (5 folds, 45k samples per seed)."""
    out = {}
    for seed, sub in df_sel.groupby("seed"):
        out[int(seed)] = math.sqrt(sub["true_loss"].mean())
    return out


def pooled_per_n(df_sel):
    per_n = {}
    for nv, sub in df_sel.groupby("n"):
        per_n[int(nv)] = math.sqrt(sub["true_loss"].mean())
    return per_n


def main():
    print("=" * 60)
    print("Dimensionless candidate — seed-level pooled + comparison analysis")
    print("=" * 60)

    main_dim = pd.read_csv(LOCAL / "dimensional_main_per_sample.csv")
    main_dl = pd.read_csv(LOCAL / "candidate_main_per_sample.csv")
    p2_dim = pd.read_csv(LOCAL / "dimensional_p2_per_sample.csv")
    p2_dl = pd.read_csv(LOCAL / "candidate_p2_per_sample.csv")

    print("\n[Seed-level pooled J1 — 5 folds x 45k samples per seed]")
    rows = []
    for name, df in [("dimensional", main_dim), ("dimensionless", main_dl)]:
        sp = seed_pooled(df)
        pn = pooled_per_n(df)
        rows.append({
            "route": name,
            "seed42": sp.get(42), "seed2026": sp.get(2026), "seed3407": sp.get(3407),
            "seed_mean": float(np.mean(list(sp.values()))),
            "J1_n7": pn.get(7), "J1_n10": pn.get(10), "J1_n20": pn.get(20),
            "endpoint_rate": float(df["selected_delta"].isin([0.0, 0.02, 0.48, 0.5]).mean()),
            "failure_rate": 1.0 - df["is_valid"].mean(),
        })
    df_seed = pd.DataFrame(rows)
    print(df_seed.to_string(index=False))

    # Sealed E3b seed stability.
    sealed_ss = pd.read_csv(E3B / "seed_stability.csv")
    print("\n[Sealed E3b Vector-MLP-L6 seed stability]")
    print(sealed_ss.to_string(index=False))

    # Sealed E4a 'full' 15-model distribution.
    e4a = pd.read_csv(E4 / "E4a_feature_ablation.csv")
    e4a_full = e4a[e4a["feature_group"] == "full"]["pooled_J1"]
    print("\n[Sealed E4a 'full' 15-model distribution]")
    print(f"  mean={e4a_full.mean():.5f} median={e4a_full.median():.5f} "
          f"SD={e4a_full.std(ddof=1):.5f} min={e4a_full.min():.5f} max={e4a_full.max():.5f}")

    # My in-harness 15-model distributions.
    ml = pd.read_csv(CAND / "model_level_summary.csv")
    print("\n[In-harness 15-model distribution (model_level_summary.csv)]")
    for route in ["dimensional", "dimensionless"]:
        v = ml[ml["route"] == route]["pooled_J1"]
        print(f"  {route:<14} mean={v.mean():.5f} median={v.median():.5f} "
              f"SD={v.std(ddof=1):.5f} min={v.min():.5f} max={v.max():.5f}")

    # Retention: dimensionless relative to dimensional.
    dim_seed_mean = float(np.mean(list(seed_pooled(main_dim).values())))
    dl_seed_mean = float(np.mean(list(seed_pooled(main_dl).values())))
    print("\n[Retention (3-seed mean pooled J1)]")
    print(f"  dimensional   = {dim_seed_mean:.6f}")
    print(f"  dimensionless = {dl_seed_mean:.6f}")
    print(f"  absolute delta = {dl_seed_mean - dim_seed_mean:+.6f} "
          f"(+ means worse)")
    print(f"  relative retention = {dim_seed_mean / dl_seed_mean:.4f} "
          f"(dimensionless J1 as fraction of dimensional)")

    # P2 comparisons.
    print("\n[P2 generalization — 15-model mean per track]")
    for track in sorted(p2_dl["track"].unique()):
        a = p2_dim[p2_dim["track"] == track]["true_loss"]
        b = p2_dl[p2_dl["track"] == track]["true_loss"]
        # per-model pooled J1 then mean (mirrors sealed cross_model_distribution mean)
        a_mean = float(p2_dim[p2_dim["track"] == track]
                       .groupby(["fold", "seed"])["true_loss"].mean()
                       .pipe(np.sqrt).mean())
        b_mean = float(p2_dl[p2_dl["track"] == track]
                       .groupby(["fold", "seed"])["true_loss"].mean()
                       .pipe(np.sqrt).mean())
        print(f"  {track:<7} dimensional={a_mean:.5f} dimensionless={b_mean:.5f} "
              f"delta={b_mean - a_mean:+.5f}")

    # Scale invariance summary from summary.json.
    summary = json.loads((CAND / "summary.json").read_text(encoding="utf-8"))
    si = summary["scale_invariance"]
    print("\n[Scale invariance]")
    print(f"  max_feature_rel_diff={si['max_feature_rel_diff']:.3e} "
          f"max_curve_rel_diff={si['max_curve_rel_diff']:.3e} "
          f"delta_consistent_rate={si['delta_consistent_rate']:.4f} "
          f"(n_probe={si['n_probe_samples']})")

    print("\nDone.")


if __name__ == "__main__":
    main()
