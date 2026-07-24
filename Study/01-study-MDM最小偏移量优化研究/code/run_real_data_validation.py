"""
Study/01 — Real Data Holdout Validation (R3) — P7 Full Implementation

Per frozen contract P6_FROZEN_CONTRACT.md (v1.1-FROZEN-REVISED):

  - Seed-based split generation: n={7,10,20}, 500 repeats each, without replacement.
  - All methods (Default, L2, NN) share identical train/holdout indices.
  - Default δ=0.1; L2 uses frozen per-n deltas from E1/E2 cross-fit.
  - 15 NN selectors retrained per E4d contract (5 folds × 3 seeds),
    training data and scalers from main-grid train folds ONLY.
  - Primary metric: one-sample two-sided KS distance with piecewise 3P Weibull CDF.
  - Failure handling: D=1, failed=True, recorded reason — never silently dropped.
  - Per-model aggregation first, then cross-model distribution.
  - Output: real_holdout_results.csv (25500 rows), summary, model stability, manifest, run log.

Inputs:
  - Real dataset: lifetimes.csv + BIRNSAUN.DAT (SHA256 verified)
  - Frozen E3b/E4d contract NN config
  - Frozen main-grid L2 delta table
  - Authoritative main-grid MC chunks (for NN training only)

Outputs (written to OUTPUT_DIR/<dataset_id>/):
  - real_holdout_results.csv       — per-repeat, per-method rows (25500 expected)
  - real_holdout_summary.json      — aggregate metrics
  - real_nn_model_stability.csv    — 15 model-level rows
  - real_data_manifest.json        — provenance
  - run_log.txt                    — timestamped execution log
"""

import sys
import os
import json
import hashlib
import time
import math
import warnings
import subprocess
import re
import tempfile
import importlib.util
from datetime import datetime, timezone
from itertools import product

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

# ═══════════════════════════════════════════════════════════════
# Path setup
# ═══════════════════════════════════════════════════════════════

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

from config import (
    BETA_GRID, ETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID,
    DELTA_GRID, DEFAULT_DELTA, SEED_NAMESPACE,
    ARTIFACTS_DIR, SHARED_DATA_DIR, R_MAIN,
)
from utils import now_iso
from studies.common.sample import generate_sample

# ── Real data gate ──
from real_data_gate import (
    run_real_data_gate, RealDataGateResult,
    MIN_UNCENSORED_LIFETIMES, WEIBULL_FIT_MIN_R2, _estimate_weibull_ols,
)

# ═══════════════════════════════════════════════════════════════
# Frozen constants (from P6_FROZEN_CONTRACT.md)
# ═══════════════════════════════════════════════════════════════

BASE_SEED = 20260725
TRAIN_N_VALUES = [7, 10, 20]
N_REPEATS = 500

# L2 frozen per-n deltas (from E1/E2 cross-fit, selected_deltas.csv)
L2_DELTAS = {7: 0.10, 10: 0.10, 20: 0.08}

# Tie tolerance for paired comparisons
TIE_TOLERANCE = 1e-9

# Failure penalty — D=1 for failed estimates
FAILURE_D = 1.0

# NN feature columns (same as E3b/E4d contract)
FEATURE_COLS_ZSCORE = [
    'x_min', 'x_max', 'range', 'Q1', 'Med', 'Q3', 'IQR', 'x_bar', 's'
]
FEATURE_COLS_RAW = ['n', 'CV', 'g1', 'g2']
SAMPLE_FEATURE_COLS = FEATURE_COLS_ZSCORE + FEATURE_COLS_RAW

# NN config (same as E3b/E4d)
MLP_HIDDEN_LAYERS = (256, 128, 64)
MLP_MAX_ITER = 300
MLP_BATCH_SIZE = 256
MLP_ALPHA = 1e-4
MLP_LR = 1e-3
MLP_VALIDATION_FRACTION = 0.15
MLP_N_ITER_NO_CHANGE = 20
STABILITY_SEEDS = [42, 2026, 3407]
N_FOLDS = 5
N_DELTAS = len(DELTA_GRID)
# FAILURE_PENALTY is computed per-fold as P99 of training loss (E4d contract).
# No fixed constant — see train_all_nn_selectors().

# Output columns for real_holdout_results.csv
RESULT_COLUMNS = [
    'train_n', 'repeat_index', 'method', 'model_id',
    'delta_used',
    'beta_hat', 'eta_hat', 'gamma_hat', 'r_squared', 'mdm_status',
    'D', 'failed', 'failure_reason',
    'support_set_violation',
    'param_dist_beta', 'param_dist_eta',
]

# Output directory default (overridable for tests/smoke)
DEFAULT_OUTPUT_DIR = os.path.join(
    ARTIFACTS_DIR, "real_data", "nist-6061-t6-fatigue"
)

# ═══════════════════════════════════════════════════════════════
# P8a authorization (narrow, auditable — only in generation commit)
# ═══════════════════════════════════════════════════════════════

# P6 placeholder guard: RELEASED after P7 Codex APPROVE (d619a40).
# This guard served its purpose during P7 implementation to prevent
# accidental formal execution. Now set to False.
_P6_PLACEHOLDER_GUARD = False

# P8a formal authorization: NARROW, AUDITABLE, SINGLE-COMMIT scope.
# Set to True ONLY in the P8a generation commit. This authorizes
# exactly one formal run against the frozen P6 contract.
# Tests call run_pipeline() directly and are not affected.
# There is NO CLI flag, NO bypass_guard parameter, NO hidden entry point.
_P8A_FORMAL_AUTHORIZED = True

# P7 APPROVE record that must exist before P8a formal run.
_P7_APPROVE_RECORD = os.path.join(
    PROJECT_ROOT, "coworker", "reviews",
    "2026-07-25-study01xu-p7-codex-approve.md"
)

log_lines = []


def log(msg):
    ts = datetime.now().strftime('%H:%M:%S')
    line = f"[{ts}] {msg}"
    # Encode-replace to survive GBK terminals on Windows
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode('ascii', errors='replace').decode('ascii'), flush=True)
    log_lines.append(line)


def get_git_info():
    """Return (short_commit, is_dirty) for PROJECT_ROOT.

    Uses 'git status --porcelain' for complete dirty detection covering
    unstaged, staged, and untracked files.
    """
    try:
        r = subprocess.run(
            ['git', 'rev-parse', '--short', 'HEAD'],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=10
        )
        commit = r.stdout.strip() if r.returncode == 0 else "UNKNOWN"
        r2 = subprocess.run(
            ['git', 'status', '--porcelain'],
            capture_output=True, text=True, cwd=PROJECT_ROOT, timeout=10
        )
        dirty = bool(r2.stdout.strip())
        return commit, dirty
    except Exception:
        return "UNKNOWN", True


# ═══════════════════════════════════════════════════════════════
# Seed and split generation
# ═══════════════════════════════════════════════════════════════

def make_seed(train_n, repeat_index):
    """Frozen seed derivation: base_seed + train_n * 10000 + repeat_index."""
    return BASE_SEED + train_n * 10000 + repeat_index


def generate_splits(n_total, train_n, n_repeats=N_REPEATS):
    """Generate deterministic train/holdout index splits.

    Returns list of (train_indices, holdout_indices) as numpy arrays.
    Seed = BASE_SEED + train_n * 10000 + repeat_index.
    """
    splits = []
    for rep in range(n_repeats):
        seed = make_seed(train_n, rep)
        rng = np.random.default_rng(seed)
        indices = rng.permutation(n_total)
        train_idx = np.sort(indices[:train_n])
        holdout_idx = np.sort(indices[train_n:])
        splits.append((train_idx, holdout_idx))
    return splits


# ═══════════════════════════════════════════════════════════════
# Feature computation from real data sample
# ═══════════════════════════════════════════════════════════════

def compute_sample_features(sample):
    """Compute 13 observable features from a real data sample.

    Same feature set as E3b/E4d: n, x_min, x_max, range, Q1, Med, Q3, IQR,
    x_bar, s, CV, g1, g2.
    """
    n = len(sample)
    s_sorted = np.sort(np.asarray(sample, dtype=float))
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
        g1 = float(np.sum(z ** 3) / n)
        g2 = float(np.sum(z ** 4) / n - 3.0)
    else:
        g1 = 0.0
        g2 = 0.0

    return {
        'n': n,
        'x_min': x_min, 'x_max': x_max, 'range': rng,
        'Q1': Q1, 'Med': Med, 'Q3': Q3, 'IQR': IQR,
        'x_bar': x_bar, 's': s, 'CV': CV, 'g1': g1, 'g2': g2,
    }


# ═══════════════════════════════════════════════════════════════
# Piecewise 3-parameter Weibull CDF
# ═══════════════════════════════════════════════════════════════

def weibull_cdf_piecewise(x, beta, eta, gamma):
    """Three-parameter Weibull CDF, piecewise per contract.

    F(y) = 0                                    if y <= gamma
    F(y) = 1 - exp(-((y - gamma) / eta)^beta)   if y > gamma

    This avoids illegal power operations when holdout values fall below
    the estimated location parameter.
    """
    x = np.asarray(x, dtype=float)
    result = np.zeros_like(x)
    mask = x > gamma
    if np.any(mask):
        z = (x[mask] - gamma) / eta
        # Guard against negative z (shouldn't happen due to mask, but be safe)
        z = np.maximum(z, 0.0)
        result[mask] = 1.0 - np.exp(-(z ** beta))
    return result


# ═══════════════════════════════════════════════════════════════
# One-sample two-sided KS distance
# ═══════════════════════════════════════════════════════════════

def one_sample_two_sided_ks(holdout, beta_hat, eta_hat, gamma_hat):
    """Compute one-sample two-sided KS distance.

    D = max_i { |F(y_(i)) - i/m|, |F(y_(i)) - (i-1)/m| }

    where:
      - y_(i) are sorted holdout values, i = 1..m (1-indexed)
      - F is the fitted piecewise 3P Weibull CDF
      - i/m is the right-continuous ECDF
      - (i-1)/m is the left-continuous ECDF
    """
    m = len(holdout)
    if m == 0:
        return 1.0
    y_sorted = np.sort(np.asarray(holdout, dtype=float))
    F_vals = weibull_cdf_piecewise(y_sorted, beta_hat, eta_hat, gamma_hat)
    i = np.arange(1, m + 1)
    ecdf_right = i / m
    ecdf_left = (i - 1) / m
    diffs_right = np.abs(F_vals - ecdf_right)
    diffs_left = np.abs(F_vals - ecdf_left)
    return float(np.maximum(np.max(diffs_right), np.max(diffs_left)))


# ═══════════════════════════════════════════════════════════════
# Failure detection (frozen per §5.1)
# ═══════════════════════════════════════════════════════════════

def detect_failure(beta, eta, gamma, status, train_sample, exception=None):
    """Check all frozen failure criteria.

    Returns (failed: bool, reason: str or None).
    """
    if exception is not None:
        return True, f"exception: {str(exception)[:200]}"
    if not status:
        return True, "mdm_status_false"
    if not np.isfinite(beta) or beta <= 0:
        return True, f"invalid_beta: {beta}"
    if not np.isfinite(eta) or eta <= 0:
        return True, f"invalid_eta: {eta}"
    if not np.isfinite(gamma):
        return True, f"invalid_gamma: {gamma}"
    train_min = float(np.min(train_sample))
    if gamma >= train_min:
        return True, f"support_set_violation_train: gamma={gamma} >= train_min={train_min}"
    if gamma < 0:
        return True, f"negative_gamma: {gamma}"
    return False, None


# ═══════════════════════════════════════════════════════════════
# Support-set violation (holdout)
# ═══════════════════════════════════════════════════════════════

def check_support_set_violation(holdout, gamma):
    """Return True if any holdout lifetime < gamma_hat."""
    return bool(np.any(np.asarray(holdout) < gamma))


# ═══════════════════════════════════════════════════════════════
# Parameter distance from large-sample reference
# ═══════════════════════════════════════════════════════════════

def param_distance_rel(beta_hat, eta_hat, beta_ref, eta_ref):
    """Relative absolute parameter distance from reference.

    Returns (dist_beta, dist_eta) where dist = |hat - ref| / ref.
    """
    dist_beta = abs(beta_hat - beta_ref) / beta_ref if beta_ref > 0 else float('inf')
    dist_eta = abs(eta_hat - eta_ref) / eta_ref if eta_ref > 0 else float('inf')
    return float(dist_beta), float(dist_eta)


# ═══════════════════════════════════════════════════════════════
# MDM estimation wrapper
# ═══════════════════════════════════════════════════════════════

def run_mdm_estimation(train_sample, delta):
    """Run MDM estimation with given delta offset.

    Returns (beta, eta, gamma, r_squared, status, exception).
    MDM.run() returns 5-tuple: (beta, eta, gamma, r_squared, status).
    """
    from methods.mdm import MDM
    exception = None
    try:
        mdm = MDM(train_sample)
        beta, eta, gamma, r2, status = mdm.run(offset=delta)
        beta = float(beta)
        eta = float(eta)
        gamma = float(gamma)
        r2 = float(r2)
        status = bool(status)
    except Exception as e:
        beta = float('nan')
        eta = float('nan')
        gamma = float('nan')
        r2 = float('nan')
        status = False
        exception = e
    return beta, eta, gamma, r2, status, exception


# ═══════════════════════════════════════════════════════════════
# NN Selector Training (from main-grid chunks only)
# ═══════════════════════════════════════════════════════════════

def get_combo_split():
    """Deterministic 5-fold combo-level split (same as E3b/E4d)."""
    combos = list(product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID))
    folds = []
    for fold_idx in range(N_FOLDS):
        test_combos = [c for i, c in enumerate(combos) if i % 5 == fold_idx]
        train_combos = [c for i, c in enumerate(combos) if i % 5 != fold_idx]
        folds.append({
            'fold_name': f'combo_fold_{fold_idx + 1}',
            'fold_idx': fold_idx,
            'train_combos': train_combos,
            'test_combos': test_combos,
        })
    return folds


def _load_main_grid_chunks(chunks_dir):
    """Load all 45 authoritative main-grid MDM chunks.

    Returns a concatenated DataFrame with columns:
    beta, eta, gamma, gamma_over_eta, n, repeat_id, delta,
    beta_hat, eta_hat, gamma_hat, converged, status
    """
    expected_units = list(product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID))
    # Build chunk path mapping
    pattern = re.compile(r'^chunk_(\d{4})_mdm\.csv$')
    chunk_map = {}
    for name in os.listdir(chunks_dir):
        m = pattern.fullmatch(name)
        if m:
            chunk_map[int(m.group(1))] = os.path.join(chunks_dir, name)

    if len(chunk_map) != len(expected_units):
        raise FileNotFoundError(
            f"Expected {len(expected_units)} chunks, found {len(chunk_map)}"
        )

    frames = []
    for chunk_id in range(len(expected_units)):
        if chunk_id not in chunk_map:
            raise FileNotFoundError(f"Missing chunk {chunk_id:04d}")
        df = pd.read_csv(chunk_map[chunk_id])
        frames.append(df)

    return pd.concat(frames, ignore_index=True)


def build_feature_table_from_mc(df_mc, seed_ns=SEED_NAMESPACE):
    """Build features from MC scan data by reconstructing samples."""
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
    log(f"  Features done in {time.time() - t0:.1f}s")
    return df_feat


def compute_loss(df):
    """Compute per-sample J1 loss."""
    r_beta = (df['beta_hat'] - df['beta']) / df['beta']
    r_eta = (df['eta_hat'] - df['eta']) / df['eta']
    r_gamma = (df['gamma_hat'] - df['gamma']) / df['eta']
    df = df.copy()
    df['loss'] = r_beta ** 2 + r_eta ** 2 + r_gamma ** 2
    df['loss'] = df['loss'].replace([np.inf, -np.inf], np.nan)
    return df


def _pivot_risk_vectors(df, label_col='loss', failure_penalty=None):
    """Pivot per-delta rows into 26-dim risk vectors (one per sample).

    failure_penalty is required — use per-fold P99 of training loss (E4d contract).
    """
    if failure_penalty is None:
        raise ValueError("failure_penalty is required (use per-fold P99 of training loss)")
    sample_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    feat_cols_local = [c for c in SAMPLE_FEATURE_COLS if c not in sample_keys]
    sample_df = df[sample_keys + feat_cols_local].drop_duplicates(
        subset=sample_keys).reset_index(drop=True)
    pivot = df.pivot_table(
        index=sample_keys, columns='delta',
        values=label_col, aggfunc='first'
    ).reset_index()
    result = pivot[sample_keys].merge(sample_df, on=sample_keys, how='left')
    Y = np.full((len(pivot), N_DELTAS), np.nan)
    for j, d in enumerate(DELTA_GRID):
        if d in pivot.columns:
            Y[:, j] = pivot[d].values
    Y = np.where(np.isnan(Y), failure_penalty, Y)
    return result, Y


def _fit_zscore_params(df_train):
    """Compute per-feature z-score parameters from training split only."""
    means = {}
    stds = {}
    for col in FEATURE_COLS_ZSCORE:
        vals = df_train[col].astype(float)
        means[col] = float(vals.mean())
        stds[col] = float(vals.std(ddof=0))
        if stds[col] < 1e-12:
            stds[col] = 1.0
    return means, stds


def _build_X_from_samples(samples_df, zscore_means, zscore_stds):
    """Build 13-dim feature matrix with z-score normalization applied."""
    cols = []
    for col in FEATURE_COLS_ZSCORE:
        vals = samples_df[col].astype(float).values
        cols.append((vals - zscore_means[col]) / max(zscore_stds[col], 1e-12))
    for col in FEATURE_COLS_RAW:
        cols.append(samples_df[col].astype(float).values)
    return np.column_stack(cols).astype(np.float32) if cols else \
        np.zeros((len(samples_df), 0), dtype=np.float32)


def _build_X_from_feature_dict(feat_dict, zscore_means, zscore_stds):
    """Build a single 13-dim feature vector from a feature dict."""
    vals = []
    for col in FEATURE_COLS_ZSCORE:
        v = (feat_dict[col] - zscore_means[col]) / max(zscore_stds[col], 1e-12)
        vals.append(v)
    for col in FEATURE_COLS_RAW:
        vals.append(feat_dict[col])
    return np.array(vals, dtype=np.float32).reshape(1, -1)


def _train_mlp(X_train, Y_train, seed):
    """Train one Vector-MLP-L6 model under frozen E3b config."""
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
    return model, target_scaler


def train_all_nn_selectors(chunks_dir):
    """Train all 15 NN selectors from main-grid train folds.

    Returns list of dicts, each with:
      fold_idx, seed, model, target_scaler, zscore_means, zscore_stds
    """
    log("Loading main-grid chunks for NN training...")
    df_mc = _load_main_grid_chunks(chunks_dir)
    log(f"  Loaded {len(df_mc)} rows from {len(df_mc['delta'].unique())} deltas")

    # Build feature table
    df_feat = build_feature_table_from_mc(df_mc)
    merge_keys = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
    df_merged = df_mc.merge(df_feat, on=merge_keys, how='left',
                            suffixes=('', '_feat'))
    for col in list(df_merged.columns):
        if col.endswith('_feat'):
            df_merged.drop(columns=col, inplace=True)
    df_merged = compute_loss(df_merged)

    # Ban fields that must never appear in model inputs
    banned = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'seed', 'repeat_id', 'combo_id'}
    assert not (set(SAMPLE_FEATURE_COLS) & banned), "Banned field in feature set!"

    folds = get_combo_split()
    selectors = []

    for fold in folds:
        fold_idx = fold['fold_idx']
        fold_name = fold['fold_name']
        train_combos = set(fold['train_combos'])

        # Filter to train combos ONLY
        df_train = df_merged[
            df_merged.apply(
                lambda r: (r['beta'], r['gamma_over_eta'], r['n']) in train_combos,
                axis=1
            )
        ].copy()
        log(f"  {fold_name}: {len(df_train)} train rows "
            f"({df_train['delta'].nunique()} deltas)")

        # Fit z-score params on train fold only
        zscore_means, zscore_stds = _fit_zscore_params(df_train)

        # Per-fold P99 failure penalty (E4d contract, NOT a fixed constant)
        train_valid_loss = df_train['loss'].dropna()
        failure_penalty = float(np.nanpercentile(train_valid_loss, 99))
        df_train['loss_filled'] = df_train['loss'].fillna(failure_penalty)
        log(f"    failure_penalty (P99)={failure_penalty:.4f}")

        # Pivot to 26-dim risk vectors using loss_filled
        samples_df, Y_train = _pivot_risk_vectors(
            df_train, label_col='loss_filled', failure_penalty=failure_penalty
        )

        # Build X matrix
        X_train = _build_X_from_samples(samples_df, zscore_means, zscore_stds)

        # Train 3 seeds
        for seed in STABILITY_SEEDS:
            log(f"    Training seed={seed}...")
            t0 = time.time()
            model, target_scaler = _train_mlp(X_train, Y_train, seed)
            elapsed = time.time() - t0
            log(f"    seed={seed} done in {elapsed:.1f}s "
                f"(iters={model.n_iter_}, loss={model.loss_:.6f})")

            selectors.append({
                'fold_idx': fold_idx,
                'fold_name': fold_name,
                'seed': seed,
                'model': model,
                'target_scaler': target_scaler,
                'zscore_means': zscore_means,
                'zscore_stds': zscore_stds,
                'failure_penalty': failure_penalty,
            })

    log(f"Trained {len(selectors)} NN selectors ({N_FOLDS} folds × "
        f"{len(STABILITY_SEEDS)} seeds)")
    return selectors


def predict_nn_delta(selector, feat_dict):
    """Predict delta for a real data sample using one NN selector.

    Returns selected_delta (float).
    """
    X = _build_X_from_feature_dict(
        feat_dict, selector['zscore_means'], selector['zscore_stds']
    )
    Y_pred = selector['target_scaler'].inverse_transform(
        selector['model'].predict(X)
    )
    Y_pred = np.clip(Y_pred, 0, None)
    best_idx = int(np.argmin(Y_pred[0]))
    return DELTA_GRID[best_idx]


# ═══════════════════════════════════════════════════════════════
# Per-model aggregation
# ═══════════════════════════════════════════════════════════════

def aggregate_per_model(df_results):
    """Compute per-model aggregated metrics from per-repeat results.

    For each (train_n, method, model_id) group, compute:
      - n_repeats, n_failed, failure_rate
      - mean_D, median_D, std_D
      - mean_support_set_violation_rate
      - mean_param_dist_beta, mean_param_dist_eta
    Returns DataFrame with one row per (train_n, method, model_id).
    """
    agg_rows = []
    group_cols = ['train_n', 'method', 'model_id']

    for (train_n, method, model_id), grp in df_results.groupby(group_cols):
        n_total = len(grp)
        n_failed = int(grp['failed'].sum())
        failure_rate = n_failed / n_total if n_total > 0 else 0.0

        D_vals = grp['D'].values
        mean_D = float(np.mean(D_vals))
        median_D = float(np.median(D_vals))
        std_D = float(np.std(D_vals, ddof=1)) if n_total > 1 else 0.0

        # Support-set violation: only compute rate on known (0/1) values
        ss_vals = grp['support_set_violation'].values
        ss_known = ss_vals[np.isfinite(ss_vals)]  # exclude NaN
        n_ss_unknown = int(np.sum(~np.isfinite(ss_vals)))
        ss_violation_rate = float(np.mean(ss_known)) if len(ss_known) > 0 else float('nan')

        param_dist_beta_vals = grp['param_dist_beta'].values
        param_dist_eta_vals = grp['param_dist_eta'].values
        finite_beta = param_dist_beta_vals[np.isfinite(param_dist_beta_vals)]
        finite_eta = param_dist_eta_vals[np.isfinite(param_dist_eta_vals)]

        agg_rows.append({
            'train_n': train_n,
            'method': method,
            'model_id': model_id,
            'n_repeats': n_total,
            'n_failed': n_failed,
            'failure_rate': failure_rate,
            'mean_D': mean_D,
            'median_D': median_D,
            'std_D': std_D,
            'mean_support_set_violation_rate': ss_violation_rate,
            'n_support_set_unknown': n_ss_unknown,
            'mean_param_dist_beta': float(np.mean(finite_beta)) if len(finite_beta) > 0 else float('nan'),
            'mean_param_dist_eta': float(np.mean(finite_eta)) if len(finite_eta) > 0 else float('nan'),
        })

    return pd.DataFrame(agg_rows)


def cross_model_distribution(model_agg_df):
    """Compute distribution of 15 model-level values.

    For NN methods, compute min, Q1, median, Q3, max, mean, std of the
    15 model-level values for each metric and train_n.
    """
    nn_df = model_agg_df[model_agg_df['method'] == 'nn'].copy()
    if len(nn_df) == 0:
        return pd.DataFrame()

    dist_rows = []
    metrics = ['median_D', 'mean_D', 'failure_rate',
               'mean_support_set_violation_rate', 'n_support_set_unknown',
               'mean_param_dist_beta', 'mean_param_dist_eta']

    for train_n, grp in nn_df.groupby('train_n'):
        for metric in metrics:
            vals = grp[metric].dropna().values
            if len(vals) == 0:
                continue
            dist_rows.append({
                'train_n': train_n,
                'metric': metric,
                'min': float(np.min(vals)),
                'Q1': float(np.percentile(vals, 25)),
                'median': float(np.median(vals)),
                'Q3': float(np.percentile(vals, 75)),
                'max': float(np.max(vals)),
                'mean': float(np.mean(vals)),
                'std': float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
            })

    return pd.DataFrame(dist_rows)


# ═══════════════════════════════════════════════════════════════
# Paired win/loss/tie computation
# ═══════════════════════════════════════════════════════════════

def compute_paired_wins(df_results, method_a, method_b):
    """Compute paired win/loss/tie rates between two methods.

    Uses tolerance epsilon = 1e-9 on D difference.
    Win rate = wins / (wins + losses + ties).
    """
    results = {}
    for train_n in TRAIN_N_VALUES:
        # For Default/L2 methods: single model_id per method
        a_rows = df_results[
            (df_results['train_n'] == train_n) &
            (df_results['method'] == method_a)
        ]
        b_rows = df_results[
            (df_results['train_n'] == train_n) &
            (df_results['method'] == method_b)
        ]

        if method_a == 'nn' or method_b == 'nn':
            # Handle NN separately: per-model paired wins
            continue

        # Match by repeat_index
        merged = a_rows[['repeat_index', 'D']].merge(
            b_rows[['repeat_index', 'D']],
            on='repeat_index', suffixes=('_a', '_b')
        )
        if len(merged) == 0:
            results[train_n] = {'wins': 0, 'losses': 0, 'ties': 0,
                                'win_rate': float('nan'), 'tie_rate': float('nan')}
            continue

        diff = merged['D_a'] - merged['D_b']
        wins = int((diff < -TIE_TOLERANCE).sum())
        losses = int((diff > TIE_TOLERANCE).sum())
        ties = int((np.abs(diff) <= TIE_TOLERANCE).sum())
        total = wins + losses + ties
        win_rate = wins / total if total > 0 else float('nan')
        tie_rate = ties / total if total > 0 else float('nan')

        results[train_n] = {
            'wins': wins, 'losses': losses, 'ties': ties,
            'total': total, 'win_rate': win_rate, 'tie_rate': tie_rate,
        }

    return results


def compute_nn_paired_wins(df_results, nn_model_id, method_b):
    """Paired win rate for one NN model vs another method.

    Returns (win_rate, tie_rate, wins, losses, ties) per train_n.
    """
    results = {}
    for train_n in TRAIN_N_VALUES:
        nn_rows = df_results[
            (df_results['train_n'] == train_n) &
            (df_results['method'] == 'nn') &
            (df_results['model_id'] == nn_model_id)
        ]
        b_rows = df_results[
            (df_results['train_n'] == train_n) &
            (df_results['method'] == method_b)
        ]

        merged = nn_rows[['repeat_index', 'D']].merge(
            b_rows[['repeat_index', 'D']],
            on='repeat_index', suffixes=('_nn', '_b')
        )
        if len(merged) == 0:
            results[train_n] = {'win_rate': float('nan'), 'tie_rate': float('nan')}
            continue

        diff = merged['D_nn'] - merged['D_b']
        wins = int((diff < -TIE_TOLERANCE).sum())
        losses = int((diff > TIE_TOLERANCE).sum())
        ties = int((np.abs(diff) <= TIE_TOLERANCE).sum())
        total = wins + losses + ties
        win_rate = wins / total if total > 0 else float('nan')
        tie_rate = ties / total if total > 0 else float('nan')

        results[train_n] = {
            'win_rate': win_rate, 'tie_rate': tie_rate,
            'wins': wins, 'losses': losses, 'ties': ties, 'total': total,
        }

    return results


# ═══════════════════════════════════════════════════════════════
# Large-sample reference fit
# ═══════════════════════════════════════════════════════════════

def compute_reference_fit(all_lifetimes):
    """OLS Weibull fit to all 101 lifetimes.

    This is the empirical reference, never called "true parameters."
    Returns (beta_ref, eta_ref, gamma_ref=0).
    """
    beta, eta, gamma = _estimate_weibull_ols(all_lifetimes)
    return beta, eta, gamma


# ═══════════════════════════════════════════════════════════════
# Input verification
# ═══════════════════════════════════════════════════════════════

def verify_input_hashes(data_dir):
    """Verify SHA256 of BIRNSAUN.DAT and lifetimes.csv against frozen values.

    Returns dict with verification results. Raises RuntimeError on mismatch.
    """
    frozen_birnsaun = (
        "7814c533818517d8b824c56213abac2b4076786a13a66d85a8481a32bbccf127"
    )
    frozen_lifetimes = (
        "43c85155bdfeafd21e2366610e88a3f4e1a09e36466fb22d34729dc60418ee12"
    )

    results = {}

    # Verify BIRNSAUN.DAT
    birnsaun_path = os.path.join(data_dir, "BIRNSAUN.DAT")
    if os.path.exists(birnsaun_path):
        with open(birnsaun_path, 'rb') as f:
            raw = f.read()
        # LF-normalize
        raw_lf = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        sha = hashlib.sha256(raw_lf).hexdigest()
        results['BIRNSAUN.DAT'] = {'sha256': sha, 'match': sha == frozen_birnsaun}
        if not results['BIRNSAUN.DAT']['match']:
            raise RuntimeError(
                f"BIRNSAUN.DAT SHA256 mismatch: got {sha}, expected {frozen_birnsaun}"
            )
    else:
        results['BIRNSAUN.DAT'] = {'sha256': None, 'match': False, 'missing': True}

    # Verify lifetimes.csv
    lifetimes_path = os.path.join(data_dir, "lifetimes.csv")
    if os.path.exists(lifetimes_path):
        with open(lifetimes_path, 'rb') as f:
            raw = f.read()
        raw_lf = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        sha = hashlib.sha256(raw_lf).hexdigest()
        results['lifetimes.csv'] = {'sha256': sha, 'match': sha == frozen_lifetimes}
        if not results['lifetimes.csv']['match']:
            raise RuntimeError(
                f"lifetimes.csv SHA256 mismatch: got {sha}, expected {frozen_lifetimes}"
            )
    else:
        raise FileNotFoundError(f"Missing lifetimes.csv in {data_dir}")

    return results


# ═══════════════════════════════════════════════════════════════
# Output protection
# ═══════════════════════════════════════════════════════════════

def check_output_safety(output_dir):
    """Fail-closed: raise RuntimeError if output_dir already contains P7 output files.

    Must be called BEFORE any heavy computation (training, estimation).
    """
    expected_files = [
        'real_holdout_results.csv',
        'real_holdout_summary.json',
        'real_nn_model_stability.csv',
        'real_data_manifest.json',
        'run_log.txt',
    ]
    existing = []
    for fname in expected_files:
        fpath = os.path.join(output_dir, fname)
        if os.path.exists(fpath):
            existing.append(fpath)
    if existing:
        raise RuntimeError(
            f"Output directory {output_dir} already contains P7 output files. "
            f"Refusing to overwrite formal artifacts: {existing}. "
            f"Move or remove them before re-running, or use a different output_dir."
        )
    return existing


def validate_preflight(data_dir, chunks_dir):
    """Fail-closed pre-flight validation. Raises RuntimeError on any failure.

    Checks (in order, least expensive first):
      1. BIRNSAUN.DAT present
      2. L2 delta table: exists, has n=7/10/20 with correct majority-vote deltas
      3. E4d manifest: exists, 5 folds × 3 seeds = 15 models, training contract
      4. All 45 main-grid chunks: identity, row count (R_MAIN × 26),
         metadata columns, delta grid, repeat structure
    """
    # 1. BIRNSAUN.DAT
    birnsaun_path = os.path.join(data_dir, "BIRNSAUN.DAT")
    if not os.path.exists(birnsaun_path):
        raise RuntimeError(f"Missing BIRNSAUN.DAT in {data_dir}")

    # 2. L2 delta table — verify all n=7/10/20 have correct deltas
    l2_path = os.path.join(ARTIFACTS_DIR, "E1_E2_crossfit", "selected_deltas.csv")
    if not os.path.exists(l2_path):
        raise RuntimeError(f"Missing L2 delta table: {l2_path}")
    df_l2 = pd.read_csv(l2_path)
    for n_val, expected_delta in L2_DELTAS.items():
        l2_rows = df_l2[(df_l2['layer'] == 'L2') & (df_l2['n'] == float(n_val))]
        if len(l2_rows) < 3:
            raise RuntimeError(
                f"L2 table: expected >=3 fold rows for n={n_val}, got {len(l2_rows)}"
            )
        # Majority vote: the frozen delta should be the most common value
        delta_counts = l2_rows['delta_star'].value_counts()
        majority_delta = float(delta_counts.index[0])
        if abs(majority_delta - expected_delta) > 1e-9:
            raise RuntimeError(
                f"L2 table n={n_val}: majority delta={majority_delta}, "
                f"expected frozen={expected_delta}"
            )

    # 3. E4d manifest
    e4d_path = os.path.join(ARTIFACTS_DIR, "E4_robustness", "manifest_e4d.json")
    if not os.path.exists(e4d_path):
        raise RuntimeError(f"Missing E4d manifest: {e4d_path}")
    with open(e4d_path, encoding='utf-8') as f:
        e4d = json.load(f)
    tc = e4d.get('training_contract', {})
    if tc.get('total_models') != 15:
        raise RuntimeError(f"E4d manifest: total_models={tc.get('total_models')}, expected 15")
    if tc.get('folds') != N_FOLDS:
        raise RuntimeError(f"E4d manifest: folds={tc.get('folds')}, expected {N_FOLDS}")
    if sorted(tc.get('seeds', [])) != sorted(STABILITY_SEEDS):
        raise RuntimeError(
            f"E4d manifest: seeds={tc.get('seeds')}, expected {STABILITY_SEEDS}"
        )
    if tc.get('training_data') != 'main_grid_train_combos_only':
        raise RuntimeError(
            f"E4d manifest: training_data={tc.get('training_data')}, "
            f"expected 'main_grid_train_combos_only'"
        )

    # 4. All 45 main-grid chunks — full structural + identity validation
    # Build expected parameter-unit order (same as _expected_main_chunk_units in E4d)
    expected_units = []
    for eta in ETA_GRID:
        for goe in GAMMA_OVER_ETA_GRID:
            gamma = goe * eta
            for beta in BETA_GRID:
                for n_val in N_GRID:
                    expected_units.append({
                        'beta': float(beta), 'eta': float(eta),
                        'gamma': float(gamma), 'gamma_over_eta': float(goe),
                        'n': int(n_val),
                    })

    pattern = re.compile(r'^chunk_(\d{4})_mdm\.csv$')
    chunk_map = {}
    for name in os.listdir(chunks_dir):
        m = pattern.fullmatch(name)
        if m:
            chunk_map[int(m.group(1))] = os.path.join(chunks_dir, name)

    expected_ids = set(range(len(expected_units)))
    actual_ids = set(chunk_map.keys())
    if actual_ids != expected_ids:
        missing = sorted(expected_ids - actual_ids)
        extra = sorted(actual_ids - expected_ids)
        msg = f"Chunk identity mismatch: expected 45 chunks (0-44)"
        if missing:
            msg += f", missing={missing}"
        if extra:
            msg += f", unexpected={extra}"
        raise RuntimeError(msg)

    required_cols = {'beta', 'eta', 'gamma', 'gamma_over_eta', 'n',
                     'repeat_id', 'delta', 'beta_hat', 'eta_hat', 'gamma_hat'}
    expected_rows_per_chunk = R_MAIN * len(DELTA_GRID)  # 1000 × 26 = 26000

    for chunk_id in sorted(actual_ids):
        chunk_path = chunk_map[chunk_id]
        df = pd.read_csv(chunk_path)
        # Column check
        missing = required_cols - set(df.columns)
        if missing:
            raise RuntimeError(f"Chunk {chunk_id:04d} missing columns: {missing}")
        # Row count
        if len(df) != expected_rows_per_chunk:
            raise RuntimeError(
                f"Chunk {chunk_id:04d}: {len(df)} rows, expected {expected_rows_per_chunk}"
            )
        # Chunk identity → frozen parameter unit mapping
        expected_unit = expected_units[chunk_id]
        meta = df[['beta', 'eta', 'gamma_over_eta', 'n']].drop_duplicates()
        if len(meta) != 1:
            raise RuntimeError(
                f"Chunk {chunk_id:04d}: expected 1 combo, got {len(meta)}"
            )
        actual = meta.iloc[0]
        for key in ['beta', 'gamma_over_eta', 'n']:
            if abs(float(actual[key]) - expected_unit[key]) > 1e-9:
                raise RuntimeError(
                    f"Chunk {chunk_id:04d}: {key} mismatch — "
                    f"expected {expected_unit[key]}, got {float(actual[key])}"
                )
        # Delta grid matches
        chunk_deltas = sorted(df['delta'].unique())
        if chunk_deltas != DELTA_GRID:
            raise RuntimeError(f"Chunk {chunk_id:04d}: delta grid mismatch")
        # Repeat IDs are 0..R_MAIN-1
        chunk_repeats = sorted(df['repeat_id'].unique())
        if chunk_repeats != list(range(R_MAIN)):
            raise RuntimeError(
                f"Chunk {chunk_id:04d}: repeat_id set mismatch "
                f"(min={min(chunk_repeats)}, max={max(chunk_repeats)}, "
                f"n_unique={len(chunk_repeats)})"
            )
        # Each (repeat_id, delta) pair appears exactly once
        n_pairs = len(df[['repeat_id', 'delta']].drop_duplicates())
        if n_pairs != len(df):
            raise RuntimeError(
                f"Chunk {chunk_id:04d}: duplicate (repeat_id, delta) pairs — "
                f"{len(df)} rows but only {n_pairs} unique pairs"
            )


def compute_frozen_config_sha256():
    """Return SHA256 of the frozen p6_frozen_config.json file bytes (LF-normalized)."""
    config_path = os.path.join(
        ARTIFACTS_DIR, "real_data", "p6_frozen_config.json"
    )
    if not os.path.exists(config_path):
        return None
    with open(config_path, 'rb') as f:
        raw = f.read()
    raw_lf = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
    return hashlib.sha256(raw_lf).hexdigest()


def compute_config_hash():
    """Deterministic hash of all frozen configuration parameters."""
    config_dict = {
        'base_seed': BASE_SEED,
        'train_n_values': TRAIN_N_VALUES,
        'n_repeats': N_REPEATS,
        'l2_deltas': {str(k): v for k, v in L2_DELTAS.items()},
        'default_delta': DEFAULT_DELTA,
        'tie_tolerance': TIE_TOLERANCE,
        'failure_D': FAILURE_D,
        'delta_grid': DELTA_GRID,
        'n_folds': N_FOLDS,
        'stability_seeds': STABILITY_SEEDS,
        'mlp_hidden_layers': list(MLP_HIDDEN_LAYERS),
        'mlp_max_iter': MLP_MAX_ITER,
        'mlp_batch_size': MLP_BATCH_SIZE,
        'mlp_alpha': MLP_ALPHA,
        'mlp_lr': MLP_LR,
        'mlp_validation_fraction': MLP_VALIDATION_FRACTION,
        'mlp_n_iter_no_change': MLP_N_ITER_NO_CHANGE,
        'feature_cols_zscore': FEATURE_COLS_ZSCORE,
        'feature_cols_raw': FEATURE_COLS_RAW,
        'contract_version': 'P6-v1.1-FROZEN-REVISED',
    }
    canonical = json.dumps(config_dict, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(canonical.encode('utf-8')).hexdigest()


def get_package_versions():
    """Return dict with Python, numpy, sklearn versions."""
    import sklearn
    return {
        'python': sys.version.split()[0],
        'numpy': np.__version__,
        'scikit_learn': sklearn.__version__,
    }


# ═══════════════════════════════════════════════════════════════
# Main pipeline
# ═══════════════════════════════════════════════════════════════

def run_pipeline(data_dir, output_dir=None, chunks_dir=None,
                 smoke_n_repeats=None, smoke_skip_nn=False):
    """Run the full P7 real data validation pipeline.

    Args:
        data_dir: Path to dataset directory with lifetimes.csv + source.json
        output_dir: Output directory (default: DEFAULT_OUTPUT_DIR)
        chunks_dir: Main-grid chunks directory for NN training
        smoke_n_repeats: If set, override N_REPEATS (for smoke testing)
        smoke_skip_nn: If True, skip NN training (for fast smoke tests)
    """
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    if chunks_dir is None:
        chunks_dir = os.path.join(SHARED_DATA_DIR, "chunks")

    n_repeats = smoke_n_repeats if smoke_n_repeats is not None else N_REPEATS

    os.makedirs(output_dir, exist_ok=True)

    log("=" * 70)
    log("Study/01 Real Data Holdout Validation — P7 Pipeline")
    log(f"Started: {now_iso()}")
    log(f"Data dir: {data_dir}")
    log(f"Output dir: {output_dir}")
    log(f"Chunks dir: {chunks_dir}")
    log(f"Repeats: {n_repeats} per train_n")
    log(f"Train n: {TRAIN_N_VALUES}")
    log("=" * 70)

    # ── Step 0: Fail-closed pre-flight ──
    log("Step 0: Pre-flight validation (fail-closed)...")

    # 0a: Verify input hashes
    hash_results = verify_input_hashes(data_dir)
    for k, v in hash_results.items():
        status = "MATCH" if v.get('match') else "MISSING/MISMATCH"
        log(f"  SHA256 {k}: {status}")
        if k == 'BIRNSAUN.DAT' and v.get('missing'):
            raise RuntimeError(f"Missing BIRNSAUN.DAT in {data_dir}")

    # 0b: Validate all required inputs exist and have correct structure
    validate_preflight(data_dir, chunks_dir)
    log("  Pre-flight: all inputs valid")

    # 0c: Fail-closed output protection — BEFORE any computation
    check_output_safety(output_dir)
    log("  Output safety: no conflicts")

    # ── Step 1: Gate check ──
    log("Step 1: Running admission gate...")
    gate = run_real_data_gate(data_dir)
    if not gate.passed:
        log(f"  GATE FAILED: {gate.reason}")
        gate_path = os.path.join(output_dir, "dataset-ineligible.md")
        with open(gate_path, 'w', encoding='utf-8') as f:
            f.write(f"# Dataset Ineligible\n\n{gate.reason}\n")
        log(f"  Saved: {gate_path}")
        return None
    log(f"  GATE PASSED: R^2={gate.diagnostics['r_squared']:.4f}")

    # ── Step 2: Load data ──
    log("Step 2: Loading lifetimes...")
    lifetimes = pd.read_csv(
        os.path.join(data_dir, 'lifetimes.csv')
    )['failure_time'].dropna().astype(float).values
    n_total = len(lifetimes)
    log(f"  Loaded {n_total} lifetimes")

    # ── Step 3: Large-sample reference fit ──
    log("Step 3: Computing large-sample reference fit...")
    beta_ref, eta_ref, gamma_ref = compute_reference_fit(lifetimes)
    log(f"  beta_ref={beta_ref:.4f}, eta_ref={eta_ref:.2f}, gamma_ref={gamma_ref}")

    # ── Step 4: Generate splits (shared by all methods) ──
    log("Step 4: Generating train/holdout splits...")
    all_splits = {}
    for train_n in TRAIN_N_VALUES:
        all_splits[train_n] = generate_splits(n_total, train_n, n_repeats)
        log(f"  n={train_n}: {len(all_splits[train_n])} splits generated")

    # ── Step 5: Pre-generate NN-delta predictions (if not skipping) ──
    nn_selectors = None
    if not smoke_skip_nn:
        log("Step 5: Training 15 NN selectors from main-grid chunks...")
        t0 = time.time()
        nn_selectors = train_all_nn_selectors(chunks_dir)
        log(f"  NN training complete in {time.time() - t0:.1f}s")
        # Fail-closed: must have exactly 15 selectors
        if len(nn_selectors) != 15:
            raise RuntimeError(
                f"Expected 15 NN selectors, got {len(nn_selectors)}"
            )
    else:
        log("Step 5: NN training SKIPPED (smoke_skip_nn=True)")

    # ── Step 6: Run all methods on all splits ──
    log("Step 6: Running methods on all splits...")
    all_rows = []
    total_splits = sum(len(v) for v in all_splits.values())
    done = 0

    for train_n in TRAIN_N_VALUES:
        splits = all_splits[train_n]
        l2_delta = L2_DELTAS[train_n]

        for rep_idx, (train_idx, holdout_idx) in enumerate(splits):
            train_sample = lifetimes[train_idx]
            holdout_sample = lifetimes[holdout_idx]
            train_min = float(np.min(train_sample))

            # Compute features from train data only (for NN)
            feats = compute_sample_features(train_sample)

            # ── Default (δ=0.1) ──
            beta_d, eta_d, gamma_d, r2_d, status_d, exc_d = \
                run_mdm_estimation(train_sample, DEFAULT_DELTA)
            failed_d, reason_d = detect_failure(
                beta_d, eta_d, gamma_d, status_d, train_sample, exc_d
            )
            if failed_d:
                D_d = FAILURE_D
            else:
                D_d = one_sample_two_sided_ks(
                    holdout_sample, beta_d, eta_d, gamma_d
                )
            ss_violation_d = check_support_set_violation(holdout_sample, gamma_d)
            dist_beta_d, dist_eta_d = param_distance_rel(
                beta_d, eta_d, beta_ref, eta_ref
            )
            all_rows.append({
                'train_n': train_n, 'repeat_index': rep_idx,
                'method': 'default', 'model_id': 'default',
                'delta_used': DEFAULT_DELTA,
                'beta_hat': beta_d, 'eta_hat': eta_d, 'gamma_hat': gamma_d,
                'r_squared': r2_d, 'mdm_status': int(status_d),
                'D': D_d, 'failed': failed_d, 'failure_reason': reason_d or '',
                'support_set_violation': int(ss_violation_d),
                'param_dist_beta': dist_beta_d, 'param_dist_eta': dist_eta_d,
            })

            # ── L2 (frozen per-n delta) ──
            beta_l2, eta_l2, gamma_l2, r2_l2, status_l2, exc_l2 = \
                run_mdm_estimation(train_sample, l2_delta)
            failed_l2, reason_l2 = detect_failure(
                beta_l2, eta_l2, gamma_l2, status_l2, train_sample, exc_l2
            )
            if failed_l2:
                D_l2 = FAILURE_D
            else:
                D_l2 = one_sample_two_sided_ks(
                    holdout_sample, beta_l2, eta_l2, gamma_l2
                )
            ss_violation_l2 = check_support_set_violation(holdout_sample, gamma_l2)
            dist_beta_l2, dist_eta_l2 = param_distance_rel(
                beta_l2, eta_l2, beta_ref, eta_ref
            )
            all_rows.append({
                'train_n': train_n, 'repeat_index': rep_idx,
                'method': 'l2', 'model_id': 'l2',
                'delta_used': l2_delta,
                'beta_hat': beta_l2, 'eta_hat': eta_l2, 'gamma_hat': gamma_l2,
                'r_squared': r2_l2, 'mdm_status': int(status_l2),
                'D': D_l2, 'failed': failed_l2, 'failure_reason': reason_l2 or '',
                'support_set_violation': int(ss_violation_l2),
                'param_dist_beta': dist_beta_l2, 'param_dist_eta': dist_eta_l2,
            })

            # ── NN (all 15 selectors, same splits) ──
            if nn_selectors is not None:
                for sel in nn_selectors:
                    model_id = f"fold_{sel['fold_idx']}_seed_{sel['seed']}"
                    nn_pred_failed = False
                    nn_pred_reason = None
                    try:
                        nn_delta = predict_nn_delta(sel, feats)
                    except Exception as e:
                        nn_pred_failed = True
                        nn_pred_reason = f"nn_prediction_exception: {str(e)[:200]}"
                        nn_delta = float('nan')

                    if nn_pred_failed:
                        # Prediction failure → record as failed, D=1
                        # support_set_violation=NaN: unknown (no γ̂ exists)
                        all_rows.append({
                            'train_n': train_n, 'repeat_index': rep_idx,
                            'method': 'nn', 'model_id': model_id,
                            'delta_used': float('nan'),
                            'beta_hat': float('nan'), 'eta_hat': float('nan'),
                            'gamma_hat': float('nan'),
                            'r_squared': float('nan'), 'mdm_status': 0,
                            'D': FAILURE_D, 'failed': True,
                            'failure_reason': nn_pred_reason,
                            'support_set_violation': float('nan'),
                            'param_dist_beta': float('inf'),
                            'param_dist_eta': float('inf'),
                        })
                        continue

                    beta_nn, eta_nn, gamma_nn, r2_nn, status_nn, exc_nn = \
                        run_mdm_estimation(train_sample, nn_delta)
                    failed_nn, reason_nn = detect_failure(
                        beta_nn, eta_nn, gamma_nn, status_nn, train_sample, exc_nn
                    )
                    if failed_nn:
                        D_nn = FAILURE_D
                    else:
                        D_nn = one_sample_two_sided_ks(
                            holdout_sample, beta_nn, eta_nn, gamma_nn
                        )
                    ss_violation_nn = check_support_set_violation(
                        holdout_sample, gamma_nn
                    )
                    dist_beta_nn, dist_eta_nn = param_distance_rel(
                        beta_nn, eta_nn, beta_ref, eta_ref
                    )
                    all_rows.append({
                        'train_n': train_n, 'repeat_index': rep_idx,
                        'method': 'nn', 'model_id': model_id,
                        'delta_used': nn_delta,
                        'beta_hat': beta_nn, 'eta_hat': eta_nn,
                        'gamma_hat': gamma_nn,
                        'r_squared': r2_nn, 'mdm_status': int(status_nn),
                        'D': D_nn, 'failed': failed_nn,
                        'failure_reason': reason_nn or '',
                        'support_set_violation': int(ss_violation_nn),
                        'param_dist_beta': dist_beta_nn,
                        'param_dist_eta': dist_eta_nn,
                    })

            done += 1
            if done % 100 == 0 or done == total_splits:
                log(f"  Progress: {done}/{total_splits} splits done "
                    f"({done * 100 / total_splits:.0f}%)")

    df_results = pd.DataFrame(all_rows, columns=RESULT_COLUMNS)
    log(f"  Total result rows: {len(df_results)}")

    # ── Step 7: Verify expected row count (fail-closed) ──
    n_methods_per_split = 2  # default + l2
    if nn_selectors is not None:
        n_methods_per_split += len(nn_selectors)  # 15 NN models
    expected_rows = sum(len(all_splits[tn]) * n_methods_per_split
                        for tn in TRAIN_N_VALUES)
    log(f"  Expected rows: {expected_rows}, actual: {len(df_results)}")
    if len(df_results) != expected_rows:
        raise RuntimeError(
            f"Row count mismatch: expected {expected_rows}, got {len(df_results)}"
        )

    # Verify primary key uniqueness (fail-closed)
    pk_cols = ['train_n', 'repeat_index', 'method', 'model_id']
    n_dups = int(df_results.duplicated(subset=pk_cols).sum())
    if n_dups > 0:
        raise RuntimeError(
            f"Found {n_dups} duplicate primary keys in results"
        )
    log(f"  Primary key uniqueness: OK ({len(df_results)} rows)")

    # ── Step 8: Per-model aggregation ──
    log("Step 8: Computing per-model aggregation...")
    df_model_agg = aggregate_per_model(df_results)
    log(f"  Model-level rows: {len(df_model_agg)}")

    # ── Step 9: Cross-model distribution (NN only) ──
    log("Step 9: Computing cross-model distribution...")
    df_nn_dist = cross_model_distribution(df_model_agg)
    log(f"  NN distribution rows: {len(df_nn_dist)}")

    # ── Step 10: Paired win rates ──
    log("Step 10: Computing paired win rates...")

    # Default vs L2
    default_l2_wins = compute_paired_wins(df_results, 'l2', 'default')

    # NN vs Default and NN vs L2: per-model then distribution
    nn_vs_default_rates = []
    nn_vs_l2_rates = []
    nn_vs_default_tie_rates = []
    nn_vs_l2_tie_rates = []
    if nn_selectors is not None:
        for sel in nn_selectors:
            model_id = f"fold_{sel['fold_idx']}_seed_{sel['seed']}"
            for train_n in TRAIN_N_VALUES:
                w = compute_nn_paired_wins(df_results, model_id, 'default')
                if not np.isnan(w[train_n]['win_rate']):
                    nn_vs_default_rates.append({
                        'model_id': model_id, 'train_n': train_n,
                        'win_rate': w[train_n]['win_rate'],
                    })
                    nn_vs_default_tie_rates.append({
                        'model_id': model_id, 'train_n': train_n,
                        'tie_rate': w[train_n]['tie_rate'],
                    })
                w2 = compute_nn_paired_wins(df_results, model_id, 'l2')
                if not np.isnan(w2[train_n]['win_rate']):
                    nn_vs_l2_rates.append({
                        'model_id': model_id, 'train_n': train_n,
                        'win_rate': w2[train_n]['win_rate'],
                    })
                    nn_vs_l2_tie_rates.append({
                        'model_id': model_id, 'train_n': train_n,
                        'tie_rate': w2[train_n]['tie_rate'],
                    })

    df_nn_vs_default = pd.DataFrame(nn_vs_default_rates) if nn_vs_default_rates else pd.DataFrame()
    df_nn_vs_l2 = pd.DataFrame(nn_vs_l2_rates) if nn_vs_l2_rates else pd.DataFrame()
    df_nn_vs_default_ties = pd.DataFrame(nn_vs_default_tie_rates) if nn_vs_default_tie_rates else pd.DataFrame()
    df_nn_vs_l2_ties = pd.DataFrame(nn_vs_l2_tie_rates) if nn_vs_l2_tie_rates else pd.DataFrame()

    # ── Step 11: Build summary ──
    log("Step 11: Building summary...")

    # Per-method, per-n primary D stats & failure rates
    # Default and L2: pooled across 500 repeats (contract allows)
    # NN: model-first — per-model first, then distribution of 15 model-level values
    primary_stats = {}

    for method in ['default', 'l2']:
        primary_stats[method] = {}
        for train_n in TRAIN_N_VALUES:
            mask = (df_results['train_n'] == train_n) & (df_results['method'] == method)
            subset = df_results[mask]
            if len(subset) == 0:
                continue
            D_vals = subset['D'].values
            n_failed = int(subset['failed'].sum())
            n_total = len(subset)
            primary_stats[method][str(train_n)] = {
                'n_total': n_total,
                'n_failed': n_failed,
                'failure_rate': n_failed / n_total,
                'mean_D': float(np.mean(D_vals)),
                'median_D': float(np.median(D_vals)),
                'std_D': float(np.std(D_vals, ddof=1)) if n_total > 1 else 0.0,
                'Q1_D': float(np.percentile(D_vals, 25)),
                'Q3_D': float(np.percentile(D_vals, 75)),
            }

    # NN: model-first aggregation — compute per-model stats, then distribution
    primary_stats['nn'] = {}
    complete_case = {}
    nn_model_primary = {}  # model_id -> {train_n: {mean_D, median_D, failure_rate, ...}}
    nn_model_cc = {}       # model_id -> {train_n: {mean_D, median_D, ...}}

    if nn_selectors is not None:
        for sel in nn_selectors:
            model_id = f"fold_{sel['fold_idx']}_seed_{sel['seed']}"
            nn_model_primary[model_id] = {}
            nn_model_cc[model_id] = {}
            for train_n in TRAIN_N_VALUES:
                mask = (df_results['train_n'] == train_n) & \
                       (df_results['method'] == 'nn') & \
                       (df_results['model_id'] == model_id)
                subset = df_results[mask]
                if len(subset) == 0:
                    continue
                D_vals = subset['D'].values
                n_total = len(subset)
                n_failed = int(subset['failed'].sum())
                nn_model_primary[model_id][str(train_n)] = {
                    'n_total': n_total,
                    'n_failed': n_failed,
                    'failure_rate': n_failed / n_total,
                    'mean_D': float(np.mean(D_vals)),
                    'median_D': float(np.median(D_vals)),
                    'std_D': float(np.std(D_vals, ddof=1)) if n_total > 1 else 0.0,
                    'Q1_D': float(np.percentile(D_vals, 25)),
                    'Q3_D': float(np.percentile(D_vals, 75)),
                }
                # Complete-case for this model
                cc_mask = mask & (~df_results['failed'])
                cc_subset = df_results[cc_mask]
                if len(cc_subset) > 0:
                    cc_D_vals = cc_subset['D'].values
                    nn_model_cc[model_id][str(train_n)] = {
                        'n_complete_case': int(len(cc_subset)),
                        'mean_D': float(np.mean(cc_D_vals)),
                        'median_D': float(np.median(cc_D_vals)),
                        'std_D': float(np.std(cc_D_vals, ddof=1)) if len(cc_subset) > 1 else 0.0,
                    }

        # Cross-model distribution of per-model primary stats
        for train_n in TRAIN_N_VALUES:
            tn_str = str(train_n)
            model_medians = []
            model_means = []
            model_failure_rates = []
            for model_id in nn_model_primary:
                if tn_str in nn_model_primary[model_id]:
                    model_medians.append(nn_model_primary[model_id][tn_str]['median_D'])
                    model_means.append(nn_model_primary[model_id][tn_str]['mean_D'])
                    model_failure_rates.append(nn_model_primary[model_id][tn_str]['failure_rate'])

            primary_stats['nn'][tn_str] = {
                'n_models': len(model_medians),
                'n_repeats_per_model': n_repeats,
                'model_median_D': _dist_summary(np.array(model_medians)) if model_medians else None,
                'model_mean_D': _dist_summary(np.array(model_means)) if model_means else None,
                'model_failure_rate': _dist_summary(np.array(model_failure_rates)) if model_failure_rates else None,
                'primary_nn_result': (
                    float(np.median(model_medians)) if model_medians else None
                ),
            }

    # Complete-case sensitivity
    # Default/L2: pooled (contract allows)
    # NN: model-first
    complete_case['default'] = {}
    complete_case['l2'] = {}
    for method in ['default', 'l2']:
        for train_n in TRAIN_N_VALUES:
            mask = (df_results['train_n'] == train_n) & \
                   (df_results['method'] == method) & \
                   (~df_results['failed'])
            subset = df_results[mask]
            if len(subset) == 0:
                continue
            D_vals = subset['D'].values
            n_cc = len(subset)
            complete_case[method][str(train_n)] = {
                'n_complete_case': n_cc,
                'mean_D': float(np.mean(D_vals)),
                'median_D': float(np.median(D_vals)),
                'std_D': float(np.std(D_vals, ddof=1)) if n_cc > 1 else 0.0,
            }

    complete_case['nn'] = {}
    if nn_selectors is not None:
        for train_n in TRAIN_N_VALUES:
            tn_str = str(train_n)
            cc_medians = []
            cc_means = []
            for model_id in nn_model_cc:
                if tn_str in nn_model_cc[model_id]:
                    cc_medians.append(nn_model_cc[model_id][tn_str]['median_D'])
                    cc_means.append(nn_model_cc[model_id][tn_str]['mean_D'])
            if cc_medians:
                complete_case['nn'][tn_str] = {
                    'n_models_with_complete_cases': len(cc_medians),
                    'model_median_D': _dist_summary(np.array(cc_medians)),
                    'model_mean_D': _dist_summary(np.array(cc_means)) if cc_means else None,
                }

    # NN win rate & tie rate distributions
    nn_win_dist = {}
    nn_tie_dist = {}
    for label, df_w, df_t in [
        ('vs_default', df_nn_vs_default, df_nn_vs_default_ties),
        ('vs_l2', df_nn_vs_l2, df_nn_vs_l2_ties),
    ]:
        nn_win_dist[label] = {}
        nn_tie_dist[label] = {}
        for train_n in TRAIN_N_VALUES:
            if len(df_w) > 0:
                rates_w = df_w[df_w['train_n'] == train_n]['win_rate']
                if len(rates_w) > 0:
                    nn_win_dist[label][str(train_n)] = _dist_summary(rates_w)
            if len(df_t) > 0:
                rates_t = df_t[df_t['train_n'] == train_n]['tie_rate']
                if len(rates_t) > 0:
                    nn_tie_dist[label][str(train_n)] = _dist_summary(rates_t)

    # Default vs L2
    dl2_wins = {}
    for tn, v in default_l2_wins.items():
        dl2_wins[str(tn)] = {
            'win_rate_l2_over_default': v['win_rate'],
            'tie_rate': v['tie_rate'],
            'wins': v['wins'],
            'losses': v['losses'],
            'ties': v['ties'],
        }

    summary = {
        'dataset_id': 'nist-6061-t6-fatigue',
        'created_at': now_iso(),
        'n_total_lifetimes': int(n_total),
        'n_repeats_per_train_n': n_repeats,
        'train_n_values': TRAIN_N_VALUES,
        'large_sample_ref': {
            'beta': float(beta_ref),
            'eta': float(eta_ref),
            'gamma': float(gamma_ref),
        },
        'primary_stats': primary_stats,
        'complete_case_sensitivity': complete_case,
        'default_vs_l2_paired': dl2_wins,
        'nn_win_rate_distributions': nn_win_dist,
        'nn_tie_rate_distributions': nn_tie_dist,
    }

    # ── Finalize summary (all additions must happen BEFORE writing to disk) ──
    if len(df_nn_dist) > 0:
        summary['nn_cross_model_distribution'] = df_nn_dist.to_dict(orient='records')

    # ── Step 12: Write outputs ──
    log("Step 12: Writing outputs...")

    # real_holdout_results.csv
    results_path = os.path.join(output_dir, 'real_holdout_results.csv')
    df_results.to_csv(results_path, index=False)
    log(f"  Saved: {results_path} ({len(df_results)} rows)")

    # real_holdout_summary.json (summary is fully built above)
    summary_path = os.path.join(output_dir, 'real_holdout_summary.json')
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, sort_keys=True, ensure_ascii=False)
    log(f"  Saved: {summary_path}")

    # real_nn_model_stability.csv
    stability_path = os.path.join(output_dir, 'real_nn_model_stability.csv')
    nn_model_rows = df_model_agg[df_model_agg['method'] == 'nn'].copy()
    if len(nn_model_rows) > 0:
        # Add win/tie rates to model-level rows
        for idx_val in nn_model_rows.index:
            mid = nn_model_rows.loc[idx_val, 'model_id']
            tn = nn_model_rows.loc[idx_val, 'train_n']
            if len(df_nn_vs_default) > 0:
                vd = df_nn_vs_default[
                    (df_nn_vs_default['model_id'] == mid) &
                    (df_nn_vs_default['train_n'] == tn)
                ]
                if len(vd) > 0:
                    nn_model_rows.loc[idx_val, 'win_rate_vs_default'] = float(vd.iloc[0]['win_rate'])
            if len(df_nn_vs_l2) > 0:
                vl = df_nn_vs_l2[
                    (df_nn_vs_l2['model_id'] == mid) &
                    (df_nn_vs_l2['train_n'] == tn)
                ]
                if len(vl) > 0:
                    nn_model_rows.loc[idx_val, 'win_rate_vs_l2'] = float(vl.iloc[0]['win_rate'])
            if len(df_nn_vs_default_ties) > 0:
                td = df_nn_vs_default_ties[
                    (df_nn_vs_default_ties['model_id'] == mid) &
                    (df_nn_vs_default_ties['train_n'] == tn)
                ]
                if len(td) > 0:
                    nn_model_rows.loc[idx_val, 'tie_rate_vs_default'] = float(td.iloc[0]['tie_rate'])
            if len(df_nn_vs_l2_ties) > 0:
                tl = df_nn_vs_l2_ties[
                    (df_nn_vs_l2_ties['model_id'] == mid) &
                    (df_nn_vs_l2_ties['train_n'] == tn)
                ]
                if len(tl) > 0:
                    nn_model_rows.loc[idx_val, 'tie_rate_vs_l2'] = float(tl.iloc[0]['tie_rate'])
    nn_model_rows.to_csv(stability_path, index=False)
    log(f"  Saved: {stability_path} ({len(nn_model_rows)} rows)")

    # real_data_manifest.json
    git_commit, git_dirty = get_git_info()
    config_hash = compute_config_hash()
    frozen_config_sha256 = compute_frozen_config_sha256()
    versions = get_package_versions()
    # Collect per-fold P99 values
    p99_values = {}
    if nn_selectors:
        for sel in nn_selectors:
            key = f"fold_{sel['fold_idx']}"
            if key not in p99_values:
                p99_values[key] = sel.get('failure_penalty')
    manifest = {
        'experiment': 'real_data_holdout_validation_p7',
        'created_at': now_iso(),
        'contract_version': 'P6-v1.1-FROZEN-REVISED',
        'contract_content_commit': '2ee23a8',
        'execution_commit': git_commit,
        'git_dirty': git_dirty,
        'config_hash': config_hash,
        'frozen_config_sha256': frozen_config_sha256,
        'versions': versions,
        'dataset_id': 'nist-6061-t6-fatigue',
        'data_source': {
            'BIRNSAUN_DAT_sha256': hash_results.get('BIRNSAUN.DAT', {}).get('sha256'),
            'lifetimes_csv_sha256': hash_results.get('lifetimes.csv', {}).get('sha256'),
        },
        'gate': {
            'passed': gate.passed,
            'r_squared': gate.diagnostics['r_squared'],
            'beta_hat': gate.diagnostics['beta_hat'],
            'eta_hat': gate.diagnostics['eta_hat'],
        },
        'nn_training': {
            'n_selectors': len(nn_selectors) if nn_selectors else 0,
            'folds': N_FOLDS,
            'seeds': STABILITY_SEEDS,
            'hidden_layers': list(MLP_HIDDEN_LAYERS),
            'failure_penalty_method': 'per_fold_P99_of_training_loss',
            'per_fold_p99': p99_values if p99_values else None,
        },
        'config': {
            'base_seed': BASE_SEED,
            'train_n_values': TRAIN_N_VALUES,
            'n_repeats': n_repeats,
            'default_delta': DEFAULT_DELTA,
            'l2_deltas': L2_DELTAS,
            'tie_tolerance': TIE_TOLERANCE,
            'failure_D': FAILURE_D,
            'delta_grid_n_points': N_DELTAS,
            'delta_grid': DELTA_GRID,
        },
        'output_schema': {
            'real_holdout_results_columns': RESULT_COLUMNS,
            'expected_rows': expected_rows,
            'actual_rows': len(df_results),
            'primary_key': ['train_n', 'repeat_index', 'method', 'model_id'],
        },
    }
    manifest_path = os.path.join(output_dir, 'real_data_manifest.json')
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, sort_keys=True, ensure_ascii=False)
    log(f"  Saved: {manifest_path}")

    # run_log.txt
    log_path = os.path.join(output_dir, 'run_log.txt')
    with open(log_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(log_lines) + '\n')
    log(f"  Saved: {log_path}")

    log("=" * 70)
    log("P7 pipeline complete.")
    log(f"Output: {output_dir}")
    log("=" * 70)

    return {
        'df_results': df_results,
        'df_model_agg': df_model_agg,
        'df_nn_dist': df_nn_dist,
        'summary': summary,
        'manifest': manifest,
        'nn_selectors': nn_selectors,
    }


def _dist_summary(values):
    """Helper: return {min, Q1, median, Q3, max, mean, std} for a numeric array."""
    vals = np.asarray(values, dtype=float)
    vals = vals[np.isfinite(vals)]
    if len(vals) == 0:
        return None
    return {
        'min': float(np.min(vals)),
        'Q1': float(np.percentile(vals, 25)),
        'median': float(np.median(vals)),
        'Q3': float(np.percentile(vals, 75)),
        'max': float(np.max(vals)),
        'mean': float(np.mean(vals)),
        'std': float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0,
    }


# ═══════════════════════════════════════════════════════════════
# P8a formal run: environment validation + transactional output
# ═══════════════════════════════════════════════════════════════

def validate_p8a_environment():
    """Verify P8a pre-conditions before formal run. Raises RuntimeError on failure.

    Checks:
      1. Git tree is clean (no uncommitted changes).
      2. P7 Codex APPROVE record exists.
      3. P6 frozen contract exists.
    Returns the short execution commit hash.
    """
    # 1. Git tree must be clean
    commit, dirty = get_git_info()
    if dirty:
        raise RuntimeError(
            "P8a formal run requires a clean git tree. "
            "Uncommitted changes detected via 'git status --porcelain'.\n"
            "Commit or stash changes before running the formal experiment."
        )
    if commit == "UNKNOWN":
        raise RuntimeError(
            "P8a formal run requires a known git commit. "
            "Could not determine HEAD commit."
        )

    # 2. P7 APPROVE record must exist
    if not os.path.exists(_P7_APPROVE_RECORD):
        raise RuntimeError(
            f"P7 Codex APPROVE record not found at: {_P7_APPROVE_RECORD}\n"
            "P8a formal run requires P7 independent review approval."
        )

    # 3. P6 frozen contract must exist
    p6_contract = os.path.join(
        ARTIFACTS_DIR, "real_data", "P6_FROZEN_CONTRACT.md"
    )
    if not os.path.exists(p6_contract):
        raise RuntimeError(f"P6 frozen contract not found: {p6_contract}")

    log(f"P8a environment validated: commit={commit}, tree=clean, "
        f"P7_APPROVE=present, P6_contract=present")
    return commit


def run_p8a_formal(data_dir=None, output_dir=None, chunks_dir=None):
    """P8a formal run with transactional output (scratch -> promote).

    Protocol:
      1. Validate environment (git clean, P7 APPROVE, P6 contract).
      2. Fail-closed: formal output must not already exist.
      3. Create unique scratch directory under output_dir/scratch/.
      4. Run pipeline to scratch.
      5. Verify all 5 output files exist in scratch.
      6. Promote files from scratch to formal dir.
      7. Clean up scratch.

    If the run fails, scratch preserves partial results for diagnosis
    but formal dir remains uncontaminated.
    """
    if not _P8A_FORMAL_AUTHORIZED:
        raise RuntimeError(
            "P8A_FORMAL_AUTHORIZED is False. "
            "P8a formal run requires explicit authorization in the generation commit."
        )

    if data_dir is None:
        data_dir = os.path.join(ARTIFACTS_DIR, "real_data", "nist-6061-t6-fatigue")
    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    if chunks_dir is None:
        chunks_dir = os.path.join(SHARED_DATA_DIR, "chunks")

    # ── Environment validation ──
    log("=" * 70)
    log("P8a Formal Run — Environment Validation")
    log("=" * 70)
    exec_commit = validate_p8a_environment()

    # ── Fail-closed: formal output must not exist ──
    log("Checking formal output safety...")
    check_output_safety(output_dir)
    log("  Formal output dir is clean.")

    # ── Create scratch directory ──
    run_ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    scratch_dir = os.path.join(output_dir, 'scratch', f'run_{run_ts}')
    os.makedirs(scratch_dir, exist_ok=True)
    log(f"Scratch directory: {scratch_dir}")

    # ── Run pipeline to scratch ──
    t_start = time.time()
    start_iso = now_iso()
    log(f"Formal run start: {start_iso}")
    log(f"Execution commit: {exec_commit}")

    try:
        result = run_pipeline(
            data_dir=data_dir,
            output_dir=scratch_dir,
            chunks_dir=chunks_dir,
        )
    except Exception:
        elapsed = time.time() - t_start
        log(f"P8a formal run FAILED after {elapsed:.0f}s")
        log(f"Scratch directory preserved: {scratch_dir}")
        raise

    t_end = time.time()
    elapsed = t_end - t_start
    end_iso = now_iso()
    log(f"Formal run end: {end_iso}")
    log(f"Elapsed: {elapsed:.0f}s ({elapsed/60:.1f} min)")

    # ── Verify scratch outputs ──
    expected_files = [
        'real_holdout_results.csv',
        'real_holdout_summary.json',
        'real_nn_model_stability.csv',
        'real_data_manifest.json',
        'run_log.txt',
    ]
    for fname in expected_files:
        fpath = os.path.join(scratch_dir, fname)
        if not os.path.exists(fpath):
            raise RuntimeError(
                f"Scratch verification failed: missing {fname} in {scratch_dir}"
            )
    log("Scratch outputs verified: all 5 files present.")

    # ── Promote: move files from scratch to formal dir ──
    log("Promoting outputs from scratch to formal directory...")
    for fname in expected_files:
        src = os.path.join(scratch_dir, fname)
        dst = os.path.join(output_dir, fname)
        os.rename(src, dst)
        log(f"  Promoted: {fname}")

    # ── Clean up scratch ──
    try:
        os.rmdir(scratch_dir)
        log("Scratch directory cleaned.")
    except OSError:
        log(f"  (scratch dir not empty, leaving: {scratch_dir})")

    # ── Re-read manifest and add P8a provenance fields ──
    manifest_path = os.path.join(output_dir, 'real_data_manifest.json')
    with open(manifest_path, 'r', encoding='utf-8') as f:
        manifest = json.load(f)

    # Augment manifest with P8a-specific fields
    manifest['experiment'] = 'real_data_holdout_validation_p8a_formal'
    manifest['p8a_contract_version'] = 'P8a-v1.0-FROZEN'
    manifest['p7_approve_tip'] = 'd619a40'
    manifest['p7_approve_record'] = 'coworker/reviews/2026-07-25-study01xu-p7-codex-approve.md'
    manifest['generation_code_commit'] = exec_commit
    manifest['start_time'] = start_iso
    manifest['end_time'] = end_iso
    manifest['elapsed_seconds'] = round(elapsed, 1)
    manifest['recovery_attempts'] = 0
    manifest['p8a_authorization'] = {
        'guard': '_P8A_FORMAL_AUTHORIZED',
        'scope': 'single_generation_commit',
        'bypass_exists': False,
    }

    # Compute output file hashes
    output_hashes = {}
    for fname in expected_files:
        fpath = os.path.join(output_dir, fname)
        with open(fpath, 'rb') as f:
            raw = f.read()
        raw_lf = raw.replace(b'\r\n', b'\n').replace(b'\r', b'\n')
        output_hashes[fname] = hashlib.sha256(raw_lf).hexdigest()
    manifest['output_hashes'] = output_hashes

    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, sort_keys=True, ensure_ascii=False)
    log("Manifest augmented with P8a provenance fields.")

    log("=" * 70)
    log("P8a formal run COMPLETE.")
    log(f"Output: {output_dir}")
    log(f"Execution commit: {exec_commit}")
    log(f"Elapsed: {elapsed:.0f}s")
    log("=" * 70)

    return result


# ═══════════════════════════════════════════════════════════════
# CLI entry point
# ═══════════════════════════════════════════════════════════════

def main():
    """CLI entry point for real data holdout validation.

    P8a formal run: requires _P8A_FORMAL_AUTHORIZED=True (narrow, auditable).
    There is NO CLI bypass flag, NO hidden parameter, NO test-only entry point.
    Tests call run_pipeline() directly without going through main().
    """
    if '--help' in sys.argv or '-h' in sys.argv:
        print("Usage: python run_real_data_validation.py")
        print()
        print("P8a formal real data holdout validation.")
        print("No CLI flags. The formal run is fully automated against")
        print("the frozen P6 contract and P8a execution contract.")
        print()
        print("Tests call run_pipeline() directly — there is no test-only")
        print("entry point or bypass flag on this path.")
        return

    if not _P8A_FORMAL_AUTHORIZED:
        raise RuntimeError(
            "run_real_data_validation.py: P8a formal authorization is not active.\n"
            "The _P8A_FORMAL_AUTHORIZED guard must be True in the generation commit.\n"
            "There is NO CLI bypass. Tests call run_pipeline() directly.\n"
            "See: P8A_EXECUTION_CONTRACT.md and "
            "coworker/reviews/2026-07-25-study01xu-p7-codex-approve.md"
        )

    return run_p8a_formal()


if __name__ == '__main__':
    main()
