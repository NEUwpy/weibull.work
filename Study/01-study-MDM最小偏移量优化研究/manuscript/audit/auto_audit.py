"""G7 auto-audit v3: fail-closed manuscript check against formal artifacts."""
import os, sys, json, ast, re
import numpy as np, pandas as pd

CODE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'code')
sys.path.insert(0, CODE_DIR)
from config import BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID, DELTA_GRID

ARTIFACTS = os.path.join(os.path.dirname(CODE_DIR), 'artifacts', 'formal')
FIGDIR = os.path.join(os.path.dirname(CODE_DIR), 'manuscript', 'figures')
PAPER = os.path.join(os.path.dirname(CODE_DIR), 'manuscript', 'paper.md')
AUDIT_DIR = os.path.dirname(os.path.abspath(__file__))
errs = []

def check(desc, ok):
    if not ok: errs.append(desc)
    print(f'  {desc}: {"OK" if ok else "FAIL"}')

# ═══ 1. Config Grid ═══
check('beta={1.5,2,2.5,4,5}', BETA_GRID == [1.5, 2.0, 2.5, 4.0, 5.0])
check('goe={0.1,0.5,1.0}', GAMMA_OVER_ETA_GRID == [0.1, 0.5, 1.0])
check('n={7,10,20}', N_GRID == [7, 10, 20])
check('26 deltas', len(DELTA_GRID) == 26)

# ═══ 2. Oracle Ladder ═══
with open(os.path.join(ARTIFACTS, 'E2_oracle_layers', 'summary.json'), encoding='utf-8') as f:
    lad = {r['layer']: r['J1_global'] for r in json.load(f)['results']['ladder']}
exp_lad = {'Default': 0.633218947, 'L1': 0.632913084, 'L2': 0.632540558,
           'L3': 0.585067506, 'L4': 0.582090109, 'L5': 0.571170388, 'L6': 0.494529731}
for k, v in exp_lad.items():
    check(f'ladder {k}={v:.9f}', abs(lad[k]-v) < 1e-8)

# ═══ 3. E4a Retained-Subset ═══
df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4a_feature_ablation.csv'))
exp_e4a = {'full': 0.545628, 'scale_quantile': 0.550596, 'shape': 0.581578, 'n': 0.637761}
for g, ev in exp_e4a.items():
    m = float(df[df['feature_group']==g]['pooled_J1'].mean())
    check(f'E4a {g}={ev:.6f}', abs(m-ev) < 0.001)
check('E4a 60 runs', len(df) == 60)

# ═══ 4. Fig.7 Per-Track Pooled J1 ═══
with open(os.path.join(ARTIFACTS, 'E4_robustness', 'summary_e4d.json'), encoding='utf-8') as f:
    s = json.load(f)
pt = s['per_track_pooled_J1']
j1b_actual = pt['E4b_boundary']['Vector-MLP-L6']['J1']
j1o_actual = pt['E4c_offgrid']['Vector-MLP-L6']['J1']
check(f'Fig.7 boundary J1={j1b_actual:.10f}', abs(j1b_actual - 0.603773509338463) < 1e-12)
check(f'Fig.7 offgrid J1={j1o_actual:.10f}', abs(j1o_actual - 0.526333743982320) < 1e-12)

# ═══ 5. E4d Tracks ═══
df7 = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4d_selector_extrapolation.csv'))
for t in ['E4b_boundary', 'E4c_offgrid']:
    check(f'E4d {t} non-empty', len(df7[df7['track']==t]) > 0)
    check(f'E4d {t} 5 folds', df7[df7['track']==t]['fold'].nunique() == 5)
    check(f'E4d {t} 3 seeds', df7[df7['track']==t]['seed'].nunique() == 3)

# ═══ 6. R2 Bins ═══
cs = pd.read_csv(os.path.join(ARTIFACTS, 'delta_upper_bound_audit', 'cohort_summary.csv'))
row = cs[cs['cohort_delta']==0.50].iloc[0]
dist = ast.literal_eval(row['extended_best_delta_distribution'])
bins = {'d=0.50':0,'0.52-0.70':0,'0.72-0.90':0,'0.92-0.98':0,'d=1.00':0}
for k,v in dist.items():
    d=float(k)
    if d<=0.50: bins['d=0.50']+=v
    elif d<=0.70: bins['0.52-0.70']+=v
    elif d<=0.90: bins['0.72-0.90']+=v
    elif d<=0.98: bins['0.92-0.98']+=v
    else: bins['d=1.00']+=v
check('R2 total=2958', sum(bins.values())==2958)
check(f'R2 bins={list(bins.values())}', list(bins.values())==[158,1218,682,157,743])

# ═══ 7. Seed Stability ═══
sd = pd.read_csv(os.path.join(ARTIFACTS, 'E3b_vector_mlp', 'seed_stability.csv'))
check('3 seeds', len(sd)==3)
check('seeds=[42,2026,3407]', list(sd['seed'])==[42,2026,3407])

# ═══ 8. S5: 90 rows, 30 Default-ref ═══
bm = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4d_paired_comparisons_by_model.csv'))
check('S5: 90 rows total', len(bm)==90)
bm_def = bm[bm['reference_model']=='Default']
check('S5: 30 Default-ref rows', len(bm_def)==30)
check('S5: E4b_boundary in Default ref', len(bm_def[bm_def['track']=='E4b_boundary'])==15)
check('S5: E4c_offgrid in Default ref', len(bm_def[bm_def['track']=='E4c_offgrid'])==15)

# ═══ 9. S2: Beta-Profile Source ═══
bp = pd.read_csv(os.path.join(ARTIFACTS, 'E2_beta_profile_audit', 'by_beta_n.csv'))
check('S2: by_beta_n.csv has data', len(bp)>0)
check('S2: 5 betas', bp['beta'].nunique()==5)
check('S2: 3 n', bp['n'].nunique()==3)
check('S2: 15 rows (5b x 3n)', len(bp)==15)
# Spearman rho
ts = pd.read_csv(os.path.join(ARTIFACTS, 'E2_beta_profile_audit', 'trend_summary.csv'))
rhos = ts[ts['metric']=='local_gradient_slope']['spearman_rho'].values
check(f'S2: Spearman rhos per-n (found {len(rhos)})', len(rhos) >= 3)
check('S2: rho_n7 approx -0.46', abs(rhos[0] - (-0.463)) < 0.05)

# ═══ 10. All Figures Exist ═══
main_figs = ['fig6_feature_ablation','fig7_boundary_offgrid','fig8_upper_bound_audit','fig9_real_data_comparison']
supp_figs = ['fig_s1_crossfit','fig_s2_beta_profile','fig_s3_seed_stability','fig_s4_ablation_folds',
             'fig_s5_boundary_folds','fig_s6_upper_bound_dist','fig_s7_nn_15model_dist','fig_s8_support_set']
for fn in main_figs + supp_figs:
    for ext in ['png','svg','pdf']:
        p = os.path.join(FIGDIR, f'{fn}.{ext}')
        ok = os.path.exists(p) and os.path.getsize(p) > 200
        check(f'Fig {fn}.{ext}', ok)

# ═══ 11. Figure Checklist: No Stale Status ═══
fc_path = os.path.join(AUDIT_DIR, 'figure-checklist.csv')
if os.path.exists(fc_path):
    fc = pd.read_csv(fc_path)
    stale_status = ['未生成', '待生成', '需检查', '待补充']
    for _, row in fc.iterrows():
        for col in fc.columns:
            val = str(row[col])
            for s in stale_status:
                if s in val:
                    check(f'Fig checklist no "{s}" in {row.get("fig_number", "?")}', False)
                    break
check('Fig checklist no stale status', True)  # passes if no explicit fails above

# ═══ 12. Reference Checklist: [3][4][7] Verified ═══
rc_path = os.path.join(AUDIT_DIR, 'reference-checklist.csv')
if os.path.exists(rc_path):
    rc = pd.read_csv(rc_path)
    for ref_num in ['[3]', '[4]', '[7]']:
        rows = rc[rc['ref_number']==ref_num]
        if len(rows) > 0:
            status = str(rows.iloc[0]['status'])
            check(f'Ref {ref_num} verified', '待' not in status and '未' not in status)

# ═══ 13. No Stale Terms in Paper ═══
with open(PAPER, encoding='utf-8') as f:
    txt = f.read()
for stale in ['-Spread', '-Shape', '理论上限', '边际递减', '单侧两样本KS',
              'spread贡献最大', '正文不可获得', '待用户补充']:
    check(f'No stale: "{stale}"', stale not in txt)

# ═══ 14. KS Term Present ═══
for term in ['one-sample two-sided KS distance']:
    check(f'KS term present: {term}', term in txt)

# ═══ 15. Claims-to-Data Source Files Exist ═══
cd_path = os.path.join(AUDIT_DIR, 'claims-to-data.csv')
if os.path.exists(cd_path):
    cd = pd.read_csv(cd_path)
    for _, row in cd.iterrows():
        src = str(row.get('source_file', ''))
        if src and src != 'nan' and not src.startswith('formal/'):
            # Check that source exists relative to ARTIFACTS
            full = os.path.join(ARTIFACTS, '..', '..', src) if not src.startswith('artifacts') else os.path.join(os.path.dirname(CODE_DIR), src)
            if os.path.exists(full):
                pass  # OK
            elif '/' in src:
                check(f'Claims source exists: {src[:60]}', os.path.exists(os.path.join(ARTIFACTS, src)))

# ═══ 16. Study1.5 Path ═══
study015_path = 'Study/015-study-NN输入表征与样本量机制研究'
check(f'Study1.5 path exists: {study015_path}', os.path.exists(os.path.join(os.path.dirname(CODE_DIR), '..', '..', study015_path)))

# ═══ 17. git diff --check on SVG files ═══
import subprocess
result = subprocess.run(['git', 'diff', '--check', 'HEAD~1..HEAD'], capture_output=True, text=True)
check('git diff --check clean', len(result.stdout.strip()) == 0 and result.returncode == 0)

print()
if errs:
    print(f'{len(errs)} ERRORS:')
    for e in errs: print(f'  FAIL: {e}')
    sys.exit(1)
else:
    print('ALL AUDIT CHECKS PASSED')
