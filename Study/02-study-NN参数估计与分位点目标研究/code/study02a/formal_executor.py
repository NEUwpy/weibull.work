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
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import torch
from torch import nn

from .config import FrozenConfig, load_frozen_config
from .formal_config import EffectiveFormalConfig, load_effective_formal_config
from .formal_data import FormalFixedBatch, FormalSetBatch  # noqa: F401  (type re-export)
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
from .training import fit_fixed_candidate, fit_set_candidate


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


def _terminal_validation_slope(curve: Sequence[float]) -> float:
    """OLS slope over the last 10 validation losses (mirrors the frozen ceiling contract)."""
    values = tuple(float(v) for v in curve)
    terminal = values[-10:]
    if len(terminal) <= 1:
        return 0.0
    x_mean = (len(terminal) - 1) / 2.0
    y_mean = sum(terminal) / len(terminal)
    numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(terminal))
    denominator = sum((index - x_mean) ** 2 for index in range(len(terminal)))
    return numerator / denominator


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
    route = str(plan_row["route"])
    is_set = route == "S"

    # Infrastructure: data + scaler + resolved model/hyperparams (errors propagate).
    training_spec, validation_spec = reconstruct_a_e1_specs(plan_row, frozen, effective)
    training_dataset = cache_dataset(training_spec, frozen, effective, cache_root)
    validation_dataset = cache_dataset(validation_spec, frozen, effective, cache_root)
    scaler = fit_training_scaler(training_dataset, frozen, effective)
    scaled_training = apply_training_scaler(training_dataset, scaler, training_dataset, frozen, effective)
    scaled_validation = apply_training_scaler(validation_dataset, scaler, training_dataset, frozen, effective)
    input_dim = None if is_set else int(scaled_training.batch.features.shape[1])
    model_factory = resolve_model_factory(str(plan_row["architecture"]), frozen, input_dim)
    hyperparams = resolve_optimizer_hyperparams(str(plan_row["optimizer"]), frozen)
    loss_id = resolve_loss_id(str(plan_row["loss"]))

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
        "terminal_validation_slope": _terminal_validation_slope(curve),
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
    *, study_root: Path, run_dir: Path, cache_root: Path, module_id: str, run_id: str
) -> dict[str, Any]:
    """Build the selection trace/receipt/ledger for a completed module (D7, deferred).

    Ranks each decision's candidates by the frozen ranking rule
    (``mean_validation_failure_penalized_l_param_across_screening_seeds_ascending``
    with ``architecture_id_lexicographic`` tie-break) and publishes the immutable
    selection evidence consumed by downstream modules and by ``selected:*``
    placeholder resolution. NOT YET IMPLEMENTED: the ``L_param`` failure-penalized
    validation metric is not defined in the frozen search config, so the ranking
    contract must be finalized (and oracle-reviewed) before this runs.
    """
    raise NotImplementedError(
        "build_module_selection (D7) is deferred; the L_param ranking metric is not yet defined"
    )


def resolve_selected_placeholders(*arg: Any, **kw: Any) -> Any:  # pragma: no cover - placeholder
    """Resolve ``selected:<decision>`` architecture/optimizer/loss ids from a selection trace (D8)."""
    raise NotImplementedError("resolve_selected_placeholders (D8) is deferred until D7 lands")


def reconstruct_deferred_specs(*arg: Any, **kw: Any) -> Any:  # pragma: no cover - placeholder
    """Reconstruct A-E3/A-E2 FormalDatasetSpecs bound to a predecessor selection trace (D8)."""
    raise NotImplementedError("reconstruct_deferred_specs (D8) is deferred until the predecessor chain is wired")


__all__ = [
    "execute_claimed_fit",
    "reconstruct_a_e1_specs",
    "resolve_loss_id",
    "resolve_model_factory",
    "resolve_optimizer_hyperparams",
    "run_module",
]
