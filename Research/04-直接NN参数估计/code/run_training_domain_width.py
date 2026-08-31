"""Direct-P training-domain width experiment.

The experiment separates two questions:

1. fixed_total: every beta interval receives 12,000 training samples per n,
   so widening the interval reduces samples per beta x gamma cell;
2. fixed_density: every beta x gamma cell receives 300 samples, so widening
   the interval increases total training data.

All models use the same architecture, seed, optimization budget, gamma/eta
grid, n values, and independent shared test samples as the formal Research04
generalization experiment.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

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
import run_p3_direct_mlp as DIRECT  # noqa: E402
from studies.common.metrics import (  # noqa: E402
    check_status,
    param_relative_errors,
    quantile_relative_error,
)
from studies.common.sample import generate_sample  # noqa: E402


RUN_ID = "training_domain_width_v1"
MODEL_SEED = 42
TRAIN_SEED_NAMESPACE = "study01_nrmc_v1"
TEST_SEED_NAMESPACE = "research04_generalization_v1"
ETA = 1000.0
GAMMA_RATIOS = tuple(float(x) for x in STUDY_CFG.GAMMA_OVER_ETA_GRID)
N_VALUES = tuple(int(x) for x in STUDY_CFG.N_GRID)
TEST_BETAS = tuple(round(0.75 + 0.25 * i, 2) for i in range(21))
TEST_REPEATS = 300
R_LEVELS = (0.90, 0.95, 0.99)
FIXED_TOTAL_PER_N = 12_000
FIXED_DENSITY_REPEATS = 300

DOMAIN_SPECS = {
    "narrow_2.0_3.0": {
        "label": "[2.0, 3.0]",
        "betas": (2.0, 2.5, 3.0),
    },
    "medium_1.5_3.5": {
        "label": "[1.5, 3.5]",
        "betas": (1.5, 2.0, 2.5, 3.0, 3.5),
    },
    "wide_1.5_5.0": {
        "label": "[1.5, 5.0]",
        "betas": tuple(float(x) for x in STUDY_CFG.BETA_GRID),
    },
}

OUT_DIR = RESEARCH_ROOT / "artifacts" / RUN_ID
SMOKE_DIR = RESEARCH_ROOT / "artifacts" / "smoke" / RUN_ID
MODEL_DIR = OUT_DIR / "models"
BLOCK_DIR = OUT_DIR / "evaluation_blocks"
RESULTS_PATH = OUT_DIR / "per_sample_results.csv.gz"
MANIFEST_PATH = OUT_DIR / "manifest.json"
RUN_LOG_PATH = OUT_DIR / "run_log.txt"
SOURCE_FORMAL_DIR = (
    RESEARCH_ROOT / "artifacts" / "study01_aligned_generalization_v1"
)

RESULT_COLUMNS = [
    "budget_policy", "domain_id", "domain_label", "train_beta_min",
    "train_beta_max", "train_beta_width", "train_repeats_per_cell",
    "n_train_per_n", "beta", "eta", "gamma", "gamma_over_eta", "n",
    "repeat_id", "signed_distance_to_domain", "ood_distance",
    "beta_hat", "eta_hat", "gamma_hat", "status", "loss_primary",
    "beta_rel_error", "eta_rel_error", "gamma_rel_error",
    "x0.90_rel_error", "x0.95_rel_error", "x0.99_rel_error",
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def log(message: str, path: Path) -> None:
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


def repeats_for(domain_id: str, policy: str) -> int:
    n_cells = len(DOMAIN_SPECS[domain_id]["betas"]) * len(GAMMA_RATIOS)
    if policy == "fixed_total":
        if FIXED_TOTAL_PER_N % n_cells:
            raise RuntimeError(f"fixed total is not divisible for {domain_id}")
        return FIXED_TOTAL_PER_N // n_cells
    if policy == "fixed_density":
        return FIXED_DENSITY_REPEATS
    raise ValueError(policy)


def scenario_specs() -> list[dict]:
    rows = []
    for policy in ("fixed_total", "fixed_density"):
        for domain_id, domain in DOMAIN_SPECS.items():
            repeats = repeats_for(domain_id, policy)
            rows.append(
                {
                    "budget_policy": policy,
                    "domain_id": domain_id,
                    "domain_label": domain["label"],
                    "betas": tuple(domain["betas"]),
                    "train_beta_min": min(domain["betas"]),
                    "train_beta_max": max(domain["betas"]),
                    "train_beta_width": max(domain["betas"]) - min(domain["betas"]),
                    "train_repeats_per_cell": repeats,
                    "n_train_per_n": len(domain["betas"]) * len(GAMMA_RATIOS) * repeats,
                }
            )
    return rows


def unique_model_key(spec: dict) -> str:
    return f"{spec['domain_id']}__reps{spec['train_repeats_per_cell']}"


def training_arrays(spec: dict, n_value: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    repeats = int(spec["train_repeats_per_cell"])
    count = int(spec["n_train_per_n"])
    raw = np.empty((count, n_value), dtype=np.float64)
    params = np.empty((count, 3), dtype=np.float64)
    index = 0
    for beta in spec["betas"]:
        for ratio in GAMMA_RATIOS:
            gamma = ratio * ETA
            for repeat_id in range(repeats):
                raw[index] = generate_sample(
                    beta, ETA, gamma, n_value, repeat_id,
                    seed=TRAIN_SEED_NAMESPACE,
                )
                params[index] = [beta, ETA, gamma]
                index += 1
    if index != count:
        raise RuntimeError(f"training row count {index} != {count}")
    means = raw.mean(axis=1)
    normalized = raw / means[:, None]
    if not np.allclose(normalized.mean(axis=1), 1.0, atol=1e-12):
        raise RuntimeError("mean normalization failed")
    return normalized, params, means


def model_paths(model_root: Path, key: str, n_value: int) -> tuple[Path, Path]:
    root = model_root / key
    return root / f"direct_n{n_value}_seed42.pt", root / f"training_n{n_value}.json"


def load_model(path: Path, n_value: int) -> tuple[torch.nn.Module, dict]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    model = DIRECT.DirectMLP(input_dim=n_value)
    model.load_state_dict(payload["state_dict"])
    return model, payload["info"]


def train_or_load_model(
    spec: dict, n_value: int, model_root: Path, log_path: Path,
    smoke: bool,
) -> tuple[torch.nn.Module, dict, dict]:
    key = unique_model_key(spec)
    model_path, meta_path = model_paths(model_root, key, n_value)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if model_path.is_file() and meta_path.is_file():
        model, info = load_model(model_path, n_value)
        return model, info, json.loads(meta_path.read_text(encoding="utf-8"))

    formal_wide = (
        spec["domain_id"] == "wide_1.5_5.0"
        and spec["train_repeats_per_cell"] == 300
        and not smoke
    )
    if formal_wide:
        source_model = SOURCE_FORMAL_DIR / "models" / f"direct_n{n_value}_seed42.pt"
        source_meta = SOURCE_FORMAL_DIR / "models" / f"training_n{n_value}_seed42.json"
        if not source_model.is_file() or not source_meta.is_file():
            raise FileNotFoundError("formal wide-domain Direct-P model is missing")
        model, info = load_model(source_model, n_value)
        meta = json.loads(source_meta.read_text(encoding="utf-8"))
        meta.update(
            {
                "domain_id": spec["domain_id"],
                "domain_label": spec["domain_label"],
                "budget_equivalence": ["fixed_total", "fixed_density"],
                "source_model": str(source_model.relative_to(PROJECT_ROOT)),
            }
        )
        torch.save({"state_dict": model.state_dict(), "info": info}, model_path)
        meta_path.write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        log(f"MODEL_REUSED key={key} n={n_value}", log_path)
        return model, info, meta

    started = time.perf_counter()
    normalized, params, means = training_arrays(spec, n_value)
    max_iter = 8 if smoke else int(STUDY_CFG.MLP_MAX_ITER)
    patience = 3 if smoke else int(STUDY_CFG.MLP_N_ITER_NO_CHANGE)
    model, info = DIRECT.train_direct_mlp(
        normalized, params, means, MODEL_SEED,
        max_iter=max_iter, patience=patience,
    )
    elapsed = time.perf_counter() - started
    torch.save({"state_dict": model.state_dict(), "info": info}, model_path)
    meta = {
        "domain_id": spec["domain_id"],
        "domain_label": spec["domain_label"],
        "betas": list(spec["betas"]),
        "train_repeats_per_cell": int(spec["train_repeats_per_cell"]),
        "n_train": int(spec["n_train_per_n"]),
        "n": int(n_value),
        "seed": MODEL_SEED,
        "training_seed_namespace": TRAIN_SEED_NAMESPACE,
        "max_iter": max_iter,
        "patience": patience,
        "n_iter": int(info["n_iter"]),
        "best_val_loss": float(info["best_val_loss"]),
        "seconds": elapsed,
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(
        f"MODEL_TRAINED key={key} n={n_value} rows={len(normalized)} "
        f"iter={info['n_iter']} seconds={elapsed:.2f}",
        log_path,
    )
    return model, info, meta


def signed_distance(beta: float, low: float, high: float) -> float:
    if beta < low:
        return beta - low
    if beta > high:
        return beta - high
    return 0.0


def test_arrays(n_value: int, repeats: int) -> tuple[pd.DataFrame, np.ndarray, np.ndarray]:
    rows = []
    raw = np.empty((len(TEST_BETAS) * len(GAMMA_RATIOS) * repeats, n_value))
    index = 0
    for beta in TEST_BETAS:
        for ratio in GAMMA_RATIOS:
            gamma = ratio * ETA
            for repeat_id in range(repeats):
                sample = generate_sample(
                    beta, ETA, gamma, n_value, repeat_id,
                    seed=TEST_SEED_NAMESPACE,
                )
                raw[index] = sample
                rows.append(
                    {
                        "beta": beta,
                        "eta": ETA,
                        "gamma": gamma,
                        "gamma_over_eta": ratio,
                        "n": n_value,
                        "repeat_id": repeat_id,
                        "sample_min": float(np.min(sample)),
                    }
                )
                index += 1
    keys = pd.DataFrame(rows)
    means = raw.mean(axis=1)
    return keys, raw / means[:, None], means


def evaluate_scenario(
    spec: dict, keys: pd.DataFrame, normalized: np.ndarray, means: np.ndarray,
    model: torch.nn.Module, info: dict, failure_penalty: float,
) -> pd.DataFrame:
    predictions = DIRECT.predict_direct_mlp(model, info, normalized, means)
    output = keys.copy()
    output.insert(0, "n_train_per_n", int(spec["n_train_per_n"]))
    output.insert(0, "train_repeats_per_cell", int(spec["train_repeats_per_cell"]))
    output.insert(0, "train_beta_width", float(spec["train_beta_width"]))
    output.insert(0, "train_beta_max", float(spec["train_beta_max"]))
    output.insert(0, "train_beta_min", float(spec["train_beta_min"]))
    output.insert(0, "domain_label", spec["domain_label"])
    output.insert(0, "domain_id", spec["domain_id"])
    output.insert(0, "budget_policy", spec["budget_policy"])
    distances = [
        signed_distance(beta, spec["train_beta_min"], spec["train_beta_max"])
        for beta in output["beta"].to_numpy(float)
    ]
    output["signed_distance_to_domain"] = distances
    output["ood_distance"] = np.abs(output["signed_distance_to_domain"])
    output["beta_hat"] = predictions[:, 0]
    output["eta_hat"] = predictions[:, 1]
    output["gamma_hat"] = predictions[:, 2]

    status = []
    losses = []
    errors = {name: [] for name in (
        "beta_rel_error", "eta_rel_error", "gamma_rel_error",
        "x0.90_rel_error", "x0.95_rel_error", "x0.99_rel_error",
    )}
    for row in output.itertuples(index=False):
        valid = check_status(
            float(row.beta_hat), float(row.eta_hat), float(row.gamma_hat),
            float(row.beta), float(row.eta), float(row.gamma),
            converged=True, sample_min=float(row.sample_min),
        )
        if float(row.gamma_hat) < 0:
            valid = "failure"
        status.append(valid)
        if valid == "success":
            rel = param_relative_errors(
                row.beta_hat, row.eta_hat, row.gamma_hat,
                row.beta, row.eta, row.gamma,
            )
            loss = rel["beta"] ** 2 + rel["eta"] ** 2 + rel["gamma"] ** 2
            losses.append(loss)
            errors["beta_rel_error"].append(rel["beta"])
            errors["eta_rel_error"].append(rel["eta"])
            errors["gamma_rel_error"].append(rel["gamma"])
            for level in R_LEVELS:
                errors[f"x{level:.2f}_rel_error"].append(
                    quantile_relative_error(
                        row.beta_hat, row.eta_hat, row.gamma_hat,
                        row.beta, row.eta, row.gamma, level,
                    )
                )
        else:
            losses.append(failure_penalty)
            for name in errors:
                errors[name].append(np.nan)
    output["status"] = status
    output["loss_primary"] = losses
    for name, values in errors.items():
        output[name] = values
    output = output.drop(columns=["sample_min"])
    return output[RESULT_COLUMNS]


def block_path(root: Path, spec: dict, n_value: int) -> Path:
    safe = f"{spec['budget_policy']}__{spec['domain_id']}__n{n_value}.csv.gz"
    return root / "evaluation_blocks" / safe


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    smoke = bool(args.smoke)
    root = SMOKE_DIR if smoke else OUT_DIR
    model_root = root / "models"
    log_path = root / "run_log.txt"
    repeats = 20 if smoke else TEST_REPEATS
    specs = scenario_specs()
    if smoke:
        for spec in specs:
            spec["train_repeats_per_cell"] = min(
                int(spec["train_repeats_per_cell"]), 8
            )
            spec["n_train_per_n"] = (
                len(spec["betas"])
                * len(GAMMA_RATIOS)
                * int(spec["train_repeats_per_cell"])
            )
    root.mkdir(parents=True, exist_ok=True)

    formal_manifest = json.loads(
        (SOURCE_FORMAL_DIR / "manifest.json").read_text(encoding="utf-8")
    )
    failure_penalty = max(
        float(value["failure_penalty"])
        for value in formal_manifest["model_training"].values()
    )
    model_cache: dict[tuple[str, int], tuple[torch.nn.Module, dict, dict]] = {}
    model_meta = {}
    for spec in specs:
        key = unique_model_key(spec)
        for n_value in N_VALUES:
            cache_key = (key, n_value)
            if cache_key not in model_cache:
                model_cache[cache_key] = train_or_load_model(
                    spec, n_value, model_root, log_path, smoke,
                )
                model_meta[f"{key}__n{n_value}"] = model_cache[cache_key][2]

    block_paths = []
    for n_value in N_VALUES:
        keys, normalized, means = test_arrays(n_value, repeats)
        for spec in specs:
            path = block_path(root, spec, n_value)
            path.parent.mkdir(parents=True, exist_ok=True)
            model, info, _ = model_cache[(unique_model_key(spec), n_value)]
            frame = evaluate_scenario(
                spec, keys, normalized, means, model, info, failure_penalty,
            )
            frame.to_csv(path, index=False, compression="gzip")
            block_paths.append(path)
            log(
                f"EVALUATED policy={spec['budget_policy']} "
                f"domain={spec['domain_id']} n={n_value} rows={len(frame)}",
                log_path,
            )

    combined = pd.concat(
        [pd.read_csv(path, low_memory=False) for path in block_paths],
        ignore_index=True,
    )
    combined.to_csv(
        root / "per_sample_results.csv.gz", index=False, compression="gzip"
    )
    expected = len(specs) * len(TEST_BETAS) * len(GAMMA_RATIOS) * len(N_VALUES) * repeats
    if len(combined) != expected:
        raise RuntimeError(f"result rows {len(combined)} != {expected}")

    manifest = {
        "run_id": RUN_ID,
        "status": "smoke_complete" if smoke else "complete",
        "generated_at": utc_now(),
        "git": {
            "commit": git_value("rev-parse", "HEAD"),
            "branch": git_value("branch", "--show-current"),
            "dirty": bool(git_value("status", "--porcelain")),
        },
        "question": (
            "How do training beta-domain width and training-data budget alter "
            "Direct-P common-core accuracy and OOD degradation?"
        ),
        "domain_specs": {
            key: {
                "label": value["label"],
                "betas": list(value["betas"]),
                "min": min(value["betas"]),
                "max": max(value["betas"]),
            }
            for key, value in DOMAIN_SPECS.items()
        },
        "budget_policies": {
            "fixed_total": {
                "samples_per_n": FIXED_TOTAL_PER_N,
                "meaning": "constant total training samples; local density falls as domain widens",
            },
            "fixed_density": {
                "repeats_per_beta_gamma_cell": FIXED_DENSITY_REPEATS,
                "meaning": "constant local sampling density; total samples grow as domain widens",
            },
        },
        "scenarios": [
            {key: value for key, value in spec.items() if key != "betas"}
            | {"betas": list(spec["betas"])}
            for spec in specs
        ],
        "shared_controls": {
            "eta": ETA,
            "gamma_over_eta": list(GAMMA_RATIOS),
            "n": list(N_VALUES),
            "model_seed": MODEL_SEED,
            "architecture": list(STUDY_CFG.MLP_HIDDEN_LAYERS),
            "max_iter": 8 if smoke else int(STUDY_CFG.MLP_MAX_ITER),
            "patience": 3 if smoke else int(STUDY_CFG.MLP_N_ITER_NO_CHANGE),
            "input": "sorted X / sample mean",
            "target": "three decoded parameters with J1-compatible P loss",
            "training_seed_namespace": TRAIN_SEED_NAMESPACE,
        },
        "test_design": {
            "beta": list(TEST_BETAS),
            "gamma_over_eta": list(GAMMA_RATIOS),
            "n": list(N_VALUES),
            "repeats": repeats,
            "seed_namespace": TEST_SEED_NAMESPACE,
            "shared_with": "study01_aligned_generalization_v1",
        },
        "failure_penalty": failure_penalty,
        "model_training": model_meta,
        "validation": {
            "n_rows": int(len(combined)),
            "expected_rows": expected,
            "failure_counts": {
                f"{policy}|{domain}": int((group["status"] != "success").sum())
                for (policy, domain), group in combined.groupby(
                    ["budget_policy", "domain_id"], sort=True
                )
            },
        },
        "code_sha256": sha256_file(HERE),
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    checksum_paths = [root / "manifest.json", root / "per_sample_results.csv.gz"]
    checksum_paths.extend(block_paths)
    lines = [
        f"{sha256_file(path)}  {path.relative_to(root).as_posix()}"
        for path in checksum_paths
    ]
    (root / "SHA256SUMS.txt").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(
        f"DOMAIN_WIDTH_COMPLETE smoke={smoke} rows={len(combined)} "
        f"models={len(model_cache)}"
    )


if __name__ == "__main__":
    main()
