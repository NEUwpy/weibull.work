"""Fail-closed tests for P3 Direct-MLP v3.

Tests the hardest issues:
- Scale equivariance: scaling sample scales eta/gamma correctly
- J1-compatible loss: training loss weights match J1 formula
- P99 penalty from ALL 26 deltas (not just delta=0.1)
- Six-method fold×seed coverage (detects baseline 3-seed vs learning 1-seed)
- Production-path run_fair_comparison with tamper detection
- Perfect decode round-trip for non-unit eta
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


# ── 1. Scale equivariance ──────────────────────────────────────────────

class TestScaleEquivariance:
    def test_decode_scales_eta_by_x_bar(self):
        """eta_hat = eta_ratio * x_bar, so doubling x_bar doubles eta_hat."""
        z = np.array([[2.0, 1.0, 0.5]])
        x_bar1 = np.array([1.0])
        x_bar2 = np.array([2.0])
        p1 = direct.decode_output(z, x_bar1)
        p2 = direct.decode_output(z, x_bar2)
        assert p2[0, 1] == pytest.approx(2 * p1[0, 1])  # eta doubled
        assert p2[0, 0] == pytest.approx(p1[0, 0])      # beta unchanged
        assert p2[0, 2] == pytest.approx(2 * p1[0, 2])  # gamma doubled (goe*eta)

    def test_encode_decode_roundtrip_unit_eta(self):
        params = np.array([[2.0, 1.0, 0.5]])
        x_bar = np.array([1.0])
        z = direct.encode_targets(params, x_bar)
        decoded = direct.decode_output(z, x_bar)
        assert np.allclose(decoded, params, atol=1e-5)

    def test_encode_decode_roundtrip_nonunit_eta(self):
        """Non-unit eta must round-trip correctly."""
        params = np.array([[2.5, 3.0, 1.5]])
        x_bar = np.array([3.0])  # eta/x_bar = 1.0
        z = direct.encode_targets(params, x_bar)
        decoded = direct.decode_output(z, x_bar)
        assert np.allclose(decoded, params, atol=1e-5)

    def test_encode_decode_roundtrip_different_scales(self):
        """Same shape params at different eta scales must produce different targets."""
        p1 = np.array([[2.0, 1.0, 0.5]])  # eta=1
        p2 = np.array([[2.0, 5.0, 2.5]])  # eta=5, same beta/goe
        x_bar1 = np.array([1.0])
        x_bar2 = np.array([5.0])  # scaled
        z1 = direct.encode_targets(p1, x_bar1)
        z2 = direct.encode_targets(p2, x_bar2)
        # z_beta should be same (shape param)
        assert np.allclose(z1[0, 0], z2[0, 0], atol=1e-5)
        # z_eta_ratio should be same (eta/x_bar = 1.0 in both cases)
        assert np.allclose(z1[0, 1], z2[0, 1], atol=1e-5)
        # z_goe should be same (gamma/eta = 0.5 in both cases)
        assert np.allclose(z1[0, 2], z2[0, 2], atol=1e-5)

    def test_scale_equivariance_verification(self):
        """verify_scale_equivariance detects correct scaling."""
        preds1 = np.array([[2.0, 1.0, 0.5]])
        preds2 = np.array([[2.0, 2.0, 1.0]])  # eta*2, gamma*2, beta same
        assert direct.verify_scale_equivariance(preds1, preds2, 2.0)


# ── 2. Output constraints ──────────────────────────────────────────────

class TestOutputConstraints:
    def test_beta_positive(self):
        z = np.array([[-100, 1.0, 0.5]])
        x_bar = np.array([1.0])
        p = direct.decode_output(z, x_bar)
        assert p[0, 0] > 0

    def test_eta_positive(self):
        z = np.array([[1.0, -100, 0.5]])
        x_bar = np.array([1.0])
        p = direct.decode_output(z, x_bar)
        assert p[0, 1] > 0

    def test_gamma_nonneg(self):
        z = np.array([[1.0, 1.0, -100]])
        x_bar = np.array([1.0])
        p = direct.decode_output(z, x_bar)
        assert p[0, 2] >= 0


# ── 3. Forbidden fields ────────────────────────────────────────────────

class TestForbiddenFields:
    def test_no_forbidden_in_features(self):
        feats = set(e4.SAMPLE_FEATURE_COLS)
        for f in cfg.FORBIDDEN_INPUT_FIELDS:
            assert f not in feats

    def test_x_bar_is_feature_not_forbidden(self):
        """x_bar IS a feature (used as scale anchor) and must not be forbidden."""
        assert "x_bar" in e4.SAMPLE_FEATURE_COLS
        assert "x_bar" not in cfg.FORBIDDEN_INPUT_FIELDS


# ── 4. J1-compatible loss ──────────────────────────────────────────────

class TestJ1CompatibleLoss:
    def test_zero_loss_for_perfect_prediction(self):
        loss = direct.compute_param_loss(2.0, 2.0, 1.0, 1.0, 0.5, 0.5)
        assert loss == pytest.approx(0.0, abs=1e-12)

    def test_matches_j1_squared(self):
        loss = direct.compute_param_loss(2.5, 2.0, 1.5, 1.0, 0.8, 0.5)
        e_b = (2.5-2.0)/2.0
        e_e = (1.5-1.0)/1.0
        e_g = (0.8-0.5)/1.0
        assert loss == pytest.approx(e_b**2 + e_e**2 + e_g**2)

    def test_gamma_normalized_by_eta(self):
        loss = direct.compute_param_loss(2.0, 2.0, 1.0, 1.0, 1.5, 1.0)
        assert loss == pytest.approx(0.5**2)

    def test_nonunit_eta_gamma_normalization(self):
        """For eta=3, gamma error normalized by eta."""
        loss = direct.compute_param_loss(2.0, 2.0, 3.0, 3.0, 2.0, 1.5)
        e_g = (2.0 - 1.5) / 3.0
        assert loss == pytest.approx(e_g**2)

    def test_training_loss_weights_match_j1(self):
        """Numerically verify: same param errors produce same loss weights as J1."""
        # Three different param errors
        errors = [
            (2.2, 2.0, 1.1, 1.0, 0.6, 0.5),  # e_b=0.1, e_e=0.1, e_g=0.1/0.5=0.2
            (3.0, 2.0, 1.5, 1.0, 0.7, 0.5),  # different errors
        ]
        for bh, b, eh, e, gh, g in errors:
            loss = direct.compute_param_loss(bh, b, eh, e, gh, g)
            e_b = (bh - b) / b
            e_e = (eh - e) / e
            e_g = (gh - g) / e
            j1_sq = e_b**2 + e_e**2 + e_g**2
            assert loss == pytest.approx(j1_sq), \
                f"Loss {loss} != J1² {j1_sq} for params ({bh},{b},{eh},{e},{gh},{g})"


# ── 5. Fold/scaler isolation ───────────────────────────────────────────

class TestFoldIsolation:
    def test_train_excludes_test(self):
        for fold in e4.get_combo_split():
            assert set(fold["train_combos"]).isdisjoint(fold["test_combos"])

    def test_no_inline_duplication(self):
        import inspect
        src = inspect.getsource(direct.build_training_data)
        assert "e4._fit_zscore_params" in src
        assert "e4._build_X_from_samples" in src


# ── 6. Seed reproducibility ────────────────────────────────────────────

class TestSeedReproducibility:
    def test_same_seed_same_model(self):
        df = _make_mini_features(n_combos=1, repeats=30)
        X, Y, x_bar, _ = direct.build_training_data(df, [(1.5, 0.1, 7)])
        m1, i1 = direct.train_direct_mlp(X, Y, x_bar, seed=42, max_iter=10)
        m2, i2 = direct.train_direct_mlp(X, Y, x_bar, seed=42, max_iter=10)
        for k1, k2 in zip(m1.state_dict().keys(), m2.state_dict().keys()):
            np.testing.assert_array_equal(
                m1.state_dict()[k1].numpy(), m2.state_dict()[k2].numpy()
            )

    def test_different_seed_different_model(self):
        df = _make_mini_features(n_combos=1, repeats=30)
        X, Y, x_bar, _ = direct.build_training_data(df, [(1.5, 0.1, 7)])
        m1, _ = direct.train_direct_mlp(X, Y, x_bar, seed=42, max_iter=10)
        m2, _ = direct.train_direct_mlp(X, Y, x_bar, seed=2026, max_iter=10)
        w1 = m1.state_dict()["net.0.weight"].numpy()
        w2 = m2.state_dict()["net.0.weight"].numpy()
        assert not np.allclose(w1, w2)


# ── 7. P99 penalty from ALL 26 deltas ──────────────────────────────────

class TestFoldPenalty:
    def test_uses_all_26_deltas(self):
        """Penalty must use all 26 delta points, not just delta=0.1."""
        df_features = _make_mini_features(1, 5)
        df_risk = _make_mini_risk_curves(1, 5)
        penalty = direct.compute_fold_penalty(df_features, df_risk, [(1.5, 0.1, 7)])
        # With 5 samples × 26 deltas = 130 losses, P99 should be a high value
        assert penalty > 0
        # Verify it's the P99 of ALL losses, not just delta=0.1
        all_losses = []
        for _, row in df_risk.iterrows():
            for d in range(0, 52, 2):
                all_losses.append(float(row[f"loss_d{d/100:.2f}"]))
        expected_p99 = float(np.percentile(all_losses, 99))
        assert penalty == pytest.approx(expected_p99)

    def test_no_fallback_to_3(self):
        """Must raise ValueError if no valid training losses, not fall back to 3.0."""
        df_features = _make_mini_features(1, 5)
        # Empty risk curves → no matches
        df_risk = pd.DataFrame(columns=["beta", "gamma_over_eta", "n", "repeat_id"] +
                               [f"loss_d{d/100:.2f}" for d in range(0, 52, 2)])
        with pytest.raises(ValueError):
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

    def test_zero_penalty_rejected(self):
        rows = [{"method": "MLE", "true_loss": 0.1, "failed": False, "failure_reason": "", "failure_penalty": 0.0}]
        with pytest.raises(AssertionError):
            compare.apply_failure_contract(rows)


# ── 9. Model-first aggregation ─────────────────────────────────────────

class TestModelFirstAggregation:
    def test_pooled_j1_sqrt_mean(self):
        assert compare.pooled_j1(np.array([0.0, 1.0, 4.0])) == pytest.approx(np.sqrt(5/3))


# ── 10. Six-method fold×seed coverage ──────────────────────────────────

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
            "gamma_over_eta": df_test["gamma_over_eta"].values,
            "n": df_test["n"].values,
            "repeat_id": df_test["repeat_id"].values,
            "eta": df_test["eta"].values,
            "gamma": df_test["gamma"].values,
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
            folds=mini_setup["folds"], repeats=10,
            seeds=[42],
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

    def test_penalty_nonzero(self, mini_setup):
        result = compare.run_fair_comparison(
            df_features=mini_setup["df_features"],
            direct_models=mini_setup["direct_models"],
            vector_models=mini_setup["vector_models"],
            df_risk_curves=mini_setup["df_risk"],
            folds=mini_setup["folds"], repeats=10, seeds=[42],
        )
        df = pd.DataFrame(result["per_sample"])
        assert (df["failure_penalty"] > 0).all()

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

    def test_missing_direct_model_detected(self, mini_setup):
        with pytest.raises(AssertionError):
            compare.run_fair_comparison(
                df_features=mini_setup["df_features"],
                direct_models={},
                vector_models=mini_setup["vector_models"],
                df_risk_curves=mini_setup["df_risk"],
                folds=mini_setup["folds"], repeats=10, seeds=[42],
            )

    def test_empty_vector_detected(self, mini_setup):
        with pytest.raises(AssertionError):
            compare.run_fair_comparison(
                df_features=mini_setup["df_features"],
                direct_models=mini_setup["direct_models"],
                vector_models={},
                df_risk_curves=mini_setup["df_risk"],
                folds=mini_setup["folds"], repeats=10, seeds=[42],
            )

    def test_coverage_gap_detected(self, mini_setup):
        """If traditional methods run 3 seeds but learning methods only 1,
        the coverage check must catch it."""
        # Request 3 seeds but only provide models for 1
        with pytest.raises(AssertionError) as exc_info:
            compare.run_fair_comparison(
                df_features=mini_setup["df_features"],
                direct_models=mini_setup["direct_models"],
                vector_models=mini_setup["vector_models"],
                df_risk_curves=mini_setup["df_risk"],
                folds=mini_setup["folds"], repeats=10,
                seeds=[42, 2026, 3407],  # 3 seeds requested
            )
        assert "coverage" in str(exc_info.value).lower() or "missing" in str(exc_info.value).lower()


# ── 11. Config ─────────────────────────────────────────────────────────

class TestConfigFrozen:
    def test_hash_stable(self):
        assert direct.config_hash() == direct.config_hash()

    def test_contract_complete(self):
        c = cfg.production_contract()
        assert c["output_transform"] == "scale_equivariant_softplus_softplus_relu"
        assert c["target_encoding"] == "inverse_softplus_scale_equivariant"
        assert c["training_loss"] == "J1_compatible_relative_error"
        assert c["training_framework"] == "pytorch"
        assert c["scale_anchor"] == "x_bar"

    def test_correction_not_used(self):
        assert cfg.CONFIG_CORRECTION_USED is False


# ── 12. No overwrite ───────────────────────────────────────────────────

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
