"""
加权极大似然估计 (WMLE)
Weighted Maximum Likelihood Estimation

算法文档: ../../src/content/algorithms/wmle.md
参考文献: Cousineau (2009), Paper 182-088
描述: 以 J₁、J₂、J₃ 校准加权方程；数值求根不构成精度改善保证

权重数据来源: https://github.com/dcousin3/wMLE
权重表已嵌入代码中，无需外部文件

符号映射说明:
  ┌─────────────┬──────────────┬──────────────┬─────────────┐
  │   参数      │   论文符号   │   系统符号   │  代码变量   │
  ├─────────────┼──────────────┼──────────────┼─────────────┤
  │   形状参数  │     γ        │      β       │  beta       │
  │   尺度参数  │     β        │      η       │  eta        │
  │   位置参数  │     α        │      γ       │  gamma      │
  └─────────────┴──────────────┴──────────────┴─────────────┘

注意: 本文件注释中的公式使用系统标准符号 (β=形状, η=尺度, γ=位置)
"""

import sys
import numpy as np
from scipy.special import gammaincinv
from base import WeibullBase
from .profile_solvers import solve_wmle_profile
from .conditional_profiles import wmle_residuals

# 形状参数搜索上界（实现保护，超出视为无解，见 run() 中的显式失败分支）
SHAPE_UPPER = 10.0

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
# Complete table: n=1-100, gamma=0.1-5.0 (step 0.1), 4999 entries
# Note: J3 depends on both n and gamma (shape parameter)
# ============================================================================

import os

# Load complete J3 table from external file (loaded once on module import)
_J3_TABLE = None
_J3_GAMMA_VALUES = None

def _load_j3_table():
    """Load J3 weights from TSV file."""
    global _J3_TABLE, _J3_GAMMA_VALUES
    if _J3_TABLE is not None:
        return _J3_TABLE, _J3_GAMMA_VALUES

    j3_table = {}
    gamma_values = set()

    # Get the directory of this file
    current_dir = os.path.dirname(os.path.abspath(__file__))
    j3_file = os.path.join(current_dir, 'j3_weights.tsv')

    with open(j3_file, 'r') as f:
        for line in f:
            parts = line.strip().split()
            if len(parts) >= 3:
                n = int(parts[0])
                gamma = float(parts[1])
                value = float(parts[2])
                if n not in j3_table:
                    j3_table[n] = {}
                j3_table[n][gamma] = value
                gamma_values.add(gamma)

    _J3_TABLE = j3_table
    _J3_GAMMA_VALUES = sorted(gamma_values)
    return _J3_TABLE, _J3_GAMMA_VALUES

# Pre-load on module import
_J3_TABLE, _J3_GAMMA_VALUES = _load_j3_table()


def get_weight_j1(n: int) -> float:
    """
    Get J1 weight (median of W1) for sample size n.

    J1 is used to compute the scale parameter beta.
    Paper definition: W1 = (1/n) * sum(log(1/(1-F(x_i)))), the summands are
    iid Exp(1), so W1 ~ Gamma(n, 1/n) and its exact median is
    gammaincinv(n, 0.5) / n (Cousineau 2009, Table 2 lists the same values).
    For n > 100 (outside the lookup table) we use this exact median.
    """
    if n in WEIGHT_TABLE_J1:
        return WEIGHT_TABLE_J1[n]
    if n < 1:
        return 0.5
    if n > 100:
        # Exact median of W1 ~ Gamma(n, 1/n)
        return float(gammaincinv(n, 0.5)) / n
    # Linear interpolation
    known_ns = sorted(WEIGHT_TABLE_J1.keys())
    for i in range(len(known_ns) - 1):
        n_low, n_high = known_ns[i], known_ns[i + 1]
        if n_low < n < n_high:
            w_low = WEIGHT_TABLE_J1[n_low]
            w_high = WEIGHT_TABLE_J1[n_high]
            t = (n - n_low) / (n_high - n_low)
            return w_low + t * (w_high - w_low)
    return WEIGHT_TABLE_J1[known_ns[-1]]


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

    Implementation follows R code approach:
    - Linear interpolation in gamma direction (0.1 resolution)
    - For n not in table, interpolate between nearest n values
    """
    global _J3_TABLE, _J3_GAMMA_VALUES

    # Clamp gamma to [0.1, 5.0] (same as R code)
    gamma_clamped = max(0.1, min(5.0, gamma))

    # Calculate asymptotic value for very large n
    if gamma_clamped > 1:
        asymp_val = gamma_clamped / (gamma_clamped - 1)
    else:
        asymp_val = float('inf')

    # Helper function for gamma interpolation
    def interpolate_gamma(n_val):
        """Linear interpolation in gamma direction"""
        if n_val not in _J3_TABLE:
            return asymp_val if gamma_clamped > 1 else 2.0

        gammas = sorted(_J3_TABLE[n_val].keys())

        if gamma_clamped <= gammas[0]:
            return _J3_TABLE[n_val][gammas[0]]
        if gamma_clamped >= gammas[-1]:
            return _J3_TABLE[n_val][gammas[-1]]

        # Linear interpolation
        for i in range(len(gammas) - 1):
            g_low, g_high = gammas[i], gammas[i + 1]
            if g_low <= gamma_clamped <= g_high:
                j3_low = _J3_TABLE[n_val][g_low]
                j3_high = _J3_TABLE[n_val][g_high]
                t = (gamma_clamped - g_low) / (g_high - g_low)
                return j3_low + t * (j3_high - j3_low)

        return _J3_TABLE[n_val][gammas[-1]]

    # Get available n values
    available_ns = sorted(_J3_TABLE.keys())

    # n is in table
    if n in _J3_TABLE:
        return interpolate_gamma(n)

    # n < minimum in table
    if n < available_ns[0]:
        return interpolate_gamma(available_ns[0])

    # n > maximum in table (100)
    if n > available_ns[-1]:
        # Use asymptotic value for very large n
        if gamma_clamped > 1:
            return asymp_val
        else:
            return 2.0

    # Interpolate between two nearest n values (bilinear interpolation)
    n_low, n_high = None, None
    for i in range(len(available_ns) - 1):
        if available_ns[i] < n < available_ns[i + 1]:
            n_low, n_high = available_ns[i], available_ns[i + 1]
            break

    if n_low is None:
        # Fallback to closest value
        return interpolate_gamma(available_ns[-1])

    # Get J3 values at both n values
    j3_low = interpolate_gamma(n_low)
    j3_high = interpolate_gamma(n_high)

    # Linear interpolation in n direction
    t = (n - n_low) / (n_high - n_low)
    return j3_low + t * (j3_high - j3_low)


class WMLE(WeibullBase):
    """Original weighted equations and weights, with profile root search."""

    def run(self, trace=False, generate_surface=False):
        # @step: 1 | 校准权重 | 使用原有J1、J2、J3查表与插值规则
        # @step: 2 | 联立方程求根 | 条件形状求根后扫描位置方程的交点
        # @formula: T1(beta,gamma)=0, T2(beta,gamma)=0
        # @step: 3 | 多根选择 | 沿用原启发式初值的距离规则，与真值无关
        try:
            selected, info = solve_wmle_profile(self.data, sys.modules[__name__])
        except (ValueError, FloatingPointError, RuntimeError) as error:
            self.last_solution_info = dict(status='profile_solver_failed', error=str(error))
            return [None, None, None, 0., 'profile_solver_failed']
        self.last_solution_info = info
        if trace:
            for candidate in info.get('candidates', []):
                self.log_step(dict(phase='candidate', beta=candidate['beta'],
                                   eta=candidate['eta'], gamma=candidate['gamma'],
                                   objective=candidate['objective']))
        if selected is None:
            if trace:
                self.log_step(dict(phase='failed', reason=info['status']))
            return [None, None, None, 0., info['status']]
        beta, eta, gamma = (selected[p] for p in ['beta', 'eta', 'gamma'])
        # @step: 4 | 尺度恢复 | 在对数域实现原J1加权幂均值公式
        # @formula: eta=(sum((x-gamma)**beta)/(n*J1))**(1/beta)
        if trace:
            self.log_step(dict(phase='final', beta=beta, eta=eta, gamma=gamma))
        if generate_surface:
            betas = np.linspace(.5, 5., 50)
            gammas = np.linspace(0., self.data[0] * .95, 50)
            values = []
            for b in betas:
                a, c = wmle_residuals(self.data, b, gammas, sys.modules[__name__])
                values.append([float(v) if np.isfinite(v) and v < 1e5 else None for v in a*a+c*c])
            self.trace_data.append(dict(phase='surface', betas=betas.tolist(), gammas=gammas.tolist(),
                                        values=values, optimal_beta=beta, optimal_gamma=gamma))
        # @step: 5 | 拟合优度 | 保持统一概率图R平方的输出接口
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma), True]
