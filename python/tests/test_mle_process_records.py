"""The method page must expose the original solve, without another solve for plotting."""
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from methods import conditional_profiles, profile_solvers
from methods.mle import MLE

SAMPLE = [1314.68, 1509.32, 1672.86, 1832.55, 2005.13, 2215.02, 2536.73]


def test_mle_recording_adds_no_conditional_or_curve_evaluations(monkeypatch):
    original = conditional_profiles.mle_profile
    calls = []

    def measured(data, gamma, **options):
        calls.append(float(gamma))
        return original(data, gamma, **options)

    monkeypatch.setattr(profile_solvers, 'mle_profile', measured)
    monkeypatch.setattr(conditional_profiles, 'mle_profile', measured)
    ordinary = MLE(SAMPLE).run()
    plain_calls = list(calls)
    calls.clear()
    traced = MLE(SAMPLE)
    assert traced.run(trace=True) == ordinary
    assert calls == plain_calls
    details = traced.calculation_trace['details']
    assert len(details['reading_frames']) == len(calls)
    assert [p['normalized_gamma'] for p in details['reading_frames']] == calls
    assert {p['source'] for p in details['selected_shape_evaluations']} == {'solver'}


def test_normalized_evaluation_identity_is_kept_at_support_rounding_collisions():
    model = MLE([310, 342, 353, 365, 383, 393, 403, 412, 451, 456])
    model.run(trace=True)
    details = model.calculation_trace['details']
    for frame in details['reading_frames']:
        point = next(p for p in details['profile_values'] if p['normalized_gamma'] == frame['normalized_gamma'])
        assert frame['evaluation'] == point['evaluation']
        beta, value = frame['beta'], frame['shape_score']
        plotted = frame['shape_chart']['series'][0]['points']
        assert any(p['x'] == beta and p['y'] == value for p in plotted)


@pytest.mark.parametrize('factor', [1., 1e240])
def test_scale_rows_recover_the_returned_scale_including_overflow(factor):
    model = MLE(np.asarray(SAMPLE)*factor)
    beta, eta, gamma, _, ok = model.run(trace=True)
    assert ok
    scale = model.calculation_trace['details']['scale_calculation']
    assert sum(p['scaled_power'] for p in scale['samples']) == pytest.approx(scale['scaled_sum'])
    assert scale['reference_distance'] * scale['scaled_mean']**(1/beta) == pytest.approx(eta, rel=3e-13)
    assert scale['use_scaled'] is (factor > 1)
    json.dumps(model.calculation_trace, allow_nan=False)


def test_no_finite_candidate_never_creates_a_final_frame_or_parameter():
    model = MLE(np.random.default_rng(0).weibull(.6, 30)*50)
    result = model.run(trace=True)
    record = model.calculation_trace
    assert result[:3] == [None, None, None]
    assert record['selection']['status'] == 'no_finite_local_maximum'
    assert record['details']['candidates'] == []
    assert not any(frame['final'] for frame in record['details']['reading_frames'])
    assert all(not record['selection'].get(p) for p in ('beta', 'eta', 'gamma'))
    json.dumps(record, allow_nan=False)
