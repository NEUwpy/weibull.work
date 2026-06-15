"""
E03-4 visualization: ladder chart (updated for expanded grid)
"""
import numpy as np, pandas as pd, matplotlib.pyplot as plt, os

BASE = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE, "实验数据")
IMG_DIR = os.path.join(BASE, "图像")
os.makedirs(IMG_DIR, exist_ok=True)

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': ['Arial', 'DejaVu Sans'],
    'axes.unicode_minus': False, 'figure.dpi': 200, 'savefig.dpi': 200, 'font.size': 10
})

ladder_df = pd.read_csv(os.path.join(DATA_DIR, "E03-4c_ladder_table.csv"))
ladder_df = ladder_df.sort_values('jparam')

methods = ladder_df['method'].tolist()
jparams = ladder_df['jparam'].values
notes = ladder_df['note'].tolist()

default_idx = [i for i, m in enumerate(methods) if 'Default' in m][0]
default_j = jparams[default_idx]

colors = []
for i, m in enumerate(methods):
    if 'Oracle' in m or 'L5' in m:
        colors.append('#2ca02c')
    elif 'L4' in m:
        colors.append('#1f77b4')
    elif 'L3' in m:
        colors.append('#1f77b4')
    elif 'L1' in m:
        colors.append('#17becf')
    elif 'Default' in m:
        colors.append('#ff7f0e')
    elif 'Self' in m:
        colors.append('#d62728')
    elif 'L-moments' in m:
        colors.append('#9467bd')
    else:
        colors.append('#8c564b')

fig, ax = plt.subplots(figsize=(10, 6))
bars = ax.barh(range(len(methods)), jparams, color=colors, edgecolor='white', height=0.6)

# Add labels
for i, (bar, val, note) in enumerate(zip(bars, jparams, notes)):
    delta_pct = (val - default_j) / default_j * 100
    label = f'{val:.4f} ({delta_pct:+.1f}%)'
    ax.text(bar.get_width() + 0.005, bar.get_y() + bar.get_height()/2, label, va='center', fontsize=8)

# Highlight default
bars[default_idx].set_edgecolor('black')
bars[default_idx].set_linewidth(3)

# Oracle line
ax.axvline(x=jparams[0], color='#2ca02c', linestyle='--', alpha=0.5, linewidth=1.5, label='Oracle L5')

ax.set_yticks(range(len(methods)))
ax.set_yticklabels(methods, fontsize=8)
ax.set_xlabel('J_param')
ax.set_title(f'Scheme Ladder (45 configs, beta in [1.5, 5.0])\nBaseline Default J={default_j:.4f}')
ax.invert_yaxis()
ax.legend(fontsize=8)

plt.tight_layout()
fig.savefig(os.path.join(IMG_DIR, "E03-4_ladder_table.png"), bbox_inches='tight')
plt.close()
print("Saved: E03-4_ladder_table.png")

# Also a version grouped by beta
ext_df = pd.read_csv(os.path.join(DATA_DIR, "E03-4b_v2_summary.csv"))

fig, axes = plt.subplots(1, 5, figsize=(20, 4.5), sharey=True)
BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
for idx, beta in enumerate(BETAS):
    ax = axes[idx]
    beta_data = ext_df[ext_df['beta'] == beta]
    methods_show = ['oracle', 'default', 'wmle', 'mdm0', 'dual']
    labels = ['Oracle', 'Default', 'WMLE', 'MDM0', 'Dual']
    colors2 = ['#2ca02c', '#ff7f0e', '#d62728', '#8c564b', '#9467bd']
    x = np.arange(len(methods_show))
    vals = []
    for m in methods_show:
        sub = beta_data[beta_data['method'] == m]
        vals.append(sub['jparam'].mean() if len(sub) > 0 else np.nan)
    ax.bar(x, vals, color=colors2, edgecolor='white')
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=7, rotation=30)
    ax.set_title(f'beta = {beta}')
    if idx == 0:
        ax.set_ylabel('J_param')
    ax.grid(True, alpha=0.3, axis='y')

plt.suptitle('J_param by Method and Beta (expanded grid)', fontsize=12)
plt.tight_layout()
fig.savefig(os.path.join(IMG_DIR, "E03-4_by_config.png"), bbox_inches='tight')
plt.close()
print("Saved: E03-4_by_config.png")
print("Done.")
