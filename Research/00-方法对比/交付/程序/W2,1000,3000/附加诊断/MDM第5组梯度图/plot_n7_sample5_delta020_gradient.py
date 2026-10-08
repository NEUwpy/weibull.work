from __future__ import annotations

import csv
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

from studies.common.runner import run_method  # noqa: E402


SAMPLE_SIZE = 7
SAMPLE_ID = 5
OFFSET = 0.20
GAMMA_STEPS = 500


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
plt.rcParams["font.size"] = 7.4
plt.rcParams["axes.linewidth"] = 0.8
plt.rcParams["axes.spines.top"] = False
plt.rcParams["axes.spines.right"] = False
plt.rcParams["legend.frameon"] = False
plt.rcParams["xtick.major.width"] = 0.7
plt.rcParams["ytick.major.width"] = 0.7


CURVE_COLOR = "#0072B2"
TARGET_COLOR = "#B23A48"
ROOT_COLOR = "#009E73"
MAX_COLOR = "#E69F00"
BOUND_COLOR = "#6B7280"
PROBE_COLOR = "#CC79A7"


def load_sample() -> np.ndarray:
    values: list[float] = []
    with (TASK_DIR / "samples.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if (
                int(row["sample_size"]) == SAMPLE_SIZE
                and int(row["sample_id"]) == SAMPLE_ID
            ):
                values.append(float(row["value"]))
    sample = np.sort(np.asarray(values, dtype=float))
    if sample.size != SAMPLE_SIZE:
        raise AssertionError(f"Expected {SAMPLE_SIZE} observations, found {sample.size}")
    return sample


def interpolate_crossings(gammas: np.ndarray, gradients: np.ndarray) -> list[float]:
    differences = gradients - OFFSET
    indexes = np.where(differences[:-1] * differences[1:] <= 0)[0]
    crossings: list[float] = []
    for index in indexes:
        x1, x2 = gammas[index], gammas[index + 1]
        y1, y2 = differences[index], differences[index + 1]
        crossing = x1 - y1 * (x2 - x1) / (y2 - y1)
        crossings.append(float(crossing))
    return crossings


def main() -> None:
    sample = load_sample()
    result = run_method(
        "mdm",
        sample,
        offset=OFFSET,
        gamma_steps=GAMMA_STEPS,
        trace=True,
    )
    trace = result["trace_data"]
    info = result["extra"]["solution_info"]

    actual_points = [
        point for point in trace["grad_gamma_curve"] if not point.get("virtual", False)
    ]
    actual_points.sort(key=lambda point: point["gamma"])
    gammas = np.asarray([point["gamma"] for point in actual_points], dtype=float)
    gradients = np.asarray([point["gradient"] for point in actual_points], dtype=float)
    crossings = interpolate_crossings(gammas, gradients)

    if len(crossings) != 2:
        raise AssertionError(f"Expected two actual crossings, found {crossings}")

    gamma_left, gamma_right = crossings
    max_index = int(np.argmax(gradients))
    max_gamma = float(gammas[max_index])
    max_gradient = float(gradients[max_index])
    sample_min = float(sample[0])
    probe_zone_left = sample_min * (1.0 - 1e-3)
    last_probe_gamma = float(info["root_bracket"]["left"]["gamma"])
    last_probe_gradient = float(info["root_bracket"]["left"]["gradient"])
    virtual_gamma = float(info["root_bracket"]["right"]["gamma"])
    virtual_gradient = float(info["root_bracket"]["right"]["gradient"])

    if not (
        gamma_left < max_gamma < gamma_right < probe_zone_left < sample_min
        and max_gradient > OFFSET
        and last_probe_gradient < OFFSET
        and info["root_solver"] == "right_edge_fit"
    ):
        raise AssertionError("The expected non-monotone/right-edge-fit mechanism changed")

    fig, axes = plt.subplots(1, 2, figsize=(183 / 25.4, 98 / 25.4))
    panels = [
        (axes[0], (0.0, sample_min * 1.008), (-0.025, 0.235), "a", "完整搜索区间"),
        (axes[1], (3000.0, sample_min * 1.0015), (0.145, 0.225), "b", "右端局部放大"),
    ]

    for ax, xlim, ylim, label, title in panels:
        ax.plot(
            gammas,
            gradients,
            color=CURVE_COLOR,
            linewidth=1.65,
            label="实际计算的梯度曲线",
            zorder=3,
        )
        ax.axhline(
            OFFSET,
            color=TARGET_COLOR,
            linewidth=1.1,
            linestyle="-.",
            label=rf"偏移量判据 $\delta={OFFSET:.2f}$",
            zorder=2,
        )
        ax.axvline(
            sample_min,
            color=BOUND_COLOR,
            linewidth=1.0,
            linestyle=":",
            label=rf"支持边界 $t_{{(1)}}={sample_min:.3f}$",
            zorder=2,
        )
        ax.scatter(
            crossings,
            [OFFSET, OFFSET],
            s=31,
            marker="o",
            color=ROOT_COLOR,
            edgecolor="white",
            linewidth=0.6,
            zorder=6,
            label="实际交点",
        )
        ax.scatter(
            [max_gamma],
            [max_gradient],
            s=31,
            marker="^",
            color=MAX_COLOR,
            edgecolor="white",
            linewidth=0.6,
            zorder=6,
            label="梯度峰值",
        )
        ax.scatter(
            [virtual_gamma],
            [virtual_gradient],
            s=42,
            marker="X",
            color=TARGET_COLOR,
            edgecolor="white",
            linewidth=0.6,
            zorder=7,
            label="程序补出的虚拟端点",
        )
        ax.set_xlim(*xlim)
        ax.set_ylim(*ylim)
        ax.set_xlabel(r"候选位置参数 $\gamma$")
        ax.set_ylabel("标准梯度")
        ax.set_title(title, loc="left", fontsize=8.2, pad=5)
        ax.grid(axis="y", color="#E5E7EB", linewidth=0.55)
        ax.text(
            -0.11,
            1.05,
            label,
            transform=ax.transAxes,
            fontsize=9,
            fontweight="bold",
            ha="left",
            va="bottom",
        )

    axes[0].annotate(
        f"内部存在两个真实交点\n"
        rf"$\gamma_1\approx{gamma_left:.1f}$，$\gamma_2\approx{gamma_right:.1f}$",
        xy=(gamma_right, OFFSET),
        xytext=(0.34, 0.69),
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": ROOT_COLOR, "lw": 0.9},
        color=ROOT_COLOR,
        fontsize=7.0,
        ha="left",
        va="top",
    )
    axes[0].annotate(
        rf"实际峰值 {max_gradient:.3f}>0.20",
        xy=(max_gamma, max_gradient),
        xytext=(0.47, 0.93),
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": MAX_COLOR, "lw": 0.9},
        color=MAX_COLOR,
        fontsize=6.9,
        ha="left",
        va="top",
    )

    axes[1].axvspan(
        probe_zone_left,
        sample_min,
        color=PROBE_COLOR,
        alpha=0.13,
        zorder=1,
    )
    axes[1].scatter(
        [last_probe_gamma],
        [last_probe_gradient],
        s=28,
        marker="s",
        facecolor="white",
        edgecolor=PROBE_COLOR,
        linewidth=1.1,
        zorder=7,
        label="最靠近边界的实际探测点",
    )
    axes[1].plot(
        [last_probe_gamma, virtual_gamma],
        [last_probe_gradient, virtual_gradient],
        color=TARGET_COLOR,
        linewidth=1.0,
        linestyle="--",
        zorder=5,
    )
    axes[1].annotate(
        "程序只在最右侧阴影区寻找锚点\n该区梯度均低于0.20",
        xy=(probe_zone_left + 0.45 * (sample_min - probe_zone_left), 0.166),
        xytext=(0.54, 0.15),
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": PROBE_COLOR, "lw": 0.9},
        color=PROBE_COLOR,
        fontsize=6.8,
        ha="left",
        va="bottom",
    )
    axes[1].annotate(
        "应识别的右侧真实交点\n" rf"$\gamma\approx{gamma_right:.1f}$",
        xy=(gamma_right, OFFSET),
        xytext=(0.18, 0.87),
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": ROOT_COLOR, "lw": 0.9},
        color=ROOT_COLOR,
        fontsize=6.9,
        ha="left",
        va="top",
    )
    axes[1].annotate(
        "虚拟补点\n" rf"返回 $\hat{{\gamma}}={sample_min:.3f}$",
        xy=(virtual_gamma, virtual_gradient),
        xytext=(0.54, 0.76),
        textcoords="axes fraction",
        arrowprops={"arrowstyle": "->", "color": TARGET_COLOR, "lw": 0.9},
        color=TARGET_COLOR,
        fontsize=6.9,
        ha="left",
        va="top",
    )

    handles, labels = axes[1].get_legend_handles_labels()
    unique = dict(zip(labels, handles))
    fig.legend(
        unique.values(),
        unique.keys(),
        loc="lower center",
        bbox_to_anchor=(0.5, 0.008),
        ncol=4,
        fontsize=6.6,
        handlelength=2.4,
        columnspacing=1.2,
    )
    fig.suptitle(
        r"MDM梯度诊断：$n=7$、第5组、偏移量$\delta=0.20$",
        fontsize=9.4,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.145,
        "结论：曲线内部确有交点；当前结果落到样本最小值，是右端探测范围过窄并启用虚拟补点造成的。",
        ha="center",
        va="bottom",
        fontsize=7.0,
    )
    fig.subplots_adjust(left=0.08, right=0.985, top=0.84, bottom=0.31, wspace=0.29)

    stem = "n7第5组_偏移量0.20_γ梯度图"
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_DIR / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{stem}.pdf", bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{stem}.png", dpi=600, bbox_inches="tight")
    fig.savefig(OUT_DIR / f"{stem}.tiff", dpi=600, bbox_inches="tight")
    fig.savefig(DELIVERY_DIR / f"{stem}.png", dpi=600, bbox_inches="tight")
    fig.savefig(DELIVERY_DIR / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)

    print(
        {
            "sample_min": sample_min,
            "gradient_max": max_gradient,
            "gradient_max_gamma": max_gamma,
            "actual_crossings": crossings,
            "right_probe_zone": [probe_zone_left, sample_min],
            "last_probe": [last_probe_gamma, last_probe_gradient],
            "virtual_endpoint": [virtual_gamma, virtual_gradient],
            "reported_gamma_hat": result["gamma_hat"],
        }
    )


if __name__ == "__main__":
    main()
