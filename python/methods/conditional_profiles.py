"""Conditional diagnostics for MLE/WMLE; these do not run joint estimators.

Symbols follow the method documents: beta=shape, eta=scale, gamma=location.
An explicit weight provider preserves the identity of an archived WMLE table.
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp


def _distances(data, gamma):
    x = np.asarray(data, dtype=float)
    d = x - gamma
    if x.ndim != 1 or len(x) < 2 or not np.all(np.isfinite(x)):
        raise ValueError("Expected a finite one-dimensional sample of at least two points")
    if not np.isfinite(gamma) or gamma < 0 or np.any(d <= 0):
        raise ValueError("Conditional location must satisfy 0 <= gamma < min(data)")
    return d


def _shape(logd, weight=1.0, lower=0.0, upper=None):
    z = logd - logd.mean()

    def score(beta):
        w = np.exp(beta * (z - z.max()))
        w /= w.sum()
        return float(weight / beta - w @ z)

    if np.ptp(logd) == 0:
        return None  # No finite shape root for an equal-valued sample.
    if lower > 0 and score(lower) <= 0:
        return float(lower), score(lower), True
    if upper is None:
        upper = 2.0
        while score(upper) > 0:
            upper *= 2
            if not np.isfinite(upper):
                return None
    elif score(upper) >= 0:
        return None  # WMLE needs an interior T1 zero, never a clamped boundary.
    beta = float(brentq(score, max(lower, 1e-8), upper, xtol=1e-11, rtol=2e-14))
    return beta, score(beta), False


def mle_profile(data, gamma, *, shape_lower=1.0):
    """Maximize the standard likelihood at fixed gamma over beta>=shape_lower.

    shape_lower=1 is the R00 diagnostic domain. shape_lower=0 is an explicitly
    unrestricted diagnostic (also needed by the distinct MMLE construction).
    At beta=1 the scale is recalculated; the shape score need not be zero.
    """
    if shape_lower < 0 or not np.isfinite(shape_lower):
        raise ValueError("shape_lower must be finite and nonnegative")
    d = _distances(data, gamma)
    t = np.log(d)
    solution = _shape(t, lower=shape_lower)
    if solution is None:
        return None
    beta, score, boundary = solution
    z = t - t.mean()
    log_mean_power = logsumexp(beta * z) - np.log(len(d))
    log_eta = t.mean() + log_mean_power / beta
    ll = len(d) * (np.log(beta) - t.mean() - log_mean_power - 1)
    w = np.exp(beta * (z - z.max()))
    w /= w.sum()
    grad = len(d) * (beta * float(w @ (1 / d)) - (beta - 1) * np.mean(1 / d))
    return dict(beta=beta, eta=float(np.exp(log_eta)), ll=float(ll),
                location_score=float(grad), shape_score=score,
                shape_at_lower_boundary=boundary)


def wmle_residuals(data, beta, gamma, weights):
    """Evaluate T1,T2 with the caller's J2/J3; beta/gamma may broadcast as grids."""
    x = np.asarray(data, dtype=float)
    b, g = np.broadcast_arrays(np.asarray(beta, float), np.asarray(gamma, float))
    d = x - g[..., None]
    if (x.ndim != 1 or len(x) < 2 or not np.all(np.isfinite(x))
            or np.any(~np.isfinite(b)) or np.any(b <= 0)
            or np.any(~np.isfinite(g)) or np.any(g < 0) or np.any(d <= 0)):
        raise ValueError("Invalid WMLE residual sample or parameter")
    t = np.log(d)
    z = t - t.mean(axis=-1, keepdims=True)
    powers = b[..., None] * z
    w = np.exp(powers - logsumexp(powers, axis=-1, keepdims=True))
    t1 = weights.get_weight_j2(len(x)) / b - np.sum(w * z, axis=-1)
    log_ratio = (t.mean(axis=-1) + logsumexp(powers, axis=-1)
                 - logsumexp((b[..., None] - 1) * z, axis=-1))
    j3 = np.asarray([weights.get_weight_j3(len(x), float(v)) for v in b.flat]).reshape(b.shape)
    t2 = np.mean(1 / d, axis=-1) * np.exp(log_ratio) - j3
    if b.ndim == 0:
        return float(t1), float(t2)
    return t1, t2


def wmle_profile(data, gamma, weights):
    """Evaluate T2 along an interior T1=0 branch with the solver's shape cap.

    None means no conditional T1 zero in 0<beta<weights.SHAPE_UPPER. It does
    not establish absence of a joint solution at another location.
    """
    d = _distances(data, gamma)
    n = len(d)
    j1, j2 = weights.get_weight_j1(n), weights.get_weight_j2(n)
    t = np.log(d)
    solution = _shape(t, weight=j2, upper=weights.SHAPE_UPPER)
    if solution is None:
        return None
    beta, _, _ = solution
    log_eta = t.mean() + (logsumexp(beta * (t - t.mean())) - np.log(n * j1)) / beta
    t1, t2 = wmle_residuals(data, beta, gamma, weights)
    j3 = float(weights.get_weight_j3(n, beta))
    return dict(beta=beta, eta=float(np.exp(log_eta)), t1=t1, t2=t2,
                inverse_distance_product=t2 + j3, j1=float(j1), j2=float(j2), j3=j3,
                j3_clamped=bool(beta < .1 or beta > 5))
