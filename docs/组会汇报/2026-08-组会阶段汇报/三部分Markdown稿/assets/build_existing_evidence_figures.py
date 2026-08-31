"""Build group-meeting figures from existing sealed Study01/P4 evidence.

This script performs no model fitting and does not alter research artifacts. It
only derives presentation figures and a small audit CSV in this assets folder.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[4]
P4 = (
    REPO
    / "Study"
    / "01-study-MDM最小偏移量优化研究"
    / "artifacts"
    / "formal"
    / "p4_formal_compare"
)
OUT = HERE / "part2"

METHODS = ["Direct-MLP", "MDM-Vector-MLP"]
COLORS = {"Direct-MLP": "#0072B2", "MDM-Vector-MLP": "#D55E00"}
MARKERS = {"Direct-MLP": "o", "MDM-Vector-MLP": "s"}
TRACKS = ["main_holdout", "param_interp", "n_interp", "extrap_diag"]
TRACK_LABELS = ["主留出", "参数插值", "样本量插值", "外推诊断"]
PARAMETERS = ["beta", "eta", "gamma"]
PARAM_LABELS = [r"$\beta$", r"$\eta$", r"$\gamma$"]


def configure_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Microsoft YaHei", "SimHei", "Arial", "DejaVu Sans"],
            "axes.unicode_minus": False,
            "font.size": 10,
            "axes.labelsize": 10,
            "axes.titlesize": 11,
            "xtick.labelsize": 9,
            "ytick.labelsize": 9,
            "legend.fontsize": 9,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def load_track_summary() -> pd.DataFrame:
    payload = json.loads((P4 / "result_tables.json").read_text(encoding="utf-8"))
    rows: list[dict] = []
    for track in TRACKS:
        for method in METHODS:
            summary = payload[track]["methods"][method]["j1_summary"]
            rows.append(
                {
                    "track": track,
                    "method": method,
                    "mean_J1": float(summary["mean_J1"]),
                    "sd_J1_across_models": float(summary["SD_J1"]),
                    "n_models": int(summary["n_models"]),
                }
            )
    return pd.DataFrame(rows)


def load_parameter_metrics() -> pd.DataFrame:
    path = P4 / "main_holdout" / "evaluation.csv"
    usecols = [
        "method",
        "beta",
        "gamma_over_eta",
        "beta_hat",
        "eta_hat",
        "gamma_hat",
        "failed",
    ]
    df = pd.read_csv(path, usecols=usecols)
    df = df[df["method"].isin(METHODS) & ~df["failed"].astype(bool)].copy()
    df["err_beta"] = (df["beta_hat"] - df["beta"]) / df["beta"]
    df["err_eta"] = df["eta_hat"] - 1.0
    df["err_gamma"] = df["gamma_hat"] - df["gamma_over_eta"]

    rows: list[dict] = []
    for method in METHODS:
        m = df[df["method"] == method]
        for parameter in PARAMETERS:
            err = m[f"err_{parameter}"].to_numpy(dtype=float)
            rows.append(
                {
                    "method": method,
                    "parameter": parameter,
                    "bias": float(np.mean(err)),
                    "sd": float(np.std(err, ddof=1)),
                    "rmse": float(np.sqrt(np.mean(err**2))),
                    "n_predictions": int(err.size),
                }
            )
    return pd.DataFrame(rows)


def draw_metric_panel(ax: plt.Axes, metrics: pd.DataFrame, metric: str, title: str) -> None:
    x = np.arange(len(PARAMETERS), dtype=float)
    offsets = {"Direct-MLP": -0.09, "MDM-Vector-MLP": 0.09}
    for method in METHODS:
        sub = metrics[metrics["method"] == method].set_index("parameter")
        y = np.array([sub.loc[p, metric] for p in PARAMETERS])
        ax.plot(
            x + offsets[method],
            y,
            marker=MARKERS[method],
            linestyle="none",
            markersize=6,
            color=COLORS[method],
            label=method,
        )
    if metric == "bias":
        ax.axhline(0, color="#666666", linewidth=0.8, linestyle="--")
    ax.set_xticks(x, PARAM_LABELS)
    ax.set_title(title, loc="left", fontweight="bold")
    ax.spines[["top", "right"]].set_visible(False)
    ax.grid(axis="y", color="#D9D9D9", linewidth=0.6, alpha=0.7)


def build_current_evidence_figure(track_summary: pd.DataFrame, metrics: pd.DataFrame) -> None:
    configure_style()
    fig = plt.figure(figsize=(11.0, 6.2), constrained_layout=True)
    gs = fig.add_gridspec(2, 3, height_ratios=[1.25, 1.0])
    ax0 = fig.add_subplot(gs[0, :])
    x = np.arange(len(TRACKS), dtype=float)
    offsets = {"Direct-MLP": -0.08, "MDM-Vector-MLP": 0.08}
    for method in METHODS:
        sub = track_summary[track_summary["method"] == method].set_index("track")
        y = np.array([sub.loc[t, "mean_J1"] for t in TRACKS])
        sd = np.array([sub.loc[t, "sd_J1_across_models"] for t in TRACKS])
        ax0.errorbar(
            x + offsets[method],
            y,
            yerr=sd,
            color=COLORS[method],
            marker=MARKERS[method],
            linestyle="-",
            linewidth=1.5,
            markersize=6,
            capsize=3,
            label=method,
        )
    ax0.set_xticks(x, TRACK_LABELS)
    ax0.set_ylabel(r"平均 $J_1$")
    ax0.set_title("A  现有 P4 封存比较：误差线为 15 个模型的 SD", loc="left", fontweight="bold")
    ax0.legend(frameon=False, ncol=2)
    ax0.spines[["top", "right"]].set_visible(False)
    ax0.grid(axis="y", color="#D9D9D9", linewidth=0.6, alpha=0.7)

    draw_metric_panel(fig.add_subplot(gs[1, 0]), metrics, "bias", "B  标准化 Bias")
    draw_metric_panel(fig.add_subplot(gs[1, 1]), metrics, "sd", "C  标准化 SD")
    draw_metric_panel(fig.add_subplot(gs[1, 2]), metrics, "rmse", "D  标准化 RMSE")

    handles, labels = fig.axes[-1].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=2, frameon=False)
    fig.savefig(OUT / "fig_part2_current_evidence.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / "fig_part2_current_evidence.pdf", bbox_inches="tight")
    plt.close(fig)


def build_domain_design_figure() -> None:
    configure_style()
    fig, ax = plt.subplots(figsize=(10.0, 4.2), constrained_layout=True)
    ax.axvspan(1.5, 5.0, ymin=0.36, ymax=0.76, color="#DCEAF7", alpha=0.85)
    ax.plot([1.5, 5.0], [1.0, 1.0], color="#0072B2", linewidth=2.0)
    ax.text(3.25, 1.43, r"Study01 训练域 $\beta\in[1.5,5.0]$",
            ha="center", va="bottom", fontweight="bold")

    seen = np.arange(1.5, 5.01, 0.5)
    interp = np.arange(1.75, 4.76, 0.5)
    near_ood = np.array([1.25, 5.25])
    far_ood = np.array([0.75, 1.0, 5.5, 5.75])
    ax.scatter(seen, np.full_like(seen, 1.0), marker="o", s=65,
               color="#0072B2", label="Study01 已见网格")
    ax.scatter(interp, np.full_like(interp, 0.35), marker="o", s=58,
               facecolors="white", edgecolors="#009E73", linewidths=1.5,
               label="域内插值")
    ax.scatter(near_ood, np.full_like(near_ood, 0.35), marker="^", s=70,
               color="#D55E00", label="近域外")
    ax.scatter(far_ood, np.full_like(far_ood, 0.35), marker="X", s=70,
               color="#000000", label="远域外")

    ax.text(3.25, 0.02, "同一训练模型上的连续 β 泛化测试",
            ha="center", va="bottom", color="#333333")
    ax.set_xlim(0.5, 6.0)
    ax.set_ylim(-0.05, 1.75)
    ax.set_yticks([])
    ax.set_xlabel(r"形状参数 $\beta$")
    ax.set_title("Study01 对齐训练空间与连续 β 泛化位置", loc="left", fontweight="bold")
    ax.spines[["left", "right", "top"]].set_visible(False)
    ax.grid(axis="x", color="#E3E3E3", linewidth=0.6)
    ax.legend(loc="lower center", bbox_to_anchor=(0.5, -0.38),
              ncol=4, frameon=False)
    fig.savefig(OUT / "fig_part2_domain_design.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / "fig_part2_domain_design.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    track_summary = load_track_summary()
    metrics = load_parameter_metrics()
    track_summary.to_csv(OUT / "current_track_summary.csv", index=False)
    metrics.to_csv(OUT / "current_parameter_metrics.csv", index=False)
    build_current_evidence_figure(track_summary, metrics)
    build_domain_design_figure()


if __name__ == "__main__":
    main()
