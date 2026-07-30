"""P3 Direct-MLP: directly predicts Weibull (beta, eta, gamma) from 13 features.

Key design decision: training targets are inverse-transformed params so
that a perfect network prediction decodes back to exactly the true params.

Decode path: network raw output → inverse StandardScaler → softplus/softplus/relu
    → (beta_hat, eta_hat, gamma_hat)

Encode path (training targets): true params → inverse softplus / identity
    → StandardScaler → network learns these

If the network perfectly predicts the scaled inverse-softplus targets, then:
  inverse_transform(scaler) gives inverse_softplus(beta)
  softplus(inverse_softplus(beta)) = beta   (exact identity)

Reuses E4 formal validation infrastructure verbatim:
  - _fit_zscore_params, _build_X_from_samples (feature pipeline)
  - _train_mlp pattern (MLPRegressor + StandardScaler on Y)
  - get_combo_split, STABILITY_SEEDS, compute_sample_features
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import run_E4_formal_validation as e4
import p3_config as cfg


# ════════════════════════════════════════════════════════════════════════
# Output transforms: softplus for positive params, relu for non-negative
# ════════════════════════════════════════════════════════════════════════

def _softplus(x: np.ndarray) -> np.ndarray:
    """Numerically stable softplus: log(1 + exp(x))."""
    return np.where(x > 20, x, np.log1p(np.exp(np.clip(x, -50, 20))))


def _inverse_softplus(y: np.ndarray, eps: float = 1e-12) -> np.ndarray:
    """Inverse of softplus: log(exp(y) - 1) for y > 0.

    For y <= eps, returns a large negative value (≈ log(eps)).
    This is the pre-image that softplus maps back to y.
    """
    y_clipped = np.maximum(y, eps)
    return np.log(np.expm1(np.clip(y_clipped, eps, 50)))


def encode_targets(params: np.ndarray) -> np.ndarray:
    """Encode true params to network target space.

    beta, eta → inverse_softplus (so softplus recovers them)
    gamma     → identity (gamma >= 0 already; relu recovers it)
    """
    out = np.empty_like(params, dtype=np.float64)
    out[:, 0] = _inverse_softplus(params[:, 0])  # beta
    out[:, 1] = _inverse_softplus(params[:, 1])  # eta
    out[:, 2] = params[:, 2]                       # gamma (>= 0 already)
    return out


def decode_output(raw_output: np.ndarray) -> np.ndarray:
    """Decode network output to constrained params.

    softplus for beta, eta (always positive)
    relu for gamma (non-negative)
    """
    out = np.empty_like(raw_output, dtype=np.float64)
    out[:, 0] = _softplus(raw_output[:, 0])
    out[:, 1] = _softplus(raw_output[:, 1])
    out[:, 2] = np.maximum(raw_output[:, 2], 0.0)
    return out


# Kept for backward compatibility with tests
def apply_output_transform(raw_output: np.ndarray) -> np.ndarray:
    """Alias for decode_output."""
    return decode_output(raw_output)


# ════════════════════════════════════════════════════════════════════════
# Training
# ════════════════════════════════════════════════════════════════════════

def train_direct_mlp(
    X_train: np.ndarray,
    Y_train_raw: np.ndarray,
    seed: int,
) -> tuple[MLPRegressor, StandardScaler]:
    """Train one Direct-MLP model.

    Parameters
    ----------
    X_train : [N, 13] feature matrix (already z-scored)
    Y_train_raw : [N, 3] true (beta, eta, gamma) in original param space

    Returns (model, target_scaler) where target_scaler operates on the
    encoded (inverse-softplus) target space.
    """
    # Encode targets: true params → inverse_softplus space
    Y_encoded = encode_targets(Y_train_raw)

    # StandardScaler on encoded targets (same pattern as Vector-MLP)
    target_scaler = StandardScaler()
    Y_scaled = target_scaler.fit_transform(Y_encoded)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=ConvergenceWarning)
        model = MLPRegressor(
            hidden_layer_sizes=cfg.DIRECT_MLP_HIDDEN_LAYERS,
            activation="relu",
            solver="adam",
            alpha=cfg.DIRECT_MLP_ALPHA,
            learning_rate_init=cfg.DIRECT_MLP_LR,
            max_iter=cfg.DIRECT_MLP_MAX_ITER,
            early_stopping=True,
            validation_fraction=cfg.DIRECT_MLP_VALIDATION_FRACTION,
            n_iter_no_change=cfg.DIRECT_MLP_N_ITER_NO_CHANGE,
            random_state=seed,
            batch_size=cfg.DIRECT_MLP_BATCH_SIZE,
        )
        model.fit(X_train, Y_scaled)
    return model, target_scaler


def predict_direct_mlp(
    model: MLPRegressor,
    target_scaler: StandardScaler,
    X_eval: np.ndarray,
) -> np.ndarray:
    """Predict (beta_hat, eta_hat, gamma_hat) for evaluation samples.

    Decode path: model.predict → inverse StandardScaler → softplus/softplus/relu
    """
    raw_scaled = model.predict(X_eval)
    raw_encoded = target_scaler.inverse_transform(raw_scaled)
    return decode_output(raw_encoded)


# ════════════════════════════════════════════════════════════════════════
# Per-sample loss (identical to J1 parameter normalization)
# ════════════════════════════════════════════════════════════════════════

def compute_param_loss(
    beta_hat: float, beta: float,
    eta_hat: float, eta: float,
    gamma_hat: float, gamma: float,
) -> float:
    """Same formula as e4.compute_loss / p2_config.compute_j1_squared.

    ell = ((bh-b)/b)^2 + ((eh-e)/e)^2 + ((gh-g)/e)^2
    """
    e_beta = (beta_hat - beta) / beta
    e_eta = (eta_hat - eta) / eta
    e_gamma = (gamma_hat - gamma) / eta
    return e_beta ** 2 + e_eta ** 2 + e_gamma ** 2


# ════════════════════════════════════════════════════════════════════════
# Build training data using E4's proven functions directly (no duplication)
# ════════════════════════════════════════════════════════════════════════

def build_training_data(
    df_features: pd.DataFrame,
    train_combos: list[tuple],
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Build X_train [N,13] and Y_train [N,3] for Direct-MLP.

    Uses e4._fit_zscore_params and e4._build_X_from_samples directly.
    """
    mask = df_features.apply(
        lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in train_combos,
        axis=1,
    )
    df_train = df_features[mask].copy()

    # Verify no forbidden fields leak into features
    feature_cols = [c for c in e4.SAMPLE_FEATURE_COLS if c in df_train.columns]
    for forbidden in cfg.FORBIDDEN_INPUT_FIELDS:
        assert forbidden not in feature_cols, (
            f"Forbidden field '{forbidden}' in feature columns"
        )

    # Use E4's functions directly — no inline duplication
    means, stds = e4._fit_zscore_params(df_train)
    X_train = e4._build_X_from_samples(df_train, means, stds)

    # Build Y: true (beta, eta, gamma) in original param space
    Y_train = df_train[["beta", "eta", "gamma"]].values.astype(np.float64)

    meta = {
        "n_train_samples": len(df_train),
        "feature_columns": list(e4.SAMPLE_FEATURE_COLS),
        "target_columns": ["beta", "eta", "gamma"],
        "zscore_means": means,
        "zscore_stds": stds,
    }
    return X_train, Y_train, meta


def build_eval_features(
    df_features: pd.DataFrame,
    eval_combos: list[tuple],
    means: dict,
    stds: dict,
) -> tuple[np.ndarray, pd.DataFrame]:
    """Build X_eval for a set of evaluation combos using E4's functions."""
    mask = df_features.apply(
        lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in eval_combos,
        axis=1,
    )
    df_eval = df_features[mask].copy()
    X_eval = e4._build_X_from_samples(df_eval, means, stds)
    return X_eval, df_eval


# ════════════════════════════════════════════════════════════════════════
# Per-fold failure penalty (same as P2 Vector-MLP contract)
# ════════════════════════════════════════════════════════════════════════

def compute_fold_penalty(
    df_features: pd.DataFrame,
    df_risk: pd.DataFrame,
    train_combos: list[tuple],
) -> float:
    """Compute the P99 failure penalty for a training fold.

    Same as P2: P99 of valid per-sample losses in the training fold.
    Uses the risk_curves data to get per-delta losses for the Default delta.
    """
    mask = df_features.apply(
        lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in train_combos,
        axis=1,
    )
    df_train = df_features[mask]

    # Match training samples to risk data at delta=0.1 (Default)
    train_keys = set(zip(
        df_train["beta"].astype(float),
        df_train["gamma_over_eta"].astype(float),
        df_train["n"].astype(int),
        df_train["repeat_id"].astype(int),
    ))

    losses = []
    for _, row in df_risk.iterrows():
        key = (
            float(row["beta"]),
            float(row["gamma_over_eta"]),
            int(row["n"]),
            int(row["repeat_id"]),
        )
        if key in train_keys:
            # Use delta=0.1 loss column
            loss_col = "loss_d0.1" if "loss_d0.1" in df_risk.columns else None
            if loss_col:
                val = float(row[loss_col])
                if not np.isnan(val):
                    losses.append(val)

    if not losses:
        return 3.0  # Fallback (should not happen with real data)

    return float(np.nanpercentile(losses, 99))


# ════════════════════════════════════════════════════════════════════════
# Full training loop (one fold × seed)
# ════════════════════════════════════════════════════════════════════════

def train_one_model(
    df_features: pd.DataFrame,
    fold: dict,
    seed: int,
) -> tuple[MLPRegressor, StandardScaler, dict, dict, float]:
    """Train one Direct-MLP model for a given fold and seed."""
    train_combos = fold["train_combos"]
    X_train, Y_train, meta = build_training_data(df_features, train_combos)

    t0 = time.time()
    model, target_scaler = train_direct_mlp(X_train, Y_train, seed)
    elapsed = time.time() - t0

    return (
        model,
        target_scaler,
        meta["zscore_means"],
        meta["zscore_stds"],
        elapsed,
    )


# ════════════════════════════════════════════════════════════════════════
# Evaluation on arbitrary samples
# ════════════════════════════════════════════════════════════════════════

def evaluate_on_samples(
    model: MLPRegressor,
    target_scaler: StandardScaler,
    df_eval: pd.DataFrame,
    means: dict,
    stds: dict,
    fold_name: str,
    seed: int,
    failure_penalty: float,
) -> list[dict]:
    """Evaluate Direct-MLP on a set of samples.

    Uses failure_penalty for any sample that violates output constraints
    (should not happen with softplus/relu, but included for contract safety).
    """
    X_eval = e4._build_X_from_samples(df_eval, means, stds)
    preds = predict_direct_mlp(model, target_scaler, X_eval)

    rows = []
    for i in range(len(df_eval)):
        row = df_eval.iloc[i]
        beta = float(row["beta"])
        eta = float(row["eta"])
        gamma = float(row["gamma"])
        goe = float(row["gamma_over_eta"])
        n_val = int(row["n"])
        rid = int(row["repeat_id"])

        beta_hat = float(preds[i, 0])
        eta_hat = float(preds[i, 1])
        gamma_hat = float(preds[i, 2])

        # Check for NaN/inf (failure)
        if not (np.isfinite(beta_hat) and np.isfinite(eta_hat) and np.isfinite(gamma_hat)):
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
# Output constraint verification
# ════════════════════════════════════════════════════════════════════════

def verify_output_constraints(preds: np.ndarray) -> bool:
    """Verify that all predictions satisfy beta>0, eta>0, gamma>=0."""
    if preds.shape[1] != 3:
        return False
    beta_ok = np.all(preds[:, 0] > 0)
    eta_ok = np.all(preds[:, 1] > 0)
    gamma_ok = np.all(preds[:, 2] >= 0)
    return bool(beta_ok and eta_ok and gamma_ok)


def verify_perfect_decode(params: np.ndarray, atol: float = 1e-6) -> bool:
    """Verify that encode → decode round-trips exactly.

    A perfect network prediction in encoded space should decode back
    to the original params within numerical tolerance.
    """
    encoded = encode_targets(params)
    decoded = decode_output(encoded)
    return bool(np.allclose(decoded, params, atol=atol))


# ════════════════════════════════════════════════════════════════════════
# Config hash for provenance
# ════════════════════════════════════════════════════════════════════════

def config_hash() -> str:
    """SHA256 of the frozen production contract."""
    contract = cfg.production_contract()
    contract["seeds"] = list(contract["seeds"])
    contract["hidden_layers"] = list(contract["hidden_layers"])
    contract["feature_columns"] = list(contract["feature_columns"])
    contract["feature_zscore_cols"] = list(contract["feature_zscore_cols"])
    contract["feature_raw_cols"] = list(contract["feature_raw_cols"])
    raw = json.dumps(contract, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
