"""Command-line entry point for auditable Study/02 research-A runs."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone


SCRIPT_PATH = Path(__file__).resolve()
STUDY_ROOT = SCRIPT_PATH.parents[1]
REPO_ROOT = SCRIPT_PATH.parents[3]
for path in (SCRIPT_PATH.parent, REPO_ROOT / "python"):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from study02a.artifacts import write_manifest
from study02a.config import load_frozen_config
from study02a import design
from study02a.matrix import expand_module_matrix
from study02a.pilot import run_pilot
from study02a.formal_scheduler import claim_next_fit, materialize_run, status_run, _rebuild_authority
from study02a.formal_executor import (
    build_module_pre_unseal_bundle,
    run_a_e1_staged,
    run_module as run_formal_module,
    reconstruct_deferred_specs,
    resolve_a_e1_staged_selection,
    _validate_selection_point_evidence_dir,
)
from study02a.formal_contracts import (
    PredecessorTrace,
    build_fit_status_record,
    write_ceiling_hit_report,
    write_fit_status,
    write_leakage_audit,
    write_pre_unseal_bundle,
)
from study02a.formal_state import (
    authorize_test_once,
    initialize_formal_state,
    publish_oracle_approval,
)
from study02a.formal_config import load_effective_formal_config
from study02a.selection import build_decision_specs, load_point_evidence
from study02a.training import FitResult


def _load_pilot_amendment() -> dict:
    path = STUDY_ROOT / "configs" / "A-g3-pilot-amendment-v4.json"
    checksum_path = path.with_suffix(".sha256")
    expected = checksum_path.read_text(encoding="utf-8").split()[0]
    actual = hashlib.sha256(path.read_bytes()).hexdigest()
    if actual != expected:
        raise ValueError(f"Pilot amendment hash mismatch: {actual} != {expected}")
    return json.loads(path.read_text(encoding="utf-8"))


def _git_sha() -> str:
    return subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


def validate_config() -> dict:
    config = load_frozen_config(STUDY_ROOT)
    screening = set(config.protocol["seeds"]["nn_screening"])
    formal = set(config.protocol["seeds"]["nn_formal"])
    return {
        "protocol_id": config.protocol["protocol_id"],
        "search_id": config.search["search_id"],
        "status": config.protocol["status"],
        "protocol_sha256": config.protocol_sha256,
        "search_sha256": config.search_sha256,
        "screening_formal_seed_overlap": sorted(screening & formal),
    }


def expand_matrix(output: Path) -> dict:
    config = load_frozen_config(STUDY_ROOT)
    output = Path(output)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Matrix output directory is not empty: {output}")
    output.mkdir(parents=True, exist_ok=True)
    matrix = expand_module_matrix(config)
    matrix_path = output / "experiment_matrix.csv"
    matrix.to_csv(matrix_path, index=False, encoding="utf-8", lineterminator="\n")
    manifest = {
        "run_id": output.name,
        "artifact_type": "g3_experiment_matrix",
        "code_version": _git_sha(),
        "protocol_sha256": config.protocol_sha256,
        "search_sha256": config.search_sha256,
        "test_state": "sealed",
        "total_fits": int(len(matrix)),
        "rules": sorted(matrix["rule_id"].unique().tolist()),
        "output_files": ["experiment_matrix.csv", "manifest.json"],
    }
    write_manifest(manifest, output / "manifest.json")
    return manifest


def accredit_authorize(
    *, module: str, run_id: str, artifact_root: Path,
    approval_path: Path, oracle_review_path: Path, run_family_id: str, timestamp: str,
) -> dict:
    """Pre-unseal accreditation (Task 9 Step 6/8): bind an external oracle approval to a
    completed module run and transition the approval-bound state machine sealed -> unsealed_once.

    The approval artifact MUST be supplied externally (the oracle/Codex owns the decision);
    this entry never creates an APPROVE. It initializes the formal state from the run's
    pre_unseal_bundle.json and authorizes one test access, then stops -- consume_test_once
    (the actual one-shot test evaluation) is deliberately not wired here.
    """
    run_dir = Path(artifact_root) / module / run_id
    bundle_path = run_dir / "pre_unseal_bundle.json"
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    state_path = run_dir / "formal_state.json"
    ledger_path = run_dir / "transition_ledger.jsonl"
    initialize_formal_state(
        state_path=state_path, bundle_path=bundle_path, run_family_id=run_family_id,
        code_commit=bundle["code_commit"],
        effective_config_sha256=bundle["effective_config_sha256"], timestamp=timestamp,
    )
    return authorize_test_once(
        state_path=state_path, bundle_path=bundle_path, approval_path=approval_path,
        ledger_path=ledger_path, timestamp=timestamp,
        ceiling_report_path=run_dir / "ceiling_hit_report.json",
        leakage_audit_path=run_dir / "leakage_audit.json",
        oracle_review_path=oracle_review_path,
    )


def resolve_deferred(
    *, module: str, run_id: str, artifact_root: Path,
    predecessor_module: str, predecessor_run_id: str,
) -> list[dict]:
    """Resolve A-E3/A-E2 deferred dataset specs from a verified predecessor trace (Task 9 D8).

    Reads the downstream module's plan.jsonl, builds a PredecessorTrace from the predecessor
    run's selection trace/receipt/ledger, and reconstructs each deferred plan row's concrete
    dataset specs (cache-key drift / wrong-order / stale predecessor -> fail-closed). No
    training; concrete spec resolution only.
    """
    if module not in ("A-E3", "A-E2"):
        raise ValueError("formal-resolve-deferred supports only downstream modules A-E3 and A-E2")
    run_dir = Path(artifact_root) / module / run_id
    pred_dir = Path(artifact_root) / predecessor_module / predecessor_run_id
    frozen = load_frozen_config(STUDY_ROOT)
    effective = load_effective_formal_config(STUDY_ROOT)
    trace_path = pred_dir / "selection_trace.jsonl"
    receipt_path = pred_dir / "selection_receipt.json"
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes.decode("utf-8"))
    pred_manifest = json.loads((pred_dir / "manifest.json").read_text(encoding="utf-8"))
    predecessor = PredecessorTrace(
        module_id=predecessor_module, run_id=predecessor_run_id, trace_path=trace_path,
        trace_sha256=str(receipt["selection_trace_sha256"]), receipt_path=receipt_path,
        receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
        ledger_path=pred_dir / "selection_ledger.jsonl",
        selection_code_commit=str(pred_manifest["code_commit"]),
    )
    plan_rows = [
        json.loads(line)
        for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    resolved: list[dict] = []
    for row in plan_rows:
        if str(row.get("module_id")) != module:
            continue
        training, validation = reconstruct_deferred_specs(row, frozen, effective, predecessor)
        resolved.append({
            "fit_id": str(row["fit_id"]), "module_id": module, "route": str(row["route"]),
            "training_cache_key": training.cache_key, "validation_cache_key": validation.cache_key,
        })
    return resolved


def _canonical_write(path: Path, obj: Mapping[str, Any]) -> None:
    """Write canonical JSON bytes (LF, sorted, compact) matching the study02a artifact convention."""
    path.write_bytes(
        (json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8"))


def _training_parameter_cell_ids(plan_rows: list[dict], frozen) -> list[str]:
    """Faithfully regenerate the unique training parameter-point IDs across the run's training
    configs via the design module's single-source allocator (the same authority formal_runner uses)."""
    unique: set[str] = set()
    seen: set[tuple] = set()
    for row in plan_rows:
        distribution = str(row.get("distribution", ""))
        if not distribution:
            continue
        cfg = (distribution, str(row.get("n_mode")), int(row.get("training_size") or 0), row.get("fixed_n"))
        if cfg in seen:
            continue
        seen.add(cfg)
        try:
            frame = design.allocate_training_rows(
                distribution, str(row.get("n_mode")), int(row.get("training_size") or 0),
                frozen, fixed_n=row.get("fixed_n"))
        except (ValueError, KeyError):
            continue
        unique.update(str(value) for value in frame["parameter_cell_id"].tolist())
    return sorted(unique)


def _accredit_role_parameter_points(module: str, frozen, plan_rows: list[dict]) -> dict[str, list[str]]:
    """Regenerate the four formal role parameter-point ID sets from the frozen design (disjoint by
    independent role/module design seeds + role-prefixed IDs; the audit asserts zero intersections)."""
    formal = frozen.protocol["formal_sizes"]
    return {
        "training": _training_parameter_cell_ids(plan_rows, frozen),
        "validation": list(design.generate_parameter_points(
            "validation", "core", int(formal["validation"]["parameter_points"]), frozen)["point_id"]),
        "calibration": list(design.generate_parameter_points(
            "calibration", "core", int(formal["calibration"]["parameter_points"]), frozen)["point_id"]),
        "test": list(design.generate_parameter_points(
            module, "core", int(formal["module_test"]["parameter_points"]), frozen)["point_id"]),
    }


def _accredit_role_namespaces(manifest: Mapping[str, Any]) -> dict[str, str]:
    """The formal manifest records only training/validation namespaces; the leakage audit needs all
    four roles. Derive calibration/test from the training namespace pattern (``<prefix>/<role>``)."""
    manifest_ns = manifest["role_namespaces"]
    base = str(manifest_ns["training"])
    prefix = base[: base.rfind("/")]
    return {role: (str(manifest_ns[role]) if role in manifest_ns else f"{prefix}/{role}")
            for role in ("training", "validation", "calibration", "test")}


def _recover_selection_n(plan_row: Mapping[str, Any], fit_id: str) -> int:
    """Recover a selection candidate's concrete sample size from the formal plan row.

    plan.jsonl carries ``n_mode``/``fixed_n`` (the matrix ``n`` is renamed at plan-build time; the
    plan has no ``n`` field), so the prior ``int(plan_row["n"])`` was a latent KeyError. A selection
    candidate must be a concrete-n fit (shared-n is for historical fits only, which are never
    selection candidates), so shared_n / missing fixed_n fail closed. The value is not written back
    into the plan (no second source of truth).
    """
    if plan_row.get("n_mode") == "shared_n":
        raise ValueError(f"selection candidate {fit_id} is shared-n; selection requires a concrete n")
    fixed_n = plan_row.get("fixed_n")
    if fixed_n is None:
        raise ValueError(f"selection candidate {fit_id} plan row has no fixed_n")
    return int(fixed_n)


def _fit_terminal_receipt(run_dir: Path, fit_id: str) -> tuple[str, str | None]:
    """Read a selection fit's scheduler terminal receipt and return ``(state, failure_code)``.

    Exactly one of ``receipts/{fit_id}.succeeded.json`` / ``.failed.json`` must exist (the scheduler
    authority's terminal-state record; its SHA is event-bound). This is the scheduler terminal
    state/receipt source accredit_build cross-checks the point-evidence failure record against.
    Both receipts, neither receipt, a wrong-state receipt, or a failed receipt missing its
    ``failure_code`` all fail closed. ``failure_code`` is ``None`` for succeeded fits.
    """
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


def accredit_build(module: str, run_id: str, artifact_root: Path, cache_root: Path) -> dict:
    """Pre-unseal accreditation build (Task 9 Step 4/5/8): generate the run-level diagnostics a
    completed module run needs (fit_status.csv, ceiling_hit_report.json, leakage_audit.json) from
    the run's per-fit evidence + selection trace, then build the pre-unseal bundle.

    Authority preflight FIRST: a full ``_rebuild_authority`` replay is the sole source of the
    manifest, plan and ``fit_states`` -- raw ``manifest.json``/``plan.jsonl``/receipt JSON are never
    trusted as fact. The replay raises on any tampering (terminal-receipt content vs event
    ``receipt_sha256``, ``plan_sha256``, event-chain hash, manifest/controller-anchor drift) BEFORE
    any diagnostic file is written. Each selection fit's point-evidence ``failed`` flag, scheduler
    ``fit_state`` and terminal-receipt state must then agree (three-way consistency). The
    diagnostics are not produced by training/selection; this entry reconstructs them faithfully so
    the bundle can accredit the run up to test unseal. Test stays sealed; point provenance is
    rebuilt inside the bundle builder (R5). No training; no test read.
    """
    run_dir = Path(artifact_root) / module / run_id
    frozen = load_frozen_config(STUDY_ROOT)
    effective = load_effective_formal_config(STUDY_ROOT)
    # Authority preflight (FIRST): replay-verified manifest/plan/fit_states. Raises on tampering
    # before any diagnostic is written. Requires a clean scoped code/ tree (same as all scheduler use).
    authority_manifest, verified_plan, scheduler_state, _events = _rebuild_authority(run_dir, cache_root)
    manifest = authority_manifest
    fit_states = scheduler_state["fit_states"]
    plan_by_fit: dict[str, dict] = {str(row["fit_id"]): row for row in verified_plan}

    trace_records = [
        json.loads(line) for line in (run_dir / "selection_trace.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    selected_by_decision = {
        str(r["decision_id"]): str(r["candidate_id"]) for r in trace_records if r.get("selected")}

    # Expected selection fit_id set from the FROZEN authority (matrix -> DecisionSpecs), NOT a
    # directory scan of outputs/. Selection candidates are matrix-determined; their point evidence is
    # a post-selection artifact that lives in selection/point_evidence/, never under outputs/{fit_id}/
    # (the scheduler-authority training-output dir, which must stay exactly the frozen expected_outputs).
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    specs = build_decision_specs(module, matrix_rows)
    expected_fit_ids: set[str] = set()
    for spec in specs:
        for candidate in spec.candidates:
            for key in candidate.support_keys:
                expected_fit_ids.add(candidate.support_for(key))

    # The selection point-evidence dir must hold exactly the expected candidates (no missing/extra/
    # duplicate/alias/non-file/nested/unknown fit); evidence.json still comes from outputs/{fit_id}/.
    point_evidence_by_fit = _validate_selection_point_evidence_dir(
        run_dir=run_dir, expected_fit_ids=expected_fit_ids)

    rows: list[dict] = []
    point_evidence_paths: dict[str, Path] = {}
    for fit_id in sorted(expected_fit_ids):
        evaluation = load_point_evidence(json.loads(point_evidence_by_fit[fit_id].read_text(encoding="utf-8")))
        plan_row = plan_by_fit[fit_id]
        selected = selected_by_decision.get(evaluation.decision_id) == evaluation.candidate_id
        n = _recover_selection_n(plan_row, fit_id)
        common = dict(
            fit_id=fit_id, module_id=module, rule_id=str(plan_row["rule_id"]), route_id=str(plan_row["route"]),
            n=n, seed=int(plan_row["seed"]), decision_id=evaluation.decision_id,
            candidate_id=evaluation.candidate_id, selected=selected)
        # Three independent sources must agree, else fail closed (before any diagnostic write): the
        # scheduler fit_state (from the authority replay), the terminal-receipt state (hash-verified by
        # the replay) and the point-evidence failure record. No fit may vanish -- a failed fit gets a
        # failure row, never a silent skip.
        scheduler_fit = fit_states.get(fit_id)
        receipt_state, failure_code = _fit_terminal_receipt(run_dir, fit_id)
        evidence_path = run_dir / "outputs" / fit_id / "evidence.json"
        if scheduler_fit not in ("succeeded", "failed"):
            raise ValueError(
                f"selection fit {fit_id} is not scheduler-terminal (state={scheduler_fit!r}); "
                f"accreditation requires a complete terminal run")
        if receipt_state != scheduler_fit:
            raise ValueError(
                f"selection fit {fit_id}: scheduler fit_state {scheduler_fit!r} disagrees with its "
                f"terminal-receipt state {receipt_state!r}")
        if scheduler_fit == "succeeded":
            if evaluation.failed:
                raise ValueError(f"selection fit {fit_id}: scheduler succeeded but its point evidence is failed")
            if not evidence_path.is_file():
                raise ValueError(f"succeeded selection fit {fit_id} has no training evidence.json")
            evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
            curve = tuple(float(v) for v in evidence["validation_curve"])
            best_epoch_zero = int(evidence["best_epoch_one_based"]) - 1
            result = FitResult(
                predictions=None, checkpoint_sha256=str(evidence["checkpoint_sha256"]),
                best_validation_loss=curve[best_epoch_zero], best_epoch=best_epoch_zero,
                actual_epochs=int(evidence["actual_epochs"]), validation_loss_history=curve,
                early_stop_reason=str(evidence["early_stop_reason"]),
                hit_epoch_ceiling=bool(evidence["hit_epoch_100"]))
            rows.append(build_fit_status_record(**common, result=result, selection_score=float(evaluation.selection_score)))
        else:  # scheduler_fit == "failed"
            if not evaluation.failed:
                raise ValueError(f"selection fit {fit_id}: scheduler failed but its point evidence is not failed")
            if evidence_path.is_file():
                raise ValueError(f"failed selection fit {fit_id} unexpectedly has a training evidence.json")
            rows.append(build_fit_status_record(
                **common, result=None, failure_penalty=float(evaluation.failure_penalty),
                failure_message=failure_code))
        point_evidence_paths[fit_id] = point_evidence_by_fit[fit_id]

    fit_status_path = run_dir / "fit_status.csv"
    write_fit_status(fit_status_path, rows)
    ceiling_path = run_dir / "ceiling_hit_report.json"
    write_ceiling_hit_report(ceiling_path, rows)
    leakage_path = run_dir / "leakage_audit.json"
    write_leakage_audit(
        leakage_path, parameter_point_ids=_accredit_role_parameter_points(module, frozen, list(plan_by_fit.values())),
        role_namespaces=_accredit_role_namespaces(manifest), scaler_source="training_only",
        feature_selection_source="validation_only", model_selection_source="validation_only", test_access_count=0)

    bundle = build_module_pre_unseal_bundle(
        study_root=STUDY_ROOT, cache_root=cache_root, run_dirs={module: run_dir},
        formal_manifests=[run_dir / "manifest.json"],
        selection_traces=[run_dir / "selection_trace.jsonl"],
        selection_receipts=[run_dir / "selection_receipt.json"],
        selection_ledger_path=run_dir / "selection_ledger.jsonl", fit_status_path=fit_status_path,
        ceiling_report_path=ceiling_path, leakage_audit_path=leakage_path,
        code_commit=str(manifest["code_commit"]), effective_config_sha256=effective.effective_config_sha256,
        module_run_ids={module: run_id}, point_evidence_paths=point_evidence_paths,
        selection_diagnostics_paths=[run_dir / "selection_diagnostics.jsonl"])
    _canonical_write(run_dir / "pre_unseal_bundle.json", bundle)
    return bundle


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Study/02 research-A experiment runner")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("validate-config", help="verify frozen config hashes and seed isolation")
    matrix = commands.add_parser("expand-matrix", help="expand the frozen G3 fit matrix without opening test data")
    matrix.add_argument("--output", type=Path, required=True)
    pilot = commands.add_parser("pilot", help="run pilot-only data, feature, admission, and smoke-fit checks")
    pilot.add_argument("--output", type=Path, required=True)
    pilot.add_argument("--run-id", required=True)
    pilot.add_argument("--points", type=int, default=32)
    pilot.add_argument("--repeats", type=int, default=4)
    pilot.add_argument("--n", default="5,20")
    pilot.add_argument("--ledger", type=Path, default=STUDY_ROOT / "artifacts" / "run_ledger.jsonl")
    pilot.add_argument("--skip-methods", action="store_true")
    pilot.add_argument("--skip-train-smoke", action="store_true")
    formal = commands.add_parser("formal-select", help="plan, inspect, or claim sealed training/validation work")
    formal.add_argument("--module", choices=("A-E1", "A-E3", "A-E2"), required=True)
    formal.add_argument("--run-id", required=True)
    formal.add_argument("--artifact-root", type=Path, required=True)
    formal.add_argument("--cache-root", type=Path, required=True)
    mode = formal.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--claim-next", action="store_true")
    formal.add_argument("--owner-id", default="formal-select-cli")
    execute = commands.add_parser("formal-execute", help="drive resumable claim->train->record formal fits")
    execute.add_argument("--module", choices=("A-E1", "A-E3", "A-E2"), required=True)
    execute.add_argument("--run-id", required=True)
    execute.add_argument("--artifact-root", type=Path, required=True)
    execute.add_argument("--cache-root", type=Path, required=True)
    execute.add_argument("--max-fits", type=int, default=None, help="stop after N successful fits (default: run to exhaustion)")
    execute.add_argument("--owner-id", default="formal-executor")
    staged = commands.add_parser(
        "formal-staged",
        help="derive the staged A-E1 selection ledger (top4 -> stage2 -> winner-retrain -> F2-vs-V baseline -> aliases) from a completed selection trace",
    )
    staged.add_argument("--module", choices=("A-E1",), required=True)
    staged.add_argument("--run-id", required=True)
    staged.add_argument("--artifact-root", type=Path, required=True)
    staged.add_argument("--cache-root", type=Path, required=True)
    authorize = commands.add_parser(
        "formal-accredit-authorize",
        help="bind an external oracle approval to a completed run and authorize one test access (sealed -> unsealed_once); never consumes test",
    )
    authorize.add_argument("--module", choices=("A-E1", "A-E3", "A-E2"), required=True)
    authorize.add_argument("--run-id", required=True)
    authorize.add_argument("--artifact-root", type=Path, required=True)
    authorize.add_argument("--approval", type=Path, required=True,
                           help="external oracle 'APPROVE test unseal' artifact path (oracle-owned; never auto-created)")
    authorize.add_argument("--oracle-review", type=Path, required=True,
                           help="oracle review artifact path bound by the approval")
    authorize.add_argument("--run-family-id", required=True)
    deferred = commands.add_parser(
        "formal-resolve-deferred",
        help="resolve A-E3/A-E2 deferred dataset specs from a verified predecessor trace (no training)",
    )
    deferred.add_argument("--module", choices=("A-E3", "A-E2"), required=True)
    deferred.add_argument("--run-id", required=True)
    deferred.add_argument("--artifact-root", type=Path, required=True)
    deferred.add_argument("--predecessor-module", required=True)
    deferred.add_argument("--predecessor-run-id", required=True)
    build = commands.add_parser(
        "formal-accredit-build",
        help="generate fit_status/ceiling/leakage diagnostics + the sealed pre_unseal_bundle for a completed module run (test stays sealed)",
    )
    build.add_argument("--module", choices=("A-E1",), required=True)
    build.add_argument("--run-id", required=True)
    build.add_argument("--artifact-root", type=Path, required=True)
    build.add_argument("--cache-root", type=Path, required=True)
    return parser


def resolve_staged(module: str, run_id: str, artifact_root: Path, cache_root: Path) -> dict:
    """Derive the staged A-E1 selection ledger from a run's published selection trace.

    Production entry point (D8): reads the module's immutable selection trace + receipt +
    ledger and appends the staged resolution ledger. Pending stages are computed from the
    run authority + frozen matrix; the caller never supplies winner/top4/baseline.
    """
    run_dir = Path(artifact_root) / module / run_id
    return resolve_a_e1_staged_selection(
        study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
        module_id=module, run_id=run_id,
    )


def main() -> int:
    args = _parser().parse_args()
    if args.command == "validate-config":
        payload = validate_config()
    elif args.command == "expand-matrix":
        payload = expand_matrix(args.output)
    elif args.command == "pilot":
        config = load_frozen_config(STUDY_ROOT)
        amendment = _load_pilot_amendment()
        payload = run_pilot(
            config,
            args.output,
            run_id=args.run_id,
            code_version=_git_sha(),
            points=args.points,
            repeats=args.repeats,
            n_values=[int(value) for value in args.n.split(",")],
            run_methods=not args.skip_methods,
            train_smoke=not args.skip_train_smoke,
            ledger_path=args.ledger,
            pilot_amendment=amendment,
            matrix_path=STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv",
        )
    elif args.command == "formal-select":
        run_dir = args.artifact_root / args.module / args.run_id
        if args.dry_run:
            payload = materialize_run(
                study_root=STUDY_ROOT,
                matrix_path=STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv",
                module_id=args.module,
                run_id=args.run_id,
                artifact_root=args.artifact_root,
                cache_root=args.cache_root,
                predecessor=None,
            )
        elif args.status:
            payload = status_run(run_dir, cache_root=args.cache_root)
        else:
            payload = claim_next_fit(
                run_dir,
                cache_root=args.cache_root,
                owner_id=args.owner_id,
                owner_nonce=secrets.token_hex(16),
                timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            )
    elif args.command == "formal-execute":
        if args.module == "A-E1":
            payload = run_a_e1_staged(
                study_root=STUDY_ROOT,
                module_id=args.module,
                run_id=args.run_id,
                artifact_root=args.artifact_root,
                cache_root=args.cache_root,
                owner_id=args.owner_id,
                max_fits=args.max_fits,
            )
        else:
            payload = run_formal_module(
                study_root=STUDY_ROOT,
                module_id=args.module,
                run_id=args.run_id,
                artifact_root=args.artifact_root,
                cache_root=args.cache_root,
                owner_id=args.owner_id,
                max_fits=args.max_fits,
            )
    elif args.command == "formal-staged":
        payload = resolve_staged(args.module, args.run_id, args.artifact_root, args.cache_root)
    elif args.command == "formal-accredit-authorize":
        payload = accredit_authorize(
            module=args.module, run_id=args.run_id, artifact_root=args.artifact_root,
            approval_path=args.approval, oracle_review_path=args.oracle_review,
            run_family_id=args.run_family_id,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )
    elif args.command == "formal-resolve-deferred":
        payload = resolve_deferred(
            module=args.module, run_id=args.run_id, artifact_root=args.artifact_root,
            predecessor_module=args.predecessor_module, predecessor_run_id=args.predecessor_run_id,
        )
    elif args.command == "formal-accredit-build":
        payload = accredit_build(args.module, args.run_id, args.artifact_root, args.cache_root)
    else:
        raise AssertionError(f"Unreachable command: {args.command}")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
