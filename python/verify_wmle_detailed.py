"""
Detailed WMLE verification - Check J3 interpolation and paper's exact calculation

Key observation:
- Paper says J3=1.759 when gamma=2, but Table 4 shows J3=1.758 for n=10, gamma=2.0
- Paper says: "at gamma_hat = 2, J3 = 1.759"
- But the final result is gamma_hat=2.29, so J3 should be interpolated

Let's try different J3 approaches.
"""

import numpy as np
from scipy.optimize import minimize

# Sample data from paper
X = np.array([310, 342, 353, 365, 383, 393, 403, 412, 451, 456])
n = len(X)

# Paper weights (n=10)
J1 = 0.967
J2 = 0.853

# Full J3 table from paper (n=10)
# gamma: 0.5, 1.0, 1.5, 2.0, 2.5
J3_TABLE_GAMMA = [0.5, 1.0, 1.5, 2.0, 2.5]
J3_TABLE_VALUES = [8.643, 3.365, 2.180, 1.758, 1.552]

def get_J3_interpolate(gamma):
    """Linear interpolation from Table 4"""
    if gamma <= 0.5:
        return J3_TABLE_VALUES[0]
    if gamma >= 2.5:
        return J3_TABLE_VALUES[-1]

    for i in range(len(J3_TABLE_GAMMA) - 1):
        if J3_TABLE_GAMMA[i] <= gamma <= J3_TABLE_GAMMA[i+1]:
            t = (gamma - J3_TABLE_GAMMA[i]) / (J3_TABLE_GAMMA[i+1] - J3_TABLE_GAMMA[i])
            return J3_TABLE_VALUES[i] + t * (J3_TABLE_VALUES[i+1] - J3_TABLE_VALUES[i])
    return 1.758

def wmle_objective(params, X, w2, j3_func):
    """Paper equation (4)"""
    gamma = params[0]
    alpha = params[1]

    if alpha >= X.min() - 1e-6 or gamma <= 0:
        return 1e10

    x_minus_alpha = X - alpha
    if np.any(x_minus_alpha <= 0):
        return 1e10

    log_x = np.log(x_minus_alpha)
    x_gamma = x_minus_alpha ** gamma

    sum_log = np.sum(log_x)
    sum_log_x_gamma = np.sum(log_x * x_gamma)
    sum_x_gamma = np.sum(x_gamma)

    term1 = w2 / gamma + sum_log / n - sum_log_x_gamma / sum_x_gamma

    sum_inv = np.sum(1.0 / x_minus_alpha)
    sum_x_gamma_minus1 = np.sum(x_minus_alpha ** (gamma - 1))

    w3 = j3_func(gamma)
    term2 = sum_inv / n * sum_x_gamma / sum_x_gamma_minus1 - w3

    return term1 ** 2 + term2 ** 2

def compute_beta(X, alpha, gamma, w1):
    """Algebraic solution for beta"""
    x_minus_alpha = X - alpha
    sum_x_gamma = np.sum(x_minus_alpha ** gamma)
    return (sum_x_gamma / (n * w1)) ** (1 / gamma)

print("=" * 70)
print("Detailed WMLE Verification")
print("=" * 70)

# Check J3 interpolation
print("\nJ3 interpolation check:")
print(f"  J3(0.5) = {get_J3_interpolate(0.5):.3f} (table: 8.643)")
print(f"  J3(1.0) = {get_J3_interpolate(1.0):.3f} (table: 3.365)")
print(f"  J3(1.5) = {get_J3_interpolate(1.5):.3f} (table: 2.180)")
print(f"  J3(2.0) = {get_J3_interpolate(2.0):.3f} (table: 1.758, paper says 1.759)")
print(f"  J3(2.29) = {get_J3_interpolate(2.29):.3f}")
print(f"  J3(2.5) = {get_J3_interpolate(2.5):.3f} (table: 1.552)")

print("\n" + "=" * 70)
print("Test different J3 approaches:")
print("=" * 70)

# Approach 1: J3 = gamma / (gamma - 1) (standard MLE)
print("\n1. Standard MLE: J3 = gamma/(gamma-1)")
result1 = minimize(
    lambda p: wmle_objective(p, X, w2=1.0, j3_func=lambda g: g/(g-1)),
    x0=np.array([2.0, 280.0]),
    method='Nelder-Mead',
    options={'maxiter': 1000}
)
if result1.success:
    g, a = result1.x
    b = compute_beta(X, a, g, w1=1.0)
    print(f"   Result: gamma={g:.2f}, alpha={a:.1f}, beta={b:.1f}")
    print(f"   Paper:  gamma=2.62, alpha=280.9, beta=119.0")

# Approach 2: Fixed J3 = 1.759 (paper's value at gamma=2)
print("\n2. Fixed J3 = 1.759 (not varying with gamma)")
result2 = minimize(
    lambda p: wmle_objective(p, X, w2=J2, j3_func=lambda g: 1.759),
    x0=np.array([2.0, 280.0]),
    method='Nelder-Mead',
    options={'maxiter': 1000}
)
if result2.success:
    g, a = result2.x
    b = compute_beta(X, a, g, w1=J1)
    print(f"   Result: gamma={g:.2f}, alpha={a:.1f}, beta={b:.1f}")
    print(f"   Paper:  gamma=2.29, alpha=283.7, beta=116.0")

# Approach 3: Interpolated J3 from Table 4
print("\n3. Interpolated J3 from Table 4")
result3 = minimize(
    lambda p: wmle_objective(p, X, w2=J2, j3_func=get_J3_interpolate),
    x0=np.array([2.0, 280.0]),
    method='Nelder-Mead',
    options={'maxiter': 1000}
)
if result3.success:
    g, a = result3.x
    b = compute_beta(X, a, g, w1=J1)
    print(f"   Result: gamma={g:.2f}, alpha={a:.1f}, beta={b:.1f}")
    print(f"   Paper:  gamma=2.29, alpha=283.7, beta=116.0")

# Approach 4: Try to find the J3 value that gives paper's exact result
print("\n4. Find J3 value that gives paper's result (gamma=2.29, alpha=283.7)")
gamma_target = 2.29
alpha_target = 283.7
x_minus_alpha = X - alpha_target
log_x = np.log(x_minus_alpha)
x_gamma = x_minus_alpha ** gamma_target

sum_log = np.sum(log_x)
sum_log_x_gamma = np.sum(log_x * x_gamma)
sum_x_gamma = np.sum(x_gamma)
sum_inv = np.sum(1.0 / x_minus_alpha)
sum_x_gamma_minus1 = np.sum(x_minus_alpha ** (gamma_target - 1))

# At optimum, both terms should be zero
# Term1 = 0 gives us an equation (already satisfied)
term1 = J2 / gamma_target + sum_log / n - sum_log_x_gamma / sum_x_gamma
print(f"   Term1 = {term1:.6f} (should be ~0 for optimum)")

# Term2 = 0 gives us: W3 = (sum_inv/n) * (sum_x_gamma/sum_x_gamma_minus1)
w3_needed = (sum_inv / n) * (sum_x_gamma / sum_x_gamma_minus1)
print(f"   To make Term2=0, we need J3 = {w3_needed:.3f}")
print(f"   Table gives J3(2.29) = {get_J3_interpolate(gamma_target):.3f}")
print(f"   Paper says J3(2.0) = 1.759")

# Compute beta at paper's result
beta_computed = compute_beta(X, alpha_target, gamma_target, w1=J1)
print(f"   Computed beta = {beta_computed:.1f} (paper: 116.0)")

# Approach 5: Check if paper might have used a different formula
print("\n5. Check alternative J3 formula (paper mentions MLE weight = gamma/(gamma-1))")
# Maybe paper used some correction to the MLE weight?
for correction in [1.0, 0.95, 0.90, 0.85]:
    result = minimize(
        lambda p: wmle_objective(p, X, w2=J2, j3_func=lambda g: correction * g/(g-1) if g > 1 else 10),
        x0=np.array([2.0, 280.0]),
        method='Nelder-Mead',
        options={'maxiter': 1000}
    )
    if result.success:
        g, a = result.x
        b = compute_beta(X, a, g, w1=J1)
        print(f"   J3 = {correction}*gamma/(gamma-1): gamma={g:.2f}, alpha={a:.1f}, beta={b:.1f}")

print("\n" + "=" * 70)
print("Key finding:")
print("=" * 70)
print(f"To match paper's result (gamma=2.29, alpha=283.7), we need J3={w3_needed:.3f}")
print(f"But Table 4 gives J3(2.29) = {get_J3_interpolate(gamma_target):.3f}")
print()
print("Possible explanations:")
print("1. Paper used more precise J3 values (not shown in truncated table)")
print("2. Paper used a different interpolation method")
print("3. There's a subtle difference in the optimization approach")
print("4. The small difference (~0.02) might be due to rounding in the paper")
