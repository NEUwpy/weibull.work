"""Study02 S4 论文级图表（`13-PQ-综合科学报告.md` 配套）。

只从已封存分析产物读取（JSON/CSV），禁止手抄数值；可复跑、确定性输出。
用法（Study02 根目录下）：

    python code/study02pq/paper_figures.py --root . --out figures/pq-paper
    python code/study02pq/paper_figures.py --root . --figure fig2

输出 4 张图（各 300 dpi PNG + 矢量 PDF）：
  fig1_main_effect  10-seed 主效应：总体与按 n 的 P/Q rRMSE + 相对改善 95% CI
  fig2_mechanism    x0.95 逐参数敏感度、区域收益关联、精确补偿
  fig3_robustness   稳健性：目标水平（confirmatory/robustness）、交叉目标、容量（descriptive）
  fig4_boundary     边界：网格 / 连续域内 / 中点 / gamma-holdout OOD（禁池化）

色板为 Okabe-Ito（色盲友好）。图注/坐标含单位与定义。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

# ----------------------------------------------------------------------
# 常量：色盲友好 Okabe-Ito 色板
# ----------------------------------------------------------------------
C_BLUE = "#0072B2"
C_ORANGE = "#E69F00"
C_GREEN = "#009E73"
C_RED = "#D55E00"
C_SKY = "#56B4E9"
C_PURPLE = "#CC79A7"
C_GREY = "#999999"
C_BLACK = "#000000"

# 三个数据合同：与 S4 报告/图一致，顺序固定，禁止池化
CONTRACT_ORDER = ["iid grid", "continuous within-range", "within-domain midpoints",
                  "gamma-holdout OOD"]
CONTRACT_COLORS = [C_BLUE, C_SKY, C_ORANGE, C_GREEN]

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.colors import TwoSlopeNorm

    HAS_MPL = True
except Exception:  # pragma: no cover - CI 无 matplotlib 时给出可读报错
    HAS_MPL = False


# ----------------------------------------------------------------------
# 工具
# ----------------------------------------------------------------------
def _load_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _save(fig, name: str, out_dir: str) -> None:
    os.makedirs(out_dir, exist_ok=True)
    fig.savefig(os.path.join(out_dir, f"{name}.png"), dpi=300, bbox_inches="tight")
    fig.savefig(os.path.join(out_dir, f"{name}.pdf"), bbox_inches="tight")
    plt.close(fig)


# ----------------------------------------------------------------------
# Fig 1 主效应
# ----------------------------------------------------------------------
def fig1_main_effect(s5b: dict, out_dir: str) -> None:
    """10-seed grid confirmatory rRMSE and relative-improvement intervals."""
    pooled = s5b["confirmatory"]["grid_P_equal_vs_Q_param"]
    per_n = s5b["exploratory"]["per_n"]
    n_keys = ["7", "10", "15", "20"]
    n_labels = ["n=7", "n=10", "n=15", "n=20"]
    grid_n = [per_n[k]["grid_P_vs_Q"] for k in n_keys]
    p_vals = [v["baseline_rrmse"] for v in grid_n]
    q_vals = [v["comparison_rrmse"] for v in grid_n]
    imp_vals = [v["relative_improvement"] * 100 for v in grid_n]
    lo_vals = [v["relative_improvement_ci95"][0] * 100 for v in grid_n]
    hi_vals = [v["relative_improvement_ci95"][1] * 100 for v in grid_n]

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))

    # (a) rRMSE：按 n + pooled
    x = np.arange(5)
    w = 0.36
    all_p = p_vals + [pooled["baseline_rrmse"]]
    all_q = q_vals + [pooled["comparison_rrmse"]]
    axes[0].bar(x - w / 2, all_p, w, label="$P_{equal}$", color=C_BLUE)
    axes[0].bar(x + w / 2, all_q, w, label="$Q_{param}$", color=C_ORANGE)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(n_labels + ["pooled"])
    axes[0].set_ylabel("rRMSE at $x_R$, $R(x_R)=0.95$ · lower better")
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].set_title("(a) P vs Q rRMSE, by sample size and pooled", fontsize=10)
    # 标注 Q 相对 P 的改善（正 => Q better）
    for i in range(5):
        rel = (all_p[i] - all_q[i]) / all_p[i] * 100
        axes[0].text(x[i], max(all_p[i], all_q[i]) + 0.004, f"{rel:.1f}%",
                     ha="center", fontsize=7, color=C_BLACK)

    # (b) 直接对应主 estimand 的相对 rRMSE 改善与 95% CI
    cats = n_labels + ["pooled"]
    means = imp_vals + [pooled["relative_improvement"] * 100]
    los = lo_vals + [pooled["relative_improvement_ci95"][0] * 100]
    his = hi_vals + [pooled["relative_improvement_ci95"][1] * 100]
    xx = np.arange(5)
    axes[1].errorbar(xx, means, yerr=[np.asarray(means) - np.asarray(los),
                                      np.asarray(his) - np.asarray(means)],
                     fmt="o", color=C_BLUE, capsize=4, ms=6, linewidth=1.5)
    axes[1].axhline(0, color=C_GREY, linestyle="--", linewidth=1)
    axes[1].set_xticks(xx)
    axes[1].set_xticklabels(cats)
    axes[1].set_ylabel(r"rRMSE improvement $(P-Q)/P$, % · positive ⇒ Q better")
    axes[1].set_title("(b) Relative improvement with 95% crossed CI", fontsize=10)
    axes[1].set_ylim(0, max(his) + 1.0)
    fig.suptitle("Fig 1 · Confirmatory frozen-grid result across 10 training seeds",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    _save(fig, "fig1_main_effect", out_dir)


# ----------------------------------------------------------------------
# Fig 2 机制
# ----------------------------------------------------------------------
def fig2_mechanism(core: dict, sensitivity: pd.DataFrame,
                   regions: pd.DataFrame, cells: pd.DataFrame,
                   out_dir: str) -> None:
    """当前核心论文 Fig2：只展示冻结网格的 x_0.95 机制证据。"""
    fig, axes = plt.subplots(1, 3, figsize=(12.8, 4.35))

    # (a) P 归一化坐标下逐参数敏感度：线为 5 个 gamma/eta 层级中位数，带为全范围。
    labels = {
        "s_beta": (r"$s_{\beta}$", C_BLUE, "o", "-"),
        "s_eta": (r"$s_{\eta}$", C_ORANGE, "s", "--"),
        "s_gamma": (r"$s_{\gamma}$", C_GREEN, "^", "-."),
    }
    betas = np.sort(sensitivity["beta"].unique())
    for column, (label, color, marker, linestyle) in labels.items():
        grouped = sensitivity.groupby("beta")[column]
        median = grouped.median().reindex(betas).to_numpy(float)
        lo = grouped.min().reindex(betas).to_numpy(float)
        hi = grouped.max().reindex(betas).to_numpy(float)
        axes[0].fill_between(betas, lo, hi, color=color, alpha=0.13, linewidth=0)
        axes[0].plot(betas, median, label=label, color=color, marker=marker,
                     linestyle=linestyle, linewidth=1.5, markersize=4)
    grid_diag = core["sensitivity_grid"]
    axes[0].set_yscale("log")
    axes[0].set_xlabel(r"shape parameter $\beta$")
    axes[0].set_ylabel(r"$|s_j|$ in P-normalized coordinates (log scale)")
    axes[0].set_title("(a) Target sensitivity changes across the frozen grid\n"
                      "line: median; band: range over $\gamma/\eta$", fontsize=9)
    axes[0].legend(frameon=False, fontsize=8, ncol=3, loc="lower left")
    axes[0].text(
        0.98, 0.98,
        rf"$\Vert s\Vert$ range {grid_diag['component_ranges']['s_norm']['max_over_min']:.2f}×"
        "\n" + rf"max direction change {grid_diag['max_pairwise_direction_angle_degrees']:.1f}°",
        transform=axes[0].transAxes, ha="right", va="top", fontsize=7,
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": C_GREY, "alpha": 0.9})

    # (b) 完整 10-seed（200 pair）冻结网格的区域关联；正值表示 Q 的区域 rRMSE 更低。
    styles = {
        "beta": (C_BLUE, "o", r"$\beta$ regions"),
        "gamma_over_eta": (C_ORANGE, "s", r"$\gamma/\eta$ regions"),
    }
    correlations = core["regional_association_exploratory"]["correlations"]
    for region, (color, marker, label) in styles.items():
        sub = regions[regions["region"] == region].sort_values("value")
        axes[1].scatter(sub["mean_s_norm"], sub["q_advantage_abs"],
                        color=color, marker=marker, s=36, label=label, zorder=3)
        for row in sub.itertuples():
            axes[1].annotate(f"{row.value:g}",
                             (row.mean_s_norm, row.q_advantage_abs),
                             xytext=(3, 3), textcoords="offset points", fontsize=6,
                             color=color)
    axes[1].axhline(0, color=C_GREY, linestyle="--", linewidth=1)
    axes[1].set_xlabel(r"regional mean $\Vert s \Vert$")
    axes[1].set_ylabel("regional Q advantage in rRMSE (P − Q)")
    axes[1].set_title("(b) Larger target sensitivity is associated with\n"
                      "larger Q advantage (exploratory)", fontsize=9)
    axes[1].legend(frameon=False, fontsize=8, loc="lower right")
    rb = correlations["beta"]["pearson_r_s_norm_vs_q_advantage_abs"]
    rg = correlations["gamma_over_eta"]["pearson_r_s_norm_vs_q_advantage_abs"]
    axes[1].text(0.03, 0.97, rf"Pearson $r_\beta$={rb:.2f}, $r_{{\gamma/\eta}}$={rg:.2f}",
                 transform=axes[1].transAxes, ha="left", va="top", fontsize=7)

    # (c) 200 个 (n,fold,seed) 配对单元的 x0.95 精确补偿指数。
    p_vals = cells["p_mean_cancel_exact"].to_numpy(float)
    q_vals = cells["q_mean_cancel_exact"].to_numpy(float)
    for p_value, q_value in zip(p_vals, q_vals):
        axes[2].plot([0, 1], [p_value, q_value], color=C_GREY,
                     alpha=0.22, linewidth=0.7, zorder=1)
    jitter = np.linspace(-0.055, 0.055, len(cells))
    axes[2].scatter(jitter, p_vals, color=C_BLUE, marker="o", s=14,
                    alpha=0.68, label="$P_{equal}$ cells", zorder=2)
    axes[2].scatter(1 + jitter, q_vals, color=C_ORANGE, marker="s", s=14,
                    alpha=0.68, label="$Q_{param}$ cells", zorder=2)
    comp = core["exact_compensation_x_0.95"]
    axes[2].scatter([0, 1], [comp["mean_cancel_exact_P"],
                             comp["mean_cancel_exact_Q"]],
                    color=[C_BLUE, C_ORANGE], edgecolor=C_BLACK,
                    marker="D", s=55, linewidth=0.7, zorder=4, label="pooled mean")
    axes[2].set_xticks([0, 1])
    axes[2].set_xticklabels([r"$P_{equal}$", r"$Q_{param}$"])
    axes[2].set_xlim(-0.25, 1.25)
    axes[2].set_ylim(0.25, 1.0)
    axes[2].set_ylabel(r"mean exact cancellation index at $x_{0.95}$")
    axes[2].set_title("(c) Q reaches stronger exact parameter-error\n"
                      "compensation in every paired cell", fontsize=9)
    axes[2].text(
        0.5, 0.30,
        f"{comp['n_cell_pairs_Q_gt_P']}/{comp['n_cell_pairs']} cells; "
        f"means {comp['mean_cancel_exact_P']:.3f} → {comp['mean_cancel_exact_Q']:.3f}",
        ha="center", va="bottom", fontsize=7)

    for ax in axes:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

    fig.suptitle("Fig 2 · Loss geometry and observed result-space mechanism for $x_{0.95}$",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    _save(fig, "fig2_mechanism", out_dir)


# ----------------------------------------------------------------------
# Fig 3 稳健性
# ----------------------------------------------------------------------
def fig3_robustness(target: dict, cross: dict, capacity: dict, out_dir: str) -> None:
    """目标水平（confirmatory/robustness）、交叉目标矩阵、容量（descriptive）。"""
    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.2))

    # (a) 目标特异 Q 各水平：设计级 Δ pooled（mean Q−P 平方相对误差差）95% CI
    #     注：CI 单位为绝对平方相对误差差（~1e-3）；下方标注对应 rel_change %
    lvls = ["0.9", "0.95", "0.99"]
    bt = [target[l]["bootstrap"] for l in lvls]
    rel = [target[l]["rel_change_percent"] for l in lvls]
    means = [b["pooled_mean"] for b in bt]
    lo = [b["ci_lo"] for b in bt]
    hi = [b["ci_hi"] for b in bt]
    xx = np.arange(3)
    axes[0].errorbar(xx, means, yerr=[np.asarray(means) - np.asarray(lo),
                                      np.asarray(hi) - np.asarray(means)],
                     fmt="o", color=C_BLUE, capsize=4, ms=6)
    axes[0].axhline(0, color=C_GREY, linestyle="--", linewidth=1)
    axes[0].set_xticks(xx)
    axes[0].set_xticklabels(["$x_{0.90}$", "$x_{0.95}$\n(confirmatory)", "$x_{0.99}$"])
    axes[0].set_ylabel(r"$\Delta$ pooled (Q−P), sq. rel. err · 95% CI")
    axes[0].set_title("(a) Target-specific Q: consistent direction\n(rel −2.5 / −3.1 / −6.5%)",
                      fontsize=9)
    for i, v in enumerate(rel):
        axes[0].text(xx[i], means[i] - 0.0006, f"{v:+.1f}%", ha="center", fontsize=8)

    # (b) 交叉目标矩阵：各 route 在三个水平上的 rRMSE vs P（%），对角线 = 目标特异
    routes = ["P", "Q95", "Q90", "Q99"]
    targs = ["0.9", "0.95", "0.99"]
    rv = cross["rel_change_vs_P_percent"]
    mat = np.zeros((len(routes), len(targs)))
    for i, r in enumerate(routes):
        for j, t in enumerate(targs):
            if r == "P":
                mat[i, j] = 0.0
            else:
                mat[i, j] = rv[r][t]
    vmin, vmax = -10, 160
    norm = TwoSlopeNorm(vcenter=0, vmin=vmin, vmax=vmax)
    im = axes[1].imshow(mat, cmap="RdBu_r", aspect="auto", norm=norm)
    axes[1].set_xticks(range(3))
    axes[1].set_xticklabels(["$x_{0.90}$", "$x_{0.95}$", "$x_{0.99}$"])
    axes[1].set_yticks(range(4))
    axes[1].set_yticklabels(routes)
    for i in range(4):
        for j in range(3):
            v = mat[i, j]
            nv = norm(v)
            axes[1].text(j, i, f"{v:+.1f}", ha="center", va="center",
                         fontsize=8, color="white" if nv < 0.3 or nv > 0.7 else "black")
    axes[1].set_title("(b) Cross-target rRMSE vs P (%)\nQ best only at its own level (diagonal)",
                      fontsize=9)
    fig.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04, label="rel vs P, %")

    # (c) 容量：rel_change%（folds {1,3}，descriptive）
    caps = ["sm64", "baseline", "lg512"]
    cap_labels = ["small\n64-32", "baseline\n256-128-64", "large\n512-256-128"]
    rel_c = [capacity[c]["rel_change_percent"] for c in caps]
    xx = np.arange(3)
    axes[2].bar(xx, rel_c, 0.55, color=[C_BLUE, C_ORANGE, C_GREEN])
    axes[2].axhline(0, color=C_GREY, linestyle="--", linewidth=1)
    axes[2].set_xticks(xx)
    axes[2].set_xticklabels(cap_labels, fontsize=7)
    axes[2].set_ylabel("rel_change (Q−P)/P, %")
    axes[2].set_title("(c) Capacity (folds {1,3}): direction\nnot removed · descriptive only",
                      fontsize=9)
    for i, v in enumerate(rel_c):
        va, dy = ("bottom", 0.15) if v >= 0 else ("top", -0.15)
        axes[2].text(xx[i], v + dy, f"{v:+.2f}", ha="center", va=va, fontsize=8)
    axes[2].set_ylim(min(rel_c) - 1.1, 0.5)  # 注释留在坐标轴内，不与横轴标签接触

    fig.suptitle("Fig 3 · Robustness: target-specific Q direction holds across levels and capacity",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    _save(fig, "fig3_robustness", out_dir)


# ----------------------------------------------------------------------
# Fig 4 边界
# ----------------------------------------------------------------------
def fig4_boundary(s5b: dict, interp: dict, ood: dict, out_dir: str) -> None:
    """四数据合同分面 + 连续域内 Q-direct（不同合同禁池化）。"""
    grid = s5b["confirmatory"]["grid_P_equal_vs_Q_param"]
    continuous = s5b["exploratory"]["continuous_P_equal_vs_Q_param"]
    g_p, g_q = grid["baseline_rrmse"], grid["comparison_rrmse"]
    g_imp = grid["relative_improvement"] * 100
    c_p, c_q = continuous["baseline_rrmse"], continuous["comparison_rrmse"]
    c_imp = continuous["relative_improvement"] * 100
    m_p, m_q = interp["pooled_rrmse"]["P"], interp["pooled_rrmse"]["Q"]
    m_imp = -interp["rel_change_percent"]  # 转为 (P-Q)/P；负 => P better
    o_p, o_q = ood["pooled"]["p_rrmse"], ood["pooled"]["q_rrmse"]
    # (Q−P)/P 与 grid/midpoint 同度量；sealed p_error_reduction_vs_q=8.07% 为 (P−Q)/Q
    o_imp = -ood["pooled"]["q_error_excess_vs_p"] * 100  # 转为 (P-Q)/P

    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.2))

    # (a) rRMSE across contracts
    x = np.arange(4)
    w = 0.36
    axes[0].bar(x - w / 2, [g_p, c_p, m_p, o_p], w, label="$P_{equal}$", color=C_BLUE)
    axes[0].bar(x + w / 2, [g_q, c_q, m_q, o_q], w, label="$Q_{param}$", color=C_ORANGE)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(["iid grid", "continuous\nwithin-range",
                             "joint\nmidpoints", "γ-holdout\nOOD"], fontsize=7)
    axes[0].set_ylabel("rRMSE at $x_R$")
    axes[0].set_title("(a) rRMSE under four separate contracts", fontsize=9)
    axes[0].legend(frameon=False, fontsize=8)

    # (b) 效应（Q−P)/P%，负 = Q better；每合同独立，不池化
    eff = [g_imp, c_imp, m_imp, o_imp]
    labels = ["iid grid", "continuous", "midpoints", "γ-holdout"]
    bars = axes[1].bar(x, eff, 0.55, color=CONTRACT_COLORS)
    axes[1].axhline(0, color=C_BLACK, linewidth=0.8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=8)
    axes[1].set_ylabel("improvement (P−Q)/P, % · positive ⇒ Q better")
    axes[1].set_title("(b) Target-loss benefit changes across\ndata contracts (no pooling)",
                      fontsize=9)
    for i, (b, v) in enumerate(zip(bars, eff)):
        va, dy = ("bottom", 0.15) if v >= 0 else ("top", -0.15)
        axes[1].text(b.get_x() + b.get_width() / 2, v + dy,
                     f"{v:+.2f}%\n({'Q' if v > 0 else 'P'} better)", ha="center",
                     va=va, fontsize=8)
    axes[1].set_ylim(min(eff) - 2.5, max(eff) + 3.0)  # 上下留白：负值/正值双行注释均在坐标轴内

    # (c) 连续域内：同三输出 P/Q 与单输出 Q-direct，按 n 分层
    per_n = s5b["exploratory"]["per_n"]
    ns = ["7", "10", "15", "20"]
    pp = [per_n[n]["continuous_P_vs_Qdirect"]["baseline_rrmse"] for n in ns]
    qq = [per_n[n]["continuous_P_vs_Q"]["comparison_rrmse"] for n in ns]
    dd = [per_n[n]["continuous_P_vs_Qdirect"]["comparison_rrmse"] for n in ns]
    xx = np.arange(4); width = 0.25
    axes[2].bar(xx - width, pp, width, color=C_BLUE, label="$P_{equal}$")
    axes[2].bar(xx, qq, width, color=C_ORANGE, label="$Q_{param}$")
    axes[2].bar(xx + width, dd, width, color=C_PURPLE, label="$Q_{direct}$")
    axes[2].set_xticks(xx)
    axes[2].set_xticklabels([f"n={n}" for n in ns], fontsize=8)
    axes[2].set_ylabel("continuous-within-range rRMSE")
    axes[2].set_title("(c) Continuous support: direct scalar head\nadds only a modest improvement", fontsize=9)
    axes[2].legend(frameon=False, fontsize=7)

    fig.suptitle("Fig 4 · Boundary: target alignment is conditional on the data contract",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    _save(fig, "fig4_boundary", out_dir)


# ----------------------------------------------------------------------
# 主入口
# ----------------------------------------------------------------------
def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Study02 S4 paper figures (read-only on sealed evidence)")
    p.add_argument("--root", default=".", help="Study02 root dir (contains artifacts/, code/)")
    p.add_argument("--out", default="figures/pq-paper", help="figure output dir (relative to root)")
    p.add_argument("--figure", choices=["all", "fig2"], default="all",
                   help="render all figures or only the current core-mechanism Fig2")
    a = p.parse_args(argv)

    if not HAS_MPL:
        print("matplotlib not available; cannot render figures", file=sys.stderr)
        return 2

    root = os.path.abspath(a.root)
    art = os.path.join(root, "artifacts")

    out_dir = os.path.join(root, a.out)
    core_dir = os.path.join(art, "pq_paper_core/analysis")
    core = _load_json(os.path.join(core_dir, "mechanism_paper_core.json"))
    sensitivity = pd.read_csv(os.path.join(core_dir, "mechanism_sensitivity_grid.csv"))
    regions = pd.read_csv(os.path.join(core_dir, "mechanism_paper_regions.csv"))
    cells = pd.read_csv(os.path.join(core_dir, "mechanism_paper_cells.csv"))
    made = []
    if a.figure == "all":
        s5b = _load_json(os.path.join(art, "pq_s5b_revision/analysis/summary_s5b.json"))
        target = _load_json(os.path.join(art, "pq_s3_target/analysis/target_summary.json"))
        cross = _load_json(os.path.join(art, "pq_s3_target/analysis/cross_target_matrix.json"))
        capacity = _load_json(os.path.join(art, "pq_s3_capacity/analysis/capacity_summary.json"))
        interp = _load_json(os.path.join(art, "pq_s3_interp/analysis/interp_summary.json"))
        ood = _load_json(os.path.join(art, "pq_v3/analysis/summary_v3.json"))
        fig1_main_effect(s5b, out_dir)
        made.append("fig1_main_effect")
        fig3_robustness(target, cross, capacity, out_dir)
        made.append("fig3_robustness")
        fig4_boundary(s5b, interp, ood, out_dir)
        made.append("fig4_boundary")
    fig2_mechanism(core, sensitivity, regions, cells, out_dir)
    made.append("fig2_mechanism")

    print(f"figures written to {out_dir}: {len(made)} PNG (+ matching PDF)")
    for name in made:
        print("  ", f"{name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
