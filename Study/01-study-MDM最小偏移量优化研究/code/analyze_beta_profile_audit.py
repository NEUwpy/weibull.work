"""Lightweight Ch5 audit of beta-dependent MDM profile geometry.

The formal design is frozen in ``_ch5_beta_profile_audit_contract.md``.  This
module regenerates the E1/E2 samples from their deterministic seed contract and
extracts profile-gradient diagnostics without rescanning candidate deltas.
"""

from __future__ import annotations

from pathlib import Path
from datetime import datetime, timezone
import json
import os
import subprocess
import sys
import tempfile
import time

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


STUDY_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = STUDY_ROOT.parents[1]
PLATFORM_ROOT = REPO_ROOT / "python"
if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))

from methods.mdm import MDM
from studies.common.sample import generate_sample

BETA_GRID = [1.5, 2.0, 2.5, 4.0, 5.0]
N_GRID = [7, 10, 20]
REPEAT_IDS = range(20)
TRUE_ETA = 1.0
TRUE_GAMMA = 0.5
SEED_NAMESPACE = "study01_v1"
TARGET_OFFSET = 0.1
OUTPUT_DIR = STUDY_ROOT / "artifacts" / "formal" / "E2_beta_profile_audit"
METRIC_COLS = [
    "gradient_at_zero",
    "gradient_at_true_gamma",
    "local_gradient_slope",
    "gamma_hat_d01",
    "gamma_error_d01",
]


def build_design() -> pd.DataFrame:
    """Return the frozen 5 beta x 3 n x 20 repeat audit design."""
    return pd.DataFrame(
        {
            "beta": beta,
            "eta": TRUE_ETA,
            "gamma": TRUE_GAMMA,
            "gamma_over_eta": TRUE_GAMMA / TRUE_ETA,
            "n": n,
            "repeat_id": repeat_id,
        }
        for beta in BETA_GRID
        for n in N_GRID
        for repeat_id in REPEAT_IDS
    )


def _finite_nonvirtual_points(points: list[dict]) -> list[dict]:
    return [
        point
        for point in points
        if not point.get("virtual", False)
        and np.isfinite(point["gamma"])
        and np.isfinite(point["gradient"])
    ]


def interpolate_gradient(points: list[dict], target_gamma: float) -> float:
    """Linearly interpolate the finite trace gradient at ``target_gamma``."""
    ordered = sorted(_finite_nonvirtual_points(points), key=lambda point: point["gamma"])
    if len(ordered) < 2:
        raise ValueError("need at least two finite nonvirtual trace points")
    gammas = np.asarray([point["gamma"] for point in ordered], dtype=float)
    gradients = np.asarray([point["gradient"] for point in ordered], dtype=float)
    if target_gamma < gammas[0] or target_gamma > gammas[-1]:
        raise ValueError("true gamma is outside the finite trace interval")
    return float(np.interp(target_gamma, gammas, gradients))


def local_gradient_slope(
    points: list[dict], target_gamma: float, k: int = 7
) -> float:
    """Fit gradient against gamma on the nearest ``k`` finite trace points."""
    candidates = sorted(
        _finite_nonvirtual_points(points),
        key=lambda point: (abs(point["gamma"] - target_gamma), point["gamma"]),
    )[:k]
    if len(candidates) != k:
        raise ValueError(f"need exactly {k} finite nonvirtual points")
    return float(
        np.polyfit(
            [point["gamma"] for point in candidates],
            [point["gradient"] for point in candidates],
            1,
        )[0]
    )


def direction_consistent(values: list[float]) -> bool:
    """Return true only for three finite, nonzero coefficients of one sign."""
    if len(values) != len(N_GRID) or not np.isfinite(values).all():
        return False
    signs = [int(np.sign(value)) for value in values]
    return 0 not in signs and len(set(signs)) == 1


def extract_sample_metrics(row: dict) -> dict:
    """Regenerate one formal sample and extract its profile diagnostics."""
    sample = generate_sample(
        float(row["beta"]),
        float(row["eta"]),
        float(row["gamma"]),
        int(row["n"]),
        int(row["repeat_id"]),
        seed=SEED_NAMESPACE,
    )
    mdm = MDM(sample)
    _, _, gamma_hat, _, _ = mdm.run(trace=True, offset=TARGET_OFFSET)
    trace = mdm.trace_data
    curve = trace["grad_gamma_curve"]
    true_gamma = float(row["gamma"])
    result = {
        "beta": float(row["beta"]),
        "eta": float(row["eta"]),
        "gamma": true_gamma,
        "gamma_over_eta": float(row["gamma_over_eta"]),
        "n": int(row["n"]),
        "repeat_id": int(row["repeat_id"]),
        "gradient_at_zero": float(trace["probe_gradient_at_zero"]),
        "gradient_at_true_gamma": interpolate_gradient(curve, true_gamma),
        "local_gradient_slope": local_gradient_slope(curve, true_gamma, k=7),
        "gamma_hat_d01": float(gamma_hat),
        "gamma_error_d01": float(gamma_hat - true_gamma),
        "solution_strategy": str(trace["solution_strategy"]),
    }
    if not np.isfinite([result[name] for name in METRIC_COLS]).all():
        raise ValueError("non-finite profile metric")
    return result


def compute_trends(metrics: pd.DataFrame, metric_cols: list[str]) -> pd.DataFrame:
    """Compute descriptive Spearman trends within n and for the pooled sample."""
    rows = []
    scopes = [(f"n={n}", metrics[metrics["n"] == n]) for n in N_GRID]
    scopes.append(("pooled", metrics))
    for metric in metric_cols:
        for scope, frame in scopes:
            rho = float(spearmanr(frame["beta"], frame[metric]).statistic)
            rows.append(
                {
                    "metric": metric,
                    "scope": scope,
                    "n_samples": int(len(frame)),
                    "spearman_rho": rho,
                }
            )
    return pd.DataFrame(rows)


def summarize_by_beta_n(metrics: pd.DataFrame) -> pd.DataFrame:
    """Summarize continuous metrics and solver strategies in 15 design cells."""
    rows = []
    for (beta, n), frame in metrics.groupby(["beta", "n"], sort=True):
        row = {"beta": float(beta), "n": int(n), "n_samples": int(len(frame))}
        for metric in METRIC_COLS:
            row[f"{metric}_median"] = float(frame[metric].median())
            row[f"{metric}_q1"] = float(frame[metric].quantile(0.25))
            row[f"{metric}_q3"] = float(frame[metric].quantile(0.75))
        strategies = frame["solution_strategy"].value_counts()
        row["strategy_truncated_at_zero_count"] = int(
            strategies.get("truncated_at_zero", 0)
        )
        row["strategy_brent_root_count"] = int(strategies.get("brent_root", 0))
        rows.append(row)
    return pd.DataFrame(rows)


def validate_outputs(
    metrics: pd.DataFrame, by_beta_n: pd.DataFrame, trends: pd.DataFrame
) -> None:
    """Fail closed when the frozen audit or its derived tables drift."""
    if len(metrics) != 300:
        raise ValueError(f"expected 300 metric rows, got {len(metrics)}")
    if metrics.duplicated(["beta", "n", "repeat_id"]).any():
        raise ValueError("duplicate beta-n-repeat rows")
    if not np.isfinite(metrics[METRIC_COLS].to_numpy(dtype=float)).all():
        raise ValueError("non-finite sample metrics")
    if len(by_beta_n) != 15 or set(by_beta_n["n_samples"]) != {20}:
        raise ValueError("expected 15 complete beta-n cells of 20 samples")
    expected_scopes = {"n=7", "n=10", "n=20", "pooled"}
    if set(trends["scope"]) != expected_scopes:
        raise ValueError("trend scopes do not match the frozen design")
    if not trends.groupby("metric")["scope"].nunique().eq(4).all():
        raise ValueError("each metric must have three n trends and one pooled trend")
    if not np.isfinite(trends["spearman_rho"]).all():
        raise ValueError("non-finite Spearman trend")


def _git_info() -> dict:
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=REPO_ROOT, text=True
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", None
    return {"git_commit": commit, "workspace_dirty": dirty}


def build_summary(trends: pd.DataFrame) -> dict:
    consistency = {}
    for metric in METRIC_COLS:
        within_n = trends[
            (trends["metric"] == metric) & (trends["scope"] != "pooled")
        ].copy()
        within_n["n_order"] = within_n["scope"].str.removeprefix("n=").astype(int)
        within_n = within_n.sort_values("n_order")
        rhos = [float(value) for value in within_n["spearman_rho"]]
        consistency[metric] = {
            "within_n_spearman_rho": {
                scope: float(rho)
                for scope, rho in zip(within_n["scope"], within_n["spearman_rho"])
            },
            "direction_consistent_across_n": direction_consistent(rhos),
        }
    return {
        "run_id": "E2_beta_profile_audit_v1",
        "created_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "design": {
            "beta": BETA_GRID,
            "eta": TRUE_ETA,
            "gamma_over_eta": TRUE_GAMMA / TRUE_ETA,
            "n": N_GRID,
            "repeat_ids": [min(REPEAT_IDS), max(REPEAT_IDS)],
            "n_samples": 300,
            "seed_namespace": SEED_NAMESPACE,
            "mdm_call": "MDM.run(trace=True, offset=0.1)",
        },
        "metric_trends": consistency,
        "evidence_boundary": {
            "causal_claim_allowed": False,
            "allowed_if_direction_consistent": (
                "profile curve geometry varies systematically with beta and is "
                "consistent with the proposed mechanism explanation"
            ),
            "prohibited_claims": [
                "tail shape causally determines optimal delta",
                "the mechanism is proven",
                "mediation is identified",
            ],
        },
    }


def write_outputs(
    metrics: pd.DataFrame,
    by_beta_n: pd.DataFrame,
    trends: pd.DataFrame,
    summary: dict,
) -> None:
    """Write validated outputs through a temporary sibling directory."""
    validate_outputs(metrics, by_beta_n, trends)
    manifest = {
        "run_id": summary["run_id"],
        "created_at": summary["created_at"],
        **_git_info(),
        "contract": "code/_ch5_beta_profile_audit_contract.md",
        "parameter_grid": summary["design"],
        "metric_definitions": {
            "gradient_at_zero": "profile gradient g(gamma) at gamma=0",
            "gradient_at_true_gamma": "linear interpolation of trace g(gamma) at true gamma=0.5",
            "local_gradient_slope": "OLS slope of g(gamma) on nearest 7 finite nonvirtual trace points",
            "gamma_hat_d01": "MDM solution at offset delta=0.1",
            "gamma_error_d01": "gamma_hat_d01 - true gamma",
        },
        "outputs": {
            "profile_metrics.csv": int(len(metrics)),
            "by_beta_n.csv": int(len(by_beta_n)),
            "trend_summary.csv": int(len(trends)),
            "summary.json": 1,
        },
    }
    OUTPUT_DIR.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix="E2_beta_profile_audit_", dir=OUTPUT_DIR.parent
    ) as temp_name:
        temp_dir = Path(temp_name)
        metrics.to_csv(temp_dir / "profile_metrics.csv", index=False)
        by_beta_n.to_csv(temp_dir / "by_beta_n.csv", index=False)
        trends.to_csv(temp_dir / "trend_summary.csv", index=False)
        (temp_dir / "summary.json").write_text(
            json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        (temp_dir / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        for path in temp_dir.iterdir():
            os.replace(path, OUTPUT_DIR / path.name)


def run_audit() -> dict:
    """Execute the frozen 300-sample audit and write formal artifacts."""
    started = time.perf_counter()
    design = build_design()
    rows = []
    for index, row in design.iterrows():
        rows.append(extract_sample_metrics(row.to_dict()))
        completed = index + 1
        if completed % 25 == 0 or completed == len(design):
            print(f"[beta-profile-audit] {completed}/{len(design)}")
    metrics = pd.DataFrame(rows)
    by_beta_n = summarize_by_beta_n(metrics)
    trends = compute_trends(metrics, METRIC_COLS)
    validate_outputs(metrics, by_beta_n, trends)
    summary = build_summary(trends)
    write_outputs(metrics, by_beta_n, trends, summary)
    elapsed = time.perf_counter() - started
    print(f"[beta-profile-audit] wrote {OUTPUT_DIR}")
    print(f"[beta-profile-audit] elapsed_seconds={elapsed:.2f}")
    return summary


if __name__ == "__main__":
    run_audit()
