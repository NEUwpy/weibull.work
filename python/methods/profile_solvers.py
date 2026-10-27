"""One-dimensional candidate searches for the existing MLE/WMLE criteria.

Only observations and numerical controls enter these solvers. Historical
diagnostic profiles remain unchanged in conditional_profiles.py.
"""
import numpy as np
from scipy.optimize import brentq, minimize_scalar

from .conditional_profiles import mle_profile, wmle_profile, wmle_residuals, wmle_objective_profile

SOLVER_VERSION = '2026-10-16-profile-v2'


def _location_grid():
    # Dimensionless locations: ordinary range, near zero, and near support.
    end = np.log(1. - np.nextafter(1., 0.))
    return np.unique(np.r_[np.linspace(0., .99, 97),
                           -np.expm1(np.linspace(0., end, 97)),
                           np.geomspace(1e-12, .1, 33)])


def solve_mle_profile(data):
    """Find finite likelihood maxima over beta>=1 and 0<=gamma<min(x).

    The open-support beta=1 limit is reported separately. It is never turned
    into a fabricated finite maximum by subtracting an arbitrary epsilon.
    """
    x = np.sort(np.asarray(data, float))
    unit = float(x[0])
    z = x / unit
    cache = {}

    def profile(g):
        g = float(g)
        if g not in cache:
            cache[g] = mle_profile(z, g, shape_lower=1.)
        return cache[g]

    grid = _location_grid()
    points = [profile(g) for g in grid]
    candidates = []

    def add(g, kind):
        p = profile(g)
        if p is None or not np.isfinite(p['ll']):
            return
        gamma = float(g * unit)
        if not 0 <= gamma < unit:
            return
        if kind == 'interior' and p['beta'] <= 1.:
            return
        if any(abs(g - c['gamma'] / unit) <= 1e-9 for c in candidates):
            return
        candidates.append(dict(beta=float(p['beta']), eta=float(p['eta'] * unit),
                               gamma=gamma, ll=float(p['ll'] - len(x) * np.log(unit)),
                               kind=kind, location_score=float(p['location_score'] / unit)))

    zero = points[0]
    if zero is not None and zero['location_score'] <= 0:
        add(0., 'zero_location_boundary')
    for i in range(len(grid) - 1):
        left, right = points[i:i + 2]
        if left is None or right is None:
            continue
        if left['location_score'] > 0 and right['location_score'] < 0:
            root = brentq(lambda g: profile(g)['location_score'], grid[i], grid[i + 1],
                          xtol=5e-15, rtol=1e-13)
            add(float(root), 'interior')
    # A narrow maximum/minimum pair can lie between two positive grid scores.
    # Refine sampled derivative valleys before concluding that no peak exists.
    for i in range(1, len(grid) - 1):
        a, b, c = points[i - 1:i + 2]
        if (a is None or b is None or c is None or b['beta'] <= 1
                or not (0 < b['location_score'] < a['location_score']
                        and b['location_score'] < c['location_score'])):
            continue
        valley = minimize_scalar(lambda g: profile(g)['location_score'],
                                 bounds=(grid[i - 1], grid[i + 1]), method='bounded',
                                 options={'xatol': 1e-14})
        if valley.success and valley.fun < 0 and a['location_score'] > 0:
            root = brentq(lambda g: profile(g)['location_score'], grid[i - 1], valley.x,
                          xtol=5e-15, rtol=1e-13)
            add(float(root), 'interior')
    # Catch a peak whose derivative is too flat to resolve on the coarse grid.
    for i in range(1, len(grid) - 1):
        p = points[i]
        if (p is None or p['beta'] <= 1 or points[i - 1] is None or points[i + 1] is None
                or not (p['ll'] > points[i - 1]['ll'] and p['ll'] > points[i + 1]['ll'])):
            continue
        optimum = minimize_scalar(lambda g: -profile(g)['ll'],
                                  bounds=(grid[i - 1], grid[i + 1]), method='bounded',
                                  options={'xatol': 1e-13})
        if optimum.success:
            g = float(optimum.x)
            h = min(1e-6, g / 2, (1 - g) / 2)
            if h > 0 and profile(g - h)['location_score'] >= 0 and profile(g + h)['location_score'] <= 0:
                add(g, 'interior')
    eta_limit = float(np.mean(x - x[0]))
    limit_ll = float(-len(x) * (1 + np.log(eta_limit)))
    best = max(candidates, key=lambda p: p['ll']) if candidates else None
    info = dict(status='ok' if best else 'no_finite_local_maximum',
                solver_version=SOLVER_VERSION, strategy='profile_likelihood_finite_maxima',
                constraint='beta>=1, eta>0, 0<=gamma<min(x)',
                profile_grid_points=len(grid), profile_evaluations=len(cache),
                candidate_count=len(candidates), candidates=candidates,
                support_boundary_limit=dict(beta=1., eta=eta_limit, gamma=float(x[0]),
                                            log_likelihood=limit_ll, attained_in_open_support=False),
                boundary_limit_exceeds_selected=bool(best and limit_ll > best['ll'] + 1e-9))
    if best:
        info.update(log_likelihood=best['ll'], location_at_zero_boundary=best['gamma'] == 0.)
    return best, info


def solve_wmle_profile(data, weights):
    """Solve both weighted equations; preserve the table, cap and root tie rule."""
    x = np.sort(np.asarray(data, float))
    unit = float(x[0])
    z = x / unit
    cache = {}

    def profile(g):
        g = float(g)
        if g not in cache:
            cache[g] = wmle_profile(z, g, weights)
        return cache[g]

    grid = _location_grid()
    # Explicitly split at J3 interpolation knots, where slopes can change.
    knots = []
    for left, right in zip(grid[:-1], grid[1:]):
        a, b = profile(left), profile(right)
        if a is None or b is None:
            continue
        for shape in np.arange(.1, min(5., weights.SHAPE_UPPER) + 1e-9, .1):
            if (a['beta'] - shape) * (b['beta'] - shape) < 0:
                knots.append(brentq(lambda g: profile(g)['beta'] - shape, left, right,
                                    xtol=5e-15, rtol=1e-13))
    grid = np.unique(np.r_[grid, knots])
    candidates = []

    def add(g, point=None, kind='equation_root'):
        p = profile(g) if point is None else point
        if p is None or p['beta'] >= weights.SHAPE_UPPER - .01:
            return
        gamma = float(g * unit)
        if not 0 <= gamma < unit:
            return
        # Validate the returned coordinates after floating-point rounding.
        a, b = wmle_residuals(x, p['beta'], gamma, weights)
        objective = float(a * a + b * b)
        if objective > 1e-8 or not np.isfinite(p['eta']):
            return
        if any(abs(g - c['gamma'] / unit) <= 1e-9 for c in candidates):
            return
        candidates.append(dict(beta=float(p['beta']), eta=float(p['eta'] * unit),
                               gamma=gamma, objective=objective,
                               t1=float(a), t2=float(b), j3_clamped=bool(p['j3_clamped']), kind=kind))

    points = [profile(g) for g in grid]
    for g, p in zip(grid, points):
        if p is not None and abs(p['t2']) <= 1e-10:
            add(float(g))
    for i in range(len(grid) - 1):
        a, b = points[i:i + 2]
        if a is not None and b is not None and a['t2'] * b['t2'] < 0:
            root = brentq(lambda g: profile(g)['t2'], grid[i], grid[i + 1],
                          xtol=5e-15, rtol=1e-13)
            add(float(root))
    # Tangent roots and narrow root pairs need not change sign on the grid.
    for i in range(1, len(grid) - 1):
        a, b, c = points[i - 1:i + 2]
        if (a is None or b is None or c is None
                or not (abs(b['t2']) < abs(a['t2']) and abs(b['t2']) < abs(c['t2']))):
            continue
        optimum = minimize_scalar(lambda g: profile(g)['t2'] ** 2,
                                  bounds=(grid[i - 1], grid[i + 1]), method='bounded',
                                  options={'xatol': 1e-13})
        if optimum.success:
            add(float(optimum.x))

    # The previous estimator accepted residual-tolerant near-roots at gamma=0.
    # Preserve that acceptance rule when an exact conditional intersection is
    # unavailable, while explicitly identifying the boundary approximation.
    if not candidates:
        boundary = wmle_objective_profile(z, 0., weights)
        if boundary['objective'] <= 1e-8:
            add(0., boundary, kind='boundary_residual_tolerance')

    def proximity(p):
        return (np.log(p['beta'] / 2.) ** 2
                + ((p['gamma'] - .9 * unit) / max(unit, 1.)) ** 2)

    minimum = min((p['objective'] for p in candidates), default=np.inf)
    near_best = [p for p in candidates if p['objective'] <= minimum + 1e-12]
    best = min(near_best, key=proximity) if near_best else None
    residuals = [p['t1'] ** 2 + p['t2'] ** 2 for p in cache.values() if p is not None]
    info = dict(status='ok' if best else 'no_equation_root_found',
                solver_version=SOLVER_VERSION, strategy='profile_weighted_equation_roots',
                constraint='0<beta<9.99, eta>0, 0<=gamma<min(x)',
                shape_upper=float(weights.SHAPE_UPPER), profile_grid_points=len(grid),
                profile_evaluations=len(cache), candidate_count=len(candidates), candidates=candidates,
                best_profile_objective=float(min(residuals)) if residuals else None,
                selection='root nearest original beta=2, gamma=.9*min(x) heuristic')
    if best:
        info.update(objective=best['objective'], j3_clamped=best['j3_clamped'],
                    location_at_zero_boundary=best['gamma'] == 0.,
                    approximate_boundary_root=best['kind'] == 'boundary_residual_tolerance')
    return best, info
