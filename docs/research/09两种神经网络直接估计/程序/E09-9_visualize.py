"""
E09-9/10/11 可视化
- 跨样本量矩阵热力图
- 混合训练对比
- 范围泛化对比
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "图像")
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# Nature 风格
matplotlib.rcParams.update({
    'font.family': 'Arial',
    'font.size': 9,
    'axes.linewidth': 0.8,
    'xtick.major.width': 0.8,
    'ytick.major.width': 0.8,
    'figure.dpi': 300,
})

COLORS = ['#E69F00', '#56B4E9', '#009E73', '#F0E442', '#0072B2', '#D55E00', '#CC79A7']


def plot_cross_n_heatmap():
    """E09-9a: 跨样本量 J_param 矩阵热力图"""
    df = pd.read_csv(os.path.join(DATA_DIR, 'E09-9a_cross_n_matrix.csv'))
    sample_sizes = sorted(df['train_n'].unique())
    matrix = np.zeros((len(sample_sizes), len(sample_sizes)))
    for _, row in df.iterrows():
        i = sample_sizes.index(row['train_n'])
        j = sample_sizes.index(row['test_n'])
        matrix[i, j] = row['jparam']

    fig, ax = plt.subplots(figsize=(5, 4.5))
    im = ax.imshow(matrix, cmap='YlOrRd', aspect='auto')

    # 标注数值
    for i in range(len(sample_sizes)):
        for j in range(len(sample_sizes)):
            val = matrix[i, j]
            color = 'white' if val > 0.5 else 'black'
            ax.text(j, i, f'{val:.3f}', ha='center', va='center',
                    fontsize=8, color=color, fontweight='bold' if i == j else 'normal')

    ax.set_xticks(range(len(sample_sizes)))
    ax.set_xticklabels(sample_sizes)
    ax.set_yticks(range(len(sample_sizes)))
    ax.set_yticklabels([f'n={n}' for n in sample_sizes])
    ax.set_xlabel('Test sample size')
    ax.set_ylabel('Training sample size')
    ax.set_title('E09-9a: Cross-n J_param Matrix', fontweight='bold')

    # 对角线标记
    for i in range(len(sample_sizes)):
        ax.add_patch(plt.Rectangle((i-0.5, i-0.5), 1, 1, fill=False,
                                    edgecolor='black', linewidth=2))

    plt.colorbar(im, ax=ax, label='J_param', shrink=0.8)
    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'E09-9a_cross_n_heatmap.pdf'), bbox_inches='tight')
    plt.savefig(os.path.join(OUTPUT_DIR, 'E09-9a_cross_n_heatmap.png'), bbox_inches='tight')
    plt.close()
    print("已保存: E09-9a_cross_n_heatmap")


def plot_mixed_n_compare():
    """E09-9b: 混合训练 vs 单样本量训练"""
    df = pd.read_csv(os.path.join(DATA_DIR, 'E09-9b_mixed_n_compare.csv'))

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

    # 左图：J_param 对比
    x = np.arange(len(df))
    width = 0.35
    bars1 = ax1.bar(x - width/2, df['jparam_single'], width, label='Single-n model',
                    color=COLORS[0], edgecolor='black', linewidth=0.5)
    bars2 = ax1.bar(x + width/2, df['jparam_mixed'], width, label='Mixed-n model',
                    color=COLORS[1], edgecolor='black', linewidth=0.5)
    ax1.set_xlabel('Test sample size (n)')
    ax1.set_ylabel('J_param')
    ax1.set_title('E09-9b: Mixed-n vs Single-n', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(df['n'].astype(int))
    ax1.legend(fontsize=8)
    ax1.set_ylim(0, 0.6)

    # 右图：比值
    ax2.bar(x, df['ratio'], color=[COLORS[2] if r < 1 else COLORS[5] for r in df['ratio']],
            edgecolor='black', linewidth=0.5)
    ax2.axhline(y=1.0, color='gray', linestyle='--', linewidth=0.8)
    ax2.set_xlabel('Test sample size (n)')
    ax2.set_ylabel('Ratio (mixed / single)')
    ax2.set_title('Mixed-n relative performance', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(df['n'].astype(int))
    ax2.set_ylim(0.95, 1.05)

    for i, row in df.iterrows():
        label = f'{row["ratio"]:.3f}'
        ax2.text(i, row['ratio'] + 0.005, label, ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'E09-9b_mixed_n_compare.pdf'), bbox_inches='tight')
    plt.savefig(os.path.join(OUTPUT_DIR, 'E09-9b_mixed_n_compare.png'), bbox_inches='tight')
    plt.close()
    print("已保存: E09-9b_mixed_n_compare")


def plot_range_generalization():
    """E09-10: 范围泛化对比"""
    df = pd.read_csv(os.path.join(DATA_DIR, 'E09-10b_multi_n_range.csv'))

    # 分离基准和扩展
    base = df[df['scenario'] == '基准']
    ext = df[df['scenario'] == '全部扩展']

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.5))

    # 左图：基准 vs 扩展
    x = np.arange(len(base))
    width = 0.35
    ax1.bar(x - width/2, base['jparam'], width, label='Base range', color=COLORS[0],
            edgecolor='black', linewidth=0.5)
    ax1.bar(x + width/2, ext['jparam'], width, label='Extended range', color=COLORS[5],
            edgecolor='black', linewidth=0.5)
    ax1.set_xlabel('Sample size (n)')
    ax1.set_ylabel('J_param')
    ax1.set_title('E09-10: Base vs Extended Range', fontweight='bold')
    ax1.set_xticks(x)
    ax1.set_xticklabels(base['n'].astype(int))
    ax1.legend(fontsize=8)

    # 右图：增长百分比
    pct = ((ext['jparam'].values - base['jparam'].values) / base['jparam'].values) * 100
    bars = ax2.bar(x, pct, color=COLORS[3], edgecolor='black', linewidth=0.5)
    ax2.set_xlabel('Sample size (n)')
    ax2.set_ylabel('J_param increase (%)')
    ax2.set_title('Range extension penalty', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(base['n'].astype(int))

    for i, v in enumerate(pct):
        ax2.text(i, v + 0.3, f'+{v:.1f}%', ha='center', va='bottom', fontsize=8)

    plt.tight_layout()
    plt.savefig(os.path.join(OUTPUT_DIR, 'E09-10_range_generalization.pdf'), bbox_inches='tight')
    plt.savefig(os.path.join(OUTPUT_DIR, 'E09-10_range_generalization.png'), bbox_inches='tight')
    plt.close()
    print("已保存: E09-10_range_generalization")


if __name__ == "__main__":
    plot_cross_n_heatmap()
    plot_mixed_n_compare()
    plot_range_generalization()
    print("\n所有图表已生成！")
