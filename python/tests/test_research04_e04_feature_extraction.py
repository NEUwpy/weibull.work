import importlib.util
import math
from pathlib import Path

import numpy as np


SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "docs"
    / "research"
    / "04基于神经网络的MDM偏移量自适应选取"
    / "程序"
    / "E04-1_feature_extraction.py"
)


def load_module():
    spec = importlib.util.spec_from_file_location("e04_feature_extraction", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_compute_sample_features_matches_contract():
    module = load_module()
    sample = np.array([1.0, 2.0, 4.0, 8.0])

    features = module.compute_sample_features(sample)

    assert list(features) == module.FEATURE_COLUMNS
    assert features["order_mean"] == 3.75
    assert features["order_var"] == 7.1875
    assert features["spacing_ratio_mean"] == 2.0
    assert features["spacing_ratio_var"] == 0.0
    assert features["t1_over_median"] == 1.0 / 3.0
    assert features["tn_over_median"] == 8.0 / 3.0
    assert features["log_tn_over_t1"] == math.log(8.0)
    assert features["n"] == 4.0


def test_parse_l4_labels_uses_config_tuple_keys():
    module = load_module()
    labels = module.parse_l4_labels(
        {
            "level": "L4",
            "delta_star_by_config": {
                "(1.5, 7, 0.1)": 0.24,
                "(2.0, 10, 0.5)": 0.22,
            },
        }
    )

    assert labels[(1.5, 7, 0.1)] == 0.24
    assert labels[(2.0, 10, 0.5)] == 0.22


def test_build_feature_row_keeps_truth_out_of_feature_columns():
    module = load_module()
    sample = np.array([1.0, 2.0, 4.0, 8.0])
    risk_losses = {0.0: 1.25, 0.02: 0.75}

    row = module.build_feature_row(
        beta=1.5,
        n=4,
        gamma_ratio=0.1,
        rep=3,
        sample=sample,
        l4_delta=0.24,
        l5_delta=0.02,
        risk_losses=risk_losses,
    )

    for leaked_name in ["beta", "gamma_ratio", "gamma_true", "eta_true"]:
        assert leaked_name not in module.FEATURE_COLUMNS

    assert row["beta"] == 1.5
    assert row["gamma_ratio"] == 0.1
    assert row["rep"] == 3
    assert row["l4_delta"] == 0.24
    assert row["l5_delta"] == 0.02
    assert row["loss_d_0_00"] == 1.25
    assert row["loss_d_0_02"] == 0.75
