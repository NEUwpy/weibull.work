"""
统一方法调用模块

通过 registry 解析方法 ID，实例化并调用 run()，
兼容 MethodResult / 5 元组 / 4 元组三种返回格式。

规范来源：AI辅助三参数威布尔参数估计S4统一蒙特卡洛框架规划 第 3.3 节
"""

import time
import traceback
from typing import Optional, Dict, Any

from base import MethodResult
from methods.registry import resolve_method
from methods.mdm_variants import (
    mdm_offset_strict,
    mdm_offset_constrained,
    mdm_min_sigma,
    mdm_allow_negative_gamma,
)

# MDM 变体函数表：key=method_variant, value=(函数, method_id)
_MDM_VARIANTS = {
    "mdm_offset_strict": (mdm_offset_strict, "mdm"),
    "mdm_offset_constrained": (mdm_offset_constrained, "mdm"),
    "mdm_min_sigma": (mdm_min_sigma, "mdm"),
    "mdm_allow_negative_gamma": (mdm_allow_negative_gamma, "mdm"),
}


def run_method(method_id: str, sample, variant: Optional[str] = None,
               **kwargs) -> Dict[str, Any]:
    """统一调用估计方法，返回标准化结果字典。

    Args:
        method_id: 方法标识（如 "mle", "mdm"）
        sample: 排序后的样本（list 或 np.ndarray）
        variant: 方法方案标识，用于区分同一方法的不同参数配置；
                 为 None 时自动设为 method_id
        **kwargs: 方法特有参数（如 MDM 的 offset, gamma_steps）

    Returns:
        标准化结果字典：
        {
            "method_id": str,
            "method_variant": str,
            "beta_hat": float | None,
            "eta_hat": float | None,
            "gamma_hat": float | None,
            "r_squared": float | None,
            "converged": bool,
            "time": float,
            "extra": dict | None,
        }
    """
    method_variant = variant if variant is not None else method_id

    result = {
        "method_id": method_id,
        "method_variant": method_variant,
        "beta_hat": None,
        "eta_hat": None,
        "gamma_hat": None,
        "r_squared": None,
        "converged": False,
        "time": 0.0,
        "extra": None,
    }

    # MDM 变体函数：直接调用，不经 registry
    variant_fn_info = _MDM_VARIANTS.get(method_variant)
    if variant_fn_info is not None:
        variant_fn, effective_id = variant_fn_info
        result["method_id"] = effective_id
        try:
            t0 = time.perf_counter()
            raw = variant_fn(sample, **kwargs)
            elapsed = time.perf_counter() - t0
            result["time"] = elapsed
            if raw[0] is None:
                result["converged"] = False
            else:
                result["beta_hat"] = float(raw[0])
                result["eta_hat"] = float(raw[1])
                result["gamma_hat"] = float(raw[2])
                result["converged"] = True
            # 捕获 fallback_reason（如有）
            reason = getattr(variant_fn, "last_fallback_reason", None)
            if reason is not None:
                result["extra"] = {"fallback_reason": reason}
        except Exception as e:
            result["extra"] = {"error": f"{type(e).__name__}: {e}"}
        return result

    try:
        _, method_cls = resolve_method(method_id)
    except Exception as e:
        result["extra"] = {"error": f"resolve_method failed: {e}"}
        return result

    try:
        instance = method_cls(sample)
        t0 = time.perf_counter()
        raw = instance.run(**kwargs)
        elapsed = time.perf_counter() - t0

        result["time"] = elapsed

        if isinstance(raw, MethodResult):
            result["beta_hat"] = float(raw.beta)
            result["eta_hat"] = float(raw.eta)
            result["gamma_hat"] = float(raw.gamma)
            result["r_squared"] = float(raw.r_squared)
            result["converged"] = bool(raw.converged)
        elif isinstance(raw, (list, tuple)):
            # 检查第 5 个元素是否为非 True 的状态字符串（如 "no_intersection"）
            if len(raw) >= 5:
                status_val = raw[4]
                if isinstance(status_val, str) and status_val is not True:
                    # 方法返回了诊断状态（如 MDM 的 "no_intersection"）
                    result["converged"] = False
                    result["extra"] = {"raw_status": status_val}
                elif raw[0] is None:
                    # 返回值包含 None（如 MDM 无交点时）
                    result["converged"] = False
                    if isinstance(status_val, str):
                        result["extra"] = {"raw_status": status_val}
                else:
                    result["beta_hat"] = float(raw[0])
                    result["eta_hat"] = float(raw[1])
                    result["gamma_hat"] = float(raw[2])
                    result["r_squared"] = float(raw[3])
                    result["converged"] = bool(status_val)
            elif len(raw) == 4:
                if raw[0] is None:
                    result["converged"] = False
                else:
                    result["beta_hat"] = float(raw[0])
                    result["eta_hat"] = float(raw[1])
                    result["gamma_hat"] = float(raw[2])
                    result["r_squared"] = float(raw[3])
                    result["converged"] = True
    except Exception as e:
        result["extra"] = {"error": f"{type(e).__name__}: {e}"}

    return result
