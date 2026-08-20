"""Diagnose why the sample-specific low-risk MDM offset changes.

This bounded mechanism experiment reuses the untouched E10 confirmation
repeats (200..299) and the frozen 26-point MDM scan.  It does not train a new
selector or rerun the offset grid.  For a balanced set of parameter-domain
corners plus the centre, it regenerates each sample once and records the MDM
profile-gradient trace at the default offset.

The scientific question is deliberately narrow: within a fixed
``(beta, gamma/eta, n)`` cell, does random sample geometry move the profiled
MDM gradient curve in a way that also moves the realised low-risk offset?
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr


HERE = Path(__file__).resolve().parent
STUDY_ROOT = HERE.parent
REPO_ROOT = STUDY_ROOT.parents[1]
PYTHON_ROOT = REPO_ROOT / "python"
for path in (HERE, PYTHON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import dim_raw_config as CFG
from methods.mdm import MDM
from studies.common.sample import generate_sample


CONTRACT = "E11_profile_mechanism_v1"
OUTPUT_DIR = STUDY_ROOT / "artifacts" / "formal" / "E11_profile_mechanism"
CONFIRMATION_REPEATS = tuple(range(200, 300))
PARAMETER_PAIRS = (
    (1.5, 0.10),
    (1.5, 1.00),
    (3.0, 0.50),
    (5.0, 0.10),
    (5.0, 1.00),
)
N_VALUES = tuple(CFG.N_GRID)
TARGET_OFFSET = float(CFG.DEFAULT_DELTA)
OUTPUT_FILES = (
    "sample_metrics.csv",
    "cell_associations.csv",
    "conditional_loss_curves.csv",
    "representative_gradient_curves.csv",
    "summary.json",
    "mechanism_report.md",
)


def sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="\n")


def selected_cells() -> pd.DataFrame:
    """Return the predeclared 5 parameter locations x 4 sample sizes."""
    rows = [
        {
            "beta": float(beta),
            "eta": float(CFG.ETA),
            "gamma_over_eta": float(ratio),
            "gamma": float(CFG.ETA * ratio),
            "n": int(n_value),
        }
        for beta, ratio in PARAMETER_PAIRS
        for n_value in N_VALUES
    ]
    return pd.DataFrame(rows)


def _find_chunk(cell: dict) -> tuple[Path, Path]:
    chunk_dir = Path(CFG.CHUNKS_DIR)
    matches: list[tuple[Path, Path]] = []
    for meta_path in sorted(chunk_dir.glob("chunk_*_meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        unit = meta["unit"]
        if (
            np.isclose(float(unit["beta"]), float(cell["beta"]))
            and np.isclose(
                float(unit["gamma_over_eta"]), float(cell["gamma_over_eta"])
            )
            and int(unit["n"]) == int(cell["n"])
        ):
            mdm_path = meta_path.with_name(meta_path.name.replace("_meta.json", "_mdm.csv"))
            matches.append((meta_path, mdm_path))
    if len(matches) != 1 or not matches[0][1].is_file():
        raise RuntimeError(f"expected one complete chunk for {cell}, got {matches}")
    return matches[0]


def _sample_loss(frame: pd.DataFrame) -> pd.Series:
    return (
        ((frame["beta_hat"] - frame["beta"]) / frame["beta"]) ** 2
        + ((frame["eta_hat"] - frame["eta"]) / frame["eta"]) ** 2
        + ((frame["gamma_hat"] - frame["gamma"]) / frame["eta"]) ** 2
    )


def load_cell_scan(cell: dict) -> tuple[pd.DataFrame, dict]:
    """Load and validate the frozen 100 x 26 confirmation rows for one cell."""
    meta_path, mdm_path = _find_chunk(cell)
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    frame = pd.read_csv(mdm_path, low_memory=False)
    frame = frame[frame["repeat_id"].isin(CONFIRMATION_REPEATS)].copy()
    expected = len(CONFIRMATION_REPEATS) * len(CFG.DELTA_GRID)
    if len(frame) != expected:
        raise RuntimeError(f"{mdm_path.name}: expected {expected} rows, got {len(frame)}")
    if frame.duplicated(["repeat_id", "delta"]).any():
        raise RuntimeError(f"{mdm_path.name}: duplicate repeat-delta rows")
    if set(frame["repeat_id"].astype(int)) != set(CONFIRMATION_REPEATS):
        raise RuntimeError(f"{mdm_path.name}: incomplete confirmation repeats")
    if not np.allclose(sorted(frame["delta"].unique()), CFG.DELTA_GRID):
        raise RuntimeError(f"{mdm_path.name}: delta grid drift")
    if not frame["status"].eq("success").all():
        raise RuntimeError(f"{mdm_path.name}: unexpected failed MDM estimate")
    frame["loss"] = _sample_loss(frame)
    if not np.isfinite(frame["loss"]).all():
        raise RuntimeError(f"{mdm_path.name}: non-finite loss")
    return frame, {
        "meta": str(meta_path.relative_to(STUDY_ROOT)).replace("\\", "/"),
        "data": str(mdm_path.relative_to(STUDY_ROOT)).replace("\\", "/"),
        "meta_sha256_lf": sha256_lf(meta_path),
        "data_sha256_lf": sha256_lf(mdm_path),
        "seed_namespace": meta["seed_namespace"],
    }


def _finite_curve(trace: dict) -> pd.DataFrame:
    frame = pd.DataFrame(trace["grad_gamma_curve"])
    if "virtual" in frame:
        virtual = pd.Series(frame["virtual"], dtype="boolean").fillna(False).to_numpy()
    else:
        virtual = np.zeros(len(frame), dtype=bool)
    frame = frame[~virtual].copy()
    frame = frame[np.isfinite(frame["gamma"]) & np.isfinite(frame["gradient"])]
    frame = frame.sort_values("gamma").drop_duplicates("gamma")
    if len(frame) < 20:
        raise RuntimeError("profile-gradient trace is unexpectedly short")
    return frame


def interpolate_gradient(curve: pd.DataFrame, target_gamma: float) -> float:
    if target_gamma < curve["gamma"].min() or target_gamma > curve["gamma"].max():
        raise RuntimeError("true gamma lies outside the finite profile trace")
    return float(np.interp(target_gamma, curve["gamma"], curve["gradient"]))


def local_gradient_slope(
    curve: pd.DataFrame, target_gamma: float, k: int = 7
) -> float:
    nearest = curve.assign(
        distance=(curve["gamma"] - float(target_gamma)).abs()
    ).nsmallest(k, ["distance", "gamma"])
    if len(nearest) != k:
        raise RuntimeError(f"need {k} finite points for local slope")
    return float(np.polyfit(nearest["gamma"], nearest["gradient"], 1)[0])


def extract_sample(
    cell: dict, repeat_id: int, scan: pd.DataFrame
) -> tuple[dict, pd.DataFrame]:
    """Extract one sample's geometry, gradient trace and realised best offset."""
    sample = generate_sample(
        float(cell["beta"]),
        float(cell["eta"]),
        float(cell["gamma"]),
        int(cell["n"]),
        int(repeat_id),
        seed=CFG.SEED_NAMESPACE,
    )
    mdm = MDM(sample)
    _, _, gamma_default, _, status = mdm.run(
        trace=True, offset=TARGET_OFFSET, gamma_steps=60
    )
    if not status:
        raise RuntimeError("default MDM trace did not converge")
    curve = _finite_curve(mdm.trace_data)

    rows = scan[scan["repeat_id"].astype(int) == int(repeat_id)].sort_values("delta")
    if len(rows) != len(CFG.DELTA_GRID):
        raise RuntimeError("sample scan is incomplete")
    losses = rows["loss"].to_numpy(dtype=float)
    best_index = int(np.argmin(losses))
    best = rows.iloc[best_index]
    default_rows = rows[np.isclose(rows["delta"], TARGET_OFFSET)]
    if len(default_rows) != 1:
        raise RuntimeError("default offset row is missing or duplicated")
    default = default_rows.iloc[0]

    sample_mean = float(np.mean(sample))
    sample_sd = float(np.std(sample, ddof=1))
    true_gamma = float(cell["gamma"])
    metric = {
        **{key: cell[key] for key in ("beta", "eta", "gamma", "gamma_over_eta", "n")},
        "repeat_id": int(repeat_id),
        "gradient_at_zero": float(mdm.trace_data["probe_gradient_at_zero"]),
        "gradient_at_true_gamma": interpolate_gradient(curve, true_gamma),
        "local_gradient_slope_eta_scaled": float(
            local_gradient_slope(curve, true_gamma) * float(cell["eta"])
        ),
        "default_solution_strategy": str(mdm.trace_data["solution_strategy"]),
        "gamma_hat_default": float(gamma_default),
        "gamma_hat_default_over_eta": float(gamma_default / float(cell["eta"])),
        "l6_delta": float(best["delta"]),
        "l6_loss": float(best["loss"]),
        "default_loss": float(default["loss"]),
        "l6_gamma_hat": float(best["gamma_hat"]),
        "l6_solution_at_boundary": bool(np.isclose(float(best["gamma_hat"]), 0.0)),
        "sample_min_over_mean": float(sample[0] / sample_mean),
        "lower_gap_over_mean": float((sample[1] - sample[0]) / sample_mean),
        "sample_cv": float(sample_sd / sample_mean),
    }
    finite_names = [
        "gradient_at_zero", "gradient_at_true_gamma",
        "local_gradient_slope_eta_scaled", "gamma_hat_default",
        "gamma_hat_default_over_eta", "l6_delta", "l6_loss",
        "default_loss", "l6_gamma_hat", "sample_min_over_mean",
        "lower_gap_over_mean", "sample_cv",
    ]
    if not np.isfinite([metric[name] for name in finite_names]).all():
        raise RuntimeError("non-finite sample mechanism metric")
    return metric, curve


def _within_cell_tertiles(metrics: pd.DataFrame, column: str) -> pd.DataFrame:
    out = metrics.copy()
    labels = ("low", "middle", "high")
    out["tertile"] = (
        out.groupby(["beta", "gamma_over_eta", "n"], group_keys=False)[
            column
        ]
        .transform(lambda values: pd.qcut(values.rank(method="first"), 3, labels=labels))
        .astype(str)
    )
    return out


def derive_associations(metrics: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grouping = ["beta", "gamma_over_eta", "n"]
    for keys, frame in metrics.groupby(grouping, sort=True):
        row = dict(zip(grouping, keys))
        row["n_samples"] = int(len(frame))
        for target in (
            "l6_delta", "gamma_hat_default_over_eta", "gradient_at_true_gamma",
            "local_gradient_slope_eta_scaled", "sample_min_over_mean",
            "lower_gap_over_mean", "sample_cv"
        ):
            result = spearmanr(frame["gradient_at_zero"], frame[target])
            row[f"rho_g0_{target}"] = float(result.statistic)
        row["rho_default_gamma_l6_delta"] = float(
            spearmanr(frame["gamma_hat_default_over_eta"], frame["l6_delta"]).statistic
        )
        row["l6_boundary_rate"] = float(frame["l6_solution_at_boundary"].mean())
        row["default_boundary_rate"] = float(
            frame["default_solution_strategy"].eq("truncated_at_zero").mean()
        )
        rows.append(row)
    result = pd.DataFrame(rows)
    if len(result) != len(PARAMETER_PAIRS) * len(N_VALUES):
        raise RuntimeError("cell association table is incomplete")
    return result


def derive_conditional_curves(
    metrics: pd.DataFrame, scans: dict[tuple[float, float, int], pd.DataFrame]
) -> pd.DataFrame:
    rows = []
    stratifiers = {
        "gradient_at_zero": "gradient_at_zero",
        "default_gamma_hat": "gamma_hat_default_over_eta",
    }
    for stratifier, column in stratifiers.items():
        tagged = _within_cell_tertiles(metrics, column)
        for _, sample_row in tagged.iterrows():
            key = (
                float(sample_row["beta"]),
                float(sample_row["gamma_over_eta"]),
                int(sample_row["n"]),
            )
            frame = scans[key]
            scan_rows = frame[
                frame["repeat_id"].astype(int) == int(sample_row["repeat_id"])
            ]
            for _, loss_row in scan_rows.iterrows():
                rows.append(
                    {
                        "stratifier": stratifier,
                        "beta": key[0],
                        "gamma_over_eta": key[1],
                        "n": key[2],
                        "repeat_id": int(sample_row["repeat_id"]),
                        "tertile": sample_row["tertile"],
                        "delta": float(loss_row["delta"]),
                        "loss": float(loss_row["loss"]),
                        "excess_over_l6": float(loss_row["loss"] - sample_row["l6_loss"]),
                    }
                )
    long = pd.DataFrame(rows)
    # Equal repeats in every selected cell make the pooled average also cell-equal.
    summary = (
        long.groupby(["stratifier", "tertile", "delta"], as_index=False)
        .agg(
            R_mean_loss=("loss", "mean"),
            mean_excess_over_l6=("excess_over_l6", "mean"),
            n_samples=("loss", "size"),
        )
    )
    summary["J1"] = np.sqrt(summary["R_mean_loss"])
    order = {"low": 0, "middle": 1, "high": 2}
    summary["_order"] = summary["tertile"].map(order)
    return summary.sort_values(["stratifier", "_order", "delta"]).drop(columns="_order")


def representative_curves(
    metrics: pd.DataFrame,
    traces: dict[tuple[float, float, int, int], pd.DataFrame],
) -> pd.DataFrame:
    """Select three default-root quantiles from the central n=10 cell."""
    frame = metrics[
        np.isclose(metrics["beta"], 3.0)
        & np.isclose(metrics["gamma_over_eta"], 0.50)
        & (metrics["n"] == 10)
    ].sort_values("gamma_hat_default_over_eta")
    if len(frame) != len(CONFIRMATION_REPEATS):
        raise RuntimeError("central representative cell is incomplete")
    ranked = frame.copy()
    ranked["profile_group"] = pd.qcut(
        ranked["gamma_hat_default_over_eta"].rank(method="first"),
        3,
        labels=("low", "middle", "high"),
    ).astype(str)
    rows = []
    for label, group in ranked.groupby("profile_group", sort=False):
        target_gamma = float(group["gamma_hat_default_over_eta"].median())
        target_delta = float(group["l6_delta"].median())
        gamma_scale = max(float(group["gamma_hat_default_over_eta"].std()), 1e-12)
        score = (
            (group["gamma_hat_default_over_eta"] - target_gamma).abs() / gamma_scale
            + (group["l6_delta"] - target_delta).abs() / 0.02
        )
        chosen = group.loc[score.idxmin()]
        key = (3.0, 0.50, 10, int(chosen["repeat_id"]))
        curve = traces[key]
        for _, point in curve.iterrows():
            rows.append(
                {
                    "profile_group": label,
                    "repeat_id": int(chosen["repeat_id"]),
                    "gradient_at_zero": float(chosen["gradient_at_zero"]),
                    "gamma_hat_default_over_eta": float(
                        chosen["gamma_hat_default_over_eta"]
                    ),
                    "l6_delta": float(chosen["l6_delta"]),
                    "l6_gamma_hat_over_eta": float(chosen["l6_gamma_hat"] / CFG.ETA),
                    "gamma_over_eta": float(point["gamma"] / CFG.ETA),
                    "gradient": float(point["gradient"]),
                }
            )
    return pd.DataFrame(rows)


def validate_outputs(
    metrics: pd.DataFrame,
    associations: pd.DataFrame,
    curves: pd.DataFrame,
    representatives: pd.DataFrame,
) -> None:
    expected_samples = len(PARAMETER_PAIRS) * len(N_VALUES) * len(CONFIRMATION_REPEATS)
    if len(metrics) != expected_samples:
        raise RuntimeError(f"expected {expected_samples} samples, got {len(metrics)}")
    if metrics.duplicated(["beta", "gamma_over_eta", "n", "repeat_id"]).any():
        raise RuntimeError("duplicate sample metrics")
    if associations["n_samples"].nunique() != 1 or associations["n_samples"].iloc[0] != 100:
        raise RuntimeError("each mechanism cell must contain 100 confirmation samples")
    expected_stratifiers = {"gradient_at_zero", "default_gamma_hat"}
    if set(curves["stratifier"]) != expected_stratifiers:
        raise RuntimeError("conditional curves do not contain both trace stratifiers")
    if set(curves["tertile"]) != {"low", "middle", "high"}:
        raise RuntimeError("conditional curves do not contain all tertiles")
    if not curves.groupby(["stratifier", "tertile"])["delta"].nunique().eq(26).all():
        raise RuntimeError("conditional curves do not contain the 26-point grid")
    if set(representatives["profile_group"]) != {"low", "middle", "high"}:
        raise RuntimeError("representative profile curves are incomplete")


def summarize(
    metrics: pd.DataFrame,
    associations: pd.DataFrame,
    curves: pd.DataFrame,
    chunk_receipts: list[dict],
    runtime_seconds: float,
) -> dict:
    rho = associations["rho_g0_l6_delta"].to_numpy(dtype=float)
    rho_gamma = associations["rho_g0_gamma_hat_default_over_eta"].to_numpy(dtype=float)
    rho_gamma_delta = associations["rho_default_gamma_l6_delta"].to_numpy(dtype=float)
    minima = {}
    for (stratifier, label), frame in curves.groupby(["stratifier", "tertile"]):
        row = frame.loc[frame["mean_excess_over_l6"].idxmin()]
        minima.setdefault(stratifier, {})[label] = {
            "delta": float(row["delta"]),
            "mean_excess_over_l6": float(row["mean_excess_over_l6"]),
            "R_mean_loss": float(row["R_mean_loss"]),
            "J1": float(row["J1"]),
        }
    return {
        "status": "FORMAL_SUPPORTING_MECHANISM_EVIDENCE",
        "contract": CONTRACT,
        "question": (
            "Within fixed beta-gamma_over_eta-n cells, does random sample geometry "
            "move the MDM profile gradient and the realised low-risk offset together?"
        ),
        "design": {
            "parameter_pairs": [list(pair) for pair in PARAMETER_PAIRS],
            "n_values": list(N_VALUES),
            "confirmation_repeats": [min(CONFIRMATION_REPEATS), max(CONFIRMATION_REPEATS)],
            "cells": int(len(associations)),
            "samples": int(len(metrics)),
            "delta_grid": list(CFG.DELTA_GRID),
            "seed_namespace": CFG.SEED_NAMESPACE,
            "selection_rule": "four parameter-domain corners plus centre, crossed with all four n values",
        },
        "primary_result": {
            "median_within_cell_spearman_g0_vs_l6_delta": float(np.median(rho)),
            "q1": float(np.quantile(rho, 0.25)),
            "q3": float(np.quantile(rho, 0.75)),
            "min": float(np.min(rho)),
            "max": float(np.max(rho)),
            "positive_cell_fraction": float(np.mean(rho > 0)),
            "median_within_cell_spearman_default_gamma_vs_l6_delta": float(
                np.median(rho_gamma_delta)
            ),
            "default_gamma_vs_l6_delta_q1": float(np.quantile(rho_gamma_delta, 0.25)),
            "default_gamma_vs_l6_delta_q3": float(np.quantile(rho_gamma_delta, 0.75)),
            "negative_default_gamma_association_cell_fraction": float(
                np.mean(np.asarray(rho_gamma_delta) < 0)
            ),
            "median_within_cell_spearman_g0_vs_default_gamma": float(
                np.median(rho_gamma)
            ),
            "conditional_curve_minima": minima,
            "l6_boundary_rate": float(metrics["l6_solution_at_boundary"].mean()),
            "default_boundary_rate": float(
                metrics["default_solution_strategy"].eq("truncated_at_zero").mean()
            ),
        },
        "interpretation": (
            "Random samples from the same true-parameter cell shift the empirical MDM "
            "profile-gradient curve.  g(0) is a compact trace marker: when it moves, "
            "the low-risk region of the realised 26-point loss curve also moves.  "
            "The gamma=0 constraint is a special case, not assumed to be the dominant mechanism."
        ),
        "limitations": [
            "The analysis uses 20 predeclared cells, not all 160 design cells.",
            "L6 remains a 26-point hindsight reference and is not a deployable decision rule.",
            "Associations diagnose a numerical mechanism; they do not prove a closed-form causal decomposition.",
        ],
        "chunk_receipts": chunk_receipts,
        "runtime_seconds": float(runtime_seconds),
        "runtime_head_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, text=True
        ).strip(),
        "script_sha256_lf": sha256_lf(Path(__file__)),
    }


def write_report(summary: dict, output_dir: Path = OUTPUT_DIR) -> None:
    result = summary["primary_result"]
    minima = result["conditional_curve_minima"]["default_gamma_hat"]
    text = f"""# E11 MDM profile-gradient mechanism diagnostic

Status: `{summary['status']}`

## Question

Within the same true-parameter cell, why can the realised low-risk offset change
from one random sample to another?

## Design

The diagnostic uses four parameter-domain corners plus the centre, crossed with
all four trained sample sizes: {summary['design']['cells']} cells and
{summary['design']['samples']} untouched confirmation samples.  It reuses the
frozen 26-point loss scan and regenerates only one MDM profile trace per sample.

## Result

- Median within-cell Spearman correlation between `g(0)` and the L6 offset:
  **{result['median_within_cell_spearman_g0_vs_l6_delta']:.3f}**
  (IQR {result['q1']:.3f} to {result['q3']:.3f}; range
  {result['min']:.3f} to {result['max']:.3f}).
- Positive association in {100 * result['positive_cell_fraction']:.1f}% of cells.
- Median within-cell correlation between the default-offset location estimate
  and the L6 offset: **{result['median_within_cell_spearman_default_gamma_vs_l6_delta']:.3f}**
  (IQR {result['default_gamma_vs_l6_delta_q1']:.3f} to
  {result['default_gamma_vs_l6_delta_q3']:.3f}); the direction is negative in
  {100 * result['negative_default_gamma_association_cell_fraction']:.1f}% of cells.
- Conditional pooled excess-loss minima for low/middle/high within-cell default
  location estimates:
  {minima['low']['delta']:.2f}, {minima['middle']['delta']:.2f},
  {minima['high']['delta']:.2f}.
- L6 solutions at the `gamma=0` boundary: {100 * result['l6_boundary_rate']:.2f}%;
  default-offset boundary solutions: {100 * result['default_boundary_rate']:.2f}%.

## Interpretation

The sample-specific phenomenon is not adequately described as a boundary switch.
Even within a fixed `(beta, gamma/eta, n)` cell, random lower-order statistics move
the empirical profiled MDM gradient curve.  The offset solves an intersection
condition on that curve, so the corresponding MDM estimates and their coupled
three-parameter loss change with the sample.  `g(0)` is a compact diagnostic of
that displacement: its within-cell ordering also orders the low-risk region of
the realised offset-loss curve.

This explains why L5, which chooses one average offset per parameter cell, cannot
match L6 sample by sample.  It does not make L6 deployable and does not identify
an exact Bayes rule from observable data.

## Boundaries

""" + "\n".join(f"- {item}" for item in summary["limitations"]) + "\n"
    _write_text(Path(output_dir) / "mechanism_report.md", text)


def run(output_dir: Path = OUTPUT_DIR) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    started = time.time()

    metric_rows = []
    traces: dict[tuple[float, float, int, int], pd.DataFrame] = {}
    scans: dict[tuple[float, float, int], pd.DataFrame] = {}
    receipts = []
    cells = selected_cells()
    for _, cell_row in cells.iterrows():
        cell = cell_row.to_dict()
        key = (float(cell["beta"]), float(cell["gamma_over_eta"]), int(cell["n"]))
        scan, receipt = load_cell_scan(cell)
        scans[key] = scan
        receipts.append(receipt)
        print(f"[E11] beta={key[0]:.1f}, gamma/eta={key[1]:.2f}, n={key[2]}", flush=True)
        for repeat_id in CONFIRMATION_REPEATS:
            metric, curve = extract_sample(cell, repeat_id, scan)
            metric_rows.append(metric)
            traces[(*key, int(repeat_id))] = curve

    metrics = pd.DataFrame(metric_rows).sort_values(
        ["beta", "gamma_over_eta", "n", "repeat_id"]
    )
    associations = derive_associations(metrics)
    conditional = derive_conditional_curves(metrics, scans)
    representatives = representative_curves(metrics, traces)
    validate_outputs(metrics, associations, conditional, representatives)

    metrics.to_csv(output_dir / "sample_metrics.csv", index=False, lineterminator="\n")
    associations.to_csv(
        output_dir / "cell_associations.csv", index=False, lineterminator="\n"
    )
    conditional.to_csv(
        output_dir / "conditional_loss_curves.csv", index=False, lineterminator="\n"
    )
    representatives.to_csv(
        output_dir / "representative_gradient_curves.csv", index=False, lineterminator="\n"
    )
    summary = summarize(metrics, associations, conditional, receipts, time.time() - started)
    _write_text(
        output_dir / "summary.json",
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
    )
    write_report(summary, output_dir)
    lines = [f"{sha256_lf(output_dir / name)}  {name}" for name in OUTPUT_FILES]
    _write_text(output_dir / "SHA256SUMS", "\n".join(lines) + "\n")
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
