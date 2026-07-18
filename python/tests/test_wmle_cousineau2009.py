"""WMLE 论文级验真测试

专项论文：Cousineau (2009), "Nearly unbiased estimators for the
three-parameter Weibull distribution with greater efficiency than the
iterative likelihood method", Br. J. Math. Stat. Psychol. 62(1)
（src/content/182-088-pdf原文.md）。

- 式(3)/(4)：以 W2、W3 加权的形状/位置方程组 + 以 W1 加权的尺度闭式解；
- Table 2/3/4：中位数权重 J1、J2、J3 数值表；
- §4 数值例：X={310,...,456}, n=10, 真值 {shape=2, scale=100, loc=300}，
  WMLE 结果 {shape=2.29, loc=283.7, scale=116.0}，
  两步 MLE {2.62, 280.9, 119.0}，迭代 MLE {2.80, 274.8, 126.0}。

注：实现内嵌的 J3 表来自论文作者仓库 github.com/dcousin3/wMLE（0.1 步长），
比论文正文使用的 0.25 步长插值更细，数值例复现允许相应容差。
"""

import sys
import os

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "methods"))

from studies.common.runner import run_method
from methods import wmle as wmle_module
from methods.wmle import WMLE, get_weight_j1, get_weight_j2, get_weight_j3

# Cousineau (2009) §4 数值例
COUSINEAU_X = [310, 342, 353, 365, 383, 393, 403, 412, 451, 456]


def _weighted_equation_terms(shape, loc, data):
    """独立实现论文式(3) 的两个加权方程（不复述被测代码）。"""
    arr = np.array(sorted(data), dtype=float)
    n = len(arr)
    xa = arr - loc
    w2 = get_weight_j2(n)
    w3 = get_weight_j3(n, shape)
    term1 = (w2 / shape + np.mean(np.log(xa))
             - np.sum(np.log(xa) * xa ** shape) / np.sum(xa ** shape))
    term2 = np.mean(1.0 / xa) * np.sum(xa ** shape) / np.sum(xa ** (shape - 1)) - w3
    return term1, term2


def test_j1_j2_match_paper_tables():
    """J1/J2 与论文 Table 2/3 一致（论文精度 3 位小数，允许 ±0.002 MC 舍入）。"""
    paper_j1 = {1: 0.693, 4: 0.918, 5: 0.934, 8: 0.959, 10: 0.967, 16: 0.979}
    paper_j2 = {1: 0.000, 4: 0.638, 8: 0.817, 10: 0.853, 16: 0.908}
    for n, val in paper_j1.items():
        assert abs(get_weight_j1(n) - val) < 0.002, f"J1({n})"
    for n, val in paper_j2.items():
        assert abs(get_weight_j2(n) - val) < 0.002, f"J2({n})"


def test_j3_matches_paper_table4_at_n10():
    """J3 与论文 Table 4 (n=10) 一致（论文两位小数精度，MC 噪声容差 0.03）。"""
    paper_j3_n10 = {0.5: 8.643, 1.0: 3.365, 1.5: 2.180, 2.0: 1.758, 2.5: 1.552}
    for shape, val in paper_j3_n10.items():
        assert abs(get_weight_j3(10, shape) - val) < 0.03, f"J3(10, {shape})"


def test_j1_uses_exact_median_beyond_table():
    """n > 100 时 J1 取 W1 ~ Gamma(n, 1/n) 的精确中位数，且与表尾连续。"""
    j1_100 = get_weight_j1(100)
    j1_101 = get_weight_j1(101)
    # 中位数近似 (n - 1/3) / n
    assert abs(j1_101 - (1 - 1.0 / (3 * 101))) < 1e-3
    assert abs(j1_101 - j1_100) < 0.002
    assert get_weight_j1(1000) > 0.999


def test_wmle_reproduces_cousineau_numerical_example():
    """复现论文 §4 数值例的 WMLE 解（J3 表分辨率差异容差内）。"""
    r = run_method("wmle", COUSINEAU_X)
    assert r["method_id"] == "wmle"
    assert r["converged"] is True
    # 论文：shape=2.29, scale=116.0, loc=283.7
    assert abs(r["beta_hat"] - 2.29) < 0.06
    assert abs(r["eta_hat"] - 116.0) < 2.5
    assert abs(r["gamma_hat"] - 283.7) < 2.5


def test_wmle_solution_satisfies_weighted_equations():
    """返回的 (shape, loc) 是论文式(3) 加权方程组的根（残差 ~ 0）。"""
    r = run_method("wmle", COUSINEAU_X)
    t1, t2 = _weighted_equation_terms(r["beta_hat"], r["gamma_hat"], COUSINEAU_X)
    assert t1 ** 2 + t2 ** 2 < 1e-8


def test_wmle_scale_uses_j1_closed_form():
    """尺度参数满足论文式(3) 的 J1 加权闭式解。"""
    r = run_method("wmle", COUSINEAU_X)
    arr = np.array(sorted(COUSINEAU_X), dtype=float)
    n = len(arr)
    xa = arr - r["gamma_hat"]
    expected_scale = (np.sum(xa ** r["beta_hat"]) / (n * get_weight_j1(n))) ** (1 / r["beta_hat"])
    assert abs(r["eta_hat"] - expected_scale) < 1e-9


def test_wmle_differs_from_mle_identity():
    """同一样本上 WMLE 与 MLE 输出可区分（论文 §4：2.29 vs 2.80），且身份正确。"""
    r_wmle = run_method("wmle", COUSINEAU_X)
    r_mle = run_method("mle", COUSINEAU_X)
    assert r_wmle["method_id"] == "wmle"
    assert r_wmle["method_variant"] == "wmle"
    assert r_mle["method_id"] == "mle"
    # WMLE 收缩形状估计（更接近真值 2）：明显小于迭代 MLE 的形状估计
    assert r_wmle["beta_hat"] < r_mle["beta_hat"] - 0.2


def test_wmle_optimizer_failure_returns_explicit_failure(monkeypatch):
    """优化器失败时显式失败，不再返回伪造的 [1, 100, 0, 0]。"""

    class _FailResult:
        success = False
        message = "forced failure"
        x = np.array([2.0, 0.0])
        fun = 1e9

    monkeypatch.setattr(wmle_module, "minimize", lambda *a, **k: _FailResult())

    r = run_method("wmle", COUSINEAU_X)

    assert r["converged"] is False
    # 不允许出现旧版伪结果 (beta=1, eta=100, gamma=0, converged=True)
    assert not (r["converged"] is True and r["beta_hat"] == 1.0 and r["eta_hat"] == 100.0)
    assert r["extra"]["solution_info"]["status"] == "optimizer_failed"


def test_wmle_degenerate_sample_fails_at_shape_bound():
    """退化样本（零方差）无加权方程根：形状压上界必须显式失败。"""
    r = run_method("wmle", [5.0, 5.0, 5.0, 5.0, 5.0])
    assert r["converged"] is False
    assert r["beta_hat"] is None
    assert r["extra"]["raw_status"] == "shape_at_bound"


def test_wmle_location_boundary_diagnostic_recorded():
    """位置根被平台约束截到 0 时，诊断信息记录边界标记（不冒充无约束根）。"""
    rng = np.random.default_rng(3)
    sample = (rng.weibull(3.5, 20) * 200.0).tolist()
    r = run_method("wmle", sample)
    assert r["converged"] is True
    info = r["extra"]["solution_info"]
    assert info["status"] == "ok"
    if r["gamma_hat"] < 1e-6:
        assert info["location_at_zero_boundary"] is True


def test_wmle_gamma_estimate_stays_inside_support():
    """位置估计满足 0 <= gamma < min(x)，参数均为有限合法值。"""
    rng = np.random.default_rng(11)
    for shape, scale, loc in [(1.5, 100.0, 5.0), (2.5, 80.0, 10.0)]:
        sample = (loc + scale * rng.weibull(shape, 40)).tolist()
        r = run_method("wmle", sample)
        assert r["converged"] is True
        assert r["beta_hat"] > 0
        assert r["eta_hat"] > 0
        assert 0.0 <= r["gamma_hat"] < min(sample)
        assert np.isfinite(r["beta_hat"])
        assert np.isfinite(r["eta_hat"])
        assert np.isfinite(r["gamma_hat"])
