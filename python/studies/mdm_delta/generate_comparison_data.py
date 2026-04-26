"""
MDM 偏移量 δ 优化 — 对比/验证数据生成脚本

用途：
    生成可视化所需的对比和验证 CSV 文件。
    需要先运行 generate_training_data.py 和 train_model.py。

使用方法：
    cd python/studies/mdm_delta
    python generate_comparison_data.py

输出文件（存放在 data/ 目录）：
    comparison_ai_vs_fixed.csv   — AI δ 和固定 δ 的参数估计误差对比
    comparison_sweep.csv          — 固定 δ sweep 的 MSE 曲线
    comparison_improvement.csv    — AI δ 相对固定 δ 的改善百分比
    comparison_routes.csv         — 路线 1 vs 路线 2 效果对比
    iteration_stats.csv           — 路线 2 批量测试收敛统计
    verification_cases.csv        — 已知参数验证案例
    boundary_tests.csv            — 边界条件测试

作者：Claude Code
日期：2026-04-26
"""

import sys
import os
import json
import csv
import numpy as np
from pathlib import Path
from itertools import product

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM

import torch
import torch.nn as nn


# ============================================================
# 模型定义（与 train_model.py 一致）
# ============================================================

class DeltaMLP_N2(nn.Module):
    def __init__(self, input_dim: int):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 128), nn.ReLU(), nn.BatchNorm1d(128),
            nn.Linear(128, 64), nn.ReLU(), nn.BatchNorm1d(64),
            nn.Linear(64, 1), nn.Sigmoid()
        )
    def forward(self, x):
        return self.net(x)

class DeltaMLP_N1(nn.Module):
    def __init__(self):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(3, 32), nn.ReLU(),
            nn.Linear(32, 16), nn.ReLU(),
            nn.Linear(16, 1), nn.Sigmoid()
        )
    def forward(self, x):
        return self.net(x)


# ============================================================
# 工具函数
# ============================================================

def generate_weibull_sample(beta, eta, gamma, n, seed):
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)

def run_mdm(sample, delta, gamma_steps=60):
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps)
        if result[4] == "no_intersection":
            return None
        est_beta, est_eta, est_gamma = result[0], result[1], result[2]
        if est_beta <= 0 or est_beta > 50 or est_eta <= 0 or est_eta > 1e6:
            return None
        return (est_beta, est_eta, est_gamma)
    except:
        return None

def compute_relative_mse(est, true_beta, true_eta, true_gamma):
    if est is None:
        return float('inf')
    return ((est[0]-true_beta)/true_beta)**2 + ((est[1]-true_eta)/true_eta)**2 + ((est[2]-true_gamma)/true_gamma)**2

def load_model_n2(n, models_dir):
    path = models_dir / f'n{n}_model.pth'
    if not path.exists():
        return None
    ckpt = torch.load(path, map_location='cpu', weights_only=False)
    model = DeltaMLP_N2(input_dim=ckpt['input_dim'])
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval()
    return model, ckpt

def load_model_n1(models_dir):
    path = models_dir / 'delta_from_params.pth'
    if not path.exists():
        return None
    ckpt = torch.load(path, map_location='cpu', weights_only=False)
    model = DeltaMLP_N1()
    model.load_state_dict(ckpt['model_state_dict'])
    model.eval()
    return model, ckpt

def predict_delta_n2(model, ckpt, sample):
    sample_arr = np.array(sample).reshape(1, -1)
    sp = ckpt['scaler_params']
    sample_arr = (sample_arr - np.array(sp['x_mean'])) / np.array(sp['x_std'])
    with torch.no_grad():
        pred = model(torch.FloatTensor(sample_arr)).squeeze().item()
    delta_min, delta_max = ckpt['delta_min'], ckpt['delta_max']
    return pred * (delta_max - delta_min) + delta_min

def predict_delta_n1(model, ckpt, beta, eta, gamma):
    params = np.array([[beta, eta, gamma]])
    sp = ckpt['scaler_params']
    params = (params - np.array(sp['x_mean'])) / np.array(sp['x_std'])
    with torch.no_grad():
        pred = model(torch.FloatTensor(params)).squeeze().item()
    delta_min, delta_max = ckpt['delta_min'], ckpt['delta_max']
    return pred * (delta_max - delta_min) + delta_min


# ============================================================
# 主流程
# ============================================================

def main():
    data_dir = Path(__file__).parent / 'data'
    models_dir = PROJECT_ROOT / 'python' / 'models' / 'mdm_delta'

    # 参数空间
    betas = [2.0]
    etas = [100.0, 1000.0, 5000.0]
    gamma = 1000.0
    sample_sizes = [5, 7, 10, 15, 20]
    fixed_deltas = [0.01, 0.05, 0.10, 0.20, 0.50, 1.00]
    delta_sweep = np.arange(0.001, 1.01, 0.05)

    # 加载模型
    n2_models = {}
    for n in sample_sizes:
        result = load_model_n2(n, models_dir)
        if result:
            n2_models[n] = result
    n1_result = load_model_n1(models_dir)

    if not n2_models:
        print("Error: N2 models not found, run train_model.py --model-type n2 first")
        sys.exit(1)

    print(f"Loaded N2 models: {list(n2_models.keys())}")
    print(f"N1 model: {'loaded' if n1_result else 'not found'}")

    # 生成测试样本
    print("\n生成测试样本...")
    test_cases = []
    for beta_val, eta_val, n in product(betas, etas, sample_sizes):
        for sim_id in range(1, 51):  # 50 个测试样本/组合
            seed = sim_id + int(beta_val * 1000) + int(eta_val) + n * 100 + 99999
            sample = generate_weibull_sample(beta_val, eta_val, gamma, n, seed)
            test_cases.append({
                'beta': beta_val, 'eta': eta_val, 'gamma': gamma,
                'n': n, 'sample': sample, 'seed': seed
            })
    print(f"  测试样本数: {len(test_cases)}")

    # ============================================================
    # 1. comparison_sweep.csv — δ sweep MSE 曲线
    # ============================================================
    print("\n生成 comparison_sweep.csv...")
    sweep_rows = []
    for beta_val in betas:
        for n in sample_sizes:
            # 用 20 个样本做 sweep
            cases = [c for c in test_cases if c['beta'] == beta_val and c['n'] == n][:20]
            for delta in delta_sweep:
                mses = []
                for case in cases:
                    est = run_mdm(case['sample'], delta)
                    mse = compute_relative_mse(est, beta_val, case['eta'], gamma)
                    if mse < float('inf'):
                        mses.append(mse)
                if mses:
                    sweep_rows.append({
                        'beta': beta_val, 'n': n, 'delta': round(delta, 4),
                        'mean_mse': round(np.mean(mses), 2),
                        'std_mse': round(np.std(mses), 2),
                        'n_valid': len(mses),
                    })

    with open(data_dir / 'comparison_sweep.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['beta', 'n', 'delta', 'mean_mse', 'std_mse', 'n_valid'])
        writer.writeheader()
        writer.writerows(sweep_rows)
    print(f"  已写入 {len(sweep_rows)} 条记录")

    # ============================================================
    # 2. comparison_ai_vs_fixed.csv + comparison_improvement.csv
    # ============================================================
    print("\n生成 comparison_ai_vs_fixed.csv 和 comparison_improvement.csv...")
    comparison_rows = []
    improvement_rows = []

    for case in test_cases:
        n = case['n']
        if n not in n2_models:
            continue

        model, ckpt = n2_models[n]
        ai_delta = predict_delta_n2(model, ckpt, case['sample'])
        ai_est = run_mdm(case['sample'], ai_delta)
        ai_mse = compute_relative_mse(ai_est, case['beta'], case['eta'], gamma)

        row = {
            'beta': case['beta'], 'eta': case['eta'], 'n': n,
            'ai_delta': round(ai_delta, 4), 'ai_mse': round(ai_mse, 2),
        }

        for fd in fixed_deltas:
            est = run_mdm(case['sample'], fd)
            mse = compute_relative_mse(est, case['beta'], case['eta'], gamma)
            row[f'fixed_{fd}_mse'] = round(mse, 2) if mse < float('inf') else None

        comparison_rows.append(row)

        # 改善百分比
        imp_row = {'beta': case['beta'], 'eta': case['eta'], 'n': n}
        for fd in fixed_deltas:
            fixed_mse = row.get(f'fixed_{fd}_mse')
            if fixed_mse and fixed_mse > 0 and ai_mse < float('inf'):
                improvement = (fixed_mse - ai_mse) / fixed_mse * 100
                imp_row[f'vs_{fd}'] = round(improvement, 1)
            else:
                imp_row[f'vs_{fd}'] = None
        improvement_rows.append(imp_row)

    if comparison_rows:
        with open(data_dir / 'comparison_ai_vs_fixed.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(comparison_rows[0].keys()))
            writer.writeheader()
            writer.writerows(comparison_rows)
        print(f"  comparison_ai_vs_fixed: {len(comparison_rows)} 条")

    if improvement_rows:
        with open(data_dir / 'comparison_improvement.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=list(improvement_rows[0].keys()))
            writer.writeheader()
            writer.writerows(improvement_rows)
        print(f"  comparison_improvement: {len(improvement_rows)} 条")

    # ============================================================
    # 3. verification_cases.csv — 已知参数验证
    # ============================================================
    print("\n生成 verification_cases.csv...")
    verification_rows = []
    for beta_val, eta_val, n in product(betas, etas, sample_sizes):
        case = {'beta': beta_val, 'eta': eta_val, 'gamma': gamma, 'n': n}
        seed = 42 + int(beta_val * 1000) + int(eta_val) + n * 100
        sample = generate_weibull_sample(beta_val, eta_val, gamma, n, seed)

        if n in n2_models:
            model, ckpt = n2_models[n]
            ai_delta = predict_delta_n2(model, ckpt, sample)
            ai_est = run_mdm(sample, ai_delta)

            verification_rows.append({
                'beta': beta_val, 'eta': eta_val, 'gamma': gamma, 'n': n,
                'ai_delta': round(ai_delta, 4),
                'est_beta': round(ai_est[0], 4) if ai_est else None,
                'est_eta': round(ai_est[1], 4) if ai_est else None,
                'est_gamma': round(ai_est[2], 4) if ai_est else None,
                'beta_error': round(ai_est[0] - beta_val, 4) if ai_est else None,
                'eta_error': round(ai_est[1] - eta_val, 4) if ai_est else None,
                'gamma_error': round(ai_est[2] - gamma, 4) if ai_est else None,
            })

    with open(data_dir / 'verification_cases.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(verification_rows[0].keys()))
        writer.writeheader()
        writer.writerows(verification_rows)
    print(f"  verification_cases: {len(verification_rows)} 条")

    # ============================================================
    # 4. iteration_stats.csv — 路线 2 收敛统计
    # ============================================================
    if n1_result:
        print("\n生成 iteration_stats.csv...")
        n1_model, n1_ckpt = n1_result
        iter_rows = []

        for case in test_cases[:200]:  # 取前 200 个测试
            n = case['n']
            delta = 0.5
            converged = False
            steps = 0

            for step in range(10):
                est = run_mdm(case['sample'], delta)
                if est is None:
                    break
                delta_new = predict_delta_n1(n1_model, n1_ckpt, est[0], est[1], est[2])
                steps = step + 1
                if abs(delta_new - delta) < 0.001:
                    converged = True
                    delta = delta_new
                    break
                delta = delta_new

            iter_rows.append({
                'beta': case['beta'], 'eta': case['eta'], 'n': case['n'],
                'final_delta': round(delta, 6),
                'steps': steps,
                'converged': converged,
            })

        with open(data_dir / 'iteration_stats.csv', 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=['beta', 'eta', 'n', 'final_delta', 'steps', 'converged'])
            writer.writeheader()
            writer.writerows(iter_rows)
        print(f"  iteration_stats: {len(iter_rows)} 条")

    # ============================================================
    # 5. boundary_tests.csv — 边界条件测试
    # ============================================================
    print("\n生成 boundary_tests.csv...")
    boundary_cases = [
        {'beta': 2.0, 'eta': 50, 'gamma': 1000, 'n': 5, 'label': 'beta=2,小η'},
        {'beta': 2.0, 'eta': 10000, 'gamma': 1000, 'n': 5, 'label': 'beta=2,大η'},
        {'beta': 2.0, 'eta': 100, 'gamma': 1000, 'n': 3, 'label': '极小样本'},
        {'beta': 2.0, 'eta': 5000, 'gamma': 1000, 'n': 30, 'label': '大样本'},
    ]

    boundary_rows = []
    for bc in boundary_cases:
        n = bc['n']
        if n not in n2_models:
            continue
        model, ckpt = n2_models[n]
        seed = 12345
        sample = generate_weibull_sample(bc['beta'], bc['eta'], bc['gamma'], n, seed)
        ai_delta = predict_delta_n2(model, ckpt, sample)
        ai_est = run_mdm(sample, ai_delta)

        boundary_rows.append({
            'label': bc['label'],
            'beta': bc['beta'], 'eta': bc['eta'], 'gamma': bc['gamma'], 'n': n,
            'ai_delta': round(ai_delta, 4),
            'est_beta': round(ai_est[0], 4) if ai_est else None,
            'est_eta': round(ai_est[1], 4) if ai_est else None,
            'est_gamma': round(ai_est[2], 4) if ai_est else None,
            'status': 'ok' if ai_est else 'failed',
        })

    with open(data_dir / 'boundary_tests.csv', 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(boundary_rows[0].keys()) if boundary_rows else ['label'])
        writer.writeheader()
        writer.writerows(boundary_rows)
    print(f"  boundary_tests: {len(boundary_rows)} 条")

    print("\n对比/验证数据生成完成！")


if __name__ == '__main__':
    main()
