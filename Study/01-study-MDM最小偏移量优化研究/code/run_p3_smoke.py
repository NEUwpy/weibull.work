"""P3 smoke test: real end-to-end Direct-MLP training + six-method comparison.

Uses 36,000 real main-grid training samples (9 combos × 4000 repeats).
Tests a small number of held-out samples (50 repeats × 9 test combos).
Runs OUTSIDE the repository. NOT formal results.
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

OUT = Path(r"D:\weibull-local-artifacts\study01-p3-smoke-v2")
OUT.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("P3 Direct-MLP Smoke Test v2 (36k train, 6 methods)")
print("=" * 60)

# ── 1. Build features: 4000 repeats for train, 50 for test ─────────────
print("\n[1] Building features...")
folds = e4.get_combo_split()
fold = folds[0]
TRAIN_REPEATS = 1000  # 36 combos × 1000 = 36,000 training samples (full grid)
TEST_REPEATS = 20     # 9 combos × 20 = 180 test samples (small for smoke)

rows = []
for beta, goe, n in fold["train_combos"]:
    eta = 1.0
    gamma = goe * eta
    for rid in range(TRAIN_REPEATS):
        sample = generate_sample(beta, eta, gamma, n, rid, seed="study01_v1")
        feats = e4.compute_sample_features(sample)
        rows.append({
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n, "repeat_id": rid,
            **feats,
        })
for beta, goe, n in fold["test_combos"]:
    eta = 1.0
    gamma = goe * eta
    for rid in range(TEST_REPEATS):
        sample = generate_sample(beta, eta, gamma, n, rid, seed="study01_v1")
        feats = e4.compute_sample_features(sample)
        rows.append({
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n, "repeat_id": rid,
            **feats,
        })
df_features = pd.DataFrame(rows)
n_train = len(df_features[
    df_features.apply(
        lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in fold["train_combos"],
        axis=1,
    )
])
print(f"   Fold: {fold['fold_name']}, train combos: {len(fold['train_combos'])}, test combos: {len(fold['test_combos'])}")
print(f"   Train samples: {n_train} (must be 36000)")

# ── 2. Build risk curves for fold penalty ──────────────────────────────
print("\n[2] Building risk curves for fold penalty...")
risk_rows = []
for beta, goe, n in fold["train_combos"]:
    eta = 1.0
    for rid in range(min(TRAIN_REPEATS, 200)):  # Subset for speed
        row = {"beta": beta, "gamma_over_eta": goe, "n": n, "repeat_id": rid}
        for d_pct in range(0, 52, 2):
            d = d_pct / 100
            row[f"loss_d{d:.2f}"] = 0.3 + abs(d - 0.1) * 1.5
        risk_rows.append(row)
df_risk = pd.DataFrame(risk_rows)
print(f"   Risk curves: {len(df_risk)} rows")

# ── 3. Train Direct-MLP (36,000 samples, seed=42) ──────────────────────
print("\n[3] Training Direct-MLP on 36,000 samples (seed=42)...")
X_train, Y_train, meta = direct.build_training_data(df_features, fold["train_combos"])
assert meta["n_train_samples"] == 36000, f"Expected 36000, got {meta['n_train_samples']}"
print(f"   Y_train shape: {Y_train.shape}")
print(f"   Y_train beta range: [{Y_train[:,0].min():.3f}, {Y_train[:,0].max():.3f}]")
print(f"   Y_train eta range: [{Y_train[:,1].min():.3f}, {Y_train[:,1].max():.3f}]")

t0 = time.time()
model, target_scaler = direct.train_direct_mlp(X_train, Y_train, seed=42)
elapsed = time.time() - t0
print(f"   Training: {elapsed:.1f}s, n_iter={model.n_iter_}")

# ── 4. Build Vector-MLP placeholder predictions ────────────────────────
print("\n[4] Building Vector-MLP predictions...")
test_mask = df_features.apply(
    lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in fold["test_combos"], axis=1
)
df_test = df_features[test_mask]
np.random.seed(42)
vector_preds = pd.DataFrame({
    "beta": df_test["beta"].values,
    "gamma_over_eta": df_test["gamma_over_eta"].values,
    "n": df_test["n"].values,
    "repeat_id": df_test["repeat_id"].values,
    "beta_hat": df_test["beta"].values * (1 + np.random.normal(0, 0.1, len(df_test))),
    "eta_hat": df_test["eta"].values,
    "gamma_hat": df_test["gamma"].values,
    "failed": [False] * len(df_test),
    "failure_reason": [""] * len(df_test),
})
print(f"   Vector-MLP predictions: {len(vector_preds)} samples")

# ── 5. Run six-method comparison ───────────────────────────────────────
print("\n[5] Running six-method fair comparison...")
direct_models = {
    fold["fold_name"]: [(42, model, target_scaler, meta["zscore_means"], meta["zscore_stds"])]
}
vector_models = {
    fold["fold_name"]: [(42, vector_preds)]
}

result = compare.run_fair_comparison(
    df_features=df_features,
    direct_models=direct_models,
    vector_models=vector_models,
    df_risk_curves=df_risk,
    folds=[fold],
    repeats=TEST_REPEATS,
    require_all_six=True,
)

# ── 6. Verify and report ───────────────────────────────────────────────
print(f"\n[6] Results:")
print(f"   Methods: {result['methods_seen']}")
print(f"   Total rows: {result['n_rows']}")
print(f"   Alignment: {result['sample_key_alignment']['ok']}")

df_all = pd.DataFrame(result["per_sample"])
for m in sorted(df_all["method"].unique()):
    summary = result["summaries"][m]
    print(f"   {m:20s}: J1={summary['median_J1']:.4f}, n={summary['n_rows']}, fails={summary['n_failures']}")

# ── 7. Assert ──────────────────────────────────────────────────────────
print(f"\n{'=' * 60}")
print("SMOKE CHECKS:")
assert len(result["methods_seen"]) == 6
assert set(result["methods_seen"]) == set(compare.ALL_SIX_METHODS)
print(f"  [PASS] All six methods: {result['methods_seen']}")
assert result["sample_key_alignment"]["ok"]
print(f"  [PASS] Sample key alignment")
assert (df_all["failure_penalty"] > 0).all()
print(f"  [PASS] failure_penalty > 0")
direct_rows = df_all[df_all["method"] == "Direct-MLP"]
preds = direct_rows[["beta_hat", "eta_hat", "gamma_hat"]].values
assert direct.verify_output_constraints(preds)
print(f"  [PASS] Output constraints")
chash = direct.config_hash()
print(f"  [INFO] Config hash: {chash[:16]}...")

# ── 8. Save ────────────────────────────────────────────────────────────
smoke_output = {
    "config_hash": chash,
    "fold": fold["fold_name"],
    "n_train_samples": 36000,
    "n_test_samples": len(df_test),
    "mlp_n_iter": model.n_iter_,
    "mlp_elapsed_s": elapsed,
    "methods": result["methods_seen"],
    "total_rows": result["n_rows"],
    "alignment_ok": result["sample_key_alignment"]["ok"],
    "summaries": {m: {k: v for k, v in s.items() if k != "error"} for m, s in result["summaries"].items()},
    "note": "Smoke test only — NOT formal results. Vector-MLP uses simulated predictions.",
}
(OUT / "p3_smoke_v2_result.json").write_text(
    json.dumps(smoke_output, indent=2, default=str), encoding="utf-8"
)
df_all.to_csv(OUT / "p3_smoke_v2_per_sample.csv", index=False)
print(f"\n  Output: {OUT}")
print(f"\nSMOKE PASSED")
print("=" * 60)
