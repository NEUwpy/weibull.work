from pathlib import Path
import sys

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CODE = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.evaluation import (
    cluster_bootstrap_difference,
    evaluate_rows,
    global_better_from_intervals,
    parameter_loss,
)


def test_parameter_loss_matches_frozen_formula():
    result = parameter_loss(2.2, 90.0, 15.0, 2.0, 100.0, 10.0)
    expected = np.sqrt((0.1**2 + (-0.1)**2 + 0.05**2) / 3.0)
    assert result == pytest.approx(expected)


def test_evaluation_keeps_failures_and_applies_penalty():
    rows = [
        {"beta_hat": 2.0, "eta_hat": 100.0, "gamma_hat": 10.0, "beta": 2.0, "eta": 100.0, "gamma": 10.0, "sample_min": 20.0, "converged": True},
        {"beta_hat": None, "eta_hat": None, "gamma_hat": None, "beta": 2.0, "eta": 100.0, "gamma": 10.0, "sample_min": 20.0, "converged": False},
    ]
    result = evaluate_rows(rows, failure_penalty=10.0)
    assert result["n_total"] == 2
    assert result["n_failure"] == 1
    assert result["failure_rate"] == 0.5
    assert result["conditional_mean_l_param"] == pytest.approx(0.0)
    assert result["unconditional_mean_l_param"] == pytest.approx(5.0)


def test_single_parameter_gain_cannot_be_called_global_better():
    decision = global_better_from_intervals(
        failure_diff_upper=0.005,
        l_param_improvement_lower=0.02,
        component_worsening_upper={"beta": 0.01, "eta": 0.08, "gamma": 0.02},
    )
    assert decision == "tradeoff"


def test_cluster_bootstrap_is_reproducible():
    clusters = np.repeat(np.arange(8), 3)
    a = np.linspace(0.2, 1.0, len(clusters))
    b = a + 0.1
    first = cluster_bootstrap_difference(a, b, clusters, replicates=200, seed=520001)
    second = cluster_bootstrap_difference(a, b, clusters, replicates=200, seed=520001)
    assert first == second
    assert first["mean_improvement"] == pytest.approx(0.1)
