"""
E09-4 SVM 分类可视化（Nature 风格）
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


def plot_svm_vs_bp():
    """SVM vs BP J_param 对比"""
    comparison = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-4d_comparison.csv'))

    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    ax.plot(comparison['n'], comparison['svm_jparam_proba'], 's-', color=COLORS["red"],
            linewidth=1.5, markersize=6, markerfacecolor='white', markeredgewidth=1.2,
            markeredgecolor=COLORS["red"], label='SVM (proba)')
    ax.plot(comparison['n'], comparison['bp_jparam'], 'o--', color=COLORS["blue"],
            linewidth=1.5, markersize=6, markerfacecolor='white', markeredgewidth=1.2,
            markeredgecolor=COLORS["blue"], label='BP-raw')

    # 标注数值
    for _, row in comparison.iterrows():
        ax.annotate(f"{row['svm_jparam_proba']:.3f}", (row['n'], row['svm_jparam_proba']),
                   textcoords="offset points", xytext=(10, 8), ha="center", fontsize=6, color=COLORS["red"])
        ax.annotate(f"{row['bp_jparam']:.3f}", (row['n'], row['bp_jparam']),
                   textcoords="offset points", xytext=(-15, -10), ha="center", fontsize=6, color=COLORS["blue"])

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$")
    ax.set_xscale("log")
    ax.set_xticks(comparison['n'])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-4d_svm_vs_bp.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-4d_svm_vs_bp.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-4d_svm_vs_bp")


def plot_discretization_bounds():
    """离散化误差下界"""
    bounds = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-4a_discretization_bounds.csv'))

    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    params = ['beta', 'eta', 'gamma']
    param_labels = [r'$\beta$', r'$\eta$', r'$\gamma$']
    colors = [COLORS["blue"], COLORS["orange"], COLORS["purple"]]

    x = np.arange(len(bounds))
    width = 0.25

    for i, (param, label, color) in enumerate(zip(params, param_labels, colors)):
        ax.bar(x + i * width, bounds[f'bound_{param}'], width, label=label, color=color, alpha=0.8)

    ax.set_xlabel("Number of bins $K$")
    ax.set_ylabel("Discretization bound (RMSE)")
    ax.set_xticks(x + width)
    ax.set_xticklabels(bounds['K'])
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-4a_discretization_bounds.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-4a_discretization_bounds.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-4a_discretization_bounds")


def plot_classification_accuracy():
    """SVM 分类准确率"""
    svm_df = pd.read_csv(os.path.join(OUTPUT_DIR, 'E09-4b_svm_summary.csv'))

    fig, axes = plt.subplots(1, 2, figsize=(7, 3))

    # J_param 对比
    ax = axes[0]
    ax.plot(svm_df['n'], svm_df['jparam_center'], 's-', color=COLORS["orange"],
            linewidth=1.5, markersize=5, markerfacecolor='white', markeredgewidth=1,
            markeredgecolor=COLORS["orange"], label='Center')
    ax.plot(svm_df['n'], svm_df['jparam_proba'], 'o-', color=COLORS["red"],
            linewidth=1.5, markersize=5, markerfacecolor='white', markeredgewidth=1,
            markeredgecolor=COLORS["red"], label='Proba-weighted')
    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$")
    ax.set_xscale("log")
    ax.set_xticks(svm_df['n'])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("(a) SVM reconstruction", fontsize=9)

    # 训练时间
    ax = axes[1]
    ax.bar(range(len(svm_df)), svm_df['train_time'], color=COLORS["green"], alpha=0.7)
    ax.set_xticks(range(len(svm_df)))
    ax.set_xticklabels(svm_df['n'])
    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("Training time (s)")
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title("(b) Training time", fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-4b_svm_details.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-4b_svm_details.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-4b_svm_details")


def main():
    print("Generating E09-4 figures...")
    plot_svm_vs_bp()
    plot_discretization_bounds()
    plot_classification_accuracy()
    print("Done!")


if __name__ == "__main__":
    main()
