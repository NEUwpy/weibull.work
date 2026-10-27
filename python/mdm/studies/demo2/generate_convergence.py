"""
示例2: 生成收敛曲线数据

从已有的 chunks/n{n}.csv 文件中读取数据，计算收敛曲线。
X轴步长：100 (0-5000)
"""

import sys
import numpy as np
import pandas as pd
from pathlib import Path
from typing import List

# 添加项目根目录到路径
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / 'python'))


def calculate_stats(values: np.ndarray) -> dict:
    """计算统计量"""
    if len(values) == 0:
        return {'mean': None, 'median': None, 'std': None}
    return {
        'mean': float(np.mean(values)),
        'median': float(np.median(values)),
        'std': float(np.std(values, ddof=1))
    }


def main():
    """主函数 - 从已有数据生成收敛曲线"""
    # 真实参数值
    true_beta = 2.0
    true_eta = 1000
    true_gamma = 1000

    # 样本量列表
    sample_sizes = [3, 4, 5, 6, 7, 8, 9, 10, 15, 20, 30]

    # X轴步长：100
    mc_runs_list = list(range(100, 5001, 100))  # [100, 200, ..., 5000]

    # 输入输出目录
    chunks_dir = PROJECT_ROOT / 'public' / 'studies' / 'mdm' / 'demo2' / 'chunks'
    output_path = PROJECT_ROOT / 'public' / 'studies' / 'mdm' / 'demo2' / 'convergence.csv'

    print("=" * 60)
    print("生成收敛曲线数据")
    print("=" * 60)
    print(f"样本量列表: {sample_sizes}")
    print(f"MC步长: 100 (共{len(mc_runs_list)}个点)")

    # 收敛曲线数据
    convergence_data = []

    for n in sample_sizes:
        print(f"\n处理样本量 n={n}...")

        # 读取已有数据
        chunk_path = chunks_dir / f'n{n}.csv'
        if not chunk_path.exists():
            print(f"  警告: 文件不存在 {chunk_path}")
            continue

        df = pd.read_csv(chunk_path)
        print(f"  读取 {len(df)} 条记录")

        # 对每个MC步长计算统计量
        for mc in mc_runs_list:
            # 取前mc条记录
            subset = df[df['sim_id'] <= mc]

            # 过滤有效估计（非NaN）
            beta_vals = subset['est_beta'].dropna().values
            eta_vals = subset['est_eta'].dropna().values
            gamma_vals = subset['est_gamma'].dropna().values

            beta_stats = calculate_stats(beta_vals)
            eta_stats = calculate_stats(eta_vals)
            gamma_stats = calculate_stats(gamma_vals)

            convergence_data.append({
                'sample_size': n,
                'mc_runs': mc,
                'beta_mean': beta_stats['mean'],
                'beta_median': beta_stats['median'],
                'beta_std': beta_stats['std'],
                'eta_mean': eta_stats['mean'],
                'eta_median': eta_stats['median'],
                'eta_std': eta_stats['std'],
                'gamma_mean': gamma_stats['mean'],
                'gamma_median': gamma_stats['median'],
                'gamma_std': gamma_stats['std']
            })

        print(f"  完成 n={n}")

    # 保存收敛曲线数据
    convergence_df = pd.DataFrame(convergence_data)
    convergence_df.to_csv(output_path, index=False)
    print(f"\n收敛曲线数据已保存: {output_path}")
    print(f"共 {len(convergence_data)} 条记录")

    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)


if __name__ == '__main__':
    main()
