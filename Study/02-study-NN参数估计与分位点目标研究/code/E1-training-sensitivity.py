"""E1 minimal training-sensitivity experiment.

Answers A5 (training-data size), A6 (parameter distribution), A13 (range-clipped oracle).
Reuses study02a.models / study02a.training (non-formal utilities) and representations.py.
Does NOT call formal scheduler, lease, authority, unseal, hash-chain, capsule, or attack machinery.

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
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from scipy.stats import qmc

# --- Resolve project root and add import paths ---
_SCRIPT_DIR = Path(__file__).resolve().parent
_STUDY_ROOT = _SCRIPT_DIR.parent
_REPO_ROOT = _STUDY_ROOT.parent.parent  # Study/02-study.../ -> repo root
sys.path.insert(0, str(_STUDY_ROOT / "code"))
sys.path.insert(0, str(_REPO_ROOT / "python"))

from study02a.models import build_mlp, trainable_parameter_count
from study02a.training import compute_loss, seed_everything
from study02a.representations import (
    anchor_sample, build_features, encode_targets, decode_targets, Anchor)


# --- Constants ---
FIT_STATE_FILENAME = "fit_state.json"
CHECKPOINT_FILENAME = "checkpoint.pt"
OUTPUTS_DIRNAME = "outputs"

STATS_KEY_SD = "sd"  # compute_loss uses stats={"mean", "sd"}


# ===========================================================================
# Data generation (Sobol, no formal pipeline)
# ===========================================================================

def _sobol_points(n: int, d: int, seed: int) -> np.ndarray:
    return qmc.Sobol(d=d, scramble=True, seed=seed).random(n)


def _log_uniform_sample(sobol_col: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return np.exp(np.log(lo) + sobol_col * (np.log(hi) - np.log(lo)))


def _uniform_sample(sobol_col: np.ndarray, lo: float, hi: float) -> np.ndarray:
    return lo + sobol_col * (hi - lo)


def _full_factorial_grid(beta_vals, eta_vals, gamma_vals, n_rows: int, seed: int) -> np.ndarray:
    """Generate grid distribution param points by sampling from full factorial."""
    import itertools
    grid = list(itertools.product(beta_vals, eta_vals, gamma_vals))
    rng = np.random.default_rng(seed)
    indices = rng.choice(len(grid), size=n_rows, replace=True)
    return np.array([grid[i] for i in indices])


def generate_distribution_params(dist_config: dict, n_rows: int, seed: int) -> np.ndarray:
    """Generate (beta, eta, rho) parameter points for one training distribution.

    Supports continuous (log_uniform + uniform rho) and discrete grid formats.
    Returns (n_rows, 3).
    """
    sob = _sobol_points(n_rows, 3, seed)

    beta_cfg = dist_config["beta"]
    if isinstance(beta_cfg, dict) and beta_cfg.get("distribution") == "log_uniform":
        beta = _log_uniform_sample(sob[:, 0], float(beta_cfg["min"]), float(beta_cfg["max"]))
    else:
        # Discrete: sample from list
        vals = list(beta_cfg)
        rng = np.random.default_rng(seed)
        beta = np.array(rng.choice(vals, n_rows))

    eta_cfg = dist_config["eta"]
    if isinstance(eta_cfg, dict) and eta_cfg.get("distribution") == "log_uniform":
        eta = _log_uniform_sample(sob[:, 1], float(eta_cfg["min"]), float(eta_cfg["max"]))
    else:
        rng = np.random.default_rng(seed + 1)
        eta = np.array(rng.choice(list(eta_cfg), n_rows))

    rho_cfg = dist_config["rho"]
    if isinstance(rho_cfg, dict):
        rho = _uniform_sample(sob[:, 2], float(rho_cfg["min"]), float(rho_cfg["max"]))
    else:
        # gamma values: convert to rho = gamma / eta
        rng = np.random.default_rng(seed + 2)
        gamma_vals = np.array(rng.choice(list(rho_cfg), n_rows))
        rho = gamma_vals / eta  # approximate; for grid, gamma is already absolute

    if "gamma" in dist_config:  # legacy_grid has absolute gamma, not rho
        gamma_cfg = dist_config["gamma"]
        rng = np.random.default_rng(seed + 2)
        gamma_vals = np.array(rng.choice(list(gamma_cfg), n_rows))
        rho = gamma_vals / eta
    else:
        rho = _uniform_sample(sob[:, 2], float(rho_cfg["min"]), float(rho_cfg["max"]))

    gamma = rho * eta
    return np.column_stack([beta, eta, gamma])


def _weibull_sample(beta: float, eta: float, gamma: float, n: int, seed: int) -> np.ndarray:
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 1, n)
    return np.sort(gamma + eta * (-np.log(1 - u)) ** (1.0 / max(beta, 1e-8)))


def generate_pool(config: dict, *, prefix_size: int | None = None,
                  dist_name: str = "core_continuous") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Generate (params, samples, targets) for a training pool."""
    pool_cfg = config["training_pool"]
    dist_cfg = config["A6_distributions"][dist_name]
    n_points = prefix_size if prefix_size else pool_cfg["max_rows"]
    n = config["baseline"]["sample_size"]
    seed_design = int(pool_cfg["seed_design"])
    seed_sample = int(pool_cfg["seed_sample"])

    params = generate_distribution_params(dist_cfg, n_points, seed_design)
    samples = np.zeros((n_points, n))
    targets_raw = np.zeros((n_points, 3))
    for i in range(n_points):
        beta, eta, gamma = float(params[i, 0]), float(params[i, 1]), float(params[i, 2])
        s = _weibull_sample(beta, eta, gamma, n, seed_sample + i)
        samples[i] = s
        targets_raw[i] = [beta, eta, gamma]
    return params, samples, targets_raw


def generate_role_data(config: dict, role: str) -> tuple[np.ndarray, np.ndarray]:
    """Generate (samples, targets) for validation or confirmation role."""
    role_cfg = config.get(role, {})
    n_points = int(role_cfg["param_points"])
    n = int(role_cfg["n"])
    repeats = int(role_cfg["repeats_per_point"])
    design_seed = int(role_cfg["design_seed"])
    sample_seed = int(role_cfg["sample_seed"])
    total = n_points * repeats

    pool_cfg = config["training_pool"]
    core = pool_cfg["core_continuous"]
    params = _sobol_points(n_points, 3, design_seed)
    beta = _log_uniform_sample(params[:, 0], core["beta"]["min"], core["beta"]["max"])
    eta = _log_uniform_sample(params[:, 1], core["eta"]["min"], core["eta"]["max"])
    rho = _uniform_sample(params[:, 2], core["rho"]["min"], core["rho"]["max"])
    gamma = rho * eta

    samples = np.zeros((total, n))
    targets_raw = np.zeros((total, 3))
    idx = 0
    for pt in range(n_points):
        b, e, g = float(beta[pt]), float(eta[pt]), float(gamma[pt])
        for rep in range(repeats):
            s = _weibull_sample(b, e, g, n, sample_seed + pt * repeats + rep)
            samples[idx] = s
            targets_raw[idx] = [b, e, g]
            idx += 1
    return samples, targets_raw


# ===========================================================================
# Equivariant preprocessing (V route) — delegates to representations.py
# ===========================================================================

def preprocess_v_route(samples: np.ndarray) -> np.ndarray:
    """V route: sorted normalized values via Anchor.z. Shape (N, n)."""
    n_rows, n = samples.shape
    out = np.zeros((n_rows, n))
    for i in range(n_rows):
        anchor = anchor_sample(samples[i])
        out[i] = anchor.z
    return out


def prepare_targets(samples: np.ndarray, targets_raw: np.ndarray) -> np.ndarray:
    """Encode targets using representations.encode_targets. (N, 3)."""
    n_rows = targets_raw.shape[0]
    encoded = np.zeros((n_rows, 3))
    for i in range(n_rows):
        anchor = anchor_sample(samples[i])
        beta, eta, gamma = (float(targets_raw[i, 0]), float(targets_raw[i, 1]),
                            float(targets_raw[i, 2]))
        encoded[i] = encode_targets(beta, eta, gamma, anchor)
    return encoded


def decode_predictions(raw: np.ndarray, samples: np.ndarray) -> np.ndarray:
    """Decode model outputs using decode_targets. (N, 3) in (beta, eta, gamma)."""
    n = raw.shape[0]
    est = np.zeros((n, 3))
    for i in range(n):
        anchor = anchor_sample(samples[i])
        beta, eta, gamma = decode_targets(raw[i], anchor)
        est[i] = [beta, eta, gamma]
    return est


# ===========================================================================
# Minimal training loop
# ===========================================================================

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

    t_mean = train_targets.mean(dim=0)
    t_sd = train_targets.std(dim=0, unbiased=False).clamp(min=1e-8)
    training_stats = {"mean": t_mean, STATS_KEY_SD: t_sd}

    best_val_loss = float("inf")
    best_epoch = 0
    best_state = None
    patience_counter = 0
    train_losses = []
    val_losses = []

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

    if best_state is not None:
        model.load_state_dict(best_state)

    output_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), output_dir / CHECKPOINT_FILENAME)

    result = {
        "seed": seed, "best_epoch": best_epoch,
        "best_val_loss": float(best_val_loss),
        "train_losses": train_losses, "val_losses": val_losses,
        "n_params": trainable_parameter_count(model),
        "early_stopped": best_epoch < int(epoch_cfg["max"]),
    }
    with open(output_dir / FIT_STATE_FILENAME, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


# ===========================================================================
# Evaluation
# ===========================================================================

def compute_l_param(est: np.ndarray, true: np.ndarray, eta_true: np.ndarray) -> float:
    valid = ~np.isnan(est[:, 0])
    e_beta = (est[valid, 0] - true[valid, 0]) / true[valid, 0]
    e_eta = (est[valid, 1] - true[valid, 1]) / true[valid, 1]
    e_gamma = (est[valid, 2] - true[valid, 2]) / eta_true[valid]
    return float(np.sqrt(np.mean((e_beta**2 + e_eta**2 + e_gamma**2) / 3)))


def evaluate_model(
    model: torch.nn.Module,
    eval_features: torch.Tensor,
    eval_targets_raw: np.ndarray,
    eval_samples: np.ndarray,
) -> dict[str, Any]:
    model.eval()
    device = torch.device("cpu")
    model = model.to(device)
    eval_features = eval_features.to(device)
    with torch.no_grad():
        raw = model(eval_features).numpy()
    est = decode_predictions(raw, eval_samples)

    l_param = compute_l_param(est, eval_targets_raw, eval_targets_raw[:, 1])
    valid = ~np.isnan(est[:, 0])
    legal = valid & (est[:, 0] > 0) & (est[:, 1] > 0) & (est[:, 2] < np.min(eval_samples, axis=1))
    legality_rate = float(legal.sum() / max(len(eval_samples), 1))

    e_beta = (est[valid, 0] - eval_targets_raw[valid, 0]) / eval_targets_raw[valid, 0]
    e_eta = (est[valid, 1] - eval_targets_raw[valid, 1]) / eval_targets_raw[valid, 1]
    e_gamma = (est[valid, 2] - eval_targets_raw[valid, 2]) / eval_targets_raw[valid, 1]

    return {
        "l_param": l_param, "legality_rate": legality_rate,
        "n_valid": int(valid.sum()), "n_total": len(eval_samples),
        "beta_bias": float(np.mean(e_beta)), "beta_rmse": float(np.sqrt(np.mean(e_beta**2))),
        "eta_bias": float(np.mean(e_eta)), "eta_rmse": float(np.sqrt(np.mean(e_eta**2))),
        "gamma_bias": float(np.mean(e_gamma)), "gamma_rmse": float(np.sqrt(np.mean(e_gamma**2))),
    }


# ===========================================================================
# A13: range-clipped oracle — uses actual WeibullBase subclasses
# ===========================================================================

def _single_method_estimate(method_name: str, sample: np.ndarray) -> np.ndarray | None:
    """Run one conventional method on one sample. Returns (beta, eta, gamma) or None."""
    try:
        if method_name == "MLE":
            from methods.mle import MLE
            result = MLE(sample).run()
        elif method_name == "MPS":
            from methods.mps import MPS
            result = MPS(sample).run()
        elif method_name == "WMLE":
            from methods.wmle import WMLE
            result = WMLE(sample).run()
        elif method_name == "MDM":
            from methods.mdm import MDM
            result = MDM(sample).run(offset=0.1)
        elif method_name == "LRE":
            from methods.lre import LRE
            result = LRE(sample).run()
        else:
            return None
        if result is None:
            return None
        # Normalize return: result may be dict or tuple
        if isinstance(result, dict):
            beta, eta, gamma = result.get("beta", np.nan), result.get("eta", np.nan), result.get("gamma", np.nan)
        else:
            beta, eta, gamma = float(result[0]), float(result[1]), float(result[2])
        # Validate
        if not (np.isfinite(beta) and np.isfinite(eta) and np.isfinite(gamma)):
            return None
        if eta <= 0 or beta <= 0:
            return None
        return np.array([beta, eta, gamma])
    except Exception:
        return None


def evaluate_a13_oracle(conf_samples: np.ndarray, conf_targets: np.ndarray, config: dict) -> dict:
    """Range-clipped oracle. Original failures stay failures. No eta<=0 clipping."""
    core = config["training_pool"]["core_continuous"]
    clip_beta = (float(core["beta"]["min"]), float(core["beta"]["max"]))
    clip_eta = (float(core["eta"]["min"]), float(core["eta"]["max"]))
    clip_rho = (0.0, 1.0)

    method_names = config["A13_oracle"]["conventional_methods"]
    results = {}
    for name in method_names:
        estimates = np.full((conf_samples.shape[0], 3), np.nan)
        n_fail = 0
        for i in range(conf_samples.shape[0]):
            est = _single_method_estimate(name, conf_samples[i])
            if est is None:
                n_fail += 1
                continue
            beta_h, eta_h, gamma_h = float(est[0]), float(est[1]), float(est[2])
            # Clip to core
            beta_c = np.clip(beta_h, *clip_beta)
            eta_c = np.clip(eta_h, *clip_eta)
            rho_c = np.clip(gamma_h / eta_c if eta_c > 0 else 0.5, *clip_rho)
            gamma_c = rho_c * eta_c
            estimates[i] = [beta_c, eta_c, gamma_c]

        valid = ~np.isnan(estimates[:, 0])
        l_param = compute_l_param(estimates[valid], conf_targets[valid], conf_targets[valid, 1])
        failure_penalty = 10.0 if n_fail > 0 else 0.0
        results[name] = {
            "l_param": l_param,
            "l_param_incl_failures": l_param + failure_penalty * n_fail / max(conf_samples.shape[0], 1),
            "failure_rate": n_fail / max(conf_samples.shape[0], 1),
            "n_valid": int(valid.sum()), "n_total": conf_samples.shape[0],
        }
    return results


# ===========================================================================
# Mode runners
# ===========================================================================

def _make_model(config: dict) -> torch.nn.Module:
    arch = config["baseline"]["architecture"]
    return build_mlp(
        input_dim=int(arch["input_dim"]),
        widths=list(arch["widths"]),
        activation=arch["activation"],
        dropout=float(arch["dropout"]),
    )


def _output_dir_for(base_dir: Path, arm: str, combo: str, seed: int) -> Path:
    return base_dir / arm / combo / str(seed) / OUTPUTS_DIRNAME


def run_pilot(config: dict) -> None:
    """A5: 1 size (25K) x 1 seed + A6: 1 dist (core_continuous) x 1 seed = 2 fits."""
    base = Path(config["output_root"])
    print("=== PILOT (2 fits) ===")
    t0 = time.time()

    val_samples, val_targets = generate_role_data(config, "validation")
    val_features = torch.tensor(preprocess_v_route(val_samples), dtype=torch.float32)
    val_targets_t = torch.tensor(prepare_targets(val_samples, val_targets), dtype=torch.float32)

    # A5 pilot: size=25000, seed=720001
    _, train_samples, train_targets = generate_pool(config, prefix_size=25000)
    train_features = torch.tensor(preprocess_v_route(train_samples), dtype=torch.float32)
    train_targets_t = torch.tensor(prepare_targets(train_samples, train_targets), dtype=torch.float32)
    out = _output_dir_for(base, "A5", "25000", 720001)
    model = _make_model(config)
    r = train_one_fit(model, train_features, train_targets_t, val_features, val_targets_t,
                      config, 720001, out)
    print(f"  A5/25000/seed=720001: best_epoch={r['best_epoch']} val_loss={r['best_val_loss']:.6f}")

    # A6 pilot: dist=core_continuous, seed=720011
    _, train_samples2, train_targets2 = generate_pool(config, prefix_size=7000)
    train_features2 = torch.tensor(preprocess_v_route(train_samples2), dtype=torch.float32)
    train_targets_t2 = torch.tensor(prepare_targets(train_samples2, train_targets2), dtype=torch.float32)
    out2 = _output_dir_for(base, "A6", "core_continuous", 720011)
    model2 = _make_model(config)
    r2 = train_one_fit(model2, train_features2, train_targets_t2, val_features, val_targets_t,
                        config, 720011, out2)
    print(f"  A6/core_continuous/seed=720011: best_epoch={r2['best_epoch']} val_loss={r2['best_val_loss']:.6f}")

    elapsed = time.time() - t0
    print(f"PILOT done in {elapsed:.1f}s (~{elapsed/60:.1f} min)")


def run_full(config: dict) -> None:
    """21 fits (12 A5 + 9 A6). Resume: skip if fit_state.json exists."""
    base = Path(config["output_root"])
    print("=== FULL (21 fits) ===")
    t0 = time.time()

    val_samples, val_targets = generate_role_data(config, "validation")
    val_features = torch.tensor(preprocess_v_route(val_samples), dtype=torch.float32)
    val_targets_t = torch.tensor(prepare_targets(val_samples, val_targets), dtype=torch.float32)

    # A5
    for size in config["A5_training_sizes"]:
        _, train_samples, train_targets = generate_pool(config, prefix_size=size)
        train_features = torch.tensor(preprocess_v_route(train_samples), dtype=torch.float32)
        train_targets_t = torch.tensor(prepare_targets(train_samples, train_targets), dtype=torch.float32)
        for seed in config["A5_training_seeds"]:
            out = _output_dir_for(base, "A5", str(size), seed)
            if (out / FIT_STATE_FILENAME).exists():
                print(f"  A5/{size}/seed={seed}: SKIP (existing)")
                continue
            model = _make_model(config)
            r = train_one_fit(model, train_features, train_targets_t, val_features, val_targets_t,
                              config, seed, out)
            print(f"  A5/{size}/seed={seed}: epoch={r['best_epoch']} val={r['best_val_loss']:.6f}")

    # A6
    for dist_name in config["A6_distributions"]:
        _, train_samples, train_targets = generate_pool(config, prefix_size=config["A6_training_rows"],
                                                         dist_name=dist_name)
        train_features = torch.tensor(preprocess_v_route(train_samples), dtype=torch.float32)
        train_targets_t = torch.tensor(prepare_targets(train_samples, train_targets), dtype=torch.float32)
        for seed in config["A6_seeds"]:
            out = _output_dir_for(base, "A6", dist_name, seed)
            if (out / FIT_STATE_FILENAME).exists():
                print(f"  A6/{dist_name}/seed={seed}: SKIP (existing)")
                continue
            model = _make_model(config)
            r = train_one_fit(model, train_features, train_targets_t, val_features, val_targets_t,
                              config, seed, out)
            print(f"  A6/{dist_name}/seed={seed}: epoch={r['best_epoch']} val={r['best_val_loss']:.6f}")

    elapsed = time.time() - t0
    print(f"FULL done in {elapsed:.1f}s (~{elapsed/60:.1f} min)")


def run_confirmation(config: dict) -> None:
    """Evaluate ALL preregistered arms on conf split. Does NOT choose architecture/loss."""
    base = Path(config["output_root"])
    print("=== CONFIRMATION ===")
    t0 = time.time()

    conf_samples, conf_targets = generate_role_data(config, "confirmation")
    conf_features = torch.tensor(preprocess_v_route(conf_samples), dtype=torch.float32)

    results = {}
    # A5 arms
    for size in config["A5_training_sizes"]:
        for seed in config["A5_training_seeds"]:
            arm = f"A5/{size}/s{seed}"
            ckpt = _output_dir_for(base, "A5", str(size), seed) / CHECKPOINT_FILENAME
            if not ckpt.exists():
                print(f"  {arm}: NO CHECKPOINT")
                results[arm] = None
                continue
            model = _make_model(config)
            model.load_state_dict(torch.load(ckpt, map_location="cpu"))
            r = evaluate_model(model, conf_features, conf_targets, conf_samples)
            print(f"  {arm}: L_param={r['l_param']:.6f} legal={r['legality_rate']:.3f}")
            results[arm] = r

    # A6 arms
    for dist_name in config["A6_distributions"]:
        for seed in config["A6_seeds"]:
            arm = f"A6/{dist_name}/s{seed}"
            ckpt = _output_dir_for(base, "A6", dist_name, seed) / CHECKPOINT_FILENAME
            if not ckpt.exists():
                print(f"  {arm}: NO CHECKPOINT")
                results[arm] = None
                continue
            model = _make_model(config)
            model.load_state_dict(torch.load(ckpt, map_location="cpu"))
            r = evaluate_model(model, conf_features, conf_targets, conf_samples)
            print(f"  {arm}: L_param={r['l_param']:.6f} legal={r['legality_rate']:.3f}")
            results[arm] = r

    # A13 oracle
    print("--- A13 oracle ---")
    a13 = evaluate_a13_oracle(conf_samples, conf_targets, config)
    for name, r in a13.items():
        print(f"  {name}: L_param_incl_fail={r['l_param_incl_failures']:.4f} fail_rate={r['failure_rate']:.3f}")
    results["A13"] = a13

    # Save confirmation summary
    summary_path = base / "confirmation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2, default=str)
    print(f"Confirmation summary saved to {summary_path}")
    elapsed = time.time() - t0
    print(f"CONFIRMATION done in {elapsed:.1f}s (~{elapsed/60:.1f} min)")


# ===========================================================================
# CLI
# ===========================================================================

def fit_count(config: dict) -> int:
    return (len(config["A5_training_sizes"]) * len(config["A5_training_seeds"]) +
            len(config["A6_distributions"]) * len(config["A6_seeds"]))


def dry_run(config: dict) -> None:
    n_fits = fit_count(config)
    n_val = config["validation"]["param_points"] * config["validation"]["repeats_per_point"]
    n_conf = config["confirmation"]["param_points"] * config["confirmation"]["repeats_per_point"]
    print(f"E1 dry-run:")
    print(f"  baseline: V route, n=10, m12-style MLP, huber")
    print(f"  A5: {len(config['A5_training_sizes'])} sizes x {len(config['A5_training_seeds'])} seeds = {len(config['A5_training_sizes']) * len(config['A5_training_seeds'])} fits")
    print(f"    sizes: {config['A5_training_sizes']}")
    print(f"  A6: {len(config['A6_distributions'])} dists x {len(config['A6_seeds'])} seeds = {len(config['A6_distributions']) * len(config['A6_seeds'])} fits")
    print(f"    dists: {list(config['A6_distributions'])}")
    print(f"  A13: evaluation-only ({', '.join(config['A13_oracle']['conventional_methods'])})")
    print(f"  Total NN fits: {n_fits}")
    print(f"  Validation: {n_val} rows ({config['validation']['param_points']} pts x {config['validation']['repeats_per_point']} reps)")
    print(f"  Confirmation: {n_conf} rows ({config['confirmation']['param_points']} pts x {config['confirmation']['repeats_per_point']} reps)")
    print(f"  Output: {config.get('output_root', '')}")
    print(f"  Formal-test path referenced: NO")
    print(f"  Soft bound: {n_fits}/{config['stop']['max_soft_bound_fits']} fits")


def main() -> None:
    parser = argparse.ArgumentParser(description="E1 training-sensitivity experiment")
    parser.add_argument("--config", required=True, help="Path to E1 JSON config")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--verify-config", action="store_true")
    parser.add_argument("--mode", choices=["pilot", "full", "confirmation"])
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}")
        sys.exit(1)

    config = json.loads(config_path.read_text(encoding="utf-8"))

    if args.dry_run:
        dry_run(config)
        return

    if args.verify_config:
        sha = hashlib.sha256(config_path.read_bytes()).hexdigest()
        print(f"config_sha256: {sha}")
        print(f"fit_count: {fit_count(config)}")
        return

    if args.mode == "pilot":
        run_pilot(config)
    elif args.mode == "full":
        run_full(config)
    elif args.mode == "confirmation":
        run_confirmation(config)
    else:
        print("Usage: --dry-run | --verify-config | --mode {pilot|full|confirmation}")


if __name__ == "__main__":
    main()
