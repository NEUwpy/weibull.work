"""A-E3 output-form contract (joint vs independent), SHA-bound.

Freezes the scientific contract for the A-E3 ``output_form`` decision so the
``joint`` and ``independent_capacity_matched`` candidates are contrastive controls
(different model structures, not just different labels):

* ``joint`` -- one shared-trunk MLP producing all three Weibull parameter outputs
  concurrently (``build_mlp`` with ``output_dim=3``).
* ``independent_capacity_matched`` -- three parameter-isolated single-output MLP
  subnetworks in a ``ModuleList`` (:class:`~study02a.models.IndependentContainer`),
  trained under ONE optimizer managing every subnetwork's parameters, with an
equal-weight three-component loss. ``forward`` concatenates the three scalar
subnetwork outputs into the ``(N, 3)`` raw-output shape :func:`decode_model_output`
already consumes, so target / decode / metric contracts are unchanged.

Two contract versions are present:

* **v2** (:data:`_CONTRACT` / :data:`_CONTRACT_V2`, id
  ``A-E3-output-form-contract-v2``) is the ACTIVE formal contract. The independent
  architecture's widths are DERIVED from the joint architecture's widths via the
  deterministic width-scaling rule (:func:`derive_independent_widths`); activation
  and dropout are reused from the joint architecture unchanged. Selection picks the
  derived candidate whose three-subnetwork total is ``<= joint * 1.05`` and closest
  to the joint model's (tie: widths tuple lexicographic ascending). The candidate
  set always contains the all-1s widths (``k=1``), so for every frozen joint
  architecture and every fixed-route ``input_dim`` there is a feasible candidate
  whose total is strictly below the joint count: capacity selection is guaranteed
  to succeed and the independent fit is NEVER a scientific failure for capacity
  reasons. If selection ever fails it is a contract / infrastructure error and
  formal preflight blocks.

* **v1** (:data:`_CONTRACT_V1`, id ``A-E3-output-form-contract-v1``) is RETAINED
  ONLY FOR SHA AUDIT -- it is NOT used for formal execution. v1 selected the
  independent arm from the frozen ``m01..m12`` candidate set; for ``joint=m01``
  every candidate's three-subnetwork total exceeded the joint count, so v1
  fail-closed and the independent fit was recorded as a scientific failure. v2
  removes that failure mode. The v1 dict and its SHA are kept so a future reader
  can verify the v1 contract bytes have not been tampered with.

The contract dicts are SHA-bound: :data:`CONTRACT_SHA256` (the active v2 SHA) and
:data:`CONTRACT_V1_SHA256` are each the SHA-256 of the canonical JSON of their
contract dict and are validated at every load.
:data:`formal_contracts.APPROVED_A_E3_OUTPUT_FORM_CONTRACT_V2_SHA256` mirrors the
v2 SHA for cross-module authority; the A-E3 executor records the v2 SHA in every
output_form fit's evidence so scoring / rebuild / test-consumer paths uniquely
reconstruct the correct model factory from the bound evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping, Sequence

from torch import nn

from .formal_contracts import (
    APPROVED_A_E3_OUTPUT_FORM_CONTRACT_SHA256,
    APPROVED_A_E3_OUTPUT_FORM_CONTRACT_V2_SHA256,
)
from .models import (
    _feed_forward,
    build_independent_container,
    build_mlp,
    trainable_parameter_count,
)
from .training import select_independent_capacity


# ---------------------------------------------------------------------------
# Frozen contract definitions (SHA-bound below).
# ---------------------------------------------------------------------------

# v1 contract (R3-A): RETAINED FOR SHA AUDIT ONLY -- NOT used for formal execution.
# v1 selected the independent arm from the frozen m01..m12 candidate set, which had
# no feasible candidate for joint=m01 (the smallest architecture). See :data:`_CONTRACT`
# (v2) for the active formal contract.
_CONTRACT_V1: dict[str, Any] = {
    "contract_id": "A-E3-output-form-contract-v1",
    "joint": {
        "model_type": "single_mlp_shared_trunk",
        "output_dim": 3,
        "parameter_sharing": "shared hidden trunk; one 3-output head",
        "factory": "build_mlp(input_dim, widths, activation, dropout) [output_dim=3]",
    },
    "independent": {
        "model_type": "module_list_three_single_output",
        "subnetwork_count": 3,
        "output_dim_per_subnetwork": 1,
        "subnetwork_hidden_spec": (
            "identical across the three subnetworks; each subnetwork reuses one "
            "frozen m0X MLP architecture's widths/activation/dropout with a "
            "single-output head"
        ),
        "parameter_sharing": "none -- each subnetwork owns its parameters",
        "total_trainable_parameters": "sum of the three subnetworks' trainable parameters",
        "forward_contract": "torch.cat([subnet_0(x), subnet_1(x), subnet_2(x)], dim=1) -> (N, 3)",
        "optimizer": "single optimizer managing all subnetwork parameters jointly",
        "loss": "equal-weight three-component loss (mean reduction over all N*3 elements)",
        "factory": "build_independent_container(input_dim, widths, activation, dropout)",
    },
    "capacity_selection": {
        "joint_parameter_basis": (
            "trainable parameters of build_mlp(input_dim, <selected-arch widths>, "
            "<act>, <dropout>) -- the A-E3 selected architecture instantiated as joint"
        ),
        "candidate_set": (
            "frozen m01..m12 MLP architectures; each candidate's total = "
            "3 * trainable_parameter_count(single-output MLP built from that architecture)"
        ),
        "ceiling_ratio": 1.05,
        "primary_rule": (
            "select the candidate whose total trainable parameters <= joint * ceiling_ratio "
            "and is closest to joint"
        ),
        "tie_break": "architecture_id lexicographic ascending",
        "fallback": (
            "if no candidate satisfies the primary ceiling, select the candidate nearest "
            "to joint whose total does not exceed joint"
        ),
        "hard_fail": (
            "if every candidate's total exceeds joint, capacity selection fails closed; "
            "the independent fit records a scientific failure"
        ),
    },
    "decode_contract": (
        "decode_model_output is shared: both joint and independent produce (N, 3) raw "
        "outputs decoded identically; target / decode / metric contracts are unchanged"
    ),
    "checkpoint_contract": (
        "model.state_dict() serialized via _checkpoint_canonical_bytes; the independent "
        "container's state_dict keys are namespaced by subnetwork index "
        "(subnetworks.{0,1,2}.*), structurally distinct from the joint model's flat keys"
    ),
}

# v2 contract (R4-2): the ACTIVE formal A-E3 output-form contract. The independent
# widths are DERIVED from the joint widths via the deterministic width-scaling rule,
# guaranteeing a feasible candidate (all-1s) for every joint architecture + input_dim.
_CONTRACT_V2: dict[str, Any] = {
    "contract_id": "A-E3-output-form-contract-v2",
    "supersedes": (
        "A-E3-output-form-contract-v1 (v1 retained only for SHA audit; not used for "
        "formal execution)"
    ),
    "joint": {
        "model_type": "single_mlp_shared_trunk",
        "output_dim": 3,
        "parameter_sharing": "shared hidden trunk; one 3-output head",
        "factory": "build_mlp(input_dim, widths, activation, dropout) [output_dim=3]",
    },
    "independent": {
        "model_type": "module_list_three_single_output",
        "subnetwork_count": 3,
        "output_dim_per_subnetwork": 1,
        "subnetwork_hidden_spec": (
            "identical across the three subnetworks; each subnetwork reuses the JOINT "
            "architecture's activation/dropout with a single-output head, but with widths "
            "DERIVED from the joint widths via the deterministic width-scaling rule"
        ),
        "width_scaling_rule": {
            "algorithm": (
                "for joint widths W with M=max(W), enumerate k=1..M: "
                "widths(k) = tuple(max(1, floor(w*k/M)) for w in W); "
                "deduplicate preserving k-ascending order"
            ),
            "all_ones_guarantee": (
                "k=1 yields widths all-1s; this candidate is always present in the set"
            ),
            "joint_widths_member": (
                "k=M yields the original joint widths; this candidate is always present"
            ),
            "activation_dropout_source": (
                "the three subnetworks reuse the joint architecture's activation and "
                "dropout exactly (no scaling applied to activation/dropout)"
            ),
        },
        "parameter_sharing": "none -- each subnetwork owns its parameters",
        "total_trainable_parameters": "sum of the three subnetworks' trainable parameters",
        "forward_contract": "torch.cat([subnet_0(x), subnet_1(x), subnet_2(x)], dim=1) -> (N, 3)",
        "optimizer": "single optimizer managing all subnetwork parameters jointly",
        "loss": "equal-weight three-component loss (mean reduction over all N*3 elements)",
        "factory": "build_independent_container(input_dim, widths, activation, dropout)",
    },
    "capacity_selection": {
        "joint_parameter_basis": (
            "trainable parameters of build_mlp(input_dim, <selected-arch widths>, "
            "<act>, <dropout>) -- the A-E3 selected architecture instantiated as joint"
        ),
        "candidate_set": (
            "derived from the joint widths via the width-scaling rule; each candidate's "
            "total = 3 * trainable_parameter_count(single-output MLP built from that "
            "candidate's derived widths with the joint's activation/dropout)"
        ),
        "ceiling_ratio": 1.05,
        "primary_rule": (
            "select the candidate whose total trainable parameters <= joint * ceiling_ratio "
            "and is closest to joint"
        ),
        "tie_break": "widths tuple lexicographic ascending",
        "all_ones_feasibility": (
            "the all-1s candidate (k=1) is always present and its 3-subnetwork total is "
            "strictly less than the joint count for every non-degenerate joint "
            "architecture, so the eligible set is never empty for any frozen joint "
            "architecture + input_dim"
        ),
        "no_scientific_failure": (
            "if derived candidate selection ever fails to find a feasible candidate, this "
            "is a contract/infrastructure error (formal preflight blocks), NOT an "
            "independent-fit scientific failure"
        ),
    },
    "decode_contract": (
        "decode_model_output is shared: both joint and independent produce (N, 3) raw "
        "outputs decoded identically; target / decode / metric contracts are unchanged"
    ),
    "checkpoint_contract": (
        "model.state_dict() serialized via _checkpoint_canonical_bytes; the independent "
        "container's state_dict keys are namespaced by subnetwork index "
        "(subnetworks.{0,1,2}.*), structurally distinct from the joint model's flat keys"
    ),
}

# SHA-256 of the canonical JSON of each contract dict. Computed once and frozen;
# validated at every load.
CONTRACT_V1_SHA256 = APPROVED_A_E3_OUTPUT_FORM_CONTRACT_SHA256
CONTRACT_V2_SHA256 = APPROVED_A_E3_OUTPUT_FORM_CONTRACT_V2_SHA256

# The ACTIVE formal contract is v2. ``_CONTRACT`` and ``CONTRACT_SHA256`` are the
# names the rest of the codebase reads, so they pin to v2.
_CONTRACT = _CONTRACT_V2
CONTRACT_SHA256 = CONTRACT_V2_SHA256


_JOINT = "joint"
_INDEPENDENT = "independent_capacity_matched"
_OUTPUT_FORM_VALUES = frozenset({_JOINT, _INDEPENDENT})


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    ).encode("utf-8")


def load_output_form_contract() -> Mapping[str, Any]:
    """Load and SHA-validate the A-E3 output-form contract v2 (fail-closed).

    Re-computes the canonical-JSON SHA-256 of :data:`_CONTRACT` (the active v2
    contract dict) and requires it to match :data:`CONTRACT_SHA256` (the frozen
    mirror of :data:`formal_contracts.APPROVED_A_E3_OUTPUT_FORM_CONTRACT_V2_SHA256`).
    Any drift -- a tampered contract dict, a mismatched SHA constant -- fails closed
    before any model factory resolves.
    """
    actual = hashlib.sha256(_canonical_json_bytes(_CONTRACT)).hexdigest()
    if actual != CONTRACT_SHA256:
        raise ValueError(
            "A-E3 output-form contract v2 SHA-256 mismatch: the contract dict does not "
            f"match the frozen SHA (expected {CONTRACT_SHA256}, got {actual})"
        )
    return _CONTRACT


def load_output_form_contract_v1() -> Mapping[str, Any]:
    """Load and SHA-validate the A-E3 output-form contract v1 (audit only).

    v1 is retained only for SHA audit -- it is NOT used for formal execution. This
    entry exists so a future reader can independently verify the v1 contract bytes
    have not been tampered with; the formal path (:func:`load_output_form_contract`)
    never calls this. Raises on any drift from the frozen v1 SHA.
    """
    actual = hashlib.sha256(_canonical_json_bytes(_CONTRACT_V1)).hexdigest()
    if actual != CONTRACT_V1_SHA256:
        raise ValueError(
            "A-E3 output-form contract v1 SHA-256 mismatch (audit): the contract dict "
            f"does not match the frozen SHA (expected {CONTRACT_V1_SHA256}, got {actual})"
        )
    return _CONTRACT_V1


def output_form_from_route(route: str) -> str | None:
    """Extract the output_form suffix from an A-E3 plan/scoring row route.

    ``"V:joint"`` -> ``"joint"``;
    ``"V:independent_capacity_matched"`` / ``"selected:F2_or_V:independent_capacity_matched"``
    -> ``"independent_capacity_matched"``;
    any route whose final ``:``-suffix is not one of the two frozen output_form values
    (including ``"V"``, ``"S"``, ``"F2"``) -> ``None`` (the route does not carry an
    output_form and the joint 3-output MLP is used).
    """
    parts = str(route).rsplit(":", 1)
    if len(parts) == 2 and parts[1] in _OUTPUT_FORM_VALUES:
        return parts[1]
    return None


def _find_mlp_architecture_entry(
    frozen: Any, architecture_id: str,
) -> Mapping[str, Any]:
    for entry in frozen.search["mlp_stage1_architectures"]:
        if str(entry["id"]) == str(architecture_id):
            return entry
    raise ValueError(f"unknown frozen mlp architecture id: {architecture_id!r}")


def _single_output_mlp_param_count(
    input_dim: int, widths: Sequence[int], activation: str, dropout: float,
) -> int:
    """Trainable parameter count of ONE single-output MLP built from ``widths``."""
    return trainable_parameter_count(_feed_forward(input_dim, tuple(widths), 1, activation, dropout))


def derive_independent_widths(
    joint_widths: Sequence[int],
) -> tuple[tuple[int, ...], ...]:
    """Derive independent candidate widths from joint widths (v2 width-scaling rule).

    For ``joint_widths = W`` with ``M = max(W)``, enumerate ``k = 1..M``::

        widths(k) = tuple(max(1, floor(w * k / M)) for w in W)

    and deduplicate preserving ``k``-ascending order. ``k = 1`` always yields the
    all-1s widths (so the candidate set always has at least one feasible member
    whose three-subnetwork total is strictly less than the joint count); ``k = M``
    always yields the original joint widths. The returned tuple is therefore
    non-empty, deterministic in ``joint_widths``, and ordered from smallest
    (all-1s) to largest (joint widths) by ``k``.

    Activation and dropout are NOT scaled: they are reused from the joint
    architecture unchanged (they do not affect parameter count anyway).
    """
    W = tuple(int(w) for w in joint_widths)
    if not W or any(w < 1 for w in W):
        raise ValueError(
            f"joint widths must be a non-empty sequence of positive ints, got {joint_widths!r}"
        )
    M = max(W)
    seen: set[tuple[int, ...]] = set()
    candidates: list[tuple[int, ...]] = []
    for k in range(1, M + 1):
        widths_k = tuple(max(1, (w * k) // M) for w in W)
        if widths_k not in seen:
            seen.add(widths_k)
            candidates.append(widths_k)
    return tuple(candidates)


def independent_candidate_counts_v2(
    input_dim: int, joint_widths: Sequence[int], activation: str, dropout: float,
) -> dict[tuple[int, ...], int]:
    """v2: derived candidate widths -> total trainable parameters per candidate.

    For each candidate produced by :func:`derive_independent_widths`, build ONE
    single-output MLP from those (derived) widths with the joint's
    activation/dropout, count its trainable parameters, and triple it (three
    identical subnetworks). Returns ``{widths_tuple: total_trainable_parameters}``.

    Activation/dropout do not affect the parameter count (only widths +
    input_dim + the ``1``-output head do), but they ARE reused at build time so
    the trained container matches the joint architecture's spec exactly.
    """
    counts: dict[tuple[int, ...], int] = {}
    for widths in derive_independent_widths(joint_widths):
        single_count = _single_output_mlp_param_count(input_dim, widths, activation, dropout)
        counts[widths] = 3 * single_count
    return counts


def independent_candidate_counts(
    input_dim: int, frozen: Any,
) -> dict[str, int]:
    """v1 (audit): total trainable parameters for each m0X independent container.

    Each candidate's total = three identical single-output subnetworks built from
    that architecture's frozen widths/activation/dropout. Retained for v1 SHA audit
    only; the v2 formal path uses :func:`independent_candidate_counts_v2` (derived
    widths) instead. Per-candidate dropout / activation do not affect the parameter
    count (only widths + input_dim + the ``1``-output head do), but the
    architecture's full spec is reused at build time so the trained container
    matches the spec exactly.
    """
    counts: dict[str, int] = {}
    for entry in frozen.search["mlp_stage1_architectures"]:
        candidate_id = str(entry["id"])
        widths = tuple(int(value) for value in entry["widths"])
        single_count = _single_output_mlp_param_count(
            input_dim, widths, str(entry["activation"]), float(entry["dropout"]),
        )
        counts[candidate_id] = 3 * single_count
    return counts


def joint_trainable_parameter_count(
    joint_architecture_id: str, input_dim: int, frozen: Any,
) -> int:
    """Trainable parameter count of the joint model (3-output MLP) for ``joint_architecture_id``."""
    entry = _find_mlp_architecture_entry(frozen, joint_architecture_id)
    widths = tuple(int(value) for value in entry["widths"])
    joint_model = build_mlp(input_dim, widths, str(entry["activation"]), float(entry["dropout"]))
    return trainable_parameter_count(joint_model)


def resolve_independent_capacity(
    joint_architecture_id: str, input_dim: int, frozen: Any,
) -> dict[str, Any]:
    """Resolve the v2 independent architecture + exact parameter counts for one cell.

    Pure/deterministic in ``(joint_architecture_id, input_dim, frozen)``:

    1. Build the joint model to count its parameters.
    2. Read the joint architecture's widths / activation / dropout.
    3. Derive the independent candidate widths via :func:`derive_independent_widths`.
    4. For each derived candidate, compute the three-subnetwork total.
    5. Apply :func:`select_independent_capacity` (v2 rule: ``<= joint * 1.05`` and
       closest, tie: widths tuple lexicographic ascending).

    Returns a metadata dict recorded in the fit evidence so scoring / rebuild /
    test consumer uniquely reconstruct the factory without re-running the
    selection (the rebuild path re-derives widths deterministically from the same
    joint architecture + input_dim, so the evidence is a redundant audit record --
    but it is the authoritative audit record).

    v2 NEVER raises for a legitimate frozen joint architecture: the all-1s derived
    candidate is always present and its three-subnetwork total is strictly less
    than the joint count, so a feasible candidate always exists. If selection ever
    raises it indicates a contract / infrastructure error (formal preflight
    blocks), NOT an independent-fit scientific failure.
    """
    load_output_form_contract()
    entry = _find_mlp_architecture_entry(frozen, str(joint_architecture_id))
    joint_widths = tuple(int(value) for value in entry["widths"])
    activation = str(entry["activation"])
    dropout = float(entry["dropout"])
    joint_count = joint_trainable_parameter_count(
        str(joint_architecture_id), int(input_dim), frozen,
    )
    candidate_counts = independent_candidate_counts_v2(
        int(input_dim), joint_widths, activation, dropout,
    )
    selected_widths, selected_count = select_independent_capacity(joint_count, candidate_counts)
    return {
        "contract_id": _CONTRACT["contract_id"],
        "form": _INDEPENDENT,
        "joint_architecture_id": str(joint_architecture_id),
        "joint_widths": list(joint_widths),
        "joint_activation": activation,
        "joint_dropout": dropout,
        "joint_trainable_parameters": int(joint_count),
        "independent_widths": list(selected_widths),
        "independent_trainable_parameters": int(selected_count),
        "derived_candidate_widths": [
            {"widths": list(widths), "total_trainable_parameters": int(count)}
            for widths, count in sorted(candidate_counts.items())
        ],
        "ceiling_ratio": 1.05,
        "ceiling": int(round(1.05 * int(joint_count))),
        "selection_rule": "select_independent_capacity_v2",
        "width_scaling_rule": (
            "for joint widths W with M=max(W), enumerate k=1..M "
            "widths(k)=tuple(max(1,floor(w*k/M)) for w in W); dedupe k-ascending"
        ),
    }


def build_output_form_aware_factory(
    architecture_id: str, output_form: str | None, frozen: Any, input_dim: int,
) -> tuple[Callable[[], nn.Module], dict[str, Any] | None]:
    """Return ``(model_factory, evidence_metadata)`` for one A-E3 output_form cell.

    * ``output_form`` is ``None`` or ``"joint"`` -> the joint 3-output MLP factory;
      metadata is ``None`` (joint is the default; nothing to record beyond the
      checkpoint itself).
    * ``output_form == "independent_capacity_matched"`` -> the v2 capacity-selected
      :class:`IndependentContainer` factory (widths derived from the joint widths
      via :func:`derive_independent_widths`); metadata records the joint
      architecture, derived independent widths, exact parameter counts, the full
      derived candidate set, and the v2 contract id + SHA so the evidence-binding
      path (scoring / rebuild / test consumer) reconstructs the exact factory from
      evidence alone (and can independently re-derive widths from the joint
      architecture to detect drift).

    The v2 contract SHA is validated on every call (fail-closed on tamper).
    """
    load_output_form_contract()
    if output_form in (None, _JOINT):
        entry = _find_mlp_architecture_entry(frozen, str(architecture_id))
        widths = tuple(int(value) for value in entry["widths"])
        activation = str(entry["activation"])
        dropout = float(entry["dropout"])
        factory: Callable[[], nn.Module] = lambda: build_mlp(
            int(input_dim), widths, activation, dropout,
        )
        return factory, None
    if output_form == _INDEPENDENT:
        capacity = resolve_independent_capacity(
            str(architecture_id), int(input_dim), frozen,
        )
        selected_widths = tuple(int(w) for w in capacity["independent_widths"])
        activation = str(capacity["joint_activation"])
        dropout = float(capacity["joint_dropout"])
        factory = lambda: build_independent_container(
            int(input_dim), selected_widths, activation, dropout,
        )
        metadata = {
            **capacity,
            "contract_sha256": CONTRACT_SHA256,
        }
        return factory, metadata
    raise ValueError(f"unknown output_form value: {output_form!r}")


__all__ = [
    "CONTRACT_SHA256",
    "CONTRACT_V1_SHA256",
    "CONTRACT_V2_SHA256",
    "build_output_form_aware_factory",
    "derive_independent_widths",
    "independent_candidate_counts",
    "independent_candidate_counts_v2",
    "joint_trainable_parameter_count",
    "load_output_form_contract",
    "load_output_form_contract_v1",
    "output_form_from_route",
    "resolve_independent_capacity",
]
