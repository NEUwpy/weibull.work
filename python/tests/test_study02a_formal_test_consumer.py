"""Tests for the one-shot test evaluation consumer (formal_test_consumer.py).

Uses synthetic test namespaces with reduced sizes; never reads real formal test data.
"""

import hashlib
import json
import math
from pathlib import Path
import sys

import numpy as np
import pytest
import torch

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CODE = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code"
for _p in (str(STUDY_CODE), str(REPO_ROOT / "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from study02a.formal_state import authorize_test_once, consume_test_once, initialize_formal_state, publish_oracle_approval
from study02a.formal_test_consumer import (
    ModuleTestSpec,
    _apply_scaler_to_test_batch,
    _build_test_batch,
    _canonical,
    _publish_no_replace,
    _sha256_bytes,
    build_module_test_spec,
    consume_test_evaluation,
)

COMMIT = "ab" * 20
CONFIG_SHA = "cd" * 32
BUNDLE_SHA_PLACEHOLDER = "ef" * 32


def _canonical_bytes(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode()


def _setup_run_dir(tmp_path, *, state="unsealed_once", with_checkpoint=True, corrupt_checkpoint=False):
    """Build a minimal synthetic run directory with state machine in the requested state."""
    run_dir = tmp_path / "A-E1" / "run-test"
    run_dir.mkdir(parents=True)

    ceiling = run_dir / "ceiling_hit_report.json"
    leakage = run_dir / "leakage_audit.json"
    oracle_review = run_dir / "oracle_review.json"
    ceiling.write_bytes(_canonical_bytes({"report": "ceiling", "test_access_count": 0}))
    leakage.write_bytes(_canonical_bytes({"audit": "leakage", "test_access_count": 0}))
    oracle_review.write_bytes(_canonical_bytes({"review": "oracle"}))

    bundle = {
        "bundle_version": "study02-pre-unseal-v3",
        "code_commit": COMMIT,
        "effective_config_sha256": CONFIG_SHA,
        "module_run_ids": {"A-E1": "run-test"},
        "selection_trace_hashes": {"A-E1": "dd" * 32},
        "artifact_hashes": {
            str(ceiling): hashlib.sha256(ceiling.read_bytes()).hexdigest(),
            str(leakage): hashlib.sha256(leakage.read_bytes()).hexdigest(),
        },
        "test_state": "sealed",
    }
    bundle_path = run_dir / "pre_unseal_bundle.json"
    bundle_path.write_bytes(_canonical_bytes(bundle))
    bundle_sha = hashlib.sha256(bundle_path.read_bytes()).hexdigest()

    approval = {
        "approval_version": "study02-test-unseal-approval-v1",
        "decision": "APPROVE test unseal",
        "code_commit": COMMIT,
        "effective_config_sha256": CONFIG_SHA,
        "pre_unseal_bundle_sha256": bundle_sha,
        "selection_trace_hashes": {"A-E1": "dd" * 32},
        "ceiling_report_sha256": hashlib.sha256(ceiling.read_bytes()).hexdigest(),
        "leakage_audit_sha256": hashlib.sha256(leakage.read_bytes()).hexdigest(),
        "oracle_review_artifact_sha256": hashlib.sha256(oracle_review.read_bytes()).hexdigest(),
        "issued_at": "2026-07-25T10:00:00Z",
    }
    approval_path = run_dir / "oracle_approval.json"
    approval_path.write_bytes(_canonical_bytes(approval))

    plan_row = {
        "fit_id": "winner-001",
        "run_id": "run-test",
        "module": "A-E1",
        "route": "F2",
        "n_mode": "fixed_n",
        "fixed_n": 7,
        "n": 7,
        "architecture": "m4_64_32",
        "optimizer": "adamw_1e3",
        "loss": "mse",
        "seed": 420101,
        "training_size": 7000,
        "training_rows": 7000,
        "fit_kind": "stage1",
    }
    plan_path = run_dir / "plan.jsonl"
    plan_path.write_text(json.dumps(plan_row) + "\n", encoding="utf-8")

    if with_checkpoint:
        output_dir = run_dir / "outputs" / "winner-001"
        output_dir.mkdir(parents=True)
        checkpoint_path = output_dir / "checkpoint.pt"
        if corrupt_checkpoint:
            checkpoint_path.write_bytes(b"corrupt-not-a-checkpoint")
        else:
            from study02a.models import build_mlp
            model = build_mlp(15, (64, 32), "relu", 0.0)
            from study02a.training import _checkpoint_canonical_bytes
            checkpoint_path.write_bytes(_checkpoint_canonical_bytes(model.state_dict()))

    state_path = run_dir / "formal_state.json"
    ledger_path = run_dir / "transition_ledger.jsonl"

    initialize_formal_state(
        state_path=state_path, bundle_path=bundle_path, run_family_id="G3-test",
        code_commit=COMMIT, effective_config_sha256=CONFIG_SHA,
        timestamp="2026-07-25T09:00:00Z",
    )

    if state in ("unsealed_once", "consumed"):
        authorize_test_once(
            state_path=state_path, bundle_path=bundle_path, approval_path=approval_path,
            ledger_path=ledger_path, timestamp="2026-07-25T09:30:00Z",
            ceiling_report_path=ceiling, leakage_audit_path=leakage,
            oracle_review_path=oracle_review,
        )

    if state == "consumed":
        receipt = {"receipt_version": "study02-test-result-v1", "dummy": True}
        receipt_sha = hashlib.sha256(_canonical_bytes(receipt)).hexdigest()
        consume_test_once(
            state_path=state_path, bundle_path=bundle_path, approval_path=approval_path,
            ledger_path=ledger_path, result_receipt_sha256=receipt_sha,
            failure_receipt_sha256=None, timestamp="2026-07-25T09:45:00Z",
            ceiling_report_path=ceiling, leakage_audit_path=leakage,
            oracle_review_path=oracle_review,
        )

    return run_dir


class TestModuleTestSpec:
    def test_valid_spec(self, tmp_path):
        from study02a.config import load_frozen_config
        study_root = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
        frozen = load_frozen_config(study_root)
        spec = build_module_test_spec(
            module_id="A-E1", route="F2", n_mode="fixed_n", fixed_n=7,
            frozen_config=frozen, _point_count=4, _repeat_count=2,
        )
        assert spec.design_namespace == 220301
        assert spec.sample_namespace == 320301
        assert spec.point_count == 4
        assert spec.repeat_count == 2

    def test_unknown_module_rejected(self, tmp_path):
        from study02a.config import load_frozen_config
        study_root = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
        frozen = load_frozen_config(study_root)
        with pytest.raises(ValueError, match="no frozen test design namespace"):
            build_module_test_spec(
                module_id="INVALID", route="F2", n_mode="fixed_n", fixed_n=7,
                frozen_config=frozen,
            )

    def test_fixed_n_requires_value(self):
        with pytest.raises(ValueError, match="fixed_n mode requires"):
            ModuleTestSpec(
                module_id="A-E1", route="F2", n_mode="fixed_n", fixed_n=None,
                point_count=4, repeat_count=2,
                design_namespace=220301, sample_namespace=320301,
            )

    def test_shared_n_rejects_fixed_n(self):
        with pytest.raises(ValueError, match="shared_n mode cannot"):
            ModuleTestSpec(
                module_id="A-E1", route="S", n_mode="shared_n", fixed_n=7,
                point_count=4, repeat_count=2,
                design_namespace=220301, sample_namespace=320301,
            )


class TestBuildTestBatch:
    def test_builds_correct_row_count(self):
        from study02a.config import load_frozen_config
        study_root = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
        frozen = load_frozen_config(study_root)
        spec = build_module_test_spec(
            module_id="A-E1", route="F2", n_mode="fixed_n", fixed_n=7,
            frozen_config=frozen, _point_count=4, _repeat_count=2,
        )
        batch, metadata = _build_test_batch(spec, frozen)
        assert len(metadata) == 4 * 2
        assert batch.features.shape[0] == 8
        assert batch.targets.shape == (8, 3)

    def test_shared_n_multiplies_by_core_n(self):
        from study02a.config import load_frozen_config
        study_root = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
        frozen = load_frozen_config(study_root)
        spec = build_module_test_spec(
            module_id="A-E1", route="S", n_mode="shared_n", fixed_n=None,
            frozen_config=frozen, _point_count=2, _repeat_count=2,
        )
        batch, metadata = _build_test_batch(spec, frozen)
        n_count = len(frozen.protocol["sample_sizes"]["core"])
        assert len(metadata) == 2 * 2 * n_count

    def test_metadata_namespace_binding(self):
        from study02a.config import load_frozen_config
        study_root = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
        frozen = load_frozen_config(study_root)
        spec = build_module_test_spec(
            module_id="A-E1", route="F2", n_mode="fixed_n", fixed_n=7,
            frozen_config=frozen, _point_count=2, _repeat_count=1,
        )
        _, metadata = _build_test_batch(spec, frozen)
        for row in metadata:
            assert row["design_namespace"] == 220301
            assert row["sample_namespace"] == 320301
            assert row["role"] == "module_test"


class TestConsumeTestEvaluation:
    def test_sealed_state_rejects_consumption(self, tmp_path):
        run_dir = _setup_run_dir(tmp_path, state="sealed")
        with pytest.raises(ValueError, match="requires state unsealed_once"):
            consume_test_evaluation(
                run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
                cache_root=tmp_path / "cache", module_id="A-E1",
                winner_fit_id="winner-001", timestamp="2026-07-25T10:00:00Z",
                _point_count=2, _repeat_count=1,
            )

    def test_consumed_state_rejects_repeat(self, tmp_path):
        run_dir = _setup_run_dir(tmp_path, state="consumed")
        with pytest.raises(ValueError, match="requires state unsealed_once"):
            consume_test_evaluation(
                run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
                cache_root=tmp_path / "cache", module_id="A-E1",
                winner_fit_id="winner-001", timestamp="2026-07-25T10:00:00Z",
                _point_count=2, _repeat_count=1,
            )

    def test_missing_checkpoint_produces_failure_receipt_and_consumes(self, tmp_path):
        run_dir = _setup_run_dir(tmp_path, state="unsealed_once", with_checkpoint=False)
        result = consume_test_evaluation(
            run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
            cache_root=tmp_path / "cache", module_id="A-E1",
            winner_fit_id="winner-001", timestamp="2026-07-25T10:00:00Z",
            _point_count=2, _repeat_count=1,
        )
        assert result["outcome"] == "failure"
        state = json.loads((run_dir / "formal_state.json").read_text(encoding="utf-8"))
        assert state["state"] == "consumed"
        assert state["failure_receipt_sha256"] is not None
        assert state["result_receipt_sha256"] is None
        failure_path = run_dir / "test_failure_receipt.json"
        assert failure_path.is_file()
        failure = json.loads(failure_path.read_text(encoding="utf-8"))
        assert failure["receipt_version"] == "study02-test-failure-v1"
        assert failure["test_access_count"] == 1

    def test_corrupt_checkpoint_produces_failure_receipt_and_consumes(self, tmp_path):
        run_dir = _setup_run_dir(tmp_path, state="unsealed_once", corrupt_checkpoint=True)
        result = consume_test_evaluation(
            run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
            cache_root=tmp_path / "cache", module_id="A-E1",
            winner_fit_id="winner-001", timestamp="2026-07-25T10:00:00Z",
            _point_count=2, _repeat_count=1,
        )
        assert result["outcome"] == "failure"
        state = json.loads((run_dir / "formal_state.json").read_text(encoding="utf-8"))
        assert state["state"] == "consumed"
        assert state["failure_receipt_sha256"] is not None

    def test_repeat_consumption_after_failure_rejected(self, tmp_path):
        run_dir = _setup_run_dir(tmp_path, state="unsealed_once", with_checkpoint=False)
        consume_test_evaluation(
            run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
            cache_root=tmp_path / "cache", module_id="A-E1",
            winner_fit_id="winner-001", timestamp="2026-07-25T10:00:00Z",
            _point_count=2, _repeat_count=1,
        )
        with pytest.raises(ValueError, match="requires state unsealed_once"):
            consume_test_evaluation(
                run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
                cache_root=tmp_path / "cache", module_id="A-E1",
                winner_fit_id="winner-001", timestamp="2026-07-25T11:00:00Z",
                _point_count=2, _repeat_count=1,
            )

    def test_bundle_sha_mismatch_rejected(self, tmp_path):
        run_dir = _setup_run_dir(tmp_path, state="unsealed_once")
        bundle_path = run_dir / "pre_unseal_bundle.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle["code_commit"] = "ff" * 20
        bundle_path.write_bytes(_canonical_bytes(bundle))
        with pytest.raises(ValueError, match="pre_unseal_bundle_sha256 does not match"):
            consume_test_evaluation(
                run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
                cache_root=tmp_path / "cache", module_id="A-E1",
                winner_fit_id="winner-001", timestamp="2026-07-25T10:00:00Z",
                _point_count=2, _repeat_count=1,
            )

    def test_approval_sha_mismatch_rejected(self, tmp_path):
        run_dir = _setup_run_dir(tmp_path, state="unsealed_once")
        approval_path = run_dir / "oracle_approval.json"
        approval = json.loads(approval_path.read_text(encoding="utf-8"))
        approval["decision"] = "REJECT"
        approval_path.write_bytes(_canonical_bytes(approval))
        with pytest.raises(ValueError, match="approval_sha256 does not match"):
            consume_test_evaluation(
                run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
                cache_root=tmp_path / "cache", module_id="A-E1",
                winner_fit_id="winner-001", timestamp="2026-07-25T10:00:00Z",
                _point_count=2, _repeat_count=1,
            )

    def test_unknown_winner_fit_id_rejected(self, tmp_path):
        run_dir = _setup_run_dir(tmp_path, state="unsealed_once")
        with pytest.raises(ValueError, match="not found in plan"):
            consume_test_evaluation(
                run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
                cache_root=tmp_path / "cache", module_id="A-E1",
                winner_fit_id="nonexistent-fit", timestamp="2026-07-25T10:00:00Z",
                _point_count=2, _repeat_count=1,
            )

    def test_receipt_no_replace_semantics(self, tmp_path):
        run_dir = _setup_run_dir(tmp_path, state="unsealed_once", with_checkpoint=False)
        consume_test_evaluation(
            run_dir=run_dir, study_root=REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究",
            cache_root=tmp_path / "cache", module_id="A-E1",
            winner_fit_id="winner-001", timestamp="2026-07-25T10:00:00Z",
            _point_count=2, _repeat_count=1,
        )
        failure_path = run_dir / "test_failure_receipt.json"
        assert failure_path.is_file()
        original_bytes = failure_path.read_bytes()
        with pytest.raises(ValueError, match="no-replace"):
            _publish_no_replace(failure_path, b"overwrite-attempt")
        assert failure_path.read_bytes() == original_bytes


class TestPublishNoReplace:
    def test_creates_file(self, tmp_path):
        target = tmp_path / "receipt.json"
        _publish_no_replace(target, b'{"test": true}\n')
        assert target.read_bytes() == b'{"test": true}\n'

    def test_rejects_overwrite(self, tmp_path):
        target = tmp_path / "receipt.json"
        target.write_bytes(b"original")
        with pytest.raises(ValueError, match="no-replace"):
            _publish_no_replace(target, b"new")
        assert target.read_bytes() == b"original"


class TestRealTestNotAccessed:
    def test_real_runs_test_access_count_stays_zero(self):
        """Verify no real formal run directory has test_access_count > 0."""
        study_root = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
        formal_dir = study_root / "artifacts" / "formal"
        if not formal_dir.is_dir():
            pytest.skip("no formal artifacts directory")
        for state_file in formal_dir.rglob("formal_state.json"):
            state = json.loads(state_file.read_text(encoding="utf-8"))
            assert state.get("test_access_count", 0) == 0, (
                f"real formal state {state_file} has test_access_count != 0"
            )
