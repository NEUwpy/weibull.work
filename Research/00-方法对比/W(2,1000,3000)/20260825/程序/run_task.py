"""Generate samples, MDM estimates, summaries, and paper-style gradient plots.

The task is intentionally self-contained under docs. Sampling and estimation reuse
the repository's shared deterministic sampler and production MDM runner.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np


TASK_DIR = Path(__file__).resolve().parent
REPO_ROOT = TASK_DIR.parents[1]
sys.path.insert(0, str(REPO_ROOT / "python"))

from studies.common.metrics import aggregate_standard_metrics  # noqa: E402
from studies.common.runner import run_method  # noqa: E402
from studies.common.sample import generate_sample  # noqa: E402


BETA = 2.0
ETA = 1000.0
GAMMA = 3000.0
SAMPLE_SIZES = (7, 15)
REPEATS = 50
OFFSETS = (0.10, 0.15, 0.20)
SEED_NAMESPACE = 20260825
GAMMA_STEPS = 240
X_RANGE = (0.0, 4000.0)
Y_RANGE = (-0.6, 1.0)


def code_version() -> str:
    proc = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip()


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path.name}")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def generate_and_estimate():
    sample_rows: list[dict[str, object]] = []
    estimate_rows: list[dict[str, object]] = []
    curve_rows: list[dict[str, object]] = []

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
            sample_min = float(sample[0])
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
                include_trace = offset_index == 0
                result = run_method(
                    "mdm",
                    sample,
                    variant=f"mdm-delta-{offset:.2f}",
                    offset=offset,
                    gamma_steps=GAMMA_STEPS,
                    trace=include_trace,
                )
                solution = (result.get("extra") or {}).get("solution_info") or {}
                estimate_rows.append(
                    {
                        "beta": BETA,
                        "eta": ETA,
                        "gamma": GAMMA,
                        "sample_size": n,
                        "sample_id": sample_id,
                        "repeat_id": repeat_id,
                        "offset": offset,
                        "beta_hat": result["beta_hat"],
                        "eta_hat": result["eta_hat"],
                        "gamma_hat": result["gamma_hat"],
                        "r_squared": result["r_squared"],
                        "converged": bool(result["converged"]),
                        "sample_min": sample_min,
                        "solution_strategy": solution.get("solution_strategy"),
                        "root_solver": solution.get("root_solver"),
                        "gradient_at_zero": solution.get("probe_gradient_at_zero"),
                        "runtime_seconds": result["time"],
                    }
                )

                if include_trace:
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
                                "sigma_min": float(point["sigma_min"]),
                                "best_beta": float(point["best_beta"]),
                                "best_eta": float(point["best_eta"]),
                            }
                        )

    return sample_rows, estimate_rows, curve_rows


def build_summary(estimate_rows: list[dict[str, object]]):
    summary_rows: list[dict[str, object]] = []
    full_summaries: dict[str, object] = {}
    for n in SAMPLE_SIZES:
        for offset in OFFSETS:
            subset = [
                row
                for row in estimate_rows
                if row["sample_size"] == n and row["offset"] == offset
            ]
            summary = aggregate_standard_metrics(subset, include_diagnostics=True)
            key = f"n{n}_delta{offset:.2f}"
            full_summaries[key] = summary
            summary_rows.append(
                {
                    "sample_size": n,
                    "offset": offset,
                    "n_total": summary["n_total"],
                    "n_valid": summary["n_valid"],
                    "n_failure": summary["n_failure"],
                    "failure_rate": summary["failure_rate"],
                    "bias_beta": summary.get("bias_beta"),
                    "sd_beta": summary.get("sd_beta"),
                    "rmse_beta": summary.get("rmse_beta"),
                    "mae_beta": summary.get("mae_beta"),
                    "bias_eta": summary.get("bias_eta"),
                    "sd_eta": summary.get("sd_eta"),
                    "rmse_eta": summary.get("rmse_eta"),
                    "mae_eta": summary.get("mae_eta"),
                    "bias_gamma": summary.get("bias_gamma"),
                    "sd_gamma": summary.get("sd_gamma"),
                    "rmse_gamma": summary.get("rmse_gamma"),
                    "mae_gamma": summary.get("mae_gamma"),
                }
            )
    return summary_rows, full_summaries


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
            "svg.fonttype": "none",
            "pdf.fonttype": 42,
            "axes.unicode_minus": True,
        }
    )


def curve_groups(curve_rows: list[dict[str, object]], n: int):
    for sample_id in range(1, REPEATS + 1):
        rows = [
            row
            for row in curve_rows
            if row["sample_size"] == n and row["sample_id"] == sample_id
        ]
        rows.sort(key=lambda row: float(row["gamma_candidate"]))
        yield rows


def draw_reference_style(curve_rows: list[dict[str, object]], n: int, offset: float):
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

    ax.set_xticks(np.arange(0, 4001, 500))
    ax.set_yticks([-0.6, -0.2, 0.2, 0.6, 1.0])
    ax.xaxis.set_minor_locator(MultipleLocator(100))
    ax.yaxis.set_minor_locator(MultipleLocator(0.1))
    ax.tick_params(which="major", direction="in", length=4.2, pad=3)
    ax.tick_params(which="minor", direction="in", length=2.4)
    ax.set_ylabel("Std gradient", labelpad=8)
    fig.text(0.56, 0.055, "Location parameter value adopted", ha="center", va="center")
    fig.subplots_adjust(left=0.14, right=0.985, bottom=0.18, top=0.975)
    return fig


def save_figures(curve_rows: list[dict[str, object]]) -> None:
    for n in SAMPLE_SIZES:
        for offset in OFFSETS:
            fig = draw_reference_style(curve_rows, n, offset)
            stem = TASK_DIR / f"gradient_location_n{n}_delta{offset:.2f}".replace(".", "p")
            fig.savefig(stem.with_suffix(".png"), dpi=600, facecolor="white")
            fig.savefig(stem.with_suffix(".svg"), facecolor="white")
            fig.savefig(stem.with_suffix(".pdf"), facecolor="white")
            plt.close(fig)


def validate(
    sample_rows: list[dict[str, object]],
    estimate_rows: list[dict[str, object]],
    curve_rows: list[dict[str, object]],
    summary_rows: list[dict[str, object]],
) -> None:
    assert len(sample_rows) == REPEATS * sum(SAMPLE_SIZES) == 1100
    assert len(estimate_rows) == len(SAMPLE_SIZES) * REPEATS * len(OFFSETS) == 300
    assert len(summary_rows) == len(SAMPLE_SIZES) * len(OFFSETS) == 6
    assert len(curve_rows) == len(SAMPLE_SIZES) * REPEATS * GAMMA_STEPS == 24000
    assert all(bool(row["converged"]) for row in estimate_rows)
    assert max(float(row["sample_min"]) for row in estimate_rows) < X_RANGE[1]


def main() -> None:
    sample_rows, estimate_rows, curve_rows = generate_and_estimate()
    summary_rows, full_summaries = build_summary(estimate_rows)
    validate(sample_rows, estimate_rows, curve_rows, summary_rows)

    write_csv(TASK_DIR / "samples.csv", sample_rows)
    write_csv(TASK_DIR / "parameter_estimates.csv", estimate_rows)
    write_csv(TASK_DIR / "gradient_curves.csv", curve_rows)
    write_csv(TASK_DIR / "summary.csv", summary_rows)
    save_figures(curve_rows)

    manifest = {
        "task": "W(2,1000,3000) MDM estimates and gradient-location plots",
        "code_version": code_version(),
        "true_parameters": {"beta": BETA, "eta": ETA, "gamma": GAMMA},
        "sample_sizes": list(SAMPLE_SIZES),
        "repeats_per_sample_size": REPEATS,
        "offsets": list(OFFSETS),
        "seed_namespace": SEED_NAMESPACE,
        "gamma_steps": GAMMA_STEPS,
        "figure_contract": {
            "x_range": list(X_RANGE),
            "y_range": list(Y_RANGE),
            "y_major_ticks": [-0.6, -0.2, 0.2, 0.6, 1.0],
            "x_axis_crossing": "y=0",
            "curves_per_figure": REPEATS,
            "criterion_line": "one red dash-dot line at the figure-specific offset",
        },
        "summaries": full_summaries,
    }
    (TASK_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"samples={len(sample_rows)} estimates={len(estimate_rows)} curves={len(curve_rows)}")
    for row in summary_rows:
        print(
            f"n={row['sample_size']} delta={row['offset']:.2f} "
            f"valid={row['n_valid']}/{row['n_total']} gamma_rmse={row['rmse_gamma']:.6f}"
        )


if __name__ == "__main__":
    main()

