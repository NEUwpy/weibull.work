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
from .calculation_trace import plot_point, plot_series, plot_chart, calculation_step


def sample_weibull_moment(sorted_x, k, trace_terms=None):
    """论文式(3)：样本 Weibull 矩 m̄_k = Σ (1 - r/n)^k (x_(r+1) - x_(r))，x_(0)=0。"""
    n = len(sorted_x)
    x_prev = np.concatenate(([0.0], sorted_x[:-1]))
    weights = (1.0 - np.arange(n) / n) ** k
    terms = weights * (sorted_x - x_prev)
    if trace_terms is not None:
        trace_terms.extend(float(v) for v in terms)
    return float(np.sum(terms))


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
        self.calculation_trace = None
        x = self.data
        n = self.n

        if n < 3:
            self.last_solution_info = {"status": "insufficient_sample", "n": int(n)}
            return [0, 0, 0, 0, "insufficient_sample"]

        terms = {k: [] for k in (1, 2, 4)}
        m1 = sample_weibull_moment(x, 1, terms[1] if trace else None)
        m2 = sample_weibull_moment(x, 2, terms[2] if trace else None)
        m4 = sample_weibull_moment(x, 4, terms[4] if trace else None)

        if trace:
            self.log_step({"phase": "moments", "m1": m1, "m2": m2, "m4": m4})

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

        shape, location, scale = solved
        raw_estimate = dict(beta=float(shape), eta=float(scale), gamma=float(location))
        location_adjustment = None

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

        two_param_shape = None
        two_param_scale = None
        if m1 > 0 and m2 > 0 and m1 > m2:
            two_param_shape = math.log(2.0) / (math.log(m1) - math.log(m2))
            two_param_scale = m1 / gamma_fn(1.0 + 1.0 / two_param_shape)

        r2 = self._calculate_r2(shape, scale, location)

        self.last_solution_info = {
            "status": "ok",
            "m1": m1,
            "m2": m2,
            "m4": m4,
            "location_adjustment": location_adjustment,
            "two_param_shape": two_param_shape,
            "two_param_scale": two_param_scale,
            "raw_estimate": raw_estimate,
        }

        if trace:
            self.log_step({
                "phase": "final",
                "beta": float(shape),
                "eta": float(scale),
                "gamma": float(location),
                "location_adjustment": location_adjustment,
            })
            description = '先检验 m̄₁−m̄₂ > m̄₂−m̄₄ > 0，再由式(2a–c)显式解参数并执行记录的位置处理。'
            self.calculation_trace = dict(
                schema_version=1, method='mm', criterion=dict(description=description),
                selection=dict(description=description, status='ok', beta=float(shape),
                               eta=float(scale), gamma=float(location),
                               raw_estimate=raw_estimate, location_adjustment=location_adjustment),
                charts=[plot_chart('weibull-moments', '生存函数面积形成样本矩', '失效时间 t', '经验生存函数的幂 Ŝf(t)ᵏ',
                                   [dict(**plot_series(f'survival-{k}', f'k={k}，m̄={moment:.6g}',
                                        [plot_point(0, 1)] + [plot_point(value, ((n-i-1)/n)**k)
                                                              for i, value in enumerate(x)], role='diagnostic'),
                                         interpolation='stepAfter') for k, moment in ((1,m1),(2,m2),(4,m4))],
                                    formula=r'\bar m_k=\int_0^\infty [1-S_n(t)]^k\,dt=\sum_{r=0}^{n-1}(1-r/n)^k(t_{(r+1)}-t_{(r)})',
                                   description='三条阶梯曲线下的面积分别是 m̄₁、m̄₂、m̄₄，用来显式求解参数。'),
                        plot_chart('moment-admissibility', '样本矩能否给出正的形状和尺度',
                                   'd₂₄ = m̄₂−m̄₄', 'd₁₂ = m̄₁−m̄₂',
                                   [plot_series('boundary', 'd₁₂=d₂₄ 边界',
                                                [plot_point(0,0),plot_point(m1-m2,m1-m2)], role='diagnostic')],
                                   selected=[plot_point(m2-m4,m1-m2,label='本次矩组合')],
                                   formula=r'd_{12}>d_{24}>0',
                                   description='本次矩组合应在对角线上方且横坐标大于零，随后代入显式解。')],
                recovery=[calculation_step('样本矩与形状显式解', r'\hat\beta=\frac{\ln2}{\ln(\bar m_1-\bar m_2)-\ln(\bar m_2-\bar m_4)}',
                                           [('m̄₁',m1),('m̄₂',m2),('m̄₄',m4),('β̂',shape)]),
                          calculation_step('位置显式解与当前处理', r'\gamma^*=\frac{\bar m_1\bar m_4-\bar m_2^2}{\bar m_1+\bar m_4-2\bar m_2}',
                                           [('γ*（原始）',raw_estimate['gamma']),('γ̂（返回）',location)]),
                          calculation_step('尺度恢复', r'\hat\eta=\frac{\bar m_1-\hat\gamma}{\Gamma(1+1/\hat\beta)}',
                                           [('η*（原始）',raw_estimate['eta']),('η̂（返回）',scale)])],
                details=dict(**self.last_solution_info,
                             moment_terms=terms,
                              moment_intervals=[dict(
                                  left=float(x[i-1]) if i else 0.0, right=float(value),
                                  survival=float(1.0-i/n),
                                  contributions={str(k): terms[k][i] for k in (1, 2, 4)})
                                  for i, value in enumerate(x)],
                              formula_values=dict(d12=m1-m2, d24=m2-m4,
                                                  shape_denominator=math.log(m1-m2)-math.log(m2-m4),
                                                  location_numerator=m1*m4-m2*m2,
                                                  location_denominator=m1+m4-2*m2,
                                                  gamma_function=float(gamma_fn(1.0+1.0/shape)),
                                                  minimum=float(x[0])),
                              location_calculation=dict(
                                  alternative=float(alt) if location_adjustment == 'alternative_a_star_star' else None,
                                  sample_size=n, sample_size_root=float(n ** (1.0/shape)),
                                  final_scale_numerator=float(m1-location)),
                              reference=dict(paper='Cran (1988)', section='式(1)–(3)，位置参数节'),
                             scale_recomputed=location_adjustment is not None,
                             implementation_note='位置处理后的尺度重算是当前实现的工程补充规则，未经修正参数保留在 raw_estimate。'))

        return [float(shape), float(scale), float(location), float(r2), True]


# @method-flow
# {
#   "schemaVersion": 2,
#   "methodId": "mm",
#   "methodName": "矩估计 (MM)",
#   "description": "Cran Weibull矩 → 显式三参数解 → 位置可采纳性修正。",
#   "steps": [
#     {
#       "name": "数据预处理",
#       "description": "获取排序后的失效时间数据和样本数量",
#       "formula": {
#         "symbols": [
#           {
#             "symbol": "x",
#             "meaning": "排序后的失效时间数组"
#           },
#           {
#             "symbol": "n",
#             "meaning": "样本数量"
#           }
#         ],
#         "explanation": "获取排序后的失效时间数据和样本数量",
#         "equations": [
#           "x_{(1)} \\leq x_{(2)} \\leq \\cdots \\leq x_{(n)}"
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
#           "file": "python/methods/mm.py",
#           "symbol": "MM.run",
#           "label": "本步实现",
#           "from": "self.calculation_trace = None",
#           "until": "terms = {k: []"
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
#       "name": "把阶梯面积相加，得到三个矩",
#       "description": "由经验生存函数的一次、二次、四次幂曲线下面积，得到三个样本Weibull矩。",
#       "formula": {
#         "symbols": [
#           {
#             "symbol": "\\bar{m}_k",
#             "meaning": "k 阶样本 Weibull 矩"
#           }
#         ],
#         "explanation": "由经验生存函数的一次、二次、四次幂曲线下面积，得到三个样本Weibull矩。",
#         "equations": [
#           "\\bar{m}_k = \\sum_{r=0}^{n-1}\\left(1-\\frac{r}{n}\\right)^k (x_{(r+1)} - x_{(r)}), \\quad x_{(0)}=0"
#         ]
#       },
#       "inputs": [
#         "ordered",
#         "n"
#       ],
#       "outputs": [
#         "m1",
#         "m2",
#         "m4"
#       ],
#       "basis": "Cran (1988) Weibull矩构造；m₂、m₄不是样本普通二阶和四阶幂矩。",
#       "notes": "m₁等于均值；m₂、m₄由阶梯生存函数加权间距得到。",
#       "sources": [
#         {
#           "file": "python/methods/mm.py",
#           "symbol": "MM.run",
#           "label": "本步实现",
#           "from": "terms = {k: []",
#           "until": "solved = solve_from_weibull_moments"
#         },
#         {
#           "file": "python/methods/mm.py",
#           "symbol": "sample_weibull_moment"
#         }
#       ],
#       "id": 2,
#       "primarySource": 1,
#       "flow": {
#         "label": "累加阶梯面积求矩"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "ordered",
#             "n"
#           ],
#           "name": "有序样本",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "m1",
#             "m2",
#             "m4"
#           ],
#           "name": "三个Weibull矩",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "name": "检查矩差，显式代入三参数",
#       "description": "矩差满足可采纳条件后，把三个样本矩代入Cran式(2a–c)，一次得到形状、位置、尺度。",
#       "formula": {
#         "explanation": "矩差满足可采纳条件后，把三个样本矩代入Cran式(2a–c)，一次得到形状、位置、尺度。",
#         "symbols": [
#           {
#             "symbol": "\\beta^*,\\gamma^*,\\eta^*",
#             "meaning": "未修正的三参数解"
#           }
#         ],
#         "equations": [
#           "\\begin{gathered}m_1-m_2>m_2-m_4>0\\\\[6pt]\\begin{gathered}\\beta^*=\\frac{\\ln2}{\\ln(m_1-m_2)-\\ln(m_2-m_4)}\\\\[5pt] \\gamma^*=\\frac{m_1m_4-m_2^2}{m_1+m_4-2m_2}\\\\[5pt] \\eta^*=\\frac{m_1-\\gamma^*}{\\Gamma(1+1/\\beta^*)}\\end{gathered}\\end{gathered}"
#         ]
#       },
#       "inputs": [
#         "m1",
#         "m2",
#         "m4"
#       ],
#       "outputs": [
#         "raw_beta",
#         "raw_gamma",
#         "raw_eta"
#       ],
#       "basis": "Cran显式解：原文c、a、b分别对应全站β、γ、η。",
#       "notes": "",
#       "sources": [
#         {
#           "file": "python/methods/mm.py",
#           "symbol": "solve_from_weibull_moments",
#           "from": "d12 = m1 - m2",
#           "through": "return None"
#         },
#         {
#           "file": "python/methods/mm.py",
#           "symbol": "solve_from_weibull_moments",
#           "from": "shape = math.log(2.0)",
#           "through": "return shape, location, scale"
#         },
#         {
#           "file": "python/methods/mm.py",
#           "symbol": "MM.run",
#           "label": "本步实现",
#           "from": "solved = solve_from_weibull_moments",
#           "until": "x_min = float(x[0])"
#         }
#       ],
#       "id": 3,
#       "primarySource": 1,
#       "flow": {
#         "label": "检查矩差并显式求参",
#         "symbol": "d_{12}>d_{24}>0"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "m1",
#             "m2",
#             "m4"
#           ],
#           "name": "Weibull矩",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "raw_beta",
#             "raw_gamma",
#             "raw_eta"
#           ],
#           "name": "显式参数解",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "name": "检查位置并作必要处理",
#       "description": "检查原始位置是否非负且低于最小观测；超界时按当前实现的规则处理并恢复尺度。",
#       "formula": {
#         "explanation": "检查原始位置是否非负且低于最小观测；超界时按当前实现的规则处理并恢复尺度。",
#         "symbols": [
#           {
#             "symbol": "\\hat\\gamma",
#             "meaning": "修正后位置"
#           },
#           {
#             "symbol": "\\hat\\eta",
#             "meaning": "重算的尺度"
#           }
#         ],
#         "equations": [
#           "\\begin{gathered}\\gamma^*<0\\Rightarrow\\hat\\gamma=0;\\\\[5pt]\\gamma^*\\ge t_{(1)}\\Rightarrow\\hat\\gamma=\\max\\left(0,t_{(1)}-\\frac{\\eta^*\\Gamma(1+1/\\beta^*)}{n^{1/\\beta^*}}\\right)\\\\[5pt]\\hat\\eta=\\frac{m_1-\\hat\\gamma}{\\Gamma(1+1/\\beta^*)}\\end{gathered}"
#         ],
#         "variants": {
#           "alternative_a_star_star": [
#             "\\begin{gathered}\\gamma^*<0\\Rightarrow\\hat\\gamma=0;\\\\[5pt]\\gamma^*\\ge t_{(1)}\\Rightarrow\\hat\\gamma=\\max\\left(0,t_{(1)}-\\frac{\\eta^*\\Gamma(1+1/\\beta^*)}{n^{1/\\beta^*}}\\right)\\\\[5pt]\\hat\\eta=\\frac{m_1-\\hat\\gamma}{\\Gamma(1+1/\\beta^*)}\\end{gathered}"
#           ],
#           "clamped_to_zero": [
#             "\\gamma^*<0\\Rightarrow\\hat\\gamma=0,\\quad\\hat\\eta=\\frac{m_1-\\hat\\gamma}{\\Gamma(1+1/\\beta^*)}"
#           ],
#           "unchanged": [
#             "0\\le\\gamma^*<t_{(1)}\\Rightarrow\\hat\\gamma=\\gamma^*,\\quad\\hat\\eta=\\eta^*"
#           ]
#         }
#       },
#       "inputs": [
#         "raw_beta",
#         "raw_gamma",
#         "raw_eta",
#         "minimum"
#       ],
#       "outputs": [
#         "beta_hat",
#         "eta_hat",
#         "gamma_hat"
#       ],
#       "basis": "Cran（1988）式(3)之后：负位置可取零，越过最小观测时可采用替代位置。",
#       "notes": "位置处理后重算尺度、对替代位置再次限制非负，是当前实现的补充处理；图中同时保留原始解与返回值。",
#       "sources": [
#         {
#           "file": "python/methods/mm.py",
#           "symbol": "MM.run",
#           "label": "本步实现",
#           "from": "x_min = float(x[0])",
#           "until": "two_param_shape = None"
#         }
#       ],
#       "id": 4,
#       "primarySource": 0,
#       "flow": {
#         "label": "检查位置并修正尺度",
#         "symbol": "0\\le\\gamma^*<x_{(1)}"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "raw_beta",
#             "raw_gamma",
#             "raw_eta"
#           ],
#           "name": "显式参数解",
#           "wrap": 2
#         },
#         "input-1": {
#           "refs": [
#             "minimum"
#           ],
#           "name": "最小观测",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "beta_hat",
#             "eta_hat",
#             "gamma_hat"
#           ],
#           "name": "处理后参数",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "name": "计算两参数对照，辅助判断阈值",
#       "description": "论文 LOCATION 节：同时计算 a=0 的两参数矩估计用于阈值判断",
#       "formula": {
#         "symbols": [
#           {
#             "symbol": "c^{**}",
#             "meaning": "2P 形状估计"
#           },
#           {
#             "symbol": "b^{**}",
#             "meaning": "2P 尺度估计"
#           }
#         ],
#         "explanation": "论文 LOCATION 节：同时计算 a=0 的两参数矩估计用于阈值判断",
#         "equations": [
#           "c^{**} = \\frac{\\ln 2}{\\ln \\bar{m}_1 - \\ln \\bar{m}_2}, \\quad b^{**} = \\bar{m}_1 / \\Gamma(1+1/c^{**})"
#         ]
#       },
#       "inputs": [
#         "m1",
#         "m2"
#       ],
#       "outputs": [
#         "beta_2p",
#         "eta_2p"
#       ],
#       "basis": "诊断对照：计算零位置的两参数矩估计，记录在last_solution_info。",
#       "notes": "两参数结果不替换本次三参数返回值，也不参与当前代码的最终选择。",
#       "sources": [
#         {
#           "file": "python/methods/mm.py",
#           "symbol": "MM.run",
#           "label": "本步实现",
#           "from": "two_param_shape = None",
#           "until": "r2 = self._calculate_r2"
#         }
#       ],
#       "id": 5,
#       "primarySource": 0,
#       "flow": {
#         "label": "计算两参数对照",
#         "symbol": "\\gamma=0"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "m1",
#             "m2"
#           ],
#           "name": "Weibull矩",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "beta_2p",
#             "eta_2p"
#           ],
#           "name": "两参数对照",
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
#           "file": "python/methods/mm.py",
#           "symbol": "MM.run",
#           "from": "r2 = self._calculate_r2"
#         }
#       ],
#       "id": 6,
#       "primarySource": 0,
#       "flow": {
#         "label": "汇总参数与拟合优度",
#         "symbol": "(\\hat\\beta,\\hat\\eta,\\hat\\gamma,R^2)"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "beta_hat",
#             "eta_hat",
#             "gamma_hat"
#           ],
#           "name": "三参数估计",
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
#     "description": "Cran Weibull矩 → 显式三参数解 → 位置可采纳性修正。",
#     "targets": {
#       "samples": 1,
#       "moments": 2,
#       "estimate": 3,
#       "adjustment": 4,
#       "comparison": 5,
#       "result": 6
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
#             "target": "moments",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "step",
#             "anchor": "s2",
#             "step": 2,
#             "target": "moments"
#           },
#           {
#             "kind": "port",
#             "anchor": "o2",
#             "target": "moments",
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
#             "target": "estimate",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "step",
#             "anchor": "s3",
#             "step": 3,
#             "target": "estimate"
#           },
#           {
#             "kind": "port",
#             "anchor": "o3",
#             "target": "estimate",
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
#             "target": "adjustment",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "port",
#             "anchor": "i4-2",
#             "target": "adjustment",
#             "direction": "input",
#             "group": "input-1"
#           },
#           {
#             "kind": "step",
#             "anchor": "s4",
#             "step": 4,
#             "target": "adjustment"
#           },
#           {
#             "kind": "port",
#             "anchor": "o4",
#             "target": "adjustment",
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
#             "target": "comparison",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "step",
#             "anchor": "s5",
#             "step": 5,
#             "target": "comparison"
#           },
#           {
#             "kind": "port",
#             "anchor": "o5",
#             "target": "comparison",
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
#             "anchor": "i6-1",
#             "target": "result",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "step",
#             "anchor": "s6",
#             "step": 6,
#             "target": "result"
#           },
#           {
#             "kind": "port",
#             "anchor": "o6",
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
#         "from": "o3",
#         "to": "i4-1"
#       },
#       {
#         "from": "o1",
#         "to": "i4-2"
#       },
#       {
#         "from": "o2",
#         "to": "i5-1"
#       },
#       {
#         "from": "o4",
#         "to": "i6-1"
#       }
#     ]
#   },
#   "variables": {
#     "samples": {
#       "symbol": "x_i",
#       "name": "样本",
#       "meaning": "样本",
#       "code": "data"
#     },
#     "ordered": {
#       "symbol": "x_{(i)}",
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
#     "m1": {
#       "symbol": "\\bar m_1",
#       "name": "一阶Weibull矩",
#       "meaning": "一阶Weibull矩",
#       "code": "m1"
#     },
#     "m2": {
#       "symbol": "\\bar m_2",
#       "name": "二阶Weibull矩",
#       "meaning": "二阶Weibull矩",
#       "code": "m2"
#     },
#     "m4": {
#       "symbol": "\\bar m_4",
#       "name": "四阶Weibull矩",
#       "meaning": "四阶Weibull矩",
#       "code": "m4"
#     },
#     "raw_beta": {
#       "symbol": "\\beta^*",
#       "name": "显式形状",
#       "meaning": "显式形状",
#       "code": "raw_beta"
#     },
#     "raw_gamma": {
#       "symbol": "\\gamma^*",
#       "name": "显式位置",
#       "meaning": "显式位置",
#       "code": "raw_gamma"
#     },
#     "raw_eta": {
#       "symbol": "\\eta^*",
#       "name": "显式尺度",
#       "meaning": "显式尺度",
#       "code": "raw_eta"
#     },
#     "minimum": {
#       "symbol": "x_{(1)}",
#       "name": "最小观测",
#       "meaning": "最小观测",
#       "code": "minimum"
#     },
#     "beta_2p": {
#       "symbol": "\\beta_{2P}",
#       "name": "两参数形状",
#       "meaning": "两参数形状",
#       "code": "two_param_shape"
#     },
#     "eta_2p": {
#       "symbol": "\\eta_{2P}",
#       "name": "两参数尺度",
#       "meaning": "两参数尺度",
#       "code": "two_param_scale"
#     },
#     "lifetime_axis": {
#       "name": "失效时间",
#       "meaning": "寿命坐标",
#       "symbol": "t",
#       "code": "lifetime_axis",
#       "axisLabel": "失效时间 t"
#     },
#     "survival": {
#       "name": "经验生存函数",
#       "meaning": "用于Weibull矩的经验生存函数",
#       "symbol": "\\hat S_f(t)",
#       "code": "survival",
#       "axisLabel": "经验生存函数 Ŝf(t)"
#     }
#   },
#   "chartBindings": {
#     "weibull-moments": {
#       "x": "lifetime_axis",
#       "y": "survival"
#     }
#   }
# }
# @end-method-flow
