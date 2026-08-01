"""Focused tests for B4 core test design, seed accounting, and config freeze."""

from pathlib import Path
import json
import sys

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
PYTHON = REPO_ROOT / "python"
for p in [STUDY_CODE, PYTHON]:
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from study02b.evaluate_b4 import (
    TestDataset,
    generate_test_data,
    _N_CLUSTERS,
    _N_REPLICATES,
    _N_VALUES,
    _N_BOOTSTRAP,
    _SEED_TEST_NS,
    load_all_models,
)


def test_test_data_count():
    """Must generate exactly 6,400 datasets."""
    datasets = generate_test_data()
    assert len(datasets) == _N_CLUSTERS * _N_REPLICATES * len(_N_VALUES) == 6400


def test_test_data_keys():
    """All expected (cluster, replicate, n) combinations present."""
    datasets = generate_test_data()
    for ci in range(_N_CLUSTERS):
        for ri in range(_N_REPLICATES):
            for n in _N_VALUES:
                assert (ci, ri, n) in datasets


def test_test_data_true_x095_is_finite():
    """All true x0.95 values must be finite and positive."""
    datasets = generate_test_data()
    for td in datasets.values():
        assert np.isfinite(td.true_x095)
        assert td.true_x095 > 0


def test_test_data_deterministic():
    """Same seed → same first dataset."""
    d1 = generate_test_data()
    d2 = generate_test_data()
    td1 = d1[(0, 0, 5)]
    td2 = d2[(0, 0, 5)]
    np.testing.assert_array_equal(td1.sample, td2.sample)
    assert td1.true_x095 == td2.true_x095


def test_test_data_params_in_core_domain():
    """Parameters must be within the core domain."""
    datasets = generate_test_data()
    for td in datasets.values():
        assert 1.2 <= td.beta <= 4.0
        assert 100.0 <= td.eta <= 10000.0
        rho = td.gamma / td.eta
        assert 0.0 <= rho <= 1.0


def test_constants():
    assert _N_CLUSTERS == 64
    assert _N_REPLICATES == 20
    assert _N_VALUES == [5, 7, 10, 15, 20]
    assert _N_BOOTSTRAP == 2000
    assert _SEED_TEST_NS == 6000


def test_b3_manifest_loadable():
    """B3 manifest must be loadable and contain required sections."""
    b3_path = Path(
        "C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json"
    )
    b3 = json.loads(b3_path.read_text(encoding="utf-8"))
    assert "p_checkpoints" in b3
    assert "d_checkpoints" in b3
    assert "target_stats" in b3
    assert len(b3["p_checkpoints"]["entries"]) == 50
    assert len(b3["d_checkpoints"]) == 75
    assert set(b3["target_stats"].keys()) == {"5", "7", "10", "15", "20"}


def test_models_loadable():
    """All models from B3 manifest must load without error."""
    b3_path = Path(
        "C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json"
    )
    b3 = json.loads(b3_path.read_text(encoding="utf-8"))
    models = load_all_models(b3)
    assert len(models["P"]) == 50
    assert len(models["D"]) == 50
    assert len(models["Dctrl"]) == 25


def test_seed_namespace_isolation():
    """B test seed namespace must differ from training/validation namespaces."""
    assert _SEED_TEST_NS not in (4000, 5000, 2000, 3000)
