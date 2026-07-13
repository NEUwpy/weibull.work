"""Fail-closed planning and claim coordination for sealed Study/02 formal fits."""

from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import threading
import time
from typing import Any, Mapping

from .config import load_frozen_config
from .formal_config import load_effective_formal_config
from .formal_contracts import (
    APPROVED_FORMAL_SEEDS,
    APPROVED_SCREENING_SEEDS,
    FROZEN_MATRIX_ROWS,
    FROZEN_MATRIX_SHA256,
    build_formal_manifest,
)
from .formal_runner import build_training_spec, build_validation_spec
from .matrix import expand_module_matrix


_MODULE_RULES = {
    "A-E1": ("A-E1_historical", "A-E1_controlled", "A-E1_optimized_supplement"),
    "A-E3": ("A-E3_loss", "A-E3_architecture", "A-E3_joint_independent", "A-E3_fixed_shared"),
    "A-E2": ("A-E2_training_size", "A-E2_distribution"),
}
_MANIFEST = "manifest.json"
_PLAN = "plan.jsonl"
_STATE = "scheduler_state.json"
_LEDGER = "scheduler_ledger.jsonl"


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _identifier(value: str, label: str) -> str:
    if not isinstance(value, str) or not value or any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_." for char in value):
        raise ValueError(f"{label} must be a safe non-empty identifier")
    return value


def _reject_alias(path: Path) -> Path:
    path = Path(path).absolute()
    for current in (path, *path.parents):
        if not current.exists():
            continue
        try:
            info = current.lstat()
        except OSError as exc:
            raise ValueError(f"cannot inspect scheduler path: {current}") from exc
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0):
            raise ValueError(f"scheduler path aliases/reparse points are forbidden: {current}")
        if current.is_file() and info.st_nlink != 1:
            raise ValueError(f"scheduler hard-linked files are forbidden: {current}")
    return path


def _write_no_replace(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _replace(path: Path, payload: bytes) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _matrix_rows(study_root: Path, matrix_path: Path) -> list[dict[str, str]]:
    path = _reject_alias(matrix_path)
    payload = path.read_bytes()
    if _sha(payload) != FROZEN_MATRIX_SHA256:
        raise ValueError("formal matrix SHA-256 mismatch")
    try:
        rows = list(csv.DictReader(payload.decode("utf-8").splitlines()))
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("formal matrix is not valid canonical UTF-8 CSV") from exc
    if len(rows) != FROZEN_MATRIX_ROWS or len(rows) > 900:
        raise ValueError("formal matrix row count/cap mismatch")
    frozen = load_frozen_config(study_root)
    expected = [{key: str(value) for key, value in row.items()} for row in expand_module_matrix(frozen).to_dict("records")]
    if rows != expected:
        raise ValueError("formal matrix differs from independently reconstructed frozen order")
    if len({row["fit_id"] for row in rows}) != len(rows):
        raise ValueError("formal matrix contains duplicate fit identity")
    return rows


def _route_for_spec(route: str) -> str:
    return route.split(":", 1)[0]


def _distribution(row: Mapping[str, str]) -> str:
    if row["route"].startswith(("H0_", "H1")):
        return "legacy_grid"
    if row["route"].endswith(":legacy_grid"):
        return "legacy_grid"
    if row["route"].endswith(":extended_wide"):
        return "extended_wide"
    return "core_continuous"


def _plan_rows(study_root: Path, matrix_rows: list[dict[str, str]], module_id: str, run_id: str, cache_root: Path, code_commit: str, predecessor_hash: str) -> list[dict[str, Any]]:
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    selected = [row for row in matrix_rows if row["module"] == module_id]
    if not selected:
        raise ValueError(f"matrix has no rows for module {module_id}")
    result: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        route = _route_for_spec(row["route"])
        shared = row["n"] == "shared"
        fixed_n = None if shared else int(row["n"])
        n_mode = "shared_n" if shared else "fixed_n"
        distribution = _distribution(row)
        training_size = int(row["training_size"])
        if module_id == "A-E1":
            training = build_training_spec(route=route, distribution=distribution, n_mode=n_mode, fixed_n=fixed_n, training_rows=training_size, frozen_config=frozen, effective_config=effective)
            validation_distribution = "legacy_grid" if distribution == "legacy_grid" and route.startswith(("H0_", "H1")) else "core_continuous"
            validation = build_validation_spec(route=route, distribution=validation_distribution, n_mode=n_mode, fixed_n=fixed_n, frozen_config=frozen, effective_config=effective)
            training_key, validation_key = training.cache_key, validation.cache_key
        else:
            # Downstream symbolic selections are already bound to an immutable predecessor
            # receipt. Their eventual resolved data specs therefore key on that trace too.
            common_key = {
                "schema_version": "study02-formal-deferred-dataset-v1", "route": row["route"],
                "distribution": distribution, "n_mode": n_mode, "fixed_n": fixed_n,
                "training_size": training_size, "effective_config_sha256": effective.effective_config_sha256,
                "predecessor_trace_sha256": predecessor_hash,
            }
            training_key = _sha(_canonical({**common_key, "role": "training"}))
            validation_key = _sha(_canonical({**common_key, "role": "validation"}))
        output_dir = Path("outputs") / row["fit_id"]
        result.append({
            "plan_version": "study02-formal-plan-row-v1", "plan_index": index,
            "run_id": run_id, "fit_id": row["fit_id"], "fit_range": [int(row["fit_id"].rsplit("-", 1)[1])] * 2,
            "matrix_row_sha256": _sha(_canonical(row)), "module_id": module_id,
            "rule_id": row["rule_id"], "route": row["route"], "distribution": distribution,
            "n_mode": n_mode, "fixed_n": fixed_n, "loss": row["loss"],
            "architecture": row["architecture"], "optimizer": row["optimizer"],
            "training_size": training_size, "seed": int(row["seed"]),
            "effective_config_sha256": effective.effective_config_sha256,
            "code_commit": code_commit.lower(), "training_cache_key": training_key,
            "validation_cache_key": validation_key,
            "training_cache_path": str(cache_root / training_key),
            "validation_cache_path": str(cache_root / validation_key),
            "predecessor_trace_sha256": predecessor_hash,
            "expected_output_paths": [str(output_dir / "checkpoint.pt"), str(output_dir / "fit_status.json")],
            "test_access_count": 0,
        })
    return result


def _event(event_type: str, seq: int, previous_hash: str, payload: Mapping[str, Any]) -> dict[str, Any]:
    core = {"event_version": "study02-formal-scheduler-event-v1", "seq": seq, "event_type": event_type, "previous_event_sha256": previous_hash, "payload": dict(payload), "test_access_count": 0}
    return {**core, "event_sha256": _sha(_canonical(core))}


def _validate_ledger(path: Path) -> list[dict[str, Any]]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    previous = "0" * 64
    for seq, row in enumerate(rows):
        event_hash = row.get("event_sha256")
        core = {key: value for key, value in row.items() if key != "event_sha256"}
        if row.get("seq") != seq or row.get("previous_event_sha256") != previous or event_hash != _sha(_canonical(core)) or row.get("test_access_count") != 0:
            raise ValueError("scheduler ledger hash chain is invalid")
        previous = event_hash
    return rows


def _load(run_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    run_dir = _reject_alias(run_dir)
    for name in (_MANIFEST, _PLAN, _STATE, _LEDGER):
        _reject_alias(run_dir / name)
    manifest_bytes = (run_dir / _MANIFEST).read_bytes()
    manifest = json.loads(manifest_bytes)
    plan_bytes = (run_dir / _PLAN).read_bytes()
    if _sha(plan_bytes) != manifest["scheduler"]["plan_sha256"]:
        raise ValueError("formal plan hash mismatch")
    plan = [json.loads(line) for line in plan_bytes.decode("utf-8").splitlines()]
    if len(plan) != manifest["scheduler"]["fit_count"] or b"".join(_canonical(row) for row in plan) != plan_bytes:
        raise ValueError("formal plan canonical bytes/count mismatch")
    state_bytes = (run_dir / _STATE).read_bytes()
    state = json.loads(state_bytes)
    if state_bytes != _canonical(state) or state["plan_sha256"] != manifest["scheduler"]["plan_sha256"] or state["manifest_sha256"] != _sha(manifest_bytes):
        raise ValueError("scheduler state binding is invalid")
    ledger = _validate_ledger(run_dir / _LEDGER)
    if state["last_event_sha256"] != ledger[-1]["event_sha256"] or state["event_count"] != len(ledger):
        raise ValueError("scheduler state/ledger binding is invalid")
    fit_ids = {row["fit_id"] for row in plan}
    if set(state["fit_states"]) != fit_ids or any(value not in {"pending", "claimed", "succeeded", "failed"} for value in state["fit_states"].values()):
        raise ValueError("scheduler fit states do not match the exact plan")
    claim_hashes = {_sha(path.read_bytes()) for path in (run_dir / "claims").glob("*.json")} if (run_dir / "claims").exists() else set()
    for event in ledger:
        payload = event["payload"]
        if event["event_type"] == "fit_claimed" and payload["claim_receipt_sha256"] not in claim_hashes:
            raise ValueError("immutable claim receipt is missing or changed")
        if event["event_type"] in {"fit_succeeded", "fit_failed"}:
            terminal = event["event_type"].removeprefix("fit_")
            receipt_path = run_dir / "receipts" / f"{payload['fit_id']}.{terminal}.json"
            if not receipt_path.is_file() or _sha(receipt_path.read_bytes()) != payload["receipt_sha256"]:
                raise ValueError("immutable terminal receipt is missing or changed")
    return manifest, plan, state, ledger


def materialize_run(*, study_root: Path, matrix_path: Path, module_id: str, run_id: str, artifact_root: Path, cache_root: Path, code_commit: str, predecessor: Mapping[str, Any] | None) -> dict[str, Any]:
    module_id = _identifier(module_id, "module_id")
    run_id = _identifier(run_id, "run_id")
    if module_id not in _MODULE_RULES:
        raise ValueError("unsupported formal module")
    artifact_root = _reject_alias(artifact_root)
    cache_root = _reject_alias(cache_root)
    run_dir = artifact_root / module_id / run_id
    matrix_rows = _matrix_rows(study_root, matrix_path)
    effective = load_effective_formal_config(study_root)
    module_rows = [row for row in matrix_rows if row["module"] == module_id]
    rules = tuple(dict.fromkeys(row["rule_id"] for row in module_rows))
    fits = tuple(row["fit_id"] for row in module_rows)
    formal_manifest = build_formal_manifest(effective_config=effective, module_id=module_id, run_id=run_id, code_commit=code_commit, matrix_path=matrix_path, rule_ids=rules, fit_ids=fits, role_namespaces={"training": "study02/formal/training", "validation": "study02/formal/validation"}, screening_seeds=APPROVED_SCREENING_SEEDS, formal_seeds=APPROVED_FORMAL_SEEDS, predecessor=predecessor)
    predecessor_hash = formal_manifest["predecessor"]["selection_trace_sha256"]
    plan = _plan_rows(study_root, matrix_rows, module_id, run_id, cache_root, code_commit, predecessor_hash)
    plan_bytes = b"".join(_canonical(row) for row in plan)
    plan_sha = _sha(plan_bytes)
    manifest = {**formal_manifest, "scheduler": {"scheduler_version": "study02-formal-scheduler-v1", "fit_count": len(plan), "plan_sha256": plan_sha, "cache_root": str(cache_root), "test_access_count": 0}}
    manifest_bytes = _canonical(manifest)
    if run_dir.exists():
        existing_manifest, _, _, _ = _load(run_dir)
        if _canonical(existing_manifest) != manifest_bytes:
            raise ValueError("existing run bindings differ from requested inputs")
        return {"status": "existing_exact", "run_dir": str(run_dir), "plan_sha256": plan_sha, "fit_count": len(plan), "test_access_count": 0}
    stage = run_dir.with_name(f".{run_dir.name}.{os.getpid()}.{threading.get_ident()}.staging")
    if stage.exists():
        raise FileExistsError(f"scheduler staging path exists: {stage}")
    try:
        stage.mkdir(parents=True)
        _write_no_replace(stage / _PLAN, plan_bytes)
        _write_no_replace(stage / _MANIFEST, manifest_bytes)
        initial_event = _event("run_initialized", 0, "0" * 64, {"run_id": run_id, "module_id": module_id, "plan_sha256": plan_sha})
        _write_no_replace(stage / _LEDGER, _canonical(initial_event))
        state = {"state_version": "study02-formal-scheduler-state-v1", "run_id": run_id, "module_id": module_id, "plan_sha256": plan_sha, "manifest_sha256": _sha(manifest_bytes), "fit_states": {row["fit_id"]: "pending" for row in plan}, "live_claim": None, "event_count": 1, "last_event_sha256": initial_event["event_sha256"], "test_access_count": 0}
        _write_no_replace(stage / _STATE, _canonical(state))
        run_dir.parent.mkdir(parents=True, exist_ok=True)
        os.rename(stage, run_dir)
    except Exception:
        shutil.rmtree(stage, ignore_errors=True)
        raise
    return {"status": "created", "run_dir": str(run_dir), "plan_sha256": plan_sha, "fit_count": len(plan), "test_access_count": 0}


def _acquire(run_dir: Path) -> Path:
    lock = run_dir / ".scheduler.lock"
    for _ in range(200):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            time.sleep(0.005)
            continue
        os.close(fd)
        return lock
    raise ValueError("scheduler is locked")


def _mutate(run_dir: Path, state: dict[str, Any], ledger: list[dict[str, Any]], event_type: str, payload: Mapping[str, Any]) -> None:
    event = _event(event_type, len(ledger), ledger[-1]["event_sha256"], payload)
    with (run_dir / _LEDGER).open("ab") as handle:
        handle.write(_canonical(event)); handle.flush(); os.fsync(handle.fileno())
    state["event_count"] = len(ledger) + 1
    state["last_event_sha256"] = event["event_sha256"]
    _replace(run_dir / _STATE, _canonical(state))


def claim_next_fit(run_dir: Path, *, owner_id: str, process_id: int, timestamp: str) -> dict[str, Any]:
    run_dir = _reject_alias(run_dir)
    owner_id = _identifier(owner_id, "owner_id")
    if isinstance(process_id, bool) or not isinstance(process_id, int) or process_id <= 0:
        raise ValueError("process_id must be positive")
    lock = _acquire(run_dir)
    try:
        _, plan, state, ledger = _load(run_dir)
        if state["live_claim"] is not None:
            return {"status": "monitor_only", **state["live_claim"]}
        row = next((item for item in plan if state["fit_states"][item["fit_id"]] == "pending"), None)
        if row is None:
            return {"status": "exhausted"}
        existing_outputs = [str(run_dir / path) for path in row["expected_output_paths"] if (run_dir / path).exists()]
        if existing_outputs:
            raise ValueError(f"pending fit has conflicting scientific output: {existing_outputs}")
        claim_seq = sum(1 for item in ledger if item["event_type"] == "fit_claimed")
        expected = [str(run_dir / path) for path in row["expected_output_paths"]]
        claim = {"claim_version": "study02-formal-claim-v1", "run_id": state["run_id"], "fit_id": row["fit_id"], "owner_id": owner_id, "process_id": process_id, "started_at": timestamp, "expected_output_paths": expected, "predecessor_event_sha256": ledger[-1]["event_sha256"], "fit_identity_sha256": _sha(_canonical(row)), "test_access_count": 0}
        claim_path = run_dir / "claims" / f"{row['fit_id']}.{claim_seq:04d}.json"
        _write_no_replace(claim_path, _canonical(claim))
        state["fit_states"][row["fit_id"]] = "claimed"
        state["live_claim"] = {**claim, "claim_receipt_path": str(claim_path)}
        _mutate(run_dir, state, ledger, "fit_claimed", {"fit_id": row["fit_id"], "claim_receipt_sha256": _sha(claim_path.read_bytes())})
        return {"status": "claimed", **state["live_claim"]}
    finally:
        lock.unlink(missing_ok=True)


def _pid_live(process_id: int) -> bool:
    try:
        os.kill(process_id, 0)
    except (OSError, ValueError):
        return False
    return True


def recover_claim(run_dir: Path, *, timestamp: str) -> dict[str, Any]:
    run_dir = _reject_alias(run_dir)
    lock = _acquire(run_dir)
    try:
        _, _, state, ledger = _load(run_dir)
        claim = state["live_claim"]
        if claim is None:
            return {"status": "clean_pending"}
        if _pid_live(claim["process_id"]):
            return {"status": "monitor_only", **claim}
        if any(Path(path).exists() for path in claim["expected_output_paths"]):
            raise ValueError("stale claim has partial/conflicting scientific output")
        state["fit_states"][claim["fit_id"]] = "pending"
        state["live_claim"] = None
        _mutate(run_dir, state, ledger, "claim_recovered", {"fit_id": claim["fit_id"], "timestamp": timestamp, "reason": "dead_process_no_outputs"})
        return {"status": "released_to_pending", "fit_id": claim["fit_id"]}
    finally:
        lock.unlink(missing_ok=True)


def _terminal(run_dir: Path, *, fit_id: str, owner_id: str, terminal_state: str, details: Mapping[str, Any], timestamp: str) -> dict[str, Any]:
    run_dir = _reject_alias(run_dir)
    lock = _acquire(run_dir)
    try:
        _, _, state, ledger = _load(run_dir)
        claim = state["live_claim"]
        if claim is None or claim["fit_id"] != fit_id or claim["owner_id"] != owner_id or state["fit_states"].get(fit_id) != "claimed":
            raise ValueError("terminal receipt does not own the live claim")
        receipt = {"receipt_version": "study02-formal-fit-terminal-v1", "run_id": state["run_id"], "fit_id": fit_id, "owner_id": owner_id, "state": terminal_state, "details": dict(details), "timestamp": timestamp, "claim_receipt_sha256": _sha(Path(claim["claim_receipt_path"]).read_bytes()), "test_access_count": 0}
        receipt_path = run_dir / "receipts" / f"{fit_id}.{terminal_state}.json"
        _write_no_replace(receipt_path, _canonical(receipt))
        state["fit_states"][fit_id] = terminal_state
        state["live_claim"] = None
        _mutate(run_dir, state, ledger, f"fit_{terminal_state}", {"fit_id": fit_id, "receipt_sha256": _sha(receipt_path.read_bytes())})
        return {**receipt, "receipt_path": str(receipt_path)}
    finally:
        lock.unlink(missing_ok=True)


def record_fit_failed(run_dir: Path, *, fit_id: str, owner_id: str, failure_code: str, timestamp: str) -> dict[str, Any]:
    return _terminal(run_dir, fit_id=fit_id, owner_id=owner_id, terminal_state="failed", details={"failure_code": _identifier(failure_code, "failure_code")}, timestamp=timestamp)


def record_fit_succeeded(run_dir: Path, *, fit_id: str, owner_id: str, output_hashes: Mapping[str, str], timestamp: str) -> dict[str, Any]:
    for path, declared in output_hashes.items():
        payload = Path(path).read_bytes()
        if _sha(payload) != declared:
            raise ValueError("scientific output hash mismatch")
    return _terminal(run_dir, fit_id=fit_id, owner_id=owner_id, terminal_state="succeeded", details={"output_hashes": dict(output_hashes)}, timestamp=timestamp)


def status_run(run_dir: Path) -> dict[str, Any]:
    manifest, _, state, _ = _load(run_dir)
    counts = {name: sum(value == name for value in state["fit_states"].values()) for name in ("pending", "claimed", "succeeded", "failed")}
    return {"run_id": state["run_id"], "module_id": state["module_id"], "plan_sha256": state["plan_sha256"], "manifest_sha256": state["manifest_sha256"], "matrix_sha256": manifest["matrix"]["sha256"], "effective_config_sha256": manifest["effective_config"]["sha256"], "counts": counts, "live_claim": state["live_claim"], "test_access_count": 0}


__all__ = ["claim_next_fit", "materialize_run", "record_fit_failed", "record_fit_succeeded", "recover_claim", "status_run"]
