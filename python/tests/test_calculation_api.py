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
