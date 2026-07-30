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
        with pytest.raises(ValueError, match="row count mismatch"):
            p4.verify_no_valid_only_filtering(
                df, track="test_track", expected_rows_per_method={"MLE": 10}
            )

    def test_dropped_failures_detected(self):
        rows = _make_test_rows(n=10, failed_count=3, method="MLE")
        rows = p4.apply_failure_contract_p4(rows)
        rows_filtered = [r for r in rows if not r["failed"]]
        df = pd.DataFrame(rows_filtered)
        with pytest.raises(ValueError, match="row count mismatch"):
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
        assert "complete_case_parametrics" in m
        assert "bias" in m["complete_case_parametrics"]
        assert "rmse" in m["complete_case_parametrics"]
        assert "mae" in m["complete_case_parametrics"]
        assert "loss_quantiles_full_sample" in m
        assert "P95" in m["loss_quantiles_full_sample"]
        assert "P99" in m["loss_quantiles_full_sample"]
        assert "failure_rate" in m
        assert "support_rate" in m
        assert "stratification_by_n" in m
        assert "stratification_by_beta" in m
        assert "stratification_by_gamma_over_eta" in m

    def test_paired_comparisons_all_pairs(self):
        df = _make_eval_df(n_samples=3, methods=["MLE", "LSE", "WMLE"])
        results = p4.compute_result_tables(df, "test_track")
        pairs = results["paired_comparisons"]
        assert "LSE_vs_MLE" in pairs or "MLE_vs_LSE" in pairs
        assert len(pairs) == 3


# ════════════════════════════════════════════════════════════════════════
# 22. Production-path fixture (P4-R10)
# ════════════════════════════════════════════════════════════════════════

class TestProductionPathFixture:
    """Tiny fixture exercising real orchestration with patched compute.

    Patches only at estimator/training boundaries (generate_sample, run_method,
    train_direct_mlp, predict_direct_mlp). Does NOT replace orchestration:
    build_evaluation_layer, verify_*, compute_result_tables, seal, lock all run real.
    """

    def _make_tiny_features(self, n_combos=2, n_repeats=3):
        """Create tiny feature DataFrame mimicking E3b sample_features."""
        rows = []
        combos = [(2.0, 0.5, 10), (3.0, 0.3, 15)][:n_combos]
        for beta, goe, n in combos:
            for rid in range(n_repeats):
                rows.append({
                    "beta": beta, "eta": 1.0, "gamma": goe,
                    "gamma_over_eta": goe, "n": n, "repeat_id": rid,
                    "x_bar": beta * 0.5 + rid * 0.01,
                    "x_min": beta * 0.1, "x_max": beta * 0.9,
                    "x_std": 0.2, "x_cv": 0.3, "x_skew": 0.1,
                    "x_kurt": 2.5, "x_median": beta * 0.45,
                    "x_q25": beta * 0.3, "x_q75": beta * 0.7,
                    "x_iqr": beta * 0.4,
                })
        return pd.DataFrame(rows)

    def _make_tiny_folds(self, n_combos=2):
        combos = [(2.0, 0.5, 10), (3.0, 0.3, 15)][:n_combos]
        return [{
            "fold_name": "combo_fold_1",
            "train_combos": combos[:1],
            "test_combos": combos[1:],
        }]

    def test_evaluation_layer_from_estimation(self):
        """Real build_evaluation_layer with fold_assignment produces correct counts."""
        est_rows = []
        for method in ["MLE", "Direct-MLP"]:
            is_learning = method in cfg.LEARNING_METHODS
            if is_learning:
                for seed in [42]:
                    for i in range(3):
                        est_rows.append(p4.make_estimation_row(
                            "test", method, "combo_fold_1", seed,
                            3.0, 0.3, 15, i, 3.1, 1.0, 0.3, False, ""
                        ))
            else:
                for i in range(3):
                    est_rows.append(p4.make_estimation_row(
                        "test", method, cfg.TRADITIONAL_FOLD_LABEL, cfg.TRADITIONAL_SEED_LABEL,
                        3.0, 0.3, 15, i, 3.1, 1.0, 0.3, False, ""
                    ))

        df_est = pd.DataFrame(est_rows)
        fold_penalties = {"combo_fold_1": 5.0}
        fold_assignment = {(3.0, 0.3, 15, i): "combo_fold_1" for i in range(3)}

        df_eval = p4.build_evaluation_layer(df_est, fold_penalties, fold_assignment=fold_assignment)

        mle_rows = df_eval[df_eval["method"] == "MLE"]
        direct_rows = df_eval[df_eval["method"] == "Direct-MLP"]
        assert len(mle_rows) == 3 * len(cfg.SEEDS)
        assert len(direct_rows) == 3
        assert set(df_eval["fold"].unique()) == {"combo_fold_1"}

    def test_seal_recursive_rejects_extra(self, tmp_path):
        """seal_recursive rejects unexpected files."""
        p4.atomic_write_csv(pd.DataFrame({"a": [1]}), tmp_path / "expected.csv")
        p4.atomic_write_csv(pd.DataFrame({"b": [2]}), tmp_path / "unexpected.csv")
        with pytest.raises(ValueError, match="unexpected"):
            p4.seal_recursive(tmp_path, ["expected.csv"])

    def test_seal_recursive_rejects_missing(self, tmp_path):
        """seal_recursive rejects missing files."""
        p4.atomic_write_csv(pd.DataFrame({"a": [1]}), tmp_path / "exists.csv")
        with pytest.raises(FileNotFoundError, match="missing"):
            p4.seal_recursive(tmp_path, ["exists.csv", "gone.csv"])

    def test_run_lock_atomic_exclusive(self, tmp_path):
        """Second lock acquisition fails atomically."""
        lock1 = p4.acquire_run_lock(tmp_path)
        assert lock1.exists()
        with pytest.raises(RuntimeError, match="lock"):
            p4.acquire_run_lock(tmp_path)
        p4.release_run_lock(tmp_path)
        assert not lock1.exists()

    def test_checkpoint_drift_on_script_hash(self, tmp_path):
        """Checkpoint with different script_sha256 is rejected."""
        df = pd.DataFrame({"x": [1]})
        ctx = {"git_commit": "abc", "input_sha256": "def",
               "p4_authorized": True, "script_sha256": "v1"}
        p4.save_checkpoint(tmp_path, "t", "m", df, ctx)

        loaded = p4.load_checkpoint(tmp_path, "t", "m")
        ctx_drifted = dict(ctx, script_sha256="v2")
        with pytest.raises(p4.CheckpointDriftError, match="config_script_sha256"):
            p4.verify_checkpoint_config(loaded, ctx_drifted)

    def test_full_evaluation_pipeline_tiny(self):
        """End-to-end: estimation → evaluation → verify → result tables → seal."""
        import tempfile
        est_rows = []
        for method in cfg.P4_METHODS:
            is_learning = method in cfg.LEARNING_METHODS
            if is_learning:
                for seed in cfg.SEEDS:
                    for i in range(3):
                        est_rows.append(p4.make_estimation_row(
                            "test", method, "combo_fold_1", seed,
                            3.0, 0.3, 15, i, 3.1, 1.05, 0.31, False, ""
                        ))
            else:
                for i in range(3):
                    est_rows.append(p4.make_estimation_row(
                        "test", method, cfg.TRADITIONAL_FOLD_LABEL, cfg.TRADITIONAL_SEED_LABEL,
                        3.0, 0.3, 15, i, 3.1, 1.05, 0.31, False, ""
                    ))

        df_est = pd.DataFrame(est_rows)
        fold_penalties = {"combo_fold_1": 5.0}
        fold_assignment = {(3.0, 0.3, 15, i): "combo_fold_1" for i in range(3)}

        df_eval = p4.build_evaluation_layer(df_est, fold_penalties, fold_assignment=fold_assignment)

        p4.verify_no_valid_only_filtering(df_eval, track="test")
        key_check = p4.verify_sample_keys_identical(df_eval, track="test")
        assert key_check["ok"], f"Key check failed: {key_check}"

        results = p4.compute_result_tables(df_eval, "test")
        assert len(results["methods"]) == 6
        assert "paired_comparisons" in results

        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            p4.atomic_write_csv(df_eval, td / "eval.csv")
            p4.atomic_write_json(results, td / "results.json")
            seal_hash = p4.seal_outputs(td, ["eval.csv", "results.json"])
            assert len(seal_hash) == 64

    def test_run_traditional_method_patched(self, monkeypatch):
        """run_traditional_method with patched run_method produces valid rows."""
        import unittest.mock as mock

        call_count = [0]
        def fake_run_method(method_id, sample, **kwargs):
            call_count[0] += 1
            return {"beta_hat": 2.1, "eta_hat": 1.05, "gamma_hat": 0.48,
                    "converged": True, "r_squared": 0.99}

        def fake_generate_sample(beta, eta, gamma, n, rid, seed=None):
            return np.sort(np.random.default_rng(rid).weibull(2.0, n))

        monkeypatch.setattr(p4, "run_method", fake_run_method)
        monkeypatch.setattr(p4, "generate_sample", fake_generate_sample)

        samples_df = pd.DataFrame({
            "beta": [2.0, 2.0, 3.0],
            "gamma_over_eta": [0.5, 0.5, 0.3],
            "n": [10, 10, 15],
            "repeat_id": [0, 1, 0],
        })
        rows = p4.run_traditional_method("MLE", samples_df, "test_track", "study01_v1")
        assert len(rows) == 3
        assert call_count[0] == 3
        assert all(r["method"] == "MLE" for r in rows)
        assert all(not r["failed"] for r in rows)
        assert all(r["beta_hat"] == 2.1 for r in rows)

    def test_run_traditional_mdm_default_uses_delta(self, monkeypatch):
        """MDM-Default passes offset=0.1 to run_method."""
        captured_kwargs = []
        def fake_run_method(method_id, sample, **kwargs):
            captured_kwargs.append(kwargs)
            return {"beta_hat": 2.0, "eta_hat": 1.0, "gamma_hat": 0.5,
                    "converged": True}

        def fake_generate_sample(beta, eta, gamma, n, rid, seed=None):
            return np.array([1.0, 2.0, 3.0])

        monkeypatch.setattr(p4, "run_method", fake_run_method)
        monkeypatch.setattr(p4, "generate_sample", fake_generate_sample)

        samples_df = pd.DataFrame({
            "beta": [2.0], "gamma_over_eta": [0.5], "n": [10], "repeat_id": [0],
        })
        p4.run_traditional_method("MDM-Default", samples_df, "test", "study01_v1")
        assert captured_kwargs[0]["offset"] == 0.1

    def test_prediction_validity_in_traditional(self, monkeypatch):
        """Non-finite predictions from run_method are marked failed."""
        def fake_run_method(method_id, sample, **kwargs):
            return {"beta_hat": float("nan"), "eta_hat": 1.0, "gamma_hat": 0.5,
                    "converged": True}

        def fake_generate_sample(beta, eta, gamma, n, rid, seed=None):
            return np.array([1.0, 2.0, 3.0])

        monkeypatch.setattr(p4, "run_method", fake_run_method)
        monkeypatch.setattr(p4, "generate_sample", fake_generate_sample)

        samples_df = pd.DataFrame({
            "beta": [2.0], "gamma_over_eta": [0.5], "n": [10], "repeat_id": [0],
        })
        rows = p4.run_traditional_method("MLE", samples_df, "test", "study01_v1")
        assert rows[0]["failed"] is True
        assert "non_finite" in rows[0]["failure_reason"]

    def test_content_hash_probe(self):
        """verify_sample_content_hash is deterministic and raises on mismatch."""
        h1 = p4.verify_sample_content_hash(2.0, 1.0, 0.5, 10, 0, "study01_v1")
        h2 = p4.verify_sample_content_hash(2.0, 1.0, 0.5, 10, 0, "study01_v1")
        assert h1 == h2
        assert len(h1) == 64

        with pytest.raises(RuntimeError, match="mismatch"):
            p4.verify_sample_content_hash(2.0, 1.0, 0.5, 10, 0, "study01_v1",
                                          expected_sha256="0" * 64)

    def test_content_hash_different_namespace(self):
        """Different namespaces produce different samples."""
        h1 = p4.verify_sample_content_hash(2.0, 1.0, 0.5, 10, 0, "study01_v1")
        h2 = p4.verify_sample_content_hash(2.0, 1.0, 0.5, 10, 0, "study01_p2_v1")
        assert h1 != h2


# ════════════════════════════════════════════════════════════════════════
# 23. Production orchestration test (P4-R10)
# ════════════════════════════════════════════════════════════════════════

class TestProductionOrchestration:
    """Calls real _execute_track_main with patched estimator/training boundaries.

    Does NOT replace orchestration: build_evaluation_layer, verify_*,
    compute_result_tables, seal_recursive, checkpoint all run real.
    """

    def _make_tiny_e3b(self, tmp_path):
        """Create tiny E3b-like fixture files."""
        import hashlib
        combos = [(2.0, 0.5, 10), (3.0, 0.3, 15)]
        feat_rows = []
        risk_rows = []
        for beta, goe, n in combos:
            for rid in range(3):
                sample = generate_sample(beta, 1.0, goe, n, rid, seed="study01_v1")
                feats = e4.compute_sample_features(sample)
                feat_rows.append({"beta": beta, "eta": 1.0, "gamma": goe,
                                  "gamma_over_eta": goe, "n": n, "repeat_id": rid, **feats})
                risk_row = {"beta": beta, "gamma_over_eta": goe, "n": n, "repeat_id": rid}
                for d in e4.DELTA_GRID:
                    risk_row[f"loss_d{d}"] = 0.5 + rid * 0.1
                risk_rows.append(risk_row)

        df_feat = pd.DataFrame(feat_rows)
        df_risk = pd.DataFrame(risk_rows)

        e3b_dir = tmp_path / "E3b_vector_mlp"
        e3b_dir.mkdir(parents=True)
        df_feat.to_csv(e3b_dir / "sample_features.csv", index=False)
        df_risk.to_csv(e3b_dir / "risk_curves.csv", index=False)
        return e3b_dir, df_feat, df_risk

    def _make_tiny_folds(self):
        return [{
            "fold_name": "combo_fold_1",
            "train_combos": [(2.0, 0.5, 10)],
            "test_combos": [(3.0, 0.3, 15)],
        }]

    def test_execute_track_main_orchestration(self, tmp_path, monkeypatch):
        """Real _execute_track_main with patched compute produces all 6 methods."""
        e3b_dir, df_feat, df_risk = self._make_tiny_e3b(tmp_path)
        folds = self._make_tiny_folds()
        seeds = [42]

        monkeypatch.setattr(p4, "compute_sha256", lambda p: "a" * 64)
        monkeypatch.setattr(cfg, "INPUT_SHA256", {
            "E3b_sample_features_csv": "a" * 64,
            "E3b_risk_curves_csv": "a" * 64,
        })

        def fake_train(X, Y, x_bar, seed=42):
            class FakeModel:
                def eval(self): pass
            return FakeModel(), {"n_iter": 1, "x_mean": np.zeros(X.shape[1]),
                                 "x_std": np.ones(X.shape[1]),
                                 "z_mean": np.zeros(3), "z_std": np.ones(3)}

        def fake_predict(model, info, X, x_bar):
            n = X.shape[0]
            return np.column_stack([np.full(n, 2.5), np.full(n, 1.1), np.full(n, 0.4)])

        monkeypatch.setattr(direct, "train_direct_mlp", fake_train)
        monkeypatch.setattr(direct, "predict_direct_mlp", fake_predict)

        def fake_train_mlp(X, Y, seed=42):
            class FakeVec:
                def predict(self, x): return np.zeros((x.shape[0], 26))
            return FakeVec(), None

        monkeypatch.setattr(e4, "_train_mlp", fake_train_mlp)

        def fake_eval_model(model, scaler, df_test, df_loss, means, stds, penalty, fold, seed):
            rows = []
            for _, r in df_test.iterrows():
                rows.append({"beta": r["beta"], "gamma_over_eta": r["gamma_over_eta"],
                             "n": int(r["n"]), "repeat_id": int(r["repeat_id"]),
                             "selected_delta": 0.1, "true_loss": 0.5})
            return rows

        monkeypatch.setattr(e4, "_evaluate_single_model", fake_eval_model)

        fold_penalties = {"combo_fold_1": 2.0}
        run_context = p4.build_run_context("a" * 64)
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        est_rows, fold_assignment = p4._execute_track_main(
            output_dir, folds, seeds, "study01_v1", run_context, e3b_dir, False,
            fold_penalties
        )

        methods_seen = set(r["method"] for r in est_rows)
        assert methods_seen == set(cfg.P4_METHODS), f"Missing methods: {set(cfg.P4_METHODS) - methods_seen}"

        df_est = pd.DataFrame(est_rows, columns=p4.ESTIMATION_COLUMNS)
        df_eval = p4.build_evaluation_layer(df_est, fold_penalties, fold_assignment=fold_assignment, seeds=seeds)

        assert len(df_eval) > 0
        key_check = p4.verify_sample_keys_identical(df_eval, track=cfg.TRACK_MAIN_HOLDOUT)
        assert key_check["ok"], f"Key check failed: {key_check}"

        results = p4.compute_result_tables(df_eval, cfg.TRACK_MAIN_HOLDOUT)
        assert len(results["methods"]) == 6
        assert "paired_comparisons" in results

    def test_authorization_contract_rejects_wrong_output_dir(self):
        """verify_authorization_contract rejects non-standard output_dir."""
        import unittest.mock as mock
        with mock.patch.object(cfg, "P4_FORMAL_AUTHORIZED", True):
            with pytest.raises(RuntimeError, match="output_dir must be"):
                p4.verify_authorization_contract(
                    "/tmp/wrong", cfg.ALL_TRACKS, cfg.SEEDS, False
                )

    def test_authorization_contract_rejects_track_subset(self):
        """verify_authorization_contract rejects track subsets."""
        import unittest.mock as mock
        with mock.patch.object(cfg, "P4_FORMAL_AUTHORIZED", True):
            with pytest.raises(RuntimeError, match="tracks must be"):
                p4.verify_authorization_contract(
                    cfg.FORMAL_OUTPUT_DIR, ["main_holdout"], cfg.SEEDS, False
                )

    def test_authorization_contract_rejects_seed_subset(self):
        """verify_authorization_contract rejects seed subsets."""
        import unittest.mock as mock
        with mock.patch.object(cfg, "P4_FORMAL_AUTHORIZED", True):
            with pytest.raises(RuntimeError, match="seeds must be"):
                p4.verify_authorization_contract(
                    cfg.FORMAL_OUTPUT_DIR, cfg.ALL_TRACKS, [42], False
                )


# ════════════════════════════════════════════════════════════════════════
# 24. P4-R2 negative tests: pre-seal drift detection
# ════════════════════════════════════════════════════════════════════════

class TestPreSealDrift:
    def test_pre_seal_rejects_head_drift(self):
        """verify_pre_seal_state rejects HEAD change."""
        import unittest.mock as mock
        auth = {"script_sha256": "a" * 64, "config_sha256": "b" * 64, "start_head": "original"}
        with mock.patch.object(p4, "get_git_dirty", return_value=False):
            with mock.patch.object(p4, "get_git_commit", return_value="drifted"):
                with pytest.raises(RuntimeError, match="HEAD drifted"):
                    p4.verify_pre_seal_state("/tmp", auth)

    def test_pre_seal_rejects_script_drift(self):
        """verify_pre_seal_state rejects script SHA256 change."""
        import unittest.mock as mock
        auth = {"script_sha256": "a" * 64, "config_sha256": "b" * 64, "start_head": "abc"}
        with mock.patch.object(p4, "get_git_dirty", return_value=False):
            with mock.patch.object(p4, "get_git_commit", return_value="abc"):
                with mock.patch.object(p4, "compute_script_sha256", return_value="x" * 64):
                    with pytest.raises(RuntimeError, match="script SHA256 drifted"):
                        p4.verify_pre_seal_state("/tmp", auth)

    def test_pre_seal_rejects_dirty_worktree(self):
        """verify_pre_seal_state rejects dirty worktree."""
        import unittest.mock as mock
        auth = {"script_sha256": "a" * 64, "config_sha256": "b" * 64, "start_head": "abc"}
        with mock.patch.object(p4, "get_git_dirty", return_value=True):
            with pytest.raises(RuntimeError, match="worktree became dirty"):
                p4.verify_pre_seal_state("/tmp", auth)


# ════════════════════════════════════════════════════════════════════════
# 25. P4-R8 negative tests: resume validation
# ════════════════════════════════════════════════════════════════════════

class TestResumeValidation:
    def test_resume_rejects_git_drift(self, tmp_path):
        """Resume rejects manifest with different git_commit."""
        manifest = {"git_commit": "old", "script_sha256": "a" * 64,
                    "config_sha256": "b" * 64, "tracks": list(cfg.ALL_TRACKS),
                    "seeds": list(cfg.SEEDS), "p4_formal_authorized": True}
        p4.atomic_write_json(manifest, tmp_path / "manifest.json")
        auth = {"start_head": "new", "script_sha256": "a" * 64, "config_sha256": "b" * 64}
        with pytest.raises(RuntimeError, match="git_commit"):
            p4._validate_resume_manifest(tmp_path, auth, cfg.ALL_TRACKS, cfg.SEEDS)

    def test_resume_rejects_script_drift(self, tmp_path):
        """Resume rejects manifest with different script_sha256."""
        manifest = {"git_commit": "abc", "script_sha256": "old" + "x" * 60,
                    "config_sha256": "b" * 64, "tracks": list(cfg.ALL_TRACKS),
                    "seeds": list(cfg.SEEDS), "p4_formal_authorized": True}
        p4.atomic_write_json(manifest, tmp_path / "manifest.json")
        auth = {"start_head": "abc", "script_sha256": "a" * 64, "config_sha256": "b" * 64}
        with pytest.raises(RuntimeError, match="script_sha256"):
            p4._validate_resume_manifest(tmp_path, auth, cfg.ALL_TRACKS, cfg.SEEDS)

    def test_resume_rejects_unauthorized_manifest(self, tmp_path):
        """Resume rejects manifest that was not authorized."""
        manifest = {"git_commit": "abc", "script_sha256": "a" * 64,
                    "config_sha256": "b" * 64, "tracks": list(cfg.ALL_TRACKS),
                    "seeds": list(cfg.SEEDS), "p4_formal_authorized": False}
        p4.atomic_write_json(manifest, tmp_path / "manifest.json")
        auth = {"start_head": "abc", "script_sha256": "a" * 64, "config_sha256": "b" * 64}
        with pytest.raises(RuntimeError, match="not authorized"):
            p4._validate_resume_manifest(tmp_path, auth, cfg.ALL_TRACKS, cfg.SEEDS)

    def test_resume_accepts_valid_manifest(self, tmp_path):
        """Resume accepts manifest matching all bindings."""
        manifest = {"git_commit": "abc", "script_sha256": "a" * 64,
                    "config_sha256": "b" * 64, "tracks": list(cfg.ALL_TRACKS),
                    "seeds": list(cfg.SEEDS), "p4_formal_authorized": True}
        p4.atomic_write_json(manifest, tmp_path / "manifest.json")
        auth = {"start_head": "abc", "script_sha256": "a" * 64, "config_sha256": "b" * 64}
        p4._validate_resume_manifest(tmp_path, auth, cfg.ALL_TRACKS, cfg.SEEDS)


# ════════════════════════════════════════════════════════════════════════
# 26. P4-R10: _run_formal orchestration with patched compute
# ════════════════════════════════════════════════════════════════════════

class TestRunFormalOrchestration:
    """Calls real _run_formal with all four tracks, patched compute boundaries."""

    def _setup_tiny_artifacts(self, tmp_path, monkeypatch):
        """Create tiny artifact files and patch SHA256 checks."""
        e3b_dir = tmp_path / "E3b_vector_mlp"
        e3b_dir.mkdir(parents=True)
        p2_dir = tmp_path / "extended_validation" / "p2_generalization_v2"
        p2_dir.mkdir(parents=True)
        e4_dir = tmp_path / "E4_robustness"
        e4_dir.mkdir(parents=True)

        combos = [(2.0, 0.5, 10), (3.0, 0.3, 15)]
        feat_rows, risk_rows = [], []
        for beta, goe, n in combos:
            for rid in range(2):
                sample = generate_sample(beta, 1.0, goe, n, rid, seed="study01_v1")
                feats = e4.compute_sample_features(sample)
                feat_rows.append({"beta": beta, "eta": 1.0, "gamma": goe,
                                  "gamma_over_eta": goe, "n": n, "repeat_id": rid, **feats})
                risk_row = {"beta": beta, "gamma_over_eta": goe, "n": n, "repeat_id": rid}
                for d in e4.DELTA_GRID:
                    risk_row[f"loss_d{d}"] = 0.5 + rid * 0.1
                risk_rows.append(risk_row)

        pd.DataFrame(feat_rows).to_csv(e3b_dir / "sample_features.csv", index=False)
        pd.DataFrame(risk_rows).to_csv(e3b_dir / "risk_curves.csv", index=False)

        p2_rows = []
        for beta, goe, n in [(1.5, 0.1, 15), (2.5, 0.5, 15)]:
            for rid in range(2):
                p2_rows.append({"track": "P2-NI", "beta": beta, "gamma_over_eta": goe,
                                "n": n, "repeat_id": rid, "sample_sha256": "x" * 64})
        pd.DataFrame(p2_rows).to_csv(p2_dir / "p2_baseline_per_sample.csv", index=False)

        vec_rows = []
        for fold_idx in range(1):
            for seed in [42]:
                for beta, goe, n in [(1.5, 0.1, 15), (2.5, 0.5, 15)]:
                    for rid in range(2):
                        vec_rows.append({"track": "P2-NI", "fold": f"combo_fold_{fold_idx+1}",
                                         "seed": seed, "beta": beta, "gamma_over_eta": goe,
                                         "n": n, "repeat_id": rid, "selected_delta": 0.1})
        pd.DataFrame(vec_rows).to_csv(p2_dir / "p2_vector_per_sample.csv", index=False)

        e4d_rows = []
        for fold_idx in range(1):
            for seed in [42]:
                for beta, goe, n in [(6.0, 0.05, 5), (0.8, 1.5, 30)]:
                    for rid in range(2):
                        e4d_rows.append({"track": "E4c_offgrid", "fold": f"combo_fold_{fold_idx+1}",
                                         "seed": seed, "beta": beta, "gamma_over_eta": goe,
                                         "n": n, "repeat_id": rid, "selected_delta": 0.2})
        pd.DataFrame(e4d_rows).to_csv(e4_dir / "E4d_selector_extrapolation.csv", index=False)

        monkeypatch.setattr(p4, "compute_sha256", lambda p: "f" * 64)
        monkeypatch.setattr(cfg, "INPUT_SHA256", {k: "f" * 64 for k in cfg.INPUT_SHA256})

        return tmp_path

    def test_run_formal_all_tracks(self, tmp_path, monkeypatch):
        """_run_formal executes all 4 tracks with patched track execution, real seal."""
        import unittest.mock as mock

        folds = [{"fold_name": "combo_fold_1",
                  "train_combos": [(2.0, 0.5, 10)],
                  "test_combos": [(3.0, 0.3, 15)]}]

        def make_tiny_track_est(track, methods=None):
            if methods is None:
                methods = cfg.P4_METHODS
            rows = []
            for method in methods:
                is_learning = method in cfg.LEARNING_METHODS
                if is_learning:
                    for seed in [42]:
                        for i in range(2):
                            rows.append(p4.make_estimation_row(
                                track, method, "combo_fold_1", seed,
                                3.0, 0.3, 15, i, 3.1, 1.05, 0.31, False, ""))
                else:
                    for i in range(2):
                        rows.append(p4.make_estimation_row(
                            track, method, cfg.TRADITIONAL_FOLD_LABEL, cfg.TRADITIONAL_SEED_LABEL,
                            3.0, 0.3, 15, i, 3.1, 1.05, 0.31, False, ""))
            return rows

        fold_assignment = {(3.0, 0.3, 15, i): "combo_fold_1" for i in range(2)}

        monkeypatch.setattr(e4, "get_combo_split", lambda: folds)
        monkeypatch.setattr(p4, "_compute_frozen_fold_penalties", lambda *a: {"combo_fold_1": 2.0})
        monkeypatch.setattr(p4, "_execute_track_main",
                            lambda *a, **kw: (make_tiny_track_est(cfg.TRACK_MAIN_HOLDOUT), fold_assignment))
        monkeypatch.setattr(p4, "_execute_track_p2",
                            lambda *a, **kw: (make_tiny_track_est(a[5] if len(a) > 5 else cfg.TRACK_PARAM_INTERP), None))
        monkeypatch.setattr(p4, "_execute_track_extrap",
                            lambda *a, **kw: (make_tiny_track_est(cfg.TRACK_EXTRAP), None))
        monkeypatch.setattr(p4, "verify_pre_seal_state", lambda *a, **kw: None)
        monkeypatch.setattr(p4, "verify_no_valid_only_filtering", lambda *a, **kw: True)
        monkeypatch.setattr(p4, "verify_sample_keys_identical", lambda *a, **kw: {"ok": True})

        output_dir = tmp_path / "formal_output"
        output_dir.mkdir(parents=True)
        auth_hashes = {"script_sha256": "f" * 64, "config_sha256": "f" * 64, "start_head": "abc"}

        p4._run_formal(output_dir, cfg.ALL_TRACKS, [42], False, auth_hashes)

        assert (output_dir / "manifest.json").exists()
        assert (output_dir / "evaluation_all.csv").exists()
        assert (output_dir / "result_tables.json").exists()
        assert (output_dir / "SHA256SUMS").exists()
        for track in cfg.ALL_TRACKS:
            assert (output_dir / track / "estimation.csv").exists()
            assert (output_dir / track / "evaluation.csv").exists()
            assert (output_dir / track / "results.json").exists()

        sums = (output_dir / "SHA256SUMS").read_text()
        assert "manifest.json" in sums
        assert "evaluation_all.csv" in sums

        results = json.loads((output_dir / "result_tables.json").read_text())
        assert len(results) == 4
        for track in cfg.ALL_TRACKS:
            assert track in results
            assert len(results[track]["methods"]) == 6

    def test_seal_recursive_rejects_stale_lock(self, tmp_path):
        """seal_recursive rejects unexpected .lock files that aren't run.lock."""
        p4.atomic_write_csv(pd.DataFrame({"a": [1]}), tmp_path / "data.csv")
        (tmp_path / "stale.lock").write_text("stale")
        with pytest.raises(ValueError, match="unexpected"):
            p4.seal_recursive(tmp_path, ["data.csv"])


# ════════════════════════════════════════════════════════════════════════
# 27. P4-R6 negative: partial hash rejection
# ════════════════════════════════════════════════════════════════════════

class TestP2HashStrictness:
    def test_rejects_missing_hash(self):
        """_verify_p2_sample_hashes raises if any key lacks a valid SHA256."""
        df = pd.DataFrame({
            "beta": [2.0, 3.0],
            "gamma_over_eta": [0.5, 0.3],
            "n": [10, 15],
            "repeat_id": [0, 0],
            "sample_sha256": [None, None],
        })
        with pytest.raises(RuntimeError, match="missing valid SHA256"):
            p4._verify_p2_sample_hashes(df, "study01_p2_v1")

    def test_rejects_nan_hash(self):
        """_verify_p2_sample_hashes raises on nan hash values."""
        df = pd.DataFrame({
            "beta": [2.0],
            "gamma_over_eta": [0.5],
            "n": [10],
            "repeat_id": [0],
            "sample_sha256": [float("nan")],
        })
        with pytest.raises(RuntimeError, match="missing valid SHA256"):
            p4._verify_p2_sample_hashes(df, "study01_p2_v1")

    def test_rejects_short_hash(self):
        """_verify_p2_sample_hashes raises on non-64-char hash."""
        df = pd.DataFrame({
            "beta": [2.0],
            "gamma_over_eta": [0.5],
            "n": [10],
            "repeat_id": [0],
            "sample_sha256": ["abc123"],
        })
        with pytest.raises(RuntimeError, match="missing valid SHA256"):
            p4._verify_p2_sample_hashes(df, "study01_p2_v1")


# ════════════════════════════════════════════════════════════════════════
# 28. P4-R8 negative: resume rejects unknown files
# ════════════════════════════════════════════════════════════════════════

class TestResumeUnknownFiles:
    def test_resume_rejects_unknown_file(self, tmp_path):
        """Resume rejects unknown files beside the manifest."""
        manifest = {"git_commit": "abc", "script_sha256": "a" * 64,
                    "config_sha256": "b" * 64, "tracks": list(cfg.ALL_TRACKS),
                    "seeds": list(cfg.SEEDS), "p4_formal_authorized": True,
                    "approved_parent_commit": "parent1"}
        p4.atomic_write_json(manifest, tmp_path / "manifest.json")
        (tmp_path / "unknown.bin").write_text("junk")
        auth = {"start_head": "abc", "script_sha256": "a" * 64,
                "config_sha256": "b" * 64, "approved_parent_commit": "parent1"}
        with pytest.raises(RuntimeError, match="unknown file"):
            p4._validate_resume_manifest(tmp_path, auth, cfg.ALL_TRACKS, cfg.SEEDS)

    def test_resume_accepts_checkpoint_files(self, tmp_path):
        """Resume accepts checkpoint_ files as valid partial state."""
        manifest = {"git_commit": "abc", "script_sha256": "a" * 64,
                    "config_sha256": "b" * 64, "tracks": list(cfg.ALL_TRACKS),
                    "seeds": list(cfg.SEEDS), "p4_formal_authorized": True,
                    "approved_parent_commit": "parent1"}
        p4.atomic_write_json(manifest, tmp_path / "manifest.json")
        (tmp_path / "checkpoint_main_holdout_Direct-MLP.csv").write_text("data")
        auth = {"start_head": "abc", "script_sha256": "a" * 64,
                "config_sha256": "b" * 64, "approved_parent_commit": "parent1"}
        result = p4._validate_resume_manifest(tmp_path, auth, cfg.ALL_TRACKS, cfg.SEEDS)
        assert len(result) == 64

    def test_resume_rejects_approved_parent_drift(self, tmp_path):
        """Resume rejects manifest with different approved_parent_commit."""
        manifest = {"git_commit": "abc", "script_sha256": "a" * 64,
                    "config_sha256": "b" * 64, "tracks": list(cfg.ALL_TRACKS),
                    "seeds": list(cfg.SEEDS), "p4_formal_authorized": True,
                    "approved_parent_commit": "old_parent"}
        p4.atomic_write_json(manifest, tmp_path / "manifest.json")
        auth = {"start_head": "abc", "script_sha256": "a" * 64,
                "config_sha256": "b" * 64, "approved_parent_commit": "new_parent"}
        with pytest.raises(RuntimeError, match="approved_parent_commit"):
            p4._validate_resume_manifest(tmp_path, auth, cfg.ALL_TRACKS, cfg.SEEDS)

    def test_resume_rejects_nested_unknown_file(self, tmp_path):
        """Resume rejects unknown files inside track subdirectories."""
        manifest = {"git_commit": "abc", "script_sha256": "a" * 64,
                    "config_sha256": "b" * 64, "tracks": list(cfg.ALL_TRACKS),
                    "seeds": list(cfg.SEEDS), "p4_formal_authorized": True,
                    "approved_parent_commit": "parent1"}
        p4.atomic_write_json(manifest, tmp_path / "manifest.json")
        track_dir = tmp_path / "param_interp"
        track_dir.mkdir()
        (track_dir / "unknown.bin").write_text("junk")
        auth = {"start_head": "abc", "script_sha256": "a" * 64,
                "config_sha256": "b" * 64, "approved_parent_commit": "parent1"}
        with pytest.raises(RuntimeError, match="unknown file in track dir"):
            p4._validate_resume_manifest(tmp_path, auth, cfg.ALL_TRACKS, cfg.SEEDS)


# ════════════════════════════════════════════════════════════════════════
# 29. P4-R6 negative: duplicate hash inconsistency + missing column
# ════════════════════════════════════════════════════════════════════════

class TestP2HashDuplicateAndColumn:
    def test_rejects_inconsistent_duplicate_hash(self):
        """Same key with different hashes across rows raises."""
        h1 = p4.verify_sample_content_hash(2.0, 1.0, 0.5, 10, 0, "study01_p2_v1")
        df = pd.DataFrame({
            "beta": [2.0, 2.0],
            "gamma_over_eta": [0.5, 0.5],
            "n": [10, 10],
            "repeat_id": [0, 0],
            "sample_sha256": [h1, "b" * 64],
        })
        with pytest.raises(RuntimeError, match="inconsistent"):
            p4._verify_p2_sample_hashes(df, "study01_p2_v1")

    def test_rejects_missing_column(self):
        """Raises if sample_sha256 column is absent."""
        df = pd.DataFrame({
            "beta": [2.0],
            "gamma_over_eta": [0.5],
            "n": [10],
            "repeat_id": [0],
        })
        with pytest.raises(RuntimeError, match="column missing"):
            p4._verify_p2_sample_hashes(df, "study01_p2_v1")

    def test_rejects_wrong_key_count(self):
        """Raises if verified count doesn't match expected_key_count."""
        h1 = p4.verify_sample_content_hash(2.0, 1.0, 0.5, 10, 0, "study01_p2_v1")
        df = pd.DataFrame({
            "beta": [2.0],
            "gamma_over_eta": [0.5],
            "n": [10],
            "repeat_id": [0],
            "sample_sha256": [h1],
        })
        with pytest.raises(RuntimeError, match="expected"):
            p4._verify_p2_sample_hashes(df, "study01_p2_v1", expected_key_count=99)
