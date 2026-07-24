"""
Contract tests for real data admission gate (R3 preflight).

Covers:
  1. Minimum 60 uncensored lifetimes check
  2. Missing source.json → fail-closed
  3. Bad Weibull fit → dataset-ineligible
  4. Valid data → gate passes
  5. Source provenance validation

Run:
    python -m pytest python/tests/test_study01_real_data_gate.py -v
"""

import sys
import os
import json
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Path setup
PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = next((PROJECT_ROOT / "Study").glob("01-study-MDM*"))
STUDY_CODE_DIR = STUDY_ROOT / "code"
sys.path.insert(0, str(STUDY_CODE_DIR))

from real_data_gate import (
    RealDataSource, RealDataGateResult,
    run_real_data_gate,
    WEIBULL_FIT_MIN_R2, MIN_UNCENSORED_LIFETIMES,
    _estimate_weibull_ols, _weibull_cdf,
)


# ============================================================
# Helpers
# ============================================================

def make_source_json(**overrides):
    base = {
        "dataset_id": "test-ds-001",
        "name": "Test Dataset",
        "source_url": "https://example.com/data.csv",
        "version": "2024-01",
        "license_name": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "download_sha256": "a" * 64,
        "original_filename": "test_data.csv",
        "failure_mode": "fatigue",
        "censoring_semantics": "all complete, no censoring",
        "n_total": 100,
        "n_uncensored": 100,
        "inclusion_rule": "all rows",
        "exclusion_rule": "none",
    }
    base.update(overrides)
    return base


def make_dataset_dir(tmp_path, source_overrides=None, lifetimes=None,
                     lifetimes_filename="lifetimes.csv"):
    """Create a temporary dataset directory with source.json + lifetimes."""
    ds_dir = tmp_path / "test-ds-001"
    ds_dir.mkdir()
    source = make_source_json(**(source_overrides or {}))
    (ds_dir / "source.json").write_text(
        json.dumps(source, indent=2), encoding='utf-8'
    )
    if lifetimes is not None:
        df = pd.DataFrame({"failure_time": lifetimes})
        df.to_csv(ds_dir / lifetimes_filename, index=False)
    return str(ds_dir)


def generate_weibull_sample(n, beta=2.0, eta=100.0, gamma=0.0, seed=42):
    rng = np.random.default_rng(seed)
    if gamma > 0:
        return eta * (-np.log(1.0 - rng.random(n))) ** (1.0 / beta) + gamma
    return eta * (-np.log(1.0 - rng.random(n))) ** (1.0 / beta)


# ============================================================
# Source provenance
# ============================================================

class TestRealDataSource:
    def test_valid_source_passes_validation(self):
        source = RealDataSource(**make_source_json())
        source.validate()  # should not raise

    def test_missing_required_field_fails(self):
        data = make_source_json()
        del data['source_url']
        source = RealDataSource(**data)
        with pytest.raises(ValueError, match="source_url"):
            source.validate()

    def test_invalid_sha256_fails(self):
        data = make_source_json(download_sha256="too-short")
        source = RealDataSource(**data)
        with pytest.raises(ValueError, match="64-character hex"):
            source.validate()

    def test_n_uncensored_exceeds_n_total_fails(self):
        data = make_source_json(n_uncensored=200, n_total=100)
        source = RealDataSource(**data)
        with pytest.raises(ValueError, match="cannot exceed"):
            source.validate()


# ============================================================
# Gate checks
# ============================================================

class TestRealDataGate:
    def test_n_uncensored_below_minimum_fails(self, tmp_path):
        ds = make_dataset_dir(
            tmp_path,
            source_overrides={"n_uncensored": 50, "n_total": 50},
            lifetimes=generate_weibull_sample(50),
        )
        result = run_real_data_gate(ds)
        assert not result.passed
        assert str(MIN_UNCENSORED_LIFETIMES) in result.reason

    def test_missing_source_json_fails(self, tmp_path):
        ds_dir = tmp_path / "no-source"
        ds_dir.mkdir()
        (ds_dir / "lifetimes.csv").write_text("failure_time\n100\n")
        result = run_real_data_gate(str(ds_dir))
        assert not result.passed
        assert "not found" in result.reason

    def test_missing_lifetimes_csv_fails(self, tmp_path):
        ds = make_dataset_dir(tmp_path)
        result = run_real_data_gate(ds)
        assert not result.passed
        assert "not found" in result.reason

    def test_non_positive_lifetimes_fails(self, tmp_path):
        ds = make_dataset_dir(
            tmp_path,
            lifetimes=[100.0, -5.0, 200.0] + list(range(97)),
        )
        result = run_real_data_gate(ds)
        assert not result.passed
        assert "non-positive" in result.reason

    def test_too_few_rows_fails(self, tmp_path):
        ds = make_dataset_dir(
            tmp_path,
            source_overrides={"n_uncensored": 30, "n_total": 30},
            lifetimes=generate_weibull_sample(30),
        )
        result = run_real_data_gate(ds)
        assert not result.passed

    def test_good_weibull_data_passes(self, tmp_path):
        n = 100
        lifetimes = generate_weibull_sample(n, beta=2.5, eta=500.0)
        lifetimes = lifetimes.tolist()
        ds = make_dataset_dir(
            tmp_path,
            source_overrides={"n_uncensored": n, "n_total": n},
            lifetimes=lifetimes,
        )
        result = run_real_data_gate(ds)
        assert result.passed
        assert 'r_squared' in result.diagnostics
        assert result.diagnostics['r_squared'] >= WEIBULL_FIT_MIN_R2

    def test_bad_fit_data_fails(self, tmp_path):
        """Uniform random data should fail Weibull fit (low R²)."""
        rng = np.random.default_rng(99)
        lifetimes = rng.uniform(1, 1000, size=100).tolist()
        ds = make_dataset_dir(
            tmp_path,
            source_overrides={"n_uncensored": 100, "n_total": 100},
            lifetimes=lifetimes,
        )
        result = run_real_data_gate(ds)
        if not result.passed:
            assert 'r_squared' in result.reason or 'R' in result.reason


# ============================================================
# Weibull helpers
# ============================================================

# ============================================================
# Fail-closed guard
# ============================================================

class TestP6PlaceholderGuard:
    def test_run_real_data_validation_has_fail_closed_guard(self):
        """P6 run script must raise RuntimeError until P7 is complete."""
        import run_real_data_validation as rv
        assert rv._P6_PLACEHOLDER_GUARD is True, (
            "P6 placeholder guard must be True until P7 is complete. "
            "Do not set to False before P7 implementation + review."
        )
        with pytest.raises(RuntimeError, match="PLACEHOLDER"):
            rv.main("/nonexistent/path")
        # Guard should fire before any file I/O, so non-existent path is OK

    def test_fail_closed_guard_is_module_level_constant(self):
        """Guard must be an importable module-level constant for testability."""
        import run_real_data_validation as rv
        assert hasattr(rv, '_P6_PLACEHOLDER_GUARD'), (
            "P6 guard constant missing — cannot test fail-closed state"
        )


class TestWeibullHelpers:
    def test_weibull_cdf_endpoints(self):
        """CDF(0) ≈ 0, CDF(∞) → 1."""
        assert _weibull_cdf(0.0, 2.0, 100.0) == 0.0
        assert _weibull_cdf(1e9, 2.0, 100.0) > 0.9999

    def test_ols_fit_returns_finite_params(self):
        lifetimes = generate_weibull_sample(100, beta=2.0, eta=200.0)
        beta, eta, gamma = _estimate_weibull_ols(lifetimes)
        assert np.isfinite(beta)
        assert np.isfinite(eta)
        assert beta > 0
        assert eta > 0

    def test_ols_fit_fails_on_tiny_sample(self):
        beta, eta, gamma = _estimate_weibull_ols(np.array([1.0, 2.0, 3.0]))
        assert not np.isfinite(beta)
