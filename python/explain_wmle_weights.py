"""
WMLE 权重处理策略详解

问题1: 原文中没有的样本数 n 怎么办？
问题2: 原文中没有的形状参数 β 怎么办？
问题3: 估计时只知道样本，不知道真实参数，怎么确定 J3 权重？
"""

import sys
sys.path.insert(0, '.')
from methods.wmle import get_weight_j1, get_weight_j2, get_weight_j3

print("=" * 70)
print("WMLE 权重处理策略")
print("=" * 70)

# ==================== J1 权重 ====================
print("\n【J1 权重】(只依赖于 n)")
print("-" * 50)
print("论文表格: n = 1-16, 20, 32, 50, 100")
print()

# 测试不同 n 值
test_ns = [3, 5, 10, 15, 16, 17, 20, 25, 30, 50, 100, 150, 200]
print(f"{'n':<8} {'J1':<12} {'处理方式':<20}")
print("-" * 50)
for n in test_ns:
    j1 = get_weight_j1(n)
    if n <= 16 or n in [20, 32, 50, 100]:
        method = "查表"
    elif n < 100:
        method = "插值"
    elif n == 100:
        method = "查表"
    else:
        method = "渐近值=1.0"
    print(f"{n:<8} {j1:<12.6f} {method:<20}")

print()
print("J1 的精确公式: exp(ψ(n)) / n，其中 ψ 是 digamma 函数")
print("当 n → ∞ 时，J1 → 1")

# ==================== J2 权重 ====================
print("\n【J2 权重】(只依赖于 n)")
print("-" * 50)
print("论文表格: n = 1-16, 20, 32, 50, 100")
print()

print(f"{'n':<8} {'J2':<12} {'处理方式':<20}")
print("-" * 50)
for n in test_ns:
    j2 = get_weight_j2(n)
    if n <= 16 or n in [20, 32, 50, 100]:
        method = "查表"
    elif n < 100:
        method = "线性插值"
    else:
        method = "渐近值=1.0"
    print(f"{n:<8} {j2:<12.6f} {method:<20}")

print()
print("J2 的渐近值: 当 n → ∞ 时，J2 → 1")

# ==================== J3 权重 ====================
print("\n【J3 权重】(依赖于 n 和 β)")
print("-" * 50)
print("论文表格: n = 1-16, β = 0.5, 1.0, 1.5, 2.0, 2.5")
print()

# 测试不同 n 和 β 组合
print("n=10 时不同 β 的 J3 值:")
print(f"{'β':<8} {'J3':<12} {'处理方式':<20}")
print("-" * 50)
test_betas = [0.3, 0.5, 0.8, 1.0, 1.3, 1.5, 1.8, 2.0, 2.3, 2.5, 2.8, 3.0, 4.0]
for beta in test_betas:
    j3 = get_weight_j3(10, beta)
    if beta < 0.5:
        method = "使用 β=0.5 边界值"
    elif beta > 2.5:
        method = "插值到渐近值"
    elif beta in [0.5, 1.0, 1.5, 2.0, 2.5]:
        method = "查表"
    else:
        method = "线性插值"
    print(f"{beta:<8.1f} {j3:<12.6f} {method:<20}")

print()
print("J3 的渐近值: 当 n → ∞ 时，J3 → β/(β-1)")
print()

# 测试不同 n（固定 β=2.0）
print("β=2.0 时不同 n 的 J3 值:")
print(f"{'n':<8} {'J3':<12} {'处理方式':<20}")
print("-" * 50)
for n in test_ns:
    j3 = get_weight_j3(n, 2.0)
    if n <= 16:
        method = "查表"
    elif n <= 100:
        method = "外推公式"
    else:
        method = "渐近值=2.0"
    print(f"{n:<8} {j3:<12.6f} {method:<20}")

# ==================== 核心问题：J3 动态更新 ====================
print("\n" + "=" * 70)
print("核心问题：估计时不知道真实 β，怎么确定 J3？")
print("=" * 70)
print("""
答案：J3 在优化过程中**动态更新**！

WMLE 的优化过程：
1. 初始化 β̂ = 2.0（初始猜测）
2. 循环迭代：
   a. 根据当前 β̂ 计算 J3(β̂)
   b. 计算目标函数值
   c. 更新 β̂ 和 γ̂
3. 收敛后，使用最终的 β̂ 计算 J3

论文原话：
"The value of the third weight is not a constant but changes during
the search as new values of γ̂ are explored."

这意味着：
- J3 不是固定值，而是随着优化过程变化
- 每次迭代都重新计算 J3
- 最终收敛时，J3 与 β̂ 是一致的
""")

# 展示优化过程中 J3 的变化
print("\n示例：论文样本 (n=10) 优化过程中 J3 的变化")
print("-" * 50)

import numpy as np
X = np.array([310, 342, 353, 365, 383, 393, 403, 412, 451, 456])
n = 10
J2 = 0.853

def wmle_obj(beta, gamma_loc):
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
    j3 = get_weight_j3(n, beta)
    term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - j3
    return term1 ** 2 + term2 ** 2, j3

print(f"{'迭代':<8} {'β':<10} {'γ':<10} {'J3':<12} {'目标函数':<15}")
print("-" * 60)

# 模拟优化过程
iterations = [
    (0, 2.0, 279.0),    # 初始值
    (1, 2.2, 282.0),
    (2, 2.3, 284.0),
    (3, 2.25, 285.0),
    (4, 2.24, 285.5),   # 收敛
]

for it, beta, gamma_loc in iterations:
    obj, j3 = wmle_obj(beta, gamma_loc)
    print(f"{it:<8} {beta:<10.4f} {gamma_loc:<10.2f} {j3:<12.6f} {obj:<15.10f}")
