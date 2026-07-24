"""
Contract tests for delta upper-bound sensitivity audit (R2).

Covers:
  1. Extension grid correctness (0.52–1.00, step 0.02)
  2. Cohort identification from existing cache
  3. Merge-and-analyze conditioned on original best delta
  4. Cohort summary keys

Run:
    python -m pytest python/tests/test_study01_delta_upper_bound.py -v
"""

import sys
import os
import math
import importlib
import types
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = PROJECT_ROOT / "python"
STUDY_ROOT = next((PROJECT_ROOT / "Study").glob("01-study-MDM*"))
STUDY_CODE_DIR = STUDY_ROOT / "code"
_COLLECTION_SYS_PATH = list(sys.path)
_RELATED_MODULE_PREFIXES = (
    "run_delta_upper_bound_audit", "config", "utils",
    "studies", "methods",
)
# Note: methods/studies are cleaned up after _AUDIT_MODULE import but
# integration tests re-import them on first use.
_COLLECTION_RELATED_MODULES = {
    name: module for name, module in sys.modules.items()
    if name in _RELATED_MODULE_PREFIXES
    or name.startswith(tuple(prefix + "." for prefix in _RELATED_MODULE_PREFIXES))
}
try:
    sys.path.insert(0, str(STUDY_CODE_DIR))
    sys.path.insert(0, str(PYTHON_DIR))          # for methods.mdm etc.
    _AUDIT_MODULE = importlib.import_module("run_delta_upper_bound_audit")
finally:
    sys.path[:] = _COLLECTION_SYS_PATH
    for name in list(sys.modules):
        if (
            name in _RELATED_MODULE_PREFIXES
            or name.startswith(tuple(
                prefix + "." for prefix in _RELATED_MODULE_PREFIXES
            ))
        ):
            sys.modules.pop(name, None)
    sys.modules.update(_COLLECTION_RELATED_MODULES)


# ============================================================
# Extension grid
# ============================================================

class TestExtensionGrid:
    def test_grid_starts_at_0_52(self):
        assert _AUDIT_MODULE.EXTENSION_GRID[0] == 0.52

    def test_grid_ends_at_1_00(self):
        assert _AUDIT_MODULE.EXTENSION_GRID[-1] == 1.00

    def test_grid_step_is_0_02(self):
        grid = _AUDIT_MODULE.EXTENSION_GRID
        for i in range(len(grid) - 1):
            assert abs(round(grid[i + 1] - grid[i], 2) - 0.02) < 0.001, (
                f"step at {i}: {grid[i]} -> {grid[i+1]}"
            )

    def test_grid_has_25_points(self):
        assert len(_AUDIT_MODULE.EXTENSION_GRID) == 25

    def test_no_overlap_with_original_grid(self):
        orig_max = max(_AUDIT_MODULE.DELTA_GRID)  # 0.50
        ext_min = min(_AUDIT_MODULE.EXTENSION_GRID)  # 0.52
        assert ext_min > orig_max, (
            "extension grid must not overlap original DELTA_GRID"
        )


# ============================================================
# Cohort identification
# ============================================================

class TestCohortIdentification:
    def test_identify_cohort_from_perfect_predictions(self):
        audit = _AUDIT_MODULE
        # Use the full DELTA_GRID so 0.50 and 0.48 are available
        best_deltas = [0.50, 0.48, 0.10]  # 2 in cohort, 1 not
        rows = []
        for sample_idx, best_delta in enumerate(best_deltas):
            for delta in audit.DELTA_GRID:
                is_best = abs(delta - best_delta) < 0.001
                rows.append({
                    "beta": 1.5, "eta": 1.0, "gamma": 0.5,
                    "gamma_over_eta": 0.5, "n": 10,
                    "repeat_id": sample_idx,
                    "delta": delta,
                    "beta_hat": 1.5 if is_best else 2.0,
                    "eta_hat": 1.0, "gamma_hat": 0.5,
                })
        df = pd.DataFrame(rows)
        df = audit.compute_loss(df)
        cohorts, best = audit.identify_cohort_samples(df)

        assert 0.50 in cohorts
        assert 0.48 in cohorts
        assert len(cohorts[0.50]) == 1, f"cohort 0.50 has {len(cohorts[0.50])}"
        assert len(cohorts[0.48]) == 1

        for col in ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']:
            assert col in best.columns, f"missing column {col}"


# ============================================================
# Merge and analyze
# ============================================================

class TestMergeAndAnalyze:
    def test_conditioned_on_original_cohort_delta(self):
        """All rows must have cohort_delta == the original best delta."""
        audit = _AUDIT_MODULE

        cohort_delta = 0.50  # actual best delta in original grid
        better_delta = audit.EXTENSION_GRID[0]  # 0.52 — now even better

        # Original data: one sample, best at delta=0.50
        orig_rows = []
        for delta in audit.DELTA_GRID:
            # At delta=0.50: beta_hat is close (small loss)
            # At other deltas: beta_hat is far (large loss)
            if abs(delta - cohort_delta) < 0.001:
                beta_hat = 2.1  # small deviation → small loss
            else:
                beta_hat = 4.0  # large deviation → large loss
            orig_rows.append({
                "beta": 2.0, "eta": 1.0, "gamma": 0.8,
                "gamma_over_eta": 0.8, "n": 10, "repeat_id": 0,
                "delta": delta,
                "beta_hat": beta_hat, "eta_hat": 1.0, "gamma_hat": 0.8,
                "r_squared": 0.99, "converged": True,
                "time_ms": 1.0, "status": "success",
            })
        # Extended data: ALL 25 extension deltas required (fail-closed contract).
        # delta=0.52 has even smaller deviation → lower loss (migration).
        ext_rows = []
        for delta in audit.EXTENSION_GRID:
            if abs(delta - better_delta) < 0.001:
                beta_hat = 2.01  # even smaller → even lower loss — migration
            else:
                beta_hat = 4.0   # large deviation → large loss — no better
            ext_rows.append({
                "beta": 2.0, "eta": 1.0, "gamma": 0.8,
                "gamma_over_eta": 0.8, "n": 10, "repeat_id": 0,
                "delta": delta,
                "beta_hat": beta_hat, "eta_hat": 1.0, "gamma_hat": 0.8,
                "r_squared": 0.99, "converged": True,
                "time_ms": 1.0, "status": "success",
                "cohort": cohort_delta,
            })

        df_orig = audit.compute_loss(pd.DataFrame(orig_rows))
        df_ext = pd.DataFrame(ext_rows)

        best = pd.DataFrame([{
            "beta": 2.0, "eta": 1.0, "gamma": 0.8,
            "gamma_over_eta": 0.8, "n": 10,
            "repeat_id": 0, "best_delta": cohort_delta,
        }])

        result = audit.merge_and_analyze(df_orig, df_ext, cohort_delta, best)
        assert len(result) == 1
        assert result.iloc[0]['cohort_delta'] == cohort_delta
        assert result.iloc[0]['extended_best_delta'] == better_delta
        assert result.iloc[0]['migrated'] == True  # noqa: E712
        assert result.iloc[0]['loss_improvement'] > 0


# ============================================================
# Cohort summary
# ============================================================

class TestCohortSummary:
    def test_summary_keys(self):
        audit = _AUDIT_MODULE
        df = pd.DataFrame([{
            "cohort_delta": 0.50, "orig_best_delta": 0.50,
            "orig_best_loss": 0.1, "extended_best_delta": 0.70,
            "extended_best_loss": 0.05, "migrated": True,
            "loss_improvement": 0.05, "rel_improvement": 0.5,
        }])
        s = audit.summarize_cohort(df, 0.50)
        assert s['n_samples'] == 1
        assert s['n_migrated'] == 1
        assert s['migration_rate'] == 1.0
        assert 'extended_best_delta_distribution' in s
        assert '0.7' in s['extended_best_delta_distribution']


# ============================================================
# Migration conditioned on original
# ============================================================

class TestConditionalClaims:
    def test_migration_is_conditioned_on_original_delta(self):
        """A sample that migrated from 0.50 to 0.70 must have
        cohort_delta=0.50, not a newly minted claim."""
        audit = _AUDIT_MODULE
        df = pd.DataFrame([{
            "cohort_delta": 0.50, "orig_best_delta": 0.50,
            "orig_best_loss": 0.1, "extended_best_delta": 0.70,
            "extended_best_loss": 0.05, "migrated": True,
            "loss_improvement": 0.05, "rel_improvement": 0.5,
        }])
        s = audit.summarize_cohort(df, 0.50)
        assert s['cohort_delta'] == 0.50
        assert s['migration_rate'] == 1.0
        # A general-population rate cannot be computed from this single-cohort
        # result — there is no 'total_population_migration_rate' key

    def test_no_migration_samples_are_unchanged(self):
        """A sample that stays at 0.50 must report migrated=False."""
        audit = _AUDIT_MODULE
        df = pd.DataFrame([{
            "cohort_delta": 0.50, "orig_best_delta": 0.50,
            "orig_best_loss": 0.1, "extended_best_delta": 0.50,
            "extended_best_loss": 0.1, "migrated": False,
            "loss_improvement": 0.0, "rel_improvement": 0.0,
        }, {
            "cohort_delta": 0.50, "orig_best_delta": 0.50,
            "orig_best_loss": 0.2, "extended_best_delta": 0.50,
            "extended_best_loss": 0.2, "migrated": False,
            "loss_improvement": 0.0, "rel_improvement": 0.0,
        }])
        s = audit.summarize_cohort(df, 0.50)
        assert s['n_migrated'] == 0
        assert s['migration_rate'] == 0.0


# ============================================================
# Production MDM integration — prevent tuple-vs-dict bugs
# ============================================================

class TestProductionMDMInterface:
    """Verify that the audit script correctly calls the REAL production MDM.

    All prior tests use synthetic DataFrames and never invoke MDM.run().
    This class guards against the bug where MDM.run() returns a 5-tuple
    but the audit script calls .get() on it as if it were a dict.

    Module-levele cleanup may have removed methods/studies from sys.modules
    after the audit module import, so each test re-establishes the import
    path when needed.
    """

    @staticmethod
    def _ensure_imports():
        """Re-establish methods/studies in sys.path if the module-level
        cleanup removed them."""
        if str(PYTHON_DIR) not in sys.path:
            sys.path.insert(0, str(PYTHON_DIR))

    def test_real_mdm_run_returns_tuple_not_dict(self):
        """MDM.run() returns (beta, eta, gamma, r_squared, status) — a 5-tuple."""
        self._ensure_imports()
        from methods.mdm import MDM
        from studies.common.sample import generate_sample

        sample = generate_sample(beta=2.0, eta=1.0, gamma=0.5, n=10,
                                 repeat_id=0, seed=42)
        mdm = MDM(sample)
        result = mdm.run(offset=0.52)

        assert isinstance(result, tuple), (
            f"MDM.run() must be a tuple, got {type(result).__name__}"
        )
        assert len(result) == 5, (
            f"MDM.run() must return 5 elements, got {len(result)}"
        )
        beta, eta, gamma, r_squared, status = result
        assert isinstance(beta, (int, float)), f"beta must be numeric, got {type(beta)}"
        assert isinstance(eta, (int, float)), f"eta must be numeric, got {type(eta)}"
        assert isinstance(gamma, (int, float)), f"gamma must be numeric, got {type(gamma)}"
        assert isinstance(r_squared, (int, float)), f"r_squared must be numeric, got {type(r_squared)}"
        assert status is True, f"status must be True, got {status}"

    def test_audit_run_mdm_for_sample_produces_valid_rows(self):
        """The audit script's run_mdm_for_sample must work with real MDM."""
        self._ensure_imports()
        from methods.mdm import MDM  # noqa: F401 — verify availability
        from studies.common.sample import generate_sample

        audit = _AUDIT_MODULE

        sample = generate_sample(beta=2.0, eta=1.0, gamma=0.5, n=10,
                                 repeat_id=0, seed=42)
        result = audit.run_mdm_for_sample(sample, delta=0.70)

        assert isinstance(result, dict)
        assert result['status'] == 'success', (
            f"Expected status='success', got {result['status']!r}"
        )
        assert result['converged'] is True
        # Parameters must be finite (not NaN, not inf)
        for key in ['beta_hat', 'eta_hat', 'gamma_hat', 'r_squared']:
            val = result[key]
            assert not np.isnan(val), f"{key} is NaN"
            assert not np.isinf(val), f"{key} is inf"
        # Gamma must be >= 0 (Weibull constraint)
        assert result['gamma_hat'] >= 0, f"gamma must be >= 0, got {result['gamma_hat']}"
        # r_squared must be in [0, 1]
        assert 0 <= result['r_squared'] <= 1, (
            f"r_squared must be [0, 1], got {result['r_squared']}"
        )
        # time_ms must be positive
        assert result['time_ms'] > 0, f"time_ms must be > 0, got {result['time_ms']}"

    def test_extension_grid_sample_runs_all_25_deltas(self):
        """A real sample must complete all 25 extension deltas successfully."""
        self._ensure_imports()
        from studies.common.sample import generate_sample

        audit = _AUDIT_MODULE

        sample = generate_sample(beta=2.0, eta=1.0, gamma=0.5, n=10,
                                 repeat_id=0, seed=42)
        results = []
        for delta in audit.EXTENSION_GRID:
            result = audit.run_mdm_for_sample(sample, delta)
            results.append(result)

        n_success = sum(1 for r in results if r['status'] == 'success')
        assert n_success == 25, (
            f"All 25 extension deltas must succeed, got {n_success}/25 success"
        )
        # No NaN parameters in successful runs
        for i, r in enumerate(results):
            if r['status'] == 'success':
                for key in ['beta_hat', 'eta_hat', 'gamma_hat', 'r_squared']:
                    assert not np.isnan(r[key]), (
                        f"delta={audit.EXTENSION_GRID[i]:.2f} {key} is NaN"
                    )
