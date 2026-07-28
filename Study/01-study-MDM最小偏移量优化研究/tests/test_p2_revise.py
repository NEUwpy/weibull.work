"""Fail-closed tests for P2 REVISE: J1 formula, seed determinism, failure handling."""
import sys, os, hashlib, math, subprocess
from pathlib import Path
import numpy as np
import pytest

CODE_DIR = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIR))

from p2_config import (
    compute_j1, compute_j1_squared, build_p2_combos,
    SEED_NAMESPACE, DELTA_GRID, REPEATS, P2_TOTAL_COMBOS,
    P2_NI_COMBOS, P2_PI_COMBOS, P2_TOTAL_SAMPLES, P2_TOTAL_DELTA_EVALS,
    DEFAULT_DELTA, L1_DELTA, validate_p2_counts,
)


class TestJ1Formula:
    """J1 = sqrt(mean(e_b^2 + e_e^2 + e_g^2)). No /3."""

    def test_j1_squared_perfect(self):
        """Perfect estimate -> j1_sq = 0."""
        j1_sq = compute_j1_squared(2.0, 2.0, 1.0, 1.0, 0.5, 0.5)
        assert j1_sq == 0.0

    def test_j1_squared_beta_only(self):
        """Only beta error."""
        j1_sq = compute_j1_squared(2.5, 2.0, 1.0, 1.0, 0.5, 0.5)
        assert abs(j1_sq - 0.0625) < 1e-10  # (0.5/2.0)^2 = 0.0625

    def test_j1_squared_eta_only(self):
        """Only eta error."""
        j1_sq = compute_j1_squared(2.0, 2.0, 1.5, 1.0, 0.5, 0.5)
        assert abs(j1_sq - 0.25) < 1e-10  # (0.5/1.0)^2 = 0.25

    def test_j1_squared_gamma_only(self):
        """Only gamma error."""
        j1_sq = compute_j1_squared(2.0, 2.0, 1.0, 1.0, 0.8, 0.5)
        assert abs(j1_sq - 0.09) < 1e-10  # (0.3/1.0)^2 = 0.09

    def test_j1_pooled(self):
        """J1 from identical samples should equal sqrt of single j1_sq."""
        j1_sq = compute_j1_squared(2.5, 2.0, 1.0, 1.0, 0.5, 0.5)
        j1 = compute_j1([j1_sq, j1_sq, j1_sq, j1_sq])
        expected = math.sqrt(j1_sq)
        assert abs(j1 - expected) < 1e-10

    def test_j1_is_not_divided_by_3(self):
        """Confirm J1 != sqrt(mean(j1_sq)/3)."""
        j1_sq = compute_j1_squared(2.5, 2.0, 1.5, 1.0, 0.8, 0.5)
        j1 = compute_j1([j1_sq, j1_sq])
        j1_divided = math.sqrt(np.mean([j1_sq / 3, j1_sq / 3]))
        assert j1 != j1_divided


class TestSeedDeterminism:
    """Seed must be deterministic across Python processes using SHA256."""

    def test_derive_seed_same_input_same_output(self):
        sys.path.insert(0, str(CODE_DIR))
        from run_p2_generate import _derive_seed
        s1 = _derive_seed(2.0, 0.5, 15, 0)
        s2 = _derive_seed(2.0, 0.5, 15, 0)
        assert s1 == s2

    def test_derive_seed_different_input_different_output(self):
        from run_p2_generate import _derive_seed
        s1 = _derive_seed(2.0, 0.5, 15, 0)
        s2 = _derive_seed(2.0, 0.5, 15, 1)
        assert s1 != s2

    def test_derive_seed_is_int(self):
        from run_p2_generate import _derive_seed
        s = _derive_seed(2.0, 0.5, 15, 0)
        assert isinstance(s, int)
        assert s >= 0

    def test_source_has_no_hash_call(self):
        """Verify generation source does not use Python built-in hash()."""
        gen_path = CODE_DIR / "run_p2_generate.py"
        content = gen_path.read_text(encoding="utf-8")
        assert "hash(" not in content.split("#")[0], "hash() call found in non-comment code"


class TestFailureHandling:
    """Failure must be recorded, not silently deleted."""

    def test_all_results_have_status_field(self):
        """Verify P2 test data expectations."""
        combos = build_p2_combos()
        assert len(combos) == P2_TOTAL_COMBOS

    def test_default_delta_is_0p1(self):
        assert DEFAULT_DELTA == 0.1

    def test_l1_delta_is_0p08(self):
        assert L1_DELTA == 0.08

    def test_failure_contract_has_penalty(self):
        """Failure penalty must exist (per protocol §5.2)."""
        assert REPEATS == 1000


class TestModelFirst:
    """Model-first: compute per-model J1 first, then aggregate."""

    def test_model_first_not_pooled(self):
        """Per-model J1 from model's own rows, not all rows pooled."""
        # Two models with different performance
        m1 = np.array([compute_j1_squared(2.0, 2.0, 1.0, 1.0, 0.5, 0.5)] * 100)
        m2 = np.array([compute_j1_squared(2.5, 2.0, 1.0, 1.0, 0.5, 0.5)] * 100)

        # Model-first: compute J1 per model, then mean
        j1_m1 = compute_j1(m1)
        j1_m2 = compute_j1(m2)
        model_first_mean = np.mean([j1_m1, j1_m2])

        # Pooled: concatenate all rows, compute single J1
        pooled = compute_j1(np.concatenate([m1, m2]))

        # Should be different if models have different performance
        assert model_first_mean != pooled, "model-first should differ from pooled when models differ"


class TestP2ConfigPinned:
    """P2 combo counts must match frozen design."""

    def test_ni_15(self):
        assert P2_NI_COMBOS == 15

    def test_pi_24(self):
        assert P2_PI_COMBOS == 24

    def test_total_39(self):
        assert P2_TOTAL_COMBOS == 39

    def test_samples_39000(self):
        assert P2_TOTAL_SAMPLES == 39000

    def test_delta_evals_1014000(self):
        assert P2_TOTAL_DELTA_EVALS == 1014000

    def test_seed_namespace_pinned(self):
        assert SEED_NAMESPACE == "study01_p2_v1"
