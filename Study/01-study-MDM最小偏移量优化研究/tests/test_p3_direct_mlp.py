"""Fail-closed tests for P3 Direct-MLP v4 (full scale invariance).

Tests:
- Production feature path: same sample * c → identical 13-dim network input
- End-to-end model scale equivariance (not just decoder)
- Shared j1_loss_torch with gamma=0 and non-unit eta
- Strict Vector-MLP schema (missing eta/gamma → error)
- Explicit exceptions instead of assert
- Six-method fold×seed coverage
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

CODE_DIR = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIR))

_PYTHON_DIR = Path(__file__).resolve().parents[3] / "python"
sys.path.insert(0, str(_PYTHON_DIR))

import p3_config as cfg
import run_p3_direct_mlp as direct
import run_p3_fair_compare as compare
import run_E4_formal_validation as e4
from studies.common.sample import generate_sample


def _make_mini_features(n_combos=2, repeats=5):
    rows = []
    for beta in [1.5, 2.0][:n_combos]:
        for rid in range(repeats):
            sample = generate_sample(beta, 1.0, beta * 0.1, 7, rid, seed="study01_v1")
            feats = e4.compute_sample_features(sample)
            rows.append({"beta": beta, "eta": 1.0, "gamma": beta * 0.1,
                         "gamma_over_eta": 0.1, "n": 7, "repeat_id": rid, **feats})
    return pd.DataFrame(rows)


def _make_mini_risk_curves(n_combos=2, repeats=5):
    rows = []
    for beta in [1.5, 2.0][:n_combos]:
        for rid in range(repeats):
            row = {"beta": beta, "gamma_over_eta": 0.1, "n": 7, "repeat_id": rid}
            for d in range(0, 52, 2):
                row[f"loss_d{d/100:.2f}"] = 0.5 + abs(d/100 - 0.1) * 2
            rows.append(row)
    return pd.DataFrame(rows)


# ── 1. Full scale invariance: production feature path ──────────────────

class TestScaleInvariantFeatures:
    def test_scale_invariant_transform_divides_by_xbar(self):
        """After transform, all 9 scale cols should be divided by x_bar."""
        df = _make_mini_features(1, 3)
        df_si = direct.make_scale_invariant(df)
        # x_bar should be 1.0 after transform
        assert np.allclose(df_si["x_bar"].values, 1.0)
        # x_min should be x_min/x_bar
        assert np.allclose(df_si["x_min"].values, df["x_min"].values / df["x_bar"].values)
        # s should be s/x_bar
        assert np.allclose(df_si["s"].values, df["s"].values / df["x_bar"].values)

    def test_scale_invariant_features_unchanged(self):
        """n, CV, g1, g2 should be unchanged by the transform."""
        df = _make_mini_features(1, 3)
        df_si = direct.make_scale_invariant(df)
        for col in ["n", "CV", "g1", "g2"]:
            assert np.allclose(df_si[col].values, df[col].values)

    def test_production_input_scale_invariance(self):
        """Same sample * c → identical 13-dim network input.

        This tests the FULL feature pipeline, not just the decoder.
        """
        df = _make_mini_features(1, 5)
        df_si = direct.make_scale_invariant(df)
        means, stds = direct.fit_scale_invariant_zscore(df_si)
        ok = direct.verify_input_scale_invariance(df, means, stds, scale_factor=2.5)
        assert ok, "Network input changed when sample was scaled by 2.5"

    def test_production_input_scale_invariance_multiple_factors(self):
        """Test with multiple scale factors including fractional."""
        df = _make_mini_features(1, 5)
        df_si = direct.make_scale_invariant(df)
        means, stds = direct.fit_scale_invariant_zscore(df_si)
        for c in [0.5, 1.0, 3.7, 100.0, 0.01]:
            ok = direct.verify_input_scale_invariance(df, means, stds, scale_factor=c)
            assert ok, f"Network input changed when sample was scaled by {c}"

    def test_end_to_end_model_scale_equivariance(self):
        """Trained model: scale sample by c → beta unchanged, eta/gamma * c.

        This uses a REAL trained model, not just decode_output.
        """
        df = _make_mini_features(2, 20)
        X, Y, x_bar, meta = direct.build_training_data(df, [(1.5, 0.1, 7)])
        model, info = direct.train_direct_mlp(X, Y, x_bar, seed=42, max_iter=5)

        # Original sample
        df_test = df[df.apply(
            lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) == (2.0, 0.1, 7), axis=1
        )].head(5)
        df_test_si = direct.make_scale_invariant(df_test)
        X_orig = direct.build_scale_invariant_X(df_test_si, meta["zscore_means"], meta["zscore_stds"])
        x_bar_orig = df_test["x_bar"].values.astype(np.float64)
        preds_orig = direct.predict_direct_mlp(model, info, X_orig, x_bar_orig)

        # Scaled sample (multiply all scale-dependent features by c)
        c = 3.0
        df_scaled = df_test.copy()
        for col in direct.SCALE_DEPENDENT_COLS:
            df_scaled[col] = df_scaled[col].astype(float) * c
        df_scaled_si = direct.make_scale_invariant(df_scaled)
        X_scaled = direct.build_scale_invariant_X(df_scaled_si, meta["zscore_means"], meta["zscore_stds"])
        x_bar_scaled = df_scaled["x_bar"].values.astype(np.float64)
        preds_scaled = direct.predict_direct_mlp(model, info, X_scaled, x_bar_scaled)

        # Network input must be identical
        assert np.allclose(X_orig, X_scaled, atol=1e-6), \
            "Network input differs between original and scaled samples"

        # Predictions must satisfy scale equivariance
        assert direct.verify_scale_equivariance(preds_orig, preds_scaled, c, atol=1e-4), \
            "Model predictions do not satisfy scale equivariance"


# ── 2. Output transforms ───────────────────────────────────────────────

class TestOutputConstraints:
    def test_beta_positive(self):
        z = np.array([[-100, 1.0, 0.5]])
        p = direct.decode_output(z, np.array([1.0]))
        assert p[0, 0] > 0

    def test_eta_positive(self):
        z = np.array([[1.0, -100, 0.5]])
        p = direct.decode_output(z, np.array([1.0]))
        assert p[0, 1] > 0

    def test_gamma_nonneg(self):
        z = np.array([[1.0, 1.0, -100]])
        p = direct.decode_output(z, np.array([1.0]))
        assert p[0, 2] >= 0

    def test_gamma_zero(self):
        """gamma=0 should produce gamma_hat=0 when goe_hat=0."""
        z = np.array([[1.0, 1.0, 0.0]])
        p = direct.decode_output(z, np.array([1.0]))
        assert p[0, 2] == pytest.approx(0.0)


class TestEncodeDecode:
    def test_roundtrip_unit_eta(self):
        params = np.array([[2.0, 1.0, 0.5]])
        x_bar = np.array([1.0])
        z = direct.encode_targets(params, x_bar)
        decoded = direct.decode_output(z, x_bar)
        assert np.allclose(decoded, params, atol=1e-5)

    def test_roundtrip_nonunit_eta(self):
        params = np.array([[2.5, 3.0, 1.5]])
        x_bar = np.array([3.0])
        z = direct.encode_targets(params, x_bar)
        decoded = direct.decode_output(z, x_bar)
        assert np.allclose(decoded, params, atol=1e-5)

    def test_roundtrip_gamma_zero(self):
        """gamma=0 must round-trip correctly."""
        params = np.array([[2.0, 1.0, 0.0]])
        x_bar = np.array([1.0])
        z = direct.encode_targets(params, x_bar)
        decoded = direct.decode_output(z, x_bar)
        assert np.allclose(decoded, params, atol=1e-5)

    def test_same_shape_different_scale_same_target(self):
        """Same shape params at different scales → same network target."""
        p1 = np.array([[2.0, 1.0, 0.5]])
        p2 = np.array([[2.0, 5.0, 2.5]])
        z1 = direct.encode_targets(p1, np.array([1.0]))
        z2 = direct.encode_targets(p2, np.array([5.0]))
        assert np.allclose(z1, z2, atol=1e-5)


# ── 3. Shared J1 loss ──────────────────────────────────────────────────

class TestSharedJ1Loss:
    def test_zero_loss_perfect_prediction(self):
        bh = torch.tensor([2.0]); b = torch.tensor([2.0])
        eh = torch.tensor([1.0]); e = torch.tensor([1.0])
        gh = torch.tensor([0.5]); g = torch.tensor([0.5])
        loss = direct.j1_loss_torch(bh, b, eh, e, gh, g)
        assert loss.item() == pytest.approx(0.0, abs=1e-12)

    def test_gamma_zero_loss_finite(self):
        """gamma=0: loss must be finite."""
        bh = torch.tensor([2.0]); b = torch.tensor([2.0])
        eh = torch.tensor([1.0]); e = torch.tensor([1.0])
        gh = torch.tensor([0.1]); g = torch.tensor([0.0])
        loss = direct.j1_loss_torch(bh, b, eh, e, gh, g)
        assert torch.isfinite(loss)
        # gamma error = (0.1 - 0.0) / eta(1.0) = 0.1
        assert loss.item() == pytest.approx(0.01)

    def test_nonunit_eta_gamma_denominator(self):
        """gamma error normalized by eta_true, not gamma_true."""
        bh = torch.tensor([2.0]); b = torch.tensor([2.0])
        eh = torch.tensor([3.0]); e = torch.tensor([3.0])
        gh = torch.tensor([2.0]); g = torch.tensor([1.5])
        loss = direct.j1_loss_torch(bh, b, eh, e, gh, g)
        e_gamma = (2.0 - 1.5) / 3.0  # denominator = eta_true = 3.0
        assert loss.item() == pytest.approx(e_gamma ** 2)

    def test_matches_compute_param_loss(self):
        """j1_loss_torch must produce same result as compute_param_loss."""
        bh, b = 2.2, 2.0
        eh, e = 1.5, 1.0
        gh, g = 0.8, 0.5

        torch_loss = direct.j1_loss_torch(
            torch.tensor([bh]), torch.tensor([b]),
            torch.tensor([eh]), torch.tensor([e]),
            torch.tensor([gh]), torch.tensor([g]),
        ).item()

        np_loss = direct.compute_param_loss(bh, b, eh, e, gh, g)

        assert torch_loss == pytest.approx(np_loss)

    def test_training_and_validation_use_same_loss(self):
        """Both train and val code paths call j1_loss_torch."""
        import inspect
        src = inspect.getsource(direct.train_direct_mlp)
        train_calls = src.count("j1_loss_torch(")
        assert train_calls >= 2, "Both training and validation must call j1_loss_torch"


# ── 4. Forbidden fields ────────────────────────────────────────────────

class TestForbiddenFields:
    def test_no_forbidden_in_features(self):
        feats = set(e4.SAMPLE_FEATURE_COLS)
        for f in cfg.FORBIDDEN_INPUT_FIELDS:
            assert f not in feats

    def test_x_bar_is_feature_not_forbidden(self):
        assert "x_bar" in e4.SAMPLE_FEATURE_COLS
        assert "x_bar" not in cfg.FORBIDDEN_INPUT_FIELDS


# ── 5. Fold/scaler isolation ───────────────────────────────────────────

class TestFoldIsolation:
    def test_train_excludes_test(self):
        for fold in e4.get_combo_split():
            assert set(fold["train_combos"]).isdisjoint(fold["test_combos"])

    def test_uses_scale_invariant_pipeline(self):
        """build_training_data must use scale-invariant transform."""
        import inspect
        src = inspect.getsource(direct.build_training_data)
        assert "make_scale_invariant" in src
        assert "fit_scale_invariant_zscore" in src
        assert "build_scale_invariant_X" in src


# ── 6. Seed reproducibility ────────────────────────────────────────────

class TestSeedReproducibility:
    def test_same_seed_same_model(self):
        df = _make_mini_features(1, 30)
        X, Y, x_bar, _ = direct.build_training_data(df, [(1.5, 0.1, 7)])
        m1, _ = direct.train_direct_mlp(X, Y, x_bar, seed=42, max_iter=10)
        m2, _ = direct.train_direct_mlp(X, Y, x_bar, seed=42, max_iter=10)
        for k1, k2 in zip(m1.state_dict().keys(), m2.state_dict().keys()):
            np.testing.assert_array_equal(
                m1.state_dict()[k1].numpy(), m2.state_dict()[k2].numpy()
            )

    def test_different_seed_different_model(self):
        df = _make_mini_features(1, 30)
        X, Y, x_bar, _ = direct.build_training_data(df, [(1.5, 0.1, 7)])
        m1, _ = direct.train_direct_mlp(X, Y, x_bar, seed=42, max_iter=10)
        m2, _ = direct.train_direct_mlp(X, Y, x_bar, seed=2026, max_iter=10)
        w1 = m1.state_dict()["net.0.weight"].numpy()
        w2 = m2.state_dict()["net.0.weight"].numpy()
        assert not np.allclose(w1, w2)


# ── 7. P99 penalty from ALL 26 deltas ──────────────────────────────────

class TestFoldPenalty:
    def test_uses_all_26_deltas(self):
        df_features = _make_mini_features(1, 5)
        df_risk = _make_mini_risk_curves(1, 5)
        penalty = direct.compute_fold_penalty(df_features, df_risk, [(1.5, 0.1, 7)])
        assert penalty > 0
        all_losses = []
        for _, row in df_risk.iterrows():
            for d in range(0, 52, 2):
                all_losses.append(float(row[f"loss_d{d/100:.2f}"]))
        expected_p99 = float(np.percentile(all_losses, 99))
        assert penalty == pytest.approx(expected_p99)

    def test_no_fallback_raises_penalty_error(self):
        """Must raise PenaltyError (not ValueError) if no valid losses."""
        df_features = _make_mini_features(1, 5)
        df_risk = pd.DataFrame(columns=["beta", "gamma_over_eta", "n", "repeat_id"] +
                               [f"loss_d{d/100:.2f}" for d in range(0, 52, 2)])
        with pytest.raises(direct.PenaltyError):
            direct.compute_fold_penalty(df_features, df_risk, [(1.5, 0.1, 7)])

    def test_wrong_loss_count_raises_schema_error(self):
        """Wrong number of loss_d columns must raise SchemaError."""
        df_features = _make_mini_features(1, 5)
        # Only 13 loss columns instead of 26
        df_risk = pd.DataFrame(columns=["beta", "gamma_over_eta", "n", "repeat_id"] +
                               [f"loss_d{d/100:.2f}" for d in range(0, 26, 2)])
        with pytest.raises(direct.SchemaError):
            direct.compute_fold_penalty(df_features, df_risk, [(1.5, 0.1, 7)])


# ── 8. Failure contract ────────────────────────────────────────────────

class TestFailureContract:
    def test_no_silent_deletion(self):
        rows = [
            {"method": "MLE", "true_loss": 0.1, "failed": False, "failure_reason": "", "failure_penalty": 5.0},
            {"method": "MLE", "true_loss": float("nan"), "failed": True, "failure_reason": "fail", "failure_penalty": 5.0},
        ]
        result = compare.apply_failure_contract(rows)
        assert len(result) == 2
        assert result[1]["true_loss"] == 5.0

    def test_zero_penalty_raises_penalty_error(self):
        """Must raise PenaltyError, not AssertionError."""
        rows = [{"method": "MLE", "true_loss": 0.1, "failed": False, "failure_reason": "", "failure_penalty": 0.0}]
        with pytest.raises(direct.PenaltyError):
            compare.apply_failure_contract(rows)


# ── 9. Model-first aggregation ─────────────────────────────────────────

class TestModelFirstAggregation:
    def test_pooled_j1_sqrt_mean(self):
        assert compare.pooled_j1(np.array([0.0, 1.0, 4.0])) == pytest.approx(np.sqrt(5/3))


# ── 10. Vector-MLP strict schema ───────────────────────────────────────

class TestVectorMLPSchema:
    def test_missing_eta_raises_schema_error(self):
        """Missing eta column must raise SchemaError."""
        df = pd.DataFrame({
            "beta": [2.0], "gamma": [0.5], "gamma_over_eta": [0.1],
            "n": [7], "repeat_id": [0],
            "beta_hat": [2.1], "eta_hat": [1.0], "gamma_hat": [0.5],
            "failed": [False], "failure_reason": [""],
        })
        with pytest.raises(direct.SchemaError, match="eta"):
            compare.validate_vector_pred_schema(df, "fold1", 42)

    def test_missing_gamma_raises_schema_error(self):
        """Missing gamma column must raise SchemaError."""
        df = pd.DataFrame({
            "beta": [2.0], "eta": [1.0], "gamma_over_eta": [0.1],
            "n": [7], "repeat_id": [0],
            "beta_hat": [2.1], "eta_hat": [1.0], "gamma_hat": [0.5],
            "failed": [False], "failure_reason": [""],
        })
        with pytest.raises(direct.SchemaError, match="gamma"):
            compare.validate_vector_pred_schema(df, "fold1", 42)

    def test_empty_raises_schema_error(self):
        with pytest.raises(direct.SchemaError):
            compare.validate_vector_pred_schema(pd.DataFrame(), "fold1", 42)

    def test_valid_schema_passes(self):
        df = pd.DataFrame({
            "beta": [2.0], "eta": [1.0], "gamma": [0.5], "gamma_over_eta": [0.1],
            "n": [7], "repeat_id": [0],
            "beta_hat": [2.1], "eta_hat": [1.0], "gamma_hat": [0.5],
            "failed": [False], "failure_reason": [""],
        })
        compare.validate_vector_pred_schema(df, "fold1", 42)  # should not raise


# ── 11. Six-method fold×seed coverage (explicit exceptions) ────────────

class TestFairComparisonProduction:
    @pytest.fixture
    def mini_setup(self):
        df_features = _make_mini_features(2, 10)
        df_risk = _make_mini_risk_curves(2, 10)
        folds = e4.get_combo_split()
        fold = folds[0]
        train_combos = [(1.5, 0.1, 7)]
        test_combos = [(2.0, 0.1, 7)]

        X, Y, x_bar, meta = direct.build_training_data(df_features, train_combos)
        model, info = direct.train_direct_mlp(X, Y, x_bar, seed=42, max_iter=10)

        direct_models = {fold["fold_name"]: {42: (model, info, meta["zscore_means"], meta["zscore_stds"])}}

        test_mask = df_features.apply(
            lambda r: (r["beta"], r["gamma_over_eta"], r["n"]) in test_combos, axis=1
        )
        df_test = df_features[test_mask]
        vector_preds = pd.DataFrame({
            "beta": df_test["beta"].values,
            "eta": df_test["eta"].values,
            "gamma": df_test["gamma"].values,
            "gamma_over_eta": df_test["gamma_over_eta"].values,
            "n": df_test["n"].values,
            "repeat_id": df_test["repeat_id"].values,
            "beta_hat": df_test["beta"].values * 1.05,
            "eta_hat": df_test["eta"].values,
            "gamma_hat": df_test["gamma"].values,
            "failed": [False] * len(df_test),
            "failure_reason": [""] * len(df_test),
        })
        vector_models = {fold["fold_name"]: {42: vector_preds}}
        mini_fold = {"fold_name": fold["fold_name"], "train_combos": train_combos, "test_combos": test_combos}

        return {
            "df_features": df_features, "df_risk": df_risk,
            "direct_models": direct_models, "vector_models": vector_models,
            "folds": [mini_fold],
        }

    def test_all_six_methods_present(self, mini_setup):
        result = compare.run_fair_comparison(
            df_features=mini_setup["df_features"],
            direct_models=mini_setup["direct_models"],
            vector_models=mini_setup["vector_models"],
            df_risk_curves=mini_setup["df_risk"],
            folds=mini_setup["folds"], repeats=10, seeds=[42],
        )
        assert len(result["methods_seen"]) == 6
        assert set(result["methods_seen"]) == set(compare.ALL_SIX_METHODS)

    def test_alignment_ok(self, mini_setup):
        result = compare.run_fair_comparison(
            df_features=mini_setup["df_features"],
            direct_models=mini_setup["direct_models"],
            vector_models=mini_setup["vector_models"],
            df_risk_curves=mini_setup["df_risk"],
            folds=mini_setup["folds"], repeats=10, seeds=[42],
        )
        assert result["sample_key_alignment"]["ok"]

    def test_tampered_keys_detected(self, mini_setup):
        result = compare.run_fair_comparison(
            df_features=mini_setup["df_features"],
            direct_models=mini_setup["direct_models"],
            vector_models=mini_setup["vector_models"],
            df_risk_curves=mini_setup["df_risk"],
            folds=mini_setup["folds"], repeats=10, seeds=[42],
        )
        df = pd.DataFrame(result["per_sample"])
        mle_idx = df[df["method"] == "MLE"].index[0]
        df.loc[mle_idx, "repeat_id"] = 999
        alignment = compare.verify_sample_key_alignment(df.to_dict("records"))
        assert not alignment["ok"]

    def test_missing_direct_raises_coverage_error(self, mini_setup):
        """Must raise CoverageError, not AssertionError."""
        with pytest.raises(direct.CoverageError):
            compare.run_fair_comparison(
                df_features=mini_setup["df_features"],
                direct_models={},
                vector_models=mini_setup["vector_models"],
                df_risk_curves=mini_setup["df_risk"],
                folds=mini_setup["folds"], repeats=10, seeds=[42],
            )

    def test_empty_vector_raises_coverage_error(self, mini_setup):
        with pytest.raises(direct.CoverageError):
            compare.run_fair_comparison(
                df_features=mini_setup["df_features"],
                direct_models=mini_setup["direct_models"],
                vector_models={},
                df_risk_curves=mini_setup["df_risk"],
                folds=mini_setup["folds"], repeats=10, seeds=[42],
            )

    def test_coverage_gap_raises_coverage_error(self, mini_setup):
        """3 seeds requested but models for 1 → CoverageError."""
        with pytest.raises(direct.CoverageError):
            compare.run_fair_comparison(
                df_features=mini_setup["df_features"],
                direct_models=mini_setup["direct_models"],
                vector_models=mini_setup["vector_models"],
                df_risk_curves=mini_setup["df_risk"],
                folds=mini_setup["folds"], repeats=10,
                seeds=[42, 2026, 3407],
            )

    def test_vector_missing_eta_raises_schema_error(self, mini_setup):
        """Vector-MLP predictions missing eta → SchemaError during comparison."""
        # Remove eta from vector predictions
        vm = mini_setup["vector_models"]
        for fold_name in vm:
            for seed in vm[fold_name]:
                vm[fold_name][seed] = vm[fold_name][seed].drop(columns=["eta"])
        with pytest.raises(direct.SchemaError):
            compare.run_fair_comparison(
                df_features=mini_setup["df_features"],
                direct_models=mini_setup["direct_models"],
                vector_models=vm,
                df_risk_curves=mini_setup["df_risk"],
                folds=mini_setup["folds"], repeats=10, seeds=[42],
            )


# ── 12. Config ─────────────────────────────────────────────────────────

class TestConfigFrozen:
    def test_hash_stable(self):
        assert direct.config_hash() == direct.config_hash()

    def test_contract_has_scale_invariance(self):
        c = cfg.production_contract()
        assert c["input_scale_invariance"] == "divide_by_x_bar_before_zscore"
        assert "x_bar" in c["scale_dependent_features"]
        assert "n" in c["scale_invariant_features"]
        assert c["output_transform"] == "scale_equivariant_softplus_softplus_relu"
        assert c["training_framework"] == "pytorch"

    def test_correction_not_used(self):
        assert cfg.CONFIG_CORRECTION_USED is False


# ── 13. No overwrite ───────────────────────────────────────────────────

class TestNoOverwrite:
    def test_p2_v2_manifest(self):
        p = Path(__file__).resolve().parents[1] / "artifacts/formal/extended_validation/p2_generalization_v2/manifest.json"
        if p.exists():
            m = json.loads(p.read_text(encoding="utf-8"))
            assert m.get("manifest_version") == "study01-p2-generation-v2"

    def test_e3b_manifest(self):
        p = Path(__file__).resolve().parents[1] / "artifacts/formal/E3b_vector_mlp/manifest.json"
        if p.exists():
            m = json.loads(p.read_text(encoding="utf-8"))
            assert m.get("run_id", "").startswith("E3b")
