"""
mdm_core.py
===========
Core routines for the Minimum Discrepancy Method (MDM) applied to the
three-parameter Weibull distribution, and the gradient-offset (delta)
variant studied in this project.

Three-parameter Weibull CDF:
    F(t) = 1 - exp( -((t - gamma)/eta)^beta ),  t > gamma

MDM idea
--------
Sort the failure times t_(1) <= ... <= t_(n). Assign median-rank plotting
positions via Bernard's approximation

    F_i = (i - 0.3) / (n + 0.4),     x_i = -ln(1 - F_i).

For any (beta, gamma) the per-point "pseudo scale" is

    eta_i(beta, gamma) = (t_i - gamma) / x_i**(1/beta).

If (beta, gamma) are correct, all eta_i should coincide. MDM therefore
minimises the spread (sample standard deviation) of the eta_i:

    S(beta, gamma) = sqrt( 1/(n-1) * sum_i (eta_i - mean(eta_i))^2 ).

For each gamma we profile out beta:

    beta*(gamma) = argmin_beta S(beta, gamma),
    sigma_min(gamma) = S(beta*(gamma), gamma).

The location parameter must satisfy gamma < t_min = t_(1).

The classical extremum rule sets the gradient  d sigma_min / d gamma = 0,
which tends to drive gamma towards the boundary t_min and destabilises the
estimates. The MDM gradient-offset variant instead targets a small offset
delta: it stops the descent of sigma_min(gamma) at the point where the slope
magnitude equals delta, backing the estimate away from the degenerate
boundary sink.

Scale invariance
----------------
sigma_min has the units of eta (time); gamma has the units of time; hence
the slope d sigma_min / d gamma is DIMENSIONLESS. If the data are rescaled
t -> c*t then sigma_min -> c*sigma_min and gamma -> c*gamma, so the slope is
unchanged. Consequently the offset delta is naturally scale invariant and
its optimal value should not depend on eta. This module therefore works in
raw (dimensional) units, as requested, and the scale invariance is verified
empirically elsewhere.
"""

from __future__ import annotations
import numpy as np


# ----------------------------------------------------------------------
# Plotting positions
# ----------------------------------------------------------------------
def bernard_positions(n: int) -> np.ndarray:
    """Median-rank (Bernard) plotting positions F_i, i = 1..n."""
    i = np.arange(1, n + 1)
    return (i - 0.3) / (n + 0.4)


def weibull_x(n: int) -> np.ndarray:
    """x_i = -ln(1 - F_i) for Bernard positions. Depends only on n."""
    F = bernard_positions(n)
    return -np.log(1.0 - F)


# ----------------------------------------------------------------------
# Sampling
# ----------------------------------------------------------------------
def sample_weibull3(beta: float, eta: float, gamma: float, n: int,
                    rng: np.random.Generator) -> np.ndarray:
    """Draw n i.i.d. 3-parameter Weibull failure times (sorted)."""
    u = rng.uniform(0.0, 1.0, size=n)
    t = gamma + eta * (-np.log(1.0 - u)) ** (1.0 / beta)
    return np.sort(t)


# ----------------------------------------------------------------------
# Spread of pseudo-scales and the profiled sigma_min(gamma) curve
# ----------------------------------------------------------------------
def sigma_min_curve(t_sorted: np.ndarray,
                    gamma_grid: np.ndarray,
                    beta_grid: np.ndarray,
                    x: np.ndarray | None = None):
    """
    Vectorised computation of sigma_min(gamma) and beta*(gamma) over a grid.

    Parameters
    ----------
    t_sorted   : (n,)  sorted failure times
    gamma_grid : (G,)  candidate gamma values (all < t_min)
    beta_grid  : (B,)  candidate beta values for the inner minimisation
    x          : (n,)  optional precomputed x_i (else derived from n)

    Returns
    -------
    sigma_min  : (G,)  min over beta of S(beta, gamma)
    beta_star  : (G,)  argmin beta for each gamma
    eta_hat    : (G,)  mean pseudo-scale at (beta*, gamma)  (the eta estimate)
    """
    n = t_sorted.size
    if x is None:
        x = weibull_x(n)

    # diff[g, i] = t_i - gamma_g            -> (G, n)
    diff = t_sorted[None, :] - gamma_grid[:, None]
    # Guard: only gammas strictly below t_min are valid; others -> inf later.
    valid = np.all(diff > 0.0, axis=1)               # (G,)

    a = 1.0 / beta_grid                               # (B,) exponent 1/beta
    # xpow[b, i] = x_i ** a_b                          -> (B, n)
    logx = np.log(x)
    xpow = np.exp(a[:, None] * logx[None, :])         # (B, n)

    # eta_i for every (gamma, beta): (G, B, n)
    # eta[g, b, i] = diff[g, i] / xpow[b, i]
    eta = diff[:, None, :] / xpow[None, :, :]         # (G, B, n)

    mean = eta.mean(axis=2, keepdims=True)            # (G, B, 1)
    var = ((eta - mean) ** 2).sum(axis=2) / (n - 1)   # (G, B)
    S = np.sqrt(var)                                  # (G, B)

    # Invalidate gammas that are not strictly below t_min
    S = np.where(valid[:, None], S, np.inf)

    b_idx = np.argmin(S, axis=1)                      # (G,)
    g_idx = np.arange(gamma_grid.size)
    sigma_min = S[g_idx, b_idx]                        # (G,)
    beta_star = beta_grid[b_idx]                       # (G,)
    eta_hat = mean[g_idx, b_idx, 0]                    # (G,)

    sigma_min = np.where(valid, sigma_min, np.nan)
    beta_star = np.where(valid, beta_star, np.nan)
    eta_hat = np.where(valid, eta_hat, np.nan)
    return sigma_min, beta_star, eta_hat


# ----------------------------------------------------------------------
# gamma grid: clustered near t_min where the boundary behaviour lives
# ----------------------------------------------------------------------
def make_gamma_grid(t_sorted: np.ndarray, n_points: int = 220,
                    span_mult: float = 3.0, power: float = 2.4,
                    floor_frac: float = 1e-3) -> np.ndarray:
    """
    Build a gamma grid on (gamma_lo, t_min), denser near t_min.

    offset = t_min - gamma ranges from floor_frac*span to span_mult*span,
    spaced as offset = offset_max * u**power with u in (0,1], so points
    cluster near t_min (small offset).
    """
    t_min = t_sorted[0]
    t_max = t_sorted[-1]
    span = max(t_max - t_min, 1e-9)
    offset_max = span_mult * span
    offset_min = floor_frac * span
    u = np.linspace(0.0, 1.0, n_points)
    offset = offset_min + (offset_max - offset_min) * (u ** power)
    gamma = t_min - offset
    return gamma[::-1]  # ascending gamma (towards t_min)


# ----------------------------------------------------------------------
# beta refinement around the grid minimum (local 1-D polish)
# ----------------------------------------------------------------------
def _refine_beta(t_sorted, gamma, beta0, x, span=1.4, iters=2, k=9):
    """Local golden-ish grid refinement of beta at a single gamma."""
    n = t_sorted.size
    diff = t_sorted - gamma
    if np.any(diff <= 0):
        return beta0, np.nan
    lo, hi = beta0 / span, beta0 * span
    best_b, best_S = beta0, np.inf
    for _ in range(iters):
        bs = np.linspace(lo, hi, k)
        for b in bs:
            eta = diff / (x ** (1.0 / b))
            S = eta.std(ddof=1)
            if S < best_S:
                best_S, best_b = S, b
        width = (hi - lo) / (k - 1)
        lo, hi = best_b - width, best_b + width
        lo = max(lo, 0.05)
    return best_b, best_S


# ----------------------------------------------------------------------
# The gradient-offset (delta) estimator
# ----------------------------------------------------------------------
def _moving_average(y: np.ndarray, w: int = 5) -> np.ndarray:
    """Light symmetric moving average (odd window) for feature detection."""
    if w < 3 or y.size < w:
        return y.copy()
    if w % 2 == 0:
        w += 1
    k = np.ones(w) / w
    pad = w // 2
    yp = np.pad(y, pad, mode="edge")
    return np.convolve(yp, k, mode="valid")


def estimate_mdm(t_sorted: np.ndarray,
                 deltas,
                 beta_grid: np.ndarray | None = None,
                 gamma_grid: np.ndarray | None = None,
                 n_gamma: int = 240,
                 refine: bool = True,
                 smooth_w: int = 7):
    """
    Run the MDM gradient-offset estimator for a list of delta values, reusing
    a single profiled curve sigma_min(gamma).

    Geometry (verified empirically)
    -------------------------------
    sigma_min(gamma) is a broad BOWL: high for very negative gamma, descending
    to a wide, flat minimum, then RISING (a steep "wall") as gamma -> t_min.
    The true location parameter sits on the RISING RIGHT FLANK of the bowl,
    between the bowl bottom and t_min, where the slope d sigma_min/d gamma is
    positive. The classical extremum rule (slope = 0, the bowl bottom) is
    unstable precisely because the bottom is flat: its position swings widely
    from sample to sample (sometimes far left, sometimes close to t_min),
    which is the instability the gradient-offset is meant to cure.

    Operational delta-criterion (documented in the report)
    -------------------------------------------------------
    1. gamma0 = argmin sigma_min(gamma) (the bowl bottom, the slope = 0 /
       "min-sigma" solution; reported for delta = 0).
    2. For delta > 0, move RIGHT from gamma0 along the rising flank and take
       the first gamma where the slope equals +delta. Because the flank is
       steep and monotone, this crossing is unique and STABLE, and it lies
       closer to the true gamma than the bowl bottom. Larger delta moves
       gamma_hat further up the flank, towards t_min.
    3. The steep wall near t_min means a crossing of slope = delta on the
       flank exists for essentially all reasonable delta, so a strict
       interior root almost always exists. If it does not (e.g. the bowl
       bottom is itself at the boundary, typical for beta < 1, leaving no
       right flank), we fall back to the constrained solution -- the feasible
       point nearest t_min -- and set strict_root = False. This guarantees a
       feasible solution (gamma < t_min) in all cases.

    Returns a dict keyed by float(delta) with (beta_hat, eta_hat, gamma_hat,
    strict_root) plus shared diagnostics: 'gamma_grid', 'sigma_min', 'grad',
    'gamma0' (bowl bottom), 'has_right_flank' (bool).
    """
    deltas = np.atleast_1d(np.asarray(deltas, dtype=float))
    n = t_sorted.size
    x = weibull_x(n)
    t_min = t_sorted[0]

    if beta_grid is None:
        beta_grid = np.exp(np.linspace(np.log(0.1), np.log(30.0), 90))
    if gamma_grid is None:
        gamma_grid = make_gamma_grid(t_sorted, n_points=n_gamma)

    sigma, beta_star, eta_hat = sigma_min_curve(t_sorted, gamma_grid,
                                                beta_grid, x=x)

    ok = np.isfinite(sigma)
    g = gamma_grid[ok]
    s = sigma[ok]
    bstar = beta_star[ok]

    out = {"gamma_grid": g, "sigma_min": s, "beta_star_curve": bstar}

    def _nan_result():
        for d in deltas:
            out[float(d)] = dict(beta_hat=np.nan, eta_hat=np.nan,
                                 gamma_hat=np.nan, strict_root=False)
        out["grad"] = np.full_like(g, np.nan)
        out["gamma0"] = np.nan
        out["has_right_flank"] = False
        return out

    if g.size < 7:
        return _nan_result()

    # Smooth for robust slope; slope from smoothed curve.
    s_sm = _moving_average(s, smooth_w)
    grad = np.gradient(s_sm, g)
    out["grad"] = grad

    # bowl bottom = global minimum of the (smoothed) curve
    i0 = int(np.argmin(s_sm))
    gamma0 = float(g[i0])
    out["gamma0"] = gamma0
    # is there a usable rising right flank between the bottom and t_min?
    has_flank = (i0 < g.size - 2) and (grad[i0 + 1:].max() > 0)
    out["has_right_flank"] = bool(has_flank)

    def _beta_eta_at(gh):
        bh = float(np.interp(gh, g, bstar))
        if refine and np.isfinite(bh):
            bh, _ = _refine_beta(t_sorted, gh, bh, x)
        diff = t_sorted - gh
        if np.any(diff <= 0) or not np.isfinite(bh) or bh <= 0:
            eh = np.nan
        else:
            eh = float(np.mean(diff / (x ** (1.0 / bh))))
        return bh, eh

    for d in deltas:
        d = float(d)
        if d == 0.0 or not has_flank:
            gamma_hat = gamma0
            strict = (d == 0.0)
            if d > 0.0 and not has_flank:
                # constrained: nearest-t_min feasible point
                gamma_hat = float(g[-1])
                strict = False
        else:
            target = d  # positive slope on the rising flank
            gamma_hat = None
            strict = False
            # move RIGHT from the bottom; first crossing of slope == +delta
            for j in range(i0, g.size - 1):
                a0, a1 = grad[j], grad[j + 1]
                if a0 <= target <= a1 or (a0 < target and a1 >= target):
                    x0, x1 = g[j], g[j + 1]
                    y0, y1 = a0 - target, a1 - target
                    if y1 != y0:
                        gamma_hat = x0 + (0.0 - y0) * (x1 - x0) / (y1 - y0)
                    else:
                        gamma_hat = 0.5 * (x0 + x1)
                    strict = True
                    break
            if gamma_hat is None:
                # delta exceeds the steepest available slope before t_min:
                # take the feasible point nearest t_min (constrained solution)
                gamma_hat = float(g[-1])
                strict = False

        gamma_hat = min(float(gamma_hat), t_min - 1e-9)  # enforce feasibility
        beta_hat, eta_h = _beta_eta_at(gamma_hat)
        out[d] = dict(beta_hat=float(beta_hat), eta_hat=eta_h,
                      gamma_hat=float(gamma_hat), strict_root=bool(strict))

    return out


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    t = sample_weibull3(beta=2.0, eta=100.0, gamma=10.0, n=20, rng=rng)
    res = estimate_mdm(t, deltas=[0.0, 0.05, 0.1, 0.2, 0.5])
    print(f"t_min = {t[0]:.3f}  gamma0(anchor) = {res['gamma0']:.3f}  "
          f"interior_min = {res['has_interior_min']}")
    for d in [0.0, 0.05, 0.1, 0.2, 0.5]:
        r = res[d]
        print(f"delta={d:4.2f}: beta={r['beta_hat']:.3f} eta={r['eta_hat']:.2f} "
              f"gamma={r['gamma_hat']:8.3f} strict={r['strict_root']}")
