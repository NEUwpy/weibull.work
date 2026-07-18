"""MDM 论文级验真测试

专项论文：谢里阳等 (2025), "基于统计最小差异原理的威布尔分布参数估计方法",
东北大学学报（自然科学版）1005-3026(2025)07-0108-06
（src/content/182-046-pdf原文.md）。

- 式(1)：三参数威布尔 CDF；
- 式(3)：精确中位秩 F̂(t_(i)) = i / (i + (n+1-i)·F_{2(n+1-i),2i,0.5})；
- 式(4)：尺度参数伪估计量 η̂_i = (t_(i)-γ) / (-ln(1-F̂))^{1/β}；
- 最小差异原理：正确 (γ, β) 使 n 个伪估计值的标准差最小；
- 式(6)：尺度参数取 n 个伪估计值的均值；
- §3：极值判据偏移 δ=0.1（把"梯度=0"改为"梯度=δ>0"）。

论文 §2 的理想样本：W(2.0, 1000, 1000)，n=7，样本值由式(3) 的
精确中位秩概率 {0.094, 0.228, 0.364, 0.500, 0.636, 0.772, 0.906} 反算。
"""

import sys
import os

import numpy as np
from scipy.special import betaincinv
from scipy.stats import f as f_dist

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from methods.mdm import MDM
from studies.common.runner import run_method
from studies.common.sample import generate_sample


def _ideal_sample(beta=2.0, eta=1000.0, gamma=1000.0, n=7):
    """按论文 §2 用精确中位秩反算理想样本。"""
    i = np.arange(1, n + 1)
    p = betaincinv(i, n - i + 1, 0.5)
    return gamma + eta * (-np.log(1 - p)) ** (1.0 / beta)


def test_exact_median_rank_equals_paper_f_distribution_formula():
    """式(3) 的 F 分布中位数形式与实现的 betaincinv 精确中位秩一致。"""
    n = 7
    i = np.arange(1, n + 1)
    f_median = f_dist.ppf(0.5, 2 * (n + 1 - i), 2 * i)
    paper_rank = i / (i + (n + 1 - i) * f_median)
    impl_rank = betaincinv(i, n - i + 1, 0.5)
    assert np.allclose(paper_rank, impl_rank, atol=1e-9)
    # 论文正文给出的 3 位小数概率
    assert np.allclose(np.round(impl_rank, 3),
                       [0.094, 0.228, 0.364, 0.500, 0.636, 0.772, 0.906],
                       atol=5e-4)


def test_mdm_ideal_sample_with_exact_ranks_recovers_true_parameters():
    """理想样本 + 式(3) 精确中位秩：伪估计量差异为零的点就是真值。

    论文 §1.1（图1）：理想样本在正确 (β, γ) 下各伪尺度估计值全部等于
    真实 η。因此最小差异搜索应精确还原 W(2, 1000, 1000)。
    """
    sample = _ideal_sample()
    mdm = MDM(sample.tolist())
    beta, eta, gamma, r2, status = mdm.run(offset=0.1, rank_method="exact")

    assert status is True
    assert abs(beta - 2.0) < 1e-3
    assert abs(eta - 1000.0) < 0.1
    assert abs(gamma - 1000.0) < 0.1

    # 偏移=0（原始极值判据）在理想样本上同样应还原真值（论文 §3）
    mdm0 = MDM(sample.tolist())
    beta0, eta0, gamma0, _, status0 = mdm0.run(offset=0.0, rank_method="exact")
    assert status0 is True
    assert abs(beta0 - 2.0) < 1e-3
    assert abs(gamma0 - 1000.0) < 0.1


def test_mdm_default_bernard_ranks_stay_close_to_paper_exact_ranks():
    """工程默认 Bernard 近似与论文精确秩在理想样本上的偏差应远小于论文自身网格噪声（990~1025）。"""
    sample = _ideal_sample()
    beta, eta, gamma, r2, status = MDM(sample.tolist()).run(offset=0.1)

    assert status is True
    assert abs(beta - 2.0) < 0.05
    assert abs(eta - 1000.0) < 15.0
    assert abs(gamma - 1000.0) < 15.0


def test_mdm_scale_estimate_is_mean_of_pseudo_estimates():
    """式(6)：返回的 η̂ 等于 n 个伪估计量 (式4) 的均值（独立复算）。"""
    sample = generate_sample(2.0, 100.0, 5.0, 30, 0)
    mdm = MDM(sample)
    beta, eta, gamma, r2, status = mdm.run(offset=0.1)

    assert status is True
    arr = np.sort(np.asarray(sample, dtype=float))
    n = len(arr)
    i = np.arange(1, n + 1)
    bernard = (i - 0.3) / (n + 0.4)
    pseudo = (arr - gamma) / (-np.log(1 - bernard)) ** (1.0 / beta)
    assert abs(eta - pseudo.mean()) < 1e-9


def test_mdm_offset_shifts_location_estimate_upward():
    """论文 §3：偏移判据 (δ=0.1) 的根位于零判据根的右侧（γ 更大）。"""
    sample = generate_sample(2.0, 100.0, 5.0, 30, 0)
    _, _, gamma_zero, _, s0 = MDM(sample).run(offset=0.0)
    _, _, gamma_offset, _, s1 = MDM(sample).run(offset=0.1)

    assert s0 is True and s1 is True
    assert gamma_offset >= gamma_zero - 1e-9


def test_mdm_identity_and_diagnostics_via_runner():
    """run_method 身份为 mdm，附带论文判据的求解诊断。"""
    sample = generate_sample(2.0, 100.0, 5.0, 30, 0)
    r = run_method("mdm", sample, offset=0.1)

    assert r["method_id"] == "mdm"
    assert r["method_variant"] == "mdm"
    assert r["converged"] is True
    info = r["extra"]["solution_info"]
    assert info["target_offset"] == 0.1
    assert info["constraint"] == "gamma >= 0"
    assert 0.0 <= r["gamma_hat"] < min(sample)
