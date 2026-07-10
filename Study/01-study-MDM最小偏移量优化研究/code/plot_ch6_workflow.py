"""Figure 8: deployable E3b vector-output MLP workflow.

The figure explains method semantics only. Quantitative comparisons remain in
Table 5, while the former pooled-J1 bar chart is retained as supplementary
diagnostic material.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch


STUDY_DIR = Path(__file__).resolve().parents[1]
FIG_DIR = STUDY_DIR / "artifacts" / "formal" / "figures"

mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "font.size": 7,
})


COLORS = {
    "text": "#222222",
    "muted": "#666666",
    "line": "#6F7782",
    "input_fill": "#E8EEF3",
    "input_edge": "#4C78A8",
    "model_fill": "#E1F0E2",
    "model_edge": "#2E7D32",
    "offline_fill": "#F9E9DD",
    "offline_edge": "#D55E00",
    "warning_fill": "#F8EEEE",
    "warning_edge": "#A64B4B",
}


def build_workflow_spec():
    """Return the semantic contract that drives the workflow figure."""
    return {
        "deployable_inputs": [
            "n",
            "x_(1)",
            "x_(n)",
            "range",
            "Q1",
            "median",
            "Q3",
            "IQR",
            "mean",
            "sd",
            "CV",
            "g1",
            "g2",
        ],
        "excluded_inputs": [
            "true beta",
            "true gamma/eta",
            "configuration ID",
            "seed",
            "repeat_id",
            "candidate delta",
        ],
        "model": "vector-output MLP",
        "hidden_layers": [256, 128, 64],
        "output_dimensions": 26,
        "delta_grid": {"min": 0.0, "max": 0.5, "step": 0.02},
        "selection": "argmin predicted loss",
        "training_label": "raw per-sample 26-point loss curve",
        "evaluation": "true selected-loss aggregated as J1",
        "split": "5-fold full-combination holdout",
    }


def _rounded_box(ax, x, y, width, height, facecolor, edgecolor, linewidth=1.0):
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.035,rounding_size=0.08",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
    )
    ax.add_patch(box)
    return box


def _arrow(ax, start, end, color, linestyle="-", linewidth=1.0, connectionstyle="arc3"):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "-|>",
            "color": color,
            "linestyle": linestyle,
            "linewidth": linewidth,
            "mutation_scale": 9,
            "shrinkA": 1,
            "shrinkB": 1,
            "connectionstyle": connectionstyle,
        },
    )


def _step_badge(ax, number, x, y, color):
    badge = Circle(
        (x, y),
        0.15,
        facecolor=color,
        edgecolor="white",
        linewidth=0.7,
        clip_on=False,
    )
    ax.add_patch(badge)
    ax.text(x, y, str(number), color="white", fontsize=6, fontweight="bold",
            ha="center", va="center")


def _draw_vector_glyph(ax, x, y, width, height, count=13):
    """Draw an abstract vector glyph without implying a measured curve."""
    gap = width * 0.018
    cell_width = (width - gap * (count - 1)) / count
    for index in range(count):
        alpha = 0.22 + 0.58 * (index / max(count - 1, 1))
        rect = FancyBboxPatch(
            (x + index * (cell_width + gap), y),
            cell_width,
            height,
            boxstyle="round,pad=0.002,rounding_size=0.01",
            facecolor=COLORS["model_edge"],
            edgecolor="none",
            alpha=alpha,
        )
        ax.add_patch(rect)


def plot_workflow(spec=None, save=True):
    """Draw the Ch6 workflow and optionally export SVG/PDF/PNG."""
    spec = build_workflow_spec() if spec is None else spec

    fig, ax = plt.subplots(figsize=(7.2, 3.22))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 6.2)
    ax.axis("off")

    ax.text(0.30, 5.86, "DEPLOYABLE INFERENCE", fontsize=7.5, fontweight="bold",
            color=COLORS["model_edge"], va="center")
    ax.plot([2.13, 11.70], [5.86, 5.86], color=COLORS["model_edge"],
            linewidth=0.7, alpha=0.45)

    node_y = 3.55
    node_h = 1.55
    node_w = 1.82
    node_x = [0.30, 2.72, 5.14, 7.56, 9.98]
    node_styles = [
        (COLORS["input_fill"], COLORS["input_edge"]),
        (COLORS["input_fill"], COLORS["input_edge"]),
        (COLORS["model_fill"], COLORS["model_edge"]),
        (COLORS["model_fill"], COLORS["model_edge"]),
        (COLORS["model_fill"], COLORS["model_edge"]),
    ]

    for x, (fill, edge) in zip(node_x, node_styles):
        _rounded_box(ax, x, node_y, node_w, node_h, fill, edge, linewidth=1.0)

    centers = [x + node_w / 2 for x in node_x]
    for index in range(len(node_x) - 1):
        _arrow(
            ax,
            (node_x[index] + node_w + 0.05, node_y + node_h / 2),
            (node_x[index + 1] - 0.05, node_y + node_h / 2),
            COLORS["line"],
        )

    for index, (x, (_, edge)) in enumerate(zip(node_x, node_styles), start=1):
        _step_badge(ax, index, x + 0.10, node_y + node_h + 0.02, edge)

    ax.text(centers[0], 4.68, "New lifetime sample", fontsize=7.1,
            fontweight="bold", ha="center", va="center", color=COLORS["text"])
    ax.text(centers[0], 4.27, r"$x_{(1)},\ldots,x_{(n)}$", fontsize=7.2,
            ha="center", va="center", color=COLORS["text"])
    ax.text(centers[0], 3.86, r"observed $n$", fontsize=5.5,
            ha="center", va="center", color=COLORS["muted"])

    ax.text(centers[1], 4.68, "13 observable features", fontsize=7.0,
            fontweight="bold", ha="center", va="center", color=COLORS["text"])
    ax.text(centers[1], 4.25, "order statistics · quantiles", fontsize=5.2,
            ha="center", va="center", color=COLORS["text"])
    ax.text(centers[1], 3.91, "scale · dispersion · shape", fontsize=5.2,
            ha="center", va="center", color=COLORS["muted"])

    ax.text(centers[2], 4.72, "Vector-output MLP", fontsize=7.1,
            fontweight="bold", ha="center", va="center", color=COLORS["text"])
    ax.text(centers[2], 4.29, "13 → 256 → 128 → 64 → 26", fontsize=5.7,
            ha="center", va="center", color=COLORS["text"])
    ax.text(centers[2], 3.88, r"no candidate $\delta$ input", fontsize=5.5,
            ha="center", va="center", color=COLORS["model_edge"],
            fontweight="bold")

    ax.text(centers[3], 4.75, "Predicted loss vector", fontsize=7.0,
            fontweight="bold", ha="center", va="center", color=COLORS["text"])
    _draw_vector_glyph(ax, node_x[3] + 0.24, 4.18, node_w - 0.48, 0.18)
    ax.text(centers[3], 3.87,
            r"$\hat{\ell}_i(\delta_0),\ldots,\hat{\ell}_i(\delta_{25})$",
            fontsize=5.3, ha="center", va="center", color=COLORS["muted"])

    ax.text(centers[4], 4.72, "Select offset", fontsize=7.1,
            fontweight="bold", ha="center", va="center", color=COLORS["text"])
    ax.text(centers[4], 4.29,
            r"$\hat{\delta}_i=\arg\min_{\delta_j}\hat{\ell}_i(\delta_j)$",
            fontsize=5.9, ha="center", va="center", color=COLORS["text"])
    ax.text(centers[4], 3.87, r"$\delta_j=0.02j,\ j=0,\ldots,25$",
            fontsize=5.3, ha="center", va="center", color=COLORS["muted"])

    ax.text(0.30, 2.72, "OFFLINE TRAINING AND EVALUATION", fontsize=7.2,
            fontweight="bold", color=COLORS["offline_edge"], va="center")
    ax.plot([3.14, 11.70], [2.72, 2.72], color=COLORS["offline_edge"],
            linewidth=0.7, alpha=0.42)

    train_x, train_y, train_w, train_h = 1.15, 0.72, 5.05, 1.35
    _rounded_box(ax, train_x, train_y, train_w, train_h,
                 COLORS["offline_fill"], COLORS["offline_edge"], linewidth=0.9)
    ax.text(train_x + 0.22, train_y + 1.02, "Training labels (formal MC only)",
            fontsize=6.5, fontweight="bold", color=COLORS["text"], va="center")
    ax.text(train_x + 0.22, train_y + 0.61,
            r"raw per-sample vector $[\ell_i(\delta_0),\ldots,\ell_i(\delta_{25})]$",
            fontsize=5.4, color=COLORS["text"], va="center")
    ax.text(train_x + 0.22, train_y + 0.25,
            spec["split"], fontsize=5.2, color=COLORS["muted"], va="center")
    _arrow(
        ax,
        (train_x + train_w - 0.38, train_y + train_h + 0.04),
        (centers[2] - 0.18, node_y - 0.05),
        COLORS["offline_edge"],
        linestyle="--",
        linewidth=0.9,
        connectionstyle="arc3,rad=-0.12",
    )
    ax.text(5.73, 2.91, "fit targets", fontsize=4.9,
            color=COLORS["offline_edge"], ha="center", va="center")

    eval_x, eval_y, eval_w, eval_h = 7.08, 0.72, 4.62, 1.35
    _rounded_box(ax, eval_x, eval_y, eval_w, eval_h,
                 COLORS["offline_fill"], COLORS["offline_edge"], linewidth=0.9)
    ax.text(eval_x + 0.22, eval_y + 1.02, "Evaluation only — not a deployment input",
            fontsize=6.3, fontweight="bold", color=COLORS["text"], va="center")
    ax.text(eval_x + 0.22, eval_y + 0.61,
            r"run MDM at $\hat{\delta}_i$ → true selected-loss $\ell_i(\hat{\delta}_i)$",
            fontsize=5.2, color=COLORS["text"], va="center")
    ax.text(eval_x + 0.22, eval_y + 0.25,
            r"aggregate after selection: $J_1=\sqrt{\operatorname{mean}_i\ell_i(\hat{\delta}_i)}$",
            fontsize=5.2, color=COLORS["muted"], va="center")
    _arrow(
        ax,
        (centers[4], node_y - 0.05),
        (eval_x + eval_w - 0.62, eval_y + eval_h + 0.04),
        COLORS["offline_edge"],
        linestyle="--",
        linewidth=0.9,
        connectionstyle="arc3,rad=0.08",
    )

    warning_text = (
        "Excluded from model input: true β · true γ/η · configuration ID · seed · "
        "repeat_id · candidate δ"
    )
    _rounded_box(ax, 0.30, 2.16, 11.40, 0.34,
                 COLORS["warning_fill"], COLORS["warning_edge"], linewidth=0.55)
    ax.text(6.00, 2.33, warning_text, fontsize=5.1, color=COLORS["warning_edge"],
            ha="center", va="center")

    fig.subplots_adjust(left=0.018, right=0.992, top=0.99, bottom=0.02)
    if save:
        FIG_DIR.mkdir(parents=True, exist_ok=True)
        out = FIG_DIR / "fig_ch6_vector_mlp_workflow"
        fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
        fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
        fig.savefig(out.with_suffix(".png"), dpi=300, bbox_inches="tight")
        print("Saved fig_ch6_vector_mlp_workflow.{svg,pdf,png}")
    return fig


if __name__ == "__main__":
    figure = plot_workflow()
    plt.close(figure)
