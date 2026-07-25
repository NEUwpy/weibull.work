"""G5: Generate manuscript figures from formal artifacts.

Figures: fig6 (E4a retained-subset), fig7 (E4d boundary/offgrid),
         fig8 (R2 upper bound), fig9 (P6-P8 real data),
         figs S1-S8 (supplementary).

All values sourced from formal CSV/JSON artifacts. No hardcoded numbers.
"""
import os, sys, json
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

plt.rcParams.update({'font.size': 9, 'axes.titlesize': 10, 'axes.labelsize': 9,
                     'figure.dpi': 150, 'savefig.dpi': 150, 'savefig.bbox': 'tight'})

def save(fig, name):
    for fmt in ['png', 'svg', 'pdf']:
        p = os.path.join(OUT, f'{name}.{fmt}')
        fig.savefig(p, format=fmt)
        # Verify non-empty
        if os.path.getsize(p) < 100:
            raise RuntimeError(f'Figure {p} is too small ({os.path.getsize(p)} bytes)')
    plt.close(fig)
    print(f'  {name}.{{png,svg,pdf}}')

# ═══════════════════════════════════════════════════════════════
# Fig 6: E4a Retained-Subset Comparison
# ═══════════════════════════════════════════════════════════════
def fig6():
    df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4a_feature_ablation.csv'))
    groups = ['full', 'scale_quantile', 'shape', 'n']
    labels = ['full\n(13 features)', 'scale_quantile\n(10 features)',
              'shape\n(4 features)', 'n\n(1 feature)']
    colors = ['#0072B2', '#56B4E9', '#D55E00', '#CC79A7']
    means = [float(df[df['feature_group']==g]['pooled_J1'].mean()) for g in groups]
    stds = [float(df[df['feature_group']==g]['pooled_J1'].std(ddof=1)) for g in groups]

    fig, ax = plt.subplots(figsize=(6, 4))
    x = range(len(groups))
    ax.bar(x, means, yerr=stds, color=colors, capsize=6, width=0.55, edgecolor='white')
    for i, (m, s) in enumerate(zip(means, stds)):
        ax.text(i, m + s + 0.004, f'{m:.4f}\n±{s:.4f}', ha='center', fontsize=7.5)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel('Pooled J1 (lower better)')
    ax.set_title('E4a: Retained-Subset Comparison (15-run mean +/- SD)')
    save(fig, 'fig6_feature_ablation')

# ═══════════════════════════════════════════════════════════════
# Fig 7: E4d Boundary/Off-grid Extrapolation
# ═══════════════════════════════════════════════════════════════
def fig7():
    df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4d_selector_extrapolation.csv'))
    df['model_key'] = 'f' + df['fold'].astype(str) + '_s' + df['seed'].astype(str)
    tracks = ['boundary', 'offgrid']
    colors_track = {'boundary': '#D55E00', 'offgrid': '#0072B2'}

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4))
    for i, trk in enumerate(tracks):
        vals = df[df['track']==trk]['true_loss'].dropna().values
        ax1.boxplot(vals, positions=[i], widths=0.4, patch_artist=True,
                    boxprops=dict(facecolor=colors_track[trk], alpha=0.7))
    ax1.set_xticklabels(['Boundary', 'Off-grid'])
    ax1.set_ylabel('True Loss'); ax1.set_title('True Loss by Track')

    models = list(dict.fromkeys(df['model_key'].values))
    for trk, ls in [('boundary', '-'), ('offgrid', '--')]:
        meds = [float(df[(df['track']==trk)&(df['model_key']==m)]['true_loss'].median())
                for m in models]
        ax2.plot(range(len(models)), meds, color=colors_track[trk], linestyle=ls,
                 marker='o', markersize=3, label=trk)
    ax2.set_xlabel('Model index'); ax2.set_ylabel('Median True Loss')
    ax2.set_title('Per-Model (15 models)'); ax2.legend(fontsize=8)
    save(fig, 'fig7_boundary_offgrid')

# ═══════════════════════════════════════════════════════════════
# Fig 8: R2 Upper Bound Audit
# ═══════════════════════════════════════════════════════════════
def fig8():
    cs = pd.read_csv(os.path.join(ARTIFACTS, 'delta_upper_bound_audit', 'cohort_summary.csv'))
    row = cs[cs['cohort_delta']==0.50].iloc[0]
    dist = eval(row['extended_best_delta_distribution'])

    # 5-bin partition from actual data
    bins = {'delta=0.50': 0, '0.52-0.70': 0, '0.72-0.90': 0, '0.92-0.98': 0, 'delta=1.00': 0}
    for k, v in dist.items():
        d = float(k)
        if d <= 0.50: bins['delta=0.50'] += v
        elif d <= 0.70: bins['0.52-0.70'] += v
        elif d <= 0.90: bins['0.72-0.90'] += v
        elif d <= 0.98: bins['0.92-0.98'] += v
        else: bins['delta=1.00'] += v

    fig, ax = plt.subplots(figsize=(7, 4))
    names = list(bins.keys())
    counts = list(bins.values())
    colors = ['#999999', '#0072B2', '#56B4E9', '#D55E00', '#CC79A7']
    bars = ax.bar(names, counts, color=colors, edgecolor='white')
    for i, (n, c) in enumerate(zip(names, counts)):
        ax.text(i, c + 15, f'{c}\n({100*c/sum(counts):.1f}%)', ha='center', fontsize=8)
    ax.set_ylabel('Number of samples')
    ax.set_title(f'R2: New Optimal Delta Distribution (N={sum(counts)}, cohort: orig delta*=0.50)')
    nm = row['n_migrated']
    ns = row['n_samples']
    mr = 100 * row['migration_rate']
    ax.text(0.5, -0.18, f'{nm}/{ns} ({mr:.1f}%) migrated above 0.50',
            transform=ax.transAxes, ha='center', fontsize=8, style='italic')
    save(fig, 'fig8_upper_bound_audit')

# ═══════════════════════════════════════════════════════════════
# Fig 9: P6-P8 Real Data
# ═══════════════════════════════════════════════════════════════
def fig9():
    real_dir = os.path.join(ARTIFACTS, 'real_data', 'nist-6061-t6-fatigue')
    df = pd.read_csv(os.path.join(real_dir, 'real_holdout_results.csv'))
    nn_df = df[df['method']=='nn']
    nn_ids = sorted(nn_df['model_id'].unique())
    eps = 1e-9

    fig, axes = plt.subplots(2, 2, figsize=(10, 8))

    # A: Median D by method
    ax = axes[0,0]; x = np.arange(3); w = 0.22
    for i, (method, label, c) in enumerate([
        ('default', 'Default', '#0072B2'), ('l2', 'L2', '#D55E00')]):
        meds = [np.median(df[(df['train_n']==n)&(df['method']==method)]['D']) for n in [7,10,20]]
        ax.bar(x + i*w, meds, w, label=label, color=c, alpha=0.85)
    nn_meds = [np.median([np.median(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['D'])
               for m in nn_ids]) for n in [7,10,20]]
    ax.bar(x + 2*w, nn_meds, w, label='NN (med of 15)', color='#009E73', alpha=0.85)
    ax.set_xticks(x + w); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('KS Distance D'); ax.legend(fontsize=7.5)
    ax.set_title('Holdout KS Distance by Method')

    # B: NN vs Default win rates
    ax = axes[0,1]
    for n in [7,10,20]:
        d_D = df[(df['train_n']==n)&(df['method']=='default')][['repeat_index','D']].set_index('repeat_index')
        rates = []
        for mid in nn_ids:
            n_D = nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==mid)][['repeat_index','D']].set_index('repeat_index')
            m = n_D.join(d_D, lsuffix='_n', rsuffix='_d')
            wr = int((m['D_n']-m['D_d'] < -eps).sum())/len(m)
            rates.append(wr)
        ax.boxplot(rates, positions=[n], widths=0.25)
    ax.axhline(y=0.5, color='gray', linestyle='--', alpha=0.5)
    ax.set_xticks([7,10,20]); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('Win Rate vs Default'); ax.set_title('NN vs Default: 15-Model Distribution')

    # C: Default vs L2
    ax = axes[1,0]
    for idx, n in enumerate([7,10,20]):
        d_D = df[(df['train_n']==n)&(df['method']=='default')][['repeat_index','D']].set_index('repeat_index')
        l_D = df[(df['train_n']==n)&(df['method']=='l2')][['repeat_index','D']].set_index('repeat_index')
        m = d_D.join(l_D, lsuffix='_d', rsuffix='_l')
        diff = m['D_d'] - m['D_l']
        w_l2, w_d, ties = int((diff>eps).sum()), int((diff<-eps).sum()), int((abs(diff)<=eps).sum())
        ax.bar(idx-0.12, w_d, 0.1, color='#0072B2', label='Default wins' if idx==0 else '')
        ax.bar(idx, ties, 0.1, color='gray', label='Ties' if idx==0 else '')
        ax.bar(idx+0.12, w_l2, 0.1, color='#D55E00', label='L2 wins' if idx==0 else '')
    ax.set_xticks([0,1,2]); ax.set_xticklabels(['n=7','n=10','n=20'])
    ax.set_ylabel('Count'); ax.legend(fontsize=6.5); ax.set_title('Default vs L2 Paired')

    # D: Support-set violation
    ax = axes[1,1]
    for method, label, c in [('default','Default','#0072B2'),('l2','L2','#D55E00')]:
        sv = [np.mean(df[(df['train_n']==n)&(df['method']==method)]['support_set_violation']) for n in [7,10,20]]
        ax.plot([7,10,20], sv, 'o-', color=c, label=label, markersize=5)
    nn_sv_meds = []
    for n in [7,10,20]:
        model_sv = [np.mean(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['support_set_violation'].dropna())
                    for m in nn_ids]
        nn_sv_meds.append(np.median(model_sv))
    ax.plot([7,10,20], nn_sv_meds, 's--', color='#009E73', label='NN (med)', markersize=5)
    ax.set_xlabel('Train n'); ax.set_ylabel('Violation Rate'); ax.legend(fontsize=7.5)
    ax.set_title('Support-Set Violation Rate')

    fig.suptitle('P6-P8: NIST 6061-T6 Real Data Holdout Validation', fontsize=11, fontweight='bold')
    save(fig, 'fig9_real_data_comparison')

# ═══════════════════════════════════════════════════════════════
# Supplementary S4: E4a by fold
# ═══════════════════════════════════════════════════════════════
def fig_s4():
    df = pd.read_csv(os.path.join(ARTIFACTS, 'E4_robustness', 'E4a_feature_ablation.csv'))
    groups = ['full', 'scale_quantile', 'shape', 'n']
    labels = ['full', 'scale_quantile', 'shape', 'n']
    fig, ax = plt.subplots(figsize=(8, 4))
    x = np.arange(len(groups)); w = 0.15
    folds_unique = sorted(set(str(f) for f in df['fold'].unique()))
    for fi, fold in enumerate(folds_unique):
        means = [float(df[(df['feature_group']==g)&(df['fold'].astype(str)==fold)]['pooled_J1'].mean()) for g in groups]
        ax.bar(x + fi*w - 1.5*w, means, w, label=fold.replace('combo_fold_','f'), alpha=0.8)
    ax.set_xticks(x); ax.set_xticklabels(labels)
    ax.set_ylabel('Pooled J1'); ax.legend(fontsize=7); ax.set_title('S4: Feature Ablation by Fold')
    save(fig, 'fig_s4_ablation_folds')

# ═══════════════════════════════════════════════════════════════
# Supplementary S7: NN 15-model per-n distribution
# ═══════════════════════════════════════════════════════════════
def fig_s7():
    real_dir = os.path.join(ARTIFACTS, 'real_data', 'nist-6061-t6-fatigue')
    df = pd.read_csv(os.path.join(real_dir, 'real_holdout_results.csv'))
    nn_df = df[df['method']=='nn']
    nn_ids = sorted(nn_df['model_id'].unique())

    fig, axes = plt.subplots(1, 3, figsize=(12, 4))
    for idx, n in enumerate([7,10,20]):
        ax = axes[idx]
        meds = sorted([np.median(nn_df[(nn_df['train_n']==n)&(nn_df['model_id']==m)]['D']) for m in nn_ids])
        ax.barh(range(15), meds, color='#009E73', alpha=0.7, height=0.7)
        ax.axvline(x=np.mean(meds), color='black', linestyle='--', linewidth=1.5, label=f'mean={np.mean(meds):.4f}')
        ax.set_xlabel('Median D'); ax.set_title(f'n={n}'); ax.legend(fontsize=7)
    fig.suptitle('S7: NN 15-Model Median D by Train n', fontweight='bold')
    save(fig, 'fig_s7_nn_15model_dist')

# ═══════════════════════════════════════════════════════════════
if __name__ == '__main__':
    print('Generating manuscript figures from formal artifacts...')
    fig6()
    fig7()
    fig8()
    fig9()
    fig_s4()
    fig_s7()
    print('Done.')
