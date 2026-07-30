"""Frozen configuration for P3 Direct-MLP and six-method fair comparison.

This module is intentionally minimal: it holds only the P3-specific decisions
that are NOT already frozen in run_E4_formal_validation.py or p2_config.py.
All shared infrastructure (feature columns, MLP hyperparams, combo splits,
sample generation, traditional estimators, J1 formula) is imported from
existing modules and never re-declared here.
"""

from __future__ import annotations

# ── Output transformation (frozen before any testing) ──────────────────
# Direct-MLP outputs raw network values, then applies these transforms
# to guarantee beta > 0, eta > 0, gamma >= 0.
# Strategy: softplus for beta and eta (always positive), relu for gamma.
OUTPUT_TRANSFORM = "softplus_softplus_relu"
OUTPUT_PARAMS = ["beta_hat", "eta_hat", "gamma_hat"]
OUTPUT_CONSTRAINTS = {"beta_gt_0": True, "eta_gt_0": True, "gamma_ge_0": True}

# ── Training target ────────────────────────────────────────────────────
# Direct-MLP regresses on TRUE (beta, eta, gamma) — not on risk curves.
# The per-sample loss uses the same J1 parameter-normalization scale:
#   ell = ((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2
TARGET_PARAMS = ["beta", "eta", "gamma"]

# ── Target scaling ─────────────────────────────────────────────────────
# StandardScaler on Y (same pattern as Vector-MLP _train_mlp).
TARGET_SCALER = "StandardScaler"

# ── MLP hyperparameters (identical to Vector-MLP, from E4 frozen config) ─
# Import from E4 to ensure single source of truth.
import sys
from pathlib import Path

_CODE_DIR = Path(__file__).resolve().parent
if str(_CODE_DIR) not in sys.path:
    sys.path.insert(0, str(_CODE_DIR))

import run_E4_formal_validation as _e4

DIRECT_MLP_HIDDEN_LAYERS = _e4.MLP_HIDDEN_LAYERS   # (256, 128, 64)
DIRECT_MLP_MAX_ITER = _e4.MLP_MAX_ITER               # 300
DIRECT_MLP_BATCH_SIZE = _e4.MLP_BATCH_SIZE           # 256
DIRECT_MLP_ALPHA = _e4.MLP_ALPHA                     # 1e-4
DIRECT_MLP_LR = _e4.MLP_LR                           # 1e-3
DIRECT_MLP_VALIDATION_FRACTION = _e4.MLP_VALIDATION_FRACTION  # 0.15
DIRECT_MLP_N_ITER_NO_CHANGE = _e4.MLP_N_ITER_NO_CHANGE        # 20
DIRECT_MLP_SEEDS = _e4.STABILITY_SEEDS                # [42, 2026, 3407]

# ── Forbidden input fields ─────────────────────────────────────────────
# These must NEVER appear in Direct-MLP input features.
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
# If the initial config fails to train, exactly ONE correction is allowed.
# It must be driven by training/validation evidence, not test results.
CONFIG_CORRECTION_USED = False
CONFIG_CORRECTION_REASON = ""

# ── Fair comparison methods ────────────────────────────────────────────
FAIR_COMPARE_METHODS = [
    "MDM-Default",       # MDM with delta=0.1
    "MDM-Vector-MLP",    # P2 v2 frozen Vector-MLP (15 models)
    "Direct-MLP",        # This module's output
    "MLE",               # python/methods/mle.py
    "LSE",               # python/methods/lse.py
    "WMLE",              # python/methods/wmle.py
]

# ── Output schema for per-sample comparison results ───────────────────
PER_SAMPLE_COLUMNS = [
    "fold", "seed", "method",
    "beta", "gamma_over_eta", "n", "repeat_id",
    "beta_hat", "eta_hat", "gamma_hat",
    "true_loss", "failed", "failure_reason",
    "failure_penalty",
]


def production_contract() -> dict:
    """Return the frozen Direct-MLP config for manifest provenance."""
    return {
        "output_transform": OUTPUT_TRANSFORM,
        "output_params": OUTPUT_PARAMS,
        "output_constraints": OUTPUT_CONSTRAINTS,
        "target_params": TARGET_PARAMS,
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
