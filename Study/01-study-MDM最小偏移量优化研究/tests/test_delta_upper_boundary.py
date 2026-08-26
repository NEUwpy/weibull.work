"""Minimal contract tests for the E12 delta upper-bound diagnostic."""

import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd


SCRIPT = Path(__file__).resolve().parents[1] / "code" / "analyze_E12_delta_upper_boundary.py"
SPEC = importlib.util.spec_from_file_location("e12_boundary", SCRIPT)
E12 = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(E12)


def _row(repeat_id, delta, loss):
    beta, eta, gamma = 2.0, 1000.0, 500.0
    # Put the requested total loss entirely in beta for a transparent fixture.
    return {
        "beta": beta,
        "eta": eta,
        "gamma": gamma,
        "gamma_over_eta": 0.5,
        "n": 7,
        "repeat_id": repeat_id,
        "delta": delta,
        "beta_hat": beta * (1.0 + np.sqrt(loss)),
        "eta_hat": eta,
        "gamma_hat": gamma,
        "status": "success",
    }


def test_extended_grid_is_contiguous_and_stops_at_one():
    assert E12.EXTENDED_DELTAS[0] == 0.52
    assert E12.EXTENDED_DELTAS[-1] == 1.0
    assert len(E12.EXTENDED_DELTAS) == 25
    assert np.allclose(np.diff(E12.EXTENDED_DELTAS), 0.02)


def test_sample_loss_matches_frozen_formula():
    frame = pd.DataFrame([{
        "beta": 2.0, "eta": 1000.0, "gamma": 500.0,
        "beta_hat": 2.2, "eta_hat": 1100.0, "gamma_hat": 600.0,
    }])
    # Three relative errors are all 0.1.
    assert np.isclose(E12.sample_loss(frame).iloc[0], 0.03)


def test_selection_uses_falling_final_segment_not_only_argmin_label():
    rows = []
    # repeat 0 is falling at the edge; repeat 1 is rising.
    for repeat_id, losses in ((0, (0.30, 0.20, 0.10)), (1, (0.10, 0.20, 0.30))):
        for delta, loss in zip((0.10, 0.48, 0.50), losses):
            rows.append(_row(repeat_id, delta, loss))
    scan = pd.DataFrame(rows)
    scan["loss"] = E12.sample_loss(scan)
    all_samples, selected = E12.select_boundary_samples(scan)
    assert len(all_samples) == 2
    assert selected["repeat_id"].tolist() == [0]
    assert np.isclose(selected.iloc[0]["base_l6_delta"], 0.50)


def test_extended_summary_replaces_only_selected_sample():
    rows = []
    for repeat_id, losses in ((0, (0.30, 0.20, 0.10)), (1, (0.10, 0.20, 0.30))):
        for delta, loss in zip((0.10, 0.48, 0.50), losses):
            rows.append(_row(repeat_id, delta, loss))
    scan = pd.DataFrame(rows)
    scan["loss"] = E12.sample_loss(scan)
    all_samples, selected = E12.select_boundary_samples(scan)
    extended = pd.DataFrame([
        {**{key: selected.iloc[0][key] for key in E12.SAMPLE_KEYS},
         "delta": 0.52, "loss": 0.08, "status": "success"},
        {**{key: selected.iloc[0][key] for key in E12.SAMPLE_KEYS},
         "delta": 1.00, "loss": 0.05, "status": "success"},
    ])
    samples, _, summary = E12.derive_sample_summary(all_samples, selected, extended)
    assert np.isclose(samples.iloc[0]["extended_l6_loss"], 0.05)
    assert np.isclose(summary["risk"]["base_l6_R_000_050"], 0.10)
    assert np.isclose(summary["risk"]["extended_l6_R_000_100"], 0.075)
    assert summary["sample_counts"]["best_at_new_upper_boundary_100"] == 1


def test_numerical_tie_is_not_counted_as_boundary_improvement():
    rows = [_row(0, delta, loss) for delta, loss in (
        (0.10, 0.30), (0.48, 0.20), (0.50, 0.10)
    )]
    scan = pd.DataFrame(rows)
    scan["loss"] = E12.sample_loss(scan)
    all_samples, selected = E12.select_boundary_samples(scan)
    extended = pd.DataFrame([
        {**{key: selected.iloc[0][key] for key in E12.SAMPLE_KEYS},
         "delta": 0.52, "loss": 0.10 - 1e-14, "status": "success"},
    ])
    samples, _, summary = E12.derive_sample_summary(all_samples, selected, extended)
    assert samples.iloc[0]["loss_reduction"] == 0.0
    assert summary["sample_counts"]["improved_beyond_050"] == 0
