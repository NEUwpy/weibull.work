"""Focused checks for the bounded E11 MDM profile diagnostic."""

from pathlib import Path
import sys

import numpy as np
import pandas as pd


STUDY_ROOT = Path(__file__).resolve().parents[1]
CODE_DIR = STUDY_ROOT / "code"
if str(CODE_DIR) not in sys.path:
    sys.path.insert(0, str(CODE_DIR))

import analyze_E11_profile_mechanism as E11


def test_design_is_predeclared_balanced_and_uses_untouched_confirmation_repeats():
    cells = E11.selected_cells()
    assert len(cells) == 20
    assert set(cells["n"]) == {7, 10, 15, 20}
    assert cells.groupby("n").size().eq(5).all()
    assert set(E11.CONFIRMATION_REPEATS) == set(range(200, 300))
    assert (3.0, 0.50) in E11.PARAMETER_PAIRS
    assert {(1.5, 0.10), (1.5, 1.00), (5.0, 0.10), (5.0, 1.00)}.issubset(
        set(E11.PARAMETER_PAIRS)
    )


def test_cell_scan_uses_complete_frozen_loss_grid():
    cell = E11.selected_cells().iloc[0].to_dict()
    frame, receipt = E11.load_cell_scan(cell)
    assert len(frame) == 100 * 26
    assert frame.groupby("repeat_id")["delta"].nunique().eq(26).all()
    assert frame["status"].eq("success").all()
    assert receipt["seed_namespace"] == "study01_nrmc_v1"


def test_one_real_sample_connects_trace_and_hindsight_scan():
    cell = E11.selected_cells().query("beta == 3.0 and gamma_over_eta == 0.5 and n == 10").iloc[0].to_dict()
    scan, _ = E11.load_cell_scan(cell)
    metric, curve = E11.extract_sample(cell, 200, scan)
    assert np.isfinite(metric["gradient_at_zero"])
    assert metric["l6_delta"] in E11.CFG.DELTA_GRID
    assert metric["l6_loss"] <= metric["default_loss"] + 1e-15
    assert len(curve) >= 20
    assert np.isfinite(curve[["gamma", "gradient"]]).all().all()


def test_association_table_is_cell_level_not_pooled_only():
    rows = []
    for beta, ratio in E11.PARAMETER_PAIRS:
        for n_value in E11.N_VALUES:
            for repeat_id in range(100):
                g0 = float(repeat_id)
                rows.append({
                    "beta": beta,
                    "gamma_over_eta": ratio,
                    "n": n_value,
                    "repeat_id": repeat_id,
                    "gradient_at_zero": g0,
                    "l6_delta": g0,
                    "gamma_hat_default_over_eta": -g0,
                    "gradient_at_true_gamma": g0 / 4,
                    "local_gradient_slope_eta_scaled": g0 / 5,
                    "sample_min_over_mean": -g0,
                    "lower_gap_over_mean": g0 / 2,
                    "sample_cv": g0 / 3,
                    "l6_solution_at_boundary": False,
                    "default_solution_strategy": "brent_root",
                })
    table = E11.derive_associations(pd.DataFrame(rows))
    assert len(table) == 20
    assert np.allclose(table["rho_g0_l6_delta"], 1.0)
    assert np.allclose(table["rho_g0_sample_min_over_mean"], -1.0)


def test_conditional_curve_minima_can_shift_with_gradient_group():
    metrics = pd.DataFrame({
        "beta": [3.0] * 6,
        "gamma_over_eta": [0.5] * 6,
        "n": [10] * 6,
        "repeat_id": list(range(6)),
        "gradient_at_zero": list(range(6)),
        "gamma_hat_default_over_eta": list(range(6)),
        "l6_loss": [0.0] * 6,
    })
    scan_rows = []
    for repeat_id in range(6):
        preferred = 0.0 if repeat_id < 2 else 0.1 if repeat_id < 4 else 0.2
        for delta in (0.0, 0.1, 0.2):
            scan_rows.append({
                "repeat_id": repeat_id,
                "delta": delta,
                "loss": (delta - preferred) ** 2,
            })
    curves = E11.derive_conditional_curves(
        metrics, {(3.0, 0.5, 10): pd.DataFrame(scan_rows)}
    )
    curves = curves[curves["stratifier"] == "gradient_at_zero"]
    minima = curves.loc[curves.groupby("tertile")["R_mean_loss"].idxmin()]
    found = dict(zip(minima["tertile"], minima["delta"]))
    assert found == {"low": 0.0, "middle": 0.1, "high": 0.2}


def test_sha_inventory_excludes_itself_and_covers_compact_outputs():
    assert "SHA256SUMS" not in E11.OUTPUT_FILES
    assert set(E11.OUTPUT_FILES) == {
        "sample_metrics.csv",
        "cell_associations.csv",
        "conditional_loss_curves.csv",
        "representative_gradient_curves.csv",
        "summary.json",
        "mechanism_report.md",
    }
