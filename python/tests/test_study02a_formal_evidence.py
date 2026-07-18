"""Selection evidence + pre-unseal bundle tests (v2 DecisionSpec-driven schema).

These tests lock the v2 fail-closed evidence layer: per-(n, seed) supporting
evidence, the full-context supporting_evidence_sha256, the independent pre-unseal
DecisionSpec rebuild (expected support from the frozen plan, never from actual
rows), candidate-level ``selected`` consistency (failed fits may belong to the
winning candidate), and the attack surface (relabel / missing / extra / duplicate /
tamper). Bundle fixtures use a REAL frozen-matrix decision scope (A-E1
architecture:F2:n10, two-architecture subset) so pre-unseal rebuilds the same
DecisionSpec the publisher used.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import sys
from typing import Mapping

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.config import load_frozen_config  # noqa: E402
from study02a.formal_contracts import (  # noqa: E402
    build_ceiling_hit_report,
    build_fit_status_record,
    build_leakage_audit,
    build_pre_unseal_bundle,
    write_ceiling_hit_report,
    write_fit_status,
    write_leakage_audit,
    write_pre_unseal_bundle,
)
from study02a.matrix import expand_module_matrix  # noqa: E402
from study02a.selection import (  # noqa: E402
    DecisionSpec,
    FitEvaluation,
    SupportKey,
    build_decision_specs,
    build_selection_trace,
    candidate_supporting_evidence,
)
from study02a.training import FitResult  # noqa: E402


SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
EFFECTIVE_SHA = "44fba47c7af66166e1d3f11890299a8bb5c352ac1abf3447cd00cfd3acf97449"
FROZEN = load_frozen_config(STUDY_ROOT)
MATRIX_ROWS = expand_module_matrix(FROZEN).to_dict("records")


def _fit(*, epochs=100, curve=None, checkpoint_sha: str = SHA_A) -> FitResult:
    values = tuple(curve or [1.0 / (index + 1) for index in range(epochs)])
    return FitResult(
        predictions=None,
        checkpoint_sha256=checkpoint_sha,
        best_validation_loss=min(values),
        best_epoch=values.index(min(values)),
        actual_epochs=len(values),
        validation_loss_history=values,
        early_stop_reason="max_epochs" if len(values) == 100 else "patience_exhausted",
        hit_epoch_ceiling=len(values) == 100,
    )


# --------------------------------------------------------------------------
# A real frozen-matrix decision scope: A-E1 architecture:F2:n10, two architectures.
# The manifest declares exactly these fit ids so pre-unseal rebuilds one decision
# with two candidates -- the same authority the publisher used.
# --------------------------------------------------------------------------


def _ae1_f2_scope() -> tuple[list[dict], DecisionSpec]:
    f2_stage1 = [r for r in MATRIX_ROWS if r["module"] == "A-E1" and r["route"] == "F2"
                 and r["fit_kind"] == "search_stage1"]
    architectures = sorted({r["architecture"] for r in f2_stage1})[:2]
    scope_rows = [r for r in f2_stage1 if r["architecture"] in architectures]
    assert len(scope_rows) == 6  # 2 architectures x 3 screening seeds
    specs = build_decision_specs("A-E1", scope_rows)
    assert len(specs) == 1 and len(specs[0].candidates) == 2
    return scope_rows, specs[0]


def _status_for(row: Mapping, *, selection_score: float, selected: bool, checkpoint_sha: str = SHA_A):
    return build_fit_status_record(
        fit_id=row["fit_id"], module_id="A-E1", rule_id=row["rule_id"], route_id=row["route"],
        n=int(row["n"]), seed=int(row["seed"]), decision_id=row["_decision_id"],
        candidate_id=row["candidate_id"], selected=selected,
        result=_fit(curve=[1.0] * 100, checkpoint_sha=checkpoint_sha),
        selection_score=selection_score,
    )


def _selection_fixture(*, run_id: str = "G3-AE1-formal-v1", candidate_scores: dict[str, float] | None = None,
                       checkpoint_shas: dict[str, str] | None = None):
    """Build a full v2 selection fixture over the A-E1 F2 two-architecture scope.

    Returns (scope_rows_with_decision, spec, records, evaluations_by_fit). The
    decision_id/candidate_id are written onto each scope row so fit_status and the
    authority agree exactly.
    """
    scope_rows, spec = _ae1_f2_scope()
    scores = candidate_scores or {spec.candidates[0].candidate_id: 0.10,
                                  spec.candidates[1].candidate_id: 0.20}
    shas = checkpoint_shas or {}
    rows_out: list[dict] = []
    evaluations: dict[str, FitEvaluation] = {}
    for candidate in spec.candidates:
        score = float(scores[candidate.candidate_id])
        for idx, key in enumerate(candidate.support_keys):
            fit_id = candidate.support_for(key)
            matrix_row = next(r for r in scope_rows if r["fit_id"] == fit_id)
            row = {**matrix_row, "_decision_id": spec.decision_id, "candidate_id": candidate.candidate_id}
            rows_out.append(row)
            checkpoint = shas.get(candidate.candidate_id, SHA_A if idx == 0 else SHA_B)
            evaluations[fit_id] = FitEvaluation(
                fit_id=fit_id, support_key=key, failed=False, checkpoint_sha256=checkpoint,
                selection_score=score, failure_penalty=0.0,
            )
    records = build_selection_trace(module_id="A-E1", run_id=run_id, specs=(spec,), evaluations_by_fit=evaluations)
    return rows_out, spec, records, evaluations


# --------------------------------------------------------------------------
# fit_status record contract.
# --------------------------------------------------------------------------


def test_fit_status_records_success_and_failure_without_invented_values(tmp_path):
    success = build_fit_status_record(
        fit_id="G3-fit-0000", module_id="A-E1", rule_id="A-E1_historical", route_id="F2",
        n=10, seed=420101, decision_id="d", candidate_id="candidate-a", selected=True,
        result=_fit(), selection_score=0.5,
    )
    failure = build_fit_status_record(
        fit_id="fit-2", module_id="A-E1", rule_id="rule-1", route_id="S", n=15, seed=420102,
        decision_id="d", candidate_id="candidate-b", selected=False, failure_penalty=10.0,
        failure_message="optimizer failed",
    )
    assert success["best_epoch_one_based"] == 100
    assert success["selection_score"] == 0.5
    assert success["failure_penalty"] == ""
    assert failure["failed"] is True
    assert failure["checkpoint_sha256"] == ""
    assert failure["selection_score"] == ""
    assert failure["failure_penalty"] == 10.0
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
            fit_id="fit-bad", module_id="A-E1", rule_id="r", route_id="F1", n=5, seed=420101,
            decision_id="d", candidate_id="c", selected=False, result=bad, selection_score=0.5,
        )


def test_failed_fit_may_belong_to_winning_candidate():
    # R2 #4: a failed supporting fit may carry selected=True (belongs to the selected
    # candidate); only candidate-level consistency is enforced, not "failed cannot be selected".
    failed_selected = build_fit_status_record(
        fit_id="G3-fit-0000", module_id="A-E1", rule_id="A-E1_historical", route_id="F2",
        n=10, seed=420101, decision_id="d", candidate_id="winner", selected=True,
        failure_penalty=10.0, failure_message="transparent failure on a winning-candidate seed",
    )
    assert failed_selected["failed"] is True
    assert failed_selected["selected"] is True


# --------------------------------------------------------------------------
# Selection trace (v2) via the DecisionSpec engine.
# --------------------------------------------------------------------------


def test_selection_trace_is_deterministic_and_writes_once(tmp_path):
    rows_out, spec, records, _ = _selection_fixture()
    path = tmp_path / "selection_trace.jsonl"
    from study02a.formal_contracts import write_selection_trace
    digest = write_selection_trace(path, records)
    assert digest == hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        write_selection_trace(path, records)
    written = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert {r["candidate_id"] for r in written} == {spec.candidates[0].candidate_id, spec.candidates[1].candidate_id}
    assert sum(1 for r in written if r["selected"]) == 1
    # winner is the lower-score candidate (lowest_aggregate), computed not supplied
    winner = next(r for r in written if r["selected"])
    assert winner["validation_score"] == min(r["validation_score"] for r in written)


def test_supporting_evidence_hash_is_full_context_and_tamper_sensitive():
    rows_out, spec, records, evaluations = _selection_fixture()
    by_cand = {r["candidate_id"]: r for r in records}
    cand = spec.candidates[0]
    evals = {key: evaluations[cand.support_for(key)] for key in cand.support_keys}
    base = candidate_supporting_evidence(module_id="A-E1", run_id="G3-AE1-formal-v1", candidate=cand, evaluations_by_support=evals)
    assert base["supporting_evidence_sha256"] == by_cand[cand.candidate_id]["supporting_evidence_sha256"]
    # tampering one fit's checkpoint sha changes the hash
    tampered_key = cand.support_keys[0]
    tampered = dict(evals)
    tampered[tampered_key] = FitEvaluation(
        fit_id=cand.support_for(tampered_key), support_key=tampered_key, failed=False,
        checkpoint_sha256="d" * 64, selection_score=evals[tampered_key].selection_score, failure_penalty=0.0)
    changed = candidate_supporting_evidence(module_id="A-E1", run_id="G3-AE1-formal-v1", candidate=cand, evaluations_by_support=tampered)
    assert changed["supporting_evidence_sha256"] != base["supporting_evidence_sha256"]


# --------------------------------------------------------------------------
# Ceiling report + leakage audit (unchanged contracts).
# --------------------------------------------------------------------------


def test_ceiling_report_groups_and_derives_frozen_last_ten_slope(tmp_path):
    curve = [float(20 - index) for index in range(20)] + [float(0 - index) for index in range(80)]
    row = build_fit_status_record(
        fit_id="fit-1", module_id="A-E1", rule_id="A-E1_historical", route_id="F2", n=10, seed=420101,
        decision_id="d", candidate_id="candidate-a", selected=False, result=_fit(curve=curve), selection_score=0.5,
    )
    failed = build_fit_status_record(
        fit_id="fit-failed", module_id="A-E1", rule_id="A-E1_historical", route_id="F2", n=10, seed=420101,
        decision_id="d", candidate_id="candidate-a", selected=False, failure_penalty=10.0, failure_message="failed",
    )
    report = build_ceiling_hit_report([row, failed])
    group = report["groups"][0]
    assert group["fit_count"] == 2 and group["failure_count"] == 1
    assert group["fits"][0]["terminal_validation_slope"] == pytest.approx(-1.0)
    path = tmp_path / "ceiling_hit_report.json"
    write_ceiling_hit_report(path, report)
    bad_report = json.loads(json.dumps(report))
    bad_report["groups"][0]["fits"][0]["terminal_validation_slope"] = 4.0
    with pytest.raises(ValueError, match="slope"):
        write_ceiling_hit_report(tmp_path / "bad-ceiling.json", bad_report)


def _leakage_kwargs():
    return {
        "parameter_point_ids": {"training": ["tr-1"], "validation": ["va-1"],
                                "calibration": ["ca-1"], "test": ["te-1"]},
        "role_namespaces": {"training": "study02/formal/training", "validation": "study02/formal/validation",
                            "calibration": "study02/formal/calibration", "test": "study02/formal/test"},
        "scaler_source": "training_only", "feature_selection_source": "validation_only",
        "model_selection_source": "validation_only", "test_access_count": 0,
    }


def test_leakage_audit_metadata_only_contract(tmp_path):
    audit = build_leakage_audit(**_leakage_kwargs())
    path = tmp_path / "leakage_audit.json"
    write_leakage_audit(path, audit)
    bad = _leakage_kwargs()
    bad["test_access_count"] = 1
    with pytest.raises(ValueError, match="test_access_count"):
        build_leakage_audit(**bad)


# --------------------------------------------------------------------------
# Pre-unseal bundle (v2 independent DecisionSpec rebuild).
# --------------------------------------------------------------------------


def _json(path: Path, payload: dict):
    path.write_text(json.dumps(payload, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _bundle_inputs(tmp_path: Path, *, fixture=None):
    rows_out, spec, records, evaluations = fixture or _selection_fixture()
    run_id = "G3-AE1-formal-v1"
    fit_ids = [r["fit_id"] for r in rows_out]
    manifest = _json(tmp_path / "manifest.json", {
        "manifest_version": "study02-formal-v1", "module_id": "A-E1", "run_id": run_id, "code_commit": "c" * 40,
        "base_protocol": {"id": "A-G2-v1", "sha256": "f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11"},
        "base_search": {"id": "A-G2-search-v1", "sha256": "abd6d17b1d2467e1253e0154adba0b6582a3feeb83ed889534ed4f6ab5e0ca13"},
        "amendment": {"id": "A-G3-pilot-amendment-v4", "sha256": "164e72658669dbb57f6dab8b1fc80099bd319f1fa327d5dda60cb61cb929ee38"},
        "effective_config": {"sha256": EFFECTIVE_SHA, "max_epochs": 100, "min_epochs": 50, "patience": 40},
        "matrix": {"path": "experiment_matrix.csv",
                   "sha256": "fad701af2e2084bf7ce8f678d642410af58057b4ae33029c9150e50971fdf6b1",
                   "row_count": 820, "rule_ids": ["A-E1_optimized_supplement"], "fit_ids": fit_ids},
        "role_namespaces": {"training": "study02/formal/training", "validation": "study02/formal/validation"},
        "seeds": {"screening": [420001, 420002, 420003], "formal": list(range(420101, 420111))},
        "test_state": "sealed",
        "predecessor": {"module_id": "none", "run_id": "none", "selection_trace_path": "none",
                        "selection_trace_sha256": "none", "selection_receipt_path": "none",
                        "selection_receipt_sha256": "none", "selection_ledger_path": "none"},
    })
    trace = tmp_path / "selection_trace.jsonl"
    from study02a.formal_contracts import write_selection_trace
    trace_sha = write_selection_trace(trace, records)
    winner_id = next(r["candidate_id"] for r in records if r["selected"])
    fit_status_rows = []
    for row in rows_out:
        candidate = next(c for c in spec.candidates if c.candidate_id == row["candidate_id"])
        selected = row["candidate_id"] == winner_id
        evaluation = evaluations[row["fit_id"]]
        if evaluation.failed:
            fit_status_rows.append(build_fit_status_record(
                fit_id=row["fit_id"], module_id="A-E1", rule_id=row["rule_id"], route_id=row["route"],
                n=int(row["n"]), seed=int(row["seed"]), decision_id=spec.decision_id,
                candidate_id=row["candidate_id"], selected=selected, failure_penalty=float(evaluation.failure_penalty),
                failure_message="failed seed"))
        else:
            fit_status_rows.append(_status_for(row, selection_score=float(evaluation.selection_score),
                                               selected=selected, checkpoint_sha=evaluation.checkpoint_sha256))
    fit_status = tmp_path / "fit_status.csv"
    write_fit_status(fit_status, fit_status_rows)
    receipt_payload = {"receipt_version": "study02-formal-selection-v2", "module_id": "A-E1", "run_id": run_id,
                       "selection_trace_sha256": trace_sha, "effective_config_sha256": EFFECTIVE_SHA,
                       "code_commit": "c" * 40, "record_count": len(records), "decision_count": 1}
    receipt = _json(tmp_path / "selection_receipt.json", receipt_payload)
    ledger = tmp_path / "selection_ledger.jsonl"
    ledger_entry = {"binding_type": "formal-selection", **receipt_payload,
                    "receipt_sha256": hashlib.sha256(receipt.read_bytes()).hexdigest()}
    ledger.write_text(json.dumps(ledger_entry, sort_keys=True) + "\n", encoding="utf-8")
    ceiling = tmp_path / "ceiling_hit_report.json"
    write_ceiling_hit_report(ceiling, build_ceiling_hit_report(fit_status_rows))
    leakage = tmp_path / "leakage_audit.json"
    write_leakage_audit(leakage, **_leakage_kwargs())
    return {
        "formal_manifests": [manifest], "selection_traces": [trace], "selection_receipts": [receipt],
        "fit_status_path": fit_status, "selection_ledger_path": ledger, "ceiling_report_path": ceiling,
        "leakage_audit_path": leakage, "code_commit": "c" * 40, "effective_config_sha256": EFFECTIVE_SHA,
        "module_run_ids": {"A-E1": run_id},
    }


def test_pre_unseal_bundle_rebuilds_decision_spec_and_binds_evidence(tmp_path):
    kwargs = _bundle_inputs(tmp_path)
    bundle = build_pre_unseal_bundle(**kwargs)
    assert bundle["test_state"] == "sealed"
    assert bundle["bundle_version"] == "study02-pre-unseal-v2"
    assert bundle["module_run_ids"] == {"A-E1": "G3-AE1-formal-v1"}


def _rewrite_fit_evidence(kwargs, mutation):
    fit_path = kwargs["fit_status_path"]
    with fit_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    mutation(rows)
    fit_path.unlink()
    write_fit_status(fit_path, rows)
    ceiling_path = kwargs["ceiling_report_path"]
    ceiling_path.unlink()
    write_ceiling_hit_report(ceiling_path, build_ceiling_hit_report(rows))


def test_bundle_rejects_fit_relabelled_to_other_decision_or_candidate(tmp_path):
    kwargs = _bundle_inputs(tmp_path)
    _rewrite_fit_evidence(kwargs, lambda rows: rows[0].update(decision_id="forged-decision"))
    with pytest.raises(ValueError, match="relabelled"):
        build_pre_unseal_bundle(**kwargs)


def test_bundle_rejects_fit_with_wrong_n_or_seed(tmp_path):
    kwargs = _bundle_inputs(tmp_path)
    _rewrite_fit_evidence(kwargs, lambda rows: rows[0].update(n=999))
    with pytest.raises(ValueError, match="disagrees with frozen expected|support"):
        build_pre_unseal_bundle(**kwargs)


def test_bundle_rejects_missing_support_fit(tmp_path):
    kwargs = _bundle_inputs(tmp_path)
    _rewrite_fit_evidence(kwargs, lambda rows: rows.pop(0))  # drop one support fit
    with pytest.raises(ValueError, match="cover exactly|support"):
        build_pre_unseal_bundle(**kwargs)


def test_bundle_rejects_duplicate_fit_id(tmp_path):
    kwargs = _bundle_inputs(tmp_path)
    _rewrite_fit_evidence(kwargs, lambda rows: rows.append(dict(rows[0])))
    with pytest.raises(ValueError, match="duplicate fit_id"):
        build_pre_unseal_bundle(**kwargs)


def test_bundle_rejects_cross_candidate_fit_reuse(tmp_path):
    # Hand-build fit_status where one fit_id is duplicated under two candidates.
    rows_out, spec, records, evaluations = _selection_fixture()
    winner_id = next(r["candidate_id"] for r in records if r["selected"])
    fit_status_rows = []
    for row in rows_out:
        selected = row["candidate_id"] == winner_id
        fit_status_rows.append(_status_for(row, selection_score=float(evaluations[row["fit_id"]].selection_score),
                                           selected=selected))
    # Relabel the second candidate's first fit to reuse the first candidate's fit_id.
    fit_status_rows[len(fit_status_rows) // 2]["fit_id"] = fit_status_rows[0]["fit_id"]
    kwargs = _bundle_inputs(tmp_path)
    fit_path = kwargs["fit_status_path"]
    fit_path.unlink()
    write_fit_status(fit_path, fit_status_rows)
    kwargs["ceiling_report_path"].unlink()
    write_ceiling_hit_report(kwargs["ceiling_report_path"], build_ceiling_hit_report(fit_status_rows))
    with pytest.raises(ValueError, match="duplicate fit_id"):
        build_pre_unseal_bundle(**kwargs)


def test_bundle_rejects_tampered_checkpoint_score(tmp_path):
    kwargs = _bundle_inputs(tmp_path)
    _rewrite_fit_evidence(kwargs, lambda rows: rows[0].update(selection_score="9.999"))
    with pytest.raises(ValueError, match="supporting evidence SHA|aggregate"):
        build_pre_unseal_bundle(**kwargs)


def test_bundle_rejects_inconsistent_selected_membership(tmp_path):
    # R2 #4: two supporting rows of the SAME candidate carry different selected flags.
    # rows_out orders winner (candidates[0]) rows first; flip one of them to un-selected.
    kwargs = _bundle_inputs(tmp_path)
    _rewrite_fit_evidence(kwargs, lambda rows: rows[1].update(selected="False"))
    with pytest.raises(ValueError, match="selected membership"):
        build_pre_unseal_bundle(**kwargs)


def test_bundle_allows_failed_seed_in_winning_candidate(tmp_path):
    # R2 #4: the winning candidate may contain a failed supporting fit (selected=True).
    rows_out, spec, _, evaluations = _selection_fixture()
    winner = spec.candidates[0]
    failed_fit_id = winner.support_for(winner.support_keys[0])
    new_evals = dict(evaluations)
    new_evals[failed_fit_id] = FitEvaluation(
        fit_id=failed_fit_id, support_key=winner.support_keys[0], failed=True,
        checkpoint_sha256="", selection_score=0.0, failure_penalty=10.0)
    new_records = build_selection_trace(module_id="A-E1", run_id="G3-AE1-formal-v1", specs=(spec,), evaluations_by_fit=new_evals)
    kwargs = _bundle_inputs(tmp_path, fixture=(rows_out, spec, new_records, new_evals))
    bundle = build_pre_unseal_bundle(**kwargs)
    assert bundle["test_state"] == "sealed"


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
    elif case == "alias":
        kwargs["leakage_audit_path"] = kwargs["ceiling_report_path"]
    else:
        report = json.loads(kwargs["ceiling_report_path"].read_text(encoding="utf-8"))
        report["ceiling_hit_count"] = 0
        _json(kwargs["ceiling_report_path"], report)
    output = tmp_path / "pre_unseal_bundle.json"
    with pytest.raises((ValueError, FileNotFoundError)):
        write_pre_unseal_bundle(output, **kwargs)
    assert not output.exists()


def test_bundle_rejects_v1_selection_receipt(tmp_path):
    # R2 #5: a v1 receipt mixed into a v2 bundle must fail closed.
    kwargs = _bundle_inputs(tmp_path)
    receipt = json.loads(kwargs["selection_receipts"][0].read_text(encoding="utf-8"))
    receipt["receipt_version"] = "study02-formal-selection-v1"
    _json(kwargs["selection_receipts"][0], receipt)
    ledger = kwargs["selection_ledger_path"]
    rows = [json.loads(line) for line in ledger.read_text(encoding="utf-8").splitlines()]
    rows[0]["receipt_version"] = "study02-formal-selection-v1"
    ledger.write_text("".join(json.dumps(r, sort_keys=True) + "\n" for r in rows), encoding="utf-8")
    with pytest.raises(ValueError, match="selection receipt"):
        build_pre_unseal_bundle(**kwargs)
