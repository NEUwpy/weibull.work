"""
MSE-δ 曲线可视化

对选定的样本，遍历 δ 网格，记录每个 δ 的 MSE，画出 MSE(δ) 曲线。
用途：验证 MSE(δ) 是否单峰、光滑，指导搜索策略优化。

使用方法：
    cd python/studies/mdm_delta
    python plot_mse_delta_curve.py
    python plot_mse_delta_curve.py --samples 10 --delta-step 0.01
"""

import sys
import os
import csv
import argparse
import numpy as np
from pathlib import Path
from itertools import product

# Project root
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM


def generate_weibull_sample(beta, eta, gamma, n, seed):
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 1, n)
    t = gamma + eta * (-np.log(1 - u)) ** (1.0 / beta)
    return np.sort(t)


def run_mdm_with_delta(sample, delta, gamma_steps=60):
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps, rank_method='bernard')
        if result[4] == "no_intersection":
            return None
        return (result[0], result[1], result[2])
    except Exception:
        return None


def compute_relative_mse(est_beta, est_eta, est_gamma, true_beta, true_eta, true_gamma):
    return ((est_beta - true_beta) / true_beta) ** 2 + \
           ((est_eta - true_eta) / true_eta) ** 2 + \
           ((est_gamma - true_gamma) / true_gamma) ** 2


def evaluate_mse_curve(sample, true_beta, true_eta, true_gamma, delta_values, gamma_steps=60):
    """对一个样本，计算所有 δ 值的 MSE"""
    results = []
    for delta in delta_values:
        est = run_mdm_with_delta(sample, delta, gamma_steps)
        if est is None:
            results.append({'delta': delta, 'mse': None, 'beta': None, 'eta': None, 'gamma': None})
        else:
            mse = compute_relative_mse(*est, true_beta, true_eta, true_gamma)
            results.append({
                'delta': delta,
                'mse': mse,
                'beta': est[0],
                'eta': est[1],
                'gamma': est[2],
            })
    return results


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--samples', type=int, default=6, help='Number of samples to plot')
    parser.add_argument('--delta-step', type=float, default=0.005, help='Delta grid step')
    parser.add_argument('--gamma-steps', type=int, default=60, help='MDM gamma steps')
    parser.add_argument('--output-dir', type=str, default='data/mse_curves', help='Output directory')
    args = parser.parse_args()

    output_dir = Path(__file__).parent / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    delta_values = np.arange(0.005, 1.0, args.delta_step)
    print(f"Delta grid: {len(delta_values)} points, step={args.delta_step}")

    # 选取有代表性的参数组合
    param_sets = [
        # (beta, eta, gamma, n, label)
        (1.0, 100, 1000, 5, 'b1_e100_n5'),
        (1.0, 1000, 1000, 5, 'b1_e1000_n5'),
        (1.0, 5000, 1000, 5, 'b1_e5000_n5'),
        (2.0, 100, 1000, 5, 'b2_e100_n5'),
        (2.0, 1000, 1000, 5, 'b2_e1000_n5'),
        (2.0, 5000, 1000, 5, 'b2_e5000_n5'),
        (5.0, 100, 1000, 5, 'b5_e100_n5'),
        (5.0, 1000, 1000, 5, 'b5_e1000_n5'),
        (5.0, 5000, 1000, 5, 'b5_e5000_n5'),
        (2.0, 1000, 1000, 10, 'b2_e1000_n10'),
        (2.0, 1000, 1000, 20, 'b2_e1000_n20'),
        (1.0, 1000, 1000, 20, 'b1_e1000_n20'),
        (5.0, 1000, 1000, 20, 'b5_e1000_n20'),
    ]

    # 只取前 N 个
    param_sets = param_sets[:args.samples]

    all_curves = []

    for beta, eta, gamma, n, label in param_sets:
        print(f"\n--- {label} (beta={beta}, eta={eta}, gamma={gamma}, n={n}) ---")
        seed = 42 + int(beta * 1000) + int(eta) + n * 100
        sample = generate_weibull_sample(beta, eta, gamma, n, seed)

        curve = evaluate_mse_curve(sample, beta, eta, gamma, delta_values, args.gamma_steps)

        # 统计
        valid_mse = [r['mse'] for r in curve if r['mse'] is not None]
        if valid_mse:
            best_idx = np.argmin(valid_mse)
            best_delta = delta_values[best_idx]
            best_mse = valid_mse[best_idx]
            no_solution_count = sum(1 for r in curve if r['mse'] is None)
            print(f"  Best delta={best_delta:.3f}, MSE={best_mse:.6f}")
            print(f"  No solution: {no_solution_count}/{len(delta_values)}")

            # 检查是否单峰
            # 简单检查：从最小值往两边看，MSE 是否单调递增
            is_unimodal = check_unimodal(valid_mse)
            print(f"  Unimodal: {is_unimodal}")
        else:
            best_delta = None
            best_mse = None
            print("  All deltas failed!")

        # 保存详细数据
        csv_path = output_dir / f'curve_{label}.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['delta', 'mse', 'est_beta', 'est_eta', 'est_gamma'])
            for i, r in enumerate(curve):
                writer.writerow([delta_values[i], r['mse'], r['beta'], r['eta'], r['gamma']])
        print(f"  Saved: {csv_path}")

        all_curves.append({
            'label': label,
            'beta': beta, 'eta': eta, 'gamma': gamma, 'n': n,
            'delta_values': delta_values.copy(),
            'curve': curve,
            'best_delta': best_delta,
            'best_mse': best_mse,
        })

    # 汇总统计
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for c in all_curves:
        valid = [r['mse'] for r in c['curve'] if r['mse'] is not None]
        if valid:
            print(f"{c['label']:20s}  best_delta={c['best_delta']:.3f}  MSE={c['best_mse']:.6f}  "
                  f"valid={len(valid)}/{len(delta_values)}")

    # 保存汇总
    summary_path = output_dir / 'summary.csv'
    with open(summary_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['label', 'beta', 'eta', 'gamma', 'n', 'best_delta', 'best_mse', 'valid_count'])
        for c in all_curves:
            valid = [r['mse'] for r in c['curve'] if r['mse'] is not None]
            writer.writerow([c['label'], c['beta'], c['eta'], c['gamma'], c['n'],
                           c['best_delta'], c['best_mse'], len(valid)])
    print(f"\nSummary saved: {summary_path}")


def check_unimodal(mse_values):
    """简单检查 MSE 序列是否单峰（先降后升）"""
    if len(mse_values) < 3:
        return True

    # 找到最小值位置
    min_idx = np.argmin(mse_values)

    # 检查最小值左边是否单调递减
    for i in range(min_idx):
        if mse_values[i] < mse_values[i + 1]:
            # 左边有上升，可能不是单峰
            # 但如果上升幅度很小，可能是噪声
            pass

    # 检查最小值右边是否单调递增
    for i in range(min_idx, len(mse_values) - 1):
        if mse_values[i] > mse_values[i + 1]:
            # 右边有下降，不是单峰
            return False

    return True


if __name__ == '__main__':
    main()
