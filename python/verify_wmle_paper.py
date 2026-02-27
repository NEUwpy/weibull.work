"""
验证 WMLE 实现 - 使用论文 182-088 的确切样本

论文: Cousineau (2009) - Nearly unbiased estimators for the three-parameter Weibull distribution
论文 Section 4 数值例子:

样本: X = {310, 342, 353, 365, 383, 393, 403, 412, 451, 456}, n = 10
真值: γ=2 (形状), β=100 (尺度), α=300 (位置)

符号对应:
- 论文 γ (形状) → 代码 β (形状)
- 论文 β (尺度) → 代码 η (尺度)
- 论文 α (位置) → 代码 γ (位置)

论文结果:
- 迭代 MLE: γ̂=2.80, β̂=126.0, α̂=274.8
- 两步 MLE: γ̂=2.62, β̂=119.0, α̂=280.9
- WMLE: γ̂=2.29, β̂=116.0, α̂=283.7 (使用 J1=0.967, J2=0.853, J3 动态)
"""

import numpy as np
from scipy.optimize import minimize

# ============== 符号转换说明 ==============
# 论文: γ=形状, β=尺度, α=位置
# 代码: β=形状, η=尺度, γ=位置
#
# 本脚本变量名遵循代码约定:
# beta = 形状参数 (论文的 γ)
# eta = 尺度参数 (论文的 β)
# gamma = 位置参数 (论文的 α)

# ============== 论文的确切样本数据 ==============
X = np.array([310, 342, 353, 365, 383, 393, 403, 412, 451, 456])
n = len(X)

print("=" * 70)
print("WMLE 验证 - 使用论文 182-088 Section 4 的确切样本")
print("=" * 70)
print()
print(f"样本 X = {X.tolist()}")
print(f"n = {n}")
print()

# 论文真值 (转换为代码符号)
true_beta = 2.0   # 形状 (论文 γ)
true_eta = 100.0  # 尺度 (论文 β)
true_gamma = 300.0  # 位置 (论文 α)

# 论文结果 (转换为代码符号)
paper_mle_iter = {"beta": 2.80, "eta": 126.0, "gamma": 274.8}
paper_mle_twostep = {"beta": 2.62, "eta": 119.0, "gamma": 280.9}
paper_wmle = {"beta": 2.29, "eta": 116.0, "gamma": 283.7}

print("论文结果 (代码符号):")
print(f"  真值:     β={true_beta}, η={true_eta}, γ={true_gamma}")
print(f"  迭代MLE:  β={paper_mle_iter['beta']}, η={paper_mle_iter['eta']}, γ={paper_mle_iter['gamma']}")
print(f"  两步MLE:  β={paper_mle_twostep['beta']}, η={paper_mle_twostep['eta']}, γ={paper_mle_twostep['gamma']}")
print(f"  WMLE:     β={paper_wmle['beta']}, η={paper_wmle['eta']}, γ={paper_wmle['gamma']}")
print()

# ============== 权重表 (论文 Table 2, 3, 4) ==============
# Table 2: J1 (median of W1)
J1_TABLE = {
    1: 0.693, 2: 0.839, 3: 0.891, 4: 0.918, 5: 0.934,
    6: 0.945, 7: 0.953, 8: 0.959, 9: 0.963, 10: 0.967,
    11: 0.970, 12: 0.972, 13: 0.974, 14: 0.976, 15: 0.978,
    16: 0.979
}

# Table 3: J2 (median of W2)
J2_TABLE = {
    1: 0.000, 2: 0.275, 3: 0.517, 4: 0.638, 5: 0.711,
    6: 0.759, 7: 0.791, 8: 0.817, 9: 0.838, 10: 0.853,
    11: 0.867, 12: 0.877, 13: 0.886, 14: 0.895, 15: 0.902,
    16: 0.908
}

# Table 4: J3 (median of W3) - depends on n and shape parameter
# 格式: J3_TABLE[n][gamma_paper] 其中 gamma_paper 是论文的形状参数(即代码的beta)
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
    11: {0.5: 9.319, 1.0: 3.462, 1.5: 2.207, 2.0: 1.774, 2.5: 1.555},
    12: {0.5: 10.051, 1.0: 3.560, 1.5: 2.239, 2.0: 1.782, 2.5: 1.565},
    13: {0.5: 10.746, 1.0: 3.642, 1.5: 2.262, 2.0: 1.793, 2.5: 1.570},
    14: {0.5: 11.379, 1.0: 3.713, 1.5: 2.285, 2.0: 1.804, 2.5: 1.578},
    15: {0.5: 12.069, 1.0: 3.780, 1.5: 2.301, 2.0: 1.813, 2.5: 1.581},
    16: {0.5: 12.743, 1.0: 3.854, 1.5: 2.324, 2.0: 1.820, 2.5: 1.586},
}

GAMMA_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5]

def get_j3(n, beta):
    """
    获取 J3 权重 (W3 的中位数)
    n: 样本大小
    beta: 形状参数 (代码符号, 论文中叫 γ)
    """
    if n > 16:
        # 对于 n > 16, 使用渐近值
        if beta <= 1:
            return 2.0  # 近似值
        return beta / (beta - 1)

    j3_at_n = J3_TABLE.get(n, J3_TABLE[16])

    # 边界情况
    if beta <= 0.5:
        return j3_at_n[0.5]
    if beta >= 2.5:
        return j3_at_n[2.5]

    # 线性插值
    for i in range(len(GAMMA_VALUES) - 1):
        g_low, g_high = GAMMA_VALUES[i], GAMMA_VALUES[i + 1]
        if g_low <= beta <= g_high:
            t = (beta - g_low) / (g_high - g_low)
            return j3_at_n[g_low] + t * (j3_at_n[g_high] - j3_at_n[g_low])

    return j3_at_n[2.0]


# ============== 目标函数 ==============

def mle_objective(params, X):
    """
    MLE 目标函数 (论文方程 2, A.2, A.3)

    params = [beta, gamma] (形状, 位置)
    eta 通过代数求解
    """
    beta, gamma = params
    n = len(X)

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

    # 论文方程 A.2: 1/γ + (1/n)Σlog(xi-α) - Σlog(xi-α)(xi-α)^γ / Σ(xi-α)^γ = 0
    # 代码符号: 1/beta + (1/n)Σlog(xi-gamma) - Σlog(xi-gamma)(xi-gamma)^beta / Σ(xi-gamma)^beta = 0
    term1 = 1/beta + sum_log/n - sum_log_x_beta/sum_x_beta

    sum_inv = np.sum(1.0 / x_adj)
    sum_x_beta_minus1 = np.sum(x_adj ** (beta - 1))

    # 论文方程 A.3: (1/n)Σ1/(xi-α) × Σ(xi-α)^γ / Σ(xi-α)^(γ-1) - γ/(γ-1) = 0
    # 代码符号: (1/n)Σ1/(xi-gamma) × Σ(xi-gamma)^beta / Σ(xi-gamma)^(beta-1) - beta/(beta-1) = 0
    if beta <= 1:
        term2 = 1e10
    else:
        mle_weight = beta / (beta - 1)
        term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - mle_weight

    return term1 ** 2 + term2 ** 2


def wmle_objective(params, X, w2, n):
    """
    WMLE 目标函数 (论文方程 3, 4)

    params = [beta, gamma] (形状, 位置)
    w2: 静态权重 J2
    w3: 动态权重 J3, 依赖于 beta

    论文方程 (4):
    argmin_{α,γ} [
        (W2/γ + (1/n)Σlog(xi-α) - Σlog(xi-α)(xi-α)^γ / Σ(xi-α)^γ)^2
        + ((1/n)Σ1/(xi-α) × Σ(xi-α)^γ / Σ(xi-α)^(γ-1) - W3)^2
    ]
    """
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

    # 论文方程 4 第一部分 (使用 W2 权重)
    # W2/γ + (1/n)Σlog(xi-α) - Σlog(xi-α)(xi-α)^γ / Σ(xi-α)^γ
    # 代码符号: w2/beta + (1/n)Σlog(xi-gamma) - ...
    term1 = w2/beta + sum_log/n - sum_log_x_beta/sum_x_beta

    sum_inv = np.sum(1.0 / x_adj)
    sum_x_beta_minus1 = np.sum(x_adj ** (beta - 1))

    # 动态权重 W3 (J3)
    w3 = get_j3(n, beta)

    # 论文方程 4 第二部分 (使用 W3 权重)
    # (1/n)Σ1/(xi-α) × Σ(xi-α)^γ / Σ(xi-α)^(γ-1) - W3
    # 代码符号: (1/n)Σ1/(xi-gamma) × Σ(xi-gamma)^beta / Σ(xi-gamma)^(beta-1) - w3
    term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - w3

    return term1 ** 2 + term2 ** 2


def compute_eta(X, gamma, beta, w1=1.0):
    """
    代数求解尺度参数 eta (论文方程 A.1 / B.2)

    论文: β = [ (1/(n×W1)) Σ(xi-α)^γ ]^(1/γ)
    代码: eta = [ (1/(n×w1)) Σ(xi-gamma)^beta ]^(1/beta)
    """
    x_adj = X - gamma
    sum_x_beta = np.sum(x_adj ** beta)
    n = len(X)
    return (sum_x_beta / (n * w1)) ** (1 / beta)


# ============== 测试 ==============

print("-" * 70)
print("测试 1: 两步 MLE (论文方程 2)")
print("-" * 70)

# 初始猜测
beta_init = 2.0
gamma_init = X[0] * 0.9  # 279

result_mle = minimize(
    lambda p: mle_objective(p, X),
    x0=np.array([beta_init, gamma_init]),
    method='Nelder-Mead',
    options={'maxiter': 2000, 'xatol': 1e-8, 'fatol': 1e-8}
)

if result_mle.success:
    beta_mle, gamma_mle = result_mle.x
    eta_mle = compute_eta(X, gamma_mle, beta_mle, w1=1.0)
    print(f"我们的结果: β={beta_mle:.2f}, η={eta_mle:.1f}, γ={gamma_mle:.1f}")
    print(f"论文结果:   β={paper_mle_twostep['beta']}, η={paper_mle_twostep['eta']}, γ={paper_mle_twostep['gamma']}")
    print(f"差异:       Δβ={beta_mle-paper_mle_twostep['beta']:.2f}, Δη={eta_mle-paper_mle_twostep['eta']:.1f}, Δγ={gamma_mle-paper_mle_twostep['gamma']:.1f}")
else:
    print("MLE 优化失败:", result_mle.message)

print()

print("-" * 70)
print("测试 2: WMLE (论文方程 3, 使用 J1, J2, J3)")
print("-" * 70)

# 论文中的权重
J1 = J1_TABLE[n]  # 0.967
J2 = J2_TABLE[n]  # 0.853

print(f"静态权重: J1={J1}, J2={J2}")
print(f"动态权重 J3: 依赖于 β, 例如 β=2 时 J3={get_j3(n, 2.0):.3f}")
print()

result_wmle = minimize(
    lambda p: wmle_objective(p, X, J2, n),
    x0=np.array([beta_init, gamma_init]),
    method='Nelder-Mead',
    options={'maxiter': 2000, 'xatol': 1e-8, 'fatol': 1e-8}
)

if result_wmle.success:
    beta_wmle, gamma_wmle = result_wmle.x
    eta_wmle = compute_eta(X, gamma_wmle, beta_wmle, w1=J1)
    j3_at_result = get_j3(n, beta_wmle)

    print(f"我们的结果: β={beta_wmle:.2f}, η={eta_wmle:.1f}, γ={gamma_wmle:.1f}")
    print(f"论文结果:   β={paper_wmle['beta']}, η={paper_wmle['eta']}, γ={paper_wmle['gamma']}")
    print(f"差异:       Δβ={beta_wmle-paper_wmle['beta']:.2f}, Δη={eta_wmle-paper_wmle['eta']:.1f}, Δγ={gamma_wmle-paper_wmle['gamma']:.1f}")
    print()
    print(f"最终 J3 (β={beta_wmle:.2f}): {j3_at_result:.3f}")
else:
    print("WMLE 优化失败:", result_wmle.message)

print()

# ============== 诊断: 检查论文结果处的目标函数值 ==============
print("-" * 70)
print("诊断: 在论文结果处检查目标函数值")
print("-" * 70)

# 论文 WMLE 结果
paper_beta = paper_wmle['beta']
paper_gamma = paper_wmle['gamma']
paper_eta = paper_wmle['eta']

mle_val_at_paper = mle_objective([paper_beta, paper_gamma], X)
wmle_val_at_paper = wmle_objective([paper_beta, paper_gamma], X, J2, n)

print(f"论文 WMLE 结果处 (β={paper_beta}, γ={paper_gamma}):")
print(f"  MLE 目标函数值:  {mle_val_at_paper:.6f}")
print(f"  WMLE 目标函数值: {wmle_val_at_paper:.6f}")

# 我们的结果
if result_wmle.success:
    mle_val_at_ours = mle_objective([beta_wmle, gamma_wmle], X)
    wmle_val_at_ours = wmle_objective([beta_wmle, gamma_wmle], X, J2, n)
    print(f"\n我们的 WMLE 结果处 (β={beta_wmle:.2f}, γ={gamma_wmle:.1f}):")
    print(f"  MLE 目标函数值:  {mle_val_at_ours:.6f}")
    print(f"  WMLE 目标函数值: {wmle_val_at_ours:.6f}")

# 目标函数各分量分析
print()
print("-" * 70)
print("目标函数分量分析 (论文方程 4)")
print("-" * 70)

def analyze_objective(beta, gamma, X, w2, n):
    x_adj = X - gamma
    log_x = np.log(x_adj)
    x_beta = x_adj ** beta

    sum_log = np.sum(log_x)
    sum_log_x_beta = np.sum(log_x * x_beta)
    sum_x_beta = np.sum(x_beta)

    term1 = w2/beta + sum_log/n - sum_log_x_beta/sum_x_beta

    sum_inv = np.sum(1.0 / x_adj)
    sum_x_beta_minus1 = np.sum(x_adj ** (beta - 1))
    w3 = get_j3(n, beta)

    term2 = sum_inv/n * sum_x_beta/sum_x_beta_minus1 - w3

    return term1, term2, w3

print(f"\n论文 WMLE 结果 (β={paper_beta}, γ={paper_gamma}):")
t1_paper, t2_paper, w3_paper = analyze_objective(paper_beta, paper_gamma, X, J2, n)
print(f"  term1 = {t1_paper:.6f}")
print(f"  term2 = {t2_paper:.6f}")
print(f"  J3 = {w3_paper:.3f}")
print(f"  目标函数 = {t1_paper**2 + t2_paper**2:.6f}")

if result_wmle.success:
    print(f"\n我们的 WMLE 结果 (β={beta_wmle:.2f}, γ={gamma_wmle:.1f}):")
    t1_ours, t2_ours, w3_ours = analyze_objective(beta_wmle, gamma_wmle, X, J2, n)
    print(f"  term1 = {t1_ours:.6f}")
    print(f"  term2 = {t2_ours:.6f}")
    print(f"  J3 = {w3_ours:.3f}")
    print(f"  目标函数 = {t1_ours**2 + t2_ours**2:.6f}")

print()
print("=" * 70)
print("结论")
print("=" * 70)
print("""
如果我们的结果与论文结果一致,说明 WMLE 实现正确。
如果差异较大,需要检查:
1. J3 权重的插值计算
2. 目标函数的实现细节
3. 优化器的设置
""")
