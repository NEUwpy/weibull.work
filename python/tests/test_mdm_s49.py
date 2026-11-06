"""S4.9 默认 MDM：离散搜索、边界截断与 trace 一致性测试。"""

import os
import sys

import pytest
import numpy as np
from scipy.optimize import minimize_scalar

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from methods.mdm import MDM
from studies.common.sample import generate_sample


def test_default_mdm_truncates_negative_offset_root_to_zero():
    """已知旧版 no_intersection 样本应返回 gamma=0 边界截断解。"""
    sample = generate_sample(1.5, 100.0, 0.0, 10, 1)

    mdm = MDM(sample)
    beta, eta, gamma, r2, status = mdm.run(trace=True, offset=0.1, gamma_steps=20)

    assert status is True
    assert beta is not None and beta > 0
    assert eta is not None and eta > 0
    assert gamma == 0.0
    assert r2 is not None

    trace = mdm.trace_data
    assert trace["solution_strategy"] == "truncated_at_zero"
    assert trace["constraint"] == "gamma >= 0"
    assert trace["gamma_steps"] == 20
    assert trace["optimal_gamma"] == 0.0
    computed = [p for p in trace["grad_gamma_curve"] if p['source'] != 'display_sample']
    assert len(computed) == 20
    assert len(trace["grad_gamma_curve"]) == len(computed)
    assert trace["probe_gradient_at_zero"] > trace["target_offset"]


def test_default_mdm_uses_brent_root_when_zero_probe_is_below_offset():
    """g(0) < offset 时应使用右端括弧 + Brent 定根，而不是离散网格插值。"""
    sample = generate_sample(2.0, 100.0, 5.0, 30, 0)

    mdm = MDM(sample)
    beta, eta, gamma, r2, status = mdm.run(trace=True, offset=0.1, gamma_steps=30)

    assert status is True
    assert beta is not None and beta > 0
    assert eta is not None and eta > 0
    assert gamma is not None and gamma > 0
    assert r2 is not None

    trace = mdm.trace_data
    assert trace["search_strategy"] == "geometric_from_tmin"
    assert trace["solution_strategy"] == "brent_root"
    assert trace["root_solver"] == "brent"
    assert trace["gamma_steps"] == 30
    assert len(trace["grad_gamma_curve"]) >= 30
    assert trace["probe_gradient_at_zero"] < trace["target_offset"]

    bracket = trace["root_bracket"]
    assert bracket is not None
    left = bracket["left"]
    right = bracket["right"]
    assert min(left["gamma"], right["gamma"]) <= gamma <= max(left["gamma"], right["gamma"])
    assert (left["gradient"] - trace["target_offset"]) * (
        right["gradient"] - trace["target_offset"]
    ) <= 0
    assert trace["right_anchor_gamma"] == right["gamma"]
    assert trace["right_anchor_gradient"] == right["gradient"]
    assert trace["root_solver_iterations"] > 0


def test_default_mdm_fits_right_edge_when_anchor_is_still_below_offset():
    """最右端锚点仍低于 offset 时也应补出内点解，而不是引入第四种截断。"""
    sample = generate_sample(2.0, 100.0, 5.0, 30, 0)

    mdm = MDM(sample)
    beta, eta, gamma, r2, status = mdm.run(trace=True, offset=5.0, gamma_steps=30)

    assert status is True
    assert beta is not None and beta > 0
    assert eta is not None and eta > 0
    assert gamma is not None and 0 < gamma < min(sample)
    assert r2 is not None

    trace = mdm.trace_data
    assert trace["solution_strategy"] == "brent_root"
    assert trace["root_solver"] == "right_edge_fit"
    assert trace["root_bracket"] is not None
    assert trace.get("offset_diagnostic") is None
    assert trace["right_edge_extrapolation"] is not None
    assert trace["right_anchor_gradient"] < trace["target_offset"]


def test_default_mdm_trace_curve_matches_solver_gradient_function():
    """trace 中的梯度曲线应展示后端求解器使用的同一套 g(gamma)。"""
    sample = generate_sample(2.0, 100.0, 5.0, 30, 0)

    mdm = MDM(sample)
    _, _, gamma, _, _ = mdm.run(trace=True, offset=0.1, gamma_steps=30)

    trace = mdm.trace_data
    curve = trace["grad_gamma_curve"]

    zero_point = min(curve, key=lambda point: abs(point["gamma"]))
    assert zero_point["gradient"] == pytest.approx(trace["probe_gradient_at_zero"])

    root_point = min(curve, key=lambda point: abs(point["gamma"] - gamma))
    assert root_point["gamma"] == pytest.approx(gamma)
    assert root_point["gradient"] == pytest.approx(trace["target_offset"], abs=1e-5)


def test_mdm_curves_only_use_actual_solver_evaluations(monkeypatch):
    from methods import mdm as mdm_module
    evaluations = []
    original = mdm_module.minimize_scalar
    def counted(function, *args, **kwargs):
        def objective(beta):
            evaluations.append(float(beta))
            return function(beta)
        return original(objective, *args, **kwargs)
    monkeypatch.setattr(mdm_module, 'minimize_scalar', counted)
    sample = np.array([1314.68, 1509.32, 1672.86, 1832.55, 2005.13, 2215.02, 2536.73])
    mdm = MDM(sample)
    plain = MDM(sample).run(trace=False, offset=.12)
    original_evaluations = list(evaluations)
    evaluations.clear()
    assert mdm.run(trace=True, offset=.12) == plain
    assert evaluations == original_evaluations
    curve = mdm.trace_data['grad_gamma_curve']
    by_gamma = {point['gamma']: point for point in curve}
    for point in mdm.calculation_trace['details']['root_evaluations']:
        assert by_gamma[point['gamma']]['gradient'] == point['gradient']
        assert by_gamma[point['gamma']]['source'] in ('solver_evaluation', 'solver_root')
    expected_gammas = {point['gamma'] for point in mdm.calculation_trace['details']['gradient_scan']}
    expected_gammas.update(point['gamma'] for point in mdm.calculation_trace['details']['root_evaluations'])
    assert set(by_gamma) == expected_gammas
    assert all(point['source'] != 'display_sample' for point in curve)
    plotted_shape = mdm.trace_data['sigma_beta_curve']
    recorded_shape = mdm.calculation_trace['charts'][0]['series'][0]['points']
    assert sorted((p['beta'], p['sigma'], p['evaluation']) for p in plotted_shape) == sorted(
        (p['x'], p['y'], p['evaluation']) for p in recorded_shape)

    probabilities = (np.arange(1, len(sample)+1)-.3)/(len(sample)+.4)
    quantiles = -np.log1p(-probabilities)
    def sigma(gamma):
        return minimize_scalar(lambda beta: np.std((sample-gamma)/quantiles**(1/beta), ddof=1),
                               bounds=(.1, 15.), method='bounded').fun
    # Check actual function values independently near the selected root.
    nearest = sorted(curve, key=lambda point: abs(point['gamma']-plain[2]))[:3]
    for point in nearest:
        h = min(sample)*1e-5
        expected = (sigma(point['gamma']+h)-sigma(point['gamma']-h))/(2*h)
        assert point['gradient'] == pytest.approx(expected, abs=2e-8)
    for surface in mdm.trace_data['sigma_beta_gamma']:
        assert list(zip(surface['betas'], surface['sigmas'])) == sorted(
            (p['beta'], p['sigma']) for p in surface['solver_points'])
        for point in surface['solver_points']:
            expected = np.std((sample-surface['gamma'])/quantiles**(1/point['beta']), ddof=1)
            assert point['sigma'] == pytest.approx(expected, rel=2e-12)


def test_default_mdm_records_lightweight_solution_info_without_trace():
    """批量研究可读取轻量求解摘要，而不必为每个 delta 生成完整 trace。"""
    sample = generate_sample(2.0, 100.0, 5.0, 30, 0)

    mdm = MDM(sample)
    mdm.run(trace=False, offset=0.1, gamma_steps=30)

    info = mdm.last_solution_info
    assert info["solution_strategy"] == "brent_root"
    assert info["root_solver"] == "brent"
    assert info["optimal_gamma"] > 0
    assert info["target_offset"] == pytest.approx(0.1)


@pytest.mark.parametrize("offset", [0.0, 0.1, 0.5])
def test_default_mdm_is_scale_equivariant_for_fixed_offset(offset):
    """整体缩放寿命时 beta 不变，eta/gamma 应按相同比例缩放。"""
    sample = generate_sample(2.0, 1.0, 1.0, 7, 0)
    scale = 1000.0

    base = MDM(sample).run(trace=False, offset=offset, gamma_steps=200)
    scaled = MDM(sample * scale).run(
        trace=False,
        offset=offset,
        gamma_steps=200,
    )

    beta, eta, gamma, r2, status = base
    beta_scaled, eta_scaled, gamma_scaled, r2_scaled, status_scaled = scaled

    assert status is True and status_scaled is True
    assert beta_scaled == pytest.approx(beta, rel=1e-6, abs=1e-8)
    assert eta_scaled / scale == pytest.approx(eta, rel=1e-6, abs=1e-8)
    assert gamma_scaled / scale == pytest.approx(gamma, rel=1e-6, abs=1e-8)
    assert r2_scaled == pytest.approx(r2, rel=1e-8, abs=1e-10)
