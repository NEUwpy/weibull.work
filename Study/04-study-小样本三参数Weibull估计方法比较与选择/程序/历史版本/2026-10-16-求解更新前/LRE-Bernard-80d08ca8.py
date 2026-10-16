"""
线性回归法 (LRE)
Linear Regression Estimation

算法文档: ../../src/content/algorithms/lre.md
描述: 最基础的工程方法。对威布尔公式进行线性化变换，通过最小二乘法拟合直线。
公式: ln(-ln(1-F)) = beta * ln(t-gamma) - beta * ln(eta)
"""

import math

import numpy as np
from scipy.optimize import minimize_scalar
from base import WeibullBase


class LRE(WeibullBase):
    def run(self):
        """
        LRE 参数估计
        策略：
        1. 先检查原始样本是否存在有意义的信息（退化检测在优化前）。
        2. 优化 γ 使相关系数平方 ρ² 最大。
        3. 固定 γ 后 OLS 回归解 β 和 η。
        """
        # @step: 1 | 数据预处理 | 获取排序后的失效时间数据和样本数量
        # @formula: t_{(1)} \leq t_{(2)} \leq \cdots \leq t_{(n)}
        # @symbols: t|t|排序后的失效时间数组, n|n|样本数量
        # @inputs: data|t_i|原始失效时间样本
        # @outputs: t|t|排序后数组, n|n|样本数量
        n = self.n
        t = self.data

        if n < 3:
            self.last_solution_info = {"status": "insufficient_sample", "n": int(n)}
            return [0, 0, 0, 0, "insufficient_sample"]

        # 进入优化前检查原始样本退化性：全等值或近全等值样本无信息。
        # 使用尺度相关容差，不依赖优化后的对数变换精度。
        t_range = float(np.ptp(t))
        t_scale = max(1.0, float(np.mean(t)), float(np.max(t)))
        if t_range <= t_scale * 1e-12:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        # @step: 2 | 计算中位秩变换 | 使用 Bernard 近似计算经验生存函数并经双对数变换得到回归因变量
        # @formula: F(t_i) = \frac{i - 0.3}{n + 0.4}, \quad y_i = \ln(-\ln(1 - F(t_i)))
        # @symbols: F(t_i)|F(t_i)|第i个样本的经验累积概率, y_i|y_i|变换后的因变量
        # @inputs: n|n|样本数量
        # @outputs: y|y_i|双对数变换的因变量数组
        F = self._median_ranks()
        y = np.log(-np.log(1 - F))

        y_var = float(np.var(y))
        if y_var <= 0:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        # @step: 3 | 优化位置参数 | 以相关系数平方 ρ² 为目标函数在有界区间内搜索最优 γ
        # @formula: \hat{\gamma} = \arg\max_{\gamma \in [0, 0.999 t_{(1)})} \rho^{2}(\gamma),
        #   \rho = \mathrm{corr}(\ln(t-\gamma), y)
        # @symbols: \gamma|\gamma|位置参数候选值, \rho|\rho|Pearson 相关系数
        # @inputs: t|t|失效时间数组, y|y_i|变换因变量
        # @outputs: gamma_hat|\hat{\gamma}|最优位置参数
        # @loop: 尺度无关的粗网格搜索 + 最优邻域有界精化
        def negative_r_squared(gamma_val):
            if gamma_val >= t[0] - 1e-5:
                return 1e10
            try:
                x_vals = np.log(t - gamma_val)
            except Exception:
                return 1e10
            corr = np.corrcoef(x_vals, y)[0, 1]
            if not np.isfinite(corr):
                return 1e10
            return -(corr ** 2)

        t_min = float(t[0])
        min_gap = max(abs(t_min) * 1e-9, 1e-10)
        upper = t_min - min_gap
        linear_grid = np.linspace(0.0, upper, 201)
        geometric_grid = t_min - np.geomspace(min_gap, t_min, 201)
        gamma_grid = np.unique(np.clip(np.concatenate([linear_grid, geometric_grid]), 0.0, upper))
        objective_grid = np.array([negative_r_squared(float(gamma)) for gamma in gamma_grid])

        finite = np.isfinite(objective_grid) & (objective_grid < 1e9)
        if not np.any(finite):
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        best_idx = int(np.argmin(np.where(finite, objective_grid, np.inf)))
        gamma_hat = float(gamma_grid[best_idx])
        best_objective = float(objective_grid[best_idx])
        refined = False
        lo = float(gamma_grid[max(best_idx - 1, 0)])
        hi = float(gamma_grid[min(best_idx + 1, len(gamma_grid) - 1)])
        if hi > lo:
            result = minimize_scalar(
                negative_r_squared,
                bounds=(lo, hi),
                method="bounded",
                options={"xatol": max(t_min * 1e-11, 1e-10)},
            )
            if result.success and np.isfinite(result.fun) and float(result.fun) <= best_objective:
                gamma_hat = float(result.x)
                best_objective = float(result.fun)
                refined = True

        if gamma_hat < max(t_min * 1e-12, 1e-10):
            gamma_hat = 0.0

        if not np.isfinite(gamma_hat) or gamma_hat >= t[0] or gamma_hat < 0:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        # @step: 4 | OLS 线性回归 | 在最优 γ 下对 (ln(t-γ), y) 做最小二乘拟合
        # @formula: \hat{\beta} = \frac{\sum(x_i-\bar{x})(y_i-\bar{y})}{\sum(x_i-\bar{x})^2},
        #   \hat{\eta} = e^{-\hat{\alpha}/\hat{\beta}},\ \hat{\alpha}=\bar{y}-\hat{\beta}\bar{x}
        # @symbols: \hat{\beta}|\hat{\beta}|形状参数（回归斜率）, \hat{\eta}|\hat{\eta}|尺度参数（截距反解）
        # @inputs: gamma_hat|\hat{\gamma}|最优γ, t|t|失效时间数组, y|y_i|变换因变量
        # @outputs: beta_hat|\hat{\beta}|形状参数, eta_hat|\hat{\eta}|尺度参数
        x_vals = np.log(t - gamma_hat)
        x_mean = float(np.mean(x_vals))
        y_mean = float(np.mean(y))

        numerator = float(np.sum((x_vals - x_mean) * (y - y_mean)))
        denominator = float(np.sum((x_vals - x_mean) ** 2))

        # 尺度相关容差：全等值样本的优化后分母在浮点噪声级（~1e-28）
        x_scale = max(1.0, abs(float(x_vals[0])))
        if denominator <= x_scale * 1e-12:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        beta_hat = numerator / denominator

        # @step: 5 | 系数合理性检查 | β ≤ 0 时回归方向与 Weibull 支撑矛盾，不可采纳
        # @symbols: \hat{\beta}|\hat{\beta}|形状参数估计值
        # @inputs: beta_hat|\hat{\beta}|形状参数
        # @outputs: status|status|采纳性判定
        if not (np.isfinite(beta_hat) and beta_hat > 0):
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        intercept = y_mean - beta_hat * x_mean
        eta_hat = math.exp(-intercept / beta_hat)

        if not np.isfinite(eta_hat) or eta_hat <= 0:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        # @step: 6 | 计算拟合优度 R² | 评估模型与数据的拟合程度
        # @formula: R^2 = 1 - \frac{\sum(F_i - \hat{F}_i)^2}{\sum(F_i - \bar{F})^2}
        # @symbols: R^2|R^2|决定系数, F_i|F_i|经验累积概率, \hat{F}_i|\hat{F}_i|模型预测概率
        # @inputs: beta_hat|\hat{\beta}|形状参数, eta_hat|\hat{\eta}|尺度参数, gamma_hat|\hat{\gamma}|位置参数
        # @outputs: r2|R^2|拟合优度
        r2 = self._calculate_r2(beta_hat, eta_hat, gamma_hat)

        self.last_solution_info = {
            "status": "ok",
            "strategy": "rho_squared_maximization",
            "constraint": "0 <= gamma < t[0]",
            "gamma_grid_points": int(len(gamma_grid)),
            "refined": bool(refined),
            "rho_squared": float(-best_objective),
            "location_at_zero_boundary": bool(gamma_hat == 0.0),
        }

        return [float(beta_hat), float(eta_hat), float(gamma_hat), float(r2), True]
