"""
Figure diagnostics: Ch1-Ch5 图像解释链补齐

4 张图：
  Fig A (fig_offset_mechanism): δ mechanism 概念示意图
    - 手绘 profile σ_η(γ) 曲线，标注 zero-gradient 判据 vs offset-δ 判据
    - 数据源：概念图，不来自 MC
    - 目标：Ch3 §1.4

  Fig B (fig_l2_n_heterogeneity): L2/n 双 panel 诊断
    - Panel A: pooled δ-risk by n (n=7/10/20)，标 δ*
    - Panel B: within each n, δ-risk curves split by β
    - 数据源：delta_risk_curve.csv (Panel A) + mc_scan_raw.csv (Panel B)
    - 目标：Ch4 §2

  Fig C (fig_l4_beta_n_heatmap): β×n δ* heatmap
    - 数据源：L4_by_beta_n.csv
    - 目标：Ch5 §3

  Fig D (fig_l5_heatmap): L5 β×γ/η×n heatmap (supplementary)
    - 数据源：L5_by_beta_goe_n.csv
    - 目标：附录

聚合规则与 analyze_E1.py / plot_fig2.py 完全一致：
  j1_sq = (Δβ/β)² + (Δη/η)² + (Δγ/η)²，先 mean(j1_sq) 再 sqrt

可复现性：若 mc_scan_raw.csv 缺失，脚本会打印明确指令，不会自动运行
generate_mc_data.py。请用户手动执行：
  python code/generate_mc_data.py --merge-only

输出: artifacts/formal/figures/fig_*.{svg,pdf,png}
"""

import os
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

# ── 路径 ──
STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E1_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "E1_baseline")
E2_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "E2_oracle_layers")
SHARED_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "shared_data")
FIG_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── 出版级 rcParams（与 plot_fig2.py 一致）──
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "font.size": 7,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
})

# Okabe-Ito 色盲安全调色板（与 plot_fig2.py 一致）
OKABE_ITO = {
    1.5: "#E69F00",
    2.0: "#56B4E9",
    2.5: "#009E73",
    4.0: "#0072B2",
    5.0: "#D55E00",
}

# n 值调色板（灰阶递进，n 大 = 深）
N_COLORS = {7: "#9ecae1", 10: "#4292c6", 20: "#08519c"}


def save_three_formats(fig, out_base):
    """保存 SVG + PDF + PNG 三格式。"""
    fig.savefig(f"{out_base}.svg", bbox_inches="tight")
    fig.savefig(f"{out_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{out_base}.png", dpi=300, bbox_inches="tight")
    print(f"  Saved: {os.path.basename(out_base)}.{{svg,pdf,png}}")


def ensure_mc_scan_raw():
    """检查 mc_scan_raw.csv 是否存在。

    若缺失，打印明确指令让用户手动运行 merge，返回 False。
    本脚本不会自动运行 generate_mc_data.py。
    """
    csv_path = os.path.join(SHARED_DIR, "mc_scan_raw.csv")
    if os.path.exists(csv_path):
        return True
    print("\n" + "=" * 60)
    print("ERROR: mc_scan_raw.csv not found at:")
    print(f"  {csv_path}")
    print("\nThis file is excluded from git (too large). To rebuild it")
    print("from the tracked chunks, run from the Study/01 directory:")
    print()
    print("  python code/generate_mc_data.py --merge-only")
    print()
    print("Do NOT run the full generate_mc_data.py without --merge-only,")
    print("as that would regenerate MC data (not needed for figures).")
    print("=" * 60 + "\n")
    return False


# ============================================================
# Fig A: δ mechanism schematic (概念图)
# ============================================================

def plot_fig_offset_mechanism():
    """
    概念示意图：profile 标准差曲线 σ_η,min(γ) 在真实 γ 附近，
    展示 zero-gradient 判据 vs offset-δ 判据的差异。

    这是 finite-sample 下的一种可能示意，不是所有样本的通用行为。
    """
    print("\n[Fig A] δ mechanism schematic ...")

    fig, ax = plt.subplots(figsize=(4.8, 3.2))

    # ── 构造一条 profile 曲线（概念化，非真实数据）──
    gamma = np.linspace(-0.3, 1.0, 400)
    gamma_true = 0.15

    sigma_ideal = 0.6 * (gamma - gamma_true)**2 + 0.02
    distortion = -0.15 * np.exp(-((gamma - 0.55) / 0.18)**2)
    sigma_profile = sigma_ideal + distortion + 0.04
    sigma_profile = sigma_profile - sigma_profile.min() + 0.05

    ax.plot(gamma, sigma_profile, color="#333333", linewidth=1.3, zorder=4,
            label=r"$\sigma_{\eta,\min}(\gamma)$ profile (schematic)")

    # 计算极值用于设置 ylim（给底部留出空间放误差标注）
    sigma_min_val = sigma_profile.min()
    sigma_max_val = sigma_profile.max()

    # ── 真实 γ 标记 ──
    sigma_at_true = np.interp(gamma_true, gamma, sigma_profile)
    ax.axvline(gamma_true, color="#009E73", linewidth=0.7, linestyle="--", zorder=2)
    ax.scatter([gamma_true], [sigma_at_true], color="#009E73", s=18, zorder=5,
               clip_on=False)
    ax.annotate(r"True $\gamma$", xy=(gamma_true, sigma_at_true),
                xytext=(gamma_true - 0.08, sigma_at_true + 0.06),
                fontsize=6, color="#009E73", ha="right",
                arrowprops=dict(arrowstyle="-", lw=0.5, color="#009E73"))

    # ── 零梯度判据 ──
    grad = np.gradient(sigma_profile, gamma)
    mask_right = gamma > 0.3
    idx_zero = np.argmin(np.abs(grad[mask_right]))
    gamma_zero_grad = gamma[mask_right][idx_zero]
    sigma_zero_grad = sigma_profile[mask_right][idx_zero]

    ax.axvline(gamma_zero_grad, color="#D55E00", linewidth=0.7, linestyle=":", zorder=2)
    ax.scatter([gamma_zero_grad], [sigma_zero_grad], color="#D55E00", s=18,
               zorder=5, clip_on=False, marker="v")
    ax.annotate(r"$\hat{\gamma}_0$ (zero-gradient)" + "\n" +
                r"$\partial\sigma/\partial\gamma = 0$",
                xy=(gamma_zero_grad, sigma_zero_grad),
                xytext=(gamma_zero_grad + 0.06, sigma_zero_grad + 0.02),
                fontsize=5.5, color="#D55E00",
                arrowprops=dict(arrowstyle="-", lw=0.5, color="#D55E00"))

    # ── offset-δ 判据 ──
    delta_val = 0.35
    mask_left = (gamma > -0.1) & (gamma < 0.4)
    target = grad[mask_left] - delta_val
    idx_delta = np.argmin(np.abs(target))
    gamma_delta = gamma[mask_left][idx_delta]
    sigma_delta = sigma_profile[mask_left][idx_delta]

    ax.axvline(gamma_delta, color="#0072B2", linewidth=0.7, linestyle="--", zorder=2)
    ax.scatter([gamma_delta], [sigma_delta], color="#0072B2", s=18,
               zorder=5, clip_on=False, marker="s")
    ax.annotate(r"$\hat{\gamma}_\delta$ (offset-$\delta$)" + "\n" +
                r"$\partial\sigma/\partial\gamma = \delta$",
                xy=(gamma_delta, sigma_delta),
                xytext=(gamma_delta - 0.08, sigma_delta + 0.08),
                fontsize=5.5, color="#0072B2", ha="center",
                arrowprops=dict(arrowstyle="-", lw=0.5, color="#0072B2"))

    # ── 误差箭头：放在 axes 内部的可见区域（修复底部重叠）──
    # 用 axes 坐标系，确保始终在可见范围内
    y_small_err = sigma_min_val - 0.008  # 略低于曲线最低点
    y_large_err = y_small_err - 0.035    # 再低一档，两箭头分层不重叠
    ax.annotate("", xy=(gamma_delta, y_small_err), xytext=(gamma_true, y_small_err),
                arrowprops=dict(arrowstyle="<->", lw=0.6, color="#0072B2",
                                shrinkA=0, shrinkB=0))
    ax.text((gamma_true + gamma_delta) / 2, y_small_err + 0.003,
            "small error", fontsize=5, color="#0072B2", ha="center", va="bottom")

    ax.annotate("", xy=(gamma_zero_grad, y_large_err), xytext=(gamma_true, y_large_err),
                arrowprops=dict(arrowstyle="<->", lw=0.6, color="#D55E00",
                                shrinkA=0, shrinkB=0))
    ax.text((gamma_true + gamma_zero_grad) / 2, y_large_err + 0.003,
            "large error", fontsize=5, color="#D55E00", ha="center", va="bottom")

    # ── 梯度判据的文字说明框 ──
    textstr = ("Two criteria (schematic):\n"
               r"(· · ·) $\partial\sigma/\partial\gamma = 0$" + "  zero-gradient\n"
               r"(---) $\partial\sigma/\partial\gamma = \delta$" + "  offset-$\\delta$")
    props = dict(boxstyle="round,pad=0.3", facecolor="white", edgecolor="#cccccc",
                 linewidth=0.5)
    ax.text(0.97, 0.97, textstr, transform=ax.transAxes, fontsize=5.5,
            verticalalignment="top", horizontalalignment="right", bbox=props)

    ax.set_xlabel(r"Location parameter $\gamma$")
    ax.set_ylabel(r"Profile std $\sigma_{\eta,\min}(\gamma)$")
    ax.set_xlim(-0.3, 1.0)
    # 显式设置 ylim，底部留足空间放误差箭头和文字
    ax.set_ylim(y_large_err - 0.02, sigma_max_val * 1.12)
    ax.set_title(r"$\delta$ shifts the search criterion"
                 "\n(one possible finite-sample schematic, not a universal claim)",
                 fontweight="bold", loc="left", fontsize=7)

    out_base = os.path.join(FIG_DIR, "fig_offset_mechanism")
    fig.tight_layout(pad=0.5)
    save_three_formats(fig, out_base)
    plt.close(fig)

    # QA
    print(f"  QA: γ_true={gamma_true}, γ_hat_0={gamma_zero_grad:.3f} (zero-grad), "
          f"γ_hat_δ={gamma_delta:.3f} (offset)")
    print(f"  |error zero-grad| = {abs(gamma_zero_grad - gamma_true):.3f}, "
          f"|error offset| = {abs(gamma_delta - gamma_true):.3f}")


# ============================================================
# Fig B: L2/n heterogeneity (GridSpec 布局，无重叠)
# ============================================================

def plot_fig_l2_n_heterogeneity(by_nb=None):
    """
    使用 GridSpec 2列布局：
      左列（1个大子图）：Panel A，pooled δ-risk by n
      右列（3个小子图纵向排列）：Panel B，每个 n 内 split by β

    Args:
        by_nb: 预聚合的 (n, β, δ) → J1 DataFrame。
               若为 None，则从 mc_scan_raw.csv 聚合。
               若 mc_scan_raw 缺失，打印指令并返回。
    """
    print("\n[Fig B] L2/n heterogeneity diagnostic ...")

    # Panel A 数据（已聚合，总是可用）
    curve = pd.read_csv(os.path.join(E1_DIR, "delta_risk_curve.csv"))

    # Panel B 数据
    if by_nb is None:
        if not ensure_mc_scan_raw():
            print("  [SKIP] fig_l2_n_heterogeneity: mc_scan_raw.csv missing")
            return
        print("  Reading mc_scan_raw.csv for Panel B ...")
        df_raw = pd.read_csv(os.path.join(SHARED_DIR, "mc_scan_raw.csv"))
        df = df_raw[df_raw["converged"]].copy()
        df["j1_sq"] = (
            ((df["beta_hat"] - df["beta"]) / df["beta"]) ** 2
            + ((df["eta_hat"] - df["eta"]) / df["eta"]) ** 2
            + ((df["gamma_hat"] - df["gamma"]) / df["eta"]) ** 2
        )
        df = df[np.isfinite(df["j1_sq"])]
        by_nb = df.groupby(["n", "beta", "delta"])["j1_sq"].mean().reset_index()
        by_nb["J1"] = np.sqrt(by_nb["j1_sq"])
    print(f"  Panel B aggregation: {len(by_nb)} rows")

    # ── GridSpec 布局：左1大 + 右3小 ──
    fig = plt.figure(figsize=(7.5, 3.5))
    gs = gridspec.GridSpec(3, 2, width_ratios=[1, 1.1], height_ratios=[1, 1, 1],
                           hspace=0.45, wspace=0.25,
                           left=0.08, right=0.96, top=0.88, bottom=0.16)

    ax_a = fig.add_subplot(gs[:, 0])  # 左侧整列
    sub_axes = [fig.add_subplot(gs[i, 1]) for i in range(3)]  # 右侧3行

    n_vals = [7, 10, 20]
    beta_vals = [1.5, 2.0, 2.5, 4.0, 5.0]

    # ──────────── Panel A: pooled by n ────────────
    delta_stars_by_n = {}
    for n_val in n_vals:
        col = f"J1_n{n_val}"
        yvals = curve[col].values
        color = N_COLORS[n_val]
        ax_a.plot(curve["delta"], yvals, color=color, linewidth=1.1,
                  label=f"n = {n_val}")
        idx_min = np.argmin(yvals)
        ds = curve["delta"].iloc[idx_min]
        delta_stars_by_n[n_val] = ds
        j1_min = yvals[idx_min]
        ax_a.scatter([ds], [j1_min], color=color, s=12, zorder=5, clip_on=False)

    for n_val in [7, 20]:
        ds = delta_stars_by_n[n_val]
        ax_a.annotate(f"$\\delta^*$={ds:.2f}",
                      xy=(ds, curve[f"J1_n{n_val}"].min()),
                      xytext=(ds + 0.04 if n_val == 7 else ds - 0.18,
                              curve[f"J1_n{n_val}"].min() + 0.02),
                      fontsize=5.5, color=N_COLORS[n_val])

    ax_a.axvline(0.10, color="#666666", linewidth=0.5, linestyle=":", zorder=2)
    ax_a.text(0.105, ax_a.get_ylim()[0] + 0.01, "Default", fontsize=5,
              color="#666666")

    ax_a.set_xlabel(r"Offset $\delta$")
    ax_a.set_ylabel(r"$J_1$ (pooled by $n$)")
    ax_a.set_xlim(-0.01, 0.52)
    ax_a.legend(loc="upper left", handlelength=1.2)
    ax_a.set_title("(a) $\\delta$-risk pooled by $n$\n(all $\\beta$ combined)",
                    fontweight="bold", loc="left", fontsize=7)

    # ──────────── Panel B: within each n, split by β ────────────
    for i, n_val in enumerate(n_vals):
        ax_sub = sub_axes[i]
        for beta_val in beta_vals:
            sub = by_nb[(by_nb["n"] == n_val) & (by_nb["beta"] == beta_val)]
            sub = sub.sort_values("delta")
            color = OKABE_ITO[beta_val]
            ax_sub.plot(sub["delta"], sub["J1"], color=color, linewidth=0.8,
                        label=f"β={beta_val}")
            if beta_val in (1.5, 5.0):
                idx_min = sub["J1"].idxmin()
                ds = sub.loc[idx_min, "delta"]
                ax_sub.scatter([ds], [sub.loc[idx_min, "J1"]], color=color,
                               s=8, zorder=5, clip_on=False)

        ax_sub.axvline(0.10, color="#666666", linewidth=0.4, linestyle=":", zorder=1)
        ax_sub.set_title(f"(b{i+1}) n = {n_val}", fontsize=6.5, fontweight="bold",
                         loc="left")
        ax_sub.set_xlim(-0.01, 0.52)
        if i == 0:
            ax_sub.set_ylabel(r"$J_1$")
            ax_sub.legend(loc="upper left", fontsize=4.5, handlelength=0.8,
                          columnspacing=0.3)
        if i == 2:
            ax_sub.set_xlabel(r"Offset $\delta$")
        ax_sub.tick_params(labelsize=5)

    # Panel B 整体说明（用 figtext 放在右侧顶部）
    fig.text(0.55, 0.93,
             "(b) Within each $n$: $\\delta$-risk split by $\\beta$\n"
             "same $n$, different $\\beta$ → opposite $\\delta^*$",
             fontsize=6.5, fontweight="bold", ha="left", va="bottom")

    out_base = os.path.join(FIG_DIR, "fig_l2_n_heterogeneity")
    save_three_formats(fig, out_base)
    plt.close(fig)

    # QA
    print("  Panel A δ* by n:")
    for n_val in n_vals:
        print(f"    n={n_val}: δ*={delta_stars_by_n[n_val]:.2f}, "
              f"J1_min={curve[f'J1_n{n_val}'].min():.4f}")
    print("  Panel B δ* by (n, β):")
    for n_val in n_vals:
        for beta_val in [1.5, 5.0]:
            sub = by_nb[(by_nb["n"] == n_val) & (by_nb["beta"] == beta_val)]
            idx_min = sub["J1"].idxmin()
            ds = sub.loc[idx_min, "delta"]
            print(f"    n={n_val}, β={beta_val}: δ*={ds:.2f}")


# ============================================================
# Fig C: β×n δ* heatmap (L4)
# ============================================================

def plot_fig_l4_beta_n_heatmap():
    print("\n[Fig C] β×n δ* heatmap (L4) ...")
    df = pd.read_csv(os.path.join(E2_DIR, "L4_by_beta_n.csv"))

    pivot = df.pivot(index="beta", columns="n", values="delta_star_L4")
    beta_order = [1.5, 2.0, 2.5, 4.0, 5.0]
    n_order = [7, 10, 20]
    pivot = pivot.reindex(index=beta_order, columns=n_order)

    fig, ax = plt.subplots(figsize=(3.2, 3.0))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto",
                   vmin=0, vmax=0.55)

    for i in range(len(beta_order)):
        for j in range(len(n_order)):
            val = pivot.values[i, j]
            color = "white" if val > 0.3 else "#333333"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=7, fontweight="bold", color=color)

    ax.set_xticks(range(len(n_order)))
    ax.set_xticklabels([f"n = {n}" for n in n_order])
    ax.set_yticks(range(len(beta_order)))
    ax.set_yticklabels([f"β = {b}" for b in beta_order])

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label(r"Optimal $\delta^*$ (L4)", fontsize=6)
    cbar.ax.tick_params(labelsize=5)

    ax.set_title(r"$\delta^*$ by $\beta$ (rows) and $n$ (columns)"
                 "\n" + r"$\beta$ = main effect, $n$ = modifier",
                 fontweight="bold", loc="left", fontsize=7)

    ax.spines["right"].set_visible(True)
    ax.spines["top"].set_visible(True)

    out_base = os.path.join(FIG_DIR, "fig_l4_beta_n_heatmap")
    fig.tight_layout(pad=0.5)
    save_three_formats(fig, out_base)
    plt.close(fig)

    print("  Heatmap values:")
    print(pivot.to_string())
    row_range = pivot.max(axis=1) - pivot.min(axis=1)
    col_range = pivot.max(axis=0) - pivot.min(axis=0)
    print(f"  β主效应 (列方向range, per n): {col_range.to_dict()}")
    print(f"  n调节项 (行方向range, per β): {row_range.to_dict()}")
    print(f"  β平均跨度: {col_range.mean():.3f}, n平均跨度: {row_range.mean():.3f}")


# ============================================================
# Fig D: L5 β×γ/η×n heatmap (supplementary)
# ============================================================

def plot_fig_l5_heatmap():
    print("\n[Fig D] L5 β×γ/η×n heatmap (supplementary) ...")
    df = pd.read_csv(os.path.join(E2_DIR, "L5_by_beta_goe_n.csv"))

    beta_order = [1.5, 2.0, 2.5, 4.0, 5.0]
    goe_order = [0.1, 0.5, 1.0]
    n_order = [7, 10, 20]

    fig, axes = plt.subplots(1, 3, figsize=(6.5, 2.8), sharey=True)

    for idx, n_val in enumerate(n_order):
        ax = axes[idx]
        sub = df[df["n"] == n_val]
        pivot = sub.pivot(index="beta", columns="gamma_over_eta",
                          values="delta_star_L5")
        pivot = pivot.reindex(index=beta_order, columns=goe_order)

        im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto",
                       vmin=0, vmax=0.55)

        for i in range(len(beta_order)):
            for j in range(len(goe_order)):
                val = pivot.values[i, j]
                color = "white" if val > 0.3 else "#333333"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=6, fontweight="bold", color=color)

        ax.set_xticks(range(len(goe_order)))
        ax.set_xticklabels([f"{g}" for g in goe_order])
        ax.set_xlabel(r"$\gamma/\eta$", fontsize=6)
        if idx == 0:
            ax.set_yticks(range(len(beta_order)))
            ax.set_yticklabels([f"{b}" for b in beta_order])
            ax.set_ylabel(r"$\beta$", fontsize=7)
        ax.set_title(f"n = {n_val}", fontsize=7, fontweight="bold")
        ax.tick_params(labelsize=5)

    cbar = fig.colorbar(im, ax=axes, shrink=0.8, pad=0.02)
    cbar.set_label(r"$\delta^*$ (L5)", fontsize=6)
    cbar.ax.tick_params(labelsize=5)

    fig.suptitle(r"L5 $\delta^*$: $\beta$ (main) × $\gamma/\eta$ × $n$"
                 "  — γ/η detail effect, small margin",
                 fontsize=7, fontweight="bold", x=0.02, ha="left")

    out_base = os.path.join(FIG_DIR, "fig_l5_heatmap")
    save_three_formats(fig, out_base)
    plt.close(fig)

    l4 = pd.read_csv(os.path.join(E2_DIR, "L4_by_beta_n.csv"))
    l5_grouped = df.groupby(["beta", "n"]).agg({"J1_at_L5": "mean"}).reset_index()
    l4_grouped = l4.groupby(["beta", "n"]).agg({"J1_at_L4": "mean"}).reset_index()
    merged = l4_grouped.merge(l5_grouped, on=["beta", "n"])
    merged["improvement_pct"] = (1 - merged["J1_at_L5"] / merged["J1_at_L4"]) * 100
    print(f"  L4→L5 mean improvement: {merged['improvement_pct'].mean():.2f}% "
          f"(range {merged['improvement_pct'].min():.2f}%-{merged['improvement_pct'].max():.2f}%)")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Figure diagnostics: Ch1-Ch5 图像解释链补齐")
    print("=" * 60)

    # Fig A, C, D 不依赖 mc_scan_raw.csv
    plot_fig_offset_mechanism()
    plot_fig_l4_beta_n_heatmap()
    plot_fig_l5_heatmap()

    # Fig B 依赖 mc_scan_raw.csv
    plot_fig_l2_n_heterogeneity()

    print("\n" + "=" * 60)
    print("Done. Output:", FIG_DIR)
    print("=" * 60)
