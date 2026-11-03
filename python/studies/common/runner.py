"""
统一方法调用模块

通过 registry 解析方法 ID，实例化并调用 run()，
兼容 MethodResult / 5 元组 / 4 元组三种返回格式。

规范来源：AI辅助三参数威布尔参数估计S4统一蒙特卡洛框架规划 第 3.3 节
"""

import inspect
import time
import hashlib
import json
import uuid
import platform
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Dict, Any

import numpy as np
import scipy

from base import MethodResult
from methods.registry import resolve_method


def _calculation_record(instance, method_id, values, run_kwargs, elapsed, result):
    """Bind backend-owned chart quantities to the exact sample and implementation."""
    record = getattr(instance, 'calculation_trace', None)
    if record is None:
        info = (result.get('extra') or {}).get('solution_info') or result.get('extra') or {}
        explanations = {
            'weight_table_unsupported_sample_size': '本次样本量超出当前已核验权重表的3–100覆盖范围；未使用表外替代权重。',
            'inadmissible_moments': '样本矩不满足 m̄₁−m̄₂ > m̄₂−m̄₄ > 0，原式不能给出可采纳的正形状与尺度。',
            'fixed_point_not_converged': '形状不动点迭代未满足停止条件；保留失败状态，没有改用其他求解方法。',
        }
        reason = explanations.get(info.get('status'), info.get('error', '本次运行未满足估计的接受条件。'))
        record = dict(schema_version=1, method=method_id, charts=[],
                      criterion=dict(description=reason),
                      selection=dict(status=info.get('status', 'failed'),
                                     description=reason),
                      details=info)
    source_root = Path(__file__).resolve().parents[2]
    source_paths = [Path(inspect.getfile(type(instance))).resolve(), source_root / 'base.py',
                    source_root / 'methods' / 'calculation_trace.py']
    if method_id in ('mle', 'wmle'):
        source_paths.extend(source_root / 'methods' / name for name in
                            ('profile_solvers.py', 'conditional_profiles.py'))
    if method_id == 'wmle':
        source_paths.append(source_root / 'methods' / 'wmle.py')
        source_paths.append(source_root / 'methods' / 'j3_weights.tsv')
    sources = [{"path": path.relative_to(source_root).as_posix(),
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
               for path in source_paths if path.is_file()]
    payload = json.dumps(sorted(float(v) for v in values), separators=(',', ':'), allow_nan=False)
    effective_parameters = {name: parameter.default for name, parameter in inspect.signature(instance.run).parameters.items()
                            if parameter.default is not inspect.Parameter.empty and name != 'trace'}
    effective_parameters.update({k: v for k, v in run_kwargs.items() if k != 'trace'})
    record['run'] = dict(id=str(uuid.uuid4()), completed_at=datetime.now(timezone.utc).isoformat(),
                         sample_sha256=hashlib.sha256(payload.encode()).hexdigest(),
                         observations=sorted(float(v) for v in values), n=int(len(values)),
                         parameters=effective_parameters,
                         duration_seconds=elapsed, sources=sources,
                         runtime=dict(python=platform.python_version(), numpy=np.__version__, scipy=scipy.__version__))
    def serializable(value):
        if isinstance(value, dict):
            return {str(k): serializable(v) for k, v in value.items()}
        if isinstance(value, (list, tuple, np.ndarray)):
            return [serializable(v) for v in value]
        if isinstance(value, (float, np.floating)):
            return float(value) if np.isfinite(value) else None
        if isinstance(value, np.integer):
            return int(value)
        if isinstance(value, np.bool_):
            return bool(value)
        return value
    # JSON has no NaN/Infinity. Retain such diagnostic entries as null;
    # chart constructors separately omit non-finite points rather than inventing values.
    return serializable(record)


def _accepted_run_kwargs(instance, kwargs: Dict[str, Any]) -> Dict[str, Any]:
    """只传递算法 run() 支持的参数，兼容旧方法的无参签名。"""
    signature = inspect.signature(instance.run)
    parameters = signature.parameters

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in parameters.values()):
        return kwargs

    return {key: value for key, value in kwargs.items() if key in parameters}


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

    try:
        values = np.asarray(sample, dtype=float).reshape(-1)
    except (TypeError, ValueError):
        result["extra"] = {"error": "invalid sample: observations must be numeric"}
        return result
    if values.size < 2 or not np.isfinite(values).all():
        result["extra"] = {"error": "invalid sample: at least two finite observations are required"}
        return result
    if np.any(values <= 0):
        # The production estimators require positive failure times. Never reuse
        # the historical silent filtering for a research sample outside this contract.
        result["extra"] = {"error": "invalid sample: observations must all be greater than zero"}
        return result
    if float(np.ptp(values)) == 0.0:
        result["extra"] = {"error": "invalid sample: observations must not all be equal"}
        return result

    try:
        resolved_method_id, method_cls = resolve_method(method_id)
        result["method_id"] = resolved_method_id
    except Exception as e:
        result["extra"] = {"error": f"resolve_method failed: {e}"}
        return result

    try:
        instance = method_cls(values)
        run_kwargs = _accepted_run_kwargs(instance, kwargs)
        t0 = time.perf_counter()
        raw = instance.run(**run_kwargs)
        elapsed = time.perf_counter() - t0

        result["time"] = elapsed

        if isinstance(raw, MethodResult):
            if isinstance(raw.converged, str) and raw.converged is not True:
                result["converged"] = False
                result["extra"] = {"raw_status": raw.converged}
            else:
                result["converged"] = bool(raw.converged)

            if raw.beta is not None:
                result["beta_hat"] = float(raw.beta)
                result["eta_hat"] = float(raw.eta)
                result["gamma_hat"] = float(raw.gamma)
                result["r_squared"] = float(raw.r_squared)
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

        # 无条件暴露 last_solution_info（MDM 求解器诊断）
        solution_info = getattr(instance, "last_solution_info", None)
        if solution_info is not None:
            if result["extra"] is None:
                result["extra"] = {}
            result["extra"]["solution_info"] = solution_info

        if kwargs.get('include_plot_points') and result['beta_hat'] is not None:
            # Probability-plot diagnostics use this instance's actual rank rule.
            # LRE uses its own Park plotting positions; others use their actual rank setting.
            probabilities = getattr(instance, 'plotting_positions', None)
            if probabilities is None:
                probabilities = instance._median_ranks()
            result['plot_points'] = [dict(x=float(np.log(t-result['gamma_hat'])),
                                          y=float(np.log(-np.log1p(-p))),
                                          originalValue=float(t), medianRank=float(p))
                                     for t, p in zip(instance.data, probabilities)
                                     if t > result['gamma_hat']]

        if kwargs.get("trace"):
            trace_data = getattr(instance, "trace_data", None)
            if isinstance(raw, MethodResult) and raw.trace_data is not None:
                trace_data = raw.trace_data
            result["trace_data"] = trace_data
            result['calculation'] = _calculation_record(
                instance, resolved_method_id, values, run_kwargs, elapsed, result)
    except Exception as e:
        result["extra"] = {"error": f"{type(e).__name__}: {e}"}
        if kwargs.get("trace"):
            result["trace_data"] = None

    return result
