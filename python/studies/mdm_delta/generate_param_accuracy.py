"""
参数精度三-way 对比数据生成

对同一批验证样本，分别用 δ=0.5、δ=AI 预测值、δ=最优值 运行 MDM，
记录 (β̂, η̂, γ̂) 用于 M1-R1 ParamAccuracyTab 的对比分析。

Usage:
    cd python/studies/mdm_delta
    python generate_param_accuracy.py

Output:
    data/param_accuracy_comparison.csv — 三-way 对比数据
"""

import sys
import csv
import numpy as np
from pathlib import Path
from itertools import product

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM

import torch
import torch.nn as nn


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


def generate_weibull_sample(beta, eta, gamma, n, seed):
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    return np.sort(gamma + eta * (-np.log(1 - u)) ** (1 / beta))


def run_mdm(sample, delta, gamma_steps=60):
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps)
        if result[4] == "no_intersection":
            return None
        b, e, g = result[0], result[1], result[2]
        if b <= 0 or b > 50 or e <= 0 or e > 1e6:
            return None
        return (b, e, g)
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


def predict_delta_n2(model, ckpt, sample):
    sample_arr = np.array(sample).reshape(1, -1)
    sp = ckpt['scaler_params']
    sample_arr = (sample_arr - np.array(sp['x_mean'])) / np.array(sp['x_std'])
    with torch.no_grad():
        pred = model(torch.FloatTensor(sample_arr)).squeeze().item()
    delta_min, delta_max = ckpt['delta_min'], ckpt['delta_max']
    return pred * (delta_max - delta_min) + delta_min


def find_optimal_delta(sample, true_beta, true_eta, true_gamma,
                       delta_range=np.arange(0.01, 0.51, 0.01)):
    """Grid search for optimal delta that minimizes relative MSE."""
    best_delta = None
    best_mse = float('inf')
    for delta in delta_range:
        est = run_mdm(sample, delta)
        if est is None:
            continue
        mse = compute_relative_mse(est, true_beta, true_eta, true_gamma)
        if mse < best_mse:
            best_mse = mse
            best_delta = delta
    return best_delta, best_mse


def main():
    data_dir = Path(__file__).parent / 'data'
    models_dir = PROJECT_ROOT / 'python' / 'models' / 'mdm_delta'

    betas = [1.0, 2.0, 5.0]
    etas = [100.0, 1000.0, 5000.0]
    gamma = 1000.0
    sample_sizes = [5, 7, 10, 15, 20]
    fixed_delta = 0.5

    # Load M1-R1 models
    n2_models = {}
    for n in sample_sizes:
        result = load_model_n2(n, models_dir)
        if result:
            n2_models[n] = result

    if not n2_models:
        print("Error: M1-R1 models not found")
        sys.exit(1)

    print(f"Loaded M1-R1 models: {list(n2_models.keys())}")
    print(f"Generating three-way comparison data...")

    rows = []
    total = len(betas) * len(etas) * len(sample_sizes)
    done = 0

    for beta_val, eta_val, n in product(betas, etas, sample_sizes):
        done += 1
        seed = 42 + int(beta_val * 1000) + int(eta_val) + n * 100
        sample = generate_weibull_sample(beta_val, eta_val, gamma, n, seed)

        row = {
            'beta': beta_val, 'eta': eta_val, 'gamma': gamma, 'n': n,
        }

        # δ = 0.5 (fixed)
        est_fixed = run_mdm(sample, fixed_delta)
        row['fixed_delta'] = fixed_delta
        if est_fixed:
            row['fixed_est_beta'] = round(est_fixed[0], 4)
            row['fixed_est_eta'] = round(est_fixed[1], 2)
            row['fixed_est_gamma'] = round(est_fixed[2], 2)
            row['fixed_mse'] = round(compute_relative_mse(est_fixed, beta_val, eta_val, gamma), 6)
        else:
            row['fixed_est_beta'] = None
            row['fixed_est_eta'] = None
            row['fixed_est_gamma'] = None
            row['fixed_mse'] = None

        # δ = AI predicted (M1-R1)
        if n in n2_models:
            model, ckpt = n2_models[n]
            ai_delta = predict_delta_n2(model, ckpt, sample)
            est_ai = run_mdm(sample, ai_delta)
            row['ai_delta'] = round(ai_delta, 4)
            if est_ai:
                row['ai_est_beta'] = round(est_ai[0], 4)
                row['ai_est_eta'] = round(est_ai[1], 2)
                row['ai_est_gamma'] = round(est_ai[2], 2)
                row['ai_mse'] = round(compute_relative_mse(est_ai, beta_val, eta_val, gamma), 6)
            else:
                row['ai_est_beta'] = None
                row['ai_est_eta'] = None
                row['ai_est_gamma'] = None
                row['ai_mse'] = None
        else:
            row['ai_delta'] = None
            row['ai_est_beta'] = None
            row['ai_est_eta'] = None
            row['ai_est_gamma'] = None
            row['ai_mse'] = None

        # δ = optimal (grid search)
        opt_delta, opt_mse = find_optimal_delta(sample, beta_val, eta_val, gamma)
        est_opt = run_mdm(sample, opt_delta) if opt_delta else None
        row['optimal_delta'] = round(opt_delta, 4) if opt_delta else None
        if est_opt:
            row['opt_est_beta'] = round(est_opt[0], 4)
            row['opt_est_eta'] = round(est_opt[1], 2)
            row['opt_est_gamma'] = round(est_opt[2], 2)
            row['optimal_mse'] = round(opt_mse, 6)
        else:
            row['opt_est_beta'] = None
            row['opt_est_eta'] = None
            row['opt_est_gamma'] = None
            row['optimal_mse'] = None

        rows.append(row)
        print(f"  [{done}/{total}] β={beta_val}, η={eta_val}, n={n}: "
              f"fixed={row.get('fixed_mse', 'N/A')}, ai={row.get('ai_mse', 'N/A')}, opt={row.get('optimal_mse', 'N/A')}")

    # Write CSV
    out_path = data_dir / 'param_accuracy_comparison.csv'
    fieldnames = list(rows[0].keys())
    with open(out_path, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"\nOutput: {out_path} ({len(rows)} records)")


if __name__ == '__main__':
    main()
