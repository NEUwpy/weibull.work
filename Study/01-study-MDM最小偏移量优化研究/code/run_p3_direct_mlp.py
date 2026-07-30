"""P3 Direct-MLP: scale-equivariant direct Weibull parameter estimation.

ARCHITECTURE (frozen before testing)
=====================================

Scale equivariance: the network predicts dimensionless shape parameters and a
scale ratio, so that scaling a sample by c correctly scales eta_hat by c.

Network output (3-dim, raw):
    z = (z_beta, z_eta_ratio, z_goe)   ← network raw output

Decode (network → params):
    beta_hat   = softplus(z_beta)               # shape, always > 0
    eta_ratio  = softplus(z_eta_ratio)           # eta / x_bar (dimensionless)
    eta_hat    = eta_ratio * x_bar               # scale, uses sample feature
    goe_hat    = relu(z_goe)                     # gamma / eta (dimensionless)
    gamma_hat  = goe_hat * eta_hat               # derived

Scale equivariance proof:
    If sample is scaled by c, then x_bar → c * x_bar.
    Network input features (z-scored) change for scale-dependent cols,
    but the network's output is based on shape info.
    eta_hat = eta_ratio * (c * x_bar) = c * (eta_ratio * x_bar) = c * eta_hat_original.
    beta_hat, goe_hat are shape parameters, unaffected by scale.
    → beta_hat, eta_hat (scaled), gamma_hat (scaled) are all correct.

Training target (encode):
    Encode true params to network target space:
    z_beta_target       = inverse_softplus(beta_true)
    z_eta_ratio_target  = inverse_softplus(eta_true / x_bar)
    z_goe_target        = gamma_true / eta_true

Training loss (J1-compatible):
    The network minimizes MSE in the *decoded relative-error* space.
    After decoding predictions, we compute:
        loss = (beta_hat - beta_true)² / beta_true²
             + (eta_hat - eta_true)²  / eta_true²
             + (gamma_hat - gamma_true)² / eta_true²
    This is exactly J1² per sample. The PyTorch training loop computes this
    loss with autograd, so the network's gradient is J1-compatible.

MLP backbone: 256-128-64 (identical to Vector-MLP), ReLU, Adam.

Reuses E4 infrastructure: _fit_zscore_params, _build_X_from_samples,
get_combo_split, compute_sample_features, generate_sample.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import torch.nn as nn
import torch.optim as optim
from sklearn.preprocessing import StandardScaler

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import run_E4_formal_validation as e4
import p3_config as cfg


# ════════════════════════════════════════════════════════════════════════
# Output transforms
# ════════════════════════════════════════════════════════════════════════

def _softplus(x):
    """Numerically stable softplus."""
    return torch.where(x > 20, x, torch.log1p(torch.exp(torch.clamp(x, -50, 20))))


def _softplus_np(x: np.ndarray) -> np.ndarray:
    return np.where(x > 20, x, np.log1p(np.exp(np.clip(x, -50, 20))))


def _inverse_softplus_np(y: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    y_clipped = np.maximum(y, eps)
    return np.log(np.expm1(np.clip(y_clipped, eps, 50)))


def decode_output(z: np.ndarray, x_bar: np.ndarray) -> np.ndarray:
    """Decode network raw output to constrained params.

    Parameters
    ----------
    z : [N, 3] raw network output (z_beta, z_eta_ratio, z_goe)
    x_bar : [N] sample mean from features (scale anchor)

    Returns
    -------
    [N, 3] with (beta_hat, eta_hat, gamma_hat)
    """
    beta_hat = _softplus_np(z[:, 0])
    eta_ratio = _softplus_np(z[:, 1])
    eta_hat = eta_ratio * x_bar
    goe_hat = np.maximum(z[:, 2], 0.0)
    gamma_hat = goe_hat * eta_hat
    return np.column_stack([beta_hat, eta_hat, gamma_hat])


def encode_targets(params: np.ndarray, x_bar: np.ndarray) -> np.ndarray:
    """Encode true params to network target space.

    Parameters
    ----------
    params : [N, 3] true (beta, eta, gamma)
    x_bar : [N] sample mean from features

    Returns
    -------
    [N, 3] encoded targets (z_beta, z_eta_ratio, z_goe)
    """
    beta = params[:, 0]
    eta = params[:, 1]
    gamma = params[:, 2]
    goe = gamma / eta  # gamma over eta

    z_beta = _inverse_softplus_np(beta)
    z_eta_ratio = _inverse_softplus_np(eta / x_bar)
    z_goe = goe  # relu on decode; already >= 0

    return np.column_stack([z_beta, z_eta_ratio, z_goe])


# ════════════════════════════════════════════════════════════════════════
# PyTorch model (minimal, frozen architecture)
# ════════════════════════════════════════════════════════════════════════

class DirectMLP(nn.Module):
    """256-128-64 MLP with ReLU, outputs 3 raw values."""

    def __init__(self, input_dim: int = 13, hidden: tuple = (256, 128, 64)):
        super().__init__()
        layers = []
        prev = input_dim
        for h in hidden:
            layers.append(nn.Linear(prev, h))
            layers.append(nn.ReLU())
            prev = h
        layers.append(nn.Linear(prev, 3))
        self.net = nn.Sequential(*layers)

    def forward(self, x):
        return self.net(x)


def _init_seed(seed: int):
    torch.manual_seed(seed)
    np.random.seed(seed)


# ════════════════════════════════════════════════════════════════════════
# Training with J1-compatible loss
# ════════════════════════════════════════════════════════════════════════

def train_direct_mlp(
    X_train: np.ndarray,
    Y_train_raw: np.ndarray,
    x_bar_train: np.ndarray,
    seed: int,
    max_iter: int = 300,
    lr: float = 1e-3,
    batch_size: int = 256,
    val_fraction: float = 0.15,
    patience: int = 20,
) -> tuple[DirectMLP, dict]:
    """Train one Direct-MLP with J1-compatible loss.

    The loss is computed in decoded parameter space:
        L = mean_j [ (bh-b)^2/b^2 + (eh-e)^2/e^2 + (gh-g)^2/e^2 ]
    where j indexes the 3 params. This is J1²/N per sample.

    Returns (model, training_info)
    """
    _init_seed(seed)
    n = len(X_train)

    # Encode targets
    Z_train = encode_targets(Y_train_raw, x_bar_train)

    # Standardize input features (X is already z-scored by E4 pipeline)
    # and targets
    x_mean = X_train.mean(axis=0)
    x_std = X_train.std(axis=0)
    x_std[x_std < 1e-12] = 1.0

    z_mean = Z_train.mean(axis=0)
    z_std = Z_train.std(axis=0)
    z_std[z_std < 1e-12] = 1.0

    X_norm = (X_train - x_mean) / x_std
    Z_norm = (Z_train - z_mean) / z_std

    # Convert to tensors
    X_t = torch.FloatTensor(X_norm)
    x_bar_t = torch.FloatTensor(x_bar_train)
    Y_t = torch.FloatTensor(Y_train_raw)

    # Split train/val
    n_val = max(1, int(n * val_fraction))
    perm = torch.randperm(n)
    val_idx = perm[:n_val]
    tr_idx = perm[n_val:]

    model = DirectMLP(input_dim=X_train.shape[1])
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=cfg.DIRECT_MLP_ALPHA)

    best_val_loss = float('inf')
    best_state = None
    no_improve = 0
    n_iter = 0

    for epoch in range(max_iter):
        # Train
        model.train()
        train_perm = tr_idx[torch.randperm(len(tr_idx))]
        for start in range(0, len(train_perm), batch_size):
            idx = train_perm[start:start + batch_size]
            optimizer.zero_grad()
            z_norm_pred = model(X_t[idx])
            z_pred = z_norm_pred * torch.FloatTensor(z_std) + torch.FloatTensor(z_mean)

            # Decode predictions
            beta_pred = _softplus(z_pred[:, 0])
            eta_ratio_pred = _softplus(z_pred[:, 1])
            eta_pred = eta_ratio_pred * x_bar_t[idx]
            goe_pred = torch.clamp(z_pred[:, 2], min=0.0)
            gamma_pred = goe_pred * eta_pred

            # J1-compatible loss (per-sample, then mean)
            beta_true = Y_t[idx, 0]
            eta_true = Y_t[idx, 1]
            gamma_true = Y_t[idx, 2]

            loss = ((beta_pred - beta_true) / beta_true) ** 2 \
                 + ((eta_pred - eta_true) / eta_true) ** 2 \
                 + ((gamma_pred - gamma_true) / eta_true) ** 2
            loss = loss.mean()

            loss.backward()
            optimizer.step()

        # Validate
        model.eval()
        with torch.no_grad():
            z_pred = model(X_t[val_idx]) * torch.FloatTensor(z_std) + torch.FloatTensor(z_mean)
            beta_pred = _softplus(z_pred[:, 0])
            eta_ratio_pred = _softplus(z_pred[:, 1])
            eta_pred = eta_ratio_pred * x_bar_t[val_idx]
            goe_pred = torch.clamp(z_pred[:, 2], min=0.0)
            gamma_pred = goe_pred * eta_pred

            val_loss = ((beta_pred - Y_t[val_idx, 0]) / Y_t[val_idx, 0]) ** 2 \
                     + ((eta_pred - Y_t[val_idx, 1]) / Y_t[val_idx, 1]) ** 2 \
                     + ((gamma_pred - Y_t[val_idx, 2]) / Y_t[val_idx, 2]) ** 2
            val_loss = val_loss.mean().item()

        n_iter = epoch + 1
        if val_loss < best_val_loss - 1e-6:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break

    # Restore best model
    if best_state is not None:
        model.load_state_dict(best_state)

    info = {
        "n_iter": n_iter,
        "best_val_loss": best_val_loss,
        "x_mean": x_mean,
        "x_std": x_std,
        "z_mean": z_mean,
        "z_std": z_std,
    }
    return model, info


def predict_direct_mlp(
    model: DirectMLP,
    info: dict,
    X_eval: np.ndarray,
    x_bar_eval: np.ndarray,
) -> np.ndarray:
    """Predict (beta_hat, eta_hat, gamma_hat) for evaluation samples."""
    X_norm = (X_eval - info["x_mean"]) / info["x_std"]
    X_t = torch.FloatTensor(X_norm)
    model.eval()
    with torch.no_grad():
        z_norm = model(X_t).numpy()
    z = z_norm * info["z_std"] + info["z_mean"]
    return decode_output(z, x_bar_eval)


# ════════════════════════════════════════════════════════════════════════
# Per-sample loss (identical to J1 parameter normalization)
# ════════════════════════════════════════════════════════════════════════

def compute_param_loss(beta_hat, beta, eta_hat, eta, gamma_hat, gamma):
    """J1² per sample: ((bh-b)/b)² + ((eh-e)/e)² + ((gh-g)/e)²"""
    e_beta = (beta_hat - beta) / beta
    e_eta = (eta_hat - eta) / eta
    e_gamma = (gamma_hat - gamma) / eta
    return e_beta ** 2 + e_eta ** 2 + e_gamma ** 2


# ════════════════════════════════════════════════════════════════════════
# Build training data using E4's proven functions directly
# ════════════════════════════════════════════════════════════════════════

def build_training_data(df_features, train_combos):
    """Build X_train, Y_train, x_bar_train using E4 functions."""
    mask = df_features.apply(
        lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in train_combos, axis=1
    )
    df_train = df_features[mask].copy()

    # Verify no forbidden fields
    for forbidden in cfg.FORBIDDEN_INPUT_FIELDS:
        assert forbidden not in e4.SAMPLE_FEATURE_COLS, f"Forbidden '{forbidden}' in features"

    # Use E4's functions directly
    means, stds = e4._fit_zscore_params(df_train)
    X_train = e4._build_X_from_samples(df_train, means, stds)

    # Build Y: true (beta, eta, gamma)
    Y_train = df_train[["beta", "eta", "gamma"]].values.astype(np.float64)

    # Extract x_bar for scale-equivariant decode
    x_bar_train = df_train["x_bar"].values.astype(np.float64)

    meta = {
        "n_train_samples": len(df_train),
        "zscore_means": means,
        "zscore_stds": stds,
    }
    return X_train, Y_train, x_bar_train, meta


# ════════════════════════════════════════════════════════════════════════
# Per-fold failure penalty (ALL 26 delta points, not just delta=0.1)
# ════════════════════════════════════════════════════════════════════════

def compute_fold_penalty(df_features, df_risk, train_combos):
    """Compute P99 penalty from ALL 26 delta points in the training fold.

    Parameters
    ----------
    df_features : sample_features DataFrame
    df_risk : risk_curves DataFrame with loss_d{0.00..0.50} columns
    train_combos : list of (beta, gamma_over_eta, n)

    Returns
    -------
    float: P99 of all valid per-sample losses across all 26 deltas
    """
    mask = df_features.apply(
        lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in train_combos, axis=1
    )
    df_train = df_features[mask]

    train_keys = set(zip(
        df_train["beta"].astype(float),
        df_train["gamma_over_eta"].astype(float),
        df_train["n"].astype(int),
        df_train["repeat_id"].astype(int),
    ))

    # Collect ALL 26 delta losses for training samples
    loss_cols = [c for c in df_risk.columns if c.startswith("loss_d")]
    assert len(loss_cols) == 26, f"Expected 26 loss columns, got {len(loss_cols)}"

    all_losses = []
    for _, row in df_risk.iterrows():
        key = (
            float(row["beta"]),
            float(row["gamma_over_eta"]),
            int(row["n"]),
            int(row["repeat_id"]),
        )
        if key in train_keys:
            for col in loss_cols:
                val = float(row[col])
                if not np.isnan(val):
                    all_losses.append(val)

    if not all_losses:
        raise ValueError(
            "No valid training losses found for penalty computation. "
            "Cannot fall back to arbitrary penalty."
        )

    return float(np.nanpercentile(all_losses, 99))


# ════════════════════════════════════════════════════════════════════════
# Full training loop
# ════════════════════════════════════════════════════════════════════════

def train_one_model(df_features, fold, seed):
    """Train one Direct-MLP model for a given fold and seed."""
    X_train, Y_train, x_bar_train, meta = build_training_data(
        df_features, fold["train_combos"]
    )
    t0 = time.time()
    model, info = train_direct_mlp(X_train, Y_train, x_bar_train, seed)
    elapsed = time.time() - t0
    return model, info, meta, elapsed


# ════════════════════════════════════════════════════════════════════════
# Evaluation
# ════════════════════════════════════════════════════════════════════════

def evaluate_on_samples(model, info, df_eval, means, stds,
                        fold_name, seed, failure_penalty):
    """Evaluate Direct-MLP on a set of samples."""
    X_eval = e4._build_X_from_samples(df_eval, means, stds)
    x_bar_eval = df_eval["x_bar"].values.astype(np.float64)
    preds = predict_direct_mlp(model, info, X_eval, x_bar_eval)

    rows = []
    for i in range(len(df_eval)):
        row = df_eval.iloc[i]
        beta = float(row["beta"])
        eta = float(row["eta"])
        gamma = float(row["gamma"])
        goe = float(row["gamma_over_eta"])
        n_val = int(row["n"])
        rid = int(row["repeat_id"])

        beta_hat, eta_hat, gamma_hat = float(preds[i, 0]), float(preds[i, 1]), float(preds[i, 2])

        if not all(np.isfinite([beta_hat, eta_hat, gamma_hat])):
            rows.append({
                "fold": fold_name, "seed": seed, "method": "Direct-MLP",
                "beta": beta, "gamma_over_eta": goe, "n": n_val, "repeat_id": rid,
                "beta_hat": 0.0, "eta_hat": 0.0, "gamma_hat": 0.0,
                "true_loss": float("nan"),
                "failed": True, "failure_reason": "nan_prediction",
                "failure_penalty": failure_penalty,
            })
            continue

        loss = compute_param_loss(beta_hat, beta, eta_hat, eta, gamma_hat, gamma)
        rows.append({
            "fold": fold_name, "seed": seed, "method": "Direct-MLP",
            "beta": beta, "gamma_over_eta": goe, "n": n_val, "repeat_id": rid,
            "beta_hat": beta_hat, "eta_hat": eta_hat, "gamma_hat": gamma_hat,
            "true_loss": loss,
            "failed": False, "failure_reason": "",
            "failure_penalty": failure_penalty,
        })
    return rows


# ════════════════════════════════════════════════════════════════════════
# Verification
# ════════════════════════════════════════════════════════════════════════

def verify_output_constraints(preds):
    if preds.shape[1] != 3:
        return False
    return bool(np.all(preds[:, 0] > 0) and np.all(preds[:, 1] > 0) and np.all(preds[:, 2] >= 0))


def verify_scale_equivariance(preds1, preds2, scale_factor, atol=1e-4):
    """Verify that scaling input by c scales eta and gamma by c, beta unchanged.

    preds1: predictions on original samples
    preds2: predictions on scaled samples (x * c)
    scale_factor: the scaling factor c
    """
    beta_ok = np.allclose(preds1[:, 0], preds2[:, 0], atol=atol)
    eta_ok = np.allclose(preds1[:, 1] * scale_factor, preds2[:, 1], atol=atol * scale_factor)
    gamma_ok = np.allclose(preds1[:, 2] * scale_factor, preds2[:, 2], atol=atol * scale_factor)
    return bool(beta_ok and eta_ok and gamma_ok)


def config_hash():
    contract = cfg.production_contract()
    contract["seeds"] = list(contract["seeds"])
    contract["hidden_layers"] = list(contract["hidden_layers"])
    contract["feature_columns"] = list(contract["feature_columns"])
    contract["feature_zscore_cols"] = list(contract["feature_zscore_cols"])
    contract["feature_raw_cols"] = list(contract["feature_raw_cols"])
    raw = json.dumps(contract, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
