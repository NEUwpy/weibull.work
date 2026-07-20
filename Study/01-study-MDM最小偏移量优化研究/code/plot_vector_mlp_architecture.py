"""Draw a publication-style FCNN diagram for the Vector-MLP.

The visual convention follows classic FCNN node-link diagrams such as NN-SVG,
while the layout and annotations here are implemented specifically for Study01.
"""

from pathlib import Path

import matplotlib.pyplot as plt


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


def representative_positions():
    """Six visible neurons with a central omission marker."""
    return [0.20, 0.30, 0.40, 0.60, 0.70, 0.80]


def draw_ellipsis(ax, x, center=0.50):
    ax.scatter(
        [x, x, x],
        [center - 0.022, center, center + 0.022],
        s=8,
        color="#5B5B5B",
        edgecolors="none",
        zorder=5,
    )


fig, ax = plt.subplots(figsize=(14.5, 7.6))
ax.set_xlim(0.00, 1.00)
ax.set_ylim(0.04, 0.96)
ax.axis("off")

input_x = 0.23
hidden_x = [0.42, 0.57, 0.72]
output_x = 0.87

input_y = [0.14 + i * (0.72 / 12) for i in range(13)]
hidden_y = representative_positions()
output_y = representative_positions()

input_labels = [
    r"$n$",
    r"$x_{\min}$",
    r"$x_{\max}$",
    r"$range$",
    r"$Q_1$",
    r"$Med$",
    r"$Q_3$",
    r"$IQR$",
    r"$\bar{x}$",
    r"$s$",
    r"$CV$",
    r"$g_1$",
    r"$g_2$",
]
output_labels = [
    r"$\widehat{L}(0.00)$",
    r"$\widehat{L}(0.02)$",
    r"$\widehat{L}(0.04)$",
    r"$\widehat{L}(0.46)$",
    r"$\widehat{L}(0.48)$",
    r"$\widehat{L}(0.50)$",
]

# Connections are deliberately light so the network remains readable in print.
layer_positions = [(input_x, input_y)] + [(x, hidden_y) for x in hidden_x] + [(output_x, output_y)]
for (x1, ys1), (x2, ys2) in zip(layer_positions[:-1], layer_positions[1:]):
    for y1 in ys1:
        for y2 in ys2:
            ax.plot(
                [x1, x2],
                [y1, y2],
                color="#707070",
                linewidth=0.45,
                alpha=0.13,
                zorder=1,
            )

node_size = 205
ax.scatter(
    [input_x] * len(input_y),
    input_y,
    s=node_size,
    facecolors="#EAF3F8",
    edgecolors="#0072B2",
    linewidths=1.8,
    zorder=4,
)
for x in hidden_x:
    ax.scatter(
        [x] * len(hidden_y),
        hidden_y,
        s=node_size,
        facecolors="white",
        edgecolors="#505050",
        linewidths=1.5,
        zorder=4,
    )
    draw_ellipsis(ax, x)
ax.scatter(
    [output_x] * len(output_y),
    output_y,
    s=node_size,
    facecolors="#FFF4DD",
    edgecolors="#E69F00",
    linewidths=1.8,
    zorder=4,
)
draw_ellipsis(ax, output_x)

# Explicit input and output meanings.
for y, label in zip(input_y, input_labels):
    ax.text(input_x - 0.027, y, label, ha="right", va="center", fontsize=11.5, color="#222222")
for y, label in zip(output_y, output_labels):
    ax.text(output_x + 0.027, y, label, ha="left", va="center", fontsize=11.5, color="#222222")

headers = [
    (input_x, "输入层", "13个样本统计特征"),
    (hidden_x[0], "隐藏层 1", "256个神经元 · ReLU"),
    (hidden_x[1], "隐藏层 2", "128个神经元 · ReLU"),
    (hidden_x[2], "隐藏层 3", "64个神经元 · ReLU"),
    (output_x, "输出层", "26点预测损失曲线"),
]
for x, title, subtitle in headers:
    ax.text(x, 0.925, title, ha="center", va="center", fontsize=14.5, weight="bold", color="#202020")
    ax.text(x, 0.885, subtitle, ha="center", va="center", fontsize=10.8, color="#555555")

ax.annotate(
    r"$\widehat{\delta}=\arg\min_{\delta}\widehat{L}(\delta)$",
    xy=(output_x, 0.115),
    xytext=(output_x, 0.065),
    ha="center",
    va="center",
    fontsize=12.5,
    color="#007A5E",
    arrowprops={"arrowstyle": "-|>", "color": "#007A5E", "linewidth": 1.2},
)

fig.tight_layout(pad=0.2)
for suffix in ("png", "svg", "pdf"):
    path = OUT_DIR / f"fig_vector_mlp_architecture.{suffix}"
    kwargs = {"bbox_inches": "tight", "facecolor": "white"}
    if suffix == "png":
        kwargs["dpi"] = 300
    fig.savefig(path, **kwargs)
plt.close(fig)

