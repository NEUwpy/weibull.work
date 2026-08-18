"""Paired cell-bootstrap uncertainty for the E9 selector comparison."""

from __future__ import annotations

import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6
import run_E7_scale_invariant_input_screen as E7
import run_E9_target_confirmation_unseen_beta as CONFIRM
import run_E9_target_representation_screen as SCREEN
import run_b1_unseen_beta as B1


STUDY_ROOT = Path(__file__).resolve().parent.parent
OUTPUT = (
    STUDY_ROOT / "artifacts" / "candidate" /
    "E9_selector_mechanism_diagnostic" / "paired_cluster_bootstrap.csv"
)
CLUSTERS = ["beta", "gamma_over_eta", "n"]
REPLICATES = 20_000
RNG_SEED = 20_260_819


def reconstruct_main(
    full: pd.DataFrame, input_map: dict
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    actual = full.pivot(
        index=SCREEN.KEYS, columns="delta", values="loss"
    ).reindex(columns=SCREEN.DELTA_GRID)
    absolute = SCREEN.load_absolute_predictions(actual)
    folds = E6.get_combo_split()
    preparations = [E6.prepare_fold(full, fold) for fold in folds]
    oracle_parts = []
    for n in CFG.N_GRID:
        for fold_index in range(CFG.N_FOLDS):
            keys, _, true, _ = E6.pivot_raw_vector(
                preparations[fold_index]["df_test"], input_map, n
            )
            for seed in CFG.STABILITY_SEEDS:
                prediction = np.load(
                    SCREEN.runtime_paths(
                        "oracle_regret", n, fold_index, seed
                    )[0]
                )["prediction"]
                oracle_parts.append(
                    SCREEN.prediction_frame(
                        keys, prediction, true, "oracle_regret", seed,
                        fold_index
                    )
                )
    oracle = pd.concat(oracle_parts, ignore_index=True)
    _, absolute_single = SCREEN.summarise_target(
        absolute, "model_first_rows"
    )
    _, absolute_ensemble = SCREEN.summarise_target(
        absolute, "three_seed_curve_ensemble"
    )
    _, oracle_ensemble = SCREEN.summarise_target(
        oracle, "three_seed_curve_ensemble"
    )
    return absolute_single, absolute_ensemble, oracle_ensemble


def reconstruct_alternate_split(
    full: pd.DataFrame, input_map: dict
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    folds = B1.get_beta_folds()
    preparations = {
        fold["fold_name"]: E6.prepare_fold(full, fold) for fold in folds
    }
    parts = {"absolute": [], "oracle_regret": []}
    for fold in folds:
        beta = float(fold["held_out_beta"])
        preparation = preparations[fold["fold_name"]]
        for n in CFG.N_GRID:
            keys, _, true, _ = E6.pivot_raw_vector(
                preparation["df_test"], input_map, n
            )
            for target in parts:
                for seed in CFG.STABILITY_SEEDS:
                    prediction = np.load(
                        CONFIRM.paths(target, beta, n, seed)[0]
                    )["prediction"]
                    parts[target].append(
                        CONFIRM.block_frame(
                            keys, prediction, true, target, beta, n, seed
                        )
                    )
    frames = {
        target: pd.concat(target_parts, ignore_index=True)
        for target, target_parts in parts.items()
    }
    _, absolute_single = CONFIRM.evaluate(frames["absolute"], False)
    _, absolute_ensemble = CONFIRM.evaluate(frames["absolute"], True)
    _, oracle_ensemble = CONFIRM.evaluate(frames["oracle_regret"], True)
    return absolute_single, absolute_ensemble, oracle_ensemble


def mean_single_seed_by_sample(frame: pd.DataFrame) -> pd.DataFrame:
    return frame.groupby(
        SCREEN.KEYS, as_index=False, observed=True
    )["selected_loss"].mean()


def paired_bootstrap(
    method_a: pd.DataFrame,
    method_b: pd.DataFrame,
    comparison: str,
) -> dict:
    paired = method_a[SCREEN.KEYS + ["selected_loss"]].rename(
        columns={"selected_loss": "loss_a"}
    ).merge(
        method_b[SCREEN.KEYS + ["selected_loss"]].rename(
            columns={"selected_loss": "loss_b"}
        ),
        on=SCREEN.KEYS,
        validate="one_to_one",
    )
    cells = paired.groupby(CLUSTERS, observed=True)[
        ["loss_a", "loss_b"]
    ].mean()
    if len(cells) != 160:
        raise RuntimeError(f"Expected 160 design cells, got {len(cells)}")
    loss_a = cells["loss_a"].to_numpy()
    loss_b = cells["loss_b"].to_numpy()
    observed = math.sqrt(float(loss_b.mean())) - math.sqrt(float(loss_a.mean()))
    rng = np.random.default_rng(RNG_SEED)
    bootstrap = np.empty(REPLICATES, dtype=np.float64)
    for start in range(0, REPLICATES, 1000):
        count = min(1000, REPLICATES - start)
        indices = rng.integers(0, len(cells), size=(count, len(cells)))
        bootstrap[start:start + count] = (
            np.sqrt(loss_b[indices].mean(axis=1))
            - np.sqrt(loss_a[indices].mean(axis=1))
        )
    return {
        "comparison": comparison,
        "delta_J1_method_b_minus_a": observed,
        "ci95_low": float(np.quantile(bootstrap, 0.025)),
        "ci95_high": float(np.quantile(bootstrap, 0.975)),
        "n_equal_sized_design_cells": int(len(cells)),
        "bootstrap_replicates": REPLICATES,
        "rng_seed": RNG_SEED,
    }


def run() -> pd.DataFrame:
    scan = E6.load_mc_scan()
    full = E6.compute_per_sample_loss(scan)
    raw_map, _ = E6.build_raw_sample_map(scan)
    input_map = E7.build_representation_map(raw_map, "mean")
    main = reconstruct_main(full, input_map)
    alternate = reconstruct_alternate_split(full, input_map)
    rows = [
        paired_bootstrap(
            mean_single_seed_by_sample(main[0]), main[1],
            "main: absolute ensemble minus mean single-seed"
        ),
        paired_bootstrap(
            main[1], main[2],
            "main: oracle-regret ensemble minus absolute ensemble"
        ),
        paired_bootstrap(
            mean_single_seed_by_sample(alternate[0]), alternate[1],
            "alternate split: absolute ensemble minus mean single-seed"
        ),
        paired_bootstrap(
            alternate[1], alternate[2],
            "alternate split: oracle-regret ensemble minus absolute ensemble"
        ),
    ]
    result = pd.DataFrame(rows)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(OUTPUT, index=False)
    print(json.dumps(rows, ensure_ascii=False, indent=2))
    return result


if __name__ == "__main__":
    run()
