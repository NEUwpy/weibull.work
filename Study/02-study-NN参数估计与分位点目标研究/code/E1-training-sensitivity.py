"""E1 minimal training-sensitivity experiment.

Answers A5 (training-data size), A6 (parameter distribution), A13 (range-clipped oracle).
Reuses study02a.models, study02a.training (non-formal utilities), and representations.py.
No formal scheduler/lease/authority/unseal machinery. Formal test permanently sealed.

Usage:
  python E1-training-sensitivity.py --config CONFIG [--dry-run] [--mode MODE]
"""

from __future__ import annotations

import argparse, hashlib, json, os, sys, time, itertools
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from scipy.stats import qmc

# --- Paths ---
_SCRIPT_DIR = Path(__file__).resolve().parent
_STUDY_ROOT = _SCRIPT_DIR.parent
_REPO_ROOT = _STUDY_ROOT.parent.parent
sys.path.insert(0, str(_STUDY_ROOT / "code"))
sys.path.insert(0, str(_REPO_ROOT / "python"))

from study02a.models import build_mlp, trainable_parameter_count
from study02a.training import compute_loss, seed_everything
from study02a.representations import anchor_sample, encode_targets, decode_targets

STATS_KEY_SD = "sd"
FIT_STATE = "fit_state.json"; CHECKPOINT = "checkpoint.pt"
OUTPUTS = "outputs"; PILOT_PREFIX = "pilot"


# ===========================================================================
# Data generation
# ===========================================================================

def _sobol(n: int, d: int, seed: int) -> np.ndarray:
    return qmc.Sobol(d=d, scramble=True, seed=seed).random(n)

def _logu(col, lo, hi): return np.exp(np.log(lo) + col * (np.log(hi) - np.log(lo)))
def _uni(col, lo, hi): return lo + col * (hi - lo)

def _weibull_sample(beta, eta, gamma, n, seed):
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 1, n)
    return np.sort(gamma + eta * (-np.log(1 - u)) ** (1.0 / max(beta, 1e-8)))


def generate_distribution_params(dist_cfg: dict, n_rows: int, seed: int) -> np.ndarray:
    """Generate (beta, eta, gamma) for one training distribution.

    - continuous: log_uniform beta/eta + uniform rho, then gamma = rho * eta.
    - legacy_grid: full factorial of {beta} x {eta} x {gamma} values,
      repeated in a deterministic balanced sequence, with any remainder
      drawn from a shuffled copy.
    """
    beta_cfg = dist_cfg["beta"]
    eta_cfg = dist_cfg["eta"]

    # --- Determine generation mode ---
    is_continuous = (isinstance(beta_cfg, dict) and beta_cfg.get("distribution") == "log_uniform")

    if is_continuous:
        sob = _sobol(n_rows, 3, seed)
        beta = _logu(sob[:, 0], float(beta_cfg["min"]), float(beta_cfg["max"]))
        eta = _logu(sob[:, 1], float(eta_cfg["min"]), float(eta_cfg["max"]))
        rho_cfg = dist_cfg["rho"]
        rho = _uni(sob[:, 2], float(rho_cfg["min"]), float(rho_cfg["max"]))
        gamma = rho * eta
        return np.column_stack([beta, eta, gamma])
    else:
        # Discrete grid: build full factorial, repeat deterministically
        beta_vals = list(beta_cfg)
        eta_vals = list(eta_cfg)
        gamma_vals = list(dist_cfg["gamma"])
        grid = list(itertools.product(beta_vals, eta_vals, gamma_vals))
        n_grid = len(grid)
        rng = np.random.default_rng(seed)
        # Deterministic balanced sequence: repeat complete grid, remainder from shuffle
        full_repeats = n_rows // n_grid
        remainder = n_rows % n_grid
        seq = grid * full_repeats
        if remainder > 0:
            shuffled = list(grid)  # copy
            rng.shuffle(shuffled)
            seq += shuffled[:remainder]
        return np.array(seq)


def generate_pool(config: dict, *, prefix_size: int | None = None,
                  dist_name: str = "core_continuous") -> tuple[np.ndarray, np.ndarray, np.ndarray]:
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
        samples[i] = s; targets_raw[i] = [beta, eta, gamma]
    return params, samples, targets_raw


def generate_role_data(config: dict, role: str) -> tuple[np.ndarray, np.ndarray]:
    role_cfg = config.get(role, {})
    n_points = int(role_cfg["param_points"])
    n = int(role_cfg["n"]); repeats = int(role_cfg["repeats_per_point"])
    design_seed = int(role_cfg["design_seed"])
    sample_seed = int(role_cfg["sample_seed"])
    total = n_points * repeats

    core = config["training_pool"]["core_continuous"]
    sob = _sobol(n_points, 3, design_seed)
    beta = _logu(sob[:, 0], core["beta"]["min"], core["beta"]["max"])
    eta = _logu(sob[:, 1], core["eta"]["min"], core["eta"]["max"])
    rho = _uni(sob[:, 2], core["rho"]["min"], core["rho"]["max"])
    gamma = rho * eta

    samples = np.zeros((total, n)); targets_raw = np.zeros((total, 3))
    idx = 0
    for pt in range(n_points):
        b, e, g = float(beta[pt]), float(eta[pt]), float(gamma[pt])
        for rep in range(repeats):
            s = _weibull_sample(b, e, g, n, sample_seed + pt * repeats + rep)
            samples[idx] = s; targets_raw[idx] = [b, e, g]; idx += 1

    # Attach parameter-point IDs for aggregation
    pt_ids = np.repeat(np.arange(n_points), repeats)
    return samples, targets_raw, pt_ids


# ===========================================================================
# Preprocessing (V route via representations.py)
# ===========================================================================

def preprocess_v_route(samples): return np.array([anchor_sample(s).z for s in samples])

def prepare_targets(samples, targets_raw):
    out = np.zeros((targets_raw.shape[0], 3))
    for i in range(targets_raw.shape[0]):
        a = anchor_sample(samples[i])
        beta, eta, gamma = float(targets_raw[i, 0]), float(targets_raw[i, 1]), float(targets_raw[i, 2])
        out[i] = encode_targets(beta, eta, gamma, a)
    return out

def decode_predictions(raw, samples):
    est = np.zeros((raw.shape[0], 3))
    for i in range(raw.shape[0]):
        a = anchor_sample(samples[i])
        b, e, g = decode_targets(raw[i], a); est[i] = [b, e, g]
    return est


# ===========================================================================
# Training
# ===========================================================================

def train_one_fit(model, train_feat, train_targ, val_feat, val_targ, config, seed, out_dir):
    seed_everything(seed)
    opt_cfg = config["baseline"]["optimizer"]; epoch_cfg = config["baseline"]["epochs"]
    loss_id = config["baseline"]["loss"]; device = torch.device("cpu")
    batch_size = int(opt_cfg["batch_size"]); n_train = train_feat.shape[0]

    model = model.to(device)
    train_feat, train_targ = train_feat.to(device), train_targ.to(device)
    val_feat, val_targ = val_feat.to(device), val_targ.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=float(opt_cfg["lr"]),
                                  weight_decay=float(opt_cfg["weight_decay"]))
    stats = {"mean": train_targ.mean(dim=0),
             STATS_KEY_SD: train_targ.std(dim=0, unbiased=False).clamp(min=1e-8)}

    best_val = float("inf"); best_epoch = 0; best_state = None; patience = 0
    train_losses, val_losses = [], []

    for epoch in range(1, int(epoch_cfg["max"]) + 1):
        model.train(); perm = torch.randperm(n_train)
        epoch_loss = 0.0; n_batches = 0
        for start in range(0, n_train, batch_size):
            idx = perm[start:start + batch_size]
            pred = model(train_feat[idx])
            loss = compute_loss(loss_id, pred, train_targ[idx], stats)
            optimizer.zero_grad(); loss.backward(); optimizer.step()
            epoch_loss += loss.item(); n_batches += 1
        train_losses.append(epoch_loss / max(n_batches, 1))
        model.eval()
        with torch.no_grad():
            val_loss = compute_loss(loss_id, model(val_feat), val_targ, stats)
        val_losses.append(val_loss.item())
        if val_loss < best_val:
            best_val = val_loss; best_epoch = epoch
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            patience = 0
        else:
            patience += 1
        if epoch >= int(epoch_cfg["min"]) and patience >= int(epoch_cfg["patience"]):
            break

    if best_state is not None: model.load_state_dict(best_state)
    out_dir.mkdir(parents=True, exist_ok=True)
    torch.save(model.state_dict(), out_dir / CHECKPOINT)
    result = {"seed": seed, "best_epoch": best_epoch, "best_val_loss": float(best_val),
              "train_losses": train_losses, "val_losses": val_losses,
              "n_params": trainable_parameter_count(model),
              "early_stopped": best_epoch < int(epoch_cfg["max"])}
    with open(out_dir / FIT_STATE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


# ===========================================================================
# Resume checks
# ===========================================================================

def can_resume(out_dir: Path, model: torch.nn.Module, expected_rows: int) -> bool:
    """Return True only if checkpoint+state both exist, parse, match, and load."""
    cp = out_dir / CHECKPOINT; st = out_dir / FIT_STATE
    if not (cp.exists() and st.exists()): return False
    try:
        state = json.loads(st.read_text(encoding="utf-8"))
        if not all(k in state for k in ("best_epoch", "seed")): return False
        checkpoint = torch.load(cp, map_location="cpu")
        model.load_state_dict(checkpoint)
        return True
    except Exception:
        return False


# ===========================================================================
# Evaluation + Aggregation
# ===========================================================================

def compute_l_param(est, true, eta_true):
    valid = ~np.isnan(est[:, 0])
    e_beta = (est[valid, 0] - true[valid, 0]) / true[valid, 0]
    e_eta = (est[valid, 1] - true[valid, 1]) / true[valid, 1]
    e_gamma = (est[valid, 2] - true[valid, 2]) / eta_true[valid]
    return float(np.sqrt(np.mean((e_beta**2 + e_eta**2 + e_gamma**2) / 3)))

def evaluate_model(model, eval_feat, eval_targ_raw, eval_samples):
    model.eval(); device = torch.device("cpu")
    model = model.to(device); eval_feat = eval_feat.to(device)
    with torch.no_grad(): raw = model(eval_feat).numpy()
    est = decode_predictions(raw, eval_samples)
    l_param = compute_l_param(est, eval_targ_raw, eval_targ_raw[:, 1])
    valid = ~np.isnan(est[:, 0])
    legal = valid & (est[:, 0] > 0) & (est[:, 1] > 0) & (est[:, 2] < np.min(eval_samples, axis=1))
    legality = float(legal.sum() / max(len(eval_samples), 1))
    e_beta = (est[valid, 0] - eval_targ_raw[valid, 0]) / eval_targ_raw[valid, 0]
    e_eta = (est[valid, 1] - eval_targ_raw[valid, 1]) / eval_targ_raw[valid, 1]
    e_gamma = (est[valid, 2] - eval_targ_raw[valid, 2]) / eval_targ_raw[valid, 1]
    return {"l_param": l_param, "legality_rate": legality, "n_valid": int(valid.sum()),
            "beta_bias": float(np.mean(e_beta)), "beta_rmse": float(np.sqrt(np.mean(e_beta**2))),
            "eta_bias": float(np.mean(e_eta)), "eta_rmse": float(np.sqrt(np.mean(e_eta**2))),
            "gamma_bias": float(np.mean(e_gamma)), "gamma_rmse": float(np.sqrt(np.mean(e_gamma**2))),
            "estimates": est, "pt_ids": None}


def bootstrap_ci(values, n_boot=2000, seed=520001):
    """Cluster bootstrap CI (over parameter points). Percentile 95% CI."""
    rng = np.random.default_rng(seed)
    boots = np.array([np.mean(rng.choice(values, len(values), replace=True)) for _ in range(n_boot)])
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)), float(np.mean(values))


def aggregate_seeds(eval_results: list[dict]) -> dict:
    """Aggregate 3 seeds: mean L_param, seed SD, per-param stats."""
    lp = np.array([r["l_param"] for r in eval_results])
    return {"l_param_mean": float(np.mean(lp)), "l_param_sd": float(np.std(lp, ddof=1)),
            "l_param_seeds": lp.tolist(), "n_seeds": len(eval_results)}


# ===========================================================================
# A13: range-clipped oracle
# ===========================================================================

def _single_method_estimate(method_name: str, sample: np.ndarray):
    """Run one conventional method. Returns dict with beta/eta/gamma + success status, or None."""
    try:
        if method_name == "MLE":
            from methods.mle import MLE
            result = MLE(sample).run()
            # [beta, eta, gamma, r2, success_bool]
            if isinstance(result, (list, tuple)) and len(result) >= 5:
                beta, eta, gamma, _, success = (float(result[0]), float(result[1]),
                                                float(result[2]), result[3], result[4])
                if not success or not (np.isfinite(beta) and np.isfinite(eta) and np.isfinite(gamma)):
                    return None
                if beta <= 0 or eta <= 0: return None
                return (beta, eta, gamma)
        elif method_name == "WMLE":
            from methods.wmle import WMLE
            result = WMLE(sample).run()
            # [gamma, beta, alpha(scale=eta), r2] — REORDER to (beta, eta, gamma)
            if isinstance(result, (list, tuple)) and len(result) >= 4:
                gamma_w, beta_w, alpha_w = float(result[0]), float(result[1]), float(result[2])
                if not (np.isfinite(beta_w) and np.isfinite(alpha_w) and np.isfinite(gamma_w)):
                    return None
                if beta_w <= 0 or alpha_w <= 0: return None
                return (beta_w, alpha_w, gamma_w)
        elif method_name == "MPS":
            from methods.mps import MPS
            result = MPS(sample).run()
            if isinstance(result, (list, tuple)) and len(result) >= 3:
                beta, eta, gamma = float(result[0]), float(result[1]), float(result[2])
                if not (np.isfinite(beta) and np.isfinite(eta) and np.isfinite(gamma)):
                    return None
                if beta <= 0 or eta <= 0: return None
                return (beta, eta, gamma)
        elif method_name == "MDM":
            from methods.mdm import MDM
            result = MDM(sample).run(offset=0.1)
            if isinstance(result, (list, tuple)) and len(result) >= 5:
                beta, eta, gamma, _, success = (float(result[0]), float(result[1]),
                                                float(result[2]), result[3], result[4])
                if not success or not (np.isfinite(beta) and np.isfinite(eta) and np.isfinite(gamma)):
                    return None
                if beta <= 0 or eta <= 0: return None
                return (beta, eta, gamma)
        elif method_name == "LRE":
            from methods.lre import LRE
            result = LRE(sample).run()
            if isinstance(result, (list, tuple)) and len(result) >= 5:
                beta, eta, gamma, _, success = (float(result[0]), float(result[1]),
                                                float(result[2]), result[3], result[4])
                if not success or not (np.isfinite(beta) and np.isfinite(eta) and np.isfinite(gamma)):
                    return None
                if beta <= 0 or eta <= 0: return None
                return (beta, eta, gamma)
        return None
    except Exception:
        return None


def apply_oracle_clip(beta, eta, gamma, clip_beta, clip_eta):
    """Clip: rho_c = clip(gamma_hat / eta_hat, 0, 1), then gamma_c = rho_c * eta_c.

    Uses original eta_hat for the rho division (not pre-clipped eta).
    """
    rho_c = np.clip(gamma / eta if eta > 0 else 0.5, 0.0, 1.0)
    beta_c = np.clip(beta, *clip_beta)
    eta_c = np.clip(eta, *clip_eta)
    gamma_c = rho_c * eta_c
    return beta_c, eta_c, gamma_c


def evaluate_a13_oracle(conf_samples, conf_targets, config):
    core = config["training_pool"]["core_continuous"]
    clip_beta = (float(core["beta"]["min"]), float(core["beta"]["max"]))
    clip_eta = (float(core["eta"]["min"]), float(core["eta"]["max"]))
    method_names = config["A13_oracle"]["conventional_methods"]
    results = {}
    for name in method_names:
        raw_est = np.full((conf_samples.shape[0], 3), np.nan)
        clipped_est = np.full((conf_samples.shape[0], 3), np.nan)
        raw_fail = clipped_fail = 0
        for i in range(conf_samples.shape[0]):
            est = _single_method_estimate(name, conf_samples[i])
            if est is None:
                raw_fail += 1; clipped_fail += 1; continue
            beta_h, eta_h, gamma_h = float(est[0]), float(est[1]), float(est[2])
            raw_est[i] = [beta_h, eta_h, gamma_h]
            bc, ec, gc = apply_oracle_clip(beta_h, eta_h, gamma_h, clip_beta, clip_eta)
            clipped_est[i] = [bc, ec, gc]
        valid_r = ~np.isnan(raw_est[:, 0])
        valid_c = ~np.isnan(clipped_est[:, 0])
        lp_raw = compute_l_param(raw_est[valid_r], conf_targets[valid_r], conf_targets[valid_r, 1]) if valid_r.any() else 10.0
        lp_clip = compute_l_param(clipped_est[valid_c], conf_targets[valid_c], conf_targets[valid_c, 1]) if valid_c.any() else 10.0
        results[name] = {
            "raw_l_param": lp_raw, "clipped_l_param": lp_clip,
            "raw_failure_rate": raw_fail / max(conf_samples.shape[0], 1),
            "clipped_failure_rate": clipped_fail / max(conf_samples.shape[0], 1),
            "raw_n_valid": int(valid_r.sum()), "clipped_n_valid": int(valid_c.sum()),
        }
    return results


# ===========================================================================
# Modes
# ===========================================================================

def _make_model(config): return build_mlp(
    input_dim=int(config["baseline"]["architecture"]["input_dim"]),
    widths=list(config["baseline"]["architecture"]["widths"]),
    activation=config["baseline"]["architecture"]["activation"],
    dropout=float(config["baseline"]["architecture"]["dropout"]))

def _output_dir(base, arm, combo, seed, prefix=""):
    p = base / prefix / arm / combo / str(seed) / OUTPUTS if prefix else base / arm / combo / str(seed) / OUTPUTS
    return p


def run_pilot(config):
    """2 fits in pilot/ subtree. Reduced epochs/rows for speed."""
    base = Path(config["output_root"])
    print("=== PILOT ==="); t0 = time.time()
    val_samples, val_targets, _ = generate_role_data(config, "validation")
    val_feat = torch.tensor(preprocess_v_route(val_samples), dtype=torch.float32)
    val_targ = torch.tensor(prepare_targets(val_samples, val_targets), dtype=torch.float32)

    # A5 pilot
    _, tr_s, tr_t = generate_pool(config, prefix_size=25000)
    tf = torch.tensor(preprocess_v_route(tr_s), dtype=torch.float32)
    tt_t = torch.tensor(prepare_targets(tr_s, tr_t), dtype=torch.float32)
    out = _output_dir(base, "A5", "25000", 720001, PILOT_PREFIX)
    model = _make_model(config)
    r = train_one_fit(model, tf, tt_t, val_feat, val_targ, config, 720001, out)
    print(f"  A5/25000: epoch={r['best_epoch']} val={r['best_val_loss']:.4f}")

    # A6 pilot
    _, tr_s2, tr_t2 = generate_pool(config, prefix_size=7000)
    tf2 = torch.tensor(preprocess_v_route(tr_s2), dtype=torch.float32)
    tt_t2 = torch.tensor(prepare_targets(tr_s2, tr_t2), dtype=torch.float32)
    out2 = _output_dir(base, "A6", "core_continuous", 720011, PILOT_PREFIX)
    model2 = _make_model(config)
    r2 = train_one_fit(model2, tf2, tt_t2, val_feat, val_targ, config, 720011, out2)
    print(f"  A6/core_continuous: epoch={r2['best_epoch']} val={r2['best_val_loss']:.4f}")

    t = time.time() - t0
    print(f"PILOT done: {t:.1f}s (~{t/60:.1f} min)")
    return t


def run_full(config):
    """21 fits with valid resume check."""
    base = Path(config["output_root"])
    print("=== FULL (21 fits) ==="); t0 = time.time()
    val_samples, val_targets, _ = generate_role_data(config, "validation")
    val_feat = torch.tensor(preprocess_v_route(val_samples), dtype=torch.float32)
    val_targ = torch.tensor(prepare_targets(val_samples, val_targets), dtype=torch.float32)

    for size in config["A5_training_sizes"]:
        _, tr_s, tr_t = generate_pool(config, prefix_size=size)
        tf = torch.tensor(preprocess_v_route(tr_s), dtype=torch.float32)
        tt_t = torch.tensor(prepare_targets(tr_s, tr_t), dtype=torch.float32)
        n_rows = tr_s.shape[0]
        for seed in config["A5_training_seeds"]:
            out = _output_dir(base, "A5", str(size), seed)
            model = _make_model(config)
            if can_resume(out, model, n_rows):
                print(f"  A5/{size}/s{seed}: RESUME (valid)")
                continue
            r = train_one_fit(model, tf, tt_t, val_feat, val_targ, config, seed, out)
            print(f"  A5/{size}/s{seed}: epoch={r['best_epoch']} val={r['best_val_loss']:.4f}")

    for dist_name in config["A6_distributions"]:
        _, tr_s, tr_t = generate_pool(config, prefix_size=config["A6_training_rows"], dist_name=dist_name)
        tf = torch.tensor(preprocess_v_route(tr_s), dtype=torch.float32)
        tt_t = torch.tensor(prepare_targets(tr_s, tr_t), dtype=torch.float32)
        n_rows = tr_s.shape[0]
        for seed in config["A6_seeds"]:
            out = _output_dir(base, "A6", dist_name, seed)
            model = _make_model(config)
            if can_resume(out, model, n_rows):
                print(f"  A6/{dist_name}/s{seed}: RESUME (valid)")
                continue
            r = train_one_fit(model, tf, tt_t, val_feat, val_targ, config, seed, out)
            print(f"  A6/{dist_name}/s{seed}: epoch={r['best_epoch']} val={r['best_val_loss']:.4f}")

    t = time.time() - t0
    print(f"FULL done: {t:.1f}s (~{t/60:.1f} min)")
    return t


def run_confirmation(config):
    """Evaluate all 21 preregistered arms on conf split. Fails if any fit missing."""
    base = Path(config["output_root"])
    conf_samples, conf_targets, pt_ids = generate_role_data(config, "confirmation")
    conf_feat = torch.tensor(preprocess_v_route(conf_samples), dtype=torch.float32)

    # Check completeness: all 21 fits must be present + valid
    missing = []
    for size in config["A5_training_sizes"]:
        for seed in config["A5_training_seeds"]:
            out = _output_dir(base, "A5", str(size), seed)
            if not can_resume(out, _make_model(config), -1):  # -1 = don't check rows
                missing.append(f"A5/{size}/s{seed}")
    for dist_name in config["A6_distributions"]:
        for seed in config["A6_seeds"]:
            out = _output_dir(base, "A6", dist_name, seed)
            if not can_resume(out, _make_model(config), -1):
                missing.append(f"A6/{dist_name}/s{seed}")

    if missing:
        print(f"CONFIRMATION REFUSED: {len(missing)} fit(s) missing/invalid: {missing}")
        print("No partial confirmation saved.")
        return

    print("=== CONFIRMATION ==="); t0 = time.time()
    results = {}
    # Evaluate all arms
    for size in config["A5_training_sizes"]:
        for seed in config["A5_training_seeds"]:
            arm = f"A5/{size}/s{seed}"
            ckpt = _output_dir(base, "A5", str(size), seed) / CHECKPOINT
            model = _make_model(config)
            model.load_state_dict(torch.load(ckpt, map_location="cpu"))
            r = evaluate_model(model, conf_feat, conf_targets, conf_samples)
            r["pt_ids"] = pt_ids.tolist()
            print(f"  {arm}: L_param={r['l_param']:.6f} legal={r['legality_rate']:.3f}")
            results[arm] = r

    for dist_name in config["A6_distributions"]:
        for seed in config["A6_seeds"]:
            arm = f"A6/{dist_name}/s{seed}"
            ckpt = _output_dir(base, "A6", dist_name, seed) / CHECKPOINT
            model = _make_model(config)
            model.load_state_dict(torch.load(ckpt, map_location="cpu"))
            r = evaluate_model(model, conf_feat, conf_targets, conf_samples)
            r["pt_ids"] = pt_ids.tolist()
            print(f"  {arm}: L_param={r['l_param']:.6f} legal={r['legality_rate']:.3f}")
            results[arm] = r

    # A13
    print("--- A13 oracle ---")
    a13 = evaluate_a13_oracle(conf_samples, conf_targets, config)
    for name, rd in a13.items():
        print(f"  {name}: raw_L={rd['raw_l_param']:.4f} clip_L={rd['clipped_l_param']:.4f} "
              f"raw_fail={rd['raw_failure_rate']:.3f} clip_fail={rd['clipped_failure_rate']:.3f}")
    results["A13"] = a13

    # Aggregate: A5 plateau + A6 paired effects
    agg = {}
    # A5: per-size aggregate (mean of 3 seeds), paired adjacent-size effects
    for size in config["A5_training_sizes"]:
        seeds = [results[f"A5/{size}/s{s}"] for s in config["A5_training_seeds"]]
        agg[f"A5/{size}"] = aggregate_seeds(seeds)
    sizes = config["A5_training_sizes"]
    for i in range(len(sizes) - 1):
        smaller = agg[f"A5/{sizes[i]}"]["l_param_mean"]
        larger = agg[f"A5/{sizes[i+1]}"]["l_param_mean"]
        rel_impr = (smaller - larger) / max(smaller, 1e-10)
        agg[f"A5_plateau_{sizes[i]}_to_{sizes[i+1]}"] = {
            "rel_improvement": float(rel_impr),
            "plateau_candidate": float(rel_impr) < 0.02,  # <2% improvement
        }

    # A6: paired dist vs core_continuous
    core_seeds = [results[f"A6/core_continuous/s{s}"]["l_param"] for s in config["A6_seeds"]]
    core_mean = float(np.mean(core_seeds))
    for dist_name in config["A6_distributions"]:
        if dist_name == "core_continuous": continue
        dist_seeds = [results[f"A6/{dist_name}/s{s}"]["l_param"] for s in config["A6_seeds"]]
        dist_mean = float(np.mean(dist_seeds))
        diff = dist_mean - core_mean
        lo, hi, _ = bootstrap_ci(np.array(dist_seeds) - np.array(core_seeds))
        agg[f"A6_{dist_name}_vs_core"] = {"l_param_diff": diff, "ci_lower": lo, "ci_upper": hi}

    agg["A13"] = a13

    summary_path = base / "confirmation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"results": {k: {kk: vv for kk, vv in v.items() if kk != "estimates"}
                               for k, v in results.items() if k != "A13"},
                   "A13": a13, "aggregation": agg},
                  f, ensure_ascii=False, indent=2, default=str)
    print(f"Confirmation saved to {summary_path}")
    t = time.time() - t0
    print(f"CONFIRMATION done: {t:.1f}s (~{t/60:.1f} min)")
    return t


# ===========================================================================
# CLI
# ===========================================================================

def fit_count(config):
    return (len(config["A5_training_sizes"]) * len(config["A5_training_seeds"]) +
            len(config["A6_distributions"]) * len(config["A6_seeds"]))

def dry_run(config):
    n_fits = fit_count(config)
    n_val = config["validation"]["param_points"] * config["validation"]["repeats_per_point"]
    n_conf = config["confirmation"]["param_points"] * config["confirmation"]["repeats_per_point"]
    print(f"E1 dry-run:")
    print(f"  A5: {len(config['A5_training_sizes'])} sizes x {len(config['A5_training_seeds'])} seeds = {len(config['A5_training_sizes']) * len(config['A5_training_seeds'])} fits")
    print(f"  A6: {len(config['A6_distributions'])} dists x {len(config['A6_seeds'])} seeds = {len(config['A6_distributions']) * len(config['A6_seeds'])} fits")
    print(f"  A13: eval-only ({', '.join(config['A13_oracle']['conventional_methods'])})")
    print(f"  Total NN fits: {n_fits}  |  Validation: {n_val}  |  Confirmation: {n_conf}")
    print(f"  Output: {config.get('output_root', '')}")
    print(f"  Formal-test path referenced: NO")

def main():
    p = argparse.ArgumentParser(description="E1 training-sensitivity")
    p.add_argument("--config", required=True); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--verify-config", action="store_true")
    p.add_argument("--mode", choices=["pilot", "full", "confirmation"])
    args = p.parse_args()
    cp = Path(args.config)
    if not cp.exists(): print(f"ERROR: {cp}"); sys.exit(1)
    config = json.loads(cp.read_text(encoding="utf-8"))

    if args.dry_run: dry_run(config); return
    if args.verify_config:
        print(f"config_sha256: {hashlib.sha256(cp.read_bytes()).hexdigest()}")
        print(f"fit_count: {fit_count(config)}"); return
    if args.mode == "pilot": run_pilot(config)
    elif args.mode == "full": run_full(config)
    elif args.mode == "confirmation": run_confirmation(config)
    else: print("Use: --dry-run | --verify-config | --mode {pilot|full|confirmation}")

if __name__ == "__main__": main()
