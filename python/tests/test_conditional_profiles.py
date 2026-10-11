"""Independent likelihood/bound checks for the report diagnostics."""
import sys
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from methods.conditional_profiles import mle_profile, wmle_profile, wmle_residuals
from methods import wmle


def direct_ll(x, beta, eta, gamma):
    z = (x - gamma) / eta
    return len(x) * (np.log(beta) - np.log(eta)) + (beta - 1) * np.log(z).sum() - (z**beta).sum()


def test_mle_boundary_is_kept_with_recomputed_scale():
    x = np.array([1., 2., 3., 4., 10., 40., 100.])
    expanded = mle_profile(x, 0, shape_lower=0)
    fit = mle_profile(x, 0)
    assert expanded['beta'] < 1
    assert fit['beta'] == 1 and fit['shape_at_lower_boundary']
    assert np.isclose(fit['eta'], x.mean())
    assert fit['shape_score'] < 0  # Correct one-sided optimum, not U_beta=0.
    assert np.isclose(fit['ll'], direct_ll(x, 1, x.mean(), 0))
    for b in np.linspace(1.01, 4, 100):
        eta = np.mean(x**b)**(1/b)
        assert direct_ll(x, b, eta, 0) <= fit['ll']


def test_mle_interior_matches_independent_maximum_and_derivative():
    x = np.array([6., 7., 8., 9., 11., 12., 14.])
    g = 2.
    fit = mle_profile(x, g)
    opt = minimize_scalar(lambda b: -direct_ll(x, b, np.mean((x-g)**b)**(1/b), g),
                          bounds=(1, 20), method='bounded')
    assert np.isclose(fit['beta'], opt.x, rtol=1e-6)
    assert abs(fit['shape_score']) < 1e-10
    assert np.isclose(fit['ll'], direct_ll(x, fit['beta'], fit['eta'], g))
    h = 1e-4
    derivative = (mle_profile(x, g+h)['ll']-mle_profile(x, g-h)['ll'])/(2*h)
    assert np.isclose(derivative, fit['location_score'], atol=1e-8)


def test_wmle_no_conditional_root_beyond_cap():
    x = np.array([100., 100.1, 100.2, 100.3, 100.4, 100.5, 100.6])
    assert wmle_profile(x, 0, wmle) is None
    t1, _ = wmle_residuals(x, wmle.SHAPE_UPPER, 0, wmle)
    assert t1 > 0
    assert wmle_profile(x, 99.999, wmle) is not None


def test_wmle_residuals_match_direct_equations_and_broadcast():
    x = np.array([6., 7., 8., 9., 11., 12., 14.])
    fit = wmle_profile(x, 2, wmle)
    b, d = fit['beta'], x-2
    t1 = wmle.get_weight_j2(len(x))/b + np.log(d).mean() - np.sum(d**b*np.log(d))/np.sum(d**b)
    t2 = np.mean(1/d)*np.sum(d**b)/np.sum(d**(b-1)) - wmle.get_weight_j3(len(x), b)
    assert abs(t1) < 1e-10 and np.isclose(fit['t2'], t2)
    assert np.isclose(fit['eta'], (np.sum(d**b)/(len(x)*wmle.get_weight_j1(len(x))))**(1/b))
    grid = wmle_residuals(x, np.array([b, 6.])[None, :], np.array([0., 2.])[:, None], wmle)
    assert np.isclose(grid[0][1, 0], t1) and np.isclose(grid[1][1, 0], t2)
    assert wmle.get_weight_j3(len(x), 6) == wmle.get_weight_j3(len(x), 5)
