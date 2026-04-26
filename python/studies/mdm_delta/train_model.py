"""
MDM 偏移量 δ 优化 — PyTorch 模型训练脚本

用途：
    读取 generate_training_data.py 生成的 CSV，训练两种全连接 MLP 模型：
    - N₂（路线1）：样本 → 最优 δ，按 n 分别训练
    - N₁（路线2）：(β,η,γ) 真值 → 最优 δ，训练一个公共模型

架构（已确认）：
    N₂: Linear(n,128)→ReLU→BN→Linear(128,64)→ReLU→BN→Linear(64,1)→Sigmoid
    N₁: Linear(3,32)→ReLU→Linear(32,16)→ReLU→Linear(16,1)→Sigmoid

训练超参（已确认）：
    Adam, lr=0.001, batch=64, ReduceLROnPlateau(patience=10, factor=0.5)
    max_epoch=300, 早停 patience=30, 验证比例 20%

使用方法：
    cd python/studies/mdm_delta

    # 训练 N₂ 模型（按 n 分别训练，默认）
    python train_model.py --model-type n2

    # 训练 N₁ 模型（公共模型）
    python train_model.py --model-type n1

    # 自定义超参数
    python train_model.py --model-type n2 --epochs 300 --lr 0.001 --batch-size 64

输出文件：
    models/mdm_delta/
    ├── n5_model.pth              # N₂: n=5 的模型权重
    ├── n7_model.pth              # N₂: n=7 的模型权重
    ├── n15_model.pth             # N₂: n=15 的模型权重
    ├── n5_metrics.json           # N₂: n=5 的训练指标
    ├── n7_metrics.json           # N₂: n=7 的训练指标
    ├── n15_metrics.json          # N₂: n=15 的训练指标
    ├── delta_from_params.pth     # N₁: 公共模型权重
    └── delta_from_params_metrics.json  # N₁: 训练指标

作者：Claude Code
日期：2026-04-26
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


# ============================================================
# 模型定义
# ============================================================

class DeltaMLP_N2(nn.Module):
    """路线 1 模型：样本 → 最优 δ
    Linear(n,128)→ReLU→BN→Linear(128,64)→ReLU→BN→Linear(64,1)→Sigmoid
    """

    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128),
            nn.ReLU(),
            nn.BatchNorm1d(128),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.BatchNorm1d(64),
            nn.Linear(64, 1),
            nn.Sigmoid()  # 输出 [0, 1]，后续缩放到 δ 范围
        )

    def forward(self, x):
        return self.net(x)


class DeltaMLP_N1(nn.Module):
    """路线 2 公共模型：(β,η,γ) 真值 → 最优 δ
    Linear(3,32)→ReLU→Linear(32,16)→ReLU→Linear(16,1)→Sigmoid
    """

    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3, 32),
            nn.ReLU(),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Linear(16, 1),
            nn.Sigmoid()  # 输出 [0, 1]，后续缩放到 δ 范围
        )

    def forward(self, x):
        return self.net(x)


# ============================================================
# 数据加载
# ============================================================

def load_training_data_n2(csv_path: Path):
    """加载 N₂ 训练数据 CSV，返回 (X, y, meta) numpy 数组
    CSV 格式: n,beta,eta,gamma,t1,...,tn,optimal_delta,best_mse
    X = t1, t2, ..., tn
    y = optimal_delta
    meta = (beta, eta, gamma, n)
    """
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append([float(v) if v != '' else np.nan for v in row])

    data = np.array(rows)
    # 列结构: [n, beta, eta, gamma, t1, t2, ..., tn, optimal_delta, best_mse]
    n = int(data[0, 0])
    X = data[:, 4:4+n]  # 样本数据 t1...tn
    y = data[:, -2]      # optimal_delta
    meta = data[:, :4]   # [n, beta, eta, gamma]

    return X, y, meta


def load_training_data_n1(csv_path: Path):
    """加载 N₁ 训练数据 CSV（全量合并），返回 (X, y) numpy 数组
    CSV 格式: n,beta,eta,gamma,t1,...,t_maxn,optimal_delta,best_mse
    X = (beta, eta, gamma)
    y = optimal_delta
    """
    rows = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            rows.append([float(v) if v != '' else np.nan for v in row])

    data = np.array(rows)
    # X = beta, eta, gamma (列 1,2,3)
    X = data[:, 1:4]
    # y = optimal_delta (倒数第二列)
    y = data[:, -2]

    return X, y


# ============================================================
# 数据预处理
# ============================================================

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


# ============================================================
# 训练
# ============================================================

def train_model(model, train_loader, val_loader, epochs, lr, device, patience=30):
    """训练模型，返回训练历史"""
    model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=lr)
    criterion = nn.MSELoss()
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
    }, pred_delta


def save_validation_predictions(X_val, y_val, pred_delta, meta_val, output_path):
    """保存验证集预测结果到 CSV"""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # 写入表头
        if meta_val is not None:
            writer.writerow(['n', 'beta', 'eta', 'gamma', 'true_delta', 'predicted_delta', 'error'])
            for i in range(len(y_val)):
                writer.writerow([
                    meta_val[i][0], meta_val[i][1], meta_val[i][2], meta_val[i][3],
                    round(y_val[i], 6), round(pred_delta[i], 6),
                    round(pred_delta[i] - y_val[i], 6)
                ])
        else:
            writer.writerow(['true_delta', 'predicted_delta', 'error'])
            for i in range(len(y_val)):
                writer.writerow([
                    round(y_val[i], 6), round(pred_delta[i], 6),
                    round(pred_delta[i] - y_val[i], 6)
                ])


# ============================================================
# 主流程
# ============================================================

def main():
    parser = argparse.ArgumentParser(description='MDM delta offset optimization - model training')
    parser.add_argument('--model-type', type=str, default='n2', choices=['n1', 'n2'],
                        help='model type: n2=route1(sample->delta), n1=route2(params->delta) (default: n2)')
    parser.add_argument('--data-dir', type=str, default=None,
                        help='训练数据目录 (默认: ./data)')
    parser.add_argument('--output-dir', type=str, default=None,
                        help='模型输出目录 (默认: ../../models/mdm_delta)')
    parser.add_argument('--epochs', type=int, default=300,
                        help='最大训练轮数 (默认: 300)')
    parser.add_argument('--lr', type=float, default=0.001,
                        help='学习率 (默认: 0.001)')
    parser.add_argument('--batch-size', type=int, default=64,
                        help='批次大小 (默认: 64)')
    parser.add_argument('--delta-min', type=float, default=0.001,
                        help='δ 最小值 (默认: 0.001)')
    parser.add_argument('--delta-max', type=float, default=1.00,
                        help='δ 最大值 (默认: 1.00)')
    parser.add_argument('--patience', type=int, default=30,
                        help='早停耐心 (默认: 30)')
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
    print(f"Model type: {args.model_type.upper()}")

    all_metrics = {}

    if args.model_type == 'n2':
        # ============================================================
        # N₂ 模型训练（路线 1：样本 → δ）
        # ============================================================
        csv_files = sorted(data_dir.glob('training_data_n*.csv'))
        # 排除 training_data_all.csv
        csv_files = [f for f in csv_files if 'all' not in f.stem]

        if not csv_files:
            print(f"错误: 在 {data_dir} 中未找到 training_data_n*.csv 文件")
            sys.exit(1)

        print(f"找到 {len(csv_files)} 个训练数据文件")
        print("=" * 60)

        for csv_path in csv_files:
            # 提取样本量 n
            n_str = csv_path.stem.replace('training_data_n', '')
            n = int(n_str)
            print(f"\n--- 训练 N2 模型 (n={n}) ---")

            # 加载数据
            X, y, meta = load_training_data_n2(csv_path)
            print(f"  数据量: {len(X)} 条，输入维度: {X.shape[1]}")

            # 划分
            X_train, y_train, X_val, y_val = split_data(X, y, val_ratio=args.val_ratio)
            # 保持 meta 同步划分
            np.random.seed(42)
            indices = np.random.permutation(len(X))
            val_size = int(len(X) * args.val_ratio)
            meta_val = meta[indices[:val_size]]
            print(f"  训练集: {len(X_train)}，验证集: {len(X_val)}")

            # 标准化
            X_train_norm, y_train_norm, X_val_norm, y_val_norm, scaler_params = normalize_data(
                X_train, y_train, X_val, y_val, args.delta_min, args.delta_max
            )
            print(f"  X 均值范围: [{np.min(scaler_params['x_mean']):.1f}, {np.max(scaler_params['x_mean']):.1f}]")
            print(f"  X 标准差范围: [{np.min(scaler_params['x_std']):.1f}, {np.max(scaler_params['x_std']):.1f}]")
            print(f"  y (delta) range: [{args.delta_min}, {args.delta_max}] -> [0, 1]")

            # 构建 DataLoader
            train_dataset = TensorDataset(
                torch.FloatTensor(X_train_norm),
                torch.FloatTensor(y_train_norm)
            )
            val_dataset = TensorDataset(
                torch.FloatTensor(X_val_norm),
                torch.FloatTensor(y_val_norm)
            )
            train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, drop_last=True)
            val_loader = DataLoader(val_dataset, batch_size=args.batch_size)

            # 构建模型
            model = DeltaMLP_N2(input_dim=n)
            param_count = sum(p.numel() for p in model.parameters())
            print(f"  模型参数量: {param_count:,}")

            # 训练
            model, history, best_epoch, best_val_loss = train_model(
                model, train_loader, val_loader,
                epochs=args.epochs, lr=args.lr, device=device,
                patience=args.patience
            )

            # 评估
            metrics, pred_delta = evaluate_model(
                model, X_val_norm, y_val, args.delta_min, args.delta_max, device
            )
            metrics['best_epoch'] = best_epoch + 1
            metrics['best_val_loss'] = float(best_val_loss)
            metrics['input_dim'] = n
            metrics['train_samples'] = len(X_train)
            metrics['architecture'] = f'Linear({n},128)->ReLU->BN->Linear(128,64)->ReLU->BN->Linear(64,1)->Sigmoid'

            print(f"  最佳 epoch: {best_epoch+1}")
            print(f"  验证 MSE: {metrics['mse']:.6f}")
            print(f"  验证 MAE: {metrics['mae']:.6f}")
            print(f"  验证 RMSE: {metrics['rmse']:.6f}")
            print(f"  pred delta range: [{metrics['pred_min']:.4f}, {metrics['pred_max']:.4f}]")
            print(f"  true delta range: [{metrics['true_mean']:.4f} +/- {metrics['true_std']:.4f}]")

            # 保存模型
            model_path = output_dir / f'n{n}_model.pth'
            torch.save({
                'model_state_dict': model.state_dict(),
                'input_dim': n,
                'model_type': 'n2',
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
                    'model_type': 'n2',
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
                        'delta_min': args.delta_min,
                        'delta_max': args.delta_max,
                        'patience': args.patience,
                        'val_ratio': args.val_ratio,
                    },
                    'trained_at': datetime.now().isoformat(timespec='seconds'),
                }, f, indent=2, ensure_ascii=False)

            # 保存验证集预测
            val_pred_path = data_dir / f'validation_predictions_n{n}.csv'
            save_validation_predictions(X_val, y_val, pred_delta, meta_val, val_pred_path)
            print(f"  验证预测已保存: {val_pred_path}")

            all_metrics[f'n{n}'] = metrics

    else:
        # ============================================================
        # N₁ 模型训练（路线 2：真值 → δ）
        # ============================================================
        csv_path = data_dir / 'training_data_all.csv'
        if not csv_path.exists():
            print(f"错误: 未找到 {csv_path}")
            print("请先运行 generate_training_data.py 生成训练数据")
            sys.exit(1)

        print(f"\n--- 训练 N1 模型 (公共模型) ---")

        # 加载数据
        X, y = load_training_data_n1(csv_path)
        print(f"  Data: {len(X)} rows, input dim: {X.shape[1]} (beta, eta, gamma)")

        # 划分
        X_train, y_train, X_val, y_val = split_data(X, y, val_ratio=args.val_ratio)
        print(f"  训练集: {len(X_train)}，验证集: {len(X_val)}")

        # 标准化
        X_train_norm, y_train_norm, X_val_norm, y_val_norm, scaler_params = normalize_data(
            X_train, y_train, X_val, y_val, args.delta_min, args.delta_max
        )
        print(f"  X 均值: {scaler_params['x_mean']}")
        print(f"  X 标准差: {scaler_params['x_std']}")
        print(f"  y (delta) range: [{args.delta_min}, {args.delta_max}] -> [0, 1]")

        # 构建 DataLoader
        train_dataset = TensorDataset(
            torch.FloatTensor(X_train_norm),
            torch.FloatTensor(y_train_norm)
        )
        val_dataset = TensorDataset(
            torch.FloatTensor(X_val_norm),
            torch.FloatTensor(y_val_norm)
        )
        train_loader = DataLoader(train_dataset, batch_size=args.batch_size, shuffle=True, drop_last=True)
        val_loader = DataLoader(val_dataset, batch_size=args.batch_size)

        # 构建模型
        model = DeltaMLP_N1()
        param_count = sum(p.numel() for p in model.parameters())
        print(f"  模型参数量: {param_count:,}")

        # 训练
        model, history, best_epoch, best_val_loss = train_model(
            model, train_loader, val_loader,
            epochs=args.epochs, lr=args.lr, device=device,
            patience=args.patience
        )

        # 评估
        metrics, pred_delta = evaluate_model(
            model, X_val_norm, y_val, args.delta_min, args.delta_max, device
        )
        metrics['best_epoch'] = best_epoch + 1
        metrics['best_val_loss'] = float(best_val_loss)
        metrics['input_dim'] = 3
        metrics['train_samples'] = len(X_train)
        metrics['architecture'] = 'Linear(3,32)->ReLU->Linear(32,16)->ReLU->Linear(16,1)->Sigmoid'

        print(f"  最佳 epoch: {best_epoch+1}")
        print(f"  验证 MSE: {metrics['mse']:.6f}")
        print(f"  验证 MAE: {metrics['mae']:.6f}")
        print(f"  验证 RMSE: {metrics['rmse']:.6f}")
        print(f"  pred delta range: [{metrics['pred_min']:.4f}, {metrics['pred_max']:.4f}]")
        print(f"  true delta range: [{metrics['true_mean']:.4f} +/- {metrics['true_std']:.4f}]")

        # 保存模型
        model_path = output_dir / 'delta_from_params.pth'
        torch.save({
            'model_state_dict': model.state_dict(),
            'model_type': 'n1',
            'delta_min': args.delta_min,
            'delta_max': args.delta_max,
            'scaler_params': scaler_params,
            'metrics': metrics,
        }, model_path)
        print(f"  模型已保存: {model_path}")

        # 保存指标
        metrics_path = output_dir / 'delta_from_params_metrics.json'
        with open(metrics_path, 'w', encoding='utf-8') as f:
            json.dump({
                'model_type': 'n1',
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
                    'delta_min': args.delta_min,
                    'delta_max': args.delta_max,
                    'patience': args.patience,
                    'val_ratio': args.val_ratio,
                },
                'trained_at': datetime.now().isoformat(timespec='seconds'),
            }, f, indent=2, ensure_ascii=False)

        all_metrics['n1'] = metrics

    # 总结
    print("\n" + "=" * 60)
    print("训练完成！")
    print(f"模型目录: {output_dir}")
    for key, m in all_metrics.items():
        print(f"  {key}: MSE={m['mse']:.6f}, MAE={m['mae']:.6f}, RMSE={m['rmse']:.6f}")
    print("=" * 60)


if __name__ == '__main__':
    main()
