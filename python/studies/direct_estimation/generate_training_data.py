"""
直接估计 — 训练数据生成脚本

用途：
    蒙特卡洛模拟生成训练数据，供神经网络学习"样本 → β,η,γ"的直接映射。
    与模块 1（MDM δ 优化）不同，本模块不需要调用 MDM，直接从 Weibull 分布采样即可。

参数空间（V2）：
    β∈{0.5,1,2,3,5}, η∈{100,500,1000,3000,5000}, γ∈{50,100,200,1000}, n∈{5,7,10,15}, MC=500
    100 组 × 4 n × 500 = 200,000 个样本

使用方法：
    cd python/studies/direct_estimation

    # 使用默认参数生成
    python generate_training_data.py

    # 自定义参数
    python generate_training_data.py --betas 1,2 --etas 1000 --sample-sizes 5,10 --mc-runs 200

输出文件：
    data/
    ├── config.json                  # 生成配置
    ├── training_data_n5.csv         # n=5 的训练数据
    └── training_data_n10.csv        # n=10 的训练数据

CSV 格式：
    n,beta,eta,gamma,t1,t2,...,tn

作者：Claude Code
日期：2026-04-26
"""

import sys
import json
import csv
import argparse
import numpy as np
from pathlib import Path
from itertools import product
from datetime import datetime


def generate_weibull_sample(beta: float, eta: float, gamma: float, n: int, seed: int) -> np.ndarray:
    """生成三参数威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)


def main():
    parser = argparse.ArgumentParser(description='直接估计 — 训练数据生成')
    parser.add_argument('--betas', type=str, default='0.5,1,2,3,5',
                        help='β 值列表，逗号分隔 (默认: 0.5,1,2,3,5)')
    parser.add_argument('--etas', type=str, default='100,500,1000,3000,5000',
                        help='η 值列表，逗号分隔 (默认: 100,500,1000,3000,5000)')
    parser.add_argument('--gammas', type=str, default='50,100,200,1000',
                        help='γ 值列表，逗号分隔 (默认: 50,100,200,1000)')
    parser.add_argument('--sample-sizes', type=str, default='5,7,10,15',
                        help='样本量列表，逗号分隔 (默认: 5,7,10,15)')
    parser.add_argument('--mc-runs', type=int, default=500,
                        help='每组参数的蒙特卡洛次数 (默认: 500)')
    parser.add_argument('--output', type=str, default=None,
                        help='输出目录 (默认: 同目录下 data/)')
    parser.add_argument('--seed-start', type=int, default=1,
                        help='随机种子起始值 (默认: 1)')

    args = parser.parse_args()

    # 解析参数
    betas = [float(b) for b in args.betas.split(',')]
    etas = [float(e) for e in args.etas.split(',')]
    gammas = [float(g) for g in args.gammas.split(',')]
    sample_sizes = [int(n) for n in args.sample_sizes.split(',')]

    # 输出目录
    output_dir = Path(args.output) if args.output else Path(__file__).parent / 'data'
    output_dir.mkdir(exist_ok=True)

    # 记录配置
    config = {
        'betas': betas,
        'etas': etas,
        'gammas': gammas,
        'sampleSizes': sample_sizes,
        'mcRuns': args.mc_runs,
        'seedStart': args.seed_start,
        'totalCombinations': len(betas) * len(etas) * len(gammas) * len(sample_sizes),
        'expectedSamples': len(betas) * len(etas) * len(gammas) * len(sample_sizes) * args.mc_runs,
        'generatedAt': datetime.now().isoformat(timespec='seconds'),
    }

    with open(output_dir / 'config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    print("=" * 60)
    print("直接估计 -- 训练数据生成")
    print("=" * 60)
    print(f"beta: {betas}")
    print(f"eta: {etas}")
    print(f"gamma: {gammas}")
    print(f"样本量: {sample_sizes}")
    print(f"MC 次数: {args.mc_runs}")
    total_combos = len(betas) * len(etas) * len(gammas) * len(sample_sizes)
    print(f"参数组合: {total_combos} 组")
    print(f"预期样本: {total_combos * args.mc_runs}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)

    # 按样本量分组生成
    total_records = 0
    summary = {}

    for n in sample_sizes:
        print(f"\n--- 生成 n={n} 的训练数据 ---")

        records = []

        # 遍历所有 (β, η, γ) 组合
        param_combos = list(product(betas, etas, gammas))

        for beta_val, eta_val, gamma_val in param_combos:
            print(f"  β={beta_val}, η={eta_val}, γ={gamma_val}: ", end='', flush=True)

            for sim_id in range(args.seed_start, args.seed_start + args.mc_runs):
                seed = sim_id + int(beta_val * 1000) + int(eta_val) + int(gamma_val * 100) + n * 100

                # 生成样本
                sample = generate_weibull_sample(beta_val, eta_val, gamma_val, n, seed)

                # 记录: [n, beta, eta, gamma, t1, t2, ..., tn]
                row = [n, beta_val, eta_val, gamma_val] + sample.tolist()
                records.append(row)

            print(f"{args.mc_runs} 条")

        # 写入按 n 分文件的 CSV
        csv_path = output_dir / f'training_data_n{n}.csv'
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            header = ['n', 'beta', 'eta', 'gamma'] + [f't{i+1}' for i in range(n)]
            writer.writerow(header)
            writer.writerows(records)

        total_records += len(records)

        summary[f'n{n}'] = {
            'totalSamples': len(records),
            'paramCombinations': len(param_combos),
            'mcRuns': args.mc_runs,
            'outputFile': str(csv_path.name),
        }

        print(f"  输出: {csv_path} ({len(records)} 条记录)")

    # 写入 summary
    summary_data = {
        'config': config,
        'results': summary,
        'totalRecords': total_records,
    }

    with open(output_dir / 'summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("生成完成！")
    print(f"总记录数: {total_records}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
