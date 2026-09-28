"""Park (2017) Proposed+Plot: §2 分段绘图位置、§5 式(2)/(3)、表1。

DOI: 10.23055/ijietap.2017.24.4.2848。
用论文算例和独立导数定根检验位置估计，不把 Li 线性化背景当作算法来源。
"""

import sys
import os

import numpy as np
import pytest
from scipy.optimize import brentq

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from methods.lre import LRE
from studies.common.runner import run_method
from studies.common.sample import generate_sample


FIXED_SAMPLE = generate_sample(2.0, 100.0, 5.0, 30, 0)


# Park §5 Murthy et al. (2004) 的24个完整寿命，顺序沿用原文。
PARK_SAMPLE = [
    30.94, 18.51, 16.62, 51.56, 22.85, 22.38, 19.08, 49.56,
    17.12, 10.67, 25.43, 10.24, 27.47, 14.70, 14.10, 29.93,
    27.98, 36.02, 19.40, 14.97, 22.57, 12.26, 18.14, 18.84,
]


def test_park_table1_and_independent_stationary_equation():
    t = np.sort(PARK_SAMPLE)
    v = np.log(-np.log1p(-(np.arange(1, 25) - 0.5) / 24))

    def equation3(gamma):
        u = np.log(t - gamma)
        w = -1 / (t - gamma)
        u, v0, w = u - u.mean(), v - v.mean(), w - w.mean()
        return np.dot(w, v0) / np.dot(u, v0) - np.dot(u, w) / np.dot(u, u)

    gamma = brentq(equation3, 9.0, 9.5, xtol=1e-13)
    slope, intercept = np.linalg.lstsq(
        np.column_stack([np.log(t - gamma), np.ones(len(t))]), v, rcond=None,
    )[0]
    expected = [slope, np.exp(-intercept / slope), gamma]
    model = LRE(PARK_SAMPLE)
    actual = model.run()
    assert actual[4] is True
    np.testing.assert_allclose(actual[:3], expected, rtol=2e-7)
    assert actual[2] == pytest.approx(9.198, abs=0.0005)
    assert actual[1] == pytest.approx(15.116, abs=0.0005)
    # 原表写1.363；公式复算1.363761，常规三位小数为1.364。
    # 两者独立记录，不修改绘图位置/舍入去强行匹配表中末位。
    assert actual[0] == pytest.approx(1.363761, abs=1e-6)
    assert abs(actual[0] - 1.363) < 0.001
    assert np.sqrt(actual[3]) == pytest.approx(0.9902, abs=0.00005)
    assert model.last_solution_info['implementation'] == 'park2017_proposed_plot'


@pytest.mark.parametrize('n', [3, 7, 10, 11, 24])
def test_park_plotting_positions_recover_exact_probability_line(n):
    """在两段公式及切换边界生成精确概率图直线；Bernard 替换会破坏恢复。"""
    i = np.arange(1, n + 1)
    p = (i - 0.375) / (n + 0.25) if n <= 10 else (i - 0.5) / n
    sample = 3 + 15 * np.sqrt(-np.log1p(-p))
    model = LRE(sample)
    actual = model.run()
    np.testing.assert_allclose(actual[:3], [2, 15, 3], rtol=2e-6)
    assert actual[3] == pytest.approx(1, abs=1e-12)


def test_lre_regression_and_r_squared_use_park_scores():
    r = run_method('lre', FIXED_SAMPLE)
    t = np.sort(FIXED_SAMPLE)
    v = np.log(-np.log1p(-(np.arange(1, len(t) + 1) - 0.5) / len(t)))
    u = np.log(t - r['gamma_hat'])
    slope, intercept = np.polyfit(u, v, 1)
    r2 = 1 - np.sum((v - (slope * u + intercept)) ** 2) / np.sum((v - v.mean()) ** 2)
    assert r['beta_hat'] == pytest.approx(slope, rel=1e-12)
    assert r['eta_hat'] == pytest.approx(np.exp(-intercept / slope), rel=1e-12)
    assert r['r_squared'] == pytest.approx(r2, abs=1e-12)
    assert r['extra']['solution_info']['rho_squared'] == pytest.approx(r2, abs=1e-12)


@pytest.mark.parametrize('factor', [1e-12, 1e-6, 1e6, 1e12])
def test_lre_change_of_time_unit(factor):
    original = LRE(PARK_SAMPLE).run()
    scaled = LRE(np.array(PARK_SAMPLE) * factor).run()
    assert scaled[4] is True
    np.testing.assert_allclose(
        [scaled[0], scaled[1] / factor, scaled[2] / factor, scaled[3]],
        original[:4], rtol=2e-7,
    )


def test_lre_keeps_zero_location_boundary():
    p = (np.arange(1, 11) - 0.375) / 10.25
    sample = np.sqrt(-np.log1p(-p)) - 0.1
    model = LRE(sample)
    result = model.run()
    assert result[4] is True
    assert result[2] == 0
    assert model.last_solution_info['location_at_zero_boundary'] is True


def test_lre_identity_distinct_from_mle():
    """LRE 与 MLE 在同一固定样本上输出可区分，且身份正确。"""
    r_lre = run_method("lre", FIXED_SAMPLE)
    r_mle = run_method("mle", FIXED_SAMPLE)
    assert r_lre["method_id"] == "lre"
    assert r_lre["method_variant"] == "lre"
    assert r_mle["method_id"] == "mle"
    assert abs(r_lre["beta_hat"] - r_mle["beta_hat"]) > 0.01
    assert 0.0 <= r_lre["gamma_hat"] < min(FIXED_SAMPLE)


def test_lre_gamma_stays_in_support():
    """LRE 的 γ 估计满足 0 ≤ γ < t_(1)，参数有限。"""
    for seed in range(3):
        s = generate_sample(2.0, 100.0, 5.0, 30, seed)
        r = run_method("lre", s)
        assert r["converged"] is True
        assert 0.0 <= r["gamma_hat"] < min(s)
        assert np.isfinite(r["beta_hat"]) and r["beta_hat"] > 0
        assert np.isfinite(r["eta_hat"]) and r["eta_hat"] > 0


def test_lre_not_an_alias():
    """LRE 不是任何其他方法的别名或回退（run_method 始终返回 lre ID）。"""
    r = run_method("lre", FIXED_SAMPLE)
    assert r["method_id"] == "lre"
    assert r["extra"] is None or "solution_info" in (r["extra"] or {})


def test_lre_large_location_scale_does_not_stick_at_zero_boundary():
    """γ 为数千时仍应搜索相关系数峰值，不能因零起点的数值步长停在下边界。"""
    sample = generate_sample(2.0, 1000.0, 3000.0, 15, 0, seed=20260825)
    r = run_method("lre", sample)
    assert r["converged"] is True
    assert r["gamma_hat"] > 1000.0
    info = r["extra"]["solution_info"]
    assert info["location_at_zero_boundary"] is False
    assert info["rho_squared"] > 0.95


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.parametrize("n_eq", [5, 7, 10, 12])
def test_lre_degenerate_all_equal_fails_for_multiple_sizes(n_eq):
    """全等值样本由统一 runner 在进入具体求解器前显式拒绝。"""
    r = run_method("lre", [5.0] * n_eq)
    assert r["converged"] is False, f"n={n_eq} should fail"
    assert r["beta_hat"] is None, f"n={n_eq} beta should be None"
    assert r["extra"] == {
        "error": "invalid sample: observations must not all be equal"
    }


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
def test_lre_insufficient_sample_fails_explicitly():
    """n < 3 无相关系数自由度，必须显式失败。"""
    r = run_method("lre", [1.0, 2.0])
    assert r["converged"] is False
    assert r["beta_hat"] is None
    assert r["extra"]["raw_status"] == "insufficient_sample"
