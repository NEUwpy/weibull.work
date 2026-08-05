"""
E09-3 BP 误差分布深度分析
- E09-3a: 参数误差分布（直方图、Q-Q图、偏度峰度）
- E09-3b: gamma 边界行为分析
- E09-3c: 工程寿命尾部风险分析
"""

import sys
import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib as mpl
from scipy import stats

# Nature 风格设置
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

# 配色
COLORS = {
    "blue": "#0072B2",
    "orange": "#E69F00",
    "green": "#009E73",
    "red": "#D55E00",
    "purple": "#CC79A7",
    "gray": "#666666",
}

SAMPLE_SIZES = [5, 7, 10, 15, 20, 50]


def load_test_data(prefix, n):
    """加载测试数据"""
    csv_path = os.path.join(OUTPUT_DIR, f'{prefix}_test_n{n}.csv')
    df = pd.read_csv(csv_path)

    # 计算相对误差
    df['err_beta'] = (df['beta_pred'] - df['beta_true']) / df['beta_true']
    df['err_eta'] = (df['eta_pred'] - df['eta_true']) / df['eta_true']
    df['err_gamma'] = (df['gamma_pred'] - df['gamma_true']) / df['eta_true']  # gamma 用 eta 归一化

    # 计算绝对误差
    df['abs_err_beta'] = df['beta_pred'] - df['beta_true']
    df['abs_err_eta'] = df['eta_pred'] - df['eta_true']
    df['abs_err_gamma'] = df['gamma_pred'] - df['gamma_true']

    return df


def compute_error_stats(errors):
    """计算误差统计量"""
    return {
        'mean': np.mean(errors),
        'std': np.std(errors, ddof=1),
        'median': np.median(errors),
        'skew': stats.skew(errors),
        'kurt': stats.kurtosis(errors),  # 超额峰度
        'p5': np.percentile(errors, 5),
        'p25': np.percentile(errors, 25),
        'p75': np.percentile(errors, 75),
        'p95': np.percentile(errors, 95),
        'n_outliers': np.sum(np.abs(errors) > 3 * np.std(errors)),
    }


# ============================================================
# E09-3a: 参数误差分布分析
# ============================================================

def plot_error_distributions(prefix='E09-2a'):
    """绘制各参数误差分布（直方图 + KDE）"""
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6))

    params = ['beta', 'eta', 'gamma']
    param_labels = [r'$\beta$', r'$\eta$', r'$\gamma$']
    ns_show = [5, 20, 50]  # 选择代表性样本量

    for i, (param, label) in enumerate(zip(params, param_labels)):
        for j, n in enumerate(ns_show):
            ax = axes[i, j]
            df = load_test_data(prefix, n)
            errors = df[f'err_{param}']

            # 直方图
            ax.hist(errors, bins=30, density=True, alpha=0.6, color=COLORS["blue"], edgecolor='white')

            # KDE
            x_range = np.linspace(errors.min() - 0.1, errors.max() + 0.1, 200)
            kde = stats.gaussian_kde(errors)
            ax.plot(x_range, kde(x_range), color=COLORS["red"], linewidth=1.5)

            # 正态拟合
            mu, sigma = errors.mean(), errors.std()
            ax.plot(x_range, stats.norm.pdf(x_range, mu, sigma),
                   '--', color=COLORS["gray"], linewidth=1, alpha=0.7)

            # 统计量
            stats_text = f'μ={mu:.3f}\nσ={sigma:.3f}\nskew={stats.skew(errors):.2f}'
            ax.text(0.95, 0.95, stats_text, transform=ax.transAxes,
                   fontsize=6, va='top', ha='right',
                   bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

            ax.axvline(x=0, color='black', linestyle='-', linewidth=0.5, alpha=0.5)

            if i == 0:
                ax.set_title(f'$n = {n}$', fontsize=9)
            if j == 0:
                ax.set_ylabel(f'{label} error', fontsize=8)
            if i == 2:
                ax.set_xlabel('Relative error', fontsize=8)

    plt.suptitle(f'{prefix}: Parameter Error Distributions', fontsize=10, y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_error_distributions.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_error_distributions.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print(f"Saved: {prefix}_error_distributions")


def plot_qq_plots(prefix='E09-2a'):
    """绘制 Q-Q 图检验正态性"""
    fig, axes = plt.subplots(3, 3, figsize=(7.2, 6))

    params = ['beta', 'eta', 'gamma']
    param_labels = [r'$\beta$', r'$\eta$', r'$\gamma$']
    ns_show = [5, 20, 50]

    for i, (param, label) in enumerate(zip(params, param_labels)):
        for j, n in enumerate(ns_show):
            ax = axes[i, j]
            df = load_test_data(prefix, n)
            errors = df[f'err_{param}']

            # Q-Q 图
            stats.probplot(errors, dist="norm", plot=ax)
            ax.get_lines()[0].set_markerfacecolor(COLORS["blue"])
            ax.get_lines()[0].set_markeredgecolor(COLORS["blue"])
            ax.get_lines()[0].set_markersize(3)
            ax.get_lines()[1].set_color(COLORS["red"])

            if i == 0:
                ax.set_title(f'$n = {n}$', fontsize=9)
            if j == 0:
                ax.set_ylabel(f'{label} quantiles', fontsize=8)
            else:
                ax.set_ylabel('')
            if i == 2:
                ax.set_xlabel('Theoretical quantiles', fontsize=8)
            else:
                ax.set_xlabel('')

    plt.suptitle(f'{prefix}: Q-Q Plots (Normal)', fontsize=10, y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_qq_plots.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_qq_plots.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print(f"Saved: {prefix}_qq_plots")


def plot_skewness_kurtosis(prefix='E09-2a'):
    """绘制偏度和峰度随样本量变化"""
    fig, axes = plt.subplots(1, 2, figsize=(7, 3))

    params = ['beta', 'eta', 'gamma']
    param_labels = [r'$\beta$', r'$\eta$', r'$\gamma$']
    colors = [COLORS["blue"], COLORS["orange"], COLORS["purple"]]

    skew_data = {p: [] for p in params}
    kurt_data = {p: [] for p in params}

    for n in SAMPLE_SIZES:
        df = load_test_data(prefix, n)
        for p in params:
            skew_data[p].append(stats.skew(df[f'err_{p}']))
            kurt_data[p].append(stats.kurtosis(df[f'err_{p}']))

    # 偏度
    ax = axes[0]
    for p, label, color in zip(params, param_labels, colors):
        ax.plot(SAMPLE_SIZES, skew_data[p], 'o-', color=color, linewidth=1.5, markersize=5,
                markerfacecolor='white', markeredgewidth=1, markeredgecolor=color, label=label)
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.6)
    ax.set_xlabel('Sample size $n$')
    ax.set_ylabel('Skewness')
    ax.set_xscale('log')
    ax.set_xticks(SAMPLE_SIZES)
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title('(a) Skewness', fontsize=9)

    # 峰度
    ax = axes[1]
    for p, label, color in zip(params, param_labels, colors):
        ax.plot(SAMPLE_SIZES, kurt_data[p], 'o-', color=color, linewidth=1.5, markersize=5,
                markerfacecolor='white', markeredgewidth=1, markeredgecolor=color, label=label)
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.6)
    ax.set_xlabel('Sample size $n$')
    ax.set_ylabel('Excess kurtosis')
    ax.set_xscale('log')
    ax.set_xticks(SAMPLE_SIZES)
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title('(b) Excess kurtosis', fontsize=9)

    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_skewness_kurtosis.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_skewness_kurtosis.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print(f"Saved: {prefix}_skewness_kurtosis")


# ============================================================
# E09-3b: gamma 边界行为分析
# ============================================================

def plot_gamma_analysis(prefix='E09-2a'):
    """分析 gamma 的边界行为"""
    fig, axes = plt.subplots(2, 2, figsize=(7, 5.5))

    # 收集所有样本量的数据
    all_data = []
    for n in SAMPLE_SIZES:
        df = load_test_data(prefix, n)
        df['n'] = n
        all_data.append(df)
    df_all = pd.concat(all_data, ignore_index=True)

    # 1. gamma 真值 vs 误差
    ax = axes[0, 0]
    ax.scatter(df_all['gamma_true'], df_all['err_gamma'], s=5, alpha=0.3, color=COLORS["blue"])
    ax.axhline(y=0, color='red', linestyle='-', linewidth=0.8)
    ax.set_xlabel(r'$\gamma_{\mathrm{true}}$')
    ax.set_ylabel(r'$\gamma$ relative error')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title('(a) Error vs true value', fontsize=9)

    # 2. gamma 真值分布
    ax = axes[0, 1]
    ax.hist(df_all['gamma_true'], bins=30, density=True, alpha=0.6, color=COLORS["green"], edgecolor='white')
    ax.set_xlabel(r'$\gamma_{\mathrm{true}}$')
    ax.set_ylabel('Density')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title('(b) True value distribution', fontsize=9)

    # 3. gamma 预测值 vs 真值
    ax = axes[1, 0]
    ax.scatter(df_all['gamma_true'], df_all['gamma_pred'], s=5, alpha=0.3, color=COLORS["purple"])
    lims = [min(df_all['gamma_true'].min(), df_all['gamma_pred'].min()) - 0.1,
            max(df_all['gamma_true'].max(), df_all['gamma_pred'].max()) + 0.1]
    ax.plot(lims, lims, '--', color='gray', linewidth=0.8)
    ax.set_xlabel(r'$\gamma_{\mathrm{true}}$')
    ax.set_ylabel(r'$\gamma_{\mathrm{pred}}$')
    ax.set_xlim(lims)
    ax.set_ylim(lims)
    ax.set_aspect('equal')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title('(c) Predicted vs true', fontsize=9)

    # 4. gamma 预测值为负的比例（按样本量）
    ax = axes[1, 1]
    neg_rates = []
    for n in SAMPLE_SIZES:
        df = load_test_data(prefix, n)
        neg_rate = (df['gamma_pred'] < 0).mean() * 100
        neg_rates.append(neg_rate)

    ax.bar(range(len(SAMPLE_SIZES)), neg_rates, color=COLORS["red"], alpha=0.7)
    ax.set_xticks(range(len(SAMPLE_SIZES)))
    ax.set_xticklabels(SAMPLE_SIZES)
    ax.set_xlabel('Sample size $n$')
    ax.set_ylabel('Negative predictions (%)')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title('(d) Negative prediction rate', fontsize=9)

    # 标注数值
    for i, v in enumerate(neg_rates):
        if v > 0:
            ax.text(i, v + 0.5, f'{v:.1f}%', ha='center', fontsize=7)

    plt.suptitle(f'{prefix}: Gamma Boundary Analysis', fontsize=10, y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_gamma_analysis.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_gamma_analysis.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print(f"Saved: {prefix}_gamma_analysis")


# ============================================================
# E09-3c: 工程寿命尾部风险分析
# ============================================================

def compute_x_error(beta, eta, gamma, beta_hat, eta_hat, gamma_hat, R=0.95):
    """计算工程寿命分位点误差"""
    x_true = gamma + eta * (-np.log(R)) ** (1.0 / beta)
    x_pred = gamma_hat + eta_hat * (-np.log(R)) ** (1.0 / beta_hat)
    return (x_pred - x_true) / x_true  # 相对误差


def plot_x095_tail_analysis(prefix='E09-2a'):
    """分析 x0.95 的尾部风险"""
    fig, axes = plt.subplots(2, 2, figsize=(7, 5.5))

    # 收集所有样本量的数据
    all_data = []
    for n in SAMPLE_SIZES:
        df = load_test_data(prefix, n)
        df['n'] = n
        # 计算 x0.95 误差
        df['err_x095'] = compute_x_error(
            df['beta_true'], df['eta_true'], df['gamma_true'],
            df['beta_pred'], df['eta_pred'], df['gamma_pred'], R=0.95
        )
        all_data.append(df)
    df_all = pd.concat(all_data, ignore_index=True)

    # 1. x0.95 误差分布
    ax = axes[0, 0]
    for n, color in zip([5, 20, 50], [COLORS["blue"], COLORS["orange"], COLORS["red"]]):
        df_n = df_all[df_all['n'] == n]
        ax.hist(df_n['err_x095'] * 100, bins=30, density=True, alpha=0.4,
                color=color, label=f'$n={n}$', edgecolor='white')
    ax.axvline(x=0, color='black', linestyle='-', linewidth=0.5)
    ax.set_xlabel('$x_{0.95}$ relative error (%)')
    ax.set_ylabel('Density')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title('(a) Error distribution', fontsize=9)

    # 2. 尾部风险（95th/99th percentile）
    ax = axes[0, 1]
    p95_data = []
    p99_data = []
    for n in SAMPLE_SIZES:
        df_n = df_all[df_all['n'] == n]
        abs_err = np.abs(df_n['err_x095']) * 100
        p95_data.append(np.percentile(abs_err, 95))
        p99_data.append(np.percentile(abs_err, 99))

    ax.plot(SAMPLE_SIZES, p95_data, 'o-', color=COLORS["blue"], linewidth=1.5, markersize=5,
            markerfacecolor='white', markeredgewidth=1, markeredgecolor=COLORS["blue"], label='95th percentile')
    ax.plot(SAMPLE_SIZES, p99_data, 's--', color=COLORS["red"], linewidth=1.5, markersize=5,
            markerfacecolor='white', markeredgewidth=1, markeredgecolor=COLORS["red"], label='99th percentile')
    ax.set_xlabel('Sample size $n$')
    ax.set_ylabel('$|x_{0.95}$ error| (%)')
    ax.set_xscale('log')
    ax.set_xticks(SAMPLE_SIZES)
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title('(b) Tail risk', fontsize=9)

    # 3. x0.95 误差 vs gamma 真值
    ax = axes[1, 0]
    ax.scatter(df_all['gamma_true'], df_all['err_x095'] * 100, s=5, alpha=0.2, color=COLORS["purple"])
    ax.axhline(y=0, color='red', linestyle='-', linewidth=0.8)
    ax.set_xlabel(r'$\gamma_{\mathrm{true}}$')
    ax.set_ylabel('$x_{0.95}$ error (%)')
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_title('(c) Error vs gamma', fontsize=9)

    # 4. 各样本量的 x0.95 统计
    ax = axes[1, 1]
    stats_data = []
    for n in SAMPLE_SIZES:
        df_n = df_all[df_all['n'] == n]
        err = df_n['err_x095'] * 100
        stats_data.append({
            'n': n,
            'mean': err.mean(),
            'std': err.std(),
            'p5': np.percentile(err, 5),
            'p95': np.percentile(err, 95),
        })
    stats_df = pd.DataFrame(stats_data)

    ax.errorbar(stats_df['n'], stats_df['mean'], yerr=stats_df['std'],
               fmt='o-', color=COLORS["blue"], linewidth=1.5, markersize=5,
               markerfacecolor='white', markeredgewidth=1, markeredgecolor=COLORS["blue"],
               capsize=3, capthick=1, label='Mean ± SD')
    ax.fill_between(stats_df['n'], stats_df['p5'], stats_df['p95'],
                    alpha=0.2, color=COLORS["blue"], label='5th-95th')
    ax.axhline(y=0, color='gray', linestyle='--', linewidth=0.6)
    ax.set_xlabel('Sample size $n$')
    ax.set_ylabel('$x_{0.95}$ error (%)')
    ax.set_xscale('log')
    ax.set_xticks(SAMPLE_SIZES)
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.legend(fontsize=7, frameon=False)
    ax.set_title('(d) Summary statistics', fontsize=9)

    plt.suptitle(f'{prefix}: $x_{{0.95}}$ Tail Risk Analysis', fontsize=10, y=1.02)
    plt.tight_layout()
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_x095_tail_analysis.pdf"), bbox_inches="tight", dpi=300)
    plt.savefig(os.path.join(IMAGE_DIR, f"{prefix}_x095_tail_analysis.png"), bbox_inches="tight", dpi=300)
    plt.close()
    print(f"Saved: {prefix}_x095_tail_analysis")


# ============================================================
# 汇总统计
# ============================================================

def generate_summary_table(prefix='E09-2a'):
    """生成误差分布汇总表"""
    rows = []

    for n in SAMPLE_SIZES:
        df = load_test_data(prefix, n)

        row = {'n': n}
        for param in ['beta', 'eta', 'gamma']:
            errors = df[f'err_{param}']
            stats_dict = compute_error_stats(errors)
            for key, val in stats_dict.items():
                row[f'{param}_{key}'] = val

        # x0.95
        df['err_x095'] = compute_x_error(
            df['beta_true'], df['eta_true'], df['gamma_true'],
            df['beta_pred'], df['eta_pred'], df['gamma_pred'], R=0.95
        )
        x_stats = compute_error_stats(df['err_x095'])
        for key, val in x_stats.items():
            row[f'x095_{key}'] = val

        rows.append(row)

    summary_df = pd.DataFrame(rows)

    # 保存
    output_path = os.path.join(OUTPUT_DIR, f'{prefix}_error_stats.csv')
    summary_df.to_csv(output_path, index=False)
    print(f"Saved: {output_path}")

    return summary_df


# ============================================================
# 主函数
# ============================================================

def main():
    print("="*60)
    print("E09-3 BP 误差分布深度分析")
    print("="*60)

    for prefix in ['E09-2a', 'E09-2b']:
        print(f"\n{'='*40}")
        print(f"分析 {prefix}")
        print(f"{'='*40}")

        # E09-3a: 误差分布
        plot_error_distributions(prefix)
        plot_qq_plots(prefix)
        plot_skewness_kurtosis(prefix)

        # E09-3b: gamma 边界行为
        plot_gamma_analysis(prefix)

        # E09-3c: 工程寿命尾部风险
        plot_x095_tail_analysis(prefix)

        # 汇总统计
        summary = generate_summary_table(prefix)
        print(f"\n{prefix} 误差统计汇总:")
        print(summary[['n', 'beta_skew', 'eta_skew', 'gamma_skew', 'gamma_n_outliers']].to_string(index=False))

    print("\nDone!")


if __name__ == "__main__":
    main()
