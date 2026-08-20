"""Derive the paper's fixed-seed primary summaries from sealed E8 outputs.

This script does not train a model or rerun MDM.  It selects seed 42 from the
existing E8 fold-out results, while retaining seeds 2026 and 3407 only as an
initialization-sensitivity receipt.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from paper_support import sha256_file_lf, write_sha256sums


STUDY_ROOT = Path(__file__).resolve().parents[1]
E8_ROOT = STUDY_ROOT / "artifacts" / "formal" / "E8_mean_normalized_selector"
DEFAULT_OUTPUT = E8_ROOT / "seed42_primary"
PRIMARY_SEED = 42
SENSITIVITY_SEEDS = [2026, 3407]
N_VALUES = [7, 10, 15, 20]


def pooled_from_equal_blocks(values: pd.Series) -> float:
    """Combine equal-size block J1 values using the frozen J1 definition."""
    array = values.to_numpy(dtype=float)
    return float(np.sqrt(np.mean(array ** 2)))


def derive(output_dir: Path = DEFAULT_OUTPUT) -> dict:
    specialist_path = E8_ROOT / "specialist" / "model_comparison.csv"
    stability_path = E8_ROOT / "specialist" / "seed_stability.csv"
    unseen_path = E8_ROOT / "unseen_beta" / "beta_holdout.csv"
    quantile_path = E8_ROOT / "quantiles" / "summary.csv"

    comparison = pd.read_csv(specialist_path)
    stability = pd.read_csv(stability_path)
    unseen = pd.read_csv(unseen_path)
    quantiles = pd.read_csv(quantile_path)

    main = comparison[comparison["seed"] == PRIMARY_SEED].copy()
    if set(main["model"]) != {"Mean-Normalized-MLP", "Default", "L6-hindsight"}:
        raise AssertionError("E8 primary-seed model set is incomplete")
    if len(main) != 3:
        raise AssertionError("E8 primary-seed comparison must contain exactly three rows")

    unseen_primary = unseen[unseen["seed"] == PRIMARY_SEED].copy()
    if len(unseen_primary) != 8 * 3:
        raise AssertionError("E8 unseen-beta primary-seed rows are incomplete")

    quantile_primary = quantiles[(quantiles["method"] != "Mean-Normalized") |
                                 (quantiles["seed"] == PRIMARY_SEED)].copy()
    if len(quantile_primary) != 15:
        raise AssertionError("E8 primary-seed quantile rows are incomplete")

    output_dir.mkdir(parents=True, exist_ok=True)
    main.to_csv(output_dir / "main_results.csv", index=False, lineterminator="\n")
    unseen_primary.to_csv(output_dir / "unseen_beta.csv", index=False,
                          lineterminator="\n")
    quantile_primary.to_csv(output_dir / "quantiles.csv", index=False,
                            lineterminator="\n")

    adaptive = main[main["model"] == "Mean-Normalized-MLP"].iloc[0]
    default = main[main["model"] == "Default"].iloc[0]
    unseen_models = {
        model: pooled_from_equal_blocks(group["J1"])
        for model, group in unseen_primary.groupby("model")
    }
    q_primary = quantile_primary[quantile_primary["method"] == "Mean-Normalized"]
    q_default = quantile_primary[quantile_primary["method"] == "Default"]

    summary = {
        "contract": "E8_paper_primary_seed42_v1",
        "primary_seed": PRIMARY_SEED,
        "sensitivity_seeds": SENSITIVITY_SEEDS,
        "reporting_rule": (
            "seed 42 defines paper primary estimates; seeds 2026 and 3407 "
            "are initialization-sensitivity evidence only; no prediction ensemble"
        ),
        "main": {
            "adaptive_J1": float(adaptive["J1"]),
            "default_J1": float(default["J1"]),
            "relative_improvement_vs_default": float(1 - adaptive["J1"] / default["J1"]),
            "failure_rate": float(adaptive["failure_rate"]),
            "by_n": {str(n): float(adaptive[f"J1_n{n}"]) for n in N_VALUES},
        },
        "initialization_sensitivity": {
            "seeds": stability["seed"].astype(int).tolist(),
            "pooled_J1": stability["pooled_J1"].astype(float).tolist(),
            "minimum": float(stability["pooled_J1"].min()),
            "maximum": float(stability["pooled_J1"].max()),
            "population_standard_deviation": float(stability["pooled_J1"].std(ddof=0)),
        },
        "unseen_beta": {
            "adaptive_J1": unseen_models["Mean-Normalized-MLP"],
            "default_J1": unseen_models["Default"],
            "relative_improvement_vs_default": float(
                1 - unseen_models["Mean-Normalized-MLP"] / unseen_models["Default"]
            ),
            "failure_rate": float(
                unseen_primary[unseen_primary["model"] == "Mean-Normalized-MLP"]
                ["failure_rate"].max()
            ),
        },
        "quantile_relative_rmse": {
            row.quantile: float(row.rmse) for row in q_primary.itertuples()
        },
        "default_quantile_relative_rmse": {
            row.quantile: float(row.rmse) for row in q_default.itertuples()
        },
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    manifest = {
        "contract": summary["contract"],
        "derivation_only": True,
        "primary_seed": PRIMARY_SEED,
        "source_files_sha256_lf": {
            str(path.relative_to(STUDY_ROOT)).replace("\\", "/"): sha256_file_lf(path)
            for path in (specialist_path, stability_path, unseen_path, quantile_path)
        },
        "derived_files_sha256_lf": {
            name: sha256_file_lf(output_dir / name)
            for name in ("main_results.csv", "unseen_beta.csv", "quantiles.csv", "summary.json")
        },
        "notes": [
            "No MDM run and no neural-network training were performed.",
            "The primary seed was fixed by author decision, not selected by performance ranking.",
        ],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    _, n_local = write_sha256sums(output_dir)
    if n_local == 0:
        (output_dir / "SHA256SUMS.local_not_in_git").unlink(missing_ok=True)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    summary = derive(args.output)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
