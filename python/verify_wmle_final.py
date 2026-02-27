"""
Compare current WMLE implementation with paper-correct implementation

Problem: Current get_weight_j3 uses a rough approximation
Solution: Use paper's Table 4 values with interpolation
"""

import numpy as np
from scipy.optimize import minimize

# Sample data from paper
X = np.array([310, 342, 353, 365, 383, 393, 403, 412, 451, 456])
n = len(X)

J1 = 0.967
J2 = 0.853

# ========== Current (problematic) implementation ==========
def get_weight_j3_old(n, gamma):
    """Current approximate formula - NOT ACCURATE!"""
    if gamma <= 1:
        return 1.5 + 0.5 * np.log10(n)
    mle_weight = gamma / (gamma - 1)
    correction = max(0.1, 0.3 * np.exp(-n/10))
    return mle_weight * (1 - correction)

# ========== Paper-correct implementation ==========
# Full J3 table from paper Table 4
J3_TABLE = {
    # n: {gamma: J3}
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

def get_weight_j3_table(n, gamma):
    """Use paper's Table 4 with bilinear interpolation"""
    # Clamp n
    if n < 1:
        n = 1
    if n > 16:
        # For n > 16, extrapolate towards asymptotic value
        # As n -> infinity, J3 -> gamma/(gamma-1)
        if gamma <= 1:
            return 1.5 + 0.5 * np.log10(n)
        return gamma / (gamma - 1)

    # Get table bounds
    if n in J3_TABLE:
        j3_at_n = J3_TABLE[n]
    else:
        # Linear interpolation in n (not implemented, use closest)
        closest_n = min(J3_TABLE.keys(), key=lambda x: abs(x - n))
        j3_at_n = J3_TABLE[closest_n]

    # Linear interpolation in gamma
    if gamma <= 0.5:
        return j3_at_n[0.5]
    if gamma >= 2.5:
        return j3_at_n[2.5]

    for i in range(len(GAMMA_VALUES) - 1):
        if GAMMA_VALUES[i] <= gamma <= GAMMA_VALUES[i+1]:
            t = (gamma - GAMMA_VALUES[i]) / (GAMMA_VALUES[i+1] - GAMMA_VALUES[i])
            return j3_at_n[GAMMA_VALUES[i]] + t * (j3_at_n[GAMMA_VALUES[i+1]] - j3_at_n[GAMMA_VALUES[i]])

    return j3_at_n[2.0]

def wmle_objective(params, X, w2, j3_func):
    """Paper equation (4)"""
    gamma = params[0]  # shape
    alpha = params[1]  # location

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
    x_minus_alpha = X - alpha
    sum_x_gamma = np.sum(x_minus_alpha ** gamma)
    return (sum_x_gamma / (n * w1)) ** (1 / gamma)

print("=" * 70)
print("WMLE Implementation Comparison")
print("=" * 70)
print(f"Sample: X = {X}")
print(f"n = {n}, J1 = {J1}, J2 = {J2}")
print(f"True params: gamma=2 (shape), beta=100 (scale), alpha=300 (location)")
print()

# Test 1: Current (approximate) J3
print("-" * 70)
print("Test 1: Current implementation (approximate J3)")
print("-" * 70)
result1 = minimize(
    lambda p: wmle_objective(p, X, J2, lambda g: get_weight_j3_old(n, g)),
    x0=np.array([2.0, 280.0]),
    method='Nelder-Mead',
    options={'maxiter': 1000}
)
if result1.success:
    g, a = result1.x
    b = compute_beta(X, a, g, J1)
    j3_at_result = get_weight_j3_old(n, g)
    print(f"Result: gamma={g:.2f}, alpha={a:.1f}, beta={b:.1f}")
    print(f"J3 at gamma={g:.2f}: {j3_at_result:.3f}")

# Test 2: Paper-correct J3 (using table)
print()
print("-" * 70)
print("Test 2: Paper-correct implementation (table-based J3)")
print("-" * 70)
result2 = minimize(
    lambda p: wmle_objective(p, X, J2, lambda g: get_weight_j3_table(n, g)),
    x0=np.array([2.0, 280.0]),
    method='Nelder-Mead',
    options={'maxiter': 1000}
)
if result2.success:
    g, a = result2.x
    b = compute_beta(X, a, g, J1)
    j3_at_result = get_weight_j3_table(n, g)
    print(f"Result: gamma={g:.2f}, alpha={a:.1f}, beta={b:.1f}")
    print(f"J3 at gamma={g:.2f}: {j3_at_result:.3f}")

print()
print("-" * 70)
print("Paper result: gamma=2.29, alpha=283.7, beta=116.0")
print("-" * 70)

# Show J3 comparison table
print()
print("=" * 70)
print("J3 value comparison table (n=10)")
print("=" * 70)
print(f"{'gamma':>8} {'Current':>12} {'Table':>12} {'Diff':>12}")
print("-" * 48)
for g in [0.5, 1.0, 1.5, 2.0, 2.5]:
    curr = get_weight_j3_old(10, g)
    table = get_weight_j3_table(10, g)
    print(f"{g:>8.1f} {curr:>12.3f} {table:>12.3f} {abs(curr-table):>12.3f}")

print()
print("=" * 70)
print("Conclusion")
print("=" * 70)
print("""
The current get_weight_j3() function uses an approximate formula that is
not accurate for small gamma values. This causes errors in WMLE estimation.

RECOMMENDATION: Replace the approximate formula with table lookup and
interpolation based on paper's Table 4.
""")
