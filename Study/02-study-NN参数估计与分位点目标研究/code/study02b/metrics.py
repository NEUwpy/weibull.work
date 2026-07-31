"""Thin metric adapter for direct x_{0.95} predictions.

Reuses `python/studies/common/metrics.py` for summary functions
(summarize_standard_errors, summarize_relative_errors) and
`quantile_true` for computing ground-truth x_R from parameters.

The D-route predicts x_{0.95} directly, so we do NOT go through the
parameter space.  This adapter bridges raw (predicted, true) pairs into
the same summary format that the existing metric aggregators expect.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional

import numpy as np

from studies.common.metrics import (
    summarize_standard_errors,
    summarize_relative_errors,
    DEFAULT_STANDARD_R_LEVELS,
)


def direct_errors(
    predictions: np.ndarray,
    true_x095: np.ndarray,
) -> Dict[str, np.ndarray]:
    """Compute absolute and relative errors for direct x_{0.95} predictions.

    Args:
        predictions: (N,) array of predicted x_{0.95} values.
        true_x095:  (N,) array of true x_{0.95} values.

    Returns:
        dict with keys "absolute" and "relative", each an (N,) array.
    """
    pred = np.asarray(predictions, dtype=float).ravel()
    true = np.asarray(true_x095, dtype=float).ravel()
    if pred.shape != true.shape:
        raise ValueError(
            f"predictions and true_x095 must have matching shapes, "
            f"got {pred.shape} vs {true.shape}"
        )
    abs_err = pred - true
    rel_err = np.where(true != 0.0, abs_err / true, np.nan)
    return {"absolute": abs_err, "relative": rel_err}


def aggregate_direct_metrics(
    predictions: np.ndarray,
    true_x095: np.ndarray,
    valid_mask: Optional[np.ndarray] = None,
    include_diagnostics: bool = True,
) -> Dict:
    """Compute standard metric summary for direct x_{0.95} predictions.

    Args:
        predictions: (N,) array of predicted x_{0.95} values.
        true_x095:  (N,) array of true x_{0.95} values.
        valid_mask: optional (N,) boolean mask for valid predictions
            (finite and physically plausible).  If None, all rows are used.
        include_diagnostics: if True, also compute MdAPE / tail diagnostics
            via summarize_relative_errors.

    Returns:
        dict with "n_total", "n_valid", "n_failure", "valid_rate",
        "failure_rate", "bias", "sd", "rmse", "mae", "bias_rel",
        "sd_rel", "rmse_rel", "mae_rel", and optionally diagnostics keys.
    """
    pred = np.asarray(predictions, dtype=float).ravel()
    true = np.asarray(true_x095, dtype=float).ravel()

    if pred.shape != true.shape:
        raise ValueError("predictions and true_x095 shapes must match")

    n_total = len(pred)

    if valid_mask is None:
        # Default: finite predictions
        valid_mask = np.isfinite(pred)

    n_valid = int(valid_mask.sum())
    n_failure = n_total - n_valid

    output: Dict = {
        "n_total": n_total,
        "n_valid": n_valid,
        "n_failure": n_failure,
        "valid_rate": n_valid / n_total if n_total > 0 else None,
        "failure_rate": n_failure / n_total if n_total > 0 else None,
    }

    if n_valid == 0:
        if include_diagnostics:
            output["diagnostics"] = summarize_relative_errors(np.array([]))
        return output

    errors = direct_errors(pred[valid_mask], true[valid_mask])
    abs_summary = summarize_standard_errors(errors["absolute"])
    rel_errors = errors["relative"]
    rel_errors_finite = rel_errors[np.isfinite(rel_errors)]
    rel_summary = summarize_standard_errors(rel_errors_finite)

    # Flatten into top-level keys
    for key, value in abs_summary.items():
        if key != "n":
            output[key] = value
    for key, value in rel_summary.items():
        if key != "n":
            output[f"{key}_rel"] = value

    if include_diagnostics:
        output["diagnostics"] = summarize_relative_errors(rel_errors_finite)

    return output
