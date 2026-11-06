"""Calculation charts must be evidence of the same run, not display inventions."""
import json
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from methods.mle import MLE
from methods.wmle import WMLE, get_weight_j2, get_weight_j3
from methods.mdm import MDM
from studies.common.sample import generate_sample

PAPER_SAMPLE = [310, 342, 353, 365, 383, 393, 403, 412, 451, 456]


def _chart(record, key):
    return next(c for c in record['charts'] if c['id'] == key)


@pytest.mark.parametrize('method,kwargs', [(MLE, {}), (WMLE, {}), (MDM, {'offset': .1})])
def test_trace_does_not_change_estimate_or_selection(method, kwargs):
    plain = method(PAPER_SAMPLE)
    recorded = method(PAPER_SAMPLE)
    assert plain.run(trace=False, **kwargs) == recorded.run(trace=True, **kwargs)
    assert plain.calculation_trace is None
    record = recorded.calculation_trace
    assert record['selection']['beta'] > 0
    assert record['selection']['gamma'] < min(PAPER_SAMPLE)
    # This also rejects NaN/inf and numpy-only values in JSON plot payloads.
    json.dumps(record, allow_nan=False)
    assert plain.last_solution_info == recorded.last_solution_info


def test_mle_plot_values_are_actual_likelihood_and_location_score():
    estimator = MLE(PAPER_SAMPLE)
    beta, eta, gamma, _, _ = estimator.run(trace=True)
    record = estimator.calculation_trace
    points = _chart(record, 'profile-likelihood')['series'][0]['points']
    x = np.asarray(PAPER_SAMPLE)
    for p in points:
        d = x - p['gamma']
        b, e = p['beta'], p['eta']
        ll = np.sum(np.log(b / e) + (b - 1) * np.log(d / e) - (d / e) ** b)
        assert p['y'] == pytest.approx(ll, abs=2e-8)
    selected = _chart(record, 'profile-likelihood')['selected'][0]
    assert selected['x'] == gamma
    assert selected['y'] == record['selection']['log_likelihood']
    selected_score = _chart(record, 'location-score')['selected'][0]
    assert selected_score['x'] == gamma
    assert abs(selected_score['y']) < 1e-8
    assert any(p['x'] == gamma for p in points)
    assert all(p['evaluation'] > 0 for p in points)
    assert record['selection']['beta'] == beta
    assert record['selection']['eta'] == eta


def test_wmle_selected_residuals_satisfy_equations_at_output_coordinates():
    estimator = WMLE(PAPER_SAMPLE)
    beta, eta, gamma, _, _ = estimator.run(trace=True)
    record = estimator.calculation_trace
    d = np.asarray(PAPER_SAMPLE) - gamma
    power = d ** beta
    t1 = get_weight_j2(len(d)) / beta + np.log(d).mean() - np.sum(np.log(d) * power) / power.sum()
    t2 = np.mean(1 / d) * power.sum() / np.sum(d ** (beta - 1)) - get_weight_j3(len(d), beta)
    assert record['selection']['t1'] == pytest.approx(t1, abs=1e-12)
    assert record['selection']['t2'] == pytest.approx(t2, abs=1e-12)
    assert _chart(record, 'weighted-location-equation')['selected'][0]['y'] == record['selection']['t2']
    selected = _chart(record, 'candidate-residuals')['selected'][0]
    assert selected['x'] == gamma
    assert selected['y'] == record['selection']['objective']
    assert selected['y'] < 1e-8
    assert record['selection']['eta'] == eta


def test_mdm_inner_curve_uses_real_objective_and_exact_selected_gamma():
    estimator = MDM(PAPER_SAMPLE)
    beta, eta, gamma, _, _ = estimator.run(trace=True, offset=.1)
    record = estimator.calculation_trace
    ranks = estimator._median_ranks()
    transformed_ranks = -np.log(1 - ranks)
    curve = _chart(record, 'shape-discrepancy')
    for p in curve['series'][0]['points']:
        pseudo_scales = (np.asarray(PAPER_SAMPLE) - gamma) / transformed_ranks ** (1 / p['x'])
        assert p['y'] == pytest.approx(np.std(pseudo_scales, ddof=1), rel=1e-12)
        assert p['gamma'] == gamma
    selected = curve['selected'][0]
    pseudo_scales = (np.asarray(PAPER_SAMPLE) - gamma) / transformed_ranks ** (1 / beta)
    assert selected['x'] == beta
    assert selected['y'] == pytest.approx(np.std(pseudo_scales, ddof=1), rel=1e-12)
    assert eta == pytest.approx(np.mean(pseudo_scales), rel=1e-12)
    operands = record['details']['pseudo_scales']
    assert len(operands) == len(PAPER_SAMPLE)
    for index, point in enumerate(operands):
        assert point['observation'] == sorted(PAPER_SAMPLE)[index]
        assert point['rank'] == ranks[index]
        assert point['distance'] == point['observation'] - gamma
        assert point['rank_transform'] == transformed_ranks[index]
        assert point['denominator'] == pytest.approx((-np.log1p(-point['rank'])) ** (1 / beta), rel=1e-12)
        assert point['eta'] == point['distance'] / point['denominator']
    assert record['details']['pseudo_scale_sum'] == pytest.approx(sum(point['eta'] for point in operands), rel=1e-12)
    assert record['details']['pseudo_scale_sum'] / len(operands) == eta
    root_plot = _chart(record, 'location-criterion')
    assert root_plot['selected'][0]['x'] == gamma
    assert root_plot['selected'][0]['y'] == pytest.approx(.1, abs=1e-8)
    assert len(root_plot['series'][0]['points']) == len(record['details']['root_evaluations'])


def test_mdm_zero_boundary_is_a_boundary_selection_not_a_fake_root():
    sample = generate_sample(1.5, 100., 0., 10, 1)
    estimator = MDM(sample)
    _, _, gamma, _, _ = estimator.run(trace=True, offset=.1, gamma_steps=20)
    record = estimator.calculation_trace
    selected = _chart(record, 'location-criterion')['selected'][0]
    assert gamma == 0
    assert selected['x'] == 0
    assert selected['y'] > .1
    assert record['selection']['strategy'] == 'truncated_at_zero'


def test_mdm_endpoint_fit_is_explicit_and_not_in_actual_gradient_series():
    sample = generate_sample(2., 100., 5., 30, 0)
    estimator = MDM(sample)
    estimator.run(trace=True, offset=5., gamma_steps=30)
    record = estimator.calculation_trace
    chart = _chart(record, 'location-criterion')
    assert record['selection']['approximate'] is True
    assert record['selection']['solver'] == 'right_edge_fit'
    assert chart['selected'] == []
    solver_points = chart['series'][0]['points']
    assert all(p['x'] != record['selection']['gamma'] for p in solver_points)
    virtual = chart['series'][1]
    assert virtual['role'] == 'virtual'
    assert virtual['points'][0]['virtual'] is True
    assert virtual['points'][0]['x'] == record['selection']['gamma']


def test_mle_failure_keeps_evidence_without_fabricating_selected_point():
    sample = np.random.default_rng(0).weibull(.6, 30) * 50
    estimator = MLE(sample)
    assert estimator.run(trace=True)[0] is None
    record = estimator.calculation_trace
    assert record['selection']['status'] == 'no_finite_local_maximum'
    assert 'beta' not in record['selection']
    assert all(c['selected'] == [] for c in record['charts'])
    assert record['details']['support_boundary_limit']['attained_in_open_support'] is False
