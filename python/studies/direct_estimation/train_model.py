"""
直接估计 — PyTorch 模型训练脚本

用途：
    读取 generate_training_data.py 生成的 CSV，训练全连接 MLP 模型。
    按 n 分别训练独立模型，输入原始样本，直接输出 β,η,γ。

架构（V0 已确认）：
    Linear(n,64)→ReLU→Linear(64,32)→ReLU→Linear(32,3)
    输出层：线性，直接输出原始值（无 Sigmoid）

损失函数：
    相对 MSE = ((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/γ)²

训练超参：
    Adam, lr=0.001, batch=32, ReduceLROnPlateau(patience=10, factor=0.5)
    max_epoch=300, 早停 patience=30, 验证比例 20%

使用方法：
    cd python/studies/direct_estimation

    # 训练所有 n 的模型（默认）
    python train_model.py

    # 自定义超参数
    python train_model.py --epochs 300 --lr 0.001 --batch-size 32

输出文件：
    models/direct_estimation/
    ├── n5_model.pth               # n=5 的模型权重
    ├── n10_model.pth              # n=10 的模型权重
    ├── n5_metrics.json            # n=5 的训练指标
    ├── n10_metrics.json           # n=10 的训练指标

    data/
    ├── training_history_n5.csv    # n=5 的训练 loss 曲线
    ├── training_history_n10.csv   # n=10 的训练 loss 曲线
    ├── validation_predictions_n5.csv   # n=5 的验证集预测
    └── validation_predictions_n10.csv  # n=10 的验证集预测

作者：Claude Code
日期：2026-04-26
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
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from scipy import stats

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


# ============================================================
# 模型定义
# ============================================================

class DirectEstimationMLP(nn.Module):
    """直接估计 MLP：样本 → (β, η, γ)
    Linear(n,128)→ReLU→Linear(128,64)→ReLU→Linear(64,32)→ReLU→Linear(32,3)
    输出层线性，直接输出原始值
    """

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
# 数据加载
# ============================================================

def load_training_data(csv_path: Path):
    """加载训练数据 CSV，返回 (X, y) numpy 数组
    CSV 格式: n,beta,eta,gamma,t1,...,tn
    X = t1, t2, ..., tn
    y = [beta, eta, gamma]
    """
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append([float(v) for v in row])

    data = np.array(rows)
    # 列结构: [n, beta, eta, gamma, t1, t2, ..., tn]
    n = int(data[0, 0])
    X = data[:, 4:4+n]       # 样本数据 t1...tn
    y = data[:, 1:4]          # [beta, eta, gamma]

    return X, y


# ============================================================
# 损失函数
# ============================================================

def relative_mse_loss(pred, target):
    """相对 MSE 损失：((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/γ)²
    消除量纲差异，三参数同等权重
    """
    # 防止除零：给 gamma 加一个小常数（gamma 可能为 0）
    safe_target = target.clone()
    safe_target[:, 2] = torch.where(
        torch.abs(safe_target[:, 2]) < 1e-6,
        torch.ones_like(safe_target[:, 2]) * 1e-6,
        safe_target[:, 2]
    )
    relative_error = (pred - target) / safe_target
    return torch.mean(relative_error ** 2)


def normalized_mse_loss(pred, target):
    """归一化后的 MSE 损失（用于输出归一化的训练）"""
    return torch.mean((pred - target) ** 2)


# ============================================================
# 数据预处理
# ============================================================

def normalize_X(X_train, X_val):
    """标准化输入 X（按列），返回标准化后的数据和参数"""
    x_mean = np.mean(X_train, axis=0)
    x_std = np.std(X_train, axis=0)
    x_std[x_std < 1e-10] = 1.0  # 避免除零

    X_train_norm = (X_train - x_mean) / x_std
    X_val_norm = (X_val - x_mean) / x_std

    scaler_params = {
        'x_mean': x_mean.tolist(),
        'x_std': x_std.tolist(),
    }

    return X_train_norm, X_val_norm, scaler_params


def normalize_y(y_train, y_val):
    """标准化输出 y（按列），返回标准化后的数据和参数"""
    y_mean = np.mean(y_train, axis=0)
    y_std = np.std(y_train, axis=0)
    y_std[y_std < 1e-10] = 1.0  # 避免除零

    y_train_norm = (y_train - y_mean) / y_std
    y_val_norm = (y_val - y_mean) / y_std

    y_scaler = {
        'y_mean': y_mean.tolist(),
        'y_std': y_std.tolist(),
    }

    return y_train_norm, y_val_norm, y_scaler


def preprocess_a2(X):
    """A-2 预处理：除以均值 + 拼接均值
    输入: X shape (N, n)  原始样本 [t1, t2, ..., tn]
    输出: X_a2 shape (N, n+1)  [t1/t̄, t2/t̄, ..., tn/t̄, t̄]
    """
    t_bar = np.mean(X, axis=1, keepdims=True)  # (N, 1)
    t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
    X_normalized = X / t_bar_safe  # (N, n)
    X_a2 = np.concatenate([X_normalized, t_bar], axis=1)  # (N, n+1)
    return X_a2


def preprocess_c1(X):
    """C-1 预处理：基础统计量
    输入: X shape (N, n)
    输出: X_c1 shape (N, 4)  [t̄, s, t_min, t_max]
    """
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_std = np.std(X, axis=1, keepdims=True)
    t_min = np.min(X, axis=1, keepdims=True)
    t_max = np.max(X, axis=1, keepdims=True)
    return np.concatenate([t_bar, t_std, t_min, t_max], axis=1)


def preprocess_c2(X):
    """C-2 预处理：扩展统计量
    输入: X shape (N, n)
    输出: X_c2 shape (N, 7)  [t̄, s, t_min, t_max, skewness, kurtosis, median]
    """
    t_bar = np.mean(X, axis=1, keepdims=True)
    t_std = np.std(X, axis=1, keepdims=True)
    t_min = np.min(X, axis=1, keepdims=True)
    t_max = np.max(X, axis=1, keepdims=True)
    t_median = np.median(X, axis=1, keepdims=True)

    # 偏度和峰度
    skewness = np.array([stats.skew(x) for x in X]).reshape(-1, 1)
    kurtosis = np.array([stats.kurtosis(x) for x in X]).reshape(-1, 1)

    return np.concatenate([t_bar, t_std, t_min, t_max, skewness, kurtosis, t_median], axis=1)


def preprocess_a3(X):
    """A-3 预处理：去位置（减去最小值）
    输入: X shape (N, n)  原始样本 [t1, t2, ..., tn]
    输出: X_a3 shape (N, n)  [t1-t_min, t2-t_min, ..., tn-t_min]
    """
    t_min = np.min(X, axis=1, keepdims=True)
    return X - t_min


def preprocess_b1(X, n_max):
    """B-1 预处理：填充 + 掩码
    输入: X shape (N, n)  原始样本
    输出: X_b1 shape (N, n_max*2)  [t1,...,tn,0,...,0, 1,...,1,0,...,0]
    """
    N = X.shape[0]
    n = X.shape[1]

    # 填充到 n_max
    X_padded = np.zeros((N, n_max))
    X_padded[:, :n] = X

    # 创建掩码
    mask = np.zeros((N, n_max))
    mask[:, :n] = 1.0

    # 拼接
    return np.concatenate([X_padded, mask], axis=1)


def preprocess_b2(X, n_max):
    """B-2 预处理：除以均值 + 填充 + 掩码
    输入: X shape (N, n)  原始样本
    输出: X_b2 shape (N, n_max*2+1)  [t1/t̄,...,tn/t̄,0,...,0, t̄, mask]
    """
    N = X.shape[0]
    n = X.shape[1]

    t_bar = np.mean(X, axis=1, keepdims=True)  # (N, 1)
    t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
    X_normalized = X / t_bar_safe  # (N, n)

    # 填充到 n_max
    X_padded = np.zeros((N, n_max))
    X_padded[:, :n] = X_normalized

    # 创建掩码
    mask = np.zeros((N, n_max))
    mask[:, :n] = 1.0

    # 拼接: [normalized_padded, t_bar, mask]
    return np.concatenate([X_padded, t_bar, mask], axis=1)


def preprocess_c3(X):
    """C-3 预处理：最大化统计量（11 特征）
    输入: X shape (N, n)
    输出: X_c3 shape (N, 11)
    [t̄, s, t_min, t_max, skewness, kurtosis, median, Q1, Q3, IQR, CV]
    """
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

    # 变异系数 CV = std / mean
    t_bar_safe = np.where(t_bar < 1e-10, 1e-10, t_bar)
    cv = t_std / t_bar_safe

    return np.concatenate([t_bar, t_std, t_min, t_max, skewness, kurtosis, t_median, q1, q3, iqr, cv], axis=1)


def split_data(X, y, val_ratio=0.2, seed=42):
    """随机划分训练集和验证集"""
    np.random.seed(seed)
    n = len(X)
    indices = np.random.permutation(n)
    val_size = int(n * val_ratio)

    val_idx = indices[:val_size]
    train_idx = indices[val_size:]

    return X[train_idx], y[train_idx], X[val_idx], y[val_idx]


# ============================================================
# 训练
# ============================================================

def train_model(model, train_loader, val_loader, epochs, lr, device, patience=30):
    """训练模型（使用归一化 MSE），返回训练历史"""
    model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    scheduler = optim.lr_scheduler.ReduceLROnPlateau(
        optimizer, mode='min', factor=0.5, patience=10
    )

    history = {
        'train_loss': [],
        'val_loss': [],
        'lr': [],
    }

    best_val_loss = float('inf')
    best_epoch = 0
    best_state = None
    no_improve = 0

    for epoch in range(epochs):
        # 训练
        model.train()
        train_loss_sum = 0
        train_count = 0
        for X_batch, y_batch in train_loader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)

            optimizer.zero_grad()
            pred = model(X_batch)
            loss = normalized_mse_loss(pred, y_batch)
            loss.backward()
            optimizer.step()

            train_loss_sum += loss.item() * len(y_batch)
            train_count += len(y_batch)

        avg_train_loss = train_loss_sum / train_count

        # 验证
        model.eval()
        val_loss_sum = 0
        val_count = 0
        with torch.no_grad():
            for X_batch, y_batch in val_loader:
                X_batch = X_batch.to(device)
                y_batch = y_batch.to(device)
                pred = model(X_batch)
                loss = normalized_mse_loss(pred, y_batch)
                val_loss_sum += loss.item() * len(y_batch)
                val_count += len(y_batch)

        avg_val_loss = val_loss_sum / val_count

        history['train_loss'].append(avg_train_loss)
        history['val_loss'].append(avg_val_loss)
        history['lr'].append(optimizer.param_groups[0]['lr'])

        # 学习率调度
        scheduler.step(avg_val_loss)

        # 早停
        if avg_val_loss < best_val_loss:
            best_val_loss = avg_val_loss
            best_epoch = epoch
            best_state = {k: v.cpu().clone() for k, v in model.state_dict().items()}
            no_improve = 0
        else:
            no_improve += 1

        if no_improve >= patience:
            print(f"  早停于 epoch {epoch+1}，最佳 epoch {best_epoch+1}")
            break

        if (epoch + 1) % 30 == 0:
            current_lr = optimizer.param_groups[0]['lr']
            print(f"  Epoch {epoch+1}/{epochs}: train_loss={avg_train_loss:.6f}, val_loss={avg_val_loss:.6f}, lr={current_lr:.6f}")

    # 恢复最佳模型
    if best_state is not None:
        model.load_state_dict(best_state)

    return model, history, best_epoch, best_val_loss


# ============================================================
# 评估
# ============================================================

def evaluate_model(model, X_val_norm, y_val, device, y_scaler=None):
    """评估模型，计算指标。y_val 是原始值，y_scaler 用于反归一化预测"""
    model.eval()
    X_tensor = torch.FloatTensor(X_val_norm).to(device)
    with torch.no_grad():
        pred_norm = model(X_tensor).cpu().numpy()

    # 反归一化
    if y_scaler:
        y_mean = np.array(y_scaler['y_mean'])
        y_std = np.array(y_scaler['y_std'])
        pred = pred_norm * y_std + y_mean
    else:
        pred = pred_norm

    # 按参数分别计算指标
    param_names = ['beta', 'eta', 'gamma']
    metrics = {}

    for i, name in enumerate(param_names):
        true_vals = y_val[:, i]
        pred_vals = pred[:, i]

        mse = np.mean((pred_vals - true_vals) ** 2)
        mae = np.mean(np.abs(pred_vals - true_vals))
        rmse = np.sqrt(mse)

        # 相对误差（处理 gamma=0 的情况）
        with np.errstate(divide='ignore', invalid='ignore'):
            rel_errors = np.abs(pred_vals - true_vals) / np.where(np.abs(true_vals) < 1e-6, 1e-6, np.abs(true_vals))
        mean_rel_error = np.mean(rel_errors)

        metrics[f'mse_{name}'] = float(mse)
        metrics[f'mae_{name}'] = float(mae)
        metrics[f'rmse_{name}'] = float(rmse)
        metrics[f'mean_relative_error_{name}'] = float(mean_rel_error)

    # 总体相对 MSE
    total_rel_mse = (
        metrics['mse_beta'] / max(np.mean(y_val[:, 0]) ** 2, 1e-10) +
        metrics['mse_eta'] / max(np.mean(y_val[:, 1]) ** 2, 1e-10) +
        metrics['mse_gamma'] / max(np.mean(y_val[:, 2]) ** 2, 1e-10)
    )
    metrics['total_relative_mse'] = float(total_rel_mse)
    metrics['val_samples'] = len(y_val)

    return metrics, pred


def save_training_history(history, output_path):
    """保存训练历史到 CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['epoch', 'train_loss', 'val_loss', 'lr'])
        for i in range(len(history['train_loss'])):
            writer.writerow([
                i + 1,
                round(history['train_loss'][i], 8),
                round(history['val_loss'][i], 8),
                history['lr'][i],
            ])


def save_validation_predictions(y_val, pred, output_path):
    """保存验证集预测结果到 CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['n', 'true_beta', 'true_eta', 'true_gamma',
                          'pred_beta', 'pred_eta', 'pred_gamma'])
        # n 从 y_val 推断不了，统一写 0（由调用方补充）
        for i in range(len(y_val)):
            writer.writerow([
                0,  # placeholder，会被调用方覆盖
                round(float(y_val[i, 0]), 6),
                round(float(y_val[i, 1]), 6),
                round(float(y_val[i, 2]), 6),
                round(float(pred[i, 0]), 6),
                round(float(pred[i, 1]), 6),
                round(float(pred[i, 2]), 6),
            ])


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='直接估计 — 模型训练')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='训练数据目录 (默认: ./data)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='模型输出目录 (默认: ../../models/direct_estimation)')
    parser.add_argument('--epochs', type=int, default=300,
                        help='最大训练轮数 (默认: 300)')
    parser.add_argument('--lr', type=float, default=0.001,
                        help='学习率 (默认: 0.001)')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='批次大小 (默认: 32)')
    parser.add_argument('--patience', type=int, default=30,
                        help='早停耐心 (默认: 30)')
    parser.add_argument('--val-ratio', type=float, default=0.2,
                        help='验证集比例 (默认: 0.2)')
    parser.add_argument('--preprocessing', type=str, default='a1', choices=['a1', 'a2', 'a3', 'b1', 'b2', 'c1', 'c2', 'c3'],
                        help='预处理方案: a1=原始样本, a2=除以均值, a3=去位置, b1=填充+掩码, b2=除以均值+掩码, c1=基础统计量, c2=扩展统计量, c3=最大化统计量 (默认: a1)')
    parser.add_argument('--n-max', type=int, default=15,
                        help='B-1 模式的最大填充长度 (默认: 15)')

    args = parser.parse_args()

    # 目录
    data_dir = Path(args.data_dir) if args.data_dir else Path(__file__).parent / 'data'
    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / 'python' / 'models' / 'direct_estimation'
    output_dir.mkdir(parents=True, exist_ok=True)

    # 设备
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"设备: {device}")

    csv_files = sorted(data_dir.glob('training_data_n*.csv'))
    if not csv_files:
        print(f"错误: 在 {data_dir} 中未找到 training_data_n*.csv 文件")
        sys.exit(1)

    print(f"找到 {len(csv_files)} 个训练数据文件")
    print("=" * 60)

    all_metrics = {}

    # B-1/B-2 模式：统一模型，填充+掩码
    if args.preprocessing in ('b1', 'b2'):
        n_max = args.n_max
        is_b2 = args.preprocessing == 'b2'
        mode_label = 'B-2 除以均值+掩码' if is_b2 else 'B-1 原始+掩码'
        print(f"\n--- {mode_label} 统一模型训练 (n_max={n_max}) ---")

        # 加载所有数据并填充
        X_all, y_all, n_all = [], [], []
        for csv_path in csv_files:
            n_str = csv_path.stem.replace('training_data_n', '')
            n = int(n_str)
            X, y = load_training_data(csv_path)
            if is_b2:
                X_processed = preprocess_b2(X, n_max)
            else:
                X_processed = preprocess_b1(X, n_max)
            X_all.append(X_processed)
            y_all.append(y)
            n_all.append(np.full(len(X), n))
            print(f"  加载 n={n}: {len(X)} 条")

        X_all = np.concatenate(X_all, axis=0)
        y_all = np.concatenate(y_all, axis=0)
        n_all = np.concatenate(n_all, axis=0)
        input_dim = n_max * 2 + (1 if is_b2 else 0)
        print(f"  总数据量: {len(X_all)} 条，输入维度: {input_dim}")

        # 划分（保持 n 分布）
        X_train, y_train, X_val, y_val = split_data(X_all, y_all, val_ratio=args.val_ratio)
        n_train, _, n_val, _ = split_data(n_all, n_all, val_ratio=args.val_ratio)
        print(f"  训练集: {len(X_train)}，验证集: {len(X_val)}")

        # 标准化
        X_train_norm, X_val_norm, scaler_params = normalize_X(X_train, X_val)
        y_train_norm, y_val_norm, y_scaler = normalize_y(y_train, y_val)

        # DataLoader
        train_dataset = TensorDataset(torch.FloatTensor(X_train_norm), torch.FloatTensor(y_train_norm))
        val_dataset = TensorDataset(torch.FloatTensor(X_val_norm), torch.FloatTensor(y_val_norm))
        train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=args.batch_size)

        # 模型
        model = DirectEstimationMLP(input_dim=input_dim)
        param_count = sum(p.numel() for p in model.parameters())
        print(f"  模型参数量: {param_count:,}")

        # 训练
        model, history, best_epoch, best_val_loss = train_model(
            model, train_loader, val_loader,
            epochs=args.epochs, lr=args.lr, device=device, patience=args.patience
        )

        # 总体评估
        metrics, pred = evaluate_model(model, X_val_norm, y_val, device, y_scaler=y_scaler)
        metrics['best_epoch'] = best_epoch + 1
        metrics['best_val_loss'] = float(best_val_loss)
        metrics['input_dim'] = input_dim
        metrics['train_samples'] = len(X_train)
        metrics['preprocessing'] = args.preprocessing
        metrics['architecture'] = f'Linear({input_dim},128)->ReLU->Linear(128,64)->ReLU->Linear(64,32)->ReLU->Linear(32,3)'

        print(f"\n  总体验证 MAE (beta):  {metrics['mae_beta']:.4f}")
        print(f"  总体验证 MAE (eta):   {metrics['mae_eta']:.2f}")
        print(f"  总体相对 MSE: {metrics['total_relative_mse']:.6f}")

        # 保存模型
        b_prefix = args.preprocessing
        model_path = output_dir / f'{b_prefix}_model.pth'
        torch.save({
            'model_state_dict': model.state_dict(),
            'input_dim': input_dim,
            'n_max': n_max,
            'preprocessing': args.preprocessing,
            'scaler_params': scaler_params,
            'y_scaler': y_scaler,
            'metrics': metrics,
        }, model_path)
        print(f"  模型已保存: {model_path}")

        # 保存总体指标
        metrics_path = output_dir / f'{b_prefix}_metrics.json'
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump({
                'metrics': metrics,
                'history': {'train_loss': history['train_loss'], 'val_loss': history['val_loss'], 'lr': history['lr']},
                'config': {'epochs': args.epochs, 'lr': args.lr, 'batch_size': args.batch_size, 'n_max': n_max},
                'trained_at': datetime.now().isoformat(timespec='seconds'),
            }, f, indent=2, ensure_ascii=False)

        # 按 n 分别评估
        print(f"\n  --- 按样本量分别评估 ---")
        for n_cur in np.unique(n_val):
            mask = n_val == n_cur
            if mask.sum() == 0:
                continue
            y_n = y_val[mask]
            X_n_norm = X_val_norm[mask]
            m_n, pred_n = evaluate_model(model, X_n_norm, y_n, device, y_scaler=y_scaler)
            print(f"  n={int(n_cur)}: MAE(β)={m_n['mae_beta']:.4f}, MAE(η)={m_n['mae_eta']:.2f}, 样本数={mask.sum()}")
            all_metrics[f'{b_prefix}_n{int(n_cur)}'] = m_n

        # 保存训练历史
        history_path = data_dir / f'training_history_{b_prefix}.csv'
        save_training_history(history, history_path)

        # 保存验证预测
        val_pred_path = data_dir / f'validation_predictions_{b_prefix}.csv'
        with open(val_pred_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['n', 'true_beta', 'true_eta', 'true_gamma', 'pred_beta', 'pred_eta', 'pred_gamma'])
            for i in range(len(y_val)):
                writer.writerow([
                    int(n_val[i]),
                    round(float(y_val[i, 0]), 6), round(float(y_val[i, 1]), 6), round(float(y_val[i, 2]), 6),
                    round(float(pred[i, 0]), 6), round(float(pred[i, 1]), 6), round(float(pred[i, 2]), 6),
                ])

        print(f"\n  {mode_label} 统一模型训练完成!")
        sys.exit(0)

    for csv_path in csv_files:
        # 提取样本量 n
        n_str = csv_path.stem.replace('training_data_n', '')
        n = int(n_str)
        print(f"\n--- 训练直接估计模型 (n={n}, 预处理={args.preprocessing}) ---")

        # 加载数据
        X, y = load_training_data(csv_path)
        print(f"  数据量: {len(X)} 条，原始输入维度: {X.shape[1]}")

        # 预处理
        if args.preprocessing == 'a2':
            X = preprocess_a2(X)
            input_dim = n + 1
            print(f"  A-2 预处理后输入维度: {input_dim}  [t1/t_bar,...,tn/t_bar, t_bar]")
        elif args.preprocessing == 'a3':
            X = preprocess_a3(X)
            input_dim = n
            print(f"  A-3 预处理后输入维度: {input_dim}  [t1-t_min,...,tn-t_min]")
        elif args.preprocessing == 'c1':
            X = preprocess_c1(X)
            input_dim = 4
            print(f"  C-1 预处理后输入维度: {input_dim}  [mean, std, min, max]")
        elif args.preprocessing == 'c2':
            X = preprocess_c2(X)
            input_dim = 7
            print(f"  C-2 预处理后输入维度: {input_dim}  [mean, std, min, max, skew, kurt, median]")
        elif args.preprocessing == 'c3':
            X = preprocess_c3(X)
            input_dim = 11
            print(f"  C-3 预处理后输入维度: {input_dim}  [mean, std, min, max, skew, kurt, median, Q1, Q3, IQR, CV]")
        else:
            input_dim = n

        # 划分
        X_train, y_train, X_val, y_val = split_data(X, y, val_ratio=args.val_ratio)
        print(f"  训练集: {len(X_train)}，验证集: {len(X_val)}")

        # 标准化输入 X
        X_train_norm, X_val_norm, scaler_params = normalize_X(X_train, X_val)
        print(f"  X 均值范围: [{np.min(scaler_params['x_mean']):.1f}, {np.max(scaler_params['x_mean']):.1f}]")

        # 归一化输出 y
        y_train_norm, y_val_norm, y_scaler = normalize_y(y_train, y_val)
        print(f"  y (beta) range: [{np.min(y[:, 0]):.1f}, {np.max(y[:, 0]):.1f}], mean={y_scaler['y_mean'][0]:.2f}, std={y_scaler['y_std'][0]:.2f}")
        print(f"  y (eta) range: [{np.min(y[:, 1]):.1f}, {np.max(y[:, 1]):.1f}], mean={y_scaler['y_mean'][1]:.1f}, std={y_scaler['y_std'][1]:.1f}")
        print(f"  y (gamma) range: [{np.min(y[:, 2]):.1f}, {np.max(y[:, 2]):.1f}]")

        # 构建 DataLoader（使用归一化的 y）
        train_dataset = TensorDataset(
            torch.FloatTensor(X_train_norm),
            torch.FloatTensor(y_train_norm)
        )
        val_dataset = TensorDataset(
            torch.FloatTensor(X_val_norm),
            torch.FloatTensor(y_val_norm)
        )
        train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True)
        val_loader = DataLoader(val_dataset, batch_size=args.batch_size)

        # 构建模型
        model = DirectEstimationMLP(input_dim=input_dim)
        param_count = sum(p.numel() for p in model.parameters())
        print(f"  模型参数量: {param_count:,}")

        # 训练
        model, history, best_epoch, best_val_loss = train_model(
            model, train_loader, val_loader,
            epochs=args.epochs, lr=args.lr, device=device,
            patience=args.patience
        )

        # 评估（反归一化预测值）
        metrics, pred = evaluate_model(model, X_val_norm, y_val, device, y_scaler=y_scaler)
        metrics['best_epoch'] = best_epoch + 1
        metrics['best_val_loss'] = float(best_val_loss)
        metrics['input_dim'] = input_dim
        metrics['train_samples'] = len(X_train)
        metrics['preprocessing'] = args.preprocessing
        metrics['architecture'] = f'Linear({input_dim},128)->ReLU->Linear(128,64)->ReLU->Linear(64,32)->ReLU->Linear(32,3)'

        print(f"  最佳 epoch: {best_epoch+1}")
        print(f"  验证 MAE (beta):  {metrics['mae_beta']:.4f}")
        print(f"  验证 MAE (eta):   {metrics['mae_eta']:.2f}")
        print(f"  验证 MAE (gamma): {metrics['mae_gamma']:.2f}")
        print(f"  相对 MSE: {metrics['total_relative_mse']:.6f}")

        # 保存模型
        suffix = f'_{args.preprocessing}' if args.preprocessing != 'a1' else ''
        model_path = output_dir / f'n{n}{suffix}_model.pth'
        torch.save({
            'model_state_dict': model.state_dict(),
            'input_dim': input_dim,
            'preprocessing': args.preprocessing,
            'scaler_params': scaler_params,
            'y_scaler': y_scaler,
            'metrics': metrics,
        }, model_path)
        print(f"  模型已保存: {model_path}")

        # 保存指标 + 训练历史
        metrics_path = output_dir / f'n{n}{suffix}_metrics.json'
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump({
                'metrics': metrics,
                'history': {
                    'train_loss': history['train_loss'],
                    'val_loss': history['val_loss'],
                    'lr': history['lr'],
                },
                'config': {
                    'epochs': args.epochs,
                    'lr': args.lr,
                    'batch_size': args.batch_size,
                    'patience': args.patience,
                    'val_ratio': args.val_ratio,
                },
                'trained_at': datetime.now().isoformat(timespec='seconds'),
            }, f, indent=2, ensure_ascii=False)

        # 保存训练历史 CSV
        history_path = data_dir / f'training_history_n{n}{suffix}.csv'
        save_training_history(history, history_path)
        print(f"  训练历史已保存: {history_path}")

        # 保存验证集预测 CSV
        val_pred_path = data_dir / f'validation_predictions_n{n}{suffix}.csv'
        with open(val_pred_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['n', 'true_beta', 'true_eta', 'true_gamma',
                              'pred_beta', 'pred_eta', 'pred_gamma'])
            for i in range(len(y_val)):
                writer.writerow([
                    n,
                    round(float(y_val[i, 0]), 6),
                    round(float(y_val[i, 1]), 6),
                    round(float(y_val[i, 2]), 6),
                    round(float(pred[i, 0]), 6),
                    round(float(pred[i, 1]), 6),
                    round(float(pred[i, 2]), 6),
                ])
        print(f"  验证预测已保存: {val_pred_path}")

        all_metrics[f'n{n}{suffix}'] = metrics

    # 总结
    print("\n" + "=" * 60)
    print("训练完成！")
    print(f"模型目录: {output_dir}")
    for key, m in all_metrics.items():
        print(f"  {key}: MAE(β)={m['mae_beta']:.4f}, MAE(η)={m['mae_eta']:.2f}, MAE(γ)={m['mae_gamma']:.2f}")
    print("=" * 60)


if __name__ == '__main__':
    main()
