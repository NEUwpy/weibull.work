"""Untouched leave-one-beta confirmation for the E9 target candidate.

The candidate screen selected oracle-centred regret with a three-seed curve
ensemble as the only alternative worth confirming.  This script compares it
against the incumbent absolute-loss curve on the existing eight unseen-beta
folds.  It reuses the frozen scan and runs no MDM fit.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

import dim_raw_config as CFG
import paper_support as PS
import run_E6b_dimensional_raw_specialist as E6
import run_E7_scale_invariant_input_screen as E7
import run_E9_target_representation_screen as E9
import run_b1_unseen_beta as B1


HERE = Path(__file__).resolve().parent
STUDY_ROOT = HERE.parent
OUT_DIR = STUDY_ROOT / "artifacts" / "candidate" / "E9_target_confirmation_unseen_beta"
RUNTIME_DIR = OUT_DIR / "runtime"
TARGETS = ("absolute", "oracle_regret")
KEYS = E6.SAMPLE_KEYS
DELTA_GRID = np.asarray(E6.DELTA_GRID, dtype=np.float64)
DEFAULT_INDEX = int(np.flatnonzero(np.isclose(DELTA_GRID, CFG.DEFAULT_DELTA))[0])
CONTRACT = "E9_target_confirmation_unseen_beta_v1"


def script_sha256() -> str:
    return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()


def paths(target: str, beta: float, n: int, seed: int) -> tuple[Path, Path]:
    tag = f"{target}_beta{beta}_n{n}_seed{seed}"
    return RUNTIME_DIR / f"{tag}.npz", RUNTIME_DIR / f"{tag}.json"


def load_or_train(
    target: str,
    beta: float,
    n: int,
    seed: int,
    x_train: np.ndarray,
    y_train: np.ndarray,
    x_test: np.ndarray,
    y_test: np.ndarray,
    force: bool,
) -> tuple[np.ndarray, dict]:
    npz_path, meta_path = paths(target, beta, n, seed)
    sha = script_sha256()
    if not force and npz_path.is_file() and meta_path.is_file():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if (
            meta.get("contract") == CONTRACT
            and meta.get("script_sha256") == sha
            and meta.get("test_rows") == len(x_test)
        ):
            prediction = np.load(npz_path)["prediction"]
            if prediction.shape == y_test.shape and np.isfinite(prediction).all():
                print(f"[skip] {npz_path.stem}", flush=True)
                return prediction, meta

    if target == "absolute":
        prediction, n_iter, *_ = E6.train_specialist(
            x_train, y_train, x_test, seed
        )
        prediction_contract = "incumbent absolute loss; nonnegative clipping"
    elif target == "oracle_regret":
        transformed = E9.transform_target(y_train, target)
        prediction, n_iter, _elapsed = E9.train_target(
            x_train, transformed, x_test, seed
        )
        prediction_contract = "oracle-centred decision score; no clipping"
    else:
        raise ValueError(target)
    meta = {
        "contract": CONTRACT,
        "script_sha256": sha,
        "target": target,
        "held_out_beta": float(beta),
        "n": int(n),
        "seed": int(seed),
        "train_rows": int(len(x_train)),
        "test_rows": int(len(x_test)),
        "n_iter": int(n_iter),
        "prediction_contract": prediction_contract,
    }
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(npz_path, prediction=prediction)
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"[done] {npz_path.stem}: iter={n_iter}", flush=True
    )
    return prediction, meta


def block_frame(
    keys: pd.DataFrame,
    prediction: np.ndarray,
    actual: np.ndarray,
    target: str,
    beta: float,
    n: int,
    seed: int,
) -> pd.DataFrame:
    frame = keys.copy()
    frame["target"] = target
    frame["held_out_beta"] = float(beta)
    frame["n_specialist"] = int(n)
    frame["seed"] = int(seed)
    for index, delta in enumerate(DELTA_GRID):
        frame[f"pred_d{float(delta)}"] = prediction[:, index]
        frame[f"true_d{float(delta)}"] = actual[:, index]
    return frame


def evaluate(frame: pd.DataFrame, ensemble: bool) -> tuple[dict, pd.DataFrame]:
    pred_cols = [f"pred_d{float(d)}" for d in DELTA_GRID]
    true_cols = [f"true_d{float(d)}" for d in DELTA_GRID]
    group_keys = KEYS
    if ensemble:
        pred = frame.groupby(group_keys, sort=True, observed=True)[pred_cols].mean()
        true = frame.groupby(group_keys, sort=True, observed=True)[true_cols].first()
        rows = pred.reset_index()[group_keys].copy()
        prediction = pred.to_numpy(dtype=np.float64)
        actual = true.to_numpy(dtype=np.float64)
        aggregation = "three_seed_curve_ensemble"
    else:
        rows = frame[group_keys + ["seed"]].copy()
        prediction = frame[pred_cols].to_numpy(dtype=np.float64)
        actual = frame[true_cols].to_numpy(dtype=np.float64)
        aggregation = "model_first_rows"
    selected = np.argmin(prediction, axis=1)
    oracle = np.argmin(actual, axis=1)
    index = np.arange(len(actual))
    selected_loss = actual[index, selected]
    default_loss = actual[:, DEFAULT_INDEX]
    oracle_loss = actual[index, oracle]
    gain = default_loss - selected_loss
    predicted_gain = prediction[:, DEFAULT_INDEX] - prediction[index, selected]
    rows["selected_loss"] = selected_loss
    rows["default_loss"] = default_loss
    rows["oracle_loss"] = oracle_loss
    rows["actual_gain"] = gain
    rows["predicted_gain"] = predicted_gain
    rows["selected_delta"] = DELTA_GRID[selected]
    rows["oracle_delta"] = DELTA_GRID[oracle]
    default_j1 = math.sqrt(float(default_loss.mean()))
    selected_j1 = math.sqrt(float(selected_loss.mean()))
    summary = {
        "target": str(frame["target"].iloc[0]),
        "aggregation": aggregation,
        "n_rows": int(len(rows)),
        "J1": selected_j1,
        "default_J1": default_j1,
        "oracle_J1": math.sqrt(float(oracle_loss.mean())),
        "relative_improvement_vs_default": 1.0 - selected_j1 / default_j1,
        "improved_rate": float((gain > 1e-12).mean()),
        "harmed_rate": float((gain < -1e-12).mean()),
        "exact_oracle_rate": float((selected == oracle).mean()),
        "within_0.02_oracle_rate": float(
            (np.abs(DELTA_GRID[selected] - DELTA_GRID[oracle]) <= 0.0200001).mean()
        ),
        "spearman_predicted_vs_actual_gain": float(
            pd.Series(predicted_gain).corr(pd.Series(gain), method="spearman")
        ),
    }
    return summary, rows


def run(force: bool = False) -> dict:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    scan, full, raw_map = PS.load_scan()
    PS.verify_design(full)
    input_map = E7.build_representation_map(raw_map, "mean")
    folds = B1.get_beta_folds()
    prepared = {
        fold["fold_name"]: E6.prepare_fold(full, fold) for fold in folds
    }

    target_frames: dict[str, list[pd.DataFrame]] = {target: [] for target in TARGETS}
    metadata = []
    for fold in folds:
        beta = float(fold["held_out_beta"])
        prep = prepared[fold["fold_name"]]
        for n in CFG.N_GRID:
            keys_train, x_train, y_train, _ = E6.pivot_raw_vector(
                prep["df_train"], input_map, n
            )
            keys_test, x_test, y_test, _ = E6.pivot_raw_vector(
                prep["df_test"], input_map, n
            )
            if len(keys_test) != 5 * CFG.REPEATS:
                raise RuntimeError("Unexpected unseen-beta test size")
            if set(map(tuple, keys_train.to_numpy())) & set(map(tuple, keys_test.to_numpy())):
                raise RuntimeError("Train/test overlap")
            for target in TARGETS:
                for seed in CFG.STABILITY_SEEDS:
                    prediction, meta = load_or_train(
                        target, beta, n, seed, x_train, y_train, x_test,
                        y_test, force
                    )
                    metadata.append(meta)
                    target_frames[target].append(
                        block_frame(
                            keys_test, prediction, y_test, target, beta, n, seed
                        )
                    )

    summaries = []
    by_beta = []
    by_n = []
    for target, parts in target_frames.items():
        frame = pd.concat(parts, ignore_index=True)
        if len(frame) != 144_000:
            raise RuntimeError(f"{target}: {len(frame)} rows")
        plain, _ = evaluate(frame, ensemble=False)
        ensemble, rows = evaluate(frame, ensemble=True)
        summaries.extend([plain, ensemble])
        for beta, group in rows.groupby("beta"):
            default_j1 = math.sqrt(float(group["default_loss"].mean()))
            selected_j1 = math.sqrt(float(group["selected_loss"].mean()))
            by_beta.append({
                "target": target,
                "held_out_beta": float(beta),
                "J1": selected_j1,
                "default_J1": default_j1,
                "relative_improvement_vs_default": 1.0 - selected_j1 / default_j1,
                "improved_rate": float((group["actual_gain"] > 1e-12).mean()),
                "harmed_rate": float((group["actual_gain"] < -1e-12).mean()),
            })
        for n, group in rows.groupby("n"):
            default_j1 = math.sqrt(float(group["default_loss"].mean()))
            selected_j1 = math.sqrt(float(group["selected_loss"].mean()))
            by_n.append({
                "target": target,
                "n": int(n),
                "J1": selected_j1,
                "default_J1": default_j1,
                "relative_improvement_vs_default": 1.0 - selected_j1 / default_j1,
                "improved_rate": float((group["actual_gain"] > 1e-12).mean()),
                "harmed_rate": float((group["actual_gain"] < -1e-12).mean()),
            })

    summary_df = pd.DataFrame(summaries)
    summary_df.to_csv(OUT_DIR / "target_summary.csv", index=False)
    pd.DataFrame(by_beta).to_csv(OUT_DIR / "by_beta_ensemble.csv", index=False)
    pd.DataFrame(by_n).to_csv(OUT_DIR / "by_n_ensemble.csv", index=False)
    pd.DataFrame(metadata).to_csv(OUT_DIR / "trained_model_metadata.csv", index=False)
    result = {
        "status": "CANDIDATE_CONFIRMATION",
        "contract": CONTRACT,
        "selection_rule": (
            "oracle_regret plus three-seed curve ensemble was selected for this "
            "confirmation before inspecting unseen-beta results"
        ),
        "split": "leave one complete beta level out; 8 folds",
        "mdm_rerun": False,
        "results": summary_df.to_dict(orient="records"),
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
