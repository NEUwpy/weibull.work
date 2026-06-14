"""E01-3 情景2-5 图"""
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

# Load E01-6 data (n=20 subset for scenarios 2-4)
rows_n20 = []
with open(os.path.join(data_dir, 'E01-6_mc_results.csv'), 'r', encoding='utf-8') as f:
    for row in csv.DictReader(f):
        if row['n'] == '20':
            try:
                bh = float(row['beta_hat'])
                eh = float(row['eta_hat'])
                gh = float(row['gamma_hat'])
                rows_n20.append({'method': row['method'], 'bh': bh, 'eh': eh, 'gh': gh,
                                 'err_gamma': gh - 100})
            except (TypeError, ValueError):
                pass

mdm_n20 = [r for r in rows_n20 if r['method'] == 'mdm']
lse_n20 = [r for r in rows_n20 if r['method'] == 'lse']

# ============================
# Scenario 2: Tail insensitivity
# ============================
fig, axes = plt.subplots(1, 2, figsize=(7, 2.5))

# Left: error distribution with tail markers
ax = axes[0]
errs = np.array([r['err_gamma'] for r in mdm_n20])
abs_errs = np.abs(errs)

# Show mean vs median vs P99 vs P99.9
stats = {
    'Mean': abs_errs.mean(),
    'Median': np.median(abs_errs),
    'P99': np.percentile(abs_errs, 99),
    'P99.9': np.percentile(abs_errs, 99.9),
    'Max': abs_errs.max(),
}

# Bar chart of these stats
names = list(stats.keys())
vals = list(stats.values())
colors_bar = ['#0072B2', '#E69F00', '#D55E00', '#CC79A7', '#000000']
ax.bar(range(len(names)), vals, color=colors_bar, edgecolor='none', width=0.6)
for i, v in enumerate(vals):
    ax.text(i, v + 5, f'{v:.0f}', ha='center', fontsize=5.5)
ax.set_xticks(range(len(names)))
ax.set_xticklabels(names, fontsize=6)
ax.set_ylabel('|γ̂ − γ|', fontsize=7)
ax.set_title('MDM n=20: tail metrics vs central metrics', fontsize=6, pad=3)

# Right: empirical survival function of |error|
ax2 = axes[1]
for method, color, label in [('mdm', '#D55E00', 'MDM'), ('lse', '#009E73', 'LSE')]:
    errs_m = np.abs(np.array([r['err_gamma'] for r in rows_n20 if r['method'] == method]))
    sorted_e = np.sort(errs_m)
    surv = 1 - np.arange(1, len(sorted_e)+1) / len(sorted_e)
    ax2.step(sorted_e, surv, where='post', color=color, label=label, linewidth=1)
ax2.axvline(np.median(np.abs([r['err_gamma'] for r in mdm_n20])),
            color='#E69F00', linestyle=':', linewidth=0.5, label='MDM median')
ax2.set_xlabel('|γ̂ − γ|', fontsize=7)
ax2.set_ylabel('Survival probability', fontsize=7)
ax2.set_title('Empirical survival of |error|', fontsize=6, pad=3)
ax2.legend(fontsize=5, frameon=False)
ax2.set_xlim(0, 800)

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-3b_尾部钝感.png'), dpi=600, facecolor='white')
plt.close()
print("saved: E01-3b_尾部钝感.png")

# ============================
# Scenario 3: Relative error explosion near γ=0
# ============================
fig, ax = plt.subplots(figsize=(3.5, 2.2))

gamma_true_vals = [100, 50, 20, 10, 5, 2, 1]
abs_rmse_gamma = 176.0  # from E01-6 n=20 MDM

rel_rmse = [abs_rmse_gamma / g * 100 for g in gamma_true_vals]

ax.plot(gamma_true_vals, rel_rmse, 'o-', color='#D55E00', markersize=4, linewidth=1.2)
ax.axhline(100, color='#ccc', linestyle='--', linewidth=0.4)
ax.set_xlabel('γ true value (η=1000 fixed)', fontsize=7)
ax.set_ylabel('Relative RMSE of γ̂ (%)', fontsize=7)
ax.set_title('Same absolute RMSE → relative RMSE explodes as γ→0', fontsize=6, pad=3)
ax.set_xscale('log')
ax.set_yscale('log')
# Annotate key points
for g, r in zip(gamma_true_vals, rel_rmse):
    if g in [100, 10, 2, 1]:
        ax.annotate(f'{r:.0f}%', (g, r), textcoords='offset points',
                    xytext=(5, 5), fontsize=5, color='#333')

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-3c_相对误差失真.png'), dpi=600, facecolor='white')
plt.close()
print("saved: E01-3c_相对误差失真.png")

# ============================
# Scenario 4: Two-perspective ranking
# ============================
fig, axes = plt.subplots(1, 2, figsize=(5, 2.2))

methods = ['mdm', 'mle', 'lse']
colors_m = {'mdm': '#D55E00', 'mle': '#0072B2', 'lse': '#009E73'}
labels_m = {'mdm': 'MDM', 'mle': 'MLE', 'lse': 'LS'}

# Left: parameter perspective (β RMSE)
ax = axes[0]
rmse_beta = {}
for m in methods:
    errs = np.array([r['bh'] for r in rows_n20 if r['method'] == m]) - 2.5
    rmse_beta[m] = np.sqrt(np.mean(errs**2))

bars = ax.bar(range(3), [rmse_beta[m] for m in methods],
              color=[colors_m[m] for m in methods], edgecolor='none', width=0.5)
for i, m in enumerate(methods):
    ax.text(i, rmse_beta[m] + 0.01, f'{rmse_beta[m]:.3f}', ha='center', fontsize=5.5)
ax.set_xticks(range(3))
ax.set_xticklabels([labels_m[m] for m in methods], fontsize=6)
ax.set_ylabel('RMSE of β̂', fontsize=7)
ax.set_title('Parameter perspective', fontsize=6, pad=3)
# Mark winner
ax.bar(0, rmse_beta['mdm'], width=0.5, fill=False, edgecolor='red', linewidth=1.5)

# Right: engineering perspective (x95 RMSE)
ax2 = axes[1]
x95_true = 100 + 1000 * (-np.log(0.95)) ** (1/2.5)
rmse_x95 = {}
for m in methods:
    sub = [r for r in rows_n20 if r['method'] == m]
    x95h = np.array([r['gh'] + r['eh'] * (-np.log(0.95)) ** (1/r['bh']) for r in sub])
    rmse_x95[m] = np.sqrt(np.mean((x95h - x95_true)**2))

bars2 = ax2.bar(range(3), [rmse_x95[m] for m in methods],
                color=[colors_m[m] for m in methods], edgecolor='none', width=0.5)
for i, m in enumerate(methods):
    ax2.text(i, rmse_x95[m] + 1, f'{rmse_x95[m]:.1f}', ha='center', fontsize=5.5)
ax2.set_xticks(range(3))
ax2.set_xticklabels([labels_m[m] for m in methods], fontsize=6)
ax2.set_ylabel('RMSE of x̂$_{95}$', fontsize=7)
ax2.set_title('Engineering perspective', fontsize=6, pad=3)

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-3d_两视角排序.png'), dpi=600, facecolor='white')
plt.close()
print("saved: E01-3d_两视角排序.png")

# ============================
# Scenario 5: Cross-parameter MSE incomparability
# ============================
fig, axes = plt.subplots(1, 2, figsize=(5, 2.2))

# Left: raw MSE values
ax = axes[0]
params = ['β', 'η', 'γ']
true_vals = [2.5, 1000, 100]
mse_vals = []
for p_name, true_v in [('bh', 2.5), ('eh', 1000), ('gh', 100)]:
    errs = np.array([r[p_name] for r in mdm_n20]) - true_v
    mse_vals.append(np.mean(errs**2))

bars = ax.bar(range(3), mse_vals, color=['#0072B2', '#E69F00', '#D55E00'],
              edgecolor='none', width=0.5)
for i, (p, v) in enumerate(zip(params, mse_vals)):
    ax.text(i, v + 200, f'{v:.0f}', ha='center', fontsize=6)
ax.set_xticks(range(3))
ax.set_xticklabels(params, fontsize=7)
ax.set_ylabel('MSE', fontsize=7)
ax.set_title('Raw MSE: γ >> β, but different scales', fontsize=6, pad=3)

# Right: relative MSE (MSE / true^2) for comparison
ax2 = axes[1]
rel_mse = [m / t**2 * 100 for m, t in zip(mse_vals, true_vals)]
bars2 = ax2.bar(range(3), rel_mse, color=['#0072B2', '#E69F00', '#D55E00'],
                edgecolor='none', width=0.5)
for i, (p, v) in enumerate(zip(params, rel_mse)):
    ax2.text(i, v + 0.5, f'{v:.1f}%', ha='center', fontsize=6)
ax2.set_xticks(range(3))
ax2.set_xticklabels(params, fontsize=7)
ax2.set_ylabel('Relative MSE (%)', fontsize=7)
ax2.set_title('Relative MSE: now comparable', fontsize=6, pad=3)

plt.tight_layout()
fig.savefig(os.path.join(img_dir, 'E01-3e_跨量纲MSE.png'), dpi=600, facecolor='white')
plt.close()
print("saved: E01-3e_跨量纲MSE.png")

print("done")
