"""
E03-3 L5 Oracle：逐样本最优 δ
在所有配置上，对每个样本扫描 26 个 δ，找使复合指标最小的 δ*
"""
import sys
sys.path.insert(0, "D:/weibull/python")

import numpy as np
import csv
import os

datadir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"
eta_true = 1.0
n_reps = 500
deltas = np.arange(0, 0.52, 0.02)

oracle_rows = []

for beta in [2.0, 2.5, 4.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            gamma_true = ger * eta_true
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            fpath = os.path.join(datadir, fname)
            
            # 按 (delta, rep) 组织数据
            data = {}
            with open(fpath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['beta_hat']:
                        key = (row['delta'], int(row['rep']))
                        data[key] = (float(row['beta_hat']), float(row['eta_hat']), float(row['gamma_hat']))
            
            # 对每个 rep，找最优 δ
            for rep in range(n_reps):
                best_delta = None
                best_composite = float('inf')
                
                for d in deltas:
                    d_str = f"{d:.2f}"
                    key = (d_str, rep)
                    if key not in data:
                        continue
                    bh, eh, gh = data[key]
                    composite = abs(bh - beta) + abs(gh - gamma_true) + abs(eh - eta_true)
                    if composite < best_composite:
                        best_composite = composite
                        best_delta = d
                
                if best_delta is not None:
                    key = (f"{best_delta:.2f}", rep)
                    bh, eh, gh = data[key]
                    oracle_rows.append({
                        'beta': beta,
                        'n': n,
                        'gamma_eta': ger,
                        'rep': rep,
                        'optimal_delta': best_delta,
                        'composite': best_composite,
                        'beta_hat': bh,
                        'eta_hat': eh,
                        'gamma_hat': gh,
                        'bias_beta': bh - beta,
                        'bias_eta': eh - eta_true,
                        'bias_gamma': gh - gamma_true,
                    })

# 保存
out_path = os.path.join(datadir, "E03-3_L5_oracle.csv")
with open(out_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'beta', 'n', 'gamma_eta', 'rep', 'optimal_delta', 'composite',
        'beta_hat', 'eta_hat', 'gamma_hat', 'bias_beta', 'bias_eta', 'bias_gamma'
    ])
    writer.writeheader()
    writer.writerows(oracle_rows)

# 汇总统计
import pandas as pd
df = pd.DataFrame(oracle_rows)

print("=" * 60)
print("E03-3 L5 Oracle 结果（逐样本最优 δ*）")
print("=" * 60)

for beta in [2.0, 2.5, 4.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            sub = df[(df['beta'] == beta) & (df['n'] == n) & (df['gamma_eta'] == ger)]
            print(f"β={beta}, n={n}, γ/η={ger}:  "
                  f"δ*均值={sub['optimal_delta'].mean():.3f}±{sub['optimal_delta'].std():.3f}  "
                  f"复合={sub['composite'].mean():.4f}  "
                  f"Bias(β̂)={sub['bias_beta'].mean():+.4f}  "
                  f"Bias(γ̂)={sub['bias_gamma'].mean():+.4f}  "
                  f"Bias(η̂)={sub['bias_eta'].mean():+.4f}")

print(f"\n总行数: {len(oracle_rows)}")
print(f"保存: {out_path}")
