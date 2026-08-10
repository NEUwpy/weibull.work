"""Study02 S4 论文级图表（`13-PQ-综合科学报告.md` 配套）。

只从已封存分析产物读取（JSON/CSV），禁止手抄数值；可复跑、确定性输出。
用法（Study02 根目录下）：

    python code/study02pq/paper_figures.py --root . --out figures/pq-paper
    python code/study02pq/paper_figures.py --root . --figure fig2

`--all` 输出当前正文 3 张图（各 300 dpi PNG + 矢量 PDF）：
  fig1_main_effect  10-seed 主效应：总体与按 n 的 P/Q rRMSE + 相对改善 95% CI
  fig2_mechanism    目标敏感度、静态 M95 消融、精确补偿与非线性分解
  fig3_error_distribution  x0.95 有符号误差、尾部概率与方向性 MSE 再分配

`--figure extras` 才生成退出正文的两张归档探索图：
  fig3_robustness   目标水平、交叉目标、容量
  fig4_boundary     网格 / 连续域内 / 中点 / gamma-holdout OOD

色板为 Okabe-Ito（色盲友好）。图注/坐标含单位与定义。
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
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
def fig2_mechanism(art_dir: str, out_dir: str) -> None:
    """发布机制闭环分析生成的 Fig2，避免论文图与封存数值各自重算。"""
    source = os.path.join(art_dir, "pq_mechanism_closure", "analysis", "mechanism_closure")
    os.makedirs(out_dir, exist_ok=True)
    for suffix in (".png", ".pdf"):
        src = source + suffix
        if not os.path.exists(src):
            raise FileNotFoundError(
                f"missing mechanism-closure figure {src}; run "
                "python -m study02pq.mechanism_closure first")
        shutil.copyfile(src, os.path.join(out_dir, "fig2_mechanism" + suffix))


# ----------------------------------------------------------------------
# Fig 3 工程误差分布
# ----------------------------------------------------------------------
def _load_engineering_errors(art_dir: str) -> tuple[np.ndarray, np.ndarray]:
    """读取冻结 10-seed P/Q 证据中的相对误差；不修改任何封存文件。"""
    ns = [7, 10, 15, 20]
    seeds = [42, 2026, 3407, 17, 73, 314, 2718, 4099, 8128, 12011]
    p_errors: list[np.ndarray] = []
    q_errors: list[np.ndarray] = []
    for n in ns:
        for fold in range(1, 6):
            for seed in seeds:
                base = "pq_iid_main/evidence" if seed in seeds[:3] \
                    else "pq_s5b_revision/grid_extra/evidence"
                loaded = []
                for route in ("P", "Q"):
                    path = os.path.join(
                        art_dir, base, f"n{n}_f{fold}_s{seed}_r{route}.npz")
                    with np.load(path) as evidence:
                        error = np.asarray(evidence["rel_err"], dtype=np.float64)
                    if not np.isfinite(error).all():
                        raise AssertionError(f"non-finite relative error: {path}")
                    loaded.append(error)
                if loaded[0].shape != loaded[1].shape:
                    raise AssertionError(
                        f"P/Q row-count mismatch: n={n}, fold={fold}, seed={seed}")
                p_errors.append(loaded[0])
                q_errors.append(loaded[1])
    return np.concatenate(p_errors), np.concatenate(q_errors)


def fig3_error_distribution(art_dir: str, out_dir: str) -> None:
    """探索性描述 Q 如何重新分配高估与低估误差。"""
    p_err, q_err = _load_engineering_errors(art_dir)
    cells = pd.read_csv(os.path.join(art_dir, "pq_engineering_audit/cell_metrics.csv"))
    summary = _load_json(os.path.join(art_dir, "pq_engineering_audit/summary.json"))
    if len(p_err) != 480_000 or len(q_err) != 480_000 or len(cells) != 200:
        raise AssertionError("expected 480,000 rows per route and 200 paired model cells")
    # 图中曲线必须与封存审计的点估计逐项一致，避免绘图脚本形成第二套口径。
    checks = {
        "mse": (np.mean(p_err**2), np.mean(q_err**2)),
        "mae": (np.mean(np.abs(p_err)), np.mean(np.abs(q_err))),
        "over_10pct": (np.mean(p_err > 0.10), np.mean(q_err > 0.10)),
        "under_10pct": (np.mean(p_err < -0.10), np.mean(q_err < -0.10)),
    }
    for name, values in checks.items():
        sealed = summary["metrics"][name]
        if not (np.isclose(values[0], sealed["P"], atol=1e-12) and
                np.isclose(values[1], sealed["Q"], atol=1e-12)):
            raise AssertionError(f"figure data drift from engineering audit: {name}")

    fig, axes = plt.subplots(2, 2, figsize=(11.8, 8.2))

    # (a) 有符号相对误差 ECDF。使用分位数参数化，避免绘制近百万个重叠点。
    probs = np.linspace(0.001, 0.999, 1999)
    for error, color, linestyle, label in (
            (p_err, C_BLUE, "-", r"$P_{equal}$"),
            (q_err, C_ORANGE, "--", r"$Q_{param}$")):
        axes[0, 0].plot(np.quantile(error, probs) * 100, probs * 100,
                        color=color, linestyle=linestyle, linewidth=1.7, label=label)
    axes[0, 0].axvline(0, color=C_GREY, linestyle=":", linewidth=1)
    axes[0, 0].set_xlim(-60, 60)
    axes[0, 0].set_xlabel(r"signed relative error $(\hat x_{0.95}-x_{0.95})/x_{0.95}$, %")
    axes[0, 0].set_ylabel("empirical cumulative probability, %")
    axes[0, 0].set_title("(a) Q shifts the error distribution toward\nunderestimation (exploratory)", fontsize=9)
    axes[0, 0].legend(frameon=False, fontsize=8, loc="lower right")
    axes[0, 0].text(
        0.03, 0.97,
        f"mean bias: P {p_err.mean()*100:+.2f}%\nQ {q_err.mean()*100:+.2f}%",
        transform=axes[0, 0].transAxes, ha="left", va="top", fontsize=7,
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": C_GREY, "alpha": 0.9})

    # (b) 绝对误差生存曲线；交叉展示“典型误差略差、极端尾部更好”。
    thresholds = np.linspace(0, 0.60, 121)
    for error, color, linestyle, label in (
            (p_err, C_BLUE, "-", r"$P_{equal}$"),
            (q_err, C_ORANGE, "--", r"$Q_{param}$")):
        survival = [np.mean(np.abs(error) > threshold) * 100 for threshold in thresholds]
        axes[0, 1].plot(thresholds * 100, survival, color=color,
                        linestyle=linestyle, linewidth=1.7, label=label)
    axes[0, 1].set_xlabel("absolute relative-error threshold, %")
    axes[0, 1].set_ylabel("predictions exceeding threshold, %")
    axes[0, 1].set_title("(b) Q is slightly worse at moderate errors\nbut better in the far tail (exploratory)", fontsize=9)
    axes[0, 1].legend(frameon=False, fontsize=8)

    # (c) 高估/低估的方向性尾部概率；颜色区分路线，线型区分方向。
    directional_thresholds = np.linspace(0, 0.40, 81)
    for error, color, route in ((p_err, C_BLUE, "P"), (q_err, C_ORANGE, "Q")):
        over = [np.mean(error > threshold) * 100 for threshold in directional_thresholds]
        under = [np.mean(error < -threshold) * 100 for threshold in directional_thresholds]
        axes[1, 0].plot(directional_thresholds * 100, over, color=color,
                        linestyle="-", linewidth=1.7, label=f"{route}: overestimate")
        axes[1, 0].plot(directional_thresholds * 100, under, color=color,
                        linestyle="--", linewidth=1.7, label=f"{route}: underestimate")
    axes[1, 0].set_xlabel("one-sided relative-error threshold, %")
    axes[1, 0].set_ylabel("predictions beyond threshold, %")
    axes[1, 0].set_title("(c) Under a guaranteed-life interpretation, Q\nreduces overestimation but increases underestimation", fontsize=9)
    axes[1, 0].legend(frameon=False, fontsize=7, ncol=2)

    # (d) 每个模型单元对 MSE 的方向性贡献变化，保留 200 个配对单元。
    over_delta = (cells["Q_positive_mse_contribution"] -
                  cells["P_positive_mse_contribution"]).to_numpy(float) * 1000
    under_delta = (cells["Q_negative_mse_contribution"] -
                   cells["P_negative_mse_contribution"]).to_numpy(float) * 1000
    rng = np.random.default_rng(20260810)
    for x, values, color, marker in (
            (0, over_delta, C_BLUE, "o"), (1, under_delta, C_ORANGE, "s")):
        jitter = rng.uniform(-0.10, 0.10, size=len(values))
        axes[1, 1].scatter(x + jitter, values, color=color, marker=marker,
                           s=13, alpha=0.38, edgecolors="none")
        axes[1, 1].boxplot(
            values, positions=[x], widths=0.34, showfliers=False, patch_artist=True,
            boxprops={"facecolor": color, "alpha": 0.18, "edgecolor": color},
            whiskerprops={"color": color}, capprops={"color": color},
            medianprops={"color": C_BLACK, "linewidth": 1.2})
        axes[1, 1].scatter([x], [values.mean()], marker="D", s=42,
                           color=color, edgecolor=C_BLACK, linewidth=0.6, zorder=4)
    axes[1, 1].axhline(0, color=C_GREY, linestyle=":", linewidth=1)
    axes[1, 1].set_xticks([0, 1])
    axes[1, 1].set_xticklabels(["overestimate\ncontribution", "underestimate\ncontribution"])
    axes[1, 1].set_ylabel(r"paired change Q−P in MSE contribution, $\times10^{-3}$")
    axes[1, 1].set_title("(d) Decomposing the 5.91% MSE difference\nshows opposite directional changes", fontsize=9)
    pos = summary["metrics"]["positive_mse_contribution"]
    neg = summary["metrics"]["negative_mse_contribution"]
    axes[1, 1].text(
        0.02, 0.97,
        f"overestimate MSE: −{pos['effect']*100:.1f}% ({pos['positive_effect_cells']}/200 cells)\n"
        f"underestimate MSE: +{-neg['effect']*100:.1f}% ({200-neg['positive_effect_cells']}/200 cells)",
        transform=axes[1, 1].transAxes, ha="left", va="top", fontsize=7,
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": C_GREY, "alpha": 0.9})

    for ax in axes.flat:
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(axis="y", color="#dddddd", linewidth=0.5, alpha=0.55)

    fig.suptitle(
        "Fig 3 · Exploratory audit: target-aligned training redistributes $x_{0.95}$ error",
        fontsize=11, y=0.995)
    fig.tight_layout(rect=(0, 0, 1, 0.975))
    _save(fig, "fig3_error_distribution", out_dir)


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
    p.add_argument("--figure", choices=["all", "fig2", "fig3error", "extras"], default="all",
                   help="render current paper figures, one core figure, or archived extras")
    a = p.parse_args(argv)

    if not HAS_MPL:
        print("matplotlib not available; cannot render figures", file=sys.stderr)
        return 2

    root = os.path.abspath(a.root)
    art = os.path.join(root, "artifacts")

    out_dir = os.path.join(root, a.out)
    made = []
    if a.figure == "all":
        s5b = _load_json(os.path.join(art, "pq_s5b_revision/analysis/summary_s5b.json"))
        fig1_main_effect(s5b, out_dir)
        made.append("fig1_main_effect")
        fig2_mechanism(art, out_dir)
        made.append("fig2_mechanism")
        fig3_error_distribution(art, out_dir)
        made.append("fig3_error_distribution")
    if a.figure == "extras":
        s5b = _load_json(os.path.join(art, "pq_s5b_revision/analysis/summary_s5b.json"))
        target = _load_json(os.path.join(art, "pq_s3_target/analysis/target_summary.json"))
        cross = _load_json(os.path.join(art, "pq_s3_target/analysis/cross_target_matrix.json"))
        capacity = _load_json(os.path.join(art, "pq_s3_capacity/analysis/capacity_summary.json"))
        interp = _load_json(os.path.join(art, "pq_s3_interp/analysis/interp_summary.json"))
        ood = _load_json(os.path.join(art, "pq_v3/analysis/summary_v3.json"))
        fig3_robustness(target, cross, capacity, out_dir)
        made.append("fig3_robustness")
        fig4_boundary(s5b, interp, ood, out_dir)
        made.append("fig4_boundary")
    if a.figure == "fig2":
        fig2_mechanism(art, out_dir)
        made.append("fig2_mechanism")
    if a.figure == "fig3error":
        fig3_error_distribution(art, out_dir)
        made.append("fig3_error_distribution")

    print(f"figures written to {out_dir}: {len(made)} PNG (+ matching PDF)")
    for name in made:
        print("  ", f"{name}.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
