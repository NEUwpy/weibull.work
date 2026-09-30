"""Generate the W(2,1000,500) samples, estimates, and six MDM gradient plots."""

from __future__ import annotations

import csv
import json
import math
import os
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np


WORK_DIR = Path(__file__).resolve().parent
REPO_ROOT = WORK_DIR.parents[1]
TASK_ROOT = (
    REPO_ROOT
    / "docs"
    / "临时任务-W2-1000-3000-MDM偏移量估计-20260825"
)
DELIVERY_DIR = TASK_ROOT / "260826位置参数500"
os.environ.setdefault("MPLCONFIGDIR", str(WORK_DIR / "mplconfig"))

import matplotlib as mpl  # noqa: E402
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.ticker import MultipleLocator  # noqa: E402

sys.path.insert(0, str(REPO_ROOT / "python"))

from studies.common.runner import run_method  # noqa: E402
from studies.common.sample import generate_sample  # noqa: E402


BETA = 2.0
ETA = 1000.0
GAMMA = 500.0
SAMPLE_SIZES = (7, 15)
REPEATS = 50
OFFSETS = (0.10, 0.15, 0.20)
SEED_NAMESPACE = 20260826
GAMMA_STEPS = 240
X_RANGE = (0.0, 1500.0)
Y_RANGE = (-0.8, 1.6)
METHODS = (
    ("lse", "LS", "LSE"),
    ("lre", "LRE", "LRE"),
    ("wmle", "WMLM", "WMLE"),
    ("mle", "MLM", "MLE"),
)


def json_value(value: Any) -> Any:
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, dict):
        return {str(key): json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_value(item) for item in value]
    return value


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path.name}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def code_version() -> dict[str, Any]:
    head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
    ).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
        ).strip()
    )
    return {"head": head, "dirty_worktree": dirty}


def result_row(
    *,
    n: int,
    sample_id: int,
    sample: np.ndarray,
    display_name: str,
    implementation: str,
    result: dict[str, Any],
    offset: float | None,
) -> dict[str, Any]:
    extra = result.get("extra") or {}
    solution = extra.get("solution_info") or {}
    status = (
        solution.get("status")
        or extra.get("raw_status")
        or ("ok" if result.get("converged") else extra.get("error", "failed"))
    )
    return {
        "beta": BETA,
        "eta": ETA,
        "gamma": GAMMA,
        "sample_size": n,
        "sample_id": sample_id,
        "repeat_id": sample_id - 1,
        "display_name": display_name,
        "implementation_name": implementation,
        "method_id": result.get("method_id"),
        "offset": offset,
        "beta_hat": result.get("beta_hat"),
        "eta_hat": result.get("eta_hat"),
        "gamma_hat": result.get("gamma_hat"),
        "r_squared": result.get("r_squared"),
        "converged": bool(result.get("converged")),
        "sample_min": float(sample[0]),
        "solution_status": str(status),
    }


def generate_results() -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
    list[dict[str, Any]],
]:
    sample_rows: list[dict[str, Any]] = []
    mdm_rows: list[dict[str, Any]] = []
    other_rows: list[dict[str, Any]] = []
    curve_rows: list[dict[str, Any]] = []

    for n in SAMPLE_SIZES:
        for repeat_id in range(REPEATS):
            sample = generate_sample(
                BETA,
                ETA,
                GAMMA,
                n,
                repeat_id,
                seed=SEED_NAMESPACE,
            )
            sample_id = repeat_id + 1
            for observation_index, value in enumerate(sample, start=1):
                sample_rows.append(
                    {
                        "sample_size": n,
                        "sample_id": sample_id,
                        "repeat_id": repeat_id,
                        "observation_index": observation_index,
                        "value": float(value),
                    }
                )

            for offset_index, offset in enumerate(OFFSETS):
                result = run_method(
                    "mdm",
                    sample,
                    variant=f"mdm-delta-{offset:.2f}",
                    offset=offset,
                    gamma_steps=GAMMA_STEPS,
                    trace=(offset_index == 0),
                )
                mdm_rows.append(
                    result_row(
                        n=n,
                        sample_id=sample_id,
                        sample=sample,
                        display_name="MDM",
                        implementation="MDM",
                        result=result,
                        offset=offset,
                    )
                )
                if offset_index == 0:
                    trace_data = result.get("trace_data") or {}
                    for point in trace_data.get("grad_gamma_curve", []):
                        if point.get("source") != "trace_grid" or point.get("virtual", False):
                            continue
                        gradient = float(point["gradient"])
                        if not math.isfinite(gradient):
                            continue
                        curve_rows.append(
                            {
                                "sample_size": n,
                                "sample_id": sample_id,
                                "repeat_id": repeat_id,
                                "gamma_candidate": float(point["gamma"]),
                                "std_gradient": gradient,
                            }
                        )

            for method_id, display_name, implementation in METHODS:
                result = run_method(method_id, sample)
                other_rows.append(
                    result_row(
                        n=n,
                        sample_id=sample_id,
                        sample=sample,
                        display_name=display_name,
                        implementation=implementation,
                        result=result,
                        offset=None,
                    )
                )

            if sample_id % 10 == 0:
                print(f"progress n={n}: {sample_id}/{REPEATS}", flush=True)

    return sample_rows, mdm_rows, other_rows, curve_rows


def configure_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "Times", "DejaVu Serif"],
            "font.size": 8,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.8,
            "ytick.major.width": 0.8,
            "xtick.minor.width": 0.6,
            "ytick.minor.width": 0.6,
            "pdf.fonttype": 42,
            "axes.unicode_minus": True,
        }
    )


def curve_groups(curve_rows: list[dict[str, Any]], n: int):
    for sample_id in range(1, REPEATS + 1):
        rows = [
            row
            for row in curve_rows
            if row["sample_size"] == n and row["sample_id"] == sample_id
        ]
        rows.sort(key=lambda row: float(row["gamma_candidate"]))
        yield rows


def draw_reference_style(
    curve_rows: list[dict[str, Any]], n: int, offset: float
) -> plt.Figure:
    configure_style()
    fig, ax = plt.subplots(figsize=(130 / 25.4, 92 / 25.4))

    for rows in curve_groups(curve_rows, n):
        ax.plot(
            [float(row["gamma_candidate"]) for row in rows],
            [float(row["std_gradient"]) for row in rows],
            color="black",
            linewidth=0.48,
            alpha=0.82,
            solid_capstyle="round",
        )

    ax.axhline(offset, color="#b2182b", linewidth=0.85, linestyle="-.", zorder=5)
    ax.set_xlim(*X_RANGE)
    ax.set_ylim(*Y_RANGE)
    ax.spines["bottom"].set_position(("data", 0.0))
    ax.spines["left"].set_position(("data", 0.0))
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.xaxis.set_ticks_position("bottom")
    ax.yaxis.set_ticks_position("left")
    ax.set_xticks(np.arange(0, 1501, 500))
    ax.set_yticks(np.arange(-0.8, 1.61, 0.4))
    ax.xaxis.set_minor_locator(MultipleLocator(100))
    ax.yaxis.set_minor_locator(MultipleLocator(0.1))
    ax.tick_params(which="major", direction="in", length=4.2, pad=3)
    ax.tick_params(which="minor", direction="in", length=2.4)
    ax.set_ylabel("Std gradient", labelpad=8)
    fig.text(
        0.56,
        0.055,
        "Location parameter value adopted",
        ha="center",
        va="center",
    )
    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.18, top=0.975)
    return fig


def save_figures(curve_rows: list[dict[str, Any]]) -> list[str]:
    DELIVERY_DIR.mkdir(parents=True, exist_ok=True)
    filenames: list[str] = []
    for n in SAMPLE_SIZES:
        for offset in OFFSETS:
            filename = f"样本量{n}_偏移量{offset:.2f}.png"
            output_path = WORK_DIR / filename
            delivery_path = DELIVERY_DIR / filename
            fig = draw_reference_style(curve_rows, n, offset)
            fig.savefig(output_path, dpi=600, facecolor="white")
            plt.close(fig)
            shutil.copy2(output_path, delivery_path)
            filenames.append(filename)
    return filenames


def validate_results(
    sample_rows: list[dict[str, Any]],
    mdm_rows: list[dict[str, Any]],
    other_rows: list[dict[str, Any]],
    curve_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    assert len(sample_rows) == REPEATS * sum(SAMPLE_SIZES) == 1100
    assert len(mdm_rows) == len(SAMPLE_SIZES) * REPEATS * len(OFFSETS) == 300
    assert len(other_rows) == len(SAMPLE_SIZES) * REPEATS * len(METHODS) == 400
    curve_point_counts = Counter(
        (int(row["sample_size"]), int(row["sample_id"])) for row in curve_rows
    )
    expected_curve_keys = {
        (n, sample_id)
        for n in SAMPLE_SIZES
        for sample_id in range(1, REPEATS + 1)
    }
    assert set(curve_point_counts) == expected_curve_keys
    assert all(
        GAMMA_STEPS - 1 <= count <= GAMMA_STEPS
        for count in curve_point_counts.values()
    )
    assert all(row["converged"] for row in mdm_rows)
    assert max(float(row["sample_min"]) for row in mdm_rows) < X_RANGE[1]

    for row in [*mdm_rows, *other_rows]:
        if not row["converged"]:
            continue
        estimates = [row["beta_hat"], row["eta_hat"], row["gamma_hat"]]
        if not all(value is not None and math.isfinite(float(value)) for value in estimates):
            raise RuntimeError(f"Non-finite converged estimate: {row}")
        if float(row["beta_hat"]) <= 0 or float(row["eta_hat"]) <= 0:
            raise RuntimeError(f"Invalid positive-parameter estimate: {row}")
        if not 0 <= float(row["gamma_hat"]) < float(row["sample_min"]):
            raise RuntimeError(f"Invalid location estimate: {row}")

    counts: dict[str, Any] = {}
    for n in SAMPLE_SIZES:
        for display_name in ["MDM", *[item[1] for item in METHODS]]:
            subset = [
                row
                for row in [*mdm_rows, *other_rows]
                if row["sample_size"] == n and row["display_name"] == display_name
            ]
            if display_name == "MDM":
                for offset in OFFSETS:
                    offset_subset = [row for row in subset if row["offset"] == offset]
                    counts[f"n{n}_{display_name}_delta{offset:.2f}"] = {
                        "total": len(offset_subset),
                        "converged": sum(row["converged"] for row in offset_subset),
                        "gamma_zero": sum(
                            row["converged"] and float(row["gamma_hat"]) == 0.0
                            for row in offset_subset
                        ),
                        "statuses": dict(Counter(row["solution_status"] for row in offset_subset)),
                    }
            else:
                counts[f"n{n}_{display_name}"] = {
                    "total": len(subset),
                    "converged": sum(row["converged"] for row in subset),
                    "gamma_zero": sum(
                        row["converged"] and float(row["gamma_hat"]) == 0.0
                        for row in subset
                    ),
                    "statuses": dict(Counter(row["solution_status"] for row in subset)),
                }
    counts["gradient_curves"] = {
        "curve_count": len(curve_point_counts),
        "finite_points": len(curve_rows),
        "expected_grid_points": len(curve_point_counts) * GAMMA_STEPS,
        "curves_with_one_filtered_nonfinite_endpoint": sum(
            count == GAMMA_STEPS - 1 for count in curve_point_counts.values()
        ),
    }
    return counts


def main() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    sample_rows, mdm_rows, other_rows, curve_rows = generate_results()
    validation = validate_results(sample_rows, mdm_rows, other_rows, curve_rows)
    figures = save_figures(curve_rows)

    write_csv(WORK_DIR / "samples.csv", sample_rows)
    write_csv(WORK_DIR / "mdm_estimates.csv", mdm_rows)
    write_csv(WORK_DIR / "other_method_estimates.csv", other_rows)
    write_csv(WORK_DIR / "gradient_curves.csv", curve_rows)

    workbook_payload = {
        "parameters": {
            "distribution": "W(2,1000,500)",
            "beta": BETA,
            "eta": ETA,
            "gamma": GAMMA,
            "sample_sizes": list(SAMPLE_SIZES),
            "samples_per_size": REPEATS,
            "offsets": list(OFFSETS),
            "seed_namespace": SEED_NAMESPACE,
        },
        "mdm_rows": mdm_rows,
        "other_rows": other_rows,
    }
    (WORK_DIR / "workbook_data.json").write_text(
        json.dumps(json_value(workbook_payload), ensure_ascii=False),
        encoding="utf-8",
    )
    manifest = {
        "task": "W(2,1000,500) six MDM gradient plots and estimation table",
        "code_version": code_version(),
        "parameters": workbook_payload["parameters"],
        "gamma_steps": GAMMA_STEPS,
        "figure_contract": {
            "x_range": list(X_RANGE),
            "x_major_step": 500,
            "x_minor_step": 100,
            "y_range": list(Y_RANGE),
            "y_major_step": 0.4,
            "y_minor_step": 0.1,
            "curves_per_figure": REPEATS,
            "criterion_line": "one red dash-dot line at the figure-specific offset",
        },
        "method_mapping": {
            "MDM": "MDM",
            "LS": "LSE",
            "LRE": "LRE",
            "WMLM": "WMLE",
            "MLM": "MLE",
        },
        "validation": validation,
        "figures": figures,
    }
    (WORK_DIR / "manifest.json").write_text(
        json.dumps(json_value(manifest), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(validation, ensure_ascii=False, indent=2), flush=True)
    print(f"figures={len(figures)} delivery={DELIVERY_DIR}", flush=True)


if __name__ == "__main__":
    main()
