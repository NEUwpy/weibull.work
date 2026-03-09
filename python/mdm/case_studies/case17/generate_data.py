"""
案例17: 小样本估计的统计陷阱

研究 MDM 方法在 n=3 时估计偏差反而小于大样本的现象。

研究问题:
1. 增加模拟次数是否会消除偶然性?
2. 无解率是否导致幸存者偏差?
3. 为什么会无解?

使用方法:
    cd python/mdm/case_studies/case17
    python generate_data.py

输出:
    - data.json: 完整数据
    - summary.json: 汇总统计
"""

import sys
import json
import numpy as np
from pathlib import Path
from typing import List, Dict, Any, Optional

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))

from methods.mdm import MDM


def generate_weibull_sample(beta: float, eta: float, gamma: float, n: int, seed: int) -> np.ndarray:
    """生成三参数威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)


def extract_trace_for_charts(trace_data: dict) -> dict:
    """
    从 trace_data 提取用于绘制 SigmaBetaChart 和 GradientGammaChart 的数据

    返回:
        {
            'sigma_beta_curves': [{gamma, betas, sigmas}, ...],
            'gradient_gamma_curve': [{gamma, gradient}, ...]
        }
    """
    if not trace_data:
        return None

    result = {
        'sigma_beta_curves': [],
        'gradient_gamma_curve': []
    }

    # 提取 sigma_beta 数据（每个 gamma 对应一条曲线）
    if 'sigma_beta_data' in trace_data:
        for item in trace_data['sigma_beta_data']:
            curve = {
                'gamma': float(item.get('gamma', 0)),
                'betas': [float(b) for b in item.get('betas', [])],
                'sigmas': [float(s) for s in item.get('sigmas', [])]
            }
            result['sigma_beta_curves'].append(curve)

    # 提取 gradient_gamma 数据
    if 'gradient_data' in trace_data:
        for item in trace_data['gradient_data']:
            point = {
                'gamma': float(item.get('gamma', 0)),
                'gradient': float(item.get('gradient', 0))
            }
            result['gradient_gamma_curve'].append(point)

    return result


def run_mdm_estimation(sample: np.ndarray, offset: float, gamma_steps: int = 60):
    """
    运行 MDM 估计
    返回: dict 包含估计结果和详细信息
    """
    try:
        algo = MDM(sample.tolist(), rank_method='bernard')
        result = algo.run(trace=True, offset=offset, gamma_steps=gamma_steps, rank_method='bernard')

        if result[4] == "no_intersection":
            # 获取 trace_data 用于分析无解原因
            trace_data = algo.trace_data if hasattr(algo, 'trace_data') else None
            chart_data = extract_trace_for_charts(trace_data)
            return {
                'status': 'no_intersection',
                'est_beta': None,
                'est_eta': None,
                'est_gamma': None,
                'r_squared': None,
                'trace_data': trace_data,
                'chart_data': chart_data
            }

        est_beta, est_eta, est_gamma, r2, status = result
        trace_data = algo.trace_data if hasattr(algo, 'trace_data') else None
        chart_data = extract_trace_for_charts(trace_data)

        return {
            'status': 'success',
            'est_beta': float(est_beta),
            'est_eta': float(est_eta),
            'est_gamma': float(est_gamma),
            'r_squared': float(r2),
            'trace_data': trace_data,
            'chart_data': chart_data
        }
    except Exception as e:
        return {
            'status': 'error',
            'error': str(e),
            'est_beta': None,
            'est_eta': None,
            'est_gamma': None,
            'r_squared': None,
            'trace_data': None,
            'chart_data': None
        }


def run_simulation(
    beta: float,
    eta: float,
    gamma: float,
    sample_size: int,
    offset: float,
    mc_runs: int,
    base_seed: int = 0,
    max_no_solution_samples: int = 5
) -> Dict[str, Any]:
    """运行单组模拟"""
    results = []
    no_solution_samples = []  # 保存无解样本的详细信息
    all_estimates = {  # 保存所有估计值用于分布图
        'beta': [],
        'eta': [],
        'gamma': []
    }

    for sim_id in range(1, mc_runs + 1):
        seed = base_seed + sim_id + int(beta * 1000) + int(eta) + sample_size * 1000 + int(offset * 1000)

        # 生成样本
        sample = generate_weibull_sample(beta, eta, gamma, sample_size, seed)

        # MDM 估计
        result = run_mdm_estimation(sample, offset)
        result['sim_id'] = sim_id
        result['seed'] = seed
        result['sample_min'] = float(sample[0])
        result['sample_max'] = float(sample[-1])
        result['sample_mean'] = float(np.mean(sample))

        # 计算偏差
        if result['status'] == 'success':
            result['bias_beta'] = result['est_beta'] - beta
            result['bias_eta'] = result['est_eta'] - eta
            result['bias_gamma'] = result['est_gamma'] - gamma
            result['abs_bias_beta'] = abs(result['bias_beta'])

            # 收集估计值
            all_estimates['beta'].append(result['est_beta'])
            all_estimates['eta'].append(result['est_eta'])
            all_estimates['gamma'].append(result['est_gamma'])
        else:
            result['bias_beta'] = None
            result['bias_eta'] = None
            result['bias_gamma'] = None
            result['abs_bias_beta'] = None

            # 收集无解样本（限制数量）
            if result['status'] == 'no_intersection' and len(no_solution_samples) < max_no_solution_samples:
                no_solution_samples.append({
                    'sim_id': sim_id,
                    'seed': seed,
                    'sample': sample.tolist(),
                    'sample_min': result['sample_min'],
                    'sample_max': result['sample_max'],
                    'chart_data': result.get('chart_data')
                })

        results.append(result)

    # 计算统计量
    valid_results = [r for r in results if r['status'] == 'success']
    no_solution_count = len([r for r in results if r['status'] == 'no_intersection'])

    stats = {
        'total_runs': mc_runs,
        'valid_count': len(valid_results),
        'no_solution_count': no_solution_count,
        'no_solution_rate': no_solution_count / mc_runs * 100 if mc_runs > 0 else 0,
    }

    if valid_results:
        est_betas = [r['est_beta'] for r in valid_results]
        est_etas = [r['est_eta'] for r in valid_results]
        est_gammas = [r['est_gamma'] for r in valid_results]
        bias_betas = [r['bias_beta'] for r in valid_results]

        stats.update({
            'est_beta_mean': float(np.mean(est_betas)),
            'est_beta_std': float(np.std(est_betas, ddof=1)),
            'est_beta_median': float(np.median(est_betas)),
            'est_eta_mean': float(np.mean(est_etas)),
            'est_eta_std': float(np.std(est_etas, ddof=1)),
            'est_gamma_mean': float(np.mean(est_gammas)),
            'est_gamma_std': float(np.std(est_gammas, ddof=1)),
            'bias_beta_mean': float(np.mean(bias_betas)),
            'bias_beta_std': float(np.std(bias_betas, ddof=1)),
            'abs_bias_beta_mean': float(np.mean([abs(b) for b in bias_betas])),
        })
    else:
        stats.update({
            'est_beta_mean': None,
            'est_beta_std': None,
            'est_beta_median': None,
            'est_eta_mean': None,
            'est_eta_std': None,
            'est_gamma_mean': None,
            'est_gamma_std': None,
            'bias_beta_mean': None,
            'bias_beta_std': None,
            'abs_bias_beta_mean': None,
        })

    return {
        'params': {
            'beta': beta,
            'eta': eta,
            'gamma': gamma,
            'sample_size': sample_size,
            'offset': offset,
            'mc_runs': mc_runs
        },
        'stats': stats,
        'all_estimates': all_estimates,  # 新增：所有估计值
        'no_solution_samples': no_solution_samples,  # 新增：无解样本详情
        'results': results
    }


def main():
    # 输出目录
    output_dir = PROJECT_ROOT / 'public' / 'case-studies' / 'mdm' / 'case17'
    output_dir.mkdir(parents=True, exist_ok=True)

    # 固定参数
    gamma = 1000

    # 重点研究的参数组合: β=2, η=1000, γ=1000
    target_combos = [
        {'beta': 2.0, 'eta': 1000, 'offset': 0.1, 'desc': '主要研究条件'},
    ]

    # 样本量列表
    sample_sizes = [3, 5, 7, 10, 20, 30]

    # 模拟次数列表
    mc_runs_list = [1000, 2000, 3000, 5000]

    # 收集所有数据
    all_data = {
        'config': {
            'gamma': gamma,
            'sample_sizes': sample_sizes,
            'mc_runs_list': mc_runs_list,
            'target_combos': target_combos
        },
        'combinations': []
    }

    print("=" * 60)
    print("案例17: 小样本估计的统计陷阱 - 数据生成")
    print("=" * 60)

    for combo in target_combos:
        beta = combo['beta']
        eta = combo['eta']
        offset = combo['offset']
        desc = combo['desc']

        print(f"\n参数组合: β={beta}, η={eta}, δ={offset} ({desc})")

        combo_data = {
            'beta': beta,
            'eta': eta,
            'offset': offset,
            'description': desc,
            'gamma': gamma,
            'by_mc_runs': {},
            'by_sample_size': {}
        }

        for mc_runs in mc_runs_list:
            print(f"  模拟次数: {mc_runs}")

            mc_data = {
                'mc_runs': mc_runs,
                'by_sample_size': {}
            }

            for n in sample_sizes:
                print(f"    n={n}...", end=' ', flush=True)

                result = run_simulation(
                    beta=beta,
                    eta=eta,
                    gamma=gamma,
                    sample_size=n,
                    offset=offset,
                    mc_runs=mc_runs,
                    base_seed=42,
                    max_no_solution_samples=5
                )

                mc_data['by_sample_size'][str(n)] = {
                    'stats': result['stats'],
                    'all_estimates': result['all_estimates'],
                    'no_solution_samples': result['no_solution_samples']
                }

                print(f"无解率={result['stats']['no_solution_rate']:.1f}%, "
                      f"偏差均值={result['stats'].get('bias_beta_mean', 'N/A')}")

            combo_data['by_mc_runs'][str(mc_runs)] = mc_data

        # 生成按样本量汇总的对比数据（使用最大模拟次数）
        combo_data['by_sample_size'] = combo_data['by_mc_runs'][str(max(mc_runs_list))]['by_sample_size']

        all_data['combinations'].append(combo_data)

    # 保存完整数据
    data_path = output_dir / 'data.json'
    with open(data_path, 'w', encoding='utf-8') as f:
        json.dump(all_data, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n完整数据已保存: {data_path}")

    # 生成汇总报告
    summary = generate_summary(all_data)
    summary_path = output_dir / 'summary.json'
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"汇总报告已保存: {summary_path}")

    # 打印关键发现
    print("\n" + "=" * 60)
    print("关键发现")
    print("=" * 60)

    for combo in all_data['combinations']:
        print(f"\nβ={combo['beta']}, η={combo['eta']}, δ={combo['offset']} ({combo['description']})")

        for mc_runs in mc_runs_list:
            mc_data = combo['by_mc_runs'][str(mc_runs)]
            n3_stats = mc_data['by_sample_size']['3']['stats']
            n30_stats = mc_data['by_sample_size']['30']['stats']

            n3_bias = n3_stats.get('abs_bias_beta_mean', float('inf')) or float('inf')
            n30_bias = n30_stats.get('abs_bias_beta_mean', float('inf')) or float('inf')

            flag = "✓ n=3更小" if n3_bias < n30_bias else "  n=30更小"

            print(f"  mc={mc_runs}: n=3偏差={n3_bias:.4f}, n=30偏差={n30_bias:.4f} {flag}")


def generate_summary(all_data: Dict) -> Dict:
    """生成汇总报告"""
    summary = {
        'title': '案例17: 小样本估计的统计陷阱',
        'findings': [],
        'conclusions': []
    }

    for combo in all_data['combinations']:
        finding = {
            'params': f"β={combo['beta']}, η={combo['eta']}, δ={combo['offset']}",
            'description': combo['description'],
            'mc_runs_comparison': []
        }

        # 对比不同模拟次数下的结果
        for mc_runs in all_data['config']['mc_runs_list']:
            mc_data = combo['by_mc_runs'][str(mc_runs)]

            comparison = {'mc_runs': mc_runs, 'sample_sizes': []}

            for n in all_data['config']['sample_sizes']:
                stats = mc_data['by_sample_size'][str(n)]['stats']
                comparison['sample_sizes'].append({
                    'n': n,
                    'bias_beta_mean': stats.get('bias_beta_mean'),
                    'abs_bias_beta_mean': stats.get('abs_bias_beta_mean'),
                    'est_beta_std': stats.get('est_beta_std'),
                    'no_solution_rate': stats.get('no_solution_rate')
                })

            finding['mc_runs_comparison'].append(comparison)

        summary['findings'].append(finding)

    return summary


if __name__ == '__main__':
    main()
