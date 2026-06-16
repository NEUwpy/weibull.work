"""
E03 Page 2 可视化 (a-f): 各层级最优δ选择图
Nature-figure 规范: 定量网格 archetype
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
IMG_DIR = BASE / "图像"

# ── Nature-figure rcParams ──
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "font.size": 8,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 7,
})

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GAMMA_RATIOS = [0.1, 0.5, 1.0]
DELTAS = np.arange(0, 0.51, 0.02)

# ── Color palette: NMI pastel-like, unified method families ──
C_BETA = {1.5: '#E8A87C', 2.0: '#D4A574', 2.5: '#95B8D1', 4.0: '#809BCE', 5.0: '#6A7BB5'}
C_N = {7: '#D4A574', 10: '#95B8D1', 20: '#809BCE'}
C_GLOBAL = '#333333'
C_DEFAULT = '#888888'
C_HEATMAP = mpl.colormaps['RdYlBu_r']

def save_pub(fig, name):
    for ext, dpi in [('.png', 300), ('.pdf', None), ('.svg', None)]:
        p = IMG_DIR / f"{name}{ext}"
        fig.savefig(p, bbox_inches='tight', dpi=dpi)
    plt.close(fig)

# ═══════════════════════════════════════════════
# (a) L0 全局曲线
# ═══════════════════════════════════════════════
print("(a) L0 global curve...")
l0_df = pd.read_csv(DATA_DIR / 'E03_L0_curve_v2.csv')
fig, ax = plt.subplots(figsize=(4.5, 3.2))
ax.plot(l0_df['delta'], l0_df['J_param'], color=C_GLOBAL, linewidth=1.5)
best_idx = l0_df['J_param'].idxmin()
ax.axvline(l0_df.loc[best_idx, 'delta'], color=C_GLOBAL, linestyle='--', linewidth=0.8, alpha=0.6)
ax.annotate(f"δ*₀={l0_df.loc[best_idx,'delta']:.2f}", 
            xy=(l0_df.loc[best_idx,'delta'], l0_df.loc[best_idx,'J_param']),
            fontsize=7, ha='left', va='bottom', color=C_GLOBAL)
default_j = l0_df[l0_df['delta']==0.1]['J_param'].values[0]
ax.scatter([0.1], [default_j], color=C_DEFAULT, s=20, zorder=5)
ax.annotate("δ=0.1", xy=(0.1, default_j), fontsize=6, ha='right', va='top', color=C_DEFAULT)
ax.set_xlabel('δ')
ax.set_ylabel('J_param')
ax.set_title('L0: Global optimal offset')
save_pub(fig, 'E03_L0_global_curve')

# ═══════════════════════════════════════════════
# (b) L1 按 n 曲线
# ═══════════════════════════════════════════════
print("(b) L1 by n...")
l1_df = pd.read_csv(DATA_DIR / 'E03_L1_curves_v2.csv')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3.2), gridspec_kw={'width_ratios': [1.4, 1]})
for n in NS:
    col = str(n)
    ax1.plot(l1_df['delta'], l1_df[col], color=C_N[n], linewidth=1.3, label=f'n={n}')
    best_idx = l1_df[col].idxmin()
    best_d = l1_df.loc[best_idx, 'delta']
    ax1.axvline(best_d, color=C_N[n], linestyle='--', linewidth=0.6, alpha=0.5)
ax1.set_xlabel('δ')
ax1.set_ylabel('J_param(δ|n)')
ax1.set_title('L1: Risk curves by n')
ax1.legend(loc='upper right')

# 柱状图
l1_best = {}
for n in NS:
    col = str(n)
    l1_best[n] = l1_df.loc[l1_df[col].idxmin(), 'delta']
ax2.bar([f'n={n}' for n in NS], [l1_best[n] for n in NS], color=[C_N[n] for n in NS], width=0.5)
ax2.set_ylabel('δ*_n')
ax2.set_title('L1: Optimal δ by n')
save_pub(fig, 'E03_L1_by_n')

# ═══════════════════════════════════════════════
# (c) L2 按 β 曲线
# ═══════════════════════════════════════════════
print("(c) L2 by beta...")
l2_df = pd.read_csv(DATA_DIR / 'E03_L2_curves_v2.csv')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3.2), gridspec_kw={'width_ratios': [1.4, 1]})
l2_best = {}
for beta in BETAS:
    col = str(float(beta))  # '1.5', '2.0', etc.
    ax1.plot(l2_df['delta'], l2_df[col], color=C_BETA[beta], linewidth=1.3, label=f'β={beta}')
    best_idx = l2_df[col].idxmin()
    best_d = l2_df.loc[best_idx, 'delta']
    l2_best[beta] = best_d
    ax1.axvline(best_d, color=C_BETA[beta], linestyle='--', linewidth=0.6, alpha=0.5)
ax1.set_xlabel('δ')
ax1.set_ylabel('J_param(δ|β)')
ax1.set_title('L2: Risk curves by β')
ax1.legend(loc='upper right', ncol=2, fontsize=6)

ax2.plot(BETAS, [l2_best[b] for b in BETAS], 'o-', color='#555555', markersize=5, linewidth=1.2)
ax2.set_xlabel('β')
ax2.set_ylabel('δ*_β')
ax2.set_title('L2: Optimal δ vs β')
ax2.set_xticks(BETAS)
save_pub(fig, 'E03_L2_by_beta')

# ═══════════════════════════════════════════════
# (d) L3 热力图
# ═══════════════════════════════════════════════
print("(d) L3 heatmap...")
l3_mat = pd.read_csv(DATA_DIR / 'E03_L3_heatmap_v2.csv', index_col=0)
fig, ax = plt.subplots(figsize=(4.2, 2.5))
im = ax.imshow(l3_mat.values, aspect='auto', cmap=C_HEATMAP, vmin=0, vmax=0.5)
ax.set_xticks(range(len(BETAS)))
ax.set_xticklabels([str(b) for b in BETAS])
ax.set_yticks(range(len(NS)))
ax.set_yticklabels(NS)
ax.set_xlabel('β')
ax.set_ylabel('n')
ax.set_title('L3: δ*_{β,n}')
for i in range(len(NS)):
    for j in range(len(BETAS)):
        v = l3_mat.iloc[i, j]
        ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=7,
                color='white' if v > 0.25 else 'black')
cbar = fig.colorbar(im, ax=ax, shrink=0.85)
cbar.set_label('δ*')
save_pub(fig, 'E03_L3_heatmap')

# ═══════════════════════════════════════════════
# (e) L4 热力图 (3张分面)
# ═══════════════════════════════════════════════
print("(e) L4 heatmaps...")
fig, axes = plt.subplots(1, 3, figsize=(9, 2.8), sharey=True)
for idx, gr in enumerate(GAMMA_RATIOS):
    mat = pd.read_csv(DATA_DIR / f'E03_L4_heatmap_gamma{gr}_v2.csv', index_col=0)
    ax = axes[idx]
    im = ax.imshow(mat.values, aspect='auto', cmap=C_HEATMAP, vmin=0, vmax=0.5)
    ax.set_xticks(range(len(BETAS)))
    ax.set_xticklabels([str(b) for b in BETAS])
    ax.set_yticks(range(len(NS)))
    ax.set_yticklabels(NS)
    ax.set_xlabel('β')
    ax.set_title(f'γ/η = {gr}')
    for i in range(len(NS)):
        for j in range(len(BETAS)):
            v = mat.iloc[i, j]
            ax.text(j, i, f'{v:.2f}', ha='center', va='center', fontsize=6.5,
                    color='white' if v > 0.25 else 'black')
axes[0].set_ylabel('n')
cbar = fig.colorbar(im, ax=axes, shrink=0.85, pad=0.02)
cbar.set_label('δ*')
fig.suptitle('L4: δ*_{β,n,γ/η}', fontsize=9, y=1.02)
save_pub(fig, 'E03_L4_heatmaps')

# ═══════════════════════════════════════════════
# (f) L5 逐样本分布
# ═══════════════════════════════════════════════
print("(f) L5 distributions...")
l5_df = pd.read_csv(DATA_DIR / 'E03_L5_per_sample_v2.csv')
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7, 3.2), gridspec_kw={'width_ratios': [1.2, 1]})

ax1.hist(l5_df['delta_star_i'], bins=30, color='#95B8D1', edgecolor='white', linewidth=0.3)
ax1.axvline(0.1, color=C_DEFAULT, linestyle='--', linewidth=1, label='δ=0.1')
ax1.set_xlabel('δ*_i')
ax1.set_ylabel('Count')
ax1.set_title(f'L5: Per-sample δ* distribution\n(n={len(l5_df):,} samples)')
ax1.legend(fontsize=6)
mean_ds = l5_df['delta_star_i'].mean()
ax1.axvline(mean_ds, color='#333333', linestyle=':', linewidth=0.8, label=f'mean={mean_ds:.3f}')

bp_data = [l5_df[l5_df['beta'] == b]['delta_star_i'].values for b in BETAS]
bp = ax2.boxplot(bp_data, positions=BETAS, widths=0.25, patch_artist=True,
                  flierprops=dict(marker='.', markersize=2, markerfacecolor='#aaaaaa'))
for patch, beta in zip(bp['boxes'], BETAS):
    patch.set_facecolor(C_BETA[beta])
    patch.set_alpha(0.7)
ax2.set_xlabel('β')
ax2.set_ylabel('δ*_i')
ax2.set_title('L5: δ*_i distribution by β')
ax2.set_xticks(BETAS)
save_pub(fig, 'E03_L5_distributions')

print("Page 2 plots (a-f) done.")
