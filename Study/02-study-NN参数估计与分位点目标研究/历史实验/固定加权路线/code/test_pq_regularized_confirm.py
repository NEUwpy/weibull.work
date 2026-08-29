"""Formal QP confirmation helpers."""

from __future__ import annotations

import numpy as np

from . import regularized_confirm as CONFIRM


def test_comparator_source_routing():
    assert CONFIRM.comparator_root(42).name == "pq_iid_main"
    assert CONFIRM.comparator_root(2026).name == "pq_iid_main"
    assert CONFIRM.comparator_root(17).name == "grid_extra"
    assert CONFIRM.comparator_root(12011).name == "grid_extra"


def test_crossed_bootstrap_constant_cube_is_exact():
    cube = np.full((4, 5, 10), -0.125)
    lo, hi = CONFIRM.crossed_bootstrap(cube, replicates=1000, seed=1)
    assert np.isclose(lo, -0.125)
    assert np.isclose(hi, -0.125)


def test_crossed_bootstrap_is_deterministic():
    cube = np.arange(200, dtype=float).reshape(4, 5, 10)
    assert CONFIRM.crossed_bootstrap(cube, replicates=500, seed=7) == \
        CONFIRM.crossed_bootstrap(cube, replicates=500, seed=7)


def test_grid_extra_repeat_key_alias(tmp_path, monkeypatch):
    path = tmp_path / "e.npz"
    np.savez(path, keys_point_or_repeat_id=np.array([1, 2], dtype=np.int32))
    monkeypatch.setattr(CONFIRM, "comparator_paths", lambda *args: (tmp_path / "m", path))
    got = CONFIRM._load_evidence(7, 1, 17, "Q")
    assert np.array_equal(got["keys_repeat_id"], np.array([1, 2], dtype=np.int32))
