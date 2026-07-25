"""G5: Generate manuscript figures from formal artifacts.

Figures: fig6 (E4a retained-subset), fig7 (E4d boundary/off-grid),
         fig8 (R2 upper bound), fig9 (P6-P8 real data),
         S1 (cross-fit), S2 (beta-profile), S3 (seed stability),
         S4 (E4a by fold), S5 (boundary by model), S6 (R2 distribution),
         S7 (NN 15-model), S8 (support-set violation).

All values sourced from formal CSV/JSON. No hardcoded numbers.
Uses ast.literal_eval for CSV dictionary parsing.
"""
import os, sys, json, ast
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY = os.path.dirname(CODE_DIR)
ARTIFACTS = os.path.join(STUDY, 'artifacts', 'formal')
OUT = os.path.join(STUDY, 'manuscript', 'figures')
os.makedirs(OUT, exist_ok=True)

plt.rcParams.update({'font.size': 8.5, 'axes.titlesize': 10, 'axes.labelsize': 9,
                     'figure.dpi': 150, 'savefig.dpi': 150, 'savefig.bbox': 'tight'})

def save(fig, name):
    for fmt in ['png', 'svg', 'pdf']:
        p = os.path.join(OUT, f'{name}.{fmt}')
        fig.savefig(p, format=fmt)
        sz = os.path.getsize(p)
        assert sz > 200, f'Figure {p} too small: {sz} bytes'
    plt.close(fig)
    print(f'  {name}.{{png,svg,pdf}}')

# ═══════════════════ Fig 6: E4a Retained-Subset ═══════════════
def fig6():
    df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4a_feature_ablation.csv'))
    groups = ['full', 'scale_quantile', 'shape', 'n']
    labels = ['full\n(13 features)', 'scale_quantile\n(10 features)',
              'shape\n(4 features)', 'n\n(1 feature)']
    colors = ['#0072B2', '#56B4E9', '#D55E00', '#CC79A7']
    means = [float(df[df['feature_group']==g]['pooled_J1'].mean()) for g in groups]
    stds = [float(df[df['feature_group']==g]['pooled_J1'].std(ddof=1)) for g in groups]
    assert len(df) == 60, f'E4a expected 60 runs, got {len(df)}'
    for g in groups:
        assert len(df[df['feature_group']==g]) == 15, f'{g} expected 15 runs'

    fig, ax = plt.subplots(figsize=(6, 4))
    x = range(len(groups))
    ax.bar(x, means, yerr=stds, color=colors, capsize=6, width=0.55, edgecolor='white')
    for i, (m, s) in enumerate(zip(means, stds)):
        ax.text(i, m + s + 0.004, f'{m:.4f}\n+/-{s:.4f}', ha='center', fontsize=7)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel('Pooled J1 (lower better)')
    ax.set_title('E4a: Retained-Subset Comparison (15-run mean +/- SD)')
    save(fig, 'fig6_feature_ablation')

# ═══════════════════ Fig 7: E4d Extrapolation ═════════════════
def fig7():
    df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4d_selector_extrapolation.csv'))
    agg = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4d_paired_comparisons_aggregate.csv'))
    tracks = ['E4b_boundary', 'E4c_offgrid']
    track_labels = {'E4b_boundary': 'Boundary', 'E4c_offgrid': 'Off-grid'}
    colors = {'E4b_boundary': '#D55E00', 'E4c_offgrid': '#0072B2'}

    # Assertions
    for trk in tracks:
        assert len(df[df['track']==trk]) > 0, f'{trk} is empty'
        assert df[df['track']==trk]['fold'].nunique() == 5, f'{trk}: expected 5 folds'
        assert df[df['track']==trk]['seed'].nunique() == 3, f'{trk}: expected 3 seeds'

    # Aggregate J1 from paired_comparisons_aggregate
    nn_rows = agg[agg['reference_model']=='Default']
    j1_vals = {}
    for trk in tracks:
        row = nn_rows[nn_rows['track']==trk]
        assert len(row) == 1, f'{trk}: expected 1 aggregate row for NN Default ref'
        j1_vals[trk] = float(row['l6_J1_common_mean'].iloc[0])
    print(f'  E4d J1: boundary={j1_vals["E4b_boundary"]:.4f}, offgrid={j1_vals["E4c_offgrid"]:.4f}')

    # Panel A: aggregate J1 by track
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    ax1.bar(['Boundary', 'Off-grid'], [j1_vals[t] for t in tracks],
            color=[colors[t] for t in tracks], alpha=0.85, width=0.5)
    for i, t in enumerate(tracks):
        ax1.text(i, j1_vals[t] + 0.005, f'{j1_vals[t]:.4f}', ha='center', fontsize=10)
    ax1.set_ylabel('Pooled J1 (NN models)'); ax1.set_title('E4d: NN Pooled J1 by Track')

    # Panel B: per-model true_loss distribution
    df['model_key'] = df['fold'].astype(str) + '_s' + df['seed'].astype(str)
    models = list(dict.fromkeys(df['model_key'].values))
    for trk, ls in zip(tracks, ['-', '--']):
        meds = [float(df[(df['track']==trk)&(df['model_key']==m)]['true_loss'].median()) for m in models]
        ax2.plot(range(len(models)), meds, color=colors[trk], linestyle=ls,
                 marker='o', markersize=3, label=track_labels[trk])
    ax2.set_xlabel('Model index'); ax2.set_ylabel('Median True Loss')
    ax2.set_title('Per-Model (15 models)'); ax2.legend(fontsize=8)
    save(fig, 'fig7_boundary_offgrid')

# ═══════════════════ Fig 8: R2 Upper Bound ═══════════════════
def fig8():
    cs = pd.read_csv(os.path.join(ARTIFACTS, 'delta_upper_bound_audit', 'cohort_summary.csv'))
    row = cs[cs['cohort_delta']==0.50].iloc[0]
    dist = ast.literal_eval(row['extended_best_delta_distribution'])
    assert len(dist) > 20, f'R2 distribution too small: {len(dist)} bins'

    bins = {'delta=0.50': 0, '0.52-0.70': 0, '0.72-0.90': 0, '0.92-0.98': 0, 'delta=1.00': 0}
    for k, v in dist.items():
        d = float(k)
        if d <= 0.50: bins['delta=0.50'] += v
        elif d <= 0.70: bins['0.52-0.70'] += v
        elif d <= 0.90: bins['0.72-0.90'] += v
        elif d <= 0.98: bins['0.92-0.98'] += v
        else: bins['delta=1.00'] += v
    total = sum(bins.values())
    assert total == 2958, f'R2 total {total} != 2958'

    fig, ax = plt.subplots(figsize=(7, 4))
    names = list(bins.keys()); counts = list(bins.values())
    bar_colors = ['#999999', '#0072B2', '#56B4E9', '#D55E00', '#CC79A7']
    ax.bar(names, counts, color=bar_colors, edgecolor='white')
    for i, (c) in enumerate(counts):
        ax.text(i, c + 15, f'{c}\n({100*c/total:.1f}%)', ha='center', fontsize=7.5)
    ax.set_ylabel('Number of samples')
    nm = row['n_migrated']; ns = row['n_samples']; mr = 100*row['migration_rate']
    ax.set_title(f'R2: New Optimal Delta Distribution (N={total}, orig delta*=0.50)')
    ax.text(0.5, -0.15, f'{nm}/{ns} ({mr:.1f}%) migrated above 0.50',
            transform=ax.transAxes, ha='center', fontsize=8, style='italic')
    save(fig, 'fig8_upper_bound_audit')

# ═══════════════════ Fig 9: P6-P8 Real Data ═══════════════════
def fig9():
    real_dir = os.path.join(ARTIFACTS, 'real_data', 'nist-6061-t6-fatigue')
    df = pd.read_csv(os.path.join(real_dir, 'real_holdout_results.csv'))
    nn_df = df[df['method']=='nn']; nn_ids = sorted(nn_df['model_id'].unique())
    eps = 1e-9
    assert len(df) == 25500; assert len(nn_ids) == 15

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))
    # A: Median D
    ax = axes[0,0]; x = np.arange(3); w = 0.22
    for i, (method, label, c) in enumerate([('default','Default','#0072B2'),('l2','L2','#D55E00')]):
        meds = [np.median(df[(df['train_n']==n)&(df['method']==method)]['D']) for n in [7,10,20]]
        ax.bar(x+i*w, meds, w, label=label, color=c, alpha=0.85)
    nn_meds = [np.median([np.median(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['D']) for m in nn_ids]) for n in [7,10,20]]
    ax.bar(x+2*w, nn_meds, w, label='NN (med of 15)', color='#009E73', alpha=0.85)
    ax.set_xticks(x+w); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('KS Distance D'); ax.legend(fontsize=7); ax.set_title('Holdout KS Distance')

    # B: NN vs Default
    ax = axes[0,1]
    for n in [7,10,20]:
        d_D = df[(df['train_n']==n)&(df['method']=='default')][['repeat_index','D']].set_index('repeat_index')
        rates = []; n_D_all = {}
        for mid in nn_ids:
            n_D = nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==mid)][['repeat_index','D']].set_index('repeat_index')
            m = n_D.join(d_D, lsuffix='_n', rsuffix='_d')
            rates.append(int((m['D_n']-m['D_d']<-eps).sum())/len(m))
        ax.boxplot(rates, positions=[n], widths=0.25)
    ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
    ax.set_xticks([7,10,20]); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('Win Rate vs Default'); ax.set_title('NN vs Default: 15-Model')

    # C: Default vs L2
    ax = axes[1,0]
    for idx, n in enumerate([7,10,20]):
        d_D = df[(df['train_n']==n)&(df['method']=='default')][['repeat_index','D']].set_index('repeat_index')
        l_D = df[(df['train_n']==n)&(df['method']=='l2')][['repeat_index','D']].set_index('repeat_index')
        m = d_D.join(l_D, lsuffix='_d', rsuffix='_l')
        diff = m['D_d']-m['D_l']
        w_l2, w_d, ties = int((diff>eps).sum()), int((diff<-eps).sum()), int((abs(diff)<=eps).sum())
        bars = [w_d, ties, w_l2]
        ax.bar(idx-0.12, bars[0], 0.1, color='#0072B2', label='Default wins' if idx==0 else '')
        ax.bar(idx, bars[1], 0.1, color='gray', label='Ties' if idx==0 else '')
        ax.bar(idx+0.12, bars[2], 0.1, color='#D55E00', label='L2 wins' if idx==0 else '')
    ax.set_xticks([0,1,2]); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('Count'); ax.legend(fontsize=6); ax.set_title('Default vs L2 Paired')

    # D: Support-set violation
    ax = axes[1,1]
    for method, label, c in [('default','Default','#0072B2'),('l2','L2','#D55E00')]:
        sv = [np.mean(df[(df['train_n']==n)&(df['method']==method)]['support_set_violation']) for n in [7,10,20]]
        ax.plot([7,10,20], sv, 'o-', color=c, label=label, markersize=5)
    nn_sv = [np.median([np.mean(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['support_set_violation'].dropna()) for m in nn_ids]) for n in [7,10,20]]
    ax.plot([7,10,20], nn_sv, 's--', color='#009E73', label='NN (med)', markersize=5)
    ax.set_xlabel('Train n'); ax.set_ylabel('Violation Rate'); ax.legend(fontsize=7)
    ax.set_title('Support-Set Violation Rate')
    fig.suptitle('P6-P8: NIST 6061-T6 Real Data', fontsize=11, fontweight='bold')
    save(fig, 'fig9_real_data_comparison')

# ═══════════════════ S1: Cross-fit ═══════════════════════════
def fig_s1():
    df = pd.read_csv(os.path.join(ARTIFACTS, 'E1_E2_crossfit', 'selected_deltas.csv'))
    assert len(df) > 0
    l2 = df[df['layer']=='L2']
    fig, ax = plt.subplots(figsize=(6, 3.5))
    for n in sorted(l2['n'].unique()):
        nd = l2[l2['n']==n]
        ax.scatter([n]*len(nd), nd['delta_star'], alpha=0.6, s=30)
    ax.set_xlabel('n'); ax.set_ylabel('Selected delta')
    ax.set_title('S1: L2 Cross-Fit Selected Delta by Fold and n')
    save(fig, 'fig_s1_crossfit')

# ═══════════════════ S2: Beta-Profile ═══════════════════════
def fig_s2():
    # From E2_oracle_layers results — use the ladder as summary
    with open(os.path.join(ARTIFACTS, 'E2_oracle_layers', 'summary.json'), encoding='utf-8') as f:
        s = json.load(f)
    ladder = s['results']['ladder']
    layers = [r['layer'] for r in ladder]
    j1s = [r['J1_global'] for r in ladder]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.plot(layers, j1s, 'o-', color='#0072B2', markersize=8)
    for i, (l, j) in enumerate(zip(layers, j1s)):
        ax.text(i, j+0.015, f'{j:.4f}', ha='center', fontsize=8)
    ax.set_ylabel('Pooled J1'); ax.set_title('S2: L1-L6 Oracle Ladder (J1 values)')
    save(fig, 'fig_s2_beta_profile')

# ═══════════════════ S3: Seed Stability ═════════════════════
def fig_s3():
    df = pd.read_csv(os.path.join(ARTIFACTS, 'E3b_vector_mlp', 'seed_stability.csv'))
    assert len(df) == 3
    fig, ax = plt.subplots(figsize=(5, 3.5))
    x = np.arange(3); w = 0.2
    for i, n in enumerate([7, 10, 20]):
        vals = [df[f'J1_n{n}'].iloc[j] for j in range(3)]
        ax.bar(x + i*w, vals, w, label=f'n={n}', alpha=0.8)
    ax.set_xticks(x + w); ax.set_xticklabels([f'seed={s}' for s in df['seed']])
    ax.set_ylabel('J1'); ax.legend(fontsize=7); ax.set_title('S3: Three-Seed J1 by n')
    save(fig, 'fig_s3_seed_stability')

# ═══════════════════ S4: E4a by Fold ════════════════════════
def fig_s4():
    df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4a_feature_ablation.csv'))
    groups = ['full', 'scale_quantile', 'shape', 'n']
    folds_u = sorted(set(str(f) for f in df['fold'].unique()))
    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(groups)); w = 0.13
    for fi, fold in enumerate(folds_u):
        means = [float(df[(df['feature_group']==g)&(df['fold'].astype(str)==fold)]['pooled_J1'].mean()) for g in groups]
        ax.bar(x + fi*w - 1.5*w, means, w, label=fold.replace('combo_fold_','f'), alpha=0.8)
    ax.set_xticks(x); ax.set_xticklabels(groups)
    ax.set_ylabel('Pooled J1'); ax.legend(fontsize=6); ax.set_title('S4: E4a by Fold')
    save(fig, 'fig_s4_ablation_folds')

# ═══════════════════ S5: Boundary by Model ══════════════════
def fig_s5():
    df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4d_selector_extrapolation.csv'))
    agg = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4d_paired_comparisons_aggregate.csv'))
    tracks = ['E4b_boundary', 'E4c_offgrid']
    fig, ax = plt.subplots(figsize=(7, 4))
    for trk, c, m in zip(tracks, ['#D55E00','#0072B2'], ['o','s']):
        trk_rows = agg[agg['track']==trk]
        refs = trk_rows['reference_model'].unique()
        for ref in refs:
            row = trk_rows[trk_rows['reference_model']==ref]
            ax.scatter(ref, row['l6_J1_common_mean'], color=c, marker=m, s=80,
                      label=trk if ref==refs[0] else '')
    ax.set_ylabel('l6 J1 common mean'); ax.legend(fontsize=8)
    ax.set_title('S5: E4d NN J1 by Track and Reference')
    save(fig, 'fig_s5_boundary_folds')

# ═══════════════════ S6: R2 Distribution ════════════════════
def fig_s6():
    cs = pd.read_csv(os.path.join(ARTIFACTS, 'delta_upper_bound_audit', 'cohort_summary.csv'))
    row = cs[cs['cohort_delta']==0.50].iloc[0]
    dist = ast.literal_eval(row['extended_best_delta_distribution'])
    deltas = sorted([float(k) for k in dist.keys()])
    counts = [dist[str(d)] for d in deltas]
    fig, ax = plt.subplots(figsize=(10, 3.5))
    ax.bar(range(len(deltas)), counts, color='#0072B2', alpha=0.8, width=0.8)
    ax.set_xticks(range(0, len(deltas), 5))
    ax.set_xticklabels([f'{deltas[i]:.2f}' for i in range(0, len(deltas), 5)])
    ax.set_xlabel('Extended best delta'); ax.set_ylabel('Count')
    ax.set_title(f'S6: R2 Full Extended Best Delta Distribution (N={sum(counts)})')
    save(fig, 'fig_s6_upper_bound_dist')

# ═══════════════════ S7: NN 15-Model ════════════════════════
def fig_s7():
    real_dir = os.path.join(ARTIFACTS, 'real_data', 'nist-6061-t6-fatigue')
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

# ═══════════════════ S8: Support-Set Detail ═════════════════
def fig_s8():
    real_dir = os.path.join(ARTIFACTS, 'real_data', 'nist-6061-t6-fatigue')
    df = pd.read_csv(os.path.join(real_dir, 'real_holdout_results.csv'))
    nn_df = df[df['method']=='nn']; nn_ids = sorted(nn_df['model_id'].unique())
    fig, ax = plt.subplots(figsize=(7, 4))
    x = np.arange(3); w = 0.2
    for i, (method, label, c) in enumerate([('default','Default','#0072B2'),('l2','L2','#D55E00')]):
        sv = [np.mean(df[(df['train_n']==n)&(df['method']==method)]['support_set_violation']) for n in [7,10,20]]
        ax.bar(x+i*w, sv, w, label=label, color=c, alpha=0.85)
    nn_meds = [np.median([np.mean(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['support_set_violation'].dropna()) for m in nn_ids]) for n in [7,10,20]]
    ax.bar(x+2*w, nn_meds, w, label='NN (med of 15)', color='#009E73', alpha=0.85)
    ax.set_xticks(x+w); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('Violation Rate'); ax.legend(); ax.set_title('S8: Support-Set Violation by Method')
    save(fig, 'fig_s8_support_set')

# ═════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('Generating manuscript figures from formal artifacts...')
    import matplotlib as mpl
    print(f'  matplotlib={mpl.__version__} numpy={np.__version__} pandas={pd.__version__}')
    fig6(); fig7(); fig8(); fig9()
    fig_s1(); fig_s2(); fig_s3(); fig_s4(); fig_s5(); fig_s6(); fig_s7(); fig_s8()
    print('Done: 4 main + 8 supplementary figures generated.')
