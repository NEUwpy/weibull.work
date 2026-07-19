"""
Study/01 Formal E3b: Vector-Output Heavy MLP Experiment and Diagnostics

Experiment design:
  - Standalone E3b script under the same data contract as E3a.
  - Reconstruct formal MC samples from manifest seed scheme.
  - Compute observable sample-statistic features (no true parameters).
  - Vector-output MLP: sample features -> 26-dim risk curve (no delta input).
  - Scalar tabular baseline: sample features + delta -> scalar loss.
  - Select delta_hat = argmin_delta predicted_loss (inverse-transformed for vector).
  - Evaluate true selected J1 vs Default/L1/L2/oracle references.

Key differences from E3a:
  - Heavier MLP: (256,128,64), max_iter=300, early_stopping, batch_size=256.
  - Vector-output: 26-dim target (full risk curve), no delta in features.
  - Full fold training (no 12000 sample cap).
  - Train-fold-only target scaling for vector MLP.
  - Comprehensive diagnostics: endpoints, near-optimal/regret, feature ablation, seed stability.

Plan reference: coworker/plans/2026-07-08-study01-e3b-vector-mlp-diagnostics.md
"""

import sys
import os
import json
import time
import math
import hashlib
import subprocess
import warnings
from datetime import datetime, timezone
from itertools import product
from sklearn.exceptions import ConvergenceWarning

import numpy as np
import pandas as pd

# ============================================================
# Path setup
# ============================================================

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

from config import (
    BETA_GRID, ETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID,
    DELTA_GRID, DEFAULT_DELTA, R_MAIN, SEED_NAMESPACE,
    ARTIFACTS_DIR, SHARED_DATA_DIR
)
from studies.common.sample import generate_sample

# ============================================================
# Output directory
# ============================================================

E3B_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "E3b_vector_mlp")
PLOTS_DIR = os.path.join(E3B_OUTPUT_DIR, "plots")

# MC scan data
MC_SCAN_PATH = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")

# ============================================================
# Feature columns (plan contract)
# ============================================================

# Dimensional lifetime features — z-scored with train-fold-only stats
FEATURE_COLS_ZSCORE = [
    'x_min', 'x_max', 'range', 'Q1', 'Med', 'Q3', 'IQR', 'x_bar', 's'
]
# Raw passthrough features — no scaling
FEATURE_COLS_RAW = ['n', 'CV', 'g1', 'g2']
# All sample features (NO delta for vector-output MLP)
SAMPLE_FEATURE_COLS = FEATURE_COLS_ZSCORE + FEATURE_COLS_RAW
# Tabular model features (sample features + delta)
TABULAR_FEATURE_COLS = FEATURE_COLS_ZSCORE + FEATURE_COLS_RAW + ['delta']

# Vector MLP input: SAMPLE_FEATURE_COLS with z-scored dimensional features
VECTOR_FEATURE_COLS = [f'{c}_z' for c in FEATURE_COLS_ZSCORE] + FEATURE_COLS_RAW
# Tabular input: TABULAR_FEATURE_COLS with z-scored dimensional features
TABULAR_INPUT_COLS = [f'{c}_z' for c in FEATURE_COLS_ZSCORE] + FEATURE_COLS_RAW + ['delta']

SAMPLE_KEYS = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
N_DELTAS = len(DELTA_GRID)  # 26

# Vector MLP config (plan contract)
MLP_HIDDEN_LAYERS = (256, 128, 64)
MLP_MAX_ITER = 300
MLP_BATCH_SIZE = 256
MLP_ALPHA = 1e-4
MLP_LR = 1e-3
MLP_VALIDATION_FRACTION = 0.15
MLP_N_ITER_NO_CHANGE = 20

# Seeds for stability check
STABILITY_SEEDS = [42, 2026, 3407]

# Near-optimal epsilons (relative)
NEAR_OPTIMAL_EPS = [0.01, 0.02, 0.05]

# Feature ablation groups
ABLATION_GROUPS = {
    'full': SAMPLE_FEATURE_COLS,
    'n_only': ['n'],
    'scale_quantile': ['n', 'x_min', 'x_max', 'range', 'Q1', 'Med', 'Q3', 'IQR', 'x_bar', 's'],
    'shape': ['n', 'CV', 'g1', 'g2'],
}

# Banned fields that must NEVER appear in model inputs
BANNED_FIELDS = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'seed', 'repeat_id', 'combo_id'}


# ============================================================
# Data integrity checks
# ============================================================

def verify_data_integrity(df, manifest):
    """Stop condition: check for missing combos, duplicate rows, inconsistent counts."""
    expected_combos = (
        len(BETA_GRID) * len(ETA_GRID) * len(GAMMA_OVER_ETA_GRID) * len(N_GRID)
    )
    expected_deltas = len(DELTA_GRID)
    expected_repeats = manifest.get("repeats", R_MAIN)
    expected_rows = expected_combos * expected_deltas * expected_repeats

    actual_rows = len(df)
    print(f"[Data Integrity] Expected rows: {expected_rows}, Actual: {actual_rows}")
    assert actual_rows == expected_rows, \
        f"Row count mismatch: expected {expected_rows}, got {actual_rows}"

    dup_key = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id', 'delta']
    dups = df.duplicated(subset=dup_key).sum()
    print(f"[Data Integrity] Duplicate rows: {dups}")
    assert dups == 0, f"Found {dups} duplicate rows"

    unique_combos = df[['beta', 'eta', 'gamma_over_eta', 'n']].drop_duplicates()
    print(f"[Data Integrity] Unique (beta, gamma/eta, n) combos: {len(unique_combos)}")
    assert len(unique_combos) == expected_combos, \
        f"Expected {expected_combos} combos, got {len(unique_combos)}"

    unique_deltas = sorted(df['delta'].unique())
    print(f"[Data Integrity] Delta values: {len(unique_deltas)}")
    assert unique_deltas == DELTA_GRID, f"Delta grid mismatch"

    rep_counts = df.groupby(['beta', 'eta', 'gamma_over_eta', 'n'])['repeat_id'].nunique()
    print(f"[Data Integrity] Repeats per combo: min={rep_counts.min()}, max={rep_counts.max()}")
    assert rep_counts.min() == expected_repeats, \
        f"Expected {expected_repeats} repeats, min found {rep_counts.min()}"

    fail_rate = None
    if 'status' in df.columns:
        fail_rate = float((df['status'] != 'success').mean())
        print(f"[Data Integrity] Non-success rate: {fail_rate:.4f}")

    print("[Data Integrity] ALL CHECKS PASSED")
    return {
        'expected_rows': int(expected_rows),
        'actual_rows': int(actual_rows),
        'duplicate_rows': int(dups),
        'unique_combos': int(len(unique_combos)),
        'delta_points': int(len(unique_deltas)),
        'repeat_min': int(rep_counts.min()),
        'repeat_max': int(rep_counts.max()),
        'non_success_rate': fail_rate,
    }


# ============================================================
# Sample reconstruction and feature computation
# ============================================================

def verify_sample_reconstruction(manifest):
    """Verify that the manifest seed namespace can reconstruct observable samples."""
    seed_ns = manifest.get("seed_namespace", SEED_NAMESPACE)
    probe = generate_sample(1.5, 1.0, 0.1, 7, 0, seed=seed_ns)
    return {
        'seed_namespace': seed_ns,
        'probe': 'beta=1.5, eta=1.0, gamma=0.1, n=7, repeat_id=0',
        'n': int(len(probe)),
        'x_min': float(probe[0]),
        'x_max': float(probe[-1]),
        'sample_sha256_rounded_12': hashlib_sample(probe),
    }


def hashlib_sample(sample):
    rounded = np.round(np.asarray(sample, dtype=float), 12)
    return hashlib.sha256(rounded.tobytes()).hexdigest()


def compute_sample_features(sample):
    """Compute the observable sample-statistic features (excluding delta).

    Returns dict with keys: x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s, CV, g1, g2, n
    """
    n = len(sample)
    sample_sorted = np.sort(sample)
    x_min = float(sample_sorted[0])
    x_max = float(sample_sorted[-1])
    rng = x_max - x_min
    Q1 = float(np.percentile(sample_sorted, 25))
    Med = float(np.median(sample_sorted))
    Q3 = float(np.percentile(sample_sorted, 75))
    IQR = Q3 - Q1
    x_bar = float(np.mean(sample_sorted))
    s = float(np.std(sample_sorted, ddof=1)) if n > 1 else 0.0
    CV = s / x_bar if x_bar > 0 else 0.0

    if n > 2 and s > 0:
        z = (sample_sorted - x_bar) / s
        g1 = float(np.sum(z**3) / n)
        g2 = float(np.sum(z**4) / n - 3.0)
    else:
        g1 = 0.0
        g2 = 0.0

    return {
        'n': n,
        'x_min': x_min, 'x_max': x_max, 'range': rng,
        'Q1': Q1, 'Med': Med, 'Q3': Q3, 'IQR': IQR,
        'x_bar': x_bar, 's': s, 'CV': CV, 'g1': g1, 'g2': g2
    }


def build_feature_table(df_mc, manifest):
    """Build the per-sample feature table from MC scan data.

    For each unique (beta, eta, gamma, gamma_over_eta, n, repeat_id):
    - Reconstruct the sample using the manifest seed scheme
    - Compute features
    - Merge with MC scan estimates at each delta

    Returns a DataFrame with columns:
      beta, eta, gamma, gamma_over_eta, n, repeat_id, delta,
      <13 features>, beta_hat, eta_hat, gamma_hat, converged, status
    """
    seed_ns = manifest.get("seed_namespace", SEED_NAMESPACE)

    sample_keys = (
        df_mc[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']]
        .drop_duplicates()
        .sort_values(['beta', 'gamma_over_eta', 'n', 'repeat_id'])
        .reset_index(drop=True)
    )
    print(f"[Features] Computing features for {len(sample_keys)} unique samples...")

    feat_records = []
    t0 = time.time()
    for _, row in sample_keys.iterrows():
        beta = float(row['beta'])
        eta = float(row['eta'])
        gamma = float(row['gamma'])
        n = int(row['n'])
        rid = int(row['repeat_id'])

        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_ns)
        feats = compute_sample_features(sample)
        feats['beta'] = beta
        feats['eta'] = eta
        feats['gamma'] = gamma
        feats['gamma_over_eta'] = float(row['gamma_over_eta'])
        feats['n'] = n
        feats['repeat_id'] = rid
        feat_records.append(feats)

    df_feat = pd.DataFrame(feat_records)
    elapsed = time.time() - t0
    print(f"[Features] Done in {elapsed:.1f}s")

    merge_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    df_merged = df_mc.merge(df_feat, on=merge_keys, how='left')

    print(f"[Features] Merged table: {len(df_merged)} rows, "
          f"{len(df_merged.columns)} columns")

    return df_merged


# ============================================================
# Loss computation
# ============================================================

def compute_per_sample_loss(df):
    """Add per-sample loss column.

    loss_i(delta) = ((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2
    """
    r_beta = (df['beta_hat'] - df['beta']) / df['beta']
    r_eta = (df['eta_hat'] - df['eta']) / df['eta']
    r_gamma = (df['gamma_hat'] - df['gamma']) / df['eta']

    df = df.copy()
    df['loss'] = r_beta**2 + r_eta**2 + r_gamma**2
    df['loss'] = df['loss'].replace([np.inf, -np.inf], np.nan)
    return df


# ============================================================
# Split definitions
# ============================================================

def get_combo_split():
    """Combo-holdout folds: same deterministic 5-fold as E3a.

    Each fold holds out 9 complete (beta, gamma/eta, n) combos.
    """
    combos = list(product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID))
    folds = []
    for fold_idx in range(5):
        test_combos = [
            combo for idx, combo in enumerate(combos)
            if idx % 5 == fold_idx
        ]
        train_combos = [
            combo for idx, combo in enumerate(combos)
            if idx % 5 != fold_idx
        ]
        folds.append({
            'fold_name': f'combo_fold_{fold_idx + 1}',
            'train_combos': train_combos,
            'test_combos': test_combos,
        })
    return folds


def split_by_random(df, test_frac=0.2, random_state=42):
    """Random sample-level split (sanity check)."""
    unique_samples = (
        df[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']]
        .drop_duplicates()
        .reset_index(drop=True)
    )
    rng = np.random.default_rng(random_state)
    n_test = int(len(unique_samples) * test_frac)
    test_idx = rng.choice(len(unique_samples), size=n_test, replace=False)
    test_samples = unique_samples.iloc[test_idx]

    merge_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    df_test = df.merge(test_samples[merge_keys], on=merge_keys, how='inner')
    df_train = df.merge(test_samples[merge_keys], on=merge_keys, how='left', indicator=True)
    df_train = df_train[df_train['_merge'] == 'left_only'].drop(columns=['_merge'])
    return df_train, df_test


def build_split_rows():
    split_rows = []
    for fold in get_combo_split():
        for combo in fold['test_combos']:
            split_rows.append({
                'fold': fold['fold_name'],
                'test_beta': combo[0],
                'test_gamma_over_eta': combo[1],
                'test_n': combo[2],
            })
    return split_rows


# ============================================================
# Oracle references (computed from full data — evaluation references only)
# ============================================================

def compute_reference_deltas(df):
    """Compute reference delta selections at each information layer."""
    default_delta = DEFAULT_DELTA

    global_loss = df.groupby('delta')['loss'].apply(
        lambda x: np.sqrt(np.nanmean(x))
    )
    l1_delta = global_loss.idxmin()

    l2_table = {}
    for n_val in N_GRID:
        df_n = df[df['n'] == n_val]
        loss_by_delta = df_n.groupby('delta')['loss'].apply(
            lambda x: np.sqrt(np.nanmean(x))
        )
        l2_table[n_val] = {
            'delta_star': float(loss_by_delta.idxmin()),
            'J1': float(loss_by_delta.min())
        }

    l3_table = {}
    for b_val in BETA_GRID:
        df_b = df[df['beta'] == b_val]
        loss_by_delta = df_b.groupby('delta')['loss'].apply(
            lambda x: np.sqrt(np.nanmean(x))
        )
        l3_table[b_val] = {
            'delta_star': float(loss_by_delta.idxmin()),
            'J1': float(loss_by_delta.min())
        }

    l4_table = {}
    for b_val in BETA_GRID:
        for n_val in N_GRID:
            df_bn = df[(df['beta'] == b_val) & (df['n'] == n_val)]
            loss_by_delta = df_bn.groupby('delta')['loss'].apply(
                lambda x: np.sqrt(np.nanmean(x))
            )
            l4_table[(b_val, n_val)] = {
                'delta_star': float(loss_by_delta.idxmin()),
                'J1': float(loss_by_delta.min())
            }

    l5_table = {}
    for b_val in BETA_GRID:
        for g_val in GAMMA_OVER_ETA_GRID:
            for n_val in N_GRID:
                df_bgn = df[
                    (df['beta'] == b_val) &
                    (df['gamma_over_eta'] == g_val) &
                    (df['n'] == n_val)
                ]
                loss_by_delta = df_bgn.groupby('delta')['loss'].apply(
                    lambda x: np.sqrt(np.nanmean(x))
                )
                l5_table[(b_val, g_val, n_val)] = {
                    'delta_star': float(loss_by_delta.idxmin()),
                    'J1': float(loss_by_delta.min())
                }

    return {
        'default_delta': default_delta,
        'l1_delta': float(l1_delta),
        'l2_table': l2_table,
        'l3_table': l3_table,
        'l4_table': l4_table,
        'l5_table': l5_table,
    }


# ============================================================
# Fold preparation (scalers, failure penalty, group labels)
# ============================================================

def prepare_fold_data(df_train_raw, df_test_raw):
    """Prepare a training fold: scalers, failure_penalty, labels.

    - Z-score dimensional features from TRAIN only.
    - Failure penalty from TRAIN only.
    - L4/L5 vector group-mean curves from TRAIN only.
    - Returns pivoted vector targets for vector-output MLP.

    Returns dict with prepared data structures.
    """
    # Failure penalty
    train_valid_loss = df_train_raw['loss'].dropna()
    failure_penalty = float(np.nanpercentile(train_valid_loss, 99))
    print(f"  Failure penalty (train p99): {failure_penalty:.6f}")

    # Fill NaN losses
    df_train = df_train_raw.copy()
    df_test = df_test_raw.copy()
    df_train['loss_filled'] = df_train['loss'].fillna(failure_penalty)
    df_test['loss_filled'] = df_test['loss'].fillna(failure_penalty)
    df_train['is_valid'] = df_train.get('status', 'success').eq('success') & df_train['loss'].notna()
    df_test['is_valid'] = df_test.get('status', 'success').eq('success') & df_test['loss'].notna()

    # Z-score dimensional features from TRAIN
    zscore_means = {}
    zscore_stds = {}
    for col in FEATURE_COLS_ZSCORE:
        vals = df_train[col].astype(float)
        zscore_means[col] = float(vals.mean())
        zscore_stds[col] = float(vals.std(ddof=0))
        if zscore_stds[col] < 1e-12:
            zscore_stds[col] = 1.0

    def apply_zscore(df):
        df = df.copy()
        for col in FEATURE_COLS_ZSCORE:
            df[f'{col}_z'] = (df[col].astype(float) - zscore_means[col]) / zscore_stds[col]
        return df

    df_train = apply_zscore(df_train)
    df_test = apply_zscore(df_test)

    # Compute L4/L5 vector group labels from TRAIN only
    # L4: mean loss per (beta, n, delta) -> 26-dim curve per (beta, n)
    # L5: mean loss per (beta, gamma/eta, n, delta) -> 26-dim curve per (beta, gamma/eta, n)
    l4_group = (
        df_train.groupby(['beta', 'n', 'delta'])['loss_filled']
        .mean()
        .reset_index()
        .rename(columns={'loss_filled': 'l4_label'})
    )
    l5_group = (
        df_train.groupby(['beta', 'gamma_over_eta', 'n', 'delta'])['loss_filled']
        .mean()
        .reset_index()
        .rename(columns={'loss_filled': 'l5_label'})
    )
    global_fallback = (
        df_train.groupby('delta')['loss_filled']
        .mean()
        .reset_index()
        .rename(columns={'loss_filled': 'global_label'})
    )

    df_train = df_train.merge(l4_group, on=['beta', 'n', 'delta'], how='left')
    df_train = df_train.merge(l5_group, on=['beta', 'gamma_over_eta', 'n', 'delta'], how='left')
    df_train = df_train.merge(global_fallback, on='delta', how='left')
    df_train['l4_label'] = df_train['l4_label'].fillna(df_train['global_label'])
    df_train['l5_label'] = df_train['l5_label'].fillna(df_train['global_label'])

    df_test = df_test.merge(l4_group, on=['beta', 'n', 'delta'], how='left')
    df_test = df_test.merge(l5_group, on=['beta', 'gamma_over_eta', 'n', 'delta'], how='left')
    df_test = df_test.merge(global_fallback, on='delta', how='left')
    df_test['l4_label'] = df_test['l4_label'].fillna(df_test['global_label'])
    df_test['l5_label'] = df_test['l5_label'].fillna(df_test['global_label'])

    return {
        'zscore_means': zscore_means,
        'zscore_stds': zscore_stds,
        'failure_penalty': failure_penalty,
        'df_train': df_train,
        'df_test': df_test,
    }


def pivot_to_vector(df, label_col='loss_filled'):
    """Pivot a long-format DataFrame to vector format: one row per sample.

    Returns (result_df, Y_matrix) where:
    - result_df has sample keys + features (one row per sample), STRICTLY aligned with Y rows
    - Y_matrix is (n_samples, 26) with columns ordered by DELTA_GRID

    CRITICAL: result_df row i corresponds to Y_matrix row i, guaranteed by
    constructing Y from the final sorted result, not from an intermediate pivot.
    """
    # Get one feature row per sample (one row per unique SAMPLE_KEYS combo)
    feat_cols = [c for c in SAMPLE_FEATURE_COLS if c not in SAMPLE_KEYS]
    sample_df = df[SAMPLE_KEYS + feat_cols].drop_duplicates(subset=SAMPLE_KEYS).reset_index(drop=True)

    # Pivot labels to wide format, sorted by SAMPLE_KEYS for deterministic order
    pivot = df.pivot_table(
        index=SAMPLE_KEYS,
        columns='delta',
        values=label_col,
        aggfunc='first'
    ).reset_index()

    # Merge features into the pivot (pivot is the source of truth for row order)
    result = pivot[SAMPLE_KEYS].merge(sample_df, on=SAMPLE_KEYS, how='left')

    # Build Y directly from pivot, which has the SAME row order as result
    Y = np.zeros((len(pivot), N_DELTAS), dtype=np.float64)
    for j, d in enumerate(DELTA_GRID):
        if d in pivot.columns:
            Y[:, j] = pivot[d].values
        else:
            Y[:, j] = np.nan

    # Safety assert: result and Y must have the same number of rows
    assert len(result) == Y.shape[0], \
        f"Row count mismatch: result={len(result)}, Y={Y.shape[0]}"

    return result, Y


def apply_zscore_to_vector_features(df_samples, zscore_means, zscore_stds, feature_cols=None):
    """Apply train-fold z-score to the vector-feature columns.

    If feature_cols is None, uses the default SAMPLE_FEATURE_COLS.
    Returns the feature matrix for the vector MLP.
    """
    if feature_cols is None:
        feature_cols = SAMPLE_FEATURE_COLS

    n_samples = len(df_samples)
    # Determine which columns need z-scoring
    zscore_subset = [c for c in FEATURE_COLS_ZSCORE if c in feature_cols]
    raw_subset = [c for c in FEATURE_COLS_RAW if c in feature_cols]

    cols = []
    for col in zscore_subset:
        vals = df_samples[col].astype(float).values
        std = zscore_stds.get(col, 1.0)
        mean = zscore_means.get(col, 0.0)
        if std < 1e-12:
            std = 1.0
        cols.append((vals - mean) / std)
    for col in raw_subset:
        cols.append(df_samples[col].astype(float).values)

    if not cols:
        return np.zeros((n_samples, 0), dtype=np.float32)

    return np.column_stack(cols).astype(np.float32)


# ============================================================
# Vector-output MLP training
# ============================================================

def train_vector_mlp(X_train, Y_train, X_test, seed=42,
                     hidden_layers=MLP_HIDDEN_LAYERS,
                     max_iter=MLP_MAX_ITER,
                     batch_size=MLP_BATCH_SIZE):
    """Train a vector-output MLP that predicts the full 26-dim risk curve.

    Uses train-fold-only target scaling (StandardScaler on 26-dim targets).
    Inverse-transforms predictions back to raw loss before returning.

    Returns predicted curves in raw loss space, shape (n_test, 26).
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPRegressor

    # Target scaling (train-only)
    target_scaler = StandardScaler()
    Y_train_scaled = target_scaler.fit_transform(Y_train)

    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=ConvergenceWarning)
        model = MLPRegressor(
            hidden_layer_sizes=hidden_layers,
            activation='relu',
            solver='adam',
            alpha=MLP_ALPHA,
            learning_rate_init=MLP_LR,
            max_iter=max_iter,
            early_stopping=True,
            validation_fraction=MLP_VALIDATION_FRACTION,
            n_iter_no_change=MLP_N_ITER_NO_CHANGE,
            random_state=seed,
            batch_size=batch_size,
        )
        model.fit(X_train, Y_train_scaled)

    Y_pred_scaled = model.predict(X_test)
    Y_pred_raw = target_scaler.inverse_transform(Y_pred_scaled)
    # Clip to non-negative
    Y_pred_raw = np.clip(Y_pred_raw, 0, None)

    n_iter = model.n_iter_
    return Y_pred_raw, n_iter


def train_tabular_scalar(X_train, y_train, X_test):
    """Train HistGradientBoosting on scalar (features + delta) -> raw loss."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    model = HistGradientBoostingRegressor(
        max_iter=200,
        learning_rate=0.1,
        max_depth=6,
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model.predict(X_test)


# ============================================================
# Evaluation: selection quality from predicted curves
# ============================================================

def evaluate_vector_selection(df_test_samples, Y_pred, Y_true_loss, model_name,
                              is_valid=None):
    """Evaluate delta selection from vector predictions.

    For each sample, delta_hat = argmin over 26 predicted loss values.
    Then look up the TRUE loss at that delta.

    Args:
        df_test_samples: DataFrame with sample keys, aligned to Y_pred rows.
        Y_pred: (n_samples, 26) predicted risk curves.
        Y_true_loss: (n_samples, 26) true loss values.
        model_name: label for results.
        is_valid: (n_samples,) bool array of validity flags.

    Returns dict with J1, per-n, delta_distribution, df_sel.
    """
    n_samples = len(df_test_samples)
    if is_valid is None:
        is_valid = np.ones(n_samples, dtype=bool)

    best_indices = np.argmin(Y_pred, axis=1)
    selected_deltas = np.array([DELTA_GRID[i] for i in best_indices])
    true_losses = Y_true_loss[np.arange(n_samples), best_indices]
    valid_flags = is_valid

    results = []
    for i in range(n_samples):
        results.append({
            'beta': float(df_test_samples.iloc[i]['beta']),
            'gamma_over_eta': float(df_test_samples.iloc[i]['gamma_over_eta']),
            'n': int(df_test_samples.iloc[i]['n']),
            'repeat_id': int(df_test_samples.iloc[i]['repeat_id']),
            'selected_delta': float(selected_deltas[i]),
            'true_loss': float(true_losses[i]),
            'is_valid': bool(valid_flags[i]),
            'model': model_name,
        })

    df_sel = pd.DataFrame(results)
    j1 = math.sqrt(df_sel['true_loss'].mean())
    failure_rate = 1.0 - df_sel['is_valid'].mean()

    per_n = {}
    for n_val in sorted(df_sel['n'].unique()):
        sub = df_sel[df_sel['n'] == n_val]
        per_n[n_val] = {
            'J1': math.sqrt(sub['true_loss'].mean()),
            'failure_rate': 1.0 - sub['is_valid'].mean(),
            'count': len(sub),
        }

    return {
        'model': model_name,
        'J1': j1,
        'failure_rate': failure_rate,
        'n_samples': len(df_sel),
        'per_n': per_n,
        'delta_distribution': df_sel['selected_delta'].value_counts().sort_index().to_dict(),
        'df_sel': df_sel,
    }


def evaluate_reference_selection(df_test_samples, Y_true_loss, ref_name, ref_delta_fn):
    """Evaluate a reference delta selection rule on the test set.

    ref_delta_fn(sample_row) -> selected delta index (0..25)
    """
    n_samples = len(df_test_samples)
    results = []

    for i in range(n_samples):
        row = df_test_samples.iloc[i]
        delta_idx = ref_delta_fn(row)
        true_loss = Y_true_loss[i, delta_idx]
        results.append({
            'beta': float(row['beta']),
            'gamma_over_eta': float(row['gamma_over_eta']),
            'n': int(row['n']),
            'repeat_id': int(row['repeat_id']),
            'selected_delta': float(DELTA_GRID[delta_idx]),
            'true_loss': float(true_loss),
            'is_valid': True,
            'model': ref_name,
        })

    df_sel = pd.DataFrame(results)
    j1 = math.sqrt(df_sel['true_loss'].mean())
    failure_rate = 0.0

    per_n = {}
    for n_val in sorted(df_sel['n'].unique()):
        sub = df_sel[df_sel['n'] == n_val]
        per_n[n_val] = {
            'J1': math.sqrt(sub['true_loss'].mean()),
            'failure_rate': 0.0,
            'count': len(sub),
        }

    return {
        'model': ref_name,
        'J1': j1,
        'failure_rate': failure_rate,
        'n_samples': len(df_sel),
        'per_n': per_n,
        'delta_distribution': df_sel['selected_delta'].value_counts().sort_index().to_dict(),
        'df_sel': df_sel,
    }


def evaluate_l6_hindsight(df_test_samples, Y_true_loss, model_name='L6-hindsight'):
    """Per-sample hindsight: select delta with minimum TRUE loss."""
    n_samples = len(df_test_samples)
    best_indices = np.argmin(Y_true_loss, axis=1)
    results = []

    for i in range(n_samples):
        row = df_test_samples.iloc[i]
        results.append({
            'beta': float(row['beta']),
            'gamma_over_eta': float(row['gamma_over_eta']),
            'n': int(row['n']),
            'repeat_id': int(row['repeat_id']),
            'selected_delta': float(DELTA_GRID[best_indices[i]]),
            'true_loss': float(Y_true_loss[i, best_indices[i]]),
            'is_valid': True,
            'model': model_name,
        })

    df_sel = pd.DataFrame(results)
    j1 = math.sqrt(df_sel['true_loss'].mean())

    per_n = {}
    for n_val in sorted(df_sel['n'].unique()):
        sub = df_sel[df_sel['n'] == n_val]
        per_n[n_val] = {
            'J1': math.sqrt(sub['true_loss'].mean()),
            'failure_rate': 0.0,
            'count': len(sub),
        }

    return {
        'model': model_name,
        'J1': j1,
        'failure_rate': 0.0,
        'n_samples': len(df_sel),
        'per_n': per_n,
        'delta_distribution': df_sel['selected_delta'].value_counts().sort_index().to_dict(),
        'df_sel': df_sel,
    }


# ============================================================
# Diagnostics: endpoints, near-optimal, regret
# ============================================================

ENDPOINT_INDICES = {
    'delta_0': DELTA_GRID.index(0.00),
    'delta_0_02': DELTA_GRID.index(0.02),
    'delta_0_48': DELTA_GRID.index(0.48),
    'delta_0_5': DELTA_GRID.index(0.50),
}


def compute_endpoint_diagnostics(df_sel, model_name):
    """Compute endpoint selection rates for a model's selected deltas."""
    sel = df_sel[df_sel['model'] == model_name].copy()
    n = len(sel)
    if n == 0:
        return []

    p_d0 = float((sel['selected_delta'] == 0.00).mean())
    p_d05 = float((sel['selected_delta'] == 0.50).mean())
    p_extreme = float(
        sel['selected_delta'].isin([0.00, 0.02, 0.48, 0.50]).mean()
    )

    rows = [{
        'model': model_name,
        'category': 'pooled',
        'P_delta_0': p_d0,
        'P_delta_0.5': p_d05,
        'P_extreme': p_extreme,
        'n_samples': n,
    }]

    # By n
    for n_val in sorted(sel['n'].unique()):
        sub = sel[sel['n'] == n_val]
        rows.append({
            'model': model_name,
            'category': f'n={n_val}',
            'P_delta_0': float((sub['selected_delta'] == 0.00).mean()),
            'P_delta_0.5': float((sub['selected_delta'] == 0.50).mean()),
            'P_extreme': float(sub['selected_delta'].isin([0.00, 0.02, 0.48, 0.50]).mean()),
            'n_samples': len(sub),
        })

    # By combo
    for (b, g, nv), sub in sel.groupby(['beta', 'gamma_over_eta', 'n']):
        rows.append({
            'model': model_name,
            'category': f'b={b}_g={g}_n={nv}',
            'P_delta_0': float((sub['selected_delta'] == 0.00).mean()),
            'P_delta_0.5': float((sub['selected_delta'] == 0.50).mean()),
            'P_extreme': float(sub['selected_delta'].isin([0.00, 0.02, 0.48, 0.50]).mean()),
            'n_samples': len(sub),
        })

    return rows


def compute_near_optimal_diagnostics(df_sel, Y_true_loss_all, model_name):
    """Compute selected loss, oracle min loss, regret, and near-optimal hit rates.

    Args:
        df_sel: selected results for this model (must have sample keys + true_loss).
        Y_true_loss_all: dict mapping (beta, gamma_over_eta, n, repeat_id) -> 26-dim true loss array.
    """
    sel = df_sel[df_sel['model'] == model_name].copy()
    rows = []

    for _, r in sel.iterrows():
        key = (r['beta'], r['gamma_over_eta'], r['n'], r['repeat_id'])
        true_curve = Y_true_loss_all.get(key)
        if true_curve is None:
            continue
        oracle_min = float(np.min(true_curve))
        selected_loss = r['true_loss']
        regret = selected_loss - oracle_min
        rel_regret = regret / oracle_min if oracle_min > 1e-12 else regret

        near_hits = {}
        for eps in NEAR_OPTIMAL_EPS:
            near_hits[f'near_{eps}'] = int(rel_regret <= eps)

        rows.append({
            'model': model_name,
            'beta': r['beta'],
            'gamma_over_eta': r['gamma_over_eta'],
            'n': r['n'],
            'selected_loss': selected_loss,
            'oracle_min_loss': oracle_min,
            'regret': regret,
            'rel_regret': rel_regret,
            **near_hits,
        })

    df_diag = pd.DataFrame(rows)
    if len(df_diag) == 0:
        return df_diag

    # Aggregate
    summary = {
        'model': model_name,
        'mean_selected_loss': df_diag['selected_loss'].mean(),
        'mean_oracle_min': df_diag['oracle_min_loss'].mean(),
        'mean_regret': df_diag['regret'].mean(),
        'mean_rel_regret': df_diag['rel_regret'].mean(),
    }
    for eps in NEAR_OPTIMAL_EPS:
        summary[f'near_{eps}_rate'] = df_diag[f'near_{eps}'].mean()

    return df_diag, summary


# ============================================================
# Feature ablation
# ============================================================

def run_feature_ablation(fold_prep, df_train_long, df_test_long, seed=42):
    """Run Vector-MLP-L6 with different feature groups.

    Only one fold, seed=42.
    Returns list of dicts with pooled/per-n J1, endpoint rate, near-optimal rate.
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPRegressor

    zscore_means = fold_prep['zscore_means']
    zscore_stds = fold_prep['zscore_stds']

    results = []
    for group_name, group_features in ABLATION_GROUPS.items():
        print(f"    Ablation: {group_name} ({len(group_features)} features)")

        # Pivot train/test to vector
        train_samples, Y_train = pivot_to_vector(df_train_long, 'loss_filled')
        test_samples, Y_test = pivot_to_vector(df_test_long, 'loss_filled')

        # Build feature matrices with only this group's features
        X_train = apply_zscore_to_vector_features(
            train_samples, zscore_means, zscore_stds, feature_cols=group_features
        )
        X_test = apply_zscore_to_vector_features(
            test_samples, zscore_means, zscore_stds, feature_cols=group_features
        )

        if X_train.shape[1] == 0:
            print(f"      Skipping {group_name}: no features")
            continue

        # Train
        target_scaler = StandardScaler()
        Y_train_scaled = target_scaler.fit_transform(Y_train)

        with warnings.catch_warnings():
            warnings.simplefilter('ignore', category=ConvergenceWarning)
            model = MLPRegressor(
                hidden_layer_sizes=MLP_HIDDEN_LAYERS,
                activation='relu', solver='adam',
                alpha=MLP_ALPHA, learning_rate_init=MLP_LR,
                max_iter=MLP_MAX_ITER, early_stopping=True,
                validation_fraction=MLP_VALIDATION_FRACTION,
                n_iter_no_change=MLP_N_ITER_NO_CHANGE,
                random_state=seed, batch_size=MLP_BATCH_SIZE,
            )
            model.fit(X_train, Y_train_scaled)

        Y_pred_scaled = model.predict(X_test)
        Y_pred = target_scaler.inverse_transform(Y_pred_scaled)
        Y_pred = np.clip(Y_pred, 0, None)

        # Evaluate
        res = evaluate_vector_selection(
            test_samples, Y_pred, Y_test, f'Ablation-{group_name}'
        )

        # Endpoint rate
        sel = res['df_sel']
        p_extreme = float(sel['selected_delta'].isin([0.00, 0.02, 0.48, 0.50]).mean())

        # Near-optimal
        true_loss_map = {}
        for i in range(len(test_samples)):
            row = test_samples.iloc[i]
            key = (row['beta'], row['gamma_over_eta'], row['n'], row['repeat_id'])
            true_loss_map[key] = Y_test[i]
        df_no, _ = compute_near_optimal_diagnostics(sel, true_loss_map, f'Ablation-{group_name}')
        near_5 = float(df_no['near_0.05'].mean()) if len(df_no) > 0 else 0.0

        results.append({
            'feature_group': group_name,
            'n_features': len(group_features),
            'pooled_J1': res['J1'],
            'J1_n7': res['per_n'].get(7, {}).get('J1', float('nan')),
            'J1_n10': res['per_n'].get(10, {}).get('J1', float('nan')),
            'J1_n20': res['per_n'].get(20, {}).get('J1', float('nan')),
            'endpoint_rate': p_extreme,
            'near_5pct_rate': near_5,
            'n_iter': model.n_iter_,
        })

    return results


# ============================================================
# Seed stability
# ============================================================

def run_seed_stability(all_fold_results, df_full, refs, seeds=None):
    """Run Vector-MLP-L6 full features with multiple seeds across ALL combo folds.

    Returns list of per-seed results (pooled across all 5 folds).
    This supports the plan's APPROVE criterion: 3-seed mean combo-holdout J1.
    """
    if seeds is None:
        seeds = STABILITY_SEEDS

    combo_folds = get_combo_split()
    seed_results = []

    for seed in seeds:
        print(f"\n    Seed stability: seed={seed} (5-fold combo holdout)")
        all_seed_fold_dfs = []

        for fold_idx, fold in enumerate(combo_folds):
            fold_result = all_fold_results[fold_idx]
            df_train_long = fold_result['_df_train_long']
            df_test_long = fold_result['_df_test_long']
            zscore_means = fold_result['_fold_prep']['zscore_means']
            zscore_stds = fold_result['_fold_prep']['zscore_stds']

            train_samples, Y_train = pivot_to_vector(df_train_long, 'loss_filled')
            test_samples, Y_test = pivot_to_vector(df_test_long, 'loss_filled')

            X_train = apply_zscore_to_vector_features(train_samples, zscore_means, zscore_stds)
            X_test = apply_zscore_to_vector_features(test_samples, zscore_means, zscore_stds)

            Y_pred, n_iter = train_vector_mlp(X_train, Y_train, X_test, seed=seed)
            res = evaluate_vector_selection(
                test_samples, Y_pred, Y_test, f'Vector-MLP-L6-seed{seed}'
            )
            all_seed_fold_dfs.append(res['df_sel'])

        # Pool across folds
        df_pooled = pd.concat(all_seed_fold_dfs, ignore_index=True)
        pooled_j1 = math.sqrt(df_pooled['true_loss'].mean())
        p_extreme = float(df_pooled['selected_delta'].isin([0.00, 0.02, 0.48, 0.50]).mean())

        per_n = {}
        for n_val in sorted(df_pooled['n'].unique()):
            sub = df_pooled[df_pooled['n'] == n_val]
            per_n[n_val] = math.sqrt(sub['true_loss'].mean())

        seed_results.append({
            'seed': seed,
            'pooled_J1': pooled_j1,
            'J1_n7': per_n.get(7, float('nan')),
            'J1_n10': per_n.get(10, float('nan')),
            'J1_n20': per_n.get(20, float('nan')),
            'endpoint_rate': p_extreme,
            'n_iter': n_iter,
        })
        print(f"      seed={seed}: pooled J1={pooled_j1:.6f}, endpoint={p_extreme:.4f}")

    return seed_results


# ============================================================
# Banned field check
# ============================================================

def verify_no_banned_fields(feature_cols):
    """Verify that no banned field appears in model input columns."""
    for col in feature_cols:
        base = col.replace('_z', '')
        assert base not in BANNED_FIELDS, \
            f"BANNED field '{base}' found in feature columns: {feature_cols}"


# ============================================================
# Main experiment
# ============================================================

def run_combo_fold(df_full, fold, refs, seed=42):
    """Run all models on one combo-holdout fold. Returns fold results dict."""
    fold_name = fold['fold_name']
    train_combo_set = set(fold['train_combos'])
    test_combo_set = set(fold['test_combos'])

    # Build combo filter without copying the full DataFrame (memory optimization)
    # Vectorized: string-encode combos and use isin (avoids full DataFrame copy)
    combo_str = (
        df_full['beta'].astype(str) + '|' +
        df_full['gamma_over_eta'].astype(str) + '|' +
        df_full['n'].astype(str)
    )
    train_strs = set(
        f'{b}|{g}|{n}' for b, g, n in train_combo_set
    )
    test_strs = set(
        f'{b}|{g}|{n}' for b, g, n in test_combo_set
    )
    train_mask = combo_str.isin(train_strs)
    test_mask = combo_str.isin(test_strs)
    df_tr_long = df_full[train_mask].copy()
    df_te_long = df_full[test_mask].copy()
    print(f"  Train rows: {len(df_tr_long)}, Test rows: {len(df_te_long)}")

    fold_prep = prepare_fold_data(df_tr_long, df_te_long)
    df_train_long = fold_prep['df_train']
    df_test_long = fold_prep['df_test']

    zscore_means = fold_prep['zscore_means']
    zscore_stds = fold_prep['zscore_stds']

    # Pivot to vector format
    train_samples, Y_train_l6 = pivot_to_vector(df_train_long, 'loss_filled')
    test_samples, Y_test = pivot_to_vector(df_test_long, 'loss_filled')

    # Also pivot L4 and L5 labels
    _, Y_train_l4 = pivot_to_vector(df_train_long, 'l4_label')
    _, Y_train_l5 = pivot_to_vector(df_train_long, 'l5_label')

    # Verify alignment: train_samples rows match Y_train_l4/l5
    assert len(Y_train_l4) == len(Y_train_l6), "L4 label count mismatch"
    assert len(Y_train_l5) == len(Y_train_l6), "L5 label count mismatch"

    # Build feature matrices
    X_train = apply_zscore_to_vector_features(train_samples, zscore_means, zscore_stds)
    X_test = apply_zscore_to_vector_features(test_samples, zscore_means, zscore_stds)

    verify_no_banned_fields(SAMPLE_FEATURE_COLS)
    print(f"  Vector MLP: X_train={X_train.shape}, Y_train_l6={Y_train_l6.shape}, X_test={X_test.shape}")

    fold_results = {}

    # --- Vector-MLP-L6 ---
    print(f"  Training Vector-MLP-L6...")
    t0 = time.time()
    Y_pred_l6, n_iter_l6 = train_vector_mlp(X_train, Y_train_l6, X_test, seed=seed)
    t_l6 = time.time() - t0
    print(f"    Done in {t_l6:.1f}s, n_iter={n_iter_l6}")
    fold_results['Vector-MLP-L6'] = evaluate_vector_selection(
        test_samples, Y_pred_l6, Y_test, 'Vector-MLP-L6'
    )

    # --- Vector-MLP-L5 ---
    print(f"  Training Vector-MLP-L5...")
    t0 = time.time()
    Y_pred_l5, n_iter_l5 = train_vector_mlp(X_train, Y_train_l5, X_test, seed=seed)
    t_l5 = time.time() - t0
    print(f"    Done in {t_l5:.1f}s, n_iter={n_iter_l5}")
    fold_results['Vector-MLP-L5'] = evaluate_vector_selection(
        test_samples, Y_pred_l5, Y_test, 'Vector-MLP-L5'
    )

    # --- Vector-MLP-L4 ---
    print(f"  Training Vector-MLP-L4...")
    t0 = time.time()
    Y_pred_l4, n_iter_l4 = train_vector_mlp(X_train, Y_train_l4, X_test, seed=seed)
    t_l4 = time.time() - t0
    print(f"    Done in {t_l4:.1f}s, n_iter={n_iter_l4}")
    fold_results['Vector-MLP-L4'] = evaluate_vector_selection(
        test_samples, Y_pred_l4, Y_test, 'Vector-MLP-L4'
    )

    # --- Tabular-L6 (scalar) ---
    print(f"  Training Tabular-L6...")
    # Build scalar input: features + delta
    tab_input_cols = [f'{c}_z' for c in FEATURE_COLS_ZSCORE] + FEATURE_COLS_RAW + ['delta']
    df_tr_scalar = df_train_long.copy()
    df_te_scalar = df_test_long.copy()
    X_train_tab = df_tr_scalar[tab_input_cols].values.astype(np.float32)
    X_test_tab = df_te_scalar[tab_input_cols].values.astype(np.float32)
    y_train_tab = df_tr_scalar['loss_filled'].values.astype(np.float32)

    t0 = time.time()
    preds_tab = train_tabular_scalar(X_train_tab, y_train_tab, X_test_tab)
    t_tab = time.time() - t0
    print(f"    Done in {t_tab:.1f}s")

    # Evaluate tabular: need to find argmin predicted per sample
    df_te_scalar = df_te_scalar.copy()
    df_te_scalar['pred_tab'] = preds_tab
    tab_sel_results = []
    for _, grp in df_te_scalar.groupby(SAMPLE_KEYS):
        if len(grp) != N_DELTAS:
            continue
        best_idx = np.argmin(grp['pred_tab'].values)
        sel_row = grp.iloc[best_idx]
        tab_sel_results.append({
            'beta': float(sel_row['beta']),
            'gamma_over_eta': float(sel_row['gamma_over_eta']),
            'n': int(sel_row['n']),
            'repeat_id': int(sel_row['repeat_id']),
            'selected_delta': float(sel_row['delta']),
            'true_loss': float(sel_row['loss_filled']),
            'is_valid': bool(sel_row['is_valid']),
            'model': 'Tabular-L6',
        })
    df_tab_sel = pd.DataFrame(tab_sel_results)
    tab_J1 = math.sqrt(df_tab_sel['true_loss'].mean())
    tab_per_n = {}
    for n_val in sorted(df_tab_sel['n'].unique()):
        sub = df_tab_sel[df_tab_sel['n'] == n_val]
        tab_per_n[n_val] = {
            'J1': math.sqrt(sub['true_loss'].mean()),
            'failure_rate': 1.0 - sub['is_valid'].mean(),
            'count': len(sub),
        }
    fold_results['Tabular-L6'] = {
        'model': 'Tabular-L6',
        'J1': tab_J1,
        'failure_rate': 1.0 - df_tab_sel['is_valid'].mean(),
        'n_samples': len(df_tab_sel),
        'per_n': tab_per_n,
        'delta_distribution': df_tab_sel['selected_delta'].value_counts().sort_index().to_dict(),
        'df_sel': df_tab_sel,
    }

    # --- References ---
    def get_delta_idx(delta_val):
        return DELTA_GRID.index(float(delta_val))

    ref_fns = {
        'Default': lambda r: get_delta_idx(refs['default_delta']),
        'L1': lambda r: get_delta_idx(refs['l1_delta']),
        'L2': lambda r: get_delta_idx(refs['l2_table'][int(r['n'])]['delta_star']),
        'L3-oracle': lambda r: get_delta_idx(refs['l3_table'][float(r['beta'])]['delta_star']),
        'L4-oracle': lambda r: get_delta_idx(refs['l4_table'][(float(r['beta']), int(r['n']))]['delta_star']),
        'L5-oracle': lambda r: get_delta_idx(refs['l5_table'][(float(r['beta']), float(r['gamma_over_eta']), int(r['n']))]['delta_star']),
    }
    for ref_name, ref_fn in ref_fns.items():
        fold_results[ref_name] = evaluate_reference_selection(
            test_samples, Y_test, ref_name, ref_fn
        )

    fold_results['L6-hindsight'] = evaluate_l6_hindsight(test_samples, Y_test)

    # Store timing info
    fold_results['_timing'] = {
        'Vector-MLP-L6': t_l6, 'Vector-MLP-L5': t_l5,
        'Vector-MLP-L4': t_l4, 'Tabular-L6': t_tab,
    }
    fold_results['_n_iters'] = {
        'Vector-MLP-L6': n_iter_l6, 'Vector-MLP-L5': n_iter_l5,
        'Vector-MLP-L4': n_iter_l4,
    }
    fold_results['_fold_prep'] = fold_prep
    fold_results['_df_train_long'] = df_train_long
    fold_results['_df_test_long'] = df_test_long
    fold_results['_test_samples'] = test_samples
    fold_results['_Y_test'] = Y_test

    return fold_results


def pool_combo_results(all_fold_results):
    """Pool selection results across all combo folds for each model."""
    model_names = [
        'Vector-MLP-L4', 'Vector-MLP-L5', 'Vector-MLP-L6', 'Tabular-L6',
        'Default', 'L1', 'L2', 'L3-oracle', 'L4-oracle', 'L5-oracle', 'L6-hindsight'
    ]

    pooled = []
    for model_name in model_names:
        all_dfs = []
        for fold_result in all_fold_results:
            r = fold_result.get(model_name)
            if r and 'df_sel' in r:
                all_dfs.append(r['df_sel'])

        if not all_dfs:
            continue

        df_pooled = pd.concat(all_dfs, ignore_index=True)
        j1 = math.sqrt(df_pooled['true_loss'].mean())
        fail = 1.0 - df_pooled['is_valid'].mean()

        per_n = {}
        for n_val in sorted(df_pooled['n'].unique()):
            sub = df_pooled[df_pooled['n'] == n_val]
            per_n[n_val] = {
                'J1': math.sqrt(sub['true_loss'].mean()),
                'failure_rate': 1.0 - sub['is_valid'].mean(),
                'count': len(sub),
            }

        pooled.append({
            'model': model_name,
            'split': 'combo_holdout_pooled',
            'J1': j1,
            'failure_rate': fail,
            'n_samples': len(df_pooled),
            'per_n': per_n,
            'delta_distribution': df_pooled['selected_delta'].value_counts().sort_index().to_dict(),
            'df_sel': df_pooled,
        })

    return pooled


def run_random_split_sanity(df_full, refs, seed=42):
    """Run random split as sanity check. Returns results dict."""
    print("\n  Random split (sanity check)...")
    df_tr_long, df_te_long = split_by_random(df_full, test_frac=0.2, random_state=42)
    print(f"  Train rows: {len(df_tr_long)}, Test rows: {len(df_te_long)}")

    fold_prep = prepare_fold_data(df_tr_long, df_te_long)
    df_train_long = fold_prep['df_train']
    df_test_long = fold_prep['df_test']

    zscore_means = fold_prep['zscore_means']
    zscore_stds = fold_prep['zscore_stds']

    train_samples, Y_train_l6 = pivot_to_vector(df_train_long, 'loss_filled')
    test_samples, Y_test = pivot_to_vector(df_test_long, 'loss_filled')

    X_train = apply_zscore_to_vector_features(train_samples, zscore_means, zscore_stds)
    X_test = apply_zscore_to_vector_features(test_samples, zscore_means, zscore_stds)

    results = {}

    # Vector-MLP-L6
    print("  Training Vector-MLP-L6 (random)...")
    Y_pred_l6, n_iter = train_vector_mlp(X_train, Y_train_l6, X_test, seed=seed)
    results['Vector-MLP-L6'] = evaluate_vector_selection(
        test_samples, Y_pred_l6, Y_test, 'Vector-MLP-L6'
    )

    # References
    def get_delta_idx(delta_val):
        return DELTA_GRID.index(float(delta_val))

    ref_fns = {
        'Default': lambda r: get_delta_idx(refs['default_delta']),
        'L1': lambda r: get_delta_idx(refs['l1_delta']),
        'L2': lambda r: get_delta_idx(refs['l2_table'][int(r['n'])]['delta_star']),
        'L6-hindsight': None,
    }
    for ref_name, ref_fn in ref_fns.items():
        if ref_fn is not None:
            results[ref_name] = evaluate_reference_selection(
                test_samples, Y_test, ref_name, ref_fn
            )
    results['L6-hindsight'] = evaluate_l6_hindsight(test_samples, Y_test)

    return results


def decide_acceptance(combo_pooled, random_results=None):
    """Decide APPROVE/REVISE/BLOCK based on combo holdout results."""
    by_model = {r['model']: r for r in combo_pooled}
    l2 = by_model.get('L2')
    if l2 is None:
        return 'BLOCK', ['Missing pooled L2 baseline in combo holdout results.']

    candidates = {m: by_model[m] for m in ('Vector-MLP-L6', 'Vector-MLP-L5', 'Vector-MLP-L4')
                  if m in by_model}
    if not candidates:
        return 'BLOCK', ['Missing Vector-MLP pooled combo holdout results.']

    best_name = min(candidates, key=lambda m: candidates[m]['J1'])
    best = candidates[best_name]
    improvement = l2['J1'] - best['J1']
    tab = by_model.get('Tabular-L6')
    tab_gap = (tab['J1'] - best['J1']) if tab else None
    clear_threshold = max(0.005, 0.01 * l2['J1'])

    reasons = [
        f"Best vector candidate is {best_name} with J1={best['J1']:.6f}; "
        f"L2 J1={l2['J1']:.6f}; improvement={improvement:.6f}."
    ]
    if tab:
        reasons.append(f"Tabular-L6 J1={tab['J1']:.6f}; gap to best vector={tab_gap:.6f}.")

    # Check failure rate
    if best['failure_rate'] > l2['failure_rate'] + 0.01:
        reasons.append(
            f"{best_name} failure rate {best['failure_rate']:.4f} exceeds "
            f"L2 {l2['failure_rate']:.4f} by more than 0.01."
        )
        return 'BLOCK', reasons

    # Check per-n degradation
    degraded_n = []
    for n_val, l2_info in l2.get('per_n', {}).items():
        best_info = best.get('per_n', {}).get(n_val)
        if not best_info:
            continue
        if best_info['J1'] > l2_info['J1'] * 1.10 and best_info['J1'] - l2_info['J1'] > 0.02:
            degraded_n.append((n_val, l2_info['J1'], best_info['J1']))
    if degraded_n:
        detail = ', '.join(
            f"n={n}: L2={l2_j1:.6f}, {best_name}={best_j1:.6f}"
            for n, l2_j1, best_j1 in degraded_n
        )
        reasons.append(f"Catastrophic per-n degradation: {detail}.")
        return 'BLOCK', reasons

    # Check improvement
    if improvement >= clear_threshold:
        reasons.append('Combo holdout shows clear pooled J1 improvement over L2.')

        # Check strong NN signal
        if tab and best['J1'] <= tab['J1'] + 0.01:
            reasons.append('Strong NN signal: Vector-MLP is within 0.01 J1 of or better than Tabular-L6.')

        return 'APPROVE', reasons

    if improvement > 0:
        reasons.append('Combo holdout improves over L2, but below clear-improvement threshold.')
        return 'REVISE', reasons

    reasons.append('Vector MLP does not improve over L2 in combo holdout.')
    return 'BLOCK', reasons


# ============================================================
# Plot generation
# ============================================================

def plot_model_j1_comparison(model_rows, output_dir=PLOTS_DIR):
    """Plot all pooled combo-holdout methods ordered by ascending J1."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    matplotlib.rcParams.update({
        'font.family': 'sans-serif',
        'font.sans-serif': ['Arial', 'Helvetica', 'DejaVu Sans', 'sans-serif'],
        'svg.fonttype': 'none',
        'pdf.fonttype': 42,
    })

    os.makedirs(output_dir, exist_ok=True)

    allowed_models = {
        'Default', 'L1', 'L2',
        'Vector-MLP-L4', 'Vector-MLP-L5', 'Vector-MLP-L6',
        'Tabular-L6',
        'L3-oracle', 'L4-oracle', 'L5-oracle', 'L6-hindsight'
    }
    by_model = {
        row['model']: row
        for row in model_rows
        if row['model'] in allowed_models
    }
    models_present = sorted(by_model, key=lambda model: float(by_model[model]['J1']))
    j1_vals = [float(by_model[model]['J1']) for model in models_present]

    def model_color(model):
        if 'Vector' in model:
            return '#E69F00'
        if model == 'Tabular-L6':
            return '#56B4E9'
        if 'oracle' in model or 'hindsight' in model:
            return '#009E73'
        return '#999999'

    colors = [model_color(model) for model in models_present]

    fig, ax = plt.subplots(figsize=(10, 6))
    bars = ax.barh(range(len(models_present)), j1_vals, color=colors)
    ax.set_yticks(range(len(models_present)))
    ax.set_yticklabels(models_present)
    ax.set_xlabel(r'Pooled $J_1$ (lower is better)')
    ax.set_title(r'E3b full-combination holdout: pooled $J_1$')
    ax.invert_yaxis()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.grid(axis='x', color='#D9D9D9', linewidth=0.6, alpha=0.7)
    ax.set_axisbelow(True)
    ax.set_xlim(0, max(j1_vals) + 0.045)

    for bar, value in zip(bars, j1_vals):
        ax.text(
            value + 0.003,
            bar.get_y() + bar.get_height() / 2,
            f'{value:.4f}',
            va='center',
            fontsize=8,
        )

    fig.tight_layout()
    output_base = os.path.join(output_dir, 'model_j1_comparison')
    fig.savefig(f'{output_base}.png', dpi=300, bbox_inches='tight')
    fig.savefig(f'{output_base}.svg', bbox_inches='tight')
    fig.savefig(f'{output_base}.pdf', bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved plots/model_j1_comparison.{{png,svg,pdf}}")


def generate_plots(combo_pooled, seed_results, ablation_results,
                   endpoint_rows, near_opt_summaries):
    """Generate basic diagnostic PNGs for decision-making."""
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt

    os.makedirs(PLOTS_DIR, exist_ok=True)

    by_model = {r['model']: r for r in combo_pooled}

    # Plot 1: Model J1 comparison
    plot_model_j1_comparison(combo_pooled)

    # Plot 2: Delta distribution comparison
    fig, axes = plt.subplots(1, 3, figsize=(15, 5), sharey=True)
    for ax, n_val in zip(axes, N_GRID):
        for m in ['Vector-MLP-L6', 'Tabular-L6', 'L2']:
            if m not in by_model:
                continue
            df_sel = by_model[m]['df_sel']
            sub = df_sel[df_sel['n'] == n_val]
            if len(sub) == 0:
                continue
            dist = sub['selected_delta'].value_counts().sort_index()
            ax.bar(dist.index + (0.005 if 'Vector' in m else (-0.005 if m == 'L2' else 0)),
                   dist.values / dist.sum(), width=0.008,
                   alpha=0.7, label=m)
        ax.set_xlabel('Selected delta')
        ax.set_title(f'n={n_val}')
        ax.legend(fontsize=7)
    axes[0].set_ylabel('Fraction')
    plt.suptitle('E3b Delta Distribution by n (Combo Holdout Pooled)')
    plt.tight_layout()
    plt.savefig(os.path.join(PLOTS_DIR, 'delta_distribution_comparison.png'), dpi=150)
    plt.close()
    print(f"  Saved plots/delta_distribution_comparison.png")

    # Plot 3: Endpoint rate by n
    if endpoint_rows:
        df_ep = pd.DataFrame(endpoint_rows)
        df_ep_n = df_ep[df_ep['category'].str.startswith('n=')]
        if len(df_ep_n) > 0:
            fig, ax = plt.subplots(figsize=(8, 5))
            for m in df_ep_n['model'].unique():
                sub = df_ep_n[df_ep_n['model'] == m].sort_values('category')
                ax.plot(sub['category'], sub['P_extreme'], 'o-', label=m, markersize=4)
            ax.set_ylabel('P(extreme delta)')
            ax.set_title('E3b Endpoint Rate by n')
            ax.legend(fontsize=7)
            plt.tight_layout()
            plt.savefig(os.path.join(PLOTS_DIR, 'endpoint_rate_by_n.png'), dpi=150)
            plt.close()
            print(f"  Saved plots/endpoint_rate_by_n.png")

    # Plot 4: Near-optimal / regret summary
    if near_opt_summaries:
        fig, ax = plt.subplots(figsize=(8, 5))
        models = list(near_opt_summaries.keys())
        for eps in NEAR_OPTIMAL_EPS:
            rates = [near_opt_summaries[m].get(f'near_{eps}_rate', 0) for m in models]
            ax.bar([f'{m}\neps={eps}' for m in models], rates, alpha=0.7)
        ax.set_ylabel('Near-optimal hit rate')
        ax.set_title('E3b Near-Optimal Hit Rates')
        plt.xticks(rotation=45, ha='right', fontsize=7)
        plt.tight_layout()
        plt.savefig(os.path.join(PLOTS_DIR, 'near_optimal_summary.png'), dpi=150)
        plt.close()
        print(f"  Saved plots/near_optimal_summary.png")

    # Plot 5: Seed stability
    if seed_results:
        df_seed = pd.DataFrame(seed_results)
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))
        axes[0].bar(range(len(df_seed)), df_seed['pooled_J1'], color='#E69F00')
        axes[0].set_xticks(range(len(df_seed)))
        axes[0].set_xticklabels([f'seed={s}' for s in df_seed['seed']])
        axes[0].set_ylabel('Pooled J1')
        axes[0].set_title('E3b Vector-MLP-L6 Seed Stability (5-fold J1)')
        for i, v in enumerate(df_seed['pooled_J1']):
            axes[0].text(i, v + 0.001, f'{v:.4f}', ha='center', fontsize=8)

        axes[1].bar(range(len(df_seed)), df_seed['endpoint_rate'], color='#D55E00')
        axes[1].set_xticks(range(len(df_seed)))
        axes[1].set_xticklabels([f'seed={s}' for s in df_seed['seed']])
        axes[1].set_ylabel('Endpoint rate')
        axes[1].set_title('E3b Vector-MLP-L6 Seed Stability (Endpoint)')
        plt.tight_layout()
        plt.savefig(os.path.join(PLOTS_DIR, 'seed_stability.png'), dpi=150)
        plt.close()
        print(f"  Saved plots/seed_stability.png")

    # Plot 6: Feature ablation
    if ablation_results:
        df_abl = pd.DataFrame(ablation_results)
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.barh(df_abl['feature_group'], df_abl['pooled_J1'], color='#0072B2')
        ax.set_xlabel('Pooled J1')
        ax.set_title('E3b Feature Ablation (Vector-MLP-L6, fold 1)')
        ax.invert_yaxis()
        for i, v in enumerate(df_abl['pooled_J1']):
            ax.text(v + 0.002, i, f'{v:.4f}', va='center', fontsize=8)
        plt.tight_layout()
        plt.savefig(os.path.join(PLOTS_DIR, 'feature_ablation.png'), dpi=150)
        plt.close()
        print(f"  Saved plots/feature_ablation.png")


# ============================================================
# Artifact saving
# ============================================================

def get_git_metadata():
    try:
        commit = subprocess.check_output(
            ['git', 'rev-parse', '--short', 'HEAD'],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode().strip()
    except Exception:
        commit = 'unknown'
    try:
        status = subprocess.check_output(
            ['git', 'status', '--short'],
            cwd=PROJECT_ROOT,
            stderr=subprocess.DEVNULL,
        ).decode(errors='replace').strip()
    except Exception:
        status = ''
    return {
        'git_commit': commit,
        'workspace_dirty': bool(status),
        'git_status_short': status.splitlines(),
    }


def save_artifacts(
    combo_pooled, random_results, all_fold_results, refs,
    seed_results, ablation_results, endpoint_rows, near_opt_summaries,
    near_opt_details, data_integrity, sample_reconstruction,
    decision, decision_reasons, timing_info, n_iter_info,
):
    """Save all E3b experiment artifacts."""
    os.makedirs(E3B_OUTPUT_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)

    # --- model_comparison.csv ---
    rows = []
    for r in combo_pooled:
        row = {
            'model': r['model'], 'split': r['split'],
            'J1': r['J1'], 'failure_rate': r['failure_rate'],
            'n_samples': r['n_samples'],
        }
        for n_val, n_info in r.get('per_n', {}).items():
            row[f'J1_n{n_val}'] = n_info['J1']
            row[f'fail_n{n_val}'] = n_info['failure_rate']
        rows.append(row)
    # Add random split results
    for model_name, r in random_results.items():
        row = {
            'model': model_name, 'split': 'random',
            'J1': r['J1'], 'failure_rate': r['failure_rate'],
            'n_samples': r['n_samples'],
        }
        for n_val, n_info in r.get('per_n', {}).items():
            row[f'J1_n{n_val}'] = n_info['J1']
        rows.append(row)
    pd.DataFrame(rows).to_csv(os.path.join(E3B_OUTPUT_DIR, 'model_comparison.csv'), index=False)
    print(f"  Saved model_comparison.csv")

    # --- split_report.csv ---
    split_info = build_split_rows()
    pd.DataFrame(split_info).to_csv(os.path.join(E3B_OUTPUT_DIR, 'split_report.csv'), index=False)
    print(f"  Saved split_report.csv")

    # --- vector_mlp_results.csv (per-sample combo holdout Vector-MLP-L6 selections) ---
    vm_rows = []
    for r in combo_pooled:
        if 'Vector-MLP' in r['model'] or r['model'] == 'Tabular-L6':
            for _, row in r['df_sel'].iterrows():
                vm_rows.append({
                    'model': row['model'],
                    'beta': row['beta'],
                    'gamma_over_eta': row['gamma_over_eta'],
                    'n': row['n'],
                    'repeat_id': row['repeat_id'],
                    'selected_delta': row['selected_delta'],
                    'true_loss': row['true_loss'],
                    'is_valid': row['is_valid'],
                })
    df_vm = pd.DataFrame(vm_rows)
    df_vm.to_csv(os.path.join(E3B_OUTPUT_DIR, 'vector_mlp_results.csv'), index=False)
    print(f"  Saved vector_mlp_results.csv")

    # --- tabular_l6_results.csv ---
    tab_rows = []
    for r in combo_pooled:
        if r['model'] == 'Tabular-L6':
            for _, row in r['df_sel'].iterrows():
                tab_rows.append({
                    'beta': row['beta'], 'gamma_over_eta': row['gamma_over_eta'],
                    'n': row['n'], 'repeat_id': row['repeat_id'],
                    'selected_delta': row['selected_delta'],
                    'true_loss': row['true_loss'], 'is_valid': row['is_valid'],
                })
    pd.DataFrame(tab_rows).to_csv(os.path.join(E3B_OUTPUT_DIR, 'tabular_l6_results.csv'), index=False)
    print(f"  Saved tabular_l6_results.csv")

    # --- sample_features.csv (cache: per-sample features, may contain true params as keys) ---
    # Aggregate from ALL folds' test samples. Each fold holds out 9 unique combos;
    # 5 folds × 9 combos × 1000 repeats = 45000 unique samples (full coverage).
    # NOTE: SAMPLE_KEYS and SAMPLE_FEATURE_COLS both contain 'n'; deduplicate columns
    # to avoid duplicate header entries that break CSV parsers (e.g. PowerShell Import-Csv).
    if all_fold_results:
        sf_cols = SAMPLE_KEYS + [c for c in SAMPLE_FEATURE_COLS if c not in SAMPLE_KEYS]
        sf_dfs = []
        for fold_result in all_fold_results:
            sf_dfs.append(fold_result['_test_samples'][sf_cols].copy())
        cache_df = pd.concat(sf_dfs, ignore_index=True).drop_duplicates(subset=SAMPLE_KEYS)
        cache_df.to_csv(os.path.join(E3B_OUTPUT_DIR, 'sample_features.csv'), index=False)
        print(f"  Saved sample_features.csv ({len(cache_df)} unique samples from all folds)")

    # --- risk_curves.csv (cache: per-sample true risk curves, 26-dim) ---
    if all_fold_results:
        rc_rows = []
        for fold_result in all_fold_results:
            test_samples = fold_result['_test_samples']
            Y_test = fold_result['_Y_test']
            for i in range(len(test_samples)):
                row = test_samples.iloc[i]
                rc_row = {
                    'beta': float(row['beta']),
                    'gamma_over_eta': float(row['gamma_over_eta']),
                    'n': int(row['n']),
                    'repeat_id': int(row['repeat_id']),
                }
                for j, d in enumerate(DELTA_GRID):
                    rc_row[f'loss_d{d}'] = float(Y_test[i, j])
                rc_rows.append(rc_row)
        pd.DataFrame(rc_rows).to_csv(os.path.join(E3B_OUTPUT_DIR, 'risk_curves.csv'), index=False)
        print(f"  Saved risk_curves.csv ({len(rc_rows)} samples × 26 deltas)")

    # --- endpoint_diagnostics.csv ---
    if endpoint_rows:
        pd.DataFrame(endpoint_rows).to_csv(
            os.path.join(E3B_OUTPUT_DIR, 'endpoint_diagnostics.csv'), index=False
        )
        print(f"  Saved endpoint_diagnostics.csv")

    # --- near_optimal_diagnostics.csv ---
    if near_opt_details:
        all_no = []
        for df_no in near_opt_details.values():
            all_no.append(df_no)
        pd.concat(all_no, ignore_index=True).to_csv(
            os.path.join(E3B_OUTPUT_DIR, 'near_optimal_diagnostics.csv'), index=False
        )
        print(f"  Saved near_optimal_diagnostics.csv")

    # --- feature_ablation.csv ---
    if ablation_results:
        pd.DataFrame(ablation_results).to_csv(
            os.path.join(E3B_OUTPUT_DIR, 'feature_ablation.csv'), index=False
        )
        print(f"  Saved feature_ablation.csv")

    # --- seed_stability.csv ---
    if seed_results:
        pd.DataFrame(seed_results).to_csv(
            os.path.join(E3B_OUTPUT_DIR, 'seed_stability.csv'), index=False
        )
        print(f"  Saved seed_stability.csv")

    # --- summary.json ---
    summary = {
        'experiment': 'E3b',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'description': 'Vector-output heavy MLP experiment and diagnostics',
        'vector_mlp_config': {
            'hidden_layer_sizes': list(MLP_HIDDEN_LAYERS),
            'max_iter': MLP_MAX_ITER,
            'batch_size': MLP_BATCH_SIZE,
            'alpha': MLP_ALPHA,
            'learning_rate_init': MLP_LR,
            'early_stopping': True,
            'validation_fraction': MLP_VALIDATION_FRACTION,
            'n_iter_no_change': MLP_N_ITER_NO_CHANGE,
        },
        'feature_contract': {
            'vector_input': SAMPLE_FEATURE_COLS,
            'no_delta_input_for_vector': True,
            'zscore_applied': FEATURE_COLS_ZSCORE,
            'zscore_source': 'training_set_only',
            'raw_passthrough': FEATURE_COLS_RAW,
        },
        'target_scaling': 'StandardScaler on 26-dim targets, train-fold-only',
        'training_data': 'full fold (no sample cap)',
        'combo_holdout_pooled': [
            {
                'model': r['model'], 'J1': r['J1'],
                'failure_rate': r['failure_rate'],
                'per_n': {str(k): v for k, v in r.get('per_n', {}).items()},
            }
            for r in combo_pooled
        ],
        'random_split': [
            {'model': m, 'J1': r['J1'], 'failure_rate': r['failure_rate']}
            for m, r in random_results.items()
        ],
        'timing': timing_info,
        'n_iters': n_iter_info,
        'near_optimal_summaries': near_opt_summaries,
    }
    with open(os.path.join(E3B_OUTPUT_DIR, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved summary.json")

    # --- acceptance report ---
    write_acceptance_report(
        combo_pooled, random_results, split_info,
        data_integrity, decision, decision_reasons,
        seed_results, ablation_results, endpoint_rows, near_opt_summaries,
    )

    # --- manifest.json ---
    git_meta = get_git_metadata()
    manifest_out = {
        'run_id': 'E3b_vector_mlp_v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'code_entry': 'code/run_E3b_vector_mlp.py',
        **git_meta,
        'python_version': sys.version.split()[0],
        'data_source': {
            'mc_scan': 'artifacts/formal/shared_data/mc_scan_raw.csv',
            'mc_manifest': 'artifacts/formal/shared_data/manifest.json',
        },
        'sample_reconstruction': {
            'function': 'generate_sample(beta, eta, gamma, n, repeat_id, seed)',
            'seed_namespace': SEED_NAMESPACE,
            'verification': sample_reconstruction,
        },
        'feature_contract': {
            'vector_input': SAMPLE_FEATURE_COLS,
            'zscore_applied': FEATURE_COLS_ZSCORE,
            'zscore_source': 'training_set_only',
            'raw_passthrough': FEATURE_COLS_RAW,
            'no_delta_in_vector_input': True,
        },
        'label_contract': {
            'base': '((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2',
            'failure_penalty': 'p99(valid_training_loss)',
            'no_regret': True,
            'no_log_transform': True,
            'vector_target': '26-dim raw loss curve per sample',
            'target_scaling': 'StandardScaler, train-fold-only',
        },
        'split_contract': {
            'random_split': '80/20 sanity check, seed=42',
            'combo_holdout': 'deterministic 5-fold full-combo holdout; same as E3a',
        },
        'training_contract': {
            'full_fold': True,
            'no_sample_cap': True,
            'note': 'All training samples used for vector MLP; scalers/failure_penalty/L4L5 from train fold only.',
        },
        'models': {
            'Vector-MLP-L4': f'sklearn MLPRegressor{MLP_HIDDEN_LAYERS}, max_iter={MLP_MAX_ITER}, ReLU/Adam; target: train-only mean loss per (beta,n,delta)',
            'Vector-MLP-L5': f'sklearn MLPRegressor{MLP_HIDDEN_LAYERS}, max_iter={MLP_MAX_ITER}, ReLU/Adam; target: train-only mean loss per (beta,gamma/eta,n,delta)',
            'Vector-MLP-L6': f'sklearn MLPRegressor{MLP_HIDDEN_LAYERS}, max_iter={MLP_MAX_ITER}, ReLU/Adam; target: per-sample 26-dim loss curve',
            'Tabular-L6': 'HistGradientBoostingRegressor(200), scalar form, supervised by per-sample loss_i(delta)',
        },
        'evaluation': {
            'objective': 'selection_quality (argmin_delta predicted_loss -> true selected J1)',
            'metric': 'J1 = sqrt(mean_i(true_loss_i(delta_hat_i)))',
        },
        'diagnostics': {
            'endpoint': 'P(delta=0), P(delta=0.5), P(extreme) by n and combo',
            'near_optimal': 'regret, rel_regret, near hit rate for eps=1%/2%/5%',
            'feature_ablation': 'full/n_only/scale_quantile/shape, fold 1 seed 42',
            'seed_stability': 'seeds 42/2026/3407, ALL 5 folds pooled',
        },
        'output_files': [
            'manifest.json', 'summary.json', 'model_comparison.csv',
            'vector_mlp_results.csv', 'tabular_l6_results.csv',
            'split_report.csv', 'endpoint_diagnostics.csv',
            'near_optimal_diagnostics.csv', 'feature_ablation.csv',
            'seed_stability.csv', 'E3b_acceptance_report.md',
            'sample_features.csv', 'risk_curves.csv',
            'plots/*.png',
        ],
        'notes': 'E3b: standalone vector-output heavy MLP. No E3a modification. No MDM reruns. No manuscript conclusions.',
    }
    with open(os.path.join(E3B_OUTPUT_DIR, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest_out, f, indent=2, ensure_ascii=False)
    print(f"  Saved manifest.json")


def write_acceptance_report(
    combo_pooled, random_results, split_rows,
    data_integrity, decision, decision_reasons,
    seed_results, ablation_results, endpoint_rows, near_opt_summaries,
):
    """Write E3b_acceptance_report.md."""
    report_path = os.path.join(E3B_OUTPUT_DIR, 'E3b_acceptance_report.md')

    def fmt(v):
        if v is None:
            return ''
        if isinstance(v, float):
            return f"{v:.6f}"
        return str(v)

    def result_table(results):
        lines = [
            "| model | J1 | failure_rate | n_samples | J1_n7 | J1_n10 | J1_n20 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for r in sorted(results, key=lambda x: x['J1']):
            per_n = r.get('per_n', {})
            lines.append(
                "| {model} | {J1} | {fr} | {ns} | {n7} | {n10} | {n20} |".format(
                    model=r['model'],
                    J1=fmt(r['J1']),
                    fr=fmt(r['failure_rate']),
                    ns=r['n_samples'],
                    n7=fmt(per_n.get(7, {}).get('J1')),
                    n10=fmt(per_n.get(10, {}).get('J1')),
                    n20=fmt(per_n.get(20, {}).get('J1')),
                )
            )
        return "\n".join(lines)

    random_list = list(random_results.values())

    integrity_lines = [
        f"- expected_rows: {data_integrity.get('expected_rows')}",
        f"- actual_rows: {data_integrity.get('actual_rows')}",
        f"- duplicate_rows: {data_integrity.get('duplicate_rows')}",
        f"- unique_combos: {data_integrity.get('unique_combos')}",
        f"- delta_points: {data_integrity.get('delta_points')}",
        f"- repeat_min/repeat_max: {data_integrity.get('repeat_min')}/{data_integrity.get('repeat_max')}",
        f"- non_success_rate: {fmt(data_integrity.get('non_success_rate'))}",
    ]

    split_preview = split_rows[:10]
    split_lines = [
        "| fold | test_beta | test_gamma_over_eta | test_n |",
        "|---|---:|---:|---:|",
    ]
    for row in split_preview:
        split_lines.append(
            f"| {row.get('fold')} | {row.get('test_beta')} | "
            f"{row.get('test_gamma_over_eta', '')} | {row.get('test_n', '')} |"
        )

    # Endpoint table
    endpoint_lines = ["| model | category | P_delta_0 | P_delta_0.5 | P_extreme |",
                      "|---|---|---:|---:|---:|"]
    if endpoint_rows:
        df_ep = pd.DataFrame(endpoint_rows)
        for _, r in df_ep[df_ep['category'] == 'pooled'].iterrows():
            endpoint_lines.append(
                f"| {r['model']} | {r['category']} | "
                f"{r['P_delta_0']:.4f} | {r['P_delta_0.5']:.4f} | {r['P_extreme']:.4f} |"
            )

    # Seed stability table
    seed_lines = ["| seed | pooled_J1 | J1_n7 | J1_n10 | J1_n20 | endpoint_rate |",
                  "|---:|---:|---:|---:|---:|---:|"]
    if seed_results:
        for r in seed_results:
            seed_lines.append(
                f"| {r['seed']} | {r['pooled_J1']:.6f} | "
                f"{r.get('J1_n7', 0):.6f} | {r.get('J1_n10', 0):.6f} | "
                f"{r.get('J1_n20', 0):.6f} | {r['endpoint_rate']:.4f} |"
            )

    # Feature ablation table
    abl_lines = ["| group | n_features | pooled_J1 | endpoint_rate | near_5pct |",
                 "|---|---:|---:|---:|---:|"]
    if ablation_results:
        for r in ablation_results:
            abl_lines.append(
                f"| {r['feature_group']} | {r['n_features']} | "
                f"{r['pooled_J1']:.6f} | {r['endpoint_rate']:.4f} | "
                f"{r.get('near_5pct_rate', 0):.4f} |"
            )

    # Near-optimal summary
    near_lines = ["| model | mean_regret | mean_rel_regret | near_1% | near_2% | near_5% |",
                  "|---|---:|---:|---:|---:|---:|"]
    for m, s in near_opt_summaries.items():
        near_lines.append(
            f"| {m} | {s['mean_regret']:.6f} | {s['mean_rel_regret']:.6f} | "
            f"{s.get('near_0.01_rate', 0):.4f} | {s.get('near_0.02_rate', 0):.4f} | "
            f"{s.get('near_0.05_rate', 0):.4f} |"
        )

    text = "\n".join([
        "# E3b Acceptance Report",
        "",
        "## Verdict",
        "",
        f"**{decision}**",
        "",
        *[f"- {reason}" for reason in decision_reasons],
        "",
        "## Data Integrity",
        "",
        *integrity_lines,
        "",
        "## Combo Holdout Pooled",
        "",
        result_table(combo_pooled),
        "",
        "## Random Split (Sanity Check)",
        "",
        result_table(random_list) if random_list else "_Not recorded._",
        "",
        "## Split Preview",
        "",
        "\n".join(split_lines),
        "",
        f"_Split rows recorded: {len(split_rows)}._",
        "",
        "## Endpoint Diagnostics (Pooled)",
        "",
        "\n".join(endpoint_lines),
        "",
        "## Seed Stability (Vector-MLP-L6, 5-fold combo holdout pooled)",
        "",
        "\n".join(seed_lines),
        "",
        "## Feature Ablation (Vector-MLP-L6, fold 1, seed 42)",
        "",
        "\n".join(abl_lines),
        "",
        "## Near-Optimal / Regret Summary (Combo Holdout Pooled)",
        "",
        "\n".join(near_lines),
        "",
    ])

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(text)
    print(f"  Saved E3b_acceptance_report.md")
    return report_path


# ============================================================
# Main entry point
# ============================================================

def run_experiment():
    os.makedirs(E3B_OUTPUT_DIR, exist_ok=True)
    os.makedirs(PLOTS_DIR, exist_ok=True)

    print("=" * 70)
    print("Study/01 Formal E3b: Vector-Output Heavy MLP Experiment")
    print("=" * 70)

    # 1. Load data
    print("\n[1/8] Loading MC scan data...")
    df_mc = pd.read_csv(MC_SCAN_PATH)
    with open(MC_MANIFEST_PATH, encoding='utf-8') as f:
        manifest = json.load(f)
    print(f"  Loaded {len(df_mc)} rows from mc_scan_raw.csv")

    # 2. Data integrity
    print("\n[2/8] Verifying data integrity...")
    data_integrity = verify_data_integrity(df_mc, manifest)
    sample_reconstruction = verify_sample_reconstruction(manifest)
    print(f"  Sample probe SHA256: {sample_reconstruction['sample_sha256_rounded_12'][:12]}...")

    # 3. Build features
    print("\n[3/8] Building feature table...")
    df_full = build_feature_table(df_mc, manifest)

    # 4. Compute per-sample loss
    print("\n[4/8] Computing per-sample loss labels...")
    df_full = compute_per_sample_loss(df_full)
    nan_count = df_full['loss'].isna().sum()
    print(f"  NaN/invalid losses: {nan_count} ({nan_count/len(df_full)*100:.2f}%)")

    # 5. Compute oracle references
    print("\n[5/8] Computing oracle references...")
    refs = compute_reference_deltas(df_full)
    print(f"  L1 delta* = {refs['l1_delta']}")
    print(f"  L2 table: {refs['l2_table']}")

    # Verify no banned fields in feature contract
    verify_no_banned_fields(SAMPLE_FEATURE_COLS)
    print("  Banned field check: PASSED")

    # 6. Combo holdout (main judgment)
    print("\n[6/8] Combo holdout (main judgment)...")
    combo_folds = get_combo_split()
    all_fold_results = []
    all_timing = {}
    all_n_iters = {}

    for fold_idx, fold in enumerate(combo_folds):
        print(f"\n  === {fold['fold_name']} ===")
        print(f"  Train combos: {len(fold['train_combos'])}, "
              f"Test combos: {len(fold['test_combos'])}")
        fold_result = run_combo_fold(df_full, fold, refs, seed=42)
        import gc; gc.collect()
        all_fold_results.append(fold_result)
        # Accumulate timing
        for k, v in fold_result.get('_timing', {}).items():
            all_timing.setdefault(k, []).append(v)
        for k, v in fold_result.get('_n_iters', {}).items():
            all_n_iters.setdefault(k, []).append(v)

    # Pool combo holdout results
    print("\n  Pooling combo holdout across folds...")
    combo_pooled = pool_combo_results(all_fold_results)

    # 7. Diagnostics
    print("\n[7/8] Running diagnostics...")

    # Build true loss map for near-optimal
    by_model = {r['model']: r for r in combo_pooled}
    # Build a Y_true_loss map from fold results
    true_loss_map = {}
    for fold_result in all_fold_results:
        test_samples = fold_result['_test_samples']
        Y_test = fold_result['_Y_test']
        for i in range(len(test_samples)):
            row = test_samples.iloc[i]
            key = (float(row['beta']), float(row['gamma_over_eta']),
                   int(row['n']), int(row['repeat_id']))
            true_loss_map[key] = Y_test[i]

    # Endpoint diagnostics
    endpoint_models = ['Vector-MLP-L6', 'Vector-MLP-L5', 'Vector-MLP-L4', 'Tabular-L6', 'L2', 'L6-hindsight']
    endpoint_rows = []
    for m in endpoint_models:
        if m in by_model:
            endpoint_rows.extend(compute_endpoint_diagnostics(by_model[m]['df_sel'], m))

    # Near-optimal diagnostics
    near_opt_models = ['Vector-MLP-L6', 'Tabular-L6', 'L2']
    near_opt_details = {}
    near_opt_summaries = {}
    for m in near_opt_models:
        if m in by_model:
            df_no, summary = compute_near_optimal_diagnostics(
                by_model[m]['df_sel'], true_loss_map, m
            )
            near_opt_details[m] = df_no
            near_opt_summaries[m] = summary

    # Feature ablation (fold 1 only, seed 42)
    print("\n  Feature ablation (fold 1)...")
    ablation_results = run_feature_ablation(
        all_fold_results[0]['_fold_prep'],
        all_fold_results[0]['_df_train_long'],
        all_fold_results[0]['_df_test_long'],
        seed=42
    )

    # Seed stability (ALL 5 folds, 3 seeds — supports APPROVE criterion)
    print("\n  Seed stability (5-fold combo holdout, 3 seeds)...")
    seed_results = run_seed_stability(
        all_fold_results, df_full, refs,
    )

    # Free fold-internal large objects (no longer needed after seed_stability)
    for fr in all_fold_results:
        fr.pop('_fold_prep', None)
        fr.pop('_df_train_long', None)
        fr.pop('_df_test_long', None)
    import gc; gc.collect()

    # Random split sanity check
    print("\n  Random split sanity check...")
    random_results = run_random_split_sanity(df_full, refs, seed=42)

    # Generate plots
    print("\n  Generating diagnostic plots...")
    generate_plots(combo_pooled, seed_results, ablation_results,
                   endpoint_rows, near_opt_summaries)

    # Decision
    decision, decision_reasons = decide_acceptance(combo_pooled, random_results)

    # Aggregate timing
    timing_info = {k: {'mean_s': float(np.mean(v)), 'total_s': float(np.sum(v))}
                   for k, v in all_timing.items()}
    n_iter_info = {k: {'mean': float(np.mean(v)), 'min': int(np.min(v)), 'max': int(np.max(v))}
                   for k, v in all_n_iters.items()}

    # 8. Save artifacts
    print("\n[8/8] Saving artifacts...")
    save_artifacts(
        combo_pooled, random_results, all_fold_results, refs,
        seed_results, ablation_results, endpoint_rows, near_opt_summaries,
        near_opt_details, data_integrity, sample_reconstruction,
        decision, decision_reasons, timing_info, n_iter_info,
    )

    return combo_pooled, random_results, decision, decision_reasons


if __name__ == '__main__':
    combo_pooled, random_results, decision, decision_reasons = run_experiment()

    print("\n" + "=" * 70)
    print("RESULTS SUMMARY — Combo Holdout (Pooled)")
    print("=" * 70)
    print(f"{'Model':<18} {'J1':>8} {'Fail%':>7} {'J1(n=7)':>8} {'J1(n=10)':>8} {'J1(n=20)':>8}")
    print("-" * 70)
    for r in sorted(combo_pooled, key=lambda x: x['J1']):
        per_n = r.get('per_n', {})
        j1_7 = per_n.get(7, {}).get('J1', float('nan'))
        j1_10 = per_n.get(10, {}).get('J1', float('nan'))
        j1_20 = per_n.get(20, {}).get('J1', float('nan'))
        print(f"{r['model']:<18} {r['J1']:>8.4f} {r['failure_rate']*100:>6.2f}% "
              f"{j1_7:>8.4f} {j1_10:>8.4f} {j1_20:>8.4f}")

    print(f"\nDecision: {decision}")
    for reason in decision_reasons:
        print(f"  - {reason}")
