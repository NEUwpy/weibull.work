"""
案例15: WMLE 权重 Monte Carlo 验证

研究内容:
- 复现 Cousineau (2009) 论文的 Monte Carlo 方法
- 计算 W1, W2, W3 的统计量 (均值 E, 中位数 J, 几何均值 G)
- 验证 n=1-16 时与论文表格的一致性
- 扩展 n 到 30
- 形状参数 γ = 2.0

论文方法:
- 将 W1, W2, W3 公式中的 log(1/(1-F(x_i))) 替换为标准指数分布随机变量 z_i
- 重复 2^20 次模拟
- 取所有结果的均值、中位数、几何均值

权重公式:
- W1 = (1/n) * sum(z_i)
- W2 = sum(z_i * log(z_i)) / sum(z_i) - (1/n) * sum(log(z_i))
- W3 = W1 * sum(z_i^(-1/γ)) / sum(z_i^((γ-1)/γ))

输出:
- public/case-studies/mdm/case15/data.json
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

import json
import numpy as np
from typing import Dict, List, Any
import time

# 模拟参数
N_SIMULATIONS = 2**20  # 约 100 万次，与论文一致
SAMPLE_SIZES = list(range(1, 31))  # n 从 1 到 30
GAMMA_VALUES = [2.0]  # 形状参数 (论文符号 γ，代码中为 beta)

# 随机种子
SEED = 42

# 论文参考值 (Cousineau 2009, Tables 2-4, γ=2.0)
PAPER_VALUES = {
    "J1": {
        1: 0.693, 2: 0.839, 3: 0.891, 4: 0.918, 5: 0.934,
        6: 0.945, 7: 0.953, 8: 0.959, 9: 0.963, 10: 0.967,
        11: 0.970, 12: 0.972, 13: 0.974, 14: 0.976, 15: 0.978,
        16: 0.979
    },
    "J2": {
        1: 0.000, 2: 0.275, 3: 0.517, 4: 0.638, 5: 0.711,
        6: 0.759, 7: 0.791, 8: 0.817, 9: 0.838, 10: 0.853,
        11: 0.867, 12: 0.877, 13: 0.886, 14: 0.895, 15: 0.902,
        16: 0.908
    },
    "J3": {  # γ=2.0
        1: 0.995, 2: 1.339, 3: 1.479, 4: 1.567, 5: 1.625,
        6: 1.669, 7: 1.698, 8: 1.722, 9: 1.739, 10: 1.758,
        11: 1.774, 12: 1.782, 13: 1.793, 14: 1.804, 15: 1.813,
        16: 1.820
    },
    "G1": {
        1: 0.561, 2: 0.763, 3: 0.839, 4: 0.878, 5: 0.902,
        6: 0.918, 7: 0.929, 8: 0.938, 9: 0.945, 10: 0.950,
        11: 0.955, 12: 0.959, 13: 0.962, 14: 0.965, 15: 0.967,
        16: 0.969
    },
    "G2": {
        1: 0.000, 2: 0.163, 3: 0.409, 4: 0.553, 5: 0.642,
        6: 0.702, 7: 0.742, 8: 0.775, 9: 0.800, 10: 0.820,
        11: 0.835, 12: 0.849, 13: 0.860, 14: 0.871, 15: 0.879,
        16: 0.887
    },
    "G3": {  # γ=2.0
        1: 1.006, 2: 1.360, 3: 1.520, 4: 1.603, 5: 1.665,
        6: 1.704, 7: 1.740, 8: 1.766, 9: 1.778, 10: 1.800,
        11: 1.817, 12: 1.829, 13: 1.839, 14: 1.842, 15: 1.854,
        16: 1.862
    },
    "E1": {  # 均值恒为 1
        n: 1.0 for n in range(1, 17)
    },
    "E2": {  # 均值 = 1 - 1/n
        n: 1 - 1/n for n in range(1, 17)
    },
}


def compute_weights_monte_carlo(n: int, gamma: float, rng: np.random.Generator, n_sims: int = N_SIMULATIONS) -> Dict[str, float]:
    """
    使用 Monte Carlo 模拟计算 W1, W2, W3 的统计量

    Args:
        n: 样本量
        gamma: 形状参数 (论文符号 γ)
        rng: 随机数生成器
        n_sims: 模拟次数

    Returns:
        dict: 包含 E(均值), G(几何均值), J(中位数) 的字典
    """
    # 预分配数组
    w1_values = np.zeros(n_sims)
    w2_values = np.zeros(n_sims)
    w3_values = np.zeros(n_sims)

    for i in range(n_sims):
        # 从标准指数分布采样 n 个值
        z = rng.exponential(1.0, n)

        # W1 = (1/n) * sum(z_i)
        w1 = np.mean(z)

        # W2 = sum(z * log(z)) / sum(z) - (1/n) * sum(log(z))
        log_z = np.log(z)
        # 处理 z=0 的情况 (理论上指数分布不会产生 0，但数值上可能出现极小值)
        log_z = np.where(z > 1e-300, log_z, -300)
        w2 = np.sum(z * log_z) / np.sum(z) - np.mean(log_z)

        # W3 = W1 * sum(z^(-1/γ)) / sum(z^((γ-1)/γ))
        exp1 = -1.0 / gamma
        exp2 = (gamma - 1.0) / gamma
        w3 = w1 * np.sum(z ** exp1) / np.sum(z ** exp2)

        w1_values[i] = w1
        w2_values[i] = w2
        w3_values[i] = w3

    # 计算统计量
    results = {}

    # W1 的统计量
    results['E1'] = float(np.mean(w1_values))
    results['J1'] = float(np.median(w1_values))
    # 几何均值: exp(mean(log(values)))
    # 过滤掉负值和零值 (W1 应该都是正的)
    valid_w1 = w1_values[w1_values > 0]
    results['G1'] = float(np.exp(np.mean(np.log(valid_w1)))) if len(valid_w1) > 0 else 0.0

    # W2 的统计量
    results['E2'] = float(np.mean(w2_values))
    results['J2'] = float(np.median(w2_values))
    # W2 可能有负值，需要特殊处理
    valid_w2 = w2_values[w2_values > 0]
    if len(valid_w2) > 0:
        results['G2'] = float(np.exp(np.mean(np.log(valid_w2))))
    else:
        results['G2'] = 0.0

    # W3 的统计量
    results['E3'] = float(np.mean(w3_values))
    results['J3'] = float(np.median(w3_values))
    valid_w3 = w3_values[w3_values > 0]
    results['G3'] = float(np.exp(np.mean(np.log(valid_w3)))) if len(valid_w3) > 0 else 0.0

    return results


def get_current_code_weights(n: int, gamma: float) -> Dict[str, float]:
    """
    获取当前代码实现中的权重值
    参考: python/methods/wmle.py
    """
    from scipy.special import digamma

    # W1 (J1): 查表或使用 exp(digamma(n))/n
    WEIGHT_TABLE_J1 = {
        1: 0.693, 2: 0.839, 3: 0.891, 4: 0.918, 5: 0.934,
        6: 0.945, 7: 0.953, 8: 0.959, 9: 0.963, 10: 0.967,
        11: 0.970, 12: 0.972, 13: 0.974, 14: 0.976, 15: 0.978,
        16: 0.979, 20: 0.985, 32: 0.991, 50: 0.994, 100: 0.997
    }

    # W2 (J2): 查表或使用 1 - 1/n
    WEIGHT_TABLE_J2 = {
        1: 0.000, 2: 0.275, 3: 0.517, 4: 0.638, 5: 0.711,
        6: 0.759, 7: 0.791, 8: 0.817, 9: 0.838, 10: 0.853,
        11: 0.867, 12: 0.877, 13: 0.886, 14: 0.895, 15: 0.902,
        16: 0.908, 20: 0.925, 32: 0.947, 50: 0.963, 100: 0.978
    }

    def get_weight_j1(n: int) -> float:
        if n in WEIGHT_TABLE_J1:
            return WEIGHT_TABLE_J1[n]
        if n < 1:
            return 0.5
        if n > 100:
            return 1.0
        return np.exp(digamma(n)) / n

    def get_weight_j2(n: int) -> float:
        if n in WEIGHT_TABLE_J2:
            return WEIGHT_TABLE_J2[n]
        if n < 2:
            return 0.0
        return max(0.0, min(1.0, 1.0 - 1.0/n))

    def get_weight_j3(n: int, gamma: float) -> float:
        if gamma <= 1:
            return 1.5 + 0.5 * np.log10(n)
        mle_weight = gamma / (gamma - 1)
        correction = max(0.1, 0.3 * np.exp(-n/10))
        return mle_weight * (1 - correction)

    return {
        'J1': get_weight_j1(n),
        'J2': get_weight_j2(n),
        'J3': get_weight_j3(n, gamma),
    }


def main():
    print("=" * 70)
    print("案例15: WMLE 权重 Monte Carlo 验证")
    print(f"模拟次数: {N_SIMULATIONS:,} 次/n")
    print(f"样本量范围: n = 1 到 {SAMPLE_SIZES[-1]}")
    print(f"形状参数: γ = {GAMMA_VALUES}")
    print("=" * 70)

    # 初始化随机数生成器
    rng = np.random.default_rng(SEED)

    all_results = []

    start_time = time.time()

    for gamma in GAMMA_VALUES:
        gamma_results = {
            'gamma': gamma,
            'n_simulations': N_SIMULATIONS,
            'weights': []
        }

        for n in SAMPLE_SIZES:
            print(f"\n计算 n={n}, γ={gamma}...")

            step_start = time.time()

            # Monte Carlo 模拟
            mc_results = compute_weights_monte_carlo(n, gamma, rng)

            # 当前代码实现
            code_weights = get_current_code_weights(n, gamma)

            # 论文参考值
            paper_weights = {
                'J1': PAPER_VALUES['J1'].get(n),
                'J2': PAPER_VALUES['J2'].get(n),
                'J3': PAPER_VALUES['J3'].get(n),
                'G1': PAPER_VALUES['G1'].get(n),
                'G2': PAPER_VALUES['G2'].get(n),
                'G3': PAPER_VALUES['G3'].get(n),
                'E1': PAPER_VALUES['E1'].get(n),
                'E2': PAPER_VALUES['E2'].get(n),
            }

            step_time = time.time() - step_start

            result = {
                'n': n,
                'monte_carlo': mc_results,
                'code': code_weights,
                'paper': paper_weights,
                'errors': {
                    'J1_mc_vs_paper': None if paper_weights['J1'] is None else (mc_results['J1'] - paper_weights['J1']) / paper_weights['J1'] * 100,
                    'J2_mc_vs_paper': None if paper_weights['J2'] is None else (mc_results['J2'] - paper_weights['J2']) / paper_weights['J2'] * 100 if paper_weights['J2'] != 0 else None,
                    'J3_mc_vs_paper': None if paper_weights['J3'] is None else (mc_results['J3'] - paper_weights['J3']) / paper_weights['J3'] * 100,
                    'J1_code_vs_paper': None if paper_weights['J1'] is None else (code_weights['J1'] - paper_weights['J1']) / paper_weights['J1'] * 100,
                    'J2_code_vs_paper': None if paper_weights['J2'] is None else (code_weights['J2'] - paper_weights['J2']) / paper_weights['J2'] * 100 if paper_weights['J2'] != 0 else None,
                    'J3_code_vs_paper': None if paper_weights['J3'] is None else (code_weights['J3'] - paper_weights['J3']) / paper_weights['J3'] * 100,
                    'J3_code_vs_mc': (code_weights['J3'] - mc_results['J3']) / mc_results['J3'] * 100,
                }
            }

            gamma_results['weights'].append(result)

            # 打印进度
            if paper_weights['J3'] is not None:
                print(f"  J3: MC={mc_results['J3']:.4f}, Paper={paper_weights['J3']:.4f}, Code={code_weights['J3']:.4f}")
                print(f"  J3 误差: MC vs Paper={result['errors']['J3_mc_vs_paper']:.2f}%, Code vs Paper={result['errors']['J3_code_vs_paper']:.2f}%")
            else:
                print(f"  J3: MC={mc_results['J3']:.4f}, Code={code_weights['J3']:.4f}")

            print(f"  耗时: {step_time:.1f}s")

        all_results.append(gamma_results)

    total_time = time.time() - start_time
    print(f"\n总耗时: {total_time/60:.1f} 分钟")

    # 构建输出数据
    output_data = {
        'simulation_params': {
            'n_simulations': N_SIMULATIONS,
            'sample_sizes': SAMPLE_SIZES,
            'gamma_values': GAMMA_VALUES,
            'seed': SEED,
        },
        'paper_values': PAPER_VALUES,
        'results': all_results,
    }

    # 保存结果
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.normpath(os.path.join(script_dir, "..", "..", "..", ".."))
    output_path = os.path.join(project_root, "public", "case-studies", "mdm", "case15", "data.json")
    print(f"\n输出路径: {output_path}")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"结果已保存到: {output_path}")

    # 打印汇总表
    print("\n" + "=" * 120)
    print("汇总表 (γ=2.0)")
    print("=" * 120)

    print(f"\n{'n':<4} {'J1_MC':<10} {'J1_Paper':<10} {'J1_Err%':<10} {'J2_MC':<10} {'J2_Paper':<10} {'J2_Err%':<10} {'J3_MC':<10} {'J3_Paper':<10} {'J3_Err%':<10}")
    print("-" * 120)

    for result in all_results[0]['weights']:
        n = result['n']
        mc = result['monte_carlo']
        paper = result['paper']
        err = result['errors']

        j1_paper_str = f"{paper['J1']:.3f}" if paper['J1'] is not None else "-"
        j2_paper_str = f"{paper['J2']:.3f}" if paper['J2'] is not None else "-"
        j3_paper_str = f"{paper['J3']:.3f}" if paper['J3'] is not None else "-"

        j1_err_str = f"{err['J1_mc_vs_paper']:.2f}" if err['J1_mc_vs_paper'] is not None else "-"
        j2_err_str = f"{err['J2_mc_vs_paper']:.2f}" if err['J2_mc_vs_paper'] is not None else "-"
        j3_err_str = f"{err['J3_mc_vs_paper']:.2f}" if err['J3_mc_vs_paper'] is not None else "-"

        print(f"{n:<4} {mc['J1']:<10.4f} {j1_paper_str:<10} {j1_err_str:<10} {mc['J2']:<10.4f} {j2_paper_str:<10} {j2_err_str:<10} {mc['J3']:<10.4f} {j3_paper_str:<10} {j3_err_str:<10}")


if __name__ == "__main__":
    main()
