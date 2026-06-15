"""
E09-2a 可视化：使用 scientific-visualization skill 的 Nature 风格
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 添加 skill scripts 路径
SKILL_DIR = os.path.expanduser("~/.agents/skills/scientific-visualization/scripts")
sys.path.insert(0, SKILL_DIR)

# 添加项目路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python/studies/common"))

# 手动应用 Nature 风格
import matplotlib as mpl
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

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
IMAGE_DIR = os.path.join(SCRIPT_DIR, "..", "图像")
os.makedirs(IMAGE_DIR, exist_ok=True)


def load_summary():
    return pd.read_csv(os.path.join(OUTPUT_DIR, "E09-2a_summary.csv"))


def plot_jparam_curve(df):
    """J_param 曲线 - Nature 风格"""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    j_param = np.sqrt(df["rmse_beta"]**2 + df["rmse_eta"]**2 + df["rmse_gamma"]**2)

    ax.plot(df["n"], j_param, "o-", color="#0072B2", linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor="#0072B2")

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
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_jparam_curve.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_jparam_curve.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2a_jparam_curve")


def plot_param_rmse(df):
    """各参数 RMSE - Nature 风格"""
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5))

    params = ["beta", "eta", "gamma"]
    colors = ["#0072B2", "#E69F00", "#CC79A7"]
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
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_param_rmse.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_param_rmse.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2a_param_rmse")


def plot_bias_analysis(df):
    """Bias 分析 - Nature 风格"""
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.5))

    params = ["beta", "eta", "gamma"]
    colors = ["#0072B2", "#E69F00", "#CC79A7"]
    labels = ["$\\beta$", "$\\eta$", "$\\gamma$"]

    for ax, param, color, label in zip(axes, params, colors, labels):
        ax.plot(df["n"], df[f"bias_{param}"], "o-", color=color, linewidth=1.5, markersize=6,
                markerfacecolor="white", markeredgewidth=1.2, markeredgecolor=color)
        ax.axhline(y=0, color="gray", linestyle="--", linewidth=0.6, alpha=0.7)

        for _, row in df.iterrows():
            ax.annotate(f"{row[f'bias_{param}']:.2f}",
                       (row["n"], row[f"bias_{param}"]),
                       textcoords="offset points", xytext=(0, 10),
                       ha="center", fontsize=6)

        ax.set_xlabel("Sample size $n$")
        ax.set_ylabel(f"Bias({label})")
        ax.set_xscale("log")
        ax.set_xticks(df["n"])
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_param_bias.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_param_bias.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2a_param_bias")


def plot_x095_error(df):
    """x0.95 误差 - Nature 风格"""
    fig, ax = plt.subplots(figsize=(3.5, 2.8))

    ax.plot(df["n"], df["rmse_x095"] * 100, "o-", color="#D55E00", linewidth=1.5, markersize=6,
            markerfacecolor="white", markeredgewidth=1.2, markeredgecolor="#D55E00", label="RMSE")
    ax.plot(df["n"], df["mae_x095"] * 100, "s--", color="#666666", linewidth=1.2, markersize=5,
            markerfacecolor="white", markeredgewidth=1.0, markeredgecolor="#666666", label="MAE")

    for _, row in df.iterrows():
        ax.annotate(f"{row['rmse_x095']*100:.1f}%",
                   (row["n"], row["rmse_x095"]*100),
                   textcoords="offset points", xytext=(0, 10),
                   ha="center", fontsize=7)

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$x_{0.95}$ relative error (%)")
    ax.set_xscale("log")
    ax.set_xticks(df["n"])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_x095_error.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_x095_error.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2a_x095_error")


def plot_training_history():
    """训练历史 - Nature 风格"""
    fig, axes = plt.subplots(2, 3, figsize=(7.2, 5))
    axes = axes.flatten()

    ns = [5, 7, 10, 15, 20, 50]
    colors = ["#0072B2", "#D55E00"]

    for ax, n in zip(axes, ns):
        try:
            hist = pd.read_csv(os.path.join(OUTPUT_DIR, f"E09-2a_history_n{n}.csv"))
            epochs = range(1, len(hist) + 1)
            ax.plot(epochs, hist["train_loss"], color=colors[0], linewidth=1, label="Train")
            ax.plot(epochs, hist["val_loss"], color=colors[1], linewidth=1, label="Val")
            ax.set_xlabel("Epoch")
            ax.set_ylabel("Loss")
            ax.set_title(f"$n = {n}$", fontsize=9, pad=3)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)
            if n == 5:
                ax.legend(fontsize=6, frameon=False)
        except Exception as e:
            ax.text(0.5, 0.5, f"Error", ha="center", va="center", transform=ax.transAxes)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_training_history.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_training_history.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-2a_training_history")


def main():
    df = load_summary()

    print("Generating publication-quality figures (Nature style)...")
    plot_jparam_curve(df)
    plot_param_rmse(df)
    plot_bias_analysis(df)
    plot_x095_error(df)
    plot_training_history()
    print("Done!")


if __name__ == "__main__":
    main()
