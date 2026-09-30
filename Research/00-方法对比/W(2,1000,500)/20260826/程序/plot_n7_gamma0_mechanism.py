"""Explain why two real n=7 samples produce the MDM gamma=0 boundary solution."""

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
    / "n7样本_孤立最小值导致γ0边界解机制图.png"
)
PROVENANCE_PATH = WORK_DIR / "_n7_gamma0_mechanism_sample_provenance.md"
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
        "font.size": 9.2,
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


OFFSET = 0.10
SELECTED_IDS = (4, 8, 32, 18)
FLAGGED_IDS = (4, 32)
CONTROL_IDS = (8, 18)
COLORS = {
    4: "#D55E00",
    8: "#E69F00",
    32: "#0072B2",
    18: "#56B4E9",
}


def profile_fit(sample: np.ndarray, z: np.ndarray, gamma: float) -> tuple[float, float]:
    """Return beta*(gamma) and the minimum sample SD of pseudo-scales."""

    def eta_std(shape: float) -> float:
        q = z ** (-1.0 / shape)
        return float(np.std((sample - gamma) * q, ddof=1))

    result = minimize_scalar(
        eta_std,
        bounds=(0.1, 15.0),
        method="bounded",
        options={"xatol": 1e-12},
    )
    return float(result.x), float(result.fun)


def mechanism_at_zero(sample: np.ndarray, z: np.ndarray) -> dict[str, object]:
    beta, sigma = profile_fit(sample, z, 0.0)
    q = z ** (-1.0 / beta)
    pseudo_scale = sample * q
    covariance = float(np.cov(pseudo_scale, q, ddof=1)[0, 1])
    gradient = float(-covariance / sigma)
    return {
        "beta": beta,
        "sigma": sigma,
        "q": q,
        "pseudo_scale": pseudo_scale,
        "centered_pseudo_scale": pseudo_scale - np.mean(pseudo_scale),
        "covariance": covariance,
        "gradient": gradient,
    }


def objective_increment(
    sample: np.ndarray, z: np.ndarray, gamma_grid: np.ndarray
) -> np.ndarray:
    sigmas = np.array([profile_fit(sample, z, float(gamma))[1] for gamma in gamma_grid])
    objective = sigmas - OFFSET * gamma_grid
    return objective - objective[0]


def style_axis(ax: plt.Axes, grid_axis: str = "both") -> None:
    ax.grid(
        axis=grid_axis,
        color="#E5E7EB",
        linewidth=0.65,
        linestyle=(0, (2, 3)),
        zorder=0,
    )
    ax.tick_params(labelsize=8.2)


def draw_sorted_pair(
    ax: plt.Axes,
    order: np.ndarray,
    theory: np.ndarray,
    samples: dict[int, np.ndarray],
    first_id: int,
    control_id: int,
    panel_label: str,
) -> None:
    ax.plot(
        order,
        theory,
        color="#111827",
        linewidth=1.5,
        linestyle=(0, (3, 2)),
        marker="D",
        markersize=3.1,
        label="理论分位点",
        zorder=2,
    )
    for sample_id, linestyle, marker in (
        (first_id, "-", "o"),
        (control_id, (0, (5, 2)), "s"),
    ):
        row = samples[sample_id]
        gap = row[1] - row[0]
        ax.plot(
            order,
            row,
            color=COLORS[sample_id],
            linewidth=2.0 if sample_id == first_id else 1.55,
            linestyle=linestyle,
            marker=marker,
            markersize=4.4,
            markeredgecolor="white",
            markeredgewidth=0.55,
            label=f"第{sample_id}组：前两点间距 {gap:.1f}",
            zorder=4 if sample_id == first_id else 3,
        )
    ax.annotate(
        "孤立的最小值",
        xy=(1, samples[first_id][0]),
        xytext=(1.75, samples[first_id][0] - 105),
        arrowprops={"arrowstyle": "->", "lw": 0.9, "color": COLORS[first_id]},
        color=COLORS[first_id],
        fontsize=8.2,
        fontweight="bold",
        ha="left",
        va="top",
    )
    ax.set_xlim(0.75, 7.25)
    ax.set_ylim(430, 2100)
    ax.set_xticks(order)
    ax.set_xlabel("顺序位置 $i$")
    ax.set_ylabel("排序样本值 $t_{(i)}$")
    ax.set_title(panel_label, loc="left", fontweight="bold", fontsize=10.3, pad=7)
    ax.legend(loc="upper left", fontsize=7.5, handlelength=2.6)
    style_axis(ax, "y")


def draw_covariance_pair(
    ax: plt.Axes,
    mechanisms: dict[int, dict[str, object]],
    first_id: int,
    control_id: int,
    panel_label: str,
) -> None:
    ax.axhline(0.0, color="#6B7280", linewidth=0.85, linestyle=(0, (3, 2)), zorder=1)
    for sample_id, linestyle, marker in (
        (first_id, "-", "o"),
        (control_id, (0, (5, 2)), "s"),
    ):
        mechanism = mechanisms[sample_id]
        q = np.asarray(mechanism["q"], dtype=float)
        centered = np.asarray(mechanism["centered_pseudo_scale"], dtype=float)
        coefficient = np.polyfit(q, centered, 1)
        xline = np.linspace(float(np.min(q)), float(np.max(q)), 80)
        g0 = float(mechanism["gradient"])
        ax.plot(
            xline,
            np.polyval(coefficient, xline),
            color=COLORS[sample_id],
            linewidth=1.6,
            linestyle=linestyle,
            alpha=0.95,
            zorder=2,
        )
        ax.scatter(
            q,
            centered,
            s=28 if sample_id == first_id else 24,
            color=COLORS[sample_id],
            marker=marker,
            edgecolor="white",
            linewidth=0.55,
            label=(
                f"第{sample_id}组：Cov={float(mechanism['covariance']):+.2f}，"
                f"g(0)={g0:.3f}"
            ),
            zorder=4,
        )
        ax.annotate(
            "$i=1$",
            xy=(q[0], centered[0]),
            xytext=(5, -12 if sample_id == first_id else 7),
            textcoords="offset points",
            color=COLORS[sample_id],
            fontsize=7.5,
            fontweight="bold",
        )
    ax.set_xlabel(r"中位秩权重 $q_i=z_i^{-1/\beta^*(0)}$")
    ax.set_ylabel(r"中心化伪尺度 $a_i-\bar{a}$")
    ax.set_title(panel_label, loc="left", fontweight="bold", fontsize=10.3, pad=7)
    ax.legend(loc="lower left", fontsize=7.5, handlelength=2.4)
    style_axis(ax)


def main() -> None:
    payload = json.loads(SOURCE_PATH.read_text(encoding="utf-8"))
    all_samples = {
        int(row["sample_id"]): np.asarray(row["values"], dtype=float)
        for row in payload["rows"]
    }
    samples = {sample_id: all_samples[sample_id] for sample_id in SELECTED_IDS}

    n = len(samples[4])
    order = np.arange(1, n + 1)
    ranks = (order - 0.3) / (n + 0.4)
    z = -np.log1p(-ranks)
    theory = 500.0 + 1000.0 * np.sqrt(z)

    mechanisms = {
        sample_id: mechanism_at_zero(sample, z)
        for sample_id, sample in samples.items()
    }
    gamma_grid = np.linspace(0.0, 25.0, 201)
    objective_curves = {
        sample_id: objective_increment(sample, z, gamma_grid)
        for sample_id, sample in samples.items()
    }

    fig = plt.figure(figsize=(15.1, 8.1), constrained_layout=False)
    gs = fig.add_gridspec(
        2,
        3,
        width_ratios=(1.0, 1.0, 1.17),
        left=0.055,
        right=0.982,
        bottom=0.115,
        top=0.805,
        wspace=0.28,
        hspace=0.39,
    )
    ax_a1 = fig.add_subplot(gs[0, 0])
    ax_a2 = fig.add_subplot(gs[1, 0])
    ax_b1 = fig.add_subplot(gs[0, 1])
    ax_b2 = fig.add_subplot(gs[1, 1])
    ax_c = fig.add_subplot(gs[:, 2])

    draw_sorted_pair(ax_a1, order, theory, samples, 4, 8, "a1  第4组与最小值匹配对照")
    draw_sorted_pair(ax_a2, order, theory, samples, 32, 18, "a2  第32组与最小值匹配对照")
    draw_covariance_pair(ax_b1, mechanisms, 4, 8, "b1  排序形态传到伪尺度协方差")
    draw_covariance_pair(ax_b2, mechanisms, 32, 18, "b2  排序形态传到伪尺度协方差")

    ax_c.axhline(0.0, color="#111827", linewidth=0.9, linestyle=(0, (3, 2)), zorder=1)
    for sample_id in SELECTED_IDS:
        is_flagged = sample_id in FLAGGED_IDS
        curve = objective_curves[sample_id]
        ax_c.plot(
            gamma_grid,
            curve,
            color=COLORS[sample_id],
            linewidth=2.15 if is_flagged else 1.65,
            linestyle="-" if is_flagged else (0, (5, 2)),
            label=f"第{sample_id}组：g(0)-0.1={float(mechanisms[sample_id]['gradient']) - OFFSET:+.3f}",
            zorder=4 if is_flagged else 3,
        )
        ax_c.scatter(
            [0],
            [0],
            s=36 if is_flagged else 26,
            color=COLORS[sample_id],
            marker="o" if is_flagged else "s",
            edgecolor="white",
            linewidth=0.5,
            zorder=5,
        )
    ax_c.axvspan(0, 4, color="#F3F4F6", zorder=0)
    ax_c.annotate(
        "第4、32组从边界向右\n目标函数立即上升",
        xy=(3.0, objective_curves[4][24]),
        xytext=(7.0, max(objective_curves[4][24], objective_curves[32][24]) + 0.35),
        arrowprops={"arrowstyle": "->", "color": "#4B5563", "lw": 0.9},
        fontsize=8.5,
        color="#374151",
        ha="left",
    )
    ax_c.text(
        0.035,
        0.035,
        r"$J_{0.1}(\gamma)=\sigma_{\min}(\gamma)-0.1\gamma$" "\n"
        r"$J'_{0.1}(0+)=g(0)-0.1$",
        transform=ax_c.transAxes,
        fontsize=9.0,
        color="#374151",
        ha="left",
        va="bottom",
        bbox={"boxstyle": "round,pad=0.35", "fc": "white", "ec": "#D1D5DB", "lw": 0.7},
        zorder=6,
    )
    ax_c.set_xlim(0, 25)
    all_objective_values = np.concatenate(list(objective_curves.values()))
    lower = min(-0.6, float(np.min(all_objective_values)) * 1.08)
    upper = max(0.6, float(np.max(all_objective_values)) * 1.16)
    ax_c.set_ylim(lower, upper)
    ax_c.set_xlabel(r"从左端边界向右移动的位置参数 $\gamma$")
    ax_c.set_ylabel(r"约束目标函数增量 $J_{0.1}(\gamma)-J_{0.1}(0)$")
    ax_c.set_title(r"c  为什么取 $\hat{\gamma}=0$", loc="left", fontweight="bold", fontsize=10.3, pad=7)
    ax_c.legend(loc="upper right", fontsize=7.7, handlelength=2.8)
    style_axis(ax_c)

    fig.suptitle(
        r"从“孤立最小值”到 MDM 的 $\gamma=0$ 边界解",
        x=0.055,
        y=0.955,
        ha="left",
        fontsize=16,
        fontweight="bold",
        color="#111827",
    )
    fig.text(
        0.055,
        0.906,
        "W(2,1000,500)，n=7，偏移量0.10。对照组按“其余样本中最小值最接近”选取；全部点和曲线均由当前工作簿真实样本复算。",
        ha="left",
        va="center",
        fontsize=9.4,
        color="#4B5563",
    )
    fig.text(
        0.055,
        0.852,
        r"读图链条：同样低的最小值  →  若第一个点相对后续点过度孤立  →  Cov($a_i,q_i$)更负  →  $g(0)=-\mathrm{Cov}(a,q)/\mathrm{SD}(a)>0.1$  →  左端点为受约束最小值。",
        ha="left",
        va="center",
        fontsize=9.0,
        color="#374151",
    )
    fig.text(
        0.982,
        0.038,
        "注：这里说明的是一次小样本实现对固定中位秩匹配不利，并不表示生成分布错误。",
        ha="right",
        va="bottom",
        fontsize=8.0,
        color="#6B7280",
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUTPUT_PATH, dpi=600, facecolor="white")

    provenance_lines = [
        "# n=7 gamma=0 mechanism figure provenance",
        "",
        f"- Source workbook: `{payload['workbook']}`",
        f"- Source sheet: `{payload['sheet']}`",
        "- Source range: `A2:H51` (50 real generated samples)",
        "- Generator distribution: `W(2,1000,500)`",
        "- MDM offset: `0.10`",
        "- Flag rule: `g(0) > 0.10`, giving samples 4 and 32.",
        "- Control rule: among non-flagged samples, choose the closest `t_(1)` to each flagged sample, giving 8 for 4 and 18 for 32.",
        "- Figure curves: direct recomputation from the source samples; no schematic or simulated replacement data.",
        "",
    ]
    for sample_id in SELECTED_IDS:
        row = samples[sample_id]
        mechanism = mechanisms[sample_id]
        provenance_lines.append(
            f"- Sample {sample_id}: t1={row[0]:.12g}, gap12={row[1]-row[0]:.12g}, "
            f"beta*(0)={float(mechanism['beta']):.12g}, "
            f"Cov(a,q)={float(mechanism['covariance']):.12g}, "
            f"g(0)={float(mechanism['gradient']):.12g}."
        )
    PROVENANCE_PATH.write_text("\n".join(provenance_lines) + "\n", encoding="utf-8")

    report = {
        "output": str(OUTPUT_PATH),
        "provenance": str(PROVENANCE_PATH),
        "font": FONT,
        "selected_ids": list(SELECTED_IDS),
        "flagged_ids": list(FLAGGED_IDS),
        "controls": {"4": 8, "32": 18},
        "theory_q1": float(theory[0]),
        "theory_gap12": float(theory[1] - theory[0]),
        "samples": {},
        "axes": len(fig.axes),
        "titles": [ax.get_title(loc="left") for ax in fig.axes],
        "xlabels": [ax.get_xlabel() for ax in fig.axes],
        "ylabels": [ax.get_ylabel() for ax in fig.axes],
    }
    for sample_id in SELECTED_IDS:
        mechanism = mechanisms[sample_id]
        curve = objective_curves[sample_id]
        report["samples"][str(sample_id)] = {
            "t1": float(samples[sample_id][0]),
            "gap12": float(samples[sample_id][1] - samples[sample_id][0]),
            "beta0": float(mechanism["beta"]),
            "cov_a_q": float(mechanism["covariance"]),
            "g0": float(mechanism["gradient"]),
            "Jprime0": float(mechanism["gradient"]) - OFFSET,
            "J_increment_gamma1": float(curve[np.searchsorted(gamma_grid, 1.0)]),
            "J_increment_gamma25": float(curve[-1]),
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    plt.close(fig)


if __name__ == "__main__":
    main()
