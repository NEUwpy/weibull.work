from __future__ import annotations

import csv
import math
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


ROOT = Path(__file__).resolve().parents[3]
TASK_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent
DELIVERY_DIR = TASK_DIR / "260825给老师"

sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "python" / "methods"))

from lse import log_weibull_order_stat_means  # noqa: E402


plt.rcParams["font.family"] = "sans-serif"
plt.rcParams["font.sans-serif"] = [
    "Microsoft YaHei",
    "Noto Sans SC",
    "Arial",
    "DejaVu Sans",
    "sans-serif",
]
plt.rcParams["svg.fonttype"] = "none"
plt.rcParams["pdf.fonttype"] = 42
plt.rcParams["font.size"] = 7.2
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False
plt.rcParams["xtick.major.width"] = 0.7
plt.rcParams["ytick.major.width"] = 0.7


def load_sample() -> np.ndarray:
    values: list[float] = []
    with (TASK_DIR / "samples.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row["sample_size"]) == 7 and int(row["sample_id"]) == 5:
                values.append(float(row["value"]))
    return np.sort(np.asarray(values, dtype=float))


def linear_fit(x: np.ndarray, y: np.ndarray) -> tuple[float, float, np.ndarray]:
    slope, intercept = np.polyfit(x, y, 1)
    fitted = intercept + slope * x
    return float(slope), float(intercept), fitted


def ls_coordinates(sample: np.ndarray, gamma: float) -> dict[str, object]:
    x = log_weibull_order_stat_means(sample.size)
    y = np.log(sample - gamma)
    slope, intercept, fitted = linear_fit(x, y)
    total_variance = float(np.sum((y - np.mean(y)) ** 2)) / (sample.size - 1)
    residual_variance = float(np.sum((y - fitted) ** 2)) / (sample.size - 2)
    return {
        "x": x,
        "y": y,
        "fitted": fitted,
        "score": total_variance / residual_variance,
        "shape": 1.0 / slope,
        "slope": slope,
        "intercept": intercept,
    }


def lre_coordinates(sample: np.ndarray, gamma: float) -> dict[str, object]:
    ranks = (np.arange(1, sample.size + 1) - 0.3) / (sample.size + 0.4)
    x = np.log(sample - gamma)
    y = np.log(-np.log(1 - ranks))
    slope, intercept, fitted = linear_fit(x, y)
    rho_squared = float(np.corrcoef(x, y)[0, 1] ** 2)
    return {
        "x": x,
        "y": y,
        "fitted": fitted,
        "score": rho_squared,
        "shape": slope,
        "slope": slope,
        "intercept": intercept,
    }


sample = load_sample()
cases = [
    ("LS", 0.0, ls_coordinates(sample, 0.0)),
    ("LS", 3000.0, ls_coordinates(sample, 3000.0)),
    ("LRE", 0.0, lre_coordinates(sample, 0.0)),
    ("LRE", 3000.0, lre_coordinates(sample, 3000.0)),
]

source_path = OUT_DIR / "LS_LRE回归原理图_源数据.csv"
with source_path.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow([
        "method", "gamma_used", "order", "sample_value", "regression_x",
        "regression_y", "fitted_y", "residual", "criterion", "shape_hat",
    ])
    for method, gamma, fit in cases:
        for index, (x, y, fitted) in enumerate(
            zip(fit["x"], fit["y"], fit["fitted"]), start=1
        ):
            writer.writerow([
                method, gamma, index, sample[index - 1], x, y, fitted,
                y - fitted, fit["score"], fit["shape"],
            ])


line_color = "#0F4D92"
point_color = "#3775BA"
first_color = "#B64342"
residual_color = "#A8A8A8"
grid_color = "#E5E7EB"

fig, axes = plt.subplots(2, 2, figsize=(183 / 25.4, 142 / 25.4))

panel_specs = [
    (axes[0, 0], "a", "LS，γ=0（被选择）", cases[0][2], "LS"),
    (axes[0, 1], "b", "LS，γ=3000（未选择）", cases[1][2], "LS"),
    (axes[1, 0], "c", "LRE，γ=0（被选择）", cases[2][2], "LRE"),
    (axes[1, 1], "d", "LRE，γ=3000（未选择）", cases[3][2], "LRE"),
]

for ax, panel, title, fit, method in panel_specs:
    x = np.asarray(fit["x"], dtype=float)
    y = np.asarray(fit["y"], dtype=float)
    fitted = np.asarray(fit["fitted"], dtype=float)

    order = np.argsort(x)
    for xi, yi, yhat in zip(x, y, fitted):
        ax.plot([xi, xi], [yi, yhat], color=residual_color, linewidth=0.8, zorder=1)
    ax.plot(x[order], fitted[order], color=line_color, linewidth=1.5, zorder=2)
    ax.scatter(x[1:], y[1:], s=24, color=point_color, edgecolor="white",
               linewidth=0.45, zorder=3)
    ax.scatter([x[0]], [y[0]], s=38, color=first_color, edgecolor="white",
               linewidth=0.55, zorder=4)
    ax.annotate(
        "最小观测值",
        xy=(x[0], y[0]),
        xytext=(0.12, 0.15 if method == "LS" else 0.22),
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": first_color, "lw": 0.8},
        color=first_color,
        fontsize=6.7,
        ha="left",
    )
    score_name = "F" if method == "LS" else r"$\rho^2$"
    ax.text(
        0.97,
        0.06,
        f"{score_name} = {fit['score']:.3f}\n"
        rf"$\hat{{\alpha}}$ = {fit['shape']:.2f}",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.0,
        bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": "#CBD5E1", "lw": 0.6},
    )
    ax.set_title(title, loc="left", fontsize=8.1, pad=5)
    ax.text(-0.11, 1.03, panel, transform=ax.transAxes, fontsize=9,
            fontweight="bold", ha="left", va="bottom")
    ax.grid(color=grid_color, linewidth=0.55)

axes[0, 0].set_xlabel(r"理论顺序统计量 $E[W_{(i:n)}]$")
axes[0, 1].set_xlabel(r"理论顺序统计量 $E[W_{(i:n)}]$")
axes[0, 0].set_ylabel(r"$\ln(t_i-\gamma)$")
axes[0, 1].set_ylabel(r"$\ln(t_i-\gamma)$")
axes[1, 0].set_xlabel(r"$\ln(t_i-\gamma)$")
axes[1, 1].set_xlabel(r"$\ln(t_i-\gamma)$")
axes[1, 0].set_ylabel(r"$\ln[-\ln(1-F_i)]$")
axes[1, 1].set_ylabel(r"$\ln[-\ln(1-F_i)]$")

fig.suptitle(
    "为什么LS与LRE会选择γ=0：回归直线性比较\n"
    "W(2,1000,3000)，n=7，第5组样本",
    fontsize=9.4,
    fontweight="bold",
    y=0.985,
)
fig.text(
    0.5,
    0.018,
    "灰线表示回归残差，红点为最小观测值；F比或ρ²越大，表示线性拟合越好。",
    ha="center",
    va="bottom",
    fontsize=6.9,
    color="#4D4D4D",
)
fig.subplots_adjust(left=0.09, right=0.985, top=0.86, bottom=0.105,
                    hspace=0.43, wspace=0.30)

base = OUT_DIR / "LS_LRE回归原理图"
fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
fig.savefig(base.with_suffix(".png"), dpi=600, bbox_inches="tight")
fig.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
fig.savefig(DELIVERY_DIR / "LS_LRE回归原理图.png", dpi=600, bbox_inches="tight")
plt.close(fig)

print({
    "ls_gamma_0": {"F": cases[0][2]["score"], "shape": cases[0][2]["shape"]},
    "ls_gamma_3000": {"F": cases[1][2]["score"], "shape": cases[1][2]["shape"]},
    "lre_gamma_0": {"rho2": cases[2][2]["score"], "shape": cases[2][2]["shape"]},
    "lre_gamma_3000": {"rho2": cases[3][2]["score"], "shape": cases[3][2]["shape"]},
})
