"""LSE 论文级验真测试

专项论文：Soman & Misra (1992), "A Least Square Estimation of Three
Parameters of a Weibull Distribution", Microelectronics Reliability
（src/content/182-104-pdf原文.md）。

- 式(3)/(4)/(6)：White (1969) 对数变换回归，X_i 取 reduced Log-Weibull
  顺序统计量期望（密度 h(w)=exp(w-e^w)）；ĉ=1/β̂, b̂=e^α̂；
- Procedure Step 1-4：对 μ 一维搜索，取 Fisher F = S_y²/S_res² 最大者；
- Example 1：n=30，真值 μ=500, c=1.7, b=40；论文 Table 1 F 峰在
  μ=502.1（ĉ=1.603, b̂=39.26）；
- Example 2：n=30，真值 μ=100, c=0.8, b=10；论文 Table 2 F 峰在
  μ=99.9（ĉ=0.8361, b̂=8.8521）。

论文使用 White (1969) 的舍入数表，本实现用数值积分精确计算 X_i，
故在同一 μ 处 ĉ/b̂ 与论文有 <1% 的表格舍入差，测试容差按此设定。
"""

import sys
import os

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from methods.lse import LSE, log_weibull_order_stat_means
from studies.common.runner import run_method

EULER_GAMMA = 0.5772156649015329

# Soman & Misra (1992) Example 1（真值 mu=500, c=1.7, b=40）
SOMAN_EX1 = [552.0525, 548.6083, 506.3785, 565.5352, 511.7620,
             515.2365, 516.1401, 514.7593, 520.6400, 513.8919,
             543.7966, 556.5106, 517.9078, 562.4553, 531.9044,
             539.6028, 518.5398, 565.7348, 541.8414, 554.3255,
             506.0710, 547.0142, 571.4103, 523.5997, 541.8120,
             519.8716, 556.1709, 548.5325, 544.3080, 538.5575]

# Soman & Misra (1992) Example 2（真值 mu=100, c=0.8, b=10）
SOMAN_EX2 = [102.4378, 114.7585, 103.5102, 101.3378, 141.7785,
             102.5250, 102.5244, 124.9970, 146.9202, 117.0452,
             103.5730, 113.6165, 102.2618, 110.0926, 107.1926,
             125.1443, 100.3264, 102.9202, 100.0017, 107.7962,
             101.3272, 101.3620, 102.5391, 100.0935, 104.8785,
             125.1759, 105.1076, 101.6966, 102.4999, 130.1677]


def _white_f_ratio(data, mu):
    """独立实现论文 Step 1-2：White 回归 + F 比（不复述被测代码）。"""
    t = np.sort(np.asarray(data, dtype=float))
    n = len(t)
    x = log_weibull_order_stat_means(n)
    y = np.log(t - mu)
    slope = np.sum((x - x.mean()) * (y - y.mean())) / np.sum((x - x.mean()) ** 2)
    intercept = y.mean() - slope * x.mean()
    s_y2 = np.sum((y - y.mean()) ** 2) / (n - 1)
    s_res2 = np.sum((y - (intercept + slope * x)) ** 2) / (n - 2)
    return 1.0 / slope, np.exp(intercept), s_y2 / s_res2


def test_order_stat_means_match_known_values():
    """X_i 基础值核对：n=1 时 E[W]= -γ_E；n=2 有解析值；序列单调递增。"""
    x1 = log_weibull_order_stat_means(1)
    assert abs(x1[0] - (-EULER_GAMMA)) < 1e-9

    x2 = log_weibull_order_stat_means(2)
    # E[W_(1:2)] = -log 2 - γ_E（最小值 = Exp(1/2) 的对数期望）
    assert abs(x2[0] - (-np.log(2.0) - EULER_GAMMA)) < 1e-9
    # E[W_(1:2)] + E[W_(2:2)] = 2·E[W] = -2γ_E
    assert abs(x2.sum() - (-2 * EULER_GAMMA)) < 1e-9

    x30 = log_weibull_order_stat_means(30)
    assert np.all(np.diff(x30) > 0)
    assert abs(x30.sum() - (-30 * EULER_GAMMA)) < 1e-6


def test_lse_reproduces_soman_example1():
    """Example 1：估计值落在论文 Table 1 峰值行附近。"""
    r = run_method("lse", SOMAN_EX1)
    assert r["method_id"] == "lse"
    assert r["converged"] is True
    # 论文峰值行：mu=502.1, c=1.603, b=39.26（White 数表舍入差 <1%）
    assert abs(r["gamma_hat"] - 502.1) < 0.5
    assert abs(r["beta_hat"] - 1.603) < 0.05
    assert abs(r["eta_hat"] - 39.26) < 0.4


def test_lse_reproduces_soman_example2():
    """Example 2：形状参数 0.8 的 MLE 失效区，估计值与论文峰值行一致。"""
    r = run_method("lse", SOMAN_EX2)
    assert r["converged"] is True
    # 论文峰值行：mu=99.9, c=0.8361, b=8.8521
    assert abs(r["gamma_hat"] - 99.9) < 0.5
    assert abs(r["beta_hat"] - 0.8361) < 0.08
    assert abs(r["eta_hat"] - 8.8521) < 0.4


def test_lse_f_profile_orders_match_paper_tables():
    """论文 Table 1/2 的 F 比排序与峰位在本实现的 F(μ) 上重现。"""
    # Table 1: F 在 496.6 → 502.1 递增，502.1 → 503.1 递减
    f1 = [_white_f_ratio(SOMAN_EX1, mu)[2]
          for mu in (496.6, 499.6, 501.1, 502.1, 502.7, 503.1)]
    assert f1[0] < f1[1] < f1[2] < f1[3]
    assert f1[3] > f1[4] > f1[5]

    # Table 2: F 峰在 99.9
    f2 = [_white_f_ratio(SOMAN_EX2, mu)[2]
          for mu in (99.8, 99.85, 99.9, 99.99, 100.0)]
    assert max(f2) == f2[2]

    # 同一 μ 处的 ĉ/b̂ 与论文列印值一致（表格舍入容差）
    c_at, b_at, _ = _white_f_ratio(SOMAN_EX1, 502.1)
    assert abs(c_at - 1.603) < 0.02
    assert abs(b_at - 39.26) < 0.4
    c_at2, b_at2, _ = _white_f_ratio(SOMAN_EX2, 99.9)
    assert abs(c_at2 - 0.8361) < 0.02
    assert abs(b_at2 - 8.8521) < 0.1


def test_lse_solution_matches_independent_regression():
    """返回参数满足论文式(6)：与测试内独立回归在同一 μ 处一致。"""
    r = run_method("lse", SOMAN_EX1)
    c_ind, b_ind, _ = _white_f_ratio(SOMAN_EX1, r["gamma_hat"])
    assert abs(r["beta_hat"] - c_ind) < 1e-9
    assert abs(r["eta_hat"] - b_ind) < 1e-9


def test_lse_recovers_parameters_in_low_shape_region():
    """论文适用区 0<c<3：合法参数网格上返回有限合法估计。"""
    rng = np.random.default_rng(5)
    for shape, scale, loc in [(1.7, 40.0, 500.0), (0.8, 10.0, 100.0), (2.5, 80.0, 10.0)]:
        sample = (loc + scale * rng.weibull(shape, 30)).tolist()
        r = run_method("lse", sample)
        assert r["converged"] is True
        assert np.isfinite(r["beta_hat"]) and r["beta_hat"] > 0
        assert np.isfinite(r["eta_hat"]) and r["eta_hat"] > 0
        assert 0.0 <= r["gamma_hat"] < min(sample)
        assert abs(r["beta_hat"] - shape) / shape < 0.6


def test_lse_insufficient_sample_fails_explicitly():
    """n < 3 无回归自由度：显式失败，无伪结果。"""
    r = run_method("lse", [10.0, 20.0])
    assert r["converged"] is False
    assert r["beta_hat"] is None
    assert r["extra"]["raw_status"] == "insufficient_sample"


def test_lse_degenerate_sample_fails_explicitly():
    """全等值样本无信息：显式失败 degenerate_sample。"""
    r = run_method("lse", [5.0] * 10)
    assert r["converged"] is False
    assert r["beta_hat"] is None
    assert r["extra"]["raw_status"] == "degenerate_sample"


def test_lse_identity_never_substituted():
    """run_method 返回身份必须是 lse 本身，且与 MLE/MDM 输出可区分。"""
    r = run_method("lse", SOMAN_EX2)
    assert r["method_id"] == "lse"
    assert r["method_variant"] == "lse"
    # c=0.8 区域 MLE 报 unbounded（Smith 1985），LSE 必须给出独立结果
    r_mle = run_method("mle", SOMAN_EX2)
    assert r_mle["converged"] is False
    assert r["converged"] is True
