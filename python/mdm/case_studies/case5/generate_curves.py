"""
⚠ 历史复现实验，不是当前默认 MDM 口径

使用现有MDM方法生成案例5的梯度曲线数据

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

print("使用现有MDM方法生成梯度曲线数据...")

all_curve_data = []

for idx, row in df_samples.iterrows():
    sample_id = row['id']
    data = row[['v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7']].values.astype(float)
    data = np.round(data, 1)  # 四舍五入到1位小数

    print(f"处理 {sample_id}...")

    # 创建MDM实例并运行
    mdm = MDM(data)
    beta, eta, gamma, r2, converged = mdm.run(trace=True, offset=0.1)

    if converged and mdm.trace_data:
        # 提取梯度曲线数据
        trace = mdm.trace_data
        grad_gamma_curve = trace.get('grad_gamma_curve', [])

        all_curve_data.append({
            'sample_id': sample_id,
            'grad_gamma_curve': grad_gamma_curve,
            'est_beta': beta,
            'est_eta': eta,
            'est_gamma': gamma
        })

# 保存为JSON
with open('../public/cases/mdm_case5_curves.json', 'w') as f:
    json.dump({'samples': all_curve_data}, f, indent=2)

print(f"\n梯度曲线数据已保存到 mdm_case5_curves.json")
print(f"成功处理样本数: {len(all_curve_data)}")

# 打印第一个样本的曲线数据作为验证
if all_curve_data:
    print(f"\n第一个样本 {all_curve_data[0]['sample_id']} 的梯度曲线数据（前5点）:")
    for i, point in enumerate(all_curve_data[0]['grad_gamma_curve'][:5]):
        print(f"  γ={point.get('gamma', 'N/A'):.4f}, 梯度={point.get('gradient', 'N/A'):.6f}")
