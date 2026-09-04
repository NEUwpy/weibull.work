"""Run the frozen Direct-P beta training-domain width/location experiment."""

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
STUDY_CODE = PROJECT_ROOT / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
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


RUN_ID = "training_domain_width_location_v1"
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


def beta_grid(low: float, high: float) -> tuple[float, ...]:
    count = int(round((high - low) / 0.5))
    return tuple(round(low + 0.5 * i, 2) for i in range(count + 1))


DOMAIN_SPECS = {
    "center_w1_2.5_3.5": {"label": "[2.5, 3.5]", "betas": beta_grid(2.5, 3.5)},
    "center_w2_2.0_4.0": {"label": "[2.0, 4.0]", "betas": beta_grid(2.0, 4.0)},
    "center_w4_1.0_5.0": {"label": "[1.0, 5.0]", "betas": beta_grid(1.0, 5.0)},
    "center_w5_0.5_5.5": {"label": "[0.5, 5.5]", "betas": beta_grid(0.5, 5.5)},
    "location_low_1.5_2.5": {"label": "[1.5, 2.5]", "betas": beta_grid(1.5, 2.5)},
    "location_high_3.5_4.5": {"label": "[3.5, 4.5]", "betas": beta_grid(3.5, 4.5)},
}
WIDTH_ORDER = (
    "center_w1_2.5_3.5", "center_w2_2.0_4.0",
    "center_w4_1.0_5.0", "center_w5_0.5_5.5",
)
LOCATION_ORDER = (
    "location_low_1.5_2.5", "center_w1_2.5_3.5", "location_high_3.5_4.5",
)

OUT_DIR = RESEARCH_ROOT / "artifacts" / RUN_ID
SMOKE_DIR = RESEARCH_ROOT / "artifacts" / "smoke" / RUN_ID
SOURCE_MANIFEST = RESEARCH_ROOT / "artifacts" / "study01_aligned_generalization_v1" / "manifest.json"

RESULT_COLUMNS = [
    "budget_policy", "domain_id", "domain_label", "train_beta_min",
    "train_beta_max", "train_beta_width", "train_repeats_min",
    "train_repeats_max", "n_train_per_n", "beta", "eta", "gamma",
    "gamma_over_eta", "n", "repeat_id", "signed_distance_to_domain",
    "ood_distance", "beta_hat", "eta_hat", "gamma_hat", "status",
    "loss_primary", "beta_rel_error", "eta_rel_error", "gamma_rel_error",
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
            ["git", *args], cwd=PROJECT_ROOT, text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        return "unknown"


def balanced_cell_counts(domain_id: str, policy: str) -> dict[tuple[float, float], int]:
    cells = [
        (float(beta), float(ratio))
        for beta in DOMAIN_SPECS[domain_id]["betas"]
        for ratio in GAMMA_RATIOS
    ]
    if policy == "fixed_density":
        return {cell: FIXED_DENSITY_REPEATS for cell in cells}
    if policy != "fixed_total":
        raise ValueError(policy)
    base, remainder = divmod(FIXED_TOTAL_PER_N, len(cells))
    return {cell: base + int(index < remainder) for index, cell in enumerate(cells)}


def scenario_specs(smoke: bool = False) -> list[dict]:
    rows = []
    for policy in ("fixed_total", "fixed_density"):
        for domain_id, domain in DOMAIN_SPECS.items():
            counts = balanced_cell_counts(domain_id, policy)
            if smoke:
                counts = {cell: min(value, 8) for cell, value in counts.items()}
            values = list(counts.values())
            rows.append({
                "budget_policy": policy,
                "domain_id": domain_id,
                "domain_label": domain["label"],
                "betas": tuple(domain["betas"]),
                "train_beta_min": min(domain["betas"]),
                "train_beta_max": max(domain["betas"]),
                "train_beta_width": max(domain["betas"]) - min(domain["betas"]),
                "train_repeats_min": min(values),
                "train_repeats_max": max(values),
                "n_train_per_n": sum(values),
                "cell_counts": counts,
            })
    return rows


def unique_model_key(spec: dict) -> str:
    return f"{spec['budget_policy']}__{spec['domain_id']}"


def training_arrays(spec: dict, n_value: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    count = int(spec["n_train_per_n"])
    raw = np.empty((count, n_value), dtype=np.float64)
    params = np.empty((count, 3), dtype=np.float64)
    index = 0
    for beta in spec["betas"]:
        for ratio in GAMMA_RATIOS:
            repeats = int(spec["cell_counts"][(float(beta), float(ratio))])
            gamma = ratio * ETA
            for repeat_id in range(repeats):
                raw[index] = generate_sample(
                    beta, ETA, gamma, n_value, repeat_id, seed=TRAIN_SEED_NAMESPACE
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


def model_paths(root: Path, spec: dict, n_value: int) -> tuple[Path, Path]:
    model_root = root / "models" / unique_model_key(spec)
    return model_root / f"direct_n{n_value}_seed42.pt", model_root / f"training_n{n_value}.json"


def load_model(path: Path, n_value: int) -> tuple[torch.nn.Module, dict]:
    payload = torch.load(path, map_location="cpu", weights_only=False)
    model = DIRECT.DirectMLP(input_dim=n_value)
    model.load_state_dict(payload["state_dict"])
    return model, payload["info"]


def train_or_load_model(spec: dict, n_value: int, root: Path, smoke: bool) -> tuple[torch.nn.Module, dict, dict]:
    model_path, meta_path = model_paths(root, spec, n_value)
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if model_path.is_file() and meta_path.is_file():
        model, info = load_model(model_path, n_value)
        return model, info, json.loads(meta_path.read_text(encoding="utf-8"))
    started = time.perf_counter()
    normalized, params, means = training_arrays(spec, n_value)
    max_iter = 8 if smoke else int(STUDY_CFG.MLP_MAX_ITER)
    patience = 3 if smoke else int(STUDY_CFG.MLP_N_ITER_NO_CHANGE)
    model, info = DIRECT.train_direct_mlp(
        normalized, params, means, MODEL_SEED, max_iter=max_iter, patience=patience
    )
    elapsed = time.perf_counter() - started
    torch.save({"state_dict": model.state_dict(), "info": info}, model_path)
    allocation = {
        f"beta={beta:g}|gamma_over_eta={ratio:g}": int(value)
        for (beta, ratio), value in spec["cell_counts"].items()
    }
    meta = {
        "budget_policy": spec["budget_policy"], "domain_id": spec["domain_id"],
        "domain_label": spec["domain_label"], "betas": list(spec["betas"]),
        "cell_allocation": allocation, "train_repeats_min": spec["train_repeats_min"],
        "train_repeats_max": spec["train_repeats_max"], "n_train": len(normalized),
        "n": n_value, "seed": MODEL_SEED,
        "training_seed_namespace": TRAIN_SEED_NAMESPACE, "max_iter": max_iter,
        "patience": patience, "n_iter": int(info["n_iter"]),
        "best_val_loss": float(info["best_val_loss"]), "seconds": elapsed,
    }
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    log(
        f"MODEL_TRAINED key={unique_model_key(spec)} n={n_value} rows={len(normalized)} "
        f"iter={info['n_iter']} seconds={elapsed:.2f}", root / "run_log.txt"
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
                    beta, ETA, gamma, n_value, repeat_id, seed=TEST_SEED_NAMESPACE
                )
                raw[index] = sample
                rows.append({
                    "beta": beta, "eta": ETA, "gamma": gamma,
                    "gamma_over_eta": ratio, "n": n_value,
                    "repeat_id": repeat_id, "sample_min": float(np.min(sample)),
                })
                index += 1
    keys = pd.DataFrame(rows)
    if keys.duplicated(["beta", "gamma_over_eta", "n", "repeat_id"]).any():
        raise RuntimeError("duplicate shared test key")
    means = raw.mean(axis=1)
    normalized = raw / means[:, None]
    if not np.allclose(normalized.mean(axis=1), 1.0, atol=1e-12):
        raise RuntimeError("test mean normalization failed")
    return keys, normalized, means


def evaluate_scenario(spec: dict, keys: pd.DataFrame, normalized: np.ndarray,
                      means: np.ndarray, model: torch.nn.Module, info: dict,
                      failure_penalty: float) -> pd.DataFrame:
    predictions = DIRECT.predict_direct_mlp(model, info, normalized, means)
    output = keys.copy()
    for name in (
        "n_train_per_n", "train_repeats_max", "train_repeats_min",
        "train_beta_width", "train_beta_max", "train_beta_min",
        "domain_label", "domain_id", "budget_policy",
    ):
        output.insert(0, name, spec[name])
    output["signed_distance_to_domain"] = [
        signed_distance(beta, spec["train_beta_min"], spec["train_beta_max"])
        for beta in output["beta"].to_numpy(float)
    ]
    output["ood_distance"] = np.abs(output["signed_distance_to_domain"])
    output[["beta_hat", "eta_hat", "gamma_hat"]] = predictions
    statuses, losses = [], []
    errors = {name: [] for name in (
        "beta_rel_error", "eta_rel_error", "gamma_rel_error",
        "x0.90_rel_error", "x0.95_rel_error", "x0.99_rel_error",
    )}
    for row in output.itertuples(index=False):
        status = check_status(
            float(row.beta_hat), float(row.eta_hat), float(row.gamma_hat),
            float(row.beta), float(row.eta), float(row.gamma), converged=True,
            sample_min=float(row.sample_min),
        )
        if float(row.gamma_hat) < 0:
            status = "failure"
        statuses.append(status)
        if status == "success":
            rel = param_relative_errors(
                row.beta_hat, row.eta_hat, row.gamma_hat, row.beta, row.eta, row.gamma
            )
            losses.append(rel["beta"] ** 2 + rel["eta"] ** 2 + rel["gamma"] ** 2)
            for parameter in ("beta", "eta", "gamma"):
                errors[f"{parameter}_rel_error"].append(rel[parameter])
            for level in R_LEVELS:
                errors[f"x{level:.2f}_rel_error"].append(quantile_relative_error(
                    row.beta_hat, row.eta_hat, row.gamma_hat,
                    row.beta, row.eta, row.gamma, level,
                ))
        else:
            losses.append(failure_penalty)
            for name in errors:
                errors[name].append(np.nan)
    output["status"], output["loss_primary"] = statuses, losses
    for name, values in errors.items():
        output[name] = values
    return output.drop(columns=["sample_min"])[RESULT_COLUMNS]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    smoke = bool(args.smoke)
    root = SMOKE_DIR if smoke else OUT_DIR
    root.mkdir(parents=True, exist_ok=True)
    specs = scenario_specs(smoke=smoke)
    repeats = 20 if smoke else TEST_REPEATS
    source_manifest = json.loads(SOURCE_MANIFEST.read_text(encoding="utf-8"))
    penalty_by_n = {
        int(n): float(meta["failure_penalty"])
        for n, meta in source_manifest["model_training"].items()
    }
    failure_penalty = max(penalty_by_n.values())

    models, model_meta = {}, {}
    for spec in specs:
        for n_value in N_VALUES:
            key = (spec["budget_policy"], spec["domain_id"], n_value)
            models[key] = train_or_load_model(spec, n_value, root, smoke)
            model_meta[f"{spec['budget_policy']}__{spec['domain_id']}__n{n_value}"] = models[key][2]

    block_paths = []
    for n_value in N_VALUES:
        keys, normalized, means = test_arrays(n_value, repeats)
        for spec in specs:
            path = root / "evaluation_blocks" / f"{spec['budget_policy']}__{spec['domain_id']}__n{n_value}.csv.gz"
            path.parent.mkdir(parents=True, exist_ok=True)
            model, info, _ = models[(spec["budget_policy"], spec["domain_id"], n_value)]
            frame = evaluate_scenario(
                spec, keys, normalized, means, model, info, failure_penalty
            )
            frame.to_csv(path, index=False, compression="gzip")
            block_paths.append(path)
            log(f"EVALUATED policy={spec['budget_policy']} domain={spec['domain_id']} n={n_value} rows={len(frame)}", root / "run_log.txt")

    combined = pd.concat([pd.read_csv(path, low_memory=False) for path in block_paths], ignore_index=True)
    results_path = root / "per_sample_results.csv.gz"
    combined.to_csv(results_path, index=False, compression="gzip")
    expected = len(specs) * len(TEST_BETAS) * len(GAMMA_RATIOS) * len(N_VALUES) * repeats
    if len(combined) != expected:
        raise RuntimeError(f"result rows {len(combined)} != {expected}")
    formal_totals = {
        spec["domain_id"]: sum(balanced_cell_counts(spec["domain_id"], "fixed_total").values())
        for spec in specs if spec["budget_policy"] == "fixed_total"
    }
    if not smoke and set(formal_totals.values()) != {FIXED_TOTAL_PER_N}:
        raise RuntimeError("fixed-total allocation is not exactly 12,000")

    manifest = {
        "run_id": RUN_ID, "status": "smoke_complete" if smoke else "complete",
        "generated_at": utc_now(),
        "git": {"commit": git_value("rev-parse", "HEAD"),
                "branch": git_value("branch", "--show-current"),
                "dirty": bool(git_value("status", "--porcelain"))},
        "question": "Separate Direct-P beta training-domain width and location effects.",
        "domain_specs": {key: {"label": value["label"], "betas": list(value["betas"]),
                                      "min": min(value["betas"]), "max": max(value["betas"])}
                         for key, value in DOMAIN_SPECS.items()},
        "effect_families": {"width": list(WIDTH_ORDER), "location": list(LOCATION_ORDER)},
        "budget_policies": {
            "fixed_total": {"samples_per_n": FIXED_TOTAL_PER_N,
                            "allocation": "deterministic beta-major balanced allocation; cell counts differ by at most one"},
            "fixed_density": {"repeats_per_beta_gamma_cell": FIXED_DENSITY_REPEATS},
        },
        "scenarios": [{key: value for key, value in spec.items() if key not in {"betas", "cell_counts"}}
                      | {"betas": list(spec["betas"]),
                         "cell_allocation": {f"beta={b:g}|gamma_over_eta={r:g}": int(c)
                                             for (b, r), c in spec["cell_counts"].items()}}
                      for spec in specs],
        "shared_controls": {"eta": ETA, "gamma_over_eta": list(GAMMA_RATIOS),
                            "n": list(N_VALUES), "model_seed": MODEL_SEED,
                            "architecture": list(STUDY_CFG.MLP_HIDDEN_LAYERS),
                            "max_iter": 8 if smoke else int(STUDY_CFG.MLP_MAX_ITER),
                            "patience": 3 if smoke else int(STUDY_CFG.MLP_N_ITER_NO_CHANGE),
                            "input": "sorted X / sample mean",
                            "target": "three decoded parameters with J1-compatible P loss",
                            "training_seed_namespace": TRAIN_SEED_NAMESPACE},
        "test_design": {"beta": list(TEST_BETAS), "gamma_over_eta": list(GAMMA_RATIOS),
                        "n": list(N_VALUES), "repeats": repeats,
                        "seed_namespace": TEST_SEED_NAMESPACE,
                        "shared_with": "study01_aligned_generalization_v1",
                        "widest_domain_has_left_ood_test_points": False},
        "failure_penalty": failure_penalty,
        "failure_penalty_contract": {"source": str(SOURCE_MANIFEST.relative_to(PROJECT_ROOT)),
                                     "source_values_by_n": penalty_by_n,
                                     "rule": "maximum train-derived penalty across n, frozen for every scenario"},
        "model_training": model_meta,
        "validation": {"n_rows": len(combined), "expected_rows": expected,
                       "n_models": len(models), "expected_models": 48,
                       "failure_counts": {f"{p}|{d}": int((g["status"] != "success").sum())
                                          for (p, d), g in combined.groupby(["budget_policy", "domain_id"], sort=True)}},
        "code_sha256": sha256_file(HERE),
    }
    manifest_path = root / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    checks = [manifest_path, results_path, *block_paths]
    (root / "SHA256SUMS.txt").write_text(
        "\n".join(f"{sha256_file(path)}  {path.relative_to(root).as_posix()}" for path in checks) + "\n",
        encoding="utf-8",
    )
    print(f"DOMAIN_WIDTH_LOCATION_COMPLETE smoke={smoke} rows={len(combined)} models={len(models)}")


if __name__ == "__main__":
    main()
