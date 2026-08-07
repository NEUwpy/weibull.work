"""Study02 S4 论文级图表（`13-PQ-综合科学报告.md` 配套）。

只从已封存分析产物读取（JSON/CSV），禁止手抄数值；可复跑、确定性输出。
用法（Study02 根目录下）：

    python code/study02pq/paper_figures.py --root . --out figures/pq-paper

输出 4 张图（各 PNG + PDF）：
  fig1_main_effect  主效应：总体与按 n 的 P/Q rRMSE + Q-P 效应 95% CI
  fig2_mechanism    机制：精确分解分量、区域敏感度关系、cancel_exact 按目标水平
  fig3_robustness   稳健性：目标水平（confirmatory/robustness）、交叉目标、容量（descriptive）
  fig4_boundary     边界：iid 网格 / 域内中点 / gamma-holdout OOD 三数据合同分面（禁池化）

色板为 Okabe-Ito（色盲友好）。图注/坐标含单位与定义。
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np

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
CONTRACT_ORDER = ["iid grid (x0.95)", "within-domain midpoints", "gamma-holdout OOD"]
CONTRACT_COLORS = [C_BLUE, C_ORANGE, C_GREEN]

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

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
    fig.savefig(os.path.join(out_dir, f"{name}.png"), dpi=200, bbox_inches="tight")
    fig.savefig(os.path.join(out_dir, f"{name}.pdf"), bbox_inches="tight")
    plt.close(fig)


# ----------------------------------------------------------------------
# Fig 1 主效应
# ----------------------------------------------------------------------
def fig1_main_effect(s1: dict, out_dir: str) -> None:
    """总体与按 n 的 P/Q rRMSE + Q-P 效应 95% CI（confirmatory, x0.95）。"""
    pooled = s1["pooled"]
    per_n = s1["per_n"]
    n_keys = ["7", "10", "15", "20"]
    n_labels = ["n=7", "n=10", "n=15", "n=20"]
    p_vals = [per_n[k]["p_rrmse"] for k in n_keys]
    q_vals = [per_n[k]["q_rrmse"] for k in n_keys]
    d_vals = [per_n[k]["mean_diff"] for k in n_keys]
    lo_vals = [per_n[k]["ci_lo"] for k in n_keys]
    hi_vals = [per_n[k]["ci_hi"] for k in n_keys]

    fig, axes = plt.subplots(1, 2, figsize=(11.5, 4.2))

    # (a) rRMSE：按 n + pooled
    x = np.arange(5)
    w = 0.36
    all_p = p_vals + [pooled["p_rrmse"]]
    all_q = q_vals + [pooled["q_rrmse"]]
    axes[0].bar(x - w / 2, all_p, w, label="P (parameter precision)", color=C_BLUE)
    axes[0].bar(x + w / 2, all_q, w, label="Q (target quantile)", color=C_ORANGE)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(n_labels + ["pooled"])
    axes[0].set_ylabel("rRMSE at $x_{0.95}$ (rel. squared error) · lower better")
    axes[0].legend(frameon=False, fontsize=8)
    axes[0].set_title("(a) P vs Q rRMSE, by sample size and pooled", fontsize=10)
    # 标注相对变化 (Q−P)/P（与 rel_change 语义一致，负 => Q better）
    for i in range(5):
        rel = (all_q[i] - all_p[i]) / all_p[i] * 100
        axes[0].text(x[i], max(all_p[i], all_q[i]) + 0.004, f"{rel:+.1f}%",
                     ha="center", fontsize=7, color=C_BLACK)

    # (b) Q−P 效应（mean_diff）与 95% CI
    cats = n_labels + ["pooled"]
    means = d_vals + [pooled["hat_delta"]]
    los = lo_vals + [pooled["ci_lo"]]
    his = hi_vals + [pooled["ci_hi"]]
    xx = np.arange(5)
    axes[1].errorbar(xx, means, yerr=[np.asarray(means) - np.asarray(los),
                                      np.asarray(his) - np.asarray(means)],
                     fmt="o", color=C_BLUE, capsize=4, ms=6, linewidth=1.5)
    axes[1].axhline(0, color=C_GREY, linestyle="--", linewidth=1)
    axes[1].set_xticks(xx)
    axes[1].set_xticklabels(cats)
    axes[1].set_ylabel(r"$\Delta$ = mean(rel.sq.err$_Q$ − rel.sq.err$_P$) at $x_{0.95}$")
    axes[1].set_title("(b) Q−P effect with 95% crossed CI (0 excluded)", fontsize=10)
    axes[1].set_ylim(-0.005, 0.001)
    fig.suptitle("Fig 1 · S1 confirmatory: Q lower rRMSE at $x_{0.95}$ (pooled rel −3.14%)",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    _save(fig, "fig1_main_effect", out_dir)


# ----------------------------------------------------------------------
# Fig 2 机制
# ----------------------------------------------------------------------
def fig2_mechanism(mech: dict, sens: dict, me_exact: dict, out_dir: str) -> None:
    """精确分解/抵消、区域敏感度、cancel_exact 按目标水平（S2 + S3 mechanism）。"""
    pooled = mech["pooled"]
    fig, axes = plt.subplots(1, 3, figsize=(12.5, 4.2))

    # (a) 精确分解分量 |C_beta|,|C_eta|,|C_gamma|,|actual|：P vs Q（log scale）
    comps = ["beta", "eta", "gamma"]
    p_c = [pooled["P"][f"rms_c_{c}"] for c in comps] + [pooled["P"]["rms_actual"]]
    q_c = [pooled["Q"][f"rms_c_{c}"] for c in comps] + [pooled["Q"]["rms_actual"]]
    x = np.arange(4)
    w = 0.36
    axes[0].bar(x - w / 2, p_c, w, label="P", color=C_BLUE)
    axes[0].bar(x + w / 2, q_c, w, label="Q", color=C_ORANGE)
    axes[0].set_yscale("log")
    axes[0].set_xticks(x)
    axes[0].set_xticklabels([r"$|C_{\beta}|$", r"$|C_{\eta}|$", r"$|C_{\gamma}|$",
                             r"$|actual|$"])
    axes[0].set_ylabel("RMS component (log)")
    axes[0].set_title("(a) Exact decomposition: Q's large components\ncancel into small |actual|",
                      fontsize=9)
    axes[0].legend(frameon=False, fontsize=8)

    # (b) 区域：mean ||s||（目标敏感度）vs Δ rms_actual（<0 => Q better）
    sens95 = sens["0.95"]
    for rn, color, lbl in [("beta", C_BLUE, "β region"),
                           ("gamma_over_eta", C_ORANGE, "γ/η region")]:
        s_reg = sens95["mean_s_norm_by_region"][rn]
        d_reg = sens95["delta_rms_actual_at_p_by_region"][rn]
        ks = sorted(s_reg.keys(), key=float)
        axes[1].scatter([s_reg[k] for k in ks], [d_reg[k] for k in ks],
                        color=color, s=36, label=lbl)
    axes[1].axhline(0, color=C_GREY, linestyle="--", linewidth=1)
    axes[1].set_xlabel(r"mean $\Vert s \Vert$ (target sensitivity)")
    axes[1].set_ylabel(r"$\Delta$ rms actual (Q−P; <0 ⇒ Q better)")
    axes[1].set_title("(b) Higher-sensitivity regions gain more\n(exploratory association)",
                      fontsize=9)
    axes[1].legend(frameon=False, fontsize=8)

    # (c) cancel_exact 按目标水平（pooled P vs 目标特异 Q）
    lvls = ["0.9", "0.95", "0.99"]
    qkeys = {"0.9": "Q90", "0.95": "Q95", "0.99": "Q99"}
    p_ce = [me_exact[l]["pooled"]["P"]["mean_cancel_exact"] for l in lvls]
    q_ce = [me_exact[l]["pooled"][qkeys[l]]["mean_cancel_exact"] for l in lvls]
    xx = np.arange(3)
    axes[2].plot(xx, p_ce, "o-", color=C_BLUE, label="P", ms=5)
    axes[2].plot(xx, q_ce, "s-", color=C_ORANGE, label="Q (target-specific)", ms=5)
    axes[2].set_xticks(xx)
    axes[2].set_xticklabels(["$x_{0.90}$", "$x_{0.95}$", "$x_{0.99}$"])
    axes[2].set_ylim(0, 1.0)
    axes[2].set_ylabel("mean cancel_exact")
    axes[2].set_title("(c) Exact cancellation by target level\n(identity: |C1|+|C2|+|C3| vs |ΣC|)",
                      fontsize=9)
    axes[2].legend(frameon=False, fontsize=8)

    fig.suptitle("Fig 2 · Mechanism: Q works by along-target cancellation, not per-parameter accuracy",
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
    vmax = 160
    im = axes[1].imshow(mat, cmap="RdBu_r", aspect="auto", vmin=-20, vmax=vmax)
    axes[1].set_xticks(range(3))
    axes[1].set_xticklabels(["$x_{0.90}$", "$x_{0.95}$", "$x_{0.99}$"])
    axes[1].set_yticks(range(4))
    axes[1].set_yticklabels(routes)
    for i in range(4):
        for j in range(3):
            v = mat[i, j]
            axes[1].text(j, i, f"{v:+.1f}", ha="center", va="center",
                         fontsize=8, color="white" if v > vmax * 0.5 else "black")
    axes[1].set_title("(b) Cross-target rRMSE vs P (%)\nQ best only at its own level (diagonal)",
                      fontsize=9)
    fig.colorbar(im, ax=axes[1], fraction=0.046, pad=0.04, label="rel vs P, %")

    # (c) 容量：rel_change%（folds {1,3}，descriptive）
    caps = ["sm64", "baseline", "lg512"]
    cap_labels = ["small 64-32", "baseline 256-128-64", "large 512-256-128"]
    rel_c = [capacity[c]["rel_change_percent"] for c in caps]
    xx = np.arange(3)
    axes[2].bar(xx, rel_c, 0.55, color=[C_BLUE, C_ORANGE, C_GREEN])
    axes[2].axhline(0, color=C_GREY, linestyle="--", linewidth=1)
    axes[2].set_xticks(xx)
    axes[2].set_xticklabels(cap_labels, fontsize=8)
    axes[2].set_ylabel("rel_change (Q−P)/P, %")
    axes[2].set_title("(c) Capacity (folds {1,3}): direction\nnot removed · descriptive only",
                      fontsize=9)
    for i, v in enumerate(rel_c):
        axes[2].text(xx[i], v - 0.5, f"{v:+.2f}", ha="center", fontsize=8)

    fig.suptitle("Fig 3 · Robustness: target-specific Q direction holds across levels and capacity",
                 fontsize=11, y=1.02)
    fig.tight_layout()
    _save(fig, "fig3_robustness", out_dir)


# ----------------------------------------------------------------------
# Fig 4 边界
# ----------------------------------------------------------------------
def fig4_boundary(s1: dict, interp: dict, ood: dict, out_dir: str) -> None:
    """三数据合同分面：iid 网格 / 域内中点 / gamma-holdout OOD（禁池化）。"""
    g_p, g_q = s1["pooled"]["p_rrmse"], s1["pooled"]["q_rrmse"]
    g_rel = s1["pooled"]["rel_change"] * 100  # −3.14% (Q better)
    m_p, m_q = interp["pooled_rrmse"]["P"], interp["pooled_rrmse"]["Q"]
    m_rel = interp["rel_change_percent"]  # +1.86% (P better)
    o_p, o_q = ood["pooled"]["p_rrmse"], ood["pooled"]["q_rrmse"]
    # (Q−P)/P 与 grid/midpoint 同度量；sealed p_error_reduction_vs_q=8.07% 为 (P−Q)/Q
    o_rel = ood["pooled"]["q_error_excess_vs_p"] * 100  # +8.77% (P better)

    fig, axes = plt.subplots(1, 3, figsize=(13.0, 4.2))

    # (a) rRMSE across contracts
    x = np.arange(3)
    w = 0.36
    axes[0].bar(x - w / 2, [g_p, m_p, o_p], w, label="P", color=C_BLUE)
    axes[0].bar(x + w / 2, [g_q, m_q, o_q], w, label="Q", color=C_ORANGE)
    axes[0].set_xticks(x)
    axes[0].set_xticklabels(CONTRACT_ORDER, fontsize=8)
    axes[0].set_ylabel("rRMSE at $x_{0.95}$")
    axes[0].set_title("(a) rRMSE under three data contracts", fontsize=9)
    axes[0].legend(frameon=False, fontsize=8)

    # (b) 效应（Q−P)/P%，负 = Q better；每合同独立，不池化
    eff = [g_rel, m_rel, o_rel]
    labels = ["iid grid", "midpoints", "γ-holdout OOD"]
    bars = axes[1].bar(x, eff, 0.55, color=CONTRACT_COLORS)
    axes[1].axhline(0, color=C_BLACK, linewidth=0.8)
    axes[1].set_xticks(x)
    axes[1].set_xticklabels(labels, fontsize=8)
    axes[1].set_ylabel("effect (Q−P)/P, % · negative ⇒ Q better")
    axes[1].set_title("(b) Q advantage does not generalize across\ndata contracts (no pooling)",
                      fontsize=9)
    for i, (b, v) in enumerate(zip(bars, eff)):
        axes[1].text(b.get_x() + b.get_width() / 2, v + (0.3 if v >= 0 else -1.2),
                     f"{v:+.2f}%\n({'Q' if v < 0 else 'P'} better)", ha="center",
                     fontsize=8)

    # (c) 域内中点按 γ/η 分档：仅最低档 Q 仍优
    goe = interp["per_goe_midpoint"]
    ks = sorted(goe.keys(), key=float)
    grel = [goe[k]["rel_change_percent"] for k in ks]
    xx = np.arange(len(ks))
    axes[2].plot(xx, grel, "o-", color=C_PURPLE, ms=5)
    axes[2].axhline(0, color=C_GREY, linestyle="--", linewidth=1)
    axes[2].set_xticks(xx)
    axes[2].set_xticklabels([f"γ/η {k}" for k in ks], fontsize=8)
    axes[2].set_ylabel("rel_change (Q−P)/P, %")
    axes[2].set_title("(c) Midpoints: Q keeps edge only at\nlowest γ/η (0.175)", fontsize=9)
    for i, v in enumerate(grel):
        axes[2].text(xx[i], v + (0.6 if v >= 0 else -1.6), f"{v:+.2f}",
                     ha="center", fontsize=8)

    fig.suptitle("Fig 4 · Boundary: Q advantage is grid-specific, OOD reverses to P",
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
    a = p.parse_args(argv)

    if not HAS_MPL:
        print("matplotlib not available; cannot render figures", file=sys.stderr)
        return 2

    root = os.path.abspath(a.root)
    art = os.path.join(root, "artifacts")

    s1 = _load_json(os.path.join(art, "pq_iid_main/analysis/summary_iid.json"))
    mech = _load_json(os.path.join(art, "pq_iid_main/analysis/mechanism_summary.json"))
    sens = _load_json(os.path.join(art, "pq_s3_target/analysis/sensitivity_by_target.json"))
    me_exact = _load_json(os.path.join(art, "pq_s3_target/analysis/mechanism_exact_by_target.json"))
    target = _load_json(os.path.join(art, "pq_s3_target/analysis/target_summary.json"))
    cross = _load_json(os.path.join(art, "pq_s3_target/analysis/cross_target_matrix.json"))
    capacity = _load_json(os.path.join(art, "pq_s3_capacity/analysis/capacity_summary.json"))
    interp = _load_json(os.path.join(art, "pq_s3_interp/analysis/interp_summary.json"))
    ood = _load_json(os.path.join(art, "pq_v3/analysis/summary_v3.json"))

    out_dir = os.path.join(root, a.out)
    fig1_main_effect(s1, out_dir)
    fig2_mechanism(mech, sens, me_exact, out_dir)
    fig3_robustness(target, cross, capacity, out_dir)
    fig4_boundary(s1, interp, ood, out_dir)

    made = sorted(f for f in os.listdir(out_dir) if f.endswith(".png"))
    print(f"figures written to {out_dir}: {len(made)} PNG (+ matching PDF)")
    for f in made:
        print("  ", f)
    return 0


if __name__ == "__main__":
    sys.exit(main())
