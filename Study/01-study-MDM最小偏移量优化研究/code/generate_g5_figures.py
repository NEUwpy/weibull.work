"""G5: Generate manuscript figures from formal artifacts. Deterministic, single-pass."""
import os, sys, json, ast
import numpy as np, pandas as pd
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.dirname(CODE_DIR)
A = os.path.join(STUDY, 'artifacts', 'formal')
OUT = os.path.join(STUDY, 'manuscript', 'figures')
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({'font.size': 8.5, 'axes.titlesize': 10, 'axes.labelsize': 9,
                     'figure.dpi': 150, 'savefig.dpi': 150, 'savefig.bbox': 'tight'})

def save(fig, name):
    for fmt in ['png', 'svg', 'pdf']:
        p = os.path.join(OUT, f'{name}.{fmt}')
        fig.savefig(p, format=fmt)
        assert os.path.getsize(p) > 200, f'{p} too small'
        if fmt == 'svg':
            with open(p, 'r', encoding='utf-8') as fh:
                svg = fh.read()
            svg_clean = '\n'.join(line.rstrip() for line in svg.splitlines())
            with open(p, 'w', encoding='utf-8') as fh:
                fh.write(svg_clean)
    plt.close(fig)
    print(f'  {name}')

# ═══ Fig 6: E4a Retained-Subset ═══
def fig6():
    df = pd.read_csv(os.path.join(A, 'E4_robustness', 'E4a_feature_ablation.csv'))
    groups = ['full', 'scale_quantile', 'shape', 'n']
    labels = ['full (13)', 'scale_quantile (10)', 'shape (4)', 'n (1)']
    colors = ['#0072B2', '#56B4E9', '#D55E00', '#CC79A7']
    means = [float(df[df['feature_group']==g]['pooled_J1'].mean()) for g in groups]
    stds  = [float(df[df['feature_group']==g]['pooled_J1'].std(ddof=1)) for g in groups]
    fig, ax = plt.subplots(figsize=(6, 4))
    x = range(len(groups))
    ax.bar(x, means, yerr=stds, color=colors, capsize=6, width=0.55, edgecolor='white')
    for i, (m, s) in enumerate(zip(means, stds)):
        ax.text(i, m + s + 0.004, f'{m:.4f}\n+/-{s:.4f}', ha='center', fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel('Pooled J1 (lower better)')
    ax.set_title('Fig.6: E4a Retained-Subset Comparison (15-run mean +/- SD)')
    save(fig, 'fig6_feature_ablation')

# ═══ Fig 7: E4d Extrapolation ═══
def fig7():
    with open(os.path.join(A, 'E4_robustness', 'summary_e4d.json'), encoding='utf-8') as f:
        s = json.load(f)
    pt = s['per_track_pooled_J1']
    j1_boundary = pt['E4b_boundary']['Vector-MLP-L6']['J1']   # 0.603773509338463
    j1_offgrid  = pt['E4c_offgrid']['Vector-MLP-L6']['J1']    # 0.526333743982320
    tracks = ['E4b_boundary', 'E4c_offgrid']
    tlabels = ['Boundary', 'Off-grid']
    colors  = ['#D55E00', '#0072B2']

    # Per-model distribution from extrapolation CSV
    df = pd.read_csv(os.path.join(A, 'E4_robustness', 'E4d_selector_extrapolation.csv'))
    df['mk'] = df['fold'].astype(str) + '_s' + df['seed'].astype(str)
    models = list(dict.fromkeys(df['mk'].values))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    j1v = [j1_boundary, j1_offgrid]
    ax1.bar(tlabels, j1v, color=colors, alpha=0.85, width=0.5)
    for i, v in enumerate(j1v): ax1.text(i, v+0.005, f'{v:.4f}', ha='center', fontsize=10)
    ax1.set_ylabel('Per-Track Pooled J1 (Vector-MLP-L6)')
    ax1.set_title('Fig.7: E4d NN Pooled J1 by Track')

    for trk, ls in zip(tracks, ['-','--']):
        meds = [float(df[(df['track']==trk)&(df['mk']==m)]['true_loss'].median()) for m in models]
        ax2.plot(range(len(models)), meds, color=colors[tracks.index(trk)], linestyle=ls,
                 marker='o', markersize=3, label=tlabels[tracks.index(trk)])
    ax2.set_xlabel('Model index'); ax2.set_ylabel('Median True Loss')
    ax2.set_title('Per-Model True Loss (15 models)'); ax2.legend(fontsize=8)
    save(fig, 'fig7_boundary_offgrid')

# ═══ Fig 8: R2 Upper Bound ═══
def fig8():
    cs = pd.read_csv(os.path.join(A, 'delta_upper_bound_audit', 'cohort_summary.csv'))
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
    total = sum(bins.values())
    fig, ax = plt.subplots(figsize=(7, 4))
    names = list(bins.keys()); counts = list(bins.values())
    bar_colors = ['#999999','#0072B2','#56B4E9','#D55E00','#CC79A7']
    ax.bar(names, counts, color=bar_colors, edgecolor='white')
    for i,c in enumerate(counts): ax.text(i, c+15, f'{c}\n({100*c/total:.1f}%)', ha='center', fontsize=7.5)
    ax.set_ylabel('Number of samples')
    nm, ns, mr = row['n_migrated'], row['n_samples'], 100*row['migration_rate']
    ax.set_title(f'Fig.8: R2 New Optimal Delta Distribution (N={total}, orig delta*=0.50)')
    ax.text(0.5, -0.15, f'{nm}/{ns} ({mr:.1f}%) migrated above 0.50',
            transform=ax.transAxes, ha='center', fontsize=8, style='italic')
    save(fig, 'fig8_upper_bound_audit')

# ═══ Fig 9: P6-P8 Real Data ═══
def fig9():
    real_dir = os.path.join(A, 'real_data', 'nist-6061-t6-fatigue')
    df = pd.read_csv(os.path.join(real_dir, 'real_holdout_results.csv'))
    nn_df = df[df['method']=='nn']; nn_ids = sorted(nn_df['model_id'].unique())
    eps = 1e-9
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    # A: Median D
    ax = axes[0,0]; x = np.arange(3); w = 0.22
    for i,(method,label,c) in enumerate([('default','Default','#0072B2'),('l2','L2','#D55E00')]):
        meds = [np.median(df[(df['train_n']==n)&(df['method']==method)]['D']) for n in [7,10,20]]
        ax.bar(x+i*w, meds, w, label=label, color=c, alpha=0.85)
    nn_meds = [np.median([np.median(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['D']) for m in nn_ids]) for n in [7,10,20]]
    ax.bar(x+2*w, nn_meds, w, label='NN (med of 15)', color='#009E73', alpha=0.85)
    ax.set_xticks(x+w); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('KS Distance D'); ax.legend(fontsize=7); ax.set_title('KS Distance by Method')
    # B: NN vs Default
    ax = axes[0,1]
    for n in [7,10,20]:
        d_D = df[(df['train_n']==n)&(df['method']=='default')][['repeat_index','D']].set_index('repeat_index')
        rates = [int((nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==mid)][['repeat_index','D']].set_index('repeat_index').join(d_D,lsuffix='_n',rsuffix='_d')['D_n']-nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==mid)][['repeat_index','D']].set_index('repeat_index').join(d_D,lsuffix='_n',rsuffix='_d')['D_d']<-eps).sum())/500 for mid in nn_ids]
        ax.boxplot(rates, positions=[n], widths=0.25)
    ax.axhline(y=0.5,color='gray',linestyle='--',alpha=0.5)
    ax.set_xticks([7,10,20]); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('Win Rate vs Default'); ax.set_title('NN vs Default: 15-Model')
    # C: Default vs L2
    ax = axes[1,0]
    for idx,n in enumerate([7,10,20]):
        d_D = df[(df['train_n']==n)&(df['method']=='default')][['repeat_index','D']].set_index('repeat_index')
        l_D = df[(df['train_n']==n)&(df['method']=='l2')][['repeat_index','D']].set_index('repeat_index')
        m = d_D.join(l_D,lsuffix='_d',rsuffix='_l')
        diff=m['D_d']-m['D_l']
        w_l2,w_d,ties = int((diff>eps).sum()),int((diff<-eps).sum()),int((abs(diff)<=eps).sum())
        ax.bar(idx-0.12,w_d,0.1,color='#0072B2',label='Default wins' if idx==0 else '')
        ax.bar(idx,ties,0.1,color='gray',label='Ties' if idx==0 else '')
        ax.bar(idx+0.12,w_l2,0.1,color='#D55E00',label='L2 wins' if idx==0 else '')
    ax.set_xticks([0,1,2]); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('Count'); ax.legend(fontsize=6); ax.set_title('Default vs L2 Paired')
    # D: Support-set
    ax = axes[1,1]
    for method,label,c in [('default','Default','#0072B2'),('l2','L2','#D55E00')]:
        sv=[np.mean(df[(df['train_n']==n)&(df['method']==method)]['support_set_violation']) for n in [7,10,20]]
        ax.plot([7,10,20],sv,'o-',color=c,label=label,markersize=5)
    nn_sv=[np.median([np.mean(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['support_set_violation'].dropna()) for m in nn_ids]) for n in [7,10,20]]
    ax.plot([7,10,20],nn_sv,'s--',color='#009E73',label='NN (med)',markersize=5)
    ax.set_xlabel('Train n'); ax.set_ylabel('Violation Rate'); ax.legend(fontsize=7)
    ax.set_title('Support-Set Violation Rate')
    fig.suptitle('Fig.9: P6-P8 NIST 6061-T6 Real Data Holdout Validation', fontsize=11, fontweight='bold')
    save(fig, 'fig9_real_data_comparison')

# ═══ S1: Cross-fit ═══
def fig_s1():
    df = pd.read_csv(os.path.join(A, 'E1_E2_crossfit', 'selected_deltas.csv'))
    l2 = df[df['layer']=='L2']
    fig, ax = plt.subplots(figsize=(6, 3.5))
    for n in sorted(l2['n'].unique()):
        nd = l2[l2['n']==n]
        ax.scatter([n]*len(nd), nd['delta_star'], alpha=0.6, s=30)
    ax.set_xlabel('n'); ax.set_ylabel('Selected delta')
    ax.set_title('S1: L2 Cross-Fit Selected Delta by Fold and n')
    save(fig, 'fig_s1_crossfit')

# ═══ S2: Beta-Profile (from E2_beta_profile_audit) ═══
def fig_s2():
    df = pd.read_csv(os.path.join(A, 'E2_beta_profile_audit', 'by_beta_n.csv'))
    betas = sorted(df['beta'].unique())
    ns = sorted(df['n'].unique())
    fig, axes = plt.subplots(1, len(ns), figsize=(12, 4), sharey=True)
    for i, n in enumerate(ns):
        ax = axes[i]; ndf = df[df['n']==n]
        meds = [float(ndf[ndf['beta']==b]['local_gradient_slope_median'].iloc[0]) for b in betas]
        q1s  = [float(ndf[ndf['beta']==b]['local_gradient_slope_q1'].iloc[0]) for b in betas]
        q3s  = [float(ndf[ndf['beta']==b]['local_gradient_slope_q3'].iloc[0]) for b in betas]
        yerr = [[m-q1 for m,q1 in zip(meds,q1s)], [q3-m for m,q3 in zip(meds,q3s)]]
        ax.errorbar(range(len(betas)), meds, yerr=yerr, fmt='o-', color='#0072B2', capsize=4, markersize=6)
        ax.set_xticks(range(len(betas))); ax.set_xticklabels([str(b) for b in betas])
        ax.set_title(f'n={n}'); ax.set_xlabel('beta')
    axes[0].set_ylabel('Local Gradient Slope (median +/- IQR)')
    fig.suptitle('S2: Beta-Profile — local_gradient_slope by beta and n', fontweight='bold')
    # Add Spearman rho annotation
    with open(os.path.join(A, 'E2_beta_profile_audit', 'trend_summary.csv')) as f:
        ts = pd.read_csv(f)
    rhos = ts[ts['metric']=='local_gradient_slope']['spearman_rho'].values
    rho_str = ', '.join([f'n={ns[i]}: rho={rhos[i]:.3f}' for i in range(len(ns))])
    fig.subplots_adjust(bottom=0.18)
    fig.text(0.5, 0.04, f'Spearman rho: {rho_str}', ha='center', fontsize=7.5, style='italic')
    save(fig, 'fig_s2_beta_profile')

# ═══ S3: Seed Stability ═══
def fig_s3():
    df = pd.read_csv(os.path.join(A, 'E3b_vector_mlp', 'seed_stability.csv'))
    fig, ax = plt.subplots(figsize=(5, 3.5))
    x = np.arange(3); w = 0.2
    for i, n in enumerate([7,10,20]):
        ax.bar(x+i*w, [df[f'J1_n{n}'].iloc[j] for j in range(3)], w, label=f'n={n}', alpha=0.8)
    ax.set_xticks(x+w); ax.set_xticklabels([f'seed={s}' for s in df['seed']])
    ax.set_ylabel('J1'); ax.legend(fontsize=7); ax.set_title('S3: Three-Seed J1 by n')
    save(fig, 'fig_s3_seed_stability')

# ═══ S4: E4a by Fold ═══
def fig_s4():
    df = pd.read_csv(os.path.join(A, 'E4_robustness', 'E4a_feature_ablation.csv'))
    groups = ['full', 'scale_quantile', 'shape', 'n']
    folds_u = sorted(set(str(f) for f in df['fold'].unique()))
    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(groups)); w = 0.13
    for fi, fold in enumerate(folds_u):
        means = [float(df[(df['feature_group']==g)&(df['fold'].astype(str)==fold)]['pooled_J1'].mean()) for g in groups]
        ax.bar(x+fi*w-1.5*w, means, w, label=fold.replace('combo_fold_','f'), alpha=0.8)
    ax.set_xticks(x); ax.set_xticklabels(groups); ax.set_ylabel('Pooled J1')
    ax.legend(fontsize=6); ax.set_title('S4: E4a Retained-Subset by Fold')
    save(fig, 'fig_s4_ablation_folds')

# ═══ S5: E4d Per-Model (15 models, by_model.csv) ═══
def fig_s5():
    bm = pd.read_csv(os.path.join(A, 'E4_robustness', 'E4d_paired_comparisons_by_model.csv'))
    assert len(bm) == 90, f'S5: expected 90 rows (2 tracks x 15 models x 3 refs), got {len(bm)}'
    # Filter to Default reference only (l6_J1_common is same per model per track)
    bm_def = bm[bm['reference_model']=='Default'].copy()
    assert len(bm_def) == 30, f'S5: expected 30 Default-ref rows, got {len(bm_def)}'
    bm_def['label'] = bm_def['fold'].astype(str) + '_s' + bm_def['seed'].astype(str)
    tracks = ['E4b_boundary', 'E4c_offgrid']
    tlabels = ['Boundary', 'Off-grid']
    colors = ['#D55E00', '#0072B2']
    fig, ax = plt.subplots(figsize=(10, 4))
    for trk, tl, c in zip(tracks, tlabels, colors):
        td = bm_def[bm_def['track']==trk].sort_values('label')
        ax.bar(np.arange(15) + (0.3 if trk=='E4c_offgrid' else -0.3),
               td['l6_J1_common'].values, 0.3, label=tl, color=c, alpha=0.8)
    # Annotate per-track pooled J1 from summary_e4d.json
    with open(os.path.join(A, 'E4_robustness', 'summary_e4d.json'), encoding='utf-8') as f:
        s = json.load(f)
    j1b = s['per_track_pooled_J1']['E4b_boundary']['Vector-MLP-L6']['J1']
    j1o = s['per_track_pooled_J1']['E4c_offgrid']['Vector-MLP-L6']['J1']
    ax.axhline(y=j1b, color='#D55E00', linestyle='--', linewidth=1, alpha=0.7, label=f'Boundary pooled J1={j1b:.4f}')
    ax.axhline(y=j1o, color='#0072B2', linestyle='--', linewidth=1, alpha=0.7, label=f'Off-grid pooled J1={j1o:.4f}')
    ax.set_xticks(range(15)); ax.set_xticklabels(sorted(bm_def['label'].unique()), rotation=45, fontsize=6)
    ax.set_ylabel('l6_J1_common (common-sample)'); ax.legend(fontsize=7, ncol=2)
    ax.set_title('S5: E4d Per-Model Common-Sample J1 (15 models, Default reference)')
    save(fig, 'fig_s5_boundary_folds')

# ═══ S6: R2 Full Distribution ═══
def fig_s6():
    cs = pd.read_csv(os.path.join(A, 'delta_upper_bound_audit', 'cohort_summary.csv'))
    row = cs[cs['cohort_delta']==0.50].iloc[0]
    dist = ast.literal_eval(row['extended_best_delta_distribution'])
    deltas = sorted([float(k) for k in dist.keys()]); counts = [dist[str(d)] for d in deltas]
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.bar(range(len(deltas)), counts, color='#0072B2', alpha=0.8, width=0.8)
    ax.set_xticks(range(0, len(deltas), 5))
    ax.set_xticklabels([f'{deltas[i]:.2f}' for i in range(0,len(deltas),5)])
    ax.set_xlabel('Extended best delta'); ax.set_ylabel('Count')
    ax.set_title(f'S6: R2 Full Extended Best Delta Distribution (N={sum(counts)})')
    save(fig, 'fig_s6_upper_bound_dist')

# ═══ S7: NN 15-Model ═══
def fig_s7():
    real_dir = os.path.join(A, 'real_data', 'nist-6061-t6-fatigue')
    df = pd.read_csv(os.path.join(real_dir, 'real_holdout_results.csv'))
    nn_df = df[df['method']=='nn']; nn_ids = sorted(nn_df['model_id'].unique())
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for idx, n in enumerate([7,10,20]):
        ax = axes[idx]
        meds = sorted([np.median(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['D']) for m in nn_ids])
        ax.barh(range(15), meds, color='#009E73', alpha=0.7, height=0.7)
        ax.axvline(x=np.mean(meds), color='black', linestyle='--', linewidth=1.5, label=f'mean={np.mean(meds):.4f}')
        ax.set_xlabel('Median D'); ax.set_title(f'n={n}'); ax.legend(fontsize=7)
    fig.suptitle('S7: NN 15-Model Median D by Train n', fontweight='bold')
    save(fig, 'fig_s7_nn_15model_dist')

# ═══ S8: Support-Set Detail ═══
def fig_s8():
    real_dir = os.path.join(A, 'real_data', 'nist-6061-t6-fatigue')
    df = pd.read_csv(os.path.join(real_dir, 'real_holdout_results.csv'))
    nn_df = df[df['method']=='nn']; nn_ids = sorted(nn_df['model_id'].unique())
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(3); w = 0.2
    for i,(method,label,c) in enumerate([('default','Default','#0072B2'),('l2','L2','#D55E00')]):
        sv=[np.mean(df[(df['train_n']==n)&(df['method']==method)]['support_set_violation']) for n in [7,10,20]]
        ax.bar(x+i*w,sv,w,label=label,color=c,alpha=0.85)
    nn_m=[np.median([np.mean(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['support_set_violation'].dropna()) for m in nn_ids]) for n in [7,10,20]]
    ax.bar(x+2*w,nn_m,w,label='NN (med of 15)',color='#009E73',alpha=0.85)
    ax.set_xticks(x+w); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('Violation Rate'); ax.legend(); ax.set_title('S8: Support-Set Violation by Method')
    save(fig, 'fig_s8_support_set')

# ═════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print(f'Generating figures: matplotlib={matplotlib.__version__} numpy={np.__version__} pandas={pd.__version__}')
    fig6(); fig7(); fig8(); fig9()
    fig_s1(); fig_s2(); fig_s3(); fig_s4(); fig_s5(); fig_s6(); fig_s7(); fig_s8()
    print('Done: 4 main + 8 supp.')
