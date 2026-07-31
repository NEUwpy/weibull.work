"""D-route target encoding/decoding for direct x_{0.95} prediction.

Protocol (§1): input = sorted sample V (same anchor as P-route); target =
(x_{0.95} - a) / s  where a = sample min, s = IQR (or range fallback).
Training standardizes by training-set mean/sd; decode reverses both steps.

Equivariance: the anchored target is invariant under unit change and
translation — verified by roundtrip tests.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from study02a.representations import DegenerateSampleError, anchor_sample, Anchor


def encode_d_target(x_095: float, anchor: Anchor) -> float:
    """Encode the true x_{0.95} as an anchored scalar.

    target = (x_{0.95} - a) / s

    where a = sample min (anchor.location), s = IQR (anchor.scale).
    This is scale- and translation-equivariant: scaling the sample and
    x_{0.95} by factor k and shifting by c yields the same anchored target.
    """
    return float((float(x_095) - anchor.location) / anchor.scale)


def decode_d_target(encoded: float, anchor: Anchor) -> float:
    """Decode a (possibly standardized) anchored scalar back to x_{0.95}.

    x_{0.95} = a + s * y
    """
    return float(anchor.location + anchor.scale * float(encoded))


def encode_d_batch(x_095_values: np.ndarray, anchors: list[Anchor]) -> np.ndarray:
    """Encode a batch of true x_{0.95} values given per-sample anchors."""
    values = np.asarray(x_095_values, dtype=float).ravel()
    if len(values) != len(anchors):
        raise ValueError("x_095_values and anchors must have matching lengths")
    encoded = np.array([
        encode_d_target(float(v), a)
        for v, a in zip(values, anchors)
    ], dtype=float)
    return encoded


def decode_d_batch(encoded: np.ndarray, anchors: list[Anchor]) -> np.ndarray:
    """Decode a batch of encoded x_{0.95} predictions."""
    values = np.asarray(encoded, dtype=float).ravel()
    if len(values) != len(anchors):
        raise ValueError("encoded and anchors must have matching lengths")
    decoded = np.array([
        decode_d_target(float(v), a)
        for v, a in zip(values, anchors)
    ], dtype=float)
    return decoded


@dataclass(frozen=True)
class DTrainingStats:
    """Training-set statistics for standardizing D-route targets."""
    mean: float
    sd: float


def compute_d_stats(encoded_targets: np.ndarray) -> DTrainingStats:
    """Compute standardization statistics from encoded training targets."""
    values = np.asarray(encoded_targets, dtype=float).ravel()
    if values.size == 0:
        raise ValueError("cannot compute stats from empty targets")
    mean = float(np.mean(values))
    sd = float(np.std(values, ddof=0))
    return DTrainingStats(mean=mean, sd=sd)


def safe_sd(sd: float) -> float:
    """Return sd if positive, else 1.0 to avoid division by zero in standardization."""
    return float(sd) if sd > 0.0 else 1.0


def standardize_d(encoded: np.ndarray, stats: DTrainingStats) -> np.ndarray:
    """Standardize encoded targets: (y - mean) / sd."""
    values = np.asarray(encoded, dtype=float).ravel()
    safe = safe_sd(stats.sd)
    return (values - stats.mean) / safe


def unstandardize_d(standardized: np.ndarray, stats: DTrainingStats) -> np.ndarray:
    """Reverse standardization: y * sd + mean."""
    values = np.asarray(standardized, dtype=float).ravel()
    safe = safe_sd(stats.sd)
    return values * safe + stats.mean
