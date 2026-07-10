from pathlib import Path
import sys

import numpy as np
import pandas as pd
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FIGURE_CODE = REPO_ROOT / "Study" / "01-study-MDM最小偏移量优化研究" / "code"
if str(FIGURE_CODE) not in sys.path:
    sys.path.insert(0, str(FIGURE_CODE))

import plot_fig_diagnostics as figure_module


def test_prepare_paired_offset_diagnostics_aligns_repeat_ids_and_classifies_changes():
    rows = pd.DataFrame(
        [
            {"repeat_id": 1, "delta": 0.1, "gamma_hat": 1.30},
            {"repeat_id": 0, "delta": 0.0, "gamma_hat": 0.80},
            {"repeat_id": 2, "delta": 0.1, "gamma_hat": 1.10},
            {"repeat_id": 1, "delta": 0.0, "gamma_hat": 0.90},
            {"repeat_id": 0, "delta": 0.1, "gamma_hat": 0.90},
            {"repeat_id": 2, "delta": 0.0, "gamma_hat": 0.90},
        ]
    )

    paired = figure_module.prepare_paired_offset_diagnostics(
        rows, gamma_true=1.0, eta_true=1.0
    )

    assert paired["repeat_id"].tolist() == [0, 1, 2]
    np.testing.assert_allclose(paired["abs_error_zero"], [0.20, 0.10, 0.10])
    np.testing.assert_allclose(paired["abs_error_offset"], [0.10, 0.30, 0.10])
    assert paired["effect"].tolist() == ["improved", "worsened", "tied"]


def test_prepare_paired_offset_diagnostics_rejects_missing_pairs():
    rows = pd.DataFrame(
        [
            {"repeat_id": 0, "delta": 0.0, "gamma_hat": 0.80},
            {"repeat_id": 0, "delta": 0.1, "gamma_hat": 0.90},
            {"repeat_id": 1, "delta": 0.0, "gamma_hat": 1.10},
        ]
    )

    with pytest.raises(ValueError, match="complete paired observations"):
        figure_module.prepare_paired_offset_diagnostics(
            rows, gamma_true=1.0, eta_true=1.0
        )


def test_representative_samples_use_symmetric_median_effect_rules():
    def row(rid, err_zero, err_offset):
        return {
            "rid": rid,
            "gamma_zero_curve": 1.0,
            "err_zero_curve": err_zero,
            "err_offset": err_offset,
        }

    results = [
        row(0, 0.01, 0.02),   # closest change to neutral: +0.01
        row(1, 1.00, 0.10),   # improvement change: -0.90
        row(2, 0.80, 0.30),   # improvement median: -0.50
        row(3, 0.40, 0.30),   # improvement change: -0.10
        row(4, 0.10, 0.20),   # worsening change: +0.10
        row(5, 0.10, 0.40),   # worsening median: +0.30
        row(6, 0.10, 0.80),   # worsening change: +0.70
        row(7, 0.001, 0.80),  # closest zero-error, but strongly worsened
    ]

    neutral, typical_improvement, typical_worsening = (
        figure_module._select_representative_samples(results, gamma_true=1.0)
    )

    assert neutral["rid"] == 0
    assert typical_improvement["rid"] == 2
    assert typical_worsening["rid"] == 5
