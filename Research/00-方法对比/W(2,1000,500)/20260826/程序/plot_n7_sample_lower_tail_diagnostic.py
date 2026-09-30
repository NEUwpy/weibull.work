"""Plot the real 50 n=7 samples and diagnose isolated lower-tail minima."""

from __future__ import annotations

import json
import os
from pathlib import Path

import matplotlib as mpl
import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
from scipy.optimize import minimize_scalar


WORK_DIR = Path(__file__).resolve().parent
SOURCE_PATH = WORK_DIR / "all_n7_samples_for_check.json"
OUTPUT_PATH = (
    Path(r"D:\weibull\docs")
    / "临时任务-W2-1000-3000-MDM偏移量估计-20260825"
    / "260826位置参数500"
    / "n7样本_排序值与下尾部异常诊断.png"
)
os.environ.setdefault("MPLCONFIGDIR", str(WORK_DIR / "mplconfig"))


def choose_chinese_font() -> str:
    available = {font.name for font in fm.fontManager.ttflist}
    for name in (
        "Microsoft YaHei",
        "Microsoft JhengHei",
        "SimHei",
        "Noto Sans CJK SC",
        "Arial Unicode MS",
    ):
        if name in available:
            return name
    return "DejaVu Sans"


FONT = choose_chinese_font()
mpl.rcParams.update(
    {
        "font.family": "sans-serif",
        "font.sans-serif": [FONT, "Arial", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "font.size": 9.5,
        "axes.spines.right": False,
        "axes.spines.top": False,
        "axes.linewidth": 0.8,
        "xtick.major.width": 0.8,
        "ytick.major.width": 0.8,
        "legend.frameon": False,
        "pdf.fonttype": 42,
        "svg.fonttype": "none",
    }
)


def profile_gradient_at_zero(sample: np.ndarray, z: np.ndarray) -> float:
    def eta_std(shape: float) -> float:
        q = z ** (-1.0 / shape)
        return float(np.std(sample * q, ddof=1))

    result = minimize_scalar(
        eta_std,
        bounds=(0.1, 15.0),
        method="bounded",
        options={"xatol": 1e-12},
    )
    shape = float(result.x)
    q = z ** (-1.0 / shape)
    a = sample * q
    return float(-np.cov(a, q, ddof=1)[0, 1] / np.std(a, ddof=1))


def main() -> None:
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    ids = np.array([row["sample_id"] for row in payload["rows"]], dtype=int)
    samples = np.array([row["values"] for row in payload["rows"]], dtype=float)

    n = samples.shape[1]
    order = np.arange(1, n + 1)
    bernard = (order - 0.3) / (n + 0.4)
    z = -np.log1p(-bernard)
    theory = 500.0 + 1000.0 * np.sqrt(z)
    gradients = np.array([profile_gradient_at_zero(row, z) for row in samples])
    flagged = gradients > 0.1

    min_deviation = samples[:, 0] - theory[0]
    first_gap = samples[:, 1] - samples[:, 0]
    theory_gap = theory[1] - theory[0]

    red = "#D55E00"
    blue = "#0072B2"
    gray = "#9AA0A6"
    dark = "#243447"
    grid = "#E5E7EB"
    pale = "#F7F8FA"

    fig = plt.figure(figsize=(12.6, 5.7), constrained_layout=False)
    gs = fig.add_gridspec(
        1,
        2,
        width_ratios=(1.15, 1.0),
        left=0.065,
        right=0.985,
        bottom=0.145,
        top=0.855,
        wspace=0.27,
    )
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    ax1.set_facecolor("white")
    for sample_id, row, is_flagged in zip(ids, samples, flagged):
        if is_flagged:
            continue
        ax1.plot(
            order,
            row,
            color=gray,
            alpha=0.34,
            linewidth=0.72,
            marker="o",
            markersize=2.0,
            markeredgewidth=0,
            zorder=1,
        )
    ax1.plot(
        order,
        theory,
        color="#111827",
        linestyle=(0, (5, 3)),
        linewidth=2.0,
        marker="D",
        markersize=4.0,
        label="Bernard中位秩对应的理论分位数",
        zorder=4,
    )
    color_by_id = {4: red, 32: blue}
    for sample_id in (4, 32):
        idx = int(np.where(ids == sample_id)[0][0])
        ax1.plot(
            order,
            samples[idx],
            color=color_by_id[sample_id],
            linewidth=2.25,
            marker="o",
            markersize=4.8,
            markeredgecolor="white",
            markeredgewidth=0.7,
            label=f"第{sample_id}组，g(0)={gradients[idx]:.3f}",
            zorder=5,
        )
    ax1.set_xlim(0.75, 7.25)
    ax1.set_ylim(450, 3650)
    ax1.set_xticks(order)
    ax1.set_xlabel("顺序统计量位置 $i$")
    ax1.set_ylabel("排序样本值 $t_{(i)}$")
    ax1.set_title("a  50组排序样本的整体位置", loc="left", fontweight="bold", pad=10)
    ax1.grid(axis="y", color=grid, linewidth=0.7, linestyle=(0, (2, 3)))
    ax1.legend(loc="upper left", fontsize=8.2, handlelength=2.8)
    ax1.text(
        0.98,
        0.035,
        "灰线：其余48组真实样本",
        transform=ax1.transAxes,
        ha="right",
        va="bottom",
        color="#6B7280",
        fontsize=8.2,
    )

    ax2.set_facecolor("white")
    ax2.axvspan(-320, 0, color=pale, zorder=0)
    ax2.axvline(0, color="#4B5563", linewidth=1.0, linestyle=(0, (4, 3)), zorder=1)
    ax2.axhline(
        theory_gap,
        color="#4B5563",
        linewidth=1.0,
        linestyle=(0, (4, 3)),
        zorder=1,
    )
    ax2.scatter(
        min_deviation[~flagged],
        first_gap[~flagged],
        s=30,
        color="#B7BDC5",
        edgecolor="white",
        linewidth=0.55,
        alpha=0.92,
        zorder=2,
    )
    ax2.scatter(
        0,
        theory_gap,
        marker="*",
        s=125,
        color="#111827",
        edgecolor="white",
        linewidth=0.7,
        zorder=5,
    )
    ax2.annotate(
        "理论位置",
        xy=(0, theory_gap),
        xytext=(38, 155),
        textcoords="offset points",
        arrowprops={"arrowstyle": "-", "color": "#4B5563", "lw": 0.8},
        fontsize=8.4,
        color=dark,
        ha="left",
    )

    label_offsets = {4: (15, -38), 32: (16, 10)}
    for sample_id in (4, 32):
        idx = int(np.where(ids == sample_id)[0][0])
        ax2.scatter(
            min_deviation[idx],
            first_gap[idx],
            s=72,
            color=color_by_id[sample_id],
            edgecolor="white",
            linewidth=0.9,
            zorder=6,
        )
        ax2.annotate(
            f"第{sample_id}组\n偏差={min_deviation[idx]:.1f}\n间距={first_gap[idx]:.1f}",
            xy=(min_deviation[idx], first_gap[idx]),
            xytext=label_offsets[sample_id],
            textcoords="offset points",
            color=color_by_id[sample_id],
            fontsize=8.5,
            fontweight="bold",
            ha="left",
            va="center",
            arrowprops={
                "arrowstyle": "->",
                "color": color_by_id[sample_id],
                "lw": 1.0,
                "shrinkA": 3,
                "shrinkB": 4,
            },
            zorder=7,
        )

    for sample_id, offset in ((6, (-2, -19)), (8, (-2, 10))):
        idx = int(np.where(ids == sample_id)[0][0])
        ax2.scatter(
            min_deviation[idx],
            first_gap[idx],
            s=48,
            facecolor="white",
            edgecolor="#6B7280",
            linewidth=1.0,
            zorder=4,
        )
        ax2.annotate(
            f"第{sample_id}组，g(0)={gradients[idx]:.3f}",
            xy=(min_deviation[idx], first_gap[idx]),
            xytext=offset,
            textcoords="offset points",
            fontsize=7.6,
            color="#6B7280",
            ha="left",
            va="center",
        )

    ax2.set_xlim(-320, 510)
    ax2.set_ylim(0, 560)
    ax2.set_xlabel("最小值相对第一理论分位数的偏差  $t_{(1)}-Q_1$")
    ax2.set_ylabel("前两顺序统计量间距  $t_{(2)}-t_{(1)}$")
    ax2.set_title("b  下尾部“孤立最小值”诊断", loc="left", fontweight="bold", pad=10)
    ax2.grid(color=grid, linewidth=0.7, linestyle=(0, (2, 3)), zorder=0)
    ax2.text(
        0.97,
        0.96,
        f"理论间距={theory_gap:.1f}\n其余48组间距中位数={np.median(first_gap[~flagged]):.1f}",
        transform=ax2.transAxes,
        ha="right",
        va="top",
        fontsize=8.2,
        color="#4B5563",
        bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "#D1D5DB", "lw": 0.7},
        zorder=8,
    )

    fig.suptitle(
        "n=7样本的排序位置与下尾部结构",
        x=0.065,
        y=0.955,
        ha="left",
        fontsize=15,
        fontweight="bold",
        color="#111827",
    )
    fig.text(
        0.065,
        0.905,
        "分布：W(2,1000,500)；红、蓝两组满足 g(0)>0.1。最小值偏低并非充分条件，关键是它是否相对后续样本孤立。",
        ha="left",
        va="center",
        fontsize=9.2,
        color="#4B5563",
    )
    fig.text(
        0.985,
        0.045,
        "数据：当前工作簿中的50组真实生成样本；理论点由Bernard中位秩计算。",
        ha="right",
        va="bottom",
        fontsize=7.8,
        color="#6B7280",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=600, facecolor="white", bbox_inches="tight", pad_inches=0.08)

    print(
        json.dumps(
            {
                "output": str(OUTPUT_PATH),
                "font": FONT,
                "sample_count": int(len(ids)),
                "flagged_ids": ids[flagged].tolist(),
                "q1": float(theory[0]),
                "q2": float(theory[1]),
                "theory_gap": float(theory_gap),
                "other_gap_median": float(np.median(first_gap[~flagged])),
                "sample4": {
                    "g0": float(gradients[ids == 4][0]),
                    "min_deviation": float(min_deviation[ids == 4][0]),
                    "first_gap": float(first_gap[ids == 4][0]),
                },
                "sample32": {
                    "g0": float(gradients[ids == 32][0]),
                    "min_deviation": float(min_deviation[ids == 32][0]),
                    "first_gap": float(first_gap[ids == 32][0]),
                },
                "axes": len(fig.axes),
                "titles": [ax.get_title(loc="left") for ax in fig.axes],
                "xlabels": [ax.get_xlabel() for ax in fig.axes],
                "ylabels": [ax.get_ylabel() for ax in fig.axes],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
