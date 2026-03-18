"""
MLE 示例2 数据生成脚本 - 蒙特卡洛收敛性研究

用途：
    为每个样本量生成 5000 次 MLE 仿真数据，用于研究收敛特性

使用方法：
    cd python/studies/mle/demo2
    python generate_data.py              # 生成所有样本量
    python generate_data.py --only 3 5 7 # 只生成指定样本量
    python generate_data.py --force      # 强制重新生成

输出文件：
    public/studies/mle/demo2/chunks/
    ├── n3.csv    # 样本量=3 的 5000 次仿真
    ├── n4.csv    # 样本量=4 的 5000 次仿真
    └── ...
"""

import sys
import os
import csv
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Optional, List

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

import yaml
from methods.mle import MLE


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


def run_mle_estimation(sample: np.ndarray):
    """
    运行 MLE 估计
    返回: (est_beta, est_eta, est_gamma, r2, status) 或 None
    """
    try:
        algo = MLE(sample.tolist())
        result = algo.run(trace=False)

        if result is None or result[4] == "no_solution":
            return None

        return result
    except Exception as e:
        return None


def generate_chunk(
    sample_size: int,
    fixed_params: dict,
    mc_runs: int,
    output_path: Path,
    verbose: bool = False
) -> dict:
    """生成单个样本量的仿真数据"""
    true_beta = fixed_params['beta']
    true_eta = fixed_params['eta']
    true_gamma = fixed_params['gamma']

    no_solution_count = 0

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # 写入表头 (MLE 没有 offset_value)
        header = ['beta_true', 'eta_true', 'sample_size', 'sim_id',
                  'est_beta', 'est_eta', 'est_gamma',
                  'bias_beta', 'bias_eta', 'bias_gamma', 'r_squared']
        writer.writerow(header)

        for sim_id in range(1, mc_runs + 1):
            # 生成种子 (确定性)
            seed = sim_id + sample_size * 1000

            # 生成样本
            sample = generate_weibull_sample(true_beta, true_eta, true_gamma, sample_size, seed)

            # MLE 估计
            result = run_mle_estimation(sample)

            if result is None:
                no_solution_count += 1
                row = [true_beta, true_eta, sample_size, sim_id,
                       'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN']
            else:
                est_beta, est_eta, est_gamma, r2, _ = result
                bias_beta = est_beta - true_beta
                bias_eta = est_eta - true_eta
                bias_gamma = est_gamma - true_gamma
                row = [true_beta, true_eta, sample_size, sim_id,
                       f'{est_beta:.6f}', f'{est_eta:.6f}', f'{est_gamma:.6f}',
                       f'{bias_beta:.6f}', f'{bias_eta:.6f}', f'{bias_gamma:.6f}',
                       f'{r2:.6f}' if r2 is not None else 'NaN']

            writer.writerow(row)

            if verbose and sim_id % 1000 == 0:
                print(f"  n={sample_size}: {sim_id}/{mc_runs} 完成")

    return {
        'sampleSize': sample_size,
        'mcRuns': mc_runs,
        'noSolutionCount': no_solution_count,
        'generated': datetime.now().isoformat(timespec='seconds')
    }


def generate_convergence_csv(chunks_dir: Path, output_path: Path, mc_runs_list: List[int]):
    """从 chunks 生成 convergence.csv"""
    sample_sizes = []

    # 找到所有 chunk 文件
    chunk_files = sorted(chunks_dir.glob('n*.csv'))
    for cf in chunk_files:
        # 从文件名提取样本量
        n = int(cf.stem[1:])
        sample_sizes.append(n)

    sample_sizes.sort()

    if not sample_sizes:
        print("错误: 没有找到 chunk 文件")
        return

    # 读取所有数据
    all_data = {}
    for n in sample_sizes:
        chunk_path = chunks_dir / f'n{n}.csv'
        with open(chunk_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            all_data[n] = rows

    # 生成 convergence.csv
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # 表头
        header = ['sample_size', 'mc_runs',
                  'beta_mean', 'beta_median', 'beta_std',
                  'eta_mean', 'eta_median', 'eta_std',
                  'gamma_mean', 'gamma_median', 'gamma_std']
        writer.writerow(header)

        for n in sample_sizes:
            rows = all_data[n]

            for mc in mc_runs_list:
                # 筛选前 mc 次仿真
                subset = rows[:mc]

                # 提取有效值
                beta_vals = []
                eta_vals = []
                gamma_vals = []

                for row in subset:
                    try:
                        if row['est_beta'] and row['est_beta'] != 'NaN':
                            beta_vals.append(float(row['est_beta']))
                            eta_vals.append(float(row['est_eta']))
                            gamma_vals.append(float(row['est_gamma']))
                    except:
                        pass

                if beta_vals:
                    beta_arr = np.array(beta_vals)
                    eta_arr = np.array(eta_vals)
                    gamma_arr = np.array(gamma_vals)

                    row = [
                        n, mc,
                        f'{np.mean(beta_arr):.16f}', f'{np.median(beta_arr):.16f}', f'{np.std(beta_arr):.16f}',
                        f'{np.mean(eta_arr):.16f}', f'{np.median(eta_arr):.16f}', f'{np.std(eta_arr):.16f}',
                        f'{np.mean(gamma_arr):.16f}', f'{np.median(gamma_arr):.16f}', f'{np.std(gamma_arr):.16f}'
                    ]
                else:
                    row = [n, mc, 'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN', 'NaN']

                writer.writerow(row)

    print(f"生成 convergence.csv: {output_path}")


def main():
    parser = argparse.ArgumentParser(description='MLE 示例2 数据生成脚本')
    parser.add_argument('--only', nargs='+', type=int, help='只生成指定样本量')
    parser.add_argument('--force', '-f', action='store_true', help='强制重新生成')
    parser.add_argument('--verbose', '-v', action='store_true', help='详细输出')
    parser.add_argument('--convergence-only', action='store_true', help='只生成 convergence.csv')

    args = parser.parse_args()

    # 定位配置文件
    config_path = PROJECT_ROOT / 'public' / 'studies' / 'mle' / 'demo2' / 'config.md'
    output_dir = config_path.parent / 'chunks'
    output_dir.mkdir(exist_ok=True)

    if not config_path.exists():
        print(f"错误: 配置文件不存在 - {config_path}")
        sys.exit(1)

    # 解析配置
    config = parse_config(str(config_path))

    # 获取固定参数
    defaults = config.get('defaults', {})
    fixed_params = {
        'beta': defaults.get('beta', 2.0),
        'eta': defaults.get('eta', 1000),
        'gamma': defaults.get('gamma', 1000)
    }

    # 获取样本量列表
    sample_size_param = next((p for p in config.get('params', []) if p['id'] == 'sampleSize'), None)
    if not sample_size_param:
        print("错误: 配置中未找到 sampleSize 参数")
        sys.exit(1)

    sample_sizes = [int(v) for v in sample_size_param.get('discreteValues', [])]

    # 仿真次数
    mc_runs = config.get('simulation', {}).get('maxMcRuns', 5000)
    mc_runs_list = config.get('simulation', {}).get('mcRunsList', [1000, 2000, 3000, 4000, 5000])

    # 只生成 convergence.csv
    if args.convergence_only:
        generate_convergence_csv(output_dir, config_path.parent / 'convergence.csv', mc_runs_list)
        return

    # 筛选要生成的样本量
    if args.only:
        to_generate = [n for n in sample_sizes if n in args.only]
    elif args.force:
        to_generate = sample_sizes
    else:
        # 增量模式：跳过已存在的文件
        to_generate = []
        for n in sample_sizes:
            output_path = output_dir / f'n{n}.csv'
            if not output_path.exists():
                to_generate.append(n)

    if not to_generate:
        print("所有分片已存在，无需生成")
    else:
        print("=" * 60)
        print(f"MLE 示例2 数据生成")
        print(f"固定参数: β={fixed_params['beta']}, η={fixed_params['eta']}, γ={fixed_params['gamma']}")
        print(f"样本量: {to_generate}")
        print(f"每组仿真次数: {mc_runs}")
        print("=" * 60)

        # 生成数据
        results = []
        for i, n in enumerate(to_generate):
            output_path = output_dir / f'n{n}.csv'
            print(f"\n[{i+1}/{len(to_generate)}] 生成 n={n} ...")

            result = generate_chunk(
                sample_size=n,
                fixed_params=fixed_params,
                mc_runs=mc_runs,
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

    # 生成 convergence.csv
    print("\n生成 convergence.csv ...")
    generate_convergence_csv(output_dir, config_path.parent / 'convergence.csv', mc_runs_list)
    print("完成！")


if __name__ == '__main__':
    main()
