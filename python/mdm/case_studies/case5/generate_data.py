"""
⚠ 历史复现实验，不是当前默认 MDM 口径

使用现有MDM方法重新生成案例5的统计数据

S4.9 后默认 MDM 已重写（几何加密网格+约束边界规则），本脚本仅用于历史案例复现。
"""

import sys
import numpy as np
sys.path.insert(0, '.')
from methods.mdm import MDM
import pandas as pd
import json

# 读取样本数据
df_samples = pd.read_csv('../public/cases/mdm_case5.csv')

print("使用现有MDM方法重新生成统计数据...")

all_results = []

for idx, row in df_samples.iterrows():
    sample_id = row['id']
    data = row[['v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7']].values.astype(float)
    data = np.round(data, 1)  # 四舍五入到1位小数

    print(f"处理 {sample_id}...")

    # 创建MDM实例并运行
    mdm = MDM(data)
    beta, eta, gamma, r2, converged = mdm.run(trace=False, offset=0.1)

    if converged:
        all_results.append({
            'sample_id': sample_id,
            'est_beta': beta,
            'est_eta': eta,
            'est_gamma': gamma,
            'bias_beta': beta - 2.0,  # 真实β=2
            'bias_eta': eta - 1000.0,  # 真实η=1000
            'bias_gamma': gamma - 1000.0  # 真实γ=1000
        })

# 保存结果
results_df = pd.DataFrame(all_results)
results_df.to_csv('../public/cases/mdm_case5_results.csv', index=False)

# 计算统计摘要（包含范围）
summary = {
    'n_samples': len(all_results),
    'true_params': {
        'beta': 2.0,
        'eta': 1000.0,
        'gamma': 1000.0
    },
    'estimates': {
        'beta_mean': float(results_df['est_beta'].mean()),
        'beta_std': float(results_df['est_beta'].std()),
        'beta_min': float(results_df['est_beta'].min()),
        'beta_max': float(results_df['est_beta'].max()),
        'eta_mean': float(results_df['est_eta'].mean()),
        'eta_std': float(results_df['est_eta'].std()),
        'eta_min': float(results_df['est_eta'].min()),
        'eta_max': float(results_df['est_eta'].max()),
        'gamma_mean': float(results_df['est_gamma'].mean()),
        'gamma_std': float(results_df['est_gamma'].std()),
        'gamma_min': float(results_df['est_gamma'].min()),
        'gamma_max': float(results_df['est_gamma'].max())
    },
    'bias': {
        'beta_mean': float(results_df['bias_beta'].mean()),
        'beta_std': float(results_df['bias_beta'].std()),
        'beta_min': float(results_df['bias_beta'].min()),
        'beta_max': float(results_df['bias_beta'].max()),
        'eta_mean': float(results_df['bias_eta'].mean()),
        'eta_std': float(results_df['bias_eta'].std()),
        'eta_min': float(results_df['bias_eta'].min()),
        'eta_max': float(results_df['bias_eta'].max()),
        'gamma_mean': float(results_df['bias_gamma'].mean()),
        'gamma_std': float(results_df['bias_gamma'].std()),
        'gamma_min': float(results_df['bias_gamma'].min()),
        'gamma_max': float(results_df['bias_gamma'].max())
    }
}

with open('../public/cases/mdm_case5_summary.json', 'w') as f:
    json.dump(summary, f, indent=2)

print(f"\n结果已保存到 mdm_case5_results.csv")
print(f"统计摘要已保存到 mdm_case5_summary.json")
print(f"\n成功处理样本数: {len(all_results)}")
print(f"\n偏差统计:")
print(f"  β 偏差均值: {summary['bias']['beta_mean']:.4f} ± {summary['bias']['beta_std']:.4f}")
print(f"  η 偏差均值: {summary['bias']['eta_mean']:.2f} ± {summary['bias']['eta_std']:.2f}")
print(f"  γ 偏差均值: {summary['bias']['gamma_mean']:.2f} ± {summary['bias']['gamma_std']:.2f}")

# 打印前5行结果验证
print(f"\n前5个样本结果:")
print(results_df.head(5).to_string(index=False))
