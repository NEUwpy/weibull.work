"""
Weighted Maximum Likelihood Estimation (WMLE)

Algorithm Documentation: ../../src/content/algorithms/wmle.md
Reference: Cousineau (2009), Paper 182-088

This implementation uses the official weights from:
https://github.com/dcousin3/wMLE

Weight tables are embedded (no external files needed).

Symbol mapping (paper -> system):
  - paper gamma (shape) -> system beta
  - paper beta (scale) -> system eta
  - paper alpha (location) -> system gamma
"""

import numpy as np
from scipy.optimize import minimize
from scipy.special import digamma
from base import WeibullBase

# ============================================================================
# J1 Weight Table (median of W1)
# Source: https://github.com/dcousin3/wMLE/weigths/J1.tsv
# Monte Carlo simulation with 2^20 replicates
# ============================================================================
WEIGHT_TABLE_J1 = {
    1: 0.693, 2: 0.840, 3: 0.892, 4: 0.918, 5: 0.935,
    6: 0.944, 7: 0.953, 8: 0.959, 9: 0.964, 10: 0.967,
    11: 0.970, 12: 0.972, 13: 0.974, 14: 0.976, 15: 0.978,
    16: 0.979, 17: 0.981, 18: 0.982, 19: 0.982, 20: 0.983,
    21: 0.985, 22: 0.985, 23: 0.986, 24: 0.986, 25: 0.987,
    26: 0.987, 27: 0.988, 28: 0.988, 29: 0.989, 30: 0.989,
    31: 0.989, 32: 0.990, 33: 0.990, 34: 0.990, 35: 0.990,
    36: 0.991, 37: 0.991, 38: 0.991, 39: 0.991, 40: 0.992,
    41: 0.992, 42: 0.992, 43: 0.992, 44: 0.992, 45: 0.993,
    46: 0.993, 47: 0.993, 48: 0.993, 49: 0.994, 50: 0.993,
    51: 0.994, 52: 0.993, 53: 0.994, 54: 0.994, 55: 0.994,
    56: 0.994, 57: 0.994, 58: 0.994, 59: 0.994, 60: 0.994,
    61: 0.995, 62: 0.995, 63: 0.995, 64: 0.995, 65: 0.995,
    66: 0.995, 67: 0.995, 68: 0.995, 69: 0.995, 70: 0.995,
    71: 0.995, 72: 0.995, 73: 0.996, 74: 0.995, 75: 0.996,
    76: 0.996, 77: 0.995, 78: 0.996, 79: 0.996, 80: 0.996,
    81: 0.996, 82: 0.996, 83: 0.996, 84: 0.996, 85: 0.996,
    86: 0.996, 87: 0.996, 88: 0.996, 89: 0.996, 90: 0.996,
    91: 0.996, 92: 0.996, 93: 0.997, 94: 0.997, 95: 0.997,
    96: 0.997, 97: 0.997, 98: 0.997, 99: 0.997, 100: 0.997,
}

# ============================================================================
# J2 Weight Table (median of W2)
# Source: https://github.com/dcousin3/wMLE/weigths/J2.tsv
# ============================================================================
WEIGHT_TABLE_J2 = {
    1: 0.000, 2: 0.275, 3: 0.518, 4: 0.639, 5: 0.709,
    6: 0.758, 7: 0.792, 8: 0.818, 9: 0.838, 10: 0.853,
    11: 0.866, 12: 0.877, 13: 0.886, 14: 0.894, 15: 0.901,
    16: 0.907, 17: 0.912, 18: 0.918, 19: 0.922, 20: 0.926,
    21: 0.929, 22: 0.932, 23: 0.935, 24: 0.938, 25: 0.940,
    26: 0.943, 27: 0.944, 28: 0.947, 29: 0.948, 30: 0.950,
    31: 0.952, 32: 0.953, 33: 0.954, 34: 0.956, 35: 0.958,
    36: 0.959, 37: 0.960, 38: 0.961, 39: 0.962, 40: 0.962,
    41: 0.964, 42: 0.965, 43: 0.965, 44: 0.966, 45: 0.967,
    46: 0.968, 47: 0.968, 48: 0.969, 49: 0.970, 50: 0.970,
    51: 0.970, 52: 0.971, 53: 0.972, 54: 0.972, 55: 0.973,
    56: 0.974, 57: 0.974, 58: 0.974, 59: 0.975, 60: 0.975,
    61: 0.976, 62: 0.975, 63: 0.977, 64: 0.976, 65: 0.977,
    66: 0.977, 67: 0.978, 68: 0.977, 69: 0.978, 70: 0.978,
    71: 0.979, 72: 0.979, 73: 0.979, 74: 0.980, 75: 0.980,
    76: 0.980, 77: 0.980, 78: 0.980, 79: 0.981, 80: 0.981,
    81: 0.982, 82: 0.982, 83: 0.982, 84: 0.982, 85: 0.982,
    86: 0.982, 87: 0.983, 88: 0.983, 89: 0.983, 90: 0.983,
    91: 0.983, 92: 0.984, 93: 0.984, 94: 0.984, 95: 0.984,
    96: 0.984, 97: 0.984, 98: 0.985, 99: 0.985, 100: 0.985,
}

# ============================================================================
# J3 Weight Table (median of W3)
# Source: https://github.com/dcousin3/wMLE/weigths/J3.tsv
# Note: J3 depends on both n and gamma (shape parameter)
# This table provides key values; linear interpolation is used for gamma
# ============================================================================
J3_TABLE = {
    # n=1: J3 ~ 1.0 for all gamma
    1: {0.5: 1.001, 1.0: 0.999, 1.5: 0.999, 2.0: 0.995, 2.5: 0.998},
    2: {0.5: 2.101, 1.0: 1.677, 1.5: 1.450, 2.0: 1.328, 2.5: 1.259},
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

J3_GAMMA_VALUES = [0.5, 1.0, 1.5, 2.0, 2.5]


def get_weight_j1(n: int) -> float:
    """
    Get J1 weight (median of W1) for sample size n.

    J1 is used to compute the scale parameter beta.
    For n > 100, asymptotic value is 1.0.
    """
    if n in WEIGHT_TABLE_J1:
        return WEIGHT_TABLE_J1[n]
    if n < 1:
        return 0.5
    if n > 100:
        return 1.0
    # Exact formula: exp(digamma(n)) / n
    return np.exp(digamma(n)) / n


def get_weight_j2(n: int) -> float:
    """
    Get J2 weight (median of W2) for sample size n.

    J2 is used in the shape equation.
    For n > 100, asymptotic value is 1.0.
    """
    if n in WEIGHT_TABLE_J2:
        return WEIGHT_TABLE_J2[n]
    if n < 1:
        return 0.0
    if n < 2:
        return 0.0
    if n > 100:
        return 1.0

    # Linear interpolation for n not in table
    known_ns = sorted(WEIGHT_TABLE_J2.keys())
    if n < known_ns[0]:
        return 0.0
    if n > known_ns[-1]:
        return 1.0

    for i in range(len(known_ns) - 1):
        n_low, n_high = known_ns[i], known_ns[i + 1]
        if n_low < n < n_high:
            w_low = WEIGHT_TABLE_J2[n_low]
            w_high = WEIGHT_TABLE_J2[n_high]
            t = (n - n_low) / (n_high - n_low)
            return w_low + t * (w_high - w_low)

    return WEIGHT_TABLE_J2[known_ns[-1]]


def get_weight_j3(n: int, gamma: float) -> float:
    """
    Get J3 weight (median of W3) for sample size n and shape parameter gamma.

    J3 is used in the location equation.
    Unlike J1 and J2, J3 depends on both n and gamma.

    For gamma > 1, the asymptotic value is gamma / (gamma - 1).
    """
    gamma = max(0.1, min(5.0, gamma))  # Clamp to [0.1, 5.0]

    # Asymptotic value for gamma > 1
    if gamma > 1:
        asymp_val = gamma / (gamma - 1)
    else:
        asymp_val = float('inf')

    if n <= 16:
        # Use table with interpolation
        if n not in J3_TABLE:
            return asymp_val if gamma > 1 else 2.0

        gammas = J3_GAMMA_VALUES

        if gamma <= gammas[0]:
            return J3_TABLE[n][gammas[0]]
        if gamma >= gammas[-1]:
            return J3_TABLE[n][gammas[-1]]

        # Linear interpolation in gamma
        for i in range(len(gammas) - 1):
            g_low, g_high = gammas[i], gammas[i + 1]
            if g_low <= gamma <= g_high:
                j3_low = J3_TABLE[n][g_low]
                j3_high = J3_TABLE[n][g_high]
                t = (gamma - g_low) / (g_high - g_low)
                return j3_low + t * (j3_high - j3_low)

        return J3_TABLE[n][gammas[-1]]
    else:
        # n > 16: Use asymptotic approximation
        if gamma > 1:
            return asymp_val
        else:
            return 2.0


class WMLE(WeibullBase):
    """
    Weighted Maximum Likelihood Estimation (WMLE)

    Based on: Cousineau, D. (2009). Nearly unbiased estimators for the
    three-parameter Weibull distribution.

    Algorithm (two-step method):
    1. Optimize gamma (shape) and alpha (location) to minimize:
       term1^2 + term2^2
       where:
         term1 = J2/gamma + (1/n)*sum(log(x-alpha))
                 - sum(log(x-alpha)*(x-alpha)^gamma) / sum((x-alpha)^gamma)
         term2 = (1/n)*sum(1/(x-alpha)) * sum((x-alpha)^gamma) / sum((x-alpha)^(gamma-1))
                 - J3(gamma)
    2. Algebraically solve for beta (scale):
         beta = (sum((x-alpha)^gamma) / (n * J1))^(1/gamma)
    """

    def run(self, trace=False):
        """
        Run WMLE estimation.

        Returns: [beta_hat, eta_hat, gamma_hat, r2]
        - beta_hat: shape parameter (paper's gamma)
        - eta_hat: scale parameter (paper's beta)
        - gamma_hat: location parameter (paper's alpha)
        """
        # @step: 1 | Compute static weights | Get J1 and J2 weights
        # @symbols: n|n|sample size, w1|J_1|scale weight, w2|J_2|shape weight
        # @outputs: w1|J_1|scale weight, w2|J_2|shape weight
        n = self.n
        arr = self.data
        x_min = np.min(arr)

        w1 = get_weight_j1(n)
        w2 = get_weight_j2(n)

        if trace:
            self.log_step({"phase": "init", "w1": w1, "w2": w2, "n": n})

        # @step: 2 | Initialize parameters | Set starting values for optimization
        # @formula: \\alpha_{init} = 0.9 \\times \\min(X), \\gamma_{init} = 2.0
        # @outputs: gamma_init|\\gamma_{init}|shape initial, alpha_init|\\alpha_{init}|location initial
        gamma_init = 2.0  # Paper's heuristic
        alpha_init = 0.9 * x_min  # Paper's heuristic

        # @step: 3 | Define objective function | Paper equation (4)
        # @formula: \\min_{\\gamma,\\alpha} \\left( \\text{term}_1^2 + \\text{term}_2^2 \\right)
        # @loop: Up to 500 iterations
        def wmle_objective(params):
            gamma = params[0]  # Shape (paper's gamma)
            alpha = params[1]  # Location (paper's alpha)

            # Constraints: gamma > 0, alpha < min(data)
            if gamma <= 0 or gamma > 10 or alpha >= x_min - 1e-6 or alpha < 0:
                return 1e10

            x_minus_alpha = arr - alpha
            if np.any(x_minus_alpha <= 0):
                return 1e10

            log_x = np.log(x_minus_alpha)
            x_gamma = x_minus_alpha ** gamma

            sum_log = np.sum(log_x)
            sum_log_x_gamma = np.sum(log_x * x_gamma)
            sum_x_gamma = np.sum(x_gamma)

            # Term 1: fctGamma in R code
            term1 = w2 / gamma + sum_log / n - sum_log_x_gamma / sum_x_gamma

            sum_inv = np.sum(1.0 / x_minus_alpha)
            sum_x_gamma_minus1 = np.sum(x_minus_alpha ** (gamma - 1))

            # Term 2: fctAlpha in R code
            w3 = get_weight_j3(n, gamma)
            term2 = (sum_inv / n) * (sum_x_gamma / sum_x_gamma_minus1) - w3

            return term1 ** 2 + term2 ** 2

        def callback(xk):
            if trace:
                gamma_curr, alpha_curr = xk
                w3_curr = get_weight_j3(n, gamma_curr)
                val = wmle_objective(xk)
                self.log_step({
                    "phase": "iter",
                    "gamma": gamma_curr,
                    "alpha": alpha_curr,
                    "w3": w3_curr,
                    "obj_val": val if val < 1e5 else None
                })

        # @step: 4 | Optimize | Use Nelder-Mead method
        # @inputs: gamma_init|\\gamma_{init}|initial shape, alpha_init|\\alpha_{init}|initial location
        # @outputs: gamma_hat|\\hat{\\gamma}|estimated shape, alpha_hat|\\hat{\\alpha}|estimated location
        result = minimize(
            wmle_objective,
            x0=np.array([gamma_init, alpha_init]),
            method='Nelder-Mead',
            callback=callback if trace else None,
            options={'maxiter': 500}
        )

        if not result.success:
            return [1, 100, 0, 0]

        gamma_hat = result.x[0]  # Shape (paper's gamma -> system's beta)
        alpha_hat = result.x[1]  # Location (paper's alpha -> system's gamma)

        # @step: 5 | Compute scale parameter | Algebraic solution from paper
        # @formula: \\hat{\\beta} = \\left( \\frac{\\sum(x_i-\\hat{\\alpha})^{\\hat{\\gamma}}}{n \\times J_1} \\right)^{1/\\hat{\\gamma}}
        # @inputs: gamma_hat|\\hat{\\gamma}|shape, alpha_hat|\\hat{\\alpha}|location, w1|J_1|scale weight
        # @outputs: beta_hat|\\hat{\\beta}|scale parameter
        x_adj = arr - alpha_hat
        beta_hat = (np.sum(x_adj ** gamma_hat) / (n * w1)) ** (1 / gamma_hat)

        if trace:
            self.log_step({
                "phase": "final",
                "paper_gamma": gamma_hat,
                "paper_beta": beta_hat,
                "paper_alpha": alpha_hat
            })

        r2 = self._calculate_r2(gamma_hat, beta_hat, alpha_hat)

        # Return: [shape, scale, location, r2]
        # System notation: beta=shape, eta=scale, gamma=location
        return [gamma_hat, beta_hat, alpha_hat, r2]
