"""P4 formal comparison: frozen track definitions, method list, and run matrix.

This module holds ONLY P4-specific decisions:
- Four evaluation tracks (frozen)
- Six comparison methods (frozen)
- Run matrix: what can be reused vs what must be computed fresh

All shared infrastructure (sample generation, Direct-MLP, Vector-MLP,
traditional estimators, metrics, audit code) is imported from existing modules.

NO new experiment framework, NO second large pipeline.
"""

from __future__ import annotations

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

# Learning methods (need model-first aggregation: 5 folds × 3 seeds = 15 models)
LEARNING_METHODS = ["MDM-Vector-MLP", "Direct-MLP"]

# Traditional methods (single-run, no model variance)
TRADITIONAL_METHODS = ["MDM-Default", "MLE", "LSE", "WMLE"]

# ════════════════════════════════════════════════════════════════════════
# Frozen evaluation tracks
# ════════════════════════════════════════════════════════════════════════

# Track 1: Main design domain combo holdout
#   - 45 main-grid combos, 5-fold combo split holdout
#   - Same folds and seeds as E3b/E4/P3
#   - Source: E3b sample_features.csv + risk_curves.csv
TRACK_MAIN_HOLDOUT = "main_holdout"

# Track 2: Parameter interpolation (P2-PI)
#   - 24 combos: beta∈{1.75,2.25,3.25,4.50} × goe∈{0.30,0.75} × n∈{7,10,20}
#   - Source: P2 v2 baseline + vector per-sample (approved, 53932687)
TRACK_PARAM_INTERP = "param_interp"

# Track 3: Sample size interpolation (P2-NI)
#   - 15 combos: beta∈{1.5,2.0,2.5,4.0,5.0} × goe∈{0.1,0.5,1.0} × n=15
#   - Source: P2 v2 baseline + vector per-sample (approved, 53932687)
TRACK_N_INTERP = "n_interp"

# Track 4: Parameter/sample-size extrapolation diagnostics (E4d)
#   - 34 off-grid combos from E4d, categorized into param-extrap / n-extrap / multi-axis
#   - Source: E4d selector_extrapolation.csv (approved, P3b)
TRACK_EXTRAP = "extrap_diag"

ALL_TRACKS = [TRACK_MAIN_HOLDOUT, TRACK_PARAM_INTERP, TRACK_N_INTERP, TRACK_EXTRAP]

# ════════════════════════════════════════════════════════════════════════
# Frozen learning configuration
# ════════════════════════════════════════════════════════════════════════

N_FOLDS = 5
N_SEEDS = 3
SEEDS = [42, 2026, 3407]
N_MODELS = N_FOLDS * N_SEEDS  # 15

# Repeats per combo for evaluation (same as all formal experiments)
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
    # Track 1 inputs (E3b sealed)
    "E3b_risk_curves_csv": "4b3ad2a3121af616f991b6d91cf15ede1b3f8670f9b97b6baf5527da9ac71ca5",
    "E3b_sample_features_csv": "75bb9a0619f1e04fc8e1cd80451fd5c5a199953f67793740edad06a5ea909e32",
    # Track 2/3 inputs (P2 v2 approved)
    "P2_baseline_per_sample_csv": "09f419f02304011556d2640eaf794e00ba8ebf1b7bda2f5574d691d00ec94770",
    "P2_vector_per_sample_csv": "a882034bca1721141f7b4883b4c121efbd4f78f4c66bbc2256477993dc9fab66",
}

# ════════════════════════════════════════════════════════════════════════
# Run matrix: track × method → reuse / compute
# ════════════════════════════════════════════════════════════════════════

def run_matrix():
    """Return the track × method reuse/missing matrix.

    For each cell:
    - sample_key_source: where sample keys come from
    - true_param_source: where true params come from
    - reusable_artifact: existing approved artifact (or None)
    - missing_compute: what must be freshly computed
    - folds_seeds: learning config (or None for traditional)
    - penalty_source: where failure penalty comes from
    - expected_rows: expected per-sample row count
    """
    matrix = {}

    # ── Track 1: main_holdout × 6 methods ─────────────────────────────
    # 45 combos × 1000 repeats = 45,000 samples
    # Traditional: 45,000 rows each
    # Learning: 15 models × 9 test combos × 1000 repeats = 135,000 rows each
    for method in P4_METHODS:
        is_learning = method in LEARNING_METHODS
        if method == "MDM-Default":
            reusable = "E3b risk_curves.csv loss_d0.10 column (reuse as-is)"
            missing = "None — read loss_d0.10 from risk_curves.csv"
            exp_rows = 45000
        elif method == "MDM-Vector-MLP":
            reusable = "E3b vector_mlp_results (15 models, selected_delta + true_loss)"
            missing = "None — reuse E3b Vector-MLP per-sample results"
            exp_rows = 45000  # per model, 15 models total → model-first
        elif method == "Direct-MLP":
            reusable = None
            missing = "Train 15 Direct-MLP models (5 folds × 3 seeds), evaluate on test combos"
            exp_rows = 45000  # per model, 15 models total → model-first
        elif method in ("MLE", "LSE", "WMLE"):
            reusable = None
            missing = f"Run {method} on 45,000 samples via run_method()"
            exp_rows = 45000

        matrix[(TRACK_MAIN_HOLDOUT, method)] = {
            "sample_key_source": "E3b sample_features.csv: (beta, gamma_over_eta, n, repeat_id)",
            "true_param_source": "E3b sample_features.csv: beta, eta, gamma columns",
            "reusable_artifact": reusable,
            "missing_compute": missing,
            "folds_seeds": f"{N_FOLDS} folds × {N_SEEDS} seeds = {N_MODELS} models" if is_learning else None,
            "penalty_source": "Per-fold P99 of 26-delta training losses (E3b risk_curves.csv)",
            "expected_rows": exp_rows,
            "input_sha256": INPUT_SHA256["E3b_risk_curves_csv"],
            "approved_commit": E3B_SEALED_COMMIT if reusable else BASELINE_COMMIT,
        }

    # ── Track 2: param_interp (P2-PI) × 6 methods ────────────────────
    # 24 combos × 1000 repeats = 24,000 samples
    for method in P4_METHODS:
        is_learning = method in LEARNING_METHODS
        if method == "MDM-Default":
            reusable = "P2 v2 baseline per-sample (Default, P2-PI track)"
            missing = "None — reuse approved P2 baseline"
            exp_rows = 24000
        elif method == "MDM-Vector-MLP":
            reusable = "P2 v2 vector per-sample (P2-PI track, 15 models)"
            missing = "None — reuse approved P2 vector results"
            exp_rows = 24000  # per model
        elif method == "Direct-MLP":
            reusable = None
            missing = "Evaluate 15 frozen Direct-MLP models on P2-PI samples"
            exp_rows = 24000  # per model
        elif method in ("MLE", "LSE", "WMLE"):
            reusable = None
            missing = f"Run {method} on 24,000 P2-PI samples via run_method()"
            exp_rows = 24000

        matrix[(TRACK_PARAM_INTERP, method)] = {
            "sample_key_source": "P2 baseline: (beta, gamma_over_eta, n, repeat_id) for P2-PI track",
            "true_param_source": "P2 baseline: beta, eta, gamma columns",
            "reusable_artifact": reusable,
            "missing_compute": missing,
            "folds_seeds": f"{N_FOLDS} folds × {N_SEEDS} seeds = {N_MODELS} models" if is_learning else None,
            "penalty_source": "Per-fold P99 (same frozen folds as main grid)",
            "expected_rows": exp_rows,
            "input_sha256": INPUT_SHA256["P2_baseline_per_sample_csv"],
            "approved_commit": P2_APPROVED_COMMIT if reusable else BASELINE_COMMIT,
        }

    # ── Track 3: n_interp (P2-NI) × 6 methods ────────────────────────
    # 15 combos × 1000 repeats = 15,000 samples
    for method in P4_METHODS:
        is_learning = method in LEARNING_METHODS
        if method == "MDM-Default":
            reusable = "P2 v2 baseline per-sample (Default, P2-NI track)"
            missing = "None — reuse approved P2 baseline"
            exp_rows = 15000
        elif method == "MDM-Vector-MLP":
            reusable = "P2 v2 vector per-sample (P2-NI track, 15 models)"
            missing = "None — reuse approved P2 vector results"
            exp_rows = 15000  # per model
        elif method == "Direct-MLP":
            reusable = None
            missing = "Evaluate 15 frozen Direct-MLP models on P2-NI samples"
            exp_rows = 15000  # per model
        elif method in ("MLE", "LSE", "WMLE"):
            reusable = None
            missing = f"Run {method} on 15,000 P2-NI samples via run_method()"
            exp_rows = 15000

        matrix[(TRACK_N_INTERP, method)] = {
            "sample_key_source": "P2 baseline: (beta, gamma_over_eta, n, repeat_id) for P2-NI track",
            "true_param_source": "P2 baseline: beta, eta, gamma columns",
            "reusable_artifact": reusable,
            "missing_compute": missing,
            "folds_seeds": f"{N_FOLDS} folds × {N_SEEDS} seeds = {N_MODELS} models" if is_learning else None,
            "penalty_source": "Per-fold P99 (same frozen folds as main grid)",
            "expected_rows": exp_rows,
            "input_sha256": INPUT_SHA256["P2_baseline_per_sample_csv"],
            "approved_commit": P2_APPROVED_COMMIT if reusable else BASELINE_COMMIT,
        }

    # ── Track 4: extrap_diag (E4d) × 6 methods ───────────────────────
    # 34 off-grid combos, categorized by extrapolation axis
    # Traditional: run on all 34 combos
    # Learning: evaluate 15 frozen models on all 34 combos
    # NOTE: E4d combos have varying repeats (not all 1000)
    for method in P4_METHODS:
        is_learning = method in LEARNING_METHODS
        if method == "MDM-Default":
            reusable = None  # E4d has Vector-MLP selected_delta but not Default per-sample
            missing = "Run MDM-Default (delta=0.1) on all E4d off-grid samples"
            exp_rows = "varies (E4d combos have different repeats)"
        elif method == "MDM-Vector-MLP":
            reusable = "E4d selector_extrapolation.csv (15 models, selected_delta + true_loss)"
            missing = "Re-evaluate selected_delta → MDM params for 3-param comparison"
            exp_rows = "varies (E4d combos have different repeats)"
        elif method == "Direct-MLP":
            reusable = None
            missing = "Evaluate 15 frozen Direct-MLP models on E4d off-grid samples"
            exp_rows = "varies (E4d combos have different repeats)"
        elif method in ("MLE", "LSE", "WMLE"):
            reusable = None
            missing = f"Run {method} on all E4d off-grid samples via run_method()"
            exp_rows = "varies (E4d combos have different repeats)"

        matrix[(TRACK_EXTRAP, method)] = {
            "sample_key_source": "E4d selector_extrapolation.csv: (beta, gamma_over_eta, n, repeat_id)",
            "true_param_source": "Generated from seed_namespace + combo params (deterministic)",
            "reusable_artifact": reusable,
            "missing_compute": missing,
            "folds_seeds": f"{N_FOLDS} folds × {N_SEEDS} seeds = {N_MODELS} models" if is_learning else None,
            "penalty_source": "Per-fold P99 (same frozen folds as main grid)",
            "expected_rows": exp_rows,
            "input_sha256": "E4d_selector_extrapolation_csv (compute at runtime)",
            "approved_commit": BASELINE_COMMIT,
        }

    return matrix


# ════════════════════════════════════════════════════════════════════════
# Formal output path (must NOT exist until authorized)
# ════════════════════════════════════════════════════════════════════════

import os
from pathlib import Path

_STUDY_DIR = Path(__file__).resolve().parents[1]
FORMAL_OUTPUT_DIR = _STUDY_DIR / "artifacts" / "formal" / "p4_formal_compare"

# Formal subdirectories (must not be created until P4_FORMAL_AUTHORIZED=True)
FORMAL_SUBDIRS = [
    "main_holdout",
    "param_interp",
    "n_interp",
    "extrap_diag",
]


def check_formal_not_authorized():
    """Raise if P4_FORMAL_AUTHORIZED is True or formal output exists."""
    if P4_FORMAL_AUTHORIZED:
        raise RuntimeError(
            "P4_FORMAL_AUTHORIZED is True — this gate must remain False "
            "until independently authorized by Codex."
        )
    if FORMAL_OUTPUT_DIR.exists():
        raise RuntimeError(
            f"Formal output directory already exists: {FORMAL_OUTPUT_DIR}. "
            "This indicates a prior formal run or unauthorized creation."
        )


def assert_smoke_outside_formal(smoke_path: str):
    """Assert that smoke output path is outside the formal directory tree.

    Checks: not equal to, not contained in, and not parent of formal dir.
    """
    smoke = Path(smoke_path).resolve()
    formal = FORMAL_OUTPUT_DIR.resolve()
    formal_parent = formal.parent  # artifacts/formal/

    # smoke must not be inside formal_parent
    if smoke == formal_parent or formal_parent in smoke.parents:
        raise RuntimeError(
            f"Smoke path {smoke} is inside formal directory tree {formal_parent}. "
            "Smoke must be completely outside artifacts/formal/."
        )
    # smoke must not contain the formal dir
    if formal == smoke or formal in smoke.parents:
        raise RuntimeError(
            f"Smoke path {smoke} contains formal directory {formal}. "
            "Smoke must not be a parent of formal output."
        )
