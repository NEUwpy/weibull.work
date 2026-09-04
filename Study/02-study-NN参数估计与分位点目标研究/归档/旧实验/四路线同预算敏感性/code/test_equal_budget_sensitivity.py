"""Tests for the four-route equal-budget sensitivity workflow."""

from __future__ import annotations

import numpy as np

from . import equal_budget_sensitivity as EQUAL


def test_fit_paths_are_isolated_by_artifact_root():
    meta, evidence = EQUAL._paths(EQUAL.OUT, 7, 1, 42, "QP")
    assert meta == EQUAL.OUT / "fit_metadata" / "n7_f1_s42_rQP.json"
    assert evidence == EQUAL.OUT / "evidence" / "n7_f1_s42_rQP.npz"


def test_qcp_source_is_reused_not_written_into_new_artifact():
    assert EQUAL.QCP_ROOT.name == "qcp_constrained_confirm"
    assert "QCP" not in EQUAL.TRAINED_ROUTES
    assert EQUAL.ALL_ROUTES == ("P", "Q", "QP", "QCP")


def test_pairing_validation_accepts_identical_identity_fields():
    fields = ["n", "fold", "seed", "init_param_sha", "batch_order_sha",
              "network_sha", "scaler_sha", "train_rows_sha", "val_rows_sha",
              "test_rows_sha", "split_strategy"]
    meta = {field: index for index, field in enumerate(fields)}
    EQUAL._validate_pair(meta, dict(meta))


def test_reused_bootstrap_constant_ratio_is_exact():
    comparator = np.full((4, 5, 10), 0.04)
    target = np.full((4, 5, 10), 0.0324)
    got = EQUAL.QCP_CONFIRM.crossed_bootstrap_contrast(
        target, comparator, replicates=1000, seed=11)
    assert np.allclose(got["mse_difference_95ci"], [-0.0076, -0.0076])
    assert np.allclose(got["relative_rrmse_improvement_95ci"], [0.1, 0.1])

