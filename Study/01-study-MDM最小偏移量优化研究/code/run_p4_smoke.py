"""P4 smoke test: real six-method comparison under unified schema.

Uses 1 fold × 1 seed × minimal repeats to validate the execution chain.
Output goes OUTSIDE the repository to D:\\weibull-local-artifacts.
NOT formal results. Only validates that the pipeline works end-to-end.

Verifies:
- Direct-MLP real training and inference
- Vector-MLP real risk curve prediction, delta selection, MDM re-estimation
- MLE/LSE/WMLE real production implementations
- Identical sample keys across all six methods
- Unified failure handling (per-fold P99 penalty)
- Model-first aggregation (not sample-merged)
- Atomic write and independent SHA256 recomputation
"""
from __future__ import annotations

import hashlib
import json
import platform
import subprocess
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
import run_p4_formal_compare as p4
import p4_config as cfg
import p3_config as p3cfg
from studies.common.sample import generate_sample
from studies.common.runner import run_method

# ── Output: OUTSIDE repository ──────────────────────────────────────────
OUT = Path(r"D:\weibull-local-artifacts\study01-p4-smoke")
# Verify smoke path is outside formal directory tree
cfg.assert_smoke_outside_formal(str(OUT))
# Verify P4 not authorized
cfg.check_formal_not_authorized()

OUT.mkdir(parents=True, exist_ok=True)

print("=" * 70)
print("P4 Formal Compare Smoke Test (1 fold, 1 seed, 5 repeats, 6 methods)")
print("=" * 70)
t_start = time.time()

# ── 1. Build features: minimal main grid for one fold ──────────────────
print("\n[1] Building features (1 fold, 5 test repeats)...")
folds = e4.get_combo_split()
fold = folds[0]
TRAIN_REPEATS = 1000  # Need full training data for realistic models
TEST_REPEATS = 5  # Minimal for smoke

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

# ── 2. Load E3b risk curves for fold penalty + Vector-MLP ───────────────
print("\n[2] Loading E3b risk_curves.csv for fold penalty + Vector-MLP training...")
e3b_risk = pd.read_csv(
    REPO / "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3b_vector_mlp/risk_curves.csv"
)
train_keys = set((b, g, n) for b, g, n in fold["train_combos"])
e3b_risk["combo_key"] = list(zip(
    e3b_risk["beta"], e3b_risk["gamma_over_eta"], e3b_risk["n"]
))
df_risk = e3b_risk[e3b_risk["combo_key"].apply(lambda k: k in train_keys)].drop(columns=["combo_key"])
print(f"   Risk curves: {len(df_risk)} train rows")

# ── 3. Compute fold penalty (P99 of ALL 26 deltas) ──────────────────────
print("\n[3] Computing fold penalty...")
fold_penalty = direct.compute_fold_penalty(df_features, df_risk, fold["train_combos"])
print(f"   Fold penalty (P99): {fold_penalty:.6f}")

# ── 4. Train Direct-MLP (real PyTorch training) ─────────────────────────
print("\n[4] Training Direct-MLP (36,000 samples, seed=42)...")
X_train, Y_train, x_bar_train, meta = direct.build_training_data(df_features, fold["train_combos"])
assert meta["n_train_samples"] == 36000, f"Expected 36000, got {meta['n_train_samples']}"
t0 = time.time()
direct_model, direct_info = direct.train_direct_mlp(X_train, Y_train, x_bar_train, seed=42)
elapsed_direct = time.time() - t0
print(f"   Training: {elapsed_direct:.1f}s, n_iter={direct_info['n_iter']}")

# ── 5. Train Vector-MLP via E4 production code (real) ───────────────────
print("\n[5] Training Vector-MLP via E4 production code (seed=42)...")
train_mask = df_features.apply(
    lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in fold["train_combos"], axis=1
)
df_train_feats = df_features[train_mask].copy()

loss_cols = [c for c in df_risk.columns if c.startswith("loss_d")]
train_keys_set = set(zip(
    df_train_feats["beta"].astype(float),
    df_train_feats["gamma_over_eta"].astype(float),
    df_train_feats["n"].astype(int),
    df_train_feats["repeat_id"].astype(int),
))

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
                "beta": key[0], "eta": 1.0, "gamma": key[1] * 1.0,
                "gamma_over_eta": key[1], "n": key[2], "repeat_id": key[3],
                "delta": d, "loss": val,
            })
df_loss_long = pd.DataFrame(loss_long)

feat_cols_no_n = [c for c in e4.SAMPLE_FEATURE_COLS if c != "n"]
df_train_feats_for_merge = df_train_feats[
    ["beta", "gamma_over_eta", "n", "repeat_id"] + feat_cols_no_n
].copy()
df_loss_merged = df_loss_long.merge(
    df_train_feats_for_merge,
    on=["beta", "gamma_over_eta", "n", "repeat_id"],
)

samples_df, Y_vector = e4._pivot_risk_vectors(df_loss_merged, "loss", fold_penalty)
X_vector = e4._build_X_from_samples(samples_df, *e4._fit_zscore_params(samples_df))

print(f"   Vector-MLP train: X={X_vector.shape}, Y={Y_vector.shape}")
t0 = time.time()
vector_model, vector_scaler = e4._train_mlp(X_vector, Y_vector, seed=42)
elapsed_vec = time.time() - t0
print(f"   Vector-MLP training: {elapsed_vec:.1f}s")

# ── 6. Evaluate Vector-MLP on test combos → MDM params ──────────────────
print("\n[6] Evaluating Vector-MLP on test combos...")
test_combos = fold["test_combos"]
test_mask = df_features.apply(
    lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1
)
df_test_feats = df_features[test_mask].copy()

test_keys_set = set(zip(
    df_test_feats["beta"].astype(float),
    df_test_feats["gamma_over_eta"].astype(float),
    df_test_feats["n"].astype(int),
    df_test_feats["repeat_id"].astype(int),
))

test_risk = e3b_risk[
    e3b_risk.apply(lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1)
]

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

means_vec, stds_vec = e4._fit_zscore_params(df_train_feats)
vector_eval_rows = e4._evaluate_single_model(
    vector_model, vector_scaler, df_test_feats, df_test_loss,
    means_vec, stds_vec, fold_penalty, fold["fold_name"], 42,
)

# Join Vector-MLP selected_delta → MDM params
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
print(f"   Vector-MLP predictions: {len(vector_preds_df)} samples, failures: {vector_preds_df['failed'].sum()}")

# ── 7. Run six-method comparison via P3 fair compare ────────────────────
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

print(f"\n[8] Results:")
print(f"   Methods: {result['methods_seen']}")
print(f"   Total rows: {result['n_rows']}")
print(f"   Alignment: {result['sample_key_alignment']['ok']}")
print(f"   Coverage gaps: {result['coverage_gaps']}")

df_all = pd.DataFrame(result["per_sample"])
for m in sorted(df_all["method"].unique()):
    summary = result["summaries"][m]
    print(f"   {m:20s}: J1={summary['median_J1']:.4f}, n={summary['n_rows']}, fails={summary['n_failures']}")

# ── 9. Convert to P4 unified schema ─────────────────────────────────────
print("\n[9] Converting to P4 unified schema with track='main_holdout'...")
p4_rows = []
for row in result["per_sample"]:
    p4_row = {col: row.get(col, "") for col in p4.PER_SAMPLE_COLUMNS}
    p4_row["track"] = cfg.TRACK_MAIN_HOLDOUT
    # Ensure true_loss_complete_case is present
    if "true_loss_complete_case" not in row:
        p4_row["true_loss_complete_case"] = row.get("true_loss", float("nan"))
    p4_rows.append(p4_row)

# Apply P4 failure contract (idempotent with P3's, but validates consistency)
p4_rows = p4.apply_failure_contract_p4(p4_rows)
df_p4 = pd.DataFrame(p4_rows)
print(f"   P4 unified rows: {len(df_p4)}")

# ── 10. P4 contract checks ──────────────────────────────────────────────
print(f"\n[10] P4 Contract Checks:")

# All six methods present
assert len(result["methods_seen"]) == 6
assert set(result["methods_seen"]) == set(cfg.P4_METHODS)
print(f"  [PASS] All six methods present")

# Sample key alignment
assert result["sample_key_alignment"]["ok"]
print(f"  [PASS] Sample key alignment")

# No coverage gaps
assert not result["coverage_gaps"]
print(f"  [PASS] No coverage gaps")

# Failure penalty > 0
assert (df_p4["failure_penalty"] > 0).all()
print(f"  [PASS] failure_penalty > 0")

# Direct-MLP output constraints
direct_rows = df_p4[df_p4["method"] == "Direct-MLP"]
preds = direct_rows[["beta_hat", "eta_hat", "gamma_hat"]].values
assert direct.verify_output_constraints(preds)
print(f"  [PASS] Direct-MLP output constraints (beta>0, eta>0, gamma>=0)")

# Model-first aggregation check (smoke: 1 fold × 1 seed, verify structure not count)
for method in cfg.LEARNING_METHODS:
    m_df = df_p4[df_p4["method"] == method]
    assert not m_df.empty, f"{method} has no rows"
    assert m_df["fold"].notna().all(), f"{method} fold column has NaN"
    assert m_df["seed"].notna().all(), f"{method} seed column has NaN"
    n_models = m_df.groupby(["fold", "seed"]).ngroups
    assert n_models >= 1, f"{method} has no (fold,seed) groups"
    agg = p4.model_first_aggregate(df_p4, method, track=cfg.TRACK_MAIN_HOLDOUT)
    assert "median_J1" in agg, f"{method} model_first_aggregate missing median_J1"
    assert agg["n_models"] >= 1, f"{method} model_first_aggregate n_models < 1"
print(f"  [PASS] Model-first aggregation structure (Direct-MLP and Vector-MLP)")

# Vector-MLP is NOT random noise
vec_rows = df_p4[df_p4["method"] == "MDM-Vector-MLP"]
if len(vec_rows) > 3:
    corr = np.corrcoef(vec_rows["beta"], vec_rows["beta_hat"])[0, 1]
    assert corr > 0.3, f"Vector-MLP beta correlation too low: {corr}"
    print(f"  [PASS] Vector-MLP beta correlation: {corr:.3f}")

# Scale equivariance
c = 5.0
df_test_si = direct.make_scale_invariant(df_test_feats)
X_test_orig = direct.build_scale_invariant_X(df_test_si, meta["zscore_means"], meta["zscore_stds"])
x_bar_orig = df_test_feats["x_bar"].values.astype(np.float64)
preds_orig = direct.predict_direct_mlp(direct_model, direct_info, X_test_orig, x_bar_orig)

df_test_scaled = df_test_feats.copy()
for col in direct.SCALE_DEPENDENT_COLS:
    df_test_scaled[col] = df_test_scaled[col].astype(float) * c
df_test_scaled_si = direct.make_scale_invariant(df_test_scaled)
X_test_scaled = direct.build_scale_invariant_X(df_test_scaled_si, meta["zscore_means"], meta["zscore_stds"])
x_bar_scaled = df_test_scaled["x_bar"].values.astype(np.float64)
preds_scaled = direct.predict_direct_mlp(direct_model, direct_info, X_test_scaled, x_bar_scaled)

input_ok = np.allclose(X_test_orig, X_test_scaled, atol=1e-6)
assert input_ok
equiv_ok = direct.verify_scale_equivariance(preds_orig, preds_scaled, c, atol=1e-4)
assert equiv_ok
print(f"  [PASS] Full model scale equivariance (c={c})")

# ── 11. Atomic write and SHA256 ─────────────────────────────────────────
print("\n[11] Atomic write and SHA256 sealing...")

# Write per-sample results atomically
p4.atomic_write_csv(df_p4, OUT / "p4_smoke_per_sample.csv")

# Write summary
summaries = {}
for m in df_p4["method"].unique():
    summaries[m] = p4.model_first_aggregate(df_p4, m, track=cfg.TRACK_MAIN_HOLDOUT)

smoke_output = {
    "test_type": "P4 smoke — NOT formal results",
    "p4_formal_authorized": cfg.P4_FORMAL_AUTHORIZED,
    "fold": fold["fold_name"],
    "seed": 42,
    "n_train_samples": 36000,
    "n_test_samples": len(df_test_feats),
    "fold_penalty": fold_penalty,
    "direct_mlp_elapsed_s": elapsed_direct,
    "vector_mlp_elapsed_s": elapsed_vec,
    "total_elapsed_s": time.time() - t_start,
    "methods": result["methods_seen"],
    "total_rows": result["n_rows"],
    "alignment_ok": result["sample_key_alignment"]["ok"],
    "coverage_gaps": result["coverage_gaps"],
    "summaries": {m: {k: v for k, v in s.items() if k != "error"} for m, s in summaries.items()},
    "config_hash": direct.config_hash(),
    "git_commit": p4.get_git_commit(),
    "python_version": platform.python_version(),
    "numpy_version": np.__version__,
}
p4.atomic_write_json(smoke_output, OUT / "p4_smoke_result.json")

# Seal with SHA256SUMS
sums_hash = p4.seal_outputs(OUT, ["p4_smoke_per_sample.csv", "p4_smoke_result.json"])
print(f"   SHA256SUMS seal hash: {sums_hash[:16]}...")

# Independent SHA256 recomputation
print("\n[12] Independent SHA256 verification...")
for fname in ["p4_smoke_per_sample.csv", "p4_smoke_result.json", "SHA256SUMS"]:
    fpath = OUT / fname
    h = p4.compute_sha256(fpath)
    print(f"   {fname}: {h[:16]}...")

# Verify SHA256SUMS entries match recomputed hashes
sums_content = (OUT / "SHA256SUMS").read_text(encoding="utf-8").strip().split("\n")
for line in sums_content:
    parts = line.split("  ", 1)
    if len(parts) == 2:
        recorded_hash, fname = parts
        recomputed = p4.compute_sha256(OUT / fname)
        assert recorded_hash == recomputed, f"SHA256 mismatch for {fname}"
print(f"  [PASS] All SHA256 independently verified")

print(f"\n{'=' * 70}")
print(f"SMOKE PASSED — {time.time() - t_start:.1f}s total")
print(f"  Direct-MLP training: {elapsed_direct:.1f}s")
print(f"  Vector-MLP training: {elapsed_vec:.1f}s")
print(f"  Six methods: {', '.join(sorted(result['methods_seen']))}")
print(f"  Output: {OUT}")
print(f"  NOTE: Smoke results do NOT constitute formal comparison conclusions.")
print(f"  P4_FORMAL_AUTHORIZED = {cfg.P4_FORMAL_AUTHORIZED}")
print("=" * 70)
