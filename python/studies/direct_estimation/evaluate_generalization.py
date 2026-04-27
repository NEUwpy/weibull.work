"""
直接估计 — 泛化评估脚本

用途：
    用训练好的模型对测试数据做推理，按 validation_type 分组计算精度。
    输出 generalization_metrics.json。

使用方法：
    cd python/studies/direct_estimation

    # 评估全部 8 个方案
    python evaluate_generalization.py

    # 评估指定方案
    python evaluate_generalization.py --schemes a1,b1,c1

输出：
    public/ai/data/direct_estimation_generalization_metrics.json

作者：Claude Code
日期：2026-04-27
"""

import sys
import json
import csv
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime

import torch
import torch.nn as nn
from scipy import stats

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
PUBLIC_DATA_DIR = PROJECT_ROOT / 'public' / 'ai' / 'data'
MODEL_DIR = PROJECT_ROOT / 'python' / 'models' / 'direct_estimation'
DATA_DIR = Path(__file__).parent / 'data'

SAMPLE_SIZES = [5, 7, 10, 15]
VALIDATION_TYPES = ['ig', 'ip', 'ex']


# ============================================================
# 模型定义（与 train_model.py 一致）
# ============================================================

class DirectEstimationMLP(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Linear(32, 3),
        )

    def forward(self, x):
        return self.net(x)


# ============================================================
# 预处理函数（与 train_model.py 一致）
# ============================================================

def preprocess_a2(X):
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
    X_normalized = X / t_bar_safe
    return np.concatenate([X_normalized, t_bar], axis=1)

def preprocess_a3(X):
    t_min = np.min(X, axis=1, keepdims=True)
    return X - t_min

def preprocess_b1(X, n_max):
    N, n = X.shape
    X_padded = np.zeros((N, n_max))
    X_padded[:, :n] = X
    mask = np.zeros((N, n_max))
    mask[:, :n] = 1.0
    return np.concatenate([X_padded, mask], axis=1)

def preprocess_b2(X, n_max):
    N, n = X.shape
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
    X_normalized = X / t_bar_safe
    X_padded = np.zeros((N, n_max))
    X_padded[:, :n] = X_normalized
    mask = np.zeros((N, n_max))
    mask[:, :n] = 1.0
    return np.concatenate([X_padded, t_bar, mask], axis=1)

def preprocess_c1(X):
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_std = np.std(X, axis=1, keepdims=True)
    t_min = np.min(X, axis=1, keepdims=True)
    t_max = np.max(X, axis=1, keepdims=True)
    return np.concatenate([t_bar, t_std, t_min, t_max], axis=1)

def preprocess_c2(X):
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_std = np.std(X, axis=1, keepdims=True)
    t_min = np.min(X, axis=1, keepdims=True)
    t_max = np.max(X, axis=1, keepdims=True)
    t_median = np.median(X, axis=1, keepdims=True)
    skewness = np.array([stats.skew(x) for x in X]).reshape(-1, 1)
    kurtosis = np.array([stats.kurtosis(x) for x in X]).reshape(-1, 1)
    return np.concatenate([t_bar, t_std, t_min, t_max, skewness, kurtosis, t_median], axis=1)

def preprocess_c3(X):
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_std = np.std(X, axis=1, keepdims=True)
    t_min = np.min(X, axis=1, keepdims=True)
    t_max = np.max(X, axis=1, keepdims=True)
    t_median = np.median(X, axis=1, keepdims=True)
    skewness = np.array([stats.skew(x) for x in X]).reshape(-1, 1)
    kurtosis = np.array([stats.kurtosis(x) for x in X]).reshape(-1, 1)
    q1 = np.percentile(X, 25, axis=1, keepdims=True)
    q3 = np.percentile(X, 75, axis=1, keepdims=True)
    iqr = q3 - q1
    t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
    cv = t_std / t_bar_safe
    return np.concatenate([t_bar, t_std, t_min, t_max, skewness, kurtosis, t_median, q1, q3, iqr, cv], axis=1)


# ============================================================
# 数据加载
# ============================================================

def load_test_csv(csv_path: Path):
    """加载测试数据 CSV，返回 (X, y, validation_type)"""
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append(row)

    # 列结构: n, beta, eta, gamma, validation_type, t1, t2, ..., tn
    data = []
    vtypes = []
    for row in rows:
        n = int(row[0])
        beta = float(row[1])
        eta = float(row[2])
        gamma = float(row[3])
        vtype = row[4]
        samples = [float(v) for v in row[5:5+n]]
        data.append([n, beta, eta, gamma] + samples)
        vtypes.append(vtype)

    data = np.array(data)
    n = int(data[0, 0])
    X = data[:, 4:4+n]
    y = data[:, 1:4]
    return X, y, vtypes


# ============================================================
# 模型加载与推理
# ============================================================

def load_model_and_predict(scheme: str, n: int, X: np.ndarray, device: torch.device):
    """加载模型并对 X 做推理，返回预测值 (原始尺度)"""
    # 确定模型文件路径
    if scheme == 'b1' or scheme == 'b2':
        model_path = MODEL_DIR / f'{scheme}_model.pth'
    else:
        suffix = f'_{scheme}' if scheme != 'a1' else ''
        model_path = MODEL_DIR / f'n{n}{suffix}_model.pth'

    if not model_path.exists():
        return None

    checkpoint = torch.load(model_path, map_location=device, weights_only=False)
    input_dim = checkpoint['input_dim']
    preprocessing = checkpoint.get('preprocessing', scheme)
    scaler_params = checkpoint['scaler_params']
    y_scaler = checkpoint['y_scaler']

    # 预处理
    n_max = checkpoint.get('n_max', 15)
    if preprocessing == 'a1':
        X_processed = X
    elif preprocessing == 'a2':
        X_processed = preprocess_a2(X)
    elif preprocessing == 'a3':
        X_processed = preprocess_a3(X)
    elif preprocessing == 'b1':
        X_processed = preprocess_b1(X, n_max)
    elif preprocessing == 'b2':
        X_processed = preprocess_b2(X, n_max)
    elif preprocessing == 'c1':
        X_processed = preprocess_c1(X)
    elif preprocessing == 'c2':
        X_processed = preprocess_c2(X)
    elif preprocessing == 'c3':
        X_processed = preprocess_c3(X)
    else:
        X_processed = X

    # 标准化输入
    x_mean = np.array(scaler_params['x_mean'])
    x_std = np.array(scaler_params['x_std'])
    X_norm = (X_processed - x_mean) / x_std

    # 推理
    model = DirectEstimationMLP(input_dim=input_dim)
    model.load_state_dict(checkpoint['model_state_dict'])
    model.to(device)
    model.eval()

    X_tensor = torch.FloatTensor(X_norm).to(device)
    with torch.no_grad():
        pred_norm = model(X_tensor).cpu().numpy()

    # 反归一化
    y_mean = np.array(y_scaler['y_mean'])
    y_std = np.array(y_scaler['y_std'])
    pred = pred_norm * y_std + y_mean

    return pred


# ============================================================
# 指标计算
# ============================================================

def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray):
    """计算 MAE 和 MRE"""
    metrics = {}
    param_names = ['beta', 'eta', 'gamma']

    for i, name in enumerate(param_names):
        true_vals = y_true[:, i]
        pred_vals = y_pred[:, i]

        mae = float(np.mean(np.abs(pred_vals - true_vals)))
        with np.errstate(divide='ignore', invalid='ignore'):
            rel_errors = np.abs(pred_vals - true_vals) / np.where(np.abs(true_vals) < 1e-6, 1e-6, np.abs(true_vals))
        mre = float(np.mean(rel_errors))

        metrics[f'mae_{name}'] = mae
        metrics[f'mre_{name}'] = mre

    metrics['count'] = len(y_true)
    return metrics


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='直接估计 — 泛化评估')
    parser.add_argument('--schemes', type=str, default='a1,a2,a3,b1,b2,c1,c2,c3',
                        help='评估方案列表 (默认: 全部 8 个)')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='测试数据目录 (默认: ./data)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='输出目录 (默认: public/ai/data/)')

    args = parser.parse_args()

    schemes = args.schemes.split(',')
    data_dir = Path(args.data_dir) if args.data_dir else DATA_DIR
    output_dir = Path(args.output_dir) if args.output_dir else PUBLIC_DATA_DIR
    output_dir.mkdir(parents=True, exist_ok=True)

    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"设备: {device}")
    print(f"方案: {schemes}")
    print("=" * 60)

    all_results = {}

    for scheme in schemes:
        print(f"\n--- 方案: {scheme} ---")
        scheme_metrics = {}

        for vtype in VALIDATION_TYPES:
            type_metrics_by_n = {}

            for n in SAMPLE_SIZES:
                csv_path = data_dir / f'test_data_{vtype}_n{n}.csv'
                if not csv_path.exists():
                    print(f"  跳过 {vtype} n={n}: 文件不存在")
                    continue

                X, y, vtypes = load_test_csv(csv_path)

                # B-1/B-2 统一模型：用所有 n 的数据
                if scheme in ('b1', 'b2'):
                    pred = load_model_and_predict(scheme, n, X, device)
                else:
                    pred = load_model_and_predict(scheme, n, X, device)

                if pred is None:
                    print(f"  跳过 {scheme} n={n}: 模型不存在")
                    continue

                metrics = compute_metrics(y, pred)
                type_metrics_by_n[f'n{n}'] = metrics

                print(f"  {vtype} n={n}: MAE(β)={metrics['mae_beta']:.4f}, MAE(η)={metrics['mae_eta']:.2f}, MAE(γ)={metrics['mae_gamma']:.2f} ({metrics['count']} 条)")

            # 汇总该 validation_type 的所有 n
            if type_metrics_by_n:
                # 计算加权平均
                total_count = sum(m['count'] for m in type_metrics_by_n.values())
                avg_metrics = {}
                for key in ['mae_beta', 'mae_eta', 'mae_gamma', 'mre_beta', 'mre_eta', 'mre_gamma']:
                    weighted_sum = sum(m[key] * m['count'] for m in type_metrics_by_n.values())
                    avg_metrics[key] = weighted_sum / total_count if total_count > 0 else 0
                avg_metrics['count'] = total_count

                scheme_metrics[vtype] = {
                    'overall': avg_metrics,
                    'by_n': type_metrics_by_n,
                }

        all_results[scheme] = scheme_metrics

    # 保存结果
    output_path = output_dir / 'direct_estimation_generalization_metrics.json'
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump({
            'results': all_results,
            'validation_types': VALIDATION_TYPES,
            'sample_sizes': SAMPLE_SIZES,
            'generated_at': datetime.now().isoformat(timespec='seconds'),
        }, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print(f"泛化评估完成！输出: {output_path}")
    print("=" * 60)

    # 打印汇总对比
    print("\n--- 汇总对比 ---")
    print(f"{'方案':<6} {'类型':<4} {'MAE(β)':<10} {'MAE(η)':<10} {'MAE(γ)':<10} {'MRE(β)':<10} {'MRE(η)':<10}")
    print("-" * 60)
    for scheme in schemes:
        if scheme not in all_results:
            continue
        for vtype in VALIDATION_TYPES:
            if vtype not in all_results[scheme]:
                continue
            m = all_results[scheme][vtype]['overall']
            print(f"{scheme:<6} {vtype:<4} {m['mae_beta']:<10.4f} {m['mae_eta']:<10.2f} {m['mae_gamma']:<10.2f} {m['mre_beta']*100:<10.1f}% {m['mre_eta']*100:<10.1f}%")


if __name__ == '__main__':
    main()
