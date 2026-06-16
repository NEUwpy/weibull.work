"""
E04 Plots: main results + generalization + ablation
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np, pandas as pd, json
from pathlib import Path

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
IMG_DIR = BASE / "图像"

mpl.rcParams.update({
    "font.family": "sans-serif", "font.sans-serif": ["Arial","DejaVu Sans"],
    "svg.fonttype": "none", "pdf.fonttype": 42, "font.size": 8,
    "axes.spines.right": False, "axes.spines.top": False,
    "axes.linewidth": 0.8, "legend.frameon": False,
})

def save(fig, name):
    for ext, dpi in [('.png',300),('.pdf',None),('.svg',None)]:
        fig.savefig(IMG_DIR / f"{name}{ext}", bbox_inches='tight', dpi=dpi)
    plt.close(fig)

# ════════════════════════════════════
# Fig 1: Main results
# ════════════════════════════════════
with open(DATA_DIR / 'E04_main_results.json') as f:
    mr = json.load(f)
oracles = {'L4_Oracle': 0.5701, 'L5_Oracle': 0.4941, 'Default': mr['Default']['J_param']}
all_r = {**oracles, **{k: v['J_param'] for k, v in mr.items()}}
order = ['L5_Oracle','Risk_curve','L5_hard','L4_Oracle','L4_hard','Default']
colors = ['#2ca02c','#1f77b4','#1f77b4','#ff7f0e','#ff7f0e','#888888']
alphas = [0.6, 1.0, 0.7, 0.6, 0.7, 0.8]

fig, ax = plt.subplots(figsize=(6.5, 3.2))
vals = [all_r[k] for k in order]
bars = ax.barh(range(len(order)), [v - all_r['Default'] for v in vals],
               color=colors, height=0.6)
for bar, a in zip(bars, alphas):
    bar.set_alpha(a)
ax.axvline(0, color='#333', linewidth=0.8)
ax.set_yticks(range(len(order)))
ax.set_yticklabels(order)
ax.set_xlabel(f'J_param - Default ({all_r["Default"]:.4f})')
for bar, v in zip(bars, vals):
    pct = (v - all_r['Default']) / all_r['Default'] * 100
    ax.text(bar.get_width() + (0.002 if bar.get_width() >= 0 else -0.025),
            bar.get_y() + 0.3, f'{v:.4f} ({pct:+.1f}%)', va='center', fontsize=7)
ax.set_title('E04: Main Results (7:3 split)')
save(fig, 'E04_main_results')

# ════════════════════════════════════
# Fig 2: Per-config heatmap
# ════════════════════════════════════
config_df = pd.read_csv(DATA_DIR / 'E04_main_by_config.csv', index_col=0)
betas = [1.5,2.0,2.5,4.0,5.0]; ns = [7,10,20]; gers = [0.1,0.5,1.0]
for method in ['L4_hard','L5_hard','Risk_curve']:
    fig, axes = plt.subplots(1, 3, figsize=(9, 2.8), sharey=True)
    for gi, gr in enumerate(gers):
        mat = np.full((3,5), np.nan)
        for ri, n in enumerate(ns):
            for ci, b in enumerate(betas):
                k = f'{b}_{n}_{gr}'
                if k in config_df.index:
                    mat[ri,ci] = config_df.loc[k, method]
        im = axes[gi].imshow(mat, aspect='auto', cmap='RdYlBu_r', vmin=0, vmax=1)
        axes[gi].set_xticks(range(5)); axes[gi].set_xticklabels(betas)
        axes[gi].set_yticks(range(3)); axes[gi].set_yticklabels(ns)
        axes[gi].set_xlabel('β'); axes[gi].set_title(f'γ/η={gr}')
        for ri in range(3):
            for ci in range(5):
                if np.isfinite(mat[ri,ci]):
                    axes[gi].text(ci, ri, f'{mat[ri,ci]:.3f}', ha='center', va='center', fontsize=6,
                                  color='white' if mat[ri,ci] > 0.5 else 'black')
    axes[0].set_ylabel('n')
    cbar = fig.colorbar(im, ax=axes, shrink=0.85, pad=0.02); cbar.set_label('J_param')
    fig.suptitle(f'{method} per-config J_param', fontsize=9, y=1.02)
    save(fig, f'E04_config_{method}')

# ════════════════════════════════════
# Fig 3: Generalization
# ════════════════════════════════════
with open(DATA_DIR / 'E04_generalization.json') as f:
    gen = json.load(f)
with open(DATA_DIR / 'E04_main_results.json') as f:
    main = json.load(f)
id_j = main['Risk_curve']['J_param']

fig, ax = plt.subplots(figsize=(5.5, 2.8))
x = np.arange(3); w = 0.25
for i, (k, label) in enumerate([('cross_beta','Cross β'),('cross_n','Cross n'),('cross_ger','Cross γ/η')]):
    d = gen[k]
    ax.bar(x[i]-w, d['Default']-d['Default'], w/0.7, color='#888888', alpha=0.8, label='Default' if i==0 else '')
    ax.bar(x[i], d['Risk_curve']-d['Default'], w/0.7, color='#1f77b4', label='Risk curve' if i==0 else '')
    ax.text(x[i], d['Risk_curve']-d['Default']+0.003, f'{d["Risk_curve"]:.4f}', ha='center', fontsize=7)
ax.axhline(id_j - d['Default'], color='#1f77b4', linestyle='--', linewidth=0.7, label=f'In-dist ({id_j:.4f})')
ax.axhline(0, color='#333', linewidth=0.8)
ax.set_xticks(x); ax.set_xticklabels(['Cross β','Cross n','Cross γ/η'])
ax.set_ylabel('J_param - Default')
ax.set_title('Generalization: Risk Curve')
ax.legend(fontsize=6)
save(fig, 'E04_generalization')

# ════════════════════════════════════
# Fig 4: Ablation
# ════════════════════════════════════
with open(DATA_DIR / 'E04_ablation.json') as f:
    abl = json.load(f)
items = sorted(abl.items(), key=lambda x: x[1])
names = [x[0].replace('_',' ') for x in items]; vals = [x[1] for x in items]
fig, ax = plt.subplots(figsize=(5.5, 2.8))
colors2 = ['#1f77b4'] + ['#95B8D1']*4 + ['#E8A87C']*3
ax.barh(range(len(items)), [v - vals[0] for v in vals], color=colors2, height=0.6)
ax.axvline(0, color='#333', linewidth=0.8)
ax.set_yticks(range(len(items))); ax.set_yticklabels(names)
ax.set_xlabel(f'J_param - baseline ({vals[0]:.4f})')
for i, v in enumerate(vals):
    ax.text(v - vals[0] + 0.001, i, f'{v:.4f}', va='center', fontsize=7)
ax.set_title('Ablation: J_param by Feature/Architecture')
save(fig, 'E04_ablation')

print("All plots done.")
