"""
E09-6 三种范式统一对比
- E09-6a: 统一测试数据汇总
- E09-6b: 样本量-误差主图
- E09-6c: 参数视角与工程视角排序
- E09-6d: 最终方法阶梯表
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from matplotlib.patches import FancyBboxPatch
from scipy.interpolate import make_interp_spline

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
DATA_DIR = os.path.join(SCRIPT_DIR, "..", "实验数据")
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

# 方法定义
METHODS = {
    'BP-raw': {'color': COLORS['blue'], 'marker': 'o', 'label': 'BP-raw'},
    'BP-feature': {'color': COLORS['purple'], 'marker': 'D', 'label': 'BP-feature'},
    'SVM': {'color': COLORS['red'], 'marker': 's', 'label': 'SVM'},
    'Hybrid': {'color': COLORS['orange'], 'marker': '^', 'label': 'Hybrid'},
    'Oracle': {'color': COLORS['green'], 'marker': 'p', 'label': 'Oracle'},
}


def load_all_data():
    """加载所有实验数据"""
    # BP-raw (corrected)
    bp_raw = pd.read_csv(os.path.join(DATA_DIR, 'E09-2a_summary_corrected.csv'))

    # BP-feature (corrected)
    bp_feature = pd.read_csv(os.path.join(DATA_DIR, 'E09-2b_summary_corrected.csv'))

    # SVM
    svm = pd.read_csv(os.path.join(DATA_DIR, 'E09-4b_svm_summary.csv'))

    # Hybrid & Oracle
    hybrid = pd.read_csv(os.path.join(DATA_DIR, 'E09-5_hybrid_summary.csv'))

    # 组装统一表
    rows = []
    for _, br in bp_raw.iterrows():
        n = int(br['n'])
        bf = bp_feature[bp_feature['n'] == n].iloc[0]
        sv = svm[svm['n'] == n].iloc[0]
        hb = hybrid[hybrid['n'] == n].iloc[0]

        rows.append({
            'n': n,
            'jparam_bp_raw': br['j_param'],
            'jparam_bp_feature': bf['j_param'],
            'jparam_svm': sv['jparam_proba'],
            'jparam_hybrid': hb['jparam_hybrid'],
            'jparam_oracle': hb['jparam_oracle'],
            # BP-raw 详细指标
            'rmse_beta': br.get('rmse_beta_rel', np.nan),
            'rmse_eta': br.get('rmse_eta_rel', np.nan),
            'rmse_gamma': br.get('rmse_gamma_rel', np.nan),
            'bias_beta': br.get('bias_beta', np.nan),
            'bias_eta': br.get('bias_eta', np.nan),
            'bias_gamma': br.get('bias_gamma', np.nan),
            'rmse_x095': br.get('rmse_x095', np.nan),
        })

    df = pd.DataFrame(rows)
    return df


# ============================================================
# E09-6a: 统一汇总表
# ============================================================

def generate_unified_table(df):
    """生成统一汇总表"""
    out = os.path.join(DATA_DIR, 'E09-6_unified_summary.csv')
    df.to_csv(out, index=False)
    print(f"Saved: {out}")
    return df


# ============================================================
# E09-6b: 样本量-误差主图
# ============================================================

def plot_main_figure(df):
    """样本量-误差主图：所有方法 J_param vs n"""
    fig, ax = plt.subplots(figsize=(4.5, 3.2))

    methods = ['jparam_bp_raw', 'jparam_bp_feature', 'jparam_svm', 'jparam_hybrid', 'jparam_oracle']
    labels = ['BP-raw', 'BP-feature', 'SVM', 'Hybrid', 'Oracle']
    colors = [COLORS['blue'], COLORS['purple'], COLORS['red'], COLORS['orange'], COLORS['green']]
    markers = ['o', 'D', 's', '^', 'p']

    for method, label, color, marker in zip(methods, labels, colors, markers):
        ax.plot(df['n'], df[method], f'{marker}-', color=color, linewidth=1.5, markersize=6,
                markerfacecolor='white', markeredgewidth=1.2, markeredgecolor=color, label=label)

    # 标注 Oracle 数值
    for _, row in df.iterrows():
        ax.annotate(f"{row['jparam_oracle']:.3f}", (row['n'], row['jparam_oracle']),
                   textcoords="offset points", xytext=(0, -14), ha="center", fontsize=6, color=COLORS['green'])

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
    plt.savefig(os.path.join(IMAGE_DIR, "E09-6b_main_figure.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-6b_main_figure.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-6b_main_figure")


# ============================================================
# E09-6c: 参数视角 vs 工程视角排序
# ============================================================

def plot_param_vs_engineering(df):
    """参数视角 vs 工程视角对比"""
    fig, axes = plt.subplots(1, 2, figsize=(7, 3))

    # 左图：参数视角 J_param
    ax = axes[0]
    methods = ['jparam_bp_raw', 'jparam_bp_feature', 'jparam_svm', 'jparam_hybrid']
    labels = ['BP-raw', 'BP-feature', 'SVM', 'Hybrid']
    colors = [COLORS['blue'], COLORS['purple'], COLORS['red'], COLORS['orange']]
    markers = ['o', 'D', 's', '^']

    for method, label, color, marker in zip(methods, labels, colors, markers):
        ax.plot(df['n'], df[method], f'{marker}-', color=color, linewidth=1.5, markersize=5,
                markerfacecolor='white', markeredgewidth=1, markeredgecolor=color, label=label)

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$ (parameter perspective)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xticks(df['n'])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("(a) Parameter perspective", fontsize=9)

    # 右图：BP-raw 各参数 RMSE
    ax = axes[1]
    params = ['rmse_beta', 'rmse_eta', 'rmse_gamma']
    param_labels = [r'$\mathrm{RMSE}_{rel}(\beta)$', r'$\mathrm{RMSE}_{rel}(\eta)$', r'$\mathrm{RMSE}_{rel}(\gamma)$']
    param_colors = [COLORS['blue'], COLORS['orange'], COLORS['green']]

    for param, label, color in zip(params, param_labels, param_colors):
        ax.plot(df['n'], df[param], 'o-', color=color, linewidth=1.5, markersize=5,
                markerfacecolor='white', markeredgewidth=1, markeredgecolor=color, label=label)

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("Relative RMSE")
    ax.set_xscale("log")
    ax.set_xticks(df['n'])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title("(b) Per-parameter RMSE (BP-raw)", fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-6c_param_vs_engineering.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-6c_param_vs_engineering.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-6c_param_vs_engineering")


# ============================================================
# E09-6d: 最终方法阶梯表
# ============================================================

def plot_ladder_table(df):
    """最终方法阶梯表"""
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.axis('off')

    # 表头
    headers = ['$n$', 'BP-raw', 'BP-feature', 'SVM', 'Hybrid', 'Oracle']
    col_x = [0.05, 0.2, 0.35, 0.5, 0.65, 0.8]

    # 绘制表头
    y = 0.92
    for i, (h, x) in enumerate(zip(headers, col_x)):
        weight = 'bold' if i == 0 else 'normal'
        ax.text(x, y, h, fontsize=8, fontweight=weight, ha='left', va='center',
                transform=ax.transAxes)

    # 分隔线
    ax.plot([0.02, 0.95], [y - 0.05, y - 0.05], color='black', linewidth=0.8, transform=ax.transAxes, clip_on=False)

    # 数据行
    for idx, (_, row) in enumerate(df.iterrows()):
        y = 0.82 - idx * 0.1
        values = [
            f"{int(row['n'])}",
            f"{row['jparam_bp_raw']:.3f}",
            f"{row['jparam_bp_feature']:.3f}",
            f"{row['jparam_svm']:.3f}",
            f"{row['jparam_hybrid']:.3f}",
            f"{row['jparam_oracle']:.3f}",
        ]

        # 找到每行最小值（排除 Oracle）
        main_vals = [row['jparam_bp_raw'], row['jparam_bp_feature'], row['jparam_svm'], row['jparam_hybrid']]
        min_val = min(main_vals)
        min_idx = main_vals.index(min_val) + 1  # +1 因为第一列是 n

        for i, (v, x) in enumerate(zip(values, col_x)):
            if i == 0:
                ax.text(x, y, v, fontsize=8, ha='left', va='center', transform=ax.transAxes)
            elif i == 5:  # Oracle 特殊颜色
                ax.text(x, y, v, fontsize=8, ha='left', va='center', transform=ax.transAxes,
                       color=COLORS['green'])
            elif i == min_idx:
                ax.text(x, y, v, fontsize=8, ha='left', va='center', transform=ax.transAxes,
                       fontweight='bold', color=COLORS['blue'])
            else:
                ax.text(x, y, v, fontsize=8, ha='left', va='center', transform=ax.transAxes)

    # 注释
    ax.text(0.05, 0.02, "Bold: best among non-Oracle methods. Green: Oracle upper bound.",
            fontsize=7, ha='left', va='center', transform=ax.transAxes, color=COLORS['gray'])

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-6d_ladder_table.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-6d_ladder_table.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-6d_ladder_table")


# ============================================================
# E09-6d: 相对比率图
# ============================================================

def plot_ratio_figure(df):
    """各方法相对 BP-raw 的比率"""
    fig, ax = plt.subplots(figsize=(4.5, 3))

    methods = ['jparam_bp_feature', 'jparam_svm', 'jparam_hybrid', 'jparam_oracle']
    labels = ['BP-feature', 'SVM', 'Hybrid', 'Oracle']
    colors = [COLORS['purple'], COLORS['red'], COLORS['orange'], COLORS['green']]
    markers = ['D', 's', '^', 'p']

    for method, label, color, marker in zip(methods, labels, colors, markers):
        ratio = df[method] / df['jparam_bp_raw']
        ax.plot(df['n'], ratio, f'{marker}-', color=color, linewidth=1.5, markersize=6,
                markerfacecolor='white', markeredgewidth=1.2, markeredgecolor=color, label=label)

    ax.axhline(y=1.0, color=COLORS['gray'], linewidth=0.8, linestyle='--', alpha=0.5)
    ax.text(df['n'].iloc[-1], 1.02, 'BP-raw baseline', fontsize=6, color=COLORS['gray'], ha='right')

    ax.set_xlabel("Sample size $n$")
    ax.set_ylabel("$J_{\\mathrm{param}}$ / BP-raw")
    ax.set_xscale("log")
    ax.set_xticks(df['n'])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False, loc='upper right')

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, "E09-6_ratio_to_bp.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, "E09-6_ratio_to_bp.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print("Saved: E09-6_ratio_to_bp")


# ============================================================
# 主函数
# ============================================================

def main():
    print("=" * 60)
    print("E09-6 三种范式统一对比")
    print("=" * 60)

    # 加载数据
    df = load_all_data()

    # E09-6a: 统一汇总表
    print("\n--- E09-6a: 统一汇总表 ---")
    generate_unified_table(df)
    print(df.to_string(index=False))

    # E09-6b: 样本量-误差主图
    print("\n--- E09-6b: 样本量-误差主图 ---")
    plot_main_figure(df)

    # E09-6c: 参数视角 vs 工程视角
    print("\n--- E09-6c: 参数视角 vs 工程视角 ---")
    plot_param_vs_engineering(df)

    # E09-6d: 最终方法阶梯表
    print("\n--- E09-6d: 最终方法阶梯表 ---")
    plot_ladder_table(df)
    plot_ratio_figure(df)

    # 汇总结论
    print("\n" + "=" * 60)
    print("E09-6 结论汇总：")
    print("-" * 60)

    for _, row in df.iterrows():
        n = int(row['n'])
        bp = row['jparam_bp_raw']
        svm = row['jparam_svm']
        hybrid = row['jparam_hybrid']
        oracle = row['jparam_oracle']
        print(f"n={n:>2}: BP-raw={bp:.3f}  SVM={svm:.3f} ({svm/bp:.2f}x)  "
              f"Hybrid={hybrid:.3f} ({hybrid/bp:.2f}x)  Oracle={oracle:.3f} ({oracle/bp:.2f}x)")

    print("\n最终排名（非 Oracle）：")
    print("  BP-raw ≈ BP-feature < SVM < Hybrid")
    print("  Oracle 上限极好 (J_param ≈ 0.11)，说明分类精度是瓶颈")


if __name__ == "__main__":
    main()
