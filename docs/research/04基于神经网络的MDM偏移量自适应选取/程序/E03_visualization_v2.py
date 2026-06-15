"""
E03 可视化（修正版）：J_param 指标，按 n 分色柱状图
"""
import sys
sys.path.insert(0, "D:/weibull/python")
import os
import re
import numpy as np
import pandas as pd

import matplotlib as mpl
mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica', 'DejaVu Sans']
mpl.rcParams['font.size'] = 7
mpl.rcParams['axes.labelsize'] = 8
mpl.rcParams['axes.titlesize'] = 8
mpl.rcParams['xtick.labelsize'] = 6
mpl.rcParams['ytick.labelsize'] = 6
mpl.rcParams['legend.fontsize'] = 6
mpl.rcParams['axes.linewidth'] = 0.5
mpl.rcParams['lines.linewidth'] = 1.5
mpl.rcParams['lines.markersize'] = 4
mpl.rcParams['savefig.dpi'] = 600
mpl.rcParams['savefig.bbox'] = 'tight'
mpl.rcParams['savefig.pad_inches'] = 0.05
mpl.rcParams['axes.spines.top'] = False
mpl.rcParams['axes.spines.right'] = False
mpl.rcParams['xtick.direction'] = 'out'
mpl.rcParams['ytick.direction'] = 'out'

import matplotlib.pyplot as plt

datadir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"
imgdir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/图像"
os.makedirs(imgdir, exist_ok=True)

# 读数据
summary = pd.read_csv(os.path.join(datadir, "E03-3_summary.csv"))
opt_jparam = pd.read_csv(os.path.join(datadir, "E03-2_level_optimal_jparam.csv"))
oracle_jparam = pd.read_csv(os.path.join(datadir, "E03-3_L5_oracle_jparam.csv"))

# ============================================================
# 图1：J_param 层级对比柱状图（按 n 分色，一个图）
# ============================================================
eta_true = 1.0
levels = ['L0', 'L1', 'L2', 'L3', 'L4', 'L5', 'Default']
n_vals = [7, 10, 20]
n_colors = {7: '#4477AA', 10: '#EE6677', 20: '#228833'}  # 蓝/红/绿

fig, ax = plt.subplots(figsize=(183/25.4, 70/25.4))

x = np.arange(len(levels))
width = 0.22

for i, n in enumerate(n_vals):
    vals = []
    
    # L0: 全局只有一个值，对所有 n 相同
    l0_sub = opt_jparam[opt_jparam['level'] == 'L0']
    l0_val = l0_sub['jparam'].iloc[0]
    
    for level in levels:
        if level == 'L0':
            vals.append(l0_val)
        elif level == 'L1':
            sub = opt_jparam[(opt_jparam['level'] == 'L1') & (opt_jparam['group'] == f'n={n}')]
            vals.append(sub['jparam'].iloc[0] if len(sub) > 0 else 0)
        elif level == 'L2':
            # L2 按β，不含n维度，需要从L3按n平均
            sub = opt_jparam[opt_jparam['level'] == 'L3']
            sub = sub[sub['group'].str.contains(f'_n={n}')]
            vals.append(sub['jparam'].mean())
        elif level == 'L3':
            sub = opt_jparam[opt_jparam['level'] == 'L3']
            sub = sub[sub['group'].str.contains(f'_n={n}')]
            vals.append(sub['jparam'].mean())
        elif level == 'L4':
            sub = opt_jparam[opt_jparam['level'] == 'L4']
            sub = sub[sub['group'].str.contains(f'_n={n}')]
            vals.append(sub['jparam'].mean())
        elif level == 'L5':
            sub = oracle_jparam[oracle_jparam['n'] == n]
            vals.append(sub['jparam'].mean())
        elif level == 'Default':
            sub = summary[(summary['n'] == n) & (summary['delta'] == 0.10)]
            if len(sub) > 0:
                # 用 J_param 公式重算
                jparams = []
                for _, row in sub.iterrows():
                    beta = row['beta']
                    ger = row['gamma_eta']
                    gamma_true = ger * eta_true
                    # summary 有 bias 和 sd，可以用 bias 近似单点 J_param
                    # 但更准确的是用原始数据。这里用 summary 的 bias 作为均值
                    # J_param ≈ √( (bias_β/β)² + (bias_η/η)² + (bias_γ/η)² + (sd_β/β)² + (sd_η/η)² + (sd_γ/η)² )
                    # 这里 bias 是 mean bias，sd 是 std，J_param 需要的是 RMSE/真值
                    # J_param = √( mean((β̂-β)/β)² + ... ) = √( (bias/β)² + (sd/β)² + ... )
                    jp = np.sqrt(
                        (row['bias_beta']/beta)**2 + (row['sd_beta']/beta)**2 +
                        (row['bias_eta']/eta_true)**2 + (row['sd_eta']/eta_true)**2 +
                        (row['bias_gamma']/eta_true)**2 + (row['sd_gamma']/eta_true)**2
                    )
                    jparams.append(jp)
                vals.append(np.mean(jparams))
            else:
                vals.append(0)
    
    bars = ax.bar(x + (i - 1) * width, vals, width, label=f'$n$={n}',
                  color=n_colors[n], edgecolor='black', linewidth=0.3)
    for bar, val in zip(bars, vals):
        if val > 0:
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.008,
                    f'{val:.3f}', ha='center', va='bottom', fontsize=4)

ax.set_xticks(x)
ax.set_xticklabels(levels, fontsize=6)
ax.set_ylabel(r'$J_{param}$')
ax.set_title(r'$J_{param} = \sqrt{mean\left(\frac{(\hat{\beta}-\beta)^2}{\beta^2} + \frac{(\hat{\eta}-\eta)^2}{\eta^2} + \frac{(\hat{\gamma}-\gamma)^2}{\eta^2}\right)}$')
ax.legend(frameon=False, ncol=3)

plt.tight_layout()
fig.savefig(os.path.join(imgdir, 'E03_jparam_comparison.png'), dpi=600)
fig.savefig(os.path.join(imgdir, 'E03_jparam_comparison.pdf'))
plt.close()
print("图1 已保存: E03_jparam_comparison.png/pdf")

# ============================================================
# 图2：最优 δ* 热力图（L4 逐配置）
# ============================================================
l4 = opt_jparam[opt_jparam['level'] == 'L4'].copy()
l4['beta_val'] = l4['group'].str.extract(r'beta=([\d.]+)').astype(float)
l4['n_val'] = l4['group'].str.extract(r'n=(\d+)').astype(int)
l4['g_val'] = l4['group'].str.extract(r'g=([\d.]+)').astype(float)

fig, axes = plt.subplots(1, 3, figsize=(183/25.4, 55/25.4))

for idx, ger in enumerate([0.1, 0.5, 1.0]):
    ax = axes[idx]
    sub = l4[l4['g_val'] == ger]
    pivot = sub.pivot_table(values='optimal_delta', index='n_val', columns='beta_val')
    
    im = ax.imshow(pivot.values, cmap='YlOrRd', aspect='auto', vmin=0, vmax=0.35)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f'{b}' for b in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f'{n}' for n in pivot.index])
    ax.set_xlabel(r'$\beta$')
    ax.set_ylabel(r'$n$')
    ax.set_title(r'$\gamma/\eta$' + f'={ger}')
    
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=5,
                       color='white' if val > 0.15 else 'black')

    plt.colorbar(im, ax=ax, shrink=0.8, label=r'$\delta^*$')

plt.tight_layout(w_pad=2)
fig.savefig(os.path.join(imgdir, 'E03_delta_heatmap_jparam.png'), dpi=600)
fig.savefig(os.path.join(imgdir, 'E03_delta_heatmap_jparam.pdf'))
plt.close()
print("图2 已保存: E03_delta_heatmap_jparam.png/pdf")

print("\n全部完成。")
