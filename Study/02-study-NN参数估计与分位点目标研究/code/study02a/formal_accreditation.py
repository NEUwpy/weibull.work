"""Sealed-only module diagnostics reconstruction for unified G3 accreditation.

This library module has no dependency on the CLI runner. It rebuilds diagnostics from
replay authority and verified selection evidence; it cannot authorize, unseal, or consume test.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from . import design
from . import formal_executor as _formal_executor
from .config import load_frozen_config
from .formal_contracts import (
    build_fit_status_record,
    write_ceiling_hit_report,
    write_fit_status,
    write_leakage_audit,
)
from .formal_executor import (
    _validate_selection_evidence,
    _validate_selection_point_evidence_dir,
)
from .formal_scheduler import _rebuild_authority
from .matrix import expand_module_matrix
from .selection import (
    assert_point_evidence_provenance,
    build_decision_specs,
    build_selection_trace,
    load_point_evidence,
)
from .training import FitResult


def _training_parameter_cell_ids(plan_rows: list[dict], frozen) -> list[str]:
    unique: set[str] = set()
    seen: set[tuple] = set()
    for row in plan_rows:
        distribution = str(row.get("distribution", ""))
        if not distribution:
            continue
        cfg = (
            distribution,
            str(row.get("n_mode")),
            int(row.get("training_size") or 0),
            row.get("fixed_n"),
        )
        if cfg in seen:
            continue
        seen.add(cfg)
        try:
            frame = design.allocate_training_rows(
                distribution,
                str(row.get("n_mode")),
                int(row.get("training_size") or 0),
                frozen,
                fixed_n=row.get("fixed_n"),
            )
        except (ValueError, KeyError):
            continue
        unique.update(str(value) for value in frame["parameter_cell_id"].tolist())
    return sorted(unique)


def _accredit_role_parameter_points(
    module: str, frozen, plan_rows: list[dict],
) -> dict[str, list[str]]:
    formal = frozen.protocol["formal_sizes"]
    return {
        "training": _training_parameter_cell_ids(plan_rows, frozen),
        "validation": list(
            design.generate_parameter_points(
                "validation", "core", int(formal["validation"]["parameter_points"]), frozen,
            )["point_id"]
        ),
        "calibration": list(
            design.generate_parameter_points(
                "calibration", "core", int(formal["calibration"]["parameter_points"]), frozen,
            )["point_id"]
        ),
        "test": list(
            design.generate_parameter_points(
                module, "core", int(formal["module_test"]["parameter_points"]), frozen,
            )["point_id"]
        ),
    }


def _accredit_role_namespaces(manifest: Mapping[str, Any]) -> dict[str, str]:
    manifest_ns = manifest["role_namespaces"]
    base = str(manifest_ns["training"])
    prefix = base[: base.rfind("/")]
    return {
        role: str(manifest_ns[role]) if role in manifest_ns else f"{prefix}/{role}"
        for role in ("training", "validation", "calibration", "test")
    }


def _recover_selection_n(plan_row: Mapping[str, Any], fit_id: str) -> int | str:
    """Recover concrete n, preserving only the frozen A-E3 S-route shared-n case."""
    if plan_row.get("n_mode") == "shared_n":
        if plan_row.get("module_id") != "A-E3" or plan_row.get("route") != "S":
            raise ValueError(
                f"selection candidate {fit_id} uses shared_n outside frozen A-E3/S"
            )
        return "shared"
    fixed_n = plan_row.get("fixed_n")
    if fixed_n is None:
        raise ValueError(f"selection candidate {fit_id} plan row has no fixed_n")
    return int(fixed_n)


def _fit_terminal_receipt(run_dir: Path, fit_id: str) -> tuple[str, str | None]:
    succeeded = run_dir / "receipts" / f"{fit_id}.succeeded.json"
    failed = run_dir / "receipts" / f"{fit_id}.failed.json"
    if succeeded.is_file() and failed.is_file():
        raise ValueError(f"selection fit {fit_id} has both succeeded and failed receipts")
    if succeeded.is_file():
        receipt = json.loads(succeeded.read_text(encoding="utf-8"))
        if receipt.get("state") != "succeeded":
            raise ValueError(f"selection fit {fit_id} succeeded receipt state is not 'succeeded'")
        return "succeeded", None
    if failed.is_file():
        receipt = json.loads(failed.read_text(encoding="utf-8"))
        if receipt.get("state") != "failed":
            raise ValueError(f"selection fit {fit_id} failed receipt state is not 'failed'")
        code = receipt.get("details", {}).get("failure_code")
        if not isinstance(code, str) or not code.strip():
            raise ValueError(f"selection fit {fit_id} failure receipt has no failure_code")
        return "failed", code
    raise ValueError(f"selection fit {fit_id} has no scheduler terminal receipt")


def _write_or_verify(path: Path, writer) -> None:
    """Publish once; on rerun accept exact rebuilt bytes and reject any conflict."""
    if not path.exists():
        writer(path)
        return
    temp = path.with_name(path.name + ".rebuild")
    if temp.exists():
        raise ValueError(f"stale diagnostics rebuild artifact exists: {temp}")
    try:
        writer(temp)
        if temp.read_bytes() != path.read_bytes():
            raise ValueError(f"existing diagnostics conflict with deterministic rebuild: {path}")
    finally:
        temp.unlink(missing_ok=True)


def build_module_accreditation_diagnostics(
    *, study_root: Path, module: str, run_id: str,
    artifact_root: Path, cache_root: Path,
) -> dict[str, Any]:
    """Rebuild one completed module's sealed accreditation diagnostics.

    Full scheduler replay runs before any diagnostic write. Selection trace/receipt/ledger,
    relocated point evidence, scheduler terminal state, and terminal receipts must agree.
    """
    run_dir = Path(artifact_root) / module / run_id
    frozen = load_frozen_config(study_root)
    manifest, verified_plan, scheduler_state, _events = _rebuild_authority(
        run_dir, cache_root,
    )
    fit_states = scheduler_state["fit_states"]
    plan_by_fit: dict[str, dict] = {
        str(row["fit_id"]): row for row in verified_plan
    }

    trace_path = run_dir / "selection_trace.jsonl"
    trace_sha = hashlib.sha256(trace_path.read_bytes()).hexdigest()
    trace_records = _validate_selection_evidence(
        selection_trace_path=trace_path,
        selection_trace_sha256=trace_sha,
        selection_receipt_path=run_dir / "selection_receipt.json",
        selection_ledger_path=run_dir / "selection_ledger.jsonl",
        module_id=module,
        run_id=run_id,
    )
    specs = build_decision_specs(
        module, expand_module_matrix(frozen).to_dict("records"),
    )
    expected_fit_ids = {
        candidate.support_for(key)
        for spec in specs
        for candidate in spec.candidates
        for key in candidate.support_keys
    }
    point_evidence_by_fit = _validate_selection_point_evidence_dir(
        run_dir=run_dir, expected_fit_ids=expected_fit_ids,
    )
    rebuilt_by_fit = _formal_executor.rebuild_selection_point_provenance(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root,
        module_id=module, run_id=run_id,
    )
    if set(rebuilt_by_fit) != expected_fit_ids:
        raise ValueError(
            f"{module} rebuilt point provenance fit set differs from frozen selection set"
        )

    published_by_fit = {}
    for fit_id in sorted(expected_fit_ids):
        evaluation = load_point_evidence(
            json.loads(point_evidence_by_fit[fit_id].read_text(encoding="utf-8"))
        )
        assert_point_evidence_provenance(
            published=evaluation, rebuilt=rebuilt_by_fit[fit_id],
        )
        published_by_fit[fit_id] = evaluation

    rebuilt_records, rebuilt_diagnostics = build_selection_trace(
        module_id=module, run_id=run_id, specs=specs,
        evaluations_by_fit=rebuilt_by_fit,
    )
    rebuilt_trace_by_identity = {
        (record["decision_id"], record["candidate_id"]): record
        for record in rebuilt_records
    }
    published_trace_by_identity = {
        (record["decision_id"], record["candidate_id"]): record
        for record in trace_records
    }
    if rebuilt_trace_by_identity != published_trace_by_identity:
        raise ValueError(
            f"{module} selection trace disagrees with checkpoint-rebuilt selection"
        )
    diagnostics_path = run_dir / "selection_diagnostics.jsonl"
    if not diagnostics_path.is_file():
        raise ValueError(f"{module} selection_diagnostics.jsonl is missing")
    expected_diagnostics_bytes = b"".join(
        (json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for record in rebuilt_diagnostics
    )
    if diagnostics_path.read_bytes() != expected_diagnostics_bytes:
        raise ValueError(
            f"{module} selection diagnostics disagree with checkpoint-rebuilt selection"
        )

    selected_by_decision = {
        str(record["decision_id"]): str(record["candidate_id"])
        for record in rebuilt_records
        if record.get("selected")
    }

    rows: list[dict[str, Any]] = []
    point_evidence_paths: dict[str, Path] = {}
    for fit_id in sorted(expected_fit_ids):
        evaluation = published_by_fit[fit_id]
        plan_row = plan_by_fit[fit_id]
        selected = (
            selected_by_decision.get(evaluation.decision_id) == evaluation.candidate_id
        )
        common = dict(
            fit_id=fit_id,
            module_id=module,
            rule_id=str(plan_row["rule_id"]),
            route_id=str(plan_row["route"]),
            n=_recover_selection_n(plan_row, fit_id),
            seed=int(plan_row["seed"]),
            decision_id=evaluation.decision_id,
            candidate_id=evaluation.candidate_id,
            selected=selected,
        )
        scheduler_fit = fit_states.get(fit_id)
        receipt_state, failure_code = _fit_terminal_receipt(run_dir, fit_id)
        evidence_path = run_dir / "outputs" / fit_id / "evidence.json"
        if scheduler_fit not in ("succeeded", "failed"):
            raise ValueError(
                f"selection fit {fit_id} is not scheduler-terminal "
                f"(state={scheduler_fit!r})"
            )
        if receipt_state != scheduler_fit:
            raise ValueError(
                f"selection fit {fit_id}: scheduler fit_state {scheduler_fit!r} "
                f"disagrees with terminal receipt {receipt_state!r}"
            )
        if scheduler_fit == "succeeded":
            if evaluation.failed:
                raise ValueError(
                    f"selection fit {fit_id}: scheduler succeeded but point evidence is failed"
                )
            if not evidence_path.is_file():
                raise ValueError(
                    f"succeeded selection fit {fit_id} has no training evidence.json"
                )
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            curve = tuple(float(value) for value in evidence["validation_curve"])
            best_epoch_zero = int(evidence["best_epoch_one_based"]) - 1
            result = FitResult(
                predictions=None,
                checkpoint_sha256=str(evidence["checkpoint_sha256"]),
                best_validation_loss=curve[best_epoch_zero],
                best_epoch=best_epoch_zero,
                actual_epochs=int(evidence["actual_epochs"]),
                validation_loss_history=curve,
                early_stop_reason=str(evidence["early_stop_reason"]),
                hit_epoch_ceiling=bool(evidence["hit_epoch_100"]),
            )
            rows.append(
                build_fit_status_record(
                    **common,
                    result=result,
                    selection_score=float(evaluation.selection_score),
                )
            )
        else:
            if not evaluation.failed:
                raise ValueError(
                    f"selection fit {fit_id}: scheduler failed but point evidence is not failed"
                )
            if evidence_path.is_file():
                raise ValueError(
                    f"failed selection fit {fit_id} unexpectedly has training evidence.json"
                )
            rows.append(
                build_fit_status_record(
                    **common,
                    result=None,
                    failure_penalty=float(evaluation.failure_penalty),
                    failure_message=failure_code,
                )
            )
        point_evidence_paths[fit_id] = point_evidence_by_fit[fit_id]

    fit_status_path = run_dir / "fit_status.csv"
    _write_or_verify(fit_status_path, lambda path: write_fit_status(path, rows))
    ceiling_path = run_dir / "ceiling_hit_report.json"
    _write_or_verify(ceiling_path, lambda path: write_ceiling_hit_report(path, rows))
    leakage_path = run_dir / "leakage_audit.json"
    leakage_kwargs = dict(
        parameter_point_ids=_accredit_role_parameter_points(
            module, frozen, list(plan_by_fit.values())
        ),
        role_namespaces=_accredit_role_namespaces(manifest),
        scaler_source="training_only",
        feature_selection_source="validation_only",
        model_selection_source="validation_only",
        test_access_count=0,
    )
    _write_or_verify(
        leakage_path, lambda path: write_leakage_audit(path, **leakage_kwargs),
    )
    return {
        "module": module,
        "run_id": run_id,
        "run_dir": run_dir,
        "manifest": manifest,
        "fit_status_path": fit_status_path,
        "ceiling_path": ceiling_path,
        "leakage_path": leakage_path,
        "point_evidence_paths": point_evidence_paths,
    }


__all__ = ["build_module_accreditation_diagnostics"]
