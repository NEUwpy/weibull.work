"""
MDM 偏移量 δ 优化 — 训练数据生成脚本

用途：
    蒙特卡洛模拟生成训练数据，供神经网络学习"样本 → 最优 δ"的映射。
    对每个样本遍历 δ 网格，用 MSE(β,η,γ) 选出最优 δ*。

使用方法：
    cd python/studies/mdm_delta

    # 使用默认精简方案生成
    python generate_training_data.py

    # 自定义参数
    python generate_training_data.py --betas 1,2 --gamma 0 --sample-sizes 5,10 --mc-runs 200

    # 指定输出目录
    python generate_training_data.py --output ./data

输出文件：
    training_data_n{n}.csv  — 按样本量分文件
    config.json             — 生成配置记录
    summary.json            — 统计摘要

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
from itertools import product
from datetime import datetime

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM


def generate_weibull_sample(beta: float, eta: float, gamma: float, n: int, seed: int) -> np.ndarray:
    """生成三参数威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)


def run_mdm_with_delta(sample: np.ndarray, delta: float, gamma_steps: int = 60, rank_method: str = 'bernard'):
    """
    用指定的 δ 运行 MDM 估计
    返回: (est_beta, est_eta, est_gamma) 或 None (无解时)
    """
    try:
        algo = MDM(sample.tolist(), rank_method=rank_method)
        result = algo.run(trace=False, offset=delta, gamma_steps=gamma_steps, rank_method=rank_method)

        if result[4] == "no_intersection":
            return None

        return (result[0], result[1], result[2])  # (beta, eta, gamma)
    except Exception:
        return None


def compute_mse(est_beta, est_eta, est_gamma, true_beta, true_eta, true_gamma):
    """计算三参数 MSE"""
    return ((est_beta - true_beta) ** 2 +
            (est_eta - true_eta) ** 2 +
            (est_gamma - true_gamma) ** 2)


def find_optimal_delta(sample, true_beta, true_eta, true_gamma, delta_grid, gamma_steps):
    """
    对给定样本，遍历 δ 网格，找到使 MSE 最小的 δ*
    返回: (optimal_delta, best_mse, success_count) 或 (None, None, 0) 如果所有 δ 都无解
    """
    best_delta = None
    best_mse = float('inf')
    success_count = 0

    for delta in delta_grid:
        result = run_mdm_with_delta(sample, delta, gamma_steps=gamma_steps)
        if result is None:
            continue

        est_beta, est_eta, est_gamma = result
        # 过滤明显发散的结果
        if est_beta <= 0 or est_beta > 50 or est_eta <= 0 or est_eta > 1e6:
            continue

        mse = compute_mse(est_beta, est_eta, est_gamma, true_beta, true_eta, true_gamma)
        success_count += 1

        if mse < best_mse:
            best_mse = mse
            best_delta = delta

    return best_delta, best_mse, success_count


def main():
    parser = argparse.ArgumentParser(description='MDM 偏移量 δ 优化 — 训练数据生成')
    parser.add_argument('--betas', type=str, default='1,2',
                        help='β 值列表，逗号分隔 (默认: 1,2)')
    parser.add_argument('--eta', type=float, default=1000,
                        help='η 值 (默认: 1000)')
    parser.add_argument('--gamma', type=float, default=0,
                        help='γ 值 (默认: 0)')
    parser.add_argument('--sample-sizes', type=str, default='5,10',
                        help='样本量列表，逗号分隔 (默认: 5,10)')
    parser.add_argument('--delta-min', type=float, default=0.01,
                        help='δ 搜索最小值 (默认: 0.01)')
    parser.add_argument('--delta-max', type=float, default=0.50,
                        help='δ 搜索最大值 (默认: 0.50)')
    parser.add_argument('--delta-step', type=float, default=0.01,
                        help='δ 搜索步长 (默认: 0.01)')
    parser.add_argument('--mc-runs', type=int, default=200,
                        help='每组参数的蒙特卡洛次数 (默认: 200)')
    parser.add_argument('--gamma-steps', type=int, default=60,
                        help='MDM γ 搜索步数 (默认: 60)')
    parser.add_argument('--output', type=str, default=None,
                        help='输出目录 (默认: 同目录下 data/)')
    parser.add_argument('--seed-start', type=int, default=1,
                        help='随机种子起始值 (默认: 1)')

    args = parser.parse_args()

    # 解析参数
    betas = [float(b) for b in args.betas.split(',')]
    sample_sizes = [int(n) for n in args.sample_sizes.split(',')]
    delta_grid = np.arange(args.delta_min, args.delta_max + args.delta_step / 2, args.delta_step)
    delta_grid = np.round(delta_grid, 4)

    # 输出目录
    if args.output:
        output_dir = Path(args.output)
    else:
        output_dir = Path(__file__).parent / 'data'
    output_dir.mkdir(exist_ok=True)

    # 记录配置
    config = {
        'betas': betas,
        'eta': args.eta,
        'gamma': args.gamma,
        'sampleSizes': sample_sizes,
        'deltaRange': [args.delta_min, args.delta_max, args.delta_step],
        'deltaCount': len(delta_grid),
        'mcRuns': args.mc_runs,
        'gammaSteps': args.gamma_steps,
        'seedStart': args.seed_start,
        'generatedAt': datetime.now().isoformat(timespec='seconds'),
    }

    with open(output_dir / 'config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print("MDM 偏移量 δ 优化 — 训练数据生成")
    print("=" * 60)
    print(f"β: {betas}")
    print(f"η: {args.eta}")
    print(f"γ: {args.gamma}")
    print(f"样本量: {sample_sizes}")
    print(f"δ 网格: [{args.delta_min}, {args.delta_max}], 步长 {args.delta_step}, 共 {len(delta_grid)} 个")
    print(f"MC 次数: {args.mc_runs}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)

    # 按样本量分组生成
    total_records = 0
    total_no_solution = 0
    summary = {}

    for n in sample_sizes:
        print(f"\n--- 生成 n={n} 的训练数据 ---")

        records = []
        no_solution_count = 0

        param_combos = list(product(betas))
        # 对每个 (β,) 组合，γ 和 η 固定
        for beta in param_combos:
            beta_val = beta[0]
            eta_val = args.eta
            gamma_val = args.gamma

            print(f"  β={beta_val}, η={eta_val}, γ={gamma_val}: ", end='', flush=True)

            combo_no_solution = 0
            for sim_id in range(args.seed_start, args.seed_start + args.mc_runs):
                seed = sim_id + int(beta_val * 1000) + n * 100

                # 生成样本
                sample = generate_weibull_sample(beta_val, eta_val, gamma_val, n, seed)

                # 找最优 δ
                optimal_delta, best_mse, success_count = find_optimal_delta(
                    sample, beta_val, eta_val, gamma_val, delta_grid, args.gamma_steps
                )

                if optimal_delta is None:
                    combo_no_solution += 1
                    continue

                # 记录: [n, t1, t2, ..., tn, optimal_delta, best_mse]
                row = [n] + sample.tolist() + [optimal_delta, best_mse]
                records.append(row)

            no_solution_count += combo_no_solution
            success_rate = (args.mc_runs - combo_no_solution) / args.mc_runs * 100
            print(f"成功 {args.mc_runs - combo_no_solution}/{args.mc_runs} ({success_rate:.0f}%)")

        # 写入 CSV
        csv_path = output_dir / f'training_data_n{n}.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # 表头
            header = ['n'] + [f't{i+1}' for i in range(n)] + ['optimal_delta', 'best_mse']
            writer.writerow(header)
            writer.writerows(records)

        total_records += len(records)
        total_no_solution += no_solution_count

        summary[f'n{n}'] = {
            'totalSamples': len(records) + no_solution_count,
            'successSamples': len(records),
            'noSolutionSamples': no_solution_count,
            'successRate': f"{len(records) / max(len(records) + no_solution_count, 1) * 100:.1f}%",
            'outputFile': str(csv_path.name),
        }

        print(f"  输出: {csv_path} ({len(records)} 条记录)")

    # 写入 summary
    summary_data = {
        'config': config,
        'results': summary,
        'totalRecords': total_records,
        'totalNoSolution': total_no_solution,
    }

    with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("生成完成！")
    print(f"总记录数: {total_records}")
    print(f"无解记录: {total_no_solution}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
