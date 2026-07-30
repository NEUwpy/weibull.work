"""Frozen configuration for P3 Direct-MLP and six-method fair comparison.

Holds only P3-specific decisions. All shared infrastructure (feature columns,
MLP hyperparams, combo splits, sample generation, traditional estimators,
J1 formula) is imported from existing modules.
"""

from __future__ import annotations

# ── Full scale-invariant input design (frozen) ─────────────────────────
# The 9 scale-dependent feature columns (x_min, x_max, range, Q1, Med, Q3,
# IQR, x_bar, s) are divided by x_bar BEFORE train-fold-only z-score.
# After normalization, these become dimensionless ratios.
# n, CV, g1, g2 remain unchanged (already scale-invariant).
# x_bar itself becomes 1.0 in the network input.
# The network can only see dimensionless shape information, not absolute scale.
# x_bar is only used OUTSIDE the network to recover eta_hat and gamma_hat.
INPUT_SCALE_INVARIANCE = "divide_by_x_bar_before_zscore"
SCALE_DEPENDENT_FEATURES = ["x_min", "x_max", "range", "Q1", "Med", "Q3", "IQR", "x_bar", "s"]
SCALE_INVARIANT_FEATURES = ["n", "CV", "g1", "g2"]

# ── Scale-equivariant output design (frozen) ───────────────────────────
# Network outputs 3 raw values: (z_beta, z_eta_ratio, z_goe)
# Decode:
#   beta_hat  = softplus(z_beta)           — shape param, always > 0
#   eta_ratio = softplus(z_eta_ratio)       — eta / x_bar (dimensionless)
#   eta_hat   = eta_ratio * x_bar           — scale, from sample feature
#   goe_hat   = relu(z_goe)                 — gamma / eta (dimensionless)
#   gamma_hat = goe_hat * eta_hat           — derived
#
# Full scale invariance: scaling sample by c → all scale cols scale by c,
# x_bar scales by c → ratios unchanged → network input IDENTICAL →
# network output IDENTICAL → beta_hat unchanged, eta_ratio unchanged →
# eta_hat = eta_ratio * (c * x_bar) = c * original_eta_hat ✓
# gamma_hat = goe_hat * c * original_eta_hat = c * original_gamma_hat ✓
OUTPUT_TRANSFORM = "scale_equivariant_softplus_softplus_relu"
OUTPUT_PARAMS = ["beta_hat", "eta_hat", "gamma_hat"]
OUTPUT_CONSTRAINTS = {"beta_gt_0": True, "eta_gt_0": True, "gamma_ge_0": True}
SCALE_ANCHOR = "x_bar"  # sample mean, used for eta recovery

# ── Target encoding ────────────────────────────────────────────────────
# Training targets are inverse-softplus encoded:
#   z_beta_target      = inverse_softplus(beta_true)
#   z_eta_ratio_target = inverse_softplus(eta_true / x_bar)
#   z_goe_target       = gamma_true / eta_true
TARGET_ENCODING = "inverse_softplus_scale_equivariant"
TARGET_PARAMS = ["beta", "eta_ratio", "gamma_over_eta"]

# ── Training loss (J1-compatible) ──────────────────────────────────────
# The network minimizes per-sample loss in decoded parameter space:
#   L_i = ((bh-b)/b)^2 + ((eh-e)/e)^2 + ((gh-g)/e)^2
# This is exactly J1² per sample. The PyTorch training loop computes this
# with autograd, so the gradient is J1-compatible.
TRAINING_LOSS = "J1_compatible_relative_error"
TRAINING_LOSS_FORMULA = "((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2"

# ── Training framework ─────────────────────────────────────────────────
# Using PyTorch (not sklearn MLPRegressor) because sklearn cannot implement
# a custom J1-compatible loss function with autograd gradients.
TRAINING_FRAMEWORK = "pytorch"

# ── Target scaling ─────────────────────────────────────────────────────
TARGET_SCALER = "StandardScaler_on_encoded_targets"

# ── MLP hyperparameters (identical architecture to Vector-MLP) ──────────
import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import run_E4_formal_validation as _e4

DIRECT_MLP_HIDDEN_LAYERS = _e4.MLP_HIDDEN_LAYERS   # (256, 128, 64)
DIRECT_MLP_MAX_ITER = _e4.MLP_MAX_ITER               # 300
DIRECT_MLP_BATCH_SIZE = _e4.MLP_BATCH_SIZE           # 256
DIRECT_MLP_ALPHA = _e4.MLP_ALPHA                     # 1e-4 (weight_decay)
DIRECT_MLP_LR = _e4.MLP_LR                           # 1e-3
DIRECT_MLP_VALIDATION_FRACTION = _e4.MLP_VALIDATION_FRACTION  # 0.15
DIRECT_MLP_N_ITER_NO_CHANGE = _e4.MLP_N_ITER_NO_CHANGE        # 20
DIRECT_MLP_SEEDS = _e4.STABILITY_SEEDS                # [42, 2026, 3407]

# ── Forbidden input fields ─────────────────────────────────────────────
FORBIDDEN_INPUT_FIELDS = [
    "beta", "eta", "gamma", "gamma_over_eta",
    "repeat_id", "fold", "seed",
    "combo_id", "track",
    "loss", "delta", "selected_delta",
    "oracle_min", "regret",
    "sample_sha256",
    "failure_penalty", "failed", "failure_reason",
    "true_loss", "true_loss_complete_case",
]

# ── Configuration correction policy ────────────────────────────────────
CONFIG_CORRECTION_USED = False
CONFIG_CORRECTION_REASON = ""

# ── Fair comparison methods ────────────────────────────────────────────
FAIR_COMPARE_METHODS = [
    "MDM-Default",
    "MDM-Vector-MLP",
    "Direct-MLP",
    "MLE",
    "LSE",
    "WMLE",
]

# ── Output schema ──────────────────────────────────────────────────────
PER_SAMPLE_COLUMNS = [
    "fold", "seed", "method",
    "beta", "gamma_over_eta", "n", "repeat_id",
    "beta_hat", "eta_hat", "gamma_hat",
    "true_loss", "failed", "failure_reason",
    "failure_penalty",
]


def production_contract():
    return {
        "input_scale_invariance": INPUT_SCALE_INVARIANCE,
        "scale_dependent_features": SCALE_DEPENDENT_FEATURES,
        "scale_invariant_features": SCALE_INVARIANT_FEATURES,
        "output_transform": OUTPUT_TRANSFORM,
        "scale_anchor": SCALE_ANCHOR,
        "output_params": OUTPUT_PARAMS,
        "output_constraints": OUTPUT_CONSTRAINTS,
        "target_encoding": TARGET_ENCODING,
        "target_params": TARGET_PARAMS,
        "training_loss": TRAINING_LOSS,
        "training_loss_formula": TRAINING_LOSS_FORMULA,
        "training_framework": TRAINING_FRAMEWORK,
        "target_scaler": TARGET_SCALER,
        "hidden_layers": DIRECT_MLP_HIDDEN_LAYERS,
        "max_iter": DIRECT_MLP_MAX_ITER,
        "batch_size": DIRECT_MLP_BATCH_SIZE,
        "alpha": DIRECT_MLP_ALPHA,
        "learning_rate": DIRECT_MLP_LR,
        "validation_fraction": DIRECT_MLP_VALIDATION_FRACTION,
        "n_iter_no_change": DIRECT_MLP_N_ITER_NO_CHANGE,
        "seeds": DIRECT_MLP_SEEDS,
        "forbidden_input_fields": FORBIDDEN_INPUT_FIELDS,
        "config_correction_used": CONFIG_CORRECTION_USED,
        "config_correction_reason": CONFIG_CORRECTION_REASON,
        "feature_columns": _e4.SAMPLE_FEATURE_COLS,
        "feature_zscore_cols": _e4.FEATURE_COLS_ZSCORE,
        "feature_raw_cols": _e4.FEATURE_COLS_RAW,
    }
