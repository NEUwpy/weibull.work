"""
E03-4a MDM自迭代方案验证
流程：默认δ=0.1 → MDM估计β̂ → 查δ*(n, β̂) → MDM再估计 → 直到收敛
直接复用E03-3分片数据，不需要重新运行MDM
"""
import sys
import numpy as np
import pandas as pd
import os

# 路径设置
BASE_DIR = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE_DIR, "实验数据")
OUT_DIR = os.path.join(BASE_DIR, "实验数据")

# 加载L3层级最优δ*表
l3_df = pd.read_csv(os.path.join(DATA_DIR, "E03-2_level_optimal_jparam.csv"))
l3_df = l3_df[l3_df['level'] == 'L3'].copy()

def parse_l3_group(group_str):
    parts = group_str.split('_')
    beta = float(parts[0].split('=')[1])
    n = int(parts[1].split('=')[1])
    return beta, n

l3_lookup = {}
for _, row in l3_df.iterrows():
    beta, n = parse_l3_group(row['group'])
    l3_lookup[(n, beta)] = row['optimal_delta']

print("L3查找表 (n, β) → δ*:")
for (n, beta), delta in sorted(l3_lookup.items()):
    print(f"  n={n}, β={beta} → δ*={delta}")

BETA_VALUES = [2.0, 2.5, 4.0]
DELTA_VALUES = np.arange(0, 0.52, 0.02)

def nearest_beta(beta_hat):
    return min(BETA_VALUES, key=lambda b: abs(b - beta_hat))

def nearest_delta(delta_star):
    return min(DELTA_VALUES, key=lambda d: abs(d - delta_star))

def compute_jparam(beta_hats, eta_hats, gamma_hats, beta_true, eta_true, gamma_true):
    """
    正确公式: J_param = √( mean( ((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/η)² ) )
    """
    if len(beta_hats) == 0:
        return np.nan, 0
    term_beta = ((beta_hats - beta_true) / beta_true) ** 2
    term_eta = ((eta_hats - eta_true) / eta_true) ** 2
    term_gamma = ((gamma_hats - gamma_true) / eta_true) ** 2
    jparam = np.sqrt(np.mean(term_beta + term_eta + term_gamma))
    return jparam, len(beta_hats)

print("\n加载E03-3分片数据...")

betas = [2.0, 2.5, 4.0]
ns = [7, 10, 20]
gamma_eta_ratios = [0.1, 0.5, 1.0]
ETA_TRUE = 1.0

all_data = {}
for beta in betas:
    for n in ns:
        for ger in gamma_eta_ratios:
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            fpath = os.path.join(DATA_DIR, fname)
            df = pd.read_csv(fpath)
            all_data[(beta, n, ger)] = df
            print(f"  加载 {fname}: {len(df)} 行")

def self_iterate(df, n, beta_true, gamma_true, max_iter=5):
    delta_current = 0.10
    trajectory = []
    visited_deltas = set()

    for iteration in range(max_iter):
        delta_key = round(delta_current, 2)
        delta_rows = df[df['delta'] == delta_key]
        if len(delta_rows) == 0:
            break
        valid_rows = delta_rows[delta_rows['status'] == True]
        if len(valid_rows) == 0:
            break
        beta_hats = valid_rows['beta_hat'].values
        eta_hats = valid_rows['eta_hat'].values
        gamma_hats = valid_rows['gamma_hat'].values
        beta_hat_mean = np.mean(beta_hats)
        jparam, n_valid = compute_jparam(beta_hats, eta_hats, gamma_hats,
                                         beta_true, ETA_TRUE, gamma_true)
        trajectory.append({
            'iteration': iteration, 'delta': delta_key,
            'beta_hat_mean': beta_hat_mean, 'jparam': jparam,
            'n_valid': n_valid
        })
        beta_near = nearest_beta(beta_hat_mean)
        key = (n, beta_near)
        if key not in l3_lookup:
            break
        delta_new = nearest_delta(l3_lookup[key])
        if delta_new in visited_deltas:
            break
        visited_deltas.add(delta_new)
        delta_current = delta_new

    return trajectory

print("\n执行自迭代验证...")
results = []

for beta in betas:
    for n in ns:
        for ger in gamma_eta_ratios:
            gamma_true = ger * ETA_TRUE
            df = all_data[(beta, n, ger)]

            trajectory = self_iterate(df, n, beta_true=beta, gamma_true=gamma_true)

            # 默认δ=0.1的J_param
            default_rows = df[(df['delta'] == 0.10) & (df['status'] == True)]
            default_vals = default_rows[['beta_hat', 'eta_hat', 'gamma_hat']].values
            jparam_default, _ = compute_jparam(
                default_vals[:, 0], default_vals[:, 1], default_vals[:, 2],
                beta, ETA_TRUE, gamma_true
            )

            jparam_iter = trajectory[-1]['jparam'] if trajectory else np.nan
            final_delta = trajectory[-1]['delta'] if trajectory else np.nan
            n_iter = len(trajectory)

            impr = (jparam_default - jparam_iter) / jparam_default * 100 if not np.isnan(jparam_default) and not np.isnan(jparam_iter) else np.nan

            results.append({
                'beta': beta, 'n': n, 'gamma_eta': ger,
                'jparam_default': jparam_default, 'jparam_iterate': jparam_iter,
                'final_delta': final_delta, 'n_iterations': n_iter,
                'improvement': impr
            })

            print(f"  β={beta}, n={n}, γ/η={ger}: δ=0.1→{final_delta}, "
                  f"J={jparam_default:.4f}→{jparam_iter:.4f}, "
                  f"改善{impr:.1f}%, 迭代{n_iter}次")

results_df = pd.DataFrame(results)
out_path = os.path.join(OUT_DIR, "E03-4a_self_iteration.csv")
results_df.to_csv(out_path, index=False)
print(f"\n结果已保存: {out_path}")

print("\n=== 自迭代方案汇总 ===")
print(f"平均改善: {results_df['improvement'].mean():.2f}%")
print(f"改善为正的比例: {(results_df['improvement'] > 0).mean()*100:.1f}%")
print(f"平均迭代次数: {results_df['n_iterations'].mean():.2f}")
