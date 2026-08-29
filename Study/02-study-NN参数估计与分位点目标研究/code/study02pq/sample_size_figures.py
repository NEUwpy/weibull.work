"""Publication figure for sample-size and P-equivalent sample-size results."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from . import config as CFG


ROOT = Path(CFG.STUDY02_ROOT)
INPUT = ROOT / "artifacts" / "qcp_sample_size_analysis" / "analysis" / "by_n.csv"
OUT = ROOT / "figures" / "qcp-main"


def _load() -> list[dict[str, float]]:
    with INPUT.open("r", encoding="utf-8", newline="") as handle:
        return [{key: float(value) for key, value in row.items()} for row in csv.DictReader(handle)]


def main() -> None:
    rows = _load()
    n = np.asarray([row["n"] for row in rows])
    colors = {"p": "#4D4D4D", "q": "#0072B2", "qcp": "#D55E00"}
    markers = {"p": "o", "q": "s", "qcp": "^"}
    labels = {"p": "P", "q": "Q", "qcp": "QCP"}
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
        "font.size": 9,
        "axes.labelsize": 10,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "savefig.dpi": 400,
    })
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 3.15), constrained_layout=True)

    ax = axes[0]
    for route in ("p", "q", "qcp"):
        y = 100 * np.asarray([row[f"{route}_rrmse"] for row in rows])
        low = 100 * np.asarray([row[f"{route}_rrmse_ci_low"] for row in rows])
        high = 100 * np.asarray([row[f"{route}_rrmse_ci_high"] for row in rows])
        ax.errorbar(
            n, y, yerr=np.vstack([y - low, high - y]), color=colors[route],
            marker=markers[route], markersize=5, linewidth=1.5, capsize=2.5,
            label=labels[route],
        )
    ax.set_xlabel("单次估计的寿命观测数 $n$")
    ax.set_ylabel("$x_{0.95}$ rRMSE (%)")
    ax.set_xticks(n)
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5)
    ax.text(-0.13, 1.04, "A", transform=ax.transAxes, fontweight="bold", fontsize=11)

    ax = axes[1]
    for route in ("q", "qcp"):
        y = np.asarray([row[f"{route}_equivalent_added_n"] for row in rows])
        low = np.asarray([row[f"{route}_equivalent_added_n_ci_low"] for row in rows])
        high = np.asarray([row[f"{route}_equivalent_added_n_ci_high"] for row in rows])
        ax.errorbar(
            n, y, yerr=np.vstack([y - low, high - y]), color=colors[route],
            marker=markers[route], markersize=5, linewidth=1.5, capsize=2.5,
            label=labels[route],
        )
    ax.axhline(0, color="#777777", linewidth=0.8, linestyle="--")
    ax.set_xlabel("实际寿命观测数 $n$")
    ax.set_ylabel("相对 P 的等效附加观测数")
    ax.set_xticks(n)
    ax.legend(frameon=False)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.5)
    ax.text(-0.13, 1.04, "B", transform=ax.transAxes, fontweight="bold", fontsize=11)

    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "fig_qcp_sample_size_equivalence.png", bbox_inches="tight")
    fig.savefig(OUT / "fig_qcp_sample_size_equivalence.pdf", bbox_inches="tight")
    plt.close(fig)
    print(OUT / "fig_qcp_sample_size_equivalence.png")


if __name__ == "__main__":
    main()
