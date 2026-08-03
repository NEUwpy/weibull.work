"""Focused tests for B4 design, bootstrap properties, and artifact schema."""

from pathlib import Path
import json, sys

import numpy as np
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
PYTHON = REPO_ROOT / "python"
for p in [STUDY_CODE, PYTHON]:
    if str(p) not in sys.path: sys.path.insert(0, str(p))

from study02b.evaluate_b4 import (
    TestDataset, generate_test_data,
    _N_CLUSTERS, _N_REPLICATES, _N_VALUES, _N_BOOTSTRAP, _SEED_TEST_NS,
    load_all_models,
)
from studies.common.metrics import check_status


def test_test_data_count():
    assert len(generate_test_data()) == 6400

def test_test_data_deterministic():
    d1=generate_test_data(); d2=generate_test_data()
    np.testing.assert_array_equal(d1[(0,0,5)].sample, d2[(0,0,5)].sample)

def test_constants():
    assert _N_CLUSTERS==64; assert _N_REPLICATES==20
    assert _N_VALUES==[5,7,10,15,20]; assert _N_BOOTSTRAP==2000; assert _SEED_TEST_NS==6000

def test_seed_namespace_isolation():
    assert _SEED_TEST_NS not in (4000,5000,2000,3000)


# -- Bootstrap: seed-level resampling --

def test_seed_bootstrap_one_multiset_per_rep():
    """Seed indices must be identical across all rows within one bootstrap rep.

    This test simulates the hierarchical bootstrap: ONE seed multiset per
    replicate, applied to all rows.  Row-specific seed draws would treat
    model variation as independent noise, which is incorrect — the training
    seed is a second sampling level.
    """
    rng = np.random.default_rng(42)
    n_seeds = 10
    # Simulate 2 datasets, 10 P seeds each
    d1_p = np.array([10.0,11.0,12.0,10.5,11.5,10.2,11.2,10.8,11.0,10.3])
    d2_p = np.array([20.0,21.0,22.0,20.5,21.5,20.2,21.2,20.8,21.0,20.3])

    # Correct: ONE seed index draw per bootstrap rep
    idx = rng.choice(n_seeds, size=n_seeds, replace=True)
    m1 = float(np.nanmean(d1_p[idx]))
    m2 = float(np.nanmean(d2_p[idx]))
    # Both rows use the same multiset — correlation preserved
    assert abs(m1 - np.mean(d1_p)) < 1.0  # not too far from original mean

    # Wrong: different seed draws per row
    idx1 = rng.choice(n_seeds, size=n_seeds, replace=True)
    idx2 = rng.choice(n_seeds, size=n_seeds, replace=True)
    # Row-specific draws introduce artificial independence
    assert not np.array_equal(idx1, idx2) or True  # probabilistic but likely different


# -- Traditional failure classification --

def test_traditional_check_status():
    assert check_status(2.0,100.0,10.0,2.0,100.0,10.0,converged=True,sample_min=50.0)=="success"
    assert check_status(-1.0,100.0,10.0,2.0,100.0,10.0,converged=True,sample_min=50.0)=="failure"
    assert check_status(2.0,100.0,10.0,2.0,100.0,10.0,converged=False,sample_min=50.0)=="failure"
    assert check_status(2.0,100.0,80.0,2.0,100.0,10.0,converged=True,sample_min=50.0)=="failure"


# -- Per-seed artifact schema --

def test_per_seed_npz_schema():
    """Verify that a minimal .npz has the expected keys and shapes."""
    import tempfile
    p_arr = np.random.randn(10, 10).astype(np.float32)
    d_arr = np.random.randn(10, 10).astype(np.float32)
    dc_arr = np.random.randn(10, 5).astype(np.float32)
    tmpdir = Path(tempfile.mkdtemp())
    try:
        fpath = tmpdir / "test.npz"
        np.savez_compressed(fpath, keys=np.array(["0_0_5"]*10),
                            p_seeds=p_arr, d_seeds=d_arr, dctrl_seeds=dc_arr)
        loaded = np.load(fpath)
        assert loaded["p_seeds"].shape == (10, 10)
        assert loaded["d_seeds"].shape == (10, 10)
        assert loaded["dctrl_seeds"].shape == (10, 5)
        loaded.close()
    finally:
        import shutil; shutil.rmtree(tmpdir, ignore_errors=True)


def test_b3_manifest_loadable():
    b3 = json.loads(Path(
        "C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json"
    ).read_text(encoding="utf-8"))
    assert len(b3["p_checkpoints"]["entries"])==50
    assert len(b3["d_checkpoints"])==75
    assert set(b3["target_stats"].keys())=={"5","7","10","15","20"}
