"""Render Figure 5: estimation risk under the L1--L6 information conditions."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from make_submission_figures import export_figure as export_submission_figure


SCRIPT_DIR = Path(__file__).resolve().parent
FIGURE_DIR = SCRIPT_DIR.parent
STUDY_DIR = SCRIPT_DIR.parents[2]
FORMAL_SOURCE = (
    STUDY_DIR
    / "artifacts"
    / "formal"
    / "E6_dimensional_raw"
    / "paper"
    / "table1_l1_l6.csv"
)
OUTPUT_STEM = FIGURE_DIR / "main" / "fig5_information_level_results"
SOURCE_PATH = (
    FIGURE_DIR / "data" / "derived" / "fig5_information_level_results.csv"
)

LAYERS = ["Default", "L1", "L2", "L3", "L4", "L5", "L6"]
N_VALUES = [7, 10, 15, 20]
ROW_LABELS = {
    "Default": "固定 $\\delta=0.10$",
    "L1": "L1  统一取值",
    "L2": "L2  $n$",
    "L3": "L3  $\\beta$",
    "L4": "L4  $(\\beta,n)$",
    "L5": "L5  $(\\beta,\\gamma/\\eta,n)$",
    "L6": "L6  逐样本事后",
}
COLORS = {
    "Default": "#7A7A7A",
    "L1": "#E6A15A",
    "L2": "#D77A32",
    "L3": "#79B8E5",
    "L4": "#3F8FC7",
    "L5": "#185A8D",
    "L6": "#2A9D8F",
}


def read_formal_results() -> dict[str, dict[str, float]]:
    if not FORMAL_SOURCE.is_file():
        raise FileNotFoundError(f"Formal L1--L6 source not found: {FORMAL_SOURCE}")

    with FORMAL_SOURCE.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    by_layer = {row["规则"]: row for row in rows}
    if set(by_layer) != set(LAYERS):
        raise ValueError(
            f"Expected layers {LAYERS}, found {sorted(by_layer)} in {FORMAL_SOURCE}"
        )

    results: dict[str, dict[str, float]] = {}
    for layer in LAYERS:
        row = by_layer[layer]
        results[layer] = {"pooled_J1": float(row["$J_1$"])}
        for n_value in N_VALUES:
            results[layer][f"J1_n{n_value}"] = float(row[f"$n={n_value}$"])
    return results


def write_source_data(results: dict[str, dict[str, float]]) -> None:
    SOURCE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temporary = SOURCE_PATH.with_name(f"{SOURCE_PATH.stem}.new.csv")
    fields = [
        "layer",
        "selection_information",
        "pooled_J1",
        "pooled_reduction_vs_default_pct",
        *[f"J1_n{n_value}" for n_value in N_VALUES],
        *[f"reduction_vs_default_pct_n{n_value}" for n_value in N_VALUES],
    ]
    default = results["Default"]
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for layer in LAYERS:
            row = {
                "layer": layer,
                "selection_information": ROW_LABELS[layer],
                "pooled_J1": f"{results[layer]['pooled_J1']:.12f}",
                "pooled_reduction_vs_default_pct": (
                    f"{100 * (default['pooled_J1'] - results[layer]['pooled_J1']) / default['pooled_J1']:.8f}"
                ),
            }
            for n_value in N_VALUES:
                key = f"J1_n{n_value}"
                row[key] = f"{results[layer][key]:.12f}"
                row[f"reduction_vs_default_pct_n{n_value}"] = (
                    f"{100 * (default[key] - results[layer][key]) / default[key]:.8f}"
                )
            writer.writerow(row)
    temporary.replace(SOURCE_PATH)


def export_figure(fig: plt.Figure) -> None:
    export_submission_figure(fig, OUTPUT_STEM.name, OUTPUT_STEM.parent)


def draw_figure(results: dict[str, dict[str, float]]) -> plt.Figure:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "font.size": 8.5,
            "axes.linewidth": 0.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )

    fig = plt.figure(figsize=(12.3, 5.5), constrained_layout=False)
    grid = fig.add_gridspec(
        1, 2, width_ratios=[1.08, 0.92],
        left=0.13, right=0.965, bottom=0.16, top=0.91, wspace=0.29,
    )
    ax_a = fig.add_subplot(grid[0, 0])
    ax_b = fig.add_subplot(grid[0, 1])

    # Panel a: pooled risk under each information condition.
    default_j1 = results["Default"]["pooled_J1"]
    y_positions = np.arange(len(LAYERS), dtype=float)
    for y, layer in zip(y_positions, LAYERS):
        value = results[layer]["pooled_J1"]
        reduction = 100 * (default_j1 - value) / default_j1
        color = COLORS[layer]
        ax_a.hlines(y, value, default_j1, color=color, linewidth=2.2, alpha=0.55)
        ax_a.scatter(value, y, s=66, color=color, edgecolor="white", linewidth=0.8, zorder=3)
        if layer == "Default":
            label = f"{value:.4f}"
        else:
            label = f"{value:.4f}   {reduction:.1f}% lower"
        ax_a.text(value - 0.003, y - 0.19, label, ha="right", va="center", color=color, fontsize=8.0)

    ax_a.axvline(default_j1, color="#777777", linewidth=1.0, linestyle=(0, (4, 3)))
    ax_a.axhline(5.5, color="#B7B7B7", linewidth=0.9, linestyle=(0, (3, 3)))
    ax_a.text(0.487, 5.62, "post hoc reference", color="#6B6B6B", fontsize=7.4, va="bottom")
    ax_a.set_yticks(y_positions, [ROW_LABELS[layer] for layer in LAYERS])
    ax_a.invert_yaxis()
    ax_a.set_xlim(0.475, 0.646)
    ax_a.set_xticks([0.48, 0.52, 0.56, 0.60, 0.64])
    ax_a.set_xlabel("Pooled $J_1$  (lower is better)", labelpad=7)
    ax_a.set_title("Risk under each information condition", loc="left", fontsize=10, pad=9)
    ax_a.grid(axis="x", color="#E7E7E7", linewidth=0.7)
    ax_a.tick_params(axis="y", length=0, pad=6)
    ax_a.spines["left"].set_visible(False)

    # Panel b: reductions versus Default across sample sizes.
    heat_layers = LAYERS[1:]
    matrix = np.array(
        [
            [
                100
                * (
                    results["Default"][f"J1_n{n_value}"]
                    - results[layer][f"J1_n{n_value}"]
                )
                / results["Default"][f"J1_n{n_value}"]
                for n_value in N_VALUES
            ]
            for layer in heat_layers
        ]
    )
    boundaries = [0, 1, 2, 4, 6, 8, 10, 15, 20, 25]
    cmap = mpl.colors.LinearSegmentedColormap.from_list(
        "study01_blue_teal",
        ["#F7FAFC", "#D7EAF4", "#8EC1DA", "#377EAD", "#176A79"],
        N=256,
    )
    norm = mpl.colors.BoundaryNorm(boundaries, cmap.N, clip=True)
    image = ax_b.imshow(matrix, cmap=cmap, norm=norm, aspect="auto", interpolation="nearest")
    for row_index, layer in enumerate(heat_layers):
        for column_index, _ in enumerate(N_VALUES):
            value = matrix[row_index, column_index]
            text_color = "white" if value >= 8 else "#17324D"
            ax_b.text(
                column_index,
                row_index,
                f"{value:.1f}%",
                ha="center",
                va="center",
                color=text_color,
                fontsize=8.0,
                fontweight="bold" if value >= 6 else "normal",
            )
    ax_b.axhline(4.5, color="white", linewidth=2.6)
    ax_b.axhline(4.5, color="#7E7E7E", linewidth=0.8, linestyle=(0, (3, 3)))
    ax_b.set_xticks(np.arange(len(N_VALUES)), [str(value) for value in N_VALUES])
    ax_b.set_yticks(np.arange(len(heat_layers)), heat_layers)
    ax_b.set_xlabel("Sample size, $n$", labelpad=7)
    ax_b.set_title("$J_1$ reduction relative to Default", loc="left", fontsize=10, pad=9)
    ax_b.tick_params(length=0)
    for spine in ax_b.spines.values():
        spine.set_visible(False)

    colorbar = fig.colorbar(
        image,
        ax=ax_b,
        orientation="horizontal",
        fraction=0.07,
        pad=0.14,
        ticks=[0, 2, 4, 6, 8, 10, 15, 20, 25],
    )
    colorbar.set_label("Reduction relative to Default (%)", labelpad=5)
    colorbar.outline.set_visible(False)

    fig.text(0.045, 0.945, "a", fontsize=14, fontweight="bold", va="top")
    fig.text(0.57, 0.945, "b", fontsize=14, fontweight="bold", va="top")
    return fig


def main() -> None:
    results = read_formal_results()
    write_source_data(results)
    figure = draw_figure(results)
    export_figure(figure)
    plt.close(figure)
    print(OUTPUT_STEM.with_suffix(".png"))


if __name__ == "__main__":
    main()
