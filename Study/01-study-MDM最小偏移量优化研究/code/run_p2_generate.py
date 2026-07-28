"""Generate the frozen Study01 P2 risk curves.

The formal entry point is sealed by ``P2_FORMAL_AUTHORIZED``.  Smoke runs use
temporary output and never write the formal directory.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import platform
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

CODE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(CODE_DIR))

from config import PLATFORM_ROOT, STUDY_ROOT  # noqa: E402
from p2_config import (  # noqa: E402
    DELTA_GRID,
    ETA,
    OUTPUT_DIR_NAME,
    P2_APPROVED_PARENT_COMMIT,
    P2_FORMAL_AUTHORIZED,
    P2_RUN_ID,
    P2_TOTAL_COMBOS,
    REPEATS,
    SEED_NAMESPACE,
    build_p2_combos,
)

sys.path.insert(0, PLATFORM_ROOT)
from methods.mdm import MDM  # noqa: E402
from studies.common.sample import generate_sample  # noqa: E402

PROJECT_ROOT = Path(STUDY_ROOT).parents[1]
FORMAL_DIR = Path(STUDY_ROOT) / "artifacts" / "formal" / OUTPUT_DIR_NAME
CHUNKS_DIR = FORMAL_DIR / "chunks"
PROGRESS_PATH = FORMAL_DIR / "progress.json"
RUN_CONTEXT_PATH = FORMAL_DIR / "run_context.json"
MANIFEST_PATH = FORMAL_DIR / "manifest.json"
SHA256SUMS_PATH = FORMAL_DIR / "SHA256SUMS"

MDM_FIELDS = [
    "track",
    "combo_id",
    "beta",
    "eta",
    "gamma",
    "gamma_over_eta",
    "n",
    "repeat_id",
    "sample_sha256",
    "delta",
    "beta_hat",
    "eta_hat",
    "gamma_hat",
    "r_squared",
    "converged",
    "time_ms",
    "status",
    "failure_reason",
]


class P2GenerationError(RuntimeError):
    """Fail-closed P2 generation error."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_text_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    if temp.exists():
        raise P2GenerationError(f"stale partial file exists: {temp}")
    try:
        temp.write_text(text, encoding="utf-8")
        os.replace(temp, path)
    finally:
        if temp.exists():
            temp.unlink()


def _write_json_atomic(path: Path, value: dict) -> None:
    _write_text_atomic(
        path, json.dumps(value, ensure_ascii=False, indent=2)
    )


def _sample_sha256(sample: np.ndarray) -> str:
    rounded = np.round(np.asarray(sample, dtype=float), 12)
    return hashlib.sha256(rounded.tobytes()).hexdigest()


def reconstruct_sample(beta: float, ge: float, n: int, repeat_id: int) -> np.ndarray:
    """Use the shared deterministic namespace contract directly."""
    return generate_sample(
        beta=float(beta),
        eta=ETA,
        gamma=float(ge) * ETA,
        n=int(n),
        repeat_id=int(repeat_id),
        seed=SEED_NAMESPACE,
    )


def _combo_id(track: str, beta: float, ge: float, n: int) -> str:
    return f"{track}_{beta:.2f}_{ge:.2f}_{int(n)}"


def _chunk_path(
    track: str, beta: float, ge: float, n: int, chunks_dir: Path = CHUNKS_DIR
) -> Path:
    return chunks_dir / f"{_combo_id(track, beta, ge, n)}.csv"


def _failure_reason(result: tuple, values: tuple[float, ...], sample: np.ndarray) -> str:
    beta_hat, eta_hat, gamma_hat, _ = values
    converged = bool(result[4]) if len(result) > 4 else True
    if not converged:
        return "not_converged"
    if not np.isfinite(values).all():
        return "non_finite"
    if beta_hat <= 0 or eta_hat <= 0:
        return "non_positive_beta_or_eta"
    if gamma_hat >= float(np.min(sample)):
        return "support_set_violation"
    return ""


def _run_one_sample(
    track: str, beta: float, ge: float, n: int, repeat_id: int
) -> list[dict]:
    gamma = ge * ETA
    combo_id = _combo_id(track, beta, ge, n)
    sample = reconstruct_sample(beta, ge, n, repeat_id)
    sample_hash = _sample_sha256(sample)
    rows = []
    for delta in DELTA_GRID:
        started = time.perf_counter()
        try:
            result = MDM(sample.tolist()).run(trace=False, offset=delta)
            values = tuple(float(result[i]) for i in range(4))
            reason = _failure_reason(result, values, sample)
            beta_hat, eta_hat, gamma_hat, r_squared = values
            converged = bool(result[4]) if len(result) > 4 else True
            status = "success" if not reason else "failed"
        except Exception as exc:  # preserve the reason; do not silently drop it
            beta_hat = eta_hat = gamma_hat = r_squared = np.nan
            converged = False
            status = "failed"
            reason = f"{type(exc).__name__}:{str(exc)[:160]}"
        rows.append(
            {
                "track": track,
                "combo_id": combo_id,
                "beta": beta,
                "eta": ETA,
                "gamma": gamma,
                "gamma_over_eta": ge,
                "n": n,
                "repeat_id": repeat_id,
                "sample_sha256": sample_hash,
                "delta": delta,
                "beta_hat": beta_hat,
                "eta_hat": eta_hat,
                "gamma_hat": gamma_hat,
                "r_squared": r_squared,
                "converged": converged,
                "time_ms": round((time.perf_counter() - started) * 1000, 3),
                "status": status,
                "failure_reason": reason,
            }
        )
    return rows


def validate_chunk(
    path: Path,
    expected_combo: tuple[str, float, float, int],
    repeats: int = REPEATS,
    expected_sha256: str | None = None,
) -> dict:
    """Validate one checkpoint from bytes through reconstructed sample hashes."""
    import pandas as pd

    if not path.is_file():
        raise P2GenerationError(f"missing chunk: {path}")
    if expected_sha256 and _sha256_file(path) != expected_sha256:
        raise P2GenerationError(f"chunk SHA256 mismatch: {path.name}")
    frame = pd.read_csv(path, keep_default_na=False)
    missing = sorted(set(MDM_FIELDS) - set(frame.columns))
    if missing:
        raise P2GenerationError(f"{path.name}: missing columns {missing}")
    expected_rows = repeats * len(DELTA_GRID)
    if len(frame) != expected_rows:
        raise P2GenerationError(
            f"{path.name}: rows={len(frame)}, expected={expected_rows}"
        )
    track, beta, ge, n = expected_combo
    expected_id = _combo_id(track, beta, ge, n)
    metadata = frame[
        ["track", "combo_id", "beta", "eta", "gamma_over_eta", "n"]
    ].drop_duplicates()
    if len(metadata) != 1:
        raise P2GenerationError(f"{path.name}: mixed combo metadata")
    actual = metadata.iloc[0]
    if (
        actual["track"] != track
        or actual["combo_id"] != expected_id
        or not np.isclose(float(actual["beta"]), beta, atol=1e-12, rtol=0)
        or not np.isclose(float(actual["eta"]), ETA, atol=1e-12, rtol=0)
        or not np.isclose(float(actual["gamma_over_eta"]), ge, atol=1e-12, rtol=0)
        or int(actual["n"]) != n
    ):
        raise P2GenerationError(f"{path.name}: combo metadata mismatch")
    if frame.duplicated(["repeat_id", "delta"]).any():
        raise P2GenerationError(f"{path.name}: duplicate repeat/delta keys")
    if set(frame["repeat_id"].astype(int)) != set(range(repeats)):
        raise P2GenerationError(f"{path.name}: repeat set mismatch")
    if set(np.round(frame["delta"].astype(float), 12)) != set(
        np.round(DELTA_GRID, 12)
    ):
        raise P2GenerationError(f"{path.name}: delta grid mismatch")
    counts = frame.groupby("repeat_id")["delta"].nunique()
    if not (counts == len(DELTA_GRID)).all():
        raise P2GenerationError(f"{path.name}: incomplete risk curve")
    sample_hashes = frame.groupby("repeat_id")["sample_sha256"].nunique()
    if not (sample_hashes == 1).all():
        raise P2GenerationError(f"{path.name}: inconsistent sample hashes")
    recorded = frame.groupby("repeat_id")["sample_sha256"].first()
    for repeat_id, digest in recorded.items():
        expected = _sample_sha256(reconstruct_sample(beta, ge, n, int(repeat_id)))
        if digest != expected:
            raise P2GenerationError(
                f"{path.name}: sample hash mismatch at repeat {repeat_id}"
            )
    allowed_status = {"success", "failed"}
    if not set(frame["status"]).issubset(allowed_status):
        raise P2GenerationError(f"{path.name}: invalid status values")
    failed = frame["status"] != "success"
    if (frame.loc[failed, "failure_reason"].astype(str).str.len() == 0).any():
        raise P2GenerationError(f"{path.name}: failed row missing failure_reason")
    return {
        "path": path.name,
        "sha256": _sha256_file(path),
        "rows": int(len(frame)),
        "samples": int(frame["repeat_id"].nunique()),
        "failures": int(failed.sum()),
    }


def _write_chunk_atomic(
    combo: tuple[str, float, float, int],
    chunks_dir: Path,
    repeats: int,
) -> dict:
    track, beta, ge, n = combo
    final_path = _chunk_path(track, beta, ge, n, chunks_dir)
    temp_path = final_path.with_suffix(final_path.suffix + ".tmp")
    if temp_path.exists():
        raise P2GenerationError(f"stale partial chunk exists: {temp_path}")
    rows: list[dict] = []
    for repeat_id in range(repeats):
        rows.extend(_run_one_sample(track, beta, ge, n, repeat_id))
    chunks_dir.mkdir(parents=True, exist_ok=True)
    try:
        with temp_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=MDM_FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        receipt = validate_chunk(temp_path, combo, repeats=repeats)
        os.replace(temp_path, final_path)
    finally:
        if temp_path.exists():
            temp_path.unlink()
    receipt["path"] = final_path.name
    receipt["sha256"] = _sha256_file(final_path)
    return receipt


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout.strip()


def _input_hashes() -> dict[str, str]:
    paths = {
        "p2_config": CODE_DIR / "p2_config.py",
        "generator": Path(__file__),
        "baseline_evaluator": CODE_DIR / "run_p2_evaluate.py",
        "vector_evaluator": CODE_DIR / "run_p2_vector_mlp.py",
        "mdm": Path(PLATFORM_ROOT) / "methods" / "mdm.py",
        "sample": Path(PLATFORM_ROOT) / "studies" / "common" / "sample.py",
        "e4_production": CODE_DIR / "run_E4_formal_validation.py",
    }
    return {
        name: _sha256_file(path)
        for name, path in paths.items()
        if path.is_file()
    }


def _new_run_context(command: list[str]) -> dict:
    worktree_status = _git("status", "--porcelain")
    if worktree_status:
        raise P2GenerationError(
            "worktree must be fully clean before formal execution"
        )
    import pandas
    import sklearn

    return {
        "run_id": P2_RUN_ID,
        "generation_commit": _git("rev-parse", "HEAD"),
        "approved_parent_commit": P2_APPROVED_PARENT_COMMIT,
        "exact_command": command,
        "started_at": _now_iso(),
        "worktree_dirty_before": False,
        "versions": {
            "python": platform.python_version(),
            "numpy": np.__version__,
            "pandas": pandas.__version__,
            "sklearn": sklearn.__version__,
        },
        "input_hashes": _input_hashes(),
    }


def _load_or_create_context(output_dir: Path, command: list[str]) -> dict:
    context_path = output_dir / "run_context.json"
    if context_path.exists():
        context = json.loads(context_path.read_text(encoding="utf-8"))
        if context.get("generation_commit") != _git("rev-parse", "HEAD"):
            raise P2GenerationError("generation commit changed during resume")
        if context.get("input_hashes") != _input_hashes():
            raise P2GenerationError("input code/config hashes changed during resume")
        return context
    if output_dir.exists() and any(output_dir.iterdir()):
        raise P2GenerationError(
            f"non-empty output has no valid run context: {output_dir}"
        )
    output_dir.mkdir(parents=True, exist_ok=True)
    context = _new_run_context(command)
    _write_json_atomic(context_path, context)
    return context


def _assert_smoke_output_safe(output_dir: Path) -> None:
    resolved = output_dir.resolve()
    formal = FORMAL_DIR.resolve()
    project = PROJECT_ROOT.resolve()
    if (
        resolved == formal
        or formal in resolved.parents
        or resolved in formal.parents
        or resolved == project
        or project in resolved.parents
    ):
        raise P2GenerationError(
            "smoke output must be outside the repository and formal output tree"
        )


def run_generation(
    output_dir: Path = FORMAL_DIR,
    combos: list[tuple[str, float, float, int]] | None = None,
    repeats: int = REPEATS,
    smoke: bool = False,
    command: list[str] | None = None,
) -> list[dict]:
    """Generate or resume validated chunks."""
    if smoke:
        _assert_smoke_output_safe(output_dir)
    else:
        if output_dir.resolve() != FORMAL_DIR.resolve():
            raise P2GenerationError("formal generation must use the frozen formal directory")
        if not P2_FORMAL_AUTHORIZED:
            raise P2GenerationError(
                "P2 formal execution is sealed; request exact-commit authorization"
            )
        if not P2_APPROVED_PARENT_COMMIT:
            raise P2GenerationError("approved parent commit is not bound")
        if _git("rev-parse", "HEAD^") != P2_APPROVED_PARENT_COMMIT:
            raise P2GenerationError(
                "formal execution HEAD is not the direct child of the approved parent"
            )
    combos = list(build_p2_combos() if combos is None else combos)
    command = list(sys.argv if command is None else command)
    context = _load_or_create_context(output_dir, command)
    chunks_dir = output_dir / "chunks"
    progress_path = output_dir / "progress.json"
    completed: dict[str, dict] = {}
    if progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        if progress.get("generation_commit") != context["generation_commit"]:
            raise P2GenerationError("progress generation commit mismatch")
        completed = {
            item["combo_id"]: item for item in progress.get("completed", [])
        }
    receipts = []
    for index, combo in enumerate(combos, start=1):
        combo_id = _combo_id(*combo)
        path = _chunk_path(*combo, chunks_dir=chunks_dir)
        if path.exists():
            expected_sha = completed.get(combo_id, {}).get("sha256")
            receipt = validate_chunk(
                path, combo, repeats=repeats, expected_sha256=expected_sha
            )
        else:
            if combo_id in completed:
                raise P2GenerationError(
                    f"progress claims missing checkpoint: {combo_id}"
                )
            print(f"[{index}/{len(combos)}] generating {combo_id}")
            receipt = _write_chunk_atomic(combo, chunks_dir, repeats)
        receipt["combo_id"] = combo_id
        receipts.append(receipt)
        progress = {
            "run_id": P2_RUN_ID,
            "generation_commit": context["generation_commit"],
            "expected_combos": len(combos),
            "repeats": repeats,
            "completed": receipts,
            "updated_at": _now_iso(),
        }
        _write_json_atomic(progress_path, progress)
    return receipts


def seal_outputs(
    output_dir: Path,
    receipts: list[dict],
    expected_combos: int,
    repeats: int,
) -> dict:
    if len(receipts) != expected_combos:
        raise P2GenerationError(
            f"cannot seal: {len(receipts)}/{expected_combos} combos"
        )
    context = json.loads((output_dir / "run_context.json").read_text(encoding="utf-8"))
    manifest = {
        "manifest_version": "study01-p2-generation-v2",
        "run_id": P2_RUN_ID,
        "authorization_baseline": context["generation_commit"],
        "generation_commit": context["generation_commit"],
        "created_at": _now_iso(),
        "combo_counts": {
            "P2-NI": sum(r["combo_id"].startswith("P2-NI") for r in receipts),
            "P2-PI": sum(r["combo_id"].startswith("P2-PI") for r in receipts),
            "total": len(receipts),
        },
        "repeats_per_combo": repeats,
        "delta_grid": DELTA_GRID,
        "eta": ETA,
        "seed_namespace": SEED_NAMESPACE,
        "exact_command": context["exact_command"],
        "versions": context["versions"],
        "worktree_dirty_before": context["worktree_dirty_before"],
        "input_hashes": context["input_hashes"],
        "chunks": receipts,
    }
    manifest_path = output_dir / "manifest.json"
    _write_json_atomic(manifest_path, manifest)
    paths = [output_dir / "run_context.json", output_dir / "progress.json", manifest_path]
    paths.extend(output_dir / "chunks" / r["path"] for r in receipts)
    lines = [
        f"{_sha256_file(path)}  {path.relative_to(output_dir).as_posix()}"
        for path in sorted(paths)
    ]
    _write_text_atomic(output_dir / "SHA256SUMS", "\n".join(lines) + "\n")
    return manifest


def run_smoke(output_dir: Path) -> dict:
    _assert_smoke_output_safe(output_dir)
    receipts = run_generation(
        output_dir=output_dir,
        combos=build_p2_combos()[:1],
        repeats=2,
        smoke=True,
        command=["run_p2_generate.py", "--smoke", str(output_dir)],
    )
    return seal_outputs(output_dir, receipts, expected_combos=1, repeats=2)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--smoke", type=Path)
    args = parser.parse_args()
    if args.status:
        if not FORMAL_DIR.exists():
            print("P2 v2 formal output: 0/39")
            return 0
        valid = 0
        for combo in build_p2_combos():
            path = _chunk_path(*combo)
            if path.exists():
                validate_chunk(path, combo)
                valid += 1
        print(f"P2 v2 formal output: {valid}/{P2_TOTAL_COMBOS}")
        return 0
    if args.smoke is not None:
        run_smoke(args.smoke.resolve())
        return 0
    receipts = run_generation()
    seal_outputs(FORMAL_DIR, receipts, P2_TOTAL_COMBOS, REPEATS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
