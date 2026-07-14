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
from study02a.formal_executor import run_module as run_formal_module


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
    return parser


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
        payload = run_formal_module(
            study_root=STUDY_ROOT,
            module_id=args.module,
            run_id=args.run_id,
            artifact_root=args.artifact_root,
            cache_root=args.cache_root,
            owner_id=args.owner_id,
            max_fits=args.max_fits,
        )
    else:
        raise AssertionError(f"Unreachable command: {args.command}")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
