from pathlib import Path
import sys

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CODE = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))

from study02a.admission import DECLARED_DOMAINS, audit_method, audit_method_contracts


def test_out_of_domain_case_does_not_remove_core_admission():
    calls = []

    def runner(method_id, sample, **kwargs):
        calls.append(tuple(sample))
        return {"beta_hat": 2.0, "eta_hat": 100.0, "gamma_hat": 5.0, "converged": True}

    cases = [
        {"case_id": "core", "sample": [10.0, 20.0, 30.0], "in_declared_domain": True},
        {"case_id": "negative-shift", "sample": [-20.0, -10.0, 0.0], "in_declared_domain": False},
    ]
    result = audit_method("wmle", DECLARED_DOMAINS["wmle"], cases, runner=runner)
    assert result.admitted_core is True
    assert result.case_status["negative-shift"] == "out_of_declared_domain"
    assert len(calls) == 1


def test_support_domain_failure_fails_closed():
    def runner(method_id, sample, **kwargs):
        raise RuntimeError("solver failed")

    cases = [{"case_id": "core", "sample": [10.0, 20.0, 30.0], "in_declared_domain": True}]
    result = audit_method("mle", DECLARED_DOMAINS["mle"], cases, runner=runner)
    assert result.admitted_core is False
    assert result.case_status["core"] == "contract_failure"


def test_pending_implementation_fails_closed_without_calling_runner():
    def runner(method_id, sample, **kwargs):
        raise AssertionError("pending implementation must not be executed")

    cases = [{"case_id": "core", "sample": [10.0, 20.0, 30.0], "in_declared_domain": True}]
    result = audit_method("mps", DECLARED_DOMAINS["mps"], cases, runner=runner)
    assert result.admitted_core is False
    assert result.case_status["core"] == "implementation_not_admitted"


def test_full_contract_audit_checks_determinism_equivariance_and_failure_propagation():
    def runner(method_id, sample, **kwargs):
        values = list(sample)
        if max(values) == min(values):
            return {"beta_hat": None, "eta_hat": None, "gamma_hat": None, "converged": False}
        span = max(values) - min(values)
        return {
            "beta_hat": 2.0,
            "eta_hat": span,
            "gamma_hat": min(values) - span,
            "converged": True,
        }

    result = audit_method_contracts(
        "mle", DECLARED_DOMAINS["mle"], [10.0, 20.0, 40.0], runner=runner
    )
    assert result.admitted_core is True
    assert result.case_status == {
        "core": "contract_pass",
        "determinism": "contract_pass",
        "scale_equivariance": "contract_pass",
        "translation_equivariance": "contract_pass",
        "failure_propagation": "contract_pass",
    }
    assert set(result.residuals) == {"determinism", "scale_equivariance", "translation_equivariance"}


def test_full_contract_audit_fails_closed_on_silent_degenerate_success():
    def runner(method_id, sample, **kwargs):
        return {"beta_hat": 2.0, "eta_hat": 1.0, "gamma_hat": min(sample) - 1.0, "converged": True}

    result = audit_method_contracts(
        "mle", DECLARED_DOMAINS["mle"], [10.0, 20.0, 40.0], runner=runner
    )
    assert result.admitted_core is False
    assert result.case_status["failure_propagation"] == "contract_failure"


@pytest.mark.parametrize("method_id, admitted", [("mmle", True), ("mle", False), ("wmle", False), ("mdm", False), ("lre", False)])
def test_only_mmle_accepts_location_at_deleted_minimum(method_id, admitted):
    def runner(method_id, sample, **kwargs):
        return {"beta_hat": 2.0, "eta_hat": 100.0, "gamma_hat": min(sample), "converged": True}

    cases = [{"case_id": "core", "sample": [30.0, 10.0, 20.0], "in_declared_domain": True}]
    result = audit_method(method_id, DECLARED_DOMAINS[method_id], cases, runner=runner)
    assert result.admitted_core is admitted
    assert DECLARED_DOMAINS["mmle"]["gamma"] == "nonnegative_below_retained_sample_min"


@pytest.mark.parametrize("sample, gamma, converged, admitted", [
    ([30.0, 10.0, 20.0], 10.0, True, True),
    ([30.0, 10.0, 20.0], 15.0, True, True),
    ([30.0, 10.0, 20.0], 20.0, True, False),
    ([30.0, 10.0, 20.0], 21.0, True, False),
    ([30.0, 10.0, 20.0], -1.0, True, False),
    ([30.0, 10.0, 20.0], 10.0, False, False),
    ([30.0, 10.0, 10.0], 10.0, True, False),
    ([20.0, 10.0, 20.0], 10.0, True, True),
    ([10.0], 10.0, True, False),
    ([], 10.0, True, False),
    ([10.0, np.nan, 20.0], 10.0, True, False),
    ([10.0, np.inf, 20.0], 10.0, True, False),
    ([0.0, 10.0, 20.0], 0.0, True, False),
    ([10.0, 20.0, 30.0], np.nan, True, False),
])
def test_mmle_admission_checks_the_retained_support(sample, gamma, converged, admitted):
    def runner(method_id, sample, **kwargs):
        return {"beta_hat": 2.0, "eta_hat": 100.0, "gamma_hat": gamma, "converged": converged}

    cases = [{"case_id": "core", "sample": sample, "in_declared_domain": True}]
    result = audit_method("mmle", DECLARED_DOMAINS["mmle"], cases, runner=runner)
    assert result.admitted_core is admitted
    assert result.case_status["core"] == ("contract_pass" if admitted else "contract_failure")


def _kr_contract_runner(method_id, sample, **kwargs):
    if max(sample) == min(sample):
        return {"beta_hat": None, "eta_hat": None, "gamma_hat": None, "converged": False}
    return {"beta_hat": 2.0, "eta_hat": max(sample) - min(sample), "gamma_hat": min(sample), "converged": True}


def test_mmle_full_contract_audit_accepts_retained_support_for_all_transformations():
    result = audit_method_contracts(
        "mmle", DECLARED_DOMAINS["mmle"], [40.0, 10.0, 20.0], runner=_kr_contract_runner,
    )
    assert result.admitted_core is True
    assert all(status == "contract_pass" for status in result.case_status.values())
    assert all(residual == 0.0 for residual in result.residuals.values())


@pytest.mark.parametrize("call_index, contract", [(2, "determinism"), (3, "scale_equivariance"), (4, "translation_equivariance")])
def test_mmle_full_contract_audit_rejects_unconverged_transformed_results(call_index, contract):
    calls = 0

    def runner(method_id, sample, **kwargs):
        nonlocal calls
        calls += 1
        result = _kr_contract_runner(method_id, sample, **kwargs)
        if calls == call_index:
            result["converged"] = False
        return result

    result = audit_method_contracts(
        "mmle", DECLARED_DOMAINS["mmle"], [40.0, 10.0, 20.0], runner=runner,
    )
    assert result.admitted_core is False
    assert result.case_status[contract] == "contract_failure"
    assert np.isinf(result.residuals[contract])


def test_mmle_full_contract_audit_rejects_support_violation_even_with_small_residual():
    calls = 0

    def runner(method_id, sample, **kwargs):
        nonlocal calls
        calls += 1
        result = _kr_contract_runner(method_id, sample, **kwargs)
        if calls == 2:
            result["gamma_hat"] = sorted(sample)[1]
        return result

    result = audit_method_contracts(
        "mmle", DECLARED_DOMAINS["mmle"], [40.0, 10.0, 10.0000001], runner=runner,
    )
    assert result.admitted_core is False
    assert result.case_status["determinism"] == "contract_failure"


def test_mmle_full_contract_audit_rejects_repeated_minimum_after_deleting_one():
    result = audit_method_contracts(
        "mmle", DECLARED_DOMAINS["mmle"], [30.0, 10.0, 10.0], runner=_kr_contract_runner,
    )
    assert result.admitted_core is False
    assert result.case_status["core"] == "contract_failure"


def test_mmle_full_contract_audit_detects_silent_degenerate_success():
    def runner(method_id, sample, **kwargs):
        if max(sample) == min(sample):
            return {"beta_hat": 2.0, "eta_hat": 1.0, "gamma_hat": min(sample) - 1.0, "converged": True}
        return _kr_contract_runner(method_id, sample, **kwargs)

    result = audit_method_contracts(
        "mmle", DECLARED_DOMAINS["mmle"], [40.0, 10.0, 20.0], runner=runner,
    )
    assert result.admitted_core is False
    assert result.case_status["failure_propagation"] == "contract_failure"
