"""Loss and capacity contracts for deterministic Study/02 training."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
from pathlib import Path
import random
import struct
from typing import Any, Callable, Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset

from .formal_config import (
    APPROVED_MAX_EPOCHS,
    APPROVED_MIN_EPOCHS,
    APPROVED_PATIENCE,
    EffectiveFormalConfig,
)
from .formal_data import FormalFixedBatch, FormalSetBatch


STANDARDIZED_LOSSES = {"raw_train_z_mse", "transformed_train_z_mse", "transformed_train_z_huber"}


def _standardize(values: torch.Tensor, stats: Mapping[str, torch.Tensor]) -> torch.Tensor:
    mean = stats["mean"].to(device=values.device, dtype=values.dtype)
    sd = stats["sd"].to(device=values.device, dtype=values.dtype)
    safe_sd = torch.where(sd == 0, torch.ones_like(sd), sd)
    return (values - mean) / safe_sd


def compute_loss(
    loss_id: str,
    prediction: torch.Tensor,
    target: torch.Tensor,
    training_stats: Mapping[str, torch.Tensor],
) -> torch.Tensor:
    if loss_id in STANDARDIZED_LOSSES:
        prediction = _standardize(prediction, training_stats)
        target = _standardize(target, training_stats)
    if loss_id in {"raw_train_z_mse", "transformed_unscaled_mse", "transformed_train_z_mse"}:
        return F.mse_loss(prediction, target)
    if loss_id == "transformed_train_z_huber":
        return F.huber_loss(prediction, target, delta=1.0)
    raise ValueError(f"Unknown frozen loss: {loss_id}")


def select_independent_capacity(joint_count: int, candidate_counts: Mapping[str, int]) -> tuple[str, int]:
    ceiling = 1.05 * int(joint_count)
    eligible = [(identifier, int(count)) for identifier, count in candidate_counts.items() if int(count) <= ceiling]
    if not eligible:
        raise ValueError("No independent candidate satisfies the frozen capacity ceiling")
    return min(eligible, key=lambda item: (abs(item[1] - joint_count), item[0]))


@dataclass(frozen=True)
class CandidateSpec:
    architecture_id: str
    optimizer_id: str
    architecture: dict[str, Any]
    optimizer: dict[str, Any]


@dataclass(frozen=True)
class SearchSpecs:
    stage1: tuple[CandidateSpec, ...]
    architectures: Mapping[str, dict[str, Any]]
    stage2_rule: Mapping[str, Any]

    def expand_stage2(self, architecture_ids: Sequence[str]) -> tuple[CandidateSpec, ...]:
        selected = sorted(set(architecture_ids))
        expected = int(self.stage2_rule["select_top_architectures"])
        if len(selected) != expected:
            raise ValueError(f"Stage 2 requires exactly {expected} unique architectures")
        candidates = []
        for architecture_id in selected:
            architecture = self.architectures.get(architecture_id)
            if architecture is None:
                raise ValueError(f"Unknown architecture selected for stage 2: {architecture_id}")
            for optimizer in self.stage2_rule["optimizer_candidates"]:
                candidates.append(CandidateSpec(
                    architecture_id=architecture_id,
                    optimizer_id=str(optimizer["id"]),
                    architecture=dict(architecture),
                    optimizer=dict(optimizer),
                ))
        return tuple(candidates)


@dataclass(frozen=True)
class FitResult:
    predictions: torch.Tensor
    checkpoint_sha256: str
    best_validation_loss: float
    best_epoch: int
    actual_epochs: int = 0
    validation_loss_history: tuple[float, ...] = ()
    early_stop_reason: str = "max_epochs"
    hit_epoch_ceiling: bool = False
    checkpoint_bytes: bytes = b""


@dataclass(frozen=True)
class SearchResult:
    winner_id: str
    rows: tuple[dict[str, Any], ...]


def seed_everything(seed: int) -> None:
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)


def expand_search_specs(route_id: str, search_config: Mapping[str, Any]) -> SearchSpecs:
    key = "deepsets_stage1_architectures" if route_id == "S" else "mlp_stage1_architectures"
    architectures = {str(item["id"]): dict(item) for item in search_config[key]}
    optimizer = {"id": "stage1", **dict(search_config["stage1_optimizer"])}
    stage1 = tuple(
        CandidateSpec(identifier, "stage1", architecture, optimizer)
        for identifier, architecture in sorted(architectures.items())
    )
    if len(stage1) != 12:
        raise ValueError(f"Frozen stage 1 must contain 12 architectures, got {len(stage1)}")
    return SearchSpecs(stage1, architectures, search_config["stage2_rule"])


def _checkpoint_canonical_bytes(state: Mapping[str, torch.Tensor]) -> bytes:
    """Deterministic, loadable, pickle-free checkpoint bytes.

    Each parameter (sorted by name) is encoded with explicit length prefixes so the
    bytes are unambiguously parseable by :func:`load_checkpoint`:

        uint32 name_len | name(utf-8) | uint32 dtype_len | dtype(ascii)
        | uint32 ndim | ndim*uint64 shape | uint64 nbytes | raw tensor bytes (C order)

    ``sha256`` of these bytes is ``_checkpoint_hash``; the same bytes are written to
    ``checkpoint.pt``. This is deliberately *not* ``torch.save`` so the hash is stable
    across processes and library versions, while remaining loadable via the decoder.
    """
    parts: list[bytes] = []
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        arr = tensor.numpy()
        name_bytes = name.encode("utf-8")
        dtype_bytes = str(arr.dtype).encode("ascii")
        shape = arr.shape
        parts.append(struct.pack("<I", len(name_bytes)))
        parts.append(name_bytes)
        parts.append(struct.pack("<I", len(dtype_bytes)))
        parts.append(dtype_bytes)
        parts.append(struct.pack("<I", len(shape)))
        if shape:
            parts.append(struct.pack("<%dQ" % len(shape), *shape))
        raw = arr.tobytes(order="C")
        parts.append(struct.pack("<Q", len(raw)))
        parts.append(raw)
    return b"".join(parts)


def load_checkpoint(source: bytes | str | Path) -> dict[str, torch.Tensor]:
    """Decode canonical checkpoint bytes (or a path to them) back into a state dict.

    Inverse of :func:`_checkpoint_canonical_bytes`; used by Task 9d to restore a
    selected fit's model for one-shot test evaluation.
    """
    if isinstance(source, (str, Path)):
        source = Path(source).read_bytes()
    pos = 0
    total = len(source)
    state: dict[str, torch.Tensor] = {}
    while pos < total:
        (name_len,) = struct.unpack_from("<I", source, pos); pos += 4
        name = source[pos:pos + name_len].decode("utf-8"); pos += name_len
        (dtype_len,) = struct.unpack_from("<I", source, pos); pos += 4
        dtype = source[pos:pos + dtype_len].decode("ascii"); pos += dtype_len
        (ndim,) = struct.unpack_from("<I", source, pos); pos += 4
        shape = struct.unpack_from("<%dQ" % ndim, source, pos) if ndim else ()
        pos += 8 * ndim
        (nbytes,) = struct.unpack_from("<Q", source, pos); pos += 8
        raw = source[pos:pos + nbytes]; pos += nbytes
        array = np.frombuffer(raw, dtype=np.dtype(dtype)).reshape(shape).copy()
        state[name] = torch.from_numpy(array)
    if pos != total:
        raise ValueError("checkpoint bytes have a trailing/short tail; not canonical")
    return state


def _checkpoint_hash(state: Mapping[str, torch.Tensor]) -> str:
    return hashlib.sha256(_checkpoint_canonical_bytes(state)).hexdigest()


def _fit_deterministic_candidate(
    model_factory: Callable[[], nn.Module],
    training_inputs: tuple[torch.Tensor, ...],
    training_targets: torch.Tensor,
    validation_targets: torch.Tensor,
    forward_batch: Callable[[nn.Module, tuple[torch.Tensor, ...]], torch.Tensor],
    forward_validation: Callable[[nn.Module], torch.Tensor],
    *,
    seed: int,
    max_epochs: int,
    min_epochs: int,
    patience: int,
    loss_id: str,
    lr: float,
    weight_decay: float,
    batch_size: int,
    optimizer_id: str = "adamw",
) -> FitResult:
    if optimizer_id == "adamw":
        optimizer_cls = torch.optim.AdamW
    elif optimizer_id == "adam":
        optimizer_cls = torch.optim.Adam
    else:
        raise ValueError(f"unsupported frozen optimizer id: {optimizer_id!r}")
    seed_everything(seed)
    stats = {
        "mean": training_targets.mean(dim=0),
        "sd": training_targets.std(dim=0, unbiased=False),
    }
    model = model_factory()
    optimizer = optimizer_cls(model.parameters(), lr=lr, weight_decay=weight_decay)
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        TensorDataset(*training_inputs, training_targets),
        batch_size=min(int(batch_size), len(training_targets)),
        shuffle=True,
        generator=generator,
    )
    best_loss = float("inf")
    best_epoch = -1
    best_state: dict[str, torch.Tensor] | None = None
    stale_epochs = 0
    validation_loss_history: list[float] = []

    for epoch in range(int(max_epochs)):
        model.train()
        for batch in loader:
            inputs = tuple(batch[:-1])
            targets = batch[-1]
            optimizer.zero_grad(set_to_none=True)
            loss = compute_loss(loss_id, forward_batch(model, inputs), targets, stats)
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = float(
                compute_loss(loss_id, forward_validation(model), validation_targets, stats)
            )
        if not np.isfinite(validation_loss):
            raise RuntimeError("Training produced a non-finite validation loss")
        validation_loss_history.append(validation_loss)
        if validation_loss < best_loss:
            best_loss = validation_loss
            best_epoch = epoch
            best_state = {name: value.detach().clone() for name, value in model.state_dict().items()}
            stale_epochs = 0
        else:
            stale_epochs += 1
        if epoch + 1 >= int(min_epochs) and stale_epochs >= int(patience):
            break

    if best_state is None:
        raise RuntimeError("Training produced no checkpoint")
    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        predictions = forward_validation(model).detach().clone()
    actual_epochs = len(validation_loss_history)
    hit_epoch_ceiling = actual_epochs == int(max_epochs)
    return FitResult(
        predictions=predictions,
        checkpoint_sha256=_checkpoint_hash(best_state),
        best_validation_loss=best_loss,
        best_epoch=best_epoch,
        actual_epochs=actual_epochs,
        validation_loss_history=tuple(validation_loss_history),
        early_stop_reason="max_epochs" if hit_epoch_ceiling else "patience_exhausted",
        hit_epoch_ceiling=hit_epoch_ceiling,
        checkpoint_bytes=_checkpoint_canonical_bytes(best_state),
    )


def fit_candidate(
    model_factory: Callable[[], nn.Module],
    training_data: tuple[torch.Tensor, torch.Tensor],
    validation_data: tuple[torch.Tensor, torch.Tensor],
    *,
    seed: int,
    max_epochs: int = 500,
    min_epochs: int = 50,
    patience: int = 40,
    loss_id: str = "transformed_train_z_huber",
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    batch_size: int = 512,
    optimizer_id: str = "adamw",
) -> FitResult:
    train_x, train_y = training_data
    validation_x, validation_y = validation_data
    return _fit_deterministic_candidate(
        model_factory,
        (train_x,),
        train_y,
        validation_y,
        lambda model, inputs: model(inputs[0]),
        lambda model: model(validation_x),
        seed=seed,
        max_epochs=max_epochs,
        min_epochs=min_epochs,
        patience=patience,
        loss_id=loss_id,
        lr=lr,
        weight_decay=weight_decay,
        batch_size=batch_size,
        optimizer_id=optimizer_id,
    )


def _require_approved_formal_config(effective_config: EffectiveFormalConfig) -> None:
    """Fail closed unless the sole effective formal epoch contract is supplied."""

    if not isinstance(effective_config, EffectiveFormalConfig) or (
        effective_config.max_epochs,
        effective_config.min_epochs,
        effective_config.patience,
    ) != (APPROVED_MAX_EPOCHS, APPROVED_MIN_EPOCHS, APPROVED_PATIENCE):
        raise ValueError("formal fits require the approved 100/50/40 epoch contract")


def fit_fixed_candidate(
    model_factory: Callable[[], nn.Module],
    training_data: FormalFixedBatch,
    validation_data: FormalFixedBatch,
    effective_config: EffectiveFormalConfig,
    *,
    seed: int,
    loss_id: str = "transformed_train_z_huber",
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    batch_size: int = 512,
    optimizer_id: str = "adamw",
) -> FitResult:
    """Fit a fixed-route MLP under the sole approved formal epoch contract."""

    _require_approved_formal_config(effective_config)
    if len(training_data) == 0 or len(validation_data) == 0:
        raise ValueError("formal fixed training and validation batches must be non-empty")
    return _fit_deterministic_candidate(
        model_factory,
        (training_data.features,),
        training_data.targets,
        validation_data.targets,
        lambda model, inputs: model(inputs[0]),
        lambda model: model(validation_data.features),
        seed=seed,
        max_epochs=effective_config.max_epochs,
        min_epochs=effective_config.min_epochs,
        patience=effective_config.patience,
        loss_id=loss_id,
        lr=lr,
        weight_decay=weight_decay,
        batch_size=batch_size,
        optimizer_id=optimizer_id,
    )


def fit_set_candidate(
    model_factory: Callable[[], nn.Module],
    training_data: FormalSetBatch,
    validation_data: FormalSetBatch,
    effective_config: EffectiveFormalConfig,
    *,
    seed: int,
    loss_id: str = "transformed_train_z_huber",
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    batch_size: int = 512,
    optimizer_id: str = "adamw",
) -> FitResult:
    """Fit a DeepSets candidate under the sole approved formal epoch contract."""

    _require_approved_formal_config(effective_config)
    if len(training_data) == 0 or len(validation_data) == 0:
        raise ValueError("formal set training and validation batches must be non-empty")
    return _fit_deterministic_candidate(
        model_factory,
        (
            training_data.values,
            training_data.mask,
            training_data.model_n,
        ),
        training_data.targets,
        validation_data.targets,
        lambda model, inputs: model(inputs[0], inputs[1], inputs[2]),
        lambda model: model(
            validation_data.values,
            validation_data.mask,
            validation_data.model_n,
        ),
        seed=seed,
        max_epochs=effective_config.max_epochs,
        min_epochs=effective_config.min_epochs,
        patience=effective_config.patience,
        loss_id=loss_id,
        lr=lr,
        weight_decay=weight_decay,
        batch_size=batch_size,
        optimizer_id=optimizer_id,
    )


def run_two_stage_search(
    route_id: str,
    training_data: tuple[torch.Tensor, torch.Tensor],
    validation_data: tuple[torch.Tensor, torch.Tensor],
    search_config: Mapping[str, Any],
    model_factory: Callable[[CandidateSpec], nn.Module],
    validation_scorer: Callable[[FitResult], float],
) -> SearchResult:
    specs = expand_search_specs(route_id, search_config)
    seeds = [int(seed) for seed in search_config["screening_seeds"]]
    rows: list[dict[str, Any]] = []

    def evaluate(candidates: Sequence[CandidateSpec]) -> None:
        for candidate in candidates:
            for seed in seeds:
                optimizer = candidate.optimizer
                result = fit_candidate(
                    lambda candidate=candidate: model_factory(candidate),
                    training_data,
                    validation_data,
                    seed=seed,
                    max_epochs=int(search_config["training"]["max_epochs"]),
                    min_epochs=int(search_config["training"]["min_epochs"]),
                    patience=int(search_config["training"]["early_stopping_patience"]),
                    lr=float(optimizer["lr"]),
                    weight_decay=float(optimizer["weight_decay"]),
                    batch_size=int(optimizer["batch_size"]),
                )
                validation_score = float(validation_scorer(result))
                if not np.isfinite(validation_score):
                    raise ValueError("validation_scorer returned a non-finite score")
                rows.append({
                    "architecture_id": candidate.architecture_id,
                    "optimizer_id": candidate.optimizer_id,
                    "seed": seed,
                    "validation_loss": result.best_validation_loss,
                    "validation_score": validation_score,
                    "checkpoint_sha256": result.checkpoint_sha256,
                })

    evaluate(specs.stage1)
    stage1_means = {
        architecture_id: float(np.mean([
            row["validation_score"] for row in rows
            if row["architecture_id"] == architecture_id and row["optimizer_id"] == "stage1"
        ]))
        for architecture_id in specs.architectures
    }
    top = sorted(stage1_means, key=lambda identifier: (stage1_means[identifier], identifier))[:4]
    evaluate(specs.expand_stage2(top))
    candidate_ids = sorted({(row["architecture_id"], row["optimizer_id"]) for row in rows if row["optimizer_id"] != "stage1"})
    means = {
        pair: float(np.mean([
            row["validation_score"] for row in rows
            if (row["architecture_id"], row["optimizer_id"]) == pair
        ]))
        for pair in candidate_ids
    }
    winner = min(means, key=lambda pair: (means[pair], pair[0], pair[1]))
    return SearchResult(f"{winner[0]}:{winner[1]}", tuple(rows))
