"""
E03-2 层级最优 δ 计算
从 E03-1 汇总数据计算 L0~L4 各层级的最优 δ*
最优目标：复合指标 = |Bias(β̂)| + |Bias(γ̂)| + |Bias(η̂)|
"""
import sys
sys.path.insert(0, "D:/weibull/python")

import numpy as np
import pandas as pd
import csv
import os

# 读取汇总数据
datadir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"
summary_path = os.path.join(datadir, "E03-3_summary.csv")
df = pd.read_csv(summary_path)

# 计算复合指标（η=1.0，所以不除η不影响）
df['composite'] = df['bias_beta'].abs() + df['bias_gamma'].abs() + df['bias_eta'].abs()

# 各配置的真实值
df['gamma_true'] = df['gamma_eta'] * 1.0  # η=1.0

# ============================================================
# 层级最优计算
# ============================================================

results = []

# --- L0 全局：所有配置共用一个 δ* ---
for delta in df['delta'].unique():
    sub = df[df['delta'] == delta]
    results.append({
        'level': 'L0', 'group': 'global',
        'delta': delta,
        'mean_composite': sub['composite'].mean(),
        'mean_bias_beta': sub['bias_beta'].mean(),
        'mean_bias_gamma': sub['bias_gamma'].mean(),
        'mean_bias_eta': sub['bias_eta'].mean(),
        'mean_sd_beta': sub['sd_beta'].mean(),
        'mean_sd_gamma': sub['sd_gamma'].mean(),
        'mean_sd_eta': sub['sd_eta'].mean(),
    })

# --- L1 按 n ---
for n in sorted(df['n'].unique()):
    for delta in df['delta'].unique():
        sub = df[(df['n'] == n) & (df['delta'] == delta)]
        results.append({
            'level': 'L1', 'group': f'n={n}',
            'delta': delta,
            'mean_composite': sub['composite'].mean(),
            'mean_bias_beta': sub['bias_beta'].mean(),
            'mean_bias_gamma': sub['bias_gamma'].mean(),
            'mean_bias_eta': sub['bias_eta'].mean(),
            'mean_sd_beta': sub['sd_beta'].mean(),
            'mean_sd_gamma': sub['sd_gamma'].mean(),
            'mean_sd_eta': sub['sd_eta'].mean(),
        })

# --- L2 按 β ---
for beta in sorted(df['beta'].unique()):
    for delta in df['delta'].unique():
        sub = df[(df['beta'] == beta) & (df['delta'] == delta)]
        results.append({
            'level': 'L2', 'group': f'beta={beta}',
            'delta': delta,
            'mean_composite': sub['composite'].mean(),
            'mean_bias_beta': sub['bias_beta'].mean(),
            'mean_bias_gamma': sub['bias_gamma'].mean(),
            'mean_bias_eta': sub['bias_eta'].mean(),
            'mean_sd_beta': sub['sd_beta'].mean(),
            'mean_sd_gamma': sub['sd_gamma'].mean(),
            'mean_sd_eta': sub['sd_eta'].mean(),
        })

# --- L3 按 (β, n) ---
for beta in sorted(df['beta'].unique()):
    for n in sorted(df['n'].unique()):
        for delta in df['delta'].unique():
            sub = df[(df['beta'] == beta) & (df['n'] == n) & (df['delta'] == delta)]
            results.append({
                'level': 'L3', 'group': f'beta={beta}_n={n}',
                'delta': delta,
                'mean_composite': sub['composite'].mean(),
                'mean_bias_beta': sub['bias_beta'].mean(),
                'mean_bias_gamma': sub['bias_gamma'].mean(),
                'mean_bias_eta': sub['bias_eta'].mean(),
                'mean_sd_beta': sub['sd_beta'].mean(),
                'mean_sd_gamma': sub['sd_gamma'].mean(),
                'mean_sd_eta': sub['sd_eta'].mean(),
            })

# --- L4 按 (β, n, γ/η) ---
for beta in sorted(df['beta'].unique()):
    for n in sorted(df['n'].unique()):
        for ger in sorted(df['gamma_eta'].unique()):
            for delta in df['delta'].unique():
                sub = df[(df['beta'] == beta) & (df['n'] == n) & 
                         (df['gamma_eta'] == ger) & (df['delta'] == delta)]
                results.append({
                    'level': 'L4', 'group': f'beta={beta}_n={n}_g={ger}',
                    'delta': delta,
                    'mean_composite': sub['composite'].mean(),
                    'mean_bias_beta': sub['bias_beta'].mean(),
                    'mean_bias_gamma': sub['bias_gamma'].mean(),
                    'mean_bias_eta': sub['bias_eta'].mean(),
                    'mean_sd_beta': sub['sd_beta'].mean(),
                    'mean_sd_gamma': sub['sd_gamma'].mean(),
                    'mean_sd_eta': sub['sd_eta'].mean(),
                })

res_df = pd.DataFrame(results)

# ============================================================
# 找各层级各组的最优 δ*
# ============================================================

optimal_rows = []
for (level, group), gdf in res_df.groupby(['level', 'group']):
    best_idx = gdf['mean_composite'].idxmin()
    best = gdf.loc[best_idx]
    optimal_rows.append({
        'level': level,
        'group': group,
        'optimal_delta': best['delta'],
        'composite': best['mean_composite'],
        'bias_beta': best['mean_bias_beta'],
        'bias_gamma': best['mean_bias_gamma'],
        'bias_eta': best['mean_bias_eta'],
        'sd_beta': best['mean_sd_beta'],
        'sd_gamma': best['mean_sd_gamma'],
        'sd_eta': best['mean_sd_eta'],
    })

opt_df = pd.DataFrame(optimal_rows)

# 保存
out_path = os.path.join(datadir, "E03-2_level_optimal.csv")
opt_df.to_csv(out_path, index=False)

# 同时保存完整扫描（供画图用）
full_path = os.path.join(datadir, "E03-2_level_scan.csv")
res_df.to_csv(full_path, index=False)

# ============================================================
# 打印结果
# ============================================================

print("=" * 70)
print("E03-2 层级最优 δ* 结果")
print("最优定义：复合指标 = |Bias(β̂)| + |Bias(γ̂)| + |Bias(η̂)| 最小")
print("=" * 70)

for level in ['L0', 'L1', 'L2', 'L3', 'L4']:
    sub = opt_df[opt_df['level'] == level].sort_values('group')
    print(f"\n--- {level} ---")
    for _, row in sub.iterrows():
        print(f"  {row['group']:30s}  δ*={row['optimal_delta']:.2f}  "
              f"复合={row['composite']:.4f}  "
              f"Bias(β̂)={row['bias_beta']:+.4f}  "
              f"Bias(γ̂)={row['bias_gamma']:+.4f}  "
              f"Bias(η̂)={row['bias_eta']:+.4f}")

print(f"\n结果已保存: {out_path}")
print(f"完整扫描已保存: {full_path}")
