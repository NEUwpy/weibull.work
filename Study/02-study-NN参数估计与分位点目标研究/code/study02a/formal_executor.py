"""Fail-closed execution driver for sealed Study/02 formal fits.

This module is the missing execution layer between the scheduler (which plans and
coordinates fits) and the training core (which trains a network). For one formal
module it loops:

    materialize_run -> claim_next_fit -> build/cache dataset -> fit training-only
    scaler -> train under the approved 100/50/40 contract -> write canonical
    checkpoint.pt + fit_status.json -> record_fit_succeeded / record_fit_failed.

Test data is never opened: every dataset role is training or validation, the
scaler is fit from training only, and ``test_access_count`` stays 0.

Scope note (relay 2026-07-15): single-fit execution, the A-E1 spec
reconstruction, the decision/candidate model (D6) and the resumable
``run_module`` loop are implemented here. Selection-trace generation (D7) and
the predecessor chain / deferred-spec reconstruction for A-E3/A-E2 (D8) are
deferred until the production run is launched; their public signatures are
declared below as fail-closed placeholders so callers cannot use them by
accident. See ``.superpowers/sdd/task-9c3-brief.md``.
"""

from __future__ import annotations

import hashlib
import math
import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import torch
from torch import nn

from .config import FrozenConfig, load_frozen_config
from .formal_config import EffectiveFormalConfig, load_effective_formal_config
from .formal_contracts import (
    APPROVED_EFFECTIVE_CONFIG_SHA256,
    SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT,
    SELECTION_RULE_GLOBAL_BETTER,
    _CODE_COMMIT_RE,
    _PREDECESSOR_BY_MODULE,
    _read_jsonl_bytes,
    _tie_break_sort_key,
    _validate_predecessor,
    _validate_selection_trace_bytes,
    build_pre_unseal_bundle,
    publish_selection_receipt,
    write_selection_trace,
    _publish_bytes_no_replace,
    _terminal_ols_slope,
    PredecessorTrace,
)
from .selection import (
    CandidateSpec,
    DecisionSpec,
    FitEvaluation,
    SupportKey,
    _equal_weight_per_n_aggregate,
    _validate_evaluation_finite,
    apply_selection_rule,
    build_decision_specs,
    build_selection_trace,
    candidate_supporting_evidence,
    serialize_point_evidence,
)
from .formal_data import FormalFixedBatch, FormalSetBatch  # noqa: F401  (type re-export)
from .artifacts import append_ledger
from .evaluation import evaluate_rows, evaluate_rows_per_sample
from .formal_runner import (
    FormalDataset,
    FormalDatasetSpec,
    apply_training_scaler,
    build_training_spec,
    build_validation_spec,
    cache_dataset,
    fit_training_scaler,
)
from .formal_scheduler import (
    _contained,
    _rebuild_authority,
    _reject_alias,
    claim_next_fit,
    materialize_run,
    record_fit_failed,
    record_fit_succeeded,
)
from .models import build_deepsets, build_mlp
from .matrix import expand_module_matrix
from .output_form_contract import (
    build_output_form_aware_factory,
    output_form_from_route,
)
from .training import fit_fixed_candidate, fit_set_candidate, load_checkpoint


_HISTORICAL_PREFIX = "historical_"
_MLP_PREFIX = "m"
_DEEP_PREFIX = "d"
_STAGE_TOP_PREFIX = "selected_top_"
_SELECTED_PREFIX = "selected:"

# Selection point-evidence (R3#1) lives under run_dir/selection/point_evidence/{fit_id}.json -- a
# selection-owned dir, NOT under outputs/{fit_id}/ (the scheduler-authority training-output dir, which
# must stay exactly equal to the frozen expected_outputs). Selection candidates are determined by the
# frozen matrix, but point evidence is a post-selection artifact: it cannot be a pre-training-success
# output, so it never belongs in the scheduler-validated fit output dir.
_SELECTION_POINT_EVIDENCE_REL = ("selection", "point_evidence")


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _require(cond: bool, message: str) -> None:
    if not cond:
        raise ValueError(message)


def _historical_widths(architecture_id: str, recipe: Mapping[str, Any]) -> tuple[int, ...]:
    raw = recipe.get("architecture")
    if isinstance(raw, dict) and isinstance(raw.get("widths"), Sequence):
        widths = tuple(int(value) for value in raw["widths"])
        if widths:
            return widths
    suffix = architecture_id[len(_HISTORICAL_PREFIX):]
    parts = suffix.split("_")
    widths = tuple(int(value) for value in parts if value.isdigit())
    _require(bool(widths), f"cannot resolve historical architecture widths: {architecture_id}")
    return widths


def resolve_model_factory(
    architecture_id: str, frozen: FrozenConfig, input_dim: int | None,
    *,
    output_form: str | None = None,
) -> Callable[[], nn.Module]:
    """Resolve a frozen architecture id to a deterministic model factory.

    ``selected:*`` and ``selected_top_N`` ids require a completed selection trace
    (D7/D8) and fail closed here.

    When ``output_form`` is set (an A-E3 ``output_form`` row's route suffix), the
    factory is routed through the SHA-bound :mod:`output_form_contract`:

    * ``"joint"`` / ``None`` -> the standard 3-output MLP (shared trunk).
    * ``"independent_capacity_matched"`` -> a capacity-selected
      :class:`~study02a.models.IndependentContainer` (three single-output MLP
      subnetworks), structurally distinct from the joint model so the two
      output_form arms are a contrastive control.

    The capacity selection (which m0X architecture the independent container is
    built from) is deterministic in ``(architecture_id, input_dim, frozen)``; the
    selection metadata is available via :func:`build_output_form_aware_factory` for
    evidence recording.
    """
    _require(isinstance(architecture_id, str) and architecture_id, "architecture id is required")
    if output_form is not None and output_form not in {"joint", "independent_capacity_matched"}:
        raise ValueError(f"unknown output_form value: {output_form!r}")
    if output_form == "independent_capacity_matched":
        _require(
            input_dim is not None and int(input_dim) > 0,
            "independent_capacity_matched requires a positive input_dim",
        )
        factory, _metadata = build_output_form_aware_factory(
            architecture_id, output_form, frozen, int(input_dim),
        )
        return factory
    if architecture_id.startswith(_SELECTED_PREFIX) or architecture_id.startswith(_STAGE_TOP_PREFIX):
        raise NotImplementedError(
            f"architecture {architecture_id!r} requires selection-trace resolution (D7/D8, deferred)"
        )
    if architecture_id.startswith(_HISTORICAL_PREFIX):
        recipe = frozen.search.get("historical_reconstruction_recipe", {})
        widths = _historical_widths(architecture_id, recipe)
        return lambda: build_mlp(input_dim or 0, widths, "relu", 0.0)
    if architecture_id.startswith(_MLP_PREFIX):
        entry = _find_by_id(frozen.search["mlp_stage1_architectures"], architecture_id, "mlp architecture")
        return lambda: build_mlp(
            input_dim or 0, tuple(int(value) for value in entry["widths"]), entry["activation"], float(entry["dropout"])
        )
    if architecture_id.startswith(_DEEP_PREFIX):
        entry = _find_by_id(frozen.search["deepsets_stage1_architectures"], architecture_id, "deepsets architecture")
        return lambda: build_deepsets(
            tuple(int(value) for value in entry["encoder"]), entry["pool"],
            tuple(int(value) for value in entry["head"]), entry["activation"],
        )
    raise ValueError(f"unknown frozen architecture id: {architecture_id!r}")


def resolve_optimizer_hyperparams(optimizer_id: str, frozen: FrozenConfig) -> dict[str, float | int | str]:
    """Resolve a frozen optimizer id to (optimizer, lr, weight_decay, batch_size)."""
    _require(isinstance(optimizer_id, str) and optimizer_id, "optimizer id is required")
    if optimizer_id.startswith(_SELECTED_PREFIX):
        raise NotImplementedError(
            f"optimizer {optimizer_id!r} requires selection-trace resolution (D7/D8, deferred)"
        )
    if optimizer_id == "stage1":
        entry = dict(frozen.search["stage1_optimizer"])
    elif optimizer_id == "adam_historical":
        recipe = frozen.search.get("historical_reconstruction_recipe", {})
        raw = recipe.get("optimizer", {})
        _require(isinstance(raw, dict) and raw, "historical recipe optimizer is missing")
        entry = {"optimizer": raw.get("id", "adam"), "lr": raw["lr"], "weight_decay": float(raw.get("weight_decay", 0.0)),
                 "batch_size": raw["batch_size"]}
    else:
        entry = _find_by_id(frozen.search["stage2_rule"]["optimizer_candidates"], optimizer_id, "optimizer candidate")
        entry = dict(entry)
    return {
        "optimizer": str(entry["optimizer"]),
        "lr": float(entry["lr"]),
        "weight_decay": float(entry.get("weight_decay", 0.0)),
        "batch_size": int(entry["batch_size"]),
    }


def resolve_loss_id(loss_id: str) -> str:
    """A concrete frozen loss id; ``selected:*`` fails closed (needs D7/D8)."""
    _require(isinstance(loss_id, str) and loss_id, "loss id is required")
    if loss_id.startswith(_SELECTED_PREFIX):
        raise NotImplementedError(f"loss {loss_id!r} requires selection-trace resolution (D7/D8, deferred)")
    return loss_id


def _find_by_id(items: Sequence[Mapping[str, Any]], identifier: str, label: str) -> Mapping[str, Any]:
    for item in items:
        if str(item.get("id")) == identifier:
            return item
    raise ValueError(f"unknown frozen {label} id: {identifier!r}")


def _decode_param_columns(raw: torch.Tensor, location: np.ndarray, scale: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Vectorized inverse of representations.encode_targets (identical formula to
    representations.decode_targets, kept vectorized for one-time selection cost).
    Round-trip equivalence is asserted by the selection unit tests.
    """
    values = raw.detach().cpu().numpy().astype(float)
    beta = np.exp(values[:, 0])
    eta = scale * np.exp(values[:, 1])
    gamma = location - scale * np.exp(values[:, 2])
    return beta, eta, gamma


def validation_failure_penalized_l_param(
    *, checkpoint_bytes: bytes,
    model_factory: Callable[[], nn.Module],
    validation_batch: FormalFixedBatch | FormalSetBatch,
    is_set: bool,
) -> float:
    """Mean failure-penalized ``L_param`` over the validation batch, derived by
    loading the integrity-bound checkpoint and running inference — never a sidecar.

    The model's raw output lives in the ``encode_targets`` (log-transform) space for
    every frozen loss (the loss-internal standardization is affine and does not move
    the output target), so the inverse transform recovers ``(/hat\\beta, /hat\\eta,
    /hat\\gamma)``. True params are recovered the same way from the bound targets.
    ``anchor.location`` is the sample minimum (``anchor_sample`` sorts and takes
    ``values[0]``), which is the legality bound ``\\hat\\gamma < \\min x``.
    ``evaluate_rows`` then applies the frozen failure penalty (10) to non-finite or
    illegal estimates and returns ``unconditional_mean_l_param`` — the frozen ranking
    metric ``mean_validation_failure_penalized_l_param_across_screening_seeds`` per
    (candidate, seed).
    """
    state = load_checkpoint(checkpoint_bytes)
    model = model_factory()
    model.load_state_dict(state)
    model.eval()
    with torch.no_grad():
        if is_set:
            prediction = model(validation_batch.values, validation_batch.mask, validation_batch.model_n)
        else:
            prediction = model(validation_batch.features)
    location = validation_batch.location.detach().cpu().numpy().astype(float)
    scale = validation_batch.scale.detach().cpu().numpy().astype(float)
    beta_hat, eta_hat, gamma_hat = _decode_param_columns(prediction, location, scale)
    beta_true, eta_true, gamma_true = _decode_param_columns(validation_batch.targets, location, scale)
    rows = [
        {
            "beta_hat": float(beta_hat[i]), "eta_hat": float(eta_hat[i]), "gamma_hat": float(gamma_hat[i]),
            "beta": float(beta_true[i]), "eta": float(eta_true[i]), "gamma": float(gamma_true[i]),
            "sample_min": float(location[i]),
        }
        for i in range(location.size)
    ]
    return float(evaluate_rows(rows, failure_penalty=10.0)["unconditional_mean_l_param"])


def validation_failure_penalized_l_param_points(
    *, checkpoint_bytes: bytes,
    model_factory: Callable[[], nn.Module],
    validation_batch: FormalFixedBatch | FormalSetBatch,
    validation_metadata: Sequence[Mapping[str, Any]],
    seed_id: str,
    is_set: bool,
) -> tuple[float, tuple[dict, ...]]:
    """Per-sample failure-penalized evidence derived from the integrity-bound checkpoint.

    Like :func:`validation_failure_penalized_l_param` but returns the per-sample
    records (stable pairing via ``sample_id``/``point_id`` from the validation
    cache metadata, plus the fit's ``seed_id``) that the CI rules cluster on, in
    addition to the scalar mean. The scalar equals the mean of the per-sample
    ``L_param`` values, matching the frozen ranking metric. This is the
    no-sidecar, checkpoint-bound per-parameter-point evaluation evidence the
    decision-rule engine consumes (R2: a scalar selection_score is insufficient
    to verify a CI).
    """
    if len(validation_metadata) != int(location_of_batch(validation_batch)):
        raise ValueError("validation metadata length must match the validation batch size")
    state = load_checkpoint(checkpoint_bytes)
    model = model_factory()
    model.load_state_dict(state)
    model.eval()
    with torch.no_grad():
        if is_set:
            prediction = model(validation_batch.values, validation_batch.mask, validation_batch.model_n)
        else:
            prediction = model(validation_batch.features)
    location = validation_batch.location.detach().cpu().numpy().astype(float)
    scale = validation_batch.scale.detach().cpu().numpy().astype(float)
    beta_hat, eta_hat, gamma_hat = _decode_param_columns(prediction, location, scale)
    beta_true, eta_true, gamma_true = _decode_param_columns(validation_batch.targets, location, scale)
    rows = [
        {
            "sample_id": str(validation_metadata[i].get("sample_id", f"val:{i:07d}")),
            "point_id": str(validation_metadata[i].get("point_id", f"point-{i:07d}")),
            "seed_id": str(seed_id),
            "beta_hat": float(beta_hat[i]), "eta_hat": float(eta_hat[i]), "gamma_hat": float(gamma_hat[i]),
            "beta": float(beta_true[i]), "eta": float(eta_true[i]), "gamma": float(gamma_true[i]),
            "sample_min": float(location[i]),
        }
        for i in range(location.size)
    ]
    records = tuple(evaluate_rows_per_sample(rows, failure_penalty=10.0))
    scalar = float(sum(record["l_param"] for record in records) / len(records)) if records else 10.0
    return scalar, records


def location_of_batch(batch: FormalFixedBatch | FormalSetBatch) -> int:
    return int(batch.location.shape[0])


def _is_selection_dependent(plan_row: Mapping[str, Any]) -> bool:
    """A fit whose architecture/optimizer/loss is a ``selected:`` / ``selected_top_`` placeholder.

    Such fits cannot be executed until a within-module selection (D7) resolves the
    placeholder from the concrete fits' bound checkpoints. ``run_module`` defers them.
    """
    for field in ("architecture", "optimizer", "loss"):
        value = str(plan_row[field])
        if value.startswith(_SELECTED_PREFIX) or value.startswith(_STAGE_TOP_PREFIX):
            return True
    return False


# D6: fit_kind -> (decision axis, candidate value extractor). Search fit_kinds compete;
# historical / controlled / *_retrain fits are singletons or deferred and return None.
_DECISION_AXIS_BY_FIT_KIND = {
    "search_stage1": "architecture",
    "search_stage2": "stage2",
    "loss_screen": "loss",
    "output_form": "output_form",
    "size_screen": "training_size",
    "distribution_screen": "distribution",
}


def _derive_decision_candidate(plan_row: Mapping[str, Any]) -> tuple[str, str, list] | None:
    """Map a plan row to ``(decision_id, candidate_id, tie_break_key)`` per the frozen
    module_matrix_rules (brief D6), or ``None`` if the row is not a competitive search
    candidate (historical/controlled/winner_retrain/selected_*_retrain).

    ``decision_id`` scopes exactly the candidates that compete on one axis
    (``{axis}:{module}:{route}:{n}``); ``candidate_id`` is the varying axis value;
    ``tie_break_key`` encodes the frozen tie-break (architecture_id_lexicographic etc.).
    A-E1 routes are concrete; A-E3/A-E2 routes are ``selected:*`` placeholders that all
    candidates of a decision share (resolved by D8 before execution).
    """
    kind = str(plan_row["fit_kind"])
    axis = _DECISION_AXIS_BY_FIT_KIND.get(kind)
    if axis is None:
        return None
    module = str(plan_row["module"])
    route = str(plan_row["route"])
    n = plan_row["n"]
    n_key = "shared" if n == "shared" else f"n{n}"
    decision_id = f"{axis}:{module}:{route}:{n_key}"
    if axis == "architecture":
        candidate = str(plan_row["architecture"])
        return decision_id, candidate, [candidate]
    if axis == "stage2":
        arch = str(plan_row["architecture"])  # selected_top_{slot}
        opt = str(plan_row["optimizer"])
        return decision_id, f"{arch}:{opt}", [arch, opt]
    if axis == "loss":
        candidate = str(plan_row["loss"])
        return decision_id, candidate, [candidate]
    if axis == "output_form":
        candidate = route.rsplit(":", 1)[-1] if ":" in route else route
        return decision_id, candidate, [candidate]
    if axis == "training_size":
        size = int(plan_row["training_size"])
        return decision_id, str(size), [size]  # smaller size wins ties (A-E2 smallest-within-2% spirit)
    if axis == "distribution":
        candidate = route.rsplit(":", 1)[-1] if ":" in route else str(plan_row.get("distribution", route))
        return decision_id, candidate, [candidate]
    return None


def reconstruct_a_e1_specs(
    plan_row: Mapping[str, Any], frozen: FrozenConfig, effective: EffectiveFormalConfig
) -> tuple[FormalDatasetSpec, FormalDatasetSpec]:
    """Rebuild the A-E1 training/validation specs exactly as the scheduler did.

    Asserts the reconstructed ``cache_key`` equals the plan row's bound key, so the
    executor and the scheduler agree byte-for-byte.
    """
    common = dict(
        route=str(plan_row["route"]),
        distribution=str(plan_row["distribution"]),
        n_mode=str(plan_row["n_mode"]),
        fixed_n=plan_row["fixed_n"],
        frozen_config=frozen,
        effective_config=effective,
    )
    training = build_training_spec(training_rows=int(plan_row["training_size"]), **common)
    validation_distribution = "legacy_grid" if (
        common["distribution"] == "legacy_grid" and common["route"].startswith(("H0_", "H1"))
    ) else "core_continuous"
    validation = build_validation_spec(
        distribution=validation_distribution, n_mode=common["n_mode"], fixed_n=common["fixed_n"],
        route=common["route"], frozen_config=frozen, effective_config=effective,
    )
    _require(
        training.cache_key == plan_row["training_cache_key"],
        "reconstructed training cache key drifts from the scheduler plan",
    )
    _require(
        validation.cache_key == plan_row["validation_cache_key"],
        "reconstructed validation cache key drifts from the scheduler plan",
    )
    return training, validation


def reconstruct_a_e3_specs(
    plan_row: Mapping[str, Any], frozen: FrozenConfig, effective: EffectiveFormalConfig,
    predecessor: Mapping[str, Any] | PredecessorTrace | None,
    resolved_route: str,
) -> tuple[FormalDatasetSpec, FormalDatasetSpec]:
    """Rebuild the A-E3 CONCRETE training/validation specs bound to a predecessor trace (D8 + A-E3).

    Mirrors :func:`reconstruct_a_e1_specs` for the deferred-spec module. Two-step provenance:

    1. Validate the predecessor (including the C1 staged-ledger binding) and the plan row's
       deferred cache keys via the EXISTING :func:`reconstruct_deferred_specs`, using the plan
       row PLACEHOLDER route literal (``selected:F2_or_V`` / ``S``). This asserts the deferred
       cache keys (computed at planning time with the placeholder route) match -- so the
       executor and the scheduler agree byte-for-byte on provenance, plan bytes unchanged.
    2. Build the CONCRETE :class:`FormalDatasetSpec` pair with the RESOLVED route stem
       (``V`` / ``S``) via the EXISTING :func:`build_training_spec` /
       :func:`build_validation_spec`. The concrete spec cache_key (route=V/S based) WILL differ
       from the plan row deferred cache_key -- this is correct: the deferred key was validated
       in step 1 (provenance binding); :func:`cache_dataset` caches under the concrete key, so
       the A-E3 V-route dataset transparently reuses the A-E1 V cache entry.

    The caller supplies ``resolved_route`` (the predecessor-derived route stem, V or S).
    Output_form suffixes are stripped for the dataset spec (Flag K.1: the suffix affects only
    the model head, not the dataset bytes).
    """
    # Step 1: predecessor + deferred cache-key binding (placeholder route, plan bytes unchanged).
    reconstruct_deferred_specs(plan_row, frozen, effective, predecessor)
    # Step 2: build CONCRETE specs with the resolved route stem.
    common = dict(
        route=str(resolved_route),
        distribution=str(plan_row["distribution"]),
        n_mode=str(plan_row["n_mode"]),
        fixed_n=plan_row["fixed_n"],
        frozen_config=frozen,
        effective_config=effective,
    )
    training = build_training_spec(training_rows=int(plan_row["training_size"]), **common)
    validation_distribution = "legacy_grid" if (
        common["distribution"] == "legacy_grid" and common["route"].startswith(("H0_", "H1"))
    ) else "core_continuous"
    validation = build_validation_spec(
        distribution=validation_distribution, n_mode=common["n_mode"], fixed_n=common["fixed_n"],
        route=common["route"], frozen_config=frozen, effective_config=effective,
    )
    return training, validation


def _predecessor_trace_from_manifest(run_dir: Path) -> PredecessorTrace:
    """Build a :class:`PredecessorTrace` from the run's manifest predecessor section.

    The manifest's ``predecessor`` section was produced by :func:`_validate_predecessor` at
    materialize time (paths + SHAs all verified). The predecessor's ``selection_code_commit``
    is NOT persisted in the downstream manifest (only its SHA-bound artifacts are); it is read
    from the predecessor's own manifest at ``selection_trace_path.parent / manifest.json``.
    Staged-ledger fields use the sentinel ``"none"`` when the predecessor module does not
    publish a staged ledger (none in the A-E1 -> A-E3 chain); the mapping restores ``None``.
    """
    manifest = json.loads((Path(run_dir) / "manifest.json").read_text(encoding="utf-8"))
    predecessor = manifest["predecessor"]
    pred_manifest_path = Path(predecessor["selection_trace_path"]).parent / "manifest.json"
    pred_manifest = json.loads(pred_manifest_path.read_text(encoding="utf-8"))
    staged_path = predecessor.get("selection_staged_ledger_path")
    staged_sha = predecessor.get("selection_staged_ledger_sha256")
    scoped_code = predecessor.get("scoped_code_sha256")
    authority_sha = predecessor.get("authority_sha256")
    if manifest.get("manifest_version") == "study02-formal-v2" and str(predecessor.get("module_id")) != "none":
        if scoped_code in (None, "none"):
            raise ValueError("v2 manifest predecessor missing scoped_code_sha256 for non-none predecessor")
        if authority_sha in (None, "none"):
            raise ValueError("v2 manifest predecessor missing authority_sha256 for non-none predecessor")
    return PredecessorTrace(
        module_id=str(predecessor["module_id"]),
        run_id=str(predecessor["run_id"]),
        trace_path=Path(predecessor["selection_trace_path"]),
        trace_sha256=str(predecessor["selection_trace_sha256"]),
        receipt_path=Path(predecessor["selection_receipt_path"]),
        receipt_sha256=str(predecessor["selection_receipt_sha256"]),
        ledger_path=Path(predecessor["selection_ledger_path"]),
        selection_code_commit=str(pred_manifest["code_commit"]),
        staged_ledger_path=None if staged_path in (None, "none") else Path(staged_path),
        staged_ledger_sha256=None if staged_sha in (None, "none") else str(staged_sha),
        scoped_code_sha256=None if scoped_code in (None, "none") else str(scoped_code),
        authority_sha256=None if authority_sha in (None, "none") else str(authority_sha),
    )


def _a_e3_resolved_baseline_route_from_manifest(run_dir: Path) -> str:
    """Read ``predecessor.resolved_baseline_route`` from the run manifest (C1 binding).

    This is the verified resolution of ``selected:F2_or_V`` from the A-E1 predecessor's
    staged_resolution_ledger (``V`` for the r5 outcome the design freezes). It is read ONCE
    per scoring pass / materialize and threaded into every A-E3 fit's route resolution.
    """
    manifest = json.loads((Path(run_dir) / "manifest.json").read_text(encoding="utf-8"))
    route = manifest["predecessor"]["resolved_baseline_route"]
    _require(
        isinstance(route, str) and route in {"F2", "V"},
        f"manifest predecessor resolved_baseline_route must be 'F2' or 'V' (got {route!r})")
    return route


def _read_plan_row_by_fit_id(run_dir: Path, fit_id: str) -> Mapping[str, Any]:
    """Read one plan row from ``plan.jsonl`` by ``fit_id`` (fail-closed on missing).

    The staged executor resolves a plan row (concrete route / architecture / optimizer / loss)
    before passing it to the runner; the ORIGINAL placeholder-route row is needed to validate
    the deferred dataset cache keys (which were computed at planning time with the placeholder).
    This reads that original row from the authoritative plan file.
    """
    plan_path = Path(run_dir) / "plan.jsonl"
    for line in plan_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if str(row["fit_id"]) == str(fit_id):
            return row
    raise ValueError(f"fit_id {fit_id!r} not found in {plan_path}")


def _write_outputs(
    run_dir: Path,
    fit_id: str,
    run_id: str,
    checkpoint_bytes: bytes,
    checkpoint_sha256: str,
    evidence: Mapping[str, Any],
) -> dict[str, str]:
    """Write the three scheduler-required per-fit outputs atomically to a staging dir.

    All three (checkpoint.pt, fit_status.json, evidence.json) are staged under a
    process-private temp dir and ``os.replace``-d into ``outputs/{fit_id}/`` together,
    so a crash leaves either nothing or the complete bound triple — never a partial
    set that the scheduler's success validation would reject on recovery. The
    selection signal itself is never stored here: evidence holds only the
    non-recomputable training trajectory; validation loss / L_param are derived by
    selection (D7) from the integrity-bound checkpoint.
    """
    output_dir = run_dir / "outputs" / fit_id
    _require(not output_dir.exists(), f"fit output directory already exists: {output_dir}")
    fit_status_binding = {
        "checkpoint_sha256": checkpoint_sha256, "fit_id": fit_id, "run_id": run_id,
        "status": "succeeded", "test_access_count": 0,
    }
    status_bytes = _canonical(fit_status_binding)
    evidence_bytes = _canonical(evidence)
    staging = output_dir.parent / f".{fit_id}.{os.getpid()}.staging"
    staging.mkdir(parents=True, exist_ok=False)
    try:
        (staging / "checkpoint.pt").write_bytes(checkpoint_bytes)
        (staging / "fit_status.json").write_bytes(status_bytes)
        (staging / "evidence.json").write_bytes(evidence_bytes)
        os.replace(staging, output_dir)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {
        f"outputs/{fit_id}/checkpoint.pt": hashlib.sha256(checkpoint_bytes).hexdigest(),
        f"outputs/{fit_id}/fit_status.json": hashlib.sha256(status_bytes).hexdigest(),
        f"outputs/{fit_id}/evidence.json": hashlib.sha256(evidence_bytes).hexdigest(),
    }


@dataclass(frozen=True)
class _PreparedFit:
    """Shared, single-source-of-truth fit inputs (training + validation + model).

    Both single-fit execution and D7 selection scoring prepare the validation
    batch through this path so the L_param is computed on the exact scaled
    validation set the fit trained against — no drift between training and
    selection. ``validation_metadata`` carries the per-row stable pairing ids
    (sample_id / point_id) the CI rules cluster on. ``output_form_evidence`` carries
    the A-E3 output-form capacity-selection metadata (joint/independent architecture
    ids, exact parameter counts, capacity selection) for independent unit verification;
    it is NOT written to fit evidence v1 (scheduler schema is frozen). ``None`` for
    non-output-form fits.
    """

    scaled_training: FormalDataset
    scaled_validation: FormalDataset
    validation_metadata: tuple[Mapping[str, Any], ...]
    validation_identity: str
    model_factory: Callable[[], nn.Module]
    hyperparams: Mapping[str, Any]
    loss_id: str
    is_set: bool
    output_form_evidence: Mapping[str, Any] | None = None


def _prepare_fit_inputs(
    plan_row: Mapping[str, Any], frozen: FrozenConfig,
    effective: EffectiveFormalConfig, cache_root: Path,
    run_dir: Path | None = None,
) -> _PreparedFit:
    """Build the cached datasets, training-only scaler, resolved model and hyperparams.

    Reconstructs the module's training/validation specs exactly as the scheduler did
    (so executor and scheduler agree byte-for-byte) and applies the training-only
    scaler. Dispatches on ``plan_row["module_id"]``: A-E1 rebuilds the concrete specs
    directly; A-E3 rebuilds the deferred specs (placeholder route, validated against the
    plan row's deferred cache key via :func:`reconstruct_a_e3_specs`) and then builds the
    CONCRETE specs with the predecessor-resolved route (V or S), reading the original
    placeholder-route plan row + the predecessor binding from the run manifest.
    ``validation_identity`` (the validation dataset hash) binds which validation cache the
    per-point evidence was scored on (R3#1).
    """
    module_id = str(plan_row["module_id"])
    if module_id == "A-E1":
        training_spec, validation_spec = reconstruct_a_e1_specs(plan_row, frozen, effective)
    elif module_id == "A-E3":
        _require(run_dir is not None,
                 "A-E3 _prepare_fit_inputs requires run_dir (to read the manifest predecessor binding)")
        original_row = _read_plan_row_by_fit_id(run_dir, str(plan_row["fit_id"]))
        predecessor = _predecessor_trace_from_manifest(run_dir)
        resolved_baseline_route = _a_e3_resolved_baseline_route_from_manifest(run_dir)
        resolved_route_stem = _a_e3_resolved_route_stem(
            str(original_row["route"]), resolved_baseline_route)
        training_spec, validation_spec = reconstruct_a_e3_specs(
            original_row, frozen, effective, predecessor, resolved_route_stem)
    else:
        raise NotImplementedError(
            f"_prepare_fit_inputs does not support module {module_id!r} (only A-E1 and A-E3)")
    training_dataset = cache_dataset(training_spec, frozen, effective, cache_root)
    validation_dataset = cache_dataset(validation_spec, frozen, effective, cache_root)
    scaler = fit_training_scaler(training_dataset, frozen, effective)
    scaled_training = apply_training_scaler(training_dataset, scaler, training_dataset, frozen, effective)
    scaled_validation = apply_training_scaler(validation_dataset, scaler, training_dataset, frozen, effective)
    is_set = str(plan_row["route"]) == "S"
    input_dim = None if is_set else int(scaled_training.batch.features.shape[1])
    output_form = output_form_from_route(str(plan_row["route"]))
    if output_form is None:
        # No output_form suffix -> the standard architecture resolver (MLP, DeepSets,
        # historical, etc.). The output_form contract is not engaged.
        model_factory = resolve_model_factory(str(plan_row["architecture"]), frozen, input_dim)
        output_form_evidence = None
    else:
        # output_form suffix present (joint/independent_capacity_matched) -> route
        # through the SHA-bound output_form contract. The architecture is always an
        # m-prefix MLP id for output_form fits (F2_or_V route), so the contract
        # module's MLP-only lookup is correct here.
        model_factory, output_form_evidence = build_output_form_aware_factory(
            str(plan_row["architecture"]), output_form, frozen, int(input_dim),
        )
    hyperparams = resolve_optimizer_hyperparams(str(plan_row["optimizer"]), frozen)
    loss_id = resolve_loss_id(str(plan_row["loss"]))
    return _PreparedFit(
        scaled_training, scaled_validation, tuple(validation_dataset.metadata),
        validation_dataset.dataset_hash, model_factory, hyperparams, loss_id, is_set,
        output_form_evidence=output_form_evidence,
    )


def execute_claimed_fit(
    *,
    study_root: Path,
    run_dir: Path,
    cache_root: Path,
    plan_row: Mapping[str, Any],
    claim: Mapping[str, Any],
    frozen: FrozenConfig,
    effective: EffectiveFormalConfig,
    timestamp: str,
) -> dict[str, Any]:
    """Train one claimed fit and record its terminal state through the scheduler.

    Returns ``{"state": "succeeded"|"failed", "receipt": ...}``. Only the training
    call itself is a per-fit *scientific* failure (recorded as a failed terminal);
    dataset/cache/scaler/write/record errors are infrastructure failures and
    propagate so the run aborts and can be retried, never misrecorded as a
    scientific failure. No outputs are written before a successful fit, so a
    scientific failure records cleanly; an infra crash after writing is recovered
    by the scheduler cleaning the orphaned outputs of a confirmed-dead claim.
    """
    fit_id = str(claim["fit_id"])
    owner_id = str(claim["owner_id"])
    owner_nonce = str(claim["owner_nonce"])

    # Infrastructure: data + scaler + resolved model/hyperparams (errors propagate).
    prepared = _prepare_fit_inputs(plan_row, frozen, effective, cache_root, run_dir=run_dir)
    scaled_training = prepared.scaled_training
    scaled_validation = prepared.scaled_validation
    model_factory = prepared.model_factory
    hyperparams = prepared.hyperparams
    loss_id = prepared.loss_id
    is_set = prepared.is_set

    # Scientific: the fit itself. Only this is a retryable-as-failed scientific outcome.
    try:
        if is_set:
            fit = fit_set_candidate(
                model_factory, scaled_training.batch, scaled_validation.batch, effective,
                seed=int(plan_row["seed"]), loss_id=loss_id, lr=hyperparams["lr"],
                weight_decay=hyperparams["weight_decay"], batch_size=hyperparams["batch_size"],
                optimizer_id=str(hyperparams["optimizer"]),
            )
        else:
            fit = fit_fixed_candidate(
                model_factory, scaled_training.batch, scaled_validation.batch, effective,
                seed=int(plan_row["seed"]), loss_id=loss_id, lr=hyperparams["lr"],
                weight_decay=hyperparams["weight_decay"], batch_size=hyperparams["batch_size"],
                optimizer_id=str(hyperparams["optimizer"]),
            )
    except (RuntimeError, ValueError) as science_error:
        return {
            "state": "failed",
            "failure_code": f"{type(science_error).__name__}",
            "message": str(science_error)[:200],
            "receipt": record_fit_failed(
                run_dir, cache_root=cache_root, fit_id=fit_id, owner_id=owner_id, owner_nonce=owner_nonce,
                failure_code=f"{type(science_error).__name__}"[:64], timestamp=timestamp,
            ),
        }

    _require(
        hashlib.sha256(fit.checkpoint_bytes).hexdigest() == fit.checkpoint_sha256,
        "canonical checkpoint bytes do not hash to the recorded checkpoint_sha256",
    )
    curve = [float(value) for value in fit.validation_loss_history]
    evidence = {
        "evidence_version": "study02-formal-fit-evidence-v1",
        "fit_id": fit_id, "run_id": str(plan_row["run_id"]),
        "checkpoint_sha256": fit.checkpoint_sha256,
        "actual_epochs": int(fit.actual_epochs),
        "best_epoch_one_based": int(fit.best_epoch) + 1,
        "hit_epoch_100": bool(fit.hit_epoch_ceiling),
        "early_stop_reason": str(fit.early_stop_reason),
        "terminal_validation_slope": _terminal_ols_slope(curve),
        "validation_curve": curve,
        "test_access_count": 0,
    }
    # output_form metadata is a deterministic derivative of plan/matrix + frozen
    # contract SHA + input_dim + checkpoint. Do NOT write it to evidence.json:
    # scheduler _EVIDENCE_FIELDS is frozen (rejects extra fields). Contract SHA
    # + factory + capacity derivation remain independently unit-verified.
    output_hashes = _write_outputs(
        run_dir, fit_id, str(plan_row["run_id"]), fit.checkpoint_bytes, fit.checkpoint_sha256, evidence,
    )
    return {
        "state": "succeeded",
        "receipt": record_fit_succeeded(
            run_dir, cache_root=cache_root, fit_id=fit_id, owner_id=owner_id, owner_nonce=owner_nonce,
            output_hashes=output_hashes, timestamp=timestamp,
        ),
    }


def _advance_consecutive_failures(count: int, failure_code: str, message: str, *, max_failures: int = 8, label: str = "formal execution") -> int:
    count += 1
    if count >= max_failures:
        raise RuntimeError(f"{label} aborted: {max_failures} consecutive scientific failures (last: {failure_code}: {message})")
    return count


def run_module(
    *,
    study_root: Path,
    module_id: str,
    run_id: str,
    artifact_root: Path,
    cache_root: Path,
    owner_id: str = "formal-executor",
    max_fits: int | None = None,
    predecessor: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Drive one formal module end-to-end (materialize if needed, then claim/execute/record).

    Executes the **concrete** fits of the module (those whose architecture/optimizer/loss
    are fully resolved). When the next pending fit depends on a within-module selection
    (``selected_top_*`` / ``selected:*`` placeholders), it STOPS cleanly with
    ``selection_required`` rather than claiming and failing it — selection itself is a
    separate operation (D7) that resolves placeholders from the concrete fits' bound
    checkpoints. This is why A-E1 is not "fully executable" in one pass: its stage-2
    and winner-retrain fits require the stage-1 selection to have run first.

    Each concrete fit is one claim->record transaction guarded by the scheduler journal.
    Infrastructure errors (data/cache/scaler/write/record) propagate so the run aborts and
    can be retried; only training/numerical failures are recorded as per-fit scientific
    failures. A-E3/A-E2 require a predecessor (D8, deferred) and fail closed here.
    """
    study_root = Path(study_root)
    if module_id != "A-E1":
        raise NotImplementedError(
            f"execution of module {module_id!r} requires predecessor wiring (D8, deferred); "
            "only A-E1 is executable in this relay"
        )
    study_root = Path(study_root).resolve()
    artifact_root = Path(artifact_root).resolve()
    cache_root = Path(cache_root).resolve()
    matrix_path = (study_root / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv").resolve()
    materialize_run(
        study_root=study_root, matrix_path=matrix_path, module_id=module_id, run_id=run_id,
        artifact_root=artifact_root, cache_root=cache_root, predecessor=predecessor,
    )
    run_dir = artifact_root / module_id / run_id
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)

    plan_rows = [
        json.loads(line)
        for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    plan_order = [row["fit_id"] for row in plan_rows]
    by_fit = {row["fit_id"]: row for row in plan_rows}

    succeeded: list[str] = []
    failed: list[dict[str, str]] = []
    selection_required: list[str] = []
    consecutive_failures = 0
    while max_fits is None or len(succeeded) < int(max_fits):
        # Peek the next pending fit WITHOUT claiming, so a selection-dependent fit is
        # deferred cleanly instead of being claimed and then failed.
        state = _rebuild_authority(run_dir, cache_root)[2]
        pending = [fid for fid in plan_order if state["fit_states"].get(fid) == "pending"]
        if not pending:
            break  # plan exhausted
        next_fit = pending[0]
        if _is_selection_dependent(by_fit[next_fit]):
            selection_required.append(next_fit)
            break  # defer to D7 selection
        timestamp = _utc_now()
        claim = claim_next_fit(
            run_dir, cache_root=cache_root, owner_id=owner_id,
            owner_nonce=hashlib.sha256(f"{owner_id}:{timestamp}".encode("utf-8")).hexdigest()[:32],
            timestamp=timestamp,
        )
        if claim["status"] == "exhausted":
            break
        if claim["status"] != "claimed":
            break  # monitor_only: another live owner; let the caller retry
        result = execute_claimed_fit(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root,
            plan_row=by_fit[claim["fit_id"]], claim=claim, frozen=frozen, effective=effective,
            timestamp=timestamp,
        )
        if result["state"] == "succeeded":
            succeeded.append(claim["fit_id"])
            consecutive_failures = 0
        else:
            failed.append({"fit_id": claim["fit_id"], "failure_code": result["failure_code"], "message": result["message"]})
            consecutive_failures = _advance_consecutive_failures(consecutive_failures, result["failure_code"], result["message"])

    return {
        "module_id": module_id, "run_id": run_id, "run_dir": str(run_dir),
        "succeeded": succeeded, "failed": failed, "selection_required": selection_required,
        "succeeded_count": len(succeeded), "failed_count": len(failed),
        "selection_required_count": len(selection_required),
    }


# ---------------------------------------------------------------------------
# Deferred until the production run is launched (D7 selection / D8 predecessor).
# Signatures declared so callers fail closed instead of silently no-op'ing.
# ---------------------------------------------------------------------------


def _validate_selection_point_evidence_dir(
    *, run_dir: Path, expected_fit_ids: set[str]
) -> dict[str, Path]:
    """Validate ``run_dir/selection/point_evidence/`` holds exactly one ``{fit_id}.json`` per
    expected selection candidate.

    The selection point-evidence dir is a post-selection, selection-owned artifact store
    (NOT under the scheduler-authority ``outputs/{fit_id}/``). It must contain exactly the
    expected candidate set -- ``missing``/``extra``/``duplicate``/``alias``/``non-file``/
    ``nested``/``unknown fit`` all fail closed. Returns ``{fit_id: path}`` for the exact set.

    Alias-chain: the directory AND every parent (``run_dir/selection``, ``run_dir``) must be
    real -- no symlink/junction/reparse/hardlink -- and the resolved path must stay within
    ``run_dir``. Reuses the scheduler's ``_reject_alias`` (path + parents) and ``_contained``
    (no new framework); per-entry checks mirror the scheduler's
    ``os.scandir`` + ``is_file(follow_symlinks=False)`` + ``_reject_alias(..., require_file=True)``.
    """
    relative = Path(*_SELECTION_POINT_EVIDENCE_REL)
    directory = _contained(run_dir, str(relative))  # resolved path stays within run_dir (no traversal escape)
    if not directory.is_dir():
        raise ValueError(f"selection point-evidence directory is missing: {directory}")
    _reject_alias(directory)  # dir + all parents (run_dir/selection, run_dir) reject symlink/junction/reparse/hardlink
    by_fit: dict[str, Path] = {}
    for entry in sorted(os.scandir(directory), key=lambda e: e.name):
        if not entry.is_file(follow_symlinks=False):  # reject non-file/nested/broken-symlink before the alias check
            raise ValueError(f"selection point-evidence dir contains a non-file/nested entry: {entry.name}")
        path = _reject_alias(Path(entry.path), require_file=True)  # plain file, no symlink/reparse/hardlink (nlink==1)
        if path.suffix != ".json":
            raise ValueError(f"selection point-evidence dir contains a non-json entry: {path.name}")
        fit_id = path.stem
        if fit_id in by_fit:
            raise ValueError(f"duplicate selection point-evidence fit_id: {fit_id}")
        if fit_id not in expected_fit_ids:
            raise ValueError(f"selection point-evidence dir contains an unknown fit_id: {fit_id}")
        by_fit[fit_id] = path
    missing = sorted(set(expected_fit_ids) - set(by_fit))
    if missing:
        raise ValueError(f"selection point-evidence directory is missing fits: {missing}")
    return by_fit


def build_module_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path, module_id: str, run_id: str,
    score_fit: Callable[[str, Mapping[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    """Build the v2 selection trace/receipt/ledger for a completed module (D7).

    Derives the module's DecisionSpecs deterministically from the frozen plan, scores
    each expected supporting fit's integrity-bound checkpoint (mean failure-penalized
    validation ``L_param`` + per-parameter-point evidence, no sidecar), and publishes
    one immutable selection trace + receipt whose winner each rule COMPUTES (never a
    caller-supplied winner). ``score_fit(fit_id, plan_row)`` may be supplied to inject
    bound :class:`~study02a.selection.FitEvaluation` evidence (used by tests); by default
    each succeeded fit is scored from ``outputs/{fit_id}/checkpoint.pt`` and each failed
    fit carries the frozen penalty.

    Scope (relay 2026-07-18): the engine path -- derive specs, score, aggregate, apply
    the rule, emit trace + receipt for the module's concrete screening decisions in one
    pass. The staged A-E1 execution (stage1 -> selected_top -> stage2 -> baseline_input,
    interleaved with execution) and D8 (placeholder resolution / deferred-spec / A-E3<-A-E1
    / A-E2<-A-E3 predecessor wiring) remain fail-closed in ``resolve_selected_placeholders``
    / ``reconstruct_deferred_specs``. No receipt is published before every decision's rule
    has been applied and verified (``build_selection_trace`` raises on any inconsistent or
    incomplete evidence before records are written).
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    specs, evaluations_by_fit = _derive_and_score_evaluations(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, module_id=module_id,
        run_id=run_id, frozen=frozen, effective=effective, score_fit=score_fit,
    )
    if not specs:
        raise ValueError(f"build_module_selection derived no selection decisions for module {module_id!r}")

    records, diagnostics_records = build_selection_trace(
        module_id=module_id, run_id=run_id, specs=specs, evaluations_by_fit=evaluations_by_fit,
    )
    trace_path = run_dir / "selection_trace.jsonl"
    trace_sha = write_selection_trace(trace_path, records)
    # R3#1/#2: publish the per-decision diagnostics artifact and the per-fit point-evidence
    # artifacts (canonical, no-replace). The trace binds the diagnostics SHA; the supporting
    # hash binds each fit's point-evidence SHA. Pre-unseal reloads + re-derives from these.
    diagnostics_path = run_dir / "selection_diagnostics.jsonl"
    diagnostics_payload = b"".join(_canonical(record) for record in diagnostics_records)
    _publish_bytes_no_replace(diagnostics_payload, diagnostics_path)
    # R3#1/#2: publish the per-decision diagnostics artifact and the per-fit point-evidence
    # artifacts (canonical, no-replace). The point-evidence artifacts live in the selection-owned
    # run_dir/selection/point_evidence/{fit_id}.json dir -- NOT under outputs/{fit_id}/, which must
    # stay exactly equal to the frozen expected_outputs (the scheduler's authority invariant). The
    # trace binds the diagnostics SHA; the supporting hash binds each fit's point-evidence SHA.
    # Pre-unseal reloads + re-derives from these. _publish_bytes_no_replace creates the parent dir.
    point_evidence_dir = run_dir.joinpath(*_SELECTION_POINT_EVIDENCE_REL)
    point_evidence_paths: dict[str, str] = {}
    for fit_id, evaluation in evaluations_by_fit.items():
        artifact_path = point_evidence_dir / f"{fit_id}.json"
        _publish_bytes_no_replace(_canonical(serialize_point_evidence(evaluation)), artifact_path)
        point_evidence_paths[fit_id] = str(artifact_path)
    # fail-closed: the selection point-evidence dir holds exactly the expected candidates (no
    # missing/extra/duplicate/alias/non-file/nested/unknown fit).
    _validate_selection_point_evidence_dir(run_dir=run_dir, expected_fit_ids=set(evaluations_by_fit))
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    receipt = publish_selection_receipt(
        receipt_path=run_dir / "selection_receipt.json",
        ledger_path=run_dir / "selection_ledger.jsonl",
        module_id=module_id, run_id=run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=effective, code_commit=manifest["code_commit"],
    )
    return {
        "module_id": module_id, "run_id": run_id, "selection_trace_sha256": trace_sha,
        "decision_count": len(specs), "record_count": len(records),
        "selection_diagnostics_path": str(diagnostics_path),
        "point_evidence_paths": point_evidence_paths, **receipt,
    }


def _n_key_of(row: Mapping[str, Any]) -> int | str:
    """Recover the SupportKey ``n`` from a plan row (``n_mode``/``fixed_n``) or matrix row (``n``)."""
    if row.get("n_mode") == "shared_n" or row.get("n") == "shared":
        return "shared"
    if row.get("fixed_n") is not None:
        return int(row["fixed_n"])
    return int(row["n"])


def _require_finite_evaluation(fit_id: str, scalar: float, point_records: tuple) -> None:
    """R6 fail-closed: selection_score and all point numerics must be finite before aggregation."""
    if not math.isfinite(scalar):
        raise ValueError(f"fit {fit_id!r} selection_score is non-finite ({scalar})")
    for record in point_records:
        for field in ("l_param", "e_beta", "e_eta", "e_gamma"):
            value = record[field]
            if not math.isfinite(value):
                raise ValueError(
                    f"fit {fit_id!r} point record {record.get('sample_id', '?')} "
                    f"has non-finite {field} ({value})"
                )


def _score_fit_from_checkpoint(
    *, run_dir: Path, cache_root: Path, fit_id: str, plan_row: Mapping[str, Any],
    frozen: FrozenConfig, effective: EffectiveFormalConfig, fit_states: Mapping[str, str],
    module_id: str, decision_id: str, candidate_id: str,
) -> FitEvaluation:
    """Score one fit from its integrity-bound checkpoint (the default, no sidecar).

    Succeeded fits are loaded, forwarded on their exact scaled validation batch, decoded
    and scored per-parameter-point; FAILED fits carry the frozen penalty AND the
    all-illegal point records over their validation cell set, so failure rate, L_param
    and pairing truly include the failed seed (R3#6). A fit that is neither succeeded
    nor failed (pending / missing) means the decision's support is incomplete and
    selection fails closed.
    """
    support_key = SupportKey(n=_n_key_of(plan_row), seed=int(plan_row["seed"]))
    status = fit_states.get(fit_id)
    prepared = _prepare_fit_inputs(plan_row, frozen, effective, cache_root, run_dir=run_dir)
    if status == "failed":
        # R3#6: synthesize the all-illegal point records over the failed fit's validation
        # cells so non-ranking rules (failure rate / L_param / pairing) include the failed seed.
        illegal_records = tuple(
            {
                "sample_id": str(meta.get("sample_id", f"val:{i:07d}")),
                "seed_id": str(plan_row["seed"]),
                "point_id": str(meta.get("point_id", f"point-{i:07d}")),
                "legal": False, "failure": 1, "l_param": 10.0,
                "e_beta": 10.0, "e_eta": 10.0, "e_gamma": 10.0,
            }
            for i, meta in enumerate(prepared.validation_metadata)
        )
        return FitEvaluation(
            fit_id=fit_id, module_id=module_id, decision_id=decision_id, candidate_id=candidate_id,
            support_key=support_key, failed=True, checkpoint_sha256="",
            validation_identity=prepared.validation_identity,
            selection_score=0.0, failure_penalty=10.0, point_records=illegal_records,
        )
    if status != "succeeded":
        raise ValueError(
            f"build_module_selection expected fit {fit_id!r} to be terminal, but its state is "
            f"{status!r}; a decision's support must be complete before selection"
        )
    checkpoint_path = run_dir / "outputs" / fit_id / "checkpoint.pt"
    checkpoint_bytes = checkpoint_path.read_bytes()
    scalar, point_records = validation_failure_penalized_l_param_points(
        checkpoint_bytes=checkpoint_bytes, model_factory=prepared.model_factory,
        validation_batch=prepared.scaled_validation.batch, validation_metadata=prepared.validation_metadata,
        seed_id=str(plan_row["seed"]), is_set=prepared.is_set,
    )
    _require_finite_evaluation(fit_id, scalar, point_records)
    return FitEvaluation(
        fit_id=fit_id, module_id=module_id, decision_id=decision_id, candidate_id=candidate_id,
        support_key=support_key, failed=False,
        checkpoint_sha256=hashlib.sha256(checkpoint_bytes).hexdigest(),
        validation_identity=prepared.validation_identity,
        selection_score=scalar, failure_penalty=0.0, point_records=point_records,
    )


def _derive_and_score_evaluations(
    *, study_root: Path, run_dir: Path, cache_root: Path, module_id: str, run_id: str,
    frozen: FrozenConfig, effective: EffectiveFormalConfig,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> tuple[tuple, dict[str, FitEvaluation]]:
    """Single-source derivation + scoring of one module's selection fits (R4#1).

    Derives the module's DecisionSpecs deterministically from the frozen matrix and scores
    every expected supporting fit. With ``score_fit=None`` (the production path used at BOTH
    publish time and pre-unseal) each fit is scored from its integrity-bound checkpoint via
    :func:`_score_fit_from_checkpoint` -- the one scoring path, so the publish-time artifacts
    and the independent pre-unseal rebuild cannot drift into two reasoning calibers. A test
    may inject ``score_fit`` to stand in for checkpoint scoring without launching training.
    Returns ``(specs, evaluations_by_fit)``.
    """
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line)
        for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id=module_id)
    # DecisionSpecs are derived from the frozen matrix (which carries module/fit_kind/n), not
    # from plan.jsonl (whose rows rename those fields); the plan rows supply the runtime
    # per-fit metadata used for scoring. The matrix is the same frozen authority pre-unseal
    # reopens, so the two derivations agree.
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    specs = build_decision_specs(module_id, matrix_rows)
    fit_states: Mapping[str, str] = {}
    if score_fit is None:
        fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
    # A-E3 resolves selected:F2_or_V -> V/F2 ONCE from the predecessor binding (the manifest,
    # validated at materialize time). Threaded into every fit's scoring plan-row resolution.
    a_e3_resolved_baseline_route = (
        _a_e3_resolved_baseline_route_from_manifest(run_dir) if module_id == "A-E3" else "")
    evaluations_by_fit: dict[str, FitEvaluation] = {}
    for spec in specs:
        for candidate in spec.candidates:
            for key in candidate.support_keys:
                fit_id = candidate.support_for(key)
                plan_row = plan_by_fit[fit_id]
                if score_fit is not None:
                    evaluation = score_fit(fit_id, plan_row)
                else:
                    if module_id == "A-E1":
                        scoring_row = _resolve_a_e1_scoring_plan_row(
                            run_dir=run_dir, run_id=run_id, fit_id=fit_id,
                            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)
                    elif module_id == "A-E3":
                        scoring_row = _resolve_a_e3_scoring_plan_row(
                            run_dir=run_dir, run_id=run_id, fit_id=fit_id,
                            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
                            predecessor_resolved_route=a_e3_resolved_baseline_route)
                    else:
                        scoring_row = plan_row
                    evaluation = _score_fit_from_checkpoint(
                        run_dir=run_dir, cache_root=cache_root, fit_id=fit_id,
                        plan_row=scoring_row, frozen=frozen, effective=effective, fit_states=fit_states,
                        module_id=module_id, decision_id=spec.decision_id, candidate_id=candidate.candidate_id,
                    )
                if evaluation.support_key != key:
                    raise ValueError(
                        f"scored fit {fit_id!r} support {evaluation.support_key!r} disagrees with "
                        f"frozen expected {key!r}"
                    )
                evaluations_by_fit[fit_id] = evaluation
    return specs, evaluations_by_fit


def rebuild_selection_point_provenance(
    *, study_root: Path, run_dir: Path, cache_root: Path, module_id: str, run_id: str,
) -> dict[str, FitEvaluation]:
    """R4#1: independently rebuild every selection fit's point evidence from its bound
    checkpoint, reusing the single-source scoring path the publisher used.

    For each expected supporting fit of the module's decisions: a succeeded fit is reloaded
    from ``outputs/{fit_id}/checkpoint.pt`` (the scheduler-authority file), forwarded on the
    validation batch rebuilt from the frozen plan/config/cache, decoded and scored per
    parameter point (mean failure-penalized ``L_param`` + canonical point records); a failed
    fit is rebuilt as the all-illegal records over its frozen validation cells. No fit_status
    scalar and no published artifact is trusted -- the returned :class:`FitEvaluation` map is
    the independently reconstructed truth pre-unseal compares the published artifacts against.
    ``run_id`` is forwarded to the scoring resolver so each A-E1 staged placeholder can be
    concretized from its route's on-disk verified stage1/stage2 receipts; checkpoint bytes
    themselves are read from ``run_dir`` directly.
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    specs, evaluations_by_fit = _derive_and_score_evaluations(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, module_id=module_id,
        run_id=run_id, frozen=frozen, effective=effective, score_fit=None,
    )
    if not specs:
        raise ValueError(f"rebuild_selection_point_provenance derived no selection decisions for module {module_id!r}")
    return evaluations_by_fit


def _validate_selection_evidence(
    *,
    selection_trace_path: Path,
    selection_trace_sha256: str,
    selection_receipt_path: Path,
    selection_ledger_path: Path,
    module_id: str,
    run_id: str,
) -> list[dict[str, Any]]:
    """Read-only validation of one module's immutable selection trace + receipt + ledger.

    Mirrors the binding checks :func:`_validate_predecessor` applies to a downstream module's
    predecessor, but framed for the trace's OWN module -- so placeholder resolution and
    deferred-spec reconstruction can trust a self-published trace, never a hand-assembled one.
    Returns the validated trace records. Fail-closed on any hash, canonical-bytes, ownership,
    receipt-trace binding or ledger-binding mismatch.
    """
    trace_path = Path(selection_trace_path)
    receipt_path = Path(selection_receipt_path)
    ledger_path = Path(selection_ledger_path)
    trace_bytes = trace_path.read_bytes()
    actual_digest, record_count, decision_count = _validate_selection_trace_bytes(
        trace_bytes, selection_trace_sha256, module_id, run_id,
    )
    receipt_bytes = receipt_path.read_bytes()
    try:
        receipt = json.loads(receipt_bytes.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"selection receipt must be valid JSON: {exc}") from exc
    if not isinstance(receipt, dict):
        raise ValueError("selection receipt must be a JSON object")
    receipt_sha = hashlib.sha256(receipt_bytes).hexdigest()
    if receipt.get("receipt_version") != "study02-formal-selection-v3":
        raise ValueError("selection receipt version is not the frozen v3")
    if receipt.get("module_id") != module_id or receipt.get("run_id") != run_id:
        raise ValueError("selection receipt ownership disagrees with declared module/run")
    if receipt.get("selection_trace_sha256") != actual_digest:
        raise ValueError("selection receipt does not bind the validated selection trace SHA-256")
    if receipt.get("effective_config_sha256") != APPROVED_EFFECTIVE_CONFIG_SHA256:
        raise ValueError("selection receipt effective_config_sha256 is not the frozen approved config")
    code_commit = receipt.get("code_commit")
    if not isinstance(code_commit, str) or _CODE_COMMIT_RE.fullmatch(code_commit) is None:
        raise ValueError("selection receipt code_commit must be a full commit ID")
    if receipt.get("record_count") != record_count or receipt.get("decision_count") != decision_count:
        raise ValueError("selection receipt record/decision counts disagree with the validated trace")
    ledger_records = _read_jsonl_bytes(ledger_path.read_bytes(), "Formal selection ledger")
    bindings = [
        row for row in ledger_records
        if row.get("binding_type") == "formal-selection"
        and row.get("module_id") == module_id
        and row.get("run_id") == run_id
    ]
    if len(bindings) != 1:
        raise ValueError(
            f"selection ledger must contain exactly one binding for {module_id}/{run_id}; "
            f"got {len(bindings)}"
        )
    expected_binding = {"binding_type": "formal-selection", **receipt, "receipt_sha256": receipt_sha}
    if bindings[0] != expected_binding:
        raise ValueError("selection ledger binding does not match the validated selection receipt")
    return _read_jsonl_bytes(trace_bytes, "Selection trace")


def resolve_selected_placeholders(
    *,
    placeholders: Mapping[str, str | None],
    selection_trace_path: Path,
    selection_trace_sha256: str,
    selection_receipt_path: Path,
    selection_ledger_path: Path,
    module_id: str,
    run_id: str,
) -> dict[str, str]:
    """Resolve ``selected:<decision>`` / ``selected_top_N`` placeholders from one
    fully-validated immutable selection trace + receipt + ledger (D8).

    ``placeholders`` maps each placeholder token to the ``rank_decision_id`` whose candidate
    ranking defines it: REQUIRED for ``selected_top_N`` (the N-th ranked candidate comes from
    that decision's ranking), and ignored for ``selected:<decision>`` (which embeds its own
    decision id). Returns ``{placeholder: resolved_value}``.

    The trace/receipt/ledger are validated read-only first (:func:`_validate_selection_evidence`
    -- hash + canonical bytes + module/run ownership + receipt-trace binding + ledger binding),
    so a caller cannot inject an unverified or hand-assembled trace. Each placeholder then
    resolves fail-closed:

    * ``selected:<decision>`` -> the unique selected winner of the trace decision whose
      ``decision_id`` equals ``<decision>``. Zero matches (missing) or a decision without
      exactly one winner (non-winner / ambiguous) raise.
    * ``selected_top_N`` -> the rank-N candidate (1-indexed) of ``rank_decision_id``, where the
      ranking is the frozen ``(validation_score, tie_break_key, candidate_id)`` ascending order
      the trace validator enforces (rank-1 is the winner). ``N`` out of bounds, a non-integer
      slot, or a missing/ambiguous ranking decision raise.

    Determinism: a given validated trace + placeholders always yield the same resolved values
    and the same raise behaviour, independent of dict ordering; the winners and rankings are
    materialised in a single deterministic pass before any placeholder is resolved.
    """
    records = _validate_selection_evidence(
        selection_trace_path=Path(selection_trace_path),
        selection_trace_sha256=selection_trace_sha256,
        selection_receipt_path=Path(selection_receipt_path),
        selection_ledger_path=Path(selection_ledger_path),
        module_id=module_id, run_id=run_id,
    )
    by_decision: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        by_decision.setdefault(record["decision_id"], []).append(record)
    ranking_by_decision: dict[str, list[str]] = {}
    winners_by_decision: dict[str, str] = {}
    for decision_id in sorted(by_decision):
        decision_rows = by_decision[decision_id]
        ranked = sorted(
            decision_rows,
            key=lambda row: (
                float(row["validation_score"]),
                _tie_break_sort_key(row["tie_break_key"]),
                str(row["candidate_id"]),
            ),
        )
        ranking_by_decision[decision_id] = [str(row["candidate_id"]) for row in ranked]
        selected = [row for row in decision_rows if row["selected"] is True]
        if len(selected) != 1:
            raise ValueError(
                f"selection trace decision {decision_id!r} must select exactly one winner; "
                f"got {len(selected)}"
            )
        winners_by_decision[decision_id] = str(selected[0]["candidate_id"])

    resolved: dict[str, str] = {}
    for placeholder in placeholders:
        rank_decision_id = placeholders[placeholder]
        _require(isinstance(placeholder, str) and placeholder, "placeholder token must be non-empty")
        if placeholder.startswith(_STAGE_TOP_PREFIX):
            if not isinstance(rank_decision_id, str) or not rank_decision_id:
                raise ValueError(
                    f"placeholder {placeholder!r} (selected_top_N) requires a rank_decision_id"
                )
            slot_text = placeholder[len(_STAGE_TOP_PREFIX):]
            if not slot_text.isdigit():
                raise ValueError(f"selected_top_N slot must be a positive integer: {placeholder!r}")
            slot = int(slot_text)
            if slot < 1:
                raise ValueError(f"selected_top_N slot must be >= 1: {placeholder!r}")
            ranking = ranking_by_decision.get(rank_decision_id)
            if ranking is None:
                raise ValueError(
                    f"rank decision {rank_decision_id!r} is missing from the selection trace "
                    f"(needed by {placeholder!r})"
                )
            if slot > len(ranking):
                raise ValueError(
                    f"{placeholder!r} slot {slot} is out of bounds for decision "
                    f"{rank_decision_id!r} with {len(ranking)} ranked candidates"
                )
            resolved[placeholder] = ranking[slot - 1]
        elif placeholder.startswith(_SELECTED_PREFIX):
            decision_id = placeholder[len(_SELECTED_PREFIX):]
            _require(
                bool(decision_id),
                f"selected:<decision> placeholder must name a decision: {placeholder!r}",
            )
            if decision_id not in winners_by_decision:
                raise ValueError(
                    f"placeholder {placeholder!r} names decision {decision_id!r} that is absent "
                    "from the selection trace"
                )
            resolved[placeholder] = winners_by_decision[decision_id]
        else:
            raise ValueError(f"unsupported placeholder token: {placeholder!r}")
    return resolved


@dataclass(frozen=True)
class _DeferredDatasetSpec:
    """A frozen A-E3/A-E2 deferred-dataset-v1 binding (placeholder route + predecessor trace).

    Downstream modules (A-E3, A-E2) cannot build a concrete dataset until their predecessor
    selection resolves the placeholder route/loss/architecture/optimizer; the scheduler
    therefore binds a deferred-dataset-v1 schema (the placeholder route literal + the verified
    predecessor trace SHA) and hashes it into the plan row's ``training_cache_key`` /
    ``validation_cache_key``. This dataclass rebuilds that exact schema so the executor and the
    scheduler agree byte-for-byte (mirroring :func:`reconstruct_a_e1_specs` for the concrete
    A-E1 path). It is NOT a concrete dataset and opens no data.
    """

    role: str
    schema_version: str
    route: str
    distribution: str
    n_mode: str
    fixed_n: int | None
    training_size: int
    effective_config_sha256: str
    predecessor_trace_sha256: str

    def payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "route": self.route,
            "distribution": self.distribution,
            "n_mode": self.n_mode,
            "fixed_n": self.fixed_n,
            "training_size": self.training_size,
            "effective_config_sha256": self.effective_config_sha256,
            "predecessor_trace_sha256": self.predecessor_trace_sha256,
            "role": self.role,
        }

    @property
    def cache_key(self) -> str:
        return hashlib.sha256(_canonical(self.payload())).hexdigest()


def reconstruct_deferred_specs(
    plan_row: Mapping[str, Any],
    frozen: FrozenConfig,
    effective: EffectiveFormalConfig,
    predecessor: Mapping[str, Any] | PredecessorTrace | None,
) -> tuple[_DeferredDatasetSpec, _DeferredDatasetSpec]:
    """Rebuild the A-E3/A-E2 deferred training/validation specs bound to a predecessor trace (D8).

    Validates the predecessor exactly as the scheduler's manifest builder does
    (:func:`_validate_predecessor` -- A-E3 accepts only an A-E1 predecessor, A-E2 only an A-E3
    predecessor; the trace SHA, receipt SHA, ledger binding, module and run are all checked), then
    rebuilds the deferred-dataset-v1 cache keys from the frozen plan row and the verified
    predecessor trace SHA, asserting they equal the plan row's bound
    ``training_cache_key`` / ``validation_cache_key`` -- so the executor and the scheduler agree
    byte-for-byte (the same contract :func:`reconstruct_a_e1_specs` enforces for concrete A-E1).

    Fail-closed (raises) on: a module with no predecessor (A-E1 or unknown), a wrong-order
    predecessor, a predecessor whose trace SHA disagrees with the plan row's bound
    ``predecessor_trace_sha256`` (stale or cross-run trace), a missing/inconsistent receipt or
    ledger binding (double / zero consumption), or any reconstructed cache key that drifts from
    the scheduler plan.
    """
    module_id = str(plan_row["module_id"])
    expected_pred = _PREDECESSOR_BY_MODULE.get(module_id)
    if expected_pred is None:
        raise ValueError(
            f"deferred dataset specs exist only for downstream modules (A-E3, A-E2); "
            f"module {module_id!r} has no predecessor"
        )
    predecessor_manifest = _validate_predecessor(module_id, predecessor)
    predecessor_trace_sha = predecessor_manifest["selection_trace_sha256"]
    # Stale / cross-run guard: the plan row binds a predecessor trace SHA at planning time; the
    # verified predecessor must be that exact trace. A different SHA means the trace was replaced
    # after planning (stale) or belongs to a different run (cross-run).
    bound_pred_sha = str(plan_row["predecessor_trace_sha256"])
    if bound_pred_sha != predecessor_trace_sha:
        raise ValueError(
            f"plan row binds predecessor trace {bound_pred_sha!r} but the verified predecessor "
            f"trace is {predecessor_trace_sha!r} (stale or cross-run predecessor)"
        )
    common = dict(
        schema_version="study02-formal-deferred-dataset-v1",
        route=str(plan_row["route"]),
        distribution=str(plan_row["distribution"]),
        n_mode=str(plan_row["n_mode"]),
        fixed_n=plan_row["fixed_n"],
        training_size=int(plan_row["training_size"]),
        effective_config_sha256=effective.effective_config_sha256,
        predecessor_trace_sha256=predecessor_trace_sha,
    )
    training = _DeferredDatasetSpec(role="training", **common)
    validation = _DeferredDatasetSpec(role="validation", **common)
    _require(
        training.cache_key == str(plan_row["training_cache_key"]),
        "reconstructed deferred training cache key drifts from the scheduler plan",
    )
    _require(
        validation.cache_key == str(plan_row["validation_cache_key"]),
        "reconstructed deferred validation cache key drifts from the scheduler plan",
    )
    return training, validation


def build_module_pre_unseal_bundle(
    *,
    study_root: Path,
    cache_root: Path,
    run_dirs: Mapping[str, Path],
    formal_manifests: Sequence[Path],
    selection_traces: Sequence[Path],
    selection_receipts: Sequence[Path],
    selection_ledger_path: Path,
    fit_status_path: Path,
    ceiling_report_path: Path,
    leakage_audit_path: Path,
    code_commit: str,
    effective_config_sha256: str,
    module_run_ids: Mapping[str, str],
    point_evidence_paths: Mapping[str, Path],
    selection_diagnostics_paths: Sequence[Path],
) -> dict[str, Any]:
    """Production pre-unseal entry (D8 + R5 hard requirement).

    Builds the pre-unseal bundle by independently rebuilding every module's selection point
    provenance from its bound checkpoints (:func:`rebuild_selection_point_provenance` -- the
    R5-approved single-source rebuild: reload ``checkpoint.pt`` -> rebuild validation inputs ->
    forward -> decode -> canonical point records) and handing the result to
    :func:`build_pre_unseal_bundle` as ``point_provenance_by_fit``.

    The caller CANNOT supply ``point_provenance_by_fit`` -- the rebuild is mandatory and is
    performed inside this entry, never imported from outside, so no caller can substitute an
    unverified or stale provenance map for the production authority (R5: the artifact's
    self-consistent content SHA leaves a re-synced forgery open unless the records come from the
    actual checkpoint). ``point_provenance_by_fit`` is deliberately absent from this signature,
    so passing it raises ``TypeError``. ``run_dirs`` maps each module id to its materialized run
    directory.
    """
    study_root = Path(study_root).resolve()
    cache_root = Path(cache_root).resolve()
    if set(run_dirs) != set(module_run_ids):
        raise ValueError("run_dirs and module_run_ids must cover the same modules")
    point_provenance_by_fit: dict[str, Any] = {}
    for module_id, run_id in module_run_ids.items():
        run_dir = Path(run_dirs[module_id]).resolve()
        rebuilt = rebuild_selection_point_provenance(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root,
            module_id=module_id, run_id=run_id,
        )
        for fit_id, evaluation in rebuilt.items():
            if fit_id in point_provenance_by_fit:
                raise ValueError(
                    f"independent provenance rebuild produced a duplicate fit_id {fit_id!r} "
                    f"across modules"
                )
            point_provenance_by_fit[fit_id] = evaluation
    return build_pre_unseal_bundle(
        formal_manifests=formal_manifests,
        selection_traces=selection_traces,
        selection_receipts=selection_receipts,
        selection_ledger_path=selection_ledger_path,
        fit_status_path=fit_status_path,
        ceiling_report_path=ceiling_report_path,
        leakage_audit_path=leakage_audit_path,
        code_commit=code_commit,
        effective_config_sha256=effective_config_sha256,
        module_run_ids=module_run_ids,
        point_evidence_paths=point_evidence_paths,
        selection_diagnostics_paths=selection_diagnostics_paths,
        point_provenance_by_fit=point_provenance_by_fit,
    )


# ---------------------------------------------------------------------------
# D8 staged A-E1 resolution. The frozen A-E1 matrix emits placeholders the generic
# resolver cannot resolve on its own:
#   selected_top_1..4            -> rank-1..4 architecture of a route's stage1
#   selected:A-E1_loss           -> the frozen stage2 loss (transformed_train_z_huber)
#   selected:A-E1_architecture   -> a route's stage2 winner architecture (via its top slot)
#   selected:A-E1_optimizer      -> a route's stage2 winner optimizer
#   selected:F2_or_V             -> the F2-vs-V baseline route (global_better_rule)
# This resolver derives every one of them from the validated module selection trace +
# the winner-retrain evidence, through an immutable, hash-bound, append-only staged
# ledger. The caller supplies only the run authority (``run_dir``) + frozen matrix;
# winner/top4/baseline are DERIVED, never passed in. No real fit is launched and no
# test role is opened (``test_access_count`` stays 0).
# ---------------------------------------------------------------------------

_A_E1_OPTIMIZED_ROUTES = ("F2", "V")
_A_E1_SEARCH_N = 10
_A_E1_STAGE2_FROZEN_LOSS = "transformed_train_z_huber"  # the matrix fixes the stage2 loss
_A_E1_BASELINE_DECISION_ID = "baseline_input:A-E1:F2_vs_V"
_STAGED_RESOLUTION_VERSION = "study02-staged-resolution-v1"
_STAGED_JOURNAL_VERSION = "study02-staged-resolution-journal-v1"
_STAGED_LEDGER_NAME = "staged_resolution_ledger.jsonl"
_ZERO_HASH = "0" * 64


def _a_e1_stage1_decision_id(route: str) -> str:
    return f"architecture:A-E1:{route}:n{_A_E1_SEARCH_N}"


def _a_e1_stage2_decision_id(route: str) -> str:
    return f"stage2:A-E1:{route}:n{_A_E1_SEARCH_N}"


def _parse_stage2_winner_candidate(candidate_id: str) -> tuple[str, str]:
    """Split a stage2 winner ``selected_top_{slot}:{opt}`` into (arch_placeholder, optimizer)."""
    arch_part, sep, opt_part = candidate_id.partition(":")
    if not sep or not arch_part.startswith(_STAGE_TOP_PREFIX) or not opt_part:
        raise ValueError(
            f"stage2 winner candidate {candidate_id!r} must be a selected_top slot:optimizer pair"
        )
    return arch_part, opt_part


def _staged_ledger_path(run_dir: Path) -> Path:
    return Path(run_dir) / _STAGED_LEDGER_NAME


def _read_staged_ledger(run_dir: Path) -> list[dict[str, Any]]:
    path = _staged_ledger_path(run_dir)
    if not path.exists():
        return []
    return _read_jsonl_bytes(path.read_bytes(), "Staged resolution ledger")


def _build_stage_record(
    *, module_id: str, run_id: str, code_commit: str, effective_config_sha256: str,
    selection_trace_sha256: str, stage: str, route: str | None,
    previous_record_sha256: str, input_payload: Mapping[str, Any],
    resolution: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble one hash-bound staged resolution record (record_sha256 self-hashes the core)."""
    resolution_sha = hashlib.sha256(_canonical(dict(resolution))).hexdigest()
    core = {
        "record_version": _STAGED_RESOLUTION_VERSION,
        "module_id": module_id,
        "run_id": run_id,
        "code_commit": str(code_commit).lower(),
        "effective_config_sha256": effective_config_sha256,
        "selection_trace_sha256": selection_trace_sha256,
        "stage": stage,
        "route": route,
        "previous_record_sha256": previous_record_sha256,
        "input": dict(input_payload),
        "resolution": dict(resolution),
        "resolution_sha256": resolution_sha,
    }
    record_sha = hashlib.sha256(_canonical(core)).hexdigest()
    return {**core, "record_sha256": record_sha}


def _recover_staged_journal(ledger_path: Path, journal_path: Path) -> None:
    """Replay or drop a staged-ledger journal left by a crash mid-append (never overwrites)."""
    if not journal_path.exists():
        return
    journal = json.loads(journal_path.read_bytes().decode("utf-8"))
    expected_size = int(journal["ledger_size_before"])
    expected_sha = str(journal["ledger_sha_before"])
    record = journal["record"]
    ledger_bytes = ledger_path.read_bytes() if ledger_path.exists() else b""
    if (len(ledger_bytes) < expected_size
            or hashlib.sha256(ledger_bytes[:expected_size]).hexdigest() != expected_sha):
        raise ValueError("staged resolution journal ledger prefix conflicts with the recorded snapshot")
    canonical_line = _canonical(record)
    if ledger_bytes[expected_size:] != canonical_line:
        # partial or garbled tail -> restore the verified prefix and re-append the full record
        with ledger_path.open("r+b" if ledger_path.exists() else "w+b") as handle:
            handle.truncate(expected_size)
            handle.flush()
            os.fsync(handle.fileno())
        append_ledger(record, ledger_path)
    journal_path.unlink(missing_ok=True)


def _append_stage_record(run_dir: Path, record: Mapping[str, Any]) -> dict[str, Any]:
    """Append one staged resolution record under an exclusive lock.

    Append-only (never overwrites). Idempotent on an exact match (a recovery rerun that
    recomputes the same resolution reuses the existing record -- no double-consume);
    fail-closed on a conflicting duplicate (a second, different resolution for the same
    stage/route is a duplicate stage receipt / stale mapping, never silently overwritten).
    A crash mid-append is recovered idempotently via ``_recover_staged_journal``.
    """
    ledger_path = _staged_ledger_path(run_dir)
    ledger_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = ledger_path.with_name(ledger_path.name + ".lock")
    journal_path = ledger_path.with_name(ledger_path.name + ".journal")
    lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    try:
        _recover_staged_journal(ledger_path, journal_path)
        existing = _read_staged_ledger(run_dir)
        key = (record["stage"], record.get("route"))
        for prior in existing:
            if (prior["stage"], prior.get("route")) == key:
                if (prior["record_sha256"] != record["record_sha256"]
                        or prior["resolution_sha256"] != record["resolution_sha256"]):
                    raise ValueError(
                        f"staged resolution record for stage={key[0]!r} route={key[1]!r} already "
                        f"exists with a different resolution (duplicate stage receipt / stale mapping)"
                    )
                return dict(prior)  # idempotent reuse -- no double-consume, no overwrite
        ledger_bytes = ledger_path.read_bytes() if ledger_path.exists() else b""
        journal_record = {
            "journal_version": _STAGED_JOURNAL_VERSION,
            "ledger_size_before": len(ledger_bytes),
            "ledger_sha_before": hashlib.sha256(ledger_bytes).hexdigest(),
            "record": dict(record),
        }
        journal_path.write_bytes(_canonical(journal_record))
        append_ledger(record, ledger_path)
        journal_path.unlink(missing_ok=True)
        return dict(record)
    finally:
        try:
            os.close(lock_fd)
        except OSError:
            pass
        Path(lock_path).unlink(missing_ok=True)


def _build_a_e1_baseline_candidates(frozen: FrozenConfig) -> list[CandidateSpec]:
    """Build the F2/V baseline-input CandidateSpecs from the frozen winner-retrain rows.

    Each route's support grid is its full winner-retrain plan (core_n x formal seeds); the
    two routes share the same grid so their evidence is pairable for ``global_better_rule``.
    """
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    candidates: list[CandidateSpec] = []
    for route in _A_E1_OPTIMIZED_ROUTES:
        support_to_fit: dict[SupportKey, str] = {}
        for row in matrix_rows:
            if (str(row["module"]) != "A-E1" or str(row["fit_kind"]) != "winner_retrain"
                    or str(row["route"]) != route):
                continue
            key = SupportKey(n=int(row["n"]), seed=int(row["seed"]))
            if key in support_to_fit:
                raise ValueError(f"duplicate winner-retrain support {key!r} for route {route!r}")
            support_to_fit[key] = str(row["fit_id"])
        if not support_to_fit:
            raise ValueError(f"frozen matrix has no A-E1 winner-retrain rows for route {route!r}")
        support_keys = tuple(sorted(support_to_fit, key=lambda k: (str(k.n), int(k.seed))))
        candidates.append(CandidateSpec(
            decision_id=_A_E1_BASELINE_DECISION_ID, candidate_id=route,
            selection_rule=SELECTION_RULE_GLOBAL_BETTER, tie_break_key=(route,),
            support_keys=support_keys,
            expected_fit_ids=tuple(support_to_fit[key] for key in support_keys),
            fit_id_by_support=support_to_fit,
            approved_seeds=tuple(sorted({int(key.seed) for key in support_keys})),
        ))
    return candidates


def _score_a_e1_winner_retrain(
    *, study_root: Path, run_dir: Path, cache_root: Path, frozen: FrozenConfig,
    effective: EffectiveFormalConfig, candidates: Sequence[CandidateSpec],
    run_id: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
) -> tuple[dict[str, FitEvaluation] | None, bool]:
    """Score the F2/V winner-retrain fits. Returns ``(evaluations_by_fit, pending)``.

    The full A-E1 plan is read and validated against the frozen matrix first
    (``_validate_plan_against_matrix``); the winner-retrain subset is taken from that validated
    ``plan_by_fit`` (never passed to the validator as a subset). ``score_fit`` (tests) injects bound
    evaluations without launching training. The production default scores each winner-retrain
    checkpoint with the route's RESOLVED architecture/optimizer/loss, recovered from the route's
    on-disk verified stage1/stage2 receipts via ``_resolve_a_e1_scoring_plan_row`` (the placeholders
    cannot build a model until stage2 resolves them); a winner-retrain fit that has not yet
    succeeded leaves the baseline ``pending`` rather than forcing a partial comparison.
    """
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line)
        for line in (Path(run_dir) / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E1")
    if score_fit is not None:
        evaluations: dict[str, FitEvaluation] = {}
        for candidate in candidates:
            for key in candidate.support_keys:
                fit_id = candidate.support_for(key)
                evaluation = score_fit(fit_id, plan_by_fit[fit_id])
                if evaluation.support_key != key:
                    raise ValueError(
                        f"winner-retrain evaluation for {fit_id!r} support {evaluation.support_key!r} "
                        f"disagrees with frozen expected {key!r}"
                    )
                evaluations[fit_id] = evaluation
        return evaluations, False
    fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
    evaluations = {}
    for candidate in candidates:
        for key in candidate.support_keys:
            fit_id = candidate.support_for(key)
            if fit_states.get(fit_id) != "succeeded":
                return None, True  # winner-retrain not executed yet -> baseline pending
            resolved_row = _resolve_a_e1_scoring_plan_row(
                run_dir=run_dir, run_id=run_id, fit_id=fit_id,
                matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)
            evaluations[fit_id] = _score_fit_from_checkpoint(
                run_dir=run_dir, cache_root=cache_root, fit_id=fit_id, plan_row=resolved_row,
                frozen=frozen, effective=effective, fit_states=fit_states, module_id="A-E1",
                decision_id=_A_E1_BASELINE_DECISION_ID, candidate_id=candidate.candidate_id,
            )
    return evaluations, False


def _resolve_a_e1_baseline(
    *, module_id: str, run_id: str, candidates: Sequence[CandidateSpec],
    evaluations_by_fit: Mapping[str, FitEvaluation],
) -> tuple[str, dict[str, dict[str, Any]], Mapping[str, Any]]:
    """Apply the frozen ``global_better_rule`` to the F2/V winner-retrain evidence.

    Returns ``(winner_route, evidence_by_candidate, rule_result)``. The winner is COMPUTED by
    the frozen rule over the full pairable winner-retrain support, never supplied.
    """
    spec = DecisionSpec(
        module_id=module_id, decision_id=_A_E1_BASELINE_DECISION_ID, axis="baseline_input",
        selection_rule=SELECTION_RULE_GLOBAL_BETTER, candidates=tuple(candidates),
    )
    evidence_by_candidate: dict[str, dict[str, Any]] = {}
    evals_by_candidate: dict[str, Mapping[SupportKey, FitEvaluation]] = {}
    for candidate in candidates:
        evaluations_by_support: dict[SupportKey, FitEvaluation] = {}
        for key in candidate.support_keys:
            fit_id = candidate.support_for(key)
            evaluation = evaluations_by_fit.get(fit_id)
            if evaluation is None:
                raise ValueError(f"missing winner-retrain evaluation for baseline fit {fit_id!r}")
            if evaluation.support_key != key:
                raise ValueError(
                    f"baseline fit {fit_id!r} support {evaluation.support_key!r} disagrees with {key!r}"
                )
            evaluations_by_support[key] = evaluation
        evidence_by_candidate[candidate.candidate_id] = candidate_supporting_evidence(
            module_id=module_id, run_id=run_id, candidate=candidate,
            evaluations_by_support=evaluations_by_support,
        )
        evals_by_candidate[candidate.candidate_id] = evaluations_by_support
    winner, rule_result = apply_selection_rule(spec, evidence_by_candidate, evals_by_candidate)
    if winner not in {candidate.candidate_id for candidate in candidates}:
        raise ValueError(f"baseline winner {winner!r} is not one of the F2/V routes")
    return winner, evidence_by_candidate, rule_result


def resolve_a_e1_staged_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path,
    module_id: str = "A-E1", run_id: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Production staged A-E1 resolver (D8).

    Derives every real frozen A-E1 placeholder from the validated module selection trace +
    winner-retrain evidence through an immutable, hash-bound, append-only staged ledger
    (``run_dir/staged_resolution_ledger.jsonl``). The caller supplies only the run authority
    (``run_dir``) + frozen matrix; ``winner``/``top4``/``baseline`` are DERIVED, never passed.

    Pending stages are computed from the run authority + frozen matrix:

    * If the module selection trace does not exist, every stage is pending.
    * ``stage1`` -> ``selected_top_1..4``, ``stage2`` -> the route's
      ``selected:A-E1_{loss,architecture,optimizer}``, and the route's ``winner_retrain``
      aliases resolve from the validated selection trace (the architecture + stage2 decisions).
    * The F2-vs-V ``baseline_input`` (``selected:F2_or_V`` via ``global_better_rule``) and the
      final module aliases resolve once the winner-retrain evidence is available
      (``score_fit`` injection in tests; scored from bound checkpoints in production). Until
      then they are reported as pending rather than resolved from a partial support.

    The staged ledger is append-only and crash-recoverable: a recovery rerun recomputes each
    stage, reuses records whose resolution matches, and fails closed on a conflicting
    duplicate (no overwrite, no double-consume). No real fit is launched; no test role is
    opened (``test_access_count`` stays 0).
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    if module_id != "A-E1":
        raise NotImplementedError(
            f"staged resolution of module {module_id!r} is not implemented; only A-E1"
        )
    pending_all = ["stage1", "stage2", "winner_retrain", "baseline_input", "final_aliases"]
    if not (run_dir / "selection_trace.jsonl").exists():
        return {
            "module_id": module_id, "run_id": run_id,
            "staged_ledger_path": str(_staged_ledger_path(run_dir)),
            "selection_trace_sha256": None, "top4_by_route": {}, "stage2_by_route": {},
            "selected_F2_or_V": None, "final_aliases": None, "record_sha256": {},
            "pending": pending_all,
        }
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    code_commit = str(manifest["code_commit"])
    receipt = json.loads((run_dir / "selection_receipt.json").read_text(encoding="utf-8"))
    trace_sha = str(receipt["selection_trace_sha256"])
    trace_records = _validate_selection_evidence(
        selection_trace_path=run_dir / "selection_trace.jsonl",
        selection_trace_sha256=trace_sha,
        selection_receipt_path=run_dir / "selection_receipt.json",
        selection_ledger_path=run_dir / "selection_ledger.jsonl",
        module_id=module_id, run_id=run_id,
    )
    by_decision: dict[str, list[dict[str, Any]]] = {}
    for record in trace_records:
        by_decision.setdefault(record["decision_id"], []).append(record)
    evidence_kwargs = dict(
        selection_trace_path=run_dir / "selection_trace.jsonl",
        selection_trace_sha256=trace_sha,
        selection_receipt_path=run_dir / "selection_receipt.json",
        selection_ledger_path=run_dir / "selection_ledger.jsonl",
        module_id=module_id, run_id=run_id,
    )

    existing_records = _read_staged_ledger(run_dir)
    # The chain is rebuilt from the first stage on every call; idempotent reuse inside
    # ``_append_stage_record`` walks the existing records in the same deterministic order, so a
    # recovery rerun never reorders or re-chains an already-published ledger.
    previous_sha = _ZERO_HASH
    record_shas: dict[str, str] = {}
    top4_by_route: dict[str, dict[str, str]] = {}
    stage2_by_route: dict[str, dict[str, str]] = {}

    def _publish(stage: str, route: str | None, input_payload: Mapping[str, Any],
                 resolution: Mapping[str, Any]) -> dict[str, Any]:
        nonlocal previous_sha
        record = _build_stage_record(
            module_id=module_id, run_id=run_id, code_commit=code_commit,
            effective_config_sha256=effective.effective_config_sha256,
            selection_trace_sha256=trace_sha, stage=stage, route=route,
            previous_record_sha256=previous_sha, input_payload=input_payload, resolution=resolution,
        )
        published = _append_stage_record(run_dir, record)
        previous_sha = published["record_sha256"]
        record_shas[f"{stage}:{route if route else ''}"] = published["record_sha256"]
        return published

    pending_stages: list[str] = []

    # --- stage1 -> top4, stage2 -> route winner, winner_retrain aliases (from the trace) ---
    for route in _A_E1_OPTIMIZED_ROUTES:
        stage1_dec = _a_e1_stage1_decision_id(route)
        stage2_dec = _a_e1_stage2_decision_id(route)
        _require(stage1_dec in by_decision, f"selection trace is missing the stage1 decision {stage1_dec!r}")
        _require(stage2_dec in by_decision, f"selection trace is missing the stage2 decision {stage2_dec!r}")
        top4 = resolve_selected_placeholders(
            placeholders={f"selected_top_{slot}": stage1_dec for slot in range(1, 5)},
            **evidence_kwargs,
        )
        top4_by_route[route] = top4
        arch_records = sorted(
            by_decision[stage1_dec],
            key=lambda r: (float(r["validation_score"]), _tie_break_sort_key(r["tie_break_key"]), str(r["candidate_id"])),
        )
        stage1_input = {
            "decision_id": stage1_dec,
            "ranking": [
                {"candidate_id": str(r["candidate_id"]), "validation_score": float(r["validation_score"]),
                 "selected": bool(r["selected"]), "supporting_evidence_sha256": str(r["supporting_evidence_sha256"])}
                for r in arch_records
            ],
        }
        stage1_record = _publish("stage1", route, stage1_input, top4)

        stage2_records = by_decision[stage2_dec]
        winner_record = next((r for r in stage2_records if r["selected"]), None)
        _require(winner_record is not None, f"stage2 decision {stage2_dec!r} has no selected winner")
        arch_placeholder, optimizer = _parse_stage2_winner_candidate(str(winner_record["candidate_id"]))
        _require(
            arch_placeholder in top4,
            f"stage2 winner slot {arch_placeholder!r} is outside the resolved top4 for route {route!r}",
        )
        architecture = top4[arch_placeholder]
        loss = _A_E1_STAGE2_FROZEN_LOSS
        route_result = {
            "selected:A-E1_loss": loss,
            "selected:A-E1_architecture": architecture,
            "selected:A-E1_optimizer": optimizer,
        }
        stage2_by_route[route] = route_result
        stage2_input = {
            "decision_id": stage2_dec,
            "winner_candidate_id": str(winner_record["candidate_id"]),
            "winner_supporting_evidence_sha256": str(winner_record["supporting_evidence_sha256"]),
            "stage1_record_sha256": stage1_record["record_sha256"],
            "resolved_top_slot": arch_placeholder,
            "frozen_loss": loss,
        }
        stage2_record = _publish("stage2", route, stage2_input, route_result)
        retrain_input = {
            "stage2_record_sha256": stage2_record["record_sha256"],
            "placeholder_fields": ["selected:A-E1_loss", "selected:A-E1_architecture", "selected:A-E1_optimizer"],
        }
        _publish("winner_retrain", route, retrain_input, route_result)

    # --- baseline (F2 vs V) + final aliases, from the winner-retrain evidence ---
    baseline_candidates = _build_a_e1_baseline_candidates(frozen)
    route_stage2 = {route: (res["selected:A-E1_loss"], res["selected:A-E1_architecture"],
                            res["selected:A-E1_optimizer"]) for route, res in stage2_by_route.items()}
    evaluations_by_fit, pending = _score_a_e1_winner_retrain(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, frozen=frozen,
        effective=effective, candidates=baseline_candidates, run_id=run_id,
        score_fit=score_fit,
    )
    winner_route: str | None = None
    final_aliases: dict[str, str] | None = None
    if pending or evaluations_by_fit is None:
        pending_stages.extend(["baseline_input", "final_aliases"])
    else:
        winner_route, baseline_evidence, baseline_rule_result = _resolve_a_e1_baseline(
            module_id=module_id, run_id=run_id, candidates=baseline_candidates,
            evaluations_by_fit=evaluations_by_fit,
        )
        baseline_input = {
            "decision_id": _A_E1_BASELINE_DECISION_ID,
            "candidate_supporting_evidence_sha256": {
                candidate.candidate_id: baseline_evidence[candidate.candidate_id]["supporting_evidence_sha256"]
                for candidate in baseline_candidates
            },
            "rule_result": dict(baseline_rule_result),
            "winner_retrain_fit_count": len(evaluations_by_fit),
        }
        baseline_resolution = {"selected:F2_or_V": winner_route}
        baseline_record = _publish("baseline_input", None, baseline_input, baseline_resolution)
        loss_w, arch_w, opt_w = route_stage2[winner_route]
        final_aliases = {
            "selected:A-E1_loss": loss_w,
            "selected:A-E1_architecture": arch_w,
            "selected:A-E1_optimizer": opt_w,
        }
        final_input = {
            "baseline_record_sha256": baseline_record["record_sha256"],
            "winning_route": winner_route,
            "winning_route_stage2": {"loss": loss_w, "architecture": arch_w, "optimizer": opt_w},
        }
        _publish("final_aliases", None, final_input, final_aliases)

    return {
        "module_id": module_id, "run_id": run_id,
        "staged_ledger_path": str(_staged_ledger_path(run_dir)),
        "selection_trace_sha256": trace_sha,
        "top4_by_route": top4_by_route,
        "stage2_by_route": stage2_by_route,
        "selected_F2_or_V": winner_route,
        "final_aliases": final_aliases,
        "record_sha256": record_shas,
        "pending": pending_stages,
    }


# ---------------------------------------------------------------------------
# R3-B: dedicated n_strategy evidence (fixed vs shared).
#
# The n_strategy decision is NOT a matrix decision (``shared_winner_retrain`` is not in
# ``_FIT_KIND_AXIS``; reproducer #2 stays negative). It is constructed from two dedicated
# cohorts scored outside ``build_decision_specs``:
#
#   * fixed cohort  = 5 core n x 10 formal seeds (50 cells); each cell's checkpoint is the
#     output_form winner candidate's fit at (core_n, formal_seed), scored on its fixed-n
#     validation cell (re-using the single-source ``_score_fit_from_checkpoint`` path).
#   * shared cohort = 10 shared_winner_retrain checkpoints x 5 core-n validation subsets
#     (50 cells); each shared DeepSets checkpoint is scored on each core-n subset of the
#     shared_n validation batch (sliced where ``batch.n == core_n``).
#
# Both cohorts share the SAME 5 x 10 = 50-cell support grid (``SupportKey(core_n,
# formal_seed)``), so the frozen ``fixed_vs_shared_equal_weight`` rule
# (``_equal_weight_per_n_aggregate``) pairs them cell-for-cell. Failed fits are NOT skipped
# (they carry the frozen penalty + all-illegal point records over their validation cell).
# ---------------------------------------------------------------------------


def _a_e3_core_n_values(frozen: FrozenConfig) -> tuple[int, ...]:
    """The frozen 5 core sample sizes (``protocol.sample_sizes.core``).

    Used as the equal-weight aggregation axis for the n_strategy decision. Read from the
    frozen config (never hardcoded) so a protocol bump flows through.
    """
    return tuple(int(n) for n in frozen.protocol["sample_sizes"]["core"])


def _shared_core_n_validation_identity(shared_validation_identity: str, core_n: int) -> str:
    """Deterministic per-core-n validation identity for the shared cohort.

    The shared_n validation batch mixes all 5 core n; slicing it by ``batch.n == core_n``
    yields a per-core-n subset whose content identity is the shared cache key plus the
    ``:n{core_n}`` filter. This is the identity bound into each shared-cohort cell's
    point-evidence SHA, so pre-unseal rebuilds reconstruct the same digest.
    """
    return f"{shared_validation_identity}:n{int(core_n)}"


def _score_shared_fit_on_core_n_subset(
    *, run_dir: Path, cache_root: Path, fit_id: str, plan_row: Mapping[str, Any],
    frozen: FrozenConfig, effective: EffectiveFormalConfig, fit_states: Mapping[str, str],
    core_n: int, module_id: str, decision_id: str, candidate_id: str,
) -> FitEvaluation:
    """Score one shared DeepSets checkpoint on one core-n validation subset.

    Builds the shared_n validation batch via the single-source ``_prepare_fit_inputs`` path
    and slices it where ``batch.n == core_n``. The sliced sub-batch is forwarded through
    the loaded checkpoint and scored per-parameter-point. A failed shared fit carries the
    frozen penalty + all-illegal point records over its core-n subset (R3#6: failures are
    not skipped). Returns a :class:`FitEvaluation` keyed by ``SupportKey(core_n, seed)``.
    """
    prepared = _prepare_fit_inputs(plan_row, frozen, effective, cache_root, run_dir=run_dir)
    full_batch = prepared.scaled_validation.batch
    # The shared validation batch carries the true set size per row in ``batch.n``. Select
    # the rows whose set size equals this core_n -- this is the per-core-n validation subset
    # the shared model is scored on for the n_strategy comparison.
    n_values = full_batch.n
    selection = torch.nonzero(n_values == float(int(core_n)), as_tuple=False).flatten()
    if selection.numel() == 0:
        raise ValueError(
            f"shared validation batch for fit {fit_id!r} has no rows at core_n={core_n}"
        )
    sub_indices = selection.tolist()
    sub_metadata = tuple(prepared.validation_metadata[i] for i in sub_indices)
    sub_identity = _shared_core_n_validation_identity(prepared.validation_identity, core_n)
    support_key = SupportKey(n=int(core_n), seed=int(plan_row["seed"]))
    status = fit_states.get(fit_id)
    if status == "failed":
        illegal_records = tuple(
            {
                "sample_id": str(meta.get("sample_id", f"val:{i:07d}")),
                "seed_id": str(plan_row["seed"]),
                "point_id": str(meta.get("point_id", f"point-{i:07d}")),
                "legal": False, "failure": 1, "l_param": 10.0,
                "e_beta": 10.0, "e_eta": 10.0, "e_gamma": 10.0,
            }
            for i, meta in enumerate(sub_metadata)
        )
        return FitEvaluation(
            fit_id=fit_id, module_id=module_id, decision_id=decision_id, candidate_id=candidate_id,
            support_key=support_key, failed=True, checkpoint_sha256="",
            validation_identity=sub_identity,
            selection_score=0.0, failure_penalty=10.0, point_records=illegal_records,
        )
    if status != "succeeded":
        raise ValueError(
            f"n_strategy shared cohort requires fit {fit_id!r} terminal; its state is "
            f"{status!r}"
        )
    checkpoint_path = run_dir / "outputs" / fit_id / "checkpoint.pt"
    checkpoint_bytes = checkpoint_path.read_bytes()
    sub_batch = FormalSetBatch(
        values=full_batch.values.index_select(0, selection),
        mask=full_batch.mask.index_select(0, selection),
        n=full_batch.n.index_select(0, selection),
        model_n=full_batch.model_n.index_select(0, selection),
        targets=full_batch.targets.index_select(0, selection),
        location=full_batch.location.index_select(0, selection),
        scale=full_batch.scale.index_select(0, selection),
    )
    scalar, point_records = validation_failure_penalized_l_param_points(
        checkpoint_bytes=checkpoint_bytes, model_factory=prepared.model_factory,
        validation_batch=sub_batch, validation_metadata=sub_metadata,
        seed_id=str(plan_row["seed"]), is_set=True,
    )
    _require_finite_evaluation(fit_id, scalar, point_records)
    return FitEvaluation(
        fit_id=fit_id, module_id=module_id, decision_id=decision_id, candidate_id=candidate_id,
        support_key=support_key, failed=False,
        checkpoint_sha256=hashlib.sha256(checkpoint_bytes).hexdigest(),
        validation_identity=sub_identity,
        selection_score=scalar, failure_penalty=0.0, point_records=point_records,
    )


def _output_form_winner_candidate_from_trace(*, run_dir: Path, run_id: str) -> str:
    """Recover the output_form winner candidate id (``joint`` / ``independent_capacity_matched``).

    The output_form selection receipt is the on-disk authority (re-validated read-only via
    ``_recover_a_e3_output_form_selection``). The winner drives the fixed cohort's per-cell
    checkpoint selection (the 50 fits of the winning candidate).
    """
    record = _recover_a_e3_output_form_selection(run_dir=run_dir, run_id=run_id)
    return str(record["selected:A-E3_baseline"])


def _build_a_e3_n_strategy_fixed_evaluations(
    *, study_root: Path, run_dir: Path, cache_root: Path, frozen: FrozenConfig,
    effective: EffectiveFormalConfig, matrix_by_fit: Mapping[str, Mapping[str, str]],
    plan_by_fit: Mapping[str, Mapping[str, Any]], fit_states: Mapping[str, str],
    output_form_winner_candidate: str, predecessor_resolved_route: str,
    module_id: str, run_id: str,
    score_n_strategy_cell: Callable[[str, int, int, str], FitEvaluation] | None = None,
) -> dict[SupportKey, FitEvaluation]:
    """Build the fixed cohort's 50 per-cell evaluations (5 core n x 10 formal seeds).

    Each cell scores the output_form WINNING candidate's fit at (core_n, formal_seed) via
    the single-source ``_score_fit_from_checkpoint`` path. ``score_n_strategy_cell`` (tests)
    injects a synthetic evaluation without checkpoint scoring.
    """
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    output_form_rows = [
        row for row in matrix_rows
        if str(row["module"]) == "A-E3" and str(row["fit_kind"]) == "output_form"
    ]
    output_form_spec = next(
        (spec for spec in build_decision_specs("A-E3", output_form_rows)
         if spec.decision_id == _A_E3_OUTPUT_FORM_DECISION_ID),
        None,
    )
    if output_form_spec is None:
        raise ValueError(
            f"matrix has no A-E3 output_form decision {_A_E3_OUTPUT_FORM_DECISION_ID!r}")
    winner_candidate = next(
        (c for c in output_form_spec.candidates if c.candidate_id == output_form_winner_candidate),
        None,
    )
    if winner_candidate is None:
        raise ValueError(
            f"output_form winner candidate {output_form_winner_candidate!r} is not in the "
            f"output_form decision's candidate set")
    evaluations: dict[SupportKey, FitEvaluation] = {}
    for key in winner_candidate.support_keys:
        fit_id = winner_candidate.support_for(key)
        if score_n_strategy_cell is not None:
            evaluation = score_n_strategy_cell(fit_id, int(key.n), int(key.seed), _A_E3_N_STRATEGY_FIXED)
        else:
            scoring_row = _resolve_a_e3_scoring_plan_row(
                run_dir=run_dir, run_id=run_id, fit_id=fit_id,
                matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
                predecessor_resolved_route=predecessor_resolved_route)
            evaluation = _score_fit_from_checkpoint(
                run_dir=run_dir, cache_root=cache_root, fit_id=fit_id, plan_row=scoring_row,
                frozen=frozen, effective=effective, fit_states=fit_states,
                module_id=module_id, decision_id=_A_E3_N_STRATEGY_DECISION_ID,
                candidate_id=_A_E3_N_STRATEGY_FIXED,
            )
        if evaluation.support_key != key:
            raise ValueError(
                f"fixed-cohort evaluation for {fit_id!r} support {evaluation.support_key!r} "
                f"disagrees with frozen expected {key!r}")
        evaluations[key] = evaluation
    return evaluations


def _build_a_e3_n_strategy_shared_evaluations(
    *, study_root: Path, run_dir: Path, cache_root: Path, frozen: FrozenConfig,
    effective: EffectiveFormalConfig, matrix_by_fit: Mapping[str, Mapping[str, str]],
    plan_by_fit: Mapping[str, Mapping[str, Any]], fit_states: Mapping[str, str],
    predecessor_resolved_route: str, module_id: str, run_id: str,
    score_n_strategy_cell: Callable[[str, int, int, str], FitEvaluation] | None = None,
) -> dict[SupportKey, FitEvaluation]:
    """Build the shared cohort's 50 per-cell evaluations (10 shared x 5 core-n validations).

    Each of the 10 ``shared_winner_retrain`` checkpoints is scored on each of the 5 core-n
    validation subsets (sliced from the shared_n batch where ``batch.n == core_n``). The
    resulting support grid is 5 core n x 10 formal seeds -- identical to the fixed cohort's
    grid, so the two pair cell-for-cell under ``fixed_vs_shared_equal_weight``.

    R4-3: production scoring (``score_n_strategy_cell is None``) resolves each shared fit's
    plan row through ``_resolve_a_e3_scoring_plan_row`` BEFORE checkpoint scoring -- exactly
    like the fixed cohort. The resolver's ``shared_winner_retrain`` branch recovers the loss +
    S stage2 winner from the on-disk receipts (``_recover_a_e3_loss_selection`` +
    ``_recover_a_e3_stage2_selection`` -> ``_resolve_a_e3_shared_retrain_plan_row``), so the
    concrete route/loss/architecture/optimizer consumed by ``_prepare_fit_inputs`` /
    ``resolve_model_factory`` never carries a ``selected:S_*`` / ``selected:A-E3_loss``
    placeholder. A missing/tampered/stage-S receipt fails closed here rather than silently
    forwarding a placeholder to the model factory.
    """
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    shared_rows = [
        row for row in matrix_rows
        if str(row["module"]) == "A-E3" and str(row["fit_kind"]) == "shared_winner_retrain"
    ]
    if not shared_rows:
        raise ValueError("matrix has no A-E3 shared_winner_retrain rows")
    core_n_values = _a_e3_core_n_values(frozen)
    evaluations: dict[SupportKey, FitEvaluation] = {}
    for row in shared_rows:
        fit_id = str(row["fit_id"])
        formal_seed = int(row["seed"])
        for core_n in core_n_values:
            key = SupportKey(n=int(core_n), seed=formal_seed)
            if score_n_strategy_cell is not None:
                evaluation = score_n_strategy_cell(fit_id, int(core_n), formal_seed, _A_E3_N_STRATEGY_SHARED)
            else:
                scoring_row = _resolve_a_e3_scoring_plan_row(
                    run_dir=run_dir, run_id=run_id, fit_id=fit_id,
                    matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
                    predecessor_resolved_route=predecessor_resolved_route)
                evaluation = _score_shared_fit_on_core_n_subset(
                    run_dir=run_dir, cache_root=cache_root, fit_id=fit_id, plan_row=scoring_row,
                    frozen=frozen, effective=effective, fit_states=fit_states,
                    core_n=int(core_n), module_id=module_id,
                    decision_id=_A_E3_N_STRATEGY_DECISION_ID, candidate_id=_A_E3_N_STRATEGY_SHARED,
                )
            if evaluation.support_key != key:
                raise ValueError(
                    f"shared-cohort evaluation for {fit_id!r} support {evaluation.support_key!r} "
                    f"disagrees with frozen expected {key!r}")
            evaluations[key] = evaluation
    return evaluations


def _n_strategy_candidate_supporting_evidence(
    *, module_id: str, run_id: str, decision_id: str, candidate_id: str,
    selection_rule: str, support_keys: Sequence[SupportKey],
    evaluations_by_support: Mapping[SupportKey, FitEvaluation],
) -> dict[str, Any]:
    """Aggregate one n_strategy candidate's cohort evidence + supporting_evidence_sha256.

    Mirrors :func:`candidate_supporting_evidence` from selection.py but for the dedicated
    n_strategy structure (no ``CandidateSpec``; the support grid is the shared 5 core n x
    10 formal seeds). Uses :func:`_equal_weight_per_n_aggregate` for the aggregate score;
    binds each cell's ``point_evidence_sha256`` into the supporting hash so any swapped
    artifact, relabel, or tampered checkpoint/score/validation-subset fails closed.
    """
    if set(evaluations_by_support) != set(support_keys):
        missing = sorted(set(support_keys) - set(evaluations_by_support), key=lambda k: (str(k.n), k.seed))
        extra = sorted(set(evaluations_by_support) - set(support_keys), key=lambda k: (str(k.n), k.seed))
        raise ValueError(
            f"n_strategy evidence for {decision_id}/{candidate_id} must cover exactly the "
            f"support grid; missing={missing!r} extra={extra!r}")
    evaluations = [evaluations_by_support[key] for key in support_keys]
    for evaluation in evaluations:
        _validate_evaluation_finite(evaluation)
    aggregate = _equal_weight_per_n_aggregate(evaluations)
    if not math.isfinite(aggregate):
        raise ValueError(
            f"n_strategy aggregate score for {candidate_id!r} is non-finite ({aggregate})")
    supporting_rows: list[dict[str, Any]] = []
    for key, evaluation in zip(support_keys, evaluations):
        if evaluation.support_key != key:
            raise ValueError(
                f"n_strategy evaluation keyed by {evaluation.support_key!r} disagrees with "
                f"expected support {key!r}")
        point_sha = evaluation.point_evidence_sha256()
        supporting_rows.append({
            "fit_id": evaluation.fit_id, "n": key.n, "seed": int(key.seed),
            "failed": bool(evaluation.failed),
            "checkpoint_sha256": evaluation.checkpoint_sha256,
            "validation_identity": evaluation.validation_identity,
            "selection_score": float(evaluation.selection_score),
            "failure_penalty": float(evaluation.failure_penalty),
            "point_evidence_sha256": point_sha,
        })
    canonical_payload = _canonical({
        "module_id": module_id, "run_id": run_id, "decision_id": decision_id,
        "candidate_id": candidate_id, "selection_rule": selection_rule,
        "supporting_rows": supporting_rows,
    })
    return {
        "module_id": module_id, "run_id": run_id, "decision_id": decision_id,
        "candidate_id": candidate_id, "selection_rule": selection_rule,
        "supporting_rows": supporting_rows,
        "aggregate_score": aggregate,
        "supporting_evidence_sha256": hashlib.sha256(canonical_payload).hexdigest(),
        "support_count": len(supporting_rows),
        "seed_count": len({int(key.seed) for key in support_keys}),
    }


def _resolve_a_e3_n_strategy(
    *, study_root: Path, run_dir: Path, cache_root: Path, frozen: FrozenConfig,
    effective: EffectiveFormalConfig, matrix_by_fit: Mapping[str, Mapping[str, str]],
    plan_by_fit: Mapping[str, Mapping[str, Any]], fit_states: Mapping[str, str],
    output_form_winner_candidate: str, predecessor_resolved_route: str,
    module_id: str, run_id: str,
    score_n_strategy_cell: Callable[[str, int, int, str], FitEvaluation] | None = None,
) -> tuple[str, dict[str, dict[str, Any]], Mapping[str, Any]]:
    """Apply the frozen ``fixed_vs_shared_equal_weight`` rule to the n_strategy cohorts.

    Builds both cohorts' per-cell evaluations (5 core n x 10 formal seeds each), aggregates
    each under core-n equal-weight mean L_param, and ranks by aggregate ascending (the
    frozen rule). Returns ``(winner_candidate_id, evidence_by_candidate, rule_result)``.

    The winner is COMPUTED by the frozen rule over the dedicated cohort evidence, never
    supplied. ``rule_result`` carries the ranked order for the staged-ledger record (enough
    for pre-unseal to re-derive the winner). ``score_n_strategy_cell`` (tests) injects
    synthetic per-cell evaluations; production (None) scores from bound checkpoints.
    """
    fixed_evals = _build_a_e3_n_strategy_fixed_evaluations(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, frozen=frozen,
        effective=effective, matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
        fit_states=fit_states, output_form_winner_candidate=output_form_winner_candidate,
        predecessor_resolved_route=predecessor_resolved_route,
        module_id=module_id, run_id=run_id, score_n_strategy_cell=score_n_strategy_cell,
    )
    shared_evals = _build_a_e3_n_strategy_shared_evaluations(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, frozen=frozen,
        effective=effective, matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
        fit_states=fit_states, predecessor_resolved_route=predecessor_resolved_route,
        module_id=module_id, run_id=run_id,
        score_n_strategy_cell=score_n_strategy_cell,
    )
    # Both cohorts share the SAME 5 core n x 10 formal seeds support grid. Assert this so
    # a future matrix change that desynchronises the grids fails closed here (the
    # fixed_vs_shared rule is only defined for pairable support).
    if set(fixed_evals) != set(shared_evals):
        missing = sorted(set(fixed_evals) - set(shared_evals), key=lambda k: (str(k.n), k.seed))
        extra = sorted(set(shared_evals) - set(fixed_evals), key=lambda k: (str(k.n), k.seed))
        raise ValueError(
            f"n_strategy fixed/shared cohort support grids disagree; missing={missing!r} "
            f"extra={extra!r}")
    support_keys = tuple(sorted(fixed_evals, key=lambda k: (str(k.n), int(k.seed))))
    evidence_by_candidate: dict[str, dict[str, Any]] = {}
    for candidate_id, evaluations_by_support in (
        (_A_E3_N_STRATEGY_FIXED, fixed_evals),
        (_A_E3_N_STRATEGY_SHARED, shared_evals),
    ):
        evidence_by_candidate[candidate_id] = _n_strategy_candidate_supporting_evidence(
            module_id=module_id, run_id=run_id, decision_id=_A_E3_N_STRATEGY_DECISION_ID,
            candidate_id=candidate_id, selection_rule=SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT,
            support_keys=support_keys, evaluations_by_support=evaluations_by_support,
        )
    # Rank by aggregate score ascending, tie-break by candidate id (frozen deterministic).
    ranked = sorted(
        _A_E3_N_STRATEGY_CANDIDATES,
        key=lambda cid: (float(evidence_by_candidate[cid]["aggregate_score"]), cid),
    )
    winner = ranked[0]
    rule_result = {"reason": "fixed_vs_shared_equal_weight", "ranked": ranked}
    return winner, evidence_by_candidate, rule_result


def rebuild_a_e3_n_strategy_provenance(
    *, study_root: Path, run_dir: Path, cache_root: Path, module_id: str = "A-E3", run_id: str,
    score_n_strategy_cell: Callable[[str, int, int, str], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """R3-B pre-unseal: independently rebuild the n_strategy winner from bound checkpoints.

    Mirrors :func:`rebuild_selection_point_provenance` for the dedicated n_strategy decision.
    Reloads the output_form winner candidate from its on-disk receipt, re-scores the fixed
    cohort (50 output_form winner checkpoints on their fixed-n validation cells) and the
    shared cohort (10 shared_winner_retrain checkpoints x 5 core-n validation subsets) from
    ``outputs/{fit_id}/checkpoint.pt``, re-aggregates both under
    ``fixed_vs_shared_equal_weight``, and recomputes the winner + supporting evidence SHAs.

    No fit_status scalar, no published artifact, no staged-ledger record is trusted -- the
    returned map is the independently reconstructed truth pre-unseal compares the published
    n_strategy record against. Fail-closed if any expected fit is not terminal, any
    checkpoint is missing, or any scoring non-finite.

    ``score_n_strategy_cell`` (tests) injects synthetic per-cell evaluations without
    checkpoint scoring; when it is supplied the scheduler-authority rebuild is skipped
    (fit_states are unused under injection). Production (``None``) scores from bound
    checkpoints via the full ``_rebuild_authority`` path.
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id=module_id)
    if score_n_strategy_cell is None:
        fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
    else:
        # Under per-cell injection the scheduler fit_states are never consulted (each
        # evaluation comes from the injection); skip the authority rebuild so tests do not
        # require a sealed scheduler fixture. Production never takes this branch.
        fit_states = {}
    predecessor_resolved_route = _a_e3_resolved_baseline_route_from_manifest(run_dir)
    output_form_winner_candidate = _output_form_winner_candidate_from_trace(
        run_dir=run_dir, run_id=run_id)
    winner, evidence_by_candidate, rule_result = _resolve_a_e3_n_strategy(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, frozen=frozen,
        effective=effective, matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
        fit_states=fit_states, output_form_winner_candidate=output_form_winner_candidate,
        predecessor_resolved_route=predecessor_resolved_route,
        module_id=module_id, run_id=run_id, score_n_strategy_cell=score_n_strategy_cell,
    )
    return {
        "module_id": module_id, "run_id": run_id,
        "decision_id": _A_E3_N_STRATEGY_DECISION_ID,
        "winner": winner,
        "evidence_by_candidate": evidence_by_candidate,
        "rule_result": dict(rule_result),
    }


def resolve_a_e3_staged_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path,
    module_id: str = "A-E3", run_id: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
    predecessor: Mapping[str, Any] | PredecessorTrace | None = None,
    score_n_strategy_cell: Callable[[str, int, int, str], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Production staged A-E3 resolver (D8/C4 + R3-B n_strategy).

    Derives every frozen A-E3 placeholder from the validated module selection trace +
    the A-E1 predecessor binding through an immutable, hash-bound, append-only staged
    ledger (``run_dir/staged_resolution_ledger.jsonl``). The caller supplies only the run
    authority (``run_dir``) + frozen matrix; every placeholder is DERIVED from validated
    evidence, never passed.

    The 10-record canonical chain binds:
      1. ``loss``              -> ``selected:A-E3_loss`` (loss-screen winner from the trace).
      2. ``stage1:F2_or_V``    -> F2_or_V ``selected_top_1..4`` (architecture ranking).
      3. ``stage2:F2_or_V``    -> ``selected:A-E3_{architecture,optimizer}`` (stage2 winner).
      4. ``stage1:S``          -> S ``selected_top_1..4``.
      5. ``stage2:S``          -> ``selected:S_{architecture,optimizer}``.
      6. ``output_form``       -> ``selected:A-E3_baseline`` (joint vs independent winner).
      7. ``shared_winner_retrain:S`` -> aliases (``selected:A-E3_loss`` + ``selected:S_*``).
      8. ``baseline_route``    -> ``selected:F2_or_V`` = predecessor's resolved baseline route
         (``V`` for the r5 design). Its input cryptographically binds the A-E1 predecessor's
         ``selection_staged_ledger_sha256`` so A-E3 cannot rest on a swapped predecessor ledger.
      9. ``n_strategy``        -> ``selected:A-E3_n_strategy`` in {fixed, shared}. R3-B: a
         dedicated decision (OUTSIDE the matrix ``build_decision_specs`` path) over the fixed
         cohort (output_form winner checkpoints, 5 core n x 10 formal seeds) vs the shared
         cohort (shared_winner_retrain checkpoints, 10 x 5 core-n validation subsets), under
         the frozen ``fixed_vs_shared_equal_weight`` rule (core-n equal-weight aggregate).
      10. ``final_aliases``    -> the concrete baseline tuple consumed by A-E2 (route / loss /
         architecture / optimizer / output_form) chosen by the n_strategy winner, plus
         ``selected:A-E3_n_strategy`` and the flat aliases for back-compat.

    Every record's ``selection_trace_sha256`` binds the A-E3 final selection trace; the chain
    threads ``previous_record_sha256`` from ``_ZERO_HASH``. The ledger is append-only and
    crash-recoverable (mirrors A-E1): a recovery rerun recomputes each stage, reuses records
    whose resolution matches, and fails closed on a conflicting duplicate. No real fit is
    launched; no test role is opened (``test_access_count`` stays 0). ``score_fit`` /
    ``predecessor`` are accepted for API symmetry; the authority is the validated final trace +
    the run manifest's predecessor section (bound at materialize time). ``score_n_strategy_cell``
    (tests) injects synthetic per-cell n_strategy evaluations.
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    if module_id != "A-E3":
        raise NotImplementedError(
            f"staged resolution of module {module_id!r} is not implemented; only A-E3"
        )
    pending_all = ["loss", "stage1", "stage2", "output_form",
                   "shared_winner_retrain", "baseline_route", "n_strategy", "final_aliases"]
    if not (run_dir / "selection_trace.jsonl").exists():
        return {
            "module_id": module_id, "run_id": run_id,
            "staged_ledger_path": str(_staged_ledger_path(run_dir)),
            "selection_trace_sha256": None, "top4_by_token": {}, "stage2_by_token": {},
            "selected_F2_or_V": None, "selected_baseline": None, "final_aliases": None,
            "record_sha256": {}, "pending": pending_all,
        }
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    code_commit = str(manifest["code_commit"])
    predecessor_section = manifest["predecessor"]
    predecessor_staged_ledger_sha = str(predecessor_section["selection_staged_ledger_sha256"])
    predecessor_resolved_route = str(predecessor_section["resolved_baseline_route"])
    _require(
        predecessor_resolved_route in {"F2", "V"},
        f"manifest predecessor resolved_baseline_route must be 'F2' or 'V' "
        f"(got {predecessor_resolved_route!r})")
    receipt = json.loads((run_dir / "selection_receipt.json").read_text(encoding="utf-8"))
    trace_sha = str(receipt["selection_trace_sha256"])
    trace_records = _validate_selection_evidence(
        selection_trace_path=run_dir / "selection_trace.jsonl",
        selection_trace_sha256=trace_sha,
        selection_receipt_path=run_dir / "selection_receipt.json",
        selection_ledger_path=run_dir / "selection_ledger.jsonl",
        module_id=module_id, run_id=run_id,
    )
    by_decision: dict[str, list[dict[str, Any]]] = {}
    for record in trace_records:
        by_decision.setdefault(record["decision_id"], []).append(record)

    def _require_decision(decision_id: str) -> None:
        _require(
            decision_id in by_decision,
            f"A-E3 selection trace is missing the decision {decision_id!r}")

    def _winner(decision_id: str) -> dict[str, Any]:
        records = by_decision[decision_id]
        winner = next((r for r in records if r["selected"]), None)
        _require(winner is not None, f"decision {decision_id!r} has no selected winner")
        return winner

    def _ranking(decision_id: str) -> list[dict[str, Any]]:
        return sorted(
            by_decision[decision_id],
            key=lambda r: (float(r["validation_score"]), _tie_break_sort_key(r["tie_break_key"]),
                           str(r["candidate_id"])))

    # ``selection_trace_sha256`` (bound on every record) and ``previous_record_sha256`` (chained
    # from _ZERO_HASH) are filled in by the _publish closure below. Idempotent reuse inside
    # ``_append_stage_record`` walks the existing records in the same deterministic order, so a
    # recovery rerun never reorders or re-chains an already-published ledger.
    previous_sha = _ZERO_HASH
    record_shas: dict[str, str] = {}
    top4_by_token: dict[str, dict[str, str]] = {}
    stage2_by_token: dict[str, dict[str, str]] = {}
    stage_record_shas: dict[str, str] = {}

    def _publish(stage: str, route: str | None, input_payload: Mapping[str, Any],
                 resolution: Mapping[str, Any]) -> dict[str, Any]:
        nonlocal previous_sha
        record = _build_stage_record(
            module_id=module_id, run_id=run_id, code_commit=code_commit,
            effective_config_sha256=effective.effective_config_sha256,
            selection_trace_sha256=trace_sha, stage=stage, route=route,
            previous_record_sha256=previous_sha, input_payload=input_payload, resolution=resolution,
        )
        published = _append_stage_record(run_dir, record)
        previous_sha = published["record_sha256"]
        key = f"{stage}:{route if route else ''}"
        record_shas[key] = published["record_sha256"]
        stage_record_shas[key] = published["record_sha256"]
        return published

    # --- (1) loss -> selected:A-E3_loss ----------------------------------------
    _require_decision(_A_E3_LOSS_DECISION_ID)
    loss_winner = _winner(_A_E3_LOSS_DECISION_ID)
    loss_id = str(loss_winner["candidate_id"])
    loss_resolution = {"selected:A-E3_loss": loss_id}
    loss_input = {
        "decision_id": _A_E3_LOSS_DECISION_ID,
        "winner_candidate_id": loss_id,
        "winner_supporting_evidence_sha256": str(loss_winner["supporting_evidence_sha256"]),
    }
    loss_record = _publish("loss", None, loss_input, loss_resolution)

    # --- (2-5) per-token stage1 (top4) + stage2 (winner) -----------------------
    for token in (_A_E3_FV_TOKEN, _A_E3_S_TOKEN):
        stage1_dec = _a_e3_stage1_decision_id(token)
        stage2_dec = _a_e3_stage2_decision_id(token)
        _require_decision(stage1_dec)
        _require_decision(stage2_dec)
        # Derive the token's top4 from the validated trace (same partial-trace discipline as
        # the per-token stage1 builder; the staged ledger binds the FINAL trace, not the
        # per-token partial receipts, but the rankings agree because both come from the same
        # frozen matrix + scored fits).
        stage1_records = _ranking(stage1_dec)
        top4 = {
            f"selected_top_{slot}": str(stage1_records[slot - 1]["candidate_id"])
            for slot in range(1, min(5, len(stage1_records) + 1))
        }
        _require(
            len(top4) == 4,
            f"A-E3 stage1 decision {stage1_dec!r} must select exactly 4 architectures "
            f"(got {len(top4)})")
        top4_by_token[token] = top4
        stage1_input = {
            "decision_id": stage1_dec,
            "ranking": [
                {"candidate_id": str(r["candidate_id"]),
                 "validation_score": float(r["validation_score"]),
                 "selected": bool(r["selected"]),
                 "supporting_evidence_sha256": str(r["supporting_evidence_sha256"])}
                for r in stage1_records
            ],
        }
        stage1_record = _publish("stage1", token, stage1_input, top4)

        stage2_winner = _winner(stage2_dec)
        arch_placeholder, optimizer = _parse_stage2_winner_candidate(
            str(stage2_winner["candidate_id"]))
        _require(
            arch_placeholder in top4,
            f"A-E3 stage2 winner slot {arch_placeholder!r} is outside the {token!r} top4")
        architecture = top4[arch_placeholder]
        arch_key, opt_key = _a_e3_stage2_winner_keys(token)
        winner_resolution = {arch_key: architecture, opt_key: optimizer}
        stage2_by_token[token] = winner_resolution
        stage2_input = {
            "decision_id": stage2_dec,
            "winner_candidate_id": str(stage2_winner["candidate_id"]),
            "winner_supporting_evidence_sha256": str(
                stage2_winner["supporting_evidence_sha256"]),
            "stage1_record_sha256": stage1_record["record_sha256"],
            "resolved_top_slot": arch_placeholder,
        }
        _publish("stage2", token, stage2_input, winner_resolution)

    # --- (6) output_form -> selected:A-E3_baseline -----------------------------
    _require_decision(_A_E3_OUTPUT_FORM_DECISION_ID)
    output_form_winner = _winner(_A_E3_OUTPUT_FORM_DECISION_ID)
    baseline_alias = str(output_form_winner["candidate_id"])
    output_form_resolution = {"selected:A-E3_baseline": baseline_alias}
    output_form_input = {
        "decision_id": _A_E3_OUTPUT_FORM_DECISION_ID,
        "winner_candidate_id": baseline_alias,
        "winner_supporting_evidence_sha256": str(
            output_form_winner["supporting_evidence_sha256"]),
    }
    output_form_record = _publish("output_form", None, output_form_input, output_form_resolution)

    # --- (7) shared_winner_retrain:S -> aliases (loss + S stage2 winner) -------
    arch_key_s, opt_key_s = _a_e3_stage2_winner_keys(_A_E3_S_TOKEN)
    s_winner = stage2_by_token[_A_E3_S_TOKEN]
    shared_resolution = {
        "selected:A-E3_loss": loss_id,
        arch_key_s: s_winner[arch_key_s],
        opt_key_s: s_winner[opt_key_s],
    }
    shared_input = {
        "loss_record_sha256": loss_record["record_sha256"],
        "stage2_S_record_sha256": stage_record_shas[f"stage2:{_A_E3_S_TOKEN}"],
        "placeholder_fields": [
            "selected:A-E3_loss", arch_key_s, opt_key_s],
    }
    _publish("shared_winner_retrain", _A_E3_S_TOKEN, shared_input, shared_resolution)

    # --- (8) baseline_route -> selected:F2_or_V = predecessor resolved route ---
    # Cryptographically binds the A-E1 predecessor's staged-ledger SHA: an A-E3 run cannot
    # rest on a swapped A-E1 staged ledger because this record's input carries the verified
    # SHA from the run manifest (validated at materialize time).
    baseline_resolution = {"selected:F2_or_V": predecessor_resolved_route}
    baseline_input = {
        "predecessor_module_id": str(predecessor_section["module_id"]),
        "predecessor_run_id": str(predecessor_section["run_id"]),
        "predecessor_selection_trace_sha256": str(
            predecessor_section["selection_trace_sha256"]),
        "predecessor_staged_ledger_sha256": predecessor_staged_ledger_sha,
        "predecessor_resolved_baseline_route": predecessor_resolved_route,
    }
    baseline_record = _publish("baseline_route", None, baseline_input, baseline_resolution)

    # --- (9) n_strategy -> selected:A-E3_n_strategy ----------------------------
    # R3-B: dedicated n_strategy decision (fixed vs shared). Constructed OUTSIDE the matrix
    # build_decision_specs path (no fit_kind -> n_strategy mapping; reproducer #2 stays
    # negative). Two cohorts share the 5 core n x 10 formal seeds support grid:
    #   * fixed  = output_form winner candidate's 50 checkpoints, scored on their fixed-n
    #     validation cells (re-uses the single-source _score_fit_from_checkpoint path).
    #   * shared = 10 shared_winner_retrain checkpoints x 5 core-n validation subsets
    #     (each shared DeepSets checkpoint scored on each core-n slice of the shared_n
    #     validation batch where batch.n == core_n).
    # Aggregated under the frozen fixed_vs_shared_equal_weight rule (core-n equal-weight
    # mean failure-penalized L_param). Failed fits carry the penalty + all-illegal records
    # (R3#6: never skipped). The winner is COMPUTED by the rule, never supplied; the input
    # binds both cohorts' supporting_evidence_sha256 + the rule_result + the prerequisite
    # record SHAs so pre-unseal can re-derive the winner independently.
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id=module_id)
    fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
    n_strategy_winner, n_strategy_evidence, n_strategy_rule_result = _resolve_a_e3_n_strategy(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, frozen=frozen,
        effective=effective, matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
        fit_states=fit_states,
        output_form_winner_candidate=baseline_alias,
        predecessor_resolved_route=predecessor_resolved_route,
        module_id=module_id, run_id=run_id, score_n_strategy_cell=score_n_strategy_cell,
    )
    n_strategy_resolution = {"selected:A-E3_n_strategy": n_strategy_winner}
    n_strategy_input = {
        "decision_id": _A_E3_N_STRATEGY_DECISION_ID,
        "selection_rule": SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT,
        "candidate_supporting_evidence_sha256": {
            candidate_id: n_strategy_evidence[candidate_id]["supporting_evidence_sha256"]
            for candidate_id in _A_E3_N_STRATEGY_CANDIDATES
        },
        "candidate_aggregate_scores": {
            candidate_id: float(n_strategy_evidence[candidate_id]["aggregate_score"])
            for candidate_id in _A_E3_N_STRATEGY_CANDIDATES
        },
        "rule_result": dict(n_strategy_rule_result),
        "output_form_record_sha256": output_form_record["record_sha256"],
        "baseline_route_record_sha256": baseline_record["record_sha256"],
        "shared_winner_retrain_record_sha256": stage_record_shas[f"shared_winner_retrain:{_A_E3_S_TOKEN}"],
        "fixed_cohort_support_count": int(n_strategy_evidence[_A_E3_N_STRATEGY_FIXED]["support_count"]),
        "shared_cohort_support_count": int(n_strategy_evidence[_A_E3_N_STRATEGY_SHARED]["support_count"]),
    }
    n_strategy_record = _publish("n_strategy", None, n_strategy_input, n_strategy_resolution)

    # --- (10) final_aliases -> concrete baseline tuple + n_strategy ------------
    # R3-B: final_aliases carries a CONCRETE baseline tuple directly consumable by A-E2
    # (route / loss / architecture / optimizer / output_form), chosen by the n_strategy
    # winner. The original token-namespaced aliases (F2_or_V arch/opt + S arch/opt) are
    # preserved unchanged so downstream code reading them is unaffected. The concrete tuple
    # under ``selected:A-E3_baseline`` is the authority A-E2 consumes.
    arch_key_fv, opt_key_fv = _a_e3_stage2_winner_keys(_A_E3_FV_TOKEN)
    fv_winner = stage2_by_token[_A_E3_FV_TOKEN]
    if n_strategy_winner == _A_E3_N_STRATEGY_FIXED:
        baseline_tuple = {
            "route": predecessor_resolved_route,
            "loss": loss_id,
            "architecture": fv_winner[arch_key_fv],
            "optimizer": fv_winner[opt_key_fv],
            "output_form": baseline_alias,
        }
    elif n_strategy_winner == _A_E3_N_STRATEGY_SHARED:
        baseline_tuple = {
            "route": _A_E3_S_TOKEN,
            "loss": loss_id,
            "architecture": s_winner[arch_key_s],
            "optimizer": s_winner[opt_key_s],
            "output_form": "N/A",  # DeepSets has no joint/independent output_form
        }
    else:  # pragma: no cover - defensive (_resolve_a_e3_n_strategy returns only fixed/shared)
        raise ValueError(f"n_strategy winner {n_strategy_winner!r} is not fixed/shared")
    final_aliases = {
        "selected:A-E3_n_strategy": n_strategy_winner,
        "selected:A-E3_baseline": baseline_tuple,
        "selected:A-E3_loss": loss_id,
        arch_key_fv: fv_winner[arch_key_fv],
        opt_key_fv: fv_winner[opt_key_fv],
        arch_key_s: s_winner[arch_key_s],
        opt_key_s: s_winner[opt_key_s],
        "selected:F2_or_V": predecessor_resolved_route,
    }
    final_input = {
        "n_strategy_record_sha256": n_strategy_record["record_sha256"],
        "baseline_route_record_sha256": baseline_record["record_sha256"],
        "loss_record_sha256": loss_record["record_sha256"],
        "stage2_F2_or_V_record_sha256": stage_record_shas[f"stage2:{_A_E3_FV_TOKEN}"],
        "stage2_S_record_sha256": stage_record_shas[f"stage2:{_A_E3_S_TOKEN}"],
        "output_form_record_sha256": output_form_record["record_sha256"],
        "n_strategy_winner": n_strategy_winner,
        "baseline_tuple": dict(baseline_tuple),
    }
    _publish("final_aliases", None, final_input, final_aliases)

    return {
        "module_id": module_id, "run_id": run_id,
        "staged_ledger_path": str(_staged_ledger_path(run_dir)),
        "selection_trace_sha256": trace_sha,
        "top4_by_token": top4_by_token,
        "stage2_by_token": stage2_by_token,
        "selected_F2_or_V": predecessor_resolved_route,
        "selected_baseline": baseline_alias,
        "selected_n_strategy": n_strategy_winner,
        "final_aliases": final_aliases,
        "n_strategy_evidence": n_strategy_evidence,
        "record_sha256": record_shas,
        "pending": [],
    }


def _authoritative_matrix_by_fit(study_root: Path) -> dict[str, dict[str, str]]:
    """The single authoritative ``fit_id`` -> frozen matrix row map for staged execution.

    ``fit_kind`` / ``module`` / ``n`` live ONLY in the frozen matrix; ``plan.jsonl`` deliberately
    renames those fields and carries just the runtime training metadata. The matrix is
    ``expand_module_matrix`` over the frozen config, which ``_matrix_snapshot`` proves is
    byte-identical to the SHA-256-verified ``experiment_matrix.csv`` (so it is the same frozen
    authority the scheduler hashed into each plan row's ``matrix_row_sha256``). Rows are stringified
    exactly as the scheduler does, so the per-row hash correspondence check uses one canonical form.
    Fail-closed on a duplicate ``fit_id`` (the matrix must key uniquely).
    """
    frozen = load_frozen_config(study_root)
    rows = [{key: str(value) for key, value in row.items()}
            for row in expand_module_matrix(frozen).to_dict("records")]
    by_fit: dict[str, dict[str, str]] = {}
    for row in rows:
        fit_id = str(row["fit_id"])
        if fit_id in by_fit:
            raise ValueError(f"frozen matrix has a duplicate fit_id {fit_id!r}")
        by_fit[fit_id] = row
    return by_fit


def _validate_plan_against_matrix(
    *, plan_rows: Sequence[Mapping[str, Any]], matrix_by_fit: Mapping[str, Mapping[str, str]],
    module_id: str,
) -> dict[str, Mapping[str, Any]]:
    """Fail-closed correspondence between one module's ``plan.jsonl`` and the authoritative matrix.

    The plan's ``fit_id`` set must correspond EXACTLY to the module's matrix rows (no missing,
    duplicate or extra fit), and every plan row's ``matrix_row_sha256`` must equal
    ``sha256(canonical(authoritative matrix row))`` -- binding each plan row to its frozen matrix
    row (which carries ``fit_kind``). Returns ``plan_by_fit``; raises on any mismatch (stale plan,
    matrix tamper, or a plan that drifted from the frozen matrix). This is the single gate a staged
    run passes before classifying any fit's stage from the matrix.
    """
    plan_by_fit: dict[str, Mapping[str, Any]] = {}
    for row in plan_rows:
        fit_id = str(row["fit_id"])
        if fit_id in plan_by_fit:
            raise ValueError(f"plan.jsonl has a duplicate fit_id {fit_id!r}")
        plan_by_fit[fit_id] = row
    plan_fits = set(plan_by_fit)
    matrix_fits = {fid for fid, row in matrix_by_fit.items() if str(row["module"]) == module_id}
    missing = sorted(matrix_fits - plan_fits)
    extra = sorted(plan_fits - matrix_fits)
    if missing or extra:
        raise ValueError(
            f"plan.jsonl fit_id set does not match the {module_id} matrix rows: "
            f"missing={missing} extra={extra}")
    for fit_id, row in plan_by_fit.items():
        matrix_row = matrix_by_fit[fit_id]
        expected = hashlib.sha256(_canonical(matrix_row)).hexdigest()
        bound = str(row["matrix_row_sha256"])
        if bound != expected:
            raise ValueError(
                f"plan row {fit_id!r} binds matrix_row_sha256 {bound!r} but the authoritative "
                f"matrix row hashes to {expected!r} (stale plan or matrix tamper)")
    return plan_by_fit


def _a_e1_fit_stage(matrix_row: Mapping[str, Any]) -> str:
    """Classify an A-E1 fit into its staged-execution stage from its AUTHORITATIVE matrix row.

    ``fit_kind`` lives in the frozen matrix (never in ``plan.jsonl``, which renames it); the caller
    passes the fit's matrix row (looked up by ``fit_id`` from ``_authoritative_matrix_by_fit``).
    ``stage2`` / ``winner_retrain`` rows carry placeholders and need a prior-stage receipt to
    concretize before execution; everything else (historical / controlled / ``search_stage1``
    architecture rows) is directly executable."""
    kind = str(matrix_row["fit_kind"])
    if kind == "search_stage2":
        return "stage2"
    if kind == "winner_retrain":
        return "winner_retrain"
    return "concrete"


# ---------------------------------------------------------------------------
# A-E3 staged-execution classifier + scoring plan-row resolver (C2).
# Mirrors the A-E1 patterns (_a_e1_fit_stage / _resolve_a_e1_scoring_plan_row)
# with one key structural difference: A-E3's route is a PLACEHOLDER
# (``selected:F2_or_V``) that resolves to the A-E1 predecessor's verified
# baseline route (V), NOT to a within-A-E3 stage receipt. The predecessor
# binding (C1) exposes ``resolved_baseline_route`` on the manifest, so the
# resolver resolves the route placeholder from the predecessor evidence
# before any placeholder reaches the runner.
# ---------------------------------------------------------------------------

# Safe per-stage receipt tokens (section A.1). The matrix routes
# ``selected:F2_or_V`` / ``selected:F2_or_V:{output_form}`` and ``S`` contain
# characters that are unsafe as Windows filename segments; these tokens strip
# the ``selected:`` prefix from the route stem.
_A_E3_FV_TOKEN = "F2_or_V"
_A_E3_S_TOKEN = "S"
# The matrix placeholder stem that ``_validate_predecessor`` resolves to V/F2.
_A_E3_BASELINE_PLACEHOLDER = "selected:F2_or_V"


def _a_e3_fit_stage(matrix_row: Mapping[str, Any]) -> str:
    """Classify an A-E3 fit into its staged-execution stage from its AUTHORITATIVE matrix row.

    Mirrors :func:`_a_e1_fit_stage` but classifies A-E3 ``fit_kind`` values into four stages.
    ``fit_kind`` lives in the frozen matrix (never in ``plan.jsonl``); the caller passes the
    fit's matrix row (looked up by ``fit_id`` from :func:`_authoritative_matrix_by_fit`).
    The route is NOT used to classify -- the F2_or_V placeholder route is resolved from the
    A-E1 predecessor (not from a within-A-E3 stage), so only ``fit_kind`` determines the stage.

    Returns one of ``concrete`` / ``stage2`` / ``output_form`` / ``shared_winner_retrain``:
      * ``loss_screen`` / ``search_stage1`` (concrete arch/opt/loss) -> ``concrete``
      * ``search_stage2`` (arch = ``selected_top_N``) -> ``stage2``
      * ``output_form`` (loss/arch/opt all ``selected:A-E3_*``) -> ``output_form``
      * ``shared_winner_retrain`` (``selected:S_*`` + ``selected:A-E3_loss``) -> ``shared_winner_retrain``
    """
    kind = str(matrix_row["fit_kind"])
    if kind == "search_stage2":
        return "stage2"
    if kind == "output_form":
        return "output_form"
    if kind == "shared_winner_retrain":
        return "shared_winner_retrain"
    return "concrete"


def _a_e3_route_token(matrix_route: str) -> str:
    """Derive the safe per-stage receipt token from an A-E3 matrix route stem.

    ``selected:F2_or_V`` / ``selected:F2_or_V:{suffix}`` -> ``F2_or_V``; ``S`` -> ``S``.
    Used to build/recover per-route stage receipts (section A.1 token scheme).
    """
    route = str(matrix_route)
    if route == _A_E3_S_TOKEN:
        return _A_E3_S_TOKEN
    if route == _A_E3_BASELINE_PLACEHOLDER or route.startswith(_A_E3_BASELINE_PLACEHOLDER + ":"):
        return _A_E3_FV_TOKEN
    raise ValueError(f"unknown A-E3 matrix route stem: {route!r}")


def _a_e3_resolve_scoring_route(route_placeholder: str, predecessor_resolved_route: str) -> str:
    """Resolve an A-E3 route placeholder to its concrete scoring-row value.

    ``selected:F2_or_V`` -> ``predecessor_resolved_route`` (V); ``selected:F2_or_V:{suffix}``
    -> ``predecessor_resolved_route:{suffix}`` (suffix preserved for the scoring row, Flag K.1);
    ``S`` -> ``S``. The scoring row route is what the runner reads for the ``is_set`` check.
    """
    route = str(route_placeholder)
    if route == _A_E3_S_TOKEN:
        return _A_E3_S_TOKEN
    if route == _A_E3_BASELINE_PLACEHOLDER:
        return str(predecessor_resolved_route)
    if route.startswith(_A_E3_BASELINE_PLACEHOLDER + ":"):
        suffix = route[len(_A_E3_BASELINE_PLACEHOLDER):]  # includes the leading ':'
        return str(predecessor_resolved_route) + suffix
    raise ValueError(f"unknown A-E3 route placeholder: {route!r}")


def _a_e3_resolved_route_stem(route_placeholder: str, predecessor_resolved_route: str) -> str:
    """Resolve the concrete route STEM (V/F2 or S) for FormalDatasetSpec construction.

    Mirrors :func:`_a_e3_resolve_scoring_route` but strips the ``:output_form`` suffix so the
    concrete dataset spec reuses the A-E1 V-route (or S-route) cache entry (Flag K.1: the
    output_form suffix affects only the model head, not the dataset bytes).
    """
    route = str(route_placeholder)
    if route == _A_E3_S_TOKEN:
        return _A_E3_S_TOKEN
    if route == _A_E3_BASELINE_PLACEHOLDER or route.startswith(_A_E3_BASELINE_PLACEHOLDER + ":"):
        return str(predecessor_resolved_route)
    raise ValueError(f"unknown A-E3 route placeholder: {route!r}")


def build_a_e1_stage1_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path,
    module_id: str = "A-E1", run_id: str, route: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Per-route stage-1 selection receipt (top4) from ONE route's stage-1 architecture fits ONLY.

    The frozen A-E1 plan order is route-interleaved (all of F2's stages run before V's), so a
    route's stage-1 fits are terminal before that route's stage-2 fits are reached -- but NOT
    before the OTHER route's. Receipts are therefore per-route: this publishes an immutable
    PARTIAL selection trace + receipt + ledger over the one route's architecture decision and
    derives its ``selected_top_1..4`` (rank-1..4 architectures). It does NOT require stage-2 /
    winner-retrain / other-route evidence (the deadlock-free staged authority). Production scores
    from checkpoints; tests inject ``score_fit``. No training; no test read.
    """
    _require(route in _A_E1_OPTIMIZED_ROUTES, f"staged A-E1 route must be one of {_A_E1_OPTIMIZED_ROUTES}")
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = {str(row["fit_id"]): row for row in plan_rows}
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    stage1_rows = [
        row for row in matrix_rows if str(row["module"]) == "A-E1"
        and str(row["fit_kind"]) == "search_stage1" and str(row["route"]) == route]
    specs = tuple(build_decision_specs("A-E1", stage1_rows))
    expected = {_a_e1_stage1_decision_id(route)}
    _require(
        {spec.decision_id for spec in specs} == expected,
        f"stage1 selection scope must be exactly the {route!r} architecture decision")
    fit_states: Mapping[str, str] = {}
    if score_fit is None:
        fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
    evaluations: dict[str, FitEvaluation] = {}
    for spec in specs:
        for candidate in spec.candidates:
            for key in candidate.support_keys:
                fit_id = candidate.support_for(key)
                plan_row = plan_by_fit[fit_id]
                if score_fit is not None:
                    evaluation = score_fit(fit_id, plan_row)
                else:
                    _require(
                        fit_states.get(fit_id) == "succeeded",
                        f"stage1 selection requires every {route} stage1 fit terminal; {fit_id!r} is not succeeded")
                    evaluation = _score_fit_from_checkpoint(
                        run_dir=run_dir, cache_root=cache_root, fit_id=fit_id, plan_row=plan_row,
                        frozen=frozen, effective=effective, fit_states=fit_states,
                        module_id="A-E1", decision_id=spec.decision_id, candidate_id=candidate.candidate_id)
                evaluations[fit_id] = evaluation
    records, _diagnostics = build_selection_trace(
        module_id="A-E1", run_id=run_id, specs=specs, evaluations_by_fit=evaluations)
    trace_path = run_dir / f"stage1_selection_{route}_trace.jsonl"
    trace_sha = write_selection_trace(trace_path, records)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    receipt = publish_selection_receipt(
        receipt_path=run_dir / f"stage1_selection_{route}_receipt.json",
        ledger_path=run_dir / f"stage1_selection_{route}_ledger.jsonl",
        module_id="A-E1", run_id=run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=effective, code_commit=manifest["code_commit"])
    top4 = resolve_selected_placeholders(
        placeholders={f"selected_top_{slot}": _a_e1_stage1_decision_id(route) for slot in range(1, 5)},
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=run_dir / f"stage1_selection_{route}_receipt.json",
        selection_ledger_path=run_dir / f"stage1_selection_{route}_ledger.jsonl",
        module_id="A-E1", run_id=run_id)
    return {
        "module_id": "A-E1", "run_id": run_id, "route": route,
        "selection_trace_sha256": trace_sha, "top4": top4, **receipt,
    }


def build_a_e1_stage2_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path,
    module_id: str = "A-E1", run_id: str, route: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Per-route stage-2 selection receipt (winner architecture/optimizer/loss) from ONE route's
    stage-2 fits ONLY. Maps the route's stage-2 winner (``selected_top_{slot}:{opt}``) to the
    concrete architecture (the route's verified stage1 top4[slot]), optimizer, and frozen loss --
    the authority that route's winner-retrain placeholders resolve against.

    Scoring reads the route's stage1 top4 from its OWN on-disk verified receipt
    (``_recover_a_e1_stage1_selection``); the caller never supplies top4. Each scored fit's plan
    row is resolved from that verified authority before checkpoint scoring, so no placeholder
    reaches ``resolve_model_factory``.
    """
    _require(route in _A_E1_OPTIMIZED_ROUTES, f"staged A-E1 route must be one of {_A_E1_OPTIMIZED_ROUTES}")
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E1")
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    stage2_rows = [
        row for row in matrix_rows if str(row["module"]) == "A-E1"
        and str(row["fit_kind"]) == "search_stage2" and str(row["route"]) == route]
    specs = tuple(build_decision_specs("A-E1", stage2_rows))
    expected = {_a_e1_stage2_decision_id(route)}
    _require(
        {spec.decision_id for spec in specs} == expected,
        f"stage2 selection scope must be exactly the {route!r} stage2 decision")
    fit_states: Mapping[str, str] = {}
    if score_fit is None:
        fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
    evaluations: dict[str, FitEvaluation] = {}
    for spec in specs:
        for candidate in spec.candidates:
            for key in candidate.support_keys:
                fit_id = candidate.support_for(key)
                if score_fit is not None:
                    evaluation = score_fit(fit_id, plan_by_fit[fit_id])
                else:
                    _require(
                        fit_states.get(fit_id) == "succeeded",
                        f"stage2 selection requires every {route} stage2 fit terminal; {fit_id!r} is not succeeded")
                    resolved_row = _resolve_a_e1_scoring_plan_row(
                        run_dir=run_dir, run_id=run_id, fit_id=fit_id,
                        matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit)
                    evaluation = _score_fit_from_checkpoint(
                        run_dir=run_dir, cache_root=cache_root, fit_id=fit_id, plan_row=resolved_row,
                        frozen=frozen, effective=effective, fit_states=fit_states,
                        module_id="A-E1", decision_id=spec.decision_id, candidate_id=candidate.candidate_id)
                evaluations[fit_id] = evaluation
    records, _diagnostics = build_selection_trace(
        module_id="A-E1", run_id=run_id, specs=specs, evaluations_by_fit=evaluations)
    trace_path = run_dir / f"stage2_selection_{route}_trace.jsonl"
    trace_sha = write_selection_trace(trace_path, records)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    receipt = publish_selection_receipt(
        receipt_path=run_dir / f"stage2_selection_{route}_receipt.json",
        ledger_path=run_dir / f"stage2_selection_{route}_ledger.jsonl",
        module_id="A-E1", run_id=run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=effective, code_commit=manifest["code_commit"])
    decision_id = _a_e1_stage2_decision_id(route)
    winner = next((r for r in records if r["decision_id"] == decision_id and r["selected"]), None)
    _require(winner is not None, f"stage2 decision {decision_id!r} has no selected winner")
    arch_placeholder, optimizer = _parse_stage2_winner_candidate(str(winner["candidate_id"]))
    top4 = _recover_a_e1_stage1_selection(run_dir=run_dir, run_id=run_id, route=route)["top4"]
    _require(
        arch_placeholder in top4,
        f"stage2 winner slot {arch_placeholder!r} is outside the stage1 top4 for route {route!r}")
    winner_spec = {
        "selected:A-E1_loss": _A_E1_STAGE2_FROZEN_LOSS,
        "selected:A-E1_architecture": top4[arch_placeholder],
        "selected:A-E1_optimizer": optimizer,
    }
    return {
        "module_id": "A-E1", "run_id": run_id, "route": route,
        "selection_trace_sha256": trace_sha, "winner": winner_spec, **receipt,
    }


def _resolve_stage2_plan_row(plan_row: Mapping[str, Any], top4: Mapping[str, str]) -> dict[str, Any]:
    """Concretize a stage2 plan row's ``selected_top_N`` architecture from the route's stage1 top4."""
    arch = str(plan_row["architecture"])
    _require(arch in top4, f"stage2 architecture placeholder {arch!r} is not in the stage1 top4")
    return {**plan_row, "architecture": top4[arch]}


def _resolve_winner_retrain_plan_row(plan_row: Mapping[str, Any], winner: Mapping[str, str]) -> dict[str, Any]:
    """Concretize a winner-retrain plan row's selected:A-E1_* placeholders from the route's stage2 winner."""
    return {
        **plan_row,
        "architecture": winner["selected:A-E1_architecture"],
        "optimizer": winner["selected:A-E1_optimizer"],
        "loss": winner["selected:A-E1_loss"],
    }


def _resolve_a_e3_output_form_plan_row(
    plan_row: Mapping[str, Any], resolved_route: str,
    loss_resolution: Mapping[str, str], fv_stage2_winner: Mapping[str, str],
) -> dict[str, Any]:
    """Concretize an A-E3 output_form plan row from the loss + F2_or_V stage2 + predecessor route.

    Thin dict merge in the style of :func:`_resolve_stage2_plan_row` /
    :func:`_resolve_winner_retrain_plan_row`. ``loss_resolution`` carries
    ``selected:A-E3_loss``; ``fv_stage2_winner`` carries ``selected:A-E3_architecture`` /
    ``selected:A-E3_optimizer`` (both from the F2_or_V stage2 receipt). The route is the
    resolved scoring route (V or V:{output_form}).
    """
    return {
        **plan_row,
        "route": resolved_route,
        "loss": loss_resolution["selected:A-E3_loss"],
        "architecture": fv_stage2_winner["selected:A-E3_architecture"],
        "optimizer": fv_stage2_winner["selected:A-E3_optimizer"],
    }


def _resolve_a_e3_shared_retrain_plan_row(
    plan_row: Mapping[str, Any], resolved_route: str,
    loss_resolution: Mapping[str, str], s_stage2_winner: Mapping[str, str],
) -> dict[str, Any]:
    """Concretize an A-E3 shared_winner_retrain plan row from the loss + S stage2 winner.

    The S route is concrete (``S``), so ``resolved_route`` is always ``S`` for this branch.
    ``loss_resolution`` carries ``selected:A-E3_loss``; ``s_stage2_winner`` carries
    ``selected:S_architecture`` / ``selected:S_optimizer``.
    """
    return {
        **plan_row,
        "route": resolved_route,
        "loss": loss_resolution["selected:A-E3_loss"],
        "architecture": s_stage2_winner["selected:S_architecture"],
        "optimizer": s_stage2_winner["selected:S_optimizer"],
    }


def _resolve_a_e1_scoring_plan_row(
    *, run_dir: Path, run_id: str, fit_id: str,
    matrix_by_fit: Mapping[str, Mapping[str, str]],
    plan_by_fit: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Resolve an A-E1 plan row's staged placeholders from on-disk verified evidence BEFORE
    checkpoint scoring.

    The plan row is read ONLY from ``plan_by_fit[fit_id]`` (the plan the caller already validated
    against the frozen matrix); callers cannot supply a second copy of the scientific fields. Each
    fit self-proves its plan<->matrix SHA binding and route, then classifies by the authoritative
    matrix ``fit_kind``:
      concrete        -> plan row unchanged
      stage2          -> recover the route's verified stage1 top4 -> _resolve_stage2_plan_row
      winner_retrain  -> recover stage1 top4 + stage2 winner -> _resolve_winner_retrain_plan_row
    Reads ONLY ``run_dir/stage{1,2}_selection_{route}_*`` via the fail-closed ``_recover_a_e1_*``
    helpers (no in-process cache, no publish). Fails closed on a missing/tampered/out-of-scope/
    cross-route receipt, an unbound plan<->matrix row, or a winner slot outside the recovered top4.
    """
    fit_id = str(fit_id)
    if fit_id not in plan_by_fit:
        raise ValueError(f"_resolve_a_e1_scoring_plan_row: fit_id {fit_id!r} is not in the validated plan")
    if fit_id not in matrix_by_fit:
        raise ValueError(f"_resolve_a_e1_scoring_plan_row: fit_id {fit_id!r} is not in the authoritative matrix")
    plan_row = dict(plan_by_fit[fit_id])
    matrix_row = matrix_by_fit[fit_id]
    _require(
        hashlib.sha256(_canonical(matrix_row)).hexdigest() == str(plan_row["matrix_row_sha256"]),
        f"plan row {fit_id!r} matrix_row_sha256 does not bind the authoritative matrix row")
    route = str(matrix_row["route"])
    _require(
        str(plan_row.get("route")) == route,
        f"plan row {fit_id!r} route {plan_row.get('route')!r} disagrees with matrix route {route!r}")
    stage = _a_e1_fit_stage(matrix_row)
    if stage == "concrete":
        return plan_row
    stage1 = _recover_a_e1_stage1_selection(run_dir=run_dir, run_id=run_id, route=route)
    if stage == "stage2":
        return _resolve_stage2_plan_row(plan_row, stage1["top4"])
    winner = _recover_a_e1_stage2_selection(
        run_dir=run_dir, run_id=run_id, route=route, top4=stage1["top4"])["winner"]
    return _resolve_winner_retrain_plan_row(plan_row, winner)


def _stage_evidence_paths(run_dir: Path, stage: str, route: str) -> tuple[Path, Path, Path]:
    """ ``(trace, receipt, ledger)`` paths for one per-route staged selection receipt."""
    return (
        run_dir / f"{stage}_selection_{route}_trace.jsonl",
        run_dir / f"{stage}_selection_{route}_receipt.json",
        run_dir / f"{stage}_selection_{route}_ledger.jsonl",
    )


def _recover_a_e1_stage1_selection(*, run_dir: Path, run_id: str, route: str) -> dict[str, Any]:
    """Recover a route's stage1 ``top4`` from its EXISTING immutable trace/receipt/ledger.

    Read-only and fail-closed: validates the trace hash, receipt-trace binding and ledger binding
    (``_validate_selection_evidence``), checks the decision scope is exactly the route's stage1
    architecture decision (binding the receipt to the frozen matrix), and re-derives ``top4`` from
    the validated ranking. No scoring, no re-publish, no overwrite -- the receipt is the authority a
    restart recovers from. Raises if any artifact is missing/tampered/out-of-scope.
    """
    trace_path, receipt_path, ledger_path = _stage_evidence_paths(run_dir, "stage1", route)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    trace_sha = str(receipt["selection_trace_sha256"])
    records = _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E1", run_id=run_id,
    )
    decision_id = _a_e1_stage1_decision_id(route)
    _require(
        {str(record["decision_id"]) for record in records} == {decision_id},
        f"stage1 receipt for route {route!r} is out of scope: expected decision {decision_id!r}")
    top4 = resolve_selected_placeholders(
        placeholders={f"selected_top_{slot}": decision_id for slot in range(1, 5)},
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E1", run_id=run_id,
    )
    return {"module_id": "A-E1", "run_id": run_id, "route": route,
            "selection_trace_sha256": trace_sha, "top4": top4, **dict(receipt)}


def _recover_a_e1_stage2_selection(
    *, run_dir: Path, run_id: str, route: str, top4: Mapping[str, str],
) -> dict[str, Any]:
    """Recover a route's stage2 ``winner`` from its EXISTING immutable trace/receipt/ledger.

    Like ``_recover_a_e1_stage1_selection`` for the stage2 decision, then maps the validated winner
    (``selected_top_{slot}:{opt}``) to the concrete architecture (``top4[slot]``) plus the frozen
    stage2 loss. ``top4`` is the route's recovered stage1 top4 (itself derived from a validated
    receipt, never supplied by the orchestrator's caller). Fail-closed on a missing/tampered/
    out-of-scope receipt or a winner slot outside the recovered stage1 top4.
    """
    trace_path, receipt_path, ledger_path = _stage_evidence_paths(run_dir, "stage2", route)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    trace_sha = str(receipt["selection_trace_sha256"])
    records = _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E1", run_id=run_id,
    )
    decision_id = _a_e1_stage2_decision_id(route)
    _require(
        {str(record["decision_id"]) for record in records} == {decision_id},
        f"stage2 receipt for route {route!r} is out of scope: expected decision {decision_id!r}")
    winner_record = next(
        (record for record in records
         if record["decision_id"] == decision_id and record["selected"]),
        None,
    )
    _require(winner_record is not None, f"stage2 decision {decision_id!r} has no selected winner")
    arch_placeholder, optimizer = _parse_stage2_winner_candidate(str(winner_record["candidate_id"]))
    _require(
        arch_placeholder in top4,
        f"stage2 winner slot {arch_placeholder!r} is outside the recovered stage1 top4 for "
        f"route {route!r}")
    winner = {
        "selected:A-E1_loss": _A_E1_STAGE2_FROZEN_LOSS,
        "selected:A-E1_architecture": top4[arch_placeholder],
        "selected:A-E1_optimizer": optimizer,
    }
    return {"module_id": "A-E1", "run_id": run_id, "route": route,
            "selection_trace_sha256": trace_sha, "winner": winner, **dict(receipt)}


def _ensure_a_e1_stage1_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path, run_id: str, route: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
) -> dict[str, Any]:
    """Ensure the route's stage1 selection receipt exists and return its ``top4``.

    Crash-recoverable: if the receipt already exists (a prior pass or a restart after this stage was
    reached) it is RE-VALIDATED and its ``top4`` recovered (no re-scoring, no re-publish, no
    overwrite); otherwise it is published from the route's terminal stage1 architecture fits. The
    caller never supplies ``top4`` -- it is always derived from a validated receipt.
    """
    _require(route in _A_E1_OPTIMIZED_ROUTES, f"staged A-E1 route must be one of {_A_E1_OPTIMIZED_ROUTES}")
    receipt_path = run_dir / f"stage1_selection_{route}_receipt.json"
    if receipt_path.exists():
        return _recover_a_e1_stage1_selection(run_dir=run_dir, run_id=run_id, route=route)
    return build_a_e1_stage1_selection(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        route=route, score_fit=score_fit)


def _ensure_a_e1_stage2_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path, run_id: str, route: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
    stage1_by_route: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Ensure the route's stage2 selection receipt exists and return its ``winner``.

    Crash-recoverable like ``_ensure_a_e1_stage1_selection``. The route's stage1 ``top4`` is ensured
    first (recovered or built) so the stage2 winner slot can be validated against it; the winner is
    then recovered (if the stage2 receipt exists) or built. No caller-supplied winner/top4.
    ``stage1_by_route`` is the orchestrator's within-pass cache; a recovered stage1 top4 is stored
    back into it so a later winner-retrain fit for the same route does not re-derive it.
    """
    _require(route in _A_E1_OPTIMIZED_ROUTES, f"staged A-E1 route must be one of {_A_E1_OPTIMIZED_ROUTES}")
    if route not in stage1_by_route:
        stage1_by_route[route] = _ensure_a_e1_stage1_selection(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
            route=route, score_fit=score_fit)
    top4 = stage1_by_route[route]["top4"]
    receipt_path = run_dir / f"stage2_selection_{route}_receipt.json"
    if receipt_path.exists():
        return _recover_a_e1_stage2_selection(run_dir=run_dir, run_id=run_id, route=route, top4=top4)
    return build_a_e1_stage2_selection(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        route=route, score_fit=score_fit)


def _ensure_a_e1_final_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path, run_id: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
) -> dict[str, Any]:
    """Ensure the module's final selection trace/receipt/ledger exists; idempotent on restart.

    If the final receipt already exists it is RE-VALIDATED read-only (no re-publish, no overwrite);
    otherwise it is published from the terminal selection fits via ``build_module_selection``.
    Repeated calls after completion are idempotent (validate-only).
    """
    receipt_path = run_dir / "selection_receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        trace_sha = str(receipt["selection_trace_sha256"])
        _validate_selection_evidence(
            selection_trace_path=run_dir / "selection_trace.jsonl",
            selection_trace_sha256=trace_sha,
            selection_receipt_path=receipt_path,
            selection_ledger_path=run_dir / "selection_ledger.jsonl",
            module_id="A-E1", run_id=run_id,
        )
        return {"module_id": "A-E1", "run_id": run_id, "reused": True,
                "selection_trace_sha256": trace_sha}
    return build_module_selection(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, module_id="A-E1",
        run_id=run_id, score_fit=score_fit)


# ---------------------------------------------------------------------------
# A-E3 staged-selection recovery (per-token stage1/stage2 + global loss/output_form).
#
# Mirrors ``_recover_a_e1_stage{1,2}_selection`` but keyed by the A-E3 route token
# (``F2_or_V`` / ``S``) for stage1/stage2 and token-less (global) for the single loss /
# output_form decisions. The recover helpers are read-only and fail-closed: they
# re-validate the immutable trace/receipt/ledger and assert the decision scope before
# deriving any placeholder. C3 replaces the C2 ``NotImplementedError`` stubs.
# ---------------------------------------------------------------------------

# Frozen A-E3 stage parameters (from the authoritative matrix).
_A_E3_FV_SEARCH_N = 10                 # F2_or_V search_stage1/stage2 use core n=10
_A_E3_S_N_PART = "shared"              # S route uses shared-n DeepSets
_A_E3_LOSS_DECISION_ID = f"loss:A-E3:{_A_E3_BASELINE_PLACEHOLDER}:n{_A_E3_FV_SEARCH_N}"
_A_E3_OUTPUT_FORM_DECISION_ID = f"output_form:A-E3:{_A_E3_BASELINE_PLACEHOLDER}"

# R3-B: dedicated n_strategy decision (fixed vs shared). This decision_id is NOT derived
# from the frozen matrix ``build_decision_specs`` path (the matrix's ``fit_kind`` axis does
# not map ``shared_winner_retrain`` to ``n_strategy`` -- reproducer #2 stays negative). It
# is a dedicated evidence structure constructed from the output-form winner checkpoints
# (fixed cohort) and the shared_winner_retrain checkpoints (shared cohort), aggregated under
# the frozen ``fixed_vs_shared_equal_weight`` rule. The two candidates share the SAME 5 core
# n x 10 formal seeds support grid (50 cells each), so the equal-weight-per-n aggregation
# pairs them cell-for-cell.
_A_E3_N_STRATEGY_DECISION_ID = "n_strategy:A-E3:F2_or_V_vs_S"
_A_E3_N_STRATEGY_FIXED = "fixed"
_A_E3_N_STRATEGY_SHARED = "shared"
_A_E3_N_STRATEGY_CANDIDATES = (_A_E3_N_STRATEGY_FIXED, _A_E3_N_STRATEGY_SHARED)


def _a_e3_route_for_token(token: str) -> str:
    """Map an A-E3 stage token to its matrix route stem (``F2_or_V`` -> placeholder)."""
    if token == _A_E3_FV_TOKEN:
        return _A_E3_BASELINE_PLACEHOLDER
    if token == _A_E3_S_TOKEN:
        return _A_E3_S_TOKEN
    raise ValueError(f"unknown A-E3 stage token: {token!r}")


def _a_e3_stage1_decision_id(token: str) -> str:
    """The single architecture decision id recovered/built by an A-E3 stage1 receipt."""
    if token == _A_E3_FV_TOKEN:
        return f"architecture:A-E3:{_A_E3_BASELINE_PLACEHOLDER}:n{_A_E3_FV_SEARCH_N}"
    if token == _A_E3_S_TOKEN:
        return f"architecture:A-E3:{_A_E3_S_TOKEN}:{_A_E3_S_N_PART}"
    raise ValueError(f"unknown A-E3 stage1 token: {token!r}")


def _a_e3_stage2_decision_id(token: str) -> str:
    """The single stage2 decision id recovered/built by an A-E3 stage2 receipt."""
    if token == _A_E3_FV_TOKEN:
        return f"stage2:A-E3:{_A_E3_BASELINE_PLACEHOLDER}:n{_A_E3_FV_SEARCH_N}"
    if token == _A_E3_S_TOKEN:
        return f"stage2:A-E3:{_A_E3_S_TOKEN}:{_A_E3_S_N_PART}"
    raise ValueError(f"unknown A-E3 stage2 token: {token!r}")


def _a_e3_stage2_winner_keys(token: str) -> tuple[str, str]:
    """The ``(arch_key, opt_key)`` placeholders a stage2 winner carries, namespaced by token.

    ``F2_or_V`` -> ``selected:A-E3_architecture`` / ``selected:A-E3_optimizer`` (the A-E3
    baseline aliases consumed by output_form fits); ``S`` -> ``selected:S_architecture`` /
    ``selected:S_optimizer`` (the S-route aliases consumed by shared_winner_retrain fits).
    """
    if token == _A_E3_FV_TOKEN:
        return "selected:A-E3_architecture", "selected:A-E3_optimizer"
    if token == _A_E3_S_TOKEN:
        return "selected:S_architecture", "selected:S_optimizer"
    raise ValueError(f"unknown A-E3 stage2 token: {token!r}")


def _a_e3_stage_evidence_paths(
    run_dir: Path, stage: str, token: str | None,
) -> tuple[Path, Path, Path]:
    """``(trace, receipt, ledger)`` paths for one A-E3 staged selection receipt.

    Per-token stages (``stage1`` / ``stage2``) carry the token in the filename, mirroring
    :func:`_stage_evidence_paths` for A-E1; the global loss / output_form stages omit it
    (one receipt each, no route namespace).
    """
    if token is None:
        return (
            run_dir / f"{stage}_selection_trace.jsonl",
            run_dir / f"{stage}_selection_receipt.json",
            run_dir / f"{stage}_selection_ledger.jsonl",
        )
    return (
        run_dir / f"{stage}_selection_{token}_trace.jsonl",
        run_dir / f"{stage}_selection_{token}_receipt.json",
        run_dir / f"{stage}_selection_{token}_ledger.jsonl",
    )


def _recover_a_e3_stage1_selection(*, run_dir: Path, run_id: str, token: str) -> dict[str, Any]:
    """Recover an A-E3 route token's stage1 ``top4`` from its EXISTING immutable receipt.

    Read-only and fail-closed (mirrors :func:`_recover_a_e1_stage1_selection`): validates the
    trace hash, receipt-trace binding and ledger binding (``_validate_selection_evidence``),
    checks the decision scope is exactly the token's architecture decision, and re-derives
    ``top4`` from the validated ranking. No scoring, no re-publish, no overwrite -- the
    receipt is the authority a restart recovers from. Raises if any artifact is missing,
    tampered or out-of-scope.
    """
    trace_path, receipt_path, ledger_path = _a_e3_stage_evidence_paths(run_dir, "stage1", token)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    trace_sha = str(receipt["selection_trace_sha256"])
    records = _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id,
    )
    decision_id = _a_e3_stage1_decision_id(token)
    _require(
        {str(record["decision_id"]) for record in records} == {decision_id},
        f"A-E3 stage1 receipt for token {token!r} is out of scope: expected decision {decision_id!r}")
    top4 = resolve_selected_placeholders(
        placeholders={f"selected_top_{slot}": decision_id for slot in range(1, 5)},
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id,
    )
    return {"module_id": "A-E3", "run_id": run_id, "token": token,
            "selection_trace_sha256": trace_sha, "top4": top4, **dict(receipt)}


def _recover_a_e3_stage2_selection(
    *, run_dir: Path, run_id: str, token: str, top4: Mapping[str, str],
) -> dict[str, Any]:
    """Recover an A-E3 route token's stage2 ``winner`` from its EXISTING immutable receipt.

    Mirrors :func:`_recover_a_e1_stage2_selection`: validates the receipt, finds the selected
    winner, maps its ``selected_top_{slot}:{opt}`` candidate to the concrete architecture
    (``top4[slot]``) plus optimizer, and namespaces the placeholders by token (``A-E3`` for
    ``F2_or_V``; ``S`` for ``S``). ``top4`` is the token's recovered stage1 top4 (itself
    derived from a validated receipt, never caller-supplied). Fail-closed on missing,
    tampered, out-of-scope evidence or a winner slot outside the recovered top4.
    """
    trace_path, receipt_path, ledger_path = _a_e3_stage_evidence_paths(run_dir, "stage2", token)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    trace_sha = str(receipt["selection_trace_sha256"])
    records = _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id,
    )
    decision_id = _a_e3_stage2_decision_id(token)
    _require(
        {str(record["decision_id"]) for record in records} == {decision_id},
        f"A-E3 stage2 receipt for token {token!r} is out of scope: expected decision {decision_id!r}")
    winner_record = next(
        (record for record in records
         if record["decision_id"] == decision_id and record["selected"]),
        None,
    )
    _require(winner_record is not None, f"A-E3 stage2 decision {decision_id!r} has no selected winner")
    arch_placeholder, optimizer = _parse_stage2_winner_candidate(str(winner_record["candidate_id"]))
    _require(
        arch_placeholder in top4,
        f"A-E3 stage2 winner slot {arch_placeholder!r} is outside the recovered stage1 top4 "
        f"for token {token!r}")
    arch_key, opt_key = _a_e3_stage2_winner_keys(token)
    winner = {arch_key: top4[arch_placeholder], opt_key: optimizer}
    return {"module_id": "A-E3", "run_id": run_id, "token": token,
            "selection_trace_sha256": trace_sha, "winner": winner, **dict(receipt)}


def _recover_a_e3_loss_selection(*, run_dir: Path, run_id: str) -> dict[str, Any]:
    """Recover the global A-E3 ``selected:A-E3_loss`` from the loss selection receipt.

    The loss decision is global (no route token): the frozen matrix has a single
    ``loss:A-E3:selected:F2_or_V:n10`` decision over the 4 loss-screen candidates
    (``lowest_aggregate``), and its winner is the A-E3-wide loss id that every downstream
    output_form / shared_winner_retrain fit resolves against. Read-only + fail-closed like
    the stage1/stage2 recovers.
    """
    trace_path, receipt_path, ledger_path = _a_e3_stage_evidence_paths(run_dir, "loss", None)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    trace_sha = str(receipt["selection_trace_sha256"])
    records = _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id,
    )
    _require(
        {str(record["decision_id"]) for record in records} == {_A_E3_LOSS_DECISION_ID},
        f"A-E3 loss receipt is out of scope: expected decision {_A_E3_LOSS_DECISION_ID!r}")
    winner_record = next(
        (record for record in records
         if record["decision_id"] == _A_E3_LOSS_DECISION_ID and record["selected"]),
        None,
    )
    _require(winner_record is not None, "A-E3 loss decision has no selected winner")
    return {"module_id": "A-E3", "run_id": run_id,
            "selection_trace_sha256": trace_sha,
            "selected:A-E3_loss": str(winner_record["candidate_id"]), **dict(receipt)}


def _recover_a_e3_output_form_selection(*, run_dir: Path, run_id: str) -> dict[str, Any]:
    """Recover the global A-E3 ``selected:A-E3_baseline`` from the output_form receipt.

    The output_form decision is global (no route token): the frozen matrix has a single
    ``output_form:A-E3:selected:F2_or_V`` decision over the ``joint`` /
    ``independent_capacity_matched`` candidates (``fixed_vs_shared_equal_weight``), and its
    winner is the A-E3 baseline output form (the ``selected:A-E3_baseline`` alias).
    Read-only + fail-closed.
    """
    trace_path, receipt_path, ledger_path = _a_e3_stage_evidence_paths(run_dir, "output_form", None)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    trace_sha = str(receipt["selection_trace_sha256"])
    records = _validate_selection_evidence(
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id,
    )
    _require(
        {str(record["decision_id"]) for record in records} == {_A_E3_OUTPUT_FORM_DECISION_ID},
        f"A-E3 output_form receipt is out of scope: expected decision {_A_E3_OUTPUT_FORM_DECISION_ID!r}")
    winner_record = next(
        (record for record in records
         if record["decision_id"] == _A_E3_OUTPUT_FORM_DECISION_ID and record["selected"]),
        None,
    )
    _require(winner_record is not None, "A-E3 output_form decision has no selected winner")
    return {"module_id": "A-E3", "run_id": run_id,
            "selection_trace_sha256": trace_sha,
            "selected:A-E3_baseline": str(winner_record["candidate_id"]), **dict(receipt)}


def _resolve_a_e3_scoring_plan_row(
    *, run_dir: Path, run_id: str, fit_id: str,
    matrix_by_fit: Mapping[str, Mapping[str, str]],
    plan_by_fit: Mapping[str, Mapping[str, Any]],
    predecessor_resolved_route: str,
) -> dict[str, Any]:
    """Resolve an A-E3 plan row's staged placeholders + route BEFORE checkpoint scoring.

    Mirrors :func:`_resolve_a_e1_scoring_plan_row` for the A-E3 module. The plan row is read
    ONLY from ``plan_by_fit[fit_id]`` (the plan the caller already validated against the frozen
    matrix); callers cannot supply a second copy of the scientific fields. Each fit self-proves
    its plan<->matrix SHA binding and route, then:

    * ALWAYS resolves the route placeholder (``selected:F2_or_V`` -> ``predecessor_resolved_route``
      preserving any ``:output_form`` suffix; ``S`` -> ``S``).
    * Branches on the authoritative matrix ``fit_kind`` (via :func:`_a_e3_fit_stage`):
      - concrete        -> row with resolved route only (no other fields change).
      - stage2          -> recover the route token's stage1 top4 -> ``_resolve_stage2_plan_row``.
      - output_form     -> recover loss + F2_or_V stage2 winner -> ``_resolve_a_e3_output_form_plan_row``.
      - shared_winner_retrain -> recover loss + S stage2 winner -> ``_resolve_a_e3_shared_retrain_plan_row``.

    The stage2 / output_form / shared_winner_retrain branches call the ``_recover_a_e3_*``
    readers, each re-validating its own immutable trace/receipt/ledger before deriving any
    placeholder.

    Fails closed on: a fit_id absent from the validated plan or matrix, an unbound
    plan<->matrix row SHA, a route that disagrees with the matrix, an unknown route placeholder,
    or a missing/tampered/out-of-scope stage receipt.
    """
    fit_id = str(fit_id)
    if fit_id not in plan_by_fit:
        raise ValueError(f"_resolve_a_e3_scoring_plan_row: fit_id {fit_id!r} is not in the validated plan")
    if fit_id not in matrix_by_fit:
        raise ValueError(f"_resolve_a_e3_scoring_plan_row: fit_id {fit_id!r} is not in the authoritative matrix")
    plan_row = dict(plan_by_fit[fit_id])
    matrix_row = matrix_by_fit[fit_id]
    _require(
        hashlib.sha256(_canonical(matrix_row)).hexdigest() == str(plan_row["matrix_row_sha256"]),
        f"plan row {fit_id!r} matrix_row_sha256 does not bind the authoritative matrix row")
    matrix_route = str(matrix_row["route"])
    _require(
        str(plan_row.get("route")) == matrix_route,
        f"plan row {fit_id!r} route {plan_row.get('route')!r} disagrees with matrix route {matrix_route!r}")
    resolved_route = _a_e3_resolve_scoring_route(matrix_route, predecessor_resolved_route)
    resolved_row = {**plan_row, "route": resolved_route}
    stage = _a_e3_fit_stage(matrix_row)
    if stage == "concrete":
        return resolved_row
    # The non-concrete branches recover on-disk verified evidence via the C3 readers;
    # each fails closed (missing/tampered/out-of-scope receipt) so no placeholder can
    # reach resolve_model_factory.
    if stage == "stage2":
        token = _a_e3_route_token(matrix_route)
        top4 = _recover_a_e3_stage1_selection(run_dir=run_dir, run_id=run_id, token=token)["top4"]
        return _resolve_stage2_plan_row(resolved_row, top4)
    if stage == "output_form":
        loss_resolution = _recover_a_e3_loss_selection(run_dir=run_dir, run_id=run_id)
        fv_token = _a_e3_route_token(matrix_route)
        fv_stage1 = _recover_a_e3_stage1_selection(run_dir=run_dir, run_id=run_id, token=fv_token)
        fv_stage2 = _recover_a_e3_stage2_selection(
            run_dir=run_dir, run_id=run_id, token=fv_token, top4=fv_stage1["top4"])
        return _resolve_a_e3_output_form_plan_row(
            resolved_row, resolved_route, loss_resolution, fv_stage2["winner"])
    if stage == "shared_winner_retrain":
        loss_resolution = _recover_a_e3_loss_selection(run_dir=run_dir, run_id=run_id)
        s_stage1 = _recover_a_e3_stage1_selection(run_dir=run_dir, run_id=run_id, token=_A_E3_S_TOKEN)
        s_stage2 = _recover_a_e3_stage2_selection(
            run_dir=run_dir, run_id=run_id, token=_A_E3_S_TOKEN, top4=s_stage1["top4"])
        return _resolve_a_e3_shared_retrain_plan_row(
            resolved_row, resolved_route, loss_resolution, s_stage2["winner"])
    raise ValueError(f"unknown A-E3 fit stage {stage!r} for fit {fit_id!r}")


# ---------------------------------------------------------------------------
# A-E3 staged-selection builders (per-token stage1/stage2 + global loss/output_form).
#
# Mirror ``build_a_e1_stage{1,2}_selection``: each publishes an immutable PARTIAL selection
# trace + receipt + ledger over its stage's decision(s), derives its placeholders from the
# validated ranking, and reuses the A-E1 plan-row resolver helpers (``_resolve_stage2_plan_row``)
# so the scoring row a fit's checkpoint is scored against never carries a placeholder. The
# global loss/output_form builders score every fit through ``_resolve_a_e3_scoring_plan_row``
# (which itself recovers the prerequisite receipts), so production scoring only ever sees a
# fully-concrete row. Production scores from checkpoints; tests inject ``score_fit``.
# ---------------------------------------------------------------------------


def _a_e3_score_stage_candidates(
    *, specs: Sequence[DecisionSpec], plan_by_fit: Mapping[str, Mapping[str, Any]],
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
    run_dir: Path, cache_root: Path, run_id: str,
    matrix_by_fit: Mapping[str, Mapping[str, str]], frozen: FrozenConfig,
    effective: EffectiveFormalConfig, fit_states: Mapping[str, str],
    resolved_route: str, label: str,
) -> dict[str, FitEvaluation]:
    """Shared scoring loop for every A-E3 staged-selection builder.

    Production (``score_fit is None``) resolves each fit's scoring row via
    ``_resolve_a_e3_scoring_plan_row`` -- which recovers any prerequisite receipts from disk --
    before checkpoint scoring, so no placeholder reaches ``_score_fit_from_checkpoint``. Tests
    inject ``score_fit`` to stand in for checkpoint scoring. Each fit must be terminal
    (``succeeded``) on the production path.
    """
    evaluations: dict[str, FitEvaluation] = {}
    for spec in specs:
        for candidate in spec.candidates:
            for key in candidate.support_keys:
                fit_id = candidate.support_for(key)
                plan_row = plan_by_fit[fit_id]
                if score_fit is not None:
                    evaluation = score_fit(fit_id, plan_row)
                else:
                    _require(
                        fit_states.get(fit_id) == "succeeded",
                        f"{label} requires every fit terminal; {fit_id!r} is not succeeded")
                    scoring_row = _resolve_a_e3_scoring_plan_row(
                        run_dir=run_dir, run_id=run_id, fit_id=fit_id,
                        matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
                        predecessor_resolved_route=resolved_route)
                    evaluation = _score_fit_from_checkpoint(
                        run_dir=run_dir, cache_root=cache_root, fit_id=fit_id, plan_row=scoring_row,
                        frozen=frozen, effective=effective, fit_states=fit_states,
                        module_id="A-E3", decision_id=spec.decision_id, candidate_id=candidate.candidate_id)
                evaluations[fit_id] = evaluation
    return evaluations


def build_a_e3_stage1_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path,
    module_id: str = "A-E3", run_id: str, token: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Per-token A-E3 stage-1 selection receipt (top4) from ONE token's stage-1 architecture fits.

    Mirrors :func:`build_a_e1_stage1_selection` for A-E3. The frozen matrix partitions A-E3
    stage-1 architecture fits by route stem (``selected:F2_or_V`` core-n MLP; ``S`` shared-n
    DeepSets); each token's stage-1 fits are terminal before that token's stage-2 fits are
    reached, so receipts are per-token. Publishes an immutable PARTIAL selection trace +
    receipt + ledger over the one token's architecture decision and derives its
    ``selected_top_1..4`` (rank-1..4 architectures). It does NOT require stage-2 /
    output_form / other-token evidence (the deadlock-free staged authority). Production scores
    from checkpoints; tests inject ``score_fit``. No training; no test read.
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    route_stem = _a_e3_route_for_token(token)
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    stage1_rows = [
        row for row in matrix_rows if str(row["module"]) == "A-E3"
        and str(row["fit_kind"]) == "search_stage1" and str(row["route"]) == route_stem]
    specs = tuple(build_decision_specs("A-E3", stage1_rows))
    expected = {_a_e3_stage1_decision_id(token)}
    _require(
        {spec.decision_id for spec in specs} == expected,
        f"A-E3 stage1 selection scope must be exactly the {token!r} architecture decision")
    fit_states: Mapping[str, str] = {}
    resolved_route = ""
    if score_fit is None:
        fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
        resolved_route = _a_e3_resolved_baseline_route_from_manifest(run_dir)
    evaluations = _a_e3_score_stage_candidates(
        specs=specs, plan_by_fit=plan_by_fit, score_fit=score_fit,
        run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        matrix_by_fit=matrix_by_fit, frozen=frozen, effective=effective,
        fit_states=fit_states, resolved_route=resolved_route,
        label=f"A-E3 stage1 ({token})")
    records, _diagnostics = build_selection_trace(
        module_id="A-E3", run_id=run_id, specs=specs, evaluations_by_fit=evaluations)
    trace_path, receipt_path, ledger_path = _a_e3_stage_evidence_paths(run_dir, "stage1", token)
    trace_sha = write_selection_trace(trace_path, records)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    receipt = publish_selection_receipt(
        receipt_path=receipt_path, ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=effective, code_commit=manifest["code_commit"])
    top4 = resolve_selected_placeholders(
        placeholders={f"selected_top_{slot}": _a_e3_stage1_decision_id(token) for slot in range(1, 5)},
        selection_trace_path=trace_path, selection_trace_sha256=trace_sha,
        selection_receipt_path=receipt_path, selection_ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id)
    return {
        "module_id": "A-E3", "run_id": run_id, "token": token,
        "selection_trace_sha256": trace_sha, "top4": top4, **receipt,
    }


def build_a_e3_stage2_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path,
    module_id: str = "A-E3", run_id: str, token: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Per-token A-E3 stage-2 selection receipt (winner) from ONE token's stage-2 fits ONLY.

    Mirrors :func:`build_a_e1_stage2_selection`. Maps the token's stage-2 winner
    (``selected_top_{slot}:{opt}``) to the concrete architecture (the token's verified stage1
    top4[slot]) and optimizer, namespaced by token (``selected:A-E3_*`` for ``F2_or_V``;
    ``selected:S_*`` for ``S``) -- the authority that token's output_form /
    shared_winner_retrain placeholders resolve against.

    Scoring reads the token's stage1 top4 from its OWN on-disk verified receipt
    (:func:`_recover_a_e3_stage1_selection`); the caller never supplies top4. Each scored
    fit's plan row is resolved from that verified authority before checkpoint scoring, so no
    placeholder reaches ``resolve_model_factory``.
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    route_stem = _a_e3_route_for_token(token)
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    stage2_rows = [
        row for row in matrix_rows if str(row["module"]) == "A-E3"
        and str(row["fit_kind"]) == "search_stage2" and str(row["route"]) == route_stem]
    specs = tuple(build_decision_specs("A-E3", stage2_rows))
    expected = {_a_e3_stage2_decision_id(token)}
    _require(
        {spec.decision_id for spec in specs} == expected,
        f"A-E3 stage2 selection scope must be exactly the {token!r} stage2 decision")
    fit_states: Mapping[str, str] = {}
    resolved_route = ""
    if score_fit is None:
        fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
        resolved_route = _a_e3_resolved_baseline_route_from_manifest(run_dir)
    evaluations = _a_e3_score_stage_candidates(
        specs=specs, plan_by_fit=plan_by_fit, score_fit=score_fit,
        run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        matrix_by_fit=matrix_by_fit, frozen=frozen, effective=effective,
        fit_states=fit_states, resolved_route=resolved_route,
        label=f"A-E3 stage2 ({token})")
    records, _diagnostics = build_selection_trace(
        module_id="A-E3", run_id=run_id, specs=specs, evaluations_by_fit=evaluations)
    trace_path, receipt_path, ledger_path = _a_e3_stage_evidence_paths(run_dir, "stage2", token)
    trace_sha = write_selection_trace(trace_path, records)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    receipt = publish_selection_receipt(
        receipt_path=receipt_path, ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=effective, code_commit=manifest["code_commit"])
    decision_id = _a_e3_stage2_decision_id(token)
    winner_record = next(
        (record for record in records if record["decision_id"] == decision_id and record["selected"]),
        None)
    _require(winner_record is not None, f"A-E3 stage2 decision {decision_id!r} has no selected winner")
    arch_placeholder, optimizer = _parse_stage2_winner_candidate(str(winner_record["candidate_id"]))
    top4 = _recover_a_e3_stage1_selection(run_dir=run_dir, run_id=run_id, token=token)["top4"]
    _require(
        arch_placeholder in top4,
        f"A-E3 stage2 winner slot {arch_placeholder!r} is outside the stage1 top4 for token {token!r}")
    arch_key, opt_key = _a_e3_stage2_winner_keys(token)
    winner = {arch_key: top4[arch_placeholder], opt_key: optimizer}
    return {
        "module_id": "A-E3", "run_id": run_id, "token": token,
        "selection_trace_sha256": trace_sha, "winner": winner, **receipt,
    }


def build_a_e3_loss_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path,
    module_id: str = "A-E3", run_id: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Global A-E3 loss selection receipt (``selected:A-E3_loss``) from the loss-screen fits.

    The frozen matrix has one A-E3 loss decision (``loss:A-E3:selected:F2_or_V:n10``) over the
    4 loss-screen candidates (``lowest_aggregate``). The winner is the A-E3-wide loss id that
    every downstream output_form / shared_winner_retrain fit resolves against. Production scores
    from checkpoints; tests inject ``score_fit``. No training; no test read.
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    loss_rows = [
        row for row in matrix_rows if str(row["module"]) == "A-E3"
        and str(row["fit_kind"]) == "loss_screen"]
    specs = tuple(build_decision_specs("A-E3", loss_rows))
    _require(
        {spec.decision_id for spec in specs} == {_A_E3_LOSS_DECISION_ID},
        f"A-E3 loss selection scope must be exactly {_A_E3_LOSS_DECISION_ID!r}")
    fit_states: Mapping[str, str] = {}
    resolved_route = ""
    if score_fit is None:
        fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
        resolved_route = _a_e3_resolved_baseline_route_from_manifest(run_dir)
    evaluations = _a_e3_score_stage_candidates(
        specs=specs, plan_by_fit=plan_by_fit, score_fit=score_fit,
        run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        matrix_by_fit=matrix_by_fit, frozen=frozen, effective=effective,
        fit_states=fit_states, resolved_route=resolved_route,
        label="A-E3 loss")
    records, _diagnostics = build_selection_trace(
        module_id="A-E3", run_id=run_id, specs=specs, evaluations_by_fit=evaluations)
    trace_path, receipt_path, ledger_path = _a_e3_stage_evidence_paths(run_dir, "loss", None)
    trace_sha = write_selection_trace(trace_path, records)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    receipt = publish_selection_receipt(
        receipt_path=receipt_path, ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=effective, code_commit=manifest["code_commit"])
    winner_record = next(
        (record for record in records
         if record["decision_id"] == _A_E3_LOSS_DECISION_ID and record["selected"]),
        None)
    _require(winner_record is not None, "A-E3 loss decision has no selected winner")
    return {
        "module_id": "A-E3", "run_id": run_id,
        "selection_trace_sha256": trace_sha,
        "selected:A-E3_loss": str(winner_record["candidate_id"]), **receipt,
    }


def build_a_e3_output_form_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path,
    module_id: str = "A-E3", run_id: str, predecessor_resolved_route: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Global A-E3 output_form selection receipt (``selected:A-E3_baseline``) from output_form fits.

    The frozen matrix has one A-E3 output_form decision (``output_form:A-E3:selected:F2_or_V``)
    over the ``joint`` / ``independent_capacity_matched`` candidates
    (``fixed_vs_shared_equal_weight``). Each output_form fit's scoring row is resolved from
    the verified loss + F2_or_V stage2 winner + predecessor route (via
    :func:`_resolve_a_e3_scoring_plan_row`) before checkpoint scoring, so no placeholder reaches
    ``resolve_model_factory``. The winner is the A-E3 baseline output form (the
    ``selected:A-E3_baseline`` alias). Production scores from checkpoints; tests inject
    ``score_fit``.
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id="A-E3")
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    output_form_rows = [
        row for row in matrix_rows if str(row["module"]) == "A-E3"
        and str(row["fit_kind"]) == "output_form"]
    specs = tuple(build_decision_specs("A-E3", output_form_rows))
    _require(
        {spec.decision_id for spec in specs} == {_A_E3_OUTPUT_FORM_DECISION_ID},
        f"A-E3 output_form selection scope must be exactly {_A_E3_OUTPUT_FORM_DECISION_ID!r}")
    fit_states: Mapping[str, str] = {}
    if score_fit is None:
        fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
    evaluations = _a_e3_score_stage_candidates(
        specs=specs, plan_by_fit=plan_by_fit, score_fit=score_fit,
        run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        matrix_by_fit=matrix_by_fit, frozen=frozen, effective=effective,
        fit_states=fit_states, resolved_route=str(predecessor_resolved_route),
        label="A-E3 output_form")
    records, _diagnostics = build_selection_trace(
        module_id="A-E3", run_id=run_id, specs=specs, evaluations_by_fit=evaluations)
    trace_path, receipt_path, ledger_path = _a_e3_stage_evidence_paths(run_dir, "output_form", None)
    trace_sha = write_selection_trace(trace_path, records)
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    receipt = publish_selection_receipt(
        receipt_path=receipt_path, ledger_path=ledger_path,
        module_id="A-E3", run_id=run_id, trace_path=trace_path, trace_sha256=trace_sha,
        effective_config=effective, code_commit=manifest["code_commit"])
    winner_record = next(
        (record for record in records
         if record["decision_id"] == _A_E3_OUTPUT_FORM_DECISION_ID and record["selected"]),
        None)
    _require(winner_record is not None, "A-E3 output_form decision has no selected winner")
    return {
        "module_id": "A-E3", "run_id": run_id,
        "selection_trace_sha256": trace_sha,
        "selected:A-E3_baseline": str(winner_record["candidate_id"]), **receipt,
    }


# ---------------------------------------------------------------------------
# A-E3 crash-recoverable ensure helpers (mirror ``_ensure_a_e1_*``).
#
# Each is idempotent on restart: if the receipt already exists it is RE-VALIDATED read-only
# (no re-scoring, no re-publish, no overwrite) and its placeholder(s) recovered; otherwise it
# is published from the stage's terminal fits. ``stage1_by_token`` / ``stage2_by_token`` are
# the orchestrator's within-pass caches (never the source of truth -- disk is).
# ---------------------------------------------------------------------------


def _ensure_a_e3_stage1_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path, run_id: str, token: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
) -> dict[str, Any]:
    """Ensure the token's A-E3 stage1 selection receipt exists and return its ``top4``.

    Crash-recoverable (mirrors :func:`_ensure_a_e1_stage1_selection`). The caller never
    supplies ``top4`` -- it is always derived from a validated receipt.
    """
    receipt_path = run_dir / f"stage1_selection_{token}_receipt.json"
    if receipt_path.exists():
        return _recover_a_e3_stage1_selection(run_dir=run_dir, run_id=run_id, token=token)
    return build_a_e3_stage1_selection(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        token=token, score_fit=score_fit)


def _ensure_a_e3_stage2_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path, run_id: str, token: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
    stage1_by_token: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Ensure the token's A-E3 stage2 selection receipt exists and return its ``winner``.

    Crash-recoverable (mirrors :func:`_ensure_a_e1_stage2_selection`). The token's stage1
    ``top4`` is ensured first so the stage2 winner slot can be validated against it.
    ``stage1_by_token`` is the orchestrator's within-pass cache; a recovered stage1 top4 is
    stored back into it so a later fit for the same token does not re-derive it.
    """
    if token not in stage1_by_token:
        stage1_by_token[token] = _ensure_a_e3_stage1_selection(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
            token=token, score_fit=score_fit)
    top4 = stage1_by_token[token]["top4"]
    receipt_path = run_dir / f"stage2_selection_{token}_receipt.json"
    if receipt_path.exists():
        return _recover_a_e3_stage2_selection(run_dir=run_dir, run_id=run_id, token=token, top4=top4)
    return build_a_e3_stage2_selection(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        token=token, score_fit=score_fit)


def _ensure_a_e3_loss_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path, run_id: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
) -> dict[str, Any]:
    """Ensure the global A-E3 loss selection receipt exists and return its resolution.

    Idempotent on restart: an existing receipt is re-validated and its ``selected:A-E3_loss``
    recovered (no re-publish); otherwise it is published from the loss-screen fits.
    """
    receipt_path = run_dir / "loss_selection_receipt.json"
    if receipt_path.exists():
        return _recover_a_e3_loss_selection(run_dir=run_dir, run_id=run_id)
    return build_a_e3_loss_selection(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        score_fit=score_fit)


def _ensure_a_e3_output_form_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path, run_id: str,
    predecessor_resolved_route: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
) -> dict[str, Any]:
    """Ensure the global A-E3 output_form selection receipt exists and return its resolution.

    Idempotent on restart: an existing receipt is re-validated and its
    ``selected:A-E3_baseline`` recovered (no re-publish); otherwise it is published from the
    output_form fits (which requires the prerequisite loss + F2_or_V stage2 receipts on disk).
    """
    receipt_path = run_dir / "output_form_selection_receipt.json"
    if receipt_path.exists():
        return _recover_a_e3_output_form_selection(run_dir=run_dir, run_id=run_id)
    return build_a_e3_output_form_selection(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
        predecessor_resolved_route=predecessor_resolved_route, score_fit=score_fit)


def _ensure_a_e3_final_selection(
    *, study_root: Path, run_dir: Path, cache_root: Path, run_id: str,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
) -> dict[str, Any]:
    """Ensure the A-E3 final module selection trace/receipt/ledger exists; idempotent on restart.

    Mirrors :func:`_ensure_a_e1_final_selection`. If the final receipt already exists it is
    RE-VALIDATED read-only (no re-publish, no overwrite); otherwise it is published from the
    terminal selection fits via :func:`build_module_selection`. Repeated calls after
    completion are idempotent (validate-only).
    """
    receipt_path = run_dir / "selection_receipt.json"
    if receipt_path.exists():
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        trace_sha = str(receipt["selection_trace_sha256"])
        _validate_selection_evidence(
            selection_trace_path=run_dir / "selection_trace.jsonl",
            selection_trace_sha256=trace_sha,
            selection_receipt_path=receipt_path,
            selection_ledger_path=run_dir / "selection_ledger.jsonl",
            module_id="A-E3", run_id=run_id,
        )
        return {"module_id": "A-E3", "run_id": run_id, "reused": True,
                "selection_trace_sha256": trace_sha}
    return build_module_selection(
        study_root=study_root, run_dir=run_dir, cache_root=cache_root, module_id="A-E3",
        run_id=run_id, score_fit=score_fit)


def run_a_e1_staged(
    *, study_root: Path, module_id: str = "A-E1", run_id: str,
    artifact_root: Path, cache_root: Path, owner_id: str = "formal-executor",
    max_fits: int | None = None,
    fit_runner: Callable[..., Mapping[str, Any]] | None = None,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Drive the real frozen A-E1 module through its staged execution (deadlock-free, crash-recoverable).

    Source of truth: a fit's stage (``concrete`` / ``stage2`` / ``winner_retrain``) is classified
    from its AUTHORITATIVE frozen matrix row (looked up by ``fit_id``), never from ``plan.jsonl`` --
    ``fit_kind`` lives in the matrix and the plan deliberately omits it. Before any fit runs, the
    plan is validated against the matrix (exact ``fit_id`` correspondence + per-row
    ``matrix_row_sha256`` binding), fail-closed on any missing/duplicate/extra fit or hash mismatch.

    Executes every fit in plan order via the existing scheduler journal (claim -> train ->
    record). Concrete / stage1 rows run directly; stage2 (``selected_top_*``) rows are concretized
    from the stage1 top4 receipt; winner-retrain (``selected:A-E1_*``) rows from the stage2 winner
    receipt. Each per-route receipt is ENSURED, not rebuilt blindly: if it already exists (a prior
    pass or a restart) it is re-validated read-only and its top4/winner recovered (no re-scoring,
    no re-publish, no overwrite); otherwise it is published once its stage's fits are terminal
    (plan ordering guarantees it). On restart, already-terminal fits are not re-trained and staged
    state is recovered from the receipts on disk -- the in-memory route dicts are only a
    within-pass cache. After every fit is terminal, the final module selection trace + F2/V
    decision + staged ledger are ensured (an existing final receipt is re-validated, so repeated
    calls after completion are idempotent). ``top4`` / ``winner`` are always derived from a
    validated receipt, never supplied by the caller. Reuses the scheduler throughout. No test read;
    test stays sealed; ``test_access_count`` stays 0.
    """
    if module_id != "A-E1":
        raise NotImplementedError(
            f"staged execution of module {module_id!r} is not implemented; only A-E1")
    study_root = Path(study_root).resolve()
    artifact_root = Path(artifact_root).resolve()
    cache_root = Path(cache_root).resolve()
    matrix_path = (study_root / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv").resolve()
    materialize_run(
        study_root=study_root, matrix_path=matrix_path, module_id=module_id, run_id=run_id,
        artifact_root=artifact_root, cache_root=cache_root, predecessor=None)
    run_dir = artifact_root / module_id / run_id
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)

    # Authoritative fit_id -> matrix row map: fit_kind/module/n live ONLY in the frozen matrix
    # (plan.jsonl renames them and carries just runtime training metadata). Validated against
    # plan.jsonl -- exact fit_id correspondence + per-row matrix_row_sha256 binding -- fail-closed
    # on any missing/duplicate/extra fit or hash mismatch, BEFORE any stage is classified.
    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id=module_id)
    plan_order = [str(row["fit_id"]) for row in plan_rows]

    runner = fit_runner or execute_claimed_fit
    # Per-route staged receipts are recovered from disk on every pass (a restart re-validates the
    # existing trace/receipt/ledger and reuses its top4/winner); these dicts are only a within-pass
    # cache, never the source of truth.
    stage1_by_route: dict[str, dict[str, Any]] = {}
    stage2_by_route: dict[str, dict[str, Any]] = {}
    succeeded: list[str] = []
    failed: list[dict[str, str]] = []
    consecutive_failures = 0
    while max_fits is None or len(succeeded) < int(max_fits):
        state = _rebuild_authority(run_dir, cache_root)[2]
        pending = [fid for fid in plan_order if state["fit_states"].get(fid) == "pending"]
        if not pending:
            break
        fit_id = pending[0]
        plan_row = plan_by_fit[fit_id]
        # Stage is classified from the AUTHORITATIVE matrix row (fit_kind is absent from plan.jsonl).
        stage = _a_e1_fit_stage(matrix_by_fit[fit_id])
        route = str(plan_row["route"])
        if stage == "stage2":
            # the route's stage1 fits precede its stage2 fits in plan order, so they are terminal now
            if route not in stage1_by_route:
                stage1_by_route[route] = _ensure_a_e1_stage1_selection(
                    study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
                    route=route, score_fit=score_fit)
            resolved = _resolve_stage2_plan_row(plan_row, stage1_by_route[route]["top4"])
        elif stage == "winner_retrain":
            if route not in stage2_by_route:
                stage2_by_route[route] = _ensure_a_e1_stage2_selection(
                    study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
                    route=route, score_fit=score_fit, stage1_by_route=stage1_by_route)
            resolved = _resolve_winner_retrain_plan_row(plan_row, stage2_by_route[route]["winner"])
        else:
            resolved = plan_row
        timestamp = _utc_now()
        claim = claim_next_fit(
            run_dir, cache_root=cache_root, owner_id=owner_id,
            owner_nonce=hashlib.sha256(f"{owner_id}:{timestamp}".encode("utf-8")).hexdigest()[:32],
            timestamp=timestamp)
        if claim.get("status") != "claimed":
            break  # exhausted or monitor_only (another live owner); caller may retry
        result = runner(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, plan_row=resolved,
            claim=claim, frozen=frozen, effective=effective, timestamp=timestamp)
        if result["state"] == "succeeded":
            succeeded.append(fit_id)
            consecutive_failures = 0
        else:
            failed.append({"fit_id": fit_id, "failure_code": result["failure_code"], "message": result["message"]})
            consecutive_failures = _advance_consecutive_failures(
                consecutive_failures, result["failure_code"], result["message"],
                label="staged A-E1")

    # The final module selection + staged resolution require EVERY selection fit terminal. A
    # partial run (max_fits capped, or a smoke) skips them and returns the partial execution
    # result; the full run ensures the final trace + F2/V decision + staged ledger (idempotent on
    # restart: an existing final receipt is re-validated, never re-published or overwritten).
    final_state = _rebuild_authority(run_dir, cache_root)[2]
    pending_remaining = [fid for fid in plan_order if final_state["fit_states"].get(fid) == "pending"]
    result: dict[str, Any] = {
        "module_id": "A-E1", "run_id": run_id, "run_dir": str(run_dir),
        "succeeded": succeeded, "failed": failed,
        "succeeded_count": len(succeeded), "failed_count": len(failed),
        "complete": not pending_remaining,
        "stage1_by_route": {route: {"top4": receipt["top4"]} for route, receipt in stage1_by_route.items()},
        "stage2_by_route": {route: {"winner": receipt["winner"]} for route, receipt in stage2_by_route.items()},
    }
    if not pending_remaining:
        result["final_selection"] = _ensure_a_e1_final_selection(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
            score_fit=score_fit)
        result["staged"] = resolve_a_e1_staged_selection(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, module_id="A-E1",
            run_id=run_id, score_fit=score_fit)
    return result


def run_a_e3_staged(
    *, study_root: Path, module_id: str = "A-E3", run_id: str,
    artifact_root: Path, cache_root: Path, owner_id: str = "formal-executor",
    max_fits: int | None = None,
    fit_runner: Callable[..., Mapping[str, Any]] | None = None,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
    score_n_strategy_cell: Callable[[str, int, int, str], FitEvaluation] | None = None,
    predecessor: Mapping[str, Any] | PredecessorTrace | None,
) -> dict[str, Any]:
    """Drive the real frozen A-E3 module through its staged execution (deadlock-free, crash-recoverable).

    Mirrors :func:`run_a_e1_staged` for A-E3. Source of truth: a fit's stage
    (``concrete`` / ``stage2`` / ``output_form`` / ``shared_winner_retrain``) is classified from its
    AUTHORITATIVE frozen matrix row (looked up by ``fit_id``), never from ``plan.jsonl``. Before
    any fit runs, the plan is validated against the matrix (exact ``fit_id`` correspondence +
    per-row ``matrix_row_sha256`` binding), fail-closed on any mismatch. The A-E1 predecessor is
    bound at ``materialize_run`` time: its trace/receipt/ledger/staged-ledger SHAs are verified
    and ``resolved_baseline_route`` (V for the r5 design) is extracted, so every A-E3
    ``selected:F2_or_V`` route placeholder resolves to a cryptographically bound value (not a
    re-read).

    Executes every fit in plan order via the existing scheduler journal (claim -> train ->
    record). Concrete rows (``loss_screen`` / ``search_stage1``) run directly; ``search_stage2``
    rows are concretized from the route token's stage1 top4 receipt; ``output_form`` rows from
    the global loss receipt + the F2_or_V stage2 winner + the predecessor route;
    ``shared_winner_retrain`` rows from the global loss receipt + the S stage2 winner. Each
    prerequisite receipt is ENSURED, not rebuilt blindly: if it already exists it is re-validated
    read-only (no re-scoring, no re-publish, no overwrite); otherwise it is published once its
    stage's fits are terminal (plan ordering guarantees it). On restart, already-terminal fits
    are not re-trained and staged state is recovered from the receipts on disk -- the in-memory
    token dicts are only a within-pass cache. After every fit is terminal, the final module
    selection trace + 10-record staged ledger are ensured (idempotent on restart).

    Reuses the scheduler throughout (``materialize_run`` / ``claim_next_fit`` /
    ``record_fit_succeeded`` / ``_rebuild_authority``) and the C2/C3 A-E3 helpers
    (``_a_e3_fit_stage`` / ``_resolve_a_e3_scoring_plan_row`` / ``_ensure_a_e3_*`` /
    ``build_a_e3_*``). No test read; test stays sealed; ``test_access_count`` stays 0.
    """
    if module_id != "A-E3":
        raise NotImplementedError(
            f"staged execution of module {module_id!r} is not implemented; only A-E3")
    if predecessor is None:
        raise ValueError("A-E3 staged execution requires a predecessor (A-E1 staged run)")
    study_root = Path(study_root).resolve()
    artifact_root = Path(artifact_root).resolve()
    cache_root = Path(cache_root).resolve()
    matrix_path = (study_root / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv").resolve()
    # The scheduler's _validate_predecessor (C1) verifies the predecessor trace/receipt/ledger +
    # staged-ledger SHA + chain, and extracts resolved_baseline_route, BEFORE any claim. A bad
    # predecessor fails closed at materialize.
    materialize_run(
        study_root=study_root, matrix_path=matrix_path, module_id=module_id, run_id=run_id,
        artifact_root=artifact_root, cache_root=cache_root, predecessor=predecessor)
    run_dir = artifact_root / module_id / run_id
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)

    matrix_by_fit = _authoritative_matrix_by_fit(study_root)
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_by_fit = _validate_plan_against_matrix(
        plan_rows=plan_rows, matrix_by_fit=matrix_by_fit, module_id=module_id)
    plan_order = [str(row["fit_id"]) for row in plan_rows]

    # Resolve the predecessor route ONCE from the manifest (C1 binding). Every A-E3 fit's
    # ``selected:F2_or_V`` placeholder resolves against this value, threaded through the
    # scoring plan-row resolver.
    predecessor_resolved_route = _a_e3_resolved_baseline_route_from_manifest(run_dir)

    runner = fit_runner or execute_claimed_fit
    # Per-token staged receipts are recovered from disk on every pass; these dicts are only a
    # within-pass cache (disk is the source of truth, mirroring run_a_e1_staged).
    stage1_by_token: dict[str, dict[str, Any]] = {}
    stage2_by_token: dict[str, dict[str, Any]] = {}
    loss_receipt: dict[str, Any] | None = None
    succeeded: list[str] = []
    failed: list[dict[str, str]] = []
    consecutive_failures = 0
    while max_fits is None or len(succeeded) < int(max_fits):
        state = _rebuild_authority(run_dir, cache_root)[2]
        pending = [fid for fid in plan_order if state["fit_states"].get(fid) == "pending"]
        if not pending:
            break
        fit_id = pending[0]
        matrix_row = matrix_by_fit[fit_id]
        matrix_route = str(matrix_row["route"])
        stage = _a_e3_fit_stage(matrix_row)
        # Ensure the prerequisite stage receipt(s) BEFORE claiming, so the scoring plan-row
        # resolver can recover the verified placeholders from disk. Plan order guarantees the
        # prerequisite stage's fits are terminal at this point (deadlock-free staged authority).
        if stage == "stage2":
            token = _a_e3_route_token(matrix_route)
            if token not in stage1_by_token:
                stage1_by_token[token] = _ensure_a_e3_stage1_selection(
                    study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
                    token=token, score_fit=score_fit)
        elif stage == "output_form":
            if loss_receipt is None:
                loss_receipt = _ensure_a_e3_loss_selection(
                    study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
                    score_fit=score_fit)
            if _A_E3_FV_TOKEN not in stage2_by_token:
                stage2_by_token[_A_E3_FV_TOKEN] = _ensure_a_e3_stage2_selection(
                    study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
                    token=_A_E3_FV_TOKEN, score_fit=score_fit, stage1_by_token=stage1_by_token)
        elif stage == "shared_winner_retrain":
            if loss_receipt is None:
                loss_receipt = _ensure_a_e3_loss_selection(
                    study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
                    score_fit=score_fit)
            if _A_E3_S_TOKEN not in stage2_by_token:
                stage2_by_token[_A_E3_S_TOKEN] = _ensure_a_e3_stage2_selection(
                    study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
                    token=_A_E3_S_TOKEN, score_fit=score_fit, stage1_by_token=stage1_by_token)
        # Resolve the scoring row from on-disk verified evidence (the runner sees ONLY concrete
        # fields; no placeholder reaches resolve_model_factory).
        resolved = _resolve_a_e3_scoring_plan_row(
            run_dir=run_dir, run_id=run_id, fit_id=fit_id,
            matrix_by_fit=matrix_by_fit, plan_by_fit=plan_by_fit,
            predecessor_resolved_route=predecessor_resolved_route)
        timestamp = _utc_now()
        claim = claim_next_fit(
            run_dir, cache_root=cache_root, owner_id=owner_id,
            owner_nonce=hashlib.sha256(f"{owner_id}:{timestamp}".encode("utf-8")).hexdigest()[:32],
            timestamp=timestamp)
        if claim.get("status") != "claimed":
            break  # exhausted or monitor_only (another live owner); caller may retry
        result = runner(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, plan_row=resolved,
            claim=claim, frozen=frozen, effective=effective, timestamp=timestamp)
        if result["state"] == "succeeded":
            succeeded.append(fit_id)
            consecutive_failures = 0
        else:
            failed.append({"fit_id": fit_id, "failure_code": result["failure_code"], "message": result["message"]})
            consecutive_failures = _advance_consecutive_failures(
                consecutive_failures, result["failure_code"], result["message"],
                label="staged A-E3")

    # The final module selection + 10-record staged ledger require EVERY fit terminal. A partial
    # run (max_fits capped, or a smoke) skips them and returns the partial execution result; the
    # full run ensures the final trace + staged ledger (idempotent on restart).
    final_state = _rebuild_authority(run_dir, cache_root)[2]
    pending_remaining = [fid for fid in plan_order if final_state["fit_states"].get(fid) == "pending"]
    result: dict[str, Any] = {
        "module_id": "A-E3", "run_id": run_id, "run_dir": str(run_dir),
        "succeeded": succeeded, "failed": failed,
        "succeeded_count": len(succeeded), "failed_count": len(failed),
        "complete": not pending_remaining,
        "stage1_by_token": {token: {"top4": receipt["top4"]}
                            for token, receipt in stage1_by_token.items()},
        "stage2_by_token": {token: {"winner": receipt["winner"]}
                            for token, receipt in stage2_by_token.items()},
    }
    if not pending_remaining:
        result["final_selection"] = _ensure_a_e3_final_selection(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
            score_fit=score_fit)
        result["staged"] = resolve_a_e3_staged_selection(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, module_id="A-E3",
            run_id=run_id, score_fit=score_fit, predecessor=predecessor,
            score_n_strategy_cell=score_n_strategy_cell)
    return result


__all__ = [
    "build_a_e1_stage1_selection",
    "build_a_e1_stage2_selection",
    "build_a_e3_loss_selection",
    "build_a_e3_output_form_selection",
    "build_a_e3_stage1_selection",
    "build_a_e3_stage2_selection",
    "build_module_pre_unseal_bundle",
    "build_module_selection",
    "execute_claimed_fit",
    "rebuild_a_e3_n_strategy_provenance",
    "rebuild_selection_point_provenance",
    "reconstruct_a_e1_specs",
    "reconstruct_a_e3_specs",
    "reconstruct_deferred_specs",
    "resolve_loss_id",
    "resolve_model_factory",
    "resolve_optimizer_hyperparams",
    "resolve_a_e1_staged_selection",
    "resolve_a_e3_staged_selection",
    "resolve_selected_placeholders",
    "run_a_e1_staged",
    "run_a_e3_staged",
    "run_module",
]
