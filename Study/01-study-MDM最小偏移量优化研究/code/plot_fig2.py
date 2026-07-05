"""
Figure 2: δ-risk 曲线

Panel A: 全局 δ-risk 曲线（标注 δ*=0.08 和 Default=0.10）
Panel B: 分 β 的 δ-risk 曲线（5 条线，揭示不同 β 最优 δ 方向相反）

数据来源：
  - Panel A: artifacts/formal/E1_baseline/delta_risk_curve.csv (已聚合)
  - Panel B: artifacts/formal/shared_data/mc_scan_raw.csv (从源头按 β 聚合)
    聚合规则与 analyze_E1.py 完全一致：
    j1_sq = (Δβ/β)² + (Δη/η)² + (Δγ/η)²，先 mean(j1_sq) 再 sqrt

输出: artifacts/formal/figures/fig2_delta_risk_curve.{svg,pdf,png}
"""

import os
import sys

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# ── 路径 ──
STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E1_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "E1_baseline")
SHARED_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "shared_data")
FIG_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── 出版级 rcParams ──
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",       # editable text in SVG
    "pdf.fonttype": 42,           # editable TrueType in PDF
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

# Okabe-Ito 色盲安全调色板（5 色，给 5 个 β 值）
OKABE_ITO = {
    1.5: "#E69F00",  # orange
    2.0: "#56B4E9",  # sky blue
    2.5: "#009E73",  # green
    4.0: "#0072B2",  # blue
    5.0: "#D55E00",  # vermillion
}

# ── 读取数据 ──
# Panel A: 全局 + 分 n 的 δ-risk（已由 analyze_E1.py 产出）
curve_global = pd.read_csv(os.path.join(E1_DIR, "delta_risk_curve.csv"))

# Panel B: 从 mc_scan_raw.csv 按 β 聚合
# 聚合规则与 analyze_E1.py 的 build_j1_sq_table 完全一致
print("[fig2] 读取 mc_scan_raw.csv 计算 per-β δ-risk ...")
df_raw = pd.read_csv(os.path.join(SHARED_DIR, "mc_scan_raw.csv"))
df = df_raw[df_raw["converged"]].copy()

# 逐样本未开方贡献 j1_sq
df["j1_sq"] = (
    ((df["beta_hat"] - df["beta"]) / df["beta"]) ** 2
    + ((df["eta_hat"] - df["eta"]) / df["eta"]) ** 2
    + ((df["gamma_hat"] - df["gamma"]) / df["eta"]) ** 2
)
df = df[np.isfinite(df["j1_sq"])]

# 按 (β, δ) 分组聚合：先 mean(j1_sq) 再 sqrt
by_beta = df.groupby(["beta", "delta"])["j1_sq"].mean().reset_index()
by_beta["J1"] = np.sqrt(by_beta["j1_sq"])
print(f"[fig2] per-β 聚合完成，{len(by_beta)} 行")

# ── Figure ──
fig, (ax_a, ax_b) = plt.subplots(1, 2, figsize=(7.2, 2.8))

# ──────────── Panel A: 全局 δ-risk ────────────
ax_a.plot(curve_global["delta"], curve_global["J1_global"],
          color="#333333", linewidth=1.2, zorder=5)

# 标注 δ*=0.08 和 Default=0.10
delta_star = 0.08
j1_star = curve_global.loc[curve_global["delta"] == delta_star, "J1_global"].values[0]
j1_default = curve_global.loc[curve_global["delta"] == 0.10, "J1_global"].values[0]

# δ* 标记
ax_a.axvline(delta_star, color="#0072B2", linewidth=0.6, linestyle="--", zorder=3)
ax_a.scatter([delta_star], [j1_star], color="#0072B2", s=12, zorder=6, clip_on=False)
ax_a.annotate(f"$\\delta^*$ = {delta_star:.2f}\n$J_1$ = {j1_star:.4f}",
              xy=(delta_star, j1_star), xytext=(delta_star + 0.06, j1_star + 0.04),
              fontsize=6, color="#0072B2",
              arrowprops=dict(arrowstyle="-", lw=0.5, color="#0072B2"))

# Default 标记
ax_a.axvline(0.10, color="#D55E00", linewidth=0.6, linestyle=":", zorder=3)
ax_a.scatter([0.10], [j1_default], color="#D55E00", s=12, zorder=6, clip_on=False)
ax_a.annotate(f"Default = 0.10\n$J_1$ = {j1_default:.4f}",
              xy=(0.10, j1_default), xytext=(0.10 + 0.06, j1_default - 0.06),
              fontsize=6, color="#D55E00",
              arrowprops=dict(arrowstyle="-", lw=0.5, color="#D55E00"))

# 平坦区间阴影 [0.06, 0.12]
ax_a.axvspan(0.06, 0.12, alpha=0.08, color="#999999", zorder=1)
ax_a.text(0.09, ax_a.get_ylim()[1] * 0.95 if ax_a.get_ylim()[1] > 0 else 0.7,
          "flat\nregion", ha="center", fontsize=5, color="#666666")

ax_a.set_xlabel("Offset $\\delta$")
ax_a.set_ylabel("$J_1$ (global)")
ax_a.set_xlim(-0.01, 0.52)
ax_a.set_title("(a) Global $\\delta$-risk curve", fontweight="bold", loc="left")

# ──────────── Panel B: 分 β 的 δ-risk ────────────
for beta_val in [1.5, 2.0, 2.5, 4.0, 5.0]:
    sub = by_beta[by_beta["beta"] == beta_val].sort_values("delta")
    color = OKABE_ITO[beta_val]
    ax_b.plot(sub["delta"], sub["J1"],
              color=color, linewidth=1.0, label=f"$\\beta$ = {beta_val}")

    # 标注每条线的最优 δ（用最低 J1 点）
    idx_min = sub["J1"].idxmin()
    delta_opt = sub.loc[idx_min, "delta"]
    j1_opt = sub.loc[idx_min, "J1"]
    ax_b.scatter([delta_opt], [j1_opt], color=color, s=10, zorder=5, clip_on=False)

    # 只标极端 β 的最优 δ 文字（避免拥挤）
    if beta_val in (1.5, 5.0):
        ax_b.annotate(f"$\\delta^*$={delta_opt:.2f}",
                      xy=(delta_opt, j1_opt),
                      xytext=(delta_opt + (0.03 if beta_val == 1.5 else -0.13),
                              j1_opt + (0.03 if beta_val == 1.5 else -0.04)),
                      fontsize=5, color=color)

# Default 竖线
ax_b.axvline(0.10, color="#333333", linewidth=0.5, linestyle=":", zorder=2)
ax_b.text(0.105, ax_b.get_ylim()[0] + 0.01, "Default=0.10", fontsize=5, color="#333333")

ax_b.set_xlabel("Offset $\\delta$")
ax_b.set_ylabel("$J_1$ (by $\\beta$)")
ax_b.set_xlim(-0.01, 0.52)
ax_b.legend(loc="upper left", ncol=1, columnspacing=0.5, handlelength=1.2)
ax_b.set_title("(b) $\\delta$-risk by shape parameter $\\beta$", fontweight="bold", loc="left")

# ── 保存 ──
out_base = os.path.join(FIG_DIR, "fig2_delta_risk_curve")
fig.tight_layout(pad=0.5, w_pad=1.5)
fig.savefig(f"{out_base}.svg", bbox_inches="tight")
fig.savefig(f"{out_base}.pdf", bbox_inches="tight")
fig.savefig(f"{out_base}.png", dpi=300, bbox_inches="tight")
print(f"Saved: {out_base}.{{svg,pdf,png}}")

# ── QA: 打印关键数值验证 ──
print("\n=== QA ===")
print(f"Panel A: δ*=0.08 J1={j1_star:.6f}, Default J1={j1_default:.6f}, diff={abs(j1_star-j1_default)/j1_default*100:.3f}%")
print("Panel B: per-β optimal δ:")
for beta_val in [1.5, 2.0, 2.5, 4.0, 5.0]:
    sub = by_beta[by_beta["beta"] == beta_val].sort_values("delta")
    idx_min = sub["J1"].idxmin()
    print(f"  β={beta_val}: δ*={sub.loc[idx_min,'delta']:.2f}, J1={sub.loc[idx_min,'J1']:.4f}")
