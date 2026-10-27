"""Product contract tests for AI-assisted MDM process-variable selection."""

import os
import sys

import numpy as np
import pytest


sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from ai_methods.mdm_process_optimizer import (  # noqa: E402
    MDMProcessOptimizationError,
    SUPPORTED_SAMPLE_SIZES,
    select_mdm_offset,
)


SAMPLE_N7 = [1314.68, 1509.32, 1672.86, 1832.55, 2005.13, 2215.02, 2536.73]


def test_selector_returns_the_frozen_discrete_curve_contract():
    result = select_mdm_offset(SAMPLE_N7)

    assert result["model_n"] == 7
    assert len(result["delta_grid"]) == 26
    assert result["delta_grid"][0] == 0.0
    assert result["delta_grid"][-1] == 0.5
    assert len(result["predicted_loss_curve"]) == 26
    assert np.all(np.isfinite(result["predicted_loss_curve"]))
    assert result["selected_index"] == int(np.argmin(result["predicted_loss_curve"]))
    assert result["selected_delta"] == result["delta_grid"][result["selected_index"]]
    assert result["default_delta"] == 0.1


def test_selector_is_scale_invariant_for_the_same_sample_shape():
    reference = select_mdm_offset(SAMPLE_N7)
    scaled = select_mdm_offset([value * 1000.0 for value in SAMPLE_N7])

    assert scaled["selected_delta"] == reference["selected_delta"]
    assert np.allclose(
        scaled["predicted_loss_curve"],
        reference["predicted_loss_curve"],
        rtol=0.0,
        atol=2e-12,
    )


@pytest.mark.parametrize("n", [5, 8, 12, 21])
def test_selector_rejects_unsupported_sample_sizes(n):
    with pytest.raises(MDMProcessOptimizationError, match="仅支持样本量"):
        select_mdm_offset(list(range(1, n + 1)))


@pytest.mark.parametrize(
    "sample",
    [
        [1, 2, 3, 4, 5, 6, float("nan")],
        [1, 2, 3, 4, 5, 6, float("inf")],
        [0, 1, 2, 3, 4, 5, 6],
        [-1, 1, 2, 3, 4, 5, 6],
    ],
)
def test_selector_rejects_invalid_complete_failure_samples(sample):
    with pytest.raises(MDMProcessOptimizationError):
        select_mdm_offset(sample)


def test_supported_sample_size_contract_is_explicit():
    assert SUPPORTED_SAMPLE_SIZES == (7, 10, 15, 20)
