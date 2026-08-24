"""Quantify uncertainty in the fixed-seed E8 paper result.

This is a derivation-only analysis.  It reuses the sealed seed-42 out-of-fold
losses and the shared Default losses; it does not retrain a network or rerun
MDM.  Two distinct summaries are produced:

1. paired repeat-block bootstrap: Monte Carlo uncertainty conditional on the
   frozen 160-cell design and its equal weights;
2. paired design-cell bootstrap: sensitivity of the pooled result to the
   composition of the 160 design cells.  This is not presented as a confidence
   interval for a continuous parameter population.
"""

from __future__ import annotations

import hashlib
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd


CODE_DIR = Path(__file__).resolve().parent
STUDY_ROOT = CODE_DIR.parent
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import paper_support as PS


SOURCE_SELECTION = (
    STUDY_ROOT / "artifacts" / "formal" / "E5_normalized_raw" /
    "specialist" / "raw_specialist_results.csv"
)
SOURCE_SELECTION_SHA256 = (
    "b67578fe3a6e02c606ce0ba0bf224f4ce8a7acbf48de1fd87ef1739e368ad7db"
)
OUTPUT_DIR = (
    STUDY_ROOT / "artifacts" / "formal" /
    "E8_mean_normalized_selector" / "main_uncertainty"
)
PRIMARY_SEED = 42
N_BOOTSTRAP = 20_000
RNG_SEED = 20_260_824
EXPECTED_ADAPTIVE_J1 = 0.5845531935428129
EXPECTED_DEFAULT_J1 = 0.6304091999323665
SAMPLE_KEYS = list(PS.SAMPLE_KEYS)
CELL_KEYS = ["beta", "gamma_over_eta", "n"]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metric_values(adaptive_loss: np.ndarray, default_loss: np.ndarray) -> dict:
    adaptive_r = float(np.mean(adaptive_loss))
    default_r = float(np.mean(default_loss))
    adaptive_j1 = math.sqrt(adaptive_r)
    default_j1 = math.sqrt(default_r)
    return {
        "adaptive_R": adaptive_r,
        "default_R": default_r,
        "R_difference": adaptive_r - default_r,
        "adaptive_J1": adaptive_j1,
        "default_J1": default_j1,
        "delta_J1": adaptive_j1 - default_j1,
        "relative_improvement": 1.0 - adaptive_j1 / default_j1,
    }


def validate_paired_losses(frame: pd.DataFrame) -> None:
    required = set(SAMPLE_KEYS + ["adaptive_loss", "default_loss"])
    missing = sorted(required - set(frame.columns))
    if missing:
        raise RuntimeError(f"Missing paired-loss columns: {missing}")
    if frame[SAMPLE_KEYS].duplicated().any():
        raise RuntimeError("Paired sample keys are not unique")
    if not np.isfinite(frame[["adaptive_loss", "default_loss"]]).all().all():
        raise RuntimeError("Paired losses contain non-finite values")

    cell_sizes = frame.groupby(CELL_KEYS, observed=True).size()
    if len(cell_sizes) != 160 or not (cell_sizes == 300).all():
        raise RuntimeError(
            "Expected 160 equal design cells with 300 repeats each"
        )
    repeat_sizes = frame.groupby("repeat_id", observed=True).size()
    if list(repeat_sizes.index) != list(range(300)):
        raise RuntimeError("Expected complete repeat_id blocks 0..299")
    if not (repeat_sizes == 160).all():
        raise RuntimeError("Each repeat block must contain all 160 design cells")


def load_paired_losses() -> tuple[pd.DataFrame, dict]:
    if not SOURCE_SELECTION.is_file():
        raise FileNotFoundError(f"Missing sealed E5 selections: {SOURCE_SELECTION}")
    source_hash = sha256_file(SOURCE_SELECTION)
    if source_hash != SOURCE_SELECTION_SHA256:
        raise RuntimeError(
            f"E5 selection SHA256 mismatch: {source_hash}"
        )

    selections = pd.read_csv(SOURCE_SELECTION, low_memory=False)
    selections = selections.loc[
        selections["seed"].eq(PRIMARY_SEED),
        SAMPLE_KEYS + ["true_loss", "is_valid"],
    ].copy()
    if len(selections) != 48_000:
        raise RuntimeError(f"Expected 48,000 seed-42 selections, got {len(selections)}")
    if not selections["is_valid"].astype(bool).all():
        raise RuntimeError("Seed-42 primary selections contain failures")
    selections = selections.rename(columns={"true_loss": "adaptive_loss"})

    scan = PS.E6.load_mc_scan()
    full = PS.E6.compute_per_sample_loss(scan)
    PS.verify_design(full)
    baselines = PS.default_and_l6(full)
    default = baselines[SAMPLE_KEYS + ["default_loss", "default_valid"]].copy()
    if not default["default_valid"].astype(bool).all():
        raise RuntimeError("Default comparison contains failures")

    paired = selections.merge(
        default.drop(columns="default_valid"),
        on=SAMPLE_KEYS,
        how="inner",
        validate="one_to_one",
    )
    validate_paired_losses(paired)
    observed = metric_values(
        paired["adaptive_loss"].to_numpy(),
        paired["default_loss"].to_numpy(),
    )
    if not math.isclose(observed["adaptive_J1"], EXPECTED_ADAPTIVE_J1,
                        rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("Seed-42 adaptive J1 no longer matches sealed evidence")
    if not math.isclose(observed["default_J1"], EXPECTED_DEFAULT_J1,
                        rel_tol=0.0, abs_tol=1e-12):
        raise RuntimeError("Default J1 no longer matches sealed evidence")
    paired_digest = hashlib.sha256(
        paired[SAMPLE_KEYS + ["adaptive_loss", "default_loss"]]
        .sort_values(SAMPLE_KEYS)
        .to_csv(index=False, lineterminator="\n")
        .encode("utf-8")
    ).hexdigest()
    return paired, {
        "selection_file": SOURCE_SELECTION.relative_to(STUDY_ROOT).as_posix(),
        "selection_sha256_raw_bytes": source_hash,
        "paired_key_and_loss_sha256": paired_digest,
        "primary_seed": PRIMARY_SEED,
        "n_samples": int(len(paired)),
    }


def bootstrap_from_units(
    adaptive_loss: np.ndarray,
    default_loss: np.ndarray,
    *,
    n_bootstrap: int,
    rng_seed: int,
) -> dict:
    adaptive_loss = np.asarray(adaptive_loss, dtype=np.float64)
    default_loss = np.asarray(default_loss, dtype=np.float64)
    if adaptive_loss.ndim != 1 or default_loss.ndim != 1:
        raise ValueError("Bootstrap inputs must be one-dimensional")
    if len(adaptive_loss) != len(default_loss) or len(adaptive_loss) < 2:
        raise ValueError("Bootstrap inputs must be paired and non-trivial")
    if not np.isfinite(adaptive_loss).all() or not np.isfinite(default_loss).all():
        raise ValueError("Bootstrap inputs must be finite")

    observed = metric_values(adaptive_loss, default_loss)
    rng = np.random.default_rng(rng_seed)
    draws = {
        name: np.empty(n_bootstrap, dtype=np.float64)
        for name in ("adaptive_J1", "default_J1", "delta_J1",
                     "relative_improvement", "R_difference")
    }
    batch_size = 1_000
    n_units = len(adaptive_loss)
    for start in range(0, n_bootstrap, batch_size):
        count = min(batch_size, n_bootstrap - start)
        indices = rng.integers(0, n_units, size=(count, n_units))
        adaptive_r = adaptive_loss[indices].mean(axis=1)
        default_r = default_loss[indices].mean(axis=1)
        adaptive_j1 = np.sqrt(adaptive_r)
        default_j1 = np.sqrt(default_r)
        draws["adaptive_J1"][start:start + count] = adaptive_j1
        draws["default_J1"][start:start + count] = default_j1
        draws["delta_J1"][start:start + count] = adaptive_j1 - default_j1
        draws["relative_improvement"][start:start + count] = (
            1.0 - adaptive_j1 / default_j1
        )
        draws["R_difference"][start:start + count] = adaptive_r - default_r

    result = {**observed, "n_resampling_units": int(n_units),
              "n_bootstrap": int(n_bootstrap), "rng_seed": int(rng_seed)}
    for name, values in draws.items():
        result[f"{name}_ci95_low"] = float(np.quantile(values, 0.025))
        result[f"{name}_bootstrap_median"] = float(np.median(values))
        result[f"{name}_ci95_high"] = float(np.quantile(values, 0.975))
    return result


def repeat_block_summary(
    frame: pd.DataFrame, *, scope: str, rng_seed: int
) -> dict:
    blocks = frame.groupby("repeat_id", sort=True, observed=True)[
        ["adaptive_loss", "default_loss"]
    ].mean()
    result = bootstrap_from_units(
        blocks["adaptive_loss"].to_numpy(),
        blocks["default_loss"].to_numpy(),
        n_bootstrap=N_BOOTSTRAP,
        rng_seed=rng_seed,
    )
    return {
        "analysis": "conditional_monte_carlo_uncertainty",
        "scope": scope,
        "resampling_unit": "paired_repeat_block",
        "interpretation": (
            "95% percentile interval conditional on the frozen design and "
            "equal design-cell weights"
        ),
        **result,
    }


def cell_effects(frame: pd.DataFrame) -> pd.DataFrame:
    cells = frame.groupby(CELL_KEYS, sort=True, observed=True)[
        ["adaptive_loss", "default_loss"]
    ].mean().reset_index()
    cells = cells.rename(columns={
        "adaptive_loss": "adaptive_R",
        "default_loss": "default_R",
    })
    cells["adaptive_J1"] = np.sqrt(cells["adaptive_R"])
    cells["default_J1"] = np.sqrt(cells["default_R"])
    cells["delta_J1"] = cells["adaptive_J1"] - cells["default_J1"]
    cells["relative_improvement"] = (
        1.0 - cells["adaptive_J1"] / cells["default_J1"]
    )
    return cells


def run(output_dir: Path = OUTPUT_DIR) -> dict:
    paired, source = load_paired_losses()

    interval_rows = [repeat_block_summary(
        paired, scope="pooled", rng_seed=RNG_SEED
    )]
    for n_value, group in paired.groupby("n", sort=True, observed=True):
        interval_rows.append(repeat_block_summary(
            group,
            scope=f"n={int(n_value)}",
            rng_seed=RNG_SEED + int(n_value),
        ))

    cells = cell_effects(paired)
    cell_bootstrap = bootstrap_from_units(
        cells["adaptive_R"].to_numpy(),
        cells["default_R"].to_numpy(),
        n_bootstrap=N_BOOTSTRAP,
        rng_seed=RNG_SEED + 100,
    )
    interval_rows.append({
        "analysis": "design_composition_sensitivity",
        "scope": "pooled",
        "resampling_unit": "paired_design_cell",
        "interpretation": (
            "95% resampling range for sensitivity to the composition of the "
            "160 frozen cells; not a confidence interval for a continuous "
            "parameter population"
        ),
        **cell_bootstrap,
    })
    intervals = pd.DataFrame(interval_rows)

    tolerance = 1e-12
    improved = int((cells["delta_J1"] < -tolerance).sum())
    worse = int((cells["delta_J1"] > tolerance).sum())
    ties = int(len(cells) - improved - worse)
    pooled = interval_rows[0]
    design = interval_rows[-1]
    summary = {
        "contract": "E8_seed42_main_uncertainty_v1",
        "source": source,
        "primary_result": {
            key: pooled[key]
            for key in (
                "adaptive_R", "default_R", "adaptive_J1", "default_J1",
                "delta_J1", "relative_improvement"
            )
        },
        "conditional_monte_carlo_uncertainty": {
            "method": "paired percentile bootstrap of 300 balanced repeat blocks",
            "bootstrap_replicates": N_BOOTSTRAP,
            "rng_seed": RNG_SEED,
            "relative_improvement_ci95": [
                pooled["relative_improvement_ci95_low"],
                pooled["relative_improvement_ci95_high"],
            ],
            "delta_J1_ci95": [
                pooled["delta_J1_ci95_low"],
                pooled["delta_J1_ci95_high"],
            ],
            "boundary": (
                "conditional on the frozen 160-cell design and the fixed trained "
                "seed-42 selector; does not include representation/model-selection "
                "uncertainty or quantify continuous-parameter or real-data "
                "generalization"
            ),
        },
        "design_composition_sensitivity": {
            "method": "paired percentile bootstrap of 160 design-cell means",
            "bootstrap_replicates": N_BOOTSTRAP,
            "rng_seed": RNG_SEED + 100,
            "relative_improvement_resampling_range95": [
                design["relative_improvement_ci95_low"],
                design["relative_improvement_ci95_high"],
            ],
            "boundary": (
                "describes sensitivity to design-cell composition; is not a "
                "population confidence interval"
            ),
        },
        "cell_heterogeneity": {
            "n_cells": int(len(cells)),
            "n_improved": improved,
            "n_worse": worse,
            "n_tied": ties,
            "relative_improvement_quantiles": {
                str(q): float(cells["relative_improvement"].quantile(q))
                for q in (0.0, 0.25, 0.5, 0.75, 1.0)
            },
            "interpretation": (
                "the pooled benefit is not a per-cell guarantee; cell effects "
                "describe heterogeneity over the frozen grid"
            ),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    intervals.to_csv(
        output_dir / "bootstrap_intervals.csv", index=False, lineterminator="\n"
    )
    cells.to_csv(
        output_dir / "cell_effects.csv", index=False, lineterminator="\n"
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    output_names = ["bootstrap_intervals.csv", "cell_effects.csv", "summary.json"]
    manifest = {
        "contract": summary["contract"],
        "derivation_only": True,
        "mdm_rerun": False,
        "network_retrained": False,
        "hash_policy": "SHA256 of LF-normalized bytes",
        "analysis_code": Path(__file__).relative_to(STUDY_ROOT).as_posix(),
        "analysis_code_sha256_lf": PS.sha256_file_lf(Path(__file__)),
        "source": source,
        "files": {
            name: PS.sha256_file_lf(output_dir / name)
            for name in output_names
        },
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    ledger_names = sorted([*output_names, "manifest.json"])
    (output_dir / "SHA256SUMS").write_text(
        "".join(
            f"{PS.sha256_file_lf(output_dir / name)}  {name}\n"
            for name in ledger_names
        ),
        encoding="ascii",
        newline="\n",
    )
    return summary


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=2))
