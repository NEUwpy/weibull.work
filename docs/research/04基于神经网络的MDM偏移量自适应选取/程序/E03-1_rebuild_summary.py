"""
从27个分片CSV重新生成 E03-3_summary.csv
"""
import sys
sys.path.insert(0, "D:/weibull/python")

import numpy as np
import csv
import os

datadir = "D:/weibull/docs/research/04基于神经网络的MDM偏移量自适应选取/实验数据"
eta_true = 1.0
deltas = [f"{d:.2f}" for d in np.arange(0, 0.52, 0.02)]

summary_rows = []

for beta in [2.0, 2.5, 4.0]:
    for n in [7, 10, 20]:
        for ger in [0.1, 0.5, 1.0]:
            gamma_true = ger * eta_true
            fname = f"E03-3_delta_sweep_beta{beta}_n{n}_gamma{ger}.csv"
            fpath = os.path.join(datadir, fname)
            
            # 按delta分组读取
            delta_data = {}
            with open(fpath, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    d = row['delta']
                    if d not in delta_data:
                        delta_data[d] = {'beta_hats': [], 'eta_hats': [], 'gamma_hats': []}
                    if row['beta_hat']:
                        delta_data[d]['beta_hats'].append(float(row['beta_hat']))
                        delta_data[d]['eta_hats'].append(float(row['eta_hat']))
                        delta_data[d]['gamma_hats'].append(float(row['gamma_hat']))
            
            for d_str in deltas:
                if d_str not in delta_data:
                    continue
                dd = delta_data[d_str]
                bh = dd['beta_hats']
                eh = dd['eta_hats']
                gh = dd['gamma_hats']
                
                if len(bh) > 0:
                    bias_beta = np.mean(bh) - beta
                    sd_beta = np.std(bh, ddof=1)
                    bias_eta = np.mean(eh) - eta_true
                    sd_eta = np.std(eh, ddof=1)
                    bias_gamma = np.mean(gh) - gamma_true
                    sd_gamma = np.std(gh, ddof=1)
                else:
                    bias_beta = sd_beta = bias_eta = sd_eta = bias_gamma = sd_gamma = np.nan
                
                summary_rows.append({
                    'beta': beta,
                    'n': n,
                    'gamma_eta': ger,
                    'delta': float(d_str),
                    'bias_beta': bias_beta,
                    'sd_beta': sd_beta,
                    'bias_eta': bias_eta,
                    'sd_eta': sd_eta,
                    'bias_gamma': bias_gamma,
                    'sd_gamma': sd_gamma,
                    'n_valid': len(bh)
                })

summary_path = os.path.join(datadir, "E03-3_summary.csv")
with open(summary_path, 'w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=[
        'beta', 'n', 'gamma_eta', 'delta',
        'bias_beta', 'sd_beta', 'bias_eta', 'sd_eta', 'bias_gamma', 'sd_gamma', 'n_valid'
    ])
    writer.writeheader()
    writer.writerows(summary_rows)

print(f"汇总完成: {len(summary_rows)} 行 (应为 {27*26}={27*26})")
print(f"保存: {summary_path}")
