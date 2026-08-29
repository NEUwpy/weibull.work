"""Draw the Q-equivalence geometry, P feasible set, and broad-domain evidence."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / "artifacts" / "qcp_main_analysis" / "analysis" / "summary.json"
OUT = ROOT / "figures" / "qcp-main"


def _equivalent_eta_error(beta_error: float, beta: float, eta: float,
                          gamma: float, reliability: float) -> float:
    a = -np.log(reliability)
    x_true = gamma + eta * a ** (1.0 / beta)
    beta_hat = beta * (1.0 + beta_error)
    eta_hat = (x_true - gamma) / a ** (1.0 / beta_hat)
    return float(eta_hat / eta - 1.0)


def main() -> None:
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))

    mpl.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
        "font.size": 8.5,
        "axes.labelsize": 9,
        "axes.titlesize": 10,
        "xtick.labelsize": 7.5,
        "ytick.labelsize": 7.5,
        "legend.fontsize": 7.5,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    })

    # A real two-dimensional slice through the Weibull output space.  Gamma is
    # held fixed only so the one-target equivalence curve can be seen on paper.
    beta, eta, gamma, reliability = 1.5, 1000.0, 100.0, 0.95
    ub = np.linspace(-0.65, 1.25, 401)
    ue = np.linspace(-0.78, 0.80, 401)
    xx, yy = np.meshgrid(ub, ue)
    beta_hat = beta * (1.0 + xx)
    eta_hat = eta * (1.0 + yy)
    a = -np.log(reliability)
    x_true = gamma + eta * a ** (1.0 / beta)
    x_hat = gamma + eta_hat * a ** (1.0 / beta_hat)
    q_error_pct = np.abs((x_hat - x_true) / x_true) * 100.0
    eta_equal = np.array([
        _equivalent_eta_error(value, beta, eta, gamma, reliability)
        for value in ub
    ])

    q_point = np.array([1.0, _equivalent_eta_error(1.0, beta, eta, gamma, reliability)])
    qcp_point = np.array([0.30, _equivalent_eta_error(0.30, beta, eta, gamma, reliability)])
    p_point = np.array([0.0, 0.0])
    p_radius = 0.52

    colors = {"P": "#0072B2", "Q": "#E69F00", "QCP": "#009E73"}
    levels = [0.0, 0.25, 0.5, 1, 2, 5, 10, 20, 40, 80]

    fig = plt.figure(figsize=(10.6, 3.55), constrained_layout=True)
    gs = fig.add_gridspec(1, 3, width_ratios=[1.08, 1.08, 1.12])
    axes = [fig.add_subplot(gs[0, i]) for i in range(3)]

    for ax in axes[:2]:
        cf = ax.contourf(xx, yy, q_error_pct, levels=levels, cmap="cividis_r",
                         extend="max")
        ax.contour(xx, yy, q_error_pct, levels=[0.25, 1, 5, 10, 20],
                   colors="white", linewidths=0.55, alpha=0.8)
        ax.plot(ub, eta_equal, color="#D55E00", linewidth=1.8,
                linestyle="--", label=r"等寿命点轨迹：$\hat{x}_{0.95}=x_{0.95}$")
        ax.set_xlim(ub.min(), ub.max())
        ax.set_ylim(ue.min(), ue.max())
        ax.set_xlabel(r"$u_\beta=(\hat\beta-\beta)/\beta$")
        ax.set_ylabel(r"$u_\eta=(\hat\eta-\eta)/\eta$")
        ax.axhline(0, color="0.25", lw=0.45, alpha=0.45)
        ax.axvline(0, color="0.25", lw=0.45, alpha=0.45)

    axes[0].set_title(r"A  $L_Q$ 等高线与等寿命点轨迹", loc="left",
                      fontweight="bold")
    axes[0].scatter(*p_point, s=50, marker="o", c=colors["P"], edgecolor="white",
                    linewidth=0.8, zorder=5, label=r"真值点 $u=(0,0)$")
    axes[0].scatter(*q_point, s=66, marker="^", c=colors["Q"], edgecolor="black",
                    linewidth=0.6, zorder=6, label=r"示意解 $u_Q$")
    axes[0].annotate(r"$L_Q=0$，但 $L_P>0$", xy=q_point,
                     xytext=(0.38, 0.46), arrowprops=dict(arrowstyle="->", lw=0.8),
                     ha="center", va="center")
    axes[0].legend(frameon=False, loc="lower left")

    axes[1].set_title(r"B  约束 $L_P\leq\tau$ 下的可行解", loc="left",
                      fontweight="bold")
    feasible = Ellipse((0, 0), 2 * p_radius, 2 * p_radius,
                       facecolor=colors["P"], edgecolor=colors["P"],
                       alpha=0.14, lw=1.5, hatch="///")
    axes[1].add_patch(feasible)
    axes[1].scatter(*q_point, s=58, marker="^", facecolors="none",
                    edgecolors=colors["Q"], linewidth=1.6, zorder=6,
                    label=r"示意解 $u_Q$（不可行）")
    axes[1].scatter(*qcp_point, s=66, marker="s", c=colors["QCP"],
                    edgecolor="black", linewidth=0.6, zorder=7,
                    label=r"示意解 $u_{QCP}$（可行）")
    axes[1].scatter(*p_point, s=46, marker="o", c=colors["P"],
                    edgecolor="white", linewidth=0.8, zorder=6)
    axes[1].annotate(r"$L_P\leq\tau$", xy=(-0.27, 0.23), xytext=(-0.55, 0.58),
                     arrowprops=dict(arrowstyle="->", lw=0.8, color=colors["P"]),
                     color=colors["P"], ha="center")
    axes[1].annotate(r"可行域内最小化 $L_Q$", xy=qcp_point, xytext=(0.74, 0.42),
                     arrowprops=dict(arrowstyle="->", lw=0.8), ha="center")
    axes[1].legend(frameon=False, loc="lower left")

    ax = axes[2]
    ax.set_title("C  广参数域配对结果（200 个模型单元）", loc="left",
                 fontweight="bold")
    routes = ["P", "Q", "QCP"]
    xvals = np.array([summary["pooled_rrmse"][r] * 100 for r in routes])
    yvals = np.array([summary["diagnostics"][r]["mean_parameter_loss"] for r in routes])
    markers = {"P": "o", "Q": "^", "QCP": "s"}
    label_offsets = {"P": (-70, 6), "Q": (-58, -32), "QCP": (8, 8)}
    for route, x, y in zip(routes, xvals, yvals):
        ax.scatter(x, y, s=86, marker=markers[route], c=colors[route],
                   edgecolor="black", linewidth=0.65, zorder=5, label=route)
        ax.annotate(f"{route}\n{x:.2f}%,  $L_P$={y:.3g}", (x, y),
                    xytext=label_offsets[route], textcoords="offset points",
                    fontsize=7.4, ha="left")
    ax.annotate(r"加入 $L_P$ 约束", xy=(xvals[2], yvals[2]),
                xytext=(xvals[1], yvals[1]),
                arrowprops=dict(arrowstyle="-|>", lw=1.6, color=colors["QCP"],
                                connectionstyle="arc3,rad=-0.12"),
                color=colors["QCP"], ha="right", va="bottom")
    ax.set_yscale("log")
    ax.set_xlim(15.78, 16.56)
    ax.set_ylim(0.035, 150)
    ax.set_xlabel(r"$x_{0.95}$ RMSRE (%)")
    ax.set_ylabel(r"平均归一化参数损失 $L_P$（对数尺度）")
    ax.grid(axis="y", which="both", color="0.88", lw=0.6)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    cbar = fig.colorbar(cf, ax=axes[:2], fraction=0.035, pad=0.02)
    cbar.set_label(r"$|\hat{x}_{0.95}-x_{0.95}|/x_{0.95}$ (%)")
    fig.text(
        0.5, -0.02,
        r"A–B：固定 $\gamma=100$、$\beta=1.5$、$\eta=1000$ 的二维输出切片；"
        r"符号位置为机制示意，不是单个训练模型的实测参数。C：每条路线 480,000 条 held-out 预测。",
        ha="center", va="top", fontsize=7.5,
    )

    OUT.mkdir(parents=True, exist_ok=True)
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"fig_qcp_geometry_and_evidence.{suffix}",
                    dpi=600 if suffix == "png" else None,
                    bbox_inches="tight", facecolor="white")
    plt.close(fig)


if __name__ == "__main__":
    main()
