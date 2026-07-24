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
from pathlib import Path
from typing import Any, Mapping, Sequence

from .config import FrozenConfig
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
_BUNDLE_VERSION = "study02-g3-pre-unseal-v1"
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
) -> dict[str, Any]:
    """Build the unified G3 pre-unseal bundle (v1). Binds manifest + three modules."""
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


__all__ = [
    "G3RunChain",
    "ResolvedCohortEntry",
    "authorize_g3_test_once",
    "build_g3_pre_unseal_bundle",
    "build_g3_test_manifest",
    "derive_g3_cohort_resolved",
    "initialize_g3_formal_state",
    "publish_g3_approval",
    "publish_g3_bundle",
    "publish_g3_test_manifest",
    "resolve_g3_predecessor_chain",
]
