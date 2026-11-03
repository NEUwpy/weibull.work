"""Repeated and single estimation must use the same canonical method and offset."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from studies.common.simulation import simulate_method
from studies.common.runner import run_method
from studies.common.sample import generate_sample


@pytest.mark.parametrize('method', ['mdm', 'wmle', 'mm'])
def test_simulation_uses_same_method_as_single_calculation(method):
    rows = simulate_method(method, 2., 1000., 1000., 7, 2, seed=42, offset=.24)
    for row in rows:
        sample = generate_sample(2., 1000., 1000., 7, row['sim_id'], seed=42)
        kwargs = {'offset': .24} if method == 'mdm' else {}
        expected = run_method(method, sample, **kwargs)
        assert row['method_id'] == method
        assert row['est_beta'] == expected['beta_hat']
        assert row['est_eta'] == expected['eta_hat']
        assert row['est_gamma'] == expected['gamma_hat']
        if method == 'mdm':
            assert row['offset_value'] == .24
