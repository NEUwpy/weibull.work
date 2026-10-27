"""
示例2: 蒙特卡洛收敛性研究

生成用于示例2的模拟数据。

数据结构：
- 每个样本量 n 运行 5000 次仿真
- 按 [1000, 2000, 3000, 4000, 5000] 切片统计
- 收敛曲线：步长100，共51个点
- 保存到 chunks/n{sample_size}.csv 和 convergence.csv

"""

import sys
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

import pandas as pd

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM


from scipy import stats


def generate_weibull_sample(beta: float, eta: float, gamma: float, n: int, seed: int) -> np.ndarray:
    """生成三参数威布尔分布样本"""
    rng = np.random.Random(seed)
    u = rng.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)


def calculate_stats(values: List[float], true_value: float) -> dict:
    """计算统计量"""
    if len(values) == 0:
        return {}
    arr = np.array(values)
    sorted_vals = np.sort(arr)
    n = len(arr)
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))
    median = float(np.median(arr))
    q025 = np.percentile(arr, 2.5)
    q975 = np.percentile(arr, 97.5)
    return {
        'count': n,
        'mean': mean,
        'median': median,
        'std': std,
        'min': float(np.min(arr)),
        'max': float(np.max(arr)),
        'q025': q025,
        'q975': q975,
        'bias_mean': mean - true_value,
        'abs_bias_mean': abs(mean - true_value)
    }


def run_single_mdm_estimation(sample: np.ndarray, offset: float = 0.1, gamma_steps: int = 60) -> dict:
    """运行单次MDM估计"""
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=True, offset=offset, gamma_steps=gamma_steps, rank_method='bernard')
        if result[4] == "no_intersection":
            return {'status': 'no_intersection', 'est_beta': None, 'est_eta': None, 'est_gamma': None}
        est_beta, est_eta, est_gamma, r2, status = result
        return {
            'status': 'success',
            'est_beta': float(est_beta),
            'est_eta': float(est_eta),
            'est_gamma': float(est_gamma),
            'r_squared': float(r2)
        }
    except Exception as e:
        return {'status': 'error', 'error': str(e), 'est_beta': None, 'est_eta': None, 'est_gamma': None}


def run_simulation(
    beta: float,
    eta: float,
    gamma: float,
    sample_size: int,
    offset: float,
    mc_runs: int,
    base_seed: int = 42
) -> list:
    """运行模拟并收集所有估计值"""
    all_estimates = []
    for sim_id in range(1, mc_runs + 1):
        seed = base_seed + sim_id + sample_size * 1000 + int(beta * 1000) + int(eta)
        sample = generate_weibull_sample(beta, eta, gamma, sample_size, seed)
        result = run_single_mdm_estimation(sample, offset)
        all_estimates.append({
            'sim_id': sim_id,
            'status': result['status'],
            'est_beta': result.get('est_beta'),
            'est_eta': result.get('est_eta'),
            'est_gamma': result.get('est_gamma'),
            'bias_beta': result.get('est_beta') - beta if result.get('est_beta') else None,
            'bias_eta': result.get('est_eta') - eta if result.get('est_eta') else None,
            'bias_gamma': result.get('est_gamma') - gamma if result.get('est_gamma') else None,
            'r_squared': result.get('r_squared')
        })
    return all_estimates


def calculate_slice_statistics(
    all_estimates: List[dict],
    mc_runs_list: List[int],
    true_beta: float,
    true_eta: float,
    true_gamma: float
) -> Dict[int, dict]:
    """
    按不同重复次数切片计算统计量
    返回: {mc_runs: {beta, eta, gamma 各参数的统计量}}
    """
    slice_stats = {}
    for mc in mc_runs_list:
        # 取前 mc 个估计值
        slice_data = all_estimates[:mc]
        # 过滤有效估计
        valid_betas = [e['est_beta'] for e in slice_data if e['status'] == 'success' and e['est_beta'] is not None]
        valid_etas = [e['est_eta'] for e in slice_data if e['status'] == 'success' and e['est_eta'] is not None]
        valid_gammas = [e['est_gamma'] for e in slice_data if e['status'] == 'success' and e['est_gamma'] is not None]
        no_solution_count = len([e for e in slice_data if e['status'] != 'success'])
        slice_stats[mc] = {
            'beta': calculate_stats(valid_betas, true_beta),
            'eta': calculate_stats(valid_etas, true_eta),
            'gamma': calculate_stats(valid_gammas, true_gamma),
            'valid_count': len(valid_betas),
            'no_solution_count': no_solution_count,
            'no_solution_rate': no_solution_count / mc * 100 if mc > 0 else 0
        }
    return slice_stats


def main():
    """主函数 - 生成示例2数据"""
    # 固定参数
    beta = 2.0
    eta = 1000
    gamma = 1000
    offset = 0.1
    gamma_steps = 60

    # 样本量列表
    sample_sizes = [3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 30]
    # 收敛曲线用的重复次数列表（步长100）
    convergence_mc_list = list(range(100, 5001, 100))  # [100, 200, ..., 5000]
    # 筛选显示用的重复次数列表
    mc_runs_list = [1000, 2000, 3000, 4000, 5000]
    max_mc_runs = 5000
    base_seed = 42

    # 输出目录
    output_dir = PROJECT_ROOT / 'public' / 'studies' / 'mdm' / 'demo2'
    chunks_dir = output_dir / 'chunks'
    output_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("示例2: 蒙特卡洛收敛性研究 - 数据生成")
    print("=" * 60)
    print(f"固定参数: β={beta}, η={eta}, γ={gamma}, δ={offset}")
    print(f"样本量列表: {sample_sizes}")
    print(f"重复次数切片: {mc_runs_list}")
    print(f"收敛曲线步长: 100 (共{len(convergence_mc_list)}个点)")
    print(f"最大模拟次数: {max_mc_runs}")

    # 数据结构
    data = {
        'config': {
            'fixed_params': {'beta': beta, 'eta': eta, 'gamma': gamma, 'offset': offset},
            'sample_sizes': sample_sizes,
            'mc_runs_list': mc_runs_list,
            'calculation': {'gamma_steps': gamma_steps, 'rank_method': 'bernard'}
        },
        'results': {}  # {sample_size: {mc_runs: slice_stats}}
    }

    # 收敛曲线数据
    convergence_data = []

    # 对每个样本量运行模拟
    for n in sample_sizes:
        print(f"\n处理样本量 n={n}...")

        # 运行最大模拟次数
        all_estimates = run_simulation(
            beta=beta,
            eta=eta,
            gamma=gamma,
            sample_size=n,
            offset=offset,
            mc_runs=max_mc_runs,
            base_seed=base_seed
        )

        # 保存原始数据到 chunk 文件
        chunk_df = pd.DataFrame(all_estimates)
        chunk_path = chunks_dir / f'n{n}.csv'
        chunk_df.to_csv(chunk_path, index=False)
        print(f"  保存: {chunk_path}")

        # 计算不同重复次数切片的统计量（用于筛选显示）
        slice_stats = calculate_slice_statistics(
            all_estimates=all_estimates,
            mc_runs_list=mc_runs_list,
            true_beta=beta,
            true_eta=eta,
            true_gamma=gamma
        )

        # 保存到数据结构
        data['results'][str(n)] = slice_stats

        # 计算收敛曲线数据（步长100）
        print(f"  计算收敛曲线...")
        for mc in convergence_mc_list:
            slice_data = all_estimates[:mc]
            valid_betas = [e['est_beta'] for e in slice_data if e['status'] == 'success' and e['est_beta'] is not None]
            valid_etas = [e['est_eta'] for e in slice_data if e['status'] == 'success' and e['est_eta'] is not None]
            valid_gammas = [e['est_gamma'] for e in slice_data if e['status'] == 'success' and e['est_gamma'] is not None]

            beta_stats = calculate_stats(valid_betas, beta)
            eta_stats = calculate_stats(valid_etas, eta)
            gamma_stats = calculate_stats(valid_gammas, gamma)

            convergence_data.append({
                'sample_size': n,
                'mc_runs': mc,
                'beta_mean': beta_stats.get('mean'),
                'beta_median': beta_stats.get('median'),
                'beta_std': beta_stats.get('std'),
                'eta_mean': eta_stats.get('mean'),
                'eta_median': eta_stats.get('median'),
                'eta_std': eta_stats.get('std'),
                'gamma_mean': gamma_stats.get('mean'),
                'gamma_median': gamma_stats.get('median'),
                'gamma_std': gamma_stats.get('std')
            })

        print(f"  完成 n={n}, 有效估计: {len([e for e in all_estimates if e['status'] == 'success'])}/{max_mc_runs}")

    # 保存数据
    data_path = output_dir / 'data.json'
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"\n数据已保存: {data_path}")

    # 保存收敛曲线数据为CSV
    convergence_df = pd.DataFrame(convergence_data)
    convergence_path = output_dir / 'convergence.csv'
    convergence_df.to_csv(convergence_path, index=False)
    print(f"收敛曲线数据已保存: {convergence_path}")

    # 生成汇总报告
    summary = {
        'title': '示例2: 蒙特卡洛收敛性研究',
        'generated_at': datetime.now().isoformat(),
        'fixed_params': {'beta': beta, 'eta': eta, 'gamma': gamma, 'offset': offset},
        'sample_sizes': {}
    }

    for n in sample_sizes:
        results = data['results'][str(n)]
        summary['sample_sizes'][str(n)] = {
            'mc_5000': {
                'valid_rate': results[5000]['beta']['count'] / max_mc_runs * 100,
                'beta_mean': results[5000]['beta'].get('mean'),
                'beta_std': results[5000]['beta'].get('std'),
                'no_solution_rate': results[5000].get('no_solution_rate', 0)
            }
        }

    summary_path = output_dir / 'summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"汇总报告已保存: {summary_path}")

    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
