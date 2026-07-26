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


def _selection_point_records(key, base):
    records = []
    for point in range(2):
        value = base + point * 0.001
        records.append({
            "sample_id": f"n{key.n}:p{point}", "seed_id": str(key.seed),
            "point_id": f"n{key.n}:p{point}", "legal": True, "failure": 0,
            "l_param": value,
            "e_beta": value, "e_eta": value, "e_gamma": value,
        })
    return records


def _publish_module_selection(tmp_path, module_id):
    """Publish a direct, cryptographically valid module selection fixture from the frozen matrix."""
    from study02a.config import load_frozen_config
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import publish_selection_receipt, write_selection_trace
    from study02a.matrix import expand_module_matrix
    from study02a.selection import FitEvaluation, build_decision_specs, build_selection_trace

    frozen = load_frozen_config(STUDY_ROOT)
    rows = expand_module_matrix(frozen)
    specs = build_decision_specs(
        module_id, rows[rows["module"] == module_id].to_dict("records"),
    )
    run_id = f"run-{module_id.lower()}"
    run_dir = tmp_path / module_id / run_id
    run_dir.mkdir(parents=True)
    evaluations = {}
    for spec in specs:
        for candidate_index, candidate in enumerate(spec.candidates):
            for key in candidate.support_keys:
                fit_id = candidate.support_for(key)
                records = _selection_point_records(key, 0.1 + candidate_index)
                evaluations[fit_id] = FitEvaluation(
                    fit_id=fit_id, module_id=module_id, decision_id=spec.decision_id,
                    candidate_id=candidate.candidate_id, support_key=key, failed=False,
                    checkpoint_sha256=hashlib.sha256(fit_id.encode()).hexdigest(),
                    validation_identity=f"val-{fit_id}",
                    selection_score=sum(r["l_param"] for r in records) / len(records),
                    failure_penalty=0.0, point_records=records,
                )
    records, diagnostics = build_selection_trace(
        module_id=module_id, run_id=run_id, specs=tuple(specs),
        evaluations_by_fit=evaluations,
    )
    trace_path = run_dir / "selection_trace.jsonl"
    trace_sha = write_selection_trace(trace_path, records)
    publish_selection_receipt(
        receipt_path=run_dir / "selection_receipt.json",
        ledger_path=run_dir / "selection_ledger.jsonl",
        module_id=module_id, run_id=run_id, trace_path=trace_path,
        trace_sha256=trace_sha, effective_config=load_effective_formal_config(STUDY_ROOT),
        code_commit=COMMIT,
    )
    (run_dir / "selection_diagnostics.jsonl").write_bytes(
        b"".join(_canonical(record) for record in diagnostics)
    )
    return frozen, run_dir, run_id, records, evaluations, specs


def _republish_mutated_selection(run_dir, module_id, run_id, records):
    from study02a.formal_config import load_effective_formal_config
    from study02a.formal_contracts import publish_selection_receipt, write_selection_trace

    (run_dir / "selection_receipt.json").unlink()
    (run_dir / "selection_ledger.jsonl").unlink()
    trace_path = run_dir / "selection_trace.jsonl"
    trace_path.unlink()
    trace_sha = write_selection_trace(trace_path, records)
    publish_selection_receipt(
        receipt_path=run_dir / "selection_receipt.json",
        ledger_path=run_dir / "selection_ledger.jsonl",
        module_id=module_id, run_id=run_id, trace_path=trace_path,
        trace_sha256=trace_sha, effective_config=load_effective_formal_config(STUDY_ROOT),
        code_commit=COMMIT,
    )


class TestCLIFailClosed:
    def test_formal_consume_test_refuses(self):
        result = subprocess.run(
            [sys.executable, str(STUDY_CODE / "run_study02a.py"), "formal-consume-test",
             "--artifact-root", "/fake", "--cache-root", "/fake"],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert result.returncode != 0
        assert "BLOCKED" in result.stderr or "BLOCKED" in result.stdout

    def test_legacy_per_module_authorize_refuses(self):
        result = subprocess.run(
            [
                sys.executable, str(STUDY_CODE / "run_study02a.py"),
                "formal-accredit-authorize", "--module", "A-E1", "--run-id", "r1",
                "--artifact-root", "/fake", "--approval", "/fake/approval.json",
                "--oracle-review", "/fake/review.json", "--run-family-id", "G3",
            ],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert result.returncode != 0
        assert "permanently BLOCKED" in result.stderr or "permanently BLOCKED" in result.stdout

    def test_runner_does_not_expose_legacy_consumer_api(self):
        import run_study02a
        import study02a.formal_accreditation as formal_accreditation
        import study02a.formal_executor as formal_executor

        assert not hasattr(run_study02a, "consume_g3_test")

    def test_unified_build_cli_rejects_caller_supplied_code_commit(self):
        result = subprocess.run(
            [
                sys.executable, str(STUDY_CODE / "run_study02a.py"),
                "formal-g3-accredit-build", "--artifact-root", "/fake",
                "--cache-root", "/fake", "--a-e2-run-id", "r2",
                "--output-dir", "/fake/out", "--code-commit", COMMIT,
            ],
            capture_output=True, text=True, encoding="utf-8",
        )
        assert result.returncode != 0
        assert "unrecognized arguments: --code-commit" in result.stderr


class TestDirectModuleResolution:
    def test_a_e3_selected_top_resolves_to_concrete_architectures(self, tmp_path):
        from study02a.formal_g3_control import _resolve_a_e3_from_selection

        frozen, run_dir, run_id, _records, _evaluations, _specs = _publish_module_selection(tmp_path, "A-E3")
        out = {}
        _resolve_a_e3_from_selection(
            run_dir, run_id, out, frozen_config=frozen,
        )
        assert out["selected:A-E3_architecture"] == "m01"
        assert out["selected:S_architecture"] == "d01"
        assert not any(value.startswith(("selected:", "selected_top_")) for value in out.values())

    def test_a_e3_rejects_stage2_candidate_outside_frozen_domain(self, tmp_path):
        from study02a.formal_g3_control import _resolve_a_e3_from_selection

        frozen, run_dir, run_id, records, _evaluations, _specs = _publish_module_selection(tmp_path, "A-E3")
        attacked = [dict(record) for record in records]
        target = next(
            record for record in attacked
            if record["decision_id"] == "stage2:A-E3:selected:F2_or_V:n10" and record["selected"]
        )
        target["candidate_id"] = "selected_top_5:o1"
        _republish_mutated_selection(run_dir, "A-E3", run_id, attacked)
        with pytest.raises(ValueError, match="outside the frozen candidates"):
            _resolve_a_e3_from_selection(
                run_dir, run_id, {}, frozen_config=frozen,
            )

    def test_a_e2_size_and_distribution_resolve_from_frozen_candidates(self, tmp_path):
        from study02a.formal_g3_control import _resolve_a_e2_from_selection

        frozen, run_dir, run_id, _records, _evaluations, _specs = _publish_module_selection(tmp_path, "A-E2")
        out = {}
        _resolve_a_e2_from_selection(
            run_dir, run_id, out, frozen_config=frozen,
        )
        assert out["selected_training_size"] == "100000"
        assert out["selected:A-E2_distribution"] == "core_continuous"

    @pytest.mark.parametrize(
        ("decision_id", "forged"),
        [
            ("training_size:A-E2:selected:A-E3_baseline", "12345"),
            ("distribution:A-E2:selected:A-E3_baseline", "forged_distribution"),
        ],
    )
    def test_a_e2_rejects_resolution_outside_frozen_domain(
        self, tmp_path, decision_id, forged,
    ):
        from study02a.formal_g3_control import _resolve_a_e2_from_selection

        frozen, run_dir, run_id, records, _evaluations, _specs = _publish_module_selection(tmp_path, "A-E2")
        attacked = [dict(record) for record in records]
        target = next(
            record for record in attacked
            if record["decision_id"] == decision_id and record["selected"]
        )
        target["candidate_id"] = forged
        _republish_mutated_selection(run_dir, "A-E2", run_id, attacked)
        with pytest.raises(ValueError, match="outside the frozen candidates"):
            _resolve_a_e2_from_selection(
                run_dir, run_id, {}, frozen_config=frozen,
            )


class TestThreeModuleDiagnostics:
    @pytest.mark.parametrize("module_id", ["A-E1", "A-E3", "A-E2"])
    def test_rejects_rechained_forged_selection_before_writing_diagnostics(
        self, tmp_path, monkeypatch, module_id,
    ):
        import study02a.formal_accreditation as formal_accreditation
        import study02a.formal_executor as formal_executor
        from study02a.selection import serialize_point_evidence

        _frozen, run_dir, run_id, records, evaluations, _specs = (
            _publish_module_selection(tmp_path, module_id)
        )
        point_dir = run_dir / "selection" / "point_evidence"
        point_dir.mkdir(parents=True)
        for fit_id, evaluation in evaluations.items():
            (point_dir / f"{fit_id}.json").write_bytes(
                _canonical(serialize_point_evidence(evaluation))
            )

        monkeypatch.setattr(
            formal_accreditation, "_rebuild_authority",
            lambda run_dir_arg, cache_root_arg: ({}, [], {"fit_states": {}}, []),
        )
        monkeypatch.setattr(
            formal_executor, "rebuild_selection_point_provenance",
            lambda **kwargs: dict(evaluations),
        )

        attacked = [dict(record) for record in records]
        decision_id = str(attacked[0]["decision_id"])
        decision_records = [
            record for record in attacked if record["decision_id"] == decision_id
        ]
        selected = next(record for record in decision_records if record["selected"])
        replacement = next(record for record in decision_records if not record["selected"])
        selected["selected"] = False
        replacement["selected"] = True
        selected["validation_score"] = float(selected["validation_score"]) + 1.0
        replacement["validation_score"] = min(
            float(record["validation_score"]) for record in decision_records
        ) - 1.0
        selected["supporting_evidence_sha256"] = "f" * 64
        _republish_mutated_selection(run_dir, module_id, run_id, attacked)

        with pytest.raises(ValueError, match="selection trace disagrees"):
            formal_accreditation.build_module_accreditation_diagnostics(
                study_root=STUDY_ROOT, module=module_id, run_id=run_id,
                artifact_root=tmp_path, cache_root=tmp_path / "cache",
            )
        for name in (
            "fit_status.csv", "ceiling_hit_report.json", "leakage_audit.json",
        ):
            assert not (run_dir / name).exists()

    @pytest.mark.parametrize("module_id", ["A-E3", "A-E2"])
    def test_downstream_module_diagnostics_rebuild_semantically(
        self, tmp_path, monkeypatch, module_id,
    ):
        import run_study02a
        import study02a.formal_accreditation as formal_accreditation
        import study02a.formal_executor as formal_executor
        from study02a.formal_contracts import APPROVED_EFFECTIVE_CONFIG_SHA256
        from study02a.matrix import expand_module_matrix
        from study02a.selection import serialize_point_evidence

        frozen, run_dir, run_id, records, evaluations, specs = _publish_module_selection(
            tmp_path, module_id,
        )
        expected_fit_ids = {
            candidate.support_for(key)
            for spec in specs for candidate in spec.candidates for key in candidate.support_keys
        }
        matrix_by_fit = {
            str(row["fit_id"]): row
            for row in expand_module_matrix(frozen).to_dict("records")
            if str(row["fit_id"]) in expected_fit_ids
        }
        plans = []
        fit_states = {}
        point_dir = run_dir / "selection" / "point_evidence"
        point_dir.mkdir(parents=True)
        receipt_dir = run_dir / "receipts"
        receipt_dir.mkdir()
        for index, fit_id in enumerate(sorted(expected_fit_ids)):
            row = matrix_by_fit[fit_id]
            n = row["n"]
            plans.append({
                "fit_id": fit_id, "module_id": module_id, "rule_id": str(row["rule_id"]),
                "route": str(row["route"]), "distribution": "core_continuous",
                "n_mode": "shared_n" if n == "shared" else "fixed_n",
                "fixed_n": None if n == "shared" else int(n),
                "training_size": int(row["training_size"]), "seed": int(row["seed"]),
            })
            evaluation = evaluations[fit_id]
            (point_dir / f"{fit_id}.json").write_bytes(_canonical(serialize_point_evidence(evaluation)))
            output_dir = run_dir / "outputs" / fit_id
            output_dir.mkdir(parents=True)
            curve = [100.0 / (epoch + 1) for epoch in range(60)]
            (output_dir / "evidence.json").write_bytes(_canonical({
                "evidence_version": "study02-formal-fit-evidence-v1",
                "fit_id": fit_id, "run_id": run_id,
                "checkpoint_sha256": evaluation.checkpoint_sha256,
                "actual_epochs": 60, "best_epoch_one_based": 60,
                "hit_epoch_100": False, "early_stop_reason": "patience_exhausted",
                "terminal_validation_slope": 0.0,
                "validation_curve": curve, "test_access_count": 0,
            }))
            (receipt_dir / f"{fit_id}.succeeded.json").write_bytes(_canonical({
                "state": "succeeded",
            }))
            fit_states[fit_id] = "succeeded"

        manifest = {
            "module_id": module_id, "run_id": run_id, "code_commit": COMMIT,
            "effective_config": {"sha256": APPROVED_EFFECTIVE_CONFIG_SHA256},
            "role_namespaces": {
                "training": "study02/formal/training",
                "validation": "study02/formal/validation",
            },
        }
        (run_dir / "manifest.json").write_bytes(_canonical(manifest))

        monkeypatch.setattr(
            formal_accreditation, "_rebuild_authority",
            lambda run_dir_arg, cache_root_arg: (
                manifest, plans, {"fit_states": fit_states}, [],
            ),
        )
        monkeypatch.setattr(
            formal_executor, "rebuild_selection_point_provenance",
            lambda **kwargs: dict(evaluations),
        )
        result = formal_accreditation.build_module_accreditation_diagnostics(
            study_root=STUDY_ROOT, module=module_id, run_id=run_id,
            artifact_root=tmp_path, cache_root=tmp_path / "cache",
        )
        assert result["module"] == module_id
        fit_status = result["fit_status_path"].read_text(encoding="utf-8")
        assert len(fit_status.splitlines()) == len(expected_fit_ids) + 1
        if module_id == "A-E3":
            assert ",shared," in fit_status
        leakage = json.loads(result["leakage_path"].read_text(encoding="utf-8"))
        assert leakage["test_access_count"] == 0
        # Exact diagnostics are idempotently reusable.
        second = formal_accreditation.build_module_accreditation_diagnostics(
            study_root=STUDY_ROOT, module=module_id, run_id=run_id,
            artifact_root=tmp_path, cache_root=tmp_path / "cache",
        )
        assert second["fit_status_path"].read_bytes() == result["fit_status_path"].read_bytes()

        # A published point artifact that diverges from checkpoint-rebuilt provenance fails first.
        attacked_fit = sorted(expected_fit_ids)[0]
        attacked_path = point_dir / f"{attacked_fit}.json"
        original_point_bytes = attacked_path.read_bytes()
        attacked_point = json.loads(original_point_bytes.decode("utf-8"))
        attacked_point["checkpoint_sha256"] = "f" * 64
        attacked_path.write_bytes(_canonical(attacked_point))
        with pytest.raises(ValueError, match="content SHA disagrees|checkpoint_sha256 disagrees"):
            formal_accreditation.build_module_accreditation_diagnostics(
                study_root=STUDY_ROOT, module=module_id, run_id=run_id,
                artifact_root=tmp_path, cache_root=tmp_path / "cache",
            )
        attacked_path.write_bytes(original_point_bytes)

        # An existing diagnostic is reusable only when it matches the deterministic rebuild.
        result["ceiling_path"].write_bytes(b"conflicting-ceiling\n")
        with pytest.raises(ValueError, match="existing diagnostics conflict"):
            formal_accreditation.build_module_accreditation_diagnostics(
                study_root=STUDY_ROOT, module=module_id, run_id=run_id,
                artifact_root=tmp_path, cache_root=tmp_path / "cache",
            )


class TestReusableSealedGenesisState:
    @staticmethod
    def _valid():
        bundle = {
            "code_commit": COMMIT,
            "effective_config_sha256": CONFIG_SHA,
            "bundle_sha256": "aa" * 32,
        }
        manifest = {"manifest_sha256": "bb" * 32}
        timestamp = "2026-07-26T12:34:56.123456Z"
        state = {
            "state_version": _STATE_VERSION,
            "run_family_id": "G3-formal",
            "state": "sealed",
            "transition_seq": 0,
            "code_commit": COMMIT,
            "effective_config_sha256": CONFIG_SHA,
            "frozen_matrix_sha256": FROZEN_MATRIX_SHA256,
            "g3_pre_unseal_bundle_sha256": bundle["bundle_sha256"],
            "g3_test_manifest_sha256": manifest["manifest_sha256"],
            "approval_sha256": None,
            "result_receipt_sha256": None,
            "failure_receipt_sha256": None,
            "created_at": timestamp,
            "updated_at": timestamp,
            "test_access_count": 0,
        }
        return state, bundle, manifest

    @pytest.mark.parametrize(
        "timestamp",
        ["2026-07-26T12:34:56Z", "2026-07-26T12:34:56.123456Z"],
    )
    def test_valid_canonical_genesis(self, timestamp):
        from study02a.formal_g3_control import _validate_reusable_g3_formal_state

        state, bundle, manifest = self._valid()
        state["created_at"] = timestamp
        state["updated_at"] = timestamp
        _validate_reusable_g3_formal_state(
            state, bundle=bundle, manifest=manifest,
        )

    @pytest.mark.parametrize(
        "case",
        [
            "transition_false", "transition_float", "access_false", "access_float",
            "version", "family", "commit", "config", "matrix", "bundle_sha",
            "manifest_sha", "approval", "result", "failure", "extra", "missing",
            "garbage_time", "blank_time", "non_utc_time", "unequal_time",
        ],
    )
    def test_rejects_forged_or_noncanonical_genesis(self, case):
        from study02a.formal_g3_control import _validate_reusable_g3_formal_state

        state, bundle, manifest = self._valid()
        mutations = {
            "transition_false": lambda: state.__setitem__("transition_seq", False),
            "transition_float": lambda: state.__setitem__("transition_seq", 0.0),
            "access_false": lambda: state.__setitem__("test_access_count", False),
            "access_float": lambda: state.__setitem__("test_access_count", 0.0),
            "version": lambda: state.__setitem__("state_version", "wrong"),
            "family": lambda: state.__setitem__("run_family_id", "wrong"),
            "commit": lambda: state.__setitem__("code_commit", "cc" * 20),
            "config": lambda: state.__setitem__("effective_config_sha256", "cc" * 32),
            "matrix": lambda: state.__setitem__("frozen_matrix_sha256", "cc" * 32),
            "bundle_sha": lambda: state.__setitem__("g3_pre_unseal_bundle_sha256", "cc" * 32),
            "manifest_sha": lambda: state.__setitem__("g3_test_manifest_sha256", "cc" * 32),
            "approval": lambda: state.__setitem__("approval_sha256", "cc" * 32),
            "result": lambda: state.__setitem__("result_receipt_sha256", "cc" * 32),
            "failure": lambda: state.__setitem__("failure_receipt_sha256", "cc" * 32),
            "extra": lambda: state.__setitem__("unexpected", None),
            "missing": lambda: state.pop("approval_sha256"),
            "garbage_time": lambda: (
                state.__setitem__("created_at", "garbage"),
                state.__setitem__("updated_at", "garbage"),
            ),
            "blank_time": lambda: (
                state.__setitem__("created_at", " "),
                state.__setitem__("updated_at", " "),
            ),
            "non_utc_time": lambda: (
                state.__setitem__("created_at", "2026-07-26T20:34:56+08:00"),
                state.__setitem__("updated_at", "2026-07-26T20:34:56+08:00"),
            ),
            "unequal_time": lambda: state.__setitem__(
                "updated_at", "2026-07-26T12:34:57.123456Z"
            ),
        }
        mutations[case]()
        with pytest.raises(ValueError, match="existing unified G3 state"):
            _validate_reusable_g3_formal_state(
                state, bundle=bundle, manifest=manifest,
            )


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
            staged_ledger_shas={"A-E1": "g1" * 32},
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

    def test_four_way_sha_consistency_after_authorized_setup(self, tmp_path):
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

    def test_four_way_sha_consistency_from_direct_publication(self, tmp_path):
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


class TestUnifiedSealedBuilder:
    def test_full_build_derives_commit_rebuilds_three_modules_and_publishes_only_sealed(
        self, tmp_path, monkeypatch,
    ):
        import run_study02a
        import study02a.formal_g3_control as g3
        from study02a.config import load_frozen_config
        from study02a.matrix import expand_module_matrix

        artifact_root = tmp_path / "artifacts"
        cache_root = tmp_path / "cache"
        output_dir = tmp_path / "g3-output"
        run_ids = {"A-E1": "run-ae1", "A-E3": "run-ae3", "A-E2": "run-ae2"}
        run_dirs = {
            module: artifact_root / module / run_id for module, run_id in run_ids.items()
        }
        for run_dir in run_dirs.values():
            run_dir.mkdir(parents=True)
            (run_dir / "selection_trace.jsonl").write_bytes(b"{}\n")
        (run_dirs["A-E1"] / "staged_resolution_ledger.jsonl").write_bytes(b"{}\n")

        chain = G3RunChain(
            ae1_run_id=run_ids["A-E1"], ae1_run_dir=run_dirs["A-E1"],
            ae3_run_id=run_ids["A-E3"], ae3_run_dir=run_dirs["A-E3"],
            ae2_run_id=run_ids["A-E2"], ae2_run_dir=run_dirs["A-E2"],
            ae1_authority_sha256="a1" * 32, ae3_authority_sha256="a3" * 32,
            ae2_authority_sha256="a2" * 32,
        )
        common_manifest = {"code_commit": COMMIT}
        authority = g3.G3Authority(
            ae1_manifest=dict(common_manifest), ae1_plan=[], ae1_state={}, ae1_events=[],
            ae3_manifest=dict(common_manifest), ae3_plan=[], ae3_state={}, ae3_events=[],
            ae2_manifest=dict(common_manifest), ae2_plan=[], ae2_state={}, ae2_events=[],
        )
        monkeypatch.setattr(g3, "resolve_g3_predecessor_chain", lambda **kwargs: chain)
        monkeypatch.setattr(g3, "verify_g3_chain_authority", lambda **kwargs: authority)

        frozen = load_frozen_config(STUDY_ROOT)
        matrix = expand_module_matrix(frozen)
        cohort_rows = matrix[matrix["fit_kind"].isin(g3._COHORT_FIT_KINDS)]
        cohort = tuple(
            ResolvedCohortEntry(
                fit_id=str(row["fit_id"]), module_id=str(row["module"]),
                rule_id=str(row["rule_id"]),
                route="resolved_route", distribution="core_continuous",
                n="shared" if row["n"] == "shared" else int(row["n"]),
                seed=int(row["seed"]), fit_kind=str(row["fit_kind"]),
                training_size=max(1, int(row["training_size"])),
                architecture="m01", optimizer="o1", loss="raw_train_z_mse",
                checkpoint_sha256=hashlib.sha256(f"ckpt:{row['fit_id']}".encode()).hexdigest(),
                terminal_receipt_sha256=hashlib.sha256(f"receipt:{row['fit_id']}".encode()).hexdigest(),
                comparison_role="baseline",
            )
            for _, row in cohort_rows.iterrows()
        )
        monkeypatch.setattr(g3, "derive_g3_cohort_from_authority", lambda **kwargs: cohort)
        monkeypatch.setattr(g3, "resolve_g3_placeholders_from_evidence", lambda **kwargs: kwargs["cohort"])

        rebuilt_modules = []

        def fake_diagnostics(*, study_root, module, run_id, artifact_root, cache_root):
            assert study_root == STUDY_ROOT
            assert artifact_root == artifact_root_expected
            assert cache_root == cache_root_expected
            assert run_id == run_ids[module]
            rebuilt_modules.append(module)
            run_dir = run_dirs[module]
            ceiling = run_dir / "ceiling_hit_report.json"
            leakage = run_dir / "leakage_audit.json"
            ceiling.write_bytes(_canonical({"module": module, "kind": "ceiling"}))
            leakage.write_bytes(_canonical({"module": module, "test_access_count": 0}))
            return {"ceiling_path": ceiling, "leakage_path": leakage}

        artifact_root_expected = artifact_root
        cache_root_expected = cache_root
        monkeypatch.setattr(g3, "build_module_accreditation_diagnostics", fake_diagnostics)
        import study02a.formal_scheduler as formal_scheduler
        monkeypatch.setattr(formal_scheduler, "_assert_scoped_code_clean", lambda study_root: None)
        monkeypatch.setattr(formal_scheduler, "_git_sha", lambda study_root: COMMIT)

        result = g3.build_g3_accreditation(
            ae2_run_dir=run_dirs["A-E2"], artifact_root=artifact_root,
            cache_root=cache_root, study_root=STUDY_ROOT, output_dir=output_dir,
        )
        assert rebuilt_modules == ["A-E1", "A-E3", "A-E2"]
        assert result["cohort_total"] == 415
        manifest = json.loads((output_dir / "g3_test_manifest.json").read_text(encoding="utf-8"))
        state = json.loads((output_dir / "g3_formal_state.json").read_text(encoding="utf-8"))
        assert manifest["code_commit"] == COMMIT
        assert state["state"] == "sealed"
        assert state["test_access_count"] == 0
        assert not any(output_dir.glob("*approval*"))
        assert not any(output_dir.glob("*test*data*"))

        state["transition_seq"] = 9
        (output_dir / "g3_formal_state.json").write_bytes(_canonical(state))
        with pytest.raises(ValueError, match="transition_seq conflicts"):
            g3.build_g3_accreditation(
                ae2_run_dir=run_dirs["A-E2"], artifact_root=artifact_root,
                cache_root=cache_root, study_root=STUDY_ROOT, output_dir=output_dir,
            )


class TestCurrentCodeReplayGuard:
    def test_scoped_dirty_failure_is_propagated(self, monkeypatch):
        import study02a.formal_g3_control as g3
        import study02a.formal_scheduler as formal_scheduler

        monkeypatch.setattr(
            formal_scheduler, "_assert_scoped_code_clean",
            lambda study_root: (_ for _ in ()).throw(ValueError("scoped code is dirty")),
        )
        with pytest.raises(ValueError, match="scoped code is dirty"):
            g3._assert_current_code_matches_replay(STUDY_ROOT, COMMIT)

    def test_head_mismatch_fails_closed(self, monkeypatch):
        import study02a.formal_g3_control as g3
        import study02a.formal_scheduler as formal_scheduler

        monkeypatch.setattr(
            formal_scheduler, "_assert_scoped_code_clean", lambda study_root: None,
        )
        monkeypatch.setattr(formal_scheduler, "_git_sha", lambda study_root: "cd" * 20)
        with pytest.raises(ValueError, match="current HEAD does not match"):
            g3._assert_current_code_matches_replay(STUDY_ROOT, COMMIT)


def _build_real_run(tmp_path, module_id="A-E1", run_id="G3-test-run"):
    """Create a minimal REAL scheduler run (materialize + 1 succeeded fit)."""
    import hashlib as _hashlib
    from study02a.formal_scheduler import materialize_run, claim_next_fit, record_fit_succeeded
    import study02a.formal_executor as fe

    matrix_path = STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv"
    if not matrix_path.is_file():
        pytest.skip("G3 matrix not available")
    artifact_root = tmp_path / "artifacts"
    cache_root = tmp_path / "cache"
    try:
        result = materialize_run(
            study_root=STUDY_ROOT, matrix_path=matrix_path, module_id=module_id,
            run_id=run_id, artifact_root=artifact_root, cache_root=cache_root, predecessor=None,
        )
    except ValueError as exc:
        if "dirty" in str(exc):
            pytest.skip("Study02 code tree is dirty (commit first)")
        raise
    run_dir = Path(result["run_dir"])
    claim = claim_next_fit(run_dir, cache_root=cache_root, owner_id="w1", owner_nonce="n1", timestamp="T1")
    fit_id = claim["fit_id"]
    ckpt = b"test-checkpoint-bytes"
    ckpt_sha = _hashlib.sha256(ckpt).hexdigest()
    curve = [100.0 / (i + 1) for i in range(60)]
    evidence = {
        "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": fit_id, "run_id": run_id,
        "checkpoint_sha256": ckpt_sha, "actual_epochs": 60,
        "best_epoch_one_based": 60, "hit_epoch_100": False,
        "early_stop_reason": "patience_exhausted",
        "terminal_validation_slope": fe._terminal_ols_slope(tuple(curve)),
        "validation_curve": curve, "test_access_count": 0,
    }
    output_hashes = fe._write_outputs(run_dir, fit_id, run_id, ckpt, ckpt_sha, evidence)
    record_fit_succeeded(run_dir, cache_root=cache_root, fit_id=fit_id, owner_id="w1", owner_nonce="n1",
                         output_hashes=output_hashes, timestamp="T2")
    return run_dir, cache_root, fit_id


class TestProductionAuthority:
    def test_rebuild_authority_called_and_rejects_tampered_plan(self, tmp_path):
        from study02a.formal_scheduler import _rebuild_authority
        run_dir, cache_root, fit_id = _build_real_run(tmp_path)
        _rebuild_authority(run_dir, cache_root, validate_controller=False)
        plan_file = run_dir / "plan.jsonl"
        plan_file.write_bytes(plan_file.read_bytes() + b'{"tampered": true}\n')
        with pytest.raises(ValueError, match="plan"):
            _rebuild_authority(run_dir, cache_root, validate_controller=False)

    def test_rebuild_authority_rejects_tampered_receipt(self, tmp_path):
        from study02a.formal_scheduler import _rebuild_authority
        import study02a.formal_executor as fe
        run_dir, cache_root, fit_id = _build_real_run(tmp_path)
        receipt_file = sorted((run_dir / "receipts").glob("*.succeeded.json"))[0]
        forged = json.loads(receipt_file.read_text(encoding="utf-8"))
        forged["owner_id"] = "tampered"
        receipt_file.write_bytes(fe._canonical(forged))
        with pytest.raises(ValueError):
            _rebuild_authority(run_dir, cache_root, validate_controller=False)

    def test_derive_cohort_rejects_non_succeeded_fit(self, tmp_path):
        from study02a.formal_g3_control import (
            G3RunChain, G3Authority, derive_g3_cohort_from_authority,
        )
        from study02a.config import load_frozen_config
        frozen = load_frozen_config(STUDY_ROOT)
        run_dir, cache_root, fit_id = _build_real_run(tmp_path)
        chain = G3RunChain(
            ae1_run_id="r1", ae1_run_dir=run_dir,
            ae3_run_id="r3", ae3_run_dir=run_dir,
            ae2_run_id="r2", ae2_run_dir=run_dir,
            ae1_authority_sha256="a1" * 32, ae3_authority_sha256="a3" * 32,
            ae2_authority_sha256="a2" * 32,
        )
        fake_state = {"fit_states": {fit_id: "succeeded"}, "live_claim": None}
        empty_state = {"fit_states": {}, "live_claim": None}
        authority = G3Authority(
            ae1_manifest={}, ae1_plan=[], ae1_state=fake_state, ae1_events=[],
            ae3_manifest={}, ae3_plan=[], ae3_state=empty_state, ae3_events=[],
            ae2_manifest={}, ae2_plan=[], ae2_state=empty_state, ae2_events=[],
        )
        with pytest.raises(ValueError, match="not terminal succeeded"):
            derive_g3_cohort_from_authority(frozen_config=frozen, chain=chain, authority=authority)

    def test_resolve_placeholders_rejects_unresolved(self, tmp_path):
        from study02a.formal_g3_control import _resolve_or_fail
        resolutions = {"A-E1": {}, "A-E3": {}, "A-E2": {}}
        with pytest.raises(ValueError, match="unresolved"):
            _resolve_or_fail("selected:A-E1_architecture", "architecture", "A-E1", "G3-fit-0001", resolutions)
        with pytest.raises(ValueError, match="unresolved"):
            _resolve_or_fail("selected_top_1", "architecture", "A-E1", "G3-fit-0002", resolutions)

    def test_resolve_placeholders_succeeds_with_evidence(self, tmp_path):
        from study02a.formal_g3_control import _resolve_or_fail
        resolutions = {"A-E1": {"selected:A-E1_architecture": "m05"}, "A-E3": {}, "A-E2": {}}
        assert _resolve_or_fail("selected:A-E1_architecture", "architecture", "A-E1", "G3-fit-0001", resolutions) == "m05"
        assert _resolve_or_fail("m05", "architecture", "A-E1", "G3-fit-0002", resolutions) == "m05"

    def test_verify_authority_rejects_live_claim(self, tmp_path):
        from study02a.formal_g3_control import (
            G3RunChain, G3Authority, verify_g3_chain_authority,
        )
        from study02a.formal_scheduler import materialize_run, claim_next_fit
        matrix_path = STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv"
        if not matrix_path.is_file():
            pytest.skip("G3 matrix not available")
        artifact_root = tmp_path / "artifacts"
        cache_root = tmp_path / "cache"
        try:
            result = materialize_run(
                study_root=STUDY_ROOT, matrix_path=matrix_path, module_id="A-E1",
                run_id="G3-live-claim", artifact_root=artifact_root, cache_root=cache_root, predecessor=None,
            )
        except ValueError as exc:
            if "dirty" in str(exc):
                pytest.skip("Study02 code tree is dirty (commit first)")
            raise
        run_dir = Path(result["run_dir"])
        claim_next_fit(run_dir, cache_root=cache_root, owner_id="w1", owner_nonce="n1", timestamp="T1")
        chain = G3RunChain(
            ae1_run_id="G3-live-claim", ae1_run_dir=run_dir,
            ae3_run_id="G3-live-claim", ae3_run_dir=run_dir,
            ae2_run_id="G3-live-claim", ae2_run_dir=run_dir,
            ae1_authority_sha256="a1" * 32, ae3_authority_sha256="a3" * 32,
            ae2_authority_sha256="a2" * 32,
        )
        with pytest.raises(ValueError, match="live claim"):
            verify_g3_chain_authority(chain=chain, cache_root=cache_root)
