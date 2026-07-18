"""MLE 论文级验真测试

主锚论文：Hirose (1996), "Maximum Likelihood Estimation in the 3-parameter
Weibull Distribution: A Look through the Generalized Extreme-value
Distribution", IEEE TDEI（src/content/182-105-pdf原文.md）。

- Table 1 提供环氧树脂击穿电压 5 组各 20 点样本；
- Table 2 给出 W3P 的 MLE 基准（case 2/3/5 与 100 点合并样本）；
- 第 5.3 节给出 case 4 的 W2P（gamma=0）MLE 基准；
- case 1/4 为参数发散样本（beta->inf, gamma->-inf），
  平台以工程约束 0 <= gamma < t_(1) 收敛到 gamma=0 边界的 W2P 解。

非正则边界：Smith (1985)（src/content/182-090-pdf原文.md）——
beta < 1 时不存在（局部极大意义下的）MLE，实现必须显式报 "unbounded"。
"""

import sys
import os

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.runner import run_method
from studies.common.sample import generate_sample

# Hirose (1996) Table 1: Dielectric Breakdown Voltage Data of Epoxy Resin
HIROSE_CASE1 = [24.54, 28.00, 25.69, 27.72, 28.05, 27.53, 27.34, 26.80, 26.51, 27.28,
                28.16, 28.86, 26.67, 28.37, 28.37, 28.44, 28.05, 24.61, 27.54, 26.85]
HIROSE_CASE2 = [27.15, 29.13, 28.28, 27.74, 28.87, 26.42, 24.46, 30.88, 29.11, 27.31,
                27.54, 27.98, 28.49, 26.25, 28.50, 25.61, 29.50, 28.04, 27.94, 26.66]
HIROSE_CASE3 = [27.66, 26.54, 26.96, 26.15, 25.26, 29.44, 28.32, 27.66, 28.21, 27.80,
                27.59, 26.63, 28.08, 28.83, 27.96, 28.13, 29.06, 26.78, 28.00, 26.28]
HIROSE_CASE4 = [27.98, 27.49, 27.85, 27.93, 24.19, 25.01, 27.06, 27.62, 28.94, 29.09,
                27.63, 28.28, 27.63, 28.20, 27.95, 28.33, 27.11, 26.47, 28.17, 27.35]
HIROSE_CASE5 = [28.04, 28.57, 26.33, 29.61, 28.17, 27.14, 29.17, 25.44, 28.49, 27.46,
                27.31, 26.95, 27.88, 27.30, 29.02, 29.52, 26.89, 27.89, 28.08, 27.75]

# Hirose (1996) Table 2: W3P MLE 基准 (beta, eta, gamma, logL)
HIROSE_TABLE2 = {
    "case2": (HIROSE_CASE2, 4.529, 6.239, 22.092, -35.375),
    "case3": (HIROSE_CASE3, 5.267, 5.051, 22.921, -28.652),
    "case5": (HIROSE_CASE5, 4.811, 4.725, 23.523, -28.824),
}


def _log_likelihood(beta, eta, gamma, data):
    """独立实现的三参数威布尔对数似然（Hirose 1996 式(1) 对应的 PDF）。"""
    arr = np.array(sorted(data), dtype=float)
    z = (arr - gamma) / eta
    n = len(arr)
    return (n * np.log(beta) - n * np.log(eta)
            + (beta - 1) * np.sum(np.log(z)) - np.sum(z ** beta))


def test_mle_reproduces_hirose_table2_benchmarks():
    """W3P MLE 复现 Hirose Table 2 的 case 2/3/5（论文精度 3 位小数）。"""
    for name, (data, beta_p, eta_p, gamma_p, ll_p) in HIROSE_TABLE2.items():
        r = run_method("mle", data)
        assert r["method_id"] == "mle", name
        assert r["converged"] is True, name
        assert abs(r["beta_hat"] - beta_p) < 0.01, name
        assert abs(r["eta_hat"] - eta_p) < 0.01, name
        assert abs(r["gamma_hat"] - gamma_p) < 0.01, name
        ll_ours = _log_likelihood(r["beta_hat"], r["eta_hat"], r["gamma_hat"], data)
        assert abs(ll_ours - ll_p) < 0.01, name


def test_mle_reproduces_hirose_100_sample_benchmark():
    """100 点合并样本复现 Table 2 'altogether' 列。"""
    data = HIROSE_CASE1 + HIROSE_CASE2 + HIROSE_CASE3 + HIROSE_CASE4 + HIROSE_CASE5
    r = run_method("mle", data)
    assert r["converged"] is True
    assert abs(r["beta_hat"] - 6.560) < 0.01
    assert abs(r["eta_hat"] - 7.158) < 0.01
    assert abs(r["gamma_hat"] - 20.916) < 0.01
    ll_ours = _log_likelihood(r["beta_hat"], r["eta_hat"], r["gamma_hat"], data)
    assert abs(ll_ours - (-157.073)) < 0.01


def test_mle_diverging_case_converges_to_w2p_boundary():
    """Hirose case 4 参数发散（beta->inf, gamma->-inf）；

    平台工程约束 gamma >= 0 下应收敛到 gamma=0 边界，
    即论文第 5.3 节给出的 W2P MLE（eta=27.984, beta=34.519, logL=-27.770）。
    """
    r = run_method("mle", HIROSE_CASE4)
    assert r["converged"] is True
    assert r["gamma_hat"] == 0.0
    assert abs(r["beta_hat"] - 34.519) < 0.01
    assert abs(r["eta_hat"] - 27.984) < 0.01
    ll_ours = _log_likelihood(r["beta_hat"], r["eta_hat"], r["gamma_hat"], HIROSE_CASE4)
    assert abs(ll_ours - (-27.770)) < 0.01


def test_mle_rejects_beta_below_one_as_unbounded():
    """Smith (1985)：beta < 1 时 MLE 不存在；实现必须报 unbounded 而非伪结果。"""
    rng = np.random.default_rng(0)
    data = (rng.weibull(0.6, 30) * 50.0).tolist()

    r = run_method("mle", data)

    assert r["converged"] is False
    assert r["extra"] == {"raw_status": "unbounded"}
    assert r["beta_hat"] is None
    assert r["eta_hat"] is None
    assert r["gamma_hat"] is None


def test_mle_gamma_estimate_stays_inside_support():
    """gamma 估计必须满足 0 <= gamma < t_(1)（似然支撑与平台约束）。"""
    for beta, eta, gamma, n, rep in [(1.5, 100.0, 5.0, 50, 0),
                                     (2.5, 80.0, 10.0, 100, 1),
                                     (4.0, 60.0, 0.0, 50, 2)]:
        sample = generate_sample(beta, eta, gamma, n, rep)
        r = run_method("mle", sample)
        assert r["converged"] is True
        assert r["beta_hat"] > 0
        assert r["eta_hat"] > 0
        assert 0.0 <= r["gamma_hat"] < min(sample)
        assert np.isfinite(r["beta_hat"])
        assert np.isfinite(r["eta_hat"])
        assert np.isfinite(r["gamma_hat"])


def test_mle_identity_never_substituted():
    """run_method 返回的身份必须是 mle 本身。"""
    r = run_method("mle", HIROSE_CASE2)
    assert r["method_id"] == "mle"
    assert r["method_variant"] == "mle"
