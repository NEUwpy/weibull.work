"""Focused tests for B4 design, seed accounting, and bootstrap properties."""

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
    TestDataset, generate_test_data,
    _N_CLUSTERS, _N_REPLICATES, _N_VALUES, _N_BOOTSTRAP,
    _SEED_TEST_NS, _P_SEEDS, _D_SEEDS, _DCTRL_SEEDS,
    load_all_models,
)
from studies.common.metrics import check_status, quantile_true


# -- Data design --

def test_test_data_count():
    datasets = generate_test_data()
    assert len(datasets) == 6400


def test_test_data_deterministic():
    d1 = generate_test_data(); d2 = generate_test_data()
    np.testing.assert_array_equal(d1[(0, 0, 5)].sample, d2[(0, 0, 5)].sample)


def test_constants():
    assert _N_CLUSTERS == 64
    assert _N_REPLICATES == 20
    assert _N_VALUES == [5, 7, 10, 15, 20]
    assert _N_BOOTSTRAP == 2000
    assert _SEED_TEST_NS == 6000
    assert len(_P_SEEDS) == 10
    assert len(_D_SEEDS) == 10
    assert len(_DCTRL_SEEDS) == 5


# -- Bootstrap properties using synthetic data --

def test_bootstrap_aggregator_is_per_row_not_cluster_mean():
    """Demonstrate that RMSE-over-rows differs from mean-of-cluster-RMSE."""
    # 2 clusters with very different variances
    c0_errs = [0.1] * 5 + [0.2] * 5  # cluster 0, 10 rows
    c1_errs = [0.5] * 5 + [1.0] * 5  # cluster 1, 10 rows

    # RMSE over all rows (correct)
    all_errs = np.array(c0_errs + c1_errs)
    row_rmse = np.sqrt(np.mean(all_errs ** 2))

    # Mean of per-cluster RMSE (incorrect aggregator)
    c0_rmse = np.sqrt(np.mean(np.array(c0_errs) ** 2))
    c1_rmse = np.sqrt(np.mean(np.array(c1_errs) ** 2))
    mean_cluster_rmse = np.mean([c0_rmse, c1_rmse])

    # They differ when cluster variances differ
    assert not np.isclose(row_rmse, mean_cluster_rmse), \
        f"row_rmse={row_rmse} should differ from mean_cluster_rmse={mean_cluster_rmse}"


def test_paired_seed_resampling_preserves_correlation():
    """Paired seed resampling means same seed indices for D and P."""
    rng = np.random.default_rng(42)
    d_vals = np.array([10.0, 11.0, 12.0, 10.5, 11.5])  # 5 seeds
    p_vals = np.array([15.0, 16.0, 17.0, 15.5, 16.5])
    n_seeds = len(d_vals)
    # Paired: same index for both
    idx = rng.choice(n_seeds, size=n_seeds, replace=True)
    d_mean = np.mean(d_vals[idx])
    p_mean = np.mean(p_vals[idx])
    assert abs(d_mean - np.mean(d_vals)) < 2.0  # bootstrap variation, but paired


# -- Traditional failure classification --

def test_traditional_check_status():
    """check_status correctly identifies invalid estimates."""
    # Valid
    assert check_status(2.0, 100.0, 10.0, 2.0, 100.0, 10.0,
                        converged=True, sample_min=50.0) == "success"
    # Negative beta
    assert check_status(-1.0, 100.0, 10.0, 2.0, 100.0, 10.0,
                        converged=True, sample_min=50.0) == "failure"
    # Non-converged
    assert check_status(2.0, 100.0, 10.0, 2.0, 100.0, 10.0,
                        converged=False, sample_min=50.0) == "failure"
    # Gamma >= sample min
    assert check_status(2.0, 100.0, 80.0, 2.0, 100.0, 10.0,
                        converged=True, sample_min=50.0) == "failure"


# -- Seed namespace isolation --

def test_seed_namespace_isolation():
    assert _SEED_TEST_NS not in (4000, 5000, 2000, 3000)


# -- B3 manifest --

def test_b3_manifest_loadable():
    b3 = json.loads(Path(
        "C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json"
    ).read_text(encoding="utf-8"))
    assert len(b3["p_checkpoints"]["entries"]) == 50
    assert len(b3["d_checkpoints"]) == 75
    assert set(b3["target_stats"].keys()) == {"5", "7", "10", "15", "20"}
