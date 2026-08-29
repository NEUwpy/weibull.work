from __future__ import annotations

import numpy as np

from . import sample_size_equivalence as SSE


def test_frozen_grid_is_complete() -> None:
    values, seeds = SSE._load_cells()
    assert values.shape == (4, 5, 10, 3)
    assert seeds == SSE.DEFAULT_SEEDS
    assert np.isfinite(values).all()


def test_p_error_decreases_with_n_and_power_is_near_root_n() -> None:
    values, _ = SSE._load_cells()
    rrmse = np.sqrt(np.mean(values, axis=(1, 2)))
    _, exponent, r2 = SSE._fit_power_law(rrmse[:, 0])
    assert np.all(np.diff(rrmse[:, 0]) < 0)
    assert 0.4 < exponent < 0.65
    assert r2 > 0.99


def test_effective_n_exceeds_observed_n_for_q_and_qcp() -> None:
    values, _ = SSE._load_cells()
    rrmse = np.sqrt(np.mean(values, axis=(1, 2)))
    _, exponent, _ = SSE._fit_power_law(rrmse[:, 0])
    effective = SSE._effective_n(rrmse, exponent)
    assert np.all(effective > SSE.N_GRID[:, None])
    assert np.all(effective[:, 1] > effective[:, 0])
