"""P4 formal comparison: frozen track definitions, method list, and run matrix.

This module holds ONLY P4-specific decisions:
- Four evaluation tracks (frozen)
- Six comparison methods (frozen)
- Run matrix: what can be reused vs what must be computed fresh
- Row count contract (frozen)
- Authorization gates (both preflight and formal)

All shared infrastructure (sample generation, Direct-MLP, Vector-MLP,
traditional estimators, metrics, audit code) is imported from existing modules.

NO new experiment framework, NO second large pipeline.
"""

from __future__ import annotations

import os
from pathlib import Path

# ════════════════════════════════════════════════════════════════════════
# Authorization gate — must remain False until independently authorized
# ════════════════════════════════════════════════════════════════════════

P4_FORMAL_AUTHORIZED = False

# ════════════════════════════════════════════════════════════════════════
# Frozen comparison methods (from P3 config, identical set)
# ════════════════════════════════════════════════════════════════════════

P4_METHODS = [
    "MDM-Default",
    "MDM-Vector-MLP",
    "Direct-MLP",
    "MLE",
    "LSE",
    "WMLE",
]

LEARNING_METHODS = ["MDM-Vector-MLP", "Direct-MLP"]
TRADITIONAL_METHODS = ["MDM-Default", "MLE", "LSE", "WMLE"]

MDM_DEFAULT_DELTA = 0.1

# ════════════════════════════════════════════════════════════════════════
# Frozen evaluation tracks
# ════════════════════════════════════════════════════════════════════════

TRACK_MAIN_HOLDOUT = "main_holdout"
TRACK_PARAM_INTERP = "param_interp"
TRACK_N_INTERP = "n_interp"
TRACK_EXTRAP = "extrap_diag"

ALL_TRACKS = [TRACK_MAIN_HOLDOUT, TRACK_PARAM_INTERP, TRACK_N_INTERP, TRACK_EXTRAP]

# ════════════════════════════════════════════════════════════════════════
# Frozen learning configuration
# ════════════════════════════════════════════════════════════════════════

N_FOLDS = 5
N_SEEDS = 3
SEEDS = [42, 2026, 3407]
N_MODELS = N_FOLDS * N_SEEDS  # 15

EVAL_REPEATS = 1000

# ════════════════════════════════════════════════════════════════════════
# Baseline commits and provenance
# ════════════════════════════════════════════════════════════════════════

BASELINE_COMMIT = "fde26eaa9613a0e79c8b8cced134d0e240625635"
P2_APPROVED_COMMIT = "53932687"
P3_APPROVED_COMMIT = "ec263120"
E3B_SEALED_COMMIT = "bedd65a"

# ════════════════════════════════════════════════════════════════════════
# Input SHA256 (computed from approved formal artifacts)
# ════════════════════════════════════════════════════════════════════════

INPUT_SHA256 = {
    "E3b_risk_curves_csv": "4b3ad2a3121af616f991b6d91cf15ede1b3f8670f9b97b6baf5527da9ac71ca5",
    "E3b_sample_features_csv": "75bb9a0619f1e04fc8e1cd80451fd5c5a199953f67793740edad06a5ea909e32",
    "P2_baseline_per_sample_csv": "09f419f02304011556d2640eaf794e00ba8ebf1b7bda2f5574d691d00ec94770",
    "P2_vector_per_sample_csv": "a882034bca1721141f7b4883b4c121efbd4f78f4c66bbc2256477993dc9fab66",
    "E4d_selector_extrapolation_csv": "eb261ff65a46b7f8eaed0d8cfc4e6c4232b7ba2bfdd71dd5408bb32f4a66692b",
}

# ════════════════════════════════════════════════════════════════════════
# Frozen row count contract
# ════════════════════════════════════════════════════════════════════════
#
# Two-layer design:
#   Layer 1 (estimation): each method produces one parameter estimate per
#     physical sample (beta, gamma_over_eta, n, repeat_id).
#     - Traditional methods: 1 row per sample, fold="all", seed="all".
#     - Learning methods: 1 row per (sample, fold, seed) — 15 models.
#   Layer 2 (evaluation): pairing broadcasts traditional rows to each
#     (fold, seed) context; applies per-fold P99 penalty; model-first J1.
#
# Track 1 (main_holdout): 45 combos, 5-fold split → 9 test combos/fold
#   Traditional: 45,000 rows (all samples, run once)
#   Learning: 9,000 test samples/fold × 15 models = 135,000 rows
# Track 2 (param_interp): 24 combos × 1000 repeats = 24,000 samples
#   Traditional: 24,000 rows
#   Learning: 24,000 × 15 = 360,000 rows
# Track 3 (n_interp): 15 combos × 1000 repeats = 15,000 samples
#   Traditional: 15,000 rows
#   Learning: 15,000 × 15 = 225,000 rows
# Track 4 (extrap_diag): E4d combos (varying repeats)
#   Computed at runtime from sealed E4d file; verified against SHA256.

ROW_COUNT_CONTRACT = {
    TRACK_MAIN_HOLDOUT: {"traditional": 45000, "learning_per_model": 9000, "learning_total": 135000},
    TRACK_PARAM_INTERP: {"traditional": 24000, "learning_per_model": 24000, "learning_total": 360000},
    TRACK_N_INTERP: {"traditional": 15000, "learning_per_model": 15000, "learning_total": 225000},
    TRACK_EXTRAP: {"traditional": "runtime", "learning_per_model": "runtime", "learning_total": "runtime"},
}

TRADITIONAL_FOLD_LABEL = "all"
TRADITIONAL_SEED_LABEL = "all"


def expected_rows(track, method):
    """Return expected row count for a track×method cell."""
    contract = ROW_COUNT_CONTRACT[track]
    if method in LEARNING_METHODS:
        return contract["learning_total"]
    return contract["traditional"]


# ════════════════════════════════════════════════════════════════════════
# Run matrix: track × method → reuse / compute
# ════════════════════════════════════════════════════════════════════════

def run_matrix():
    """Return the track × method reuse/missing matrix.

    Key correction: E3b/P2 artifacts store selected_delta and true_loss but
    NOT beta_hat/eta_hat/gamma_hat. MDM-Default and MDM-Vector-MLP must
    REBUILD 3-param estimates by regenerating the same sample and running
    MDM with the sealed delta.
    """
    matrix = {}

    for method in P4_METHODS:
        is_learning = method in LEARNING_METHODS

        if method == "MDM-Default":
            reusable = "E3b sample keys + true params (read-only)"
            missing = (
                "Rebuild: regenerate same samples, run MDM(δ=0.1) → beta_hat/eta_hat/gamma_hat. "
                "E3b risk_curves.csv loss_d0.10 provides J1 but NOT 3-param estimates."
            )
        elif method == "MDM-Vector-MLP":
            reusable = "E3b/E4d sealed selected_delta per (fold, seed, sample_key)"
            missing = (
                "Rebuild: regenerate same samples, run MDM(sealed selected_delta) → "
                "beta_hat/eta_hat/gamma_hat. Existing artifacts have loss only."
            )
        elif method == "Direct-MLP":
            reusable = "P3 approved architecture + training code (run_p3_direct_mlp.py)"
            missing = "Train 15 models (5 folds × 3 seeds), predict → beta_hat/eta_hat/gamma_hat"
        elif method in ("MLE", "LSE", "WMLE"):
            reusable = "Production estimator via run_method()"
            missing = f"Run {method} on all samples → beta_hat/eta_hat/gamma_hat"

        exp = expected_rows(TRACK_MAIN_HOLDOUT, method)

        matrix[(TRACK_MAIN_HOLDOUT, method)] = {
            "sample_key_source": "E3b sample_features.csv: (beta, gamma_over_eta, n, repeat_id)",
            "true_param_source": "E3b sample_features.csv: beta, eta=1.0, gamma=goe*eta",
            "reusable_artifact": reusable,
            "missing_compute": missing,
            "folds_seeds": f"{N_FOLDS}×{N_SEEDS}={N_MODELS}" if is_learning else None,
            "penalty_source": "Per-fold P99 of 26-delta training losses (E3b risk_curves.csv)",
            "expected_rows": exp,
            "input_sha256": INPUT_SHA256["E3b_risk_curves_csv"],
            "approved_commit": E3B_SEALED_COMMIT,
        }

    for method in P4_METHODS:
        is_learning = method in LEARNING_METHODS
        if method == "MDM-Default":
            reusable = "P2 sample keys + true params (read-only)"
            missing = "Rebuild: run MDM(δ=0.1) on P2-PI samples → 3-param estimates"
        elif method == "MDM-Vector-MLP":
            reusable = "P2 vector sealed selected_delta"
            missing = "Rebuild: run MDM(sealed delta) on P2-PI samples → 3-param estimates"
        elif method == "Direct-MLP":
            reusable = "P3 training code"
            missing = "Train 15 models, evaluate on P2-PI samples"
        elif method in ("MLE", "LSE", "WMLE"):
            reusable = "Production estimator"
            missing = f"Run {method} on P2-PI samples"

        matrix[(TRACK_PARAM_INTERP, method)] = {
            "sample_key_source": "P2 baseline: (beta, gamma_over_eta, n, repeat_id) for P2-PI",
            "true_param_source": "P2 baseline: beta, eta, gamma columns",
            "reusable_artifact": reusable,
            "missing_compute": missing,
            "folds_seeds": f"{N_FOLDS}×{N_SEEDS}={N_MODELS}" if is_learning else None,
            "penalty_source": "Per-fold P99 (same frozen folds as main grid)",
            "expected_rows": expected_rows(TRACK_PARAM_INTERP, method),
            "input_sha256": INPUT_SHA256["P2_baseline_per_sample_csv"],
            "approved_commit": P2_APPROVED_COMMIT,
        }

    for method in P4_METHODS:
        is_learning = method in LEARNING_METHODS
        if method == "MDM-Default":
            reusable = "P2 sample keys + true params (read-only)"
            missing = "Rebuild: run MDM(δ=0.1) on P2-NI samples → 3-param estimates"
        elif method == "MDM-Vector-MLP":
            reusable = "P2 vector sealed selected_delta"
            missing = "Rebuild: run MDM(sealed delta) on P2-NI samples → 3-param estimates"
        elif method == "Direct-MLP":
            reusable = "P3 training code"
            missing = "Train 15 models, evaluate on P2-NI samples"
        elif method in ("MLE", "LSE", "WMLE"):
            reusable = "Production estimator"
            missing = f"Run {method} on P2-NI samples"

        matrix[(TRACK_N_INTERP, method)] = {
            "sample_key_source": "P2 baseline: (beta, gamma_over_eta, n, repeat_id) for P2-NI",
            "true_param_source": "P2 baseline: beta, eta, gamma columns",
            "reusable_artifact": reusable,
            "missing_compute": missing,
            "folds_seeds": f"{N_FOLDS}×{N_SEEDS}={N_MODELS}" if is_learning else None,
            "penalty_source": "Per-fold P99 (same frozen folds as main grid)",
            "expected_rows": expected_rows(TRACK_N_INTERP, method),
            "input_sha256": INPUT_SHA256["P2_baseline_per_sample_csv"],
            "approved_commit": P2_APPROVED_COMMIT,
        }

    for method in P4_METHODS:
        is_learning = method in LEARNING_METHODS
        if method == "MDM-Default":
            reusable = "E4d sample keys (read-only)"
            missing = "Rebuild: run MDM(δ=0.1) on E4d off-grid samples → 3-param estimates"
        elif method == "MDM-Vector-MLP":
            reusable = "E4d sealed selected_delta per (fold, seed, sample_key)"
            missing = "Rebuild: run MDM(sealed delta) on E4d samples → 3-param estimates"
        elif method == "Direct-MLP":
            reusable = "P3 training code"
            missing = "Train 15 models, evaluate on E4d off-grid samples"
        elif method in ("MLE", "LSE", "WMLE"):
            reusable = "Production estimator"
            missing = f"Run {method} on E4d off-grid samples"

        matrix[(TRACK_EXTRAP, method)] = {
            "sample_key_source": "E4d selector_extrapolation.csv: (beta, gamma_over_eta, n, repeat_id)",
            "true_param_source": "Generated from seed_namespace + combo params (deterministic)",
            "reusable_artifact": reusable,
            "missing_compute": missing,
            "folds_seeds": f"{N_FOLDS}×{N_SEEDS}={N_MODELS}" if is_learning else None,
            "penalty_source": "Per-fold P99 (same frozen folds as main grid)",
            "expected_rows": "runtime (from sealed E4d file)",
            "input_sha256": INPUT_SHA256["E4d_selector_extrapolation_csv"],
            "approved_commit": BASELINE_COMMIT,
        }

    return matrix


# ════════════════════════════════════════════════════════════════════════
# Formal output path (must NOT exist until authorized)
# ════════════════════════════════════════════════════════════════════════

_STUDY_DIR = Path(__file__).resolve().parents[1]
FORMAL_OUTPUT_DIR = _STUDY_DIR / "artifacts" / "formal" / "p4_formal_compare"

FORMAL_SUBDIRS = [
    "main_holdout",
    "param_interp",
    "n_interp",
    "extrap_diag",
]


def check_formal_not_authorized():
    """Preflight gate: raise if P4_FORMAL_AUTHORIZED is True or formal output exists.

    Used by smoke and preflight scripts to ensure they cannot accidentally
    write to formal directories.
    """
    if P4_FORMAL_AUTHORIZED:
        raise RuntimeError(
            "P4_FORMAL_AUTHORIZED is True — preflight/smoke must not run "
            "after authorization. Use the formal entry point instead."
        )
    if FORMAL_OUTPUT_DIR.exists():
        raise RuntimeError(
            f"Formal output directory already exists: {FORMAL_OUTPUT_DIR}. "
            "This indicates a prior formal run or unauthorized creation."
        )


def assert_formal_authorized():
    """Formal entry gate: raise if P4_FORMAL_AUTHORIZED is False.

    Called by the formal main() to ensure explicit authorization before
    any formal computation or output writing.
    """
    if not P4_FORMAL_AUTHORIZED:
        raise RuntimeError(
            "P4_FORMAL_AUTHORIZED is False. Formal P4 run requires explicit "
            "authorization: set P4_FORMAL_AUTHORIZED=True in a dedicated "
            "authorization commit approved by Codex."
        )


def assert_smoke_outside_formal(smoke_path: str):
    """Assert that smoke output path is outside the formal directory tree."""
    smoke = Path(smoke_path).resolve()
    formal = FORMAL_OUTPUT_DIR.resolve()
    formal_parent = formal.parent

    if smoke == formal_parent or formal_parent in smoke.parents:
        raise RuntimeError(
            f"Smoke path {smoke} is inside formal directory tree {formal_parent}."
        )
    if smoke == formal_parent or smoke in formal_parent.parents:
        raise RuntimeError(
            f"Smoke path {smoke} is equal to or a parent of formal directory {formal_parent}."
        )
    if smoke == formal or smoke in formal.parents:
        raise RuntimeError(
            f"Smoke path {smoke} is equal to or a parent of formal output {formal}."
        )
