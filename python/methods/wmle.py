"""
加权极大似然估计 (WMLE)
Weighted Maximum Likelihood Estimation

算法文档: ../../src/content/algorithms/wmle.md
参考文献: Cousineau (2009), Paper 182-088
描述: 通过引入三个权重 (J₁, J₂, J₃) 修正 MLE 在小样本下的偏差，偏差减少约 7 倍

权重数据来源: https://github.com/dcousin3/wMLE
权重表已嵌入代码中，无需外部文件

符号映射说明:
  ┌─────────────┬──────────────┬──────────────┬─────────────┐
  │   参数      │   论文符号   │   系统符号   │  代码变量   │
  ├─────────────┼──────────────┼──────────────┼─────────────┤
  │   形状参数  │     γ        │      β       │  gamma_hat  │
  │   尺度参数  │     β        │      η       │  beta_hat   │
  │   位置参数  │     α        │      γ       │  alpha_hat  │
  └─────────────┴──────────────┴──────────────┴─────────────┘

注意: 本文件注释中的公式使用系统标准符号 (β=形状, η=尺度, γ=位置)
"""

import numpy as np
from scipy.optimize import minimize
from scipy.special import gammaincinv
from base import WeibullBase

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

    def run(self, trace=False, generate_surface=False):
        """
        执行 WMLE 参数估计

        参数:
            trace: 是否记录追踪数据
            generate_surface: 是否生成 3D 曲面网格数据（用于可视化，计算量较大）

        返回: [beta_hat, eta_hat, gamma_hat, r2]
        - beta_hat: 形状参数（论文中的 gamma）
        - eta_hat: 尺度参数（论文中的 beta）
        - gamma_hat: 位置参数（论文中的 alpha）
        """
        # @step: 1 | 数据预处理 | 获取排序后的失效时间数据和样本数量
        # @formula: x_{(1)} \leq x_{(2)} \leq \cdots \leq x_{(n)}
        # @symbols: x_{(i)}|x_{(i)}|第i小的失效时间, n|n|样本数量, x_{min}|x_{min}|最小失效时间
        # @inputs: data|x_i|原始失效时间样本
        # @outputs: arr|x|排序后数组, n|n|样本数量, x_min|x_{min}|最小值
        n = self.n
        arr = self.data
        x_min = np.min(arr)

        # @step: 2 | 计算静态权重 J₁, J₂ | 根据样本量 n 从权重表中查取两个静态修正权重
        # @formula: J_1 = \mathrm{median}(W_1), \quad J_2 = \mathrm{median}(W_2)
        # @symbols: J_1|J_1|尺度参数权重, J_2|J_2|形状参数权重
        # @inputs: n|n|样本数量
        # @outputs: J1|J_1|尺度权重, J2|J_2|形状权重
        w1 = get_weight_j1(n)
        w2 = get_weight_j2(n)

        if trace:
            self.log_step({"phase": "init", "w1": w1, "w2": w2, "n": n})

        # @step: 3 | 初始化优化起点 | 为 Nelder-Mead 优化算法设置初始猜测值
        # @formula: \beta^{(0)} = 2.0, \quad \gamma^{(0)} = 0.9 \times x_{\min}
        # @symbols: \beta^{(0)}|\beta^{(0)}|形状参数初始值, \gamma^{(0)}|\gamma^{(0)}|位置参数初始值
        # @inputs: x_min|x_{min}|最小失效时间
        # @outputs: gamma_init|\beta^{(0)}|形状参数初始值, alpha_init|\gamma^{(0)}|位置参数初始值
        gamma_init = 2.0  # Paper's heuristic
        alpha_init = 0.9 * x_min  # Paper's heuristic

        # @step: 4 | 定义 WMLE 目标函数 | 构造包含两个平方项的目标函数（论文公式4）
        # @formula: O(\beta, \gamma) = T_1^2 + T_2^2
        # @symbols: T_1|T_1|第一项：修正的形状参数似然方程, T_2|T_2|第二项：修正的位置参数似然方程, J_3|J_3|动态位置权重
        # @inputs: J2|J_2|形状权重, arr|x|失效时间数组
        # @outputs: O|O|目标函数值
        def wmle_objective(params):
            gamma = params[0]  # Shape (paper's gamma)
            alpha = params[1]  # Location (paper's alpha)

            # Constraints: gamma > 0, alpha < min(data)
            if gamma <= 0 or gamma > SHAPE_UPPER or alpha >= x_min - 1e-6 or alpha < 0:
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
                # 论文符号 -> 系统符号映射
                # paper_gamma (形状) -> system_beta
                # paper_alpha (位置) -> system_gamma
                paper_gamma_curr, paper_alpha_curr = xk
                system_beta_curr = paper_gamma_curr   # 形状参数
                system_gamma_curr = paper_alpha_curr  # 位置参数
                w3_curr = get_weight_j3(n, paper_gamma_curr)
                val = wmle_objective(xk)
                self.log_step({
                    "phase": "iter",
                    "beta": system_beta_curr,      # 系统符号：形状参数
                    "gamma": system_gamma_curr,    # 系统符号：位置参数
                    "w3": w3_curr,
                    "obj_val": val if val < 1e5 else None
                })

        # @step: 5 | Nelder-Mead 优化 | 使用无导数单纯形优化算法搜索使目标函数最小的 β 和 γ
        # @formula: \{\hat{\beta}, \hat{\gamma}\} = \arg\min_{\beta, \gamma} O(\beta, \gamma)
        # @symbols: \hat{\beta}|\hat{\beta}|最优形状参数, \hat{\gamma}|\hat{\gamma}|最优位置参数
        # @inputs: gamma_init|\beta^{(0)}|形状初始值, alpha_init|\gamma^{(0)}|位置初始值
        # @outputs: gamma_hat|\hat{\beta}|最优形状参数, alpha_hat|\hat{\gamma}|最优位置参数
        # @loop: 约 50-200 次迭代
        # 单一起点在大位置参数尺度下可能停在非零残差的局部极小点。
        # 保留论文启发式起点，并增加少量确定性起点；仍优化同一组加权方程。
        starts = [
            np.array([gamma_init, alpha_init]),
            np.array([2.0, 0.5 * x_min]),
            np.array([2.0, 0.1 * x_min]),
            np.array([1.2, 0.9 * x_min]),
            np.array([4.0, 0.9 * x_min]),
        ]
        candidates = []
        for start_index, start in enumerate(starts):
            result = minimize(
                wmle_objective,
                x0=start,
                method='Nelder-Mead',
                callback=callback if trace else None,
                options={'maxiter': 1200, 'xatol': 1e-9, 'fatol': 1e-12},
            )
            shape_candidate, location_candidate = result.x
            if (
                result.success
                and np.isfinite(result.fun)
                and float(result.fun) < 1e9
                and 0 < shape_candidate < SHAPE_UPPER
                and 0 <= location_candidate < x_min
            ):
                candidates.append((result, start_index))

        if not candidates:
            # 优化失败必须显式报错，禁止返回伪造的默认参数
            self.last_solution_info = {
                "status": "optimizer_failed",
                "message": "all deterministic starts failed",
                "start_count": int(len(starts)),
            }
            if trace:
                self.log_step({
                    "phase": "failed",
                    "reason": "optimizer_failed",
                    "message": "all deterministic starts failed",
                })
            return [0, 0, 0, 0, False]

        min_objective = min(float(item[0].fun) for item in candidates)
        near_best = [
            item for item in candidates
            if float(item[0].fun) <= min_objective + 1e-12
        ]
        result, selected_start = min(
            near_best,
            key=lambda item: (
                np.log(float(item[0].x[0]) / gamma_init) ** 2
                + ((float(item[0].x[1]) - alpha_init) / max(float(x_min), 1.0)) ** 2
            ),
        )

        gamma_hat = result.x[0]  # Shape (paper's gamma -> System's beta)
        alpha_hat = result.x[1]  # Location (Paper's alpha -> System's gamma)

        # 形状估计压在实现上界：加权方程组在支持范围内无根，视为无解
        if gamma_hat >= SHAPE_UPPER - 0.01:
            self.last_solution_info = {
                "status": "shape_at_bound",
                "shape_upper": SHAPE_UPPER,
                "objective": float(result.fun),
            }
            if trace:
                self.log_step({
                    "phase": "failed",
                    "reason": "shape_at_bound",
                    "shape": float(gamma_hat),
                    "objective": float(result.fun),
                })
            return [0, 0, 0, 0, "shape_at_bound"]

        # WMLE 定义为求解两条加权方程；优化器“成功”但残差未接近零时，
        # 不能把局部最小点伪装成方程根。
        if float(result.fun) > 1e-8:
            self.last_solution_info = {
                "status": "equation_residual",
                "objective": float(result.fun),
                "strategy": "deterministic_multistart_equation_minimization",
                "start_count": int(len(starts)),
                "selected_start": int(selected_start),
            }
            return [0, 0, 0, 0, "equation_residual"]

        # 求解诊断：目标函数残差（论文式(4) 应在根处为 0）与位置边界标记
        self.last_solution_info = {
            "status": "ok",
            "objective": float(result.fun),
            "strategy": "deterministic_multistart_equation_minimization",
            "start_count": int(len(starts)),
            "selected_start": int(selected_start),
            "location_at_zero_boundary": bool(alpha_hat < 1e-6),
        }

        # @step: 6 | 代数计算尺度参数 η | 使用最优的 β̂ 和 γ̂，通过加权代数公式直接计算尺度参数
        # @formula: \hat{\eta} = \left[ \frac{1}{n \cdot J_1} \sum_{i=1}^{n} (x_i - \hat{\gamma})^{\hat{\beta}} \right]^{1/\hat{\beta}}
        # @symbols: \hat{\eta}|\hat{\eta}|尺度参数估计值, x_i - \hat{\gamma}|x_i-\hat{\gamma}|平移后的数据, J_1|J_1|尺度修正权重
        # @inputs: gamma_hat|\hat{\beta}|最优形状参数, alpha_hat|\hat{\gamma}|最优位置参数, w1|J_1|尺度权重
        # @outputs: beta_hat|\hat{\eta}|尺度参数估计值
        x_adj = arr - alpha_hat
        beta_hat = (np.sum(x_adj ** gamma_hat) / (n * w1)) ** (1 / gamma_hat)

        # 符号映射：论文 -> 系统
        # paper_gamma (形状) -> system_beta
        # paper_alpha (位置) -> system_gamma
        # paper_beta (尺度) -> system_eta
        system_beta = gamma_hat   # 形状参数
        system_gamma = alpha_hat  # 位置参数
        system_eta = beta_hat     # 尺度参数

        if trace:
            self.log_step({
                "phase": "final",
                "beta": system_beta,
                "eta": system_eta,
                "gamma": system_gamma
            })

        # 只有在请求时才生成 3D 曲面网格数据（计算量较大）
        if generate_surface:
            beta_range = np.linspace(0.5, 5.0, 50)
            gamma_range = np.linspace(0, x_min * 0.95, 50)

            surface_data = []
            for b in beta_range:
                row = []
                for g in gamma_range:
                    val = wmle_objective([b, g])
                    row.append(val if val < 1e5 else None)
                surface_data.append(row)

            self.trace_data.append({
                "phase": "surface",
                "betas": beta_range.tolist(),   # 形状参数 β (x轴)
                "gammas": gamma_range.tolist(), # 位置参数 γ (y轴)
                "values": surface_data,         # 目标函数值 O(β,γ) (z轴)
                "optimal_beta": system_beta,
                "optimal_gamma": system_gamma
            })

        # @step: 7 | 计算拟合优度 R² | 评估模型与数据的拟合程度
        # @formula: R^2 = 1 - \frac{\sum(F_i - \hat{F}_i)^2}{\sum(F_i - \bar{F})^2}
        # @symbols: R^2|R^2|决定系数, F_i|F_i|经验累积概率, \hat{F}_i|\hat{F}_i|模型预测概率
        # @inputs: gamma_hat|\hat{\beta}|形状参数, beta_hat|\hat{\eta}|尺度参数, alpha_hat|\hat{\gamma}|位置参数
        # @outputs: r2|R^2|拟合优度
        r2 = self._calculate_r2(gamma_hat, beta_hat, alpha_hat)

        # 返回: [形状参数, 尺度参数, 位置参数, R²]
        return [gamma_hat, beta_hat, alpha_hat, r2]
