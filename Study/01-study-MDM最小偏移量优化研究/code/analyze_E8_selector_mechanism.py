"""Diagnose why E8 curve prediction can underperform the fixed offset.

This is a read-only, post-hoc mechanism analysis.  It reuses the saved E5/E8
out-of-fold 26-point predictions and the shared 26-point MDM scan.  It does not
train a model, rerun MDM, select a new production rule, or modify formal data.

The analysis asks whether harmful adaptive decisions are associated with:

* small predicted improvement over the default offset;
* a spurious predicted minimum far from the realised hindsight minimum;
* poor prediction of the low-loss region despite acceptable whole-curve fit.

Threshold policies are descriptive diagnostics evaluated on the same OOF rows.
They must not be reported as independently validated methods.
"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
STUDY_ROOT = HERE.parent
E5_ROOT = STUDY_ROOT / "artifacts" / "formal" / "E5_normalized_raw"
SCAN_PATH = E5_ROOT / "shared_data" / "mc_scan_raw.csv"
PREDICTION_DIR = E5_ROOT / "specialist" / "predictions"
DEFAULT_OUTPUT = (
    STUDY_ROOT / "artifacts" / "candidate" /
    "E9_selector_mechanism_diagnostic"
)

SAMPLE_KEYS = [
    "beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id"
]
DELTA_GRID = np.round(np.arange(0.0, 0.5000001, 0.02), 2)
DEFAULT_DELTA = 0.10
DEFAULT_INDEX = int(np.flatnonzero(np.isclose(DELTA_GRID, DEFAULT_DELTA))[0])


def _pred_col(delta: float) -> str:
    return f"pred_d{float(delta)}"


def load_actual_curves() -> tuple[pd.DataFrame, np.ndarray]:
    columns = SAMPLE_KEYS + [
        "delta", "beta_hat", "eta_hat", "gamma_hat", "status"
    ]
    scan = pd.read_csv(SCAN_PATH, usecols=columns)
    if len(scan) != 160 * 300 * len(DELTA_GRID):
        raise RuntimeError(f"Unexpected scan row count: {len(scan)}")
    if scan.duplicated(SAMPLE_KEYS + ["delta"]).any():
        raise RuntimeError("Duplicate sample/delta rows in shared scan")

    r_beta = (scan["beta_hat"] - scan["beta"]) / scan["beta"]
    r_eta = (scan["eta_hat"] - scan["eta"]) / scan["eta"]
    r_gamma = (scan["gamma_hat"] - scan["gamma"]) / scan["eta"]
    scan["loss"] = r_beta**2 + r_eta**2 + r_gamma**2
    scan.loc[~np.isfinite(scan["loss"]), "loss"] = np.nan
    if scan["loss"].isna().any():
        raise RuntimeError("This diagnostic expects the zero-failure E5 scan")
    if not scan["status"].eq("success").all():
        raise RuntimeError("This diagnostic expects all scan rows to succeed")

    pivot = scan.pivot(index=SAMPLE_KEYS, columns="delta", values="loss")
    pivot = pivot.reindex(columns=DELTA_GRID)
    if pivot.shape != (48_000, 26) or pivot.isna().any().any():
        raise RuntimeError(f"Unexpected actual curve matrix: {pivot.shape}")
    return pivot, pivot.to_numpy(dtype=np.float64)


def load_predictions() -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    required_pred = [_pred_col(delta) for delta in DELTA_GRID]
    for path in sorted(PREDICTION_DIR.glob("n*_fold*_seed*.csv")):
        frame = pd.read_csv(path)
        missing = set(SAMPLE_KEYS + required_pred) - set(frame.columns)
        if missing:
            raise RuntimeError(f"{path.name} missing columns: {sorted(missing)}")
        stem = path.stem
        pieces = stem.split("_")
        frame["model_id"] = stem
        frame["fold"] = int(pieces[1].removeprefix("fold"))
        frame["seed"] = int(pieces[2].removeprefix("seed"))
        frames.append(frame)
    if len(frames) != 60:
        raise RuntimeError(f"Expected 60 prediction files, found {len(frames)}")
    predictions = pd.concat(frames, ignore_index=True)
    if len(predictions) != 144_000:
        raise RuntimeError(f"Expected 144000 OOF rows, found {len(predictions)}")
    if predictions.duplicated(SAMPLE_KEYS + ["seed"]).any():
        raise RuntimeError("Duplicate OOF sample/seed rows")
    return predictions


def align_curves(
    actual_pivot: pd.DataFrame, predictions: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    row_index = pd.MultiIndex.from_frame(predictions[SAMPLE_KEYS])
    actual = actual_pivot.reindex(row_index).to_numpy(dtype=np.float64)
    predicted = predictions[[_pred_col(d) for d in DELTA_GRID]].to_numpy(
        dtype=np.float64
    )
    if actual.shape != predicted.shape or not np.isfinite(predicted).all():
        raise RuntimeError(
            f"Curve alignment failed: actual={actual.shape}, predicted={predicted.shape}"
        )
    return actual, predicted


def build_row_diagnostics(
    predictions: pd.DataFrame, actual: np.ndarray, predicted: np.ndarray
) -> pd.DataFrame:
    selected_idx = np.argmin(predicted, axis=1)
    oracle_idx = np.argmin(actual, axis=1)
    rows = np.arange(len(predictions))
    selected_loss = actual[rows, selected_idx]
    default_loss = actual[:, DEFAULT_INDEX]
    oracle_loss = actual[rows, oracle_idx]
    predicted_selected = predicted[rows, selected_idx]
    predicted_default = predicted[:, DEFAULT_INDEX]

    recorded_idx = predictions["selected_delta_idx"].to_numpy(dtype=int)
    if not np.array_equal(recorded_idx, selected_idx):
        raise RuntimeError("Saved selected_delta_idx does not match curve argmin")
    if not np.allclose(
        predictions["true_loss"].to_numpy(dtype=float), selected_loss,
        rtol=0.0, atol=1e-12,
    ):
        raise RuntimeError("Saved selected loss does not match shared scan")

    curve_rmse = np.sqrt(np.mean((predicted - actual) ** 2, axis=1))
    actual_relative = actual - actual[:, [DEFAULT_INDEX]]
    predicted_relative = predicted - predicted[:, [DEFAULT_INDEX]]
    relative_curve_rmse = np.sqrt(
        np.mean((predicted_relative - actual_relative) ** 2, axis=1)
    )
    valley_mask = actual <= (oracle_loss[:, None] + 0.01)
    valley_sqerr = np.where(valley_mask, (predicted - actual) ** 2, np.nan)
    valley_rmse = np.sqrt(np.nanmean(valley_sqerr, axis=1))

    out = predictions[SAMPLE_KEYS + ["seed", "fold", "model_id"]].copy()
    out["selected_delta"] = DELTA_GRID[selected_idx]
    out["oracle_delta"] = DELTA_GRID[oracle_idx]
    out["default_loss"] = default_loss
    out["selected_loss"] = selected_loss
    out["oracle_loss"] = oracle_loss
    out["predicted_gain"] = predicted_default - predicted_selected
    out["actual_gain"] = default_loss - selected_loss
    out["selection_regret"] = selected_loss - oracle_loss
    out["oracle_available_gain"] = default_loss - oracle_loss
    out["delta_distance_to_oracle"] = np.abs(
        out["selected_delta"] - out["oracle_delta"]
    )
    out["delta_distance_to_default"] = np.abs(
        out["selected_delta"] - DEFAULT_DELTA
    )
    out["curve_rmse"] = curve_rmse
    out["relative_to_default_curve_rmse"] = relative_curve_rmse
    out["valley_rmse_0.01"] = valley_rmse
    out["actual_valley_width_0.01"] = valley_mask.sum(axis=1)
    actual_order = np.argsort(np.argsort(actual, axis=1), axis=1)
    out["selected_actual_rank"] = actual_order[rows, selected_idx] + 1
    out["improved"] = out["actual_gain"] > 1e-12
    out["harmed"] = out["actual_gain"] < -1e-12
    out["tied"] = ~(out["improved"] | out["harmed"])
    return out


def summarise_rows(rows: pd.DataFrame) -> dict[str, float | int]:
    default_j1 = math.sqrt(rows["default_loss"].mean())
    selected_j1 = math.sqrt(rows["selected_loss"].mean())
    oracle_j1 = math.sqrt(rows["oracle_loss"].mean())
    predicted_gain_corr = rows[["predicted_gain", "actual_gain"]].corr(
        method="spearman"
    ).iloc[0, 1]
    harmful = rows[rows["harmed"]]
    return {
        "n_model_sample_rows": int(len(rows)),
        "n_unique_samples": int(rows[SAMPLE_KEYS].drop_duplicates().shape[0]),
        "default_J1": default_j1,
        "adaptive_J1": selected_j1,
        "oracle_J1": oracle_j1,
        "relative_improvement_vs_default": 1.0 - selected_j1 / default_j1,
        "fraction_of_default_oracle_J1_gap_recovered": (
            (default_j1 - selected_j1) / (default_j1 - oracle_j1)
        ),
        "improved_rate": float(rows["improved"].mean()),
        "harmed_rate": float(rows["harmed"].mean()),
        "tie_rate": float(rows["tied"].mean()),
        "spearman_predicted_vs_actual_gain": float(predicted_gain_corr),
        "median_predicted_gain": float(rows["predicted_gain"].median()),
        "median_actual_gain": float(rows["actual_gain"].median()),
        "median_selection_regret": float(rows["selection_regret"].median()),
        "p95_selection_regret": float(rows["selection_regret"].quantile(0.95)),
        "p99_selection_regret": float(rows["selection_regret"].quantile(0.99)),
        "median_curve_rmse": float(rows["curve_rmse"].median()),
        "median_relative_to_default_curve_rmse": float(
            rows["relative_to_default_curve_rmse"].median()
        ),
        "median_valley_rmse_0.01": float(rows["valley_rmse_0.01"].median()),
        "median_actual_valley_width_0.01": float(
            rows["actual_valley_width_0.01"].median()
        ),
        "selected_delta_exact_oracle_rate": float(
            (rows["delta_distance_to_oracle"] < 1e-12).mean()
        ),
        "selected_delta_within_0.02_of_oracle_rate": float(
            (rows["delta_distance_to_oracle"] <= 0.0200001).mean()
        ),
        "median_selected_actual_rank": float(rows["selected_actual_rank"].median()),
        "p90_selected_actual_rank": float(rows["selected_actual_rank"].quantile(0.90)),
        "spearman_relative_curve_rmse_vs_regret": float(
            rows[["relative_to_default_curve_rmse", "selection_regret"]]
            .corr(method="spearman").iloc[0, 1]
        ),
        "harmful_far_from_oracle_rate": float(
            (harmful["delta_distance_to_oracle"] >= 0.10).mean()
        ),
        "harmful_default_near_oracle_rate": float(
            ((harmful["default_loss"] - harmful["oracle_loss"]) <= 0.01).mean()
        ),
    }


def calibration_table(rows: pd.DataFrame) -> pd.DataFrame:
    ranked = rows.copy()
    ranked["predicted_gain_decile"] = pd.qcut(
        ranked["predicted_gain"].rank(method="first"), 10, labels=False
    ) + 1
    grouped = ranked.groupby("predicted_gain_decile", observed=True)
    return grouped.agg(
        n=("actual_gain", "size"),
        predicted_gain_min=("predicted_gain", "min"),
        predicted_gain_median=("predicted_gain", "median"),
        predicted_gain_max=("predicted_gain", "max"),
        actual_gain_mean=("actual_gain", "mean"),
        actual_gain_median=("actual_gain", "median"),
        improved_rate=("improved", "mean"),
        harmed_rate=("harmed", "mean"),
        selection_regret_mean=("selection_regret", "mean"),
        delta_distance_to_oracle_median=("delta_distance_to_oracle", "median"),
    ).reset_index()


def descriptive_gate_table(rows: pd.DataFrame) -> pd.DataFrame:
    default_j1 = math.sqrt(rows["default_loss"].mean())
    quantiles = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
    thresholds = sorted(set(float(rows["predicted_gain"].quantile(q)) for q in quantiles))
    records = []
    for threshold in thresholds:
        use_adaptive = rows["predicted_gain"].to_numpy() > threshold
        policy_loss = np.where(
            use_adaptive,
            rows["selected_loss"].to_numpy(),
            rows["default_loss"].to_numpy(),
        )
        policy_j1 = math.sqrt(float(np.mean(policy_loss)))
        records.append({
            "threshold": threshold,
            "adaptive_coverage": float(use_adaptive.mean()),
            "policy_J1_same_data_descriptive": policy_j1,
            "relative_improvement_vs_default_same_data": 1.0 - policy_j1 / default_j1,
            "actual_improved_rate_among_adaptive": float(
                rows.loc[use_adaptive, "improved"].mean()
            ),
            "actual_harmed_rate_among_adaptive": float(
                rows.loc[use_adaptive, "harmed"].mean()
            ),
        })
    return pd.DataFrame(records)


def distance_table(rows: pd.DataFrame) -> pd.DataFrame:
    bins = [-1e-12, 0.0200001, 0.0600001, 0.1000001, 0.2000001, np.inf]
    labels = ["0-0.02", "0.04-0.06", "0.08-0.10", "0.12-0.20", ">0.20"]
    binned = rows.copy()
    binned["distance_bin"] = pd.cut(
        binned["delta_distance_to_oracle"], bins=bins, labels=labels
    )
    return binned.groupby("distance_bin", observed=True).agg(
        n=("actual_gain", "size"),
        row_rate=("actual_gain", lambda x: len(x) / len(rows)),
        actual_gain_mean=("actual_gain", "mean"),
        improved_rate=("improved", "mean"),
        harmed_rate=("harmed", "mean"),
        selection_regret_mean=("selection_regret", "mean"),
        selection_regret_p95=("selection_regret", lambda x: x.quantile(0.95)),
    ).reset_index()


def seed_table(rows: pd.DataFrame) -> pd.DataFrame:
    records = []
    for seed, part in rows.groupby("seed"):
        summary = summarise_rows(part)
        summary["seed"] = int(seed)
        records.append(summary)
    return pd.DataFrame(records)


def ensemble_diagnostics(
    predictions: pd.DataFrame, actual_pivot: pd.DataFrame
) -> tuple[dict[str, float | int], pd.DataFrame]:
    pred_cols = [_pred_col(d) for d in DELTA_GRID]
    grouped = predictions.groupby(SAMPLE_KEYS, sort=True, observed=True)
    mean_predictions = grouped[pred_cols].mean().reset_index()
    if len(mean_predictions) != 48_000:
        raise RuntimeError("Expected one ensemble prediction per unique sample")
    row_index = pd.MultiIndex.from_frame(mean_predictions[SAMPLE_KEYS])
    actual = actual_pivot.reindex(row_index).to_numpy(dtype=np.float64)
    predicted = mean_predictions[pred_cols].to_numpy(dtype=np.float64)

    selected_idx = np.argmin(predicted, axis=1)
    oracle_idx = np.argmin(actual, axis=1)
    row_ids = np.arange(len(mean_predictions))
    selected_loss = actual[row_ids, selected_idx]
    default_loss = actual[:, DEFAULT_INDEX]
    oracle_loss = actual[row_ids, oracle_idx]
    predicted_gain = predicted[:, DEFAULT_INDEX] - predicted[row_ids, selected_idx]
    actual_gain = default_loss - selected_loss

    seed_choices = predictions[SAMPLE_KEYS + ["seed", "selected_delta_idx"]].copy()
    choice_counts = seed_choices.groupby(SAMPLE_KEYS, observed=True)[
        "selected_delta_idx"
    ].nunique()
    if len(choice_counts) != 48_000:
        raise RuntimeError("Seed-choice agreement did not cover all samples")

    ensemble_summary = {
        "n_unique_samples": int(len(mean_predictions)),
        "default_J1": math.sqrt(float(default_loss.mean())),
        "ensemble_adaptive_J1": math.sqrt(float(selected_loss.mean())),
        "oracle_J1": math.sqrt(float(oracle_loss.mean())),
        "relative_improvement_vs_default": 1.0 - math.sqrt(float(selected_loss.mean())) / math.sqrt(float(default_loss.mean())),
        "improved_rate": float((actual_gain > 1e-12).mean()),
        "harmed_rate": float((actual_gain < -1e-12).mean()),
        "tie_rate": float((np.abs(actual_gain) <= 1e-12).mean()),
        "spearman_predicted_vs_actual_gain": float(
            pd.Series(predicted_gain).corr(pd.Series(actual_gain), method="spearman")
        ),
        "selected_delta_exact_oracle_rate": float((selected_idx == oracle_idx).mean()),
        "selected_delta_within_0.02_of_oracle_rate": float(
            (np.abs(DELTA_GRID[selected_idx] - DELTA_GRID[oracle_idx]) <= 0.0200001).mean()
        ),
        "three_seed_unanimous_choice_rate": float((choice_counts == 1).mean()),
        "three_seed_two_choice_rate": float((choice_counts == 2).mean()),
        "three_seed_three_choice_rate": float((choice_counts == 3).mean()),
    }

    tolerance_records = []
    for tolerance in [0.0, 0.001, 0.002, 0.005, 0.01, 0.02, 0.05]:
        eligible = predicted <= (predicted.min(axis=1, keepdims=True) + tolerance)
        distance_to_default = np.abs(DELTA_GRID - DEFAULT_DELTA)
        tie_scores = np.where(eligible, distance_to_default[None, :], np.inf)
        tolerant_idx = np.argmin(tie_scores, axis=1)
        tolerant_loss = actual[row_ids, tolerant_idx]
        tolerant_gain = default_loss - tolerant_loss
        tolerance_records.append({
            "predicted_near_min_tolerance": tolerance,
            "policy_J1_same_data_descriptive": math.sqrt(float(tolerant_loss.mean())),
            "relative_improvement_vs_default_same_data": (
                1.0 - math.sqrt(float(tolerant_loss.mean())) / math.sqrt(float(default_loss.mean()))
            ),
            "improved_rate": float((tolerant_gain > 1e-12).mean()),
            "harmed_rate": float((tolerant_gain < -1e-12).mean()),
            "mean_abs_delta_change_from_plain_ensemble": float(
                np.mean(np.abs(DELTA_GRID[tolerant_idx] - DELTA_GRID[selected_idx]))
            ),
        })
    return ensemble_summary, pd.DataFrame(tolerance_records)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    actual_pivot, _ = load_actual_curves()
    predictions = load_predictions()
    actual, predicted = align_curves(actual_pivot, predictions)
    rows = build_row_diagnostics(predictions, actual, predicted)
    ensemble_summary, tolerance_table = ensemble_diagnostics(
        predictions, actual_pivot
    )

    summary = summarise_rows(rows)
    summary["status"] = "DESCRIPTIVE_MECHANISM_DIAGNOSTIC"
    summary["warning"] = (
        "Gate thresholds are evaluated on the same OOF diagnostic rows and are "
        "not independently validated method results."
    )
    (args.output / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    calibration_table(rows).to_csv(
        args.output / "calibration_by_predicted_gain.csv", index=False
    )
    descriptive_gate_table(rows).to_csv(
        args.output / "descriptive_gate_thresholds.csv", index=False
    )
    distance_table(rows).to_csv(
        args.output / "distance_to_oracle.csv", index=False
    )
    seed_table(rows).to_csv(args.output / "summary_by_seed.csv", index=False)
    (args.output / "three_seed_curve_ensemble_summary.json").write_text(
        json.dumps(ensemble_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    tolerance_table.to_csv(
        args.output / "descriptive_near_min_tolerance.csv", index=False
    )

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote diagnostic summaries to {args.output}")


if __name__ == "__main__":
    main()
