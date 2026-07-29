"""Blocker reproducer tests for de25710 (Study/02 A-E3 orchestration R1).

These tests document the three blockers (A / B / C) identified at de25710.
Blocker A was resolved by R3-A (output-form contract). Blocker C was resolved
by R3-C (versioned cross-commit authority). Blocker B remains a negative
reproducer. Each test name carries ``blocker_reproducer`` so they can be
selected together::

    python -m pytest python/tests -k "blocker_reproducer" -q

Blockers (cross-referenced in coworker/reports/2026-07-28-study02-a-e3-orchestration-r1.md)
---------------------------------------------------------------------------------------
* A (scientific contract ambiguity) -- RESOLVED BY R3-A: see
  ``test_r3_a_fixed_joint_vs_independent_now_contrastive`` below.
* B (no n_strategy decision): the decision engine derives an ``output_form``
  decision for A-E3 but no ``n_strategy`` decision -- remains a negative reproducer.
* C (schema / cross-commit replay blockers) -- RESOLVED BY R3-C:
  - ``_validate_formal_manifest_snapshot`` now dispatches predecessor schema by
    ``manifest_version`` (v1 7-key r5 legacy accepted; v2 13-key with authority
    triple for new runs); see ``test_r3_c_fixed_version_dispatched_predecessor_*``.
  - ``_verify_chain_consistency`` removed the single-code_commit gate and replaced
    it with per-module independent authority + predecessor authority continuity;
    see ``test_r3_c_fixed_cross_commit_chain_passes_per_module_authority``.

Constraints honoured: no production code is changed beyond the R3-A/R3-B/R3-C
implementation; no real r5 / A-E3 sealed run dir is modified (r5 is read-only
in the dedicated historical-verifier test).
"""

from __future__ import annotations

import inspect
from pathlib import Path
import sys
import types

import pytest
import torch


ROOT = Path(__file__).resolve().parents[2]
STUDY_ROOT = ROOT / "Study" / "02-study-NN参数估计与分位点目标研究"
STUDY_CODE = STUDY_ROOT / "code"
if str(STUDY_CODE) not in sys.path:
    sys.path.insert(0, str(STUDY_CODE))
if str(ROOT / "python") not in sys.path:
    sys.path.insert(0, str(ROOT / "python"))

from study02a import formal_executor as fe  # noqa: E402
from study02a import formal_g3_control as g3c  # noqa: E402
from study02a import output_form_contract as ofc  # noqa: E402
from study02a import training as training_module  # noqa: E402
from study02a.config import load_frozen_config  # noqa: E402
from study02a.formal_config import load_effective_formal_config  # noqa: E402
from study02a.matrix import expand_module_matrix  # noqa: E402
from study02a.models import (  # noqa: E402
    IndependentContainer,
    build_independent_container,
    build_mlp,
    trainable_parameter_count,
)
from study02a.selection import _FIT_KIND_AXIS, build_decision_specs  # noqa: E402
from study02a.training import (  # noqa: E402
    _checkpoint_canonical_bytes,
    select_independent_capacity,
)


FROZEN = load_frozen_config(STUDY_ROOT)
EFFECTIVE = load_effective_formal_config(STUDY_ROOT)
MATRIX_ROWS = expand_module_matrix(FROZEN).to_dict("records")
FROZEN_MATRIX_PATH = STUDY_ROOT / "artifacts" / "pilot" / "G3-matrix" / "experiment_matrix.csv"

# Real commit ids referenced by the R1 report (looked up via ``git rev-parse``);
# used only as string literals in the cross-commit reproducer -- no sealed run
# dir is opened.
_COMMIT_DE25710 = "de25710f752f11c89ce521e4852ffbe25e4dfda6"
_COMMIT_D2A056F = "d2a056fdfe650af9f2992f8ea85f8b2daab2fbb3"


# ============================================================================
# Reproducer #1 -- Blocker A (RESOLVED BY R3-A): at de25710 the joint vs
# ``independent_capacity_matched`` A-E3 arms were NOT contrastive controls -- the
# matrix emitted both under one architecture placeholder, ``resolve_model_factory``
# dispatched on architecture alone, ``build_mlp`` hardcoded ``output_dim=3``, and
# ``select_independent_capacity`` was dead code from the executor's perspective.
# R3-A (output-form contract) fixed all four defects: the resolver grew an
# ``output_form`` kwarg, the independent arm builds a capacity-selected
# ``IndependentContainer`` (three single-output MLP subnetworks), and
# ``select_independent_capacity`` is wired in via the SHA-bound
# ``output_form_contract`` module. The test below was inverted from the negative
# reproducer into a positive confirmation that the two arms are now a real
# contrastive control. (Comprehensive coverage lives in
# ``test_study02a_a_e3_output_form_contract.py``.)
# ============================================================================


def test_r3_a_fixed_joint_vs_independent_now_contrastive():
    """Blocker A (R3-A fixed): the joint and ``independent_capacity_matched``
    A-E3 arms now select structurally distinct model contracts. The matrix still
    emits both arms under one architecture placeholder and differs only in the
    route suffix, but R3-A made that suffix load-bearing: ``resolve_model_factory``
    takes an ``output_form`` kwarg, the independent arm routes through the
    SHA-bound ``output_form_contract`` to a capacity-selected
    ``IndependentContainer``, and ``select_independent_capacity`` is wired into
    the executor's import graph. The two arms are now a contrastive control."""

    joint_rows = [
        r for r in MATRIX_ROWS
        if r["module"] == "A-E3" and r["fit_kind"] == "output_form"
        and r["route"].endswith(":joint")
    ]
    indep_rows = [
        r for r in MATRIX_ROWS
        if r["module"] == "A-E3" and r["fit_kind"] == "output_form"
        and r["route"].endswith(":independent_capacity_matched")
    ]
    assert joint_rows and indep_rows, "A-E3 output_form matrix rows not found"

    # (1) Matrix layer unchanged: both arms still share ONE architecture
    # placeholder -- the distinguishing carrier is the route suffix (R3-A made
    # the suffix load-bearing rather than adding a new matrix column).
    joint_arch = {r["architecture"] for r in joint_rows}
    indep_arch = {r["architecture"] for r in indep_rows}
    assert joint_arch == indep_arch == {"selected:A-E3_architecture"}

    # (2) For matching (n, seed) cells the two arms are identical apart from
    # route / fit_id -- so the SAME sample + seed feeds both arms and the
    # contrast is purely the output_form contract (a clean control).
    joint_by_key = {(r["n"], r["seed"]): r for r in joint_rows}
    indep_by_key = {(r["n"], r["seed"]): r for r in indep_rows}
    common_keys = set(joint_by_key) & set(indep_by_key)
    assert common_keys, "no shared (n, seed) cells between joint and independent arms"
    sample_key = next(iter(common_keys))
    joint_row = dict(joint_by_key[sample_key])
    indep_row = dict(indep_by_key[sample_key])
    for field in ("route", "fit_id"):
        joint_row.pop(field, None)
        indep_row.pop(field, None)
    assert joint_row == indep_row, (
        f"joint vs independent rows differ beyond route/fit_id: "
        f"{joint_row} vs {indep_row}"
    )

    # (3) R3-A: resolve_model_factory now takes ``output_form`` and the source
    # consumes it (inverts de25710's architecture-only signature).
    signature_params = set(inspect.signature(fe.resolve_model_factory).parameters)
    assert "output_form" in signature_params, signature_params
    resolver_source = inspect.getsource(fe.resolve_model_factory)
    assert "output_form" in resolver_source, (
        "resolve_model_factory unexpectedly ignores output_form"
    )
    # And the route -> output_form parser is the bridge the executor uses.
    assert ofc.output_form_from_route("selected:F2_or_V:independent_capacity_matched") \
        == "independent_capacity_matched"
    assert ofc.output_form_from_route("selected:F2_or_V:joint") == "joint"
    assert ofc.output_form_from_route("V") is None

    # (4) R3-A: with a concrete arch, joint and independent resolve to
    # DIFFERENT models -- different type, different parameter count, different
    # state_dict key namespace, different checkpoint bytes (inverts de25710's
    # "both arms fail closed identically / would train the same model").
    input_dim = 15
    joint_factory = fe.resolve_model_factory(
        "m05", FROZEN, input_dim, output_form="joint",
    )
    indep_factory = fe.resolve_model_factory(
        "m05", FROZEN, input_dim, output_form="independent_capacity_matched",
    )
    joint_model = joint_factory()
    indep_model = indep_factory()
    assert type(joint_model).__name__ == "Sequential"
    assert isinstance(indep_model, IndependentContainer)
    assert type(joint_model) is not type(indep_model)
    joint_params = trainable_parameter_count(joint_model)
    indep_params = trainable_parameter_count(indep_model)
    assert joint_params != indep_params, (
        f"joint vs independent param counts must differ: {joint_params} vs {indep_params}"
    )
    joint_keys = set(joint_model.state_dict().keys())
    indep_keys = set(indep_model.state_dict().keys())
    assert joint_keys.isdisjoint(indep_keys), (
        "joint and independent state_dict keys must be disjoint namespaces"
    )
    assert all(k.startswith("subnetworks.") for k in indep_keys), indep_keys
    joint_bytes = _checkpoint_canonical_bytes(joint_model.state_dict())
    indep_bytes = _checkpoint_canonical_bytes(indep_model.state_dict())
    assert joint_bytes != indep_bytes, (
        "joint and independent checkpoint bytes must differ"
    )

    # (5) R3-A: build_mlp is STILL the 3-output joint arm (unchanged); the
    # per-quantile capacity of the independent arm is now expressed via
    # build_independent_container (three single-output subnetworks).
    assert "output_dim" not in inspect.signature(build_mlp).parameters
    joint_last = [m for m in build_mlp(4, [8], "relu", 0.0).modules()
                  if isinstance(m, torch.nn.Linear)][-1]
    assert joint_last.out_features == 3, "build_mlp is the 3-output joint arm"
    indep_container = build_independent_container(4, [8], "relu", 0.0)
    assert len(indep_container.subnetworks) == 3
    sub_last_features = [
        [m for m in sub.modules() if isinstance(m, torch.nn.Linear)][-1].out_features
        for sub in indep_container.subnetworks
    ]
    assert sub_last_features == [1, 1, 1], (
        f"each independent subnetwork must be single-output, got {sub_last_features}"
    )

    # (6) R3-A: select_independent_capacity is now wired into the executor's
    # import graph via the output_form_contract module (inverts de25710's dead
    # code). The strongest proof is end-to-end: the only way resolve_model_factory
    # returns an IndependentContainer is via the contract module's capacity
    # selection, which calls select_independent_capacity.
    assert hasattr(training_module, "select_independent_capacity")
    assert hasattr(ofc, "select_independent_capacity"), (
        "output_form_contract must import select_independent_capacity"
    )
    executor_source = inspect.getsource(fe)
    assert "output_form_contract" in executor_source, (
        "formal_executor must import from the output_form_contract module"
    )
    assert "build_output_form_aware_factory" in executor_source, (
        "formal_executor must wire the contract-aware factory builder"
    )
    assert "output_form_from_route" in executor_source, (
        "formal_executor must wire the route -> output_form parser"
    )
    # And the independent arm's parameter count is the capacity-selected total.
    # Under v2 (R4-2) the independent widths are DERIVED from the joint widths
    # via the deterministic width-scaling rule; the recorded independent widths
    # differ from the joint widths (a smaller derived candidate is always
    # feasible), so the independent model is structurally distinct from joint.
    single_indep_arch = ofc.resolve_independent_capacity("m05", input_dim, FROZEN)
    assert single_indep_arch["independent_trainable_parameters"] == indep_params
    assert single_indep_arch["independent_widths"] != single_indep_arch["joint_widths"]


# ============================================================================
# Reproducer #2 -- Blocker B: no n_strategy decision is derived for A-E3.
# _FIT_KIND_AXIS (selection.py:81-88) maps no fit_kind to the n_strategy
# axis; build_decision_specs therefore produces output_form but no
# n_strategy decision, and shared_winner_retrain fits never compete.
# ============================================================================


def test_blocker_reproducer_no_n_strategy_decision_for_a_e3():
    """Blocker B: build_decision_specs('A-E3', ...) derives the output_form
    decision (joint vs independent_capacity_matched) but NO n_strategy
    decision, and shared_winner_retrain fits never appear in any decision's
    support. The capacity axis (fixed n vs shared) is silently dropped from
    the A-E3 selection plan at de25710."""

    decisions = build_decision_specs("A-E3", MATRIX_ROWS)
    decision_ids = [d.decision_id for d in decisions]

    # (1) No n_strategy decision is derived for A-E3.
    n_strategy_decisions = [did for did in decision_ids if "n_strategy" in did]
    assert not n_strategy_decisions, (
        f"unexpected n_strategy decision(s) for A-E3: {n_strategy_decisions}"
    )

    # (2) The joint vs independent output_form decision IS derived -- this is
    # the only A-E3 capacity-shaped decision in the plan.
    output_form_decisions = [d for d in decisions if d.axis == "output_form"]
    assert len(output_form_decisions) == 1, (
        f"expected exactly one output_form decision, got {len(output_form_decisions)}"
    )
    output_form = output_form_decisions[0]
    assert output_form.decision_id == "output_form:A-E3:selected:F2_or_V"
    candidate_ids = {c.candidate_id for c in output_form.candidates}
    assert candidate_ids == {"joint", "independent_capacity_matched"}, candidate_ids

    # (3) shared_winner_retrain is NOT a competitive fit_kind (absent from
    # _FIT_KIND_AXIS), so the shared-n retrain fits never enter a decision.
    assert "shared_winner_retrain" not in _FIT_KIND_AXIS, (
        "shared_winner_retrain unexpectedly promoted to a competitive axis"
    )

    # (4) Cross-check at the matrix level: shared_winner_retrain fit_ids for
    # A-E3 exist in the frozen plan but never appear in any decision's
    # expected_fit_ids (they are singletons, not competing candidates).
    shared_retrain_fits = {
        r["fit_id"] for r in MATRIX_ROWS
        if r["module"] == "A-E3" and r["fit_kind"] == "shared_winner_retrain"
    }
    assert shared_retrain_fits, "A-E3 shared_winner_retrain rows missing from matrix"
    all_supported_fits: set[str] = set()
    for decision in decisions:
        for candidate in decision.candidates:
            all_supported_fits.update(candidate.expected_fit_ids)
    overlap = shared_retrain_fits & all_supported_fits
    assert not overlap, (
        f"shared_winner_retrain fits unexpectedly compete in a decision: {sorted(overlap)}"
    )


# ============================================================================
# Reproducer #3 -- Blocker C (r5 replay): RESOLVED BY R3-C. de25710 C1 expanded
# the formal manifest predecessor schema from r5's 7 keys to 10 keys without
# versioning, so _require_exact_fields rejected r5's 7-key段. R3-C introduced
# version-dispatched predecessor schemas: ``study02-formal-v1`` (7-key, r5
# legacy) and ``study02-formal-v2`` (13-key = 10 C1 + authority triple). The
# snapshot validator dispatches on ``manifest_version``; v1/v2 field mixing
# fails closed. The test below was rewritten from a negative reproducer (7-key
# rejected) into a positive confirmation that v1 7-key now replays, plus
# negative coverage for schema mixing.
# ============================================================================


# r5-era predecessor段 schema (7 keys; sealed at d2a056f, immutable).
_R5_PREDECESSOR_FIELDS = {
    "module_id", "run_id",
    "selection_trace_path", "selection_trace_sha256",
    "selection_receipt_path", "selection_receipt_sha256",
    "selection_ledger_path",
}

# R3-C v2 predecessor段 schema (13 keys = 10 C1 + authority triple).
_V2_PREDECESSOR_FIELDS = {
    "module_id", "run_id",
    "selection_trace_path", "selection_trace_sha256",
    "selection_receipt_path", "selection_receipt_sha256",
    "selection_ledger_path",
    "selection_staged_ledger_path", "selection_staged_ledger_sha256",
    "resolved_baseline_route",
    "code_commit", "scoped_code_sha256", "authority_sha256",
}


def _build_valid_a_e1_manifest() -> dict:
    """Build a fully valid A-E1 v2 formal manifest (predecessor=None) using the
    frozen matrix + effective config."""
    from study02a.formal_contracts import build_formal_manifest

    return build_formal_manifest(
        effective_config=EFFECTIVE,
        module_id="A-E1",
        run_id="G3-AE1-formal-v1",
        code_commit="a" * 40,
        matrix_path=FROZEN_MATRIX_PATH,
        rule_ids=("A-E1_historical",),
        fit_ids=("G3-fit-0000",),
        role_namespaces={
            "training": "study02/formal/train",
            "validation": "study02/formal/validation",
        },
        screening_seeds=(420001, 420002, 420003),
        formal_seeds=tuple(range(420101, 420111)),
        predecessor=None,
    )


def _to_v1_a_e1_manifest(v2_manifest: dict) -> dict:
    """Downgrade a v2 A-E1 manifest to the r5-era v1 shape (7-key predecessor)."""
    v1 = dict(v2_manifest)
    v1["manifest_version"] = "study02-formal-v1"
    v1_predecessor = dict(v2_manifest["predecessor"])
    v1["predecessor"] = {
        key: v1_predecessor[key] for key in _R5_PREDECESSOR_FIELDS
    }
    return v1


def test_r3_c_fixed_version_dispatched_predecessor_schema_accepts_v1_and_v2():
    """Blocker C (R3-C fixed): _validate_formal_manifest_snapshot now dispatches
    on manifest_version. v1 (study02-formal-v1) accepts the r5-era 7-key
    predecessor段; v2 (study02-formal-v2) requires the 13-key段 with authority
    triple. Schema mixing (v1 version + v2 fields, or vice versa) fails closed."""

    from study02a.formal_contracts import _validate_formal_manifest_snapshot

    v2_manifest = _build_valid_a_e1_manifest()

    # (1) R3-C: build_formal_manifest emits v2 with the 13-key predecessor段.
    assert v2_manifest["manifest_version"] == "study02-formal-v2"
    assert set(v2_manifest["predecessor"]) == _V2_PREDECESSOR_FIELDS, (
        f"v2 predecessor fields: {set(v2_manifest['predecessor'])}"
    )

    # (2) v2 manifest passes the snapshot validator (13-key段 accepted).
    _validate_formal_manifest_snapshot(
        v2_manifest,
        module_id=v2_manifest["module_id"],
        run_id=v2_manifest["run_id"],
        code_commit=v2_manifest["code_commit"],
        effective_config_sha256=v2_manifest["effective_config"]["sha256"],
    )

    # (3) R3-C: a v1 manifest (r5-era 7-key段) is ACCEPTED -- the original blocker
    # is resolved. r5 sealed at d2a056f with this exact 7-key shape.
    v1_manifest = _to_v1_a_e1_manifest(v2_manifest)
    assert v1_manifest["manifest_version"] == "study02-formal-v1"
    assert set(v1_manifest["predecessor"]) == _R5_PREDECESSOR_FIELDS
    _validate_formal_manifest_snapshot(
        v1_manifest,
        module_id=v1_manifest["module_id"],
        run_id=v1_manifest["run_id"],
        code_commit=v1_manifest["code_commit"],
        effective_config_sha256=v1_manifest["effective_config"]["sha256"],
    )

    # (4) Schema mixing: v1 version + v2 13-key段 is rejected (r5-era version
    # cannot carry the new fields -- mixing fails closed).
    mixed_v1_fields = dict(v1_manifest)
    mixed_v1_fields["predecessor"] = dict(v2_manifest["predecessor"])
    with pytest.raises(ValueError, match="formal manifest predecessor schema"):
        _validate_formal_manifest_snapshot(
            mixed_v1_fields,
            module_id=mixed_v1_fields["module_id"],
            run_id=mixed_v1_fields["run_id"],
            code_commit=mixed_v1_fields["code_commit"],
            effective_config_sha256=mixed_v1_fields["effective_config"]["sha256"],
        )

    # (5) Schema mixing: v2 version + v1 7-key段 is rejected.
    mixed_v2_fields = dict(v2_manifest)
    mixed_v2_fields["predecessor"] = dict(v1_manifest["predecessor"])
    with pytest.raises(ValueError, match="formal manifest predecessor schema"):
        _validate_formal_manifest_snapshot(
            mixed_v2_fields,
            module_id=mixed_v2_fields["module_id"],
            run_id=mixed_v2_fields["run_id"],
            code_commit=mixed_v2_fields["code_commit"],
            effective_config_sha256=mixed_v2_fields["effective_config"]["sha256"],
        )


# ============================================================================
# Reproducer #4 -- Blocker C (cross-commit): RESOLVED BY R3-C.
# verify_g3_chain_authority / _verify_chain_consistency previously required all
# three module manifests to share one code_commit (len(set) == 1). R3-C removed
# that gate and replaced it with per-module independent code authority +
# predecessor authority continuity: each downstream's predecessor段 must bind the
# exact authority triple of its predecessor module's sealed manifest. The test
# below was rewritten from a negative reproducer (cross-commit rejected) into a
# positive confirmation that mixed-commit chains now pass, plus negative
# coverage for a forged predecessor authority triple.
# ============================================================================


def test_r3_c_fixed_cross_commit_chain_passes_per_module_authority():
    """Blocker C (R3-C fixed): _verify_chain_consistency no longer requires
    three manifests to share one code_commit. A chain where A-E1 was sealed
    under d2a056f and A-E3/A-E2 under de25710 is ACCEPTED, as long as each
    downstream's predecessor段 binds the correct predecessor authority triple."""

    shared_config_sha = EFFECTIVE.effective_config_sha256
    from study02a.formal_contracts import FROZEN_MATRIX_SHA256
    shared_matrix_sha = FROZEN_MATRIX_SHA256

    def _authority_triple(code_commit: str) -> dict[str, str]:
        return {
            "code_commit": code_commit,
            "scoped_code_sha256": "e" * 64,
            "authority_sha256": "f" * 64,
        }

    def _manifest_with_authority(
        module_id: str, run_id: str, code_commit: str,
        predecessor_module: str | None, predecessor_run: str | None,
        predecessor_triple: dict[str, str] | None,
    ) -> dict:
        return {
            "module_id": module_id,
            "run_id": run_id,
            "code_commit": code_commit,
            "effective_config": {"sha256": shared_config_sha},
            "matrix": {"sha256": shared_matrix_sha},
            "predecessor": (
                {"module_id": "none", "run_id": "none"}
                if predecessor_module is None
                else {
                    "module_id": predecessor_module,
                    "run_id": predecessor_run,
                    **predecessor_triple,
                }
            ),
            "scheduler": {"authority": _authority_triple(code_commit)},
        }

    ae1_triple = _authority_triple(_COMMIT_D2A056F)
    ae3_triple = _authority_triple(_COMMIT_DE25710)

    ae1_manifest = _manifest_with_authority(
        "A-E1", "r5", _COMMIT_D2A056F, None, None, None,
    )
    ae3_manifest = _manifest_with_authority(
        "A-E3", "ae3-run", _COMMIT_DE25710, "A-E1", "r5", ae1_triple,
    )
    ae2_manifest = _manifest_with_authority(
        "A-E2", "ae2-run", _COMMIT_DE25710, "A-E3", "ae3-run", ae3_triple,
    )
    chain = types.SimpleNamespace(
        ae1_run_id="r5",
        ae3_run_id="ae3-run",
        ae2_run_id="ae2-run",
    )

    code_commits = {
        ae1_manifest["code_commit"],
        ae3_manifest["code_commit"],
        ae2_manifest["code_commit"],
    }
    assert len(code_commits) == 2, (
        f"fixture invariant: expected 2 distinct commits, got {len(code_commits)}"
    )

    # R3-C: mixed-commit chain PASSES (the old blocker is resolved).
    g3c._verify_chain_consistency(ae1_manifest, ae3_manifest, ae2_manifest, chain)

    # Negative: a forged predecessor authority triple is rejected. A-E3's
    # predecessor段 claims A-E1's authority is all-"a"*64 but A-E1's sealed
    # manifest has a different triple.
    forged_ae3 = _manifest_with_authority(
        "A-E3", "ae3-run", _COMMIT_DE25710, "A-E1", "r5",
        {"code_commit": _COMMIT_D2A056F, "scoped_code_sha256": "a" * 64, "authority_sha256": "a" * 64},
    )
    with pytest.raises(ValueError, match="predecessor authority discontinuity"):
        g3c._verify_chain_consistency(ae1_manifest, forged_ae3, ae2_manifest, chain)

    # Negative: missing authority triple fields (v1段 under v2 expectations) rejected.
    missing_triple_ae3 = dict(ae3_manifest)
    missing_triple_ae3["predecessor"] = {
        "module_id": "A-E1",
        "run_id": "r5",
    }
    with pytest.raises(ValueError, match="missing authority triple field"):
        g3c._verify_chain_consistency(
            ae1_manifest, missing_triple_ae3, ae2_manifest, chain,
        )
