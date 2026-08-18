"""Minimum contract tests for the formal mean-normalized confirmation."""

import inspect
import os
import sys

import numpy as np


STUDY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(STUDY_ROOT, "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6
import run_b1_mean_normalized_unseen_beta as E8B1


def test_mean_normalized_map_is_exact_scale_invariant_and_key_preserving():
    key = (2.5, 1000.0, 500.0, 0.5, 7, 3)
    sample = np.array([8.0, 2.0, 3.0, 15.0, 6.0, 10.0, 5.0])
    expected = np.sort(sample) / np.mean(sample)
    base = E8B1.mean_normalized_map({key: sample})
    assert set(base) == {key}
    assert np.allclose(base[key], expected)
    for factor in (1e-3, 1.0, 1e3):
        got = E8B1.mean_normalized_map({key: factor * sample})[key]
        assert np.allclose(got, expected, rtol=0.0, atol=1e-12)


def test_unseen_beta_contract_is_complete_and_disjoint():
    folds = E8B1.B1.get_beta_folds()
    assert len(folds) == len(CFG.BETA_GRID) == 8
    assert {fold["held_out_beta"] for fold in folds} == set(CFG.BETA_GRID)
    for fold in folds:
        train = set(fold["train_combos"])
        test = set(fold["test_combos"])
        assert not train.intersection(test)
        assert len(train) == 140 and len(test) == 20
        assert {combo[0] for combo in test} == {fold["held_out_beta"]}
        assert fold["held_out_beta"] not in {combo[0] for combo in train}


def test_confirmation_reuses_e6_training_and_train_only_scalers():
    source = inspect.getsource(E8B1.run_beta_fold)
    assert "E6.pivot_raw_vector" in source
    assert "E6.train_specialist" in source
    assert "E6.evaluate_selection" in source
    assert "StandardScaler" not in source

    train_source = inspect.getsource(E6.train_specialist)
    assert "input_scaler.fit_transform(X_train)" in train_source
    assert "input_scaler.transform(X_test)" in train_source
    assert "target_scaler.fit_transform(Y_train)" in train_source
    assert "fit_transform(X_test)" not in train_source


def test_confirmation_contract_keeps_frozen_models_and_metric():
    assert E8B1.SEEDS == [42, 2026, 3407]
    assert list(CFG.N_GRID) == [7, 10, 15, 20]
    assert list(CFG.MLP_HIDDEN_LAYERS) == [256, 128, 64]
    assert len(CFG.DELTA_GRID) == 26
    assert CFG.DEFAULT_DELTA == 0.1
    assert E8B1.MODEL_NAME == "Mean-Normalized-MLP"

