"""
E03 Page 4 plots: 方向1自迭代轨迹图 + 改善热力图, 方向2方法对比图
Nature-figure 规范
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd
from pathlib import Path
from scipy.interpolate import interp1d

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
IMG_DIR = BASE / "图像"

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none", "pdf.fonttype": 42,
    "font.size": 8, "axes.spines.right": False, "axes.spines.top": False,
    "axes.linewidth": 0.8, "legend.frameon": False,
})

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GERS = [0.1, 0.5, 1.0]
ETA = 1.0
DELTA_GRID = [round(d, 2) for d in np.arange(0, 0.51, 0.02)]

C_BETA = {1.5: '#E8A87C', 2.0: '#D4A574', 2.5: '#95B8D1', 4.0: '#809BCE', 5.0: '#6A7BB5'}
C_GER = {0.1: '#1f77b4', 0.5: '#ff7f0e', 1.0: '#2ca02c'}

def save_pub(fig, name):
    for ext, dpi in [('.png', 300), ('.pdf', None), ('.svg', None)]:
        fig.savefig(IMG_DIR / f"{name}{ext}", bbox_inches='tight', dpi=dpi)
    plt.close(fig)

# Load L3 lookup, J_param curves, per-sample iteration data
l3_mat = pd.read_csv(DATA_DIR / 'E03_L3_heatmap_v2.csv', index_col=0)
l3_lookup = {}
for n_str in l3_mat.index:
    for b_str in l3_mat.columns:
        l3_lookup[(float(b_str), int(n_str))] = l3_mat.loc[n_str, b_str]

def delta_from_beta(bh, n):
    bs, ds = zip(*sorted([(bb, d) for (bb, nn), d in l3_lookup.items() if nn == n]))
    return float(np.interp(np.clip(bh, bs[0], bs[-1]), bs, ds))

it_df = pd.read_csv(DATA_DIR / 'E03-4a_self_iteration_v2.csv')

# ═══════════════════════════════════════════════
# Figure 1: Iteration trajectories (n=10, 5β panels × 3 γ/η lines)
# ═══════════════════════════════════════════════
print("Figure 1: Trajectories...")
n_show = 10
fig, axes = plt.subplots(1, 5, figsize=(18, 3.5), sharey=True)

# Pre-compute J_param curves per config
curves = {}
for beta in BETAS:
    for ger in GERS:
        key = (beta, n_show, ger)
        fpath = DATA_DIR / f"E03-3_delta_sweep_beta{beta}_n{n_show}_gamma{ger}.csv"
        df = pd.read_csv(fpath)
        gamma_t = ger * ETA
        j_by_d = {}
        for d in DELTA_GRID:
            rows = df[(df['delta'] == d) & (df['status'] == True)]
            if len(rows) > 0:
                loss = ((rows['beta_hat']-beta)/beta)**2 + ((rows['eta_hat']-ETA)/ETA)**2 + ((rows['gamma_hat']-gamma_t)/ETA)**2
                j_by_d[d] = float(np.sqrt(loss.mean()))
        curves[key] = j_by_d

# Simulate config-level trajectory
for bi, beta in enumerate(BETAS):
    ax = axes[bi]
    l2_opt = l3_lookup.get((beta, n_show), 0.1)
    
    for ger in GERS:
        jcurve = curves[(beta, n_show, ger)]
        ds_sorted = sorted(jcurve.keys())
        js_curve = [jcurve[d] for d in ds_sorted]
        color = C_GER[ger]
        # Faint J_param curve
        ax.plot(ds_sorted, js_curve, '-', color=color, alpha=0.2, linewidth=0.8)
        
        # Simulate iteration: start at δ=0.1, look up β̂, find δ*, repeat
        d_current = 0.10
        traj_d, traj_j = [], []
        for it in range(20):
            dk = min(DELTA_GRID, key=lambda x: abs(x - d_current))
            if dk not in jcurve: break
            traj_d.append(dk)
            traj_j.append(jcurve[dk])
            # Get β̂ at current δ
            gamma_t = ger * ETA
            df = pd.read_csv(DATA_DIR / f"E03-3_delta_sweep_beta{beta}_n{n_show}_gamma{ger}.csv")
            rows = df[(df['delta'] == dk) & (df['status'] == True)]
            if len(rows) == 0: break
            bh_mean = rows['beta_hat'].mean()
            d_next = delta_from_beta(bh_mean, n_show)
            d_current = d_current + 0.6 * (d_next - d_current)
            d_current = max(0.0, min(0.5, d_current))
            if abs(d_next - d_current) < 0.001: break
        
        ax.plot(traj_d, traj_j, 'o-', color=color, linewidth=1.5, markersize=4, label=f'g={ger}')
        ax.plot(traj_d[0], traj_j[0], 's', color=color, markersize=6)
        ax.plot(traj_d[-1], traj_j[-1], 'D', color=color, markersize=6)
    
    ax.axvline(l2_opt, color='#cc3333', linestyle='--', linewidth=0.8, alpha=0.6, label='L3 opt')
    ax.axvline(0.1, color='#888888', linestyle=':', linewidth=0.6, alpha=0.5, label='default')
    ax.set_title(f'β = {beta}', fontsize=9)
    ax.set_xlabel('δ')
    if bi == 0:
        ax.set_ylabel('J_param')
        ax.legend(fontsize=6, loc='upper left')

fig.suptitle('Direction 1: Self-Iteration Trajectories (n=10)', fontsize=10, y=1.02)
save_pub(fig, 'E03-4a_trajectories')

# ═══════════════════════════════════════════════
# Figure 2: Improvement heatmap (by β × n × γ/η)
# ═══════════════════════════════════════════════
print("Figure 2: Improvement heatmap...")
summary = it_df.groupby(['beta', 'n', 'gamma_ratio']).agg(
    loss_default=('loss_default', 'mean'),
    loss_iter=('loss_iterated', 'mean'),
).reset_index()
summary['improvement'] = (np.sqrt(summary['loss_default']) - np.sqrt(summary['loss_iter'])) / np.sqrt(summary['loss_default']) * 100

fig, ax = plt.subplots(figsize=(14, 3))
heat = np.full((len(NS), len(BETAS) * len(GERS)), np.nan)
annot = [['' for _ in range(15)] for _ in range(3)]
xlabels = []

for ci, beta in enumerate(BETAS):
    for gi, ger in enumerate(GERS):
        col = ci * 3 + gi
        xlabels.append(f'β={beta}\nγ={ger}')
        for ri, n in enumerate(NS):
            row = summary[(summary['beta'] == beta) & (summary['n'] == n) & (summary['gamma_ratio'] == ger)]
            if len(row) > 0:
                v = row['improvement'].values[0]
                heat[ri, col] = v
                annot[ri][col] = f'{v:+.1f}%'

im = ax.imshow(heat, cmap='RdYlGn', aspect='auto', vmin=-30, vmax=30)
ax.set_yticks(range(3))
ax.set_yticklabels([f'n={n}' for n in NS])
ax.set_xticks(range(15))
ax.set_xticklabels(xlabels, fontsize=6)

for ri in range(3):
    for ci in range(15):
        if np.isfinite(heat[ri, ci]):
            c = 'white' if abs(heat[ri, ci]) > 15 else 'black'
            ax.text(ci, ri, annot[ri][ci], ha='center', va='center', fontsize=6, color=c)

cbar = fig.colorbar(im, ax=ax, shrink=0.9)
cbar.set_label('Improvement (%)')
ax.set_title('Direction 1: Self-Iteration Improvement by Config (green=improve, red=degrade)')
save_pub(fig, 'E03-4a_improvement_heatmap')

# ═══════════════════════════════════════════════
# Figure 3: Direction 2 method comparison bar chart
# ═══════════════════════════════════════════════
print("Figure 3: Direction 2 comparison...")
d2 = pd.read_csv(DATA_DIR / 'E03-4b_v3_overall.csv')
default_j = d2[d2['method'] == 'default']['J_param'].values[0]
d2 = d2.sort_values('J_param')

fig, ax = plt.subplots(figsize=(6, 3.5))
methods = d2['method'].tolist()
jvals = d2['J_param'].values
colors = []
for m in methods:
    if m == 'default': colors.append('#333333')
    elif m == 'oracle': colors.append('#95B8D1')
    elif jvals[methods.index(m)] < default_j: colors.append('#6BAED6')
    else: colors.append('#E8A87C')

bars = ax.barh(methods, jvals - default_j, color=colors, height=0.6)
ax.axvline(0, color='#333333', linewidth=0.8)
ax.set_xlabel(f'J_param − {default_j:.3f} (Default)')
ax.set_title('Direction 2: External β Estimation Methods')

# Add annotations
for bar, m, j in zip(bars, methods, jvals):
    vpct = d2[d2['method'] == m]['valid_rate'].values[0] if 'valid_rate' in d2.columns else 100
    label = f'{j:.4f}'
    if vpct < 100:
        label += f' ({vpct:.0f}% valid)'
    ax.text(bar.get_width() + (0.002 if bar.get_width() >= 0 else -0.02),
            bar.get_y() + bar.get_height()/2, label, va='center', fontsize=7)

save_pub(fig, 'E03-4b_methods_comparison')

print("Page 4 plots done.")
