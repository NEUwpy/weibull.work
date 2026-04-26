"""
MDM 偏移量 δ 优化 — 训练数据生成脚本

用途：
    蒙特卡洛模拟生成训练数据，供神经网络学习"样本 → 最优 δ"的映射。
    对每个样本遍历 δ 网格，用相对 MSE(β,η,γ) 选出最优 δ*。
    边界样本（最优 δ 在搜索范围两端）自动排除。

参数空间（已确认）：
    β=2, η∈{100,1000,5000}, γ=1000, n∈{5,7,10,15,20}, MC=500
    15 组 × 500 样本 = 7,500 个样本
    δ 网格: [0.001, 1.00] 步长 0.05, 共 20 个值
    MDM 调用: 7,500 × 20 = 150,000 次

指标方案：
    相对 MSE = (β̂-β)²/β² + (η̂-η)²/η² + (γ̂-γ)²/γ²
    消除量纲差异，三参数同等权重

使用方法：
    cd python/studies/mdm_delta

    # 使用默认参数生成（全量 7,500 样本）
    python generate_training_data.py

    # 快速测试（减少 MC 次数）
    python generate_training_data.py --mc-runs 50

    # 自定义参数
    python generate_training_data.py --betas 1,2 --etas 1000 --sample-sizes 5 --mc-runs 100

输出文件：
    training_data_n{n}.csv  — 按样本量分文件（供 N₂ 训练）
    training_data_all.csv   — 全量合并（供 N₁ 训练）
    config.json             — 生成配置记录
    summary.json            — 统计摘要

CSV 格式：
    n,beta,eta,gamma,t1,t2,...,tn,optimal_delta,best_relative_mse

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


def compute_relative_mse(est_beta, est_eta, est_gamma, true_beta, true_eta, true_gamma):
    """计算三参数相对 MSE（消除量纲影响）"""
    return ((est_beta - true_beta) / true_beta) ** 2 + \
           ((est_eta - true_eta) / true_eta) ** 2 + \
           ((est_gamma - true_gamma) / true_gamma) ** 2


def find_optimal_delta(sample, true_beta, true_eta, true_gamma, delta_grid, gamma_steps):
    """
    对给定样本，遍历 δ 网格，找到使相对 MSE 最小的 δ*
    边界排除：最优 δ 在搜索范围两端的样本视为无效
    返回: (optimal_delta, best_relative_mse, success_count) 或 (None, None, 0) 如果所有 δ 都无解
    """
    best_delta = None
    best_mse = float('inf')
    success_count = 0

    delta_min = delta_grid[0]
    delta_max = delta_grid[-1]

    for delta in delta_grid:
        result = run_mdm_with_delta(sample, delta, gamma_steps=gamma_steps)
        if result is None:
            continue

        est_beta, est_eta, est_gamma = result
        # 过滤明显发散的结果
        if est_beta <= 0 or est_beta > 50 or est_eta <= 0 or est_eta > 1e6:
            continue

        mse = compute_relative_mse(est_beta, est_eta, est_gamma, true_beta, true_eta, true_gamma)
        success_count += 1

        if mse < best_mse:
            best_mse = mse
            best_delta = delta

    # 边界排除：最优 δ 在搜索范围两端的样本视为无效
    if best_delta is not None:
        if abs(best_delta - delta_min) < 1e-9 or abs(best_delta - delta_max) < 1e-9:
            return None, None, success_count

    return best_delta, best_mse, success_count


def find_optimal_delta_coarse_to_fine(sample, true_beta, true_eta, true_gamma,
                                      delta_min, delta_max, coarse_step, fine_step,
                                      gamma_steps, fine_range):
    """
    粗搜+细搜两阶段 δ 搜索

    阶段 1（粗搜）: 步长 coarse_step 遍历 [delta_min, delta_max]
    阶段 2（细搜）: 在 best_coarse ± fine_range 范围内，步长 fine_step 精搜

    优点：
    - 比小步长全覆盖快得多
    - 比大步长全覆盖精度高
    - 自然减少边界聚集（粗搜边界不影响，细搜在内部）

    返回: (optimal_delta, best_relative_mse, success_count, is_boundary)
    """
    # === 阶段 1: 粗搜 ===
    coarse_grid = np.arange(delta_min, delta_max + coarse_step / 2, coarse_step)
    coarse_grid = np.round(coarse_grid, 4)

    best_coarse_delta = None
    best_coarse_mse = float('inf')
    coarse_success = 0

    for delta in coarse_grid:
        result = run_mdm_with_delta(sample, delta, gamma_steps=gamma_steps)
        if result is None:
            continue
        est_beta, est_eta, est_gamma = result
        if est_beta <= 0 or est_beta > 50 or est_eta <= 0 or est_eta > 1e6:
            continue
        mse = compute_relative_mse(est_beta, est_eta, est_gamma, true_beta, true_eta, true_gamma)
        coarse_success += 1
        if mse < best_coarse_mse:
            best_coarse_mse = mse
            best_coarse_delta = delta

    if best_coarse_delta is None:
        return None, None, 0, False

    # === 阶段 2: 细搜 ===
    fine_min = max(delta_min, best_coarse_delta - fine_range)
    fine_max = min(delta_max, best_coarse_delta + fine_range)
    fine_grid = np.arange(fine_min, fine_max + fine_step / 2, fine_step)
    fine_grid = np.round(fine_grid, 4)

    best_fine_delta = best_coarse_delta
    best_fine_mse = best_coarse_mse
    fine_success = 0

    for delta in fine_grid:
        result = run_mdm_with_delta(sample, delta, gamma_steps=gamma_steps)
        if result is None:
            continue
        est_beta, est_eta, est_gamma = result
        if est_beta <= 0 or est_beta > 50 or est_eta <= 0 or est_eta > 1e6:
            continue
        mse = compute_relative_mse(est_beta, est_eta, est_gamma, true_beta, true_eta, true_gamma)
        fine_success += 1
        if mse < best_fine_mse:
            best_fine_mse = mse
            best_fine_delta = delta

    # 边界检查：用细搜的边界
    is_boundary = (abs(best_fine_delta - delta_min) < 1e-9 or
                   abs(best_fine_delta - delta_max) < 1e-9)

    return best_fine_delta, best_fine_mse, coarse_success + fine_success, is_boundary


def main():
    parser = argparse.ArgumentParser(description='MDM 偏移量 δ 优化 — 训练数据生成')
    parser.add_argument('--betas', type=str, default='2',
                        help='β 值列表，逗号分隔 (默认: 2)')
    parser.add_argument('--etas', type=str, default='100,1000,5000',
                        help='η 值列表，逗号分隔 (默认: 100,1000,5000)')
    parser.add_argument('--gamma', type=float, default=1000,
                        help='γ 值 (默认: 1000)')
    parser.add_argument('--sample-sizes', type=str, default='5,7,10,15,20',
                        help='样本量列表，逗号分隔 (默认: 5,7,10,15,20)')
    parser.add_argument('--delta-min', type=float, default=0.001,
                        help='δ 搜索最小值 (默认: 0.001)')
    parser.add_argument('--delta-max', type=float, default=1.00,
                        help='δ 搜索最大值 (默认: 1.00)')
    parser.add_argument('--delta-step', type=float, default=0.05,
                        help='δ 搜索步长 (默认: 0.05)')
    parser.add_argument('--search-mode', type=str, default='coarse-to-fine',
                        choices=['grid', 'coarse-to-fine'],
                        help='搜索模式: grid=网格搜索, coarse-to-fine=粗搜+细搜 (默认: coarse-to-fine)')
    parser.add_argument('--coarse-step', type=float, default=0.1,
                        help='粗搜步长 (默认: 0.1)')
    parser.add_argument('--fine-step', type=float, default=0.01,
                        help='细搜步长 (默认: 0.01)')
    parser.add_argument('--fine-range', type=float, default=0.1,
                        help='细搜范围: best_coarse +/- fine_range (默认: 0.1)')
    parser.add_argument('--mc-runs', type=int, default=500,
                        help='每组参数的蒙特卡洛次数 (默认: 500)')
    parser.add_argument('--gamma-steps', type=int, default=60,
                        help='MDM γ 搜索步数 (默认: 60)')
    parser.add_argument('--output', type=str, default=None,
                        help='输出目录 (默认: 同目录下 data/)')
    parser.add_argument('--seed-start', type=int, default=1,
                        help='随机种子起始值 (默认: 1)')

    args = parser.parse_args()

    # 解析参数
    betas = [float(b) for b in args.betas.split(',')]
    etas = [float(e) for e in args.etas.split(',')]
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
        'etas': etas,
        'gamma': args.gamma,
        'sampleSizes': sample_sizes,
        'searchMode': args.search_mode,
        'deltaRange': [args.delta_min, args.delta_max, args.delta_step],
        'deltaCount': len(delta_grid),
        'coarseStep': args.coarse_step if args.search_mode == 'coarse-to-fine' else None,
        'fineStep': args.fine_step if args.search_mode == 'coarse-to-fine' else None,
        'fineRange': args.fine_range if args.search_mode == 'coarse-to-fine' else None,
        'mcRuns': args.mc_runs,
        'gammaSteps': args.gamma_steps,
        'seedStart': args.seed_start,
        'totalCombinations': len(betas) * len(etas) * len(sample_sizes),
        'expectedSamples': len(betas) * len(etas) * len(sample_sizes) * args.mc_runs,
        'generatedAt': datetime.now().isoformat(timespec='seconds'),
    }

    with open(output_dir / 'config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print("MDM 偏移量 delta 优化 -- 训练数据生成")
    print("=" * 60)
    print(f"beta: {betas}")
    print(f"eta: {etas}")
    print(f"gamma: {args.gamma}")
    print(f"样本量: {sample_sizes}")
    if args.search_mode == 'coarse-to-fine':
        print(f"搜索模式: 粗搜+细搜")
        print(f"  粗搜: [{args.delta_min}, {args.delta_max}], 步长 {args.coarse_step}")
        print(f"  细搜: best +/- {args.fine_range}, 步长 {args.fine_step}")
    else:
        print(f"搜索模式: 网格搜索")
        print(f"  delta 网格: [{args.delta_min}, {args.delta_max}], 步长 {args.delta_step}, 共 {len(delta_grid)} 个")
    print(f"MC 次数: {args.mc_runs}")
    print(f"参数组合: {len(betas)}x{len(etas)}x{len(sample_sizes)} = {len(betas)*len(etas)*len(sample_sizes)} 组")
    print(f"预期样本: {len(betas)*len(etas)*len(sample_sizes)*args.mc_runs}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)

    # 按样本量分组生成
    total_records = 0
    total_no_solution = 0
    summary = {}
    all_records = []  # 用于合并 CSV

    for n in sample_sizes:
        print(f"\n--- 生成 n={n} 的训练数据 ---")

        records = []
        no_solution_count = 0

        # 遍历所有 (β, η) 组合
        param_combos = list(product(betas, etas))

        for beta_val, eta_val in param_combos:
            gamma_val = args.gamma

            print(f"  β={beta_val}, η={eta_val}, γ={gamma_val}: ", end='', flush=True)

            combo_no_solution = 0
            for sim_id in range(args.seed_start, args.seed_start + args.mc_runs):
                seed = sim_id + int(beta_val * 1000) + int(eta_val) + n * 100

                # 生成样本
                sample = generate_weibull_sample(beta_val, eta_val, gamma_val, n, seed)

                # 找最优 δ
                if args.search_mode == 'coarse-to-fine':
                    optimal_delta, best_mse, success_count, is_boundary = find_optimal_delta_coarse_to_fine(
                        sample, beta_val, eta_val, gamma_val,
                        args.delta_min, args.delta_max, args.coarse_step, args.fine_step,
                        args.gamma_steps, args.fine_range
                    )
                    if is_boundary:
                        optimal_delta = None
                else:
                    optimal_delta, best_mse, success_count = find_optimal_delta(
                        sample, beta_val, eta_val, gamma_val, delta_grid, args.gamma_steps
                    )

                if optimal_delta is None:
                    combo_no_solution += 1
                    continue

                # 记录: [n, beta, eta, gamma, t1, t2, ..., tn, optimal_delta, best_relative_mse]
                row = [n, beta_val, eta_val, gamma_val] + sample.tolist() + [optimal_delta, best_mse]
                records.append(row)
                all_records.append(row)

            no_solution_count += combo_no_solution
            success_rate = (args.mc_runs - combo_no_solution) / args.mc_runs * 100
            print(f"成功 {args.mc_runs - combo_no_solution}/{args.mc_runs} ({success_rate:.0f}%)")

        # 写入按 n 分文件的 CSV
        csv_path = output_dir / f'training_data_n{n}.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # 表头
            header = ['n', 'beta', 'eta', 'gamma'] + [f't{i+1}' for i in range(n)] + ['optimal_delta', 'best_relative_mse']
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

    # 写入全量合并 CSV（供 N₁ 训练）
    all_csv_path = output_dir / 'training_data_all.csv'
    max_n = max(sample_sizes)
    with open(all_csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # 使用最大 n 的表头，不足的列填空
        header = ['n', 'beta', 'eta', 'gamma'] + [f't{i+1}' for i in range(max_n)] + ['optimal_delta', 'best_relative_mse']
        writer.writerow(header)
        for row in all_records:
            n_val = int(row[0])
            # 补齐到 max_n 列
            padded = row[:4 + n_val] + [None] * (max_n - n_val) + row[4 + n_val:]
            writer.writerow(padded)

    print(f"\n  全量合并: {all_csv_path} ({len(all_records)} 条记录)")

    # 写入 summary
    summary_data = {
        'config': config,
        'results': summary,
        'totalRecords': total_records,
        'totalNoSolution': total_no_solution,
        'successRate': f"{total_records / max(total_records + total_no_solution, 1) * 100:.1f}%",
    }

    with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("生成完成！")
    print(f"总记录数: {total_records}")
    print(f"无解记录: {total_no_solution}")
    print(f"成功率: {total_records / max(total_records + total_no_solution, 1) * 100:.1f}%")
    print(f"输出目录: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
