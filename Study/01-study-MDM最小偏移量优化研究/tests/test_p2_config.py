"""Fail-closed tests for P2 configuration and contracts."""
import sys, importlib.util
from pathlib import Path
import pytest

# Resolve p2_config module path
CODE_DIR = Path(__file__).resolve().parents[1] / "code"
spec = importlib.util.spec_from_file_location("p2_config", CODE_DIR / "p2_config.py")
cfg = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cfg)


class TestP2ComboCounts:
    def test_p2_ni_exact_15_combos(self):
        combos = cfg.build_p2_combos()
        ni = [c for c in combos if c[0] == "P2-NI"]
        assert len(ni) == 15

    def test_p2_pi_exact_24_combos(self):
        combos = cfg.build_p2_combos()
        pi = [c for c in combos if c[0] == "P2-PI"]
        assert len(pi) == 24

    def test_p2_total_39_combos(self):
        assert len(cfg.build_p2_combos()) == 39

    def test_p2_total_samples_39000(self):
        assert cfg.P2_TOTAL_SAMPLES == 39000

    def test_p2_total_delta_evals_1014000(self):
        assert cfg.P2_TOTAL_DELTA_EVALS == 1014000

    def test_validate_p2_counts_passes(self):
        assert cfg.validate_p2_counts() is True


class TestP2ComboValues:
    def test_p2_ni_betas(self):
        assert set(cfg.P2_NI_BETAS) == {1.5, 2.0, 2.5, 4.0, 5.0}

    def test_p2_ni_ge(self):
        assert set(cfg.P2_NI_GAMMA_OVER_ETA) == {0.1, 0.5, 1.0}

    def test_p2_ni_n(self):
        assert cfg.P2_NI_N == [15]

    def test_p2_pi_betas(self):
        assert set(cfg.P2_PI_BETAS) == {1.75, 2.25, 3.25, 4.50}

    def test_p2_pi_ge(self):
        assert set(cfg.P2_PI_GAMMA_OVER_ETA) == {0.30, 0.75}

    def test_p2_pi_n(self):
        assert set(cfg.P2_PI_N) == {7, 10, 20}

    def test_eta_is_1(self):
        assert cfg.ETA == 1.0

    def test_repeats_1000(self):
        assert cfg.REPEATS == 1000

    def test_delta_grid_26_points(self):
        assert len(cfg.DELTA_GRID) == 26

    def test_seed_namespace(self):
        assert cfg.SEED_NAMESPACE == "study01_p2_v1"


class TestP2VectorMLP:
    def test_folds_and_seeds(self):
        assert cfg.VECTOR_MLP_FOLDS == 5
        assert cfg.VECTOR_MLP_SEEDS == [42, 2026, 3407]

    def test_total_15_models(self):
        assert cfg.VECTOR_MLP_FOLDS * len(cfg.VECTOR_MLP_SEEDS) == 15


class TestP2DefaultL1:
    def test_default_delta(self):
        assert cfg.DEFAULT_DELTA == 0.1

    def test_l1_delta(self):
        assert cfg.L1_DELTA == 0.08
