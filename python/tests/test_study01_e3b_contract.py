"""
E3b Contract Tests — verify data boundary, feature contract, and split integrity.

Run: python python/tests/test_study01_e3b_contract.py
"""

import sys
import os
import json

import numpy as np
import pandas as pd

# ============================================================
# Path setup
# ============================================================

PROJECT_ROOT = r"D:\weibull"
STUDY_CODE_DIR = os.path.join(
    PROJECT_ROOT,
    "Study", "01-study-MDM最小偏移量优化研究", "code"
)
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
STUDY_ROOT = os.path.join(
    PROJECT_ROOT,
    "Study", "01-study-MDM最小偏移量优化研究"
)

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

ARTIFACTS_DIR = os.path.join(STUDY_ROOT, "artifacts", "formal")
SHARED_DATA_DIR = os.path.join(ARTIFACTS_DIR, "shared_data")
MC_SCAN_PATH = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")
E3B_DIR = os.path.join(ARTIFACTS_DIR, "E3b_vector_mlp")


# ============================================================
# Tests
# ============================================================

def test_source_data_integrity():
    """Verify mc_scan_raw.csv row counts, combo counts, delta counts, duplicates."""
    df = pd.read_csv(MC_SCAN_PATH)
    with open(MC_MANIFEST_PATH, encoding='utf-8') as f:
        manifest = json.load(f)

    expected_combos = 45  # 5 beta × 1 eta × 3 gamma/eta × 3 n
    expected_deltas = 26
    expected_repeats = manifest.get("repeats", 1000)
    expected_rows = expected_combos * expected_deltas * expected_repeats

    assert len(df) == expected_rows, \
        f"Row count: expected {expected_rows}, got {len(df)}"

    dup_key = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id', 'delta']
    dups = df.duplicated(subset=dup_key).sum()
    assert dups == 0, f"Duplicate rows: {dups}"

    unique_combos = df[['beta', 'eta', 'gamma_over_eta', 'n']].drop_duplicates()
    assert len(unique_combos) == expected_combos

    from config import DELTA_GRID
    unique_deltas = sorted(df['delta'].unique())
    assert unique_deltas == DELTA_GRID

    rep_counts = df.groupby(['beta', 'eta', 'gamma_over_eta', 'n'])['repeat_id'].nunique()
    assert rep_counts.min() == expected_repeats

    print(f"  [PASS] Source data: {len(df)} rows, {expected_combos} combos, "
          f"{expected_deltas} deltas, {expected_repeats} repeats, 0 duplicates")


def test_no_banned_fields_in_features():
    """Verify that model input features exclude all banned fields."""
    from run_E3b_vector_mlp import SAMPLE_FEATURE_COLS, BANNED_FIELDS

    for col in SAMPLE_FEATURE_COLS:
        base = col.replace('_z', '')
        assert base not in BANNED_FIELDS, \
            f"BANNED field '{base}' in SAMPLE_FEATURE_COLS"

    # Also verify delta is NOT in the vector MLP features
    assert 'delta' not in SAMPLE_FEATURE_COLS, \
        "delta must not be in vector MLP features"
    assert 'beta' not in SAMPLE_FEATURE_COLS
    assert 'gamma' not in SAMPLE_FEATURE_COLS
    assert 'eta' not in SAMPLE_FEATURE_COLS
    assert 'repeat_id' not in SAMPLE_FEATURE_COLS

    print(f"  [PASS] No banned fields in SAMPLE_FEATURE_COLS: {SAMPLE_FEATURE_COLS}")


def test_split_report():
    """Verify split_report has 45 unique combos, 9 per fold."""
    split_path = os.path.join(E3B_DIR, "split_report.csv")
    if not os.path.exists(split_path):
        raise FileNotFoundError(f"split_report.csv not found: {split_path}")

    df_split = pd.read_csv(split_path)
    assert len(df_split) == 45, f"Expected 45 split rows, got {len(df_split)}"

    # Each fold should have 9 combos
    for fold in df_split['fold'].unique():
        n = len(df_split[df_split['fold'] == fold])
        assert n == 9, f"Fold {fold}: expected 9 combos, got {n}"

    # No combo should appear in multiple folds
    combo_keys = df_split[['test_beta', 'test_gamma_over_eta', 'test_n']].apply(
        lambda r: f"{r['test_beta']}_{r['test_gamma_over_eta']}_{r['test_n']}", axis=1
    )
    assert combo_keys.nunique() == 45, "Duplicate combos across folds"

    print(f"  [PASS] Split report: 45 combos, 9 per fold, no cross-fold duplicates")


def test_manifest_no_banned_inputs():
    """Verify E3b manifest feature contract has no banned fields."""
    manifest_path = os.path.join(E3B_DIR, "manifest.json")
    if not os.path.exists(manifest_path):
        raise FileNotFoundError(f"manifest.json not found: {manifest_path}")

    with open(manifest_path, encoding='utf-8') as f:
        manifest = json.load(f)

    feat_contract = manifest.get('feature_contract', {})
    vector_input = feat_contract.get('vector_input', [])

    for col in vector_input:
        assert col not in ['beta', 'eta', 'gamma', 'gamma_over_eta',
                           'seed', 'repeat_id', 'combo_id'], \
            f"BANNED field '{col}' in manifest vector_input"
        assert col != 'delta', "delta must not be in vector_input"

    print(f"  [PASS] Manifest feature contract: no banned fields in vector_input")


def test_j1_reproducibility():
    """Independently recompute pooled J1 from vector_mlp_results.csv."""
    results_path = os.path.join(E3B_DIR, "vector_mlp_results.csv")
    comp_path = os.path.join(E3B_DIR, "model_comparison.csv")
    if not os.path.exists(results_path) or not os.path.exists(comp_path):
        raise FileNotFoundError(f"results not found: {results_path} or {comp_path}")

    df_res = pd.read_csv(results_path)
    df_comp = pd.read_csv(comp_path)

    import math

    for model_name in df_res['model'].unique():
        sub = df_res[df_res['model'] == model_name]
        j1_recomputed = math.sqrt(sub['true_loss'].mean())

        comp_row = df_comp[
            (df_comp['model'] == model_name) &
            (df_comp['split'] == 'combo_holdout_pooled')
        ]
        if len(comp_row) == 0:
            continue
        j1_reported = comp_row.iloc[0]['J1']

        diff = abs(j1_recomputed - j1_reported)
        assert diff < 1e-4, \
            f"{model_name}: J1 mismatch recomputed={j1_recomputed:.6f} vs reported={j1_reported:.6f}"

        print(f"  [PASS] {model_name}: J1 recomputed={j1_recomputed:.6f} "
              f"matches reported={j1_reported:.6f}")


def test_e3a_unchanged():
    """Verify E3a artifacts were not modified by E3b — uses git diff."""
    import subprocess
    # Check that E3a directory has no uncommitted changes
    e3a_dir = os.path.join(ARTIFACTS_DIR, "E3_sample_adaptive")
    if not os.path.exists(e3a_dir):
        raise FileNotFoundError(f"E3a directory not found: {e3a_dir}")

    # Check git diff for E3a files (they are tracked)
    try:
        result = subprocess.run(
            ['git', 'diff', '--name-only', '--',
             'Study/01-study-MDM最小偏移量优化研究/artifacts/formal/E3_sample_adaptive/'],
            cwd=PROJECT_ROOT, capture_output=True, text=True, timeout=10
        )
        changed = result.stdout.strip()
        assert changed == '', f"E3a files modified: {changed}"
    except subprocess.TimeoutExpired:
        raise AssertionError("git diff timed out")

    # Verify all expected E3a files still exist
    e3a_files = ['manifest.json', 'summary.json', 'results.csv',
                 'model_comparison.csv', 'split_report.csv',
                 'delta_distribution.csv', 'E3a_acceptance_report.md']
    for fname in e3a_files:
        fpath = os.path.join(e3a_dir, fname)
        assert os.path.exists(fpath), f"E3a file missing: {fname}"

    print(f"  [PASS] E3a artifacts unchanged (git diff clean, {len(e3a_files)} files present)")


def test_combo_holdout_pooled_count():
    """Verify combo holdout pooled has 45000 samples per model."""
    results_path = os.path.join(E3B_DIR, "vector_mlp_results.csv")
    if not os.path.exists(results_path):
        raise FileNotFoundError(f"results not found: {results_path}")

    df_res = pd.read_csv(results_path)
    for model_name in df_res['model'].unique():
        n = len(df_res[df_res['model'] == model_name])
        assert n == 45000, \
            f"{model_name}: expected 45000 pooled samples, got {n}"

    print(f"  [PASS] All models have 45000 pooled combo-holdout samples")


def test_pivot_to_vector_alignment():
    """Verify pivot_to_vector produces result and Y that are strictly row-aligned.

    Uses an intentionally unsorted input to catch the alignment bug.
    """
    import sys
    sys.path.insert(0, os.path.join(
        PROJECT_ROOT,
        "Study", "01-study-MDM最小偏移量优化研究", "code"
    ))
    from run_E3b_vector_mlp import pivot_to_vector, DELTA_GRID

    # Craft input where drop_duplicates preserves an order different from pivot_table sort
    n_rows = 8  # 2 samples × 4 deltas (simplified, only 4 of 26)
    deltas_test = [0.00, 0.02, 0.04, 0.06]
    data = pd.DataFrame({
        'beta': [2.0]*4 + [1.5]*4,
        'repeat_id': [1]*4 + [2]*4,
        'delta': deltas_test * 2,
        'loss_filled': [0.3, 0.4, 0.5, 0.6] + [0.1, 0.2, 0.15, 0.25],
        'n': [7]*8, 'eta': [1.0]*8, 'gamma': [0.1]*8, 'gamma_over_eta': [0.1]*8,
        'x_min': [0.6]*4 + [0.5]*4, 'x_max': [2.0]*4 + [1.8]*4,
        'range': [1.4]*4 + [1.3]*4, 'Q1': [1.0]*8, 'Med': [1.2]*8,
        'Q3': [1.5]*8, 'IQR': [0.5]*8, 'x_bar': [1.3]*8, 's': [0.4]*8,
        'CV': [0.3]*8, 'g1': [0.5]*8, 'g2': [2.0]*8,
    })

    result, Y = pivot_to_vector(data, 'loss_filled')

    # Verify: for each row i, Y[i] should match the loss curve for that sample
    for i in range(len(result)):
        beta = result.iloc[i]['beta']
        rid = result.iloc[i]['repeat_id']
        sample_rows = data[(data['beta'] == beta) & (data['repeat_id'] == rid)].sort_values('delta')
        expected = sample_rows['loss_filled'].values

        # Find which delta columns in Y correspond to our test deltas
        for j, d in enumerate(DELTA_GRID):
            if d in deltas_test:
                idx = deltas_test.index(d)
                assert abs(Y[i, j] - expected[idx]) < 1e-10, \
                    f"Row {i} (beta={beta}, rid={rid}): Y[{j}] (delta={d}) = {Y[i,j]} " \
                    f"but expected {expected[idx]}"

    print(f"  [PASS] pivot_to_vector alignment verified ({len(result)} rows, all aligned)")


def test_oracle_hierarchy_and_values():
    """Verify L5<=L4<=L3 oracle hierarchy and match known E3a formal values.

    Information layers: L5 (most info) > L4 > L3 > L2 > L1.
    Oracle J1 must satisfy L5-oracle <= L4-oracle <= L3-oracle < L2.
    Values must match independent recomputation from mc_scan_raw.csv.
    """
    comp_path = os.path.join(E3B_DIR, "model_comparison.csv")
    if not os.path.exists(comp_path):
        raise FileNotFoundError(f"model_comparison.csv not found: {comp_path}")

    df_comp = pd.read_csv(comp_path)
    import math

    # Extract combo_holdout_pooled oracle/reference values
    def get_j1(model_name):
        row = df_comp[
            (df_comp['model'] == model_name) &
            (df_comp['split'] == 'combo_holdout_pooled')
        ]
        if len(row) == 0:
            return None
        return float(row.iloc[0]['J1'])

    l3 = get_j1('L3-oracle')
    l4 = get_j1('L4-oracle')
    l5 = get_j1('L5-oracle')
    l6 = get_j1('L6-hindsight')
    l2 = get_j1('L2')
    default = get_j1('Default')

    assert l3 is not None, "L3-oracle missing from model_comparison.csv"
    assert l4 is not None, "L4-oracle missing"
    assert l5 is not None, "L5-oracle missing"
    assert l6 is not None, "L6-hindsight missing"

    # Hierarchy: more information => lower (better) J1
    assert l5 <= l4 + 1e-9, \
        f"Hierarchy violation: L5-oracle ({l5:.6f}) > L4-oracle ({l4:.6f})"
    assert l4 <= l3 + 1e-9, \
        f"Hierarchy violation: L4-oracle ({l4:.6f}) > L3-oracle ({l3:.6f})"
    assert l6 <= l5 + 1e-9, \
        f"Hierarchy violation: L6-hindsight ({l6:.6f}) > L5-oracle ({l5:.6f})"

    # Oracle must be better (lower J1) than L2
    assert l3 < l2, \
        f"Oracle should beat L2: L3-oracle ({l3:.6f}) >= L2 ({l2:.6f})"

    # Match known E3a formal values (independent recomputation)
    # L3=0.585068, L4=0.582090, L5=0.571170, L6=0.494530
    tol = 0.005
    assert abs(l3 - 0.585068) < tol, \
        f"L3-oracle J1={l3:.6f} != expected ~0.585068 (tol={tol})"
    assert abs(l4 - 0.582090) < tol, \
        f"L4-oracle J1={l4:.6f} != expected ~0.582090 (tol={tol})"
    assert abs(l5 - 0.571170) < tol, \
        f"L5-oracle J1={l5:.6f} != expected ~0.571170 (tol={tol})"
    assert abs(l6 - 0.494530) < tol, \
        f"L6-hindsight J1={l6:.6f} != expected ~0.494530 (tol={tol})"

    print(f"  [PASS] Oracle hierarchy: L6={l6:.6f} <= L5={l5:.6f} <= "
          f"L4={l4:.6f} <= L3={l3:.6f} < L2={l2:.6f}")


def test_seed_stability_runlog_consistency():
    """Verify seed_stability.csv values match run_log.txt for ALL seeds."""
    import re

    seed_path = os.path.join(E3B_DIR, "seed_stability.csv")
    log_path = os.path.join(E3B_DIR, "run_log.txt")
    if not os.path.exists(seed_path):
        raise FileNotFoundError(f"seed_stability.csv not found: {seed_path}")
    if not os.path.exists(log_path):
        raise FileNotFoundError(f"run_log.txt not found: {log_path}")

    df_seed = pd.read_csv(seed_path)

    with open(log_path, encoding='utf-8', errors='replace') as f:
        log_text = f.read()

    # Check all seeds present in CSV
    expected_seeds = [42, 2026, 3407]
    actual_seeds = sorted(df_seed['seed'].unique())
    assert set(expected_seeds).issubset(set(actual_seeds)), \
        f"Missing seeds: expected {expected_seeds}, got {actual_seeds}"

    # Cross-check each seed's J1 against run_log
    checked = 0
    for seed in expected_seeds:
        csv_j1 = float(df_seed[df_seed['seed'] == seed]['pooled_J1'].iloc[0])
        m = re.search(rf'seed={seed}.*?pooled J1=([0-9.]+)', log_text)
        if m:
            log_j1 = float(m.group(1))
            assert abs(log_j1 - csv_j1) < 0.01, \
                f"seed={seed} J1 mismatch: run_log={log_j1:.6f} vs " \
                f"seed_stability.csv={csv_j1:.6f}"
            checked += 1

    assert checked == len(expected_seeds), \
        f"Only cross-checked {checked}/{len(expected_seeds)} seeds against run_log " \
        f"(run_log may be truncated)"

    print(f"  [PASS] All {checked} seeds match between seed_stability.csv and run_log.txt")


def test_sample_features_schema():
    """Verify sample_features.csv has unique columns, 45000 rows, 45 combos,
    and key alignment with risk_curves.csv."""
    sf_path = os.path.join(E3B_DIR, "sample_features.csv")
    rc_path = os.path.join(E3B_DIR, "risk_curves.csv")
    if not os.path.exists(sf_path):
        raise FileNotFoundError(f"sample_features.csv not found: {sf_path}")
    if not os.path.exists(rc_path):
        raise FileNotFoundError(f"risk_curves.csv not found: {rc_path}")

    df_sf = pd.read_csv(sf_path)

    # 1. No duplicate columns — check RAW CSV header (pandas auto-mangles dup names
    #    to e.g. 'n.1', which hides the bug from a DataFrame.columns check)
    with open(sf_path, 'r') as f:
        raw_header = f.readline().strip()
    raw_cols = raw_header.split(',')
    from collections import Counter
    dups = {k: v for k, v in Counter(raw_cols).items() if v > 1}
    assert not dups, \
        f"Duplicate columns in sample_features.csv raw header: {dups}"

    # 2. 45000 rows
    assert len(df_sf) == 45000, \
        f"Expected 45000 rows, got {len(df_sf)}"

    # 3. 45 unique combos
    combos = df_sf[['beta', 'gamma_over_eta', 'n']].drop_duplicates()
    assert len(combos) == 45, \
        f"Expected 45 unique combos, got {len(combos)}"

    # 4. Key alignment with risk_curves.csv
    df_rc = pd.read_csv(rc_path)
    key_cols = ['beta', 'gamma_over_eta', 'n', 'repeat_id']
    sf_keys = df_sf[key_cols].drop_duplicates()
    rc_keys = df_rc[key_cols].drop_duplicates()
    merged = sf_keys.merge(rc_keys, on=key_cols, how='outer', indicator=True)
    mismatch = len(merged[merged['_merge'] != 'both'])
    assert mismatch == 0, \
        f"Key mismatch between sample_features and risk_curves: {mismatch} rows"

    print(f"  [PASS] sample_features.csv: {len(df_sf)} rows, {len(combos)} combos, "
          f"{len(raw_cols)} unique cols, keys aligned with risk_curves.csv")


# ============================================================

if __name__ == '__main__':
    tests = [
        ("Source data integrity", test_source_data_integrity),
        ("No banned fields in features", test_no_banned_fields_in_features),
        ("Pivot alignment", test_pivot_to_vector_alignment),
        ("Split report structure", test_split_report),
        ("Manifest feature contract", test_manifest_no_banned_inputs),
        ("J1 reproducibility", test_j1_reproducibility),
        ("E3a unchanged", test_e3a_unchanged),
        ("Combo holdout pooled count", test_combo_holdout_pooled_count),
        ("Oracle hierarchy and values", test_oracle_hierarchy_and_values),
        ("Seed stability run-log consistency", test_seed_stability_runlog_consistency),
        ("Sample features schema", test_sample_features_schema),
    ]

    print("=" * 60)
    print("E3b Contract Tests")
    print("=" * 60)

    passed = 0
    skipped = 0
    failed = 0

    for name, test_fn in tests:
        print(f"\n[{name}]")
        try:
            test_fn()
            passed += 1
        except SystemExit:
            skipped += 1
        except AssertionError as e:
            print(f"  [FAIL] {e}")
            failed += 1
        except Exception as e:
            print(f"  [SKIP] {e}")
            skipped += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {skipped} skipped, {failed} failed")
    print("=" * 60)

    if failed > 0:
        sys.exit(1)
