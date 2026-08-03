"""P4 formal comparison: frozen configuration, authorization contract, run matrix.

Holds ONLY P4-specific decisions:
- Four evaluation tracks (frozen) with per-track seed namespaces
- Six comparison methods (frozen)
- Two-layer row contract (estimation + evaluation)
- Authorization contract (binds parent commit, worktree, paths, tracks, seeds)
- Run matrix: what can be reused vs what must be computed fresh

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
# Frozen comparison methods
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
# Frozen evaluation tracks with per-track seed namespaces (P4-R6)
# ════════════════════════════════════════════════════════════════════════

TRACK_MAIN_HOLDOUT = "main_holdout"
TRACK_PARAM_INTERP = "param_interp"
TRACK_N_INTERP = "n_interp"
TRACK_EXTRAP = "extrap_diag"

ALL_TRACKS = [TRACK_MAIN_HOLDOUT, TRACK_PARAM_INTERP, TRACK_N_INTERP, TRACK_EXTRAP]

TRACK_SEED_NAMESPACE = {
    TRACK_MAIN_HOLDOUT: "study01_v1",
    TRACK_PARAM_INTERP: "study01_p2_v1",
    TRACK_N_INTERP: "study01_p2_v1",
    TRACK_EXTRAP: "study01_v1",
}

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
# Input SHA256 (all frozen)
# ════════════════════════════════════════════════════════════════════════

INPUT_SHA256 = {
    "E3b_risk_curves_csv": "4b3ad2a3121af616f991b6d91cf15ede1b3f8670f9b97b6baf5527da9ac71ca5",
    "E3b_sample_features_csv": "75bb9a0619f1e04fc8e1cd80451fd5c5a199953f67793740edad06a5ea909e32",
    "P2_baseline_per_sample_csv": "09f419f02304011556d2640eaf794e00ba8ebf1b7bda2f5574d691d00ec94770",
    "P2_vector_per_sample_csv": "a882034bca1721141f7b4883b4c121efbd4f78f4c66bbc2256477993dc9fab66",
    "E4d_selector_extrapolation_csv": "eb261ff65a46b7f8eaed0d8cfc4e6c4232b7ba2bfdd71dd5408bb32f4a66692b",
}

# ════════════════════════════════════════════════════════════════════════
# Two-layer row contract (P4-R5)
# ════════════════════════════════════════════════════════════════════════
#
# Layer 1 — ESTIMATION: one parameter estimate per physical sample.
#   Traditional: (track, method, beta, goe, n, repeat_id) → beta_hat/eta_hat/gamma_hat
#     fold="all", seed="all". Computed once per track.
#   Learning: (track, method, fold, seed, beta, goe, n, repeat_id) → beta_hat/eta_hat/gamma_hat
#     One estimate per model per sample.
#
# Layer 2 — EVALUATION: one loss row per (sample, fold, seed) context.
#   Traditional estimates are BROADCAST to each fold context with fold-specific
#   P99 penalty applied. Learning rows keep their own fold/seed.
#   Evaluation rows carry: true_loss (with penalty), failure_penalty, fold, seed.
#   This is the layer used for model-first J1, pairing, stratification.
#
# Row counts (Track 1 main_holdout, 45 combos, 5-fold → 9 test/fold, 1000 reps):
#   Estimation: Traditional=45,000; Learning=135,000 (9,000 test × 15 models)
#   Evaluation: Traditional=135,000 (45,000 × 3 seeds per fold, but only test combos
#     per fold → 9,000 × 5 folds × 3 seeds = 135,000); Learning=135,000
#   Actually: Traditional evaluation = 9,000 test per fold × 3 seeds × 5 folds = 135,000
#   Learning evaluation = same 135,000
#   So evaluation layer is SYMMETRIC: all methods have 135,000 rows for Track 1.

ROW_COUNT_CONTRACT = {
    TRACK_MAIN_HOLDOUT: {
        "estimation_traditional": 45000,
        "estimation_learning_per_model": 9000,
        "estimation_learning_total": 135000,
        "evaluation_per_method": 135000,
    },
    TRACK_PARAM_INTERP: {
        "estimation_traditional": 24000,
        "estimation_learning_per_model": 24000,
        "estimation_learning_total": 360000,
        "evaluation_per_method": 360000,
    },
    TRACK_N_INTERP: {
        "estimation_traditional": 15000,
        "estimation_learning_per_model": 15000,
        "estimation_learning_total": 225000,
        "evaluation_per_method": 225000,
    },
    TRACK_EXTRAP: {
        "estimation_traditional": 7000,
        "estimation_learning_per_model": 7000,
        "estimation_learning_total": 105000,
        "evaluation_per_method": 105000,
    },
}

TRADITIONAL_FOLD_LABEL = "all"
TRADITIONAL_SEED_LABEL = "all"

# ════════════════════════════════════════════════════════════════════════
# Authorization contract (P4-R2)
# ════════════════════════════════════════════════════════════════════════
#
# Formal run requires ALL of:
#   1. P4_FORMAL_AUTHORIZED = True (set in dedicated authorization commit)
#   2. APPROVED_PARENT_COMMIT matches the commit that was independently reviewed
#   3. Clean worktree (no uncommitted changes)
#   4. HEAD == authorization commit (child of approved parent)
#   5. Script SHA256 matches the reviewed version
#   6. Config SHA256 matches the reviewed version
#   7. All input SHA256 match frozen values
#   8. Output path is exactly FORMAL_OUTPUT_DIR
#   9. ALL_TRACKS and SEEDS are the frozen sets
#  10. Exclusive run lock (no concurrent run)

APPROVED_PARENT_COMMIT = None  # reset after run; re-bound at next authorization commit


# ════════════════════════════════════════════════════════════════════════
# Formal output path
# ════════════════════════════════════════════════════════════════════════

_STUDY_DIR = Path(__file__).resolve().parents[1]
FORMAL_OUTPUT_DIR = _STUDY_DIR / "artifacts" / "formal" / "p4_formal_compare"

FORMAL_SUBDIRS = ["main_holdout", "param_interp", "n_interp", "extrap_diag"]

# ════════════════════════════════════════════════════════════════════════
# Run matrix
# ════════════════════════════════════════════════════════════════════════

def run_matrix():
    """Return the track × method reuse/missing matrix."""
    matrix = {}
    for track in ALL_TRACKS:
        ns = TRACK_SEED_NAMESPACE[track]
        for method in P4_METHODS:
            is_learning = method in LEARNING_METHODS
            if method == "MDM-Default":
                missing = f"Rebuild: regenerate samples (ns={ns}), run MDM(δ=0.1) → 3 params"
            elif method == "MDM-Vector-MLP":
                missing = f"Rebuild: regenerate samples (ns={ns}), run MDM(sealed δ) → 3 params"
            elif method == "Direct-MLP":
                missing = "Train 15 models, predict → 3 params (with validity check)"
            else:
                missing = f"Run {method} on samples (ns={ns}) → 3 params"

            matrix[(track, method)] = {
                "seed_namespace": ns,
                "missing_compute": missing,
                "folds_seeds": f"{N_FOLDS}×{N_SEEDS}={N_MODELS}" if is_learning else None,
                "input_sha256": _track_input_sha256(track),
            }
    return matrix


def _track_input_sha256(track):
    if track == TRACK_MAIN_HOLDOUT:
        return INPUT_SHA256["E3b_risk_curves_csv"]
    elif track in (TRACK_PARAM_INTERP, TRACK_N_INTERP):
        return INPUT_SHA256["P2_baseline_per_sample_csv"]
    else:
        return INPUT_SHA256["E4d_selector_extrapolation_csv"]


# ════════════════════════════════════════════════════════════════════════
# Gates
# ════════════════════════════════════════════════════════════════════════

def check_formal_not_authorized():
    """Preflight gate: raise if authorized or formal output exists."""
    if P4_FORMAL_AUTHORIZED:
        raise RuntimeError(
            "P4_FORMAL_AUTHORIZED is True — preflight/smoke must not run "
            "after authorization."
        )
    if FORMAL_OUTPUT_DIR.exists():
        raise RuntimeError(
            f"Formal output directory already exists: {FORMAL_OUTPUT_DIR}."
        )


def assert_formal_authorized():
    """Formal entry gate: raise if not authorized."""
    if not P4_FORMAL_AUTHORIZED:
        raise RuntimeError(
            "P4_FORMAL_AUTHORIZED is False. Formal P4 run requires explicit "
            "authorization commit approved by Codex."
        )


def assert_smoke_outside_formal(smoke_path: str):
    """Assert smoke path is outside formal directory tree."""
    smoke = Path(smoke_path).resolve()
    formal = FORMAL_OUTPUT_DIR.resolve()
    formal_parent = formal.parent

    if smoke == formal_parent or formal_parent in smoke.parents:
        raise RuntimeError(f"Smoke path {smoke} is inside formal tree {formal_parent}.")
    if smoke == formal_parent or smoke in formal_parent.parents:
        raise RuntimeError(f"Smoke path {smoke} is parent of formal tree.")
    if smoke == formal or smoke in formal.parents:
        raise RuntimeError(f"Smoke path {smoke} overlaps formal output.")
