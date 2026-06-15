"""
E03-1 δ扫描蒙特卡洛
扫描不同δ值，生成分片数据文件
"""
import sys
sys.path.insert(0, "D:/weibull/python")
sys.path.insert(0, "D:/weibull/python/studies/common")

import numpy as np
import csv
import os
from studies.common.sample import generate_sample
from studies.common.runner import run_method

# 参数网格
betas = [1.5, 2.0, 2.5, 4.0, 5.0]
ns = [7, 10, 20]
gamma_eta_ratios = [0.1, 0.5, 1.0]
deltas = np.arange(0, 0.52, 0.02)  # 0, 0.02, ..., 0.50
n_reps = 500
eta_true = 1.0  # 固定η=1

# 输出目录
outdir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"
os.makedirs(outdir, exist_ok=True)

# 汇总结果
summary_rows = []

# 总进度
total_configs = len(betas) * len(ns) * len(gamma_eta_ratios)
config_idx = 0

for beta in betas:
    for n in ns:
        for ger in gamma_eta_ratios:
            config_idx += 1
            gamma_true = ger * eta_true
            
            # 分片文件名
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            fpath = os.path.join(outdir, fname)
            expected_lines = 1 + len(deltas) * n_reps  # header + data
            
            # 跳过已完成的文件
            if os.path.exists(fpath):
                with open(fpath, 'r') as _f:
                    actual_lines = sum(1 for _ in _f)
                if actual_lines >= expected_lines:
                    print(f"[{config_idx}/{total_configs}] β={beta}, n={n}, γ/η={ger} → 已完成，跳过")
                    continue
                else:
                    print(f"[{config_idx}/{total_configs}] β={beta}, n={n}, γ/η={ger} → 未完成({actual_lines}/{expected_lines})，重新开始")
            
            print(f"[{config_idx}/{total_configs}] β={beta}, n={n}, γ/η={ger} → {fname}")
            
            # 生成所有样本（可复现）
            samples = []
            for rep in range(n_reps):
                sample = generate_sample(beta, eta_true, gamma_true, n, rep)
                samples.append(sample)
            
            # 扫描δ
            with open(fpath, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow(['delta', 'rep', 'beta_hat', 'eta_hat', 'gamma_hat', 'status'])
                
                for delta in deltas:
                    beta_hats = []
                    eta_hats = []
                    gamma_hats = []
                    
                    for rep in range(n_reps):
                        result = run_method('mdm', samples[rep], offset=float(delta))
                        
                        beta_hat = result['beta_hat']
                        eta_hat = result['eta_hat']
                        gamma_hat = result['gamma_hat']
                        status = result['converged']
                        
                        writer.writerow([
                            f"{delta:.2f}",
                            rep,
                            f"{beta_hat:.6f}" if beta_hat is not None else "",
                            f"{eta_hat:.6f}" if eta_hat is not None else "",
                            f"{gamma_hat:.6f}" if gamma_hat is not None else "",
                            status
                        ])
                        
                        if beta_hat is not None:
                            beta_hats.append(beta_hat)
                            eta_hats.append(eta_hat)
                            gamma_hats.append(gamma_hat)
                    
                    # 计算 Bias 和 SD
                    if len(beta_hats) > 0:
                        bias_beta = np.mean(beta_hats) - beta
                        sd_beta = np.std(beta_hats, ddof=1)
                        bias_eta = np.mean(eta_hats) - eta_true
                        sd_eta = np.std(eta_hats, ddof=1)
                        bias_gamma = np.mean(gamma_hats) - gamma_true
                        sd_gamma = np.std(gamma_hats, ddof=1)
                    else:
                        bias_beta = sd_beta = bias_eta = sd_eta = bias_gamma = sd_gamma = np.nan
                    
                    summary_rows.append({
                        'beta': beta,
                        'n': n,
                        'gamma_eta': ger,
                        'delta': float(delta),
                        'bias_beta': bias_beta,
                        'sd_beta': sd_beta,
                        'bias_eta': bias_eta,
                        'sd_eta': sd_eta,
                        'bias_gamma': bias_gamma,
                        'sd_gamma': sd_gamma,
                        'n_valid': len(beta_hats)
                    })
            
            print(f"  完成，{n_reps * len(deltas)} 次拟合")

# 保存汇总文件
summary_path = os.path.join(outdir, "E03-3_summary.csv")
with open(summary_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'beta', 'n', 'gamma_eta', 'delta',
        'bias_beta', 'sd_beta', 'bias_eta', 'sd_eta', 'bias_gamma', 'sd_gamma', 'n_valid'
    ])
    writer.writeheader()
    writer.writerows(summary_rows)

print(f"\n汇总文件已保存: {summary_path}")
print(f"分片文件数: {total_configs}")
print(f"总拟合次数: {total_configs * n_reps * len(deltas)}")
