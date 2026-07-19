"""Contract tests for the Study01 raw-vs-feature input pilot."""

import os
import sys

import numpy as np
import pandas as pd


PROJECT_ROOT = r"D:\weibull"
STUDY_CODE_DIR = os.path.join(
    PROJECT_ROOT, "Study", "01-study-MDM最小偏移量优化研究", "code"
)
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

import run_input_representation_pilot as pilot


def test_raw_encoding_is_fixed_width_and_masked():
    samples = [np.array([1.0, 2.0]), np.array([3.0, 4.0, 5.0])]
    X = pilot.encode_sorted_samples(samples, mean=0.0, std=1.0)
    assert X.shape == (2, pilot.RAW_MAX_N * 2 + 1)
    assert np.allclose(X[0, :2], [1.0, 2.0])
    assert np.allclose(X[0, 2:pilot.RAW_MAX_N], 0.0)
    assert np.allclose(X[0, pilot.RAW_MAX_N:pilot.RAW_MAX_N + 2], 1.0)
    assert np.allclose(X[0, pilot.RAW_MAX_N + 2:-1], 0.0)
    assert X[0, -1] == 2.0


def test_raw_input_contract_has_no_true_parameters():
    banned = {"beta", "eta", "gamma", "gamma_over_eta", "repeat_id", "seed", "combo_id", "delta"}
    assert not banned.intersection(pilot.RAW_INPUT_FIELDS)


def test_feature_without_n_contract_removes_only_sample_size():
    assert "n" in pilot.e3b.SAMPLE_FEATURE_COLS
    assert "n" not in pilot.FEATURE_FIELDS_WITHOUT_N
    assert len(pilot.FEATURE_FIELDS_WITHOUT_N) == len(pilot.e3b.SAMPLE_FEATURE_COLS) - 1
    assert set(pilot.FEATURE_FIELDS_WITHOUT_N) == set(pilot.e3b.SAMPLE_FEATURE_COLS) - {"n"}


def test_fold_partition_is_disjoint_and_complete():
    rows = []
    for beta in pilot.e3b.BETA_GRID:
        for gamma_ratio in pilot.e3b.GAMMA_OVER_ETA_GRID:
            for n in pilot.e3b.N_GRID:
                rows.append({"beta": beta, "gamma_over_eta": gamma_ratio, "n": n, "repeat_id": 0})
    df = pd.DataFrame(rows)
    train_mask, test_mask, fold = pilot.split_fold(df, 1)
    assert not np.any(train_mask & test_mask)
    assert np.all(train_mask | test_mask)
    assert int(test_mask.sum()) == 9
    assert len(fold["test_combos"]) == 9


def test_sample_size_specialist_partitions_cover_each_fold_split():
    df, _ = pilot.load_cached_samples()
    train_mask, test_mask, _ = pilot.split_fold(df, 1)
    df_train = df.loc[train_mask]
    df_test = df.loc[test_mask]
    assert sorted(df_train["n"].unique().tolist()) == sorted(pilot.e3b.N_GRID)
    assert sorted(df_test["n"].unique().tolist()) == sorted(pilot.e3b.N_GRID)
    assert df_train.groupby("n").size().to_dict() == {7: 12000, 10: 12000, 20: 12000}
    assert df_test.groupby("n").size().to_dict() == {7: 3000, 10: 3000, 20: 3000}


def test_selected_j1_uses_true_loss_at_predicted_argmin():
    df = pd.DataFrame({"n": [7, 7, 10]})
    Y_true = np.array([[1.0, 4.0], [9.0, 1.0], [4.0, 16.0]])
    Y_pred = np.array([[0.0, 1.0], [2.0, 0.0], [0.0, 3.0]])
    metrics, selected_idx, selected_loss = pilot.evaluate_predictions(df, Y_true, Y_pred)
    assert selected_idx.tolist() == [0, 1, 0]
    assert selected_loss.tolist() == [1.0, 1.0, 4.0]
    assert np.isclose(metrics["pooled_J1"], np.sqrt(2.0))
    assert np.isclose(metrics["per_n"]["7"]["J1"], 1.0)
    assert np.isclose(metrics["per_n"]["10"]["J1"], 2.0)
