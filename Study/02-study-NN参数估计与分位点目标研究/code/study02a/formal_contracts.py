"""Fail-closed manifest and dependency contracts for Study/02 formal runs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

from .artifacts import write_manifest
from .formal_config import (
    APPROVED_BASE_MAX_EPOCHS,
    APPROVED_AMENDMENT_ID,
    APPROVED_AMENDMENT_SHA256,
    APPROVED_MAX_EPOCHS,
    APPROVED_MIN_EPOCHS,
    APPROVED_OVERRIDE_PATH,
    APPROVED_PATIENCE,
    EffectiveFormalConfig,
)


FROZEN_MATRIX_SHA256 = "fad701af2e2084bf7ce8f678d642410af58057b4ae33029c9150e50971fdf6b1"
FROZEN_MATRIX_ROWS = 820
APPROVED_SCREENING_SEEDS = (420001, 420002, 420003)
APPROVED_FORMAL_SEEDS = tuple(range(420101, 420111))
APPROVED_BASE_PROTOCOL_ID = "A-G2-v1"
APPROVED_BASE_PROTOCOL_SHA256 = "f82e078051d760d7c9c11ece54b8fae7360c6db1aef3229a97b4fcd92ae01a11"
APPROVED_BASE_SEARCH_ID = "A-G2-search-v1"
APPROVED_BASE_SEARCH_SHA256 = "abd6d17b1d2467e1253e0154adba0b6582a3feeb83ed889534ed4f6ab5e0ca13"
APPROVED_EFFECTIVE_CONFIG_SHA256 = "44fba47c7af66166e1d3f11890299a8bb5c352ac1abf3447cd00cfd3acf97449"
_SHA256_RE = re.compile(r"[0-9a-fA-F]{64}")
_CODE_COMMIT_RE = re.compile(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}")
_PREDECESSOR_BY_MODULE = {"A-E1": None, "A-E3": "A-E1", "A-E2": "A-E3"}
_MATRIX_FIELDS = {"fit_id", "rule_id", "module", "test_state"}


@dataclass(frozen=True)
class PredecessorTrace:
    """Immutable declaration binding a downstream run to exact trace bytes."""

    module_id: str
    run_id: str
    trace_path: Path
    trace_sha256: str


@dataclass(frozen=True)
class RoleNamespaces:
    """Immutable training/validation seed namespace declaration."""

    training: str
    validation: str


def _require_sha256(value: str, label: str) -> str:
    if not isinstance(value, str) or _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{label} must be a 64-character SHA-256")
    return value.lower()


def _validate_effective_config(config: EffectiveFormalConfig) -> None:
    if not isinstance(config, EffectiveFormalConfig):
        raise ValueError("effective_config must be an EffectiveFormalConfig")
    for label, value in (
        ("base_protocol_sha256", config.base_protocol_sha256),
        ("base_search_sha256", config.base_search_sha256),
        ("amendment_sha256", config.amendment_sha256),
        ("effective_config_sha256", config.effective_config_sha256),
    ):
        _require_sha256(value, label)
    for label, value in (
        ("base_protocol_id", config.base_protocol_id),
        ("base_search_id", config.base_search_id),
        ("amendment_id", config.amendment_id),
    ):
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label} is required")
    approved_provenance = (
        ("base_protocol_id", config.base_protocol_id, APPROVED_BASE_PROTOCOL_ID),
        ("base_protocol_sha256", config.base_protocol_sha256, APPROVED_BASE_PROTOCOL_SHA256),
        ("base_search_id", config.base_search_id, APPROVED_BASE_SEARCH_ID),
        ("base_search_sha256", config.base_search_sha256, APPROVED_BASE_SEARCH_SHA256),
        ("amendment_id", config.amendment_id, APPROVED_AMENDMENT_ID),
        ("amendment_sha256", config.amendment_sha256, APPROVED_AMENDMENT_SHA256),
        ("effective_config_sha256", config.effective_config_sha256, APPROVED_EFFECTIVE_CONFIG_SHA256),
    )
    for label, actual, approved in approved_provenance:
        if actual != approved:
            raise ValueError(f"effective config {label} does not match the approved authority")
    expected = (
        ("max_epochs", config.max_epochs, APPROVED_MAX_EPOCHS),
        ("min_epochs", config.min_epochs, APPROVED_MIN_EPOCHS),
        ("patience", config.patience, APPROVED_PATIENCE),
        ("base_max_epochs", config.base_max_epochs, APPROVED_BASE_MAX_EPOCHS),
    )
    for label, actual, approved in expected:
        if actual != approved:
            raise ValueError(f"effective config {label} must be exactly {approved}; got {actual!r}")
    if tuple(config.approved_override_paths) != (APPROVED_OVERRIDE_PATH,):
        raise ValueError("effective config approved override paths mismatch")


def _validate_namespaces(value: Mapping[str, str] | RoleNamespaces) -> RoleNamespaces:
    if isinstance(value, RoleNamespaces):
        namespaces = value
    elif isinstance(value, Mapping):
        try:
            namespaces = RoleNamespaces(training=value["training"], validation=value["validation"])
        except KeyError as exc:
            raise ValueError(f"Missing role namespace: {exc.args[0]}") from exc
    else:
        raise ValueError("role_namespaces must declare training and validation")
    if not all(isinstance(item, str) and item.strip() for item in (namespaces.training, namespaces.validation)):
        raise ValueError("training and validation namespaces must be non-empty strings")
    if namespaces.training == namespaces.validation:
        raise ValueError("training and validation namespaces must be distinct")
    return namespaces


def _validate_seeds(values: Sequence[int], label: str, approved: tuple[int, ...]) -> tuple[int, ...]:
    if isinstance(values, (str, bytes)):
        raise ValueError(f"{label} seeds must be a non-empty integer sequence")
    seeds = tuple(values)
    if not seeds or any(isinstance(seed, bool) or not isinstance(seed, int) for seed in seeds):
        raise ValueError(f"{label} seeds must be a non-empty integer sequence")
    if len(set(seeds)) != len(seeds):
        raise ValueError(f"{label} seeds must be unique")
    if seeds != approved:
        raise ValueError(f"{label} seeds must match the frozen formal contract exactly")
    return seeds


def _validate_matrix(
    matrix_path: Path,
    module_id: str,
    rule_ids: Sequence[str],
    fit_ids: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    path = Path(matrix_path)
    if not path.is_file():
        raise ValueError(f"Formal matrix file is missing: {path}")
    try:
        matrix_bytes = path.read_bytes()
        matrix_text = matrix_bytes.decode("utf-8")
        reader = csv.DictReader(io.StringIO(matrix_text, newline=""))
        if reader.fieldnames is None or not _MATRIX_FIELDS.issubset(reader.fieldnames):
            raise ValueError("Formal matrix is missing required columns")
        rows = list(reader)
    except (OSError, UnicodeError, csv.Error) as exc:
        raise ValueError(f"Formal matrix cannot be read: {exc}") from exc

    if len(rows) != FROZEN_MATRIX_ROWS:
        raise ValueError(f"Formal matrix must contain exactly {FROZEN_MATRIX_ROWS} rows; got {len(rows)}")
    matrix_fit_ids = [row["fit_id"] for row in rows]
    if any(not fit_id for fit_id in matrix_fit_ids) or len(set(matrix_fit_ids)) != len(matrix_fit_ids):
        raise ValueError("Formal matrix must contain unique fit_id values")
    if any(row["test_state"] != "sealed" for row in rows):
        raise ValueError("Every formal matrix row must remain sealed")
    actual_digest = hashlib.sha256(matrix_bytes).hexdigest()
    if actual_digest != FROZEN_MATRIX_SHA256:
        raise ValueError(
            f"Formal matrix SHA-256 mismatch: expected {FROZEN_MATRIX_SHA256}, got {actual_digest}"
        )

    requested_rules = tuple(rule_ids)
    requested_fits = tuple(fit_ids)
    if not requested_rules or not requested_fits:
        raise ValueError("Formal rule/fit subset must be non-empty")
    if len(set(requested_rules)) != len(requested_rules) or len(set(requested_fits)) != len(requested_fits):
        raise ValueError("Formal rule/fit subset identifiers must be unique")
    known_rules = {row["rule_id"] for row in rows}
    missing_rules = set(requested_rules) - known_rules
    if missing_rules:
        raise ValueError(f"Requested rule IDs do not exist: {sorted(missing_rules)}")
    by_fit = {row["fit_id"]: row for row in rows}
    missing_fits = set(requested_fits) - set(by_fit)
    if missing_fits:
        raise ValueError(f"Requested fit IDs do not exist: {sorted(missing_fits)}")
    selected = [by_fit[fit_id] for fit_id in requested_fits]
    wrong_modules = sorted({row["module"] for row in selected if row["module"] != module_id})
    if wrong_modules:
        raise ValueError(f"Requested fits do not belong to module {module_id}: {wrong_modules}")
    selected_rules = {row["rule_id"] for row in selected}
    if selected_rules != set(requested_rules):
        raise ValueError("Requested rule IDs and fit IDs do not agree exactly")
    return requested_rules, requested_fits


def _coerce_predecessor(value: Mapping[str, Any] | PredecessorTrace) -> PredecessorTrace:
    if isinstance(value, PredecessorTrace):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("Downstream formal module requires predecessor selection trace metadata")
    try:
        return PredecessorTrace(
            module_id=value["module_id"],
            run_id=value["run_id"],
            trace_path=Path(value["trace_path"]),
            trace_sha256=value["trace_sha256"],
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("Incomplete predecessor selection trace metadata") from exc


def _validate_predecessor(
    module_id: str,
    value: Mapping[str, Any] | PredecessorTrace | None,
) -> dict[str, str]:
    expected_module = _PREDECESSOR_BY_MODULE[module_id]
    if expected_module is None:
        if value is not None:
            raise ValueError("A-E1 requires exactly no predecessor")
        return {"module_id": "none", "selection_trace_path": "none", "selection_trace_sha256": "none"}

    predecessor = _coerce_predecessor(value)
    if predecessor.module_id != expected_module:
        raise ValueError(
            f"Wrong predecessor module for {module_id}: expected {expected_module}, got {predecessor.module_id!r}"
        )
    if not isinstance(predecessor.run_id, str) or not predecessor.run_id.strip():
        raise ValueError("Predecessor trace run_id is required")
    declared_digest = _require_sha256(predecessor.trace_sha256, "Predecessor trace SHA-256")
    path = Path(predecessor.trace_path)
    if not path.is_file():
        raise ValueError(f"Predecessor selection trace is missing: {path}")
    trace_bytes = path.read_bytes()
    if not trace_bytes:
        raise ValueError("Predecessor selection trace must not be empty")
    actual_digest = hashlib.sha256(trace_bytes).hexdigest()
    if actual_digest != declared_digest:
        raise ValueError(
            f"Predecessor trace SHA-256 mismatch: declared {declared_digest}, actual {actual_digest}"
        )
    try:
        trace_text = trace_bytes.decode("utf-8")
        records = [json.loads(line) for line in trace_text.splitlines() if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Predecessor selection trace must be valid UTF-8 JSONL: {exc}") from exc
    if not records or any(not isinstance(record, dict) for record in records):
        raise ValueError("Predecessor selection trace must contain JSON objects")
    if any(record.get("module_id") != expected_module for record in records):
        raise ValueError("Predecessor selection trace module does not match declared dependency")
    if any(record.get("run_id") != predecessor.run_id for record in records):
        raise ValueError("Predecessor selection trace run does not match declared dependency")
    return {
        "module_id": predecessor.module_id,
        "run_id": predecessor.run_id,
        "selection_trace_path": str(path),
        "selection_trace_sha256": actual_digest,
    }


def build_formal_manifest(
    *,
    effective_config: EffectiveFormalConfig,
    module_id: str,
    run_id: str,
    code_commit: str,
    matrix_path: Path,
    rule_ids: Sequence[str],
    fit_ids: Sequence[str],
    role_namespaces: Mapping[str, str] | RoleNamespaces,
    screening_seeds: Sequence[int],
    formal_seeds: Sequence[int],
    predecessor: Mapping[str, Any] | PredecessorTrace | None,
) -> dict[str, Any]:
    """Validate every formal input, then return a write-free manifest."""

    if module_id not in _PREDECESSOR_BY_MODULE:
        raise ValueError(f"Unsupported formal module_id: {module_id!r}")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("run_id is required")
    if not isinstance(code_commit, str) or _CODE_COMMIT_RE.fullmatch(code_commit) is None:
        raise ValueError("code_commit must be a full 40- or 64-character hexadecimal commit ID")
    _validate_effective_config(effective_config)
    namespaces = _validate_namespaces(role_namespaces)
    screening = _validate_seeds(screening_seeds, "screening", APPROVED_SCREENING_SEEDS)
    formal = _validate_seeds(formal_seeds, "formal", APPROVED_FORMAL_SEEDS)
    requested_rules, requested_fits = _validate_matrix(matrix_path, module_id, rule_ids, fit_ids)
    predecessor_manifest = _validate_predecessor(module_id, predecessor)

    return {
        "manifest_version": "study02-formal-v1",
        "module_id": module_id,
        "run_id": run_id,
        "base_protocol": {
            "id": effective_config.base_protocol_id,
            "sha256": effective_config.base_protocol_sha256,
        },
        "base_search": {
            "id": effective_config.base_search_id,
            "sha256": effective_config.base_search_sha256,
        },
        "amendment": {
            "id": effective_config.amendment_id,
            "sha256": effective_config.amendment_sha256,
        },
        "effective_config": {
            "sha256": effective_config.effective_config_sha256,
            "max_epochs": effective_config.max_epochs,
            "min_epochs": effective_config.min_epochs,
            "patience": effective_config.patience,
        },
        "matrix": {
            "path": str(Path(matrix_path)),
            "sha256": FROZEN_MATRIX_SHA256,
            "row_count": FROZEN_MATRIX_ROWS,
            "rule_ids": list(requested_rules),
            "fit_ids": list(requested_fits),
        },
        "code_commit": code_commit.lower(),
        "role_namespaces": {
            "training": namespaces.training,
            "validation": namespaces.validation,
        },
        "seeds": {"screening": list(screening), "formal": list(formal)},
        "test_state": "sealed",
        "predecessor": predecessor_manifest,
    }


def build_and_write_formal_manifest(destination: Path, **manifest_kwargs: Any) -> dict[str, Any]:
    """Fully validate, then atomically create a previously absent manifest file."""

    manifest = build_formal_manifest(**manifest_kwargs)
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + f".{os.getpid()}.validated")
    if temporary.exists():
        raise FileExistsError(f"Formal manifest temporary destination already exists: {temporary}")
    try:
        write_manifest(manifest, temporary)
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)
    return manifest


__all__ = [
    "FROZEN_MATRIX_ROWS",
    "FROZEN_MATRIX_SHA256",
    "APPROVED_FORMAL_SEEDS",
    "APPROVED_SCREENING_SEEDS",
    "PredecessorTrace",
    "RoleNamespaces",
    "build_and_write_formal_manifest",
    "build_formal_manifest",
]
