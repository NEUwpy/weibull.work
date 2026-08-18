"""Minimum contract tests for the E7 candidate representation screen."""

import inspect
import os
import sys

import numpy as np
import pandas as pd


STUDY_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CODE_DIR = os.path.join(STUDY_ROOT, "code")
if CODE_DIR not in sys.path:
    sys.path.insert(0, CODE_DIR)

import dim_raw_config as CFG
import run_E6b_dimensional_raw_specialist as E6
import run_E7_scale_invariant_input_screen as E7


def test_representation_formulas_are_exact_and_not_centered():
    x = np.array([2.0, 5.0, 11.0, 17.0])
    ordered = np.sort(x)
    assert np.allclose(E7.represent_sample(x, "mean"), ordered / ordered.mean())
    assert np.allclose(
        E7.represent_sample(x, "sample_sd"), ordered / ordered.std(ddof=1)
    )
    assert np.allclose(
        E7.represent_sample(x, "rms"), ordered / np.sqrt(np.mean(ordered**2))
    )
    assert not np.isclose(E7.represent_sample(x, "sample_sd").mean(), 0.0)


def test_all_representations_are_scale_invariant():
    x = np.array([1.2, 2.1, 3.4, 9.7, 12.0, 14.5, 18.2])
    for name in E7.REPRESENTATIONS:
        base = E7.represent_sample(x, name)
        for factor in E7.SCALES:
            assert np.allclose(E7.represent_sample(factor * x, name), base)


def test_invalid_representation_and_zero_scale_fail():
    with np.testing.assert_raises(ValueError):
        E7.represent_sample(np.ones(7), "sample_sd")
    with np.testing.assert_raises(ValueError):
        E7.represent_sample(np.arange(1, 8), "unknown")


def test_representations_preserve_sample_keys_and_width():
    raw_map = {
        (2.0, 1000.0, 500.0, 0.5, 7, 0): np.arange(10.0, 17.0),
        (2.0, 1000.0, 500.0, 0.5, 7, 1): np.arange(20.0, 27.0),
    }
    for name in E7.REPRESENTATIONS:
        rep = E7.build_representation_map(raw_map, name)
        assert set(rep) == set(raw_map)
        assert all(value.shape == (7,) for value in rep.values())


def test_screen_reuses_e6_split_and_training_implementation():
    source = inspect.getsource(E7.run_one)
    assert "E6.get_combo_split()" in source
    assert "E6.pivot_raw_vector" in source
    assert "E6.train_specialist" in source
    assert "StandardScaler" not in source
    assert E6.get_combo_split() == E6.get_combo_split()
    assert CFG.STABILITY_SEEDS == [42, 2026, 3407]


def test_e6_scaler_contract_is_train_fit_test_transform():
    source = inspect.getsource(E6.train_specialist)
    assert "input_scaler.fit_transform(X_train)" in source
    assert "input_scaler.transform(X_test)" in source
    assert "input_scaler.fit_transform(X_test)" not in source


def test_aggregation_uses_pooled_losses_not_mean_model_j1():
    rows = []
    meta = []
    for representation in E7.REPRESENTATIONS:
        for seed in CFG.STABILITY_SEEDS:
            for n_val in CFG.N_GRID:
                losses = [1.0, 9.0]
                for loss in losses:
                    rows.append({
                        "representation": representation,
                        "seed": seed,
                        "n": n_val,
                        "true_loss": loss,
                        "is_valid": True,
                    })
                meta.append({
                    "representation": representation,
                    "n": n_val,
                    "fold": 1,
                    "seed": seed,
                    "J1": np.sqrt(np.mean(losses)),
                    "failure_rate": 0.0,
                    "n_iter": 1,
                    "runtime_s": 0.1,
                })
    result = E7.aggregate(meta, pd.DataFrame(rows), default_j1=4.0)
    expected = np.sqrt(5.0)
    assert np.allclose(result["seed_metrics"]["pooled_J1"], expected)
    assert np.allclose(result["summary"]["pooled_J1_mean"], expected)
