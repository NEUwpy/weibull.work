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


class IndependentContainer(nn.Module):
    """Three parameter-isolated single-output MLP subnetworks (A-E3 output-form contract).

    Holds a ``ModuleList`` of three independent MLP subnetworks, each built from the
    SAME frozen hidden spec (one m0X architecture's widths/activation/dropout) but
    terminating in a ``output_dim=1`` head. ``forward`` concatenates the three scalar
    outputs column-wise so the raw output shape stays ``(N, 3)`` -- the exact contract
    :func:`decode_model_output` already consumes -- while the parameters are fully
    partitioned across the three Weibull outputs (no shared trunk).

    Used by the ``independent_capacity_matched`` arm of the A-E3 output_form decision.
    The companion ``joint`` arm is a single :func:`build_mlp` (shared trunk, 3-output
    head); the two are structurally distinct (different state_dict key namespaces,
    different parameter matrices) so the output_form suffix selects a real model
    contract, not a label.
    """

    def __init__(self, input_dim: int, widths: Sequence[int], activation: str, dropout: float) -> None:
        super().__init__()
        self.subnetworks = nn.ModuleList(
            [_feed_forward(input_dim, widths, 1, activation, dropout) for _ in range(3)]
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return torch.cat([subnet(x) for subnet in self.subnetworks], dim=1)


def build_independent_container(
    input_dim: int, widths: Sequence[int], activation: str, dropout: float,
) -> IndependentContainer:
    """Build a three-subnetwork independent container (A-E3 output-form contract)."""
    return IndependentContainer(input_dim, widths, activation, dropout)


class DeepSets(nn.Module):
    def __init__(self, encoder: Sequence[int], pool: str, head: Sequence[int], activation: str):
        super().__init__()
        if pool not in {"mean", "sum"}:
            raise ValueError("pool must be mean or sum")
        self.pool = pool
        self.encoder = _feed_forward(1, encoder[:-1], int(encoder[-1]), activation, 0.0)
        self.head = _feed_forward(int(encoder[-1]) + 1, head, 3, activation, 0.0)

    def forward(self, values: torch.Tensor, mask: torch.Tensor, n: torch.Tensor) -> torch.Tensor:
        encoded = self.encoder(values)
        weights = mask.to(encoded.dtype).unsqueeze(-1)
        total = (encoded * weights).sum(dim=1)
        if self.pool == "mean":
            pooled = total / weights.sum(dim=1).clamp_min(1.0)
        else:
            pooled = total
        explicit_n = n.to(device=pooled.device, dtype=pooled.dtype).reshape(-1, 1)
        return self.head(torch.cat([pooled, explicit_n], dim=1))


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
