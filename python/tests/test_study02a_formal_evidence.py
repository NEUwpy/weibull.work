import csv
import hashlib
import json
from pathlib import Path
import sys

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.formal_contracts import (
    build_ceiling_hit_report,
    build_fit_status_record,
    build_leakage_audit,
    build_pre_unseal_bundle,
    build_selection_trace_records,
    write_ceiling_hit_report,
    write_fit_status,
    write_leakage_audit,
    write_pre_unseal_bundle,
    write_selection_trace,
)
from study02a.training import FitResult


SHA_A = "a" * 64
SHA_B = "b" * 64
EFFECTIVE_SHA = "44fba47c7af66166e1d3f11890299a8bb5c352ac1abf3447cd00cfd3acf97449"


def _fit(*, epochs=100, curve=None) -> FitResult:
    values = tuple(curve or [1.0 / (index + 1) for index in range(epochs)])
    return FitResult(
        predictions=None,
        checkpoint_sha256=SHA_A,
        best_validation_loss=min(values),
        best_epoch=values.index(min(values)),
        actual_epochs=len(values),
        validation_loss_history=values,
        early_stop_reason="max_epochs" if len(values) == 100 else "patience_exhausted",
        hit_epoch_ceiling=len(values) == 100,
    )


def _status(fit_id="G3-fit-0000", *, selected=True, curve=None):
    return build_fit_status_record(
        fit_id=fit_id,
        module_id="A-E1",
        rule_id="A-E1_historical",
        route_id="F2",
        n=10,
        seed=420101,
        decision_id="d",
        candidate_id="candidate-a",
        selected=selected,
        result=_fit(curve=curve),
    )


def test_fit_status_records_success_and_failure_without_invented_values(tmp_path):
    success = _status()
    failure = build_fit_status_record(
        fit_id="fit-2",
        module_id="A-E1",
        rule_id="rule-1",
        route_id="S",
        n=15,
        seed=420102,
        decision_id="d",
        candidate_id="candidate-b",
        selected=False,
        failure_message="optimizer failed",
    )

    assert success["best_epoch_one_based"] == 100
    assert success["hit_epoch_100"] is True
    assert json.loads(success["validation_curve_json"])[-1] == pytest.approx(0.01)
    assert failure["failed"] is True
    assert failure["checkpoint_sha256"] == ""
    assert failure["validation_score"] == ""
    path = tmp_path / "fit_status.csv"
    write_fit_status(path, [success, failure])
    with path.open(encoding="utf-8", newline="") as handle:
        assert len(list(csv.DictReader(handle))) == 2
    with pytest.raises(FileExistsError):
        write_fit_status(path, [success])


def test_fit_status_rejects_inconsistent_or_nonfinite_diagnostics(tmp_path):
    bad = _fit()
    object.__setattr__(bad, "actual_epochs", 99)
    with pytest.raises(ValueError, match="history"):
        build_fit_status_record(
            fit_id="fit-bad", module_id="A-E1", rule_id="r", route_id="F1",
            n=5, seed=420101, decision_id="d", candidate_id="c", selected=False, result=bad,
        )
    success = _status()
    success["failure_message"] = "must be empty"
    with pytest.raises(ValueError, match="failure_message"):
        write_fit_status(tmp_path / "unused-fit-status.csv", [success])


def test_selection_trace_is_deterministic_preserves_ties_and_validates(tmp_path):
    candidates = [
        {"decision_id": "d1", "candidate_id": "z", "validation_score": 0.2,
         "tie_break_key": ["same"], "checkpoint_sha256": SHA_A},
        {"decision_id": "d1", "candidate_id": "a", "validation_score": 0.2,
         "tie_break_key": ["same"], "checkpoint_sha256": SHA_B},
        {"decision_id": "d2", "candidate_id": "x", "validation_score": 0.1,
         "tie_break_key": [1], "checkpoint_sha256": SHA_A},
    ]
    records = build_selection_trace_records("A-E1", "run-1", candidates)
    assert [row["candidate_id"] for row in records[:2]] == ["a", "z"]
    assert [row["candidate_id"] for row in records if row["selected"]] == ["a", "x"]
    path = tmp_path / "selection_trace.jsonl"
    digest = write_selection_trace(path, records)
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        write_selection_trace(path, records)
    with pytest.raises(ValueError, match="duplicate"):
        build_selection_trace_records("A-E1", "run-1", candidates + [candidates[0]])


def test_selection_trace_uses_value_order_for_tie_break_and_writer_rejects_wrong_winner(tmp_path):
    candidates = [
        {"decision_id": "d", "candidate_id": "a", "validation_score": 1.0,
         "tie_break_key": [10], "checkpoint_sha256": SHA_A},
        {"decision_id": "d", "candidate_id": "z", "validation_score": 1.0,
         "tie_break_key": [2], "checkpoint_sha256": SHA_B},
    ]
    records = list(build_selection_trace_records("A-E1", "run-1", candidates))
    assert [row["candidate_id"] for row in records if row["selected"]] == ["z"]
    records[0]["selected"] = not records[0]["selected"]
    records[1]["selected"] = not records[1]["selected"]
    with pytest.raises(ValueError, match="rank"):
        write_selection_trace(tmp_path / "wrong.jsonl", records)


def test_selection_trace_writer_canonicalizes_decision_and_candidate_order(tmp_path):
    candidates = [
        {"decision_id": "z-decision", "candidate_id": "b", "validation_score": 2.0,
         "tie_break_key": [2], "checkpoint_sha256": SHA_A},
        {"decision_id": "a-decision", "candidate_id": "x", "validation_score": 1.0,
         "tie_break_key": [1], "checkpoint_sha256": SHA_B},
        {"decision_id": "z-decision", "candidate_id": "a", "validation_score": 1.0,
         "tie_break_key": [1], "checkpoint_sha256": SHA_B},
    ]
    records = list(build_selection_trace_records("A-E1", "run-1", candidates))
    first = tmp_path / "first.jsonl"
    second = tmp_path / "second.jsonl"
    write_selection_trace(first, records)
    write_selection_trace(second, list(reversed(records)))
    assert first.read_bytes() == second.read_bytes()


def test_selection_trace_writer_rejects_extra_fields(tmp_path):
    records = list(build_selection_trace_records("A-E1", "run-1", [{
        "decision_id": "d", "candidate_id": "a", "validation_score": 1.0,
        "tie_break_key": ["a"], "checkpoint_sha256": SHA_A,
    }]))
    records[0]["extra"] = "forbidden"
    with pytest.raises(ValueError, match="schema"):
        write_selection_trace(tmp_path / "extra.jsonl", records)


def test_ceiling_report_groups_and_derives_frozen_last_ten_slope(tmp_path):
    curve = [float(20 - index) for index in range(20)] + [float(0 - index) for index in range(80)]
    row = _status(curve=curve)
    failed = build_fit_status_record(
        fit_id="fit-failed", module_id="A-E1", rule_id="A-E1_historical", route_id="F2",
        n=10, seed=420101, decision_id="d", candidate_id="candidate-a", selected=True,
        failure_message="failed",
    )
    report = build_ceiling_hit_report([row, failed])
    group = report["groups"][0]
    assert group["fit_count"] == 2
    assert group["failure_count"] == 1
    assert group["ceiling_hit_count"] == 1
    assert group["fits"][0]["terminal_validation_slope"] == pytest.approx(-1.0)
    path = tmp_path / "ceiling_hit_report.json"
    write_ceiling_hit_report(path, report)
    bad_report = json.loads(json.dumps(report))
    bad_report["groups"][0]["fits"][0]["terminal_validation_slope"] = 4.0
    with pytest.raises(ValueError, match="slope"):
        write_ceiling_hit_report(tmp_path / "bad-ceiling.json", bad_report)
    with pytest.raises(ValueError, match="history"):
        build_ceiling_hit_report([{**row, "actual_epochs": 99}])


def test_ceiling_report_keeps_selected_candidate_arms_separate():
    first = _status("fit-a", selected=True)
    second = {**_status("fit-b", selected=True), "candidate_id": "candidate-b"}
    report = build_ceiling_hit_report([first, second])
    assert len(report["groups"]) == 2
    assert {group["selected_arm"] for group in report["groups"]} == {"candidate-a", "candidate-b"}


def _leakage_kwargs():
    return {
        "parameter_point_ids": {
            "training": ["tr-1"], "validation": ["va-1"],
            "calibration": ["ca-1"], "test": ["te-1"],
        },
        "role_namespaces": {
            "training": "study02/formal/training",
            "validation": "study02/formal/validation",
            "calibration": "study02/formal/calibration",
            "test": "study02/formal/test",
        },
        "scaler_source": "training_only",
        "feature_selection_source": "validation_only",
        "model_selection_source": "validation_only",
        "test_access_count": 0,
    }


def test_leakage_audit_metadata_only_contract_and_no_write_on_violation(tmp_path):
    audit = build_leakage_audit(**_leakage_kwargs())
    assert audit["pairwise_intersections"] == {
        "calibration:test": 0, "training:calibration": 0, "training:test": 0,
        "training:validation": 0, "validation:calibration": 0, "validation:test": 0,
    }
    path = tmp_path / "leakage_audit.json"
    write_leakage_audit(path, audit)
    bad_audit = dict(audit, scaler_source="validation_only")
    with pytest.raises(ValueError, match="scaler_source"):
        write_leakage_audit(tmp_path / "bad-audit.json", bad_audit)
    bad = _leakage_kwargs()
    bad["parameter_point_ids"]["test"] = ["tr-1"]
    missing = tmp_path / "not-written.json"
    with pytest.raises(ValueError, match="intersection"):
        write_leakage_audit(missing, **bad)
    assert not missing.exists()
    bad = _leakage_kwargs()
    bad["test_access_count"] = 1
    with pytest.raises(ValueError, match="test_access_count"):
        build_leakage_audit(**bad)


def _json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _bundle_inputs(tmp_path: Path):
    manifest = _json(tmp_path / "manifest.json", {
        "manifest_version": "study02-formal-v1",
        "module_id": "A-E1", "run_id": "run-1", "code_commit": "c" * 40,
        "base_protocol": {
            "id": "A-G2-v1",
            "sha256": "f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11",
        },
        "base_search": {
            "id": "A-G2-search-v1",
            "sha256": "abd6d17b1d2467e1253e0154adba0b6582a3feeb83ed889534ed4f6ab5e0ca13",
        },
        "amendment": {
            "id": "A-G3-pilot-amendment-v4",
            "sha256": "164e72658669dbb57f6dab8b1fc80099bd319f1fa327d5dda60cb61cb929ee38",
        },
        "effective_config": {"sha256": EFFECTIVE_SHA, "max_epochs": 100, "min_epochs": 50, "patience": 40},
        "matrix": {
            "path": "experiment_matrix.csv",
            "sha256": "fad701af2e2084bf7ce8f678d642410af58057b4ae33029c9150e50971fdf6b1",
            "row_count": 820,
            "rule_ids": ["A-E1_historical"],
            "fit_ids": ["G3-fit-0000"],
        },
        "role_namespaces": {"training": "study02/formal/training", "validation": "study02/formal/validation"},
        "seeds": {"screening": [420001, 420002, 420003], "formal": list(range(420101, 420111))},
        "test_state": "sealed",
        "predecessor": {
            "module_id": "none", "run_id": "none", "selection_trace_path": "none",
            "selection_trace_sha256": "none", "selection_receipt_path": "none",
            "selection_receipt_sha256": "none", "selection_ledger_path": "none",
        },
    })
    trace = tmp_path / "selection_trace.jsonl"
    records = build_selection_trace_records("A-E1", "run-1", [
        {"decision_id": "d", "candidate_id": "candidate-a", "validation_score": 1.0,
         "tie_break_key": ["a"], "checkpoint_sha256": SHA_A},
        {"decision_id": "d", "candidate_id": "candidate-b", "validation_score": 2.0,
         "tie_break_key": ["b"], "checkpoint_sha256": SHA_B},
    ])
    trace_sha = write_selection_trace(trace, records)
    receipt_payload = {
        "module_id": "A-E1", "run_id": "run-1", "selection_trace_sha256": trace_sha,
        "effective_config_sha256": EFFECTIVE_SHA, "code_commit": "c" * 40,
        "record_count": 2, "decision_count": 1,
        "receipt_version": "study02-formal-selection-v1",
    }
    receipt = _json(tmp_path / "selection_receipt.json", receipt_payload)
    ledger = tmp_path / "selection_ledger.jsonl"
    ledger_entry = {
        "binding_type": "formal-selection",
        **receipt_payload,
        "receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest(),
    }
    ledger.write_text(json.dumps(ledger_entry, sort_keys=True) + "\n", encoding="utf-8")
    fit_status = tmp_path / "fit_status.csv"
    write_fit_status(fit_status, [_status()])
    ceiling = tmp_path / "ceiling_hit_report.json"
    write_ceiling_hit_report(ceiling, build_ceiling_hit_report([_status()]))
    leakage = tmp_path / "leakage_audit.json"
    write_leakage_audit(leakage, **_leakage_kwargs())
    return {
        "formal_manifests": [manifest], "selection_traces": [trace],
        "selection_receipts": [receipt], "fit_status_path": fit_status,
        "selection_ledger_path": ledger,
        "ceiling_report_path": ceiling, "leakage_audit_path": leakage,
        "code_commit": "c" * 40, "effective_config_sha256": EFFECTIVE_SHA,
        "module_run_ids": {"A-E1": "run-1"},
    }


def _sync_trace_receipt_and_ledger(kwargs, records):
    trace = kwargs["selection_traces"][0]
    trace.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in records), encoding="utf-8")
    receipt_path = kwargs["selection_receipts"][0]
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["selection_trace_sha256"] = hashlib.sha256(trace.read_bytes()).hexdigest()
    _json(receipt_path, receipt)
    ledger_entry = {
        "binding_type": "formal-selection", **receipt,
        "receipt_sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
    }
    kwargs["selection_ledger_path"].write_text(
        json.dumps(ledger_entry, sort_keys=True) + "\n", encoding="utf-8"
    )


@pytest.mark.parametrize(("case", "match"), [("wrong_winner", "rank"), ("extra", "schema"), ("order", "canonical")])
def test_bundle_rejects_invalid_trace_even_when_hash_receipt_and_ledger_are_synchronized(tmp_path, case, match):
    kwargs = _bundle_inputs(tmp_path)
    records = [json.loads(line) for line in kwargs["selection_traces"][0].read_text(encoding="utf-8").splitlines()]
    if case == "wrong_winner":
        records[0]["selected"] = False
        records[1]["selected"] = True
    elif case == "extra":
        records[0]["extra"] = "forbidden"
    else:
        records.reverse()
    _sync_trace_receipt_and_ledger(kwargs, records)
    with pytest.raises(ValueError, match=match):
        build_pre_unseal_bundle(**kwargs)


def _rewrite_fit_evidence(kwargs, mutation):
    fit_path = kwargs["fit_status_path"]
    with fit_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mutation(rows[0])
    fit_path.unlink()
    write_fit_status(fit_path, rows)
    ceiling_path = kwargs["ceiling_report_path"]
    ceiling_path.unlink()
    write_ceiling_hit_report(ceiling_path, build_ceiling_hit_report(rows))


@pytest.mark.parametrize(
    "mutation",
    [
        lambda row: row.update(module_id="A-E3"),
        lambda row: row.update(fit_id="G3-fit-0030"),
        lambda row: row.update(rule_id="A-E1_controlled"),
        lambda row: row.update(decision_id="missing-decision"),
        lambda row: row.update(candidate_id="missing-candidate"),
        lambda row: row.update(selected="False"),
        lambda row: row.update(checkpoint_sha256=SHA_B),
    ],
)
def test_bundle_binds_every_fit_status_row_to_manifest_and_selection_trace(tmp_path, mutation):
    kwargs = _bundle_inputs(tmp_path)
    _rewrite_fit_evidence(kwargs, mutation)
    with pytest.raises(ValueError, match="fit status"):
        build_pre_unseal_bundle(**kwargs)


@pytest.mark.parametrize("case", ["missing", "tamper", "duplicate", "conflict"])
def test_bundle_requires_one_exact_global_ledger_binding_per_module(tmp_path, case):
    kwargs = _bundle_inputs(tmp_path)
    ledger = kwargs["selection_ledger_path"]
    if case == "missing":
        ledger.unlink()
    else:
        rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
        if case == "tamper":
            rows[0]["selection_trace_sha256"] = "0" * 64
        elif case == "duplicate":
            rows.append(dict(rows[0]))
        else:
            conflict = dict(rows[0])
            conflict["receipt_sha256"] = "0" * 64
            rows.append(conflict)
        ledger.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    with pytest.raises((ValueError, FileNotFoundError), match="ledger|artifact"):
        build_pre_unseal_bundle(**kwargs)


def test_pre_unseal_bundle_hashes_validated_artifacts_and_refuses_overwrite(tmp_path):
    kwargs = _bundle_inputs(tmp_path)
    bundle = build_pre_unseal_bundle(**kwargs)
    assert bundle["test_state"] == "sealed"
    assert bundle["module_run_ids"] == {"A-E1": "run-1"}
    assert bundle["selection_trace_hashes"]["A-E1"] == hashlib.sha256(
        kwargs["selection_traces"][0].read_bytes()
    ).hexdigest()
    output = tmp_path / "pre_unseal_bundle.json"
    write_pre_unseal_bundle(output, **kwargs)
    with pytest.raises(FileExistsError):
        write_pre_unseal_bundle(output, **kwargs)


@pytest.mark.parametrize(
    ("mutation", "match"),
    [
        (lambda manifest: manifest.pop("base_protocol"), "manifest"),
        (lambda manifest: manifest["effective_config"].update(max_epochs=500), "max_epochs"),
        (lambda manifest: manifest["matrix"].update(row_count=819), "matrix"),
        (lambda manifest: manifest["matrix"].update(rule_ids=["A-E1_replacement"]), "subset"),
        (lambda manifest: manifest["seeds"].update(formal=[420101]), "formal"),
        (lambda manifest: manifest.update(extra="replacement"), "schema"),
    ],
)
def test_pre_unseal_bundle_rejects_truncated_or_replaced_formal_manifest(tmp_path, mutation, match):
    kwargs = _bundle_inputs(tmp_path)
    path = kwargs["formal_manifests"][0]
    manifest = json.loads(path.read_text(encoding="utf-8"))
    mutation(manifest)
    _json(path, manifest)
    with pytest.raises(ValueError, match=match):
        build_pre_unseal_bundle(**kwargs)


def test_pre_unseal_bundle_reads_each_artifact_bytes_once(tmp_path, monkeypatch):
    kwargs = _bundle_inputs(tmp_path)
    artifacts = {
        path.resolve()
        for path in [
            *kwargs["formal_manifests"], *kwargs["selection_traces"], *kwargs["selection_receipts"],
            kwargs["selection_ledger_path"], kwargs["fit_status_path"],
            kwargs["ceiling_report_path"], kwargs["leakage_audit_path"],
        ]
    }
    counts = {path: 0 for path in artifacts}
    original = Path.read_bytes

    def counted(path):
        resolved = path.resolve()
        if resolved in counts:
            counts[resolved] += 1
        return original(path)

    monkeypatch.setattr(Path, "read_bytes", counted)
    build_pre_unseal_bundle(**kwargs)
    assert set(counts.values()) == {1}


@pytest.mark.parametrize("case", ["missing", "tamper", "unsealed", "alias", "ceiling_tamper"])
def test_pre_unseal_bundle_fails_closed_before_publication(tmp_path, case):
    kwargs = _bundle_inputs(tmp_path)
    if case == "missing":
        kwargs["fit_status_path"].unlink()
    elif case == "tamper":
        receipt = json.loads(kwargs["selection_receipts"][0].read_text(encoding="utf-8"))
        receipt["selection_trace_sha256"] = "0" * 64
        _json(kwargs["selection_receipts"][0], receipt)
    elif case == "unsealed":
        manifest = json.loads(kwargs["formal_manifests"][0].read_text(encoding="utf-8"))
        manifest["test_state"] = "unsealed_once"
        _json(kwargs["formal_manifests"][0], manifest)
    else:
        if case == "alias":
            kwargs["leakage_audit_path"] = kwargs["ceiling_report_path"]
        else:
            report = json.loads(kwargs["ceiling_report_path"].read_text(encoding="utf-8"))
            report["ceiling_hit_count"] = 0
            _json(kwargs["ceiling_report_path"], report)
    output = tmp_path / "pre_unseal_bundle.json"
    with pytest.raises((ValueError, FileNotFoundError)):
        write_pre_unseal_bundle(output, **kwargs)
    assert not output.exists()
