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


# Editable SVG text and publication-style defaults.
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
plt.rcParams["legend.frameon"] = False
plt.rcParams["xtick.major.width"] = 0.7
plt.rcParams["ytick.major.width"] = 0.7


def load_sample() -> np.ndarray:
    values: list[float] = []
    with (TASK_DIR / "samples.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if int(row["sample_size"]) == 7 and int(row["sample_id"]) == 5:
                values.append(float(row["value"]))
    return np.sort(np.asarray(values, dtype=float))


def ls_profile(sample: np.ndarray, gamma_grid: np.ndarray) -> np.ndarray:
    n = sample.size
    x = log_weibull_order_stat_means(n)
    x_bar = float(np.mean(x))
    sxx = float(np.sum((x - x_bar) ** 2))
    values = np.full(gamma_grid.shape, np.nan, dtype=float)
    for index, gamma in enumerate(gamma_grid):
        shifted = sample - gamma
        if np.any(shifted <= 0):
            continue
        y = np.log(shifted)
        y_bar = float(np.mean(y))
        sy2_total = float(np.sum((y - y_bar) ** 2))
        slope = float(np.sum((x - x_bar) * (y - y_bar))) / sxx
        if slope <= 0 or sy2_total <= 0:
            continue
        intercept = y_bar - slope * x_bar
        residuals = y - (intercept + slope * x)
        residual_variance = float(np.sum(residuals**2)) / (n - 2)
        if residual_variance > 0:
            values[index] = (sy2_total / (n - 1)) / residual_variance
    return values


def lre_profile(sample: np.ndarray, gamma_grid: np.ndarray) -> np.ndarray:
    n = sample.size
    ranks = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    y = np.log(-np.log(1 - ranks))
    values = np.full(gamma_grid.shape, np.nan, dtype=float)
    for index, gamma in enumerate(gamma_grid):
        shifted = sample - gamma
        if np.any(shifted <= 0):
            continue
        corr = np.corrcoef(np.log(shifted), y)[0, 1]
        if np.isfinite(corr):
            values[index] = corr**2
    return values


sample = load_sample()
t_min = float(sample[0])
gamma_true = 3000.0
gamma_grid = np.linspace(0.0, t_min * (1.0 - 1e-6), 1601)
ls_f = ls_profile(sample, gamma_grid)
lre_r2 = lre_profile(sample, gamma_grid)

ls_best_index = int(np.nanargmax(ls_f))
lre_best_index = int(np.nanargmax(lre_r2))
assert gamma_grid[ls_best_index] == 0.0
assert gamma_grid[lre_best_index] == 0.0

source_path = OUT_DIR / "LS_LRE位置参数零值机制图_源数据.csv"
with source_path.open("w", encoding="utf-8-sig", newline="") as handle:
    writer = csv.writer(handle)
    writer.writerow(["gamma_candidate", "ls_F_ratio", "lre_rho_squared"])
    writer.writerows(zip(gamma_grid, ls_f, lre_r2))

curve_color = "#0F4D92"
boundary_color = "#B64342"
truth_color = "#42949E"
minimum_color = "#767676"

fig, axes = plt.subplots(1, 2, figsize=(183 / 25.4, 86 / 25.4), sharex=True)

panels = [
    (axes[0], ls_f, "a", "LS：F 比剖面", "F 比"),
    (axes[1], lre_r2, "b", "LRE：相关系数平方剖面", r"$\rho^2$"),
]
for ax, values, label, title, ylabel in panels:
    ax.plot(gamma_grid, values, color=curve_color, linewidth=1.7, zorder=2)
    ax.scatter([0], [values[0]], s=28, marker="D", color=boundary_color,
               edgecolor="white", linewidth=0.5, zorder=5, label=r"估计值 $\hat{\gamma}=0$")
    ax.axvline(gamma_true, color=truth_color, linestyle="--", linewidth=1.15,
               label=r"真实值 $\gamma=3000$")
    ax.axvline(t_min, color=minimum_color, linestyle=":", linewidth=1.15,
               label=rf"$t_{{(1)}}={t_min:.1f}$")
    ax.annotate(
        "约束区间左端\n目标函数在此最大",
        xy=(0, values[0]),
        xytext=(0.16, 0.80),
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": boundary_color, "lw": 0.9},
        color=boundary_color,
        ha="left",
        va="top",
        fontsize=6.8,
    )
    ax.set_title(title, loc="left", fontsize=8.2, pad=6)
    ax.set_xlabel(r"候选位置参数 $\gamma$")
    ax.set_ylabel(ylabel)
    ax.set_xlim(0, t_min * 1.015)
    ax.grid(axis="y", color="#E5E7EB", linewidth=0.55)
    ax.text(-0.12, 1.06, label, transform=ax.transAxes, fontsize=9,
            fontweight="bold", ha="left", va="bottom")

handles, labels = axes[1].get_legend_handles_labels()
fig.legend(handles, labels, loc="lower center", bbox_to_anchor=(0.5, 0.035),
           ncol=3, handlelength=2.2, columnspacing=1.5)
fig.suptitle(
    "位置参数零值的形成机制：目标函数的受约束边界最优\n"
    "W(2,1000,3000)，n=7，第5组样本",
    fontsize=9.2,
    fontweight="bold",
    y=1.01,
)
fig.subplots_adjust(left=0.085, right=0.985, top=0.79, bottom=0.23, wspace=0.30)

base = OUT_DIR / "LS_LRE位置参数零值机制图"
fig.savefig(base.with_suffix(".svg"), bbox_inches="tight")
fig.savefig(base.with_suffix(".pdf"), bbox_inches="tight")
fig.savefig(base.with_suffix(".png"), dpi=600, bbox_inches="tight")
fig.savefig(base.with_suffix(".tiff"), dpi=600, bbox_inches="tight")
fig.savefig(DELIVERY_DIR / "LS_LRE位置参数零值机制图.png", dpi=600, bbox_inches="tight")
plt.close(fig)

print(
    {
        "sample_min": t_min,
        "ls_gamma_hat": float(gamma_grid[ls_best_index]),
        "lre_gamma_hat": float(gamma_grid[lre_best_index]),
        "ls_F_at_zero": float(ls_f[0]),
        "ls_F_at_true": float(np.interp(gamma_true, gamma_grid, ls_f)),
        "lre_r2_at_zero": float(lre_r2[0]),
        "lre_r2_at_true": float(np.interp(gamma_true, gamma_grid, lre_r2)),
    }
)
