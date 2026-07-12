"""Declared-domain admission audit for traditional Weibull estimators."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

import numpy as np


DECLARED_DOMAINS: dict[str, dict[str, Any]] = {
    "mle": {"sample_min": "positive", "gamma": "unrestricted_below_sample_min"},
    "mps": {"sample_min": "positive", "gamma": "implementation_pending"},
    "wmle": {"sample_min": "positive", "gamma": "nonnegative_below_sample_min"},
    "mdm": {"sample_min": "positive", "gamma": "nonnegative_below_sample_min", "kwargs": {"offset": 0.1}},
    "lre": {"sample_min": "positive", "gamma": "nonnegative_below_sample_min"},
    "mmle": {"sample_min": "positive", "gamma": "nonnegative_below_sample_min"},
    "lse": {"sample_min": "positive", "gamma": "implementation_pending"},
    "mm": {"sample_min": "positive", "gamma": "implementation_pending"},
    "pwm": {"sample_min": "positive", "gamma": "implementation_pending"},
}


@dataclass(frozen=True)
class AdmissionResult:
    method_id: str
    admitted_core: bool
    case_status: dict[str, str]
    messages: dict[str, str]
    residuals: dict[str, float] = field(default_factory=dict)


def _valid_result(result: Mapping, sample: Sequence[float]) -> bool:
    estimates = [result.get("beta_hat"), result.get("eta_hat"), result.get("gamma_hat")]
    return bool(
        all(value is not None and np.isfinite(value) for value in estimates)
        and float(estimates[0]) > 0
        and float(estimates[1]) > 0
        and float(estimates[2]) < float(np.min(sample))
        and result.get("converged", True)
    )


def audit_method(
    method_id: str,
    declared_domain: Mapping[str, Any],
    cases: Sequence[Mapping[str, Any]],
    *,
    runner: Callable[..., Mapping],
) -> AdmissionResult:
    statuses: dict[str, str] = {}
    messages: dict[str, str] = {}
    if declared_domain.get("gamma") == "implementation_pending":
        for case in cases:
            case_id = str(case["case_id"])
            statuses[case_id] = "implementation_not_admitted"
            messages[case_id] = "repository implementation is pending or raises NotImplementedError"
        return AdmissionResult(method_id, False, statuses, messages)
    core_failure = False
    kwargs = dict(declared_domain.get("kwargs", {}))
    for case in cases:
        case_id = str(case["case_id"])
        if not bool(case["in_declared_domain"]):
            statuses[case_id] = "out_of_declared_domain"
            messages[case_id] = "case skipped outside the method's declared support domain"
            continue
        try:
            result = runner(method_id, case["sample"], **kwargs)
            if _valid_result(result, case["sample"]):
                statuses[case_id] = "contract_pass"
                messages[case_id] = "finite, converged, and support-legal estimate"
            else:
                statuses[case_id] = "contract_failure"
                messages[case_id] = "invalid, unconverged, or support-illegal estimate"
                core_failure = True
        except Exception as error:
            statuses[case_id] = "contract_failure"
            messages[case_id] = f"{type(error).__name__}: {error}"
            core_failure = True
    return AdmissionResult(method_id, not core_failure, statuses, messages)


def _parameter_vector(result: Mapping[str, Any]) -> np.ndarray:
    return np.asarray(
        [result.get("beta_hat"), result.get("eta_hat"), result.get("gamma_hat")],
        dtype=float,
    )


def _relative_residual(observed: np.ndarray, expected: np.ndarray) -> float:
    denominator = np.maximum(np.abs(expected), 1.0)
    return float(np.max(np.abs(observed - expected) / denominator))


def audit_method_contracts(
    method_id: str,
    declared_domain: Mapping[str, Any],
    sample: Sequence[float],
    *,
    runner: Callable[..., Mapping],
    deterministic_rtol: float = 1e-12,
    equivariance_rtol: float = 1e-3,
    scale_factor: float = 1000.0,
) -> AdmissionResult:
    """Fail-closed audit of all contracts required before core admission.

    The transformations stay inside the positive-sample domain declared for the
    current method.  Residuals are normalized componentwise so beta, eta and
    gamma can be judged by one frozen dimensionless tolerance.
    """

    contract_ids = (
        "core",
        "determinism",
        "scale_equivariance",
        "translation_equivariance",
        "failure_propagation",
    )
    if declared_domain.get("gamma") == "implementation_pending":
        status = {identifier: "implementation_not_admitted" for identifier in contract_ids}
        messages = {
            identifier: "repository implementation is pending or raises NotImplementedError"
            for identifier in contract_ids
        }
        return AdmissionResult(method_id, False, status, messages)

    values = np.asarray(sample, dtype=float).reshape(-1)
    if values.size < 3 or not np.isfinite(values).all() or float(values.min()) <= 0:
        raise ValueError("contract audit requires at least three finite positive observations")
    kwargs = dict(declared_domain.get("kwargs", {}))
    statuses: dict[str, str] = {}
    messages: dict[str, str] = {}
    residuals: dict[str, float] = {}

    try:
        base = runner(method_id, values.tolist(), **kwargs)
    except Exception as error:
        statuses["core"] = "contract_failure"
        messages["core"] = f"{type(error).__name__}: {error}"
        for identifier in contract_ids[1:]:
            statuses[identifier] = "not_evaluable_after_core_failure"
            messages[identifier] = "core estimate failed"
        return AdmissionResult(method_id, False, statuses, messages, residuals)

    if not _valid_result(base, values):
        statuses["core"] = "contract_failure"
        messages["core"] = "invalid, unconverged, or support-illegal estimate"
        for identifier in contract_ids[1:]:
            statuses[identifier] = "not_evaluable_after_core_failure"
            messages[identifier] = "core estimate failed"
        return AdmissionResult(method_id, False, statuses, messages, residuals)

    statuses["core"] = "contract_pass"
    messages["core"] = "finite, converged, and support-legal estimate"
    base_vector = _parameter_vector(base)

    checks: list[tuple[str, np.ndarray, np.ndarray, float]] = []
    try:
        repeated = runner(method_id, values.tolist(), **kwargs)
        checks.append(("determinism", _parameter_vector(repeated), base_vector, deterministic_rtol))

        scaled_sample = values * float(scale_factor)
        scaled = runner(method_id, scaled_sample.tolist(), **kwargs)
        checks.append((
            "scale_equivariance",
            _parameter_vector(scaled),
            base_vector * np.asarray([1.0, scale_factor, scale_factor]),
            equivariance_rtol,
        ))

        shift = max(1.0, float(values.min()) / 2.0)
        translated_sample = values + shift
        translated = runner(method_id, translated_sample.tolist(), **kwargs)
        checks.append((
            "translation_equivariance",
            _parameter_vector(translated),
            base_vector + np.asarray([0.0, 0.0, shift]),
            equivariance_rtol,
        ))
    except Exception as error:
        missing = contract_ids[1:4]
        for identifier in missing:
            if identifier not in statuses:
                statuses[identifier] = "contract_failure"
                messages[identifier] = f"{type(error).__name__}: {error}"

    for identifier, observed, expected, tolerance in checks:
        residual = _relative_residual(observed, expected) if np.isfinite(observed).all() else float("inf")
        residuals[identifier] = residual
        if residual <= tolerance:
            statuses[identifier] = "contract_pass"
            messages[identifier] = f"normalized residual {residual:.6g} <= {tolerance:.6g}"
        else:
            statuses[identifier] = "contract_failure"
            messages[identifier] = f"normalized residual {residual:.6g} > {tolerance:.6g}"

    try:
        degenerate = np.full(values.size, float(values.mean()))
        failure_result = runner(method_id, degenerate.tolist(), **kwargs)
        if _valid_result(failure_result, degenerate):
            statuses["failure_propagation"] = "contract_failure"
            messages["failure_propagation"] = "degenerate sample silently returned a valid estimate"
        else:
            statuses["failure_propagation"] = "contract_pass"
            messages["failure_propagation"] = "degenerate sample propagated as invalid or unconverged"
    except Exception as error:
        statuses["failure_propagation"] = "contract_failure"
        messages["failure_propagation"] = f"runner leaked {type(error).__name__}: {error}"

    admitted = all(statuses.get(identifier) == "contract_pass" for identifier in contract_ids)
    return AdmissionResult(method_id, admitted, statuses, messages, residuals)
