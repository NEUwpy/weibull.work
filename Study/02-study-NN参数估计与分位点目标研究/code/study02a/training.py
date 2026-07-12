"""Loss and capacity contracts for deterministic Study/02 training."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import hashlib
import random
from typing import Any, Callable, Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset


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


def _checkpoint_hash(state: Mapping[str, torch.Tensor]) -> str:
    digest = hashlib.sha256()
    for name in sorted(state):
        tensor = state[name].detach().cpu().contiguous()
        digest.update(name.encode("utf-8"))
        digest.update(str(tensor.dtype).encode("ascii"))
        digest.update(np.asarray(tensor.shape, dtype=np.int64).tobytes())
        digest.update(tensor.numpy().tobytes())
    return digest.hexdigest()


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
) -> FitResult:
    seed_everything(seed)
    train_x, train_y = training_data
    validation_x, validation_y = validation_data
    stats = {"mean": train_y.mean(dim=0), "sd": train_y.std(dim=0, unbiased=False)}
    model = model_factory()
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=weight_decay)
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        TensorDataset(train_x, train_y),
        batch_size=min(int(batch_size), len(train_x)),
        shuffle=True,
        generator=generator,
    )
    best_loss = float("inf")
    best_epoch = -1
    best_state: dict[str, torch.Tensor] | None = None
    stale_epochs = 0

    for epoch in range(int(max_epochs)):
        model.train()
        for batch_x, batch_y in loader:
            optimizer.zero_grad(set_to_none=True)
            loss = compute_loss(loss_id, model(batch_x), batch_y, stats)
            loss.backward()
            optimizer.step()
        model.eval()
        with torch.no_grad():
            validation_loss = float(compute_loss(loss_id, model(validation_x), validation_y, stats))
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
        predictions = model(validation_x).detach().clone()
    return FitResult(predictions, _checkpoint_hash(best_state), best_loss, best_epoch)


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
