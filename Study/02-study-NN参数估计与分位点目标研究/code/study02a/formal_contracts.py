"""Fail-closed manifest and dependency contracts for Study/02 formal runs."""

from __future__ import annotations

import csv
from dataclasses import dataclass
import hashlib
import io
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Any, Mapping, Sequence

from .artifacts import append_ledger, write_manifest
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
# 64-character zero SHA-256 sentinel anchoring the first record of every staged-ledger
# hash chain (mirrors ``formal_executor._ZERO_HASH`` / ``formal_scheduler._ZERO_HASH`` so FC
# stays the single authority for staged-ledger validation without importing either module).
_ZERO_HASH_FC = "0" * 64
_PREDECESSOR_BY_MODULE = {"A-E1": None, "A-E3": "A-E1", "A-E2": "A-E3"}
# Control-plane v2: modules that publish a ``staged_resolution_ledger.jsonl`` whose SHA a
# downstream run must bind through PredecessorTrace (the on-disk authority for the
# module's deferred placeholders + final aliases). A-E1 publishes its 8-record chain
# (``resolve_a_e1_staged_selection``); A-E3 publishes its 9-record chain once its staged
# resolver is wired. The single authority for staged-ledger validation lives in FC
# (``_validate_staged_resolution_ledger``); G3 calls FC, never the reverse.
_PUBLISHES_STAGED_LEDGER = {"A-E1", "A-E3"}
_STAGED_LEDGER_RECORD_VERSION = "study02-staged-resolution-v1"
_STAGED_LEDGER_REQUIRED_FIELDS = {
    "record_version", "module_id", "run_id", "code_commit",
    "effective_config_sha256", "selection_trace_sha256", "stage", "route",
    "previous_record_sha256", "input", "resolution", "resolution_sha256",
    "record_sha256",
}
# Per-module canonical (stage, route) sequence for the staged resolution ledger. A-E1's
# 8-record chain is frozen (mirrors ``formal_g3_control._resolve_a_e1_from_staged_ledger``
# at FC1191-read-time); A-E3's 9-record chain is per the A-E3 orchestration design (section
# E). Semantic-order deviations are a tamper even when the hash chain is re-broken-and-rebuilt.
_STAGED_LEDGER_SEQUENCES: dict[str, tuple[tuple[str, str | None], ...]] = {
    "A-E1": (
        ("stage1", "F2"),
        ("stage2", "F2"),
        ("winner_retrain", "F2"),
        ("stage1", "V"),
        ("stage2", "V"),
        ("winner_retrain", "V"),
        ("baseline_input", None),
        ("final_aliases", None),
    ),
    "A-E3": (
        ("loss", None),
        ("stage1", "F2_or_V"),
        ("stage2", "F2_or_V"),
        ("stage1", "S"),
        ("stage2", "S"),
        ("output_form", None),
        ("shared_winner_retrain", "S"),
        ("baseline_route", None),
        ("final_aliases", None),
    ),
}
_MATRIX_FIELDS = {"fit_id", "rule_id", "module", "test_state"}
# v3 selection trace record schema. v2 lacked rule_diagnostics_sha256, so the
# exact-field-set check below inherently rejects v1/v2 traces (R3#2: v2/v3 mixing
# fails closed at the schema gate). Records are produced by
# study02a.selection.build_selection_trace from a DecisionSpec -- never assembled by
# callers -- and carry both the per-candidate supporting_evidence_sha256 (binding the
# point-evidence chain) AND the per-decision rule_diagnostics_sha256 (binding the
# bootstrap config, CIs, rule result and computed winner). The trace never relies on
# the `selected` flag alone.
_SELECTION_RECORD_FIELDS = {
    "module_id",
    "run_id",
    "decision_id",
    "candidate_id",
    "validation_score",
    "tie_break_key",
    "selected",
    "supporting_evidence_sha256",
    "rule_diagnostics_sha256",
    "support_count",
    "seed_count",
    "selection_rule",
}
_SELECTION_TRACE_VERSION = "study02-selection-trace-v3"
# Per-decision winner rules. "lowest_aggregate" (ranking) is enforced inside the trace
# validator (winner == argmin of validation_score). The CI/equal-weight rules are
# re-derived at pre-unseal from the bound supporting fits; the trace validator only
# checks exactly-one-winner for them.
SELECTION_RULE_LOWEST_AGGREGATE = "lowest_aggregate"
SELECTION_RULE_GLOBAL_BETTER = "global_better_rule"
SELECTION_RULE_SMALLEST_WITHIN_2PCT_CI = "smallest_within_2pct_ci"
SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT = "fixed_vs_shared_equal_weight"
_SELECTION_RULES = {
    SELECTION_RULE_LOWEST_AGGREGATE,
    SELECTION_RULE_GLOBAL_BETTER,
    SELECTION_RULE_SMALLEST_WITHIN_2PCT_CI,
    SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT,
}
_FIT_STATUS_FIELDS = (
    "fit_id",
    "module_id",
    "rule_id",
    "route_id",
    "n",
    "seed",
    "decision_id",
    "candidate_id",
    "selected",
    "checkpoint_sha256",
    "validation_score",
    "selection_score",
    "failure_penalty",
    "actual_epochs",
    "best_epoch_one_based",
    "hit_epoch_100",
    "early_stop_reason",
    "failed",
    "failure_message",
    "terminal_validation_slope",
    "validation_curve_json",
)
_EVIDENCE_ROLES = ("training", "validation", "calibration", "test")
_FROZEN_RULE_FIT_RANGES = {
    "A-E1_historical": (0, 29),
    "A-E1_controlled": (30, 104),
    "A-E1_optimized_supplement": (105, 348),
    "A-E3_loss": (349, 360),
    "A-E3_architecture": (361, 432),
    "A-E3_joint_independent": (433, 532),
    "A-E3_fixed_shared": (533, 614),
    "A-E2_training_size": (615, 724),
    "A-E2_distribution": (725, 819),
}
_FROZEN_MATRIX_PATH = (
    Path(__file__).resolve().parents[2]
    / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv"
).resolve()


@dataclass(frozen=True)
class PredecessorTrace:
    """Immutable declaration binding a downstream run to exact trace bytes."""

    module_id: str
    run_id: str
    trace_path: Path
    trace_sha256: str
    receipt_path: Path
    receipt_sha256: str
    ledger_path: Path
    selection_code_commit: str
    # Control-plane v2 (optional; required when the predecessor module publishes a staged
    # resolution ledger -- see ``_PUBLISHES_STAGED_LEDGER``). Defaults to ``None`` so A-E1
    # root (no predecessor) and legacy callers remain valid; ``_validate_predecessor``
    # fail-closes when a staged-ledger-publishing predecessor omits them.
    staged_ledger_path: Path | None = None
    staged_ledger_sha256: str | None = None


@dataclass(frozen=True)
class RoleNamespaces:
    """Immutable training/validation seed namespace declaration."""

    training: str
    validation: str


@dataclass(frozen=True)
class _VerifiedMatrixEvidence:
    path: Path
    payload: bytes
    identity: tuple[int, int, int, int]
    rows: tuple[dict[str, str], ...]


def _open_verified_matrix_evidence(matrix_path: Path) -> _VerifiedMatrixEvidence:
    path = Path(matrix_path).resolve(strict=False)
    if path != _FROZEN_MATRIX_PATH:
        raise ValueError("Formal matrix path must be the exact frozen repository path")
    try:
        info = path.lstat()
        if path.is_symlink() or not path.is_file() or info.st_nlink != 1:
            raise ValueError("Formal matrix must be one plain non-aliased file")
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno())
            payload = handle.read()
            after = os.fstat(handle.fileno())
        final = path.stat()
    except OSError as exc:
        raise ValueError(f"Formal matrix cannot be opened safely: {exc}") from exc
    identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or identity != (
        final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns
    ):
        raise ValueError("Formal matrix identity changed during its one-open snapshot")
    try:
        reader = csv.DictReader(io.StringIO(payload.decode("utf-8"), newline=""))
        if reader.fieldnames is None or not _MATRIX_FIELDS.issubset(reader.fieldnames):
            raise ValueError("Formal matrix is missing required columns")
        rows = tuple(reader)
    except (UnicodeError, csv.Error) as exc:
        raise ValueError(f"Formal matrix cannot be decoded: {exc}") from exc
    if len(rows) != FROZEN_MATRIX_ROWS or hashlib.sha256(payload).hexdigest() != FROZEN_MATRIX_SHA256:
        raise ValueError("Formal matrix row count or frozen SHA-256 mismatch")
    return _VerifiedMatrixEvidence(path=path, payload=payload, identity=identity, rows=rows)


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
    evidence: _VerifiedMatrixEvidence,
    module_id: str,
    rule_ids: Sequence[str],
    fit_ids: Sequence[str],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    if not isinstance(evidence, _VerifiedMatrixEvidence) or evidence.path != _FROZEN_MATRIX_PATH:
        raise ValueError("Formal matrix evidence must come from the internal one-open validator")
    rows = list(evidence.rows)

    if len(rows) != FROZEN_MATRIX_ROWS:
        raise ValueError(f"Formal matrix must contain exactly {FROZEN_MATRIX_ROWS} rows; got {len(rows)}")
    matrix_fit_ids = [row["fit_id"] for row in rows]
    if any(not fit_id for fit_id in matrix_fit_ids) or len(set(matrix_fit_ids)) != len(matrix_fit_ids):
        raise ValueError("Formal matrix must contain unique fit_id values")
    if any(row["test_state"] != "sealed" for row in rows):
        raise ValueError("Every formal matrix row must remain sealed")
    actual_digest = hashlib.sha256(evidence.payload).hexdigest()
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


def _read_jsonl(path: Path, label: str) -> tuple[bytes, list[dict[str, Any]]]:
    if not path.is_file():
        raise ValueError(f"{label} is missing: {path}")
    payload = path.read_bytes()
    return payload, _read_jsonl_bytes(payload, label)


def _safe_one_read(path: Path, label: str) -> bytes:
    path = Path(path)
    for current in (path, *path.parents):
        if not current.exists():
            continue
        info = current.lstat()
        reparse = getattr(info, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        if current.is_symlink() or reparse:
            raise ValueError(f"{label} path aliases/reparse points are forbidden")
    try:
        info = path.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ValueError(f"{label} must be one plain non-hardlinked file")
        with path.open("rb") as handle:
            before = os.fstat(handle.fileno()); payload = handle.read(); after = os.fstat(handle.fileno())
        final = path.stat()
    except OSError as exc:
        raise ValueError(f"{label} cannot be read safely: {exc}") from exc
    identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    if identity != (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns) or identity != (final.st_dev, final.st_ino, final.st_size, final.st_mtime_ns):
        raise ValueError(f"{label} identity changed during its one-read snapshot")
    return payload


def _read_jsonl_bytes(payload: bytes, label: str) -> list[dict[str, Any]]:
    if not payload:
        raise ValueError(f"{label} must not be empty")
    try:
        records = [json.loads(line) for line in payload.decode("utf-8").splitlines() if line.strip()]
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid UTF-8 JSONL: {exc}") from exc
    if not records or any(not isinstance(record, dict) for record in records):
        raise ValueError(f"{label} must contain JSON objects")
    return records


def _validate_selection_trace(
    path: Path,
    declared_sha256: str,
    module_id: str,
    run_id: str,
) -> tuple[str, int, int]:
    trace_bytes, _ = _read_jsonl(Path(path), "Predecessor selection trace")
    return _validate_selection_trace_bytes(trace_bytes, declared_sha256, module_id, run_id)


def _validate_selection_trace_bytes(
    trace_bytes: bytes,
    declared_sha256: str,
    module_id: str,
    run_id: str,
) -> tuple[str, int, int]:
    declared_digest = _require_sha256(declared_sha256, "Selection trace SHA-256")
    records = _read_jsonl_bytes(trace_bytes, "Predecessor selection trace")
    actual_digest = hashlib.sha256(trace_bytes).hexdigest()
    if actual_digest != declared_digest:
        raise ValueError(
            f"Predecessor trace SHA-256 mismatch: declared {declared_digest}, actual {actual_digest}"
        )

    pairs: set[tuple[str, str]] = set()
    by_decision: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        if set(record) != _SELECTION_RECORD_FIELDS:
            raise ValueError("selection trace record must match the frozen schema exactly")
        if record["module_id"] != module_id or record["run_id"] != run_id:
            raise ValueError("Predecessor selection trace ownership does not match declared module/run")
        decision_id = record["decision_id"]
        candidate_id = record["candidate_id"]
        if not isinstance(decision_id, str) or not decision_id.strip():
            raise ValueError("Predecessor selection trace decision_id must be a non-empty string")
        if not isinstance(candidate_id, str) or not candidate_id.strip():
            raise ValueError("Predecessor selection trace candidate_id must be a non-empty string")
        pair = (decision_id, candidate_id)
        if pair in pairs:
            raise ValueError("Predecessor selection trace decision/candidate pairs must be unique")
        pairs.add(pair)
        score = record["validation_score"]
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
            raise ValueError("Predecessor selection trace validation_score must be finite")
        if record["tie_break_key"] is None:
            raise ValueError("Predecessor selection trace tie_break_key is required")
        _tie_break_sort_key(record["tie_break_key"])
        if not isinstance(record["selected"], bool):
            raise ValueError("Predecessor selection trace selected must be boolean")
        _require_sha256(record["supporting_evidence_sha256"], "Selection trace supporting_evidence_sha256")
        _require_sha256(record["rule_diagnostics_sha256"], "Selection trace rule_diagnostics_sha256")
        support_count = record["support_count"]
        if isinstance(support_count, bool) or not isinstance(support_count, int) or support_count <= 0:
            raise ValueError("Predecessor selection trace support_count must be a positive integer")
        seed_count = record["seed_count"]
        if isinstance(seed_count, bool) or not isinstance(seed_count, int) or seed_count <= 0:
            raise ValueError("Predecessor selection trace seed_count must be a positive integer")
        if seed_count > support_count:
            raise ValueError("Predecessor selection trace seed_count cannot exceed support_count")
        if record["selection_rule"] not in _SELECTION_RULES:
            raise ValueError("Predecessor selection trace selection_rule is not a frozen rule")
        by_decision.setdefault(decision_id, []).append(record)
    for decision_id, decision_rows in by_decision.items():
        # Contract E: a decision's selection_rule must be unique (no mixed rules within one
        # decision). Two candidates of the same decision carrying different rules is a tamper.
        decision_rules = {row["selection_rule"] for row in decision_rows}
        if len(decision_rules) != 1:
            raise ValueError(
                f"selection trace decision {decision_id} mixes selection rules {sorted(decision_rules)!r}"
            )
        # R3#2: every candidate of one decision binds the SAME rule_diagnostics_sha256 (the
        # decision's diagnostics artifact); a divergence is a tamper.
        decision_diag = {row["rule_diagnostics_sha256"] for row in decision_rows}
        if len(decision_diag) != 1:
            raise ValueError(
                f"selection trace decision {decision_id} binds divergent rule_diagnostics_sha256 values"
            )
        ranked = sorted(
            decision_rows,
            key=lambda row: (
                row["validation_score"], _tie_break_sort_key(row["tie_break_key"]), row["candidate_id"]
            ),
        )
        selected = [row for row in decision_rows if row["selected"]]
        if len(selected) != 1:
            raise ValueError(f"selection trace decision {decision_id} must select exactly one winner")
        if ranked[0]["selection_rule"] == SELECTION_RULE_LOWEST_AGGREGATE:
            if selected[0]["candidate_id"] != ranked[0]["candidate_id"]:
                raise ValueError(
                    f"selection trace winner for {decision_id} does not equal deterministic frozen rank"
                )
    canonical = sorted(
        records,
        key=lambda row: (
            row["decision_id"], row["validation_score"],
            _tie_break_sort_key(row["tie_break_key"]), row["candidate_id"],
        ),
    )
    if records != canonical:
        raise ValueError("selection trace records are not in canonical order")
    canonical_bytes = b"".join(_canonical_json_bytes(record) for record in canonical)
    if trace_bytes != canonical_bytes:
        raise ValueError("selection trace must equal canonical JSONL bytes exactly")
    return actual_digest, len(records), len(by_decision)


def _publish_json_no_replace(payload: Mapping[str, Any], destination: Path) -> None:
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + f".{os.getpid()}.validated")
    if temporary.exists():
        raise FileExistsError(f"Temporary destination already exists: {temporary}")
    try:
        write_manifest(payload, temporary)
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _canonical_json_bytes(payload: Any) -> bytes:
    return (json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
        "utf-8"
    )


def _publish_bytes_no_replace(payload: bytes, destination: Path) -> None:
    destination = Path(destination)
    if destination.exists():
        raise FileExistsError(f"Destination already exists: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + f".{os.getpid()}.validated")
    if temporary.exists():
        raise FileExistsError(f"Temporary destination already exists: {temporary}")
    try:
        temporary.write_bytes(payload)
        os.link(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def _terminal_ols_slope(curve: Sequence[float]) -> float:
    values = tuple(float(value) for value in curve)
    if not values or any(not math.isfinite(value) for value in values):
        raise ValueError("validation history must contain finite values")
    terminal = values[-10:]
    if len(terminal) == 1:
        return 0.0
    x_mean = (len(terminal) - 1) / 2.0
    y_mean = sum(terminal) / len(terminal)
    numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(terminal))
    denominator = sum((index - x_mean) ** 2 for index in range(len(terminal)))
    return numerator / denominator


def _require_identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value


def _tie_break_sort_key(value: Any) -> tuple[Any, ...]:
    if value is None:
        return (0,)
    if isinstance(value, bool):
        return (1, int(value))
    if isinstance(value, (int, float)):
        if not math.isfinite(value):
            raise ValueError("selection tie_break_key numeric values must be finite")
        return (2, float(value))
    if isinstance(value, str):
        return (3, value)
    if isinstance(value, (list, tuple)):
        return (4, tuple(_tie_break_sort_key(item) for item in value))
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("selection tie_break_key object keys must be strings")
        return (5, tuple((key, _tie_break_sort_key(value[key])) for key in sorted(value)))
    raise ValueError("selection tie_break_key must contain only JSON values")


def build_fit_status_record(
    *,
    fit_id: str,
    module_id: str,
    rule_id: str,
    route_id: str,
    n: int | str,
    seed: int,
    decision_id: str,
    candidate_id: str,
    selected: bool,
    result: Any | None = None,
    selection_score: float | None = None,
    failure_penalty: float | None = None,
    failure_message: str | None = None,
) -> dict[str, Any]:
    """Build one validated fit-status row; best_epoch_one_based is explicitly one based.

    ``validation_score`` is the training best validation loss (bound to the curve, used by
    the ceiling report). ``selection_score`` is the recomputed failure-penalized L_param
    derived from the checkpoint (used by selection); failed fits leave it empty and carry
    the frozen ``failure_penalty`` instead. Selection never treats one checkpoint as
    representing multiple seeds.
    """

    identifiers = {
        "fit_id": _require_identifier(fit_id, "fit_id"),
        "module_id": _require_identifier(module_id, "module_id"),
        "rule_id": _require_identifier(rule_id, "rule_id"),
        "route_id": _require_identifier(route_id, "route_id"),
        "decision_id": _require_identifier(decision_id, "decision_id"),
        "candidate_id": _require_identifier(candidate_id, "candidate_id"),
    }
    if n != "shared" and (isinstance(n, bool) or not isinstance(n, int) or n <= 0):
        raise ValueError("n must be a positive integer or the frozen shared-n marker")
    if n == "shared" and (identifiers["module_id"] != "A-E3" or identifiers["route_id"] != "S"):
        raise ValueError("n='shared' is valid only for the frozen A-E3/S route")
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise ValueError("seed must be an integer")
    if not isinstance(selected, bool):
        raise ValueError("selected must be boolean")
    if result is None:
        # R2 #4: ``selected`` is a candidate-level attribute. A failed supporting fit
        # may belong to the winning candidate, so a failed fit may carry selected=True
        # (meaning "part of the selected candidate"); pre-unseal enforces that every
        # supporting row of a candidate agrees with the trace, not that none failed.
        message = _require_identifier(failure_message, "failure_message")
        if isinstance(failure_penalty, bool) or not isinstance(failure_penalty, (int, float)) or not math.isfinite(failure_penalty):
            raise ValueError("failed fit status requires a finite failure_penalty")
        return {
            **identifiers,
            "n": n,
            "seed": seed,
            "selected": selected,
            "checkpoint_sha256": "",
            "validation_score": "",
            "selection_score": "",
            "failure_penalty": float(failure_penalty),
            "actual_epochs": 0,
            "best_epoch_one_based": "",
            "hit_epoch_100": False,
            "early_stop_reason": "",
            "failed": True,
            "failure_message": message,
            "terminal_validation_slope": "",
            "validation_curve_json": "[]",
        }
    if failure_message is not None:
        raise ValueError("successful fit status cannot include failure_message")
    if isinstance(selection_score, bool) or not isinstance(selection_score, (int, float)) or not math.isfinite(selection_score):
        raise ValueError("successful fit status requires a finite selection_score (recomputed L_param)")
    if failure_penalty is not None:
        raise ValueError("successful fit status must not include failure_penalty")
    checkpoint = _require_sha256(getattr(result, "checkpoint_sha256", None), "checkpoint_sha256")
    score = getattr(result, "best_validation_loss", None)
    actual_epochs = getattr(result, "actual_epochs", None)
    best_epoch = getattr(result, "best_epoch", None)
    history = tuple(getattr(result, "validation_loss_history", ()))
    reason = getattr(result, "early_stop_reason", None)
    hit_ceiling = getattr(result, "hit_epoch_ceiling", None)
    if isinstance(score, bool) or not isinstance(score, (int, float)) or not math.isfinite(score):
        raise ValueError("validation score must be finite")
    if isinstance(actual_epochs, bool) or not isinstance(actual_epochs, int) or actual_epochs <= 0:
        raise ValueError("actual_epochs must be a positive integer")
    if len(history) != actual_epochs or any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in history
    ):
        raise ValueError("validation history must be finite and match actual_epochs")
    if isinstance(best_epoch, bool) or not isinstance(best_epoch, int) or not 0 <= best_epoch < actual_epochs:
        raise ValueError("best_epoch must be a valid zero-based history index")
    if float(history[best_epoch]) != float(score):
        raise ValueError("best validation score must match validation history at best_epoch")
    if reason not in {"patience_exhausted", "max_epochs"}:
        raise ValueError("early_stop_reason is invalid")
    expected_hit = actual_epochs == APPROVED_MAX_EPOCHS
    if hit_ceiling is not expected_hit or (reason == "max_epochs") is not expected_hit:
        raise ValueError("epoch ceiling and early-stop fields are inconsistent")
    return {
        **identifiers,
        "n": n,
        "seed": seed,
        "selected": selected,
        "checkpoint_sha256": checkpoint,
        "validation_score": float(score),
        "selection_score": float(selection_score),
        "failure_penalty": "",
        "actual_epochs": actual_epochs,
        "best_epoch_one_based": best_epoch + 1,
        "hit_epoch_100": expected_hit,
        "early_stop_reason": reason,
        "failed": False,
        "failure_message": "",
        "terminal_validation_slope": _terminal_ols_slope(history),
        "validation_curve_json": json.dumps(list(map(float, history)), separators=(",", ":")),
    }


def _validate_fit_status_row(row: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(row, Mapping) or set(row) != set(_FIT_STATUS_FIELDS):
        raise ValueError("fit status row must match the frozen schema exactly")
    normalized = dict(row)
    if isinstance(normalized["failed"], str):
        try:
            for field in ("failed", "selected", "hit_epoch_100"):
                if normalized[field].lower() not in {"true", "false"}:
                    raise ValueError(f"fit status {field} must be boolean")
                normalized[field] = normalized[field].lower() == "true"
            if normalized["n"] != "shared":
                normalized["n"] = int(normalized["n"])
            for field in ("seed", "actual_epochs"):
                normalized[field] = int(normalized[field])
            if normalized["best_epoch_one_based"] != "":
                normalized["best_epoch_one_based"] = int(normalized["best_epoch_one_based"])
            if normalized["validation_score"] != "":
                normalized["validation_score"] = float(normalized["validation_score"])
            if normalized["selection_score"] != "":
                normalized["selection_score"] = float(normalized["selection_score"])
            if normalized["failure_penalty"] != "":
                normalized["failure_penalty"] = float(normalized["failure_penalty"])
            if normalized["terminal_validation_slope"] != "":
                normalized["terminal_validation_slope"] = float(normalized["terminal_validation_slope"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"fit status contains an invalid scalar: {exc}") from exc
    for field in ("fit_id", "module_id", "rule_id", "route_id", "decision_id", "candidate_id"):
        _require_identifier(normalized[field], f"fit status {field}")
    if normalized["n"] != "shared" and (
        isinstance(normalized["n"], bool)
        or not isinstance(normalized["n"], int)
        or normalized["n"] <= 0
    ):
        raise ValueError("fit status n must be a positive integer or the frozen shared-n marker")
    if normalized["n"] == "shared" and (
        normalized["module_id"] != "A-E3" or normalized["route_id"] != "S"
    ):
        raise ValueError("fit status n='shared' is valid only for the frozen A-E3/S route")
    if isinstance(normalized["seed"], bool) or not isinstance(normalized["seed"], int):
        raise ValueError("fit status seed must be an integer")
    if not all(isinstance(normalized[field], bool) for field in ("failed", "selected", "hit_epoch_100")):
        raise ValueError("fit status boolean fields are invalid")
    if normalized["failed"]:
        # R2 #4: a failed supporting fit may belong to the winning candidate, so
        # failed+selected is allowed; candidate-level consistency is enforced at pre-unseal.
        if normalized["checkpoint_sha256"] or normalized["validation_score"] != "" or normalized["selection_score"] != "" or not normalized["failure_message"]:
            raise ValueError("failed fit status must not invent checkpoint, validation score, or selection score")
        if not math.isfinite(float(normalized["failure_penalty"])):
            raise ValueError("failed fit status must carry a finite failure_penalty")
        if normalized["actual_epochs"] != 0 or normalized["validation_curve_json"] != "[]":
            raise ValueError("failed fit status must have empty history")
        if normalized["best_epoch_one_based"] != "" or normalized["early_stop_reason"] != "" or normalized[
            "terminal_validation_slope"
        ] != "" or normalized["hit_epoch_100"]:
            raise ValueError("failed fit status diagnostics must remain empty")
        return normalized
    if normalized["failure_message"] != "":
        raise ValueError("successful fit status failure_message must be empty")
    if normalized["failure_penalty"] != "":
        raise ValueError("successful fit status must not carry failure_penalty")
    if not math.isfinite(float(normalized["selection_score"])) or float(normalized["selection_score"]) < 0:
        raise ValueError("successful fit status selection_score must be a finite non-negative L_param")
    try:
        curve = json.loads(normalized["validation_curve_json"])
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError("fit status validation history is invalid") from exc
    if len(curve) != normalized["actual_epochs"] or any(
        isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
        for value in curve
    ):
        raise ValueError("fit status history does not match actual_epochs")
    if normalized["hit_epoch_100"] is not (normalized["actual_epochs"] == APPROVED_MAX_EPOCHS):
        raise ValueError("fit status history/epoch/ceiling fields are inconsistent")
    if normalized["early_stop_reason"] != (
        "max_epochs" if normalized["hit_epoch_100"] else "patience_exhausted"
    ):
        raise ValueError("fit status early-stop reason is inconsistent")
    best = normalized["best_epoch_one_based"]
    if not isinstance(best, int) or not 1 <= best <= len(curve):
        raise ValueError("fit status best epoch is invalid")
    if not math.isfinite(float(normalized["validation_score"])) or float(curve[best - 1]) != float(
        normalized["validation_score"]
    ):
        raise ValueError("fit status validation score is inconsistent")
    slope = _terminal_ols_slope(curve)
    if not math.isclose(float(normalized["terminal_validation_slope"]), slope, rel_tol=1e-12, abs_tol=1e-12):
        raise ValueError("fit status terminal validation slope is inconsistent")
    _require_sha256(normalized["checkpoint_sha256"], "fit status checkpoint_sha256")
    return normalized


def write_fit_status(destination: Path, rows: Sequence[Mapping[str, Any]]) -> str:
    validated = [_validate_fit_status_row(row) for row in rows]
    if not validated:
        raise ValueError("fit status must contain at least one row")
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=_FIT_STATUS_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(validated)
    payload = output.getvalue().encode("utf-8")
    _publish_bytes_no_replace(payload, destination)
    return hashlib.sha256(payload).hexdigest()


def write_selection_trace(destination: Path, records: Sequence[Mapping[str, Any]]) -> str:
    rows = [dict(record) for record in records]
    if not rows:
        raise ValueError("selection trace must not be empty")
    ownership = {(row.get("module_id"), row.get("run_id")) for row in rows}
    if len(ownership) != 1:
        raise ValueError("selection trace ownership must be uniform")
    rows = sorted(
        rows,
        key=lambda row: (
            row["decision_id"], row["validation_score"],
            _tie_break_sort_key(row["tie_break_key"]), row["candidate_id"],
        ),
    )
    payload = b"".join(_canonical_json_bytes(row) for row in rows)
    digest = hashlib.sha256(payload).hexdigest()
    module_id, run_id = next(iter(ownership))
    _validate_selection_trace_bytes(payload, digest, module_id, run_id)
    _publish_bytes_no_replace(payload, destination)
    return digest


def build_ceiling_hit_report(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    validated = [_validate_fit_status_row(row) for row in rows]
    if not validated:
        raise ValueError("ceiling report requires fit-status rows")
    groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
    for row in validated:
        selected_arm = row["candidate_id"] if row["selected"] else ""
        key = (row["rule_id"], row["route_id"], row["n"], row["seed"], row["selected"], selected_arm)
        groups.setdefault(key, []).append(row)
    output_groups = []
    for key in sorted(groups, key=lambda item: tuple(str(value) for value in item)):
        group_rows = sorted(groups[key], key=lambda row: (row["fit_id"], row["candidate_id"]))
        successes = [row for row in group_rows if not row["failed"]]
        ceiling_hits = [row for row in successes if row["hit_epoch_100"]]
        actual = [row["actual_epochs"] for row in successes]
        best = [row["best_epoch_one_based"] for row in successes]
        fits = [{
            "fit_id": row["fit_id"],
            "decision_id": row["decision_id"],
            "candidate_id": row["candidate_id"],
            "selected": row["selected"],
            "failed": row["failed"],
            "hit_epoch_100": row["hit_epoch_100"],
            "actual_epochs": row["actual_epochs"],
            "best_epoch_one_based": row["best_epoch_one_based"],
            "terminal_validation_slope": row["terminal_validation_slope"],
            "validation_curve": json.loads(row["validation_curve_json"]),
            "failure_message": row["failure_message"],
        } for row in group_rows]
        output_groups.append({
            "rule_id": key[0], "route_id": key[1], "n": key[2], "seed": key[3], "selected": key[4],
            "selected_arm": key[5],
            "fit_count": len(group_rows), "failure_count": len(group_rows) - len(successes),
            "ceiling_hit_count": len(ceiling_hits),
            "ceiling_hit_rate": len(ceiling_hits) / len(successes) if successes else 0.0,
            "actual_epochs_summary": {
                "min": min(actual) if actual else None, "max": max(actual) if actual else None,
                "mean": sum(actual) / len(actual) if actual else None,
            },
            "best_epoch_one_based_summary": {
                "min": min(best) if best else None, "max": max(best) if best else None,
                "mean": sum(best) / len(best) if best else None,
            },
            "fits": fits,
        })
    return {
        "report_version": "study02-ceiling-hit-v1",
        "terminal_slope_contract": "OLS slope over last 10 validation losses, or all losses if shorter",
        "fit_count": len(validated),
        "failure_count": sum(row["failed"] for row in validated),
        "ceiling_hit_count": sum(not row["failed"] and row["hit_epoch_100"] for row in validated),
        "groups": output_groups,
    }


def write_ceiling_hit_report(
    destination: Path, report_or_rows: Mapping[str, Any] | Sequence[Mapping[str, Any]]
) -> str:
    report = dict(report_or_rows) if isinstance(report_or_rows, Mapping) else build_ceiling_hit_report(report_or_rows)
    _validate_ceiling_hit_report(report)
    payload = _canonical_json_bytes(report)
    _publish_bytes_no_replace(payload, destination)
    return hashlib.sha256(payload).hexdigest()


def _validate_ceiling_hit_report(report: Mapping[str, Any]) -> None:
    if report.get("report_version") != "study02-ceiling-hit-v1" or not isinstance(report.get("groups"), list):
        raise ValueError("invalid ceiling-hit report")
    total_fits = total_failures = total_hits = 0
    for group in report["groups"]:
        if not isinstance(group, Mapping) or not isinstance(group.get("fits"), list) or not group["fits"]:
            raise ValueError("ceiling report groups must contain fit evidence")
        successes = []
        hits = 0
        expected_selected_arm = None
        for fit in group["fits"]:
            if fit.get("selected") is not group.get("selected"):
                raise ValueError("ceiling report selected-arm membership is inconsistent")
            fit_arm = fit.get("candidate_id") if fit.get("selected") else ""
            if expected_selected_arm is None:
                expected_selected_arm = fit_arm
            elif fit_arm != expected_selected_arm:
                raise ValueError("ceiling report merges distinct selected candidate arms")
            if fit.get("failed"):
                if fit.get("actual_epochs") != 0 or fit.get("validation_curve") != []:
                    raise ValueError("failed ceiling evidence must have empty history")
                continue
            curve = fit.get("validation_curve")
            if not isinstance(curve, list) or len(curve) != fit.get("actual_epochs") or any(
                isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                for value in curve
            ):
                raise ValueError("ceiling report history does not match actual epochs")
            expected_hit = len(curve) == APPROVED_MAX_EPOCHS
            if fit.get("hit_epoch_100") is not expected_hit:
                raise ValueError("ceiling report history/ceiling fields are inconsistent")
            best = fit.get("best_epoch_one_based")
            if isinstance(best, bool) or not isinstance(best, int) or not 1 <= best <= len(curve):
                raise ValueError("ceiling report best epoch is invalid")
            slope = fit.get("terminal_validation_slope")
            if isinstance(slope, bool) or not isinstance(slope, (int, float)) or not math.isclose(
                float(slope), _terminal_ols_slope(curve), rel_tol=1e-12, abs_tol=1e-12
            ):
                raise ValueError("ceiling report terminal validation slope is inconsistent")
            successes.append(fit)
            hits += int(expected_hit)
        if group.get("selected_arm") != (expected_selected_arm or ""):
            raise ValueError("ceiling report selected arm is inconsistent")
        fit_count = len(group["fits"])
        failures = fit_count - len(successes)
        if group.get("fit_count") != fit_count or group.get("failure_count") != failures:
            raise ValueError("ceiling report group counts are inconsistent")
        if group.get("ceiling_hit_count") != hits:
            raise ValueError("ceiling report group hit count is inconsistent")
        expected_rate = hits / len(successes) if successes else 0.0
        if not math.isclose(float(group.get("ceiling_hit_rate", -1)), expected_rate):
            raise ValueError("ceiling report group hit rate is inconsistent")
        actual = [fit["actual_epochs"] for fit in successes]
        best = [fit["best_epoch_one_based"] for fit in successes]
        expected_actual = {
            "min": min(actual) if actual else None, "max": max(actual) if actual else None,
            "mean": sum(actual) / len(actual) if actual else None,
        }
        expected_best = {
            "min": min(best) if best else None, "max": max(best) if best else None,
            "mean": sum(best) / len(best) if best else None,
        }
        if group.get("actual_epochs_summary") != expected_actual or group.get(
            "best_epoch_one_based_summary"
        ) != expected_best:
            raise ValueError("ceiling report epoch summaries are inconsistent")
        total_fits += fit_count
        total_failures += failures
        total_hits += hits
    if (report.get("fit_count"), report.get("failure_count"), report.get("ceiling_hit_count")) != (
        total_fits, total_failures, total_hits
    ):
        raise ValueError("ceiling report total counts are inconsistent")


def build_leakage_audit(
    *, parameter_point_ids: Mapping[str, Sequence[Any]], role_namespaces: Mapping[str, str],
    scaler_source: str, feature_selection_source: str, model_selection_source: str,
    test_access_count: int,
) -> dict[str, Any]:
    if set(parameter_point_ids) != set(_EVIDENCE_ROLES) or set(role_namespaces) != set(_EVIDENCE_ROLES):
        raise ValueError("leakage audit requires exact training/validation/calibration/test roles")
    point_sets: dict[str, set[Any]] = {}
    for role in _EVIDENCE_ROLES:
        values = list(parameter_point_ids[role])
        try:
            point_sets[role] = set(values)
        except TypeError as exc:
            raise ValueError("parameter-point IDs must be hashable metadata") from exc
        if len(point_sets[role]) != len(values):
            raise ValueError(f"duplicate parameter-point ID in {role}")
        namespace = role_namespaces[role]
        if not isinstance(namespace, str) or not namespace.strip() or role not in namespace.lower():
            raise ValueError(f"{role} namespace is not role-correct")
    if len(set(role_namespaces.values())) != len(_EVIDENCE_ROLES):
        raise ValueError("role namespaces must be distinct")
    intersections: dict[str, int] = {}
    for index, first in enumerate(_EVIDENCE_ROLES):
        for second in _EVIDENCE_ROLES[index + 1:]:
            size = len(point_sets[first] & point_sets[second])
            intersections[f"{first}:{second}"] = size
            if size:
                raise ValueError(f"parameter-point intersection detected for {first}/{second}")
    expected_sources = {
        "scaler_source": (scaler_source, "training_only"),
        "feature_selection_source": (feature_selection_source, "validation_only"),
        "model_selection_source": (model_selection_source, "validation_only"),
    }
    for label, (actual, expected) in expected_sources.items():
        if actual != expected:
            raise ValueError(f"{label} must be {expected}")
    if test_access_count != 0 or isinstance(test_access_count, bool):
        raise ValueError("test_access_count must be exactly 0")
    return {
        "audit_version": "study02-leakage-v1",
        "parameter_point_counts": {role: len(point_sets[role]) for role in _EVIDENCE_ROLES},
        "pairwise_intersections": dict(sorted(intersections.items())),
        "role_namespaces": {role: role_namespaces[role] for role in _EVIDENCE_ROLES},
        "scaler_source": scaler_source,
        "feature_selection_source": feature_selection_source,
        "model_selection_source": model_selection_source,
        "test_access_count": 0,
    }


def write_leakage_audit(destination: Path, audit: Mapping[str, Any] | None = None, **kwargs: Any) -> str:
    if audit is not None and kwargs:
        raise ValueError("supply either a built leakage audit or builder arguments")
    payload_obj = dict(audit) if audit is not None else build_leakage_audit(**kwargs)
    _validate_leakage_audit(payload_obj)
    payload = _canonical_json_bytes(payload_obj)
    _publish_bytes_no_replace(payload, destination)
    return hashlib.sha256(payload).hexdigest()


def _validate_leakage_audit(audit: Mapping[str, Any]) -> None:
    if audit.get("audit_version") != "study02-leakage-v1":
        raise ValueError("leakage audit version mismatch")
    if set(audit.get("parameter_point_counts", {})) != set(_EVIDENCE_ROLES):
        raise ValueError("leakage audit parameter-point roles mismatch")
    namespaces = audit.get("role_namespaces", {})
    if set(namespaces) != set(_EVIDENCE_ROLES) or len(set(namespaces.values())) != len(_EVIDENCE_ROLES):
        raise ValueError("leakage audit role namespaces mismatch")
    if any(not isinstance(namespaces[role], str) or role not in namespaces[role].lower() for role in _EVIDENCE_ROLES):
        raise ValueError("leakage audit contains a role-incorrect namespace")
    expected_pairs = {
        f"{first}:{second}"
        for index, first in enumerate(_EVIDENCE_ROLES)
        for second in _EVIDENCE_ROLES[index + 1:]
    }
    intersections = audit.get("pairwise_intersections", {})
    if set(intersections) != expected_pairs or any(value != 0 for value in intersections.values()):
        raise ValueError("leakage audit contains parameter-point intersections")
    for field, expected in (
        ("scaler_source", "training_only"),
        ("feature_selection_source", "validation_only"),
        ("model_selection_source", "validation_only"),
    ):
        if audit.get(field) != expected:
            raise ValueError(f"{field} must be {expected}")
    if audit.get("test_access_count") != 0 or isinstance(audit.get("test_access_count"), bool):
        raise ValueError("test_access_count must be exactly 0")


def _load_json_object(path: Path, label: str) -> tuple[bytes, dict[str, Any]]:
    if not Path(path).is_file():
        raise FileNotFoundError(f"{label} is missing: {path}")
    payload = Path(path).read_bytes()
    return payload, _load_json_object_bytes(payload, label)


def _load_json_object_bytes(payload: bytes, label: str) -> dict[str, Any]:
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{label} must be valid JSON") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _require_exact_fields(value: Any, fields: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping) or set(value) != fields:
        raise ValueError(f"{label} schema must contain exactly {sorted(fields)}")
    return value


def _validate_formal_manifest_snapshot(
    manifest: Mapping[str, Any], *, module_id: str, run_id: str, code_commit: str,
    effective_config_sha256: str,
) -> None:
    _require_exact_fields(manifest, {
        "manifest_version", "module_id", "run_id", "base_protocol", "base_search",
        "amendment", "effective_config", "matrix", "code_commit", "role_namespaces",
        "seeds", "test_state", "predecessor",
    }, "formal manifest")
    if manifest["manifest_version"] != "study02-formal-v1":
        raise ValueError("formal manifest version mismatch")
    if manifest["module_id"] != module_id or manifest["run_id"] != run_id:
        raise ValueError("formal manifest module/run ownership mismatch")
    if manifest["code_commit"] != code_commit.lower():
        raise ValueError("formal manifest code commit mismatch")
    if manifest["test_state"] != "sealed":
        raise ValueError("formal manifest test_state must remain sealed")

    for label, actual, expected in (
        ("base_protocol", manifest["base_protocol"], {
            "id": APPROVED_BASE_PROTOCOL_ID, "sha256": APPROVED_BASE_PROTOCOL_SHA256,
        }),
        ("base_search", manifest["base_search"], {
            "id": APPROVED_BASE_SEARCH_ID, "sha256": APPROVED_BASE_SEARCH_SHA256,
        }),
        ("amendment", manifest["amendment"], {
            "id": APPROVED_AMENDMENT_ID, "sha256": APPROVED_AMENDMENT_SHA256,
        }),
    ):
        if actual != expected:
            raise ValueError(f"formal manifest {label} frozen binding mismatch")

    effective = _require_exact_fields(
        manifest["effective_config"], {"sha256", "max_epochs", "min_epochs", "patience"},
        "formal manifest effective_config",
    )
    if effective_config_sha256 != APPROVED_EFFECTIVE_CONFIG_SHA256 or effective["sha256"] != effective_config_sha256:
        raise ValueError("formal manifest effective config SHA mismatch")
    for field, expected in (
        ("max_epochs", APPROVED_MAX_EPOCHS), ("min_epochs", APPROVED_MIN_EPOCHS),
        ("patience", APPROVED_PATIENCE),
    ):
        if effective[field] != expected:
            raise ValueError(f"formal manifest effective {field} must be exactly {expected}")

    matrix = _require_exact_fields(
        manifest["matrix"], {"path", "sha256", "row_count", "rule_ids", "fit_ids"},
        "formal manifest matrix",
    )
    if not isinstance(matrix["path"], str) or not matrix["path"].strip():
        raise ValueError("formal manifest matrix path is required")
    if matrix["sha256"] != FROZEN_MATRIX_SHA256 or matrix["row_count"] != FROZEN_MATRIX_ROWS:
        raise ValueError("formal manifest matrix frozen binding mismatch")
    rules, fits = matrix["rule_ids"], matrix["fit_ids"]
    if not isinstance(rules, list) or not rules or any(not isinstance(rule, str) for rule in rules):
        raise ValueError("formal manifest matrix rule subset is invalid")
    if len(set(rules)) != len(rules) or any(
        rule not in _FROZEN_RULE_FIT_RANGES or not rule.startswith(module_id + "_") for rule in rules
    ):
        raise ValueError("formal manifest matrix rule subset is invalid")
    if not isinstance(fits, list) or not fits or any(not isinstance(fit, str) for fit in fits):
        raise ValueError("formal manifest matrix fit subset is invalid")
    if len(set(fits)) != len(fits) or any(re.fullmatch(r"G3-fit-\d{4}", fit) is None for fit in fits):
        raise ValueError("formal manifest matrix fit subset is invalid")
    fit_numbers = [int(fit.rsplit("-", 1)[1]) for fit in fits]
    if any(not any(_FROZEN_RULE_FIT_RANGES[rule][0] <= number <= _FROZEN_RULE_FIT_RANGES[rule][1] for rule in rules)
           for number in fit_numbers) or any(
        not any(start <= number <= end for number in fit_numbers)
        for start, end in (_FROZEN_RULE_FIT_RANGES[rule] for rule in rules)
    ):
        raise ValueError("formal manifest matrix rule/fit subset is inconsistent")

    namespaces = _require_exact_fields(
        manifest["role_namespaces"], {"training", "validation"}, "formal manifest role_namespaces"
    )
    if any(not isinstance(namespaces[role], str) or not namespaces[role].strip() for role in namespaces) or (
        namespaces["training"] == namespaces["validation"]
    ):
        raise ValueError("formal manifest role namespaces are invalid")
    seeds = _require_exact_fields(manifest["seeds"], {"screening", "formal"}, "formal manifest seeds")
    if seeds["screening"] != list(APPROVED_SCREENING_SEEDS):
        raise ValueError("formal manifest screening seeds mismatch")
    if seeds["formal"] != list(APPROVED_FORMAL_SEEDS):
        raise ValueError("formal manifest formal seeds mismatch")
    predecessor = _require_exact_fields(manifest["predecessor"], {
        "module_id", "run_id", "selection_trace_path", "selection_trace_sha256",
        "selection_receipt_path", "selection_receipt_sha256", "selection_ledger_path",
        "selection_staged_ledger_path", "selection_staged_ledger_sha256",
        "resolved_baseline_route",
    }, "formal manifest predecessor")
    if any(not isinstance(predecessor[field], str) or not predecessor[field] for field in predecessor):
        raise ValueError("formal manifest predecessor fields must be non-empty strings")


def build_pre_unseal_bundle(
    *, formal_manifests: Sequence[Path], selection_traces: Sequence[Path],
    selection_receipts: Sequence[Path], selection_ledger_path: Path,
    fit_status_path: Path, ceiling_report_path: Path,
    leakage_audit_path: Path, code_commit: str, effective_config_sha256: str,
    module_run_ids: Mapping[str, str],
    point_evidence_paths: Mapping[str, Path] | None = None,
    selection_diagnostics_paths: Sequence[Path] | None = None,
    point_provenance_by_fit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    if not isinstance(code_commit, str) or _CODE_COMMIT_RE.fullmatch(code_commit) is None:
        raise ValueError("code_commit must be a full commit ID")
    effective_config_sha256 = _require_sha256(effective_config_sha256, "effective_config_sha256")
    if effective_config_sha256 != APPROVED_EFFECTIVE_CONFIG_SHA256:
        raise ValueError("effective_config_sha256 must match the frozen approved config")
    if not module_run_ids:
        raise ValueError("module_run_ids must not be empty")
    point_evidence_paths = dict(point_evidence_paths or {})
    selection_diagnostics_paths = list(selection_diagnostics_paths or [])
    paths = [*map(Path, formal_manifests), *map(Path, selection_traces), *map(Path, selection_receipts),
             Path(selection_ledger_path), Path(fit_status_path), Path(ceiling_report_path),
             Path(leakage_audit_path), *map(Path, selection_diagnostics_paths),
             *map(Path, point_evidence_paths.values())]
    resolved = [path.resolve(strict=False) for path in paths]
    if len(set(resolved)) != len(resolved):
        raise ValueError("pre-unseal artifact paths must not alias")
    for index, first in enumerate(paths):
        if not first.is_file():
            raise FileNotFoundError(f"required pre-unseal artifact is missing: {first}")
        for second in paths[index + 1:]:
            try:
                if first.samefile(second):
                    raise ValueError("pre-unseal artifact paths must not alias")
            except OSError as exc:
                raise ValueError(f"pre-unseal artifact identity cannot be verified: {exc}") from exc

    snapshots = {resolved_path: path.read_bytes() for path, resolved_path in zip(paths, resolved)}

    def artifact_bytes(path: Path) -> bytes:
        return snapshots[Path(path).resolve(strict=False)]

    manifests: dict[str, dict[str, Any]] = {}
    manifest_fields = {
        "manifest_version", "module_id", "run_id", "base_protocol", "base_search",
        "amendment", "effective_config", "matrix", "code_commit", "role_namespaces",
        "seeds", "test_state", "predecessor",
    }
    for path in formal_manifests:
        manifest = _load_json_object_bytes(artifact_bytes(Path(path)), "formal manifest")
        _require_exact_fields(manifest, manifest_fields, "formal manifest")
        module = manifest["module_id"]
        if module in manifests or module not in module_run_ids:
            raise ValueError("formal manifests must have unique declared module ownership")
        _validate_formal_manifest_snapshot(
            manifest, module_id=module, run_id=module_run_ids[module], code_commit=code_commit,
            effective_config_sha256=effective_config_sha256,
        )
        manifests[module] = manifest
    if set(manifests) != set(module_run_ids):
        raise ValueError("formal manifests do not cover module_run_ids exactly")
    if len(selection_traces) != len(module_run_ids) or len(selection_receipts) != len(module_run_ids):
        raise ValueError("selection traces and receipts must cover every module")

    traces: dict[str, tuple[Path, str, int, int]] = {}
    trace_records: dict[str, list[dict[str, Any]]] = {}
    for path in selection_traces:
        payload = artifact_bytes(Path(path))
        records = _read_jsonl_bytes(payload, "selection trace")
        module = records[0].get("module_id")
        if module in traces or module not in module_run_ids:
            raise ValueError("selection traces must have unique declared module ownership")
        digest = hashlib.sha256(payload).hexdigest()
        _, count, decisions = _validate_selection_trace_bytes(payload, digest, module, module_run_ids[module])
        traces[module] = (Path(path), digest, count, decisions)
        trace_records[module] = records

    receipts: dict[str, tuple[Path, str, dict[str, Any]]] = {}
    for path in selection_receipts:
        receipt_payload = artifact_bytes(Path(path))
        receipt = _load_json_object_bytes(receipt_payload, "selection receipt")
        module = receipt.get("module_id")
        if module in receipts or module not in traces:
            raise ValueError("selection receipts must have unique declared module ownership")
        trace = traces[module]
        expected = {
            "receipt_version": "study02-formal-selection-v3", "module_id": module,
            "run_id": module_run_ids[module], "selection_trace_sha256": trace[1],
            "effective_config_sha256": effective_config_sha256, "code_commit": code_commit.lower(),
            "record_count": trace[2], "decision_count": trace[3],
        }
        if receipt != expected:
            raise ValueError("selection receipt does not match trace/config ownership")
        receipts[module] = (Path(path), hashlib.sha256(receipt_payload).hexdigest(), receipt)

    ledger_records = _read_jsonl_bytes(
        artifact_bytes(Path(selection_ledger_path)), "Formal selection ledger"
    )
    for module, (_, receipt_sha, receipt) in receipts.items():
        bindings = [
            row for row in ledger_records
            if row.get("binding_type") == "formal-selection"
            and row.get("module_id") == module
            and row.get("run_id") == module_run_ids[module]
        ]
        if len(bindings) != 1:
            raise ValueError(f"Formal selection ledger must contain exactly one binding for {module}")
        expected_binding = {"binding_type": "formal-selection", **receipt, "receipt_sha256": receipt_sha}
        if bindings[0] != expected_binding:
            raise ValueError(f"Formal selection ledger binding for {module} is not exact")

    for module, manifest in manifests.items():
        predecessor = manifest["predecessor"]
        expected_predecessor = _PREDECESSOR_BY_MODULE.get(module)
        if expected_predecessor is None:
            if set(predecessor.values()) != {"none"}:
                raise ValueError("A-E1 formal manifest predecessor binding must be none")
        else:
            if expected_predecessor not in traces or expected_predecessor not in receipts:
                raise ValueError("formal manifest predecessor evidence is missing from bundle")
            trace_path, trace_sha, _, _ = traces[expected_predecessor]
            receipt_path, receipt_sha, _ = receipts[expected_predecessor]
            if predecessor["module_id"] != expected_predecessor or predecessor["run_id"] != module_run_ids[
                expected_predecessor
            ]:
                raise ValueError("formal manifest predecessor module/run binding mismatch")
            if predecessor["selection_trace_sha256"] != trace_sha or Path(
                predecessor["selection_trace_path"]
            ).resolve(strict=False) != trace_path.resolve(strict=False):
                raise ValueError("formal manifest predecessor trace binding mismatch")
            if predecessor["selection_receipt_sha256"] != receipt_sha or Path(
                predecessor["selection_receipt_path"]
            ).resolve(strict=False) != receipt_path.resolve(strict=False):
                raise ValueError("formal manifest predecessor receipt binding mismatch")
            if Path(predecessor["selection_ledger_path"]).resolve(strict=False) != Path(
                selection_ledger_path
            ).resolve(strict=False):
                raise ValueError("formal manifest predecessor selection ledger path mismatch")

    fit_payload = artifact_bytes(Path(fit_status_path))
    try:
        fit_rows = list(csv.DictReader(io.StringIO(fit_payload.decode("utf-8"), newline="")))
        if not fit_rows:
            raise ValueError("fit status is empty")
        normalized_fit_rows = [_validate_fit_status_row(row) for row in fit_rows]
    except (UnicodeError, csv.Error) as exc:
        raise ValueError("fit status must be valid UTF-8 CSV") from exc
    seen_fit_ids: set[str] = set()
    fit_rows_by_module: dict[str, list[dict[str, Any]]] = {}
    for row in normalized_fit_rows:
        module = row["module_id"]
        if module not in manifests:
            raise ValueError("fit status module is not present in formal manifests")
        matrix = manifests[module]["matrix"]
        if row["fit_id"] not in matrix["fit_ids"] or row["rule_id"] not in matrix["rule_ids"]:
            raise ValueError("fit status fit_id/rule_id is outside its formal manifest subset")
        fit_number = int(row["fit_id"].rsplit("-", 1)[1])
        rule_start, rule_end = _FROZEN_RULE_FIT_RANGES[row["rule_id"]]
        if not rule_start <= fit_number <= rule_end:
            raise ValueError("fit status rule_id and fit_id are cross-labelled")
        if row["fit_id"] in seen_fit_ids:
            raise ValueError("fit status contains a duplicate fit_id; fit_id must be globally unique")
        seen_fit_ids.add(row["fit_id"])
        fit_rows_by_module.setdefault(module, []).append(row)
    # R3#1/#2/#3: independently rebuild each module's DecisionSpecs from the frozen matrix
    # and recompute, from the verified per-fit point-evidence artifacts + fit_status
    # scalars, each candidate's supporting_evidence_sha256 AND each decision's
    # rule_diagnostics_sha256 -- RE-RUNNING the frozen rule (including the non-ranking
    # rules, with the frozen bootstrap seed 520001 / 2000 reps). The recomputed SHAs and
    # winner are compared to the selection trace; the trace's ``selected`` flag is NOT
    # trusted (R3#3).
    from .selection import (
        SupportKey as _SupportKey,
        apply_selection_rule as _apply_selection_rule,
        build_decision_specs as _build_decision_specs,
        build_rule_diagnostics as _build_rule_diagnostics,
        candidate_supporting_evidence as _candidate_supporting_evidence,
        compute_rule_diagnostics_sha256 as _compute_rule_diagnostics_sha256,
        load_point_evidence as _load_point_evidence,
    )
    # Load + integrity-verify every point-evidence artifact (recompute its content SHA).
    point_evidence_by_fit: dict[str, Any] = {}
    for fit_id, art_path in point_evidence_paths.items():
        payload = _load_json_object_bytes(artifact_bytes(Path(art_path)), "point-evidence artifact")
        evaluation = _load_point_evidence(payload)
        if evaluation.fit_id != fit_id:
            raise ValueError(
                f"point-evidence artifact path keyed by {fit_id!r} carries fit_id {evaluation.fit_id!r}"
            )
        if fit_id in point_evidence_by_fit:
            raise ValueError(f"duplicate point-evidence artifact for fit {fit_id!r}")
        point_evidence_by_fit[fit_id] = evaluation
    # Load the published per-decision diagnostics artifacts (canonical JSONL).
    published_diagnostics: dict[tuple[str, str], dict[str, Any]] = {}
    for diag_path in selection_diagnostics_paths:
        for record in _read_jsonl_bytes(artifact_bytes(Path(diag_path)), "selection diagnostics"):
            key = (str(record.get("module_id")), str(record.get("decision_id")))
            if key in published_diagnostics:
                raise ValueError(f"duplicate selection diagnostics record for {key!r}")
            published_diagnostics[key] = record

    # R4#1: independently rebuild each fit's point evidence from its bound checkpoint and
    # require every published artifact to agree with the rebuild field-by-field. The caller
    # supplies ``point_provenance_by_fit`` (produced by formal_executor's single-source
    # rebuild_selection_point_provenance: reload checkpoint.pt -> rebuild validation inputs
    # -> forward -> decode -> canonical point records). This closes the loop the artifact's
    # self-consistent content SHA leaves open: an attacker who rewrites the point records AND
    # resynchronises the artifact's content SHA plus the downstream supporting/diagnostics/
    # trace/receipt/ledger/fit_status still fails closed, because the rebuilt records come
    # from the actual checkpoint, not the artifact. Mandatory whenever point-evidence
    # artifacts are present (fail-closed -- the rebuild cannot be skipped).
    if point_evidence_paths:
        if point_provenance_by_fit is None:
            raise ValueError(
                "point_evidence_paths requires point_provenance_by_fit (the independent checkpoint rebuild)"
            )
        from .selection import assert_point_evidence_provenance as _assert_point_evidence_provenance
        artifact_keys = set(point_evidence_paths)
        provenance_keys = set(point_provenance_by_fit)
        if provenance_keys != artifact_keys:
            missing = sorted(artifact_keys - provenance_keys)
            extra = sorted(provenance_keys - artifact_keys)
            raise ValueError(
                "point_provenance_by_fit must cover exactly the point-evidence artifacts; "
                f"missing={missing!r} extra={extra!r}"
            )
        for fit_id in sorted(point_evidence_paths):
            _assert_point_evidence_provenance(
                published=point_evidence_by_fit[fit_id],
                rebuilt=point_provenance_by_fit[fit_id],
            )

    frozen_matrix_rows = _open_verified_matrix_evidence(_FROZEN_MATRIX_PATH).rows
    for module, module_fit_rows in fit_rows_by_module.items():
        declared_fit_ids = set(manifests[module]["matrix"]["fit_ids"])
        scope_rows = [row for row in frozen_matrix_rows if row["fit_id"] in declared_fit_ids]
        specs = _build_decision_specs(module, scope_rows)
        authority: dict[str, tuple[str, str, _SupportKey]] = {}
        for spec in specs:
            for candidate in spec.candidates:
                for key in candidate.support_keys:
                    fit_id = candidate.support_for(key)
                    if fit_id in authority:
                        raise ValueError("frozen matrix maps one fit_id to two selection supports")
                    authority[fit_id] = (spec.decision_id, candidate.candidate_id, key)
        support_rows_by_candidate: dict[tuple[str, str], dict[_SupportKey, dict[str, Any]]] = {}
        for row in module_fit_rows:
            entry = authority.get(row["fit_id"])
            if entry is None:
                continue  # non-selection fit (historical/controlled/retrain): transparent
            decision_id, candidate_id, key = entry
            if row["decision_id"] != decision_id or row["candidate_id"] != candidate_id:
                raise ValueError(
                    f"fit status fit_id {row['fit_id']!r} is relabelled to "
                    f"{row['decision_id']!r}/{row['candidate_id']!r}; frozen plan expects "
                    f"{decision_id!r}/{candidate_id!r}"
                )
            row_key = _SupportKey(n=row["n"], seed=int(row["seed"]))
            if row_key != key:
                raise ValueError(
                    f"fit status fit_id {row['fit_id']!r} support {row_key!r} disagrees with "
                    f"frozen expected {key!r}"
                )
            bucket = support_rows_by_candidate.setdefault((decision_id, candidate_id), {})
            if row_key in bucket:
                raise ValueError(f"fit status has a duplicate support fit for {decision_id}/{candidate_id}/{row_key!r}")
            bucket[row_key] = row
        trace_by_pair = {(rec["decision_id"], rec["candidate_id"]): rec for rec in trace_records[module]}
        rebuilt_pairs: set[tuple[str, str]] = set()
        for spec in specs:
            evidence_by_candidate: dict[str, dict[str, Any]] = {}
            evals_by_candidate: dict[str, Any] = {}
            for candidate in spec.candidates:
                pair = (spec.decision_id, candidate.candidate_id)
                rebuilt_pairs.add(pair)
                rows_by_support = support_rows_by_candidate.get(pair, {})
                if len(rows_by_support) != len(candidate.support_keys):
                    raise ValueError(
                        f"fit status for {spec.decision_id}/{candidate.candidate_id} must cover exactly "
                        f"the {len(candidate.support_keys)} frozen support keys; got {len(rows_by_support)}"
                    )
                if pair not in trace_by_pair:
                    raise ValueError(
                        f"selection candidate {spec.decision_id}/{candidate.candidate_id} is in the "
                        "frozen plan but missing from the selection trace"
                    )
                selection = trace_by_pair[pair]
                evaluations_by_support = {}
                for key in candidate.support_keys:
                    fit_id = candidate.support_for(key)
                    fit_row = rows_by_support[key]
                    artifact_eval = point_evidence_by_fit.get(fit_id)
                    if artifact_eval is None:
                        raise ValueError(f"missing point-evidence artifact for selection fit {fit_id!r}")
                    if artifact_eval.checkpoint_sha256 != fit_row["checkpoint_sha256"]:
                        raise ValueError(
                            f"point-evidence artifact {fit_id!r} checkpoint disagrees with fit_status"
                        )
                    if bool(artifact_eval.failed) != bool(fit_row["failed"]):
                        raise ValueError(
                            f"point-evidence artifact {fit_id!r} failed flag disagrees with fit_status"
                        )
                    if not artifact_eval.failed:
                        score = float(fit_row["selection_score"]) if fit_row["selection_score"] != "" else 0.0
                        if not math.isclose(float(artifact_eval.selection_score), score, rel_tol=1e-12, abs_tol=1e-12):
                            raise ValueError(
                                f"point-evidence artifact {fit_id!r} selection_score disagrees with fit_status"
                            )
                    else:
                        penalty = float(fit_row["failure_penalty"]) if fit_row["failure_penalty"] != "" else 0.0
                        if not math.isclose(float(artifact_eval.failure_penalty), penalty, rel_tol=1e-12, abs_tol=1e-12):
                            raise ValueError(
                                f"point-evidence artifact {fit_id!r} failure_penalty disagrees with fit_status"
                            )
                    evaluations_by_support[key] = artifact_eval
                evidence = _candidate_supporting_evidence(
                    module_id=module, run_id=selection["run_id"], candidate=candidate,
                    evaluations_by_support=evaluations_by_support,
                )
                if evidence["supporting_evidence_sha256"] != selection["supporting_evidence_sha256"]:
                    raise ValueError("recomputed supporting evidence SHA disagrees with selection trace")
                if not math.isclose(evidence["aggregate_score"], float(selection["validation_score"]), rel_tol=1e-12, abs_tol=1e-12):
                    raise ValueError("recomputed aggregate score disagrees with selection trace")
                if evidence["support_count"] != selection["support_count"]:
                    raise ValueError("recomputed support_count disagrees with selection trace")
                if evidence["seed_count"] != selection["seed_count"]:
                    raise ValueError("recomputed seed_count disagrees with selection trace")
                # R2#4: selected is candidate-level. Every supporting row of this candidate must
                # carry the SAME selected value, equal to the trace -- no any/all.
                row_selected = {bool(rows_by_support[key]["selected"]) for key in candidate.support_keys}
                if len(row_selected) != 1 or row_selected.pop() is not selection["selected"]:
                    raise ValueError(
                        f"fit status selected membership for {spec.decision_id}/{candidate.candidate_id} "
                        "is inconsistent or disagrees with its selection trace"
                    )
                evidence_by_candidate[candidate.candidate_id] = evidence
                evals_by_candidate[candidate.candidate_id] = evaluations_by_support
            # R3#3: re-run the frozen rule from the verified point evidence, recompute the
            # diagnostics SHA, and require both the SHA and the recomputed winner to agree
            # with the trace. The trace ``selected`` flag is NOT trusted.
            winner, rule_result = _apply_selection_rule(spec, evidence_by_candidate, evals_by_candidate)
            any_pair = (spec.decision_id, spec.candidates[0].candidate_id)
            diagnostics = _build_rule_diagnostics(
                module_id=module, run_id=trace_by_pair[any_pair]["run_id"], spec=spec,
                evidence_by_candidate=evidence_by_candidate, winner=winner, rule_result=rule_result,
            )
            diag_sha = _compute_rule_diagnostics_sha256(diagnostics)
            trace_diag_sha = trace_by_pair[any_pair]["rule_diagnostics_sha256"]
            if diag_sha != trace_diag_sha:
                raise ValueError(
                    f"recomputed rule diagnostics SHA for {spec.decision_id} disagrees with selection trace"
                )
            trace_winner = next(
                rec["candidate_id"] for rec in trace_records[module]
                if rec["decision_id"] == spec.decision_id and rec["selected"]
            )
            if winner != trace_winner:
                raise ValueError(
                    f"recomputed winner {winner!r} for {spec.decision_id} disagrees with trace "
                    f"selected {trace_winner!r}"
                )
            published = published_diagnostics.get((module, spec.decision_id))
            if published is None:
                raise ValueError(
                    f"missing published selection diagnostics artifact for {module}/{spec.decision_id}"
                )
            if _compute_rule_diagnostics_sha256(published) != trace_diag_sha:
                raise ValueError(
                    f"published diagnostics artifact SHA for {spec.decision_id} disagrees with trace"
                )
        if set(trace_by_pair) != rebuilt_pairs:
            raise ValueError(
                "selection trace candidates do not agree with the independently rebuilt DecisionSpec"
            )
    ceiling = _load_json_object_bytes(artifact_bytes(Path(ceiling_report_path)), "ceiling report")
    _validate_ceiling_hit_report(ceiling)
    if ceiling != build_ceiling_hit_report(normalized_fit_rows):
        raise ValueError("ceiling report does not match fit-status evidence")
    leakage = _load_json_object_bytes(artifact_bytes(Path(leakage_audit_path)), "leakage audit")
    _validate_leakage_audit(leakage)
    artifact_hashes = {str(path): hashlib.sha256(artifact_bytes(path)).hexdigest() for path in paths}
    return {
        "bundle_version": "study02-pre-unseal-v3",
        "code_commit": code_commit.lower(),
        "effective_config_sha256": effective_config_sha256,
        "module_run_ids": dict(sorted(module_run_ids.items())),
        "selection_trace_hashes": {module: traces[module][1] for module in sorted(traces)},
        "artifact_hashes": dict(sorted(artifact_hashes.items())),
        "test_state": "sealed",
    }


def write_pre_unseal_bundle(destination: Path, **kwargs: Any) -> dict[str, Any]:
    bundle = build_pre_unseal_bundle(**kwargs)
    _publish_bytes_no_replace(_canonical_json_bytes(bundle), destination)
    return bundle


def _read_selection_ledger(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    _, records = _read_jsonl(path, "Formal selection ledger")
    return records


def _resolve_distinct_selection_paths(
    trace_path: Path,
    receipt_path: Path,
    ledger_path: Path,
) -> tuple[Path, Path, Path]:
    try:
        paths = tuple(Path(path).resolve(strict=False) for path in (trace_path, receipt_path, ledger_path))
    except (OSError, TypeError) as exc:
        raise ValueError(f"Selection paths cannot be resolved: {exc}") from exc
    for index, first in enumerate(paths):
        for second in paths[index + 1:]:
            if first == second:
                raise ValueError("Selection trace, receipt, and ledger paths must be distinct")
            if first.exists() and second.exists():
                try:
                    if first.samefile(second):
                        raise ValueError("Selection trace, receipt, and ledger paths must be distinct")
                except OSError as exc:
                    raise ValueError(f"Selection path identity cannot be verified: {exc}") from exc
    return paths


def publish_selection_receipt(
    *,
    receipt_path: Path,
    ledger_path: Path,
    module_id: str,
    run_id: str,
    trace_path: Path,
    trace_sha256: str,
    effective_config: EffectiveFormalConfig,
    code_commit: str,
) -> dict[str, Any]:
    """Publish one immutable selection receipt and its unique ledger binding."""

    trace_path, receipt_path, ledger_path = _resolve_distinct_selection_paths(
        trace_path, receipt_path, ledger_path
    )
    if module_id not in _PREDECESSOR_BY_MODULE:
        raise ValueError(f"Unsupported formal selection module_id: {module_id!r}")
    if not isinstance(run_id, str) or not run_id.strip():
        raise ValueError("Selection receipt run_id is required")
    if not isinstance(code_commit, str) or _CODE_COMMIT_RE.fullmatch(code_commit) is None:
        raise ValueError("Selection receipt code_commit must be a full commit ID")
    _validate_effective_config(effective_config)
    actual_trace_sha, record_count, decision_count = _validate_selection_trace(
        trace_path, trace_sha256, module_id, run_id
    )
    if receipt_path.exists():
        raise FileExistsError(f"Selection receipt already exists: {receipt_path}")

    receipt = {
        "receipt_version": "study02-formal-selection-v3",
        "module_id": module_id,
        "run_id": run_id,
        "selection_trace_sha256": actual_trace_sha,
        "effective_config_sha256": effective_config.effective_config_sha256,
        "code_commit": code_commit.lower(),
        "record_count": record_count,
        "decision_count": decision_count,
    }
    lock_path = ledger_path.with_name(ledger_path.name + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ValueError(f"Formal selection ledger binding is locked: {ledger_path}") from exc
    os.close(lock_fd)
    try:
        existing = _read_selection_ledger(ledger_path)
        same_run = [
            row for row in existing
            if row.get("binding_type") == "formal-selection"
            and row.get("module_id") == module_id
            and row.get("run_id") == run_id
        ]
        if same_run:
            raise ValueError(f"Formal selection binding already exists for {module_id}/{run_id}")
        _publish_json_no_replace(receipt, receipt_path)
        receipt_sha256 = hashlib.sha256(receipt_path.read_bytes()).hexdigest()
        ledger_entry = {
            "binding_type": "formal-selection",
            **receipt,
            "receipt_sha256": receipt_sha256,
        }
        try:
            append_ledger(ledger_entry, ledger_path)
        except Exception:
            receipt_path.unlink(missing_ok=True)
            raise
    finally:
        lock_path.unlink(missing_ok=True)
    return {**receipt, "receipt_sha256": receipt_sha256}


def _coerce_predecessor(value: Mapping[str, Any] | PredecessorTrace) -> PredecessorTrace:
    if isinstance(value, PredecessorTrace):
        return value
    if not isinstance(value, Mapping):
        raise ValueError("Downstream formal module requires predecessor selection trace metadata")
    staged_ledger_path = value.get("staged_ledger_path")
    try:
        return PredecessorTrace(
            module_id=value["module_id"],
            run_id=value["run_id"],
            trace_path=Path(value["trace_path"]),
            trace_sha256=value["trace_sha256"],
            receipt_path=Path(value["receipt_path"]),
            receipt_sha256=value["receipt_sha256"],
            ledger_path=Path(value["ledger_path"]),
            selection_code_commit=value["selection_code_commit"],
            staged_ledger_path=None if staged_ledger_path is None else Path(staged_ledger_path),
            staged_ledger_sha256=value.get("staged_ledger_sha256"),
        )
    except (KeyError, TypeError) as exc:
        raise ValueError("Incomplete predecessor selection trace metadata") from exc


def _validate_staged_resolution_ledger(
    *,
    staged_ledger_path: Path,
    staged_ledger_sha256: str,
    expected_trace_sha: str,
    predecessor_module: str,
    run_id: str,
    code_commit: str,
    effective_config_sha256: str,
) -> dict[str, Any]:
    """Validate a predecessor module's ``staged_resolution_ledger.jsonl`` (single FC authority).

    Lifts the A-E1 staged-ledger verification discipline currently embedded in
    ``formal_g3_control._resolve_a_e1_from_staged_ledger`` into the formal-contracts module so
    every downstream (A-E3 executor, G3 reader, future A-E2) shares one authority. Pure
    validation -- never calls into G3, never reads selection-trace bytes (the caller passes the
    already-verified ``expected_trace_sha``). Verifies:

    * the path SHA-256 matches ``staged_ledger_sha256`` (no swap after binding).
    * each record matches the frozen 13-field schema, ``record_version``, ``module_id``,
      ``run_id``, ``code_commit``, ``effective_config_sha256``, ``selection_trace_sha256``
      (every record binds the verified root trace SHA).
    * the (stage, route) sequence matches the per-module canonical order
      (``_STAGED_LEDGER_SEQUENCES``); a re-chained-but-reordered ledger is a tamper.
    * ``previous_record_sha256`` chains from ``_ZERO_HASH``, ``resolution_sha256`` /
      ``record_sha256`` self-consistency.

    Returns ``{"records": [...], "baseline_route": <str|None>}`` -- ``baseline_route`` is the
    A-E1 ``baseline_input.resolution["selected:F2_or_V"]`` value (the deferred route the A-E3
    executor resolves from the bound file, not from a re-read); ``None`` for A-E3 (no
    baseline_input stage) or when the record is absent in a partial ledger.
    """
    expected_sequence = _STAGED_LEDGER_SEQUENCES.get(predecessor_module)
    if expected_sequence is None:
        raise ValueError(
            f"staged resolution ledger validation has no canonical sequence for predecessor "
            f"module {predecessor_module!r}"
        )
    declared_sha = _require_sha256(staged_ledger_sha256, "Predecessor staged_resolution_ledger SHA-256")
    ledger_bytes = _safe_one_read(staged_ledger_path, "Predecessor staged_resolution_ledger")
    actual_sha = hashlib.sha256(ledger_bytes).hexdigest()
    if actual_sha != declared_sha:
        raise ValueError("Predecessor staged_resolution_ledger SHA-256 mismatch")
    records = _read_jsonl_bytes(ledger_bytes, "Predecessor staged_resolution_ledger")
    if len(records) != len(expected_sequence):
        raise ValueError(
            f"{predecessor_module} staged ledger must contain exactly {len(expected_sequence)} "
            f"records; got {len(records)}"
        )
    lowered_code_commit = str(code_commit).lower()
    baseline_route: str | None = None
    seen: set[tuple[str, str | None]] = set()
    for index, record in enumerate(records):
        if set(record) != _STAGED_LEDGER_REQUIRED_FIELDS:
            raise ValueError(f"{predecessor_module} staged record has unexpected field set: {set(record)}")
        if record.get("record_version") != _STAGED_LEDGER_RECORD_VERSION:
            raise ValueError(
                f"{predecessor_module} staged record_version is {record.get('record_version')!r}"
            )
        if record.get("selection_trace_sha256") != expected_trace_sha:
            raise ValueError(
                f"{predecessor_module} staged record selection_trace_sha256 does not match the "
                f"verified root trace SHA"
            )
        if record.get("module_id") != predecessor_module:
            raise ValueError(
                f"{predecessor_module} staged record module_id is {record.get('module_id')!r}"
            )
        if record.get("run_id") != run_id:
            raise ValueError(f"{predecessor_module} staged record run_id mismatch")
        if record.get("code_commit") != lowered_code_commit:
            raise ValueError(f"{predecessor_module} staged record code_commit mismatch")
        if record.get("effective_config_sha256") != effective_config_sha256:
            raise ValueError(
                f"{predecessor_module} staged record effective_config_sha256 mismatch"
            )
        stage = record.get("stage")
        route = record.get("route")
        actual_key = (stage, route)
        expected_key = expected_sequence[index]
        if actual_key != expected_key:
            raise ValueError(
                f"{predecessor_module} staged ledger semantic order mismatch at index {index}: "
                f"expected {expected_key!r}, got {actual_key!r}"
            )
        if actual_key in seen:
            raise ValueError(f"{predecessor_module} staged ledger duplicate stage/route: {actual_key!r}")
        seen.add(actual_key)
        previous_sha = _ZERO_HASH_FC if index == 0 else records[index - 1]["record_sha256"]
        if record.get("previous_record_sha256") != previous_sha:
            raise ValueError(
                f"{predecessor_module} staged ledger hash chain broken at stage={stage}: "
                f"expected previous={previous_sha}, got {record.get('previous_record_sha256')}"
            )
        resolution = record.get("resolution", {})
        resolution_sha = hashlib.sha256(_canonical_json_bytes(dict(resolution))).hexdigest()
        if record.get("resolution_sha256") != resolution_sha:
            raise ValueError(
                f"{predecessor_module} staged record resolution_sha256 mismatch at stage={stage}"
            )
        core = {key: value for key, value in record.items() if key != "record_sha256"}
        expected_record_sha = hashlib.sha256(_canonical_json_bytes(core)).hexdigest()
        if record.get("record_sha256") != expected_record_sha:
            raise ValueError(
                f"{predecessor_module} staged record SHA mismatch at stage={stage}"
            )
        if predecessor_module == "A-E1" and stage == "baseline_input":
            resolution_value = resolution.get("selected:F2_or_V")
            if resolution_value not in ("F2", "V"):
                raise ValueError(
                    "A-E1 staged baseline_input.resolution['selected:F2_or_V'] must be F2 or V"
                )
            baseline_route = resolution_value
    return {"records": records, "baseline_route": baseline_route}


def _validate_predecessor(
    module_id: str,
    value: Mapping[str, Any] | PredecessorTrace | None,
) -> dict[str, str]:
    expected_module = _PREDECESSOR_BY_MODULE[module_id]
    if expected_module is None:
        if value is not None:
            raise ValueError("A-E1 requires exactly no predecessor")
        return {
            "module_id": "none",
            "run_id": "none",
            "selection_trace_path": "none",
            "selection_trace_sha256": "none",
            "selection_receipt_path": "none",
            "selection_receipt_sha256": "none",
            "selection_ledger_path": "none",
            "selection_staged_ledger_path": "none",
            "selection_staged_ledger_sha256": "none",
            "resolved_baseline_route": "none",
        }

    predecessor = _coerce_predecessor(value)
    if predecessor.module_id != expected_module:
        raise ValueError(
            f"Wrong predecessor module for {module_id}: expected {expected_module}, got {predecessor.module_id!r}"
        )
    if not isinstance(predecessor.run_id, str) or not predecessor.run_id.strip():
        raise ValueError("Predecessor trace run_id is required")
    if not isinstance(predecessor.selection_code_commit, str) or _CODE_COMMIT_RE.fullmatch(
        predecessor.selection_code_commit
    ) is None:
        raise ValueError("Predecessor selection code_commit must be a full commit ID")
    path = Path(predecessor.trace_path)
    trace_bytes = _safe_one_read(path, "Predecessor selection trace")
    actual_digest, record_count, decision_count = _validate_selection_trace_bytes(
        trace_bytes, predecessor.trace_sha256, expected_module, predecessor.run_id
    )

    receipt_path = Path(predecessor.receipt_path)
    receipt_bytes = _safe_one_read(receipt_path, "Predecessor selection receipt")
    declared_receipt_sha = _require_sha256(predecessor.receipt_sha256, "Selection receipt SHA-256")
    actual_receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    if actual_receipt_sha != declared_receipt_sha:
        raise ValueError("Predecessor selection receipt SHA-256 mismatch")
    try:
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Predecessor selection receipt must be valid JSON: {exc}") from exc
    expected_receipt = {
        "receipt_version": "study02-formal-selection-v3",
        "module_id": expected_module,
        "run_id": predecessor.run_id,
        "selection_trace_sha256": actual_digest,
        "effective_config_sha256": APPROVED_EFFECTIVE_CONFIG_SHA256,
        "code_commit": predecessor.selection_code_commit.lower(),
        "record_count": record_count,
        "decision_count": decision_count,
    }
    if receipt != expected_receipt:
        raise ValueError("Predecessor selection receipt does not match trace/config ownership")

    ledger_path = Path(predecessor.ledger_path)
    ledger = _read_jsonl_bytes(_safe_one_read(ledger_path, "Predecessor selection ledger"), "Formal selection ledger")
    same_run = [
        row for row in ledger
        if row.get("binding_type") == "formal-selection"
        and row.get("module_id") == expected_module
        and row.get("run_id") == predecessor.run_id
    ]
    if len(same_run) != 1:
        raise ValueError("Formal selection ledger must contain exactly one binding for predecessor run")
    expected_ledger_entry = {
        "binding_type": "formal-selection",
        **expected_receipt,
        "receipt_sha256": actual_receipt_sha,
    }
    if same_run[0] != expected_ledger_entry:
        raise ValueError("Formal selection ledger binding does not match predecessor receipt")

    # Control-plane v2: when the predecessor module publishes a staged_resolution_ledger
    # (A-E1, A-E3), bind its on-disk SHA + chain through this predecessor trace. The staged
    # ledger is the ONLY on-disk authority for the predecessor's deferred placeholders +
    # final aliases; without this binding, a downstream run rests on an unbound file the
    # predecessor could swap after materialize. Fail-closed BEFORE any claim/training.
    staged_ledger_path = "none"
    staged_ledger_sha = "none"
    resolved_baseline_route = "none"
    if expected_module in _PUBLISHES_STAGED_LEDGER:
        if predecessor.staged_ledger_path is None or predecessor.staged_ledger_sha256 is None:
            raise ValueError(
                f"Predecessor staged_resolution_ledger binding required for module {module_id} "
                f"(predecessor {expected_module} publishes a staged ledger)"
            )
        staged_path = Path(predecessor.staged_ledger_path)
        staged_ledger_sha = _require_sha256(
            predecessor.staged_ledger_sha256, "Predecessor staged_resolution_ledger SHA-256"
        )
        staged_result = _validate_staged_resolution_ledger(
            staged_ledger_path=staged_path,
            staged_ledger_sha256=staged_ledger_sha,
            expected_trace_sha=actual_digest,
            predecessor_module=expected_module,
            run_id=predecessor.run_id,
            code_commit=predecessor.selection_code_commit.lower(),
            effective_config_sha256=APPROVED_EFFECTIVE_CONFIG_SHA256,
        )
        staged_ledger_path = str(staged_path)
        # ``staged_ledger_sha`` stays as the declared SHA (== actual SHA, verified above).
        if staged_result["baseline_route"] is not None:
            resolved_baseline_route = staged_result["baseline_route"]
    return {
        "module_id": predecessor.module_id,
        "run_id": predecessor.run_id,
        "selection_trace_path": str(path),
        "selection_trace_sha256": actual_digest,
        "selection_receipt_path": str(receipt_path),
        "selection_receipt_sha256": actual_receipt_sha,
        "selection_ledger_path": str(ledger_path),
        "selection_staged_ledger_path": staged_ledger_path,
        "selection_staged_ledger_sha256": staged_ledger_sha,
        "resolved_baseline_route": resolved_baseline_route,
    }


def _build_formal_manifest_with_matrix_evidence(
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
    matrix_evidence: _VerifiedMatrixEvidence,
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
    if Path(matrix_path).resolve(strict=False) != matrix_evidence.path:
        raise ValueError("Formal matrix path and internal evidence identity differ")
    requested_rules, requested_fits = _validate_matrix(matrix_evidence, module_id, rule_ids, fit_ids)
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
    """Open and validate the exact frozen matrix once, then build a sealed manifest."""

    evidence = _open_verified_matrix_evidence(matrix_path)
    return _build_formal_manifest_with_matrix_evidence(
        effective_config=effective_config, module_id=module_id, run_id=run_id,
        code_commit=code_commit, matrix_path=matrix_path, rule_ids=rule_ids,
        fit_ids=fit_ids, role_namespaces=role_namespaces,
        screening_seeds=screening_seeds, formal_seeds=formal_seeds,
        predecessor=predecessor, matrix_evidence=evidence,
    )


def build_and_write_formal_manifest(destination: Path, **manifest_kwargs: Any) -> dict[str, Any]:
    """Fully validate, then atomically create a previously absent manifest file."""

    manifest = build_formal_manifest(**manifest_kwargs)
    _publish_json_no_replace(manifest, Path(destination))
    return manifest


__all__ = [
    "FROZEN_MATRIX_ROWS",
    "FROZEN_MATRIX_SHA256",
    "APPROVED_FORMAL_SEEDS",
    "APPROVED_SCREENING_SEEDS",
    "PredecessorTrace",
    "RoleNamespaces",
    "build_ceiling_hit_report",
    "build_fit_status_record",
    "build_and_write_formal_manifest",
    "build_formal_manifest",
    "build_leakage_audit",
    "build_pre_unseal_bundle",
    "publish_selection_receipt",
    "write_ceiling_hit_report",
    "write_fit_status",
    "write_leakage_audit",
    "write_pre_unseal_bundle",
    "write_selection_trace",
]
