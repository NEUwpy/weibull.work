"""
E03 Page 2 (g): 各层级单样本误差分布
每层级选3个代表性配置，画 j_i 分布直方图
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(r"D:\weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
DATA_DIR = BASE / "实验数据"
IMG_DIR = BASE / "图像"
import json
with open(DATA_DIR / 'E03_level_results_v2.json', 'r', encoding='utf-8') as f:
    results = json.load(f)

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none", "pdf.fonttype": 42,
    "font.size": 8, "axes.spines.right": False, "axes.spines.top": False,
    "axes.linewidth": 0.8, "legend.frameon": False,
})

BETAS = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GAMMA_RATIOS = [0.1, 0.5, 1.0]
ETA = 1.0
DELTAS = np.arange(0, 0.51, 0.02)

# Representative configs: hard, medium, easy
REPRESENTATIVE = [
    (1.5, 7, 0.1),    # hardest
    (2.5, 10, 0.5),   # medium
    (5.0, 20, 1.0),   # easiest
]

def load_config(beta, n, gr):
    fpath = DATA_DIR / f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv"
    return pd.read_csv(fpath)

def j_i_for_delta(df, beta, n, gr, delta_val):
    gamma_true = gr * ETA
    sub = df[df['delta'] == delta_val].copy()
    sub['loss_i'] = ((sub['beta_hat']-beta)/beta)**2 + ((sub['eta_hat']-ETA)/ETA)**2 + ((sub['gamma_hat']-gamma_true)/ETA)**2
    sub['j_i'] = np.sqrt(sub['loss_i'])
    return sub['j_i'].values

# Level optimal deltas
l0_ds = results['l0']['delta_star']  # global
l1_ds = results['l1']['delta_star_by_n']  # dict n->delta
l2_ds = results['l2']['delta_star_by_beta']  # dict str(beta)->delta
l3_ds = results['l3']['delta_star_by_bn']  # dict str((b,n))->delta
l4_ds = results['l4']['delta_star_by_config']  # dict str((b,n,g))->delta

def save_pub(fig, name):
    for ext, dpi in [('.png', 300), ('.pdf', None), ('.svg', None)]:
        fig.savefig(IMG_DIR / f"{name}{ext}", bbox_inches='tight', dpi=dpi)
    plt.close(fig)

# Per-level plot: 3 configs side by side
for level_name in ['L0', 'L1', 'L2', 'L3', 'L4']:
    print(f"(g) {level_name} error distributions...")
    fig, axes = plt.subplots(1, 3, figsize=(9, 2.8), sharey=False)
    
    for idx, (beta, n, gr) in enumerate(REPRESENTATIVE):
        ax = axes[idx]
        df = load_config(beta, n, gr)
        
        # Determine delta for this config under this level
        if level_name == 'L0':
            ds = l0_ds
        elif level_name == 'L1':
            ds = l1_ds[str(n)]
        elif level_name == 'L2':
            ds = l2_ds[str(float(beta))]
        elif level_name == 'L3':
            ds = l3_ds[str((beta, n))]
        elif level_name == 'L4':
            ds = l4_ds[str((beta, n, gr))]
        
        j_vals = j_i_for_delta(df, beta, n, gr, ds)
        
        ax.hist(j_vals, bins=25, color='#95B8D1', edgecolor='white', linewidth=0.3, alpha=0.85)
        mean_j = np.mean(j_vals)
        ax.axvline(mean_j, color='#333333', linestyle='--', linewidth=0.8)
        ax.set_title(f'β={beta}, n={n}, γ/η={gr}\nδ*={ds:.2f}', fontsize=7)
        ax.set_xlabel('j_i')
        if idx == 0:
            ax.set_ylabel('Count')
        ax.text(0.95, 0.95, f'mean={mean_j:.3f}', transform=ax.transAxes,
                ha='right', va='top', fontsize=6, color='#333333')
    
    fig.suptitle(f'{level_name}: Single-sample error distribution (j_i) at optimal δ', fontsize=9, y=1.03)
    save_pub(fig, f'E03_{level_name}_error_dist')

print("Page 2 plots (g) done.")
