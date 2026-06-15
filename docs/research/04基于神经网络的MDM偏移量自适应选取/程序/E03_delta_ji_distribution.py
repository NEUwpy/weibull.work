"""
E03 固定δ下逐样本误差分布分析
生成两张图：
1. E03_delta_ji_boxplot  — 箱线图（δ vs j_i 分布）
2. E03_delta_ji_histograms — 直方图（典型配置 × 典型δ）
"""
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import sys, os

# Style
sys.path.insert(0, os.path.expanduser("~/AppData/Local/hermes/skills/scientific-visualization/scripts"))
from style_presets import configure_for_journal

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE, "实验数据")
IMG_DIR = os.path.join(BASE, "图像")

BETAS = [2.0, 2.5, 4.0]
NS = [7, 10, 20]
GAMMA_RATIOS = [0.1, 0.5, 1.0]


def compute_ji(df, beta, eta=1.0, gamma_ratio=0.1):
    gamma = gamma_ratio * eta
    return np.sqrt(
        ((df['beta_hat'] - beta) / beta) ** 2 +
        ((df['eta_hat'] - eta) / eta) ** 2 +
        ((df['gamma_hat'] - gamma) / eta) ** 2
    )


def load_all():
    """Load all 27 shard files and compute j_i."""
    records = []
    for beta in BETAS:
        for n in NS:
            for gr in GAMMA_RATIOS:
                fname = f"{DATA_DIR}/E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv"
                df = pd.read_csv(fname)
                df['j_i'] = compute_ji(df, beta, gamma_ratio=gr)
                df['beta'], df['n'], df['gamma_ratio'] = beta, n, gr
                records.append(df[['delta', 'rep', 'j_i', 'beta', 'n', 'gamma_ratio']])
    return pd.concat(records, ignore_index=True)


def fig1_boxplot(big):
    """Boxplot: j_i distribution vs delta (all configs pooled)."""
    configure_for_journal('nature', figure_width='single')
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

    select_deltas = [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14,
                     0.16, 0.20, 0.30, 0.40, 0.50]
    sub = big[big['delta'].isin(select_deltas)]

    fig, ax = plt.subplots(figsize=(7, 3.5))
    bp_data = [sub[sub['delta'] == d]['j_i'].values for d in select_deltas]
    bp = ax.boxplot(bp_data, positions=select_deltas, widths=0.015,
                    showfliers=False, patch_artist=True,
                    medianprops=dict(color='#D55E00', linewidth=1.5),
                    whiskerprops=dict(linewidth=0.8),
                    capprops=dict(linewidth=0.8))

    colors = ['#56B4E9' if d != 0.10 else '#E69F00' for d in select_deltas]
    for patch, color in zip(bp['boxes'], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)

    ax.axvline(0.10, color='#D55E00', linestyle='--', alpha=0.5, linewidth=1,
               label=r'$\delta^*=0.10$')
    ax.set_xlabel(r'偏移量 $\delta$')
    ax.set_ylabel(r'逐样本误差 $j_i$')
    ax.set_title('固定 δ 下的逐样本误差分布（27配置合并）', fontsize=9)
    ax.legend(fontsize=7, frameon=False)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)

    fig.tight_layout()
    fig.savefig(f"{IMG_DIR}/E03_delta_ji_boxplot.png", dpi=300, bbox_inches='tight')
    fig.savefig(f"{IMG_DIR}/E03_delta_ji_boxplot.pdf", bbox_inches='tight')
    plt.close()
    print("Figure 1: E03_delta_ji_boxplot")


def fig2_histograms():
    """Histograms: 3 configs × 3 deltas."""
    configure_for_journal('nature', figure_width='double')
    plt.rcParams['font.sans-serif'] = ['SimHei', 'Arial']
    plt.rcParams['axes.unicode_minus'] = False

    fig_cfgs = [(2.0, 7, 0.1), (2.5, 10, 0.5), (4.0, 20, 1.0)]
    cfg_labels = [r'$\beta=2.0, n=7, \gamma/\eta=0.1$',
                  r'$\beta=2.5, n=10, \gamma/\eta=0.5$',
                  r'$\beta=4.0, n=20, \gamma/\eta=1.0$']
    compare_deltas = [0.02, 0.10, 0.30]
    delta_colors = ['#56B4E9', '#E69F00', '#009E73']

    fig, axes = plt.subplots(3, 3, figsize=(14, 8))

    for row, (beta, n, gr), label in zip(range(3), fig_cfgs, cfg_labels):
        df = pd.read_csv(f"{DATA_DIR}/E03-3_delta_sweep_beta{beta}_n{n}_gamma{gr}.csv")
        df['j_i'] = compute_ji(df, beta, gamma_ratio=gr)

        for col, (delta, color) in enumerate(zip(compare_deltas, delta_colors)):
            ax = axes[row, col]
            data = df[df['delta'] == delta]['j_i'].values

            ax.hist(data, bins=30, density=True, alpha=0.7, color=color,
                    edgecolor='white', linewidth=0.5)
            ax.axvline(np.median(data), color='#D55E00', linestyle='--',
                       linewidth=1.2, label=f'中位数={np.median(data):.3f}')
            ax.axvline(np.mean(data), color='black', linestyle=':',
                       linewidth=1.0, label=f'均值={np.mean(data):.3f}')

            if row == 0:
                ax.set_title(rf'$\delta$={delta}', fontsize=10)
            if col == 0:
                ax.text(-0.25, 0.5, label, transform=ax.transAxes, fontsize=8,
                        va='center', ha='right', rotation=90)
            if row == 2:
                ax.set_xlabel(r'$j_i$')
            if col == 0:
                ax.set_ylabel('概率密度')

            ax.legend(fontsize=6, loc='upper right', frameon=False)
            ax.spines['top'].set_visible(False)
            ax.spines['right'].set_visible(False)

    fig.suptitle('不同 δ 下逐样本误差 j_i 的分布（三个典型配置）', fontsize=11, y=1.01)
    fig.tight_layout()
    fig.savefig(f"{IMG_DIR}/E03_delta_ji_histograms.png", dpi=300, bbox_inches='tight')
    fig.savefig(f"{IMG_DIR}/E03_delta_ji_histograms.pdf", bbox_inches='tight')
    plt.close()
    print("Figure 2: E03_delta_ji_histograms")


def print_summary(big):
    """Print summary statistics."""
    summary = big.groupby('delta')['j_i'].agg(
        ['median', 'mean', 'std',
         lambda x: x.quantile(0.25),
         lambda x: x.quantile(0.75),
         lambda x: x.quantile(0.95),
         lambda x: x.quantile(0.99)])
    summary.columns = ['median', 'mean', 'std', 'Q25', 'Q75', 'P95', 'P99']
    print("\n=== 全局聚合 j_i 按 delta ===")
    print(summary.round(4).to_string())


if __name__ == '__main__':
    print("Loading data...")
    big = load_all()
    print(f"Total rows: {len(big):,}")
    print_summary(big)
    fig1_boxplot(big)
    fig2_histograms()
    print("Done.")
