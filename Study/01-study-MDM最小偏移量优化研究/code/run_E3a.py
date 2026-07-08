"""
Study/01 Formal E3a: Existing-Grid Risk-Curve Learning Pilot

Experiment design:
  - Reconstruct formal MC samples from manifest seed scheme
  - Compute observable sample-statistic features (no true parameters)
  - For each (sample, candidate delta), predict the per-sample loss
  - Select delta_hat = argmin_delta predicted_loss
  - Evaluate true selected J1 vs Default/L1/L2/oracle references

Models:
  - NN-RC-L4: supervised by train-only mean loss per (beta, n, delta)
  - NN-RC-L5: supervised by train-only mean loss per (beta, gamma/eta, n, delta)
  - NN-RC-L6: supervised by per-sample loss_i(delta)
  - Tabular baseline: HistGradientBoostingRegressor (sanity check)

Splits:
  - random_sample_split: 80/20 sanity check
  - combo_holdout: leave out entire (beta, gamma/eta, n) combos — main judgment

Plan reference: coworker/plans/2026-07-08-study01-e3a-risk-curve-pilot.md
"""

import sys
import os
import json
import time
import math
import subprocess
from datetime import datetime, timezone
from itertools import product

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

# Output directory
E3_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "E3_sample_adaptive")

# MC scan data
MC_SCAN_PATH = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")

# Feature columns (plan contract)
FEATURE_COLS_ZSCORE = [
    'x_min', 'x_max', 'range', 'Q1', 'Med', 'Q3', 'IQR', 'x_bar', 's'
]
FEATURE_COLS_RAW = ['n', 'CV', 'g1', 'g2', 'delta']
ALL_FEATURE_COLS = FEATURE_COLS_ZSCORE + FEATURE_COLS_RAW
SAMPLE_KEYS = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
MAX_TRAIN_SAMPLES_PER_FOLD = 12000
MLP_HIDDEN_LAYERS = (32, 16)
MLP_MAX_ITER = 40
MLP_BATCH_SIZE = 4096


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

    # Check duplicates
    dup_key = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id', 'delta']
    dups = df.duplicated(subset=dup_key).sum()
    print(f"[Data Integrity] Duplicate rows: {dups}")
    assert dups == 0, f"Found {dups} duplicate rows"

    # Check all combos present
    unique_combos = df[['beta', 'eta', 'gamma_over_eta', 'n']].drop_duplicates()
    print(f"[Data Integrity] Unique (beta, gamma/eta, n) combos: {len(unique_combos)}")
    assert len(unique_combos) == expected_combos, \
        f"Expected {expected_combos} combos, got {len(unique_combos)}"

    # Check delta values
    unique_deltas = sorted(df['delta'].unique())
    print(f"[Data Integrity] Delta values: {len(unique_deltas)}")
    assert unique_deltas == DELTA_GRID, f"Delta grid mismatch"

    # Check repeats per combo
    rep_counts = df.groupby(['beta', 'eta', 'gamma_over_eta', 'n'])['repeat_id'].nunique()
    print(f"[Data Integrity] Repeats per combo: min={rep_counts.min()}, max={rep_counts.max()}")
    assert rep_counts.min() == expected_repeats, \
        f"Expected {expected_repeats} repeats, min found {rep_counts.min()}"

    # Check failure rate
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
    return hashlib_sha256(rounded.tobytes())


def hashlib_sha256(data):
    import hashlib
    return hashlib.sha256(data).hexdigest()


def compute_sample_features(sample):
    """Compute the 13 observable sample-statistic features (excluding delta).

    Returns dict with keys: x_min, x_max, range, Q1, Med, Q3, IQR, x_bar, s, CV, g1, g2, n
    """
    n = len(sample)
    x_min = float(sample[0])
    x_max = float(sample[-1])
    rng = x_max - x_min
    Q1 = float(np.percentile(sample, 25))
    Med = float(np.median(sample))
    Q3 = float(np.percentile(sample, 75))
    IQR = Q3 - Q1
    x_bar = float(np.mean(sample))
    s = float(np.std(sample, ddof=1)) if n > 1 else 0.0
    CV = s / x_bar if x_bar > 0 else 0.0

    # Skewness (g1) and Kurtosis (g2) — sample standard formulas
    if n > 2 and s > 0:
        z = (sample - x_bar) / s
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

    # Unique samples
    sample_keys = (
        df_mc[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']]
        .drop_duplicates()
        .sort_values(['beta', 'gamma_over_eta', 'n', 'repeat_id'])
        .reset_index(drop=True)
    )
    print(f"[Features] Computing features for {len(sample_keys)} unique samples...")

    # Compute features for each sample
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

    # Merge features into MC scan data
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

    # Replace inf/nan with NaN (will be handled by failure_penalty)
    df['loss'] = df['loss'].replace([np.inf, -np.inf], np.nan)

    return df


# ============================================================
# Split definitions
# ============================================================

def get_combo_split():
    """Define combo-holdout folds: leave out entire (beta, gamma/eta, n) combos.

    Use deterministic 5-fold partition over the 45 full parameter combos.
    Each fold holds out 9 complete combos and trains on the other 36.
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


def select_fit_rows(df_train, sample_cap=MAX_TRAIN_SAMPLES_PER_FOLD, random_state=42):
    """Limit training rows by samples while preserving each sample's full delta curve."""
    unique_samples = df_train[SAMPLE_KEYS].drop_duplicates().reset_index(drop=True)
    if sample_cap is None or len(unique_samples) <= sample_cap:
        return df_train

    sampled = unique_samples.sample(n=sample_cap, random_state=random_state)
    return df_train.merge(sampled, on=SAMPLE_KEYS, how='inner')


# ============================================================
# Oracle references (computed from full data — these are evaluation references, not inputs)
# ============================================================

def compute_reference_deltas(df):
    """Compute reference delta selections at each information layer.

    These are computed from the FULL dataset and serve as evaluation benchmarks.
    They are NOT used as model inputs.
    """
    # Default
    default_delta = DEFAULT_DELTA

    # L1: global best delta (argmin of pooled mean loss)
    global_loss = df.groupby('delta')['loss'].apply(
        lambda x: np.sqrt(np.nanmean(x))  # J1 = sqrt(mean(loss))
    )
    l1_delta = global_loss.idxmin()

    # L2: best delta per n
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

    # L3: best delta per (beta)
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

    # L4: best delta per (beta, n)
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

    # L5: best delta per (beta, gamma/eta, n)
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
# Model training and evaluation
# ============================================================

def prepare_training_data(df_train, df_test):
    """Prepare feature matrices and labels for training and evaluation.

    - Compute z-score scalers from TRAIN data only
    - Compute failure_penalty from TRAIN data only
    - Compute L4/L5 group labels from TRAIN data only

    Returns dict with prepared data.
    """
    # Failure penalty: p99 of valid training loss
    train_valid_loss = df_train['loss'].dropna()
    failure_penalty = float(np.nanpercentile(train_valid_loss, 99))
    print(f"  Failure penalty (train p99): {failure_penalty:.6f}")

    # Fill NaN losses with failure_penalty
    df_train = df_train.copy()
    df_test = df_test.copy()
    df_train['loss_filled'] = df_train['loss'].fillna(failure_penalty)
    df_test['loss_filled'] = df_test['loss'].fillna(failure_penalty)

    # Mark invalid (non-success) for failure tracking
    df_train['is_valid'] = df_train.get('status', 'success').eq('success') & df_train['loss'].notna()
    df_test['is_valid'] = df_test.get('status', 'success').eq('success') & df_test['loss'].notna()

    # Z-score scalers from TRAIN
    zscore_means = {}
    zscore_stds = {}
    for col in FEATURE_COLS_ZSCORE:
        vals = df_train[col].astype(float)
        zscore_means[col] = float(vals.mean())
        zscore_stds[col] = float(vals.std(ddof=0))
        # Guard against zero std
        if zscore_stds[col] < 1e-12:
            zscore_stds[col] = 1.0

    def apply_zscore(df):
        df = df.copy()
        for col in FEATURE_COLS_ZSCORE:
            df[f'{col}_z'] = (df[col].astype(float) - zscore_means[col]) / zscore_stds[col]
        return df

    df_train = apply_zscore(df_train)
    df_test = apply_zscore(df_test)

    # Feature columns for model input
    feat_cols = [f'{c}_z' for c in FEATURE_COLS_ZSCORE] + FEATURE_COLS_RAW

    # Compute L4 group labels from TRAIN only
    # L4: mean loss by (beta, n, delta) computed from train
    l4_group = (
        df_train.groupby(['beta', 'n', 'delta'])['loss_filled']
        .mean()
        .reset_index()
        .rename(columns={'loss_filled': 'l4_label'})
    )

    # Compute L5 group labels from TRAIN only
    # L5: mean loss by (beta, gamma/eta, n, delta) computed from train
    l5_group = (
        df_train.groupby(['beta', 'gamma_over_eta', 'n', 'delta'])['loss_filled']
        .mean()
        .reset_index()
        .rename(columns={'loss_filled': 'l5_label'})
    )

    # Merge group labels into train and test
    df_train = df_train.merge(l4_group, on=['beta', 'n', 'delta'], how='left')
    df_train = df_train.merge(l5_group, on=['beta', 'gamma_over_eta', 'n', 'delta'], how='left')

    df_test = df_test.merge(l4_group, on=['beta', 'n', 'delta'], how='left')
    df_test = df_test.merge(l5_group, on=['beta', 'gamma_over_eta', 'n', 'delta'], how='left')

    # For test rows where group label is NaN (combo not in train), fall back to
    # nearest available group label: use L3 (beta only) or L1 as fallback
    # This is expected behavior in combo holdout — test combos have no train data
    # for their specific (beta, n) or (beta, gamma/eta, n) group
    # We fill with global train mean loss per delta as fallback
    global_fallback = (
        df_train.groupby('delta')['loss_filled']
        .mean()
        .reset_index()
        .rename(columns={'loss_filled': 'global_label'})
    )
    df_train = df_train.merge(global_fallback, on='delta', how='left')
    df_test = df_test.merge(global_fallback, on='delta', how='left')

    # Fill NaN group labels with global fallback
    df_train['l4_label'] = df_train['l4_label'].fillna(df_train['global_label'])
    df_train['l5_label'] = df_train['l5_label'].fillna(df_train['global_label'])
    df_test['l4_label'] = df_test['l4_label'].fillna(df_test['global_label'])
    df_test['l5_label'] = df_test['l5_label'].fillna(df_test['global_label'])

    return {
        'feat_cols': feat_cols,
        'zscore_means': zscore_means,
        'zscore_stds': zscore_stds,
        'failure_penalty': failure_penalty,
        'df_train': df_train,
        'df_test': df_test,
    }


def train_and_predict_mlp(X_train, y_train, X_test, input_dim, seed=42):
    """Train a lightweight MLP regressor and predict on test set.

    Uses sklearn.neural_network.MLPRegressor (no TensorFlow/PyTorch available).
    Architecture: 64 -> 64 -> 32, ReLU activation, Adam optimizer.
    """
    from sklearn.neural_network import MLPRegressor

    model = MLPRegressor(
        hidden_layer_sizes=MLP_HIDDEN_LAYERS,
        activation='relu',
        solver='adam',
        alpha=1e-4,              # L2 regularization
        learning_rate_init=1e-3,
        max_iter=MLP_MAX_ITER,
        early_stopping=True,
        validation_fraction=0.1,
        n_iter_no_change=8,
        random_state=seed,
        batch_size=MLP_BATCH_SIZE,
    )

    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    # Clip to non-negative (loss >= 0)
    preds = np.clip(preds, 0, None)
    return preds


def train_and_predict_tabular(X_train, y_train, X_test):
    """Train HistGradientBoosting and predict."""
    from sklearn.ensemble import HistGradientBoostingRegressor

    model = HistGradientBoostingRegressor(
        max_iter=200,
        learning_rate=0.1,
        max_depth=6,
        random_state=42,
    )
    model.fit(X_train, y_train)
    preds = model.predict(X_test)
    return preds


def evaluate_model_selection(df_test, predicted_loss_col, model_name):
    """Evaluate delta selection quality for a model.

    For each test sample, select delta_hat = argmin predicted_loss over delta candidates.
    Then compute true selected J1.
    """
    sample_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    delta_candidates = sorted(df_test['delta'].unique())

    results = []

    for _, grp in df_test.groupby(sample_keys):
        if len(grp) != len(delta_candidates):
            continue

        # Predicted argmin
        pred_losses = grp[predicted_loss_col].values
        best_idx = np.argmin(pred_losses)
        selected_row = grp.iloc[best_idx]

        # True loss at selected delta
        true_loss = selected_row['loss_filled']
        is_valid = selected_row['is_valid']

        results.append({
            'beta': float(grp['beta'].iloc[0]),
            'eta': float(grp['eta'].iloc[0]),
            'gamma': float(grp['gamma'].iloc[0]),
            'gamma_over_eta': float(grp['gamma_over_eta'].iloc[0]),
            'n': int(grp['n'].iloc[0]),
            'repeat_id': int(grp['repeat_id'].iloc[0]),
            'selected_delta': float(selected_row['delta']),
            'true_loss': float(true_loss),
            'is_valid': bool(is_valid),
            'model': model_name,
        })

    df_sel = pd.DataFrame(results)
    if len(df_sel) == 0:
        return None

    # Compute J1 = sqrt(mean(true_loss))
    j1 = math.sqrt(df_sel['true_loss'].mean())
    failure_rate = 1.0 - df_sel['is_valid'].mean()

    # Per-n breakdown
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


def evaluate_reference_selection(df_test, ref_name, ref_delta_fn):
    """Evaluate a reference delta selection rule.

    ref_delta_fn(sample_row) -> selected delta
    """
    sample_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    results = []

    for _, grp in df_test.groupby(sample_keys):
        sample_info = grp.iloc[0]
        selected_delta = ref_delta_fn(sample_info)

        # Find the row at selected delta
        selected_row = grp[grp['delta'] == selected_delta]
        if len(selected_row) == 0:
            # Snap to nearest available delta
            deltas = grp['delta'].values
            idx = np.argmin(np.abs(deltas - selected_delta))
            selected_row = grp.iloc[[idx]]
        selected_row = selected_row.iloc[0]

        true_loss = selected_row['loss_filled']
        is_valid = selected_row['is_valid']

        results.append({
            'beta': float(grp['beta'].iloc[0]),
            'gamma_over_eta': float(grp['gamma_over_eta'].iloc[0]),
            'n': int(grp['n'].iloc[0]),
            'repeat_id': int(grp['repeat_id'].iloc[0]),
            'selected_delta': float(selected_row['delta']),
            'true_loss': float(true_loss),
            'is_valid': bool(is_valid),
            'model': ref_name,
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
        'model': ref_name,
        'J1': j1,
        'failure_rate': failure_rate,
        'n_samples': len(df_sel),
        'per_n': per_n,
        'delta_distribution': df_sel['selected_delta'].value_counts().sort_index().to_dict(),
        'df_sel': df_sel,
    }


def evaluate_l6_hindsight_selection(df_test, model_name='L6-hindsight'):
    """Evaluate per-sample hindsight selection by true loss."""
    sample_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    results = []

    for _, grp in df_test.groupby(sample_keys):
        best_idx = grp['loss_filled'].values.argmin()
        selected_row = grp.iloc[best_idx]
        results.append({
            'beta': float(grp['beta'].iloc[0]),
            'eta': float(grp['eta'].iloc[0]),
            'gamma': float(grp['gamma'].iloc[0]),
            'gamma_over_eta': float(grp['gamma_over_eta'].iloc[0]),
            'n': int(grp['n'].iloc[0]),
            'repeat_id': int(grp['repeat_id'].iloc[0]),
            'selected_delta': float(selected_row['delta']),
            'true_loss': float(selected_row['loss_filled']),
            'is_valid': bool(selected_row['is_valid']),
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


# ============================================================
# Main experiment
# ============================================================

def run_experiment():
    os.makedirs(E3_OUTPUT_DIR, exist_ok=True)

    print("=" * 70)
    print("Study/01 Formal E3a: Existing-Grid Risk-Curve Learning Pilot")
    print("=" * 70)

    # 1. Load data
    print("\n[1/7] Loading MC scan data...")
    df_mc = pd.read_csv(MC_SCAN_PATH)
    with open(MC_MANIFEST_PATH, encoding='utf-8') as f:
        manifest = json.load(f)
    print(f"  Loaded {len(df_mc)} rows from mc_scan_raw.csv")

    # 2. Data integrity
    print("\n[2/7] Verifying data integrity...")
    data_integrity = verify_data_integrity(df_mc, manifest)
    sample_reconstruction = verify_sample_reconstruction(manifest)
    print(f"  Sample probe SHA256: {sample_reconstruction['sample_sha256_rounded_12'][:12]}...")

    # 3. Build features
    print("\n[3/7] Building feature table...")
    df_full = build_feature_table(df_mc, manifest)

    # 4. Compute per-sample loss
    print("\n[4/7] Computing per-sample loss labels...")
    df_full = compute_per_sample_loss(df_full)

    # Count NaN losses
    nan_count = df_full['loss'].isna().sum()
    print(f"  NaN/invalid losses: {nan_count} ({nan_count/len(df_full)*100:.2f}%)")

    # 5. Compute oracle references (from full data, for evaluation only)
    print("\n[5/7] Computing oracle references...")
    refs = compute_reference_deltas(df_full)
    print(f"  L1 delta* = {refs['l1_delta']}")
    print(f"  L2 table: {refs['l2_table']}")

    # 6. Run evaluations
    all_results = []

    # --- 6a. Random split sanity check ---
    print("\n[6a/7] Random split (sanity check)...")
    df_train_r, df_test_r = split_by_random(df_full, test_frac=0.2, random_state=42)
    print(f"  Train: {len(df_train_r)} rows, Test: {len(df_test_r)} rows")

    prep_r = prepare_training_data(df_train_r, df_test_r)
    feat_cols = prep_r['feat_cols']
    df_tr = prep_r['df_train']
    df_te = prep_r['df_test']
    df_fit = select_fit_rows(df_tr, random_state=42)
    print(f"  Fit rows: {len(df_fit)} "
          f"({df_fit[SAMPLE_KEYS].drop_duplicates().shape[0]} samples)")

    X_train_r = df_fit[feat_cols].values.astype(np.float32)
    X_test_r = df_te[feat_cols].values.astype(np.float32)

    # NN-RC-L6
    print("  Training NN-RC-L6 (MLP, per-sample)...")
    y_train_l6 = df_fit['loss_filled'].values.astype(np.float32)
    preds_l6_r = train_and_predict_mlp(X_train_r, y_train_l6, X_test_r,
                                        len(feat_cols))
    df_te = df_te.copy()
    df_te['pred_l6'] = preds_l6_r
    res_l6_r = evaluate_model_selection(df_te, 'pred_l6', 'NN-RC-L6')
    res_l6_r['split'] = 'random'
    all_results.append(res_l6_r)

    # NN-RC-L4
    print("  Training NN-RC-L4 (MLP, beta×n group)...")
    y_train_l4 = df_fit['l4_label'].values.astype(np.float32)
    preds_l4_r = train_and_predict_mlp(X_train_r, y_train_l4, X_test_r,
                                        len(feat_cols))
    df_te['pred_l4'] = preds_l4_r
    res_l4_r = evaluate_model_selection(df_te, 'pred_l4', 'NN-RC-L4')
    res_l4_r['split'] = 'random'
    all_results.append(res_l4_r)

    # NN-RC-L5
    print("  Training NN-RC-L5 (MLP, beta×gamma/eta×n group)...")
    y_train_l5 = df_fit['l5_label'].values.astype(np.float32)
    preds_l5_r = train_and_predict_mlp(X_train_r, y_train_l5, X_test_r,
                                        len(feat_cols))
    df_te['pred_l5'] = preds_l5_r
    res_l5_r = evaluate_model_selection(df_te, 'pred_l5', 'NN-RC-L5')
    res_l5_r['split'] = 'random'
    all_results.append(res_l5_r)

    # Tabular baseline (HistGBR) with L6 label
    print("  Training Tabular-L6 (HistGBR, per-sample)...")
    preds_tab_r = train_and_predict_tabular(X_train_r, y_train_l6, X_test_r)
    df_te['pred_tab_l6'] = preds_tab_r
    res_tab_r = evaluate_model_selection(df_te, 'pred_tab_l6', 'Tabular-L6')
    res_tab_r['split'] = 'random'
    all_results.append(res_tab_r)

    # References on random split test set
    for ref_name, ref_fn in [
        ('Default', lambda s: refs['default_delta']),
        ('L1', lambda s: refs['l1_delta']),
        ('L2', lambda s: refs['l2_table'][int(s['n'])]['delta_star']),
        ('L3-oracle', lambda s: refs['l3_table'][float(s['beta'])]['delta_star']),
        ('L4-oracle', lambda s: refs['l4_table'][(float(s['beta']), int(s['n']))]['delta_star']),
        ('L5-oracle', lambda s: refs['l5_table'][(float(s['beta']), float(s['gamma_over_eta']), int(s['n']))]['delta_star']),
    ]:
        res_ref = evaluate_reference_selection(df_te, ref_name, ref_fn)
        res_ref['split'] = 'random'
        all_results.append(res_ref)
    res_l6_ref = evaluate_l6_hindsight_selection(df_te)
    res_l6_ref['split'] = 'random'
    all_results.append(res_l6_ref)

    # --- 6b. Combo holdout (main judgment) ---
    print("\n[6b/7] Combo holdout (main judgment)...")
    combo_folds = get_combo_split()

    fold_results = []
    for fold_idx, fold in enumerate(combo_folds):
        fold_name = fold['fold_name']
        print(f"\n  Fold: {fold_name}")
        print(f"  Train combos: {len(fold['train_combos'])}, "
              f"Test combos: {len(fold['test_combos'])}")

        # Split by combo
        train_combo_set = set(fold['train_combos'])
        test_combo_set = set(fold['test_combos'])

        def combo_key(row):
            return (float(row['beta']), float(row['gamma_over_eta']), int(row['n']))

        df_full['_combo'] = [
            (float(b), float(g), int(n))
            for b, g, n in zip(df_full['beta'], df_full['gamma_over_eta'], df_full['n'])
        ]

        df_tr_c = df_full[df_full['_combo'].isin(train_combo_set)].copy()
        df_te_c = df_full[df_full['_combo'].isin(test_combo_set)].copy()

        print(f"  Train rows: {len(df_tr_c)}, Test rows: {len(df_te_c)}")

        prep_c = prepare_training_data(df_tr_c, df_te_c)
        df_tr = prep_c['df_train']
        df_te = prep_c['df_test']
        df_fit = select_fit_rows(df_tr, random_state=100 + fold_idx)
        print(f"  Fit rows: {len(df_fit)} "
              f"({df_fit[SAMPLE_KEYS].drop_duplicates().shape[0]} samples)")

        X_train_c = df_fit[feat_cols].values.astype(np.float32)
        X_test_c = df_te[feat_cols].values.astype(np.float32)

        # NN-RC-L6
        print(f"  Training NN-RC-L6...")
        y_l6 = df_fit['loss_filled'].values.astype(np.float32)
        preds_l6 = train_and_predict_mlp(X_train_c, y_l6, X_test_c, len(feat_cols))
        df_te = df_te.copy()
        df_te['pred_l6'] = preds_l6
        res = evaluate_model_selection(df_te, 'pred_l6', 'NN-RC-L6')
        res['split'] = f'combo_{fold_name}'
        fold_results.append(res)

        # NN-RC-L4
        print(f"  Training NN-RC-L4...")
        y_l4 = df_fit['l4_label'].values.astype(np.float32)
        preds_l4 = train_and_predict_mlp(X_train_c, y_l4, X_test_c, len(feat_cols))
        df_te['pred_l4'] = preds_l4
        res = evaluate_model_selection(df_te, 'pred_l4', 'NN-RC-L4')
        res['split'] = f'combo_{fold_name}'
        fold_results.append(res)

        # NN-RC-L5
        print(f"  Training NN-RC-L5...")
        y_l5 = df_fit['l5_label'].values.astype(np.float32)
        preds_l5 = train_and_predict_mlp(X_train_c, y_l5, X_test_c, len(feat_cols))
        df_te['pred_l5'] = preds_l5
        res = evaluate_model_selection(df_te, 'pred_l5', 'NN-RC-L5')
        res['split'] = f'combo_{fold_name}'
        fold_results.append(res)

        # Tabular-L6
        print(f"  Training Tabular-L6...")
        preds_tab = train_and_predict_tabular(X_train_c, y_l6, X_test_c)
        df_te['pred_tab_l6'] = preds_tab
        res = evaluate_model_selection(df_te, 'pred_tab_l6', 'Tabular-L6')
        res['split'] = f'combo_{fold_name}'
        fold_results.append(res)

        # References
        for ref_name, ref_fn in [
            ('Default', lambda s: refs['default_delta']),
            ('L1', lambda s: refs['l1_delta']),
            ('L2', lambda s: refs['l2_table'][int(s['n'])]['delta_star']),
            ('L3-oracle', lambda s: refs['l3_table'][float(s['beta'])]['delta_star']),
            ('L4-oracle', lambda s: refs['l4_table'][(float(s['beta']), int(s['n']))]['delta_star']),
            ('L5-oracle', lambda s: refs['l5_table'][(float(s['beta']), float(s['gamma_over_eta']), int(s['n']))]['delta_star']),
        ]:
            res = evaluate_reference_selection(df_te, ref_name, ref_fn)
            res['split'] = f'combo_{fold_name}'
            fold_results.append(res)
        res = evaluate_l6_hindsight_selection(df_te)
        res['split'] = f'combo_{fold_name}'
        fold_results.append(res)

    # Aggregate combo holdout results across folds
    print("\n  Aggregating combo holdout across folds...")
    combo_models = ['NN-RC-L4', 'NN-RC-L5', 'NN-RC-L6', 'Tabular-L6',
                    'Default', 'L1', 'L2', 'L3-oracle', 'L4-oracle',
                    'L5-oracle', 'L6-hindsight']

    combo_agg = []
    for model_name in combo_models:
        model_fold_results = [r for r in fold_results if r['model'] == model_name]
        if not model_fold_results:
            continue

        # Pool all selected samples
        all_dfs = []
        for r in model_fold_results:
            if 'df_sel' in r:
                all_dfs.append(r['df_sel'])

        if all_dfs:
            df_pooled = pd.concat(all_dfs, ignore_index=True)
            j1_pooled = math.sqrt(df_pooled['true_loss'].mean())
            fail_pooled = 1.0 - df_pooled['is_valid'].mean()

            per_n = {}
            for n_val in sorted(df_pooled['n'].unique()):
                sub = df_pooled[df_pooled['n'] == n_val]
                per_n[n_val] = {
                    'J1': math.sqrt(sub['true_loss'].mean()),
                    'failure_rate': 1.0 - sub['is_valid'].mean(),
                    'count': len(sub),
                }

            combo_agg.append({
                'model': model_name,
                'split': 'combo_holdout_pooled',
                'J1': j1_pooled,
                'failure_rate': fail_pooled,
                'n_samples': len(df_pooled),
                'per_n': per_n,
                'delta_distribution': df_pooled['selected_delta'].value_counts().sort_index().to_dict(),
            })

    all_results.extend(fold_results)
    all_results.extend(combo_agg)

    # 7. Save artifacts
    print("\n[7/7] Saving artifacts...")
    save_artifacts(
        df_full, refs, all_results, combo_agg, prep_r,
        data_integrity=data_integrity,
        sample_reconstruction=sample_reconstruction,
    )

    return all_results, refs, combo_agg


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


def decide_acceptance(combo_agg, random_results):
    by_model = {r['model']: r for r in combo_agg}
    l2 = by_model.get('L2')
    candidates = [by_model[m] for m in ('NN-RC-L5', 'NN-RC-L6') if m in by_model]

    if l2 is None:
        return 'BLOCK', ['Missing pooled L2 baseline in combo holdout results.']
    if not candidates:
        return 'BLOCK', ['Missing NN-RC-L5/NN-RC-L6 pooled combo holdout results.']

    best = min(candidates, key=lambda r: r['J1'])
    improvement = l2['J1'] - best['J1']
    clear_threshold = max(0.005, 0.01 * l2['J1'])
    reasons = [
        f"Best adaptive candidate is {best['model']} with J1={best['J1']:.6f}; "
        f"L2 J1={l2['J1']:.6f}; improvement={improvement:.6f}."
    ]

    if best['failure_rate'] > l2['failure_rate'] + 0.01:
        reasons.append(
            f"{best['model']} failure rate {best['failure_rate']:.4f} exceeds "
            f"L2 {l2['failure_rate']:.4f} by more than 0.01."
        )
        return 'BLOCK', reasons

    degraded_n = []
    for n_val, l2_info in l2.get('per_n', {}).items():
        best_info = best.get('per_n', {}).get(n_val)
        if not best_info:
            continue
        if best_info['J1'] > l2_info['J1'] * 1.10 and best_info['J1'] - l2_info['J1'] > 0.02:
            degraded_n.append((n_val, l2_info['J1'], best_info['J1']))
    if degraded_n:
        detail = ', '.join(
            f"n={n}: L2={l2_j1:.6f}, {best['model']}={best_j1:.6f}"
            for n, l2_j1, best_j1 in degraded_n
        )
        reasons.append(f"Catastrophic per-n degradation: {detail}.")
        return 'BLOCK', reasons

    if improvement >= clear_threshold:
        reasons.append('Combo holdout shows a clear pooled J1 improvement over L2.')
        return 'APPROVE', reasons

    if improvement > 0:
        reasons.append('Combo holdout improves over L2, but the gain is below the clear-improvement threshold.')
        return 'REVISE', reasons

    random_by_model = {r['model']: r for r in random_results}
    random_l2 = random_by_model.get('L2')
    random_candidates = [
        random_by_model[m] for m in ('NN-RC-L5', 'NN-RC-L6') if m in random_by_model
    ]
    if random_l2 and random_candidates:
        random_best = min(random_candidates, key=lambda r: r['J1'])
        if random_best['J1'] < random_l2['J1']:
            reasons.append(
                f"Random split improves over L2 ({random_best['model']} "
                f"{random_best['J1']:.6f} vs L2 {random_l2['J1']:.6f}), "
                "but combo holdout does not."
            )
            return 'REVISE', reasons

    reasons.append('Neither NN-RC-L5 nor NN-RC-L6 improves over L2 in combo holdout.')
    return 'BLOCK', reasons


def write_acceptance_report(
    output_dir,
    data_integrity,
    combo_agg,
    random_results,
    split_rows,
    decision,
    decision_reasons,
):
    os.makedirs(output_dir, exist_ok=True)
    report_path = os.path.join(output_dir, 'E3a_acceptance_report.md')

    def fmt(value):
        if value is None:
            return ''
        if isinstance(value, float):
            return f"{value:.6f}"
        return str(value)

    def result_table(results):
        lines = [
            "| model | J1 | failure_rate | n_samples | J1_n7 | J1_n10 | J1_n20 |",
            "|---|---:|---:|---:|---:|---:|---:|",
        ]
        for r in sorted(results, key=lambda x: x['J1']):
            per_n = r.get('per_n', {})
            lines.append(
                "| {model} | {J1} | {failure_rate} | {n_samples} | {n7} | {n10} | {n20} |".format(
                    model=r['model'],
                    J1=fmt(r['J1']),
                    failure_rate=fmt(r['failure_rate']),
                    n_samples=r['n_samples'],
                    n7=fmt(per_n.get(7, {}).get('J1')),
                    n10=fmt(per_n.get(10, {}).get('J1')),
                    n20=fmt(per_n.get(20, {}).get('J1')),
                )
            )
        return "\n".join(lines)

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

    text = "\n".join([
        "# E3a Acceptance Report",
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
        result_table(combo_agg),
        "",
        "## Random Split",
        "",
        result_table(random_results) if random_results else "_No random split results recorded._",
        "",
        "## Split Preview",
        "",
        "\n".join(split_lines),
        "",
        f"_Split rows recorded: {len(split_rows)}._",
        "",
    ])

    with open(report_path, 'w', encoding='utf-8') as f:
        f.write(text)
    return report_path


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
    df_full, refs, all_results, combo_agg, prep_data,
    data_integrity,
    sample_reconstruction,
):
    """Save all experiment artifacts."""
    os.makedirs(E3_OUTPUT_DIR, exist_ok=True)

    # --- model_comparison.csv ---
    rows = []
    for r in all_results:
        row = {
            'model': r['model'],
            'split': r['split'],
            'J1': r['J1'],
            'failure_rate': r['failure_rate'],
            'n_samples': r['n_samples'],
        }
        for n_val, n_info in r.get('per_n', {}).items():
            row[f'J1_n{n_val}'] = n_info['J1']
            row[f'fail_n{n_val}'] = n_info['failure_rate']
        rows.append(row)

    df_comp = pd.DataFrame(rows)
    comp_path = os.path.join(E3_OUTPUT_DIR, 'model_comparison.csv')
    df_comp.to_csv(comp_path, index=False)
    print(f"  Saved {comp_path}")

    # --- split_report.csv ---
    split_info = build_split_rows()
    df_split = pd.DataFrame(split_info)
    split_path = os.path.join(E3_OUTPUT_DIR, 'split_report.csv')
    df_split.to_csv(split_path, index=False)
    print(f"  Saved {split_path}")

    # --- delta_distribution.csv ---
    dist_rows = []
    for r in combo_agg:
        for delta_val, count in r.get('delta_distribution', {}).items():
            dist_rows.append({
                'model': r['model'],
                'split': r['split'],
                'selected_delta': delta_val,
                'count': count,
                'fraction': count / r['n_samples'] if r['n_samples'] > 0 else 0,
            })
    df_dist = pd.DataFrame(dist_rows)
    dist_path = os.path.join(E3_OUTPUT_DIR, 'delta_distribution.csv')
    df_dist.to_csv(dist_path, index=False)
    print(f"  Saved {dist_path}")

    # --- results.csv (per-sample selected results for combo holdout pooled) ---
    # Save the pooled selection results for the main models
    results_rows = []
    for r in all_results:
        if 'df_sel' in r and r['split'].startswith('combo_'):
            for _, row in r['df_sel'].iterrows():
                results_rows.append({
                    'model': row['model'],
                    'split': r['split'],
                    'beta': row['beta'],
                    'gamma_over_eta': row['gamma_over_eta'],
                    'n': row['n'],
                    'repeat_id': row['repeat_id'],
                    'selected_delta': row['selected_delta'],
                    'true_loss': row['true_loss'],
                    'is_valid': row['is_valid'],
                })
    df_results = pd.DataFrame(results_rows)
    results_path = os.path.join(E3_OUTPUT_DIR, 'results.csv')
    df_results.to_csv(results_path, index=False)
    print(f"  Saved {results_path}")

    # --- summary.json ---
    summary = {
        'experiment': 'E3a',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'description': 'Existing-grid risk-curve learning pilot',
        'feature_cols': ALL_FEATURE_COLS,
        'zscore_cols': FEATURE_COLS_ZSCORE,
        'raw_cols': FEATURE_COLS_RAW,
        'references': {
            'default_delta': refs['default_delta'],
            'l1_delta': refs['l1_delta'],
            'l2_table': {str(k): v for k, v in refs['l2_table'].items()},
        },
        'combo_holdout_pooled': [
            {
                'model': r['model'],
                'J1': r['J1'],
                'failure_rate': r['failure_rate'],
                'per_n': {str(k): v for k, v in r.get('per_n', {}).items()},
            }
            for r in combo_agg
        ],
        'random_split': [
            {
                'model': r['model'],
                'J1': r['J1'],
                'failure_rate': r['failure_rate'],
            }
            for r in all_results if r.get('split') == 'random'
        ],
    }

    summary_path = os.path.join(E3_OUTPUT_DIR, 'summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)
    print(f"  Saved {summary_path}")

    # --- acceptance report ---
    random_results = [r for r in all_results if r.get('split') == 'random']
    decision, decision_reasons = decide_acceptance(combo_agg, random_results)
    report_path = write_acceptance_report(
        output_dir=E3_OUTPUT_DIR,
        data_integrity=data_integrity,
        combo_agg=combo_agg,
        random_results=random_results,
        split_rows=split_info,
        decision=decision,
        decision_reasons=decision_reasons,
    )
    print(f"  Saved {report_path}")

    # --- manifest.json ---
    git_meta = get_git_metadata()

    manifest_out = {
        'run_id': 'E3a_risk_curve_pilot_v1',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'code_entry': 'code/run_E3a.py',
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
            'input': ALL_FEATURE_COLS,
            'zscore_applied': FEATURE_COLS_ZSCORE,
            'zscore_source': 'training_set_only',
            'raw_passthrough': FEATURE_COLS_RAW,
            'no_rescale_delta': True,
        },
        'label_contract': {
            'base': '((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2',
            'failure_penalty': 'p99(valid_training_loss)',
            'no_regret': True,
            'no_log_transform': True,
        },
        'split_contract': {
            'random_split': '80/20 sanity check, seed=42',
            'combo_holdout': 'deterministic 5-fold full-combo holdout; each fold holds 9 complete (beta,gamma/eta,n) combos',
        },
        'fit_contract': {
            'max_train_samples_per_fold': MAX_TRAIN_SAMPLES_PER_FOLD,
            'sample_curve_preserved': True,
            'note': 'Scalers, failure penalties, and L4/L5 group labels use the full training fold; model fitting is capped by complete sample curves for runtime.',
        },
        'models': {
            'NN-RC-L4': f'sklearn MLPRegressor{MLP_HIDDEN_LAYERS}, max_iter={MLP_MAX_ITER}, ReLU/Adam, supervised by train-only mean loss per (beta,n,delta)',
            'NN-RC-L5': f'sklearn MLPRegressor{MLP_HIDDEN_LAYERS}, max_iter={MLP_MAX_ITER}, ReLU/Adam, supervised by train-only mean loss per (beta,gamma/eta,n,delta)',
            'NN-RC-L6': f'sklearn MLPRegressor{MLP_HIDDEN_LAYERS}, max_iter={MLP_MAX_ITER}, ReLU/Adam, supervised by per-sample loss_i(delta)',
            'Tabular-L6': 'HistGradientBoostingRegressor(200 trees), supervised by per-sample loss_i(delta)',
        },
        'evaluation': {
            'objective': 'selection_quality (argmin_delta predicted_loss -> true selected J1)',
            'metric': 'J1 = sqrt(mean_i(true_loss_i(delta_hat_i)))',
        },
        'output_files': [
            'manifest.json',
            'results.csv',
            'summary.json',
            'model_comparison.csv',
            'split_report.csv',
            'delta_distribution.csv',
            'E3a_acceptance_report.md',
        ],
        'notes': 'E3a pilot: existing-grid only, no new MC scans. L4/L5 group labels computed from train fold only.',
    }

    manifest_path = os.path.join(E3_OUTPUT_DIR, 'manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest_out, f, indent=2, ensure_ascii=False)
    print(f"  Saved {manifest_path}")


# ============================================================
# Main
# ============================================================

if __name__ == '__main__':
    import subprocess
    results, refs, combo_agg = run_experiment()

    # Print summary table
    print("\n" + "=" * 70)
    print("RESULTS SUMMARY — Combo Holdout (Pooled)")
    print("=" * 70)
    print(f"{'Model':<15} {'J1':>8} {'Fail%':>7} {'J1(n=7)':>8} {'J1(n=10)':>8} {'J1(n=20)':>8}")
    print("-" * 70)
    for r in sorted(combo_agg, key=lambda x: x['J1']):
        per_n = r.get('per_n', {})
        j1_7 = per_n.get(7, {}).get('J1', float('nan'))
        j1_10 = per_n.get(10, {}).get('J1', float('nan'))
        j1_20 = per_n.get(20, {}).get('J1', float('nan'))
        print(f"{r['model']:<15} {r['J1']:>8.4f} {r['failure_rate']*100:>6.2f}% "
              f"{j1_7:>8.4f} {j1_10:>8.4f} {j1_20:>8.4f}")

    print(f"\n{'Model':<15} {'J1':>8} {'Fail%':>7}")
    print("-" * 35)
    print("Random split (sanity check):")
    for r in results:
        if r.get('split') == 'random':
            print(f"  {r['model']:<13} {r['J1']:>8.4f} {r['failure_rate']*100:>6.2f}%")
