"""
E03-4 可视化：方案阶梯表柱状图
"""
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import os

# Nature样式
import matplotlib
try:
    matplotlib.font_manager.findfont('SimHei', fallback_to_default=False)
    CJK_FONT = 'SimHei'
except:
    try:
        matplotlib.font_manager.findfont('Microsoft YaHei', fallback_to_default=False)
        CJK_FONT = 'Microsoft YaHei'
    except:
        CJK_FONT = 'sans-serif'

plt.rcParams.update({
    'font.family': 'sans-serif',
    'font.sans-serif': [CJK_FONT, 'Arial', 'DejaVu Sans'],
    'axes.unicode_minus': False,
    'figure.dpi': 300,
    'savefig.dpi': 300,
    'font.size': 10,
    'axes.labelsize': 11,
    'axes.titlesize': 12,
    'xtick.labelsize': 9,
    'ytick.labelsize': 9,
    'legend.fontsize': 9
})

BASE_DIR = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE_DIR, "实验数据")
IMG_DIR = os.path.join(BASE_DIR, "图像")
os.makedirs(IMG_DIR, exist_ok=True)

# 加载阶梯表
ladder_df = pd.read_csv(os.path.join(DATA_DIR, "E03-4c_ladder_table.csv"))

# 排序
ladder_df = ladder_df.sort_values('jparam')

name_map = {
    'L5 Oracle (per-sample)': 'L5 Oracle',
    'Self-iterate': 'Self-iter',
    'MLE external beta': 'MLE+table',
    'Default(delta=0.1)': 'Default',
    'L4 by (beta,n,gamma/eta)': 'L4',
    'L3 by (beta,n)': 'L3',
    'LSE external beta': 'LSE+table',
    'L1 by n': 'L1',
    'L0 global': 'L0'
}

methods = [name_map.get(m, m) for m in ladder_df['method']]
jparams = ladder_df['jparam'].values
vs_oracle = ladder_df['vs_oracle'].astype(float).values

# 颜色方案
colors = []
for m in ladder_df['method']:
    if 'Oracle' in m:
        colors.append('#2ca02c')  # 绿色
    elif 'Self' in m:
        colors.append('#ff7f0e')  # 橙色
    elif 'MLE' in m:
        colors.append('#d62728')  # 红色
    elif 'LSE' in m:
        colors.append('#9467bd')  # 紫色
    elif 'Default' in m:
        colors.append('#1f77b4')  # 蓝色
    else:
        colors.append('#8c564b')  # 棕色

# 创建图表
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 5))

# 左图：J_param柱状图
bars = ax1.barh(range(len(methods)), jparams, color=colors, edgecolor='white', height=0.6)
ax1.set_yticks(range(len(methods)))
ax1.set_yticklabels(methods)
ax1.set_xlabel('J_param')
ax1.set_title('J_param Comparison')
ax1.invert_yaxis()

# 添加数值标签
for i, (bar, val) in enumerate(zip(bars, jparams)):
    ax1.text(bar.get_width() + 0.01, bar.get_y() + bar.get_height()/2,
             f'{val:.3f}', va='center', fontsize=8)

# 添加Oracle下界线
oracle_jparam = jparams[0]
ax1.axvline(x=oracle_jparam, color='#2ca02c', linestyle='--', alpha=0.5, label='Oracle')

# 右图：相对Oracle比例
bars2 = ax2.barh(range(len(methods)), vs_oracle, color=colors, edgecolor='white', height=0.6)
ax2.set_yticks(range(len(methods)))
ax2.set_yticklabels(methods)
ax2.set_xlabel('Ratio to Oracle')
ax2.set_title('Relative to Oracle (1.0 = best)')
ax2.invert_yaxis()
ax2.axvline(x=1.0, color='#2ca02c', linestyle='--', alpha=0.5)

# 添加数值标签
for i, (bar, val) in enumerate(zip(bars2, vs_oracle)):
    ax2.text(bar.get_width() + 0.02, bar.get_y() + bar.get_height()/2,
             f'{val:.3f}', va='center', fontsize=8)

plt.tight_layout()

# 保存
out_path = os.path.join(IMG_DIR, "E03-4_ladder_table.png")
plt.savefig(out_path, bbox_inches='tight')
plt.close()
print(f"图已保存: {out_path}")

# 画第二张图：按配置分组的对比
print("\n画按配置分组的对比图...")

# 加载详细数据
ext_df = pd.read_csv(os.path.join(DATA_DIR, "E03-4b_summary.csv"))
iter_df = pd.read_csv(os.path.join(DATA_DIR, "E03-4a_self_iteration.csv"))

# 按beta分组
fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)

for idx, beta in enumerate([1.5, 2.0, 2.5, 4.0, 5.0]):
    ax = axes[idx]

    # 筛选该beta的数据
    ext_beta = ext_df[ext_df['beta'] == beta]
    iter_beta = iter_df[iter_df['beta'] == beta]

    # 按n分组
    ns = [7, 10, 20]
    x = np.arange(len(ns))
    width = 0.2

    # Default
    default_vals = [ext_beta[(ext_beta['n']==n) & (ext_beta['method']=='Default(delta=0.1)')]['jparam'].mean() for n in ns]
    ax.bar(x - width*1.5, default_vals, width, label='Default', color='#1f77b4')

    # MLE
    mle_vals = [ext_beta[(ext_beta['n']==n) & (ext_beta['method']=='MLE')]['jparam'].mean() for n in ns]
    ax.bar(x - width*0.5, mle_vals, width, label='MLE+table', color='#d62728')

    # LSE
    lse_vals = [ext_beta[(ext_beta['n']==n) & (ext_beta['method']=='LSE')]['jparam'].mean() for n in ns]
    ax.bar(x + width*0.5, lse_vals, width, label='LSE+table', color='#9467bd')

    # Self-iterate
    iter_vals = [iter_beta[iter_beta['n']==n]['jparam_iterate'].mean() for n in ns]
    ax.bar(x + width*1.5, iter_vals, width, label='Self-iter', color='#ff7f0e')

    ax.set_xticks(x)
    ax.set_xticklabels([f'n={n}' for n in ns])
    ax.set_title(f'beta={beta}')
    ax.set_ylabel('J_param' if idx == 0 else '')

    if idx == 2:
        ax.legend(loc='upper right', fontsize=8)

plt.suptitle('J_param by Configuration', fontsize=12)
plt.tight_layout()

out_path2 = os.path.join(IMG_DIR, "E03-4_by_config.png")
plt.savefig(out_path2, bbox_inches='tight')
plt.close()
print(f"图已保存: {out_path2}")