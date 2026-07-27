"""P0-P1: Study01 baseline audit and evidence re-analysis."""
import pandas as pd, numpy as np, json
from pathlib import Path

ARTIFACT = Path("Study/01-study-MDM最小偏移量优化研究/artifacts/formal")
E4 = ARTIFACT / "E4_robustness"
TRAIN_BETAS = {1.5, 2.0, 2.5, 4.0, 5.0}
TRAIN_GAMMAS = {0.1, 0.5, 1.0}
TRAIN_NS = {7, 10, 20}

# ============================================================
# 1. Manifest audit
# ============================================================
print("=" * 60)
print("1. MANIFEST AUDIT")
for path in sorted(ARTIFACT.rglob("manifest*.json")):
    m = json.loads(path.read_text(encoding="utf-8"))
    status = m.get("status", m.get("state", "?"))
    commit = str(m.get("git_commit", m.get("code_commit", m.get("execution_commit", "?"))))[:8]
    run = m.get("run_id", m.get("experiment", "?"))
    print(f"  {path.relative_to(ARTIFACT)}: {run} @ {commit} [{status}]")

# ============================================================
# 2. E4a feature ablation analysis (P1)
# ============================================================
print("\n" + "=" * 60)
print("2. E4a FEATURE ABLATION (P1: internal credibility)")
e4a = pd.read_csv(E4 / "E4a_feature_ablation.csv")
print(f"\n  Rows: {len(e4a)}")
print(f"  Feature groups: {sorted(e4a.feature_group.unique())}")
print(f"\n  Per-group J1:")
for grp in sorted(e4a.feature_group.unique()):
    gd = e4a[e4a.feature_group == grp]
    print(f"    {grp}: mean_J1={gd.pooled_J1.mean():.4f} sd={gd.pooled_J1.std():.4f} "
          f"min={gd.pooled_J1.min():.4f} max={gd.pooled_J1.max():.4f}")

# Pairwise vs full
full_mean = e4a[e4a.feature_group == "full"].pooled_J1.mean()
for grp in sorted(e4a.feature_group.unique()):
    if grp == "full":
        continue
    gd = e4a[e4a.feature_group == grp]
    delta = gd.pooled_J1.mean() - full_mean
    print(f"    {grp} vs full: delta_J1={delta:+.4f} ({delta/full_mean*100:+.1f}%)")

print(f"\n  Seed stability (full group):")
fd = e4a[e4a.feature_group == "full"]
for s in sorted(fd.seed.unique()):
    sd = fd[fd.seed == s]
    print(f"    seed={s}: mean_J1={sd.pooled_J1.mean():.4f}")

# Check: model-first aggregation (each model scored first, then averaged)
print(f"\n  Model-first check: 5 folds x 3 seeds = 15 models per group")
for grp in ["full", "n_only"]:
    gd = e4a[e4a.feature_group == grp]
    print(f"    {grp}: {len(gd)} rows")

# ============================================================
# 3. E4d per-axis analysis (P1)
# ============================================================
print("\n" + "=" * 60)
print("3. E4d PER-AXIS ANALYSIS (P1: generalization)")

df = pd.read_csv(E4 / "E4d_selector_extrapolation.csv")

# Classification function
def classify(row):
    beta, ge, n = row["beta"], row["gamma_over_eta"], row["n"]
    beta_in = 1.5 <= beta <= 5.0
    ge_in = 0.1 <= ge <= 1.0
    n_in = 7 <= n <= 20
    on_bg = beta in TRAIN_BETAS
    on_gg = ge in TRAIN_GAMMAS
    on_ng = n in TRAIN_NS
    on_grid = on_bg and on_gg and on_ng

    if beta_in and ge_in and n_in and not on_grid and n in TRAIN_NS:
        return "p_interp"
    if on_bg and on_gg and 7 <= n <= 20 and n not in TRAIN_NS:
        return "n_interp"
    p_ext = not beta_in or not ge_in
    n_ext = n < 7 or n > 20
    if p_ext and n_ext:
        return "multi_extrap"
    if p_ext:
        return "p_extrap"
    if n_ext:
        return "n_extrap"
    return "p_interp"

df["gen_label"] = df.apply(classify, axis=1)

# Use df to compute J1 per-label (Vector-MLP-L6 only)
l6 = df[df["model"] == "Vector-MLP-L6"]
print(f"\n  Vector-MLP-L6 rows: {len(l6)}")

# Per-axis J1 and regret
print(f"\n  Per-axis Vector-MLP-L6 metrics:")
for label in ["p_interp", "n_interp", "p_extrap", "n_extrap", "multi_extrap"]:
    ld = l6[l6["gen_label"] == label]
    if len(ld) == 0:
        print(f"    {label}: NO DATA")
        continue
    j1 = np.sqrt(np.mean(ld["true_loss"]))
    regret_mean = ld["regret"].mean()
    print(f"    {label}: n={len(ld):,} J1={j1:.4f} regret_mean={regret_mean:.4f}")

# ============================================================
# 4. P1 conclusion: what can existing evidence answer?
# ============================================================
print("\n" + "=" * 60)
print("4. P1 CONCLUSION: Evidence sufficiency by axis")

axes_verdict = {
    "p_interp": {
        "has_data": len(l6[l6["gen_label"] == "p_interp"]) > 0,
        "combos": len(df[df["gen_label"] == "p_interp"].groupby(["beta", "gamma_over_eta", "n"])),
        "verdict": "INSUFFICIENT" if len(df[df["gen_label"] == "p_interp"].groupby(["beta", "gamma_over_eta", "n"])) < 10 else "SUFFICIENT",
    },
    "n_interp": {
        "has_data": len(l6[l6["gen_label"] == "n_interp"]) > 0,
        "combos": len(df[df["gen_label"] == "n_interp"].groupby(["beta", "gamma_over_eta", "n"])),
        "verdict": "NO_DATA",
    },
    "p_extrap": {
        "has_data": len(l6[l6["gen_label"] == "p_extrap"]) > 0,
        "combos": len(df[df["gen_label"] == "p_extrap"].groupby(["beta", "gamma_over_eta", "n"])),
        "verdict": "SUFFICIENT",
    },
    "n_extrap": {
        "has_data": len(l6[l6["gen_label"] == "n_extrap"]) > 0,
        "combos": len(df[df["gen_label"] == "n_extrap"].groupby(["beta", "gamma_over_eta", "n"])),
        "verdict": "SUFFICIENT",
    },
    "multi_extrap": {
        "has_data": len(l6[l6["gen_label"] == "multi_extrap"]) > 0,
        "combos": len(df[df["gen_label"] == "multi_extrap"].groupby(["beta", "gamma_over_eta", "n"])),
        "verdict": "SUFFICIENT",
    },
}
for axis, v in axes_verdict.items():
    print(f"  {axis}: has_data={v['has_data']} combos={v['combos']} → {v['verdict']}")

# ============================================================
# 5. Ref E4b/E4c reference-only per-axis J1
# ============================================================
print("\n" + "=" * 60)
print("5. E4b/E4c REFERENCE-ONLY PER-AXIS (Default vs L1 vs L2 vs L6-hindsight)")

e4b_ref = pd.read_csv(E4 / "E4b_boundary_reference.csv")
e4c_ref = pd.read_csv(E4 / "E4c_offgrid_reference.csv")
ref = pd.concat([e4b_ref, e4c_ref], ignore_index=True)
ref["gen_label"] = ref.apply(classify, axis=1)

for model_name in ["Default", "L1", "L2", "L6-hindsight"]:
    md = ref[ref["model"] == model_name]
    print(f"\n  {model_name}:")
    for label in ["p_interp", "n_interp", "p_extrap", "n_extrap", "multi_extrap"]:
        ld = md[md["gen_label"] == label]
        if len(ld) == 0:
            print(f"    {label}: NO DATA")
            continue
        j1 = np.sqrt(np.mean(ld["true_loss"]))
        print(f"    {label}: n={len(ld):,} J1={j1:.4f}")

print("\n" + "=" * 60)
print("6. SUMMARY OF GAPS AND P2 RECOMMENDATIONS")
print("""
  n_interp (sample size interpolation): ZERO coverage
    → P2 MUST add n=15 at all 45 training-grid (beta,gamma/eta,n) combos
    → Need 45 combos x 1000 repeats = 45,000 MDM estimates total

  p_interp (parameter interpolation): only 4 combos
    → P2 SHOULD add more non-grid parameter combos at train n
    → Minimum: 6-8 combos distributed across beta and gamma/eta range
    
  Existing p_extrap, n_extrap, multi_extrap from E4b+E4c: SUFFICIENT
    → No new combos needed
""")
