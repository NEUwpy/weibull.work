"""P3 smoke test v3: real Direct-MLP + real Vector-MLP + six methods.

Uses 36,000 real main-grid training samples.
Vector-MLP is trained via E4 production code, then its selected deltas are
joined to MC chunk files to retrieve actual (beta_hat, eta_hat, gamma_hat).

Output goes OUTSIDE the repository. NOT formal results.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

REPO = Path(r"D:\weibull")
CODE_DIR = REPO / "Study/01-study-MDM最小偏移量优化研究/code"
PYTHON_DIR = REPO / "python"
sys.path.insert(0, str(CODE_DIR))
sys.path.insert(0, str(PYTHON_DIR))

import run_E4_formal_validation as e4
import run_p3_direct_mlp as direct
import run_p3_fair_compare as compare
import p3_config as cfg
from studies.common.sample import generate_sample
from studies.common.runner import run_method

OUT = Path(r"D:\weibull-local-artifacts\study01-p3-smoke-v3")
OUT.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("P3 Direct-MLP Smoke Test v3 (36k train, REAL Vector-MLP, 6 methods)")
print("=" * 60)

# ── 1. Build features: full main grid for one fold ─────────────────────
print("\n[1] Building features...")
folds = e4.get_combo_split()
fold = folds[0]
TRAIN_REPEATS = 1000  # 36 combos × 1000 = 36,000
TEST_REPEATS = 20

rows = []
for beta, goe, n in fold["train_combos"] + fold["test_combos"]:
    eta = 1.0
    gamma = goe * eta
    reps = TRAIN_REPEATS if (beta, goe, n) in fold["train_combos"] else TEST_REPEATS
    for rid in range(reps):
        sample = generate_sample(beta, eta, gamma, n, rid, seed="study01_v1")
        feats = e4.compute_sample_features(sample)
        rows.append({"beta": beta, "eta": eta, "gamma": gamma,
                     "gamma_over_eta": goe, "n": n, "repeat_id": rid, **feats})
df_features = pd.DataFrame(rows)
n_train = sum(1 for r in rows if (r["beta"], r["gamma_over_eta"], r["n"]) in fold["train_combos"])
print(f"   Fold: {fold['fold_name']}, train: {n_train}, test: {len(rows) - n_train}")

# ── 2. Build risk curves (full 26-delta) for fold penalty + Vector-MLP training
print("\n[2] Building risk curves from MC chunks...")
# Load the actual MC data for this fold's training combos
chunk_dir = REPO / "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/shared_data/chunks"
risk_rows = []
mc_rows = []

for beta, goe, n in fold["train_combos"] + fold["test_combos"]:
    eta = 1.0
    gamma = goe * eta
    # Find the chunk file for this combo
    # Chunk naming: chunk_XXXX_mdm.csv, need to find by combo
    # Use the same approach as E4: load authoritative chunks
    combo_mc = []
    for rid in range(min(reps := (TRAIN_REPEATS if (beta, goe, n) in fold["train_combos"] else TEST_REPEATS), reps)):
        # Generate sample and run MDM for delta=0.1 only (for speed)
        # Actually, for risk curves we need ALL 26 deltas
        # Use the pre-computed MC data from chunks
        pass

# Instead of loading chunks (slow), build risk curves from E3b risk_curves.csv
print("   Loading E3b risk_curves.csv...")
e3b_risk = pd.read_csv(
    REPO / "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3b_vector_mlp/risk_curves.csv"
)
# Filter to this fold's training combos
train_keys = set((b, g, n) for b, g, n in fold["train_combos"])
e3b_risk["combo_key"] = list(zip(
    e3b_risk["beta"], e3b_risk["gamma_over_eta"], e3b_risk["n"]
))
df_risk = e3b_risk[e3b_risk["combo_key"].apply(lambda k: k in train_keys)].drop(columns=["combo_key"])
print(f"   Risk curves: {len(df_risk)} train rows")

# ── 3. Compute fold penalty ────────────────────────────────────────────
print("\n[3] Computing fold penalty (ALL 26 deltas)...")
fold_penalty = direct.compute_fold_penalty(df_features, df_risk, fold["train_combos"])
print(f"   Fold penalty (P99 of 26-delta losses): {fold_penalty:.6f}")

# ── 4. Train Direct-MLP (36,000 samples, seed=42) ──────────────────────
print("\n[4] Training Direct-MLP on 36,000 samples (seed=42)...")
X_train, Y_train, x_bar_train, meta = direct.build_training_data(df_features, fold["train_combos"])
assert meta["n_train_samples"] == 36000, f"Expected 36000, got {meta['n_train_samples']}"
print(f"   Y_train shape: {Y_train.shape}")
t0 = time.time()
direct_model, direct_info = direct.train_direct_mlp(X_train, Y_train, x_bar_train, seed=42)
elapsed = time.time() - t0
print(f"   Training: {elapsed:.1f}s, n_iter={direct_info['n_iter']}")

# ── 5. Train Vector-MLP using E4 production code ───────────────────────
print("\n[5] Training Vector-MLP via E4 production code (seed=42)...")
# Build Vector-MLP training data: need risk vectors for training samples
# Use E4's _pivot_risk_vectors
train_mask = df_features.apply(
    lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in fold["train_combos"], axis=1
)
df_train_feats = df_features[train_mask].copy()

# Build per-delta loss table for training samples
loss_cols = [c for c in df_risk.columns if c.startswith("loss_d")]
train_keys_set = set(zip(
    df_train_feats["beta"].astype(float),
    df_train_feats["gamma_over_eta"].astype(float),
    df_train_feats["n"].astype(int),
    df_train_feats["repeat_id"].astype(int),
))

# Pivot risk curves to long format for Vector-MLP training
loss_long = []
for _, row in df_risk.iterrows():
    key = (float(row["beta"]), float(row["gamma_over_eta"]), int(row["n"]), int(row["repeat_id"]))
    if key in train_keys_set:
        for d_idx, col in enumerate(loss_cols):
            d = e4.DELTA_GRID[d_idx]
            val = float(row[col])
            if np.isnan(val):
                val = fold_penalty
            loss_long.append({
                "beta": key[0], "gamma_over_eta": key[1], "n": key[2], "repeat_id": key[3],
                "delta": d, "loss": val,
            })
df_loss_long = pd.DataFrame(loss_long)

# Merge features into loss table
df_loss_merged = df_loss_long.merge(
    df_train_feats[["beta", "gamma_over_eta", "n", "repeat_id"] + e4.SAMPLE_FEATURE_COLS],
    on=["beta", "gamma_over_eta", "n", "repeat_id"],
)

# Pivot to 26-dim risk vectors
samples_df, Y_vector = e4._pivot_risk_vectors(df_loss_merged, "loss", fold_penalty)
X_vector = e4._build_X_from_samples(samples_df, *e4._fit_zscore_params(samples_df))

print(f"   Vector-MLP train: X={X_vector.shape}, Y={Y_vector.shape}")
t0 = time.time()
vector_model, vector_scaler = e4._train_mlp(X_vector, Y_vector, seed=42)
elapsed_vec = time.time() - t0
print(f"   Vector-MLP training: {elapsed_vec:.1f}s")

# ── 6. Vector-MLP evaluation: select delta → join to MC params ─────────
print("\n[6] Evaluating Vector-MLP on test combos...")
test_combos = fold["test_combos"]
test_mask = df_features.apply(
    lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1
)
df_test_feats = df_features[test_mask].copy()

# Build eval loss table for test combos (from E3b risk_curves)
test_keys_set = set(zip(
    df_test_feats["beta"].astype(float),
    df_test_feats["gamma_over_eta"].astype(float),
    df_test_feats["n"].astype(int),
    df_test_feats["repeat_id"].astype(int),
))

# Get risk curves for test combos
test_risk = e3b_risk[
    e3b_risk.apply(lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1)
]

# Build per-delta loss for test
test_loss_long = []
for _, row in test_risk.iterrows():
    key = (float(row["beta"]), float(row["gamma_over_eta"]), int(row["n"]), int(row["repeat_id"]))
    if key in test_keys_set:
        for d_idx, col in enumerate(loss_cols):
            d = e4.DELTA_GRID[d_idx]
            val = float(row[col])
            if np.isnan(val):
                val = fold_penalty
            test_loss_long.append({
                "beta": key[0], "gamma_over_eta": key[1], "n": key[2], "repeat_id": key[3],
                "delta": d, "loss": val,
            })
df_test_loss = pd.DataFrame(test_loss_long)

# Evaluate Vector-MLP on test
means_vec, stds_vec = e4._fit_zscore_params(df_train_feats)
vector_eval_rows = e4._evaluate_single_model(
    vector_model, vector_scaler, df_test_feats, df_test_loss,
    means_vec, stds_vec, fold_penalty, fold["fold_name"], 42,
)

# Convert Vector-MLP selected_delta → (beta_hat, eta_hat, gamma_hat) via MC chunk join
# For each test sample, run MDM at selected_delta to get params
print("   Joining Vector-MLP selected deltas to MDM parameter estimates...")
vector_preds = []
for row in vector_eval_rows:
    beta = row["beta"]
    goe = row["gamma_over_eta"]
    n_val = row["n"]
    rid = row["repeat_id"]
    sel_delta = row["selected_delta"]
    eta = 1.0
    gamma = goe * eta

    # Run MDM at selected delta on this sample
    sample = generate_sample(beta, eta, gamma, n_val, rid, seed="study01_v1")
    result = run_method("mdm", sample, offset=sel_delta)

    vector_preds.append({
        "beta": beta, "gamma_over_eta": goe, "n": n_val, "repeat_id": rid,
        "eta": eta, "gamma": gamma,
        "beta_hat": result.get("beta_hat", 0.0),
        "eta_hat": result.get("eta_hat", 0.0),
        "gamma_hat": result.get("gamma_hat", 0.0),
        "failed": not result.get("converged", False),
        "failure_reason": "" if result.get("converged", False) else "mdm_not_converged",
    })
vector_preds_df = pd.DataFrame(vector_preds)
print(f"   Vector-MLP predictions: {len(vector_preds_df)} samples")
print(f"   Vector-MLP failures: {vector_preds_df['failed'].sum()}")

# ── 7. Run six-method comparison ───────────────────────────────────────
print("\n[7] Running six-method fair comparison...")
direct_models = {
    fold["fold_name"]: {42: (direct_model, direct_info, meta["zscore_means"], meta["zscore_stds"])}
}
vector_models = {
    fold["fold_name"]: {42: vector_preds_df}
}

result = compare.run_fair_comparison(
    df_features=df_features,
    direct_models=direct_models,
    vector_models=vector_models,
    df_risk_curves=df_risk,
    folds=[fold],
    repeats=TEST_REPEATS,
    seeds=[42],
    require_all_six=True,
)

# ── 8. Report ──────────────────────────────────────────────────────────
print(f"\n[8] Results:")
print(f"   Methods: {result['methods_seen']}")
print(f"   Total rows: {result['n_rows']}")
print(f"   Alignment: {result['sample_key_alignment']['ok']}")
print(f"   Coverage gaps: {result['coverage_gaps']}")

df_all = pd.DataFrame(result["per_sample"])
for m in sorted(df_all["method"].unique()):
    summary = result["summaries"][m]
    print(f"   {m:20s}: J1={summary['median_J1']:.4f}, n={summary['n_rows']}, fails={summary['n_failures']}")

# ── 9. Assert ──────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print("SMOKE CHECKS:")
assert len(result["methods_seen"]) == 6
assert set(result["methods_seen"]) == set(compare.ALL_SIX_METHODS)
print(f"  [PASS] All six methods")
assert result["sample_key_alignment"]["ok"]
print(f"  [PASS] Sample key alignment")
assert (df_all["failure_penalty"] > 0).all()
print(f"  [PASS] failure_penalty > 0")
assert not result["coverage_gaps"]
print(f"  [PASS] No coverage gaps")

direct_rows = df_all[df_all["method"] == "Direct-MLP"]
preds = direct_rows[["beta_hat", "eta_hat", "gamma_hat"]].values
assert direct.verify_output_constraints(preds)
print(f"  [PASS] Output constraints")

# Verify Vector-MLP is NOT random noise (betas should correlate with true betas)
vec_rows = df_all[df_all["method"] == "MDM-Vector-MLP"]
if len(vec_rows) > 3:
    corr = np.corrcoef(vec_rows["beta"], vec_rows["beta_hat"])[0, 1]
    assert corr > 0.3, f"Vector-MLP beta correlation too low: {corr}"
    print(f"  [PASS] Vector-MLP beta correlation: {corr:.3f} (not random noise)")

print(f"  [INFO] Fold penalty: {fold_penalty:.6f}")
print(f"  [INFO] Config hash: {direct.config_hash()[:16]}...")

# ── 10. Save ───────────────────────────────────────────────────────────
smoke_output = {
    "config_hash": direct.config_hash(),
    "fold": fold["fold_name"],
    "n_train_samples": 36000,
    "n_test_samples": len(df_test_feats),
    "direct_mlp_n_iter": direct_info["n_iter"],
    "direct_mlp_elapsed_s": elapsed,
    "vector_mlp_elapsed_s": elapsed_vec,
    "fold_penalty": fold_penalty,
    "methods": result["methods_seen"],
    "total_rows": result["n_rows"],
    "alignment_ok": result["sample_key_alignment"]["ok"],
    "coverage_gaps": result["coverage_gaps"],
    "summaries": {m: {k: v for k, v in s.items() if k != "error"} for m, s in result["summaries"].items()},
    "note": "Smoke test only — NOT formal results. Vector-MLP uses REAL E4 production training.",
}
(OUT / "p3_smoke_v3_result.json").write_text(
    json.dumps(smoke_output, indent=2, default=str), encoding="utf-8"
)
df_all.to_csv(OUT / "p3_smoke_v3_per_sample.csv", index=False)
print(f"\n  Output: {OUT}")
print(f"\nSMOKE PASSED")
print("=" * 60)
