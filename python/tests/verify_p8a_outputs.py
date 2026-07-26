"""Quick verification of P8a formal outputs."""
import pandas as pd, json, os

DIR = os.path.join(
    os.path.dirname(__file__), '..', '..',
    'Study', '01-study-MDM最小偏移量优化研究',
    'artifacts', 'formal', 'real_data', 'nist-6061-t6-fatigue'
)

# 1. CSV
df = pd.read_csv(os.path.join(DIR, 'real_holdout_results.csv'))
assert len(df) == 25500, f"Expected 25500 rows, got {len(df)}"
assert set(df['train_n'].unique()) == {7, 10, 20}
assert set(df['method'].unique()) == {'default', 'l2', 'nn'}
nn_ids = [m for m in df['model_id'].unique() if m.startswith('fold_')]
assert len(nn_ids) == 15, f"Expected 15 NN model_ids, got {len(nn_ids)}"
assert df['D'].between(0, 1).all()
assert df[['train_n', 'repeat_index', 'method', 'model_id']].duplicated().sum() == 0
print(f"CSV: {len(df)} rows, {len(nn_ids)} NN models, PK unique, D in [0,1]")

# 2. Stability CSV
stab = pd.read_csv(os.path.join(DIR, 'real_nn_model_stability.csv'))
nn_stab = stab[stab['method'] == 'nn']
assert len(nn_stab) == 45, f"Expected 45 NN stability rows, got {len(nn_stab)}"
print(f"Stability: {len(stab)} rows ({len(nn_stab)} NN)")

# 3. Manifest
with open(os.path.join(DIR, 'real_data_manifest.json'), encoding='utf-8') as f:
    manifest = json.load(f)
assert manifest['git_dirty'] is False, f"git_dirty={manifest['git_dirty']}"
assert manifest['experiment'] == 'real_data_holdout_validation_p8a_formal'
assert 'output_hashes' in manifest
assert len(manifest['output_hashes']) == 5
print(f"Manifest: experiment={manifest['experiment']}, commit={manifest.get('generation_code_commit')}, dirty={manifest['git_dirty']}, elapsed={manifest.get('elapsed_seconds')}s")

# 4. Summary JSON
with open(os.path.join(DIR, 'real_holdout_summary.json'), encoding='utf-8') as f:
    summary = json.load(f)
assert 'primary_stats' in summary
assert 'nn_cross_model_distribution' in summary
nn_dist = summary['nn_cross_model_distribution']
assert len(nn_dist) > 0
print(f"Summary: primary_stats methods={list(summary['primary_stats'].keys())}, nn_dist rows={len(nn_dist)}")

# 5. Run log
with open(os.path.join(DIR, 'run_log.txt'), encoding='utf-8') as f:
    log_content = f.read()
assert 'Total result rows: 25500' in log_content
assert 'Primary key uniqueness: OK' in log_content
print("Run log: row count and PK markers found")

print("\nALL OUTPUT VERIFICATIONS PASSED")
