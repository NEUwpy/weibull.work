"""
加权极大似然估计 (WMLE)
Weighted Maximum Likelihood Estimation for Three-Parameter Weibull Distribution

算法文档: ../../src/content/algorithms/wmle.md
参考文献: Cousineau, D. (2009). British Journal of Mathematical and Statistical Psychology, 62(1), 167-191.

描述: 通过引入三个权重 (W1, W2, W3) 修正 MLE 在小样本下的偏差，偏差减少约 7 倍。
"""

import numpy as np
from scipy.optimize import minimize
from scipy.special import digamma
from base import WeibullBase


# 权重表 - 中位数权重 J1, J2 (基于论文表2, 表3)
WEIGHT_TABLE_J1 = {
    1: 0.693, 2: 0.839, 3: 0.891, 4: 0.918, 5: 0.934,
    6: 0.945, 7: 0.953, 8: 0.959, 9: 0.963, 10: 0.967,
    11: 0.970, 12: 0.972, 13: 0.974, 14: 0.976, 15: 0.978,
    16: 0.979, 20: 0.985, 32: 0.991, 50: 0.994, 100: 0.997
}

WEIGHT_TABLE_J2 = {
    1: 0.000, 2: 0.275, 3: 0.517, 4: 0.638, 5: 0.711,
    6: 0.759, 7: 0.791, 8: 0.817, 9: 0.838, 10: 0.853,
    11: 0.867, 12: 0.877, 13: 0.886, 14: 0.895, 15: 0.902,
    16: 0.908, 20: 0.925, 32: 0.947, 50: 0.963, 100: 0.978
}


def get_weight_j1(n: int) -> float:
    """获取 W1 的中位数权重 J1"""
    if n in WEIGHT_TABLE_J1:
        return WEIGHT_TABLE_J1[n]
    # 使用几何平均近似: e^psi(n) / n
    if n < 1:
        return 0.5
    if n > 100:
        return 1.0
    return np.exp(digamma(n)) / n


def get_weight_j2(n: int) -> float:
    """获取 W2 的中位数权重 J2"""
    if n in WEIGHT_TABLE_J2:
        return WEIGHT_TABLE_J2[n]
    # 插值: E[J2] = 1 - 1/n
    if n < 2:
        return 0.0
    if n > 100:
        return 1.0
    return max(0.0, min(1.0, 1.0 - 1.0/n))


def get_weight_j3(n: int, gamma: float) -> float:
    """
    获取 W3 的中位数权重 J3
    J3 依赖于 n 和 gamma，这里使用近似公式
    """
    if gamma <= 1:
        # 当 gamma <= 1 时，MLE权重无定义或为负，使用近似值
        return 1.5 + 0.5 * np.log10(n)
    # 当 gamma > 1 时，渐近趋向于 gamma / (gamma - 1)
    mle_weight = gamma / (gamma - 1)
    # 小样本修正：使用中位数权重略小于 MLE 权重
    correction = max(0.1, 0.3 * np.exp(-n/10))
    return mle_weight * (1 - correction)


class WMLE(WeibullBase):
    def run(self):
        """
        WMLE 参数估计

        Returns:
            [beta, eta, gamma, r_squared]
            - beta: 形状参数 (论文中的 gamma)
            - eta: 尺度参数 (论文中的 beta)
            - gamma: 位置参数 (论文中的 alpha)
            - r_squared: 拟合优度

        注意：参数命名转换
            - 论文: (gamma=形状, beta=尺度, alpha=位置)
            - 我们系统: (beta=形状, eta=尺度, gamma=位置)
        """

        n = self.n
        arr = self.data

        # 计算权重
        w1 = get_weight_j1(n)
        w2 = get_weight_j2(n)

        # 初始猜测：alpha 略小于最小值，gamma 约为 2
        alpha_init = arr[0] * 0.95
        gamma_init = 2.0

        # WMLE 目标函数：搜索 gamma 和 alpha
        def wmle_objective(params):
            """
            params[0] = gamma (形状参数，论文中的 gamma)
            params[1] = alpha (位置参数，论文中的 alpha)
            """
            gamma = params[0]
            alpha = params[1]

            # 约束检查
            if gamma <= 0 or gamma > 10:
                return 1e10
            if alpha >= arr[0] - 1e-6:
                return 1e10

            # 计算变换后的数据
            x_minus_alpha = arr - alpha

            # 避免数值问题
            if np.any(x_minus_alpha <= 0):
                return 1e10

            log_x_minus_alpha = np.log(x_minus_alpha)
            x_minus_alpha_gamma = x_minus_alpha ** gamma

            # 第一项：方程的左侧部分
            sum_log = np.sum(log_x_minus_alpha)
            sum_log_x_gamma = np.sum(log_x_minus_alpha * x_minus_alpha_gamma)
            sum_x_gamma = np.sum(x_minus_alpha_gamma)

            term1_left = w2 / gamma + sum_log / n - sum_log_x_gamma / sum_x_gamma

            # 第二项：方程的右侧部分
            sum_inv = np.sum(1.0 / x_minus_alpha)
            sum_x_gamma_minus1 = np.sum(x_minus_alpha ** (gamma - 1))

            w3 = get_weight_j3(n, gamma)
            term2_left = sum_inv / n * sum_x_gamma / sum_x_gamma_minus1 - w3

            return term1_left ** 2 + term2_left ** 2

        # 数值搜索 gamma 和 alpha
        result = minimize(
            wmle_objective,
            x0=np.array([gamma_init, alpha_init]),
            method='Nelder-Mead',
            options={'maxiter': 500, 'xatol': 1e-6}
        )

        if not result.success:
            # 如果优化失败，回退到简单的 LRE
            y = np.log(-np.log(1 - self._median_ranks()))

            def negative_r_squared(gamma_val):
                if gamma_val >= arr[0]:
                    return 1e15
                x = np.log(arr - gamma_val)
                return -(np.corrcoef(x, y)[0, 1]**2)

            res_gamma = minimize(negative_r_squared, [0], bounds=[(0, arr[0]-1e-5)])
            gamma = res_gamma.x[0]
            x = np.log(arr - gamma)
            beta = (np.sum(x * y) - n * np.mean(x) * np.mean(y)) / (np.sum(x**2) - n * np.mean(x)**2)
            eta = np.exp(-(np.mean(y) - beta * np.mean(x)) / beta)
            return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]

        # 提取结果
        beta_hat = result.x[0]      # 形状参数（论文符号）
        alpha_hat = result.x[1]     # 位置参数（论文符号）

        # 代数计算 eta（尺度参数，论文符号）
        x_minus_alpha = arr - alpha_hat
        eta_hat = (np.sum(x_minus_alpha ** beta_hat) / (n * w1)) ** (1 / beta_hat)

        # 参数命名转换（论文符号 -> 我们系统符号）
        # 论文: (gamma=形状, beta=尺度, alpha=位置)
        # 我们系统: (beta=形状, eta=尺度, gamma=位置)

        gamma_hat = alpha_hat       # 位置参数

        return [beta_hat, eta_hat, gamma_hat, self._calculate_r2(beta_hat, eta_hat, gamma_hat)]


# 测试代码
if __name__ == "__main__":
    # 测试数据
    test_data = [310, 342, 353, 365, 383, 393, 403, 412, 451, 456]
    print("WMLE 算法测试")
    print(f"测试数据 (n={len(test_data)}): {test_data}")
    print("预期参数范围: beta≈2, eta≈100, gamma≈300")

    result = WMLE(test_data).run()
    print(f"\n估计结果:")
    print(f"  形状参数 (beta):  {result[0]:.3f}")
    print(f"  尺度参数 (eta):   {result[1]:.1f}")
    print(f"  位置参数 (gamma): {result[2]:.1f}")
    print(f"  R²:               {result[3]:.4f}")
