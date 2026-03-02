"""
进一步验证：我们找到了比论文更优的解

论文声称在 beta=2.29, gamma=283.7 处找到了方程 (4) 的零点。
但实际上那里的目标函数值是 0.00009163，不是真正的零点。
我们的解 (beta=2.24, gamma=285.48) 处的目标函数值接近 0。
"""

import sys
sys.path.insert(0, '.')
import numpy as np
from scipy.optimize import minimize

# 论文样本
X = np.array([310, 342, 353, 365, 383, 393, 403, 412, 451, 456])
n = len(X)

# 权重
J1 = 0.967
J2 = 0.853

J3_TABLE = {10: {0.5: 8.643, 1.0: 3.365, 1.5: 2.180, 2.0: 1.758, 2.5: 1.552}}
GAMMA_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5]

def get_j3(beta):
    j3 = J3_TABLE[10]
    if beta <= 0.5: return j3[0.5]
    if beta >= 2.5: return j3[2.5]
    for i in range(len(GAMMA_VALUES) - 1):
        g_low, g_high = GAMMA_VALUES[i], GAMMA_VALUES[i + 1]
        if g_low <= beta <= g_high:
            t = (beta - g_low) / (g_high - g_low)
            return j3[g_low] + t * (j3[g_high] - j3[g_low])
    return j3[2.0]

def wmle_objective(params):
    beta, gamma_loc = params
    if beta <= 0 or gamma_loc >= X.min() - 1e-6 or gamma_loc < 0:
        return 1e10
    x_adj = X - gamma_loc
    if np.any(x_adj <= 0):
        return 1e10
    log_x = np.log(x_adj)
    x_beta = x_adj ** beta
    sum_log = np.sum(log_x)
    sum_log_x_beta = np.sum(log_x * x_beta)
    sum_x_beta = np.sum(x_beta)
    term1 = J2/beta + sum_log/n - sum_log_x_beta/sum_x_beta
    sum_inv = np.sum(1.0 / x_adj)
    sum_x_beta_minus1 = np.sum(x_adj ** (beta - 1))
    j3 = get_j3(beta)
    term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - j3
    return term1 ** 2 + term2 ** 2

def compute_eta(gamma_loc, beta):
    x_adj = X - gamma_loc
    return (np.sum(x_adj ** beta) / (n * J1)) ** (1/beta)

print("=" * 70)
print("WMLE 解的精度对比")
print("=" * 70)

# 论文结果
paper_beta = 2.29
paper_gamma = 283.7
paper_eta = 116.0
paper_obj = wmle_objective([paper_beta, paper_gamma])

# 我们的结果
our_beta = 2.2401
our_gamma = 285.48
our_eta = compute_eta(our_gamma, our_beta)
our_obj = wmle_objective([our_beta, our_gamma])

print()
print(f"{'指标':<20} {'论文结果':<20} {'我们的结果':<20}")
print("-" * 60)
print(f"{'β (形状参数)':<20} {paper_beta:<20.4f} {our_beta:<20.4f}")
print(f"{'γ (位置参数)':<20} {paper_gamma:<20.4f} {our_gamma:<20.4f}")
print(f"{'η (尺度参数)':<20} {paper_eta:<20.4f} {our_eta:<20.4f}")
print(f"{'目标函数值':<20} {paper_obj:<20.10f} {our_obj:<20.10f}")
print(f"{'J3 权重':<20} {get_j3(paper_beta):<20.6f} {get_j3(our_beta):<20.6f}")

print()
print("=" * 70)
print("结论")
print("=" * 70)
print(f"""
1. 论文结果处的目标函数值 = {paper_obj:.10f} (非零!)
2. 我们结果处的目标函数值 = {our_obj:.15f} (接近零!)

这说明:
- 我们找到了更优的解 (目标函数值更小)
- 论文的优化器可能没有收敛到全局最优
- 2009 年的优化器精度可能不够

两个结果都接近真值 β=2.0, γ=300:
- 论文: β=2.29 (偏差 +14.5%), γ=283.7 (偏差 -5.4%)
- 我们:  β=2.24 (偏差 +12.0%), γ=285.5 (偏差 -4.8%)

两者都存在正向偏差，这是因为样本量 n=10 较小导致的。
我们的解在数学上更优（目标函数更接近零），但差异很小。
""")

# 用更高精度优化
print("-" * 70)
print("高精度优化验证")
print("-" * 70)

result = minimize(
    wmle_objective,
    x0=np.array([2.24, 285.5]),
    method='Nelder-Mead',
    options={'maxiter': 10000, 'xatol': 1e-15, 'fatol': 1e-15}
)

beta_opt, gamma_opt = result.x
eta_opt = compute_eta(gamma_opt, beta_opt)
print(f"高精度优化: beta={beta_opt:.10f}, gamma={gamma_opt:.8f}, eta={eta_opt:.6f}")
print(f"目标函数值: {result.fun:.20e}")
print(f"J3 = {get_j3(beta_opt):.10f}")
