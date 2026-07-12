from pathlib import Path
import sys


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
