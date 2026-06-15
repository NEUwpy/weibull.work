"""
E03 可视化：层级对比图（Nature 样式）
图1：L0~L4 + 默认δ=0.1 的 Bias 对比
图2：L0~L4 + 默认δ=0.1 的 SD 对比
图3：δ* 分布散点图（L4 逐配置最优 δ*）
"""
import sys
sys.path.insert(0, "D:/weibull/python")
import os

# Nature 样式配置
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
mpl.rcParams['xtick.major.size'] = 3
mpl.rcParams['ytick.major.size'] = 3
mpl.rcParams['xtick.major.width'] = 0.5
mpl.rcParams['ytick.major.width'] = 0.5

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# 中文支持（Nature 样式后覆盖）
plt.rcParams['axes.unicode_minus'] = False

datadir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"
imgdir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/图像"
os.makedirs(imgdir, exist_ok=True)

# 读数据
summary = pd.read_csv(os.path.join(datadir, "E03-3_summary.csv"))
optimal = pd.read_csv(os.path.join(datadir, "E03-2_level_optimal.csv"))
oracle = pd.read_csv(os.path.join(datadir, "E03-3_L5_oracle.csv"))

summary['composite'] = summary['bias_beta'].abs() + summary['bias_gamma'].abs() + summary['bias_eta'].abs()
summary['gamma_true'] = summary['gamma_eta'] * 1.0

# ============================================================
# 图1 & 图2：L0~L5 + 默认δ=0.1 在典型配置下的 Bias/SD 对比
# ============================================================
# 典型配置：β=2.5, n=10, γ/η=0.5
typical = summary[(summary['beta'] == 2.5) & (summary['n'] == 10) & (summary['gamma_eta'] == 0.5)]

# L0~L4 最优 δ
levels_data = []
for level in ['L0', 'L1', 'L2', 'L3', 'L4']:
    row = optimal[(optimal['level'] == level)]
    if level == 'L0':
        row = row.iloc[0]
    elif level == 'L1':
        row = row[row['group'] == 'n=10'].iloc[0]
    elif level == 'L2':
        row = row[row['group'] == 'beta=2.5'].iloc[0]
    elif level == 'L3':
        row = row[row['group'] == 'beta=2.5_n=10'].iloc[0]
    elif level == 'L4':
        row = row[row['group'] == 'beta=2.5_n=10_g=0.5'].iloc[0]
    
    delta_star = row['optimal_delta']
    # 从 summary 取对应行
    sub = typical[typical['delta'] == delta_star]
    if len(sub) > 0:
        r = sub.iloc[0]
        levels_data.append({
            'level': level,
            'delta': delta_star,
            'bias_beta': r['bias_beta'],
            'bias_gamma': r['bias_gamma'],
            'bias_eta': r['bias_eta'],
            'sd_beta': r['sd_beta'],
            'sd_gamma': r['sd_gamma'],
            'sd_eta': r['sd_eta'],
        })

# 默认 δ=0.1
default_row = typical[typical['delta'] == 0.10]
if len(default_row) > 0:
    r = default_row.iloc[0]
    levels_data.append({
        'level': 'default\n(delta=0.1)',
        'delta': 0.1,
        'bias_beta': r['bias_beta'],
        'bias_gamma': r['bias_gamma'],
        'bias_eta': r['bias_eta'],
        'sd_beta': r['sd_beta'],
        'sd_gamma': r['sd_gamma'],
        'sd_eta': r['sd_eta'],
    })

ldf = pd.DataFrame(levels_data)

# Okabe-Ito 配色
colors = ['#E69F00', '#56B4E9', '#009E73']

fig, axes = plt.subplots(1, 2, figsize=(183/25.4, 60/25.4))

# 图1：Bias 对比
ax = axes[0]
x = np.arange(len(ldf))
width = 0.25
ax.bar(x - width, ldf['bias_beta'], width, label=r'Bias($\hat{\beta}$)', color=colors[0], edgecolor='black', linewidth=0.3)
ax.bar(x, ldf['bias_gamma'], width, label=r'Bias($\hat{\gamma}$)', color=colors[1], edgecolor='black', linewidth=0.3)
ax.bar(x + width, ldf['bias_eta'], width, label=r'Bias($\hat{\eta}$)', color=colors[2], edgecolor='black', linewidth=0.3)
ax.axhline(0, color='black', linewidth=0.5, linestyle='-')
ax.set_xticks(x)
ax.set_xticklabels(ldf['level'], fontsize=5)
ax.set_ylabel('Bias')
ax.set_title(r'(a) Bias comparison at $\beta$=2.5, $n$=10, $\gamma/\eta$=0.5')
ax.legend(ncol=3, loc='upper left', frameon=False)

# 图2：SD 对比
ax = axes[1]
ax.bar(x - width, ldf['sd_beta'], width, label=r'SD($\hat{\beta}$)', color=colors[0], edgecolor='black', linewidth=0.3)
ax.bar(x, ldf['sd_gamma'], width, label=r'SD($\hat{\gamma}$)', color=colors[1], edgecolor='black', linewidth=0.3)
ax.bar(x + width, ldf['sd_eta'], width, label=r'SD($\hat{\eta}$)', color=colors[2], edgecolor='black', linewidth=0.3)
ax.set_xticks(x)
ax.set_xticklabels(ldf['level'], fontsize=5)
ax.set_ylabel('Standard Deviation')
ax.set_title(r'(b) SD comparison at $\beta$=2.5, $n$=10, $\gamma/\eta$=0.5')
ax.legend(ncol=3, loc='upper left', frameon=False)

plt.tight_layout(w_pad=2)
fig.savefig(os.path.join(imgdir, 'E03_level_comparison.png'), dpi=600)
fig.savefig(os.path.join(imgdir, 'E03_level_comparison.pdf'))
plt.close()
print("图1-2 已保存: E03_level_comparison.png/pdf")

# ============================================================
# 图3：L4 各配置最优 δ* 热力图
# ============================================================
l4 = optimal[optimal['level'] == 'L4'].copy()
l4['beta_val'] = l4['group'].str.extract(r'beta=([\d.]+)').astype(float)
l4['n_val'] = l4['group'].str.extract(r'n=(\d+)').astype(int)
l4['g_val'] = l4['group'].str.extract(r'g=([\d.]+)').astype(float)

fig, axes = plt.subplots(1, 3, figsize=(183/25.4, 60/25.4))

for idx, ger in enumerate([0.1, 0.5, 1.0]):
    ax = axes[idx]
    sub = l4[l4['g_val'] == ger]
    
    pivot = sub.pivot_table(values='optimal_delta', index='n_val', columns='beta_val')
    
    im = ax.imshow(pivot.values, cmap='YlOrRd', aspect='auto', vmin=0, vmax=0.15)
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f'{b}' for b in pivot.columns])
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f'{n}' for n in pivot.index])
    ax.set_xlabel(r'$\beta$')
    ax.set_ylabel(r'$n$')
    ax.set_title(r'$\gamma/\eta$' + f'={ger}')
    
    # 标注数值
    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f'{val:.2f}', ha='center', va='center', fontsize=5,
                       color='white' if val > 0.08 else 'black')

    plt.colorbar(im, ax=ax, shrink=0.8, label=r'Optimal $\delta^*$')

plt.tight_layout(w_pad=2)
fig.savefig(os.path.join(imgdir, 'E03_optimal_delta_heatmap.png'), dpi=600)
fig.savefig(os.path.join(imgdir, 'E03_optimal_delta_heatmap.pdf'))
plt.close()
print("图3 已保存: E03_optimal_delta_heatmap.png/pdf")

# ============================================================
# 图4：复合指标对比（按 n 分图，公平对比）
# ============================================================
# L5 oracle 按 (beta, n, ger) 汇总
oracle_by_config = {}
for beta in [1.5, 2.0, 2.5, 4.0, 5.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            sub = oracle[(oracle['beta'] == beta) & (oracle['n'] == n) & (oracle['gamma_eta'] == ger)]
            oracle_by_config[(beta, n, ger)] = abs(sub['bias_beta'].mean()) + abs(sub['bias_gamma'].mean()) + abs(sub['bias_eta'].mean())

# L0~L4 按配置汇总
opt_by_config = {}
for level in ['L0', 'L1', 'L2', 'L3', 'L4']:
    sub = optimal[optimal['level'] == level]
    for _, row in sub.iterrows():
        # 从 group 字段解析 beta, n, ger
        group = row['group']
        import re
        m = re.match(r'beta=([\d.]+)_n=(\d+)(?:_g=([\d.]+))?', group)
        if m:
            b = float(m.group(1))
            nn = int(m.group(2))
            g = float(m.group(3)) if m.group(3) else None
            opt_by_config[(level, b, nn, g)] = row['composite']

# 默认 δ=0.1 按配置汇总
default_by_config = {}
for beta in [1.5, 2.0, 2.5, 4.0, 5.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            sub = summary[(summary['beta'] == beta) & (summary['n'] == n) & 
                         (summary['gamma_eta'] == ger) & (summary['delta'] == 0.10)]
            if len(sub) > 0:
                r = sub.iloc[0]
                default_by_config[(beta, n, ger)] = abs(r['bias_beta']) + abs(r['bias_gamma']) + abs(r['bias_eta'])

# 每个 n 一张图
colors_bar = ['#4477AA', '#EE6677', '#228833', '#CCBB44', '#66CCEE', '#AA3377', '#BBBBBB']
labels = ['L0', 'L1', 'L2', 'L3', 'L4', 'L5\n(oracle)', r'Default']

for target_n in [7, 10, 20]:
    fig, ax = plt.subplots(figsize=(89/25.4, 60/25.4))
    
    # 收集该 n 下所有 (beta, ger) 组合的均值
    level_vals = {lv: [] for lv in ['L0', 'L1', 'L2', 'L3', 'L4']}
    oracle_vals = []
    default_vals = []
    
    for beta in [1.5, 2.0, 2.5, 4.0, 5.0]:
        for ger in [0.1, 0.5, 1.0]:
            # L0-L4
            for level in ['L0', 'L1', 'L2', 'L3', 'L4']:
                # L0/L1/L2 没有完整 (beta,n,ger) 键，用最近的
                if level == 'L0':
                    key = (level, None, None, None)
                    # L0 只有一个全局值
                    sub = optimal[optimal['level'] == 'L0']
                    level_vals[level].append(sub['composite'].iloc[0])
                elif level == 'L1':
                    key = (level, None, target_n, None)
                    sub = optimal[(optimal['level'] == 'L1') & (optimal['group'] == f'n={target_n}')]
                    if len(sub) > 0:
                        level_vals[level].append(sub['composite'].iloc[0])
                elif level == 'L2':
                    key = (level, beta, None, None)
                    sub = optimal[(optimal['level'] == 'L2') & (optimal['group'] == f'beta={beta}')]
                    if len(sub) > 0:
                        level_vals[level].append(sub['composite'].iloc[0])
                elif level == 'L3':
                    sub = optimal[(optimal['level'] == 'L3') & (optimal['group'] == f'beta={beta}_n={target_n}')]
                    if len(sub) > 0:
                        level_vals[level].append(sub['composite'].iloc[0])
                elif level == 'L4':
                    sub = optimal[(optimal['level'] == 'L4') & (optimal['group'] == f'beta={beta}_n={target_n}_g={ger}')]
                    if len(sub) > 0:
                        level_vals[level].append(sub['composite'].iloc[0])
            
            # L5 oracle
            k = (beta, target_n, ger)
            if k in oracle_by_config:
                oracle_vals.append(oracle_by_config[k])
            
            # default
            k = (beta, target_n, ger)
            if k in default_by_config:
                default_vals.append(default_by_config[k])
    
    means = [np.mean(level_vals[lv]) for lv in ['L0', 'L1', 'L2', 'L3', 'L4']]
    means.append(np.mean(oracle_vals))
    means.append(np.mean(default_vals))
    
    bars = ax.bar(range(len(labels)), means, color=colors_bar, edgecolor='black', linewidth=0.3)
    
    for bar, val in zip(bars, means):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.005, f'{val:.3f}',
                ha='center', va='bottom', fontsize=5)
    
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, fontsize=5)
    ax.set_ylabel('Mean Composite Metric')
    ax.set_title(f'$n$={target_n}  |  Composite = |Bias(' + r'$\hat{\beta}$)| + |Bias(' + r'$\hat{\gamma}$)| + |Bias(' + r'$\hat{\eta}$)|')
    
    plt.tight_layout()
    fig.savefig(os.path.join(imgdir, f'E03_composite_n{target_n}.png'), dpi=600)
    fig.savefig(os.path.join(imgdir, f'E03_composite_n{target_n}.pdf'))
    plt.close()
    print(f"图4-{target_n} 已保存: E03_composite_n{target_n}.png/pdf")

print("\n全部完成。")
