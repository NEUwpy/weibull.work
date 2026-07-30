"""P3 smoke test: real end-to-end Direct-MLP training + six-method comparison.

Runs OUTSIDE the repository to prove the production path works.
Uses a small subset (1 fold × 1 seed, 2 combos × 5 repeats) — NOT formal results.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# Add code paths (these point to the repo, but the OUTPUT goes outside)
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

# ── Output directory (OUTSIDE repo) ────────────────────────────────────
OUT = Path(r"D:\weibull-local-artifacts\study01-p3-smoke")
OUT.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("P3 Direct-MLP Smoke Test")
print("=" * 60)

# ── 1. Build features for a small subset ───────────────────────────────
print("\n[1] Building sample features...")
rows = []
# Use 2 combos from the main grid, 10 repeats each
smoke_combos = [(1.5, 0.1, 7), (2.0, 0.5, 10)]
for beta, goe, n in smoke_combos:
    eta = 1.0
    gamma = goe * eta
    for rid in range(10):
        sample = generate_sample(beta, eta, gamma, n, rid, seed="study01_v1")
        feats = e4.compute_sample_features(sample)
        rows.append({
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n, "repeat_id": rid,
            **feats,
        })
df_features = pd.DataFrame(rows)
print(f"   Features: {len(df_features)} samples, {len(smoke_combos)} combos")

# ── 2. Train Direct-MLP on one combo, evaluate on the other ────────────
print("\n[2] Training Direct-MLP (1 fold, seed=42)...")
train_combos = [(1.5, 0.1, 7)]
X_train, Y_train, meta = direct.build_training_targets(df_features, train_combos)
print(f"   Train samples: {meta['n_train_samples']}")
print(f"   Y_train shape: {Y_train.shape}")
print(f"   Y_train beta range: [{Y_train[:,0].min():.3f}, {Y_train[:,0].max():.3f}]")

t0 = time.time()
model, target_scaler = direct.train_direct_mlp(X_train, Y_train, seed=42)
elapsed = time.time() - t0
print(f"   Training: {elapsed:.1f}s, n_iter={model.n_iter_}")

# ── 3. Evaluate Direct-MLP on test combo ───────────────────────────────
print("\n[3] Evaluating Direct-MLP on held-out combo...")
test_combo = (2.0, 0.5, 10)
mask = df_features.apply(
    lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) == test_combo,
    axis=1,
)
df_eval = df_features[mask]
direct_rows = direct.evaluate_on_samples(
    model, target_scaler, df_eval,
    meta["zscore_means"], meta["zscore_stds"],
    "smoke_fold", 42,
)

# Verify constraints
preds = np.array([[r["beta_hat"], r["eta_hat"], r["gamma_hat"]] for r in direct_rows])
constraints_ok = direct.verify_output_constraints(preds)
print(f"   Eval samples: {len(direct_rows)}")
print(f"   Output constraints satisfied: {constraints_ok}")
print(f"   Sample beta_hat: {direct_rows[0]['beta_hat']:.3f} (true={direct_rows[0]['beta']:.1f})")
print(f"   Sample loss: {direct_rows[0]['true_loss']:.4f}")

# ── 4. Run traditional methods on same samples ─────────────────────────
print("\n[4] Running traditional methods...")
all_rows = list(direct_rows)

for method_id in ["mle", "lse", "wmle"]:
    for beta, goe, n in [test_combo]:
        eta = 1.0
        gamma = goe * eta
        rows = compare.evaluate_traditional(method_id, beta, eta, gamma, n, repeats=10)
        all_rows.extend(rows)
        n_fail = sum(1 for r in rows if r["failed"])
        print(f"   {method_id.upper()}: {len(rows)} samples, {n_fail} failures")

# MDM-Default
for beta, goe, n in [test_combo]:
    rows = compare.evaluate_traditional("mdm", beta, eta, gamma, n, repeats=10)
    all_rows.extend(rows)
    n_fail = sum(1 for r in rows if r["failed"])
    print(f"   MDM-Default: {len(rows)} samples, {n_fail} failures")

# ── 5. Apply failure contract ──────────────────────────────────────────
penalty = 3.0  # Fixed for smoke
all_rows = compare.apply_failure_contract(all_rows, penalty)

# ── 6. Verify sample key alignment ─────────────────────────────────────
alignment = compare.verify_sample_key_alignment(all_rows)
print(f"\n[5] Sample key alignment: {alignment}")

# ── 7. Summaries ───────────────────────────────────────────────────────
print("\n[6] Method summaries:")
df_all = pd.DataFrame(all_rows)
for m in df_all["method"].unique():
    sub = df_all[df_all["method"] == m]
    losses = sub["true_loss"].values.astype(float)
    j1 = compare.pooled_j1(losses)
    n_fail = int(sub["failed"].sum())
    print(f"   {m:15s}: J1={j1:.4f}, n={len(sub)}, failures={n_fail}")

# ── 8. Save smoke output ───────────────────────────────────────────────
smoke_output = {
    "config_hash": direct.config_hash(),
    "smoke_combos": smoke_combos,
    "train_combo": train_combos[0],
    "test_combo": test_combo,
    "n_train_samples": meta["n_train_samples"],
    "n_eval_samples": len(direct_rows),
    "mlp_n_iter": model.n_iter_,
    "mlp_elapsed_s": elapsed,
    "output_constraints_ok": constraints_ok,
    "sample_key_alignment": alignment,
    "failure_penalty": penalty,
    "methods": list(df_all["method"].unique()),
    "total_rows": len(all_rows),
    "note": "Smoke test only — NOT formal results.",
}
output_path = OUT / "p3_smoke_result.json"
output_path.write_text(json.dumps(smoke_output, indent=2, default=str), encoding="utf-8")

# Also save per-sample rows
df_all.to_csv(OUT / "p3_smoke_per_sample.csv", index=False)

print(f"\n[7] Smoke output saved to: {output_path}")
print(f"    Per-sample CSV: {OUT / 'p3_smoke_per_sample.csv'}")

# ── 9. Final checks ────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("SMOKE CHECKS:")
print(f"  Config hash:      {smoke_output['config_hash'][:16]}...")
print(f"  Constraints:      {'PASS' if constraints_ok else 'FAIL'}")
print(f"  Key alignment:    {'PASS' if alignment else 'FAIL'}")
print(f"  Total methods:    {len(smoke_output['methods'])}")
print(f"  Total rows:       {smoke_output['total_rows']}")
print(f"  MLP converged:    {model.n_iter_} iters")
print("=" * 60)

assert constraints_ok, "Output constraints violated"
assert alignment, "Sample key alignment failed"
assert len(smoke_output["methods"]) >= 5, "Fewer than 5 methods ran"
print("\nSMOKE PASSED")
