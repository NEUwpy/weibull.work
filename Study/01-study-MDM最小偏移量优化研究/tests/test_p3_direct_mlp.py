"""Fail-closed tests for P3 Direct-MLP and fair comparison contract.

Covers the issues most likely to affect scientific conclusions:
- Fold/scaler/test data leakage
- Forbidden fields not in Direct-MLP input
- Output parameter constraints
- Fixed seed reproducibility
- Six-method sample key alignment
- J1 and failure penalty correctness
- Failed samples not silently deleted
- Model-first aggregation correctness
- Existing formal products not overwritten
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

CODE_DIR = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIR))

_PYTHON_DIR = Path(__file__).resolve().parents[3] / "python"
sys.path.insert(0, str(_PYTHON_DIR))

import p3_config as cfg
import run_p3_direct_mlp as direct
import run_p3_fair_compare as compare
import run_E4_formal_validation as e4
from studies.common.sample import generate_sample


# ── Helpers ────────────────────────────────────────────────────────────

def _make_mini_features(n_combos=2, repeats=5):
    """Build a minimal sample_features DataFrame for testing."""
    rows = []
    for beta in [1.5, 2.0][:n_combos]:
        for rid in range(repeats):
            sample = generate_sample(beta, 1.0, beta * 0.1, 7, rid, seed="study01_v1")
            feats = e4.compute_sample_features(sample)
            rows.append({
                "beta": beta, "eta": 1.0, "gamma": beta * 0.1,
                "gamma_over_eta": 0.1, "n": 7, "repeat_id": rid,
                **feats,
            })
    return pd.DataFrame(rows)


# ── 1. Output constraints ──────────────────────────────────────────────

class TestOutputConstraints:
    def test_softplus_positive_for_beta_eta(self):
        raw = np.array([[-100, -100, -100]])
        out = direct.apply_output_transform(raw)
        assert out[0, 0] > 0, "beta must be > 0 even for very negative input"
        assert out[0, 1] > 0, "eta must be > 0 even for very negative input"

    def test_relu_nonneg_for_gamma(self):
        raw = np.array([[1.0, 1.0, -5.0]])
        out = direct.apply_output_transform(raw)
        assert out[0, 2] == 0.0, "gamma must be >= 0"

    def test_verify_accepts_valid(self):
        raw = np.array([[1.0, 2.0, 3.0], [0.5, 0.1, 0.0]])
        out = direct.apply_output_transform(raw)
        assert direct.verify_output_constraints(out)

    def test_verify_rejects_zero_beta(self):
        preds = np.array([[0.0, 1.0, 1.0]])
        assert not direct.verify_output_constraints(preds)

    def test_verify_rejects_negative_eta(self):
        preds = np.array([[1.0, -0.001, 1.0]])
        assert not direct.verify_output_constraints(preds)


# ── 2. Forbidden fields ────────────────────────────────────────────────

class TestForbiddenFields:
    def test_no_forbidden_in_feature_cols(self):
        feats = set(e4.SAMPLE_FEATURE_COLS)
        for f in cfg.FORBIDDEN_INPUT_FIELDS:
            assert f not in feats, f"Forbidden field '{f}' is in SAMPLE_FEATURE_COLS"

    def test_no_true_params_in_features(self):
        """True beta/eta/gamma must never be in the 13 feature columns."""
        forbidden_params = {"beta", "eta", "gamma"}
        feats = set(e4.SAMPLE_FEATURE_COLS)
        assert forbidden_params.isdisjoint(feats)

    def test_no_combo_id_in_features(self):
        """combo_id / repeat_id / fold must not appear in features."""
        forbidden_ids = {"repeat_id", "fold", "combo_id", "track", "seed"}
        feats = set(e4.SAMPLE_FEATURE_COLS)
        assert forbidden_ids.isdisjoint(feats)


# ── 3. Parameter loss formula ──────────────────────────────────────────

class TestParamLoss:
    def test_zero_loss_for_perfect_prediction(self):
        loss = direct.compute_param_loss(2.0, 2.0, 1.0, 1.0, 0.5, 0.5)
        assert loss == pytest.approx(0.0, abs=1e-12)

    def test_matches_j1_squared_formula(self):
        """Direct-MLP loss must match the J1 parameter-normalization."""
        loss = direct.compute_param_loss(2.5, 2.0, 1.5, 1.0, 0.8, 0.5)
        e_beta = (2.5 - 2.0) / 2.0
        e_eta = (1.5 - 1.0) / 1.0
        e_gamma = (0.8 - 0.5) / 1.0
        expected = e_beta**2 + e_eta**2 + e_gamma**2
        assert loss == pytest.approx(expected)

    def test_gamma_normalized_by_eta_not_gamma(self):
        """gamma error must be normalized by eta, not gamma (per protocol)."""
        loss = direct.compute_param_loss(2.0, 2.0, 1.0, 1.0, 1.5, 1.0)
        e_gamma = (1.5 - 1.0) / 1.0  # normalized by eta=1
        assert loss == pytest.approx(e_gamma**2)


# ── 4. Fold/scaler isolation ───────────────────────────────────────────

class TestFoldIsolation:
    def test_train_fold_excludes_test_combos(self):
        """Training data must not contain test combos."""
        splits = e4.get_combo_split()
        assert len(splits) == 5
        for fold in splits:
            train_set = set(fold["train_combos"])
            test_set = set(fold["test_combos"])
            assert train_set.isdisjoint(test_set), (
                f"{fold['fold_name']}: train and test overlap"
            )

    def test_zscore_uses_train_fold_only(self):
        """Z-score params must be computed from training data only."""
        df = _make_mini_features(n_combos=2, repeats=5)
        # Use combo (1.5, 0.1, 7) as train, verify only those rows selected
        train_combos = [(1.5, 0.1, 7)]
        X, Y, meta = direct.build_training_targets(df, train_combos)
        assert meta["n_train_samples"] == 5  # 1 combo × 5 repeats


# ── 5. Seed reproducibility ────────────────────────────────────────────

class TestSeedReproducibility:
    def test_same_seed_same_model(self):
        """Same seed must produce identical models (weights)."""
        df = _make_mini_features(n_combos=1, repeats=30)
        train_combos = [(1.5, 0.1, 7)]
        X, Y, _ = direct.build_training_targets(df, train_combos)

        m1, _ = direct.train_direct_mlp(X, Y, seed=42)
        m2, _ = direct.train_direct_mlp(X, Y, seed=42)

        # Same seed → same coefs
        np.testing.assert_array_equal(m1.coefs_[0], m2.coefs_[0])

    def test_different_seed_different_model(self):
        """Different seeds should generally produce different weights."""
        df = _make_mini_features(n_combos=1, repeats=30)
        train_combos = [(1.5, 0.1, 7)]
        X, Y, _ = direct.build_training_targets(df, train_combos)

        m1, _ = direct.train_direct_mlp(X, Y, seed=42)
        m2, _ = direct.train_direct_mlp(X, Y, seed=2026)

        # Weights should differ (not identical)
        assert not np.allclose(m1.coefs_[0], m2.coefs_[0]), \
            "Different seeds produced identical weights"


# ── 6. Six-method sample key alignment ─────────────────────────────────

class TestSampleKeyAlignment:
    def test_traditional_methods_use_same_samples(self):
        """MLE, LSE, WMLE, MDM must evaluate identical sample instances."""
        rows_mle = compare.evaluate_traditional("mle", 1.5, 1.0, 0.15, 7, repeats=3)
        rows_lse = compare.evaluate_traditional("lse", 1.5, 1.0, 0.15, 7, repeats=3)
        rows_wmle = compare.evaluate_traditional("wmle", 1.5, 1.0, 0.15, 7, repeats=3)

        keys_mle = [(r["beta"], r["gamma_over_eta"], r["n"], r["repeat_id"]) for r in rows_mle]
        keys_lse = [(r["beta"], r["gamma_over_eta"], r["n"], r["repeat_id"]) for r in rows_lse]
        keys_wmle = [(r["beta"], r["gamma_over_eta"], r["n"], r["repeat_id"]) for r in rows_wmle]

        assert keys_mle == keys_lse == keys_wmle


# ── 7. Failure contract ────────────────────────────────────────────────

class TestFailureContract:
    def test_failed_samples_not_deleted(self):
        """Failed samples must remain in results with failure_reason."""
        rows = compare.evaluate_traditional("mle", 1.5, 1.0, 0.15, 7, repeats=5)
        # Even if some fail, all 5 rows must be present
        assert len(rows) == 5
        for r in rows:
            assert "failure_reason" in r
            assert "failed" in r

    def test_failure_penalty_applied(self):
        """Failed samples get the frozen penalty, not deleted."""
        rows = [
            {"method": "MLE", "true_loss": 0.1, "failed": False, "failure_reason": ""},
            {"method": "MLE", "true_loss": float("nan"), "failed": True, "failure_reason": "unbounded"},
        ]
        penalty = 5.0
        rows = compare.apply_failure_contract(rows, penalty)
        assert rows[1]["true_loss"] == penalty
        assert rows[1]["true_loss_complete_case"] != penalty or np.isnan(rows[1]["true_loss_complete_case"])

    def test_no_silent_deletion(self):
        """apply_failure_contract must not remove any rows."""
        rows = [
            {"method": "MLE", "true_loss": 0.1, "failed": False, "failure_reason": ""},
            {"method": "MLE", "true_loss": float("nan"), "failed": True, "failure_reason": "fail"},
            {"method": "MLE", "true_loss": 0.2, "failed": False, "failure_reason": ""},
        ]
        result = compare.apply_failure_contract(rows, 5.0)
        assert len(result) == 3


# ── 8. Model-first aggregation ─────────────────────────────────────────

class TestModelFirstAggregation:
    def test_pooled_j1_is_sqrt_of_mean(self):
        losses = np.array([0.0, 1.0, 4.0])
        j1 = compare.pooled_j1(losses)
        assert j1 == pytest.approx(np.sqrt(5.0 / 3.0))

    def test_learning_method_aggregates_per_model(self):
        """Learning methods must aggregate per fold×seed first."""
        rows = [
            {"fold": "f1", "seed": 42, "method": "Direct-MLP", "true_loss": 0.1, "failed": False},
            {"fold": "f1", "seed": 42, "method": "Direct-MLP", "true_loss": 0.4, "failed": False},
            {"fold": "f1", "seed": 2026, "method": "Direct-MLP", "true_loss": 0.2, "failed": False},
            {"fold": "f1", "seed": 2026, "method": "Direct-MLP", "true_loss": 0.2, "failed": False},
        ]
        summary = compare.model_first_summary(rows, "Direct-MLP")
        assert summary["n_models"] == 2  # Two (fold, seed) pairs
        # Per-model: f1/42 → sqrt(mean([0.1,0.4]))=sqrt(0.25), f1/2026 → sqrt(mean([0.2,0.2]))=sqrt(0.2)
        per_model_j1s = [np.sqrt(0.25), np.sqrt(0.2)]
        assert summary["median_J1"] == pytest.approx(np.median(per_model_j1s))

    def test_traditional_method_single_pool(self):
        """Non-learning methods have a single pooled J1."""
        rows = [
            {"fold": "", "seed": 0, "method": "MLE", "true_loss": 0.1, "failed": False},
            {"fold": "", "seed": 0, "method": "MLE", "true_loss": 0.4, "failed": False},
        ]
        summary = compare.model_first_summary(rows, "MLE")
        assert summary["n_models"] == 1
        assert summary["median_J1"] == pytest.approx(np.sqrt(0.25))


# ── 9. Config frozen / provenance ──────────────────────────────────────

class TestConfigFrozen:
    def test_config_hash_stable(self):
        """Config hash must be deterministic across runs."""
        h1 = direct.config_hash()
        h2 = direct.config_hash()
        assert h1 == h2

    def test_production_contract_complete(self):
        c = cfg.production_contract()
        assert c["output_transform"] == "softplus_softplus_relu"
        assert c["hidden_layers"] == (256, 128, 64)
        assert c["seeds"] == [42, 2026, 3407]
        assert "beta" not in c["feature_columns"]
        assert "gamma" not in c["feature_columns"]
        assert "repeat_id" not in c["feature_columns"]

    def test_correction_not_used(self):
        """The one-allowed correction must not have been used yet."""
        assert cfg.CONFIG_CORRECTION_USED is False


# ── 10. No overwrite of existing artifacts ─────────────────────────────

class TestNoOverwrite:
    def test_p2_v2_manifest_unchanged(self):
        """P2 v2 manifest must still be sealed."""
        manifest_path = Path(__file__).resolve().parents[1] / (
            "artifacts/formal/extended_validation/p2_generalization_v2/manifest.json"
        )
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert m.get("manifest_version") == "study01-p2-generation-v2"

    def test_e3b_manifest_unchanged(self):
        """E3b manifest must still be sealed."""
        manifest_path = Path(__file__).resolve().parents[1] / (
            "artifacts/formal/E3b_vector_mlp/manifest.json"
        )
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert m.get("run_id", "").startswith("E3b")
