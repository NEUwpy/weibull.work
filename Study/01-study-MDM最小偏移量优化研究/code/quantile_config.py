"""Engineering-life quantile derivation configuration (frozen).

Derives x_0.90 / x_0.95 / x_0.99 from the sealed P4 per-sample three-parameter
estimates (artifacts/formal/p4_formal_compare/evaluation_all.csv). No estimator
is re-run; the only inputs are the P4 per-sample estimates and the true grid
parameters. Config values are frozen before the run; do not edit after sealing.
"""

from __future__ import annotations

from pathlib import Path

_STUDY_ROOT = Path(__file__).resolve().parents[1]

# --- input (read-only, sealed) ---------------------------------------------
P4_INPUT_CSV = _STUDY_ROOT / "artifacts/formal/p4_formal_compare/evaluation_all.csv"
P4_RESULT_TABLES = _STUDY_ROOT / "artifacts/formal/p4_formal_compare/result_tables.json"

# --- quantile levels (main = 0.95; 0.50 removed by confirmed decision) ------
QUANTILE_LEVELS = (0.90, 0.95, 0.99)
MAIN_QUANTILE_LEVEL = 0.95

# --- method scope ------------------------------------------------------------
# MLE is excluded: sealed-not-consumed as paper evidence and it is the only
# method with failures (17.8%–29.9%). Direct-MLP is tagged research-only.
# paper_role: core | external_reference | research
METHOD_SCOPE = {
    "MDM-Default": "core",
    "MDM-Vector-MLP": "core",
    "WMLE": "external_reference",
    "LSE": "external_reference",
    "Direct-MLP": "research",
}

# --- evaluation contract -----------------------------------------------------
# Complete-case basis: all five scoped methods have 0.0% failures on every
# track (verified against P4 evaluation_all.csv), so complete case == full
# sample. Failure rate and n_valid are reported per method for transparency.
# Per-model metric = per (fold, seed) model; aggregation is model-first across
# the 15 (5 folds × 3 seeds) models, mirroring P4's j1_summary.

# --- output ------------------------------------------------------------------
OUTPUT_DIR = _STUDY_ROOT / "artifacts/formal/quantile_derivation"

# --- seed namespace note ------------------------------------------------------
# P4 tracks use seed namespaces study01_v1 (main_holdout, extrap_diag) and
# study01_p2_v1 (param_interp, n_interp). Sample keys are carried through
# verbatim; no new samples are generated.
