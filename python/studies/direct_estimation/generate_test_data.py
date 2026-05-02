"""
直接估计 — 泛化测试数据生成脚本

用途：
    生成独立测试集，用于评估模型的泛化能力。
    测试集参数组合分三类：组内(ig)、插值(ip)、外推(ex)。

三类测试数据：
    组内(in_group): 训练集中的参数组合（基线精度）
    插值(interpolation): 训练网格中间的新组合
    外推(extrapolation): 超出训练范围的组合

参数空间（V2 训练集）：
    β∈{0.5,1,2,3,5}, η∈{100,500,1000,3000,5000}, γ∈{50,100,200,1000}, n∈{5,7,10,15}

插值参数（训练点之间的值）：
    β_ip∈{0.75,1.5,2.5,4}, η_ip∈{300,750,2000,4000}, γ_ip∈{75,150,600}

外推参数（超出训练范围）：
    β_ex∈{0.3,8,10}, η_ex∈{50,8000,10000}, γ_ex∈{10,300,1500}

使用方法：
    cd python/studies/direct_estimation

    # 生成全部测试数据
    python generate_test_data.py --type all

    # 只生成插值测试集
    python generate_test_data.py --type interpolation

    # 只生成外推测试集
    python generate_test_data.py --type extrapolation

    # 只生成组内测试集
    python generate_test_data.py --type in_group

输出文件：
    data/
    ├── test_data_ig_n{5,7,10,15}.csv     # 组内测试集
    ├── test_data_ip_n{5,7,10,15}.csv     # 插值测试集
    └── test_data_ex_n{5,7,10,15}.csv     # 外推测试集

CSV 格式：
    n,beta,eta,gamma,validation_type,t1,t2,...,tn

作者：Claude Code
日期：2026-04-27
"""

import sys
import json
import csv
import argparse
import numpy as np
from pathlib import Path
from itertools import product
from datetime import datetime


# V2 训练参数空间
TRAIN_BETAS = [0.5, 1.0, 2.0, 3.0, 5.0]
TRAIN_ETAS = [100.0, 500.0, 1000.0, 3000.0, 5000.0]
TRAIN_GAMMAS = [50.0, 100.0, 200.0, 1000.0]
TRAIN_NS = [5, 7, 10, 15]


def generate_weibull_sample(beta: float, eta: float, gamma: float, n: int, seed: int) -> np.ndarray:
    """生成三参数威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)


def get_in_group_combos():
    """组内参数组合（训练集中的组合）"""
    return list(product(TRAIN_BETAS, TRAIN_ETAS, TRAIN_GAMMAS))


def get_interpolation_combos():
    """插值参数组合（训练网格之间的值）"""
    betas_ip = [0.75, 1.5, 2.5, 4.0]
    etas_ip = [300.0, 750.0, 2000.0, 4000.0]
    gammas_ip = [75.0, 150.0, 600.0]
    return list(product(betas_ip, etas_ip, gammas_ip))


def get_extrapolation_combos():
    """外推参数组合（超出训练范围的值）"""
    betas_ex = [0.3, 8.0, 10.0]
    etas_ex = [50.0, 8000.0, 10000.0]
    gammas_ex = [10.0, 300.0, 1500.0]

    # 合理搭配：避免 gamma > eta 的无意义组合
    combos = []
    for b in betas_ex:
        for e in etas_ex:
            for g in gammas_ex:
                # gamma 应小于 eta（位置参数 < 尺度参数）
                if g < e:
                    combos.append((b, e, g))
    return combos


def main():
    parser = argparse.ArgumentParser(description='直接估计 — 泛化测试数据生成')
    parser.add_argument('--type', type=str, default='all',
                        choices=['all', 'in_group', 'interpolation', 'extrapolation'],
                        help='测试类型: all=全部, in_group=组内, interpolation=插值, extrapolation=外推 (默认: all)')
    parser.add_argument('--sample-sizes', type=str, default='5,7,10,15',
                        help='样本量列表，逗号分隔 (默认: 5,7,10,15)')
    parser.add_argument('--mc-runs', type=int, default=100,
                        help='每组参数的蒙特卡洛次数 (默认: 100)')
    parser.add_argument('--output', type=str, default=None,
                        help='输出目录 (默认: 同目录下 data/)')
    parser.add_argument('--seed-start', type=int, default=100000,
                        help='随机种子起始值 (默认: 100000，避免与训练集重叠)')

    args = parser.parse_args()

    sample_sizes = [int(n) for n in args.sample_sizes.split(',')]

    # 输出目录
    output_dir = Path(args.output) if args.output else Path(__file__).parent / 'data'
    output_dir.mkdir(exist_ok=True)

    # 确定要生成的类型
    types_to_generate = []
    if args.type == 'all':
        types_to_generate = ['in_group', 'interpolation', 'extrapolation']
    else:
        types_to_generate = [args.type]

    # 参数组合
    type_combos = {
        'in_group': get_in_group_combos(),
        'interpolation': get_interpolation_combos(),
        'extrapolation': get_extrapolation_combos(),
    }

    type_labels = {
        'in_group': 'ig',
        'interpolation': 'ip',
        'extrapolation': 'ex',
    }

    print("=" * 60)
    print("直接估计 -- 泛化测试数据生成")
    print("=" * 60)
    print(f"生成类型: {types_to_generate}")
    print(f"样本量: {sample_sizes}")
    print(f"MC 次数: {args.mc_runs}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)

    total_records = 0
    summary = {}

    for test_type in types_to_generate:
        combos = type_combos[test_type]
        label = type_labels[test_type]

        print(f"\n--- {test_type} ({label}): {len(combos)} 组参数组合 ---")

        for n in sample_sizes:
            records = []

            for beta_val, eta_val, gamma_val in combos:
                for sim_id in range(args.seed_start, args.seed_start + args.mc_runs):
                    # 种子设计：不同 test_type 用不同偏移，避免重叠
                    type_offset = {'in_group': 0, 'interpolation': 500000, 'extrapolation': 1000000}
                    seed = sim_id + int(beta_val * 1000) + int(eta_val) + int(gamma_val * 100) + n * 100 + type_offset[test_type]

                    sample = generate_weibull_sample(beta_val, eta_val, gamma_val, n, seed)
                    row = [n, beta_val, eta_val, gamma_val, label] + sample.tolist()
                    records.append(row)

            # 写入 CSV
            csv_path = output_dir / f'test_data_{label}_n{n}.csv'
            with open(csv_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                header = ['n', 'beta', 'eta', 'gamma', 'validation_type'] + [f't{i+1}' for i in range(n)]
                writer.writerow(header)
                writer.writerows(records)

            total_records += len(records)
            key = f'{label}_n{n}'
            summary[key] = {
                'testType': test_type,
                'validationType': label,
                'sampleSize': n,
                'paramCombinations': len(combos),
                'mcRuns': args.mc_runs,
                'totalSamples': len(records),
                'outputFile': str(csv_path.name),
            }

            print(f"  n={n}: {len(combos)} 组 × {args.mc_runs} MC = {len(records)} 条 → {csv_path.name}")

    # 写入 summary
    summary_data = {
        'config': {
            'type': args.type,
            'sampleSizes': sample_sizes,
            'mcRuns': args.mc_runs,
            'seedStart': args.seed_start,
        },
        'results': summary,
        'totalRecords': total_records,
        'generatedAt': datetime.now().isoformat(timespec='seconds'),
    }

    with open(output_dir / 'test_data_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary_data, f, indent=2, ensure_ascii=False)

    print("\n" + "=" * 60)
    print("测试数据生成完成！")
    print(f"总记录数: {total_records}")
    print(f"输出目录: {output_dir}")
    print("=" * 60)


if __name__ == '__main__':
    main()
