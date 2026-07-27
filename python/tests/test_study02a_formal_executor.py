"""Tests for the Study/02 formal execution driver (Task 9c.3)."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import sys

import pytest
import torch


ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
sys.path.insert(0, str(STUDY_ROOT / "code"))
sys.path.insert(0, str(ROOT / "python"))

from study02a import formal_executor as fe  # noqa: E402
from study02a.config import load_frozen_config  # noqa: E402
from study02a.formal_config import load_effective_formal_config  # noqa: E402
from study02a.formal_contracts import (  # noqa: E402
    PredecessorTrace,
    publish_selection_receipt,
    write_selection_trace,
)
from study02a.formal_runner import build_training_spec, build_validation_spec  # noqa: E402
from study02a.matrix import expand_module_matrix  # noqa: E402
from study02a.models import build_mlp  # noqa: E402
from study02a.selection import (  # noqa: E402
    FitEvaluation,
    SupportKey,
    build_decision_specs,
    build_selection_trace,
)
from study02a.training import fit_candidate  # noqa: E402


FROZEN = load_frozen_config(STUDY_ROOT)
EFFECTIVE = load_effective_formal_config(STUDY_ROOT)
MATRIX_ROWS = expand_module_matrix(FROZEN).to_dict("records")


def _plan_row(**overrides):
    base = {
        "plan_version": "study02-formal-plan-row-v2", "plan_index": 0, "run_id": "r1",
        "fit_id": "G3-fit-0000", "fit_range": [0, 0], "matrix_row_sha256": "0"*64,
        "module_id": "A-E1", "rule_id": "A-E1_historical", "route": "H0_hsm",
        "distribution": "legacy_grid", "n_mode": "shared_n", "fixed_n": None,
        "loss": "raw_train_z_mse", "architecture": "historical_128_64_32",
        "optimizer": "adam_historical", "training_size": 7000, "seed": 420101,
        "effective_config_sha256": EFFECTIVE.effective_config_sha256, "code_commit": "0"*40,
        "training_cache_key": "", "validation_cache_key": "",
        "training_cache_path": "", "validation_cache_path": "",
        "predecessor_trace_sha256": "0"*64,
        "expected_outputs": [
            {"relative_path": "outputs/G3-fit-0000/checkpoint.pt", "content_type": "binary", "required": True},
            {"relative_path": "outputs/G3-fit-0000/fit_status.json", "content_type": "canonical_json", "required": True},
        ],
        "test_access_count": 0,
    }
    base.update(overrides)
    return base


def test_checkpoint_canonical_bytes_hash_to_checkpoint_sha256():
    """D1: sha256(FitResult.checkpoint_bytes) == checkpoint_sha256 (the on-disk contract)."""
    import hashlib
    tx = torch.randn(32, 4); ty = torch.randn(32, 3); vx = torch.randn(8, 4); vy = torch.randn(8, 3)
    fit = fit_candidate(lambda: build_mlp(4, [8], "relu", 0.0), (tx, ty), (vx, vy),
                        seed=1, max_epochs=2, min_epochs=1, patience=1, batch_size=16)
    assert len(fit.checkpoint_bytes) > 0
    assert hashlib.sha256(fit.checkpoint_bytes).hexdigest() == fit.checkpoint_sha256


def test_resolve_model_factory_concrete_and_fail_closed():
    mlp_factory = fe.resolve_model_factory("m05", FROZEN, input_dim=15)
    assert mlp_factory() is not None
    deep_factory = fe.resolve_model_factory("d01", FROZEN, input_dim=None)
    assert deep_factory() is not None
    hist_factory = fe.resolve_model_factory("historical_128_64_32", FROZEN, input_dim=7)
    assert hist_factory() is not None
    with pytest.raises(NotImplementedError):
        fe.resolve_model_factory("selected:A-E1_architecture", FROZEN, input_dim=15)
    with pytest.raises(NotImplementedError):
        fe.resolve_model_factory("selected_top_1", FROZEN, input_dim=15)
    with pytest.raises(ValueError):
        fe.resolve_model_factory("unknown_x", FROZEN, input_dim=15)


def test_resolve_optimizer_hyperparams_concrete_and_fail_closed():
    s1 = fe.resolve_optimizer_hyperparams("stage1", FROZEN)
    assert s1["batch_size"] == 512 and s1["lr"] == pytest.approx(1e-3)
    hist = fe.resolve_optimizer_hyperparams("adam_historical", FROZEN)
    assert hist["batch_size"] == 32
    o1 = fe.resolve_optimizer_hyperparams("o1", FROZEN)
    assert o1["batch_size"] == 128 and o1["lr"] == pytest.approx(3e-4)
    with pytest.raises(NotImplementedError):
        fe.resolve_optimizer_hyperparams("selected:A-E1_optimizer", FROZEN)


def test_resolve_loss_id_passthrough_and_fail_closed():
    assert fe.resolve_loss_id("raw_train_z_mse") == "raw_train_z_mse"
    assert fe.resolve_loss_id("transformed_train_z_huber") == "transformed_train_z_huber"
    with pytest.raises(NotImplementedError):
        fe.resolve_loss_id("selected:A-E1_loss")


def test_is_selection_dependent_defers_placeholder_fits():
    # concrete historical/controlled/stage1 fits are executable; selected:* / selected_top_* defer to D7
    assert fe._is_selection_dependent(_plan_row()) is False  # historical_128_64_32 / adam_historical
    assert fe._is_selection_dependent(_plan_row(architecture="m05", optimizer="stage1")) is False
    assert fe._is_selection_dependent(_plan_row(architecture="selected_top_1", optimizer="o1")) is True
    assert fe._is_selection_dependent(_plan_row(architecture="selected:A-E1_architecture", optimizer="selected:A-E1_optimizer")) is True


def test_reconstruct_a_e1_specs_cache_keys_match_scheduler(tmp_path):
    """The executor rebuilds the exact same spec the scheduler planned (no drift)."""
    # Build the spec the way the scheduler does, then compare cache_key to what the executor reconstructs.
    training = build_training_spec(route="H0_hsm", distribution="legacy_grid", n_mode="shared_n",
                                   fixed_n=None, training_rows=7000, frozen_config=FROZEN, effective_config=EFFECTIVE)
    validation = build_validation_spec(route="H0_hsm", distribution="legacy_grid", n_mode="shared_n",
                                       fixed_n=None, frozen_config=FROZEN, effective_config=EFFECTIVE)
    row = _plan_row(training_cache_key=training.cache_key, validation_cache_key=validation.cache_key)
    t_spec, v_spec = fe.reconstruct_a_e1_specs(row, FROZEN, EFFECTIVE)
    assert t_spec.cache_key == training.cache_key
    assert v_spec.cache_key == validation.cache_key
    # drift must fail closed:
    with pytest.raises(ValueError):
        fe.reconstruct_a_e1_specs(_plan_row(training_cache_key="0"*64, validation_cache_key=validation.cache_key), FROZEN, EFFECTIVE)


def test_run_module_rejects_non_a_e1_modules(tmp_path):
    with pytest.raises(NotImplementedError):
        fe.run_module(study_root=STUDY_ROOT, module_id="A-E3", run_id="r1",
                      artifact_root=tmp_path, cache_root=tmp_path / "cache")


# ---------------------------------------------------------------------------
# D8: placeholder resolution, deferred-spec reconstruction, pre-unseal wiring.
# Each fixture builds a real, immutable selection trace + receipt + ledger over a
# frozen-matrix decision scope, then exercises the fail-closed production path.
# No formal run is launched; no test data is opened.
# ---------------------------------------------------------------------------

_D8_RUN_ID = "G3-AE1-formal-v1"
_D8_CODE_COMMIT = "c" * 40


def _synth_point_records(fit_id: str, seed: int, base: float):
    records = []
    for p in range(2):
        for s in range(2):
            value = base + ((seed % 7) + p + s) * 0.001
            records.append({
                "sample_id": f"{fit_id}:pt{p}:s{s}", "seed_id": str(seed),
                "point_id": f"{fit_id}:pt{p}", "legal": True, "failure": 0,
                "l_param": value, "e_beta": value, "e_eta": value, "e_gamma": value,
            })
    return tuple(records)


def _d8_three_arch_fixture(candidate_scores):
    """A 3-candidate A-E1 architecture:F2:n10 decision (3 architectures x 3 screening seeds).

    Returns (spec, evaluations_by_fit) where each candidate's aggregate score is the mean of
    its synthetic per-point records (exactly as the real scoring path produces). ``candidate_scores``
    picks each candidate's base score so the ranking is deterministic.
    """
    f2_stage1 = [r for r in MATRIX_ROWS if r["module"] == "A-E1" and r["route"] == "F2"
                 and r["fit_kind"] == "search_stage1"]
    architectures = sorted({r["architecture"] for r in f2_stage1})[:3]
    scope_rows = [r for r in f2_stage1 if r["architecture"] in architectures]
    specs = build_decision_specs("A-E1", scope_rows)
    assert len(specs) == 1 and len(specs[0].candidates) == 3
    spec = specs[0]
    evaluations: dict[str, FitEvaluation] = {}
    for candidate in spec.candidates:
        base = float(candidate_scores[candidate.candidate_id])
        for key in candidate.support_keys:
            fit_id = candidate.support_for(key)
            records = _synth_point_records(fit_id, int(key.seed), base)
            aggregate = sum(record["l_param"] for record in records) / len(records)
            evaluations[fit_id] = FitEvaluation(
                fit_id=fit_id, module_id="A-E1", decision_id=spec.decision_id,
                candidate_id=candidate.candidate_id, support_key=key, failed=False,
                checkpoint_sha256=hashlib.sha256(fit_id.encode("utf-8")).hexdigest(),
                validation_identity=f"val-cache-{fit_id}", selection_score=aggregate,
                failure_penalty=0.0, point_records=records,
            )
    return spec, evaluations


def _publish_d8_evidence(tmp_path: Path, spec, evaluations, *,
                         module_id="A-E1", run_id=_D8_RUN_ID, code_commit=_D8_CODE_COMMIT):
    """Publish a real selection trace + receipt + ledger for one decision; return their paths/sha."""
    records, _diagnostics = build_selection_trace(
        module_id=module_id, run_id=run_id, specs=(spec,), evaluations_by_fit=evaluations,
    )
    trace_path = tmp_path / "selection_trace.jsonl"
    trace_sha = write_selection_trace(trace_path, records)
    publish_selection_receipt(
        receipt_path=tmp_path / "selection_receipt.json",
        ledger_path=tmp_path / "selection_ledger.jsonl",
        module_id=module_id, run_id=run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=EFFECTIVE, code_commit=code_commit,
    )
    return {
        "trace_path": trace_path, "trace_sha256": trace_sha,
        "receipt_path": tmp_path / "selection_receipt.json",
        "ledger_path": tmp_path / "selection_ledger.jsonl",
        "module_id": module_id, "run_id": run_id, "records": records, "spec": spec,
    }


def _d8_evidence_kwargs(ev):
    return {
        "selection_trace_path": ev["trace_path"], "selection_trace_sha256": ev["trace_sha256"],
        "selection_receipt_path": ev["receipt_path"], "selection_ledger_path": ev["ledger_path"],
        "module_id": ev["module_id"], "run_id": ev["run_id"],
    }


def test_resolve_selected_placeholders_winner_and_top_n(tmp_path):
    """D8: selected:<decision> -> winner; selected_top_N -> rank-N candidate, from a validated trace."""
    scores = {"m01": 0.10, "m02": 0.20, "m03": 0.30}  # lowest_aggregate ranks m01 < m02 < m03
    spec, evaluations = _d8_three_arch_fixture(scores)
    ev = _publish_d8_evidence(tmp_path, spec, evaluations)
    decision_id = spec.decision_id  # architecture:A-E1:F2:n10
    resolved = fe.resolve_selected_placeholders(
        placeholders={
            f"selected:{decision_id}": None,        # winner of the named decision
            "selected_top_1": decision_id,           # rank-1 (winner)
            "selected_top_2": decision_id,           # rank-2
            "selected_top_3": decision_id,           # rank-3
        },
        **_d8_evidence_kwargs(ev),
    )
    assert resolved[f"selected:{decision_id}"] == "m01"
    assert resolved["selected_top_1"] == "m01"
    assert resolved["selected_top_2"] == "m02"
    assert resolved["selected_top_3"] == "m03"
    # a second call with the same inputs is deterministic and independent of dict ordering
    again = fe.resolve_selected_placeholders(
        placeholders={"selected_top_2": decision_id, f"selected:{decision_id}": None},
        **_d8_evidence_kwargs(ev),
    )
    assert again["selected_top_2"] == "m02" and again[f"selected:{decision_id}"] == "m01"


def test_resolve_selected_placeholders_fail_closed(tmp_path):
    """D8: missing decision, out-of-bounds slot, missing rank decision, unsupported token, and
    a hand-edited / mis-bound trace all raise (never silently resolve)."""
    spec, evaluations = _d8_three_arch_fixture({"m01": 0.10, "m02": 0.20, "m03": 0.30})
    ev = _publish_d8_evidence(tmp_path, spec, evaluations)
    decision_id = spec.decision_id
    base = _d8_evidence_kwargs(ev)
    # missing decision (placeholder names a decision absent from the trace)
    with pytest.raises(ValueError, match="absent"):
        fe.resolve_selected_placeholders(placeholders={"selected:no:such:decision": None}, **base)
    # selected_top_N without a rank_decision_id
    with pytest.raises(ValueError, match="rank_decision_id"):
        fe.resolve_selected_placeholders(placeholders={"selected_top_1": None}, **base)
    # selected_top_N whose rank decision is absent
    with pytest.raises(ValueError, match="missing from the selection trace"):
        fe.resolve_selected_placeholders(placeholders={"selected_top_1": "architecture:A-E1:V:n10"}, **base)
    # out-of-bounds slot (only 3 candidates)
    with pytest.raises(ValueError, match="out of bounds"):
        fe.resolve_selected_placeholders(placeholders={"selected_top_4": decision_id}, **base)
    # non-integer slot
    with pytest.raises(ValueError, match="positive integer"):
        fe.resolve_selected_placeholders(placeholders={"selected_top_X": decision_id}, **base)
    # unsupported token (not a selected:* / selected_top_ placeholder)
    with pytest.raises(ValueError, match="unsupported placeholder"):
        fe.resolve_selected_placeholders(placeholders={"historical_128_64_32": None}, **base)
    # trace SHA mismatch (a hand-edited trace cannot substitute for the immutable authority)
    bad_sha = dict(base, selection_trace_sha256="0" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        fe.resolve_selected_placeholders(placeholders={"selected_top_1": decision_id}, **bad_sha)
    # module/run ownership mismatch
    bad_run = dict(base, run_id="other-run")
    with pytest.raises(ValueError, match="ownership"):
        fe.resolve_selected_placeholders(placeholders={"selected_top_1": decision_id}, **bad_run)


def test_resolve_selected_placeholders_rejects_unbound_ledger(tmp_path):
    """D8: a trace whose receipt/ledger binding is broken (double consumption / missing receipt)
    is rejected before any placeholder resolves."""
    spec, evaluations = _d8_three_arch_fixture({"m01": 0.10, "m02": 0.20, "m03": 0.30})
    ev = _publish_d8_evidence(tmp_path, spec, evaluations)
    decision_id = spec.decision_id
    # append a SECOND ledger binding for the same module/run -> double consumption
    with ev["ledger_path"].open("a", encoding="utf-8") as handle:
        import json as _json
        receipt = _json.loads(ev["receipt_path"].read_text(encoding="utf-8"))
        extra = {"binding_type": "formal-selection", **receipt,
                 "receipt_sha256": hashlib.sha256(ev["receipt_path"].read_bytes()).hexdigest()}
        handle.write(_json.dumps(extra, sort_keys=True) + "\n")
    with pytest.raises(ValueError, match="exactly one binding"):
        fe.resolve_selected_placeholders(placeholders={"selected_top_1": decision_id}, **_d8_evidence_kwargs(ev))


def _deferred_cache_key(role, *, route, distribution, n_mode, fixed_n, training_size, pred_sha):
    spec = fe._DeferredDatasetSpec(
        role=role, schema_version="study02-formal-deferred-dataset-v1", route=route,
        distribution=distribution, n_mode=n_mode, fixed_n=fixed_n, training_size=training_size,
        effective_config_sha256=EFFECTIVE.effective_config_sha256,
        predecessor_trace_sha256=pred_sha,
    )
    return spec.cache_key


def _d8_predecessor_trace(ev):
    return PredecessorTrace(
        module_id=ev["module_id"], run_id=ev["run_id"], trace_path=ev["trace_path"],
        trace_sha256=ev["trace_sha256"], receipt_path=ev["receipt_path"],
        receipt_sha256=hashlib.sha256(ev["receipt_path"].read_bytes()).hexdigest(),
        ledger_path=ev["ledger_path"], selection_code_commit=_D8_CODE_COMMIT,
    )


def test_reconstruct_deferred_specs_a_e3_from_a_e1_predecessor(tmp_path):
    """D8: A-E3 deferred specs rebuild the scheduler's deferred-dataset-v1 cache keys from a
    verified A-E1 predecessor; the reconstructed keys match the plan row byte-for-byte."""
    spec, evaluations = _d8_three_arch_fixture({"m01": 0.10, "m02": 0.20, "m03": 0.30})
    ev = _publish_d8_evidence(tmp_path, spec, evaluations)
    pred_sha = ev["trace_sha256"]
    route, distribution, n_mode, fixed_n, training_size = "selected:F2_or_V", "core_continuous", "fixed_n", 10, 100000
    plan_row = {
        "module_id": "A-E3", "route": route, "distribution": distribution, "n_mode": n_mode,
        "fixed_n": fixed_n, "training_size": training_size,
        "predecessor_trace_sha256": pred_sha,
        "training_cache_key": _deferred_cache_key("training", route=route, distribution=distribution,
                                                  n_mode=n_mode, fixed_n=fixed_n, training_size=training_size, pred_sha=pred_sha),
        "validation_cache_key": _deferred_cache_key("validation", route=route, distribution=distribution,
                                                    n_mode=n_mode, fixed_n=fixed_n, training_size=training_size, pred_sha=pred_sha),
    }
    training, validation = fe.reconstruct_deferred_specs(plan_row, FROZEN, EFFECTIVE, _d8_predecessor_trace(ev))
    assert training.role == "training" and validation.role == "validation"
    assert training.route == route and training.predecessor_trace_sha256 == pred_sha
    assert training.cache_key == plan_row["training_cache_key"]
    assert validation.cache_key == plan_row["validation_cache_key"]


def test_reconstruct_deferred_specs_fail_closed(tmp_path):
    """D8: A-E1 (no predecessor), wrong-order predecessor, stale/cross-run trace, missing receipt
    and a drifted cache key all raise."""
    spec, evaluations = _d8_three_arch_fixture({"m01": 0.10, "m02": 0.20, "m03": 0.30})
    ev = _publish_d8_evidence(tmp_path, spec, evaluations)
    pred_sha = ev["trace_sha256"]
    pred_trace = _d8_predecessor_trace(ev)  # capture the bound predecessor before any mutation
    good_row = {
        "module_id": "A-E3", "route": "selected:F2_or_V", "distribution": "core_continuous",
        "n_mode": "fixed_n", "fixed_n": 10, "training_size": 100000,
        "predecessor_trace_sha256": pred_sha,
        "training_cache_key": _deferred_cache_key("training", route="selected:F2_or_V", distribution="core_continuous",
                                                  n_mode="fixed_n", fixed_n=10, training_size=100000, pred_sha=pred_sha),
        "validation_cache_key": _deferred_cache_key("validation", route="selected:F2_or_V", distribution="core_continuous",
                                                    n_mode="fixed_n", fixed_n=10, training_size=100000, pred_sha=pred_sha),
    }
    # A-E1 has no predecessor -> deferred specs do not exist for it
    ae1_row = dict(good_row, module_id="A-E1")
    with pytest.raises(ValueError, match="no predecessor"):
        fe.reconstruct_deferred_specs(ae1_row, FROZEN, EFFECTIVE, None)
    # wrong order: A-E2's predecessor must be A-E3, not A-E1
    ae2_row = dict(good_row, module_id="A-E2")
    with pytest.raises(ValueError, match="Wrong predecessor module"):
        fe.reconstruct_deferred_specs(ae2_row, FROZEN, EFFECTIVE, pred_trace)
    # stale / cross-run: plan row binds a different predecessor trace SHA than the verified one
    stale_row = dict(good_row, predecessor_trace_sha256="e" * 64,
                     training_cache_key="0" * 64, validation_cache_key="0" * 64)
    with pytest.raises(ValueError, match="stale or cross-run"):
        fe.reconstruct_deferred_specs(stale_row, FROZEN, EFFECTIVE, pred_trace)
    # cache-key drift: the reconstructed key disagrees with the plan row's bound key
    ev2 = _publish_d8_evidence(tmp_path / "second", spec, evaluations)
    drifted_row = dict(good_row, training_cache_key="0" * 64)
    with pytest.raises(ValueError, match="drifts"):
        fe.reconstruct_deferred_specs(drifted_row, FROZEN, EFFECTIVE, _d8_predecessor_trace(ev2))
    # missing receipt: predecessor trace whose receipt file is gone (pred_trace captured above)
    ev["receipt_path"].unlink()
    with pytest.raises(ValueError, match="[Rr]eceipt"):
        fe.reconstruct_deferred_specs(good_row, FROZEN, EFFECTIVE, pred_trace)


def test_build_module_pre_unseal_bundle_rebuilds_provenance_internally(tmp_path, monkeypatch):
    """D8 + R5: the production pre-unseal entry rebuilds point provenance internally and forwards
    it to build_pre_unseal_bundle; an externally-supplied point_provenance_by_fit is rejected."""
    from study02a.selection import serialize_point_evidence
    spec, evaluations = _d8_three_arch_fixture({"m01": 0.10, "m02": 0.20, "m03": 0.30})
    ev = _publish_d8_evidence(tmp_path, spec, evaluations)
    # Build a minimal but valid bundle input set around this one module's selection evidence.
    import json as _json
    from study02a.formal_contracts import (
        APPROVED_EFFECTIVE_CONFIG_SHA256, build_ceiling_hit_report, build_fit_status_record,
        write_ceiling_hit_report, write_fit_status, write_leakage_audit,
    )
    fit_ids = list(evaluations.keys())
    winner_id = next(r["candidate_id"] for r in ev["records"] if r["selected"])
    manifest_payload = {
        "manifest_version": "study02-formal-v1", "module_id": "A-E1", "run_id": _D8_RUN_ID,
        "code_commit": _D8_CODE_COMMIT,
        "base_protocol": {"id": "A-G2-v1", "sha256": "f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11"},
        "base_search": {"id": "A-G2-search-v1", "sha256": "abd6d17b1d2467e1253e0154adba0b6582a3feeb83ed889534ed4f6ab5e0ca13"},
        "amendment": {"id": "A-G3-pilot-amendment-v4", "sha256": "164e72658669dbb57f6dab8b1fc80099bd319f1fa327d5dda60cb61cb929ee38"},
        "effective_config": {"sha256": APPROVED_EFFECTIVE_CONFIG_SHA256, "max_epochs": 100, "min_epochs": 50, "patience": 40},
        "matrix": {"path": "experiment_matrix.csv",
                   "sha256": "fad701af2e2084bf7ce8f678d642410af58057b4ae33029c9150e50971fdf6b1",
                   "row_count": 820, "rule_ids": ["A-E1_optimized_supplement"], "fit_ids": fit_ids},
        "role_namespaces": {"training": "study02/formal/training", "validation": "study02/formal/validation"},
        "seeds": {"screening": [420001, 420002, 420003], "formal": list(range(420101, 420111))},
        "test_state": "sealed",
        "predecessor": {"module_id": "none", "run_id": "none", "selection_trace_path": "none",
                        "selection_trace_sha256": "none", "selection_receipt_path": "none",
                        "selection_receipt_sha256": "none", "selection_ledger_path": "none"},
    }
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(_json.dumps(manifest_payload, sort_keys=True) + "\n", encoding="utf-8")
    point_evidence_paths: dict[str, Path] = {}
    fit_status_rows = []
    from study02a.training import FitResult
    curve = tuple(1.0 / (i + 1) for i in range(100))
    for fit_id, evaluation in evaluations.items():
        art_path = tmp_path / f"point_evidence_{fit_id}.json"
        art_path.write_text(_json.dumps(serialize_point_evidence(evaluation), sort_keys=True, separators=(",", ":")) + "\n",
                            encoding="utf-8")
        point_evidence_paths[fit_id] = art_path
        selected = evaluation.candidate_id == winner_id
        result = FitResult(
            predictions=None, checkpoint_sha256=evaluation.checkpoint_sha256,
            best_validation_loss=min(curve), best_epoch=curve.index(min(curve)),
            actual_epochs=len(curve), validation_loss_history=curve,
            early_stop_reason="max_epochs", hit_epoch_ceiling=True,
        )
        fit_status_rows.append(build_fit_status_record(
            fit_id=fit_id, module_id="A-E1", rule_id="A-E1_optimized_supplement",
            route_id="F2", n=10, seed=int(evaluation.support_key.seed), decision_id=spec.decision_id,
            candidate_id=evaluation.candidate_id, selected=selected, result=result,
            selection_score=float(evaluation.selection_score),
        ))
    fit_status_path = tmp_path / "fit_status.csv"
    write_fit_status(fit_status_path, fit_status_rows)
    ceiling_path = tmp_path / "ceiling_hit_report.json"
    write_ceiling_hit_report(ceiling_path, build_ceiling_hit_report(fit_status_rows))
    leakage_path = tmp_path / "leakage_audit.json"
    write_leakage_audit(
        leakage_path,
        parameter_point_ids={"training": ["tr-1"], "validation": ["va-1"],
                             "calibration": ["ca-1"], "test": ["te-1"]},
        role_namespaces={"training": "study02/formal/training", "validation": "study02/formal/validation",
                         "calibration": "study02/formal/calibration", "test": "study02/formal/test"},
        scaler_source="training_only", feature_selection_source="validation_only",
        model_selection_source="validation_only", test_access_count=0,
    )
    diagnostics_path = tmp_path / "selection_diagnostics.jsonl"
    _records, diagnostics = build_selection_trace(
        module_id="A-E1", run_id=_D8_RUN_ID, specs=(spec,), evaluations_by_fit=evaluations,
    )
    diagnostics_path.write_bytes(b"".join(
        (_json.dumps(d, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8") for d in diagnostics))

    # The production entry rebuilds provenance internally. Monkeypatch the rebuild to return the
    # same synthetic evaluations the publisher used (stands in for a completed run's checkpoint
    # rebuild -- no training is launched, no test data opened).
    captured: dict[str, object] = {}

    def fake_rebuild(*, study_root, run_dir, cache_root, module_id, run_id):
        captured["called"] = True
        captured["module_id"] = module_id
        captured["run_id"] = run_id
        return dict(evaluations)

    monkeypatch.setattr(fe, "rebuild_selection_point_provenance", fake_rebuild)
    run_dir = tmp_path / "A-E1" / _D8_RUN_ID
    run_dir.mkdir(parents=True)
    bundle = fe.build_module_pre_unseal_bundle(
        study_root=STUDY_ROOT, cache_root=tmp_path / "cache",
        run_dirs={"A-E1": run_dir},
        formal_manifests=[manifest_path], selection_traces=[ev["trace_path"]],
        selection_receipts=[ev["receipt_path"]], selection_ledger_path=ev["ledger_path"],
        fit_status_path=fit_status_path, ceiling_report_path=ceiling_path,
        leakage_audit_path=leakage_path, code_commit=_D8_CODE_COMMIT,
        effective_config_sha256=APPROVED_EFFECTIVE_CONFIG_SHA256,
        module_run_ids={"A-E1": _D8_RUN_ID}, point_evidence_paths=point_evidence_paths,
        selection_diagnostics_paths=[diagnostics_path],
    )
    assert captured.get("called") is True and captured.get("module_id") == "A-E1"
    assert bundle["bundle_version"] == "study02-pre-unseal-v3"
    assert bundle["test_state"] == "sealed"
    # The caller cannot substitute an external point_provenance_by_fit (the kwarg is absent).
    with pytest.raises(TypeError):
        fe.build_module_pre_unseal_bundle(
            study_root=STUDY_ROOT, cache_root=tmp_path / "cache", run_dirs={"A-E1": run_dir},
            formal_manifests=[manifest_path], selection_traces=[ev["trace_path"]],
            selection_receipts=[ev["receipt_path"]], selection_ledger_path=ev["ledger_path"],
            fit_status_path=fit_status_path, ceiling_report_path=ceiling_path,
            leakage_audit_path=leakage_path, code_commit=_D8_CODE_COMMIT,
            effective_config_sha256=APPROVED_EFFECTIVE_CONFIG_SHA256,
            module_run_ids={"A-E1": _D8_RUN_ID}, point_evidence_paths=point_evidence_paths,
            selection_diagnostics_paths=[diagnostics_path],
            point_provenance_by_fit=dict(evaluations),
        )


@pytest.mark.slow
def test_smoke_a_e1_one_fit_end_to_end(tmp_path, monkeypatch):
    """End-to-end: materialize A-E1, claim+train+record ONE real fit; assert scheduler integrity.

    Requires a clean ``code/`` tree (the scheduler authority check fails on dirty scientific
    code), so run after committing. Training epochs are reduced via a fast wrapper so this
    exercises the full plumbing (dataset build/cache, training-only scaler, canonical
    checkpoint + 5-field fit_status binding, metrics sidecar, record_fit_succeeded, authority
    rebuild) in seconds rather than the full 100-epoch formal contract.
    """
    # fail fast with a clear message if code/ is dirty (materialize_run would reject it)
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--",
         str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"

    def fast_fixed(model_factory, train_batch, val_batch, effective, *, seed, loss_id, lr, weight_decay, batch_size, optimizer_id="adamw"):
        # Real checkpoint + predictions from a 2-epoch warmup, but a synthetic 60-epoch
        # trajectory so the evidence satisfies the formal [min,max]-epochs contract without
        # paying for 50-100 real epochs. Real training->checkpoint->evidence is covered by
        # test_checkpoint_round_trip_reproduces_predictions.
        from study02a.training import FitResult
        warmup = fit_candidate(
            model_factory, (train_batch.features, train_batch.targets), (val_batch.features, val_batch.targets),
            seed=seed, max_epochs=2, min_epochs=1, patience=1,
            batch_size=min(int(batch_size), 64), loss_id=loss_id, lr=lr, weight_decay=weight_decay, optimizer_id=optimizer_id,
        )
        curve = tuple(100.0 / (i + 1) for i in range(60))
        best_epoch = min(range(60), key=lambda i: curve[i])
        return FitResult(
            predictions=warmup.predictions, checkpoint_sha256=warmup.checkpoint_sha256,
            checkpoint_bytes=warmup.checkpoint_bytes, best_validation_loss=warmup.best_validation_loss,
            actual_epochs=60, best_epoch=best_epoch, validation_loss_history=curve,
            early_stop_reason="patience_exhausted", hit_epoch_ceiling=False,
        )
    monkeypatch.setattr(fe, "fit_fixed_candidate", fast_fixed)

    artifact_root = tmp_path / "artifact"
    cache_root = tmp_path / "cache"
    summary = fe.run_module(
        study_root=STUDY_ROOT, module_id="A-E1", run_id="smoke-0001",
        artifact_root=artifact_root, cache_root=cache_root, owner_id="smoke-test", max_fits=1,
    )
    assert summary["succeeded_count"] == 1
    assert summary["failed_count"] == 0
    fit_id = summary["succeeded"][0]

    from study02a.formal_scheduler import status_run, _rebuild_authority
    run_dir = artifact_root / "A-E1" / "smoke-0001"
    stat = status_run(run_dir, cache_root=cache_root)
    assert stat["test_access_count"] == 0
    assert stat["counts"]["succeeded"] == 1
    manifest, plan, state, events = _rebuild_authority(run_dir, cache_root)
    assert state["fit_states"][fit_id] == "succeeded"
    # checkpoint.pt is loadable and reproduces the model; fit_status binds the checkpoint; evidence binds trajectory
    import hashlib, json
    from study02a.training import load_checkpoint
    checkpoint = (run_dir / "outputs" / fit_id / "checkpoint.pt").read_bytes()
    binding = json.loads((run_dir / "outputs" / fit_id / "fit_status.json").read_bytes())
    assert binding == {"checkpoint_sha256": hashlib.sha256(checkpoint).hexdigest(),
                       "fit_id": fit_id, "run_id": "smoke-0001", "status": "succeeded", "test_access_count": 0}
    evidence = json.loads((run_dir / "outputs" / fit_id / "evidence.json").read_bytes())
    assert evidence["checkpoint_sha256"] == binding["checkpoint_sha256"]
    assert evidence["actual_epochs"] >= 1 and len(evidence["validation_curve"]) == evidence["actual_epochs"]
    state_dict = load_checkpoint(checkpoint)
    assert set(state_dict) and all(isinstance(t, torch.Tensor) for t in state_dict.values())
    # no untrusted metrics sidecar exists (selection signal must derive from the bound checkpoint)
    assert not (run_dir / "metrics").exists()


@pytest.mark.slow
def test_run_module_defers_selection_dependent_fits(tmp_path, monkeypatch):
    """#1: selection-dependent fits are deferred cleanly, not claimed-and-failed.

    Forces every fit to look placeholder-dependent; run_module must stop at the first
    pending fit with ``selection_required`` and record zero successes/failures (no churn).
    Requires a clean ``code/`` tree for materialize.
    """
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--", str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True,
    )
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"
    monkeypatch.setattr(fe, "_is_selection_dependent", lambda row: True)
    summary = fe.run_module(
        study_root=STUDY_ROOT, module_id="A-E1", run_id="defer-0001",
        artifact_root=tmp_path / "artifact", cache_root=tmp_path / "cache",
        owner_id="defer-test", max_fits=5,
    )
    assert summary["succeeded_count"] == 0
    assert summary["failed_count"] == 0
    assert summary["selection_required_count"] == 1
    assert summary["selection_required"] == ["G3-fit-0000"]


# ---------------------------------------------------------------------------
# D8 staged A-E1 selection resolver (resolve_a_e1_staged_selection).
# Real frozen A-E1 matrix (stage1+stage2, F2+V), deterministic synthetic scoring
# injected via score_fit (no training launched, no test opened). Exercises the full
# stage1 -> top4 -> stage2 -> winner-retrain -> F2/V baseline -> final aliases chain,
# the immutable hash-bound append-only staged ledger, idempotent crash recovery, and
# every fail-closed path. No formal run is launched; no test data is opened.
# ---------------------------------------------------------------------------

_STAGED_RUN_ID = "G3-AE1-staged-v1"


def _staged_score(decision_id: str, candidate_id: str) -> float:
    """Deterministic per-candidate base score over the real staged decisions.

    stage1 (architecture): m01 best .. m12 worst (so top4 = [m01, m02, m03, m04] on both
    routes). stage2: F2 winner = selected_top_2:o2, V winner = selected_top_3:o3 (distinct
    per route so final aliases provably track the winning route)."""
    if decision_id.startswith("architecture:"):
        return 0.01 * int(candidate_id[1:])  # m01 -> 0.01 ... m12 -> 0.12
    route = decision_id.split(":")[2]  # stage2:A-E1:{F2|V}:n10
    forced = {"F2": "selected_top_2:o2", "V": "selected_top_3:o3"}[route]
    if candidate_id == forced:
        return 0.001
    slot_n = int(candidate_id.split(":")[0].rsplit("_", 1)[-1])
    opt = candidate_id.split(":")[1]
    return 0.5 + slot_n * 0.1 + ("o1o2o3".index(opt) // 2) * 0.01


def _staged_specs_and_evaluations():
    """Build the 4 real staged A-E1 decision specs (stage1+stage2 x F2+V) with synthetic
    checkpoint-bound evaluations, scored by :func:`_staged_score`."""
    scope = [r for r in MATRIX_ROWS if str(r["module"]) == "A-E1"
             and str(r["fit_kind"]) in ("search_stage1", "search_stage2")
             and str(r["route"]) in ("F2", "V")]
    specs = build_decision_specs("A-E1", scope)
    assert len(specs) == 4
    evaluations: dict[str, FitEvaluation] = {}
    for spec in specs:
        for cand in spec.candidates:
            base = float(_staged_score(spec.decision_id, cand.candidate_id))
            for key in cand.support_keys:
                fit_id = cand.support_for(key)
                records = _synth_point_records(fit_id, int(key.seed), base)
                aggregate = sum(rec["l_param"] for rec in records) / len(records)
                evaluations[fit_id] = FitEvaluation(
                    fit_id=fit_id, module_id="A-E1", decision_id=spec.decision_id,
                    candidate_id=cand.candidate_id, support_key=key, failed=False,
                    checkpoint_sha256=hashlib.sha256(fit_id.encode("utf-8")).hexdigest(),
                    validation_identity=f"val-cache-{fit_id}", selection_score=aggregate,
                    failure_penalty=0.0, point_records=records,
                )
    return specs, evaluations


def _publish_staged_run(tmp_path: Path, specs, evaluations, *,
                        run_id=_STAGED_RUN_ID, code_commit=_D8_CODE_COMMIT,
                        winner_retrain_only_plan=True):
    """Publish a real staged A-E1 selection trace + receipt + ledger + manifest + plan into
    ``tmp_path/A-E1/<run_id>`` and return ``(run_dir, trace_sha, records)``."""
    run_dir = tmp_path / "A-E1" / run_id
    run_dir.mkdir(parents=True)
    records, _diag = build_selection_trace(
        module_id="A-E1", run_id=run_id, specs=tuple(specs), evaluations_by_fit=evaluations,
    )
    trace_path = run_dir / "selection_trace.jsonl"
    trace_sha = write_selection_trace(trace_path, records)
    publish_selection_receipt(
        receipt_path=run_dir / "selection_receipt.json",
        ledger_path=run_dir / "selection_ledger.jsonl",
        module_id="A-E1", run_id=run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=EFFECTIVE, code_commit=code_commit,
    )
    run_dir.joinpath("manifest.json").write_text(
        json.dumps({"code_commit": code_commit}, sort_keys=True) + "\n", encoding="utf-8")
    plan_rows = [r for r in MATRIX_ROWS if str(r["module"]) == "A-E1"]
    if winner_retrain_only_plan:
        plan_rows = [r for r in plan_rows if str(r["fit_kind"]) == "winner_retrain"]
    (run_dir / "plan.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in plan_rows), encoding="utf-8")
    return run_dir, trace_sha, records


def _baseline_point_records(n: int, seed: int, base: float):
    """Route-independent winner-retrain point records so F2 and V pair on (seed_id, sample_id).

    Both routes' winner-retrain fits are evaluated on the same frozen validation parameter
    points, so sample_id/point_id are derived from the support point (n) + parameter point
    -- never from the fit_id (which differs per route and would break the paired grid)."""
    records = []
    for p in range(2):
        for s in range(2):
            value = base + ((seed % 7) + p + s) * 0.001
            records.append({
                "sample_id": f"n{n}:pt{p}:rep{s}", "seed_id": str(seed),
                "point_id": f"n{n}:pt{p}", "legal": True, "failure": 0,
                "l_param": value, "e_beta": value, "e_eta": value, "e_gamma": value,
            })
    return records


def _baseline_score_fit(*, f2: float = 0.10, v: float = 0.20, matrix_by_fit=None):
    """score_fit for the F2/V winner-retrain baseline; F2 < V on every paired point so F2 is
    globally better under the frozen relative-RMSE rule.

    ``n`` is NOT in plan.jsonl (the plan carries ``n_mode``/``fixed_n``), so it is read from the
    authoritative matrix row looked up by ``fit_id`` when ``matrix_by_fit`` is supplied; otherwise
    the legacy in-plan ``n`` is used (callers that publish a matrix-shaped plan)."""
    _lookup = matrix_by_fit if matrix_by_fit is not None else fe._authoritative_matrix_by_fit(STUDY_ROOT)

    def score_fit(fit_id, plan_row):
        route = str(plan_row["route"])
        n = int(_lookup[str(fit_id)]["n"]); seed = int(plan_row["seed"])
        base = f2 if route == "F2" else v
        records = _baseline_point_records(n, seed, base)
        aggregate = sum(rec["l_param"] for rec in records) / len(records)
        return FitEvaluation(
            fit_id=fit_id, module_id="A-E1", decision_id="baseline_input:A-E1:F2_vs_V",
            candidate_id=route, support_key=SupportKey(n=n, seed=seed), failed=False,
            checkpoint_sha256=hashlib.sha256(fit_id.encode("utf-8")).hexdigest(),
            validation_identity=f"val-cache-{fit_id}", selection_score=aggregate,
            failure_penalty=0.0, point_records=records,
        )
    return score_fit


def _assert_chained_ledger(run_dir: Path) -> list[dict]:
    ledger_path = run_dir / fe._STAGED_LEDGER_NAME
    assert ledger_path.is_file()
    records = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert records, "staged ledger is empty"
    previous = fe._ZERO_HASH
    for record in records:
        assert record["previous_record_sha256"] == previous  # hash-bound chain from ZERO_HASH
        # each record's self-hash is recomputed from its core and matches what was written
        core = {k: record[k] for k in (
            "record_version", "module_id", "run_id", "code_commit", "effective_config_sha256",
            "selection_trace_sha256", "stage", "route", "previous_record_sha256", "input",
            "resolution", "resolution_sha256")}
        assert hashlib.sha256(fe._canonical(core)).hexdigest() == record["record_sha256"]
        previous = record["record_sha256"]
    return records


def _rewrite_staged_ledger(run_dir: Path, records: list[dict]) -> None:
    """Rewrite a syntactically and cryptographically valid staged chain for semantic attacks."""
    previous = fe._ZERO_HASH
    rebuilt = []
    for source in records:
        record = dict(source)
        record["previous_record_sha256"] = previous
        record["resolution_sha256"] = hashlib.sha256(
            fe._canonical(dict(record["resolution"]))
        ).hexdigest()
        core = {key: value for key, value in record.items() if key != "record_sha256"}
        record["record_sha256"] = hashlib.sha256(fe._canonical(core)).hexdigest()
        previous = record["record_sha256"]
        rebuilt.append(record)
    (run_dir / fe._STAGED_LEDGER_NAME).write_bytes(
        b"".join(fe._canonical(record) for record in rebuilt)
    )


def test_resolve_a_e1_staged_selection_smoke_real_matrix(tmp_path):
    """Full real-matrix staged smoke: every frozen A-E1 placeholder resolves through the
    immutable chained ledger; final aliases provably take the winning route's stage2."""
    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, trace_sha, _records = _publish_staged_run(tmp_path, specs, evaluations)
    result = fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit(),
    )
    assert result["module_id"] == "A-E1"
    assert result["selection_trace_sha256"] == trace_sha
    assert result["pending"] == []  # every stage resolved
    for route in ("F2", "V"):
        top4 = result["top4_by_route"][route]
        assert list(top4) == ["selected_top_1", "selected_top_2", "selected_top_3", "selected_top_4"]
        # stage1 ranking m01 < m02 < m03 < m04 (lowest_aggregate), independent of route
        assert (top4["selected_top_1"], top4["selected_top_2"],
                top4["selected_top_3"], top4["selected_top_4"]) == ("m01", "m02", "m03", "m04")
        s2 = result["stage2_by_route"][route]
        assert s2["selected:A-E1_loss"] == "transformed_train_z_huber"  # frozen stage2 loss
    # stage2 winners are distinct per route (forced by _staged_score)
    assert result["stage2_by_route"]["F2"] == {
        "selected:A-E1_loss": "transformed_train_z_huber",
        "selected:A-E1_architecture": "m02",  # selected_top_2 -> rank-2 architecture
        "selected:A-E1_optimizer": "o2"}
    assert result["stage2_by_route"]["V"] == {
        "selected:A-E1_loss": "transformed_train_z_huber",
        "selected:A-E1_architecture": "m03",  # selected_top_3 -> rank-3 architecture
        "selected:A-E1_optimizer": "o3"}
    # F2 carries the lower (better) winner-retrain aggregate -> global_better_rule selects F2
    assert result["selected_F2_or_V"] == "F2"
    # final aliases take the WINNING route's stage2 (F2), not V's
    assert result["final_aliases"] == result["stage2_by_route"]["F2"]
    _assert_chained_ledger(run_dir)


def test_g3_reader_accepts_direct_a_e1_staged_happy_path(tmp_path):
    """The unified G3 reader accepts the real 8-record staged order and concrete aliases."""
    from study02a.formal_g3_control import _resolve_a_e1_from_staged_ledger

    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, _trace_sha, _records = _publish_staged_run(tmp_path, specs, evaluations)
    staged = fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit(),
    )
    out = {}
    _resolve_a_e1_from_staged_ledger(
        run_dir, _STAGED_RUN_ID, _D8_CODE_COMMIT,
        EFFECTIVE.effective_config_sha256, out, study_root=STUDY_ROOT,
        cache_root=tmp_path / "cache", frozen_config=FROZEN,
        baseline_score_fit=_baseline_score_fit(),
    )
    assert out["selected:F2_or_V"] == staged["selected_F2_or_V"]
    assert {key: out[key] for key in staged["final_aliases"]} == staged["final_aliases"]


def test_g3_reader_rejects_cryptographically_valid_staged_reorder(tmp_path):
    """Re-chaining cannot legitimize a route/stage order that differs from the exact contract."""
    from study02a.formal_g3_control import _resolve_a_e1_from_staged_ledger

    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, _trace_sha, _records = _publish_staged_run(tmp_path, specs, evaluations)
    fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit(),
    )
    records = _assert_chained_ledger(run_dir)
    records[2], records[3] = records[3], records[2]
    _rewrite_staged_ledger(run_dir, records)
    with pytest.raises(ValueError, match="semantic order mismatch"):
        _resolve_a_e1_from_staged_ledger(
            run_dir, _STAGED_RUN_ID, _D8_CODE_COMMIT,
            EFFECTIVE.effective_config_sha256, {}, study_root=STUDY_ROOT,
            cache_root=tmp_path / "cache", frozen_config=FROZEN,
            baseline_score_fit=_baseline_score_fit(),
        )


def test_g3_reader_rejects_stage2_predecessor_cross_binding_tamper(tmp_path):
    """A valid self-hash cannot hide a stage2 record bound to the wrong stage1 record."""
    from study02a.formal_g3_control import _resolve_a_e1_from_staged_ledger

    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, _trace_sha, _records = _publish_staged_run(tmp_path, specs, evaluations)
    fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit(),
    )
    records = _assert_chained_ledger(run_dir)
    records[1]["input"] = {**records[1]["input"], "stage1_record_sha256": "f" * 64}
    _rewrite_staged_ledger(run_dir, records)
    with pytest.raises(ValueError, match="input/predecessor cross-binding mismatch"):
        _resolve_a_e1_from_staged_ledger(
            run_dir, _STAGED_RUN_ID, _D8_CODE_COMMIT,
            EFFECTIVE.effective_config_sha256, {}, study_root=STUDY_ROOT,
            cache_root=tmp_path / "cache", frozen_config=FROZEN,
            baseline_score_fit=_baseline_score_fit(),
        )


def test_g3_reader_rejects_final_alias_cross_binding_tamper(tmp_path):
    """Final aliases must equal the stage2 resolution of the baseline-selected route."""
    from study02a.formal_g3_control import _resolve_a_e1_from_staged_ledger

    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, _trace_sha, _records = _publish_staged_run(tmp_path, specs, evaluations)
    fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit(),
    )
    records = _assert_chained_ledger(run_dir)
    records[-1]["resolution"] = {
        **records[-1]["resolution"], "selected:A-E1_architecture": "m99",
    }
    _rewrite_staged_ledger(run_dir, records)
    with pytest.raises(ValueError, match="final_aliases do not match"):
        _resolve_a_e1_from_staged_ledger(
            run_dir, _STAGED_RUN_ID, _D8_CODE_COMMIT,
            EFFECTIVE.effective_config_sha256, {}, study_root=STUDY_ROOT,
            cache_root=tmp_path / "cache", frozen_config=FROZEN,
            baseline_score_fit=_baseline_score_fit(),
        )


def test_g3_reader_rejects_coherent_baseline_and_final_tamper(tmp_path):
    """Re-chaining a false V baseline plus matching V final aliases cannot replace replay truth."""
    from study02a.formal_g3_control import _resolve_a_e1_from_staged_ledger

    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, _trace_sha, _records = _publish_staged_run(tmp_path, specs, evaluations)
    fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit(),
    )
    records = _assert_chained_ledger(run_dir)
    v_resolution = dict(records[4]["resolution"])
    records[6]["resolution"] = {"selected:F2_or_V": "V"}
    records[7]["resolution"] = v_resolution
    records[7]["input"] = {
        **records[7]["input"],
        "winning_route": "V",
        "winning_route_stage2": {
            "loss": v_resolution["selected:A-E1_loss"],
            "architecture": v_resolution["selected:A-E1_architecture"],
            "optimizer": v_resolution["selected:A-E1_optimizer"],
        },
    }
    _rewrite_staged_ledger(run_dir, records)
    with pytest.raises(ValueError, match="baseline winner disagrees"):
        _resolve_a_e1_from_staged_ledger(
            run_dir, _STAGED_RUN_ID, _D8_CODE_COMMIT,
            EFFECTIVE.effective_config_sha256, {}, study_root=STUDY_ROOT,
            cache_root=tmp_path / "cache", frozen_config=FROZEN,
            baseline_score_fit=_baseline_score_fit(),
        )


def test_resolve_a_e1_staged_selection_pending_without_trace(tmp_path):
    """No selection trace yet -> every stage is pending (a staged run that has not started)."""
    run_dir = tmp_path / "A-E1" / _STAGED_RUN_ID
    run_dir.mkdir(parents=True)
    result = fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache", run_id=_STAGED_RUN_ID)
    assert result["selection_trace_sha256"] is None
    assert result["top4_by_route"] == {} and result["stage2_by_route"] == {}
    assert result["selected_F2_or_V"] is None and result["final_aliases"] is None
    assert result["pending"] == ["stage1", "stage2", "winner_retrain", "baseline_input", "final_aliases"]


def test_resolve_a_e1_staged_selection_idempotent_recovery(tmp_path):
    """A recovery rerun recomputes each stage, reuses records whose resolution matches, and
    leaves the ledger chained and line-count stable (no double-consume, no overwrite)."""
    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, _sha, _rec = _publish_staged_run(tmp_path, specs, evaluations)
    first = fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit())
    ledger_path = run_dir / fe._STAGED_LEDGER_NAME
    lines_after_first = ledger_path.read_text(encoding="utf-8").splitlines()
    # second call: identical inputs -> idempotent reuse, same record_sha256 chain, no new lines
    second = fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit())
    assert second["record_sha256"] == first["record_sha256"]
    assert second["final_aliases"] == first["final_aliases"]
    assert ledger_path.read_text(encoding="utf-8").splitlines() == lines_after_first


def test_resolve_a_e1_staged_selection_rejects_conflicting_duplicate(tmp_path):
    """A second, DIFFERENT resolution for an already-published stage/route (a duplicate stage
    receipt / stale mapping) is rejected -- never silently overwritten."""
    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, _sha, _rec = _publish_staged_run(tmp_path, specs, evaluations)
    fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit())
    ledger_path = run_dir / fe._STAGED_LEDGER_NAME
    # corrupt the first published record's resolution_sha in place (a stale mapping left by a
    # conflicting re-resolution); the recomputed record disagrees -> fail closed, no overwrite.
    lines = ledger_path.read_text(encoding="utf-8").splitlines()
    first = json.loads(lines[0])
    first["resolution_sha256"] = "f" * 64
    lines[0] = json.dumps(first, sort_keys=True)
    ledger_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate stage receipt|stale mapping"):
        fe.resolve_a_e1_staged_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
            run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit())


def test_resolve_a_e1_staged_selection_rejects_wrong_support_key(tmp_path):
    """A winner-retrain evaluation whose support_key disagrees with the frozen expected
    support (wrong n/seed) is rejected before the baseline is derived."""
    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, _sha, _rec = _publish_staged_run(tmp_path, specs, evaluations)

    def wrong_score_fit(fit_id, plan_row):
        return FitEvaluation(
            fit_id=fit_id, module_id="A-E1", decision_id="baseline_input:A-E1:F2_vs_V",
            candidate_id=str(plan_row["route"]),
            support_key=SupportKey(n=999, seed=999),  # disagrees with the frozen support
            failed=False, checkpoint_sha256=hashlib.sha256(fit_id.encode("utf-8")).hexdigest(),
            validation_identity=f"val-cache-{fit_id}", selection_score=0.10, failure_penalty=0.0,
            point_records=_synth_point_records(fit_id, 999, 0.10))
    with pytest.raises(ValueError, match="support|disagrees"):
        fe.resolve_a_e1_staged_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
            run_id=_STAGED_RUN_ID, score_fit=wrong_score_fit)


def test_resolve_a_e1_staged_selection_rejects_tampered_trace(tmp_path):
    """A hand-edited selection trace whose bytes no longer match the receipt-bound SHA is
    rejected before any staged placeholder resolves."""
    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, _sha, _rec = _publish_staged_run(tmp_path, specs, evaluations)
    with (run_dir / "selection_trace.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"tampered": true}\n')  # changes the trace bytes -> SHA mismatch
    with pytest.raises(ValueError, match="SHA-256"):
        fe.resolve_a_e1_staged_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
            run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit())


def test_resolve_a_e1_staged_selection_rejects_missing_stage_decision(tmp_path):
    """A trace that carries stage1 but not stage2 (an incomplete staged run) cannot resolve:
    invoking the resolver on it fails closed rather than guessing stage2."""
    scope = [r for r in MATRIX_ROWS if str(r["module"]) == "A-E1"
             and str(r["fit_kind"]) == "search_stage1" and str(r["route"]) in ("F2", "V")]
    specs = build_decision_specs("A-E1", scope)  # stage1 only, no stage2
    evaluations: dict[str, FitEvaluation] = {}
    for spec in specs:
        for cand in spec.candidates:
            base = float(_staged_score(spec.decision_id, cand.candidate_id))
            for key in cand.support_keys:
                fit_id = cand.support_for(key)
                evaluations[fit_id] = FitEvaluation(
                    fit_id=fit_id, module_id="A-E1", decision_id=spec.decision_id,
                    candidate_id=cand.candidate_id, support_key=key, failed=False,
                    checkpoint_sha256=hashlib.sha256(fit_id.encode("utf-8")).hexdigest(),
                    validation_identity=f"val-cache-{fit_id}",
                    selection_score=base, failure_penalty=0.0,
                    point_records=_synth_point_records(fit_id, int(key.seed), base))
    run_dir, _sha, _rec = _publish_staged_run(tmp_path, specs, evaluations)
    with pytest.raises(ValueError, match="stage2 decision"):
        fe.resolve_a_e1_staged_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
            run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit())


def test_formal_staged_cli_wires_resolver(tmp_path, monkeypatch):
    """The formal-staged CLI command is a real production call point: it derives run_dir from
    the run authority and forwards to resolve_a_e1_staged_selection (caller never supplies
    winner/top4/baseline)."""
    import run_study02a
    captured: dict[str, object] = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return {"module_id": kwargs["module_id"], "pending": ["stage1"]}

    monkeypatch.setattr(run_study02a, "resolve_a_e1_staged_selection", fake)
    payload = run_study02a.resolve_staged("A-E1", _STAGED_RUN_ID, tmp_path, tmp_path / "cache")
    assert payload == {"module_id": "A-E1", "pending": ["stage1"]}
    assert captured["module_id"] == "A-E1" and captured["run_id"] == _STAGED_RUN_ID
    assert Path(captured["run_dir"]) == tmp_path / "A-E1" / _STAGED_RUN_ID
    assert captured["study_root"] == run_study02a.STUDY_ROOT
    assert "score_fit" not in captured  # production never accepts a caller-supplied winner


def test_build_module_selection_publishes_trace_without_staged_side_effect(tmp_path, monkeypatch):
    """build_module_selection publishes the module selection trace/receipt (stage1+stage2 scored via
    score_fit); staged alias derivation now lives in the orchestrator (run_a_e1_staged), not here, so
    no 'staged' key is returned. (The staged resolver is covered by its own unit tests + the
    orchestrator's full-chain smoke.)"""
    _specs, evaluations = _staged_specs_and_evaluations()
    run_dir = tmp_path / "A-E1" / _STAGED_RUN_ID
    run_dir.mkdir(parents=True)
    plan_rows = [r for r in MATRIX_ROWS if str(r["module"]) == "A-E1"]
    (run_dir / "plan.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in plan_rows), encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"code_commit": _D8_CODE_COMMIT}, sort_keys=True) + "\n", encoding="utf-8")
    monkeypatch.setattr(fe, "_rebuild_authority",
                        lambda run_dir, cache_root: (None, None, {"fit_states": {}}, []))
    receipt = fe.build_module_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        module_id="A-E1", run_id=_STAGED_RUN_ID, score_fit=lambda fit_id, plan_row: evaluations[fit_id])
    assert receipt["selection_trace_sha256"] and (run_dir / "selection_trace.jsonl").is_file()
    assert "staged" not in receipt  # staged derivation moved to run_a_e1_staged


# ---------------------------------------------------------------------------
# Pre-unseal accreditation CLI wiring (Task 9 Step 6/8 + D8 deferred specs).
# authorize wraps initialize_formal_state + authorize_test_once (stops before consume);
# resolve-deferred wraps reconstruct_deferred_specs. No training; test stays sealed.
# ---------------------------------------------------------------------------

_ACCCR_RUN_ID = "G3-AE1-accredit-v1"
_ACCCR_COMMIT = "c" * 40


def _accredit_bundle_inputs(run_dir: Path, *, trace_sha: str = "d" * 64):
    """Minimal sealed pre-unseal bundle + ceiling + leakage + oracle-review on disk (mirrors the
    formal_state lifecycle fixture) so the authorize CLI can run end-to-end on a fake run."""
    run_dir.mkdir(parents=True, exist_ok=True)
    ceiling = run_dir / "ceiling_hit_report.json"
    leakage = run_dir / "leakage_audit.json"
    oracle = run_dir / "oracle_review.json"
    ceiling.write_bytes(b"ceiling-evidence\n")
    leakage.write_bytes(b"leakage-evidence\n")
    oracle.write_bytes(b"oracle-review-evidence\n")
    bundle = {
        "bundle_version": "study02-pre-unseal-v3",
        "code_commit": _ACCCR_COMMIT,
        "effective_config_sha256": EFFECTIVE.effective_config_sha256,
        "module_run_ids": {"A-E1": _ACCCR_RUN_ID},
        "selection_trace_hashes": {"A-E1": trace_sha},
        "artifact_hashes": {
            str(ceiling): hashlib.sha256(ceiling.read_bytes()).hexdigest(),
            str(leakage): hashlib.sha256(leakage.read_bytes()).hexdigest(),
        },
        "test_state": "sealed",
    }
    bundle_path = run_dir / "pre_unseal_bundle.json"
    bundle_path.write_bytes(
        (json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))
    return bundle_path, ceiling, leakage, oracle, trace_sha


def _publish_accredit_approval(approval_path: Path, bundle_path: Path, ceiling, leakage, oracle, trace_sha):
    from study02a.formal_state import publish_oracle_approval
    publish_oracle_approval(
        approval_path=approval_path, approval_version="study02-test-unseal-approval-v1",
        decision="APPROVE test unseal", code_commit=_ACCCR_COMMIT,
        effective_config_sha256=EFFECTIVE.effective_config_sha256,
        pre_unseal_bundle_sha256=hashlib.sha256(bundle_path.read_bytes()).hexdigest(),
        selection_trace_hashes={"A-E1": trace_sha},
        ceiling_report_sha256=hashlib.sha256(ceiling.read_bytes()).hexdigest(),
        leakage_audit_sha256=hashlib.sha256(leakage.read_bytes()).hexdigest(),
        oracle_review_artifact_sha256=hashlib.sha256(oracle.read_bytes()).hexdigest(),
        issued_at="2026-07-19T10:00:00+08:00",
    )


def test_formal_accredit_authorize_is_permanently_blocked(tmp_path):
    """The superseded per-module API cannot transition sealed state under any inputs."""
    import run_study02a
    with pytest.raises(SystemExit, match="permanently BLOCKED"):
        run_study02a.accredit_authorize(
            module="A-E1", run_id=_ACCCR_RUN_ID, artifact_root=tmp_path,
            approval_path=tmp_path / "approval.json", oracle_review_path=tmp_path / "review.json",
            run_family_id="G3-formal", timestamp="2026-07-19T11:30:00+08:00")
    assert not hasattr(run_study02a, "consume_g3_test")
    assert not any(tmp_path.rglob("formal_state.json"))


def test_formal_resolve_deferred_cli_a_e3_from_a_e1(tmp_path):
    """The resolve-deferred CLI reconstructs A-E3 concrete dataset specs from a verified A-E1
    predecessor trace (no training); cache keys match the scheduler's deferred-dataset-v1 plan."""
    import run_study02a
    specs, evaluations = _staged_specs_and_evaluations()
    pred_run_id = "G3-AE1-pred-v1"
    pred_dir = tmp_path / "A-E1" / pred_run_id
    pred_dir.mkdir(parents=True)
    records, _diag = build_selection_trace(
        module_id="A-E1", run_id=pred_run_id, specs=tuple(specs), evaluations_by_fit=evaluations)
    trace_path = pred_dir / "selection_trace.jsonl"
    trace_sha = write_selection_trace(trace_path, records)
    publish_selection_receipt(
        receipt_path=pred_dir / "selection_receipt.json", ledger_path=pred_dir / "selection_ledger.jsonl",
        module_id="A-E1", run_id=pred_run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=EFFECTIVE, code_commit=_D8_CODE_COMMIT)
    (pred_dir / "manifest.json").write_text(json.dumps({"code_commit": _D8_CODE_COMMIT}, sort_keys=True) + "\n", encoding="utf-8")
    route, distribution, n_mode, fixed_n, training_size = "selected:F2_or_V", "core_continuous", "fixed_n", 10, 100000
    t_key = _deferred_cache_key("training", route=route, distribution=distribution, n_mode=n_mode,
                                fixed_n=fixed_n, training_size=training_size, pred_sha=trace_sha)
    v_key = _deferred_cache_key("validation", route=route, distribution=distribution, n_mode=n_mode,
                                fixed_n=fixed_n, training_size=training_size, pred_sha=trace_sha)
    ae3_dir = tmp_path / "A-E3" / "r1"
    ae3_dir.mkdir(parents=True)
    (ae3_dir / "plan.jsonl").write_text(json.dumps({
        "fit_id": "G3-AE3-0000", "module_id": "A-E3", "route": route, "distribution": distribution,
        "n_mode": n_mode, "fixed_n": fixed_n, "training_size": training_size,
        "predecessor_trace_sha256": trace_sha, "training_cache_key": t_key, "validation_cache_key": v_key,
    }, sort_keys=True) + "\n", encoding="utf-8")
    resolved = run_study02a.resolve_deferred(
        module="A-E3", run_id="r1", artifact_root=tmp_path,
        predecessor_module="A-E1", predecessor_run_id=pred_run_id)
    assert len(resolved) == 1
    assert resolved[0]["training_cache_key"] == t_key
    assert resolved[0]["validation_cache_key"] == v_key


def test_formal_resolve_deferred_cli_fail_closed_wrong_order(tmp_path):
    """A-E2's predecessor must be A-E3, not A-E1 -- the resolve-deferred CLI rejects wrong order."""
    import pytest as _pt
    import run_study02a
    specs, evaluations = _staged_specs_and_evaluations()
    pred_run_id = "G3-AE1-pred-v1"
    pred_dir = tmp_path / "A-E1" / pred_run_id
    pred_dir.mkdir(parents=True)
    records, _diag = build_selection_trace(
        module_id="A-E1", run_id=pred_run_id, specs=tuple(specs), evaluations_by_fit=evaluations)
    trace_path = pred_dir / "selection_trace.jsonl"
    trace_sha = write_selection_trace(trace_path, records)
    publish_selection_receipt(
        receipt_path=pred_dir / "selection_receipt.json", ledger_path=pred_dir / "selection_ledger.jsonl",
        module_id="A-E1", run_id=pred_run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=EFFECTIVE, code_commit=_D8_CODE_COMMIT)
    (pred_dir / "manifest.json").write_text(json.dumps({"code_commit": _D8_CODE_COMMIT}, sort_keys=True) + "\n", encoding="utf-8")
    ae2_dir = tmp_path / "A-E2" / "r1"
    ae2_dir.mkdir(parents=True)
    (ae2_dir / "plan.jsonl").write_text(json.dumps({
        "fit_id": "G3-AE2-0000", "module_id": "A-E2", "route": "selected:F2_or_V",
        "distribution": "core_continuous", "n_mode": "fixed_n", "fixed_n": 10, "training_size": 100000,
        "predecessor_trace_sha256": trace_sha, "training_cache_key": "0" * 64, "validation_cache_key": "0" * 64,
    }, sort_keys=True) + "\n", encoding="utf-8")
    with _pt.raises(ValueError, match="[Ww]rong predecessor"):
        run_study02a.resolve_deferred(
            module="A-E2", run_id="r1", artifact_root=tmp_path,
            predecessor_module="A-E1", predecessor_run_id=pred_run_id)


def _accredit_search_fit_ids():
    """The frozen A-E1 selection-candidate fit_ids (search_stage1 + search_stage2 = 144) -- the set
    accredit_build must accredit, derived from the real matrix (never a directory scan)."""
    return [str(r["fit_id"]) for r in MATRIX_ROWS
            if str(r["module"]) == "A-E1" and str(r["fit_kind"]) in ("search_stage1", "search_stage2")]


def _failed_fit_evaluation(*, fit_id, plan_row, matrix_row):
    """A failed FitEvaluation with all-illegal point records over synthetic validation cells
    (mirrors _score_fit_from_checkpoint's failed branch): no checkpoint, frozen penalty 10.0."""
    seed = int(plan_row["seed"]); n = int(matrix_row["n"])
    illegal = tuple({
        "sample_id": f"n{n}:pt{p}", "seed_id": str(seed), "point_id": f"n{n}:pt{p}",
        "legal": False, "failure": 1, "l_param": 10.0, "e_beta": 10.0, "e_eta": 10.0, "e_gamma": 10.0,
    } for p in range(2))
    route = str(plan_row["route"])
    if str(matrix_row["fit_kind"]) == "search_stage1":
        decision_id = f"architecture:A-E1:{route}:n{fe._A_E1_SEARCH_N}"; candidate_id = str(plan_row["architecture"])
    else:
        decision_id = f"stage2:A-E1:{route}:n{fe._A_E1_SEARCH_N}"
        candidate_id = f"{plan_row['architecture']}:{plan_row['optimizer']}"
    return FitEvaluation(
        fit_id=fit_id, module_id="A-E1", decision_id=decision_id, candidate_id=candidate_id,
        support_key=SupportKey(n=n, seed=seed), failed=True, checkpoint_sha256="",
        validation_identity=f"val-cache-{fit_id}", selection_score=0.0, failure_penalty=10.0,
        point_records=illegal,
    )


def _accredit_real_matrix_run(tmp_path, monkeypatch, *, failed_fit=None, run_id="G3-AE1-build-v1"):
    """Publish a real-matrix A-E1 selection run into ``tmp_path/A-E1/<run_id>``: a ``_PLAN_FIELDS``
    plan (n via n_mode/fixed_n, NO ``n`` field), per-fit ``outputs/{fit}/evidence.json`` + scheduler
    terminal receipts, the full formal manifest, then ``build_module_selection(score_fit=...)``
    publishes the selection trace/receipt/ledger/diagnostics + the RELOCATED point evidence
    (``selection/point_evidence/{fit}.json``). No real scheduler/training; the bundle's
    ``rebuild_selection_point_provenance`` is monkeypatched. Returns ``(run_dir, fit_ids, evaluations)``."""
    import run_study02a
    import study02a.formal_accreditation as formal_accreditation
    from study02a.formal_contracts import APPROVED_EFFECTIVE_CONFIG_SHA256
    run_dir = tmp_path / "A-E1" / run_id
    run_dir.mkdir(parents=True)
    search_rows = [r for r in MATRIX_ROWS
                   if str(r["module"]) == "A-E1" and str(r["fit_kind"]) in ("search_stage1", "search_stage2")]
    fit_ids = [str(r["fit_id"]) for r in search_rows]
    base_score = _smoke_score_fit()
    evaluations_by_fit = {}
    plan_lines = []
    plan_row_objs = []
    for index, r in enumerate(search_rows):
        fit_id = str(r["fit_id"]); n = int(r["n"]); seed = int(r["seed"])
        plan_row_obj = _plan_row(
            plan_index=index, run_id=run_id, fit_id=fit_id, module_id="A-E1",
            rule_id=str(r["rule_id"]), route=str(r["route"]), distribution="core_continuous",
            n_mode="fixed_n", fixed_n=n, loss=str(r["loss"]), architecture=str(r["architecture"]),
            optimizer=str(r["optimizer"]), training_size=int(r["training_size"]), seed=seed,
            code_commit=_D8_CODE_COMMIT,
        )
        score_plan_row = {
            "fit_id": fit_id, "route": str(r["route"]), "seed": seed,
            "architecture": str(r["architecture"]), "optimizer": str(r["optimizer"]),
        }
        if failed_fit is not None and fit_id == failed_fit:
            evaluation = _failed_fit_evaluation(fit_id=fit_id, plan_row=score_plan_row, matrix_row=r)
        else:
            evaluation = base_score(fit_id, score_plan_row)
        evaluations_by_fit[fit_id] = evaluation
        plan_lines.append(json.dumps(plan_row_obj, sort_keys=True))
        plan_row_objs.append(plan_row_obj)
        if failed_fit is not None and fit_id == failed_fit:
            (run_dir / "receipts").mkdir(parents=True, exist_ok=True)
            (run_dir / "receipts" / f"{fit_id}.failed.json").write_text(json.dumps({
                "receipt_version": "study02-formal-fit-terminal-v2", "run_id": run_id, "fit_id": fit_id,
                "state": "failed", "details": {"failure_code": "dead_identity_no_outputs"},
                "test_access_count": 0,
            }, sort_keys=True) + "\n", encoding="utf-8")
        else:
            (run_dir / "outputs" / fit_id).mkdir(parents=True, exist_ok=True)
            curve = [100.0 / (i + 1) for i in range(60)]
            (run_dir / "outputs" / fit_id / "evidence.json").write_text(json.dumps({
                "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": fit_id, "run_id": run_id,
                "checkpoint_sha256": evaluation.checkpoint_sha256, "actual_epochs": 60,
                "best_epoch_one_based": 1, "hit_epoch_100": False, "early_stop_reason": "patience_exhausted",
                "terminal_validation_slope": fe._terminal_ols_slope(tuple(curve)),
                "validation_curve": curve, "test_access_count": 0,
            }, sort_keys=True) + "\n", encoding="utf-8")
            (run_dir / "receipts").mkdir(parents=True, exist_ok=True)
            (run_dir / "receipts" / f"{fit_id}.succeeded.json").write_text(json.dumps({
                "receipt_version": "study02-formal-fit-terminal-v2", "run_id": run_id, "fit_id": fit_id,
                "state": "succeeded", "details": {"output_hashes": {}}, "test_access_count": 0,
            }, sort_keys=True) + "\n", encoding="utf-8")
    (run_dir / "plan.jsonl").write_text("".join(line + "\n" for line in plan_lines), encoding="utf-8")
    manifest = {
        "manifest_version": "study02-formal-v1", "module_id": "A-E1", "run_id": run_id,
        "code_commit": _D8_CODE_COMMIT,
        "base_protocol": {"id": "A-G2-v1", "sha256": "f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11"},
        "base_search": {"id": "A-G2-search-v1", "sha256": "abd6d17b1d2467e1253e0154adba0b6582a3feeb83ed889534ed4f6ab5e0ca13"},
        "amendment": {"id": "A-G3-pilot-amendment-v4", "sha256": "164e72658669dbb57f6dab8b1fc80099bd319f1fa327d5dda60cb61cb929ee38"},
        "effective_config": {"sha256": APPROVED_EFFECTIVE_CONFIG_SHA256, "max_epochs": 100, "min_epochs": 50, "patience": 40},
        "matrix": {"path": "experiment_matrix.csv",
                   "sha256": "fad701af2e2084bf7ce8f678d642410af58057b4ae33029c9150e50971fdf6b1",
                   "row_count": 820, "rule_ids": ["A-E1_optimized_supplement"], "fit_ids": fit_ids},
        "role_namespaces": {"training": "study02/formal/training", "validation": "study02/formal/validation"},
        "seeds": {"screening": [420001, 420002, 420003], "formal": list(range(420101, 420111))},
        "test_state": "sealed",
        "predecessor": {"module_id": "none", "run_id": "none", "selection_trace_path": "none",
                        "selection_trace_sha256": "none", "selection_receipt_path": "none",
                        "selection_receipt_sha256": "none", "selection_ledger_path": "none"},
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, sort_keys=True) + "\n", encoding="utf-8")
    # publish selection via the real engine path -> publishes the RELOCATED point evidence
    fe.build_module_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        module_id="A-E1", run_id=run_id,
        score_fit=lambda fit_id, plan_row: evaluations_by_fit[str(fit_id)])
    # bundle rebuild stands in for reading bound checkpoints (no training, no test read)
    monkeypatch.setattr(fe, "rebuild_selection_point_provenance",
                        lambda *, study_root, run_dir, cache_root, module_id, run_id: dict(evaluations_by_fit))
    # authority preflight stands in for the full _rebuild_authority replay: returns the verified
    # manifest/plan/fit_states (fit_states matching the fixture's terminal receipts) so accredit_build's
    # processing path is exercised without a multi-hour real-scheduler run. The REAL rebuild's tamper-
    # detection is covered by the attack tests (which use the unmocked _rebuild_authority).
    _fit_states = {fid: ("failed" if (failed_fit is not None and fid == failed_fit) else "succeeded")
                   for fid in fit_ids}

    def _fake_rebuild_authority(run_dir, cache_root, **kw):
        return manifest, list(plan_row_objs), {"fit_states": dict(_fit_states)}, []
    monkeypatch.setattr(formal_accreditation, "_rebuild_authority", _fake_rebuild_authority)
    return run_dir, fit_ids, evaluations_by_fit


def test_formal_accredit_build_generates_sealed_bundle(tmp_path, monkeypatch):
    """accredit_build derives the expected selection set from the FROZEN matrix (no directory scan),
    reads RELOCATED point evidence (selection/point_evidence/{fit}.json -- never outputs/{fit}/),
    recovers n from n_mode/fixed_n (the plan has no 'n'), and builds the sealed pre-unseal bundle."""
    import csv
    import run_study02a
    from study02a.selection import serialize_point_evidence
    from study02a.formal_contracts import APPROVED_EFFECTIVE_CONFIG_SHA256
    run_id = "G3-AE1-build-v1"
    run_dir, fit_ids, evaluations = _accredit_real_matrix_run(tmp_path, monkeypatch)
    # contract 1: outputs/{fit_id}/ holds NO point_evidence after selection (it is relocated, so the
    # scheduler-authority dir stays exactly the frozen expected_outputs).
    assert not any((run_dir / "outputs" / fid).joinpath("point_evidence.json").exists() for fid in fit_ids)
    # contract: the selection point-evidence dir holds exactly the 144 expected candidates
    pe_dir = run_dir / "selection" / "point_evidence"
    assert sorted(p.stem for p in pe_dir.iterdir()) == sorted(fit_ids)
    # contract 3: the relocated content is byte-identical to the pre-relocation canonical artifact
    sample_fit = fit_ids[0]
    published = json.loads((pe_dir / f"{sample_fit}.json").read_text(encoding="utf-8"))
    assert published == serialize_point_evidence(evaluations[sample_fit])
    from study02a.formal_accreditation import build_module_accreditation_diagnostics
    diagnostics = build_module_accreditation_diagnostics(
        study_root=STUDY_ROOT, module="A-E1", run_id=run_id,
        artifact_root=tmp_path, cache_root=tmp_path / "cache",
    )
    assert diagnostics["module"] == "A-E1"
    assert not (run_dir / "pre_unseal_bundle.json").exists()
    assert (run_dir / "ceiling_hit_report.json").is_file()
    # contract 6: fit_status covers every selection candidate with n recovered from n_mode/fixed_n
    # (the plan carries no 'n'); no fit vanishes and no KeyError on plan_row['n'].
    fit_id_set = set(fit_ids)
    matrix_n = {str(r["fit_id"]): int(r["n"]) for r in MATRIX_ROWS if str(r["fit_id"]) in fit_id_set}
    with (run_dir / "fit_status.csv").open(encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    assert {r["fit_id"] for r in rows} == set(fit_ids)
    assert all(int(r["n"]) == matrix_n[r["fit_id"]] for r in rows)
    leakage = json.loads((run_dir / "leakage_audit.json").read_text(encoding="utf-8"))
    assert leakage["test_access_count"] == 0
    assert all(value == 0 for value in leakage["pairwise_intersections"].values())
    assert set(leakage["parameter_point_counts"]) == {"training", "validation", "calibration", "test"}
    # Preparation ends at sealed diagnostics/bundle; the superseded module authorize path is blocked.
    with pytest.raises(SystemExit, match="permanently BLOCKED"):
        run_study02a.accredit_authorize(
            module="A-E1", run_id=run_id, artifact_root=tmp_path,
            approval_path=run_dir / "approval.json", oracle_review_path=run_dir / "review.json",
            run_family_id="G3-formal", timestamp="2026-07-19T11:00:00+08:00")
    assert not (run_dir / "formal_state.json").exists()


def test_accredit_build_failed_selection_fit_is_not_silently_skipped(tmp_path, monkeypatch):
    """Contract 7: a selection candidate whose training failed (no evidence.json) is NOT silently
    dropped from accreditation. Its failure fit_status is generated from the scheduler terminal
    receipt (failure_code) + the point-evidence failure record (failed flag + frozen penalty)."""
    import csv
    import run_study02a
    run_id = "G3-AE1-build-v1"
    fit_ids = _accredit_search_fit_ids()
    failed_fit = fit_ids[0]
    run_dir, _fit_ids, _evals = _accredit_real_matrix_run(tmp_path, monkeypatch, failed_fit=failed_fit)
    # the failed fit produced no training evidence.json
    assert not (run_dir / "outputs" / failed_fit / "evidence.json").is_file()
    from study02a.formal_accreditation import build_module_accreditation_diagnostics
    build_module_accreditation_diagnostics(
        study_root=STUDY_ROOT, module="A-E1", run_id=run_id,
        artifact_root=tmp_path, cache_root=tmp_path / "cache",
    )
    with (run_dir / "fit_status.csv").open(encoding="utf-8") as fh:
        rows = {r["fit_id"]: r for r in csv.DictReader(fh)}
    # every selection candidate is present -- the failed one did not vanish
    assert set(rows) == set(fit_ids)
    failed_row = rows[failed_fit]
    assert failed_row["failed"] in ("True", "true", "1", True)
    assert failed_row["failure_penalty"] == "10.0"
    assert failed_row["failure_message"] == "dead_identity_no_outputs"
    assert failed_row["checkpoint_sha256"] == "" and failed_row["validation_score"] == ""


@pytest.mark.parametrize("defect", ["missing", "extra", "unknown_fit", "nested", "wrong_suffix"])
def test_validate_selection_point_evidence_dir_fail_closed(tmp_path, defect):
    """Contract 5: the selection point-evidence dir must hold exactly the expected {fit_id}.json;
    missing/extra/unknown-fit/nested/non-json entries all fail closed."""
    expected = {"f1", "f2", "f3"}
    pe_dir = tmp_path / "selection" / "point_evidence"
    pe_dir.mkdir(parents=True)
    present = set(expected)
    if defect == "missing":
        present.discard("f2")
    elif defect == "extra":
        present.add("fX")  # unknown fit_id
        present  # noqa
    elif defect == "unknown_fit":
        present = {"f1", "f2", "fX"}  # f3 replaced by unknown fX
    for fid in present:
        (pe_dir / f"{fid}.json").write_text("{}", encoding="utf-8")
    if defect == "nested":
        (pe_dir / "subdir").mkdir()
    elif defect == "wrong_suffix":
        (pe_dir / "f1.txt").write_text("x", encoding="utf-8")
        (pe_dir / "f1.json").unlink()
    if defect == "extra":
        # add the unknown extra file alongside the full expected set
        for fid in expected:
            if not (pe_dir / f"{fid}.json").exists():
                (pe_dir / f"{fid}.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError):
        fe._validate_selection_point_evidence_dir(run_dir=tmp_path, expected_fit_ids=set(expected))


def _make_dir_alias(target: Path, link: Path):
    """Create a directory alias ``link -> target`` and skip (without faking coverage) if the platform
    can create neither. Tries a POSIX symlink first, then a Windows junction (``mklink /J``, no
    privilege required); both are reparse/symlink entries that ``_reject_alias`` forbids, so either
    exercises the directory alias-chain rejection on its platform."""
    try:
        os.symlink(target, link); return
    except (OSError, NotImplementedError):
        pass
    if os.name == "nt":
        import subprocess
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                capture_output=True, text=True)
        if result.returncode == 0 and link.exists():
            return
    pytest.skip("neither symlink nor junction creation available on this platform")


def test_point_evidence_dir_rejects_alias_directory(tmp_path):
    """The selection point_evidence directory ITSELF being a symlink/junction/reparse is rejected
    (the dir alias-chain check walks the directory + all parents)."""
    expected = {"f1", "f2", "f3"}
    target = tmp_path / "real_point_evidence"; target.mkdir(parents=True)
    for fid in expected:
        (target / f"{fid}.json").write_text("{}", encoding="utf-8")
    run_dir = tmp_path / "run"; (run_dir / "selection").mkdir(parents=True)
    _make_dir_alias(target, run_dir / "selection" / "point_evidence")
    with pytest.raises(ValueError, match="alias|reparse"):
        fe._validate_selection_point_evidence_dir(run_dir=run_dir, expected_fit_ids=set(expected))


def test_point_evidence_dir_rejects_alias_selection_parent(tmp_path):
    """A symlink/junction on the ``selection`` PARENT is rejected: _reject_alias walks all parents."""
    expected = {"f1", "f2", "f3"}
    target = tmp_path / "real_selection" / "point_evidence"; target.mkdir(parents=True)
    for fid in expected:
        (target / f"{fid}.json").write_text("{}", encoding="utf-8")
    run_dir = tmp_path / "run"; run_dir.mkdir(parents=True)
    _make_dir_alias(target.parent, run_dir / "selection")
    with pytest.raises(ValueError, match="alias|reparse"):
        fe._validate_selection_point_evidence_dir(run_dir=run_dir, expected_fit_ids=set(expected))


def test_point_evidence_dir_accepts_real_directory(tmp_path):
    """Sanity: a plain real directory of the exact expected files passes (no alias)."""
    expected = {"f1", "f2", "f3"}
    pe_dir = tmp_path / "selection" / "point_evidence"; pe_dir.mkdir(parents=True)
    for fid in expected:
        (pe_dir / f"{fid}.json").write_text("{}", encoding="utf-8")
    by_fit = fe._validate_selection_point_evidence_dir(run_dir=tmp_path, expected_fit_ids=set(expected))
    assert set(by_fit) == expected


# ---------------------------------------------------------------------------
# Accreditation authority preflight (Gap 2): the real _rebuild_authority replay is the FIRST thing
# accredit_build does, so any tampering raises BEFORE any diagnostic file is written.
# ---------------------------------------------------------------------------

def _accredit_attack_run(tmp_path):
    """A minimal REAL scheduler run (materialize + 1 succeeded fit via synthetic outputs) for the
    accreditation authority-preflight attack tests. Self-contained (no cross-test-module import);
    mirrors test_study02a_formal_scheduler._build_mixed_run / _write_success. Returns (run_dir, cache)."""
    from study02a.formal_scheduler import materialize_run, claim_next_fit, record_fit_succeeded
    matrix_path = STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv"
    run_dir = Path(materialize_run(
        study_root=STUDY_ROOT, matrix_path=matrix_path, module_id="A-E1", run_id="G3-AE1-attack-v1",
        artifact_root=tmp_path / "artifacts", cache_root=tmp_path / "cache", predecessor=None)["run_dir"])
    cache = tmp_path / "cache"
    claim = claim_next_fit(run_dir, cache_root=cache, owner_id="w1", owner_nonce="n1", timestamp="2026-07-20T00:00:00Z")
    fit_id, run_id_val = claim["fit_id"], claim["run_id"]
    ckpt = b"attack-checkpoint"; ckpt_sha = hashlib.sha256(ckpt).hexdigest()
    curve = [100.0 / (i + 1) for i in range(60)]
    best_epoch_zero = min(range(len(curve)), key=lambda i: curve[i])
    evidence = {
        "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": fit_id, "run_id": run_id_val,
        "checkpoint_sha256": ckpt_sha, "actual_epochs": len(curve),
        "best_epoch_one_based": best_epoch_zero + 1, "hit_epoch_100": False,
        "early_stop_reason": "patience_exhausted",
        "terminal_validation_slope": fe._terminal_ols_slope(tuple(curve)),
        "validation_curve": curve, "test_access_count": 0,
    }
    output_hashes = fe._write_outputs(run_dir, fit_id, run_id_val, ckpt, ckpt_sha, evidence)
    record_fit_succeeded(run_dir, cache_root=cache, fit_id=fit_id, owner_id="w1", owner_nonce="n1",
                         output_hashes=output_hashes, timestamp="2026-07-20T00:00:01Z")
    return run_dir, cache


def _assert_no_accredit_diagnostics(run_dir: Path):
    assert not (run_dir / "fit_status.csv").exists()
    assert not (run_dir / "ceiling_hit_report.json").exists()
    assert not (run_dir / "leakage_audit.json").exists()
    assert not (run_dir / "pre_unseal_bundle.json").exists()


def test_accredit_build_rejects_tampered_terminal_receipt(tmp_path):
    """A terminal receipt rewritten (filename unchanged) flips its hash vs the event's receipt_sha256;
    the authority preflight (_rebuild_authority) raises before any diagnostic is written."""
    import run_study02a
    run_dir, cache = _accredit_attack_run(tmp_path)
    receipt_file = sorted((run_dir / "receipts").glob("*.succeeded.json"))[0]
    forged = json.loads(receipt_file.read_text(encoding="utf-8")); forged["owner_id"] = "tampered-owner"
    receipt_file.write_bytes(fe._canonical(forged))
    with pytest.raises(ValueError):
        from study02a.formal_accreditation import build_module_accreditation_diagnostics
        build_module_accreditation_diagnostics(
            study_root=STUDY_ROOT, module="A-E1", run_id="G3-AE1-attack-v1",
            artifact_root=tmp_path / "artifacts", cache_root=cache,
        )
    _assert_no_accredit_diagnostics(run_dir)


def test_accredit_build_rejects_tampered_plan(tmp_path):
    """plan.jsonl tampered after materialize -> plan_sha256 mismatch -> preflight raises, no diagnostics."""
    import run_study02a
    run_dir, cache = _accredit_attack_run(tmp_path)
    plan_file = run_dir / "plan.jsonl"
    plan_file.write_bytes(plan_file.read_bytes() + b'{"tampered": true}\n')
    with pytest.raises(ValueError, match="plan"):
        from study02a.formal_accreditation import build_module_accreditation_diagnostics
        build_module_accreditation_diagnostics(
            study_root=STUDY_ROOT, module="A-E1", run_id="G3-AE1-attack-v1",
            artifact_root=tmp_path / "artifacts", cache_root=cache,
        )
    _assert_no_accredit_diagnostics(run_dir)


def test_accredit_build_rejects_tampered_event(tmp_path):
    """A scheduler event rewritten -> event-chain/hash mismatch -> preflight raises, no diagnostics."""
    import run_study02a
    run_dir, cache = _accredit_attack_run(tmp_path)
    event_file = sorted((run_dir / "events").glob("*.json"))[-1]
    forged = json.loads(event_file.read_text(encoding="utf-8")); forged["payload"]["tampered"] = True
    event_file.write_bytes(fe._canonical(forged))
    with pytest.raises(ValueError):
        from study02a.formal_accreditation import build_module_accreditation_diagnostics
        build_module_accreditation_diagnostics(
            study_root=STUDY_ROOT, module="A-E1", run_id="G3-AE1-attack-v1",
            artifact_root=tmp_path / "artifacts", cache_root=cache,
        )
    _assert_no_accredit_diagnostics(run_dir)


# ---------------------------------------------------------------------------
# Staged execution state machine (deadlock fix): per-stage selection receipts that do NOT
# require future-stage evidence. Stage-1 first: publish a partial selection over the stage-1
# architecture decisions alone and derive top4, so stage-2 (selected_top_*) can concretize.
# ---------------------------------------------------------------------------

def test_build_a_e1_stage1_selection_publishes_partial_receipt_and_top4(tmp_path):
    """Per-route stage-1 selection builds an immutable partial trace/receipt/ledger over ONE route's
    stage-1 architecture decision (no stage-2 / winner-retrain / other-route evidence needed) and
    derives that route's top4. The plan order is route-interleaved, so receipts must be per-route."""
    run_id = "G3-AE1-staged-exec-v1"
    run_dir = tmp_path / "A-E1" / run_id
    run_dir.mkdir(parents=True)
    plan_rows = [r for r in MATRIX_ROWS if str(r["module"]) == "A-E1"]
    (run_dir / "plan.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in plan_rows), encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"code_commit": _D8_CODE_COMMIT}, sort_keys=True) + "\n", encoding="utf-8")

    def score_fit(fit_id, plan_row):
        route = str(plan_row["route"]); arch = str(plan_row["architecture"])
        decision_id = f"architecture:A-E1:{route}:n{fe._A_E1_SEARCH_N}"
        base = 0.01 * int(arch[1:])  # m01 best ... m12 worst
        key = SupportKey(n=int(plan_row["n"]), seed=int(plan_row["seed"]))
        records = _synth_point_records(fit_id, int(plan_row["seed"]), base)
        return FitEvaluation(
            fit_id=fit_id, module_id="A-E1", decision_id=decision_id, candidate_id=arch,
            support_key=key, failed=False, checkpoint_sha256=hashlib.sha256(fit_id.encode("utf-8")).hexdigest(),
            validation_identity=f"val-cache-{fit_id}",
            selection_score=sum(rec["l_param"] for rec in records) / len(records),
            failure_penalty=0.0, point_records=records)

    for route in ("F2", "V"):
        result = fe.build_a_e1_stage1_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache", run_id=run_id,
            route=route, score_fit=score_fit)
        top4 = result["top4"]
        assert list(top4) == ["selected_top_1", "selected_top_2", "selected_top_3", "selected_top_4"]
        assert (top4["selected_top_1"], top4["selected_top_2"],
                top4["selected_top_3"], top4["selected_top_4"]) == ("m01", "m02", "m03", "m04")
        records = [json.loads(line) for line in (run_dir / f"stage1_selection_{route}_trace.jsonl").read_text(encoding="utf-8").splitlines()]
        assert {r["decision_id"] for r in records} == {f"architecture:A-E1:{route}:n{fe._A_E1_SEARCH_N}"}
        assert (run_dir / f"stage1_selection_{route}_receipt.json").is_file()
        assert (run_dir / f"stage1_selection_{route}_ledger.jsonl").is_file()


def test_a_e1_fit_stage_classifies_plan_rows():
    """The stage classifier routes rows to the staged-execution stages."""
    assert fe._a_e1_fit_stage({"fit_kind": "historical"}) == "concrete"
    assert fe._a_e1_fit_stage({"fit_kind": "controlled"}) == "concrete"
    assert fe._a_e1_fit_stage({"fit_kind": "search_stage1"}) == "concrete"
    assert fe._a_e1_fit_stage({"fit_kind": "search_stage2"}) == "stage2"
    assert fe._a_e1_fit_stage({"fit_kind": "winner_retrain"}) == "winner_retrain"


def test_build_a_e1_stage2_selection_maps_winner_to_concrete(tmp_path):
    """Per-route stage-2 selection publishes a partial receipt over ONE route's stage-2 decision
    and maps the winner (selected_top_{slot}:{opt}) to the concrete architecture (top4[slot]) +
    optimizer + frozen loss."""
    run_id = "G3-AE1-staged-exec-v1"
    run_dir = tmp_path / "A-E1" / run_id
    run_dir.mkdir(parents=True)
    plan_rows = [r for r in MATRIX_ROWS if str(r["module"]) == "A-E1"]
    (run_dir / "plan.jsonl").write_text(
        "".join(json.dumps(r, sort_keys=True) + "\n" for r in plan_rows), encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"code_commit": _D8_CODE_COMMIT}, sort_keys=True) + "\n", encoding="utf-8")
    top4 = {f"selected_top_{i}": f"m0{i}" for i in range(1, 5)}

    def score_fit(fit_id, plan_row):
        route = str(plan_row["route"]); arch = str(plan_row["architecture"]); opt = str(plan_row["optimizer"])
        candidate_id = f"{arch}:{opt}"
        forced = {"F2": "selected_top_2:o2", "V": "selected_top_3:o3"}[route]
        base = 0.001 if candidate_id == forced else 0.5
        key = SupportKey(n=int(plan_row["n"]), seed=int(plan_row["seed"]))
        records = _synth_point_records(fit_id, int(plan_row["seed"]), base)
        return FitEvaluation(
            fit_id=fit_id, module_id="A-E1",
            decision_id=f"stage2:A-E1:{route}:n{fe._A_E1_SEARCH_N}", candidate_id=candidate_id,
            support_key=key, failed=False, checkpoint_sha256=hashlib.sha256(fit_id.encode("utf-8")).hexdigest(),
            validation_identity=f"val-cache-{fit_id}",
            selection_score=sum(rec["l_param"] for rec in records) / len(records),
            failure_penalty=0.0, point_records=records)

    f2 = fe.build_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache", run_id=run_id,
        route="F2", top4=top4, score_fit=score_fit)
    assert f2["winner"] == {"selected:A-E1_loss": "transformed_train_z_huber",
                            "selected:A-E1_architecture": "m02", "selected:A-E1_optimizer": "o2"}
    v = fe.build_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache", run_id=run_id,
        route="V", top4=top4, score_fit=score_fit)
    assert v["winner"] == {"selected:A-E1_loss": "transformed_train_z_huber",
                           "selected:A-E1_architecture": "m03", "selected:A-E1_optimizer": "o3"}


def test_staged_plan_row_resolvers_concretize_and_fail_closed():
    """The placeholder resolvers map stage2/winner-retrain rows to concrete plan rows and fail
    closed when the resolving receipt lacks the needed slot."""
    top4 = {"selected_top_1": "m01", "selected_top_2": "m02"}
    winner = {"selected:A-E1_loss": "transformed_train_z_huber",
              "selected:A-E1_architecture": "m02", "selected:A-E1_optimizer": "o2"}
    assert fe._resolve_stage2_plan_row({"architecture": "selected_top_2"}, top4)["architecture"] == "m02"
    retrained = fe._resolve_winner_retrain_plan_row({"route": "F2"}, winner)
    assert retrained["architecture"] == "m02" and retrained["optimizer"] == "o2"
    assert retrained["loss"] == "transformed_train_z_huber"
    import pytest as _pt
    with _pt.raises(ValueError, match="top4"):
        fe._resolve_stage2_plan_row({"architecture": "selected_top_9"}, top4)


# ---------------------------------------------------------------------------
# Source-of-truth fix: fit_kind is read from the authoritative frozen matrix (looked up by
# fit_id), never from plan.jsonl (which omits it). plan.jsonl is validated against the matrix
# (exact fit_id correspondence + per-row matrix_row_sha256 binding) and staged receipts are
# recovered from disk on restart. No direct top4/winner/stage-state injection.
# ---------------------------------------------------------------------------

def _real_a_e1_plan_rows(tmp_path, *, run_id="G3-AE1-staged-exec-v1", code_commit=_D8_CODE_COMMIT):
    """Build the REAL A-E1 plan.jsonl rows (the frozen _PLAN_FIELDS schema, NO fit_kind) via the
    scheduler's own _plan_rows, so tests exercise the true plan shape rather than a matrix-shaped
    stand-in. ``matrix_row_sha256`` is computed exactly as the scheduler does, so it matches the
    authoritative matrix row hash."""
    from study02a.formal_scheduler import _plan_rows, _PLAN_FIELDS
    matrix_str = [{key: str(value) for key, value in row.items()}
                  for row in MATRIX_ROWS if str(row["module"]) == "A-E1"]
    plan = _plan_rows(STUDY_ROOT, matrix_str, "A-E1", run_id, tmp_path / "cache", code_commit, "0" * 64)
    assert all(set(row) == _PLAN_FIELDS for row in plan) and not any("fit_kind" in row for row in plan)
    return plan


def _write_real_a_e1_run(tmp_path, *, run_id="G3-AE1-staged-exec-v1"):
    """A run_dir holding a REAL A-E1 plan.jsonl (no fit_kind) + manifest, ready for staged calls."""
    run_dir = tmp_path / "A-E1" / run_id
    run_dir.mkdir(parents=True)
    plan = _real_a_e1_plan_rows(tmp_path, run_id=run_id)
    (run_dir / "plan.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in plan), encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"code_commit": _D8_CODE_COMMIT}, sort_keys=True) + "\n", encoding="utf-8")
    return run_dir, plan


def test_authoritative_matrix_and_plan_validation_real_plan_has_no_fit_kind(tmp_path):
    """The authoritative matrix keys every A-E1 fit uniquely (349) and validates the REAL plan
    (which carries no fit_kind) by exact fit_id set + per-row matrix_row_sha256. fit_kind is read
    from the matrix, so the first stage2 / winner-retrain boundaries classify correctly (the old
    plan-row classifier saw every row as 'concrete')."""
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    a_e1 = [fid for fid, row in matrix_by_fit.items() if str(row["module"]) == "A-E1"]
    assert len(a_e1) == 349 and len(set(a_e1)) == 349
    plan = _real_a_e1_plan_rows(tmp_path)
    assert not any("fit_kind" in row for row in plan)  # the frozen plan schema has no fit_kind
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan, matrix_by_fit=matrix_by_fit, module_id="A-E1")
    assert set(plan_by_fit) == set(a_e1)
    # boundaries classify from the matrix, where the plan-row classifier returned 'concrete'
    assert fe._a_e1_fit_stage(matrix_by_fit["G3-fit-0140"]) == "concrete"      # last F2 stage1 fit
    assert fe._a_e1_fit_stage(matrix_by_fit["G3-fit-0141"]) == "stage2"        # first F2 stage2 fit
    assert fe._a_e1_fit_stage(matrix_by_fit["G3-fit-0177"]) == "winner_retrain"  # first F2 winner-retrain


@pytest.mark.parametrize("defect", ["missing", "duplicate", "extra", "sha_mismatch", "fit_id_mismatch"])
def test_validate_plan_against_matrix_fail_closed(tmp_path, defect):
    """plan/matrix correspondence is fail-closed: a missing fit, a duplicate fit, an extra fit, a
    matrix_row_sha256 mismatch (stale plan / matrix tamper) and a fit_id<->row mismatch all raise."""
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan = _real_a_e1_plan_rows(tmp_path)
    if defect == "missing":
        plan = plan[:-1]
    elif defect == "duplicate":
        plan = plan + [dict(plan[0])]
    elif defect == "extra":
        bogus = dict(plan[0])
        bogus = {**bogus, "fit_id": "G3-fit-9999", "matrix_row_sha256": "0" * 64}
        plan = plan + [bogus]
    elif defect == "sha_mismatch":
        plan = [dict(plan[0], matrix_row_sha256="0" * 64)] + plan[1:]
    elif defect == "fit_id_mismatch":
        # give the first row a different fit_id than its matrix_row_sha256 binds (sha stays of the
        # original row -> mismatch on the looked-up matrix row)
        first = dict(plan[0])
        first["fit_id"] = "G3-fit-0001"
        plan = [first] + plan[1:]
    with pytest.raises(ValueError):
        fe._validate_plan_against_matrix(plan_rows=plan, matrix_by_fit=matrix_by_fit, module_id="A-E1")


def test_authoritative_matrix_rejects_duplicate_fit_id(monkeypatch):
    """A frozen matrix with a duplicate fit_id cannot become an authority (no unique mapping)."""
    rows = [{key: str(value) for key, value in row.items()}
            for row in MATRIX_ROWS if str(row["module"]) == "A-E1"]
    rows.append(dict(rows[0]))  # duplicate fit_id
    monkeypatch.setattr(fe, "expand_module_matrix", lambda frozen: __import__("pandas").DataFrame(rows))
    with pytest.raises(ValueError, match="duplicate fit_id"):
        fe._authoritative_matrix_by_fit(STUDY_ROOT)


def test_staged_path_publishes_stage1_receipt_with_real_plan_no_fit_kind(tmp_path):
    """With the REAL plan (no fit_kind) the matrix-classified stage2 boundary still publishes the
    route's stage1 receipt (top4) -- proving the source-of-truth fix triggers staged selection in a
    full run, where the old plan-row classifier never did. No training; score_fit injected."""
    run_dir, plan = _write_real_a_e1_run(tmp_path)
    result = fe._ensure_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id="G3-AE1-staged-exec-v1", route="F2", score_fit=_smoke_score_fit())
    top4 = result["top4"]
    assert list(top4) == ["selected_top_1", "selected_top_2", "selected_top_3", "selected_top_4"]
    assert (top4["selected_top_1"], top4["selected_top_2"]) == ("m01", "m02")
    assert (run_dir / "stage1_selection_F2_receipt.json").is_file()
    assert (run_dir / "stage1_selection_F2_trace.jsonl").is_file()
    assert (run_dir / "stage1_selection_F2_ledger.jsonl").is_file()


def test_stage2_and_winner_resolved_rows_carry_no_placeholders(tmp_path):
    """The runner receives CONCRETE architectures/optimizers/losses: a resolved stage2 row's
    architecture is the concrete top4 architecture (never ``selected_top_*``), and a resolved
    winner-retrain row carries no ``selected:A-E1_*`` placeholder."""
    run_dir, plan = _write_real_a_e1_run(tmp_path)
    plan_by_fit = {str(row["fit_id"]): row for row in plan}
    stage1 = fe._ensure_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id="G3-AE1-staged-exec-v1", route="F2", score_fit=_smoke_score_fit())
    stage2 = fe._ensure_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id="G3-AE1-staged-exec-v1", route="F2", score_fit=_smoke_score_fit(),
        stage1_by_route={"F2": stage1})
    # a real stage2 plan row (placeholder architecture) resolves to the concrete winner arch
    stage2_row = next(r for r in plan if str(r["architecture"]).startswith("selected_top_"))
    resolved_stage2 = fe._resolve_stage2_plan_row(stage2_row, stage1["top4"])
    assert not str(resolved_stage2["architecture"]).startswith("selected_top_")
    # a real winner-retrain plan row resolves to concrete arch/opt/loss (no selected:A-E1_*)
    winner_row = next(r for r in plan if str(r["architecture"]) == "selected:A-E1_architecture")
    resolved_winner = fe._resolve_winner_retrain_plan_row(winner_row, stage2["winner"])
    assert resolved_winner["architecture"] == stage2["winner"]["selected:A-E1_architecture"]
    assert resolved_winner["optimizer"] != "selected:A-E1_optimizer"
    assert resolved_winner["loss"] != "selected:A-E1_loss"


def test_ensure_stage1_recovers_existing_receipt_on_restart(tmp_path, monkeypatch):
    """After the stage1 receipt is published, a restart (fresh memory) RECOVERS it: the existing
    trace/receipt/ledger are re-validated and top4 reused -- ``build_a_e1_stage1_selection`` is NOT
    called again (no re-scoring, no re-publish, no overwrite)."""
    run_dir, _plan = _write_real_a_e1_run(tmp_path)
    run_id = "G3-AE1-staged-exec-v1"
    first = fe._ensure_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    receipt_bytes = (run_dir / "stage1_selection_F2_receipt.json").read_bytes()
    trace_bytes = (run_dir / "stage1_selection_F2_trace.jsonl").read_bytes()

    def _fail_if_called(**kwargs):
        raise AssertionError("restart must recover the existing stage1 receipt, not rebuild it")
    monkeypatch.setattr(fe, "build_a_e1_stage1_selection", _fail_if_called)
    recovered = fe._ensure_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    assert recovered["top4"] == first["top4"]
    assert recovered["selection_trace_sha256"] == first["selection_trace_sha256"]
    # nothing was overwritten
    assert (run_dir / "stage1_selection_F2_receipt.json").read_bytes() == receipt_bytes
    assert (run_dir / "stage1_selection_F2_trace.jsonl").read_bytes() == trace_bytes


def test_ensure_stage2_recovers_existing_receipt_after_stage2_before_winner(tmp_path, monkeypatch):
    """Stage-2 complete but winner-retrain not yet reached: a restart recovers BOTH the stage1 top4
    and the stage2 winner from their receipts (neither builder is called again)."""
    run_dir, _plan = _write_real_a_e1_run(tmp_path)
    run_id = "G3-AE1-staged-exec-v1"
    stage1 = fe._ensure_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    fe._ensure_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, route="F2", score_fit=_smoke_score_fit(), stage1_by_route={"F2": stage1})
    winner_bytes = (run_dir / "stage2_selection_F2_receipt.json").read_bytes()

    calls = []
    real_build_s1 = fe.build_a_e1_stage1_selection
    real_build_s2 = fe.build_a_e1_stage2_selection
    monkeypatch.setattr(fe, "build_a_e1_stage1_selection",
                        lambda **kw: calls.append("s1") or real_build_s1(**kw))
    monkeypatch.setattr(fe, "build_a_e1_stage2_selection",
                        lambda **kw: calls.append("s2") or real_build_s2(**kw))
    stage1_by_route: dict = {}  # empty -> simulates a restart (no in-memory cache)
    recovered = fe._ensure_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, route="F2", score_fit=_smoke_score_fit(), stage1_by_route=stage1_by_route)
    assert calls == []  # nothing rebuilt
    assert set(stage1_by_route) == {"F2"}  # stage1 top4 was recovered into the cache
    assert recovered["winner"]["selected:A-E1_architecture"] == "m02"  # F2 forced winner
    assert (run_dir / "stage2_selection_F2_receipt.json").read_bytes() == winner_bytes


@pytest.mark.parametrize("tamper", ["trace", "receipt", "ledger", "delete_receipt"])
def test_recover_stage1_receipt_fail_closed(tmp_path, tamper):
    """A stage1 receipt that is tampered (trace/receipt/ledger) or has its receipt deleted while the
    trace remains cannot be recovered -- the recovery re-validates and fails closed (no silent reuse
    of an unverified/hand-edited receipt)."""
    run_dir, _plan = _write_real_a_e1_run(tmp_path)
    run_id = "G3-AE1-staged-exec-v1"
    fe._ensure_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    trace_path = run_dir / "stage1_selection_F2_trace.jsonl"
    receipt_path = run_dir / "stage1_selection_F2_receipt.json"
    ledger_path = run_dir / "stage1_selection_F2_ledger.jsonl"
    if tamper == "trace":
        trace_path.write_bytes(trace_path.read_bytes() + b'\n{"injected": true}\n')
    elif tamper == "receipt":
        # break the receipt<->trace binding (the validated field), not an inert literal
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["selection_trace_sha256"] = "0" * 64
        receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
    elif tamper == "ledger":
        # append a second formal-selection binding -> len(bindings) != 1
        ledger_path.write_bytes(ledger_path.read_bytes() + ledger_path.read_bytes().splitlines()[0] + b"\n")
    elif tamper == "delete_receipt":
        receipt_path.unlink()
    with pytest.raises((ValueError, FileNotFoundError, json.JSONDecodeError)):
        fe._recover_a_e1_stage1_selection(run_dir=run_dir, run_id=run_id, route="F2")


def test_recover_stage2_fails_closed_when_winner_slot_outside_top4(tmp_path):
    """If the recovered stage2 winner slot is not in the recovered stage1 top4 (a cross-route or
    stale receipt), recovery fails closed rather than resolving to an unbound architecture."""
    run_dir, _plan = _write_real_a_e1_run(tmp_path)
    run_id = "G3-AE1-staged-exec-v1"
    stage1 = fe._ensure_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    fe._ensure_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, route="F2", score_fit=_smoke_score_fit(), stage1_by_route={"F2": stage1})
    bogus_top4 = {"selected_top_1": "zzz"}  # lacks the winner's actual slot
    with pytest.raises(ValueError, match="outside the recovered stage1 top4"):
        fe._recover_a_e1_stage2_selection(run_dir=run_dir, run_id=run_id, route="F2", top4=bogus_top4)


def test_ensure_final_selection_idempotent(tmp_path):
    """The final selection receipt is idempotent: once it exists, repeated ensure calls re-validate
    it read-only (reused=True, same trace sha) and never overwrite the artifacts."""
    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, trace_sha, _records = _publish_staged_run(tmp_path, specs, evaluations)
    before = (run_dir / "selection_receipt.json").read_bytes()
    first = fe._ensure_a_e1_final_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=None)
    second = fe._ensure_a_e1_final_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=None)
    assert first.get("reused") is True and second.get("reused") is True
    assert first["selection_trace_sha256"] == trace_sha == second["selection_trace_sha256"]
    assert (run_dir / "selection_receipt.json").read_bytes() == before  # unchanged


@pytest.mark.slow
def test_run_a_e1_staged_executes_real_fits_via_scheduler(tmp_path, monkeypatch):
    """Production-equivalent sealed smoke: run_a_e1_staged drives REAL fits through the scheduler
    journal on the frozen A-E1 matrix -- real training -> canonical checkpoint -> evidence (no
    monkeypatch of winner/trace/authority/provenance). A partial run (max_fits) proves the
    orchestrator integrates with claim/execute/record on real data and test stays sealed. The
    staged receipts + final trace require the full 349-fit run (formal-launch scope, deliberately
    out of this relay); the staged mechanism itself is covered by the per-route unit tests above.
    Requires a clean code/ tree for the scheduler authority check.
    """
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--", str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"

    def fast_fixed(model_factory, train_batch, val_batch, effective, *, seed, loss_id, lr, weight_decay, batch_size, optimizer_id="adamw"):
        # Real checkpoint + predictions from a 2-epoch warmup, synthetic 60-epoch trajectory so the
        # evidence satisfies the formal [min,max]-epochs contract without 50-100 real epochs.
        from study02a.training import FitResult
        warmup = fit_candidate(
            model_factory, (train_batch.features, train_batch.targets), (val_batch.features, val_batch.targets),
            seed=seed, max_epochs=2, min_epochs=1, patience=1,
            batch_size=min(int(batch_size), 64), loss_id=loss_id, lr=lr, weight_decay=weight_decay, optimizer_id=optimizer_id,
        )
        curve = tuple(100.0 / (i + 1) for i in range(60))
        best_epoch = min(range(60), key=lambda i: curve[i])
        return FitResult(
            predictions=warmup.predictions, checkpoint_sha256=warmup.checkpoint_sha256,
            checkpoint_bytes=warmup.checkpoint_bytes, best_validation_loss=warmup.best_validation_loss,
            actual_epochs=60, best_epoch=best_epoch, validation_loss_history=curve,
            early_stop_reason="patience_exhausted", hit_epoch_ceiling=False,
        )
    monkeypatch.setattr(fe, "fit_fixed_candidate", fast_fixed)

    summary = fe.run_a_e1_staged(
        study_root=STUDY_ROOT, run_id="staged-smoke-0001",
        artifact_root=tmp_path / "artifact", cache_root=tmp_path / "cache", max_fits=3)
    assert summary["succeeded_count"] == 3 and summary["failed_count"] == 0
    assert summary["complete"] is False  # partial run; receipts/final trace need the full run

    from study02a.formal_scheduler import status_run
    run_dir = tmp_path / "artifact" / "A-E1" / "staged-smoke-0001"
    stat = status_run(run_dir, cache_root=tmp_path / "cache")
    assert stat["test_access_count"] == 0
    assert stat["counts"]["succeeded"] == 3
    # the succeeded fits carry real bound checkpoints + evidence (no monkeypatch of authority)
    import hashlib as _hl, json as _json
    for fit_id in summary["succeeded"]:
        checkpoint = (run_dir / "outputs" / fit_id / "checkpoint.pt").read_bytes()
        binding = _json.loads((run_dir / "outputs" / fit_id / "fit_status.json").read_bytes())
        assert binding == {"checkpoint_sha256": _hl.sha256(checkpoint).hexdigest(),
                           "fit_id": fit_id, "run_id": "staged-smoke-0001", "status": "succeeded", "test_access_count": 0}


def _smoke_fit_runner(seen=None):
    """A fit_runner for run_a_e1_staged that bypasses the infeasible frozen data prep (100000-row
    datasets): trains a tiny real model on a tiny synthetic batch (real canonical checkpoint), then
    writes the production per-fit outputs (checkpoint.pt / fit_status.json / evidence.json via
    _write_outputs) and records the terminal through the PRODUCTION record_fit_succeeded. claim +
    record stay on the real scheduler path; only the training inputs are synthetic.

    If ``seen`` is a list, each fit's RESOLVED (architecture, optimizer, loss) is appended -- so the
    smoke can prove no placeholder (``selected_top_*`` / ``selected:A-E1_*``) ever reaches the runner."""
    import torch
    from study02a.training import fit_candidate, FitResult
    from study02a.models import build_mlp
    from study02a.formal_scheduler import record_fit_succeeded

    def runner(*, study_root, run_dir, cache_root, plan_row, claim, frozen, effective, timestamp):
        fit_id = str(claim["fit_id"])
        if seen is not None:
            seen.append({"fit_id": fit_id, "architecture": str(plan_row["architecture"]),
                         "optimizer": str(plan_row["optimizer"]), "loss": str(plan_row["loss"])})
        warmup = fit_candidate(
            lambda: build_mlp(15, [8], "relu", 0.0),
            (torch.randn(32, 15), torch.randn(32, 3)),
            (torch.randn(8, 15), torch.randn(8, 3)),
            seed=int(plan_row["seed"]) % 1000, max_epochs=2, min_epochs=1, patience=1, batch_size=16,
        )
        curve = tuple(100.0 / (i + 1) for i in range(60))
        best_epoch = min(range(60), key=lambda i: curve[i])
        evidence = {
            "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": fit_id,
            "run_id": str(plan_row["run_id"]), "checkpoint_sha256": warmup.checkpoint_sha256,
            "actual_epochs": 60, "best_epoch_one_based": best_epoch + 1, "hit_epoch_100": False,
            "early_stop_reason": "patience_exhausted", "terminal_validation_slope": fe._terminal_ols_slope(curve),
            "validation_curve": list(curve), "test_access_count": 0,
        }
        output_hashes = fe._write_outputs(
            run_dir, fit_id, str(plan_row["run_id"]), warmup.checkpoint_bytes,
            warmup.checkpoint_sha256, evidence)
        return {"state": "succeeded", "receipt": record_fit_succeeded(
            run_dir, cache_root=cache_root, fit_id=fit_id, owner_id=str(claim["owner_id"]),
            owner_nonce=str(claim["owner_nonce"]), output_hashes=output_hashes, timestamp=timestamp)}
    return runner


def _smoke_score_fit():
    """A score_fit covering the three selection fit kinds with deterministic synthetic evidence
    derived from the frozen plan row's runtime fields (no checkpoint forward, no data prep): stage1
    ranks m01<m02<...; stage2 forces distinct per-route winners (F2=selected_top_2:o2, V=selected_top_3:o3);
    winner-retrain uses route-aligned baseline records (F2 < V) so global_better_rule selects F2.

    ``fit_kind`` and ``n`` are NOT in plan.jsonl (the plan renames them; they live in the frozen
    matrix), so they are read from the authoritative matrix row looked up by ``fit_id`` -- the
    production ``score_fit(fit_id, plan_row)`` contract is unchanged and only the test side queries
    the matrix. The rest (route/architecture/optimizer/seed) come from the plan row."""
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)

    def score_fit(fit_id, plan_row):
        kind = str(matrix_by_fit[str(fit_id)]["fit_kind"]); route = str(plan_row["route"])
        if kind == "winner_retrain":
            return _baseline_score_fit(matrix_by_fit=matrix_by_fit)(fit_id, plan_row)
        n = int(matrix_by_fit[str(fit_id)]["n"])
        key = SupportKey(n=n, seed=int(plan_row["seed"]))
        if kind == "search_stage1":
            arch = str(plan_row["architecture"]); base = 0.01 * int(arch[1:])
            decision_id = f"architecture:A-E1:{route}:n{fe._A_E1_SEARCH_N}"; candidate_id = arch
        else:  # search_stage2
            candidate_id = f"{plan_row['architecture']}:{plan_row['optimizer']}"
            forced = {"F2": "selected_top_2:o2", "V": "selected_top_3:o3"}[route]
            base = 0.001 if candidate_id == forced else 0.5
            decision_id = f"stage2:A-E1:{route}:n{fe._A_E1_SEARCH_N}"
        records = _synth_point_records(fit_id, int(plan_row["seed"]), base)
        aggregate = sum(rec["l_param"] for rec in records) / len(records)
        return FitEvaluation(
            fit_id=fit_id, module_id="A-E1", decision_id=decision_id, candidate_id=candidate_id,
            support_key=key, failed=False, checkpoint_sha256=hashlib.sha256(fit_id.encode("utf-8")).hexdigest(),
            validation_identity=f"val-cache-{fit_id}", selection_score=aggregate,
            failure_penalty=0.0, point_records=records)
    return score_fit


@pytest.mark.slow
def test_post_selection_authority_rebuilds_with_relocated_point_evidence(tmp_path, monkeypatch):
    """Contract 2/8 (focused, fast): after build_module_selection publishes RELOCATED point_evidence
    (selection/point_evidence/{fit}.json), a full _rebuild_authority()/status_run() replays cleanly
    POST-SELECTION -- the point_evidence-vs-scheduler blocker is resolved because outputs/{fit_id}/
    stays exactly the frozen expected_outputs. Real scheduler (materialize+claim+record) with synthetic
    training; selection is published over the real run via score_fit injection. (The 349-fit
    test_staged_full_chain_smoke is the full-chain version of this same check.)"""
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--", str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"
    summary = fe.run_a_e1_staged(
        study_root=STUDY_ROOT, run_id="psel-0001",
        artifact_root=tmp_path / "artifact", cache_root=tmp_path / "cache",
        fit_runner=_smoke_fit_runner(), score_fit=_smoke_score_fit(), max_fits=5)
    assert summary["succeeded_count"] == 5 and summary["complete"] is False  # partial run; no selection yet
    run_dir = tmp_path / "artifact" / "A-E1" / "psel-0001"
    # publish selection over the REAL scheduler run -> RELOCATED point_evidence (the 144 candidates)
    fe.build_module_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        module_id="A-E1", run_id="psel-0001", score_fit=_smoke_score_fit())
    _search_count = sum(1 for r in MATRIX_ROWS
                        if str(r["module"]) == "A-E1" and str(r["fit_kind"]) in ("search_stage1", "search_stage2"))
    pe_dir = run_dir / "selection" / "point_evidence"
    assert pe_dir.is_dir() and len(list(pe_dir.iterdir())) == _search_count
    # outputs/{fit_id}/ for every recorded fit holds NO point_evidence (relocated out of the authority dir)
    assert not any((run_dir / "outputs" / fid).joinpath("point_evidence.json").exists()
                   for fid in summary["succeeded"])
    # the REAL post-selection authority replay succeeds and test stayed sealed throughout
    from study02a.formal_scheduler import status_run, _rebuild_authority
    stat = status_run(run_dir, cache_root=tmp_path / "cache")
    assert stat["test_access_count"] == 0
    _, _, auth_state, events = _rebuild_authority(run_dir, tmp_path / "cache")
    assert auth_state["test_access_count"] == 0
    assert all(event["test_access_count"] == 0 for event in events)


@pytest.mark.slow
def test_staged_full_chain_smoke(tmp_path, monkeypatch):
    """Full-chain production-equivalent sealed smoke: run_a_e1_staged drives the REAL staged
    control end-to-end on the frozen A-E1 matrix -- stage1 execute+select -> top4 -> stage2
    concretize+execute+select -> winner-retrain -> F2/V decision -> final receipt + staged
    ledger. Only the DATA is synthetic (small, via cache_dataset; the frozen 100000-row prep is
    infeasible in a test); training, checkpoint-forward selection scoring, claim/record/receipt
    are all the real production path. No monkeypatch of top4/winner/stage-state. test sealed.

    Requires a clean code/ tree for the scheduler authority check.
    """
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--", str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"

    import time
    telemetry = {"rebuild_samples": [], "stage_times": {}, "rebuild_calls": 0}
    _real_rebuild = fe._rebuild_authority

    def _timed_rebuild(run_dir, cache_root, **kw):
        telemetry["rebuild_calls"] += 1
        t0 = time.time(); result = _real_rebuild(run_dir, cache_root, **kw); dt = time.time() - t0
        n = telemetry["rebuild_calls"]
        if n in (1, 50, 200, 500, 1000, 1396) or n % 250 == 0:
            telemetry["rebuild_samples"].append({"call": n, "seconds": round(dt, 3)})
        return result
    monkeypatch.setattr(fe, "_rebuild_authority", _timed_rebuild)
    _real_s1 = fe.build_a_e1_stage1_selection

    def _timed_s1(*a, **kw):
        t0 = time.time(); r = _real_s1(*a, **kw)
        telemetry["stage_times"][f"stage1_{kw['route']}"] = round(time.time() - t0, 2)
        return r
    monkeypatch.setattr(fe, "build_a_e1_stage1_selection", _timed_s1)
    _real_s2 = fe.build_a_e1_stage2_selection

    def _timed_s2(*a, **kw):
        t0 = time.time(); r = _real_s2(*a, **kw)
        telemetry["stage_times"][f"stage2_{kw['route']}"] = round(time.time() - t0, 2)
        return r
    monkeypatch.setattr(fe, "build_a_e1_stage2_selection", _timed_s2)

    _t0 = time.time()
    seen_by_runner: list[dict] = []  # resolved (architecture/optimizer/loss) the runner actually received
    summary = fe.run_a_e1_staged(
        study_root=STUDY_ROOT, run_id="sfsm-0001",
        artifact_root=tmp_path / "artifact", cache_root=tmp_path / "cache",
        fit_runner=_smoke_fit_runner(seen=seen_by_runner), score_fit=_smoke_score_fit())
    telemetry["total_seconds"] = round(time.time() - _t0, 1)
    run_dir = tmp_path / "artifact" / "A-E1" / "sfsm-0001"

    # full chain completed: every staged fit terminal
    assert summary["complete"] is True
    assert summary["succeeded_count"] == 349 and summary["failed_count"] == 0
    # NO placeholder ever reached the runner: every resolved architecture/optimizer/loss is concrete
    # (no selected_top_* / selected:A-E1_*), proving stage2/winner rows were concretized from receipts
    placeholder_arches = [s for s in seen_by_runner
                          if str(s["architecture"]).startswith(("selected_top_", "selected:"))
                          or str(s["optimizer"]).startswith("selected:")
                          or str(s["loss"]).startswith("selected:")]
    assert not placeholder_arches, f"placeholder reached the runner: {placeholder_arches[:3]}"
    telemetry["runner_saw_fits"] = len(seen_by_runner)
    # per-route stage receipts published at the right stages (immutable, on the real selection path)
    for route in ("F2", "V"):
        assert (run_dir / f"stage1_selection_{route}_receipt.json").is_file()
        assert (run_dir / f"stage2_selection_{route}_receipt.json").is_file()
        # stage1 precedes stage2 (each route's stage2 winner is bound to its stage1 top4)
        assert ((run_dir / f"stage1_selection_{route}_receipt.json").stat().st_mtime_ns
                <= (run_dir / f"stage2_selection_{route}_receipt.json").stat().st_mtime_ns)
    # final module selection trace + staged resolution (F2/V decision + final aliases)
    assert (run_dir / "selection_trace.jsonl").is_file()
    assert (run_dir / "selection_receipt.json").is_file()
    staged = summary["staged"]
    assert staged is not None
    assert staged["selected_F2_or_V"] in ("F2", "V")
    assert staged["final_aliases"] is not None
    assert set(staged["final_aliases"]) == {
        "selected:A-E1_loss", "selected:A-E1_architecture", "selected:A-E1_optimizer"}
    assert staged["final_aliases"] == staged["stage2_by_route"][staged["selected_F2_or_V"]]
    assert (run_dir / "staged_resolution_ledger.jsonl").is_file()
    # the staged ledger is a hash-bound chain (stage1 -> stage2 -> winner_retrain -> baseline -> final)
    _assert_chained_ledger(run_dir)
    # Contract 2/8: the REAL post-selection sealed-status check. point_evidence was relocated out of
    # outputs/{fit_id}/ (to selection/point_evidence/{fit}.json), so a full _rebuild_authority() /
    # status_run() AFTER selection replays cleanly (the scheduler-authority fit dirs stay exactly the
    # frozen expected_outputs -- no extra point_evidence.json) and confirms test stayed sealed. This
    # is no longer a scheduler_state.json read workaround; it exercises the real authority replay.
    from study02a.formal_scheduler import status_run, _rebuild_authority
    stat = status_run(run_dir, cache_root=tmp_path / "cache")
    assert stat["test_access_count"] == 0
    _manifest, _plan, _authority_state, _events = _rebuild_authority(run_dir, tmp_path / "cache")
    assert _authority_state["test_access_count"] == 0
    assert all(event["test_access_count"] == 0 for event in _events)
    # contract 1: outputs/{fit_id}/ holds NO point_evidence (relocated); the selection dir holds the
    # frozen selection candidates (search_stage1 + search_stage2 = 144), never the fit output dir.
    assert not any((run_dir / "outputs" / fid).joinpath("point_evidence.json").exists()
                   for fid in _authority_state["fit_states"])
    pe_dir = run_dir / "selection" / "point_evidence"
    _search_count = sum(1 for r in MATRIX_ROWS
                        if str(r["module"]) == "A-E1" and str(r["fit_kind"]) in ("search_stage1", "search_stage2"))
    assert pe_dir.is_dir() and all(p.suffix == ".json" for p in pe_dir.iterdir())
    assert len(list(pe_dir.iterdir())) == _search_count
    telemetry["fit_count"] = summary["succeeded_count"]
    telemetry["event_count"] = len(_events)
    telemetry["test_access_count"] = _authority_state["test_access_count"]
    telemetry["selected_F2_or_V"] = staged["selected_F2_or_V"]
    print("SLOW_SMOKE_TELEMETRY " + json.dumps(telemetry))


def test_consecutive_failure_guard_raises_at_eight():
    """7 failures return incremented count; 8th raises RuntimeError."""
    counter = 0
    for _ in range(7):
        counter = fe._advance_consecutive_failures(counter, "dead", "test")
    assert counter == 7
    with pytest.raises(RuntimeError, match="8 consecutive scientific failures"):
        fe._advance_consecutive_failures(counter, "dead", "test")


def test_consecutive_failure_guard_counter_resets_on_success():
    """Caller resets counter to 0 on success; helper only increments on failure."""
    counter = 0
    for _ in range(3):
        counter = fe._advance_consecutive_failures(counter, "dead", "test")
    assert counter == 3
    counter = 0  # caller's success reset
    for _ in range(5):
        counter = fe._advance_consecutive_failures(counter, "dead", "test")
    assert counter == 5


def test_consecutive_failure_guard_respects_custom_label_and_threshold():
    """Helper supports custom label and max_failures."""
    with pytest.raises(RuntimeError, match="custom label aborted: 3 consecutive"):
        fe._advance_consecutive_failures(2, "err", "msg", max_failures=3, label="custom label")


# ---------------------------------------------------------------------------
# R5: Production checkpoint scoring regression (no score_fit mock).
# Exercises the REAL validation_failure_penalized_l_param_points path that
# crashed in A-E1-formal-r2 with 'FormalDataset has no attribute location'.
# ---------------------------------------------------------------------------


def _real_checkpoint_and_validation(tmp_path, route, distribution, n_mode, fixed_n, architecture, is_set):
    """Build real small datasets, train a real checkpoint, return (fit, scaled_validation, validation_dataset)."""
    from study02a.formal_runner import (
        _build_training_spec_for_tests, _build_validation_spec_for_tests,
        _cache_dataset_for_tests, _pilot_for_tests,
        fit_training_scaler, apply_training_scaler,
    )
    from study02a.training import fit_fixed_candidate, fit_set_candidate

    pilot = _pilot_for_tests(rows=20, points=4, repeats=2)
    training_spec = _build_training_spec_for_tests(
        route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
        training_rows=7000, frozen_config=FROZEN, effective_config=EFFECTIVE, pilot=pilot,
    )
    validation_spec = _build_validation_spec_for_tests(
        route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
        frozen_config=FROZEN, effective_config=EFFECTIVE, pilot=pilot,
    )
    cache_root = tmp_path / "cache"
    training_dataset = _cache_dataset_for_tests(training_spec, FROZEN, EFFECTIVE, cache_root)
    validation_dataset = _cache_dataset_for_tests(validation_spec, FROZEN, EFFECTIVE, cache_root)
    scaler = fit_training_scaler(training_dataset, FROZEN, EFFECTIVE)
    scaled_training = apply_training_scaler(training_dataset, scaler, training_dataset, FROZEN, EFFECTIVE)
    scaled_validation = apply_training_scaler(validation_dataset, scaler, training_dataset, FROZEN, EFFECTIVE)

    input_dim = None if is_set else int(scaled_training.batch.features.shape[1])
    model_factory = fe.resolve_model_factory(architecture, FROZEN, input_dim)
    hyperparams = fe.resolve_optimizer_hyperparams("stage1", FROZEN)

    if is_set:
        fit = fit_set_candidate(
            model_factory, scaled_training.batch, scaled_validation.batch, EFFECTIVE,
            seed=420001, loss_id="transformed_train_z_huber", lr=hyperparams["lr"],
            weight_decay=hyperparams["weight_decay"], batch_size=hyperparams["batch_size"],
            optimizer_id=str(hyperparams["optimizer"]),
        )
    else:
        fit = fit_fixed_candidate(
            model_factory, scaled_training.batch, scaled_validation.batch, EFFECTIVE,
            seed=420001, loss_id="transformed_train_z_huber", lr=hyperparams["lr"],
            weight_decay=hyperparams["weight_decay"], batch_size=hyperparams["batch_size"],
            optimizer_id=str(hyperparams["optimizer"]),
        )
    return fit, scaled_training, scaled_validation, validation_dataset, model_factory


def test_production_checkpoint_scoring_fixed_batch(tmp_path):
    """R5 regression: real checkpoint scoring via validation_failure_penalized_l_param_points
    with a fixed-batch route. On old code (passing FormalDataset instead of .batch) this raises:
    AttributeError: 'FormalDataset' object has no attribute 'location'."""
    fit, scaled_training, scaled_validation, validation_dataset, model_factory = (
        _real_checkpoint_and_validation(
            tmp_path, route="F0eq_hsm", distribution="core_continuous",
            n_mode="fixed_n", fixed_n=15, architecture="m05", is_set=False,
        )
    )
    from study02a.formal_runner import FormalDataset
    assert isinstance(scaled_validation, FormalDataset)
    scalar, point_records = fe.validation_failure_penalized_l_param_points(
        checkpoint_bytes=fit.checkpoint_bytes, model_factory=model_factory,
        validation_batch=scaled_validation.batch,
        validation_metadata=tuple(validation_dataset.metadata),
        seed_id="420001", is_set=False,
    )
    assert len(point_records) == len(validation_dataset.metadata)
    expected_scalar = sum(r["l_param"] for r in point_records) / len(point_records)
    assert scalar == pytest.approx(expected_scalar)
    assert fit.checkpoint_sha256 == hashlib.sha256(fit.checkpoint_bytes).hexdigest()


def test_production_checkpoint_scoring_set_batch(tmp_path):
    """R5 regression: real checkpoint scoring with a set-batch (S route) checkpoint."""
    fit, scaled_training, scaled_validation, validation_dataset, model_factory = (
        _real_checkpoint_and_validation(
            tmp_path, route="S", distribution="core_continuous",
            n_mode="shared_n", fixed_n=None, architecture="d01", is_set=True,
        )
    )
    scalar, point_records = fe.validation_failure_penalized_l_param_points(
        checkpoint_bytes=fit.checkpoint_bytes, model_factory=model_factory,
        validation_batch=scaled_validation.batch,
        validation_metadata=tuple(validation_dataset.metadata),
        seed_id="420001", is_set=True,
    )
    assert len(point_records) == len(validation_dataset.metadata)
    expected_scalar = sum(r["l_param"] for r in point_records) / len(point_records)
    assert scalar == pytest.approx(expected_scalar)


def test_production_checkpoint_scoring_old_code_raises_attribute_error(tmp_path):
    """R5: prove the old bug — passing FormalDataset (not .batch) to
    validation_failure_penalized_l_param_points raises AttributeError."""
    fit, scaled_training, scaled_validation, validation_dataset, model_factory = (
        _real_checkpoint_and_validation(
            tmp_path, route="F0eq_hsm", distribution="core_continuous",
            n_mode="fixed_n", fixed_n=15, architecture="m05", is_set=False,
        )
    )
    from study02a.formal_runner import FormalDataset
    assert isinstance(scaled_validation, FormalDataset)
    with pytest.raises(AttributeError, match="location"):
        fe.validation_failure_penalized_l_param_points(
            checkpoint_bytes=fit.checkpoint_bytes, model_factory=model_factory,
            validation_batch=scaled_validation,
            validation_metadata=tuple(validation_dataset.metadata),
            seed_id="420001", is_set=False,
        )


def test_score_fit_from_checkpoint_production_path(tmp_path, monkeypatch):
    """R5: _score_fit_from_checkpoint end-to-end with real checkpoint scoring.
    Monkeypatches _prepare_fit_inputs (NOT score_fit) to supply small test datasets."""
    fit, scaled_training, scaled_validation, validation_dataset, model_factory = (
        _real_checkpoint_and_validation(
            tmp_path, route="F0eq_hsm", distribution="core_continuous",
            n_mode="fixed_n", fixed_n=15, architecture="m05", is_set=False,
        )
    )
    hyperparams = fe.resolve_optimizer_hyperparams("stage1", FROZEN)
    prepared = fe._PreparedFit(
        scaled_training=scaled_training, scaled_validation=scaled_validation,
        validation_metadata=tuple(validation_dataset.metadata),
        validation_identity=validation_dataset.dataset_hash,
        model_factory=model_factory, hyperparams=hyperparams,
        loss_id="transformed_train_z_huber", is_set=False,
    )
    monkeypatch.setattr(fe, "_prepare_fit_inputs", lambda *a, **kw: prepared)

    run_dir = tmp_path / "run"
    fit_id = "G3-fit-test"
    out_dir = run_dir / "outputs" / fit_id
    out_dir.mkdir(parents=True)
    (out_dir / "checkpoint.pt").write_bytes(fit.checkpoint_bytes)

    plan_row = _plan_row(fit_id=fit_id, seed=420001)
    result = fe._score_fit_from_checkpoint(
        run_dir=run_dir, cache_root=tmp_path / "cache", plan_row=plan_row, fit_id=fit_id,
        frozen=FROZEN, effective=EFFECTIVE,
        fit_states={fit_id: "succeeded"},
        module_id="A-E1", decision_id="d1", candidate_id="c1",
    )
    assert isinstance(result, FitEvaluation)
    assert result.failed is False
    assert result.checkpoint_sha256 == hashlib.sha256(fit.checkpoint_bytes).hexdigest()
    assert result.validation_identity == validation_dataset.dataset_hash
    assert len(result.point_records) == len(validation_dataset.metadata)
    expected_scalar = sum(r["l_param"] for r in result.point_records) / len(result.point_records)
    assert result.selection_score == pytest.approx(expected_scalar)


def test_prepared_fit_type_contract(tmp_path):
    """R5: _PreparedFit.scaled_training and scaled_validation are FormalDataset;
    the scorer must consume .batch, not the dataset wrapper."""
    from study02a.formal_runner import FormalDataset
    fit, scaled_training, scaled_validation, validation_dataset, model_factory = (
        _real_checkpoint_and_validation(
            tmp_path, route="F0eq_hsm", distribution="core_continuous",
            n_mode="fixed_n", fixed_n=15, architecture="m05", is_set=False,
        )
    )
    hyperparams = fe.resolve_optimizer_hyperparams("stage1", FROZEN)
    prepared = fe._PreparedFit(
        scaled_training=scaled_training, scaled_validation=scaled_validation,
        validation_metadata=tuple(validation_dataset.metadata),
        validation_identity=validation_dataset.dataset_hash,
        model_factory=model_factory, hyperparams=hyperparams,
        loss_id="transformed_train_z_huber", is_set=False,
    )
    assert isinstance(prepared.scaled_training, FormalDataset)
    assert isinstance(prepared.scaled_validation, FormalDataset)
    assert hasattr(prepared.scaled_validation.batch, "location")
    assert hasattr(prepared.scaled_validation.batch, "targets")
