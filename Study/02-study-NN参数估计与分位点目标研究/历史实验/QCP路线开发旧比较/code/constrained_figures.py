"""Publication figure for the four-route formal QCP confirmation."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as CFG


ROOT = Path(CFG.STUDY02_ROOT)
ARTIFACT = ROOT / "artifacts" / "qcp_constrained_confirm"
OUT = ROOT / "figures" / "qcp-constrained"

COLORS = {
    "P": "#999999",
    "Q": "#56B4E9",
    "QP": "#E69F00",
    "QCP": "#009E73",
}


def _style() -> None:
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "Microsoft YaHei", "DejaVu Sans"],
        "font.size": 8,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def make_figure() -> Path:
    _style()
    summary = json.loads((ARTIFACT / "analysis" / "summary.json").read_text("utf-8"))
    cells = pd.read_csv(ARTIFACT / "analysis" / "model_cells.csv")
    routes = ["P", "Q", "QP", "QCP"]

    fig = plt.figure(figsize=(7.2, 5.0), constrained_layout=True)
    grid = fig.add_gridspec(2, 2)
    axes = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]

    # A: absolute test performance, shown as points rather than truncated bars.
    ax = axes[0]
    values = [summary["pooled_rrmse"][r] for r in routes]
    ax.scatter(routes, values, s=48, c=[COLORS[r] for r in routes],
               edgecolor="black", linewidth=0.5, zorder=3)
    for x, value in enumerate(values):
        ax.text(x, value + 0.0007, f"{value:.4f}", ha="center", va="bottom", fontsize=7)
    ax.set_ylabel("Test rRMSE")
    ax.set_title("A  Four-route target accuracy", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#dddddd", linewidth=0.6)
    ax.set_ylim(0.155, 0.169)

    # B: predeclared paired effects with design-level empirical 95% CIs.
    ax = axes[1]
    comparisons = ["P", "Q", "QP"]
    effects = []
    lower = []
    upper = []
    labels = []
    for comparator in comparisons:
        item = summary["contrasts"][f"QCP_minus_{comparator}"]
        effect = 100 * item["relative_rrmse_improvement"]
        ci = 100 * np.asarray(item["relative_rrmse_improvement_95ci"])
        effects.append(effect)
        lower.append(effect - ci[0])
        upper.append(ci[1] - effect)
        labels.append(f"QCP vs {comparator}")
    y = np.arange(len(labels))
    ax.errorbar(effects, y, xerr=np.asarray([lower, upper]), fmt="o", color=COLORS["QCP"],
                ecolor="#333333", capsize=3, markersize=5, linewidth=1)
    ax.axvline(0, color="#777777", linestyle="--", linewidth=0.8)
    ax.set_yticks(y, labels)
    ax.invert_yaxis()
    ax.set_xlabel("Relative rRMSE improvement (%)")
    ax.set_title("B  Paired effects and 95% CIs", loc="left", fontweight="bold")
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)
    for yi, effect in zip(y, effects):
        ax.text(effect + 0.12, yi, f"{effect:.2f}%", va="center", fontsize=7)

    # C: all ten seed-level effects, retaining individual points.
    ax = axes[2]
    for x, comparator in enumerate(comparisons):
        by_seed = cells.groupby("seed")[["mse_qcp", f"mse_{comparator.lower()}"]].mean()
        target = np.sqrt(by_seed["mse_qcp"].to_numpy())
        comp = np.sqrt(by_seed[f"mse_{comparator.lower()}"].to_numpy())
        effect = 100 * (comp - target) / comp
        jitter = np.linspace(-0.07, 0.07, len(effect))
        ax.scatter(np.full(len(effect), x) + jitter, effect, s=18, facecolor=COLORS["QCP"],
                   edgecolor="black", linewidth=0.35, alpha=0.85)
        ax.plot([x - 0.16, x + 0.16], [effect.mean(), effect.mean()], color="black", linewidth=1.4)
    ax.axhline(0, color="#777777", linestyle="--", linewidth=0.8)
    ax.set_xticks(range(3), ["vs P", "vs Q", "vs QP"])
    ax.set_ylabel("Seed-level improvement (%)")
    ax.set_title("C  Training-seed stability (10 seeds)", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#dddddd", linewidth=0.6)

    # D: target performance versus internal parameter compensation.
    ax = axes[3]
    for route in routes:
        diag = summary["diagnostics"][route]
        ax.scatter(diag["mean_exact_cancellation_index"], summary["pooled_rrmse"][route],
                   s=52, color=COLORS[route], edgecolor="black", linewidth=0.5, label=route)
        ax.annotate(route, (diag["mean_exact_cancellation_index"], summary["pooled_rrmse"][route]),
                    xytext=(4, 3), textcoords="offset points", fontsize=7)
    ax.set_xlabel("Mean parameter-cancellation index")
    ax.set_ylabel("Test rRMSE")
    ax.set_title("D  Accuracy and parameter compensation", loc="left", fontweight="bold")
    ax.grid(color="#dddddd", linewidth=0.6)

    fig.suptitle("Q-primary learning with a parameter-consistency constraint", fontsize=11,
                 fontweight="bold")
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "fig_qcp_formal_confirmation.png"
    pdf = OUT / "fig_qcp_formal_confirmation.pdf"
    fig.savefig(png, dpi=400, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png


def main() -> None:
    print(make_figure())


if __name__ == "__main__":
    main()
