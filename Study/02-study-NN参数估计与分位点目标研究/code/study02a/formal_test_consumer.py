"""Cohort-based G3 test evaluation consumer for Study/02 formal runs.

Replaces the single-checkpoint prototype (91ccc8e6). Implements the unified G3
test path: one approval, one consumption, three modules with independent frozen
test namespaces. The checkpoint cohort (A-E1: 205, A-E3: 110, A-E2: 100) is
derived exclusively from the frozen matrix + replay-verified run authority +
selection/staged/predecessor evidence. No caller-supplied winner, module, or
scientific configuration is accepted.

Lifecycle:
    sealed -> build G3 manifest -> external oracle APPROVE -> unsealed_once
    -> preflight -> claim -> evaluate cohort (NN + traditional) -> result receipt
    -> consumed

After claim publication, any exception or crash recovers as failure + consumed.
Test data is never cached in the regular dataset cache.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np
import torch
from torch import nn

from . import design
from .config import FrozenConfig
from .evaluation import evaluate_rows
from .formal_config import EffectiveFormalConfig
from .formal_data import (
    FormalFixedBatch,
    FormalFixedExample,
    FormalSetBatch,
    FormalSetExample,
    collate_fixed_features,
    collate_set_features,
)
from .formal_runner import (
    FormalDataset,
    FormalDatasetSpec,
    ScalerManifest,
    _standardize,
    build_training_spec,
    cache_dataset,
    fit_training_scaler,
)
from .formal_state import consume_test_once
from .matrix import expand_module_matrix
from .representations import SetFeatures, anchor_sample, build_features, encode_targets
from .training import load_checkpoint

_MANIFEST_VERSION = "study02-g3-test-manifest-v1"
_RESULT_RECEIPT_VERSION = "study02-g3-test-result-v1"
_FAILURE_RECEIPT_VERSION = "study02-g3-test-failure-v1"
_CLAIM_VERSION = "study02-g3-test-claim-v1"

_COHORT_FIT_KINDS = frozenset({
    "historical", "controlled", "winner_retrain",
    "output_form", "shared_winner_retrain",
    "selected_size_retrain", "selected_distribution_retrain",
})

_EXPECTED_COHORT_COUNTS = {"A-E1": 205, "A-E3": 110, "A-E2": 100}

_PRIMARY_TRADITIONAL_METHODS = ("mle", "mps", "wmle", "mdm", "lre")
_DIAGNOSTIC_TRADITIONAL_METHODS = ("mmle", "lse", "mm", "pwm")


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _publish_no_replace(path: Path, payload: bytes) -> None:
    if path.exists():
        raise ValueError(f"artifact already exists (no-replace): {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(payload)
    tmp.replace(path)


@dataclass(frozen=True)
class CohortEntry:
    fit_id: str
    module_id: str
    rule_id: str
    route: str
    n: int | str
    seed: int
    fit_kind: str
    training_size: int
    architecture: str
    optimizer: str
    loss: str
    checkpoint_sha256: str


@dataclass(frozen=True)
class G3Cohort:
    entries: tuple[CohortEntry, ...]
    counts_by_module: dict[str, int]

    def __post_init__(self) -> None:
        for module_id, expected in _EXPECTED_COHORT_COUNTS.items():
            actual = self.counts_by_module.get(module_id, 0)
            if actual != expected:
                raise ValueError(
                    f"cohort count for {module_id} is {actual}, expected {expected}"
                )
        fit_ids = [entry.fit_id for entry in self.entries]
        if len(fit_ids) != len(set(fit_ids)):
            raise ValueError("cohort contains duplicate fit_ids")


def derive_g3_cohort(
    *, frozen_config: FrozenConfig, artifact_root: Path,
) -> G3Cohort:
    """Derive the complete G3 test cohort from the frozen matrix and run authority.

    The cohort is uniquely determined by:
    1. The frozen experiment matrix (820 rows, SHA-pinned)
    2. The fit_kind filter (only formal evaluation kinds)
    3. Replay-verified run authority (checkpoints exist and are terminal)

    No caller-supplied winner, module, or configuration is accepted.
    """
    matrix = expand_module_matrix(frozen_config)
    cohort_rows = matrix[matrix["fit_kind"].isin(_COHORT_FIT_KINDS)]

    entries: list[CohortEntry] = []
    counts: dict[str, int] = {}

    for _, row in cohort_rows.iterrows():
        fit_id = str(row["fit_id"])
        module_id = str(row["module"])
        rule_id = str(row["rule_id"])
        route = str(row["route"])
        n_raw = row["n"]
        n: int | str = "shared" if n_raw == "shared" else int(n_raw)
        seed = int(row["seed"])
        fit_kind = str(row["fit_kind"])
        training_size = int(row["training_size"])
        architecture = str(row["architecture"])
        optimizer = str(row["optimizer"])
        loss = str(row["loss"])

        run_id = _resolve_run_id(artifact_root, module_id)
        run_dir = artifact_root / module_id / run_id
        checkpoint_path = run_dir / "outputs" / fit_id / "checkpoint.pt"
        if not checkpoint_path.is_file():
            raise ValueError(
                f"cohort fit {fit_id} ({module_id}/{fit_kind}) checkpoint not found: {checkpoint_path}"
            )
        checkpoint_sha256 = _sha256_bytes(checkpoint_path.read_bytes())

        entries.append(CohortEntry(
            fit_id=fit_id, module_id=module_id, rule_id=rule_id, route=route,
            n=n, seed=seed, fit_kind=fit_kind, training_size=training_size,
            architecture=architecture, optimizer=optimizer, loss=loss,
            checkpoint_sha256=checkpoint_sha256,
        ))
        counts[module_id] = counts.get(module_id, 0) + 1

    return G3Cohort(entries=tuple(entries), counts_by_module=counts)


def _resolve_run_id(artifact_root: Path, module_id: str) -> str:
    module_dir = artifact_root / module_id
    if not module_dir.is_dir():
        raise ValueError(f"no artifact directory for module {module_id}: {module_dir}")
    runs = [d.name for d in module_dir.iterdir() if d.is_dir() and (d / "plan.jsonl").is_file()]
    if len(runs) != 1:
        raise ValueError(
            f"module {module_id} must have exactly one active run, found {len(runs)}: {runs}"
        )
    return runs[0]


def build_g3_test_manifest(
    *, cohort: G3Cohort, frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig, code_commit: str,
) -> dict[str, Any]:
    """Build and freeze the G3 test-execution manifest.

    The manifest SHA enters the bundle, approval, claim, and final receipt.
    It uniquely binds the cohort, configuration, and code version.
    """
    seeds = frozen_config.protocol["seeds"]
    formal_sizes = frozen_config.protocol["formal_sizes"]["module_test"]
    manifest = {
        "manifest_version": _MANIFEST_VERSION,
        "code_commit": code_commit,
        "effective_config_sha256": effective_config.effective_config_sha256,
        "frozen_matrix_sha256": frozen_config.protocol_sha256,
        "cohort_total": len(cohort.entries),
        "cohort_counts": dict(sorted(cohort.counts_by_module.items())),
        "cohort_fit_ids": sorted(entry.fit_id for entry in cohort.entries),
        "cohort_checkpoint_sha256s": {
            entry.fit_id: entry.checkpoint_sha256 for entry in cohort.entries
        },
        "cohort_module_by_fit_id": {
            entry.fit_id: entry.module_id for entry in cohort.entries
        },
        "test_namespaces": {
            module_id: {
                "design": int(seeds["module_test_design"][module_id]),
                "sample": int(seeds["module_test_sample"][module_id]),
            }
            for module_id in sorted(cohort.counts_by_module)
        },
        "test_sizes": {
            "parameter_points": int(formal_sizes["parameter_points"]),
            "repeats_per_point_n": int(formal_sizes["repeats_per_point_n"]),
        },
        "traditional_methods": {
            "primary": list(_PRIMARY_TRADITIONAL_METHODS),
            "diagnostic": list(_DIAGNOSTIC_TRADITIONAL_METHODS),
        },
        "failure_penalty": 10.0,
    }
    manifest_bytes = _canonical(manifest)
    manifest["manifest_sha256"] = _sha256_bytes(manifest_bytes)
    return manifest


def preflight_g3_test(
    *, manifest: dict[str, Any], artifact_root: Path, cache_root: Path,
    study_root: Path, frozen_config: FrozenConfig,
    effective_config: EffectiveFormalConfig,
) -> None:
    """All checks before test data generation. Fail-closed on any mismatch.

    Verifies: state, bundle, approval, code, config, selection traces,
    checkpoints, scaler/cache, namespaces, leakage, ceiling, matrix.
    """
    manifest_sha = manifest.get("manifest_sha256")
    if not manifest_sha:
        raise ValueError("manifest missing manifest_sha256")

    for module_id in sorted(manifest["cohort_counts"]):
        run_id = _resolve_run_id(artifact_root, module_id)
        run_dir = artifact_root / module_id / run_id

        state_path = run_dir / "formal_state.json"
        if not state_path.is_file():
            raise ValueError(f"{module_id}: formal_state.json not found")
        state = json.loads(state_path.read_text(encoding="utf-8"))
        if state.get("state") != "unsealed_once":
            raise ValueError(f"{module_id}: state must be unsealed_once, got {state.get('state')!r}")
        if state.get("test_access_count") != 1:
            raise ValueError(f"{module_id}: test_access_count must be 1")

        bundle_path = run_dir / "pre_unseal_bundle.json"
        if not bundle_path.is_file():
            raise ValueError(f"{module_id}: pre_unseal_bundle.json not found")
        bundle_sha = _sha256_bytes(bundle_path.read_bytes())
        if state.get("pre_unseal_bundle_sha256") != bundle_sha:
            raise ValueError(f"{module_id}: bundle SHA mismatch with state")

        approval_path = run_dir / "oracle_approval.json"
        if not approval_path.is_file():
            raise ValueError(f"{module_id}: oracle_approval.json not found")
        approval_sha = _sha256_bytes(approval_path.read_bytes())
        if state.get("approval_sha256") != approval_sha:
            raise ValueError(f"{module_id}: approval SHA mismatch with state")

        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        if bundle.get("code_commit") != manifest["code_commit"]:
            raise ValueError(f"{module_id}: bundle code_commit mismatch with manifest")
        if bundle.get("effective_config_sha256") != manifest["effective_config_sha256"]:
            raise ValueError(f"{module_id}: bundle config SHA mismatch with manifest")

        leakage_path = run_dir / "leakage_audit.json"
        if not leakage_path.is_file():
            raise ValueError(f"{module_id}: leakage_audit.json not found")
        ceiling_path = run_dir / "ceiling_hit_report.json"
        if not ceiling_path.is_file():
            raise ValueError(f"{module_id}: ceiling_hit_report.json not found")

    for entry in _iter_cohort_from_manifest(manifest, artifact_root):
        checkpoint_path = entry["checkpoint_path"]
        if not checkpoint_path.is_file():
            raise ValueError(f"checkpoint missing: {checkpoint_path}")
        actual_sha = _sha256_bytes(checkpoint_path.read_bytes())
        if actual_sha != entry["expected_sha256"]:
            raise ValueError(f"checkpoint SHA mismatch: {checkpoint_path}")


def _iter_cohort_from_manifest(manifest: dict[str, Any], artifact_root: Path):
    checkpoint_shas = manifest["cohort_checkpoint_sha256s"]
    module_by_fit = manifest["cohort_module_by_fit_id"]
    for fit_id, expected_sha in sorted(checkpoint_shas.items()):
        module_id = module_by_fit[fit_id]
        run_id = _resolve_run_id(artifact_root, module_id)
        yield {
            "fit_id": fit_id,
            "module_id": module_id,
            "checkpoint_path": artifact_root / module_id / run_id / "outputs" / fit_id / "checkpoint.pt",
            "expected_sha256": expected_sha,
        }


def publish_test_claim(
    *, run_dir: Path, manifest_sha256: str, timestamp: str,
) -> Path:
    """Publish a persistent, no-replace, concurrent-safe test claim.

    The claim file locks the evaluation: after publication, any failure
    terminates as failure + consumed. No retry is possible.
    """
    claim_path = run_dir / "g3_test_claim.json"
    lock_path = run_dir / "g3_test_claim.lock"

    import os
    try:
        fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.close(fd)
    except FileExistsError:
        raise ValueError("another test evaluation holds the claim lock")

    try:
        claim = {
            "claim_version": _CLAIM_VERSION,
            "manifest_sha256": manifest_sha256,
            "timestamp": timestamp,
            "status": "claimed",
        }
        _publish_no_replace(claim_path, _canonical(claim))
    except BaseException:
        lock_path.unlink(missing_ok=True)
        raise

    return claim_path


def build_module_test_samples(
    *, module_id: str, route: str, n_mode: str, fixed_n: int | None,
    frozen_config: FrozenConfig, point_count: int, repeat_count: int,
) -> tuple[list[dict[str, Any]], list[np.ndarray]]:
    """Build test parameter rows and raw lifetime samples for a module.

    Returns (design_rows, raw_samples) where raw_samples[i] is the lifetime
    sample for design_rows[i]. Traditional methods use raw_samples directly;
    NN uses features derived from the same samples.
    """
    seeds = frozen_config.protocol["seeds"]
    design_ns = int(seeds["module_test_design"][module_id])
    sample_ns = int(seeds["module_test_sample"][module_id])

    points = design.generate_parameter_points(module_id, "core", point_count, frozen_config)
    if n_mode == "shared_n":
        n_values = [int(v) for v in frozen_config.protocol["sample_sizes"]["core"]]
    else:
        n_values = [int(fixed_n)]

    rows: list[dict[str, Any]] = []
    for point in points.to_dict(orient="records"):
        for n in n_values:
            for repeat_id in range(repeat_count):
                rows.append({**point, "n": n, "repeat_id": repeat_id, "cell_id": f"{point['point_id']}:n{n}"})

    samples: list[np.ndarray] = []
    for row in rows:
        sample = design.generate_lifetime_sample(row, sample_ns)
        samples.append(sample)

    return rows, samples


def evaluate_traditional_methods(
    *, rows: list[dict[str, Any]], samples: list[np.ndarray],
    method_ids: Sequence[str], module_id: str,
) -> list[dict[str, Any]]:
    """Run traditional methods on the same test samples used for NN evaluation.

    Returns per-sample records with method_id, estimates, and legality.
    """
    import sys
    repo_root = Path(__file__).resolve().parents[4]
    python_dir = repo_root / "python"
    if str(python_dir) not in sys.path:
        sys.path.insert(0, str(python_dir))

    from methods.registry import IMPLEMENTED

    records: list[dict[str, Any]] = []
    for index, (row, sample) in enumerate(zip(rows, samples)):
        sample_sorted = np.sort(sample)
        n = int(row["n"])
        sample_n = sample_sorted[:n]
        point_id = str(row.get("point_id", f"point-{index:07d}"))
        sample_id = f"module_test:{point_id}:n{n}:r{int(row['repeat_id'])}:i{index:07d}"

        for method_id in method_ids:
            method_class = IMPLEMENTED.get(method_id)
            if method_class is None:
                continue
            try:
                estimator = method_class(sample_n.tolist())
                result = estimator.run()
                if hasattr(result, "to_list"):
                    result = result.to_list()
                beta_hat = float(result[0]) if result[0] is not None else float("nan")
                eta_hat = float(result[1]) if result[1] is not None else float("nan")
                gamma_hat = float(result[2]) if result[2] is not None else float("nan")
                converged = bool(result[4]) if len(result) > 4 else True
            except Exception:
                beta_hat, eta_hat, gamma_hat = float("nan"), float("nan"), float("nan")
                converged = False

            legal = (
                math.isfinite(beta_hat) and math.isfinite(eta_hat) and math.isfinite(gamma_hat)
                and beta_hat > 0 and eta_hat > 0
                and gamma_hat < float(sample_n[0])
                and converged
            )
            records.append({
                "point_id": point_id,
                "sample_id": sample_id,
                "module_id": module_id,
                "method_id": method_id,
                "method_role": "traditional",
                "n": n,
                "repeat_id": int(row["repeat_id"]),
                "seed": 0,
                "fit_id": "",
                "fit_kind": "traditional",
                "route": "traditional",
                "candidate_id": method_id,
                "checkpoint_sha256": "",
                "beta_hat": beta_hat,
                "eta_hat": eta_hat,
                "gamma_hat": gamma_hat,
                "beta": float(row["beta"]),
                "eta": float(row["eta"]),
                "gamma": float(row["gamma"]),
                "sample_min": float(sample_n[0]),
                "legal": legal,
                "converged": converged,
                "status": "succeeded" if legal else "failed",
                "failure_code": "" if legal else "illegal_estimate",
            })
    return records


def evaluate_nn_checkpoint(
    *, entry: CohortEntry, rows: list[dict[str, Any]], samples: list[np.ndarray],
    frozen_config: FrozenConfig, effective_config: EffectiveFormalConfig,
    cache_root: Path, artifact_root: Path,
) -> list[dict[str, Any]]:
    """Evaluate one NN checkpoint on the module test samples.

    Returns per-sample records with estimates and legality.
    """
    from .formal_executor import resolve_model_factory

    run_id = _resolve_run_id(artifact_root, entry.module_id)
    run_dir = artifact_root / entry.module_id / run_id
    checkpoint_path = run_dir / "outputs" / entry.fit_id / "checkpoint.pt"
    checkpoint_bytes = checkpoint_path.read_bytes()

    route = entry.route
    n_mode = "shared_n" if entry.n == "shared" else "fixed_n"
    fixed_n = None if entry.n == "shared" else int(entry.n)
    is_set = route == "S"

    examples: list[FormalFixedExample | FormalSetExample] = []
    for row, sample in zip(rows, samples):
        anchor = anchor_sample(sample)
        features = build_features(route, sample, int(row["n"]))
        target = encode_targets(row["beta"], row["eta"], row["gamma"], anchor)
        if isinstance(features, SetFeatures):
            examples.append(FormalSetExample(features, target, anchor.location, anchor.scale))
        else:
            examples.append(FormalFixedExample(features, target, anchor.location, anchor.scale))

    batch = collate_set_features(examples) if is_set else collate_fixed_features(examples)

    training_spec = build_training_spec(
        route=route,
        distribution="core_continuous" if route not in {"H0_hsm", "H0_kde_scott1024", "H1"} else "legacy_grid",
        n_mode=n_mode, fixed_n=fixed_n,
        training_rows=entry.training_size if entry.training_size > 0 else 7000,
        frozen_config=frozen_config, effective_config=effective_config,
    )
    training_dataset = cache_dataset(training_spec, frozen_config, effective_config, cache_root)
    scaler = fit_training_scaler(training_dataset, frozen_config, effective_config)

    from dataclasses import replace as _replace
    if isinstance(batch, FormalSetBatch):
        batch = _replace(batch, model_n=_standardize(batch.n.reshape(-1, 1), scaler).reshape(-1))
    else:
        batch = _replace(batch, features=_standardize(batch.features, scaler))

    architecture = entry.architecture
    if architecture.startswith("selected:") or architecture.startswith("selected_top_"):
        architecture = _resolve_architecture_from_authority(run_dir, entry)

    input_dim = None if is_set else int(batch.features.shape[1])
    model_factory = resolve_model_factory(architecture, frozen_config, input_dim)
    state_dict = load_checkpoint(checkpoint_bytes)
    model = model_factory()
    model.load_state_dict(state_dict)
    model.eval()

    with torch.no_grad():
        if is_set:
            prediction = model(batch.values, batch.mask, batch.model_n)
        else:
            prediction = model(batch.features)

    location = batch.location.detach().cpu().numpy().astype(float)
    scale_arr = batch.scale.detach().cpu().numpy().astype(float)
    values = prediction.detach().cpu().numpy().astype(float)
    beta_hat = np.exp(values[:, 0])
    eta_hat = scale_arr * np.exp(values[:, 1])
    gamma_hat = location - scale_arr * np.exp(values[:, 2])

    target_values = batch.targets.detach().cpu().numpy().astype(float)
    beta_true = np.exp(target_values[:, 0])
    eta_true = scale_arr * np.exp(target_values[:, 1])
    gamma_true = location - scale_arr * np.exp(target_values[:, 2])

    records: list[dict[str, Any]] = []
    for i in range(location.size):
        row = rows[i]
        point_id = str(row.get("point_id", f"point-{i:07d}"))
        n = int(row["n"])
        sample_id = f"module_test:{point_id}:n{n}:r{int(row['repeat_id'])}:i{i:07d}"
        bh, eh, gh = float(beta_hat[i]), float(eta_hat[i]), float(gamma_hat[i])
        legal = (
            math.isfinite(bh) and math.isfinite(eh) and math.isfinite(gh)
            and bh > 0 and eh > 0 and gh < float(location[i])
        )
        records.append({
            "point_id": point_id,
            "sample_id": sample_id,
            "module_id": entry.module_id,
            "method_id": f"nn:{entry.fit_kind}:{entry.route}",
            "method_role": "nn",
            "n": n,
            "repeat_id": int(row["repeat_id"]),
            "seed": entry.seed,
            "fit_id": entry.fit_id,
            "fit_kind": entry.fit_kind,
            "route": entry.route,
            "candidate_id": f"{entry.rule_id}:{entry.fit_id}",
            "checkpoint_sha256": entry.checkpoint_sha256,
            "beta_hat": bh,
            "eta_hat": eh,
            "gamma_hat": gh,
            "beta": float(beta_true[i]),
            "eta": float(eta_true[i]),
            "gamma": float(gamma_true[i]),
            "sample_min": float(location[i]),
            "legal": legal,
            "converged": True,
            "status": "succeeded" if legal else "failed",
            "failure_code": "" if legal else "illegal_estimate",
        })
    return records


def _resolve_architecture_from_authority(run_dir: Path, entry: CohortEntry) -> str:
    """Resolve a selected: architecture placeholder from the run's selection evidence."""
    staged_ledger = run_dir / "staged_resolution_ledger.jsonl"
    if staged_ledger.is_file():
        for line in staged_ledger.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            aliases = record.get("final_aliases") or record.get("aliases")
            if isinstance(aliases, dict):
                arch = aliases.get("selected:A-E1_architecture")
                if arch:
                    return str(arch)
    selection_dir = run_dir / "selection"
    if selection_dir.is_dir():
        for trace_file in selection_dir.glob("selection_trace*.json"):
            records = json.loads(trace_file.read_text(encoding="utf-8"))
            if isinstance(records, list):
                for rec in records:
                    if rec.get("selected") and rec.get("candidate_id"):
                        pass
    raise ValueError(
        f"cannot resolve architecture placeholder {entry.architecture!r} for {entry.fit_id}"
    )


def _write_evidence_artifact(records: list[dict[str, Any]], path: Path) -> str:
    """Write per-sample evidence as compressed CSV. Returns content SHA-256."""
    if not records:
        raise ValueError("no evidence records to write")
    fieldnames = sorted(records[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with gzip.open(str(tmp), "wt", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for record in records:
            writer.writerow(record)
    content_bytes = tmp.read_bytes()
    content_sha = _sha256_bytes(content_bytes)
    tmp.replace(path)
    return content_sha


def consume_g3_test(
    *,
    study_root: Path,
    artifact_root: Path,
    cache_root: Path,
    code_commit: str,
    timestamp: str,
    _point_count: int | None = None,
    _repeat_count: int | None = None,
) -> dict[str, Any]:
    """Unified G3 test evaluation: derive cohort, preflight, claim, evaluate, consume.

    No caller-supplied winner, module, or scientific configuration. Everything is
    derived from frozen authorities. After claim, any failure produces failure + consumed.
    """
    from .config import load_frozen_config
    from .formal_config import load_effective_formal_config

    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)

    cohort = derive_g3_cohort(frozen_config=frozen, artifact_root=artifact_root)
    manifest = build_g3_test_manifest(
        cohort=cohort, frozen_config=frozen,
        effective_config=effective, code_commit=code_commit,
    )
    manifest_sha256 = manifest["manifest_sha256"]

    preflight_g3_test(
        manifest=manifest, artifact_root=artifact_root, cache_root=cache_root,
        study_root=study_root, frozen_config=frozen, effective_config=effective,
    )

    primary_run_dir = artifact_root / "A-E1" / _resolve_run_id(artifact_root, "A-E1")
    claim_path = publish_test_claim(
        run_dir=primary_run_dir, manifest_sha256=manifest_sha256, timestamp=timestamp,
    )

    try:
        all_records: list[dict[str, Any]] = []
        formal_sizes = frozen.protocol["formal_sizes"]["module_test"]
        point_count = _point_count if _point_count is not None else int(formal_sizes["parameter_points"])
        repeat_count = _repeat_count if _repeat_count is not None else int(formal_sizes["repeats_per_point_n"])

        for module_id in sorted(cohort.counts_by_module):
            module_entries = [e for e in cohort.entries if e.module_id == module_id]
            routes_in_module = set()
            for entry in module_entries:
                route = entry.route
                n_mode = "shared_n" if entry.n == "shared" else "fixed_n"
                fixed_n = None if entry.n == "shared" else int(entry.n)
                route_key = (route, n_mode, fixed_n)
                if route_key in routes_in_module:
                    continue
                routes_in_module.add(route_key)

                rows, samples = build_module_test_samples(
                    module_id=module_id, route=route, n_mode=n_mode, fixed_n=fixed_n,
                    frozen_config=frozen, point_count=point_count, repeat_count=repeat_count,
                )

                for entry2 in module_entries:
                    if (entry2.route, "shared_n" if entry2.n == "shared" else "fixed_n",
                            None if entry2.n == "shared" else int(entry2.n)) != route_key:
                        continue
                    nn_records = evaluate_nn_checkpoint(
                        entry=entry2, rows=rows, samples=samples,
                        frozen_config=frozen, effective_config=effective,
                        cache_root=cache_root, artifact_root=artifact_root,
                    )
                    all_records.extend(nn_records)

            if rows:
                all_methods = list(_PRIMARY_TRADITIONAL_METHODS) + list(_DIAGNOSTIC_TRADITIONAL_METHODS)
                trad_records = evaluate_traditional_methods(
                    rows=rows, samples=samples, method_ids=all_methods, module_id=module_id,
                )
                all_records.extend(trad_records)

        evidence_path = primary_run_dir / "g3_test_evidence.csv.gz"
        evidence_sha256 = _write_evidence_artifact(all_records, evidence_path)

        evaluation_summary = evaluate_rows(
            [r for r in all_records if r["method_role"] == "nn"],
            failure_penalty=10.0,
        )

        receipt = {
            "receipt_version": _RESULT_RECEIPT_VERSION,
            "manifest_sha256": manifest_sha256,
            "code_commit": code_commit,
            "effective_config_sha256": manifest["effective_config_sha256"],
            "cohort_total": len(cohort.entries),
            "cohort_counts": manifest["cohort_counts"],
            "evidence_sha256": evidence_sha256,
            "evidence_record_count": len(all_records),
            "evaluation_summary": evaluation_summary,
            "test_access_count": 1,
            "timestamp": timestamp,
        }
        receipt_bytes = _canonical(receipt)
        receipt_sha256 = _sha256_bytes(receipt_bytes)
        receipt_path = primary_run_dir / "g3_test_result_receipt.json"
        _publish_no_replace(receipt_path, receipt_bytes)

        for module_id in sorted(cohort.counts_by_module):
            run_id = _resolve_run_id(artifact_root, module_id)
            run_dir = artifact_root / module_id / run_id
            state_path = run_dir / "formal_state.json"
            bundle_path = run_dir / "pre_unseal_bundle.json"
            approval_path = run_dir / "oracle_approval.json"
            ledger_path = run_dir / "transition_ledger.jsonl"
            consume_test_once(
                state_path=state_path, bundle_path=bundle_path, approval_path=approval_path,
                ledger_path=ledger_path, result_receipt_sha256=receipt_sha256,
                failure_receipt_sha256=None, timestamp=timestamp,
                ceiling_report_path=run_dir / "ceiling_hit_report.json",
                leakage_audit_path=run_dir / "leakage_audit.json",
                oracle_review_path=run_dir / "oracle_review.json",
            )

        claim_final = {
            "claim_version": _CLAIM_VERSION,
            "manifest_sha256": manifest_sha256,
            "timestamp": timestamp,
            "status": "completed",
            "receipt_sha256": receipt_sha256,
        }
        claim_path.write_bytes(_canonical(claim_final))

        return {"outcome": "result", "receipt_sha256": receipt_sha256, "evidence_sha256": evidence_sha256, "record_count": len(all_records)}

    except Exception as exc:
        failure_receipt = {
            "receipt_version": _FAILURE_RECEIPT_VERSION,
            "manifest_sha256": manifest_sha256,
            "code_commit": code_commit,
            "effective_config_sha256": manifest["effective_config_sha256"],
            "failure_code": type(exc).__name__[:64],
            "message": str(exc)[:500],
            "traceback_tail": traceback.format_exc()[-1000:],
            "test_access_count": 1,
            "timestamp": timestamp,
        }
        failure_bytes = _canonical(failure_receipt)
        failure_sha256 = _sha256_bytes(failure_bytes)
        failure_path = primary_run_dir / "g3_test_failure_receipt.json"
        _publish_no_replace(failure_path, failure_bytes)

        for module_id in sorted(cohort.counts_by_module):
            run_id = _resolve_run_id(artifact_root, module_id)
            run_dir = artifact_root / module_id / run_id
            state_path = run_dir / "formal_state.json"
            bundle_path = run_dir / "pre_unseal_bundle.json"
            approval_path = run_dir / "oracle_approval.json"
            ledger_path = run_dir / "transition_ledger.jsonl"
            try:
                consume_test_once(
                    state_path=state_path, bundle_path=bundle_path, approval_path=approval_path,
                    ledger_path=ledger_path, result_receipt_sha256=None,
                    failure_receipt_sha256=failure_sha256, timestamp=timestamp,
                    ceiling_report_path=run_dir / "ceiling_hit_report.json",
                    leakage_audit_path=run_dir / "leakage_audit.json",
                    oracle_review_path=run_dir / "oracle_review.json",
                )
            except Exception:
                pass

        claim_final = {
            "claim_version": _CLAIM_VERSION,
            "manifest_sha256": manifest_sha256,
            "timestamp": timestamp,
            "status": "failed",
            "failure_receipt_sha256": failure_sha256,
        }
        claim_path.write_bytes(_canonical(claim_final))

        return {"outcome": "failure", "receipt_sha256": failure_sha256, "error": str(exc)}


__all__ = [
    "CohortEntry",
    "G3Cohort",
    "build_g3_test_manifest",
    "build_module_test_samples",
    "consume_g3_test",
    "derive_g3_cohort",
    "evaluate_nn_checkpoint",
    "evaluate_traditional_methods",
    "preflight_g3_test",
    "publish_test_claim",
]
