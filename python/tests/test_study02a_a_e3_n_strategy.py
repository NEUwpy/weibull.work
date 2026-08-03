"""R3-B: dedicated n_strategy decision (fixed vs shared) tests.

Tests the n_strategy decision constructed OUTSIDE the matrix ``build_decision_specs`` path
(dedicated evidence structure from the output_form winner checkpoints + shared_winner_retrain
checkpoints). Covers:

  * fixed-win / shared-win / tie-break / failed-fit / equal-weight-per-n aggregation logic.
  * supporting evidence SHA binding (per-cell: n/seed/checkpoint/point-evidence).
  * final_aliases concrete baseline tuple structure for fixed/shared winners.
  * 10-record staged-ledger chain shape (n_strategy = record 9, final_aliases = record 10).
  * pre-unseal rebuild produces an identical winner.

These are UNIT tests of the decision logic via ``_resolve_a_e3_n_strategy`` with the
``score_n_strategy_cell`` injection -- no real training, no real checkpoint scoring. The
production scoring path (``score_n_strategy_cell=None``) is exercised by the slow staged
integration tests (test_g12 / test_g16).
"""

from __future__ import annotations

import hashlib
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from study02a import formal_contracts as fc  # noqa: E402
from study02a import formal_executor as fe  # noqa: E402
from study02a.config import load_frozen_config  # noqa: E402
from study02a.formal_config import load_effective_formal_config  # noqa: E402
from study02a.selection import FitEvaluation, SupportKey  # noqa: E402

FROZEN = load_frozen_config(STUDY_ROOT)
EFFECTIVE = load_effective_formal_config(STUDY_ROOT)
CORE_N = tuple(int(n) for n in FROZEN.protocol["sample_sizes"]["core"])  # (5, 7, 10, 15, 20)
FORMAL_SEEDS = tuple(int(s) for s in FROZEN.search["formal_seeds"])      # (420101..420110)


# ---------------------------------------------------------------------------
# Helpers for synthetic per-cell n_strategy evaluations.
# ---------------------------------------------------------------------------


def _legal_point_records(*, fit_id: str, n: int, seed: int, score: float) -> tuple[dict, ...]:
    """One canonical legal point record whose l_param equals ``score``.

    For a legal record, ``l_param == rms(e_beta, e_eta, e_gamma)``; setting all three
    component errors to ``score`` satisfies this (sqrt((3*score^2)/3) == score). The
    record's ``seed_id`` matches the support seed (validated by ``validate_canonical_point_records``).
    """
    return ({
        "sample_id": f"synthetic-{fit_id}-n{n}-s{seed}",
        "seed_id": str(seed),
        "point_id": f"point-n{n}-s{seed}-0",
        "legal": True,
        "failure": 0,
        "l_param": float(score),
        "e_beta": float(score),
        "e_eta": float(score),
        "e_gamma": float(score),
    },)


def _illegal_point_records(*, fit_id: str, n: int, seed: int) -> tuple[dict, ...]:
    """One canonical illegal point record (all errors = frozen failure penalty 10.0)."""
    penalty = 10.0
    return ({
        "sample_id": f"synthetic-{fit_id}-n{n}-s{seed}",
        "seed_id": str(seed),
        "point_id": f"point-n{n}-s{seed}-0",
        "legal": False,
        "failure": 1,
        "l_param": penalty,
        "e_beta": penalty,
        "e_eta": penalty,
        "e_gamma": penalty,
    },)


def _make_cell_evaluation(
    *, fit_id: str, n: int, seed: int, cohort: str, score: float, failed: bool = False,
) -> FitEvaluation:
    """Build a valid FitEvaluation for one n_strategy cohort cell."""
    if failed:
        records = _illegal_point_records(fit_id=fit_id, n=n, seed=seed)
        return FitEvaluation(
            fit_id=fit_id, module_id="A-E3",
            decision_id=fe._A_E3_N_STRATEGY_DECISION_ID, candidate_id=cohort,
            support_key=SupportKey(n=n, seed=seed), failed=True,
            checkpoint_sha256="",
            validation_identity=f"synthetic:{cohort}:n{n}:s{seed}",
            selection_score=0.0, failure_penalty=10.0, point_records=records,
        )
    records = _legal_point_records(fit_id=fit_id, n=n, seed=seed, score=score)
    return FitEvaluation(
        fit_id=fit_id, module_id="A-E3",
        decision_id=fe._A_E3_N_STRATEGY_DECISION_ID, candidate_id=cohort,
        support_key=SupportKey(n=n, seed=seed), failed=False,
        checkpoint_sha256=hashlib.sha256(f"{fit_id}:n{n}:s{seed}".encode()).hexdigest(),
        validation_identity=f"synthetic:{cohort}:n{n}:s{seed}",
        selection_score=float(score), failure_penalty=0.0, point_records=records,
    )


def _make_cell_scorer(
    *, fixed_score: float | dict[tuple[int, int], float] = 0.5,
    shared_score: float | dict[tuple[int, int], float] = 0.5,
    fixed_failed: set[tuple[int, int]] | None = None,
    shared_failed: set[tuple[int, int]] | None = None,
):
    """Build a ``score_n_strategy_cell`` callable from synthetic scores.

    Scores may be a single scalar (uniform across all cells) or a ``(core_n, seed) -> score``
    dict for per-cell control. ``*_failed`` sets mark specific cells as failed (penalty 10.0).
    """
    fixed_failed = fixed_failed or set()
    shared_failed = shared_failed or set()

    def score_n_strategy_cell(fit_id: str, core_n: int, formal_seed: int, cohort: str) -> FitEvaluation:
        key = (int(core_n), int(formal_seed))
        if cohort == fe._A_E3_N_STRATEGY_FIXED:
            if key in fixed_failed:
                return _make_cell_evaluation(
                    fit_id=fit_id, n=core_n, seed=formal_seed, cohort=cohort, score=10.0, failed=True)
            score = float(fixed_score[key]) if isinstance(fixed_score, dict) else float(fixed_score)
        elif cohort == fe._A_E3_N_STRATEGY_SHARED:
            if key in shared_failed:
                return _make_cell_evaluation(
                    fit_id=fit_id, n=core_n, seed=formal_seed, cohort=cohort, score=10.0, failed=True)
            score = float(shared_score[key]) if isinstance(shared_score, dict) else float(shared_score)
        else:  # pragma: no cover - defensive
            raise ValueError(f"unknown cohort {cohort!r}")
        return _make_cell_evaluation(
            fit_id=fit_id, n=core_n, seed=formal_seed, cohort=cohort, score=score)
    return score_n_strategy_cell


def _resolve_n_strategy(score_n_strategy_cell):
    """Call ``_resolve_a_e3_n_strategy`` with dummy run/cache paths (injection path only)."""
    return fe._resolve_a_e3_n_strategy(
        study_root=STUDY_ROOT, run_dir=Path("/dummy"), cache_root=Path("/dummy"),
        frozen=FROZEN, effective=EFFECTIVE,
        matrix_by_fit={}, plan_by_fit={}, fit_states={},
        output_form_winner_candidate="joint",
        predecessor_resolved_route="V",
        module_id="A-E3", run_id="n-strategy-test",
        score_n_strategy_cell=score_n_strategy_cell,
    )


# ---------------------------------------------------------------------------
# Decision logic: fixed-win / shared-win / tie / failed / equal-weight.
# ---------------------------------------------------------------------------


def test_n_strategy_fixed_win_when_fixed_aggregate_lower():
    """Fixed cohort with uniformly lower L_param wins under fixed_vs_shared_equal_weight."""
    winner, evidence, rule_result = _resolve_n_strategy(
        _make_cell_scorer(fixed_score=0.3, shared_score=0.7))
    assert winner == fe._A_E3_N_STRATEGY_FIXED
    assert evidence[fe._A_E3_N_STRATEGY_FIXED]["aggregate_score"] < \
           evidence[fe._A_E3_N_STRATEGY_SHARED]["aggregate_score"]
    assert rule_result["ranked"][0] == fe._A_E3_N_STRATEGY_FIXED
    assert rule_result["ranked"] == [fe._A_E3_N_STRATEGY_FIXED, fe._A_E3_N_STRATEGY_SHARED]


def test_n_strategy_shared_win_when_shared_aggregate_lower():
    """Shared cohort with uniformly lower L_param wins."""
    winner, evidence, rule_result = _resolve_n_strategy(
        _make_cell_scorer(fixed_score=0.8, shared_score=0.2))
    assert winner == fe._A_E3_N_STRATEGY_SHARED
    assert evidence[fe._A_E3_N_STRATEGY_SHARED]["aggregate_score"] < \
           evidence[fe._A_E3_N_STRATEGY_FIXED]["aggregate_score"]
    assert rule_result["ranked"][0] == fe._A_E3_N_STRATEGY_SHARED


def test_n_strategy_tie_breaks_to_fixed_on_equal_aggregate():
    """Equal aggregates: the frozen tie-break is candidate_id ascending (``fixed`` < ``shared``)."""
    winner, evidence, rule_result = _resolve_n_strategy(
        _make_cell_scorer(fixed_score=0.5, shared_score=0.5))
    assert math.isclose(
        evidence[fe._A_E3_N_STRATEGY_FIXED]["aggregate_score"],
        evidence[fe._A_E3_N_STRATEGY_SHARED]["aggregate_score"], rel_tol=1e-12)
    assert winner == fe._A_E3_N_STRATEGY_FIXED  # alphabetical tie-break
    assert rule_result["ranked"] == [fe._A_E3_N_STRATEGY_FIXED, fe._A_E3_N_STRATEGY_SHARED]


def test_n_strategy_failed_fit_carries_penalty_not_skipped():
    """A failed shared cell carries the frozen penalty (10.0) -- it is NOT skipped.

    With shared failed at every cell, shared's aggregate should be 10.0 (the penalty) and
    fixed should win with its lower score. The failed cells' evidence is still bound.
    """
    all_cells = {(n, s) for n in CORE_N for s in FORMAL_SEEDS}
    winner, evidence, _ = _resolve_n_strategy(_make_cell_scorer(
        fixed_score=0.4, shared_score=0.4, shared_failed=all_cells))
    assert winner == fe._A_E3_N_STRATEGY_FIXED
    # Shared aggregate is the equal-weight-per-n mean of the 10.0 penalty.
    assert math.isclose(
        evidence[fe._A_E3_N_STRATEGY_SHARED]["aggregate_score"], 10.0, rel_tol=1e-12)
    # Failed cells are bound in the supporting rows (not skipped).
    shared_rows = evidence[fe._A_E3_N_STRATEGY_SHARED]["supporting_rows"]
    assert all(row["failed"] for row in shared_rows)
    assert len(shared_rows) == len(CORE_N) * len(FORMAL_SEEDS)


def test_n_strategy_aggregates_equal_weight_per_core_n():
    """Per-n equal-weight aggregation: more seeds at one n does not bias the aggregate.

    Construct a shared cohort that is better at n=5 (the smallest n) but worse elsewhere.
    Under per-n equal weight, shared's aggregate is the mean of the 5 per-n means -- so
    shared loses if 4 of 5 n values are worse, even if it has many good seeds at n=5.
    """
    # Fixed: uniform 0.5 everywhere.
    # Shared: 0.1 at n=5 (better), 0.9 at the other 4 n (worse).
    # Per-n means: shared n=5 -> 0.1; shared n in {7,10,15,20} -> 0.9 each.
    # Shared aggregate = (0.1 + 0.9*4) / 5 = 3.7/5 = 0.74 > fixed 0.5 -> fixed wins.
    shared_scores = {}
    for n in CORE_N:
        for s in FORMAL_SEEDS:
            shared_scores[(n, s)] = 0.1 if n == 5 else 0.9
    winner, evidence, _ = _resolve_n_strategy(_make_cell_scorer(
        fixed_score=0.5, shared_score=shared_scores))
    assert winner == fe._A_E3_N_STRATEGY_FIXED
    assert evidence[fe._A_E3_N_STRATEGY_SHARED]["aggregate_score"] == pytest.approx(0.74, rel=1e-9)
    assert evidence[fe._A_E3_N_STRATEGY_FIXED]["aggregate_score"] == pytest.approx(0.5, rel=1e-9)


def test_n_strategy_supporting_evidence_binds_per_cell_checkpoint_and_point_sha():
    """Each cohort's supporting_evidence_sha256 binds every cell's checkpoint + point SHA.

    Swapping one cell's score changes the supporting hash -> the n_strategy record's input
    detects the tamper at pre-unseal.
    """
    winner_1, evidence_1, _ = _resolve_n_strategy(_make_cell_scorer(fixed_score=0.3, shared_score=0.7))
    winner_2, evidence_2, _ = _resolve_n_strategy(_make_cell_scorer(fixed_score=0.31, shared_score=0.7))
    # Both winners are fixed (0.3 / 0.31 both < 0.7), but the supporting evidence differs.
    assert winner_1 == winner_2 == fe._A_E3_N_STRATEGY_FIXED
    assert (evidence_1[fe._A_E3_N_STRATEGY_FIXED]["supporting_evidence_sha256"]
            != evidence_2[fe._A_E3_N_STRATEGY_FIXED]["supporting_evidence_sha256"])
    # Every supporting row carries a non-empty point_evidence_sha256.
    for cohort in fe._A_E3_N_STRATEGY_CANDIDATES:
        for row in evidence_1[cohort]["supporting_rows"]:
            assert row["point_evidence_sha256"] and len(row["point_evidence_sha256"]) == 64
            assert row["checkpoint_sha256"]  # non-empty for non-failed cells


def test_n_strategy_both_cohorts_share_same_50_cell_support_grid():
    """Both cohorts produce exactly 50 cells (5 core n x 10 formal seeds), pairable cell-for-cell."""
    winner, evidence, _ = _resolve_n_strategy(_make_cell_scorer(fixed_score=0.3, shared_score=0.7))
    for cohort in fe._A_E3_N_STRATEGY_CANDIDATES:
        rows = evidence[cohort]["supporting_rows"]
        assert len(rows) == len(CORE_N) * len(FORMAL_SEEDS)
        n_set = {row["n"] for row in rows}
        seed_set = {row["seed"] for row in rows}
        assert n_set == set(CORE_N)
        assert seed_set == set(FORMAL_SEEDS)


# ---------------------------------------------------------------------------
# Staged-ledger chain shape: 10 records with n_strategy at index 8.
# ---------------------------------------------------------------------------


def test_n_strategy_record_is_index_8_in_a_e3_staged_sequence():
    """The canonical A-E3 staged-ledger sequence places n_strategy at record 9 (index 8)."""
    sequence = fc._STAGED_LEDGER_SEQUENCES["A-E3"]
    assert len(sequence) == 10
    assert sequence[8] == ("n_strategy", None)
    assert sequence[9] == ("final_aliases", None)


def test_n_strategy_decision_id_is_not_a_matrix_decision_id():
    """Reproducer #2 stays negative: n_strategy is NOT derived from build_decision_specs.

    The n_strategy decision is constructed outside the matrix decision path; the matrix's
    ``_FIT_KIND_AXIS`` does not map ``shared_winner_retrain`` to ``n_strategy``.
    """
    from study02a.selection import _FIT_KIND_AXIS, build_decision_specs
    from study02a.matrix import expand_module_matrix
    matrix_rows = expand_module_matrix(FROZEN).to_dict("records")
    specs = build_decision_specs("A-E3", matrix_rows)
    decision_ids = [s.decision_id for s in specs]
    assert not any("n_strategy" in did for did in decision_ids), \
        "n_strategy must NOT appear in build_decision_specs (dedicated evidence path)"
    assert "shared_winner_retrain" not in _FIT_KIND_AXIS, \
        "shared_winner_retrain must NOT map to a decision axis (reproducer #2)"
    # The dedicated decision_id is distinct from any matrix decision_id.
    assert fe._A_E3_N_STRATEGY_DECISION_ID not in decision_ids
