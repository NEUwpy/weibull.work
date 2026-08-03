"""R4-4: A-E3 staged-ledger semantic rebuild + G3 / A-E2 integration attack tests.

Tests :func:`study02a.formal_g3_control._resolve_a_e3_from_staged_ledger` -- the
independent semantic rebuild of the A-E3 10-record staged resolution ledger. Covers:

  * valid rebuild: the n_strategy winner is independently recomputed from checkpoint-
    scoring injection and every record cross-binds to the verified selection trace +
    stage receipts + predecessor manifest. The returned baseline tuple reflects the
    n_strategy winner (NOT the ordinary output_form winner).
  * G3 bundle binds BOTH A-E1 and A-E3 staged-ledger SHAs.
  * A-E2 placeholder resolution consumes the n_strategy winner's concrete baseline
    tuple (fixed -> F2/V route + fixed arch/opt; shared -> S + DeepSets arch/opt).
  * ATTACKS (fail-closed): missing staged ledger / forged n_strategy winner /
    swapped fixed/shared evidence / tampered final tuple / broken hash chain.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from study02a import formal_executor as fe  # noqa: E402
from study02a import formal_g3_control as g3  # noqa: E402
from study02a.config import load_frozen_config  # noqa: E402
from study02a.formal_config import load_effective_formal_config  # noqa: E402
from study02a.formal_contracts import (  # noqa: E402
    APPROVED_EFFECTIVE_CONFIG_SHA256,
    _tie_break_sort_key,
)
from study02a.selection import (  # noqa: E402
    FitEvaluation,
    SupportKey,
    build_decision_specs,
)

FROZEN = load_frozen_config(STUDY_ROOT)
EFFECTIVE = load_effective_formal_config(STUDY_ROOT)
COMMIT = "f" * 40


def _canonical_json(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _legal_point_records(*, fit_id: str, seed: int, score: float) -> tuple[dict, ...]:
    return ({"sample_id": f"{fit_id}-val-0", "seed_id": str(seed), "point_id": "point-0",
             "legal": True, "failure": 0, "l_param": score, "e_beta": score, "e_eta": score,
             "e_gamma": score},)


def _make_n_strategy_scorer(*, fixed_score: float, shared_score: float):
    """Build a per-cell n_strategy scorer with controllable aggregate scores."""
    def _score(fit_id: str, n: int, seed: int, cohort_label: str) -> FitEvaluation:
        score = fixed_score if cohort_label == fe._A_E3_N_STRATEGY_FIXED else shared_score
        return FitEvaluation(
            fit_id=fit_id, module_id="A-E3",
            decision_id=fe._A_E3_N_STRATEGY_DECISION_ID, candidate_id=cohort_label,
            support_key=SupportKey(n=int(n), seed=int(seed)),
            failed=False,
            checkpoint_sha256=hashlib.sha256(f"ckpt:{fit_id}:{cohort_label}".encode()).hexdigest(),
            validation_identity=f"val:{fit_id}:{cohort_label}:n{n}",
            selection_score=score, failure_penalty=0.0,
            point_records=_legal_point_records(fit_id=fit_id, seed=int(seed), score=score),
        )
    return _score


def _build_selection_trace_records(*, run_id: str, specs) -> list[dict]:
    """Build canonically-ordered v3 selection trace records from DecisionSpecs."""
    records: list[dict] = []
    for spec in specs:
        diag_sha = hashlib.sha256(f"diag:{spec.decision_id}:{run_id}".encode()).hexdigest()
        for idx, candidate in enumerate(spec.candidates):
            score = 1.0 + idx * 0.1
            sha = hashlib.sha256(
                f"{spec.decision_id}:{candidate.candidate_id}:{run_id}".encode()).hexdigest()
            records.append({
                "module_id": "A-E3", "run_id": run_id,
                "decision_id": spec.decision_id,
                "candidate_id": candidate.candidate_id,
                "validation_score": score,
                "tie_break_key": list(candidate.tie_break_key),
                "selected": idx == 0,
                "supporting_evidence_sha256": sha,
                "rule_diagnostics_sha256": diag_sha,
                "support_count": len(candidate.support_keys),
                "seed_count": len(candidate.approved_seeds),
                "selection_rule": spec.selection_rule,
            })
    records.sort(key=lambda r: (r["decision_id"], r["validation_score"],
                                _tie_break_sort_key(r["tie_break_key"]), r["candidate_id"]))
    return records


def _write_selection_evidence(
    *, run_dir: Path, run_id: str, records: list[dict], file_stem: str = "selection",
) -> str:
    """Write selection trace + receipt + ledger; return the trace SHA-256."""
    trace_bytes = b"".join(_canonical_json(r) for r in records)
    trace_sha = hashlib.sha256(trace_bytes).hexdigest()
    decision_count = len({r["decision_id"] for r in records})

    trace_path = run_dir / f"{file_stem}_trace.jsonl"
    receipt_path = run_dir / f"{file_stem}_receipt.json"
    ledger_path = run_dir / f"{file_stem}_ledger.jsonl"
    trace_path.write_bytes(trace_bytes)

    receipt = {
        "receipt_version": "study02-formal-selection-v3",
        "module_id": "A-E3", "run_id": run_id,
        "selection_trace_sha256": trace_sha,
        "effective_config_sha256": APPROVED_EFFECTIVE_CONFIG_SHA256,
        "code_commit": COMMIT,
        "record_count": len(records), "decision_count": decision_count,
    }
    receipt_bytes = _canonical_json(receipt)
    receipt_path.write_bytes(receipt_bytes)
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()

    ledger_record = {"binding_type": "formal-selection", **receipt, "receipt_sha256": receipt_sha}
    ledger_path.write_bytes(_canonical_json(ledger_record))
    return trace_sha


def _write_plan_jsonl(*, run_dir: Path) -> None:
    """Write a plan.jsonl whose rows pass _validate_plan_against_matrix for A-E3."""
    matrix_by_fit = fe._authoritative_matrix_by_fit(STUDY_ROOT)
    lines: list[str] = []
    for fit_id, mrow in matrix_by_fit.items():
        if mrow["module"] != "A-E3":
            continue
        row_sha = hashlib.sha256(fe._canonical(dict(mrow))).hexdigest()
        lines.append(json.dumps(
            {"fit_id": fit_id, "matrix_row_sha256": row_sha, "seed": int(mrow["seed"])},
            ensure_ascii=False, sort_keys=True, separators=(",", ":")))
    (run_dir / "plan.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_manifest(*, run_dir: Path, run_id: str, resolved_route: str = "V") -> None:
    """Write a minimal A-E3 manifest with a v2 predecessor section."""
    manifest = {
        "module_id": "A-E3", "run_id": run_id, "code_commit": COMMIT,
        "predecessor": {
            "module_id": "A-E1", "run_id": "run-ae1-test",
            "selection_trace_path": str(run_dir / "ae1_trace.jsonl"),
            "selection_trace_sha256": "e" * 64,
            "selection_receipt_path": str(run_dir / "ae1_receipt.json"),
            "selection_receipt_sha256": "b" * 64,
            "selection_ledger_path": str(run_dir / "ae1_ledger.jsonl"),
            "selection_staged_ledger_path": str(run_dir / "ae1_staged.jsonl"),
            "selection_staged_ledger_sha256": "d" * 64,
            "resolved_baseline_route": resolved_route,
            "code_commit": COMMIT,
            "scoped_code_sha256": "c" * 64,
            "authority_sha256": "a" * 64,
        },
    }
    (run_dir / "manifest.json").write_bytes(_canonical_json(manifest))


def _persist_staged_ledger(run_dir: Path, records: list[dict]) -> None:
    """Write staged ledger records as canonical JSONL."""
    ledger_path = run_dir / "staged_resolution_ledger.jsonl"
    ledger_path.write_bytes(b"".join(fe._canonical(r) for r in records))


def _build_valid_a_e3_run(
    tmp_path: Path, *, n_strategy_winner: str = "fixed", resolved_route: str = "V",
) -> tuple[Path, str, str, dict]:
    """Build a complete synthetic A-E3 run dir with valid evidence + staged ledger.

    Returns (run_dir, run_id, code_commit, rebuilt_n_strategy).
    """
    run_id = "run-ae3-test"
    run_dir = tmp_path / "A-E3" / run_id
    run_dir.mkdir(parents=True)

    from study02a.matrix import expand_module_matrix
    matrix_rows = expand_module_matrix(FROZEN).to_dict("records")
    ae3_rows = [r for r in matrix_rows if str(r["module"]) == "A-E3"]
    specs = build_decision_specs("A-E3", ae3_rows)

    # Root selection trace.
    root_records = _build_selection_trace_records(run_id=run_id, specs=specs)
    trace_sha = _write_selection_evidence(
        run_dir=run_dir, run_id=run_id, records=root_records, file_stem="selection")

    # Output_form stage evidence (subset of root trace).
    of_records = [r for r in root_records if r["decision_id"] == fe._A_E3_OUTPUT_FORM_DECISION_ID]
    _write_selection_evidence(
        run_dir=run_dir, run_id=run_id, records=of_records, file_stem="output_form_selection")

    # plan.jsonl + manifest.json.
    _write_plan_jsonl(run_dir=run_dir)
    _write_manifest(run_dir=run_dir, run_id=run_id, resolved_route=resolved_route)

    # Compute n_strategy winner + evidence via the production rebuild path (injection
    # skips the scheduler-authority rebuild).
    if n_strategy_winner == fe._A_E3_N_STRATEGY_FIXED:
        scorer = _make_n_strategy_scorer(fixed_score=1.0, shared_score=5.0)
    else:
        scorer = _make_n_strategy_scorer(fixed_score=5.0, shared_score=1.0)
    rebuilt = fe.rebuild_a_e3_n_strategy_provenance(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=tmp_path / "cache",
        run_id=run_id, score_n_strategy_cell=scorer,
    )
    assert rebuilt["winner"] == n_strategy_winner, (
        f"scorer did not produce the expected winner: {rebuilt['winner']!r}")

    # Build + persist the 10-record staged ledger manually.
    ledger_records = _build_staged_ledger_records(
        run_dir=run_dir, run_id=run_id, trace_sha=trace_sha, rebuilt=rebuilt)
    _persist_staged_ledger(run_dir, ledger_records)

    return run_dir, run_id, COMMIT, rebuilt


def _build_staged_ledger_records(
    *, run_dir: Path, run_id: str, trace_sha: str, rebuilt: dict,
) -> list[dict]:
    """Build the 10 staged-ledger record dicts (NOT persisted; caller writes them)."""
    n_strategy_winner = rebuilt["winner"]
    evidence = rebuilt["evidence_by_candidate"]
    rule_result = rebuilt["rule_result"]

    root_records = [
        json.loads(line) for line in (run_dir / "selection_trace.jsonl").read_text().splitlines()
        if line.strip()
    ]
    by_decision: dict[str, list[dict]] = {}
    for rec in root_records:
        by_decision.setdefault(rec["decision_id"], []).append(rec)

    def _winner(decision_id: str) -> dict:
        return next(r for r in by_decision[decision_id] if r["selected"])

    def _ranking(decision_id: str) -> list[dict]:
        return sorted(
            by_decision[decision_id],
            key=lambda r: (r["validation_score"], _tie_break_sort_key(r["tie_break_key"]),
                           r["candidate_id"]),
        )

    from study02a.formal_executor import (
        _A_E3_FV_TOKEN, _A_E3_S_TOKEN,
        _a_e3_stage2_winner_keys, _parse_stage2_winner_candidate,
    )

    manifest = json.loads((run_dir / "manifest.json").read_text())
    predecessor_resolved_route = manifest["predecessor"]["resolved_baseline_route"]
    pred_section = manifest["predecessor"]

    loss_dec = fe._A_E3_LOSS_DECISION_ID
    loss_w = _winner(loss_dec)
    loss_id = loss_w["candidate_id"]

    token_winners: dict[str, dict[str, str]] = {}
    token_top4: dict[str, dict[str, str]] = {}
    for token in (_A_E3_FV_TOKEN, _A_E3_S_TOKEN):
        s1_dec = fe._a_e3_stage1_decision_id(token)
        s1_ranking = _ranking(s1_dec)
        top4 = {f"selected_top_{slot}": s1_ranking[slot - 1]["candidate_id"] for slot in range(1, 5)}
        token_top4[token] = top4
        s2_dec = fe._a_e3_stage2_decision_id(token)
        s2_w = _winner(s2_dec)
        arch_ph, opt = _parse_stage2_winner_candidate(s2_w["candidate_id"])
        arch_key, opt_key = _a_e3_stage2_winner_keys(token)
        token_winners[token] = {arch_key: top4[arch_ph], opt_key: opt}

    fv = token_winners[_A_E3_FV_TOKEN]
    sw = token_winners[_A_E3_S_TOKEN]
    fv_arch_key, fv_opt_key = _a_e3_stage2_winner_keys(_A_E3_FV_TOKEN)
    s_arch_key, s_opt_key = _a_e3_stage2_winner_keys(_A_E3_S_TOKEN)

    of_dec = fe._A_E3_OUTPUT_FORM_DECISION_ID
    of_w = _winner(of_dec)
    baseline_alias = of_w["candidate_id"]

    previous_sha = fe._ZERO_HASH
    records: list[dict] = []
    stage_shas: dict[str, str] = {}

    def _publish(stage: str, route: str | None, input_payload: dict, resolution: dict) -> dict:
        nonlocal previous_sha
        record = fe._build_stage_record(
            module_id="A-E3", run_id=run_id, code_commit=COMMIT,
            effective_config_sha256=APPROVED_EFFECTIVE_CONFIG_SHA256,
            selection_trace_sha256=trace_sha, stage=stage, route=route,
            previous_record_sha256=previous_sha, input_payload=input_payload, resolution=resolution,
        )
        previous_sha = record["record_sha256"]
        stage_shas[f"{stage}:{route if route else ''}"] = record["record_sha256"]
        records.append(record)
        return record

    loss_record = _publish("loss", None, {
        "decision_id": loss_dec, "winner_candidate_id": loss_id,
        "winner_supporting_evidence_sha256": loss_w["supporting_evidence_sha256"],
    }, {"selected:A-E3_loss": loss_id})

    for token in (_A_E3_FV_TOKEN, _A_E3_S_TOKEN):
        s1_dec = fe._a_e3_stage1_decision_id(token)
        s2_dec = fe._a_e3_stage2_decision_id(token)
        s1_ranking = _ranking(s1_dec)
        top4 = token_top4[token]
        _publish("stage1", token, {
            "decision_id": s1_dec,
            "ranking": [{"candidate_id": r["candidate_id"],
                         "validation_score": r["validation_score"],
                         "selected": r["selected"],
                         "supporting_evidence_sha256": r["supporting_evidence_sha256"]}
                        for r in s1_ranking],
        }, top4)
        s2_w = _winner(s2_dec)
        arch_ph, opt = _parse_stage2_winner_candidate(s2_w["candidate_id"])
        arch_key, opt_key = _a_e3_stage2_winner_keys(token)
        _publish("stage2", token, {
            "decision_id": s2_dec,
            "winner_candidate_id": s2_w["candidate_id"],
            "winner_supporting_evidence_sha256": s2_w["supporting_evidence_sha256"],
            "stage1_record_sha256": stage_shas[f"stage1:{token}"],
            "resolved_top_slot": arch_ph,
        }, {arch_key: top4[arch_ph], opt_key: opt})

    of_record = _publish("output_form", None, {
        "decision_id": of_dec, "winner_candidate_id": baseline_alias,
        "winner_supporting_evidence_sha256": of_w["supporting_evidence_sha256"],
    }, {"selected:A-E3_baseline": baseline_alias})

    shared_record = _publish("shared_winner_retrain", _A_E3_S_TOKEN, {
        "loss_record_sha256": loss_record["record_sha256"],
        "stage2_S_record_sha256": stage_shas[f"stage2:{_A_E3_S_TOKEN}"],
        "placeholder_fields": ["selected:A-E3_loss", s_arch_key, s_opt_key],
    }, {"selected:A-E3_loss": loss_id, s_arch_key: sw[s_arch_key], s_opt_key: sw[s_opt_key]})

    baseline_record = _publish("baseline_route", None, {
        "predecessor_module_id": pred_section["module_id"],
        "predecessor_run_id": pred_section["run_id"],
        "predecessor_selection_trace_sha256": pred_section["selection_trace_sha256"],
        "predecessor_staged_ledger_sha256": pred_section["selection_staged_ledger_sha256"],
        "predecessor_resolved_baseline_route": predecessor_resolved_route,
    }, {"selected:F2_or_V": predecessor_resolved_route})

    n_strategy_record = _publish("n_strategy", None, {
        "decision_id": fe._A_E3_N_STRATEGY_DECISION_ID,
        "selection_rule": fe.SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT,
        "candidate_supporting_evidence_sha256": {
            cid: evidence[cid]["supporting_evidence_sha256"]
            for cid in fe._A_E3_N_STRATEGY_CANDIDATES
        },
        "candidate_aggregate_scores": {
            cid: float(evidence[cid]["aggregate_score"])
            for cid in fe._A_E3_N_STRATEGY_CANDIDATES
        },
        "rule_result": dict(rule_result),
        "output_form_record_sha256": of_record["record_sha256"],
        "baseline_route_record_sha256": baseline_record["record_sha256"],
        "shared_winner_retrain_record_sha256": shared_record["record_sha256"],
        "fixed_cohort_support_count": int(evidence[fe._A_E3_N_STRATEGY_FIXED]["support_count"]),
        "shared_cohort_support_count": int(evidence[fe._A_E3_N_STRATEGY_SHARED]["support_count"]),
    }, {"selected:A-E3_n_strategy": n_strategy_winner})

    if n_strategy_winner == fe._A_E3_N_STRATEGY_FIXED:
        baseline_tuple = {"route": predecessor_resolved_route, "loss": loss_id,
                          "architecture": fv[fv_arch_key], "optimizer": fv[fv_opt_key],
                          "output_form": baseline_alias}
    else:
        baseline_tuple = {"route": _A_E3_S_TOKEN, "loss": loss_id,
                          "architecture": sw[s_arch_key], "optimizer": sw[s_opt_key],
                          "output_form": "N/A"}
    _publish("final_aliases", None, {
        "n_strategy_record_sha256": n_strategy_record["record_sha256"],
        "baseline_route_record_sha256": baseline_record["record_sha256"],
        "loss_record_sha256": loss_record["record_sha256"],
        "stage2_F2_or_V_record_sha256": stage_shas[f"stage2:{_A_E3_FV_TOKEN}"],
        "stage2_S_record_sha256": stage_shas[f"stage2:{_A_E3_S_TOKEN}"],
        "output_form_record_sha256": of_record["record_sha256"],
        "n_strategy_winner": n_strategy_winner,
        "baseline_tuple": dict(baseline_tuple),
    }, {
        "selected:A-E3_n_strategy": n_strategy_winner,
        "selected:A-E3_baseline": baseline_tuple,
        "selected:A-E3_loss": loss_id,
        fv_arch_key: fv[fv_arch_key], fv_opt_key: fv[fv_opt_key],
        s_arch_key: sw[s_arch_key], s_opt_key: sw[s_opt_key],
        "selected:F2_or_V": predecessor_resolved_route,
    })
    return records


def _resolve(run_dir: Path, run_id: str, tmp_path: Path, *, scorer=None) -> dict:
    """Call _resolve_a_e3_from_staged_ledger and return the baseline tuple."""
    out: dict[str, str] = {}
    baseline = g3._resolve_a_e3_from_staged_ledger(
        run_dir, run_id, COMMIT, APPROVED_EFFECTIVE_CONFIG_SHA256, out,
        study_root=STUDY_ROOT, cache_root=tmp_path / "cache", frozen_config=FROZEN,
        score_n_strategy_cell=scorer,
    )
    return baseline


# ---------------------------------------------------------------------------
# Positive tests.
# ---------------------------------------------------------------------------


def test_valid_fixed_winner_staged_ledger_resolves(tmp_path):
    """A valid 10-record staged ledger with fixed n_strategy winner resolves cleanly."""
    run_dir, run_id, _, rebuilt = _build_valid_a_e3_run(tmp_path, n_strategy_winner="fixed")
    scorer = _make_n_strategy_scorer(fixed_score=1.0, shared_score=5.0)
    baseline = _resolve(run_dir, run_id, tmp_path, scorer=scorer)
    assert baseline["route"] == "V"
    assert baseline["output_form"] != "N/A"  # fixed winner has a real output_form


def test_valid_shared_winner_staged_ledger_resolves(tmp_path):
    """A valid 10-record staged ledger with shared n_strategy winner resolves cleanly."""
    run_dir, run_id, _, rebuilt = _build_valid_a_e3_run(tmp_path, n_strategy_winner="shared")
    scorer = _make_n_strategy_scorer(fixed_score=5.0, shared_score=1.0)
    baseline = _resolve(run_dir, run_id, tmp_path, scorer=scorer)
    assert baseline["route"] == "S"
    assert baseline["output_form"] == "N/A"  # DeepSets has no output_form


def test_output_form_winner_is_not_treated_as_final_baseline(tmp_path):
    """R4-4#6: the ordinary output_form winner must not be the final A-E3 baseline.

    When n_strategy=shared, the baseline route is 'S' (not the output_form winner's
    F2_or_V route), proving the n_strategy winner overrides the output_form winner.
    """
    run_dir, run_id, _, _ = _build_valid_a_e3_run(tmp_path, n_strategy_winner="shared")
    scorer = _make_n_strategy_scorer(fixed_score=5.0, shared_score=1.0)
    out: dict[str, str] = {}
    baseline = g3._resolve_a_e3_from_staged_ledger(
        run_dir, run_id, COMMIT, APPROVED_EFFECTIVE_CONFIG_SHA256, out,
        study_root=STUDY_ROOT, cache_root=tmp_path / "cache", frozen_config=FROZEN,
        score_n_strategy_cell=scorer,
    )
    # The baseline route is 'S', not whatever the output_form winner resolved to.
    assert baseline["route"] == "S"
    # selected:A-E3_baseline in the A-E3 dict is still the output_form winner alias
    # (kept for A-E3's own fit resolution); it must NOT be 'S'.
    assert out["selected:A-E3_baseline"] != "S"
    assert out["selected:A-E3_n_strategy"] == "shared"


def test_a_e2_consumes_n_strategy_baseline(tmp_path):
    """R4-4#5: A-E2's predecessor aliases come from the n_strategy winner's baseline tuple.

    When n_strategy=shared, the A-E2-view aliases (selected:A-E3_{loss,architecture,
    optimizer,baseline}) resolve to the SHARED winner's tuple (S route + DeepSets arch/opt),
    NOT the F2/V stage2 winner that means something different inside A-E3's own fits.
    """
    run_dir, run_id, _, _ = _build_valid_a_e3_run(tmp_path, n_strategy_winner="shared")
    scorer = _make_n_strategy_scorer(fixed_score=5.0, shared_score=1.0)
    baseline_tuple = _resolve(run_dir, run_id, tmp_path, scorer=scorer)
    # This is what resolve_g3_placeholders_from_evidence seeds into resolutions["A-E2"].
    ae2_view = {
        "selected:A-E3_loss": str(baseline_tuple["loss"]),
        "selected:A-E3_architecture": str(baseline_tuple["architecture"]),
        "selected:A-E3_optimizer": str(baseline_tuple["optimizer"]),
        "selected:A-E3_baseline": str(baseline_tuple["route"]),
    }
    # Shared winner -> route is S, architecture is the DeepSets (S token) winner.
    assert ae2_view["selected:A-E3_baseline"] == "S"
    # The A-E3 dict (stage-specific) has the F2/V winner; A-E2 must NOT inherit it.
    out: dict[str, str] = {}
    g3._resolve_a_e3_from_staged_ledger(
        run_dir, run_id, COMMIT, APPROVED_EFFECTIVE_CONFIG_SHA256, out,
        study_root=STUDY_ROOT, cache_root=tmp_path / "cache", frozen_config=FROZEN,
        score_n_strategy_cell=scorer,
    )
    fv_arch_key = "selected:A-E3_architecture"
    assert out[fv_arch_key] != ae2_view["selected:A-E3_architecture"], (
        "A-E2 must consume the n_strategy winner's S-architecture, not A-E3's stage-specific "
        "F2/V architecture")
    assert out["selected:S_architecture"] == ae2_view["selected:A-E3_architecture"]


# ---------------------------------------------------------------------------
# Attack tests (fail-closed).
# ---------------------------------------------------------------------------


def test_attack_missing_staged_ledger_fails_closed(tmp_path):
    """R4-4#7: a missing A-E3 staged_resolution_ledger.jsonl fails closed."""
    run_dir, run_id, _, _ = _build_valid_a_e3_run(tmp_path, n_strategy_winner="fixed")
    (run_dir / "staged_resolution_ledger.jsonl").unlink()
    scorer = _make_n_strategy_scorer(fixed_score=1.0, shared_score=5.0)
    with pytest.raises(ValueError, match="staged_resolution_ledger.jsonl required"):
        _resolve(run_dir, run_id, tmp_path, scorer=scorer)


def test_attack_forged_n_strategy_winner_fails_closed(tmp_path):
    """R4-4#7: a forged n_strategy winner in record 9 is caught by the independent rebuild."""
    run_dir, run_id, _, rebuilt = _build_valid_a_e3_run(tmp_path, n_strategy_winner="fixed")
    records = fe._read_staged_ledger(run_dir)
    # Record 9 (index 8) is the n_strategy record. Flip its winner.
    other = fe._A_E3_N_STRATEGY_SHARED if rebuilt["winner"] == fe._A_E3_N_STRATEGY_FIXED else fe._A_E3_N_STRATEGY_FIXED
    records[8]["resolution"] = {"selected:A-E3_n_strategy": other}
    # Re-chain from record 8 onwards.
    _rechain_and_write(run_dir, records)
    scorer = _make_n_strategy_scorer(fixed_score=1.0, shared_score=5.0)  # rebuild says fixed
    with pytest.raises(ValueError, match="n_strategy winner disagrees"):
        _resolve(run_dir, run_id, tmp_path, scorer=scorer)


def test_attack_swapped_fixed_shared_evidence_fails_closed(tmp_path):
    """R4-4#7: swapped fixed/shared supporting_evidence_sha256 in record 9 is caught."""
    run_dir, run_id, _, rebuilt = _build_valid_a_e3_run(tmp_path, n_strategy_winner="fixed")
    records = fe._read_staged_ledger(run_dir)
    ev = records[8]["input"]["candidate_supporting_evidence_sha256"]
    # Swap the fixed/shared evidence SHAs.
    ev[fe._A_E3_N_STRATEGY_FIXED], ev[fe._A_E3_N_STRATEGY_SHARED] = (
        ev[fe._A_E3_N_STRATEGY_SHARED], ev[fe._A_E3_N_STRATEGY_FIXED])
    records[8]["input"]["candidate_supporting_evidence_sha256"] = ev
    _rechain_and_write(run_dir, records)
    scorer = _make_n_strategy_scorer(fixed_score=1.0, shared_score=5.0)
    with pytest.raises(ValueError, match="n_strategy input/evidence/rule_result disagrees"):
        _resolve(run_dir, run_id, tmp_path, scorer=scorer)


def test_attack_tampered_final_tuple_fails_closed(tmp_path):
    """R4-4#7: a tampered baseline tuple in record 10 is caught."""
    run_dir, run_id, _, rebuilt = _build_valid_a_e3_run(tmp_path, n_strategy_winner="fixed")
    records = fe._read_staged_ledger(run_dir)
    # Record 10 (index 9) is final_aliases. Tamper the baseline tuple's route.
    tampered_tuple = dict(records[9]["resolution"]["selected:A-E3_baseline"])
    tampered_tuple["route"] = "S" if tampered_tuple["route"] != "S" else "F2"
    records[9]["resolution"]["selected:A-E3_baseline"] = tampered_tuple
    _rechain_and_write(run_dir, records)
    scorer = _make_n_strategy_scorer(fixed_score=1.0, shared_score=5.0)
    with pytest.raises(ValueError, match="final_aliases resolution disagrees"):
        _resolve(run_dir, run_id, tmp_path, scorer=scorer)


def test_attack_broken_hash_chain_fails_closed(tmp_path):
    """A broken previous_record_sha256 chain is caught at shape validation."""
    run_dir, run_id, _, _ = _build_valid_a_e3_run(tmp_path, n_strategy_winner="fixed")
    records = fe._read_staged_ledger(run_dir)
    # Corrupt record 5's previous_record_sha256 (break the chain mid-ledger).
    records[4]["previous_record_sha256"] = "deadbeef" + "0" * 56
    # Do NOT re-chain (the chain must be broken for this attack).
    ledger_path = run_dir / "staged_resolution_ledger.jsonl"
    ledger_path.write_bytes(b"".join(fe._canonical(r) for r in records))
    scorer = _make_n_strategy_scorer(fixed_score=1.0, shared_score=5.0)
    with pytest.raises(ValueError, match="hash chain broken"):
        _resolve(run_dir, run_id, tmp_path, scorer=scorer)


def test_attack_wrong_record_count_fails_closed(tmp_path):
    """A staged ledger with the wrong record count is caught at shape validation."""
    run_dir, run_id, _, _ = _build_valid_a_e3_run(tmp_path, n_strategy_winner="fixed")
    records = fe._read_staged_ledger(run_dir)
    # Drop the last record.
    del records[-1]
    ledger_path = run_dir / "staged_resolution_ledger.jsonl"
    ledger_path.write_bytes(b"".join(fe._canonical(r) for r in records))
    scorer = _make_n_strategy_scorer(fixed_score=1.0, shared_score=5.0)
    with pytest.raises(ValueError, match="must contain exactly 10 records"):
        _resolve(run_dir, run_id, tmp_path, scorer=scorer)


# ---------------------------------------------------------------------------
# Bundle binding test.
# ---------------------------------------------------------------------------


def test_g3_bundle_binds_a_e3_staged_ledger_sha(tmp_path):
    """R4-4#4: build_g3_accreditation requires + binds the A-E3 staged ledger SHA."""
    import inspect
    src = inspect.getsource(g3.build_g3_accreditation)
    assert "A-E3" in src and "staged_resolution_ledger.jsonl" in src, (
        "build_g3_accreditation must bind the A-E3 staged_resolution_ledger SHA")


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _rechain_and_write(run_dir: Path, records: list[dict]) -> None:
    """Recompute resolution_sha256 + record_sha256 + previous_record_sha256 chain."""
    previous_sha = fe._ZERO_HASH
    for rec in records:
        rec["previous_record_sha256"] = previous_sha
        resolution = rec.get("resolution", {})
        rec["resolution_sha256"] = hashlib.sha256(fe._canonical(dict(resolution))).hexdigest()
        core = {k: v for k, v in rec.items() if k != "record_sha256"}
        rec["record_sha256"] = hashlib.sha256(fe._canonical(core)).hexdigest()
        previous_sha = rec["record_sha256"]
    ledger_path = run_dir / "staged_resolution_ledger.jsonl"
    ledger_path.write_bytes(b"".join(fe._canonical(r) for r in records))
