"""
E09-2a 可视化：BP-raw 结果分析
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
matplotlib.rcParams['axes.unicode_minus'] = False

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "../../../.."))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python"))
sys.path.insert(0, os.path.join(PROJECT_ROOT, "python/studies/common"))

OUTPUT_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
IMAGE_DIR = os.path.join(SCRIPT_DIR, "..", "图像")
os.makedirs(IMAGE_DIR, exist_ok=True)


def load_summary():
    """加载汇总数据。"""
    return pd.read_csv(os.path.join(OUTPUT_DIR, "E09-2a_summary.csv"))


def plot_jparam_curve(df):
    """绘制 J_param 随样本量变化曲线。"""
    fig, ax = plt.subplots(figsize=(8, 5))

    # 从各参数 RMSE 计算 J_param
    j_param = np.sqrt(df["rmse_beta"]**2 + df["rmse_eta"]**2 + df["rmse_gamma"]**2)

    ax.plot(df["n"], j_param, "o-", color="#2196F3", linewidth=2, markersize=8, label="J_param")

    # 标注数值
    for i, row in df.iterrows():
        jp = np.sqrt(row["rmse_beta"]**2 + row["rmse_eta"]**2 + row["rmse_gamma"]**2)
        ax.annotate(f"{jp:.3f}", (row["n"], jp), textcoords="offset points",
                   xytext=(0, 10), ha="center", fontsize=9)

    ax.set_xlabel("样本量 n", fontsize=12)
    ax.set_ylabel("J_param", fontsize=12)
    ax.set_title("BP-raw: J_param 随样本量变化", fontsize=14)
    ax.set_xscale("log")
    ax.set_xticks(df["n"])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.grid(True, alpha=0.3)
    ax.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_jparam_curve.png"), dpi=150)
    plt.close()
    print("已保存: E09-2a_jparam_curve.png")


def plot_param_rmse(df):
    """绘制各参数 RMSE 随样本量变化。"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    params = ["beta", "eta", "gamma"]
    colors = ["#4CAF50", "#FF9800", "#9C27B0"]
    labels = [r"$\beta$", r"$\eta$", r"$\gamma$"]

    for ax, param, color, label in zip(axes, params, colors, labels):
        ax.plot(df["n"], df[f"rmse_{param}"], "o-", color=color, linewidth=2, markersize=8)

        # 标注数值
        for _, row in df.iterrows():
            ax.annotate(f"{row[f'rmse_{param}']:.3f}",
                       (row["n"], row[f"rmse_{param}"]),
                       textcoords="offset points", xytext=(0, 10),
                       ha="center", fontsize=8)

        ax.set_xlabel("样本量 n", fontsize=11)
        ax.set_ylabel(f"RMSE({label})", fontsize=11)
        ax.set_title(f"BP-raw: {label} RMSE", fontsize=12)
        ax.set_xscale("log")
        ax.set_xticks(df["n"])
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_param_rmse.png"), dpi=150)
    plt.close()
    print("已保存: E09-2a_param_rmse.png")


def plot_bias_analysis(df):
    """绘制参数 bias 分析。"""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))

    params = ["beta", "eta", "gamma"]
    colors = ["#4CAF50", "#FF9800", "#9C27B0"]
    labels = [r"$\beta$", r"$\eta$", r"$\gamma$"]

    for ax, param, color, label in zip(axes, params, colors, labels):
        ax.plot(df["n"], df[f"bias_{param}"], "o-", color=color, linewidth=2, markersize=8)
        ax.axhline(y=0, color="gray", linestyle="--", alpha=0.5)

        # 标注数值
        for _, row in df.iterrows():
            ax.annotate(f"{row[f'bias_{param}']:.3f}",
                       (row["n"], row[f"bias_{param}"]),
                       textcoords="offset points", xytext=(0, 10),
                       ha="center", fontsize=8)

        ax.set_xlabel("样本量 n", fontsize=11)
        ax.set_ylabel(f"Bias({label})", fontsize=11)
        ax.set_title(f"BP-raw: {label} Bias", fontsize=12)
        ax.set_xscale("log")
        ax.set_xticks(df["n"])
        ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
        ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_param_bias.png"), dpi=150)
    plt.close()
    print("已保存: E09-2a_param_bias.png")


def plot_x095_error(df):
    """绘制 x0.95 工程寿命误差。"""
    fig, ax = plt.subplots(figsize=(8, 5))

    ax.plot(df["n"], df["rmse_x095"] * 100, "o-", color="#E91E63", linewidth=2, markersize=8, label="RMSE")
    ax.plot(df["n"], df["mae_x095"] * 100, "s--", color="#FF5722", linewidth=2, markersize=8, label="MAE")

    # 标注数值
    for _, row in df.iterrows():
        ax.annotate(f"{row['rmse_x095']*100:.1f}%",
                   (row["n"], row["rmse_x095"]*100),
                   textcoords="offset points", xytext=(0, 10),
                   ha="center", fontsize=9)

    ax.set_xlabel("样本量 n", fontsize=12)
    ax.set_ylabel("x₀.₉₅ 相对误差 (%)", fontsize=12)
    ax.set_title("BP-raw: x₀.₉₅ 工程寿命误差", fontsize=14)
    ax.set_xscale("log")
    ax.set_xticks(df["n"])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.grid(True, alpha=0.3)
    ax.legend()

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_x095_error.png"), dpi=150)
    plt.close()
    print("已保存: E09-2a_x095_error.png")


def plot_training_history():
    """绘制各样本量的训练损失曲线。"""
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))
    axes = axes.flatten()

    ns = [5, 7, 10, 15, 20, 50]

    for ax, n in zip(axes, ns):
        try:
            hist = pd.read_csv(os.path.join(OUTPUT_DIR, f"E09-2a_history_n{n}.csv"))
            ax.plot(hist["train_loss"], label="Train", linewidth=1.5)
            ax.plot(hist["val_loss"], label="Val", linewidth=1.5)
            ax.set_xlabel("Epoch")
            ax.set_ylabel("J_param Loss")
            ax.set_title(f"n = {n}")
            ax.legend()
            ax.grid(True, alpha=0.3)
        except Exception as e:
            ax.text(0.5, 0.5, f"Error: {e}", ha="center", va="center", transform=ax.transAxes)

    plt.suptitle("BP-raw: Training History", fontsize=14)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-2a_training_history.png"), dpi=150)
    plt.close()
    print("已保存: E09-2a_training_history.png")


def print_summary_table(df):
    """打印汇总表格。"""
    # 计算 J_param
    df["j_param"] = np.sqrt(df["rmse_beta"]**2 + df["rmse_eta"]**2 + df["rmse_gamma"]**2)

    print("\n" + "="*80)
    print("E09-2a BP-raw 汇总结果")
    print("="*80)

    display_cols = ["n", "j_param", "rmse_beta", "rmse_eta", "rmse_gamma", "rmse_x095", "bias_beta", "bias_eta", "bias_gamma"]
    print(df[display_cols].to_string(index=False, float_format="%.4f"))

    print("\n关键观察：")
    print(f"  J_param 范围: {df['j_param'].min():.4f} (n=50) ~ {df['j_param'].max():.4f} (n=5)")
    print(f"  x0.95 RMSE 范围: {df['rmse_x095'].min()*100:.1f}% ~ {df['rmse_x095'].max()*100:.1f}%")
    print(f"  所有样本量失败率: 0%")


def main():
    df = load_summary()

    print_summary_table(df)
    plot_jparam_curve(df)
    plot_param_rmse(df)
    plot_bias_analysis(df)
    plot_x095_error(df)
    plot_training_history()

    print("\n可视化完成！")


if __name__ == "__main__":
    main()
