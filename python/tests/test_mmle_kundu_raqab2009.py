"""Single-sample Kundu–Raqab MMLE: archived case and independent score root."""
import sys
from pathlib import Path

import numpy as np
import pytest
from scipy.optimize import brentq
from scipy.special import logsumexp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from methods.mmle import MMLE
from methods.mmle_ch import MMLE as MMLE_CH
from methods.registry import resolve_method
from studies.common.runner import run_method

SAMPLE = [1095.152505835801, 1183.164246506551, 1193.7594200675674,
          1378.183094629827, 1455.4795722007577, 1498.7728191194542,
          1916.043346962928]


@pytest.fixture(autouse=True)
def isolate_incomplete_torch_test_stub(monkeypatch):
    """Other suite modules install a torch stub lacking SciPy's Tensor probe.

    NumPy-only MMLE needs no torch. Remove only an incomplete test stub for
    this test, then let monkeypatch restore the collection state afterward.
    """
    module = sys.modules.get('torch')
    if module is not None and not hasattr(module, 'Tensor'):
        monkeypatch.delitem(sys.modules, 'torch')


def test_archived_case_and_independent_profile_score():
    """Printed equations (4),(6),(9)–(11), reduced to one retained sample."""
    model = MMLE(SAMPLE)
    beta, eta, gamma, r2, ok = model.run()
    assert ok and r2 == 0.
    assert gamma == min(SAMPLE)
    assert np.allclose([beta, eta, gamma],
                       [1.4485886121720155, 379.2748797548912, 1095.152505835801],
                       atol=1e-12, rtol=0.)
    logs = np.log(np.sort(SAMPLE)[1:] - gamma)

    def score(shape):
        normalized = np.exp(shape * logs - logsumexp(shape * logs))
        return 1. / shape + logs.mean() - normalized @ logs

    root = brentq(score, .1, 20., xtol=1e-13)
    assert abs(beta - root) < 1e-6
    assert abs(score(beta)) < 1e-7
    assert abs(eta - np.exp((logsumexp(beta * logs) - np.log(len(logs))) / beta)) < 1e-12
    info = model.last_solution_info
    assert info['deleted_observations'] == 1
    assert info['effective_sample_min'] == sorted(SAMPLE)[1]
    assert info['gamma_is_original_sample_minimum']
    assert info['no_firth'] and info['no_domain_caps'] and info['no_fallback']


def test_iteration_budget_failure_is_not_rescued():
    result = run_method('mmle', SAMPLE, initial_shape=2.,
                        shape_absolute_step_tolerance=1e-12, max_iterations=1,
                        trace=True)
    assert result['beta_hat'] is None and not result['converged']
    info = result['extra']['solution_info']
    assert info['status'] == 'fixed_point_not_converged'
    assert info['initial_shape'] == 2. and info['iterations'] == 1
    assert info['max_iterations'] == 1
    assert info['shape_absolute_step_tolerance'] == 1e-12
    assert len(result['trace_data']) == 1


def test_shape_above_ten_has_no_artificial_cap():
    beta, eta, gamma, _, ok = MMLE([1., 100., 108., 116., 124., 132.]).run()
    assert ok and beta > 10. and eta > 0. and gamma == 1.


def test_tied_minimum_cannot_be_silently_deleted_twice():
    model = MMLE([1., 1., 2., 3.])
    assert model.run() == [None, None, None, 0., False]
    assert model.last_solution_info['deleted_observations'] == 1
    assert model.last_solution_info['status'] == 'fixed_point_not_converged'


def test_registry_preserves_distinct_ch_dispatch():
    assert resolve_method('mmle') == ('mmle', MMLE)
    assert resolve_method('mmle_ch') == ('mmle_ch', MMLE_CH)
    assert run_method('mmle_ch', SAMPLE)['method_id'] == 'mmle_ch'


@pytest.mark.parametrize('kwargs', [
    {'initial_shape': 0.}, {'initial_shape': float('nan')},
    {'shape_absolute_step_tolerance': -1.}, {'max_iterations': 0},
])
def test_invalid_iteration_configuration_is_rejected(kwargs):
    with pytest.raises(ValueError):
        MMLE(SAMPLE).run(**kwargs)
