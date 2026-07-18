"""D7 DecisionSpec engine + selection-trace builder tests (study02a.selection).

These tests lock the deterministic decision/candidate/expected-fit derivation
(R1§3 grouping rewrite: output_form/distribution/training_size merged correctly),
the four frozen selection rules (winner COMPUTED, never supplied), the
supporting-evidence full-context hash, and the core attack surface
(missing/extra/duplicate/wrong support, cross-candidate fit reuse, expected-fit
mismatch). The frozen-matrix structural test is the authority for the corrected
grouping; the rule-path tests build synthetic DecisionSpec/FitEvaluation inputs.
"""

from __future__ import annotations

from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
sys.path.insert(0, str(STUDY_ROOT / "code"))

from study02a.config import load_frozen_config  # noqa: E402
from study02a.matrix import expand_module_matrix  # noqa: E402
from study02a.selection import (  # noqa: E402
    CandidateSpec,
    DecisionSpec,
    FitEvaluation,
    SupportKey,
    build_decision_specs,
    build_selection_trace,
    candidate_supporting_evidence,
    point_evidence_sha256,
)
from study02a.formal_contracts import (  # noqa: E402
    SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT,
    SELECTION_RULE_GLOBAL_BETTER,
    SELECTION_RULE_LOWEST_AGGREGATE,
    SELECTION_RULE_SMALLEST_WITHIN_2PCT_CI,
)

FROZEN = load_frozen_config(STUDY_ROOT)
MATRIX_ROWS = expand_module_matrix(FROZEN).to_dict("records")


# --------------------------------------------------------------------------
# Decision derivation from the frozen matrix (R1§3 corrected grouping).
# --------------------------------------------------------------------------


def test_frozen_matrix_derives_corrected_decision_grouping():
    specs = {sp.decision_id: sp for module in ("A-E1", "A-E3", "A-E2")
             for sp in build_decision_specs(module, MATRIX_ROWS)}
    # A-E1: architecture + stage2 per route (F2, V), n=10, 12 candidates, 3 screening supports.
    for route in ("F2", "V"):
        assert specs[f"architecture:A-E1:{route}:n10"].selection_rule == SELECTION_RULE_LOWEST_AGGREGATE
        assert len(specs[f"architecture:A-E1:{route}:n10"].candidates) == 12
        assert {len(c.support_keys) for c in specs[f"architecture:A-E1:{route}:n10"].candidates} == {3}
    # A-E3 loss: 1 decision, 4 candidates, 3 supports each.
    assert len(specs["loss:A-E3:selected:F2_or_V:n10"].candidates) == 4
    # A-E3 output_form: MERGED into 1 decision, 2 candidates, 50 supports (5 core n x 10 formal).
    output = specs["output_form:A-E3:selected:F2_or_V"]
    assert output.selection_rule == SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT
    assert len(output.candidates) == 2
    assert {len(c.support_keys) for c in output.candidates} == {50}
    # A-E2 training_size: MERGED into 1 decision, 4 candidates, 15 supports (5 core n x 3 screening).
    size = specs["training_size:A-E2:selected:A-E3_baseline"]
    assert size.selection_rule == SELECTION_RULE_SMALLEST_WITHIN_2PCT_CI
    assert len(size.candidates) == 4
    assert {len(c.support_keys) for c in size.candidates} == {15}
    # A-E2 distribution: MERGED into 1 decision, 3 candidates, 15 supports, global_better_rule.
    dist = specs["distribution:A-E2:selected:A-E3_baseline"]
    assert dist.selection_rule == SELECTION_RULE_GLOBAL_BETTER
    assert len(dist.candidates) == 3
    assert {len(c.support_keys) for c in dist.candidates} == {15}


def test_decision_spec_rule_is_unique_per_decision_and_frozen():
    for module in ("A-E1", "A-E3", "A-E2"):
        for spec in build_decision_specs(module, MATRIX_ROWS):
            rules = {c.selection_rule for c in spec.candidates}
            assert rules == {spec.selection_rule}  # uniform within a decision
            # every candidate's expected fit ids are unique within the decision
            all_fits = [fid for c in spec.candidates for fid in c.expected_fit_ids]
            assert len(all_fits) == len(set(all_fits))


def test_decision_spec_expected_fits_come_from_frozen_matrix_not_outcomes():
    # The expected fit ids are exactly the frozen screening rows for that candidate.
    spec = next(sp for sp in build_decision_specs("A-E3", MATRIX_ROWS)
                if sp.decision_id == "loss:A-E3:selected:F2_or_V:n10")
    for candidate in spec.candidates:
        for fit_id in candidate.expected_fit_ids:
            row = next(r for r in MATRIX_ROWS if r["fit_id"] == fit_id)
            assert row["fit_kind"] == "loss_screen"
            assert row["loss"] == candidate.candidate_id
            assert row["n"] == 10


def test_decision_specs_are_pure_functions_of_the_matrix():
    a = build_decision_specs("A-E2", MATRIX_ROWS)
    b = build_decision_specs("A-E2", list(reversed(MATRIX_ROWS)))
    assert a == b  # row order of the input does not change the derived specs


# --------------------------------------------------------------------------
# Synthetic helpers for rule-path + attack tests.
# --------------------------------------------------------------------------


def _candidate(decision_id, candidate_id, support_keys, *, rule, fit_suffix="fit"):
    fit_id_by_support = {key: f"{fit_suffix}:{candidate_id}:{key.n}:{key.seed}" for key in support_keys}
    return CandidateSpec(
        decision_id=decision_id, candidate_id=candidate_id, selection_rule=rule,
        tie_break_key=(candidate_id,), support_keys=tuple(support_keys),
        expected_fit_ids=tuple(fit_id_by_support[k] for k in support_keys),
        fit_id_by_support=fit_id_by_support,
        approved_seeds=tuple(sorted({k.seed for k in support_keys})),
    )


def _decision(decision_id, candidate_ids, support_keys, *, rule, axis="architecture"):
    cands = tuple(_candidate(decision_id, cid, support_keys, rule=rule) for cid in candidate_ids)
    return DecisionSpec(module_id="A-T", decision_id=decision_id, axis=axis,
                        selection_rule=rule, candidates=cands)


def _eval(candidate, support_key, score, *, failed=False, point_records=(), fit_id=None):
    fit_id = fit_id if fit_id is not None else candidate.fit_id_by_support[support_key]
    return FitEvaluation(
        fit_id=fit_id, support_key=support_key, failed=failed,
        checkpoint_sha256="" if failed else "a" * 64,
        selection_score=score if not failed else 0.0,
        failure_penalty=10.0 if failed else 0.0,
        point_records=tuple(point_records),
    )


def _standalone_eval(fit_id, support_key, score):
    return FitEvaluation(fit_id=fit_id, support_key=support_key, failed=False,
                         checkpoint_sha256="a" * 64, selection_score=score, failure_penalty=0.0)


def _evals_for(candidate, scores_by_support):
    return {key: _eval(candidate, key, score) for key, score in scores_by_support.items()}


SEEDS = (420101, 420102, 420103)


def _point_records(seed, base, delta=0.0):
    # 3 parameter points x 2 samples each, stable pairing ids, l_param = base+delta+noise
    records = []
    for p in range(3):
        for s in range(2):
            l = base + delta + (seed - 420101) * 0.001 + p * 0.0005 + s * 0.0001
            records.append({
                "sample_id": f"pt{p}:s{s}", "seed_id": str(seed), "point_id": f"pt{p}",
                "legal": True, "failure": 0, "l_param": l,
                "e_beta": l, "e_eta": l, "e_gamma": l,
            })
    return records


# --------------------------------------------------------------------------
# Rule paths (winner computed, never supplied).
# --------------------------------------------------------------------------


def test_lowest_aggregate_picks_argmin_with_id_tiebreak():
    keys = tuple(SupportKey(10, seed) for seed in SEEDS)
    spec = _decision("d:A-T:r:n10", ["z", "a"], keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    # tie on aggregate 0.2 -> candidate id 'a' wins
    evals = {
        "z": _evals_for(spec.candidates[0], {k: 0.2 for k in keys}),
        "a": _evals_for(spec.candidates[1], {k: 0.2 for k in keys}),
    }
    by_fit = {e.fit_id: e for cid in evals for e in evals[cid].values()}
    records = build_selection_trace(module_id="A-T", run_id="run-1", specs=(spec,), evaluations_by_fit=by_fit)
    winners = [r["candidate_id"] for r in records if r["selected"]]
    assert winners == ["a"]


def test_fixed_vs_shared_equal_weight_aggregates_per_core_n():
    keys_a = (SupportKey(5, 420101), SupportKey(5, 420102), SupportKey(10, 420101), SupportKey(10, 420102))
    keys_b = (SupportKey(5, 420101), SupportKey(5, 420102), SupportKey(10, 420101), SupportKey(10, 420102))
    spec = _decision("output_form:A-T:stem", ["joint", "independent"], keys_a,
                     rule=SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT, axis="output_form")
    spec = DecisionSpec(module_id="A-T", decision_id="output_form:A-T:stem", axis="output_form",
                        selection_rule=SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT,
                        candidates=(spec.candidates[0], _candidate("output_form:A-T:stem", "independent", keys_b, rule=SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT)))
    # joint: n5 mean=0.10, n10 mean=0.12 => equal-weight 0.11; independent: n5=0.20,n10=0.12 => 0.16
    joint = {SupportKey(5, 420101): 0.10, SupportKey(5, 420102): 0.10, SupportKey(10, 420101): 0.12, SupportKey(10, 420102): 0.12}
    indep = {SupportKey(5, 420101): 0.20, SupportKey(5, 420102): 0.20, SupportKey(10, 420101): 0.12, SupportKey(10, 420102): 0.12}
    by_fit = {}
    for key, score in joint.items():
        by_fit[spec.candidates[0].fit_id_by_support[key]] = _eval(spec.candidates[0], key, score)
    for key, score in indep.items():
        by_fit[spec.candidates[1].fit_id_by_support[key]] = _eval(spec.candidates[1], key, score)
    records = build_selection_trace(module_id="A-T", run_id="run-1", specs=(spec,), evaluations_by_fit=by_fit)
    by_cand = {r["candidate_id"]: r for r in records}
    assert by_cand["joint"]["validation_score"] == pytest.approx(0.11)
    assert by_cand["independent"]["validation_score"] == pytest.approx(0.16)
    assert [r["candidate_id"] for r in records if r["selected"]] == ["joint"]


# --------------------------------------------------------------------------
# Supporting-evidence hash + attack surface.
# --------------------------------------------------------------------------


def test_supporting_evidence_hash_binds_full_context():
    keys = (SupportKey(10, 420101), SupportKey(10, 420102))
    cand = _candidate("d:A-T:r:n10", "a", keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    evals = _evals_for(cand, {keys[0]: 0.1, keys[1]: 0.2})
    base = candidate_supporting_evidence(module_id="A-T", run_id="run-1", candidate=cand, evaluations_by_support=evals)
    # changing any bound context field changes the hash
    assert candidate_supporting_evidence(module_id="A-X", run_id="run-1", candidate=cand, evaluations_by_support=evals)["supporting_evidence_sha256"] != base["supporting_evidence_sha256"]
    assert candidate_supporting_evidence(module_id="A-T", run_id="run-2", candidate=cand, evaluations_by_support=evals)["supporting_evidence_sha256"] != base["supporting_evidence_sha256"]
    other_cand = _candidate("d:A-T:r:n10", "b", keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    other_evals = {keys[0]: _eval(other_cand, keys[0], 0.1), keys[1]: _eval(other_cand, keys[1], 0.2)}
    assert candidate_supporting_evidence(module_id="A-T", run_id="run-1", candidate=other_cand, evaluations_by_support=other_evals)["supporting_evidence_sha256"] != base["supporting_evidence_sha256"]
    other_decision = _candidate("other:A-T:r:n10", "a", keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    other_decision_evals = {keys[0]: _eval(other_decision, keys[0], 0.1), keys[1]: _eval(other_decision, keys[1], 0.2)}
    assert candidate_supporting_evidence(module_id="A-T", run_id="run-1", candidate=other_decision, evaluations_by_support=other_decision_evals)["supporting_evidence_sha256"] != base["supporting_evidence_sha256"]
    # tampering a checkpoint sha on a supporting row changes the hash
    tampered = {keys[0]: FitEvaluation(fit_id=cand.fit_id_by_support[keys[0]], support_key=keys[0], failed=False,
                                       checkpoint_sha256="b" * 64, selection_score=0.1, failure_penalty=0.0), keys[1]: evals[keys[1]]}
    assert candidate_supporting_evidence(module_id="A-T", run_id="run-1", candidate=cand, evaluations_by_support=tampered)["supporting_evidence_sha256"] != base["supporting_evidence_sha256"]


def test_point_evidence_sha256_is_order_independent_and_tamper_sensitive():
    records = _point_records(420101, 0.1)
    h1 = point_evidence_sha256(records)
    h2 = point_evidence_sha256(list(reversed(records)))
    assert h1 == h2
    tampered = [{**records[0], "l_param": records[0]["l_param"] + 0.5, "e_beta": records[0]["e_beta"] + 0.5,
                 "e_eta": records[0]["e_eta"] + 0.5, "e_gamma": records[0]["e_gamma"] + 0.5}] + records[1:]
    assert point_evidence_sha256(tampered) != h1


def test_missing_support_fit_fails_closed():
    keys = (SupportKey(10, 420101), SupportKey(10, 420102))
    cand = _candidate("d:A-T:r:n10", "a", keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    partial = _evals_for(cand, {keys[0]: 0.1})  # missing one support
    with pytest.raises(ValueError, match="missing"):
        candidate_supporting_evidence(module_id="A-T", run_id="run-1", candidate=cand, evaluations_by_support=partial)


def test_extra_support_fit_fails_closed():
    keys = (SupportKey(10, 420101), SupportKey(10, 420102))
    cand = _candidate("d:A-T:r:n10", "a", keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    extra = _evals_for(cand, {keys[0]: 0.1, keys[1]: 0.2})
    extra_key = SupportKey(10, 999999)
    extra[extra_key] = _standalone_eval("extra-fit", extra_key, 0.3)
    with pytest.raises(ValueError, match="extra"):
        candidate_supporting_evidence(module_id="A-T", run_id="run-1", candidate=cand, evaluations_by_support=extra)


def test_wrong_n_or_seed_support_fails_closed():
    keys = (SupportKey(10, 420101), SupportKey(10, 420102))
    cand = _candidate("d:A-T:r:n10", "a", keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    wrong_key = SupportKey(15, 420101)  # wrong n
    wrong = {wrong_key: _standalone_eval("wrong-n-fit", wrong_key, 0.1), keys[1]: _eval(cand, keys[1], 0.2)}
    with pytest.raises(ValueError):
        candidate_supporting_evidence(module_id="A-T", run_id="run-1", candidate=cand, evaluations_by_support=wrong)


def test_support_evaluation_keyed_by_wrong_fit_id_fails_closed():
    keys = (SupportKey(10, 420101),)
    cand = CandidateSpec(decision_id="d:A-T:r:n10", candidate_id="a", selection_rule=SELECTION_RULE_LOWEST_AGGREGATE,
                         tie_break_key=("a",), support_keys=keys, expected_fit_ids=("expected-fit-0001",),
                         fit_id_by_support={keys[0]: "expected-fit-0001"}, approved_seeds=(420101,))
    rogue = FitEvaluation(fit_id="rogue-fit", support_key=keys[0], failed=False, checkpoint_sha256="a" * 64,
                          selection_score=0.1, failure_penalty=0.0)
    with pytest.raises(ValueError, match="disagrees with frozen expected"):
        candidate_supporting_evidence(module_id="A-T", run_id="run-1", candidate=cand, evaluations_by_support={keys[0]: rogue})


def test_cross_candidate_fit_reuse_fails_closed():
    keys = (SupportKey(10, 420101),)
    spec = _decision("d:A-T:r:n10", ["a", "b"], keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    shared_fit = FitEvaluation(fit_id="shared-fit", support_key=keys[0], failed=False,
                               checkpoint_sha256="a" * 64, selection_score=0.1, failure_penalty=0.0)
    # Both candidates claim the SAME fit_id -> reuse must fail.
    evals = {
        spec.candidates[0].candidate_id: {keys[0]: FitEvaluation(fit_id="shared-fit", support_key=keys[0], failed=False, checkpoint_sha256="a" * 64, selection_score=0.1, failure_penalty=0.0)},
        spec.candidates[1].candidate_id: {keys[0]: FitEvaluation(fit_id="shared-fit", support_key=keys[0], failed=False, checkpoint_sha256="a" * 64, selection_score=0.2, failure_penalty=0.0)},
    }
    by_fit = {e.fit_id: e for cid in evals for e in evals[cid].values()}
    # Force candidate support_for to point at the shared fit id so the reuse is detectable.
    spec = _decision("d:A-T:r:n10", ["a", "b"], keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    spec = DecisionSpec(module_id="A-T", decision_id="d:A-T:r:n10", axis="architecture",
                        selection_rule=SELECTION_RULE_LOWEST_AGGREGATE, candidates=(
                            CandidateSpec(decision_id="d:A-T:r:n10", candidate_id="a", selection_rule=SELECTION_RULE_LOWEST_AGGREGATE,
                                          tie_break_key=("a",), support_keys=keys, expected_fit_ids=("shared-fit",),
                                          fit_id_by_support={keys[0]: "shared-fit"}, approved_seeds=(420101,)),
                            CandidateSpec(decision_id="d:A-T:r:n10", candidate_id="b", selection_rule=SELECTION_RULE_LOWEST_AGGREGATE,
                                          tie_break_key=("b",), support_keys=keys, expected_fit_ids=("shared-fit",),
                                          fit_id_by_support={keys[0]: "shared-fit"}, approved_seeds=(420101,)),
                        ))
    by_fit = {"shared-fit": FitEvaluation(fit_id="shared-fit", support_key=keys[0], failed=False, checkpoint_sha256="a" * 64, selection_score=0.1, failure_penalty=0.0)}
    with pytest.raises(ValueError, match="two selection candidates"):
        build_selection_trace(module_id="A-T", run_id="run-1", specs=(spec,), evaluations_by_fit=by_fit)


def test_missing_bound_evaluation_for_expected_fit_fails_closed():
    keys = (SupportKey(10, 420101),)
    spec = _decision("d:A-T:r:n10", ["a"], keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    with pytest.raises(ValueError, match="missing bound evaluation"):
        build_selection_trace(module_id="A-T", run_id="run-1", specs=(spec,), evaluations_by_fit={})


def test_winner_is_never_caller_supplied():
    # build_selection_trace takes no winner argument at all; the signature enforces it.
    import inspect
    params = inspect.signature(build_selection_trace).parameters
    assert "winner" not in params and "selected_candidate_id" not in params
