"""E01-3a RMSE相同结构不同"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import os, csv

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 7, 'axes.linewidth': 0.5, 'axes.labelsize': 8,
    'axes.spines.top': False, 'axes.spines.right': False,
    'xtick.major.size': 2.5, 'xtick.major.width': 0.5, 'xtick.labelsize': 6,
    'ytick.major.size': 2.5, 'ytick.major.width': 0.5, 'ytick.labelsize': 6,
    'xtick.direction': 'out', 'ytick.direction': 'out',
    'savefig.dpi': 600, 'savefig.bbox': 'tight', 'savefig.pad_inches': 0.05,
})

here = os.path.dirname(__file__)
rng = np.random.default_rng(42)
N = 1000
true_val = 100.0

est_A = true_val + 8 + rng.normal(0, 6, N)   # Bias=8, SD=6
est_B = true_val + 0 + rng.normal(0, 10, N)   # Bias=0, SD=10
err_A = est_A - true_val
err_B = est_B - true_val

# Save data
csv_path = os.path.join(here, '..', '实验数据', 'E01-3a_模拟数据.csv')
with open(csv_path, 'w', newline='') as f:
    w = csv.writer(f)
    w.writerow(["est_A", "est_B", "err_A", "err_B"])
    for i in range(N):
        w.writerow([f"{est_A[i]:.4f}", f"{est_B[i]:.4f}", f"{err_A[i]:.4f}", f"{err_B[i]:.4f}"])

# Plot
fig, axes = plt.subplots(1, 2, figsize=(3.5, 1.8))

ax = axes[0]
bins = np.linspace(-30, 30, 30)
ax.hist(err_A, bins=bins, alpha=0.6, color='#D55E00', label='A: Bias=8, SD=6', density=True)
ax.hist(err_B, bins=bins, alpha=0.6, color='#0072B2', label='B: Bias=0, SD=10', density=True)
ax.axvline(0, color='k', linewidth=0.4, linestyle='--')
ax.set_xlabel('Error', fontsize=7)
ax.set_ylabel('Density', fontsize=7)
ax.legend(fontsize=5, frameon=False, loc='upper right')
ax.set_title('Same RMSE=10, different structure', fontsize=6, pad=3)

ax2 = axes[1]
metrics = ['Bias', 'SD', 'RMSE']
vals_A = [err_A.mean(), err_A.std(), np.sqrt(np.mean(err_A**2))]
vals_B = [err_B.mean(), err_B.std(), np.sqrt(np.mean(err_B**2))]
x = np.arange(3)
w = 0.3
ax2.bar(x - w/2, vals_A, w, color='#D55E00', label='A (biased)', edgecolor='none')
ax2.bar(x + w/2, vals_B, w, color='#0072B2', label='B (unbiased)', edgecolor='none')
ax2.set_xticks(x)
ax2.set_xticklabels(metrics, fontsize=6)
ax2.set_ylabel('Value', fontsize=7)
ax2.legend(fontsize=5, frameon=False)
ax2.set_title('Decomposition reveals truth', fontsize=6, pad=3)

plt.tight_layout()
out = os.path.join(here, '..', '图像', 'E01-3a_RMSE相同结构不同.png')
fig.savefig(out, dpi=600, facecolor='white')
plt.close()
print(f"saved: {out}")
