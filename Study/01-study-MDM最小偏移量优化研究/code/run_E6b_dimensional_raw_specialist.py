"""
Study/01 Formal E6b — Dimensional-RAW per-n specialist（最终样本自适应方法）

方法（冻结）：
    排序的原始样本 X_n = sort(x_1, ..., x_n)（有量纲，保留绝对尺度）
    -> 按样本量 n 分别训练的 MLP（n=7,10,15,20，独立网络）
    -> 预测 26 点候选偏移量损失曲线
    -> 选择预测损失最低的偏移量 delta_hat
    -> 使用 MDM 完成三参数估计。

输入合同：
  - 输入为升序排序的原始样本 X_n（不除以样本均值，不删除绝对尺度信息）。
  - 不输入手工统计特征、不输入 n、真参数、组合编号或 repeat_id。
  - 允许仅由训练折拟合的 per-position StandardScaler 改善数值训练；
    测试折不参与任何标准化统计。
  - 每个 n 使用独立 MLP（输入维 = n），不使用 padding/mask/跨 n 联合网络。

评价合同（复用既有正式合同）：
  - 目标：26 维逐样本 L6 损失曲线（loss_filled；失败候选以训练折 p99 惩罚）。
  - J1 = sqrt(mean_i(true_loss_i(delta_hat_i)))。
  - delta grid 0.00~0.50（26 点）；Default = 0.1。
  - 每个 n 内按完整 (beta, gamma/eta) 组合五折留出；seeds 42/2026/3407。
  - 同测试样本参照（combo-holdout）：Default、Normalized-RAW（候选对照）、
    L6 hindsight；样本键与方法一致。
  - L1–L6 层级表：在新 160 组合设计上统一重算，采用既有正式 cross-fit 定义
    （analyze_E1_E2_crossfit.run_crossfit，repeat-id 五折选点/评价分离），
    修正 L1 用全数据选取偏移量造成的非交叉评价问题；不混用旧 45 组合结果。

模型职责：
  - 折模型（n x fold x seed）：组合留出评价。
  - 最终模型（n x 1）：全开发集训练，seed 预先固定（dim_raw_config.FINAL_DEV_SEED），
    不根据测试结果选择。

数据：复用上一轮生成并校验的 160 组合新设计数据
  （E5_normalized_raw/shared_data；不重跑 MDM，不复制分片）。

输出：artifacts/formal/E6_dimensional_raw/specialist/
  manifest.json, summary.json, run_log.txt
  model_comparison.csv（Dimensional-RAW/Default/Normalized-RAW/L6，同测试样本）
  seed_stability.csv, split_report.csv, raw_specialist_results.csv（gitignore）
  crossfit_layers.csv（L1–L6 cross-fit 表，同一 160 组合设计）
  models/*.json, predictions/*.csv（gitignore）, final_models/*.json
  SHA256SUMS（仅不可变科学产物；不含 .gitignore/run_log/日志）

用法：
    python run_E6b_dimensional_raw_specialist.py
    python run_E6b_dimensional_raw_specialist.py --force-rerun
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

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")
sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

import dim_raw_config as CFG
import analyze_E1_E2_crossfit as CROSSFIT
from studies.common.sample import generate_sample

N_DELTAS = 26
SAMPLE_KEYS = ['beta', 'eta', 'gamma', 'gamma_over_eta', 'n', 'repeat_id']
SEEDS = CFG.STABILITY_SEEDS
NEAR_OPTIMAL_EPS = [0.01, 0.02, 0.05]
ENDPOINT_DELTAS = [0.00, 0.02, 0.48, 0.50]
BANNED_FIELDS = {'beta', 'eta', 'gamma', 'gamma_over_eta',
                 'seed', 'repeat_id', 'combo_id', 'delta', 'n'}
CONTRACT_VERSION = "E6_dimensional_raw_specialist_v1"
DELTA_GRID = list(CFG.DELTA_GRID)
DEFAULT_DELTA = CFG.DEFAULT_DELTA

# 上一轮 Normalized-RAW 候选对照的逐样本选择（gitignore 但保留在盘，
# 与本路线同一测试样本；仅作同设计对照，不进入论文主证据）
NORMALIZED_RAW_RESULTS = os.path.join(
    STUDY_ROOT, "artifacts", "formal", "E5_normalized_raw", "specialist",
    "raw_specialist_results.csv")


# ============================================================
# Data loading
# ============================================================

def list_mdm_chunks():
    chunks = sorted(
        f for f in os.listdir(CFG.CHUNKS_DIR)
        if f.startswith("chunk_") and f.endswith("_mdm.csv"))
    return [os.path.join(CFG.CHUNKS_DIR, c) for c in chunks]


def load_mc_scan():
    dtypes = {
        'beta': 'float64', 'eta': 'float64', 'gamma': 'float64',
        'gamma_over_eta': 'float64', 'n': 'int64', 'repeat_id': 'int64',
        'delta': 'float64', 'beta_hat': 'float64', 'eta_hat': 'float64',
        'gamma_hat': 'float64', 'r_squared': 'float64',
        'converged': 'boolean', 'time_ms': 'float64',
    }
    frames = [pd.read_csv(p, dtype=dtypes) for p in list_mdm_chunks()]
    if not frames:
        raise FileNotFoundError(f"No chunks under {CFG.CHUNKS_DIR}")
    return pd.concat(frames, ignore_index=True)


def verify_data_integrity(df, manifest):
    expected_combos = (len(CFG.BETA_GRID) * len(CFG.GAMMA_OVER_ETA_GRID)
                       * len(CFG.N_GRID))
    expected_rows = expected_combos * N_DELTAS * CFG.REPEATS
    assert len(df) == expected_rows, \
        f"rows {len(df)} != expected {expected_rows}"
    assert df.duplicated(subset=SAMPLE_KEYS + ['delta']).sum() == 0
    assert len(df[['beta', 'gamma_over_eta', 'n']].drop_duplicates()) == expected_combos
    assert sorted(df['delta'].unique()) == DELTA_GRID
    assert set(df['beta'].unique()) == set(CFG.BETA_GRID)
    assert set(df['gamma_over_eta'].unique()) == set(CFG.GAMMA_OVER_ETA_GRID)
    assert set(df['n'].unique()) == set(CFG.N_GRID)
    rep = df.groupby(['beta', 'gamma_over_eta', 'n'])['repeat_id'].nunique()
    assert rep.min() == CFG.REPEATS
    return {
        'expected_rows': int(expected_rows), 'actual_rows': int(len(df)),
        'unique_combos': int(expected_combos),
        'non_success_rate': float((df['status'] != 'success').mean()),
    }


# ============================================================
# Raw sample map — Dimensional: X_n = sort(x) (NO division by mean)
# ============================================================

def build_raw_sample_map(df_mc):
    """为每个唯一样本键重建升序原始样本 X_n（不归一化，保留绝对尺度）。"""
    seed_ns = CFG.SEED_NAMESPACE
    keys_df = (df_mc[SAMPLE_KEYS].drop_duplicates().sort_values(SAMPLE_KEYS)
               .reset_index(drop=True))
    print(f"[DIM-RAW] Reconstructing {len(keys_df)} raw samples "
          f"(seed_namespace={seed_ns})...")
    raw_map = {}
    t0 = time.time()
    for _, row in keys_df.iterrows():
        beta = float(row['beta']); eta = float(row['eta'])
        gamma = float(row['gamma']); n = int(row['n']); rid = int(row['repeat_id'])
        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_ns)
        s = np.sort(sample)
        assert np.allclose(s, sample), "generate_sample not ascending-sorted"
        assert len(s) == n
        raw_map[(beta, eta, gamma, float(row['gamma_over_eta']), n, rid)] = \
            s.astype(np.float64)
    print(f"[DIM-RAW] Done in {time.time() - t0:.1f}s")
    return raw_map, keys_df


def compute_per_sample_loss(df):
    r_beta = (df['beta_hat'] - df['beta']) / df['beta']
    r_eta = (df['eta_hat'] - df['eta']) / df['eta']
    r_gamma = (df['gamma_hat'] - df['gamma']) / df['eta']
    df = df.copy()
    df['loss'] = r_beta**2 + r_eta**2 + r_gamma**2
    df['loss'] = df['loss'].replace([np.inf, -np.inf], np.nan)
    return df


# ============================================================
# Combo holdout + fold prep (identical to formal contract)
# ============================================================

def get_combo_split():
    combos = list(product(CFG.BETA_GRID, CFG.GAMMA_OVER_ETA_GRID, CFG.N_GRID))
    folds = []
    for fold_idx in range(5):
        folds.append({
            'fold_name': f'combo_fold_{fold_idx + 1}',
            'train_combos': [c for i, c in enumerate(combos) if i % 5 != fold_idx],
            'test_combos': [c for i, c in enumerate(combos) if i % 5 == fold_idx],
        })
    return folds


def build_split_rows():
    rows = []
    for fold in get_combo_split():
        for combo in fold['test_combos']:
            rows.append({'fold': fold['fold_name'],
                         'test_beta': combo[0],
                         'test_gamma_over_eta': combo[1],
                         'test_n': combo[2]})
    return rows


def prepare_fold(df_full, fold):
    train_combo_set = set(fold['train_combos'])
    test_combo_set = set(fold['test_combos'])
    assert not (train_combo_set & test_combo_set)
    combo_str = (df_full['beta'].astype(str) + '|' +
                 df_full['gamma_over_eta'].astype(str) + '|' +
                 df_full['n'].astype(str))
    train_strs = set(f'{b}|{g}|{n}' for b, g, n in train_combo_set)
    test_strs = set(f'{b}|{g}|{n}' for b, g, n in test_combo_set)
    df_tr = df_full[combo_str.isin(train_strs)].copy()
    df_te = df_full[combo_str.isin(test_strs)].copy()
    failure_penalty = float(np.nanpercentile(df_tr['loss'].dropna(), 99))
    for d in (df_tr, df_te):
        d['loss_filled'] = d['loss'].fillna(failure_penalty)
        d['is_valid'] = d.get('status', 'success').eq('success') & d['loss'].notna()
    return {'df_train': df_tr, 'df_test': df_te,
            'failure_penalty': failure_penalty,
            'train_combos': sorted(train_combo_set),
            'test_combos': sorted(test_combo_set)}


def pivot_raw_vector(df_long, raw_map, n_val):
    """按 n 把长表折成 (keys, X=排序原始样本, Y=26维曲线, valid)。"""
    sub = df_long[df_long['n'] == n_val]
    keys = (sub[SAMPLE_KEYS].drop_duplicates().sort_values(SAMPLE_KEYS)
            .reset_index(drop=True))
    X = np.zeros((len(keys), n_val), dtype=np.float64)
    for i, r in keys.iterrows():
        key = (float(r['beta']), float(r['eta']), float(r['gamma']),
               float(r['gamma_over_eta']), int(r['n']), int(r['repeat_id']))
        X[i] = raw_map[key]
    assert X.shape[1] == n_val
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
            hidden_layer_sizes=CFG.MLP_HIDDEN_LAYERS, activation='relu',
            solver='adam', alpha=CFG.MLP_ALPHA, learning_rate_init=CFG.MLP_LR,
            max_iter=CFG.MLP_MAX_ITER, early_stopping=True,
            validation_fraction=CFG.MLP_VALIDATION_FRACTION,
            n_iter_no_change=CFG.MLP_N_ITER_NO_CHANGE,
            random_state=seed, batch_size=CFG.MLP_BATCH_SIZE)
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
            'is_valid': bool(valid_any[i]), 'model': model_name,
        })
    df_sel = pd.DataFrame(rows)
    j1 = math.sqrt(df_sel['true_loss'].mean())
    failure_rate = 1.0 - df_sel['is_valid'].mean()
    per_n = {int(nv): {'J1': math.sqrt(g['true_loss'].mean()),
                       'failure_rate': 1.0 - g['is_valid'].mean(), 'count': len(g)}
             for nv, g in df_sel.groupby('n')}
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
    return (os.path.join(CFG.SPECIALIST_DIR, "models", f"{mid}.json"),
            os.path.join(CFG.SPECIALIST_DIR, "predictions", f"{mid}.csv"))


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


def checkpoint_valid(n_val, fold_idx, seed, expected_test_n,
                     test_keys_sha, delta_sha, code_sha):
    mpath, ppath = checkpoint_paths(n_val, fold_idx, seed)
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
    if not all(c in dfp.columns for c in [f'pred_d{d}' for d in DELTA_GRID]):
        return False
    if int(dfp['n'].iloc[0]) != int(n_val):
        return False
    return True


def compute_test_keys_sha(n_val, fold_idx):
    fold = get_combo_split()[fold_idx]
    test_combos_n = sorted(c for c in fold['test_combos'] if c[2] == n_val)
    key_tuples = sorted((float(b), float(g), int(n), int(rid))
                        for (b, g, n) in test_combos_n
                        for rid in range(CFG.REPEATS))
    return hashlib.sha256(json.dumps(key_tuples).encode()).hexdigest()


def delta_grid_sha256():
    return hashlib.sha256(json.dumps(list(DELTA_GRID)).encode()).hexdigest()


def code_sha256():
    return sha256_file_lf(os.path.abspath(__file__))


def save_checkpoint(n_val, fold_idx, seed, metrics, n_iter, runtime_s,
                    input_scaler_mean, input_scaler_std,
                    target_scaler_mean, target_scaler_std,
                    df_sel, Y_pred, Y_true, keys_df, failure_penalty,
                    train_n, test_n, test_keys_sha, delta_sha, code_sha):
    os.makedirs(os.path.join(CFG.SPECIALIST_DIR, "models"), exist_ok=True)
    os.makedirs(os.path.join(CFG.SPECIALIST_DIR, "predictions"), exist_ok=True)
    mid = model_id(n_val, fold_idx, seed)
    mpath, ppath = checkpoint_paths(n_val, fold_idx, seed)
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
        'input_representation': 'sorted raw sample X_n = sort(x) (dimensional, '
                                'NOT divided by mean)',
        'train_n_samples': int(train_n), 'test_n_samples': int(test_n),
        'n_iter': int(n_iter), 'runtime_s': float(runtime_s),
        'failure_penalty': float(failure_penalty),
        'metrics': metrics,
        'input_scaler_mean': [float(v) for v in np.asarray(input_scaler_mean).ravel()],
        'input_scaler_std': [float(v) for v in np.asarray(input_scaler_std).ravel()],
        'target_scaler_mean': [float(v) for v in np.asarray(target_scaler_mean).ravel()],
        'target_scaler_std': [float(v) for v in np.asarray(target_scaler_std).ravel()],
        'input_scaler_fit': 'train fold of this n only (per-position StandardScaler '
                            'on raw X_n; test fold never participates)',
        'target_scaler_fit': 'train fold of this n only (26-dim StandardScaler)',
        'predictions_sha256': sha256_file_lf(ppath),
        'test_sample_keys_sha256': test_keys_sha,
        'delta_grid_sha256': delta_sha,
        'code_sha256': code_sha,
    }
    with open(mpath, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    return meta


def run_one(n_val, fold_idx, seed, df_full, raw_map, fold_prep_cache, log):
    fold = get_combo_split()[fold_idx]
    fp = fold_prep_cache[fold_idx]
    df_train, df_test = fp['df_train'], fp['df_test']
    failure_penalty = fp['failure_penalty']
    test_combos_n = [c for c in fold['test_combos'] if c[2] == n_val]
    expected_test_n = len(test_combos_n) * CFG.REPEATS
    mid = model_id(n_val, fold_idx, seed)
    tks = compute_test_keys_sha(n_val, fold_idx)
    dgs = delta_grid_sha256()
    ccs = code_sha256()
    if checkpoint_valid(n_val, fold_idx, seed, expected_test_n, tks, dgs, ccs):
        log(f"  [skip] {mid}")
        mpath, ppath = checkpoint_paths(n_val, fold_idx, seed)
        return {'skipped': True, 'meta': json.load(open(mpath, encoding='utf-8')),
                'df_sel': pd.read_csv(ppath)}
    keys_tr, X_tr, Y_tr, _ = pivot_raw_vector(df_train, raw_map, n_val)
    keys_te, X_te, Y_te, valid_te = pivot_raw_vector(df_test, raw_map, n_val)
    assert X_tr.shape[1] == n_val and X_te.shape[1] == n_val
    assert X_te.shape[0] == expected_test_n
    assert not np.any(np.isnan(X_tr)), "NaN in raw input"
    t0 = time.time()
    Y_pred, n_iter, in_sc, tg_sc, _ = train_specialist(X_tr, Y_tr, X_te, seed)
    runtime = time.time() - t0
    df_sel, metrics = evaluate_selection(
        keys_te, Y_pred, Y_te, f'Dimensional-RAW-{mid}', valid_te)
    meta = save_checkpoint(n_val, fold_idx, seed, metrics, n_iter, runtime,
                           in_sc.mean_, in_sc.scale_, tg_sc.mean_, tg_sc.scale_,
                           df_sel, Y_pred, Y_te, keys_te, failure_penalty,
                           len(keys_tr), len(keys_te), tks, dgs, ccs)
    log(f"  [done] {mid}: J1={metrics['J1']:.6f} n_iter={n_iter} "
        f"t={runtime:.1f}s (train={len(keys_tr)}, test={len(keys_te)})")
    return {'skipped': False, 'meta': meta, 'df_sel': df_sel,
            'runtime_s': runtime, 'n_iter': n_iter}


# ============================================================
# Final full-development models
# ============================================================

def _serialize_mlp(model):
    return {'coefs_': [[[float(v) for v in row] for row in W] for W in model.coefs_],
            'intercepts_': [[float(v) for v in b] for b in model.intercepts_]}


def train_final_model(n_val, df_full, raw_map, log):
    from sklearn.preprocessing import StandardScaler
    from sklearn.neural_network import MLPRegressor
    fdir = os.path.join(CFG.SPECIALIST_DIR, "final_models")
    os.makedirs(fdir, exist_ok=True)
    fpath = os.path.join(fdir, f"n{n_val}_final.json")
    dev_valid = df_full[df_full['n'] == n_val]['loss'].dropna()
    dev_penalty = float(np.nanpercentile(dev_valid, 99))
    dev = df_full[df_full['n'] == n_val].copy()
    dev['loss_filled'] = dev['loss'].fillna(dev_penalty)
    dev['is_valid'] = dev.get('status', 'success').eq('success') & dev['loss'].notna()
    keys, X, Y, valid = pivot_raw_vector(dev, raw_map, n_val)
    input_scaler = StandardScaler()
    X_s = input_scaler.fit_transform(X)
    target_scaler = StandardScaler()
    Y_s = target_scaler.fit_transform(Y)
    seed = CFG.FINAL_DEV_SEED
    t0 = time.time()
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', category=ConvergenceWarning)
        model = MLPRegressor(
            hidden_layer_sizes=CFG.MLP_HIDDEN_LAYERS, activation='relu',
            solver='adam', alpha=CFG.MLP_ALPHA, learning_rate_init=CFG.MLP_LR,
            max_iter=CFG.MLP_MAX_ITER, early_stopping=True,
            validation_fraction=CFG.MLP_VALIDATION_FRACTION,
            n_iter_no_change=CFG.MLP_N_ITER_NO_CHANGE,
            random_state=seed, batch_size=CFG.MLP_BATCH_SIZE)
        model.fit(X_s, Y_s)
    runtime = time.time() - t0
    meta = {
        'contract_version': CONTRACT_VERSION,
        'model_id': f"n{n_val}_final", 'n': int(n_val), 'input_dim': int(n_val),
        'seed': int(seed), 'n_iter': int(model.n_iter_), 'runtime_s': float(runtime),
        'train_n_samples': int(len(keys)),
        'train_set': 'full development set (all samples of this n)',
        'input_representation': 'sorted raw sample X_n = sort(x) (dimensional, '
                                'NOT divided by mean)',
        'role': ('deployment model: trained on full dev set with pre-fixed seed. '
                 'Hold-out performance is estimated by the fold models.'),
        'dev_failure_penalty': float(dev_penalty),
        'input_scaler_mean': [float(v) for v in np.asarray(input_scaler.mean_).ravel()],
        'input_scaler_std': [float(v) for v in np.asarray(input_scaler.scale_).ravel()],
        'target_scaler_mean': [float(v) for v in np.asarray(target_scaler.mean_).ravel()],
        'target_scaler_std': [float(v) for v in np.asarray(target_scaler.scale_).ravel()],
        'mlp_weights': _serialize_mlp(model),
        'delta_grid': list(DELTA_GRID),
        'scale_note': ('Dimensional raw input is NOT unit-invariant: predictions '
                       'depend on the physical units and scale range of training.'),
    }
    with open(fpath, 'w', encoding='utf-8') as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)
    log(f"  [final] n{n_val}: n_iter={model.n_iter_} t={runtime:.1f}s train={len(keys)}")
    return meta, model, input_scaler, target_scaler


# ============================================================
# Representation check (raw sorted input; scaler train-only)
# ============================================================

def run_representation_check(raw_map, fold_prep_cache, log):
    """确认：输入为排序原始样本（未除以均值），scaler 只由训练折拟合。"""
    out = {'raw_input_not_normalized': True,
           'scaler_fit_on_train_only': True, 'samples': []}
    # 1) representative samples: X == generate_sample(...) exactly; mean ~ 1000-scale
    for n_val in CFG.N_GRID:
        key = next(k for k in raw_map if k[4] == n_val)
        beta, eta, gamma, goe, n, rid = key
        sample = generate_sample(beta, eta, gamma, n, rid, seed=CFG.SEED_NAMESPACE)
        X = raw_map[key]
        assert np.allclose(X, np.sort(sample)), "X != sorted raw sample"
        mean_x = float(X.mean())
        assert not np.isclose(mean_x, 1.0, atol=1e-3), \
            "input appears normalized (mean ~ 1); must be dimensional raw"
        out['samples'].append({
            'n': int(n), 'sample_key': [float(beta), float(eta), float(gamma),
                                        float(goe), int(n), int(rid)],
            'mean_x': mean_x, 'x_min': float(X[0]), 'x_max': float(X[-1]),
            'input_is_sorted_raw': True,
        })
        log(f"  [repr-check] n={n}: mean(x)={mean_x:.2f} (raw ~1000-scale, "
            f"NOT normalized)")
    # 2) scaler train-only: every fold model records its own train-fold scaler
    #    (per fold), and test fold statistics never enter (by construction in
    #    train_specialist: input_scaler.fit_transform(X_train) only).
    out['scaler_note'] = ('per-position StandardScaler fit ONLY on the train fold '
                          '(input_scaler.fit_transform(X_train)); the test fold is '
                          'only transformed, never used for fit statistics.')
    with open(os.path.join(CFG.SPECIALIST_DIR, 'representation_check.json'), 'w',
              encoding='utf-8') as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    log("  [repr-check] scaler fit on train fold only (per-fold scalers in models/*.json)")
    return out


# ============================================================
# Cross-fit L1–L6 (existing formal definition, new 160-combo design)
# ============================================================

def run_crossfit_layers(df_full, log):
    """L1–L6 在新 160 组合设计上统一重算。

    L1–L5：既有正式 cross-fit 定义（analyze_E1_E2_crossfit.run_crossfit，
    repeat-id 五折选点/评价分离）。L6：逐样本 hindsight（固定候选网格内）。
    """
    # prepare scan (converged + finite j1_sq), like the formal crossfit module
    scan = CROSSFIT.prepare_scan(df_full)
    result = CROSSFIT.run_crossfit(scan, n_folds=5, default_delta=CFG.DEFAULT_DELTA)
    pooled = result['pooled_metrics'].copy()  # Default + L1..L5, cross-fit J1
    # L6: per-sample hindsight over ALL samples (same 160-combo design)
    scan['delta'] = scan['delta'].astype(float)
    min_loss = (scan.groupby(CROSSFIT.SAMPLE_COLS, dropna=False)['j1_sq']
                .min().rename('min_j1_sq').reset_index())
    l6_j1 = math.sqrt(float(min_loss['min_j1_sq'].mean()))
    l6_row = {'layer': 'L6', 'J1': l6_j1,
              'n_selected_samples': int(len(min_loss))}
    for nv in CFG.N_GRID:
        sub = min_loss[min_loss['n'] == nv]
        l6_row[f'J1_n{int(nv)}'] = math.sqrt(float(sub['min_j1_sq'].mean()))
    layers = pd.concat([pooled, pd.DataFrame([l6_row])], ignore_index=True)
    os.makedirs(CFG.SPECIALIST_DIR, exist_ok=True)
    layers.to_csv(os.path.join(CFG.SPECIALIST_DIR, 'crossfit_layers.csv'), index=False)
    for _, r in layers.iterrows():
        log(f"  [crossfit] {r['layer']}: J1={float(r['J1']):.6f}")
    # also persist per-fold + same-sample comparison for audit
    result['pooled_metrics'].to_csv(
        os.path.join(CFG.SPECIALIST_DIR, 'crossfit_pooled.csv'), index=False)
    return layers, result


# ============================================================
# Same-test comparison incl. Normalized-RAW (candidate control)
# ============================================================

def load_normalized_raw_comparison():
    """上一轮 Normalized-RAW 逐样本选择（同一 160 组合设计测试样本）。"""
    if not os.path.isfile(NORMALIZED_RAW_RESULTS):
        return None
    df = pd.read_csv(NORMALIZED_RAW_RESULTS)
    return df[['beta', 'gamma_over_eta', 'n', 'repeat_id', 'seed',
               'selected_delta', 'true_loss']]


def compute_same_test_comparison(df_all_sel, df_full, normalized_raw, log):
    """Dimensional-RAW vs Default vs Normalized-RAW vs L6，同一 combo-holdout 测试样本。"""
    # Default (delta=0.1) per sample
    dft = df_full[SAMPLE_KEYS + ['delta', 'loss']].copy()
    default_sel = dft[dft['delta'] == DEFAULT_DELTA].copy()
    default_sel = default_sel.rename(columns={'loss': 'true_loss'})
    default_sel['selected_delta'] = DEFAULT_DELTA
    # L6 per sample
    l6 = (dft.dropna(subset=['loss']).sort_values('loss')
          .groupby(SAMPLE_KEYS, dropna=False).first().reset_index())
    l6 = l6[['beta', 'gamma_over_eta', 'n', 'repeat_id', 'delta', 'loss']]
    l6 = l6.rename(columns={'delta': 'selected_delta', 'loss': 'true_loss'})

    rows = []
    for seed in SEEDS:
        dim = df_all_sel[df_all_sel['seed'] == seed]
        # key: (beta, goe, n, repeat_id)
        def _summarize(sel, name):
            s = sel.copy()
            j1 = math.sqrt(s['true_loss'].mean())
            rec = {'model': name, 'split': 'combo_holdout_pooled', 'seed': seed,
                   'J1': j1, 'failure_rate': 0.0, 'n_samples': len(s)}
            for nv, g in s.groupby('n'):
                rec[f'J1_n{nv}'] = math.sqrt(g['true_loss'].mean())
            return rec
        rows.append(_summarize(dim, 'Dimensional-RAW-MLP'))
        rows.append(_summarize(default_sel, 'Default'))
        rows.append(_summarize(l6, 'L6-hindsight'))
        if normalized_raw is not None:
            nr = normalized_raw[normalized_raw['seed'] == seed]
            rows.append(_summarize(nr, 'Normalized-RAW-MLP'))
    comp = pd.DataFrame(rows)
    comp.to_csv(os.path.join(CFG.SPECIALIST_DIR, 'model_comparison.csv'), index=False)
    for _, r in comp.iterrows():
        log(f"  [compare] {r['model']} seed={r['seed']}: "
            f"pooled J1={float(r['J1']):.6f}")
    return comp


# ============================================================
# Provenance / seal (immutable scientific artifacts only)
# ============================================================

def get_git_metadata():
    def run(args):
        try:
            return subprocess.check_output(args, cwd=PROJECT_ROOT,
                                           stderr=subprocess.DEVNULL).decode().strip()
        except Exception:
            return ''
    return {'git_commit': run(['git', 'rev-parse', 'HEAD']),
            'git_commit_short': run(['git', 'rev-parse', '--short', 'HEAD']),
            'git_branch': run(['git', 'branch', '--show-current']),
            'workspace_dirty': bool(run(['git', 'status', '--short']))}


def _is_sealable(relpath):
    """封存清单只覆盖不可变科学产物；排除可变文件（.gitignore、日志等）。"""
    base = os.path.basename(relpath)
    if base == '.gitignore' or base == 'SHA256SUMS':
        return False
    if relpath.endswith(('.log', '.err', 'run_log.txt')):
        return False
    return True


def write_sha256sums(out_dir, project_root):
    entries = []

    def add(abs_path):
        try:
            rel = os.path.relpath(abs_path, project_root)
            if rel.startswith('..'):
                rel = 'abs://' + abs_path.replace(os.sep, '/')
            rel = rel.replace(os.sep, '/')
        except ValueError:
            rel = 'abs://' + abs_path.replace(os.sep, '/')
        if _is_sealable(rel):
            entries.append((rel, sha256_file_lf(abs_path)))

    for p in list_mdm_chunks():
        add(p)
    add(CFG.MC_MANIFEST_PATH)
    add(os.path.abspath(__file__))
    for cp in [os.path.join(STUDY_CODE_DIR, 'dim_raw_config.py'),
               os.path.join(STUDY_CODE_DIR, 'analyze_E1_E2_crossfit.py'),
               os.path.join(STUDY_CODE_DIR, 'run_E6a_data_inventory.py')]:
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
            if fn == 'SHA256SUMS' or not fn.endswith(('.csv', '.json')):
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
        out.append({'model': model_name, 'category': cat,
                    'P_delta_0': float((sub['selected_delta'] == 0.00).mean()),
                    'P_delta_0.5': float((sub['selected_delta'] == 0.50).mean()),
                    'P_extreme': float(sub['selected_delta'].isin(ENDPOINT_DELTAS).mean()),
                    'n_samples': len(sub)})
    return out


def near_optimal_summary(df_preds):
    oracle = df_preds['oracle_min_loss'].where(
        df_preds['oracle_min_loss'] > 1e-12, np.nan)
    rel = (df_preds['true_loss'] - df_preds['oracle_min_loss']) / oracle
    regret = df_preds['true_loss'] - df_preds['oracle_min_loss']
    s = {'mean_selected_loss': float(df_preds['true_loss'].mean()),
         'mean_oracle_min': float(df_preds['oracle_min_loss'].mean()),
         'mean_regret': float(regret.mean()),
         'mean_rel_regret': float(rel.mean())}
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


def run_experiment(force_rerun=False):
    out_dir = CFG.SPECIALIST_DIR
    for d in (out_dir, os.path.join(out_dir, "models"),
              os.path.join(out_dir, "predictions"),
              os.path.join(out_dir, "final_models"),
              os.path.join(out_dir, "diagnostics")):
        os.makedirs(d, exist_ok=True)
    log, buf = log_lines()
    log("=" * 72)
    log("Study/01 E6b — Dimensional-RAW per-n specialist (final method)")
    log(f"Output: {out_dir}")
    log("=" * 72)
    t_start = time.time()

    log("\n[1/8] Loading MC scan chunks (reused 160-combo design)...")
    df_mc = load_mc_scan()
    with open(CFG.MC_MANIFEST_PATH, encoding='utf-8') as f:
        mc_manifest = json.load(f)
    log(f"  Loaded {len(df_mc):,} rows")

    log("\n[2/8] Integrity + raw sample reconstruction...")
    integrity = verify_data_integrity(df_mc, mc_manifest)
    log(f"  Integrity: {integrity}")
    raw_map, _keys = build_raw_sample_map(df_mc)
    df_full = compute_per_sample_loss(df_mc)
    nan_loss = int(df_full['loss'].isna().sum())
    log(f"  NaN/invalid losses: {nan_loss} ({nan_loss/len(df_full)*100:.3f}%)")

    log("\n[3/8] Preparing 5 combo folds...")
    folds = get_combo_split()
    fold_prep_cache = [prepare_fold(df_full, f) for f in folds]
    for i, fp in enumerate(fold_prep_cache):
        log(f"  fold{i+1}: train={len(fp['train_combos'])} "
            f"test={len(fp['test_combos'])} penalty={fp['failure_penalty']:.6f}")
    all_test = sorted(c for f in folds for c in f['test_combos'])
    assert len(all_test) == 160 and len(set(all_test)) == 160

    log(f"\n[4/8] Training per-n specialists "
        f"({len(CFG.N_GRID)}n x 5fold x {len(SEEDS)}seed)...")
    all_meta, all_sel = [], []
    runtimes, n_iters = [], []
    for n_val in CFG.N_GRID:
        for fold_idx in range(5):
            for seed in SEEDS:
                if force_rerun:
                    for p in checkpoint_paths(n_val, fold_idx, seed):
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
    got_ids = {m['model_id'] for m in all_meta}
    expected_ids = {model_id(n, f, s)
                    for n in CFG.N_GRID for f in range(5) for s in SEEDS}
    assert not (expected_ids - got_ids), f"missing {sorted(expected_ids - got_ids)}"
    log(f"  All {len(got_ids)} fold models present")

    log("\n[5/8] Final full-development models (deployable, fixed seed)...")
    for n_val in CFG.N_GRID:
        train_final_model(n_val, df_full, raw_map, log)

    log("\n[6/8] Representation check (raw input; scaler train-only)...")
    repr_out = run_representation_check(raw_map, fold_prep_cache, log)

    log("\n[7/8] Cross-fit L1–L6 on the new 160-combo design...")
    layers, crossfit_result = run_crossfit_layers(df_full, log)

    log("\n[8/8] Aggregation, same-test comparison, provenance...")
    seed_summary = []
    for seed in SEEDS:
        sub = df_all_sel[df_all_sel['seed'] == seed]
        per_n = {int(nv): math.sqrt(g['true_loss'].mean())
                 for nv, g in sub.groupby('n_val')}
        seed_summary.append({
            'seed': seed, 'pooled_J1': math.sqrt(sub['true_loss'].mean()),
            **{f'J1_n{nv}': per_n.get(nv, float('nan')) for nv in CFG.N_GRID},
            'n_samples': len(sub),
            'endpoint_rate': float(sub['selected_delta'].isin(ENDPOINT_DELTAS).mean()),
            'failure_rate': float(1.0 - sub['is_valid'].mean()),
        })
    seed_df = pd.DataFrame(seed_summary)
    three_seed = {
        'pooled_J1_mean': float(seed_df['pooled_J1'].mean()),
        'pooled_J1_std': float(seed_df['pooled_J1'].std(ddof=0)),
        **{f'J1_n{nv}_mean': float(seed_df[f'J1_n{nv}'].mean())
           for nv in CFG.N_GRID},
    }
    log(f"  Dimensional-RAW 3-seed: pooled J1 mean={three_seed['pooled_J1_mean']:.6f} "
        f"(std={three_seed['pooled_J1_std']:.6f})")

    normalized_raw = load_normalized_raw_comparison()
    if normalized_raw is not None:
        log(f"  Normalized-RAW candidate control loaded: "
            f"{len(normalized_raw)} rows")
    else:
        log("  WARNING: Normalized-RAW candidate control not found on disk")
    comp = compute_same_test_comparison(df_all_sel, df_full, normalized_raw, log)

    df_all_sel.to_csv(os.path.join(out_dir, 'raw_specialist_results.csv'), index=False)
    seed_df.to_csv(os.path.join(out_dir, 'seed_stability.csv'), index=False)
    pd.DataFrame(build_split_rows()).to_csv(
        os.path.join(out_dir, 'split_report.csv'), index=False)

    diag_rows = []
    near_summaries = {}
    for seed in SEEDS:
        sub = df_all_sel[df_all_sel['seed'] == seed].copy()
        tag = f'Dimensional-RAW-seed{seed}'
        diag_rows.extend(endpoint_rows(sub, tag))
        preds_frames = []
        for n_val in CFG.N_GRID:
            for fold_idx in range(5):
                _, pp = checkpoint_paths(n_val, fold_idx, seed)
                preds_frames.append(pd.read_csv(pp))
        dfp = pd.concat(preds_frames, ignore_index=True)
        near_summaries[tag] = near_optimal_summary(dfp)
    pd.DataFrame(diag_rows).to_csv(
        os.path.join(out_dir, 'diagnostics', 'endpoint_diagnostics.csv'), index=False)

    tagged_frames = []
    for seed in SEEDS:
        for n_val in CFG.N_GRID:
            for fold_idx in range(5):
                _, pp = checkpoint_paths(n_val, fold_idx, seed)
                d = pd.read_csv(pp)
                d['seed'] = seed
                d['fold'] = fold_idx + 1
                d['n_specialist'] = n_val
                d['model_id'] = model_id(n_val, fold_idx, seed)
                tagged_frames.append(d)
    dfp_all = pd.concat(tagged_frames, ignore_index=True)
    near_3seed = near_optimal_summary(dfp_all)
    dfp_all[['model_id', 'seed', 'fold', 'n_specialist', 'beta',
             'gamma_over_eta', 'n', 'repeat_id', 'selected_delta',
             'selected_delta_idx', 'true_loss', 'oracle_min_loss', 'pred_min']]\
        .to_csv(os.path.join(out_dir, 'diagnostics', 'near_optimal_diagnostics.csv'),
                index=False)

    # reference pooled J1 for the report (from crossfit layers)
    default_j1 = float(layers[layers['layer'] == 'Default']['J1'].iloc[0])
    l6_j1 = float(layers[layers['layer'] == 'L6']['J1'].iloc[0])
    rel_improve = (default_j1 - three_seed['pooled_J1_mean']) / default_j1

    git_meta = get_git_metadata()
    manifest = {
        'run_id': CONTRACT_VERSION,
        'created_at': datetime.now(timezone.utc).isoformat(),
        'code_entry': 'code/run_E6b_dimensional_raw_specialist.py',
        'method': {
            'representation': ('X_n = ascending-sorted raw sample (dimensional, '
                               'absolute scale preserved; NOT divided by mean)'),
            'input_dim_per_n': {int(n): int(n) for n in CFG.N_GRID},
            'no_hand_crafted_stats': True, 'no_padding': True, 'no_mask': True,
            'no_explicit_n': True, 'no_true_parameters': True,
            'no_combo_id': True, 'no_repeat_id': True,
            'per_n_independent_network': True,
            'banned_fields_excluded': sorted(BANNED_FIELDS),
            'input_standardizer': ('per-position StandardScaler on raw X_n, '
                                   'fit on train fold of that n only'),
            'scale_note': ('Dimensional raw input is NOT unit-invariant; '
                           'conclusions apply only to training units/scale.'),
        },
        'design': CFG.design_summary(),
        'data_source': {
            'reused': 'artifacts/formal/E5_normalized_raw/shared_data/ '
                      '(160-combo new design; not re-generated, not copied)',
            'manifest': CFG.MC_MANIFEST_PATH,
            'data_sha256sums': 'shared_data/data_sha256sums.txt',
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
            'folds_total': 5, 'train_test_disjoint': True,
        },
        'training_contract': {
            'models_total_fold': len(got_ids), 'seeds': SEEDS,
            'mlp': {'hidden_layer_sizes': list(CFG.MLP_HIDDEN_LAYERS),
                    'activation': 'relu', 'solver': 'adam', 'alpha': CFG.MLP_ALPHA,
                    'learning_rate_init': CFG.MLP_LR, 'max_iter': CFG.MLP_MAX_ITER,
                    'early_stopping': True,
                    'validation_fraction': CFG.MLP_VALIDATION_FRACTION,
                    'n_iter_no_change': CFG.MLP_N_ITER_NO_CHANGE,
                    'batch_size': CFG.MLP_BATCH_SIZE},
            'final_models': {'role': 'deployment model per n, full dev set',
                             'seed': CFG.FINAL_DEV_SEED,
                             'seed_fixed_before_results': True},
            'checkpoint_resume': 'per (n, fold, seed) JSON+CSV checkpoint',
        },
        'references': {
            'same_test_combo_holdout': ['Default', 'Normalized-RAW-MLP (candidate)',
                                        'L6-hindsight'],
            'crossfit_layers': ('L1–L5 cross-fit (analyze_E1_E2_crossfit.run_crossfit, '
                                'repeat-id 5-fold), L6 per-sample hindsight; '
                                'all on the same 160-combo new design'),
            'note_l1_fix': ('L1 uses train-fold selection / held-out evaluation '
                            '(cross-fit), fixing the previous full-data L1 leak'),
        },
        'data_integrity': integrity,
        'results': {
            'dimensional_raw_3seed': three_seed,
            'dimensional_raw_per_seed': seed_summary,
            'relative_improvement_vs_default': rel_improve,
            'crossfit_layers_j1': {r['layer']: float(r['J1'])
                                   for _, r in layers.iterrows()},
            'normalized_raw_candidate_control': (
                None if normalized_raw is None else {
                    'note': 'same 160-combo design, same test samples (candidate '
                            'control, not main evidence)',
                    'per_seed': {int(s): math.sqrt(
                        (normalized_raw[normalized_raw['seed'] == s]['true_loss']
                         .mean()))
                        for s in SEEDS},
                }),
            'near_optimal_3seed': near_3seed,
            'representation_check': {
                'file': 'representation_check.json',
                'raw_input_not_normalized': repr_out['raw_input_not_normalized'],
                'scaler_fit_on_train_only': repr_out['scaler_fit_on_train_only'],
            },
            'training_stats': {
                'models_trained_this_run': len(runtimes),
                'runtime_s_total_this_run': float(np.sum(runtimes)) if runtimes else 0.0,
            },
        },
        'model_files': {
            m['model_id']: {'n': m['n'], 'fold': m['fold'], 'seed': m['seed'],
                            'input_dim': m['input_dim'], 'n_iter': m['n_iter'],
                            'runtime_s': m['runtime_s'], 'J1': m['metrics']['J1'],
                            'predictions_csv': f"predictions/{m['model_id']}.csv",
                            'meta_json': f"models/{m['model_id']}.json"}
            for m in all_meta
        },
        'output_files': [
            'manifest.json', 'summary.json', 'run_log.txt',
            'model_comparison.csv', 'seed_stability.csv', 'split_report.csv',
            'raw_specialist_results.csv (gitignore)', 'crossfit_layers.csv',
            'crossfit_pooled.csv', 'representation_check.json',
            'diagnostics/*.csv', 'models/*.json', 'predictions/*.csv (gitignore)',
            'final_models/*.json', 'SHA256SUMS',
        ],
        'seal_note': ('SHA256SUMS covers immutable scientific artifacts only; '
                      '.gitignore, run_log.txt and *.log are excluded.'),
        **git_meta,
    }
    with open(os.path.join(out_dir, 'manifest.json'), 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False, default=str)

    summary = {
        'experiment': 'E6b Dimensional-RAW per-n specialist (final method)',
        'created_at': datetime.now(timezone.utc).isoformat(),
        'dimensional_raw_3seed': three_seed,
        'relative_improvement_vs_default': rel_improve,
        'crossfit_layers_j1': {r['layer']: float(r['J1']) for _, r in layers.iterrows()},
        'normalized_raw_candidate_control': (
            None if normalized_raw is None else {
                'per_seed_pooled_J1': {int(s): math.sqrt(
                    (normalized_raw[normalized_raw['seed'] == s]['true_loss'].mean()))
                    for s in SEEDS},
            }),
        'seed_table': seed_summary,
        'model_comparison': comp.to_dict(orient='records'),
    }
    with open(os.path.join(out_dir, 'summary.json'), 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False, default=str)

    with open(os.path.join(out_dir, 'run_log.txt'), 'w', encoding='utf-8') as f:
        f.write('\n'.join(buf))

    lf_normalize_tree(out_dir)
    n_entries = write_sha256sums(out_dir, PROJECT_ROOT)
    log(f"  Provenance: SHA256SUMS with {n_entries} entries (immutable artifacts only)")

    elapsed = time.time() - t_start
    log(f"\nDone in {elapsed:.1f}s. Outputs in {out_dir}")
    return manifest


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--force-rerun', action='store_true')
    args = ap.parse_args()
    run_experiment(force_rerun=args.force_rerun)
