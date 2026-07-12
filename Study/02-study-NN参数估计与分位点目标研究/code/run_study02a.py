"""Command-line entry point for auditable Study/02 research-A runs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


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
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "validate-config":
        payload = validate_config()
    elif args.command == "expand-matrix":
        payload = expand_matrix(args.output)
    elif args.command == "pilot":
        config = load_frozen_config(STUDY_ROOT)
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
        )
    else:
        raise AssertionError(f"Unreachable command: {args.command}")
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
