"""R3-A / R4-2 output-form contract tests (Study/02 A-E3 orchestration).

Positive coverage for the A-E3 output-form contract. R3-A (v1) made the ``joint``
and ``independent_capacity_matched`` A-E3 arms a contrastive control. R4-2 (v2)
removes v1's capacity-selection failure mode: instead of selecting the
independent arm from the frozen ``m01..m12`` candidate set (which had no feasible
candidate for ``joint=m01``), v2 DERIVES the independent widths from the joint
widths via a deterministic width-scaling rule that always includes the all-1s
widths, so a feasible candidate exists for every frozen joint architecture and
every fixed-route ``input_dim``. The contract is now SHA-bound under v2 (id
``A-E3-output-form-contract-v2``); v1 is retained only for SHA audit and is NOT
used for formal execution.

These tests pin every load-bearing property of the v2 contract so a future
regression cannot silently:

* weaken the SHA binding (v2 must validate; v1 must still validate as the audit
  reference);
* break ``output_form_from_route`` parsing;
* break the width-scaling derivation (all-1s always present; deterministic;
  non-empty);
* re-introduce v1's hard-fail (``resolve_independent_capacity`` now never fails
  for a legitimate frozen arch + input_dim);
* collapse the two arms into the same model (structural distinctness: type,
  parameter count, state_dict key namespace, checkpoint bytes).

Selected via::

    python -m pytest python/tests -k "output_form or independent or joint or width_scaling" -q
"""

from __future__ import annotations

import inspect
import itertools
from pathlib import Path
import sys

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
from study02a import output_form_contract as ofc  # noqa: E402
from study02a.config import load_frozen_config  # noqa: E402
from study02a.formal_contracts import (  # noqa: E402
    APPROVED_A_E3_OUTPUT_FORM_CONTRACT_SHA256,
    APPROVED_A_E3_OUTPUT_FORM_CONTRACT_V2_SHA256,
)
from study02a.models import (  # noqa: E402
    IndependentContainer,
    _feed_forward,
    build_independent_container,
    build_mlp,
    decode_model_output,
    trainable_parameter_count,
)
from study02a.training import (  # noqa: E402
    _checkpoint_canonical_bytes,
    _checkpoint_hash,
    fit_candidate,
    load_checkpoint,
    select_independent_capacity,
)


FROZEN = load_frozen_config(STUDY_ROOT)

# Every frozen MLP architecture that can be selected as the A-E3 joint model.
FROZEN_ARCHITECTURES = [
    (str(entry["id"]),
     tuple(int(w) for w in entry["widths"]),
     str(entry["activation"]),
     float(entry["dropout"]))
    for entry in FROZEN.search["mlp_stage1_architectures"]
]
# Every fixed-route input_dim that actually occurs for the A-E3 output_form module.
# The output_form route resolves to V (sorted_z_fixed_n, input_dim = n) at the core
# sample sizes, or to F2 (input_dim = 15). V covers {5,7,10,15,20}; F2 adds nothing
# new (15 is already in V's set).
CORE_INPUT_DIMS = [int(n) for n in FROZEN.protocol["sample_sizes"]["core"]]
assert CORE_INPUT_DIMS == [5, 7, 10, 15, 20]


# ============================================================================
# Contract SHA binding (fail-closed on tamper) -- v2 is formal, v1 is audit
# ============================================================================


def test_v2_contract_sha_matches_frozen_mirror():
    """The ACTIVE FORMAL contract is v2: its canonical-JSON SHA matches both the
    in-module ``CONTRACT_SHA256`` constant and the cross-module v2 mirror in
    ``formal_contracts`` (the authority the executor records in evidence)."""
    import hashlib
    import json

    live_sha = hashlib.sha256(
        json.dumps(ofc._CONTRACT, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert live_sha == ofc.CONTRACT_SHA256
    assert live_sha == APPROVED_A_E3_OUTPUT_FORM_CONTRACT_V2_SHA256
    assert ofc._CONTRACT is ofc._CONTRACT_V2
    assert ofc.CONTRACT_SHA256 == ofc.CONTRACT_V2_SHA256


def test_v1_contract_sha_matches_frozen_mirror_for_audit():
    """v1 is RETAINED for SHA audit only (not used for formal execution). Its SHA
    is independently frozen and must still validate so a future reader can verify
    the v1 contract bytes have not been tampered with."""
    import hashlib
    import json

    live_v1_sha = hashlib.sha256(
        json.dumps(ofc._CONTRACT_V1, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    assert live_v1_sha == ofc.CONTRACT_V1_SHA256
    assert live_v1_sha == APPROVED_A_E3_OUTPUT_FORM_CONTRACT_SHA256
    # v1 and v2 are distinct contracts with distinct SHAs.
    assert ofc.CONTRACT_V1_SHA256 != ofc.CONTRACT_V2_SHA256
    assert ofc._CONTRACT_V1 is not ofc._CONTRACT_V2


def test_load_output_form_contract_returns_v2_and_validates_sha():
    """``load_output_form_contract`` re-computes the SHA on every call and returns
    the v2 contract dict only when it matches the frozen v2 SHA."""
    contract = ofc.load_output_form_contract()
    assert contract is ofc._CONTRACT_V2
    assert contract["contract_id"] == "A-E3-output-form-contract-v2"
    assert contract["capacity_selection"]["ceiling_ratio"] == 1.05
    assert contract["independent"]["subnetwork_count"] == 3
    assert contract["independent"]["output_dim_per_subnetwork"] == 1
    # v2-specific: the width-scaling rule is part of the frozen contract.
    assert "width_scaling_rule" in contract["independent"]
    assert "algorithm" in contract["independent"]["width_scaling_rule"]
    assert "all_ones_feasibility" in contract["capacity_selection"]
    assert "no_scientific_failure" in contract["capacity_selection"]


def test_load_output_form_contract_v1_returns_v1_and_validates_sha():
    """``load_output_form_contract_v1`` re-computes the v1 SHA and returns the v1
    contract dict only when it matches (audit-only path)."""
    contract = ofc.load_output_form_contract_v1()
    assert contract is ofc._CONTRACT_V1
    assert contract["contract_id"] == "A-E3-output-form-contract-v1"


def test_load_output_form_contract_fails_closed_on_tamper(monkeypatch):
    """Any drift in the v2 contract dict -- here a mutated contract_id -- must
    fail closed before any model factory resolves."""
    tampered = dict(ofc._CONTRACT)
    tampered["contract_id"] = "tampered-contract-id"
    monkeypatch.setattr(ofc, "_CONTRACT", tampered)
    with pytest.raises(ValueError, match="v2 SHA-256 mismatch"):
        ofc.load_output_form_contract()


def test_load_output_form_contract_v1_fails_closed_on_tamper(monkeypatch):
    """The v1 audit path is also fail-closed on tamper."""
    tampered = dict(ofc._CONTRACT_V1)
    tampered["contract_id"] = "tampered-v1"
    monkeypatch.setattr(ofc, "_CONTRACT_V1", tampered)
    with pytest.raises(ValueError, match="v1 SHA-256 mismatch"):
        ofc.load_output_form_contract_v1()


def test_build_output_form_aware_factory_validates_sha_on_every_call(monkeypatch):
    """The factory builder validates the v2 contract SHA on every call (joint and
    independent), so a tampered v2 contract cannot produce either arm's model."""
    tampered = dict(ofc._CONTRACT)
    tampered["capacity_selection"] = dict(tampered["capacity_selection"], ceiling_ratio=1.50)
    monkeypatch.setattr(ofc, "_CONTRACT", tampered)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        ofc.build_output_form_aware_factory("m05", "joint", FROZEN, 15)
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        ofc.build_output_form_aware_factory("m05", "independent_capacity_matched", FROZEN, 15)


# ============================================================================
# output_form_from_route
# ============================================================================


@pytest.mark.parametrize("route, expected", [
    ("V:joint", "joint"),
    ("V:independent_capacity_matched", "independent_capacity_matched"),
    ("selected:F2_or_V:joint", "joint"),
    ("selected:F2_or_V:independent_capacity_matched", "independent_capacity_matched"),
    ("V", None),
    ("S", None),
    ("F2", None),
    ("F2_or_V", None),
    ("", None),
    ("V:unknown", None),
    ("V:Independent_Capacity_Matched", None),  # case-sensitive
])
def test_output_form_from_route_parses_frozen_shapes(route, expected):
    assert ofc.output_form_from_route(route) == expected


def test_output_form_from_route_handles_matrix_routes():
    """Every route the frozen A-E3 output_form matrix emits is parsed, and the
    non-output_form A-E3 routes (search/loss-screen) carry no suffix."""
    from study02a.matrix import expand_module_matrix

    rows = expand_module_matrix(FROZEN).to_dict("records")
    of_routes = {
        str(r["route"]) for r in rows
        if str(r["module"]) == "A-E3" and str(r["fit_kind"]) == "output_form"
    }
    parsed = {route: ofc.output_form_from_route(route) for route in of_routes}
    assert set(parsed.values()) == {"joint", "independent_capacity_matched"}
    assert all(parsed.values())  # every output_form route carries a suffix


# ============================================================================
# IndependentContainer model contract (v2: derived widths feed the same container)
# ============================================================================


def test_independent_container_has_three_single_output_subnetworks():
    """Three subnetworks, each terminating in a 1-output head, all sharing the
    SAME frozen hidden spec (widths / activation / dropout)."""
    input_dim, widths, activation, dropout = 6, (32, 16), "silu", 0.1
    container = IndependentContainer(input_dim, widths, activation, dropout)
    assert len(container.subnetworks) == 3
    last_linears = [
        [m for m in sub.modules() if isinstance(m, torch.nn.Linear)][-1]
        for sub in container.subnetworks
    ]
    assert [lin.out_features for lin in last_linears] == [1, 1, 1]
    # Each subnetwork reuses the same hidden spec.
    for sub in container.subnetworks:
        linears = [m for m in sub.modules() if isinstance(m, torch.nn.Linear)]
        assert linears[0].in_features == input_dim
        assert [l.out_features for l in linears[:-1]] == list(widths)


def test_independent_container_forward_is_N_by_3():
    container = IndependentContainer(8, (64, 32), "relu", 0.0)
    x = torch.randn(5, 8)
    out = container(x)
    assert out.shape == (5, 3)


def test_independent_container_parameters_are_not_shared():
    """No parameter tensor is shared across the three subnetworks; each
    parameter object has a unique python id and trains independently."""
    container = IndependentContainer(5, (16,), "relu", 0.0)
    ids: list[int] = []
    for sub in container.subnetworks:
        for param in sub.parameters():
            ids.append(id(param))
    assert len(ids) == len(set(ids)), "parameter tensors must not be shared"
    # Mutating one subnetwork's parameter must not change the others.
    container.subnetworks[0][0].weight.data.fill_(123.0)
    assert not torch.allclose(
        container.subnetworks[0][0].weight, container.subnetworks[1][0].weight
    )


def test_independent_container_trainable_count_is_three_subnetworks():
    """trainable_parameter_count(container) == 3 * trainable_parameter_count
    of one single-output subnetwork built from the same spec."""
    input_dim, widths, activation, dropout = 7, (32, 16, 8), "silu", 0.1
    single = _feed_forward(input_dim, widths, 1, activation, dropout)
    container = IndependentContainer(input_dim, widths, activation, dropout)
    assert trainable_parameter_count(container) == 3 * trainable_parameter_count(single)


def test_independent_container_forward_decodes_to_valid_weibull_params():
    """The (N, 3) raw output is consumable by the shared ``decode_model_output``
    -- the target / decode contract is unchanged for the independent arm."""
    container = IndependentContainer(4, (8,), "relu", 0.0)
    raw = container(torch.randn(3, 4))
    location = torch.tensor([100.0, 50.0, 200.0])
    scale = torch.tensor([20.0, 10.0, 40.0])
    decoded = decode_model_output(raw, location, scale)
    assert decoded.shape == (3, 3)
    assert torch.isfinite(decoded).all()
    assert (decoded[:, 0] > 0).all()  # beta > 0
    assert (decoded[:, 1] > 0).all()  # eta > 0
    assert (decoded[:, 2] < location).all()  # gamma < location


# ============================================================================
# derive_independent_widths (v2 width-scaling rule)
# ============================================================================


def test_derive_independent_widths_always_includes_all_ones():
    """k=1 yields widths all-1s, which is always the FIRST candidate (smallest)."""
    for _, W, _, _ in FROZEN_ARCHITECTURES:
        candidates = ofc.derive_independent_widths(W)
        assert candidates[0] == (1,) * len(W), (W, candidates[0])
        assert (1,) * len(W) in candidates


def test_derive_independent_widths_always_includes_joint_widths():
    """k=M yields the original joint widths, which is always the LAST candidate."""
    for _, W, _, _ in FROZEN_ARCHITECTURES:
        candidates = ofc.derive_independent_widths(W)
        assert candidates[-1] == tuple(W), (W, candidates[-1])
        assert tuple(W) in candidates


def test_derive_independent_widths_is_deterministic_and_sorted():
    """The output is pure in the input widths and ordered k-ascending (smallest
    to largest), deduplicated."""
    for _, W, _, _ in FROZEN_ARCHITECTURES:
        c1 = ofc.derive_independent_widths(W)
        c2 = ofc.derive_independent_widths(tuple(W))  # new tuple, same values
        assert c1 == c2
        # No duplicates.
        assert len(c1) == len(set(c1))
        # k-ascending => each candidate's sum is non-decreasing.
        sums = [sum(c) for c in c1]
        assert sums == sorted(sums)


def test_derive_independent_widths_matches_explicit_formula():
    """The derivation matches the floor(w*k/M) formula exactly for one arch."""
    W = (128, 64, 32)
    M = max(W)
    candidates = ofc.derive_independent_widths(W)
    # Check k=1, k=2, k=M explicitly.
    assert candidates[0] == (max(1, 128 * 1 // M), max(1, 64 * 1 // M), max(1, 32 * 1 // M))
    k2 = (max(1, 128 * 2 // M), max(1, 64 * 2 // M), max(1, 32 * 2 // M))
    if k2 != candidates[0]:  # k=2 deduplicated against k=1?
        assert k2 in candidates
    assert candidates[-1] == (128, 64, 32)


def test_derive_independent_widths_rejects_degenerate_input():
    """Empty widths or non-positive widths are contract violations."""
    with pytest.raises(ValueError, match="non-empty"):
        ofc.derive_independent_widths([])
    with pytest.raises(ValueError, match="positive ints"):
        ofc.derive_independent_widths([0, 32])
    with pytest.raises(ValueError, match="positive ints"):
        ofc.derive_independent_widths([64, -1])


# ============================================================================
# select_independent_capacity (key-type agnostic: v1 string keys OR v2 tuple keys)
# ============================================================================


def test_select_independent_capacity_primary_picks_closest_under_ceiling():
    """Primary rule: among candidates whose total <= joint * 1.05, the closest
    to joint wins (joint=1000, ceiling=1050)."""
    selected = select_independent_capacity(
        joint_count=1000,
        candidate_counts={"a": 700, "b": 980, "c": 1040, "d": 1100},
    )
    assert selected == ("b", 980)  # 980 <= 1050 and |980-1000|=20 is closest


def test_select_independent_capacity_allows_up_to_ceiling_inclusive():
    """A candidate exactly at the ceiling (joint * 1.05) is eligible."""
    selected = select_independent_capacity(
        joint_count=100, candidate_counts={"a": 105, "b": 60},
    )
    # 105 <= 1.05*100 = 105.0 -> eligible; |105-100|=5 < |60-100|=40 -> a wins.
    assert selected == ("a", 105)


def test_select_independent_capacity_tie_break_is_key_ascending():
    """When two candidates are equidistant from joint, the lexicographically
    smaller candidate key wins. Works for both string keys (v1) and tuple keys
    (v2)."""
    # String keys (v1 arch ids): lexicographic.
    selected = select_independent_capacity(
        joint_count=100, candidate_counts={"b": 98, "a": 98, "c": 98},
    )
    assert selected == ("a", 98)
    # Arch-id ordering is lexicographic, not numeric.
    selected = select_independent_capacity(
        joint_count=100, candidate_counts={"m10": 90, "m02": 90},
    )
    assert selected == ("m02", 90)
    # Tuple keys (v2 derived widths): lexicographic by tuple natural ordering.
    selected = select_independent_capacity(
        joint_count=100,
        candidate_counts={(16, 8): 90, (8, 4): 90, (32, 16): 90},
    )
    assert selected == ((8, 4), 90)


def test_select_independent_capacity_hard_fails_when_every_candidate_exceeds_joint():
    """If every candidate's total exceeds joint (and therefore the ceiling),
    selection fails closed. Under v2 this never fires for a legitimate derived
    candidate set (all-1s is always feasible); the raise indicates a contract /
    infrastructure error, not a scientific failure."""
    with pytest.raises(ValueError, match="capacity contract"):
        select_independent_capacity(
            joint_count=100, candidate_counts={"a": 106, "b": 150, "c": 200},
        )


def test_select_independent_capacity_fallback_tier_is_logically_subsumed():
    """The written fallback tier (``nearest <= joint``) is logically subsumed
    by the primary tier (``<= joint * 1.05``): for non-negative ``joint`` any
    candidate ``<= joint`` is also ``<= 1.05 * joint``, so the primary eligible
    set can only be empty when the fallback set is empty too. The fallback
    branch therefore never returns a value -- it is defensive code matching the
    contract's three-tier spec, and the hard-fail fires whenever primary is
    empty. Verified exhaustively over a small grid plus boundary inputs."""
    # Boundary: a candidate at exactly joint goes through primary, not fallback.
    assert select_independent_capacity(100, {"a": 100}) == ("a", 100)
    assert select_independent_capacity(100, {"a": 50, "b": 130}) == ("a", 50)
    # When all candidates exceed the ceiling (and thus joint), hard-fail.
    with pytest.raises(ValueError):
        select_independent_capacity(100, {"a": 106, "b": 200})

    # Exhaustive property: primary empty => fallback empty (non-negative joint).
    for joint in range(0, 201, 10):
        for ca, cb, cc in itertools.product(range(0, 301, 15), repeat=3):
            candidates = {"a": ca, "b": cb, "c": cc}
            primary_eligible = [v for v in candidates.values() if v <= 1.05 * joint]
            fallback_eligible = [v for v in candidates.values() if v <= joint]
            if not primary_eligible:
                assert not fallback_eligible, (
                    f"fallback must be empty when primary is empty "
                    f"(joint={joint}, candidates={candidates})"
                )


# ============================================================================
# resolve_model_factory(output_form=...) dispatch + backward compat
# ============================================================================


def test_resolve_model_factory_output_form_dispatch():
    """joint / None -> the standard 3-output MLP (Sequential);
    independent_capacity_matched -> an IndependentContainer."""
    input_dim = 12
    none_model = fe.resolve_model_factory("m01", FROZEN, input_dim)()
    joint_model = fe.resolve_model_factory("m01", FROZEN, input_dim, output_form="joint")()
    indep_model = fe.resolve_model_factory(
        "m05", FROZEN, input_dim, output_form="independent_capacity_matched",
    )()
    assert type(none_model).__name__ == "Sequential"
    assert type(joint_model).__name__ == "Sequential"
    assert isinstance(indep_model, IndependentContainer)


def test_resolve_model_factory_backward_compat_selected_still_fails_closed():
    """``selected:*`` placeholders still require selection-trace resolution
    (D7/D8) and fail closed; R3-A/R4-2 did not weaken the deferred-resolution guard."""
    with pytest.raises(NotImplementedError):
        fe.resolve_model_factory("selected:A-E3_architecture", FROZEN, input_dim=15)
    # And output_form=None does not bypass the guard.
    with pytest.raises(NotImplementedError):
        fe.resolve_model_factory(
            "selected:A-E3_architecture", FROZEN, input_dim=15, output_form=None,
        )


def test_resolve_model_factory_rejects_unknown_output_form():
    with pytest.raises(ValueError, match="unknown output_form"):
        fe.resolve_model_factory("m01", FROZEN, input_dim=8, output_form="bogus")


def test_resolve_model_factory_independent_requires_positive_input_dim():
    """The independent arm must build a concrete model now (no deferred
    placeholder), so a missing / non-positive input_dim fails closed."""
    with pytest.raises(ValueError):
        fe.resolve_model_factory(
            "m05", FROZEN, input_dim=None, output_form="independent_capacity_matched",
        )
    with pytest.raises(ValueError):
        fe.resolve_model_factory(
            "m05", FROZEN, input_dim=0, output_form="independent_capacity_matched",
        )


# ============================================================================
# resolve_independent_capacity (v2: derive widths from joint, NEVER hard-fails)
# ============================================================================


def test_resolve_independent_capacity_returns_v2_metadata_for_joint_arch():
    """v2 metadata records the joint architecture, JOINT WIDTHS, derived
    INDEPENDENT WIDTHS, exact parameter counts, the derived candidate set, the
    ceiling, and the v2 selection rule."""
    cap = ofc.resolve_independent_capacity("m05", 15, FROZEN)
    expected_keys = {
        "contract_id", "form",
        "joint_architecture_id", "joint_widths", "joint_activation", "joint_dropout",
        "joint_trainable_parameters",
        "independent_widths", "independent_trainable_parameters",
        "derived_candidate_widths",
        "ceiling_ratio", "ceiling", "selection_rule", "width_scaling_rule",
    }
    assert set(cap) == expected_keys, set(cap) ^ expected_keys
    assert cap["contract_id"] == "A-E3-output-form-contract-v2"
    assert cap["form"] == "independent_capacity_matched"
    assert cap["joint_architecture_id"] == "m05"
    assert cap["joint_widths"] == [128, 64, 32]
    assert cap["joint_activation"] == "relu"
    assert cap["joint_dropout"] == 0.0
    assert cap["ceiling_ratio"] == 1.05
    assert cap["ceiling"] == int(round(1.05 * cap["joint_trainable_parameters"]))
    assert cap["selection_rule"] == "select_independent_capacity_v2"
    # derived_candidate_widths is a non-empty list of {widths, total_trainable_parameters}.
    assert isinstance(cap["derived_candidate_widths"], list)
    assert len(cap["derived_candidate_widths"]) >= 2  # at least all-1s and joint widths
    for entry in cap["derived_candidate_widths"]:
        assert set(entry) == {"widths", "total_trainable_parameters"}
        assert isinstance(entry["widths"], list)
        assert isinstance(entry["total_trainable_parameters"], int)


def test_resolve_independent_capacity_for_m01_now_succeeds_v2():
    """v2 removes v1's hard-fail: for joint=m01 (the smallest arch) the
    independent arm now resolves successfully because v2 derives the all-1s
    candidate (and others), guaranteeing a feasible selection. Under v1 this
    cell raised ValueError (a scientific failure); under v2 it is always a
    real, structurally distinct IndependentContainer."""
    cap = ofc.resolve_independent_capacity("m01", 15, FROZEN)
    assert cap["joint_architecture_id"] == "m01"
    assert cap["independent_trainable_parameters"] <= cap["ceiling"]
    # Independent total is strictly below joint (the all-1s candidate and its
    # neighbours are well below the joint count for m01).
    assert cap["independent_trainable_parameters"] < cap["joint_trainable_parameters"]
    # The all-1s candidate is present in the derived candidate set.
    all_ones = [1, 1]
    assert any(e["widths"] == all_ones for e in cap["derived_candidate_widths"])


def test_resolve_independent_capacity_picks_closest_under_ceiling():
    """For joint=m09 (input_dim=15) the selected derived widths produce a total
    <= 105% of joint and close to joint (the v2 selection rule)."""
    cap = ofc.resolve_independent_capacity("m09", 15, FROZEN)
    assert cap["joint_architecture_id"] == "m09"
    assert cap["independent_trainable_parameters"] <= cap["ceiling"]
    ratio = cap["independent_trainable_parameters"] / cap["joint_trainable_parameters"]
    # Close to 1.0 (the v2 rule picks the closest feasible derived candidate).
    assert 0.90 <= ratio <= 1.05, ratio


def test_resolve_independent_capacity_independent_below_joint_or_within_ceiling():
    """For every frozen arch the v2 selection either stays below joint or within
    the 105% ceiling -- and is always feasible (no raise)."""
    for arch_id, W, _, _ in FROZEN_ARCHITECTURES:
        for input_dim in CORE_INPUT_DIMS:
            cap = ofc.resolve_independent_capacity(arch_id, input_dim, FROZEN)
            assert cap["independent_trainable_parameters"] <= cap["ceiling"], (
                f"{arch_id} dim={input_dim}: indep={cap['independent_trainable_parameters']} "
                f"> ceiling={cap['ceiling']}"
            )


def test_resolve_independent_capacity_recorded_counts_match_built_models():
    """The recorded parameter counts equal the trainable parameter counts of the
    models built from the recorded widths -- the evidence-binding path
    reconstructs the exact factory from the metadata alone."""
    for arch_id, W, act, dp in FROZEN_ARCHITECTURES:
        input_dim = 15
        cap = ofc.resolve_independent_capacity(arch_id, input_dim, FROZEN)
        # Joint model from recorded joint_widths + activation + dropout.
        joint_model = build_mlp(
            input_dim, tuple(cap["joint_widths"]), cap["joint_activation"], cap["joint_dropout"],
        )
        assert cap["joint_trainable_parameters"] == trainable_parameter_count(joint_model)
        # Independent container from recorded independent_widths + same activation/dropout.
        indep_model = build_independent_container(
            input_dim, tuple(cap["independent_widths"]),
            cap["joint_activation"], cap["joint_dropout"],
        )
        assert cap["independent_trainable_parameters"] == trainable_parameter_count(indep_model)


def test_joint_trainable_parameter_count_matches_built_model():
    """The capacity selector's joint count is exactly the trainable parameter
    count of the joint 3-output MLP built from the same arch -- the contrastive
    control baseline."""
    for arch in ("m01", "m05", "m09"):
        entry = next(e for e in FROZEN.search["mlp_stage1_architectures"] if e["id"] == arch)
        widths = tuple(int(w) for w in entry["widths"])
        expected = trainable_parameter_count(
            build_mlp(15, widths, entry["activation"], float(entry["dropout"]))
        )
        assert ofc.joint_trainable_parameter_count(arch, 15, FROZEN) == expected


def test_resolve_independent_capacity_is_pure_in_arch_and_input_dim():
    """``resolve_independent_capacity`` is deterministic in (arch, input_dim,
    frozen): the same cell always selects the same derived widths and parameter
    counts."""
    for arch_id, _, _, _ in FROZEN_ARCHITECTURES:
        c1 = ofc.resolve_independent_capacity(arch_id, 12, FROZEN)
        c2 = ofc.resolve_independent_capacity(arch_id, 12, FROZEN)
        assert c1 == c2


# ============================================================================
# ENUMERATION PROOF (R4-2 Codex BLOCK): all frozen MLP × all fixed-route
# input_dim yield a feasible, deterministic, structurally distinct independent
# resolution -- no candidate-dependent crash, no scientific failure.
# ============================================================================


def test_enumeration_proof_all_frozen_archs_and_input_dims_feasible_and_distinct():
    """Codex R4-2 enumeration proof. For every (frozen m0X joint architecture,
    fixed-route input_dim) cell the v2 contract must:

    1. derive a candidate set with at least one member, containing the all-1s
       widths (k=1) -- so a feasible candidate always exists;
    2. ``select_independent_capacity`` selects WITHOUT raising (capacity
       selection never fail-closes for a legitimate derived set);
    3. the selected independent total is ``<= joint * 1.05``;
    4. the selection is deterministic (re-call reproduces the exact same widths
       and counts);
    5. the joint (3-output MLP) and independent (IndependentContainer) models
       are structurally distinct: different type, different parameter count,
       disjoint state_dict key namespaces.

    This is the property v1 violated (v1 fail-closed for joint=m01). v2 holds
    for all 60 = 12 architectures x 5 core input_dim cells.
    """
    seen_cells: set[tuple[str, int]] = set()
    for arch_id, joint_widths, activation, dropout in FROZEN_ARCHITECTURES:
        for input_dim in CORE_INPUT_DIMS:
            cell = (arch_id, input_dim)
            assert cell not in seen_cells  # paranoia
            seen_cells.add(cell)

            # (1) Width-scaling derivation: non-empty, contains all-1s.
            candidates = ofc.derive_independent_widths(joint_widths)
            assert candidates, f"empty derived set for {arch_id} W={joint_widths}"
            assert (1,) * len(joint_widths) in candidates, (
                f"all-1s missing for {arch_id} W={joint_widths}: {candidates}"
            )

            # (2) Capacity resolution never raises.
            cap = ofc.resolve_independent_capacity(arch_id, input_dim, FROZEN)

            # (3) Selected total <= 105% joint.
            assert cap["independent_trainable_parameters"] <= cap["ceiling"], (
                f"{arch_id} dim={input_dim}: indep={cap['independent_trainable_parameters']} "
                f"> ceiling={cap['ceiling']}"
            )
            # And it equals one of the derived candidate totals.
            derived_totals = {
                tuple(e["widths"]): e["total_trainable_parameters"]
                for e in cap["derived_candidate_widths"]
            }
            assert tuple(cap["independent_widths"]) in derived_totals
            assert (
                cap["independent_trainable_parameters"]
                == derived_totals[tuple(cap["independent_widths"])]
            )

            # (4) Determinism: re-call reproduces exactly.
            cap2 = ofc.resolve_independent_capacity(arch_id, input_dim, FROZEN)
            assert cap == cap2, f"non-deterministic for {arch_id} dim={input_dim}"

            # (5) Structural distinctness: type, params, state_dict keys.
            joint_model = build_mlp(input_dim, joint_widths, activation, dropout)
            factory, _ = ofc.build_output_form_aware_factory(
                arch_id, "independent_capacity_matched", FROZEN, input_dim,
            )
            indep_model = factory()
            assert type(joint_model) is not type(indep_model)
            assert trainable_parameter_count(joint_model) != trainable_parameter_count(indep_model)
            joint_keys = set(joint_model.state_dict())
            indep_keys = set(indep_model.state_dict())
            assert joint_keys.isdisjoint(indep_keys)
            assert all(k.startswith("subnetworks.") for k in indep_keys)

    # Sanity: we exercised the full cross product.
    assert len(seen_cells) == len(FROZEN_ARCHITECTURES) * len(CORE_INPUT_DIMS) == 60


def test_enumeration_proof_no_candidate_dependent_crash():
    """Codex R4-2 no-crash proof. The v1 failure mode was a candidate-dependent
    crash (``select_independent_capacity`` raised ValueError when the m0X
    candidate set had no feasible member, e.g. joint=m01). v2's derivation always
    includes the all-1s candidate, so for EVERY frozen arch + input_dim the full
    resolution chain (derive -> count -> select -> build factory -> build model)
    completes without exception. This test exercises the chain end-to-end via
    ``build_output_form_aware_factory`` for every cell."""
    for arch_id, _, _, _ in FROZEN_ARCHITECTURES:
        for input_dim in CORE_INPUT_DIMS:
            factory, metadata = ofc.build_output_form_aware_factory(
                arch_id, "independent_capacity_matched", FROZEN, input_dim,
            )
            assert callable(factory)
            assert metadata is not None
            model = factory()
            assert isinstance(model, IndependentContainer)
            # Forward + decode: (N, 3) output consumable by decode_model_output.
            x = torch.randn(4, input_dim)
            raw = model(x)
            assert raw.shape == (4, 3)
            decoded = decode_model_output(
                raw, torch.tensor([100.0] * 4), torch.tensor([20.0] * 4),
            )
            assert decoded.shape == (4, 3)
            assert torch.isfinite(decoded).all()


# ============================================================================
# Structural distinctness of the two arms (regression-pin the v1 property under v2)
# ============================================================================


def test_joint_and_independent_are_structurally_distinct_for_frozen_arch():
    """For one A-E3 cell (joint=m05, input_dim=15) the two arms produce models
    that differ in type, parameter count, state_dict key namespace, and
    checkpoint bytes -- the output_form suffix selects a real model contract."""
    input_dim = 15
    joint_model = fe.resolve_model_factory("m05", FROZEN, input_dim, output_form="joint")()
    indep_model = fe.resolve_model_factory(
        "m05", FROZEN, input_dim, output_form="independent_capacity_matched",
    )()
    # Type.
    assert type(joint_model) is not type(indep_model)
    # Parameter count.
    joint_params = trainable_parameter_count(joint_model)
    indep_params = trainable_parameter_count(indep_model)
    assert joint_params != indep_params
    # state_dict key namespaces are disjoint.
    joint_keys = set(joint_model.state_dict())
    indep_keys = set(indep_model.state_dict())
    assert joint_keys.isdisjoint(indep_keys)
    assert all(k.startswith("subnetworks.") for k in indep_keys)
    assert not any(k.startswith("subnetworks.") for k in joint_keys)
    # Checkpoint bytes.
    joint_bytes = _checkpoint_canonical_bytes(joint_model.state_dict())
    indep_bytes = _checkpoint_canonical_bytes(indep_model.state_dict())
    assert joint_bytes != indep_bytes
    assert _checkpoint_hash(joint_model.state_dict()) != _checkpoint_hash(indep_model.state_dict())


# ============================================================================
# build_output_form_aware_factory: metadata / evidence contract (v2)
# ============================================================================


def test_joint_factory_returns_no_metadata():
    """The joint arm is the default; nothing is recorded beyond the checkpoint,
    so the factory builder returns ``(factory, None)`` for joint / None."""
    for form in ("joint", None):
        factory, metadata = ofc.build_output_form_aware_factory("m05", form, FROZEN, 15)
        assert callable(factory)
        assert metadata is None
        assert type(factory()).__name__ == "Sequential"


def test_independent_factory_records_v2_capacity_evidence():
    """The independent arm records the v2 capacity-selection metadata that the
    executor writes into evidence: the bound v2 contract id + SHA, the form, the
    joint architecture + widths + activation + dropout, the derived independent
    widths, the exact parameter counts, the full derived candidate set, the
    ceiling, the selection rule, and the width-scaling rule."""
    factory, metadata = ofc.build_output_form_aware_factory(
        "m05", "independent_capacity_matched", FROZEN, 15,
    )
    assert callable(factory)
    model = factory()
    assert isinstance(model, IndependentContainer)
    assert metadata is not None
    expected_keys = {
        "contract_id", "contract_sha256", "form",
        "joint_architecture_id", "joint_widths", "joint_activation", "joint_dropout",
        "joint_trainable_parameters",
        "independent_widths", "independent_trainable_parameters",
        "derived_candidate_widths",
        "ceiling_ratio", "ceiling", "selection_rule", "width_scaling_rule",
    }
    assert set(metadata) == expected_keys, set(metadata) ^ expected_keys
    assert metadata["contract_id"] == "A-E3-output-form-contract-v2"
    assert metadata["contract_sha256"] == APPROVED_A_E3_OUTPUT_FORM_CONTRACT_V2_SHA256
    assert metadata["form"] == "independent_capacity_matched"
    assert metadata["joint_architecture_id"] == "m05"
    assert metadata["joint_widths"] == [128, 64, 32]
    # Recorded parameter counts match the built models.
    assert metadata["independent_trainable_parameters"] == trainable_parameter_count(model)
    joint_model = build_mlp(
        15,
        tuple(int(w) for w in next(
            e for e in FROZEN.search["mlp_stage1_architectures"] if e["id"] == "m05"
        )["widths"]),
        "relu", 0.0,
    )
    assert metadata["joint_trainable_parameters"] == trainable_parameter_count(joint_model)
    # Rebuilding from the recorded independent_widths reproduces the same model.
    rebuilt = build_independent_container(
        15, tuple(metadata["independent_widths"]),
        metadata["joint_activation"], metadata["joint_dropout"],
    )
    assert trainable_parameter_count(rebuilt) == trainable_parameter_count(model)
    # The rebuilt model's state_dict key namespace matches the factory's.
    assert set(rebuilt.state_dict()) == set(model.state_dict())


def test_independent_factory_metadata_is_deterministic_in_arch_and_input_dim():
    """``resolve_independent_capacity`` is pure in (arch, input_dim, frozen):
    the same cell always selects the same derived widths and builds a factory
    whose parameter count matches the recorded metadata."""
    f1, m1 = ofc.build_output_form_aware_factory("m09", "independent_capacity_matched", FROZEN, 12)
    f2, m2 = ofc.build_output_form_aware_factory("m09", "independent_capacity_matched", FROZEN, 12)
    assert m1 == m2
    assert trainable_parameter_count(f1()) == trainable_parameter_count(f2())
    assert m1["independent_widths"] != m1["joint_widths"]  # structurally distinct widths


# ============================================================================
# Training / decode / checkpoint-reload / scoring parity
# ============================================================================


def _synthetic_regression_data(input_dim: int, n: int = 64, seed: int = 0):
    torch.manual_seed(seed)
    X = torch.randn(n, input_dim)
    true_w = torch.randn(input_dim, 3)
    Y = X @ true_w + 0.1 * torch.randn(n, 3)
    return (X[: n - 16], Y[: n - 16]), (X[n - 16:], Y[n - 16:])


@pytest.mark.parametrize("arch", ["m01", "m05", "m09"])
def test_joint_and_independent_train_decode_and_reload(arch):
    """Both arms train under the shared optimizer + equal-weight 3-component
    loss, produce finite ``(N, 3)`` predictions, decode to valid Weibull
    parameters, and reload identically from their canonical checkpoint bytes.
    Under v2 this now also holds for arch=m01 (v1 hard-failed the independent
    arm there)."""
    input_dim = 8
    train, validation = _synthetic_regression_data(input_dim)
    joint_factory, _ = ofc.build_output_form_aware_factory(arch, "joint", FROZEN, input_dim)
    indep_factory, _ = ofc.build_output_form_aware_factory(
        arch, "independent_capacity_matched", FROZEN, input_dim,
    )
    for name, factory in (("joint", joint_factory), ("independent", indep_factory)):
        result = fit_candidate(
            factory, train, validation,
            seed=7, max_epochs=5, min_epochs=2, patience=2,
        )
        assert torch.isfinite(result.predictions).all()
        assert result.predictions.shape == (16, 3)
        assert result.best_validation_loss == pytest.approx(
            float(result.validation_loss_history[result.best_epoch])
        )
        # Checkpoint reload reproduces the stored predictions exactly.
        state_dict = load_checkpoint(result.checkpoint_bytes)
        reloaded = factory()
        reloaded.load_state_dict(state_dict)
        reloaded.eval()
        with torch.no_grad():
            reloaded_pred = reloaded(validation[0])
        assert torch.allclose(reloaded_pred, result.predictions, atol=1e-6)
        # Decode produces valid Weibull parameters.
        scale = torch.ones(16)
        location = torch.zeros(16)
        decoded = decode_model_output(reloaded_pred, location, scale)
        assert decoded.shape == (16, 3)
        assert torch.isfinite(decoded).all()
        assert (decoded[:, 0] > 0).all() and (decoded[:, 1] > 0).all()


def test_two_output_form_arms_same_seed_produce_distinct_checkpoints():
    """For one (arch, input_dim, seed) cell the joint and independent arms
    produce DIFFERENT checkpoint bytes -- the contrastive control is real even
    under identical sample / seed wiring (the matrix feeds both arms the same
    (n, seed))."""
    input_dim = 8
    train, validation = _synthetic_regression_data(input_dim)
    joint_factory, _ = ofc.build_output_form_aware_factory("m05", "joint", FROZEN, input_dim)
    indep_factory, _ = ofc.build_output_form_aware_factory(
        "m05", "independent_capacity_matched", FROZEN, input_dim,
    )
    joint_result = fit_candidate(
        joint_factory, train, validation, seed=11, max_epochs=3, min_epochs=1, patience=1,
    )
    indep_result = fit_candidate(
        indep_factory, train, validation, seed=11, max_epochs=3, min_epochs=1, patience=1,
    )
    assert joint_result.checkpoint_bytes != indep_result.checkpoint_bytes
    assert joint_result.checkpoint_sha256 != indep_result.checkpoint_sha256


def test_independent_container_single_optimizer_manages_all_subnetwork_parameters():
    """The training loop constructs ONE optimizer over ``model.parameters()``,
    which yields every subnetwork's parameters for an IndependentContainer; the
    equal-weight 3-component loss (mean over N*3) is applied to the concatenated
    ``(N, 3)`` output. Verified by asserting all subnetwork parameters receive a
    non-zero gradient on a backward pass through the concatenated output."""
    container = IndependentContainer(5, (16,), "relu", 0.0)
    # collect a snapshot of every subnetwork parameter's grad after backward
    x = torch.randn(4, 5)
    out = container(x)
    assert out.shape == (4, 3)
    loss = out.sum()  # touches all three columns (subnetworks) equally
    loss.backward()
    for index, sub in enumerate(container.subnetworks):
        for name, param in sub.named_parameters():
            assert param.grad is not None, (
                f"subnetwork {index} param {name} received no gradient"
            )
            assert param.grad.abs().sum().item() > 0, (
                f"subnetwork {index} param {name} got a zero gradient"
            )
