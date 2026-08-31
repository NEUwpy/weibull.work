from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "code"
    / "run_training_domain_width.py"
)
SPEC = importlib.util.spec_from_file_location("domain_width", MODULE_PATH)
MOD = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MOD)

ANALYSIS_PATH = (
    Path(__file__).resolve().parents[1]
    / "code"
    / "analyze_training_domain_width.py"
)
ANALYSIS_SPEC = importlib.util.spec_from_file_location(
    "domain_width_analysis", ANALYSIS_PATH
)
ANALYSIS = importlib.util.module_from_spec(ANALYSIS_SPEC)
assert ANALYSIS_SPEC.loader is not None
ANALYSIS_SPEC.loader.exec_module(ANALYSIS)


def test_nested_training_domains_are_frozen():
    assert MOD.DOMAIN_SPECS["narrow_2.0_3.0"]["betas"] == (2.0, 2.5, 3.0)
    assert MOD.DOMAIN_SPECS["medium_1.5_3.5"]["betas"] == (
        1.5, 2.0, 2.5, 3.0, 3.5,
    )
    assert MOD.DOMAIN_SPECS["wide_1.5_5.0"]["betas"] == (
        1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0,
    )


def test_fixed_total_keeps_equal_training_rows():
    specs = [
        row for row in MOD.scenario_specs()
        if row["budget_policy"] == "fixed_total"
    ]
    assert {row["n_train_per_n"] for row in specs} == {12_000}
    assert [row["train_repeats_per_cell"] for row in specs] == [800, 480, 300]


def test_fixed_density_keeps_equal_repeats_per_cell():
    specs = [
        row for row in MOD.scenario_specs()
        if row["budget_policy"] == "fixed_density"
    ]
    assert {row["train_repeats_per_cell"] for row in specs} == {300}
    assert [row["n_train_per_n"] for row in specs] == [4_500, 7_500, 12_000]


def test_signed_distance_preserves_extrapolation_direction():
    assert MOD.signed_distance(1.5, 2.0, 3.0) == -0.5
    assert MOD.signed_distance(2.5, 2.0, 3.0) == 0.0
    assert MOD.signed_distance(5.0, 2.0, 3.0) == 2.0


def test_paired_bootstrap_uses_the_same_resamples():
    reference = np.ones((3, 5), dtype=float)
    candidate = np.full((3, 5), 4.0, dtype=float)
    draws = ANALYSIS.paired_bootstrap_delta(
        candidate, reference, np.random.default_rng(42), reps=20
    )
    assert np.allclose(draws, 1.0)


def test_beta_point_classification_separates_grid_interpolation_and_ood_sides():
    grid = (2.0, 2.5, 3.0)
    assert ANALYSIS.classify_beta_point(2.0, grid) == "seen_grid"
    assert ANALYSIS.classify_beta_point(2.25, grid) == "in_domain_unseen"
    assert ANALYSIS.classify_beta_point(1.75, grid) == "near_ood_low"
    assert ANALYSIS.classify_beta_point(3.25, grid) == "near_ood_high"
    assert ANALYSIS.classify_beta_point(1.25, grid) == "far_ood_low"
    assert ANALYSIS.classify_beta_point(3.75, grid) == "far_ood_high"
