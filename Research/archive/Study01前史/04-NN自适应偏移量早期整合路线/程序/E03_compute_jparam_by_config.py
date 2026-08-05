"""
生成 E03-3_jparam_by_config.csv：每个 (beta, n, gamma_eta, delta) 的 J_param
从27个分片CSV直接计算
"""
import sys
sys.path.insert(0, "D:/weibull/python")
import numpy as np
import csv
import os

datadir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"
eta_true = 1.0
deltas = np.arange(0, 0.52, 0.02)

rows = []

for beta in [1.5, 2.0, 2.5, 4.0, 5.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            gamma_true = ger * eta_true
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            fpath = os.path.join(datadir, fname)
            
            # 按 delta 分组
            delta_data = {}
            with open(fpath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    d = row['delta']
                    if d not in delta_data:
                        delta_data[d] = []
                    if row['beta_hat']:
                        delta_data[d].append((
                            float(row['beta_hat']),
                            float(row['eta_hat']),
                            float(row['gamma_hat']),
                        ))
            
            for d in deltas:
                ds = f"{d:.2f}"
                if ds not in delta_data:
                    continue
                data = delta_data[ds]
                if len(data) < 2:
                    continue
                
                bhs = np.array([x[0] for x in data])
                ehs = np.array([x[1] for x in data])
                ghs = np.array([x[2] for x in data])
                
                jparam = np.sqrt(
                    np.mean(((bhs - beta) / beta)**2) +
                    np.mean(((ehs - eta_true) / eta_true)**2) +
                    np.mean(((ghs - gamma_true) / eta_true)**2)
                )
                
                rows.append({
                    'beta': beta,
                    'n': n,
                    'gamma_eta': ger,
                    'delta': d,
                    'jparam': jparam,
                    'n_valid': len(data),
                })

out_path = os.path.join(datadir, "E03-3_jparam_by_config.csv")
with open(out_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=['beta', 'n', 'gamma_eta', 'delta', 'jparam', 'n_valid'])
    writer.writeheader()
    writer.writerows(rows)

print(f"已保存: {out_path} ({len(rows)} 行)")

# 验证：L0 全局最优 δ
import pandas as pd
df = pd.DataFrame(rows)
print("\n各 δ 下全部配置的平均 J_param:")
for d in [0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12, 0.14, 0.20, 0.30]:
    sub = df[abs(df['delta'] - d) < 0.001]
    if len(sub) > 0:
        print(f"  δ={d:.2f}:  全局={sub['jparam'].mean():.4f}  "
              f"n=7={sub[sub['n']==7]['jparam'].mean():.4f}  "
              f"n=10={sub[sub['n']==10]['jparam'].mean():.4f}  "
              f"n=20={sub[sub['n']==20]['jparam'].mean():.4f}")
