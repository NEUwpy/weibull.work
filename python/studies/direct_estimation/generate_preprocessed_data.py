"""
Generate preprocessed visualization data for PerformanceTab.

Reads validation prediction CSVs (for ig) and test data CSVs (for ip/ex),
runs model inference on test data, and produces lightweight JSON files
with sampled scatter data, pre-computed histogram bins, and dimension
breakdowns — eliminating the need for client-side CSV parsing.
"""
import csv
import json
import math
import os
import sys
import numpy as np
from scipy import stats as scipy_stats

import torch
import torch.nn as nn

BASE_DIR = os.path.join(os.path.dirname(__file__), '..', '..', '..')
VALIDATION_DIR = os.path.join(BASE_DIR, 'public', 'ai', 'data')
TEST_DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')
MODEL_DIR = os.path.join(BASE_DIR, 'python', 'models', 'direct_estimation')
OUTPUT_DIR = VALIDATION_DIR

SAMPLE_SIZES = [5, 7, 10, 15]
SCATTER_SAMPLE = 200
HIST_BINS = 30
UNIFIED_SCHEMES = ['b1', 'b2']
ALL_SCHEMES = ['a1', 'a2', 'a3', 'b1', 'b2', 'c1', 'c2', 'c3']
VTYPES = ['ig', 'ip', 'ex']


# ============================================================
# Model definition (same as train_model.py / evaluate_generalization.py)
# ============================================================

class DirectEstimationMLP(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128), nn.ReLU(),
            nn.Linear(128, 64), nn.ReLU(),
            nn.Linear(64, 32), nn.ReLU(),
            nn.Linear(32, 3),
        )

    def forward(self, x):
        return self.net(x)


# ============================================================
# Preprocessing functions (same as evaluate_generalization.py)
# ============================================================

def preprocess_a2(X):
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
    return np.concatenate([X / t_bar_safe, t_bar], axis=1)

def preprocess_a3(X):
    return X - np.min(X, axis=1, keepdims=True)

def preprocess_b1(X, n_max):
    N, n = X.shape
    X_padded = np.zeros((N, n_max)); X_padded[:, :n] = X
    mask = np.zeros((N, n_max)); mask[:, :n] = 1.0
    return np.concatenate([X_padded, mask], axis=1)

def preprocess_b2(X, n_max):
    N, n = X.shape
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
    X_norm = X / t_bar_safe
    X_padded = np.zeros((N, n_max)); X_padded[:, :n] = X_norm
    mask = np.zeros((N, n_max)); mask[:, :n] = 1.0
    return np.concatenate([X_padded, t_bar, mask], axis=1)

def preprocess_c1(X):
    return np.concatenate([
        np.mean(X, axis=1, keepdims=True),
        np.std(X, axis=1, keepdims=True),
        np.min(X, axis=1, keepdims=True),
        np.max(X, axis=1, keepdims=True),
    ], axis=1)

def preprocess_c2(X):
    return np.concatenate([
        np.mean(X, axis=1, keepdims=True),
        np.std(X, axis=1, keepdims=True),
        np.min(X, axis=1, keepdims=True),
        np.max(X, axis=1, keepdims=True),
        np.array([scipy_stats.skew(x) for x in X]).reshape(-1, 1),
        np.array([scipy_stats.kurtosis(x) for x in X]).reshape(-1, 1),
        np.median(X, axis=1, keepdims=True),
    ], axis=1)

def preprocess_c3(X):
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_std = np.std(X, axis=1, keepdims=True)
    q1 = np.percentile(X, 25, axis=1, keepdims=True)
    q3 = np.percentile(X, 75, axis=1, keepdims=True)
    t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
    return np.concatenate([
        t_bar, t_std,
        np.min(X, axis=1, keepdims=True),
        np.max(X, axis=1, keepdims=True),
        np.array([scipy_stats.skew(x) for x in X]).reshape(-1, 1),
        np.array([scipy_stats.kurtosis(x) for x in X]).reshape(-1, 1),
        np.median(X, axis=1, keepdims=True),
        q1, q3, q3 - q1, t_std / t_bar_safe,
    ], axis=1)


# ============================================================
# Model loading + inference
# ============================================================

def load_model_and_predict(scheme, n, X, device):
    if scheme in ('b1', 'b2'):
        model_path = os.path.join(MODEL_DIR, f'{scheme}_model.pth')
    else:
        suffix = f'_{scheme}' if scheme != 'a1' else ''
        model_path = os.path.join(MODEL_DIR, f'n{n}{suffix}_model.pth')

    if not os.path.exists(model_path):
        return None

    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    input_dim = checkpoint['input_dim']
    preprocessing = checkpoint.get('preprocessing', scheme)
    scaler_params = checkpoint['scaler_params']
    y_scaler = checkpoint['y_scaler']
    n_max = checkpoint.get('n_max', 15)

    if preprocessing == 'a1':    X_processed = X
    elif preprocessing == 'a2':  X_processed = preprocess_a2(X)
    elif preprocessing == 'a3':  X_processed = preprocess_a3(X)
    elif preprocessing == 'b1':  X_processed = preprocess_b1(X, n_max)
    elif preprocessing == 'b2':  X_processed = preprocess_b2(X, n_max)
    elif preprocessing == 'c1':  X_processed = preprocess_c1(X)
    elif preprocessing == 'c2':  X_processed = preprocess_c2(X)
    elif preprocessing == 'c3':  X_processed = preprocess_c3(X)
    else:                        X_processed = X

    x_mean = np.array(scaler_params['x_mean'])
    x_std = np.array(scaler_params['x_std'])
    X_norm = (X_processed - x_mean) / x_std

    model = DirectEstimationMLP(input_dim=input_dim)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()

    with torch.no_grad():
        pred_norm = model(torch.FloatTensor(X_norm).to(device)).cpu().numpy()

    y_mean = np.array(y_scaler['y_mean'])
    y_std = np.array(y_scaler['y_std'])
    return pred_norm * y_std + y_mean


# ============================================================
# Data loading
# ============================================================

def load_validation_csv(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                rows.append({k: float(v) for k, v in row.items()})
            except ValueError:
                continue
    return rows


def load_test_csv(path):
    """Load test CSV → (X_samples, y_true, n)"""
    rows_list = []
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows_list.append(row)

    data = []
    for row in rows_list:
        n = int(row[0])
        beta, eta, gamma = float(row[1]), float(row[2]), float(row[3])
        samples = [float(v) for v in row[5:5+n]]
        data.append([n, beta, eta, gamma] + samples)

    data = np.array(data)
    n = int(data[0, 0])
    X = data[:, 4:4+n]
    y = data[:, 1:4]
    return X, y, n


# ============================================================
# Helpers
# ============================================================

def stratified_sample(rows, key, count):
    groups = {}
    for r in rows:
        k = r[key]
        groups.setdefault(k, []).append(r)
    result = []
    for k in sorted(groups):
        g = groups[k]
        step = max(1, len(g) // max(1, count // len(groups)))
        result.extend(g[::step])
    return result[:count]


def _calc_metrics(rows):
    n = len(rows)
    return {
        'mae_beta':  sum(abs(r['pred_beta']  - r['true_beta'])  for r in rows) / n,
        'mae_eta':   sum(abs(r['pred_eta']   - r['true_eta'])   for r in rows) / n,
        'mae_gamma': sum(abs(r['pred_gamma'] - r['true_gamma']) for r in rows) / n,
        'mre_beta':  sum(abs(r['pred_beta']  - r['true_beta'])  / abs(r['true_beta'])  for r in rows if abs(r['true_beta'])  > 1e-10) / n,
        'mre_eta':   sum(abs(r['pred_eta']   - r['true_eta'])   / abs(r['true_eta'])   for r in rows if abs(r['true_eta'])   > 1e-10) / n,
        'mre_gamma': sum(abs(r['pred_gamma'] - r['true_gamma']) / abs(r['true_gamma']) for r in rows if abs(r['true_gamma']) > 1e-10) / n,
        'count': n,
    }


def _validation_csv_path(scheme, n):
    suffix = '' if scheme == 'a1' else f'_{scheme}'
    return os.path.join(VALIDATION_DIR, f'direct_estimation_validation_predictions_n{n}{suffix}.csv')


def _sample_scatter(X, y, pred, count):
    """Stratified sample from arrays → scatter points."""
    N = X.shape[0]
    if N == 0:
        return {'beta': {'x': [], 'y': []}, 'eta': {'x': [], 'y': []}, 'gamma': {'x': [], 'y': []}}

    # Stratified by true_beta
    betas = y[:, 0]
    unique_betas = np.unique(betas)
    per_group = max(1, count // len(unique_betas))
    indices = []
    for b in sorted(unique_betas):
        idxs = np.where(betas == b)[0]
        step = max(1, len(idxs) // per_group)
        indices.extend(idxs[::step])
    indices = indices[:count]

    return {
        'beta':  {'x': y[indices, 0].tolist(), 'y': pred[indices, 0].tolist()},
        'eta':   {'x': y[indices, 1].tolist(), 'y': pred[indices, 1].tolist()},
        'gamma': {'x': y[indices, 2].tolist(), 'y': pred[indices, 2].tolist()},
    }


def _compute_boxplot_stats(values):
    """Compute box plot statistics from a list of values."""
    if not values:
        return None
    arr = sorted(values)
    n = len(arr)
    q1 = arr[n // 4] if n >= 4 else arr[0]
    q3 = arr[3 * n // 4] if n >= 4 else arr[-1]
    median = arr[n // 2]
    mean = sum(arr) / n
    iqr = q3 - q1
    lo = q1 - 1.5 * iqr
    hi = q3 + 1.5 * iqr
    whisker_data = [v for v in arr if lo <= v <= hi]
    outliers = n - len(whisker_data)
    return {
        'min': min(whisker_data) if whisker_data else arr[0],
        'q1': q1, 'median': median, 'q3': q3,
        'max': max(whisker_data) if whisker_data else arr[-1],
        'mean': mean, 'count': n, 'outlier_count': outliers,
    }


def _build_boxplot(y_true, y_pred):
    """Build boxplot data grouped by true value for each parameter."""
    result = {}
    param_names = ['beta', 'eta', 'gamma']
    for pi, param in enumerate(param_names):
        groups = {}
        for i in range(len(y_true)):
            tv = y_true[i, pi]
            pv = y_pred[i, pi]
            groups.setdefault(tv, []).append(pv)
        items = []
        for tv in sorted(groups):
            stats = _compute_boxplot_stats(groups[tv])
            if stats:
                items.append({'label': str(tv), 'true_val': float(tv), **stats})
        result[param] = items
    return result


# ============================================================
# Main
# ============================================================

def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f'Device: {device}')

    # Pre-load all test data by (vtype, n)
    test_data = {}
    for vtype in VTYPES:
        for n in SAMPLE_SIZES:
            path = os.path.join(TEST_DATA_DIR, f'test_data_{vtype}_n{n}.csv')
            if os.path.exists(path):
                X, y, _ = load_test_csv(path)
                test_data[(vtype, n)] = (X, y)
    print(f'Loaded {len(test_data)} test data files')

    count = 0
    for scheme in ALL_SCHEMES:
        print(f'\n--- {scheme} ---')

        # 1. Load validation predictions (for ig histogram + breakdown)
        predictions = {}
        metrics_by_n = {}

        if scheme in UNIFIED_SCHEMES:
            path = os.path.join(VALIDATION_DIR, f'direct_estimation_validation_predictions_{scheme}.csv')
            if os.path.exists(path):
                all_rows = load_validation_csv(path)
                for n in SAMPLE_SIZES:
                    rows = [r for r in all_rows if r.get('n') == n]
                    if rows:
                        predictions[n] = rows
                        metrics_by_n[n] = _calc_metrics(rows)
        else:
            for n in SAMPLE_SIZES:
                path = _validation_csv_path(scheme, n)
                if os.path.exists(path):
                    rows = load_validation_csv(path)
                    if rows:
                        predictions[n] = rows
                        metrics_by_n[n] = _calc_metrics(rows)

        if not predictions:
            print(f'  No validation data, skipping')
            continue

        # 2. Build scatter + boxplot data by validation type
        scatter_by_vtype = {}
        boxplot_by_vtype = {}

        # ig: use validation CSV predictions (already have pred values)
        ig_scatter = {}
        ig_y_true, ig_y_pred = [], []
        for n, rows in predictions.items():
            sampled = stratified_sample(rows, 'true_beta', SCATTER_SAMPLE)
            ig_scatter[str(n)] = {
                'beta':  {'x': [r['true_beta']  for r in sampled], 'y': [r['pred_beta']  for r in sampled]},
                'eta':   {'x': [r['true_eta']   for r in sampled], 'y': [r['pred_eta']   for r in sampled]},
                'gamma': {'x': [r['true_gamma'] for r in sampled], 'y': [r['pred_gamma'] for r in sampled]},
            }
            for r in rows:
                ig_y_true.append([r['true_beta'], r['true_eta'], r['true_gamma']])
                ig_y_pred.append([r['pred_beta'], r['pred_eta'], r['pred_gamma']])
        scatter_by_vtype['ig'] = ig_scatter
        boxplot_by_vtype['ig'] = _build_boxplot(
            np.array(ig_y_true), np.array(ig_y_pred))

        # ip/ex: load test data, run inference, sample + boxplot
        for vtype in ['ip', 'ex']:
            vt_scatter = {}
            all_y_true, all_y_pred = [], []
            for n in SAMPLE_SIZES:
                key = (vtype, n)
                if key not in test_data:
                    continue
                X_test, y_test = test_data[key]
                pred = load_model_and_predict(scheme, n, X_test, device)
                if pred is None:
                    continue
                vt_scatter[str(n)] = _sample_scatter(X_test, y_test, pred, SCATTER_SAMPLE)
                all_y_true.append(y_test)
                all_y_pred.append(pred)
                print(f'  {vtype} n={n}: inferred {X_test.shape[0]} rows')
            scatter_by_vtype[vtype] = vt_scatter
            if all_y_true:
                boxplot_by_vtype[vtype] = _build_boxplot(
                    np.vstack(all_y_true), np.vstack(all_y_pred))

        # 3. Build histograms + breakdown (from validation data only = ig)
        histograms = {}
        for param in ['beta', 'eta', 'gamma']:
            errors = []
            for rows in predictions.values():
                for r in rows:
                    tv = r[f'true_{param}']
                    pv = r[f'pred_{param}']
                    if abs(tv) > 1e-10:
                        errors.append((pv - tv) / tv * 100)
            if not errors:
                continue
            mn, mx = min(errors), max(errors)
            rng = mx - mn or 1
            width = rng / HIST_BINS
            bins = [{'x0': mn + i * width, 'x1': mn + (i + 1) * width, 'count': 0}
                    for i in range(HIST_BINS)]
            for v in errors:
                idx = min(int((v - mn) / width), HIST_BINS - 1)
                bins[idx]['count'] += 1
            mean = sum(errors) / len(errors)
            std = math.sqrt(sum((v - mean) ** 2 for v in errors) / len(errors))
            histograms[param] = {'bins': bins, 'mean': mean, 'std': std, 'count': len(errors)}

        breakdown = {
            'by_n': {},
            'by_beta': _group_by_dim(predictions, 'true_beta'),
            'by_eta':  _group_by_dim(predictions, 'true_eta'),
        }
        for n in SAMPLE_SIZES:
            m = metrics_by_n.get(n)
            if m:
                breakdown['by_n'][str(n)] = {
                    'mae_beta': m['mae_beta'], 'mae_eta': m['mae_eta'], 'mae_gamma': m['mae_gamma'],
                    'mre_beta': m['mre_beta'], 'mre_eta': m['mre_eta'], 'mre_gamma': m['mre_gamma'],
                    'count': m['count'],
                }

        # 4. Save
        result = {
            'scatter': scatter_by_vtype,
            'boxplot': boxplot_by_vtype,
            'histograms': histograms,
            'breakdown': breakdown,
        }

        out_path = os.path.join(OUTPUT_DIR, f'direct_estimation_{scheme}_preprocessed.json')
        with open(out_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, separators=(',', ':'))

        size_kb = os.path.getsize(out_path) / 1024
        print(f'  → {size_kb:.1f} KB')
        count += 1

    print(f'\nDone — {count} schemes → {OUTPUT_DIR}')


def _group_by_dim(predictions, group_key):
    groups = {}
    for rows in predictions.values():
        for r in rows:
            k = r[group_key]
            groups.setdefault(k, []).append(r)
    result = {}
    for k in sorted(groups):
        g = groups[k]
        n = len(g)
        result[str(k)] = {
            'mae_beta':  sum(abs(r['pred_beta']  - r['true_beta'])  for r in g) / n,
            'mae_eta':   sum(abs(r['pred_eta']   - r['true_eta'])   for r in g) / n,
            'mae_gamma': sum(abs(r['pred_gamma'] - r['true_gamma']) for r in g) / n,
            'mre_beta':  sum(abs(r['pred_beta']  - r['true_beta'])  / abs(r['true_beta'])  for r in g if abs(r['true_beta'])  > 1e-10) / n,
            'mre_eta':   sum(abs(r['pred_eta']   - r['true_eta'])   / abs(r['true_eta'])   for r in g if abs(r['true_eta'])   > 1e-10) / n,
            'mre_gamma': sum(abs(r['pred_gamma'] - r['true_gamma']) / abs(r['true_gamma']) for r in g if abs(r['true_gamma']) > 1e-10) / n,
            'count': n,
        }
    return result


if __name__ == '__main__':
    main()
