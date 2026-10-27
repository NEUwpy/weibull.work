"""
MDM 示例1 数据生成脚本 - 多维度参数研究

用途：
    生成 MDM 方法在不同参数组合下的蒙特卡洛仿真数据

使用方法：
    cd python/studies/mdm/demo1
    python generate_data.py                # 增量生成所有组合
    python generate_data.py --force        # 强制重新生成
    python generate_data.py --only-beta 2 3 --only-eta 1000  # 只生成指定组合

输出文件（新命名规范）：
    public/studies/mdm/demo1/chunks/
    ├── b1.5_e200_g1000_n3_d0_rep1000_seed42_step60.csv
    ├── b1.5_e200_g1000_n3_d0.05_rep1000_seed42_step60.csv
    └── ...

命名格式：b{beta}_e{eta}_g{gamma}_n{n}_d{offset}_rep{rep}_seed{seed}_step{step}.csv

参数组合：
    - β ∈ {1.5, 2, 3, 5, 7}
    - η ∈ {200, 1000, 5000}
    - γ = 1000 (固定)
    - n ∈ {3, 5, 7, 10, 20, 30}
    - δ ∈ {0, 0.05, 0.1, 0.15, 0.2}
    - 总组合数: 5 × 3 × 6 × 5 = 450
"""

import sys
import csv
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional
from itertools import product

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

import yaml
from methods.mdm import MDM


def format_number(value):
    """格式化数值：整数显示为整数，小数保留原样"""
    if value == int(value):
        return str(int(value))
    return str(value)


def generate_chunk_filename(params: dict) -> str:
    """
    生成 chunk 文件名

    格式: b{beta}_e{eta}_g{gamma}_n{n}_d{offset}_rep{rep}_seed{seed}_step{step}.csv
    """
    beta = format_number(params['beta'])
    eta = int(params['eta'])
    gamma = int(params['gamma'])
    n = int(params['n'])
    offset = format_number(params['offset'])
    rep = int(params['rep'])
    seed = int(params['seed'])
    step = int(params['step'])

    return f'b{beta}_e{eta}_g{gamma}_n{n}_d{offset}_rep{rep}_seed{seed}_step{step}.csv'


def parse_config(config_path: str) -> dict:
    """解析 config.md 文件"""
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()

    if content.startswith('---'):
        parts = content.split('---', 2)
        if len(parts) >= 3:
            yaml_content = parts[1]
            config = yaml.safe_load(yaml_content)
            return config

    raise ValueError(f"无法解析配置文件: {config_path}")


def generate_weibull_sample(beta: float, eta: float, gamma: float, n: int, seed: int) -> np.ndarray:
    """生成三参数威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)


def run_mdm_estimation(sample: np.ndarray, offset: float, gamma_steps: int, rank_method: str):
    """
    运行 MDM 估计
    返回: (est_beta, est_eta, est_gamma, r2, status) 或 None
    """
    try:
        algo = MDM(sample.tolist(), rank_method=rank_method)
        result = algo.run(trace=False, offset=offset, gamma_steps=gamma_steps, rank_method=rank_method)

        if result[4] == "no_intersection":
            return None

        return result
    except Exception as e:
        return None


def generate_chunk(
    params: dict,
    mc_runs: int,
    gamma_steps: int,
    rank_method: str,
    output_path: Path,
    verbose: bool = False
) -> dict:
    """生成单个参数组合的仿真数据"""
    beta = params['beta']
    eta = params['eta']
    gamma = params['gamma']
    n = params['n']
    offset = params['offset']

    no_solution_count = 0

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # 写入表头
        header = ['beta_true', 'eta_true', 'gamma_true', 'sample_size', 'offset_value', 'sim_id',
                  'est_beta', 'est_eta', 'est_gamma',
                  'bias_beta', 'bias_eta', 'bias_gamma', 'r_squared']
        writer.writerow(header)

        for sim_id in range(1, mc_runs + 1):
            # 生成种子 (确定性)
            seed = sim_id + int(beta * 1000) + int(eta) + int(gamma) + n * 10000 + int(offset * 100)

            # 生成样本
            sample = generate_weibull_sample(beta, eta, gamma, n, seed)

            # MDM 估计
            result = run_mdm_estimation(sample, offset, gamma_steps, rank_method)

            if result is None:
                no_solution_count += 1
                row = [beta, eta, gamma, n, offset, sim_id,
                       'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN']
            else:
                est_beta, est_eta, est_gamma, r2, _ = result
                bias_beta = est_beta - beta
                bias_eta = est_eta - eta
                bias_gamma = est_gamma - gamma
                row = [beta, eta, gamma, n, offset, sim_id,
                       f'{est_beta:.6f}', f'{est_eta:.6f}', f'{est_gamma:.6f}',
                       f'{bias_beta:.6f}', f'{bias_eta:.6f}', f'{bias_gamma:.6f}',
                       f'{r2:.6f}']

            writer.writerow(row)

            if verbose and sim_id % 200 == 0:
                print(f"    sim_id={sim_id}/{mc_runs}")

    return {
        'params': params,
        'mcRuns': mc_runs,
        'noSolutionCount': no_solution_count,
        'generated': datetime.now().isoformat(timespec='seconds')
    }


def main():
    parser = argparse.ArgumentParser(description='MDM 示例1 数据生成脚本')
    parser.add_argument('--force', '-f', action='store_true', help='强制重新生成')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--only-beta', nargs='+', type=float, help='只生成指定 beta 值')
    parser.add_argument('--only-eta', nargs='+', type=int, help='只生成指定 eta 值')
    parser.add_argument('--only-n', nargs='+', type=int, help='只生成指定样本量')
    parser.add_argument('--only-d', nargs='+', type=float, help='只生成指定偏移量')
    parser.add_argument('--seed', type=int, default=42, help='基础随机种子 (默认: 42)')
    parser.add_argument('--rep', type=int, help='仿真重复次数 (覆盖配置文件)')

    args = parser.parse_args()

    # 定位配置文件
    config_path = PROJECT_ROOT / 'public' / 'studies' / 'mdm' / 'demo1' / 'config.md'
    output_dir = config_path.parent / 'chunks'
    output_dir.mkdir(exist_ok=True)

    if not config_path.exists():
        print(f"错误: 配置文件不存在 - {config_path}")
        sys.exit(1)

    # 解析配置
    config = parse_config(str(config_path))

    # 获取固定参数
    defaults = config.get('defaults', {})
    gamma = defaults.get('gamma', 1000)

    # 获取计算配置
    calculation = config.get('calculation', {})
    gamma_steps = calculation.get('gammaSteps', 60)
    rank_method = calculation.get('rankMethod', 'bernard')

    # 仿真次数
    mc_runs = config.get('simulation', {}).get('mcRuns', 1000)
    seed = args.seed

    # 获取参数范围
    params_config = {p['id']: p for p in config.get('params', [])}

    beta_values = args.only_beta if args.only_beta else [float(v) for v in params_config['beta'].get('discreteValues', [])]
    eta_values = args.only_eta if args.only_eta else [int(v) for v in params_config['eta'].get('discreteValues', [])]
    n_values = args.only_n if args.only_n else [int(v) for v in params_config['sampleSize'].get('discreteValues', [])]
    offset_values = args.only_d if args.only_d else [float(v) for v in params_config['process'].get('discreteValues', [])]

    # 生成所有组合
    combinations = list(product(beta_values, eta_values, n_values, offset_values))

    # 筛选需要生成的组合
    to_generate = []
    for beta, eta, n, offset in combinations:
        params = {
            'beta': beta,
            'eta': eta,
            'gamma': gamma,
            'n': n,
            'offset': offset,
            'rep': mc_runs,
            'seed': seed,
            'step': gamma_steps,
        }
        filename = generate_chunk_filename(params)
        output_path = output_dir / filename

        if args.force or not output_path.exists():
            to_generate.append((params, output_path))

    if not to_generate:
        print("所有分片已存在，无需生成")
        return

    print("=" * 60)
    print(f"MDM 示例1 数据生成")
    print(f"固定参数: γ={gamma}")
    print(f"计算配置: 步长={gamma_steps}, 方法={rank_method}")
    print(f"种子: {seed}")
    print(f"β ∈ {beta_values}")
    print(f"η ∈ {eta_values}")
    print(f"n ∈ {n_values}")
    print(f"δ ∈ {offset_values}")
    print(f"总组合数: {len(combinations)}, 待生成: {len(to_generate)}")
    print(f"每组仿真次数: {mc_runs}")
    print("=" * 60)

    # 生成数据
    results = []
    for i, (params, output_path) in enumerate(to_generate):
        print(f"\n[{i+1}/{len(to_generate)}] β={params['beta']}, η={params['eta']}, n={params['n']}, δ={params['offset']}")

        result = generate_chunk(
            params=params,
            mc_runs=mc_runs,
            gamma_steps=gamma_steps,
            rank_method=rank_method,
            output_path=output_path,
            verbose=args.verbose
        )
        results.append(result)

        print(f"  完成: {output_path.name}")
        print(f"  无解次数: {result['noSolutionCount']}/{mc_runs} ({result['noSolutionCount']/mc_runs*100:.1f}%)")

    # 汇总
    print("\n" + "=" * 60)
    print("生成完成！")
    print(f"生成文件: {len(results)} 个")
    print(f"输出目录: {output_dir}")
    total_no_solution = sum(r['noSolutionCount'] for r in results)
    total_runs = len(results) * mc_runs
    print(f"总无解率: {total_no_solution}/{total_runs} ({total_no_solution/total_runs*100:.1f}%)")
    print("=" * 60)


if __name__ == '__main__':
    main()
