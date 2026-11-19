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
from .calculation_trace import plot_point, plot_series, plot_chart, calculation_step, regression_calculation

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
        self.calculation_trace = None
        evaluations = []
        t = self.data
        n = self.n

        if n < 3:
            self.last_solution_info = {"status": "insufficient_sample", "n": int(n)}
            return [0, 0, 0, 0, "insufficient_sample"]

        X = log_weibull_order_stat_means(n)
        x_bar = X.mean()
        sxx = float(np.sum((X - x_bar) ** 2))

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
            f_ratio = float('inf') if s_res2 <= 0 else s_y2 / s_res2
            if trace:
                evaluations.append(dict(x=float(mu), y=f_ratio, slope=slope, intercept=intercept,
                                        evaluation=len(evaluations) + 1))
            return slope, intercept, f_ratio

        def profile_f(mu):
            fit = white_fit(mu)
            if fit is None:
                return -float("inf")
            return fit[2]

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

        shape = 1.0 / slope
        scale = math.exp(intercept)

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
            # Reuse recorded White fits for linked reading. These views neither
            # call a second estimator nor enter the position selection above.
            finite_fits = {p['x']: p for p in evaluations if math.isfinite(p['y'])}
            ordered_fits = sorted(finite_fits.values(), key=lambda p: p['x'])
            view_positions = {float(best_mu)}
            if ordered_fits:
                targets = list(np.linspace(0.0, t_min, 9)) + [
                    best_mu - (t_min - best_mu), best_mu + (t_min - best_mu) / 2.0]
                view_positions.update(min(ordered_fits, key=lambda p: abs(p['x'] - target))['x']
                                      for target in targets)
            regression_views = []
            for mu in sorted(view_positions):
                point = finite_fits.get(mu)
                if point is None:
                    continue
                b, a = point['slope'], point['intercept']
                regression_views.append(dict(
                    gamma=mu, criterion=point['y'], slope=b, intercept=a,
                    beta=1.0 / b, eta=math.exp(a), selected=mu == best_mu,
                    points=[dict(x=float(xi), y=float(yi), fit=float(a + b * xi),
                                 observation=float(ti), distance=float(ti-mu))
                            for xi, yi, ti in zip(X, np.log(t - mu), t)]))
                regression_views[-1]['calculation'] = regression_calculation(regression_views[-1]['points'])
            curve = [
                {"mu": float(m), "f_ratio": (float(f) if math.isfinite(f) else None)}
                for m, f in zip(mus, f_values)
            ]
            self.trace_data = {
                "f_mu_curve": curve,
                **self.last_solution_info,
            }
            description = '在非负位置域内比较 F 比，保留网格及邻域精化中 F 最大的候选。'
            self.calculation_trace = dict(
                schema_version=1, method='lse', criterion=dict(description=description),
                selection=dict(description=description, status='ok', beta=float(shape),
                               eta=float(scale), gamma=float(best_mu),
                               f_ratio=float(f_final) if math.isfinite(f_final) else None),
                charts=[plot_chart(
                    'f-location', '位置参数的 F 比判据', '位置参数 γ', 'F 比',
                    [plot_series('f', '实际网格与精化求值',
                                 [plot_point(p['x'], p['y'], evaluation=p['evaluation']) for p in evaluations])],
                    formula=r'\hat\gamma=\arg\max_\gamma F(\gamma),\quad F=S_Y^2/S_{\mathrm{res}}^2',
                    description='比较各位置下的 White 回归 F 比，最高点确定 γ̂。',
                    selected=[plot_point(best_mu, f_final, label='最终选择')]),
                    plot_chart('white-regression', '最终位置下的 White 回归',
                               '顺序统计量期望 E[W₍ᵢ:ₙ₎]', '对数寿命 ln(tᵢ−γ̂)',
                               [plot_series('observations', '实际回归点',
                                            [plot_point(a, b) for a, b in zip(X, np.log(t - best_mu))],
                                            kind='scatter'),
                                plot_series('fit', '本次拟合直线',
                                            [plot_point(a, intercept + slope * a) for a in X])],
                               formula=r'\ln(t_i-\hat\gamma)=a+bE[W_{(i:n)}],\quad\hat\beta=1/b,\quad\hat\eta=e^a',
                               description='固定左图选中的位置后回归；斜率 b=1/β̂，截距 a=ln η̂。')],
                recovery=[calculation_step('F 比最大处确定位置', r'\hat\gamma=\arg\max_\gamma F(\gamma)',
                                           [('γ̂', best_mu), ('F', f_final)]),
                          calculation_step('回归斜率确定形状', r'\hat\beta=1/b', [('b', slope), ('β̂', shape)]),
                          calculation_step('回归截距确定尺度', r'\hat\eta=e^a', [('a', intercept), ('η̂', scale)])],
                details=dict(**self.last_solution_info, slope=slope, intercept=intercept,
                             order_statistic_means=X.tolist(), evaluations=evaluations,
                             regression_views=regression_views,
                             reference=dict(paper='Soman–Misra (1992)', section='§2 Procedure，表1–2')))

        return [float(shape), float(scale), float(best_mu), float(r2), True]


# @method-flow
# {
#   "schemaVersion": 2,
#   "methodId": "lse",
#   "methodName": "最小二乘估计 (LSE)",
#   "description": "White顺序统计量回归 → F比廓线定位 → 回归系数反解三参数。",
#   "steps": [
#     {
#       "name": "数据预处理",
#       "description": "获取排序后的失效时间数据和样本数量",
#       "formula": {
#         "symbols": [
#           {
#             "symbol": "t",
#             "meaning": "排序后的失效时间数组"
#           },
#           {
#             "symbol": "n",
#             "meaning": "样本数量"
#           }
#         ],
#         "explanation": "获取排序后的失效时间数据和样本数量",
#         "equations": [
#           "t_{(1)} \\leq t_{(2)} \\leq \\cdots \\leq t_{(n)}"
#         ]
#       },
#       "inputs": [
#         "samples"
#       ],
#       "outputs": [
#         "ordered",
#         "n"
#       ],
#       "basis": "公共输入规则：有限、严格为正的失效时间，统一排序。",
#       "notes": "当前实现处理完整失效样本；不包含删失样本似然。本方法在 run 内要求 n≥3。",
#       "sources": [
#         {
#           "file": "python/base.py",
#           "symbol": "WeibullBase.__init__"
#         },
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "LSE.run",
#           "label": "本步实现",
#           "from": "self.calculation_trace = None",
#           "until": "X = log_weibull_order_stat_means(n)"
#         }
#       ],
#       "id": 1,
#       "primarySource": 1,
#       "flow": {
#         "label": "排序样本"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "samples"
#           ],
#           "name": "寿命样本",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "ordered",
#             "n"
#           ],
#           "name": "有序样本",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "name": "计算顺序统计量期望",
#       "description": "计算 reduced Log-Weibull 分布的 i 阶顺序统计量一阶矩（White 1969）",
#       "formula": {
#         "explanation": "计算 reduced Log-Weibull 分布的 i 阶顺序统计量一阶矩（White 1969）",
#         "symbols": [
#           {
#             "symbol": "X_i",
#             "meaning": "顺序统计量期望"
#           },
#           {
#             "symbol": "H,h",
#             "meaning": "reduced Log-Weibull分布函数与密度"
#           },
#           {
#             "symbol": "n,i",
#             "meaning": "样本量与顺序"
#           }
#         ],
#         "equations": [
#           "X_i=\\int_{-\\infty}^{\\infty}w\\,\\frac{n!}{(i-1)!(n-i)!}H(w)^{i-1}[1-H(w)]^{n-i}h(w)\\,dw,\\quad H(w)=1-e^{-e^w},\\quad h(w)=e^{w-e^w}"
#         ]
#       },
#       "inputs": [
#         "n"
#       ],
#       "outputs": [
#         "order_means"
#       ],
#       "basis": "方法构造：White reduced Log-Weibull顺序统计量期望，不以中位秩近似替代。",
#       "notes": "",
#       "sources": [
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "LSE.run",
#           "label": "本步实现",
#           "from": "X = log_weibull_order_stat_means(n)",
#           "until": "t_min = float(t[0])"
#         },
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "log_weibull_order_stat_means"
#         },
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "_log_weibull_order_stat_mean"
#         }
#       ],
#       "id": 2,
#       "primarySource": 2,
#       "flow": {
#         "label": "求顺序统计量期望",
#         "symbol": "X_i=E[W_{(i:n)}]"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "n"
#           ],
#           "name": "样本量",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "order_means"
#           ],
#           "name": "顺序统计量期望",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "name": "逐个位置回归，比较 F 比",
#       "description": "每换一个位置γ，都平移样本、做一次White回归并计算F；比较后保留F最大的那组参数。",
#       "formula": {
#         "explanation": "每换一个位置γ，都平移样本、做一次White回归并计算F；比较后保留F最大的那组参数。",
#         "symbols": [
#           {
#             "symbol": "a,b",
#             "meaning": "回归截距与斜率"
#           },
#           {
#             "symbol": "F",
#             "meaning": "用于定位的方差比"
#           },
#           {
#             "symbol": "Y_i",
#             "meaning": "平移后对数寿命"
#           }
#         ],
#         "equations": [
#           "\\begin{gathered}Y_i=\\ln(t_i-\\gamma)=a+bX_i\\\\[5pt] b=\\frac{\\sum(X_i-\\bar X)(Y_i-\\bar Y)}{\\sum(X_i-\\bar X)^2}\\\\[5pt] F=\\frac{\\sum(Y_i-\\bar Y)^2/(n-1)}{\\sum(Y_i-a-bX_i)^2/(n-2)}\\end{gathered}\\qquad\\hat\\gamma=\\arg\\max_\\gamma F(\\gamma)"
#         ]
#       },
#       "inputs": [
#         "order_means",
#         "ordered"
#       ],
#       "outputs": [
#         "gamma_hat",
#         "slope",
#         "intercept"
#       ],
#       "basis": "Soman–Misra（1992）§2 Procedure步骤1–4：位置平移、White回归、F比比较；F的总方差除以n−1、残差方差除以n−2。",
#       "notes": "原文由最小观测附近逐减位置；现行程序以位置网格及邻域精化求同一F最大化目标。White顺序统计量期望由积分得到，未沿用原数表。",
#       "sources": [
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "_build_geometric_mu_grid"
#         },
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "LSE.run",
#           "from": "f_values = np.array",
#           "until": "shape = 1.0 / slope"
#         },
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "LSE.run.profile_f"
#         },
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "LSE.run.white_fit"
#         },
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "LSE.run",
#           "label": "本步实现",
#           "from": "shape = 1.0 / slope",
#           "until": "r2 = self._calculate_r2"
#         }
#       ],
#       "id": 3,
#       "primarySource": 3,
#       "flow": {
#         "label": "最大F比确定位置",
#         "symbol": "\\max_\\gamma F(\\gamma)"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "order_means"
#           ],
#           "name": "统计量期望",
#           "wrap": 2
#         },
#         "input-1": {
#           "refs": [
#             "ordered"
#           ],
#           "name": "有序样本",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "gamma_hat",
#             "intercept",
#             "slope"
#           ],
#           "name": "位置与回归",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "name": "反解参数",
#       "description": "由回归系数反解形状与尺度参数（论文式(6)）",
#       "formula": {
#         "explanation": "由回归系数反解形状与尺度参数（论文式(6)）",
#         "symbols": [
#           {
#             "symbol": "\\hat\\beta",
#             "meaning": "形状参数"
#           },
#           {
#             "symbol": "\\hat\\eta",
#             "meaning": "尺度参数"
#           },
#           {
#             "symbol": "\\hat\\gamma",
#             "meaning": "位置参数"
#           }
#         ],
#         "equations": [
#           "\\hat\\beta=1/b,\\quad \\hat\\eta=e^a,\\quad \\hat\\gamma=\\texttt{best\\_mu}"
#         ]
#       },
#       "inputs": [
#         "slope",
#         "intercept",
#         "gamma_hat"
#       ],
#       "outputs": [
#         "beta_hat",
#         "eta_hat"
#       ],
#       "basis": "参数映射：本文统一用β、η、γ；原论文c、b、μ分别对应β、η、γ。",
#       "notes": "",
#       "sources": [
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "LSE.run",
#           "label": "本步实现",
#           "from": "shape = 1.0 / slope",
#           "until": "r2 = self._calculate_r2"
#         }
#       ],
#       "id": 4,
#       "primarySource": 0,
#       "flow": {
#         "label": "回归求形状与尺度"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "gamma_hat",
#             "intercept",
#             "slope"
#           ],
#           "name": "位置与回归",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "beta_hat",
#             "eta_hat"
#           ],
#           "name": "形状与尺度",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "name": "计算拟合优度并返回",
#       "description": "评估模型与数据的拟合程度",
#       "formula": {
#         "explanation": "评估模型与数据的拟合程度",
#         "symbols": [
#           {
#             "symbol": "R^2",
#             "meaning": "概率图决定系数"
#           },
#           {
#             "symbol": "p_i",
#             "meaning": "绘图位置"
#           },
#           {
#             "symbol": "y_i",
#             "meaning": "变换后的经验值"
#           },
#           {
#             "symbol": "\\hat y_i",
#             "meaning": "参数预测值"
#           }
#         ],
#         "equations": [
#           "y_i=\\ln[-\\ln(1-p_i)],\\quad \\hat y_i=\\beta\\ln(t_i-\\gamma)-\\beta\\ln\\eta,\\quad R^2=1-\\frac{\\sum_i(y_i-\\hat y_i)^2}{\\sum_i(y_i-\\bar y)^2}"
#         ]
#       },
#       "inputs": [
#         "beta_hat",
#         "eta_hat",
#         "gamma_hat"
#       ],
#       "outputs": [
#         "beta_hat",
#         "eta_hat",
#         "gamma_hat",
#         "r_squared",
#         "status"
#       ],
#       "basis": "项目诊断：共用基础类的概率图 R²，不参与核心参数求解。",
#       "notes": "γ触及样本最小值或总平方和为零时返回0；普通情况下允许负R²。",
#       "sources": [
#         {
#           "file": "python/base.py",
#           "symbol": "WeibullBase._calculate_r2"
#         },
#         {
#           "file": "python/base.py",
#           "symbol": "WeibullBase._median_ranks"
#         },
#         {
#           "file": "python/methods/lse.py",
#           "symbol": "LSE.run",
#           "from": "r2 = self._calculate_r2"
#         }
#       ],
#       "id": 5,
#       "primarySource": 0,
#       "flow": {
#         "label": "汇总参数与拟合优度",
#         "symbol": "(\\hat\\beta,\\hat\\eta,\\hat\\gamma,R^2)"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "beta_hat",
#             "eta_hat"
#           ],
#           "name": "形状与尺度",
#           "wrap": 2
#         },
#         "input-1": {
#           "refs": [
#             "gamma_hat"
#           ],
#           "name": "位置估计",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "beta_hat",
#             "eta_hat",
#             "gamma_hat",
#             "r_squared"
#           ],
#           "name": "估计结果",
#           "wrap": 2
#         }
#       }
#     }
#   ],
#   "workflow": {
#     "title": "计算流程",
#     "description": "White顺序统计量回归 → F比廓线定位 → 回归系数反解三参数。",
#     "targets": {
#       "samples": 1,
#       "transformation": 2,
#       "location": 3,
#       "regression": 4,
#       "result": 5
#     },
#     "items": [
#       {
#         "kind": "group",
#         "layout": "module",
#         "children": [
#           {
#             "kind": "port",
#             "anchor": "i1-1",
#             "target": "samples",
#             "direction": "input",
#             "external": true,
#             "group": "input-0"
#           },
#           {
#             "kind": "step",
#             "anchor": "s1",
#             "step": 1,
#             "target": "samples"
#           },
#           {
#             "kind": "port",
#             "anchor": "o1",
#             "target": "samples",
#             "direction": "output",
#             "group": "output-0"
#           }
#         ]
#       },
#       {
#         "kind": "group",
#         "layout": "module",
#         "children": [
#           {
#             "kind": "port",
#             "anchor": "i2-1",
#             "target": "transformation",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "step",
#             "anchor": "s2",
#             "step": 2,
#             "target": "transformation"
#           },
#           {
#             "kind": "port",
#             "anchor": "o2",
#             "target": "transformation",
#             "direction": "output",
#             "group": "output-0"
#           }
#         ]
#       },
#       {
#         "kind": "group",
#         "layout": "module",
#         "children": [
#           {
#             "kind": "port",
#             "anchor": "i3-1",
#             "target": "location",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "port",
#             "anchor": "i3-2",
#             "target": "location",
#             "direction": "input",
#             "group": "input-1"
#           },
#           {
#             "kind": "step",
#             "anchor": "s3",
#             "step": 3,
#             "target": "location"
#           },
#           {
#             "kind": "port",
#             "anchor": "o3",
#             "target": "location",
#             "direction": "output",
#             "group": "output-0"
#           }
#         ]
#       },
#       {
#         "kind": "group",
#         "layout": "module",
#         "children": [
#           {
#             "kind": "port",
#             "anchor": "i4-1",
#             "target": "regression",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "step",
#             "anchor": "s4",
#             "step": 4,
#             "target": "regression"
#           },
#           {
#             "kind": "port",
#             "anchor": "o4",
#             "target": "regression",
#             "direction": "output",
#             "group": "output-0"
#           }
#         ]
#       },
#       {
#         "kind": "group",
#         "layout": "module",
#         "children": [
#           {
#             "kind": "port",
#             "anchor": "i5-1",
#             "target": "result",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "port",
#             "anchor": "i5-2",
#             "target": "result",
#             "direction": "input",
#             "group": "input-1"
#           },
#           {
#             "kind": "step",
#             "anchor": "s5",
#             "step": 5,
#             "target": "result"
#           },
#           {
#             "kind": "port",
#             "anchor": "o5",
#             "target": "result",
#             "direction": "output",
#             "group": "output-0"
#           }
#         ]
#       }
#     ],
#     "connections": [
#       {
#         "from": "o1",
#         "to": "i2-1"
#       },
#       {
#         "from": "o2",
#         "to": "i3-1"
#       },
#       {
#         "from": "o1",
#         "to": "i3-2"
#       },
#       {
#         "from": "o3",
#         "to": "i4-1"
#       },
#       {
#         "from": "o4",
#         "to": "i5-1"
#       },
#       {
#         "from": "o3",
#         "to": "i5-2"
#       }
#     ]
#   },
#   "variables": {
#     "samples": {
#       "symbol": "t_i",
#       "name": "样本",
#       "meaning": "样本",
#       "code": "data"
#     },
#     "ordered": {
#       "symbol": "t_{(i)}",
#       "name": "有序样本",
#       "meaning": "有序样本",
#       "code": "t"
#     },
#     "n": {
#       "symbol": "n",
#       "name": "样本量",
#       "meaning": "样本量",
#       "code": "n"
#     },
#     "beta_hat": {
#       "symbol": "\\hat\\beta",
#       "name": "形状估计",
#       "meaning": "形状估计",
#       "code": "final_beta",
#       "axisLabel": "形状参数 β"
#     },
#     "eta_hat": {
#       "symbol": "\\hat\\eta",
#       "name": "尺度估计",
#       "meaning": "尺度估计",
#       "code": "final_eta",
#       "axisLabel": "尺度参数 η"
#     },
#     "gamma_hat": {
#       "symbol": "\\hat\\gamma",
#       "name": "位置估计",
#       "meaning": "位置估计",
#       "code": "final_gamma",
#       "axisLabel": "位置参数 γ"
#     },
#     "r_squared": {
#       "symbol": "R^2",
#       "name": "拟合优度",
#       "meaning": "拟合优度",
#       "code": "r_squared"
#     },
#     "status": {
#       "symbol": "\\mathrm{status}",
#       "name": "求解状态",
#       "meaning": "求解状态",
#       "code": "process_status"
#     },
#     "gamma_axis": {
#       "symbol": "\\gamma",
#       "name": "位置",
#       "meaning": "位置",
#       "axisLabel": "位置参数 γ",
#       "code": "gamma_axis"
#     },
#     "order_means": {
#       "symbol": "X_i",
#       "name": "顺序统计量期望",
#       "meaning": "顺序统计量期望",
#       "code": "value",
#       "axisLabel": "White 顺序统计量期望 Xᵢ"
#     },
#     "slope": {
#       "symbol": "b",
#       "name": "采纳回归斜率",
#       "meaning": "采纳回归斜率",
#       "code": "final_slope"
#     },
#     "intercept": {
#       "symbol": "a",
#       "name": "采纳回归截距",
#       "meaning": "采纳回归截距",
#       "code": "final_intercept"
#     },
#     "criterion": {
#       "symbol": "F(\\gamma)",
#       "name": "位置判据",
#       "meaning": "位置判据",
#       "code": "criterion",
#       "axisLabel": "F 比 F(γ)"
#     },
#     "regression_y": {
#       "symbol": "Y_i",
#       "name": "平移对数寿命",
#       "meaning": "平移对数寿命",
#       "axisLabel": "平移对数寿命 Yᵢ",
#       "code": "regression_y"
#     }
#   },
#   "chartBindings": {
#     "white-regression": {
#       "x": "order_means",
#       "y": "regression_y"
#     },
#     "f-location": {
#       "x": "gamma_axis",
#       "y": "criterion"
#     }
#   }
# }
# @end-method-flow
