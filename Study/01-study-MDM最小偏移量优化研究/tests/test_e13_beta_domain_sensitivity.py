"""Focused contract tests for the E13 sliding-beta-domain analysis."""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd


CODE_DIR = Path(__file__).resolve().parents[1] / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import analyze_E13_beta_domain_sensitivity as e13


def _synthetic_balanced_scan() -> pd.DataFrame:
    rows = []
    for beta in e13.FULL_BETA_GRID:
        preferred = 0.04 + 0.02 * ((beta - 1.50) / 0.25)
        for delta in e13.DELTA_GRID:
            rows.append(
                {
                    "beta": beta,
                    "eta": 1000.0,
                    "gamma": 100.0,
                    "gamma_over_eta": 0.10,
                    "n": 10,
                    "repeat_id": 0,
                    "delta": delta,
                    "loss": 0.10 + (delta - preferred) ** 2,
                }
            )
    return pd.DataFrame(rows)


def test_dense_beta_grid_and_sliding_windows_are_fixed_width() -> None:
    assert e13.FULL_BETA_GRID == tuple(np.round(np.arange(1.50, 5.01, 0.25), 2))
    assert len(e13.WINDOW_CENTERS) == 11
    for center in e13.WINDOW_CENTERS:
        levels = [
            beta
            for beta in e13.FULL_BETA_GRID
            if center - 0.50 - 1e-9 <= beta <= center + 0.50 + 1e-9
        ]
        assert len(levels) == 5
        assert np.isclose(levels[-1] - levels[0], 1.0)


def test_e13_uses_the_shared_production_method_entry() -> None:
    source = Path(e13.__file__).read_text(encoding="utf-8")
    assert 'run_method("mdm", sample, offset=delta)' in source
    assert "MDM(sample).run" not in source


def test_derive_curves_uses_all_26_points_and_tracks_domain_shift() -> None:
    curves, summary = e13.derive_curves(_synthetic_balanced_scan())

    assert len(curves) == 11 * 26
    assert len(summary) == 11
    assert (summary["n_beta_levels"] == 5).all()
    assert (summary["n_parameter_conditions"] == 5 * 5 * 4).all()
    assert summary["best_delta"].is_monotonic_increasing
    assert summary["best_delta"].nunique() > 1
    assert (summary["near_optimal_1pct_lower"] <= summary["best_delta"]).all()
    assert (summary["near_optimal_1pct_upper"] >= summary["best_delta"]).all()
