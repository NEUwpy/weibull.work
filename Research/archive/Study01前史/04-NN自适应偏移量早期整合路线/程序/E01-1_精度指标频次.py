"""E01-1 精度指标频次柱状图"""
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import os

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'Helvetica'],
    'font.size': 7, 'axes.linewidth': 0.5, 'axes.labelsize': 8,
    'axes.spines.top': False, 'axes.spines.right': False,
    'xtick.major.size': 2.5, 'xtick.major.width': 0.5, 'xtick.labelsize': 6,
    'ytick.major.size': 2.5, 'ytick.major.width': 0.5, 'ytick.labelsize': 6,
    'xtick.direction': 'out', 'ytick.direction': 'out',
    'savefig.dpi': 600, 'savefig.bbox': 'tight', 'savefig.pad_inches': 0.05,
})

labels = ['Bias', 'SD / Variance', 'MSE / RMSE', 'Relative error', 'MAE']
counts = [51, 38, 27, 11, 2]
pcts = [c / 68 * 100 for c in counts]

fig, ax = plt.subplots(figsize=(3.5, 1.8))
ax.barh(range(len(labels)), pcts, color='#0072B2', edgecolor='none', height=0.6)
for i, (p, c) in enumerate(zip(pcts, counts)):
    ax.text(p + 1.5, i, f'{p:.0f}% (n={c})', va='center', fontsize=6, color='#333')

ax.set_yticks(range(len(labels)))
ax.set_yticklabels(labels, fontsize=7)
ax.set_xlabel('Usage frequency in literature (%)', fontsize=8)
ax.set_xlim(0, 100)
ax.invert_yaxis()
ax.axvline(x=50, color='#ccc', linewidth=0.4, linestyle='--')

out = os.path.join(os.path.dirname(__file__), '..', '图像', 'E01-1_精度指标频次.png')
fig.savefig(out, dpi=600, facecolor='white')
plt.close()
print(f"saved: {out}")
