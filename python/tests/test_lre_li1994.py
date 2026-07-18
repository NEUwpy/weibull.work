r"""LRE 论文级验真测试

主锚：Li (1994), "A General Linear-Regression Analysis Applied to the
3-Parameter Weibull Distribution", IEEE Trans. Reliability 43(4)
（src/content/182-107-pdf原文.md）。

- 式(2-4)：$y_1 = a_1 + b_1 x_1(\gamma)$，其中 $y_1=\ln(-\ln R)$, $x_1=\ln(t-\gamma)$,
  $a_1 = -\beta\ln\alpha$, $b_1 = \beta$；
- Li §4 近似分析法 (4a)：对 γ 搜索使 $x_1\sim y_1$ 的相关系数最大的点；
- Park (2017/2018) 进一步将此思想系统化并证明位置估计存在性
  （src/content/182-106-pdf原文.md，位置参数边界）。

本实现的 LRE 遵循 Li (1994) §4：相关系数最大化确定 γ，OLS 一次给出全部三参数。
与 Park (2017) 的不同：Park 在确定 γ 后用 **2P MLE** 求 β 和 η；LRE 用 **OLS**。
"""

import sys
import os

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from methods.lre import LRE
from studies.common.runner import run_method
from studies.common.sample import generate_sample


FIXED_SAMPLE = generate_sample(2.0, 100.0, 5.0, 30, 0)


def _independent_lre(data):
    """独立实现 Li (1994) §4：网格最大化 corr² + OLS，不复述被测代码。"""
    t = np.sort(np.asarray(data, dtype=float))
    n = len(t)
    F = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    v = np.log(-np.log(1 - F))
    t_min = t[0]
    g_grid = np.linspace(0, t_min * 0.99, 100)
    best_g = None
    best_rho2 = -1.0
    for g in g_grid:
        with np.errstate(divide="ignore", invalid="ignore"):
            u = np.log(t - g)
        mask = np.isfinite(u)
        if mask.sum() < 3:
            continue
        corr = np.corrcoef(u[mask], v[mask])[0, 1]
        rho2 = corr ** 2
        if rho2 > best_rho2:
            best_rho2 = rho2
            best_g = g
    u_star = np.log(t - best_g)
    slope = np.sum((u_star - u_star.mean()) * (v - v.mean())) / np.sum(
        (u_star - u_star.mean()) ** 2
    )
    intercept = v.mean() - slope * u_star.mean()
    eta = np.exp(-intercept / slope)
    return slope, eta, best_g, best_rho2


def test_lre_correlation_matches_independent_grid():
    """LRE 返回的 γ 使 corr² 达到独立网格搜索确定的峰值。"""
    r = run_method("lre", FIXED_SAMPLE)
    assert r["converged"] is True
    slope_i, eta_i, gamma_i, rho2_i = _independent_lre(FIXED_SAMPLE)
    # 独立网格与 L-BFGS-B 在同一样本上的最优 γ 应接近
    assert abs(r["gamma_hat"] - gamma_i) < 0.5
    assert abs(r["beta_hat"] - slope_i) < 0.05
    assert abs(r["eta_hat"] - eta_i) / eta_i < 0.05


def test_lre_regression_coefficients_match_ols():
    """LRE 返回的 β, η 与最优 γ 下手动 OLS 一致。"""
    r = run_method("lre", FIXED_SAMPLE)
    t = np.sort(np.asarray(FIXED_SAMPLE, dtype=float))
    n = len(t)
    F = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    v = np.log(-np.log(1 - F))
    u = np.log(t - r["gamma_hat"])
    slope = np.sum((u - u.mean()) * (v - v.mean())) / np.sum(
        (u - u.mean()) ** 2
    )
    intercept = v.mean() - slope * u.mean()
    eta_ols = np.exp(-intercept / slope)
    assert abs(r["beta_hat"] - slope) < 1e-9
    assert abs(r["eta_hat"] - eta_ols) < 1e-9


def test_lre_r_squared_matches_explained_variance():
    """LRE 返回的 r_squared 与 OLS 的 R² 一致（在最优 γ 处）。"""
    r = run_method("lre", FIXED_SAMPLE)
    t = np.sort(np.asarray(FIXED_SAMPLE, dtype=float))
    n = len(t)
    F = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
    v = np.log(-np.log(1 - F))
    u = np.log(t - r["gamma_hat"])
    z = np.polyfit(u, v, 1)
    ss_res = np.sum((v - (z[0] * u + z[1])) ** 2)
    ss_tot = np.sum((v - v.mean()) ** 2)
    r2_ols = 1 - ss_res / ss_tot
    assert abs(r["r_squared"] - r2_ols) < 1e-9


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
    assert r["extra"] is None
