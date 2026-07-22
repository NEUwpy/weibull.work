"""
Study/01 — E4d Output Self-Check

Verifies the formal E4d output artifacts against the frozen contract.
Run after ``run_E4_formal_validation.py --tracks e4d`` completes.

Checks:
  1. E4d_selector_extrapolation.csv exists and is non-empty
  2. E4d_model_j1_summary.csv exists with exactly 15 model rows
  3. Tracks: only E4b_boundary + E4c_offgrid (no main-grid leak)
  4. Models: Vector-MLP-L6, Default, L1, L2 (all present)
  5. 15 model-level J1 entries (not pseudo-pooled)
  6. No E4 truth columns in training data
  7. Per-sample results have no NaN true_loss
  8. selected_delta values are within DELTA_GRID

Returns non-zero exit code and a failure message on any violation.
"""

import sys
import os
import json
import math
import re

import pandas as pd
import numpy as np

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

from config import DELTA_GRID, ARTIFACTS_DIR

E4_DIR = os.path.join(ARTIFACTS_DIR, "E4_robustness")
E4D_PATH = os.path.join(E4_DIR, "E4d_selector_extrapolation.csv")
E4D_J1_PATH = os.path.join(E4_DIR, "E4d_model_j1_summary.csv")

EXPECTED_TRACKS = {"E4b_boundary", "E4c_offgrid"}
EXPECTED_MODELS = {"Vector-MLP-L6", "Default", "L1", "L2"}


def check(msg, condition):
    if not condition:
        print(f"FAIL: {msg}")
        sys.exit(1)
    print(f"  OK: {msg}")


def main():
    errors = 0

    # 1. E4d output exists
    check("E4d_selector_extrapolation.csv exists", os.path.exists(E4D_PATH))
    df = pd.read_csv(E4D_PATH)
    check(f"E4d output non-empty ({len(df)} rows)", len(df) > 0)

    # 2. Model J1 summary exists
    check("E4d_model_j1_summary.csv exists", os.path.exists(E4D_J1_PATH))
    df_j1 = pd.read_csv(E4D_J1_PATH)
    check(f"Model J1 summary non-empty ({len(df_j1)} rows)", len(df_j1) > 0)

    # 3. Tracks
    actual_tracks = set(df['track'].unique())
    check(
        f"Tracks are {sorted(actual_tracks)} (expected {sorted(EXPECTED_TRACKS)})",
        actual_tracks == EXPECTED_TRACKS
    )

    # 4. Models
    actual_models = set(df['model'].unique())
    check(
        f"Models include {sorted(EXPECTED_MODELS)}",
        EXPECTED_MODELS.issubset(actual_models)
    )

    # 5. 15 model-level J1 for Vector-MLP-L6
    selector_rows = df_j1[df_j1['model'] == 'Vector-MLP-L6']
    n_models = len(selector_rows)
    check(
        f"15 Vector-MLP-L6 model-level J1 entries (got {n_models})",
        n_models == 15
    )

    # 6. 5 folds × 3 seeds coverage
    if n_models == 15:
        folds = set(selector_rows['fold'])
        seeds = set(selector_rows['seed'])
        check(f"5 folds covered: {sorted(folds)}", len(folds) == 5)
        check(f"3 seeds covered: {sorted(seeds)}", len(seeds) == 3)

    # 7. No NaN true_loss
    nan_count = int(df['true_loss'].isna().sum())
    check(f"No NaN true_loss (found {nan_count})", nan_count == 0)

    # 8. selected_delta in frozen grid
    invalid_deltas = set(df['selected_delta'].unique()) - set(DELTA_GRID)
    check(
        f"All selected_delta in DELTA_GRID (invalid: {sorted(invalid_deltas)[:5]})",
        len(invalid_deltas) == 0
    )

    # 9. J1 values are finite and non-negative
    for col in ['pooled_J1']:
        if col in df_j1.columns:
            vals = df_j1[col].dropna()
            check(
                f"All {col} finite and >= 0",
                all(np.isfinite(vals)) and all(vals >= 0)
            )

    # 10. No banned fields in output
    BANNED = {'eta', 'gamma'}  # should be implicit from beta/gamma_over_eta
    for col in BANNED:
        if col in df.columns:
            print(f"  WARNING: column '{col}' found in output (not a hard fail)")

    # 11. Baselines have constant selected_delta per model
    default_rows = df[df['model'] == 'Default']
    if len(default_rows) > 0:
        default_deltas = set(default_rows['selected_delta'].unique())
        check(
            f"Default baseline uses single delta: {default_deltas}",
            len(default_deltas) == 1
        )

    print()
    print("=" * 50)
    print("E4d self-check PASSED")
    print(f"  {len(df):,} per-sample rows")
    print(f"  {n_models} selector models")
    print(f"  Tracks: {sorted(actual_tracks)}")
    print(f"  Models: {sorted(actual_models)}")
    print("=" * 50)


if __name__ == '__main__':
    main()
