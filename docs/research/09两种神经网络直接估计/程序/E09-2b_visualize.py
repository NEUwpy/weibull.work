"""
E09-2b 可视化：BP-feature 结果（Nature 风格）
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


def load_summary():
    return pd.read_csv(os.path.join(OUTPUT_DIR, "E09-2b_summary.csv"))


def plot_jparam_curve(df):
    """J_param 曲线"""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    j_param = np.sqrt(df["rmse_beta"]**2 + df["rmse_eta"]**2 + df["rmse_gamma"]**2)

    ax.plot(df["n"], j_param, "o-", color=COLORS["blue"], linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=COLORS["blue"])

    for _, row in df.iterrows():
        jp = np.sqrt(row["rmse_beta"]**2 + row["rmse_eta"]**2 + row["rmse_gamma"]**2)
        ax.annotate(f"{jp:.2f}", (row["n"], jp), textcoords="offset points",
                   xytext=(0, 10), ha="center", fontsize=7)

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$")
    ax.set_xscale("log")
    ax.set_xticks(df["n"])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2b_jparam_curve.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2b_jparam_curve.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2b_jparam_curve")


def plot_param_rmse(df):
    """各参数 RMSE"""
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5))

    params = ["beta", "eta", "gamma"]
    colors = [COLORS["blue"], COLORS["orange"], COLORS["purple"]]
    labels = ["$\\beta$", "$\\eta$", "$\\gamma$"]

    for ax, param, color, label in zip(axes, params, colors, labels):
        ax.plot(df["n"], df[f"rmse_{param}"], "o-", color=color, linewidth=1.5, markersize=6,
                markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=color)

        for _, row in df.iterrows():
            ax.annotate(f"{row[f'rmse_{param}']:.2f}",
                       (row["n"], row[f"rmse_{param}"]),
                       textcoords="offset points", xytext=(0, 10),
                       ha="center", fontsize=6)

        ax.set_xlabel("Sample size $n$")
        ax.set_ylabel(f"RMSE({label})")
        ax.set_xscale("log")
        ax.set_xticks(df["n"])
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2b_param_rmse.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2b_param_rmse.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2b_param_rmse")


def plot_comparison_with_2a():
    """对比 E09-2a 和 E09-2b"""
    df_a = pd.read_csv(os.path.join(OUTPUT_DIR, "E09-2a_summary.csv"))
    df_b = pd.read_csv(os.path.join(OUTPUT_DIR, "E09-2b_summary.csv"))

    # 计算 J_param
    df_a["j_param"] = np.sqrt(df_a["rmse_beta"]**2 + df_a["rmse_eta"]**2 + df_a["rmse_gamma"]**2)
    df_b["j_param"] = np.sqrt(df_b["rmse_beta"]**2 + df_b["rmse_eta"]**2 + df_b["rmse_gamma"]**2)

    fig, axes = plt.subplots(1, 2, figsize=(7, 3))

    # J_param 对比
    ax = axes[0]
    ax.plot(df_a["n"], df_a["j_param"], "o-", color=COLORS["blue"], linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=COLORS["blue"], label="BP-raw")
    ax.plot(df_b["n"], df_b["j_param"], "s--", color=COLORS["red"], linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=COLORS["red"], label="BP-feature")
    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$")
    ax.set_xscale("log")
    ax.set_xticks(df_a["n"])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("(a) J_param comparison", fontsize=9, pad=5)

    # x0.95 对比
    ax = axes[1]
    ax.plot(df_a["n"], df_a["rmse_x095"] * 100, "o-", color=COLORS["blue"], linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=COLORS["blue"], label="BP-raw")
    ax.plot(df_b["n"], df_b["rmse_x095"] * 100, "s--", color=COLORS["red"], linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=COLORS["red"], label="BP-feature")
    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$x_{0.95}$ RMSE (%)")
    ax.set_xscale("log")
    ax.set_xticks(df_a["n"])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("(b) $x_{0.95}$ error comparison", fontsize=9, pad=5)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2c_comparison.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2c_comparison.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2c_comparison")


def main():
    df = load_summary()

    print("Generating E09-2b figures...")
    plot_jparam_curve(df)
    plot_param_rmse(df)

    print("Generating E09-2c comparison figures...")
    plot_comparison_with_2a()

    print("Done!")


if __name__ == "__main__":
    main()
