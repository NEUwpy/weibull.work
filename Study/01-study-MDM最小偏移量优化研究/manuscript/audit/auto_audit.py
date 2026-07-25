"""G7 auto-audit: verify manuscript claims against formal artifacts."""
import os, sys, json, ast
import numpy as np, pandas as pd

CODE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', 'code')
sys.path.insert(0, CODE_DIR)
from config import BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID, DELTA_GRID

ARTIFACTS = os.path.join(os.path.dirname(CODE_DIR), 'artifacts', 'formal')
FIGDIR = os.path.join(os.path.dirname(CODE_DIR), 'manuscript', 'figures')
errs = []

def check(desc, ok):
    if not ok: errs.append(desc)
    print(f'  {desc}: {"OK" if ok else "FAIL"}')

# 1. Grid
check('beta={1.5,2,2.5,4,5}', BETA_GRID == [1.5, 2.0, 2.5, 4.0, 5.0])
check('goe={0.1,0.5,1.0}', GAMMA_OVER_ETA_GRID == [0.1, 0.5, 1.0])
check('n={7,10,20}', N_GRID == [7, 10, 20])
check('26 deltas', len(DELTA_GRID) == 26)

# 2. Ladder
with open(os.path.join(ARTIFACTS, 'E2_oracle_layers', 'summary.json'), encoding='utf-8') as f:
    lad = {r['layer']: r['J1_global'] for r in json.load(f)['results']['ladder']}
for k, v in {'Default':0.633218947,'L1':0.632913084,'L2':0.632540558,
             'L3':0.585067506,'L4':0.582090109,'L5':0.571170388,'L6':0.494529731}.items():
    check(f'ladder {k}', abs(lad[k]-v) < 1e-8)

# 3. E4a
df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4a_feature_ablation.csv'))
for g, v in {'full':0.545628,'scale_quantile':0.550596,'shape':0.581578,'n':0.637761}.items():
    m = float(df[df['feature_group']==g]['pooled_J1'].mean())
    check(f'E4a {g}: {m:.4f} vs {v:.4f}', abs(m-v) < 0.001)

# 4. R2
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
check('R2 bins=[158,1218,682,157,743]', list(bins.values())==[158,1218,682,157,743])

# 5. E4d tracks
df7 = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4d_selector_extrapolation.csv'))
for t in ['E4b_boundary','E4c_offgrid']:
    check(f'E4d track {t} non-empty', len(df7[df7['track']==t]) > 0)
    check(f'E4d track {t} 5 folds', df7[df7['track']==t]['fold'].nunique()==5)
    check(f'E4d track {t} 3 seeds', df7[df7['track']==t]['seed'].nunique()==3)

# 6. Seed stability
sd = pd.read_csv(os.path.join(ARTIFACTS, 'E3b_vector_mlp', 'seed_stability.csv'))
check('seed stability 3 rows', len(sd)==3)
check('seeds=[42,2026,3407]', list(sd['seed'])==[42,2026,3407])

# 7. All figures exist
main_figs = ['fig6_feature_ablation','fig7_boundary_offgrid','fig8_upper_bound_audit','fig9_real_data_comparison']
supp_figs = ['fig_s1_crossfit','fig_s2_beta_profile','fig_s3_seed_stability','fig_s4_ablation_folds',
             'fig_s5_boundary_folds','fig_s6_upper_bound_dist','fig_s7_nn_15model_dist','fig_s8_support_set']
for fn in main_figs + supp_figs:
    for ext in ['png','svg','pdf']:
        p = os.path.join(FIGDIR, f'{fn}.{ext}')
        ok = os.path.exists(p) and os.path.getsize(p) > 200
        if not ok: check(f'Figure {fn}.{ext}', False)

# 8. No stale terms in manuscript
with open(os.path.join(os.path.dirname(CODE_DIR), 'manuscript', 'paper.md'), encoding='utf-8') as f:
    txt = f.read()
for stale in ['-Spread','-Shape','理论上限','边际递减']:
    check(f'No stale: {stale}', stale not in txt)

# 9. KS metric name consistent
for term in ['one-sample two-sided KS distance']:
    check(f'KS term: {term}', term in txt)

# 10. KS not old name
for old in ['单侧两样本KS']:
    check(f'KS old name absent: {old}', old not in txt)

print()
if errs:
    print(f'{len(errs)} ERRORS:')
    for e in errs: print(f'  FAIL: {e}')
    sys.exit(1)
else:
    print('ALL AUDIT CHECKS PASSED')
