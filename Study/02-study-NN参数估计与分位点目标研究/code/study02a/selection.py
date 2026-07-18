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
from typing import Any, Mapping, Sequence

from .evaluation import (
    global_better_intervals,
    paired_two_level_bootstrap_ci,
    smallest_within_2pct_ci_choice,
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


@dataclass(frozen=True)
class FitEvaluation:
    """A fit's bound evaluation evidence (the only run-derived input).

    Produced by scoring an integrity-bound checkpoint on its validation cache:
    ``selection_score`` is the mean failure-penalized ``L_param``; ``point_records``
    are the per-validation-sample records (stable pairing ids) the CI rules consume.
    A failed fit carries the frozen penalty and no point records. ``checkpoint_sha256``
    binds the evidence to the exact trained checkpoint.
    """

    fit_id: str
    support_key: SupportKey
    failed: bool
    checkpoint_sha256: str
    selection_score: float
    failure_penalty: float
    point_records: tuple[Mapping[str, Any], ...] = ()


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


def point_evidence_sha256(point_records: Sequence[Mapping[str, Any]]) -> str:
    """Canonical hash of one fit's per-sample evaluation records.

    Records are sorted by ``sample_id`` (stable pairing id) before hashing, so the
    digest depends on the checkpoint's per-sample behaviour, not on caller ordering.
    Binding this hash into the supporting evidence ties the selection to the exact
    trained checkpoint via its per-sample output -- a tampered checkpoint or score
    changes the digest and fails closed at pre-unseal.
    """
    if not point_records:
        return ""
    canonical_rows = [
        {k: record[k] for k in ("sample_id", "point_id", "seed_id", "legal", "failure", "l_param",
                                "e_beta", "e_eta", "e_gamma") if k in record}
        for record in point_records
    ]
    payload = b"".join(_canonical(row) for row in sorted(canonical_rows, key=lambda r: str(r["sample_id"])))
    return hashlib.sha256(payload).hexdigest()


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
    supporting rows (each carrying its checkpoint sha, score/penalty and
    ``point_evidence_sha256``), so any relabelling, cross-candidate reuse, or
    checkpoint/score tampering changes the digest.
    """
    if set(evaluations_by_support) != set(candidate.support_keys):
        missing = sorted(set(candidate.support_keys) - set(evaluations_by_support), key=lambda k: (str(k.n), k.seed))
        extra = sorted(set(evaluations_by_support) - set(candidate.support_keys), key=lambda k: (str(k.n), k.seed))
        raise ValueError(
            f"supporting evidence for {candidate.decision_id}/{candidate.candidate_id} must cover "
            f"exactly the candidate support keys; missing={missing!r} extra={extra!r}"
        )
    evaluations = [evaluations_by_support[key] for key in candidate.support_keys]
    if candidate.selection_rule == SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT:
        aggregate = _equal_weight_per_n_aggregate(evaluations)
    else:
        aggregate = _mean_aggregate(evaluations)

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
        if evaluation.failed:
            row = {
                "fit_id": evaluation.fit_id, "n": key.n, "seed": int(key.seed), "failed": True,
                "checkpoint_sha256": "", "selection_score": "", "failure_penalty": float(evaluation.failure_penalty),
                "point_evidence_sha256": "",
            }
        else:
            row = {
                "fit_id": evaluation.fit_id, "n": key.n, "seed": int(key.seed), "failed": False,
                "checkpoint_sha256": evaluation.checkpoint_sha256,
                "selection_score": float(evaluation.selection_score), "failure_penalty": "",
                "point_evidence_sha256": point_evidence_sha256(evaluation.point_records),
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
    """Flatten one candidate's per-(n, seed) point records into one paired list."""
    records: list[Mapping[str, Any]] = []
    for key in candidate.support_keys:
        evaluation = evaluations_by_support[key]
        if evaluation.failed:
            continue  # failed fit contributes the penalty via aggregate, not point pairing
        records.extend(evaluation.point_records)
    return records


def _select_winner(
    spec: DecisionSpec, evidence_by_candidate: Mapping[str, dict[str, Any]],
    evaluations_by_candidate: Mapping[str, Mapping[SupportKey, FitEvaluation]],
) -> tuple[str, dict[str, Any]]:
    """Apply the decision's frozen rule and return (winner_candidate_id, diagnostics).

    The winner is always COMPUTED from the bound evidence; no caller may supply it.
    Diagnostics carry the CI/verdict details so the trace can be audited and the
    "no receipt before the rule is verified" contract holds.
    """
    candidates = spec.candidates
    if len(candidates) == 1:
        return candidates[0].candidate_id, {"reason": "unopposed"}
    rule = spec.selection_rule
    if rule == SELECTION_RULE_LOWEST_AGGREGATE:
        ranked = sorted(
            candidates,
            key=lambda c: (evidence_by_candidate[c.candidate_id]["aggregate_score"], c.tie_break_key),
        )
        return ranked[0].candidate_id, {
            "reason": "lowest_aggregate", "ranked": [c.candidate_id for c in ranked],
        }
    if rule == SELECTION_RULE_FIXED_VS_SHARED_EQUAL_WEIGHT:
        ranked = sorted(
            candidates,
            key=lambda c: (evidence_by_candidate[c.candidate_id]["aggregate_score"], c.tie_break_key),
        )
        return ranked[0].candidate_id, {
            "reason": "fixed_vs_shared_equal_weight", "ranked": [c.candidate_id for c in ranked],
        }
    if rule == SELECTION_RULE_SMALLEST_WITHIN_2PCT_CI:
        scores = {c.candidate_id: evidence_by_candidate[c.candidate_id]["aggregate_score"] for c in candidates}
        best_id = min(scores, key=lambda cid: (scores[cid], cid))
        candidate_paired: dict[str, list[Mapping[str, Any]]] = {}
        for candidate in candidates:
            if candidate.candidate_id == best_id:
                continue
            cand_points = _pairable_point_records(candidate, evaluations_by_candidate[candidate.candidate_id])
            best_points = _pairable_point_records(
                next(c for c in candidates if c.candidate_id == best_id),
                evaluations_by_candidate[best_id],
            )
            candidate_paired[candidate.candidate_id] = _improvement_records(best_points, cand_points)
        winner = smallest_within_2pct_ci_choice(candidate_scores=scores, candidate_paired=candidate_paired)
        return winner, {"reason": "smallest_within_2pct_ci", "best_by_score": best_id}
    if rule == SELECTION_RULE_GLOBAL_BETTER:
        return _global_better_winner(spec, evidence_by_candidate, evaluations_by_candidate)
    raise ValueError(f"unsupported selection rule {rule!r}")


def _improvement_records(
    comparator_points: Sequence[Mapping[str, Any]], candidate_points: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Paired improvement (comparator - candidate) per (seed, sample) for the CI rules."""
    candidate_by = {(str(r["seed_id"]), str(r["sample_id"])): r for r in candidate_points}
    comparator_by = {(str(r["seed_id"]), str(r["sample_id"])): r for r in comparator_points}
    if set(candidate_by) != set(comparator_by):
        raise ValueError("global-better/CI pairing requires identical (seed_id, sample_id) sets")
    records: list[Mapping[str, Any]] = []
    for key in sorted(candidate_by):
        cand, comp = candidate_by[key], comparator_by[key]
        records.append({
            "seed_id": str(cand["seed_id"]), "sample_id": str(cand["sample_id"]),
            "point_id": str(cand["point_id"]), "improvement": float(comp["l_param"]) - float(cand["l_param"]),
        })
    return records


def _global_better_winner(
    spec: DecisionSpec, evidence_by_candidate: Mapping[str, dict[str, Any]],
    evaluations_by_candidate: Mapping[str, Mapping[SupportKey, FitEvaluation]],
) -> tuple[str, dict[str, Any]]:
    """global_better_rule: a candidate globally-dominating all others wins; else
    fall back to the lowest mean penalized L_param with the frozen id tie-break.

    Per module_matrix_rules (A-E1 baseline_input / A-E2 distribution): "apply
    validation global_better_rule; if neither globally dominates, lowest mean
    validation failure-penalized l_param; exact tie by id".
    """
    candidates = spec.candidates
    point_records = {
        c.candidate_id: _pairable_point_records(c, evaluations_by_candidate[c.candidate_id]) for c in candidates
    }
    scores = {c.candidate_id: evidence_by_candidate[c.candidate_id]["aggregate_score"] for c in candidates}
    verdicts: dict[str, dict[str, Any]] = {}
    globally_better_ids: list[str] = []
    for candidate in candidates:
        dominated = True
        for other in candidates:
            if other.candidate_id == candidate.candidate_id:
                continue
            result = global_better_intervals(candidate=point_records[candidate.candidate_id], comparator=point_records[other.candidate_id])
            verdicts[f"{candidate.candidate_id}>vs>{other.candidate_id}"] = result["verdict"]
            if result["verdict"] != "globally_better":
                dominated = False
        if dominated:
            globally_better_ids.append(candidate.candidate_id)
    if len(globally_better_ids) == 1:
        return globally_better_ids[0], {"reason": "global_better", "verdicts": verdicts}
    # Fallback: lowest mean penalized L_param, tie by candidate id.
    ranked = sorted(candidates, key=lambda c: (scores[c.candidate_id], c.tie_break_key))
    return ranked[0].candidate_id, {"reason": "global_better_fallback_lowest_l_param", "verdicts": verdicts}


def build_selection_trace(
    *, module_id: str, run_id: str, specs: Sequence[DecisionSpec],
    evaluations_by_fit: Mapping[str, FitEvaluation],
) -> tuple[dict[str, Any], ...]:
    """Compute every decision's evidence + deterministic winner -> trace records.

    For each candidate the supporting evidence is aggregated from the bound
    :class:`FitEvaluation` overlay (keyed by fit_id), the rule selects the winner,
    and one v2 trace record per candidate is returned (caller writes them via
    ``formal_contracts.write_selection_trace``). ``evaluations_by_fit`` is the only
    run-derived input; every fit it binds must belong to exactly one candidate of
    one spec (no cross-candidate reuse).
    """
    consumed_fit_ids: set[str] = set()
    records: list[dict[str, Any]] = []
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
        winner, diagnostics = _select_winner(spec, evidence_by_candidate, evals_by_candidate)
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
                "support_count": evidence["support_count"], "seed_count": evidence["seed_count"],
                "selection_rule": spec.selection_rule,
            })
        if not marked:
            raise ValueError(f"selection winner {winner!r} for {spec.decision_id} is not a candidate")
    return tuple(records)


__all__ = [
    "SupportKey",
    "CandidateSpec",
    "DecisionSpec",
    "FitEvaluation",
    "build_decision_specs",
    "build_selection_trace",
    "candidate_supporting_evidence",
    "point_evidence_sha256",
]
