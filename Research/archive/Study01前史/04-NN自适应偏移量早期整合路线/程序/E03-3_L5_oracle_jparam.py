"""
E03-3 L5 Oracle：用 J_param 公式计算逐样本最优 δ
J_param = √( mean( ((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/η)² ) )
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

for beta in [1.5, 2.0, 2.5, 4.0, 5.0]:
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
            
            # 对每个 rep，找使 J_param 最小的 δ
            for rep in range(n_reps):
                best_delta = None
                best_jparam = float('inf')
                
                for d in deltas:
                    ds = f"{d:.2f}"
                    key = (ds, rep)
                    if key not in data:
                        continue
                    bh, eh, gh = data[key]
                    # 逐样本 J 的分量（不开根号比较，效果一样）
                    jp_sq = ((bh - beta)/beta)**2 + ((eh - eta_true)/eta_true)**2 + ((gh - gamma_true)/eta_true)**2
                    if jp_sq < best_jparam:
                        best_jparam = jp_sq
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
                        'jparam': np.sqrt(best_jparam),
                        'beta_hat': bh,
                        'eta_hat': eh,
                        'gamma_hat': gh,
                    })

# 保存
out_path = os.path.join(datadir, "E03-3_L5_oracle_jparam.csv")
with open(out_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'beta', 'n', 'gamma_eta', 'rep', 'optimal_delta', 'jparam',
        'beta_hat', 'eta_hat', 'gamma_hat'
    ])
    writer.writeheader()
    writer.writerows(oracle_rows)

# 汇总
import pandas as pd
df = pd.DataFrame(oracle_rows)

print("=" * 60)
print("L5 Oracle J_param 结果")
print("=" * 60)

for n in [7, 10, 20]:
    sub = df[df['n'] == n]
    print(f"n={n}:  J_param均值={sub['jparam'].mean():.4f}  δ*均值={sub['optimal_delta'].mean():.3f}")

print()
for beta in [1.5, 2.0, 2.5, 4.0, 5.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            sub = df[(df['beta'] == beta) & (df['n'] == n) & (df['gamma_eta'] == ger)]
            print(f"β={beta} n={n} γ/η={ger}:  J_param={sub['jparam'].mean():.4f}  δ*={sub['optimal_delta'].mean():.3f}")

print(f"\n总行数: {len(oracle_rows)}")
print(f"保存: {out_path}")
