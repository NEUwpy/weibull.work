"""
Study/01 Formal E4 — Validation Analysis Script

Handles all 4 tracks:
  E4a: Feature ablation (5-fold × 3 seeds × 4 groups, E3b MLP config)
  E4b: Boundary reference robustness (Default/L1/L2/L3/L4/L5/L6 on boundary combos)
  E4c: Off-grid reference robustness (same references on off-grid combos)
  E4d: Selector extrapolation diagnostic (train on main grid, evaluate on boundary/offgrid)

Reads:
  - Existing formal MC data: artifacts/formal/shared_data/mc_scan_raw.csv (for E4a + E4d training)
  - New boundary MC data: artifacts/formal/E4_robustness/boundary_risk_curves.csv (E4b)
  - New offgrid MC data: artifacts/formal/E4_robustness/offgrid_risk_curves.csv (E4c)

Writes:
  - artifacts/formal/E4_robustness/E4a_feature_ablation.csv
  - artifacts/formal/E4_robustness/E4b_boundary_reference.csv
  - artifacts/formal/E4_robustness/E4c_offgrid_reference.csv
  - artifacts/formal/E4_robustness/E4d_selector_extrapolation.csv (or E4d_skip_reason.md)
  - artifacts/formal/E4_robustness/endpoint_diagnostics.csv
  - artifacts/formal/E4_robustness/near_optimal_diagnostics.csv
  - artifacts/formal/E4_robustness/cost_report.csv
  - artifacts/formal/E4_robustness/split_report.csv
  - artifacts/formal/E4_robustness/manifest.json
  - artifacts/formal/E4_robustness/summary.json
  - artifacts/formal/E4_robustness/run_log.txt
  - artifacts/formal/E4_robustness/E4_acceptance_report.md
"""

import sys
import os
import json
import time
import math
import gc
import subprocess
import warnings
from datetime import datetime, timezone
from itertools import product

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

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
from utils import get_git_info, now_iso
from studies.common.sample import generate_sample

# ============================================================
# Output directory
# ============================================================

E4_OUTPUT_DIR = os.path.join(ARTIFACTS_DIR, "E4_robustness")
os.makedirs(E4_OUTPUT_DIR, exist_ok=True)

MC_SCAN_PATH = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")
BOUNDARY_PATH = os.path.join(E4_OUTPUT_DIR, "boundary_risk_curves.csv")
OFFGRID_PATH = os.path.join(E4_OUTPUT_DIR, "offgrid_risk_curves.csv")

# ============================================================
# Feature columns (same as E3b)
# ============================================================

FEATURE_COLS_ZSCORE = [
    'x_min', 'x_max', 'range', 'Q1', 'Med', 'Q3', 'IQR', 'x_bar', 's'
]
FEATURE_COLS_RAW = ['n', 'CV', 'g1', 'g2']
SAMPLE_FEATURE_COLS = FEATURE_COLS_ZSCORE + FEATURE_COLS_RAW

BANNED_FIELDS = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'seed', 'repeat_id', 'combo_id'}

ABLATION_GROUPS = {
    'full': SAMPLE_FEATURE_COLS,
    'n_only': ['n'],
    'scale_quantile': ['n', 'x_min', 'x_max', 'range', 'Q1', 'Med', 'Q3', 'IQR', 'x_bar', 's'],
    'shape': ['n', 'CV', 'g1', 'g2'],
}

N_DELTAS = len(DELTA_GRID)
NEAR_OPTIMAL_EPS = [0.01, 0.02, 0.05]
STABILITY_SEEDS = [42, 2026, 3407]

# E3b-equivalent MLP config
MLP_HIDDEN_LAYERS = (256, 128, 64)
MLP_MAX_ITER = 300
MLP_BATCH_SIZE = 256
MLP_ALPHA = 1e-4
MLP_LR = 1e-3
MLP_VALIDATION_FRACTION = 0.15
MLP_N_ITER_NO_CHANGE = 20

SAMPLE_KEYS = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']

# Frozen combo lists
E4B_BOUNDARY_COMBOS = [
    ("B01", 1.2, 0.0, 5), ("B02", 1.2, 0.0, 20), ("B03", 1.2, 0.5, 5),
    ("B04", 1.2, 0.5, 20), ("B05", 1.2, 1.0, 50), ("B06", 1.2, 0.1, 10),
    ("B07", 6.0, 0.0, 5), ("B08", 6.0, 0.0, 20), ("B09", 6.0, 0.5, 7),
    ("B10", 6.0, 0.5, 50), ("B11", 6.0, 1.0, 20), ("B12", 6.0, 0.1, 10),
    ("B13", 2.5, 0.0, 5), ("B14", 2.5, 0.0, 50), ("B15", 2.5, 0.5, 50),
    ("B16", 2.5, 1.0, 5), ("B17", 1.5, 0.0, 10), ("B18", 4.0, 0.0, 20),
    ("B19", 2.0, 0.1, 50), ("B20", 4.0, 1.0, 5),
]
E4C_OFFGRID_COMBOS = [
    ("O01", 1.8, 0.3, 12), ("O02", 3.3, 0.7, 15), ("O03", 5.5, 0.2, 30),
    ("O04", 1.3, 0.9, 8), ("O05", 4.7, 0.4, 25), ("O06", 2.2, 0.0, 6),
    ("O07", 5.8, 0.8, 45), ("O08", 1.6, 0.05, 50), ("O09", 3.8, 0.95, 5),
    ("O10", 2.8, 0.6, 18), ("O11", 4.4, 0.15, 35), ("O12", 1.25, 0.25, 7),
    ("O13", 5.9, 0.75, 20), ("O14", 3.6, 0.35, 10),
]

log_lines = []
def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    print(line)
    log_lines.append(line)


class PreflightError(Exception):
    """Raised when preflight input validation fails (fail-closed)."""
    pass


def preflight_check_inputs(requested_tracks, input_path_map):
    """Validate that all required input files exist for the requested tracks.

    Args:
        requested_tracks: set of track strings (e.g. {'e4b', 'e4c'})
        input_path_map: dict mapping track -> list of required file paths

    Raises:
        PreflightError: with a descriptive message if any input is missing.
    """
    missing_inputs = []
    for track in sorted(requested_tracks):
        for path in input_path_map.get(track, []):
            if not os.path.exists(path):
                missing_inputs.append((track, path))
    if missing_inputs:
        lines = ["Required input files missing for requested tracks:"]
        for track, path in missing_inputs:
            lines.append(f"  [{track}] {path}")
        raise PreflightError("\n".join(lines))


# ============================================================
# Feature computation (same as E3b)
# ============================================================

def compute_sample_features(sample):
    n = len(sample)
    s_sorted = np.sort(sample)
    x_min = float(s_sorted[0])
    x_max = float(s_sorted[-1])
    rng = x_max - x_min
    Q1 = float(np.percentile(s_sorted, 25))
    Med = float(np.median(s_sorted))
    Q3 = float(np.percentile(s_sorted, 75))
    IQR = Q3 - Q1
    x_bar = float(np.mean(s_sorted))
    s = float(np.std(s_sorted, ddof=1)) if n > 1 else 0.0
    CV = s / x_bar if x_bar > 0 else 0.0
    if n > 2 and s > 0:
        z = (s_sorted - x_bar) / s
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


def compute_loss(df):
    r_beta = (df['beta_hat'] - df['beta']) / df['beta']
    r_eta = (df['eta_hat'] - df['eta']) / df['eta']
    r_gamma = (df['gamma_hat'] - df['gamma']) / df['eta']
    df = df.copy()
    df['loss'] = r_beta**2 + r_eta**2 + r_gamma**2
    df['loss'] = df['loss'].replace([np.inf, -np.inf], np.nan)
    return df


def build_feature_table_for_combos(combo_list, seed_ns=SEED_NAMESPACE):
    """Build features for a list of (combo_id, beta, goe, n) tuples.
    Returns DataFrame with sample keys + features.
    """
    records = []
    for combo_id, beta, goe, n in combo_list:
        gamma = goe * 1.0  # eta=1.0
        for rid in range(R_MAIN):
            sample = generate_sample(beta, 1.0, gamma, n, rid, seed=seed_ns)
            feats = compute_sample_features(sample)
            feats['combo_id'] = combo_id
            feats['beta'] = beta
            feats['eta'] = 1.0
            feats['gamma'] = gamma
            feats['gamma_over_eta'] = goe
            feats['n'] = n
            feats['repeat_id'] = rid
            records.append(feats)
    return pd.DataFrame(records)


def build_feature_table_from_mc(df_mc, seed_ns=SEED_NAMESPACE):
    """Build features from MC scan data (for E4a — existing main grid)."""
    sample_keys_df = (
        df_mc[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']]
        .drop_duplicates()
        .sort_values(['beta', 'gamma_over_eta', 'n', 'repeat_id'])
        .reset_index(drop=True)
    )
    log(f"  Computing features for {len(sample_keys_df)} unique samples...")
    feat_records = []
    t0 = time.time()
    for _, row in sample_keys_df.iterrows():
        beta = float(row['beta'])
        eta = float(row['eta'])
        gamma = float(row['gamma'])
        n = int(row['n'])
        rid = int(row['repeat_id'])
        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_ns)
        feats = compute_sample_features(sample)
        for k, v in row.to_dict().items():
            feats[k] = v
        feat_records.append(feats)
    df_feat = pd.DataFrame(feat_records)
    log(f"  Features done in {time.time()-t0:.1f}s")
    return df_feat


# ============================================================
# Split definitions (same 5-fold as E3b)
# ============================================================

def get_combo_split():
    combos = list(product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID))
    folds = []
    for fold_idx in range(5):
        test_combos = [c for i, c in enumerate(combos) if i % 5 == fold_idx]
        train_combos = [c for i, c in enumerate(combos) if i % 5 != fold_idx]
        folds.append({
            'fold_name': f'combo_fold_{fold_idx+1}',
            'train_combos': train_combos,
            'test_combos': test_combos,
        })
    return folds


# ============================================================
# E4a: Feature ablation
# ============================================================

def run_e4a(df_mc):
    """Run formal feature ablation: 4 groups × 5 folds × 3 seeds."""
    log("=== E4a: Feature Ablation ===")

    # Build feature table
    df_feat = build_feature_table_from_mc(df_mc)
    merge_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    df_merged = df_mc.merge(df_feat, on=merge_keys, how='left', suffixes=('', '_feat'))
    for col in list(df_merged.columns):
        if col.endswith('_feat'):
            df_merged.drop(columns=col, inplace=True)
    df_merged = compute_loss(df_merged)

    # Verify no banned fields in features
    assert not (set(SAMPLE_FEATURE_COLS) & BANNED_FIELDS), "Banned field in features!"

    results = []
    cost_rows = []
    folds = get_combo_split()

    for fold in folds:
        fold_name = fold['fold_name']
        train_combos = set(fold['train_combos'])
        test_combos = set(fold['test_combos'])

        def is_in_combos(row, combo_set):
            return (row['beta'], row['gamma_over_eta'], row['n']) in combo_set

        df_train = df_merged[df_merged.apply(
            lambda r: is_in_combos(r, train_combos), axis=1
        )].copy()
        df_test = df_merged[df_merged.apply(
            lambda r: is_in_combos(r, test_combos), axis=1
        )].copy()

        log(f"  Fold {fold_name}: train={len(df_train)}, test={len(df_test)}")

        # Z-score from train
        zscore_means = {}
        zscore_stds = {}
        for col in FEATURE_COLS_ZSCORE:
            vals = df_train[col].astype(float)
            zscore_means[col] = float(vals.mean())
            zscore_stds[col] = float(vals.std(ddof=0))
            if zscore_stds[col] < 1e-12:
                zscore_stds[col] = 1.0

        # Failure penalty from train
        train_valid_loss = df_train['loss'].dropna()
        failure_penalty = float(np.nanpercentile(train_valid_loss, 99))

        df_train['loss_filled'] = df_train['loss'].fillna(failure_penalty)
        df_test['loss_filled'] = df_test['loss'].fillna(failure_penalty)

        for group_name, group_features in ABLATION_GROUPS.items():
            for seed in STABILITY_SEEDS:
                log(f"    {fold_name} / {group_name} / seed={seed}")
                t0 = time.time()

                res = _train_eval_ablation(
                    df_train, df_test, group_features,
                    zscore_means, zscore_stds, failure_penalty,
                    fold_name, seed
                )

                elapsed = time.time() - t0
                res['elapsed_s'] = elapsed
                results.append(res)

                cost_rows.append({
                    'track': 'E4a',
                    'fold': fold_name,
                    'feature_group': group_name,
                    'seed': seed,
                    'n_features': len(group_features),
                    'elapsed_s': elapsed,
                    'n_train': len(df_train),
                    'n_test': len(df_test),
                })
                log(f"      J1={res['pooled_J1']:.6f}, elapsed={elapsed:.1f}s")

                gc.collect()

    df_results = pd.DataFrame(results)
    df_cost = pd.DataFrame(cost_rows)
    return df_results, df_cost


def _train_eval_ablation(df_train, df_test, group_features,
                          zscore_means, zscore_stds, failure_penalty,
                          fold_name, seed):
    """Train one ablation model and evaluate."""
    # Pivot to vector
    def pivot_vector(df, label_col):
        feat_cols = [c for c in SAMPLE_FEATURE_COLS if c not in SAMPLE_KEYS]
        sample_df = df[SAMPLE_KEYS + feat_cols].drop_duplicates(
            subset=SAMPLE_KEYS).reset_index(drop=True)
        pivot = df.pivot_table(
            index=SAMPLE_KEYS, columns='delta',
            values=label_col, aggfunc='first'
        ).reset_index()
        result = pivot[SAMPLE_KEYS].merge(sample_df, on=SAMPLE_KEYS, how='left')
        Y = np.full((len(pivot), N_DELTAS), np.nan)
        for j, d in enumerate(DELTA_GRID):
            if d in pivot.columns:
                Y[:, j] = pivot[d].values
        Y = np.where(np.isnan(Y), failure_penalty, Y)
        assert len(result) == Y.shape[0]
        return result, Y

    train_samples, Y_train = pivot_vector(df_train, 'loss_filled')
    test_samples, Y_test = pivot_vector(df_test, 'loss_filled')

    # Build feature matrix for this group
    zscore_subset = [c for c in FEATURE_COLS_ZSCORE if c in group_features]
    raw_subset = [c for c in FEATURE_COLS_RAW if c in group_features]

    def build_X(df_samples):
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
        return np.column_stack(cols).astype(np.float32) if cols else \
            np.zeros((len(df_samples), 0), dtype=np.float32)

    X_train = build_X(train_samples)
    X_test = build_X(test_samples)

    if X_train.shape[1] == 0:
        return {
            'fold': fold_name, 'feature_group': group_features[0] if group_features else 'empty',
            'seed': seed, 'pooled_J1': float('nan'), 'n_samples': 0,
            'error': 'no features'
        }

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

    Y_pred = target_scaler.inverse_transform(model.predict(X_test))
    Y_pred = np.clip(Y_pred, 0, None)

    # Evaluate
    best_idx = np.argmin(Y_pred, axis=1)
    true_losses = Y_test[np.arange(len(Y_test)), best_idx]
    j1 = math.sqrt(np.mean(true_losses))

    # Per-n
    per_n = {}
    test_n_values = test_samples['n'].values
    for n_val in sorted(np.unique(test_n_values)):
        mask = test_n_values == n_val
        if mask.sum() > 0:
            per_n[int(n_val)] = math.sqrt(np.mean(true_losses[mask]))

    # Endpoint rate
    sel_deltas = np.array([DELTA_GRID[i] for i in best_idx])
    p_extreme = float(np.isin(sel_deltas, [0.00, 0.02, 0.48, 0.50]).mean())

    # Near-optimal
    oracle_min = np.min(Y_test, axis=1)
    regret = true_losses - oracle_min
    rel_regret = np.where(oracle_min > 1e-12, regret / oracle_min, regret)
    near_rates = {f'near_{eps}': float(np.mean(rel_regret <= eps)) for eps in NEAR_OPTIMAL_EPS}

    group_label = group_features[0] if len(group_features) <= 1 else group_name_label(group_features)
    return {
        'fold': fold_name,
        'feature_group': group_label,
        'n_features': len(group_features),
        'seed': seed,
        'pooled_J1': j1,
        'n_samples': len(test_samples),
        'n_iter': model.n_iter_,
        'endpoint_rate': p_extreme,
        'near_1pct': near_rates['near_0.01'],
        'near_2pct': near_rates['near_0.02'],
        'near_5pct': near_rates['near_0.05'],
        'mean_regret': float(np.mean(regret)),
        **{f'J1_n{n_val}': per_n.get(n_val, float('nan')) for n_val in N_GRID},
    }


def group_name_label(features):
    """Convert feature list to group name."""
    for name, group in ABLATION_GROUPS.items():
        if group == features:
            return name
    return 'unknown'


# ============================================================
# E4b/E4c: Reference evaluation
# ============================================================

def evaluate_references(df_mc_new, label):
    """Evaluate Default/L1/L2/L3/L4/L5/L6 on new MC data.

    L1: global best constant delta on THIS data.
    L2: per-n best delta on THIS data.
    L3: per-beta best delta.
    L4: per-(beta,n) best delta.
    L5: per-(beta,gamma_over_eta,n) best delta.
    L6: per-sample hindsight best delta.
    """
    log(f"=== {label}: Reference Evaluation ===")

    df = compute_loss(df_mc_new)
    df_valid = df.dropna(subset=['loss']).copy()

    if len(df_valid) == 0:
        log(f"  WARNING: No valid rows for {label}!")
        return pd.DataFrame(), {}

    # Compute reference delta tables from THIS data
    # Default
    default_delta = DEFAULT_DELTA

    # L1: global best
    global_loss = df_valid.groupby('delta')['loss'].apply(
        lambda x: np.sqrt(np.nanmean(x)))
    l1_delta = float(global_loss.idxmin())

    # L2: per-n best
    l2_table = {}
    for n_val in df_valid['n'].unique():
        df_n = df_valid[df_valid['n'] == n_val]
        loss_by_d = df_n.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
        l2_table[int(n_val)] = float(loss_by_d.idxmin())

    # L3: per-beta best
    l3_table = {}
    for b_val in df_valid['beta'].unique():
        df_b = df_valid[df_valid['beta'] == b_val]
        loss_by_d = df_b.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
        l3_table[float(b_val)] = float(loss_by_d.idxmin())

    # L4: per-(beta,n) best
    l4_table = {}
    for b_val in df_valid['beta'].unique():
        for n_val in df_valid[df_valid['beta'] == b_val]['n'].unique():
            df_bn = df_valid[(df_valid['beta'] == b_val) & (df_valid['n'] == n_val)]
            loss_by_d = df_bn.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
            l4_table[(float(b_val), int(n_val))] = float(loss_by_d.idxmin())

    # L5: per-(beta,gamma_over_eta,n) best
    l5_table = {}
    for (b_val, goe_val, n_val), grp in df_valid.groupby(['beta', 'gamma_over_eta', 'n']):
        loss_by_d = grp.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
        l5_table[(float(b_val), float(goe_val), int(n_val))] = float(loss_by_d.idxmin())

    # Build per-sample evaluation
    sample_keys = (
        df_valid[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']]
        .drop_duplicates()
        .sort_values(['beta', 'gamma_over_eta', 'n', 'repeat_id'])
        .reset_index(drop=True)
    )

    results = []
    endpoint_rows = []
    near_opt_rows = []

    for _, srow in sample_keys.iterrows():
        beta = float(srow['beta'])
        eta = float(srow['eta'])
        gamma = float(srow['gamma'])
        goe = float(srow['gamma_over_eta'])
        n_val = int(srow['n'])
        rid = int(srow['repeat_id'])

        # Get this sample's loss curve
        sample_df = df_valid[
            (df_valid['beta'] == beta) &
            (df_valid['gamma_over_eta'] == goe) &
            (df_valid['n'] == n_val) &
            (df_valid['repeat_id'] == rid)
        ].sort_values('delta')

        if len(sample_df) != N_DELTAS:
            continue

        losses = sample_df['loss'].values
        delta_values = sample_df['delta'].values

        # L6 hindsight
        l6_idx = int(np.argmin(losses))

        # Evaluate each reference
        refs = {
            'Default': (delta_values == default_delta),
            'L1': (delta_values == l1_delta),
            'L2': (delta_values == l2_table.get(n_val, l1_delta)),
            'L3': (delta_values == l3_table.get(beta, l1_delta)),
            'L4': (delta_values == l4_table.get((beta, n_val), l1_delta)),
            'L5': (delta_values == l5_table.get((beta, goe, n_val), l1_delta)),
            'L6-hindsight': np.arange(N_DELTAS) == l6_idx,
        }

        oracle_min = float(losses[l6_idx])

        for ref_name, ref_mask in refs.items():
            idx = np.where(ref_mask)[0]
            if len(idx) == 0:
                continue
            sel_idx = idx[0]
            sel_loss = float(losses[sel_idx])
            sel_delta = float(delta_values[sel_idx])

            regret = sel_loss - oracle_min
            rel_regret = regret / oracle_min if oracle_min > 1e-12 else regret

            results.append({
                'track': label,
                'model': ref_name,
                'beta': beta,
                'gamma_over_eta': goe,
                'n': n_val,
                'repeat_id': rid,
                'selected_delta': sel_delta,
                'true_loss': sel_loss,
                'oracle_min': oracle_min,
                'regret': regret,
                'rel_regret': rel_regret,
            })

            # Endpoint
            p_extreme = sel_delta in [0.00, 0.02, 0.48, 0.50]
            endpoint_rows.append({
                'track': label,
                'model': ref_name,
                'beta': beta,
                'gamma_over_eta': goe,
                'n': n_val,
                'is_extreme': p_extreme,
            })

            # Near-optimal
            near_opt_rows.append({
                'track': label,
                'model': ref_name,
                'beta': beta,
                'gamma_over_eta': goe,
                'n': n_val,
                'near_1pct': int(rel_regret <= 0.01),
                'near_2pct': int(rel_regret <= 0.02),
                'near_5pct': int(rel_regret <= 0.05),
            })

    df_results = pd.DataFrame(results)

    # Aggregate
    summary = {}
    if len(df_results) > 0:
        for model in df_results['model'].unique():
            sub = df_results[df_results['model'] == model]
            j1 = math.sqrt(sub['true_loss'].mean())
            per_n = {}
            for n_val in sorted(sub['n'].unique()):
                sub_n = sub[sub['n'] == n_val]
                per_n[int(n_val)] = math.sqrt(sub_n['true_loss'].mean())

            summary[model] = {
                'pooled_J1': j1,
                'n_samples': len(sub),
                'mean_regret': float(sub['regret'].mean()),
                'per_n_J1': per_n,
            }

    log(f"  {len(df_results)} evaluation rows, {len(summary)} models")
    for model, s in summary.items():
        log(f"    {model}: J1={s['pooled_J1']:.6f}")

    return df_results, summary


# ============================================================
# E4d: Selector extrapolation diagnostic
# ============================================================

def run_e4d(df_mc, df_boundary_feat, df_offgrid_feat,
            df_boundary_loss, df_offgrid_loss):
    """Train Vector-MLP-L6 on main grid, evaluate on boundary/offgrid.

    This is a diagnostic — not deployment proof.
    """
    log("=== E4d: Selector Extrapolation Diagnostic ===")

    # Build features for main grid
    df_feat = build_feature_table_from_mc(df_mc)
    merge_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    df_merged = df_mc.merge(df_feat, on=merge_keys, how='left', suffixes=('', '_feat'))
    for col in list(df_merged.columns):
        if col.endswith('_feat'):
            df_merged.drop(columns=col, inplace=True)
    df_merged = compute_loss(df_merged)

    # Use fold 1 as representative (same as E3b feature ablation baseline)
    folds = get_combo_split()
    fold = folds[0]
    train_combos = set(fold['train_combos'])

    def is_train(row):
        return (row['beta'], row['gamma_over_eta'], row['n']) in train_combos

    df_train = df_merged[df_merged.apply(is_train, axis=1)].copy()

    # Z-score from train
    zscore_means = {}
    zscore_stds = {}
    for col in FEATURE_COLS_ZSCORE:
        vals = df_train[col].astype(float)
        zscore_means[col] = float(vals.mean())
        zscore_stds[col] = float(vals.std(ddof=0))
        if zscore_stds[col] < 1e-12:
            zscore_stds[col] = 1.0

    train_valid = df_train['loss'].dropna()
    failure_penalty = float(np.nanpercentile(train_valid, 99))
    df_train['loss_filled'] = df_train['loss'].fillna(failure_penalty)

    # Pivot train to vector
    def pivot_vector(df, label_col):
        feat_cols_local = [c for c in SAMPLE_FEATURE_COLS if c not in SAMPLE_KEYS]
        sample_df = df[SAMPLE_KEYS + feat_cols_local].drop_duplicates(
            subset=SAMPLE_KEYS).reset_index(drop=True)
        pivot = df.pivot_table(
            index=SAMPLE_KEYS, columns='delta',
            values=label_col, aggfunc='first'
        ).reset_index()
        result = pivot[SAMPLE_KEYS].merge(sample_df, on=SAMPLE_KEYS, how='left')
        Y = np.full((len(pivot), N_DELTAS), np.nan)
        for j, d in enumerate(DELTA_GRID):
            if d in pivot.columns:
                Y[:, j] = pivot[d].values
        Y = np.where(np.isnan(Y), failure_penalty, Y)
        return result, Y

    train_samples, Y_train = pivot_vector(df_train, 'loss_filled')
    log(f"  Train samples: {len(train_samples)}")

    # Build X_train with full features
    cols = []
    for col in FEATURE_COLS_ZSCORE:
        vals = train_samples[col].astype(float).values
        cols.append((vals - zscore_means[col]) / max(zscore_stds[col], 1e-12))
    for col in FEATURE_COLS_RAW:
        cols.append(train_samples[col].astype(float).values)
    X_train = np.column_stack(cols).astype(np.float32)

    # Train with seed 42
    log("  Training Vector-MLP-L6 (seed=42)...")
    t0 = time.time()
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
            random_state=42, batch_size=MLP_BATCH_SIZE,
        )
        model.fit(X_train, Y_train_scaled)

    train_elapsed = time.time() - t0
    log(f"  Training done in {train_elapsed:.1f}s, n_iter={model.n_iter_}")

    # Evaluate on boundary and offgrid
    results = []

    for eval_label, df_eval_feat, df_eval_loss in [
        ("E4b_boundary", df_boundary_feat, df_boundary_loss),
        ("E4c_offgrid", df_offgrid_feat, df_offgrid_loss),
    ]:
        if df_eval_feat is None or len(df_eval_feat) == 0:
            continue

        # Build X_eval with same z-score params
        cols = []
        for col in FEATURE_COLS_ZSCORE:
            vals = df_eval_feat[col].astype(float).values
            cols.append((vals - zscore_means[col]) / max(zscore_stds[col], 1e-12))
        for col in FEATURE_COLS_RAW:
            cols.append(df_eval_feat[col].astype(float).values)
        X_eval = np.column_stack(cols).astype(np.float32)

        # Predict
        Y_pred = target_scaler.inverse_transform(model.predict(X_eval))
        Y_pred = np.clip(Y_pred, 0, None)

        # For each sample, select delta and look up true loss
        for i in range(len(df_eval_feat)):
            row = df_eval_feat.iloc[i]
            beta = float(row['beta'])
            goe = float(row['gamma_over_eta'])
            n_val = int(row['n'])
            rid = int(row['repeat_id'])

            best_delta_idx = int(np.argmin(Y_pred[i]))
            sel_delta = DELTA_GRID[best_delta_idx]

            # Look up true loss at selected delta
            match = df_eval_loss[
                (df_eval_loss['beta'] == beta) &
                (df_eval_loss['gamma_over_eta'] == goe) &
                (df_eval_loss['n'] == n_val) &
                (df_eval_loss['repeat_id'] == rid) &
                (df_eval_loss['delta'] == sel_delta)
            ]
            if len(match) > 0:
                true_loss = float(match.iloc[0]['loss'])
                if np.isnan(true_loss):
                    true_loss = failure_penalty
            else:
                true_loss = failure_penalty

            results.append({
                'track': eval_label,
                'model': 'Vector-MLP-L6-extrapolation',
                'beta': beta,
                'gamma_over_eta': goe,
                'n': n_val,
                'repeat_id': rid,
                'selected_delta': sel_delta,
                'true_loss': true_loss,
            })

    df_results = pd.DataFrame(results)
    if len(df_results) > 0:
        for track in df_results['track'].unique():
            sub = df_results[df_results['track'] == track]
            j1 = math.sqrt(sub['true_loss'].mean())
            log(f"  {track} Vector-MLP-L6 extrapolation J1={j1:.6f}")

    return df_results, train_elapsed


# ============================================================
# Main
# ============================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(
        description="Study/01 Formal E4 Validation Analysis")
    parser.add_argument(
        '--tracks', type=str, default='e4a,e4b,e4c,e4d',
        help='Comma-separated tracks to run (e.g. "e4b,e4c"). '
             'Default: all tracks.')
    args = parser.parse_args()

    requested_tracks = set(t.strip().lower() for t in args.tracks.split(','))
    valid_tracks = {'e4a', 'e4b', 'e4c', 'e4d'}
    invalid = requested_tracks - valid_tracks
    if invalid:
        print(f"ERROR: Unknown tracks: {invalid}. Valid: {valid_tracks}")
        sys.exit(1)

    # ============================================================
    # Pre-validate required inputs for requested tracks (fail-closed)
    # ============================================================
    required_inputs = {
        'e4a': [MC_SCAN_PATH],
        'e4b': [BOUNDARY_PATH],
        'e4c': [OFFGRID_PATH],
        'e4d': [MC_SCAN_PATH, BOUNDARY_PATH, OFFGRID_PATH],
    }
    try:
        preflight_check_inputs(requested_tracks, required_inputs)
    except PreflightError as e:
        print(f"ERROR: {e}")
        print("Aborting before any output is produced.")
        sys.exit(1)

    log("=" * 70)
    log("Study/01 Formal E4 — Validation Analysis")
    log(f"Started: {now_iso()}")
    log(f"Output: {E4_OUTPUT_DIR}")
    log(f"Tracks requested: {sorted(requested_tracks)}")
    log("=" * 70)

    overall_t0 = time.time()
    all_cost = []
    cost_e4a = pd.DataFrame()  # default empty for cost report logic

    # Track status tracking for accurate summary semantics
    track_status = {}
    for t in valid_tracks:
        if t in requested_tracks:
            track_status[t] = {'requested': True, 'status': 'pending'}
        else:
            track_status[t] = {'requested': False, 'status': 'not_requested'}

    # --- Load existing MC data ---
    log("Loading main-grid MC data...")
    df_mc = pd.read_csv(MC_SCAN_PATH)
    log(f"  Loaded: {len(df_mc)} rows")

    with open(MC_MANIFEST_PATH) as f:
        mc_manifest = json.load(f)

    # --- Check boundary/offgrid data availability ---
    # (Required inputs already validated above for requested tracks.)
    has_boundary = os.path.exists(BOUNDARY_PATH)
    has_offgrid = os.path.exists(OFFGRID_PATH)

    df_boundary = None
    df_offgrid = None

    if has_boundary:
        df_boundary = pd.read_csv(BOUNDARY_PATH)
        log(f"  Boundary data: {len(df_boundary)} rows")

    if has_offgrid:
        df_offgrid = pd.read_csv(OFFGRID_PATH)
        log(f"  Off-grid data: {len(df_offgrid)} rows")

    # --- E4a: Feature ablation ---
    df_e4a = pd.DataFrame()
    if 'e4a' in requested_tracks:
        e4a_t0 = time.time()
        df_e4a, cost_e4a = run_e4a(df_mc)
        e4a_elapsed = time.time() - e4a_t0
        log(f"E4a total: {e4a_elapsed:.1f}s")
        all_cost.append({'track': 'E4a', 'elapsed_s': e4a_elapsed, 'note': 'feature ablation'})
        track_status['e4a']['status'] = 'completed'

        # Save E4a
        e4a_path = os.path.join(E4_OUTPUT_DIR, "E4a_feature_ablation.csv")
        df_e4a.to_csv(e4a_path, index=False)
        log(f"  Saved: {e4a_path}")
    else:
        log("E4a SKIPPED (not in --tracks)")

    # --- E4b: Boundary reference evaluation ---
    df_e4b = pd.DataFrame()
    e4b_summary = {}
    if 'e4b' in requested_tracks and df_boundary is not None:
        e4b_t0 = time.time()
        df_e4b, e4b_summary = evaluate_references(df_boundary, "E4b")
        e4b_elapsed = time.time() - e4b_t0
        e4b_path = os.path.join(E4_OUTPUT_DIR, "E4b_boundary_reference.csv")
        df_e4b.to_csv(e4b_path, index=False)
        log(f"  Saved: {e4b_path}")
        all_cost.append({'track': 'E4b', 'elapsed_s': e4b_elapsed, 'note': 'boundary reference evaluation'})
        track_status['e4b']['status'] = 'completed'
    elif 'e4b' not in requested_tracks:
        log("E4b SKIPPED (not in --tracks)")

    # --- E4c: Off-grid reference evaluation ---
    df_e4c = pd.DataFrame()
    e4c_summary = {}
    if 'e4c' in requested_tracks and df_offgrid is not None:
        e4c_t0 = time.time()
        df_e4c, e4c_summary = evaluate_references(df_offgrid, "E4c")
        e4c_elapsed = time.time() - e4c_t0
        e4c_path = os.path.join(E4_OUTPUT_DIR, "E4c_offgrid_reference.csv")
        df_e4c.to_csv(e4c_path, index=False)
        log(f"  Saved: {e4c_path}")
        all_cost.append({'track': 'E4c', 'elapsed_s': e4c_elapsed, 'note': 'offgrid reference evaluation'})
        track_status['e4c']['status'] = 'completed'
    elif 'e4c' not in requested_tracks:
        log("E4c SKIPPED (not in --tracks)")

    # --- E4d: Selector extrapolation diagnostic ---
    df_e4d = pd.DataFrame()
    e4d_train_time = 0
    e4d_skip = False

    if 'e4d' not in requested_tracks:
        log("E4d SKIPPED (not in --tracks)")
        # track_status['e4d'] already set to not_requested
    elif df_boundary is not None and df_offgrid is not None:
        try:
            # Build feature tables for boundary and offgrid
            boundary_combos = [(cid, b, g, n) for cid, b, g, n in E4B_BOUNDARY_COMBOS]
            offgrid_combos = [(cid, b, g, n) for cid, b, g, n in E4C_OFFGRID_COMBOS]

            # Use R from the actual data
            r_boundary = df_boundary['repeat_id'].max() + 1
            r_offgrid = df_offgrid['repeat_id'].max() + 1

            df_boundary_feat = build_feature_table_for_combos(boundary_combos)
            df_offgrid_feat = build_feature_table_for_combos(offgrid_combos)

            # Compute loss for boundary/offgrid
            df_boundary_loss = compute_loss(df_boundary)
            df_offgrid_loss = compute_loss(df_offgrid)

            df_e4d, e4d_train_time = run_e4d(
                df_mc, df_boundary_feat, df_offgrid_feat,
                df_boundary_loss, df_offgrid_loss
            )
            e4d_path = os.path.join(E4_OUTPUT_DIR, "E4d_selector_extrapolation.csv")
            df_e4d.to_csv(e4d_path, index=False)
            log(f"  Saved: {e4d_path}")
            all_cost.append({'track': 'E4d', 'elapsed_s': e4d_train_time,
                           'note': 'selector extrapolation diagnostic'})
            track_status['e4d']['status'] = 'completed'
        except Exception as e:
            log(f"  E4d FAILED: {type(e).__name__}: {e}")
            e4d_skip = True
            track_status['e4d']['status'] = 'skipped_error'
    else:
        log("  E4d SKIPPED: boundary/offgrid data not available")
        e4d_skip = True
        track_status['e4d']['status'] = 'skipped_no_input'

    # Write E4d skip reason ONLY if e4d was requested but could not run
    if e4d_skip and 'e4d' in requested_tracks:
        skip_path = os.path.join(E4_OUTPUT_DIR, "E4d_skip_reason.md")
        with open(skip_path, 'w') as f:
            f.write("# E4d Skip Reason\n\n")
            f.write("E4d selector extrapolation was skipped because ")
            if not has_boundary or not has_offgrid:
                f.write("boundary/offgrid MC data was not available.\n")
            else:
                f.write("of an execution error (see run log).\n")

    # --- Endpoint diagnostics ---
    endpoint_path = os.path.join(E4_OUTPUT_DIR, "endpoint_diagnostics.csv")
    endpoint_dfs = []
    for df_ref, label in [(df_e4b, 'E4b'), (df_e4c, 'E4c')]:
        if len(df_ref) > 0:
            for model in df_ref['model'].unique():
                sub = df_ref[df_ref['model'] == model]
                p_extreme = float(sub['selected_delta'].isin([0.00, 0.02, 0.48, 0.50]).mean())
                endpoint_dfs.append({
                    'track': label,
                    'model': model,
                    'pooled_P_extreme': p_extreme,
                    'n_samples': len(sub),
                })
    if endpoint_dfs:
        pd.DataFrame(endpoint_dfs).to_csv(endpoint_path, index=False)

    # --- Near-optimal diagnostics ---
    near_path = os.path.join(E4_OUTPUT_DIR, "near_optimal_diagnostics.csv")
    near_dfs = []
    for df_ref, label in [(df_e4b, 'E4b'), (df_e4c, 'E4c')]:
        if len(df_ref) > 0:
            for model in df_ref['model'].unique():
                sub = df_ref[df_ref['model'] == model]
                near_dfs.append({
                    'track': label,
                    'model': model,
                    'mean_regret': float(sub['regret'].mean()),
                    'mean_rel_regret': float(sub['rel_regret'].mean()),
                    'near_1pct_rate': float((sub['rel_regret'] <= 0.01).mean()),
                    'near_2pct_rate': float((sub['rel_regret'] <= 0.02).mean()),
                    'near_5pct_rate': float((sub['rel_regret'] <= 0.05).mean()),
                })
    if near_dfs:
        pd.DataFrame(near_dfs).to_csv(near_path, index=False)

    # --- Cost report ---
    cost_path = os.path.join(E4_OUTPUT_DIR, "cost_report.csv")
    # Add per-fold costs from E4a
    all_cost_rows = []
    all_cost_rows.extend([c for c in all_cost])
    # Add detailed E4a cost
    for _, row in cost_e4a.iterrows():
        all_cost_rows.append(dict(row))
    pd.DataFrame(all_cost_rows).to_csv(cost_path, index=False)

    # --- Split report (E4a-specific, only if E4a was requested) ---
    if 'e4a' in requested_tracks:
        split_path = os.path.join(E4_OUTPUT_DIR, "split_report.csv")
        split_rows = []
        for fold in get_combo_split():
            for combo in fold['test_combos']:
                split_rows.append({
                    'fold': fold['fold_name'],
                    'test_beta': combo[0],
                    'test_gamma_over_eta': combo[1],
                    'test_n': combo[2],
                })
        pd.DataFrame(split_rows).to_csv(split_path, index=False)

    # --- Manifest ---
    git_commit = get_git_info()
    total_elapsed = time.time() - overall_t0

    # Build output_files list dynamically: only files that were actually produced this run
    output_files_actual = []
    output_files_actual.append("cost_report.csv")
    if 'e4a' in requested_tracks and len(df_e4a) > 0:
        output_files_actual.append("E4a_feature_ablation.csv")
        output_files_actual.append("split_report.csv")
    if len(df_e4b) > 0:
        output_files_actual.append("E4b_boundary_reference.csv")
    if len(df_e4c) > 0:
        output_files_actual.append("E4c_offgrid_reference.csv")
    if endpoint_dfs:
        output_files_actual.append("endpoint_diagnostics.csv")
    if near_dfs:
        output_files_actual.append("near_optimal_diagnostics.csv")
    if not e4d_skip and len(df_e4d) > 0:
        output_files_actual.append("E4d_selector_extrapolation.csv")
    elif e4d_skip and 'e4d' in requested_tracks:
        output_files_actual.append("E4d_skip_reason.md")

    # Use track-specific manifest/summary/run_log filenames when not all tracks are requested
    is_full_run = requested_tracks == valid_tracks
    if is_full_run:
        manifest_name = "manifest.json"
        summary_name = "summary.json"
        run_log_name = "run_log.txt"
    else:
        track_tag = "_".join(sorted(requested_tracks))
        manifest_name = f"manifest_{track_tag}.json"
        summary_name = f"summary_{track_tag}.json"
        run_log_name = f"run_log_{track_tag}.txt"

    output_files_actual.append(manifest_name)
    output_files_actual.append(summary_name)
    output_files_actual.append(run_log_name)

    manifest = {
        "run_id": "E4_formal_validation_v1",
        "created_at": now_iso(),
        "status": "FORMAL",
        "tracks_requested": sorted(requested_tracks),
        "is_full_run": is_full_run,
        "track_status": track_status,
        "code_entry": "code/run_E4_formal_validation.py",
        "mc_generation_entry": "code/run_E4_mc_generation.py",
        "git_commit": git_commit,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "input_data": {
            "mc_scan_path": MC_SCAN_PATH,
            "mc_manifest": mc_manifest.get("run_id", "unknown"),
            "mc_git_commit": mc_manifest.get("git_commit", "unknown"),
            "boundary_path": BOUNDARY_PATH,
            "offgrid_path": OFFGRID_PATH,
            "mc_seed_namespace": mc_manifest.get("seed_namespace", SEED_NAMESPACE),
        },
        "method_versions": {
            "mdm": {
                "source": "python/methods/mdm.py",
                "class": "MDM",
                "run_signature": "run(offset: float, gamma_steps=60, rank_method='bernard')",
            },
            "sample": {
                "source": "python/studies/common/sample.py",
                "function": "generate_sample(beta, eta, gamma, n, repeat_id, seed)",
            },
            "mlp": {
                "class": "sklearn.neural_network.MLPRegressor",
                "hidden_layer_sizes": list(MLP_HIDDEN_LAYERS),
                "max_iter": MLP_MAX_ITER,
                "early_stopping": True,
            },
        },
        "parameter_grids": {
            "e4a_main_grid": {
                "beta": BETA_GRID,
                "eta": ETA_GRID,
                "gamma_over_eta": GAMMA_OVER_ETA_GRID,
                "n": N_GRID,
            },
            "e4b_boundary_combos": [
                {"id": cid, "beta": b, "gamma_over_eta": g, "n": n}
                for cid, b, g, n in E4B_BOUNDARY_COMBOS
            ],
            "e4c_offgrid_combos": [
                {"id": cid, "beta": b, "gamma_over_eta": g, "n": n}
                for cid, b, g, n in E4C_OFFGRID_COMBOS
            ],
        },
        "delta_grid": DELTA_GRID,
        "repeats": {
            "e4a": R_MAIN,
            "e4b": "R=500 (from mc_generation)",
            "e4c": "R=500 (from mc_generation)",
        },
        "seeds": STABILITY_SEEDS,
        "metrics_contract": {
            "J1": "sqrt(mean_i[((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2])",
        },
        "feature_contract": {
            "vector_input": SAMPLE_FEATURE_COLS,
            "banned_fields": list(BANNED_FIELDS),
            "zscore_applied": FEATURE_COLS_ZSCORE,
            "zscore_source": "training_set_only",
            "raw_passthrough": FEATURE_COLS_RAW,
        },
        "total_elapsed_s": total_elapsed,
        "output_files": output_files_actual,
        "notes": [
            "E4a uses existing main-grid MC data (read-only).",
            "E4b/E4c use new MDM risk curves generated by run_E4_mc_generation.py.",
            "E4d is a diagnostic, not a deployment-ready continuous-space proof.",
            "E4b uses Option C: reference-only evaluation at boundary (no NN deployment).",
            "E4c is evaluation-only. Continuous-space training is E3c.",
        ],
    }

    # output_files_actual already includes E4d outputs if applicable

    with open(os.path.join(E4_OUTPUT_DIR, manifest_name), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)

    # --- Summary ---
    summary = {
        "run_id": manifest["run_id"],
        "created_at": manifest["created_at"],
        "status": "FORMAL",
        "total_elapsed_s": total_elapsed,
        "e4a_summary": {},
        "e4b_summary": e4b_summary,
        "e4c_summary": e4c_summary,
        "track_status": track_status,
    }

    # E4a aggregate: mean/std across seeds per group
    if len(df_e4a) > 0:
        for group in df_e4a['feature_group'].unique():
            sub = df_e4a[df_e4a['feature_group'] == group]
            j1_values = sub['pooled_J1'].dropna().values
            if len(j1_values) > 0:
                summary["e4a_summary"][group] = {
                    "mean_J1": float(np.mean(j1_values)),
                    "std_J1": float(np.std(j1_values)),
                    "n_runs": len(j1_values),
                    "mean_endpoint_rate": float(sub['endpoint_rate'].mean()),
                    "mean_near_5pct": float(sub['near_5pct'].mean()),
                }

    with open(os.path.join(E4_OUTPUT_DIR, summary_name), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    # --- Run log ---
    with open(os.path.join(E4_OUTPUT_DIR, run_log_name), 'w', encoding='utf-8') as f:
        f.write(f"Study/01 Formal E4 Validation Analysis\n")
        f.write(f"Tracks: {sorted(requested_tracks)}\n")
        f.write(f"Started: {manifest['created_at']}\n")
        f.write(f"Git commit: {git_commit}\n")
        f.write(f"Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)\n\n")
        for line in log_lines:
            f.write(line + "\n")

    log(f"\n{'='*70}")
    log(f"FORMAL E4 ANALYSIS COMPLETE")
    log(f"  Total elapsed: {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")
    log(f"  Output: {E4_OUTPUT_DIR}")
    log(f"{'='*70}")


if __name__ == "__main__":
    main()
