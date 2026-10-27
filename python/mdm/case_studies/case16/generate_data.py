"""
⚠ 历史复现实验，不是当前默认 MDM 口径

案例16: WMLE 极小样本失效分析

分析 WMLE 在 n=3, n=5 时 beta 估计值异常收敛到 2.5 或 1.0 的现象

S4.9 后默认 MDM 已重写（几何加密网格+约束边界规则），本脚本仅用于历史案例复现。
"""

import sys
import os

# 添加 python 目录到路径
python_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
sys.path.insert(0, python_dir)

import numpy as np
from scipy.optimize import minimize
import json
from methods.wmle import get_weight_j1, get_weight_j2, get_weight_j3

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
N_SIMULATIONS = 500  # 每个样本量的模拟次数

print("=" * 70)
print("案例16: WMLE 极小样本失效分析")
print("=" * 70)
print(f"真实参数: beta={TRUE_BETA}, eta={TRUE_ETA}, gamma={TRUE_GAMMA}")
print(f"模拟次数: {N_SIMULATIONS}")
print()

# 存储结果
results = {
    "simulation_params": {
        "n_simulations": N_SIMULATIONS,
        "true_beta": TRUE_BETA,
        "true_eta": TRUE_ETA,
        "true_gamma": TRUE_GAMMA,
        "seed": 42
    },
    "sample_results": []
}

# 测试不同样本量
for n in [3, 5, 7, 10]:
    print(f"\n--- 样本量 n={n} ---")

    # 权重
    w1 = get_weight_j1(n)
    w2 = get_weight_j2(n)

    beta_estimates = []
    gamma_estimates = []
    eta_estimates = []

    for sim in range(N_SIMULATIONS):
        # 生成样本
        data = generate_weibull_3p_samples(n, TRUE_BETA, TRUE_ETA, TRUE_GAMMA)
        arr = np.array(data)

        # 目标函数
        def wmle_objective(params):
            beta, gamma_loc = params
            if beta <= 0 or beta > 10 or gamma_loc >= arr[0] - 1e-6 or gamma_loc < 0:
                return 1e10
            x_adj = arr - gamma_loc
            if np.any(x_adj <= 0):
                return 1e10
            log_x = np.log(x_adj)
            x_beta = x_adj ** beta
            sum_log = np.sum(log_x)
            sum_log_x_beta = np.sum(log_x * x_beta)
            sum_x_beta = np.sum(x_beta)
            term1 = w2/beta + sum_log/n - sum_log_x_beta/sum_x_beta
            sum_inv = np.sum(1.0 / x_adj)
            sum_x_beta_minus1 = np.sum(x_adj ** (beta - 1))
            w3 = get_weight_j3(n, beta)
            term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - w3
            return term1 ** 2 + term2 ** 2

        # 优化
        result = minimize(
            wmle_objective,
            x0=np.array([2.0, arr[0] * 0.95]),
            method='Nelder-Mead',
            options={'maxiter': 500}
        )

        if result.success:
            beta_hat = result.x[0]
            gamma_hat = result.x[1]
            # 计算 eta
            x_adj = arr - gamma_hat
            eta_hat = (np.sum(x_adj ** beta_hat) / (n * w1)) ** (1 / beta_hat)

            beta_estimates.append(beta_hat)
            gamma_estimates.append(gamma_hat)
            eta_estimates.append(eta_hat)

    beta_estimates = np.array(beta_estimates)
    gamma_estimates = np.array(gamma_estimates)
    eta_estimates = np.array(eta_estimates)

    # 统计
    print(f"  beta 估计值:")
    print(f"    mean = {np.mean(beta_estimates):.4f}")
    print(f"    std  = {np.std(beta_estimates):.4f}")
    print(f"    min  = {np.min(beta_estimates):.4f}")
    print(f"    max  = {np.max(beta_estimates):.4f}")

    # 统计 beta 在各个区间的分布
    bins = [0, 0.9, 1.1, 1.4, 1.6, 1.9, 2.1, 2.4, 2.6, 10]
    labels = ["<0.9", "1.0", "1.5", "2.0", "2.5", ">2.5"]
    counts = []
    for i in range(len(bins) - 1):
        count = int(np.sum((beta_estimates >= bins[i]) & (beta_estimates < bins[i+1])))
        counts.append(count)
        pct = count / len(beta_estimates) * 100
        if count > 0:
            print(f"    [{bins[i]:.1f}, {bins[i+1]:.1f}): {count} ({pct:.1f}%)")

    # 存储结果
    sample_result = {
        "n": n,
        "n_valid": len(beta_estimates),
        "w1": w1,
        "w2": w2,
        "beta": {
            "mean": float(np.mean(beta_estimates)),
            "std": float(np.std(beta_estimates)),
            "min": float(np.min(beta_estimates)),
            "max": float(np.max(beta_estimates)),
            "median": float(np.median(beta_estimates)),
            "estimates": beta_estimates.tolist()[:100]  # 只保存前100个用于可视化
        },
        "gamma": {
            "mean": float(np.mean(gamma_estimates)),
            "std": float(np.std(gamma_estimates)),
            "estimates": gamma_estimates.tolist()[:100]
        },
        "eta": {
            "mean": float(np.mean(eta_estimates)),
            "std": float(np.std(eta_estimates)),
            "estimates": eta_estimates.tolist()[:100]
        },
        "distribution": {
            "bins": bins,
            "counts": counts
        }
    }
    results["sample_results"].append(sample_result)

# 生成目标函数等高线数据
print("\n--- 生成目标函数等高线数据 ---")

# 生成一个典型样本
contour_data = []
for n in [3, 5, 7, 10]:
    np.random.seed(42 + n)
    data = generate_weibull_3p_samples(n, TRUE_BETA, TRUE_ETA, TRUE_GAMMA)
    arr = np.array(data)

    w1 = get_weight_j1(n)
    w2 = get_weight_j2(n)

    # 创建网格
    beta_range = np.linspace(0.5, 4.0, 50)
    gamma_range = np.linspace(arr[0] * 0.7, arr[0] * 0.99, 50)

    # 计算目标函数值
    Z = np.zeros((len(gamma_range), len(beta_range)))
    for i, gamma_loc in enumerate(gamma_range):
        for j, beta in enumerate(beta_range):
            if beta <= 0 or gamma_loc >= arr[0] - 1e-6:
                Z[i, j] = 1e10
                continue
            x_adj = arr - gamma_loc
            if np.any(x_adj <= 0):
                Z[i, j] = 1e10
                continue
            log_x = np.log(x_adj)
            x_beta = x_adj ** beta
            sum_log = np.sum(log_x)
            sum_log_x_beta = np.sum(log_x * x_beta)
            sum_x_beta = np.sum(x_beta)
            term1 = w2/beta + sum_log/n - sum_log_x_beta/sum_x_beta
            sum_inv = np.sum(1.0 / x_adj)
            sum_x_beta_minus1 = np.sum(x_adj ** (beta - 1))
            w3 = get_weight_j3(n, beta)
            term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - w3
            Z[i, j] = term1 ** 2 + term2 ** 2

    # 对数变换以便可视化
    Z_log = np.log10(Z + 1e-10)

    contour_data.append({
        "n": int(n),
        "sample_data": [float(x) for x in data],
        "beta_range": [float(x) for x in beta_range],
        "gamma_range": [float(x) for x in gamma_range],
        "Z_log": [[float(z) for z in row] for row in Z_log]
    })
    print(f"  n={n}: 目标函数等高线数据已生成")

results["contour_data"] = contour_data

# 生成 J3 权重曲线数据
print("\n--- 生成 J3 权重曲线数据 ---")
j3_curve_data = []
beta_values = np.linspace(0.5, 4.0, 100)
for n in [3, 5, 7, 10, 16]:
    j3_values = [get_weight_j3(n, b) for b in beta_values]
    # MLE 权重 (渐近值)
    mle_values = [b / (b - 1) if b > 1 else 2.0 for b in beta_values]

    j3_curve_data.append({
        "n": int(n),
        "beta_values": [float(x) for x in beta_values],
        "j3_values": [float(x) for x in j3_values],
        "mle_values": [float(x) for x in mle_values]
    })
    print(f"  n={n}: J3 权重曲线已生成")

results["j3_curve_data"] = j3_curve_data

# 保存结果
output_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'public', 'case-studies', 'mdm', 'case16', 'data.json')
os.makedirs(os.path.dirname(output_path), exist_ok=True)
with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(results, f, indent=2, ensure_ascii=False)

print(f"\n结果已保存到: {output_path}")
print("\n" + "=" * 70)
print("结论")
print("=" * 70)
print("""
1. n=3 时，beta 估计值呈现明显的双峰分布 (1.0 和 2.5)
2. 这是由于 J3 权重表的离散化和目标函数的多模态特性
3. WMLE 不适用于 n < 5 或 n < 7 的极小样本
""")
