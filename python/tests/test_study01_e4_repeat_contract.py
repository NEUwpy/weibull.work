"""Regression tests for Study01 E4 boundary/off-grid repeat contracts."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[2]
E4_SCRIPT = (
    PROJECT_ROOT
    / "Study"
    / "01-study-MDM最小偏移量优化研究"
    / "code"
    / "run_E4_formal_validation.py"
)


def load_e4_module():
    spec = importlib.util.spec_from_file_location(
        "study01_e4_formal_validation_repeat_test", E4_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def make_risk_data(combo_id, beta, gamma_over_eta, n, repeat_ids):
    rows = []
    for repeat_id in repeat_ids:
        for delta in (0.0, 0.02):
            rows.append({
                "combo_id": combo_id,
                "beta": beta,
                "eta": 1.0,
                "gamma": gamma_over_eta,
                "gamma_over_eta": gamma_over_eta,
                "n": n,
                "repeat_id": repeat_id,
                "delta": delta,
            })
    return pd.DataFrame(rows)


@pytest.mark.parametrize("repeat_count", [500, 1000])
def test_feature_rows_follow_actual_repeat_count(monkeypatch, repeat_count):
    module = load_e4_module()
    calls = []

    def fake_generate_sample(beta, eta, gamma, n, repeat_id, seed):
        calls.append(repeat_id)
        return np.arange(1, n + 1, dtype=float)

    monkeypatch.setattr(module, "generate_sample", fake_generate_sample)
    combo = ("B01", 1.2, 0.0, 5)
    risk_data = make_risk_data(*combo, repeat_ids=range(repeat_count))

    features = module.build_feature_table_for_combos([combo], risk_data)

    assert len(features) == repeat_count
    assert features["repeat_id"].tolist() == list(range(repeat_count))
    assert calls == list(range(repeat_count))


def test_non_contiguous_repeat_ids_are_preserved_without_padding(monkeypatch):
    module = load_e4_module()
    calls = []

    def fake_generate_sample(beta, eta, gamma, n, repeat_id, seed):
        calls.append(repeat_id)
        return np.arange(1, n + 1, dtype=float)

    monkeypatch.setattr(module, "generate_sample", fake_generate_sample)
    combo = ("O01", 1.8, 0.3, 12)
    repeat_ids = [2, 7, 503, 1001]
    risk_data = make_risk_data(*combo, repeat_ids=repeat_ids)

    features = module.build_feature_table_for_combos([combo], risk_data)

    assert features["repeat_id"].tolist() == repeat_ids
    assert calls == repeat_ids


def test_duplicate_risk_key_is_rejected_before_sample_generation(monkeypatch):
    module = load_e4_module()
    combo = ("B01", 1.2, 0.0, 5)
    risk_data = make_risk_data(*combo, repeat_ids=[0])
    risk_data = pd.concat([risk_data, risk_data.iloc[[0]]], ignore_index=True)
    monkeypatch.setattr(
        module,
        "generate_sample",
        lambda *args, **kwargs: pytest.fail("sample generation must not run"),
    )

    with pytest.raises(ValueError, match="duplicate keys"):
        module.build_feature_table_for_combos([combo], risk_data)


def test_missing_sample_key_column_is_rejected():
    module = load_e4_module()
    combo = ("B01", 1.2, 0.0, 5)
    risk_data = make_risk_data(*combo, repeat_ids=[0]).drop(columns="repeat_id")

    with pytest.raises(ValueError, match="missing required sample-key columns"):
        module.build_feature_table_for_combos([combo], risk_data)


def test_conflicting_sample_metadata_is_rejected(monkeypatch):
    module = load_e4_module()
    combo = ("B01", 1.2, 0.0, 5)
    risk_data = make_risk_data(*combo, repeat_ids=[0])
    risk_data.loc[risk_data["delta"] == 0.02, "beta"] = 1.3
    monkeypatch.setattr(
        module,
        "generate_sample",
        lambda *args, **kwargs: pytest.fail("sample generation must not run"),
    )

    with pytest.raises(ValueError, match="inconsistent metadata for sample keys"):
        module.build_feature_table_for_combos([combo], risk_data)


def test_combo_metadata_must_match_frozen_combo_list(monkeypatch):
    module = load_e4_module()
    combo = ("B01", 1.2, 0.0, 5)
    risk_data = make_risk_data("B01", 1.3, 0.0, 5, repeat_ids=[0])
    monkeypatch.setattr(
        module,
        "generate_sample",
        lambda *args, **kwargs: pytest.fail("sample generation must not run"),
    )

    with pytest.raises(ValueError, match="does not match frozen combo list"):
        module.build_feature_table_for_combos([combo], risk_data)
