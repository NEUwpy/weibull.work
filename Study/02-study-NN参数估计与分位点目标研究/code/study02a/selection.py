"""D7 selection DecisionSpec engine for Study/02 formal modules.

A :class:`DecisionSpec` is the single deterministic source of truth for one
selection decision. It is derived ONLY from the frozen experiment matrix and the
frozen config (the pre-registered plan) -- never from the actual run's
``fit_status`` outcome rows. It fixes, per candidate:

* ``decision_id`` / ``candidate_id`` identity,
* the exact ``expected_fit_ids`` (one per supporting ``(n, seed)`` cell),
* the ``support_keys`` (the ``(n, seed)`` grid a candidate must cover),
* the ``approved_seeds`` (from the frozen matrix plan),
* the ``selection_rule``, aggregation, weighting and ``tie_break_key``.

The caller CANNOT supply expected fits, approved seeds, a winner, or a rule --
those are all derived. :func:`build_decision_specs` is called twice: once when
publishing a selection (with the actual fit outcomes bound as a separate verified
overlay) and once independently at pre-unseal; the two derivations must agree
exactly, which is what makes "expected seeds/fits derived from actual rows"
(R2 #1) impossible -- the expected set is the frozen plan, rebuilt afresh each
time, and the actual rows must conform to it.

Scope (relay 2026-07-18): the decision-rule ENGINE -- deterministic spec
derivation, the four frozen selection rules, supporting-evidence aggregation and
winner selection. The staged A-E1 execution (stage1 -> immutable artifacts ->
selected_top -> stage2 -> one final receipt) and D8 (placeholder resolution /
deferred-spec reconstruction / predecessor chain) are explicitly out of scope
and remain fail-closed in ``formal_executor``. No formal training is launched;
all evidence here is synthetic/small in tests.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Mapping, Sequence

from .evaluation import (
    POINT_RECORD_FIELDS,
    global_better_intervals,
    paired_two_level_bootstrap_ci,
    smallest_within_2pct_ci_choice,
    validate_canonical_point_records,
)
from .formal_contracts import (
    SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT,
    SELECTION_RULE_GLOBAL_BETTER,
    SELECTION_RULE_LOWEST_AGGREGATE,
    SELECTION_RULE_SMALLEST_WITHIN_2PCT_CI,
)


# --------------------------------------------------------------------------
# Frozen decision-axis -> (selection_rule, tie-break fields) table.
#
# This mapping is the deterministic authority that turns the human-language
# "selection" clauses in configs/A-g2-search-v1.json module_matrix_rules into a
# machine rule + tie-break per decision axis. It is a frozen constant: a module's
# decision gets exactly one rule, decided by its axis, with no caller input.
# --------------------------------------------------------------------------
_AXIS_RULE: dict[str, tuple[str, tuple[str, ...]]] = {
    "architecture": (SELECTION_RULE_LOWEST_AGGREGATE, ("candidate",)),
    "stage2": (SELECTION_RULE_LOWEST_AGGREGATE, ("candidate",)),
    "loss": (SELECTION_RULE_LOWEST_AGGREGATE, ("candidate",)),
    # output_form (joint vs independent) and n_strategy (fixed vs shared): core-n
    # equal-weight aggregation (02-A / module_matrix_rules capacity clause).
    "output_form": (SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT, ("candidate",)),
    "n_strategy": (SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT, ("candidate",)),
    "training_size": (SELECTION_RULE_SMALLEST_WITHIN_2PCT_CI, ("candidate",)),
    # A-E1 baseline (F2 vs V) and A-E2 distribution: global_better_rule, falling
    # back to lowest penalized L_param with an id tie-break (module_matrix_rules).
    "distribution": (SELECTION_RULE_GLOBAL_BETTER, ("candidate",)),
    "baseline_input": (SELECTION_RULE_GLOBAL_BETTER, ("candidate",)),
}

# fit_kind -> decision axis. Only screening/search fit_kinds are competitive
# candidates; historical / controlled / *_retrain fits are singletons or
# downstream applications and derive no decision here.
_FIT_KIND_AXIS: dict[str, str] = {
    "search_stage1": "architecture",
    "search_stage2": "stage2",
    "loss_screen": "loss",
    "output_form": "output_form",
    "size_screen": "training_size",
    "distribution_screen": "distribution",
}


@dataclass(frozen=True)
class SupportKey:
    """One supporting fit's ``(n, seed)`` scope -- the multi-n supporting key.

    ``n`` is a core sample-size int, or the string ``"shared"`` for shared-n
    (DeepSets / historical) models. Two candidates of the same decision share the
    same support grid, so their per-support evidence is pairable on this key.
    """

    n: int | str
    seed: int

    def as_json(self) -> list[Any]:
        return [self.n, int(self.seed)]


@dataclass(frozen=True)
class CandidateSpec:
    """One candidate of one decision, fully determined by the frozen matrix.

    ``support_keys`` and ``expected_fit_ids`` are parallel and both sorted by
    ``(n, seed)``; ``expected_fit_ids`` is the exact frozen-plan fit set the
    candidate must cover -- the actual run's ``fit_status`` rows must conform to
    it, never the reverse. ``approved_seeds`` is the seed set of the frozen
    support plan (== the frozen pool for the decision's seed role).
    """

    decision_id: str
    candidate_id: str
    selection_rule: str
    tie_break_key: tuple[Any, ...]
    support_keys: tuple[SupportKey, ...]
    expected_fit_ids: tuple[str, ...]
    fit_id_by_support: Mapping[SupportKey, str] = field(default_factory=dict)
    approved_seeds: tuple[int, ...] = ()

    def support_for(self, support_key: SupportKey) -> str:
        try:
            return self.fit_id_by_support[support_key]
        except KeyError as exc:  # pragma: no cover - defensive, spec is self-consistent
            raise ValueError(
                f"candidate {self.candidate_id} has no expected fit for support {support_key!r}"
            ) from exc


@dataclass(frozen=True)
class DecisionSpec:
    """One decision: its frozen rule, tie-break and its candidate specs."""

    module_id: str
    decision_id: str
    axis: str
    selection_rule: str
    candidates: tuple[CandidateSpec, ...]

    @property
    def tie_break_key(self) -> tuple[str, ...]:
        return _AXIS_RULE[self.axis][1]


_POINT_RECORD_FIELDS = POINT_RECORD_FIELDS  # canonical field authority lives in evaluation.py


def _canonical_point_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return {field: record[field] for field in _POINT_RECORD_FIELDS if field in record}


def compute_point_evidence_sha256(
    *, fit_id: str, module_id: str, decision_id: str, candidate_id: str,
    support_key: SupportKey, checkpoint_sha256: str, validation_identity: str,
    failed: bool, point_records: Sequence[Mapping[str, Any]],
) -> str:
    """Canonical SHA-256 of one supporting fit's per-parameter-point evidence (R3#1).

    Binds the full immutable identity (fit/decision/candidate/n/seed), the checkpoint
    SHA, the validation cache/data identity (which validation set the points were
    scored on), the failed flag and the canonical per-sample point records. A swapped
    point-evidence artifact (fit A's records under fit B's identity) or any tampered
    record/checkpoint/validation-set changes this digest, and (because it is bound into
    ``supporting_evidence_sha256``) the whole selection chain fails closed. Records are
    semantically validated (R4#2: structure + per-record semantics, bound to the frozen
    support seed) and sorted by ``(seed_id, sample_id)`` so the digest is order-independent.
    """
    records = validate_canonical_point_records(point_records, support_seed=int(support_key.seed))
    canonical_records = sorted(
        (_canonical_point_record(record) for record in records),
        key=lambda r: (str(r["seed_id"]), str(r["sample_id"])),
    )
    payload = _canonical({
        "fit_id": fit_id, "module_id": module_id, "decision_id": decision_id,
        "candidate_id": candidate_id, "n": support_key.n, "seed": int(support_key.seed),
        "checkpoint_sha256": checkpoint_sha256, "validation_identity": validation_identity,
        "failed": bool(failed), "point_records": canonical_records,
    })
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class FitEvaluation:
    """A fit's bound evaluation evidence (the only run-derived input).

    Produced by scoring an integrity-bound checkpoint on its validation cache:
    ``selection_score`` is the mean failure-penalized ``L_param``; ``point_records``
    are the per-validation-sample records (stable pairing ids) the CI rules consume.
    ``checkpoint_sha256`` binds the evidence to the exact trained checkpoint;
    ``validation_identity`` binds the validation cache/data the points were scored on.
    A FAILED fit carries no checkpoint but still carries ``point_records`` -- the
    all-illegal records over its validation cell set -- so failure rate, ``L_param``
    and pairing truly include the failed seed (R3#6); ``failed`` is True and
    ``checkpoint_sha256`` is empty. ``point_evidence_sha256`` (R3#1) binds all of the
    above into the immutable evidence chain.
    """

    fit_id: str
    support_key: SupportKey
    failed: bool
    checkpoint_sha256: str
    selection_score: float
    failure_penalty: float
    module_id: str = ""
    decision_id: str = ""
    candidate_id: str = ""
    validation_identity: str = ""
    point_records: tuple[Mapping[str, Any], ...] = ()

    def point_evidence_sha256(self) -> str:
        return compute_point_evidence_sha256(
            fit_id=self.fit_id, module_id=self.module_id, decision_id=self.decision_id,
            candidate_id=self.candidate_id, support_key=self.support_key,
            checkpoint_sha256=self.checkpoint_sha256, validation_identity=self.validation_identity,
            failed=self.failed, point_records=self.point_records,
        )


# --------------------------------------------------------------------------
# Decision derivation (deterministic from the frozen matrix).
# --------------------------------------------------------------------------


def _n_key(row: Mapping[str, Any]) -> int | str:
    raw = row["n"]
    if raw == "shared":
        return "shared"
    return int(raw)


def _candidate_and_scope(axis: str, row: Mapping[str, Any]) -> tuple[str, str]:
    """Return ``(candidate_id, decision_scope)`` for one matrix row's axis.

    The scope is the held-constant coordinate signature (everything that does not
    vary across the decision's candidates); the candidate is the varying axis
    value. Both are derived from the frozen row fields only.
    """
    module = str(row["module"])
    route = str(row["route"])
    n = _n_key(row)
    n_part = "shared" if n == "shared" else f"n{n}"
    if axis in ("architecture", "stage2", "loss"):
        return str(row["architecture" if axis != "loss" else "loss"]) if axis != "stage2" else f"{row['architecture']}:{row['optimizer']}", f"{module}:{route}:{n_part}"
    if axis == "output_form":
        # route is "...:{output_form}"; scope is the stem, candidate is the suffix.
        stem, _, candidate = route.rpartition(":")
        return candidate, f"{module}:{stem}"
    if axis == "training_size":
        return str(row["training_size"]), f"{module}:{route}"
    if axis == "distribution":
        stem, _, candidate = route.rpartition(":")
        return candidate, f"{module}:{stem}"
    raise ValueError(f"unsupported decision axis {axis!r}")


def build_decision_specs(
    module_id: str, matrix_rows: Sequence[Mapping[str, Any]]
) -> tuple[DecisionSpec, ...]:
    """Deterministically derive every selection decision of one module.

    ``matrix_rows`` is the frozen experiment matrix subset (or the full 820 rows;
    non-matching modules are ignored). Only screening/search fit_kinds become
    decisions; the candidate support grid and exact expected fit ids come from the
    frozen rows. The same input always yields the same specs (independent of any
    run outcome), so pre-unseal rebuilds an identical authority.
    """
    grouped: dict[tuple[str, str], dict[str, list[Mapping[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in matrix_rows:
        if str(row["module"]) != module_id:
            continue
        fit_kind = str(row["fit_kind"])
        axis = _FIT_KIND_AXIS.get(fit_kind)
        if axis is None:
            continue  # not a competitive search candidate
        candidate, scope = _candidate_and_scope(axis, row)
        grouped[(axis, scope)][candidate].append(row)

    specs: list[DecisionSpec] = []
    for (axis, scope), candidates_map in sorted(grouped.items()):
        rule = _AXIS_RULE[axis][0]
        decision_id = f"{axis}:{scope}"
        candidate_specs: list[CandidateSpec] = []
        for candidate_id in sorted(candidates_map):
            rows = candidates_map[candidate_id]
            support_to_fit: dict[SupportKey, str] = {}
            for row in rows:
                key = SupportKey(n=_n_key(row), seed=int(row["seed"]))
                fit_id = str(row["fit_id"])
                if key in support_to_fit:
                    raise ValueError(
                        f"duplicate support {key!r} for {decision_id}/{candidate_id} in frozen matrix"
                    )
                support_to_fit[key] = fit_id
            support_keys = tuple(sorted(support_to_fit, key=lambda k: (str(k.n), int(k.seed))))
            expected_fit_ids = tuple(support_to_fit[key] for key in support_keys)
            approved_seeds = tuple(sorted({int(key.seed) for key in support_keys}))
            candidate_specs.append(CandidateSpec(
                decision_id=decision_id, candidate_id=candidate_id, selection_rule=rule,
                tie_break_key=(candidate_id,), support_keys=support_keys,
                expected_fit_ids=expected_fit_ids, fit_id_by_support=support_to_fit,
                approved_seeds=approved_seeds,
            ))
        specs.append(DecisionSpec(
            module_id=module_id, decision_id=decision_id, axis=axis, selection_rule=rule,
            candidates=tuple(candidate_specs),
        ))
    return tuple(specs)


# --------------------------------------------------------------------------
# Supporting-evidence aggregation + canonical hashing.
# --------------------------------------------------------------------------


def _canonical(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _equal_weight_per_n_aggregate(evaluations: Sequence[FitEvaluation]) -> float:
    """Core-n equal-weight mean failure-penalized L_param (fixed-vs-shared / output_form).

    Mean over seeds within each n, then equal weight across n. This is the frozen
    "core n 等权聚合" aggregation (02-A / module_matrix_rules capacity clause): a
    candidate is not rewarded just because more seeds ran at one n.
    """
    by_n: dict[Any, list[float]] = defaultdict(list)
    for evaluation in evaluations:
        value = float(evaluation.failure_penalty) if evaluation.failed else float(evaluation.selection_score)
        by_n[evaluation.support_key.n].append(value)
    if not by_n:
        raise ValueError("equal-weight aggregate requires at least one supporting fit")
    per_n_means = [sum(values) / len(values) for values in by_n.values()]
    return sum(per_n_means) / len(per_n_means)


def _validate_evaluation_finite(evaluation: "FitEvaluation") -> None:
    """R6 fail-closed: every numeric field in a FitEvaluation must be finite before aggregation."""
    if evaluation.failed:
        if not math.isfinite(float(evaluation.failure_penalty)):
            raise ValueError(
                f"fit {evaluation.fit_id!r} failure_penalty is non-finite ({evaluation.failure_penalty})"
            )
    else:
        if not math.isfinite(float(evaluation.selection_score)):
            raise ValueError(
                f"fit {evaluation.fit_id!r} selection_score is non-finite ({evaluation.selection_score})"
            )
    for record in evaluation.point_records:
        for field in ("l_param", "e_beta", "e_eta", "e_gamma"):
            value = record[field]
            if not math.isfinite(float(value)):
                raise ValueError(
                    f"fit {evaluation.fit_id!r} point record {record.get('sample_id', '?')} "
                    f"has non-finite {field} ({value})"
                )


def _mean_aggregate(evaluations: Sequence[FitEvaluation]) -> float:
    values = [
        float(ev.failure_penalty) if ev.failed else float(ev.selection_score) for ev in evaluations
    ]
    if not values:
        raise ValueError("aggregate requires at least one supporting fit")
    return sum(values) / len(values)


def candidate_supporting_evidence(
    *, module_id: str, run_id: str, candidate: CandidateSpec,
    evaluations_by_support: Mapping[SupportKey, FitEvaluation],
) -> dict[str, Any]:
    """Aggregate one candidate's bound evidence and compute its full-context hash.

    The supporting fits must cover exactly the candidate's ``support_keys`` (no
    missing/extra/duplicate/wrong-n/wrong-seed fit). The ``supporting_evidence_sha256``
    binds module/run/decision/candidate/rule/expected_fit_ids AND the canonical
    supporting rows; each row carries its fit_id, n, seed, failed flag, checkpoint sha,
    validation identity, score/penalty AND its ``point_evidence_sha256`` (R3#1) -- so a
    swapped point-evidence artifact, a relabel, cross-candidate reuse, or any
    checkpoint/score/validation-set/point-record tampering changes the digest and fails
    closed. The large point records themselves live in per-fit point-evidence artifacts;
    only their content SHA is bound here.
    """
    if set(evaluations_by_support) != set(candidate.support_keys):
        missing = sorted(set(candidate.support_keys) - set(evaluations_by_support), key=lambda k: (str(k.n), k.seed))
        extra = sorted(set(evaluations_by_support) - set(candidate.support_keys), key=lambda k: (str(k.n), k.seed))
        raise ValueError(
            f"supporting evidence for {candidate.decision_id}/{candidate.candidate_id} must cover "
            f"exactly the candidate support keys; missing={missing!r} extra={extra!r}"
        )
    evaluations = [evaluations_by_support[key] for key in candidate.support_keys]
    for evaluation in evaluations:
        _validate_evaluation_finite(evaluation)
    if candidate.selection_rule == SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT:
        aggregate = _equal_weight_per_n_aggregate(evaluations)
    else:
        aggregate = _mean_aggregate(evaluations)
    if not math.isfinite(aggregate):
        raise ValueError(
            f"aggregate score for {candidate.candidate_id!r} is non-finite ({aggregate})"
        )

    supporting_rows: list[dict[str, Any]] = []
    for key, evaluation in zip(candidate.support_keys, evaluations):
        if evaluation.support_key != key:
            raise ValueError(
                f"support evaluation for {candidate.candidate_id} keyed by {evaluation.support_key!r} "
                f"disagrees with expected support {key!r}"
            )
        if str(evaluation.fit_id) != candidate.support_for(key):
            raise ValueError(
                f"support fit_id {evaluation.fit_id!r} disagrees with frozen expected "
                f"{candidate.support_for(key)!r} for {candidate.candidate_id}/{key!r}"
            )
        point_sha = evaluation.point_evidence_sha256()
        row = {
            "fit_id": evaluation.fit_id, "n": key.n, "seed": int(key.seed),
            "failed": bool(evaluation.failed),
            "checkpoint_sha256": evaluation.checkpoint_sha256,
            "validation_identity": evaluation.validation_identity,
            "selection_score": float(evaluation.selection_score),
            "failure_penalty": float(evaluation.failure_penalty),
            "point_evidence_sha256": point_sha,
        }
        supporting_rows.append(row)

    canonical_payload = _canonical({
        "module_id": module_id, "run_id": run_id, "decision_id": candidate.decision_id,
        "candidate_id": candidate.candidate_id, "selection_rule": candidate.selection_rule,
        "expected_fit_ids": list(candidate.expected_fit_ids),
        "supporting_rows": supporting_rows,
    })
    return {
        "module_id": module_id, "run_id": run_id, "decision_id": candidate.decision_id,
        "candidate_id": candidate.candidate_id, "selection_rule": candidate.selection_rule,
        "expected_fit_ids": list(candidate.expected_fit_ids),
        "supporting_fits": supporting_rows,
        "aggregate_score": aggregate,
        "supporting_evidence_sha256": hashlib.sha256(canonical_payload).hexdigest(),
        "support_count": len(supporting_rows),
        "seed_count": len({int(key.seed) for key in candidate.support_keys}),
    }


# --------------------------------------------------------------------------
# Rule application -- the winner is computed, never supplied.
# --------------------------------------------------------------------------


def _pairable_point_records(
    candidate: CandidateSpec, evaluations_by_support: Mapping[SupportKey, FitEvaluation],
) -> list[Mapping[str, Any]]:
    """Flatten one candidate's per-(n, seed) point records into one paired list.

    Failed fits are NOT skipped (R3#6): a failed fit carries the all-illegal point
    records over its validation cell set, so failure rate, ``L_param`` and pairing
    truly include the failed seed. Two candidates of one decision share the same
    validation cell grid, so a failed seed's all-illegal records pair against the
    comparator's real records and correctly penalise the failing candidate.
    """
    records: list[Mapping[str, Any]] = []
    for key in candidate.support_keys:
        evaluation = evaluations_by_support[key]
        records.extend(evaluation.point_records)
    return records


def apply_selection_rule(
    spec: DecisionSpec, evidence_by_candidate: Mapping[str, dict[str, Any]],
    evaluations_by_candidate: Mapping[str, Mapping[SupportKey, FitEvaluation]],
) -> tuple[str, dict[str, Any]]:
    """Apply the decision's frozen rule; return ``(winner_candidate_id, rule_result)``.

    The winner is always COMPUTED from the bound evidence; no caller may supply it.
    ``rule_result`` is the rule-specific diagnostics (ranked order, paired CIs, or
    per-pair global-better intervals/verdicts) -- enough for pre-unseal to re-derive
    the rule from the verified point evidence and recompute the diagnostics SHA.
    """
    candidates = spec.candidates
    if len(candidates) == 1:
        return candidates[0].candidate_id, {"reason": "unopposed"}
    rule = spec.selection_rule
    if rule == SELECTION_RULE_LOWEST_AGGREGATE:
        ranked = _rank_by_aggregate(candidates, evidence_by_candidate)
        return ranked[0], {"reason": "lowest_aggregate", "ranked": ranked}
    if rule == SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT:
        ranked = _rank_by_aggregate(candidates, evidence_by_candidate)
        return ranked[0], {"reason": "fixed_vs_shared_equal_weight", "ranked": ranked}
    if rule == SELECTION_RULE_SMALLEST_WITHIN_2PCT_CI:
        return _smallest_within_2pct_result(candidates, evidence_by_candidate, evaluations_by_candidate)
    if rule == SELECTION_RULE_GLOBAL_BETTER:
        return _global_better_result(candidates, evidence_by_candidate, evaluations_by_candidate)
    raise ValueError(f"unsupported selection rule {rule!r}")


def _rank_by_aggregate(candidates: Sequence[CandidateSpec], evidence_by_candidate: Mapping[str, dict[str, Any]]) -> list[str]:
    return [
        c.candidate_id for c in sorted(
            candidates,
            key=lambda c: (evidence_by_candidate[c.candidate_id]["aggregate_score"], c.tie_break_key),
        )
    ]


def _smallest_within_2pct_result(
    candidates: Sequence[CandidateSpec], evidence_by_candidate: Mapping[str, dict[str, Any]],
    evaluations_by_candidate: Mapping[str, Mapping[SupportKey, FitEvaluation]],
) -> tuple[str, dict[str, Any]]:
    scores = {c.candidate_id: float(evidence_by_candidate[c.candidate_id]["aggregate_score"]) for c in candidates}
    best_id = min(scores, key=lambda cid: (scores[cid], cid))
    best = next(c for c in candidates if c.candidate_id == best_id)
    best_points = _pairable_point_records(best, evaluations_by_candidate[best_id])
    candidate_cis: dict[str, dict[str, float]] = {}
    candidate_paired: dict[str, list[Mapping[str, Any]]] = {}
    for candidate in candidates:
        if candidate.candidate_id == best_id:
            continue
        cand_points = _pairable_point_records(candidate, evaluations_by_candidate[candidate.candidate_id])
        paired = _improvement_records(best_points, cand_points)
        candidate_paired[candidate.candidate_id] = paired
        candidate_cis[candidate.candidate_id] = paired_two_level_bootstrap_ci(paired)
    winner = smallest_within_2pct_ci_choice(candidate_scores=scores, candidate_paired=candidate_paired)
    return winner, {
        "reason": "smallest_within_2pct_ci", "best_by_score": best_id,
        "candidate_scores": scores, "candidate_cis": candidate_cis,
    }


def _improvement_records(
    comparator_points: Sequence[Mapping[str, Any]], candidate_points: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Paired improvement (comparator - candidate) per (seed, sample) for the CI rules.

    Uses the frozen failure-penalized ``L_param`` per cell (failed-seed cells carry the
    penalty, so a worse-on-failures candidate is not silently favoured). Pairing is
    exact on ``(seed_id, sample_id)`` via :func:`validate_point_records`; a mismatched
    cell set, duplicate cell, cross-point sample, or cross-candidate ``point_id``
    disagreement for the same cell fails closed (R4#2: the CROSS_POINT attack).
    """
    from .evaluation import validate_point_records
    comparator_records = validate_point_records(comparator_points)
    candidate_records = validate_point_records(candidate_points)
    candidate_by = {(r["seed_id"], r["sample_id"]): r for r in candidate_records}
    comparator_by = {(r["seed_id"], r["sample_id"]): r for r in comparator_records}
    if set(candidate_by) != set(comparator_by):
        raise ValueError("CI pairing requires identical (seed_id, sample_id) sets across candidates")
    for cell in candidate_by:
        if candidate_by[cell]["point_id"] != comparator_by[cell]["point_id"]:
            raise ValueError(
                f"cross-candidate point_id mismatch for {cell!r}: "
                f"{candidate_by[cell]['point_id']!r} vs {comparator_by[cell]['point_id']!r}"
            )
    records: list[Mapping[str, Any]] = []
    for key in sorted(candidate_by):
        cand, comp = candidate_by[key], comparator_by[key]
        records.append({
            "seed_id": cand["seed_id"], "sample_id": cand["sample_id"], "point_id": cand["point_id"],
            "improvement": float(comp["l_param"]) - float(cand["l_param"]),
        })
    return records


def _global_better_result(
    candidates: Sequence[CandidateSpec], evidence_by_candidate: Mapping[str, dict[str, Any]],
    evaluations_by_candidate: Mapping[str, Mapping[SupportKey, FitEvaluation]],
) -> tuple[str, dict[str, Any]]:
    """global_better_rule: a candidate globally-dominating all others wins; else fall
    back to the lowest mean penalized L_param with the frozen id tie-break (A-E1
    baseline_input / A-E2 distribution). Returns the per-pair intervals + verdicts so
    pre-unseal can re-derive the rule from the verified point evidence."""
    point_records = {
        c.candidate_id: _pairable_point_records(c, evaluations_by_candidate[c.candidate_id]) for c in candidates
    }
    scores = {c.candidate_id: float(evidence_by_candidate[c.candidate_id]["aggregate_score"]) for c in candidates}
    intervals: dict[str, dict[str, Any]] = {}
    verdicts: dict[str, str] = {}
    globally_better_ids: list[str] = []
    for candidate in candidates:
        dominated = True
        for other in candidates:
            if other.candidate_id == candidate.candidate_id:
                continue
            pair = f"{candidate.candidate_id}>vs>{other.candidate_id}"
            result = global_better_intervals(
                candidate=point_records[candidate.candidate_id], comparator=point_records[other.candidate_id])
            intervals[pair] = result
            verdicts[pair] = result["verdict"]
            if result["verdict"] != "globally_better":
                dominated = False
        if dominated:
            globally_better_ids.append(candidate.candidate_id)
    if len(globally_better_ids) == 1:
        return globally_better_ids[0], {"reason": "global_better", "verdicts": verdicts, "intervals": intervals}
    ranked = [c.candidate_id for c in sorted(candidates, key=lambda c: (scores[c.candidate_id], c.tie_break_key))]
    return ranked[0], {"reason": "global_better_fallback_lowest_l_param", "ranked": ranked,
                       "verdicts": verdicts, "intervals": intervals}


_BOOTSTRAP_DIAGNOSTICS_CONFIG = {"seed": 520001, "replicates": 2000}


def build_rule_diagnostics(
    *, module_id: str, run_id: str, spec: DecisionSpec,
    evidence_by_candidate: Mapping[str, dict[str, Any]], winner: str, rule_result: Mapping[str, Any],
) -> dict[str, Any]:
    """Assemble the full per-decision rule-diagnostics structure (R3#2).

    Binds the frozen bootstrap config, each candidate's aggregate evidence, the
    computed winner, and the rule-specific result (ranked order / paired CIs /
    global-better intervals+verdicts). Its canonical SHA (bound into the trace as
    ``rule_diagnostics_sha256``) lets pre-unseal re-derive the rule from the verified
    point evidence and confirm the published winner -- the trace never relies on the
    ``selected`` flag alone.
    """
    candidate_summaries = [
        {
            "candidate_id": c.candidate_id,
            "aggregate_score": float(evidence_by_candidate[c.candidate_id]["aggregate_score"]),
            "support_count": int(evidence_by_candidate[c.candidate_id]["support_count"]),
            "seed_count": int(evidence_by_candidate[c.candidate_id]["seed_count"]),
        }
        for c in sorted(spec.candidates, key=lambda c: c.candidate_id)
    ]
    diagnostics: dict[str, Any] = {
        "module_id": module_id, "run_id": run_id, "decision_id": spec.decision_id,
        "selection_rule": spec.selection_rule, "winner": winner,
        "candidates": candidate_summaries, "rule_result": dict(rule_result),
    }
    if spec.selection_rule in (SELECTION_RULE_GLOBAL_BETTER, SELECTION_RULE_SMALLEST_WITHIN_2PCT_CI,
                               SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT):
        diagnostics["bootstrap_config"] = dict(_BOOTSTRAP_DIAGNOSTICS_CONFIG)
    return diagnostics


def compute_rule_diagnostics_sha256(diagnostics: Mapping[str, Any]) -> str:
    """Canonical SHA-256 of a decision's rule diagnostics (R3#2)."""
    return hashlib.sha256(_canonical(diagnostics)).hexdigest()


# --------------------------------------------------------------------------
# Per-fit point-evidence artifacts (R3#1): large point records live in a separate
# immutable artifact; the trace/supporting hash binds the artifact's content SHA.
# --------------------------------------------------------------------------

_POINT_EVIDENCE_ARTIFACT_VERSION = "study02-point-evidence-v1"


def serialize_point_evidence(evaluation: FitEvaluation) -> dict[str, Any]:
    """Serialize one fit's point evidence to a canonical artifact dict (R3#1).

    The artifact carries the full immutable identity, checkpoint SHA, validation
    cache/data identity, failed flag, scalar score/penalty, the canonical per-sample
    point records and their content SHA (``point_evidence_sha256``). It is the unit
    pre-unseal loads to re-derive the non-ranking rules independently.
    """
    records = sorted(
        (_canonical_point_record(record) for record in evaluation.point_records),
        key=lambda r: (str(r["seed_id"]), str(r["sample_id"])),
    )
    return {
        "artifact_version": _POINT_EVIDENCE_ARTIFACT_VERSION,
        "fit_id": evaluation.fit_id, "module_id": evaluation.module_id,
        "decision_id": evaluation.decision_id, "candidate_id": evaluation.candidate_id,
        "n": evaluation.support_key.n, "seed": int(evaluation.support_key.seed),
        "checkpoint_sha256": evaluation.checkpoint_sha256,
        "validation_identity": evaluation.validation_identity,
        "failed": bool(evaluation.failed),
        "selection_score": float(evaluation.selection_score),
        "failure_penalty": float(evaluation.failure_penalty),
        "point_evidence_sha256": evaluation.point_evidence_sha256(),
        "point_records": records,
    }


def load_point_evidence(payload: Mapping[str, Any]) -> FitEvaluation:
    """Load + integrity-verify a point-evidence artifact (R3#1/##3).

    Recomputes ``point_evidence_sha256`` from the bound identity + checkpoint +
    validation identity + failed flag + canonical point records and requires it to
    equal the artifact's stored digest (any tampered record/identity/checkpoint fails
    closed). The point records are semantically validated (R4#2) before hashing, and
    the artifact's stored scalar must equal the independent aggregate of its canonical
    records (R4#2#9: a succeeded fit's ``selection_score`` is the mean per-sample
    ``L_param``; a failed fit's ``failure_penalty`` is the mean over its all-illegal
    cells) -- so a scalar fabricated independently of the records fails closed even
    before the supporting-hash check. Returns the reconstructed :class:`FitEvaluation`.
    """
    if payload.get("artifact_version") != _POINT_EVIDENCE_ARTIFACT_VERSION:
        raise ValueError("point-evidence artifact version mismatch")
    required = {"artifact_version", "fit_id", "module_id", "decision_id", "candidate_id", "n", "seed",
                "checkpoint_sha256", "validation_identity", "failed", "selection_score",
                "failure_penalty", "point_evidence_sha256", "point_records"}
    if set(payload) != required:
        raise ValueError("point-evidence artifact schema must match the frozen fields exactly")
    support_key = SupportKey(n=payload["n"], seed=int(payload["seed"]))
    recomputed = compute_point_evidence_sha256(
        fit_id=payload["fit_id"], module_id=payload["module_id"], decision_id=payload["decision_id"],
        candidate_id=payload["candidate_id"], support_key=support_key,
        checkpoint_sha256=payload["checkpoint_sha256"], validation_identity=payload["validation_identity"],
        failed=payload["failed"], point_records=payload["point_records"],
    )
    if recomputed != payload["point_evidence_sha256"]:
        raise ValueError(
            f"point-evidence artifact {payload['fit_id']!r} content SHA disagrees with its stored digest"
        )
    records = tuple(payload["point_records"])
    if records:
        mean_l_param = sum(float(record["l_param"]) for record in records) / len(records)
        if bool(payload["failed"]):
            if not math.isclose(float(payload["failure_penalty"]), mean_l_param, rel_tol=1e-9, abs_tol=1e-12):
                raise ValueError(
                    f"point-evidence artifact {payload['fit_id']!r} failure_penalty disagrees with "
                    f"the mean L_param of its canonical records"
                )
        elif not math.isclose(float(payload["selection_score"]), mean_l_param, rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(
                f"point-evidence artifact {payload['fit_id']!r} selection_score disagrees with "
                f"the mean L_param of its canonical records"
            )
    return FitEvaluation(
        fit_id=payload["fit_id"], module_id=payload["module_id"], decision_id=payload["decision_id"],
        candidate_id=payload["candidate_id"], support_key=support_key, failed=bool(payload["failed"]),
        checkpoint_sha256=payload["checkpoint_sha256"], validation_identity=payload["validation_identity"],
        selection_score=float(payload["selection_score"]), failure_penalty=float(payload["failure_penalty"]),
        point_records=tuple(payload["point_records"]),
    )


def assert_point_evidence_provenance(*, published: "FitEvaluation", rebuilt: "FitEvaluation") -> None:
    """R4#1: assert a published point-evidence artifact agrees field-by-field with an
    independently rebuilt evaluation (the rebuilt evaluation is derived from the bound
    checkpoint + the frozen validation inputs through the single-source scoring path -- never
    from the artifact itself).

    This closes the loop the artifact's self-consistent content SHA leaves open: an attacker
    who rewrites the point records AND resynchronises the artifact's content SHA plus the
    downstream supporting-evidence / diagnostics / trace / receipt / ledger / fit_status
    still fails closed, because the rebuilt records come from the actual checkpoint, not the
    artifact. Compares the checkpoint SHA (the real file, via the rebuild), the validation
    identity (must equal the rebuilt dataset/cache identity), the failed flag, the scalar
    (selection_score for a succeeded fit, failure_penalty for a failed fit), and the canonical
    point records (field-by-field, via ``point_evidence_sha256`` which binds the records plus
    the identity, checkpoint, validation identity and failed flag).
    """
    fit_id = rebuilt.fit_id
    if published.fit_id != fit_id:
        raise ValueError(f"point-evidence provenance fit_id mismatch: {published.fit_id!r} vs {fit_id!r}")
    if published.module_id != rebuilt.module_id or published.decision_id != rebuilt.decision_id \
            or published.candidate_id != rebuilt.candidate_id:
        raise ValueError(f"point-evidence provenance identity mismatch for {fit_id!r}")
    if published.support_key != rebuilt.support_key:
        raise ValueError(
            f"point-evidence provenance support key mismatch for {fit_id!r}: "
            f"{published.support_key!r} vs {rebuilt.support_key!r}"
        )
    if published.checkpoint_sha256 != rebuilt.checkpoint_sha256:
        raise ValueError(
            f"point-evidence artifact {fit_id!r} checkpoint_sha256 disagrees with the rebuilt checkpoint"
        )
    if published.validation_identity != rebuilt.validation_identity:
        raise ValueError(
            f"point-evidence artifact {fit_id!r} validation_identity disagrees with the rebuilt "
            f"dataset/cache identity"
        )
    if bool(published.failed) != bool(rebuilt.failed):
        raise ValueError(f"point-evidence artifact {fit_id!r} failed flag disagrees with the rebuild")
    if published.failed:
        if not math.isclose(float(published.failure_penalty), float(rebuilt.failure_penalty),
                            rel_tol=1e-9, abs_tol=1e-12):
            raise ValueError(
                f"point-evidence artifact {fit_id!r} failure_penalty disagrees with the rebuild"
            )
    elif not math.isclose(float(published.selection_score), float(rebuilt.selection_score),
                          rel_tol=1e-9, abs_tol=1e-12):
        raise ValueError(
            f"point-evidence artifact {fit_id!r} selection_score disagrees with the rebuild"
        )
    if published.point_evidence_sha256() != rebuilt.point_evidence_sha256():
        raise ValueError(
            f"point-evidence artifact {fit_id!r} canonical point records disagree with the rebuild"
        )


def build_selection_trace(
    *, module_id: str, run_id: str, specs: Sequence[DecisionSpec],
    evaluations_by_fit: Mapping[str, FitEvaluation],
) -> tuple[tuple[dict[str, Any], ...], tuple[dict[str, Any], ...]]:
    """Compute every decision's evidence + deterministic winner -> trace + diagnostics.

    For each candidate the supporting evidence is aggregated from the bound
    :class:`FitEvaluation` overlay (keyed by fit_id), the rule selects the winner, and
    one v3 trace record per candidate is returned (caller writes them via
    ``formal_contracts.write_selection_trace``). Each record binds the candidate's
    ``supporting_evidence_sha256`` (which binds every supporting fit's
    ``point_evidence_sha256``) AND the decision's ``rule_diagnostics_sha256`` (R3#2).
    Returns ``(trace_records, diagnostics_records)``; the diagnostics records (one per
    decision) are written as a separate immutable artifact so pre-unseal can re-derive
    the rule and recompute the diagnostics SHA.
    """
    consumed_fit_ids: set[str] = set()
    records: list[dict[str, Any]] = []
    diagnostics_records: list[dict[str, Any]] = []
    for spec in specs:
        evidence_by_candidate: dict[str, dict[str, Any]] = {}
        evals_by_candidate: dict[str, Mapping[SupportKey, FitEvaluation]] = {}
        for candidate in spec.candidates:
            evaluations_by_support: dict[SupportKey, FitEvaluation] = {}
            for key in candidate.support_keys:
                fit_id = candidate.support_for(key)
                if fit_id in consumed_fit_ids:
                    raise ValueError(
                        f"fit {fit_id!r} is bound to two selection candidates (cross-candidate reuse)"
                    )
                evaluation = evaluations_by_fit.get(fit_id)
                if evaluation is None:
                    raise ValueError(f"missing bound evaluation for expected fit {fit_id!r}")
                if evaluation.support_key != key:
                    raise ValueError(
                        f"fit {fit_id!r} support key {evaluation.support_key!r} disagrees with "
                        f"frozen expected {key!r}"
                    )
                consumed_fit_ids.add(fit_id)
                evaluations_by_support[key] = evaluation
            evidence = candidate_supporting_evidence(
                module_id=module_id, run_id=run_id, candidate=candidate,
                evaluations_by_support=evaluations_by_support,
            )
            evidence_by_candidate[candidate.candidate_id] = evidence
            evals_by_candidate[candidate.candidate_id] = evaluations_by_support
        winner, rule_result = apply_selection_rule(spec, evidence_by_candidate, evals_by_candidate)
        diagnostics = build_rule_diagnostics(
            module_id=module_id, run_id=run_id, spec=spec,
            evidence_by_candidate=evidence_by_candidate, winner=winner, rule_result=rule_result,
        )
        diagnostics_sha = compute_rule_diagnostics_sha256(diagnostics)
        diagnostics_records.append(diagnostics)
        marked = False
        for candidate in spec.candidates:
            selected = candidate.candidate_id == winner
            marked = marked or selected
            evidence = evidence_by_candidate[candidate.candidate_id]
            records.append({
                "module_id": module_id, "run_id": run_id, "decision_id": spec.decision_id,
                "candidate_id": candidate.candidate_id,
                "validation_score": evidence["aggregate_score"],
                "tie_break_key": list(candidate.tie_break_key), "selected": selected,
                "supporting_evidence_sha256": evidence["supporting_evidence_sha256"],
                "rule_diagnostics_sha256": diagnostics_sha,
                "support_count": evidence["support_count"], "seed_count": evidence["seed_count"],
                "selection_rule": spec.selection_rule,
            })
        if not marked:
            raise ValueError(f"selection winner {winner!r} for {spec.decision_id} is not a candidate")
    return tuple(records), tuple(diagnostics_records)


__all__ = [
    "SupportKey",
    "CandidateSpec",
    "DecisionSpec",
    "FitEvaluation",
    "apply_selection_rule",
    "assert_point_evidence_provenance",
    "build_decision_specs",
    "build_rule_diagnostics",
    "build_selection_trace",
    "candidate_supporting_evidence",
    "compute_point_evidence_sha256",
    "compute_rule_diagnostics_sha256",
    "load_point_evidence",
    "serialize_point_evidence",
]
