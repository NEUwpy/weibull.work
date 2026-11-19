"""Kundu–Raqab (2009) MMLE, single-sample minimum-delete-one construction.

Matches the archived Research09 KROriginal fixed-point arithmetic. The paper
uses alpha for shape and theta=eta**beta for its scale parametrization:
SPL 79(17), 1839–1846; p.1840 (4), p.1841 (6), (9)–(11).
The previous Cohen–Whitten implementation is preserved in methods.mmle_ch.
"""
import numpy as np
from scipy.special import logsumexp

from base import WeibullBase
from .calculation_trace import plot_point, plot_series, plot_chart, calculation_step, modified_likelihood_plot, power_scale_calculation

INITIAL_SHAPE = 1.0
SHAPE_ABSOLUTE_STEP_TOLERANCE = 1e-8
MAX_ITERATIONS = 10000


class MMLE(WeibullBase):
    """Fix gamma at the original minimum, delete it, then fit shifted data.

    No Firth adjustment, shape/location caps, restart or fallback solver.
    The retained observations, rather than the deleted minimum, define support.
    """

    def run(self, trace=False, *, initial_shape=INITIAL_SHAPE,
            shape_absolute_step_tolerance=SHAPE_ABSOLUTE_STEP_TOLERANCE,
            max_iterations=MAX_ITERATIONS):
        """Return [beta, eta, gamma, 0.0, converged], as in KROriginal.

        R² is the archived zero placeholder; the original minimum has zero
        shifted distance, so the full-sample log-linear R² is not evaluated.
        """
        self.calculation_trace = None
        if not np.isfinite(initial_shape) or initial_shape <= 0:
            raise ValueError('initial_shape must be finite and positive')
        if (not np.isfinite(shape_absolute_step_tolerance)
                or shape_absolute_step_tolerance <= 0):
            raise ValueError('shape_absolute_step_tolerance must be finite and positive')
        if (isinstance(max_iterations, bool)
                or not isinstance(max_iterations, (int, np.integer))
                or max_iterations < 1):
            raise ValueError('max_iterations must be a positive integer')
        if self.n < 2:
            self.last_solution_info = {'status': 'insufficient_sample', 'n': self.n}
            return [None, None, None, 0., False]

        gamma = float(self.data[0])
        y = self.data[1:] - gamma
        beta = float(initial_shape)
        converged = False
        history = []
        difference = float('inf')
        # Invalid steps fail under the original rule; they do not trigger rescue.
        with np.errstate(divide='ignore', invalid='ignore', over='ignore'):
            logs = np.log(y)
            q = len(y)
            for iteration in range(1, max_iterations + 1):
                weights = np.exp(beta * (logs - logs.max()))
                weights /= weights.sum()
                denominator = float(q * (weights @ logs))
                next_beta = float((q + beta * logs.sum()) / denominator)
                if not np.isfinite(next_beta) or next_beta <= 0:
                    break
                difference = abs(next_beta - beta)
                if iteration <= 3:
                    history.append(dict(iteration=iteration, shape_before=beta,
                                        shape_after=next_beta))
                if trace:
                    self.log_step(dict(phase='shape_iteration', iteration=iteration,
                                       shape_before=beta, shape_after=next_beta,
                                       log_sum=float(logs.sum()), weighted_log_mean=float(weights @ logs),
                                       numerator=float(q + beta * logs.sum()), denominator=denominator,
                                       shape_step=float(difference)))
                beta = next_beta
                if difference <= shape_absolute_step_tolerance:
                    converged = True
                    break
            self.last_solution_info = dict(
                status='ok' if converged else 'fixed_point_not_converged',
                iterations=iteration, initial_shape=float(initial_shape),
                final_shape_step=float(difference), deleted_observations=1,
                gamma_is_original_sample_minimum=True,
                effective_sample_min=float(self.data[1]), first_iterations=history,
                no_firth=True, no_domain_caps=True, no_fallback=True,
                shape_absolute_step_tolerance=float(shape_absolute_step_tolerance),
                max_iterations=int(max_iterations))
            if not converged:
                return [None, None, None, 0., False]
            eta = float(np.exp((logsumexp(beta * logs) - np.log(q)) / beta))
        if trace:
            self.log_step(dict(phase='final', beta=beta, eta=eta, gamma=gamma,
                               **self.last_solution_info))
            iterations = [p for p in self.trace_data if p['phase'] == 'shape_iteration']
            profile_chart, profile_frames = modified_likelihood_plot(logs, iterations, beta, eta, initial_shape)
            description = '令 γ̂ 为原样本最小值并删除该观测；保留样本按不动点规则迭代，步长达到容差后接受。'
            self.calculation_trace = dict(
                schema_version=1, method='mmle', criterion=dict(description=description),
                selection=dict(description=description, status='ok', beta=float(beta),
                               eta=float(eta), gamma=float(gamma), iterations=iteration),
                charts=[profile_chart,
                        plot_chart('shape-fixed-point', '保留样本的形状不动点迭代', '实际迭代次数', '形状参数 β',
                                   [plot_series('shape', '实际迭代结果',
                                                [plot_point(p['iteration'], p['shape_after']) for p in iterations])],
                                   formula=r'\beta_{k+1}=\frac{q+\beta_k\sum\ln y_i}{q\sum w_i(\beta_k)\ln y_i},\quad w_i=\frac{y_i^{\beta_k}}{\sum y_j^{\beta_k}}',
                                   description='原样本最小值确定 γ̂；删去该一个观测后，yᵢ=tᵢ−γ̂，q=n−1。',
                                   selected=[plot_point(iteration, beta, label='最终形状参数')]),
                        plot_chart('shape-step', '停止判据', '实际迭代次数', '相邻形状参数绝对差 |Δβ|',
                                   [plot_series('step', '实际绝对步长',
                                                [plot_point(p['iteration'], p['shape_step']) for p in iterations])],
                                   references=[dict(axis='y', value=float(shape_absolute_step_tolerance), label='停止容差')],
                                   formula=r'|\beta_{k+1}-\beta_k|\leq\varepsilon',
                                   selected=[plot_point(iteration, difference, label='达到停止条件')])],
                recovery=[calculation_step('样本最小值确定位置', r'\hat\gamma=t_{(1)},\quad y_i=t_{(i)}-\hat\gamma\;(i\geq2)',
                                           [('γ̂',gamma),('保留样本数 q',q)]),
                          calculation_step('不动点迭代确定形状', r'|\beta_{k+1}-\beta_k|\leq\varepsilon',
                                           [('β̂',beta),('|Δβ|',difference),('ε',shape_absolute_step_tolerance)]),
                          calculation_step('保留样本恢复尺度', r'\hat\eta=\left(\frac1q\sum y_i^{\hat\beta}\right)^{1/\hat\beta}',
                                           [('η̂',eta)])],
                details=dict(**self.last_solution_info, deleted_value=gamma,
                             profile_frames=profile_frames,
                             shape_iterations=iterations,
                             scale_calculation=power_scale_calculation(self.data[1:], beta, gamma, eta, first_index=2),
                             retained_observations=(y+gamma).tolist(), shifted_observations=y.tolist(),
                             r_squared_note='原流程0占位，不解释为拟合优度为零。'))
        return [beta, eta, gamma, 0., True]


# @method-flow
# {
#   "schemaVersion": 2,
#   "methodId": "mmle",
#   "methodName": "修正极大似然法 MMLE",
#   "description": "Kundu–Raqab单样本构造：删除一个最小值 → 固定点形状迭代 → 尺度恢复。",
#   "steps": [
#     {
#       "name": "准备有序样本",
#       "description": "整理样本，准备形状迭代的起点与停止条件。",
#       "basis": "Kundu–Raqab (2009)单样本版本与既有数值控制。",
#       "notes": "论文整理门槛尚未完成，此页补充程序说明，不开放计算器。不是旧Cohen–Whitten版本，也没有Firth修正。",
#       "formula": {
#         "explanation": "整理样本，准备形状迭代的起点与停止条件。",
#         "symbols": [
#           {
#             "symbol": "t_{(i)}",
#             "meaning": "排序样本"
#           },
#           {
#             "symbol": "ε",
#             "meaning": "绝对步差容差"
#           },
#           {
#             "symbol": "K_{max}",
#             "meaning": "迭代上限"
#           }
#         ],
#         "equations": [
#           "\\beta_0=1,\\quad\\varepsilon=10^{-8},\\quad K_{max}=10000,\\quad n\\ge2"
#         ]
#       },
#       "inputs": [
#         "samples"
#       ],
#       "outputs": [
#         "ordered"
#       ],
#       "sources": [
#         {
#           "file": "python/base.py",
#           "symbol": "WeibullBase.__init__"
#         },
#         {
#           "file": "python/methods/mmle.py",
#           "symbol": "MMLE.run",
#           "label": "控制量检查",
#           "until": "gamma = float(self.data[0])"
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
#             "ordered"
#           ],
#           "name": "有序样本",
#           "wrap": 2
#         }
#       },
#       "extraInputs": [
#         "iteration_settings"
#       ]
#     },
#     {
#       "name": "最小值确定位置并删除",
#       "description": "以原样本最小值确定位置γ，只删除该一个观测，保留其余到该位置的距离。",
#       "basis": "原构造：保留样本定义支撑，不用已删除的最小值检查。",
#       "notes": "重复最小值使剩余距离出现0；随后按原固定点规则失败，不扰动、不重启。",
#       "formula": {
#         "explanation": "以原样本最小值确定位置γ，只删除该一个观测，保留其余到该位置的距离。",
#         "symbols": [
#           {
#             "symbol": "\\hatγ",
#             "meaning": "固定位置"
#           },
#           {
#             "symbol": "y_i",
#             "meaning": "保留样本平移距离"
#           },
#           {
#             "symbol": "q",
#             "meaning": "保留样本量 n−1"
#           }
#         ],
#         "equations": [
#           "\\hat\\gamma=t_{(1)},\\quad y_i=t_{(i+1)}-t_{(1)},\\quad q=n-1"
#         ]
#       },
#       "inputs": [
#         "ordered"
#       ],
#       "outputs": [
#         "gamma_hat",
#         "shifted"
#       ],
#       "sources": [
#         {
#           "file": "python/methods/mmle.py",
#           "symbol": "MMLE.run",
#           "label": "删除最小观测",
#           "from": "gamma = float(self.data[0])",
#           "until": "# Invalid steps fail"
#         }
#       ],
#       "id": 2,
#       "primarySource": 0,
#       "flow": {
#         "label": "取最小值定位并删点",
#         "symbol": "\\hat\\gamma=t_{(1)}"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "ordered"
#           ],
#           "name": "有序样本",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "gamma_hat",
#             "shifted"
#           ],
#           "name": "位置与保留距离",
#           "wrap": 1
#         }
#       },
#       "extraOutputs": [
#         "q"
#       ]
#     },
#     {
#       "name": "在修改似然中确定形状",
#       "description": "将尺度消元，在保留样本的修改剖面似然上，用固定点更新寻找形状β。",
#       "basis": "原固定点构造；指数先减最大值用于数值稳定。",
#       "notes": "下一步非有限或非正立即停止；达到上限仍不收敛则失败。没有形状/位置截断、重启或后备求解器。",
#       "formula": {
#         "explanation": "将尺度消元，在保留样本的修改剖面似然上，用固定点更新寻找形状β。",
#         "symbols": [
#           {
#             "symbol": "β_{k+1}",
#             "meaning": "下一步形状"
#           },
#           {
#             "symbol": "\\mathrm{converged}",
#             "meaning": "步差收敛标志"
#           },
#           {
#             "symbol": "w_i^{(k)}",
#             "meaning": "归一化幂权重"
#           },
#           {
#             "symbol": "q",
#             "meaning": "保留样本量"
#           },
#           {
#             "symbol": "ε",
#             "meaning": "绝对步差容差"
#           },
#           {
#             "symbol": "A(\\beta)",
#             "meaning": "平移距离的幂次平均值"
#           },
#           {
#             "symbol": "\\ell_p(\\beta)",
#             "meaning": "消去尺度后的修改剖面对数似然"
#           }
#         ],
#         "equations": [
#           "\\begin{aligned}A(\\beta)&=\\frac1q\\sum_i y_i^\\beta\\\\\\ell_p(\\beta)&=q\\ln\\beta-q\\ln A(\\beta)\\\\&\\quad+(\\beta-1)\\sum_i\\ln y_i-q\\end{aligned}",
#           "\\begin{gathered}w_i^{(k)}=\\frac{e^{\\beta_k\\ln y_i}}{\\sum_j e^{\\beta_k\\ln y_j}}\\\\[5pt]\\beta_{k+1}=\\frac{q+\\beta_k\\sum_i\\ln y_i}{q\\sum_iw_i^{(k)}\\ln y_i}\\\\[5pt]|\\beta_{k+1}-\\beta_k|\\le\\varepsilon\\end{gathered}"
#         ]
#       },
#       "inputs": [
#         "shifted",
#         "iteration_settings"
#       ],
#       "outputs": [
#         "beta_hat",
#         "status"
#       ],
#       "sources": [
#         {
#           "file": "python/methods/mmle.py",
#           "symbol": "MMLE.run",
#           "label": "固定点循环",
#           "from": "with np.errstate",
#           "until": "self.last_solution_info = dict("
#         }
#       ],
#       "id": 3,
#       "primarySource": 0,
#       "flow": {
#         "label": "按固定点规则迭代形状",
#         "symbol": "|\\Delta\\beta|\\le\\varepsilon"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "shifted"
#           ],
#           "name": "保留距离",
#           "wrap": 2
#         },
#         "input-1": {
#           "refs": [
#             "iteration_settings"
#           ],
#           "name": "迭代控制",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "beta_hat"
#           ],
#           "name": "收敛形状",
#           "wrap": 2
#         }
#       },
#       "extraInputs": [
#         "q"
#       ]
#     },
#     {
#       "name": "由最终形状恢复尺度",
#       "description": "检查形状更新已收敛，再用保留距离的幂均值确定尺度η。",
#       "basis": "参数映射：原文α对应全站β，θ对应η^β。",
#       "notes": "未收敛返回None参数及False，不把最后一个迭代值作为成功估计。",
#       "formula": {
#         "explanation": "检查形状更新已收敛，再用保留距离的幂均值确定尺度η。",
#         "symbols": [
#           {
#             "symbol": "\\hatη",
#             "meaning": "尺度"
#           },
#           {
#             "symbol": "\\mathrm{status}",
#             "meaning": "收敛诊断"
#           },
#           {
#             "symbol": "θ",
#             "meaning": "原文尺度参数化 η^β"
#           }
#         ],
#         "equations": [
#           "\\hat\\eta=\\left(\\frac1q\\sum_i y_i^{\\hat\\beta}\\right)^{1/\\hat\\beta},\\quad\\theta=\\eta^\\beta"
#         ]
#       },
#       "inputs": [
#         "beta_hat",
#         "shifted"
#       ],
#       "outputs": [
#         "eta_hat"
#       ],
#       "sources": [
#         {
#           "file": "python/methods/mmle.py",
#           "symbol": "MMLE.run",
#           "label": "收敛、失败与尺度",
#           "from": "self.last_solution_info = dict(",
#           "until": "if trace:"
#         }
#       ],
#       "id": 4,
#       "primarySource": 0,
#       "flow": {
#         "label": "由保留样本恢复尺度"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "beta_hat"
#           ],
#           "name": "形状估计",
#           "wrap": 2
#         },
#         "input-1": {
#           "refs": [
#             "shifted"
#           ],
#           "name": "保留距离",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "eta_hat"
#           ],
#           "name": "尺度估计",
#           "wrap": 2
#         }
#       },
#       "extraInputs": [
#         "q"
#       ]
#     },
#     {
#       "name": "返回估计结果",
#       "description": "返回由最小值、修改似然与尺度公式共同确定的三参数。",
#       "basis": "接口兼容：保持KROriginal返回结构。",
#       "notes": "R²=0是存档占位，未计算全样本概率图拟合优度；与其他方法R²不直接比较。",
#       "formula": {
#         "explanation": "返回本次采纳的三参数，并保留求解状态。程序接口中的0占位不解释为拟合优度。",
#         "symbols": [
#           {
#             "symbol": "(β,η,γ,0,\\mathrm{True})",
#             "meaning": "成功返回"
#           }
#         ],
#         "equations": [
#           "(\\hat\\beta,\\hat\\eta,\\hat\\gamma)"
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
#         "status"
#       ],
#       "sources": [
#         {
#           "file": "python/methods/mmle.py",
#           "symbol": "MMLE.run",
#           "after": "eta = float(np.exp",
#           "from": "        if trace:",
#           "through": "return [beta, eta, gamma, 0., True]"
#         }
#       ],
#       "id": 5,
#       "primarySource": 0,
#       "flow": {
#         "label": "返回三参数",
#         "symbol": "(\\hat\\beta,\\hat\\eta,\\hat\\gamma)"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "gamma_hat",
#             "beta_hat"
#           ],
#           "name": "位置与形状",
#           "wrap": 2
#         },
#         "input-1": {
#           "refs": [
#             "eta_hat"
#           ],
#           "name": "尺度估计",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "beta_hat",
#             "eta_hat",
#             "gamma_hat"
#           ],
#           "name": "估计结果",
#           "wrap": 2
#         }
#       }
#     }
#   ],
#   "workflow": {
#     "title": "计算流程",
#     "description": "Kundu–Raqab单样本构造：删除一个最小值 → 固定点形状迭代 → 尺度恢复。",
#     "targets": {
#       "samples": 1,
#       "location": 2,
#       "shape": 3,
#       "scale": 4,
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
#             "target": "location",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "step",
#             "anchor": "s2",
#             "step": 2,
#             "target": "location"
#           },
#           {
#             "kind": "port",
#             "anchor": "o2",
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
#             "anchor": "i3-1",
#             "target": "shape",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "port",
#             "anchor": "i3-2",
#             "target": "shape",
#             "direction": "input",
#             "external": true,
#             "group": "input-1"
#           },
#           {
#             "kind": "step",
#             "anchor": "s3",
#             "step": 3,
#             "target": "shape"
#           },
#           {
#             "kind": "port",
#             "anchor": "o3",
#             "target": "shape",
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
#             "target": "scale",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "port",
#             "anchor": "i4-2",
#             "target": "scale",
#             "direction": "input",
#             "group": "input-1"
#           },
#           {
#             "kind": "step",
#             "anchor": "s4",
#             "step": 4,
#             "target": "scale"
#           },
#           {
#             "kind": "port",
#             "anchor": "o4",
#             "target": "scale",
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
#         "from": "o3",
#         "to": "i4-1"
#       },
#       {
#         "from": "o2",
#         "to": "i4-2"
#       },
#       {
#         "from": "o2",
#         "to": "i5-1"
#       },
#       {
#         "from": "o3",
#         "to": "i5-1"
#       },
#       {
#         "from": "o4",
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
#     "status": {
#       "symbol": "\\mathrm{status}",
#       "name": "求解状态",
#       "meaning": "求解状态",
#       "code": "process_status"
#     },
#     "beta_axis": {
#       "symbol": "\\beta",
#       "name": "形状",
#       "meaning": "形状",
#       "axisLabel": "形状参数 β（原文 α）",
#       "code": "beta_axis"
#     },
#     "sample_axis": {
#       "symbol": "i",
#       "name": "样本序号",
#       "meaning": "样本序号",
#       "axisLabel": "样本序号 i",
#       "code": "sample_axis"
#     },
#     "power": {
#       "symbol": "c_i",
#       "name": "幂次贡献",
#       "meaning": "幂次贡献",
#       "code": "power"
#     },
#     "shifted": {
#       "symbol": "\\{y_i\\}_{i=1}^{q}",
#       "name": "保留距离",
#       "meaning": "保留距离",
#       "code": "y"
#     },
#     "q": {
#       "symbol": "q",
#       "name": "保留样本数",
#       "meaning": "保留样本数",
#       "code": "q"
#     },
#     "iteration_settings": {
#       "symbol": "\\begin{gathered}\\beta_0\\\\\\varepsilon,K_{\\max}\\end{gathered}",
#       "name": "迭代设置",
#       "meaning": "形状初值、绝对步差容差与迭代上限",
#       "code": "iteration_settings"
#     },
#     "iteration": {
#       "symbol": "k",
#       "name": "迭代次数",
#       "meaning": "迭代次数",
#       "axisLabel": "实际迭代次数 k",
#       "code": "iteration"
#     },
#     "iteration_beta": {
#       "symbol": "\\beta_k",
#       "name": "迭代形状",
#       "meaning": "迭代形状",
#       "axisLabel": "迭代形状 βₖ",
#       "code": "iteration_beta"
#     },
#     "iteration_step": {
#       "symbol": "|\\Delta\\beta_k|",
#       "name": "迭代步差",
#       "meaning": "迭代步差",
#       "axisLabel": "绝对步差 |Δβₖ|",
#       "code": "iteration_step"
#     },
#     "modified_likelihood": {
#       "symbol": "\\ell_p(\\beta)",
#       "name": "修改剖面似然",
#       "meaning": "修改剖面似然",
#       "axisLabel": "修改剖面对数似然 ℓₚ(β)",
#       "code": "modified_likelihood"
#     }
#   },
#   "chartBindings": {
#     "modified-profile-likelihood": {
#       "x": "beta_axis",
#       "y": "modified_likelihood"
#     },
#     "shape-fixed-point": {
#       "x": "iteration",
#       "y": "iteration_beta"
#     },
#     "shape-step": {
#       "x": "iteration",
#       "y": "iteration_step"
#     },
#     "scale-sample-contributions": {
#       "x": "sample_axis",
#       "y": "power"
#     }
#   }
# }
# @end-method-flow
