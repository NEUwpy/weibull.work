"""Study01 generalization label classifier with orthogonal axis decomposition.

Each (beta, gamma_over_eta, n) combination is classified into:
  parameter_state = on_grid | interp | extrap
  n_state         = on_grid | interp | extrap

This produces a 3x3 matrix: 9 possible state combinations.
Fail-closed: rejects unknown values, non-unique labels, missing data.
"""

import math
from typing import Tuple, Dict, Set

_TRAIN_BETAS: Set[float] = {1.5, 2.0, 2.5, 4.0, 5.0}
_TRAIN_GAMMAS: Set[float] = {0.1, 0.5, 1.0}
_TRAIN_NS: Set[int] = {7, 10, 20}

_PARAM_STATES = ("on_grid", "interp", "extrap")
_N_STATES = ("on_grid", "interp", "extrap")


def classify_generalization(
    beta: float,
    gamma_over_eta: float,
    n: int,
) -> Tuple[str, str]:
    """Classify one (beta, gamma_over_eta, n) into orthogonal states.

    Returns (parameter_state, n_state) where each is one of:
      "on_grid"  — exactly on a training grid point
      "interp"   — within training domain range but not on grid
      "extrap"   — outside training domain range

    Raises ValueError on invalid inputs.
    """
    if beta <= 0:
        raise ValueError(f"beta must be positive: {beta}")
    if gamma_over_eta < 0:
        raise ValueError(f"gamma_over_eta must be >= 0: {gamma_over_eta}")
    if n <= 0:
        raise ValueError(f"n must be positive: {n}")
    if beta != beta or gamma_over_eta != gamma_over_eta:
        raise ValueError(f"NaN values rejected: beta={beta}, ge={gamma_over_eta}")
    if not math.isfinite(beta) or not math.isfinite(gamma_over_eta):
        raise ValueError(f"non-finite values rejected")

    # Parameter state
    on_beta_grid = beta in _TRAIN_BETAS
    on_ge_grid = gamma_over_eta in _TRAIN_GAMMAS
    beta_in_domain = 1.5 <= beta <= 5.0
    ge_in_domain = 0.1 <= gamma_over_eta <= 1.0

    if on_beta_grid and on_ge_grid:
        param_state = "on_grid"
    elif beta_in_domain and ge_in_domain:
        param_state = "interp"
    elif not beta_in_domain or not ge_in_domain:
        param_state = "extrap"
    else:
        raise ValueError(
            f"unclassifiable parameter state: beta={beta}, ge={gamma_over_eta}"
        )

    # N state
    n_in_domain = 7 <= n <= 20

    if n in _TRAIN_NS:
        n_state = "on_grid"
    elif n_in_domain:
        n_state = "interp"
    elif n < 7 or n > 20:
        n_state = "extrap"
    else:
        raise ValueError(f"unclassifiable n state: n={n}")

    if param_state not in _PARAM_STATES:
        raise ValueError(f"invalid param_state: {param_state!r}")
    if n_state not in _N_STATES:
        raise ValueError(f"invalid n_state: {n_state!r}")

    return param_state, n_state


def classify_generalization_compound(
    beta: float, gamma_over_eta: float, n: int,
) -> str:
    """Return compound label like 'p_interp_n_on_grid'."""
    ps, ns = classify_generalization(beta, gamma_over_eta, n)
    return f"p_{ps}_n_{ns}"


def is_pure_parameter_interp(beta: float, gamma_over_eta: float, n: int) -> bool:
    """Pure parameter interpolation: p=interp, n=on_grid."""
    ps, ns = classify_generalization(beta, gamma_over_eta, n)
    return ps == "interp" and ns == "on_grid"


def is_pure_n_interp(beta: float, gamma_over_eta: float, n: int) -> bool:
    """Pure sample-size interpolation: p=on_grid, n=interp."""
    ps, ns = classify_generalization(beta, gamma_over_eta, n)
    return ps == "on_grid" and ns == "interp"


def is_pure_param_extrap(beta: float, gamma_over_eta: float, n: int) -> bool:
    """Pure parameter extrapolation: p=extrap, n=on_grid."""
    ps, ns = classify_generalization(beta, gamma_over_eta, n)
    return ps == "extrap" and ns == "on_grid"


def is_pure_n_extrap(beta: float, gamma_over_eta: float, n: int) -> bool:
    """Pure n extrapolation: p=on_grid, n=extrap."""
    ps, ns = classify_generalization(beta, gamma_over_eta, n)
    return ps == "on_grid" and ns == "extrap"


# --- Constants for tests ---

TRAIN_BETAS = frozenset(_TRAIN_BETAS)
TRAIN_GAMMAS = frozenset(_TRAIN_GAMMAS)
TRAIN_NS = frozenset(_TRAIN_NS)
PARAM_STATES = _PARAM_STATES
N_STATES = _N_STATES
