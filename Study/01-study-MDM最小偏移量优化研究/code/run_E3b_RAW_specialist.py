"""
Study/01 Candidate E3b_RAW_specialist: RAW-input per-n specialist Vector-MLP-L6.

Candidate route (alternative NN training method inside Study01):
  - For n in {7, 10, 20} train a SEPARATE Vector-MLP-L6.
  - Each model inputs ONLY the ascending-sorted raw sample values of that n
    (input dim = n). No padding, no mask, no explicit n, no hand-crafted
    statistics, no true parameters, no combo/seed/repeat/delta leakage.
  - Output is the same 26-dim L6 loss curve as formal E3b; delta_hat is the
    argmin predicted point; final J1 uses the TRUE loss at the selected delta.
  - Same 5-fold full-combo holdout, same seeds (42/2026/3407), same
    (256,128,64) ReLU/Adam MLP + early stopping + training hyperparameters as
    formal E3b Vector-MLP-L6 (the F13 joint route).

This is a ROUTE comparison: "RAW representation + per-n specialist training"
vs formal E3b "F13 features + joint training". Representation AND training
organization change simultaneously, so any gap cannot be attributed to RAW
alone.

Reuse contract:
  - MC data, sample keys, risk curves come from the SAME formal MC scan
    (artifacts/formal/shared_data/chunks, the source behind the gitignored
    mc_scan_raw.csv). No 1.17M-call MDM rerun.
  - Raw samples are deterministically reconstructed by the formal
    generate_sample(beta, eta, gamma, n, repeat_id, seed=SEED_NAMESPACE).

Writes only to artifacts/candidate/E3b_RAW_specialist/. Never touches
artifacts/formal/E3b_vector_mlp/ or any sealed E3/E4 evidence.

Reference: coworker task 2026-07-20-study01-raw-specialist-execution.
"""

import sys
import os
import json
import time
import math
import hashlib
import subprocess
import warnings
import gzip
from datetime import datetime, timezone
from itertools import product

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

# ============================================================
# Path setup — __file__-relative so it works on any drive
# (config.py hardcodes PLATFORM_ROOT=D:\\weibull which is unused here)
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
    ARTIFACTS_DIR, SHARED_DATA_DIR,
)
from studies.common.sample import generate_sample

# ============================================================
# Output directory (candidate only — never formal)
# ============================================================

CANDIDATE_ROOT = os.path.join(STUDY_ROOT, "artifacts", "candidate")
OUTPUT_DIR = os.path.join(CANDIDATE_ROOT, "E3b_RAW_specialist")
MODELS_DIR = os.path.join(OUTPUT_DIR, "models")
PREDS_DIR = os.path.join(OUTPUT_DIR, "predictions")
DIAG_DIR = os.path.join(OUTPUT_DIR, "diagnostics")
PLOTS_DIR = os.path.join(OUTPUT_DIR, "plots")

CHUNKS_DIR = os.path.join(SHARED_DATA_DIR, "chunks")
MC_MANIFEST_PATH = os.path.join(SHARED_DATA_DIR, "manifest.json")

# ============================================================
# Contracts
# ============================================================

SPECIALIST_NS = list(N_GRID)            # [7, 10, 20]
FOLDS = list(range(5))                  # 5-fold combo holdout
SEEDS = [42, 2026, 3407]                # same as formal E3b stability
N_DELTAS = len(DELTA_GRID)              # 26
SAMPLE_KEYS = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']

# Identical MLP/training hyperparameters to formal E3b Vector-MLP-L6
MLP_HIDDEN_LAYERS = (256, 128, 64)
MLP_MAX_ITER = 300
MLP_BATCH_SIZE = 256
MLP_ALPHA = 1e-4
MLP_LR = 1e-3
MLP_VALIDATION_FRACTION = 0.15
MLP_N_ITER_NO_CHANGE = 20

NEAR_OPTIMAL_EPS = [0.01, 0.02, 0.05]
ENDPOINT_DELTAS = [0.00, 0.02, 0.48, 0.50]

# Banned fields that must NEVER appear in model inputs
BANNED_FIELDS = {'beta', 'eta', 'gamma', 'gamma_over_eta',
                 'seed', 'repeat_id', 'combo_id', 'delta'}

CONTRACT_VERSION = "E3b_RAW_specialist_v1"


# ============================================================
# Data loading (chunks -> df_mc, identical to mc_scan_raw.csv)
# ============================================================

def list_mdm_chunks():
    chunks = sorted(
        f for f in os.listdir(CHUNKS_DIR)
        if f.startswith("chunk_") and f.endswith("_mdm.csv")
    )
    assert len(chunks) == 45, f"Expected 45 mdm chunks, found {len(chunks)}"
    return [os.path.join(CHUNKS_DIR, c) for c in chunks]


def load_mc_scan():
    """Concatenate the 45 chunk_*_mdm.csv files into one DataFrame.

    This is byte-equivalent to reading the gitignored mc_scan_raw.csv aggregate.
    """
    chunk_paths = list_mdm_chunks()
    dtypes = {
        'beta': 'float64', 'eta': 'float64', 'gamma': 'float64',
        'gamma_over_eta': 'float64', 'n': 'int64', 'repeat_id': 'int64',
        'delta': 'float64', 'beta_hat': 'float64', 'eta_hat': 'float64',
        'gamma_hat': 'float64', 'r_squared': 'float64',
        'converged': 'boolean', 'time_ms': 'float64',
    }
    frames = []
    for p in chunk_paths:
        frames.append(pd.read_csv(p, dtype=dtypes))
    df = pd.concat(frames, ignore_index=True)
    return df


def verify_data_integrity(df, manifest):
    """Same integrity checks as formal E3b."""
    expected_combos = (
        len(BETA_GRID) * len(ETA_GRID) * len(GAMMA_OVER_ETA_GRID) * len(N_GRID)
    )
    expected_rows = expected_combos * N_DELTAS * manifest.get("repeats", R_MAIN)
    assert len(df) == expected_rows, \
        f"Row count: expected {expected_rows}, got {len(df)}"

    dup_key = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id', 'delta']
    dups = df.duplicated(subset=dup_key).sum()
    assert dups == 0, f"{dups} duplicate rows"

    unique_combos = df[['beta', 'eta', 'gamma_over_eta', 'n']].drop_duplicates()
    assert len(unique_combos) == expected_combos

    unique_deltas = sorted(df['delta'].unique())
    assert unique_deltas == DELTA_GRID, "Delta grid mismatch"

    rep_counts = df.groupby(['beta', 'eta', 'gamma_over_eta', 'n'])['repeat_id'].nunique()
    assert rep_counts.min() == manifest.get("repeats", R_MAIN)

    non_success_rate = None
    if 'status' in df.columns:
        non_success_rate = float((df['status'] != 'success').mean())

    return {
        'expected_rows': int(expected_rows), 'actual_rows': int(len(df)),
        'duplicate_rows': int(dups), 'unique_combos': int(len(unique_combos)),
        'delta_points': int(len(unique_deltas)),
        'repeat_min': int(rep_counts.min()), 'repeat_max': int(rep_counts.max()),
        'non_success_rate': non_success_rate,
    }


# ============================================================
# Sample reconstruction (deterministic) + raw-input builder
# ============================================================

def hashlib_sample(sample):
    rounded = np.round(np.asarray(sample, dtype=float), 12)
    return hashlib.sha256(rounded.tobytes()).hexdigest()


def verify_sample_reconstruction(manifest):
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


def build_raw_sample_map(df_mc, manifest):
    """Reconstruct the ascending-sorted raw sample for every unique sample key.

    Returns:
        raw_map: dict {(beta,eta,gamma,gamma_over_eta,n,repeat_id) -> np.ndarray(len n)}
        meta_df: DataFrame of unique sample keys (one row per sample), sorted.
    """
    seed_ns = manifest.get("seed_namespace", SEED_NAMESPACE)
    keys_df = (
        df_mc[SAMPLE_KEYS]
        .drop_duplicates()
        .sort_values(SAMPLE_KEYS)
        .reset_index(drop=True)
    )
    print(f"[Raw] Reconstructing {len(keys_df)} unique raw samples "
          f"(seed_namespace={seed_ns})...")

    raw_map = {}
    t0 = time.time()
    for _, row in keys_df.iterrows():
        beta = float(row['beta']); eta = float(row['eta'])
        gamma = float(row['gamma']); n = int(row['n'])
        rid = int(row['repeat_id'])
        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_ns)
        # generate_sample already returns ascending-sorted; sort defensively
        # and assert it equals the reconstructed sample (contract: input row
        # == ascending sorted reconstructed sample).
        sample_sorted = np.sort(sample)
        assert np.allclose(sample_sorted, sample), \
            "generate_sample did not return an ascending-sorted sample"
        raw_map[(beta, eta, gamma, float(row['gamma_over_eta']), n, rid)] = \
            sample_sorted.astype(np.float64)
    print(f"[Raw] Done in {time.time() - t0:.1f}s")
    return raw_map, keys_df


# ============================================================
# Loss computation (identical to formal E3b)
# ============================================================

def compute_per_sample_loss(df):
    r_beta = (df['beta_hat'] - df['beta']) / df['beta']
    r_eta = (df['eta_hat'] - df['eta']) / df['eta']
    r_gamma = (df['gamma_hat'] - df['gamma']) / df['eta']
    df = df.copy()
    df['loss'] = r_beta**2 + r_eta**2 + r_gamma**2
    df['loss'] = df['loss'].replace([np.inf, -np.inf], np.nan)
    return df


# ============================================================
# Split definitions (identical 5-fold combo holdout as formal E3b)
# ============================================================

def get_combo_split():
    """Deterministic 5-fold full-combo holdout over (beta, gamma/eta, n).

    Identical to formal E3b: combos enumerated as product(BETA, GAMMA/ETA, N),
    fold k holds out combos whose enumerate index % 5 == k.
    """
    combos = list(product(BETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID))
    assert len(combos) == 45
    folds = []
    for fold_idx in range(5):
        test_combos = [c for i, c in enumerate(combos) if i % 5 == fold_idx]
        train_combos = [c for i, c in enumerate(combos) if i % 5 != fold_idx]
        folds.append({
            'fold_name': f'combo_fold_{fold_idx + 1}',
            'train_combos': train_combos,
            'test_combos': test_combos,
        })
    return folds


def build_split_rows():
    rows = []
    for fold in get_combo_split():
        for combo in fold['test_combos']:
            rows.append({
                'fold': fold['fold_name'],
                'test_beta': combo[0],
                'test_gamma_over_eta': combo[1],
                'test_n': combo[2],
            })
    return rows


# ============================================================
# Reference selections (computed on full df, evaluated on held-out test)
# ============================================================

def compute_reference_deltas(df):
    """Same reference delta tables as formal E3b (Default/L1/L2 + oracles)."""
    default_delta = DEFAULT_DELTA
    global_loss = df.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
    l1_delta = float(global_loss.idxmin())
    l2_table = {}
    for n_val in N_GRID:
        loss_by_delta = df[df['n'] == n_val].groupby('delta')['loss'].apply(
            lambda x: np.sqrt(np.nanmean(x)))
        l2_table[n_val] = {'delta_star': float(loss_by_delta.idxmin()),
                           'J1': float(loss_by_delta.min())}
    return {'default_delta': default_delta, 'l1_delta': l1_delta,
            'l2_table': l2_table}


# ============================================================
# Fold preparation + RAW vector pivot (strictly aligned)
# ============================================================

def prepare_fold(df_full, fold):
    """Compute failure_penalty from the FULL train fold (all n) and attach
    loss_filled / is_valid. Mirrors formal E3b prepare_fold_data exactly for
    the penalty + loss_filled definitions.
    """
    train_combo_set = set(fold['train_combos'])
    test_combo_set = set(fold['test_combos'])
    assert not (train_combo_set & test_combo_set), "Train/test combo overlap!"

    combo_str = (df_full['beta'].astype(str) + '|' +
                 df_full['gamma_over_eta'].astype(str) + '|' +
                 df_full['n'].astype(str))
    train_strs = set(f'{b}|{g}|{n}' for b, g, n in train_combo_set)
    test_strs = set(f'{b}|{g}|{n}' for b, g, n in test_combo_set)
    df_tr = df_full[combo_str.isin(train_strs)].copy()
    df_te = df_full[combo_str.isin(test_strs)].copy()

    # Failure penalty from FULL train fold (all n), identical definition to E3b
    train_valid_loss = df_tr['loss'].dropna()
    failure_penalty = float(np.nanpercentile(train_valid_loss, 99))

    for d in (df_tr, df_te):
        d['loss_filled'] = d['loss'].fillna(failure_penalty)
        d['is_valid'] = d.get('status', 'success').eq('success') & d['loss'].notna()

    return {
        'df_train': df_tr, 'df_test': df_te,
        'failure_penalty': failure_penalty,
        'train_combos': sorted(train_combo_set),
        'test_combos': sorted(test_combo_set),
    }


def pivot_raw_vector(df_long, raw_map, n_val, label_col='loss_filled'):
    """Pivot long-format fold data to vector form for the n=n_val specialist.

    Returns:
        keys_df: DataFrame of sample keys, one row per sample (strict order).
        X: (n_samples, n_val) ascending-sorted raw sample rows, aligned to keys_df.
        Y: (n_samples, 26) label curve, aligned to keys_df, columns ordered by DELTA_GRID.
        valid: (n_samples,) is_valid flag (any-delta validity for the sample).

    CRITICAL: keys_df row i, X row i and Y row i all describe the SAME sample,
    guaranteed by building all three from one sorted sample-key list.
    """
    sub = df_long[df_long['n'] == n_val]
    # unique sample keys present in this fold×n, deterministically ordered
    keys = (sub[SAMPLE_KEYS].drop_duplicates().sort_values(SAMPLE_KEYS)
            .reset_index(drop=True))

    X = np.zeros((len(keys), n_val), dtype=np.float64)
    for i, r in keys.iterrows():
        key = (float(r['beta']), float(r['eta']), float(r['gamma']),
               float(r['gamma_over_eta']), int(r['n']), int(r['repeat_id']))
        X[i] = raw_map[key]
    assert X.shape[1] == n_val, "RAW input width must equal n"

    # Build Y from the same key order
    Y = np.full((len(keys), N_DELTAS), np.nan, dtype=np.float64)
    valid_any = np.zeros(len(keys), dtype=bool)
    lookup = sub.set_index(SAMPLE_KEYS + ['delta'])[label_col]
    valid_lookup = sub.set_index(SAMPLE_KEYS + ['delta'])['is_valid']
    for i, r in keys.iterrows():
        kvec = (float(r['beta']), float(r['eta']), float(r['gamma']),
                float(r['gamma_over_eta']), int(r['n']), int(r['repeat_id']))
        for j, d in enumerate(DELTA_GRID):
            Y[i, j] = lookup.get(kvec + (float(d),), np.nan)
            if bool(valid_lookup.get(kvec + (float(d,),), False)):
                valid_any[i] = True
    return keys, X, Y, valid_any


# ============================================================
# Specialist training (RAW input -> 26-dim L6 curve)
# ============================================================

def train_specialist(X_train, Y_train, X_test, seed):
    """Train the (256,128,64) Vector-MLP-L6 on RAW inputs.

    - Input StandardScaler fit on X_train only (per-position z-score).
    - Target StandardScaler fit on Y_train only (26-dim), inverse-transform back.
    Identical MLP hyperparameters to formal E3b Vector-MLP-L6.
    """
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPRegressor

    input_scaler = StandardScaler()
    X_train_s = input_scaler.fit_transform(X_train)
    X_test_s = input_scaler.transform(X_test)

    target_scaler = StandardScaler()
    Y_train_s = target_scaler.fit_transform(Y_train)

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
        model.fit(X_train_s, Y_train_s)

    Y_pred_s = model.predict(X_test_s)
    Y_pred = target_scaler.inverse_transform(Y_pred_s)
    Y_pred = np.clip(Y_pred, 0.0, None)
    return Y_pred, model.n_iter_, input_scaler, target_scaler


def evaluate_selection(keys_df, Y_pred, Y_true, model_name, valid_any):
    """delta_hat = argmin predicted; true loss at that delta. Returns df_sel + metrics."""
    best_idx = np.argmin(Y_pred, axis=1)
    sel_delta = np.array([DELTA_GRID[i] for i in best_idx])
    true_loss = Y_true[np.arange(len(keys_df)), best_idx]
    rows = []
    for i in range(len(keys_df)):
        r = keys_df.iloc[i]
        rows.append({
            'beta': float(r['beta']), 'eta': float(r['eta']),
            'gamma': float(r['gamma']),
            'gamma_over_eta': float(r['gamma_over_eta']),
            'n': int(r['n']), 'repeat_id': int(r['repeat_id']),
            'selected_delta': float(sel_delta[i]),
            'selected_delta_idx': int(best_idx[i]),
            'true_loss': float(true_loss[i]),
            'is_valid': bool(valid_any[i]),
            'model': model_name,
        })
    df_sel = pd.DataFrame(rows)
    j1 = math.sqrt(df_sel['true_loss'].mean())
    failure_rate = 1.0 - df_sel['is_valid'].mean()
    per_n = {int(n_val): {'J1': math.sqrt(g['true_loss'].mean()),
                          'failure_rate': 1.0 - g['is_valid'].mean(),
                          'count': len(g)}
             for n_val, g in df_sel.groupby('n')}
    return df_sel, {'model': model_name, 'J1': j1,
                    'failure_rate': failure_rate,
                    'n_samples': len(df_sel), 'per_n': per_n}


# ============================================================
# Checkpoint / resume
# ============================================================

def model_id(n_val, fold_idx, seed):
    return f"n{n_val}_fold{fold_idx + 1}_seed{seed}"


def checkpoint_paths(n_val, fold_idx, seed):
    mid = model_id(n_val, fold_idx, seed)
    return (os.path.join(MODELS_DIR, f"{mid}.json"),
            os.path.join(PREDS_DIR, f"{mid}.csv"))


def checkpoint_valid(n_val, fold_idx, seed, expected_test_n):
    """A checkpoint is valid if both files exist, JSON has contract_version,
    and the predictions CSV has exactly expected_test_n rows with the right n.
    """
    mpath, ppath = checkpoint_paths(n_val, fold_idx, seed)
    if not (os.path.exists(mpath) and os.path.exists(ppath)):
        return False
    try:
        meta = json.load(open(mpath, encoding='utf-8'))
    except Exception:
        return False
    if meta.get('contract_version') != CONTRACT_VERSION:
        return False
    if meta.get('input_dim') != n_val:
        return False
    if meta.get('test_n_samples') != expected_test_n:
        return False
    try:
        dfp = pd.read_csv(ppath)
    except Exception:
        return False
    if len(dfp) != expected_test_n:
        return False
    if int(dfp['n'].iloc[0]) != n_val:
        return False
    return True


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def save_checkpoint(n_val, fold_idx, seed, metrics, n_iter, runtime_s,
                    input_scaler_mean, input_scaler_std,
                    target_scaler_mean, target_scaler_std,
                    df_sel, Y_pred, Y_true, keys_df, failure_penalty,
                    train_n, test_n):
    os.makedirs(MODELS_DIR, exist_ok=True)
    os.makedirs(PREDS_DIR, exist_ok=True)
    mid = model_id(n_val, fold_idx, seed)
    mpath, ppath = checkpoint_paths(n_val, fold_idx, seed)

    # Per-sample predictions: keys + selection + true loss + 26-dim predicted curve
    pred_cols = {f'pred_d{d}': float for d in DELTA_GRID}
    pred_records = []
    for i in range(len(keys_df)):
        r = keys_df.iloc[i]
        rec = {
            'beta': float(r['beta']), 'eta': float(r['eta']),
            'gamma': float(r['gamma']), 'gamma_over_eta': float(r['gamma_over_eta']),
            'n': int(r['n']), 'repeat_id': int(r['repeat_id']),
            'selected_delta': float(df_sel.iloc[i]['selected_delta']),
            'selected_delta_idx': int(df_sel.iloc[i]['selected_delta_idx']),
            'true_loss': float(df_sel.iloc[i]['true_loss']),
            'is_valid': bool(df_sel.iloc[i]['is_valid']),
            'oracle_min_loss': float(np.min(Y_true[i])),
            'pred_min': float(np.min(Y_pred[i])),
        }
        for j, d in enumerate(DELTA_GRID):
            rec[f'pred_d{d}'] = float(Y_pred[i, j])
        pred_records.append(rec)
    pd.DataFrame(pred_records).to_csv(ppath, index=False)

    meta = {
        'contract_version': CONTRACT_VERSION,
        'model_id': mid, 'n': int(n_val), 'fold': int(fold_idx + 1),
        'seed': int(seed), 'input_dim': int(n_val),
        'train_n_samples': int(train_n), 'test_n_samples': int(test_n),
        'n_iter': int(n_iter), 'runtime_s': float(runtime_s),
        'failure_penalty': float(failure_penalty),
        'metrics': metrics,
        'input_scaler_mean': [float(v) for v in np.asarray(input_scaler_mean).ravel()],
        'input_scaler_std': [float(v) for v in np.asarray(input_scaler_std).ravel()],
        'target_scaler_mean': [float(v) for v in np.asarray(target_scaler_mean).ravel()],
        'target_scaler_std': [float(v) for v in np.asarray(target_scaler_std).ravel()],
        'input_scaler_fit': 'train fold of this n only (per-position StandardScaler)',
        'target_scaler_fit': 'train fold of this n only (26-dim StandardScaler)',
        'predictions_sha256': sha256_file(ppath),
    }
    with open(mpath, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta


# ============================================================
# Per-(n, fold, seed) runner with resume
# ============================================================

def run_one(n_val, fold_idx, seed, df_full, raw_map, fold_prep_cache, log):
    fold = get_combo_split()[fold_idx]
    fp = fold_prep_cache[fold_idx]
    df_train = fp['df_train']
    df_test = fp['df_test']
    failure_penalty = fp['failure_penalty']

    # Specialist test set size for this (n, fold): #test combos with this n × repeats
    test_combos_n = [c for c in fold['test_combos'] if c[2] == n_val]
    expected_test_n = len(test_combos_n) * R_MAIN

    mid = model_id(n_val, fold_idx, seed)
    if checkpoint_valid(n_val, fold_idx, seed, expected_test_n):
        log(f"  [skip] {mid} (valid checkpoint, test_n={expected_test_n})")
        mpath, ppath = checkpoint_paths(n_val, fold_idx, seed)
        meta = json.load(open(mpath, encoding='utf-8'))
        df_sel = pd.read_csv(ppath)
        return {'skipped': True, 'meta': meta, 'df_sel': df_sel}

    # Pivot (strictly aligned) — X built from raw_map, Y from loss_filled
    keys_tr, X_tr, Y_tr, _ = pivot_raw_vector(df_train, raw_map, n_val, 'loss_filled')
    keys_te, X_te, Y_te, valid_te = pivot_raw_vector(df_test, raw_map, n_val, 'loss_filled')
    assert X_tr.shape[1] == n_val and X_te.shape[1] == n_val
    assert X_te.shape[0] == expected_test_n, \
        f"test sample mismatch {X_te.shape[0]} vs {expected_test_n}"

    # Verify RAW input rows equal ascending-sorted reconstructed samples
    for i in range(len(keys_te)):
        r = keys_te.iloc[i]
        key = (float(r['beta']), float(r['eta']), float(r['gamma']),
               float(r['gamma_over_eta']), int(r['n']), int(r['repeat_id']))
        assert np.allclose(X_te[i], raw_map[key]), "RAW input != reconstructed sample"

    t0 = time.time()
    Y_pred, n_iter, in_sc, tg_sc = train_specialist(X_tr, Y_tr, X_te, seed)
    runtime = time.time() - t0
    df_sel, metrics = evaluate_selection(
        keys_te, Y_pred, Y_te, f'RAW-MLP-L6-{mid}', valid_te)
    meta = save_checkpoint(
        n_val, fold_idx, seed, metrics, n_iter, runtime,
        in_sc.mean_, in_sc.scale_, tg_sc.mean_, tg_sc.scale_,
        df_sel, Y_pred, Y_te, keys_te, failure_penalty,
        len(keys_tr), len(keys_te))
    log(f"  [done] {mid}: J1={metrics['J1']:.6f} n_iter={n_iter} "
        f"t={runtime:.1f}s (train={len(keys_tr)}, test={len(keys_te)})")
    return {'skipped': False, 'meta': meta, 'df_sel': df_sel,
            'runtime_s': runtime, 'n_iter': n_iter}


# ============================================================
# Diagnostics (endpoint, near-optimal, delta distribution)
# ============================================================

def endpoint_rows(df_sel, model_name):
    sel = df_sel.copy()
    if len(sel) == 0:
        return []
    out = []
    for cat, sub in [('pooled', sel)] + [(f'n={nv}', g) for nv, g in sel.groupby('n')]:
        out.append({
            'model': model_name, 'category': cat,
            'P_delta_0': float((sub['selected_delta'] == 0.00).mean()),
            'P_delta_0.5': float((sub['selected_delta'] == 0.50).mean()),
            'P_extreme': float(sub['selected_delta'].isin(ENDPOINT_DELTAS).mean()),
            'n_samples': len(sub),
        })
    return out


def near_optimal_summary(df_preds):
    """df_preds has oracle_min_loss, true_loss per sample."""
    rel = ((df_preds['true_loss'] - df_preds['oracle_min_loss'])
           / df_preds['oracle_min_loss'].where(df_preds['oracle_min_loss'] > 1e-12, np.nan))
    regret = df_preds['true_loss'] - df_preds['oracle_min_loss']
    s = {
        'mean_selected_loss': float(df_preds['true_loss'].mean()),
        'mean_oracle_min': float(df_preds['oracle_min_loss'].mean()),
        'mean_regret': float(regret.mean()),
        'mean_rel_regret': float(rel.mean()),
    }
    for eps in NEAR_OPTIMAL_EPS:
        s[f'near_{eps}_rate'] = float((rel <= eps).mean())
    return s


# ============================================================
# Reference evaluation on the pooled combo-holdout test set
# ============================================================

def evaluate_references_all(df_full, raw_map_unused=None):
    """Compute Default/L1/L2/L6-hindsight J1 on the pooled combo-holdout test
    set (each sample scored in its own held-out fold). Mirrors formal E3b
    pooling of evaluate_reference_selection + evaluate_l6_hindsight.
    """
    refs = compute_reference_deltas(df_full)
    folds = get_combo_split()
    recs = []
    for fold in folds:
        fp = prepare_fold(df_full, fold)
        df_te = fp['df_test']
        # pivot to per-sample true curves for this fold
        keys = (df_te[SAMPLE_KEYS].drop_duplicates().sort_values(SAMPLE_KEYS)
                .reset_index(drop=True))
        Y_true = np.full((len(keys), N_DELTAS), np.nan)
        lut = df_te.set_index(SAMPLE_KEYS + ['delta'])['loss']
        for i, r in keys.iterrows():
            kvec = (float(r['beta']), float(r['eta']), float(r['gamma']),
                    float(r['gamma_over_eta']), int(r['n']), int(r['repeat_id']))
            for j, d in enumerate(DELTA_GRID):
                Y_true[i, j] = lut.get(kvec + (float(d),), np.nan)

        def delta_idx(v):
            return DELTA_GRID.index(float(v))
        for i, r in keys.iterrows():
            base = {
                'beta': float(r['beta']), 'eta': float(r['eta']),
                'gamma': float(r['gamma']), 'gamma_over_eta': float(r['gamma_over_eta']),
                'n': int(r['n']), 'repeat_id': int(r['repeat_id']),
                'is_valid': True,
            }
            recs.append({**base, 'model': 'Default',
                         'selected_delta': float(refs['default_delta']),
                         'true_loss': float(Y_true[i, delta_idx(refs['default_delta'])])})
            recs.append({**base, 'model': 'L1',
                         'selected_delta': float(refs['l1_delta']),
                         'true_loss': float(Y_true[i, delta_idx(refs['l1_delta'])])})
            recs.append({**base, 'model': 'L2',
                         'selected_delta': float(refs['l2_table'][int(r['n'])]['delta_star']),
                         'true_loss': float(Y_true[i, delta_idx(refs['l2_table'][int(r['n'])]['delta_star'])])})
            bi = int(np.argmin(Y_true[i]))
            recs.append({**base, 'model': 'L6-hindsight',
                         'selected_delta': float(DELTA_GRID[bi]),
                         'true_loss': float(Y_true[i, bi])})
    df_refs = pd.DataFrame(recs)
    return df_refs, refs


# ============================================================
# Git metadata
# ============================================================

def get_git_metadata():
    def run(args):
        try:
            return subprocess.check_output(args, cwd=PROJECT_ROOT,
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return ''
    commit = run(['git', 'rev-parse', 'HEAD'])
    short = run(['git', 'rev-parse', '--short', 'HEAD'])
    branch = run(['git', 'branch', '--show-current'])
    status = run(['git', 'status', '--short'])
    base = run(['git', 'rev-parse', '--short', '6c955b6e5290c25f3fec297505da6b0991a6b7e5'])
    return {
        'git_commit': commit, 'git_commit_short': short, 'git_branch': branch,
        'workspace_dirty': bool(status), 'git_status_short': status.splitlines(),
        'base_commit_short': base,
    }


# ============================================================
# Main
# ============================================================

def log_lines():
    buf = []

    def _log(msg):
        print(msg)
        buf.append(msg)
    return _log, buf


def run_experiment(force_rerun=False):
    for d in (OUTPUT_DIR, MODELS_DIR, PREDS_DIR, DIAG_DIR, PLOTS_DIR):
        os.makedirs(d, exist_ok=True)
    log, buf = log_lines()

    log("=" * 72)
    log("Study/01 Candidate E3b_RAW_specialist: RAW-input per-n specialist")
    log("=" * 72)

    t_start = time.time()

    log("\n[1/7] Loading MC scan from 45 chunks...")
    df_mc = load_mc_scan()
    with open(MC_MANIFEST_PATH, encoding='utf-8') as f:
        manifest = json.load(f)
    log(f"  Loaded {len(df_mc)} rows")

    log("\n[2/7] Data integrity + sample reconstruction probe...")
    integrity = verify_data_integrity(df_mc, manifest)
    sample_probe = verify_sample_reconstruction(manifest)
    log(f"  Integrity: {integrity}")
    log(f"  Probe SHA256[:12]: {sample_probe['sample_sha256_rounded_12'][:12]}")

    log("\n[3/7] Reconstructing raw samples + computing per-sample loss...")
    raw_map, keys_df = build_raw_sample_map(df_mc, manifest)
    df_full = compute_per_sample_loss(df_mc)
    nan_loss = int(df_full['loss'].isna().sum())
    log(f"  NaN/invalid losses: {nan_loss} ({nan_loss/len(df_full)*100:.3f}%)")

    # Contract: no banned fields in input. The RAW input is the sorted sample;
    # assert it carries no banned key by construction.
    log("  Banned-field contract: RAW input = sorted sample values only (no keys).")

    log("\n[4/7] Preparing 5 folds (failure_penalty per fold)...")
    folds = get_combo_split()
    fold_prep_cache = [prepare_fold(df_full, f) for f in folds]
    for i, fp in enumerate(fold_prep_cache):
        log(f"  fold{i+1}: train_combos={len(fp['train_combos'])} "
            f"test_combos={len(fp['test_combos'])} "
            f"failure_penalty={fp['failure_penalty']:.6f}")

    # Split integrity: every combo appears exactly once as a test combo
    all_test = sorted(c for f in folds for c in f['test_combos'])
    assert len(all_test) == 45 and len(set(all_test)) == 45, "Fold test combos not a partition"

    log("\n[5/7] Training 45 RAW specialists (3 n x 5 fold x 3 seed) with resume...")
    all_meta = []
    all_sel = []
    runtimes, n_iters = [], []
    for n_val in SPECIALIST_NS:
        for fold_idx in range(5):
            for seed in SEEDS:
                if force_rerun:
                    mp, pp = checkpoint_paths(n_val, fold_idx, seed)
                    for p in (mp, pp):
                        if os.path.exists(p):
                            os.remove(p)
                res = run_one(n_val, fold_idx, seed, df_full, raw_map,
                              fold_prep_cache, log)
                all_meta.append(res['meta'])
                sel = res['df_sel'].copy()
                sel['n_val'] = n_val
                sel['fold'] = fold_idx + 1
                sel['seed'] = seed
                all_sel.append(sel)
                if not res['skipped']:
                    runtimes.append(res['runtime_s'])
                    n_iters.append(res['n_iter'])
    df_all_sel = pd.concat(all_sel, ignore_index=True)

    log(f"\n  Trained this run: {len(runtimes)} models; "
        f"skipped (cached): {len(all_meta) - len(runtimes)}")
    if runtimes:
        log(f"  Runtime: total={sum(runtimes):.1f}s mean={np.mean(runtimes):.1f}s "
            f"min={np.min(runtimes):.1f}s max={np.max(runtimes):.1f}s")
        log(f"  n_iter: mean={np.mean(n_iters):.1f} min={np.min(n_iters)} "
            f"max={np.max(n_iters)}")

    # Verify all 45 models present
    expected_ids = {model_id(n, f, s) for n in SPECIALIST_NS for f in range(5) for s in SEEDS}
    got_ids = {m['model_id'] for m in all_meta}
    missing = expected_ids - got_ids
    assert not missing, f"Missing models: {sorted(missing)}"
    log(f"  All 45 models present: {len(got_ids) == 45}")

    log("\n[6/7] Aggregation, references, diagnostics...")
    # Per-seed pooled + per-n J1 (route each sample to its n-specialist)
    seed_summary = []
    for seed in SEEDS:
        sub = df_all_sel[df_all_sel['seed'] == seed]
        pooled_j1 = math.sqrt(sub['true_loss'].mean())
        per_n = {int(nv): math.sqrt(g['true_loss'].mean())
                 for nv, g in sub.groupby('n_val')}
        seed_summary.append({
            'seed': seed, 'pooled_J1': pooled_j1,
            'J1_n7': per_n.get(7, float('nan')),
            'J1_n10': per_n.get(10, float('nan')),
            'J1_n20': per_n.get(20, float('nan')),
            'n_samples': len(sub),
            'endpoint_rate': float(sub['selected_delta'].isin(ENDPOINT_DELTAS).mean()),
            'failure_rate': float(1.0 - sub['is_valid'].mean()),
        })
    seed_df = pd.DataFrame(seed_summary)
    three_seed = {
        'pooled_J1_mean': float(seed_df['pooled_J1'].mean()),
        'pooled_J1_std': float(seed_df['pooled_J1'].std(ddof=0)),
        'J1_n7_mean': float(seed_df['J1_n7'].mean()),
        'J1_n10_mean': float(seed_df['J1_n10'].mean()),
        'J1_n20_mean': float(seed_df['J1_n20'].mean()),
    }
    log(f"  RAW specialist 3-seed: pooled J1 mean={three_seed['pooled_J1_mean']:.6f} "
        f"(std={three_seed['pooled_J1_std']:.6f})")
    log(f"    per-n mean: n7={three_seed['J1_n7_mean']:.6f} "
        f"n10={three_seed['J1_n10_mean']:.6f} n20={three_seed['J1_n20_mean']:.6f}")

    # References (Default/L1/L2/L6-hindsight) on pooled combo-holdout
    df_refs, refs = evaluate_references_all(df_full)
    ref_j1 = {m: math.sqrt(g['true_loss'].mean())
              for m, g in df_refs.groupby('model')}
    for m, j in ref_j1.items():
        log(f"  Reference {m}: J1={j:.6f}")

    # Persist pooled per-sample RAW selections (seed 42 + all seeds)
    df_all_sel.to_csv(os.path.join(OUTPUT_DIR, 'raw_specialist_results.csv'), index=False)
    seed_df.to_csv(os.path.join(OUTPUT_DIR, 'seed_stability.csv'), index=False)
    pd.DataFrame(build_split_rows()).to_csv(
        os.path.join(OUTPUT_DIR, 'split_report.csv'), index=False)

    # Diagnostics: use seed 42 as the representative, plus 3-seed pooled
    diag_rows = []
    near_summaries = {}
    for seed in SEEDS:
        sub = df_all_sel[df_all_sel['seed'] == seed].copy()
        tag = f'RAW-MLP-L6-seed{seed}'
        diag_rows.extend(endpoint_rows(sub, tag))
        # near-optimal from predictions files
        preds_frames = []
        for n_val in SPECIALIST_NS:
            for fold_idx in range(5):
                _, pp = checkpoint_paths(n_val, fold_idx, seed)
                preds_frames.append(pd.read_csv(pp))
        dfp = pd.concat(preds_frames, ignore_index=True)
        near_summaries[tag] = near_optimal_summary(dfp)
    pd.DataFrame(diag_rows).to_csv(
        os.path.join(DIAG_DIR, 'endpoint_diagnostics.csv'), index=False)

    # 3-seed pooled near-optimal
    all_preds_3seed = []
    for seed in SEEDS:
        for n_val in SPECIALIST_NS:
            for fold_idx in range(5):
                _, pp = checkpoint_paths(n_val, fold_idx, seed)
                all_preds_3seed.append(pd.read_csv(pp))
    dfp_all = pd.concat(all_preds_3seed, ignore_index=True)
    near_3seed = near_optimal_summary(dfp_all)
    dfp_all[['beta', 'gamma_over_eta', 'n', 'repeat_id', 'selected_delta',
             'true_loss', 'oracle_min_loss']].to_csv(
        os.path.join(DIAG_DIR, 'near_optimal_diagnostics.csv'), index=False)

    # Delta distribution (3-seed pooled)
    dist = (df_all_sel['selected_delta'].value_counts().sort_index()
            .rename('count').reset_index().rename(columns={'index': 'selected_delta'}))
    dist.to_csv(os.path.join(DIAG_DIR, 'delta_distribution.csv'), index=False)

    # model_comparison.csv (pooled, seed 42) + references
    comp_rows = []
    sub42 = df_all_sel[df_all_sel['seed'] == 42]
    comp_rows.append({
        'model': 'RAW-MLP-L6', 'split': 'combo_holdout_pooled', 'seed': 42,
        'J1': math.sqrt(sub42['true_loss'].mean()),
        'failure_rate': float(1.0 - sub42['is_valid'].mean()),
        'n_samples': len(sub42),
        **{f'J1_n{nv}': math.sqrt(g['true_loss'].mean())
           for nv, g in sub42.groupby('n_val')},
    })
    for m, j in ref_j1.items():
        comp_rows.append({'model': m, 'split': 'combo_holdout_pooled', 'seed': 'n/a',
                          'J1': j, 'failure_rate': 0.0,
                          'n_samples': int(len(df_refs[df_refs['model'] == m]))})
    pd.DataFrame(comp_rows).to_csv(
        os.path.join(OUTPUT_DIR, 'model_comparison.csv'), index=False)

    log("\n[7/7] Writing manifest + run log...")
    git_meta = get_git_metadata()

    # F13 comparison values (read from sealed formal artifacts, never overwritten)
    f13_path = os.path.join(ARTIFACTS_DIR, "E3b_vector_mlp", "seed_stability.csv")
    f13_comp_path = os.path.join(ARTIFACTS_DIR, "E3b_vector_mlp", "model_comparison.csv")
    f13_3seed = {}
    if os.path.exists(f13_path):
        df_f13 = pd.read_csv(f13_path)
        f13_3seed = {
            'pooled_J1_mean': float(df_f13['pooled_J1'].mean()),
            'J1_n7_mean': float(df_f13['J1_n7'].mean()),
            'J1_n10_mean': float(df_f13['J1_n10'].mean()),
            'J1_n20_mean': float(df_f13['J1_n20'].mean()),
            'per_seed': {int(r['seed']): {k: float(r[k]) for k in
                         ('pooled_J1', 'J1_n7', 'J1_n10', 'J1_n20', 'n_iter')}
                         for _, r in df_f13.iterrows()},
        }
    f13_seed42 = {}
    if os.path.exists(f13_comp_path):
        dfc = pd.read_csv(f13_comp_path)
        row = dfc[(dfc['model'] == 'Vector-MLP-L6') & (dfc['split'] == 'combo_holdout_pooled')]
        if len(row):
            r = row.iloc[0]
            f13_seed42 = {k: float(r[k]) for k in
                          ('J1', 'J1_n7', 'J1_n10', 'J1_n20') if k in r}

    manifest = {
        'run_id': CONTRACT_VERSION,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'code_entry': 'code/run_E3b_RAW_specialist.py',
        'route_description': 'RAW representation + per-n specialist training',
        'comparison_framing': ('Difference vs F13 reflects BOTH representation '
                               '(raw sample vs 13 features) AND training organization '
                               '(per-n specialist vs joint). Not attributable to RAW alone.'),
        'python_version': sys.version.split()[0],
        'sklearn_version': __import__('sklearn').__version__,
        'numpy_version': np.__version__,
        'pandas_version': pd.__version__,
        **git_meta,
        'data_source': {
            'mc_chunks': 'artifacts/formal/shared_data/chunks/chunk_*_mdm.csv (45 units)',
            'mc_manifest': 'artifacts/formal/shared_data/manifest.json',
            'note': 'Chunks concatenate to the gitignored mc_scan_raw.csv; no MDM rerun.',
        },
        'sample_reconstruction': {
            'function': 'generate_sample(beta, eta, gamma, n, repeat_id, seed)',
            'seed_namespace': SEED_NAMESPACE,
            'verification_probe': sample_probe,
        },
        'input_contract': {
            'representation': 'ascending-sorted raw sample values',
            'input_dim_per_n': {int(n): int(n) for n in SPECIALIST_NS},
            'no_padding': True, 'no_mask': True, 'no_explicit_n': True,
            'no_hand_crafted_stats': True, 'no_true_parameters': True,
            'banned_fields_excluded': sorted(BANNED_FIELDS),
            'input_standardizer': 'sklearn StandardScaler, per-position, '
                                  'fit on train fold of that n only',
        },
        'label_contract': {
            'target': '26-dim per-sample L6 loss curve (loss_filled)',
            'loss': '((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2',
            'failure_penalty': 'p99(valid training loss) from FULL train fold (all n), identical to E3b',
            'target_scaling': 'StandardScaler 26-dim, fit on train fold of that n only',
            'J1': 'sqrt(mean_i(true_loss_i(delta_hat_i)))',
        },
        'split_contract': {
            'folds': 'deterministic 5-fold full-combo holdout over (beta, gamma/eta, n), identical to E3b',
            'combos_total': 45, 'test_combos_per_fold': 9,
            'train_test_disjoint': True,
            'per_n_per_fold_test_samples': '(#test combos with that n) x 1000',
        },
        'training_contract': {
            'models_total': 45, 'ns': SPECIALIST_NS, 'folds': 5, 'seeds': SEEDS,
            'mlp': {'hidden_layer_sizes': list(MLP_HIDDEN_LAYERS),
                    'activation': 'relu', 'solver': 'adam', 'alpha': MLP_ALPHA,
                    'learning_rate_init': MLP_LR, 'max_iter': MLP_MAX_ITER,
                    'early_stopping': True,
                    'validation_fraction': MLP_VALIDATION_FRACTION,
                    'n_iter_no_change': MLP_N_ITER_NO_CHANGE,
                    'batch_size': MLP_BATCH_SIZE},
            'checkpoint_resume': 'per (n, fold, seed) JSON+CSV checkpoint; '
                                 'rerun skips valid checkpoints',
        },
        'data_integrity': integrity,
        'results': {
            'raw_3seed': three_seed,
            'raw_per_seed': seed_summary,
            'references_j1': ref_j1,
            'near_optimal_3seed': near_3seed,
            'runtimes_s': {'total': float(sum(runtimes)) if runtimes else 0.0,
                           'mean': float(np.mean(runtimes)) if runtimes else 0.0,
                           'min': float(np.min(runtimes)) if runtimes else 0.0,
                           'max': float(np.max(runtimes)) if runtimes else 0.0},
            'n_iters': {'mean': float(np.mean(n_iters)) if n_iters else 0.0,
                        'min': int(np.min(n_iters)) if n_iters else 0,
                        'max': int(np.max(n_iters)) if n_iters else 0},
        },
        'comparison_f13': {
            'f13_3seed': f13_3seed,
            'f13_seed42': f13_seed42,
            'raw_3seed': three_seed,
            'pooled_delta_raw_minus_f13': (
                three_seed['pooled_J1_mean'] - f13_3seed.get('pooled_J1_mean', float('nan'))
                if f13_3seed else None),
        },
        'model_files': {
            m['model_id']: {
                'n': m['n'], 'fold': m['fold'], 'seed': m['seed'],
                'input_dim': m['input_dim'], 'n_iter': m['n_iter'],
                'runtime_s': m['runtime_s'],
                'J1': m['metrics']['J1'],
                'predictions_csv': f"predictions/{m['model_id']}.csv",
                'predictions_sha256': m['predictions_sha256'],
                'meta_json': f"models/{m['model_id']}.json",
            } for m in all_meta
        },
        'output_files': [
            'manifest.json', 'summary.json', 'run_log.txt',
            'raw_specialist_results.csv', 'model_comparison.csv',
            'seed_stability.csv', 'split_report.csv',
            'diagnostics/endpoint_diagnostics.csv',
            'diagnostics/near_optimal_diagnostics.csv',
            'diagnostics/delta_distribution.csv',
            'models/*.json', 'predictions/*.csv', 'plots/*.png',
        ],
        'boundary': 'Writes only to artifacts/candidate/E3b_RAW_specialist/. '
                    'Never modifies artifacts/formal/E3b_vector_mlp/ or sealed E3/E4.',
    }
    with open(os.path.join(OUTPUT_DIR, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)

    summary = {
        'experiment': 'E3b_RAW_specialist (candidate)',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'raw_3seed': three_seed,
        'references_j1': ref_j1,
        'f13_3seed': f13_3seed.get('pooled_J1_mean') if f13_3seed else None,
        'near_optimal_3seed': near_3seed,
        'seed_table': seed_summary,
        'n_models': len(all_meta),
        'runtimes': manifest['results']['runtimes_s'],
        'n_iters': manifest['results']['n_iters'],
    }
    with open(os.path.join(OUTPUT_DIR, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    with open(os.path.join(OUTPUT_DIR, 'run_log.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(buf))

    elapsed = time.time() - t_start
    log(f"\nDone in {elapsed:.1f}s. Outputs in {OUTPUT_DIR}")
    return manifest


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--force-rerun', action='store_true',
                    help='Ignore checkpoints and retrain all 45 models.')
    args = ap.parse_args()
    run_experiment(force_rerun=args.force_rerun)
