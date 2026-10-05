from __future__ import annotations

import csv
import json
import math
import sys
from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
from scipy.optimize import brentq, minimize, minimize_scalar
from scipy.special import logsumexp


ROOT = Path(__file__).resolve().parents[3]
TASK_DIR = Path(__file__).resolve().parent.parent
OUT_DIR = Path(__file__).resolve().parent
DELIVERY_DIR = TASK_DIR / "260825给老师" / "WMLE过程图"

sys.path.insert(0, str(ROOT / "python"))
sys.path.insert(0, str(ROOT / "python" / "methods"))

from wmle import get_weight_j2, get_weight_j3  # noqa: E402


SHAPE_MIN = 0.1
SHAPE_MAX = 10.0
ACCEPTANCE_Q = 1e-8
VALID_CASE_KEYS = [(7, 1), (7, 14), (15, 6)]
REPRESENTATIVE_INVALID_KEY = (7, 35)
REPRESENTATIVE_VALID_KEY = (15, 6)


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


R1_COLOR = "#0072B2"
R2_COLOR = "#D55E00"
ACCEPT_COLOR = "#009E73"
REJECT_COLOR = "#B23A48"
PATH_COLOR = "#5F6368"
BOUND_COLOR = "#7A7A7A"


@dataclass
class Case:
    n: int
    sample_id: int
    sample: np.ndarray
    converged: bool
    status: str
    reported_q: float
    reported_shape: float | None
    reported_location: float | None
    best_shape: float | None = None
    best_location: float | None = None
    best_q: float | None = None
    path: np.ndarray | None = None

    @property
    def key(self) -> tuple[int, int]:
        return self.n, self.sample_id

    @property
    def x_min(self) -> float:
        return float(np.min(self.sample))


def load_samples() -> dict[tuple[int, int], np.ndarray]:
    grouped: dict[tuple[int, int], list[float]] = {}
    with (TASK_DIR / "samples.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            key = (int(row["sample_size"]), int(row["sample_id"]))
            grouped.setdefault(key, []).append(float(row["value"]))
    return {
        key: np.sort(np.asarray(values, dtype=float))
        for key, values in grouped.items()
    }


def load_cases(samples: dict[tuple[int, int], np.ndarray]) -> dict[tuple[int, int], Case]:
    cases: dict[tuple[int, int], Case] = {}
    with (TASK_DIR / "other_method_estimates.csv").open(
        "r", encoding="utf-8-sig", newline=""
    ) as handle:
        for row in csv.DictReader(handle):
            if row["method_id"] != "wmle":
                continue
            key = (int(row["sample_size"]), int(row["sample_id"]))
            info = json.loads(row["solution_info"] or "{}")
            cases[key] = Case(
                n=key[0],
                sample_id=key[1],
                sample=samples[key],
                converged=row["converged"].lower() == "true",
                status=row["solution_status"],
                reported_q=float(info.get("objective", "nan")),
                reported_shape=float(row["beta_hat"]) if row["beta_hat"] else None,
                reported_location=float(row["gamma_hat"]) if row["gamma_hat"] else None,
            )
    return cases


def residuals(sample: np.ndarray, shape: float, location: float) -> tuple[float, float]:
    """Evaluate Cousineau (2009) equation residuals stably."""
    if not (SHAPE_MIN <= shape <= SHAPE_MAX):
        return math.nan, math.nan
    shifted = sample - location
    if np.any(shifted <= 0):
        return math.nan, math.nan

    log_y = np.log(shifted)
    centered_log_y = log_y - float(np.mean(log_y))
    log_weights = shape * centered_log_y
    log_weights -= float(np.max(log_weights))
    weights = np.exp(log_weights)

    r1 = (
        get_weight_j2(sample.size) / shape
        + float(np.mean(log_y))
        - float(np.sum(weights * log_y) / np.sum(weights))
    )

    log_ratio = logsumexp(shape * centered_log_y) - logsumexp(
        (shape - 1.0) * centered_log_y
    )
    r2 = (
        float(np.mean(np.exp(-centered_log_y))) * math.exp(float(log_ratio))
        - get_weight_j3(sample.size, shape)
    )
    return float(r1), float(r2)


def objective(sample: np.ndarray, shape: float, location: float) -> float:
    r1, r2 = residuals(sample, shape, location)
    if not (np.isfinite(r1) and np.isfinite(r2)):
        return 1e10
    return float(r1 * r1 + r2 * r2)


def solve_case(case: Case) -> None:
    """Reproduce the current five-start search and preserve the selected path."""
    x_min = case.x_min
    starts = [
        np.array([2.0, 0.9 * x_min]),
        np.array([2.0, 0.5 * x_min]),
        np.array([2.0, 0.1 * x_min]),
        np.array([1.2, 0.9 * x_min]),
        np.array([4.0, 0.9 * x_min]),
    ]
    candidates: list[tuple[object, int, np.ndarray]] = []

    def wrapped(params: np.ndarray) -> float:
        shape, location = float(params[0]), float(params[1])
        if (
            shape <= 0
            or shape > SHAPE_MAX
            or location < 0
            or location >= x_min - 1e-6
        ):
            return 1e10
        return objective(case.sample, shape, location)

    for start_index, start in enumerate(starts):
        points: list[np.ndarray] = [start.copy()]

        def callback(xk: np.ndarray) -> None:
            points.append(np.asarray(xk, dtype=float).copy())

        result = minimize(
            wrapped,
            x0=start,
            method="Nelder-Mead",
            callback=callback,
            options={"maxiter": 1200, "xatol": 1e-9, "fatol": 1e-12},
        )
        shape, location = map(float, result.x)
        if (
            result.success
            and np.isfinite(result.fun)
            and 0 < shape < SHAPE_MAX
            and 0 <= location < x_min
        ):
            points.append(np.asarray(result.x, dtype=float).copy())
            candidates.append((result, start_index, np.asarray(points)))

    if not candidates:
        raise RuntimeError(f"No optimizer candidate for n={case.n}, sample={case.sample_id}")

    min_q = min(float(item[0].fun) for item in candidates)
    near_best = [item for item in candidates if float(item[0].fun) <= min_q + 1e-12]
    result, _, path = min(
        near_best,
        key=lambda item: (
            math.log(float(item[0].x[0]) / 2.0) ** 2
            + ((float(item[0].x[1]) - 0.9 * x_min) / max(x_min, 1.0)) ** 2
        ),
    )
    case.best_shape = float(result.x[0])
    case.best_location = float(result.x[1])
    case.best_q = float(result.fun)
    case.path = path

    if case.converged:
        if case.reported_shape is None or case.reported_location is None:
            raise AssertionError("Converged case lacks reported parameters")
        # Use the exact reported root for plotting; the independent solve is retained for path/profile.
        case.best_shape = case.reported_shape
        case.best_location = case.reported_location
        case.best_q = objective(case.sample, case.best_shape, case.best_location)


def surface(case: Case, grid_points: int = 260) -> tuple[np.ndarray, ...]:
    shapes = np.linspace(SHAPE_MIN, SHAPE_MAX - 0.01, grid_points)
    locations = np.linspace(0.0, case.x_min * (1.0 - 2e-5), grid_points)
    r1_grid = np.empty((grid_points, grid_points), dtype=float)
    r2_grid = np.empty_like(r1_grid)

    w2 = get_weight_j2(case.n)
    w3 = np.asarray([get_weight_j3(case.n, value) for value in shapes])
    for column, location in enumerate(locations):
        shifted = case.sample - location
        log_y = np.log(shifted)
        centered = log_y - float(np.mean(log_y))

        exponent = shapes[:, None] * centered[None, :]
        exponent -= np.max(exponent, axis=1, keepdims=True)
        weights = np.exp(exponent)
        r1_grid[:, column] = (
            w2 / shapes
            + float(np.mean(log_y))
            - np.sum(weights * log_y[None, :], axis=1) / np.sum(weights, axis=1)
        )

        log_ratio = logsumexp(shapes[:, None] * centered[None, :], axis=1) - logsumexp(
            (shapes[:, None] - 1.0) * centered[None, :], axis=1
        )
        r2_grid[:, column] = (
            float(np.mean(np.exp(-centered))) * np.exp(log_ratio) - w3
        )

    q_grid = r1_grid**2 + r2_grid**2
    return shapes, locations, r1_grid, r2_grid, q_grid


def zero_locations_at_shape(case: Case, shape: float = 5.0) -> tuple[float, float]:
    """Locate the two equation-zero positions at the J3 lookup-table edge."""
    locations = np.linspace(0.0, case.x_min * (1.0 - 2e-5), 2400)
    values = np.asarray([residuals(case.sample, shape, location) for location in locations])
    roots: list[float] = []
    for residual_index in range(2):
        brackets = np.where(
            values[:-1, residual_index] * values[1:, residual_index] <= 0
        )[0]
        if brackets.size != 1:
            raise RuntimeError(
                f"Expected one zero for R{residual_index + 1} at shape=5 in {case.key}"
            )
        left_index = int(brackets[0])
        root = brentq(
            lambda location: residuals(case.sample, shape, location)[residual_index],
            locations[left_index],
            locations[left_index + 1],
        )
        roots.append(float(root))
    return roots[0], roots[1]


def draw_parameter_panel(
    ax: plt.Axes,
    case: Case,
    grids: tuple[np.ndarray, ...],
    panel_label: str,
    show_path: bool = False,
    zoom_invalid: bool = False,
) -> None:
    shapes, locations, r1_grid, r2_grid, q_grid = grids
    log_q = np.log10(np.maximum(q_grid, 1e-12))
    mesh = ax.pcolormesh(
        locations,
        shapes,
        log_q,
        shading="auto",
        cmap="cividis_r",
        vmin=-8,
        vmax=-1.5,
        rasterized=True,
    )
    r1_contour = ax.contour(
        locations, shapes, r1_grid, levels=[0], colors=[R1_COLOR], linewidths=1.25
    )
    r2_contour = ax.contour(
        locations,
        shapes,
        r2_grid,
        levels=[0],
        colors=[R2_COLOR],
        linewidths=1.25,
        linestyles=["--"],
    )

    if show_path and case.path is not None:
        path = case.path
        valid = (
            (path[:, 0] >= SHAPE_MIN)
            & (path[:, 0] <= SHAPE_MAX)
            & (path[:, 1] >= 0)
            & (path[:, 1] < case.x_min)
        )
        path = path[valid]
        if path.size:
            stride = max(1, path.shape[0] // 35)
            ax.plot(
                path[:, 1],
                path[:, 0],
                color=PATH_COLOR,
                linewidth=0.8,
                alpha=0.72,
                zorder=3,
            )
            ax.scatter(
                path[::stride, 1],
                path[::stride, 0],
                s=5,
                color=PATH_COLOR,
                alpha=0.72,
                zorder=3,
            )

    color = ACCEPT_COLOR if case.converged else REJECT_COLOR
    marker = "o" if case.converged else "X"
    ax.scatter(
        [case.best_location],
        [case.best_shape],
        s=40,
        marker=marker,
        color=color,
        edgecolor="white",
        linewidth=0.6,
        zorder=6,
    )

    if case.converged:
        conclusion = "零线相交，可取"
    else:
        conclusion = "零线未相交，不取"
    ax.text(
        0.03,
        0.04,
        f"{conclusion}\n$Q_{{min}}={case.best_q:.2e}$",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=6.6,
        color=color,
        bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.82, "pad": 2.0},
    )
    ax.text(
        -0.11,
        1.04,
        panel_label,
        transform=ax.transAxes,
        fontsize=8.5,
        fontweight="bold",
        ha="left",
        va="bottom",
    )
    ax.set_title(f"n={case.n}，第{case.sample_id}组", fontsize=7.5, pad=4)
    ax.set_xlabel(r"位置参数候选值 $\alpha$")
    ax.set_ylabel(r"形状参数候选值 $\gamma$")
    if zoom_invalid:
        r1_location, r2_location = zero_locations_at_shape(case)
        gap = abs(r2_location - r1_location)
        left = max(0.0, min(r1_location, r2_location) - max(120.0, 0.75 * gap))
        right = min(case.x_min, max(r1_location, r2_location) + max(120.0, 0.75 * gap))
        ax.set_xlim(left, right)
        ax.set_ylim(4.35, 5.65)
        ax.axhline(5.0, color=BOUND_COLOR, linestyle=":", linewidth=0.9, zorder=2)
        ax.scatter([r1_location], [5.0], s=19, color=R1_COLOR, edgecolor="white",
                   linewidth=0.45, zorder=6)
        ax.scatter([r2_location], [5.0], s=19, color=R2_COLOR, edgecolor="white",
                   linewidth=0.45, zorder=6)
        ax.annotate(
            "",
            xy=(r1_location, 5.16),
            xytext=(r2_location, 5.16),
            arrowprops={"arrowstyle": "<->", "color": "#333333", "lw": 0.8},
        )
        ax.text(
            (r1_location + r2_location) / 2,
            5.21,
            rf"零线间距 $\Delta\alpha={gap:.0f}$",
            ha="center",
            va="bottom",
            fontsize=6.2,
            color="#333333",
        )
        ax.text(
            0.98,
            0.96,
            r"$J_3$查表上端：$\gamma=5$",
            transform=ax.transAxes,
            ha="right",
            va="top",
            fontsize=6.2,
            color=BOUND_COLOR,
        )
    else:
        ax.set_xlim(0, case.x_min)
        ax.set_ylim(SHAPE_MIN, SHAPE_MAX)
    ax.ticklabel_format(axis="x", style="plain", useOffset=False)
    ax.grid(False)
    ax._wmle_mesh = mesh  # keep a stable handle for shared colorbar
    ax._wmle_has_r1 = bool(r1_contour.allsegs[0])
    ax._wmle_has_r2 = bool(r2_contour.allsegs[0])


def save_figure(fig: plt.Figure, stem: str, deliver: bool = True) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    for suffix in (".png", ".pdf", ".svg", ".tiff"):
        kwargs = {"bbox_inches": "tight"}
        if suffix in {".png", ".tiff"}:
            kwargs["dpi"] = 600
        fig.savefig(OUT_DIR / f"{stem}{suffix}", **kwargs)
    if deliver:
        fig.savefig(DELIVERY_DIR / f"{stem}.png", dpi=600, bbox_inches="tight")
        fig.savefig(DELIVERY_DIR / f"{stem}.pdf", bbox_inches="tight")


def make_invalid_atlas(cases: list[Case], grids: dict[tuple[int, int], tuple[np.ndarray, ...]]) -> None:
    fig, axes = plt.subplots(2, 4, figsize=(183 / 25.4, 102 / 25.4))
    flat_axes = list(axes.flat)
    for index, case in enumerate(cases):
        draw_parameter_panel(
            flat_axes[index], case, grids[case.key], chr(97 + index), zoom_invalid=True
        )
    flat_axes[-1].axis("off")

    legend = [
        Line2D([0], [0], color=R1_COLOR, lw=1.4, label=r"形状方程零线 $R_1=0$"),
        Line2D([0], [0], color=R2_COLOR, lw=1.4, ls="--", label=r"位置方程零线 $R_2=0$"),
        Line2D([0], [0], marker="X", color="none", markerfacecolor=REJECT_COLOR,
               markeredgecolor="white", markersize=7, label=r"当前约束内的 $Q$ 最低点"),
    ]
    flat_axes[-1].legend(handles=legend, loc="center", fontsize=7.2)
    cbar_axis = fig.add_axes([0.915, 0.18, 0.014, 0.62])
    cbar = fig.colorbar(flat_axes[0]._wmle_mesh, cax=cbar_axis)
    cbar.set_label(r"目标函数 $\log_{10}Q$")
    fig.suptitle(
        r"被屏蔽的7组WMLE结果：在$J_3$查表上端，两条加权方程零线仍有明确间距",
        fontsize=9.2,
        fontweight="bold",
        y=0.995,
    )
    fig.text(
        0.5,
        0.012,
        r"判定依据：严格解要求 $R_1=R_2=0$；红色叉号位于两条零线之间，只是非零残差的折中最低点。",
        ha="center",
        va="bottom",
        fontsize=6.8,
    )
    fig.subplots_adjust(left=0.075, right=0.88, top=0.90, bottom=0.13, wspace=0.40, hspace=0.50)
    save_figure(fig, "WMLE屏蔽结果_零线与Q最低点")
    plt.close(fig)


def make_valid_atlas(cases: list[Case], grids: dict[tuple[int, int], tuple[np.ndarray, ...]]) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(183 / 25.4, 68 / 25.4))
    for index, (ax, case) in enumerate(zip(axes, cases)):
        draw_parameter_panel(ax, case, grids[case.key], chr(97 + index))
    legend = [
        Line2D([0], [0], color=R1_COLOR, lw=1.4, label=r"形状方程零线 $R_1=0$"),
        Line2D([0], [0], color=R2_COLOR, lw=1.4, ls="--", label=r"位置方程零线 $R_2=0$"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor=ACCEPT_COLOR,
               markeredgecolor="white", markersize=7, label="两条零线交点（可取解）"),
    ]
    fig.legend(handles=legend, loc="lower center", bbox_to_anchor=(0.46, 0.015), ncol=3)
    cbar_axis = fig.add_axes([0.915, 0.28, 0.014, 0.52])
    cbar = fig.colorbar(axes[0]._wmle_mesh, cax=cbar_axis)
    cbar.set_label(r"目标函数 $\log_{10}Q$")
    fig.suptitle(
        "可取的WMLE结果：两条加权方程零线相交，交点处Q接近数值零",
        fontsize=9.2,
        fontweight="bold",
        y=0.995,
    )
    fig.subplots_adjust(left=0.075, right=0.88, top=0.84, bottom=0.25, wspace=0.38)
    save_figure(fig, "WMLE可取结果_零线交点对比")
    plt.close(fig)


def profile_q(case: Case, locations: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    profile = np.empty_like(locations)
    shape_at_min = np.empty_like(locations)
    for index, location in enumerate(locations):
        result = minimize_scalar(
            lambda value: objective(case.sample, float(value), float(location)),
            bounds=(SHAPE_MIN, SHAPE_MAX - 0.01),
            method="bounded",
            options={"xatol": 1e-7, "maxiter": 300},
        )
        profile[index] = float(result.fun)
        shape_at_min[index] = float(result.x)
    return profile, shape_at_min


def make_detailed_comparison(
    invalid: Case,
    valid: Case,
    grids: dict[tuple[int, int], tuple[np.ndarray, ...]],
) -> None:
    fig = plt.figure(figsize=(183 / 25.4, 118 / 25.4))
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 0.85], hspace=0.40, wspace=0.28)
    axes_top = [fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1])]
    axes_bottom = [fig.add_subplot(gs[1, 0]), fig.add_subplot(gs[1, 1])]

    draw_parameter_panel(
        axes_top[0], invalid, grids[invalid.key], "a", show_path=True, zoom_invalid=True
    )
    draw_parameter_panel(axes_top[1], valid, grids[valid.key], "b", show_path=True)
    axes_top[0].set_title(
        f"不可取：n={invalid.n}，第{invalid.sample_id}组", fontsize=8.1, pad=5
    )
    axes_top[1].set_title(
        f"可取：n={valid.n}，第{valid.sample_id}组", fontsize=8.1, pad=5
    )

    for index, (ax, case, label) in enumerate(
        zip(axes_bottom, [invalid, valid], ["c", "d"])
    ):
        coarse_locations = np.linspace(0, case.x_min * (1 - 2e-5), 420)
        local_half_width = 0.025 * case.x_min
        local_locations = np.linspace(
            max(0.0, case.best_location - local_half_width),
            min(case.x_min * (1 - 2e-5), case.best_location + local_half_width),
            501,
        )
        locations = np.unique(
            np.concatenate([coarse_locations, local_locations, [case.best_location]])
        )
        profile, _ = profile_q(case, locations)
        exact_index = int(np.argmin(np.abs(locations - case.best_location)))
        profile[exact_index] = case.best_q
        ax.plot(locations, profile, color="#4C78A8", linewidth=1.5)
        ax.axhline(
            ACCEPTANCE_Q,
            color=BOUND_COLOR,
            linestyle="--",
            linewidth=1.0,
            label=r"当前程序接纳线 $Q=10^{-8}$",
        )
        point_color = ACCEPT_COLOR if case.converged else REJECT_COLOR
        point_marker = "o" if case.converged else "X"
        ax.scatter(
            [case.best_location],
            [max(case.best_q, 1e-30)],
            s=38,
            marker=point_marker,
            color=point_color,
            edgecolor="white",
            linewidth=0.6,
            zorder=5,
        )
        ax.annotate(
            f"$Q_{{min}}={case.best_q:.2e}$",
            xy=(case.best_location, max(case.best_q, 1e-30)),
            xytext=(0.05 if index == 0 else 0.42, 0.82),
            textcoords="axes fraction",
            arrowprops={"arrowstyle": "->", "color": point_color, "lw": 0.9},
            color=point_color,
            fontsize=6.9,
        )
        ax.set_yscale("log")
        ax.set_ylim(1e-28, 2e0)
        ax.set_xlim(0, case.x_min)
        ax.set_xlabel(r"候选位置参数 $\alpha$")
        ax.set_ylabel(r"剖面目标函数 $\min_{\gamma}Q$")
        ax.grid(axis="y", which="major", color="#E5E7EB", linewidth=0.55)
        ax.text(
            -0.11,
            1.04,
            label,
            transform=ax.transAxes,
            fontsize=8.5,
            fontweight="bold",
            ha="left",
            va="bottom",
        )
        ax.legend(loc="lower left", fontsize=6.5)

    legend = [
        Line2D([0], [0], color=R1_COLOR, lw=1.4, label=r"$R_1=0$"),
        Line2D([0], [0], color=R2_COLOR, lw=1.4, ls="--", label=r"$R_2=0$"),
        Line2D([0], [0], color=PATH_COLOR, lw=0.9, marker=".", label="所选起点的真实优化轨迹"),
    ]
    fig.legend(handles=legend, loc="upper center", bbox_to_anchor=(0.5, 0.905), ncol=3)
    fig.suptitle(
        "WMLE为什么有的结果可取、有的不能取",
        fontsize=9.5,
        fontweight="bold",
        y=0.99,
    )
    fig.text(
        0.5,
        0.012,
        "左：优化只能停在两个方程之间的折中最低点；右：两条零线相交，目标函数可以降到数值零。",
        ha="center",
        va="bottom",
        fontsize=7.0,
    )
    fig.subplots_adjust(left=0.085, right=0.985, top=0.82, bottom=0.12)
    save_figure(fig, "WMLE可取与不可取_过程对照图")
    plt.close(fig)


def main() -> None:
    samples = load_samples()
    cases = load_cases(samples)
    invalid_cases = sorted(
        [case for case in cases.values() if not case.converged and case.status == "equation_residual"],
        key=lambda case: case.key,
    )
    valid_cases = [cases[key] for key in VALID_CASE_KEYS]

    if len(invalid_cases) != 7:
        raise AssertionError(f"Expected 7 equation-residual cases, found {len(invalid_cases)}")

    selected_cases = invalid_cases + valid_cases
    for case in selected_cases:
        solve_case(case)
        if not np.isfinite(case.best_q):
            raise AssertionError(f"Non-finite Q for {case.key}")
        if case.converged and case.best_q > ACCEPTANCE_Q:
            raise AssertionError(f"Reported valid case exceeds threshold: {case.key}")
        if not case.converged and case.best_q <= ACCEPTANCE_Q:
            raise AssertionError(f"Reported invalid case unexpectedly passes threshold: {case.key}")

    grids = {case.key: surface(case) for case in selected_cases}
    make_invalid_atlas(invalid_cases, grids)
    make_valid_atlas(valid_cases, grids)
    make_detailed_comparison(
        cases[REPRESENTATIVE_INVALID_KEY],
        cases[REPRESENTATIVE_VALID_KEY],
        grids,
    )

    diagnostics = [
        {
            "n": case.n,
            "sample_id": case.sample_id,
            "status": "可取" if case.converged else "屏蔽",
            "shape": case.best_shape,
            "location": case.best_location,
            "Q_min": case.best_q,
            "reported_Q": case.reported_q,
        }
        for case in selected_cases
    ]
    print(json.dumps(diagnostics, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
