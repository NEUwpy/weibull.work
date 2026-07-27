from pathlib import Path
import sys

import numpy as np
import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
STUDY_CODE = REPO_ROOT / "Study" / "02-study-NN参数估计与分位点目标研究" / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
if str(REPO_ROOT / "python") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "python"))

from study02a.evaluation import (
    cluster_bootstrap_difference,
    evaluate_rows,
    global_better_from_intervals,
    parameter_loss,
)


def test_parameter_loss_matches_frozen_formula():
    result = parameter_loss(2.2, 90.0, 15.0, 2.0, 100.0, 10.0)
    expected = np.sqrt((0.1**2 + (-0.1)**2 + 0.05**2) / 3.0)
    assert result == pytest.approx(expected)


def test_evaluation_keeps_failures_and_applies_penalty():
    rows = [
        {"beta_hat": 2.0, "eta_hat": 100.0, "gamma_hat": 10.0, "beta": 2.0, "eta": 100.0, "gamma": 10.0, "sample_min": 20.0, "converged": True},
        {"beta_hat": None, "eta_hat": None, "gamma_hat": None, "beta": 2.0, "eta": 100.0, "gamma": 10.0, "sample_min": 20.0, "converged": False},
    ]
    result = evaluate_rows(rows, failure_penalty=10.0)
    assert result["n_total"] == 2
    assert result["n_failure"] == 1
    assert result["failure_rate"] == 0.5
    assert result["conditional_mean_l_param"] == pytest.approx(0.0)
    assert result["unconditional_mean_l_param"] == pytest.approx(5.0)


def test_single_parameter_gain_cannot_be_called_global_better():
    decision = global_better_from_intervals(
        failure_diff_upper=0.005,
        l_param_improvement_lower=0.02,
        component_worsening_upper={"beta": 0.01, "eta": 0.08, "gamma": 0.02},
    )
    assert decision == "tradeoff"


def test_cluster_bootstrap_is_reproducible():
    clusters = np.repeat(np.arange(8), 3)
    a = np.linspace(0.2, 1.0, len(clusters))
    b = a + 0.1
    first = cluster_bootstrap_difference(a, b, clusters, replicates=200, seed=520001)
    second = cluster_bootstrap_difference(a, b, clusters, replicates=200, seed=520001)
    assert first == second
    assert first["mean_improvement"] == pytest.approx(0.1)

# ---------------------------------------------------------------------------
# R6: numerical overflow / non-finite regression tests.
# ---------------------------------------------------------------------------

import math

from study02a.evaluation import evaluate_rows_per_sample


def _row(beta_hat, eta_hat, gamma_hat, beta=2.0, eta=100.0, gamma=10.0, sample_min=20.0):
    return {
        "sample_id": "s1", "seed_id": "420001", "point_id": "p1",
        "beta_hat": beta_hat, "eta_hat": eta_hat, "gamma_hat": gamma_hat,
        "beta": beta, "eta": eta, "gamma": gamma, "sample_min": sample_min,
    }


def test_r6_exp_decode_overflow_demoted_to_failure():
    """exp(700) overflows to Inf; _legal catches it as non-finite estimate."""
    row = _row(float("inf"), 100.0, 10.0)
    records = evaluate_rows_per_sample([row], failure_penalty=10.0)
    assert records[0]["legal"] is False
    assert records[0]["failure"] == 1
    assert records[0]["l_param"] == 10.0
    assert records[0]["e_beta"] == 10.0


def test_r6_huge_finite_estimate_error_squared_overflow():
    """Finite but huge estimate (1e300) causes error^2 overflow to Inf in L_param."""
    row = _row(1e300, 100.0, 10.0)
    records = evaluate_rows_per_sample([row], failure_penalty=10.0)
    assert records[0]["legal"] is False
    assert records[0]["failure"] == 1
    assert records[0]["l_param"] == 10.0
    assert all(math.isfinite(records[0][f]) for f in ("l_param", "e_beta", "e_eta", "e_gamma"))


def test_r6_nan_estimate_demoted_to_failure():
    """NaN estimate is caught by _legal as non-finite."""
    row = _row(float("nan"), 100.0, 10.0)
    records = evaluate_rows_per_sample([row], failure_penalty=10.0)
    assert records[0]["legal"] is False
    assert records[0]["l_param"] == 10.0


def test_r6_evaluate_rows_consistent_with_per_sample():
    """evaluate_rows and evaluate_rows_per_sample agree on overflow demotion."""
    rows = [
        {**_row(1e300, 100.0, 10.0), "sample_id": "s1"},
        {**_row(2.0, 100.0, 10.0), "sample_id": "s2"},
    ]
    per_sample = evaluate_rows_per_sample(rows, failure_penalty=10.0)
    aggregate = evaluate_rows(rows, failure_penalty=10.0)
    assert per_sample[0]["legal"] is False
    assert per_sample[1]["legal"] is True
    assert aggregate["n_failure"] == 1
    assert aggregate["n_valid"] == 1
    expected_mean = (10.0 + per_sample[1]["l_param"]) / 2.0
    assert aggregate["unconditional_mean_l_param"] == pytest.approx(expected_mean)


def test_r6_legal_result_unchanged():
    """Normal legal estimates produce finite, correct L_param (no regression)."""
    row = _row(2.2, 90.0, 15.0)
    records = evaluate_rows_per_sample([row], failure_penalty=10.0)
    assert records[0]["legal"] is True
    assert records[0]["failure"] == 0
    expected = math.sqrt((0.1**2 + (-0.1)**2 + 0.05**2) / 3.0)
    assert records[0]["l_param"] == pytest.approx(expected)
    assert all(math.isfinite(records[0][f]) for f in ("l_param", "e_beta", "e_eta", "e_gamma"))


def test_r6_scalar_equals_point_record_mean():
    """selection_score (scalar) must equal mean of point_records l_param."""
    rows = [
        {**_row(2.2, 90.0, 15.0), "sample_id": "s1"},
        {**_row(1e300, 100.0, 10.0), "sample_id": "s2"},
        {**_row(2.0, 110.0, 9.0), "sample_id": "s3"},
    ]
    records = evaluate_rows_per_sample(rows, failure_penalty=10.0)
    scalar = sum(r["l_param"] for r in records) / len(records)
    assert math.isfinite(scalar)
    assert records[0]["legal"] is True
    assert records[1]["legal"] is False
    assert records[2]["legal"] is True


def test_r6_require_finite_evaluation_rejects_nan():
    """_require_finite_evaluation raises on NaN selection_score."""
    from study02a.formal_executor import _require_finite_evaluation
    with pytest.raises(ValueError, match="non-finite"):
        _require_finite_evaluation("fit-x", float("nan"), ())


def test_r6_require_finite_evaluation_rejects_inf_point_record():
    """_require_finite_evaluation raises on Inf in point record."""
    from study02a.formal_executor import _require_finite_evaluation
    bad_record = {"sample_id": "s1", "l_param": float("inf"), "e_beta": 0.1, "e_eta": 0.1, "e_gamma": 0.1}
    with pytest.raises(ValueError, match="non-finite"):
        _require_finite_evaluation("fit-x", 1.0, (bad_record,))


def test_r6_require_finite_evaluation_passes_valid():
    """_require_finite_evaluation passes for all-finite inputs."""
    from study02a.formal_executor import _require_finite_evaluation
    good_record = {"sample_id": "s1", "l_param": 0.5, "e_beta": 0.1, "e_eta": 0.2, "e_gamma": 0.3}
    _require_finite_evaluation("fit-x", 0.5, (good_record,))

# ---------------------------------------------------------------------------
# R6 REVISE: selection-layer finite gate attack tests.
# ---------------------------------------------------------------------------

from study02a.selection import (
    CandidateSpec,
    FitEvaluation,
    SupportKey,
    _validate_evaluation_finite,
    candidate_supporting_evidence,
)


def _make_evaluation(fit_id="fit-1", failed=False, score=0.5, penalty=10.0, records=()):
    return FitEvaluation(
        fit_id=fit_id,
        support_key=SupportKey(n=15, seed=420001),
        failed=failed,
        checkpoint_sha256="a" * 64 if not failed else "",
        selection_score=score,
        failure_penalty=penalty,
        module_id="A-E1",
        decision_id="d1",
        candidate_id="c1",
        validation_identity="v" * 64,
        point_records=records,
    )


def _make_candidate(fit_ids=("fit-1",)):
    return CandidateSpec(
        decision_id="d1",
        candidate_id="c1",
        selection_rule="lowest_aggregate",
        support_keys=tuple(SupportKey(n=15, seed=420001) for _ in fit_ids),
        expected_fit_ids=fit_ids,
        approved_seeds=(420001,),
        tie_break_key=("fit-1",),
    )


def test_r6_revise_nan_selection_score_rejected_by_gate():
    """NaN selection_score is rejected before aggregation."""
    ev = _make_evaluation(score=float("nan"))
    with pytest.raises(ValueError, match="selection_score is non-finite"):
        _validate_evaluation_finite(ev)


def test_r6_revise_inf_failure_penalty_rejected_by_gate():
    """Inf failure_penalty on a failed fit is rejected."""
    ev = _make_evaluation(failed=True, penalty=float("inf"))
    with pytest.raises(ValueError, match="failure_penalty is non-finite"):
        _validate_evaluation_finite(ev)


def test_r6_revise_inf_point_record_rejected_by_gate():
    """Inf in a point record numeric field is rejected."""
    bad_record = {"sample_id": "s1", "l_param": float("inf"), "e_beta": 0.1, "e_eta": 0.1, "e_gamma": 0.1}
    ev = _make_evaluation(records=(bad_record,))
    with pytest.raises(ValueError, match="non-finite l_param"):
        _validate_evaluation_finite(ev)


def test_r6_revise_candidate_supporting_evidence_rejects_nan_score():
    """candidate_supporting_evidence rejects NaN selection_score before aggregate."""
    ev = _make_evaluation(score=float("nan"))
    candidate = _make_candidate()
    with pytest.raises(ValueError, match="non-finite"):
        candidate_supporting_evidence(
            module_id="A-E1", run_id="r1", candidate=candidate,
            evaluations_by_support={SupportKey(n=15, seed=420001): ev},
        )


def test_r6_revise_candidate_supporting_evidence_rejects_inf_penalty():
    """candidate_supporting_evidence rejects Inf failure_penalty."""
    ev = _make_evaluation(failed=True, penalty=float("inf"))
    candidate = _make_candidate()
    with pytest.raises(ValueError, match="non-finite"):
        candidate_supporting_evidence(
            module_id="A-E1", run_id="r1", candidate=candidate,
            evaluations_by_support={SupportKey(n=15, seed=420001): ev},
        )


def test_r6_revise_finite_inputs_nonfinite_aggregate_fails_closed():
    """Finite inputs that produce a non-finite aggregate (via overflow in sum) fail closed."""
    huge = 1e308
    ev1 = _make_evaluation(fit_id="fit-1", score=huge)
    ev2 = FitEvaluation(
        fit_id="fit-2",
        support_key=SupportKey(n=15, seed=420002),
        failed=False,
        checkpoint_sha256="b" * 64,
        selection_score=huge,
        failure_penalty=10.0,
        module_id="A-E1",
        decision_id="d1",
        candidate_id="c1",
        validation_identity="v" * 64,
        point_records=(),
    )
    candidate = CandidateSpec(
        decision_id="d1",
        candidate_id="c1",
        selection_rule="lowest_aggregate",
        support_keys=(SupportKey(n=15, seed=420001), SupportKey(n=15, seed=420002)),
        expected_fit_ids=("fit-1", "fit-2"),
        approved_seeds=(420001, 420002),
        tie_break_key=("fit-1",),
    )
    with pytest.raises(ValueError, match="aggregate.*non-finite"):
        candidate_supporting_evidence(
            module_id="A-E1", run_id="r1", candidate=candidate,
            evaluations_by_support={
                SupportKey(n=15, seed=420001): ev1,
                SupportKey(n=15, seed=420002): ev2,
            },
        )


def test_r6_revise_valid_evaluation_passes_gate():
    """A fully finite evaluation passes the gate without error."""
    good_record = {"sample_id": "s1", "l_param": 0.5, "e_beta": 0.1, "e_eta": 0.2, "e_gamma": 0.3}
    ev = _make_evaluation(score=0.5, records=(good_record,))
    _validate_evaluation_finite(ev)  # should not raise


# ---------------------------------------------------------------------------
# R6 REVISE: real _decode_param_columns overflow binding test.
# ---------------------------------------------------------------------------

import torch
import numpy as np


def test_r6_revise_decode_overflow_produces_penalty_via_production_scoring():
    """Real _decode_param_columns overflow: model outputs huge values -> exp overflows
    to Inf -> _legal catches non-finite estimate -> penalty=10 in production scoring."""
    from study02a.formal_executor import _decode_param_columns, validation_failure_penalized_l_param_points
    from study02a.models import build_mlp
    from study02a.training import fit_fixed_candidate
    from study02a.formal_runner import (
        _build_training_spec_for_tests, _build_validation_spec_for_tests,
        _cache_dataset_for_tests, _pilot_for_tests,
        fit_training_scaler, apply_training_scaler,
        FormalDataset,
    )
    from study02a.config import load_frozen_config
    from study02a.formal_config import load_effective_formal_config
    import tempfile

    REPO_ROOT = Path(__file__).resolve().parents[2]
    STUDY_ROOT = REPO_ROOT / "Study" / "02-study-NN\u53c2\u6570\u4f30\u8ba1\u4e0e\u5206\u4f4d\u70b9\u76ee\u6807\u7814\u7a76"
    # Find actual study root
    for d in (REPO_ROOT / "Study").iterdir():
        if "02-study" in d.name:
            STUDY_ROOT = d
            break

    frozen = load_frozen_config(STUDY_ROOT)
    effective = load_effective_formal_config(STUDY_ROOT)

    # Directly test _decode_param_columns with values that overflow exp
    # exp(710) > float64 max (~1.8e308) -> Inf
    raw = torch.tensor([[710.0, 710.0, 710.0], [0.0, 0.0, 0.0]], dtype=torch.float32)
    location = np.array([1.0, 1.0])
    scale = np.array([1.0, 1.0])
    beta, eta, gamma = _decode_param_columns(raw, location, scale)
    # First row: exp(710) = Inf
    assert not np.isfinite(beta[0])
    assert not np.isfinite(eta[0])
    # Second row: exp(0) = 1, normal
    assert np.isfinite(beta[1])

    # Now verify that evaluate_rows_per_sample treats the Inf estimates as illegal -> penalty
    from study02a.evaluation import evaluate_rows_per_sample
    rows = [
        {"sample_id": "s1", "seed_id": "420001", "point_id": "p1",
         "beta_hat": float(beta[0]), "eta_hat": float(eta[0]), "gamma_hat": float(gamma[0]),
         "beta": 2.0, "eta": 1.0, "gamma": 0.5, "sample_min": 1.0},
        {"sample_id": "s2", "seed_id": "420001", "point_id": "p2",
         "beta_hat": float(beta[1]), "eta_hat": float(eta[1]), "gamma_hat": float(gamma[1]),
         "beta": 2.0, "eta": 1.0, "gamma": 0.5, "sample_min": 1.0},
    ]
    records = evaluate_rows_per_sample(rows, failure_penalty=10.0)
    # Row 0: Inf estimates -> _legal returns False -> penalty
    assert records[0]["legal"] is False
    assert records[0]["failure"] == 1
    assert records[0]["l_param"] == 10.0
    # Row 1: normal estimates -> legal
    assert records[1]["legal"] is True
    assert records[1]["failure"] == 0
    assert math.isfinite(records[1]["l_param"])
