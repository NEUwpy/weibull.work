"""Screen decision-equivalent targets for the E8 26-point selector.

The current E8 model predicts the absolute per-sample loss curve.  This
candidate-only experiment keeps the input, folds, architecture, seeds, true
loss, and final argmin decision unchanged, while comparing three target
representations:

* absolute: L(delta), reused from the saved E5/E8 OOF predictions;
* default_residual: L(delta) - L(0.10);
* oracle_regret: L(delta) - min_delta L(delta).

All three targets have exactly the same realised argmin.  The two centred
targets remove a sample-specific additive level that is irrelevant to the
decision.  No MDM fit is rerun and no formal artifact is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6
import run_E7_scale_invariant_input_screen as E7


HERE = Path(__file__).resolve().parent
STUDY_ROOT = HERE.parent
OUT_DIR = STUDY_ROOT / "artifacts" / "candidate" / "E9_target_representation_screen"
RUNTIME_DIR = OUT_DIR / "runtime"
PREDICTION_DIR = (
    STUDY_ROOT / "artifacts" / "formal" / "E5_normalized_raw" /
    "specialist" / "predictions"
)
TARGETS = ("default_residual", "oracle_regret")
KEYS = E6.SAMPLE_KEYS
DELTA_GRID = np.asarray(E6.DELTA_GRID, dtype=np.float64)
DEFAULT_INDEX = int(np.flatnonzero(np.isclose(DELTA_GRID, CFG.DEFAULT_DELTA))[0])
CONTRACT = "E9_target_representation_screen_v1"


def script_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def transform_target(y: np.ndarray, target: str) -> np.ndarray:
    if target == "absolute":
        return y.copy()
    if target == "default_residual":
        return y - y[:, [DEFAULT_INDEX]]
    if target == "oracle_regret":
        return y - np.min(y, axis=1, keepdims=True)
    raise ValueError(target)


def train_target(
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    seed: int,
) -> tuple[np.ndarray, int, float]:
    input_scaler = StandardScaler()
    x_train_scaled = input_scaler.fit_transform(x_train)
    x_test_scaled = input_scaler.transform(x_test)
    target_scaler = StandardScaler()
    y_train_scaled = target_scaler.fit_transform(y_train)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        model = MLPRegressor(
            hidden_layer_sizes=CFG.MLP_HIDDEN_LAYERS,
            activation="relu",
            solver="adam",
            alpha=CFG.MLP_ALPHA,
            learning_rate_init=CFG.MLP_LR,
            max_iter=CFG.MLP_MAX_ITER,
            early_stopping=True,
            validation_fraction=CFG.MLP_VALIDATION_FRACTION,
            n_iter_no_change=CFG.MLP_N_ITER_NO_CHANGE,
            random_state=seed,
            batch_size=CFG.MLP_BATCH_SIZE,
        )
        started = time.time()
        model.fit(x_train_scaled, y_train_scaled)
        elapsed = time.time() - started
    prediction = target_scaler.inverse_transform(model.predict(x_test_scaled))
    return prediction, int(model.n_iter_), float(elapsed)


def runtime_paths(target: str, n: int, fold: int, seed: int) -> tuple[Path, Path]:
    tag = f"{target}_n{n}_fold{fold + 1}_seed{seed}"
    return RUNTIME_DIR / f"{tag}.npz", RUNTIME_DIR / f"{tag}.json"


def load_or_run(
    target: str,
    n: int,
    fold: int,
    seed: int,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    force: bool,
) -> tuple[np.ndarray, dict]:
    npz_path, meta_path = runtime_paths(target, n, fold, seed)
    code_sha = script_sha256()
    if not force and npz_path.is_file() and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if (
            meta.get("contract") == CONTRACT
            and meta.get("script_sha256") == code_sha
            and meta.get("test_rows") == len(x_test)
        ):
            prediction = np.load(npz_path)["prediction"]
            if prediction.shape == y_test.shape and np.isfinite(prediction).all():
                print(f"[skip] {npz_path.stem}", flush=True)
                return prediction, meta

    transformed_train = transform_target(y_train, target)
    prediction, n_iter, elapsed = train_target(
        x_train, transformed_train, x_test, seed
    )
    if prediction.shape != y_test.shape or not np.isfinite(prediction).all():
        raise RuntimeError(f"Invalid prediction for {npz_path.stem}")
    meta = {
        "contract": CONTRACT,
        "script_sha256": code_sha,
        "target": target,
        "n": int(n),
        "fold": int(fold + 1),
        "seed": int(seed),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "n_iter": n_iter,
        "runtime_s": elapsed,
    }
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(npz_path, prediction=prediction)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[done] {npz_path.stem}: iter={n_iter} runtime={elapsed:.1f}s",
        flush=True,
    )
    return prediction, meta


def prediction_frame(
    keys: pd.DataFrame,
    prediction: np.ndarray,
    y_true: np.ndarray,
    target: str,
    seed: int,
    fold: int,
) -> pd.DataFrame:
    frame = keys.copy()
    frame["target"] = target
    frame["seed"] = int(seed)
    frame["fold"] = int(fold + 1)
    for index, delta in enumerate(DELTA_GRID):
        frame[f"pred_d{float(delta)}"] = prediction[:, index]
        frame[f"true_d{float(delta)}"] = y_true[:, index]
    return frame


def load_absolute_predictions(actual_pivot: pd.DataFrame) -> pd.DataFrame:
    frames = []
    pred_cols = [f"pred_d{float(d)}" for d in DELTA_GRID]
    for path in sorted(PREDICTION_DIR.glob("n*_fold*_seed*.csv")):
        frame = pd.read_csv(path, usecols=KEYS + pred_cols)
        pieces = path.stem.split("_")
        frame["target"] = "absolute"
        frame["fold"] = int(pieces[1].removeprefix("fold"))
        frame["seed"] = int(pieces[2].removeprefix("seed"))
        index = pd.MultiIndex.from_frame(frame[KEYS])
        actual = actual_pivot.reindex(index).to_numpy(dtype=np.float64)
        for j, delta in enumerate(DELTA_GRID):
            frame[f"true_d{float(delta)}"] = actual[:, j]
        frames.append(frame)
    if len(frames) != 60:
        raise RuntimeError(f"Expected 60 absolute prediction files, got {len(frames)}")
    return pd.concat(frames, ignore_index=True)


def summarise_target(frame: pd.DataFrame, aggregation: str) -> tuple[dict, pd.DataFrame]:
    pred_cols = [f"pred_d{float(d)}" for d in DELTA_GRID]
    true_cols = [f"true_d{float(d)}" for d in DELTA_GRID]
    if aggregation == "three_seed_curve_ensemble":
        predictions = frame.groupby(KEYS, sort=True, observed=True)[pred_cols].mean()
        truths = frame.groupby(KEYS, sort=True, observed=True)[true_cols].first()
        evaluation = predictions.reset_index()[KEYS].copy()
        prediction = predictions.to_numpy(dtype=np.float64)
        actual = truths.to_numpy(dtype=np.float64)
        evaluation["seed"] = -1
    elif aggregation == "model_first_rows":
        evaluation = frame[KEYS + ["seed"]].copy()
        prediction = frame[pred_cols].to_numpy(dtype=np.float64)
        actual = frame[true_cols].to_numpy(dtype=np.float64)
    else:
        raise ValueError(aggregation)

    selected_idx = np.argmin(prediction, axis=1)
    oracle_idx = np.argmin(actual, axis=1)
    row = np.arange(len(actual))
    selected_loss = actual[row, selected_idx]
    default_loss = actual[:, DEFAULT_INDEX]
    oracle_loss = actual[row, oracle_idx]
    actual_gain = default_loss - selected_loss
    predicted_gain = prediction[:, DEFAULT_INDEX] - prediction[row, selected_idx]
    evaluation["selected_loss"] = selected_loss
    evaluation["default_loss"] = default_loss
    evaluation["oracle_loss"] = oracle_loss
    evaluation["actual_gain"] = actual_gain
    evaluation["predicted_gain"] = predicted_gain
    evaluation["selected_delta"] = DELTA_GRID[selected_idx]
    evaluation["oracle_delta"] = DELTA_GRID[oracle_idx]

    default_j1 = math.sqrt(float(default_loss.mean()))
    adaptive_j1 = math.sqrt(float(selected_loss.mean()))
    summary = {
        "target": str(frame["target"].iloc[0]),
        "aggregation": aggregation,
        "n_rows": int(len(actual)),
        "J1": adaptive_j1,
        "default_J1": default_j1,
        "oracle_J1": math.sqrt(float(oracle_loss.mean())),
        "relative_improvement_vs_default": 1.0 - adaptive_j1 / default_j1,
        "improved_rate": float((actual_gain > 1e-12).mean()),
        "harmed_rate": float((actual_gain < -1e-12).mean()),
        "exact_oracle_rate": float((selected_idx == oracle_idx).mean()),
        "within_0.02_oracle_rate": float(
            (np.abs(DELTA_GRID[selected_idx] - DELTA_GRID[oracle_idx]) <= 0.0200001).mean()
        ),
        "spearman_predicted_vs_actual_gain": float(
            pd.Series(predicted_gain).corr(pd.Series(actual_gain), method="spearman")
        ),
    }
    return summary, evaluation


def run(force: bool = False) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    with open(CFG.MC_MANIFEST_PATH, encoding="utf-8") as handle:
        manifest = json.load(handle)
    scan = E6.load_mc_scan()
    E6.verify_data_integrity(scan, manifest)
    raw_map, _ = E6.build_raw_sample_map(scan)
    mean_map = E7.build_representation_map(raw_map, "mean")
    full = E6.compute_per_sample_loss(scan)
    folds = E6.get_combo_split()
    fold_prep = [E6.prepare_fold(full, fold) for fold in folds]

    actual_pivot = full.pivot(index=KEYS, columns="delta", values="loss")
    actual_pivot = actual_pivot.reindex(columns=DELTA_GRID)
    if actual_pivot.shape != (48_000, 26) or actual_pivot.isna().any().any():
        raise RuntimeError(f"Unexpected actual curves: {actual_pivot.shape}")

    all_frames = [load_absolute_predictions(actual_pivot)]
    model_meta = []
    for target in TARGETS:
        target_frames = []
        for n in CFG.N_GRID:
            for fold_idx in range(CFG.N_FOLDS):
                prep = fold_prep[fold_idx]
                keys_train, x_train, y_train, _ = E6.pivot_raw_vector(
                    prep["df_train"], mean_map, n
                )
                keys_test, x_test, y_test, _ = E6.pivot_raw_vector(
                    prep["df_test"], mean_map, n
                )
                if set(map(tuple, keys_train.to_numpy())) & set(map(tuple, keys_test.to_numpy())):
                    raise RuntimeError("Train/test key overlap")
                for seed in CFG.STABILITY_SEEDS:
                    prediction, meta = load_or_run(
                        target, n, fold_idx, seed, x_train, y_train, x_test,
                        y_test, force
                    )
                    model_meta.append(meta)
                    target_frames.append(
                        prediction_frame(
                            keys_test, prediction, y_test, target, seed, fold_idx
                        )
                    )
        target_frame = pd.concat(target_frames, ignore_index=True)
        if len(target_frame) != 144_000:
            raise RuntimeError(f"{target}: {len(target_frame)} rows")
        all_frames.append(target_frame)

    summaries = []
    by_seed = []
    by_n = []
    ensemble_rows = []
    for frame in all_frames:
        target = str(frame["target"].iloc[0])
        row_summary, _ = summarise_target(frame, "model_first_rows")
        ensemble_summary, ensemble = summarise_target(
            frame, "three_seed_curve_ensemble"
        )
        summaries.extend([row_summary, ensemble_summary])
        ensemble["target"] = target
        ensemble_rows.append(ensemble)
        for seed, part in frame.groupby("seed"):
            summary, _ = summarise_target(part, "model_first_rows")
            summary["seed"] = int(seed)
            by_seed.append(summary)
        for n, part in ensemble.groupby("n"):
            default_j1 = math.sqrt(float(part["default_loss"].mean()))
            adaptive_j1 = math.sqrt(float(part["selected_loss"].mean()))
            by_n.append({
                "target": target,
                "n": int(n),
                "J1": adaptive_j1,
                "default_J1": default_j1,
                "relative_improvement_vs_default": 1.0 - adaptive_j1 / default_j1,
                "improved_rate": float((part["actual_gain"] > 1e-12).mean()),
                "harmed_rate": float((part["actual_gain"] < -1e-12).mean()),
            })

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT_DIR / "target_summary.csv", index=False)
    pd.DataFrame(by_seed).to_csv(OUT_DIR / "by_seed.csv", index=False)
    pd.DataFrame(by_n).to_csv(OUT_DIR / "by_n_ensemble.csv", index=False)
    pd.DataFrame(model_meta).to_csv(OUT_DIR / "trained_model_metadata.csv", index=False)

    result = {
        "status": "CANDIDATE_SCREEN_ONLY",
        "contract": CONTRACT,
        "question": "Does removing decision-irrelevant sample-level target shift improve delta selection?",
        "invariant_contract": {
            "input": "ascending sorted X / mean(X), one MLP per n",
            "folds": "same E8 gamma/eta-level holdout within n",
            "seeds": list(CFG.STABILITY_SEEDS),
            "architecture": list(CFG.MLP_HIDDEN_LAYERS),
            "decision": "argmin over the same 26 delta points",
            "true_loss": "unchanged J1 component loss",
            "mdm_rerun": False,
        },
        "target_definitions": {
            "absolute": "L(delta)",
            "default_residual": "L(delta) - L(0.10)",
            "oracle_regret": "L(delta) - min_delta L(delta)",
        },
        "target_argmin_identity_checked": True,
        "results": summary_df.to_dict(orient="records"),
        "warning": "This is a candidate screen. A selected variant requires an untouched confirmation split before becoming manuscript evidence.",
    }
    (OUT_DIR / "summary.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(summary_df.to_string(index=False), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-rerun", action="store_true")
    args = parser.parse_args()
    run(force=args.force_rerun)
