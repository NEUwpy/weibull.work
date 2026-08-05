"""
E03-3 L5 Oracle（逐样本最优δ）
在 n=7 上，对每个样本扫描所有δ，找使Bias最小的δ*
"""
import sys
sys.path.insert(0, "D:/weibull/python")
sys.path.insert(0, "D:/weibull/python/studies/common")

import numpy as np
import csv
import os
from studies.common.sample import generate_sample
from studies.common.runner import run_method

# 只在 n=7 上做
n = 7
betas = [1.5, 2.0, 2.5, 4.0, 5.0]
gamma_eta_ratios = [0.1, 0.5, 1.0]
deltas = np.arange(0, 0.52, 0.02)  # 26个点
n_reps = 500
eta_true = 1.0

# 输出目录
outdir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"
os.makedirs(outdir, exist_ok=True)

# 汇总结果
summary_rows = []

total_configs = len(betas) * len(gamma_eta_ratios)
config_idx = 0

for beta in betas:
    for ger in gamma_eta_ratios:
        config_idx += 1
        gamma_true = ger * eta_true
        
        print(f"[{config_idx}/{total_configs}] β={beta}, n={n}, γ/η={ger}")
        
        # 生成所有样本
        samples = []
        for rep in range(n_reps):
            sample = generate_sample(beta, eta_true, gamma_true, n, rep)
            samples.append(sample)
        
        # 对每个样本，扫描所有δ，找最优
        oracle_results = []
        
        for rep in range(n_reps):
            best_delta = None
            best_bias_beta = float('inf')
            best_result = None
            
            for delta in deltas:
                result = run_method('mdm', samples[rep], offset=float(delta))
                
                if result['beta_hat'] is not None:
                    bias_beta = abs(result['beta_hat'] - beta)
                    
                    if bias_beta < best_bias_beta:
                        best_bias_beta = bias_beta
                        best_delta = float(delta)
                        best_result = result
            
            oracle_results.append({
                'rep': rep,
                'best_delta': best_delta,
                'bias_beta': best_bias_beta,
                'beta_hat': best_result['beta_hat'] if best_result else None,
                'eta_hat': best_result['eta_hat'] if best_result else None,
                'gamma_hat': best_result['gamma_hat'] if best_result else None,
            })
        
        # 保存Oracle结果
        fname = f"E03-3_oracle_beta{beta}_n{n}_gamma{ger}.csv"
        fpath = os.path.join(outdir, fname)
        
        with open(fpath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['rep', 'best_delta', 'bias_beta', 'beta_hat', 'eta_hat', 'gamma_hat'])
            for res in oracle_results:
                writer.writerow([
                    res['rep'],
                    f"{res['best_delta']:.2f}" if res['best_delta'] is not None else "",
                    f"{res['bias_beta']:.6f}",
                    f"{res['beta_hat']:.6f}" if res['beta_hat'] is not None else "",
                    f"{res['eta_hat']:.6f}" if res['eta_hat'] is not None else "",
                    f"{res['gamma_hat']:.6f}" if res['gamma_hat'] is not None else ""
                ])
        
        # 汇总统计
        valid_results = [r for r in oracle_results if r['beta_hat'] is not None]
        if valid_results:
            deltas_used = [r['best_delta'] for r in valid_results if r['best_delta'] is not None]
            biases = [r['bias_beta'] for r in valid_results]
            beta_hats = [r['beta_hat'] for r in valid_results]
            eta_hats = [r['eta_hat'] for r in valid_results]
            gamma_hats = [r['gamma_hat'] for r in valid_results]
            
            summary_rows.append({
                'beta': beta,
                'n': n,
                'gamma_eta': ger,
                'oracle_delta_mean': np.mean(deltas_used),
                'oracle_delta_std': np.std(deltas_used),
                'oracle_bias_beta_mean': np.mean(biases),
                'oracle_bias_beta_std': np.std(biases),
                'sd_beta': np.std(beta_hats, ddof=1),
                'sd_eta': np.std(eta_hats, ddof=1),
                'sd_gamma': np.std(gamma_hats, ddof=1),
                'n_valid': len(valid_results)
            })
            
            print(f"  Oracle δ* 分布: 均值={np.mean(deltas_used):.3f}, 标准差={np.std(deltas_used):.3f}")
            print(f"  Oracle |Bias(β̂)|: 均值={np.mean(biases):.4f}, 标准差={np.std(biases):.4f}")

# 保存汇总
summary_path = os.path.join(outdir, "E03-3_oracle_summary.csv")
with open(summary_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'beta', 'n', 'gamma_eta',
        'oracle_delta_mean', 'oracle_delta_std',
        'oracle_bias_beta_mean', 'oracle_bias_beta_std',
        'sd_beta', 'sd_eta', 'sd_gamma', 'n_valid'
    ])
    writer.writeheader()
    writer.writerows(summary_rows)

print(f"\nOracle汇总已保存: {summary_path}")
