"""A-E3 output-form contract (joint vs independent), SHA-bound.

Freezes the scientific contract for the A-E3 ``output_form`` decision so the
``joint`` and ``independent_capacity_matched`` candidates are contrastive controls
(different model structures, not just different labels):

* ``joint`` -- one shared-trunk MLP producing all three Weibull parameter outputs
  concurrently (``build_mlp`` with ``output_dim=3``).
* ``independent_capacity_matched`` -- three parameter-isolated single-output MLP
  subnetworks in a ``ModuleList`` (:class:`~study02a.models.IndependentContainer`),
  each built from the SAME frozen m0X hidden spec (widths / activation / dropout),
  trained under ONE optimizer managing every subnetwork's parameters, with an
  equal-weight three-component loss. ``forward`` concatenates the three scalar
  subnetwork outputs into the ``(N, 3)`` raw-output shape :func:`decode_model_output`
  already consumes, so target / decode / metric contracts are unchanged.

The independent architecture is capacity-selected from the frozen ``m01..m12`` MLP
candidate set: each candidate's total = three identical single-output subnetworks
built from that architecture's spec. The selection rule (protocol §3.4 +
``A-g2-search-v1.json`` ``joint_independent_capacity``) picks the candidate whose
total trainable parameters do not exceed ``joint * 1.05`` and are closest to the
joint model's (tie: architecture id ascending; fallback: nearest not exceeding
joint; hard fail if every candidate exceeds joint).

The contract dict (``_CONTRACT``) is SHA-bound: ``CONTRACT_SHA256`` is the SHA-256
of its canonical JSON and is validated at every load.
:data:`formal_contracts.APPROVED_A_E3_OUTPUT_FORM_CONTRACT_SHA256` mirrors the SHA
for cross-module authority; the A-E3 executor records it in every output_form
fit's evidence so scoring / rebuild / test-consumer paths uniquely reconstruct the
correct model factory from the bound evidence.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Callable, Mapping

from torch import nn

from .formal_contracts import APPROVED_A_E3_OUTPUT_FORM_CONTRACT_SHA256
from .models import (
    _feed_forward,
    build_independent_container,
    build_mlp,
    trainable_parameter_count,
)
from .training import select_independent_capacity


# ---------------------------------------------------------------------------
# Frozen contract definition (SHA-bound below).
# ---------------------------------------------------------------------------

_CONTRACT: dict[str, Any] = {
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

# SHA-256 of the canonical JSON of ``_CONTRACT``. Computed once and frozen; validated
# at every load against both this constant and the cross-module mirror in
# ``formal_contracts.APPROVED_A_E3_OUTPUT_FORM_CONTRACT_SHA256``.
CONTRACT_SHA256 = APPROVED_A_E3_OUTPUT_FORM_CONTRACT_SHA256


_JOINT = "joint"
_INDEPENDENT = "independent_capacity_matched"
_OUTPUT_FORM_VALUES = frozenset({_JOINT, _INDEPENDENT})


def _canonical_json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    ).encode("utf-8")


def load_output_form_contract() -> Mapping[str, Any]:
    """Load and SHA-validate the A-E3 output-form contract (fail-closed).

    Re-computes the canonical-JSON SHA-256 of ``_CONTRACT`` and requires it to match
    ``CONTRACT_SHA256`` (the frozen mirror of
    ``APPROVED_A_E3_OUTPUT_FORM_CONTRACT_SHA256``). Any drift -- a tampered contract
    dict, a mismatched SHA constant -- fails closed before any model factory resolves.
    """
    actual = hashlib.sha256(_canonical_json_bytes(_CONTRACT)).hexdigest()
    if actual != CONTRACT_SHA256:
        raise ValueError(
            "A-E3 output-form contract SHA-256 mismatch: the contract dict does not match "
            f"the frozen SHA (expected {CONTRACT_SHA256}, got {actual})"
        )
    return _CONTRACT


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
    input_dim: int, widths: tuple[int, ...], activation: str, dropout: float,
) -> int:
    """Trainable parameter count of ONE single-output MLP built from ``widths``."""
    return trainable_parameter_count(_feed_forward(input_dim, widths, 1, activation, dropout))


def independent_candidate_counts(
    input_dim: int, frozen: Any,
) -> dict[str, int]:
    """Total trainable parameters for each m0X independent container at ``input_dim``.

    Each candidate's total = three identical single-output subnetworks built from that
    architecture's frozen widths/activation/dropout. Per-candidate dropout / activation
    do not affect the parameter count (only widths + input_dim + the ``1``-output head
    do), but the architecture's full spec is reused at build time so the trained
    container matches the spec exactly.
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
    """Resolve the independent architecture + exact parameter counts for one cell.

    Pure/deterministic in ``(joint_architecture_id, input_dim, frozen)``: builds the
    joint model to count its parameters, enumerates the m0X candidate totals, and
    applies :func:`select_independent_capacity`. Returns a metadata dict recorded in
    the fit evidence so scoring / rebuild / test consumer uniquely reconstruct the
    factory without re-running the selection.

    Raises ``ValueError`` (from the frozen selector) when every candidate exceeds the
    joint model's parameter count -- the A-E3 executor records this as a scientific
    failure for the independent arm (the output_form decision then selects joint).
    """
    joint_count = joint_trainable_parameter_count(joint_architecture_id, input_dim, frozen)
    candidate_counts = independent_candidate_counts(input_dim, frozen)
    selected_id, selected_count = select_independent_capacity(joint_count, candidate_counts)
    return {
        "joint_architecture_id": str(joint_architecture_id),
        "joint_trainable_parameters": int(joint_count),
        "independent_architecture_id": str(selected_id),
        "independent_trainable_parameters": int(selected_count),
        "candidate_counts": dict(sorted(candidate_counts.items())),
        "ceiling_ratio": 1.05,
        "ceiling": int(round(1.05 * int(joint_count))),
        "selection_rule": "select_independent_capacity",
    }


def build_output_form_aware_factory(
    architecture_id: str, output_form: str | None, frozen: Any, input_dim: int,
) -> tuple[Callable[[], nn.Module], dict[str, Any] | None]:
    """Return ``(model_factory, evidence_metadata)`` for one A-E3 output_form cell.

    * ``output_form`` is ``None`` or ``"joint"`` -> the joint 3-output MLP factory;
      metadata is ``None`` (joint is the default; nothing to record beyond the
      checkpoint itself).
    * ``output_form == "independent_capacity_matched"`` -> the capacity-selected
      :class:`IndependentContainer` factory; metadata records the joint architecture,
      independent architecture, exact parameter counts and capacity selection so the
      evidence-binding path (scoring / rebuild / test consumer) reconstructs the exact
      factory from evidence alone.

    The contract SHA is validated on every call (fail-closed on tamper).
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
        selected_id = capacity["independent_architecture_id"]
        entry = _find_mlp_architecture_entry(frozen, selected_id)
        widths = tuple(int(value) for value in entry["widths"])
        activation = str(entry["activation"])
        dropout = float(entry["dropout"])
        factory = lambda: build_independent_container(
            int(input_dim), widths, activation, dropout,
        )
        metadata = {
            "contract_id": _CONTRACT["contract_id"],
            "contract_sha256": CONTRACT_SHA256,
            "form": _INDEPENDENT,
            **capacity,
        }
        return factory, metadata
    raise ValueError(f"unknown output_form value: {output_form!r}")


__all__ = [
    "CONTRACT_SHA256",
    "build_output_form_aware_factory",
    "independent_candidate_counts",
    "joint_trainable_parameter_count",
    "load_output_form_contract",
    "output_form_from_route",
    "resolve_independent_capacity",
]
