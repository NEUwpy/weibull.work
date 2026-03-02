"""
深入分析 WMLE 实现与论文结果差异的原因

论文结果: beta=2.29, eta=116.0, gamma=283.7
我们的结果: beta=2.24, eta=114.06, gamma=285.48

可能的原因:
1. J3 权重插值方式
2. 优化器初始值
3. 优化器参数
4. 目标函数实现细节
"""

import sys
sys.path.insert(0, '.')
import numpy as np
from scipy.optimize import minimize

# 论文样本
X = np.array([310, 342, 353, 365, 383, 393, 403, 412, 451, 456])
n = len(X)

# 权重表 (论文 Table 2, 3, 4)
J1_TABLE = {10: 0.967}
J2_TABLE = {10: 0.853}
J3_TABLE = {
    10: {0.5: 8.643, 1.0: 3.365, 1.5: 2.180, 2.0: 1.758, 2.5: 1.552}
}
GAMMA_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5]

def get_j3_linear(beta):
    """线性插值获取 J3"""
    j3_at_n = J3_TABLE[10]
    if beta <= 0.5:
        return j3_at_n[0.5]
    if beta >= 2.5:
        return j3_at_n[2.5]
    for i in range(len(GAMMA_VALUES) - 1):
        g_low, g_high = GAMMA_VALUES[i], GAMMA_VALUES[i + 1]
        if g_low <= beta <= g_high:
            t = (beta - g_low) / (g_high - g_low)
            return j3_at_n[g_low] + t * (j3_at_n[g_high] - j3_at_n[g_low])
    return j3_at_n[2.0]

J1 = J1_TABLE[10]
J2 = J2_TABLE[10]

print("=" * 70)
print("分析 WMLE 与论文差异的原因")
print("=" * 70)

# 论文结果
paper_beta = 2.29
paper_gamma = 283.7
paper_eta = 116.0

print(f"\n论文结果: beta={paper_beta}, eta={paper_eta}, gamma={paper_gamma}")
print()

# 目标函数定义
def wmle_objective(params):
    beta, gamma_loc = params  # beta=形状, gamma_loc=位置

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

    # 论文方程 (4) 第一部分
    term1 = J2/beta + sum_log/n - sum_log_x_beta/sum_x_beta

    sum_inv = np.sum(1.0 / x_adj)
    sum_x_beta_minus1 = np.sum(x_adj ** (beta - 1))
    j3 = get_j3_linear(beta)

    # 论文方程 (4) 第二部分
    term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - j3

    return term1 ** 2 + term2 ** 2

# 检查论文结果处的目标函数值
print("-" * 70)
print("1. 检查论文结果处的目标函数值")
print("-" * 70)

obj_at_paper = wmle_objective([paper_beta, paper_gamma])
j3_at_paper = get_j3_linear(paper_beta)
print(f"论文结果处 (beta={paper_beta}, gamma={paper_gamma}):")
print(f"  J3 = {j3_at_paper:.6f}")
print(f"  目标函数值 = {obj_at_paper:.10f}")

# 分量分析
x_adj = X - paper_gamma
log_x = np.log(x_adj)
x_beta = x_adj ** paper_beta
sum_log = np.sum(log_x)
sum_log_x_beta = np.sum(log_x * x_beta)
sum_x_beta = np.sum(x_beta)
term1 = J2/paper_beta + sum_log/n - sum_log_x_beta/sum_x_beta
sum_inv = np.sum(1.0 / x_adj)
sum_x_beta_minus1 = np.sum(x_adj ** (paper_beta - 1))
term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - j3_at_paper

print(f"  term1 = {term1:.10f}")
print(f"  term2 = {term2:.10f}")
print(f"  term1^2 + term2^2 = {term1**2 + term2**2:.10f}")

# 用不同的初始值优化
print()
print("-" * 70)
print("2. 测试不同初始值")
print("-" * 70)

initial_guesses = [
    (2.0, 279),    # 代码默认
    (2.0, 280.9),  # 论文两步MLE结果
    (2.29, 283.7), # 论文WMLE结果
    (2.5, 280),
    (1.5, 280),
]

for init_beta, init_gamma in initial_guesses:
    result = minimize(
        wmle_objective,
        x0=np.array([init_beta, init_gamma]),
        method='Nelder-Mead',
        options={'maxiter': 2000, 'xatol': 1e-10, 'fatol': 1e-10}
    )
    if result.success:
        b, g = result.x
        eta = (np.sum((X - g) ** b) / (n * J1)) ** (1/b)
        j3 = get_j3_linear(b)
        print(f"初始({init_beta:.2f}, {init_gamma:.1f}) -> beta={b:.6f}, gamma={g:.4f}, eta={eta:.4f}, obj={result.fun:.12f}, J3={j3:.6f}")

# 使用全局优化
print()
print("-" * 70)
print("3. 使用网格搜索找全局最优")
print("-" * 70)

best_obj = float('inf')
best_params = None

for beta in np.linspace(1.5, 3.5, 100):
    for gamma_loc in np.linspace(250, 300, 100):
        obj = wmle_objective([beta, gamma_loc])
        if obj < best_obj:
            best_obj = obj
            best_params = (beta, gamma_loc)

if best_params:
    b, g = best_params
    eta = (np.sum((X - g) ** b) / (n * J1)) ** (1/b)
    j3 = get_j3_linear(b)
    print(f"网格搜索最优: beta={b:.6f}, gamma={g:.4f}, eta={eta:.4f}, obj={best_obj:.12f}")
    print(f"J3 at this beta: {j3:.6f}")

# 从网格搜索结果精细优化
print()
print("-" * 70)
print("4. 从网格搜索结果精细优化")
print("-" * 70)

result = minimize(
    wmle_objective,
    x0=np.array([best_params[0], best_params[1]]),
    method='Nelder-Mead',
    options={'maxiter': 5000, 'xatol': 1e-12, 'fatol': 1e-12}
)
if result.success:
    b, g = result.x
    eta = (np.sum((X - g) ** b) / (n * J1)) ** (1/b)
    j3 = get_j3_linear(b)
    print(f"精细优化结果: beta={b:.8f}, gamma={g:.6f}, eta={eta:.4f}, obj={result.fun:.15f}")
    print(f"J3 = {j3:.8f}")

# 检查 J3 插值是否正确
print()
print("-" * 70)
print("5. J3 插值检查")
print("-" * 70)

print("J3 权重表 (n=10):")
for g in GAMMA_VALUES:
    print(f"  gamma={g}: J3={J3_TABLE[10][g]}")

print()
print("插值结果:")
for b in [2.0, 2.1, 2.2, 2.29, 2.3, 2.4, 2.5]:
    j3 = get_j3_linear(b)
    # 计算插值位置
    if 2.0 <= b <= 2.5:
        t = (b - 2.0) / 0.5
        print(f"  beta={b}: J3={j3:.6f} (t={t:.3f}, 线性插值)")
    elif b < 2.0:
        print(f"  beta={b}: J3={j3:.6f} (在 1.5-2.0 区间插值)")
    else:
        print(f"  beta={b}: J3={j3:.6f} (>=2.5, 使用边界值)")
