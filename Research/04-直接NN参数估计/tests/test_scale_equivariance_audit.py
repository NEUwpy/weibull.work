from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "code"
    / "run_scale_equivariance_audit.py"
)
SPEC = importlib.util.spec_from_file_location("scale_audit", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)


def test_scale_grid_spans_small_and_large_engineering_units():
    assert MOD.SCALE_FACTORS == (0.001, 0.01, 0.1, 1.0, 10.0, 1000.0)
    assert [MOD.WIDTH.ETA * value for value in MOD.SCALE_FACTORS] == [
        1.0, 10.0, 100.0, 1000.0, 10000.0, 1000000.0,
    ]


def test_quantile_is_scale_equivariant():
    beta = np.array([1.5, 3.0, 5.0])
    eta = np.array([1000.0, 1000.0, 1000.0])
    gamma = np.array([100.0, 500.0, 1000.0])
    base = MOD.quantile(beta, eta, gamma)
    for factor in MOD.SCALE_FACTORS:
        scaled = MOD.quantile(beta, eta * factor, gamma * factor)
        assert np.allclose(scaled, base * factor)
