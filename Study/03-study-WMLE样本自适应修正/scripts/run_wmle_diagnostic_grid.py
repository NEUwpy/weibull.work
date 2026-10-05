"""Build a controlled diagnostic grid for small-sample three-parameter Weibull WMLE.

The grid is deliberately one-factor-at-a-time around a common baseline.  It is
an initial motivation study, not the formal training protocol for adaptive WMLE.
All methods use the repository sampler and production WMLE implementation.
"""

from __future__ import annotations

import csv
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np


TASK_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "python"
if str(PYTHON_DIR) not in sys.path:
    sys.path.insert(0, str(PYTHON_DIR))

from studies.common.sample import generate_sample  # noqa: E402
from studies.common.runner import run_method  # noqa: E402


SEED_NAMESPACE = 20260922
REPEATS = 100
SAMPLE_SIZES = (7, 15, 30)

# One-factor-at-a-time design around (beta=2, eta=1000, gamma=1000).
# The baseline is shared by all three axis comparisons.
CONDITIONS = (
    {"condition_id": "baseline", "axis": "baseline", "level": "baseline", "beta": 2.0, "eta": 1000.0, "gamma": 1000.0},
    {"condition_id": "beta_3", "axis": "beta", "level": 3.0, "beta": 3.0, "eta": 1000.0, "gamma": 1000.0},
    {"condition_id": "beta_5", "axis": "beta", "level": 5.0, "beta": 5.0, "eta": 1000.0, "gamma": 1000.0},
    {"condition_id": "eta_500", "axis": "eta", "level": 500.0, "beta": 2.0, "eta": 500.0, "gamma": 1000.0},
    {"condition_id": "eta_2000", "axis": "eta", "level": 2000.0, "beta": 2.0, "eta": 2000.0, "gamma": 1000.0},
    {"condition_id": "gamma_500", "axis": "gamma", "level": 500.0, "beta": 2.0, "eta": 1000.0, "gamma": 500.0},
    {"condition_id": "gamma_3000", "axis": "gamma", "level": 3000.0, "beta": 2.0, "eta": 1000.0, "gamma": 3000.0},
)


def git_version() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True).strip()
    except Exception:
        return "unknown"


def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        raise ValueError(f"No rows for {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def sample_features(sample: np.ndarray) -> dict[str, float]:
    x = np.asarray(sample, dtype=float)
    gaps = np.diff(x)
    range_value = float(x[-1] - x[0])
    std = float(np.std(x, ddof=1)) if x.size > 1 else 0.0
    largest_index = int(np.argmax(gaps) + 1) if gaps.size else -1
    return {
        "sample_min": float(x[0]),
        "sample_max": float(x[-1]),
        "sample_mean": float(np.mean(x)),
        "sample_sd": std,
        "sample_range": range_value,
        "sample_cv": float(std / np.mean(x)) if np.mean(x) else None,
        "gap_1": float(gaps[0]) if gaps.size else None,
        "gap_2": float(gaps[1]) if gaps.size > 1 else None,
        "largest_gap": float(np.max(gaps)) if gaps.size else None,
        "largest_gap_index": largest_index,
        "largest_gap_rel_range": float(np.max(gaps) / range_value) if gaps.size and range_value else None,
        "lower_two_span": float(x[min(2, x.size - 1)] - x[0]),
    }


def run_grid() -> tuple[list[dict], list[dict]]:
    sample_rows: list[dict] = []
    estimate_rows: list[dict] = []
    for condition in CONDITIONS:
        for n in SAMPLE_SIZES:
            for repeat_id in range(REPEATS):
                sample = generate_sample(
                    condition["beta"], condition["eta"], condition["gamma"],
                    n, repeat_id, seed=SEED_NAMESPACE,
                )
                features = sample_features(sample)
                sample_id = f"{condition['condition_id']}_n{n}_r{repeat_id:03d}"
                for observation_index, value in enumerate(sample, start=1):
                    sample_rows.append({
                        "condition_id": condition["condition_id"],
                        "axis": condition["axis"],
                        "level": condition["level"],
                        "beta": condition["beta"],
                        "eta": condition["eta"],
                        "gamma": condition["gamma"],
                        "sample_size": n,
                        "sample_id": sample_id,
                        "repeat_id": repeat_id,
                        "observation_index": observation_index,
                        "value": float(value),
                    })

                result = run_method("wmle", sample)
                extra = result.get("extra") or {}
                solution_info = extra.get("solution_info") or {}
                beta_hat = result.get("beta_hat")
                eta_hat = result.get("eta_hat")
                gamma_hat = result.get("gamma_hat")
                row = {
                    "condition_id": condition["condition_id"],
                    "axis": condition["axis"],
                    "level": condition["level"],
                    "beta": condition["beta"],
                    "eta": condition["eta"],
                    "gamma": condition["gamma"],
                    "sample_size": n,
                    "sample_id": sample_id,
                    "repeat_id": repeat_id,
                    "beta_hat": beta_hat,
                    "eta_hat": eta_hat,
                    "gamma_hat": gamma_hat,
                    "converged": bool(result.get("converged")),
                    "sample_min": features["sample_min"],
                    "sample_max": features["sample_max"],
                    "sample_mean": features["sample_mean"],
                    "sample_sd": features["sample_sd"],
                    "sample_range": features["sample_range"],
                    "sample_cv": features["sample_cv"],
                    "gap_1": features["gap_1"],
                    "gap_2": features["gap_2"],
                    "largest_gap": features["largest_gap"],
                    "largest_gap_index": features["largest_gap_index"],
                    "largest_gap_rel_range": features["largest_gap_rel_range"],
                    "lower_two_span": features["lower_two_span"],
                    "solution_status": solution_info.get("status") or extra.get("raw_status") or ("ok" if result.get("converged") else "failed"),
                    "objective": solution_info.get("objective"),
                    "selected_start": solution_info.get("selected_start"),
                    "location_at_zero_boundary": solution_info.get("location_at_zero_boundary"),
                    "runtime_seconds": result.get("time"),
                }
                if bool(result.get("converged")) and all(v is not None and math.isfinite(float(v)) for v in (beta_hat, eta_hat, gamma_hat)):
                    row.update({
                        "rel_error_beta": (float(beta_hat) - condition["beta"]) / condition["beta"],
                        "rel_error_eta": (float(eta_hat) - condition["eta"]) / condition["eta"],
                        "rel_error_gamma": (float(gamma_hat) - condition["gamma"]) / condition["eta"],
                        "abs_rel_error_max": max(
                            abs((float(beta_hat) - condition["beta"]) / condition["beta"]),
                            abs((float(eta_hat) - condition["eta"]) / condition["eta"]),
                            abs((float(gamma_hat) - condition["gamma"]) / condition["eta"]),
                        ),
                    })
                else:
                    row.update({"rel_error_beta": None, "rel_error_eta": None, "rel_error_gamma": None, "abs_rel_error_max": None})
                estimate_rows.append(row)
    return sample_rows, estimate_rows


def mean_or_none(values: list[float]) -> float | None:
    return float(np.mean(values)) if values else None


def sd_or_none(values: list[float]) -> float | None:
    return float(np.std(values, ddof=1)) if len(values) > 1 else (0.0 if values else None)


def summarize(values: list[float]) -> dict[str, float | None]:
    if not values:
        return {"bias": None, "sd": None, "rmse": None, "mae": None, "p95_abs": None, "p99_abs": None}
    arr = np.asarray(values, dtype=float)
    return {
        "bias": float(np.mean(arr)),
        "sd": sd_or_none(values),
        "rmse": float(np.sqrt(np.mean(arr ** 2))),
        "mae": float(np.mean(np.abs(arr))),
        "p95_abs": float(np.percentile(np.abs(arr), 95)),
        "p99_abs": float(np.percentile(np.abs(arr), 99)),
    }


def build_summary(rows: list[dict]) -> list[dict]:
    keys = [(c["condition_id"], n) for c in CONDITIONS for n in SAMPLE_SIZES]
    output: list[dict] = []
    for condition_id, n in keys:
        group = [r for r in rows if r["condition_id"] == condition_id and r["sample_size"] == n]
        valid = [r for r in group if r["converged"] and r["rel_error_beta"] is not None]
        out = {
            "condition_id": condition_id,
            "axis": group[0]["axis"],
            "level": group[0]["level"],
            "beta": group[0]["beta"], "eta": group[0]["eta"], "gamma": group[0]["gamma"],
            "sample_size": n, "n_total": len(group), "n_valid": len(valid),
            "n_failure": len(group) - len(valid),
            "failure_rate": (len(group) - len(valid)) / len(group),
            "extreme_rate_ge_50pct": mean_or_none([float(r["abs_rel_error_max"] >= 0.5) for r in valid]),
            "extreme_rate_ge_100pct": mean_or_none([float(r["abs_rel_error_max"] >= 1.0) for r in valid]),
        }
        for name in ("beta", "eta", "gamma"):
            metrics = summarize([float(r[f"rel_error_{name}"]) for r in valid])
            for metric, value in metrics.items():
                out[f"rel_{metric}_{name}"] = value
        output.append(out)
    return output


def build_feature_correlations(rows: list[dict]) -> list[dict]:
    features = ("sample_min", "sample_max", "sample_mean", "sample_sd", "sample_range", "sample_cv", "gap_1", "gap_2", "largest_gap", "largest_gap_rel_range", "lower_two_span")
    valid = [r for r in rows if r["converged"] and r["abs_rel_error_max"] is not None]
    output = []
    for feature in features:
        x = np.asarray([float(r[feature]) for r in valid], dtype=float)
        y = np.asarray([float(r["abs_rel_error_max"]) for r in valid], dtype=float)
        if len(x) < 3 or np.std(x) == 0 or np.std(y) == 0:
            corr = None
        else:
            corr = float(np.corrcoef(np.argsort(np.argsort(x)), np.argsort(np.argsort(y)))[0, 1])
        output.append({"feature": feature, "target": "abs_rel_error_max", "n_valid": len(x), "spearman_approx": corr})
    return output


def main() -> None:
    out_dir = TASK_DIR / "results" / "diagnostic_grid_v1"
    out_dir.mkdir(parents=True, exist_ok=True)
    samples, estimates = run_grid()
    summaries = build_summary(estimates)
    correlations = build_feature_correlations(estimates)
    worst = sorted(
        [r for r in estimates if r["abs_rel_error_max"] is not None],
        key=lambda r: float(r["abs_rel_error_max"]), reverse=True,
    )[:100]
    write_csv(out_dir / "samples_long.csv", samples)
    write_csv(out_dir / "wmle_estimates_long.csv", estimates)
    write_csv(out_dir / "wmle_cell_summary.csv", summaries)
    write_csv(out_dir / "feature_error_correlations.csv", correlations)
    write_csv(out_dir / "worst_cases_top100.csv", worst)
    manifest = {
        "study": "Study03",
        "protocol": "diagnostic_grid_v1",
        "purpose": "initial motivation and controlled WMLE heterogeneity analysis",
        "seed_namespace": SEED_NAMESPACE,
        "repeats_per_cell": REPEATS,
        "sample_sizes": list(SAMPLE_SIZES),
        "conditions": list(CONDITIONS),
        "method": "production wmle via studies.common.runner.run_method",
        "code_version": git_version(),
        "note": "One-factor-at-a-time diagnostic grid; not yet the adaptive-weight training protocol.",
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"samples={len(samples)} estimates={len(estimates)} cells={len(summaries)}")
    for row in summaries:
        print(row["condition_id"], "n", row["sample_size"], "valid", f"{row['n_valid']}/{row['n_total']}", "failure", row["failure_rate"], "extreme50", row["extreme_rate_ge_50pct"])


if __name__ == "__main__":
    main()
