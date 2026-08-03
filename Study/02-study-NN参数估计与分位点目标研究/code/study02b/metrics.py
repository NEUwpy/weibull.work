"""Thin metric adapter for direct x_{0.95} predictions.

Reuses `python/studies/common/metrics.py` for summary functions
(summarize_standard_errors, summarize_relative_errors) and
`quantile_true` for computing ground-truth x_R from parameters.

The D-route predicts x_{0.95} directly, so we do NOT go through the
parameter space.  This adapter bridges raw (predicted, true) pairs into
the same summary format that the existing metric aggregators expect.

Protocol §5.1: D predictions are valid only when finite AND greater than
zero (physically plausible for a positive lifetime quantile).
"""

from __future__ import annotations

from typing import Dict, Optional

import numpy as np

from studies.common.metrics import (
    summarize_standard_errors,
    summarize_relative_errors,
)


def _intrinsic_valid(predictions: np.ndarray) -> np.ndarray:
    """Return boolean mask: prediction is finite AND greater than zero."""
    pred = np.asarray(predictions, dtype=float).ravel()
    return np.isfinite(pred) & (pred > 0.0)


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
        Relative error is NaN where true_x095 is zero — no RuntimeWarning.
    """
    pred = np.asarray(predictions, dtype=float).ravel()
    true = np.asarray(true_x095, dtype=float).ravel()
    if pred.shape != true.shape:
        raise ValueError(
            f"predictions and true_x095 must have matching shapes, "
            f"got {pred.shape} vs {true.shape}"
        )
    abs_err = pred - true
    # Safe division: only divide where true != 0, avoiding RuntimeWarning.
    rel_err = np.full_like(abs_err, np.nan, dtype=float)
    nonzero = true != 0.0
    rel_err[nonzero] = abs_err[nonzero] / true[nonzero]
    return {"absolute": abs_err, "relative": rel_err}


def aggregate_direct_metrics(
    predictions: np.ndarray,
    true_x095: np.ndarray,
    valid_mask: Optional[np.ndarray] = None,
    include_diagnostics: bool = True,
) -> Dict:
    """Compute standard metric summary for direct x_{0.95} predictions.

    Intrinsic validity (protocol §5.1): prediction must be finite AND > 0.
    A caller-supplied ``valid_mask`` is **combined with** (AND) intrinsic
    validity — it cannot override the frozen rule.  Supplying a mask is
    useful for, e.g., excluding rows where the anchor was degenerate.

    Args:
        predictions: (N,) array of predicted x_{0.95} values.
        true_x095:  (N,) array of true x_{0.95} values.
        valid_mask: optional (N,) boolean array of externally-known invalid
            rows.  Combined with intrinsic validity via logical AND.
        include_diagnostics: if True, also compute MdAPE / tail diagnostics
            via summarize_relative_errors.

    Returns:
        dict with "n_total", "n_valid", "n_failure", "valid_rate",
        "failure_rate", "bias", "sd", "rmse", "mae", "bias_rel",
        "sd_rel", "rmse_rel", "mae_rel", and optionally "diagnostics".
    """
    pred = np.asarray(predictions, dtype=float).ravel()
    true = np.asarray(true_x095, dtype=float).ravel()

    if pred.shape != true.shape:
        raise ValueError("predictions and true_x095 shapes must match")

    n_total = len(pred)

    # Intrinsic validity: finite AND > 0.
    intrinsic = _intrinsic_valid(pred)

    if valid_mask is not None:
        ext = np.asarray(valid_mask, dtype=bool).ravel()
        if ext.shape != pred.shape:
            raise ValueError(
                f"valid_mask shape {ext.shape} does not match "
                f"predictions shape {pred.shape}"
            )
        # Combine: a row must pass BOTH intrinsic and caller-supplied checks.
        combined = intrinsic & ext
    else:
        combined = intrinsic

    n_valid = int(combined.sum())
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

    errors = direct_errors(pred[combined], true[combined])
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
