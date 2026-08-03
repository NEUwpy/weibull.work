"""Unit tests for D-route x_{0.95} metric adapter."""

from pathlib import Path
import sys
import warnings

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

from study02b.metrics import direct_errors, aggregate_direct_metrics, _intrinsic_valid


# -- intrinsic validity --

def test_intrinsic_valid_positive_finite():
    mask = _intrinsic_valid(np.array([1.0, 100.0, 5000.0]))
    np.testing.assert_array_equal(mask, [True, True, True])


def test_intrinsic_valid_zero_is_invalid():
    mask = _intrinsic_valid(np.array([0.0, 100.0, -50.0]))
    np.testing.assert_array_equal(mask, [False, True, False])


def test_intrinsic_valid_negative_is_invalid():
    mask = _intrinsic_valid(np.array([-1.0, 100.0, -0.01]))
    np.testing.assert_array_equal(mask, [False, True, False])


def test_intrinsic_valid_inf_is_invalid():
    mask = _intrinsic_valid(np.array([np.inf, 100.0, -np.inf, np.nan]))
    np.testing.assert_array_equal(mask, [False, True, False, False])


# -- direct_errors --

def test_direct_errors_perfect_prediction():
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([100.0, 200.0, 300.0])
    errors = direct_errors(pred, true)
    np.testing.assert_allclose(errors["absolute"], [0.0, 0.0, 0.0])
    np.testing.assert_allclose(errors["relative"], [0.0, 0.0, 0.0])


def test_direct_errors_positive_bias():
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([110.0, 220.0, 330.0])
    errors = direct_errors(pred, true)
    np.testing.assert_allclose(errors["absolute"], [10.0, 20.0, 30.0])
    np.testing.assert_allclose(errors["relative"], [0.1, 0.1, 0.1])


def test_direct_errors_negative_bias():
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([90.0, 180.0, 270.0])
    errors = direct_errors(pred, true)
    np.testing.assert_allclose(errors["absolute"], [-10.0, -20.0, -30.0])
    np.testing.assert_allclose(errors["relative"], [-0.1, -0.1, -0.1])


def test_direct_errors_zero_true_no_warning():
    """Relative error for zero true value is NaN without RuntimeWarning."""
    true = np.array([0.0, 100.0])
    pred = np.array([5.0, 110.0])
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        errors = direct_errors(pred, true)
    assert errors["absolute"][0] == pytest.approx(5.0)
    assert np.isnan(errors["relative"][0])
    assert errors["relative"][1] == pytest.approx(0.1)
    # No RuntimeWarning from division
    runtime_warnings = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert len(runtime_warnings) == 0, f"unexpected RuntimeWarning: {runtime_warnings}"


# -- aggregate_direct_metrics --

def test_aggregate_perfect():
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
    true = np.array([100.0, 100.0, 100.0])
    pred = np.array([110.0, 110.0, 110.0])
    result = aggregate_direct_metrics(pred, true)
    assert result["bias"] == pytest.approx(10.0)
    assert result["rmse"] == pytest.approx(10.0)
    assert result["mae"] == pytest.approx(10.0)
    assert result["bias_rel"] == pytest.approx(0.1)
    assert result["rmse_rel"] == pytest.approx(0.1)


def test_aggregate_zero_predictions_invalid():
    """Zero predictions are intrinsically invalid (frozen validity rule)."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([0.0, 220.0, 330.0])
    result = aggregate_direct_metrics(pred, true)
    assert result["n_total"] == 3
    assert result["n_valid"] == 2  # zero excluded
    assert result["n_failure"] == 1


def test_aggregate_negative_predictions_invalid():
    """Negative predictions are intrinsically invalid."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([-10.0, 220.0, 330.0])
    result = aggregate_direct_metrics(pred, true)
    assert result["n_total"] == 3
    assert result["n_valid"] == 2
    assert result["n_failure"] == 1


def test_aggregate_invalid_predictions():
    """Non-finite predictions are excluded by intrinsic validity."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([110.0, np.inf, 330.0])
    result = aggregate_direct_metrics(pred, true)
    assert result["n_total"] == 3
    assert result["n_valid"] == 2
    assert result["n_failure"] == 1
    assert result["bias"] == pytest.approx((10.0 + 30.0) / 2.0)


def test_aggregate_custom_mask_is_combined_not_override():
    """Custom mask is combined (AND) with intrinsic validity, not override."""
    true = np.array([100.0, 200.0, 300.0, 400.0])
    # Row 0: valid prediction, mask=False → excluded (mask says no)
    # Row 1: valid prediction, mask=True → included
    # Row 2: zero prediction, mask=True → excluded (intrinsic says no)
    # Row 3: valid prediction, mask=True → included
    pred = np.array([110.0, 220.0, 0.0, 440.0])
    mask = np.array([False, True, True, True])
    result = aggregate_direct_metrics(pred, true, valid_mask=mask)
    # Rows 1 and 3 only: both pass intrinsic AND mask
    assert result["n_total"] == 4
    assert result["n_valid"] == 2
    assert result["n_failure"] == 2


def test_aggregate_nonfinite_under_custom_mask():
    """Non-finite values are excluded even if custom mask says True."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([110.0, np.nan, 330.0])
    mask = np.array([True, True, True])  # all True but row 1 is non-finite
    result = aggregate_direct_metrics(pred, true, valid_mask=mask)
    assert result["n_valid"] == 2
    assert result["n_failure"] == 1


def test_aggregate_malformed_mask_shape_raises():
    """Custom mask with wrong shape must raise."""
    true = np.array([100.0, 200.0, 300.0])
    pred = np.array([110.0, 220.0, 330.0])
    with pytest.raises(ValueError):
        aggregate_direct_metrics(pred, true, valid_mask=np.array([True, False]))


def test_aggregate_empty():
    result = aggregate_direct_metrics(np.array([]), np.array([]))
    assert result["n_total"] == 0
    assert result["n_valid"] == 0


def test_aggregate_mismatched_shapes_raises():
    with pytest.raises(ValueError):
        aggregate_direct_metrics(np.array([1.0, 2.0]), np.array([1.0]))


def test_relative_error_zero_true():
    """When true x_{0.95} is zero, relative error is NaN (excluded from rel summary)."""
    true = np.array([0.0, 100.0])
    pred = np.array([1.0, 110.0])
    result = aggregate_direct_metrics(pred, true)
    assert result["n_total"] == 2
    assert result["n_valid"] == 2  # pred[0]=1.0 is finite and > 0
    assert result["bias_rel"] == pytest.approx(0.1)  # only row 1
    assert result["bias"] == pytest.approx((1.0 + 10.0) / 2.0)
