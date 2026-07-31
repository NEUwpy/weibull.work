"""E1 minimal training-sensitivity experiment.

Answers A5 (training-data size), A6 (parameter distribution), A13 (range-clipped oracle).
Reuses study02a.models / study02a.training (non-formal utilities) and
python/studies/common/sample. Does NOT call formal scheduler, lease, authority,
unseal, hash-chain, capsule, or attack machinery. Formal test namespaces are
permanently sealed and never touched.

Usage:
  python E1-training-sensitivity.py --config CONFIG [--dry-run] [--mode MODE]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from scipy.stats import qmc

# --- Project imports (must run from code/ directory or add to PYTHONPATH) ---
_SCRIPT_DIR = Path(__file__).resolve().parent
_STUDY_ROOT = _SCRIPT_DIR.parent
_CODE_DIR = _SCRIPT_DIR
sys.path.insert(0, str(_CODE_DIR))
sys.path.insert(0, str(Path("python")))

from study02a.models import build_mlp, trainable_parameter_count
from study02a.training import compute_loss, seed_everything
from study02a.representations import anchor_sample, encode_targets

# --- Constants ---
FIT_STATE_FILENAME = "fit_state.json"
OUTPUT_FILENAME = "results.json"  # per-arm summary
CHECKPOINT_FILENAME = "checkpoint.pt"

# Default output root (config can override)
DEFAULT_OUTPUT_ROOT = "C:/weibull-runs/study02/lean/E1-training-sensitivity"


# ---------------------------------------------------------------------------
# Data generation (Sobol, no formal pipeline)
# ---------------------------------------------------------------------------

def _sobol_params(
    n_points: int, seed: int, *, beta_range, eta_range, rho_range
) -> np.ndarray:
    """Generate n_points (beta, eta, rho) via scrambled Sobol."""
    sampler = qmc.Sobol(d=3, scramble=True, seed=seed)
    samples = sampler.random(n_points)
    beta = np.exp(np.log(beta_range[0]) + samples[:, 0] * (np.log(beta_range[1]) - np.log(beta_range[0])))
    eta = np.exp(np.log(eta_range[0]) + samples[:, 1] * (np.log(eta_range[1]) - np.log(eta_range[0])))
    rho = rho_range[0] + samples[:, 2] * (rho_range[1] - rho_range[0])
    gamma = rho * eta
    return np.column_stack([beta, eta, gamma])


def _weibull_sample(beta: float, eta: float, gamma: float, n: int, seed: int) -> np.ndarray:
    """Generate one MC sample of size n from 3p Weibull."""
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 1, n)
    return gamma + eta * (-np.log(1 - u)) ** (1.0 / beta)


def generate_pool(config: dict, *, prefix_size: int | None = None) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate (params, samples, targets) for the training pool."""
    pool_cfg = config["training_pool"]
    core = pool_cfg["core_continuous"]
    n_points = prefix_size if prefix_size else pool_cfg["max_rows"]
    seed_design = int(pool_cfg["seed_design"])
    seed_sample = int(pool_cfg["seed_sample"])
    n = config["baseline"]["sample_size"]

    params = _sobol_params(
        n_points, seed_design,
        beta_range=(core["beta"]["min"], core["beta"]["max"]),
        eta_range=(core["eta"]["min"], core["eta"]["max"]),
        rho_range=(core["rho"]["min"], core["rho"]["max"]),
    )
    # Generate samples
    samples = np.zeros((n_points, n))
    targets_raw = np.zeros((n_points, 3))
    for i in range(n_points):
        beta, eta, gamma = float(params[i, 0]), float(params[i, 1]), float(params[i, 2])
        s = _weibull_sample(beta, eta, gamma, n, seed_sample + i)
        samples[i] = np.sort(s)
        targets_raw[i] = [beta, eta, gamma]
    return params, samples, targets_raw


def generate_role_data(config: dict, role: str) -> tuple[np.ndarray, np.ndarray]:
    """Generate (samples, targets) for validation or confirmation."""
    role_cfg = config.get(role, {})
    n_points = int(role_cfg["param_points"])
    n = int(role_cfg["n"])
    repeats = int(role_cfg["repeats_per_point"])
    design_seed = int(role_cfg["design_seed"])
    sample_seed = int(role_cfg["sample_seed"])
    total = n_points * repeats

    params = _sobol_params(
        n_points, design_seed,
        beta_range=(config["training_pool"]["core_continuous"]["beta"]["min"],
                     config["training_pool"]["core_continuous"]["beta"]["max"]),
        eta_range=(config["training_pool"]["core_continuous"]["eta"]["min"],
                    config["training_pool"]["core_continuous"]["eta"]["max"]),
        rho_range=(config["training_pool"]["core_continuous"]["rho"]["min"],
                    config["training_pool"]["core_continuous"]["rho"]["max"]),
    )

    samples = np.zeros((total, n))
    targets_raw = np.zeros((total, 3))
    idx = 0
    for pt in range(n_points):
        beta, eta, gamma = float(params[pt, 0]), float(params[pt, 1]), float(params[pt, 2])
        for rep in range(repeats):
            s = _weibull_sample(beta, eta, gamma, n, sample_seed + pt * repeats + rep)
            samples[idx] = np.sort(s)
            targets_raw[idx] = [beta, eta, gamma]
            idx += 1
    return samples, targets_raw


# ---------------------------------------------------------------------------
# Equivariant preprocessing (V route)
# ---------------------------------------------------------------------------

def preprocess_v_route(samples: np.ndarray) -> np.ndarray:
    """V route: sorted normalized sample values z_i = (x_i - min(x)) / (Q75 - Q25).

    Fallback to range if IQR=0. Returns shape (N, n).
    """
    n_rows, n = samples.shape
    out = np.zeros_like(samples)
    for i in range(n_rows):
        x = samples[i]
        a = x[0]  # sorted, so min is first
        q25, q75 = np.percentile(x, [25, 75])
        s_val = q75 - q25
        if s_val <= 0:
            s_val = x[-1] - x[0]
        if s_val <= 0:
            s_val = 1.0  # degenerate
        out[i] = (x - a) / s_val
    return out


def prepare_targets(samples: np.ndarray, targets_raw: np.ndarray) -> np.ndarray:
    """Encode targets: log(beta), log(eta/s), log((a-gamma)/s)."""
    n_rows = targets_raw.shape[0]
    encoded = np.zeros((n_rows, 3))
    for i in range(n_rows):
        x = samples[i]
        beta, eta, gamma = float(targets_raw[i, 0]), float(targets_raw[i, 1]), float(targets_raw[i, 2])
        a = x[0]
        q25, q75 = np.percentile(x, [25, 75])
        s_val = q75 - q25
        if s_val <= 0:
            s_val = x[-1] - x[0]
        if s_val <= 0:
            s_val = 1.0
        anchor = type("Anchor", (), {"location": a, "scale": s_val})()
        enc = encode_targets(beta, eta, gamma, anchor)
        encoded[i] = enc
    return encoded


# ---------------------------------------------------------------------------
# Minimal training loop (PyTorch, no formal machinery)
# ---------------------------------------------------------------------------

def train_one_fit(
    model: torch.nn.Module,
    train_features: torch.Tensor,
    train_targets: torch.Tensor,
    val_features: torch.Tensor,
    val_targets: torch.Tensor,
    config: dict,
    seed: int,
    output_dir: Path,
) -> dict[str, Any]:
    """Train one model, save checkpoint + fit state, return result dict."""
    seed_everything(seed)

    opt_cfg = config["baseline"]["optimizer"]
    epoch_cfg = config["baseline"]["epochs"]
    loss_id = config["baseline"]["loss"]
    device = torch.device("cpu")

    model = model.to(device)
    train_features = train_features.to(device)
    train_targets = train_targets.to(device)
    val_features = val_features.to(device)
    val_targets = val_targets.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=float(opt_cfg["lr"]),
                                  weight_decay=float(opt_cfg["weight_decay"]))
    batch_size = int(opt_cfg["batch_size"])
    n_train = train_features.shape[0]

    # Training stats (mean/std of train_targets for loss standardization)
    t_mean = train_targets.mean(dim=0)
    t_std = train_targets.std(dim=0, unbiased=False).clamp(min=1e-8)
    training_stats = {"mean": t_mean, "std": t_std}

    best_val_loss = float("inf")
    best_epoch = 0
    best_state = None
    patience_counter = 0
    train_losses: list[float] = []
    val_losses: list[float] = []

    for epoch in range(1, int(epoch_cfg["max"]) + 1):
        model.train()
        perm = torch.randperm(n_train)
        epoch_train_loss = 0.0
        n_batches = 0
        for start in range(0, n_train, batch_size):
            idx = perm[start:start + batch_size]
            pred = model(train_features[idx])
            loss = compute_loss(loss_id, pred, train_targets[idx], training_stats)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            epoch_train_loss += loss.item()
            n_batches += 1
        train_losses.append(epoch_train_loss / max(n_batches, 1))

        model.eval()
        with torch.no_grad():
            pred_val = model(val_features)
            val_loss = compute_loss(loss_id, pred_val, val_targets, training_stats)
        val_losses.append(val_loss.item())

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience_counter = 0
        else:
            patience_counter += 1

        if epoch >= int(epoch_cfg["min"]) and patience_counter >= int(epoch_cfg["patience"]):
            break

    # Load best state
    if best_state is not None:
        model.load_state_dict(best_state)

    # Save checkpoint
    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_dir / CHECKPOINT_FILENAME)

    result = {
        "seed": seed,
        "best_epoch": best_epoch,
        "best_val_loss": float(best_val_loss),
        "train_losses": train_losses,
        "val_losses": val_losses,
        "n_params": trainable_parameter_count(model),
        "early_stopped": best_epoch < int(epoch_cfg["max"]),
    }
    with open(output_dir / FIT_STATE_FILENAME, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    return result


# ---------------------------------------------------------------------------
# Evaluation helpers
# ---------------------------------------------------------------------------

def compute_l_param(est: np.ndarray, true: np.ndarray, eta_true: np.ndarray) -> float:
    """Composite parameter loss L_param."""
    e_beta = (est[:, 0] - true[:, 0]) / true[:, 0]
    e_eta = (est[:, 1] - true[:, 1]) / true[:, 1]
    e_gamma = (est[:, 2] - true[:, 2]) / eta_true
    return float(np.sqrt(np.mean((e_beta**2 + e_eta**2 + e_gamma**2) / 3)))


def evaluate_model(
    model: torch.nn.Module,
    eval_features: torch.Tensor,
    eval_targets_raw: np.ndarray,
    eval_samples: np.ndarray,
) -> dict[str, Any]:
    """Evaluate model on eval set, return L_param + per-parameter metrics."""
    model.eval()
    device = torch.device("cpu")
    model = model.to(device)
    eval_features = eval_features.to(device)

    with torch.no_grad():
        raw = model(eval_features).numpy()

    # Decode predictions
    n = eval_features.shape[0]
    est = np.zeros((n, 3))
    for i in range(n):
        x = eval_samples[i]
        a = x[0]
        q25, q75 = np.percentile(x, [25, 75])
        s_val = q75 - q25
        if s_val <= 0:
            s_val = x[-1] - x[0]
        if s_val <= 0:
            s_val = 1.0
        log_beta, log_eta_s, log_a_gamma_s = raw[i]
        beta_hat = np.exp(log_beta)
        eta_hat = np.exp(log_eta_s) * s_val
        gamma_hat = a - np.exp(log_a_gamma_s) * s_val
        est[i] = [beta_hat, eta_hat, gamma_hat]

    l_param = compute_l_param(est, eval_targets_raw, eval_targets_raw[:, 1])

    # Per-parameter
    e_beta = (est[:, 0] - eval_targets_raw[:, 0]) / eval_targets_raw[:, 0]
    e_eta = (est[:, 1] - eval_targets_raw[:, 1]) / eval_targets_raw[:, 1]
    e_gamma = (est[:, 2] - eval_targets_raw[:, 2]) / eval_targets_raw[:, 1]

    # Legality
    legal = (est[:, 0] > 0) & (est[:, 1] > 0) & (est[:, 2] < np.min(eval_samples, axis=1))
    legality_rate = float(legal.mean())

    return {
        "l_param": l_param,
        "beta_bias": float(np.mean(e_beta)), "beta_rmse": float(np.sqrt(np.mean(e_beta**2))),
        "eta_bias": float(np.mean(e_eta)), "eta_rmse": float(np.sqrt(np.mean(e_eta**2))),
        "gamma_bias": float(np.mean(e_gamma)), "gamma_rmse": float(np.sqrt(np.mean(e_gamma**2))),
        "legality_rate": legality_rate,
    }


# ---------------------------------------------------------------------------
# A13: range-clipped oracle (evaluation only, no NN training)
# ---------------------------------------------------------------------------

def evaluate_a13_oracle(conf_samples: np.ndarray, conf_targets: np.ndarray, config: dict) -> dict[str, Any]:
    """Apply range-clipped oracle to conventional estimators on confirmed split."""
    from methods.mle import mle as mle_func
    from methods.wmle import wmle as wmle_func
    from methods.mps import mps as mps_func
    from methods.mdm import mdm as mdm_func
    from methods.lre import lre as lre_func

    methods = {
        "MLE": mle_func,
        "WMLE": wmle_func,
        "MPS": mps_func,
        "MDM": lambda s: mdm_func(s, offset=0.1),
        "LRE": lre_func,
    }

    core = config["training_pool"]["core_continuous"]
    clip_beta = (float(core["beta"]["min"]), float(core["beta"]["max"]))
    clip_eta = (float(core["eta"]["min"]), float(core["eta"]["max"]))
    clip_rho = (0.0, 1.0)

    results: dict[str, dict] = {}
    n = conf_samples.shape[0]
    for name, func in methods.items():
        estimates = np.zeros((n, 3))
        failures = 0
        for i in range(n):
            try:
                est = func(conf_samples[i])
                beta_h, eta_h, gamma_h = float(est[0]), float(est[1]), float(est[2])
                # Clip
                beta_c = np.clip(beta_h, *clip_beta)
                eta_c = np.clip(eta_h, *clip_eta)
                rho_c = np.clip(gamma_h / eta_h if eta_h > 0 else 0, *clip_rho)
                gamma_c = rho_c * eta_c
                estimates[i] = [beta_c, eta_c, gamma_c]
            except Exception:
                failures += 1
                estimates[i] = [np.nan, np.nan, np.nan]

        # L_param on non-failed only (with failure penalty in reporting)
        valid = ~np.isnan(estimates[:, 0])
        l_param = compute_l_param(estimates[valid], conf_targets[valid], conf_targets[valid, 1]) if valid.any() else 10.0
        results[name] = {
            "l_param": l_param,
            "l_param_incl_failures": l_param if failures == 0 else l_param + 10.0 * failures / n,
            "failure_rate": failures / n,
            "n_valid": int(valid.sum()),
        }
    return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def fit_count(config: dict) -> int:
    return (len(config["A5_training_sizes"]) * len(config["A5_training_seeds"]) +
            len(config["A6_distributions"]) * len(config["A6_seeds"]))


def dry_run(config: dict) -> None:
    n_fits = fit_count(config)
    n_val = config["validation"]["param_points"] * config["validation"]["repeats_per_point"]
    n_conf = config["confirmation"]["param_points"] * config["confirmation"]["repeats_per_point"]
    print(f"E1 dry-run:")
    print(f"  baseline: V route, n=10, m12-style MLP, huber")
    print(f"  A5: {len(config['A5_training_sizes'])} sizes × {len(config['A5_training_seeds'])} seeds = {len(config['A5_training_sizes']) * len(config['A5_training_seeds'])} fits")
    print(f"    sizes: {config['A5_training_sizes']}")
    print(f"  A6: {len(config['A6_distributions'])} dists × {len(config['A6_seeds'])} seeds = {len(config['A6_distributions']) * len(config['A6_seeds'])} fits")
    print(f"    dists: {list(config['A6_distributions'])}")
    print(f"  A13: evaluation-only ({', '.join(config['A13_oracle']['conventional_methods'])})")
    print(f"  Total NN fits: {n_fits}")
    print(f"  Validation: {n_val} rows (256 pts × 50 reps)")
    print(f"  Confirmation: {n_conf} rows (256 pts × 200 reps)")
    print(f"  Output: {config.get('output_root', DEFAULT_OUTPUT_ROOT)}")
    print(f"  Formal-test path referenced: NO")
    print(f"  Soft bound: {n_fits}/{config['stop']['max_soft_bound_fits']} fits, "
          f"~{config['stop']['estimated_runtime_h']}/{config['stop']['max_soft_bound_hours']}h")


def main() -> None:
    parser = argparse.ArgumentParser(description="E1 training-sensitivity experiment")
    parser.add_argument("--config", required=True, help="Path to E1 JSON config")
    parser.add_argument("--dry-run", action="store_true", help="Print fit count, sizes, paths, exit")
    parser.add_argument("--mode", choices=["pilot", "full", "confirmation"], help="Run mode (not yet implemented)")
    parser.add_argument("--verify-config", action="store_true", help="Validate config + compute config hash")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    config["_config_path"] = str(config_path.resolve())

    if args.dry_run:
        dry_run(config)
        return

    if args.verify_config:
        cfg_bytes = config_path.read_bytes()
        sha = hashlib.sha256(cfg_bytes).hexdigest()
        print(f"config_sha256: {sha}")
        print(f"fit_count: {fit_count(config)}")
        print("No formal-test path referenced.")
        return

    # Modes ("pilot", "full", "confirmation") launch training/evaluation.
    # For preflight, only --dry-run and --verify-config are exposed.
    if args.mode:
        print(f"Mode '{args.mode}' not yet implemented (preflight phase).")
        print("Run --dry-run or --verify-config instead.")
        sys.exit(0)

    # Default: print usage
    print("Usage: see --dry-run, --verify-config, or --mode.")
    print("No training launched (preflight phase).")


if __name__ == "__main__":
    main()
