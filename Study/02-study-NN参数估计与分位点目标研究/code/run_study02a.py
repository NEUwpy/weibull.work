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
from study02a.matrix import expand_module_matrix
from study02a.pilot import run_pilot
from study02a.formal_scheduler import claim_next_fit, materialize_run, status_run
from study02a.formal_executor import (
    run_a_e1_staged,
    run_a_e3_staged,
    run_module as run_formal_module,
    reconstruct_deferred_specs,
    resolve_a_e1_staged_selection,
    resolve_a_e3_staged_selection,
)
from study02a.formal_contracts import PredecessorTrace, _PUBLISHES_STAGED_LEDGER
from study02a.formal_config import load_effective_formal_config
from study02a.formal_g3_control import build_g3_accreditation
from study02a.formal_accreditation import (
    build_module_accreditation_diagnostics as _build_module_accreditation_diagnostics,
)


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
    """Permanently block the superseded per-module authorization path."""
    del module, run_id, artifact_root, approval_path, oracle_review_path, run_family_id, timestamp
    raise SystemExit(
        "FATAL: formal-accredit-authorize is permanently BLOCKED. Test authorization belongs "
        "only to the unified three-module G3 control plane and is outside this preparation task."
    )


def _build_predecessor_trace(
    artifact_root: Path, predecessor_module: str, predecessor_run_id: str,
) -> PredecessorTrace:
    """Build a PredecessorTrace from a predecessor run's on-disk artifacts.

    Reads the predecessor's selection_trace/receipt/ledger + manifest code_commit +
    staged_resolution_ledger SHA (when the predecessor module publishes one, per
    ``_PUBLISHES_STAGED_LEDGER``). Mirrors the assembly historically embedded in
    ``resolve_deferred``; reused by the formal-execute A-E3 arm so the predecessor binding
    is byte-identical across CLI entry points. The staged-ledger SHA is the control-plane v2
    binding: a downstream run rests on a predecessor file that cannot be swapped after the
    downstream plan is built. If the staged ledger file is missing, the fields stay ``None``
    and ``_validate_predecessor`` fail-closes later (preserving the strict-order contract: a
    wrong-order predecessor still raises "Wrong predecessor module" first).
    """
    pred_dir = Path(artifact_root) / predecessor_module / predecessor_run_id
    receipt_path = pred_dir / "selection_receipt.json"
    receipt_bytes = receipt_path.read_bytes()
    receipt = json.loads(receipt_bytes.decode("utf-8"))
    pred_manifest = json.loads((pred_dir / "manifest.json").read_text(encoding="utf-8"))
    staged_ledger_path: Path | None = None
    staged_ledger_sha256: str | None = None
    if predecessor_module in _PUBLISHES_STAGED_LEDGER:
        conventional = pred_dir / "staged_resolution_ledger.jsonl"
        if conventional.is_file():
            staged_ledger_path = conventional
            staged_ledger_sha256 = hashlib.sha256(conventional.read_bytes()).hexdigest()
    return PredecessorTrace(
        module_id=predecessor_module, run_id=predecessor_run_id,
        trace_path=pred_dir / "selection_trace.jsonl",
        trace_sha256=str(receipt["selection_trace_sha256"]),
        receipt_path=receipt_path,
        receipt_sha256=hashlib.sha256(receipt_bytes).hexdigest(),
        ledger_path=pred_dir / "selection_ledger.jsonl",
        selection_code_commit=str(pred_manifest["code_commit"]),
        staged_ledger_path=staged_ledger_path,
        staged_ledger_sha256=staged_ledger_sha256,
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
    frozen = load_frozen_config(STUDY_ROOT)
    effective = load_effective_formal_config(STUDY_ROOT)
    predecessor = _build_predecessor_trace(
        Path(artifact_root), predecessor_module, predecessor_run_id)
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


def accredit_build(module: str, run_id: str, artifact_root: Path, cache_root: Path) -> dict:
    """Permanently block the superseded single-module bundle builder."""
    del module, run_id, artifact_root, cache_root
    raise SystemExit(
        "FATAL: formal-accredit-build is permanently BLOCKED. Use the three-module "
        "diagnostics-only command followed by formal-g3-accredit-build."
    )


def diagnostics_build(module: str, run_id: str, artifact_root: Path, cache_root: Path) -> dict:
    result = _build_module_accreditation_diagnostics(
        study_root=STUDY_ROOT, module=module, run_id=run_id,
        artifact_root=artifact_root, cache_root=cache_root,
    )
    return {
        "status": "sealed_diagnostics_ready",
        "module": module,
        "run_id": run_id,
        "fit_status_path": str(result["fit_status_path"]),
        "ceiling_report_path": str(result["ceiling_path"]),
        "leakage_audit_path": str(result["leakage_path"]),
    }


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
    execute.add_argument(
        "--predecessor-run-id", default=None,
        help="predecessor A-E1 staged run ID (required for A-E3 formal-execute; ignored for A-E1)")
    staged = commands.add_parser(
        "formal-staged",
        help="derive the staged A-E1/A-E3 selection ledger from a completed selection trace",
    )
    staged.add_argument("--module", choices=("A-E1", "A-E3"), required=True)
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
        help="BLOCKED legacy single-module pre_unseal_bundle builder",
    )
    build.add_argument("--module", choices=("A-E1", "A-E3", "A-E2"), required=True)
    build.add_argument("--run-id", required=True)
    build.add_argument("--artifact-root", type=Path, required=True)
    build.add_argument("--cache-root", type=Path, required=True)
    diagnostics = commands.add_parser(
        "formal-accredit-diagnostics",
        help="rebuild sealed-only fit/ceiling/leakage diagnostics for one completed G3 module",
    )
    diagnostics.add_argument("--module", choices=("A-E1", "A-E3", "A-E2"), required=True)
    diagnostics.add_argument("--run-id", required=True)
    diagnostics.add_argument("--artifact-root", type=Path, required=True)
    diagnostics.add_argument("--cache-root", type=Path, required=True)
    g3_build = commands.add_parser(
        "formal-g3-accredit-build",
        help="replay the completed A-E1/A-E3/A-E2 chain and publish sealed-only unified G3 accreditation",
    )
    g3_build.add_argument("--artifact-root", type=Path, required=True)
    g3_build.add_argument("--cache-root", type=Path, required=True)
    g3_build.add_argument("--a-e2-run-id", required=True)
    g3_build.add_argument("--output-dir", type=Path, required=True)
    consume = commands.add_parser(
        "formal-consume-test",
        help="unified G3 test evaluation: derive cohort from frozen authorities, evaluate all checkpoints + traditional methods, consume (no caller-supplied winner/module)",
    )
    consume.add_argument("--artifact-root", type=Path, required=True)
    consume.add_argument("--cache-root", type=Path, required=True)
    return parser


def resolve_staged(module: str, run_id: str, artifact_root: Path, cache_root: Path) -> dict:
    """Derive the staged A-E1/A-E3 selection ledger from a run's published selection trace.

    Production entry point (D8/C5): reads the module's immutable selection trace + receipt +
    ledger and appends the staged resolution ledger. Pending stages are computed from the
    run authority + frozen matrix; the caller never supplies winner/top4/baseline. A-E3 reads
    its predecessor binding from the manifest (bound at materialize time), so no predecessor
    argument is required here.
    """
    run_dir = Path(artifact_root) / module / run_id
    if module == "A-E3":
        return resolve_a_e3_staged_selection(
            study_root=STUDY_ROOT, run_dir=run_dir, cache_root=cache_root,
            module_id=module, run_id=run_id,
        )
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
        elif args.module == "A-E3":
            if not args.predecessor_run_id:
                raise SystemExit(
                    "FATAL: --predecessor-run-id is required for A-E3 formal-execute (the "
                    "completed A-E1 staged run that binds this A-E3 run's predecessor trace)")
            predecessor = _build_predecessor_trace(
                args.artifact_root, "A-E1", args.predecessor_run_id)
            payload = run_a_e3_staged(
                study_root=STUDY_ROOT,
                module_id=args.module,
                run_id=args.run_id,
                artifact_root=args.artifact_root,
                cache_root=args.cache_root,
                owner_id=args.owner_id,
                max_fits=args.max_fits,
                predecessor=predecessor,
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
    elif args.command == "formal-accredit-diagnostics":
        payload = diagnostics_build(args.module, args.run_id, args.artifact_root, args.cache_root)
    elif args.command == "formal-g3-accredit-build":
        payload = build_g3_accreditation(
            ae2_run_dir=args.artifact_root / "A-E2" / args.a_e2_run_id,
            artifact_root=args.artifact_root,
            cache_root=args.cache_root,
            study_root=STUDY_ROOT,
            output_dir=args.output_dir,
        )
    elif args.command == "formal-consume-test":
        raise SystemExit(
            "FATAL: formal-consume-test is BLOCKED. The unified G3 bundle/approval/manifest "
            "control plane (R3) must be verified and Codex-APPROVED before test consumption. "
            "This CLI entry refuses to execute until the G3 accreditation path is complete."
        )
    else:
        raise AssertionError(f"Unreachable command: {args.command}")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
