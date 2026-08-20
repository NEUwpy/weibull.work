"""Contract tests for the bounded E10 Z-only mechanism experiment."""

from pathlib import Path
import inspect
import os
import sys

import numpy as np
import pandas as pd


STUDY_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = STUDY_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import analyze_E10_z_only_benchmark as E10


def test_mean_normalize_is_sorted_and_scale_invariant():
    sample = np.array([10.0, 2.0, 7.0, 4.0])
    expected = np.sort(sample) / sample.mean()
    assert np.allclose(E10.mean_normalize(sample), expected)
    for factor in (1e-3, 1.0, 1e3):
        assert np.allclose(E10.mean_normalize(sample * factor), expected)


def test_repeat_partitions_are_disjoint_complete_and_frozen():
    assert not E10.FIT_REPEATS & E10.VALIDATION_REPEATS
    assert not E10.DEVELOPMENT_REPEATS & E10.CONFIRMATION_REPEATS
    assert E10.FIT_REPEATS | E10.VALIDATION_REPEATS == E10.DEVELOPMENT_REPEATS
    assert E10.DEVELOPMENT_REPEATS | E10.CONFIRMATION_REPEATS == set(range(300))
    assert E10.repeat_partition(0) == "fit"
    assert E10.repeat_partition(160) == "validation"
    assert E10.repeat_partition(200) == "confirmation"


def test_candidate_set_is_small_and_predeclared():
    assert E10.CANDIDATES == (
        "ridge", "knn", "extra_trees", "mlp_current", "mlp_wide"
    )
    assert E10.SEED == 42


def test_selected_loss_uses_curve_argmin_not_class_labels():
    predicted = np.array([[3.0, 1.0, 2.0], [0.4, 0.2, 0.1]])
    actual = np.array([[30.0, 10.0, 20.0], [4.0, 2.0, 1.0]])
    indices, losses = E10.selected_loss(predicted, actual)
    assert indices.tolist() == [1, 2]
    assert losses.tolist() == [10.0, 1.0]


def test_safe_n_iter_accepts_estimators_with_none_or_array_counts():
    class NoneEstimator:
        n_iter_ = None

    class ArrayEstimator:
        n_iter_ = np.array([3, 7, 5])

    assert E10.safe_n_iter(NoneEstimator()) == 0
    assert E10.safe_n_iter(ArrayEstimator()) == 7


def test_gap_decomposition_is_additive_on_risk_not_j1():
    df = pd.DataFrame({
        "default_loss": [9.0, 7.0],
        "l5_loss": [6.0, 4.0],
        "paper_mlp_loss": [7.0, 5.0],
        "in_domain_current_mlp_loss": [6.0, 4.0],
        "z_reference_loss": [5.0, 3.0],
        "l6_loss": [3.0, 1.0],
    })
    rows, summary = E10.gap_decomposition(df)
    assert summary["three_part_identity_abs_error"] < 1e-15
    assert np.isclose(rows.iloc[:4]["R_difference"].sum(), 6.0)
    assert summary["z_reference_status"] == "TIGHTER_ACHIEVED_Z_ONLY_REFERENCE"


def test_training_contract_has_no_parameter_inputs():
    source = inspect.getsource(E10.confirmation_run)
    assert "matrices_for_n" in source
    assert "fit_predict" in source
    training_source = inspect.getsource(E10.fit_predict)
    for forbidden in ("beta", "gamma_over_eta", "repeat_id", "raw_map"):
        assert forbidden not in training_source


def test_paper_predictions_are_recomputed_against_scan():
    source = inspect.getsource(E10.confirmation_run)
    assert "paper_losses = y_confirm" in source
    assert "paper true loss does not match scan" in source


def test_confirmation_separates_holdout_protocol_from_model_flexibility():
    source = inspect.getsource(E10.confirmation_run)
    assert '"mlp_current"' in source
    assert '"in_domain_current_mlp_loss"' in source
    gap_source = inspect.getsource(E10.gap_decomposition)
    assert "paper_mlp_to_in_domain_current_architecture" in gap_source
    assert "current_architecture_to_flexible_reference" in gap_source


def test_run_requires_explicit_flag_and_writes_candidate_only():
    assert "artifacts" in E10.OUTPUT_DIR.parts
    assert "candidate" in E10.OUTPUT_DIR.parts
    assert "formal" not in E10.OUTPUT_DIR.parts
    source = inspect.getsource(E10.main)
    assert '"--run"' in source
    assert "parser.error" in source
