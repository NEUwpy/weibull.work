"""
E03-4b 外部β预估方案对比
流程：用MLE/LSE先估β̂ → 查δ*(n, β̂) → 用最优δ做MDM估计
复用E03-3分片数据中的MDM结果，不需要重新运行MDM
"""
import sys
import numpy as np
import pandas as pd
import os
import time

PROJ_ROOT = "D:/weibull/python"
BASE_DIR = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取"
DATA_DIR = os.path.join(BASE_DIR, "实验数据")
SCRIPT_DIR = os.path.join(BASE_DIR, "程序")

sys.path.insert(0, PROJ_ROOT)
sys.path.insert(0, os.path.join(PROJ_ROOT, "studies", "common"))
sys.path.insert(0, SCRIPT_DIR)

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from lse_weibull import fit_weibull3_lse

ETA_TRUE = 1.0
BETA_VALUES = [1.5, 2.0, 2.5, 4.0, 5.0]
NS = [7, 10, 20]
GAMMA_ETA_RATIOS = [0.1, 0.5, 1.0]
DELTA_VALUES = np.arange(0, 0.52, 0.02)

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

print("加载L3查找表...")
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

def nearest_beta(beta_hat):
    return min(BETA_VALUES, key=lambda b: abs(b - beta_hat))

def nearest_delta(delta_star):
    return min(DELTA_VALUES, key=lambda d: abs(d - delta_star))

print(f"可用的(n, β)组合: {list(l3_lookup.keys())}")

def run_mle_lse(beta_true, n, gamma_true, rep):
    """对单个样本运行MLE和LSE，返回β̂"""
    sample = generate_sample(beta_true, ETA_TRUE, gamma_true, n, rep)
    try:
        mle_result = run_method('mle', sample)
        mle_beta = mle_result['beta_hat'] if mle_result['converged'] else None
    except:
        mle_beta = None
    try:
        lse_result = fit_weibull3_lse(sample)
        lse_beta = lse_result['beta_hat']
    except:
        lse_beta = None
    return mle_beta, lse_beta

print("\n运行外部β预估实验...")
n_reps = 500
results = []
total_configs = len(BETA_VALUES) * len(NS) * len(GAMMA_ETA_RATIOS)
config_idx = 0

for beta in BETA_VALUES:
    for n in NS:
        for ger in GAMMA_ETA_RATIOS:
            config_idx += 1
            gamma_true = ger * ETA_TRUE
            print(f"\n[{config_idx}/{total_configs}] β={beta}, n={n}, γ/η={ger}")

            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            df = pd.read_csv(os.path.join(DATA_DIR, fname))

            # 默认δ=0.1对照
            default_rows = df[(df['delta'] == 0.10) & (df['status'] == True)]
            default_vals = default_rows[['beta_hat', 'eta_hat', 'gamma_hat']].values
            jparam_default, n_default = compute_jparam(
                default_vals[:, 0], default_vals[:, 1], default_vals[:, 2],
                beta, ETA_TRUE, gamma_true
            )
            results.append({
                'beta': beta, 'n': n, 'gamma_eta': ger,
                'method': 'Default(δ=0.1)', 'jparam': jparam_default,
                'n_valid': n_default
            })

            # 运行MLE/LSE
            mle_betas = []
            lse_betas = []
            t0 = time.time()
            for rep in range(n_reps):
                mle_b, lse_b = run_mle_lse(beta, n, gamma_true, rep)
                mle_betas.append(mle_b)
                lse_betas.append(lse_b)
                if (rep + 1) % 100 == 0:
                    print(f"  rep {rep+1}/{n_reps}...", flush=True)
            t1 = time.time()
            print(f"  MLE/LSE运行完成，耗时{t1-t0:.1f}s")

            # 对每个外部β方法，收集各rep对应的MDM结果，计算聚合J_param
            for method_name, beta_hats in [('MLE', mle_betas), ('LSE', lse_betas)]:
                bh_list, eh_list, gh_list = [], [], []
                for rep in range(n_reps):
                    beta_hat = beta_hats[rep]
                    if beta_hat is None or np.isnan(beta_hat):
                        continue
                    beta_near = nearest_beta(beta_hat)
                    key = (n, beta_near)
                    if key not in l3_lookup:
                        continue
                    delta_star = nearest_delta(l3_lookup[key])
                    row = df[(df['delta'] == delta_star) & (df['rep'] == rep)]
                    if len(row) == 0 or not row.iloc[0]['status']:
                        continue
                    row = row.iloc[0]
                    bh_list.append(row['beta_hat'])
                    eh_list.append(row['eta_hat'])
                    gh_list.append(row['gamma_hat'])

                jparam_ext, n_ext = compute_jparam(
                    np.array(bh_list), np.array(eh_list), np.array(gh_list),
                    beta, ETA_TRUE, gamma_true
                )
                results.append({
                    'beta': beta, 'n': n, 'gamma_eta': ger,
                    'method': method_name, 'jparam': jparam_ext,
                    'n_valid': n_ext
                })
                print(f"  {method_name}: J_param={jparam_ext:.4f} ({n_ext}/{n_reps} valid)")

results_df = pd.DataFrame(results)
out_path = os.path.join(DATA_DIR, "E03-4b_external_beta.csv")
results_df.to_csv(out_path, index=False)
print(f"\n结果已保存: {out_path}")

# 汇总对比
print("\n=== 外部β预估方案对比 ===")
pivot = results_df.pivot_table(
    values='jparam', index=['beta', 'n', 'gamma_eta'], columns='method', aggfunc='mean'
)
print(pivot.to_string())

# 保存汇总
summary_path = os.path.join(DATA_DIR, "E03-4b_summary.csv")
results_df.to_csv(summary_path, index=False)
print(f"\n汇总已保存: {summary_path}")
