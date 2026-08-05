"""
E04 MLP Architecture Diagram
"""
import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from pathlib import Path

BASE = Path(r"C:\Web\Weibull\docs\research\04基于神经网络的MDM偏移量自适应选取")
IMG_DIR = BASE / "图像"

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "font.size": 9,
})


def draw_box(ax, x, y, w, h, text, color, alpha=1.0, fontsize=9, text_color="white"):
    rect = mpatches.FancyBboxPatch(
        (x, y), w, h, boxstyle="round,pad=0.15",
        facecolor=color, edgecolor="#333", linewidth=0.8, alpha=alpha
    )
    ax.add_patch(rect)
    ax.text(x + w / 2, y + h / 2, text, ha="center", va="center",
            fontsize=fontsize, fontweight="bold", color=text_color)


def draw_arrow(ax, x1, y1, x2, y2):
    ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                arrowprops=dict(arrowstyle="-|>", color="#555", lw=1.2))


fig, ax = plt.subplots(figsize=(9, 4.5))
ax.set_xlim(-0.5, 9.5)
ax.set_ylim(-0.5, 5)
ax.set_aspect("equal")
ax.axis("off")

col = [0.3, 2.2, 4.1, 6.0, 7.9]

c_input = "#4CAF50"
c_hidden = "#2196F3"
c_output = "#FF9800"

draw_box(ax, col[0], 1.5, 1.3, 1.8, "Input\n10", c_input, fontsize=10)

draw_box(ax, col[1], 1.7, 1.3, 1.4, "256", c_hidden, fontsize=12)
ax.text(col[1] + 0.65, 1.5, "BN > ReLU > Drop", ha="center", va="top",
        fontsize=7, color="#666", style="italic")

draw_box(ax, col[2], 1.9, 1.3, 1.0, "128", c_hidden, fontsize=12)
ax.text(col[2] + 0.65, 1.7, "BN > ReLU > Drop", ha="center", va="top",
        fontsize=7, color="#666", style="italic")

draw_box(ax, col[3], 2.1, 1.3, 0.7, "64", c_hidden, fontsize=12)
ax.text(col[3] + 0.65, 1.9, "BN > ReLU > Drop", ha="center", va="top",
        fontsize=7, color="#666", style="italic")

draw_box(ax, col[4], 1.5, 1.3, 1.8, "Output\nK", c_output, fontsize=10)

for i in range(4):
    x1 = col[i] + 1.3
    x2 = col[i + 1]
    y_mid = 2.4
    draw_arrow(ax, x1, y_mid, x2, y_mid)

ax.text(col[0] + 0.65, 3.7, "sample features\n(10-dim, z-score)", ha="center", va="center",
        fontsize=8, color="#333",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#E8F5E9", edgecolor="#4CAF50", linewidth=0.8))
ax.annotate("", xy=(col[0] + 0.65, 3.3), xytext=(col[0] + 0.65, 3.55),
            arrowprops=dict(arrowstyle="-|>", color="#4CAF50", lw=1))

ax.text(9.0, 3.5, "L4/L5 hard\nK=1 (delta)", ha="center", va="center",
        fontsize=8, color="#333",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFF3E0", edgecolor="#FF9800", linewidth=0.8))
ax.text(9.0, 2.0, "Risk curve\nK=26 (loss)", ha="center", va="center",
        fontsize=8, color="#333",
        bbox=dict(boxstyle="round,pad=0.3", facecolor="#FFF3E0", edgecolor="#FF9800", linewidth=0.8))
ax.annotate("", xy=(8.55, 3.5), xytext=(8.3, 2.9),
            arrowprops=dict(arrowstyle="-|>", color="#FF9800", lw=1, connectionstyle="arc3,rad=0.2"))
ax.annotate("", xy=(8.55, 2.0), xytext=(8.3, 2.2),
            arrowprops=dict(arrowstyle="-|>", color="#FF9800", lw=1, connectionstyle="arc3,rad=-0.2"))

labels = ["Input", "Hidden 1", "Hidden 2", "Hidden 3", "Output"]
for i, label in enumerate(labels):
    ax.text(col[i] + 0.65, 0.8, label, ha="center", va="center",
            fontsize=8, color="#666", fontweight="bold")

ax.annotate("", xy=(col[3] + 0.65, 0.4), xytext=(col[1] + 0.65, 0.4),
            arrowprops=dict(arrowstyle="<|-|>", color="#999", lw=1))
ax.text((col[1] + col[3]) / 2 + 0.65, 0.2, "width decreasing", ha="center", va="center",
        fontsize=7, color="#999")

fig.suptitle("MLP Architecture (Delta Prediction Network)", fontsize=12, fontweight="bold", y=0.98)
fig.tight_layout(rect=[0, 0, 1, 0.95])

for ext, dpi in [('.png', 300), ('.pdf', None), ('.svg', None)]:
    fig.savefig(IMG_DIR / f"E04_MLP_architecture{ext}", bbox_inches='tight', dpi=dpi)
plt.close(fig)
print("Done.")
