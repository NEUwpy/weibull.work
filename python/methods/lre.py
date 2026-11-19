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
from .calculation_trace import plot_point, plot_series, plot_chart, calculation_step, regression_calculation


class LRE(WeibullBase):
    def run(self, trace=False):
        """
        LRE 参数估计
        策略：
        1. 先检查原始样本是否存在有意义的信息（退化检测在优化前）。
        2. 使用 Park 分段绘图位置，优化 γ 使相关系数 ρ 最大。
        3. 固定 γ 后 OLS 回归解 β 和 η。
        """
        self.calculation_trace = None
        evaluations = []
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

        # 此估计器的绘图位置由论文固定，不消费基础类的 Bernard/exact 开关。
        ranks = np.arange(1, n + 1, dtype=float)
        F = (ranks - 3 / 8) / (n + 1 / 4) if n <= 10 else (ranks - 1 / 2) / n
        self.plotting_positions = F
        y = np.log(-np.log1p(-F))
        y_centered = y - np.mean(y)
        y_ss = float(np.dot(y_centered, y_centered))

        y_var = float(np.var(y))
        if y_var <= 0:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

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
            rho = float(np.dot(centered, y_centered) / np.sqrt(x_ss * y_ss))
            if trace:
                evaluations.append(dict(x=float(-t_min * np.expm1(s)), y=rho,
                                        s=float(s), evaluation=len(evaluations) + 1))
            return -rho

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

        x_vals = np.log((t - gamma_hat) / t_min)
        x_mean = float(np.mean(x_vals))
        y_mean = float(np.mean(y))

        numerator = float(np.sum((x_vals - x_mean) * (y - y_mean)))
        denominator = float(np.sum((x_vals - x_mean) ** 2))

        if not np.isfinite(denominator) or denominator <= 0:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        beta_hat = numerator / denominator

        if not (np.isfinite(beta_hat) and beta_hat > 0):
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        intercept = y_mean - beta_hat * x_mean
        eta_hat = t_min * math.exp(-intercept / beta_hat)

        if not np.isfinite(eta_hat) or eta_hat <= 0:
            self.last_solution_info = {"status": "degenerate_sample"}
            return [0, 0, 0, 0, "degenerate_sample"]

        residual = y - (beta_hat * x_vals + intercept)
        r2 = 1.0 - float(np.dot(residual, residual)) / y_ss

        self.last_solution_info = {
            "status": "ok",
            "implementation": "park2017_proposed_plot",
            "plotting_positions": "blom" if n <= 10 else "(i-0.5)/n",
            "strategy": "correlation_maximization",
            "constraint": "0 <= gamma < t[0]",
            "gamma_grid_points": int(len(search_grid)),
            "refined": bool(refined),
            "rho_squared": float(r2),
            "location_at_zero_boundary": bool(gamma_hat == 0.0),
        }

        if trace:
            description = '按 Park Proposed+Plot 的绘图位置，在非负位置域内最大化相关系数，再作概率图 OLS。'
            rho = -best_objective
            physical_x = x_vals + math.log(t_min)
            physical_intercept = intercept - beta_hat * math.log(t_min)
            # Probability plots at locations already evaluated by this run.
            # Keep the stable log-gap coordinate used by the actual objective.
            finite_points = {p['x']: p for p in evaluations if math.isfinite(p['y'])}
            ordered_points = sorted(finite_points.values(), key=lambda p: p['x'])
            chosen = {float(gamma_hat)}
            targets = list(np.linspace(0.0, t_min, 9)) + [
                gamma_hat - (t_min - gamma_hat), gamma_hat + (t_min - gamma_hat) / 2.0]
            chosen.update(min(ordered_points, key=lambda p: abs(p['x'] - target))['x']
                          for target in targets)

            def regression_view(gamma):
                point = finite_points.get(gamma)
                if gamma == gamma_hat:
                    u, b, a, correlation = physical_x, float(beta_hat), float(physical_intercept), rho
                else:
                    u = np.log(relative_excess + np.exp(point['s'])) + math.log(t_min)
                    centered = u - np.mean(u)
                    b = float(np.dot(centered, y_centered) / np.dot(centered, centered))
                    a = float(np.mean(y) - b * np.mean(u))
                    correlation = point['y']
                view = dict(gamma=float(gamma), criterion=float(correlation), slope=b, intercept=a,
                            beta=b, eta=float(eta_hat) if gamma == gamma_hat else float(math.exp(-a / b)),
                            selected=gamma == gamma_hat,
                            points=[dict(x=float(xi), y=float(yi), fit=float(a + b * xi),
                                         probability=float(pi), lifetime=float(np.exp(xi)), observation=float(ti),
                                         distance=float(np.exp(xi)))
                                    for xi, yi, pi, ti in zip(u, y, F, t)])
                view['calculation'] = regression_calculation(view['points'])
                view['distance_precision_note'] = bool(view['points'][0]['distance'] < np.finfo(float).eps*t_min*100)
                return view

            regression_views = [regression_view(gamma) for gamma in sorted(chosen)]
            original_regression = regression_view(0.0)
            self.calculation_trace = dict(
                schema_version=1, method='lre', criterion=dict(description=description),
                selection=dict(description=description, status='ok', beta=float(beta_hat),
                               eta=float(eta_hat), gamma=float(gamma_hat), rho=float(rho)),
                charts=[plot_chart(
                    'correlation-location', '位置参数的相关系数判据', '位置参数 γ', '相关系数 ρ',
                    [plot_series('rho', '实际网格与精化求值', evaluations)],
                    selected=[plot_point(gamma_hat, rho, label='相关系数最大候选')],
                    formula=r'\hat\gamma=\arg\max_\gamma\rho\!\left(\ln(t_i-\gamma),\ln[-\ln(1-p_i)]\right)',
                    description='选择使概率图最接近直线的位置，即相关系数最大处。'),
                    plot_chart('park-probability-regression', '最终位置下的概率图回归',
                               '对数寿命 ln(tᵢ−γ̂)', 'Weibull 分数 ln[−ln(1−Fᵢ)]',
                               [plot_series('observations', 'Park 绘图位置',
                                            [plot_point(a, b) for a, b in zip(physical_x, y)], kind='scatter'),
                                plot_series('fit', '本次 OLS 直线',
                                            [plot_point(a, beta_hat * a + physical_intercept) for a in physical_x])],
                               formula=r'Y_i=a+b\ln(t_i-\hat\gamma),\quad\hat\beta=b,\quad\hat\eta=e^{-a/b}',
                               description='固定左图选中的位置后作 OLS；斜率 b=β̂，截距 a=−β̂ ln η̂。')],
                recovery=[calculation_step('相关系数最大处确定位置', r'\hat\gamma=\arg\max_\gamma\rho(\gamma)',
                                           [('γ̂', gamma_hat), ('ρ', rho)]),
                          calculation_step('概率图斜率确定形状', r'\hat\beta=b', [('b', beta_hat), ('β̂', beta_hat)]),
                          calculation_step('概率图截距确定尺度', r'\hat\eta=e^{-a/b}',
                                           [('a', physical_intercept), ('η̂', eta_hat)])],
                details=dict(**self.last_solution_info, slope=float(beta_hat),
                             intercept=float(physical_intercept), evaluations=evaluations,
                             regression_views=regression_views, original_regression=original_regression,
                             reference=dict(paper='Park (2017)', section='§5 Proposed+Plot，图4–5')))
            self.trace_data = self.calculation_trace

        return [float(beta_hat), float(eta_hat), float(gamma_hat), float(r2), True]


# @method-flow
# {
#   "schemaVersion": 2,
#   "methodId": "lre",
#   "methodName": "线性回归 (LRE)",
#   "description": "Park绘图位置 → 相关系数定位 → OLS形状与尺度。",
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
#           "file": "python/methods/lre.py",
#           "symbol": "LRE.run",
#           "label": "本步实现",
#           "from": "self.calculation_trace = None",
#           "until": "ranks = np.arange"
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
#       "name": "计算绘图位置",
#       "description": "n≤10 用 Blom，n≥11 用 (i−1/2)/n",
#       "formula": {
#         "symbols": [
#           {
#             "symbol": "F(t_i)",
#             "meaning": "第i个样本的经验累积概率"
#           },
#           {
#             "symbol": "y_i",
#             "meaning": "变换后的因变量"
#           }
#         ],
#         "explanation": "n≤10 用 Blom，n≥11 用 (i−1/2)/n",
#         "equations": [
#           "p_i=\\begin{cases}(i-3/8)/(n+1/4),&n\\leq10\\\\(i-1/2)/n,&n\\geq11\\end{cases},\\quad y_i=\\ln(-\\ln(1-p_i))"
#         ]
#       },
#       "inputs": [
#         "n"
#       ],
#       "outputs": [
#         "ranks",
#         "scores"
#       ],
#       "basis": "Park (2017) Proposed+Plot构造：小样本用Blom，大样本用(i−1/2)/n。",
#       "notes": "固定使用本方法的分段绘图位置；不消费基础类Bernard/exact开关。",
#       "sources": [
#         {
#           "file": "python/methods/lre.py",
#           "symbol": "LRE.run",
#           "label": "本步实现",
#           "from": "ranks = np.arange",
#           "until": "t_min = float(t[0])"
#         }
#       ],
#       "id": 2,
#       "primarySource": 0,
#       "flow": {
#         "label": "求绘图位置与概率变换",
#         "symbol": "Y_i=\\ln[-\\ln(1-p_i)]"
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
#             "ranks",
#             "scores"
#           ],
#           "name": "绘图位置与分数",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "name": "让概率图最直，确定位置",
#       "description": "按Park式(2)比较各位置下概率图的相关系数，取最大值确定γ。",
#       "formula": {
#         "symbols": [
#           {
#             "symbol": "\\gamma",
#             "meaning": "位置参数候选值"
#           },
#           {
#             "symbol": "\\rho",
#             "meaning": "Pearson 相关系数"
#           }
#         ],
#         "explanation": "按Park式(2)比较各位置下概率图的相关系数，取最大值确定γ。",
#         "equations": [
#           "\\hat{\\gamma} = \\arg\\max_{\\gamma \\in [0,t_{(1)})} \\rho(\\gamma), \\rho = \\mathrm{corr}(\\ln(t-\\gamma), y)"
#         ]
#       },
#       "inputs": [
#         "scores",
#         "ordered"
#       ],
#       "outputs": [
#         "gamma_hat"
#       ],
#       "basis": "Park（2017）§5式(2)、图4：最大化相关系数确定位置；式(3)给出等价求根条件。",
#       "notes": "包含γ=0；上界取nextafter(tmin,0)。不假定目标单峰，无有效候选时失败。",
#       "sources": [
#         {
#           "file": "python/methods/lre.py",
#           "symbol": "LRE.run",
#           "from": "t_min = float(t[0])",
#           "until": "def negative_correlation(s):"
#         },
#         {
#           "file": "python/methods/lre.py",
#           "symbol": "LRE.run",
#           "from": "search_grid = np.unique",
#           "until": "best_idx = int"
#         },
#         {
#           "file": "python/methods/lre.py",
#           "symbol": "LRE.run.negative_correlation"
#         },
#         {
#           "file": "python/methods/lre.py",
#           "symbol": "LRE.run",
#           "from": "best_idx = int",
#           "until": "x_vals = np.log((t - gamma_hat) / t_min)"
#         }
#       ],
#       "id": 3,
#       "primarySource": 3,
#       "flow": {
#         "label": "最大相关确定位置",
#         "symbol": "\\max_\\gamma\\rho(\\gamma)"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "scores"
#           ],
#           "name": "概率分数",
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
#             "gamma_hat"
#           ],
#           "name": "位置估计",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "name": "平移后回归，读出形状与尺度",
#       "description": "固定选中位置，把寿命减去γ后做概率图OLS；直线斜率就是形状，截距用于恢复尺度。",
#       "formula": {
#         "explanation": "固定选中位置，把寿命减去γ后做概率图OLS；直线斜率就是形状，截距用于恢复尺度。",
#         "symbols": [
#           {
#             "symbol": "x_i",
#             "meaning": "归一化对数横坐标"
#           },
#           {
#             "symbol": "\\hat\\beta",
#             "meaning": "回归斜率即形状参数"
#           }
#         ],
#         "equations": [
#           "Y_i=a+b\\ln(t_i-\\hat\\gamma),\\quad b=\\frac{\\sum(X_i-\\bar X)(Y_i-\\bar Y)}{\\sum(X_i-\\bar X)^2},\\quad\\hat\\beta=b,\\quad\\hat\\eta=e^{-a/b}"
#         ]
#       },
#       "inputs": [
#         "gamma_hat",
#         "ordered",
#         "scores"
#       ],
#       "outputs": [
#         "beta_hat",
#         "eta_hat"
#       ],
#       "basis": "Park（2017）§2直线关系、§5 Proposed+Plot及图5：先定位，再对平移样本回归。",
#       "notes": "源码用寿命单位归一化改善数值稳定性，恢复尺度时乘回tmin；要求斜率及尺度为有限正数。",
#       "sources": [
#         {
#           "file": "python/methods/lre.py",
#           "symbol": "LRE.run",
#           "label": "本步实现",
#           "from": "x_vals = np.log((t - gamma_hat) / t_min)",
#           "until": "if not (np.isfinite(beta_hat) and beta_hat > 0):"
#         },
#         {
#           "file": "python/methods/lre.py",
#           "symbol": "LRE.run",
#           "label": "本步实现",
#           "from": "if not (np.isfinite(beta_hat) and beta_hat > 0):",
#           "until": "residual = y - (beta_hat * x_vals + intercept)"
#         }
#       ],
#       "id": 4,
#       "primarySource": 0,
#       "flow": {
#         "label": "平移回归求形状与尺度"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "gamma_hat"
#           ],
#           "name": "位置估计",
#           "wrap": 2
#         },
#         "input-1": {
#           "refs": [
#             "ordered",
#             "scores"
#           ],
#           "name": "样本与分数",
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
#       "description": "与位置搜索采用同一组 Park 绘图位置",
#       "formula": {
#         "symbols": [
#           {
#             "symbol": "R^2",
#             "meaning": "概率图决定系数"
#           },
#           {
#             "symbol": "y_i",
#             "meaning": "变换后的绘图分数"
#           }
#         ],
#         "explanation": "与位置搜索采用同一组 Park 绘图位置",
#         "equations": [
#           "R^2 = 1-\\frac{\\sum(y_i-\\hat{y}_i)^2}{\\sum(y_i-\\bar{y})^2}=\\rho^2"
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
#       "basis": "项目诊断：使用同一组Park绘图位置计算概率图R²，OLS含截距时等于ρ²。",
#       "notes": "本方法直接计算R²；不调用基础类的绘图位置。trace包含候选结果与最终结果。",
#       "sources": [
#         {
#           "file": "python/methods/lre.py",
#           "symbol": "LRE.run",
#           "label": "本步实现",
#           "from": "residual = y - (beta_hat * x_vals + intercept)"
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
#     "description": "Park绘图位置 → 相关系数定位 → OLS形状与尺度。",
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
#             "kind": "port",
#             "anchor": "i4-2",
#             "target": "regression",
#             "direction": "input",
#             "group": "input-1"
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
#         "from": "o1",
#         "to": "i4-2"
#       },
#       {
#         "from": "o2",
#         "to": "i4-2"
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
#     "ranks": {
#       "symbol": "p_i",
#       "name": "绘图位置",
#       "meaning": "绘图位置",
#       "code": "F"
#     },
#     "scores": {
#       "symbol": "Y_i",
#       "name": "Weibull 分数",
#       "meaning": "Weibull 分数",
#       "code": "y",
#       "axisLabel": "Weibull 分数 Yᵢ"
#     },
#     "plot_x": {
#       "symbol": "x_i",
#       "name": "平移对数寿命",
#       "meaning": "平移对数寿命",
#       "code": "x_vals",
#       "axisLabel": "平移对数寿命 xᵢ"
#     },
#     "original_x": {
#       "symbol": "\\ln t_i",
#       "name": "原样本对数寿命",
#       "meaning": "原样本对数寿命",
#       "axisLabel": "原样本对数寿命 ln(tᵢ)",
#       "code": "original_x"
#     },
#     "criterion": {
#       "symbol": "\\rho(\\gamma)",
#       "name": "位置判据",
#       "meaning": "位置判据",
#       "code": "criterion",
#       "axisLabel": "相关系数 ρ(γ)"
#     }
#   },
#   "chartBindings": {
#     "park-probability-regression": {
#       "x": "plot_x",
#       "y": "scores"
#     },
#     "original-probability-plot": {
#       "x": "original_x",
#       "y": "scores"
#     },
#     "correlation-location": {
#       "x": "gamma_axis",
#       "y": "criterion"
#     }
#   }
# }
# @end-method-flow
