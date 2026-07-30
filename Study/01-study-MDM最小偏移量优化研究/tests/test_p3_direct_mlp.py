"""Fail-closed tests for P3 Direct-MLP and fair comparison contract.

Covers the issues most likely to affect scientific conclusions:
- Target representation: perfect decode round-trip
- Output constraints: beta>0, eta>0, gamma>=0
- Non-unit eta compatibility
- Fold/scaler/test data leakage (no inline duplication)
- Forbidden fields not in Direct-MLP input
- Fixed seed reproducibility
- Six-method sample key alignment (per method×fold×seed)
- J1 and per-fold failure penalty correctness
- Failed samples not silently deleted
- Model-first aggregation correctness
- Production-path regression: run_fair_comparison with tamper detection
- Existing formal products not overwritten
"""

from __future__ import annotations

import json
import sys
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


def _make_mini_risk_curves(n_combos=2, repeats=5):
    """Build a minimal risk_curves DataFrame (loss_d0.1 column)."""
    rows = []
    for beta in [1.5, 2.0][:n_combos]:
        for rid in range(repeats):
            row = {"beta": beta, "gamma_over_eta": 0.1, "n": 7, "repeat_id": rid}
            for d in range(0, 52, 2):
                row[f"loss_d{d/100:.2f}"] = 0.5 + abs(d/100 - 0.1) * 2
            rows.append(row)
    return pd.DataFrame(rows)


# ── 1. Target representation: encode/decode round-trip ─────────────────

class TestTargetRepresentation:
    def test_perfect_decode_unit_eta(self):
        """Perfect prediction must decode back to exactly the true params."""
        params = np.array([[1.5, 1.0, 0.1], [3.0, 1.0, 0.5]])
        assert direct.verify_perfect_decode(params, atol=1e-5)

    def test_perfect_decode_nonunit_eta(self):
        """Non-unit eta must also round-trip exactly."""
        params = np.array([[2.0, 3.5, 0.7], [4.0, 0.5, 0.1]])
        assert direct.verify_perfect_decode(params, atol=1e-5)

    def test_perfect_decode_extreme_params(self):
        """Extreme beta values must round-trip."""
        params = np.array([[0.5, 0.1, 0.0], [5.0, 10.0, 5.0]])
        assert direct.verify_perfect_decode(params, atol=1e-4)

    def test_perfect_decode_loss_is_zero(self):
        """After perfect decode, compute_param_loss must be 0."""
        params = np.array([[2.5, 1.5, 0.3]])
        encoded = direct.encode_targets(params)
        decoded = direct.decode_output(encoded)
        loss = direct.compute_param_loss(
            decoded[0, 0], params[0, 0],
            decoded[0, 1], params[0, 1],
            decoded[0, 2], params[0, 2],
        )
        assert loss == pytest.approx(0.0, abs=1e-10)

    def test_encode_decode_inverse_relationship(self):
        """softplus(inverse_softplus(x)) = x for x > 0."""
        for x in [0.01, 0.1, 0.5, 1.0, 2.0, 5.0, 10.0]:
            inv = direct._inverse_softplus(np.array([x]))[0]
            fwd = direct._softplus(np.array([inv]))[0]
            assert fwd == pytest.approx(x, abs=1e-6), f"softplus(inverse_softplus({x})) = {fwd}"


# ── 2. Output constraints ──────────────────────────────────────────────

class TestOutputConstraints:
    def test_softplus_positive_for_beta_eta(self):
        raw = np.array([[-100, -100, -100]])
        out = direct.decode_output(raw)
        assert out[0, 0] > 0
        assert out[0, 1] > 0

    def test_relu_nonneg_for_gamma(self):
        raw = np.array([[1.0, 1.0, -5.0]])
        out = direct.decode_output(raw)
        assert out[0, 2] == 0.0

    def test_verify_accepts_valid(self):
        raw = np.array([[1.0, 2.0, 3.0], [0.5, 0.1, 0.0]])
        out = direct.decode_output(raw)
        assert direct.verify_output_constraints(out)

    def test_verify_rejects_zero_beta(self):
        preds = np.array([[0.0, 1.0, 1.0]])
        assert not direct.verify_output_constraints(preds)


# ── 3. Forbidden fields ────────────────────────────────────────────────

class TestForbiddenFields:
    def test_no_forbidden_in_feature_cols(self):
        feats = set(e4.SAMPLE_FEATURE_COLS)
        for f in cfg.FORBIDDEN_INPUT_FIELDS:
            assert f not in feats, f"Forbidden field '{f}' is in SAMPLE_FEATURE_COLS"

    def test_no_true_params_in_features(self):
        forbidden_params = {"beta", "eta", "gamma"}
        assert forbidden_params.isdisjoint(set(e4.SAMPLE_FEATURE_COLS))

    def test_no_combo_id_in_features(self):
        forbidden_ids = {"repeat_id", "fold", "combo_id", "track", "seed"}
        assert forbidden_ids.isdisjoint(set(e4.SAMPLE_FEATURE_COLS))


# ── 4. Parameter loss formula ──────────────────────────────────────────

class TestParamLoss:
    def test_zero_loss_for_perfect_prediction(self):
        loss = direct.compute_param_loss(2.0, 2.0, 1.0, 1.0, 0.5, 0.5)
        assert loss == pytest.approx(0.0, abs=1e-12)

    def test_matches_j1_squared_formula(self):
        loss = direct.compute_param_loss(2.5, 2.0, 1.5, 1.0, 0.8, 0.5)
        e_beta = (2.5 - 2.0) / 2.0
        e_eta = (1.5 - 1.0) / 1.0
        e_gamma = (0.8 - 0.5) / 1.0
        expected = e_beta**2 + e_eta**2 + e_gamma**2
        assert loss == pytest.approx(expected)

    def test_gamma_normalized_by_eta_not_gamma(self):
        loss = direct.compute_param_loss(2.0, 2.0, 1.0, 1.0, 1.5, 1.0)
        e_gamma = (1.5 - 1.0) / 1.0
        assert loss == pytest.approx(e_gamma**2)


# ── 5. Fold/scaler isolation ───────────────────────────────────────────

class TestFoldIsolation:
    def test_train_fold_excludes_test_combos(self):
        splits = e4.get_combo_split()
        assert len(splits) == 5
        for fold in splits:
            train_set = set(fold["train_combos"])
            test_set = set(fold["test_combos"])
            assert train_set.isdisjoint(test_set)

    def test_zscore_uses_train_fold_only(self):
        df = _make_mini_features(n_combos=2, repeats=5)
        train_combos = [(1.5, 0.1, 7)]
        X, Y, meta = direct.build_training_data(df, train_combos)
        assert meta["n_train_samples"] == 5

    def test_no_inline_duplication(self):
        """build_training_data must call e4._fit_zscore_params directly."""
        import inspect
        src = inspect.getsource(direct.build_training_data)
        assert "e4._fit_zscore_params" in src, "Must call e4._fit_zscore_params"
        assert "e4._build_X_from_samples" in src, "Must call e4._build_X_from_samples"


# ── 6. Seed reproducibility ────────────────────────────────────────────

class TestSeedReproducibility:
    def test_same_seed_same_model(self):
        df = _make_mini_features(n_combos=1, repeats=30)
        train_combos = [(1.5, 0.1, 7)]
        X, Y, _ = direct.build_training_data(df, train_combos)
        m1, _ = direct.train_direct_mlp(X, Y, seed=42)
        m2, _ = direct.train_direct_mlp(X, Y, seed=42)
        np.testing.assert_array_equal(m1.coefs_[0], m2.coefs_[0])

    def test_different_seed_different_model(self):
        df = _make_mini_features(n_combos=1, repeats=30)
        train_combos = [(1.5, 0.1, 7)]
        X, Y, _ = direct.build_training_data(df, train_combos)
        m1, _ = direct.train_direct_mlp(X, Y, seed=42)
        m2, _ = direct.train_direct_mlp(X, Y, seed=2026)
        assert not np.allclose(m1.coefs_[0], m2.coefs_[0])


# ── 7. Six-method sample key alignment ─────────────────────────────────

class TestSampleKeyAlignment:
    def test_traditional_methods_use_same_samples(self):
        rows_mle = compare.evaluate_traditional(
            "mle", "MLE", [(1.5, 0.1, 7)], 3, "f1", 42, 1.0)
        rows_lse = compare.evaluate_traditional(
            "lse", "LSE", [(1.5, 0.1, 7)], 3, "f1", 42, 1.0)
        keys_mle = [(r["beta"], r["gamma_over_eta"], r["n"], r["repeat_id"]) for r in rows_mle]
        keys_lse = [(r["beta"], r["gamma_over_eta"], r["n"], r["repeat_id"]) for r in rows_lse]
        assert keys_mle == keys_lse


# ── 8. Failure contract ────────────────────────────────────────────────

class TestFailureContract:
    def test_failed_samples_not_deleted(self):
        rows = compare.evaluate_traditional(
            "mle", "MLE", [(1.5, 0.1, 7)], 5, "f1", 42, 3.0)
        assert len(rows) == 5

    def test_failure_penalty_applied(self):
        rows = [
            {"method": "MLE", "true_loss": 0.1, "failed": False, "failure_reason": "", "failure_penalty": 5.0},
            {"method": "MLE", "true_loss": float("nan"), "failed": True, "failure_reason": "unbounded", "failure_penalty": 5.0},
        ]
        result = compare.apply_failure_contract(rows)
        assert result[1]["true_loss"] == 5.0

    def test_no_silent_deletion(self):
        rows = [
            {"method": "MLE", "true_loss": 0.1, "failed": False, "failure_reason": "", "failure_penalty": 5.0},
            {"method": "MLE", "true_loss": float("nan"), "failed": True, "failure_reason": "fail", "failure_penalty": 5.0},
            {"method": "MLE", "true_loss": 0.2, "failed": False, "failure_reason": "", "failure_penalty": 5.0},
        ]
        result = compare.apply_failure_contract(rows)
        assert len(result) == 3

    def test_zero_penalty_rejected(self):
        """apply_failure_contract must reject penalty=0."""
        rows = [
            {"method": "MLE", "true_loss": 0.1, "failed": False, "failure_reason": "", "failure_penalty": 0.0},
        ]
        with pytest.raises(AssertionError):
            compare.apply_failure_contract(rows)


# ── 9. Model-first aggregation ─────────────────────────────────────────

class TestModelFirstAggregation:
    def test_pooled_j1_is_sqrt_of_mean(self):
        losses = np.array([0.0, 1.0, 4.0])
        assert compare.pooled_j1(losses) == pytest.approx(np.sqrt(5.0 / 3.0))

    def test_learning_method_aggregates_per_model(self):
        rows = [
            {"fold": "f1", "seed": 42, "method": "Direct-MLP", "true_loss": 0.1, "failed": False},
            {"fold": "f1", "seed": 42, "method": "Direct-MLP", "true_loss": 0.4, "failed": False},
            {"fold": "f1", "seed": 2026, "method": "Direct-MLP", "true_loss": 0.2, "failed": False},
            {"fold": "f1", "seed": 2026, "method": "Direct-MLP", "true_loss": 0.2, "failed": False},
        ]
        summary = compare.model_first_summary(rows, "Direct-MLP")
        assert summary["n_models"] == 2
        per_model_j1s = [np.sqrt(0.25), np.sqrt(0.2)]
        assert summary["median_J1"] == pytest.approx(np.median(per_model_j1s))


# ── 10. Production-path regression: run_fair_comparison ────────────────

class TestFairComparisonProduction:
    """Test the full run_fair_comparison driver, not just helper functions."""

    @pytest.fixture
    def mini_setup(self):
        """Build a minimal but complete six-method comparison setup."""
        df_features = _make_mini_features(n_combos=2, repeats=10)
        df_risk = _make_mini_risk_curves(n_combos=2, repeats=10)

        # Train one Direct-MLP model
        folds = e4.get_combo_split()
        # Use first fold for smoke
        fold = folds[0]
        # We'll only use combos that exist in df_features
        train_combos = [(1.5, 0.1, 7)]  # Only one combo in mini data
        test_combos = [(2.0, 0.1, 7)]   # The other combo

        X_train, Y_train, meta = direct.build_training_data(df_features, train_combos)
        model, tscaler = direct.train_direct_mlp(X_train, Y_train, seed=42)

        direct_models = {
            fold["fold_name"]: [(42, model, tscaler, meta["zscore_means"], meta["zscore_stds"])]
        }

        # Build fake Vector-MLP predictions for the same test samples
        mask = df_features.apply(
            lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1
        )
        df_test = df_features[mask]
        vector_preds = pd.DataFrame({
            "beta": df_test["beta"].values,
            "gamma_over_eta": df_test["gamma_over_eta"].values,
            "n": df_test["n"].values,
            "repeat_id": df_test["repeat_id"].values,
            "beta_hat": df_test["beta"].values * 1.05,
            "eta_hat": df_test["eta"].values,
            "gamma_hat": df_test["gamma"].values,
            "failed": [False] * len(df_test),
            "failure_reason": [""] * len(df_test),
        })
        vector_models = {
            fold["fold_name"]: [(42, vector_preds)]
        }

        # Custom fold with our mini combos
        mini_fold = {
            "fold_name": fold["fold_name"],
            "train_combos": train_combos,
            "test_combos": test_combos,
        }

        return {
            "df_features": df_features,
            "df_risk": df_risk,
            "direct_models": direct_models,
            "vector_models": vector_models,
            "folds": [mini_fold],
        }

    def test_all_six_methods_present(self, mini_setup):
        """run_fair_comparison must produce exactly six methods."""
        result = compare.run_fair_comparison(
            df_features=mini_setup["df_features"],
            direct_models=mini_setup["direct_models"],
            vector_models=mini_setup["vector_models"],
            df_risk_curves=mini_setup["df_risk"],
            folds=mini_setup["folds"],
            repeats=10,
        )
        assert len(result["methods_seen"]) == 6
        assert set(result["methods_seen"]) == set(compare.ALL_SIX_METHODS)

    def test_sample_key_alignment_ok(self, mini_setup):
        """All methods must have identical sample keys per fold×seed."""
        result = compare.run_fair_comparison(
            df_features=mini_setup["df_features"],
            direct_models=mini_setup["direct_models"],
            vector_models=mini_setup["vector_models"],
            df_risk_curves=mini_setup["df_risk"],
            folds=mini_setup["folds"],
            repeats=10,
        )
        assert result["sample_key_alignment"]["ok"], result["sample_key_alignment"]

    def test_failure_penalty_nonzero(self, mini_setup):
        """All rows must have failure_penalty > 0."""
        result = compare.run_fair_comparison(
            df_features=mini_setup["df_features"],
            direct_models=mini_setup["direct_models"],
            vector_models=mini_setup["vector_models"],
            df_risk_curves=mini_setup["df_risk"],
            folds=mini_setup["folds"],
            repeats=10,
        )
        df = pd.DataFrame(result["per_sample"])
        assert (df["failure_penalty"] > 0).all()

    def test_tampered_keys_detected(self, mini_setup):
        """Modifying one method's keys must cause alignment failure."""
        result = compare.run_fair_comparison(
            df_features=mini_setup["df_features"],
            direct_models=mini_setup["direct_models"],
            vector_models=mini_setup["vector_models"],
            df_risk_curves=mini_setup["df_risk"],
            folds=mini_setup["folds"],
            repeats=10,
        )
        # Tamper: change a repeat_id to a value not in other methods
        df = pd.DataFrame(result["per_sample"])
        mle_mask = df["method"] == "MLE"
        mle_idx = df[mle_mask].index[0]
        df.loc[mle_idx, "repeat_id"] = 999  # Non-existent repeat_id
        tampered_rows = df.to_dict("records")
        alignment = compare.verify_sample_key_alignment(tampered_rows)
        assert not alignment["ok"], "Tampered keys should be detected"

    def test_missing_model_detected(self, mini_setup):
        """Missing a method must cause assertion failure."""
        with pytest.raises(AssertionError):
            compare.run_fair_comparison(
                df_features=mini_setup["df_features"],
                direct_models={},  # Empty → Direct-MLP missing
                vector_models=mini_setup["vector_models"],
                df_risk_curves=mini_setup["df_risk"],
                folds=mini_setup["folds"],
                repeats=10,
                require_all_six=True,
            )

    def test_empty_vector_models_detected(self, mini_setup):
        """Empty vector_models must cause missing MDM-Vector-MLP."""
        with pytest.raises(AssertionError):
            compare.run_fair_comparison(
                df_features=mini_setup["df_features"],
                direct_models=mini_setup["direct_models"],
                vector_models={},  # Empty
                df_risk_curves=mini_setup["df_risk"],
                folds=mini_setup["folds"],
                repeats=10,
                require_all_six=True,
            )


# ── 11. Config frozen / provenance ─────────────────────────────────────

class TestConfigFrozen:
    def test_config_hash_stable(self):
        assert direct.config_hash() == direct.config_hash()

    def test_production_contract_complete(self):
        c = cfg.production_contract()
        assert c["output_transform"] == "softplus_softplus_relu"
        assert c["target_encoding"] == "inverse_softplus_for_positive_params"
        assert c["hidden_layers"] == (256, 128, 64)
        assert c["seeds"] == [42, 2026, 3407]
        assert "beta" not in c["feature_columns"]

    def test_correction_not_used(self):
        assert cfg.CONFIG_CORRECTION_USED is False


# ── 12. No overwrite of existing artifacts ─────────────────────────────

class TestNoOverwrite:
    def test_p2_v2_manifest_unchanged(self):
        manifest_path = Path(__file__).resolve().parents[1] / (
            "artifacts/formal/extended_validation/p2_generalization_v2/manifest.json"
        )
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert m.get("manifest_version") == "study01-p2-generation-v2"

    def test_e3b_manifest_unchanged(self):
        manifest_path = Path(__file__).resolve().parents[1] / (
            "artifacts/formal/E3b_vector_mlp/manifest.json"
        )
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text(encoding="utf-8"))
            assert m.get("run_id", "").startswith("E3b")
