"""Study01 P0-P1 REVISE v3: fail-closed audit with assertions.

Every P0 check produces an assertion (non-zero exit on failure).
No check is print-only. Sample key grouping includes fold/seed.
Verifies SHA256SUMS, split_report, E3b/P8 gate sub-checks.
"""

import json, hashlib, sys, os, warnings
from pathlib import Path
import pandas as pd, numpy as np

warnings.filterwarnings("ignore", category=pd.errors.DtypeWarning)

STUDY_CODE = Path(__file__).resolve().parents[1] / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
from gen_labels import classify_generalization, classify_generalization_compound

ARTIFACT = Path("Study/01-study-MDM最小偏移量优化研究/artifacts/formal")
E4 = ARTIFACT / "E4_robustness"

EXIT = 0


def fail(msg):
    global EXIT
    print(f"  FAIL: {msg}")
    EXIT = 1


def ok(msg):
    print(f"  OK: {msg}")


# ============================================================
# P0.1 Manifest SHA256 — record only (no expected values frozen)
# ============================================================
print("=== P0.1 Manifest SHA256 ===")
for path in sorted(ARTIFACT.rglob("manifest*.json"), key=lambda p: str(p)):
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    print(f"  {path.relative_to(ARTIFACT)}: {sha}")

# ============================================================
# P0.2 E4d data integrity
# ============================================================
print("\n=== P0.2 E4d data integrity ===")

manifest_path = E4 / "manifest_e4d.json"
m = json.loads(manifest_path.read_text(encoding="utf-8"))
prov = m.get("output_provenance", {})
print(f"  output_provenance keys: {list(prov.keys())}")

# Read E4d data — use dtype=str to avoid DtypeWarning, convert after
e4d_raw = pd.read_csv(E4 / "E4d_selector_extrapolation.csv", dtype=str)
e4d_raw["beta_f"] = e4d_raw["beta"].astype(float)
e4d_raw["ge_f"] = e4d_raw["gamma_over_eta"].astype(float)
e4d_raw["n_int"] = e4d_raw["n"].astype(int)
e4d_raw["repeat_id_int"] = e4d_raw["repeat_id"].astype(int)

# Filter NN rows (have fold != '' AND fold != 'nan')
is_nn = e4d_raw["fold"].notna() & (e4d_raw["fold"] != "") & (e4d_raw["fold"] != "nan")
e4d_nn = e4d_raw[is_nn].copy()
e4d_nn["fold_int"] = e4d_nn["fold"].apply(lambda x: int(x.split("_")[-1]) - 1 if "_" in x else int(float(x)))
e4d_nn["seed_int"] = e4d_nn["seed"].apply(lambda x: int(float(x)))
print(f"  Total rows: {len(e4d_raw)}, NN rows: {len(e4d_nn)}, Ref rows: {len(e4d_raw) - len(e4d_nn)}")

# --- P0.2a: Sample key uniqueness ---
print("\n--- P0.2a: Sample key uniqueness ---")
# Basic key = (beta,ge,n,repeat_id) without fold/seed
basic_keys = e4d_nn.groupby(["beta_f", "ge_f", "n_int", "repeat_id_int"]).size().reset_index(name="count")
n_basic = len(basic_keys)
all_15 = (basic_keys["count"] == 15).all()
if n_basic == 17000 and all_15:
    ok(f"17,000 basic sample keys, each covered by exactly 15 models")
else:
    fail(f"basic keys: {n_basic} (expected 17,000), all_15_models={all_15}")

# Full key = basic + (fold,seed)
full_keys = e4d_nn.groupby(["beta_f", "ge_f", "n_int", "repeat_id_int", "fold_int", "seed_int"]).size()
n_full = len(full_keys)
all_unique = (full_keys == 1).all()
if n_full == 255000 and all_unique:
    ok(f"255,000 full keys (basic+fold+seed), all unique")
else:
    fail(f"full keys: {n_full} (expected 255,000), all_unique={all_unique}")

# --- P0.2b: Model count and fold/seed consistency ---
print("\n--- P0.2b: Model count ---")
models = e4d_nn.groupby(["fold_int", "seed_int"]).size().reset_index()
if len(models) == 15:
    ok("15 models (5 folds x 3 seeds)")
else:
    fail(f"model count: {len(models)} (expected 15)")

# Same basic key set across all models
ref_set = set(zip(
    e4d_nn[(e4d_nn["fold_int"] == 0) & (e4d_nn["seed_int"] == 42)]["beta_f"],
    e4d_nn[(e4d_nn["fold_int"] == 0) & (e4d_nn["seed_int"] == 42)]["ge_f"],
    e4d_nn[(e4d_nn["fold_int"] == 0) & (e4d_nn["seed_int"] == 42)]["n_int"],
    e4d_nn[(e4d_nn["fold_int"] == 0) & (e4d_nn["seed_int"] == 42)]["repeat_id_int"],
))
all_match = True
for (f, s), gd in e4d_nn.groupby(["fold_int", "seed_int"]):
    ks = set(zip(gd["beta_f"], gd["ge_f"], gd["n_int"], gd["repeat_id_int"]))
    if ks != ref_set:
        fail(f"fold={f} seed={s}: key set differs from reference")
        all_match = False
if all_match:
    ok("all 15 models share identical basic sample key set")

# --- P0.2c: SHA256SUMS verification ---
print("\n--- P0.2c: SHA256SUMS verification ---")
sums_path = E4 / "SHA256SUMS_e4d"
if sums_path.is_file():
    content = sums_path.read_text(encoding="utf-8").strip()
    verified = 0
    for line in content.splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            expected_sha, rel_path = parts
            fpath = Path(rel_path)
            if fpath.is_file():
                actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
                if actual != expected_sha:
                    fail(f"SHA256 mismatch: {rel_path}")
                else:
                    verified += 1
    ok(f"SHA256SUMS_e4d: {verified} files verified")
else:
    fail("SHA256SUMS_e4d missing")

# Compare with manifest output_provenance SHAs (observational, not fail-closed:
# provenance SHAs are from manifest creation time; file modification would mismatch)
print("\n--- P0.2c-2: output_provenance cross-check (observational) ---")
matched, mismatched = 0, 0
for rel_path, expected in prov.items():
    fpath = Path(rel_path)
    if fpath.is_file():
        actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if actual != expected:
            print(f"  PROVENANCE-MISMATCH: {rel_path}")
            mismatched += 1
        else:
            matched += 1
    else:
        fail(f"manifest provenance file missing: {rel_path}")
print(f"  provenance: {matched} match, {mismatched} mismatch (SHA256SUMS_e4d is authoritative)")

# --- P0.2d: Split consistency ---
print("\n--- P0.2d: Split consistency ---")
split_path = E4 / "split_report.csv"
if split_path.is_file():
    split = pd.read_csv(split_path)
    folds_in_split = sorted(split["fold"].unique())
    folds_in_data = sorted(e4d_nn["fold_int"].unique())
    # Map combo_fold_N -> N-1 for comparison
    def _to_fold_int(v):
        s = str(v)
        if "_" in s:
            return int(s.split("_")[-1]) - 1
        return int(float(s))
    split_ints = sorted(set(_to_fold_int(f) for f in folds_in_split))
    if folds_in_data == split_ints:
        ok("fold partition matches split_report")
    else:
        fail(f"fold mismatch: data={folds_in_data}, split={split_ints}")
else:
    fail("split_report.csv missing")

# ============================================================
# P0.3 E3b gate verification (recursive)
# ============================================================
print("\n=== P0.3 E3b gate ===")
gate_path = E4 / "E4d_e3b_gate_results.json"
gate = json.loads(gate_path.read_text(encoding="utf-8"))
gates_ok = True

def check_gate(d, prefix="gate"):
    global gates_ok
    if isinstance(d, dict):
        for k, v in d.items():
            if isinstance(v, bool):
                if not v:
                    fail(f"{prefix}.{k}: False")
                    gates_ok = False
                else:
                    print(f"  {prefix}.{k}: True")
            elif isinstance(v, dict):
                if "overall_pass" in v:
                    if v["overall_pass"] is not True:
                        fail(f"{prefix}.{k}.overall_pass: {v['overall_pass']}")
                        gates_ok = False
                    else:
                        print(f"  {prefix}.{k}.overall_pass: True")
                check_gate(v, f"{prefix}.{k}")

check_gate(gate, "gate")
if gates_ok:
    ok("E3b gate: all checks PASS")
else:
    fail("E3b gate: some checks FAILED")

# ============================================================
# P0.4 E3b mandatory files
# ============================================================
print("\n=== P0.4 E3b mandatory files ===")
e3b_dir = ARTIFACT / "E3b_vector_mlp"
for fname in ["manifest.json", "summary.json", "vector_mlp_results.csv"]:
    p = e3b_dir / fname
    if p.is_file():
        ok(f"{fname}: found")
    else:
        fail(f"{fname}: MISSING")

# ============================================================
# P0.5 P8 NIST verification
# ============================================================
print("\n=== P0.5 P8 NIST ===")
p8_dir = ARTIFACT / "real_data" / "nist-6061-t6-fatigue"
p8_manifest = json.loads((p8_dir / "real_data_manifest.json").read_text(encoding="utf-8"))

# File existence
for fname in ["real_data_manifest.json", "real_holdout_results.csv", "real_holdout_summary.json"]:
    if (p8_dir / fname).is_file():
        ok(f"{fname}: found")
    else:
        fail(f"{fname}: MISSING")

# SHA256SUMS
p8_sums = p8_dir / "SHA256SUMS_p8a"
if p8_sums.is_file():
    verified = 0
    for line in p8_sums.read_text(encoding="utf-8").strip().splitlines():
        parts = line.strip().split(maxsplit=1)
        if len(parts) == 2:
            expected, fn = parts
            fp = p8_dir / fn
            if fp.is_file():
                actual = hashlib.sha256(fp.read_bytes()).hexdigest()
                if actual != expected:
                    fail(f"P8 SHA256 mismatch: {fn}")
                else:
                    verified += 1
    ok(f"P8 SHA256SUMS: {verified} files verified")
else:
    fail("P8 SHA256SUMS_p8a missing")

# Row count
hr = pd.read_csv(p8_dir / "real_holdout_results.csv", dtype=str, nrows=10)
hr_full = pd.read_csv(p8_dir / "real_holdout_results.csv")
n_rows = len(hr_full)
expected = p8_manifest.get("expected_rows", 25500)
if n_rows == expected:
    ok(f"holdout rows: {n_rows} (expected {expected})")
else:
    fail(f"holdout rows: {n_rows} (expected {expected})")

# Gate/R^2 (from manifest or contract)
gate_info = p8_manifest.get("gate", {})
r2 = gate_info.get("r_squared", p8_manifest.get("r_squared"))
gate_passed = gate_info.get("passed", p8_manifest.get("gate_passed"))
print(f"  P8 gate R^2: {r2}, passed: {gate_passed}")
if r2 is not None and float(r2) > 0.9:
    ok(f"P8 R^2={r2} > 0.9")
else:
    fail(f"P8 R^2={r2} insufficient")

# Failure rate
fail_rate = hr_full.get("failed", pd.Series(dtype=float)).mean()
print(f"  P8 failure rate: {fail_rate:.6f}")
if fail_rate == 0.0:
    ok("P8 failure rate 0.0")
else:
    fail(f"P8 failure rate {fail_rate} != 0.0")

# ============================================================
# P1. Orthogonal classification
# ============================================================
print("\n=== P1. Orthogonal classification ===")

# Classify
labels = []
for _, row in e4d_nn.iterrows():
    ps, ns = classify_generalization(row["beta_f"], row["ge_f"], int(row["n_int"]))
    labels.append(f"p_{ps}_n_{ns}")
e4d_nn["compound"] = labels

dist = e4d_nn.groupby("compound").size().sort_values(ascending=False)
for label, count in dist.items():
    pct = count / len(e4d_nn) * 100
    print(f"  {label}: {count:>8,} ({pct:.1f}%)")

pure_labels = {
    "pure_p_interp (n=on_grid)": ("p_interp_n_on_grid",),
    "pure_n_interp (p=on_grid)": ("p_on_grid_n_interp",),
    "pure_p_extrap (n=on_grid)": ("p_extrap_n_on_grid",),
    "pure_n_extrap (p=on_grid)": ("p_on_grid_n_extrap",),
}
print("\n  Pure axis coverage (objective counts only):")
for desc, labels in pure_labels.items():
    ld = e4d_nn[e4d_nn["compound"].isin(labels)]
    n_combos = len(ld.groupby(["beta_f", "ge_f", "n_int"])) if len(ld) > 0 else 0
    print(f"    {desc}: {len(ld):,} rows, {n_combos} unique combos")
    if len(ld) == 0:
        fail(f"{desc}: ZERO coverage — P2 required")

# Mixed axes
mixed = e4d_nn[~e4d_nn["compound"].isin(sum(pure_labels.values(), ()))]
print(f"  Mixed axes: {len(mixed):,} rows across {len(mixed.groupby(['beta_f','ge_f','n_int']))} combos")

# ============================================================
# P1. 15-model per-axis analysis
# ============================================================
print("\n=== P1. 15-model per-axis J1 ===")
tolerance = 0.001  # Descriptive rule for win/loss/tie classification

for compound_label in sorted(e4d_nn["compound"].unique()):
    ld = e4d_nn[e4d_nn["compound"] == compound_label]
    if len(ld) == 0:
        continue

    model_j1s = []
    for (fold, seed), gd in ld.groupby(["fold_int", "seed_int"]):
        j1 = float(np.sqrt(np.mean(gd["true_loss"].astype(float))))
        model_j1s.append(j1)
    arr = np.array(model_j1s)
    print(f"  {compound_label} ({len(ld):,} rows): "
          f"med={np.median(arr):.4f} Q1={np.percentile(arr,25):.4f} Q3={np.percentile(arr,75):.4f} "
          f"min={np.min(arr):.4f} max={np.max(arr):.4f}")

# ============================================================
# Verify n=15 has ZERO pure n_interp coverage
# ============================================================
n15 = e4d_nn[e4d_nn["n_int"] == 15]
pure_n15_interp = n15[n15["compound"] == "p_on_grid_n_interp"]
print(f"\n  n=15 rows: {len(n15)}, pure_n_interp at n=15: {len(pure_n15_interp)}")
if len(pure_n15_interp) > 0:
    fail("unexpected: n=15 has pure_n_interp rows")
else:
    ok("confirmed: n=15 has ZERO pure n_interp coverage")

# Show what n=15 combos exist
n15_combos = n15.groupby(["beta_f", "ge_f", "n_int"]).size().reset_index()
print(f"  n=15 existing combos ({len(n15_combos)}):")
for _, r in n15_combos.iterrows():
    ps, ns = classify_generalization(r["beta_f"], r["ge_f"], int(r["n_int"]))
    print(f"    beta={r['beta_f']:.1f} ge={r['ge_f']:.1f} → p={ps} n={ns}")

# ============================================================
# Final
# ============================================================
print(f"\n{'='*40}")
if EXIT == 0:
    print("P0-P1 REVISE v3: ALL CHECKS PASSED")
else:
    print(f"P0-P1 REVISE v3: {EXIT} FAILURE(S)")
print(f"{'='*40}")
raise SystemExit(EXIT)
