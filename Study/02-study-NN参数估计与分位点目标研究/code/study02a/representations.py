"""Equivariant targets and frozen input representations for Study/02."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import stats


class DegenerateSampleError(ValueError):
    """Raised when a sample cannot support the frozen representation."""


@dataclass(frozen=True)
class Anchor:
    location: float
    scale: float
    z: np.ndarray


@dataclass(frozen=True)
class SetFeatures:
    """Variable-length set values with an explicit observation mask and n."""

    values: np.ndarray
    mask: np.ndarray
    n: int


def _as_sample(x: np.ndarray) -> np.ndarray:
    values = np.asarray(x, dtype=float).reshape(-1)
    if values.size < 2:
        raise DegenerateSampleError("sample must contain at least two values")
    if not np.isfinite(values).all():
        raise DegenerateSampleError("sample contains non-finite values")
    return np.sort(values)


def anchor_sample(x: np.ndarray) -> Anchor:
    values = _as_sample(x)
    location = float(values[0])
    q25, q75 = np.quantile(values, [0.25, 0.75], method="linear")
    scale = float(q75 - q25)
    if scale == 0.0:
        scale = float(values[-1] - values[0])
    if scale == 0.0:
        raise DegenerateSampleError("constant sample")
    return Anchor(location=location, scale=scale, z=(values - location) / scale)


def encode_targets(beta: float, eta: float, gamma: float, anchor: Anchor) -> np.ndarray:
    if beta <= 0 or eta <= 0:
        raise ValueError("beta and eta must be positive")
    gap = anchor.location - float(gamma)
    if gap <= 0:
        raise ValueError("gamma must be below the sample minimum")
    return np.array([
        np.log(float(beta)),
        np.log(float(eta) / anchor.scale),
        np.log(gap / anchor.scale),
    ])


def decode_targets(encoded: np.ndarray, anchor: Anchor) -> tuple[float, float, float]:
    values = np.asarray(encoded, dtype=float).reshape(3)
    beta = float(np.exp(values[0]))
    eta = float(anchor.scale * np.exp(values[1]))
    gamma = float(anchor.location - anchor.scale * np.exp(values[2]))
    return beta, eta, gamma


def half_sample_mode(x: np.ndarray) -> float:
    values = np.sort(np.asarray(x, dtype=float).reshape(-1))
    if not values.size:
        raise DegenerateSampleError("mode requires observations")
    while values.size > 2:
        width = (values.size + 1) // 2
        interval_widths = values[width - 1:] - values[: values.size - width + 1]
        start = int(np.argmin(interval_widths))
        values = values[start: start + width]
    return float(values.mean())


def kde_mode(x: np.ndarray) -> float:
    values = np.sort(np.asarray(x, dtype=float).reshape(-1))
    if values.size < 2 or values[-1] == values[0]:
        raise DegenerateSampleError("KDE mode requires non-constant observations")
    try:
        density = stats.gaussian_kde(values, bw_method="scott")
    except np.linalg.LinAlgError as error:
        raise DegenerateSampleError("KDE covariance is singular") from error
    grid = np.linspace(values[0], values[-1], 1024)
    scores = density(grid)
    return float(grid[int(np.argmax(scores))])


def _sd(values: np.ndarray) -> float:
    return float(np.std(values, ddof=1))


def _cv(values: np.ndarray) -> float:
    mean = float(np.mean(values))
    if mean == 0.0:
        raise DegenerateSampleError("CV is undefined when the mean is zero")
    return _sd(values) / abs(mean)


def _skew(values: np.ndarray) -> float:
    return float(stats.skew(values, bias=False))


def _kurtosis(values: np.ndarray) -> float:
    return float(stats.kurtosis(values, fisher=True, bias=False))


def _mode(values: np.ndarray, route_id: str) -> float:
    return kde_mode(values) if "kde_scott1024" in route_id else half_sample_mode(values)


def build_features(route_id: str, x: np.ndarray, n: int) -> np.ndarray | SetFeatures:
    values = _as_sample(x)
    if int(n) != values.size:
        raise ValueError(f"n={n} does not match sample length {values.size}")
    anchor = anchor_sample(values)
    z = anchor.z

    if route_id in {"H0_hsm", "H0_kde_scott1024"}:
        return np.array([
            values.min(), values.max(), np.median(values), np.mean(values),
            _mode(values, route_id), _cv(values), float(n),
        ], dtype=float)
    if route_id == "H1":
        return np.array([
            np.mean(values), _sd(values), np.median(values),
            _skew(values), _kurtosis(values), float(n),
        ], dtype=float)
    if route_id in {"F0eq_hsm", "F0eq_kde_scott1024"}:
        return np.array([
            z.max(), np.median(z), np.mean(z), _mode(z, route_id), _cv(z), float(n),
        ], dtype=float)
    if route_id == "F1eq":
        return np.array([
            np.mean(z), _sd(z), np.median(z), _skew(z), _kurtosis(z), float(n),
        ], dtype=float)
    if route_id == "F2":
        q10, q25, q75, q90 = np.quantile(z, [0.10, 0.25, 0.75, 0.90], method="linear")
        median = float(np.median(z))
        return np.array([
            float(n), z.max(), np.mean(z), median, _sd(z), _cv(z),
            _skew(z), _kurtosis(z), q10, q25, q75, q90, q75 - q25,
            np.median(np.abs(z - median)), half_sample_mode(z),
        ], dtype=float)
    if route_id == "V":
        return np.array(z, dtype=float)
    if route_id == "S":
        return SetFeatures(
            values=np.asarray(z, dtype=float).reshape(-1, 1),
            mask=np.ones(values.size, dtype=bool),
            n=int(n),
        )
    raise ValueError(f"Unknown Study02 feature route: {route_id}")
