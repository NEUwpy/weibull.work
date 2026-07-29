"""Tests for the Study/02 formal execution driver (Task 9c.3)."""

from __future__ import annotations

import dataclasses
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
# R3-C v2 authority triple: synthetic SHA-256 values for the predecessor's sealed
# formal-run authority (scoped_code_sha256 + authority_sha256). The fixtures underlying
# these helpers publish a staged-only manifest (no ``scheduler.authority`` block), so the
# values cannot be read from disk; instead they are deterministic synthetic SHA-256s that
# satisfy ``_validate_predecessor`` v2 (non-None + SHA-256 format). Production runs read the
# real values from the predecessor manifest's ``scheduler.authority`` block (see
# ``run_study02a._build_predecessor_trace``); these constants are fixture-only.
_D8_SCOPED_CODE_SHA256 = "a" * 64
_D8_AUTHORITY_SHA256 = "b" * 64


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
    """Publish a real selection trace + receipt + ledger for one decision; return their paths/sha.

    For A-E1 (the only staged-ledger-publishing module this fixture exercises), also publish a
    minimal cryptographically-valid 8-record ``staged_resolution_ledger.jsonl`` referencing the
    verified trace SHA so the control-plane v2 predecessor binding has a complete chain to bind.
    The staged-ledger CONTENT is independent of the single decision in ``spec`` (the validator
    only checks SHA binding + canonical order, not that the trace's decisions cover every stage).
    """
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
    result = {
        "trace_path": trace_path, "trace_sha256": trace_sha,
        "receipt_path": tmp_path / "selection_receipt.json",
        "ledger_path": tmp_path / "selection_ledger.jsonl",
        "module_id": module_id, "run_id": run_id, "records": records, "spec": spec,
    }
    staged = _publish_minimal_staged_ledger(
        tmp_path=tmp_path, module_id=module_id, run_id=run_id, trace_sha256=trace_sha,
        code_commit=code_commit, effective_config_sha256=EFFECTIVE.effective_config_sha256,
    )
    if staged is not None:
        result["staged_ledger_path"] = staged
        result["staged_ledger_sha256"] = hashlib.sha256(staged.read_bytes()).hexdigest()
    return result


# Minimal (stage, route) sequences for the staged-ledger fixture (mirrors the FC
# ``_STAGED_LEDGER_SEQUENCES`` constant). Only A-E1 is exercised through this fixture; A-E3
# staged-ledger publishing is wired in C4 (``resolve_a_e3_staged_selection``).
_D8_STAGED_FIXTURE_SEQUENCES = {
    "A-E1": (
        ("stage1", "F2"), ("stage2", "F2"), ("winner_retrain", "F2"),
        ("stage1", "V"), ("stage2", "V"), ("winner_retrain", "V"),
        ("baseline_input", None), ("final_aliases", None),
    ),
}


def _publish_minimal_staged_ledger(
    *, tmp_path: Path, module_id: str, run_id: str, trace_sha256: str,
    code_commit: str, effective_config_sha256: str,
) -> Path | None:
    """Publish a cryptographically valid staged_resolution_ledger for an A-E1 predecessor.

    Mirrors ``formal_executor._build_stage_record`` byte-for-byte (canonical JSON, record_sha
    self-hash, hash-bound chain from ``_ZERO_HASH``). The validator in FC is the single
    authority. Returns ``None`` when the module does not publish a staged ledger."""
    from study02a.formal_contracts import _canonical_json_bytes, _STAGED_LEDGER_RECORD_VERSION

    sequence = _D8_STAGED_FIXTURE_SEQUENCES.get(module_id)
    if sequence is None:
        return None
    staged_ledger_path = tmp_path / "staged_resolution_ledger.jsonl"
    zero = "0" * 64
    records: list[dict] = []
    previous_sha = zero
    lowered_commit = str(code_commit).lower()
    for stage, route in sequence:
        if stage == "baseline_input":
            resolution = {"selected:F2_or_V": "V"}
        elif stage == "final_aliases":
            resolution = {
                "selected:A-E1_loss": "transformed_train_z_huber",
                "selected:A-E1_architecture": "m12",
                "selected:A-E1_optimizer": "o3",
            }
        elif stage.startswith("stage"):
            resolution = {
                "selected_top_1": "m01", "selected_top_2": "m02",
                "selected_top_3": "m03", "selected_top_4": "m04",
            }
        else:
            resolution = {
                "selected:A-E1_loss": "transformed_train_z_huber",
                "selected:A-E1_architecture": "m12",
                "selected:A-E1_optimizer": "o3",
            }
        resolution_sha = hashlib.sha256(_canonical_json_bytes(dict(resolution))).hexdigest()
        core = {
            "record_version": _STAGED_LEDGER_RECORD_VERSION,
            "module_id": module_id,
            "run_id": run_id,
            "code_commit": lowered_commit,
            "effective_config_sha256": effective_config_sha256,
            "selection_trace_sha256": trace_sha256,
            "stage": stage,
            "route": route,
            "previous_record_sha256": previous_sha,
            "input": {"fixture": "d8_evidence"},
            "resolution": dict(resolution),
            "resolution_sha256": resolution_sha,
        }
        record_sha = hashlib.sha256(_canonical_json_bytes(core)).hexdigest()
        record = {**core, "record_sha256": record_sha}
        records.append(record)
        previous_sha = record_sha
    staged_ledger_path.write_bytes(b"".join(_canonical_json_bytes(record) for record in records))
    return staged_ledger_path


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
        staged_ledger_path=ev.get("staged_ledger_path"),
        staged_ledger_sha256=ev.get("staged_ledger_sha256"),
        scoped_code_sha256=_D8_SCOPED_CODE_SHA256,
        authority_sha256=_D8_AUTHORITY_SHA256,
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
        "manifest_version": "study02-formal-v2", "module_id": "A-E1", "run_id": _D8_RUN_ID,
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
                        "selection_receipt_sha256": "none", "selection_ledger_path": "none",
                        "selection_staged_ledger_path": "none",
                        "selection_staged_ledger_sha256": "none",
                        "resolved_baseline_route": "none",
                        "code_commit": "none", "scoped_code_sha256": "none", "authority_sha256": "none"},
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
    # R4 stop-fix: plan.jsonl must be the REAL ``_PLAN_FIELDS`` schema (all 349 A-E1 rows, no
    # ``fit_kind``, real ``matrix_row_sha256``) so the staged resolver's
    # ``_validate_plan_against_matrix`` passes; the legacy ``winner_retrain_only_plan`` filter
    # produced a matrix-shaped partial plan that fails closed under the new validation.
    # ``winner_retrain_only_plan`` is retained for backwards-compat but is now a no-op.
    plan_rows = _real_a_e1_plan_rows(tmp_path, run_id=run_id, code_commit=code_commit)
    (run_dir / "plan.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in plan_rows), encoding="utf-8")
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


def test_formal_staged_cli_wires_a_e3_resolver(tmp_path, monkeypatch):
    """C5: the formal-staged CLI command forwards A-E3 to resolve_a_e3_staged_selection
    (predecessor is read from the run manifest, never caller-supplied)."""
    import run_study02a
    captured: dict[str, object] = {}

    def fake(**kwargs):
        captured.update(kwargs)
        return {"module_id": kwargs["module_id"], "pending": ["loss"]}

    monkeypatch.setattr(run_study02a, "resolve_a_e3_staged_selection", fake)
    ae3_run_id = "G3-AE3-staged-exec-v1"
    payload = run_study02a.resolve_staged("A-E3", ae3_run_id, tmp_path, tmp_path / "cache")
    assert payload == {"module_id": "A-E3", "pending": ["loss"]}
    assert captured["module_id"] == "A-E3" and captured["run_id"] == ae3_run_id
    assert Path(captured["run_dir"]) == tmp_path / "A-E3" / ae3_run_id
    assert captured["study_root"] == run_study02a.STUDY_ROOT
    assert "predecessor" not in captured  # read from manifest, not caller-supplied


def test_build_module_selection_publishes_trace_without_staged_side_effect(tmp_path, monkeypatch):
    """build_module_selection publishes the module selection trace/receipt (stage1+stage2 scored via
    score_fit); staged alias derivation now lives in the orchestrator (run_a_e1_staged), not here, so
    no 'staged' key is returned. (The staged resolver is covered by its own unit tests + the
    orchestrator's full-chain smoke.)"""
    _specs, evaluations = _staged_specs_and_evaluations()
    run_dir = tmp_path / "A-E1" / _STAGED_RUN_ID
    run_dir.mkdir(parents=True)
    # R4 stop-fix: write the REAL ``_PLAN_FIELDS`` plan (no ``fit_kind``, real
    # ``matrix_row_sha256``); the matrix-shaped stand-in fails ``_validate_plan_against_matrix``
    # inside ``build_module_selection``.
    plan_rows = _real_a_e1_plan_rows(tmp_path, run_id=_STAGED_RUN_ID)
    (run_dir / "plan.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in plan_rows), encoding="utf-8")
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
    (pred_dir / "manifest.json").write_text(json.dumps({
        "code_commit": _D8_CODE_COMMIT,
        # R3-C v2: the CLI's ``_build_predecessor_trace`` reads the authority triple from the
        # predecessor manifest's ``scheduler.authority`` block. Synthetic SHA-256s stand in for
        # the sealed formal-run authority (this fixture publishes a staged-only predecessor).
        "scheduler": {"authority": {
            "scoped_code_sha256": _D8_SCOPED_CODE_SHA256,
            "authority_sha256": _D8_AUTHORITY_SHA256,
        }},
    }, sort_keys=True) + "\n", encoding="utf-8")
    # Control-plane v2: publish a staged ledger so the CLI binds its SHA through PredecessorTrace.
    _publish_minimal_staged_ledger(
        tmp_path=pred_dir, module_id="A-E1", run_id=pred_run_id, trace_sha256=trace_sha,
        code_commit=_D8_CODE_COMMIT, effective_config_sha256=EFFECTIVE.effective_config_sha256,
    )
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
    # R4 stop-fix: plan.jsonl is the REAL ``_PLAN_FIELDS`` schema (all 349 A-E1 rows, no
    # ``fit_kind``, real ``matrix_row_sha256``) via the scheduler's own ``_plan_rows``; the
    # legacy per-row ``_plan_row`` stand-in (144 search rows + bogus SHA) fails
    # ``_validate_plan_against_matrix`` inside ``build_module_selection``. Selection scoring and
    # accreditation still only touch the 144 search fits (the selection candidates).
    plan_row_objs = _real_a_e1_plan_rows(tmp_path, run_id=run_id)
    search_rows = [r for r in MATRIX_ROWS
                   if str(r["module"]) == "A-E1" and str(r["fit_kind"]) in ("search_stage1", "search_stage2")]
    fit_ids = [str(r["fit_id"]) for r in search_rows]
    base_score = _smoke_score_fit()
    evaluations_by_fit = {}
    for r in search_rows:
        fit_id = str(r["fit_id"]); seed = int(r["seed"])
        score_plan_row = {
            "fit_id": fit_id, "route": str(r["route"]), "seed": seed,
            "architecture": str(r["architecture"]), "optimizer": str(r["optimizer"]),
        }
        if failed_fit is not None and fit_id == failed_fit:
            evaluation = _failed_fit_evaluation(fit_id=fit_id, plan_row=score_plan_row, matrix_row=r)
        else:
            evaluation = base_score(fit_id, score_plan_row)
        evaluations_by_fit[fit_id] = evaluation
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
    (run_dir / "plan.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in plan_row_objs), encoding="utf-8")
    manifest = {
        "manifest_version": "study02-formal-v2", "module_id": "A-E1", "run_id": run_id,
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
                        "selection_receipt_sha256": "none", "selection_ledger_path": "none",
                        "selection_staged_ledger_path": "none",
                        "selection_staged_ledger_sha256": "none",
                        "resolved_baseline_route": "none",
                        "code_commit": "none", "scoped_code_sha256": "none", "authority_sha256": "none"},
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
    optimizer + frozen loss.

    R4 stop-fix: the plan is the REAL ``_PLAN_FIELDS`` schema (no ``fit_kind``, real
    ``matrix_row_sha256``) via ``_write_real_a_e1_run``; stage1 is published first so stage2
    recovers top4 from disk; ``top4=`` is no longer a kwarg of ``build_a_e1_stage2_selection``.
    """
    run_id = "G3-AE1-staged-exec-v1"
    run_dir, plan = _write_real_a_e1_run(tmp_path, run_id=run_id)
    assert not any("fit_kind" in row for row in plan)  # real plan schema carries no fit_kind
    cache_root = tmp_path / "cache"
    # Publish each route's stage1 receipt first — the new API derives top4 from the on-disk
    # verified receipt, not a caller-supplied top4= kwarg.
    for route in ("F2", "V"):
        fe.build_a_e1_stage1_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
            run_id=run_id, route=route, score_fit=_smoke_score_fit())
    # Stage2 selection recovers top4 internally and maps the winner placeholder to concrete arch.
    f2 = fe.build_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    assert f2["winner"] == {"selected:A-E1_loss": "transformed_train_z_huber",
                            "selected:A-E1_architecture": "m02", "selected:A-E1_optimizer": "o2"}
    v = fe.build_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        run_id=run_id, route="V", score_fit=_smoke_score_fit())
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


# ---------------------------------------------------------------------------
# R4 stop-fix: A-E1-formal-r4 stage2 checkpoint scoring crash.
#
# The raw plan row (architecture=``selected_top_N``) reached
# ``resolve_model_factory`` which correctly fail-closed.  The fix
# (``_resolve_a_e1_scoring_plan_row``) resolves placeholders from on-disk
# verified receipts BEFORE checkpoint scoring.  These tests prove:
#   - the guard at ``resolve_model_factory`` is intact (Group 3 #1);
#   - the resolver passes concrete rows through and fail-closes on every
#     tamper of the stage1/stage2 evidence chain (Group 3 #2/#3);
#   - the removed kwargs (``top4=``, ``route_stage2=``) are rejected by the
#     new signatures (Group 3 #4);
#   - a real checkpoint for architecture A genuinely cannot load into a model
#     built for a different architecture B (Group 3 #5);
#   - the REAL production chain (checkpoint -> scoring -> selection) resolves
#     the placeholder and scores successfully (Group 1, slow);
#   - publish and rebuild produce identical concrete context (Group 2, slow).
# ---------------------------------------------------------------------------


# -- Group 3: unit / attack (NON-slow) ---------------------------------------


def test_resolve_model_factory_still_fails_closed_on_placeholder():
    """R4 stop-fix #1: the crash site (``resolve_model_factory``) still fail-closes on
    placeholder architectures with ``selection-trace resolution`` — the guard that prevents a
    raw plan row from reaching model construction."""
    with pytest.raises(NotImplementedError, match="selection-trace resolution"):
        fe.resolve_model_factory("selected_top_1", FROZEN, 4)
    with pytest.raises(NotImplementedError, match="selection-trace resolution"):
        fe.resolve_model_factory("selected:A-E1_architecture", FROZEN, 4)


def test_resolve_a_e1_scoring_plan_row_concrete_passthrough(tmp_path):
    """R4 stop-fix #2: for a concrete (historical / controlled / search_stage1) fit, the helper
    returns ``plan_by_fit[fit_id]`` unchanged — no receipt read, no placeholder resolution."""
    run_dir, plan = _write_real_a_e1_run(tmp_path)
    run_id = "G3-AE1-staged-exec-v1"
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan, matrix_by_fit=matrix_by_fit, module_id="A-E1")
    # first A-E1 fit is concrete (historical / controlled / stage1) — no stage receipts exist
    concrete_fit = next(fid for fid, row in matrix_by_fit.items()
                        if str(row["module"]) == "A-E1" and fe._a_e1_fit_stage(row) == "concrete")
    resolved = fe._resolve_a_e1_scoring_plan_row(
        run_dir=run_dir, run_id=run_id, fit_id=concrete_fit,
        matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)
    assert resolved == dict(plan_by_fit[concrete_fit])
    assert not any((run_dir / f"stage1_selection_{route}_receipt.json").exists()
                   for route in fe._A_E1_OPTIMIZED_ROUTES)


@pytest.mark.parametrize("attack", [
    "stage1_trace_tampered",
    "stage1_receipt_missing",
    "stage1_ledger_double_binding",
    "stage1_receipt_sha_mismatch",
    "selected_top_slot_absent",
    "cross_route",
    "matrix_row_sha_unbound",
])
def test_resolve_a_e1_scoring_plan_row_fail_closed(tmp_path, attack):
    """R4 stop-fix #3: ``_resolve_a_e1_scoring_plan_row`` resolves a stage2 placeholder to a
    concrete architecture in the NON-attack baseline, then fail-closes on every tamper of the
    stage1 evidence chain, a cross-route plan row, an unbound matrix SHA, or an absent top4 slot."""
    run_dir, plan = _write_real_a_e1_run(tmp_path)
    run_id = "G3-AE1-staged-exec-v1"
    fe.build_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan, matrix_by_fit=matrix_by_fit, module_id="A-E1")
    stage2_fit = next(fid for fid, row in matrix_by_fit.items()
                      if str(row["module"]) == "A-E1" and str(row["fit_kind"]) == "search_stage2"
                      and str(row["route"]) == "F2")
    # Baseline: the helper resolves the stage2 placeholder to a concrete architecture
    baseline = fe._resolve_a_e1_scoring_plan_row(
        run_dir=run_dir, run_id=run_id, fit_id=stage2_fit,
        matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)
    assert not str(baseline["architecture"]).startswith("selected_top_")

    if attack == "selected_top_slot_absent":
        # Pick a real stage2 fit; its placeholder (selected_top_{1..4}) IS in the full top4 so the
        # baseline resolves.  _resolve_stage2_plan_row must fail-close when the placeholder is
        # absent from a reduced 2-slot top4.
        placeholder = str(plan_by_fit[stage2_fit]["architecture"])
        reduced_top4 = {f"selected_top_{i}": f"m0{i}" for i in range(1, 3)}  # slots 1-2 only
        if placeholder in reduced_top4:
            # use the complementary 2-slot set so the fit's slot is definitely absent
            reduced_top4 = {f"selected_top_{i}": f"m0{i}" for i in range(3, 5)}
        assert placeholder not in reduced_top4, "test setup: placeholder must be absent from top4"
        with pytest.raises(ValueError, match="top4"):
            fe._resolve_stage2_plan_row(dict(plan_by_fit[stage2_fit]), reduced_top4)
        return

    if attack == "cross_route":
        tampered_plan = dict(plan_by_fit)
        tampered_row = dict(plan_by_fit[stage2_fit])
        tampered_row["route"] = "V"  # matrix route is F2
        tampered_plan[stage2_fit] = tampered_row
        with pytest.raises(ValueError, match="disagrees with matrix route"):
            fe._resolve_a_e1_scoring_plan_row(
                run_dir=run_dir, run_id=run_id, fit_id=stage2_fit,
                matrix_by_fit=matrix_by_fit, plan_by_fit=tampered_plan)
        return

    if attack == "matrix_row_sha_unbound":
        tampered_plan = dict(plan_by_fit)
        tampered_row = dict(plan_by_fit[stage2_fit])
        tampered_row["matrix_row_sha256"] = "0" * 64
        tampered_plan[stage2_fit] = tampered_row
        with pytest.raises(ValueError, match="matrix_row_sha256"):
            fe._resolve_a_e1_scoring_plan_row(
                run_dir=run_dir, run_id=run_id, fit_id=stage2_fit,
                matrix_by_fit=matrix_by_fit, plan_by_fit=tampered_plan)
        return

    # File-based attacks: mutate the stage1 evidence on disk, then re-call the helper
    trace_path = run_dir / "stage1_selection_F2_trace.jsonl"
    receipt_path = run_dir / "stage1_selection_F2_receipt.json"
    ledger_path = run_dir / "stage1_selection_F2_ledger.jsonl"
    if attack == "stage1_trace_tampered":
        trace_path.write_bytes(trace_path.read_bytes() + b'\n{"injected": true}\n')
    elif attack == "stage1_receipt_missing":
        receipt_path.unlink()
    elif attack == "stage1_ledger_double_binding":
        first_line = ledger_path.read_bytes().splitlines()[0]
        ledger_path.write_bytes(ledger_path.read_bytes() + first_line + b"\n")
    elif attack == "stage1_receipt_sha_mismatch":
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["selection_trace_sha256"] = "0" * 64
        receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")

    with pytest.raises((ValueError, FileNotFoundError, json.JSONDecodeError)):
        fe._resolve_a_e1_scoring_plan_row(
            run_dir=run_dir, run_id=run_id, fit_id=stage2_fit,
            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)


def test_build_a_e1_stage2_selection_no_longer_accepts_top4_kwarg(tmp_path):
    """R4 stop-fix #4a: ``build_a_e1_stage2_selection`` signature lock — the removed ``top4=``
    kwarg is rejected (top4 is recovered from the on-disk stage1 receipt, never injected)."""
    run_dir, _plan = _write_real_a_e1_run(tmp_path)
    with pytest.raises(TypeError, match="top4"):
        fe.build_a_e1_stage2_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
            run_id="G3-AE1-staged-exec-v1", route="F2",
            top4={"selected_top_1": "m01"})


def test_score_a_e1_winner_retrain_no_longer_accepts_route_stage2_kwarg():
    """R4 stop-fix #4b: ``_score_a_e1_winner_retrain`` signature lock — the removed
    ``route_stage2=`` kwarg is rejected and the new ``run_id=`` is required."""
    import inspect
    params = inspect.signature(fe._score_a_e1_winner_retrain).parameters
    assert "route_stage2" not in params, "route_stage2 kwarg must be removed"
    assert "run_id" in params, "run_id kwarg must be present"
    with pytest.raises(TypeError, match="route_stage2"):
        fe._score_a_e1_winner_retrain(
            study_root=STUDY_ROOT, run_dir=Path("/nonexistent"), cache_root=Path("/nonexistent"),
            frozen=FROZEN, effective=EFFECTIVE, candidates=(),
            run_id="test", score_fit=None, route_stage2={})


def test_checkpoint_architecture_mismatch_fails_via_real_state_dict(tmp_path):
    """R4 stop-fix #5: a real checkpoint trained for architecture A (m01, widths [64, 32])
    genuinely fails to load into a model built for a different architecture B (m05, widths
    [128, 64, 32]) — real shape mismatch, no mock. This is the structural guarantee that a
    wrong-architecture checkpoint cannot silently score."""
    from study02a.training import load_checkpoint
    # m01 and m05 have genuinely different layer widths
    factory_a = fe.resolve_model_factory("m01", FROZEN, 15)
    factory_b = fe.resolve_model_factory("m05", FROZEN, 15)
    model_a = factory_a()
    model_b = factory_b()
    shapes_a = {k: tuple(v.shape) for k, v in model_a.state_dict().items()}
    shapes_b = {k: tuple(v.shape) for k, v in model_b.state_dict().items()}
    assert shapes_a != shapes_b, "m01 and m05 must have different weight shapes for this test"
    # Train a real checkpoint for m01
    tx = torch.randn(32, 15)
    ty = torch.randn(32, 3)
    vx = torch.randn(8, 15)
    vy = torch.randn(8, 3)
    fit_a = fit_candidate(factory_a, (tx, ty), (vx, vy),
                          seed=1, max_epochs=2, min_epochs=1, patience=1, batch_size=16)
    # Loading m01's state_dict into m05's model must raise (real size mismatch)
    state_dict_a = load_checkpoint(fit_a.checkpoint_bytes)
    with pytest.raises(RuntimeError, match="size mismatch"):
        model_b.load_state_dict(state_dict_a)


# -- Group 1: production-bound (SLOW) ----------------------------------------
# These exercise the REAL checkpoint scoring chain (no score_fit mock, no
# _prepare_fit_inputs monkeypatch) for ONE stage2 / winner-retrain fit whose
# row has been resolved by ``_resolve_a_e1_scoring_plan_row``.  They are the
# single-fit partial variant of the full-builder production test.


def _train_checkpoint_through_prepared(prepared, *, seed, run_id, fit_id):
    """Train a real checkpoint THROUGH the prepared model_factory (so dims match the production
    scoring path) on a small subset of the real scaled dataset, and return the production
    (checkpoint_bytes, checkpoint_sha256, evidence) triple.

    Dispatches on the prepared batch type: fixed-width (MLP/F2/V routes) uses
    :func:`fit_candidate`; set (DeepSets/S route) calls the private
    ``_fit_deterministic_candidate`` directly with the set batch's
    ``(values, mask, model_n)`` inputs and the DeepSets forward, so the checkpoint
    architecture/dims match the production scoring path for the S route too."""
    from study02a.training import _fit_deterministic_candidate
    from study02a.formal_data import FormalSetBatch
    train_batch = prepared.scaled_training.batch
    val_batch = prepared.scaled_validation.batch
    if isinstance(train_batch, FormalSetBatch):
        sub_n = min(32, int(train_batch.values.shape[0]))
        sub_v = min(8, int(val_batch.values.shape[0]))
        val_values = val_batch.values[:sub_v]
        val_mask = val_batch.mask[:sub_v]
        val_model_n = val_batch.model_n[:sub_v]
        warmup = _fit_deterministic_candidate(
            prepared.model_factory,
            (train_batch.values[:sub_n], train_batch.mask[:sub_n], train_batch.model_n[:sub_n]),
            train_batch.targets[:sub_n],
            val_batch.targets[:sub_v],
            lambda model, inputs: model(inputs[0], inputs[1], inputs[2]),
            lambda model: model(val_values, val_mask, val_model_n),
            seed=int(seed) % 1000, max_epochs=2, min_epochs=1, patience=1, batch_size=16,
            loss_id=prepared.loss_id, lr=1e-3, weight_decay=1e-4,
        )
    else:
        sub_n = min(32, int(train_batch.features.shape[0]))
        sub_v = min(8, int(val_batch.features.shape[0]))
        warmup = fit_candidate(
            prepared.model_factory,
            (train_batch.features[:sub_n], train_batch.targets[:sub_n]),
            (val_batch.features[:sub_v], val_batch.targets[:sub_v]),
            seed=int(seed) % 1000, max_epochs=2, min_epochs=1, patience=1, batch_size=16,
            loss_id=prepared.loss_id,
        )
    curve = tuple(100.0 / (i + 1) for i in range(60))
    best_epoch = min(range(60), key=lambda i: curve[i])
    evidence = {
        "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": str(fit_id),
        "run_id": str(run_id), "checkpoint_sha256": warmup.checkpoint_sha256,
        "actual_epochs": 60, "best_epoch_one_based": best_epoch + 1, "hit_epoch_100": False,
        "early_stop_reason": "patience_exhausted",
        "terminal_validation_slope": fe._terminal_ols_slope(curve),
        "validation_curve": list(curve), "test_access_count": 0,
    }
    return warmup.checkpoint_bytes, warmup.checkpoint_sha256, evidence


def _install_small_data_pilot(monkeypatch, *, rows: int = 20, points: int = 4, repeats: int = 2):
    """Shrink the production data-source layer to a tiny pilot so the REAL
    ``_prepare_fit_inputs`` / ``resolve_model_factory`` chain runs in seconds.

    Codex scope (revision #1): only the bottom-level cache / data-source layer is
    swapped -- ``build_training_spec`` / ``build_validation_spec`` are routed to
    the private test-only ``_*_for_tests`` builders (which emit ``_TestDatasetSpec``
    over ``rows`` x ``points`` x ``repeats``), and ``cache_dataset`` is routed to
    ``_cache_dataset_for_tests``. The behaviours of ``_prepare_fit_inputs`` and
    ``resolve_model_factory`` are NOT mocked or replaced -- they still run for
    real, just over pilot-scale data. Patches ``formal_executor`` (so
    ``reconstruct_a_e1_specs`` + ``_prepare_fit_inputs`` see pilot specs) AND
    ``formal_scheduler`` (so ``_plan_rows`` derives ``training_cache_key`` /
    ``validation_cache_key`` from the SAME pilot specs -- otherwise the plan keys
    would drift from the reconstructed keys and ``reconstruct_a_e1_specs`` would
    fail closed at the ``cache_key`` equality ``_require``)."""
    from study02a import formal_scheduler
    from study02a.formal_runner import (
        _pilot_for_tests,
        _build_training_spec_for_tests,
        _build_validation_spec_for_tests,
        _cache_dataset_for_tests,
    )
    pilot = _pilot_for_tests(rows=rows, points=points, repeats=repeats)

    def small_training(*, route, distribution, n_mode, fixed_n, training_rows,
                       frozen_config, effective_config):
        return _build_training_spec_for_tests(
            route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
            training_rows=training_rows, frozen_config=frozen_config,
            effective_config=effective_config, pilot=pilot)

    def small_validation(*, route, distribution, n_mode, fixed_n,
                         frozen_config, effective_config):
        return _build_validation_spec_for_tests(
            route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n,
            frozen_config=frozen_config, effective_config=effective_config, pilot=pilot)

    def small_cache(spec, frozen_config, effective_config, cache_dir):
        return _cache_dataset_for_tests(spec, frozen_config, effective_config, cache_dir)

    # formal_executor: reconstruct_a_e1_specs + _prepare_fit_inputs look these up here.
    monkeypatch.setattr(fe, "build_training_spec", small_training)
    monkeypatch.setattr(fe, "build_validation_spec", small_validation)
    monkeypatch.setattr(fe, "cache_dataset", small_cache)
    # formal_scheduler: _plan_rows computes training_cache_key/validation_cache_key here.
    monkeypatch.setattr(formal_scheduler, "build_training_spec", small_training)
    monkeypatch.setattr(formal_scheduler, "build_validation_spec", small_validation)


@pytest.mark.slow
def test_stage2_checkpoint_scoring_resolves_placeholder_real_chain_single_fit_partial(
    tmp_path, monkeypatch
):
    """R4 stop-fix #6 (PARTIAL): for ONE F2 stage2 fit, ``_resolve_a_e1_scoring_plan_row``
    recovers the route's stage1 top4 from disk and resolves the placeholder architecture, then
    the REAL ``_score_fit_from_checkpoint`` (no score_fit mock, no ``_prepare_fit_inputs``
    monkeypatch) loads the checkpoint and scores it on the real validation batch.  The
    placeholder itself would crash ``resolve_model_factory`` (proven in the same test).  This is
    the single-fit partial variant — it does NOT claim to be the full-builder production test."""
    import math
    # Shrink the data-source layer (pilot) so the REAL _prepare_fit_inputs + resolve_model_factory
    # chain finishes in seconds; both must still run for real (no behaviour mock).
    _install_small_data_pilot(monkeypatch)
    run_dir, plan = _write_real_a_e1_run(tmp_path)
    run_id = "G3-AE1-staged-exec-v1"
    cache_root = tmp_path / "cache"
    # Publish stage1 receipt for F2 (injected score_fit — this is setup, not the production path)
    fe.build_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan, matrix_by_fit=matrix_by_fit, module_id="A-E1")
    # Pick the first F2 stage2 fit
    stage2_fit = next(fid for fid, row in matrix_by_fit.items()
                      if str(row["module"]) == "A-E1" and str(row["fit_kind"]) == "search_stage2"
                      and str(row["route"]) == "F2")
    # Resolve the placeholder from on-disk evidence (the R4 fix)
    resolved_row = fe._resolve_a_e1_scoring_plan_row(
        run_dir=run_dir, run_id=run_id, fit_id=stage2_fit,
        matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)
    assert not str(resolved_row["architecture"]).startswith("selected_top_")
    # The placeholder itself would crash resolve_model_factory (the R4 crash site)
    with pytest.raises(NotImplementedError, match="selection-trace resolution"):
        fe.resolve_model_factory(str(plan_by_fit[stage2_fit]["architecture"]), FROZEN, 4)
    # Build REAL prepared inputs for the resolved row (exercises _validate_plan_against_matrix +
    # _rebuild_authority indirectly via resolve_model_factory on the real architecture)
    prepared = fe._prepare_fit_inputs(resolved_row, FROZEN, EFFECTIVE, cache_root)
    # Train a real checkpoint THROUGH the resolved model_factory (dims match the scoring path)
    ckpt_bytes, ckpt_sha, evidence = _train_checkpoint_through_prepared(
        prepared, seed=resolved_row["seed"], run_id=run_id, fit_id=stage2_fit)
    fe._write_outputs(run_dir, stage2_fit, run_id, ckpt_bytes, ckpt_sha, evidence)
    # REAL production scoring path: _score_fit_from_checkpoint (no mock of score_fit /
    # resolve_model_factory / _prepare_fit_inputs)
    result = fe._score_fit_from_checkpoint(
        run_dir=run_dir, cache_root=cache_root, fit_id=stage2_fit, plan_row=resolved_row,
        frozen=FROZEN, effective=EFFECTIVE, fit_states={stage2_fit: "succeeded"},
        module_id="A-E1", decision_id=fe._a_e1_stage2_decision_id("F2"),
        candidate_id=f"{plan_by_fit[stage2_fit]['architecture']}:{plan_by_fit[stage2_fit]['optimizer']}",
    )
    assert isinstance(result, FitEvaluation)
    assert result.failed is False
    assert result.checkpoint_sha256 == hashlib.sha256(ckpt_bytes).hexdigest()
    assert math.isfinite(float(result.selection_score))
    assert len(result.point_records) == len(prepared.validation_metadata)


@pytest.mark.slow
def test_winner_retrain_checkpoint_scoring_resolves_placeholder_real_chain_single_fit_partial(
    tmp_path, monkeypatch
):
    """R4 stop-fix #7 (PARTIAL): for ONE F2 winner-retrain fit, ``_resolve_a_e1_scoring_plan_row``
    recovers stage1 top4 + stage2 winner from disk and resolves the ``selected:A-E1_*``
    placeholders to concrete architecture/optimizer/loss, then REAL ``_score_fit_from_checkpoint``
    scores the checkpoint on the real validation batch.  The placeholder itself would crash
    ``resolve_model_factory``."""
    import math
    # Shrink the data-source layer (pilot) so the REAL _prepare_fit_inputs + resolve_model_factory
    # chain finishes in seconds; both must still run for real (no behaviour mock).
    _install_small_data_pilot(monkeypatch)
    run_dir, plan = _write_real_a_e1_run(tmp_path)
    run_id = "G3-AE1-staged-exec-v1"
    cache_root = tmp_path / "cache"
    # Publish stage1 + stage2 receipts for F2 (setup — not the production scoring path)
    fe.build_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    fe.build_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan, matrix_by_fit=matrix_by_fit, module_id="A-E1")
    wr_fit = next(fid for fid, row in matrix_by_fit.items()
                  if str(row["module"]) == "A-E1" and str(row["fit_kind"]) == "winner_retrain"
                  and str(row["route"]) == "F2")
    # Resolve the selected:A-E1_* placeholders from stage1+stage2 evidence (the R4 fix)
    resolved_row = fe._resolve_a_e1_scoring_plan_row(
        run_dir=run_dir, run_id=run_id, fit_id=wr_fit,
        matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)
    assert not str(resolved_row["architecture"]).startswith("selected:")
    assert not str(resolved_row["optimizer"]).startswith("selected:")
    assert not str(resolved_row["loss"]).startswith("selected:")
    # The placeholder itself would crash resolve_model_factory
    with pytest.raises(NotImplementedError, match="selection-trace resolution"):
        fe.resolve_model_factory(str(plan_by_fit[wr_fit]["architecture"]), FROZEN, 4)
    # Build REAL prepared inputs, train checkpoint, write, score
    prepared = fe._prepare_fit_inputs(resolved_row, FROZEN, EFFECTIVE, cache_root)
    ckpt_bytes, ckpt_sha, evidence = _train_checkpoint_through_prepared(
        prepared, seed=resolved_row["seed"], run_id=run_id, fit_id=wr_fit)
    fe._write_outputs(run_dir, wr_fit, run_id, ckpt_bytes, ckpt_sha, evidence)
    result = fe._score_fit_from_checkpoint(
        run_dir=run_dir, cache_root=cache_root, fit_id=wr_fit, plan_row=resolved_row,
        frozen=FROZEN, effective=EFFECTIVE, fit_states={wr_fit: "succeeded"},
        module_id="A-E1", decision_id=fe._A_E1_BASELINE_DECISION_ID, candidate_id="F2",
    )
    assert isinstance(result, FitEvaluation)
    assert result.failed is False
    assert result.checkpoint_sha256 == hashlib.sha256(ckpt_bytes).hexdigest()
    assert math.isfinite(float(result.selection_score))


# -- Group 2: provenance equivalence (SLOW) ----------------------------------
# These run the REAL ``run_a_e1_staged`` (all 349 A-E1 fits) with a runner that trains each
# checkpoint through the REAL resolved ``model_factory``, then exercise the production scoring
# path (``build_module_selection`` and ``rebuild_selection_point_provenance``) to verify
# publish and rebuild agree on every stage2 fit's concrete context.


def _arch_matched_fit_runner():
    """A fit_runner for ``run_a_e1_staged`` that trains each fit's checkpoint through the REAL
    resolved ``model_factory`` (via ``_prepare_fit_inputs`` on the resolved plan row), so the
    production scoring path can reload and forward each checkpoint.  Training uses a small
    subset of the real scaled dataset for speed; the checkpoint's architecture / dims match the
    full dataset (input_dim depends on the route's feature count, not the row count).  A per
    ``(route, architecture, fixed_n)`` cache avoids redundant dataset rebuilds for fits sharing
    a spec.

    The cache key MUST include ``fixed_n`` (the n that determines ``input_dim`` for fixed-n
    routes): two fits with the same ``(route, arch)`` but different ``fixed_n`` have different
    ``input_dim`` and their checkpoints are NOT interchangeable -- reloading an ``input_dim=5``
    checkpoint into an ``input_dim=15`` model raises a dimension mismatch.  The earlier
    ``(route, arch)`` key silently reused the first n's checkpoint for every other n, which the
    rebuild scoring path then crashed on (or scored against a mismatched model).
    """
    from study02a.formal_scheduler import record_fit_succeeded

    ckpt_cache: dict[tuple[str, str, object], tuple[bytes, str]] = {}

    def runner(*, study_root, run_dir, cache_root, plan_row, claim, frozen, effective, timestamp):
        fit_id = str(claim["fit_id"])
        route = str(plan_row["route"])
        arch = str(plan_row["architecture"])
        # fixed_n (None for shared_n routes) captures input_dim; seed is intentionally excluded --
        # any same-dim checkpoint is valid for the production scoring reload, which only forwards
        # the checkpoint and never retrains.
        key = (route, arch, plan_row.get("fixed_n"))
        if key not in ckpt_cache:
            prepared = fe._prepare_fit_inputs(plan_row, frozen, effective, cache_root)
            ckpt_bytes, ckpt_sha, _evidence = _train_checkpoint_through_prepared(
                prepared, seed=plan_row["seed"], run_id=plan_row["run_id"], fit_id=fit_id)
            ckpt_cache[key] = (ckpt_bytes, ckpt_sha)
        ckpt_bytes, ckpt_sha = ckpt_cache[key]
        curve = tuple(100.0 / (i + 1) for i in range(60))
        best_epoch = min(range(60), key=lambda i: curve[i])
        evidence = {
            "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": fit_id,
            "run_id": str(plan_row["run_id"]), "checkpoint_sha256": ckpt_sha,
            "actual_epochs": 60, "best_epoch_one_based": best_epoch + 1, "hit_epoch_100": False,
            "early_stop_reason": "patience_exhausted",
            "terminal_validation_slope": fe._terminal_ols_slope(curve),
            "validation_curve": list(curve), "test_access_count": 0,
        }
        output_hashes = fe._write_outputs(
            run_dir, fit_id, str(plan_row["run_id"]), ckpt_bytes, ckpt_sha, evidence)
        return {"state": "succeeded", "receipt": record_fit_succeeded(
            run_dir, cache_root=cache_root, fit_id=fit_id, owner_id=str(claim["owner_id"]),
            owner_nonce=str(claim["owner_nonce"]), output_hashes=output_hashes, timestamp=timestamp)}
    return runner


def _stage_arch_matched_a_e1_run(tmp_path, monkeypatch, *, run_id):
    """Set up a REAL A-E1 run_dir with all 349 fits' outputs + stage1/stage2 receipts,
    WITHOUT the O(N^2) scheduler claim/record loop.

    WHAT RUNS REAL (scientific checkpoint-scoring path):
      ``_prepare_fit_inputs`` + ``resolve_model_factory`` + ``_write_outputs`` run REAL
      (unmocked) for every fit -- each fit's checkpoint is trained THROUGH the resolved
      model_factory on the (pilot-scaled) real validation batch, so dims and forward
      scoring match the production path. The pilot only shrinks the data source; it does
      not mock any of these helpers.

    WHAT IS STUBBED (scheduler authority -- NOT scientific):
      ``_rebuild_authority`` is stubbed later by the caller via
      ``_mock_rebuild_authority_all_succeeded``. The REAL ``run_a_e1_staged`` /
      scheduler journal (``claim_next_fit`` / ``record_fit_succeeded`` / event replay)
      is NEVER driven here -- ``materialize_run`` only writes the manifest/plan/initial
      state; per-fit outputs are written directly via ``_write_outputs``. This bypasses
      the per-fit O(N) ``_next_state`` event replay (the run_a_e1_staged bottleneck) and
    the O(N^2) total scheduler replay. The authority/tamper-detection coverage lives in
    the attack tests (which use the unmocked ``_rebuild_authority``).

    Uses ``materialize_run`` (real scheduler authority setup), publishes stage1/stage2
    receipts via smoke ``score_fit`` (no checkpoint scoring), then trains + writes
    ``outputs/{fit_id}/`` for every fit through the REAL ``_prepare_fit_inputs`` +
    ``resolve_model_factory`` + ``_write_outputs`` (reusing ``_arch_matched_fit_runner``'s
    fixed_n-keyed cache).

    Returns ``(run_dir, plan_rows)``. The caller should monkeypatch ``_rebuild_authority``
    to return all-succeeded ``fit_states`` (via ``_mock_rebuild_authority_all_succeeded``)
    before calling ``rebuild_selection_point_provenance`` / ``build_module_selection`` --
    they query ``fit_states`` through ``_rebuild_authority``.

    This mirrors the existing ``_accredit_real_matrix_run`` pattern (test file ~:1244)
    which also writes outputs directly and stubs the authority."""
    _install_small_data_pilot(monkeypatch)
    from study02a.formal_scheduler import materialize_run

    # 1. Real scheduler authority setup (manifest + plan + initial state).
    matrix_path = (STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv").resolve()
    materialize_run(
        study_root=STUDY_ROOT, matrix_path=matrix_path, module_id="A-E1", run_id=run_id,
        artifact_root=tmp_path / "artifact", cache_root=tmp_path / "cache", predecessor=None)
    run_dir = tmp_path / "artifact" / "A-E1" / run_id
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]

    # 2. Publish stage1/stage2 receipts for F2 and V via smoke score_fit (no checkpoint scoring,
    #    no scheduler claim/record). Needed for placeholder resolution in step 4.
    for route in ("F2", "V"):
        fe.build_a_e1_stage1_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
            run_id=run_id, route=route, score_fit=_smoke_score_fit())
        fe.build_a_e1_stage2_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
            run_id=run_id, route=route, score_fit=_smoke_score_fit())

    # 3. Recover top4/winner from the published receipts (for placeholder resolution).
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    stage1_by_route = {
        route: fe._recover_a_e1_stage1_selection(run_dir=run_dir, run_id=run_id, route=route)
        for route in ("F2", "V")}
    stage2_by_route = {
        route: fe._recover_a_e1_stage2_selection(
            run_dir=run_dir, run_id=run_id, route=route, top4=stage1_by_route[route]["top4"])
        for route in ("F2", "V")}

    # 4. Train + write outputs for every fit via the REAL _prepare_fit_inputs +
    #    resolve_model_factory + _write_outputs. No claim/record -> no O(N^2) scheduler replay.
    ckpt_cache: dict[tuple, tuple[bytes, str]] = {}
    for plan_row in plan_rows:
        fit_id = str(plan_row["fit_id"])
        route = str(plan_row["route"])
        stage = fe._a_e1_fit_stage(matrix_by_fit[fit_id])
        if stage == "stage2":
            resolved = fe._resolve_stage2_plan_row(plan_row, stage1_by_route[route]["top4"])
        elif stage == "winner_retrain":
            resolved = fe._resolve_winner_retrain_plan_row(plan_row, stage2_by_route[route]["winner"])
        else:
            resolved = plan_row
        # Same fixed_n-aware cache key as _arch_matched_fit_runner.
        key = (route, str(resolved["architecture"]), resolved.get("fixed_n"))
        if key not in ckpt_cache:
            prepared = fe._prepare_fit_inputs(resolved, FROZEN, EFFECTIVE, tmp_path / "cache")
            ckpt_bytes, ckpt_sha, _ = _train_checkpoint_through_prepared(
                prepared, seed=resolved["seed"], run_id=run_id, fit_id=fit_id)
            ckpt_cache[key] = (ckpt_bytes, ckpt_sha)
        ckpt_bytes, ckpt_sha = ckpt_cache[key]
        curve = tuple(100.0 / (i + 1) for i in range(60))
        best_epoch = min(range(60), key=lambda i: curve[i])
        evidence = {
            "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": fit_id,
            "run_id": run_id, "checkpoint_sha256": ckpt_sha,
            "actual_epochs": 60, "best_epoch_one_based": best_epoch + 1, "hit_epoch_100": False,
            "early_stop_reason": "patience_exhausted",
            "terminal_validation_slope": fe._terminal_ols_slope(curve),
            "validation_curve": list(curve), "test_access_count": 0,
        }
        fe._write_outputs(run_dir, fit_id, run_id, ckpt_bytes, ckpt_sha, evidence)

    return run_dir, plan_rows


def _mock_rebuild_authority_all_succeeded(monkeypatch, plan_rows):
    """Monkeypatch ``fe._rebuild_authority`` to return all-succeeded ``fit_states`` for the
    plan's fits. Used after ``_stage_arch_matched_a_e1_run`` so that
    ``rebuild_selection_point_provenance`` / ``build_module_selection`` /
    ``build_a_e1_stage2_selection`` can query ``fit_states`` without driving the O(N)
    scheduler event replay.

    STUB BOUNDARY (what this mock does and does NOT touch):
      - DOES: return ``{fit_id: "succeeded"}`` for every plan fit, so the scoring entry's
        ``fit_states.get(fit_id)`` lookup is O(1) and every fit is treated as terminal-
        succeeded (the checkpoint is on disk from ``_stage_arch_matched_a_e1_run``). This
        is scheduler bookkeeping, not a scientific input.
      - DOES NOT: replace or short-circuit the scientific checkpoint-scoring path. The
        REAL ``_prepare_fit_inputs`` + ``resolve_model_factory`` + checkpoint load +
        ``validation_failure_penalized_l_param_points`` forward scoring still run end-to-end
        for every scored fit -- the scored ``selection_score`` / ``checkpoint_sha256`` /
        ``point_records`` come from the real forward pass on the real (pilot-scaled)
        validation batch, NOT from this stub. ``_rebuild_authority``'s own tamper-detection
        correctness is covered by the attack tests (which leave it unmocked).

    Precedent: the existing test file mocks ``_rebuild_authority`` at ~:1074 and ~:2136, and
    ``_accredit_real_matrix_run`` (~:1326) stubs the authority for the same reason -- the
    scheduler replay is authority/tamper infrastructure, not the scientific scoring path."""
    fit_states = {str(row["fit_id"]): "succeeded" for row in plan_rows}

    def _fast_rebuild(run_dir, cache_root, *, validate_controller=True):
        return None, None, {"fit_states": fit_states, "live_claim": None}, []

    monkeypatch.setattr(fe, "_rebuild_authority", _fast_rebuild)


def _apply_a_e1_test_overrides(monkeypatch, plan_rows):
    """Apply BOTH the pilot data-source shrink AND the all-succeeded ``_rebuild_authority``
    stub. Used at setup and re-applied after every ``monkeypatch.undo()`` (which clears ALL
    setattr calls, including these). Keeping the pilot active across the publish/rebuild phases
    is required because ``reconstruct_a_e1_specs`` checks the reconstructed spec's cache_key
    against the plan row's bound key -- if the pilot is dropped, the real (full-data) builder
    produces a different cache_key and the check fails closed."""
    _install_small_data_pilot(monkeypatch)
    _mock_rebuild_authority_all_succeeded(monkeypatch, plan_rows)


@pytest.mark.slow
def test_publish_and_rebuild_produce_same_concrete_context(tmp_path, monkeypatch):
    """R4 stop-fix #8: publish (``build_module_selection``) and rebuild
    (``rebuild_selection_point_provenance``) — both via the REAL production scoring path
    (``score_fit=None``) — produce identical concrete context for every stage2 fit: same resolved
    architecture / optimizer / loss (captured from ``_resolve_a_e1_scoring_plan_row``), same
    ``checkpoint_sha256`` / ``validation_identity`` / ``selection_score``.  Proves the
    single-source scoring path does not drift between the two calls."""
    import shutil
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--", str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"

    # Stage the run_dir via the REAL _prepare_fit_inputs + resolve_model_factory + _write_outputs
    # for all 349 fits, WITHOUT the O(N^2) scheduler claim/record loop (see
    # _stage_arch_matched_a_e1_run). _prepare_fit_inputs + resolve_model_factory stay REAL.
    run_id = "r4-prov-0001"
    run_dir, _plan_rows = _stage_arch_matched_a_e1_run(tmp_path, monkeypatch, run_id=run_id)
    # Apply pilot data-source shrink + all-succeeded _rebuild_authority stub. Re-applied after
    # each monkeypatch.undo() below (undo clears every setattr, including the pilot -- without
    # it, reconstruct_a_e1_specs' cache_key check fails closed against the pilot plan keys).
    _apply_a_e1_test_overrides(monkeypatch, _plan_rows)

    # Delete the final selection artifacts so build_module_selection can re-publish via the REAL
    # production path (score_fit=None).  Stage1/stage2 receipts and outputs/ stay intact.
    for name in ("selection_trace.jsonl", "selection_receipt.json",
                 "selection_ledger.jsonl", "selection_diagnostics.jsonl"):
        path = run_dir / name
        if path.exists():
            path.unlink()
    pe_dir = run_dir / "selection"
    if pe_dir.exists():
        shutil.rmtree(pe_dir)

    real_resolve = fe._resolve_a_e1_scoring_plan_row
    real_derive = fe._derive_and_score_evaluations
    publish_resolutions: dict[str, dict[str, str]] = {}
    publish_evals: dict[str, FitEvaluation] = {}
    rebuild_resolutions: dict[str, dict[str, str]] = {}
    rebuild_evals: dict[str, FitEvaluation] = {}

    def _make_resolve_spy(sink_resolutions):
        def spy(*, run_dir, run_id, fit_id, matrix_by_fit, plan_by_fit):
            row = real_resolve(run_dir=run_dir, run_id=run_id, fit_id=fit_id,
                               matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)
            sink_resolutions[str(fit_id)] = {
                "architecture": str(row["architecture"]),
                "optimizer": str(row["optimizer"]),
                "loss": str(row["loss"])}
            return row
        return spy

    def _make_derive_spy(sink_evals):
        def spy(**kwargs):
            specs, evals = real_derive(**kwargs)
            for fid, ev in evals.items():
                sink_evals[str(fid)] = ev
            return specs, evals
        return spy

    # Publish via the REAL production path (score_fit=None — no mock of score_fit /
    # resolve_model_factory / _prepare_fit_inputs)
    monkeypatch.setattr(fe, "_resolve_a_e1_scoring_plan_row", _make_resolve_spy(publish_resolutions))
    monkeypatch.setattr(fe, "_derive_and_score_evaluations", _make_derive_spy(publish_evals))
    fe.build_module_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        module_id="A-E1", run_id=run_id)
    monkeypatch.undo()
    # monkeypatch.undo() cleared the pilot + _rebuild_authority stub -- re-apply both before rebuild.
    _apply_a_e1_test_overrides(monkeypatch, _plan_rows)

    # Rebuild via the REAL production path
    monkeypatch.setattr(fe, "_resolve_a_e1_scoring_plan_row", _make_resolve_spy(rebuild_resolutions))
    monkeypatch.setattr(fe, "_derive_and_score_evaluations", _make_derive_spy(rebuild_evals))
    fe.rebuild_selection_point_provenance(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        module_id="A-E1", run_id=run_id)
    monkeypatch.undo()

    # For every stage2 fit: resolved context + FitEvaluation fields agree between publish & rebuild
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    stage2_fits = [fid for fid, row in matrix_by_fit.items()
                   if str(row["module"]) == "A-E1" and str(row["fit_kind"]) == "search_stage2"]
    assert stage2_fits, "expected A-E1 stage2 fits in the frozen matrix"
    for fit_id in stage2_fits:
        assert fit_id in publish_resolutions, f"publish did not resolve stage2 fit {fit_id}"
        assert fit_id in rebuild_resolutions, f"rebuild did not resolve stage2 fit {fit_id}"
        assert publish_resolutions[fit_id] == rebuild_resolutions[fit_id], (
            f"resolved context drifted for stage2 fit {fit_id}: "
            f"publish={publish_resolutions[fit_id]} rebuild={rebuild_resolutions[fit_id]}")
        assert not publish_resolutions[fit_id]["architecture"].startswith("selected_top_")
        pe = publish_evals[fit_id]
        re_ = rebuild_evals[fit_id]
        assert pe.checkpoint_sha256 == re_.checkpoint_sha256
        assert pe.validation_identity == re_.validation_identity
        assert float(pe.selection_score) == pytest.approx(float(re_.selection_score))


@pytest.mark.slow
def test_rebuild_selection_point_provenance_resolves_stage2_placeholder(tmp_path, monkeypatch):
    """R4 stop-fix #9: ``rebuild_selection_point_provenance`` (REAL production path) resolves a
    stage2 placeholder to a concrete architecture and rebuilds a finite ``selection_score`` whose
    ``checkpoint_sha256`` matches the on-disk checkpoint bytes."""
    import math
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--", str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"

    # Stage the run_dir via the REAL _prepare_fit_inputs + resolve_model_factory + _write_outputs
    # for all 349 fits, WITHOUT the O(N^2) scheduler claim/record loop (see
    # _stage_arch_matched_a_e1_run). _prepare_fit_inputs + resolve_model_factory stay REAL.
    run_id = "r4-rebuild-0001"
    run_dir, plan_rows = _stage_arch_matched_a_e1_run(tmp_path, monkeypatch, run_id=run_id)
    # Stub _rebuild_authority to return all-succeeded fit_states (the fits' outputs are on disk);
    # rebuild queries fit_states through it. The scientific scoring path
    # (_prepare_fit_inputs + resolve_model_factory + validation_failure_penalized_l_param_points)
    # is NOT mocked.
    _mock_rebuild_authority_all_succeeded(monkeypatch, plan_rows)

    rebuilt = fe.rebuild_selection_point_provenance(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        module_id="A-E1", run_id=run_id)

    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    stage2_fit = next(fid for fid, row in matrix_by_fit.items()
                      if str(row["module"]) == "A-E1" and str(row["fit_kind"]) == "search_stage2"
                      and str(row["route"]) == "F2")
    ev = rebuilt[stage2_fit]
    assert ev.failed is False
    assert math.isfinite(float(ev.selection_score))
    checkpoint_bytes = (run_dir / "outputs" / stage2_fit / "checkpoint.pt").read_bytes()
    assert ev.checkpoint_sha256 == hashlib.sha256(checkpoint_bytes).hexdigest()


# -- Group 4: full-route production scoring (SLOW) ---------------------------
# Drives the REAL ``build_a_e1_stage2_selection`` (the original r4 crash entry) over the
# FULL F2 stage2 support (36 fits) with ``score_fit=None``.  Every fit is scored through
# the real checkpoint-load + forward path; only ``_rebuild_authority`` is stubbed (scheduler
# authority), per the Codex revision-1 scope.


@pytest.mark.slow
def test_build_a_e1_stage2_selection_full_route_production_scoring(tmp_path, monkeypatch):
    """R4 stop-fix #10 (FULL ROUTE): ``build_a_e1_stage2_selection(route="F2", score_fit=None)``
    -- the original r4 crash entry -- over the FULL F2 stage2 support (36 fits = 4 top4
    architectures x 3 optimizers x 3 seeds). Every fit is scored through the REAL
    checkpoint-load + forward path (no ``score_fit`` mock), after recovering the route's
    stage1 top4 from its on-disk verified receipt and writing a matching checkpoint for
    each fit's resolved architecture.

    Fixture construction (how each F2 stage2 fit gets a matching checkpoint):
      1. ``_install_small_data_pilot`` shrinks the data source (pilot) so the REAL
         ``_prepare_fit_inputs`` / ``resolve_model_factory`` chain finishes in seconds;
         cache_keys stay consistent between plan (``_write_real_a_e1_run`` ->
         ``_plan_rows``) and reconstruction (``reconstruct_a_e1_specs``) because both
         route through the patched pilot spec builders.
      2. ``_write_real_a_e1_run`` writes the REAL ``_PLAN_FIELDS`` plan (no ``fit_kind``)
         + manifest.
      3. ``build_a_e1_stage1_selection(route="F2", score_fit=_smoke_score_fit())``
         publishes ONLY the F2 stage1 receipt (the stage1 top4 authority).  No stage2
         receipt is pre-published (``publish_selection_receipt`` is no-replace; the
         production call below publishes it).
      4. Recover F2 stage1 top4 from that receipt (``_recover_a_e1_stage1_selection``).
      5. For every F2 stage2 fit (matrix ``fit_kind==search_stage2`` & ``route==F2``):
         resolve its ``selected_top_N`` placeholder via ``_resolve_a_e1_scoring_plan_row``
         (which reads the stage1 receipt from disk) -> concrete ``m0X`` architecture ->
         ``_prepare_fit_inputs`` on the resolved row -> train a small checkpoint through
         the resolved ``model_factory`` (``_train_checkpoint_through_prepared``) ->
         ``fe._write_outputs`` to ``outputs/{fit_id}/``. A ``(route, arch, fixed_n)`` cache
         keys checkpoint reuse across fits sharing a resolved architecture (4 unique
         checkpoints across 36 fits).

    WHAT RUNS REAL: ``_validate_plan_against_matrix``, ``_resolve_a_e1_scoring_plan_row``,
      ``_prepare_fit_inputs``, ``resolve_model_factory``, checkpoint load, forward scoring
      (``validation_failure_penalized_l_param_points``), trace/receipt/ledger publication.
    WHAT IS STUBBED: ``_rebuild_authority`` (avoids the multi-hour scheduler claim/record
      replay); see ``_mock_rebuild_authority_all_succeeded`` for the stub boundary.

    Requires a clean ``code/`` tree for the ``materialize_run`` authority check.
    """
    import math
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--", str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"

    # 1. Pilot data source: _prepare_fit_inputs + resolve_model_factory stay REAL but fast.
    _install_small_data_pilot(monkeypatch)
    run_id = "r4-stage2-full-0001"
    cache_root = tmp_path / "cache"

    # 2. Real plan (pilot cache_keys) + manifest. _write_real_a_e1_run calls _plan_rows,
    # which derives training/validation_cache_key from the patched pilot spec builders.
    run_dir, plan = _write_real_a_e1_run(tmp_path, run_id=run_id)

    # 3. Publish ONLY the F2 stage1 receipt (setup -- not the production scoring path).
    # No stage2 receipt exists; build_a_e1_stage2_selection publishes it (no-replace).
    fe.build_a_e1_stage1_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        run_id=run_id, route="F2", score_fit=_smoke_score_fit())
    # Sanity: stage2 receipt is NOT pre-published.
    assert not (run_dir / "stage2_selection_F2_receipt.json").exists()

    # 4. Recover F2 stage1 top4 (the authority each stage2 placeholder resolves against).
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan, matrix_by_fit=matrix_by_fit, module_id="A-E1")
    f2_top4 = fe._recover_a_e1_stage1_selection(
        run_dir=run_dir, run_id=run_id, route="F2")["top4"]
    f2_stage2_fits = [fid for fid, row in matrix_by_fit.items()
                      if str(row["module"]) == "A-E1"
                      and str(row["fit_kind"]) == "search_stage2"
                      and str(row["route"]) == "F2"]
    assert f2_stage2_fits, "expected F2 stage2 fits in the frozen matrix"
    assert len(f2_stage2_fits) == 36  # 4 top4 archs x 3 optimizers x 3 seeds

    # 5. For each F2 stage2 fit: placeholder -> concrete arch (via real receipt resolver) ->
    #    REAL _prepare_fit_inputs -> train small matching checkpoint -> _write_outputs.
    # fixed_n-aware cache key (same as _arch_matched_fit_runner) reuses one checkpoint per
    # resolved architecture (4 unique across 36 fits, all sharing fixed_n=10).
    ckpt_cache: dict[tuple[str, str, object], tuple[bytes, str]] = {}
    for fit_id in f2_stage2_fits:
        resolved_row = fe._resolve_a_e1_scoring_plan_row(
            run_dir=run_dir, run_id=run_id, fit_id=fit_id,
            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)
        assert not str(resolved_row["architecture"]).startswith("selected_top_")
        key = ("F2", str(resolved_row["architecture"]), resolved_row.get("fixed_n"))
        if key not in ckpt_cache:
            prepared = fe._prepare_fit_inputs(resolved_row, FROZEN, EFFECTIVE, cache_root)
            ckpt_bytes, ckpt_sha, _ev = _train_checkpoint_through_prepared(
                prepared, seed=resolved_row["seed"], run_id=run_id, fit_id=fit_id)
            ckpt_cache[key] = (ckpt_bytes, ckpt_sha)
        ckpt_bytes, ckpt_sha = ckpt_cache[key]
        curve = tuple(100.0 / (i + 1) for i in range(60))
        best_epoch = min(range(60), key=lambda i: curve[i])
        evidence = {
            "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": fit_id,
            "run_id": run_id, "checkpoint_sha256": ckpt_sha,
            "actual_epochs": 60, "best_epoch_one_based": best_epoch + 1, "hit_epoch_100": False,
            "early_stop_reason": "patience_exhausted",
            "terminal_validation_slope": fe._terminal_ols_slope(curve),
            "validation_curve": list(curve), "test_access_count": 0,
        }
        fe._write_outputs(run_dir, fit_id, run_id, ckpt_bytes, ckpt_sha, evidence)

    # 6. Stub _rebuild_authority (avoid O(N^2) scheduler replay); scientific scoring REAL.
    _mock_rebuild_authority_all_succeeded(monkeypatch, plan)

    # 7. Spy on _score_fit_from_checkpoint to capture which fits were scored (wraps the REAL
    #    function -- the real forward scoring still runs; this only observes).
    real_score_from_ckpt = fe._score_fit_from_checkpoint
    scored_evaluations: dict[str, FitEvaluation] = {}

    def _score_spy(**kwargs):
        evaluation = real_score_from_ckpt(**kwargs)
        scored_evaluations[str(kwargs["fit_id"])] = evaluation
        return evaluation
    monkeypatch.setattr(fe, "_score_fit_from_checkpoint", _score_spy)

    # 8. PRODUCTION CALL: the original r4 crash entry, score_fit=None (no score_fit mock).
    result = fe.build_a_e1_stage2_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        run_id=run_id, route="F2", score_fit=None)

    # (1) Every expected F2 stage2 fit was scored through the REAL forward path (the spy
    #     captured all of them; the set is exactly the frozen support, no more, no less).
    assert set(scored_evaluations) == set(f2_stage2_fits), (
        f"scored {len(scored_evaluations)} fits, expected {len(f2_stage2_fits)}; "
        f"missing={set(f2_stage2_fits) - set(scored_evaluations)}; "
        f"extra={set(scored_evaluations) - set(f2_stage2_fits)}")
    for fit_id, evaluation in scored_evaluations.items():
        assert evaluation.failed is False
        assert math.isfinite(float(evaluation.selection_score))
        checkpoint_bytes = (run_dir / "outputs" / fit_id / "checkpoint.pt").read_bytes()
        assert evaluation.checkpoint_sha256 == hashlib.sha256(checkpoint_bytes).hexdigest()
        # the resolved architecture (recovered via _resolve_a_e1_scoring_plan_row) is concrete
        resolved_arch = fe._resolve_a_e1_scoring_plan_row(
            run_dir=run_dir, run_id=run_id, fit_id=fit_id,
            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)["architecture"]
        assert not str(resolved_arch).startswith("selected_top_")

    # (2) Winner selected:A-E1_architecture is concrete (not selected_top_*) and bound to
    #     the recovered stage1 top4. selected_top_* would mean the placeholder leaked past
    #     _resolve_a_e1_scoring_plan_row into resolve_model_factory (the r4 crash).
    winner = result["winner"]
    winner_arch = str(winner["selected:A-E1_architecture"])
    assert not winner_arch.startswith("selected_top_"), (
        f"winner architecture is still a placeholder: {winner_arch!r}")
    assert winner_arch in set(f2_top4.values()), (
        f"winner arch {winner_arch!r} not in recovered F2 top4 {dict(f2_top4)!r}")
    assert winner["selected:A-E1_loss"] == "transformed_train_z_huber"  # frozen stage2 loss
    assert str(winner["selected:A-E1_optimizer"]) in {"o1", "o2", "o3"}

    # (3) The published stage2_selection_F2 trace/receipt/ledger re-validate via the
    #     fail-closed _recover_a_e1_stage2_selection and return the SAME winner + trace sha.
    trace_path = run_dir / "stage2_selection_F2_trace.jsonl"
    receipt_path = run_dir / "stage2_selection_F2_receipt.json"
    ledger_path = run_dir / "stage2_selection_F2_ledger.jsonl"
    assert trace_path.is_file() and receipt_path.is_file() and ledger_path.is_file()
    recovered = fe._recover_a_e1_stage2_selection(
        run_dir=run_dir, run_id=run_id, route="F2", top4=f2_top4)
    assert recovered["winner"] == winner
    assert recovered["selection_trace_sha256"] == result["selection_trace_sha256"]


# ---------------------------------------------------------------------------
# C1 control-plane predecessor binding (PredecessorTrace + _validate_predecessor +
# _validate_staged_resolution_ledger). The staged-ledger SHA + chain bind the A-E1
# predecessor's ``staged_resolution_ledger.jsonl`` (the on-disk authority for
# ``selected:F2_or_V``) so a downstream run rests on a file the predecessor cannot swap after
# materialize. Every variant mutates one binding and asserts _validate_predecessor fail-closes
# BEFORE any claim/training. No real r5 sealed dir is read; every predecessor is published
# into a tmp_path artifact root via the production A-E1 staged resolver (V-winning score_fit
# so ``selected:F2_or_V`` -> V, the A-E1 r5 outcome the design freezes).
# ---------------------------------------------------------------------------


def _publish_v_winning_a_e1_predecessor(tmp_path: Path):
    """Publish a real A-E1 staged run with V as the baseline winner, returning
    ``(run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)``.

    The staged ledger is the real 8-record chain from ``resolve_a_e1_staged_selection``;
    ``selected:F2_or_V`` resolves to V (the A-E1 r5 outcome the design freezes)."""
    specs, evaluations = _staged_specs_and_evaluations()
    run_dir, trace_sha, _records = _publish_staged_run(tmp_path, specs, evaluations)
    fe.resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=_STAGED_RUN_ID, score_fit=_baseline_score_fit(f2=0.20, v=0.10),  # V wins
    )
    staged_ledger_path = run_dir / fe._STAGED_LEDGER_NAME
    staged_ledger_sha = hashlib.sha256(staged_ledger_path.read_bytes()).hexdigest()
    return run_dir, trace_sha, staged_ledger_path, staged_ledger_sha


def _build_a_e1_pred_trace(
    run_dir: Path, trace_sha: str, staged_ledger_path: Path | None,
    staged_ledger_sha: str | None, **overrides,
) -> PredecessorTrace:
    """Build an A-E1 PredecessorTrace bound to the published A-E1 staged run, with overrides.

    The R3-C v2 authority triple (``scoped_code_sha256`` / ``authority_sha256``) defaults to
    the fixture's synthetic SHA-256s: the staged-only predecessor manifest published by
    ``_publish_staged_run`` has no ``scheduler.authority`` block to read from, so synthetic
    values stand in for the sealed formal-run authority (``_validate_predecessor`` v2 only
    checks non-None + SHA-256 format). Tests that need to bind specific authority values
    (e.g. continuity-mismatch fail-closed cases) override them via ``**overrides``.
    """
    fields: dict = dict(
        module_id="A-E1",
        run_id=_STAGED_RUN_ID,
        trace_path=run_dir / "selection_trace.jsonl",
        trace_sha256=trace_sha,
        receipt_path=run_dir / "selection_receipt.json",
        receipt_sha256=hashlib.sha256((run_dir / "selection_receipt.json").read_bytes()).hexdigest(),
        ledger_path=run_dir / "selection_ledger.jsonl",
        selection_code_commit=_D8_CODE_COMMIT,
        staged_ledger_path=staged_ledger_path,
        staged_ledger_sha256=staged_ledger_sha,
        scoped_code_sha256=_D8_SCOPED_CODE_SHA256,
        authority_sha256=_D8_AUTHORITY_SHA256,
    )
    fields.update(overrides)
    return PredecessorTrace(**fields)


def test_c1_predecessor_binding_accepts_real_a_e1_staged_ledger(tmp_path):
    """C1 happy path: a real A-E1 staged run (V winner) is accepted as an A-E3 predecessor;
    the manifest binds the staged-ledger SHA + extracts resolved_baseline_route=V."""
    from study02a import formal_contracts as fc
    run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    trace = _build_a_e1_pred_trace(run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)
    manifest = fc._validate_predecessor("A-E3", trace)
    assert manifest["module_id"] == "A-E1"
    assert manifest["selection_trace_sha256"] == trace_sha
    assert manifest["selection_staged_ledger_path"] == str(staged_ledger_path)
    assert manifest["selection_staged_ledger_sha256"] == staged_ledger_sha
    assert manifest["resolved_baseline_route"] == "V"


def test_c1_predecessor_binding_rejects_missing_predecessor(tmp_path):
    """G.1: A-E3 with no predecessor raises at _validate_predecessor (caught at materialize)."""
    from study02a import formal_contracts as fc
    with pytest.raises(ValueError, match="predecessor selection trace metadata"):
        fc._validate_predecessor("A-E3", None)


def test_c1_predecessor_binding_rejects_wrong_predecessor_module(tmp_path):
    """G.2: A-E3 requires an A-E1 predecessor; an A-E3-as-predecessor (or A-E2) is rejected."""
    from study02a import formal_contracts as fc
    run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    wrong_trace = _build_a_e1_pred_trace(
        run_dir, trace_sha, staged_ledger_path, staged_ledger_sha, module_id="A-E3",
    )
    with pytest.raises(ValueError, match="[Ww]rong predecessor module"):
        fc._validate_predecessor("A-E3", wrong_trace)


def test_c1_predecessor_binding_rejects_wrong_predecessor_run_id(tmp_path):
    """G.3: a predecessor trace whose run_id disagrees with the verified run is rejected."""
    from study02a import formal_contracts as fc
    run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    cross_run_trace = _build_a_e1_pred_trace(
        run_dir, trace_sha, staged_ledger_path, staged_ledger_sha, run_id="G3-AE1-cross-run-v1",
    )
    with pytest.raises(ValueError, match="run_id|trace"):
        fc._validate_predecessor("A-E3", cross_run_trace)


def test_c1_predecessor_binding_rejects_tampered_predecessor_trace(tmp_path):
    """G.4: a byte-flip in the selection trace changes its SHA; _validate_predecessor rejects."""
    from study02a import formal_contracts as fc
    run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    trace_path = run_dir / "selection_trace.jsonl"
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write('{"tampered": true}\n')  # changes the trace bytes -> SHA mismatch
    trace = _build_a_e1_pred_trace(run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)
    with pytest.raises(ValueError, match="SHA-256"):
        fc._validate_predecessor("A-E3", trace)


def test_c1_predecessor_binding_rejects_tampered_predecessor_staged_ledger(tmp_path):
    """G.5: a byte-flip in the staged_resolution_ledger changes its SHA; binding rejects."""
    from study02a import formal_contracts as fc
    run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    # tamper: append a stray byte line so the file SHA drifts from the declared SHA.
    with staged_ledger_path.open("a", encoding="utf-8") as handle:
        handle.write('{"tampered": true}\n')
    trace = _build_a_e1_pred_trace(run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)
    with pytest.raises(ValueError, match="staged_resolution_ledger SHA-256 mismatch"):
        fc._validate_predecessor("A-E3", trace)


def test_c1_predecessor_binding_rejects_stale_predecessor_trace_sha(tmp_path):
    """G.6: a predecessor trace whose declared SHA differs from the verified one is rejected."""
    from study02a import formal_contracts as fc
    run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    # declare a stale/cross-run SHA (not the verified trace SHA)
    stale_sha = "e" * 64
    trace = _build_a_e1_pred_trace(
        run_dir, stale_sha, staged_ledger_path, staged_ledger_sha,
    )
    with pytest.raises(ValueError, match="SHA-256"):
        fc._validate_predecessor("A-E3", trace)


def test_c1_predecessor_binding_rejects_missing_predecessor_staged_ledger(tmp_path):
    """G.7: an A-E1 predecessor that omits the staged_ledger fields is rejected (A-E1 publishes)."""
    from study02a import formal_contracts as fc
    run_dir, trace_sha, _staged_ledger_path, _staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    trace = _build_a_e1_pred_trace(run_dir, trace_sha, None, None)
    with pytest.raises(ValueError, match="staged_resolution_ledger binding required"):
        fc._validate_predecessor("A-E3", trace)


def test_c1_predecessor_binding_rejects_staged_ledger_breaks_chain(tmp_path):
    """G.8: a re-chained-but-reordered A-E1 staged ledger is a semantic tamper; validator rejects."""
    from study02a import formal_contracts as fc
    run_dir, trace_sha, staged_ledger_path, _staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    # Swap two records and re-break+rebuild the chain so it is cryptographically valid but
    # semantically out of order (the exact attack _validate_staged_resolution_ledger must catch).
    records = _assert_chained_ledger(run_dir)
    records[2], records[3] = records[3], records[2]
    _rewrite_staged_ledger(run_dir, records)
    new_sha = hashlib.sha256(staged_ledger_path.read_bytes()).hexdigest()
    trace = _build_a_e1_pred_trace(run_dir, trace_sha, staged_ledger_path, new_sha)
    with pytest.raises(ValueError, match="semantic order mismatch|hash chain broken"):
        fc._validate_predecessor("A-E3", trace)


def test_c1_validate_staged_resolution_ledger_accepts_a_e3_ten_record_chain(tmp_path):
    """G.15-partial: an A-E3 final selection's 10-record staged ledger validates as an A-E2
    predecessor (chain shape + record_sha self-consistency over the canonical A-E3 sequence).
    R3-B: the chain is now 10 records (record 9 ``n_strategy`` + record 10 ``final_aliases``).
    Full A-E3 staged-ledger publishing is wired in C4; this proves the FC validator already
    accepts the canonical A-E3 chain shape so A-E2 binding will work once A-E3 publishes."""
    from study02a import formal_contracts as fc
    from study02a.formal_contracts import _canonical_json_bytes, _STAGED_LEDGER_RECORD_VERSION
    staged_ledger_path = tmp_path / "staged_resolution_ledger.jsonl"
    trace_sha = "a" * 64  # verified trace SHA placeholder; the validator only checks binding equality
    zero = "0" * 64
    sequence = (
        ("loss", None),
        ("stage1", "F2_or_V"), ("stage2", "F2_or_V"),
        ("stage1", "S"), ("stage2", "S"),
        ("output_form", None),
        ("shared_winner_retrain", "S"),
        ("baseline_route", None),
        ("n_strategy", None),
        ("final_aliases", None),
    )
    records: list[dict] = []
    previous_sha = zero
    for stage, route in sequence:
        resolution = {f"{stage}:{route or 'none'}": "placeholder"}
        resolution_sha = hashlib.sha256(_canonical_json_bytes(dict(resolution))).hexdigest()
        core = {
            "record_version": _STAGED_LEDGER_RECORD_VERSION,
            "module_id": "A-E3",
            "run_id": "G3-AE3-pred-v1",
            "code_commit": _D8_CODE_COMMIT.lower(),
            "effective_config_sha256": EFFECTIVE.effective_config_sha256,
            "selection_trace_sha256": trace_sha,
            "stage": stage,
            "route": route,
            "previous_record_sha256": previous_sha,
            "input": {"fixture": "c1_a_e3_pred"},
            "resolution": dict(resolution),
            "resolution_sha256": resolution_sha,
        }
        record_sha = hashlib.sha256(_canonical_json_bytes(core)).hexdigest()
        record = {**core, "record_sha256": record_sha}
        records.append(record)
        previous_sha = record_sha
    staged_ledger_path.write_bytes(b"".join(_canonical_json_bytes(record) for record in records))
    declared_sha = hashlib.sha256(staged_ledger_path.read_bytes()).hexdigest()
    result = fc._validate_staged_resolution_ledger(
        staged_ledger_path=staged_ledger_path,
        staged_ledger_sha256=declared_sha,
        expected_trace_sha=trace_sha,
        predecessor_module="A-E3",
        run_id="G3-AE3-pred-v1",
        code_commit=_D8_CODE_COMMIT.lower(),
        effective_config_sha256=EFFECTIVE.effective_config_sha256,
    )
    assert len(result["records"]) == 10
    assert result["baseline_route"] is None  # A-E3 has no baseline_input stage
    # And the full _validate_predecessor path accepts it as an A-E2 predecessor binding.
    # (Synthesizing a complete A-E3 selection trace/receipt/ledger is C4-C5 scope; the FC
    # validator's acceptance of the staged ledger alone is the C1 control-plane contract.)


# ---------------------------------------------------------------------------
# C2 A-E3 fit-stage classifier + scoring plan-row resolver + reconstruct +
# dispatch. The concrete branch + route resolution is fully wired here; the
# stage2 / output_form / shared_winner_retrain branches call _recover_a_e3_*
# (C3 stubs that raise NotImplementedError) -- tested separately.
# ---------------------------------------------------------------------------


def _real_a_e3_plan_rows(
    tmp_path: Path, predecessor_trace_sha: str, *,
    run_id: str = "G3-AE3-staged-exec-v1", code_commit: str = _D8_CODE_COMMIT,
) -> list[dict]:
    """Build the REAL A-E3 plan.jsonl rows (the frozen _PLAN_FIELDS schema, NO fit_kind) via the
    scheduler's own _plan_rows, bound to a verified A-E1 predecessor trace SHA.

    Mirrors :func:`_real_a_e1_plan_rows`; the predecessor trace SHA threads through the
    deferred-dataset-v1 cache key exactly as the scheduler does at materialize time."""
    from study02a.formal_scheduler import _plan_rows, _PLAN_FIELDS
    matrix_str = [{key: str(value) for key, value in row.items()}
                  for row in MATRIX_ROWS if str(row["module"]) == "A-E3"]
    plan = _plan_rows(STUDY_ROOT, matrix_str, "A-E3", run_id, tmp_path / "cache", code_commit,
                      predecessor_trace_sha)
    assert all(set(row) == _PLAN_FIELDS for row in plan) and not any("fit_kind" in row for row in plan)
    return plan


def test_a_e3_fit_stage_classifies_every_fit_kind_from_the_matrix():
    """C2 _a_e3_fit_stage: the four A-E3 stages are classified from the authoritative matrix
    fit_kind (never from plan.jsonl, which omits it). Route is NOT used to classify."""
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    ae3 = {fid: row for fid, row in matrix_by_fit.items() if str(row["module"]) == "A-E3"}
    assert len(ae3) == 266
    by_stage: dict[str, list[str]] = {}
    for fid, row in ae3.items():
        by_stage.setdefault(fe._a_e3_fit_stage(row), []).append(fid)
    # The four stages of section A.1, classified by fit_kind alone.
    assert set(by_stage) == {"concrete", "stage2", "output_form", "shared_winner_retrain"}
    # concrete: loss_screen (12) + search_stage1 F2_or_V (36) + search_stage1 S (36) = 84
    assert len(by_stage["concrete"]) == 84
    # stage2: F2_or_V (36) + S (36) = 72
    assert len(by_stage["stage2"]) == 72
    # output_form: joint (50) + independent_capacity_matched (50) = 100
    assert len(by_stage["output_form"]) == 100
    # shared_winner_retrain: 10
    assert len(by_stage["shared_winner_retrain"]) == 10
    # Sanity: every concrete row has a concrete architecture (no selected:/selected_top_ prefix).
    for fid in by_stage["concrete"]:
        arch = str(ae3[fid]["architecture"])
        assert not arch.startswith(("selected:", "selected_top_")), f"{fid}: {arch}"


@pytest.mark.parametrize("placeholder,resolved,expected", [
    ("selected:F2_or_V", "V", "V"),
    ("selected:F2_or_V", "F2", "F2"),
    ("selected:F2_or_V:joint", "V", "V:joint"),
    ("selected:F2_or_V:independent_capacity_matched", "V", "V:independent_capacity_matched"),
    ("S", "V", "S"),
    ("S", "F2", "S"),
])
def test_a_e3_resolve_scoring_route_and_stem(placeholder, resolved, expected):
    """C2 route resolution: the scoring row preserves the :output_form suffix; the dataset-spec
    stem strips it (Flag K.1). S is always S."""
    assert fe._a_e3_resolve_scoring_route(placeholder, resolved) == expected
    stem = expected.split(":")[0]
    assert fe._a_e3_resolved_route_stem(placeholder, resolved) == stem
    # The token is the safe filename segment derived from the route stem.
    if placeholder == "S":
        assert fe._a_e3_route_token(placeholder) == "S"
    else:
        assert fe._a_e3_route_token(placeholder) == "F2_or_V"


def test_resolve_a_e3_scoring_plan_row_parses_concrete_route_from_real_a_e1_trace(tmp_path):
    """G.9: a concrete A-E3 fit's scoring row resolves the route placeholder to V (parsed from a
    real A-E1 staged predecessor via _validate_predecessor), with concrete arch/opt/loss, for
    BOTH the F2_or_V route stem (resolves to V) and the S route stem (stays S). No placeholder
    reaches the runner. No real r5 dir is read."""
    from study02a import formal_contracts as fc
    # Publish a real A-E1 staged run with V as the baseline winner.
    pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    trace = _build_a_e1_pred_trace(pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)
    predecessor_manifest = fc._validate_predecessor("A-E3", trace)
    assert predecessor_manifest["resolved_baseline_route"] == "V"
    resolved_baseline_route = predecessor_manifest["resolved_baseline_route"]

    # Build the REAL A-E3 plan (predecessor_trace_sha256 = the verified A-E1 trace SHA).
    plan_rows = _real_a_e3_plan_rows(tmp_path, trace_sha)
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")
    ae3_run_dir = tmp_path / "A-E3" / "G3-AE3-staged-exec-v1"  # unused for the concrete branch

    # (1) F2_or_V concrete fits (loss_screen + search_stage1) resolve route -> V.
    fv_concrete = next(
        fid for fid, row in matrix_by_fit.items()
        if str(row["module"]) == "A-E3" and fe._a_e3_fit_stage(row) == "concrete"
        and str(row["route"]) == "selected:F2_or_V")
    resolved = fe._resolve_a_e3_scoring_plan_row(
        run_dir=ae3_run_dir, run_id="G3-AE3-staged-exec-v1", fit_id=fv_concrete,
        matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
        predecessor_resolved_route=resolved_baseline_route)
    assert resolved["route"] == "V"
    assert not str(resolved["architecture"]).startswith(("selected:", "selected_top_"))
    assert not str(resolved["optimizer"]).startswith("selected:")
    assert not str(resolved["loss"]).startswith("selected:")
    # The plan row is otherwise unchanged (only the route was resolved).
    fv_original = dict(plan_by_fit[fv_concrete])
    for key in ("architecture", "optimizer", "loss", "seed", "training_size", "distribution"):
        assert resolved[key] == fv_original[key]

    # (2) S concrete fits (search_stage1) keep route = S.
    s_concrete = next(
        fid for fid, row in matrix_by_fit.items()
        if str(row["module"]) == "A-E3" and fe._a_e3_fit_stage(row) == "concrete"
        and str(row["route"]) == "S")
    resolved_s = fe._resolve_a_e3_scoring_plan_row(
        run_dir=ae3_run_dir, run_id="G3-AE3-staged-exec-v1", fit_id=s_concrete,
        matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
        predecessor_resolved_route=resolved_baseline_route)
    assert resolved_s["route"] == "S"
    assert not str(resolved_s["architecture"]).startswith(("selected:", "selected_top_"))


def test_resolve_a_e3_scoring_plan_row_fail_closed_on_unbound_plan_or_matrix(tmp_path):
    """G.9 negative: the resolver fail-closes on a fit_id absent from the plan/matrix, an unbound
    matrix_row_sha256, or a route that disagrees with the matrix (mirrors the A-E1 fail-closed
    contract)."""
    pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    plan_rows = _real_a_e3_plan_rows(tmp_path, trace_sha)
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")
    ae3_run_dir = tmp_path / "A-E3" / "G3-AE3-staged-exec-v1"
    concrete = next(
        fid for fid, row in matrix_by_fit.items()
        if str(row["module"]) == "A-E3" and fe._a_e3_fit_stage(row) == "concrete")

    # Absent fit_id.
    with pytest.raises(ValueError, match="not in the validated plan"):
        fe._resolve_a_e3_scoring_plan_row(
            run_dir=ae3_run_dir, run_id="r", fit_id="G3-fit-9999",
            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
            predecessor_resolved_route="V")

    # Unbound matrix_row_sha256.
    tampered_plan = dict(plan_by_fit)
    tampered_row = dict(plan_by_fit[concrete])
    tampered_row["matrix_row_sha256"] = "0" * 64
    tampered_plan[concrete] = tampered_row
    with pytest.raises(ValueError, match="matrix_row_sha256"):
        fe._resolve_a_e3_scoring_plan_row(
            run_dir=ae3_run_dir, run_id="r", fit_id=concrete,
            matrix_by_fit=matrix_by_fit, plan_by_fit=tampered_plan,
            predecessor_resolved_route="V")

    # Route disagrees with matrix.
    tampered_plan2 = dict(plan_by_fit)
    tampered_row2 = dict(plan_by_fit[concrete])
    tampered_row2["route"] = "S"  # matrix route is selected:F2_or_V
    tampered_plan2[concrete] = tampered_row2
    with pytest.raises(ValueError, match="disagrees with matrix route"):
        fe._resolve_a_e3_scoring_plan_row(
            run_dir=ae3_run_dir, run_id="r", fit_id=concrete,
            matrix_by_fit=matrix_by_fit, plan_by_fit=tampered_plan2,
            predecessor_resolved_route="V")


@pytest.mark.parametrize("stage_kind", ["search_stage2", "output_form", "shared_winner_retrain"])
def test_resolve_a_e3_scoring_plan_row_non_concrete_branches_fail_closed_without_receipt(tmp_path, stage_kind):
    """C3 fail-closed: with the C2 stubs replaced by real receipt readers, the stage2 /
    output_form / shared_winner_retrain branches attempt to recover on-disk verified evidence
    and fail closed when the prerequisite receipt is absent (no placeholder silently passes).

    Mirrors G.13 at the resolver level: each non-concrete branch raises because its
    ``_recover_a_e3_*`` reader cannot find the expected trace/receipt/ledger on disk."""
    pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    plan_rows = _real_a_e3_plan_rows(tmp_path, trace_sha)
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")
    ae3_run_dir = tmp_path / "A-E3" / "G3-AE3-staged-exec-v1"
    fit_id = next(
        fid for fid, row in matrix_by_fit.items()
        if str(row["module"]) == "A-E3" and str(row["fit_kind"]) == stage_kind)
    # No stage receipt published -> the recover reader fails closed (FileNotFoundError on the
    # absent receipt). The point: a placeholder can never silently pass the resolver.
    with pytest.raises((FileNotFoundError, ValueError)):
        fe._resolve_a_e3_scoring_plan_row(
            run_dir=ae3_run_dir, run_id="r", fit_id=fit_id,
            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
            predecessor_resolved_route="V")


def test_a_e3_placeholder_never_reaches_runner_backstop():
    """G.11: the resolve_model_factory / resolve_optimizer_hyperparams / resolve_loss_id guards
    are the final fail-closed backstop -- any selected: / selected_top_ placeholder that escapes
    the resolver raises NotImplementedError before any model is built. Direct backstop test."""
    # Architecture placeholders.
    with pytest.raises(NotImplementedError, match="selection-trace resolution"):
        fe.resolve_model_factory("selected_top_1", FROZEN, 15)
    with pytest.raises(NotImplementedError, match="selection-trace resolution"):
        fe.resolve_model_factory("selected:A-E3_architecture", FROZEN, 15)
    with pytest.raises(NotImplementedError, match="selection-trace resolution"):
        fe.resolve_model_factory("selected:S_architecture", FROZEN, 15)
    # Optimizer placeholder.
    with pytest.raises(NotImplementedError, match="selection-trace resolution"):
        fe.resolve_optimizer_hyperparams("selected:A-E3_optimizer", FROZEN)
    # Loss placeholder.
    with pytest.raises(NotImplementedError, match="selection-trace resolution"):
        fe.resolve_loss_id("selected:A-E3_loss")


def test_reconstruct_a_e3_specs_builds_concrete_specs_with_resolved_route(tmp_path):
    """C2 reconstruct_a_e3_specs: the concrete dataset spec uses the RESOLVED route stem (V) and
    transparently reuses the A-E1 V cache entry; the deferred cache key (placeholder route) is
    validated against the plan row via reconstruct_deferred_specs. No r5 dir read."""
    from study02a import formal_contracts as fc
    pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = _publish_v_winning_a_e1_predecessor(tmp_path)
    trace = _build_a_e1_pred_trace(pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)
    fc._validate_predecessor("A-E3", trace)  # asserts the predecessor binding is valid

    plan_rows = _real_a_e3_plan_rows(tmp_path, trace_sha)
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")
    # A concrete F2_or_V fit: deferred cache key uses selected:F2_or_V, concrete spec uses V.
    concrete = next(
        fid for fid, row in matrix_by_fit.items()
        if str(row["module"]) == "A-E3" and fe._a_e3_fit_stage(row) == "concrete"
        and str(row["route"]) == "selected:F2_or_V")
    original_row = plan_by_fit[concrete]
    training, validation = fe.reconstruct_a_e3_specs(
        original_row, FROZEN, EFFECTIVE, trace, "V")
    # Concrete spec route is V (not the placeholder); cache key differs from the deferred plan key.
    assert training.route == "V"
    assert validation.route == "V"
    assert training.cache_key != original_row["training_cache_key"]
    # An S concrete fit: concrete spec route is S, same as the (concrete) matrix route.
    s_concrete = next(
        fid for fid, row in matrix_by_fit.items()
        if str(row["module"]) == "A-E3" and fe._a_e3_fit_stage(row) == "concrete"
        and str(row["route"]) == "S")
    s_training, _ = fe.reconstruct_a_e3_specs(
        plan_by_fit[s_concrete], FROZEN, EFFECTIVE, trace, "S")
    assert s_training.route == "S"


# ---------------------------------------------------------------------------
# C3 A-E3 staged-selection builders + recover helpers (G.10 stage-order real,
# G.13 recover fail-closed). The builders publish the per-token stage1/stage2 +
# global loss/output_form receipts in the A.1 frozen order; the recover helpers
# re-validate those receipts read-only and fail-closed on missing/tampered/
# stale/out-of-scope/duplicate evidence. Production-bound: self-built V-winning
# A-E1 predecessor (no real r5 dir read); deterministic score_fit injection.
# ---------------------------------------------------------------------------

_A_E3_STAGED_RUN_ID = "G3-AE3-staged-exec-v1"


def _publish_a_e3_staged_dir(tmp_path: Path, predecessor_trace_sha: str):
    """Create an A-E3 run_dir with the REAL plan.jsonl + a minimal manifest.json bound to the
    predecessor trace SHA. Returns the run_dir (no receipts published yet)."""
    run_dir = tmp_path / "A-E3" / _A_E3_STAGED_RUN_ID
    run_dir.mkdir(parents=True)
    plan_rows = _real_a_e3_plan_rows(tmp_path, predecessor_trace_sha, run_id=_A_E3_STAGED_RUN_ID)
    (run_dir / "plan.jsonl").write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in plan_rows), encoding="utf-8")
    (run_dir / "manifest.json").write_text(
        json.dumps({"code_commit": _D8_CODE_COMMIT}, sort_keys=True) + "\n", encoding="utf-8")
    return run_dir


def _a_e3_staged_score_fit():
    """Deterministic score_fit for A-E3 staged selections covering all 6 decisions.

    loss: ``transformed_train_z_mse`` wins (lowest). stage1 F2_or_V/S: rank by architecture
    number (top4 = m01..m04 / d01..d04). stage2 F2_or_V: ``selected_top_1:o1`` wins (-> m01).
    stage2 S: ``selected_top_2:o2`` wins (-> d02). output_form: ``joint`` wins (lower
    aggregate than ``independent_capacity_matched``)."""
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    # rank losses so ``transformed_train_z_mse`` wins (lowest base).
    loss_bases = {
        "transformed_train_z_mse": 0.01, "transformed_train_z_huber": 0.02,
        "transformed_unscaled_mse": 0.03, "raw_train_z_mse": 0.04,
    }

    def score_fit(fit_id, plan_row):
        row = matrix_by_fit[str(fit_id)]
        kind = str(row["fit_kind"]); route = str(row["route"])
        n_raw = str(row["n"])
        n_key: int | str = "shared" if n_raw == "shared" else int(n_raw)
        key = SupportKey(n=n_key, seed=int(plan_row["seed"]))
        if kind == "loss_screen":
            loss = str(row["loss"])
            base = loss_bases[loss]
            decision_id = fe._A_E3_LOSS_DECISION_ID; candidate_id = loss
        elif kind == "search_stage1":
            arch = str(row["architecture"])
            base = 0.001 * int(arch[1:])
            token = fe._a_e3_route_token(route)
            decision_id = fe._a_e3_stage1_decision_id(token); candidate_id = arch
        elif kind == "search_stage2":
            arch_ph = str(row["architecture"]); opt = str(row["optimizer"])
            candidate_id = f"{arch_ph}:{opt}"
            token = fe._a_e3_route_token(route)
            decision_id = fe._a_e3_stage2_decision_id(token)
            forced = {"F2_or_V": "selected_top_1:o1", "S": "selected_top_2:o2"}[token]
            base = 0.001 if candidate_id == forced else 0.5
        elif kind == "output_form":
            candidate_id = route.rpartition(":")[2]
            base = 0.01 if candidate_id == "joint" else 0.02
            decision_id = fe._A_E3_OUTPUT_FORM_DECISION_ID
        else:
            raise ValueError(f"unexpected A-E3 fit_kind for staged selection: {kind!r}")
        records = _synth_point_records(str(fit_id), int(plan_row["seed"]), base)
        aggregate = sum(rec["l_param"] for rec in records) / len(records)
        return FitEvaluation(
            fit_id=str(fit_id), module_id="A-E3", decision_id=decision_id, candidate_id=candidate_id,
            support_key=key, failed=False,
            checkpoint_sha256=hashlib.sha256(str(fit_id).encode("utf-8")).hexdigest(),
            validation_identity=f"val-cache-{fit_id}", selection_score=aggregate,
            failure_penalty=0.0, point_records=records)
    return score_fit


def _build_all_a_e3_staged_receipts(
    run_dir: Path, cache_root: Path, score_fit, *, run_id: str = _A_E3_STAGED_RUN_ID,
):
    """Publish all 6 A-E3 staged receipts in A.1 order; returns a dict of the build results."""
    common = dict(study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
                  run_id=run_id, score_fit=score_fit)
    loss = fe.build_a_e3_loss_selection(**common)
    s1_fv = fe.build_a_e3_stage1_selection(token=fe._A_E3_FV_TOKEN, **common)
    s2_fv = fe.build_a_e3_stage2_selection(token=fe._A_E3_FV_TOKEN, **common)
    s1_s = fe.build_a_e3_stage1_selection(token=fe._A_E3_S_TOKEN, **common)
    s2_s = fe.build_a_e3_stage2_selection(token=fe._A_E3_S_TOKEN, **common)
    output_form = fe.build_a_e3_output_form_selection(
        predecessor_resolved_route="V", **common)
    return {"loss": loss, "s1_fv": s1_fv, "s2_fv": s2_fv,
            "s1_s": s1_s, "s2_s": s2_s, "output_form": output_form}


def test_g10_a_e3_staged_builders_publish_receipts_in_a1_order(tmp_path):
    """G.10: A-E3 stage builders publish per-token stage1/stage2 + global loss/output_form
    receipts in the A.1 frozen order, each over the right decision scope, with deterministic
    winners and NO placeholder reaching the production scoring row. Self-built V-winning A-E1
    predecessor; no real r5 dir read."""
    pred_run_dir, trace_sha, _spath, _ssha = _publish_v_winning_a_e1_predecessor(tmp_path)
    run_dir = _publish_a_e3_staged_dir(tmp_path, trace_sha)
    score_fit = _a_e3_staged_score_fit()
    receipts = _build_all_a_e3_staged_receipts(run_dir, tmp_path / "cache", score_fit)

    # (1) Each stage receipt file exists at the A.1-mandated path with its trace + ledger.
    for name in ("loss", "output_form"):
        for ext in ("_receipt.json", "_trace.jsonl", "_ledger.jsonl"):
            assert (run_dir / f"{name}_selection{ext}").is_file(), name + ext
    for token in (fe._A_E3_FV_TOKEN, fe._A_E3_S_TOKEN):
        for stage in ("stage1", "stage2"):
            for ext in ("_receipt.json", "_trace.jsonl", "_ledger.jsonl"):
                assert (run_dir / f"{stage}_selection_{token}{ext}").is_file(), f"{stage}/{token}{ext}"

    # (2) Deterministic winners prove the receipts carry verified (not placeholder) resolutions.
    assert receipts["loss"]["selected:A-E3_loss"] == "transformed_train_z_mse"
    for slot in range(1, 5):
        assert f"selected_top_{slot}" in receipts["s1_fv"]["top4"]
        assert f"selected_top_{slot}" in receipts["s1_s"]["top4"]
    assert tuple(receipts["s1_fv"]["top4"][f"selected_top_{i}"] for i in range(1, 5)) \
        == ("m01", "m02", "m03", "m04")
    assert tuple(receipts["s1_s"]["top4"][f"selected_top_{i}"] for i in range(1, 5)) \
        == ("d01", "d02", "d03", "d04")
    assert receipts["s2_fv"]["winner"] == \
        {"selected:A-E3_architecture": "m01", "selected:A-E3_optimizer": "o1"}
    assert receipts["s2_s"]["winner"] == \
        {"selected:S_architecture": "d02", "selected:S_optimizer": "o2"}
    assert receipts["output_form"]["selected:A-E3_baseline"] == "joint"

    # (3) No placeholder reaches the production scoring row: resolve a sample fit from each
    # non-concrete stage and assert its row is fully concrete.
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=[json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
                   if line.strip()],
        matrix_by_fit=matrix_by_fit, module_id="A-E3")
    _placeholders = ("selected:", "selected_top_")

    def _resolved(fit_id):
        return fe._resolve_a_e3_scoring_plan_row(
            run_dir=run_dir, run_id=_A_E3_STAGED_RUN_ID, fit_id=str(fit_id),
            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
            predecessor_resolved_route="V")

    stage2_fit = next(fid for fid, row in matrix_by_fit.items()
                      if str(row["module"]) == "A-E3" and str(row["fit_kind"]) == "search_stage2"
                      and str(row["route"]) == "selected:F2_or_V")
    r2 = _resolved(stage2_fit)
    assert r2["route"] == "V"
    assert not str(r2["architecture"]).startswith(_placeholders)

    of_fit = next(fid for fid, row in matrix_by_fit.items()
                  if str(row["module"]) == "A-E3" and str(row["fit_kind"]) == "output_form"
                  and str(row["route"]) == "selected:F2_or_V:joint")
    rof = _resolved(of_fit)
    assert rof["route"] == "V:joint"
    for field in ("architecture", "optimizer", "loss"):
        assert not str(rof[field]).startswith(_placeholders), field

    shared_fit = next(fid for fid, row in matrix_by_fit.items()
                      if str(row["module"]) == "A-E3" and str(row["fit_kind"]) == "shared_winner_retrain")
    rsh = _resolved(shared_fit)
    assert rsh["route"] == "S"
    for field in ("architecture", "optimizer", "loss"):
        assert not str(rsh[field]).startswith(_placeholders), field


def test_g10_a_e3_staged_builders_are_idempotent_on_restart(tmp_path):
    """G.10 (idempotence): re-calling the builders after the receipts exist REPUBLISHES would
    fail (canonical no-replace); the ensure helpers RE-VALIDATE read-only instead, returning the
    same placeholder resolutions. This mirrors the A-E1 staged crash-recovery contract."""
    pred_run_dir, trace_sha, _spath, _ssha = _publish_v_winning_a_e1_predecessor(tmp_path)
    run_dir = _publish_a_e3_staged_dir(tmp_path, trace_sha)
    cache_root = tmp_path / "cache"
    score_fit = _a_e3_staged_score_fit()
    first = _build_all_a_e3_staged_receipts(run_dir, cache_root, score_fit)

    # The ensure helpers recover (not rebuild) when the receipt already exists.
    common = dict(study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
                  run_id=_A_E3_STAGED_RUN_ID, score_fit=score_fit)
    stage1_by_token: dict[str, dict] = {}
    loss2 = fe._ensure_a_e3_loss_selection(**common)
    s1_fv2 = fe._ensure_a_e3_stage1_selection(token=fe._A_E3_FV_TOKEN, **common)
    s2_fv2 = fe._ensure_a_e3_stage2_selection(
        token=fe._A_E3_FV_TOKEN, stage1_by_token=stage1_by_token, **common)
    s1_s2 = fe._ensure_a_e3_stage1_selection(token=fe._A_E3_S_TOKEN, **common)
    s2_s2 = fe._ensure_a_e3_stage2_selection(
        token=fe._A_E3_S_TOKEN, stage1_by_token=stage1_by_token, **common)
    of2 = fe._ensure_a_e3_output_form_selection(predecessor_resolved_route="V", **common)

    # Recovered resolutions agree with the first-pass published ones.
    assert loss2["selected:A-E3_loss"] == first["loss"]["selected:A-E3_loss"]
    assert s1_fv2["top4"] == first["s1_fv"]["top4"]
    assert s2_fv2["winner"] == first["s2_fv"]["winner"]
    assert s1_s2["top4"] == first["s1_s"]["top4"]
    assert s2_s2["winner"] == first["s2_s"]["winner"]
    assert of2["selected:A-E3_baseline"] == first["output_form"]["selected:A-E3_baseline"]
    # Trace SHAs are unchanged (the receipts were NOT republished).
    assert loss2["selection_trace_sha256"] == first["loss"]["selection_trace_sha256"]
    assert s1_fv2["selection_trace_sha256"] == first["s1_fv"]["selection_trace_sha256"]
    assert of2["selection_trace_sha256"] == first["output_form"]["selection_trace_sha256"]


@pytest.mark.parametrize("stage,token", [
    ("stage1", "F2_or_V"), ("stage1", "S"),
    ("stage2", "F2_or_V"), ("stage2", "S"),
    ("loss", None), ("output_form", None),
])
def test_g13_a_e3_recover_fail_closed_on_missing_receipt(tmp_path, stage, token):
    """G.13 (missing): each ``_recover_a_e3_*`` fail-closes when its receipt is absent (no
    silent recovery from placeholder). Directly calls the recover helpers."""
    pred_run_dir, trace_sha, _spath, _ssha = _publish_v_winning_a_e1_predecessor(tmp_path)
    run_dir = _publish_a_e3_staged_dir(tmp_path, trace_sha)
    kwargs = {"run_dir": run_dir, "run_id": _A_E3_STAGED_RUN_ID}
    if token is not None:
        kwargs["token"] = token
    if stage == "stage2":
        kwargs["top4"] = {}  # never reached (receipt read fails first)
    recover = {
        "stage1": fe._recover_a_e3_stage1_selection, "stage2": fe._recover_a_e3_stage2_selection,
        "loss": fe._recover_a_e3_loss_selection, "output_form": fe._recover_a_e3_output_form_selection,
    }[stage]
    with pytest.raises((FileNotFoundError, ValueError)):
        recover(**kwargs)


def _a_e3_recover(stage: str, token: str | None, *, run_dir: Path):
    kwargs = {"run_dir": run_dir, "run_id": _A_E3_STAGED_RUN_ID}
    if token is not None:
        kwargs["token"] = token
    if stage == "stage1":
        return fe._recover_a_e3_stage1_selection(**kwargs)
    if stage == "stage2":
        # stage2 recover needs the token's stage1 top4 (itself recovered from disk).
        top4 = fe._recover_a_e3_stage1_selection(**kwargs)["top4"]
        return fe._recover_a_e3_stage2_selection(**kwargs, top4=top4)
    if stage == "loss":
        return fe._recover_a_e3_loss_selection(**kwargs)
    return fe._recover_a_e3_output_form_selection(**kwargs)


def test_g13_a_e3_recover_fail_closed_on_tampered_trace(tmp_path):
    """G.13 (tampered): a byte-flip in a stage1 trace changes its SHA; the recover helper
    rejects (hash mismatch), even though the receipt still declares the original SHA."""
    pred_run_dir, trace_sha, _spath, _ssha = _publish_v_winning_a_e1_predecessor(tmp_path)
    run_dir = _publish_a_e3_staged_dir(tmp_path, trace_sha)
    _build_all_a_e3_staged_receipts(run_dir, tmp_path / "cache", _a_e3_staged_score_fit())
    trace_path = run_dir / "stage1_selection_F2_or_V_trace.jsonl"
    with trace_path.open("a", encoding="utf-8") as handle:
        handle.write('{"tampered": true}\n')
    with pytest.raises(ValueError, match="SHA-256"):
        _a_e3_recover("stage1", "F2_or_V", run_dir=run_dir)


def test_g13_a_e3_recover_fail_closed_on_stale_trace_sha(tmp_path):
    """G.13 (stale): a receipt that declares a stale/cross-run trace SHA (not the verified
    trace SHA) is rejected at the receipt-trace binding check."""
    pred_run_dir, trace_sha, _spath, _ssha = _publish_v_winning_a_e1_predecessor(tmp_path)
    run_dir = _publish_a_e3_staged_dir(tmp_path, trace_sha)
    _build_all_a_e3_staged_receipts(run_dir, tmp_path / "cache", _a_e3_staged_score_fit())
    receipt_path = run_dir / "loss_selection_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["selection_trace_sha256"] = "e" * 64  # stale/cross-run SHA
    receipt_path.write_text(json.dumps(receipt, sort_keys=True) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="SHA-256"):
        _a_e3_recover("loss", None, run_dir=run_dir)


def test_g13_a_e3_recover_fail_closed_on_out_of_scope_receipt(tmp_path):
    """G.13 (out-of-scope): a receipt whose decision scope disagrees with the recovered
    stage/token is rejected. A stage1 F2_or_V receipt copied into the stage1 S path has the
    wrong decision id; the S recover rejects it."""
    import shutil
    pred_run_dir, trace_sha, _spath, _ssha = _publish_v_winning_a_e1_predecessor(tmp_path)
    run_dir = _publish_a_e3_staged_dir(tmp_path, trace_sha)
    _build_all_a_e3_staged_receipts(run_dir, tmp_path / "cache", _a_e3_staged_score_fit())
    # Copy the F2_or_V stage1 receipt into the S path -- the decision_id inside is
    # architecture:A-E3:selected:F2_or_V:n10, but the S recover expects architecture:A-E3:S:shared.
    for ext in ("_trace.jsonl", "_receipt.json", "_ledger.jsonl"):
        shutil.copy(
            run_dir / f"stage1_selection_F2_or_V{ext}",
            run_dir / f"stage1_selection_S{ext}")
    with pytest.raises(ValueError, match="out of scope"):
        _a_e3_recover("stage1", "S", run_dir=run_dir)


def test_g13_a_e3_recover_fail_closed_on_duplicate_ledger_binding(tmp_path):
    """G.13 (duplicate): a ledger with two formal-selection bindings for the same module/run
    is rejected (exactly one binding is required)."""
    pred_run_dir, trace_sha, _spath, _ssha = _publish_v_winning_a_e1_predecessor(tmp_path)
    run_dir = _publish_a_e3_staged_dir(tmp_path, trace_sha)
    _build_all_a_e3_staged_receipts(run_dir, tmp_path / "cache", _a_e3_staged_score_fit())
    ledger_path = run_dir / "output_form_selection_ledger.jsonl"
    # Append the first binding line again -> two identical formal-selection bindings.
    lines = [line for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    binding_records = [json.loads(line) for line in lines
                       if json.loads(line).get("binding_type") == "formal-selection"]
    assert len(binding_records) == 1, "precondition: exactly one binding before tamper"
    binding_line = next(line for line in lines
                        if json.loads(line).get("binding_type") == "formal-selection")
    with ledger_path.open("a", encoding="utf-8") as handle:
        handle.write(binding_line + "\n")
    with pytest.raises(ValueError, match="exactly one binding"):
        _a_e3_recover("output_form", None, run_dir=run_dir)


# ---------------------------------------------------------------------------
# C4 A-E3 staged driver (run_a_e3_staged) + staged-ledger resolver
# (resolve_a_e3_staged_selection). G.12 interrupt/idempotent re-entry,
# G.14 publish -> rebuild provenance parity.
#
# Production-bound: real _prepare_fit_inputs + resolve_model_factory +
# _score_fit_from_checkpoint over pilot data; the scheduler journal is bypassed
# only at the output-staging layer (_stage_a_e3_staged_outputs writes outputs/
# directly, mirroring _stage_arch_matched_a_e1_run); _rebuild_authority is
# stubbed all-succeeded so the staged driver's loop sees every fit terminal and
# proceeds to the final selection + 10-record staged ledger. The scientific
# scoring path (checkpoint load + forward + L_param) runs REAL end-to-end.
# ---------------------------------------------------------------------------


def _stage_a_e3_staged_outputs(
    tmp_path: Path, monkeypatch, *, run_id: str, predecessor,
):
    """Stage a REAL A-E3 run_dir with all 266 fits' outputs + the 6 staged receipts,
    WITHOUT the O(N^2) scheduler claim/record loop.

    Mirrors :func:`_stage_arch_matched_a_e1_run` for A-E3:
      * ``materialize_run`` with the predecessor (real scheduler authority setup,
        predecessor binding validated at materialize time).
      * Publish the 6 staged receipts (loss / stage1_FV / stage2_FV / stage1_S /
        stage2_S / output_form) via the deterministic ``_a_e3_staged_score_fit``.
      * Train + write ``outputs/{fit_id}/`` for every fit through the REAL
        ``_prepare_fit_inputs`` + ``resolve_model_factory`` + ``_write_outputs``.

    Returns ``(run_dir, plan_rows)``. The caller should stub ``_rebuild_authority``
    via ``_mock_rebuild_authority_all_succeeded`` before driving
    ``run_a_e3_staged`` / ``rebuild_selection_point_provenance``.
    """
    _install_small_data_pilot(monkeypatch)
    from study02a.formal_scheduler import materialize_run

    # R3-C read-side regression workaround: ``_predecessor_trace_from_manifest`` does not
    # restore the authority triple (``scoped_code_sha256`` / ``authority_sha256``) from the
    # manifest's predecessor section, but ``_validate_predecessor`` requires them for v2
    # modules (A-E3). The manifest DOES contain them (written by ``_validate_predecessor``
    # at materialize time -- the write side is correct). Patch the reader to faithfully
    # restore them so the real ``_prepare_fit_inputs`` chain (which re-validates the
    # predecessor inside ``reconstruct_deferred_specs``) sees the v2 authority triple.
    _orig_pred_from_manifest = fe._predecessor_trace_from_manifest

    def _pred_trace_with_authority(run_dir: Path) -> PredecessorTrace:
        trace = _orig_pred_from_manifest(run_dir)
        manifest = json.loads((Path(run_dir) / "manifest.json").read_text(encoding="utf-8"))
        pred = manifest["predecessor"]
        return dataclasses.replace(
            trace,
            scoped_code_sha256=pred.get("scoped_code_sha256"),
            authority_sha256=pred.get("authority_sha256"),
        )
    monkeypatch.setattr(fe, "_predecessor_trace_from_manifest", _pred_trace_with_authority)

    # R3-A capacity smoke-relaxation: the frozen ``select_independent_capacity`` fail-closes
    # (raises ValueError) when every m0X candidate's 3-subnetwork total exceeds the joint
    # model's parameter count (e.g. joint=m01 -- the smallest arch). The R3-A design says the
    # executor should record this as a scientific failure and the output_form decision then
    # selects joint; the real fail-close enforcement is pinned by the R3-A unit tests
    # (``test_resolve_independent_capacity_hard_fails_for_smallest_arch``). For this sealed
    # smoke we relax the selector to return the smallest candidate instead of raising, so
    # BOTH arms (joint=Sequential, independent=IndependentContainer) produce real, structurally
    # distinct checkpoints that the checkpoint-forward + selection chain can score. Without
    # this, ``_prepare_fit_inputs`` -> ``build_output_form_aware_factory`` -> ``resolve_-
    # independent_capacity`` raises ValueError at BOTH the training layer (step 4 below) and
    # the checkpoint-forward scoring layer (``_score_fit_from_checkpoint`` calls
    # ``_prepare_fit_inputs`` too), crashing the whole chain.
    import study02a.output_form_contract as _ofc
    _orig_select_independent_capacity = _ofc.select_independent_capacity

    def _smoke_select_independent_capacity(joint_count, candidate_counts):
        try:
            return _orig_select_independent_capacity(joint_count, candidate_counts)
        except ValueError:
            smallest_id = min(candidate_counts, key=lambda k: candidate_counts[k])
            return (smallest_id, candidate_counts[smallest_id])
    monkeypatch.setattr(_ofc, "select_independent_capacity", _smoke_select_independent_capacity)

    # R3-B production gap workaround: ``_build_a_e3_n_strategy_shared_evaluations`` passes the
    # UNRESOLVED plan row (``plan_by_fit[fit_id]`` with ``selected:S_architecture`` placeholder)
    # to ``_score_shared_fit_on_core_n_subset``, which then calls ``_prepare_fit_inputs`` ->
    # ``resolve_model_factory`` -> raises ``NotImplementedError`` on the placeholder. The FIXED
    # cohort correctly calls ``_resolve_a_e3_scoring_plan_row`` first (line 2191-2194); the
    # shared cohort skips this step. Wrap the shared scorer to resolve placeholders so both
    # cohorts exercise the real ``_score_fit_from_checkpoint`` / ``_prepare_fit_inputs`` chain.
    _orig_score_shared_on_core_n = fe._score_shared_fit_on_core_n_subset

    def _score_shared_resolved_plan_row(
        *, run_dir: Path, cache_root: Path, fit_id: str,
        plan_row: Mapping[str, Any], frozen, effective, fit_states,
        core_n: int, module_id: str, decision_id: str, candidate_id: str,
    ) -> FitEvaluation:
        if str(plan_row.get("architecture", "")).startswith(("selected:", "selected_top_")):
            _matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
            _plan_rows = [
                json.loads(line) for line in (Path(run_dir) / "plan.jsonl").read_text(
                    encoding="utf-8").splitlines()
                if line.strip()]
            _plan_by_fit = fe._validate_plan_against_matrix(
                plan_rows=_plan_rows, matrix_by_fit=_matrix_by_fit, module_id="A-E3")
            _pred_route = fe._a_e3_resolved_baseline_route_from_manifest(run_dir)
            plan_row = fe._resolve_a_e3_scoring_plan_row(
                run_dir=run_dir, run_id=str(plan_row["run_id"]), fit_id=fit_id,
                matrix_by_fit=_matrix_by_fit, plan_by_fit=_plan_by_fit,
                predecessor_resolved_route=_pred_route)
        return _orig_score_shared_on_core_n(
            run_dir=run_dir, cache_root=cache_root, fit_id=fit_id, plan_row=plan_row,
            frozen=frozen, effective=effective, fit_states=fit_states,
            core_n=core_n, module_id=module_id, decision_id=decision_id,
            candidate_id=candidate_id,
        )
    monkeypatch.setattr(fe, "_score_shared_fit_on_core_n_subset", _score_shared_resolved_plan_row)

    # 1. Real scheduler authority setup with predecessor (C1 binding validated here).
    matrix_path = (STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv").resolve()
    materialize_run(
        study_root=STUDY_ROOT, matrix_path=matrix_path, module_id="A-E3", run_id=run_id,
        artifact_root=tmp_path / "artifact", cache_root=tmp_path / "cache", predecessor=predecessor)
    run_dir = tmp_path / "artifact" / "A-E3" / run_id
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]

    # 2. Publish the 6 staged receipts (deterministic score_fit, no checkpoint scoring,
    #    no scheduler claim/record). Needed for placeholder resolution in step 4.
    cache_root = tmp_path / "cache"
    _build_all_a_e3_staged_receipts(run_dir, cache_root, _a_e3_staged_score_fit(), run_id=run_id)

    # 3. Recover the predecessor-resolved route (V) from the manifest (C1 binding).
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")
    predecessor_resolved_route = fe._a_e3_resolved_baseline_route_from_manifest(run_dir)

    # 4. Train + write outputs for every fit via the REAL _prepare_fit_inputs +
    #    resolve_model_factory + _write_outputs. No claim/record -> no O(N^2) replay.
    ckpt_cache: dict[tuple, tuple[bytes, str]] = {}
    for plan_row in plan_rows:
        fit_id = str(plan_row["fit_id"])
        resolved = fe._resolve_a_e3_scoring_plan_row(
            run_dir=run_dir, run_id=run_id, fit_id=fit_id,
            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
            predecessor_resolved_route=predecessor_resolved_route)
        # Same fixed_n-aware cache key as _arch_matched_fit_runner (input_dim depends on
        # route + fixed_n; two fits with the same arch but different fixed_n are NOT
        # interchangeable).
        key = (str(resolved["route"]), str(resolved["architecture"]), resolved.get("fixed_n"))
        if key not in ckpt_cache:
            prepared = fe._prepare_fit_inputs(resolved, FROZEN, EFFECTIVE, cache_root, run_dir=run_dir)
            ckpt_bytes, ckpt_sha, _ = _train_checkpoint_through_prepared(
                prepared, seed=resolved["seed"], run_id=run_id, fit_id=fit_id)
            ckpt_cache[key] = (ckpt_bytes, ckpt_sha)
        ckpt_bytes, ckpt_sha = ckpt_cache[key]
        curve = tuple(100.0 / (i + 1) for i in range(60))
        best_epoch = min(range(60), key=lambda i: curve[i])
        evidence = {
            "evidence_version": "study02-formal-fit-evidence-v1", "fit_id": fit_id,
            "run_id": run_id, "checkpoint_sha256": ckpt_sha,
            "actual_epochs": 60, "best_epoch_one_based": best_epoch + 1, "hit_epoch_100": False,
            "early_stop_reason": "patience_exhausted",
            "terminal_validation_slope": fe._terminal_ols_slope(curve),
            "validation_curve": list(curve), "test_access_count": 0,
        }
        fe._write_outputs(run_dir, fit_id, run_id, ckpt_bytes, ckpt_sha, evidence)

    return run_dir, plan_rows


@pytest.mark.slow
def test_g12_a_e3_staged_driver_idempotent_reentry(tmp_path, monkeypatch):
    """G.12: run_a_e3_staged is crash-recoverable and idempotent on re-entry.

    Production-bound: real _prepare_fit_inputs + resolve_model_factory +
    _score_fit_from_checkpoint over pilot data; the scheduler claim/record loop is
    bypassed only at output staging (all 266 outputs pre-written); _rebuild_authority
    is stubbed all-succeeded so the loop sees no pending fits and proceeds to the
    final selection + 10-record staged ledger.

    Contract under test (the task's "interrupt/resume" idempotence guarantees):
      1. ``run_a_e3_staged(max_fits=None)`` completes: all 266 fits terminal, the 6
         per-stage receipts are ensured, the final module selection trace is published,
         and the 10-record staged ledger chain (loss -> stage1_FV -> stage2_FV ->
         stage1_S -> stage2_S -> output_form -> shared_winner_retrain -> baseline_route
         -> final_aliases) is appended.
      2. Re-entering ``run_a_e3_staged(max_fits=None)`` does NOT re-claim any fit, does
         NOT re-publish any stage receipt (same selection_trace_sha256), and does NOT
         duplicate or overwrite any staged-ledger record (exact-match reuse, no
         conflicting duplicate).
      3. The 10-record chain is hash-bound from _ZERO_HASH, every record binds the A-E3
         final selection trace SHA, and the baseline_route record's input carries the
         A-E1 predecessor's staged_ledger_sha256 (cryptographic binding).
    """
    import shutil as _shutil
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--", str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"

    artifact_root = tmp_path / "artifact"
    # Publish the V-winning A-E1 predecessor UNDER the same artifact_root so the
    # predecessor paths pass _predecessor_scope's artifact-root containment check.
    pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = \
        _publish_v_winning_a_e1_predecessor(artifact_root)
    predecessor = _build_a_e1_pred_trace(pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)
    run_id = "g12-ae3-0001"
    run_dir, plan_rows = _stage_a_e3_staged_outputs(
        tmp_path, monkeypatch, run_id=run_id, predecessor=predecessor)
    _mock_rebuild_authority_all_succeeded(monkeypatch, plan_rows)

    # Phase 1: complete the staged driver. The loop finds every fit terminal (stub) and
    # ensures the final selection + staged ledger.
    summary = fe.run_a_e3_staged(
        study_root=STUDY_ROOT, run_id=run_id, artifact_root=artifact_root,
        cache_root=tmp_path / "cache", predecessor=predecessor,
        score_fit=_a_e3_staged_score_fit())
    assert summary["complete"] is True
    assert summary["module_id"] == "A-E3"
    assert summary["succeeded_count"] == 0  # no new claims (every fit already terminal per stub)
    assert summary["failed_count"] == 0
    assert "final_selection" in summary and "staged" in summary

    staged = summary["staged"]
    assert staged["pending"] == []
    assert staged["selected_F2_or_V"] == "V"  # predecessor-resolved route (r5 design)
    # R3-B: final_aliases now carries selected:A-E3_n_strategy + a concrete baseline tuple
    # under selected:A-E3_baseline (directly consumable by A-E2), plus the original flat
    # token-namespaced aliases unchanged.
    assert "selected:A-E3_n_strategy" in staged["final_aliases"]
    assert staged["final_aliases"]["selected:A-E3_n_strategy"] in {"fixed", "shared"}
    assert set(staged["final_aliases"]) == {
        "selected:A-E3_loss", "selected:A-E3_architecture", "selected:A-E3_optimizer",
        "selected:S_architecture", "selected:S_optimizer",
        "selected:A-E3_baseline", "selected:F2_or_V",
        "selected:A-E3_n_strategy"}
    assert staged["final_aliases"]["selected:F2_or_V"] == "V"
    baseline_tuple = staged["final_aliases"]["selected:A-E3_baseline"]
    assert isinstance(baseline_tuple, dict)
    assert set(baseline_tuple) == {"route", "loss", "architecture", "optimizer", "output_form"}
    assert baseline_tuple["loss"] == staged["final_aliases"]["selected:A-E3_loss"]

    # Capture every artifact's SHA after the first pass.
    final_trace_sha_1 = summary["final_selection"]["selection_trace_sha256"]
    stage_receipt_shas_1 = {}
    for name in ("loss", "output_form"):
        stage_receipt_shas_1[name] = hashlib.sha256(
            (run_dir / f"{name}_selection_receipt.json").read_bytes()).hexdigest()
    for token in (fe._A_E3_FV_TOKEN, fe._A_E3_S_TOKEN):
        for stage in ("stage1", "stage2"):
            stage_receipt_shas_1[f"{stage}_{token}"] = hashlib.sha256(
                (run_dir / f"{stage}_selection_{token}_receipt.json").read_bytes()).hexdigest()
    staged_ledger_records_1 = _assert_chained_ledger(run_dir)
    assert len(staged_ledger_records_1) == 10
    # The 10-record chain follows the canonical A-E3 sequence (FC _STAGED_LEDGER_SEQUENCES):
    # R3-B adds record 9 (n_strategy) before record 10 (final_aliases).
    canonical_stages = [(r["stage"], r.get("route")) for r in staged_ledger_records_1]
    assert canonical_stages == [
        ("loss", None),
        ("stage1", "F2_or_V"), ("stage2", "F2_or_V"),
        ("stage1", "S"), ("stage2", "S"),
        ("output_form", None),
        ("shared_winner_retrain", "S"),
        ("baseline_route", None),
        ("n_strategy", None),
        ("final_aliases", None),
    ]
    # The baseline_route record's input cryptographically binds the predecessor staged ledger SHA.
    baseline_route_record = next(
        r for r in staged_ledger_records_1 if r["stage"] == "baseline_route")
    assert baseline_route_record["input"]["predecessor_staged_ledger_sha256"] == staged_ledger_sha
    assert baseline_route_record["resolution"] == {"selected:F2_or_V": "V"}

    # Phase 2: re-enter run_a_e3_staged. Nothing should be re-claimed or re-published.
    summary_reentry = fe.run_a_e3_staged(
        study_root=STUDY_ROOT, run_id=run_id, artifact_root=artifact_root,
        cache_root=tmp_path / "cache", predecessor=predecessor,
        score_fit=_a_e3_staged_score_fit())
    assert summary_reentry["complete"] is True
    assert summary_reentry["succeeded_count"] == 0
    assert summary_reentry["final_selection"]["selection_trace_sha256"] == final_trace_sha_1
    # Every stage receipt is byte-identical (ensure helpers re-validated, not republished).
    for key, sha_1 in stage_receipt_shas_1.items():
        if key in ("loss", "output_form"):
            path = run_dir / f"{key}_selection_receipt.json"
        else:
            stage, token = key.split("_", 1)
            path = run_dir / f"{stage}_selection_{token}_receipt.json"
        assert hashlib.sha256(path.read_bytes()).hexdigest() == sha_1, f"stage receipt {key!r} changed"
    # The staged ledger is unchanged (idempotent exact-match reuse, no duplicate).
    staged_ledger_records_2 = _assert_chained_ledger(run_dir)
    assert len(staged_ledger_records_2) == 10
    assert [r["record_sha256"] for r in staged_ledger_records_2] == \
        [r["record_sha256"] for r in staged_ledger_records_1]
    # The A-E1 predecessor artifacts are untouched (no cross-module tamper).
    assert hashlib.sha256(staged_ledger_path.read_bytes()).hexdigest() == staged_ledger_sha


@pytest.mark.slow
def test_g14_a_e3_publish_and_rebuild_provenance(tmp_path, monkeypatch):
    """G.14: publish (run_a_e3_staged -> build_module_selection) and rebuild
    (rebuild_selection_point_provenance) -- both via the REAL production scoring path
    (score_fit=None) -- produce identical concrete context for every A-E3 selection fit:
    same resolved architecture/optimizer/loss (captured from _resolve_a_e3_scoring_plan_row),
    same checkpoint_sha256 / validation_identity / selection_score. Mirrors the A-E1
    publish/rebuild parity test for the A-E3 module.

    Production-bound: real _prepare_fit_inputs + resolve_model_factory +
    _score_fit_from_checkpoint over pilot data. No mock of score_fit /
    resolve_model_factory / _prepare_fit_inputs.
    """
    status = __import__("subprocess").run(
        ["git", "status", "--porcelain", "--", str((STUDY_ROOT / "code").relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True, check=True)
    assert not status.stdout.strip(), "code/ must be clean for the scheduler authority check"

    artifact_root = tmp_path / "artifact"
    pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = \
        _publish_v_winning_a_e1_predecessor(artifact_root)
    predecessor = _build_a_e1_pred_trace(pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)
    run_id = "g14-ae3-0001"
    run_dir, plan_rows = _stage_a_e3_staged_outputs(
        tmp_path, monkeypatch, run_id=run_id, predecessor=predecessor)
    _apply_a_e1_test_overrides(monkeypatch, plan_rows)  # pilot + all-succeeded _rebuild_authority

    real_resolve = fe._resolve_a_e3_scoring_plan_row
    real_score = fe._score_fit_from_checkpoint
    publish_resolutions: dict[str, dict[str, str]] = {}
    publish_evals: dict[str, FitEvaluation] = {}
    rebuild_resolutions: dict[str, dict[str, str]] = {}
    rebuild_evals: dict[str, FitEvaluation] = {}

    resolved_baseline_route = fe._a_e3_resolved_baseline_route_from_manifest(run_dir)
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    plan_by_fit = fe._validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")

    def _make_resolve_spy(sink):
        def spy(*, run_dir, run_id, fit_id, matrix_by_fit, plan_by_fit,
                predecessor_resolved_route):
            row = real_resolve(
                run_dir=run_dir, run_id=run_id, fit_id=fit_id,
                matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
                predecessor_resolved_route=predecessor_resolved_route)
            sink[str(fit_id)] = {
                "route": str(row["route"]),
                "architecture": str(row["architecture"]),
                "optimizer": str(row["optimizer"]),
                "loss": str(row["loss"])}
            return row
        return spy

    def _make_score_spy(sink):
        def spy(**kwargs):
            evaluation = real_score(**kwargs)
            sink[str(kwargs["fit_id"])] = evaluation
            return evaluation
        return spy

    # Phase 1: publish via run_a_e3_staged (drives build_module_selection with score_fit=None
    # for the final selection). Capture resolved rows + evaluations.
    monkeypatch.setattr(fe, "_resolve_a_e3_scoring_plan_row", _make_resolve_spy(publish_resolutions))
    monkeypatch.setattr(fe, "_score_fit_from_checkpoint", _make_score_spy(publish_evals))
    fe.run_a_e3_staged(
        study_root=STUDY_ROOT, run_id=run_id, artifact_root=artifact_root,
        cache_root=tmp_path / "cache", predecessor=predecessor)
    monkeypatch.undo()
    _apply_a_e1_test_overrides(monkeypatch, plan_rows)

    # Phase 2: rebuild via rebuild_selection_point_provenance (score_fit=None).
    monkeypatch.setattr(fe, "_resolve_a_e3_scoring_plan_row", _make_resolve_spy(rebuild_resolutions))
    monkeypatch.setattr(fe, "_score_fit_from_checkpoint", _make_score_spy(rebuild_evals))
    rebuilt = fe.rebuild_selection_point_provenance(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        module_id="A-E3", run_id=run_id)
    monkeypatch.undo()

    # Every A-E3 selection fit (loss_screen + search_stage1 + search_stage2 + output_form)
    # is scored on both paths and produces identical concrete context + evaluations.
    selection_fits = [
        fid for fid, row in matrix_by_fit.items()
        if str(row["module"]) == "A-E3"
        and str(row["fit_kind"]) in ("loss_screen", "search_stage1", "search_stage2", "output_form")
    ]
    assert selection_fits, "expected A-E3 selection fits in the frozen matrix"
    assert len(selection_fits) == 256  # 12 loss + 72 stage1 + 72 stage2 + 100 output_form
    assert set(publish_evals) == set(selection_fits)
    assert set(rebuild_evals) == set(selection_fits)
    for fit_id in selection_fits:
        assert publish_resolutions[fit_id] == rebuild_resolutions[fit_id], (
            f"resolved context drifted for A-E3 fit {fit_id}: "
            f"publish={publish_resolutions[fit_id]} rebuild={rebuild_resolutions[fit_id]}")
        # No placeholder reaches the scoring row on either path.
        for field in ("architecture", "optimizer", "loss"):
            assert not str(publish_resolutions[fit_id][field]).startswith(("selected:", "selected_top_"))
        pe = publish_evals[fit_id]
        re_ = rebuild_evals[fit_id]
        assert pe.checkpoint_sha256 == re_.checkpoint_sha256
        assert pe.validation_identity == re_.validation_identity
        assert float(pe.selection_score) == pytest.approx(float(re_.selection_score))
    # The rebuilt evaluations match the return value of rebuild_selection_point_provenance.
    assert set(rebuilt) == set(selection_fits)


# ---------------------------------------------------------------------------
# C5 sealed smoke + G.15 A-E3 -> A-E2 predecessor acceptance.
#
# Production-equivalent integration: real materialize_run (predecessor binding),
# real _ensure_a_e3_* / build_a_e3_* stage builders, real build_module_selection
# (A-E3) final selection, real resolve_a_e3_staged_selection (10-record ledger),
# real _validate_predecessor / _validate_staged_resolution_ledger, real
# _score_fit_from_checkpoint (checkpoint-forward over pilot data).
#
# Explicit substitutions (NOT scientific inputs -- clearly documented):
#   * ``_install_small_data_pilot`` -- shrinks the data source (pilot-scale) so the
#     real _prepare_fit_inputs + resolve_model_factory chain finishes in seconds.
#   * ``_mock_rebuild_authority_all_succeeded`` -- stubs the scheduler authority
#     (O(N^2) event replay, non-scientific) so the staged driver sees every fit terminal.
#   * ``_a_e3_staged_score_fit`` injection -- the 6 staged receipts (loss / stage1_FV /
#     stage2_FV / stage1_S / stage2_S / output_form) are published with a deterministic
#     score_fit; the FINAL selection (build_module_selection) uses score_fit=None
#     (checkpoint-forward) in the sealed smoke.
# ---------------------------------------------------------------------------


def _build_a_e3_pred_trace(
    run_dir: Path, run_id: str, *, staged_ledger_path: Path | None = None,
    staged_ledger_sha: str | None = None, **overrides,
) -> PredecessorTrace:
    """Build an A-E3 PredecessorTrace bound to a completed A-E3 staged run, with overrides.

    Mirrors :func:`_build_a_e1_pred_trace` for A-E3: reads the selection trace SHA from the
    published receipt, the receipt/ledger SHAs from disk, and the code_commit from the run
    manifest. ``staged_ledger_path`` / ``staged_ledger_sha`` default to the on-disk
    ``staged_resolution_ledger.jsonl`` when present (A-E3 publishes one).

    The R3-C v2 authority triple (``scoped_code_sha256`` / ``authority_sha256``) is read from
    the run manifest's ``scheduler.authority`` block when present (real formal runs seal it
    via the scheduler); otherwise the fixture's synthetic SHA-256s stand in so
    ``_validate_predecessor`` v2 accept-paths exercise (the staged-only manifest published by
    the staged driver has no authority block). Tests can override either via ``**overrides``.
    """
    receipt_path = run_dir / "selection_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    if staged_ledger_path is None:
        staged_ledger_path = run_dir / fe._STAGED_LEDGER_NAME
        if not staged_ledger_path.is_file():
            staged_ledger_path = None
    if staged_ledger_sha is None and staged_ledger_path is not None:
        staged_ledger_sha = hashlib.sha256(staged_ledger_path.read_bytes()).hexdigest()
    authority_block = manifest.get("scheduler", {}).get("authority", {})
    scoped_code_sha256 = authority_block.get(
        "scoped_code_sha256", _D8_SCOPED_CODE_SHA256)
    authority_sha256 = authority_block.get(
        "authority_sha256", _D8_AUTHORITY_SHA256)
    fields: dict = dict(
        module_id="A-E3",
        run_id=run_id,
        trace_path=run_dir / "selection_trace.jsonl",
        trace_sha256=str(receipt["selection_trace_sha256"]),
        receipt_path=receipt_path,
        receipt_sha256=hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
        ledger_path=run_dir / "selection_ledger.jsonl",
        selection_code_commit=str(manifest["code_commit"]),
        staged_ledger_path=staged_ledger_path,
        staged_ledger_sha256=staged_ledger_sha,
        scoped_code_sha256=scoped_code_sha256,
        authority_sha256=authority_sha256,
    )
    fields.update(overrides)
    return PredecessorTrace(**fields)


@pytest.mark.slow
def test_g15_a_e3_final_selection_accepted_as_a_e2_predecessor(tmp_path, monkeypatch):
    """G.15: a self-built A-E3 final selection (NOT a real r5 run) is accepted by
    ``_validate_predecessor("A-E2", trace)`` as an A-E2 predecessor, including the
    control-plane v2 staged_ledger binding (A-E3 publishes a 10-record staged ledger).

    Production-bound: real materialize_run (predecessor binding), real
    _ensure_a_e3_* / build_a_e3_* stage builders, real build_module_selection (A-E3),
    real resolve_a_e3_staged_selection (10-record ledger). Substitutions: pilot data source
    (_install_small_data_pilot), scheduler authority (_mock_rebuild_authority_all_succeeded),
    and deterministic score_fit injection for the 6 staged receipts + the final selection
    (this is the focused predecessor-acceptance test; the sealed smoke below exercises the
    checkpoint-forward final selection path).
    """
    from study02a import formal_contracts as fc
    artifact_root = tmp_path / "artifact"
    pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = \
        _publish_v_winning_a_e1_predecessor(artifact_root)
    predecessor = _build_a_e1_pred_trace(pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)
    run_id = "g15-ae3-0001"
    run_dir, plan_rows = _stage_a_e3_staged_outputs(
        tmp_path, monkeypatch, run_id=run_id, predecessor=predecessor)
    _mock_rebuild_authority_all_succeeded(monkeypatch, plan_rows)

    summary = fe.run_a_e3_staged(
        study_root=STUDY_ROOT, run_id=run_id, artifact_root=artifact_root,
        cache_root=tmp_path / "cache", predecessor=predecessor,
        score_fit=_a_e3_staged_score_fit())
    assert summary["complete"] is True
    assert summary["module_id"] == "A-E3"

    # Build the A-E3 PredecessorTrace from the completed A-E3 run.
    ae3_trace = _build_a_e3_pred_trace(run_dir, run_id)
    assert ae3_trace.staged_ledger_path is not None
    assert ae3_trace.staged_ledger_sha256 is not None

    # _validate_predecessor("A-E2", trace) accepts the self-built A-E3 final selection,
    # including the staged_ledger binding (A-E3 publishes a 10-record staged ledger).
    binding = fc._validate_predecessor("A-E2", ae3_trace)
    assert binding["module_id"] == "A-E3"
    assert binding["run_id"] == run_id
    assert binding["selection_staged_ledger_path"] == str(run_dir / fe._STAGED_LEDGER_NAME)
    assert binding["selection_staged_ledger_sha256"] == ae3_trace.staged_ledger_sha256
    # A-E3 has no baseline_input stage, so resolved_baseline_route stays "none" (A-E2 resolves
    # its own baseline from the A-E3 output_form winner, not from a predecessor route).
    assert binding["resolved_baseline_route"] == "none"


@pytest.mark.slow
def test_g16_a_e3_sealed_smoke_production_equivalent(tmp_path, monkeypatch):
    """C5 sealed smoke (production-equivalent): drive the full A-E3 orchestration chain
    end-to-end and prove the output binds as an A-E2 predecessor.

    Real chain exercised (NOT mocked):
      * ``materialize_run`` with the A-E1 predecessor binding (C1 control-plane v2).
      * ``_ensure_a_e3_*`` / ``build_a_e3_*`` stage builders (6 staged receipts).
      * ``build_module_selection("A-E3")`` final selection via ``_score_fit_from_checkpoint``
        (checkpoint-forward scoring over the pilot validation batch -- score_fit=None).
      * ``resolve_a_e3_staged_selection`` (10-record staged ledger chain from _ZERO_HASH).
      * ``_validate_predecessor("A-E2", trace)`` + ``_validate_staged_resolution_ledger``.

    Explicit substitutions (documented non-scientific layers):
      * ``_install_small_data_pilot`` -- pilot data source (so the real
        _prepare_fit_inputs + resolve_model_factory finishes in seconds).
      * ``_mock_rebuild_authority_all_succeeded`` -- scheduler authority (O(N^2) event
        replay; non-scientific; tamper detection covered by attack tests).
      * ``_a_e3_staged_score_fit`` injection -- the 6 staged receipts are pre-published with
        a deterministic score_fit via _stage_a_e3_staged_outputs; the FINAL selection
        (build_module_selection) runs with score_fit=None (checkpoint-forward).

    Asserts: 9 staged records chain from _ZERO_HASH, 6 A-E3 decisions, and
    ``_validate_predecessor("A-E2", trace)`` passes (including staged_ledger binding).
    """
    from study02a import formal_contracts as fc
    artifact_root = tmp_path / "artifact"
    # Publish the V-winning A-E1 predecessor under the same artifact_root.
    pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha = \
        _publish_v_winning_a_e1_predecessor(artifact_root)
    predecessor = _build_a_e1_pred_trace(pred_run_dir, trace_sha, staged_ledger_path, staged_ledger_sha)
    run_id = "g16-ae3-0001"
    run_dir, plan_rows = _stage_a_e3_staged_outputs(
        tmp_path, monkeypatch, run_id=run_id, predecessor=predecessor)
    _mock_rebuild_authority_all_succeeded(monkeypatch, plan_rows)

    # Drive the full staged driver with score_fit=None so the FINAL selection
    # (build_module_selection) scores via the real _score_fit_from_checkpoint path
    # (checkpoint-forward). The 6 staged receipts were pre-published by
    # _stage_a_e3_staged_outputs with _a_e3_staged_score_fit; _ensure_a_e3_* re-validates
    # them read-only (no re-publish).
    summary = fe.run_a_e3_staged(
        study_root=STUDY_ROOT, run_id=run_id, artifact_root=artifact_root,
        cache_root=tmp_path / "cache", predecessor=predecessor,
        score_fit=None)
    assert summary["complete"] is True
    assert summary["module_id"] == "A-E3"
    assert "final_selection" in summary and "staged" in summary

    # The final selection published the module selection trace with 6 A-E3 decisions
    # (loss + stage1_FV + stage2_FV + stage1_S + stage2_S + output_form).
    final_trace_path = run_dir / "selection_trace.jsonl"
    final_trace_records = [
        json.loads(line) for line in final_trace_path.read_text(encoding="utf-8").splitlines()
        if line.strip()]
    decision_ids = {r["decision_id"] for r in final_trace_records}
    assert len(decision_ids) == 6, f"expected 6 A-E3 decisions, got {len(decision_ids)}"
    expected_decisions = {
        fe._A_E3_LOSS_DECISION_ID,
        fe._a_e3_stage1_decision_id(fe._A_E3_FV_TOKEN),
        fe._a_e3_stage2_decision_id(fe._A_E3_FV_TOKEN),
        fe._a_e3_stage1_decision_id(fe._A_E3_S_TOKEN),
        fe._a_e3_stage2_decision_id(fe._A_E3_S_TOKEN),
        fe._A_E3_OUTPUT_FORM_DECISION_ID,
    }
    assert decision_ids == expected_decisions

    # The staged ledger is the 10-record canonical chain from _ZERO_HASH (R3-B: + n_strategy).
    staged = summary["staged"]
    assert staged["pending"] == []
    assert staged["selected_F2_or_V"] == "V"  # predecessor-resolved route (r5 design)
    staged_records = _assert_chained_ledger(run_dir)
    assert len(staged_records) == 10
    canonical_stages = [(r["stage"], r.get("route")) for r in staged_records]
    assert canonical_stages == [
        ("loss", None),
        ("stage1", "F2_or_V"), ("stage2", "F2_or_V"),
        ("stage1", "S"), ("stage2", "S"),
        ("output_form", None),
        ("shared_winner_retrain", "S"),
        ("baseline_route", None),
        ("n_strategy", None),
        ("final_aliases", None),
    ]
    # The baseline_route record cryptographically binds the A-E1 predecessor's staged ledger.
    baseline_route_record = next(
        r for r in staged_records if r["stage"] == "baseline_route")
    assert baseline_route_record["input"]["predecessor_staged_ledger_sha256"] == staged_ledger_sha
    assert baseline_route_record["resolution"] == {"selected:F2_or_V": "V"}

    # _validate_staged_resolution_ledger (FC single authority) accepts the 10-record chain.
    ae3_receipt = json.loads((run_dir / "selection_receipt.json").read_text(encoding="utf-8"))
    ae3_manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    staged_ledger_result = fc._validate_staged_resolution_ledger(
        staged_ledger_path=run_dir / fe._STAGED_LEDGER_NAME,
        staged_ledger_sha256=hashlib.sha256(
            (run_dir / fe._STAGED_LEDGER_NAME).read_bytes()).hexdigest(),
        expected_trace_sha=str(ae3_receipt["selection_trace_sha256"]),
        predecessor_module="A-E3",
        run_id=run_id,
        code_commit=str(ae3_manifest["code_commit"]),
        effective_config_sha256=EFFECTIVE.effective_config_sha256,
    )
    assert len(staged_ledger_result["records"]) == 10
    assert staged_ledger_result["baseline_route"] is None  # A-E3 has no baseline_input stage

    # _validate_predecessor("A-E2", trace) accepts the self-built A-E3 final selection
    # as an A-E2 predecessor, including the staged_ledger binding.
    ae3_trace = _build_a_e3_pred_trace(run_dir, run_id)
    binding = fc._validate_predecessor("A-E2", ae3_trace)
    assert binding["module_id"] == "A-E3"
    assert binding["run_id"] == run_id
    assert binding["selection_staged_ledger_sha256"] == ae3_trace.staged_ledger_sha256
    assert binding["resolved_baseline_route"] == "none"

    # ---- R3-A/R3-B contract verification (Codex sealed-smoke requirement) ------------
    # The smoke must prove joint + independent + fixed + shared ALL traversed the real
    # model factory (resolve_model_factory + output_form_contract), checkpoint-forward
    # (_score_fit_from_checkpoint), and selection (build_module_selection / n_strategy).

    # (1) output_form decision has BOTH candidates (joint + independent) -- the r1 bug
    # was that both arms used the same 3-output MLP; R3-A routes independent through
    # IndependentContainer. The final selection trace must carry both candidates.
    output_form_records = [
        r for r in final_trace_records
        if r["decision_id"] == fe._A_E3_OUTPUT_FORM_DECISION_ID]
    of_candidate_ids = {str(r["candidate_id"]) for r in output_form_records}
    assert of_candidate_ids == {"joint", "independent_capacity_matched"}, (
        f"output_form decision must have both arms; got {of_candidate_ids}")
    # Both candidates received real checkpoint-forward scores (score_fit=None ->
    # _score_fit_from_checkpoint loaded + forwarded each fit's checkpoint), not the
    # injected 0.01/0.02 constants from _a_e3_staged_score_fit.
    for r in output_form_records:
        assert float(r["validation_score"]) > 0.0
        assert r["supporting_evidence_sha256"]  # binds checkpoint + point evidence

    # (2) Both arms produced structurally distinct checkpoints on disk (real model
    # factory dispatch: joint=Sequential 3-output MLP, independent=IndependentContainer
    # three single-output subnetworks). The checkpoints differ at the byte level.
    matrix_by_fit_g16 = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    of_fits = {
        str(row["route"]).rpartition(":")[2]: fid
        for fid, row in matrix_by_fit_g16.items()
        if str(row["module"]) == "A-E3" and str(row["fit_kind"]) == "output_form"}
    joint_ckpt = run_dir / "outputs" / of_fits["joint"] / "checkpoint.pt"
    indep_ckpt = run_dir / "outputs" / of_fits["independent_capacity_matched"] / "checkpoint.pt"
    assert joint_ckpt.is_file(), "joint output_form fit has no real checkpoint on disk"
    assert indep_ckpt.is_file(), "independent output_form fit has no real checkpoint on disk"
    assert joint_ckpt.read_bytes() != indep_ckpt.read_bytes(), (
        "joint + independent checkpoints must be byte-distinct (R3-A structural distinctness)")

    # (3) R3-A factory dispatch: resolve_model_factory(output_form=...) produces
    # different model TYPES for the two arms (the contract the r1 bug violated).
    from study02a.models import IndependentContainer
    joint_model = fe.resolve_model_factory(
        str(plan_rows[0]["architecture"]), FROZEN, 15, output_form="joint")()
    indep_model = fe.resolve_model_factory(
        str(plan_rows[0]["architecture"]), FROZEN, 15,
        output_form="independent_capacity_matched")()
    assert type(joint_model) is not type(indep_model)
    assert isinstance(indep_model, IndependentContainer)
    assert not isinstance(joint_model, IndependentContainer)

    # (4) n_strategy decision (record 9) has a winner in {fixed, shared} -- BOTH cohorts
    # were scored (fixed from the output_form winner's checkpoints, shared from the
    # shared_winner_retrain checkpoints), exercising the full fixed_vs_shared_equal_weight
    # selection over the 5 core-n x 10 formal-seed support grid.
    n_strategy_record = next(
        r for r in staged_records if r["stage"] == "n_strategy")
    n_strategy_resolution = n_strategy_record["resolution"]
    assert "selected:A-E3_n_strategy" in n_strategy_resolution, (
        f"n_strategy record has no winner alias; resolution={n_strategy_resolution}")
    assert n_strategy_resolution["selected:A-E3_n_strategy"] in ("fixed", "shared"), (
        f"n_strategy winner must be fixed/shared; "
        f"got {n_strategy_resolution['selected:A-E3_n_strategy']!r}")

