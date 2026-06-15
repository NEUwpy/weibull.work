"""
使用正确的 J_param 重新生成图表（Nature 风格）
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl

# Nature 风格设置
mpl.rcParams['font.family'] = 'sans-serif'
mpl.rcParams['font.sans-serif'] = ['Arial', 'Helvetica']
mpl.rcParams['font.size'] = 8
mpl.rcParams['axes.labelsize'] = 9
mpl.rcParams['xtick.labelsize'] = 7
mpl.rcParams['ytick.labelsize'] = 7
mpl.rcParams['axes.linewidth'] = 0.8
mpl.rcParams['xtick.major.width'] = 0.8
mpl.rcParams['ytick.major.width'] = 0.8
mpl.rcParams['axes.unicode_minus'] = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
IMAGE_DIR = os.path.join(SCRIPT_DIR, "..", "图像")
os.makedirs(IMAGE_DIR, exist_ok=True)

# Okabe-Ito 色盲友好配色
COLORS = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "gray": "#666666",
}


def load_corrected_summary(prefix):
    return pd.read_csv(os.path.join(OUTPUT_DIR, f'{prefix}_summary_corrected.csv'))


def plot_jparam_comparison():
    """对比 E09-2a 和 E09-2b 的 J_param"""
    df_a = load_corrected_summary('E09-2a')
    df_b = load_corrected_summary('E09-2b')

    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    ax.plot(df_a["n"], df_a["j_param"], "o-", color=COLORS["blue"], linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=COLORS["blue"], label="BP-raw")
    ax.plot(df_b["n"], df_b["j_param"], "s--", color=COLORS["red"], linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=COLORS["red"], label="BP-feature")

    # 标注数值
    for _, row in df_a.iterrows():
        ax.annotate(f"{row['j_param']:.3f}", (row["n"], row["j_param"]),
                   textcoords="offset points", xytext=(-15, 10), ha="center", fontsize=6, color=COLORS["blue"])
    for _, row in df_b.iterrows():
        ax.annotate(f"{row['j_param']:.3f}", (row["n"], row["j_param"]),
                   textcoords="offset points", xytext=(15, -10), ha="center", fontsize=6, color=COLORS["red"])

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$")
    ax.set_xscale("log")
    ax.set_xticks(df_a["n"])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2_jparam_comparison.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2_jparam_comparison.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2_jparam_comparison")


def plot_param_rmse_corrected(prefix):
    """各参数相对 RMSE"""
    df = load_corrected_summary(prefix)

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5))

    params = ["beta", "eta", "gamma"]
    colors = [COLORS["blue"], COLORS["orange"], COLORS["purple"]]
    labels = ["$\\beta$", "$\\eta$", "$\\gamma$"]

    for ax, param, color, label in zip(axes, params, colors, labels):
        ax.plot(df["n"], df[f"rmse_{param}_rel"], "o-", color=color, linewidth=1.5, markersize=6,
                markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=color)

        for _, row in df.iterrows():
            ax.annotate(f"{row[f'rmse_{param}_rel']:.3f}",
                       (row["n"], row[f"rmse_{param}_rel"]),
                       textcoords="offset points", xytext=(0, 10),
                       ha="center", fontsize=6)

        ax.set_xlabel("Sample size $n$")
        ax.set_ylabel(f"RMSE$_{{\\mathrm{{rel}}}}$({label})")
        ax.set_xscale("log")
        ax.set_xticks(df["n"])
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_param_rmse_rel.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_param_rmse_rel.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print(f"Saved: {prefix}_param_rmse_rel")


def plot_x095_comparison():
    """x0.95 误差对比"""
    df_a = load_corrected_summary('E09-2a')
    df_b = load_corrected_summary('E09-2b')

    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    ax.plot(df_a["n"], df_a["rmse_x095"] * 100, "o-", color=COLORS["blue"], linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=COLORS["blue"], label="BP-raw")
    ax.plot(df_b["n"], df_b["rmse_x095"] * 100, "s--", color=COLORS["red"], linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=COLORS["red"], label="BP-feature")

    # 标注数值
    for _, row in df_a.iterrows():
        ax.annotate(f"{row['rmse_x095']*100:.1f}%", (row["n"], row["rmse_x095"]*100),
                   textcoords="offset points", xytext=(-15, 10), ha="center", fontsize=6, color=COLORS["blue"])
    for _, row in df_b.iterrows():
        ax.annotate(f"{row['rmse_x095']*100:.1f}%", (row["n"], row["rmse_x095"]*100),
                   textcoords="offset points", xytext=(15, -10), ha="center", fontsize=6, color=COLORS["red"])

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$x_{0.95}$ RMSE (%)")
    ax.set_xscale("log")
    ax.set_xticks(df_a["n"])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2_x095_comparison.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2_x095_comparison.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2_x095_comparison")


def main():
    print("Generating corrected figures (Nature style)...")
    plot_jparam_comparison()
    plot_param_rmse_corrected('E09-2a')
    plot_param_rmse_corrected('E09-2b')
    plot_x095_comparison()
    print("Done!")


if __name__ == "__main__":
    main()
