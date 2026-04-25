"""
MDM 偏移量 δ 优化 — PyTorch 模型训练脚本

用途：
    读取 generate_training_data.py 生成的 CSV，训练全连接 MLP 模型。
    按样本量 n 分别训练独立模型。

使用方法：
    cd python/studies/mdm_delta

    # 使用默认参数训练
    python train_model.py

    # 指定数据目录和输出目录
    python train_model.py --data-dir ./data --output-dir ../../models/mdm_delta

    # 自定义超参数
    python train_model.py --epochs 200 --lr 0.001 --batch-size 32

输出文件：
    models/mdm_delta/
    ├── n5_model.pth          # n=5 的模型权重
    ├── n10_model.pth         # n=10 的模型权重
    ├── n5_metrics.json       # n=5 的训练指标
    └── n10_metrics.json      # n=10 的训练指标

作者：Claude Code
日期：2026-04-25
"""

import sys
import os
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

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent


class DeltaMLP(nn.Module):
    """全连接 MLP：输入样本数据，输出最优偏移量 δ"""

    def __init__(self, input_dim: int, hidden1: int = 64, hidden2: int = 32):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, hidden1),
            nn.ReLU(),
            nn.Linear(hidden1, hidden2),
            nn.ReLU(),
            nn.Linear(hidden2, 1),
            nn.Sigmoid()  # 输出 [0, 1]，后续缩放到 δ 范围
        )

    def forward(self, x):
        return self.net(x)


def load_training_data(csv_path: Path):
    """加载训练数据 CSV，返回 (X, y) numpy 数组"""
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append([float(v) for v in row])

    data = np.array(rows)
    # 列结构: [n, t1, t2, ..., tn, optimal_delta, best_mse]
    # X = t1, t2, ..., tn (列 1 到 -2)
    # y = optimal_delta (列 -2)
    X = data[:, 1:-2]  # 样本数据
    y = data[:, -2]    # 最优 δ

    return X, y


def normalize_data(X_train, y_train, X_val, y_val, delta_min, delta_max):
    """
    数据标准化：
    - X: 按列标准化为零均值、单位方差
    - y: 缩放到 [0, 1] 范围
    返回: (X_train_norm, y_train_norm, X_val_norm, y_val_norm, scaler_params)
    """
    # X 标准化参数（从训练集计算）
    x_mean = np.mean(X_train, axis=0)
    x_std = np.std(X_train, axis=0)
    x_std[x_std < 1e-10] = 1.0  # 避免除零

    X_train_norm = (X_train - x_mean) / x_std
    X_val_norm = (X_val - x_mean) / x_std

    # y 缩放到 [0, 1]
    y_train_norm = (y_train - delta_min) / (delta_max - delta_min)
    y_val_norm = (y_val - delta_min) / (delta_max - delta_min)

    scaler_params = {
        'x_mean': x_mean.tolist(),
        'x_std': x_std.tolist(),
        'delta_min': delta_min,
        'delta_max': delta_max,
    }

    return X_train_norm, y_train_norm, X_val_norm, y_val_norm, scaler_params


def split_data(X, y, val_ratio=0.2, seed=42):
    """随机划分训练集和验证集"""
    np.random.seed(seed)
    n = len(X)
    indices = np.random.permutation(n)
    val_size = int(n * val_ratio)

    val_idx = indices[:val_size]
    train_idx = indices[val_size:]

    return X[train_idx], y[train_idx], X[val_idx], y[val_idx]


def train_model(model, train_loader, val_loader, epochs, lr, device, patience=20):
    """训练模型，返回训练历史"""
    model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()

    history = {
        'train_loss': [],
        'val_loss': [],
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
            pred = model(X_batch).squeeze()
            loss = criterion(pred, y_batch)
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
                pred = model(X_batch).squeeze()
                loss = criterion(pred, y_batch)
                val_loss_sum += loss.item() * len(y_batch)
                val_count += len(y_batch)

        avg_val_loss = val_loss_sum / val_count

        history['train_loss'].append(avg_train_loss)
        history['val_loss'].append(avg_val_loss)

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

        if (epoch + 1) % 20 == 0:
            print(f"  Epoch {epoch+1}/{epochs}: train_loss={avg_train_loss:.6f}, val_loss={avg_val_loss:.6f}")

    # 恢复最佳模型
    if best_state is not None:
        model.load_state_dict(best_state)

    return model, history, best_epoch, best_val_loss


def evaluate_model(model, X_val_norm, y_val_raw, delta_min, delta_max, device):
    """评估模型，计算指标。X_val_norm 是标准化后的输入，y_val_raw 是原始 δ 值"""
    model.eval()
    X_tensor = torch.FloatTensor(X_val_norm).to(device)
    with torch.no_grad():
        pred_norm = model(X_tensor).squeeze().cpu().numpy()

    # 反归一化到 δ 范围
    pred_delta = pred_norm * (delta_max - delta_min) + delta_min

    # 计算指标
    mse = np.mean((pred_delta - y_val_raw) ** 2)
    mae = np.mean(np.abs(pred_delta - y_val_raw))

    # 预测值分布
    pred_mean = float(np.mean(pred_delta))
    pred_std = float(np.std(pred_delta))
    pred_min = float(np.min(pred_delta))
    pred_max = float(np.max(pred_delta))

    # 真实值分布
    true_mean = float(np.mean(y_val_raw))
    true_std = float(np.std(y_val_raw))

    return {
        'mse': float(mse),
        'mae': float(mae),
        'rmse': float(np.sqrt(mse)),
        'pred_mean': pred_mean,
        'pred_std': pred_std,
        'pred_min': pred_min,
        'pred_max': pred_max,
        'true_mean': true_mean,
        'true_std': true_std,
        'val_samples': len(y_val_raw),
    }


def main():
    parser = argparse.ArgumentParser(description='MDM 偏移量 δ 优化 — 模型训练')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='训练数据目录 (默认: ./data)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='模型输出目录 (默认: ../../models/mdm_delta)')
    parser.add_argument('--epochs', type=int, default=100,
                        help='最大训练轮数 (默认: 100)')
    parser.add_argument('--lr', type=float, default=0.001,
                        help='学习率 (默认: 0.001)')
    parser.add_argument('--batch-size', type=int, default=32,
                        help='批次大小 (默认: 32)')
    parser.add_argument('--hidden1', type=int, default=64,
                        help='第一隐藏层神经元数 (默认: 64)')
    parser.add_argument('--hidden2', type=int, default=32,
                        help='第二隐藏层神经元数 (默认: 32)')
    parser.add_argument('--delta-min', type=float, default=0.01,
                        help='δ 最小值 (默认: 0.01)')
    parser.add_argument('--delta-max', type=float, default=0.50,
                        help='δ 最大值 (默认: 0.50)')
    parser.add_argument('--patience', type=int, default=20,
                        help='早停耐心 (默认: 20)')
    parser.add_argument('--val-ratio', type=float, default=0.2,
                        help='验证集比例 (默认: 0.2)')

    args = parser.parse_args()

    # 目录
    data_dir = Path(args.data_dir) if args.data_dir else Path(__file__).parent / 'data'
    output_dir = Path(args.output_dir) if args.output_dir else PROJECT_ROOT / 'python' / 'models' / 'mdm_delta'
    output_dir.mkdir(parents=True, exist_ok=True)

    # 设备
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    print(f"设备: {device}")

    # 找到所有训练数据文件
    csv_files = sorted(data_dir.glob('training_data_n*.csv'))
    if not csv_files:
        print(f"错误: 在 {data_dir} 中未找到训练数据文件")
        sys.exit(1)

    print(f"找到 {len(csv_files)} 个训练数据文件")
    print("=" * 60)

    all_metrics = {}

    for csv_path in csv_files:
        # 提取样本量 n
        n_str = csv_path.stem.replace('training_data_n', '')
        n = int(n_str)
        print(f"\n--- 训练 n={n} 的模型 ---")

        # 加载数据
        X, y = load_training_data(csv_path)
        print(f"  数据量: {len(X)} 条，输入维度: {X.shape[1]}")

        # 划分
        X_train, y_train, X_val, y_val = split_data(X, y, val_ratio=args.val_ratio)
        print(f"  训练集: {len(X_train)}，验证集: {len(X_val)}")

        # 标准化
        X_train_norm, y_train_norm, X_val_norm, y_val_norm, scaler_params = normalize_data(
            X_train, y_train, X_val, y_val, args.delta_min, args.delta_max
        )
        print(f"  X 均值范围: [{np.min(scaler_params['x_mean']):.1f}, {np.max(scaler_params['x_mean']):.1f}]")
        print(f"  X 标准差范围: [{np.min(scaler_params['x_std']):.1f}, {np.max(scaler_params['x_std']):.1f}]")
        print(f"  y (δ) 范围: [{args.delta_min}, {args.delta_max}] → [0, 1]")

        # 构建 DataLoader（使用标准化后的数据）
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
        model = DeltaMLP(input_dim=n, hidden1=args.hidden1, hidden2=args.hidden2)
        print(f"  模型结构: {model.net}")

        # 训练
        model, history, best_epoch, best_val_loss = train_model(
            model, train_loader, val_loader,
            epochs=args.epochs, lr=args.lr, device=device,
            patience=args.patience
        )

        # 评估（使用标准化输入，但原始 y 值计算指标）
        metrics = evaluate_model(model, X_val_norm, y_val, args.delta_min, args.delta_max, device)
        metrics['best_epoch'] = best_epoch + 1
        metrics['best_val_loss'] = float(best_val_loss)
        metrics['input_dim'] = n
        metrics['train_samples'] = len(X_train)
        metrics['architecture'] = f'Linear({n},{args.hidden1}) -> ReLU -> Linear({args.hidden1},{args.hidden2}) -> ReLU -> Linear({args.hidden2},1) -> Sigmoid'

        print(f"  最佳 epoch: {best_epoch+1}")
        print(f"  验证 MSE: {metrics['mse']:.6f}")
        print(f"  验证 MAE: {metrics['mae']:.6f}")
        print(f"  验证 RMSE: {metrics['rmse']:.6f}")
        print(f"  预测 δ 范围: [{metrics['pred_min']:.4f}, {metrics['pred_max']:.4f}]")
        print(f"  真实 δ 范围: [{metrics['true_mean']:.4f} ± {metrics['true_std']:.4f}]")

        # 保存模型
        model_path = output_dir / f'n{n}_model.pth'
        torch.save({
            'model_state_dict': model.state_dict(),
            'input_dim': n,
            'hidden1': args.hidden1,
            'hidden2': args.hidden2,
            'delta_min': args.delta_min,
            'delta_max': args.delta_max,
            'scaler_params': scaler_params,
            'metrics': metrics,
        }, model_path)
        print(f"  模型已保存: {model_path}")

        # 保存指标
        metrics_path = output_dir / f'n{n}_metrics.json'
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump({
                'metrics': metrics,
                'history': {
                    'train_loss': history['train_loss'],
                    'val_loss': history['val_loss'],
                },
                'config': {
                    'epochs': args.epochs,
                    'lr': args.lr,
                    'batch_size': args.batch_size,
                    'hidden1': args.hidden1,
                    'hidden2': args.hidden2,
                    'delta_min': args.delta_min,
                    'delta_max': args.delta_max,
                    'patience': args.patience,
                    'val_ratio': args.val_ratio,
                },
                'trained_at': datetime.now().isoformat(timespec='seconds'),
            }, f, indent=2, ensure_ascii=False)

        all_metrics[f'n{n}'] = metrics

    # 总结
    print("\n" + "=" * 60)
    print("训练完成！")
    print(f"模型目录: {output_dir}")
    for key, m in all_metrics.items():
        print(f"  {key}: MSE={m['mse']:.6f}, MAE={m['mae']:.6f}, RMSE={m['rmse']:.6f}")
    print("=" * 60)


if __name__ == '__main__':
    main()
