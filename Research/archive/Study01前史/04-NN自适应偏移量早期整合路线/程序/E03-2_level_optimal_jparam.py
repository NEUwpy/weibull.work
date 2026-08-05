"""
E03-2 层级最优 δ（J_param 版本）
从 E03-3_jparam_by_config.csv 计算 L0~L4 各层级的最优 δ*
最优定义：J_param 最小
"""
import sys
sys.path.insert(0, "D:/weibull/python")
import numpy as np
import pandas as pd
import os
import re

datadir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"

df = pd.read_csv(os.path.join(datadir, "E03-3_jparam_by_config.csv"))

results = []

# --- L0 全局 ---
for delta in df['delta'].unique():
    sub = df[df['delta'] == delta]
    results.append({'level': 'L0', 'group': 'global', 'delta': delta,
                    'jparam': sub['jparam'].mean()})

# --- L1 按 n ---
for n in sorted(df['n'].unique()):
    for delta in df['delta'].unique():
        sub = df[(df['n'] == n) & (df['delta'] == delta)]
        results.append({'level': 'L1', 'group': f'n={n}', 'delta': delta,
                        'jparam': sub['jparam'].mean()})

# --- L2 按 β ---
for beta in sorted(df['beta'].unique()):
    for delta in df['delta'].unique():
        sub = df[(df['beta'] == beta) & (df['delta'] == delta)]
        results.append({'level': 'L2', 'group': f'beta={beta}', 'delta': delta,
                        'jparam': sub['jparam'].mean()})

# --- L3 按 (β, n) ---
for beta in sorted(df['beta'].unique()):
    for n in sorted(df['n'].unique()):
        for delta in df['delta'].unique():
            sub = df[(df['beta'] == beta) & (df['n'] == n) & (df['delta'] == delta)]
            results.append({'level': 'L3', 'group': f'beta={beta}_n={n}', 'delta': delta,
                            'jparam': sub['jparam'].mean()})

# --- L4 按 (β, n, γ/η) ---
for beta in sorted(df['beta'].unique()):
    for n in sorted(df['n'].unique()):
        for ger in sorted(df['gamma_eta'].unique()):
            for delta in df['delta'].unique():
                sub = df[(df['beta'] == beta) & (df['n'] == n) & 
                         (df['gamma_eta'] == ger) & (df['delta'] == delta)]
                results.append({'level': 'L4', 'group': f'beta={beta}_n={n}_g={ger}', 
                                'delta': delta, 'jparam': sub['jparam'].mean()})

res_df = pd.DataFrame(results)

# 找各层级各组的最优 δ*
optimal_rows = []
for (level, group), gdf in res_df.groupby(['level', 'group']):
    best_idx = gdf['jparam'].idxmin()
    best = gdf.loc[best_idx]
    optimal_rows.append({
        'level': level,
        'group': group,
        'optimal_delta': best['delta'],
        'jparam': best['jparam'],
    })

opt_df = pd.DataFrame(optimal_rows)

# 保存
opt_df.to_csv(os.path.join(datadir, "E03-2_level_optimal_jparam.csv"), index=False)
res_df.to_csv(os.path.join(datadir, "E03-2_level_scan_jparam.csv"), index=False)

# 打印
print("=" * 60)
print("E03-2 层级最优 δ*（J_param 口径）")
print("=" * 60)

for level in ['L0', 'L1', 'L2', 'L3', 'L4']:
    sub = opt_df[opt_df['level'] == level].sort_values('group')
    print(f"\n--- {level} ---")
    for _, row in sub.iterrows():
        print(f"  {row['group']:30s}  δ*={row['optimal_delta']:.2f}  J_param={row['jparam']:.4f}")

print(f"\n保存: {os.path.join(datadir, 'E03-2_level_optimal_jparam.csv')}")
