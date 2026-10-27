"""
MDM curve properties and strict offset-root solvability study.

This script is intentionally limited to the MDM method itself. It generates
solution-rate tables, no-root classifications, and real curve plots for the
research note in docs/mdm2.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from dataclasses import dataclass
from html import escape
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from base import WeibullBase
from methods.mdm_variants import _compute_mdm_search
from studies.common.sample import generate_sample


ETA = 100.0
OFFSET = 0.1
BETAS = [1.0, 1.5, 2.0, 3.0]
GAMMA_ETAS = [0.0, 0.1, 0.5, 1.0]
NS = [7, 10, 30]

LOW_GAMMA_STEPS = 20
CURRENT_GAMMA_STEPS = 60
HIGH_GAMMA_POINTS = 720
ULTRA_GAMMA_POINTS = 1800

BETA_GRID = np.unique(
    np.concatenate(
        [
            np.linspace(0.10, 1.00, 52, endpoint=False),
            np.linspace(1.00, 5.00, 128, endpoint=False),
            np.linspace(5.00, 15.00, 90),
        ]
    )
)

COLORS = [
    "#2563eb",
    "#16a34a",
    "#dc2626",
    "#7c3aed",
    "#ea580c",
    "#0f766e",
    "#0891b2",
    "#be123c",
]


@dataclass(frozen=True)
class CaseKey:
    beta: float
    gamma_eta: float
    n: int
    repeat_id: int

    def label(self) -> str:
        return (
            f"beta={self.beta:g}, gamma/eta={self.gamma_eta:g}, "
            f"n={self.n}, rid={self.repeat_id}"
        )


def ensure_dirs(output_dir: Path) -> tuple[Path, Path]:
    images_dir = output_dir / "images"
    data_dir = output_dir / "data"
    images_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)
    return images_dir, data_dir


def finite_min_max(values: list[float] | np.ndarray) -> tuple[float, float]:
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return 0.0, 1.0
    lo = float(np.min(arr))
    hi = float(np.max(arr))
    if lo == hi:
        pad = abs(lo) * 0.05 + 1.0
        return lo - pad, hi + pad
    pad = (hi - lo) * 0.08
    return lo - pad, hi + pad


def scale_x(value: float, xlim: tuple[float, float], left: float, width: float) -> float:
    lo, hi = xlim
    return left + (value - lo) / (hi - lo) * width


def scale_y(value: float, ylim: tuple[float, float], top: float, height: float) -> float:
    lo, hi = ylim
    return top + height - (value - lo) / (hi - lo) * height


def tick_values(lim: tuple[float, float], n: int = 5) -> np.ndarray:
    return np.linspace(lim[0], lim[1], n)


def fmt_tick(value: float) -> str:
    if abs(value) >= 100:
        return f"{value:.0f}"
    if abs(value) >= 10:
        return f"{value:.1f}"
    if abs(value) >= 1:
        return f"{value:.2f}"
    return f"{value:.3f}"


def polyline_points(
    x: np.ndarray,
    y: np.ndarray,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    left: float,
    top: float,
    width: float,
    height: float,
) -> str:
    finite = np.isfinite(x) & np.isfinite(y)
    coords = []
    for xv, yv in zip(x[finite], y[finite]):
        coords.append(
            f"{scale_x(float(xv), xlim, left, width):.2f},"
            f"{scale_y(float(yv), ylim, top, height):.2f}"
        )
    return " ".join(coords)


def svg_line_chart(
    out: Path,
    title: str,
    series: list[dict[str, Any]],
    xlabel: str,
    ylabel: str,
    hlines: list[dict[str, Any]] | None = None,
    vlines: list[dict[str, Any]] | None = None,
    points: list[dict[str, Any]] | None = None,
    width: int = 900,
    height: int = 560,
    xlim: tuple[float, float] | None = None,
    ylim: tuple[float, float] | None = None,
) -> None:
    hlines = hlines or []
    vlines = vlines or []
    points = points or []
    left, right, top, bottom = 82, 24, 58, 64
    plot_w = width - left - right
    plot_h = height - top - bottom

    xs = np.concatenate([np.asarray(item["x"], dtype=float) for item in series])
    ys = np.concatenate([np.asarray(item["y"], dtype=float) for item in series])
    if xlim is None:
        xlim = finite_min_max(xs)
    if ylim is None:
        y_extra = [line["y"] for line in hlines]
        point_extra = [point["y"] for point in points]
        ylim = finite_min_max(np.concatenate([ys, np.asarray(y_extra + point_extra)]))

    elems = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2:.1f}" y="26" text-anchor="middle" font-family="Arial" font-size="17" font-weight="700" fill="#111827">{escape(title)}</text>',
        f'<rect x="{left}" y="{top}" width="{plot_w}" height="{plot_h}" fill="#ffffff" stroke="#d1d5db"/>',
    ]

    for tick in tick_values(xlim):
        x_pos = scale_x(float(tick), xlim, left, plot_w)
        elems.append(f'<line x1="{x_pos:.2f}" x2="{x_pos:.2f}" y1="{top}" y2="{top+plot_h}" stroke="#eef2f7"/>')
        elems.append(f'<text x="{x_pos:.2f}" y="{top+plot_h+22}" text-anchor="middle" font-family="Arial" font-size="11" fill="#374151">{fmt_tick(float(tick))}</text>')
    for tick in tick_values(ylim):
        y_pos = scale_y(float(tick), ylim, top, plot_h)
        elems.append(f'<line x1="{left}" x2="{left+plot_w}" y1="{y_pos:.2f}" y2="{y_pos:.2f}" stroke="#eef2f7"/>')
        elems.append(f'<text x="{left-10}" y="{y_pos+4:.2f}" text-anchor="end" font-family="Arial" font-size="11" fill="#374151">{fmt_tick(float(tick))}</text>')

    for line in hlines:
        y_pos = scale_y(float(line["y"]), ylim, top, plot_h)
        dash = ' stroke-dasharray="6 5"' if line.get("dash", True) else ""
        elems.append(f'<line x1="{left}" x2="{left+plot_w}" y1="{y_pos:.2f}" y2="{y_pos:.2f}" stroke="{line.get("color", "#111827")}" stroke-width="{line.get("width", 1.2)}"{dash}/>')
    for line in vlines:
        x_pos = scale_x(float(line["x"]), xlim, left, plot_w)
        dash = ' stroke-dasharray="3 5"' if line.get("dash", True) else ""
        elems.append(f'<line x1="{x_pos:.2f}" x2="{x_pos:.2f}" y1="{top}" y2="{top+plot_h}" stroke="{line.get("color", "#7c3aed")}" stroke-width="{line.get("width", 1.0)}"{dash}/>')

    for idx, item in enumerate(series):
        color = item.get("color", COLORS[idx % len(COLORS)])
        dash = f' stroke-dasharray="{item["dash"]}"' if item.get("dash") else ""
        points_text = polyline_points(
            np.asarray(item["x"], dtype=float),
            np.asarray(item["y"], dtype=float),
            xlim,
            ylim,
            left,
            top,
            plot_w,
            plot_h,
        )
        elems.append(f'<polyline points="{points_text}" fill="none" stroke="{color}" stroke-width="{item.get("width", 2.0)}" stroke-linejoin="round" stroke-linecap="round"{dash}/>')

    for point in points:
        x_pos = scale_x(float(point["x"]), xlim, left, plot_w)
        y_pos = scale_y(float(point["y"]), ylim, top, plot_h)
        elems.append(f'<circle cx="{x_pos:.2f}" cy="{y_pos:.2f}" r="{point.get("r", 4)}" fill="{point.get("color", "#ea580c")}"/>')
        if point.get("label"):
            elems.append(f'<text x="{x_pos+8:.2f}" y="{y_pos-8:.2f}" font-family="Arial" font-size="11" fill="#374151">{escape(point["label"])}</text>')

    elems.append(f'<text x="{left+plot_w/2:.1f}" y="{height-20}" text-anchor="middle" font-family="Arial" font-size="13" fill="#111827">{escape(xlabel)}</text>')
    elems.append(f'<text x="18" y="{top+plot_h/2:.1f}" transform="rotate(-90 18 {top+plot_h/2:.1f})" text-anchor="middle" font-family="Arial" font-size="13" fill="#111827">{escape(ylabel)}</text>')

    legend_x = left + 8
    legend_y = top + 18
    for idx, item in enumerate(series):
        if not item.get("label"):
            continue
        color = item.get("color", COLORS[idx % len(COLORS)])
        y = legend_y + idx * 18
        elems.append(f'<line x1="{legend_x}" x2="{legend_x+24}" y1="{y}" y2="{y}" stroke="{color}" stroke-width="2.2"/>')
        elems.append(f'<text x="{legend_x+30}" y="{y+4}" font-family="Arial" font-size="11" fill="#374151">{escape(item["label"])}</text>')

    elems.append("</svg>")
    out.write_text("\n".join(elems), encoding="utf-8")


def svg_multi_panel(
    out: Path,
    title: str,
    panels: list[dict[str, Any]],
    xlabel: str,
    width: int = 900,
    height: int = 900,
) -> None:
    left, right, top, bottom = 82, 24, 58, 64
    gap = 28
    plot_w = width - left - right
    panel_h = (height - top - bottom - gap * (len(panels) - 1)) / len(panels)
    all_x = np.concatenate(
        [
            np.asarray(item["x"], dtype=float)
            for panel in panels
            for item in panel["series"]
        ]
    )
    xlim = finite_min_max(all_x)
    elems = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        f'<text x="{width/2:.1f}" y="26" text-anchor="middle" font-family="Arial" font-size="17" font-weight="700" fill="#111827">{escape(title)}</text>',
    ]
    for pidx, panel in enumerate(panels):
        y_top = top + pidx * (panel_h + gap)
        ys = np.concatenate([np.asarray(item["y"], dtype=float) for item in panel["series"]])
        y_extra = [line["y"] for line in panel.get("hlines", [])]
        ylim = finite_min_max(np.concatenate([ys, np.asarray(y_extra)]))
        elems.append(f'<rect x="{left}" y="{y_top:.2f}" width="{plot_w}" height="{panel_h:.2f}" fill="#ffffff" stroke="#d1d5db"/>')
        for tick in tick_values(ylim):
            y_pos = scale_y(float(tick), ylim, y_top, panel_h)
            elems.append(f'<line x1="{left}" x2="{left+plot_w}" y1="{y_pos:.2f}" y2="{y_pos:.2f}" stroke="#eef2f7"/>')
            elems.append(f'<text x="{left-10}" y="{y_pos+4:.2f}" text-anchor="end" font-family="Arial" font-size="11" fill="#374151">{fmt_tick(float(tick))}</text>')
        if pidx == len(panels) - 1:
            for tick in tick_values(xlim):
                x_pos = scale_x(float(tick), xlim, left, plot_w)
                elems.append(f'<line x1="{x_pos:.2f}" x2="{x_pos:.2f}" y1="{y_top:.2f}" y2="{y_top+panel_h:.2f}" stroke="#eef2f7"/>')
                elems.append(f'<text x="{x_pos:.2f}" y="{y_top+panel_h+22:.2f}" text-anchor="middle" font-family="Arial" font-size="11" fill="#374151">{fmt_tick(float(tick))}</text>')
        for line in panel.get("hlines", []):
            y_pos = scale_y(float(line["y"]), ylim, y_top, panel_h)
            elems.append(f'<line x1="{left}" x2="{left+plot_w}" y1="{y_pos:.2f}" y2="{y_pos:.2f}" stroke="{line.get("color", "#111827")}" stroke-width="{line.get("width", 1.1)}" stroke-dasharray="6 5"/>')
        for line in panel.get("vlines", []):
            x_pos = scale_x(float(line["x"]), xlim, left, plot_w)
            elems.append(f'<line x1="{x_pos:.2f}" x2="{x_pos:.2f}" y1="{y_top:.2f}" y2="{y_top+panel_h:.2f}" stroke="{line.get("color", "#7c3aed")}" stroke-width="{line.get("width", 1.0)}" stroke-dasharray="3 5"/>')
        for idx, item in enumerate(panel["series"]):
            color = item.get("color", COLORS[idx % len(COLORS)])
            dash = f' stroke-dasharray="{item["dash"]}"' if item.get("dash") else ""
            pts = polyline_points(
                np.asarray(item["x"], dtype=float),
                np.asarray(item["y"], dtype=float),
                xlim,
                ylim,
                left,
                y_top,
                plot_w,
                panel_h,
            )
            elems.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{item.get("width", 2.0)}" stroke-linejoin="round" stroke-linecap="round"{dash}/>')
        elems.append(f'<text x="18" y="{y_top+panel_h/2:.1f}" transform="rotate(-90 18 {y_top+panel_h/2:.1f})" text-anchor="middle" font-family="Arial" font-size="13" fill="#111827">{escape(panel["ylabel"])}</text>')
    elems.append(f'<text x="{left+plot_w/2:.1f}" y="{height-20}" text-anchor="middle" font-family="Arial" font-size="13" fill="#111827">{escape(xlabel)}</text>')
    elems.append("</svg>")
    out.write_text("\n".join(elems), encoding="utf-8")


def heat_color(value: float) -> str:
    stops = [
        (0.0, (68, 1, 84)),
        (0.5, (33, 145, 140)),
        (1.0, (253, 231, 37)),
    ]
    value = min(max(value, 0.0), 1.0)
    for (x0, c0), (x1, c1) in zip(stops, stops[1:]):
        if x0 <= value <= x1:
            ratio = (value - x0) / (x1 - x0)
            rgb = [round(c0[i] + ratio * (c1[i] - c0[i])) for i in range(3)]
            return f"#{rgb[0]:02x}{rgb[1]:02x}{rgb[2]:02x}"
    return "#fde725"


def gamma_grid(t_min: float, n_points: int) -> np.ndarray:
    """Dense grid on [0, t_min), with extra resolution near t_min."""
    counts = [
        max(8, int(n_points * 0.25)),
        max(8, int(n_points * 0.22)),
        max(8, int(n_points * 0.23)),
    ]
    last_count = max(8, n_points - sum(counts))
    ratios = np.concatenate(
        [
            np.linspace(0.0, 0.90, counts[0], endpoint=False),
            np.linspace(0.90, 0.99, counts[1], endpoint=False),
            np.linspace(0.99, 0.999, counts[2], endpoint=False),
            np.linspace(0.999, 0.999999, last_count),
        ]
    )
    return np.unique(ratios * t_min)


def current_strict_status(sample: np.ndarray, steps: int) -> dict[str, Any]:
    """Run the same two-stage strict sign-change search used by mdm.py."""
    result = _compute_mdm_search(sample, OFFSET, steps)
    gammas, sigma_mins, best_betas, grads, diffs, sign_changes = result[:6]
    return {
        "has_root": bool(len(sign_changes) > 0),
        "n_roots": int(len(sign_changes)),
        "grad_min": float(np.min(grads)),
        "grad_max": float(np.max(grads)),
        "min_abs_diff": float(np.min(np.abs(diffs))),
        "sign_changes": [int(i) for i in sign_changes],
        "gamma_points": int(len(gammas)),
        "sigma_min": float(np.min(sigma_mins)),
        "beta_min": float(np.nanmin(best_betas)),
        "beta_max": float(np.nanmax(best_betas)),
    }


def profile_grid(
    sample: np.ndarray,
    n_gamma: int = HIGH_GAMMA_POINTS,
    keep_sigma_grid: bool = False,
) -> dict[str, Any]:
    """Compute sigma(beta | gamma), beta*(gamma), S(gamma), and gradients."""
    wb = WeibullBase(sample, rank_method="bernard")
    t = wb.data
    ranks = wb._median_ranks()
    x = -np.log(1.0 - ranks)
    t_min = float(t[0])
    gammas = gamma_grid(t_min, n_gamma)

    inv_denoms = 1.0 / (x[None, :] ** (1.0 / BETA_GRID[:, None]))
    chunks = []
    for start in range(0, len(gammas), 160):
        g = gammas[start : start + 160]
        eta_values = (t[None, None, :] - g[:, None, None]) * inv_denoms[None, :, :]
        chunks.append(np.std(eta_values, axis=2, ddof=1))
    sigma_by_gamma_beta = np.vstack(chunks)

    best_idx = np.argmin(sigma_by_gamma_beta, axis=1)
    s_curve = sigma_by_gamma_beta[np.arange(len(gammas)), best_idx]
    best_betas = BETA_GRID[best_idx]
    grads = np.gradient(s_curve, gammas, edge_order=2)
    diffs = grads - OFFSET

    roots = find_roots(gammas, diffs)
    min_abs_idx = int(np.argmin(np.abs(diffs)))
    beta_boundary_fraction = float(
        np.mean((best_idx <= 1) | (best_idx >= len(BETA_GRID) - 2))
    )
    multimodal_count = count_multimodal_sigma_curves(sigma_by_gamma_beta)

    payload: dict[str, Any] = {
        "t_min": t_min,
        "gammas": gammas,
        "betas": BETA_GRID,
        "best_betas": best_betas,
        "s_curve": s_curve,
        "grads": grads,
        "diffs": diffs,
        "roots": roots,
        "min_abs_diff": float(abs(diffs[min_abs_idx])),
        "closest_gamma": float(gammas[min_abs_idx]),
        "closest_grad": float(grads[min_abs_idx]),
        "grad_min": float(np.min(grads)),
        "grad_max": float(np.max(grads)),
        "beta_boundary_fraction": beta_boundary_fraction,
        "multimodal_curve_count": int(multimodal_count),
        "is_beta_unstable": bool(
            beta_boundary_fraction > 0.05 or multimodal_count > 0
        ),
    }
    if keep_sigma_grid:
        payload["sigma_grid"] = sigma_by_gamma_beta
    return payload


def count_multimodal_sigma_curves(sigma_grid: np.ndarray) -> int:
    """Count inspected gamma rows whose sigma-beta curve has >1 clear basin."""
    if sigma_grid.size == 0:
        return 0
    inspected = np.unique(np.linspace(0, sigma_grid.shape[0] - 1, 17, dtype=int))
    count = 0
    for row_idx in inspected:
        y = sigma_grid[row_idx]
        finite = np.isfinite(y)
        if np.sum(finite) < 5:
            continue
        yf = y[finite]
        scale = max(float(np.nanmax(yf) - np.nanmin(yf)), 1e-12)
        local = []
        for i in range(1, len(yf) - 1):
            if yf[i] <= yf[i - 1] and yf[i] <= yf[i + 1]:
                left = np.nanmax(yf[: i + 1]) - yf[i]
                right = np.nanmax(yf[i:]) - yf[i]
                if min(left, right) / scale > 0.01:
                    local.append(i)
        if len(local) > 1:
            count += 1
    return count


def find_roots(xs: np.ndarray, ys: np.ndarray) -> list[float]:
    """Find all sign-changing roots by linear interpolation."""
    finite = np.isfinite(xs) & np.isfinite(ys)
    xs = xs[finite]
    ys = ys[finite]
    roots: list[float] = []
    for i in range(len(xs) - 1):
        y0 = ys[i]
        y1 = ys[i + 1]
        if y0 == 0:
            roots.append(float(xs[i]))
        elif y0 * y1 < 0:
            roots.append(float(xs[i] - y0 * (xs[i + 1] - xs[i]) / (y1 - y0)))
    if len(ys) and ys[-1] == 0:
        roots.append(float(xs[-1]))
    return roots


def classify_case(
    high: dict[str, Any],
    low20: dict[str, Any],
    current60: dict[str, Any],
    near_tol: float,
) -> str:
    has_high_root = bool(high["roots"])
    beta_unstable = bool(high["is_beta_unstable"])

    if has_high_root and not low20["has_root"]:
        return "numeric_miss_low20"
    if not has_high_root and current60["has_root"]:
        return "gradient_noise_suspect"
    if has_high_root and beta_unstable:
        return "root_beta_unstable"
    if has_high_root:
        return "root_stable"
    if beta_unstable:
        return "no_root_beta_unstable"
    if high["min_abs_diff"] <= near_tol:
        return "near_miss"
    if high["grad_min"] > OFFSET:
        return "all_above_offset"
    if high["grad_max"] < OFFSET:
        return "all_below_offset"
    return "no_sign_change_mixed"


def one_case(key: CaseKey) -> dict[str, Any]:
    gamma = key.gamma_eta * ETA
    sample = generate_sample(key.beta, ETA, gamma, key.n, key.repeat_id)
    low20 = current_strict_status(sample, LOW_GAMMA_STEPS)
    current60 = current_strict_status(sample, CURRENT_GAMMA_STEPS)
    high = profile_grid(sample, HIGH_GAMMA_POINTS, keep_sigma_grid=False)
    classification = classify_case(high, low20, current60, near_tol=0.01)
    return {
        "beta": key.beta,
        "eta": ETA,
        "gamma": gamma,
        "gamma_eta": key.gamma_eta,
        "n": key.n,
        "repeat_id": key.repeat_id,
        "low20_has_root": low20["has_root"],
        "current60_has_root": current60["has_root"],
        "high_has_root": bool(high["roots"]),
        "high_root_count": int(len(high["roots"])),
        "classification": classification,
        "grad_min": high["grad_min"],
        "grad_max": high["grad_max"],
        "min_abs_diff": high["min_abs_diff"],
        "closest_gamma_ratio": high["closest_gamma"] / high["t_min"],
        "beta_boundary_fraction": high["beta_boundary_fraction"],
        "multimodal_curve_count": high["multimodal_curve_count"],
        "current60_grad_min": current60["grad_min"],
        "current60_grad_max": current60["grad_max"],
    }


def summarize_rates(rows: list[dict[str, Any]], key_fields: list[str]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in rows:
        key = tuple(row[field] for field in key_fields)
        grouped.setdefault(key, []).append(row)

    out = []
    for key, group in sorted(grouped.items()):
        total = len(group)
        high_roots = sum(1 for row in group if row["high_has_root"])
        current_roots = sum(1 for row in group if row["current60_has_root"])
        item = {field: value for field, value in zip(key_fields, key)}
        item.update(
            {
                "total": total,
                "high_root_count": high_roots,
                "high_root_rate": high_roots / total if total else math.nan,
                "current60_root_count": current_roots,
                "current60_root_rate": current_roots / total if total else math.nan,
            }
        )
        out.append(item)
    return out


def summarize_classifications(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    total = len(rows)
    names = [
        "root_stable",
        "all_above_offset",
        "all_below_offset",
        "near_miss",
        "numeric_miss_low20",
        "root_beta_unstable",
        "no_root_beta_unstable",
        "gradient_noise_suspect",
        "no_sign_change_mixed",
    ]
    return [
        {
            "classification": name,
            "count": sum(1 for row in rows if row["classification"] == name),
            "rate": (
                sum(1 for row in rows if row["classification"] == name) / total
                if total
                else math.nan
            ),
        }
        for name in names
    ]


def pick_representatives(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    priority = [
        "root_stable",
        "all_above_offset",
        "all_below_offset",
        "near_miss",
        "numeric_miss_low20",
        "root_beta_unstable",
        "no_root_beta_unstable",
        "gradient_noise_suspect",
        "no_sign_change_mixed",
    ]
    reps: dict[str, dict[str, Any]] = {}
    for name in priority:
        matches = [row for row in rows if row["classification"] == name]
        if not matches:
            continue
        if name == "root_stable":
            one_root = [row for row in matches if row["high_root_count"] == 1]
            chosen = min(one_root or matches, key=lambda row: row["min_abs_diff"])
        elif name == "near_miss":
            chosen = min(matches, key=lambda row: row["min_abs_diff"])
        elif name == "numeric_miss_low20":
            chosen = min(matches, key=lambda row: row["min_abs_diff"])
        else:
            chosen = matches[0]
        reps[name] = chosen
    return reps


def case_key_from_row(row: dict[str, Any]) -> CaseKey:
    return CaseKey(
        beta=float(row["beta"]),
        gamma_eta=float(row["gamma_eta"]),
        n=int(row["n"]),
        repeat_id=int(row["repeat_id"]),
    )


def plot_sigma_beta_fixed_gamma(
    key: CaseKey, images_dir: Path, filename: str
) -> str:
    sample = generate_sample(key.beta, ETA, key.gamma_eta * ETA, key.n, key.repeat_id)
    profile = profile_grid(sample, ULTRA_GAMMA_POINTS, keep_sigma_grid=True)
    ratios = [0.0, 0.5, 0.9, 0.99, 0.9999]
    series = []
    for ratio in ratios:
        idx = int(np.argmin(np.abs(profile["gammas"] / profile["t_min"] - ratio)))
        series.append(
            {
                "x": profile["betas"],
                "y": profile["sigma_grid"][idx],
                "label": f"gamma/t_min={profile['gammas'][idx]/profile['t_min']:.4f}",
                "width": 1.8,
            }
        )
    out = images_dir / filename
    svg_line_chart(
        out,
        "sigma(beta | gamma) under several fixed gamma values",
        series,
        "beta",
        "sigma(beta | gamma)",
    )
    return out.name


def plot_profile_curves(key: CaseKey, images_dir: Path, filename: str) -> str:
    sample = generate_sample(key.beta, ETA, key.gamma_eta * ETA, key.n, key.repeat_id)
    profile = profile_grid(sample, ULTRA_GAMMA_POINTS, keep_sigma_grid=False)
    x_ratio = profile["gammas"] / profile["t_min"]
    out = images_dir / filename
    svg_multi_panel(
        out,
        f"Profile curves: {key.label()}",
        [
            {
                "ylabel": "beta*(gamma)",
                "series": [{"x": x_ratio, "y": profile["best_betas"], "color": "#2563eb"}],
            },
            {
                "ylabel": "S(gamma)",
                "series": [{"x": x_ratio, "y": profile["s_curve"], "color": "#16a34a"}],
            },
            {
                "ylabel": "g(gamma)",
                "series": [{"x": x_ratio, "y": profile["grads"], "color": "#dc2626"}],
                "hlines": [{"y": OFFSET, "color": "#111827"}],
                "vlines": [
                    {"x": root / profile["t_min"], "color": "#7c3aed"}
                    for root in profile["roots"]
                ],
            },
        ],
        "gamma / t_min",
    )
    return out.name


def plot_diff_curve(key: CaseKey, images_dir: Path, filename: str) -> str:
    sample = generate_sample(key.beta, ETA, key.gamma_eta * ETA, key.n, key.repeat_id)
    profile = profile_grid(sample, ULTRA_GAMMA_POINTS, keep_sigma_grid=False)
    x_ratio = profile["gammas"] / profile["t_min"]
    out = images_dir / filename
    svg_line_chart(
        out,
        f"g(gamma) - offset: {key.label()}",
        [
            {
                "x": x_ratio,
                "y": profile["diffs"],
                "color": "#0f766e",
                "label": "g(gamma)-offset",
                "width": 1.6,
            }
        ],
        "gamma / t_min",
        "g(gamma) - offset",
        hlines=[{"y": 0.0, "color": "#111827"}],
        vlines=[
            {"x": root / profile["t_min"], "color": "#7c3aed"}
            for root in profile["roots"]
        ],
        points=[
            {
                "x": profile["closest_gamma"] / profile["t_min"],
                "y": profile["closest_grad"] - OFFSET,
                "label": f"closest |diff|={profile['min_abs_diff']:.4g}",
            }
        ],
    )
    return out.name


def plot_low_high_comparison(key: CaseKey, images_dir: Path, filename: str) -> str:
    sample = generate_sample(key.beta, ETA, key.gamma_eta * ETA, key.n, key.repeat_id)
    high = profile_grid(sample, ULTRA_GAMMA_POINTS, keep_sigma_grid=False)
    low = profile_grid(sample, 80, keep_sigma_grid=False)
    out = images_dir / filename
    svg_multi_panel(
        out,
        f"Low vs high resolution: {key.label()}",
        [
            {
                "ylabel": "S(gamma)",
                "series": [
                    {
                        "x": high["gammas"] / high["t_min"],
                        "y": high["s_curve"],
                        "color": "#2563eb",
                        "width": 1.6,
                    },
                    {
                        "x": low["gammas"] / low["t_min"],
                        "y": low["s_curve"],
                        "color": "#ea580c",
                        "width": 1.2,
                    },
                ],
            },
            {
                "ylabel": "g-offset",
                "series": [
                    {
                        "x": high["gammas"] / high["t_min"],
                        "y": high["diffs"],
                        "color": "#2563eb",
                        "width": 1.6,
                    },
                    {
                        "x": low["gammas"] / low["t_min"],
                        "y": low["diffs"],
                        "color": "#ea580c",
                        "width": 1.2,
                    },
                ],
                "hlines": [{"y": 0.0, "color": "#111827"}],
            },
        ],
        "gamma / t_min",
        height=720,
    )
    return out.name


def plot_case_comparison(
    representatives: dict[str, dict[str, Any]], images_dir: Path, filename: str
) -> str:
    selected_names = [
        name
        for name in [
            "root_stable",
            "all_above_offset",
            "all_below_offset",
            "near_miss",
            "numeric_miss_low20",
        ]
        if name in representatives
    ]
    series = []
    for name in selected_names:
        key = case_key_from_row(representatives[name])
        sample = generate_sample(key.beta, ETA, key.gamma_eta * ETA, key.n, key.repeat_id)
        profile = profile_grid(sample, HIGH_GAMMA_POINTS, keep_sigma_grid=False)
        series.append(
            {
                "x": profile["gammas"] / profile["t_min"],
                "y": profile["grads"],
                "label": name,
                "width": 1.5,
            }
        )
    out = images_dir / filename
    svg_line_chart(
        out,
        "Representative g(gamma) curves by class",
        series,
        "gamma / t_min",
        "g(gamma)",
        hlines=[{"y": OFFSET, "color": "#111827"}],
    )
    return out.name


def plot_root_rate_heatmap(
    rows: list[dict[str, Any]], images_dir: Path, filename: str
) -> str:
    width = 980
    height = 350
    left = 72
    top = 70
    gap = 42
    cell_w = 48
    cell_h = 44
    panel_w = len(GAMMA_ETAS) * cell_w
    elems = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="white"/>',
        '<text x="490" y="28" text-anchor="middle" font-family="Arial" font-size="17" font-weight="700" fill="#111827">Strict offset-root solvability rate</text>',
    ]
    for pidx, n in enumerate(NS):
        panel_left = left + pidx * (panel_w + gap)
        matrix = np.zeros((len(BETAS), len(GAMMA_ETAS)))
        for i, beta in enumerate(BETAS):
            for j, gamma_eta in enumerate(GAMMA_ETAS):
                subset = [
                    row
                    for row in rows
                    if row["n"] == n
                    and row["beta"] == beta
                    and row["gamma_eta"] == gamma_eta
                ]
                matrix[i, j] = (
                    sum(1 for row in subset if row["high_has_root"]) / len(subset)
                    if subset
                    else np.nan
                )
        elems.append(f'<text x="{panel_left + panel_w / 2:.1f}" y="54" text-anchor="middle" font-family="Arial" font-size="14" font-weight="700" fill="#111827">n={n}</text>')
        for j, gamma_eta in enumerate(GAMMA_ETAS):
            x = panel_left + j * cell_w + cell_w / 2
            elems.append(f'<text x="{x:.1f}" y="{top - 12}" text-anchor="middle" font-family="Arial" font-size="11" fill="#374151">{gamma_eta:g}</text>')
        if pidx == 0:
            for i, beta in enumerate(BETAS):
                y = top + i * cell_h + cell_h / 2 + 4
                elems.append(f'<text x="{panel_left - 14}" y="{y:.1f}" text-anchor="end" font-family="Arial" font-size="11" fill="#374151">{beta:g}</text>')
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                value = float(matrix[i, j])
                x = panel_left + j * cell_w
                y = top + i * cell_h
                color = heat_color(value)
                text_color = "#111827" if value > 0.72 else "white"
                elems.append(f'<rect x="{x}" y="{y}" width="{cell_w}" height="{cell_h}" fill="{color}" stroke="white"/>')
                elems.append(f'<text x="{x + cell_w / 2:.1f}" y="{y + cell_h / 2 + 4:.1f}" text-anchor="middle" font-family="Arial" font-size="11" font-weight="700" fill="{text_color}">{value:.0%}</text>')
    elems.append(f'<text x="{width/2:.1f}" y="{height-24}" text-anchor="middle" font-family="Arial" font-size="13" fill="#111827">gamma/eta (columns), beta (rows), high-res root rate</text>')
    elems.append("</svg>")
    out = images_dir / filename
    out.write_text("\n".join(elems), encoding="utf-8")
    return out.name


def make_plots(
    rows: list[dict[str, Any]],
    representatives: dict[str, dict[str, Any]],
    images_dir: Path,
) -> dict[str, str]:
    plots: dict[str, str] = {}

    primary = representatives.get("root_stable") or next(row for row in rows if row["high_has_root"])
    primary_key = case_key_from_row(primary)
    plots["sigma_beta_fixed_gamma"] = plot_sigma_beta_fixed_gamma(
        primary_key, images_dir, "sigma_beta_fixed_gamma.svg"
    )
    plots["profile_root_stable"] = plot_profile_curves(
        primary_key, images_dir, "profile_root_stable.svg"
    )
    plots["diff_root_stable"] = plot_diff_curve(
        primary_key, images_dir, "diff_root_stable.svg"
    )

    for class_name, filename in [
        ("all_above_offset", "diff_all_above_offset.svg"),
        ("all_below_offset", "diff_all_below_offset.svg"),
        ("near_miss", "diff_near_miss.svg"),
        ("numeric_miss_low20", "low_high_numeric_miss.svg"),
        ("root_beta_unstable", "profile_root_beta_unstable.svg"),
        ("no_root_beta_unstable", "profile_no_root_beta_unstable.svg"),
    ]:
        if class_name not in representatives:
            continue
        key = case_key_from_row(representatives[class_name])
        if class_name == "numeric_miss_low20":
            plots[class_name] = plot_low_high_comparison(key, images_dir, filename)
        elif "beta_unstable" in class_name:
            plots[class_name] = plot_profile_curves(key, images_dir, filename)
        else:
            plots[class_name] = plot_diff_curve(key, images_dir, filename)

    plots["case_comparison"] = plot_case_comparison(
        representatives, images_dir, "g_curve_case_comparison.svg"
    )
    plots["root_rate_heatmap"] = plot_root_rate_heatmap(
        rows, images_dir, "root_rate_heatmap.svg"
    )
    return plots


def run(args: argparse.Namespace) -> dict[str, Any]:
    output_dir = Path(args.output_dir)
    images_dir, data_dir = ensure_dirs(output_dir)

    rows: list[dict[str, Any]] = []
    total = len(BETAS) * len(GAMMA_ETAS) * len(NS) * args.repeats
    done = 0
    for beta in BETAS:
        for gamma_eta in GAMMA_ETAS:
            for n in NS:
                for repeat_id in range(args.repeats):
                    key = CaseKey(beta, gamma_eta, n, repeat_id)
                    rows.append(one_case(key))
                    done += 1
                    if args.verbose and (done % 100 == 0 or done == total):
                        print(f"processed {done}/{total}")

    representatives = pick_representatives(rows)
    plots = make_plots(rows, representatives, images_dir)

    summary = {
        "config": {
            "eta": ETA,
            "offset": OFFSET,
            "betas": BETAS,
            "gamma_etas": GAMMA_ETAS,
            "ns": NS,
            "repeats": args.repeats,
            "low_gamma_steps": LOW_GAMMA_STEPS,
            "current_gamma_steps": CURRENT_GAMMA_STEPS,
            "high_gamma_points": HIGH_GAMMA_POINTS,
            "ultra_gamma_points": ULTRA_GAMMA_POINTS,
            "beta_grid_size": int(len(BETA_GRID)),
            "near_miss_tolerance": 0.01,
            "rank_method": "bernard",
        },
        "overall": {
            "total": len(rows),
            "high_root_count": sum(1 for row in rows if row["high_has_root"]),
            "high_root_rate": (
                sum(1 for row in rows if row["high_has_root"]) / len(rows)
                if rows
                else math.nan
            ),
            "current60_root_count": sum(
                1 for row in rows if row["current60_has_root"]
            ),
            "current60_root_rate": (
                sum(1 for row in rows if row["current60_has_root"]) / len(rows)
                if rows
                else math.nan
            ),
            "low20_root_count": sum(1 for row in rows if row["low20_has_root"]),
            "low20_root_rate": (
                sum(1 for row in rows if row["low20_has_root"]) / len(rows)
                if rows
                else math.nan
            ),
            "current60_no_root_count": sum(
                1 for row in rows if not row["current60_has_root"]
            ),
            "current60_no_root_curve_no_root_count": sum(
                1
                for row in rows
                if (not row["current60_has_root"]) and (not row["high_has_root"])
            ),
            "current60_no_root_numeric_miss_count": sum(
                1
                for row in rows
                if (not row["current60_has_root"]) and row["high_has_root"]
            ),
            "current60_false_positive_count": sum(
                1
                for row in rows
                if row["current60_has_root"] and (not row["high_has_root"])
            ),
            "low20_numeric_miss_count": sum(
                1 for row in rows if (not row["low20_has_root"]) and row["high_has_root"]
            ),
        },
        "high_root_count_distribution": [
            {
                "n_roots": n_roots,
                "count": sum(1 for row in rows if row["high_root_count"] == n_roots),
            }
            for n_roots in sorted({row["high_root_count"] for row in rows})
        ],
        "classifications": summarize_classifications(rows),
        "rates_by_beta": summarize_rates(rows, ["beta"]),
        "rates_by_gamma_eta": summarize_rates(rows, ["gamma_eta"]),
        "rates_by_n": summarize_rates(rows, ["n"]),
        "rates_by_beta_gamma_eta": summarize_rates(rows, ["beta", "gamma_eta"]),
        "rates_by_gamma_eta_n": summarize_rates(rows, ["gamma_eta", "n"]),
        "representatives": representatives,
        "plots": plots,
    }

    with (data_dir / "summary.json").open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    with (data_dir / "rows.json").open("w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)

    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repeats", type=int, default=40)
    parser.add_argument("--output-dir", default="docs/mdm2")
    parser.add_argument("--verbose", action="store_true")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
