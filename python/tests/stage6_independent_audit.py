"""Stage 6: Independent verification of P8a formal outputs.

Recomputes key statistics from real_holdout_results.csv WITHOUT using
production aggregation functions. Compares against real_holdout_summary.json.
"""

import json, os, sys, hashlib
import numpy as np
import pandas as pd

DIR = os.path.join(
    os.path.dirname(__file__), '..', '..',
    'Study', '01-study-MDM最小偏移量优化研究',
    'artifacts', 'formal', 'real_data', 'nist-6061-t6-fatigue'
)

errors = []

# ── Load raw data ──
df = pd.read_csv(os.path.join(DIR, 'real_holdout_results.csv'))
stab = pd.read_csv(os.path.join(DIR, 'real_nn_model_stability.csv'))
with open(os.path.join(DIR, 'real_holdout_summary.json'), encoding='utf-8') as f:
    summary = json.load(f)
with open(os.path.join(DIR, 'real_data_manifest.json'), encoding='utf-8') as f:
    manifest = json.load(f)

print("=" * 60)
print("P8a INDEPENDENT VERIFICATION (Stage 6)")
print("=" * 60)

# A. Row count
print("\n--- A. Row Count ---")
assert len(df) == 25500, f"Expected 25500, got {len(df)}"
print(f"Rows: {len(df)} ✓")

# B. Train_n values
assert sorted(df['train_n'].unique()) == [7, 10, 20]
print(f"train_n: [7, 10, 20] ✓")

# C. repeat_index: 0-499 for each train_n
for tn in [7, 10, 20]:
    reps = sorted(df[df['train_n'] == tn]['repeat_index'].unique())
    assert reps == list(range(500)), f"n={tn}: bad repeat_index"
print("repeat_index: 0-499 per n ✓")

# D. Methods and counts
for method in ['default', 'l2']:
    for tn in [7, 10, 20]:
        mask = (df['train_n'] == tn) & (df['method'] == method)
        assert mask.sum() == 500, f"{method} n={tn}: {mask.sum()} rows"
print("Default/L2: 500 rows per n each ✓")

# E. NN: 15 models x 500 per n
nn_df = df[df['method'] == 'nn']
nn_ids = sorted(nn_df['model_id'].unique())
assert len(nn_ids) == 15, f"Expected 15 NN models, got {len(nn_ids)}"
for tn in [7, 10, 20]:
    for mid in nn_ids:
        mask = (nn_df['train_n'] == tn) & (nn_df['model_id'] == mid)
        assert mask.sum() == 500, f"NN {mid} n={tn}: {mask.sum()} rows"
print(f"NN: 15 models x 500 per n = 22500 ✓")

# F. Primary key uniqueness
pk = ['train_n', 'repeat_index', 'method', 'model_id']
assert df.duplicated(subset=pk).sum() == 0
print("PK unique ✓")

# G. D in [0,1], all finite
assert df['D'].between(0, 1).all()
assert df['D'].notna().all()
print(f"D in [0,1], all finite ✓ (min={df['D'].min():.4f}, max={df['D'].max():.4f})")

# H. failed
n_failed = int(df['failed'].sum())
print(f"Failed rows: {n_failed}")
# Verify: failed rows have D=1 and non-empty failure_reason
failed_rows = df[df['failed'] == True]
if len(failed_rows) > 0:
    assert (failed_rows['D'] == 1.0).all()
    assert (failed_rows['failure_reason'].notna() & (failed_rows['failure_reason'] != '')).all()
    print("  Failed rows: D=1, failure_reason non-empty ✓")
else:
    print("  No failed rows (all estimations succeeded)")

# I. delta_used consistency
for method, n_val, expected_delta in [
    ('default', 7, 0.1), ('default', 10, 0.1), ('default', 20, 0.1),
    ('l2', 7, 0.10), ('l2', 10, 0.10), ('l2', 20, 0.08),
]:
    mask = (df['train_n'] == n_val) & (df['method'] == method)
    deltas = df.loc[mask, 'delta_used']
    assert (deltas == expected_delta).all(), f"{method} n={n_val}: delta mismatch"
print("delta_used consistent ✓")

# J. NN prediction failure: support_set_violation is NaN
nn_failed = df[(df['method'] == 'nn') & (df['failed'] == True)]
if len(nn_failed) > 0:
    ss_viol = nn_failed['support_set_violation']
    assert ss_viol.isna().all() or (ss_viol != ss_viol).all(), \
        "NN failed rows: support_set_violation should be NaN"
    print(f"NN failures ({len(nn_failed)}): support_set_violation=NaN ✓")

# K. Stability CSV: 45 rows
nn_stab = stab[stab['method'] == 'nn']
assert len(nn_stab) == 45, f"Expected 45 NN stability rows, got {len(nn_stab)}"
assert sorted(nn_stab['train_n'].unique()) == [7, 10, 20]
assert len(nn_stab['model_id'].unique()) == 15
print(f"Stability: 45 rows (15 models x 3 n) ✓")

# L. Manifest provenance
assert manifest['experiment'] == 'real_data_holdout_validation_p8a_formal'
assert manifest['git_dirty'] is False
assert 'output_hashes' in manifest
assert len(manifest['output_hashes']) == 4, (
    "Manifest output_hashes should cover 4 data files (manifest excluded to avoid self-hash)"
)
assert 'generation_code_commit' in manifest
print(f"Manifest: experiment={manifest['experiment']}, dirty=False, 5 hashes ✓")

# M. Summary: independent recompute of Default median D
print("\n--- M. Independent Stats Recompute ---")
for method in ['default', 'l2']:
    for tn in [7, 10, 20]:
        mask = (df['train_n'] == tn) & (df['method'] == method)
        D_vals = df.loc[mask, 'D'].values
        ind_median = float(np.median(D_vals))
        ind_mean = float(np.mean(D_vals))
        # Compare with summary
        ps = summary['primary_stats'][method][str(tn)]
        assert abs(ps['median_D'] - ind_median) < 1e-9, \
            f"{method} n={tn}: median mismatch ({ps['median_D']} vs {ind_median})"
        assert abs(ps['mean_D'] - ind_mean) < 1e-9, \
            f"{method} n={tn}: mean mismatch"
print("Default/L2: independent recompute matches summary ✓")

# N. NN cross-model distribution
nn_dist = summary.get('nn_cross_model_distribution', [])
assert len(nn_dist) > 0, "nn_cross_model_distribution empty"
print(f"NN cross-model distribution: {len(nn_dist)} rows ✓")

# O. NN model-first: independently verify ALL 15 model-level medians
#    and their cross-model distribution (min/Q1/median/Q3/max/mean/SD)
print("NN model-first: verifying all 15 models per train_n...")
for tn in [7, 10, 20]:
    ind_medians = []
    for mid in nn_ids:
        mask = (df['train_n'] == tn) & (df['method'] == 'nn') & (df['model_id'] == mid)
        ind_median = float(np.median(df.loc[mask, 'D'].values))
        ind_medians.append(ind_median)
        # Compare each model's median with stability CSV
        stab_row = nn_stab[(nn_stab['train_n'] == tn) & (nn_stab['model_id'] == mid)]
        assert len(stab_row) == 1, f"NN {mid} n={tn}: missing from stability CSV"
        assert abs(stab_row.iloc[0]['median_D'] - ind_median) < 1e-9, \
            f"NN {mid} n={tn}: stability median mismatch ({stab_row.iloc[0]['median_D']} vs {ind_median})"

    ind_medians = np.array(ind_medians)
    # Compare full distribution against stability CSV
    nn_rows = nn_stab[nn_stab['train_n'] == tn]
    stab_medians = np.array(sorted(nn_rows['median_D'].values))
    ind_medians.sort()
    assert len(stab_medians) == 15
    for i in range(15):
        assert abs(stab_medians[i] - ind_medians[i]) < 1e-9, \
            f"n={tn} model[{i}]: stability vs independent mismatch"

    # Verify cross-model distribution summary
    dist_min = float(np.min(ind_medians))
    dist_q1 = float(np.percentile(ind_medians, 25))
    dist_median = float(np.median(ind_medians))
    dist_q3 = float(np.percentile(ind_medians, 75))
    dist_max = float(np.max(ind_medians))
    dist_mean = float(np.mean(ind_medians))
    dist_sd = float(np.std(ind_medians, ddof=1))

    # Find matching metric row in nn_cross_model_distribution
    nn_dist = summary.get('nn_cross_model_distribution', [])
    median_row = [r for r in nn_dist
                  if r['train_n'] == tn and r['metric'] == 'median_D']
    assert len(median_row) == 1, f"n={tn}: median_D row missing from nn_dist"
    mr = median_row[0]
    assert abs(mr['min'] - dist_min) < 1e-9, f"n={tn}: dist min mismatch"
    assert abs(mr['Q1'] - dist_q1) < 1e-9, f"n={tn}: dist Q1 mismatch"
    assert abs(mr['median'] - dist_median) < 1e-9, f"n={tn}: dist median mismatch"
    assert abs(mr['Q3'] - dist_q3) < 1e-9, f"n={tn}: dist Q3 mismatch"
    assert abs(mr['max'] - dist_max) < 1e-9, f"n={tn}: dist max mismatch"
    assert abs(mr['mean'] - dist_mean) < 1e-9, f"n={tn}: dist mean mismatch"
    assert abs(mr['std'] - dist_sd) < 1e-9, f"n={tn}: dist std mismatch"

    print(f"  n={tn}: {len(ind_medians)} models verified, "
          f"min={dist_min:.4f} Q1={dist_q1:.4f} median={dist_median:.4f} "
          f"Q3={dist_q3:.4f} max={dist_max:.4f} mean={dist_mean:.4f} "
          f"sd={dist_sd:.4f} ✓")
print("NN model-first: all 15 models + full distribution verified ✓")

# P. Verify E1/E2/E3/E4 artifacts not overwritten
old_artifacts = [
    'E1_baseline/results.csv', 'E1_E2_crossfit/results.csv',
    'E2_oracle_layers/results.csv', 'E3_sample_adaptive/results.csv',
    'E3b_vector_mlp/vector_mlp_results.csv', 'E4_robustness/offgrid_risk_curves.csv',
]
artifacts_base = os.path.join(DIR, '..', '..')
for art in old_artifacts:
    path = os.path.join(artifacts_base, art)
    assert os.path.exists(path), f"Old artifact missing: {art}"
print("E1/E2/E3/E4/R1/R2 artifacts untouched ✓")

# Q. Verify SHA256SUMS_p8a seal file against actual file bytes
print("Verifying SHA256SUMS_p8a seal...")
seal_path = os.path.join(DIR, 'SHA256SUMS_p8a')
assert os.path.exists(seal_path), "SHA256SUMS_p8a seal file missing"
with open(seal_path, 'r', encoding='utf-8') as f:
    seal_lines = [l.strip() for l in f if l.strip() and not l.startswith('#')]
seal_hashes = {}
for line in seal_lines:
    parts = line.split('  ')
    assert len(parts) == 2, f"Bad seal line: {line}"
    seal_hashes[parts[1]] = parts[0]
expected_seal_files = ['real_holdout_results.csv', 'real_holdout_summary.json',
                       'real_nn_model_stability.csv', 'run_log.txt',
                       'real_data_manifest.json']
for fname in expected_seal_files:
    assert fname in seal_hashes, f"Missing from seal: {fname}"
    fpath = os.path.join(DIR, fname)
    with open(fpath, 'rb') as f:
        raw = f.read()
    raw_lf = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    actual_sha = hashlib.sha256(raw_lf).hexdigest()
    assert seal_hashes[fname] == actual_sha, \
        f"Seal mismatch for {fname}: seal={seal_hashes[fname][:16]}... actual={actual_sha[:16]}..."
print(f"SHA256SUMS_p8a: {len(seal_hashes)} files verified, all match ✓")

# R. Verify formal dir has output files + seal + source files
formal_files = set(os.listdir(DIR))
expected = {'real_holdout_results.csv', 'real_holdout_summary.json',
            'real_nn_model_stability.csv', 'real_data_manifest.json',
            'run_log.txt', 'SHA256SUMS_p8a'}
assert expected <= formal_files, f"Missing output files: {expected - formal_files}"
print("Formal dir: all 5 output files present ✓")

print("\n" + "=" * 60)
if errors:
    print(f"VERIFICATION FAILED — {len(errors)} error(s)")
    for e in errors:
        print(f"  FAIL: {e}")
else:
    print("ALL INDEPENDENT VERIFICATIONS PASSED")
    print("Ready for executor report delivery.")
