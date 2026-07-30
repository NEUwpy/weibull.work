"""P3 Direct-MLP: fully scale-invariant direct Weibull parameter estimation.

ARCHITECTURE (frozen before testing)
=====================================

FULL SCALE INVARIANCE: the network consumes only scale-invariant features.
The 9 scale-dependent feature columns (x_min, x_max, range, Q1, Med, Q3,
IQR, x_bar, s) are divided by x_bar BEFORE train-fold-only standardization.
After normalization, n, CV, g1, g2 remain unchanged.
x_bar itself becomes 1.0 in the network input, so the network cannot see
absolute scale. x_bar is only used OUTSIDE the network to recover eta/gamma.

Feature pipeline:
    raw features → scale_invariant_transform → train-fold z-score → network

Network output (3-dim, raw):
    z = (z_beta, z_eta_ratio, z_goe)

Decode (network → params):
    beta_hat   = softplus(z_beta)               # shape, always > 0
    eta_ratio  = softplus(z_eta_ratio)           # eta / x_bar (dimensionless)
    eta_hat    = eta_ratio * x_bar               # scale, from sample feature
    goe_hat    = relu(z_goe)                     # gamma / eta (dimensionless)
    gamma_hat  = goe_hat * eta_hat               # derived

Scale invariance proof:
    If sample is scaled by c:
    - All 9 scale cols scale by c, x_bar scales by c → ratios unchanged
    - n, CV, g1, g2 unchanged
    → Network input is IDENTICAL → network output is IDENTICAL
    → beta_hat unchanged, eta_ratio unchanged
    → eta_hat = eta_ratio * (c * x_bar) = c * original_eta_hat ✓
    → gamma_hat = goe_hat * c * original_eta_hat = c * original_gamma_hat ✓

Training loss (shared j1_loss_torch):
    L = mean_i [ ((bh-b)/b)^2 + ((eh-e)/e)^2 + ((gh-g)/e)^2 ]
    gamma denominator = eta_true (NOT gamma_true, NOT eta_hat)

MLP backbone: 256-128-64 (identical to Vector-MLP), ReLU, Adam.
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

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import run_E4_formal_validation as e4
import p3_config as cfg


# ════════════════════════════════════════════════════════════════════════
# Custom exceptions for production contracts (replaces assert)
# ════════════════════════════════════════════════════════════════════════

class SchemaError(ValueError):
    """Prediction DataFrame or risk curve schema violation."""


class CoverageError(ValueError):
    """Six-method fold×seed coverage violation."""


class PenaltyError(ValueError):
    """Failure penalty computation or application violation."""


# ════════════════════════════════════════════════════════════════════════
# Scale-invariant feature transform
# ════════════════════════════════════════════════════════════════════════

SCALE_DEPENDENT_COLS = ["x_min", "x_max", "range", "Q1", "Med", "Q3", "IQR", "x_bar", "s"]
SCALE_INVARIANT_COLS = ["n", "CV", "g1", "g2"]
assert SCALE_DEPENDENT_COLS == list(e4.FEATURE_COLS_ZSCORE), \
    "Scale-dependent cols must match E4 z-score cols"
assert SCALE_INVARIANT_COLS == list(e4.FEATURE_COLS_RAW), \
    "Scale-invariant cols must match E4 raw cols"


def make_scale_invariant(df_features: pd.DataFrame) -> pd.DataFrame:
    """Divide 9 scale-dependent cols by x_bar, producing dimensionless ratios.

    After this transform:
    - x_bar itself becomes 1.0 (scale information removed from features)
    - All 9 scale cols become ratios (x_min/x_bar, s/x_bar, etc.)
    - n, CV, g1, g2 are unchanged

    The same sample scaled by c produces IDENTICAL output.
    """
    df = df_features.copy()
    x_bar = df["x_bar"].astype(float).values
    x_bar_safe = np.where(np.abs(x_bar) < 1e-12, 1e-12, x_bar)
    for col in SCALE_DEPENDENT_COLS:
        df[col] = df[col].astype(float).values / x_bar_safe
    return df


def fit_scale_invariant_zscore(df_train_si: pd.DataFrame) -> tuple[dict, dict]:
    """Train-fold-only z-score on scale-invariant features.

    Operates on the OUTPUT of make_scale_invariant.
    """
    means, stds = {}, {}
    for col in SCALE_DEPENDENT_COLS:
        vals = df_train_si[col].astype(float)
        m = float(vals.mean())
        s = float(vals.std(ddof=0))
        means[col] = m
        stds[col] = s if s >= 1e-12 else 1.0
    return means, stds


def build_scale_invariant_X(df_si: pd.DataFrame, means: dict, stds: dict) -> np.ndarray:
    """Build [N, 13] feature matrix from scale-invariant features.

    Column order: 9 z-scored scale-invariant cols, then 4 raw cols.
    Same order as e4.SAMPLE_FEATURE_COLS.
    """
    n = len(df_si)
    X = np.empty((n, len(e4.SAMPLE_FEATURE_COLS)), dtype=np.float32)
    for j, col in enumerate(e4.SAMPLE_FEATURE_COLS):
        vals = df_si[col].astype(float).values
        if col in SCALE_DEPENDENT_COLS:
            vals = (vals - means[col]) / stds[col]
        X[:, j] = vals
    return X


# ════════════════════════════════════════════════════════════════════════
# Output transforms
# ════════════════════════════════════════════════════════════════════════

def _softplus(x):
    return torch.where(x > 20, x, torch.log1p(torch.exp(torch.clamp(x, -50, 20))))


def _softplus_np(x: np.ndarray) -> np.ndarray:
    return np.where(x > 20, x, np.log1p(np.exp(np.clip(x, -50, 20))))


def _inverse_softplus_np(y: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    y_clipped = np.maximum(y, eps)
    return np.log(np.expm1(np.clip(y_clipped, eps, 50)))


def decode_output(z: np.ndarray, x_bar: np.ndarray) -> np.ndarray:
    """Decode network raw output to constrained params."""
    beta_hat = _softplus_np(z[:, 0])
    eta_ratio = _softplus_np(z[:, 1])
    eta_hat = eta_ratio * x_bar
    goe_hat = np.maximum(z[:, 2], 0.0)
    gamma_hat = goe_hat * eta_hat
    return np.column_stack([beta_hat, eta_hat, gamma_hat])


def encode_targets(params: np.ndarray, x_bar: np.ndarray) -> np.ndarray:
    """Encode true params to network target space."""
    beta, eta, gamma = params[:, 0], params[:, 1], params[:, 2]
    z_beta = _inverse_softplus_np(beta)
    z_eta_ratio = _inverse_softplus_np(eta / x_bar)
    z_goe = gamma / eta
    return np.column_stack([z_beta, z_eta_ratio, z_goe])


# ════════════════════════════════════════════════════════════════════════
# Shared J1 loss (used by both training and validation)
# ════════════════════════════════════════════════════════════════════════

def j1_loss_torch(
    beta_hat: torch.Tensor, beta_true: torch.Tensor,
    eta_hat: torch.Tensor, eta_true: torch.Tensor,
    gamma_hat: torch.Tensor, gamma_true: torch.Tensor,
) -> torch.Tensor:
    """J1-compatible per-sample loss (shared by training and validation).

    L_i = ((bh-b)/b)^2 + ((eh-e)/e)^2 + ((gh-g)/e)^2

    gamma denominator is eta_true (NOT gamma_true, NOT eta_hat).

    Returns: scalar mean loss.
    """
    e_beta = (beta_hat - beta_true) / beta_true
    e_eta = (eta_hat - eta_true) / eta_true
    e_gamma = (gamma_hat - gamma_true) / eta_true
    return (e_beta ** 2 + e_eta ** 2 + e_gamma ** 2).mean()


# ════════════════════════════════════════════════════════════════════════
# PyTorch model
# ════════════════════════════════════════════════════════════════════════

class DirectMLP(nn.Module):
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
# Training with shared J1 loss
# ════════════════════════════════════════════════════════════════════════

def train_direct_mlp(
    X_train: np.ndarray,
    Y_train_raw: np.ndarray,
    x_bar_train: np.ndarray,
    seed: int,
    max_iter: int = None,
    lr: float = None,
    batch_size: int = None,
    val_fraction: float = None,
    patience: int = None,
) -> tuple[DirectMLP, dict]:
    """Train one Direct-MLP with shared J1-compatible loss."""
    if max_iter is None:
        max_iter = cfg.DIRECT_MLP_MAX_ITER
    if lr is None:
        lr = cfg.DIRECT_MLP_LR
    if batch_size is None:
        batch_size = cfg.DIRECT_MLP_BATCH_SIZE
    if val_fraction is None:
        val_fraction = cfg.DIRECT_MLP_VALIDATION_FRACTION
    if patience is None:
        patience = cfg.DIRECT_MLP_N_ITER_NO_CHANGE

    _init_seed(seed)
    n = len(X_train)

    Z_train = encode_targets(Y_train_raw, x_bar_train)

    x_mean = X_train.mean(axis=0)
    x_std = X_train.std(axis=0)
    x_std[x_std < 1e-12] = 1.0

    z_mean = Z_train.mean(axis=0)
    z_std = Z_train.std(axis=0)
    z_std[z_std < 1e-12] = 1.0

    X_norm = (X_train - x_mean) / x_std
    Z_norm = (Z_train - z_mean) / z_std

    X_t = torch.FloatTensor(X_norm)
    x_bar_t = torch.FloatTensor(x_bar_train)
    Y_t = torch.FloatTensor(Y_train_raw)
    z_std_t = torch.FloatTensor(z_std)
    z_mean_t = torch.FloatTensor(z_mean)

    n_val = max(1, int(n * val_fraction))
    perm = torch.randperm(n)
    val_idx, tr_idx = perm[:n_val], perm[n_val:]

    model = DirectMLP(input_dim=X_train.shape[1])
    optimizer = optim.Adam(model.parameters(), lr=lr, weight_decay=cfg.DIRECT_MLP_ALPHA)

    best_val_loss = float('inf')
    best_state = None
    no_improve = 0
    n_iter = 0

    for epoch in range(max_iter):
        model.train()
        train_perm = tr_idx[torch.randperm(len(tr_idx))]
        for start in range(0, len(train_perm), batch_size):
            idx = train_perm[start:start + batch_size]
            optimizer.zero_grad()
            z_pred = model(X_t[idx]) * z_std_t + z_mean_t

            beta_pred = _softplus(z_pred[:, 0])
            eta_pred = _softplus(z_pred[:, 1]) * x_bar_t[idx]
            gamma_pred = torch.clamp(z_pred[:, 2], min=0.0) * eta_pred

            loss = j1_loss_torch(
                beta_pred, Y_t[idx, 0],
                eta_pred, Y_t[idx, 1],
                gamma_pred, Y_t[idx, 2],
            )
            loss.backward()
            optimizer.step()

        # Validate with shared J1 loss
        model.eval()
        with torch.no_grad():
            z_pred = model(X_t[val_idx]) * z_std_t + z_mean_t
            beta_pred = _softplus(z_pred[:, 0])
            eta_pred = _softplus(z_pred[:, 1]) * x_bar_t[val_idx]
            gamma_pred = torch.clamp(z_pred[:, 2], min=0.0) * eta_pred

            val_loss = j1_loss_torch(
                beta_pred, Y_t[val_idx, 0],
                eta_pred, Y_t[val_idx, 1],
                gamma_pred, Y_t[val_idx, 2],
            ).item()

        n_iter = epoch + 1
        if val_loss < best_val_loss - 1e-6:
            best_val_loss = val_loss
            best_state = {k: v.clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1
            if no_improve >= patience:
                break

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


def predict_direct_mlp(model, info, X_eval, x_bar_eval):
    """Predict (beta_hat, eta_hat, gamma_hat)."""
    X_norm = (X_eval - info["x_mean"]) / info["x_std"]
    X_t = torch.FloatTensor(X_norm)
    model.eval()
    with torch.no_grad():
        z_norm = model(X_t).numpy()
    z = z_norm * info["z_std"] + info["z_mean"]
    return decode_output(z, x_bar_eval)


# ════════════════════════════════════════════════════════════════════════
# Per-sample loss (numpy version for evaluation)
# ════════════════════════════════════════════════════════════════════════

def compute_param_loss(beta_hat, beta, eta_hat, eta, gamma_hat, gamma):
    """J1² per sample: ((bh-b)/b)² + ((eh-e)/e)² + ((gh-g)/e)²
    gamma denominator = eta (not gamma)."""
    e_beta = (beta_hat - beta) / beta
    e_eta = (eta_hat - eta) / eta
    e_gamma = (gamma_hat - gamma) / eta
    return e_beta ** 2 + e_eta ** 2 + e_gamma ** 2


# ════════════════════════════════════════════════════════════════════════
# Build training data with scale-invariant features
# ════════════════════════════════════════════════════════════════════════

def build_training_data(df_features, train_combos):
    """Build X_train (scale-invariant), Y_train, x_bar_train."""
    mask = df_features.apply(
        lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in train_combos, axis=1
    )
    df_train = df_features[mask].copy()

    for forbidden in cfg.FORBIDDEN_INPUT_FIELDS:
        if forbidden in e4.SAMPLE_FEATURE_COLS:
            raise SchemaError(f"Forbidden field '{forbidden}' in SAMPLE_FEATURE_COLS")

    # Scale-invariant transform
    df_train_si = make_scale_invariant(df_train)

    # Train-fold-only z-score on scale-invariant features
    means, stds = fit_scale_invariant_zscore(df_train_si)
    X_train = build_scale_invariant_X(df_train_si, means, stds)

    Y_train = df_train[["beta", "eta", "gamma"]].values.astype(np.float64)
    x_bar_train = df_train["x_bar"].values.astype(np.float64)

    meta = {
        "n_train_samples": len(df_train),
        "zscore_means": means,
        "zscore_stds": stds,
    }
    return X_train, Y_train, x_bar_train, meta


def build_eval_data(df_features, eval_combos, means, stds):
    """Build X_eval (scale-invariant) for evaluation combos."""
    mask = df_features.apply(
        lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in eval_combos, axis=1
    )
    df_eval = df_features[mask].copy()
    df_eval_si = make_scale_invariant(df_eval)
    X_eval = build_scale_invariant_X(df_eval_si, means, stds)
    return X_eval, df_eval


# ════════════════════════════════════════════════════════════════════════
# Per-fold failure penalty (ALL 26 delta points)
# ════════════════════════════════════════════════════════════════════════

def compute_fold_penalty(df_features, df_risk, train_combos):
    """P99 penalty from ALL 26 delta points. Raises PenaltyError if empty."""
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

    loss_cols = [c for c in df_risk.columns if c.startswith("loss_d")]
    if len(loss_cols) != 26:
        raise SchemaError(
            f"Expected 26 loss_d columns, got {len(loss_cols)}"
        )

    all_losses = []
    for _, row in df_risk.iterrows():
        key = (float(row["beta"]), float(row["gamma_over_eta"]),
               int(row["n"]), int(row["repeat_id"]))
        if key in train_keys:
            for col in loss_cols:
                val = float(row[col])
                if not np.isnan(val):
                    all_losses.append(val)

    if not all_losses:
        raise PenaltyError(
            "No valid training losses found for penalty computation. "
            "Cannot fall back to arbitrary penalty."
        )

    return float(np.nanpercentile(all_losses, 99))


# ════════════════════════════════════════════════════════════════════════
# Training loop
# ════════════════════════════════════════════════════════════════════════

def train_one_model(df_features, fold, seed):
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
    """Evaluate Direct-MLP on evaluation samples."""
    df_eval_si = make_scale_invariant(df_eval)
    X_eval = build_scale_invariant_X(df_eval_si, means, stds)
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
    beta_ok = np.allclose(preds1[:, 0], preds2[:, 0], atol=atol)
    eta_ok = np.allclose(preds1[:, 1] * scale_factor, preds2[:, 1], atol=atol * scale_factor)
    gamma_ok = np.allclose(preds1[:, 2] * scale_factor, preds2[:, 2], atol=atol * scale_factor)
    return bool(beta_ok and eta_ok and gamma_ok)


def verify_input_scale_invariance(
    df_features: pd.DataFrame,
    means: dict, stds: dict,
    scale_factor: float = 2.5,
    atol: float = 1e-6,
) -> bool:
    """Verify that scaling a sample by c produces identical network input.

    This tests the FULL feature pipeline (scale-invariant transform + z-score),
    not just the decoder. If the network sees different inputs for scaled vs
    unscaled samples, scale equivariance would break.
    """
    df_si = make_scale_invariant(df_features)
    X1 = build_scale_invariant_X(df_si, means, stds)

    # Scale the sample features by c
    df_scaled = df_features.copy()
    for col in SCALE_DEPENDENT_COLS:
        df_scaled[col] = df_scaled[col].astype(float) * scale_factor
    df_scaled_si = make_scale_invariant(df_scaled)
    X2 = build_scale_invariant_X(df_scaled_si, means, stds)

    return bool(np.allclose(X1, X2, atol=atol))


def config_hash():
    contract = cfg.production_contract()
    contract["seeds"] = list(contract["seeds"])
    contract["hidden_layers"] = list(contract["hidden_layers"])
    contract["feature_columns"] = list(contract["feature_columns"])
    contract["feature_zscore_cols"] = list(contract["feature_zscore_cols"])
    contract["feature_raw_cols"] = list(contract["feature_raw_cols"])
    raw = json.dumps(contract, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
