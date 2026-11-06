"""Linked explanations must use the estimator's own equations and units."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import minimize_scalar

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from methods.mle import MLE
from methods.wmle import WMLE
from methods.mmle import MMLE
from methods import wmle as weights
from methods.conditional_profiles import mle_profile, wmle_residuals
from methods.calculation_trace import power_scale_calculation

SAMPLE = [310, 342, 353, 365, 383, 393, 403, 412, 451, 456]


@pytest.mark.parametrize('method', [MLE, WMLE])
def test_linked_position_frames_share_equations_and_exact_final_parameters(method):
    plain, model = method(SAMPLE), method(SAMPLE)
    assert plain.run() == model.run(trace=True)
    record = model.calculation_trace
    frames = record['details']['reading_frames']
    assert 3 < len(frames) < 30
    final = next(frame for frame in frames if frame['final'])
    assert [final[p] for p in ('beta', 'eta', 'gamma')] == [record['selection'][p] for p in ('beta', 'eta', 'gamma')]
    x = np.asarray(SAMPLE)
    for frame in frames:
        points = frame['shape_chart']['series'][0]['points']
        gamma = frame['gamma']
        logs = np.log(x - gamma)
        for point in points:
            beta = point['x']
            power = np.exp(beta * (logs - logs.max()))
            shape_weight = 1. if method is MLE else weights.get_weight_j2(len(x))
            score = shape_weight / beta + logs.mean() - (power @ logs) / power.sum()
            assert point['y'] == pytest.approx(score, rel=5e-15, abs=2e-13)
        if method is MLE:
            expected = mle_profile(x, gamma)
            assert frame['log_likelihood'] == pytest.approx(expected['ll'], abs=2e-9)
            assert frame['location_score'] == pytest.approx(expected['location_score'], abs=2e-9)
        else:
            first, second = wmle_residuals(x, frame['beta'], gamma, weights)
            assert frame['t1'] == pytest.approx(first, abs=2e-12)
            assert frame['t2'] == pytest.approx(second, abs=2e-12)
            assert frame['j3'] == weights.get_weight_j3(len(x), frame['beta'])
    json.dumps(record, allow_nan=False)
    actual = next(series for series in final['shape_chart']['series'] if series['id'] == 'solver-points')
    expected = [(p['beta'], p['score']) for p in record['details']['selected_shape_evaluations'] if p['source'] == 'solver']
    assert [(p['x'], p['y']) for p in actual['points']] == expected
    assert actual['kind'] == 'scatter' and actual['role'] == 'solver'


def test_mmle_profile_and_real_iteration_marks_use_one_modified_likelihood():
    model, plain = MMLE(SAMPLE), MMLE(SAMPLE)
    result = model.run(trace=True)
    assert result == plain.run()
    beta, eta, gamma = result[:3]
    retained = np.sort(SAMPLE)[1:] - gamma

    def likelihood(shape):
        scale = np.mean(retained ** shape) ** (1 / shape)
        return np.sum(np.log(shape / scale) + (shape - 1) * np.log(retained / scale)
                      - (retained / scale) ** shape)

    trace = model.calculation_trace
    chart = next(chart for chart in trace['charts'] if chart['id'] == 'modified-profile-likelihood')
    for series in chart['series']:
        for point in series['points']:
            assert point['y'] == pytest.approx(likelihood(point['x']), abs=2e-10)
    for frame in trace['details']['profile_frames'][1:]:
        actual = next(step for step in model.trace_data if step.get('iteration') == frame['iteration'])
        assert frame['x'] == actual['shape_after']
    points = next(series for series in chart['series'] if series['id'] == 'iterations')['points']
    actual_iterations = [step for step in model.trace_data if step.get('phase') == 'shape_iteration']
    assert len(points) == len(actual_iterations) + 1
    assert [p['x'] for p in points[1:]] == [step['shape_after'] for step in actual_iterations]
    optimum = minimize_scalar(lambda b: -likelihood(b), bounds=(beta * .8, beta * 1.2), method='bounded')
    assert beta == pytest.approx(optimum.x, abs=2e-6)
    assert chart['selected'][0]['x'] == beta
    assert chart['selected'][0]['eta'] == eta
    json.dumps(trace, allow_nan=False)


@pytest.mark.parametrize('method', [MLE, WMLE, MMLE])
def test_all_samples_and_aggregation_reconstruct_the_selected_scale(method):
    model = method(SAMPLE)
    beta, eta, gamma, *_ = model.run(trace=True)
    details = model.calculation_trace['details']
    scale = details['scale_calculation']
    retained = np.sort(SAMPLE)[1:] if method is MMLE else np.sort(SAMPLE)
    d = retained-gamma
    powers = d**beta
    j1 = weights.get_weight_j1(len(d)) if method is WMLE else 1.
    assert scale['count'] == len(retained)
    assert [p['observation'] for p in scale['samples']] == list(retained)
    assert [p['distance'] for p in scale['samples']] == pytest.approx(d)
    assert [p['power'] for p in scale['samples']] == pytest.approx(powers)
    assert scale['power_sum'] == pytest.approx(powers.sum())
    assert scale['power_mean'] == pytest.approx(powers.sum()/(len(d)*j1))
    assert scale['power_mean']**(1/beta) == pytest.approx(eta, rel=2e-13)
    assert scale['reference_distance']*scale['scale_factor'] == pytest.approx(eta, rel=2e-13)
    if method is MMLE:
        assert scale['samples'][0]['index'] == 2
        for iteration in details['shape_iterations']:
            shape = iteration['shape_before']
            w = d**shape / np.sum(d**shape)
            expected = (len(d)+shape*np.log(d).sum())/(len(d)*(w@np.log(d)))
            assert iteration['shape_after'] == pytest.approx(expected, abs=2e-14)
            assert iteration['numerator']/iteration['denominator'] == iteration['shape_after']
    else:
        eq = details['equation_calculation']
        assert eq['mean_log'] == pytest.approx(np.log(d).mean())
        assert eq['weighted_log_mean'] == pytest.approx(powers@np.log(d)/powers.sum())
        assert eq['power_ratio'] == pytest.approx(powers.sum()/np.sum(d**(beta-1)))
        if method is WMLE:
            assert details['weight_values']['j1'] == j1
            residual = eq['inverse_mean']*eq['power_ratio']-details['weight_values']['j3']
            assert residual == pytest.approx(model.calculation_trace['selection']['t2'], abs=2e-12)


@pytest.mark.parametrize('magnitude', [1e-200, 1e200])
def test_extreme_sample_powers_keep_an_equivalent_finite_scale_explanation(magnitude):
    beta = 4.
    sample = np.array([magnitude, 2*magnitude])
    expected = magnitude * ((1+2**beta)/2)**(1/beta)
    record = power_scale_calculation(sample, beta, 0, expected)
    assert record['use_scaled']
    assert record['reference_distance']*record['scale_factor'] == pytest.approx(expected, rel=2e-13, abs=0)
    assert sum(p['scaled_power'] for p in record['samples']) == record['scaled_sum']
    json.dumps(record, allow_nan=False)
