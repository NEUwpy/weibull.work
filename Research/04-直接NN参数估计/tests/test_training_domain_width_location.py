from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np


CODE = Path(__file__).resolve().parents[1] / "code"


def load(name: str, filename: str):
    spec = importlib.util.spec_from_file_location(name, CODE / filename)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


RUN = load("domain_width_location_run", "run_training_domain_width_location.py")
ANALYZE = load("domain_width_location_analyze", "analyze_training_domain_width_location.py")


def test_frozen_domains_and_shared_middle_window():
    assert RUN.DOMAIN_SPECS["center_w1_2.5_3.5"]["betas"] == (2.5, 3.0, 3.5)
    assert RUN.DOMAIN_SPECS["center_w5_0.5_5.5"]["betas"] == tuple(
        np.arange(0.5, 5.51, 0.5)
    )
    assert RUN.WIDTH_ORDER[0] == RUN.LOCATION_ORDER[1]
    assert len(RUN.DOMAIN_SPECS) == 6


def test_fixed_total_is_exact_and_balanced():
    specs = [row for row in RUN.scenario_specs() if row["budget_policy"] == "fixed_total"]
    assert {row["n_train_per_n"] for row in specs} == {12_000}
    assert all(row["train_repeats_max"] - row["train_repeats_min"] <= 1 for row in specs)
    irregular = next(row for row in specs if row["domain_id"] == "center_w4_1.0_5.0")
    assert (irregular["train_repeats_min"], irregular["train_repeats_max"]) == (266, 267)


def test_fixed_density_is_300_per_cell():
    specs = [row for row in RUN.scenario_specs() if row["budget_policy"] == "fixed_density"]
    assert all(row["train_repeats_min"] == row["train_repeats_max"] == 300 for row in specs)
    expected = {
        domain_id: len(domain["betas"]) * len(RUN.GAMMA_RATIOS) * 300
        for domain_id, domain in RUN.DOMAIN_SPECS.items()
    }
    assert {row["domain_id"]: row["n_train_per_n"] for row in specs} == expected


def test_point_types_and_widest_left_boundary():
    grid = RUN.DOMAIN_SPECS["center_w1_2.5_3.5"]["betas"]
    assert ANALYZE.classify_beta_point(3.0, grid) == "train_grid"
    assert ANALYZE.classify_beta_point(2.75, grid) == "in_domain_unseen"
    assert ANALYZE.classify_beta_point(2.25, grid) == "left_ood"
    assert ANALYZE.classify_beta_point(3.75, grid) == "right_ood"
    widest = RUN.DOMAIN_SPECS["center_w5_0.5_5.5"]["betas"]
    assert all(ANALYZE.classify_beta_point(beta, widest) != "left_ood" for beta in RUN.TEST_BETAS)


def test_normalization_and_scale_restore_contract():
    spec = next(row for row in RUN.scenario_specs(smoke=True)
                if row["budget_policy"] == "fixed_total" and row["domain_id"] == "center_w1_2.5_3.5")
    normalized, params, means = RUN.training_arrays(spec, 7)
    assert np.allclose(normalized.mean(axis=1), 1.0, atol=1e-12)
    encoded = RUN.DIRECT.encode_targets(params, means)
    decoded = RUN.DIRECT.decode_output(encoded, means)
    assert np.allclose(decoded, params, rtol=1e-6, atol=1e-6)
