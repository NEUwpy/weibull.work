"""
Figure 1: 六级信息层级框架 + 实验流程示意图

Schematic diagram showing:
- Left: L1-L6 hierarchy (deployable vs oracle vs hindsight)
- Right: E1-E4 experiment mapping + NN bridge

This is a concept figure, not data-driven.
"""

import os
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

# ── 路径 ──
STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIG_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── rcParams ──
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "font.size": 7,
    "axes.linewidth": 0.6,
})

# 颜色
C = {
    "deployable": "#E8E8E8",   # 浅灰：可部署
    "oracle": "#C8DBED",       # 浅蓝：oracle
    "hindsight": "#F5D5C5",    # 浅橙：hindsight
    "border_dep": "#666666",
    "border_ora": "#0072B2",
    "border_hin": "#D55E00",
    "arrow": "#333333",
    "nn_bridge": "#0072B2",
    "text": "#222222",
    "bg": "white",
}

fig, ax = plt.subplots(figsize=(7.2, 4.0))
ax.set_xlim(0, 10)
ax.set_ylim(0, 7)
ax.set_aspect("equal")
ax.axis("off")
fig.patch.set_facecolor(C["bg"])

# ────────────────── 左侧：六级层级 ──────────────────

layer_data = [
    # (y, label, info, type, j1, imp)
    (6.0, "L1", "Global constant $\\delta^*$\n(e.g. $\\delta$=0.08)", "dep", "0.633", "+0.05%"),
    (5.0, "L2", "By sample size $n$\n(lookup table)", "dep", "0.633", "+0.06%"),
    (4.0, "L3", "By shape $\\beta$\n$\\rightarrow$ requires NN", "ora", "0.585", "+7.6%"),
    (3.0, "L4", "By $\\beta$ + $n$\n$\\rightarrow$ requires NN", "ora", "0.582", "+8.1%"),
    (2.0, "L5", "By $\\beta$ + $\\gamma/\\eta$ + $n$\n$\\rightarrow$ requires NN", "ora", "0.571", "+9.8%"),
    (1.0, "L6", "Per-sample hindsight\n(upper bound, not deployable)", "hin", "0.495", "+21.9%"),
]

box_w, box_h = 3.8, 0.75
x_left = 0.5

for y, label, info, ltype, j1, imp in layer_data:
    if ltype == "dep":
        facecolor = C["deployable"]
        edgecolor = C["border_dep"]
    elif ltype == "ora":
        facecolor = C["oracle"]
        edgecolor = C["border_ora"]
    else:
        facecolor = C["hindsight"]
        edgecolor = C["border_hin"]

    # 主框
    box = FancyBboxPatch((x_left, y - box_h / 2), box_w, box_h,
                          boxstyle="round,pad=0.05",
                          facecolor=facecolor, edgecolor=edgecolor,
                          linewidth=0.8, zorder=2)
    ax.add_patch(box)

    # 层级标签（左）
    ax.text(x_left + 0.25, y, label, fontsize=8, fontweight="bold",
            va="center", ha="left", color=C["text"], zorder=3)

    # 描述
    ax.text(x_left + 0.85, y, info, fontsize=5.5,
            va="center", ha="left", color=C["text"], zorder=3)

    # J₁ 和改善（右端）
    ax.text(x_left + box_w - 0.15, y + 0.12, f"$J_1$={j1}",
            fontsize=5, va="center", ha="right", color="#444444", zorder=3)
    ax.text(x_left + box_w - 0.15, y - 0.15, imp,
            fontsize=5, va="center", ha="right",
            color=C["border_hin"] if float(imp.strip("+%")) > 5 else "#666666",
            fontweight="bold" if float(imp.strip("+%")) > 5 else "normal",
            zorder=3)

# 层级之间的箭头
for i in range(len(layer_data) - 1):
    y_top = layer_data[i][0] - box_h / 2
    y_bot = layer_data[i + 1][0] + box_h / 2
    ax.annotate("", xy=(x_left + box_w / 2, y_bot),
                xytext=(x_left + box_w / 2, y_top),
                arrowprops=dict(arrowstyle="->", lw=0.6, color=C["arrow"]))

# ── 分组标注（右侧竖线+标签）──

# Deployable 区
ax.annotate("", xy=(x_left + box_w + 0.3, 6.0 + box_h / 2),
            xytext=(x_left + box_w + 0.3, 5.0 - box_h / 2),
            arrowprops=dict(arrowstyle="-", lw=1.2, color=C["border_dep"]))
ax.text(x_left + box_w + 0.45, 5.5, "Deployable\n(L1–L2)",
        fontsize=5.5, color=C["border_dep"], fontweight="bold",
        rotation=90, va="center", ha="left")

# Oracle 区
ax.annotate("", xy=(x_left + box_w + 0.3, 4.0 + box_h / 2),
            xytext=(x_left + box_w + 0.3, 2.0 - box_h / 2),
            arrowprops=dict(arrowstyle="-", lw=1.2, color=C["border_ora"]))
ax.text(x_left + box_w + 0.45, 3.0, "Oracle\n(L3–L5)",
        fontsize=5.5, color=C["border_ora"], fontweight="bold",
        rotation=90, va="center", ha="left")

# Hindsight 区
ax.annotate("", xy=(x_left + box_w + 0.3, 1.0 + box_h / 2),
            xytext=(x_left + box_w + 0.3, 1.0 - box_h / 2),
            arrowprops=dict(arrowstyle="-", lw=1.2, color=C["border_hin"]))
ax.text(x_left + box_w + 0.45, 1.0, "Hindsight\n(L6)",
        fontsize=5.5, color=C["border_hin"], fontweight="bold",
        rotation=90, va="center", ha="left")


# ────────────────── 右侧：实验映射 + NN bridge ──────────────────

x_right = 5.5
right_w = 3.8

# 标题
ax.text(x_right + right_w / 2, 6.7, "Experiments", fontsize=7,
        fontweight="bold", ha="center", color=C["text"])

# E1/E2/E3/E4 框
exp_data = [
    (5.8, "E1: $\\delta$ scan", "Default / L1 / L2\n(Ch.4)", "#E8E8E8"),
    (4.3, "E2: Oracle layers", "L3 / L4 / L5 / L6\n(Ch.5)", "#C8DBED"),
    (2.8, "E3: NN mapping", "Sample $\\to$ $\\delta^*$\n(Ch.6)", "#D4E8D4"),
    (1.3, "E4: Robustness", "Cross-parameter\n(Ch.7)", "#F0F0E8"),
]

for y, title, desc, color in exp_data:
    box = FancyBboxPatch((x_right, y - 0.4), right_w, 0.8,
                          boxstyle="round,pad=0.05",
                          facecolor=color, edgecolor="#666666",
                          linewidth=0.6, zorder=2)
    ax.add_patch(box)
    ax.text(x_right + 0.2, y + 0.1, title, fontsize=6.5, fontweight="bold",
            va="center", ha="left", color=C["text"], zorder=3)
    ax.text(x_right + 0.2, y - 0.18, desc, fontsize=5,
            va="center", ha="left", color="#555555", zorder=3)

# 连接线：层级→实验
# L1-L2 → E1
ax.annotate("", xy=(x_right, 5.8), xytext=(x_left + box_w + 0.8, 5.5),
            arrowprops=dict(arrowstyle="->", lw=0.5, color=C["arrow"],
                            connectionstyle="arc3,rad=0.1"))
# L3-L6 → E2
ax.annotate("", xy=(x_right, 4.3), xytext=(x_left + box_w + 0.8, 3.0),
            arrowprops=dict(arrowstyle="->", lw=0.5, color=C["arrow"],
                            connectionstyle="arc3,rad=0.1"))

# NN bridge: E2 oracle → E3 NN（虚线，表示NN学习oracle的映射）
bridge = FancyArrowPatch((x_right + right_w / 2, 4.3 - 0.4),
                          (x_right + right_w / 2, 2.8 + 0.4),
                          arrowstyle="->", lw=1.2,
                          color=C["nn_bridge"], linestyle="--",
                          connectionstyle="arc3,rad=0")
ax.add_patch(bridge)
ax.text(x_right + right_w / 2 + 0.15, (4.3 + 2.8) / 2,
        "NN learns\nsample $\\to \\delta^*$\n(bridging\noracle $\\to$\ndeployable)",
        fontsize=4.8, color=C["nn_bridge"], fontstyle="italic",
        va="center", ha="left")

# Default 基线标注
ax.text(x_left + 0.25, 6.7, "$\\delta$=0.1 baseline",
        fontsize=5.5, color=C["border_hin"], fontstyle="italic")

# ── 保存 ──
out = os.path.join(FIG_DIR, "fig1_framework")
fig.savefig(f"{out}.svg", bbox_inches="tight", facecolor=C["bg"])
fig.savefig(f"{out}.pdf", bbox_inches="tight", facecolor=C["bg"])
fig.savefig(f"{out}.png", dpi=300, bbox_inches="tight", facecolor=C["bg"])
print(f"Saved: {out}.{{svg,pdf,png}}")
