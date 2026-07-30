"""P3 Direct-MLP: directly predicts Weibull (beta, eta, gamma) from 13 features.

Reuses E4 formal validation infrastructure verbatim:
  - _train_mlp (MLPRegressor with StandardScaler on Y)
  - _fit_zscore_params (train-fold-only z-score on 9 feature cols)
  - _build_X_from_samples (13-dim feature matrix)
  - get_combo_split (5 full-combo folds)
  - compute_sample_features (13 deployment-observable statistics)
  - generate_sample (deterministic sample reconstruction)

The ONLY new logic is the output transform (softplus/softplus/relu) and
the training target (true parameters instead of 26-dim risk vectors).
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


# ── Output transforms ──────────────────────────────────────────────────

def _softplus(x: np.ndarray) -> np.ndarray:
    """Numerically stable softplus: log(1 + exp(x))."""
    return np.where(x > 20, x, np.log1p(np.exp(np.clip(x, -50, 20))))


def apply_output_transform(raw_output: np.ndarray) -> np.ndarray:
    """Transform raw network output to satisfy beta>0, eta>0, gamma>=0.

    raw_output shape: [N, 3] — columns are (beta_raw, eta_raw, gamma_raw).
    Returns: [N, 3] with (beta_hat, eta_hat, gamma_hat).
    """
    out = np.empty_like(raw_output, dtype=np.float64)
    out[:, 0] = _softplus(raw_output[:, 0])  # beta > 0
    out[:, 1] = _softplus(raw_output[:, 1])  # eta > 0
    out[:, 2] = np.maximum(raw_output[:, 2], 0.0)  # gamma >= 0
    return out


# ── Training ───────────────────────────────────────────────────────────

def train_direct_mlp(
    X_train: np.ndarray,
    Y_train: np.ndarray,
    seed: int,
) -> tuple[MLPRegressor, StandardScaler]:
    """Train one Direct-MLP model.

    Identical to e4._train_mlp except Y is [N, 3] (true params) not [N, 26].
    Reuses the same MLP hyperparameters, StandardScaler on Y, and early stopping.
    """
    target_scaler = StandardScaler()
    Y_train_scaled = target_scaler.fit_transform(Y_train)
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
        model.fit(X_train, Y_train_scaled)
    return model, target_scaler


# ── Prediction ─────────────────────────────────────────────────────────

def predict_direct_mlp(
    model: MLPRegressor,
    target_scaler: StandardScaler,
    X_eval: np.ndarray,
) -> np.ndarray:
    """Predict (beta_hat, eta_hat, gamma_hat) for evaluation samples.

    inverse_transform undoes the StandardScaler on Y, then we apply the
    frozen output transform to guarantee parameter constraints.
    """
    raw = target_scaler.inverse_transform(model.predict(X_eval))
    return apply_output_transform(raw)


# ── Per-sample loss (identical to J1 parameter normalization) ──────────

def compute_param_loss(
    beta_hat: float, beta: float,
    eta_hat: float, eta: float,
    gamma_hat: float, gamma: float,
) -> float:
    """Same formula as e4.compute_loss / p2_config.compute_j1_squared."""
    e_beta = (beta_hat - beta) / beta
    e_eta = (eta_hat - eta) / eta
    e_gamma = (gamma_hat - gamma) / eta
    return e_beta ** 2 + e_eta ** 2 + e_gamma ** 2


# ── Build training targets from main-grid sample features ──────────────

def build_training_targets(
    df_features: pd.DataFrame,
    train_combos: list[tuple],
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Build X_train [N,13] and Y_train [N,3] for Direct-MLP.

    Parameters
    ----------
    df_features : DataFrame with columns from E3b sample_features.csv
        Must include beta, eta, gamma, gamma_over_eta, n, repeat_id,
        and the 13 SAMPLE_FEATURE_COLS.
    train_combos : list of (beta, gamma_over_eta, n) tuples

    Returns
    -------
    X_train, Y_train, metadata
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

    # Build X using inline z-score pipeline (same as e4._fit_zscore_params)
    means, stds = _fit_zscore_params_inline(df_train)
    X_train = _build_X_inline(df_train, means, stds)

    # Build Y: true (beta, eta, gamma)
    Y_train = df_train[["beta", "eta", "gamma"]].values.astype(np.float64)

    meta = {
        "n_train_samples": len(df_train),
        "feature_columns": e4.SAMPLE_FEATURE_COLS,
        "target_columns": ["beta", "eta", "gamma"],
        "zscore_means": means,
        "zscore_stds": stds,
    }
    return X_train, Y_train, meta


def _fit_zscore_params_inline(df_train: pd.DataFrame) -> tuple[dict, dict]:
    """Train-fold-only z-score on 9 feature cols. Same as e4._fit_zscore_params."""
    means, stds = {}, {}
    for col in e4.FEATURE_COLS_ZSCORE:
        m = float(df_train[col].mean())
        s = float(df_train[col].std(ddof=0))
        if s < 1e-12:
            s = 1.0
        means[col] = m
        stds[col] = s
    return means, stds


def _build_X_inline(df: pd.DataFrame, means: dict, stds: dict) -> np.ndarray:
    """Build [N, 13] feature matrix. Same column order as e4._build_X_from_samples."""
    n = len(df)
    X = np.empty((n, len(e4.SAMPLE_FEATURE_COLS)), dtype=np.float32)
    for j, col in enumerate(e4.SAMPLE_FEATURE_COLS):
        vals = df[col].values.astype(np.float64)
        if col in e4.FEATURE_COLS_ZSCORE:
            vals = (vals - means[col]) / stds[col]
        X[:, j] = vals
    return X


# ── Full training loop (one fold × seed) ───────────────────────────────

def train_one_model(
    df_features: pd.DataFrame,
    fold: dict,
    seed: int,
) -> tuple[MLPRegressor, StandardScaler, dict, dict, float]:
    """Train one Direct-MLP model for a given fold and seed.

    Returns (model, target_scaler, zscore_means, zscore_stds, elapsed_s).
    Also returns training metadata via the dicts.
    """
    train_combos = fold["train_combos"]
    X_train, Y_train, meta = build_training_targets(df_features, train_combos)

    # Assert train fold isolation
    assert meta["n_train_samples"] == 36000, (
        f"Expected 36000 train samples, got {meta['n_train_samples']}"
    )

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


# ── Evaluation on arbitrary samples ────────────────────────────────────

def evaluate_on_samples(
    model: MLPRegressor,
    target_scaler: StandardScaler,
    df_eval: pd.DataFrame,
    means: dict,
    stds: dict,
    fold_name: str,
    seed: int,
) -> list[dict]:
    """Evaluate Direct-MLP on a set of samples.

    df_eval must have columns: beta, eta, gamma, gamma_over_eta, n, repeat_id,
    and the 13 SAMPLE_FEATURE_COLS.

    Returns per-sample rows with predicted params and loss.
    """
    X_eval = _build_X_inline(df_eval, means, stds)
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

        loss = compute_param_loss(beta_hat, beta, eta_hat, eta, gamma_hat, gamma)

        rows.append({
            "fold": fold_name,
            "seed": seed,
            "method": "Direct-MLP",
            "beta": beta,
            "gamma_over_eta": goe,
            "n": n_val,
            "repeat_id": rid,
            "beta_hat": beta_hat,
            "eta_hat": eta_hat,
            "gamma_hat": gamma_hat,
            "true_loss": loss,
            "failed": False,
            "failure_reason": "",
            "failure_penalty": 0.0,  # Set by fair compare driver
        })
    return rows


# ── Output constraint verification ─────────────────────────────────────

def verify_output_constraints(preds: np.ndarray) -> bool:
    """Verify that all predictions satisfy beta>0, eta>0, gamma>=0."""
    if preds.shape[1] != 3:
        return False
    beta_ok = np.all(preds[:, 0] > 0)
    eta_ok = np.all(preds[:, 1] > 0)
    gamma_ok = np.all(preds[:, 2] >= 0)
    return bool(beta_ok and eta_ok and gamma_ok)


# ── Config hash for provenance ─────────────────────────────────────────

def config_hash() -> str:
    """SHA256 of the frozen production contract."""
    contract = cfg.production_contract()
    # Convert non-serializable items
    contract["seeds"] = list(contract["seeds"])
    contract["hidden_layers"] = list(contract["hidden_layers"])
    contract["feature_columns"] = list(contract["feature_columns"])
    contract["feature_zscore_cols"] = list(contract["feature_zscore_cols"])
    contract["feature_raw_cols"] = list(contract["feature_raw_cols"])
    raw = json.dumps(contract, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()
