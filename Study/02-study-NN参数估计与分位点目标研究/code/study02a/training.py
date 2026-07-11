"""Loss and capacity contracts for deterministic Study/02 training."""

from __future__ import annotations

from collections.abc import Mapping

import torch
from torch.nn import functional as F


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
