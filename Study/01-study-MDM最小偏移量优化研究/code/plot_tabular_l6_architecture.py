"""Draw a simple publication-style regression-tree schematic."""

from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "260720汇报" / "assets"
OUT_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "svg.fonttype": "none",
    }
)

INK = "#2B2B2B"
GREY = "#6A747A"
LIGHT = "#C8D1D6"
BLUE = "#0072B2"
ORANGE = "#E69F00"
GREEN = "#009E73"


def rounded_node(ax, xy, text, width=0.16, height=0.085, edge=BLUE, face="#F4FAFD", fontsize=12):
    x, y = xy
    patch = FancyBboxPatch(
        (x - width / 2, y - height / 2),
        width,
        height,
        boxstyle="round,pad=0.012,rounding_size=0.018",
        linewidth=1.8,
        edgecolor=edge,
        facecolor=face,
        zorder=4,
    )
    ax.add_patch(patch)
    ax.text(x, y, text, ha="center", va="center", fontsize=fontsize, color=INK, zorder=5)


def branch(ax, parent, child, label, highlight=False):
    color = GREEN if highlight else LIGHT
    linewidth = 2.5 if highlight else 1.8
    ax.plot([parent[0], child[0]], [parent[1] - 0.048, child[1] + 0.048], color=color, linewidth=linewidth, zorder=1)
    xm = parent[0] * 0.55 + child[0] * 0.45
    ym = (parent[1] + child[1]) / 2 + 0.012
    ax.text(xm, ym, label, ha="center", va="center", fontsize=10.5, color=GREEN if highlight else GREY)


fig, ax = plt.subplots(figsize=(11.5, 6.0))
ax.set_xlim(0.04, 0.96)
ax.set_ylim(0.08, 0.92)
ax.axis("off")

ax.text(0.50, 0.87, "一棵回归树如何得到预测值", ha="center", va="center", fontsize=17, weight="bold", color=INK)
ax.text(0.50, 0.815, "按照特征阈值逐层分支，最终落入一个叶节点", ha="center", va="center", fontsize=11.5, color=GREY)

root = (0.50, 0.70)
left = (0.31, 0.49)
right = (0.69, 0.49)
leaves = [(0.19, 0.25), (0.39, 0.25), (0.61, 0.25), (0.81, 0.25)]

branch(ax, root, left, "是", highlight=True)
branch(ax, root, right, "否")
branch(ax, left, leaves[0], "是")
branch(ax, left, leaves[1], "否", highlight=True)
branch(ax, right, leaves[2], "是")
branch(ax, right, leaves[3], "否")

rounded_node(ax, root, r"特征 $x_k\leq c_1$？", width=0.19)
rounded_node(ax, left, r"特征 $x_l\leq c_2$？", width=0.19)
rounded_node(ax, right, r"特征 $x_r\leq c_3$？", width=0.19)

for index, (xy, value) in enumerate(zip(leaves, [r"$v_1$", r"$v_2$", r"$v_3$", r"$v_4$"])):
    selected = index == 1
    rounded_node(
        ax,
        xy,
        "预测值\n" + value,
        width=0.135,
        height=0.10,
        edge=GREEN if selected else ORANGE,
        face="#EAF7F3" if selected else "#FFF7E7",
        fontsize=12,
    )

ax.text(0.39, 0.135, "该样本的分支路径", ha="center", va="center", fontsize=10.5, color=GREEN)
ax.annotate(
    "",
    xy=(0.39, 0.19),
    xytext=(0.39, 0.155),
    arrowprops=dict(arrowstyle="-|>", color=GREEN, lw=1.5),
)

ax.text(
    0.50,
    0.075,
    "梯度提升模型由多棵这样的回归树依次叠加，后加入的树继续修正前面的预测误差",
    ha="center",
    va="center",
    fontsize=11,
    color=GREY,
)

fig.tight_layout(pad=0.35)
for suffix in ("png", "svg", "pdf"):
    path = OUT_DIR / f"fig_tabular_l6_architecture.{suffix}"
    kwargs = {"bbox_inches": "tight", "facecolor": "white"}
    if suffix == "png":
        kwargs["dpi"] = 300
    fig.savefig(path, **kwargs)
plt.close(fig)
