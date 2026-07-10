"""Figure 2: information hierarchy and final manuscript validation roadmap.

The figure is intentionally result-free. Table 1 remains the authoritative
contract for exact definitions and anti-misreading boundaries; this figure only
provides the visual logic linking L1-L6 to E1-E4 and real-data validation.
"""

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch


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
    "line": "#777777",
    "baseline_fill": "#F1F1F1",
    "baseline_edge": "#777777",
    "deployable_fill": "#E8EEF3",
    "deployable_edge": "#4C78A8",
    "oracle_fill": "#DCEAF5",
    "oracle_edge": "#0072B2",
    "hindsight_fill": "#F9E3D3",
    "hindsight_edge": "#D55E00",
    "adaptive_fill": "#E1F0E2",
    "adaptive_edge": "#2E7D32",
    "validation_fill": "#F3F0E8",
}


def build_framework_spec():
    """Return the result-free semantic contract that drives Figure 2."""
    return {
        "layers": [
            {
                "id": "Default",
                "kind": "baseline",
                "available_information": "none",
                "decision": "fixed delta = 0.1",
            },
            {
                "id": "L1",
                "kind": "deployable",
                "available_information": "none",
                "decision": "one global delta",
            },
            {
                "id": "L2",
                "kind": "deployable",
                "available_information": "sample size n",
                "decision": "lookup by n",
            },
            {
                "id": "L3",
                "kind": "oracle reference",
                "available_information": "true beta",
                "decision": "lookup by beta",
            },
            {
                "id": "L4",
                "kind": "oracle reference",
                "available_information": "true beta + n",
                "decision": "lookup by beta and n",
            },
            {
                "id": "L5",
                "kind": "oracle reference",
                "available_information": "true beta + true gamma/eta + n",
                "decision": "lookup by parameter condition",
            },
            {
                "id": "L6",
                "kind": "hindsight benchmark",
                "available_information": "per-sample post hoc loss",
                "decision": "grid argmin for each sample",
            },
        ],
        "adaptive_bridge": [
            "observable sample features",
            "26-point risk curve",
            "selected delta",
        ],
        "validation_path": [
            {
                "id": "E1",
                "title": "Simple deployable layers",
                "scope": "Default / L1 / L2",
            },
            {
                "id": "E2",
                "title": "Oracle and hindsight references",
                "scope": "L3 / L4 / L5 / L6",
            },
            {
                "id": "E3",
                "title": "Sample-adaptive selection",
                "scope": "vector-output neural network",
            },
            {
                "id": "E4",
                "title": "Robustness and boundaries",
                "scope": "cross-parameter validation",
            },
            {
                "id": "Real data",
                "title": "External applicability",
                "scope": "repeated small-sample holdout",
            },
        ],
    }


def _rounded_box(ax, x, y, width, height, facecolor, edgecolor, linewidth=1.0):
    box = FancyBboxPatch(
        (x, y),
        width,
        height,
        boxstyle="round,pad=0.025,rounding_size=0.08",
        facecolor=facecolor,
        edgecolor=edgecolor,
        linewidth=linewidth,
    )
    ax.add_patch(box)
    return box


def _layer_style(kind):
    if kind == "baseline":
        return COLORS["baseline_fill"], COLORS["baseline_edge"]
    if kind == "deployable":
        return COLORS["deployable_fill"], COLORS["deployable_edge"]
    if kind == "oracle reference":
        return COLORS["oracle_fill"], COLORS["oracle_edge"]
    return COLORS["hindsight_fill"], COLORS["hindsight_edge"]


def _draw_layer(ax, layer, x, y, width=4.65, height=0.72):
    fill, edge = _layer_style(layer["kind"])
    _rounded_box(ax, x, y, width, height, fill, edge)
    ax.text(
        x + 0.22,
        y + height / 2,
        layer["id"],
        fontsize=8,
        fontweight="bold",
        color=COLORS["text"],
        va="center",
    )
    ax.text(
        x + 1.18,
        y + 0.47,
        layer["decision"],
        fontsize=6.2,
        color=COLORS["text"],
        va="center",
    )
    ax.text(
        x + 1.18,
        y + 0.22,
        f"Information: {layer['available_information']}",
        fontsize=5.2,
        color=COLORS["muted"],
        va="center",
    )


def _draw_group_bracket(ax, x, y0, y1, label, color):
    ax.plot([x, x], [y0, y1], color=color, linewidth=2.0, solid_capstyle="round")
    ax.text(
        x + 0.15,
        (y0 + y1) / 2,
        label,
        color=color,
        fontsize=5.8,
        fontweight="bold",
        rotation=90,
        va="center",
        ha="left",
    )


def _draw_validation_box(ax, item, x, y, width=5.05, height=0.9, adaptive=False):
    fill = COLORS["adaptive_fill"] if adaptive else COLORS["validation_fill"]
    edge = COLORS["adaptive_edge"] if adaptive else COLORS["line"]
    _rounded_box(ax, x, y, width, height, fill, edge, linewidth=1.1)
    title_x = x + (1.35 if item["id"] == "Real data" else 0.82)
    title_y = y + (height * 0.70 if adaptive else height * 0.64)
    scope_y = y + (height * 0.48 if adaptive else height * 0.28)
    ax.text(
        x + 0.22,
        title_y,
        item["id"],
        fontsize=7.7,
        fontweight="bold",
        color=COLORS["text"],
        va="center",
    )
    ax.text(
        title_x,
        title_y,
        item["title"],
        fontsize=6.5,
        fontweight="bold",
        color=COLORS["text"],
        va="center",
    )
    ax.text(
        title_x,
        scope_y,
        item["scope"],
        fontsize=5.4,
        color=COLORS["muted"],
        va="center",
    )


def _arrow(ax, start, end, color=None, linewidth=0.9, linestyle="-"):
    ax.annotate(
        "",
        xy=end,
        xytext=start,
        arrowprops={
            "arrowstyle": "->",
            "color": color or COLORS["line"],
            "linewidth": linewidth,
            "linestyle": linestyle,
            "shrinkA": 1,
            "shrinkB": 1,
        },
    )


def plot_framework(spec=None, save=True):
    """Draw Figure 2 from the semantic specification and optionally export it."""
    spec = build_framework_spec() if spec is None else spec
    fig, ax = plt.subplots(figsize=(7.2, 4.45))
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis("off")

    ax.text(0.35, 9.62, "Information hierarchy", fontsize=9, fontweight="bold")
    ax.text(6.65, 9.62, "Validation path", fontsize=9, fontweight="bold")
    ax.text(
        0.35,
        9.32,
        "Table 1 defines exact rules; this panel shows only their logical relation.",
        fontsize=5.5,
        color=COLORS["muted"],
    )

    layer_y = {
        "Default": 8.35,
        "L1": 7.42,
        "L2": 6.58,
        "L3": 5.48,
        "L4": 4.64,
        "L5": 3.80,
        "L6": 2.70,
    }
    for layer in spec["layers"]:
        _draw_layer(ax, layer, 0.35, layer_y[layer["id"]])

    _draw_group_bracket(ax, 5.18, 6.56, 8.16, "Deployable", COLORS["deployable_edge"])
    _draw_group_bracket(ax, 5.18, 3.78, 6.20, "Oracle reference", COLORS["oracle_edge"])
    _draw_group_bracket(ax, 5.18, 2.68, 3.42, "Hindsight", COLORS["hindsight_edge"])

    items = {item["id"]: item for item in spec["validation_path"]}
    box_x = 6.65
    _draw_validation_box(ax, items["E1"], box_x, 8.05)
    _draw_validation_box(ax, items["E2"], box_x, 6.42)
    _draw_validation_box(ax, items["E3"], box_x, 4.35, height=1.40, adaptive=True)
    _draw_validation_box(ax, items["E4"], box_x, 2.80)
    _draw_validation_box(ax, items["Real data"], box_x, 1.22)

    # E3 bridge: observable information -> vector risk -> decision.
    bridge_x = [7.00, 8.55, 10.10]
    bridge_y = 4.42
    bridge_w = 1.25
    display_labels = {
        "observable sample features": "observable sample\nfeatures",
        "26-point risk curve": "26-point\nrisk curve",
        "selected delta": "selected delta",
    }
    for index, (x, label) in enumerate(zip(bridge_x, spec["adaptive_bridge"])):
        _rounded_box(
            ax,
            x,
            bridge_y,
            bridge_w,
            0.46,
            "#FFFFFF",
            COLORS["adaptive_edge"],
            linewidth=0.7,
        )
        ax.text(
            x + bridge_w / 2,
            bridge_y + 0.23,
            display_labels[label],
            fontsize=4.8,
            color=COLORS["text"],
            ha="center",
            va="center",
        )
        if index < len(bridge_x) - 1:
            _arrow(
                ax,
                (x + bridge_w + 0.03, bridge_y + 0.23),
                (bridge_x[index + 1] - 0.03, bridge_y + 0.23),
                color=COLORS["adaptive_edge"],
                linewidth=0.8,
            )

    # Map layer families to experiments.
    _arrow(ax, (5.52, 7.35), (6.62, 8.48), linewidth=0.9)
    _arrow(ax, (5.52, 4.95), (6.62, 6.85), linewidth=0.9)

    # E2 provides reference targets for E3; E4 and real data validate the selector.
    _arrow(
        ax,
        (9.18, 6.40),
        (9.18, 5.78),
        color=COLORS["adaptive_edge"],
        linewidth=1.1,
    )
    _arrow(ax, (9.18, 4.32), (9.18, 3.73), linewidth=1.0)
    _arrow(ax, (9.18, 2.78), (9.18, 2.17), linewidth=1.0)

    ax.text(
        9.35,
        6.05,
        "reference targets",
        fontsize=4.8,
        color=COLORS["adaptive_edge"],
        va="center",
    )
    ax.text(
        9.35,
        4.02,
        "robustness",
        fontsize=4.8,
        color=COLORS["muted"],
        va="center",
    )
    ax.text(
        9.35,
        2.47,
        "external check",
        fontsize=4.8,
        color=COLORS["muted"],
        va="center",
    )

    ax.text(
        0.35,
        1.65,
        "More information refines the reference decision,\n"
        "but only observable sample information is deployable.",
        fontsize=5.6,
        color=COLORS["muted"],
        va="top",
    )

    fig.subplots_adjust(left=0.02, right=0.99, top=0.98, bottom=0.02)
    if save:
        FIG_DIR.mkdir(parents=True, exist_ok=True)
        out = FIG_DIR / "fig1_framework"
        fig.savefig(out.with_suffix(".svg"), bbox_inches="tight")
        fig.savefig(out.with_suffix(".pdf"), bbox_inches="tight")
        fig.savefig(out.with_suffix(".png"), dpi=300, bbox_inches="tight")
        print("Saved fig1_framework.{svg,pdf,png}")
    return fig


if __name__ == "__main__":
    figure = plot_framework()
    plt.close(figure)
