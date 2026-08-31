"""Study01-aligned Direct-P versus adaptive-MDM generalization experiment.

The experiment has one fixed training design and one independent test panel:

* training: the exact Study01 8 beta x 5 gamma/eta x 4 n x 300 design;
* model seed: 42 only;
* test: 21 beta positions from 0.75 to 5.75, including seen grid,
  in-domain unseen midpoints, near OOD, and far OOD;
* methods: ordered-mean-normalized Direct-P, current Mean-Normalized selector
  followed by production MDM, and production MDM with delta=0.1.

The ignored Study01 training chunks are not available in every checkout.  This
entry therefore recreates the training loss curves with the production MDM in
its own checkpointed Research04 artifact tree.  It never modifies Study01
artifacts.  Sample generation and method calls use the shared platform entries.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing as mp
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import torch


HERE = Path(__file__).resolve()
RESEARCH_ROOT = HERE.parents[1]
PROJECT_ROOT = HERE.parents[3]
STUDY_CODE = (
    PROJECT_ROOT / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
)
PYTHON_ROOT = PROJECT_ROOT / "python"
for path in (STUDY_CODE, PYTHON_ROOT):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import dim_raw_config as STUDY_CFG  # noqa: E402
import run_E6b_dimensional_raw_specialist as SELECTOR  # noqa: E402
import run_p3_direct_mlp as DIRECT  # noqa: E402
from studies.common.metrics import (  # noqa: E402
    check_status,
    param_relative_errors,
    quantile_relative_error,
    summarize_standard_errors,
)
from studies.common.runner import run_method  # noqa: E402
from studies.common.sample import generate_sample  # noqa: E402


RUN_ID = "study01_aligned_generalization_v1"
MODEL_SEED = 42
TRAIN_SEED_NAMESPACE = "study01_nrmc_v1"
TEST_SEED_NAMESPACE = "research04_generalization_v1"
ETA = 1000.0
TRAIN_BETAS = tuple(float(x) for x in STUDY_CFG.BETA_GRID)
TEST_BETAS = tuple(round(0.75 + 0.25 * i, 2) for i in range(21))
GAMMA_RATIOS = tuple(float(x) for x in STUDY_CFG.GAMMA_OVER_ETA_GRID)
N_VALUES = tuple(int(x) for x in STUDY_CFG.N_GRID)
DELTA_GRID = tuple(float(x) for x in STUDY_CFG.DELTA_GRID)
TRAIN_REPEATS = int(STUDY_CFG.REPEATS)
TEST_REPEATS = 300
DEFAULT_DELTA = float(STUDY_CFG.DEFAULT_DELTA)
R_LEVELS = (0.90, 0.95, 0.99)

OUT_DIR = RESEARCH_ROOT / "artifacts" / RUN_ID
SMOKE_DIR = RESEARCH_ROOT / "artifacts" / "smoke" / RUN_ID
SCAN_DIR = OUT_DIR / "training_scan" / "chunks"
MODEL_DIR = OUT_DIR / "models"
BLOCK_DIR = OUT_DIR / "evaluation_blocks"
RESULTS_PATH = OUT_DIR / "per_sample_results.csv.gz"
SUMMARY_PATH = OUT_DIR / "method_summary.csv"
CELL_PATH = OUT_DIR / "cell_summary.csv"
PAIRED_PATH = OUT_DIR / "paired_method_differences.csv"
MANIFEST_PATH = OUT_DIR / "manifest.json"
RUN_LOG_PATH = OUT_DIR / "run_log.txt"

RESULT_COLUMNS = [
    "method", "beta_group", "beta", "eta", "gamma", "gamma_over_eta",
    "n", "repeat_id", "beta_hat", "eta_hat", "gamma_hat", "converged",
    "status", "failure_reason", "selected_delta", "loss_natural",
    "loss_primary", "beta_rel_error", "eta_rel_error", "gamma_rel_error",
    "x0.90_rel_error", "x0.95_rel_error", "x0.99_rel_error",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str, path: Path = RUN_LOG_PATH) -> None:
    line = f"{utc_now()} {message}"
    print(line, flush=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def git_value(*args: str) -> str:
    try:
        return subprocess.check_output(
            ["git", *args], cwd=PROJECT_ROOT, text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def beta_group(beta: float) -> str:
    if any(math.isclose(beta, x, abs_tol=1e-12) for x in TRAIN_BETAS):
        return "seen_grid"
    if 1.5 < beta < 5.0:
        return "in_domain_unseen"
    if math.isclose(beta, 1.25, abs_tol=1e-12) or math.isclose(
        beta, 5.25, abs_tol=1e-12
    ):
        return "near_ood"
    return "far_ood"


def expected_test_counts() -> dict[str, int]:
    counts: dict[str, int] = {}
    multiplier = len(GAMMA_RATIOS) * len(N_VALUES) * TEST_REPEATS
    for beta in TEST_BETAS:
        group = beta_group(beta)
        counts[group] = counts.get(group, 0) + multiplier
    return counts


def joint_loss(beta_hat: float, eta_hat: float, gamma_hat: float,
               beta: float, eta: float, gamma: float) -> float:
    return float(
        ((beta_hat - beta) / beta) ** 2
        + ((eta_hat - eta) / eta) ** 2
        + ((gamma_hat - gamma) / eta) ** 2
    )


def scan_chunk_path(root: Path, beta: float, ratio: float, n_value: int) -> Path:
    return root / f"beta_{beta:.2f}_goe_{ratio:.2f}_n_{n_value:02d}.csv.gz"


def validate_scan_chunk(path: Path, beta: float, ratio: float, n_value: int,
                        repeats: int) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing"
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        return False, f"read:{type(exc).__name__}"
    required = {
        "beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id",
        "delta", "beta_hat", "eta_hat", "gamma_hat", "converged",
        "status", "loss",
    }
    if not required.issubset(frame.columns):
        return False, "schema"
    if len(frame) != repeats * len(DELTA_GRID):
        return False, "row_count"
    if not np.allclose(frame["beta"], beta):
        return False, "beta"
    if not np.allclose(frame["gamma_over_eta"], ratio):
        return False, "ratio"
    if not frame["n"].eq(n_value).all():
        return False, "n"
    if frame.duplicated(["repeat_id", "delta"]).any():
        return False, "duplicates"
    return True, "ok"


def _generate_scan_combo(task: tuple[str, float, float, int, int]) -> dict:
    root_text, beta, ratio, n_value, repeats = task
    root = Path(root_text)
    path = scan_chunk_path(root, beta, ratio, n_value)
    valid, reason = validate_scan_chunk(path, beta, ratio, n_value, repeats)
    if valid:
        return {"status": "skipped", "path": str(path), "seconds": 0.0}
    if path.exists():
        raise RuntimeError(f"invalid existing training chunk {path}: {reason}")

    rows: list[dict] = []
    gamma = ratio * ETA
    started = time.perf_counter()
    for repeat_id in range(repeats):
        sample = generate_sample(
            beta, ETA, gamma, n_value, repeat_id, seed=TRAIN_SEED_NAMESPACE
        )
        for delta in DELTA_GRID:
            estimate = run_method("mdm", sample, offset=delta)
            bh = estimate.get("beta_hat")
            eh = estimate.get("eta_hat")
            gh = estimate.get("gamma_hat")
            converged = bool(estimate.get("converged"))
            good = (
                converged and bh is not None and eh is not None and gh is not None
                and np.isfinite([bh, eh, gh]).all()
                and float(bh) > 0 and float(eh) > 0 and float(gh) >= 0
            )
            rows.append(
                {
                    "beta": beta,
                    "eta": ETA,
                    "gamma": gamma,
                    "gamma_over_eta": ratio,
                    "n": n_value,
                    "repeat_id": repeat_id,
                    "delta": delta,
                    "beta_hat": float(bh) if bh is not None else np.nan,
                    "eta_hat": float(eh) if eh is not None else np.nan,
                    "gamma_hat": float(gh) if gh is not None else np.nan,
                    "converged": converged,
                    "status": "success" if good else "failure",
                    "loss": joint_loss(bh, eh, gh, beta, ETA, gamma)
                    if good else np.nan,
                }
            )
    frame = pd.DataFrame(rows).sort_values(["repeat_id", "delta"])
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, compression="gzip", lineterminator="\n")
    os.replace(temporary, path)
    valid, reason = validate_scan_chunk(path, beta, ratio, n_value, repeats)
    if not valid:
        raise RuntimeError(f"written training chunk failed validation: {reason}")
    return {
        "status": "written", "path": str(path),
        "seconds": time.perf_counter() - started,
    }


def generate_training_scan(root: Path, betas: tuple[float, ...],
                           ratios: tuple[float, ...], n_values: tuple[int, ...],
                           repeats: int, workers: int, log_path: Path) -> list[dict]:
    tasks = [
        (str(root), beta, ratio, n_value, repeats)
        for beta in betas for ratio in ratios for n_value in n_values
    ]
    receipts: list[dict] = []
    with mp.Pool(processes=workers) as pool:
        for index, receipt in enumerate(pool.imap_unordered(_generate_scan_combo, tasks), 1):
            receipts.append(receipt)
            if index % 5 == 0 or index == len(tasks):
                log(
                    f"TRAIN_SCAN {index}/{len(tasks)} written="
                    f"{sum(x['status'] == 'written' for x in receipts)}",
                    log_path,
                )
    return receipts


def load_training_n(root: Path, betas: tuple[float, ...],
                    ratios: tuple[float, ...], n_value: int,
                    repeats: int) -> dict:
    chunks = []
    for beta in betas:
        for ratio in ratios:
            path = scan_chunk_path(root, beta, ratio, n_value)
            valid, reason = validate_scan_chunk(path, beta, ratio, n_value, repeats)
            if not valid:
                raise RuntimeError(f"training chunk invalid {path}: {reason}")
            chunks.append(pd.read_csv(path))
    long = pd.concat(chunks, ignore_index=True)
    finite_losses = long["loss"].to_numpy(dtype=float)
    finite_losses = finite_losses[np.isfinite(finite_losses)]
    if finite_losses.size == 0:
        raise RuntimeError("no finite training losses")
    penalty = float(np.percentile(finite_losses, 99))
    long["loss_filled"] = long["loss"].fillna(penalty)

    sample_rows = (
        long[["beta", "gamma_over_eta", "n", "repeat_id"]]
        .drop_duplicates().sort_values(["beta", "gamma_over_eta", "n", "repeat_id"])
        .reset_index(drop=True)
    )
    n_samples = len(sample_rows)
    expected = len(betas) * len(ratios) * repeats
    if n_samples != expected:
        raise RuntimeError(f"training sample count {n_samples} != {expected}")

    raw = np.empty((n_samples, n_value), dtype=np.float64)
    curves = np.empty((n_samples, len(DELTA_GRID)), dtype=np.float64)
    params = np.empty((n_samples, 3), dtype=np.float64)
    lookup = long.set_index(
        ["beta", "gamma_over_eta", "n", "repeat_id", "delta"]
    )["loss_filled"]
    for i, row in sample_rows.iterrows():
        beta = float(row["beta"])
        ratio = float(row["gamma_over_eta"])
        repeat_id = int(row["repeat_id"])
        gamma = ratio * ETA
        raw[i] = generate_sample(
            beta, ETA, gamma, n_value, repeat_id, seed=TRAIN_SEED_NAMESPACE
        )
        params[i] = [beta, ETA, gamma]
        curves[i] = [
            float(lookup.loc[(beta, ratio, n_value, repeat_id, delta)])
            for delta in DELTA_GRID
        ]
    means = raw.mean(axis=1)
    normalized = raw / means[:, None]
    if not np.allclose(normalized.mean(axis=1), 1.0, atol=1e-12):
        raise RuntimeError("mean-normalized input contract failed")
    return {
        "keys": sample_rows,
        "raw": raw,
        "normalized": normalized,
        "curves": curves,
        "params": params,
        "x_bar": means,
        "failure_penalty": penalty,
    }


def train_models_for_n(data: dict, n_value: int, model_dir: Path,
                       log_path: Path) -> dict:
    model_dir.mkdir(parents=True, exist_ok=True)
    adaptive_path = model_dir / f"adaptive_n{n_value}_seed42.joblib"
    direct_path = model_dir / f"direct_n{n_value}_seed42.pt"
    meta_path = model_dir / f"training_n{n_value}_seed42.json"

    if adaptive_path.exists() and direct_path.exists() and meta_path.exists():
        adaptive = joblib.load(adaptive_path)
        payload = torch.load(direct_path, map_location="cpu", weights_only=False)
        model = DIRECT.DirectMLP(input_dim=n_value)
        model.load_state_dict(payload["state_dict"])
        return {
            "adaptive": adaptive,
            "direct_model": model,
            "direct_info": payload["info"],
            "meta": json.loads(meta_path.read_text(encoding="utf-8")),
        }

    started = time.perf_counter()
    _, adaptive_iter, input_scaler, target_scaler, adaptive_model = (
        SELECTOR.train_specialist(
            data["normalized"], data["curves"], data["normalized"][:1], MODEL_SEED
        )
    )
    adaptive_seconds = time.perf_counter() - started
    adaptive = {
        "model": adaptive_model,
        "input_scaler": input_scaler,
        "target_scaler": target_scaler,
        "n_iter": int(adaptive_iter),
    }
    joblib.dump(adaptive, adaptive_path, compress=3)

    started = time.perf_counter()
    direct_model, direct_info = DIRECT.train_direct_mlp(
        data["normalized"], data["params"], data["x_bar"], MODEL_SEED
    )
    direct_seconds = time.perf_counter() - started
    torch.save(
        {"state_dict": direct_model.state_dict(), "info": direct_info}, direct_path
    )
    meta = {
        "n": n_value,
        "seed": MODEL_SEED,
        "n_train": int(len(data["keys"])),
        "input": "sorted X / sample mean",
        "adaptive_target": "26-point Study01 J1-squared loss curve",
        "direct_target": "three decoded parameters with J1-compatible P loss",
        "hidden_layers": list(STUDY_CFG.MLP_HIDDEN_LAYERS),
        "max_iter": int(STUDY_CFG.MLP_MAX_ITER),
        "patience": int(STUDY_CFG.MLP_N_ITER_NO_CHANGE),
        "adaptive_n_iter": int(adaptive_iter),
        "direct_n_iter": int(direct_info["n_iter"]),
        "adaptive_seconds": adaptive_seconds,
        "direct_seconds": direct_seconds,
        "failure_penalty": float(data["failure_penalty"]),
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    log(
        f"TRAIN_MODELS n={n_value} adaptive_iter={adaptive_iter} "
        f"direct_iter={direct_info['n_iter']} seconds="
        f"{adaptive_seconds + direct_seconds:.2f}",
        log_path,
    )
    return {
        "adaptive": adaptive,
        "direct_model": direct_model,
        "direct_info": direct_info,
        "meta": meta,
    }


def predict_models(models: dict, samples: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    means = samples.mean(axis=1)
    normalized = samples / means[:, None]
    adaptive = models["adaptive"]
    x_scaled = adaptive["input_scaler"].transform(normalized)
    curve_scaled = adaptive["model"].predict(x_scaled)
    curves = adaptive["target_scaler"].inverse_transform(curve_scaled)
    curves = np.clip(curves, 0.0, None)
    delta_indices = np.argmin(curves, axis=1)
    selected_delta = np.asarray([DELTA_GRID[i] for i in delta_indices], dtype=float)
    direct_predictions = DIRECT.predict_direct_mlp(
        models["direct_model"], models["direct_info"], normalized, means
    )
    return selected_delta, direct_predictions


def _failure_reason(result: dict) -> str:
    extra = result.get("extra") or {}
    if isinstance(extra, dict):
        return str(extra.get("raw_status") or extra.get("error") or "not_converged")
    return "not_converged"


def _estimate_mdm_pair(task: tuple[np.ndarray, float]) -> tuple[dict, dict]:
    sample, selected_delta = task
    adaptive = run_method("mdm", sample, offset=float(selected_delta))
    default = run_method("mdm", sample, offset=DEFAULT_DELTA)
    return adaptive, default


def result_row(method: str, beta: float, ratio: float, n_value: int,
               repeat_id: int, sample: np.ndarray, beta_hat, eta_hat,
               gamma_hat, converged: bool, failure_reason: str,
               selected_delta: float | None, failure_penalty: float) -> dict:
    gamma = ratio * ETA
    values_present = beta_hat is not None and eta_hat is not None and gamma_hat is not None
    status = "failure"
    if values_present:
        status = check_status(
            float(beta_hat), float(eta_hat), float(gamma_hat),
            beta, ETA, gamma, converged=converged,
            sample_min=float(np.min(sample)),
        )
        if float(gamma_hat) < 0:
            status = "failure"
    if status == "success":
        bh, eh, gh = float(beta_hat), float(eta_hat), float(gamma_hat)
        loss_natural = joint_loss(bh, eh, gh, beta, ETA, gamma)
        rel = param_relative_errors(bh, eh, gh, beta, ETA, gamma)
        q_errors = {
            level: quantile_relative_error(bh, eh, gh, beta, ETA, gamma, level)
            for level in R_LEVELS
        }
    else:
        bh = eh = gh = np.nan
        loss_natural = np.nan
        rel = {"beta": np.nan, "eta": np.nan, "gamma": np.nan}
        q_errors = {level: np.nan for level in R_LEVELS}
    return {
        "method": method,
        "beta_group": beta_group(beta),
        "beta": beta,
        "eta": ETA,
        "gamma": gamma,
        "gamma_over_eta": ratio,
        "n": n_value,
        "repeat_id": repeat_id,
        "beta_hat": bh,
        "eta_hat": eh,
        "gamma_hat": gh,
        "converged": status == "success",
        "status": status,
        "failure_reason": "" if status == "success" else failure_reason,
        "selected_delta": selected_delta,
        "loss_natural": loss_natural,
        "loss_primary": loss_natural if status == "success" else failure_penalty,
        "beta_rel_error": rel["beta"],
        "eta_rel_error": rel["eta"],
        "gamma_rel_error": rel["gamma"],
        "x0.90_rel_error": q_errors[0.90],
        "x0.95_rel_error": q_errors[0.95],
        "x0.99_rel_error": q_errors[0.99],
    }


def evaluation_block_path(root: Path, beta: float, n_value: int) -> Path:
    return root / f"beta_{beta:.2f}_n_{n_value:02d}.csv.gz"


def validate_evaluation_block(path: Path, beta: float, n_value: int,
                              repeats: int) -> tuple[bool, str]:
    if not path.is_file():
        return False, "missing"
    try:
        frame = pd.read_csv(path)
    except Exception as exc:
        return False, f"read:{type(exc).__name__}"
    if not set(RESULT_COLUMNS).issubset(frame.columns):
        return False, "schema"
    expected = len(GAMMA_RATIOS) * repeats * 3
    if len(frame) != expected:
        return False, "row_count"
    if not np.allclose(frame["beta"], beta) or not frame["n"].eq(n_value).all():
        return False, "keys"
    key_cols = ["method", "gamma_over_eta", "repeat_id"]
    if frame.duplicated(key_cols).any():
        return False, "duplicates"
    return True, "ok"


def evaluate_block(beta: float, n_value: int, repeats: int, models: dict,
                   block_root: Path, workers: int, failure_penalty: float,
                   log_path: Path) -> Path:
    path = evaluation_block_path(block_root, beta, n_value)
    valid, reason = validate_evaluation_block(path, beta, n_value, repeats)
    if valid:
        log(f"EVAL_SKIP beta={beta:.2f} n={n_value}", log_path)
        return path
    if path.exists():
        raise RuntimeError(f"invalid existing evaluation block {path}: {reason}")

    sample_rows = []
    samples = []
    for ratio in GAMMA_RATIOS:
        gamma = ratio * ETA
        for repeat_id in range(repeats):
            samples.append(
                generate_sample(
                    beta, ETA, gamma, n_value, repeat_id,
                    seed=TEST_SEED_NAMESPACE,
                )
            )
            sample_rows.append((ratio, repeat_id))
    sample_array = np.asarray(samples, dtype=np.float64)
    selected_delta, direct_predictions = predict_models(models, sample_array)
    if not np.all(np.isin(selected_delta, np.asarray(DELTA_GRID))):
        raise RuntimeError("selector predicted delta outside frozen grid")

    tasks = [(sample_array[i], float(selected_delta[i])) for i in range(len(sample_array))]
    mdm_pairs: list[tuple[dict, dict]] = []
    with mp.Pool(processes=workers) as pool:
        for pair in pool.imap(_estimate_mdm_pair, tasks, chunksize=32):
            mdm_pairs.append(pair)

    rows = []
    for i, (ratio, repeat_id) in enumerate(sample_rows):
        sample = sample_array[i]
        dp = direct_predictions[i]
        rows.append(
            result_row(
                "Direct-P", beta, ratio, n_value, repeat_id, sample,
                dp[0], dp[1], dp[2], True, "", None, failure_penalty,
            )
        )
        adaptive, default = mdm_pairs[i]
        rows.append(
            result_row(
                "Adaptive-MDM", beta, ratio, n_value, repeat_id, sample,
                adaptive.get("beta_hat"), adaptive.get("eta_hat"),
                adaptive.get("gamma_hat"), bool(adaptive.get("converged")),
                _failure_reason(adaptive), float(selected_delta[i]), failure_penalty,
            )
        )
        rows.append(
            result_row(
                "MDM-0.1", beta, ratio, n_value, repeat_id, sample,
                default.get("beta_hat"), default.get("eta_hat"),
                default.get("gamma_hat"), bool(default.get("converged")),
                _failure_reason(default), DEFAULT_DELTA, failure_penalty,
            )
        )
    frame = pd.DataFrame(rows, columns=RESULT_COLUMNS)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    frame.to_csv(temporary, index=False, compression="gzip", lineterminator="\n")
    os.replace(temporary, path)
    valid, reason = validate_evaluation_block(path, beta, n_value, repeats)
    if not valid:
        raise RuntimeError(f"written evaluation block failed validation: {reason}")
    log(
        f"EVAL_DONE beta={beta:.2f} group={beta_group(beta)} n={n_value} "
        f"samples={len(sample_array)} failures={int((frame.status != 'success').sum())}",
        log_path,
    )
    return path


def summarize_error_frame(frame: pd.DataFrame, group_cols: list[str]) -> pd.DataFrame:
    rows = []
    error_cols = {
        "beta": "beta_rel_error",
        "eta": "eta_rel_error",
        "gamma": "gamma_rel_error",
        "x0.90": "x0.90_rel_error",
        "x0.95": "x0.95_rel_error",
        "x0.99": "x0.99_rel_error",
    }
    for keys, group in frame.groupby(group_cols, dropna=False, sort=True):
        if not isinstance(keys, tuple):
            keys = (keys,)
        base = dict(zip(group_cols, keys))
        primary = group["loss_primary"].to_numpy(dtype=float)
        valid_loss = group["loss_natural"].dropna().to_numpy(dtype=float)
        tail = np.sqrt(np.maximum(primary, 0.0))
        base.update(
            n_total=int(len(group)),
            n_valid=int(group["status"].eq("success").sum()),
            failure_rate=float(1.0 - group["status"].eq("success").mean()),
            J1_primary=float(math.sqrt(np.mean(primary))),
            J1_valid=float(math.sqrt(np.mean(valid_loss))) if valid_loss.size else np.nan,
            P95_joint_error=float(np.percentile(tail, 95)),
            CVaR95_joint_error=float(tail[tail >= np.percentile(tail, 95)].mean()),
        )
        for label, column in error_cols.items():
            stats = summarize_standard_errors(group[column].to_numpy(dtype=float))
            for metric in ("bias", "sd", "rmse", "mae"):
                base[f"{label}_{metric}"] = stats[metric]
        rows.append(base)
    return pd.DataFrame(rows)


def paired_differences(frame: pd.DataFrame) -> pd.DataFrame:
    keys = ["beta", "gamma_over_eta", "n", "repeat_id"]
    wide = frame.pivot(index=keys, columns="method", values="loss_primary").reset_index()
    rows = []
    for group_name, group in wide.assign(
        beta_group=wide["beta"].map(beta_group)
    ).groupby("beta_group"):
        for comparator in ("Adaptive-MDM", "MDM-0.1"):
            diff = group["Direct-P"].to_numpy() - group[comparator].to_numpy()
            rows.append(
                {
                    "beta_group": group_name,
                    "contrast": f"Direct-P minus {comparator}",
                    "n_samples": int(len(diff)),
                    "mean_delta_J1_squared": float(np.mean(diff)),
                    "median_delta_J1_squared": float(np.median(diff)),
                    "direct_better_fraction": float(np.mean(diff < 0)),
                }
            )
    return pd.DataFrame(rows)


def finalize_outputs(block_paths: list[Path], out_dir: Path, log_path: Path) -> dict:
    frame = pd.concat([pd.read_csv(path) for path in block_paths], ignore_index=True)
    expected_samples = len(TEST_BETAS) * len(GAMMA_RATIOS) * len(N_VALUES) * TEST_REPEATS
    if len(frame) != expected_samples * 3:
        raise RuntimeError(f"result rows {len(frame)} != {expected_samples * 3}")
    out_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(RESULTS_PATH, index=False, compression="gzip", lineterminator="\n")
    summary = summarize_error_frame(frame, ["method", "beta_group"])
    summary.to_csv(SUMMARY_PATH, index=False)
    cells = summarize_error_frame(
        frame, ["method", "beta_group", "beta", "gamma_over_eta", "n"]
    )
    cells.to_csv(CELL_PATH, index=False)
    paired = paired_differences(frame)
    paired.to_csv(PAIRED_PATH, index=False)
    log(f"FINALIZED samples={expected_samples} rows={len(frame)}", log_path)
    return {
        "n_samples": expected_samples,
        "n_rows": len(frame),
        "counts_by_beta_group": expected_test_counts(),
        "failures_by_method": frame.groupby("method")["status"].apply(
            lambda x: int((x != "success").sum())
        ).to_dict(),
    }


def write_manifest(validation: dict, model_meta: dict[int, dict]) -> None:
    manifest = {
        "run_id": RUN_ID,
        "status": "complete",
        "generated_at": utc_now(),
        "git": {
            "commit": git_value("rev-parse", "HEAD"),
            "branch": git_value("branch", "--show-current"),
            "dirty": bool(git_value("status", "--short")),
        },
        "training_design": {
            "beta": list(TRAIN_BETAS),
            "eta": ETA,
            "gamma_over_eta": list(GAMMA_RATIOS),
            "n": list(N_VALUES),
            "repeats": TRAIN_REPEATS,
            "samples": len(TRAIN_BETAS) * len(GAMMA_RATIOS) * len(N_VALUES) * TRAIN_REPEATS,
            "delta_grid": list(DELTA_GRID),
            "seed_namespace": TRAIN_SEED_NAMESPACE,
            "model_seed": MODEL_SEED,
        },
        "test_design": {
            "beta": list(TEST_BETAS),
            "beta_groups": {str(beta): beta_group(beta) for beta in TEST_BETAS},
            "eta": ETA,
            "gamma_over_eta": list(GAMMA_RATIOS),
            "n": list(N_VALUES),
            "repeats": TEST_REPEATS,
            "seed_namespace": TEST_SEED_NAMESPACE,
        },
        "methods": ["Direct-P", "Adaptive-MDM", "MDM-0.1"],
        "model_training": {str(n): meta for n, meta in model_meta.items()},
        "validation": validation,
        "metrics": {
            "primary": ["relative Bias", "relative SD", "relative RMSE"],
            "summary": "J1 with train-derived failure penalty",
            "tail": ["P95 joint error", "CVaR95 joint error"],
            "quantiles": list(R_LEVELS),
        },
        "code_sha256": sha256_file(HERE),
        "outputs": [
            RESULTS_PATH.name, SUMMARY_PATH.name, CELL_PATH.name,
            PAIRED_PATH.name, MANIFEST_PATH.name,
        ],
    }
    MANIFEST_PATH.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def run_smoke(workers: int) -> None:
    smoke_log = SMOKE_DIR / "run_log.txt"
    smoke_scan = SMOKE_DIR / "training_scan" / "chunks"
    smoke_models = SMOKE_DIR / "models"
    smoke_blocks = SMOKE_DIR / "evaluation_blocks"
    log("SMOKE_START", smoke_log)
    generate_training_scan(
        smoke_scan, (1.5, 3.0, 5.0), (0.10, 0.50, 1.00), (7,), 10,
        workers, smoke_log,
    )
    data = load_training_n(
        smoke_scan, (1.5, 3.0, 5.0), (0.10, 0.50, 1.00), 7, 10
    )
    models = train_models_for_n(data, 7, smoke_models, smoke_log)
    paths = [
        evaluate_block(beta, 7, 2, models, smoke_blocks, workers,
                       float(data["failure_penalty"]), smoke_log)
        for beta in (1.75, 1.25)
    ]
    frame = pd.concat([pd.read_csv(path) for path in paths], ignore_index=True)
    if len(frame) != 2 * len(GAMMA_RATIOS) * 2 * 3:
        raise RuntimeError("smoke row count mismatch")
    summary = {
        "status": "pass",
        "generated_at": utc_now(),
        "rows": int(len(frame)),
        "methods": sorted(frame["method"].unique()),
        "beta_groups": sorted(frame["beta_group"].unique()),
        "selected_delta_on_grid": bool(
            frame.loc[frame.method == "Adaptive-MDM", "selected_delta"].isin(DELTA_GRID).all()
        ),
        "failures": int((frame.status != "success").sum()),
    }
    (SMOKE_DIR / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log(f"SMOKE_PASS rows={len(frame)} failures={summary['failures']}", smoke_log)


def run_formal(workers: int) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    log("FORMAL_START")
    generate_training_scan(
        SCAN_DIR, TRAIN_BETAS, GAMMA_RATIOS, N_VALUES, TRAIN_REPEATS,
        workers, RUN_LOG_PATH,
    )
    models_by_n = {}
    model_meta = {}
    failure_penalties = []
    for n_value in N_VALUES:
        data = load_training_n(
            SCAN_DIR, TRAIN_BETAS, GAMMA_RATIOS, n_value, TRAIN_REPEATS
        )
        models = train_models_for_n(data, n_value, MODEL_DIR, RUN_LOG_PATH)
        models_by_n[n_value] = models
        model_meta[n_value] = models["meta"]
        failure_penalties.append(float(data["failure_penalty"]))
    failure_penalty = float(max(failure_penalties))
    log(f"FAILURE_PENALTY frozen_from_training={failure_penalty:.8f}")

    block_paths = []
    for beta in TEST_BETAS:
        for n_value in N_VALUES:
            block_paths.append(
                evaluate_block(
                    beta, n_value, TEST_REPEATS, models_by_n[n_value], BLOCK_DIR,
                    workers, failure_penalty, RUN_LOG_PATH,
                )
            )
    validation = finalize_outputs(block_paths, OUT_DIR, RUN_LOG_PATH)
    write_manifest(validation, model_meta)
    log("FORMAL_COMPLETE")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("smoke", "formal"), required=True)
    parser.add_argument("--workers", type=int, default=4)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    workers = max(1, int(args.workers))
    if args.mode == "smoke":
        run_smoke(workers)
    else:
        run_formal(workers)


if __name__ == "__main__":
    mp.freeze_support()
    main()
