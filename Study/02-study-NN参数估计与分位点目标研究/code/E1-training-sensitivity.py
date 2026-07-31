"""E1 minimal training-sensitivity experiment.

Answers A5 (training-data size), A6 (parameter distribution), A13 (range-clipped oracle).
Reuses study02a.models, study02a.training (non-formal utilities), and representations.py.
No formal scheduler/lease/authority/unseal machinery. Formal test permanently sealed.

Usage:
  python E1-training-sensitivity.py --config CONFIG [--dry-run] [--mode MODE]
"""

from __future__ import annotations

import argparse, csv, gzip, hashlib, json, os, sys, time, itertools
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


def config_sha256(config: dict) -> str:
    """Hash the scientific config while ignoring runtime-only private keys."""
    public = {k: v for k, v in config.items() if not str(k).startswith("_")}
    payload = json.dumps(public, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ===========================================================================
# Data generation
# ===========================================================================

def _sobol(n: int, d: int, seed: int) -> np.ndarray:
    if int(n) <= 0:
        return np.empty((0, int(d)), dtype=float)
    power = int(np.ceil(np.log2(int(n))))
    return qmc.Sobol(d=d, scramble=True, seed=seed).random_base2(power)[:int(n)]

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

def train_one_fit(
    model, train_feat, train_targ, val_feat, val_targ, config, seed, out_dir, *,
    arm="smoke",
):
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
    result = {"seed": seed, "arm": str(arm), "training_rows": int(n_train),
              "config_sha256": config_sha256(config),
              "best_epoch": best_epoch, "best_val_loss": float(best_val),
              "train_losses": train_losses, "val_losses": val_losses,
              "n_params": trainable_parameter_count(model),
              "early_stopped": best_epoch < int(epoch_cfg["max"])}
    with open(out_dir / FIT_STATE, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    return result


# ===========================================================================
# Resume checks
# ===========================================================================

def can_resume(
    out_dir: Path, model: torch.nn.Module, expected_rows: int, *,
    expected_seed: int | None = None,
    expected_arm: str | None = None,
    expected_config_sha256: str | None = None,
) -> bool:
    """Return True only if checkpoint+state both exist, parse, match, and load."""
    cp = out_dir / CHECKPOINT; st = out_dir / FIT_STATE
    if not (cp.exists() and st.exists()): return False
    try:
        state = json.loads(st.read_text(encoding="utf-8"))
        if not all(k in state for k in (
            "best_epoch", "seed", "arm", "training_rows", "config_sha256"
        )):
            return False
        if expected_rows >= 0 and int(state["training_rows"]) != int(expected_rows):
            return False
        if expected_seed is not None and int(state["seed"]) != int(expected_seed):
            return False
        if expected_arm is not None and str(state["arm"]) != str(expected_arm):
            return False
        if (expected_config_sha256 is not None
                and str(state["config_sha256"]) != str(expected_config_sha256)):
            return False
        checkpoint = torch.load(cp, map_location="cpu")
        model.load_state_dict(checkpoint)
        return True
    except Exception:
        return False


# ===========================================================================
# Evaluation + Aggregation
# ===========================================================================

def row_squared_composite_loss(est, true, *, failure_penalty=np.nan):
    """Per-row mean squared normalized parameter error.

    Invalid estimates receive ``failure_penalty**2`` when a finite penalty is
    supplied; otherwise they remain NaN for conditional summaries.
    """
    est = np.asarray(est, dtype=float)
    true = np.asarray(true, dtype=float)
    valid = np.isfinite(est).all(axis=1)
    valid &= est[:, 0] > 0
    valid &= est[:, 1] > 0
    out = np.full(len(est), np.nan, dtype=float)
    if valid.any():
        e_beta = (est[valid, 0] - true[valid, 0]) / true[valid, 0]
        e_eta = (est[valid, 1] - true[valid, 1]) / true[valid, 1]
        e_gamma = (est[valid, 2] - true[valid, 2]) / true[valid, 1]
        out[valid] = (e_beta**2 + e_eta**2 + e_gamma**2) / 3.0
    if np.isfinite(failure_penalty):
        out[~valid] = float(failure_penalty) ** 2
    return out


def l_param_from_row_loss(row_loss):
    values = np.asarray(row_loss, dtype=float)
    values = values[np.isfinite(values)]
    return float(np.sqrt(np.mean(values))) if values.size else float("nan")


def compute_l_param(est, true, eta_true=None):
    del eta_true  # retained for compatibility with the earlier local API
    return l_param_from_row_loss(row_squared_composite_loss(est, true))

def evaluate_model(model, eval_feat, eval_targ_raw, eval_samples):
    model.eval(); device = torch.device("cpu")
    model = model.to(device); eval_feat = eval_feat.to(device)
    with torch.no_grad(): raw = model(eval_feat).numpy()
    est = decode_predictions(raw, eval_samples)
    row_loss = row_squared_composite_loss(est, eval_targ_raw)
    l_param = l_param_from_row_loss(row_loss)
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
            "estimates": est, "row_loss": row_loss, "pt_ids": None}


def bootstrap_ci(values, n_boot=2000, seed=520001):
    """Ordinary scalar bootstrap retained for small diagnostic tests only."""
    rng = np.random.default_rng(seed)
    boots = np.array([np.mean(rng.choice(values, len(values), replace=True)) for _ in range(n_boot)])
    return float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5)), float(np.mean(values))


def aggregate_seeds(eval_results: list[dict]) -> dict:
    """Aggregate 3 seeds: mean L_param, seed SD, per-param stats."""
    lp = np.array([r["l_param"] for r in eval_results])
    return {"l_param_mean": float(np.mean(lp)), "l_param_sd": float(np.std(lp, ddof=1)),
            "l_param_seeds": lp.tolist(), "n_seeds": len(eval_results)}


def _arm_l_param(row_losses: list[np.ndarray], row_idx: np.ndarray, seed_idx: np.ndarray) -> float:
    return float(np.mean([
        l_param_from_row_loss(np.asarray(row_losses[int(i)])[row_idx])
        for i in seed_idx
    ]))


def paired_cluster_effect(
    reference_losses: list[np.ndarray],
    alternative_losses: list[np.ndarray],
    pt_ids: np.ndarray,
    *,
    mode: str,
    n_boot: int = 2000,
    seed: int = 520001,
) -> dict:
    """Paired point-cluster bootstrap with training seed as a second level.

    ``mode='relative_improvement'`` returns ``(reference-alternative)/reference``.
    ``mode='difference'`` returns ``alternative-reference``.
    """
    pt_ids = np.asarray(pt_ids)
    clusters = np.unique(pt_ids)
    all_rows = np.arange(len(pt_ids))
    ref_observed = _arm_l_param(
        reference_losses, all_rows, np.arange(len(reference_losses)))
    alt_observed = _arm_l_param(
        alternative_losses, all_rows, np.arange(len(alternative_losses)))

    def effect(ref_value, alt_value):
        if mode == "relative_improvement":
            return (ref_value - alt_value) / max(abs(ref_value), 1e-12)
        if mode == "difference":
            return alt_value - ref_value
        raise ValueError(f"unknown effect mode: {mode}")

    observed = effect(ref_observed, alt_observed)
    rng = np.random.default_rng(seed)
    boot = np.empty(int(n_boot), dtype=float)
    rows_by_cluster = {int(c): np.flatnonzero(pt_ids == c) for c in clusters}
    for b in range(int(n_boot)):
        sampled_clusters = rng.choice(clusters, size=len(clusters), replace=True)
        row_idx = np.concatenate([rows_by_cluster[int(c)] for c in sampled_clusters])
        ref_seed_idx = rng.integers(0, len(reference_losses), size=len(reference_losses))
        alt_seed_idx = rng.integers(0, len(alternative_losses), size=len(alternative_losses))
        boot[b] = effect(
            _arm_l_param(reference_losses, row_idx, ref_seed_idx),
            _arm_l_param(alternative_losses, row_idx, alt_seed_idx),
        )
    return {
        "effect": float(observed),
        "ci_lower": float(np.percentile(boot, 2.5)),
        "ci_upper": float(np.percentile(boot, 97.5)),
        "n_parameter_points": int(len(clusters)),
        "n_bootstrap": int(n_boot),
        "mode": mode,
    }


def is_plateau(effect: Mapping[str, float], threshold: float = 0.02) -> bool:
    """Preregistered A5 plateau rule: small gain and CI crosses zero."""
    return (
        float(effect["effect"]) < float(threshold)
        and float(effect["ci_lower"]) <= 0.0 <= float(effect["ci_upper"])
    )


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
                if beta <= 0 or eta <= 0 or gamma >= float(np.min(sample)): return None
                return (beta, eta, gamma)
        elif method_name == "WMLE":
            from methods.wmle import WMLE
            result = WMLE(sample).run()
            # [gamma, beta, alpha(scale=eta), r2] — REORDER to (beta, eta, gamma)
            if isinstance(result, (list, tuple)) and len(result) >= 4:
                gamma_w, beta_w, alpha_w = float(result[0]), float(result[1]), float(result[2])
                if not (np.isfinite(beta_w) and np.isfinite(alpha_w) and np.isfinite(gamma_w)):
                    return None
                if beta_w <= 0 or alpha_w <= 0 or gamma_w >= float(np.min(sample)): return None
                return (beta_w, alpha_w, gamma_w)
        elif method_name == "MPS":
            from methods.mps import MPS
            result = MPS(sample).run()
            if isinstance(result, (list, tuple)) and len(result) >= 3:
                beta, eta, gamma = float(result[0]), float(result[1]), float(result[2])
                if not (np.isfinite(beta) and np.isfinite(eta) and np.isfinite(gamma)):
                    return None
                if beta <= 0 or eta <= 0 or gamma >= float(np.min(sample)): return None
                return (beta, eta, gamma)
        elif method_name == "MDM":
            from methods.mdm import MDM
            result = MDM(sample).run(offset=0.1)
            if isinstance(result, (list, tuple)) and len(result) >= 5:
                beta, eta, gamma, _, success = (float(result[0]), float(result[1]),
                                                float(result[2]), result[3], result[4])
                if not success or not (np.isfinite(beta) and np.isfinite(eta) and np.isfinite(gamma)):
                    return None
                if beta <= 0 or eta <= 0 or gamma >= float(np.min(sample)): return None
                return (beta, eta, gamma)
        elif method_name == "LRE":
            from methods.lre import LRE
            result = LRE(sample).run()
            if isinstance(result, (list, tuple)) and len(result) >= 5:
                beta, eta, gamma, _, success = (float(result[0]), float(result[1]),
                                                float(result[2]), result[3], result[4])
                if not success or not (np.isfinite(beta) and np.isfinite(eta) and np.isfinite(gamma)):
                    return None
                if beta <= 0 or eta <= 0 or gamma >= float(np.min(sample)): return None
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
    failure_penalty = float(config["A13_oracle"]["failure_penalty"])
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
        valid_r = np.isfinite(raw_est).all(axis=1)
        valid_c = np.isfinite(clipped_est).all(axis=1)
        raw_conditional = row_squared_composite_loss(raw_est, conf_targets)
        clipped_conditional = row_squared_composite_loss(clipped_est, conf_targets)
        raw_unconditional = row_squared_composite_loss(
            raw_est, conf_targets, failure_penalty=failure_penalty)
        clipped_unconditional = row_squared_composite_loss(
            clipped_est, conf_targets, failure_penalty=failure_penalty)
        results[name] = {
            "raw_l_param": (
                l_param_from_row_loss(raw_conditional) if valid_r.any() else None),
            "clipped_l_param": (
                l_param_from_row_loss(clipped_conditional) if valid_c.any() else None),
            "raw_l_param_unconditional": l_param_from_row_loss(raw_unconditional),
            "clipped_l_param_unconditional": l_param_from_row_loss(clipped_unconditional),
            "raw_failure_rate": raw_fail / max(conf_samples.shape[0], 1),
            "clipped_failure_rate": clipped_fail / max(conf_samples.shape[0], 1),
            "raw_n_valid": int(valid_r.sum()), "clipped_n_valid": int(valid_c.sum()),
            "raw_row_loss": raw_unconditional,
            "clipped_row_loss": clipped_unconditional,
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


def write_confirmation_source(base, results, a13, pt_ids):
    """Write compact row-level losses needed to reproduce clustered summaries."""
    path = base / "confirmation_source.csv.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["arm", "seed", "row", "parameter_point", "row_loss"])
        writer.writeheader()
        for arm, record in results.items():
            if arm == "A13":
                continue
            seed = arm.rsplit("/s", 1)[-1]
            for row, (point, loss) in enumerate(zip(pt_ids, record["row_loss"])):
                writer.writerow({
                    "arm": arm, "seed": seed, "row": row,
                    "parameter_point": int(point), "row_loss": float(loss),
                })
        for method, record in a13.items():
            for variant in ("raw", "clipped"):
                for row, (point, loss) in enumerate(zip(
                    pt_ids, record[f"{variant}_row_loss"]
                )):
                    writer.writerow({
                        "arm": f"A13/{method}/{variant}", "seed": "",
                        "row": row, "parameter_point": int(point),
                        "row_loss": float(loss),
                    })
    return path


def run_pilot(config):
    """Two representative fits in pilot/ with a 10-epoch diagnostic cap."""
    base = Path(config["output_root"])
    print("=== PILOT ==="); t0 = time.time()
    pilot_config = json.loads(json.dumps(config))
    pilot_config["baseline"]["epochs"] = {"max": 10, "min": 5, "patience": 5}
    val_samples, val_targets, _ = generate_role_data(pilot_config, "validation")
    val_feat = torch.tensor(preprocess_v_route(val_samples), dtype=torch.float32)
    val_targ = torch.tensor(prepare_targets(val_samples, val_targets), dtype=torch.float32)

    # A5 pilot
    _, tr_s, tr_t = generate_pool(pilot_config, prefix_size=25000)
    tf = torch.tensor(preprocess_v_route(tr_s), dtype=torch.float32)
    tt_t = torch.tensor(prepare_targets(tr_s, tr_t), dtype=torch.float32)
    out = _output_dir(base, "A5", "25000", 720001, PILOT_PREFIX)
    model = _make_model(pilot_config)
    r = train_one_fit(
        model, tf, tt_t, val_feat, val_targ, pilot_config, 720001, out,
        arm="pilot/A5/25000",
    )
    print(f"  A5/25000: epoch={r['best_epoch']} val={r['best_val_loss']:.4f}")

    # A6 pilot
    _, tr_s2, tr_t2 = generate_pool(pilot_config, prefix_size=7000)
    tf2 = torch.tensor(preprocess_v_route(tr_s2), dtype=torch.float32)
    tt_t2 = torch.tensor(prepare_targets(tr_s2, tr_t2), dtype=torch.float32)
    out2 = _output_dir(base, "A6", "core_continuous", 720011, PILOT_PREFIX)
    model2 = _make_model(pilot_config)
    r2 = train_one_fit(
        model2, tf2, tt_t2, val_feat, val_targ, pilot_config, 720011, out2,
        arm="pilot/A6/core_continuous",
    )
    print(f"  A6/core_continuous: epoch={r2['best_epoch']} val={r2['best_val_loss']:.4f}")

    t = time.time() - t0
    print(f"PILOT done: {t:.1f}s (~{t/60:.1f} min)")
    return t


def run_full(config):
    """21 fits with valid resume check."""
    base = Path(config["output_root"])
    print("=== FULL (21 fits) ==="); t0 = time.time()
    cfg_sha = config_sha256(config)
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
            arm = f"A5/{size}"
            if can_resume(
                out, model, n_rows, expected_seed=seed, expected_arm=arm,
                expected_config_sha256=cfg_sha,
            ):
                print(f"  A5/{size}/s{seed}: RESUME (valid)")
                continue
            r = train_one_fit(
                model, tf, tt_t, val_feat, val_targ, config, seed, out, arm=arm)
            print(f"  A5/{size}/s{seed}: epoch={r['best_epoch']} val={r['best_val_loss']:.4f}")

    for dist_name in config["A6_distributions"]:
        _, tr_s, tr_t = generate_pool(config, prefix_size=config["A6_training_rows"], dist_name=dist_name)
        tf = torch.tensor(preprocess_v_route(tr_s), dtype=torch.float32)
        tt_t = torch.tensor(prepare_targets(tr_s, tr_t), dtype=torch.float32)
        n_rows = tr_s.shape[0]
        for seed in config["A6_seeds"]:
            out = _output_dir(base, "A6", dist_name, seed)
            model = _make_model(config)
            arm = f"A6/{dist_name}"
            if can_resume(
                out, model, n_rows, expected_seed=seed, expected_arm=arm,
                expected_config_sha256=cfg_sha,
            ):
                print(f"  A6/{dist_name}/s{seed}: RESUME (valid)")
                continue
            r = train_one_fit(
                model, tf, tt_t, val_feat, val_targ, config, seed, out, arm=arm)
            print(f"  A6/{dist_name}/s{seed}: epoch={r['best_epoch']} val={r['best_val_loss']:.4f}")

    t = time.time() - t0
    print(f"FULL done: {t:.1f}s (~{t/60:.1f} min)")
    return t


def run_confirmation(config):
    """Evaluate all 21 preregistered arms on conf split. Fails if any fit missing."""
    base = Path(config["output_root"])
    cfg_sha = config_sha256(config)
    conf_samples, conf_targets, pt_ids = generate_role_data(config, "confirmation")
    conf_feat = torch.tensor(preprocess_v_route(conf_samples), dtype=torch.float32)

    # Check completeness: all 21 fits must be present + valid
    missing = []
    for size in config["A5_training_sizes"]:
        for seed in config["A5_training_seeds"]:
            out = _output_dir(base, "A5", str(size), seed)
            if not can_resume(
                out, _make_model(config), int(size), expected_seed=seed,
                expected_arm=f"A5/{size}", expected_config_sha256=cfg_sha,
            ):
                missing.append(f"A5/{size}/s{seed}")
    for dist_name in config["A6_distributions"]:
        for seed in config["A6_seeds"]:
            out = _output_dir(base, "A6", dist_name, seed)
            if not can_resume(
                out, _make_model(config), int(config["A6_training_rows"]),
                expected_seed=seed, expected_arm=f"A6/{dist_name}",
                expected_config_sha256=cfg_sha,
            ):
                missing.append(f"A6/{dist_name}/s{seed}")

    if missing:
        raise RuntimeError(
            f"CONFIRMATION REFUSED: {len(missing)} fit(s) missing/invalid: {missing}. "
            "No partial confirmation saved."
        )

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
        smaller_losses = [
            results[f"A5/{sizes[i]}/s{s}"]["row_loss"]
            for s in config["A5_training_seeds"]
        ]
        larger_losses = [
            results[f"A5/{sizes[i+1]}/s{s}"]["row_loss"]
            for s in config["A5_training_seeds"]
        ]
        effect = paired_cluster_effect(
            smaller_losses, larger_losses, pt_ids,
            mode="relative_improvement",
            n_boot=int(config["metrics"]["bootstrap"]["replicates"]),
            seed=int(config["metrics"]["bootstrap"]["seed"]) + i,
        )
        effect["plateau"] = is_plateau(effect)
        agg[f"A5_plateau_{sizes[i]}_to_{sizes[i+1]}"] = effect

    # A6: paired dist vs core_continuous
    core_losses = [
        results[f"A6/core_continuous/s{s}"]["row_loss"]
        for s in config["A6_seeds"]
    ]
    for dist_name in config["A6_distributions"]:
        if dist_name == "core_continuous": continue
        dist_losses = [
            results[f"A6/{dist_name}/s{s}"]["row_loss"]
            for s in config["A6_seeds"]
        ]
        agg[f"A6_{dist_name}_vs_core"] = paired_cluster_effect(
            core_losses, dist_losses, pt_ids, mode="difference",
            n_boot=int(config["metrics"]["bootstrap"]["replicates"]),
            seed=int(config["metrics"]["bootstrap"]["seed"]) + 100,
        )

    # A13: range-prior effect and comparison to the preregistered 100k NN arm.
    comparator = config["A13_oracle"]["nn_comparator"]
    nn_losses = [
        results[
            f"{comparator['arm']}/{comparator['training_size']}/s{seed}"
        ]["row_loss"]
        for seed in comparator["seeds"]
    ]
    a13_agg = {
        "nn_comparator": comparator,
        "nn_l_param_mean": _arm_l_param(
            nn_losses, np.arange(len(pt_ids)), np.arange(len(nn_losses))),
        "methods": {},
    }
    for method_index, (method, record) in enumerate(a13.items()):
        raw = [record["raw_row_loss"]]
        clipped = [record["clipped_row_loss"]]
        a13_agg["methods"][method] = {
            "raw_vs_clipped_relative_improvement": paired_cluster_effect(
                raw, clipped, pt_ids, mode="relative_improvement",
                n_boot=int(config["metrics"]["bootstrap"]["replicates"]),
                seed=int(config["metrics"]["bootstrap"]["seed"]) + 200 + method_index,
            ),
            "raw_minus_nn": paired_cluster_effect(
                nn_losses, raw, pt_ids, mode="difference",
                n_boot=int(config["metrics"]["bootstrap"]["replicates"]),
                seed=int(config["metrics"]["bootstrap"]["seed"]) + 300 + method_index,
            ),
            "clipped_minus_nn": paired_cluster_effect(
                nn_losses, clipped, pt_ids, mode="difference",
                n_boot=int(config["metrics"]["bootstrap"]["replicates"]),
                seed=int(config["metrics"]["bootstrap"]["seed"]) + 400 + method_index,
            ),
        }
    agg["A13"] = a13_agg
    source_path = write_confirmation_source(base, results, a13, pt_ids)

    summary_path = base / "confirmation_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump({"results": {k: {kk: vv for kk, vv in v.items()
                                  if kk not in {"estimates", "row_loss", "pt_ids"}}
                               for k, v in results.items() if k != "A13"},
                   "A13": {
                       method: {k: v for k, v in record.items()
                                if k not in {"raw_row_loss", "clipped_row_loss"}}
                       for method, record in a13.items()
                   },
                   "aggregation": agg,
                   "source_table": str(source_path)},
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
