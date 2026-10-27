"""
矩估计 (MM)
Method of Moments (Weibull Moments, Cran 1988)

算法文档: ../../src/content/algorithms/mm.md
参考文献: Cran (1988), Paper 182-102
描述: 用 Weibull 矩（生存函数幂次的积分矩）的低阶样本矩显式解出三参数

符号映射说明:
  ┌─────────────┬──────────────┬──────────────┬─────────────┐
  │   参数      │   论文符号   │   系统符号   │  代码变量   │
  ├─────────────┼──────────────┼──────────────┼─────────────┤
  │   形状参数  │     c        │      β       │  shape      │
  │   尺度参数  │     b        │      η       │  scale      │
  │   位置参数  │     a        │      γ       │  location   │
  └─────────────┴──────────────┴──────────────┴─────────────┘
"""

import math

import numpy as np
from scipy.special import gamma as gamma_fn

from base import WeibullBase


def sample_weibull_moment(sorted_x, k):
    """论文式(3)：样本 Weibull 矩 m̄_k = Σ (1 - r/n)^k (x_(r+1) - x_(r))，x_(0)=0。"""
    n = len(sorted_x)
    x_prev = np.concatenate(([0.0], sorted_x[:-1]))
    weights = (1.0 - np.arange(n) / n) ** k
    return float(np.sum(weights * (sorted_x - x_prev)))


def solve_from_weibull_moments(m1, m2, m4):
    """论文式(2a)-(2c)：由 Weibull 矩显式解 (c, a, b)。

    返回 None 表示矩组合不可采纳（论文：m̄2 >= (m̄1+m̄4)/2 时 c*, b* 非正）。
    """
    d12 = m1 - m2
    d24 = m2 - m4
    if d24 <= 0 or d12 <= d24:
        return None
    shape = math.log(2.0) / (math.log(d12) - math.log(d24))
    location = (m1 * m4 - m2 * m2) / (m1 + m4 - 2.0 * m2)
    scale = (m1 - location) / gamma_fn(1.0 + 1.0 / shape)
    return shape, location, scale


class MM(WeibullBase):
    """Weibull 矩估计（Cran 1988）。"""

    def run(self, trace=False):
        """
        执行 Weibull 矩估计。

        Returns:
            [shape, scale, location, r_squared, status]
        """
        # @step: 1 | 数据预处理 | 获取排序后的失效时间数据和样本数量
        # @formula: x_{(1)} \leq x_{(2)} \leq \cdots \leq x_{(n)}
        # @symbols: x|x|排序后的失效时间数组, n|n|样本数量
        # @inputs: data|x_i|原始失效时间样本
        # @outputs: x|x|排序后数组, n|n|样本数量
        x = self.data
        n = self.n

        if n < 3:
            self.last_solution_info = {"status": "insufficient_sample", "n": int(n)}
            return [0, 0, 0, 0, "insufficient_sample"]

        # @step: 2 | 计算样本 Weibull 矩 | 用生存函数阶梯估计计算 k=1,2,4 阶样本矩（论文式(3)）
        # @formula: \bar{m}_k = \sum_{r=0}^{n-1}\left(1-\frac{r}{n}\right)^k (x_{(r+1)} - x_{(r)}), \quad x_{(0)}=0
        # @symbols: \bar{m}_k|\bar{m}_k|k 阶样本 Weibull 矩
        # @inputs: x|x|排序后数组, n|n|样本数量
        # @outputs: m1|\bar{m}_1|一阶矩（等于样本均值）, m2|\bar{m}_2|二阶矩, m4|\bar{m}_4|四阶矩
        m1 = sample_weibull_moment(x, 1)
        m2 = sample_weibull_moment(x, 2)
        m4 = sample_weibull_moment(x, 4)

        if trace:
            self.log_step({"phase": "moments", "m1": m1, "m2": m2, "m4": m4})

        # @step: 3 | 采纳性检查 | 论文：当 m̄2 >= (m̄1+m̄4)/2 时 c*, b* 非正，矩估计不可用
        # @formula: \bar{m}_1 - \bar{m}_2 > \bar{m}_2 - \bar{m}_4 > 0
        # @symbols: \bar{m}_k|\bar{m}_k|样本 Weibull 矩
        # @inputs: m1|\bar{m}_1|一阶矩, m2|\bar{m}_2|二阶矩, m4|\bar{m}_4|四阶矩
        # @outputs: solved|(c^*, a^*, b^*)|矩方程显式解或不可采纳
        solved = solve_from_weibull_moments(m1, m2, m4)
        if solved is None:
            self.last_solution_info = {
                "status": "inadmissible_moments",
                "m1": m1,
                "m2": m2,
                "m4": m4,
            }
            if trace:
                self.log_step({"phase": "failed", "reason": "inadmissible_moments"})
            return [0, 0, 0, 0, "inadmissible_moments"]

        # @step: 4 | 显式解参数 | 论文式(2a)-(2c)：由低阶矩显式解形状、位置、尺度
        # @formula: c^* = \frac{\ln 2}{\ln(\bar{m}_1-\bar{m}_2) - \ln(\bar{m}_2-\bar{m}_4)}, \quad a^* = \frac{\bar{m}_1\bar{m}_4 - \bar{m}_2^2}{\bar{m}_1 + \bar{m}_4 - 2\bar{m}_2}, \quad b^* = \frac{\bar{m}_1 - a^*}{\Gamma(1+1/c^*)}
        # @symbols: c^*|c^*|形状参数估计, a^*|a^*|位置参数估计, b^*|b^*|尺度参数估计
        # @inputs: m1|\bar{m}_1|一阶矩, m2|\bar{m}_2|二阶矩, m4|\bar{m}_4|四阶矩
        # @outputs: shape|c^*|形状参数, location|a^*|位置参数, scale|b^*|尺度参数
        shape, location, scale = solved
        location_adjustment = None

        # @step: 5 | 位置参数可采纳性修正 | a*<0 置零；a*>=x_(1) 用论文替代式 a**
        # @formula: a^{**} = x_{(1)} - b^* \Gamma(1+1/c^*) / n^{1/c^*}
        # @symbols: a^{**}|a^{**}|替代位置估计, x_{(1)}|x_{(1)}|最小失效时间
        # @inputs: location|a^*|位置参数, shape|c^*|形状参数, scale|b^*|尺度参数
        # @outputs: location|\hat{a}|修正后的位置参数, scale|\hat{b}|修正后的尺度参数
        x_min = float(x[0])
        if location < 0.0:
            location = 0.0
            scale = m1 / gamma_fn(1.0 + 1.0 / shape)
            location_adjustment = "clamped_to_zero"
        elif location >= x_min:
            alt = x_min - scale * gamma_fn(1.0 + 1.0 / shape) / (n ** (1.0 / shape))
            location = max(0.0, float(alt))
            scale = (m1 - location) / gamma_fn(1.0 + 1.0 / shape)
            location_adjustment = "alternative_a_star_star"
            if location >= x_min or scale <= 0:
                self.last_solution_info = {
                    "status": "inadmissible_location",
                    "a_star_star": float(alt),
                }
                if trace:
                    self.log_step({"phase": "failed", "reason": "inadmissible_location"})
                return [0, 0, 0, 0, "inadmissible_location"]

        # @step: 6 | 2P 对照估计 | 论文 LOCATION 节：同时计算 a=0 的两参数矩估计用于阈值判断
        # @formula: c^{**} = \frac{\ln 2}{\ln \bar{m}_1 - \ln \bar{m}_2}, \quad b^{**} = \bar{m}_1 / \Gamma(1+1/c^{**})
        # @symbols: c^{**}|c^{**}|2P 形状估计, b^{**}|b^{**}|2P 尺度估计
        # @inputs: m1|\bar{m}_1|一阶矩, m2|\bar{m}_2|二阶矩
        # @outputs: two_param_shape|c^{**}|2P 形状, two_param_scale|b^{**}|2P 尺度
        two_param_shape = None
        two_param_scale = None
        if m1 > 0 and m2 > 0 and m1 > m2:
            two_param_shape = math.log(2.0) / (math.log(m1) - math.log(m2))
            two_param_scale = m1 / gamma_fn(1.0 + 1.0 / two_param_shape)

        # @step: 7 | 计算拟合优度 R² | 评估模型与数据的拟合程度
        # @formula: R^2 = 1 - \frac{\sum(F_i - \hat{F}_i)^2}{\sum(F_i - \bar{F})^2}
        # @symbols: R^2|R^2|决定系数
        # @inputs: shape|\hat{c}|形状参数, scale|\hat{b}|尺度参数, location|\hat{a}|位置参数
        # @outputs: r2|R^2|拟合优度
        r2 = self._calculate_r2(shape, scale, location)

        self.last_solution_info = {
            "status": "ok",
            "m1": m1,
            "m2": m2,
            "m4": m4,
            "location_adjustment": location_adjustment,
            "two_param_shape": two_param_shape,
            "two_param_scale": two_param_scale,
        }

        if trace:
            self.log_step({
                "phase": "final",
                "beta": float(shape),
                "eta": float(scale),
                "gamma": float(location),
                "location_adjustment": location_adjustment,
            })

        return [float(shape), float(scale), float(location), float(r2), True]
