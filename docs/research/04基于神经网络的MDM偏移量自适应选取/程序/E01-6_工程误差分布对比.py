"""E01-6 工程视角误差分布：n=5 vs n=20 对比"""
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

methods = ['mdm', 'mle', 'lse']
colors_m = {'mdm': '#D55E00', 'mle': '#0072B2', 'lse': '#009E73'}
labels_m = {'mdm': 'MDM', 'mle': 'MLE', 'lse': 'LS'}
x95_true = 100 + 1000 * (-np.log(0.95)) ** (1/2.5)
x99_true = 100 + 1000 * (-np.log(0.99)) ** (1/2.5)

# Load data for n=5 and n=20
data = {}
for n in [5, 20]:
    for m in methods:
        data[(n, m)] = {'err_x95': [], 'err_x99': []}

with open(os.path.join(data_dir, 'E01-6_mc_results.csv'), 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        n = int(row['n'])
        if n not in [5, 20]:
            continue
        m = row['method']
        try:
            bh = float(row['beta_hat'])
            eh = float(row['eta_hat'])
            gh = float(row['gamma_hat'])
            data[(n, m)]['err_x95'].append(gh + eh * (-np.log(0.95)) ** (1/bh) - x95_true)
            data[(n, m)]['err_x99'].append(gh + eh * (-np.log(0.99)) ** (1/bh) - x99_true)
        except (TypeError, ValueError):
            pass

for key in data:
    for k in data[key]:
        data[key][k] = np.array(data[key][k])

# Shared x-axis range from n=5
shared = {}
for tag in ['err_x95', 'err_x99']:
    all_vals = np.concatenate([data[(5, m)][tag] for m in methods])
    lo, hi = np.percentile(all_vals, [0.5, 99.5])
    margin = (hi - lo) * 0.1
    shared[tag] = (lo - margin, hi + margin)

# Plot: 2 rows (x95, x99) × 2 cols (n=5, n=20), each col has 3 overlaid histograms
fig, axes = plt.subplots(2, 2, figsize=(7, 4.5))

for row_idx, (tag, plabel) in enumerate([('err_x95', 'x0.95 error'), ('err_x99', 'x0.99 error')]):
    for col_idx, n in enumerate([5, 20]):
        ax = axes[row_idx, col_idx]
        lo, hi = shared[tag]
        bins = np.linspace(lo, hi, 35)

        for m in methods:
            vals = data[(n, m)][tag]
            if len(vals) < 10:
                continue
            ax.hist(vals, bins=bins, color=colors_m[m], edgecolor='none',
                    alpha=0.5, density=True, label=f'{labels_m[m]} (Bias={np.mean(vals):.1f})')

        ax.axvline(0, color='k', linewidth=0.6, linestyle='--')
        ax.set_xlabel('Error', fontsize=6)
        ax.set_ylabel('Density', fontsize=6)
        ax.set_title(f'{plabel}, n={n}', fontsize=7, fontweight='bold')
        if row_idx == 0 and col_idx == 0:
            ax.legend(fontsize=5, frameon=False, loc='upper right')

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-6_工程误差分布_n5_n20.png'), dpi=600, facecolor='white')
plt.close()
print('saved: E01-6_工程误差分布_n5_n20.png')
