"""Cross-fitted sensitivity validation for Study/01 L1-L5.

The sealed E1/E2 analyses choose and score each empirical grid argmin on the
same Monte Carlo cache.  This module leaves those artifacts untouched and uses
five repeat-id folds to check whether the L1-L5 hierarchy persists when every
reported loss is scored on repeats that did not select the corresponding
delta.  L6 is intentionally excluded because it is a per-sample hindsight
benchmark rather than an out-of-sample decision rule.
"""

from __future__ import annotations

import hashlib
import json
import math
import subprocess
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd


STUDY_ROOT = Path(__file__).resolve().parents[1]
INPUT_PATH = STUDY_ROOT / "artifacts" / "formal" / "shared_data" / "mc_scan_raw.csv"
OUTPUT_DIR = STUDY_ROOT / "artifacts" / "formal" / "E1_E2_crossfit"

COMBO_COLS = ["beta", "eta", "gamma", "gamma_over_eta", "n"]
SAMPLE_COLS = COMBO_COLS + ["repeat_id"]
LAYER_GROUPS = {
    "L1": [],
    "L2": ["n"],
    "L3": ["beta"],
    "L4": ["beta", "n"],
    "L5": ["beta", "gamma_over_eta", "n"],
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git_info() -> dict:
    repo_root = STUDY_ROOT.parents[1]
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, text=True
        ).strip()
        dirty = bool(
            subprocess.check_output(
                ["git", "status", "--porcelain"], cwd=repo_root, text=True
            ).strip()
        )
    except (OSError, subprocess.CalledProcessError):
        commit, dirty = "unknown", None
    return {"git_commit": commit, "workspace_dirty": dirty}


def prepare_scan(raw: pd.DataFrame) -> pd.DataFrame:
    """Return successful scan rows with the canonical unrooted sample loss."""
    data = raw.copy()
    if "j1_sq" not in data.columns:
        required = {
            "beta_hat",
            "eta_hat",
            "gamma_hat",
            "beta",
            "eta",
            "gamma",
        }
        missing = sorted(required - set(data.columns))
        if missing:
            raise ValueError(f"missing estimator columns: {missing}")
        if "converged" in data.columns:
            data = data[data["converged"].astype(bool)].copy()
        data["j1_sq"] = (
            ((data["beta_hat"] - data["beta"]) / data["beta"]) ** 2
            + ((data["eta_hat"] - data["eta"]) / data["eta"]) ** 2
            + ((data["gamma_hat"] - data["gamma"]) / data["eta"]) ** 2
        )
    data = data[np.isfinite(data["j1_sq"])].copy()
    return data


def validate_scan_contract(scan: pd.DataFrame) -> None:
    """Require one complete candidate-delta curve for every repeat sample."""
    required = set(SAMPLE_COLS + ["delta", "j1_sq"])
    missing = sorted(required - set(scan.columns))
    if missing:
        raise ValueError(f"missing cross-fit columns: {missing}")

    key = SAMPLE_COLS + ["delta"]
    if scan.duplicated(key).any():
        raise ValueError("duplicate sample-delta rows violate cross-fit contract")

    expected_deltas = int(scan["delta"].nunique())
    counts = scan.groupby(SAMPLE_COLS, dropna=False)["delta"].nunique()
    if counts.empty or not counts.eq(expected_deltas).all():
        raise ValueError("cross-fit requires a complete repeat-by-delta grid")


def _group_id(row: pd.Series, group_cols: list[str]) -> str:
    if not group_cols:
        return "all"
    return "|".join(f"{col}={row[col]}" for col in group_cols)


def _choose_deltas(train: pd.DataFrame, layer: str, group_cols: list[str], fold: int) -> pd.DataFrame:
    aggregate_cols = group_cols + ["delta"]
    risk = (
        train.groupby(aggregate_cols, dropna=False, as_index=False)["j1_sq"]
        .mean()
        .rename(columns={"j1_sq": "mean_train_loss"})
    )
    sort_cols = group_cols + ["mean_train_loss", "delta"]
    risk = risk.sort_values(sort_cols, kind="mergesort")
    if group_cols:
        chosen = risk.groupby(group_cols, dropna=False, as_index=False).first()
    else:
        chosen = risk.iloc[[0]].copy()
    chosen = chosen.rename(columns={"delta": "delta_star"})
    chosen.insert(0, "fold", int(fold))
    chosen.insert(1, "layer", layer)
    chosen["group_id"] = chosen.apply(lambda row: _group_id(row, group_cols), axis=1)
    chosen["n_train_repeats"] = int(train["repeat_id"].nunique())
    return chosen


def _apply_deltas(test: pd.DataFrame, chosen: pd.DataFrame, layer: str, group_cols: list[str]) -> pd.DataFrame:
    if group_cols:
        mapping = chosen[group_cols + ["delta_star"]]
        candidates = test.merge(mapping, on=group_cols, how="left", validate="many_to_one")
    else:
        candidates = test.copy()
        candidates["delta_star"] = float(chosen.iloc[0]["delta_star"])

    selected = candidates[np.isclose(candidates["delta"], candidates["delta_star"])].copy()
    expected = int(test[SAMPLE_COLS].drop_duplicates().shape[0])
    if len(selected) != expected:
        raise ValueError(
            f"{layer} selected {len(selected)} rows for {expected} holdout samples"
        )
    selected["layer"] = layer
    return selected


def _metric_row(selected: pd.DataFrame, fold: int, layer: str) -> dict:
    return {
        "fold": int(fold),
        "layer": layer,
        "J1": math.sqrt(float(selected["j1_sq"].mean())),
        "n_holdout_samples": int(len(selected)),
        "n_holdout_repeats": int(selected["repeat_id"].nunique()),
    }


def compute_same_sample_metrics(
    scan: pd.DataFrame,
    default_delta: float = 0.1,
) -> pd.DataFrame:
    """Recompute the descriptive choose-and-score-on-all-repeats estimates."""
    data = prepare_scan(scan)
    validate_scan_contract(data)
    rows = []

    default = data[np.isclose(data["delta"], default_delta)]
    rows.append(
        {
            "layer": "Default",
            "same_sample_J1": math.sqrt(float(default["j1_sq"].mean())),
        }
    )
    for layer, group_cols in LAYER_GROUPS.items():
        chosen = _choose_deltas(data, layer, group_cols, fold=-1)
        selected = _apply_deltas(data, chosen, layer, group_cols)
        rows.append(
            {
                "layer": layer,
                "same_sample_J1": math.sqrt(float(selected["j1_sq"].mean())),
            }
        )
    return pd.DataFrame(rows)


def run_crossfit(
    scan: pd.DataFrame,
    n_folds: int = 5,
    default_delta: float = 0.1,
) -> dict[str, pd.DataFrame]:
    """Select L1-L5 deltas on four folds and score them on the fifth."""
    if n_folds < 2:
        raise ValueError("n_folds must be at least 2")
    data = prepare_scan(scan)
    validate_scan_contract(data)
    data["fold"] = data["repeat_id"].astype(int) % int(n_folds)

    fold_metrics = []
    selections = []
    selected_parts = []

    for fold in range(n_folds):
        train = data[data["fold"] != fold].copy()
        test = data[data["fold"] == fold].copy()
        if train.empty or test.empty:
            raise ValueError(f"fold {fold} has an empty train or holdout partition")

        default = test[np.isclose(test["delta"], default_delta)].copy()
        expected = int(test[SAMPLE_COLS].drop_duplicates().shape[0])
        if len(default) != expected:
            raise ValueError(f"Default delta={default_delta} is absent or incomplete")
        default["layer"] = "Default"
        default["delta_star"] = float(default_delta)
        selected_parts.append(default)
        fold_metrics.append(_metric_row(default, fold, "Default"))

        for layer, group_cols in LAYER_GROUPS.items():
            chosen = _choose_deltas(train, layer, group_cols, fold)
            selected = _apply_deltas(test, chosen, layer, group_cols)
            selections.append(chosen)
            selected_parts.append(selected)
            fold_metrics.append(_metric_row(selected, fold, layer))

    fold_metrics_df = pd.DataFrame(fold_metrics)
    selected_deltas_df = pd.concat(selections, ignore_index=True, sort=False)
    selected_rows = pd.concat(selected_parts, ignore_index=True, sort=False)

    pooled_rows = []
    by_n_rows = []
    for layer, group in selected_rows.groupby("layer", sort=False):
        row = {
            "layer": layer,
            "J1": math.sqrt(float(group["j1_sq"].mean())),
            "n_selected_samples": int(len(group)),
        }
        for n_value, n_group in group.groupby("n"):
            j1_n = math.sqrt(float(n_group["j1_sq"].mean()))
            row[f"J1_n{int(n_value)}"] = j1_n
            by_n_rows.append(
                {
                    "layer": layer,
                    "n": int(n_value),
                    "J1": j1_n,
                    "n_selected_samples": int(len(n_group)),
                }
            )
        pooled_rows.append(row)

    layer_order = {name: idx for idx, name in enumerate(["Default", *LAYER_GROUPS])}
    pooled_metrics = pd.DataFrame(pooled_rows)
    pooled_metrics["_order"] = pooled_metrics["layer"].map(layer_order)
    pooled_metrics = pooled_metrics.sort_values("_order").drop(columns="_order").reset_index(drop=True)
    by_n_metrics = pd.DataFrame(by_n_rows).sort_values(["layer", "n"]).reset_index(drop=True)

    stability = (
        selected_deltas_df.groupby(["layer", "group_id"], as_index=False)
        .agg(
            n_folds=("fold", "nunique"),
            n_unique_delta=("delta_star", "nunique"),
            min_delta=("delta_star", "min"),
            max_delta=("delta_star", "max"),
        )
    )
    modes = (
        selected_deltas_df.groupby(["layer", "group_id"])["delta_star"]
        .agg(lambda values: float(values.value_counts().sort_index().idxmax()))
        .rename("mode_delta")
        .reset_index()
    )
    mode_rates = (
        selected_deltas_df.merge(modes, on=["layer", "group_id"])
        .assign(is_mode=lambda frame: np.isclose(frame["delta_star"], frame["mode_delta"]))
        .groupby(["layer", "group_id"], as_index=False)["is_mode"]
        .mean()
        .rename(columns={"is_mode": "mode_fraction"})
    )
    stability = stability.merge(modes, on=["layer", "group_id"]).merge(
        mode_rates, on=["layer", "group_id"]
    )

    same_sample_metrics = compute_same_sample_metrics(data, default_delta=default_delta)
    comparison = pooled_metrics[["layer", "J1"]].rename(
        columns={"J1": "crossfit_J1"}
    ).merge(same_sample_metrics, on="layer", validate="one_to_one")
    comparison["crossfit_minus_same_sample"] = (
        comparison["crossfit_J1"] - comparison["same_sample_J1"]
    )
    comparison["relative_change_pct"] = (
        comparison["crossfit_minus_same_sample"]
        / comparison["same_sample_J1"]
        * 100.0
    )

    return {
        "fold_metrics": fold_metrics_df,
        "selected_deltas": selected_deltas_df,
        "selected_rows": selected_rows,
        "pooled_metrics": pooled_metrics,
        "by_n_metrics": by_n_metrics,
        "selection_stability": stability,
        "same_sample_metrics": same_sample_metrics,
        "comparison": comparison,
    }


def _write_report(result: dict[str, pd.DataFrame], output_dir: Path) -> None:
    pooled = result["pooled_metrics"]
    fold_metrics = result["fold_metrics"]
    comparison = result["comparison"]
    stability = result["selection_stability"]
    lines = [
        "# E1/E2 L1-L5 Cross-Fit Sensitivity Validation",
        "",
        "Selection uses four repeat-id folds; every reported loss is scored on the untouched fifth fold.",
        "L6 is excluded because it is an intentionally in-sample per-sample hindsight benchmark.",
        "",
        "## Pooled held-out J1",
        "",
        "| layer | J1 |",
        "|---|---:|",
    ]
    for row in pooled.itertuples(index=False):
        lines.append(f"| {row.layer} | {row.J1:.6f} |")
    lines.extend(
        [
            "",
            "## Comparison with same-sample selection/evaluation",
            "",
            "| layer | same-sample J1 | cross-fit J1 | difference | relative change |",
            "|---|---:|---:|---:|---:|",
        ]
    )
    for row in comparison.itertuples(index=False):
        lines.append(
            f"| {row.layer} | {row.same_sample_J1:.6f} | {row.crossfit_J1:.6f} | "
            f"{row.crossfit_minus_same_sample:+.6f} | {row.relative_change_pct:+.3f}% |"
        )
    lines.extend(
        [
            "",
            "## Selection stability",
            "",
            "| layer | groups | groups stable in all folds | maximum unique deltas |",
            "|---|---:|---:|---:|",
        ]
    )
    for layer, group in stability.groupby("layer", sort=False):
        lines.append(
            f"| {layer} | {len(group)} | {(group['n_unique_delta'] == 1).sum()} | "
            f"{int(group['n_unique_delta'].max())} |"
        )
    lines.extend(["", "## Fold-level J1", "", "| fold | layer | J1 |", "|---:|---|---:|"])
    for row in fold_metrics.itertuples(index=False):
        lines.append(f"| {row.fold} | {row.layer} | {row.J1:.6f} |")
    lines.extend(
        [
            "",
            "## Interpretation boundary",
            "",
            "This package audits selection optimism using the existing MC cache. It does not rerun MDM, replace the sealed E1/E2 artifacts, or convert L6 into an out-of-sample deployment estimate.",
        ]
    )
    (output_dir / "crossfit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(INPUT_PATH)
    raw = pd.read_csv(INPUT_PATH)
    result = run_crossfit(raw, n_folds=5, default_delta=0.1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    result["fold_metrics"].to_csv(OUTPUT_DIR / "results.csv", index=False)
    result["fold_metrics"].to_csv(OUTPUT_DIR / "fold_metrics.csv", index=False)
    result["pooled_metrics"].to_csv(OUTPUT_DIR / "model_comparison.csv", index=False)
    result["by_n_metrics"].to_csv(OUTPUT_DIR / "by_n_metrics.csv", index=False)
    result["selected_deltas"].to_csv(OUTPUT_DIR / "selected_deltas.csv", index=False)
    result["selection_stability"].to_csv(OUTPUT_DIR / "selection_stability.csv", index=False)
    result["comparison"].to_csv(OUTPUT_DIR / "comparison_vs_same_sample.csv", index=False)

    summary = {
        "status": "complete",
        "scope": "L1-L5 repeat-level 5-fold cross-fit sensitivity; L6 excluded as hindsight",
        "fold_rule": "fold = repeat_id mod 5",
        "default_delta": 0.1,
        "results": result["pooled_metrics"].to_dict(orient="records"),
        "comparison_vs_same_sample": result["comparison"].to_dict(orient="records"),
    }
    (OUTPUT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    manifest = {
        "experiment": "E1_E2_crossfit",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "input": str(INPUT_PATH.relative_to(STUDY_ROOT)),
        "input_sha256": _sha256(INPUT_PATH),
        "script": str(Path(__file__).relative_to(STUDY_ROOT)),
        "script_sha256": _sha256(Path(__file__)),
        "n_folds": 5,
        "fold_rule": "repeat_id mod 5",
        "selection_layers": list(LAYER_GROUPS),
        "excluded_layer": "L6 (per-sample hindsight benchmark)",
        "outputs": [
            "manifest.json",
            "summary.json",
            "results.csv",
            "fold_metrics.csv",
            "model_comparison.csv",
            "by_n_metrics.csv",
            "selected_deltas.csv",
            "selection_stability.csv",
            "comparison_vs_same_sample.csv",
            "crossfit_report.md",
        ],
        **_git_info(),
    }
    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    _write_report(result, OUTPUT_DIR)
    print(f"Saved cross-fit validation to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
