"""
E09-5 混合模型可视化（Nature 风格）
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

# Nature 风格
mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica']
mpl.rcParams['font.size'] = 8
mpl.rcParams['axes.labelsize'] = 9
mpl.rcParams['xtick.labelsize'] = 7
mpl.rcParams['ytick.labelsize'] = 7
mpl.rcParams['axes.linewidth'] = 0.8
mpl.rcParams['axes.unicode_minus'] = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
IMAGE_DIR = os.path.join(SCRIPT_DIR, "..", "图像")
os.makedirs(IMAGE_DIR, exist_ok=True)

COLORS = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "gray": "#666666",
}


def plot_four_paradigms():
    """四种范式 J_param 对比"""
    df = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-5_hybrid_summary.csv'))

    fig, ax = plt.subplots(figsize=(4, 3))

    methods = ['jparam_bp', 'jparam_svm', 'jparam_hybrid', 'jparam_oracle']
    labels = ['BP-raw', 'SVM', 'Hybrid', 'Oracle']
    colors = [COLORS["blue"], COLORS["red"], COLORS["orange"], COLORS["green"]]
    markers = ['o', 's', '^', 'D']

    for method, label, color, marker in zip(methods, labels, colors, markers):
        ax.plot(df['n'], df[method], f'{marker}-', color=color, linewidth=1.5, markersize=6,
                markerfacecolor='white', markeredgewidth=1.2, markeredgecolor=color, label=label)

    # 标注 Oracle 数值
    for _, row in df.iterrows():
        ax.annotate(f"{row['jparam_oracle']:.3f}", (row['n'], row['jparam_oracle']),
                   textcoords="offset points", xytext=(0, -15), ha="center", fontsize=6, color=COLORS["green"])

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(df['n'])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False, loc='upper right')

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-5_four_paradigms.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-5_four_paradigms.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-5_four_paradigms")


def plot_oracle_gap_analysis():
    """Oracle 间隙分析"""
    df = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-5_hybrid_summary.csv'))

    # 计算 Oracle 间隙
    df['gap_bp'] = df['jparam_bp'] - df['jparam_oracle']
    df['gap_svm'] = df['jparam_svm'] - df['jparam_oracle']
    df['gap_hybrid'] = df['jparam_hybrid'] - df['jparam_oracle']

    fig, axes = plt.subplots(1, 2, figsize=(7, 3))

    # Oracle 间隙对比
    ax = axes[0]
    x = np.arange(len(df))
    width = 0.25

    ax.bar(x - width, df['gap_bp'], width, label='BP-raw', color=COLORS["blue"], alpha=0.8)
    ax.bar(x, df['gap_svm'], width, label='SVM', color=COLORS["red"], alpha=0.8)
    ax.bar(x + width, df['gap_hybrid'], width, label='Hybrid', color=COLORS["orange"], alpha=0.8)

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$ gap to Oracle")
    ax.set_xticks(x)
    ax.set_xticklabels(df['n'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("(a) Gap to Oracle", fontsize=9)

    # 相对 Oracle 的倍数
    ax = axes[1]
    ax.plot(df['n'], df['jparam_bp'] / df['jparam_oracle'], 'o-', color=COLORS["blue"],
            linewidth=1.5, markersize=5, markerfacecolor='white', markeredgewidth=1,
            markeredgecolor=COLORS["blue"], label='BP-raw')
    ax.plot(df['n'], df['jparam_svm'] / df['jparam_oracle'], 's-', color=COLORS["red"],
            linewidth=1.5, markersize=5, markerfacecolor='white', markeredgewidth=1,
            markeredgecolor=COLORS["red"], label='SVM')
    ax.plot(df['n'], df['jparam_hybrid'] / df['jparam_oracle'], '^-', color=COLORS["orange"],
            linewidth=1.5, markersize=5, markerfacecolor='white', markeredgewidth=1,
            markeredgecolor=COLORS["orange"], label='Hybrid')

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$ / Oracle")
    ax.set_xscale("log")
    ax.set_xticks(df['n'])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("(b) Ratio to Oracle", fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-5c_oracle_gap.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-5c_oracle_gap.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-5c_oracle_gap")


def main():
    print("Generating E09-5 figures...")
    plot_four_paradigms()
    plot_oracle_gap_analysis()
    print("Done!")


if __name__ == "__main__":
    main()
