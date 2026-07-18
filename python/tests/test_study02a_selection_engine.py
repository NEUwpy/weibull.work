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
    compute_point_evidence_sha256,
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


def _eval(candidate, support_key, score, *, failed=False, point_records=(), fit_id=None,
          validation_identity="val-cache-A"):
    fit_id = fit_id if fit_id is not None else candidate.fit_id_by_support[support_key]
    return FitEvaluation(
        fit_id=fit_id, module_id="A-T", decision_id=candidate.decision_id,
        candidate_id=candidate.candidate_id, support_key=support_key, failed=failed,
        checkpoint_sha256="" if failed else "a" * 64, validation_identity=validation_identity,
        selection_score=score if not failed else 0.0,
        failure_penalty=10.0 if failed else 0.0,
        point_records=tuple(point_records),
    )


def _standalone_eval(fit_id, support_key, score, *, decision_id="d:A-T:r:n10", candidate_id="a"):
    return FitEvaluation(fit_id=fit_id, module_id="A-T", decision_id=decision_id,
                         candidate_id=candidate_id, support_key=support_key, failed=False,
                         checkpoint_sha256="a" * 64, validation_identity="val-cache-A",
                         selection_score=score, failure_penalty=0.0)


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
    records, _diag = build_selection_trace(module_id="A-T", run_id="run-1", specs=(spec,), evaluations_by_fit=by_fit)
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
    records, _diag = build_selection_trace(module_id="A-T", run_id="run-1", specs=(spec,), evaluations_by_fit=by_fit)
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
    kwargs = dict(fit_id="fit-a", module_id="A-T", decision_id="d:A-T:r:n10", candidate_id="a",
                  support_key=SupportKey(10, 420101), checkpoint_sha256="a" * 64,
                  validation_identity="val-cache-A", failed=False)
    h1 = compute_point_evidence_sha256(point_records=records, **kwargs)
    h2 = compute_point_evidence_sha256(point_records=list(reversed(records)), **kwargs)
    assert h1 == h2
    tampered = [{**records[0], "l_param": records[0]["l_param"] + 0.5, "e_beta": records[0]["e_beta"] + 0.5,
                 "e_eta": records[0]["e_eta"] + 0.5, "e_gamma": records[0]["e_gamma"] + 0.5}] + records[1:]
    assert compute_point_evidence_sha256(point_records=tampered, **kwargs) != h1


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


# --------------------------------------------------------------------------
# Additional attack-surface coverage (R2 / contract attack list).
# --------------------------------------------------------------------------


def test_identical_fits_under_two_candidates_get_distinct_supporting_hashes():
    # R2 #3: the supporting_evidence_sha256 binds candidate_id, so two candidates that
    # bind the SAME checkpoint/score still get distinct hashes.
    keys = (SupportKey(10, 420101),)
    cand_a = _candidate("d:A-T:r:n10", "a", keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    cand_b = _candidate("d:A-T:r:n10", "b", keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    ev_a = candidate_supporting_evidence(module_id="A-T", run_id="r1", candidate=cand_a, evaluations_by_support=_evals_for(cand_a, {keys[0]: 0.1}))
    ev_b = candidate_supporting_evidence(module_id="A-T", run_id="r1", candidate=cand_b, evaluations_by_support=_evals_for(cand_b, {keys[0]: 0.1}))
    assert ev_a["supporting_evidence_sha256"] != ev_b["supporting_evidence_sha256"]


def test_mixed_selection_rule_within_one_decision_is_rejected(tmp_path):
    # Contract E: a decision's selection_rule must be unique. Hand-build a trace where two
    # candidates of one decision carry different rules; write_selection_trace must reject it.
    from study02a.formal_contracts import write_selection_trace
    keys = (SupportKey(10, 420101),)
    cand_a = _candidate("d:A-T:r:n10", "a", keys, rule=SELECTION_RULE_LOWEST_AGGREGATE)
    ev = candidate_supporting_evidence(module_id="A-T", run_id="r1", candidate=cand_a,
                                       evaluations_by_support=_evals_for(cand_a, {keys[0]: 0.1}))
    records = [{
        "module_id": "A-T", "run_id": "r1", "decision_id": "d:A-T:r:n10", "candidate_id": "a",
        "validation_score": ev["aggregate_score"], "tie_break_key": ["a"], "selected": True,
        "supporting_evidence_sha256": ev["supporting_evidence_sha256"],
        "rule_diagnostics_sha256": "a" * 64,
        "support_count": 1, "seed_count": 1, "selection_rule": SELECTION_RULE_LOWEST_AGGREGATE,
    }, {
        "module_id": "A-T", "run_id": "r1", "decision_id": "d:A-T:r:n10", "candidate_id": "b",
        "validation_score": ev["aggregate_score"], "tie_break_key": ["b"], "selected": False,
        "supporting_evidence_sha256": ev["supporting_evidence_sha256"],
        "rule_diagnostics_sha256": "a" * 64,
        "support_count": 1, "seed_count": 1, "selection_rule": SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT,  # mixed!
    }]
    with pytest.raises(ValueError, match="mixes selection rules"):
        write_selection_trace(tmp_path / "mixed.jsonl", records)


def _global_better_spec_and_evals():
    """Two candidates, global_better rule, per-point evidence where NEITHER globally
    dominates (each wins one parameter point) so the rule falls back to lowest L_param."""
    keys = (SupportKey(10, 420101),)
    cand_a = CandidateSpec(decision_id="distribution:A-T:base", candidate_id="legacy", selection_rule=SELECTION_RULE_GLOBAL_BETTER,
                           tie_break_key=("legacy",), support_keys=keys, expected_fit_ids=("fit-legacy",),
                           fit_id_by_support={keys[0]: "fit-legacy"}, approved_seeds=(420101,))
    cand_b = CandidateSpec(decision_id="distribution:A-T:base", candidate_id="core", selection_rule=SELECTION_RULE_GLOBAL_BETTER,
                           tie_break_key=("core",), support_keys=keys, expected_fit_ids=("fit-core",),
                           fit_id_by_support={keys[0]: "fit-core"}, approved_seeds=(420101,))
    spec = DecisionSpec(module_id="A-T", decision_id="distribution:A-T:base", axis="distribution",
                        selection_rule=SELECTION_RULE_GLOBAL_BETTER, candidates=(cand_a, cand_b))
    # legacy wins pt0, core wins pt1 => neither globally dominates. legacy has lower mean.
    legacy_points = [
        {"sample_id": "pt0:s0", "seed_id": "420101", "point_id": "pt0", "legal": True, "failure": 0, "l_param": 0.10, "e_beta": 0.10, "e_eta": 0.10, "e_gamma": 0.10},
        {"sample_id": "pt1:s0", "seed_id": "420101", "point_id": "pt1", "legal": True, "failure": 0, "l_param": 0.30, "e_beta": 0.30, "e_eta": 0.30, "e_gamma": 0.30},
    ]
    core_points = [
        {"sample_id": "pt0:s0", "seed_id": "420101", "point_id": "pt0", "legal": True, "failure": 0, "l_param": 0.20, "e_beta": 0.20, "e_eta": 0.20, "e_gamma": 0.20},
        {"sample_id": "pt1:s0", "seed_id": "420101", "point_id": "pt1", "legal": True, "failure": 0, "l_param": 0.15, "e_beta": 0.15, "e_eta": 0.15, "e_gamma": 0.15},
    ]
    evals = {
        "fit-legacy": FitEvaluation(fit_id="fit-legacy", support_key=keys[0], failed=False, checkpoint_sha256="a"*64, selection_score=0.20, failure_penalty=0.0, point_records=tuple(legacy_points)),
        "fit-core": FitEvaluation(fit_id="fit-core", support_key=keys[0], failed=False, checkpoint_sha256="b"*64, selection_score=0.175, failure_penalty=0.0, point_records=tuple(core_points)),
    }
    return spec, evals


def test_global_better_falls_back_to_lowest_l_param_when_no_global_winner():
    spec, evals = _global_better_spec_and_evals()
    records, _diag = build_selection_trace(module_id="A-T", run_id="r1", specs=(spec,), evaluations_by_fit=evals)
    winner = next(r["candidate_id"] for r in records if r["selected"])
    # Neither globally dominates => fallback to lowest mean penalized L_param (legacy 0.20 > core 0.175
    # is NOT the metric here -- aggregate uses mean l_param: legacy 0.20 vs core 0.175 => core lower).
    assert winner == "core"


def test_global_better_winner_when_one_globally_dominates():
    keys = (SupportKey(10, 420101),)
    cand_dom = CandidateSpec(decision_id="distribution:A-T:base", candidate_id="dom", selection_rule=SELECTION_RULE_GLOBAL_BETTER,
                             tie_break_key=("dom",), support_keys=keys, expected_fit_ids=("fit-dom",),
                             fit_id_by_support={keys[0]: "fit-dom"}, approved_seeds=(420101,))
    cand_lose = CandidateSpec(decision_id="distribution:A-T:base", candidate_id="lose", selection_rule=SELECTION_RULE_GLOBAL_BETTER,
                              tie_break_key=("lose",), support_keys=keys, expected_fit_ids=("fit-lose",),
                              fit_id_by_support={keys[0]: "fit-lose"}, approved_seeds=(420101,))
    spec = DecisionSpec(module_id="A-T", decision_id="distribution:A-T:base", axis="distribution",
                        selection_rule=SELECTION_RULE_GLOBAL_BETTER, candidates=(cand_dom, cand_lose))
    dom_points = [
        {"sample_id": f"pt{p}:s{s}", "seed_id": "420101", "point_id": f"pt{p}", "legal": True, "failure": 0, "l_param": 0.05, "e_beta": 0.05, "e_eta": 0.05, "e_gamma": 0.05}
        for p in range(3) for s in range(2)
    ]
    lose_points = [
        {"sample_id": f"pt{p}:s{s}", "seed_id": "420101", "point_id": f"pt{p}", "legal": True, "failure": 0, "l_param": 0.20, "e_beta": 0.20, "e_eta": 0.20, "e_gamma": 0.20}
        for p in range(3) for s in range(2)
    ]
    evals = {
        "fit-dom": FitEvaluation(fit_id="fit-dom", support_key=keys[0], failed=False, checkpoint_sha256="a"*64, selection_score=0.05, failure_penalty=0.0, point_records=tuple(dom_points)),
        "fit-lose": FitEvaluation(fit_id="fit-lose", support_key=keys[0], failed=False, checkpoint_sha256="b"*64, selection_score=0.20, failure_penalty=0.0, point_records=tuple(lose_points)),
    }
    records, _diag = build_selection_trace(module_id="A-T", run_id="r1", specs=(spec,), evaluations_by_fit=evals)
    assert next(r["candidate_id"] for r in records if r["selected"]) == "dom"


def test_duplicate_support_seed_within_a_candidate_fails_closed():
    # build_decision_specs rejects a matrix that maps two fits of one candidate to the
    # same (n, seed) support key (the frozen matrix never does this).
    def _row(fit_id, arch, seed):
        return {"fit_id": fit_id, "rule_id": "A-E1_optimized_supplement", "module": "A-E1",
                "route": "F2", "n": 10, "loss": "transformed_train_z_huber", "architecture": arch,
                "optimizer": "stage1", "training_size": 100000, "seed": seed, "fit_kind": "search_stage1",
                "test_state": "sealed"}
    # two rows for the same architecture candidate at the same (n=10, seed) => duplicate support
    dup_matrix = [_row("G3-fit-9000", "m01", 420001), _row("G3-fit-9001", "m01", 420001)]
    with pytest.raises(ValueError, match="duplicate support"):
        build_decision_specs("A-E1", dup_matrix)


def test_failed_seed_is_included_in_global_better_rule():
    # R3#6: a failed seed is NOT silently skipped. Candidate A is all-legal with low L_param;
    # candidate B has a failed seed (all-illegal records over the same cells). The failure
    # rate / L_param / RMSE CIs therefore truly include the failure, so A globally dominates B.
    keys = (SupportKey(10, 420101),)
    cand_a = CandidateSpec(decision_id="distribution:A-T:base", candidate_id="good", selection_rule=SELECTION_RULE_GLOBAL_BETTER,
                           tie_break_key=("good",), support_keys=keys, expected_fit_ids=("fit-good",),
                           fit_id_by_support={keys[0]: "fit-good"}, approved_seeds=(420101,))
    cand_b = CandidateSpec(decision_id="distribution:A-T:base", candidate_id="flaky", selection_rule=SELECTION_RULE_GLOBAL_BETTER,
                           tie_break_key=("flaky",), support_keys=keys, expected_fit_ids=("fit-flaky",),
                           fit_id_by_support={keys[0]: "fit-flaky"}, approved_seeds=(420101,))
    spec = DecisionSpec(module_id="A-T", decision_id="distribution:A-T:base", axis="distribution",
                        selection_rule=SELECTION_RULE_GLOBAL_BETTER, candidates=(cand_a, cand_b))
    good_points = [
        {"sample_id": f"pt{p}:s{s}", "seed_id": "420101", "point_id": f"pt{p}", "legal": True, "failure": 0,
         "l_param": 0.05, "e_beta": 0.05, "e_eta": 0.05, "e_gamma": 0.05}
        for p in range(3) for s in range(2)
    ]
    # flaky candidate: the seed failed => every validation cell is illegal (penalty 10).
    flaky_points = [
        {"sample_id": f"pt{p}:s{s}", "seed_id": "420101", "point_id": f"pt{p}", "legal": False, "failure": 1,
         "l_param": 10.0, "e_beta": 10.0, "e_eta": 10.0, "e_gamma": 10.0}
        for p in range(3) for s in range(2)
    ]
    evals = {
        "fit-good": FitEvaluation(fit_id="fit-good", module_id="A-T", decision_id="distribution:A-T:base",
                                  candidate_id="good", support_key=keys[0], failed=False, checkpoint_sha256="a" * 64,
                                  validation_identity="val-A", selection_score=0.05, failure_penalty=0.0, point_records=tuple(good_points)),
        "fit-flaky": FitEvaluation(fit_id="fit-flaky", module_id="A-T", decision_id="distribution:A-T:base",
                                   candidate_id="flaky", support_key=keys[0], failed=True, checkpoint_sha256="",
                                   validation_identity="val-B", selection_score=0.0, failure_penalty=10.0, point_records=tuple(flaky_points)),
    }
    records, diagnostics = build_selection_trace(module_id="A-T", run_id="r1", specs=(spec,), evaluations_by_fit=evals)
    winner = next(r["candidate_id"] for r in records if r["selected"])
    assert winner == "good"  # the flaky candidate's failure is included => it cannot dominate
    diag = next(d for d in diagnostics if d["decision_id"] == "distribution:A-T:base")
    # good vs flaky: good has lower failure rate => non-inferior; good dominates on all 3 CIs.
    verdict = diag["rule_result"]["verdicts"]["good>vs>flaky"]
    assert verdict == "globally_better"
