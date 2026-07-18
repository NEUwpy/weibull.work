"""MM 论文级验真测试

专项论文：Cran (1988), "Moment Estimators for the 3-Parameter Weibull
Distribution", IEEE Transactions on Reliability 37(4)
（src/content/182-102-pdf原文.md）。

- 式(1)：Weibull 矩 μ̄_k = a + b·Γ(1+1/c)/k^{1/c}；
- 式(2a)-(2c)：参数由 μ̄₁, μ̄₂, μ̄₄ 显式解出；
- 式(3)：样本 Weibull 矩 m̄_k = Σ (1-r/n)^k (x_(r+1)-x_(r))，m̄₁ = 样本均值；
- 采纳性：m̄₂ ≥ (m̄₁+m̄₄)/2 时 c*, b* 非正 → 必须失败；
- a* < 0 → a=0；a* ≥ x_(1) → 替代式 a** = x_(1) - b*Γ(1+1/c*)/n^{1/c*}；
- Appendix 等变性：c*(x)=c*(y), a*(x)=a+b·a*(y), b*(x)=b·b*(y)。

论文 Example 1/2 使用 Harter & Moore (1965) Table 1 数据，该原始数据不在
本地文献库中，无法逐值复现；以论文自身的解析恒等式、手算样本矩和等变性
恒等式作为基准（均为论文明文给出的可核对关系）。
"""

import sys
import os

import numpy as np
from scipy.special import gamma as gamma_fn

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from methods.mm import sample_weibull_moment, solve_from_weibull_moments
from studies.common.runner import run_method


def test_population_moment_identity_recovers_parameters_exactly():
    """式(1)+(2a-2c) 解析闭环：用精确总体矩反解必须还原 (c, a, b)。"""
    for c, a, b in [(2.0, 10.0, 100.0), (0.8, 0.0, 10.0), (3.0, 20.0, 100.0)]:
        mu = lambda k: a + b * gamma_fn(1 + 1.0 / c) / k ** (1.0 / c)
        solved = solve_from_weibull_moments(mu(1), mu(2), mu(4))
        assert solved is not None
        c_hat, a_hat, b_hat = solved
        assert abs(c_hat - c) < 1e-9
        assert abs(a_hat - a) < 1e-6
        assert abs(b_hat - b) < 1e-6


def test_sample_weibull_moments_match_hand_computation():
    """式(3) 手算基准：x=[2,5,10] 的 m̄₁=17/3, m̄₂=35/9, m̄₄=215/81。"""
    x = np.array([2.0, 5.0, 10.0])
    assert abs(sample_weibull_moment(x, 1) - 17.0 / 3.0) < 1e-12
    assert abs(sample_weibull_moment(x, 2) - 35.0 / 9.0) < 1e-12
    assert abs(sample_weibull_moment(x, 4) - 215.0 / 81.0) < 1e-12


def test_first_sample_moment_equals_sample_mean():
    """论文：m̄₁ = x̄（任意样本恒等）。"""
    rng = np.random.default_rng(9)
    x = np.sort(rng.weibull(2.0, 50) * 80.0 + 30.0)
    assert abs(sample_weibull_moment(x, 1) - x.mean()) < 1e-9


def test_equivariance_identities_from_appendix():
    """Appendix：c*(x)=c*(y)、a*(x)=a+b·a*(y)、b*(x)=b·b*(y)（无修正路径样本）。"""
    rng = np.random.default_rng(2)
    y = np.sort(rng.weibull(1.5, 60))
    a_shift, b_scale = 50.0, 200.0
    x = a_shift + b_scale * y

    ry = run_method("mm", y.tolist())
    rx = run_method("mm", x.tolist())

    assert ry["converged"] is True and rx["converged"] is True
    assert ry["extra"]["solution_info"]["location_adjustment"] is None
    assert rx["extra"]["solution_info"]["location_adjustment"] is None

    assert abs(rx["beta_hat"] - ry["beta_hat"]) < 1e-9
    assert abs(rx["gamma_hat"] - (a_shift + b_scale * ry["gamma_hat"])) < 1e-6
    assert abs(rx["eta_hat"] - b_scale * ry["eta_hat"]) < 1e-6


def test_inadmissible_moments_fail_explicitly():
    """m̄₂ ≥ (m̄₁+m̄₄)/2 时必须显式失败（论文：c*, b* 非正不可用）。"""
    # 构造样本：间隙集中在高秩处 → m̄₁-m̄₂ < m̄₂-m̄₄
    r = run_method("mm", [1.0, 2.0, 2.01, 2.02])
    assert r["converged"] is False
    assert r["beta_hat"] is None
    assert r["extra"]["raw_status"] == "inadmissible_moments"

    # 全等值样本（零差分）同样不可采纳
    r2 = run_method("mm", [5.0] * 10)
    assert r2["converged"] is False
    assert r2["extra"]["raw_status"] == "inadmissible_moments"


def test_insufficient_sample_fails_explicitly():
    r = run_method("mm", [1.0, 2.0])
    assert r["converged"] is False
    assert r["extra"]["raw_status"] == "insufficient_sample"


def test_negative_location_clamped_to_zero_per_paper():
    """a* < 0 时按论文取 a=0，并以 b = m̄₁/Γ(1+1/c*) 重算尺度。"""
    rng = np.random.default_rng(0)
    sample = np.sort(rng.weibull(2.0, 100) * 100.0 + 10.0)
    r = run_method("mm", sample.tolist())
    assert r["converged"] is True
    info = r["extra"]["solution_info"]
    assert info["location_adjustment"] == "clamped_to_zero"
    assert r["gamma_hat"] == 0.0
    expected_scale = info["m1"] / gamma_fn(1 + 1.0 / r["beta_hat"])
    assert abs(r["eta_hat"] - expected_scale) < 1e-9


def test_location_exceeding_minimum_uses_paper_alternative():
    """a* ≥ x_(1) 时使用论文替代式 a**，且结果保持 0 ≤ a < x_(1)。"""
    rng = np.random.default_rng(1)
    sample = np.sort(rng.weibull(1.5, 200) * 50.0 + 20.0)
    r = run_method("mm", sample.tolist())
    assert r["converged"] is True
    info = r["extra"]["solution_info"]
    assert info["location_adjustment"] == "alternative_a_star_star"
    assert 0.0 <= r["gamma_hat"] < min(sample)
    # 替代式独立复算：a** = x_(1) - b*Γ(1+1/c*)/n^{1/c*}
    # （实现中 b 随 a** 重算，这里核对 a** 与位置的关系式）
    x = np.sort(np.asarray(sample))
    m1 = sample_weibull_moment(x, 1)
    expected_scale = (m1 - r["gamma_hat"]) / gamma_fn(1 + 1.0 / r["beta_hat"])
    assert abs(r["eta_hat"] - expected_scale) < 1e-9


def test_two_parameter_reference_estimates_recorded():
    """论文 LOCATION 节：2P 对照估计 c**, b** 写入诊断（阈值判断程序）。"""
    rng = np.random.default_rng(2)
    sample = np.sort(rng.weibull(1.5, 60)) * 100.0
    r = run_method("mm", sample.tolist())
    info = r["extra"]["solution_info"]
    x = np.sort(np.asarray(sample))
    m1 = sample_weibull_moment(x, 1)
    m2 = sample_weibull_moment(x, 2)
    expected_c2 = np.log(2.0) / (np.log(m1) - np.log(m2))
    assert abs(info["two_param_shape"] - expected_c2) < 1e-9
    assert abs(info["two_param_scale"] - m1 / gamma_fn(1 + 1.0 / expected_c2)) < 1e-9


def test_mm_recovers_parameters_approximately():
    """合法参数网格上的大样本恢复（矩估计为快速初估，容差相应放宽）。"""
    rng = np.random.default_rng(7)
    for shape, scale, loc in [(1.5, 50.0, 20.0), (1.0, 30.0, 5.0)]:
        sample = (loc + scale * rng.weibull(shape, 200)).tolist()
        r = run_method("mm", sample)
        assert r["converged"] is True
        assert np.isfinite(r["beta_hat"]) and r["beta_hat"] > 0
        assert np.isfinite(r["eta_hat"]) and r["eta_hat"] > 0
        assert 0.0 <= r["gamma_hat"] < min(sample)
        assert abs(r["beta_hat"] - shape) / shape < 0.5
        assert abs(r["eta_hat"] - scale) / scale < 0.5


def test_mm_identity_never_substituted():
    """run_method 返回身份必须是 mm 本身。"""
    rng = np.random.default_rng(2)
    sample = (np.sort(rng.weibull(1.5, 60)) * 100.0).tolist()
    r = run_method("mm", sample)
    assert r["method_id"] == "mm"
    assert r["method_variant"] == "mm"
