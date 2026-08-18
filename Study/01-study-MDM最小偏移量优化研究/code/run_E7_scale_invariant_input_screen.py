"""Candidate screen for scale-invariant ordered-sample inputs.

This is a representation-only comparison.  It reuses the sealed E5/E6
48,000-sample, 26-delta loss curves and the E6 training/evaluation contract.
No MDM fit is run here.

Representations (all applied to the ordered sample before the train-fold-only
per-position StandardScaler):

* mean:      x / mean(x)
* sample_sd: x / sd(x), ddof=1, without centering
* rms:       x / sqrt(mean(x**2))

Outputs are candidate evidence only.  Per-sample checkpoints live under the
ignored ``runtime/`` directory; compact summaries are written beside it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import subprocess
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6


STUDY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(
    STUDY_ROOT, "artifacts", "candidate", "E7_scale_invariant_input_screen"
)
RUNTIME_DIR = os.path.join(OUT_DIR, "runtime")
REPRESENTATIONS = ("mean", "sample_sd", "rms")
SCALES = (1e-3, 1.0, 1e3)
CONTRACT_VERSION = "E7_scale_invariant_input_screen_v1"


def sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def implementation_sha256() -> str:
    paths = [
        os.path.abspath(__file__),
        E6.__file__,
        CFG.__file__,
    ]
    h = hashlib.sha256()
    for path in paths:
        h.update(os.path.basename(path).encode("utf-8"))
        with open(path, "rb") as handle:
            h.update(handle.read())
    return h.hexdigest()


def scale_value(sample: np.ndarray, representation: str) -> float:
    sample = np.asarray(sample, dtype=np.float64)
    if representation == "mean":
        value = float(np.mean(sample))
    elif representation == "sample_sd":
        value = float(np.std(sample, ddof=1))
    elif representation == "rms":
        value = float(np.sqrt(np.mean(np.square(sample))))
    else:
        raise ValueError(f"Unknown representation: {representation}")
    if not np.isfinite(value) or value <= 0:
        raise ValueError(f"Invalid {representation} scale: {value}")
    return value


def represent_sample(sample: np.ndarray, representation: str) -> np.ndarray:
    ordered = np.sort(np.asarray(sample, dtype=np.float64))
    return ordered / scale_value(ordered, representation)


def build_representation_map(raw_map: dict, representation: str) -> dict:
    return {
        key: represent_sample(sample, representation)
        for key, sample in raw_map.items()
    }


def verify_data_sha256sums() -> dict:
    """Verify the existing shared-data receipt without modifying it."""
    receipt = os.path.join(CFG.SHARED_DATA_DIR, "data_sha256sums.txt")
    checked = 0
    with open(receipt, encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            expected, rel = line.split(maxsplit=1)
            path = os.path.join(CFG.SHARED_DATA_DIR, rel.replace("/", os.sep))
            if not os.path.isfile(path):
                raise FileNotFoundError(path)
            actual = sha256_file(path)
            if actual != expected:
                raise RuntimeError(f"SHA256 mismatch: {rel}")
            checked += 1
    return {"receipt": receipt, "entries_verified": checked, "all_match": True}


def model_tag(representation: str, n_val: int, fold_idx: int, seed: int) -> str:
    return f"{representation}_n{n_val}_fold{fold_idx + 1}_seed{seed}"


def checkpoint_paths(tag: str) -> tuple[str, str]:
    return (
        os.path.join(RUNTIME_DIR, f"{tag}.json"),
        os.path.join(RUNTIME_DIR, f"{tag}.csv"),
    )


def load_checkpoint(tag: str, expected_rows: int, code_sha: str):
    meta_path, rows_path = checkpoint_paths(tag)
    if not (os.path.isfile(meta_path) and os.path.isfile(rows_path)):
        return None
    try:
        with open(meta_path, encoding="utf-8") as handle:
            meta = json.load(handle)
        rows = pd.read_csv(rows_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return None
    required = set(E6.SAMPLE_KEYS + [
        "selected_delta", "selected_delta_idx", "true_loss", "is_valid", "model"
    ])
    if (
        meta.get("contract_version") != CONTRACT_VERSION
        or meta.get("implementation_sha256") != code_sha
        or len(rows) != expected_rows
        or not required.issubset(rows.columns)
    ):
        return None
    return meta, rows


def save_checkpoint(tag: str, meta: dict, rows: pd.DataFrame) -> None:
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    meta_path, rows_path = checkpoint_paths(tag)
    rows.to_csv(rows_path, index=False)
    with open(meta_path, "w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2, ensure_ascii=False)


def prediction_invariance_probe(
    raw_sample: np.ndarray,
    representation: str,
    input_scaler,
    target_scaler,
    model,
) -> dict:
    curves = []
    represented = []
    delta_indices = []
    for factor in SCALES:
        x = represent_sample(factor * raw_sample, representation)
        represented.append(x)
        pred_scaled = model.predict(input_scaler.transform(x.reshape(1, -1)))
        curve = target_scaler.inverse_transform(pred_scaled.reshape(1, -1))[0]
        curve = np.clip(curve, 0.0, None)
        curves.append(curve)
        delta_indices.append(int(np.argmin(curve)))
    base_x, base_curve = represented[1], curves[1]
    max_rep_diff = max(float(np.max(np.abs(x - base_x))) for x in represented)
    max_curve_diff = max(float(np.max(np.abs(curve - base_curve))) for curve in curves)
    return {
        "max_abs_representation_diff": max_rep_diff,
        "max_abs_prediction_curve_diff": max_curve_diff,
        "delta_indices": delta_indices,
        "selected_deltas": [float(E6.DELTA_GRID[i]) for i in delta_indices],
        "delta_consistent": len(set(delta_indices)) == 1,
        "curve_consistent_at_1e-10": bool(max_curve_diff <= 1e-10),
    }


def run_one(
    representation: str,
    n_val: int,
    fold_idx: int,
    seed: int,
    df_full: pd.DataFrame,
    raw_map: dict,
    rep_map: dict,
    fold_prep: list,
    code_sha: str,
) -> tuple[dict, pd.DataFrame]:
    fold = E6.get_combo_split()[fold_idx]
    prep = fold_prep[fold_idx]
    expected_rows = (
        sum(combo[2] == n_val for combo in fold["test_combos"]) * CFG.REPEATS
    )
    tag = model_tag(representation, n_val, fold_idx, seed)
    cached = load_checkpoint(tag, expected_rows, code_sha)
    if cached is not None:
        print(f"[skip] {tag}", flush=True)
        return cached

    keys_train, x_train, y_train, _ = E6.pivot_raw_vector(
        prep["df_train"], rep_map, n_val
    )
    keys_test, x_test, y_test, valid_test = E6.pivot_raw_vector(
        prep["df_test"], rep_map, n_val
    )
    if len(keys_test) != expected_rows:
        raise RuntimeError(f"{tag}: {len(keys_test)} test rows != {expected_rows}")
    if set(map(tuple, keys_train.to_numpy())) & set(map(tuple, keys_test.to_numpy())):
        raise RuntimeError(f"{tag}: train/test sample keys overlap")

    started = time.time()
    y_pred, n_iter, input_scaler, target_scaler, model = E6.train_specialist(
        x_train, y_train, x_test, seed
    )
    elapsed = time.time() - started
    selected, metrics = E6.evaluate_selection(
        keys_test, y_pred, y_test, tag, valid_test
    )

    probe_row = keys_test.iloc[0]
    probe_key = (
        float(probe_row["beta"]),
        float(probe_row["eta"]),
        float(probe_row["gamma"]),
        float(probe_row["gamma_over_eta"]),
        int(probe_row["n"]),
        int(probe_row["repeat_id"]),
    )
    invariance = prediction_invariance_probe(
        raw_map[probe_key], representation, input_scaler, target_scaler, model
    )
    meta = {
        "contract_version": CONTRACT_VERSION,
        "implementation_sha256": code_sha,
        "model_id": tag,
        "representation": representation,
        "n": int(n_val),
        "fold": int(fold_idx + 1),
        "seed": int(seed),
        "train_samples": int(len(keys_train)),
        "test_samples": int(len(keys_test)),
        "J1": float(metrics["J1"]),
        "failure_rate": float(metrics["failure_rate"]),
        "n_iter": int(n_iter),
        "runtime_s": float(elapsed),
        "input_scaler_fit": "train fold only; test fold transform only",
        "target_scaler_fit": "train fold only; test fold transform only",
        "failure_penalty": float(prep["failure_penalty"]),
        "invariance": invariance,
    }
    save_checkpoint(tag, meta, selected)
    print(
        f"[done] {tag}: J1={metrics['J1']:.6f} iter={n_iter} t={elapsed:.1f}s",
        flush=True,
    )
    return meta, selected


def aggregate(all_meta: list[dict], all_rows: pd.DataFrame, default_j1: float) -> dict:
    model_metrics = pd.DataFrame(
        {
            "representation": m["representation"],
            "n": m["n"],
            "fold": m["fold"],
            "seed": m["seed"],
            "J1": m["J1"],
            "failure_rate": m["failure_rate"],
            "n_iter": m["n_iter"],
            "runtime_s": m["runtime_s"],
        }
        for m in all_meta
    )
    seed_rows = []
    by_n_rows = []
    for representation in REPRESENTATIONS:
        rep = all_rows[all_rows["representation"] == representation]
        for seed in CFG.STABILITY_SEEDS:
            sub = rep[rep["seed"] == seed]
            seed_rows.append(
                {
                    "representation": representation,
                    "seed": seed,
                    "pooled_J1": math.sqrt(float(sub["true_loss"].mean())),
                    "failure_rate": 1.0 - float(sub["is_valid"].mean()),
                    "n_samples": int(len(sub)),
                }
            )
            for n_val, group in sub.groupby("n"):
                by_n_rows.append(
                    {
                        "representation": representation,
                        "seed": seed,
                        "n": int(n_val),
                        "J1": math.sqrt(float(group["true_loss"].mean())),
                        "n_samples": int(len(group)),
                    }
                )
    seed_df = pd.DataFrame(seed_rows)
    by_n_seed = pd.DataFrame(by_n_rows)
    summary_rows = []
    for representation, group in seed_df.groupby("representation", sort=False):
        model_j1 = model_metrics.loc[
            model_metrics["representation"] == representation, "J1"
        ]
        pooled_mean = float(group["pooled_J1"].mean())
        row = {
            "representation": representation,
            "pooled_J1_mean": pooled_mean,
            "pooled_J1_seed_std_ddof0": float(group["pooled_J1"].std(ddof=0)),
            "relative_improvement_vs_default": (default_j1 - pooled_mean) / default_j1,
            "failure_rate_mean": float(group["failure_rate"].mean()),
            "model_J1_min": float(model_j1.min()),
            "model_J1_q1": float(model_j1.quantile(0.25)),
            "model_J1_median": float(model_j1.median()),
            "model_J1_q3": float(model_j1.quantile(0.75)),
            "model_J1_max": float(model_j1.max()),
        }
        for n_val in CFG.N_GRID:
            vals = by_n_seed[
                (by_n_seed["representation"] == representation)
                & (by_n_seed["n"] == n_val)
            ]["J1"]
            row[f"J1_n{n_val}_mean"] = float(vals.mean())
            row[f"J1_n{n_val}_seed_std_ddof0"] = float(vals.std(ddof=0))
        summary_rows.append(row)
    return {
        "model_metrics": model_metrics,
        "seed_metrics": seed_df,
        "by_n_seed": by_n_seed,
        "summary": pd.DataFrame(summary_rows),
    }


def load_reference_values() -> dict:
    e6_summary_path = os.path.join(
        STUDY_ROOT, "artifacts", "formal", "E6_dimensional_raw", "specialist",
        "summary.json"
    )
    with open(e6_summary_path, encoding="utf-8") as handle:
        e6_summary = json.load(handle)
    return {
        "dimensional_raw_pooled_J1": float(
            e6_summary["dimensional_raw_3seed"]["pooled_J1_mean"]
        ),
        "existing_mean_normalized_per_seed": {
            str(seed): float(value)
            for seed, value in e6_summary["normalized_raw_candidate_control"]
            ["per_seed_pooled_J1"].items()
        },
    }


def run(force_rerun: bool = False) -> dict:
    os.makedirs(OUT_DIR, exist_ok=True)
    os.makedirs(RUNTIME_DIR, exist_ok=True)
    if force_rerun:
        for name in os.listdir(RUNTIME_DIR):
            if name.endswith((".csv", ".json")):
                os.remove(os.path.join(RUNTIME_DIR, name))

    started = time.time()
    code_sha = implementation_sha256()
    data_receipt = verify_data_sha256sums()
    with open(CFG.MC_MANIFEST_PATH, encoding="utf-8") as handle:
        mc_manifest = json.load(handle)
    df_mc = E6.load_mc_scan()
    integrity = E6.verify_data_integrity(df_mc, mc_manifest)
    raw_map, _ = E6.build_raw_sample_map(df_mc)
    df_full = E6.compute_per_sample_loss(df_mc)
    folds = E6.get_combo_split()
    fold_prep = [E6.prepare_fold(df_full, fold) for fold in folds]

    default_rows = df_full[np.isclose(df_full["delta"], CFG.DEFAULT_DELTA)]
    if default_rows["loss"].isna().any():
        raise RuntimeError("Default delta contains invalid loss; contract needs review")
    default_j1 = math.sqrt(float(default_rows["loss"].mean()))

    all_meta = []
    all_rows = []
    for representation in REPRESENTATIONS:
        rep_map = build_representation_map(raw_map, representation)
        for n_val in CFG.N_GRID:
            for fold_idx in range(CFG.N_FOLDS):
                for seed in CFG.STABILITY_SEEDS:
                    meta, selected = run_one(
                        representation, n_val, fold_idx, seed, df_full, raw_map,
                        rep_map, fold_prep, code_sha
                    )
                    all_meta.append(meta)
                    selected = selected.copy()
                    selected["representation"] = representation
                    selected["n_specialist"] = n_val
                    selected["fold"] = fold_idx + 1
                    selected["seed"] = seed
                    all_rows.append(selected)
    selected_all = pd.concat(all_rows, ignore_index=True)
    expected = len(REPRESENTATIONS) * len(CFG.STABILITY_SEEDS) * 48000
    if len(selected_all) != expected:
        raise RuntimeError(f"selected rows {len(selected_all)} != {expected}")

    agg = aggregate(all_meta, selected_all, default_j1)
    references = load_reference_values()
    summary_df = agg["summary"].copy()
    summary_df["difference_vs_dimensional_raw"] = (
        summary_df["pooled_J1_mean"] - references["dimensional_raw_pooled_J1"]
    )
    existing_mean = np.mean(
        list(references["existing_mean_normalized_per_seed"].values())
    )
    summary_df["difference_vs_existing_mean_normalized"] = (
        summary_df["pooled_J1_mean"] - existing_mean
    )

    invariance_rows = []
    for meta in all_meta:
        invariance_rows.append({
            "model_id": meta["model_id"],
            "representation": meta["representation"],
            "n": meta["n"],
            "fold": meta["fold"],
            "seed": meta["seed"],
            **meta["invariance"],
        })
    invariance_df = pd.DataFrame(invariance_rows)
    if not invariance_df["delta_consistent"].all():
        raise RuntimeError("At least one model changes selected delta under scaling")
    if not invariance_df["curve_consistent_at_1e-10"].all():
        raise RuntimeError("At least one model changes prediction curve under scaling")

    agg["model_metrics"].to_csv(os.path.join(OUT_DIR, "model_metrics.csv"), index=False)
    agg["seed_metrics"].to_csv(os.path.join(OUT_DIR, "seed_metrics.csv"), index=False)
    agg["by_n_seed"].to_csv(os.path.join(OUT_DIR, "by_n_seed.csv"), index=False)
    summary_df.to_csv(os.path.join(OUT_DIR, "representation_summary.csv"), index=False)
    invariance_df.to_csv(os.path.join(OUT_DIR, "invariance_check.csv"), index=False)
    pd.DataFrame(E6.build_split_rows()).to_csv(
        os.path.join(OUT_DIR, "split_report.csv"), index=False
    )

    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=E6.PROJECT_ROOT, text=True
    ).strip()
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"], cwd=E6.PROJECT_ROOT, text=True
    ).strip()
    summary = {
        "experiment": "E7 scale-invariant ordered-sample input screen",
        "status": "candidate_screen_only",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "contract_version": CONTRACT_VERSION,
        "representations": {
            "mean": "ordered X / mean(X)",
            "sample_sd": "ordered X / sample_sd(X), ddof=1, no centering",
            "rms": "ordered X / sqrt(mean(X^2))",
        },
        "scientific_contract": {
            "only_change": "representation before train-fold StandardScaler",
            "reused": "E6 per-n MLP, folds, seeds, 26 targets, failure and J1",
            "mdm_rerun": False,
            "confirmation_experiment": False,
        },
        "default_J1": default_j1,
        "references": references,
        "results": summary_df.to_dict(orient="records"),
        "invariance": {
            "scales": list(SCALES),
            "models_checked": int(len(invariance_df)),
            "all_delta_consistent": bool(invariance_df["delta_consistent"].all()),
            "all_curves_consistent_at_1e-10": bool(
                invariance_df["curve_consistent_at_1e-10"].all()
            ),
            "max_abs_representation_diff": float(
                invariance_df["max_abs_representation_diff"].max()
            ),
            "max_abs_prediction_curve_diff": float(
                invariance_df["max_abs_prediction_curve_diff"].max()
            ),
        },
        "data_integrity": integrity,
        "data_sha256_receipt": data_receipt,
        "implementation_sha256": code_sha,
        "run_start_git_head": git_head,
        "run_start_branch": branch,
        "runtime_s": time.time() - started,
    }
    with open(os.path.join(OUT_DIR, "summary.json"), "w", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, ensure_ascii=False)

    manifest = {
        "status": "candidate_screen_only",
        "source_data_manifest": os.path.relpath(CFG.MC_MANIFEST_PATH, E6.PROJECT_ROOT),
        "source_data_manifest_sha256": sha256_file(CFG.MC_MANIFEST_PATH),
        "source_data_receipt_sha256": sha256_file(data_receipt["receipt"]),
        "implementation_files": {
            os.path.relpath(os.path.abspath(__file__), E6.PROJECT_ROOT): sha256_file(
                os.path.abspath(__file__)
            ),
            os.path.relpath(E6.__file__, E6.PROJECT_ROOT): sha256_file(E6.__file__),
            os.path.relpath(CFG.__file__, E6.PROJECT_ROOT): sha256_file(CFG.__file__),
        },
        "outputs": [
            "summary.json", "representation_summary.csv", "seed_metrics.csv",
            "by_n_seed.csv", "model_metrics.csv", "invariance_check.csv",
            "split_report.csv",
        ],
        "ignored_runtime": "runtime/ contains per-model selected rows/checkpoint metadata",
    }
    with open(os.path.join(OUT_DIR, "manifest.json"), "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, indent=2, ensure_ascii=False)
    print(summary_df.to_string(index=False), flush=True)
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--force-rerun", action="store_true")
    args = parser.parse_args()
    run(force_rerun=args.force_rerun)
