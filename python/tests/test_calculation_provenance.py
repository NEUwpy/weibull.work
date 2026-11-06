"""Run-bound chart values must explain the estimate without changing it."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studies.common.runner import run_method

SAMPLE = [1314.68, 1509.32, 1672.86, 1832.55, 2005.13, 2215.02, 2536.73]


@pytest.mark.parametrize('method', ['mle', 'wmle', 'mdm', 'lse', 'lre', 'mm', 'mmle'])
def test_trace_does_not_change_estimate_and_binds_input_code_and_selection(method):
    kwargs = {'offset': .1} if method == 'mdm' else {}
    ordinary = run_method(method, SAMPLE, **kwargs)
    traced = run_method(method, SAMPLE, trace=True, **kwargs)
    for key in ('beta_hat', 'eta_hat', 'gamma_hat', 'r_squared', 'converged'):
        assert traced[key] == ordinary[key]
    assert traced['converged']
    record = traced['calculation']
    assert record['method'] == method
    for parameter in ('beta', 'eta', 'gamma'):
        assert record['selection'][parameter] == traced[f'{parameter}_hat']
    assert record['run']['observations'] == SAMPLE
    assert record['run']['n'] == 7
    canonical = json.dumps(SAMPLE, separators=(',', ':'), allow_nan=False)
    assert record['run']['sample_sha256'] == hashlib.sha256(canonical.encode()).hexdigest()
    assert record['run']['sources']
    for source in record['run']['sources']:
        content = (Path(__file__).resolve().parents[1] / source['path']).read_bytes()
        assert source['sha256'] == hashlib.sha256(content).hexdigest()
    json.dumps(record, allow_nan=False)


def test_lre_plotted_line_is_the_actual_ols_and_position_choice():
    result = run_method('lre', SAMPLE, trace=True)
    correlation, regression = result['calculation']['charts']
    assert correlation['selected'][0]['x'] == result['gamma_hat']
    points, line = regression['series']
    t = np.asarray(SAMPLE)
    p = (np.arange(1, 8) - .375) / 7.25
    np.testing.assert_allclose([v['x'] for v in points['points']], np.log(t-result['gamma_hat']))
    np.testing.assert_allclose([v['y'] for v in points['points']], np.log(-np.log1p(-p)))
    np.testing.assert_allclose([v['y'] for v in line['points']],
                               result['beta_hat'] * np.log(t-result['gamma_hat'])
                               - result['beta_hat'] * np.log(result['eta_hat']))


def test_lse_plotted_selection_is_independent_white_f_ratio():
    result = run_method('lse', SAMPLE, trace=True)
    record = result['calculation']
    x = np.asarray(record['details']['order_statistic_means'])
    y = np.log(np.asarray(SAMPLE)-result['gamma_hat'])
    slope, intercept = np.polyfit(x, y, 1)
    expected_f = np.var(y, ddof=1) / (np.sum((y-intercept-slope*x)**2) / (len(y)-2))
    point = record['charts'][0]['selected'][0]
    assert point['x'] == result['gamma_hat']
    assert point['y'] == pytest.approx(expected_f, rel=1e-9)


def test_mm_keeps_original_and_modified_estimate_and_actual_summands():
    sample = (np.random.default_rng(0).weibull(2., 100)*100+10).tolist()
    result = run_method('mm', sample, trace=True)
    record = result['calculation']
    assert record['selection']['location_adjustment'] == 'clamped_to_zero'
    assert record['selection']['raw_estimate']['gamma'] < 0
    assert record['selection']['gamma'] == 0
    for k in (1, 2, 4):
        assert sum(record['details']['moment_terms'][str(k)]) == pytest.approx(record['details'][f'm{k}'])


def test_mm_failure_has_no_fake_estimate_or_plot_selection():
    result = run_method('mm', [1., 2., 2.01, 2.02], trace=True)
    assert result['beta_hat'] is None
    assert result['calculation']['selection']['status'] == 'inadmissible_moments'
    assert 'beta' not in result['calculation']['selection']
    json.dumps(result['calculation'], allow_nan=False)


def test_mm_keeps_existing_scale_recalculation_until_algorithm_review():
    sample = (np.random.default_rng(0).weibull(2., 100)*100+10).tolist()
    result = run_method('mm', sample, trace=True)
    from scipy.special import gamma
    assert result['gamma_hat'] == 0
    assert result['eta_hat'] == pytest.approx(np.mean(sample) / gamma(1+1/result['beta_hat']))
    assert result['eta_hat'] != result['calculation']['selection']['raw_estimate']['eta']
    assert result['calculation']['details']['scale_recomputed'] is True


def test_mmle_steps_and_stop_line_match_actual_iterations():
    result = run_method('mmle', SAMPLE, trace=True)
    record = result['calculation']
    steps = next(chart for chart in record['charts'] if chart['id'] == 'shape-step')
    assert len(steps['series'][0]['points']) == record['selection']['iterations']
    assert steps['selected'][0]['y'] <= steps['references'][0]['value']
    assert record['selection']['gamma'] == min(SAMPLE)


@pytest.mark.parametrize('method,weight', [('mle',1.),('wmle',None)])
def test_conditional_shape_curve_is_score_at_selected_location(method, weight):
    from methods.wmle import get_weight_j2
    result = run_method(method, SAMPLE, trace=True)
    chart = next(c for c in result['calculation']['charts'] if c['id']=='conditional-shape-equation')
    logs = np.log(np.asarray(SAMPLE)-result['gamma_hat'])
    centered = logs-logs.mean()
    factor = weight if weight is not None else get_weight_j2(len(SAMPLE))
    for point in chart['series'][0]['points']:
        b=point['x']
        weights=np.exp(b*(centered-centered.max()))
        expected=factor/b-np.dot(weights/weights.sum(),centered)
        assert point['y']==pytest.approx(expected,abs=2e-12)
    assert chart['selected'][0]['x']==result['beta_hat']
    assert abs(chart['selected'][0]['y'])<1e-8


def test_mm_staircase_area_equals_solver_moments_including_ties():
    result=run_method('mm',[100.,100.,150.,200.,300.,400.,500.],trace=True)
    record=result['calculation']
    for k, series in zip((1,2,4),record['charts'][0]['series']):
        points=series['points']
        area=sum(a['y']*(b['x']-a['x']) for a,b in zip(points,points[1:]))
        assert area==pytest.approx(record['details'][f'm{k}'])


@pytest.mark.parametrize('method',['mle','wmle','lse','lre','mm','mmle'])
def test_parameter_recovery_values_are_the_returned_estimates(method):
    result=run_method(method,SAMPLE,trace=True)
    values={v['label']:v['value'] for step in result['calculation']['recovery'] for v in step['values']}
    for label,parameter in [('β̂','beta'),('η̂','eta')]:
        if method=='mm' and parameter=='eta':
            label='η̂（返回）'
        assert values[label]==result[f'{parameter}_hat']
