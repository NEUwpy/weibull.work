import importlib.util
from pathlib import Path

import numpy as np

SCRIPT = Path(__file__).with_name("E4-trust-realdata.py")
SPEC = importlib.util.spec_from_file_location("e4", SCRIPT)
E4 = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(E4)


def test_real_splits_are_deterministic_and_disjoint():
    values = np.arange(101, dtype=float) + 1
    rows, samples, holdouts = E4.real_splits(values, [5, 20], 3, 7)
    rows2, samples2, holdouts2 = E4.real_splits(values, [5, 20], 3, 7)
    assert rows == rows2 and len(rows) == 6
    assert all(np.array_equal(a, b) for a, b in zip(samples, samples2))
    for row, sample in zip(rows, samples):
        holdout = holdouts[row["point_id"]]
        assert len(sample) + len(holdout) == 101
        assert set(sample).isdisjoint(set(holdout))
        assert np.array_equal(holdout, holdouts2[row["point_id"]])


def test_ks_distance_is_small_for_matching_quantiles():
    rng = np.random.default_rng(3)
    sample = (-np.log1p(-rng.uniform(size=10000))) ** (1 / 2.0)
    assert E4.ks_distance(sample, 2.0, 1.0, 0.0) < 0.02


def test_conformal_quantile_uses_finite_sample_higher_rank():
    values = np.arange(1, 11, dtype=float)
    assert E4.conformal_quantile(values, 0.9) == 10.0


def test_weibull_cdf_is_zero_below_gamma():
    result = E4.weibull_cdf(np.array([-1.0, 0.0, 1.0]), 2.0, 1.0, 0.0)
    assert result[0] == result[1] == 0.0
    assert result[2] > 0.0
