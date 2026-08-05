"""E01-6 三方法蒙特卡洛对比图 — 修订版（v2）"""
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
colors = {'mdm': '#D55E00', 'mle': '#0072B2', 'lse': '#009E73'}
labels_map = {'mdm': 'MDM', 'mle': 'MLE', 'lse': 'LS'}

x95_true = 100 + 1000 * (-np.log(0.95)) ** (1/2.5)
x99_true = 100 + 1000 * (-np.log(0.99)) ** (1/2.5)

# Load and parse
data = {}  # (n, method) -> list of dicts
for n in ns:
    for m in methods:
        data[(n, m)] = []

with open(os.path.join(data_dir, 'E01-6_mc_results.csv'), 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        n = int(row['n'])
        m = row['method']
        try:
            bh = float(row['beta_hat'])
            eh = float(row['eta_hat'])
            gh = float(row['gamma_hat'])
            err_b = bh - 2.5
            err_e = eh - 1000
            err_g = gh - 100
            x95h = gh + eh * (-np.log(0.95)) ** (1/bh)
            x99h = gh + eh * (-np.log(0.99)) ** (1/bh)
            data[(n, m)].append({
                'err_beta': err_b, 'err_eta': err_e, 'err_gamma': err_g,
                'err_x95': x95h - x95_true, 'err_x99': x99h - x99_true,
                'gamma_hat': gh, 'converged': True,
            })
        except (TypeError, ValueError):
            data[(n, m)].append({'converged': False})


def get_rmses(key):
    """Return list of RMSE values per n for each method."""
    result = {}
    for m in methods:
        vals = []
        for n in ns:
            errs = [d[key] for d in data[(n, m)] if d.get(key) is not None]
            vals.append(np.sqrt(np.mean(np.array(errs)**2)) if errs else 0)
        result[m] = vals
    return result


# --- Figure 1: Parameter RMSE ---
fig, axes = plt.subplots(1, 3, figsize=(7, 2.2))
for idx, (p, pname) in enumerate([('beta', 'β̂'), ('eta', 'η̂'), ('gamma', 'γ̂')]):
    ax = axes[idx]
    rmse_data = get_rmses(f'err_{p}')
    x = np.arange(len(ns))
    w = 0.25
    for j, m in enumerate(methods):
        ax.bar(x + j*w, rmse_data[m], w, color=colors[m], label=labels_map[m], edgecolor='none')
    ax.set_xticks(x + w)
    ax.set_xticklabels([f'n={n}' for n in ns], fontsize=5.5)
    ax.set_ylabel(f'RMSE of {pname}', fontsize=7)
    ax.set_title(pname, fontsize=7, fontweight='bold')
    if idx == 0:
        ax.legend(fontsize=5, frameon=False)

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-6_参数视角RMSE.png'), dpi=600, facecolor='white')
plt.close()
print("saved: E01-6_参数视角RMSE.png")

# --- Figure 2: Engineering RMSE ---
fig, axes = plt.subplots(1, 2, figsize=(4.5, 2.2))
for idx, tag in enumerate(['x95', 'x99']):
    ax = axes[idx]
    rmse_data = get_rmses(f'err_{tag}')
    x = np.arange(len(ns))
    w = 0.25
    for j, m in enumerate(methods):
        ax.bar(x + j*w, rmse_data[m], w, color=colors[m], label=labels_map[m], edgecolor='none')
    ax.set_xticks(x + w)
    ax.set_xticklabels([f'n={n}' for n in ns], fontsize=5.5)
    ax.set_ylabel(f'RMSE of x̂$_{{{tag[1:]}}}$', fontsize=7)
    ax.set_title(f'x$_{{{tag[1:]}}}$ RMSE', fontsize=7, fontweight='bold')
    if idx == 0:
        ax.legend(fontsize=5, frameon=False)

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-6_工程视角RMSE.png'), dpi=600, facecolor='white')
plt.close()
print("saved: E01-6_工程视角RMSE.png")

# --- Figure 3: γ̂ distribution ---
fig, axes = plt.subplots(1, 3, figsize=(7, 2.2))
for idx, n in enumerate([5, 20, 50]):
    ax = axes[idx]
    for m in methods:
        vals = [d['gamma_hat'] for d in data[(n, m)] if d.get('gamma_hat') is not None]
        if not vals:
            continue
        vals = np.clip(np.array(vals), -200, 600)
        ax.hist(vals, bins=40, alpha=0.5, color=colors[m], label=labels_map[m],
                density=True, edgecolor='none')
    ax.axvline(100, color='k', linewidth=0.6, linestyle='--', label='True γ=100')
    ax.set_xlabel('γ̂', fontsize=7)
    ax.set_ylabel('Density', fontsize=7)
    ax.set_title(f'n={n}', fontsize=7, fontweight='bold')
    if idx == 0:
        ax.legend(fontsize=5, frameon=False)

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-6_gamma分布.png'), dpi=600, facecolor='white')
plt.close()
print("saved: E01-6_gamma分布.png")

# --- Figure 4: Failure rate ---
fig, ax = plt.subplots(figsize=(3.5, 2))
x = np.arange(len(ns))
w = 0.25
for j, m in enumerate(methods):
    frs = []
    for n in ns:
        total = len(data[(n, m)])
        n_fail = sum(1 for d in data[(n, m)] if not d.get('converged', True))
        frs.append(n_fail / total * 100 if total else 0)
    ax.bar(x + j*w, frs, w, color=colors[m], label=labels_map[m], edgecolor='none')
ax.set_xticks(x + w)
ax.set_xticklabels([f'n={n}' for n in ns], fontsize=6)
ax.set_ylabel('Failure rate (%)', fontsize=7)
ax.set_title('Estimation failure rate by sample size', fontsize=7, fontweight='bold')
ax.legend(fontsize=5, frameon=False)

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-6_失败率.png'), dpi=600, facecolor='white')
plt.close()
print("saved: E01-6_失败率.png")

print("done")
