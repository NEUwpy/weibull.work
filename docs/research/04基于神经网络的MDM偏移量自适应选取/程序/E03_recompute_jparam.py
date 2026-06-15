"""
用 J_param 重算 E03-2 层级最优 和 E03-3 L5 Oracle
J_param = √( mean( ((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/η)² ) )
"""
import sys
sys.path.insert(0, "D:/weibull/python")
import numpy as np
import csv
import os
import pandas as pd

datadir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"
eta_true = 1.0
deltas = np.arange(0, 0.52, 0.02)

# ============================================================
# 1. 从原始分片CSV算每个 (beta,n,ger,delta) 的 J_param
# ============================================================
print("计算各配置×各δ的 J_param ...")

config_jparam = {}  # (beta, n, ger, delta) -> J_param

for beta in [2.0, 2.5, 4.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            gamma_true = ger * eta_true
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            fpath = os.path.join(datadir, fname)
            
            # 按delta分组
            delta_data = {}
            with open(fpath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    d = row['delta']
                    if d not in delta_data:
                        delta_data[d] = {'bh': [], 'eh': [], 'gh': []}
                    if row['beta_hat']:
                        delta_data[d]['bh'].append(float(row['beta_hat']))
                        delta_data[d]['eh'].append(float(row['eta_hat']))
                        delta_data[d]['gh'].append(float(row['gamma_hat']))
            
            for d in deltas:
                ds = f"{d:.2f}"
                if ds not in delta_data:
                    continue
                dd = delta_data[ds]
                bh = np.array(dd['bh'])
                eh = np.array(dd['eh'])
                gh = np.array(dd['gh'])
                
                if len(bh) == 0:
                    continue
                
                # J_param = √( mean( ((β̂-β)/β)² + ((η̂-η)/η)² + ((γ̂-γ)/η)² ) )
                term_beta = ((bh - beta) / beta) ** 2
                term_eta = ((eh - eta_true) / eta_true) ** 2
                term_gamma = ((gh - gamma_true) / eta_true) ** 2
                jparam = np.sqrt(np.mean(term_beta + term_eta + term_gamma))
                
                config_jparam[(beta, n, ger, float(ds))] = jparam

# ============================================================
# 2. E03-2 层级最优（用 J_param）
# ============================================================
print("计算 L0~L4 层级最优 ...")

optimal_rows = []

# L0 全局
for d in deltas:
    vals = [config_jparam.get((b, n, g, d), np.nan) 
            for b in [2.0, 2.5, 4.0] for n in [7, 10, 20] for g in [0.1, 0.5, 1.0]]
    vals = [v for v in vals if not np.isnan(v)]
    if vals:
        optimal_rows.append({'level': 'L0', 'group': 'global', 'delta': d, 'jparam': np.mean(vals)})

# L1 按 n
for n in [7, 10, 20]:
    for d in deltas:
        vals = [config_jparam.get((b, n, g, d), np.nan) 
                for b in [2.0, 2.5, 4.0] for g in [0.1, 0.5, 1.0]]
        vals = [v for v in vals if not np.isnan(v)]
        if vals:
            optimal_rows.append({'level': 'L1', 'group': f'n={n}', 'delta': d, 'jparam': np.mean(vals)})

# L2 按 β
for beta in [2.0, 2.5, 4.0]:
    for d in deltas:
        vals = [config_jparam.get((beta, n, g, d), np.nan) 
                for n in [7, 10, 20] for g in [0.1, 0.5, 1.0]]
        vals = [v for v in vals if not np.isnan(v)]
        if vals:
            optimal_rows.append({'level': 'L2', 'group': f'beta={beta}', 'delta': d, 'jparam': np.mean(vals)})

# L3 按 (β, n)
for beta in [2.0, 2.5, 4.0]:
    for n in [7, 10, 20]:
        for d in deltas:
            vals = [config_jparam.get((beta, n, g, d), np.nan) for g in [0.1, 0.5, 1.0]]
            vals = [v for v in vals if not np.isnan(v)]
            if vals:
                optimal_rows.append({'level': 'L3', 'group': f'beta={beta}_n={n}', 'delta': d, 'jparam': np.mean(vals)})

# L4 按 (β, n, γ/η)
for beta in [2.0, 2.5, 4.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            for d in deltas:
                v = config_jparam.get((beta, n, ger, d))
                if v is not None and not np.isnan(v):
                    optimal_rows.append({'level': 'L4', 'group': f'beta={beta}_n={n}_g={ger}', 
                                         'delta': d, 'jparam': v})

res_df = pd.DataFrame(optimal_rows)

# 找最优
opt_result = []
for (level, group), gdf in res_df.groupby(['level', 'group']):
    best_idx = gdf['jparam'].idxmin()
    best = gdf.loc[best_idx]
    opt_result.append({
        'level': level, 'group': group,
        'optimal_delta': best['delta'], 'jparam': best['jparam']
    })
opt_jparam = pd.DataFrame(opt_result)

opt_jparam.to_csv(os.path.join(datadir, "E03-2_level_optimal_jparam.csv"), index=False)
print(f"E03-2 已保存 ({len(opt_jparam)} 行)")

# 打印
for level in ['L0', 'L1', 'L2', 'L3', 'L4']:
    sub = opt_jparam[opt_jparam['level'] == level].sort_values('group')
    print(f"\n--- {level} ---")
    for _, row in sub.iterrows():
        print(f"  {row['group']:30s}  δ*={row['optimal_delta']:.2f}  J_param={row['jparam']:.4f}")

# ============================================================
# 3. E03-3 L5 Oracle（用 J_param）
# ============================================================
print("\n\n计算 L5 Oracle J_param ...")

oracle_rows = []
for beta in [2.0, 2.5, 4.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            gamma_true = ger * eta_true
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            fpath = os.path.join(datadir, fname)
            
            data = {}
            with open(fpath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['beta_hat']:
                        key = (row['delta'], int(row['rep']))
                        data[key] = (float(row['beta_hat']), float(row['eta_hat']), float(row['gamma_hat']))
            
            for rep in range(500):
                best_delta = None
                best_jparam = float('inf')
                
                for d in deltas:
                    ds = f"{d:.2f}"
                    key = (ds, rep)
                    if key not in data:
                        continue
                    bh, eh, gh = data[key]
                    jparam = np.sqrt(((bh - beta)/beta)**2 + ((eh - eta_true)/eta_true)**2 + ((gh - gamma_true)/eta_true)**2)
                    if jparam < best_jparam:
                        best_jparam = jparam
                        best_delta = d
                
                if best_delta is not None:
                    key = (f"{best_delta:.2f}", rep)
                    bh, eh, gh = data[key]
                    oracle_rows.append({
                        'beta': beta, 'n': n, 'gamma_eta': ger, 'rep': rep,
                        'optimal_delta': best_delta, 'jparam': best_jparam,
                        'beta_hat': bh, 'eta_hat': eh, 'gamma_hat': gh,
                    })

oracle_df = pd.DataFrame(oracle_rows)
oracle_df.to_csv(os.path.join(datadir, "E03-3_L5_oracle_jparam.csv"), index=False)

# 按配置汇总
print("\n--- L5 Oracle 汇总 ---")
for beta in [2.0, 2.5, 4.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            sub = oracle_df[(oracle_df['beta'] == beta) & (oracle_df['n'] == n) & (oracle_df['gamma_eta'] == ger)]
            print(f"β={beta}, n={n}, γ/η={ger}:  J_param={sub['jparam'].mean():.4f}  δ*={sub['optimal_delta'].mean():.3f}")

print(f"\nL5 Oracle 已保存 ({len(oracle_df)} 行)")
print("\n全部完成。")
