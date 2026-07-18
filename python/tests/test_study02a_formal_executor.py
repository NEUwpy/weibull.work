"""Tests for the Study/02 formal execution driver (Task 9c.3)."""

from __future__ import annotations

import hashlib
import json
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


def _baseline_score_fit(*, f2: float = 0.10, v: float = 0.20):
    """score_fit for the F2/V winner-retrain baseline; F2 < V on every paired point so F2 is
    globally better under the frozen relative-RMSE rule."""
    def score_fit(fit_id, plan_row):
        route = str(plan_row["route"])
        n = int(plan_row["n"]); seed = int(plan_row["seed"])
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


def test_build_module_selection_wires_staged_resolution(tmp_path, monkeypatch):
    """Production call point: build_module_selection derives the staged A-E1 ledger from its own
    published trace once every staged decision is present, and returns it under 'staged'.

    score_fit stands in for checkpoint scoring (no training, no materialize); the staged
    sub-call's production winner-retrain scoring is stubbed to a pending run state (no
    checkpoints read), proving the wiring fires, resolves stage1/stage2, and reports the
    downstream baseline as pending without raising."""
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

    def score_fit(fit_id, plan_row):
        return evaluations[fit_id]  # pre-built stage1/stage2 evaluation

    receipt = fe.build_module_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        module_id="A-E1", run_id=_STAGED_RUN_ID, score_fit=score_fit)
    assert receipt["staged"] is not None
    assert receipt["staged"]["selection_trace_sha256"] == receipt["selection_trace_sha256"]
    # winner-retrain not executed (stubbed pending) -> baseline/final pending, stages resolved
    assert "baseline_input" in receipt["staged"]["pending"]
    assert "final_aliases" in receipt["staged"]["pending"]
    for route in ("F2", "V"):
        top4 = receipt["staged"]["top4_by_route"][route]
        assert set(top4) == {"selected_top_1", "selected_top_2", "selected_top_3", "selected_top_4"}
        assert top4["selected_top_1"] == "m01"  # stage1 ranking derived from the trace
        s2 = receipt["staged"]["stage2_by_route"][route]
        assert s2["selected:A-E1_loss"] == "transformed_train_z_huber"
    assert (run_dir / "staged_resolution_ledger.jsonl").is_file()


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
        "bundle_version": "study02-pre-unseal-v1",
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


def test_formal_accredit_authorize_requires_external_approval_then_stops(tmp_path):
    """The authorize CLI binds an EXTERNAL oracle approval, transitions sealed -> unsealed_once,
    and stops: consume_test_once is not exposed on the CLI surface (test is never read)."""
    import run_study02a
    run_dir = tmp_path / "A-E1" / _ACCCR_RUN_ID
    bundle_path, ceiling, leakage, oracle, trace_sha = _accredit_bundle_inputs(run_dir)
    approval_path = run_dir / "approval.json"
    _publish_accredit_approval(approval_path, bundle_path, ceiling, leakage, oracle, trace_sha)
    state = run_study02a.accredit_authorize(
        module="A-E1", run_id=_ACCCR_RUN_ID, artifact_root=tmp_path,
        approval_path=approval_path, oracle_review_path=oracle, run_family_id="G3-formal",
        timestamp="2026-07-19T11:00:00+08:00")
    assert state["state"] == "unsealed_once"
    assert state["transition_seq"] == 1
    assert state["test_access_count"] == 1
    assert state["approval_sha256"] == hashlib.sha256(approval_path.read_bytes()).hexdigest()
    # consume is deliberately not wired into the CLI
    assert not hasattr(run_study02a, "consume_test")
    # repeat authorize fails closed (state is no longer sealed)
    import pytest as _pt
    with _pt.raises(Exception):
        run_study02a.accredit_authorize(
            module="A-E1", run_id=_ACCCR_RUN_ID, artifact_root=tmp_path,
            approval_path=approval_path, oracle_review_path=oracle, run_family_id="G3-formal",
            timestamp="2026-07-19T11:30:00+08:00")


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
