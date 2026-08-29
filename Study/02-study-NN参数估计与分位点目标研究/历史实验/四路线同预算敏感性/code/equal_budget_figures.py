"""Publication figure for the post-test four-route equal-budget sensitivity."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from . import config as CFG


ROOT = Path(CFG.STUDY02_ROOT)
ARTIFACT = ROOT / "artifacts" / "equal_budget_sensitivity"
QCP_ARTIFACT = ROOT / "artifacts" / "qcp_constrained_confirm"
OUT = ROOT / "figures" / "equal-budget"
ROUTES = ["P", "Q", "QP", "QCP"]
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


def _metadata(route: str) -> list[dict]:
    root = QCP_ARTIFACT if route == "QCP" else ARTIFACT
    return [json.loads(path.read_text(encoding="utf-8"))
            for path in sorted((root / "fit_metadata").glob(f"*_r{route}.json"))]


def make_figure() -> Path:
    _style()
    summary = json.loads(
        (ARTIFACT / "analysis" / "summary.json").read_text(encoding="utf-8"))
    cells = pd.read_csv(ARTIFACT / "analysis" / "model_cells.csv")
    fig = plt.figure(figsize=(7.2, 5.2), constrained_layout=True)
    grid = fig.add_gridspec(2, 2)
    axes = [fig.add_subplot(grid[i, j]) for i in range(2) for j in range(2)]

    ax = axes[0]
    values = [summary["pooled_rrmse"][route] for route in ROUTES]
    markers = ["s", "o", "^", "D"]
    for x, (route, value, marker) in enumerate(zip(ROUTES, values, markers)):
        ax.scatter(x, value, s=50, marker=marker, color=COLORS[route],
                   edgecolor="black", linewidth=0.5, zorder=3)
        ax.text(x, value + 0.00035, f"{value:.4f}", ha="center", fontsize=7)
    ax.set_xticks(range(4), ROUTES)
    ax.set_ylabel("Test rRMSE")
    ax.set_ylim(0.1575, 0.1653)
    ax.set_title("A  Equal-budget target accuracy", loc="left", fontweight="bold")
    ax.grid(axis="y", color="#dddddd", linewidth=0.6)

    ax = axes[1]
    pairs = [
        ("QCP_minus_QP", "QCP vs QP", "QCP"),
        ("QCP_minus_Q", "QCP vs Q", "QCP"),
        ("QCP_minus_P", "QCP vs P", "QCP"),
        ("QP_minus_Q", "QP vs Q", "QP"),
        ("QP_minus_P", "QP vs P", "QP"),
    ]
    for y, (key, label, route) in enumerate(pairs):
        item = summary["contrasts"][key]
        effect = 100 * item["relative_rrmse_improvement"]
        ci = 100 * np.asarray(item["relative_rrmse_improvement_95ci"])
        ax.errorbar(effect, y, xerr=[[effect - ci[0]], [ci[1] - effect]],
                    fmt="D" if route == "QCP" else "^", color=COLORS[route],
                    ecolor="#333333", capsize=3, markersize=5, linewidth=1)
        ax.text(max(effect, ci[1]) + 0.08, y, f"{effect:.2f}%", va="center", fontsize=7)
    ax.axvline(0, color="#777777", linestyle="--", linewidth=0.8)
    ax.set_yticks(range(len(pairs)), [item[1] for item in pairs])
    ax.invert_yaxis()
    ax.set_xlabel("Relative rRMSE improvement (%)")
    ax.set_title("B  Paired effects with 95% CIs", loc="left", fontweight="bold")
    ax.grid(axis="x", color="#dddddd", linewidth=0.6)

    ax = axes[2]
    by_seed = cells.groupby("seed")[["mse_qcp", "mse_qp"]].mean()
    qcp = np.sqrt(by_seed["mse_qcp"].to_numpy())
    qp = np.sqrt(by_seed["mse_qp"].to_numpy())
    effects = 100 * (qp - qcp) / qp
    x = np.arange(len(effects))
    colors = [COLORS["QCP"] if value > 0 else COLORS["QP"] for value in effects]
    ax.scatter(x, effects, s=34, c=colors, marker="D", edgecolor="black", linewidth=0.4)
    ax.axhline(0, color="#777777", linestyle="--", linewidth=0.8)
    ax.set_xticks(x, [str(seed) for seed in by_seed.index], rotation=45, ha="right")
    ax.set_xlabel("Training seed")
    ax.set_ylabel("QCP vs QP improvement (%)")
    ax.set_title("C  QCP–QP seed stability (8/10 favor QCP)",
                 loc="left", fontweight="bold")
    ax.grid(axis="y", color="#dddddd", linewidth=0.6)

    ax = axes[3]
    rng = np.random.default_rng(20260828)
    epoch_values = []
    for x_pos, route in enumerate(ROUTES):
        values_route = np.asarray(
            [item["best_epoch"] for item in _metadata(route)], dtype=float)
        epoch_values.append(values_route)
        jitter = rng.uniform(-0.12, 0.12, size=len(values_route))
        ax.scatter(np.full(len(values_route), x_pos) + jitter, values_route,
                   s=6, alpha=0.22, color=COLORS[route], edgecolor="none")
    box = ax.boxplot(epoch_values, positions=np.arange(4), widths=0.45,
                     showfliers=False, patch_artist=True,
                     medianprops={"color": "black", "linewidth": 1.2},
                     whiskerprops={"linewidth": 0.8}, capprops={"linewidth": 0.8})
    for patch, route in zip(box["boxes"], ROUTES):
        patch.set_facecolor(COLORS[route])
        patch.set_alpha(0.45)
    ax.axhline(300, color="#777777", linestyle=":", linewidth=0.9,
               label="Previous ceiling (300)")
    ax.set_xticks(range(4), ROUTES)
    ax.set_ylabel("Best epoch")
    ax.set_ylim(0, 620)
    ax.set_title("D  Actual optimization depth (200 fits/route)",
                 loc="left", fontweight="bold")
    ax.legend(frameon=False, loc="upper left")
    ax.grid(axis="y", color="#dddddd", linewidth=0.6)

    fig.suptitle("Four-route comparison under a common 600/60 training budget",
                 fontsize=11, fontweight="bold")
    OUT.mkdir(parents=True, exist_ok=True)
    png = OUT / "fig_equal_budget_sensitivity.png"
    pdf = OUT / "fig_equal_budget_sensitivity.pdf"
    fig.savefig(png, dpi=400, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return png


def main() -> None:
    print(make_figure())


if __name__ == "__main__":
    main()

