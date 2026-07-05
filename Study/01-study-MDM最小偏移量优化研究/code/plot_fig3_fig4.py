"""
Figure 3 + Figure 4: Oracle 层级阶梯收益 + L6 逐样本 δ* 分布

Figure 3 (阶梯收益):
  Panel A: L1-L6 阶梯柱状图 (J₁ 高度)，标注边际收益
  Panel B: 累积改善%曲线，标注两个大跳点 (L3, L6)

Figure 4 (L6 分布):
  Panel A: 全样本 L6 δ* 直方图
  Panel B: 分 β 的 L6 δ* 分布 (boxplot)

数据来源:
  - ladder: artifacts/formal/E2_oracle_layers/ladder_L1_L6.csv
  - L6: artifacts/formal/E2_oracle_layers/L6_per_sample_delta.csv
  - MLE anchor: artifacts/formal/shared_data/mle_anchor.csv

输出: artifacts/formal/figures/fig3_ladder.{svg,pdf,png}
      artifacts/formal/figures/fig4_l6_distribution.{svg,pdf,png}
"""

import os
import numpy as np
import pandas as pd

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

# ── 路径 ──
STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E2_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "E2_oracle_layers")
SHARED_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "shared_data")
FIG_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── 出版级 rcParams ──
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

# Okabe-Ito 色盲安全调色板
OKABE = {
    "orange": "#E69F00",
    "skyblue": "#56B4E9",
    "green": "#009E73",
    "yellow": "#F0E442",
    "blue": "#0072B2",
    "vermillion": "#D55E00",
    "pink": "#CC79A7",
    "black": "#333333",
    "gray": "#999999",
}

# 层级颜色：可部署=灰系，oracle=蓝系，hindsight=红
LAYER_COLORS = {
    "Default": OKABE["gray"],
    "L1": OKABE["gray"],
    "L3": OKABE["skyblue"],
    "L4": OKABE["blue"],
    "L5": OKABE["blue"],
    "L6": OKABE["vermillion"],
}

BETA_COLORS = {
    1.5: "#E69F00",
    2.0: "#56B4E9",
    2.5: "#009E73",
    4.0: "#0072B2",
    5.0: "#D55E00",
}

# ── 读取数据 ──
print("[fig3/4] 读取数据...")
ladder = pd.read_csv(os.path.join(E2_DIR, "ladder_L1_L6.csv"))
l6 = pd.read_csv(os.path.join(E2_DIR, "L6_per_sample_delta.csv"))

# MLE J₁（只算 converged）
print("[fig3/4] 计算 MLE 锚点...")
mle_df = pd.read_csv(os.path.join(SHARED_DIR, "mle_anchor.csv"))
mle_v = mle_df[mle_df["converged"]].copy()
mle_v["j1_sq"] = (
    ((mle_v["beta_hat"] - mle_v["beta"]) / mle_v["beta"]) ** 2
    + ((mle_v["eta_hat"] - mle_v["eta"]) / mle_v["eta"]) ** 2
    + ((mle_v["gamma_hat"] - mle_v["gamma"]) / mle_v["eta"]) ** 2
)
mle_fail_rate = 1 - mle_df["converged"].mean()
j1_mle = np.sqrt(mle_v["j1_sq"].mean())
print(f"  MLE J₁={j1_mle:.4f}, fail_rate={mle_fail_rate*100:.1f}%")


# ============================================================
# Figure 3: 阶梯收益
# ============================================================
print("[fig3] 绘制阶梯收益图...")

layers_order = ["Default", "L1", "L3", "L4", "L5", "L6"]
layer_labels = ["Default\n$\\delta$=0.1", "L1\n$\\delta^*$=0.08",
                "L3\nby $\\beta$", "L4\nby $\\beta$+$n$",
                "L5\nby $\\beta$+$\\gamma/\\eta$+$n$", "L6\nper-sample"]
j1_values = [ladder.loc[ladder["layer"] == l, "J1_global"].values[0] for l in layers_order]
improvements = [ladder.loc[ladder["layer"] == l, "improvement_vs_default_pct"].values[0]
                for l in layers_order]

fig3, (ax3a, ax3b) = plt.subplots(1, 2, figsize=(7.2, 3.0),
                                   gridspec_kw={"width_ratios": [3, 2]})

# ── Panel A: 阶梯柱状图 ──
colors = [LAYER_COLORS[l] for l in layers_order]
bars = ax3a.bar(range(len(layers_order)), j1_values, color=colors,
                edgecolor="white", linewidth=0.5, width=0.7, zorder=3)

# MLE 锚点水平线
ax3a.axhline(j1_mle, color=OKABE["pink"], linewidth=0.8, linestyle="--", zorder=2)
ax3a.text(len(layers_order) - 0.5, j1_mle + 0.02,
          f"MLE\n$J_1$={j1_mle:.2f}\n(fail {mle_fail_rate*100:.0f}%)",
          fontsize=5, color=OKABE["pink"], ha="center", va="bottom",
          fontstyle="italic")

# 标注每柱的 J₁ 值
for i, (bar, j1, imp) in enumerate(zip(bars, j1_values, improvements)):
    ax3a.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + 0.008,
              f"{j1:.3f}", ha="center", va="bottom", fontsize=5.5, fontweight="bold")
    if i > 0 and imp > 0.1:
        ax3a.text(bar.get_x() + bar.get_width() / 2, bar.get_height() / 2,
                  f"+{imp:.1f}%", ha="center", va="center", fontsize=5,
                  color="white", fontweight="bold")

# 边际收益箭头（只标大跳点）
for i in [2, 5]:  # L3, L6
    prev_j1 = j1_values[i - 1]
    curr_j1 = j1_values[i]
    mid_x = i - 0.5
    mid_y = (prev_j1 + curr_j1) / 2
    delta_imp = improvements[i] - improvements[i - 1]
    if delta_imp > 3:
        ax3a.annotate(f"+{delta_imp:.1f}%", xy=(mid_x, mid_y),
                      fontsize=5.5, color=OKABE["vermillion"], fontweight="bold",
                      ha="center")

ax3a.set_xticks(range(len(layers_order)))
ax3a.set_xticklabels(layer_labels, fontsize=5.5)
ax3a.set_ylabel("$J_1$ (global)")
ax3a.set_ylim(0, max(j1_mle, max(j1_values)) * 1.15)
ax3a.set_title("(a) Accuracy ladder: Default $\\to$ L6", fontweight="bold", loc="left")

# 图例
from matplotlib.patches import Patch
legend_elements = [
    Patch(facecolor=OKABE["gray"], label="Deployable (Default, L1)"),
    Patch(facecolor=OKABE["blue"], label="Oracle (L3–L5)"),
    Patch(facecolor=OKABE["vermillion"], label="Hindsight (L6)"),
]
ax3a.legend(handles=legend_elements, loc="upper right", fontsize=5)

# ── Panel B: 累积改善曲线 ──
ax3b.plot(range(len(layers_order)), improvements, "o-",
          color=OKABE["black"], markersize=4, linewidth=1.2, zorder=5)

# 填充
ax3b.fill_between(range(len(layers_order)), improvements, 0,
                   alpha=0.08, color=OKABE["blue"], zorder=1)

# 标注大跳点
for i in [2, 5]:
    ax3b.annotate(f"+{improvements[i]-improvements[i-1]:.1f}%",
                  xy=(i, improvements[i]),
                  xytext=(i, improvements[i] + 3),
                  fontsize=5.5, color=OKABE["vermillion"], fontweight="bold",
                  ha="center",
                  arrowprops=dict(arrowstyle="->", lw=0.8, color=OKABE["vermillion"]))

ax3b.set_xticks(range(len(layers_order)))
ax3b.set_xticklabels(["Def", "L1", "L3", "L4", "L5", "L6"], fontsize=6)
ax3b.set_ylabel("Cumulative improvement vs Default (%)")
ax3b.set_ylim(-1, 26)
ax3b.set_title("(b) Marginal returns diminish at L4–L5", fontweight="bold", loc="left")

# 标注边际递减区域
ax3b.axvspan(2.7, 4.3, alpha=0.06, color=OKABE["gray"], zorder=0)
ax3b.text(3.5, 1, "diminishing\nreturns", ha="center", fontsize=5,
          color=OKABE["gray"], fontstyle="italic")

fig3.tight_layout(pad=0.5, w_pad=1.5)
out3 = os.path.join(FIG_DIR, "fig3_ladder")
fig3.savefig(f"{out3}.svg", bbox_inches="tight")
fig3.savefig(f"{out3}.pdf", bbox_inches="tight")
fig3.savefig(f"{out3}.png", dpi=300, bbox_inches="tight")
print(f"  Saved: {out3}.{{svg,pdf,png}}")


# ============================================================
# Figure 4: L6 逐样本 δ* 分布
# ============================================================
print("[fig4] 绘制 L6 分布图...")

fig4, (ax4a, ax4b) = plt.subplots(1, 2, figsize=(7.2, 2.8),
                                   gridspec_kw={"width_ratios": [2, 3]})

# ── Panel A: 全样本直方图 ──
delta_vals = l6["delta_star_L6"].values
bins = np.linspace(-0.01, 0.51, 27)  # 对应 δ grid 26 点
ax4a.hist(delta_vals, bins=bins, color=OKABE["skyblue"], edgecolor="white",
          linewidth=0.3, zorder=3)

# 标注 δ=0 占比
pct_zero = (delta_vals == 0).mean() * 100
ax4a.annotate(f"$\\delta^*$ = 0\n({pct_zero:.1f}%)",
              xy=(0.01, ax4a.get_ylim()[1] * 0.85),
              fontsize=6, color=OKABE["vermillion"], fontweight="bold")

# Default 竖线
ax4a.axvline(0.10, color=OKABE["gray"], linewidth=0.6, linestyle=":")
ax4a.text(0.11, ax4a.get_ylim()[0] + 0.5, "Default=0.10", fontsize=5, color=OKABE["gray"])

ax4a.set_xlabel("Per-sample optimal $\\delta^*$ (L6 hindsight)")
ax4a.set_ylabel("Count")
ax4a.set_title("(a) Distribution of L6 optimal $\\delta^*$", fontweight="bold", loc="left")

# ── Panel B: 分 β 的 boxplot ──
beta_order = [1.5, 2.0, 2.5, 4.0, 5.0]
data_by_beta = [l6.loc[l6["beta"] == b, "delta_star_L6"].values for b in beta_order]

bp = ax4b.boxplot(data_by_beta, positions=range(len(beta_order)),
                   widths=0.5, patch_artist=True,
                   showfliers=False, zorder=3,
                   medianprops=dict(color="white", linewidth=1.2),
                   boxprops=dict(linewidth=0.5),
                   whiskerprops=dict(linewidth=0.5),
                   capprops=dict(linewidth=0.5))

for patch, beta_val in zip(bp["boxes"], beta_order):
    patch.set_facecolor(BETA_COLORS[beta_val])
    patch.set_alpha(0.7)

# 叠加散点（jitter）
for i, (beta_val, data) in enumerate(zip(beta_order, data_by_beta)):
    jitter = np.random.normal(i, 0.06, size=len(data))
    sample_idx = np.random.choice(len(data), size=min(200, len(data)), replace=False)
    ax4b.scatter(jitter[sample_idx], data[sample_idx],
                 color=BETA_COLORS[beta_val], s=1.5, alpha=0.3, zorder=4,
                 edgecolors="none")

ax4b.set_xticks(range(len(beta_order)))
ax4b.set_xticklabels([f"$\\beta$={b}" for b in beta_order], fontsize=6)
ax4b.set_xlabel("Shape parameter $\\beta$")
ax4b.set_ylabel("L6 optimal $\\delta^*$")
ax4b.set_ylim(-0.02, 0.55)

# Default 竖线（水平）
ax4b.axhline(0.10, color=OKABE["gray"], linewidth=0.5, linestyle=":", zorder=2)
ax4b.text(4.3, 0.11, "Default", fontsize=5, color=OKABE["gray"])

# 趋势标注
ax4b.annotate("", xy=(4, np.median(data_by_beta[4])),
              xytext=(0, np.median(data_by_beta[0])),
              arrowprops=dict(arrowstyle="->", lw=0.8,
                              color=OKABE["vermillion"], connectionstyle="arc3,rad=-0.2"))
ax4b.text(2, 0.42, "larger $\\beta$ $\\Rightarrow$ smaller $\\delta^*$",
          fontsize=5, color=OKABE["vermillion"], ha="center", fontstyle="italic")

ax4b.set_title("(b) $\\delta^*$ decreases with $\\beta$", fontweight="bold", loc="left")

fig4.tight_layout(pad=0.5, w_pad=1.5)
out4 = os.path.join(FIG_DIR, "fig4_l6_distribution")
fig4.savefig(f"{out4}.svg", bbox_inches="tight")
fig4.savefig(f"{out4}.pdf", bbox_inches="tight")
fig4.savefig(f"{out4}.png", dpi=300, bbox_inches="tight")
print(f"  Saved: {out4}.{{svg,pdf,png}}")

# ── QA ──
print("\n=== QA ===")
print("Figure 3:")
for l, j1, imp in zip(layers_order, j1_values, improvements):
    print(f"  {l}: J1={j1:.4f}, improvement={imp:.2f}%")
print(f"  MLE: J1={j1_mle:.4f}, fail_rate={mle_fail_rate*100:.1f}%")
print("\nFigure 4:")
print(f"  L6 total samples: {len(l6)}")
print(f"  δ*=0: {pct_zero:.1f}%")
for b in beta_order:
    sub = l6[l6["beta"] == b]["delta_star_L6"]
    print(f"  β={b}: median={sub.median():.2f}, mean={sub.mean():.3f}, IQR=[{sub.quantile(.25):.2f}, {sub.quantile(.75):.2f}]")
