"""
加权极大似然估计 (WMLE)
Weighted Maximum Likelihood Estimation for Three-Parameter Weibull Distribution

算法文档: ../src/content/algorithms/wmle.md
参考文献: Cousineau, D. (2009). British Journal of Mathematical and Statistical Psychology, 62(1), 167-191.

描述: 通过引入三个权重 (W1, W2, W3) 修正 MLE 在小样本下的偏差，偏差减少约 7 倍。
"""

from typing import Dict, Any, List, Tuple
import numpy as np
from scipy.optimize import minimize
from scipy.special import digamma


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
    # 插值或使用近似公式
    if n < 1:
        return 0.5
    if n > 100:
        return 1.0
    # 线性插值
    keys = sorted(k for k in WEIGHT_TABLE_J1.keys() if k <= n)
    if len(keys) == 1:
        return WEIGHT_TABLE_J1[keys[0]]
    # 使用几何平均近似: e^psi(n) / n
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


def wmle_objective(params: np.ndarray, data: np.ndarray, w1: float, w2: float, n: int) -> float:
    """
    WMLE 目标函数：搜索 gamma 和 alpha

    params[0] = gamma (形状参数，论文中的 gamma)
    params[1] = alpha (位置参数，论文中的 alpha)
    """
    gamma = params[0]
    alpha = params[1]

    # 约束检查
    if gamma <= 0 or gamma > 10:
        return 1e10
    if alpha >= np.min(data) - 1e-6:
        return 1e10

    # 计算变换后的数据
    x_minus_alpha = data - alpha

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


def estimate(data: List[float], **kwargs) -> Dict[str, Any]:
    """
    WMLE 参数估计

    Args:
        data: 失效数据数组 [t1, t2, t3, ...]
        **kwargs: 额外参数
            - max_iter: 最大迭代次数（默认：500）
            - tol: 收敛容忍度（默认：1e-6）
            - use_weights: 是否使用修正权重（默认：True）
            - initial_guess: 初始参数猜测 {"gamma": 2.0, "alpha": min(data)*0.9}

    Returns:
        Dict[str, Any]: 估计结果
            - beta: 形状参数 (论文中的 gamma)
            - eta: 尺度参数 (论文中的 beta)
            - gamma: 位置参数 (论文中的 alpha)
            - success: 是否成功收敛
            - message: 状态信息或错误信息
            - iterations: 实际迭代次数

    注意：参数命名转换
        - 论文: (gamma=形状, beta=尺度, alpha=位置)
        - 我们系统: (beta=形状, eta=尺度, gamma=位置)
    """

    try:
        # 1. 数据预处理
        arr = np.array(data, dtype=float)
        n = len(arr)

        if n < 3:
            return {
                "success": False,
                "message": "数据量不足，至少需要3个观测值"
            }

        # 排序数据
        arr_sorted = np.sort(arr)

        # 2. 参数初始化
        use_weights = kwargs.get('use_weights', True)

        # 计算权重
        if use_weights:
            w1 = get_weight_j1(n)
            w2 = get_weight_j2(n)
        else:
            w1 = 1.0
            w2 = 1.0

        # 初始猜测：alpha 略小于最小值，gamma 约为 2
        alpha_init = arr_sorted[0] * 0.95
        gamma_init = kwargs.get('initial_guess', {}).get('gamma', 2.0)

        # 3. 数值搜索 gamma 和 alpha
        result = minimize(
            wmle_objective,
            x0=np.array([gamma_init, alpha_init]),
            args=(arr_sorted, w1, w2, n),
            method='Nelder-Mead',
            options={'maxiter': kwargs.get('max_iter', 500), 'xatol': kwargs.get('tol', 1e-6)},
            bounds=[(0.1, 10), (0, arr_sorted[0] * 0.999)]
        )

        if not result.success:
            return {
                "success": False,
                "message": f"优化失败: {result.message}"
            }

        # 4. 提取结果
        gamma_hat = result.x[0]  # 形状参数（论文符号）
        alpha_hat = result.x[1]  # 位置参数（论文符号）

        # 5. 代数计算 beta（尺度参数，论文符号）
        x_minus_alpha = arr_sorted - alpha_hat
        if use_weights:
            eta_hat = (np.sum(x_minus_alpha ** gamma_hat) / (n * w1)) ** (1 / gamma_hat)
        else:
            eta_hat = (np.sum(x_minus_alpha ** gamma_hat) / n) ** (1 / gamma_hat)

        # 6. 参数命名转换（论文符号 -> 我们系统符号）
        # 论文: (gamma=形状, beta=尺度, alpha=位置)
        # 我们系统: (beta=形状, eta=尺度, gamma=位置)

        return {
            "beta": gamma_hat,      # 形状参数
            "eta": eta_hat,        # 尺度参数
            "gamma": alpha_hat,    # 位置参数
            "success": True,
            "message": "WMLE 估计成功",
            "iterations": result.nit
        }

    except Exception as e:
        return {
            "success": False,
            "message": f"估计失败: {str(e)}"
        }


if __name__ == "__main__":
    # 测试代码 - 使用论文中的数值示例
    print("=" * 60)
    print("WMLE 算法测试")
    print("=" * 60)

    # 论文中的示例数据
    test_data = [310, 342, 353, 365, 383, 393, 403, 412, 451, 456]
    print(f"\n测试数据 (n={len(test_data)}): {test_data}")
    print("真实参数: gamma=2, beta=100, alpha=300")

    result = estimate(test_data)

    print(f"\n估计结果:")
    print(f"  形状参数 (beta):  {result.get('beta', 'N/A'):.3f}")
    print(f"  尺度参数 (eta):   {result.get('eta', 'N/A'):.1f}")
    print(f"  位置参数 (gamma): {result.get('gamma', 'N/A'):.1f}")
    print(f"  状态: {result.get('message', 'N/A')}")

    # 对比标准 MLE (不使用权重)
    print("\n" + "-" * 40)
    result_mle = estimate(test_data, use_weights=False)
    print(f"\n标准 MLE 结果:")
    print(f"  形状参数 (beta):  {result_mle.get('beta', 'N/A'):.3f}")
    print(f"  尺度参数 (eta):   {result_mle.get('eta', 'N/A'):.1f}")
    print(f"  位置参数 (gamma): {result_mle.get('gamma', 'N/A'):.1f}")
