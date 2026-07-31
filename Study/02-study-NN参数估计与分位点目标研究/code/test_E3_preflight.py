import importlib.util
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).with_name("E3-equivariance-robustness.py")
SPEC = importlib.util.spec_from_file_location("e3", SCRIPT)
E3 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E3)


ROW = {"beta": 2.0, "eta": 100.0, "gamma": 20.0}
SAMPLE = np.array([25.0, 30.0, 40.0, 60.0, 90.0])


def test_scale_transform_updates_sample_eta_gamma_only():
    sample, row = E3.transform_sample(SAMPLE, ROW, "scale_1000")
    assert np.allclose(sample, SAMPLE * 1000)
    assert row == {"beta": 2.0, "eta": 100000.0, "gamma": 20000.0}


def test_translation_updates_gamma_only():
    sample, row = E3.transform_sample(SAMPLE, ROW, "translate_-0.5")
    assert np.allclose(sample, SAMPLE - 50.0)
    assert row == {"beta": 2.0, "eta": 100.0, "gamma": -30.0}


def test_outlier_variants_preserve_size_and_sorting():
    for variant in ("high_3", "high_10", "low_iqr", "bilateral_10pct"):
        sample, row = E3.transform_sample(SAMPLE, ROW, variant)
        assert len(sample) == len(SAMPLE)
        assert np.all(np.diff(sample) >= 0)
        assert row == ROW


def test_equivariance_residual_is_zero_for_exact_scale():
    clean = {
        "legal": True, "beta_hat": 2.1, "eta_hat": 98.0, "gamma_hat": 19.0, "eta": 100.0,
    }
    changed = {
        "legal": True, "beta_hat": 2.1, "eta_hat": 98000.0, "gamma_hat": 19000.0, "eta": 100000.0,
    }
    assert E3.equivariance_residual(clean, changed, "scale_1000") == 0.0


def test_outlier_effect_detects_increase():
    clean, dirty = [], []
    for point in ("p0", "p1", "p2"):
        for seed in (1, 2):
            clean.append({"point_id": point + "|clean", "seed": seed, "row_loss": 0.25, "legal": True})
            dirty.append({"point_id": point + "|high_3", "seed": seed, "row_loss": 1.0, "legal": True})
    effect = E3.outlier_effect(clean, dirty, n_boot=50, seed=9)
    assert effect["l_param_increase"]["effect"] == 0.5
