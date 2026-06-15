"""
E03 c-space visualization: raw delta vs normalized c comparison
"""
import numpy as np
import pandas as pd
import matplotlib
import matplotlib.pyplot as plt
import os

BASE_DIR = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE_DIR, "实验数据")
IMG_DIR = os.path.join(BASE_DIR, "图像")
os.makedirs(IMG_DIR, exist_ok=True)

try:
    matplotlib.font_manager.findfont('SimHei', fallback_to_default=False)
    CJK = 'SimHei'
except:
    CJK = 'sans-serif'

plt.rcParams.update({
    'font.family': 'sans-serif', 'font.sans-serif': [CJK, 'Arial', 'DejaVu Sans'],
    'axes.unicode_minus': False, 'figure.dpi': 200, 'savefig.dpi': 200,
    'font.size': 10
})

# Load data
c_level = pd.read_csv(os.path.join(DATA_DIR, "E03_cspace_level_optimal.csv"))
c_config = pd.read_csv(os.path.join(DATA_DIR, "E03_cspace_jparam_by_config.csv"))

# Load raw-delta level data for comparison
raw_level = pd.read_csv(os.path.join(DATA_DIR, "E03-2_level_optimal_jparam.csv"))

# ============================================================
# Figure 1: c-space level comparison (like E03_jparam_comparison but in c)
# ============================================================
fig, axes = plt.subplots(2, 2, figsize=(12, 10))

# 1a: Raw delta level ladder
ax = axes[0, 0]
raw_order = ['L0', 'L1', 'L2', 'L3', 'L4']
raw_vals = []
for level in raw_order:
    sub = raw_level[raw_level['level'] == level]
    if level == 'L0':
        raw_vals.append(sub['jparam'].values[0])
    else:
        raw_vals.append(sub['jparam'].mean())
colors_raw = ['#8c564b', '#8c564b', '#8c564b', '#8c564b', '#1f77b4']
ax.bar(range(5), raw_vals, color=colors_raw, edgecolor='white')
ax.set_xticks(range(5))
ax.set_xticklabels(raw_order)
ax.set_ylabel('J_param')
ax.set_title('Raw delta space')
for i, v in enumerate(raw_vals):
    ax.text(i, v + 0.005, f'{v:.3f}', ha='center', fontsize=8)
ax.set_ylim(0.50, 0.62)

# 1b: c-space level ladder
ax = axes[0, 1]
c_vals = []
for level in raw_order:
    sub = c_level[c_level['level'] == level]
    if level == 'L0':
        c_vals.append(sub['jparam'].values[0])
    else:
        c_vals.append(sub['jparam'].mean())
colors_c = ['#2ca02c', '#2ca02c', '#2ca02c', '#2ca02c', '#ff7f0e']
ax.bar(range(5), c_vals, color=colors_c, edgecolor='white')
ax.set_xticks(range(5))
ax.set_xticklabels(raw_order)
ax.set_ylabel('J_param')
ax.set_title('c-space (c=delta/s_v)')
for i, v in enumerate(c_vals):
    ax.text(i, v + 0.005, f'{v:.3f}', ha='center', fontsize=8)
ax.set_ylim(0.50, 0.62)

# 1c: Delta vs c improvement gap comparison
ax = axes[1, 0]
improvements = {
    'L0->L1': (raw_vals[0] - raw_vals[1], c_vals[0] - c_vals[1]),
    'L0->L2': (raw_vals[0] - raw_vals[2], c_vals[0] - c_vals[2]),
    'L0->L3': (raw_vals[0] - raw_vals[3], c_vals[0] - c_vals[3]),
    'L0->L4': (raw_vals[0] - raw_vals[4], c_vals[0] - c_vals[4]),
}
x = np.arange(4)
w = 0.35
raw_imp = [improvements[k][0] for k in improvements]
c_imp = [improvements[k][1] for k in improvements]
ax.bar(x - w/2, raw_imp, w, label='Raw delta', color='#8c564b')
ax.bar(x + w/2, c_imp, w, label='c-space', color='#2ca02c')
ax.set_xticks(x)
ax.set_xticklabels(improvements.keys())
ax.set_ylabel('J_param reduction')
ax.set_title('Improvement over L0')
ax.legend(fontsize=8)

# 1d: J_param vs c curves by beta (averaged over n, ger)
ax = axes[1, 1]
for beta in [2.0, 2.5, 4.0]:
    sub = c_config[c_config['beta'] == beta]
    c_uniq = sorted(sub['c'].unique())
    j_avg = [sub[sub['c'] == c]['jparam'].mean() for c in c_uniq]
    ax.plot(c_uniq, j_avg, '-o', markersize=3, label=f'beta={beta}')
# Mark optimal c for each beta
c_l2 = c_level[c_level['level'] == 'L2']
for _, row in c_l2.iterrows():
    beta_val = float(row['group'].split('=')[1])
    ax.axvline(x=row['optimal_c'], color=f'C{["2.0","2.5","4.0"].index(str(beta_val))}',
               linestyle='--', alpha=0.3)
ax.set_xlabel('c = delta / s_v')
ax.set_ylabel('J_param')
ax.set_title('J_param vs normalized c')
ax.legend(fontsize=8)

plt.suptitle('Raw delta vs c-space comparison', fontsize=13, y=1.01)
plt.tight_layout()
fig.savefig(os.path.join(IMG_DIR, "E03_cspace_comparison.png"), bbox_inches='tight')
plt.close()
print("Figure 1 saved: E03_cspace_comparison.png")

# ============================================================
# Figure 2: c* heatmap (like E03_delta_heatmap_jparam but in c)
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))

betas = [2.0, 2.5, 4.0]
ns = [7, 10, 20]
c_l3 = c_level[c_level['level'] == 'L3'].copy()
heatmap_data = np.zeros((len(betas), len(ns)))
annot_data = [['' for _ in ns] for _ in betas]
for i, beta in enumerate(betas):
    for j, n in enumerate(ns):
        row = c_l3[c_l3['group'] == f'beta={beta}_n={n}']
        if len(row) > 0:
            c_val = row['optimal_c'].values[0]
            j_val = row['jparam'].values[0]
            heatmap_data[i, j] = c_val
            annot_data[i][j] = f'c*={c_val:.2f}\nJ={j_val:.3f}'

im = ax.imshow(heatmap_data, cmap='RdYlBu_r', aspect='auto', vmin=0.10, vmax=0.26)
ax.set_xticks(range(len(ns)))
ax.set_xticklabels([f'n={n}' for n in ns])
ax.set_yticks(range(len(betas)))
ax.set_yticklabels([f'beta={b}' for b in betas])
for i in range(len(betas)):
    for j in range(len(ns)):
        ax.text(j, i, annot_data[i][j], ha='center', va='center', fontsize=8)
plt.colorbar(im, ax=ax, label='c*')
ax.set_title('Optimal c* (L3: by beta, n)')

plt.tight_layout()
fig.savefig(os.path.join(IMG_DIR, "E03_cspace_heatmap.png"), bbox_inches='tight')
plt.close()
print("Figure 2 saved: E03_cspace_heatmap.png")

# ============================================================
# Figure 3: Deployment ladder comparison raw vs c-space
# ============================================================
fig, ax = plt.subplots(figsize=(8, 5))

schemes = [
    ('Raw delta=0.1', 0.5820, '#1f77b4'),
    ('Raw L4 (per-config)', 0.5468, '#1f77b4'),
    ('c=0.18 global (L0)', 0.5598, '#2ca02c'),
    ('c-space L1 (by n)', 0.5593, '#2ca02c'),
    ('c-space L2 (by beta)', 0.5576, '#2ca02c'),
    ('c-space L3 (by b,n)', 0.5567, '#2ca02c'),
    ('c-space L4 (per-config)', 0.5473, '#ff7f0e'),
]
names = [s[0] for s in schemes]
vals = [s[1] for s in schemes]
colors = [s[2] for s in schemes]

bars = ax.barh(range(len(schemes)), vals, color=colors, edgecolor='white', height=0.6)
ax.set_yticks(range(len(schemes)))
ax.set_yticklabels(names)
ax.set_xlabel('J_param')
ax.set_title('Deployment Ladder: Raw vs c-space')
ax.invert_yaxis()
for i, (bar, v) in enumerate(zip(bars, vals)):
    ax.text(v + 0.003, i, f'{v:.4f}', va='center', fontsize=8)

plt.tight_layout()
fig.savefig(os.path.join(IMG_DIR, "E03_cspace_ladder.png"), bbox_inches='tight')
plt.close()
print("Figure 3 saved: E03_cspace_ladder.png")

print("\nAll c-space figures generated.")
