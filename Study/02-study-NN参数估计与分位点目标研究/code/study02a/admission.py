"""Declared-domain admission audit for traditional Weibull estimators."""

from __future__ import annotations

from dataclasses import dataclass
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
