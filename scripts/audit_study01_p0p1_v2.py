"""Study01 P0-P1 REVISE: comprehensive audit and per-model stratified analysis.

Uses orthogonal (parameter_state x n_state) classification.
Reports per-axis analysis with 15 model-level statistics.
Includes P0 verification: manifest SHA, sample keys, split consistency.
"""

import json, hashlib, csv, gzip, os
from pathlib import Path
import pandas as pd, numpy as np
import sys

STUDY_CODE = Path(__file__).resolve().parents[1] / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
from gen_labels import classify_generalization, classify_generalization_compound

ARTIFACT = Path("Study/01-study-MDM最小偏移量优化研究/artifacts/formal")
E4 = ARTIFACT / "E4_robustness"

# ============================================================
# P0. SUBSTANTIVE VERIFICATION
# ============================================================
print("=" * 70)
print("P0. SUBSTANTIVE VERIFICATION")
print("=" * 70)

# --- P0.1 Manifest SHA256 verification ---
print("\n--- P0.1 Manifest SHA256 verification ---")
for path in sorted(ARTIFACT.rglob("manifest*.json")):
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    print(f"  {path.relative_to(ARTIFACT)}: SHA256={sha}")

# --- P0.2 Sample key uniqueness and coverage ---
print("\n--- P0.2 Sample key uniqueness ---")
e4d = pd.read_csv(E4 / "E4d_selector_extrapolation.csv")
# Filter to NN model rows (have fold/seed); last ~40k rows are reference-only
e4d_nn = e4d[e4d["fold"].notna() & (e4d["fold"] != "")].copy()
e4d_nn["fold"] = e4d_nn["fold"].apply(lambda x: int(str(x).split("_")[-1]) - 1 if "_" in str(x) else int(float(x)))
e4d_nn["seed"] = e4d_nn["seed"].apply(lambda x: int(float(x)))
print(f"[E4d] Total rows: {len(e4d)}, NN rows: {len(e4d_nn)}, Ref-only rows: {len(e4d) - len(e4d_nn)}")

# Use NN rows for model-level analysis
e4d = e4d_nn
keys = e4d.groupby(["beta", "gamma_over_eta", "n", "repeat_id"]).size().reset_index(name="count")
dups = keys[keys["count"] > 1]
print(f"  Total unique (beta,ge,n,repeat): {len(keys)}")
print(f"  Duplicate keys: {len(dups)}")
if len(dups) > 0:
    print(f"  WARNING: duplicate keys found!")
    for _, row in dups.head(5).iterrows():
        print(f"    {row.to_dict()}")

# Check fold/seed coverage per key
print(f"\n  Fold/Seed coverage:")
for f in sorted(e4d["fold"].unique()):
    for s in sorted(e4d["seed"].unique()):
        fd = e4d[(e4d["fold"] == f) & (e4d["seed"] == s)]
        n_keys = len(fd.groupby(["beta", "gamma_over_eta", "n", "repeat_id"]))
        print(f"    fold={f} seed={s}: {n_keys} unique keys, {len(fd)} rows")

# Unique combos per fold×seed (should be identical)
combo_sets = {}
for f in sorted(e4d["fold"].unique()):
    for s in sorted(e4d["seed"].unique()):
        fd = e4d[(e4d["fold"] == f) & (e4d["seed"] == s)]
        cb = set(zip(fd["beta"], fd["gamma_over_eta"], fd["n"], fd["repeat_id"]))
        combo_sets[(f, s)] = cb

ref = combo_sets[(0, 42)]
all_same = all(v == ref for v in combo_sets.values())
print(f"  All fold×seed have same key set: {all_same}")

# --- P0.3 Model count (should be 15) ---
print(f"\n--- P0.3 Model count ---")
models = e4d.groupby(["fold", "seed"]).size().reset_index()
print(f"  Unique (fold,seed) pairs: {len(models)} (expected 15)")

# --- P0.4 E3b gate verification ---
print(f"\n--- P0.4 E3b gate ---")
gate = json.loads((E4 / "E4d_e3b_gate_results.json").read_text(encoding="utf-8"))
for k, v in gate.items():
    if isinstance(v, bool):
        print(f"  {k}: {'PASS' if v else 'FAIL'}")
    elif isinstance(v, dict):
        print(f"  {k}: {v.get('overall_pass', '?')}")

# --- P0.5 E3b manifest existence ---
print(f"\n--- P0.5 E3b artifacts ---")
e3b_dir = ARTIFACT / "E3b_vector_mlp"
for fname in ["manifest.json", "summary.json", "vector_mlp_results.csv"]:
    exists = (e3b_dir / fname).is_file()
    print(f"  {fname}: {'FOUND' if exists else 'MISSING'}")

# ============================================================
# P1. ORTHOGONAL CLASSIFICATION + PER-MODEL ANALYSIS
# ============================================================
print("\n" + "=" * 70)
print("P1. ORTHOGONAL CLASSIFICATION + 15-MODEL ANALYSIS")
print("=" * 70)

# Classify all E4d rows
labels = []
for _, row in e4d.iterrows():
    ps, ns = classify_generalization(row["beta"], row["gamma_over_eta"], int(row["n"]))
    compound = f"p_{ps}_n_{ns}"
    labels.append({"param_state": ps, "n_state": ns, "compound": compound})
label_df = pd.DataFrame(labels)
e4d_labelled = pd.concat([e4d, label_df], axis=1)

print(f"\n--- Classification distribution ---")
dist = e4d_labelled.groupby(["param_state", "n_state"]).size().reset_index(name="count")
for _, row in dist.iterrows():
    pct = row["count"] / len(e4d_labelled) * 100
    print(f"  p={row['param_state']:>6} n={row['n_state']:>6}: {row['count']:>8,} ({pct:.1f}%)")

# --- Per-model per-axis analysis (Vector-MLP-L6 only) ---
print(f"\n--- Per-model per-axis (Vector-MLP-L6, 15 models) ---")

l6 = e4d_labelled[e4d_labelled["model"] == "Vector-MLP-L6"].copy()

# Load E4b/E4c reference for Default/L1 paired comparison
e4b_ref = pd.read_csv(E4 / "E4b_boundary_reference.csv")
e4c_ref = pd.read_csv(E4 / "E4c_offgrid_reference.csv")
ref = pd.concat([e4b_ref, e4c_ref], ignore_index=True)
ref_labels = []
for _, row in ref.iterrows():
    ps, ns = classify_generalization(row["beta"], row["gamma_over_eta"], int(row["n"]))
    ref_labels.append({"param_state": ps, "n_state": ns, "compound": f"p_{ps}_n_{ns}"})
ref_labelled = pd.concat([ref, pd.DataFrame(ref_labels)], axis=1)

for compound_label in sorted(l6["compound"].unique()):
    ld = l6[l6["compound"] == compound_label]
    if len(ld) == 0:
        continue

    # Per-model J1 (15 models)
    model_j1s = []
    for (fold, seed), gd in ld.groupby(["fold", "seed"]):
        j1 = float(np.sqrt(np.mean(gd["true_loss"])))
        model_j1s.append(j1)

    arr = np.array(model_j1s)
    print(f"\n  {compound_label} (n={len(ld):,}):")
    print(f"    J1: min={np.min(arr):.4f} Q1={np.percentile(arr,25):.4f} "
          f"med={np.median(arr):.4f} Q3={np.percentile(arr,75):.4f} "
          f"max={np.max(arr):.4f} mean={np.mean(arr):.4f} SD={np.std(arr,ddof=1):.4f}")

    # Paired comparison with Default and L1 on common samples
    for ref_model in ["Default", "L1"]:
        rd = ref_labelled[(ref_labelled["model"] == ref_model) & (ref_labelled["compound"] == compound_label)]
        if len(rd) == 0:
            print(f"    vs {ref_model}: NO REFERENCE DATA")
            continue

        # Match on (beta, gamma_over_eta, n, repeat_id)
        merged = pd.merge(
            ld[["beta", "gamma_over_eta", "n", "repeat_id", "true_loss", "fold", "seed"]],
            rd[["beta", "gamma_over_eta", "n", "repeat_id", "true_loss"]],
            on=["beta", "gamma_over_eta", "n", "repeat_id"],
            suffixes=("_l6", "_ref"),
        )
        if len(merged) == 0:
            print(f"    vs {ref_model}: NO COMMON SAMPLES")
            continue

        # Per-model paired comparison
        wins, ties, losses = 0, 0, 0
        j1_diffs = []
        for (fold, seed), md in merged.groupby(["fold", "seed"]):
            l6_j1 = float(np.sqrt(np.mean(md["true_loss_l6"])))
            ref_j1 = float(np.sqrt(np.mean(md["true_loss_ref"])))
            diff = l6_j1 - ref_j1
            j1_diffs.append(diff)
            if diff < -0.001:
                wins += 1
            elif abs(diff) <= 0.001:
                ties += 1
            else:
                losses += 1

        diffs = np.array(j1_diffs)
        print(f"    vs {ref_model} (n_common={len(merged):,}):")
        print(f"      J1_diff: min={np.min(diffs):.4f} Q1={np.percentile(diffs,25):.4f} "
              f"med={np.median(diffs):.4f} Q3={np.percentile(diffs,75):.4f} "
              f"max={np.max(diffs):.4f} mean={np.mean(diffs):.4f}")
        print(f"      win/loss/tie (per-model): {wins}/{losses}/{ties}")

# --- P1.3 Pure axis isolation ---
print(f"\n--- Pure axis isolation (p_interp_n_on_grid, etc.) ---")
pure_axes = {
    "pure_p_interp": lambda ld: ld[(ld["param_state"] == "interp") & (ld["n_state"] == "on_grid")],
    "pure_n_interp": lambda ld: ld[(ld["param_state"] == "on_grid") & (ld["n_state"] == "interp")],
    "pure_p_extrap": lambda ld: ld[(ld["param_state"] == "extrap") & (ld["n_state"] == "on_grid")],
    "pure_n_extrap": lambda ld: ld[(ld["param_state"] == "on_grid") & (ld["n_state"] == "extrap")],
}
for name, func in pure_axes.items():
    ld = func(l6)
    n_combos = len(ld.groupby(["beta", "gamma_over_eta", "n"])) if len(ld) > 0 else 0
    print(f"  {name}: rows={len(ld):,} combos={n_combos}")
    if len(ld) > 0:
        j1 = float(np.sqrt(np.mean(ld["true_loss"])))
        print(f"    J1={j1:.4f}")
    else:
        print(f"    NO DATA")

# --- P0.6 P6 gate confirmation ---
print(f"\n--- P0.6 P8 NIST gate ---")
p8_dir = ARTIFACT / "real_data" / "nist-6061-t6-fatigue"
for fname in ["real_data_manifest.json", "real_holdout_results.csv", "real_holdout_summary.json"]:
    exists = (p8_dir / fname).is_file()
    print(f"  {fname}: {'FOUND' if exists else 'MISSING'}")

# Verify holdout row count
hr = pd.read_csv(p8_dir / "real_holdout_results.csv")
print(f"  holdout rows: {len(hr)} (expected 25,500)")
print(f"  failure rate: {hr['failed'].mean():.4f}")
assert len(hr) == 25500, f"Expected 25,500 rows, got {len(hr)}"

print("\n" + "=" * 70)
print("P0-P1 REVISE COMPLETE")
print("=" * 70)
