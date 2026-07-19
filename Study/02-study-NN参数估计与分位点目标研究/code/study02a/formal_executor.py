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
    _rebuild_authority,
    claim_next_fit,
    materialize_run,
    record_fit_failed,
    record_fit_succeeded,
)
from .models import build_deepsets, build_mlp
from .matrix import expand_module_matrix
from .training import fit_fixed_candidate, fit_set_candidate, load_checkpoint


_HISTORICAL_PREFIX = "historical_"
_MLP_PREFIX = "m"
_DEEP_PREFIX = "d"
_STAGE_TOP_PREFIX = "selected_top_"
_SELECTED_PREFIX = "selected:"


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
    architecture_id: str, frozen: FrozenConfig, input_dim: int | None
) -> Callable[[], nn.Module]:
    """Resolve a frozen architecture id to a deterministic model factory.

    ``selected:*`` and ``selected_top_N`` ids require a completed selection trace
    (D7/D8) and fail closed here.
    """
    _require(isinstance(architecture_id, str) and architecture_id, "architecture id is required")
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
    (sample_id / point_id) the CI rules cluster on.
    """

    scaled_training: Any
    scaled_validation: FormalFixedBatch | FormalSetBatch
    validation_metadata: tuple[Mapping[str, Any], ...]
    validation_identity: str
    model_factory: Callable[[], nn.Module]
    hyperparams: Mapping[str, Any]
    loss_id: str
    is_set: bool


def _prepare_fit_inputs(
    plan_row: Mapping[str, Any], frozen: FrozenConfig,
    effective: EffectiveFormalConfig, cache_root: Path,
) -> _PreparedFit:
    """Build the cached datasets, training-only scaler, resolved model and hyperparams.

    Reconstructs the A-E1 training/validation specs exactly as the scheduler did
    (so executor and scheduler agree byte-for-byte) and applies the training-only
    scaler. A-E3/A-E2 add a deferred-spec predecessor path (D8); A-E1 is the
    currently executable scope. ``validation_identity`` (the validation dataset hash)
    binds which validation cache the per-point evidence was scored on (R3#1).
    """
    training_spec, validation_spec = reconstruct_a_e1_specs(plan_row, frozen, effective)
    training_dataset = cache_dataset(training_spec, frozen, effective, cache_root)
    validation_dataset = cache_dataset(validation_spec, frozen, effective, cache_root)
    scaler = fit_training_scaler(training_dataset, frozen, effective)
    scaled_training = apply_training_scaler(training_dataset, scaler, training_dataset, frozen, effective)
    scaled_validation = apply_training_scaler(validation_dataset, scaler, training_dataset, frozen, effective)
    is_set = str(plan_row["route"]) == "S"
    input_dim = None if is_set else int(scaled_training.batch.features.shape[1])
    model_factory = resolve_model_factory(str(plan_row["architecture"]), frozen, input_dim)
    hyperparams = resolve_optimizer_hyperparams(str(plan_row["optimizer"]), frozen)
    loss_id = resolve_loss_id(str(plan_row["loss"]))
    return _PreparedFit(
        scaled_training, scaled_validation, tuple(validation_dataset.metadata),
        validation_dataset.dataset_hash, model_factory, hyperparams, loss_id, is_set,
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
    prepared = _prepare_fit_inputs(plan_row, frozen, effective, cache_root)
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
    _MAX_CONSECUTIVE_FAILURES = 8  # stop on a systematic scientific failure, not churn
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
            consecutive_failures += 1
            if consecutive_failures >= _MAX_CONSECUTIVE_FAILURES:
                raise RuntimeError(
                    f"formal execution aborted: {_MAX_CONSECUTIVE_FAILURES} consecutive scientific failures "
                    f"(last: {result['failure_code']}: {result['message']})"
                )

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
        run_dir=run_dir, cache_root=cache_root, module_id=module_id, frozen=frozen,
        effective=effective, score_fit=score_fit,
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
    point_evidence_paths: dict[str, str] = {}
    for fit_id, evaluation in evaluations_by_fit.items():
        artifact_path = run_dir / "outputs" / fit_id / "point_evidence.json"
        _publish_bytes_no_replace(_canonical(serialize_point_evidence(evaluation)), artifact_path)
        point_evidence_paths[fit_id] = str(artifact_path)
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
    prepared = _prepare_fit_inputs(plan_row, frozen, effective, cache_root)
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
        validation_batch=prepared.scaled_validation, validation_metadata=prepared.validation_metadata,
        seed_id=str(plan_row["seed"]), is_set=prepared.is_set,
    )
    return FitEvaluation(
        fit_id=fit_id, module_id=module_id, decision_id=decision_id, candidate_id=candidate_id,
        support_key=support_key, failed=False,
        checkpoint_sha256=hashlib.sha256(checkpoint_bytes).hexdigest(),
        validation_identity=prepared.validation_identity,
        selection_score=scalar, failure_penalty=0.0, point_records=point_records,
    )


def _derive_and_score_evaluations(
    *, run_dir: Path, cache_root: Path, module_id: str, frozen: FrozenConfig,
    effective: EffectiveFormalConfig,
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
    plan_rows = [
        json.loads(line)
        for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    plan_by_fit = {str(row["fit_id"]): row for row in plan_rows}
    # DecisionSpecs are derived from the frozen matrix (which carries module/fit_kind/n), not
    # from plan.jsonl (whose rows rename those fields); the plan rows supply the runtime
    # per-fit metadata used for scoring. The matrix is the same frozen authority pre-unseal
    # reopens, so the two derivations agree.
    matrix_rows = expand_module_matrix(frozen).to_dict("records")
    specs = build_decision_specs(module_id, matrix_rows)
    fit_states: Mapping[str, str] = {}
    if score_fit is None:
        fit_states = _rebuild_authority(run_dir, cache_root)[2]["fit_states"]
    evaluations_by_fit: dict[str, FitEvaluation] = {}
    for spec in specs:
        for candidate in spec.candidates:
            for key in candidate.support_keys:
                fit_id = candidate.support_for(key)
                plan_row = plan_by_fit[fit_id]
                if score_fit is not None:
                    evaluation = score_fit(fit_id, plan_row)
                else:
                    evaluation = _score_fit_from_checkpoint(
                        run_dir=run_dir, cache_root=cache_root, fit_id=fit_id,
                        plan_row=plan_row, frozen=frozen, effective=effective, fit_states=fit_states,
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
    ``run_id`` is accepted for interface symmetry but the rebuild reads ``run_dir`` directly.
    """
    study_root = Path(study_root).resolve()
    run_dir = Path(run_dir).resolve()
    cache_root = Path(cache_root).resolve()
    del run_id  # the rebuild reads run_dir/outputs/{fit_id}/checkpoint.pt directly
    frozen = load_frozen_config(study_root)
    effective = load_effective_formal_config(study_root)
    specs, evaluations_by_fit = _derive_and_score_evaluations(
        run_dir=run_dir, cache_root=cache_root, module_id=module_id, frozen=frozen,
        effective=effective, score_fit=None,
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


def _a_e1_winner_retrain_plan_rows(
    run_dir: Path, candidates: Sequence[CandidateSpec],
) -> dict[str, Mapping[str, Any]]:
    wanted = {fit_id for candidate in candidates for fit_id in candidate.expected_fit_ids}
    plan_rows = [
        json.loads(line)
        for line in (Path(run_dir) / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return {str(row["fit_id"]): row for row in plan_rows if str(row["fit_id"]) in wanted}


def _score_a_e1_winner_retrain(
    *, study_root: Path, run_dir: Path, cache_root: Path, frozen: FrozenConfig,
    effective: EffectiveFormalConfig, candidates: Sequence[CandidateSpec],
    route_stage2: Mapping[str, tuple[str, str, str]],
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None,
) -> tuple[dict[str, FitEvaluation] | None, bool]:
    """Score the F2/V winner-retrain fits. Returns ``(evaluations_by_fit, pending)``.

    ``score_fit`` (tests) injects bound evaluations without launching training. The production
    default scores each winner-retrain checkpoint with the route's RESOLVED architecture /
    optimizer / loss (the placeholders cannot build a model until stage2 resolves them); a
    winner-retrain fit that has not yet succeeded leaves the baseline ``pending`` rather than
    forcing a partial comparison.
    """
    del study_root
    plan_by_fit = _a_e1_winner_retrain_plan_rows(run_dir, candidates)
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
        loss, architecture, optimizer = route_stage2[candidate.candidate_id]
        for key in candidate.support_keys:
            fit_id = candidate.support_for(key)
            if fit_states.get(fit_id) != "succeeded":
                return None, True  # winner-retrain not executed yet -> baseline pending
            resolved_row = dict(plan_by_fit[fit_id], architecture=architecture,
                                optimizer=optimizer, loss=loss)
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
        effective=effective, candidates=baseline_candidates, route_stage2=route_stage2,
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


def _a_e1_fit_stage(plan_row: Mapping[str, Any]) -> str:
    """Classify an A-E1 plan row into its staged-execution stage.

    ``stage2`` / ``winner_retrain`` rows carry placeholders and need a prior-stage receipt to
    concretize before execution; everything else (historical / controlled / ``search_stage1``
    architecture rows) is directly executable."""
    kind = str(plan_row.get("fit_kind", ""))
    if kind == "search_stage2":
        return "stage2"
    if kind == "winner_retrain":
        return "winner_retrain"
    return "concrete"


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
    module_id: str = "A-E1", run_id: str, route: str, top4: Mapping[str, str],
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Per-route stage-2 selection receipt (winner architecture/optimizer/loss) from ONE route's
    stage-2 fits ONLY, given that route's stage-1 top4. Maps the route's stage-2 winner
    (``selected_top_{slot}:{opt}``) to the concrete architecture (``top4[slot]``), optimizer, and
    frozen loss -- the authority that route's winner-retrain placeholders resolve against.
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
                plan_row = plan_by_fit[fit_id]
                if score_fit is not None:
                    evaluation = score_fit(fit_id, plan_row)
                else:
                    _require(
                        fit_states.get(fit_id) == "succeeded",
                        f"stage2 selection requires every {route} stage2 fit terminal; {fit_id!r} is not succeeded")
                    evaluation = _score_fit_from_checkpoint(
                        run_dir=run_dir, cache_root=cache_root, fit_id=fit_id, plan_row=plan_row,
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


def run_a_e1_staged(
    *, study_root: Path, module_id: str = "A-E1", run_id: str,
    artifact_root: Path, cache_root: Path, owner_id: str = "formal-executor",
    max_fits: int | None = None,
    fit_runner: Callable[..., Mapping[str, Any]] | None = None,
    score_fit: Callable[[str, Mapping[str, Any]], FitEvaluation] | None = None,
) -> dict[str, Any]:
    """Drive the real frozen A-E1 module through its staged execution (deadlock-free).

    Executes every fit in plan order via the existing scheduler journal (claim -> train ->
    record). Concrete / stage1 rows run directly; stage2 (``selected_top_*``) rows are
    concretized from the stage1 top4 receipt; winner-retrain (``selected:A-E1_*``) rows from the
    stage2 winner receipt. Each receipt is published once its stage's fits are terminal (plan
    ordering guarantees it). After every fit is terminal, the EXISTING ``build_module_selection``
    -- now unblocked, since every selection fit is done -- publishes the final module trace, and
    its internal ``resolve_a_e1_staged_selection`` derives the F2/V decision, final aliases and
    the staged ledger. Adds only the two staged receipts; reuses the scheduler throughout. No
    test read; test stays sealed; ``test_access_count`` stays 0.
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
    plan_rows = [
        json.loads(line) for line in (run_dir / "plan.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()]
    plan_order = [str(row["fit_id"]) for row in plan_rows]
    plan_by_fit = {str(row["fit_id"]): row for row in plan_rows}

    runner = fit_runner or execute_claimed_fit
    stage1_by_route: dict[str, dict[str, Any]] = {}
    stage2_by_route: dict[str, dict[str, Any]] = {}
    succeeded: list[str] = []
    failed: list[dict[str, str]] = []
    while max_fits is None or len(succeeded) < int(max_fits):
        state = _rebuild_authority(run_dir, cache_root)[2]
        pending = [fid for fid in plan_order if state["fit_states"].get(fid) == "pending"]
        if not pending:
            break
        fit_id = pending[0]
        plan_row = plan_by_fit[fit_id]
        stage = _a_e1_fit_stage(plan_row)
        route = str(plan_row["route"])
        if stage == "stage2":
            # the route's stage1 fits precede its stage2 fits in plan order, so they are terminal now
            if route not in stage1_by_route:
                stage1_by_route[route] = build_a_e1_stage1_selection(
                    study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
                    route=route, score_fit=score_fit)
            resolved = _resolve_stage2_plan_row(plan_row, stage1_by_route[route]["top4"])
        elif stage == "winner_retrain":
            if route not in stage2_by_route:
                stage2_by_route[route] = build_a_e1_stage2_selection(
                    study_root=study_root, run_dir=run_dir, cache_root=cache_root, run_id=run_id,
                    route=route, top4=stage1_by_route[route]["top4"], score_fit=score_fit)
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
        else:
            failed.append({"fit_id": fit_id, "failure_code": result["failure_code"], "message": result["message"]})

    # The final module selection + staged resolution require EVERY selection fit terminal. A
    # partial run (max_fits capped, or a smoke) skips them and returns the partial execution
    # result; the full run produces the final trace + F2/V decision + staged ledger.
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
        result["final_selection"] = build_module_selection(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, module_id="A-E1",
            run_id=run_id, score_fit=score_fit)
        result["staged"] = resolve_a_e1_staged_selection(
            study_root=study_root, run_dir=run_dir, cache_root=cache_root, module_id="A-E1",
            run_id=run_id, score_fit=score_fit)
    return result


__all__ = [
    "build_a_e1_stage1_selection",
    "build_a_e1_stage2_selection",
    "build_module_pre_unseal_bundle",
    "build_module_selection",
    "execute_claimed_fit",
    "rebuild_selection_point_provenance",
    "reconstruct_a_e1_specs",
    "reconstruct_deferred_specs",
    "resolve_loss_id",
    "resolve_model_factory",
    "resolve_optimizer_hyperparams",
    "resolve_a_e1_staged_selection",
    "resolve_selected_placeholders",
    "run_a_e1_staged",
    "run_module",
]
