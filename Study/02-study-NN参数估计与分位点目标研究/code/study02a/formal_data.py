"""Formal fixed-route and variable-length set data contracts for Study/02."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np
import torch

from .representations import SetFeatures


@dataclass(frozen=True)
class FormalSetExample:
    """One transformed formal example for the variable-length S route."""

    features: SetFeatures
    target: np.ndarray
    location: float
    scale: float


@dataclass(frozen=True)
class FormalSetBatch:
    """A padded, mask-preserving batch accepted by :class:`DeepSets`."""

    values: torch.Tensor
    mask: torch.Tensor
    n: torch.Tensor
    targets: torch.Tensor
    location: torch.Tensor
    scale: torch.Tensor

    def __len__(self) -> int:
        return int(self.values.shape[0])


def _validated_example(item: FormalSetExample) -> tuple[np.ndarray, np.ndarray, int, np.ndarray, float, float]:
    if not isinstance(item, FormalSetExample):
        raise ValueError("set batch items must be FormalSetExample instances")
    features = item.features
    if not isinstance(features, SetFeatures):
        raise ValueError("example features must be SetFeatures")
    if isinstance(features.n, (bool, np.bool_)) or not isinstance(features.n, (int, np.integer)):
        raise ValueError("SetFeatures.n must be a positive integer")
    n = int(features.n)
    if n <= 0:
        raise ValueError("SetFeatures.n must be positive")

    values = np.asarray(features.values)
    mask = np.asarray(features.mask)
    if values.shape != (n, 1):
        raise ValueError(f"values must have shape ({n}, 1), got {values.shape}")
    if mask.shape != (n,):
        raise ValueError(f"mask must have shape ({n},), got {mask.shape}")
    if mask.dtype.kind != "b":
        raise ValueError("mask must be boolean")
    if int(mask.sum()) != n:
        raise ValueError("original mask count must equal n")
    if not np.isfinite(values).all():
        raise ValueError("set values must be finite")

    target = np.asarray(item.target)
    if target.shape != (3,):
        raise ValueError(f"target must have shape (3,), got {target.shape}")
    if not np.isfinite(target).all():
        raise ValueError("target must be finite")
    location = float(item.location)
    scale = float(item.scale)
    if not np.isfinite(location) or not np.isfinite(scale):
        raise ValueError("anchor location and scale must be finite")
    if scale <= 0.0:
        raise ValueError("anchor scale must be positive")
    return values, mask, n, target, location, scale


def collate_set_features(items: Sequence[FormalSetExample]) -> FormalSetBatch:
    """Validate and pad formal S-route examples without encoding ``n`` as a row."""

    if not items:
        raise ValueError("cannot collate an empty set batch")
    validated = [_validated_example(item) for item in items]
    batch_size = len(validated)
    max_n = max(item[2] for item in validated)
    values = np.zeros((batch_size, max_n, 1), dtype=np.float32)
    mask = np.zeros((batch_size, max_n), dtype=bool)
    n_values = np.empty(batch_size, dtype=np.float32)
    targets = np.empty((batch_size, 3), dtype=np.float32)
    locations = np.empty(batch_size, dtype=np.float32)
    scales = np.empty(batch_size, dtype=np.float32)

    for row, (item_values, item_mask, n, target, location, scale) in enumerate(validated):
        values[row, :n, :] = item_values
        mask[row, :n] = item_mask
        n_values[row] = n
        targets[row] = target
        locations[row] = location
        scales[row] = scale

    batch = FormalSetBatch(
        values=torch.from_numpy(values),
        mask=torch.from_numpy(mask),
        n=torch.from_numpy(n_values),
        targets=torch.from_numpy(targets),
        location=torch.from_numpy(locations),
        scale=torch.from_numpy(scales),
    )
    if not torch.equal(batch.mask.sum(dim=1).to(batch.n.dtype), batch.n):
        raise RuntimeError("collated mask counts do not equal explicit n")
    return batch
