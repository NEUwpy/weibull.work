"""G7 auto-audit v4: fail-closed. Verifies claims-to-data.csv against formal artifacts,
checks all figures/references/checklists for consistency, detects stale terms."""
import os, sys, json, ast, re, subprocess
import numpy as np, pandas as pd

CODE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'code')
sys.path.insert(0, CODE_DIR)
from config import BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID

ARTIFACTS = os.path.join(os.path.dirname(CODE_DIR), 'artifacts', 'formal')
FIGDIR = os.path.join(os.path.dirname(CODE_DIR), 'manuscript', 'figures')
PAPER = os.path.join(os.path.dirname(CODE_DIR), 'manuscript', 'paper.md')
SUPP = os.path.join(os.path.dirname(CODE_DIR), 'manuscript', 'supplementary.md')
AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))

CD_CSV = os.path.join(AUDIT_DIR, 'claims-to-data.csv')
FC_CSV = os.path.join(AUDIT_DIR, 'figure-checklist.csv')
RC_CSV = os.path.join(AUDIT_DIR, 'reference-checklist.csv')
SC_MD  = os.path.join(AUDIT_DIR, 'submission-checklist.md')

errs = []
def check(desc, ok):
    if not ok: errs.append(desc)
    print(f'  {desc}: {"OK" if ok else "FAIL"}')

# ═══ 1. Config Grid ═══
check('grid beta', BETA_GRID == [1.5, 2.0, 2.5, 4.0, 5.0])
check('grid goe', GAMMA_OVER_ETA_GRID == [0.1, 0.5, 1.0])
check('grid n', N_GRID == [7, 10, 20])

# ═══ 2. Claims-to-Data: exists + unique claim_ids ═══
assert os.path.exists(CD_CSV), f'{CD_CSV} missing'
cd = pd.read_csv(CD_CSV)
check('claims-to-data has rows', len(cd) > 0)
check('claim_id column exists', 'claim_id' in cd.columns)
check('claim_ids unique', cd['claim_id'].nunique() == len(cd))
check('claim_ids non-null', cd['claim_id'].notna().all())

# ═══ 3. Verify source_file references are resolvable ═══
NON_PATH_SOURCES = {'BETA_GRID', 'GAMMA_OVER_ETA_GRID', 'N_GRID', 'exists'}
for _, row in cd.iterrows():
    src = str(row.get('source_file', ''))
    if not src or src == 'nan': continue
    cid = row['claim_id']
    if src in NON_PATH_SOURCES: continue  # Config constant, not a file path
    study_root = os.path.dirname(CODE_DIR)
    if src.startswith('artifacts/'):
        full = os.path.join(study_root, src)
    elif src.startswith('code/'):
        full = os.path.join(study_root, src)
    elif src.startswith('Study/'):
        full = os.path.join(study_root, '..', '..', src)
    else:
        full = os.path.join(ARTIFACTS, src.replace('artifacts/formal/', ''))
    if not os.path.exists(full):
        check(f'{cid} source: {src}', False)
for _, row in cd.iterrows():
    src = str(row.get('source_file', ''))
    for stale in ['R2产物', '...']:
        if stale in src:
            check(f'{row["claim_id"]} no stale: {stale}', False)

# ═══ 4. Recompute key values from formal artifacts ═══
# Ladder
with open(os.path.join(ARTIFACTS, 'E2_oracle_layers', 'summary.json'), encoding='utf-8') as f:
    lad = {r['layer']: r['J1_global'] for r in json.load(f)['results']['ladder']}
for cid, layer, expected in [('C001','Default',0.633218947),('C002','L1',0.632913084),('C003','L2',0.632540558),
                              ('C004','L3',0.585067506),('C005','L4',0.582090109),('C006','L5',0.571170388),('C007','L6',0.494529731)]:
    actual = lad[layer]
    check(f'{cid} {layer}={expected:.9f}', abs(actual-expected) < 1e-8)

# E4a
df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4a_feature_ablation.csv'))
for cid, group, expected in [('C011','full',0.545628),('C012','scale_quantile',0.550596),
                              ('C013','shape',0.581578),('C014','n',0.637761)]:
    actual = float(df[df['feature_group']==group]['pooled_J1'].mean())
    check(f'{cid} E4a {group}={expected:.6f}', abs(actual-expected) < 0.001)

# E4d per-track pooled J1
with open(os.path.join(ARTIFACTS, 'E4_robustness', 'summary_e4d.json'), encoding='utf-8') as f:
    s = json.load(f)
pt = s['per_track_pooled_J1']
for cid, track, expected in [('C015','E4b_boundary',0.603773509338463),('C016','E4c_offgrid',0.526333743982320)]:
    actual = pt[track]['Vector-MLP-L6']['J1']
    check(f'{cid} {track}={expected:.12f}', abs(actual-expected) < 1e-12)

# R2
cs = pd.read_csv(os.path.join(ARTIFACTS, 'delta_upper_bound_audit', 'cohort_summary.csv'))
row = cs[cs['cohort_delta']==0.50].iloc[0]
dist = ast.literal_eval(row['extended_best_delta_distribution'])
check('C017 R2 n_migrated=2800', row['n_migrated']==2800)
check('C018 R2 rate=0.946586', abs(row['migration_rate']-0.946586) < 1e-6)
check('C019 R2 d=0.50 count=158', dist.get('0.5',0)+dist.get(0.5,0)==158)
check('C020 R2 d=1.00 count=743', dist.get('1.0',0)+dist.get(1.0,0)==743)
bins = [158,1218,682,157,743]
for k,v in dist.items():
    d=float(k)
    if d<=0.50: bins[0]-=v
    elif d<=0.70: bins[1]-=v
    elif d<=0.90: bins[2]-=v
    elif d<=0.98: bins[3]-=v
    else: bins[4]-=v
check('R2 5-bin verified', all(b==0 for b in bins))

# Seed stability
sd = pd.read_csv(os.path.join(ARTIFACTS, 'E3b_vector_mlp', 'seed_stability.csv'))
check('C008 seed42=0.547003', abs(float(sd[sd['seed']==42]['pooled_J1'].iloc[0])-0.547003)<1e-6)
check('C009 seed2026=0.546133', abs(float(sd[sd['seed']==2026]['pooled_J1'].iloc[0])-0.546133)<1e-6)
check('C010 seed3407=0.544009', abs(float(sd[sd['seed']==3407]['pooled_J1'].iloc[0])-0.544009)<1e-6)

# Real data KS values
real = pd.read_csv(os.path.join(ARTIFACTS, 'real_data', 'nist-6061-t6-fatigue', 'real_holdout_results.csv'))
nn_df = real[real['method']=='nn']; nn_ids = sorted(nn_df['model_id'].unique())
for cid, tn, expected in [('C021',7,0.1881),('C022',10,0.1630),('C023',20,0.1276)]:
    actual = float(np.median(real[(real['train_n']==tn)&(real['method']=='default')]['D']))
    check(f'{cid} Default n={tn} D={expected}', abs(actual-expected)<0.001)
for cid, tn, expected in [('C024',7,0.2024),('C025',10,0.1727),('C026',20,0.1361)]:
    meds = [np.median(nn_df[(nn_df['train_n']==tn)&(nn_df['model_id']==m)]['D']) for m in nn_ids]
    actual = float(np.median(meds))
    check(f'{cid} NN n={tn} median_of_medians={expected}', abs(actual-expected)<0.001)

# ═══ 5. All 12 figures exist ═══
main_figs = ['fig6_feature_ablation','fig7_boundary_offgrid','fig8_upper_bound_audit','fig9_real_data_comparison']
supp_figs = [f'fig_s{i}_{n}' for i,n in [(1,'crossfit'),(2,'beta_profile'),(3,'seed_stability'),
    (4,'ablation_folds'),(5,'boundary_folds'),(6,'upper_bound_dist'),(7,'nn_15model_dist'),(8,'support_set')]]
for fn in main_figs + supp_figs:
    for ext in ['png','svg','pdf']:
        p = os.path.join(FIGDIR, f'{fn}.{ext}')
        ok = os.path.exists(p) and os.path.getsize(p) > 200
        if not ok: check(f'Fig {fn}.{ext}', False)

# ═══ 6. Figure checklist: no stale status ═══
assert os.path.exists(FC_CSV), f'{FC_CSV} missing'
fc = pd.read_csv(FC_CSV)
for stale in ['未生成','待生成','需检查','待补充','未生成']:
    for col in fc.columns:
        mask = fc[col].astype(str).str.contains(stale, na=False)
        if mask.any():
            for idx in fc[mask].index:
                check(f'Fig checklist "{stale}" in {fc.loc[idx,"fig_number"]}', False)

# ═══ 7. Reference checklist: [3][4][7] verified ═══
assert os.path.exists(RC_CSV), f'{RC_CSV} missing'
rc = pd.read_csv(RC_CSV)
expected_dois = {'[3]':'10.1142/S0219455423500852','[4]':'10.12068/j.issn.1005-3026.2025.20240194','[7]':'10.1016/j.probengmech.2025.103828'}
for ref, exp_doi in expected_dois.items():
    rows = rc[rc['ref_number']==ref]
    check(f'Ref {ref} exists in checklist', len(rows)>0)
    if len(rows)>0:
        status = str(rows.iloc[0]['status'])
        doi = str(rows.iloc[0]['doi'])
        check(f'Ref {ref} status is verified', '已核实' in status)
        check(f'Ref {ref} DOI matches {exp_doi}', exp_doi in doi)

# ═══ 8. Stale terms in paper + supplementary ═══
for fpath, label in [(PAPER,'paper'),(SUPP,'supplementary')]:
    with open(fpath, encoding='utf-8') as f: txt = f.read()
    for stale in ['-Spread','-Shape','理论上限','边际递减','单侧两样本KS','正文不可获得','待用户补充']:
        check(f'No stale "{stale}" in {label}', stale not in txt)

# ═══ 9. Figure citations in paper + supplementary ═══
with open(PAPER, encoding='utf-8') as f: ptxt = f.read()
with open(SUPP, encoding='utf-8') as f: stxt = f.read()
for i in range(1, 10):
    check(f'Figure {i} cited in paper', f'Figure {i}' in ptxt)
for i in range(1, 9):
    check(f'Figure S{i} cited in supplementary', f'Figure S{i}' in stxt or f'S{i}:' in stxt)

# ═══ 10. Supplementary no stale beta count ═══
check('supp no "每个beta各300"', '每个beta各300' not in stxt)
check('supp has correct count 5x3x20=300', '5×3×20=300' in stxt or '5x3x20=300' in stxt)

# ═══ 11. S2 Spearman rho from trend_summary (per-n only, exclude pooled) ═══
ts = pd.read_csv(os.path.join(ARTIFACTS, 'E2_beta_profile_audit', 'trend_summary.csv'))
rhos = ts[(ts['metric']=='local_gradient_slope') & (ts['scope'].str.startswith('n='))]
check('S2: 3 per-n Spearman rhos', len(rhos)==3)
check('S2: rho_n7 approx -0.463', abs(float(rhos[rhos['scope']=='n=7']['spearman_rho'].iloc[0]) - (-0.463)) < 0.05)
check('S2: rho_n10 approx -0.495', abs(float(rhos[rhos['scope']=='n=10']['spearman_rho'].iloc[0]) - (-0.495)) < 0.05)
check('S2: rho_n20 approx -0.529', abs(float(rhos[rhos['scope']=='n=20']['spearman_rho'].iloc[0]) - (-0.529)) < 0.05)

# ═══ 12. S5: 90 rows, 30 Default-ref ═══
bm = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4d_paired_comparisons_by_model.csv'))
check('S5: 90 rows', len(bm)==90)
bm_def = bm[bm['reference_model']=='Default']
check('S5: 30 Default-ref rows', len(bm_def)==30)

# ═══ 13. Study1.5 path exists ═══
check('Study1.5 path', os.path.exists(os.path.join(os.path.dirname(CODE_DIR), '..', '..', 'Study', '015-study-NN输入表征与样本量机制研究')))

# ═══ 14. Submission checklist no stale items ═══
if os.path.exists(SC_MD):
    with open(SC_MD, encoding='utf-8') as f: sc_txt = f.read()
    for stale in ['未生成','待生成']:
        check(f'submission-checklist no "{stale}"', stale not in sc_txt)

# ═══ 15. git diff --check from baseline ═══
# Use a52c3023 as baseline per contract
result = subprocess.run(['git', 'diff', '--check', 'a52c3023..HEAD'], capture_output=True, text=True)
check('git diff --check a52c3023..HEAD', len(result.stdout.strip())==0 and result.returncode==0)

print()
if errs:
    print(f'{len(errs)} ERRORS:')
    for e in errs: print(f'  FAIL: {e}')
    sys.exit(1)
else:
    print('ALL AUDIT CHECKS PASSED')
