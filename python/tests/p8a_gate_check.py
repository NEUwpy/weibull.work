"""P8a unified gate check — run before formal experiment."""
import sys, os, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..',
    'Study', '01-study-MDM最小偏移量优化研究', 'code'))

from config import ARTIFACTS_DIR, SHARED_DATA_DIR, DELTA_GRID
from run_real_data_validation import (
    verify_input_hashes, validate_preflight, check_output_safety,
    compute_frozen_config_sha256, get_git_info, DEFAULT_OUTPUT_DIR,
    L2_DELTAS, N_FOLDS, STABILITY_SEEDS, TRAIN_N_VALUES, N_REPEATS,
    _P8A_FORMAL_AUTHORIZED,
)
from real_data_gate import run_real_data_gate

errors = []

print("=" * 60)
print("P8a UNIFIED GATE CHECK")
print("=" * 60)

# 1. Authorization
print("\n1. P8a Authorization:", "OK" if _P8A_FORMAL_AUTHORIZED else "FAIL")
if not _P8A_FORMAL_AUTHORIZED:
    errors.append("P8A_FORMAL_AUTHORIZED is False")

# 2. Git
commit, dirty = get_git_info()
print(f"2. Git: commit={commit}, dirty={dirty}")
if dirty:
    errors.append("Git tree dirty")

# 3. P7 APPROVE
p7_path = os.path.join(os.getcwd(), "coworker", "reviews",
    "2026-07-25-study01xu-p7-codex-approve.md")
print(f"3. P7 APPROVE record: {'OK' if os.path.exists(p7_path) else 'MISSING'}")
if not os.path.exists(p7_path):
    errors.append("P7 APPROVE record missing")

# 4. Data SHA256
print("4. Data SHA256:")
data_dir = os.path.join(ARTIFACTS_DIR, "real_data", "nist-6061-t6-fatigue")
try:
    hashes = verify_input_hashes(data_dir)
    for k, v in hashes.items():
        ok = v.get("match", False)
        print(f"   {k}: {'MATCH' if ok else 'MISMATCH'}")
        if not ok:
            errors.append(f"SHA256 mismatch: {k}")
except Exception as e:
    print(f"   ERROR: {e}")
    errors.append(str(e))

# 5. Config SHA
sha = compute_frozen_config_sha256()
print(f"5. P6 config SHA256: {sha[:16] if sha else 'MISSING'}...")
if not sha:
    errors.append("Config SHA missing")

# 6. Gate
print("6. Admission Gate:")
gate = run_real_data_gate(data_dir)
print(f"   passed={gate.passed}, R2={gate.diagnostics['r_squared']:.4f}, n={gate.diagnostics['n_loaded']}")
if not gate.passed:
    errors.append(f"Gate failed: {gate.reason}")

# 7. Preflight
print("7. Preflight (chunks, L2, E4d):")
chunks_dir = os.path.join(SHARED_DATA_DIR, "chunks")
try:
    validate_preflight(data_dir, chunks_dir)
    print("   PASSED")
except Exception as e:
    print(f"   FAILED: {e}")
    errors.append(str(e))

# 8. Output safety
print("8. Output dir safety:")
try:
    check_output_safety(DEFAULT_OUTPUT_DIR)
    print(f"   CLEAN: {DEFAULT_OUTPUT_DIR}")
except Exception as e:
    print(f"   BLOCKED: {e}")
    errors.append(str(e))

# 9. Frozen params
print("9. Frozen parameters:")
checks = [
    ("L2 deltas", L2_DELTAS == {7: 0.10, 10: 0.10, 20: 0.08}),
    ("train_n", TRAIN_N_VALUES == [7, 10, 20]),
    ("n_repeats", N_REPEATS == 500),
    ("N_FOLDS", N_FOLDS == 5),
    ("STABILITY_SEEDS", STABILITY_SEEDS == [42, 2026, 3407]),
    ("delta_grid", len(DELTA_GRID) == 26),
]
for name, ok in checks:
    print(f"   {name}: {'OK' if ok else 'FAIL'}")
    if not ok:
        errors.append(f"Frozen param mismatch: {name}")

# 10. E4d manifest
print("10. E4d manifest:")
e4d_path = os.path.join(ARTIFACTS_DIR, "E4_robustness", "manifest_e4d.json")
with open(e4d_path) as f:
    e4d = json.load(f)
tc = e4d.get("training_contract", {})
checks2 = [
    ("total_models=15", tc.get("total_models") == 15),
    ("folds=5", tc.get("folds") == 5),
    ("training=main_grid_train_combos_only",
     tc.get("training_data") == "main_grid_train_combos_only"),
]
for name, ok in checks2:
    print(f"   {name}: {'OK' if ok else 'FAIL'}")
    if not ok:
        errors.append(f"E4d manifest mismatch: {name}")

# Final
print("\n" + "=" * 60)
if errors:
    print(f"GATE FAILED — {len(errors)} error(s):")
    for e in errors:
        print(f"  FAIL: {e}")
    sys.exit(1)
else:
    print("ALL GATES PASSED — ready for P8a formal run.")
    print(f"Execution commit: {commit}")
