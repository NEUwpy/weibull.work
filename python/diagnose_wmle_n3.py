"""
诊断 WMLE 在 n=3 时的问题

问题现象:
在案例14中，当 n=3 时，WMLE 的 β 估计值几乎只有 2.0 和 2.5 两个值。
这说明优化器被困在边界或局部最优。
"""

import numpy as np
from scipy.optimize import minimize
import sys
sys.path.insert(0, '.')
from methods.wmle import WMLE, get_weight_j1, get_weight_j2, get_weight_j3

# 设置随机种子
np.random.seed(42)

def generate_weibull_3p_samples(n, beta, eta, gamma):
    """生成三参数 Weibull 样本"""
    u = np.random.uniform(0, 1, n)
    samples = gamma + eta * np.power(-np.log(1 - u), 1.0 / beta)
    return sorted(samples)

# 真实参数
TRUE_BETA = 2.0
TRUE_ETA = 200.0
TRUE_GAMMA = 1000.0
N = 3

print("=" * 70)
print(f"诊断 WMLE 在 n={N} 时的问题")
print(f"真实参数: β={TRUE_BETA}, η={TRUE_ETA}, γ={TRUE_GAMMA}")
print("=" * 70)

# 生成多个样本并测试
results = []

for i in range(20):
    data = generate_weibull_3p_samples(N, TRUE_BETA, TRUE_ETA, TRUE_GAMMA)
    arr = np.array(data)

    print(f"\n--- 样本 {i+1} ---")
    print(f"数据: {[round(x, 2) for x in data]}")

    # 获取权重
    w1 = get_weight_j1(N)
    w2 = get_weight_j2(N)

    # 目标函数
    def wmle_objective(params):
        gamma_shape, alpha_loc = params  # gamma_shape = β (形状), alpha_loc = γ (位置)

        if gamma_shape <= 0 or gamma_shape > 10 or alpha_loc >= arr[0] - 1e-6 or alpha_loc < 0:
            return 1e10

        x_minus_alpha = arr - alpha_loc
        if np.any(x_minus_alpha <= 0):
            return 1e10

        log_x = np.log(x_minus_alpha)
        x_gamma = x_minus_alpha ** gamma_shape

        sum_log = np.sum(log_x)
        sum_log_x_gamma = np.sum(log_x * x_gamma)
        sum_x_gamma = np.sum(x_gamma)

        term1_left = w2 / gamma_shape + sum_log / N - sum_log_x_gamma / sum_x_gamma

        sum_inv = np.sum(1.0 / x_minus_alpha)
        sum_x_gamma_minus1 = np.sum(x_minus_alpha ** (gamma_shape - 1))

        w3 = get_weight_j3(N, gamma_shape)
        term2_left = sum_inv / N * sum_x_gamma / sum_x_gamma_minus1 - w3

        return term1_left ** 2 + term2_left ** 2

    # 测试不同的初始值
    print("\n不同初始值的优化结果:")

    initial_guesses = [
        (2.0, arr[0] * 0.95),  # 默认初始值
        (1.5, arr[0] * 0.90),
        (2.5, arr[0] * 0.90),
        (3.0, arr[0] * 0.95),
        (1.0, arr[0] * 0.95),
    ]

    obj_values = []
    for init_beta, init_gamma in initial_guesses:
        result = minimize(
            wmle_objective,
            x0=np.array([init_beta, init_gamma]),
            method='Nelder-Mead',
            options={'maxiter': 500}
        )

        if result.success:
            beta_hat = result.x[0]
            gamma_hat = result.x[1]

            # 计算 eta
            x_adj = arr - gamma_hat
            eta_hat = (np.sum(x_adj ** beta_hat) / (N * w1)) ** (1 / beta_hat)

            obj_val = result.fun
            obj_values.append((obj_val, beta_hat, gamma_hat, eta_hat, (init_beta, init_gamma)))

            print(f"  初始({init_beta:.1f}, {init_gamma:.1f}) → β={beta_hat:.4f}, γ={gamma_hat:.1f}, η={eta_hat:.1f}, obj={obj_val:.6f}")

    # 找最小目标函数值的结果
    if obj_values:
        best = min(obj_values, key=lambda x: x[0])
        print(f"\n最佳结果: β={best[1]:.4f}, γ={best[2]:.1f}, η={best[3]:.1f}")
        results.append(best[1])

    # 检查目标函数在 β 方向的行为
    print(f"\n目标函数在 β 方向的变化 (固定 α={arr[0] * 0.95:.1f}):")
    alpha_fixed = arr[0] * 0.95
    for beta_test in [1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0]:
        obj = wmle_objective([beta_test, alpha_fixed])
        print(f"  β={beta_test:.1f}: obj={obj:.6f}")

print("\n" + "=" * 70)
print("总结")
print("=" * 70)
print(f"20个样本的 β 估计值分布:")
print([round(b, 2) for b in results])

from collections import Counter
counter = Counter([round(b, 1) for b in results])
print(f"\nβ 估计值统计 (四舍五入到1位小数):")
for val, count in sorted(counter.items()):
    print(f"  β={val}: {count}次")
