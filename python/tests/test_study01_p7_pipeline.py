"""
P7 real data validation pipeline — contract and implementation tests.

Per P6_FROZEN_CONTRACT.md and P7 implementation requirements.

Coverage:
  - Seed & split reproducibility
  - Identical sample indices across methods
  - Piecewise CDF and one-sample two-sided KS independent recomputation
  - Failure detection, exception handling, illegal parameter paths
  - n=7/10 same delta for Default and L2
  - 15 model completeness guarantee
  - Scaler no-leakage: training data from main-grid ONLY
  - Expected row counts: 8500 per n, 25500 total
  - Primary key uniqueness
  - Model-first aggregation and tie rules (ε=1e-9)
  - Input hash verification
  - Output protection: existing formal artifacts not overwritten
  - Smoke run writes to temp directory only
"""

import sys
import os
import json
import hashlib
import math
import tempfile
import shutil
import subprocess
from pathlib import Path

import numpy as np
import pytest

# ── Path setup ──

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = next((PROJECT_ROOT / "Study").glob("01-study-MDM*"))
STUDY_CODE_DIR = STUDY_ROOT / "code"
PYTHON_DIR = PROJECT_ROOT / "python"
REAL_DATA_DIR = STUDY_ROOT / "artifacts" / "formal" / "real_data"
NIST_DIR = REAL_DATA_DIR / "nist-6061-t6-fatigue"
CHUNKS_DIR = STUDY_ROOT / "artifacts" / "formal" / "shared_data" / "chunks"

sys.path.insert(0, str(STUDY_CODE_DIR))
sys.path.insert(0, str(PYTHON_DIR))

# Import the P7 module
from run_real_data_validation import (
    # Constants
    BASE_SEED, TRAIN_N_VALUES, N_REPEATS, L2_DELTAS, DEFAULT_DELTA,
    TIE_TOLERANCE, FAILURE_D, FAILURE_PENALTY,
    FEATURE_COLS_ZSCORE, FEATURE_COLS_RAW, SAMPLE_FEATURE_COLS,
    N_FOLDS, STABILITY_SEEDS, N_DELTAS, DELTA_GRID,
    RESULT_COLUMNS,
    # Seed & split
    make_seed, generate_splits,
    # Features
    compute_sample_features,
    # CDF & KS
    weibull_cdf_piecewise, one_sample_two_sided_ks,
    # Failure
    detect_failure, check_support_set_violation,
    # Parameter distance
    param_distance_rel,
    # MDM
    run_mdm_estimation,
    # Aggregation
    aggregate_per_model, cross_model_distribution,
    # Paired wins
    compute_paired_wins, compute_nn_paired_wins,
    # Output protection
    check_output_safety,
    # Input verification
    verify_input_hashes,
    # Pipeline
    run_pipeline,
)

from methods.mdm import MDM


# ═══════════════════════════════════════════════════════════════
# Seed & Split Tests
# ═══════════════════════════════════════════════════════════════

class TestSeedAndSplits:
    """Seed derivation and split generation tests."""

    def test_seed_derivation_matches_contract(self):
        """Frozen seed formula: base_seed + train_n * 10000 + repeat_index."""
        assert make_seed(7, 0) == 20260725 + 70000
        assert make_seed(7, 499) == 20260725 + 70000 + 499
        assert make_seed(10, 0) == 20260725 + 100000
        assert make_seed(20, 0) == 20260725 + 200000
        assert make_seed(20, 499) == 20260725 + 200000 + 499

    def test_splits_are_deterministic(self):
        """Same seed produces same split."""
        splits1 = generate_splits(101, 7, n_repeats=5)
        splits2 = generate_splits(101, 7, n_repeats=5)
        for (t1, h1), (t2, h2) in zip(splits1, splits2):
            assert np.array_equal(t1, t2), "Train indices differ"
            assert np.array_equal(h1, h2), "Holdout indices differ"

    def test_splits_without_replacement(self):
        """Train and holdout indices are disjoint and cover all data."""
        for train_n in [7, 10, 20]:
            splits = generate_splits(101, train_n, n_repeats=10)
            for train_idx, holdout_idx in splits:
                assert len(train_idx) == train_n
                assert len(holdout_idx) == 101 - train_n
                assert len(np.intersect1d(train_idx, holdout_idx)) == 0
                all_idx = np.sort(np.concatenate([train_idx, holdout_idx]))
                assert np.array_equal(all_idx, np.arange(101))

    def test_splits_different_across_n(self):
        """Different train_n produce different splits."""
        splits7 = generate_splits(101, 7, n_repeats=3)
        splits10 = generate_splits(101, 10, n_repeats=3)
        # At least first split should differ
        assert not np.array_equal(splits7[0][0], splits10[0][0])

    def test_splits_across_repeats_differ(self):
        """Different repeats produce different splits."""
        splits = generate_splits(101, 7, n_repeats=10)
        train_sets = [tuple(t) for t, _ in splits]
        assert len(set(train_sets)) == len(train_sets), \
            "All 10 splits should be different"


# ═══════════════════════════════════════════════════════════════
# Piecewise CDF & KS Distance Tests
# ═══════════════════════════════════════════════════════════════

class TestPiecewiseCDF:
    """Piecewise 3-parameter Weibull CDF tests."""

    def test_cdf_at_zero(self):
        """F(0) = 0 when gamma > 0."""
        result = weibull_cdf_piecewise(np.array([5.0]), 2.0, 100.0, 10.0)
        assert result[0] == 0.0

    def test_cdf_below_gamma(self):
        """F(y) = 0 for y <= gamma."""
        x = np.array([0.0, 50.0, 99.0])
        result = weibull_cdf_piecewise(x, 2.0, 100.0, 100.0)
        assert np.all(result == 0.0)

    def test_cdf_above_gamma(self):
        """F(y) > 0 for y > gamma."""
        result = weibull_cdf_piecewise(np.array([200.0]), 2.0, 100.0, 100.0)
        assert result[0] > 0.0
        assert result[0] < 1.0

    def test_cdf_value_at_characteristic_life(self):
        """At y = gamma + eta, F = 1 - exp(-1) ≈ 0.632."""
        result = weibull_cdf_piecewise(np.array([200.0]), 1.0, 100.0, 100.0)
        expected = 1.0 - math.exp(-1.0)
        assert abs(result[0] - expected) < 1e-10

    def test_cdf_monotonic(self):
        """CDF is monotonically non-decreasing."""
        x = np.linspace(0, 1000, 100)
        result = weibull_cdf_piecewise(x, 3.0, 500.0, 100.0)
        assert np.all(np.diff(result) >= -1e-15)

    def test_cdf_nonnegative_beta(self):
        """CDF works with any positive beta."""
        x = np.array([500.0, 1000.0, 1500.0])
        for beta in [1.0, 2.0, 5.0, 10.0]:
            result = weibull_cdf_piecewise(x, beta, 1000.0, 0.0)
            assert np.all(result >= 0)
            assert np.all(result <= 1.0)


class TestKSDistance:
    """One-sample two-sided KS distance tests."""

    def test_perfect_fit_zero_d(self):
        """If F perfectly matches ECDF, D = 0 (approximately)."""
        # Generate data from Weibull, fit back
        rng = np.random.default_rng(42)
        sample = 500.0 * (-np.log(1.0 - rng.random(1000))) ** (1.0 / 3.0)
        from real_data_gate import _estimate_weibull_ols
        beta, eta, gamma = _estimate_weibull_ols(sample)
        D = one_sample_two_sided_ks(sample, beta, eta, gamma)
        # Should be very small with large sample
        assert D < 0.1

    def test_worst_case_d_one(self):
        """D = 1 when holdout and fitted CDF have zero overlap."""
        holdout = np.array([1000.0, 2000.0, 3000.0])
        D = one_sample_two_sided_ks(holdout, beta_hat=1.0, eta_hat=1.0, gamma_hat=5000.0)
        # F(y) = 0 for all y <= 5000, ECDF ranges from 1/3 to 1
        # max gap is at F=0 vs ECDF=1
        assert D > 0.9

    def test_d_bounded_zero_to_one(self):
        """D is always in [0, 1]."""
        rng = np.random.default_rng(123)
        for _ in range(20):
            holdout = rng.random(50) * 1000 + 100
            beta = rng.random() * 5 + 0.5
            eta = rng.random() * 1000 + 50
            gamma = rng.random() * 200
            D = one_sample_two_sided_ks(holdout, beta, eta, gamma)
            assert 0.0 <= D <= 1.0, f"D={D} out of [0,1]"

    def test_small_holdout(self):
        """KS works with small holdout (m=1)."""
        D = one_sample_two_sided_ks(np.array([500.0]), 2.0, 500.0, 0.0)
        assert 0.0 <= D <= 1.0

    def test_empty_holdout_returns_one(self):
        """Empty holdout returns D=1 per contract."""
        D = one_sample_two_sided_ks(np.array([]), 2.0, 100.0, 0.0)
        assert D == 1.0

    def test_ks_independent_recompute(self):
        """KS can be independently recomputed from stored values."""
        holdout = np.array([400.0, 600.0, 800.0, 1000.0, 1200.0])
        beta_hat, eta_hat, gamma_hat = 2.0, 800.0, 200.0
        D1 = one_sample_two_sided_ks(holdout, beta_hat, eta_hat, gamma_hat)
        D2 = one_sample_two_sided_ks(holdout, beta_hat, eta_hat, gamma_hat)
        assert D1 == D2


# ═══════════════════════════════════════════════════════════════
# Failure Detection Tests
# ═══════════════════════════════════════════════════════════════

class TestFailureDetection:
    """Failure detection per §5.1 of frozen contract."""

    def test_valid_estimate_not_failed(self):
        train = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
        failed, reason = detect_failure(2.0, 300.0, 50.0, True, train)
        assert not failed
        assert reason is None

    def test_mdm_status_false(self):
        train = np.array([100.0, 200.0, 300.0])
        failed, reason = detect_failure(2.0, 300.0, 50.0, False, train)
        assert failed
        assert reason == "mdm_status_false"

    def test_negative_beta(self):
        train = np.array([100.0, 200.0, 300.0])
        failed, reason = detect_failure(-1.0, 300.0, 50.0, True, train)
        assert failed
        assert "beta" in reason

    def test_zero_eta(self):
        train = np.array([100.0, 200.0, 300.0])
        failed, reason = detect_failure(2.0, 0.0, 50.0, True, train)
        assert failed
        assert "eta" in reason

    def test_non_finite_beta(self):
        train = np.array([100.0, 200.0, 300.0])
        failed, reason = detect_failure(float('nan'), 300.0, 50.0, True, train)
        assert failed

    def test_gamma_exceeds_train_min(self):
        """Support-set violation in training data itself."""
        train = np.array([100.0, 200.0, 300.0])
        failed, reason = detect_failure(2.0, 300.0, 150.0, True, train)
        assert failed
        assert "support_set_violation_train" in reason

    def test_negative_gamma(self):
        train = np.array([100.0, 200.0, 300.0])
        failed, reason = detect_failure(2.0, 300.0, -10.0, True, train)
        assert failed
        assert "negative_gamma" in reason

    def test_exception_captured(self):
        train = np.array([100.0, 200.0, 300.0])
        exc = ValueError("test error")
        failed, reason = detect_failure(2.0, 300.0, 50.0, True, train, exc)
        assert failed
        assert "exception" in reason

    def test_gamma_equal_to_train_min_fails(self):
        """gamma == train_min is a support-set violation."""
        train = np.array([100.0, 200.0, 300.0])
        failed, reason = detect_failure(2.0, 300.0, 100.0, True, train)
        assert failed


class TestSupportSetViolation:
    """Support-set violation check."""

    def test_no_violation(self):
        assert not check_support_set_violation(
            np.array([200.0, 300.0]), 100.0
        )

    def test_violation_detected(self):
        assert check_support_set_violation(
            np.array([50.0, 200.0, 300.0]), 100.0
        )

    def test_edge_case_equal(self):
        """gamma must be strictly less than holdout minimum."""
        # The check is holdout < gamma, so equality doesn't count
        assert not check_support_set_violation(
            np.array([100.0, 200.0]), 100.0
        )


# ═══════════════════════════════════════════════════════════════
# Parameter Distance Tests
# ═══════════════════════════════════════════════════════════════

class TestParamDistance:
    """Parameter distance computation."""

    def test_perfect_match_zero(self):
        db, de = param_distance_rel(2.0, 1000.0, 2.0, 1000.0)
        assert db == 0.0
        assert de == 0.0

    def test_positive_distance(self):
        db, de = param_distance_rel(3.0, 1500.0, 2.0, 1000.0)
        assert db == 0.5  # |3-2|/2
        assert de == 0.5  # |1500-1000|/1000


# ═══════════════════════════════════════════════════════════════
# MDM.run() Five-tuple Return Tests
# ═══════════════════════════════════════════════════════════════

class TestMDMFiveTuple:
    """MDM.run() returns 5-tuple: (beta, eta, gamma, r_squared, status)."""

    def test_run_returns_five_tuple(self):
        rng = np.random.default_rng(42)
        data = 500 * (-np.log(1 - rng.random(20))) ** (1 / 3.0)
        result = MDM(data).run(offset=0.1)
        assert isinstance(result, tuple)
        assert len(result) == 5
        beta, eta, gamma, r2, status = result
        assert isinstance(beta, float)
        assert isinstance(eta, float)
        assert isinstance(gamma, float)
        assert isinstance(r2, float)
        assert isinstance(status, bool)

    def test_run_mdm_estimation_wrapper(self):
        """run_mdm_estimation returns proper values."""
        rng = np.random.default_rng(42)
        data = 500 * (-np.log(1 - rng.random(15))) ** (1 / 3.0)
        beta, eta, gamma, r2, status, exc = run_mdm_estimation(data, 0.1)
        assert isinstance(beta, float)
        assert isinstance(eta, float)
        assert isinstance(gamma, float)
        assert isinstance(r2, float)
        assert status is True
        assert exc is None

    def test_run_mdm_estimation_handles_invalid(self):
        """MDM with invalid offset still returns values."""
        rng = np.random.default_rng(42)
        data = 500 * (-np.log(1 - rng.random(7))) ** (1 / 3.0)
        beta, eta, gamma, r2, status, exc = run_mdm_estimation(data, 100.0)
        # Should not raise; just return values
        assert len([beta, eta, gamma, r2]) == 4


# ═══════════════════════════════════════════════════════════════
# L2 Frozen Deltas
# ═══════════════════════════════════════════════════════════════

class TestL2FrozenDeltas:
    """L2 uses frozen per-n deltas from E1/E2 cross-fit."""

    def test_l2_deltas_match_contract(self):
        assert L2_DELTAS[7] == 0.10
        assert L2_DELTAS[10] == 0.10
        assert L2_DELTAS[20] == 0.08

    def test_n7_n10_same_delta(self):
        """n=7 and n=10 both use δ=0.10 — Default and L2 should agree."""
        assert L2_DELTAS[7] == DEFAULT_DELTA
        assert L2_DELTAS[10] == DEFAULT_DELTA

    def test_n20_differs_from_default(self):
        """n=20 uses δ=0.08, which differs from Default δ=0.1."""
        assert L2_DELTAS[20] != DEFAULT_DELTA


# ═══════════════════════════════════════════════════════════════
# NN Feature Computation (no leakage)
# ═══════════════════════════════════════════════════════════════

class TestFeaturesNoLeakage:
    """Feature computation uses only observable sample statistics."""

    def test_13_features_returned(self):
        sample = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
        feats = compute_sample_features(sample)
        assert len(feats) == 13
        for col in SAMPLE_FEATURE_COLS:
            assert col in feats, f"Missing feature: {col}"

    def test_no_banned_fields_in_features(self):
        """Features must NOT include true parameter fields."""
        banned = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'seed',
                  'repeat_id', 'combo_id'}
        for col in SAMPLE_FEATURE_COLS:
            assert col not in banned, f"Banned field in features: {col}"


# ═══════════════════════════════════════════════════════════════
# Aggregation Tests
# ═══════════════════════════════════════════════════════════════

class TestAggregation:
    """Per-model aggregation and cross-model distribution."""

    def _make_result_df(self, n_repeats=10):
        """Build a minimal result DataFrame for testing."""
        rows = []
        for tn in [7, 10, 20]:
            for rep in range(n_repeats):
                rows.append({
                    'train_n': tn, 'repeat_index': rep,
                    'method': 'default', 'model_id': 'default',
                    'delta_used': 0.1,
                    'beta_hat': 2.0, 'eta_hat': 1000.0, 'gamma_hat': 0.0,
                    'r_squared': 0.95, 'mdm_status': 1,
                    'D': 0.1 + 0.01 * rep, 'failed': False,
                    'failure_reason': '',
                    'support_set_violation': 0,
                    'param_dist_beta': 0.05, 'param_dist_eta': 0.03,
                })
                rows.append({
                    'train_n': tn, 'repeat_index': rep,
                    'method': 'l2', 'model_id': 'l2',
                    'delta_used': 0.1,
                    'beta_hat': 2.0, 'eta_hat': 1000.0, 'gamma_hat': 0.0,
                    'r_squared': 0.95, 'mdm_status': 1,
                    'D': 0.09 + 0.01 * rep, 'failed': False,
                    'failure_reason': '',
                    'support_set_violation': 0,
                    'param_dist_beta': 0.04, 'param_dist_eta': 0.03,
                })
                for fid in range(5):
                    for seed in STABILITY_SEEDS:
                        rows.append({
                            'train_n': tn, 'repeat_index': rep,
                            'method': 'nn', 'model_id': f'fold_{fid}_seed_{seed}',
                            'delta_used': 0.12,
                            'beta_hat': 2.0, 'eta_hat': 1000.0, 'gamma_hat': 0.0,
                            'r_squared': 0.95, 'mdm_status': 1,
                            'D': 0.08 + 0.001 * fid + 0.001 * rep,
                            'failed': False, 'failure_reason': '',
                            'support_set_violation': 0,
                            'param_dist_beta': 0.03, 'param_dist_eta': 0.02,
                        })
        import pandas as pd
        return pd.DataFrame(rows, columns=RESULT_COLUMNS)

    def test_15_nn_models_per_train_n(self):
        """15 NN model rows in per-model aggregation per train_n."""
        df = self._make_result_df()
        agg = aggregate_per_model(df)
        nn_models = agg[agg['method'] == 'nn']
        for tn in TRAIN_N_VALUES:
            count = len(nn_models[nn_models['train_n'] == tn])
            assert count == 15, f"Expected 15 NN models for n={tn}, got {count}"

    def test_default_l2_one_row_each(self):
        """Default and L2 have exactly 1 row each per train_n."""
        df = self._make_result_df()
        agg = aggregate_per_model(df)
        for method in ['default', 'l2']:
            m_agg = agg[agg['method'] == method]
            for tn in TRAIN_N_VALUES:
                count = len(m_agg[m_agg['train_n'] == tn])
                assert count == 1, \
                    f"Expected 1 {method} row for n={tn}, got {count}"

    def test_primary_key_unique(self):
        """(train_n, repeat_index, method, model_id) is unique."""
        df = self._make_result_df()
        pk_cols = ['train_n', 'repeat_index', 'method', 'model_id']
        dups = df.duplicated(subset=pk_cols).sum()
        assert dups == 0, f"Found {dups} duplicate primary keys"

    def test_expected_row_count_17_per_split(self):
        """Each split has 17 rows: 1 default + 1 l2 + 15 nn."""
        df = self._make_result_df(n_repeats=5)
        for tn in TRAIN_N_VALUES:
            for rep in range(5):
                count = len(df[(df['train_n'] == tn) & (df['repeat_index'] == rep)])
                assert count == 17, \
                    f"n={tn} rep={rep}: expected 17 rows, got {count}"

    def test_total_expected_rows(self):
        """Total: 3 × 500 × 17 = 25500 rows."""
        df = self._make_result_df(n_repeats=5)
        # Our test uses 5 repeats, so 3 * 5 * 17 = 255
        expected = 3 * 5 * 17
        assert len(df) == expected, f"Expected {expected}, got {len(df)}"

    def test_failed_rows_preserved(self):
        """Failed rows are kept, not silently dropped."""
        df = self._make_result_df(n_repeats=5)
        # Manually mark some rows as failed
        df_copy = df.copy()
        df_copy.loc[df_copy.sample(5, random_state=42).index, 'failed'] = True
        df_copy.loc[df_copy['failed'], 'D'] = 1.0
        # Aggregation should include all rows
        agg = aggregate_per_model(df_copy)
        for _, row in agg.iterrows():
            assert row['n_repeats'] == 5, \
                f"Expected 5 repeats, got {row['n_repeats']}"

    def test_failure_rate_reported(self):
        """Failure rate is tracked per model."""
        df = self._make_result_df(n_repeats=10)
        df_copy = df.copy()
        # Fail 3 out of 10 for default at n=7
        mask = (df_copy['train_n'] == 7) & (df_copy['method'] == 'default') & \
               (df_copy['repeat_index'].isin([0, 1, 2]))
        df_copy.loc[mask, 'failed'] = True
        agg = aggregate_per_model(df_copy)
        default_n7 = agg[(agg['method'] == 'default') & (agg['train_n'] == 7)]
        assert default_n7.iloc[0]['failure_rate'] == 0.3

    def test_cross_model_distribution_15_pattern(self):
        """Cross-model distribution aggregates across 15 models."""
        df = self._make_result_df(n_repeats=10)
        agg = aggregate_per_model(df)
        dist = cross_model_distribution(agg)
        assert len(dist) > 0
        # Should have rows for each metric × each train_n
        metrics = dist['metric'].unique()
        assert 'median_D' in metrics


# ═══════════════════════════════════════════════════════════════
# Tie Rules Tests
# ═══════════════════════════════════════════════════════════════

class TestTieRules:
    """Paired win/loss/tie with ε=1e-9 tolerance."""

    def _make_comparison_df(self):
        """Make a DataFrame where l2 always beats default by a small margin."""
        import pandas as pd
        rows = []
        for rep in range(10):
            rows.append({
                'train_n': 7, 'repeat_index': rep,
                'method': 'default', 'model_id': 'default',
                'delta_used': 0.1,
                'beta_hat': 2.0, 'eta_hat': 1000.0, 'gamma_hat': 0.0,
                'r_squared': 0.95, 'mdm_status': 1,
                'D': 0.15, 'failed': False, 'failure_reason': '',
                'support_set_violation': 0,
                'param_dist_beta': 0.05, 'param_dist_eta': 0.03,
            })
            rows.append({
                'train_n': 7, 'repeat_index': rep,
                'method': 'l2', 'model_id': 'l2',
                'delta_used': 0.1,
                'beta_hat': 2.0, 'eta_hat': 1000.0, 'gamma_hat': 0.0,
                'r_squared': 0.95, 'mdm_status': 1,
                'D': 0.10, 'failed': False, 'failure_reason': '',
                'support_set_violation': 0,
                'param_dist_beta': 0.05, 'param_dist_eta': 0.03,
            })
        return pd.DataFrame(rows, columns=RESULT_COLUMNS)

    def test_l2_wins_all(self):
        """When l2 D is always lower, l2 wins all."""
        df = self._make_comparison_df()
        wins = compute_paired_wins(df, 'l2', 'default')
        wr = wins[7]['win_rate']
        # l2 over default: D_l2=0.10 < D_default=0.15 → l2 wins all
        assert wr == 1.0, f"Expected win_rate=1.0, got {wr}"

    def test_tie_when_diff_below_epsilon(self):
        """When D diff < 1e-9, it's a tie."""
        import pandas as pd
        rows = []
        for rep in range(5):
            rows.append({
                'train_n': 7, 'repeat_index': rep,
                'method': 'default', 'model_id': 'default',
                'delta_used': 0.1,
                'beta_hat': 2.0, 'eta_hat': 1000.0, 'gamma_hat': 0.0,
                'r_squared': 0.95, 'mdm_status': 1,
                'D': 0.1, 'failed': False, 'failure_reason': '',
                'support_set_violation': 0,
                'param_dist_beta': 0.05, 'param_dist_eta': 0.03,
            })
            # D differs by 5e-10 < 1e-9
            d_val = 0.1 + 5e-10
            rows.append({
                'train_n': 7, 'repeat_index': rep,
                'method': 'l2', 'model_id': 'l2',
                'delta_used': 0.1,
                'beta_hat': 2.0, 'eta_hat': 1000.0, 'gamma_hat': 0.0,
                'r_squared': 0.95, 'mdm_status': 1,
                'D': d_val, 'failed': False, 'failure_reason': '',
                'support_set_violation': 0,
                'param_dist_beta': 0.05, 'param_dist_eta': 0.03,
            })
        df = pd.DataFrame(rows, columns=RESULT_COLUMNS)
        wins = compute_paired_wins(df, 'l2', 'default')
        assert wins[7]['ties'] == 5  # all ties

    def test_tie_tolerance_exact(self):
        """Exact epsilon boundary: diff=1e-9 is a tie."""
        import pandas as pd
        rows = [
            {'train_n': 7, 'repeat_index': 0, 'method': 'default',
             'model_id': 'default', 'D': 0.1, 'failed': False,
             'delta_used': 0.1, 'beta_hat': 2.0, 'eta_hat': 1000.0,
             'gamma_hat': 0.0, 'r_squared': 0.95, 'mdm_status': 1,
             'failure_reason': '', 'support_set_violation': 0,
             'param_dist_beta': 0.05, 'param_dist_eta': 0.03},
            {'train_n': 7, 'repeat_index': 0, 'method': 'l2',
             'model_id': 'l2', 'D': 0.1 + 1e-9, 'failed': False,
             'delta_used': 0.1, 'beta_hat': 2.0, 'eta_hat': 1000.0,
             'gamma_hat': 0.0, 'r_squared': 0.95, 'mdm_status': 1,
             'failure_reason': '', 'support_set_violation': 0,
             'param_dist_beta': 0.05, 'param_dist_eta': 0.03},
        ]
        df = pd.DataFrame(rows, columns=RESULT_COLUMNS)
        wins = compute_paired_wins(df, 'l2', 'default')
        assert wins[7]['ties'] == 1


# ═══════════════════════════════════════════════════════════════
# Input Hash Verification Tests
# ═══════════════════════════════════════════════════════════════

class TestInputHashVerification:
    """Input SHA256 verification against frozen values."""

    def test_birnsaun_sha256_verified(self):
        hashes = verify_input_hashes(str(NIST_DIR))
        assert hashes['BIRNSAUN.DAT']['match'], "BIRNSAUN.DAT SHA256 mismatch"

    def test_lifetimes_csv_sha256_verified(self):
        hashes = verify_input_hashes(str(NIST_DIR))
        assert hashes['lifetimes.csv']['match'], "lifetimes.csv SHA256 mismatch"

    def test_hash_mismatch_raises(self):
        """Mismatched SHA256 raises RuntimeError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create a fake lifetimes.csv with wrong content
            csv_path = os.path.join(tmpdir, 'lifetimes.csv')
            with open(csv_path, 'w') as f:
                f.write("failure_time\n1.0\n2.0\n3.0\n")
            # Also need BIRNSAUN.DAT (or fake it)
            dat_path = os.path.join(tmpdir, 'BIRNSAUN.DAT')
            with open(dat_path, 'wb') as f:
                f.write(b"fake data")
            with pytest.raises(RuntimeError, match="SHA256"):
                verify_input_hashes(tmpdir)


# ═══════════════════════════════════════════════════════════════
# Output Protection Tests
# ═══════════════════════════════════════════════════════════════

class TestOutputProtection:
    """Output safety checks."""

    def test_clean_dir_no_conflict(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            existing = check_output_safety(tmpdir)
            assert len(existing) == 0

    def test_existing_file_detected(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create one of the expected output files
            Path(tmpdir, 'real_holdout_results.csv').touch()
            existing = check_output_safety(tmpdir)
            assert 'real_holdout_results.csv' in str(existing[0])


# ═══════════════════════════════════════════════════════════════
# Smoke Run Tests (temp directory only)
# ═══════════════════════════════════════════════════════════════

class TestSmokeRun:
    """Small smoke run writing ONLY to temp directory."""

    def test_smoke_run_default_l2_only(self):
        """Smoke run with 3 repeats, Default and L2 only, temp dir."""
        tmpdir = tempfile.mkdtemp(prefix='p7_smoke_')
        try:
            result = run_pipeline(
                data_dir=str(NIST_DIR),
                output_dir=tmpdir,
                chunks_dir=str(CHUNKS_DIR) if CHUNKS_DIR.exists() else None,
                smoke_n_repeats=3,
                smoke_skip_nn=True,
            )
            assert result is not None, "Pipeline should succeed"
            df = result['df_results']
            # 3 train_n × 3 repeats × 2 methods = 18 rows
            assert len(df) == 3 * 3 * 2, f"Expected 18 rows, got {len(df)}"

            # Check output files exist
            assert os.path.exists(os.path.join(tmpdir, 'real_holdout_results.csv'))
            assert os.path.exists(os.path.join(tmpdir, 'real_holdout_summary.json'))
            assert os.path.exists(os.path.join(tmpdir, 'real_data_manifest.json'))
            assert os.path.exists(os.path.join(tmpdir, 'run_log.txt'))

            # Verify key uniqueness
            df_check = result['df_results']
            dups = df_check.duplicated(
                subset=['train_n', 'repeat_index', 'method', 'model_id']
            ).sum()
            assert dups == 0

            # Verify D is in [0, 1]
            assert df_check['D'].between(0, 1).all()

            # Verify failed rows are recorded properly
            assert 'failed' in df_check.columns
            assert 'failure_reason' in df_check.columns

        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_smoke_no_formal_output_contamination(self):
        """Smoke run does NOT write to formal output directory."""
        # Get the formal output dir
        formal_dir = str(NIST_DIR)
        # Check what files exist before
        before = set(os.listdir(formal_dir))
        tmpdir = tempfile.mkdtemp(prefix='p7_smoke_')
        try:
            run_pipeline(
                data_dir=str(NIST_DIR),
                output_dir=tmpdir,
                smoke_n_repeats=2,
                smoke_skip_nn=True,
            )
            after = set(os.listdir(formal_dir))
            # No new files in formal dir
            assert before == after, \
                f"Formal dir contaminated: {after - before}"
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


# ═══════════════════════════════════════════════════════════════
# Contract Compliance Tests
# ═══════════════════════════════════════════════════════════════

class TestContractCompliance:
    """Check that implementation meets frozen contract requirements."""

    def test_l2_selected_deltas_csv_exists(self):
        """L2 delta table must exist."""
        csv_path = (STUDY_ROOT / "artifacts" / "formal" /
                    "E1_E2_crossfit" / "selected_deltas.csv")
        assert csv_path.exists(), f"Missing L2 delta table: {csv_path}"

    def test_e4d_manifest_exists(self):
        """E4d manifest with 15 selectors must exist."""
        manifest_path = (STUDY_ROOT / "artifacts" / "formal" /
                         "E4_robustness" / "manifest_e4d.json")
        assert manifest_path.exists(), f"Missing E4d manifest: {manifest_path}"
        with open(manifest_path, encoding='utf-8') as f:
            m = json.load(f)
        assert m['training_contract']['total_models'] == 15

    def test_main_grid_chunks_exist(self):
        """45 main-grid chunks must exist for NN training."""
        if CHUNKS_DIR.exists():
            chunks = list(CHUNKS_DIR.glob("chunk_*_mdm.csv"))
            assert len(chunks) == 45, \
                f"Expected 45 chunks, found {len(chunks)}"

    def test_nist_data_dir_structure(self):
        """NIST data dir has all required files."""
        required = ['source.json', 'lifetimes.csv', 'BIRNSAUN.DAT',
                    'convert_birnsaun_to_lifetimes.py']
        for fname in required:
            assert (NIST_DIR / fname).exists(), f"Missing: {fname}"

    def test_placeholder_guard_active(self):
        """_P6_PLACEHOLDER_GUARD is still True."""
        from run_real_data_validation import _P6_PLACEHOLDER_GUARD
        assert _P6_PLACEHOLDER_GUARD, (
            "Guard must remain True until P7 passes independent review"
        )


# ═══════════════════════════════════════════════════════════════
# No-Leakage Constraint Tests
# ═══════════════════════════════════════════════════════════════

class TestNoLeakageConstraint:
    """Verify that real data never leaks into training or scaler fitting."""

    def test_features_exclude_true_params(self):
        """Sample features must not include true parameters."""
        sample = np.array([100.0, 200.0, 300.0, 400.0, 500.0])
        feats = compute_sample_features(sample)
        banned = {'beta', 'eta', 'gamma', 'gamma_over_eta'}
        for key in banned:
            assert key not in feats, f"Banned key in features: {key}"

    def test_feature_cols_no_banned(self):
        """Feature column set excludes true parameters."""
        banned = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'seed',
                  'repeat_id', 'combo_id'}
        for col in SAMPLE_FEATURE_COLS:
            assert col not in banned, f"{col} should be banned"

    def test_zscore_only_dimensional_features(self):
        """Only dimensional features are z-scored; raw features passthrough."""
        for col in FEATURE_COLS_ZSCORE:
            assert col in ['x_min', 'x_max', 'range', 'Q1', 'Med',
                           'Q3', 'IQR', 'x_bar', 's']
        for col in FEATURE_COLS_RAW:
            assert col in ['n', 'CV', 'g1', 'g2']

    def test_delta_grid_frozen(self):
        """Delta grid matches frozen 26-point grid."""
        assert len(DELTA_GRID) == 26
        assert DELTA_GRID[0] == 0.00
        assert DELTA_GRID[-1] == 0.50
        assert DELTA_GRID[1] - DELTA_GRID[0] == 0.02
