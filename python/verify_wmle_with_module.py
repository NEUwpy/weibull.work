"""
验证 WMLE 实现 - 使用论文 182-088 的确切样本

论文 Section 4 数值例子:
样本: X = {310, 342, 353, 365, 383, 393, 403, 412, 451, 456}, n = 10
真值: γ=2 (形状), β=100 (尺度), α=300 (位置)

符号对应 (论文 → 代码):
- γ (形状) → beta
- β (尺度) → eta
- α (位置) → gamma

论文结果:
- 迭代 MLE: γ̂=2.80, β̂=126.0, α̂=274.8
- 两步 MLE: γ̂=2.62, β̂=119.0, α̂=280.9
- WMLE: γ̂=2.29, β̂=116.0, α̂=283.7
"""

import sys
sys.path.insert(0, '.')
import numpy as np
from methods.wmle import WMLE, get_weight_j1, get_weight_j2, get_weight_j3

# 论文样本数据
X = [310, 342, 353, 365, 383, 393, 403, 412, 451, 456]
n = len(X)

# 论文真值 (论文符号 → 代码符号)
# 论文: γ=2 (形状), β=100 (尺度), α=300 (位置)
# 代码: beta=2 (形状), eta=100 (尺度), gamma=300 (位置)
true_beta = 2.0    # 形状参数
true_eta = 100.0   # 尺度参数
true_gamma = 300.0 # 位置参数

# 论文结果 (代码符号)
paper_wmle = {"beta": 2.29, "eta": 116.0, "gamma": 283.7}

print("=" * 70)
print("WMLE 验证 - 使用论文 182-088 Section 4 的样本")
print("=" * 70)
print()
print(f"样本 X = {X}")
print(f"n = {n}")
print()
print(f"真值: beta={true_beta}, eta={true_eta}, gamma={true_gamma}")
print(f"论文 WMLE 结果: beta={paper_wmle['beta']}, eta={paper_wmle['eta']}, gamma={paper_wmle['gamma']}")
print()

# 显示权重
J1 = get_weight_j1(n)
J2 = get_weight_j2(n)
print(f"权重: J1={J1}, J2={J2}")
print(f"J3 (beta=2.0时): {get_weight_j3(n, 2.0):.3f}")
print(f"J3 (beta=2.29时): {get_weight_j3(n, 2.29):.3f}")
print()

# 运行 WMLE
print("-" * 70)
print("运行 WMLE 估计")
print("-" * 70)

wmle = WMLE(X)
result = wmle.run(trace=True)

beta_hat = result[0]
eta_hat = result[1]
gamma_hat = result[2]
r2 = result[3]

print()
print(f"我们的结果: beta={beta_hat:.4f}, eta={eta_hat:.2f}, gamma={gamma_hat:.2f}, R2={r2:.4f}")
print(f"论文结果:   beta={paper_wmle['beta']}, eta={paper_wmle['eta']}, gamma={paper_wmle['gamma']}")
print()
print(f"差异: Delta_beta={beta_hat - paper_wmle['beta']:.4f}, Delta_eta={eta_hat - paper_wmle['eta']:.2f}, Delta_gamma={gamma_hat - paper_wmle['gamma']:.2f}")
print()

# 检查是否接近
beta_close = abs(beta_hat - paper_wmle['beta']) < 0.1
eta_close = abs(eta_hat - paper_wmle['eta']) < 5
gamma_close = abs(gamma_hat - paper_wmle['gamma']) < 5

print("=" * 70)
print("验证结果")
print("=" * 70)
if beta_close and eta_close and gamma_close:
    print("SUCCESS: 结果与论文一致!")
else:
    print("WARNING: 结果与论文有差异")
    if not beta_close:
        print(f"  beta 差异较大: {beta_hat:.4f} vs {paper_wmle['beta']}")
    if not eta_close:
        print(f"  eta 差异较大: {eta_hat:.2f} vs {paper_wmle['eta']}")
    if not gamma_close:
        print(f"  gamma 差异较大: {gamma_hat:.2f} vs {paper_wmle['gamma']}")

# 显示最终使用的 J3
final_j3 = get_weight_j3(n, beta_hat)
print(f"\n最终 J3 (beta={beta_hat:.4f}): {final_j3:.4f}")
