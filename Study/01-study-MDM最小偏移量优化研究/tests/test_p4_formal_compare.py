"""Fail-closed tests for P4 formal comparison contracts (v3).

Tests cover:
1. Evaluation-layer sample key alignment (cross-type, per-fold)
2. No valid-only survivor filtering (row count contract)
3. Model-first aggregation (15 models, not merged)
4. Failure penalty consistent with J1 formula
5. True params, combo ID, repeat ID do not enter learning input
6. Formal directory not writable when unauthorized
7. Smoke path protection
8. Existing formal artifacts not overwritable
9. Manifest completeness (script SHA256, row contract)
10. Checkpoint drift detection (all fields mandatory)
11. Negative: missing model, fewer samples, duplicates
12. Negative: valid-only filtering detection
13. Negative: seal_outputs fail-closed
14. Negative: checkpoint missing columns
15. Formal entry gate
16. Prediction validity (P4-R7)
17. Two-layer schema (P4-R5)
18. Paired comparison on evaluation layer (P4-R4)
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

CODE_DIR = Path(__file__).resolve().parents[1] / "code"
sys.path.insert(0, str(CODE_DIR))

_PYTHON_DIR = Path(__file__).resolve().parents[3] / "python"
sys.path.insert(0, str(_PYTHON_DIR))

import p4_config as cfg
import run_p4_formal_compare as p4
import run_p3_direct_mlp as direct
import run_p3_fair_compare as compare
import p3_config as p3cfg
import run_E4_formal_validation as e4
from studies.common.sample import generate_sample


# ── Helpers ──────────────────────────────────────────────────────────────

FOLDS = ["combo_fold_1", "combo_fold_2", "combo_fold_3", "combo_fold_4", "combo_fold_5"]
SEEDS = [42, 2026, 3407]


def _make_eval_rows(n_samples=5, methods=None, track="test_track",
                    failed_count=0, failure_penalty=5.0, n_folds=5, n_seeds=3):
    """Make evaluation-layer rows where ALL methods share identical keys.

    Every method gets rows for every (fold, seed, sample) combination.
    This simulates the evaluation layer after traditional broadcast.
    """
    if methods is None:
        methods = cfg.P4_METHODS
    rows = []
    for method in methods:
        for fold_idx in range(n_folds):
            fold = f"combo_fold_{fold_idx + 1}"
            for seed in SEEDS[:n_seeds]:
                for i in range(n_samples):
                    failed = i < failed_count
                    beta_hat = 2.1 + i * 0.01 if not failed else 0.0
                    eta_hat = 1.05 if not failed else 0.0
                    gamma_hat = 0.48 if not failed else 0.0
                    rows.append(p4.make_per_sample_row(
                        track=track, fold=fold, seed=seed, method=method,
                        beta=0.5, goe=0.5, n=10, repeat_id=i,
                        beta_hat=beta_hat, eta_hat=eta_hat, gamma_hat=gamma_hat,
                        beta_true=2.0, eta_true=1.0, gamma_true=0.5,
                        failed=failed, failure_reason="test_fail" if failed else "",
                        failure_penalty=failure_penalty,
                    ))
    return rows


def _make_eval_df(n_samples=5, methods=None, **kwargs):
    rows = _make_eval_rows(n_samples=n_samples, methods=methods, **kwargs)
    rows = p4.apply_failure_contract_p4(rows)
    return pd.DataFrame(rows)


def _make_learning_rows(n_per_model=5, n_folds=5, n_seeds=3,
                        method="Direct-MLP", track="test_track"):
    """Make synthetic learning method rows across 15 models."""
    rows = []
    for fold_idx in range(n_folds):
        for seed in SEEDS[:n_seeds]:
            for i in range(n_per_model):
                rows.append(p4.make_per_sample_row(
                    track=track,
                    fold=f"combo_fold_{fold_idx+1}", seed=seed,
                    method=method,
                    beta=0.5, goe=0.5, n=10, repeat_id=i,
                    beta_hat=2.1 + np.random.randn() * 0.1,
                    eta_hat=1.05 + np.random.randn() * 0.05,
                    gamma_hat=0.48 + np.random.randn() * 0.02,
                    beta_true=2.0, eta_true=1.0, gamma_true=0.5,
                    failed=False, failure_reason="",
                    failure_penalty=5.0,
                ))
    return rows


def _make_test_rows(n=10, track="test_track", method="MLE", fold="combo_fold_1",
                    seed=42, failed_count=0, failure_penalty=5.0):
    """Make synthetic evaluation-layer rows for a single method."""
    rows = []
    for i in range(n):
        failed = i < failed_count
        rows.append(p4.make_per_sample_row(
            track=track, fold=fold, seed=seed, method=method,
            beta=0.5, goe=0.5, n=10, repeat_id=i,
            beta_hat=2.1 + i * 0.01, eta_hat=1.05, gamma_hat=0.48,
            beta_true=2.0, eta_true=1.0, gamma_true=0.5,
            failed=failed, failure_reason="test_fail" if failed else "",
            failure_penalty=failure_penalty,
        ))
    return rows


# ════════════════════════════════════════════════════════════════════════
# 1. Evaluation-layer sample key alignment (P4-R3)
# ════════════════════════════════════════════════════════════════════════

class TestSampleKeyAlignment:
    def test_identical_keys_pass(self):
        """All six methods with identical evaluation-layer keys pass."""
        df = _make_eval_df(n_samples=3)
        result = p4.verify_sample_keys_identical(df, track="test_track")
        assert result["ok"]

    def test_mismatched_keys_detected(self):
        """Different repeat_ids between methods are detected."""
        rows_a = _make_test_rows(n=5, method="MLE")
        rows_b = _make_test_rows(n=5, method="LSE")
        for r in rows_b:
            r["repeat_id"] = r["repeat_id"] + 100
        rows_a = p4.apply_failure_contract_p4(rows_a)
        rows_b = p4.apply_failure_contract_p4(rows_b)
        df = pd.DataFrame(rows_a + rows_b)
        result = p4.verify_sample_keys_identical(df, track="test_track")
        assert not result["ok"]

    def test_cross_type_disjoint_detected(self):
        """Learning and traditional with disjoint sample keys detected."""
        rows_trad = _make_test_rows(n=5, method="MLE", fold="combo_fold_1", seed=42)
        rows_learn = _make_test_rows(n=5, method="Direct-MLP", fold="combo_fold_1", seed=42)
        for r in rows_learn:
            r["repeat_id"] = r["repeat_id"] + 50
        rows_trad = p4.apply_failure_contract_p4(rows_trad)
        rows_learn = p4.apply_failure_contract_p4(rows_learn)
        df = pd.DataFrame(rows_trad + rows_learn)
        result = p4.verify_sample_keys_identical(df, track="test_track")
        assert not result["ok"]

    def test_per_fold_seed_consistency(self):
        """Within a fold, different seeds must have same sample keys."""
        rows = _make_eval_rows(n_samples=3, methods=["Direct-MLP"], n_folds=1, n_seeds=3)
        rows = p4.apply_failure_contract_p4(rows)
        df = pd.DataFrame(rows)
        df.loc[(df["seed"] == 2026) & (df["repeat_id"] == 2), "repeat_id"] = 99
        result = p4.verify_sample_keys_identical(df, track="test_track")
        assert not result["ok"]


# ════════════════════════════════════════════════════════════════════════
# 2. No valid-only survivor filtering
# ════════════════════════════════════════════════════════════════════════

class TestNoValidOnlyFiltering:
    def test_failed_samples_kept(self):
        rows = _make_test_rows(n=10, failed_count=3)
        result = p4.apply_failure_contract_p4(rows)
        assert len(result) == 10
        failed_rows = [r for r in result if r["failed"]]
        assert len(failed_rows) == 3
        for r in failed_rows:
            assert r["true_loss"] == r["failure_penalty"]

    def test_zero_penalty_raises(self):
        rows = _make_test_rows(n=3, failure_penalty=0.0)
        with pytest.raises(direct.PenaltyError):
            p4.apply_failure_contract_p4(rows)

    def test_no_silent_deletion_in_aggregate(self):
        rows = _make_test_rows(n=20, failed_count=5, method="MLE")
        rows = p4.apply_failure_contract_p4(rows)
        df = pd.DataFrame(rows)
        summary = p4.model_first_aggregate(df, "MLE", track="test_track")
        assert summary["n_rows"] == 20
        assert summary["n_failures"] == 5


# ════════════════════════════════════════════════════════════════════════
# 3. Model-first aggregation
# ════════════════════════════════════════════════════════════════════════

class TestModelFirstAggregation:
    def test_learning_method_has_15_models(self):
        rows = _make_learning_rows(n_per_model=5, method="Direct-MLP")
        df = pd.DataFrame(rows)
        assert p4.verify_model_first_not_merged(df, "Direct-MLP")

    def test_model_first_j1_not_merged_j1(self):
        """Model-first J1 differs from pooled-all J1 with varied losses."""
        np.random.seed(42)
        rows = _make_learning_rows(n_per_model=10, method="Direct-MLP")
        rows = p4.apply_failure_contract_p4(rows)
        df = pd.DataFrame(rows)
        summary = p4.model_first_aggregate(df, "Direct-MLP", track="test_track")
        assert summary["n_models"] == 15
        all_losses = df["true_loss"].values.astype(float)
        wrong_j1 = compare.pooled_j1(all_losses)
        assert summary["median_J1"] != pytest.approx(wrong_j1, rel=0.01)

    def test_traditional_single_model_per_fold_seed(self):
        """In evaluation layer, traditional has rows per fold×seed."""
        df = _make_eval_df(n_samples=5, methods=["MLE"])
        summary = p4.model_first_aggregate(df, "MLE", track="test_track")
        assert summary["n_models"] == 15

    def test_pooled_j1_formula(self):
        losses = np.array([0.0, 1.0, 4.0])
        expected = np.sqrt(5.0 / 3.0)
        assert compare.pooled_j1(losses) == pytest.approx(expected)


# ════════════════════════════════════════════════════════════════════════
# 4. Failure penalty consistent with J1
# ════════════════════════════════════════════════════════════════════════

class TestFailurePenaltyJ1Consistency:
    def test_failed_row_uses_penalty_as_loss(self):
        penalty = 7.5
        rows = _make_test_rows(n=5, failed_count=2, failure_penalty=penalty)
        rows = p4.apply_failure_contract_p4(rows)
        for r in rows:
            if r["failed"]:
                assert r["true_loss"] == penalty
            else:
                assert r["true_loss"] == r["true_loss_complete_case"]

    def test_j1_includes_failures(self):
        penalty = 10.0
        rows = _make_test_rows(n=10, failed_count=3, failure_penalty=penalty)
        rows = p4.apply_failure_contract_p4(rows)
        df = pd.DataFrame(rows)
        losses = df["true_loss"].values.astype(float)
        j1 = compare.pooled_j1(losses)
        assert j1 > 0
        non_fail_losses = df[~df["failed"]]["true_loss"].values.astype(float)
        j1_no_fail = compare.pooled_j1(non_fail_losses)
        assert j1 > j1_no_fail


# ════════════════════════════════════════════════════════════════════════
# 5. Forbidden learning inputs
# ════════════════════════════════════════════════════════════════════════

class TestForbiddenLearningInputs:
    def test_no_true_params_in_features(self):
        for col in ["beta", "eta", "gamma", "beta_true", "eta_true", "gamma_true"]:
            assert col not in e4.SAMPLE_FEATURE_COLS

    def test_repeat_id_not_in_features(self):
        assert "repeat_id" not in e4.SAMPLE_FEATURE_COLS

    def test_combo_id_not_in_features(self):
        assert "combo_id" not in e4.SAMPLE_FEATURE_COLS

    def test_p4_per_sample_columns_not_in_features(self):
        for col in ["beta_hat", "eta_hat", "gamma_hat", "true_loss", "failed"]:
            assert col not in e4.SAMPLE_FEATURE_COLS


# ════════════════════════════════════════════════════════════════════════
# 6. Formal directory protection
# ════════════════════════════════════════════════════════════════════════

class TestFormalDirectoryProtection:
    def test_p4_not_authorized(self):
        assert cfg.P4_FORMAL_AUTHORIZED is False

    def test_formal_output_dir_does_not_exist(self):
        assert not cfg.FORMAL_OUTPUT_DIR.exists()

    def test_check_formal_not_authorized_raises_if_true(self):
        import unittest.mock as mock
        with mock.patch.object(cfg, "P4_FORMAL_AUTHORIZED", True):
            with pytest.raises(RuntimeError, match="P4_FORMAL_AUTHORIZED is True"):
                cfg.check_formal_not_authorized()


# ════════════════════════════════════════════════════════════════════════
# 7. Smoke path protection
# ════════════════════════════════════════════════════════════════════════

class TestSmokePathProtection:
    def test_smoke_inside_formal_rejected(self):
        bad = str(cfg.FORMAL_OUTPUT_DIR / "smoke")
        with pytest.raises(RuntimeError):
            cfg.assert_smoke_outside_formal(bad)

    def test_smoke_equals_formal_rejected(self):
        with pytest.raises(RuntimeError):
            cfg.assert_smoke_outside_formal(str(cfg.FORMAL_OUTPUT_DIR))

    def test_smoke_outside_formal_accepted(self):
        cfg.assert_smoke_outside_formal(r"D:\weibull-local-artifacts\smoke")

    def test_smoke_containing_formal_rejected(self):
        bad = str(cfg.FORMAL_OUTPUT_DIR.parent)
        with pytest.raises(RuntimeError):
            cfg.assert_smoke_outside_formal(bad)


# ════════════════════════════════════════════════════════════════════════
# 8. Existing formal artifacts not overwritable
# ════════════════════════════════════════════════════════════════════════

class TestNoOverwriteExisting:
    def test_e3b_manifest_intact(self):
        study_dir = Path(__file__).resolve().parents[1]
        manifest = study_dir / "artifacts" / "formal" / "E3b_vector_mlp" / "manifest.json"
        assert manifest.exists()

    def test_p2_manifest_intact(self):
        study_dir = Path(__file__).resolve().parents[1]
        p2_dir = study_dir / "artifacts" / "formal" / "extended_validation" / "p2_generalization_v2"
        assert p2_dir.exists()

    def test_e3b_risk_curves_intact(self):
        study_dir = Path(__file__).resolve().parents[1]
        rc = study_dir / "artifacts" / "formal" / "E3b_vector_mlp" / "risk_curves.csv"
        assert rc.exists()
        h = p4.compute_sha256(rc)
        assert h == cfg.INPUT_SHA256["E3b_risk_curves_csv"]

    def test_p4_formal_dir_not_created(self):
        assert not cfg.FORMAL_OUTPUT_DIR.exists()


# ════════════════════════════════════════════════════════════════════════
# 9. Manifest completeness
# ════════════════════════════════════════════════════════════════════════

class TestManifestCompleteness:
    def test_manifest_has_required_fields(self):
        manifest = p4.build_manifest(["main_holdout"], cfg.P4_METHODS)
        required = [
            "git_commit", "python_version", "numpy_version", "scipy_version",
            "sklearn_version", "torch_version", "input_sha256", "script_sha256",
            "config_sha256", "row_count_contract", "track_seed_namespaces",
            "mdm_default_delta", "approved_parent_commit",
        ]
        for field in required:
            assert field in manifest, f"missing {field}"

    def test_manifest_p4_not_authorized(self):
        manifest = p4.build_manifest(["main_holdout"], cfg.P4_METHODS)
        assert manifest["p4_formal_authorized"] is False

    def test_manifest_input_sha256_present(self):
        manifest = p4.build_manifest(["main_holdout"], cfg.P4_METHODS)
        assert "E3b_risk_curves_csv" in manifest["input_sha256"]
        assert "E4d_selector_extrapolation_csv" in manifest["input_sha256"]


# ════════════════════════════════════════════════════════════════════════
# 10. Checkpoint drift detection
# ════════════════════════════════════════════════════════════════════════

class TestCheckpointDrift:
    def _make_cp_df(self, commit="abc123", sha="def456", auth=True, script="ghi789"):
        return pd.DataFrame({
            "config_git_commit": [commit],
            "config_input_sha256": [sha],
            "config_p4_authorized": [auth],
            "config_script_sha256": [script],
        })

    def _make_ctx(self, commit="abc123", sha="def456", auth=True, script="ghi789"):
        return {"git_commit": commit, "input_sha256": sha,
                "p4_authorized": auth, "script_sha256": script}

    def test_git_commit_drift_detected(self):
        df = self._make_cp_df(commit="old")
        with pytest.raises(p4.CheckpointDriftError, match="config_git_commit"):
            p4.verify_checkpoint_config(df, self._make_ctx())

    def test_input_hash_drift_detected(self):
        df = self._make_cp_df(sha="old_hash")
        with pytest.raises(p4.CheckpointDriftError, match="config_input_sha256"):
            p4.verify_checkpoint_config(df, self._make_ctx())

    def test_authorized_drift_detected(self):
        df = self._make_cp_df(auth=False)
        with pytest.raises(p4.CheckpointDriftError, match="config_p4_authorized"):
            p4.verify_checkpoint_config(df, self._make_ctx(auth=True))

    def test_script_drift_detected(self):
        df = self._make_cp_df(script="old_script")
        with pytest.raises(p4.CheckpointDriftError, match="config_script_sha256"):
            p4.verify_checkpoint_config(df, self._make_ctx())

    def test_matching_checkpoint_passes(self):
        df = self._make_cp_df()
        assert p4.verify_checkpoint_config(df, self._make_ctx())


# ════════════════════════════════════════════════════════════════════════
# 11. Atomic write and seal
# ════════════════════════════════════════════════════════════════════════

class TestAtomicWrite:
    def test_atomic_csv_write(self, tmp_path):
        df = pd.DataFrame({"a": [1, 2], "b": [3, 4]})
        p4.atomic_write_csv(df, tmp_path / "test.csv")
        assert (tmp_path / "test.csv").exists()
        assert len(pd.read_csv(tmp_path / "test.csv")) == 2

    def test_atomic_json_write(self, tmp_path):
        p4.atomic_write_json({"key": "value"}, tmp_path / "test.json")
        result = json.loads((tmp_path / "test.json").read_text())
        assert result["key"] == "value"

    def test_sha256_seal(self, tmp_path):
        df = pd.DataFrame({"a": [1]})
        p4.atomic_write_csv(df, tmp_path / "f1.csv")
        p4.atomic_write_csv(df, tmp_path / "f2.csv")
        p4.seal_outputs(tmp_path, ["f1.csv", "f2.csv"])
        sums = (tmp_path / "SHA256SUMS").read_text()
        assert "f1.csv" in sums
        assert "f2.csv" in sums


# ════════════════════════════════════════════════════════════════════════
# 12. Paired comparison (P4-R4: evaluation layer)
# ════════════════════════════════════════════════════════════════════════

class TestPairedComparison:
    def test_paired_basic(self):
        df = _make_eval_df(n_samples=5, methods=["MLE", "LSE"])
        result = p4.paired_comparison(df, "MLE", "LSE", track="test_track")
        assert result["n_paired"] == 5 * 15
        assert result["a_wins"] + result["b_wins"] + result["draws"] == result["n_paired"]

    def test_no_common_samples(self):
        rows_a = _make_test_rows(n=5, method="MLE")
        rows_b = _make_test_rows(n=5, method="LSE")
        for r in rows_b:
            r["repeat_id"] += 1000
        rows_a = p4.apply_failure_contract_p4(rows_a)
        rows_b = p4.apply_failure_contract_p4(rows_b)
        df = pd.DataFrame(rows_a + rows_b)
        result = p4.paired_comparison(df, "MLE", "LSE", track="test_track")
        assert "error" in result

    def test_learning_traditional_exact_pairs(self):
        """Learning vs traditional pairing produces exact pair count."""
        df = _make_eval_df(n_samples=3, methods=["Direct-MLP", "MLE"])
        result = p4.paired_comparison(df, "Direct-MLP", "MLE", track="test_track")
        assert result["n_paired"] == 3 * 15


# ════════════════════════════════════════════════════════════════════════
# 13. Negative: model integrity
# ════════════════════════════════════════════════════════════════════════

class TestNegativeModelIntegrity:
    def test_missing_model_detected(self):
        rows = _make_learning_rows(n_per_model=5, method="Direct-MLP")
        df = pd.DataFrame(rows)
        df = df[~((df["fold"] == "combo_fold_5") & (df["seed"] == 3407))]
        assert not p4.verify_model_first_not_merged(df, "Direct-MLP")

    def test_fewer_samples_in_model_detected(self):
        df = _make_eval_df(n_samples=5, methods=["Direct-MLP"])
        mask = (df["fold"] == "combo_fold_1") & (df["seed"] == 42) & (df["repeat_id"] >= 3)
        df = df[~mask]
        result = p4.verify_sample_keys_identical(df, track="test_track")
        assert not result["ok"]

    def test_duplicate_samples_detected(self):
        rows = _make_test_rows(n=5, method="MLE")
        rows.append(rows[0].copy())
        rows = p4.apply_failure_contract_p4(rows)
        df = pd.DataFrame(rows)
        result = p4.verify_sample_keys_identical(df, track="test_track")
        assert not result["ok"]


# ════════════════════════════════════════════════════════════════════════
# 14. Negative: valid-only filtering
# ════════════════════════════════════════════════════════════════════════

class TestNegativeValidOnlyFiltering:
    def test_fewer_rows_raises(self):
        rows = _make_test_rows(n=8, method="MLE")
        rows = p4.apply_failure_contract_p4(rows)
        df = pd.DataFrame(rows)
        with pytest.raises(ValueError, match="valid-only filtering"):
            p4.verify_no_valid_only_filtering(
                df, track="test_track", expected_rows_per_method={"MLE": 10}
            )

    def test_dropped_failures_detected(self):
        rows = _make_test_rows(n=10, failed_count=3, method="MLE")
        rows = p4.apply_failure_contract_p4(rows)
        rows_filtered = [r for r in rows if not r["failed"]]
        df = pd.DataFrame(rows_filtered)
        with pytest.raises(ValueError, match="valid-only filtering"):
            p4.verify_no_valid_only_filtering(
                df, track="test_track", expected_rows_per_method={"MLE": 10}
            )

    def test_bad_penalty_in_failed_row_raises(self):
        rows = _make_test_rows(n=5, failed_count=2, method="MLE")
        rows = p4.apply_failure_contract_p4(rows)
        rows[0]["true_loss"] = 0.0
        df = pd.DataFrame(rows)
        with pytest.raises(ValueError, match="true_loss != failure_penalty"):
            p4.verify_no_valid_only_filtering(df, track="test_track")


# ════════════════════════════════════════════════════════════════════════
# 15. Negative: seal_outputs fail-closed
# ════════════════════════════════════════════════════════════════════════

class TestNegativeSealOutputs:
    def test_missing_file_raises(self, tmp_path):
        df = pd.DataFrame({"a": [1]})
        p4.atomic_write_csv(df, tmp_path / "exists.csv")
        with pytest.raises(FileNotFoundError, match="missing"):
            p4.seal_outputs(tmp_path, ["exists.csv", "does_not_exist.csv"])

    def test_seal_is_atomic(self, tmp_path):
        df = pd.DataFrame({"a": [1]})
        p4.atomic_write_csv(df, tmp_path / "f.csv")
        p4.seal_outputs(tmp_path, ["f.csv"])
        assert (tmp_path / "SHA256SUMS").exists()
        tmps = list(tmp_path.glob("*.tmp.*"))
        assert len(tmps) == 0


# ════════════════════════════════════════════════════════════════════════
# 16. Negative: checkpoint missing columns
# ════════════════════════════════════════════════════════════════════════

class TestNegativeCheckpointMissing:
    def test_missing_git_commit_col_raises(self):
        df = pd.DataFrame({"config_input_sha256": ["a"], "config_p4_authorized": [True],
                           "config_script_sha256": ["b"]})
        ctx = {"git_commit": "x", "input_sha256": "a", "p4_authorized": True, "script_sha256": "b"}
        with pytest.raises(p4.CheckpointDriftError, match="missing required column"):
            p4.verify_checkpoint_config(df, ctx)

    def test_missing_script_sha256_col_raises(self):
        df = pd.DataFrame({"config_git_commit": ["x"], "config_input_sha256": ["a"],
                           "config_p4_authorized": [True]})
        ctx = {"git_commit": "x", "input_sha256": "a", "p4_authorized": True, "script_sha256": "b"}
        with pytest.raises(p4.CheckpointDriftError, match="missing required column"):
            p4.verify_checkpoint_config(df, ctx)


# ════════════════════════════════════════════════════════════════════════
# 17. Formal entry gate
# ════════════════════════════════════════════════════════════════════════

class TestFormalEntryGate:
    def test_assert_formal_authorized_raises_when_false(self):
        assert cfg.P4_FORMAL_AUTHORIZED is False
        with pytest.raises(RuntimeError, match="P4_FORMAL_AUTHORIZED is False"):
            cfg.assert_formal_authorized()

    def test_main_raises_without_authorization(self):
        with pytest.raises(RuntimeError, match="P4_FORMAL_AUTHORIZED is False"):
            p4.main()

    def test_manifest_includes_script_sha256(self):
        manifest = p4.build_manifest(["main_holdout"], cfg.P4_METHODS)
        assert len(manifest["script_sha256"]) == 64

    def test_manifest_includes_row_count_contract(self):
        manifest = p4.build_manifest(["main_holdout"], cfg.P4_METHODS)
        assert "row_count_contract" in manifest
        assert manifest["mdm_default_delta"] == 0.1


# ════════════════════════════════════════════════════════════════════════
# 18. Prediction validity (P4-R7)
# ════════════════════════════════════════════════════════════════════════

class TestPredictionValidity:
    def test_valid_prediction(self):
        ok, reason = p4.check_prediction_validity(2.0, 1.0, 0.5)
        assert ok
        assert reason == ""

    def test_nan_prediction(self):
        ok, reason = p4.check_prediction_validity(float("nan"), 1.0, 0.5)
        assert not ok
        assert "non_finite" in reason

    def test_inf_prediction(self):
        ok, reason = p4.check_prediction_validity(float("inf"), 1.0, 0.5)
        assert not ok
        assert "non_finite" in reason

    def test_negative_beta(self):
        ok, reason = p4.check_prediction_validity(-1.0, 1.0, 0.5)
        assert not ok
        assert "beta" in reason

    def test_zero_eta(self):
        ok, reason = p4.check_prediction_validity(2.0, 0.0, 0.5)
        assert not ok
        assert "eta" in reason

    def test_negative_gamma(self):
        ok, reason = p4.check_prediction_validity(2.0, 1.0, -0.1)
        assert not ok
        assert "gamma" in reason


# ════════════════════════════════════════════════════════════════════════
# 19. Two-layer schema (P4-R5)
# ════════════════════════════════════════════════════════════════════════

class TestTwoLayerSchema:
    def test_estimation_columns_defined(self):
        assert "beta_hat" in p4.ESTIMATION_COLUMNS
        assert "true_loss" not in p4.ESTIMATION_COLUMNS

    def test_evaluation_columns_defined(self):
        assert "true_loss" in p4.EVALUATION_COLUMNS
        assert "failure_penalty" in p4.EVALUATION_COLUMNS

    def test_build_evaluation_layer_broadcasts_traditional(self):
        """Traditional estimation rows are broadcast to all fold×seed contexts."""
        est_rows = []
        for i in range(3):
            est_rows.append(p4.make_estimation_row(
                "test_track", "MLE", cfg.TRADITIONAL_FOLD_LABEL, cfg.TRADITIONAL_SEED_LABEL,
                2.0, 0.5, 10, i, 2.1, 1.05, 0.48, False, ""
            ))
        df_est = pd.DataFrame(est_rows)
        fold_penalties = {"combo_fold_1": 5.0, "combo_fold_2": 6.0}
        df_eval = p4.build_evaluation_layer(df_est, fold_penalties)
        assert len(df_eval) == 3 * 2 * 3
        assert set(df_eval["fold"].unique()) == {"combo_fold_1", "combo_fold_2"}
        assert set(df_eval["seed"].unique()) == set(cfg.SEEDS)

    def test_build_evaluation_layer_learning_keeps_context(self):
        """Learning rows keep their own fold/seed."""
        est_rows = [p4.make_estimation_row(
            "test_track", "Direct-MLP", "combo_fold_1", 42,
            2.0, 0.5, 10, 0, 2.1, 1.05, 0.48, False, ""
        )]
        df_est = pd.DataFrame(est_rows)
        fold_penalties = {"combo_fold_1": 5.0}
        df_eval = p4.build_evaluation_layer(df_est, fold_penalties)
        assert len(df_eval) == 1
        assert df_eval.iloc[0]["fold"] == "combo_fold_1"
        assert df_eval.iloc[0]["seed"] == 42


# ════════════════════════════════════════════════════════════════════════
# 20. Track seed namespaces (P4-R6)
# ════════════════════════════════════════════════════════════════════════

class TestTrackSeedNamespaces:
    def test_main_holdout_namespace(self):
        assert cfg.TRACK_SEED_NAMESPACE[cfg.TRACK_MAIN_HOLDOUT] == "study01_v1"

    def test_param_interp_namespace(self):
        assert cfg.TRACK_SEED_NAMESPACE[cfg.TRACK_PARAM_INTERP] == "study01_p2_v1"

    def test_n_interp_namespace(self):
        assert cfg.TRACK_SEED_NAMESPACE[cfg.TRACK_N_INTERP] == "study01_p2_v1"

    def test_extrap_namespace(self):
        assert cfg.TRACK_SEED_NAMESPACE[cfg.TRACK_EXTRAP] == "study01_v1"

    def test_all_tracks_have_namespace(self):
        for track in cfg.ALL_TRACKS:
            assert track in cfg.TRACK_SEED_NAMESPACE


# ════════════════════════════════════════════════════════════════════════
# 21. Result tables (P4-R9)
# ════════════════════════════════════════════════════════════════════════

class TestResultTables:
    def test_compute_result_tables_structure(self):
        df = _make_eval_df(n_samples=3, methods=["MLE", "LSE"])
        results = p4.compute_result_tables(df, "test_track")
        assert "methods" in results
        assert "MLE" in results["methods"]
        assert "paired_comparisons" in results
        m = results["methods"]["MLE"]
        assert "bias" in m
        assert "rmse" in m
        assert "mae" in m
        assert "loss_quantiles" in m
        assert "failure_rate" in m
        assert "stratification_by_n" in m
        assert "stratification_by_beta" in m

    def test_paired_comparisons_all_pairs(self):
        df = _make_eval_df(n_samples=3, methods=["MLE", "LSE", "WMLE"])
        results = p4.compute_result_tables(df, "test_track")
        pairs = results["paired_comparisons"]
        assert "LSE_vs_MLE" in pairs or "MLE_vs_LSE" in pairs
        assert len(pairs) == 3
