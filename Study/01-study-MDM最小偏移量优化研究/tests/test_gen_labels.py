"""Fail-closed unit tests for generalization label classifier.

Covers: all 9 orthogonal state combinations, all unique E4 combos,
edge cases (NaN, inf, zero, negative), fail-closed validation.
"""

import sys, math
from pathlib import Path

import pytest

STUDY_CODE = Path(__file__).resolve().parents[1] / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from gen_labels import (
    TRAIN_BETAS,
    TRAIN_GAMMAS,
    TRAIN_NS,
    classify_generalization,
    classify_generalization_compound,
    is_pure_parameter_interp,
    is_pure_n_interp,
    is_pure_param_extrap,
    is_pure_n_extrap,
)


class TestOrthogonalStates:
    """All 9 orthogonal state combinations."""

    def test_on_grid_on_grid(self):
        ps, ns = classify_generalization(2.0, 0.5, 10)
        assert ps == "on_grid"
        assert ns == "on_grid"

    def test_on_grid_n_interp(self):
        ps, ns = classify_generalization(2.0, 0.5, 15)
        assert ps == "on_grid"
        assert ns == "interp"

    def test_on_grid_n_extrap(self):
        ps, ns = classify_generalization(2.0, 0.5, 5)
        assert ps == "on_grid"
        assert ns == "extrap"

    def test_interp_on_grid(self):
        ps, ns = classify_generalization(1.8, 0.3, 10)
        assert ps == "interp"
        assert ns == "on_grid"

    def test_interp_n_interp(self):
        ps, ns = classify_generalization(1.8, 0.3, 15)
        assert ps == "interp"
        assert ns == "interp"

    def test_interp_n_extrap(self):
        ps, ns = classify_generalization(1.8, 0.3, 5)
        assert ps == "interp"
        assert ns == "extrap"

    def test_extrap_on_grid(self):
        ps, ns = classify_generalization(1.2, 0.5, 10)
        assert ps == "extrap"
        assert ns == "on_grid"

    def test_extrap_n_interp(self):
        ps, ns = classify_generalization(1.2, 0.5, 15)
        assert ps == "extrap"
        assert ns == "interp"

    def test_extrap_n_extrap(self):
        ps, ns = classify_generalization(1.2, 0.5, 5)
        assert ps == "extrap"
        assert ns == "extrap"


class TestAllE4Combos:
    """Cover all unique (beta, gamma_over_eta, n) combos from E4 data."""

    @staticmethod
    def _load_e4_combos():
        import pandas as pd
        e4_path = Path(__file__).resolve().parents[1] / "artifacts" / "formal" / "E4_robustness" / "E4d_selector_extrapolation.csv"
        df = pd.read_csv(e4_path, dtype=str)
        combos = df.groupby(["beta", "gamma_over_eta", "n"]).size().reset_index()
        return [(float(row.beta), float(row.gamma_over_eta), int(row.n)) for _, row in combos.iterrows()]

    def test_every_e4_combo_classifiable(self):
        for beta, ge, n in self._load_e4_combos():
            ps, ns = classify_generalization(beta, ge, int(n))
            assert ps in ("on_grid", "interp", "extrap"), f"unexpected ps={ps} for ({beta},{ge},{n})"
            assert ns in ("on_grid", "interp", "extrap"), f"unexpected ns={ns} for ({beta},{ge},{n})"

    def test_e4_combos_no_pure_n_interp(self):
        n_interp_found = False
        for beta, ge, n in self._load_e4_combos():
            if is_pure_n_interp(beta, ge, int(n)):
                n_interp_found = True
                break
        assert not n_interp_found, "E4 data should have ZERO pure n-interp combos"

    def test_e4_combos_have_pure_param_interp(self):
        found = False
        for beta, ge, n in self._load_e4_combos():
            if is_pure_parameter_interp(beta, ge, int(n)):
                found = True
                break
        assert found, "E4 data should have pure p-interp combos"


class TestFailClosed:
    """Fail-closed on invalid inputs."""

    def test_nan_rejected(self):
        with pytest.raises(ValueError, match="NaN"):
            classify_generalization(float("nan"), 0.5, 10)
        with pytest.raises(ValueError, match="NaN"):
            classify_generalization(2.0, float("nan"), 10)

    def test_inf_rejected(self):
        with pytest.raises(ValueError, match="non-finite"):
            classify_generalization(float("inf"), 0.5, 10)

    def test_negative_beta_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            classify_generalization(-1.0, 0.5, 10)

    def test_zero_beta_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            classify_generalization(0.0, 0.5, 10)

    def test_negative_ge_rejected(self):
        with pytest.raises(ValueError, match=">= 0"):
            classify_generalization(2.0, -0.1, 10)

    def test_zero_n_rejected(self):
        with pytest.raises(ValueError, match="positive"):
            classify_generalization(2.0, 0.5, 0)


class TestCompoundLabels:
    """Compound label format."""

    def test_compound_format(self):
        label = classify_generalization_compound(1.8, 0.3, 15)
        assert label == "p_interp_n_interp"

    def test_compound_on_grid(self):
        label = classify_generalization_compound(2.0, 0.5, 10)
        assert label == "p_on_grid_n_on_grid"


class TestDomainBoundaries:
    """Boundary edge cases."""

    def test_low_beta_boundary(self):
        ps, ns = classify_generalization(1.5, 0.5, 10)
        assert ps == "on_grid"  # 1.5 is on grid

    def test_high_beta_boundary(self):
        ps, ns = classify_generalization(5.0, 0.5, 10)
        assert ps == "on_grid"

    def test_low_ge_boundary(self):
        ps, ns = classify_generalization(2.0, 0.1, 10)
        assert ps == "on_grid"

    def test_high_ge_boundary(self):
        ps, ns = classify_generalization(2.0, 1.0, 10)
        assert ps == "on_grid"

    def test_beta_interp_low(self):
        ps, ns = classify_generalization(1.6, 0.5, 10)
        assert ps == "interp"

    def test_beta_extrap_low(self):
        ps, ns = classify_generalization(1.4, 0.5, 10)
        assert ps == "extrap"

    def test_n_interp(self):
        ps, ns = classify_generalization(2.0, 0.5, 15)
        assert ns == "interp"

    def test_n_boundary_low(self):
        ps, ns = classify_generalization(2.0, 0.5, 7)
        assert ns == "on_grid"

    def test_n_boundary_extrap_low(self):
        ps, ns = classify_generalization(2.0, 0.5, 6)
        assert ns == "extrap"


class TestNegativeScenarios:
    """Negative tests: invalid inputs, train grid verification."""

    def test_all_train_grid_points_on_grid(self):
        """All 45 training grid points -> (on_grid, on_grid)."""
        for beta in TRAIN_BETAS:
            for ge in TRAIN_GAMMAS:
                for n in TRAIN_NS:
                    ps, ns = classify_generalization(beta, ge, n)
                    assert ps == "on_grid", f"beta={beta} ge={ge} n={n} ps={ps}"
                    assert ns == "on_grid", f"beta={beta} ge={ge} n={n} ns={ns}"

    def test_negative_beta_zero_n_rejected(self):
        """beta<=0, n<=0 -> fail-closed."""
        for args, match in [
            ((0.0, 0.5, 10), "positive"),
            ((-1.0, 0.5, 10), "positive"),
            ((1.5, 0.5, 0), "positive"),
        ]:
            with pytest.raises(ValueError, match=match):
                classify_generalization(*args)
