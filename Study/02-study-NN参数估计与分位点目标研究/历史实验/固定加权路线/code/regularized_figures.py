"""Figures for the Study02 Q+P mechanism and confirmation evidence."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import LogNorm

from . import config as CFG


ROOT = Path(CFG.STUDY02_ROOT)
PILOT = ROOT / "artifacts" / "pq_regularized_pilot"
CONFIRM = ROOT / "artifacts" / "pq_regularized_confirm"
OUT = ROOT / "figures" / "pq-regularized"

COLORS = {"P": "#0072B2", "Q": "#D55E00", "QP": "#009E73"}


def _style() -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Arial", "DejaVu Sans"],
        "font.size": 8,
        "axes.labelsize": 8,
        "axes.titlesize": 9,
        "xtick.labelsize": 7,
        "ytick.labelsize": 7,
        "legend.fontsize": 7,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 150,
        "savefig.dpi": 300,
    })


def _save(fig: plt.Figure, stem: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"{stem}.{suffix}", bbox_inches="tight",
                    facecolor="white")
    plt.close(fig)


def geometry() -> None:
    """A 2-D slice of parameter-output loss geometry, not NN weight space."""
    beta0, eta0, gamma0 = 3.0, 1000.0, 500.0
    beta = np.linspace(1.5, 5.0, 360)
    eta = np.linspace(350.0, 1850.0, 360)
    B, E = np.meshgrid(beta, eta)
    a = -np.log(0.95)
    x0 = gamma0 + eta0 * a ** (1.0 / beta0)
    xhat = gamma0 + E * a ** (1.0 / B)
    lp = ((B - beta0) / beta0) ** 2 + ((E - eta0) / eta0) ** 2
    lq = ((xhat - x0) / x0) ** 2
    losses = [(lp, "P: parameter loss"), (lq, "Q: target loss"),
              (lq + lp, r"QP: $L_Q+L_P$")]
    levels = np.geomspace(1e-6, 1.0, 13)
    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.35), sharex=True, sharey=True)
    for label, (ax, (loss, title)) in enumerate(zip(axes, losses), start=1):
        ax.contourf(B, E, np.maximum(loss, 1e-8), levels=levels,
                    norm=LogNorm(vmin=levels[0], vmax=levels[-1]), cmap="cividis")
        ax.contour(B, E, lq, levels=[1e-6], colors="white", linewidths=1.2)
        ax.scatter([beta0], [eta0], s=28, marker="*", color="#CC79A7",
                   edgecolor="black", linewidth=0.4, zorder=4, label="True parameters")
        ax.set_title(title)
        ax.set_xlabel(r"Predicted shape $hat\beta$")
        ax.text(-0.12, 1.06, chr(64 + label), transform=ax.transAxes,
                fontweight="bold", fontsize=10)
        ax.grid(False)
    axes[0].set_ylabel(r"Predicted scale $hat\eta$")
    axes[0].legend(frameon=False, loc="upper right")
    fig.suptitle("Parameter-output loss geometry (slice at true/predicted gamma = 500)",
                 y=1.03, fontsize=9)
    fig.text(0.5, -0.02,
             "White line: near-equal x0.95 curve. Q has a long valley; P selects the true point; QP narrows the valley.",
             ha="center", fontsize=7)
    fig.tight_layout(w_pad=1.1)
    _save(fig, "fig_qp_output_geometry")


def evidence() -> None:
    resource = json.loads((PILOT / "analysis" / "resource_summary.json").read_text(
        encoding="utf-8"))
    lambdas = json.loads((PILOT / "analysis" / "lambda_summary.json").read_text(
        encoding="utf-8"))
    confirm = json.loads((CONFIRM / "analysis" / "summary.json").read_text(
        encoding="utf-8"))

    fig, axes = plt.subplots(1, 3, figsize=(7.2, 2.65), constrained_layout=True)
    ax = axes[0]
    budget_names = ["300 / 20", "600 / 60"]
    vals = [resource["by_budget"]["baseline"]["Q"]["validation_rrmse"],
            resource["by_budget"]["extended"]["Q"]["validation_rrmse"]]
    ax.plot(budget_names, vals, marker="o", color=COLORS["Q"], linewidth=1.5)
    ax.set_ylabel("Validation x0.95 rRMSE")
    ax.set_xlabel("Max epochs / patience")
    ax.set_title("Training-budget gate")
    ax.text(0.05, 0.06, "0.237% lower; below\nthe 0.5% cost-benefit gate",
            transform=ax.transAxes, fontsize=6.5, va="bottom")

    ax = axes[1]
    xs = np.array([float(k) for k in lambdas["by_lambda"]])
    ys = np.array([lambdas["by_lambda"][str(x)]["validation_rrmse"] for x in xs])
    plot_x = np.where(xs == 0.0, 1e-7, xs)
    ax.plot(plot_x, ys, marker="o", color=COLORS["QP"], linewidth=1.2, markersize=3)
    ax.set_xscale("log")
    ax.axhline(ys[xs == 0][0], color=COLORS["Q"], linestyle="--", linewidth=0.9,
               label="Pure Q")
    ax.scatter([1.0], [ys[xs == 1.0][0]], s=34, marker="*", color="#CC79A7",
               edgecolor="black", linewidth=0.4, zorder=4, label=r"Selected $\lambda=1$")
    ax.set_xlabel(r"Auxiliary weight $\lambda_P$ (0 shown at $10^{-7}$)")
    ax.set_ylabel("Validation x0.95 rRMSE")
    ax.set_title("Non-monotone lambda screen")
    ax.legend(frameon=False, loc="upper left")

    ax = axes[2]
    route_order = ["P", "Q", "QP"]
    rrmse = [confirm["pooled_rrmse"][r] for r in route_order]
    bars = ax.bar(route_order, rrmse, color=[COLORS[r] for r in route_order], width=0.68)
    ax.set_ylim(0.155, 0.169)
    ax.set_ylabel("Independent-test x0.95 rRMSE")
    ax.set_title("10-seed formal confirmation")
    for bar, value in zip(bars, rrmse):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.00025, f"{value:.4f}",
                ha="center", va="bottom", fontsize=6.5)
    ax.text(1.5, 0.1560, "QP vs Q: -0.984%\nQP vs P: -3.955%",
            ha="center", fontsize=7)

    for i, ax in enumerate(axes):
        ax.text(-0.14, 1.06, chr(65 + i), transform=ax.transAxes,
                fontweight="bold", fontsize=10)
        ax.grid(axis="y", color="#D9D9D9", linewidth=0.5, alpha=0.7)
    _save(fig, "fig_qp_selection_and_confirmation")


def main() -> None:
    _style()
    geometry()
    evidence()


if __name__ == "__main__":
    main()
