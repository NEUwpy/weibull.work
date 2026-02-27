"""
Verify WMLE implementation using paper 182-088 data and weights

Paper data:
- Sample X = {310, 342, 353, 365, 383, 393, 403, 412, 451, 456}, n = 10
- True params: gamma=2 (shape), beta=100 (scale), alpha=300 (location)

Paper WMLE result (using J1, J2, J3):
- {gamma_hat, alpha_hat} = {2.29, 283.7}, beta_hat = 116.0
- Weights: J1=0.967, J2=0.853, J3=1.759 (when gamma=2, n=10)

Note: Paper uses different notation:
- gamma (paper) = shape parameter = beta (Weibull standard)
- alpha (paper) = location parameter = gamma (Weibull standard)
- beta (paper) = scale parameter = eta (Weibull standard)
"""

import numpy as np
from scipy.optimize import minimize

# Sample data from paper
X = np.array([310, 342, 353, 365, 383, 393, 403, 412, 451, 456])
n = len(X)

# Paper weights (n=10)
J1 = 0.967
J2 = 0.853
# J3 depends on gamma, paper says J3=1.759 when gamma=2

def get_J3_from_table(gamma, n=10):
    """
    Get J3 from paper Table 4 (n=10)
    Table data:
    gamma = 0.5: J3 = 8.643
    gamma = 1.0: J3 = 3.365
    gamma = 1.5: J3 = 2.180
    gamma = 2.0: J3 = 1.758 (paper says 1.759)
    gamma = 2.5: J3 = 1.552
    """
    gamma_values = [0.5, 1.0, 1.5, 2.0, 2.5]
    j3_values = [8.643, 3.365, 2.180, 1.758, 1.552]

    if gamma <= 0.5:
        return j3_values[0]
    if gamma >= 2.5:
        return j3_values[-1]

    for i in range(len(gamma_values) - 1):
        if gamma_values[i] <= gamma <= gamma_values[i+1]:
            t = (gamma - gamma_values[i]) / (gamma_values[i+1] - gamma_values[i])
            return j3_values[i] + t * (j3_values[i+1] - j3_values[i])

    return 1.758  # fallback

def wmle_objective_paper(params, X, w2, use_table_j3=False):
    """
    Paper equation (4):

    argmin_{alpha,gamma} [
        (W2/gamma + (1/n)*sum(log(xi-alpha)) - sum(log(xi-alpha)*(xi-alpha)^gamma) / sum((xi-alpha)^gamma))^2
        + ((1/n)*sum(1/(xi-alpha)) * sum((xi-alpha)^gamma) / sum((xi-alpha)^(gamma-1)) - W3)^2
    ]
    """
    gamma = params[0]  # shape (paper notation)
    alpha = params[1]  # location (paper notation)

    # Constraints: alpha < min(X), gamma > 0
    if alpha >= X.min() - 1e-6 or gamma <= 0:
        return 1e10

    x_minus_alpha = X - alpha
    if np.any(x_minus_alpha <= 0):
        return 1e10

    # Term 1
    log_x = np.log(x_minus_alpha)
    x_gamma = x_minus_alpha ** gamma

    sum_log = np.sum(log_x)
    sum_log_x_gamma = np.sum(log_x * x_gamma)
    sum_x_gamma = np.sum(x_gamma)

    term1 = w2 / gamma + sum_log / n - sum_log_x_gamma / sum_x_gamma

    # Term 2
    sum_inv = np.sum(1.0 / x_minus_alpha)
    sum_x_gamma_minus1 = np.sum(x_minus_alpha ** (gamma - 1))

    # W3 depends on gamma
    if use_table_j3:
        w3 = get_J3_from_table(gamma, n)
    else:
        w3 = gamma / (gamma - 1)  # standard MLE weight

    term2 = sum_inv / n * sum_x_gamma / sum_x_gamma_minus1 - w3

    return term1 ** 2 + term2 ** 2

def compute_beta(X, alpha, gamma, w1):
    """
    Paper equation (3) - algebraic solution for beta:
    beta = [ (1/(n*W1)) * sum((xi-alpha)^gamma) ]^(1/gamma)
    """
    x_minus_alpha = X - alpha
    sum_x_gamma = np.sum(x_minus_alpha ** gamma)
    beta = (sum_x_gamma / (n * w1)) ** (1 / gamma)
    return beta

print("=" * 60)
print("WMLE Verification - Using Paper 182-088 Data")
print("=" * 60)
print(f"Sample X = {X}")
print(f"n = {n}")
print(f"True params: gamma=2 (shape), beta=100 (scale), alpha=300 (location)")
print()

# Test 1: Standard MLE (W1=1, W2=1, W3=gamma/(gamma-1))
print("-" * 60)
print("Test 1: Standard MLE (W1=1, W2=1, W3=gamma/(gamma-1))")
print("-" * 60)

result_mle = minimize(
    lambda p: wmle_objective_paper(p, X, w2=1.0, use_table_j3=False),
    x0=np.array([2.5, 280.0]),
    method='Nelder-Mead',
    options={'maxiter': 1000}
)

if result_mle.success:
    gamma_mle, alpha_mle = result_mle.x
    beta_mle = compute_beta(X, alpha_mle, gamma_mle, w1=1.0)
    print(f"Optimization SUCCESS!")
    print(f"gamma_hat (shape) = {gamma_mle:.2f}")
    print(f"alpha_hat (location) = {alpha_mle:.1f}")
    print(f"beta_hat (scale) = {beta_mle:.1f}")
    print(f"Paper MLE result: gamma_hat=2.62, alpha_hat=280.9, beta_hat=119.0")
else:
    print(f"Optimization FAILED: {result_mle.message}")

print()

# Test 2: WMLE using paper weights J1, J2, and table J3
print("-" * 60)
print("Test 2: WMLE (J1=0.967, J2=0.853, J3 from table)")
print("-" * 60)

result_wmle = minimize(
    lambda p: wmle_objective_paper(p, X, w2=J2, use_table_j3=True),
    x0=np.array([2.0, 280.0]),
    method='Nelder-Mead',
    options={'maxiter': 1000}
)

if result_wmle.success:
    gamma_wmle, alpha_wmle = result_wmle.x
    beta_wmle = compute_beta(X, alpha_wmle, gamma_wmle, w1=J1)
    j3_at_result = get_J3_from_table(gamma_wmle, n)
    print(f"Optimization SUCCESS!")
    print(f"gamma_hat (shape) = {gamma_wmle:.2f}")
    print(f"alpha_hat (location) = {alpha_wmle:.1f}")
    print(f"beta_hat (scale) = {beta_wmle:.1f}")
    print(f"J3(gamma_hat={gamma_wmle:.2f}) = {j3_at_result:.3f}")
    print()
    print(f"Paper WMLE result: gamma_hat=2.29, alpha_hat=283.7, beta_hat=116.0")
else:
    print(f"Optimization FAILED: {result_wmle.message}")

print()

# Test 3: Directly verify objective function at paper's result
print("-" * 60)
print("Test 3: Verify objective function at paper's result")
print("-" * 60)

paper_gamma = 2.29
paper_alpha = 283.7
paper_beta = 116.0

# Verify beta calculation
computed_beta = compute_beta(X, paper_alpha, paper_gamma, w1=J1)
print(f"Paper gives: gamma=2.29, alpha=283.7, beta=116.0")
print(f"Computed beta (J1=0.967): {computed_beta:.1f}")

# Verify objective function value
obj_val = wmle_objective_paper([paper_gamma, paper_alpha], X, w2=J2, use_table_j3=True)
print(f"Objective function value: {obj_val:.6f}")

# J3 at gamma=2.29
j3_at_229 = get_J3_from_table(2.29, n)
print(f"J3(gamma=2.29) = {j3_at_229:.3f}")

print()

# Test 4: Different initial values
print("-" * 60)
print("Test 4: Try different initial values")
print("-" * 60)

initial_guesses = [
    [2.0, 280.0],
    [2.5, 285.0],
    [1.5, 275.0],
    [3.0, 290.0],
]

for guess in initial_guesses:
    result = minimize(
        lambda p: wmle_objective_paper(p, X, w2=J2, use_table_j3=True),
        x0=np.array(guess),
        method='Nelder-Mead',
        options={'maxiter': 1000}
    )
    if result.success:
        g, a = result.x
        b = compute_beta(X, a, g, w1=J1)
        print(f"Initial {guess} -> gamma={g:.2f}, alpha={a:.1f}, beta={b:.1f}, obj={result.fun:.6f}")
    else:
        print(f"Initial {guess} -> Optimization FAILED")

print()

# Test 5: Detailed breakdown at paper's solution
print("-" * 60)
print("Test 5: Detailed breakdown at gamma=2.29, alpha=283.7")
print("-" * 60)

gamma = 2.29
alpha = 283.7
x_minus_alpha = X - alpha
log_x = np.log(x_minus_alpha)
x_gamma = x_minus_alpha ** gamma

sum_log = np.sum(log_x)
sum_log_x_gamma = np.sum(log_x * x_gamma)
sum_x_gamma = np.sum(x_gamma)
sum_inv = np.sum(1.0 / x_minus_alpha)
sum_x_gamma_minus1 = np.sum(x_minus_alpha ** (gamma - 1))

w3 = get_J3_from_table(gamma, n)

term1 = J2 / gamma + sum_log / n - sum_log_x_gamma / sum_x_gamma
term2 = sum_inv / n * sum_x_gamma / sum_x_gamma_minus1 - w3

print(f"sum_log = {sum_log:.4f}")
print(f"sum_log_x_gamma = {sum_log_x_gamma:.4f}")
print(f"sum_x_gamma = {sum_x_gamma:.4f}")
print(f"sum_inv = {sum_inv:.6f}")
print(f"sum_x_gamma_minus1 = {sum_x_gamma_minus1:.6f}")
print()
print(f"J2/gamma = {J2/gamma:.4f}")
print(f"sum_log/n = {sum_log/n:.4f}")
print(f"sum_log_x_gamma/sum_x_gamma = {sum_log_x_gamma/sum_x_gamma:.4f}")
print(f"Term 1 = {term1:.6f}")
print()
print(f"J3 (from table) = {w3:.3f}")
print(f"sum_inv/n = {sum_inv/n:.6f}")
print(f"sum_x_gamma/sum_x_gamma_minus1 = {sum_x_gamma/sum_x_gamma_minus1:.4f}")
print(f"(sum_inv/n)*(sum_x_gamma/sum_x_gamma_minus1) = {sum_inv/n * sum_x_gamma/sum_x_gamma_minus1:.4f}")
print(f"Term 2 = {term2:.6f}")
print()
print(f"Objective = Term1^2 + Term2^2 = {term1**2 + term2**2:.6f}")
