"""test_calculation_api.py — 方法失败时不回退到 WMLE，且响应保持方法身份一致"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from fastapi import HTTPException


class _FakeModule:
    pass


def _build_torch_mocks():
    nn = type(sys)("torch.nn")
    nn.Module = _FakeModule
    nn.Linear = _FakeModule
    nn.ReLU = _FakeModule
    nn.BatchNorm1d = _FakeModule
    nn.Sequential = _FakeModule
    nn.Sigmoid = _FakeModule

    torch = type(sys)("torch")
    torch.nn = nn
    torch.load = lambda *args, **kwargs: {}
    torch.FloatTensor = lambda x: x
    torch.no_grad = _FakeModule()
    return torch, nn


@pytest.fixture(scope="session", autouse=True)
def _isolated_torch_mock():
    saved = {}
    for key in ("torch", "torch.nn"):
        saved[key] = sys.modules.get(key, None)

    torch, nn = _build_torch_mocks()
    sys.modules["torch"] = torch
    sys.modules["torch.nn"] = nn
    sys.modules.pop("torch.nn.modules", None)  # 防止旧缓存的子模块干扰

    yield

    for key, original in saved.items():
        if original is None:
            sys.modules.pop(key, None)
        else:
            sys.modules[key] = original


@pytest.fixture
def helpers():
    import main  # noqa: E402  — main 在 mock 环境下解析一次，受益于 fixture 的导入缓存

    return main


def test_failed_selected_method_raises_422_and_never_calls_wmle(helpers, monkeypatch):
    """所选方法失败时抛出 422，不调用 WMLE。"""
    calls = []

    def fake_run_method(method_id, data, **kwargs):
        calls.append(method_id)
        return {
            "method_id": method_id,
            "method_variant": method_id,
            "beta_hat": None,
            "eta_hat": None,
            "gamma_hat": None,
            "r_squared": None,
            "converged": False,
            "time": 0.0,
            "extra": {"error": "NotImplementedError: "},
        }

    monkeypatch.setattr(helpers, "run_method", fake_run_method)

    with pytest.raises(HTTPException) as exc:
        helpers._run_calculation_method("mle", [1, 2, 3, 4, 5])

    assert exc.value.status_code == 422
    assert "mle" in exc.value.detail
    assert calls == ["mle"]


def test_successful_method_preserves_identity(helpers, monkeypatch):
    """成功的方法调用返回正确的 method 身份。"""
    def fake_run_method(method_id, data, **kwargs):
        return {
            "method_id": method_id,
            "method_variant": method_id,
            "beta_hat": 2.5,
            "eta_hat": 100.0,
            "gamma_hat": 5.0,
            "r_squared": 0.98,
            "converged": True,
            "time": 0.01,
            "extra": {},
        }

    monkeypatch.setattr(helpers, "run_method", fake_run_method)

    response = helpers._run_calculation_method("mdm", [1, 2, 3, 4, 5], offset=0.1)
    assert response["method"] == "mdm"
    assert response["beta"] == 2.5
    assert response["converged"] is True


def test_custom_mdm_offset_is_forwarded(helpers, monkeypatch):
    """自定义 MDM 偏移量必须原样传入统一方法调用。"""
    captured = {}

    def fake_run_method(method_id, data, **kwargs):
        captured.update(kwargs)
        return {
            "method_id": method_id,
            "method_variant": method_id,
            "beta_hat": 2.0,
            "eta_hat": 1000.0,
            "gamma_hat": 1000.0,
            "r_squared": 0.99,
            "converged": True,
            "time": 0.01,
            "extra": {},
        }

    monkeypatch.setattr(helpers, "run_method", fake_run_method)

    helpers._run_calculation_method("mdm", [1, 2, 3, 4, 5], offset=0.24)

    assert captured["offset"] == pytest.approx(0.24)


@pytest.mark.parametrize("offset", [-0.02, 0.52, float("nan"), float("inf")])
def test_invalid_mdm_offset_is_rejected(helpers, offset):
    """计算入口拒绝非有限值和超出计算器范围的偏移量。"""
    with pytest.raises(ValueError, match="MDM offset"):
        helpers._calculation_kwargs("mdm", offset=offset)


def test_failure_422_detail_includes_requested_method(helpers, monkeypatch):
    """HTTP 422 的 detail 中包含被请求的方法 ID。"""
    def fake_run_method(method_id, data, **kwargs):
        return {
            "method_id": method_id,
            "method_variant": method_id,
            "beta_hat": None,
            "eta_hat": None,
            "gamma_hat": None,
            "r_squared": None,
            "converged": False,
            "time": 0.0,
            "extra": {"error": "ValueError: optimization failed"},
        }

    monkeypatch.setattr(helpers, "run_method", fake_run_method)

    with pytest.raises(HTTPException) as exc:
        helpers._run_calculation_method("mmle", [1, 2, 3, 4, 5])

    assert exc.value.status_code == 422
    assert "mmle" in exc.value.detail


def test_wmle_not_invoked_on_any_failure(helpers, monkeypatch):
    """验证失败路径上的 WMLE 调用计数始终为 0。"""
    wmle_calls = []

    def fake_run_method(method_id, data, **kwargs):
        if method_id == "wmle":
            wmle_calls.append(1)
        return {
            "method_id": method_id,
            "method_variant": method_id,
            "beta_hat": None,
            "eta_hat": None,
            "gamma_hat": None,
            "r_squared": None,
            "converged": False,
            "time": 0.0,
            "extra": {},
        }

    monkeypatch.setattr(helpers, "run_method", fake_run_method)

    with pytest.raises(HTTPException):
        helpers._run_calculation_method("lre", [1, 2, 3, 4, 5])

    assert wmle_calls == []


# Hirose (1996) Table 1 case 2（src/content/182-105-pdf原文.md），
# Table 2 基准：beta=4.529, eta=6.239, gamma=22.092。
_HIROSE_CASE2 = [27.15, 29.13, 28.28, 27.74, 28.87, 26.42, 24.46, 30.88, 29.11, 27.31,
                 27.54, 27.98, 28.49, 26.25, 28.50, 25.61, 29.50, 28.04, 27.94, 26.66]


def test_calculate_api_runs_real_mle_with_identity(helpers):
    """真实后端路径：/calculate 的 MLE 调用返回 mle 身份和论文基准参数。"""
    response = helpers._run_calculation_method("mle", _HIROSE_CASE2)

    assert response["method"] == "mle"
    assert response["converged"] is True
    assert abs(response["beta"] - 4.529) < 0.01
    assert abs(response["eta"] - 6.239) < 0.01
    assert abs(response["gamma"] - 22.092) < 0.01


# Cousineau (2009) §4 数值例（src/content/182-088-pdf原文.md），
# WMLE 基准：shape=2.29, scale=116.0, location=283.7。
_COUSINEAU_X = [310, 342, 353, 365, 383, 393, 403, 412, 451, 456]


def test_calculate_api_runs_real_wmle_with_identity(helpers):
    """真实后端路径：/calculate 的 WMLE 调用返回 wmle 身份和论文基准参数。"""
    response = helpers._run_calculation_method("wmle", _COUSINEAU_X)

    assert response["method"] == "wmle"
    assert response["converged"] is True
    assert abs(response["beta"] - 2.29) < 0.06
    assert abs(response["eta"] - 116.0) < 2.5
    assert abs(response["gamma"] - 283.7) < 2.5


def test_calculate_api_runs_real_mdm_with_identity(helpers):
    """真实后端路径：/calculate 的 MDM 调用（默认 offset=0.1）复现 182-046 理想样本。"""
    # 谢里阳等 (2025) §2 理想样本：W(2, 1000, 1000)、n=7、精确中位秩反算
    ideal_sample = [1314.68, 1509.32, 1672.86, 1832.55, 2005.13, 2215.02, 2536.73]
    response = helpers._run_calculation_method("mdm", ideal_sample)

    assert response["method"] == "mdm"
    assert response["converged"] is True
    assert abs(response["beta"] - 2.0) < 0.05
    assert abs(response["eta"] - 1000.0) < 15.0
    assert abs(response["gamma"] - 1000.0) < 15.0


# Soman & Misra (1992) Example 2（src/content/182-104-pdf原文.md），
# LSE 基准：c=0.8361, b=8.8521, mu=99.9（MLE 失效区）。
_SOMAN_EX2 = [102.4378, 114.7585, 103.5102, 101.3378, 141.7785,
              102.5250, 102.5244, 124.9970, 146.9202, 117.0452,
              103.5730, 113.6165, 102.2618, 110.0926, 107.1926,
              125.1443, 100.3264, 102.9202, 100.0017, 107.7962,
              101.3272, 101.3620, 102.5391, 100.0935, 104.8785,
              125.1759, 105.1076, 101.6966, 102.4999, 130.1677]


def test_calculate_api_runs_real_lse_with_identity(helpers):
    """真实后端路径：/calculate 的 LSE 调用返回 lse 身份和论文基准参数。"""
    response = helpers._run_calculation_method("lse", _SOMAN_EX2)

    assert response["method"] == "lse"
    assert response["converged"] is True
    assert abs(response["beta"] - 0.8361) < 0.08
    assert abs(response["eta"] - 8.8521) < 0.4
    assert abs(response["gamma"] - 99.9) < 0.5


def test_calculate_api_runs_real_mm_with_identity(helpers):
    """真实后端路径：/calculate 的 MM 调用返回 mm 身份和有限合法参数。"""
    import numpy as np

    rng = np.random.default_rng(2)
    sample = (50.0 + 200.0 * np.sort(rng.weibull(1.5, 60))).tolist()
    response = helpers._run_calculation_method("mm", sample)

    assert response["method"] == "mm"
    assert response["converged"] is True
    assert response["beta"] > 0
    assert response["eta"] > 0
    assert 0.0 <= response["gamma"] < min(sample)


def test_calculate_api_runs_real_lre_with_identity(helpers):
    """真实后端路径：/calculate 的 LRE 调用返回 lre 身份和有限合法参数。"""
    import numpy as np

    from studies.common.sample import generate_sample

    fixed = generate_sample(2.0, 100.0, 5.0, 30, 0)
    response = helpers._run_calculation_method("lre", fixed)

    assert response["method"] == "lre"
    assert response["converged"] is True
    assert response["beta"] > 0
    assert response["eta"] > 0
    assert 0.0 <= response["gamma"] < min(fixed)


def test_calculate_api_returns_422_for_degenerate_lre(helpers):
    """退化 LRE 全等值样本必须经真实 /calculate 路径返回 HTTP 422。"""
    with pytest.raises(HTTPException) as exc:
        helpers._run_calculation_method("lre", [5.0, 5.0, 5.0, 5.0, 5.0])

    assert exc.value.status_code == 422
    assert "lre" in exc.value.detail
