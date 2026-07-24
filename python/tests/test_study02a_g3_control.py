"""Tests for the unified G3 test control plane (formal_g3_control.py R3).

Covers: CLI fail-closed, predecessor chain, cohort resolution, schema validation,
unified state machine (sealed -> unsealed_once), old version rejection, SHA binding.
"""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CODE = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code"
for _p in (str(STUDY_CODE), str(REPO_ROOT / "python")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from study02a.formal_g3_control import (
    _APPROVAL_VERSION,
    _BUNDLE_VERSION,
    _MANIFEST_VERSION,
    _STATE_VERSION,
    _canonical,
    _sha256_bytes,
    authorize_g3_test_once,
    build_g3_pre_unseal_bundle,
    build_g3_test_manifest,
    initialize_g3_formal_state,
    publish_g3_approval,
    publish_g3_bundle,
    publish_g3_test_manifest,
    resolve_g3_predecessor_chain,
    G3RunChain,
    ResolvedCohortEntry,
)
from study02a.formal_contracts import FROZEN_MATRIX_SHA256

STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
COMMIT = "ab" * 20
CONFIG_SHA = "44fba47c7af66166e1d3f11890299a8bb5c352ac1abf3447cd00cfd3acf97449"


def _make_run_dir(tmp_path, module_id, run_id, predecessor_module=None, predecessor_run=None):
    run_dir = tmp_path / module_id / run_id
    run_dir.mkdir(parents=True)
    pred = {
        "module_id": predecessor_module or "none",
        "run_id": predecessor_run or "none",
        "selection_trace_path": "none" if not predecessor_module else f"/fake/{predecessor_module}/trace.json",
        "selection_trace_sha256": "none" if not predecessor_module else "dd" * 32,
        "selection_receipt_path": "none" if not predecessor_module else f"/fake/{predecessor_module}/receipt.json",
        "selection_receipt_sha256": "none" if not predecessor_module else "ee" * 32,
        "selection_ledger_path": "none" if not predecessor_module else f"/fake/{predecessor_module}/ledger.jsonl",
    }
    manifest = {
        "manifest_version": "study02-formal-v1",
        "module_id": module_id,
        "run_id": run_id,
        "base_protocol": {"id": "A-G2-protocol-v1", "sha256": "aa" * 32},
        "base_search": {"id": "A-G2-search-v1", "sha256": "bb" * 32},
        "amendment": {"id": "A-g3-amendment-v1", "sha256": "cc" * 32},
        "effective_config": {"sha256": CONFIG_SHA, "max_epochs": 100, "min_epochs": 50, "patience": 40},
        "matrix": {"path": "/fake/matrix.csv", "sha256": FROZEN_MATRIX_SHA256, "row_count": 820,
                   "rule_ids": ["r1"], "fit_ids": ["f1"]},
        "code_commit": COMMIT,
        "role_namespaces": {"training": "study02/formal/training", "validation": "study02/formal/validation"},
        "seeds": {"screening": [420001, 420002, 420003], "formal": list(range(420101, 420111))},
        "test_state": "sealed",
        "predecessor": pred,
        "scheduler": {
            "scheduler_version": "study02-formal-scheduler-v2",
            "authority": {
                "study_root": str(STUDY_ROOT), "matrix_path": "/fake/matrix.csv",
                "matrix_sha256": FROZEN_MATRIX_SHA256, "cache_root": "/fake/cache",
                "code_commit": COMMIT, "scoped_code_sha256": "ff" * 32,
                "scoped_code_files": [], "controller_key_id": "test-key",
                "effective_config_sha256": CONFIG_SHA,
                "predecessor_input": None if not predecessor_module else {"module_id": predecessor_module, "run_id": predecessor_run},
                "predecessor_trace_sha256": "none" if not predecessor_module else "dd" * 32,
                "plan_sha256": "11" * 32, "authority_sha256": hashlib.sha256(f"{module_id}:{run_id}".encode()).hexdigest(),
            },
            "fit_count": 10, "genesis_event_sha256": "22" * 32, "test_access_count": 0,
        },
    }
    (run_dir / "manifest.json").write_bytes(_canonical(manifest))
    return run_dir


def _make_chain(tmp_path):
    ae1_dir = _make_run_dir(tmp_path, "A-E1", "run-ae1")
    ae3_dir = _make_run_dir(tmp_path, "A-E3", "run-ae3", "A-E1", "run-ae1")
    ae2_dir = _make_run_dir(tmp_path, "A-E2", "run-ae2", "A-E3", "run-ae3")
    return ae2_dir, tmp_path


class TestCLIFailClosed:
    def test_formal_consume_test_refuses(self):
        result = subprocess.run(
            [sys.executable, str(STUDY_CODE / "run_study02a.py"), "formal-consume-test",
             "--artifact-root", "/fake", "--cache-root", "/fake"],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert result.returncode != 0
        assert "BLOCKED" in result.stderr or "BLOCKED" in result.stdout


class TestPredecessorChain:
    def test_resolves_correct_chain(self, tmp_path):
        ae2_dir, artifact_root = _make_chain(tmp_path)
        chain = resolve_g3_predecessor_chain(ae2_run_dir=ae2_dir, artifact_root=artifact_root)
        assert chain.ae1_run_id == "run-ae1"
        assert chain.ae3_run_id == "run-ae3"
        assert chain.ae2_run_id == "run-ae2"

    def test_rejects_wrong_predecessor_module(self, tmp_path):
        _make_run_dir(tmp_path, "A-E1", "run-ae1")
        _make_run_dir(tmp_path, "A-E3", "run-ae3", "A-E2", "run-ae1")
        ae2_dir = _make_run_dir(tmp_path, "A-E2", "run-ae2", "A-E3", "run-ae3")
        with pytest.raises(ValueError, match="A-E3 predecessor must be A-E1"):
            resolve_g3_predecessor_chain(ae2_run_dir=ae2_dir, artifact_root=tmp_path)

    def test_rejects_ae1_with_predecessor(self, tmp_path):
        _make_run_dir(tmp_path, "A-E1", "run-ae1", "A-E3", "run-ae3")
        _make_run_dir(tmp_path, "A-E3", "run-ae3", "A-E1", "run-ae1")
        ae2_dir = _make_run_dir(tmp_path, "A-E2", "run-ae2", "A-E3", "run-ae3")
        with pytest.raises(ValueError, match="A-E1 predecessor"):
            resolve_g3_predecessor_chain(ae2_run_dir=ae2_dir, artifact_root=tmp_path)

    def test_rejects_cross_run_predecessor(self, tmp_path):
        _make_run_dir(tmp_path, "A-E1", "run-ae1")
        _make_run_dir(tmp_path, "A-E3", "run-ae3", "A-E1", "wrong-run")
        ae2_dir = _make_run_dir(tmp_path, "A-E2", "run-ae2", "A-E3", "run-ae3")
        with pytest.raises(ValueError, match="manifest.json not found"):
            resolve_g3_predecessor_chain(ae2_run_dir=ae2_dir, artifact_root=tmp_path)


class TestG3Schemas:
    def _make_bundle_and_state(self, tmp_path):
        chain = G3RunChain(
            ae1_run_id="r1", ae1_run_dir=tmp_path / "A-E1" / "r1",
            ae3_run_id="r3", ae3_run_dir=tmp_path / "A-E3" / "r3",
            ae2_run_id="r2", ae2_run_dir=tmp_path / "A-E2" / "r2",
            ae1_authority_sha256="a1" * 32, ae3_authority_sha256="a3" * 32,
            ae2_authority_sha256="a2" * 32,
        )
        manifest = {
            "manifest_version": _MANIFEST_VERSION,
            "code_commit": COMMIT,
            "effective_config_sha256": CONFIG_SHA,
            "frozen_matrix_sha256": FROZEN_MATRIX_SHA256,
            "frozen_matrix_rows": 820,
            "run_chain": {
                "A-E1": {"run_id": "r1", "authority_sha256": "a1" * 32},
                "A-E3": {"run_id": "r3", "authority_sha256": "a3" * 32},
                "A-E2": {"run_id": "r2", "authority_sha256": "a2" * 32},
            },
            "cohort_total": 415,
            "cohort_counts": {"A-E1": 205, "A-E2": 100, "A-E3": 110},
            "cohort_entries": [],
            "test_namespaces": {
                "A-E1": {"design": 220301, "sample": 320301},
                "A-E2": {"design": 220302, "sample": 320302},
                "A-E3": {"design": 220303, "sample": 320303},
            },
            "test_sizes": {"parameter_points": 256, "repeats_per_point_n": 200},
            "traditional_methods": {"primary": ["mle", "mps", "wmle", "mdm", "lre"], "diagnostic": ["mmle", "lse", "mm", "pwm"]},
            "failure_penalty": 10.0,
            "output_schema": "study02-g3-test-evidence-v1",
        }
        manifest_bytes = _canonical(manifest)
        manifest["manifest_sha256"] = _sha256_bytes(manifest_bytes)

        bundle = build_g3_pre_unseal_bundle(
            manifest=manifest, chain=chain,
            selection_trace_shas={"A-E1": "s1" * 32, "A-E3": "s3" * 32, "A-E2": "s2" * 32},
            ceiling_report_shas={"A-E1": "c1" * 32, "A-E3": "c3" * 32, "A-E2": "c2" * 32},
            leakage_audit_shas={"A-E1": "l1" * 32, "A-E3": "l3" * 32, "A-E2": "l2" * 32},
        )
        return manifest, bundle, chain

    def _setup_authorized(self, tmp_path):
        """Full setup: manifest + bundle + state + approval + oracle_review. Returns paths."""
        manifest, bundle, chain = self._make_bundle_and_state(tmp_path)
        out_dir = tmp_path / "g3"
        out_dir.mkdir(exist_ok=True)
        manifest_path = publish_g3_test_manifest(manifest, out_dir)
        bundle_path = publish_g3_bundle(bundle, out_dir)
        state_path = out_dir / "g3_formal_state.json"
        ledger_path = out_dir / "g3_transition_ledger.jsonl"
        initialize_g3_formal_state(state_path=state_path, bundle=bundle, run_family_id="G3", timestamp="T1")

        oracle_review_path = out_dir / "oracle_review.json"
        oracle_review_path.write_bytes(_canonical({"review": "oracle", "verdict": "APPROVE"}))
        oracle_review_sha = _sha256_bytes(oracle_review_path.read_bytes())

        approval_path = out_dir / "g3_oracle_approval.json"
        approval = {
            "approval_version": _APPROVAL_VERSION,
            "decision": "APPROVE G3 test unseal",
            "code_commit": COMMIT,
            "effective_config_sha256": CONFIG_SHA,
            "frozen_matrix_sha256": FROZEN_MATRIX_SHA256,
            "g3_pre_unseal_bundle_sha256": bundle["bundle_sha256"],
            "g3_test_manifest_sha256": manifest["manifest_sha256"],
            "selection_trace_hashes": bundle["selection_trace_hashes"],
            "oracle_review_artifact_sha256": oracle_review_sha,
            "issued_at": "T2",
        }
        approval_path.write_bytes(_canonical(approval))

        return {
            "manifest": manifest, "bundle": bundle, "chain": chain,
            "manifest_path": manifest_path, "bundle_path": bundle_path,
            "state_path": state_path, "ledger_path": ledger_path,
            "approval_path": approval_path, "oracle_review_path": oracle_review_path,
            "out_dir": out_dir,
        }

    def test_manifest_version(self, tmp_path):
        manifest, _, _ = self._make_bundle_and_state(tmp_path)
        assert manifest["manifest_version"] == _MANIFEST_VERSION

    def test_bundle_version(self, tmp_path):
        _, bundle, _ = self._make_bundle_and_state(tmp_path)
        assert bundle["bundle_version"] == _BUNDLE_VERSION
        assert bundle["frozen_matrix_sha256"] == FROZEN_MATRIX_SHA256

    def test_bundle_binds_manifest_sha(self, tmp_path):
        manifest, bundle, _ = self._make_bundle_and_state(tmp_path)
        assert bundle["g3_test_manifest_sha256"] == manifest["manifest_sha256"]

    def test_state_lifecycle_sealed_to_unsealed(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        after = authorize_g3_test_once(
            state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
            approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
            oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
            timestamp="T3",
        )
        assert after["state"] == "unsealed_once"
        assert after["test_access_count"] == 1
        assert after["transition_seq"] == 1
        assert after["approval_sha256"] is not None
        assert ctx["ledger_path"].is_file()
        assert not ctx["state_path"].with_name(ctx["state_path"].name + ".journal").exists()
        assert not ctx["state_path"].with_name(ctx["state_path"].name + ".lock").exists()

    def test_repeat_authorize_rejected(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        authorize_g3_test_once(
            state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
            approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
            oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
            timestamp="T3",
        )
        with pytest.raises(ValueError, match="must be sealed"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T4",
            )

    def test_wrong_approval_decision_rejected(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        bad_approval = json.loads(ctx["approval_path"].read_text(encoding="utf-8"))
        bad_approval["decision"] = "REJECT"
        ctx["approval_path"].write_bytes(_canonical(bad_approval))
        with pytest.raises(ValueError, match="APPROVE G3 test unseal"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T3",
            )
        state = json.loads(ctx["state_path"].read_text(encoding="utf-8"))
        assert state["state"] == "sealed"

    def test_old_bundle_version_rejected(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        tampered = json.loads(ctx["bundle_path"].read_text(encoding="utf-8"))
        tampered["bundle_version"] = "study02-pre-unseal-v3"
        ctx["bundle_path"].write_bytes(_canonical(tampered))
        with pytest.raises(ValueError, match="bundle version"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T3",
            )

    def test_bundle_tamper_rejected(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        tampered = json.loads(ctx["bundle_path"].read_text(encoding="utf-8"))
        tampered["code_commit"] = "ff" * 20
        ctx["bundle_path"].write_bytes(_canonical(tampered))
        with pytest.raises(ValueError, match="self-SHA mismatch|SHA mismatch"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T3",
            )
        state = json.loads(ctx["state_path"].read_text(encoding="utf-8"))
        assert state["state"] == "sealed"

    def test_oracle_review_sha_mismatch_rejected(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        ctx["oracle_review_path"].write_bytes(b"tampered-oracle-review")
        with pytest.raises(ValueError, match="oracle_review_artifact_sha256"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T3",
            )
        state = json.loads(ctx["state_path"].read_text(encoding="utf-8"))
        assert state["state"] == "sealed"

    def test_missing_oracle_review_rejected(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        ctx["oracle_review_path"].unlink()
        with pytest.raises(ValueError, match="oracle review artifact not found"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T3",
            )

    def test_concurrent_authorize_exactly_one_succeeds(self, tmp_path):
        from concurrent.futures import ThreadPoolExecutor
        ctx = self._setup_authorized(tmp_path)

        def try_authorize(i):
            try:
                authorize_g3_test_once(
                    state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                    approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                    oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                    timestamp=f"T3-{i}",
                )
                return "success"
            except (ValueError, OSError):
                return "rejected"

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = [pool.submit(try_authorize, i) for i in range(4)]
            results = [f.result() for f in futures]

        assert results.count("success") == 1
        assert results.count("rejected") == 3

    def test_stale_lock_fail_closed(self, tmp_path):
        """Even old locks are NOT auto-preempted. Fail-closed."""
        import time as _time
        import os as _os
        ctx = self._setup_authorized(tmp_path)
        lock_path = ctx["state_path"].with_name(ctx["state_path"].name + ".lock")
        lock_path.write_bytes(b'{"holder": "dead-process", "pid": 99999}')
        old_time = _time.time() - 7200
        _os.utime(str(lock_path), (old_time, old_time))
        with pytest.raises(ValueError, match="locked"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T3",
            )
        state = json.loads(ctx["state_path"].read_text(encoding="utf-8"))
        assert state["state"] == "sealed"

    def test_fresh_lock_rejected(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        lock_path = ctx["state_path"].with_name(ctx["state_path"].name + ".lock")
        lock_path.write_bytes(b'{"holder": "active", "pid": 12345}')
        with pytest.raises(ValueError, match="locked"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T3",
            )
        state = json.loads(ctx["state_path"].read_text(encoding="utf-8"))
        assert state["state"] == "sealed"

    def test_forged_journal_rejected(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        journal_path = ctx["state_path"].with_name(ctx["state_path"].name + ".journal")
        forged = {
            "event": {
                "transition_version": "study02-g3-formal-transition-v1",
                "run_family_id": "G3", "transition": "authorize_g3_test_once", "seq": 1,
                "before_state_sha256": "aa" * 32, "after_state_sha256": "bb" * 32,
                "approval_sha256": "cc" * 32, "g3_pre_unseal_bundle_sha256": "dd" * 32,
                "g3_test_manifest_sha256": "ee" * 32, "test_access_count": 1, "timestamp": "T-forged",
            },
            "ledger_size_before": 0,
            "ledger_sha_before": _sha256_bytes(b""),
        }
        journal_path.write_bytes(_canonical(forged))
        with pytest.raises(ValueError, match="neither before nor after"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T3",
            )
        state = json.loads(ctx["state_path"].read_text(encoding="utf-8"))
        assert state["state"] == "sealed"

    def test_journal_with_tampered_ledger_prefix_rejected(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        ctx["ledger_path"].write_bytes(b"tampered-ledger-content\n")
        journal_path = ctx["state_path"].with_name(ctx["state_path"].name + ".journal")
        state_bytes = ctx["state_path"].read_bytes()
        forged = {
            "event": {
                "transition_version": "study02-g3-formal-transition-v1",
                "run_family_id": "G3", "transition": "authorize_g3_test_once", "seq": 1,
                "before_state_sha256": _sha256_bytes(state_bytes), "after_state_sha256": "bb" * 32,
                "approval_sha256": "cc" * 32, "g3_pre_unseal_bundle_sha256": "dd" * 32,
                "g3_test_manifest_sha256": "ee" * 32, "test_access_count": 1, "timestamp": "T-forged",
            },
            "ledger_size_before": 0,
            "ledger_sha_before": _sha256_bytes(b""),
        }
        journal_path.write_bytes(_canonical(forged))
        with pytest.raises(ValueError, match="ledger prefix conflicts|unchanged ledger snapshot"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T3",
            )

    def test_crash_recovery_after_state_write(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        state_bytes = ctx["state_path"].read_bytes()
        state = json.loads(state_bytes.decode("utf-8"))
        approval_bytes = ctx["approval_path"].read_bytes()
        approval_sha = _sha256_bytes(approval_bytes)
        bundle_content = {k: v for k, v in ctx["bundle"].items() if k != "bundle_sha256"}
        bundle_sha = _sha256_bytes(_canonical(bundle_content))
        manifest_content = {k: v for k, v in ctx["manifest"].items() if k != "manifest_sha256"}
        manifest_sha = _sha256_bytes(_canonical(manifest_content))

        after = {**state, "state": "unsealed_once", "transition_seq": 1,
                 "approval_sha256": approval_sha, "test_access_count": 1, "updated_at": "T3"}
        after_bytes = _canonical(after)
        event = {
            "transition_version": "study02-g3-formal-transition-v1",
            "run_family_id": "G3", "transition": "authorize_g3_test_once", "seq": 1,
            "before_state_sha256": _sha256_bytes(state_bytes),
            "after_state_sha256": _sha256_bytes(after_bytes),
            "approval_sha256": approval_sha,
            "g3_pre_unseal_bundle_sha256": bundle_sha,
            "g3_test_manifest_sha256": manifest_sha,
            "test_access_count": 1, "timestamp": "T3",
        }
        ctx["state_path"].write_bytes(after_bytes)
        journal_path = ctx["state_path"].with_name(ctx["state_path"].name + ".journal")
        journal_record = {
            "event": event,
            "ledger_size_before": 0,
            "ledger_sha_before": _sha256_bytes(b""),
        }
        journal_path.write_bytes(_canonical(journal_record))

        with pytest.raises(ValueError, match="must be sealed"):
            authorize_g3_test_once(
                state_path=ctx["state_path"], bundle_path=ctx["bundle_path"],
                approval_path=ctx["approval_path"], manifest_path=ctx["manifest_path"],
                oracle_review_path=ctx["oracle_review_path"], ledger_path=ctx["ledger_path"],
                timestamp="T4",
            )
        assert not journal_path.exists()
        assert ctx["ledger_path"].is_file()
        ledger_content = ctx["ledger_path"].read_text(encoding="utf-8")
        assert "authorize_g3_test_once" in ledger_content
        final_state = json.loads(ctx["state_path"].read_text(encoding="utf-8"))
        assert final_state["state"] == "unsealed_once"

    def test_four_way_sha_consistency(self, tmp_path):
        ctx = self._setup_authorized(tmp_path)
        manifest_sha = ctx["manifest"]["manifest_sha256"]
        bundle_data = json.loads(ctx["bundle_path"].read_text(encoding="utf-8"))
        state_data = json.loads(ctx["state_path"].read_text(encoding="utf-8"))
        approval_data = json.loads(ctx["approval_path"].read_text(encoding="utf-8"))
        manifest_data = json.loads(ctx["manifest_path"].read_text(encoding="utf-8"))

        assert bundle_data["g3_test_manifest_sha256"] == manifest_sha
        assert state_data["g3_test_manifest_sha256"] == manifest_sha
        assert approval_data["g3_test_manifest_sha256"] == manifest_sha
        assert manifest_data["manifest_sha256"] == manifest_sha
        assert state_data["g3_pre_unseal_bundle_sha256"] == bundle_data["bundle_sha256"]
        assert approval_data["g3_pre_unseal_bundle_sha256"] == bundle_data["bundle_sha256"]

    def test_manifest_no_replace(self, tmp_path):
        manifest, _, _ = self._make_bundle_and_state(tmp_path)
        out_dir = tmp_path / "g3"
        out_dir.mkdir()
        publish_g3_test_manifest(manifest, out_dir)
        with pytest.raises(ValueError, match="no-replace"):
            publish_g3_test_manifest(manifest, out_dir)
        with pytest.raises(ValueError, match="no-replace"):
            publish_g3_test_manifest(manifest, out_dir)

    def test_four_way_sha_consistency(self, tmp_path):
        manifest, bundle, chain = self._make_bundle_and_state(tmp_path)
        out_dir = tmp_path / "g3"
        out_dir.mkdir()
        manifest_path = publish_g3_test_manifest(manifest, out_dir)
        bundle_path = publish_g3_bundle(bundle, out_dir)
        state_path = out_dir / "g3_formal_state.json"
        initialize_g3_formal_state(state_path=state_path, bundle=bundle, run_family_id="G3", timestamp="T1")
        approval_path = out_dir / "g3_oracle_approval.json"
        publish_g3_approval(approval_path=approval_path, bundle=bundle, oracle_review_sha256="or" * 32, issued_at="T2")

        manifest_sha = manifest["manifest_sha256"]
        bundle_data = json.loads(bundle_path.read_text(encoding="utf-8"))
        state_data = json.loads(state_path.read_text(encoding="utf-8"))
        approval_data = json.loads(approval_path.read_text(encoding="utf-8"))
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))

        assert bundle_data["g3_test_manifest_sha256"] == manifest_sha
        assert state_data["g3_test_manifest_sha256"] == manifest_sha
        assert approval_data["g3_test_manifest_sha256"] == manifest_sha
        assert manifest_data["manifest_sha256"] == manifest_sha
        assert state_data["g3_pre_unseal_bundle_sha256"] == bundle_data["bundle_sha256"]
        assert approval_data["g3_pre_unseal_bundle_sha256"] == bundle_data["bundle_sha256"]


class TestCohortCounts:
    def test_frozen_matrix_produces_exact_counts(self):
        from study02a.config import load_frozen_config
        from study02a.matrix import expand_module_matrix
        from study02a.formal_g3_control import _COHORT_FIT_KINDS, _EXPECTED_COHORT_COUNTS
        frozen = load_frozen_config(STUDY_ROOT)
        matrix = expand_module_matrix(frozen)
        cohort = matrix[matrix["fit_kind"].isin(_COHORT_FIT_KINDS)]
        counts = cohort.groupby("module").size().to_dict()
        assert counts == _EXPECTED_COHORT_COUNTS
