"""Unit tests for D-route x_{0.95} metric adapter."""

from pathlib import Path
import sys

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
PYTHON = REPO_ROOT / "python"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
if str(PYTHON) not in sys.path:
    sys.path.insert(0, str(PYTHON))

from study02b.metrics import direct_errors, aggregate_direct_metrics


def test_direct_errors_perfect_prediction():
    """Perfect prediction yields zero errors."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([100.0, 200.0, 300.0])
    errors = direct_errors(pred, true)
    np.testing.assert_allclose(errors["absolute"], [0.0, 0.0, 0.0])
    np.testing.assert_allclose(errors["relative"], [0.0, 0.0, 0.0])


def test_direct_errors_positive_bias():
    """Positive bias in predictions."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([110.0, 220.0, 330.0])  # 10% high
    errors = direct_errors(pred, true)
    np.testing.assert_allclose(errors["absolute"], [10.0, 20.0, 30.0])
    np.testing.assert_allclose(errors["relative"], [0.1, 0.1, 0.1])


def test_direct_errors_negative_bias():
    """Negative bias in predictions."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([90.0, 180.0, 270.0])  # 10% low
    errors = direct_errors(pred, true)
    np.testing.assert_allclose(errors["absolute"], [-10.0, -20.0, -30.0])
    np.testing.assert_allclose(errors["relative"], [-0.1, -0.1, -0.1])


def test_aggregate_perfect():
    """Aggregate metrics for perfect prediction."""
    true = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
    pred = true.copy()
    result = aggregate_direct_metrics(pred, true)
    assert result["n_total"] == 5
    assert result["n_valid"] == 5
    assert result["n_failure"] == 0
    assert result["bias"] == pytest.approx(0.0)
    assert result["rmse"] == pytest.approx(0.0)
    assert result["mae"] == pytest.approx(0.0)


def test_aggregate_with_bias():
    """Aggregate metrics recover known RMSE and bias."""
    true = np.array([100.0, 100.0, 100.0])
    pred = np.array([110.0, 110.0, 110.0])
    result = aggregate_direct_metrics(pred, true)
    assert result["bias"] == pytest.approx(10.0)
    assert result["rmse"] == pytest.approx(10.0)
    assert result["mae"] == pytest.approx(10.0)
    assert result["bias_rel"] == pytest.approx(0.1)
    assert result["rmse_rel"] == pytest.approx(0.1)


def test_aggregate_invalid_predictions():
    """Invalid predictions are excluded from valid count."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([110.0, np.inf, 330.0])
    result = aggregate_direct_metrics(pred, true)
    assert result["n_total"] == 3
    assert result["n_valid"] == 2
    assert result["n_failure"] == 1

    # Only rows 0 and 2 used
    assert result["bias"] == pytest.approx((10.0 + 30.0) / 2)


def test_aggregate_custom_valid_mask():
    """Custom valid_mask overrides default finite check."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([110.0, 220.0, 330.0])
    mask = np.array([True, False, True])
    result = aggregate_direct_metrics(pred, true, valid_mask=mask)
    assert result["n_valid"] == 2
    assert result["n_failure"] == 1


def test_aggregate_empty():
    """Empty input returns zeros/nulls."""
    result = aggregate_direct_metrics(np.array([]), np.array([]))
    assert result["n_total"] == 0
    assert result["n_valid"] == 0


def test_aggregate_mismatched_shapes_raises():
    """Mismatched shapes must raise."""
    with pytest.raises(ValueError):
        aggregate_direct_metrics(np.array([1.0, 2.0]), np.array([1.0]))


def test_relative_error_zero_true():
    """When true x_{0.95} is zero, relative error is NaN (excluded)."""
    true = np.array([0.0, 100.0])
    pred = np.array([1.0, 110.0])
    result = aggregate_direct_metrics(pred, true)
    assert result["n_total"] == 2
    assert result["n_valid"] == 2
    # relative bias uses only the second row (finite rel error)
    assert result["bias_rel"] == pytest.approx(0.1)
    # absolute uses both rows
    assert result["bias"] == pytest.approx((1.0 + 10.0) / 2.0)
