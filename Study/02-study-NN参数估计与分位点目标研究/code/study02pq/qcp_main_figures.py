"""Publication figure for the current P/Q/QCP manuscript narrative."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from . import config as CFG


ROOT = Path(CFG.STUDY02_ROOT)
ANALYSIS = ROOT / "artifacts" / "qcp_main_analysis" / "analysis"
OUT = ROOT / "figures" / "qcp-main"
COLORS = {"P": "#8C8C8C", "Q": "#56B4E9", "QCP": "#009E73"}


def main() -> None:
    summary = json.loads((ANALYSIS / "summary.json").read_text(encoding="utf-8"))
    with (ANALYSIS / "resource_cells.csv").open(
        "r", encoding="utf-8", newline=""
    ) as handle:
        resource = list(csv.DictReader(handle))

    routes = ["P", "Q", "QCP"]
    fig, axes = plt.subplots(2, 2, figsize=(7.2, 5.4), constrained_layout=True)
    fig.suptitle("Target alignment with an explicit parameter-feasibility constraint",
                 fontsize=12, fontweight="bold")

    ax = axes[0, 0]
    values = [summary["pooled_rrmse"][route] for route in routes]
    markers = ["s", "o", "D"]
    for idx, (route, value, marker) in enumerate(zip(routes, values, markers)):
        ax.scatter(idx, value, s=78, marker=marker, color=COLORS[route],
                   edgecolor="black", linewidth=0.7, zorder=3)
        ax.text(idx, value + 0.00025, f"{value:.4f}", ha="center", fontsize=8)
    ax.set_xticks(range(3), routes)
    ax.set_ylabel("Test rRMSE")
    ax.set_ylim(0.1578, 0.1651)
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("A  Common-budget target accuracy", loc="left",
                 fontweight="bold", fontsize=10)

    ax = axes[0, 1]
    comparisons = ["Q_minus_P", "QCP_minus_Q", "QCP_minus_P"]
    labels = ["Q vs P", "QCP vs Q", "QCP vs P"]
    colors = [COLORS["Q"], COLORS["QCP"], COLORS["QCP"]]
    y = np.arange(len(comparisons))[::-1]
    for yi, key, color in zip(y, comparisons, colors):
        item = summary["contrasts"][key]
        point = 100.0 * item["relative_rrmse_improvement"]
        low, high = [100.0 * value for value in
                     item["relative_rrmse_improvement_95ci"]]
        ax.errorbar(point, yi, xerr=[[point - low], [high - point]], fmt="D",
                    color=color, ecolor="#333333", capsize=3, markersize=6)
        ax.text(high + 0.10, yi, f"{point:.2f}%", va="center", fontsize=8)
    ax.axvline(0.0, color="#777777", linestyle="--", linewidth=1)
    ax.set_yticks(y, labels)
    ax.set_xlabel("Relative rRMSE improvement (%)")
    ax.grid(axis="x", alpha=0.3)
    ax.set_title("B  Paired effects with 95% CIs", loc="left",
                 fontweight="bold", fontsize=10)

    ax = axes[1, 0]
    cancellation = [
        summary["diagnostics"][route]["mean_exact_cancellation_index"]
        for route in routes
    ]
    bars = ax.bar(routes, cancellation, color=[COLORS[route] for route in routes],
                  edgecolor="black", linewidth=0.6)
    for bar, value in zip(bars, cancellation):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.018,
                f"{value:.3f}", ha="center", fontsize=8)
    ax.set_ylabel("Parameter compensation index")
    ax.set_ylim(0.0, 1.02)
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("C  Parameter compensation", loc="left",
                 fontweight="bold", fontsize=10)

    ax = axes[1, 1]
    rng = np.random.default_rng(20260828)
    data = []
    for route in routes:
        values_route = np.asarray([
            float(row["best_epoch"]) for row in resource if row["route"] == route
        ])
        data.append(values_route)
    box = ax.boxplot(data, tick_labels=routes, patch_artist=True, showfliers=False,
                     medianprops={"color": "black", "linewidth": 1.3})
    for patch, route in zip(box["boxes"], routes):
        patch.set_facecolor(COLORS[route])
        patch.set_alpha(0.5)
    for idx, (route, values_route) in enumerate(zip(routes, data), start=1):
        x = idx + rng.uniform(-0.12, 0.12, size=len(values_route))
        ax.scatter(x, values_route, s=7, alpha=0.18, color=COLORS[route],
                   edgecolors="none")
    ax.axhline(300, color="#777777", linestyle=":", linewidth=1,
               label="Previous ceiling (300)")
    ax.set_ylabel("Best epoch")
    ax.set_ylim(0, 620)
    ax.legend(frameon=False, fontsize=7, loc="upper left")
    ax.grid(axis="y", alpha=0.3)
    ax.set_title("D  Optimization depth", loc="left", fontweight="bold",
                 fontsize=10)

    for ax in axes.flat:
        ax.spines[["top", "right"]].set_visible(False)
        ax.tick_params(labelsize=8)

    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "fig_qcp_main_results.png"
    pdf = OUT / "fig_qcp_main_results.pdf"
    fig.savefig(png, dpi=400, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    print(png)


if __name__ == "__main__":
    main()
