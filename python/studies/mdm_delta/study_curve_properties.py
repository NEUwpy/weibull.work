"""
MSE-δ 曲线性质研究

深入研究 MDM 方法中 MSE(δ) 曲线的数学性质：
1. 曲线形状（单调性、极值点、凸性）
2. MDM 失败条件
3. 最优 δ 与搜索策略

使用方法：
    cd python/studies/mdm_delta
    python study_curve_properties.py
    python study_curve_properties.py --delta-step 0.001 --seeds 10
"""

import sys
import os
import csv
import json
import argparse
import numpy as np
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM


def generate_weibull_sample(beta, eta, gamma, n, seed):
    rng = np.random.default_rng(seed)
    u = rng.uniform(0, 1, n)
    t = gamma + eta * (-np.log(1 - u)) ** (1.0 / beta)
    return np.sort(t)


def run_mdm_with_delta(sample, delta, gamma_steps=60):
    """运行 MDM，返回 (beta, eta, gamma) 或 None"""
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps, rank_method='bernard')
        if result[4] == "no_intersection":
            return None, "no_intersection"
        return (result[0], result[1], result[2]), None
    except Exception as e:
        return None, str(e)


def compute_relative_mse(est, true_beta, true_eta, true_gamma):
    return ((est[0] - true_beta) / true_beta) ** 2 + \
           ((est[1] - true_eta) / true_eta) ** 2 + \
           ((est[2] - true_gamma) / true_gamma) ** 2


def compute_mse_components(est, true_beta, true_eta, true_gamma):
    return {
        'mse_beta': ((est[0] - true_beta) / true_beta) ** 2,
        'mse_eta': ((est[1] - true_eta) / true_eta) ** 2,
        'mse_gamma': ((est[2] - true_gamma) / true_gamma) ** 2,
    }


def scan_delta_curve(sample, true_beta, true_eta, true_gamma,
                     delta_values, gamma_steps=60):
    """精细扫描 δ，返回完整曲线数据"""
    results = []
    for delta in delta_values:
        est, failure_reason = run_mdm_with_delta(sample, delta, gamma_steps)
        if est is None:
            results.append({
                'delta': float(delta),
                'mse': None, 'mse_beta': None, 'mse_eta': None, 'mse_gamma': None,
                'est_beta': None, 'est_eta': None, 'est_gamma': None,
                'failure': failure_reason,
            })
        else:
            mse = compute_relative_mse(est, true_beta, true_eta, true_gamma)
            components = compute_mse_components(est, true_beta, true_eta, true_gamma)
            results.append({
                'delta': float(delta),
                'mse': float(mse),
                'mse_beta': float(components['mse_beta']),
                'mse_eta': float(components['mse_eta']),
                'mse_gamma': float(components['mse_gamma']),
                'est_beta': float(est[0]),
                'est_eta': float(est[1]),
                'est_gamma': float(est[2]),
                'failure': None,
            })
    return results


def analyze_curve(results):
    """分析曲线性质"""
    valid = [r for r in results if r['mse'] is not None]
    failed = [r for r in results if r['mse'] is None]

    if not valid:
        return {'status': 'all_failed'}

    mse_values = [r['mse'] for r in valid]
    delta_values = [r['delta'] for r in valid]

    min_idx = int(np.argmin(mse_values))
    best_delta = delta_values[min_idx]
    best_mse = mse_values[min_idx]

    # 检查单调性
    # 从最小值往左：是否单调递减
    left_of_min = mse_values[:min_idx + 1]
    left_monotone_decreasing = all(left_of_min[i] >= left_of_min[i+1]
                                    for i in range(len(left_of_min) - 1))

    # 从最小值往右：是否单调递增
    right_of_min = mse_values[min_idx:]
    right_monotone_increasing = all(right_of_min[i] <= right_of_min[i+1]
                                     for i in range(len(right_of_min) - 1))

    is_unimodal = left_monotone_decreasing and right_monotone_increasing

    # 检查是否在左边界最优（最优 δ 在搜索起点）
    at_left_boundary = (min_idx == 0)

    # 检查是否在右边界最优（最优 δ 在搜索终点，可能还没到真正最优）
    at_right_boundary = (min_idx == len(mse_values) - 1)

    # 失败边界
    failure_delta = None
    if failed:
        failure_delta = min(r['delta'] for r in failed)

    # 曲线在极值点附近的二阶导数（凸性）
    curvature = None
    if 1 <= min_idx <= len(mse_values) - 2:
        h = delta_values[min_idx] - delta_values[min_idx - 1]
        if h > 0:
            d2 = (mse_values[min_idx + 1] - 2 * mse_values[min_idx] + mse_values[min_idx - 1]) / (h ** 2)
            curvature = float(d2)

    # MSE 的下降速度（从起点到最优点）
    descent_rate = None
    if min_idx > 0:
        delta_span = delta_values[min_idx] - delta_values[0]
        mse_drop = mse_values[0] - best_mse
        if delta_span > 0:
            descent_rate = mse_drop / delta_span

    return {
        'status': 'ok',
        'best_delta': float(best_delta),
        'best_mse': float(best_mse),
        'min_idx': min_idx,
        'valid_count': len(valid),
        'failed_count': len(failed),
        'failure_delta': failure_delta,
        'is_unimodal': is_unimodal,
        'at_left_boundary': at_left_boundary,
        'at_right_boundary': at_right_boundary,
        'curvature_at_min': curvature,
        'descent_rate': descent_rate,
        'mse_at_left': float(mse_values[0]) if mse_values else None,
        'mse_at_right': float(mse_values[-1]) if mse_values else None,
        'delta_range': (float(delta_values[0]), float(delta_values[-1])),
    }


def main():
    parser = argparse.ArgumentParser(description='MSE-δ 曲线性质研究')
    parser.add_argument('--delta-step', type=float, default=0.002, help='δ 步长')
    parser.add_argument('--delta-max', type=float, default=1.0, help='δ 最大值')
    parser.add_argument('--delta-min', type=float, default=0.001, help='δ 最小值')
    parser.add_argument('--gamma-steps', type=int, default=60, help='MDM gamma 搜索步数')
    parser.add_argument('--seeds', type=int, default=1, help='随机种子数量（多样本验证）')
    parser.add_argument('--output-dir', type=str, default='data/curve_study', help='输出目录')
    args = parser.parse_args()

    output_dir = Path(__file__).parent / args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    delta_values = np.arange(args.delta_min, args.delta_max + args.delta_step / 2, args.delta_step)
    print(f"δ 范围: [{delta_values[0]:.4f}, {delta_values[-1]:.4f}], 步长={args.delta_step}, 点数={len(delta_values)}")

    # 主要研究对象
    primary_case = (2.0, 1000.0, 1000.0, 7, 'b2_e1000_n7')

    # 扩展案例（用于验证规律）
    extended_cases = [
        (2.0, 1000.0, 1000.0, 5, 'b2_e1000_n5'),
        (2.0, 1000.0, 1000.0, 10, 'b2_e1000_n10'),
        (2.0, 1000.0, 1000.0, 15, 'b2_e1000_n15'),
        (2.0, 1000.0, 1000.0, 20, 'b2_e1000_n20'),
        (1.0, 1000.0, 1000.0, 7, 'b1_e1000_n7'),
        (5.0, 1000.0, 1000.0, 7, 'b5_e1000_n7'),
    ]

    all_cases = [primary_case] + extended_cases
    all_analyses = []

    for beta, eta, gamma, n, label in all_cases:
        print(f"\n{'='*60}")
        print(f"案例: {label} (β={beta}, η={eta}, γ={gamma}, n={n})")
        print(f"{'='*60}")

        case_dir = output_dir / label
        case_dir.mkdir(parents=True, exist_ok=True)

        for seed_offset in range(args.seeds):
            seed = 42 + int(beta * 1000) + int(eta) + n * 100 + seed_offset * 10000
            sample = generate_weibull_sample(beta, eta, gamma, n, seed)
            print(f"\n  Seed {seed}: sample = {sample.tolist()[:5]}{'...' if n > 5 else ''}")

            # 精细扫描
            results = scan_delta_curve(sample, beta, eta, gamma,
                                       delta_values, args.gamma_steps)

            # 分析
            analysis = analyze_curve(results)
            analysis['label'] = label
            analysis['beta'] = beta
            analysis['eta'] = eta
            analysis['gamma'] = gamma
            analysis['n'] = n
            analysis['seed'] = seed
            analysis['sample'] = sample.tolist()
            all_analyses.append(analysis)

            # 打印分析结果
            if analysis['status'] == 'ok':
                print(f"  最优 δ = {analysis['best_delta']:.4f}, MSE = {analysis['best_mse']:.6f}")
                print(f"  单峰: {analysis['is_unimodal']}, 左边界最优: {analysis['at_left_boundary']}")
                print(f"  有效点: {analysis['valid_count']}/{len(delta_values)}, "
                      f"失败点: {analysis['failed_count']}")
                if analysis['failure_delta']:
                    print(f"  MDM 失败起始 δ = {analysis['failure_delta']:.4f}")
                if analysis['curvature_at_min']:
                    print(f"  极值点曲率 = {analysis['curvature_at_min']:.4f}")
            else:
                print(f"  所有 δ 均失败!")

            # 保存详细曲线数据
            csv_path = case_dir / f'curve_seed{seed}.csv'
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(['delta', 'mse', 'mse_beta', 'mse_eta', 'mse_gamma',
                                 'est_beta', 'est_eta', 'est_gamma', 'failure'])
                for r in results:
                    writer.writerow([r['delta'], r['mse'], r['mse_beta'], r['mse_eta'],
                                     r['mse_gamma'], r['est_beta'], r['est_eta'],
                                     r['est_gamma'], r['failure'] or ''])
            print(f"  保存: {csv_path}")

    # 保存汇总分析
    summary_path = output_dir / 'analysis_summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(all_analyses, f, indent=2, ensure_ascii=False)
    print(f"\n汇总分析保存: {summary_path}")

    # 打印跨案例汇总
    print(f"\n{'='*80}")
    print("跨案例汇总")
    print(f"{'='*80}")
    print(f"{'案例':20s} {'最优δ':>8s} {'MSE':>10s} {'单峰':>6s} {'边界':>6s} "
          f"{'失败δ':>8s} {'有效率':>8s}")
    print("-" * 80)
    for a in all_analyses:
        if a['status'] == 'ok':
            rate = f"{a['valid_count']}/{a['valid_count'] + a['failed_count']}"
            fail_d = f"{a['failure_delta']:.3f}" if a['failure_delta'] else "N/A"
            boundary = "左" if a['at_left_boundary'] else ("右" if a['at_right_boundary'] else "中间")
            print(f"{a['label']:20s} {a['best_delta']:8.4f} {a['best_mse']:10.6f} "
                  f"{'Y' if a['is_unimodal'] else 'N':>6s} {boundary:>6s} "
                  f"{fail_d:>8s} {rate:>8s}")


if __name__ == '__main__':
    main()
