"""
批量生成MDM案例数据的脚本

生成包含所有维度交叉组合的完整CSV文件
"""

import sys
import os
import numpy as np
import csv

# 添加methods目录到路径
sys.path.append(os.path.join(os.path.dirname(__file__), 'methods'))
from mdm import MDM

# MDM 案例1 完整参数配置
TRUE_ETA = 1000      # 真实尺度参数
TRUE_GAMMA = 1000    # 真实位置参数

BETA_VALUES = [1.5, 2.0, 3, 5, 7]      # 形状参数变化
SAMPLE_SIZES = [5, 7, 10, 20, 30]      # 样本量变化
OFFSET_VALUES = [0, 0.05, 0.1, 0.15, 0.2]  # 偏移量变化
NUM_SIMULATIONS = 100

def generate_weibull_sample(beta, eta, gamma, n, seed):
    """生成指定参数的威布尔分布样本"""
    np.random.seed(seed)
    u = np.random.uniform(0, 1, n)
    sample = gamma + eta * (-np.log(1 - u)) ** (1 / beta)
    return np.sort(sample)

def estimate_mdm(sample, offset=None):
    """使用MDM方法估计参数"""
    try:
        algo = MDM(sample.tolist())
        if offset is not None:
            res = algo.run(trace=False, offset=offset)
        else:
            res = algo.run(trace=False)
        return float(res[0]), float(res[1]), float(res[2]), float(res[3])
    except Exception as e:
        print(f"MDM估计失败: {e}")
        return 0, 0, 0, 0

def run_full_simulation():
    """运行所有维度交叉组合的批量模拟"""

    csv_path = os.path.join(os.path.dirname(__file__), '..', 'public', 'cases', 'mdm_case1_full.csv')

    total_combinations = len(BETA_VALUES) * len(SAMPLE_SIZES) * len(OFFSET_VALUES)
    total_rows = total_combinations * NUM_SIMULATIONS

    print("=" * 60)
    print("MDM 案例1 完整数据生成")
    print("=" * 60)
    print(f"形状参数 β: {BETA_VALUES}")
    print(f"样本量 n: {SAMPLE_SIZES}")
    print(f"偏移量 δ: {OFFSET_VALUES}")
    print(f"固定参数: η={TRUE_ETA}, γ={TRUE_GAMMA}")
    print(f"参数组合数: {total_combinations}")
    print(f"每组模拟次数: {NUM_SIMULATIONS}")
    print(f"总数据行数: {total_rows}")
    print("=" * 60)
    print()

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        # Header - 包含所有维度
        writer.writerow([
            'beta_true', 'sample_size', 'offset_value', 'sim_id',
            'est_beta', 'est_eta', 'est_gamma',
            'bias_beta', 'bias_eta', 'bias_gamma',
            'r_squared'
        ])

        completed = 0
        for beta_val in BETA_VALUES:
            for sample_size in SAMPLE_SIZES:
                for offset_val in OFFSET_VALUES:
                    print(f"[{completed+1}/{total_combinations}] β={beta_val}, n={sample_size}, δ={offset_val}...")

                    for sim_id in range(1, NUM_SIMULATIONS + 1):
                        # 生成样本 (seed确保可重复性)
                        seed = sim_id + sample_size * 1000 + int(beta_val * 100) + int(offset_val * 1000)
                        sample = generate_weibull_sample(beta_val, TRUE_ETA, TRUE_GAMMA, sample_size, seed)

                        # MDM估计
                        est_beta, est_eta, est_gamma, r2 = estimate_mdm(sample, offset=offset_val)

                        # 计算偏差
                        bias_beta = est_beta - beta_val
                        bias_eta = est_eta - TRUE_ETA
                        bias_gamma = est_gamma - TRUE_GAMMA

                        writer.writerow([
                            beta_val, sample_size, offset_val, sim_id,
                            f'{est_beta:.6f}', f'{est_eta:.6f}', f'{est_gamma:.6f}',
                            f'{bias_beta:.6f}', f'{bias_eta:.6f}', f'{bias_gamma:.6f}',
                            f'{r2:.6f}'
                        ])

                    completed += 1

    print(f"\n已保存: {csv_path}")
    print(f"文件大小: {os.path.getsize(csv_path) / 1024:.1f} KB")
    print("\n数据生成完成！")

if __name__ == '__main__':
    run_full_simulation()
