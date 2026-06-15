"""
E03 可视化（修正版v3）：J_param 指标，L0按n分别计算
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
opt_jparam = pd.read_csv(os.path.join(datadir, "E03-2_level_optimal_jparam.csv"))
oracle_jparam = pd.read_csv(os.path.join(datadir, "E03-3_L5_oracle_jparam.csv"))
jparam_by_config = pd.read_csv(os.path.join(datadir, "E03-3_jparam_by_config.csv"))

eta_true = 1.0
delta_default = 0.10
l0_delta = opt_jparam[opt_jparam['level'] == 'L0']['optimal_delta'].iloc[0]  # 全局最优δ

print(f"L0 全局最优 δ* = {l0_delta}")
print(f"默认 δ = {delta_default}")

# ============================================================
# 图1：J_param 层级对比柱状图（按 n 分色，L0/L1 按 n 分别计算）
# ============================================================
levels = ['L0', 'L1', 'L2', 'L3', 'L4', 'L5', 'Default']
n_vals = [7, 10, 20]
n_colors = {7: '#4477AA', 10: '#EE6677', 20: '#228833'}

fig, ax = plt.subplots(figsize=(183/25.4, 70/25.4))
x = np.arange(len(levels))
width = 0.22

for i, n in enumerate(n_vals):
    vals = []
    
    for level in levels:
        if level == 'L0':
            # L0: 用全局最优δ*，但按n分别算J_param
            # 从 jparam_by_config 取 δ=l0_delta 附近的所有配置，按n平均
            sub = jparam_by_config[
                (jparam_by_config['n'] == n) & 
                (abs(jparam_by_config['delta'] - l0_delta) < 0.001)
            ]
            vals.append(sub['jparam'].mean() if len(sub) > 0 else 0)
            
        elif level == 'L1':
            sub = opt_jparam[(opt_jparam['level'] == 'L1') & (opt_jparam['group'] == f'n={n}')]
            vals.append(sub['jparam'].iloc[0] if len(sub) > 0 else 0)
            
        elif level == 'L2':
            # L2按β，没有n维度——从L3按n取均值
            sub = opt_jparam[opt_jparam['level'] == 'L3']
            sub = sub[sub['group'].str.contains(f'_n={n}$')]
            vals.append(sub['jparam'].mean())
            
        elif level == 'L3':
            sub = opt_jparam[opt_jparam['level'] == 'L3']
            sub = sub[sub['group'].str.contains(f'_n={n}$')]
            vals.append(sub['jparam'].mean())
            
        elif level == 'L4':
            sub = opt_jparam[opt_jparam['level'] == 'L4']
            sub = sub[sub['group'].str.contains(f'_n={n}')]
            vals.append(sub['jparam'].mean())
            
        elif level == 'L5':
            sub = oracle_jparam[oracle_jparam['n'] == n]
            vals.append(sub['jparam'].mean())
            
        elif level == 'Default':
            # 用全局默认δ=0.10，按n分别算
            sub = jparam_by_config[
                (jparam_by_config['n'] == n) & 
                (abs(jparam_by_config['delta'] - delta_default) < 0.001)
            ]
            vals.append(sub['jparam'].mean() if len(sub) > 0 else 0)
    
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
print("\n图1 已保存: E03_jparam_comparison.png/pdf")

print("全部完成。")
