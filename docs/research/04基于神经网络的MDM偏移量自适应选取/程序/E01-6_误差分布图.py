"""E01-6 补充图：误差分布直方图 + 箱线图 + 工程视角分布"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import csv, os

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 7, 'axes.linewidth': 0.5, 'axes.labelsize': 8,
    'axes.spines.top': False, 'axes.spines.right': False,
    'xtick.major.size': 2.5, 'xtick.major.width': 0.5, 'xtick.labelsize': 6,
    'ytick.major.size': 2.5, 'ytick.major.width': 0.5, 'ytick.labelsize': 6,
    'xtick.direction': 'out', 'ytick.direction': 'out',
    'savefig.dpi': 600, 'savefig.bbox': 'tight', 'savefig.pad_inches': 0.05,
})

here = os.path.dirname(os.path.abspath(__file__))
data_dir = os.path.join(here, '..', '实验数据')
img_dir = os.path.join(here, '..', '图像')

ns = [5, 7, 10, 15, 20, 50]
methods = ['mdm', 'mle', 'lse']
colors_m = {'mdm': '#D55E00', 'mle': '#0072B2', 'lse': '#009E73'}
labels_m = {'mdm': 'MDM', 'mle': 'MLE', 'lse': 'LS'}
x95_true = 100 + 1000 * (-np.log(0.95)) ** (1/2.5)
x99_true = 100 + 1000 * (-np.log(0.99)) ** (1/2.5)

# Load data
data = {}  # (n, method) -> dict of arrays
for n in ns:
    for m in methods:
        data[(n, m)] = {'err_beta': [], 'err_eta': [], 'err_gamma': [],
                        'err_x95': [], 'err_x99': [], 'gamma_hat': []}

with open(os.path.join(data_dir, 'E01-6_mc_results.csv'), 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        n = int(row['n'])
        m = row['method']
        try:
            bh = float(row['beta_hat'])
            eh = float(row['eta_hat'])
            gh = float(row['gamma_hat'])
            d = data[(n, m)]
            d['err_beta'].append(bh - 2.5)
            d['err_eta'].append(eh - 1000)
            d['err_gamma'].append(gh - 100)
            d['err_x95'].append(gh + eh * (-np.log(0.95)) ** (1/bh) - x95_true)
            d['err_x99'].append(gh + eh * (-np.log(0.99)) ** (1/bh) - x99_true)
            d['gamma_hat'].append(gh)
        except (TypeError, ValueError):
            pass

for key in data:
    for k in data[key]:
        data[key][k] = np.array(data[key][k])


# ============================================================
# Figure A: 3×3 error distribution histogram
# ============================================================
# Compute shared bin ranges from n=5 (widest)
shared_ranges = {}
for pkey in ['err_beta', 'err_eta', 'err_gamma']:
    all_vals = np.concatenate([data[(5, m)][pkey] for m in methods])
    lo, hi = np.percentile(all_vals, [0.5, 99.5])
    margin = (hi - lo) * 0.1
    shared_ranges[pkey] = (lo - margin, hi + margin)


def plot_error_grid(n, filename):
    fig, axes = plt.subplots(3, 3, figsize=(7, 6))
    params = [('err_beta', 'β̂ − β'), ('err_eta', 'η̂ − η'), ('err_gamma', 'γ̂ − γ')]

    for row_idx, (pkey, plabel) in enumerate(params):
        for col_idx, m in enumerate(methods):
            ax = axes[row_idx, col_idx]
            vals = data[(n, m)][pkey]
            if len(vals) < 10:
                ax.text(0.5, 0.5, 'No data', ha='center', va='center',
                        transform=ax.transAxes, fontsize=6)
                ax.set_title(f'{labels_m[m]}', fontsize=6, fontweight='bold')
                if row_idx == 2:
                    ax.set_xlabel('Error', fontsize=6)
                continue

            lo, hi = shared_ranges[pkey]
            bins = np.linspace(lo, hi, 35)

            ax.hist(vals, bins=bins, color=colors_m[m], edgecolor='none',
                    alpha=0.7, density=True)
            ax.axvline(0, color='k', linewidth=0.6, linestyle='--')
            ax.axvline(np.mean(vals), color='#E69F00', linewidth=0.8,
                       label=f'Bias={np.mean(vals):.1f}')

            if row_idx == 0:
                ax.set_title(f'{labels_m[m]}', fontsize=6, fontweight='bold')
            if row_idx == 2:
                ax.set_xlabel('Error', fontsize=6)
            if col_idx == 0:
                ax.set_ylabel(plabel, fontsize=6)
            ax.legend(fontsize=4.5, frameon=False, loc='upper right')

    fig.suptitle(f'Parameter estimation error distribution (n={n})',
                 fontsize=8, fontweight='bold', y=0.98)
    plt.tight_layout(rect=[0, 0, 1, 0.96])
    fig.savefig(os.path.join(img_dir, filename), dpi=600, facecolor='white')
    plt.close()
    print(f'saved: {filename}')


plot_error_grid(5, 'E01-6_误差分布_n5.png')
plot_error_grid(20, 'E01-6_误差分布_n20.png')


# ============================================================
# Figure B: Boxplot - error vs sample size
# ============================================================
fig, axes = plt.subplots(1, 3, figsize=(7, 2.5))
params = [('err_beta', 'β̂ − β'), ('err_eta', 'η̂ − η'), ('err_gamma', 'γ̂ − γ')]

for idx, (pkey, plabel) in enumerate(params):
    ax = axes[idx]
    positions_base = np.arange(len(ns))

    for j, m in enumerate(methods):
        box_data = []
        positions = []
        for i, n in enumerate(ns):
            vals = data[(n, m)][pkey]
            if len(vals) > 0:
                # Clip extreme outliers for visualization
                if pkey == 'err_gamma':
                    vals = np.clip(vals, -400, 800)
                box_data.append(vals)
                positions.append(positions_base[i] + j * 0.25)

        bp = ax.boxplot(box_data, positions=positions, widths=0.2,
                        patch_artist=True, showfliers=False,
                        boxprops=dict(facecolor=colors_m[m], alpha=0.6),
                        medianprops=dict(color='black', linewidth=0.8),
                        whiskerprops=dict(linewidth=0.5),
                        capprops=dict(linewidth=0.5))

    ax.axhline(0, color='k', linewidth=0.4, linestyle='--')
    ax.set_xticks(positions_base + 0.25)
    ax.set_xticklabels([f'n={n}' for n in ns], fontsize=5.5)
    ax.set_ylabel(plabel, fontsize=7)
    ax.set_title(plabel, fontsize=7, fontweight='bold')
    if idx == 0:
        # Manual legend
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=colors_m[m], alpha=0.6, label=labels_m[m])
                           for m in methods]
        ax.legend(handles=legend_elements, fontsize=5, frameon=False)

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-6_误差箱线图.png'), dpi=600, facecolor='white')
plt.close()
print('saved: E01-6_误差箱线图.png')


# ============================================================
# Figure C: Engineering perspective boxplot (x95)
# ============================================================
fig, axes = plt.subplots(1, 2, figsize=(5, 2.5))
params_eng = [('err_x95', 'x0.95 error'), ('err_x99', 'x0.99 error')]

for idx, (pkey, plabel) in enumerate(params_eng):
    ax = axes[idx]
    positions_base = np.arange(len(ns))

    for j, m in enumerate(methods):
        box_data = []
        positions = []
        for i, n in enumerate(ns):
            vals = data[(n, m)][pkey]
            if len(vals) > 0:
                box_data.append(vals)
                positions.append(positions_base[i] + j * 0.25)

        ax.boxplot(box_data, positions=positions, widths=0.2,
                   patch_artist=True, showfliers=False,
                   boxprops=dict(facecolor=colors_m[m], alpha=0.6),
                   medianprops=dict(color='black', linewidth=0.8),
                   whiskerprops=dict(linewidth=0.5),
                   capprops=dict(linewidth=0.5))

    ax.axhline(0, color='k', linewidth=0.4, linestyle='--')
    ax.set_xticks(positions_base + 0.25)
    ax.set_xticklabels([f'n={n}' for n in ns], fontsize=5.5)
    ax.set_ylabel(plabel, fontsize=7)
    ax.set_title(plabel, fontsize=7, fontweight='bold')
    if idx == 0:
        from matplotlib.patches import Patch
        legend_elements = [Patch(facecolor=colors_m[m], alpha=0.6, label=labels_m[m])
                           for m in methods]
        ax.legend(handles=legend_elements, fontsize=5, frameon=False)

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-6_工程误差箱线图.png'), dpi=600, facecolor='white')
plt.close()
print('saved: E01-6_工程误差箱线图.png')

print('done')
