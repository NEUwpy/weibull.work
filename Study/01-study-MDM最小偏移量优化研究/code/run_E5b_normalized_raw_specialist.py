"""
Study/01 Formal E5b — Normalized-RAW per-n specialist（最终样本自适应方法）

方法（冻结）：
    排序并归一化的完整样本 Z_n = (x_(1)/mean(x), ..., x_(n)/mean(x))
    -> 按样本量 n 分别训练的 MLP（n=7,10,15,20，独立网络，无 padding/mask）
    -> 预测 26 点候选偏移量损失曲线
    -> 选择预测损失最低的偏移量 delta_hat
    -> 使用 MDM 完成三参数估计。

输入合同：
  - 每个样本升序排列后除以样本均值，得到 Z_n（尺度无关，维数 = n）。
  - 不输入手工统计特征、不输入 n、真参数、组合编号或 repeat_id。
  - 每个 n 使用独立 MLP（输入维 = n），不使用 padding、mask 或跨 n 联合网络。

训练/评价合同（复用既有正式合同）：
  - 目标：26 维逐样本 L6 损失曲线（loss_filled；失败候选以训练折 p99 失败惩罚填充）。
  - 损失：((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + ((gamma_hat-gamma)/eta)^2。
  - J1 = sqrt(mean_i(true_loss_i(delta_hat_i)))。
  - delta grid：0.00~0.50，26 点；Default delta = 0.1。
  - 每个 n 内按完整 (beta, gamma/eta) 组合五折留出；seeds {42, 2026, 3407}。
  - MLP：(256,128,64) ReLU/Adam，early stopping，max_iter=300，batch=256，
    alpha=1e-4，lr=1e-3，validation_fraction=0.15，n_iter_no_change=20。
  - 输入每位置 StandardScaler（训练折拟合）与 26 维目标 StandardScaler（训练折拟合）。

模型职责：
  - 折模型（n x fold x seed）：用于组合留出评价，每个样本在其留出折内计分一次。
  - 最终模型（n x 1）：全开发集（该 n 全部样本）训练，seed 预先固定
    （nrmc_config.FINAL_DEV_SEED，不根据测试结果选择），作为部署使用模型。

设计（--design）：
  - formal : nrmc_config 冻结设计（160 组合 x 300 重复），读新分片，
             写 artifacts/formal/E5_normalized_raw/specialist/。
  - pilot  : 既有 45 组合缓存（config.py 网格，n=7,10,20，1000 重复），
             验证输入/训练/尺度检查在现有缓存上可用，写 artifacts/pilot/E5_normalized_raw/。

用法：
    python run_E5b_normalized_raw_specialist.py --design formal
    python run_E5b_normalized_raw_specialist.py --design pilot
    python run_E5b_normalized_raw_specialist.py --design pilot --force-rerun
"""

import sys
import os
import json
import time
import math
import hashlib
import warnings
import subprocess
from datetime import datetime, timezone
from itertools import product

import numpy as np
import pandas as pd
from sklearn.exceptions import ConvergenceWarning

# ============================================================
# Path setup
# ============================================================

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

import nrmc_config as NRMC
import config as OLD_CONFIG
from studies.common.sample import generate_sample

N_DELTAS = 26  # len(DELTA_GRID) — both designs share the same 26-point grid
SAMPLE_KEYS = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
SEEDS = NRMC.STABILITY_SEEDS
NEAR_OPTIMAL_EPS = [0.01, 0.02, 0.05]
ENDPOINT_DELTAS = [0.00, 0.02, 0.48, 0.50]
BANNED_FIELDS = {'beta', 'eta', 'gamma', 'gamma_over_eta',
                 'seed', 'repeat_id', 'combo_id', 'delta', 'n'}
CONTRACT_VERSION = "E5_normalized_raw_specialist_v1"


# ============================================================
# Design registry (formal + pilot)
# ============================================================

def get_design(name):
    """返回一个设计配置 dict。formal 为冻结正式设计，pilot 为既有缓存验证。"""
    name = name.lower()
    if name == 'formal':
        return {
            'name': 'formal',
            'label': 'Normalized-RAW-MLP (formal)',
            'beta_grid': list(NRMC.BETA_GRID),
            'eta_grid': [NRMC.ETA],
            'gamma_over_eta_grid': list(NRMC.GAMMA_OVER_ETA_GRID),
            'n_grid': list(NRMC.N_GRID),
            'repeats': NRMC.REPEATS,
            'seed_namespace': NRMC.SEED_NAMESPACE,
            'chunks_dir': NRMC.CHUNKS_DIR,
            'mc_manifest': NRMC.MC_MANIFEST_PATH,
            'output_dir': NRMC.SPECIALIST_DIR,
        }
    if name == 'pilot':
        return {
            'name': 'pilot',
            'label': 'Normalized-RAW-MLP (pilot on existing 45-combo cache)',
            'beta_grid': list(OLD_CONFIG.BETA_GRID),
            'eta_grid': list(OLD_CONFIG.ETA_GRID),
            'gamma_over_eta_grid': list(OLD_CONFIG.GAMMA_OVER_ETA_GRID),
            'n_grid': list(OLD_CONFIG.N_GRID),
            'repeats': OLD_CONFIG.R_MAIN,
            'seed_namespace': OLD_CONFIG.SEED_NAMESPACE,
            'chunks_dir': OLD_CONFIG.SHARED_DATA_DIR + os.sep + 'chunks',
            'mc_manifest': OLD_CONFIG.SHARED_DATA_DIR + os.sep + 'manifest.json',
            'output_dir': os.path.join(STUDY_ROOT, "artifacts", "pilot",
                                       "E5_normalized_raw"),
        }
    raise ValueError(f"Unknown design: {name} (expected 'formal' | 'pilot')")


DELTA_GRID = list(NRMC.DELTA_GRID)
DEFAULT_DELTA = NRMC.DEFAULT_DELTA


# ============================================================
# Data loading
# ============================================================

def list_mdm_chunks(chunks_dir):
    chunks = sorted(
        f for f in os.listdir(chunks_dir)
        if f.startswith("chunk_") and f.endswith("_mdm.csv")
    )
    return [os.path.join(chunks_dir, c) for c in chunks]


def load_mc_scan(chunks_dir):
    dtypes = {
        'beta': 'float64', 'eta': 'float64', 'gamma': 'float64',
        'gamma_over_eta': 'float64', 'n': 'int64', 'repeat_id': 'int64',
        'delta': 'float64', 'beta_hat': 'float64', 'eta_hat': 'float64',
        'gamma_hat': 'float64', 'r_squared': 'float64',
        'converged': 'boolean', 'time_ms': 'float64',
    }
    frames = []
    for p in list_mdm_chunks(chunks_dir):
        frames.append(pd.read_csv(p, dtype=dtypes))
    if not frames:
        raise FileNotFoundError(f"No chunk_*_mdm.csv under {chunks_dir}")
    return pd.concat(frames, ignore_index=True)


def verify_data_integrity(df, design, manifest):
    expected_combos = (
        len(design['beta_grid']) * len(design['gamma_over_eta_grid'])
        * len(design['n_grid'])
    )
    expected_rows = expected_combos * N_DELTAS * design['repeats']
    assert len(df) == expected_rows, \
        f"Row count: expected {expected_rows}, got {len(df)}"
    dup_key = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id', 'delta']
    assert df.duplicated(subset=dup_key).sum() == 0, "duplicate rows"
    unique_combos = df[['beta', 'gamma_over_eta', 'n']].drop_duplicates()
    assert len(unique_combos) == expected_combos, "combo coverage mismatch"
    assert sorted(df['delta'].unique()) == DELTA_GRID, "delta grid mismatch"
    rep_counts = df.groupby(['beta', 'gamma_over_eta', 'n'])['repeat_id'].nunique()
    assert rep_counts.min() == design['repeats'], "repeat coverage mismatch"
    # design grid containment
    assert set(df['beta'].unique()) == set(design['beta_grid']), "beta grid mismatch"
    assert set(df['gamma_over_eta'].unique()) == set(design['gamma_over_eta_grid']), \
        "gamma/eta grid mismatch"
    assert set(df['n'].unique()) == set(design['n_grid']), "n grid mismatch"
    return {
        'expected_rows': int(expected_rows), 'actual_rows': int(len(df)),
        'duplicate_rows': int(df.duplicated(subset=dup_key).sum()),
        'unique_combos': int(len(unique_combos)),
        'delta_points': int(len(DELTA_GRID)),
        'repeat_min': int(rep_counts.min()),
        'repeat_max': int(rep_counts.max()),
        'non_success_rate': float((df['status'] != 'success').mean()),
    }


# ============================================================
# Normalization: Z_n = sorted(x)/mean(x)   (the ONLY input transform)
# ============================================================

def normalize_sample(sample):
    """返回升序排列并除以样本均值的归一化样本 Z_n（尺度无关，维数 = n）。"""
    s = np.sort(np.asarray(sample, dtype=float))
    m = s.mean()
    assert m > 0, "sample mean must be positive"
    return s / m


def build_normalized_sample_map(df_mc, design):
    """为每个唯一样本键重建升序原始样本，并存储归一化向量 Z_n。

    注意：generate_sample 使用设计专属 seed 命名空间，保证与数据分片同源。
    """
    seed_ns = design['seed_namespace']
    keys_df = (
        df_mc[SAMPLE_KEYS].drop_duplicates().sort_values(SAMPLE_KEYS)
        .reset_index(drop=True)
    )
    print(f"[NRMC] Reconstructing {len(keys_df)} normalized samples "
          f"(seed_namespace={seed_ns})...")
    norm_map = {}
    raw_check = {}
    t0 = time.time()
    for _, row in keys_df.iterrows():
        beta = float(row['beta']); eta = float(row['eta'])
        gamma = float(row['gamma']); n = int(row['n'])
        rid = int(row['repeat_id'])
        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_ns)
        s = np.sort(sample)
        assert np.allclose(s, sample), "generate_sample not ascending-sorted"
        assert len(s) == n, "sample length mismatch"
        norm_map[(beta, eta, gamma, float(row['gamma_over_eta']), n, rid)] = \
            normalize_sample(s)
        raw_check[(beta, eta, gamma, float(row['gamma_over_eta']), n, rid)] = \
            s.astype(np.float64)
    print(f"[NRMC] Done in {time.time() - t0:.1f}s")
    return norm_map, keys_df


# ============================================================
# Loss + failure handling (reuse formal contract)
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
# 5-fold full-combo holdout over (beta, gamma/eta, n)
# ============================================================

def get_combo_split(design):
    combos = list(product(design['beta_grid'], design['gamma_over_eta_grid'],
                          design['n_grid']))
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


def build_split_rows(design):
    rows = []
    for fold in get_combo_split(design):
        for combo in fold['test_combos']:
            rows.append({'fold': fold['fold_name'],
                         'test_beta': combo[0],
                         'test_gamma_over_eta': combo[1],
                         'test_n': combo[2]})
    return rows


def prepare_fold(df_full, fold):
    train_combo_set = set(fold['train_combos'])
    test_combo_set = set(fold['test_combos'])
    assert not (train_combo_set & test_combo_set), "train/test combo overlap"

    combo_str = (df_full['beta'].astype(str) + '|' +
                 df_full['gamma_over_eta'].astype(str) + '|' +
                 df_full['n'].astype(str))
    train_strs = set(f'{b}|{g}|{n}' for b, g, n in train_combo_set)
    test_strs = set(f'{b}|{g}|{n}' for b, g, n in test_combo_set)
    df_tr = df_full[combo_str.isin(train_strs)].copy()
    df_te = df_full[combo_str.isin(test_strs)].copy()

    # failure penalty from FULL train fold (all n), identical to E3b
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


# ============================================================
# Pivot: normalized vectors -> per-n specialist data
# ============================================================

def pivot_norm_vector(df_long, norm_map, n_val):
    """按 n=n_val 把长表折成 (keys, X=Z_n 归一化输入, Y=26维曲线, valid)。

    CRITICAL: keys 行 i、X 行 i、Y 行 i 严格描述同一样本。
    """
    sub = df_long[df_long['n'] == n_val]
    keys = (sub[SAMPLE_KEYS].drop_duplicates().sort_values(SAMPLE_KEYS)
            .reset_index(drop=True))

    X = np.zeros((len(keys), n_val), dtype=np.float64)
    for i, r in keys.iterrows():
        key = (float(r['beta']), float(r['eta']), float(r['gamma']),
               float(r['gamma_over_eta']), int(r['n']), int(r['repeat_id']))
        X[i] = norm_map[key]
    assert X.shape[1] == n_val, "normalized input width must equal n"

    Y = np.full((len(keys), N_DELTAS), np.nan, dtype=np.float64)
    valid_any = np.zeros(len(keys), dtype=bool)
    lookup = sub.set_index(SAMPLE_KEYS + ['delta'])['loss_filled']
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
# Training
# ============================================================

def train_specialist(X_train, Y_train, X_test, seed):
    """训练 (256,128,64) Vector-MLP：输入 Z_n（每位置 StandardScaler），
    输出 26 维损失曲线（目标 StandardScaler，反变换回原尺度）。"""
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
            hidden_layer_sizes=NRMC.MLP_HIDDEN_LAYERS,
            activation='relu', solver='adam',
            alpha=NRMC.MLP_ALPHA, learning_rate_init=NRMC.MLP_LR,
            max_iter=NRMC.MLP_MAX_ITER, early_stopping=True,
            validation_fraction=NRMC.MLP_VALIDATION_FRACTION,
            n_iter_no_change=NRMC.MLP_N_ITER_NO_CHANGE,
            random_state=seed, batch_size=NRMC.MLP_BATCH_SIZE,
        )
        model.fit(X_train_s, Y_train_s)

    Y_pred_s = model.predict(X_test_s)
    Y_pred = target_scaler.inverse_transform(Y_pred_s)
    Y_pred = np.clip(Y_pred, 0.0, None)
    return Y_pred, model.n_iter_, input_scaler, target_scaler, model


def evaluate_selection(keys_df, Y_pred, Y_true, model_name, valid_any):
    best_idx = np.argmin(Y_pred, axis=1)
    sel_delta = np.array([DELTA_GRID[i] for i in best_idx])
    true_loss = Y_true[np.arange(len(keys_df)), best_idx]
    rows = []
    for i in range(len(keys_df)):
        r = keys_df.iloc[i]
        rows.append({
            'beta': float(r['beta']), 'eta': float(r['eta']),
            'gamma': float(r['gamma']), 'gamma_over_eta': float(r['gamma_over_eta']),
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
# References (Default / L1 / L2 / L6-hindsight) on the same test set
# ============================================================

def compute_reference_deltas(df, design):
    default_delta = DEFAULT_DELTA
    global_loss = df.groupby('delta')['loss'].apply(lambda x: np.sqrt(np.nanmean(x)))
    l1_delta = float(global_loss.idxmin())
    l2_table = {}
    for n_val in design['n_grid']:
        loss_by_delta = df[df['n'] == n_val].groupby('delta')['loss'].apply(
            lambda x: np.sqrt(np.nanmean(x)))
        l2_table[n_val] = {'delta_star': float(loss_by_delta.idxmin()),
                           'J1': float(loss_by_delta.min())}
    return {'default_delta': default_delta, 'l1_delta': l1_delta,
            'l2_table': l2_table}


def evaluate_references_all(df_full, design):
    """在组合留出的 pooled 测试集上计算 Default/L1/L2/L6-hindsight。"""
    refs = compute_reference_deltas(df_full, design)
    folds = get_combo_split(design)
    recs = []
    for fold in folds:
        fp = prepare_fold(df_full, fold)
        df_te = fp['df_test']
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
            base = {'beta': float(r['beta']), 'eta': float(r['eta']),
                    'gamma': float(r['gamma']),
                    'gamma_over_eta': float(r['gamma_over_eta']),
                    'n': int(r['n']), 'repeat_id': int(r['repeat_id']),
                    'is_valid': True}
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
# Checkpoint / resume
# ============================================================

def model_id(n_val, fold_idx, seed):
    return f"n{n_val}_fold{fold_idx + 1}_seed{seed}"


def checkpoint_paths(out_dir, n_val, fold_idx, seed):
    mid = model_id(n_val, fold_idx, seed)
    return (os.path.join(out_dir, "models", f"{mid}.json"),
            os.path.join(out_dir, "predictions", f"{mid}.csv"))


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(1 << 20), b''):
            h.update(block)
    return h.hexdigest()


def sha256_file_lf(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        prev = b''
        while True:
            block = f.read(1 << 20)
            if not block:
                break
            data = prev + block
            data = data.replace(b'\r\n', b'\n')
            prev = data[-1:] if data.endswith(b'\r') else b''
            h.update(data[:-1] if prev else data)
        if prev:
            h.update(prev)
    return h.hexdigest()


def checkpoint_valid(out_dir, n_val, fold_idx, seed, expected_test_n,
                     test_keys_sha, delta_sha, code_sha):
    mpath, ppath = checkpoint_paths(out_dir, n_val, fold_idx, seed)
    if not (os.path.exists(mpath) and os.path.exists(ppath)):
        return False
    try:
        meta = json.load(open(mpath, encoding='utf-8'))
    except Exception:
        return False
    if meta.get('contract_version') != CONTRACT_VERSION:
        return False
    if meta.get('n') != int(n_val) or meta.get('fold') != int(fold_idx + 1) \
            or meta.get('seed') != int(seed):
        return False
    if meta.get('input_dim') != int(n_val):
        return False
    if meta.get('test_n_samples') != int(expected_test_n):
        return False
    if meta.get('test_sample_keys_sha256') != test_keys_sha:
        return False
    if meta.get('delta_grid_sha256') != delta_sha:
        return False
    if meta.get('code_sha256') != code_sha:
        return False
    if meta.get('predictions_sha256') != sha256_file_lf(ppath):
        return False
    try:
        dfp = pd.read_csv(ppath)
    except Exception:
        return False
    if len(dfp) != expected_test_n:
        return False
    pred_cols = [f'pred_d{d}' for d in DELTA_GRID]
    if not all(c in dfp.columns for c in pred_cols):
        return False
    if int(dfp['n'].iloc[0]) != int(n_val):
        return False
    return True


def compute_test_keys_sha(n_val, fold_idx, design):
    fold = get_combo_split(design)[fold_idx]
    test_combos_n = sorted(c for c in fold['test_combos'] if c[2] == n_val)
    key_tuples = sorted((float(b), float(g), int(n), int(rid))
                        for (b, g, n) in test_combos_n
                        for rid in range(design['repeats']))
    return hashlib.sha256(json.dumps(key_tuples).encode()).hexdigest()


def delta_grid_sha256():
    return hashlib.sha256(json.dumps(list(DELTA_GRID)).encode()).hexdigest()


def code_sha256():
    return sha256_file_lf(os.path.abspath(__file__))


def save_checkpoint(out_dir, n_val, fold_idx, seed, metrics, n_iter, runtime_s,
                    input_scaler_mean, input_scaler_std,
                    target_scaler_mean, target_scaler_std,
                    df_sel, Y_pred, Y_true, keys_df, failure_penalty,
                    train_n, test_n, test_keys_sha, delta_sha, code_sha):
    os.makedirs(os.path.join(out_dir, "models"), exist_ok=True)
    os.makedirs(os.path.join(out_dir, "predictions"), exist_ok=True)
    mid = model_id(n_val, fold_idx, seed)
    mpath, ppath = checkpoint_paths(out_dir, n_val, fold_idx, seed)

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
        'input_scaler_fit': 'train fold of this n only (per-position StandardScaler on Z_n)',
        'target_scaler_fit': 'train fold of this n only (26-dim StandardScaler)',
        'predictions_sha256': sha256_file_lf(ppath),
        'test_sample_keys_sha256': test_keys_sha,
        'delta_grid_sha256': delta_sha,
        'code_sha256': code_sha,
    }
    with open(mpath, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta


def run_one(n_val, fold_idx, seed, df_full, norm_map, fold_prep_cache, design, log):
    fold = get_combo_split(design)[fold_idx]
    fp = fold_prep_cache[fold_idx]
    df_train, df_test = fp['df_train'], fp['df_test']
    failure_penalty = fp['failure_penalty']

    test_combos_n = [c for c in fold['test_combos'] if c[2] == n_val]
    expected_test_n = len(test_combos_n) * design['repeats']

    mid = model_id(n_val, fold_idx, seed)
    tks = compute_test_keys_sha(n_val, fold_idx, design)
    dgs = delta_grid_sha256()
    ccs = code_sha256()
    out_dir = design['output_dir']
    if checkpoint_valid(out_dir, n_val, fold_idx, seed, expected_test_n,
                        tks, dgs, ccs):
        log(f"  [skip] {mid} (valid checkpoint, test_n={expected_test_n})")
        mpath, ppath = checkpoint_paths(out_dir, n_val, fold_idx, seed)
        meta = json.load(open(mpath, encoding='utf-8'))
        df_sel = pd.read_csv(ppath)
        return {'skipped': True, 'meta': meta, 'df_sel': df_sel}

    keys_tr, X_tr, Y_tr, _ = pivot_norm_vector(df_train, norm_map, n_val)
    keys_te, X_te, Y_te, valid_te = pivot_norm_vector(df_test, norm_map, n_val)
    assert X_tr.shape[1] == n_val and X_te.shape[1] == n_val
    assert X_te.shape[0] == expected_test_n, \
        f"test sample mismatch {X_te.shape[0]} vs {expected_test_n}"

    # No-leak contract: Z input is scale-free and contains no keys.
    assert not np.any(np.isnan(X_tr)), "NaN in normalized input"

    t0 = time.time()
    Y_pred, n_iter, in_sc, tg_sc, _model = train_specialist(
        X_tr, Y_tr, X_te, seed)
    runtime = time.time() - t0
    df_sel, metrics = evaluate_selection(
        keys_te, Y_pred, Y_te, f'Normalized-RAW-{mid}', valid_te)
    meta = save_checkpoint(
        out_dir, n_val, fold_idx, seed, metrics, n_iter, runtime,
        in_sc.mean_, in_sc.scale_, tg_sc.mean_, tg_sc.scale_,
        df_sel, Y_pred, Y_te, keys_te, failure_penalty,
        len(keys_tr), len(keys_te), tks, dgs, ccs)
    log(f"  [done] {mid}: J1={metrics['J1']:.6f} n_iter={n_iter} "
        f"t={runtime:.1f}s (train={len(keys_tr)}, test={len(keys_te)})")
    return {'skipped': False, 'meta': meta, 'df_sel': df_sel,
            'runtime_s': runtime, 'n_iter': n_iter}


# ============================================================
# Final full-development models (deployable; per n, fixed seed)
# ============================================================

def _serialize_mlp(model):
    return {
        'coefs_': [[[float(v) for v in row] for row in W] for W in model.coefs_],
        'intercepts_': [[float(v) for v in b] for b in model.intercepts_],
    }


def train_final_model(n_val, df_full, norm_map, design, log):
    """在全开发集（该 n 全部样本）上训练一个部署模型，seed 预先固定。"""
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPRegressor

    out_dir = design['output_dir']
    fdir = os.path.join(out_dir, "final_models")
    os.makedirs(fdir, exist_ok=True)
    fpath = os.path.join(fdir, f"n{n_val}_final.json")

    # Full dev set failure handling (same contract, computed from the full dev set)
    dev_valid_loss = df_full[df_full['n'] == n_val]['loss'].dropna()
    dev_failure_penalty = float(np.nanpercentile(dev_valid_loss, 99))
    dev = df_full[df_full['n'] == n_val].copy()
    dev['loss_filled'] = dev['loss'].fillna(dev_failure_penalty)
    dev['is_valid'] = dev.get('status', 'success').eq('success') & dev['loss'].notna()

    keys, X, Y, valid = pivot_norm_vector(dev, norm_map, n_val)
    # all samples of this n are training samples for the final model
    input_scaler = StandardScaler()
    X_s = input_scaler.fit_transform(X)
    target_scaler = StandardScaler()
    Y_s = target_scaler.fit_transform(Y)

    seed = NRMC.FINAL_DEV_SEED
    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=ConvergenceWarning)
        model = MLPRegressor(
            hidden_layer_sizes=NRMC.MLP_HIDDEN_LAYERS,
            activation='relu', solver='adam',
            alpha=NRMC.MLP_ALPHA, learning_rate_init=NRMC.MLP_LR,
            max_iter=NRMC.MLP_MAX_ITER, early_stopping=True,
            validation_fraction=NRMC.MLP_VALIDATION_FRACTION,
            n_iter_no_change=NRMC.MLP_N_ITER_NO_CHANGE,
            random_state=seed, batch_size=NRMC.MLP_BATCH_SIZE,
        )
        model.fit(X_s, Y_s)
    runtime = time.time() - t0

    meta = {
        'contract_version': CONTRACT_VERSION,
        'model_id': f"n{n_val}_final",
        'n': int(n_val), 'input_dim': int(n_val),
        'seed': int(seed), 'n_iter': int(model.n_iter_),
        'runtime_s': float(runtime),
        'train_n_samples': int(len(keys)),
        'dev_failure_penalty': float(dev_failure_penalty),
        'train_set': 'full development set (all samples of this n)',
        'role': ('deployment model: trained on full dev set with pre-fixed seed. '
                 'Hold-out performance is estimated by the fold models, not by this '
                 'model itself.'),
        'input_scaler_mean': [float(v) for v in np.asarray(input_scaler.mean_).ravel()],
        'input_scaler_std': [float(v) for v in np.asarray(input_scaler.scale_).ravel()],
        'target_scaler_mean': [float(v) for v in np.asarray(target_scaler.mean_).ravel()],
        'target_scaler_std': [float(v) for v in np.asarray(target_scaler.scale_).ravel()],
        'mlp_weights': _serialize_mlp(model),
        'delta_grid': list(DELTA_GRID),
        'normalization': 'Z_n = sorted(x)/mean(x) per sample; '
                         'per-position StandardScaler fit on full dev set',
    }
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    log(f"  [final] n{n_val}: n_iter={model.n_iter_} t={runtime:.1f}s "
        f"train={len(keys)}")
    return meta, model, input_scaler, target_scaler, X, Y


# ============================================================
# Scale-invariance check (representative samples; no multi-scale training)
# ============================================================

def run_scale_invariance_check(design, norm_map, final_models, log):
    """对代表性样本（每个 n 各取一个）：整体乘以 0.001/1/1000 后，
    归一化输入一致，且最终模型所选偏移量在数值容差内一致。"""
    from sklearn.preprocessing import StandardScaler

    out_dir = design['output_dir']
    os.makedirs(out_dir, exist_ok=True)
    scales = [0.001, 1.0, 1000.0]
    tol = 1e-9

    # pick one representative sample key per n
    rep_keys = {}
    for n_val in design['n_grid']:
        for k, v in norm_map.items():
            if k[4] == n_val:
                rep_keys[n_val] = k
                break
    assert set(rep_keys) == set(design['n_grid']), "representative sample per n missing"

    results = []
    all_ok = True
    for n_val, key in sorted(rep_keys.items()):
        beta, eta, gamma, goe, n, rid = key
        # reconstruct the raw sample, then scale it
        sample = generate_sample(beta, eta, gamma, n, rid,
                                 seed=design['seed_namespace'])
        if n_val not in final_models:
            continue
        meta, model, input_scaler, target_scaler, _, _ = final_models[n_val]
        z_orig = normalize_sample(sample)

        norm_consistent = True
        deltas = []
        for c in scales:
            z_c = normalize_sample(c * sample)
            if not np.allclose(z_c, z_orig, rtol=tol, atol=tol):
                norm_consistent = False
            # predict with the final model
            x = z_c.reshape(1, -1)
            x_s = input_scaler.transform(x)
            y_pred_s = model.predict(x_s)
            y_pred = target_scaler.inverse_transform(y_pred_s)
            y_pred = np.clip(y_pred, 0.0, None)
            deltas.append(float(DELTA_GRID[int(np.argmin(y_pred))]))

        ok = norm_consistent and (len(set(deltas)) == 1)
        all_ok = all_ok and ok
        results.append({
            'n': int(n_val), 'sample_key': [float(beta), float(eta), float(gamma),
                                            float(goe), int(n), int(rid)],
            'scales': scales,
            'normalized_input_max_diff': float(
                max(np.max(np.abs(normalize_sample(c * sample) - z_orig))
                    for c in scales)),
            'selected_deltas_per_scale': deltas,
            'normalized_input_consistent': bool(norm_consistent),
            'selected_delta_consistent': bool(len(set(deltas)) == 1),
            'ok': bool(ok),
        })
        log(f"  [scale-check] n={n_val}: deltas={deltas} "
            f"norm_diff={results[-1]['normalized_input_max_diff']:.2e} "
            f"ok={ok}")

    out = {
        'method': 'same sample scaled by {0.001, 1, 1000}; normalized input and '
                  'selected delta must match within tolerance',
        'tolerance': tol,
        'representative_samples': results,
        'all_ok': all_ok,
        'note': 'normalized input Z = x/mean(x) is scale-free by construction; '
                'this check confirms the full pipeline (scaler+MLP+argmin) '
                'introduces no scale dependence.',
    }
    with open(os.path.join(out_dir, 'scale_invariance.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    if not all_ok:
        log("  [scale-check] *** FAILED ***")
    return out


# ============================================================
# Provenance
# ============================================================

def get_git_metadata():
    def run(args):
        try:
            return subprocess.check_output(args, cwd=PROJECT_ROOT,
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return ''
    return {
        'git_commit': run(['git', 'rev-parse', 'HEAD']),
        'git_commit_short': run(['git', 'rev-parse', '--short', 'HEAD']),
        'git_branch': run(['git', 'branch', '--show-current']),
        'workspace_dirty': bool(run(['git', 'status', '--short'])),
    }


def write_sha256sums(out_dir, project_root, mc_chunks, mc_manifest, extra_code):
    entries = []

    def add(abs_path):
        try:
            rel = os.path.relpath(abs_path, project_root)
            if rel.startswith('..'):
                rel = 'abs://' + abs_path.replace(os.sep, '/')
            entries.append((rel.replace(os.sep, '/'), sha256_file_lf(abs_path)))
        except ValueError:
            entries.append(('abs://' + abs_path.replace(os.sep, '/'),
                            sha256_file_lf(abs_path)))

    for p in mc_chunks:
        add(p)
    add(mc_manifest)
    add(os.path.abspath(__file__))
    for cp in extra_code:
        if os.path.exists(cp):
            add(cp)
    for root, _, files in os.walk(out_dir):
        for fn in files:
            if fn == 'SHA256SUMS':
                continue
            add(os.path.join(root, fn))

    entries.sort(key=lambda e: e[0])
    content = ''.join(f"{h}  {p}\n" for p, h in entries)
    with open(os.path.join(out_dir, 'SHA256SUMS'), 'w', encoding='utf-8',
              newline='\n') as f:
        f.write(content)
    return len(entries)


def lf_normalize_tree(out_dir):
    for root, _, files in os.walk(out_dir):
        for fn in files:
            if fn == 'SHA256SUMS' or not fn.endswith(('.csv', '.json', '.txt')):
                continue
            fp = os.path.join(root, fn)
            with open(fp, 'rb') as f:
                data = f.read()
            if b'\r\n' in data:
                with open(fp, 'wb') as f:
                    f.write(data.replace(b'\r\n', b'\n'))


# ============================================================
# Aggregation helpers
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
    oracle = df_preds['oracle_min_loss'].where(
        df_preds['oracle_min_loss'] > 1e-12, np.nan)
    rel = (df_preds['true_loss'] - df_preds['oracle_min_loss']) / oracle
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
# Main
# ============================================================

def log_lines():
    buf = []

    def _log(msg):
        print(msg, flush=True)
        buf.append(msg)
    return _log, buf


def run_experiment(design_name, force_rerun=False):
    design = get_design(design_name)
    out_dir = design['output_dir']
    for d in (out_dir, os.path.join(out_dir, "models"),
              os.path.join(out_dir, "predictions"),
              os.path.join(out_dir, "final_models"),
              os.path.join(out_dir, "diagnostics")):
        os.makedirs(d, exist_ok=True)
    log, buf = log_lines()

    log("=" * 72)
    log(f"Study/01 E5b — {design['label']}")
    log(f"Output: {out_dir}")
    log("=" * 72)
    t_start = time.time()

    log("\n[1/7] Loading MC scan chunks...")
    df_mc = load_mc_scan(design['chunks_dir'])
    with open(design['mc_manifest'], encoding='utf-8') as f:
        mc_manifest = json.load(f)
    log(f"  Loaded {len(df_mc):,} rows")

    log("\n[2/7] Integrity + reconstruction + normalization...")
    integrity = verify_data_integrity(df_mc, design, mc_manifest)
    log(f"  Integrity: {integrity}")
    norm_map, _keys = build_normalized_sample_map(df_mc, design)
    df_full = compute_per_sample_loss(df_mc)
    nan_loss = int(df_full['loss'].isna().sum())
    log(f"  NaN/invalid losses: {nan_loss} ({nan_loss/len(df_full)*100:.3f}%)")

    log("\n[3/7] Preparing 5 folds (failure_penalty per fold)...")
    folds = get_combo_split(design)
    fold_prep_cache = [prepare_fold(df_full, f) for f in folds]
    for i, fp in enumerate(fold_prep_cache):
        log(f"  fold{i+1}: train_combos={len(fp['train_combos'])} "
            f"test_combos={len(fp['test_combos'])} "
            f"failure_penalty={fp['failure_penalty']:.6f}")
    all_test = sorted(c for f in folds for c in f['test_combos'])
    assert len(all_test) == len(folds[0]['test_combos']) * 5 \
        and len(set(all_test)) == len(all_test), "fold test combos not a partition"

    log(f"\n[4/7] Training per-n specialists "
        f"({len(design['n_grid'])}n x 5fold x {len(SEEDS)}seed)...")
    all_meta, all_sel = [], []
    runtimes, n_iters = [], []
    for n_val in design['n_grid']:
        for fold_idx in range(5):
            for seed in SEEDS:
                if force_rerun:
                    mp, pp = checkpoint_paths(out_dir, n_val, fold_idx, seed)
                    for p in (mp, pp):
                        if os.path.exists(p):
                            os.remove(p)
                res = run_one(n_val, fold_idx, seed, df_full, norm_map,
                              fold_prep_cache, design, log)
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
    all_rt = [float(m['runtime_s']) for m in all_meta]
    all_it = [int(m['n_iter']) for m in all_meta]
    training_stats_all = {
        'models': len(all_meta),
        'runtime_s': {'total': float(np.sum(all_rt)),
                      'mean': float(np.mean(all_rt)),
                      'min': float(np.min(all_rt)),
                      'max': float(np.max(all_rt))},
        'n_iter': {'mean': float(np.mean(all_it)),
                   'min': int(np.min(all_it)), 'max': int(np.max(all_it))},
    }
    training_stats_this_run = {
        'models_trained': len(runtimes),
        'models_skipped_cached': len(all_meta) - len(runtimes),
        'runtime_s': {'total': float(np.sum(runtimes)) if runtimes else 0.0,
                      'mean': float(np.mean(runtimes)) if runtimes else 0.0},
    }
    expected_ids = {model_id(n, f, s)
                    for n in design['n_grid'] for f in range(5) for s in SEEDS}
    got_ids = {m['model_id'] for m in all_meta}
    assert not (expected_ids - got_ids), f"missing models: {sorted(expected_ids - got_ids)}"
    log(f"  All {len(got_ids)} fold models present")

    log("\n[5/7] Final full-development models (deployable, fixed seed)...")
    final_models = {}
    for n_val in design['n_grid']:
        meta, model, in_sc, tg_sc, Xf, Yf = train_final_model(
            n_val, df_full, norm_map, design, log)
        final_models[n_val] = (meta, model, in_sc, tg_sc, Xf, Yf)

    log("\n[6/7] Scale-invariance check (representative samples)...")
    scale_out = run_scale_invariance_check(
        design, norm_map, final_models, log)

    log("\n[7/7] Aggregation, references, provenance...")
    seed_summary = []
    for seed in SEEDS:
        sub = df_all_sel[df_all_sel['seed'] == seed]
        per_n = {int(nv): math.sqrt(g['true_loss'].mean())
                 for nv, g in sub.groupby('n_val')}
        seed_summary.append({
            'seed': seed, 'pooled_J1': math.sqrt(sub['true_loss'].mean()),
            **{f'J1_n{nv}': per_n.get(nv, float('nan'))
               for nv in design['n_grid']},
            'n_samples': len(sub),
            'endpoint_rate': float(
                sub['selected_delta'].isin(ENDPOINT_DELTAS).mean()),
            'failure_rate': float(1.0 - sub['is_valid'].mean()),
        })
    seed_df = pd.DataFrame(seed_summary)
    three_seed = {
        'pooled_J1_mean': float(seed_df['pooled_J1'].mean()),
        'pooled_J1_std': float(seed_df['pooled_J1'].std(ddof=0)),
        **{f'J1_n{nv}_mean': float(seed_df[f'J1_n{nv}'].mean())
           for nv in design['n_grid']},
    }
    log(f"  Normalized-RAW 3-seed: pooled J1 mean={three_seed['pooled_J1_mean']:.6f} "
        f"(std={three_seed['pooled_J1_std']:.6f})")
    log(f"    per-n mean: " + ", ".join(
        f"n{nv}={three_seed[f'J1_n{nv}_mean']:.6f}" for nv in design['n_grid']))

    df_refs, refs = evaluate_references_all(df_full, design)
    ref_j1 = {m: math.sqrt(g['true_loss'].mean())
              for m, g in df_refs.groupby('model')}
    for m, j in ref_j1.items():
        log(f"  Reference {m}: J1={j:.6f}")

    # relative improvement vs Default (3-seed mean vs Default)
    default_j1 = ref_j1.get('Default', float('nan'))
    rel_improve = (default_j1 - three_seed['pooled_J1_mean']) / default_j1

    df_all_sel.to_csv(os.path.join(out_dir, 'raw_specialist_results.csv'), index=False)
    seed_df.to_csv(os.path.join(out_dir, 'seed_stability.csv'), index=False)
    pd.DataFrame(build_split_rows(design)).to_csv(
        os.path.join(out_dir, 'split_report.csv'), index=False)

    diag_rows = []
    near_summaries = {}
    for seed in SEEDS:
        sub = df_all_sel[df_all_sel['seed'] == seed].copy()
        tag = f'Normalized-RAW-seed{seed}'
        diag_rows.extend(endpoint_rows(sub, tag))
        preds_frames = []
        for n_val in design['n_grid']:
            for fold_idx in range(5):
                _, pp = checkpoint_paths(out_dir, n_val, fold_idx, seed)
                preds_frames.append(pd.read_csv(pp))
        dfp = pd.concat(preds_frames, ignore_index=True)
        near_summaries[tag] = near_optimal_summary(dfp)
    pd.DataFrame(diag_rows).to_csv(
        os.path.join(out_dir, 'diagnostics', 'endpoint_diagnostics.csv'), index=False)

    tagged_frames = []
    for seed in SEEDS:
        for n_val in design['n_grid']:
            for fold_idx in range(5):
                _, pp = checkpoint_paths(out_dir, n_val, fold_idx, seed)
                d = pd.read_csv(pp)
                d['seed'] = seed
                d['fold'] = fold_idx + 1
                d['n_specialist'] = n_val
                d['model_id'] = model_id(n_val, fold_idx, seed)
                tagged_frames.append(d)
    dfp_all = pd.concat(tagged_frames, ignore_index=True)
    near_3seed = near_optimal_summary(dfp_all)
    near_cols = ['model_id', 'seed', 'fold', 'n_specialist',
                 'beta', 'gamma_over_eta', 'n', 'repeat_id',
                 'selected_delta', 'selected_delta_idx',
                 'true_loss', 'oracle_min_loss', 'pred_min']
    dfp_all[near_cols].to_csv(
        os.path.join(out_dir, 'diagnostics', 'near_optimal_diagnostics.csv'),
        index=False)

    dist = (df_all_sel['selected_delta'].value_counts().sort_index()
            .rename('count').reset_index().rename(columns={'index': 'selected_delta'}))
    dist.to_csv(os.path.join(out_dir, 'diagnostics', 'delta_distribution.csv'),
                index=False)

    comp_rows = []
    for seed in SEEDS:
        sub = df_all_sel[df_all_sel['seed'] == seed]
        comp_rows.append({
            'model': 'Normalized-RAW-MLP', 'split': 'combo_holdout_pooled',
            'seed': seed, 'J1': math.sqrt(sub['true_loss'].mean()),
            'failure_rate': float(1.0 - sub['is_valid'].mean()),
            'n_samples': len(sub),
            **{f'J1_n{nv}': math.sqrt(g['true_loss'].mean())
               for nv, g in sub.groupby('n_val')},
        })
    for m, j in ref_j1.items():
        comp_rows.append({'model': m, 'split': 'combo_holdout_pooled',
                          'seed': 'n/a', 'J1': j, 'failure_rate': 0.0,
                          'n_samples': int(len(df_refs[df_refs['model'] == m]))})
    pd.DataFrame(comp_rows).to_csv(
        os.path.join(out_dir, 'model_comparison.csv'), index=False)

    git_meta = get_git_metadata()
    manifest = {
        'run_id': CONTRACT_VERSION,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'code_entry': 'code/run_E5b_normalized_raw_specialist.py',
        'design': {
            'name': design['name'],
            'beta_grid': design['beta_grid'],
            'eta_grid': design['eta_grid'],
            'gamma_over_eta_grid': design['gamma_over_eta_grid'],
            'n_grid': design['n_grid'],
            'repeats': design['repeats'],
            'seed_namespace': design['seed_namespace'],
            'combos_total': (len(design['beta_grid'])
                             * len(design['gamma_over_eta_grid'])
                             * len(design['n_grid'])),
        },
        'method': {
            'representation': ('Z_n = ascending-sorted sample / sample mean '
                               '(scale-free, full normalized sample)'),
            'input_dim_per_n': {int(n): int(n) for n in design['n_grid']},
            'no_hand_crafted_stats': True,
            'no_padding': True, 'no_mask': True, 'no_explicit_n': True,
            'no_true_parameters': True, 'no_combo_id': True, 'no_repeat_id': True,
            'per_n_independent_network': True,
            'banned_fields_excluded': sorted(BANNED_FIELDS),
            'input_standardizer': ('per-position StandardScaler on Z_n, '
                                   'fit on train fold of that n only'),
        },
        'label_contract': {
            'target': '26-dim per-sample L6 loss curve (loss_filled)',
            'loss': '((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + '
                    '((gamma_hat-gamma)/eta)^2',
            'failure_penalty': 'p99(valid training loss) from FULL train fold (all n)',
            'target_scaling': 'StandardScaler 26-dim, train fold of that n only',
            'J1': 'sqrt(mean_i(true_loss_i(delta_hat_i)))',
        },
        'split_contract': {
            'folds': 'deterministic 5-fold full-combo holdout over (beta, gamma/eta, n)',
            'folds_total': 5,
            'train_test_disjoint': True,
        },
        'training_contract': {
            'models_total_fold': len(got_ids),
            'seeds': SEEDS,
            'mlp': {'hidden_layer_sizes': list(NRMC.MLP_HIDDEN_LAYERS),
                    'activation': 'relu', 'solver': 'adam', 'alpha': NRMC.MLP_ALPHA,
                    'learning_rate_init': NRMC.MLP_LR,
                    'max_iter': NRMC.MLP_MAX_ITER, 'early_stopping': True,
                    'validation_fraction': NRMC.MLP_VALIDATION_FRACTION,
                    'n_iter_no_change': NRMC.MLP_N_ITER_NO_CHANGE,
                    'batch_size': NRMC.MLP_BATCH_SIZE},
            'final_models': {
                'role': 'deployment model per n, trained on full dev set',
                'seed': NRMC.FINAL_DEV_SEED,
                'seed_fixed_before_results': True,
            },
            'checkpoint_resume': 'per (n, fold, seed) JSON+CSV checkpoint',
        },
        'data_integrity': integrity,
        'results': {
            'normalized_raw_3seed': three_seed,
            'normalized_raw_per_seed': seed_summary,
            'references_j1': ref_j1,
            'relative_improvement_vs_default': rel_improve,
            'near_optimal_3seed': near_3seed,
            'training_stats_all': training_stats_all,
            'training_stats_this_run': training_stats_this_run,
            'scale_invariance': {
                'all_ok': scale_out['all_ok'],
                'file': 'scale_invariance.json',
            },
        },
        'model_files': {
            m['model_id']: {
                'n': m['n'], 'fold': m['fold'], 'seed': m['seed'],
                'input_dim': m['input_dim'], 'n_iter': m['n_iter'],
                'runtime_s': m['runtime_s'], 'J1': m['metrics']['J1'],
                'predictions_csv': f"predictions/{m['model_id']}.csv",
                'predictions_sha256': m['predictions_sha256'],
                'meta_json': f"models/{m['model_id']}.json",
            } for m in all_meta
        },
        'final_models': {
            f"n{n}_final": {
                'role': 'deployment model (full dev set, fixed seed)',
                'seed': NRMC.FINAL_DEV_SEED,
                'n': int(n),
                'train_n_samples': final_models[n][0]['train_n_samples'],
                'n_iter': final_models[n][0]['n_iter'],
                'file': f"final_models/n{n}_final.json",
            } for n in design['n_grid']
        },
        'output_files': [
            'manifest.json', 'summary.json', 'run_log.txt',
            'model_comparison.csv', 'seed_stability.csv', 'split_report.csv',
            'raw_specialist_results.csv',
            'scale_invariance.json',
            'diagnostics/*.csv', 'models/*.json', 'predictions/*.csv',
            'final_models/*.json',
        ],
        **git_meta,
    }
    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)

    summary = {
        'experiment': f'E5b {design["label"]}',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'normalized_raw_3seed': three_seed,
        'references_j1': ref_j1,
        'relative_improvement_vs_default': rel_improve,
        'seed_table': seed_summary,
        'near_optimal_3seed': near_3seed,
        'scale_invariance_all_ok': bool(scale_out['all_ok']),
        'n_models': len(all_meta),
        'training_stats_all': training_stats_all,
        'training_stats_this_run': training_stats_this_run,
    }
    with open(os.path.join(out_dir, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    with open(os.path.join(out_dir, 'run_log.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(buf))

    # LF-normalize all text artifacts (predictions/JSONs hashes are LF-based,
    # so normalization does not invalidate checkpoints), then write SHA256SUMS
    lf_normalize_tree(out_dir)
    n_entries = write_sha256sums(
        out_dir, PROJECT_ROOT, list_mdm_chunks(design['chunks_dir']),
        design['mc_manifest'], [os.path.join(STUDY_CODE_DIR, 'nrmc_config.py'),
                                os.path.join(STUDY_CODE_DIR, 'config.py')])
    log(f"  Provenance: SHA256SUMS with {n_entries} entries")

    elapsed = time.time() - t_start
    log(f"\nDone in {elapsed:.1f}s. Outputs in {out_dir}")
    return manifest


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--design', choices=['formal', 'pilot'], default='formal')
    ap.add_argument('--force-rerun', action='store_true')
    args = ap.parse_args()
    run_experiment(args.design, force_rerun=args.force_rerun)
