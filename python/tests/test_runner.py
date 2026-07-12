"""runner.py 测试：方法调用、返回格式、异常处理、method_variant"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample
from studies.common.runner import run_method


# 使用固定样本，避免随机性
FIXED_SAMPLE = generate_sample(2.0, 100.0, 5.0, 30, 0)


def test_mle_returns_valid():
    """MLE 返回有效估计值"""
    r = run_method("mle", FIXED_SAMPLE)
    assert r["method_id"] == "mle"
    assert r["converged"] is True
    assert r["beta_hat"] is not None
    assert r["eta_hat"] is not None
    assert r["gamma_hat"] is not None
    assert r["time"] > 0


def test_mdm_returns_valid():
    """MDM 返回有效估计值（需要 offset 参数）"""
    r = run_method("mdm", FIXED_SAMPLE, offset=0.1)
    assert r["method_id"] == "mdm"
    assert r["converged"] is True
    assert r["beta_hat"] is not None
    assert r["eta_hat"] is not None
    assert r["gamma_hat"] is not None


def test_mdm_with_offset():
    """MDM 传入 offset 参数"""
    r = run_method("mdm", FIXED_SAMPLE, offset=0.5)
    assert r["converged"] is True
    assert r["beta_hat"] is not None


def test_lre_returns_valid():
    """LRE 返回有效估计值"""
    r = run_method("lre", FIXED_SAMPLE)
    assert r["method_id"] == "lre"
    assert r["converged"] is True
    assert r["beta_hat"] is not None
    assert r["eta_hat"] is not None
    assert r["gamma_hat"] is not None


def test_trace_kwarg_is_ignored_when_method_does_not_accept_it():
    """统一调用器可接收 API 传来的 trace，并兼容不支持 trace 的方法。"""
    r = run_method("lre", FIXED_SAMPLE, trace=True)
    assert r["converged"] is True
    assert r["extra"] is None
    assert r["beta_hat"] is not None


def test_trace_data_returned_when_method_records_it():
    """统一调用器在 trace=True 时返回算法记录的追踪数据。"""
    r = run_method("mdm", FIXED_SAMPLE, trace=True, offset=0.1, gamma_steps=20)
    assert r["converged"] is True
    assert r["trace_data"] is not None
    assert r["trace_data"]["target_offset"] == 0.1


def test_variant_defaults_to_method_id():
    """不指定 variant 时默认为 method_id"""
    r = run_method("mle", FIXED_SAMPLE)
    assert r["method_variant"] == "mle"


def test_variant_custom():
    """可以指定自定义 variant"""
    r = run_method("mdm", FIXED_SAMPLE, variant="mdm_offset0.5", offset=0.5)
    assert r["method_variant"] == "mdm_offset0.5"


def test_invalid_method_returns_failure():
    """不存在的方法返回 failure 结构"""
    r = run_method("nonexistent_method_xyz", FIXED_SAMPLE)
    assert r["converged"] is False
    assert r["beta_hat"] is None
    assert r["method_variant"] == "nonexistent_method_xyz"


def test_mdm_no_offset_captures_error():
    """MDM 不传 offset 时 extra 包含错误信息"""
    r = run_method("mdm", FIXED_SAMPLE)
    assert r["converged"] is False
    assert r["extra"] is not None
    assert "error" in r["extra"]


def test_invalid_method_captures_error():
    """不存在的方法 extra 包含 resolve_method 错误"""
    r = run_method("nonexistent_method_xyz", FIXED_SAMPLE)
    assert r["extra"] is not None
    assert "error" in r["extra"]


def test_result_dict_keys():
    """结果字典包含所有必要字段"""
    r = run_method("mle", FIXED_SAMPLE)
    expected_keys = {
        "method_id", "method_variant",
        "beta_hat", "eta_hat", "gamma_hat",
        "r_squared", "converged", "time", "extra",
    }
    assert set(r.keys()) == expected_keys


def test_r_squared_range():
    """R² 在合理范围内"""
    r = run_method("mle", FIXED_SAMPLE)
    if r["r_squared"] is not None:
        assert 0 <= r["r_squared"] <= 1.01  # 允许微小浮点误差


def test_degenerate_sample_fails_before_method_solver_can_silently_succeed():
    r = run_method("wmle", [10.0] * 10)
    assert r["converged"] is False
    assert r["beta_hat"] is None
    assert r["extra"] == {"error": "invalid sample: observations must not all be equal"}
