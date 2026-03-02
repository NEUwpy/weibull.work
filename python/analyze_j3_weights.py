"""
分析 J3 权重表对 WMLE 的影响

论文 Table 4 只提供了 n=1-16 和 γ=0.5,1.0,1.5,2.0,2.5 的 J3 值。
当 n=3 时：
- γ=0.5: J3=3.081
- γ=1.0: J3=2.082
- γ=1.5: J3=1.680
- γ=2.0: J3=1.479
- γ=2.5: J3=1.367

这些离散值可能导致目标函数在插值点处出现非物理的局部最小值。
"""

import numpy as np
import matplotlib.pyplot as plt
from scipy.interpolate import interp1d

# J3 权重表 (论文 Table 4)
J3_TABLE = {
    1: {0.5: 1.001, 1.0: 0.999, 1.5: 0.999, 2.0: 0.995, 2.5: 0.998},
    2: {0.5: 2.096, 1.0: 1.668, 1.5: 1.456, 2.0: 1.339, 2.5: 1.262},
    3: {0.5: 3.081, 1.0: 2.082, 1.5: 1.680, 2.0: 1.479, 2.5: 1.367},
    4: {0.5: 3.950, 1.0: 2.381, 1.5: 1.822, 2.0: 1.567, 2.5: 1.428},
    5: {0.5: 4.806, 1.0: 2.631, 1.5: 1.920, 2.0: 1.625, 2.5: 1.464},
    6: {0.5: 5.631, 1.0: 2.808, 1.5: 2.004, 2.0: 1.669, 2.5: 1.492},
    7: {0.5: 6.433, 1.0: 2.982, 1.5: 2.056, 2.0: 1.698, 2.5: 1.509},
    8: {0.5: 7.150, 1.0: 3.114, 1.5: 2.105, 2.0: 1.722, 2.5: 1.525},
    9: {0.5: 7.931, 1.0: 3.252, 1.5: 2.151, 2.0: 1.739, 2.5: 1.537},
    10: {0.5: 8.643, 1.0: 3.365, 1.5: 2.180, 2.0: 1.758, 2.5: 1.552},
}

GAMMA_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5]

def get_j3_linear(n, beta):
    """线性插值获取 J3"""
    if n > 10:
        if beta <= 1:
            return 2.0
        return beta / (beta - 1)

    j3_at_n = J3_TABLE.get(n, J3_TABLE[10])

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

# 生成 J3 曲线
betas = np.linspace(0.5, 3.0, 100)

print("=" * 70)
print("J3 权重随 β 变化的曲线")
print("=" * 70)

for n in [3, 5, 10]:
    j3_values = [get_j3_linear(n, b) for b in betas]
    mle_values = [b / (b - 1) if b > 1 else 2.0 for b in betas]

    print(f"\nn={n}:")
    for b in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0]:
        j3 = get_j3_linear(n, b)
        mle = b / (b - 1) if b > 1 else float('inf')
        print(f"  β={b:.1f}: J3={j3:.3f}, MLE权重={mle:.3f}")

# 分析 J3 的变化率
print("\n" + "=" * 70)
print("J3 变化率分析 (dJ3/dβ)")
print("=" * 70)

for n in [3, 5, 10]:
    print(f"\nn={n}:")
    for i in range(len(GAMMA_VALUES) - 1):
        b_low, b_high = GAMMA_VALUES[i], GAMMA_VALUES[i + 1]
        j3_low = J3_TABLE[n][b_low]
        j3_high = J3_TABLE[n][b_high]
        slope = (j3_high - j3_low) / (b_high - b_low)
        print(f"  [{b_low}, {b_high}]: dJ3/dβ = {slope:.3f}")

# 关键发现
print("\n" + "=" * 70)
print("关键发现")
print("=" * 70)
print("""
1. J3 在 β ∈ [0.5, 2.5] 区间内是**单调递减**的
   - 对于 n=3: J3 从 3.081 (β=0.5) 下降到 1.367 (β=2.5)
   - 变化幅度: 1.714

2. MLE 权重 (β/(β-1)) 在 β>1 时是**单调递减**的
   - 但在 β≤1 时无定义或为负

3. J3 和 MLE 权重的差异:
   - β=1.5: J3=1.680, MLE=3.0 (差 1.32)
   - β=2.0: J3=1.479, MLE=2.0 (差 0.521)
   - β=2.5: J3=1.367, MLE=1.667 (差 0.3)

4. 问题根源:
   - J3 权重表只有 5 个离散点，线性插值可能引入不准确的中间值
   - 在 n=3 时，J3 的变化幅度很大，可能导致目标函数的形状异常
""")

# 验证：检查 n=10 时 WMLE 是否正常
print("\n" + "=" * 70)
print("验证: n=10 时的 WMLE 行为")
print("=" * 70)

# 论文数据
X = np.array([310, 342, 353, 365, 383, 393, 403, 412, 451, 456])
n = 10
J2 = 0.853

def wmle_objective(params, X, w2, n):
    beta, gamma = params

    if beta <= 0 or gamma >= X.min() - 1e-6 or gamma < 0:
        return 1e10

    x_adj = X - gamma
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
    w3 = get_j3_linear(n, beta)

    term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - w3

    return term1 ** 2 + term2 ** 2

# 在固定 γ 的情况下，检查目标函数随 β 的变化
gamma_fixed = 283.7  # 论文结果
print(f"\n固定 γ={gamma_fixed}, 目标函数随 β 变化:")
for beta in np.arange(1.5, 3.5, 0.25):
    obj = wmle_objective([beta, gamma_fixed], X, J2, n)
    j3 = get_j3_linear(n, beta)
    print(f"  β={beta:.2f}: obj={obj:.6f}, J3={j3:.3f}")
