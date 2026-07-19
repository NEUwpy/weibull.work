"""Approval-bound, fail-closed state transitions for one formal test access."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import threading
from typing import Any, Mapping


_SHA256 = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_BUNDLE_FIELDS = {
    "bundle_version", "code_commit", "effective_config_sha256", "module_run_ids",
    "selection_trace_hashes", "artifact_hashes", "test_state",
}
_APPROVAL_FIELDS = {
    "approval_version", "decision", "code_commit", "effective_config_sha256",
    "pre_unseal_bundle_sha256", "selection_trace_hashes", "ceiling_report_sha256",
    "leakage_audit_sha256", "oracle_review_artifact_sha256", "issued_at",
}
_STATE_FIELDS = {
    "state_version", "run_family_id", "state", "transition_seq", "code_commit",
    "effective_config_sha256", "pre_unseal_bundle_sha256", "approval_sha256",
    "result_receipt_sha256", "failure_receipt_sha256", "created_at", "updated_at",
    "test_access_count",
}
_EVENT_FIELDS = {
    "transition_version", "run_family_id", "transition", "seq", "before_state_sha256",
    "after_state_sha256", "approval_sha256", "pre_unseal_bundle_sha256",
    "result_receipt_sha256", "failure_receipt_sha256", "test_access_count", "timestamp",
}
_JOURNAL_FIELDS = {"event", "ledger_size_before", "ledger_sha_before"}
_EMPTY_SHA256 = hashlib.sha256(b"").hexdigest()


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise ValueError(f"{label} must be a lowercase 64-character SHA-256")
    return value


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _json_object(payload: bytes, label: str, fields: set[str], *, canonical: bool = True) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSON") from exc
    if not isinstance(value, dict) or set(value) != fields:
        raise ValueError(f"{label} must match its exact schema")
    if canonical and payload != _canonical(value):
        raise ValueError(f"{label} must use canonical JSON bytes")
    return value


def _validate_hash_map(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value or any(not isinstance(k, str) or not k for k in value):
        raise ValueError(f"{label} must be a non-empty object")
    for key, digest in value.items():
        _sha(digest, f"{label}[{key}]")
    return value


def _validate_bundle(payload: bytes) -> dict[str, Any]:
    bundle = _json_object(payload, "pre-unseal bundle", _BUNDLE_FIELDS)
    if bundle["bundle_version"] != "study02-pre-unseal-v3" or bundle["test_state"] != "sealed":
        raise ValueError("pre-unseal bundle must be the sealed v1 contract")
    if not isinstance(bundle["code_commit"], str) or _COMMIT.fullmatch(bundle["code_commit"]) is None:
        raise ValueError("pre-unseal bundle code_commit must be a full commit ID")
    _sha(bundle["effective_config_sha256"], "bundle effective_config_sha256")
    if not isinstance(bundle["module_run_ids"], dict) or not bundle["module_run_ids"]:
        raise ValueError("bundle module_run_ids must be non-empty")
    if any(not isinstance(k, str) or not k or not isinstance(v, str) or not v for k, v in bundle["module_run_ids"].items()):
        raise ValueError("bundle module_run_ids must bind non-empty strings")
    traces = _validate_hash_map(bundle["selection_trace_hashes"], "selection_trace_hashes")
    if set(traces) != set(bundle["module_run_ids"]):
        raise ValueError("selection trace hashes must cover module_run_ids exactly")
    _validate_hash_map(bundle["artifact_hashes"], "artifact_hashes")
    return bundle


def _validate_approval(payload: bytes, bundle: Mapping[str, Any], bundle_sha: str) -> dict[str, Any]:
    approval = _json_object(payload, "oracle approval", _APPROVAL_FIELDS)
    if approval["approval_version"] != "study02-test-unseal-approval-v1":
        raise ValueError("oracle approval version mismatch")
    if approval["decision"] != "APPROVE test unseal":
        raise ValueError("oracle approval decision must be literal APPROVE test unseal")
    if approval["code_commit"] != bundle["code_commit"]:
        raise ValueError("oracle approval code commit mismatch")
    if approval["effective_config_sha256"] != bundle["effective_config_sha256"]:
        raise ValueError("oracle approval effective config mismatch")
    if approval["pre_unseal_bundle_sha256"] != bundle_sha:
        raise ValueError("oracle approval bundle SHA-256 mismatch")
    if approval["selection_trace_hashes"] != bundle["selection_trace_hashes"]:
        raise ValueError("oracle approval selection trace hashes mismatch")
    for field in ("effective_config_sha256", "pre_unseal_bundle_sha256", "ceiling_report_sha256", "leakage_audit_sha256", "oracle_review_artifact_sha256"):
        _sha(approval[field], field)
    _validate_hash_map(approval["selection_trace_hashes"], "approval selection_trace_hashes")
    _text(approval["issued_at"], "issued_at")
    return approval


def _validate_evidence_paths(
    *,
    bundle: Mapping[str, Any],
    approval: Mapping[str, Any],
    ceiling_report_path: Path,
    leakage_audit_path: Path,
    oracle_review_path: Path,
) -> None:
    artifact_bindings: dict[Path, str] = {}
    for declared_path, declared_sha in bundle["artifact_hashes"].items():
        resolved = Path(declared_path).resolve(strict=False)
        if resolved in artifact_bindings:
            raise ValueError("bundle artifact paths must not alias")
        artifact_bindings[resolved] = declared_sha
    for role, path, approval_field in (
        ("ceiling", ceiling_report_path, "ceiling_report_sha256"),
        ("leakage", leakage_audit_path, "leakage_audit_sha256"),
    ):
        if path not in artifact_bindings:
            raise ValueError(f"{role} evidence path is not the path bound by the pre-unseal bundle")
        actual = _digest(path.read_bytes())
        if artifact_bindings[path] != approval[approval_field] or actual != approval[approval_field]:
            raise ValueError(f"{role} evidence exact-byte SHA-256 mismatch")
    if _digest(oracle_review_path.read_bytes()) != approval["oracle_review_artifact_sha256"]:
        raise ValueError("oracle review exact-byte SHA-256 mismatch")


def _validate_state(payload: bytes) -> dict[str, Any]:
    state = _json_object(payload, "formal state", _STATE_FIELDS)
    if state["state_version"] != "study02-formal-state-v1" or state["state"] not in {"sealed", "unsealed_once", "consumed"}:
        raise ValueError("formal state version/state is invalid")
    _text(state["run_family_id"], "run_family_id")
    if not isinstance(state["code_commit"], str) or _COMMIT.fullmatch(state["code_commit"]) is None:
        raise ValueError("formal state code_commit must be a full commit ID")
    _sha(state["effective_config_sha256"], "state effective_config_sha256")
    _sha(state["pre_unseal_bundle_sha256"], "state pre_unseal_bundle_sha256")
    for field in ("approval_sha256", "result_receipt_sha256", "failure_receipt_sha256"):
        if state[field] is not None:
            _sha(state[field], field)
    if isinstance(state["transition_seq"], bool) or not isinstance(state["transition_seq"], int) or state["transition_seq"] < 0:
        raise ValueError("formal state transition_seq is invalid")
    if isinstance(state["test_access_count"], bool) or state["test_access_count"] not in (0, 1):
        raise ValueError("formal state test_access_count is invalid")
    expected = {"sealed": (0, 0), "unsealed_once": (1, 1), "consumed": (2, 1)}[state["state"]]
    if (state["transition_seq"], state["test_access_count"]) != expected:
        raise ValueError("formal state skips or rolls back the mandatory sequence")
    if state["state"] == "sealed" and any(state[f] is not None for f in ("approval_sha256", "result_receipt_sha256", "failure_receipt_sha256")):
        raise ValueError("sealed state cannot carry receipts")
    if state["state"] == "unsealed_once" and (state["approval_sha256"] is None or state["result_receipt_sha256"] is not None or state["failure_receipt_sha256"] is not None):
        raise ValueError("unsealed_once state receipt contract is invalid")
    if state["state"] == "consumed" and (state["approval_sha256"] is None or ((state["result_receipt_sha256"] is None) == (state["failure_receipt_sha256"] is None))):
        raise ValueError("consumed state requires exactly one receipt")
    _text(state["created_at"], "created_at"); _text(state["updated_at"], "updated_at")
    return state


def _resolved_distinct(*paths: Path) -> tuple[Path, ...]:
    try:
        resolved = tuple(Path(path).resolve(strict=False) for path in paths)
    except (OSError, TypeError) as exc:
        raise ValueError("formal state paths cannot be resolved") from exc
    for index, first in enumerate(resolved):
        for second in resolved[index + 1:]:
            if first == second:
                raise ValueError("formal state, bundle, approval, and ledger paths must be distinct")
            if first.exists() and second.exists():
                try:
                    if first.samefile(second):
                        raise ValueError("formal state, bundle, approval, and ledger paths must be distinct")
                except OSError as exc:
                    raise ValueError("formal path identity cannot be verified") from exc
    return resolved


def _reject_internal_path_collisions(state_path: Path, *other_paths: Path) -> None:
    reserved = {
        state_path.with_name(state_path.name + ".lock"),
        state_path.with_name(state_path.name + ".journal"),
    }
    if any(path in reserved for path in other_paths):
        raise ValueError("bundle, approval, and ledger paths must be distinct from state artifacts")


def _publish_no_replace(payload: bytes, path: Path) -> None:
    if path.exists():
        raise FileExistsError(f"destination already exists: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.validated")
    try:
        temporary.write_bytes(payload)
        os.link(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _atomic_replace(payload: bytes, path: Path) -> None:
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    try:
        with temporary.open("xb") as handle:
            handle.write(payload); handle.flush(); os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def _append_ledger(entry: Mapping[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("ab") as handle:
        handle.write(_canonical(entry)); handle.flush(); os.fsync(handle.fileno())


def _ledger_rows(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = path.read_bytes().decode("utf-8")
        lines = payload.splitlines(keepends=True)
        rows = [json.loads(line) for line in lines if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError("transition ledger must be valid JSONL") from exc
    seen: set[tuple[str, int]] = set()
    if len(lines) != len(rows):
        raise ValueError("transition ledger must not contain blank records")
    for row, line in zip(rows, lines):
        if not isinstance(row, dict) or set(row) != _EVENT_FIELDS or line.encode("utf-8") != _canonical(row):
            raise ValueError("transition ledger event must match exact canonical schema")
        if row["transition_version"] != "study02-formal-transition-v1":
            raise ValueError("transition ledger version is invalid")
        expected = {"authorize_test_once": (1, 1), "consume_test_once": (2, 1)}.get(row["transition"])
        if expected is None or (row["seq"], row["test_access_count"]) != expected:
            raise ValueError("transition ledger state sequence is invalid")
        _text(row["run_family_id"], "ledger run_family_id")
        _text(row["timestamp"], "ledger timestamp")
        for field in ("before_state_sha256", "after_state_sha256", "approval_sha256", "pre_unseal_bundle_sha256"):
            _sha(row[field], f"ledger {field}")
        for field in ("result_receipt_sha256", "failure_receipt_sha256"):
            if row[field] is not None: _sha(row[field], f"ledger {field}")
        key = (row["run_family_id"], row["seq"])
        if key in seen:
            raise ValueError("transition ledger contains a duplicate or conflicting event")
        seen.add(key)
    return rows


def _validate_ledger_chain(
    state: Mapping[str, Any],
    state_bytes: bytes,
    rows: list[dict[str, Any]],
    *,
    bundle_sha: str,
    approval_sha: str,
) -> None:
    current = [row for row in rows if row["run_family_id"] == state["run_family_id"]]
    expected_count = {"sealed": 0, "unsealed_once": 1, "consumed": 2}[state["state"]]
    if len(current) != expected_count or [row["seq"] for row in current] != list(range(1, expected_count + 1)):
        raise ValueError("formal ledger chain does not match current state sequence")
    if not current:
        return

    sealed = {
        **state,
        "state": "sealed",
        "transition_seq": 0,
        "approval_sha256": None,
        "result_receipt_sha256": None,
        "failure_receipt_sha256": None,
        "updated_at": state["created_at"],
        "test_access_count": 0,
    }
    authorize = current[0]
    unsealed = {
        **state,
        "state": "unsealed_once",
        "transition_seq": 1,
        "approval_sha256": approval_sha,
        "result_receipt_sha256": None,
        "failure_receipt_sha256": None,
        "updated_at": authorize["timestamp"],
        "test_access_count": 1,
    }
    expected_authorize = {
        "transition_version": "study02-formal-transition-v1",
        "run_family_id": state["run_family_id"],
        "transition": "authorize_test_once",
        "seq": 1,
        "before_state_sha256": _digest(_canonical(sealed)),
        "after_state_sha256": _digest(_canonical(unsealed)),
        "approval_sha256": approval_sha,
        "pre_unseal_bundle_sha256": bundle_sha,
        "result_receipt_sha256": None,
        "failure_receipt_sha256": None,
        "test_access_count": 1,
        "timestamp": authorize["timestamp"],
    }
    if authorize != expected_authorize:
        raise ValueError("formal ledger chain authorize event is not exact")
    if state["state"] == "unsealed_once":
        if _digest(state_bytes) != authorize["after_state_sha256"]:
            raise ValueError("formal ledger chain after-state hash mismatch")
        return

    consume = current[1]
    expected_consume = {
        "transition_version": "study02-formal-transition-v1",
        "run_family_id": state["run_family_id"],
        "transition": "consume_test_once",
        "seq": 2,
        "before_state_sha256": authorize["after_state_sha256"],
        "after_state_sha256": _digest(state_bytes),
        "approval_sha256": approval_sha,
        "pre_unseal_bundle_sha256": bundle_sha,
        "result_receipt_sha256": state["result_receipt_sha256"],
        "failure_receipt_sha256": state["failure_receipt_sha256"],
        "test_access_count": 1,
        "timestamp": state["updated_at"],
    }
    if consume != expected_consume or _digest(_canonical(unsealed)) != consume["before_state_sha256"]:
        raise ValueError("formal ledger chain consume event is not exact")


def initialize_formal_state(*, state_path: Path, bundle_path: Path, run_family_id: str, code_commit: str, effective_config_sha256: str, timestamp: str) -> dict[str, Any]:
    state_path, bundle_path = _resolved_distinct(state_path, bundle_path)
    if state_path.exists():
        raise FileExistsError(f"formal state already exists: {state_path}")
    bundle_bytes = bundle_path.read_bytes()
    bundle = _validate_bundle(bundle_bytes)
    if code_commit != bundle["code_commit"] or effective_config_sha256 != bundle["effective_config_sha256"]:
        raise ValueError("initial state code/config must match pre-unseal bundle")
    state = {
        "state_version": "study02-formal-state-v1", "run_family_id": _text(run_family_id, "run_family_id"),
        "state": "sealed", "transition_seq": 0, "code_commit": code_commit,
        "effective_config_sha256": _sha(effective_config_sha256, "effective_config_sha256"),
        "pre_unseal_bundle_sha256": _digest(bundle_bytes), "approval_sha256": None,
        "result_receipt_sha256": None, "failure_receipt_sha256": None,
        "created_at": _text(timestamp, "timestamp"), "updated_at": timestamp, "test_access_count": 0,
    }
    _publish_no_replace(_canonical(state), state_path)
    return state


def publish_oracle_approval(*, approval_path: Path, approval_version: str, decision: str, code_commit: str, effective_config_sha256: str, pre_unseal_bundle_sha256: str, selection_trace_hashes: Mapping[str, str], ceiling_report_sha256: str, leakage_audit_sha256: str, oracle_review_artifact_sha256: str, issued_at: str) -> dict[str, Any]:
    approval = {
        "approval_version": approval_version, "decision": decision, "code_commit": code_commit,
        "effective_config_sha256": effective_config_sha256,
        "pre_unseal_bundle_sha256": pre_unseal_bundle_sha256,
        "selection_trace_hashes": dict(selection_trace_hashes),
        "ceiling_report_sha256": ceiling_report_sha256, "leakage_audit_sha256": leakage_audit_sha256,
        "oracle_review_artifact_sha256": oracle_review_artifact_sha256, "issued_at": issued_at,
    }
    # Schema and intrinsic types are checked here; bundle ownership is checked at authorization.
    _json_object(_canonical(approval), "oracle approval", _APPROVAL_FIELDS)
    if decision != "APPROVE test unseal" or approval_version != "study02-test-unseal-approval-v1":
        raise ValueError("oracle approval literal/version mismatch")
    if not isinstance(code_commit, str) or _COMMIT.fullmatch(code_commit) is None:
        raise ValueError("approval code_commit must be a full commit ID")
    for field in ("effective_config_sha256", "pre_unseal_bundle_sha256", "ceiling_report_sha256", "leakage_audit_sha256", "oracle_review_artifact_sha256"):
        _sha(approval[field], field)
    _validate_hash_map(approval["selection_trace_hashes"], "selection_trace_hashes")
    _text(issued_at, "issued_at")
    _publish_no_replace(_canonical(approval), Path(approval_path).resolve(strict=False))
    return approval


def _lock(path: Path) -> Path:
    lock = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError(f"formal state is locked: {path}") from exc
    os.close(fd)
    return lock


def _recover_journal(state_path: Path, ledger_path: Path) -> None:
    journal = state_path.with_name(state_path.name + ".journal")
    if not journal.exists():
        return
    record = _json_object(journal.read_bytes(), "transition journal", _JOURNAL_FIELDS)
    event = record["event"]
    if not isinstance(event, dict) or set(event) != _EVENT_FIELDS:
        raise ValueError("transition journal event must match exact schema")
    size_before = record["ledger_size_before"]
    if isinstance(size_before, bool) or not isinstance(size_before, int) or size_before < 0:
        raise ValueError("transition journal ledger_size_before is invalid")
    sha_before = _sha(record["ledger_sha_before"], "journal ledger_sha_before")
    ledger_bytes = ledger_path.read_bytes() if ledger_path.exists() else b""
    if len(ledger_bytes) < size_before or _digest(ledger_bytes[:size_before]) != sha_before:
        raise ValueError("transition journal ledger prefix conflicts with recorded snapshot")
    state_bytes = state_path.read_bytes()
    state_sha = _digest(state_bytes)
    if state_sha == event["before_state_sha256"]:
        if len(ledger_bytes) != size_before:
            raise ValueError("journal-before-state requires unchanged ledger snapshot")
        journal.unlink()
        return
    if state_sha != event["after_state_sha256"]:
        raise ValueError("transition journal matches neither before nor after state")

    event_bytes = _canonical(event)
    suffix = ledger_bytes[size_before:]
    if suffix == event_bytes:
        journal.unlink()
        return
    if not event_bytes.startswith(suffix):
        raise ValueError("journal-after-state ledger tail conflicts with exact event")
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with ledger_path.open("r+b" if ledger_path.exists() else "w+b") as handle:
        handle.truncate(size_before)
        handle.flush()
        os.fsync(handle.fileno())
    _append_ledger(event, ledger_path)
    journal.unlink()


def _transition(
    *, state_path: Path, bundle_path: Path, approval_path: Path, ledger_path: Path,
    timestamp: str, kind: str, ceiling_report_path: Path,
    leakage_audit_path: Path, oracle_review_path: Path,
    result_receipt_sha256: str | None = None, failure_receipt_sha256: str | None = None,
) -> dict[str, Any]:
    (
        state_path, bundle_path, approval_path, ledger_path, ceiling_report_path,
        leakage_audit_path, oracle_review_path,
    ) = _resolved_distinct(
        state_path, bundle_path, approval_path, ledger_path, ceiling_report_path,
        leakage_audit_path, oracle_review_path,
    )
    _reject_internal_path_collisions(
        state_path, bundle_path, approval_path, ledger_path, ceiling_report_path,
        leakage_audit_path, oracle_review_path,
    )
    lock = _lock(state_path)
    try:
        _recover_journal(state_path, ledger_path)
        rows = _ledger_rows(ledger_path)
        state_bytes = state_path.read_bytes(); state = _validate_state(state_bytes)
        bundle_bytes = bundle_path.read_bytes(); bundle = _validate_bundle(bundle_bytes); bundle_sha = _digest(bundle_bytes)
        approval_bytes = approval_path.read_bytes()
        approval = _validate_approval(approval_bytes, bundle, bundle_sha)
        approval_sha = _digest(approval_bytes)
        _validate_evidence_paths(
            bundle=bundle, approval=approval, ceiling_report_path=ceiling_report_path,
            leakage_audit_path=leakage_audit_path, oracle_review_path=oracle_review_path,
        )
        if state["code_commit"] != bundle["code_commit"] or state["effective_config_sha256"] != bundle["effective_config_sha256"] or state["pre_unseal_bundle_sha256"] != bundle_sha:
            raise ValueError("formal state binding differs from pre-unseal bundle")
        if state["state"] != "sealed" and state["approval_sha256"] != approval_sha:
            raise ValueError("formal state must retain the same approval SHA-256")
        _validate_ledger_chain(
            state, state_bytes, rows, bundle_sha=bundle_sha, approval_sha=approval_sha
        )
        if kind == "authorize_test_once":
            if state["state"] != "sealed" or state["test_access_count"] != 0:
                raise ValueError("authorize_test_once requires sealed state and access count 0")
            after = {**state, "state": "unsealed_once", "transition_seq": 1, "approval_sha256": approval_sha, "updated_at": _text(timestamp, "timestamp"), "test_access_count": 1}
        else:
            if state["state"] != "unsealed_once" or state["approval_sha256"] != approval_sha or state["test_access_count"] != 1:
                raise ValueError("consume_test_once requires unsealed_once state, same approval, and access count 1")
            if (result_receipt_sha256 is None) == (failure_receipt_sha256 is None):
                raise ValueError("consume_test_once requires exactly one result or failure receipt SHA-256")
            if result_receipt_sha256 is not None: _sha(result_receipt_sha256, "result receipt SHA-256")
            if failure_receipt_sha256 is not None: _sha(failure_receipt_sha256, "failure receipt SHA-256")
            after = {**state, "state": "consumed", "transition_seq": 2, "result_receipt_sha256": result_receipt_sha256, "failure_receipt_sha256": failure_receipt_sha256, "updated_at": _text(timestamp, "timestamp")}
        after_bytes = _canonical(after)
        event = {
            "transition_version": "study02-formal-transition-v1", "run_family_id": state["run_family_id"],
            "transition": kind, "seq": after["transition_seq"], "before_state_sha256": _digest(state_bytes),
            "after_state_sha256": _digest(after_bytes), "approval_sha256": approval_sha,
            "pre_unseal_bundle_sha256": bundle_sha, "result_receipt_sha256": after["result_receipt_sha256"],
            "failure_receipt_sha256": after["failure_receipt_sha256"], "test_access_count": after["test_access_count"],
            "timestamp": timestamp,
        }
        journal = state_path.with_name(state_path.name + ".journal")
        ledger_bytes_before = ledger_path.read_bytes() if ledger_path.exists() else b""
        journal_record = {
            "event": event,
            "ledger_size_before": len(ledger_bytes_before),
            "ledger_sha_before": _digest(ledger_bytes_before),
        }
        _publish_no_replace(_canonical(journal_record), journal)
        _atomic_replace(after_bytes, state_path)
        try:
            _append_ledger(event, ledger_path)
        except Exception as exc:
            raise RuntimeError(f"state transitioned but ledger append failed; recoverable journal retained: {journal}") from exc
        journal.unlink()
        return after
    finally:
        lock.unlink(missing_ok=True)


def authorize_test_once(
    *, state_path: Path, bundle_path: Path, approval_path: Path, ledger_path: Path,
    timestamp: str, ceiling_report_path: Path,
    leakage_audit_path: Path, oracle_review_path: Path,
) -> dict[str, Any]:
    return _transition(
        state_path=state_path, bundle_path=bundle_path, approval_path=approval_path,
        ledger_path=ledger_path, timestamp=timestamp, kind="authorize_test_once",
        ceiling_report_path=ceiling_report_path, leakage_audit_path=leakage_audit_path,
        oracle_review_path=oracle_review_path,
    )


def consume_test_once(
    *, state_path: Path, bundle_path: Path, approval_path: Path, ledger_path: Path,
    result_receipt_sha256: str | None, failure_receipt_sha256: str | None,
    timestamp: str, ceiling_report_path: Path,
    leakage_audit_path: Path, oracle_review_path: Path,
) -> dict[str, Any]:
    return _transition(
        state_path=state_path, bundle_path=bundle_path, approval_path=approval_path,
        ledger_path=ledger_path, timestamp=timestamp, kind="consume_test_once",
        result_receipt_sha256=result_receipt_sha256,
        failure_receipt_sha256=failure_receipt_sha256,
        ceiling_report_path=ceiling_report_path, leakage_audit_path=leakage_audit_path,
        oracle_review_path=oracle_review_path,
    )


__all__ = ["authorize_test_once", "consume_test_once", "initialize_formal_state", "publish_oracle_approval"]
