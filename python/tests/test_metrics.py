"""
统一评价指标模块测试

覆盖审查要求的最小测试集：
- NE 在 gamma=0 时可计算
- beta_hat/eta_hat 非法为 failure
- gamma_hat 非有限为 failure
- converged=False 为 failure
- NE>1 为 outlier
- NE<=1 为 success
- 分位点公式正确
- 聚合时 failure/outlier 不进入精度均值但进入总分母
"""

import math
import sys
import pytest
from pathlib import Path

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from studies.common.metrics import (
    ne, quantile_true, quantile_est, nqe_R, re_R,
    check_status, aggregate_param_metrics,
)


# ============================================================
# NE 计算
# ============================================================

class TestNE:
    def test_basic(self):
        """NE 基本计算"""
        # 三参数误差均为 0 → NE = 0
        assert ne(2.0, 100.0, 10.0, 2.0, 100.0, 10.0) == 0.0

    def test_known_value(self):
        """NE 已知值验证"""
        # beta 误差 10%, eta 误差 5%, gamma 误差 1%（用 eta 归一化）
        result = ne(2.2, 105.0, 11.0, 2.0, 100.0, 10.0)
        expected = math.sqrt(0.01 + 0.0025 + 0.0001)  # 0.1^2 + 0.05^2 + 0.01^2
        assert abs(result - expected) < 1e-10

    def test_gamma_zero(self):
        """gamma=0 时 NE 可计算，不产生除零"""
        result = ne(2.0, 100.0, 5.0, 2.0, 100.0, 0.0)
        # gamma 误差 = (5-0)/100 = 0.05
        expected = math.sqrt(0 + 0 + 0.0025)
        assert abs(result - expected) < 1e-10
        assert math.isfinite(result)

    def test_gamma_uses_eta(self):
        """gamma 归一化使用 eta 而非 gamma"""
        # gamma=0, gamma_hat=10, eta=100 → gamma 项 = (10/100)^2 = 0.01
        result = ne(2.0, 100.0, 10.0, 2.0, 100.0, 0.0)
        expected = math.sqrt(0 + 0 + 0.01)
        assert abs(result - expected) < 1e-10


# ============================================================
# 分位点公式
# ============================================================

class TestQuantile:
    def test_quantile_true_basic(self):
        """真实分位点基本计算"""
        # beta=2, eta=100, gamma=0, R=0.9
        # x_R = 0 + 100 * (-ln(0.9))^(1/2)
        x_r = quantile_true(2.0, 100.0, 0.0, 0.9)
        expected = 100.0 * (-math.log(0.9)) ** 0.5
        assert abs(x_r - expected) < 1e-10

    def test_quantile_est_basic(self):
        """估计分位点基本计算"""
        x_hat_r = quantile_est(2.0, 100.0, 0.0, 0.9)
        x_r = quantile_true(2.0, 100.0, 0.0, 0.9)
        # 相同参数 → 估计值 = 真实值
        assert abs(x_hat_r - x_r) < 1e-10

    def test_nqe_R_zero_when_perfect(self):
        """参数完全正确时 NQE_R = 0"""
        assert nqe_R(2.0, 100.0, 10.0, 2.0, 100.0, 10.0, 0.9) == 0.0

    def test_re_R_zero_when_perfect(self):
        """参数完全正确时 RE_R = 0"""
        assert re_R(2.0, 100.0, 10.0, 2.0, 100.0, 10.0, 0.9) == 0.0

    def test_nqe_R_uses_eta(self):
        """NQE_R 用 eta 归一化"""
        # x̂_R - x_R = 5, eta = 100 → NQE = 0.05
        # 手动构造：beta 相同，gamma_hat 偏移 5
        R = 0.9
        x_r = quantile_true(2.0, 100.0, 0.0, R)
        x_hat_r = quantile_est(2.0, 100.0, 5.0, R)
        expected_nqe = abs(x_hat_r - x_r) / 100.0
        result = nqe_R(2.0, 100.0, 5.0, 2.0, 100.0, 0.0, R)
        assert abs(result - expected_nqe) < 1e-10

    def test_all_R_levels(self):
        """所有 R 水平都可计算"""
        for R in (0.995, 0.990, 0.950, 0.900):
            x_r = quantile_true(2.0, 100.0, 10.0, R)
            assert math.isfinite(x_r)
            assert x_r > 0


# ============================================================
# 状态判定
# ============================================================

class TestCheckStatus:
    def test_success(self):
        """正常估计 → success"""
        assert check_status(2.0, 100.0, 10.0, 2.0, 100.0, 10.0) == "success"

    def test_failure_beta_zero(self):
        """beta_hat = 0 → failure"""
        assert check_status(0.0, 100.0, 10.0, 2.0, 100.0, 10.0) == "failure"

    def test_failure_beta_negative(self):
        """beta_hat < 0 → failure"""
        assert check_status(-1.0, 100.0, 10.0, 2.0, 100.0, 10.0) == "failure"

    def test_failure_eta_zero(self):
        """eta_hat = 0 → failure"""
        assert check_status(2.0, 0.0, 10.0, 2.0, 100.0, 10.0) == "failure"

    def test_failure_eta_negative(self):
        """eta_hat < 0 → failure"""
        assert check_status(2.0, -50.0, 10.0, 2.0, 100.0, 10.0) == "failure"

    def test_failure_beta_nan(self):
        """beta_hat = NaN → failure"""
        assert check_status(float('nan'), 100.0, 10.0, 2.0, 100.0, 10.0) == "failure"

    def test_failure_beta_inf(self):
        """beta_hat = inf → failure"""
        assert check_status(float('inf'), 100.0, 10.0, 2.0, 100.0, 10.0) == "failure"

    def test_failure_gamma_nan(self):
        """gamma_hat = NaN → failure"""
        assert check_status(2.0, 100.0, float('nan'), 2.0, 100.0, 10.0) == "failure"

    def test_failure_gamma_inf(self):
        """gamma_hat = inf → failure"""
        assert check_status(2.0, 100.0, float('inf'), 2.0, 100.0, 10.0) == "failure"

    def test_gamma_negative_allowed(self):
        """gamma_hat 为负数但有限 → 不是 failure（gamma 可以为负）"""
        # gamma_hat = -5, 但 NE 可能很大
        status = check_status(2.0, 100.0, -5.0, 2.0, 100.0, 10.0)
        # 不是 failure，可能是 success 或 outlier 取决于 NE
        assert status in ("success", "outlier")

    def test_failure_converged_false(self):
        """converged=False → failure"""
        assert check_status(2.0, 100.0, 10.0, 2.0, 100.0, 10.0, converged=False) == "failure"

    def test_outlier(self):
        """NE > 1.0 → outlier"""
        # beta 误差 50%, eta 误差 50%, gamma 误差 50%/eta
        # NE = sqrt(0.25 + 0.25 + 0.25) = sqrt(0.75) ≈ 0.866 < 1.0 → success
        status = check_status(3.0, 150.0, 15.0, 2.0, 100.0, 10.0)
        ne_val = ne(3.0, 150.0, 15.0, 2.0, 100.0, 10.0)
        assert ne_val < 1.0
        assert status == "success"

        # 更大误差 → NE > 1.0 → outlier
        # beta_hat=10, eta=2, NE ≈ sqrt(16 + ...) > 1
        status2 = check_status(10.0, 150.0, 15.0, 2.0, 100.0, 10.0)
        ne_val2 = ne(10.0, 150.0, 15.0, 2.0, 100.0, 10.0)
        assert ne_val2 > 1.0
        assert status2 == "outlier"

    def test_outlier_threshold(self):
        """NE 恰好等于阈值 → success（> 才判 outlier）"""
        # 构造 NE = 1.0 的情况
        # 只有 beta 误差：((beta_hat - 2)/2)^2 = 1 → beta_hat = 4 或 0
        # beta_hat=4: NE = sqrt(1) = 1.0 → success（不是 >）
        status = check_status(4.0, 100.0, 10.0, 2.0, 100.0, 10.0)
        assert status == "success"

        # beta_hat=4.1: NE > 1.0 → outlier
        status2 = check_status(4.1, 100.0, 10.0, 2.0, 100.0, 10.0)
        assert status2 == "outlier"


# ============================================================
# 批量聚合
# ============================================================

class TestAggregate:
    def _make_result(self, beta_hat, eta_hat, gamma_hat,
                     beta=2.0, eta=100.0, gamma=10.0,
                     time=0.1, converged=True):
        return {
            "beta_hat": beta_hat, "eta_hat": eta_hat, "gamma_hat": gamma_hat,
            "beta": beta, "eta": eta, "gamma": gamma,
            "time": time, "converged": converged,
        }

    def test_empty(self):
        """空输入"""
        result = aggregate_param_metrics([])
        assert result["n_total"] == 0

    def test_three_states(self):
        """三态互斥：failure + outlier + success = total"""
        results = [
            self._make_result(2.0, 100.0, 10.0),      # success
            self._make_result(None, None, None),        # failure（None）
            self._make_result(10.0, 500.0, 100.0),     # outlier（大误差）
        ]
        agg = aggregate_param_metrics(results)
        assert agg["n_total"] == 3
        assert agg["n_success"] + agg["n_failure"] + agg["n_outlier"] == 3

    def test_failure_not_in_accuracy(self):
        """failure 样本不进入精度均值"""
        results = [
            self._make_result(2.0, 100.0, 10.0),      # success, NE=0
            self._make_result(None, None, None),        # failure
        ]
        agg = aggregate_param_metrics(results)
        assert agg["n_success"] == 1
        assert agg["ne_mean"] == 0.0  # failure 不影响精度

    def test_outlier_not_in_accuracy(self):
        """outlier 样本不进入精度均值"""
        results = [
            self._make_result(2.0, 100.0, 10.0),      # success, NE=0
            self._make_result(10.0, 500.0, 100.0),     # outlier
        ]
        agg = aggregate_param_metrics(results)
        assert agg["n_success"] == 1
        assert agg["ne_mean"] == 0.0  # outlier 不影响精度

    def test_failure_in_denominator(self):
        """failure 样本进入 failure_rate 分母"""
        results = [
            self._make_result(2.0, 100.0, 10.0),      # success
            self._make_result(None, None, None),        # failure
            self._make_result(None, None, None),        # failure
        ]
        agg = aggregate_param_metrics(results)
        assert agg["failure_rate"] == 2.0 / 3.0

    def test_all_failure(self):
        """全部 failure 时无精度指标"""
        results = [
            self._make_result(None, None, None),
            self._make_result(None, None, None),
        ]
        agg = aggregate_param_metrics(results)
        assert agg["n_success"] == 0
        assert "ne_mean" not in agg

    def test_quantile_metrics(self):
        """分位点指标存在且可计算"""
        results = [
            self._make_result(2.0, 100.0, 10.0),
            self._make_result(2.1, 105.0, 12.0),
        ]
        agg = aggregate_param_metrics(results)
        assert "quantile" in agg
        for R in (0.995, 0.990, 0.950, 0.900):
            assert R in agg["quantile"]
            q = agg["quantile"][R]
            assert "bias" in q
            assert "mae" in q
            assert "rmse" in q
            assert "nqe_mean" in q
            assert "nqe_std" in q
            assert "re_mean" in q

    def test_converged_false_is_failure(self):
        """converged=False 的样本归为 failure"""
        results = [
            self._make_result(2.0, 100.0, 10.0, converged=True),
            self._make_result(2.0, 100.0, 10.0, converged=False),
        ]
        agg = aggregate_param_metrics(results)
        assert agg["n_success"] == 1
        assert agg["n_failure"] == 1

    def test_time_metrics(self):
        """Time 指标仅统计 success 样本"""
        results = [
            self._make_result(2.0, 100.0, 10.0, time=0.1),
            self._make_result(2.0, 100.0, 10.0, time=0.3),
            self._make_result(None, None, None, time=999.0),  # failure，不计入
        ]
        agg = aggregate_param_metrics(results)
        assert abs(agg["time_mean"] - 0.2) < 1e-10

    def test_ne_threshold_passthrough(self):
        """ne_threshold 参数透传：低阈值让更多样本变为 outlier"""
        # NE ≈ 0.5 的样本：beta_hat 偏移约 25%
        results = [
            self._make_result(2.0, 100.0, 10.0),       # NE=0, success
            self._make_result(2.5, 100.0, 10.0),       # NE ≈ 0.25
        ]
        # 默认阈值 1.0：两个都是 success
        agg_default = aggregate_param_metrics(results)
        assert agg_default["n_success"] == 2
        assert agg_default["n_outlier"] == 0

        # 低阈值 0.1：第二个变为 outlier
        agg_strict = aggregate_param_metrics(results, ne_threshold=0.1)
        assert agg_strict["n_success"] == 1
        assert agg_strict["n_outlier"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
