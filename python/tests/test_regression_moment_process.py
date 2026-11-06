"""Linked views must explain the same estimate with numerically valid evidence."""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from methods.lse import LSE
from methods.lre import LRE
from methods.mm import MM

SAMPLE = [310, 342, 353, 365, 383, 393, 403, 412, 451, 456]


@pytest.mark.parametrize('method', [LSE, LRE, MM])
def test_reading_views_do_not_change_estimate_or_solver_diagnostics(method):
    plain, recorded = method(SAMPLE), method(SAMPLE)
    assert plain.run(trace=False) == recorded.run(trace=True)
    assert plain.last_solution_info == recorded.last_solution_info
    json.dumps(recorded.calculation_trace, allow_nan=False)


@pytest.mark.parametrize('method', [LSE, LRE])
def test_linked_regression_fits_and_parameter_mapping_are_consistent(method):
    estimator = method(SAMPLE)
    beta, eta, gamma, _, _ = estimator.run(trace=True)
    record = estimator.calculation_trace
    views = record['details']['regression_views']
    assert len(views) <= 12
    selected = [view for view in views if view['selected']]
    assert len(selected) == 1
    assert [selected[0][key] for key in ('beta', 'eta', 'gamma')] == [beta, eta, gamma]
    evaluations = record['details']['evaluations']
    for view in views:
        points = np.array([[p['x'], p['y']] for p in view['points']])
        x, y = points.T
        sums = view['calculation']
        assert sums['sxx'] == pytest.approx(np.sum((x-x.mean())**2))
        assert sums['sxy'] == pytest.approx(np.sum((x-x.mean())*(y-y.mean())))
        assert sums['residual_sum'] == pytest.approx(sum((p['y']-p['fit'])**2 for p in view['points']))
        assert [p['distance'] for p in view['points']] == pytest.approx(np.sort(SAMPLE)-view['gamma'])
        if method is LSE:
            assert y == pytest.approx(np.log(np.sort(SAMPLE)-view['gamma']))
        else:
            assert x == pytest.approx(np.log([p['distance'] for p in view['points']]))
        # Independent linear algebra checks the displayed line and its mapping.
        slope, intercept = np.linalg.lstsq(np.column_stack((x, np.ones(len(x)))), y, rcond=None)[0]
        assert view['slope'] == pytest.approx(slope, rel=2e-12)
        assert view['intercept'] == pytest.approx(intercept, rel=2e-12, abs=1e-12)
        assert [p['fit'] for p in view['points']] == pytest.approx(slope*x+intercept, rel=2e-12, abs=1e-12)
        actual = [p['y'] for p in evaluations if p['x'] == view['gamma']]
        assert actual and any(view['criterion'] == pytest.approx(value, abs=2e-12) for value in actual)
        if method is LSE:
            expected = np.var(y, ddof=1) / (np.sum((y-slope*x-intercept)**2) / (len(y)-2))
            assert view['criterion'] == pytest.approx(expected, rel=2e-11)
            assert view['beta'] == pytest.approx(1/slope, rel=2e-12)
            assert view['eta'] == pytest.approx(np.exp(intercept), rel=2e-12)
        else:
            assert view['criterion'] == pytest.approx(np.corrcoef(x, y)[0, 1], abs=2e-12)
            assert view['beta'] == pytest.approx(slope, rel=2e-12)
            assert view['eta'] == pytest.approx(np.exp(-intercept/slope), rel=2e-12)
    if method is LRE:
        original = record['details']['original_regression']
        assert original['gamma'] == 0
        assert [p['x'] for p in original['points']] == pytest.approx(np.log(sorted(SAMPLE)))


def test_interval_areas_reconstruct_all_three_weibull_moments():
    estimator = MM(SAMPLE)
    estimator.run(trace=True)
    details = estimator.calculation_trace['details']
    intervals = details['moment_intervals']
    assert intervals[0]['left'] == 0
    assert [p['right'] for p in intervals] == sorted(SAMPLE)
    for k in (1, 2, 4):
        areas = [p['contributions'][str(k)] for p in intervals]
        assert areas == pytest.approx([(p['right']-p['left'])*p['survival']**k for p in intervals])
        assert sum(areas) == pytest.approx(details[f'm{k}'], rel=1e-14)
    assert details['m1'] == pytest.approx(np.mean(SAMPLE))
