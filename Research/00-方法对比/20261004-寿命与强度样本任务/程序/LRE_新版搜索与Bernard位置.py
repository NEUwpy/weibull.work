"""诊断控制：新版搜索和R2，绘图位置改为Bernard；不作为生产方法。"""
"""
线性回归法 (LRE)
Linear Regression Estimation

算法文档: ../../src/content/algorithms/lre.md
依据: Park (2017), §2、§5 Proposed+Plot，doi:10.23055/ijietap.2017.24.4.2848。
描述: 原文分段绘图位置 + 非负位置相关系数最大化 + 概率图 OLS。
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
        2. 使用 Park 分段绘图位置，优化 γ 使相关系数 ρ 最大。
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
        t_scale = float(np.max(t))
        if t_range <= t_scale * 1e-12:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        # @step: 2 | Park 绘图位置变换 | n≤10 用 Blom，n≥11 用 (i−1/2)/n
        # @formula: p_i=\begin{cases}(i-3/8)/(n+1/4),&n\leq10\\(i-1/2)/n,&n\geq11\end{cases},\quad y_i=\ln(-\ln(1-p_i))
        # @symbols: F(t_i)|F(t_i)|第i个样本的经验累积概率, y_i|y_i|变换后的因变量
        # @inputs: n|n|样本数量
        # @outputs: y|y_i|双对数变换的因变量数组
        # 此估计器的绘图位置由论文固定，不消费基础类的 Bernard/exact 开关。
        ranks = np.arange(1, n + 1, dtype=float)
        F = (ranks - 0.3) / (n + 0.4)
        y = np.log(-np.log1p(-F))
        y_centered = y - np.mean(y)
        y_ss = float(np.dot(y_centered, y_centered))

        y_var = float(np.var(y))
        if y_var <= 0:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        # @step: 3 | 优化位置参数 | 按 Park 式(2)在 [0,t_(1)) 内最大化相关系数
        # @formula: \hat{\gamma} = \arg\max_{\gamma \in [0,t_{(1)})} \rho(\gamma),
        #   \rho = \mathrm{corr}(\ln(t-\gamma), y)
        # @symbols: \gamma|\gamma|位置参数候选值, \rho|\rho|Pearson 相关系数
        # @inputs: t|t|失效时间数组, y|y_i|变换因变量
        # @outputs: gamma_hat|\hat{\gamma}|最优位置参数
        # @loop: 无量纲位置网格 + 各峰邻域有界精化，包含 γ=0
        t_min = float(t[0])
        upper = float(np.nextafter(t_min, 0.0))
        # s=log((t_min-γ)/t_min)。用对数间隔覆盖开区间的近端点；
        # x 减去常数 log(t_min) 不改变相关系数或 OLS 斜率。
        s_min = math.log((t_min - upper) / t_min)
        relative_excess = (t - t_min) / t_min

        def negative_correlation(s):
            x = np.log(relative_excess + np.exp(s))
            centered = x - np.mean(x)
            x_ss = float(np.dot(centered, centered))
            if x_ss <= 0 or not np.isfinite(x_ss):
                return np.inf
            return -float(np.dot(centered, y_centered) / np.sqrt(x_ss * y_ss))

        search_grid = np.unique(np.concatenate([
            np.linspace(s_min, 0.0, 201),
            np.log1p(-np.linspace(0.0, 0.99, 201)),
        ]))
        objective_grid = np.array([negative_correlation(s) for s in search_grid])

        finite = np.isfinite(objective_grid)
        if not np.any(finite):
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        best_idx = int(np.argmin(np.where(finite, objective_grid, np.inf)))
        best_s = float(search_grid[best_idx])
        best_objective = float(objective_grid[best_idx])
        refined = False
        # 精化所有被网格夹住的峰，保留端点候选，不假定单峰。
        peaks = [i for i in range(1, len(search_grid) - 1)
                 if objective_grid[i] <= objective_grid[i - 1]
                 and objective_grid[i] <= objective_grid[i + 1]]
        for i in peaks:
            result = minimize_scalar(
                negative_correlation,
                bounds=(float(search_grid[i - 1]), float(search_grid[i + 1])),
                method="bounded",
                options={"xatol": 1e-12},
            )
            if result.success and np.isfinite(result.fun) and float(result.fun) <= best_objective:
                best_s = float(result.x)
                best_objective = float(result.fun)
                refined = True

        gamma_hat = min(upper, float(-t_min * np.expm1(best_s)))

        if not np.isfinite(gamma_hat) or gamma_hat >= t[0] or gamma_hat < 0:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        # @step: 4 | OLS 线性回归 | 在最优 γ 下对 (ln(t-γ), y) 做最小二乘拟合
        # @formula: \hat{\beta} = \frac{\sum(x_i-\bar{x})(y_i-\bar{y})}{\sum(x_i-\bar{x})^2},
        #   \hat{\eta} = e^{-\hat{\alpha}/\hat{\beta}},\ \hat{\alpha}=\bar{y}-\hat{\beta}\bar{x}
        # @symbols: \hat{\beta}|\hat{\beta}|形状参数（回归斜率）, \hat{\eta}|\hat{\eta}|尺度参数（截距反解）
        # @inputs: gamma_hat|\hat{\gamma}|最优γ, t|t|失效时间数组, y|y_i|变换因变量
        # @outputs: beta_hat|\hat{\beta}|形状参数, eta_hat|\hat{\eta}|尺度参数
        x_vals = np.log((t - gamma_hat) / t_min)
        x_mean = float(np.mean(x_vals))
        y_mean = float(np.mean(y))

        numerator = float(np.sum((x_vals - x_mean) * (y - y_mean)))
        denominator = float(np.sum((x_vals - x_mean) ** 2))

        if not np.isfinite(denominator) or denominator <= 0:
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
        eta_hat = t_min * math.exp(-intercept / beta_hat)

        if not np.isfinite(eta_hat) or eta_hat <= 0:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        # @step: 6 | 计算概率图 R² | 与位置搜索采用同一组 Park 绘图位置
        # @formula: R^2 = 1-\frac{\sum(y_i-\hat{y}_i)^2}{\sum(y_i-\bar{y})^2}=\rho^2
        # @symbols: R^2|R^2|概率图决定系数, y_i|y_i|变换后的绘图分数
        # @inputs: beta_hat|\hat{\beta}|形状参数, eta_hat|\hat{\eta}|尺度参数, gamma_hat|\hat{\gamma}|位置参数
        # @outputs: r2|R^2|拟合优度
        residual = y - (beta_hat * x_vals + intercept)
        r2 = 1.0 - float(np.dot(residual, residual)) / y_ss

        self.last_solution_info = {
            "status": "ok",
            "implementation": "diagnostic_new_search_bernard_positions",
            "plotting_positions": "bernard_diagnostic",
            "strategy": "correlation_maximization",
            "constraint": "0 <= gamma < t[0]",
            "gamma_grid_points": int(len(search_grid)),
            "refined": bool(refined),
            "rho_squared": float(r2),
            "location_at_zero_boundary": bool(gamma_hat == 0.0),
        }

        return [float(beta_hat), float(eta_hat), float(gamma_hat), float(r2), True]
