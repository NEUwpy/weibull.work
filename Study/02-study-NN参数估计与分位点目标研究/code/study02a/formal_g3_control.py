"""Unified G3 test control plane: authority, accreditation, and state.

R3 scope: predecessor chain resolution, authority verification, cohort derivation
with resolved fields, G3 manifest/bundle/approval/state schemas, and the unified
G3 state machine (sealed -> unsealed_once). No test data generation or inference.

Schema versions (all new; v1/v2 of per-module schemas are rejected):
- Manifest: study02-g3-test-manifest-v2
- Bundle:   study02-g3-pre-unseal-v1
- Approval: study02-g3-test-unseal-approval-v1
- State:    study02-g3-formal-state-v1
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import FrozenConfig
from .formal_accreditation import build_module_accreditation_diagnostics
from .formal_config import EffectiveFormalConfig
from .formal_contracts import (
    APPROVED_EFFECTIVE_CONFIG_SHA256,
    FROZEN_MATRIX_ROWS,
    FROZEN_MATRIX_SHA256,
    _CODE_COMMIT_RE,
    _PREDECESSOR_BY_MODULE,
)
from .matrix import expand_module_matrix

_MANIFEST_VERSION = "study02-g3-test-manifest-v2"
_BUNDLE_VERSION = "study02-g3-pre-unseal-v2"
_APPROVAL_VERSION = "study02-g3-test-unseal-approval-v1"
_STATE_VERSION = "study02-g3-formal-state-v1"

_COHORT_FIT_KINDS = frozenset({
    "historical", "controlled", "winner_retrain",
    "output_form", "shared_winner_retrain",
    "selected_size_retrain", "selected_distribution_retrain",
})
_EXPECTED_COHORT_COUNTS = {"A-E1": 205, "A-E3": 110, "A-E2": 100}
_MODULE_ORDER = ("A-E1", "A-E3", "A-E2")


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    return _sha256_bytes(Path(path).read_bytes())


def _publish_no_replace(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"artifact already exists (no-replace): {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


@dataclass(frozen=True)
class ResolvedCohortEntry:
    fit_id: str
    module_id: str
    rule_id: str
    route: str
    distribution: str
    n: int | str
    seed: int
    fit_kind: str
    training_size: int
    architecture: str
    optimizer: str
    loss: str
    checkpoint_sha256: str
    terminal_receipt_sha256: str
    comparison_role: str


@dataclass(frozen=True)
class G3RunChain:
    ae1_run_id: str
    ae1_run_dir: Path
    ae3_run_id: str
    ae3_run_dir: Path
    ae2_run_id: str
    ae2_run_dir: Path
    ae1_authority_sha256: str
    ae3_authority_sha256: str
    ae2_authority_sha256: str


def resolve_g3_predecessor_chain(
    *, ae2_run_dir: Path, artifact_root: Path,
) -> G3RunChain:
    """Resolve the three-run G3 predecessor chain from the final A-E2 run.

    Follows the manifest predecessor bindings: A-E2 -> A-E3 -> A-E1.
    No directory scanning; the chain is uniquely determined by the manifests.
    """
    ae2_run_dir = Path(ae2_run_dir).resolve()
    ae2_manifest = _load_run_manifest(ae2_run_dir, "A-E2")

    ae3_binding = ae2_manifest["predecessor"]
    if ae3_binding["module_id"] != "A-E3":
        raise ValueError(f"A-E2 predecessor must be A-E3, got {ae3_binding['module_id']!r}")
    ae3_run_id = ae3_binding["run_id"]
    ae3_run_dir = (artifact_root / "A-E3" / ae3_run_id).resolve()
    ae3_manifest = _load_run_manifest(ae3_run_dir, "A-E3")

    ae1_binding = ae3_manifest["predecessor"]
    if ae1_binding["module_id"] != "A-E1":
        raise ValueError(f"A-E3 predecessor must be A-E1, got {ae1_binding['module_id']!r}")
    ae1_run_id = ae1_binding["run_id"]
    ae1_run_dir = (artifact_root / "A-E1" / ae1_run_id).resolve()
    ae1_manifest = _load_run_manifest(ae1_run_dir, "A-E1")

    _verify_ae1_predecessor_is_none(ae1_manifest)

    return G3RunChain(
        ae1_run_id=ae1_run_id, ae1_run_dir=ae1_run_dir,
        ae3_run_id=ae3_run_id, ae3_run_dir=ae3_run_dir,
        ae2_run_id=ae2_manifest["run_id"], ae2_run_dir=ae2_run_dir,
        ae1_authority_sha256=ae1_manifest["scheduler"]["authority"]["authority_sha256"],
        ae3_authority_sha256=ae3_manifest["scheduler"]["authority"]["authority_sha256"],
        ae2_authority_sha256=ae2_manifest["scheduler"]["authority"]["authority_sha256"],
    )


def _load_run_manifest(run_dir: Path, expected_module: str) -> dict[str, Any]:
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"manifest.json not found: {manifest_path}")
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest_bytes != _canonical(manifest):
        raise ValueError(f"manifest is non-canonical: {manifest_path}")
    if manifest.get("module_id") != expected_module:
        raise ValueError(f"manifest module_id is {manifest.get('module_id')!r}, expected {expected_module!r}")
    return manifest


def _verify_ae1_predecessor_is_none(manifest: dict[str, Any]) -> None:
    pred = manifest.get("predecessor", {})
    for field in ("module_id", "run_id", "selection_trace_path", "selection_trace_sha256",
                  "selection_receipt_path", "selection_receipt_sha256", "selection_ledger_path"):
        if pred.get(field, "none") != "none":
            raise ValueError(f"A-E1 predecessor field {field} must be 'none', got {pred.get(field)!r}")


def derive_g3_cohort_resolved(
    *, frozen_config: FrozenConfig, chain: G3RunChain,
) -> tuple[ResolvedCohortEntry, ...]:
    """Derive the 415-entry cohort with all fields resolved from authority.

    No selected:* placeholders, no -1 training sizes, no guessed values.
    Resolution comes from the frozen matrix + selection/staged evidence in the run dirs.
    """
    matrix = expand_module_matrix(frozen_config)
    cohort_rows = matrix[matrix["fit_kind"].isin(_COHORT_FIT_KINDS)]

    resolutions = _load_resolutions(chain)

    entries: list[ResolvedCohortEntry] = []
    counts: dict[str, int] = {}

    for _, row in cohort_rows.iterrows():
        fit_id = str(row["fit_id"])
        module_id = str(row["module"])
        rule_id = str(row["rule_id"])
        fit_kind = str(row["fit_kind"])
        seed = int(row["seed"])
        n_raw = row["n"]
        n: int | str = "shared" if n_raw == "shared" else int(n_raw)

        route = _resolve_field(str(row["route"]), "route", module_id, resolutions)
        loss = _resolve_field(str(row["loss"]), "loss", module_id, resolutions)
        architecture = _resolve_field(str(row["architecture"]), "architecture", module_id, resolutions)
        optimizer = _resolve_field(str(row["optimizer"]), "optimizer", module_id, resolutions)
        training_size = _resolve_training_size(int(row["training_size"]), module_id, fit_kind, resolutions)
        distribution = _resolve_distribution(module_id, fit_kind, resolutions)
        comparison_role = _comparison_role(fit_kind)

        run_dir = _run_dir_for_module(chain, module_id)
        checkpoint_path = run_dir / "outputs" / fit_id / "checkpoint.pt"
        receipt_path = run_dir / "outputs" / fit_id / "fit_status.json"
        if not checkpoint_path.is_file():
            raise ValueError(f"cohort fit {fit_id} ({module_id}/{fit_kind}) checkpoint missing: {checkpoint_path}")
        if not receipt_path.is_file():
            raise ValueError(f"cohort fit {fit_id} ({module_id}/{fit_kind}) terminal receipt missing: {receipt_path}")
        checkpoint_sha = _sha256_file(checkpoint_path)
        receipt_sha = _sha256_file(receipt_path)
        if not checkpoint_sha or not receipt_sha:
            raise ValueError(f"cohort fit {fit_id} has empty checkpoint or receipt SHA")

        _reject_unresolved(route, "route", fit_id)
        _reject_unresolved(loss, "loss", fit_id)
        _reject_unresolved(architecture, "architecture", fit_id)
        _reject_unresolved(optimizer, "optimizer", fit_id)
        if training_size <= 0:
            raise ValueError(f"fit {fit_id} has unresolved training_size: {training_size}")

        entries.append(ResolvedCohortEntry(
            fit_id=fit_id, module_id=module_id, rule_id=rule_id, route=route,
            distribution=distribution, n=n, seed=seed, fit_kind=fit_kind,
            training_size=training_size, architecture=architecture, optimizer=optimizer,
            loss=loss, checkpoint_sha256=checkpoint_sha, terminal_receipt_sha256=receipt_sha,
            comparison_role=comparison_role,
        ))
        counts[module_id] = counts.get(module_id, 0) + 1

    for module_id, expected in _EXPECTED_COHORT_COUNTS.items():
        actual = counts.get(module_id, 0)
        if actual != expected:
            raise ValueError(f"cohort count for {module_id} is {actual}, expected {expected}")

    return tuple(entries)


def _run_dir_for_module(chain: G3RunChain, module_id: str) -> Path:
    if module_id == "A-E1":
        return chain.ae1_run_dir
    if module_id == "A-E3":
        return chain.ae3_run_dir
    if module_id == "A-E2":
        return chain.ae2_run_dir
    raise ValueError(f"unknown module: {module_id}")


def _load_resolutions(chain: G3RunChain) -> dict[str, dict[str, str]]:
    """Load placeholder resolutions from verified selection/staged evidence.

    Every resolution must come from a verified trace/receipt/ledger file.
    No defaults, no exception swallowing, no guessed values.
    """
    resolutions: dict[str, dict[str, str]] = {"A-E1": {}, "A-E3": {}, "A-E2": {}}

    staged_ledger = chain.ae1_run_dir / "staged_resolution_ledger.jsonl"
    if not staged_ledger.is_file():
        raise ValueError(f"A-E1 staged_resolution_ledger.jsonl not found: {staged_ledger}")
    for line in staged_ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        aliases = record.get("final_aliases") or {}
        for key, value in aliases.items():
            resolutions["A-E1"][key] = str(value)
        route_result = record.get("route_result") or {}
        if isinstance(route_result, dict):
            for key, value in route_result.items():
                if key.startswith("selected:"):
                    resolutions["A-E1"][key] = str(value)
        staged_receipt = record.get("staged_receipt") or {}
        if isinstance(staged_receipt, dict):
            for key, value in staged_receipt.items():
                if key.startswith("selected:"):
                    resolutions["A-E1"][key] = str(value)

    for module_id, run_dir in [("A-E3", chain.ae3_run_dir), ("A-E2", chain.ae2_run_dir)]:
        selection_dir = run_dir / "selection"
        if not selection_dir.is_dir():
            raise ValueError(f"{module_id} selection directory not found: {selection_dir}")
        trace_files = sorted(selection_dir.glob("selection_trace*.json"))
        if not trace_files:
            raise ValueError(f"{module_id} has no selection trace files in {selection_dir}")
        for trace_file in trace_files:
            trace_bytes = trace_file.read_bytes()
            records = json.loads(trace_bytes.decode("utf-8"))
            if isinstance(records, dict) and "records" in records:
                records = records["records"]
            if not isinstance(records, list):
                raise ValueError(f"{module_id} selection trace {trace_file.name} is not a record list")
            for rec in records:
                if not isinstance(rec, dict):
                    raise ValueError(f"{module_id} selection trace record is not a dict")
                if rec.get("selected") is True:
                    candidate_id = str(rec.get("candidate_id", ""))
                    decision_id = str(rec.get("decision_id", ""))
                    if candidate_id:
                        resolutions[module_id][f"selected:{decision_id}"] = candidate_id

    return resolutions


def _resolve_field(value: str, field_name: str, module_id: str, resolutions: dict) -> str:
    if not value.startswith("selected:") and not value.startswith("selected_top_"):
        return value
    for mod in (module_id, "A-E1"):
        resolved = resolutions.get(mod, {}).get(value)
        if resolved:
            return resolved
    raise ValueError(
        f"cannot resolve {field_name} placeholder {value!r} for module {module_id}; "
        f"no verified trace/receipt/ledger provides this resolution"
    )


def _resolve_training_size(value: int, module_id: str, fit_kind: str, resolutions: dict) -> int:
    if value > 0:
        return value
    resolved = resolutions.get(module_id, {}).get("selected_training_size")
    if resolved and resolved.isdigit():
        return int(resolved)
    raise ValueError(
        f"cannot resolve training_size for module {module_id} fit_kind {fit_kind}; "
        f"matrix value is {value} and no verified selection provides the resolved size"
    )


def _resolve_distribution(module_id: str, fit_kind: str, resolutions: dict) -> str:
    if fit_kind == "historical":
        return "legacy_grid"
    if fit_kind == "selected_distribution_retrain":
        resolved = resolutions.get(module_id, {}).get("selected:A-E2_distribution")
        if resolved:
            return resolved
        raise ValueError(
            f"cannot resolve distribution for {module_id}/{fit_kind}; "
            f"no verified selection provides selected:A-E2_distribution"
        )
    return "core_continuous"


def _comparison_role(fit_kind: str) -> str:
    if fit_kind == "historical":
        return "diagnostic"
    if fit_kind == "controlled":
        return "attribution"
    if fit_kind in ("winner_retrain", "output_form", "shared_winner_retrain"):
        return "main_comparison"
    if fit_kind in ("selected_size_retrain", "selected_distribution_retrain"):
        return "finalist"
    return "unknown"


def _reject_unresolved(value: str, field: str, fit_id: str) -> None:
    if value.startswith("selected:") or value.startswith("selected_top_"):
        raise ValueError(f"fit {fit_id} has unresolved {field}: {value!r}")


def build_g3_test_manifest(
    *, cohort: tuple[ResolvedCohortEntry, ...], chain: G3RunChain,
    frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
    code_commit: str,
) -> dict[str, Any]:
    """Build the G3 test-execution manifest (v2). Generated BEFORE approval."""
    if not _CODE_COMMIT_RE.fullmatch(code_commit):
        raise ValueError("code_commit must be a full hex commit ID")
    if effective_config.effective_config_sha256 != APPROVED_EFFECTIVE_CONFIG_SHA256:
        raise ValueError("effective config SHA mismatch")

    seeds = frozen_config.protocol["seeds"]
    formal_sizes = frozen_config.protocol["formal_sizes"]["module_test"]

    manifest = {
        "manifest_version": _MANIFEST_VERSION,
        "code_commit": code_commit.lower(),
        "effective_config_sha256": effective_config.effective_config_sha256,
        "frozen_matrix_sha256": FROZEN_MATRIX_SHA256,
        "frozen_matrix_rows": FROZEN_MATRIX_ROWS,
        "run_chain": {
            "A-E1": {"run_id": chain.ae1_run_id, "authority_sha256": chain.ae1_authority_sha256},
            "A-E3": {"run_id": chain.ae3_run_id, "authority_sha256": chain.ae3_authority_sha256},
            "A-E2": {"run_id": chain.ae2_run_id, "authority_sha256": chain.ae2_authority_sha256},
        },
        "cohort_total": len(cohort),
        "cohort_counts": dict(sorted(
            {m: sum(1 for e in cohort if e.module_id == m) for m in _MODULE_ORDER}.items()
        )),
        "cohort_entries": [
            {
                "fit_id": e.fit_id, "module_id": e.module_id, "rule_id": e.rule_id,
                "route": e.route, "distribution": e.distribution, "n": e.n,
                "seed": e.seed, "fit_kind": e.fit_kind, "training_size": e.training_size,
                "architecture": e.architecture, "optimizer": e.optimizer, "loss": e.loss,
                "checkpoint_sha256": e.checkpoint_sha256,
                "terminal_receipt_sha256": e.terminal_receipt_sha256,
                "comparison_role": e.comparison_role,
            }
            for e in cohort
        ],
        "test_namespaces": {
            m: {"design": int(seeds["module_test_design"][m]), "sample": int(seeds["module_test_sample"][m])}
            for m in _MODULE_ORDER
        },
        "test_sizes": {
            "parameter_points": int(formal_sizes["parameter_points"]),
            "repeats_per_point_n": int(formal_sizes["repeats_per_point_n"]),
        },
        "traditional_methods": {
            "primary": ["mle", "mps", "wmle", "mdm", "lre"],
            "diagnostic": ["mmle", "lse", "mm", "pwm"],
        },
        "failure_penalty": 10.0,
        "output_schema": "study02-g3-test-evidence-v1",
    }
    manifest_bytes = _canonical(manifest)
    manifest["manifest_sha256"] = _sha256_bytes(manifest_bytes)
    return manifest


def publish_g3_test_manifest(manifest: dict[str, Any], output_dir: Path) -> Path:
    """Persist the G3 test manifest as a no-replace canonical file."""
    manifest_sha = manifest.get("manifest_sha256")
    if not manifest_sha:
        raise ValueError("manifest missing manifest_sha256")
    content = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    payload = _canonical(content)
    if _sha256_bytes(payload) != manifest_sha:
        raise ValueError("manifest_sha256 does not match canonical bytes")
    path = output_dir / "g3_test_manifest.json"
    _publish_no_replace(path, _canonical(manifest))
    return path


def build_g3_pre_unseal_bundle(
    *, manifest: dict[str, Any], chain: G3RunChain,
    selection_trace_shas: Mapping[str, str],
    ceiling_report_shas: Mapping[str, str],
    leakage_audit_shas: Mapping[str, str],
    staged_ledger_shas: Mapping[str, str],
) -> dict[str, Any]:
    """Build the unified G3 pre-unseal bundle (v2). Binds manifest + three modules + staged ledger."""
    manifest_sha = manifest.get("manifest_sha256")
    if not manifest_sha:
        raise ValueError("manifest missing manifest_sha256")

    bundle = {
        "bundle_version": _BUNDLE_VERSION,
        "code_commit": manifest["code_commit"],
        "effective_config_sha256": manifest["effective_config_sha256"],
        "frozen_matrix_sha256": FROZEN_MATRIX_SHA256,
        "g3_test_manifest_sha256": manifest_sha,
        "module_run_ids": {
            "A-E1": chain.ae1_run_id,
            "A-E3": chain.ae3_run_id,
            "A-E2": chain.ae2_run_id,
        },
        "module_authority_sha256s": {
            "A-E1": chain.ae1_authority_sha256,
            "A-E3": chain.ae3_authority_sha256,
            "A-E2": chain.ae2_authority_sha256,
        },
        "selection_trace_hashes": dict(sorted(selection_trace_shas.items())),
        "staged_ledger_hashes": dict(sorted(staged_ledger_shas.items())),
        "ceiling_report_hashes": dict(sorted(ceiling_report_shas.items())),
        "leakage_audit_hashes": dict(sorted(leakage_audit_shas.items())),
        "test_state": "sealed",
    }
    bundle_bytes = _canonical(bundle)
    bundle["bundle_sha256"] = _sha256_bytes(bundle_bytes)
    return bundle


def publish_g3_bundle(bundle: dict[str, Any], output_dir: Path) -> Path:
    """Persist the G3 bundle as a no-replace canonical file."""
    bundle_sha = bundle.get("bundle_sha256")
    if not bundle_sha:
        raise ValueError("bundle missing bundle_sha256")
    content = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
    payload = _canonical(content)
    if _sha256_bytes(payload) != bundle_sha:
        raise ValueError("bundle_sha256 does not match canonical bytes")
    path = output_dir / "g3_pre_unseal_bundle.json"
    _publish_no_replace(path, _canonical(bundle))
    return path


def publish_g3_approval(
    *, approval_path: Path, bundle: dict[str, Any],
    oracle_review_sha256: str, issued_at: str,
) -> None:
    """Publish an external oracle APPROVE for the unified G3 test unseal."""
    bundle_sha = bundle.get("bundle_sha256")
    if not bundle_sha:
        raise ValueError("bundle missing bundle_sha256")
    approval = {
        "approval_version": _APPROVAL_VERSION,
        "decision": "APPROVE G3 test unseal",
        "code_commit": bundle["code_commit"],
        "effective_config_sha256": bundle["effective_config_sha256"],
        "frozen_matrix_sha256": FROZEN_MATRIX_SHA256,
        "g3_pre_unseal_bundle_sha256": bundle_sha,
        "g3_test_manifest_sha256": bundle["g3_test_manifest_sha256"],
        "selection_trace_hashes": bundle["selection_trace_hashes"],
        "oracle_review_artifact_sha256": oracle_review_sha256,
        "issued_at": issued_at,
    }
    _publish_no_replace(approval_path, _canonical(approval))


def initialize_g3_formal_state(
    *, state_path: Path, bundle: dict[str, Any],
    run_family_id: str, timestamp: str,
) -> dict[str, Any]:
    """Create the unified G3 formal state in sealed mode."""
    if state_path.exists():
        raise ValueError(f"G3 formal state already exists: {state_path}")
    bundle_sha = bundle.get("bundle_sha256")
    if not bundle_sha:
        raise ValueError("bundle missing bundle_sha256")
    state = {
        "state_version": _STATE_VERSION,
        "run_family_id": run_family_id,
        "state": "sealed",
        "transition_seq": 0,
        "code_commit": bundle["code_commit"],
        "effective_config_sha256": bundle["effective_config_sha256"],
        "frozen_matrix_sha256": FROZEN_MATRIX_SHA256,
        "g3_pre_unseal_bundle_sha256": bundle_sha,
        "g3_test_manifest_sha256": bundle["g3_test_manifest_sha256"],
        "approval_sha256": None,
        "result_receipt_sha256": None,
        "failure_receipt_sha256": None,
        "created_at": timestamp,
        "updated_at": timestamp,
        "test_access_count": 0,
    }
    _publish_no_replace(state_path, _canonical(state))
    return state


def _validate_reusable_g3_formal_state(
    state: Mapping[str, Any], *, bundle: Mapping[str, Any], manifest: Mapping[str, Any],
) -> None:
    """Accept only the exact deterministic sealed genesis state on a builder rerun."""
    expected_fields = {
        "state_version", "run_family_id", "state", "transition_seq", "code_commit",
        "effective_config_sha256", "frozen_matrix_sha256",
        "g3_pre_unseal_bundle_sha256", "g3_test_manifest_sha256",
        "approval_sha256", "result_receipt_sha256", "failure_receipt_sha256",
        "created_at", "updated_at", "test_access_count",
    }
    if set(state) != expected_fields:
        raise ValueError("existing unified G3 state field set conflicts with sealed genesis")
    expected_values = {
        "state_version": _STATE_VERSION,
        "run_family_id": "G3-formal",
        "state": "sealed",
        "code_commit": bundle["code_commit"],
        "effective_config_sha256": bundle["effective_config_sha256"],
        "frozen_matrix_sha256": FROZEN_MATRIX_SHA256,
        "g3_pre_unseal_bundle_sha256": bundle["bundle_sha256"],
        "g3_test_manifest_sha256": manifest["manifest_sha256"],
        "approval_sha256": None,
        "result_receipt_sha256": None,
        "failure_receipt_sha256": None,
    }
    for field, expected in expected_values.items():
        if state.get(field) != expected:
            raise ValueError(
                f"existing unified G3 state {field} conflicts with sealed genesis"
            )
    for field in ("transition_seq", "test_access_count"):
        value = state.get(field)
        if type(value) is not int or value != 0:
            raise ValueError(
                f"existing unified G3 state {field} conflicts with sealed genesis"
            )
    created_at = state.get("created_at")
    updated_at = state.get("updated_at")
    if not isinstance(created_at, str) or updated_at != created_at:
        raise ValueError(
            "existing unified G3 state timestamps conflict with sealed genesis"
        )
    try:
        if not created_at.endswith("Z"):
            raise ValueError
        parsed = datetime.fromisoformat(created_at[:-1] + "+00:00")
        if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
            raise ValueError
        canonical = parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        raise ValueError(
            "existing unified G3 state timestamps conflict with sealed genesis"
        ) from None
    if created_at != canonical:
        raise ValueError(
            "existing unified G3 state timestamps conflict with sealed genesis"
        )


def _atomic_write(path: Path, payload: bytes) -> None:
    """Write payload to path atomically: temp file + fsync + rename."""
    tmp = path.with_name(path.name + ".tmp")
    with open(tmp, "wb") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(str(tmp), str(path))


def _append_ledger_fsync(event: dict, ledger_path: Path) -> None:
    """Append canonical event to ledger with flush + fsync."""
    event_bytes = _canonical(event)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    with open(ledger_path, "ab") as f:
        f.write(event_bytes)
        f.flush()
        os.fsync(f.fileno())


def _acquire_lock(lock_path: Path, holder_id: str) -> None:
    """Acquire exclusive lock. Fail-closed if lock exists. No mtime preemption."""
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise ValueError(
            f"G3 state is locked by another holder: {lock_path}. "
            f"Cannot prove owner is dead; fail-closed. Manual recovery required."
        )
    try:
        payload = json.dumps({"holder": holder_id, "pid": os.getpid()}).encode()
        with os.fdopen(fd, "wb") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
    except BaseException:
        lock_path.unlink(missing_ok=True)
        raise


def _release_lock(lock_path: Path) -> None:
    lock_path.unlink(missing_ok=True)


def authorize_g3_test_once(
    *, state_path: Path, bundle_path: Path, approval_path: Path,
    manifest_path: Path, oracle_review_path: Path, ledger_path: Path,
    timestamp: str, holder_id: str = "g3-authorize",
) -> dict[str, Any]:
    """Transition the unified G3 state: sealed -> unsealed_once.

    Fail-closed lock (no mtime preemption), journal with field-by-field event
    reconstruction from verified inputs, atomic state replace with fsync.
    """
    lock_path = state_path.with_name(state_path.name + ".lock")
    journal_path = state_path.with_name(state_path.name + ".journal")

    _acquire_lock(lock_path, holder_id)
    try:
        _recover_g3_journal(
            journal_path, state_path, ledger_path,
            bundle_path=bundle_path, manifest_path=manifest_path,
            approval_path=approval_path, oracle_review_path=oracle_review_path,
        )

        state_bytes = state_path.read_bytes()
        state = json.loads(state_bytes.decode("utf-8"))
        if state_bytes != _canonical(state):
            raise ValueError("G3 state is non-canonical")
        if state.get("state_version") != _STATE_VERSION:
            raise ValueError(f"G3 state version must be {_STATE_VERSION}, got {state.get('state_version')!r}")
        if state.get("state") != "sealed":
            raise ValueError(f"G3 state must be sealed, got {state.get('state')!r}")
        if state.get("test_access_count") != 0:
            raise ValueError("G3 test_access_count must be 0 before authorization")

        bundle_bytes = bundle_path.read_bytes()
        bundle = json.loads(bundle_bytes.decode("utf-8"))
        if bundle_bytes != _canonical(bundle):
            raise ValueError("G3 bundle is non-canonical")
        if bundle.get("bundle_version") != _BUNDLE_VERSION:
            raise ValueError(f"G3 bundle version must be {_BUNDLE_VERSION}, got {bundle.get('bundle_version')!r}")
        bundle_content = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
        bundle_sha = _sha256_bytes(_canonical(bundle_content))
        if bundle.get("bundle_sha256") != bundle_sha:
            raise ValueError("G3 bundle self-SHA mismatch")
        if state.get("g3_pre_unseal_bundle_sha256") != bundle_sha:
            raise ValueError("G3 bundle SHA mismatch with state")

        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes.decode("utf-8"))
        if manifest_bytes != _canonical(manifest):
            raise ValueError("G3 manifest is non-canonical")
        manifest_content = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
        manifest_sha = _sha256_bytes(_canonical(manifest_content))
        if manifest.get("manifest_sha256") != manifest_sha:
            raise ValueError("G3 manifest self-SHA mismatch")
        if bundle.get("g3_test_manifest_sha256") != manifest_sha:
            raise ValueError("G3 bundle does not bind this manifest")
        if state.get("g3_test_manifest_sha256") != manifest_sha:
            raise ValueError("G3 state does not bind this manifest")

        approval_bytes = approval_path.read_bytes()
        approval = json.loads(approval_bytes.decode("utf-8"))
        if approval_bytes != _canonical(approval):
            raise ValueError("G3 approval is non-canonical")
        if approval.get("approval_version") != _APPROVAL_VERSION:
            raise ValueError(f"G3 approval version must be {_APPROVAL_VERSION}")
        if approval.get("decision") != "APPROVE G3 test unseal":
            raise ValueError("G3 approval decision must be 'APPROVE G3 test unseal'")
        if approval.get("g3_pre_unseal_bundle_sha256") != bundle_sha:
            raise ValueError("G3 approval does not bind this bundle")
        if approval.get("g3_test_manifest_sha256") != manifest_sha:
            raise ValueError("G3 approval manifest SHA mismatch")
        if approval.get("code_commit") != bundle.get("code_commit"):
            raise ValueError("G3 approval code_commit mismatch")
        if approval.get("frozen_matrix_sha256") != FROZEN_MATRIX_SHA256:
            raise ValueError("G3 approval matrix SHA mismatch")

        if not oracle_review_path.is_file():
            raise ValueError(f"oracle review artifact not found: {oracle_review_path}")
        oracle_review_sha = _sha256_file(oracle_review_path)
        if approval.get("oracle_review_artifact_sha256") != oracle_review_sha:
            raise ValueError("G3 approval oracle_review_artifact_sha256 does not match artifact on disk")

        approval_sha = _sha256_bytes(approval_bytes)

        after = {**state, "state": "unsealed_once", "transition_seq": 1,
                 "approval_sha256": approval_sha, "test_access_count": 1,
                 "updated_at": timestamp}
        after_bytes = _canonical(after)

        event = {
            "transition_version": "study02-g3-formal-transition-v1",
            "run_family_id": state["run_family_id"],
            "transition": "authorize_g3_test_once",
            "seq": 1,
            "before_state_sha256": _sha256_bytes(state_bytes),
            "after_state_sha256": _sha256_bytes(after_bytes),
            "approval_sha256": approval_sha,
            "g3_pre_unseal_bundle_sha256": bundle_sha,
            "g3_test_manifest_sha256": manifest_sha,
            "test_access_count": 1,
            "timestamp": timestamp,
        }

        ledger_bytes_before = ledger_path.read_bytes() if ledger_path.is_file() else b""
        journal_record = {
            "event": event,
            "ledger_size_before": len(ledger_bytes_before),
            "ledger_sha_before": _sha256_bytes(ledger_bytes_before),
        }
        _atomic_write(journal_path, _canonical(journal_record))

        _atomic_write(state_path, after_bytes)

        _append_ledger_fsync(event, ledger_path)

        journal_path.unlink()
        return after

    finally:
        _release_lock(lock_path)


def _recover_g3_journal(
    journal_path: Path, state_path: Path, ledger_path: Path,
    *, bundle_path: Path, manifest_path: Path,
    approval_path: Path, oracle_review_path: Path,
) -> None:
    """Recover from a crash mid-transition.

    Reconstructs the expected event from verified inputs (state, bundle, manifest,
    approval, oracle review) and compares field-by-field with the journal event.
    Never unconditionally trusts the journal. All failures leave bytes unchanged.
    """
    if not journal_path.is_file():
        return
    journal_bytes = journal_path.read_bytes()
    journal = json.loads(journal_bytes.decode("utf-8"))
    if journal_bytes != _canonical(journal):
        raise ValueError("G3 journal is non-canonical")

    event = journal.get("event")
    if not isinstance(event, dict):
        raise ValueError("G3 journal event must be a dict")
    required_event_fields = {
        "transition_version", "run_family_id", "transition", "seq",
        "before_state_sha256", "after_state_sha256", "approval_sha256",
        "g3_pre_unseal_bundle_sha256", "g3_test_manifest_sha256",
        "test_access_count", "timestamp",
    }
    if set(event) != required_event_fields:
        raise ValueError("G3 journal event schema mismatch")

    size_before = journal.get("ledger_size_before")
    if not isinstance(size_before, int) or isinstance(size_before, bool) or size_before < 0:
        raise ValueError("G3 journal ledger_size_before is invalid")
    sha_before = journal.get("ledger_sha_before")
    if not isinstance(sha_before, str) or len(sha_before) != 64:
        raise ValueError("G3 journal ledger_sha_before is invalid")

    ledger_bytes = ledger_path.read_bytes() if ledger_path.is_file() else b""
    if len(ledger_bytes) < size_before:
        raise ValueError("G3 journal ledger prefix conflicts: ledger shorter than recorded snapshot")
    if _sha256_bytes(ledger_bytes[:size_before]) != sha_before:
        raise ValueError("G3 journal ledger prefix conflicts: SHA mismatch with recorded snapshot")

    state_bytes = state_path.read_bytes()
    state_sha = _sha256_bytes(state_bytes)

    if state_sha == event["before_state_sha256"]:
        if len(ledger_bytes) != size_before:
            raise ValueError("G3 journal before-state requires unchanged ledger snapshot")
        journal_path.unlink()
        return

    if state_sha != event["after_state_sha256"]:
        raise ValueError("G3 journal matches neither before nor after state — corruption")

    _verify_journal_event_against_inputs(
        event, state_path=state_path, bundle_path=bundle_path,
        manifest_path=manifest_path, approval_path=approval_path,
        oracle_review_path=oracle_review_path,
    )

    event_bytes = _canonical(event)
    suffix = ledger_bytes[size_before:]
    if suffix == event_bytes:
        journal_path.unlink()
        return
    if not event_bytes.startswith(suffix):
        raise ValueError("G3 journal after-state ledger tail conflicts with exact event")

    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    if ledger_path.is_file() and size_before > 0:
        fd = os.open(str(ledger_path), os.O_WRONLY)
        try:
            os.ftruncate(fd, size_before)
            os.fsync(fd)
        finally:
            os.close(fd)
    elif ledger_path.is_file():
        ledger_path.unlink()
    _append_ledger_fsync(event, ledger_path)
    journal_path.unlink()


def _verify_journal_event_against_inputs(
    event: dict, *, state_path: Path, bundle_path: Path,
    manifest_path: Path, approval_path: Path, oracle_review_path: Path,
) -> None:
    """Reconstruct the expected event from verified inputs and compare field-by-field.

    The journal event must be uniquely determined by the verified state, bundle,
    manifest, approval, and oracle review. Any mismatch means the journal is forged.
    """
    if not approval_path.is_file():
        raise ValueError("G3 journal recovery: approval input missing")
    if not bundle_path.is_file():
        raise ValueError("G3 journal recovery: bundle input missing")
    if not manifest_path.is_file():
        raise ValueError("G3 journal recovery: manifest input missing")
    if not oracle_review_path.is_file():
        raise ValueError("G3 journal recovery: oracle review input missing")

    approval_bytes = approval_path.read_bytes()
    approval = json.loads(approval_bytes.decode("utf-8"))
    if approval_bytes != _canonical(approval):
        raise ValueError("G3 journal recovery: approval is non-canonical")
    if approval.get("approval_version") != _APPROVAL_VERSION:
        raise ValueError("G3 journal recovery: approval version mismatch")
    if approval.get("decision") != "APPROVE G3 test unseal":
        raise ValueError("G3 journal recovery: approval decision mismatch")

    bundle_bytes = bundle_path.read_bytes()
    bundle = json.loads(bundle_bytes.decode("utf-8"))
    if bundle_bytes != _canonical(bundle):
        raise ValueError("G3 journal recovery: bundle is non-canonical")
    bundle_content = {k: v for k, v in bundle.items() if k != "bundle_sha256"}
    bundle_sha = _sha256_bytes(_canonical(bundle_content))

    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes.decode("utf-8"))
    if manifest_bytes != _canonical(manifest):
        raise ValueError("G3 journal recovery: manifest is non-canonical")
    manifest_content = {k: v for k, v in manifest.items() if k != "manifest_sha256"}
    manifest_sha = _sha256_bytes(_canonical(manifest_content))

    oracle_review_sha = _sha256_file(oracle_review_path)
    if approval.get("oracle_review_artifact_sha256") != oracle_review_sha:
        raise ValueError("G3 journal recovery: oracle review SHA mismatch")

    approval_sha = _sha256_bytes(approval_bytes)

    if event["approval_sha256"] != approval_sha:
        raise ValueError("G3 journal event approval_sha256 does not match verified approval")
    if event["g3_pre_unseal_bundle_sha256"] != bundle_sha:
        raise ValueError("G3 journal event bundle SHA does not match verified bundle")
    if event["g3_test_manifest_sha256"] != manifest_sha:
        raise ValueError("G3 journal event manifest SHA does not match verified manifest")
    if event["transition"] != "authorize_g3_test_once":
        raise ValueError("G3 journal event transition mismatch")
    if event["seq"] != 1:
        raise ValueError("G3 journal event seq must be 1")
    if event["test_access_count"] != 1:
        raise ValueError("G3 journal event test_access_count must be 1")
    if approval.get("g3_pre_unseal_bundle_sha256") != bundle_sha:
        raise ValueError("G3 journal recovery: approval does not bind verified bundle")
    if approval.get("g3_test_manifest_sha256") != manifest_sha:
        raise ValueError("G3 journal recovery: approval does not bind verified manifest")


@dataclass(frozen=True)
class G3Authority:
    ae1_manifest: dict
    ae1_plan: list
    ae1_state: dict
    ae1_events: list
    ae3_manifest: dict
    ae3_plan: list
    ae3_state: dict
    ae3_events: list
    ae2_manifest: dict
    ae2_plan: list
    ae2_state: dict
    ae2_events: list


def verify_g3_chain_authority(
    *, chain: G3RunChain, cache_root: Path,
) -> G3Authority:
    """Content-addressed verification of all three sealed runs (R3-C).

    Each run is verified via ``verify_historical_authority``: scoped code blobs are
    read from the git object database at each manifest's sealed ``code_commit``
    (no checkout, no worktree, no requirement that current HEAD match any sealed
    commit). Each run must pass full replay: manifest, plan, events, scheduler
    state, controller anchors. The historical verifier also enforces terminal
    sealed status (no live claim) for every predecessor. Active runs still use
    ``_rebuild_authority`` (current-HEAD strict) outside this function.
    """
    from .formal_scheduler import verify_historical_authority

    ae1_manifest, ae1_plan, ae1_state, ae1_events = verify_historical_authority(
        chain.ae1_run_dir, cache_root,
    )
    ae3_manifest, ae3_plan, ae3_state, ae3_events = verify_historical_authority(
        chain.ae3_run_dir, cache_root,
    )
    ae2_manifest, ae2_plan, ae2_state, ae2_events = verify_historical_authority(
        chain.ae2_run_dir, cache_root,
    )

    # verify_historical_authority already enforces no-live-claim per module; the
    # explicit re-check below is defense-in-depth against any future caller that
    # might bypass the historical verifier.
    for module_id, state in [("A-E1", ae1_state), ("A-E3", ae3_state), ("A-E2", ae2_state)]:
        live_claim = state.get("live_claim")
        if live_claim is not None:
            raise ValueError(f"{module_id} has a live claim: {live_claim}")

    _verify_chain_consistency(
        ae1_manifest, ae3_manifest, ae2_manifest, chain,
    )

    return G3Authority(
        ae1_manifest=ae1_manifest, ae1_plan=ae1_plan, ae1_state=ae1_state, ae1_events=ae1_events,
        ae3_manifest=ae3_manifest, ae3_plan=ae3_plan, ae3_state=ae3_state, ae3_events=ae3_events,
        ae2_manifest=ae2_manifest, ae2_plan=ae2_plan, ae2_state=ae2_state, ae2_events=ae2_events,
    )


def _verify_chain_consistency(
    ae1_manifest: dict, ae3_manifest: dict, ae2_manifest: dict, chain: G3RunChain,
) -> None:
    """Verify module/run/predecessor, per-module code authority, effective config, matrix.

    R3-C: the old ``len(code_commits) == 1`` gate is removed. Each module carries its
    own independent code authority (bound in its manifest's ``scheduler.authority``).
    Cross-commit chains are valid as long as predecessor authority continuity holds:
    each downstream's predecessor段 must bind the exact authority triple
    (``code_commit``, ``scoped_code_sha256``, ``authority_sha256``) of the predecessor
    module's sealed manifest. Forged authority triples or stale predecessor bindings
    fail closed here.
    """
    if ae1_manifest.get("module_id") != "A-E1":
        raise ValueError(f"A-E1 manifest module_id is {ae1_manifest.get('module_id')!r}")
    if ae3_manifest.get("module_id") != "A-E3":
        raise ValueError(f"A-E3 manifest module_id is {ae3_manifest.get('module_id')!r}")
    if ae2_manifest.get("module_id") != "A-E2":
        raise ValueError(f"A-E2 manifest module_id is {ae2_manifest.get('module_id')!r}")

    if ae1_manifest.get("run_id") != chain.ae1_run_id:
        raise ValueError("A-E1 manifest run_id mismatch with chain")
    if ae3_manifest.get("run_id") != chain.ae3_run_id:
        raise ValueError("A-E3 manifest run_id mismatch with chain")
    if ae2_manifest.get("run_id") != chain.ae2_run_id:
        raise ValueError("A-E2 manifest run_id mismatch with chain")

    # R3-C: per-module independent code authority. Each manifest binds its own
    # code_commit (content-addressed by verify_historical_authority); cross-commit
    # chains are valid. The old single-commit gate is replaced by predecessor
    # authority continuity checks below.

    config_shas = {
        ae1_manifest.get("effective_config", {}).get("sha256"),
        ae3_manifest.get("effective_config", {}).get("sha256"),
        ae2_manifest.get("effective_config", {}).get("sha256"),
    }
    if len(config_shas) != 1:
        raise ValueError(f"three runs have inconsistent effective_config: {config_shas}")
    if config_shas.pop() != APPROVED_EFFECTIVE_CONFIG_SHA256:
        raise ValueError("effective_config_sha256 does not match frozen approved config")

    matrix_shas = {
        ae1_manifest.get("matrix", {}).get("sha256"),
        ae3_manifest.get("matrix", {}).get("sha256"),
        ae2_manifest.get("matrix", {}).get("sha256"),
    }
    if len(matrix_shas) != 1:
        raise ValueError(f"three runs have inconsistent matrix SHA: {matrix_shas}")
    if matrix_shas.pop() != FROZEN_MATRIX_SHA256:
        raise ValueError("matrix SHA does not match FROZEN_MATRIX_SHA256")

    ae3_pred = ae3_manifest.get("predecessor", {})
    if ae3_pred.get("module_id") != "A-E1" or ae3_pred.get("run_id") != chain.ae1_run_id:
        raise ValueError("A-E3 predecessor does not point to A-E1 chain run")
    ae2_pred = ae2_manifest.get("predecessor", {})
    if ae2_pred.get("module_id") != "A-E3" or ae2_pred.get("run_id") != chain.ae3_run_id:
        raise ValueError("A-E2 predecessor does not point to A-E3 chain run")

    # R3-C predecessor authority continuity: each downstream predecessor段 must bind
    # the exact authority triple of its predecessor module's sealed manifest. This is
    # the cross-commit linkage -- it proves the downstream was sealed against the
    # specific predecessor authority, not a swapped or forged one. v1 manifests
    # without the triple fields are rejected here (v1/v2 mixing fails closed).
    _assert_predecessor_authority_continuity("A-E3", ae3_pred, ae1_manifest)
    _assert_predecessor_authority_continuity("A-E2", ae2_pred, ae3_manifest)


def _assert_predecessor_authority_continuity(
    downstream_module: str,
    predecessor_section: Mapping[str, Any],
    predecessor_manifest: Mapping[str, Any],
) -> None:
    """Verify the downstream's predecessor段 binds the predecessor's sealed authority.

    Extracts the authority triple (``code_commit``, ``scoped_code_sha256``,
    ``authority_sha256``) from the predecessor manifest's ``scheduler.authority``
    block and compares it against the triple bound in the downstream's predecessor
    section. A mismatch means the downstream was sealed against a different
    predecessor authority (swap, stale binding, or forgery) and fails closed.
    """
    if predecessor_manifest.get("module_id") != predecessor_section.get("module_id"):
        raise ValueError(
            f"{downstream_module} predecessor authority continuity: predecessor段 "
            f"module_id {predecessor_section.get('module_id')!r} does not match "
            f"the chained predecessor manifest module_id "
            f"{predecessor_manifest.get('module_id')!r}"
        )
    predecessor_authority = predecessor_manifest.get("scheduler", {}).get("authority", {})
    triple_fields = ("code_commit", "scoped_code_sha256", "authority_sha256")
    for field in triple_fields:
        bound_value = predecessor_section.get(field)
        sealed_value = predecessor_authority.get(field)
        if bound_value is None:
            raise ValueError(
                f"{downstream_module} predecessor段 is missing authority triple field "
                f"{field!r} (v1/v2 schema mixing is rejected)"
            )
        if sealed_value is None or bound_value != sealed_value:
            raise ValueError(
                f"{downstream_module} predecessor authority discontinuity: {field} "
                f"bound={bound_value!r} but predecessor manifest authority has "
                f"{sealed_value!r}"
            )



def derive_g3_cohort_from_authority(
    *, frozen_config: FrozenConfig, chain: G3RunChain, authority: G3Authority,
) -> tuple[ResolvedCohortEntry, ...]:
    """Derive the 415-entry cohort verified against replay authority.

    Every fit must be terminal succeeded in the replay state, with checkpoint
    and scheduler terminal receipt SHAs verified. Non-succeeded or missing fails closed.
    Distribution comes from the verified plan row, not hardcoded.
    """
    matrix = expand_module_matrix(frozen_config)
    cohort_rows = matrix[matrix["fit_kind"].isin(_COHORT_FIT_KINDS)]

    fit_states_by_module = {
        "A-E1": authority.ae1_state.get("fit_states", {}),
        "A-E3": authority.ae3_state.get("fit_states", {}),
        "A-E2": authority.ae2_state.get("fit_states", {}),
    }
    plans_by_module = {
        "A-E1": {str(row["fit_id"]): row for row in authority.ae1_plan},
        "A-E3": {str(row["fit_id"]): row for row in authority.ae3_plan},
        "A-E2": {str(row["fit_id"]): row for row in authority.ae2_plan},
    }
    run_dirs = {
        "A-E1": chain.ae1_run_dir,
        "A-E3": chain.ae3_run_dir,
        "A-E2": chain.ae2_run_dir,
    }

    entries: list[ResolvedCohortEntry] = []
    counts: dict[str, int] = {}

    for _, row in cohort_rows.iterrows():
        fit_id = str(row["fit_id"])
        module_id = str(row["module"])
        fit_kind = str(row["fit_kind"])
        seed = int(row["seed"])
        n_raw = row["n"]
        n: int | str = "shared" if n_raw == "shared" else int(n_raw)

        fit_states = fit_states_by_module[module_id]
        fit_state = fit_states.get(fit_id)
        if fit_state != "succeeded":
            raise ValueError(
                f"cohort fit {fit_id} ({module_id}/{fit_kind}) is not terminal succeeded; "
                f"replay state is {fit_state!r}"
            )

        run_dir = run_dirs[module_id]
        checkpoint_path = run_dir / "outputs" / fit_id / "checkpoint.pt"
        if not checkpoint_path.is_file():
            raise ValueError(f"cohort fit {fit_id} checkpoint missing: {checkpoint_path}")
        checkpoint_sha = _sha256_file(checkpoint_path)

        receipt_path = run_dir / "receipts" / f"{fit_id}.succeeded.json"
        if not receipt_path.is_file():
            raise ValueError(f"cohort fit {fit_id} scheduler terminal receipt missing: {receipt_path}")
        terminal_receipt_sha = _sha256_file(receipt_path)

        plan_row = plans_by_module[module_id].get(fit_id)
        distribution = str(plan_row["distribution"]) if plan_row and "distribution" in plan_row else "core_continuous"

        route = str(row["route"])
        loss = str(row["loss"])
        architecture = str(row["architecture"])
        optimizer = str(row["optimizer"])
        training_size = int(row["training_size"])

        entries.append(ResolvedCohortEntry(
            fit_id=fit_id, module_id=module_id, rule_id=str(row["rule_id"]),
            route=route, distribution=distribution, n=n, seed=seed,
            fit_kind=fit_kind, training_size=training_size,
            architecture=architecture, optimizer=optimizer, loss=loss,
            checkpoint_sha256=checkpoint_sha, terminal_receipt_sha256=terminal_receipt_sha,
            comparison_role=_comparison_role(fit_kind),
        ))
        counts[module_id] = counts.get(module_id, 0) + 1

    for module_id, expected in _EXPECTED_COHORT_COUNTS.items():
        actual = counts.get(module_id, 0)
        if actual != expected:
            raise ValueError(f"cohort count for {module_id} is {actual}, expected {expected}")

    return tuple(entries)


def resolve_g3_placeholders_from_evidence(
    *, chain: G3RunChain, cohort: tuple[ResolvedCohortEntry, ...],
    code_commit: str, effective_config_sha256: str, frozen_config: FrozenConfig,
    study_root: Path, cache_root: Path,
) -> tuple[ResolvedCohortEntry, ...]:
    """Resolve all selected:*/selected_top_*/training_size=-1 from verified selection evidence.

    A-E1: verified staged ledger (hash chain + field binding) → final_aliases + baseline_input.
    A-E3/A-E2: _validate_selection_evidence on run-root trace/receipt/ledger → explicit alias mapping.
    No defaults, no glob, no raw JSON trust, no selected:{decision_id} guessing.
    """
    resolutions: dict[str, dict[str, str]] = {"A-E1": {}, "A-E3": {}, "A-E2": {}}

    _resolve_a_e1_from_staged_ledger(
        chain.ae1_run_dir, chain.ae1_run_id, code_commit, effective_config_sha256,
        resolutions["A-E1"], study_root=study_root, cache_root=cache_root,
        frozen_config=frozen_config,
    )
    _resolve_a_e3_from_selection(
        chain.ae3_run_dir, chain.ae3_run_id, resolutions["A-E3"], frozen_config=frozen_config,
    )
    _resolve_a_e2_from_selection(
        chain.ae2_run_dir, chain.ae2_run_id, resolutions["A-E2"], frozen_config=frozen_config,
    )

    resolved_entries: list[ResolvedCohortEntry] = []
    for entry in cohort:
        route = _resolve_or_fail(entry.route, "route", entry.module_id, entry.fit_id, resolutions)
        loss = _resolve_or_fail(entry.loss, "loss", entry.module_id, entry.fit_id, resolutions)
        architecture = _resolve_or_fail(entry.architecture, "architecture", entry.module_id, entry.fit_id, resolutions)
        optimizer = _resolve_or_fail(entry.optimizer, "optimizer", entry.module_id, entry.fit_id, resolutions)
        training_size = entry.training_size
        if training_size <= 0:
            resolved_size = resolutions.get(entry.module_id, {}).get("selected_training_size")
            if not resolved_size or not resolved_size.isdigit():
                raise ValueError(
                    f"fit {entry.fit_id} has training_size={training_size} and no verified resolution"
                )
            training_size = int(resolved_size)

        distribution = _resolve_distribution_for_entry(entry, resolutions)

        resolved_entries.append(ResolvedCohortEntry(
            fit_id=entry.fit_id, module_id=entry.module_id, rule_id=entry.rule_id,
            route=route, distribution=distribution, n=entry.n, seed=entry.seed,
            fit_kind=entry.fit_kind, training_size=training_size,
            architecture=architecture, optimizer=optimizer, loss=loss,
            checkpoint_sha256=entry.checkpoint_sha256,
            terminal_receipt_sha256=entry.terminal_receipt_sha256,
            comparison_role=entry.comparison_role,
        ))
    return tuple(resolved_entries)


def _resolve_a_e1_from_staged_ledger(
    run_dir: Path, run_id: str, code_commit: str, effective_config_sha256: str,
    out: dict[str, str], *, study_root: Path, cache_root: Path,
    frozen_config: FrozenConfig, baseline_score_fit=None,
) -> None:
    """Read and verify A-E1 staged resolution ledger; extract final_aliases + baseline_input.

    First validates root selection_trace/receipt/ledger via _validate_selection_evidence,
    then verifies every staged record binds the verified trace SHA, correct record_version,
    resolution_sha256, full field set, unique stages, order, and predecessor references.
    """
    from .formal_executor import _validate_selection_evidence, _read_staged_ledger, _ZERO_HASH

    trace_path = run_dir / "selection_trace.jsonl"
    receipt_path = run_dir / "selection_receipt.json"
    ledger_path = run_dir / "selection_ledger.jsonl"
    for p, name in [(trace_path, "selection_trace.jsonl"), (receipt_path, "selection_receipt.json"), (ledger_path, "selection_ledger.jsonl")]:
        if not p.is_file():
            raise ValueError(f"A-E1 {name} required at run root: {p}")

    verified_trace_sha = _sha256_file(trace_path)
    _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=verified_trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E1", run_id=run_id,
    )

    staged_path = run_dir / "staged_resolution_ledger.jsonl"
    if not staged_path.is_file():
        raise ValueError(f"A-E1 staged_resolution_ledger.jsonl required: {staged_path}")
    records = _read_staged_ledger(run_dir)
    if not records:
        raise ValueError("A-E1 staged resolution ledger is empty")

    _STAGED_REQUIRED_FIELDS = {
        "record_version", "module_id", "run_id", "code_commit",
        "effective_config_sha256", "selection_trace_sha256", "stage", "route",
        "previous_record_sha256", "input", "resolution", "resolution_sha256",
        "record_sha256",
    }
    _EXPECTED_SEQUENCE = (
        ("stage1", "F2"),
        ("stage2", "F2"),
        ("winner_retrain", "F2"),
        ("stage1", "V"),
        ("stage2", "V"),
        ("winner_retrain", "V"),
        ("baseline_input", None),
        ("final_aliases", None),
    )
    _STAGED_RECORD_VERSION = "study02-staged-resolution-v1"

    previous_sha = _ZERO_HASH
    if len(records) != len(_EXPECTED_SEQUENCE):
        raise ValueError(
            f"A-E1 staged ledger must contain exactly {len(_EXPECTED_SEQUENCE)} records; "
            f"got {len(records)}"
        )
    by_stage_route: dict[tuple[str, str | None], dict[str, Any]] = {}
    for index, record in enumerate(records):
        if set(record) != _STAGED_REQUIRED_FIELDS:
            raise ValueError(f"A-E1 staged record has unexpected field set: {set(record)}")
        if record.get("record_version") != _STAGED_RECORD_VERSION:
            raise ValueError(f"A-E1 staged record_version is {record.get('record_version')!r}")
        if record.get("selection_trace_sha256") != verified_trace_sha:
            raise ValueError(
                f"A-E1 staged record selection_trace_sha256 does not match verified root trace SHA"
            )
        if record.get("module_id") != "A-E1":
            raise ValueError(f"A-E1 staged record module_id is {record.get('module_id')!r}")
        if record.get("run_id") != run_id:
            raise ValueError("A-E1 staged record run_id mismatch")
        if record.get("code_commit") != code_commit.lower():
            raise ValueError("A-E1 staged record code_commit mismatch")
        if record.get("effective_config_sha256") != effective_config_sha256:
            raise ValueError("A-E1 staged record effective_config_sha256 mismatch")

        stage = record.get("stage")
        route = record.get("route")
        actual_key = (stage, route)
        expected_key = _EXPECTED_SEQUENCE[index]
        if actual_key != expected_key:
            raise ValueError(
                f"A-E1 staged ledger semantic order mismatch at index {index}: "
                f"expected {expected_key!r}, got {actual_key!r}"
            )
        if actual_key in by_stage_route:
            raise ValueError(f"A-E1 staged ledger duplicate stage/route: {actual_key!r}")
        by_stage_route[actual_key] = record

        if record.get("previous_record_sha256") != previous_sha:
            raise ValueError(
                f"A-E1 staged ledger hash chain broken at stage={stage}: "
                f"expected previous={previous_sha}, got {record.get('previous_record_sha256')}"
            )

        resolution = record.get("resolution", {})
        resolution_sha = _sha256_bytes(_canonical(dict(resolution)))
        if record.get("resolution_sha256") != resolution_sha:
            raise ValueError(f"A-E1 staged record resolution_sha256 mismatch at stage={stage}")

        core = {k: v for k, v in record.items() if k != "record_sha256"}
        expected_sha = _sha256_bytes(_canonical(core))
        if record.get("record_sha256") != expected_sha:
            raise ValueError(f"A-E1 staged record SHA mismatch at stage={stage}")

        previous_sha = record["record_sha256"]

    # Reconstruct stage-1 and stage-2 meanings from the independently verified root
    # selection evidence, then require the staged ledger to bind those exact meanings.
    from .formal_executor import (
        _A_E1_STAGE2_FROZEN_LOSS,
        _a_e1_stage1_decision_id,
        _a_e1_stage2_decision_id,
        _build_a_e1_baseline_candidates,
        _parse_stage2_winner_candidate,
        _resolve_a_e1_baseline,
        _score_a_e1_winner_retrain,
        resolve_selected_placeholders,
    )
    from .formal_config import load_effective_formal_config

    by_decision: dict[str, list[dict[str, Any]]] = {}
    for trace_record in _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=verified_trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E1", run_id=run_id,
    ):
        by_decision.setdefault(str(trace_record["decision_id"]), []).append(trace_record)

    aliases = ("selected:A-E1_loss", "selected:A-E1_architecture", "selected:A-E1_optimizer")
    route_resolutions: dict[str, dict[str, str]] = {}
    for route in ("F2", "V"):
        stage1 = by_stage_route[("stage1", route)]
        stage2 = by_stage_route[("stage2", route)]
        retrain = by_stage_route[("winner_retrain", route)]
        stage1_decision = _a_e1_stage1_decision_id(route)
        stage2_decision = _a_e1_stage2_decision_id(route)
        expected_top4 = resolve_selected_placeholders(
            placeholders={f"selected_top_{slot}": stage1_decision for slot in range(1, 5)},
            selection_trace_path=trace_path, selection_trace_sha256=verified_trace_sha,
            selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
            module_id="A-E1", run_id=run_id,
        )
        if stage1.get("input", {}).get("decision_id") != stage1_decision:
            raise ValueError(f"A-E1 stage1:{route} decision_id cross-binding mismatch")
        if stage1.get("resolution") != expected_top4:
            raise ValueError(f"A-E1 stage1:{route} top4 resolution disagrees with verified trace")

        selected_stage2 = [r for r in by_decision.get(stage2_decision, ()) if r.get("selected") is True]
        if len(selected_stage2) != 1:
            raise ValueError(f"A-E1 {stage2_decision} must have exactly one selected winner")
        winner_record = selected_stage2[0]
        placeholder, optimizer = _parse_stage2_winner_candidate(str(winner_record["candidate_id"]))
        if placeholder not in expected_top4:
            raise ValueError(f"A-E1 stage2:{route} winner references a slot outside stage1 top4")
        expected_route_resolution = {
            "selected:A-E1_loss": _A_E1_STAGE2_FROZEN_LOSS,
            "selected:A-E1_architecture": expected_top4[placeholder],
            "selected:A-E1_optimizer": optimizer,
        }
        expected_stage2_input = {
            "decision_id": stage2_decision,
            "winner_candidate_id": str(winner_record["candidate_id"]),
            "winner_supporting_evidence_sha256": str(winner_record["supporting_evidence_sha256"]),
            "stage1_record_sha256": stage1["record_sha256"],
            "resolved_top_slot": placeholder,
            "frozen_loss": _A_E1_STAGE2_FROZEN_LOSS,
        }
        if stage2.get("input") != expected_stage2_input:
            raise ValueError(f"A-E1 stage2:{route} input/predecessor cross-binding mismatch")
        if stage2.get("resolution") != expected_route_resolution:
            raise ValueError(f"A-E1 stage2:{route} resolution disagrees with verified trace/top4")
        if retrain.get("input") != {
            "stage2_record_sha256": stage2["record_sha256"],
            "placeholder_fields": list(aliases),
        }:
            raise ValueError(f"A-E1 winner_retrain:{route} stage2 predecessor mismatch")
        if retrain.get("resolution") != expected_route_resolution:
            raise ValueError(f"A-E1 winner_retrain:{route} resolution disagrees with stage2")
        route_resolutions[route] = expected_route_resolution

    baseline = by_stage_route[("baseline_input", None)]
    final = by_stage_route[("final_aliases", None)]
    baseline_resolution = baseline.get("resolution")
    if not isinstance(baseline_resolution, dict) or set(baseline_resolution) != {"selected:F2_or_V"}:
        raise ValueError("A-E1 baseline_input resolution must contain only selected:F2_or_V")
    winner_route = str(baseline_resolution["selected:F2_or_V"])
    if winner_route not in route_resolutions:
        raise ValueError(f"A-E1 baseline_input selected:F2_or_V must be F2 or V, got {winner_route!r}")
    baseline_input = baseline.get("input", {})
    baseline_candidates = _build_a_e1_baseline_candidates(frozen_config)
    rebuilt_evaluations, pending = _score_a_e1_winner_retrain(
        study_root=study_root,
        run_dir=run_dir,
        cache_root=cache_root,
        frozen=frozen_config,
        effective=load_effective_formal_config(study_root),
        candidates=baseline_candidates,
        run_id=run_id,
        score_fit=baseline_score_fit,
    )
    if pending or rebuilt_evaluations is None:
        raise ValueError("A-E1 winner-retrain authority is incomplete during baseline replay")
    expected_winner, baseline_evidence, expected_rule_result = _resolve_a_e1_baseline(
        module_id="A-E1", run_id=run_id, candidates=baseline_candidates,
        evaluations_by_fit=rebuilt_evaluations,
    )
    expected_baseline_input = {
        "decision_id": "baseline_input:A-E1:F2_vs_V",
        "candidate_supporting_evidence_sha256": {
            candidate.candidate_id: baseline_evidence[candidate.candidate_id]["supporting_evidence_sha256"]
            for candidate in baseline_candidates
        },
        "rule_result": dict(expected_rule_result),
        "winner_retrain_fit_count": len(rebuilt_evaluations),
    }
    if winner_route != expected_winner:
        raise ValueError(
            f"A-E1 baseline winner disagrees with independent winner-retrain replay: "
            f"ledger={winner_route!r}, replay={expected_winner!r}"
        )
    if baseline_input != expected_baseline_input:
        raise ValueError("A-E1 baseline input/evidence/rule_result disagrees with independent replay")

    expected_final = route_resolutions[winner_route]
    expected_final_input = {
        "baseline_record_sha256": baseline["record_sha256"],
        "winning_route": winner_route,
        "winning_route_stage2": {
            "loss": expected_final["selected:A-E1_loss"],
            "architecture": expected_final["selected:A-E1_architecture"],
            "optimizer": expected_final["selected:A-E1_optimizer"],
        },
    }
    if final.get("input") != expected_final_input:
        raise ValueError("A-E1 final_aliases baseline/stage2 cross-binding mismatch")
    if final.get("resolution") != expected_final:
        raise ValueError("A-E1 final_aliases do not match the winning route stage2 resolution")
    for key, value in expected_final.items():
        if str(value).startswith(("selected:", "selected_top_")):
            raise ValueError(f"A-E1 final_aliases {key} is still a placeholder: {value!r}")
        out[key] = str(value)
    out["selected:F2_or_V"] = winner_route


_A_E3_ALIAS_MAP = {
    "loss:A-E3:selected:F2_or_V:n10": "selected:A-E3_loss",
    "stage2:A-E3:selected:F2_or_V:n10": "selected:A-E3_architecture",
}


def _decision_specs_for_module(frozen_config: FrozenConfig, module_id: str):
    """Rebuild the module's allowed decision/candidate domain from the frozen matrix."""
    from .selection import build_decision_specs

    rows = expand_module_matrix(frozen_config)
    return build_decision_specs(
        module_id,
        rows[rows["module"] == module_id].to_dict("records"),
    )


def _resolve_a_e3_from_selection(
    run_dir: Path, run_id: str, out: dict[str, str], *, frozen_config: FrozenConfig,
) -> None:
    """Resolve A-E3 aliases from verified selection trace/receipt/ledger at run root.

    Uses resolve_selected_placeholders to resolve selected_top_N → concrete architecture
    for both routes (selected:F2_or_V and S/shared).
    """
    from .formal_executor import _validate_selection_evidence, resolve_selected_placeholders

    trace_path = run_dir / "selection_trace.jsonl"
    receipt_path = run_dir / "selection_receipt.json"
    ledger_path = run_dir / "selection_ledger.jsonl"
    for p, name in [(trace_path, "selection_trace.jsonl"), (receipt_path, "selection_receipt.json"), (ledger_path, "selection_ledger.jsonl")]:
        if not p.is_file():
            raise ValueError(f"A-E3 {name} required at run root: {p}")

    trace_sha = _sha256_file(trace_path)
    records = _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id,
    )
    expected_candidates = {
        spec.decision_id: {candidate.candidate_id for candidate in spec.candidates}
        for spec in _decision_specs_for_module(frozen_config, "A-E3")
    }

    evidence_kwargs = dict(
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id,
    )

    fv_stage1_dec = "architecture:A-E3:selected:F2_or_V:n10"
    fv_stage2_dec = "stage2:A-E3:selected:F2_or_V:n10"
    s_stage1_dec = "architecture:A-E3:S:shared"
    s_stage2_dec = "stage2:A-E3:S:shared"

    fv_top4 = resolve_selected_placeholders(
        placeholders={f"selected_top_{slot}": fv_stage1_dec for slot in range(1, 5)},
        **evidence_kwargs,
    )
    s_top4 = resolve_selected_placeholders(
        placeholders={f"selected_top_{slot}": s_stage1_dec for slot in range(1, 5)},
        **evidence_kwargs,
    )

    for rec in records:
        if rec.get("selected") is not True:
            continue
        decision_id = str(rec["decision_id"])
        candidate_id = str(rec["candidate_id"])
        if decision_id in expected_candidates and candidate_id not in expected_candidates[decision_id]:
            raise ValueError(f"A-E3 {decision_id} winner {candidate_id!r} is outside the frozen candidates")

        if decision_id == "loss:A-E3:selected:F2_or_V:n10":
            out["selected:A-E3_loss"] = candidate_id
        elif decision_id == fv_stage2_dec:
            arch_placeholder, sep, optimizer = candidate_id.partition(":")
            if sep != ":" or not optimizer:
                raise ValueError(f"A-E3 F2/V stage2 winner {candidate_id!r} is not slot:optimizer")
            concrete_arch = fv_top4.get(arch_placeholder)
            if not concrete_arch:
                raise ValueError(f"A-E3 F2/V stage2 winner references {arch_placeholder!r} not in top4")
            out["selected:A-E3_architecture"] = concrete_arch
            out["selected:A-E3_optimizer"] = optimizer
        elif decision_id == s_stage2_dec:
            arch_placeholder, sep, optimizer = candidate_id.partition(":")
            if sep != ":" or not optimizer:
                raise ValueError(f"A-E3 S/shared stage2 winner {candidate_id!r} is not slot:optimizer")
            concrete_arch = s_top4.get(arch_placeholder)
            if not concrete_arch:
                raise ValueError(f"A-E3 S/shared stage2 winner references {arch_placeholder!r} not in top4")
            out["selected:S_architecture"] = concrete_arch
            out["selected:S_optimizer"] = optimizer
        elif decision_id == "output_form:A-E3:selected:F2_or_V":
            out["selected:A-E3_baseline"] = candidate_id

    if "selected:A-E3_loss" not in out:
        raise ValueError("A-E3 selection has no verified loss winner")
    if "selected:A-E3_architecture" not in out:
        raise ValueError("A-E3 selection has no verified F2/V architecture winner")
    if "selected:A-E3_optimizer" not in out:
        raise ValueError("A-E3 selection has no verified F2/V optimizer winner")
    if "selected:A-E3_baseline" not in out:
        raise ValueError("A-E3 selection has no verified output_form/baseline winner")
    if "selected:S_architecture" not in out:
        raise ValueError("A-E3 selection has no verified S/shared architecture winner")
    if "selected:S_optimizer" not in out:
        raise ValueError("A-E3 selection has no verified S/shared optimizer winner")


def _resolve_a_e2_from_selection(
    run_dir: Path, run_id: str, out: dict[str, str], *, frozen_config: FrozenConfig,
) -> None:
    """Resolve A-E2 aliases from verified selection trace/receipt/ledger at run root."""
    from .formal_executor import _validate_selection_evidence

    trace_path = run_dir / "selection_trace.jsonl"
    receipt_path = run_dir / "selection_receipt.json"
    ledger_path = run_dir / "selection_ledger.jsonl"
    for p, name in [(trace_path, "selection_trace.jsonl"), (receipt_path, "selection_receipt.json"), (ledger_path, "selection_ledger.jsonl")]:
        if not p.is_file():
            raise ValueError(f"A-E2 {name} required at run root: {p}")

    trace_sha = _sha256_file(trace_path)
    records = _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E2", run_id=run_id,
    )
    expected_candidates = {
        spec.decision_id: {candidate.candidate_id for candidate in spec.candidates}
        for spec in _decision_specs_for_module(frozen_config, "A-E2")
    }

    for rec in records:
        if rec.get("selected") is not True:
            continue
        decision_id = str(rec["decision_id"])
        candidate_id = str(rec["candidate_id"])
        if decision_id in expected_candidates and candidate_id not in expected_candidates[decision_id]:
            raise ValueError(f"A-E2 {decision_id} winner {candidate_id!r} is outside the frozen candidates")
        if decision_id == "training_size:A-E2:selected:A-E3_baseline":
            out["selected_training_size"] = candidate_id
        elif decision_id == "distribution:A-E2:selected:A-E3_baseline":
            out["selected:A-E2_distribution"] = candidate_id

    if "selected_training_size" not in out:
        raise ValueError("A-E2 selection has no verified training_size winner")
    if "selected:A-E2_distribution" not in out:
        raise ValueError("A-E2 selection has no verified distribution winner")


def _resolve_distribution_for_entry(entry: ResolvedCohortEntry, resolutions: dict) -> str:
    """Resolve distribution from fit_kind and verified evidence. No defaults."""
    if entry.fit_kind == "historical":
        return "legacy_grid"
    if entry.fit_kind == "controlled":
        return "core_continuous"
    if entry.fit_kind in ("winner_retrain", "output_form", "shared_winner_retrain"):
        return "core_continuous"
    if entry.fit_kind == "selected_size_retrain":
        return "core_continuous"
    if entry.fit_kind == "selected_distribution_retrain":
        resolved = resolutions.get(entry.module_id, {}).get("selected:A-E2_distribution")
        if resolved:
            return resolved
        raise ValueError(
            f"fit {entry.fit_id} requires selected:A-E2_distribution resolution; "
            f"no verified A-E2 distribution selection evidence found"
        )
    raise ValueError(f"fit {entry.fit_id} has unknown fit_kind {entry.fit_kind!r} for distribution resolution")


def _resolve_or_fail(value: str, field: str, module_id: str, fit_id: str, resolutions: dict) -> str:
    if not value.startswith("selected:") and not value.startswith("selected_top_"):
        return value
    for mod in (module_id, "A-E1"):
        resolved = resolutions.get(mod, {}).get(value)
        if resolved:
            return resolved
    raise ValueError(
        f"fit {fit_id} has unresolved {field}={value!r}; "
        f"no verified selection evidence provides this resolution"
    )


def _assert_cohort_fully_resolved(cohort: tuple[ResolvedCohortEntry, ...]) -> None:
    """Final scan: any selected:*, selected_top_*, training_size<=0 fails closed."""
    for entry in cohort:
        for field_name in ("route", "architecture", "optimizer", "loss", "distribution"):
            value = getattr(entry, field_name)
            if value.startswith("selected:") or value.startswith("selected_top_"):
                raise ValueError(
                    f"cohort fit {entry.fit_id} has unresolved {field_name}={value!r} after resolution"
                )
        if entry.training_size <= 0:
            raise ValueError(
                f"cohort fit {entry.fit_id} has training_size={entry.training_size} after resolution"
            )


def _assert_current_code_matches_replay(study_root: Path, code_commit: str) -> None:
    """Independent production guard in addition to each scheduler replay's own checks."""
    from .formal_scheduler import _assert_scoped_code_clean, _git_sha

    _assert_scoped_code_clean(study_root)
    current_commit = _git_sha(study_root).lower()
    if current_commit != code_commit:
        raise ValueError(
            f"current HEAD does not match replay-derived code_commit: "
            f"HEAD={current_commit}, replay={code_commit}"
        )


def build_g3_accreditation(
    *, ae2_run_dir: Path, artifact_root: Path, cache_root: Path,
    study_root: Path, output_dir: Path,
) -> dict[str, Any]:
    """Minimal production entry: chain → authority → cohort → manifest → bundle → state.

    Does NOT authorize, unseal, or generate test data. Produces sealed bundle + state
    persisted to output_dir with no-replace semantics and mutual SHA binding.
    Returns only after all artifacts are on disk and verified.
    """
    from .config import load_frozen_config
    from .formal_config import load_effective_formal_config

    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)

    chain = resolve_g3_predecessor_chain(ae2_run_dir=ae2_run_dir, artifact_root=artifact_root)
    authority = verify_g3_chain_authority(chain=chain, cache_root=cache_root)
    # R3-C: per-module code authority is verified content-addressed inside
    # verify_g3_chain_authority (each manifest's sealed code_commit is read from git
    # objects). The accreditation runs at the current HEAD, which may differ from any
    # sealed predecessor commit (cross-commit chain). We still require the scoped
    # scientific code tree to be clean (no uncommitted edits) so the accreditation
    # logic itself runs on committed code, but we no longer require HEAD to match any
    # one sealed code_commit.
    from .formal_scheduler import _assert_scoped_code_clean, _git_sha
    _assert_scoped_code_clean(study_root)
    # The G3 accreditation artifacts (manifest, bundle, state) bind the CURRENT HEAD
    # as their code_commit -- they are produced by the accreditation code running here,
    # not by any one sealed predecessor. Per-module predecessor authority is verified
    # content-addressed inside verify_g3_chain_authority above.
    code_commit = _git_sha(study_root)

    # Rebuild each module's diagnostics from replay authority + immutable selection
    # evidence. Existing exact diagnostics are accepted idempotently; conflicts fail closed.

    diagnostics = {}
    for module_id, run_id in (
        ("A-E1", chain.ae1_run_id),
        ("A-E3", chain.ae3_run_id),
        ("A-E2", chain.ae2_run_id),
    ):
        rebuilt = build_module_accreditation_diagnostics(
            study_root=study_root, module=module_id, run_id=run_id,
            artifact_root=artifact_root, cache_root=cache_root,
        )
        diagnostics[module_id] = rebuilt

    cohort = derive_g3_cohort_from_authority(frozen_config=frozen, chain=chain, authority=authority)
    cohort = resolve_g3_placeholders_from_evidence(
        chain=chain, cohort=cohort,
        code_commit=code_commit, effective_config_sha256=effective.effective_config_sha256,
        frozen_config=frozen, study_root=study_root, cache_root=cache_root,
    )

    manifest = build_g3_test_manifest(
        cohort=cohort, chain=chain, frozen_config=frozen,
        effective_config=effective, code_commit=code_commit,
    )

    selection_trace_shas = {}
    ceiling_report_shas = {}
    leakage_audit_shas = {}
    staged_ledger_shas = {}
    for module_id, run_dir in [("A-E1", chain.ae1_run_dir), ("A-E3", chain.ae3_run_dir), ("A-E2", chain.ae2_run_dir)]:
        trace_path = run_dir / "selection_trace.jsonl"
        if not trace_path.is_file():
            raise ValueError(f"{module_id}: selection_trace.jsonl required at run root: {trace_path}")
        selection_trace_shas[module_id] = _sha256_file(trace_path)

        ceiling_path = diagnostics[module_id]["ceiling_path"]
        if not ceiling_path.is_file():
            raise ValueError(f"{module_id}: ceiling_hit_report.json required: {ceiling_path}")
        ceiling_report_shas[module_id] = _sha256_file(ceiling_path)

        leakage_path = diagnostics[module_id]["leakage_path"]
        if not leakage_path.is_file():
            raise ValueError(f"{module_id}: leakage_audit.json required: {leakage_path}")
        leakage_audit_shas[module_id] = _sha256_file(leakage_path)

    staged_path = chain.ae1_run_dir / "staged_resolution_ledger.jsonl"
    if not staged_path.is_file():
        raise ValueError(f"A-E1: staged_resolution_ledger.jsonl required: {staged_path}")
    staged_ledger_shas["A-E1"] = _sha256_file(staged_path)

    bundle = build_g3_pre_unseal_bundle(
        manifest=manifest, chain=chain,
        selection_trace_shas=selection_trace_shas,
        ceiling_report_shas=ceiling_report_shas,
        leakage_audit_shas=leakage_audit_shas,
        staged_ledger_shas=staged_ledger_shas,
    )

    _assert_cohort_fully_resolved(cohort)

    output_dir = Path(output_dir)
    manifest_path = output_dir / "g3_test_manifest.json"
    expected_manifest_bytes = _canonical(manifest)
    if manifest_path.exists():
        if manifest_path.read_bytes() != expected_manifest_bytes:
            raise ValueError("existing unified G3 manifest conflicts with deterministic rebuild")
    else:
        manifest_path = publish_g3_test_manifest(manifest, output_dir)
    bundle_path = output_dir / "g3_pre_unseal_bundle.json"
    expected_bundle_bytes = _canonical(bundle)
    if bundle_path.exists():
        if bundle_path.read_bytes() != expected_bundle_bytes:
            raise ValueError("existing unified G3 bundle conflicts with deterministic rebuild")
    else:
        bundle_path = publish_g3_bundle(bundle, output_dir)

    state_path = output_dir / "g3_formal_state.json"
    if not state_path.exists():
        initialize_g3_formal_state(
            state_path=state_path, bundle=bundle,
            run_family_id="G3-formal",
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        )

    state_bytes = state_path.read_bytes()
    state = json.loads(state_bytes.decode("utf-8"))
    if state_bytes != _canonical(state):
        raise ValueError("persisted unified G3 state is not canonical")
    _validate_reusable_g3_formal_state(state, bundle=bundle, manifest=manifest)

    return {
        "status": "sealed_ready_for_approval",
        "manifest_path": str(manifest_path),
        "bundle_path": str(bundle_path),
        "state_path": str(state_path),
        "manifest_sha256": manifest["manifest_sha256"],
        "bundle_sha256": bundle["bundle_sha256"],
        "cohort_total": len(cohort),
        "cohort_counts": dict(sorted(
            {m: sum(1 for e in cohort if e.module_id == m) for m in _MODULE_ORDER}.items()
        )),
    }


__all__ = [
    "G3Authority",
    "G3RunChain",
    "ResolvedCohortEntry",
    "authorize_g3_test_once",
    "build_g3_accreditation",
    "build_g3_pre_unseal_bundle",
    "build_g3_test_manifest",
    "derive_g3_cohort_from_authority",
    "derive_g3_cohort_resolved",
    "initialize_g3_formal_state",
    "publish_g3_approval",
    "publish_g3_bundle",
    "publish_g3_test_manifest",
    "resolve_g3_placeholders_from_evidence",
    "resolve_g3_predecessor_chain",
    "verify_g3_chain_authority",
]
