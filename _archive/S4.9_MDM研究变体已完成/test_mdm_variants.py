"""MDM 变体测试：四种 MDM 实现的行为验证"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from methods.mdm_variants import (
    mdm_offset_strict,
    mdm_offset_constrained,
    mdm_min_sigma,
    mdm_allow_negative_gamma,
)


# 固定样本：成功 case（gamma=5, eta=100, n=30）
SAMPLE_SUCCESS = generate_sample(2.0, 100.0, 5.0, 30, 0)
# 固定样本：failure case（gamma=0, n=10, beta=1.5, rid=1 — 已知为 no_intersection）
SAMPLE_FAILURE = generate_sample(1.5, 100.0, 0.0, 10, 1)


class TestMdmOffsetStrict:
    """mdm_offset_strict：与原 MDM 行为一致，无交点返回 None。"""

    def test_success_case(self):
        """有交点时返回有效估计值"""
        r = mdm_offset_strict(SAMPLE_SUCCESS, offset=0.1, gamma_steps=20)
        assert r[0] is not None
        assert r[1] is not None
        assert r[2] is not None
        assert r[0] > 0  # beta > 0
        assert r[1] > 0  # eta > 0

    def test_failure_case_returns_none(self):
        """无交点时返回 (None, None, None)"""
        r = mdm_offset_strict(SAMPLE_FAILURE, offset=0.1, gamma_steps=20)
        assert r[0] is None
        assert r[1] is None
        assert r[2] is None


class TestMdmOffsetConstrained:
    """mdm_offset_constrained：永不返回 None。"""

    def test_success_case(self):
        """有交点时返回有效估计值（与 strict 一致）"""
        r = mdm_offset_constrained(SAMPLE_SUCCESS, offset=0.1, gamma_steps=20)
        assert r[0] is not None
        assert r[1] is not None
        assert r[2] is not None
        assert r[0] > 0

    def test_failure_case_returns_boundary(self):
        """无交点时返回约束域边界解（不返回 None）"""
        r = mdm_offset_constrained(SAMPLE_FAILURE, offset=0.1, gamma_steps=20)
        assert r[0] is not None, "constrained 不应返回 None"
        assert r[1] is not None
        assert r[2] is not None
        assert r[0] > 0
        assert r[1] > 0

    def test_constrained_matches_strict_on_success(self):
        """成功 case 下 constrained 和 strict 结果一致"""
        s = mdm_offset_strict(SAMPLE_SUCCESS, offset=0.1, gamma_steps=20)
        c = mdm_offset_constrained(SAMPLE_SUCCESS, offset=0.1, gamma_steps=20)
        assert abs(s[0] - c[0]) < 1e-10
        assert abs(s[1] - c[1]) < 1e-10
        assert abs(s[2] - c[2]) < 1e-10

    def test_constrained_never_returns_none(self):
        """在已知 failure 样本上批量验证：constrained 永不返回 None"""
        failure_cases = [
            (1.5, 100.0, 0.0, 10, 1),
            (1.5, 100.0, 0.0, 10, 6),
            (2.0, 100.0, 0.0, 30, 2),
            (3.0, 100.0, 0.0, 10, 0),
        ]
        for beta, eta, gamma, n, rid in failure_cases:
            sample = generate_sample(beta, eta, gamma, n, rid)
            r = mdm_offset_constrained(sample, offset=0.1, gamma_steps=20)
            assert r[0] is not None, f"failure on ({beta},{eta},{gamma},{n},{rid})"
            assert r[1] is not None
            assert r[2] is not None


class TestMdmMinSigma:
    """mdm_min_sigma：始终返回最小 sigma 处的解。"""

    def test_returns_valid(self):
        """始终返回有效估计值"""
        r = mdm_min_sigma(SAMPLE_SUCCESS, offset=0.1, gamma_steps=20)
        assert r[0] is not None
        assert r[1] is not None
        assert r[2] is not None
        assert r[0] > 0
        assert r[1] > 0

    def test_failure_case_also_returns(self):
        """failure 样本也返回有效值"""
        r = mdm_min_sigma(SAMPLE_FAILURE, offset=0.1, gamma_steps=20)
        assert r[0] is not None
        assert r[1] is not None
        assert r[2] is not None

    def test_gamma_in_valid_range(self):
        """gamma 在 [0, t_min) 范围内"""
        import numpy as np
        wb_data = np.sort(SAMPLE_FAILURE)
        t_min = wb_data[0]
        r = mdm_min_sigma(SAMPLE_FAILURE, offset=0.1, gamma_steps=20)
        assert 0 <= r[2] < t_min


class TestMdmAllowNegativeGamma:
    """mdm_allow_negative_gamma：允许负 gamma，仅诊断用。"""

    def test_success_case(self):
        """成功 case 正常返回"""
        r = mdm_allow_negative_gamma(SAMPLE_SUCCESS, offset=0.1, gamma_steps=20)
        assert r[0] is not None

    def test_failure_case_may_recover(self):
        """failure 样本可能通过负 gamma 恢复（也可能仍无交点）"""
        r = mdm_allow_negative_gamma(SAMPLE_FAILURE, offset=0.1, gamma_steps=20)
        # 不保证一定有结果，但 gamma 如果有值应为负
        if r[0] is not None:
            assert r[2] < 0, "恢复的 gamma 应为负值"


class TestRunnerIntegration:
    """通过 runner.run_method 调用 MDM 变体。"""

    def test_strict_via_runner(self):
        """mdm_offset_strict 通过 runner 调用"""
        r = run_method("mdm_offset_strict", SAMPLE_SUCCESS, offset=0.1)
        assert r["method_id"] == "mdm"
        assert r["method_variant"] == "mdm_offset_strict"
        assert r["converged"] is True
        assert r["beta_hat"] is not None

    def test_constrained_via_runner(self):
        """mdm_offset_constrained 通过 runner 调用"""
        r = run_method("mdm_offset_constrained", SAMPLE_FAILURE, offset=0.1)
        assert r["method_id"] == "mdm"
        assert r["method_variant"] == "mdm_offset_constrained"
        assert r["converged"] is True
        assert r["beta_hat"] is not None

    def test_min_sigma_via_runner(self):
        """mdm_min_sigma 通过 runner 调用"""
        r = run_method("mdm_min_sigma", SAMPLE_FAILURE, offset=0.1)
        assert r["method_id"] == "mdm"
        assert r["method_variant"] == "mdm_min_sigma"
        assert r["converged"] is True
        assert r["beta_hat"] is not None

    def test_negative_gamma_via_runner(self):
        """mdm_allow_negative_gamma 通过 runner 调用"""
        r = run_method("mdm_allow_negative_gamma", SAMPLE_SUCCESS, offset=0.1)
        assert r["method_id"] == "mdm"
        assert r["method_variant"] == "mdm_allow_negative_gamma"
        assert r["converged"] is True

    def test_strict_failure_via_runner(self):
        """mdm_offset_strict failure case 通过 runner 返回 converged=False"""
        r = run_method("mdm_offset_strict", SAMPLE_FAILURE, offset=0.1)
        assert r["converged"] is False
        assert r["beta_hat"] is None

    def test_constrained_failure_via_runner(self):
        """mdm_offset_constrained failure case 通过 runner 返回 converged=True"""
        r = run_method("mdm_offset_constrained", SAMPLE_FAILURE, offset=0.1)
        assert r["converged"] is True
        assert r["beta_hat"] is not None

    def test_variant_auto_from_method_id(self):
        """variant 未指定时，若 method_id 是变体名则自动识别"""
        r = run_method("mdm_offset_constrained", SAMPLE_SUCCESS)
        assert r["method_variant"] == "mdm_offset_constrained"
        assert r["converged"] is True

    def test_original_mdm_still_works(self):
        """原始 MDM 通过 registry 调用不受影响"""
        r = run_method("mdm", SAMPLE_SUCCESS, offset=0.1)
        assert r["method_id"] == "mdm"
        assert r["method_variant"] == "mdm"
        assert r["converged"] is True

    def test_variant_time_recorded(self):
        """变体函数的运行时间被正确记录"""
        r = run_method("mdm_offset_constrained", SAMPLE_SUCCESS, offset=0.1)
        assert r["time"] > 0
