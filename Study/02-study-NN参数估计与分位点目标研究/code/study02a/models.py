"""PyTorch model definitions for Study/02 research A."""

from __future__ import annotations

from collections.abc import Sequence

import torch
from torch import nn


def _activation(name: str) -> nn.Module:
    if name == "relu":
        return nn.ReLU()
    if name == "silu":
        return nn.SiLU()
    raise ValueError(f"Unsupported activation: {name}")


def _feed_forward(input_dim: int, widths: Sequence[int], output_dim: int, activation: str, dropout: float) -> nn.Sequential:
    layers: list[nn.Module] = []
    previous = input_dim
    for width in widths:
        layers.extend([nn.Linear(previous, int(width)), _activation(activation)])
        if dropout:
            layers.append(nn.Dropout(float(dropout)))
        previous = int(width)
    layers.append(nn.Linear(previous, output_dim))
    return nn.Sequential(*layers)


def build_mlp(input_dim: int, widths: Sequence[int], activation: str, dropout: float) -> nn.Module:
    return _feed_forward(input_dim, widths, 3, activation, dropout)


class DeepSets(nn.Module):
    def __init__(self, encoder: Sequence[int], pool: str, head: Sequence[int], activation: str):
        super().__init__()
        if pool not in {"mean", "sum"}:
            raise ValueError("pool must be mean or sum")
        self.pool = pool
        self.encoder = _feed_forward(1, encoder[:-1], int(encoder[-1]), activation, 0.0)
        self.head = _feed_forward(int(encoder[-1]), head, 3, activation, 0.0)

    def forward(self, values: torch.Tensor, mask: torch.Tensor | None = None) -> torch.Tensor:
        encoded = self.encoder(values)
        if mask is None:
            pooled = encoded.mean(dim=1) if self.pool == "mean" else encoded.sum(dim=1)
        else:
            weights = mask.to(encoded.dtype).unsqueeze(-1)
            total = (encoded * weights).sum(dim=1)
            if self.pool == "mean":
                pooled = total / weights.sum(dim=1).clamp_min(1.0)
            else:
                pooled = total
        return self.head(pooled)


def build_deepsets(encoder: Sequence[int], pool: str, head: Sequence[int], activation: str) -> DeepSets:
    return DeepSets(encoder, pool, head, activation)


def decode_model_output(raw: torch.Tensor, location: torch.Tensor, scale: torch.Tensor) -> torch.Tensor:
    location = location.reshape(-1)
    scale = scale.reshape(-1)
    beta = torch.exp(raw[:, 0])
    eta = scale * torch.exp(raw[:, 1])
    gamma = location - scale * torch.exp(raw[:, 2])
    return torch.stack([beta, eta, gamma], dim=1)


def trainable_parameter_count(model: nn.Module) -> int:
    return sum(parameter.numel() for parameter in model.parameters() if parameter.requires_grad)
