"""
最小二乘估计 (LSE)
Least Squares Estimation

算法文档: ../../src/content/algorithms/lse.md
参考文献: Soman & Misra (1992), Paper 182-104; White (1969)
描述: 对 log(t-μ) 与对数威布尔顺序统计量期望做最小二乘回归，用 Fisher F 比最大化定位位置参数

符号映射说明:
  ┌─────────────┬──────────────┬──────────────┬─────────────┐
  │   参数      │   论文符号   │   系统符号   │  代码变量   │
  ├─────────────┼──────────────┼──────────────┼─────────────┤
  │   形状参数  │     c        │      β       │  shape      │
  │   尺度参数  │     b        │      η       │  scale      │
  │   位置参数  │     μ        │      γ       │  mu         │
  └─────────────┴──────────────┴──────────────┴─────────────┘
"""

import math

import numpy as np
from scipy import integrate, special
from scipy.optimize import minimize_scalar

from base import WeibullBase

# E[W_(i:n)] 缓存：White (1969) 对数威布尔顺序统计量一阶矩
_OS_MEANS_CACHE = {}


def _log_weibull_order_stat_mean(i, n):
    """E[W_(i:n)]，W 服从 reduced Log-Weibull 密度 h(w)=exp(w-e^w)（论文式(5)）。

    对数密度积分（w 域），避免二项式交替求和在 n>=30 时的灾难性抵消。
    """
    log_c = special.gammaln(n + 1) - special.gammaln(i) - special.gammaln(n - i + 1)

    def integrand(w):
        ew = np.exp(w)
        log_h = w - ew
        log_cdf = np.log(-np.expm1(-ew)) if ew < 700 else 0.0
        log_pdf = log_c + (i - 1) * log_cdf + (n - i) * (-ew) + log_h
        return w * np.exp(log_pdf)

    guess = math.log(-math.log(1.0 - i / (n + 1.0)))
    value, _ = integrate.quad(integrand, -60.0, 10.0, limit=400, points=[guess])
    return value


def log_weibull_order_stat_means(n):
    """长度为 n 的 E[W_(i:n)] 向量（模块级缓存）。"""
    if n not in _OS_MEANS_CACHE:
        _OS_MEANS_CACHE[n] = np.array(
            [_log_weibull_order_stat_mean(i, n) for i in range(1, n + 1)]
        )
    return _OS_MEANS_CACHE[n]


def _build_geometric_mu_grid(t_min, mu_steps):
    """从 t_min 向 0 展开的几何加密 μ 网格（近 t_min 处最密）。"""
    steps = max(8, int(mu_steps))
    min_gap = max(abs(float(t_min)) * 1e-9, 1e-12)
    gaps = np.geomspace(min_gap, float(t_min), steps)
    mus = float(t_min) - gaps
    mus[0] = float(t_min) - min_gap
    mus[-1] = 0.0
    return np.clip(mus, 0.0, None)


class LSE(WeibullBase):
    """White 最小二乘法的三参数扩展（Soman & Misra 1992）。"""

    def run(self, trace=False, mu_steps=200):
        """
        执行 LSE 参数估计。

        Args:
            trace (bool): 是否记录追踪数据。
            mu_steps (int): 位置参数几何网格采样点数（默认 200）。

        Returns:
            [shape, scale, location, r_squared, status]
        """
        # @step: 1 | 数据预处理 | 获取排序后的失效时间数据和样本数量
        # @formula: t_{(1)} \leq t_{(2)} \leq \cdots \leq t_{(n)}
        # @symbols: t|t|排序后的失效时间数组, n|n|样本数量
        # @inputs: data|t_i|原始失效时间样本
        # @outputs: t|t|排序后数组, n|n|样本数量
        t = self.data
        n = self.n

        if n < 3:
            self.last_solution_info = {"status": "insufficient_sample", "n": int(n)}
            return [0, 0, 0, 0, "insufficient_sample"]

        # @step: 2 | 计算顺序统计量期望 | 计算 reduced Log-Weibull 分布的 i 阶顺序统计量一阶矩（White 1969）
        # @formula: X_i = E[W_{(i:n)}], \quad h(w) = e^{w - e^w}
        # @symbols: X_i|X_i|对数威布尔顺序统计量期望, h(w)|h(w)|reduced Log-Weibull 密度
        # @inputs: n|n|样本数量
        # @outputs: X|X_i|顺序统计量期望数组
        X = log_weibull_order_stat_means(n)
        x_bar = X.mean()
        sxx = float(np.sum((X - x_bar) ** 2))

        # @step: 3 | 定义 White 回归与 F 比 | 对给定 μ，拟合 log(t-μ) = α + βX 并计算 Fisher F 比
        # @formula: Y_i = \log(t_i - \mu), \quad F = S_y^2 / S_{res}^2
        # @symbols: Y_i|Y_i|对数寿命, \alpha|\alpha|截距 \log b, \beta|\beta|斜率 1/c, F|F|Fisher 比
        # @inputs: X|X_i|顺序统计量期望, t|t|失效时间数组, mu|\mu|位置参数候选值
        # @outputs: slope|\beta|回归斜率, intercept|\alpha|回归截距, F|F|Fisher 比
        t_min = float(t[0])

        def white_fit(mu):
            """返回 (slope, intercept, F)；无效时返回 None。"""
            shifted = t - mu
            if np.any(shifted <= 0):
                return None
            y = np.log(shifted)
            y_bar = y.mean()
            # 退化保护：y 的相对极差低于浮点噪声级别时视为无信息样本
            if float(y[-1] - y[0]) <= max(abs(float(y_bar)), 1.0) * 1e-12:
                return None
            sy2_total = float(np.sum((y - y_bar) ** 2))
            if sxx <= 0 or sy2_total <= 0:
                return None
            slope = float(np.sum((X - x_bar) * (y - y_bar))) / sxx
            if slope <= 0:
                return None
            intercept = y_bar - slope * x_bar
            residuals = y - (intercept + slope * X)
            s_y2 = sy2_total / (n - 1)
            s_res2 = float(np.sum(residuals ** 2)) / (n - 2)
            if s_res2 <= 0:
                return slope, intercept, float("inf")
            return slope, intercept, s_y2 / s_res2

        def profile_f(mu):
            fit = white_fit(mu)
            if fit is None:
                return -float("inf")
            return fit[2]

        # @step: 4 | μ 廓线搜索 | 在 [0, t_min) 的几何加密网格上计算 F(μ)，取最大者
        # @formula: \hat{\mu}_{grid} = \arg\max_{\mu_j} F(\mu_j)
        # @symbols: \mu_j|\mu_j|位置参数候选网格, F(\mu)|F(\mu)|F 比廓线
        # @inputs: t_min|t_{(1)}|最小失效时间, mu_steps|N|网格点数
        # @outputs: mus|\mu_j|网格数组, f_values|F(\mu_j)|F 比数组
        # @loop: mu_steps 次 (默认 200)
        mus = _build_geometric_mu_grid(t_min, mu_steps)
        f_values = np.array([profile_f(m) for m in mus])

        if not np.any(np.isfinite(f_values) & (f_values > -np.inf)):
            self.last_solution_info = {"status": "degenerate_sample"}
            if trace:
                self.log_step({"phase": "failed", "reason": "degenerate_sample"})
            return [0, 0, 0, 0, "degenerate_sample"]

        best_idx = int(np.argmax(f_values))
        best_mu = float(mus[best_idx])
        best_f = float(f_values[best_idx])

        # @step: 5 | 局部精化 | 在最优网格点邻域内用有界标量优化精化 μ
        # @formula: \hat{\mu} = \arg\max_{\mu \in [\mu_{j+1}, \mu_{j-1}]} F(\mu)
        # @symbols: \hat{\mu}|\hat{\mu}|位置参数估计值
        # @inputs: mus|\mu_j|网格数组, best_idx|j^*|最优网格索引
        # @outputs: best_mu|\hat{\mu}|精化后的位置参数
        refined = False
        if math.isfinite(best_f):
            lo = float(mus[min(best_idx + 1, len(mus) - 1)])
            hi = float(mus[max(best_idx - 1, 0)])
            lo, hi = min(lo, hi), max(lo, hi)
            if hi > lo:
                res = minimize_scalar(
                    lambda m: -profile_f(m),
                    bounds=(lo, hi),
                    method="bounded",
                    options={"xatol": max(t_min * 1e-10, 1e-12)},
                )
                if math.isfinite(res.fun) and -float(res.fun) >= best_f:
                    best_mu = float(res.x)
                    best_f = -float(res.fun)
                    refined = True

        fit = white_fit(best_mu)
        if fit is None:
            self.last_solution_info = {"status": "invalid_fit", "mu": best_mu}
            if trace:
                self.log_step({"phase": "failed", "reason": "invalid_fit", "mu": best_mu})
            return [0, 0, 0, 0, "invalid_fit"]

        slope, intercept, f_final = fit

        # @step: 6 | 反解参数 | 由回归系数反解形状与尺度参数（论文式(6)）
        # @formula: \hat{c} = 1/\hat{\beta}, \quad \hat{b} = e^{\hat{\alpha}}
        # @symbols: \hat{c}|\hat{c}|形状参数估计值, \hat{b}|\hat{b}|尺度参数估计值
        # @inputs: slope|\hat{\beta}|回归斜率, intercept|\hat{\alpha}|回归截距
        # @outputs: shape|\hat{c}|形状参数, scale|\hat{b}|尺度参数
        shape = 1.0 / slope
        scale = math.exp(intercept)

        # @step: 7 | 计算拟合优度 R² | 评估模型与数据的拟合程度
        # @formula: R^2 = 1 - \frac{\sum(F_i - \hat{F}_i)^2}{\sum(F_i - \bar{F})^2}
        # @symbols: R^2|R^2|决定系数
        # @inputs: shape|\hat{c}|形状参数, scale|\hat{b}|尺度参数, best_mu|\hat{\mu}|位置参数
        # @outputs: r2|R^2|拟合优度
        r2 = self._calculate_r2(shape, scale, best_mu)

        self.last_solution_info = {
            "status": "ok",
            "strategy": "profile_f_max",
            "constraint": "gamma >= 0",
            "f_max": f_final if math.isfinite(f_final) else None,
            "mu_grid_points": int(len(mus)),
            "refined": bool(refined),
            "location_at_zero_boundary": bool(best_mu == 0.0),
            "optimal_mu": best_mu,
            "optimal_shape": float(shape),
        }

        if trace:
            curve = [
                {"mu": float(m), "f_ratio": (float(f) if math.isfinite(f) else None)}
                for m, f in zip(mus, f_values)
            ]
            self.trace_data = {
                "f_mu_curve": curve,
                **self.last_solution_info,
            }

        return [float(shape), float(scale), float(best_mu), float(r2), True]
