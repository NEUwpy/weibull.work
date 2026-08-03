"""D-route training adapter — reuse study02a infrastructure with output_dim=1.

The D-route uses the same input representation (V = sorted sample z-scores),
same equivariant anchor, and same training loop as P-route.  The only
structural difference: the network outputs a scalar (encoded x_{0.95})
instead of three parameters.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Callable, Sequence

import numpy as np
import torch
from torch import nn
from torch.nn import functional as F
from torch.utils.data import DataLoader, TensorDataset

from study02a.models import _feed_forward
from study02a.training import (
    FitResult,
    _checkpoint_canonical_bytes,
    _checkpoint_hash,
    seed_everything,
)


def build_d_mlp(
    input_dim: int,
    widths: Sequence[int],
    activation: str = "silu",
    dropout: float = 0.1,
) -> nn.Module:
    """Build a fixed-n MLP that outputs a single encoded x_{0.95} value.

    Identical to study02a.models.build_mlp except output_dim=1 instead of 3.
    """
    return _feed_forward(input_dim, widths, 1, activation, dropout)


def compute_d_loss(
    prediction: torch.Tensor,
    target: torch.Tensor,
    loss_id: str = "huber",
) -> torch.Tensor:
    """Compute loss on standardized scalar predictions.

    Args:
        prediction: (N, 1) or (N,) standardized encoded predictions.
        target: (N, 1) or (N,) standardized encoded targets.
        loss_id: "mse" or "huber".
    """
    pred = prediction.reshape(-1)
    tgt = target.reshape(-1)
    if loss_id == "mse":
        return F.mse_loss(pred, tgt)
    if loss_id == "huber":
        return F.huber_loss(pred, tgt, delta=1.0)
    raise ValueError(f"Unknown D-route loss: {loss_id}")


def fit_d_model(
    model_factory: Callable[[], nn.Module],
    training_inputs: torch.Tensor,
    training_targets: torch.Tensor,
    validation_inputs: torch.Tensor,
    validation_targets: torch.Tensor,
    *,
    seed: int,
    max_epochs: int = 500,
    min_epochs: int = 50,
    patience: int = 40,
    loss_id: str = "huber",
    lr: float = 1e-3,
    weight_decay: float = 1e-4,
    batch_size: int = 512,
    optimizer_id: str = "adamw",
) -> FitResult:
    """Fit a D-route model reusing the deterministic training loop.

    Same algorithm as study02a.training.fit_candidate but the target is a
    scalar (standardized encoded x_{0.95}) and standardization stats are
    computed from the training targets directly (mean/sd of encoded values).

    Returns a FitResult with predictions in standardized space; caller
    must un-standardize and decode through the sample anchors.
    """
    if optimizer_id == "adamw":
        optimizer_cls = torch.optim.AdamW
    elif optimizer_id == "adam":
        optimizer_cls = torch.optim.Adam
    else:
        raise ValueError(f"unsupported optimizer: {optimizer_id!r}")

    seed_everything(seed)
    model = model_factory()
    optimizer = optimizer_cls(model.parameters(), lr=lr, weight_decay=weight_decay)
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(
        TensorDataset(training_inputs, training_targets),
        batch_size=min(int(batch_size), len(training_targets)),
        shuffle=True,
        generator=generator,
    )

    best_loss = float("inf")
    best_epoch = -1
    best_state: dict[str, torch.Tensor] | None = None
    stale_epochs = 0
    validation_loss_history: list[float] = []

    def _d_loss(pred: torch.Tensor, tgt: torch.Tensor) -> torch.Tensor:
        return compute_d_loss(pred, tgt, loss_id)

    for epoch in range(int(max_epochs)):
        model.train()
        for batch in loader:
            inputs = batch[0]
            targets = batch[-1]
            optimizer.zero_grad(set_to_none=True)
            loss = _d_loss(model(inputs), targets)
            loss.backward()
            optimizer.step()

        model.eval()
        with torch.no_grad():
            val_loss = float(_d_loss(model(validation_inputs), validation_targets))

        if not np.isfinite(val_loss):
            raise RuntimeError("D-route training produced non-finite validation loss")

        validation_loss_history.append(val_loss)
        if val_loss < best_loss:
            best_loss = val_loss
            best_epoch = epoch
            best_state = {
                name: value.detach().clone()
                for name, value in model.state_dict().items()
            }
            stale_epochs = 0
        else:
            stale_epochs += 1

        if epoch + 1 >= int(min_epochs) and stale_epochs >= int(patience):
            break

    if best_state is None:
        raise RuntimeError("D-route training produced no checkpoint")

    model.load_state_dict(best_state)
    model.eval()
    with torch.no_grad():
        predictions = model(validation_inputs).detach().clone()

    actual_epochs = len(validation_loss_history)
    hit_ceiling = actual_epochs == int(max_epochs)

    return FitResult(
        predictions=predictions,
        checkpoint_sha256=_checkpoint_hash(best_state),
        best_validation_loss=best_loss,
        best_epoch=best_epoch,
        actual_epochs=actual_epochs,
        validation_loss_history=tuple(validation_loss_history),
        early_stop_reason="max_epochs" if hit_ceiling else "patience_exhausted",
        hit_epoch_ceiling=hit_ceiling,
        checkpoint_bytes=_checkpoint_canonical_bytes(best_state),
    )
