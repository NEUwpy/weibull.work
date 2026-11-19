"""Finite local MLE with explicit engineering constraints and profile search.

The statistical likelihood and beta>=1, gamma>=0 convention are unchanged.
Open-support limits are diagnostics, not artificial finite estimates.
"""
from base import WeibullBase
from .profile_solvers import solve_mle_profile
from .calculation_trace import profile_calculation


class MLE(WeibullBase):
    def run(self, trace=False):
        self.calculation_trace = None
        try:
            selected, info = solve_mle_profile(self.data, trace=trace)
        except (ValueError, FloatingPointError, RuntimeError) as error:
            self.last_solution_info = dict(status='profile_solver_failed', error=str(error))
            return [None, None, None, 0., 'profile_solver_failed']
        self.last_solution_info = {k: v for k, v in info.items() if k not in ('profile_trace', 'selected_shape_evaluations', 'profile_shape_evaluations', 'prepared_samples', 'normalization_unit')}
        if trace:
            self.calculation_trace = profile_calculation('mle', info, selected, data=self.data)
            for candidate in info.get('candidates', []):
                self.log_step(dict(phase='candidate', beta=candidate['beta'],
                                   eta=candidate['eta'], gamma=candidate['gamma'],
                                   log_likelihood=candidate['ll'], kind=candidate['kind']))
        if selected is None:
            if trace:
                self.log_step(dict(phase='failed', reason=info['status']))
            return [None, None, None, 0., info['status']]
        beta, eta, gamma = (selected[p] for p in ['beta', 'eta', 'gamma'])
        if trace:
            self.log_step(dict(phase='final', beta=beta, eta=eta, gamma=gamma,
                               log_likelihood=selected['ll'], converged=True))
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma), True]

# @method-flow
# {
#   "schemaVersion": 2,
#   "methodId": "mle",
#   "methodName": "极大似然法 MLE",
#   "description": "条件形状求根 → 有限似然候选搜索 → 边界极限单列。",
#   "steps": [
#     {
#       "id": 1,
#       "name": "准备样本与支持范围",
#       "description": "排序并按最小观测归一化，建立本次条件剖面搜索的可取范围。",
#       "formula": {
#         "equations": [
#           "u=t_{(1)}>0",
#           "z_i=t_i/u",
#           "\\beta\\ge1,\\quad\\eta>0,\\quad0\\le\\gamma<u"
#         ],
#         "explanation": "排序并按最小观测归一化，建立本次条件剖面搜索的可取范围。",
#         "symbols": [
#           {
#             "symbol": "z_i",
#             "meaning": "无量纲样本"
#           },
#           {
#             "symbol": "u",
#             "meaning": "样本最小值；归一化单位"
#           },
#           {
#             "symbol": "\\beta",
#             "meaning": "形状参数"
#           },
#           {
#             "symbol": "\\eta",
#             "meaning": "尺度参数"
#           },
#           {
#             "symbol": "\\gamma",
#             "meaning": "位置参数"
#           }
#         ]
#       },
#       "inputs": [
#         "samples"
#       ],
#       "outputs": [
#         "ordered",
#         "normalized",
#         "n",
#         "unit"
#       ],
#       "sources": [
#         {
#           "file": "python/base.py",
#           "symbol": "WeibullBase.__init__"
#         },
#         {
#           "file": "python/methods/profile_solvers.py",
#           "symbol": "solve_mle_profile",
#           "from": "x = np.sort",
#           "until": "def profile(g):"
#         }
#       ],
#       "primarySource": 0,
#       "basis": "排序并按最小观测归一化，建立本次条件剖面搜索的可取范围。",
#       "notes": "当前实现使用 β≥1、γ≥0 的接受域。Hirose（1996）提供数值基准，当前程序不是其完整 GEV 求解流程。",
#       "flow": {
#         "label": "排序并归一化样本"
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
#             "normalized",
#             "n"
#           ],
#           "name": "样本与归一化",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "id": 2,
#       "name": "试算各位置的条件似然",
#       "description": "每个试算位置先解条件形状方程，再恢复对应尺度，形成剖面对数似然。",
#       "formula": {
#         "equations": [
#           "\\ell_p(\\gamma)=\\ell(\\beta^*,\\eta^*,\\gamma)",
#           "S_\\beta(\\beta^*,\\gamma)=0",
#           "S_\\beta=\\frac1\\beta+\\overline{\\ln d}-L_\\beta",
#           "L_\\beta=\\frac{\\sum_i d_i^\\beta\\ln d_i}{\\sum_i d_i^\\beta}",
#           "\\eta^*=\\left(\\frac1n\\sum_i d_i^{\\beta^*}\\right)^{1/\\beta^*}",
#           "\\begin{aligned}&\\ell=n\\ln\\beta-n\\beta\\ln\\eta\\\\[8pt]&\\quad+(\\beta-1)\\sum_i\\ln d_i\\\\[8pt]&\\quad-\\sum_i(d_i/\\eta)^\\beta\\end{aligned}"
#         ],
#         "explanation": "每个试算位置先解条件形状方程，再恢复对应尺度，形成剖面对数似然。",
#         "symbols": [
#           {
#             "symbol": "\\gamma",
#             "meaning": "当前试算位置"
#           },
#           {
#             "symbol": "d_i",
#             "meaning": "样本与试算位置的距离 tᵢ−γ"
#           },
#           {
#             "symbol": "\\beta",
#             "meaning": "形状图横轴"
#           },
#           {
#             "symbol": "S_\\beta",
#             "meaning": "形状图纵轴，条件形状得分"
#           },
#           {
#             "symbol": "\\ell_p",
#             "meaning": "该位置的条件最大对数似然"
#           },
#           {
#             "symbol": "L_\\beta",
#             "meaning": "以距离幂次为权重的对数距离均值"
#           },
#           {
#             "symbol": "\\ell",
#             "meaning": "样本对数似然"
#           }
#         ],
#         "variants": {
#           "boundary": [
#             "\\ell_p(\\gamma)=\\ell(\\beta^*,\\eta^*,\\gamma)",
#             "\\beta^*=1,\\quad S_\\beta(1,\\gamma)\\le0",
#             "S_\\beta=\\frac1\\beta+\\overline{\\ln d}-L_\\beta",
#             "L_\\beta=\\frac{\\sum_i d_i^\\beta\\ln d_i}{\\sum_i d_i^\\beta}",
#             "\\eta^*=\\left(\\frac1n\\sum_i d_i^{\\beta^*}\\right)^{1/\\beta^*}",
#             "\\begin{aligned}&\\ell=n\\ln\\beta-n\\beta\\ln\\eta\\\\[8pt]&\\quad+(\\beta-1)\\sum_i\\ln d_i\\\\[8pt]&\\quad-\\sum_i(d_i/\\eta)^\\beta\\end{aligned}"
#           ]
#         }
#       },
#       "inputs": [
#         "normalized",
#         "n",
#         "trial_gamma"
#       ],
#       "outputs": [
#         "trial_beta",
#         "trial_eta",
#         "profile_likelihood"
#       ],
#       "sources": [
#         {
#           "file": "python/methods/profile_solvers.py",
#           "symbol": "_location_grid"
#         },
#         {
#           "file": "python/methods/profile_solvers.py",
#           "symbol": "solve_mle_profile",
#           "from": "def profile(g):",
#           "until": "zero = points[0]"
#         },
#         {
#           "file": "python/methods/conditional_profiles.py",
#           "symbol": "_distances"
#         },
#         {
#           "file": "python/methods/conditional_profiles.py",
#           "symbol": "_shape"
#         },
#         {
#           "file": "python/methods/conditional_profiles.py",
#           "symbol": "mle_profile"
#         }
#       ],
#       "primarySource": 0,
#       "basis": "每个试算位置先解条件形状方程，再恢复对应尺度，形成剖面对数似然。",
#       "notes": "图中只读取本次求解的形状求值。β=1 下界得分≤0时按约束采纳；内层数值求根沿用Brent。尺度与似然在程序中使用中心化对数及logsumexp稳定计算。",
#       "flow": {
#         "label": "给定位置求条件形状",
#         "symbol": "S_\\beta(\\beta^*,\\gamma)=0"
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "normalized",
#             "n"
#           ],
#           "name": "样本与样本量",
#           "wrap": 2
#         },
#         "input-1": {
#           "refs": [
#             "trial_gamma"
#           ],
#           "name": "试算位置",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "trial_beta",
#             "trial_eta",
#             "profile_likelihood"
#           ],
#           "name": "条件似然",
#           "wrap": 1
#         }
#       }
#     },
#     {
#       "id": 3,
#       "name": "比较候选，确定位置",
#       "description": "以位置得分由正转负的交点及剖面峰值精化有限候选，再按原对数似然选择位置。",
#       "formula": {
#         "equations": [
#           "\\hat\\gamma=\\arg\\max_{\\gamma\\in\\mathcal C}\\ell_p(\\gamma)",
#           "S_\\gamma(\\gamma_c)=\\ell_p^{\\prime}(\\gamma_c)=0",
#           "\\begin{aligned}&S_\\gamma=n\\beta\\frac{\\sum_i d_i^{\\beta-1}}{\\sum_i d_i^\\beta}\\\\[8pt]&\\quad-(\\beta-1)\\sum_i d_i^{-1}\\end{aligned}",
#           "S_\\gamma(\\gamma_L)>0>S_\\gamma(\\gamma_R)"
#         ],
#         "explanation": "以位置得分由正转负的交点及剖面峰值精化有限候选，再按原对数似然选择位置。",
#         "symbols": [
#           {
#             "symbol": "\\gamma",
#             "meaning": "两图横轴，位置参数"
#           },
#           {
#             "symbol": "\\ell_p",
#             "meaning": "主图纵轴，剖面对数似然"
#           },
#           {
#             "symbol": "S_\\gamma",
#             "meaning": "第二图纵轴，位置得分"
#           },
#           {
#             "symbol": "\\mathcal C",
#             "meaning": "按现行规则接受的有限候选集合"
#           },
#           {
#             "symbol": "\\gamma_c",
#             "meaning": "内部有限极大候选的位置"
#           },
#           {
#             "symbol": "\\gamma_L,\\gamma_R",
#             "meaning": "括住内部极大候选的左、右试算位置"
#           },
#           {
#             "symbol": "\\beta",
#             "meaning": "该试算位置的条件形状 β*(γ)"
#           },
#           {
#             "symbol": "d_i",
#             "meaning": "该试算位置的平移距离 tᵢ−γ"
#           },
#           {
#             "symbol": "n",
#             "meaning": "失效样本数"
#           }
#         ],
#         "variants": {
#           "zero": [
#             "\\hat\\gamma=0,\\quad S_\\gamma(0)\\le0",
#             "S_\\gamma=\\frac{d\\ell_p}{d\\gamma}",
#             "\\begin{aligned}&S_\\gamma=n\\beta\\frac{\\sum_i d_i^{\\beta-1}}{\\sum_i d_i^\\beta}\\\\[8pt]&\\quad-(\\beta-1)\\sum_i d_i^{-1}\\end{aligned}",
#             "\\ell_p(0)=\\max_{\\gamma\\in\\mathcal C}\\ell_p(\\gamma)"
#           ],
#           "failed": [
#             "\\mathcal C=\\varnothing",
#             "S_\\gamma=\\frac{d\\ell_p}{d\\gamma}",
#             "\\begin{aligned}&S_\\gamma=n\\beta\\frac{\\sum_i d_i^{\\beta-1}}{\\sum_i d_i^\\beta}\\\\[8pt]&\\quad-(\\beta-1)\\sum_i d_i^{-1}\\end{aligned}",
#             "\\text{本次未找到合格有限候选}"
#           ]
#         }
#       },
#       "inputs": [
#         "profile_likelihood"
#       ],
#       "outputs": [
#         "gamma_hat",
#         "status"
#       ],
#       "sources": [
#         {
#           "file": "python/methods/profile_solvers.py",
#           "symbol": "solve_mle_profile",
#           "from": "zero = points[0]"
#         },
#         {
#           "file": "python/methods/profile_solvers.py",
#           "symbol": "solve_mle_profile.add"
#         }
#       ],
#       "primarySource": 0,
#       "basis": "以位置得分由正转负的交点及剖面峰值精化有限候选，再按原对数似然选择位置。",
#       "notes": "扫描、括根、窄谷及峰值精化属于同一位置决策。候选不是迭代轨迹。支持边界 γ=t₍₁₎ 仅记极限诊断，不作可达有限解；有限网格与局部精化不构成全局证明。",
#       "flow": {
#         "label": "比较剖面似然确定位置",
#         "symbol": {
#           "default": "\\max_{\\gamma\\in\\mathcal C}\\ell_p(\\gamma)",
#           "zero": "\\hat\\gamma=0",
#           "failed": "\\mathcal C=\\varnothing"
#         }
#       },
#       "portGroups": {
#         "input-0": {
#           "refs": [
#             "profile_likelihood"
#           ],
#           "name": "候选似然",
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
#       "id": 4,
#       "name": "采纳对应位置的形状",
#       "description": "固定已经采纳的位置，读取该位置已求得的条件形状，不另跑一个估计器。",
#       "formula": {
#         "equations": [
#           "\\hat\\beta=\\beta^*(\\hat\\gamma)",
#           "S_\\beta(\\hat\\beta,\\hat\\gamma)=0"
#         ],
#         "explanation": "固定已经采纳的位置，读取该位置已求得的条件形状，不另跑一个估计器。",
#         "symbols": [
#           {
#             "symbol": "S_\\beta",
#             "meaning": "纵轴，条件形状得分"
#           },
#           {
#             "symbol": "\\beta",
#             "meaning": "横轴，形状参数"
#           }
#         ],
#         "variants": {
#           "boundary": [
#             "\\hat\\beta=1",
#             "S_\\beta(1,\\hat\\gamma)\\le0"
#           ],
#           "failed": [
#             "\\text{本次不返回形状估计}",
#             "\\mathcal C=\\varnothing"
#           ]
#         }
#       },
#       "inputs": [
#         "gamma_hat",
#         "normalized",
#         "n"
#       ],
#       "outputs": [
#         "beta_hat"
#       ],
#       "sources": [
#         {
#           "file": "python/methods/mle.py",
#           "symbol": "MLE.run",
#           "from": "beta, eta, gamma = (selected[p]",
#           "through": "beta, eta, gamma = (selected[p]"
#         },
#         {
#           "file": "python/methods/conditional_profiles.py",
#           "symbol": "_shape"
#         }
#       ],
#       "primarySource": 0,
#       "basis": "固定已经采纳的位置，读取该位置已求得的条件形状，不另跑一个估计器。",
#       "notes": "图读该候选在原求解过程中已记录的形状方程求值；β=1边界不要求得分为零。",
#       "flow": {
#         "label": "采纳对应的形状",
#         "symbol": {
#           "default": "\\hat\\beta=\\beta^*(\\hat\\gamma)",
#           "failed": "\\varnothing"
#         }
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
#             "normalized",
#             "n"
#           ],
#           "name": "样本与归一化",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "beta_hat"
#           ],
#           "name": "形状估计",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "id": 5,
#       "name": "由幂均值恢复尺度",
#       "description": "使用采纳位置和形状，逐样本距离取幂、求和、除以样本数并开形状次方。",
#       "formula": {
#         "equations": [
#           "\\hat\\eta=\\left(\\frac1n\\sum_i c_i\\right)^{1/\\hat\\beta}",
#           "c_i=d_i^{\\hat\\beta}",
#           "d_i=t_i-\\hat\\gamma"
#         ],
#         "explanation": "使用采纳位置和形状，逐样本距离取幂、求和、除以样本数并开形状次方。",
#         "symbols": [
#           {
#             "symbol": "c_i",
#             "meaning": "各样本的幂次贡献"
#           },
#           {
#             "symbol": "n",
#             "meaning": "样本数"
#           },
#           {
#             "symbol": "A",
#             "meaning": "幂次贡献的均值 Σcᵢ/n"
#           },
#           {
#             "symbol": "d_{\\max}",
#             "meaning": "本次最大平移距离，用于稳定幂次计算"
#           }
#         ],
#         "variants": {
#           "scaled": [
#             "\\hat\\eta=d_{\\max}\\left(\\frac1n\\sum_i c_i\\right)^{1/\\hat\\beta}",
#             "c_i=(d_i/d_{\\max})^{\\hat\\beta}",
#             "d_i=t_i-\\hat\\gamma"
#           ],
#           "failed": [
#             "\\text{本次不返回尺度估计}",
#             "\\mathcal C=\\varnothing",
#             "0\\le\\gamma<t_{(1)}"
#           ]
#         }
#       },
#       "inputs": [
#         "gamma_hat",
#         "beta_hat",
#         "ordered",
#         "n"
#       ],
#       "outputs": [
#         "eta_hat"
#       ],
#       "sources": [
#         {
#           "file": "python/methods/conditional_profiles.py",
#           "symbol": "mle_profile",
#           "from": "beta, score, boundary = solution"
#         },
#         {
#           "file": "python/methods/mle.py",
#           "symbol": "MLE.run",
#           "from": "beta, eta, gamma = (selected[p]",
#           "through": "beta, eta, gamma = (selected[p]"
#         }
#       ],
#       "primarySource": 0,
#       "basis": "使用采纳位置和形状，逐样本距离取幂、求和、除以样本数并开形状次方。",
#       "notes": "尺度已在该候选的条件求解中算出，这里展开其计算。若原始幂和溢出，展示同次记录的归一化幂及稳定计算关系。",
#       "flow": {
#         "label": "由幂均值恢复尺度",
#         "symbol": {
#           "default": "\\hat\\eta",
#           "failed": "\\varnothing"
#         }
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
#             "ordered",
#             "n"
#           ],
#           "name": "寿命样本",
#           "wrap": 2
#         },
#         "output-0": {
#           "refs": [
#             "eta_hat"
#           ],
#           "name": "尺度估计",
#           "wrap": 2
#         }
#       }
#     },
#     {
#       "id": 6,
#       "name": "汇总结果与拟合检查",
#       "description": "汇总三参数、概率图拟合优度和求解状态；R²不参与似然选点。",
#       "formula": {
#         "equations": [
#           "R^2=1-\\frac{\\sum_i(y_i-\\hat y_i)^2}{\\sum_i(y_i-\\bar y)^2}",
#           "y_i=\\ln[-\\ln(1-p_i)]",
#           "\\hat y_i=\\beta\\ln(t_i-\\gamma)-\\beta\\ln\\eta"
#         ],
#         "explanation": "汇总三参数、概率图拟合优度和求解状态；R²不参与似然选点。",
#         "symbols": [
#           {
#             "symbol": "p_i",
#             "meaning": "本次概率图绘图位置"
#           },
#           {
#             "symbol": "y_i",
#             "meaning": "经验概率变换"
#           },
#           {
#             "symbol": "\\hat y_i",
#             "meaning": "参数预测值"
#           },
#           {
#             "symbol": "\\bar y",
#             "meaning": "经验概率变换 yᵢ 的均值"
#           }
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
#           "file": "python/methods/mle.py",
#           "symbol": "MLE.run",
#           "from": "if selected is None:"
#         }
#       ],
#       "primarySource": 0,
#       "basis": "汇总三参数、概率图拟合优度和求解状态；R²不参与似然选点。",
#       "notes": "未找到有限候选或求解失败时保留真实状态，不填默认参数。",
#       "flow": {
#         "label": "汇总参数与拟合优度",
#         "symbol": "(\\hat\\beta,\\hat\\eta,\\hat\\gamma,R^2)"
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
#     "title": "MLE 计算流程",
#     "description": "准备样本，试算各位置的条件似然，比较有限候选定位置，采纳对应形状与尺度，再汇总结果。",
#     "targets": {
#       "samples": 1,
#       "trial": 2,
#       "location": 3,
#       "shape": 4,
#       "scale": 5,
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
#         "layout": "search",
#         "title": "位置搜索",
#         "children": [
#           {
#             "kind": "group",
#             "layout": "module",
#             "children": [
#               {
#                 "kind": "port",
#                 "anchor": "i2-1",
#                 "target": "trial",
#                 "direction": "input",
#                 "group": "input-0"
#               },
#               {
#                 "kind": "port",
#                 "anchor": "i2-2",
#                 "target": "trial",
#                 "direction": "input",
#                 "group": "input-1"
#               },
#               {
#                 "kind": "step",
#                 "anchor": "s2",
#                 "step": 2,
#                 "target": "trial"
#               },
#               {
#                 "kind": "port",
#                 "anchor": "o2",
#                 "target": "trial",
#                 "direction": "output",
#                 "group": "output-0"
#               }
#             ]
#           },
#           {
#             "kind": "group",
#             "layout": "module",
#             "children": [
#               {
#                 "kind": "port",
#                 "anchor": "i3-1",
#                 "target": "location",
#                 "direction": "input",
#                 "group": "input-0"
#               },
#               {
#                 "kind": "step",
#                 "anchor": "s3",
#                 "step": 3,
#                 "target": "location"
#               },
#               {
#                 "kind": "port",
#                 "anchor": "o3",
#                 "target": "location",
#                 "direction": "output",
#                 "group": "output-0"
#               }
#             ]
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
#             "target": "shape",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "port",
#             "anchor": "i4-2",
#             "target": "shape",
#             "direction": "input",
#             "group": "input-1"
#           },
#           {
#             "kind": "step",
#             "anchor": "s4",
#             "step": 4,
#             "target": "shape"
#           },
#           {
#             "kind": "port",
#             "anchor": "o4",
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
#             "anchor": "i5-1",
#             "target": "scale",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "port",
#             "anchor": "i5-2",
#             "target": "scale",
#             "direction": "input",
#             "group": "input-1"
#           },
#           {
#             "kind": "step",
#             "anchor": "s5",
#             "step": 5,
#             "target": "scale"
#           },
#           {
#             "kind": "port",
#             "anchor": "o5",
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
#             "anchor": "i6-1",
#             "target": "result",
#             "direction": "input",
#             "group": "input-0"
#           },
#           {
#             "kind": "port",
#             "anchor": "i6-2",
#             "target": "result",
#             "direction": "input",
#             "group": "input-1"
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
#         "from": "s3",
#         "to": "i2-2",
#         "dashed": true,
#         "label": "位置试算"
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
#         "from": "o3",
#         "to": "i5-1"
#       },
#       {
#         "from": "o4",
#         "to": "i5-1"
#       },
#       {
#         "from": "o1",
#         "to": "i5-2"
#       },
#       {
#         "from": "o3",
#         "to": "i6-1"
#       },
#       {
#         "from": "o4",
#         "to": "i6-1"
#       },
#       {
#         "from": "o5",
#         "to": "i6-2"
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
#     "unit": {
#       "symbol": "u",
#       "name": "归一化单位",
#       "meaning": "归一化单位",
#       "code": "unit"
#     },
#     "normalized": {
#       "symbol": "z_i",
#       "name": "归一化样本",
#       "meaning": "归一化样本",
#       "code": "z"
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
#     "trial_gamma": {
#       "symbol": "\\gamma",
#       "name": "试算位置",
#       "meaning": "试算位置",
#       "code": "trial_gamma",
#       "axisLabel": "位置参数 γ"
#     },
#     "trial_beta": {
#       "symbol": "\\beta^*(\\gamma)",
#       "name": "条件形状",
#       "meaning": "条件形状",
#       "code": "trial_beta",
#       "axisLabel": "形状参数 β"
#     },
#     "trial_eta": {
#       "symbol": "\\eta^*(\\gamma)",
#       "name": "条件尺度",
#       "meaning": "条件尺度",
#       "code": "trial_eta",
#       "axisLabel": "尺度参数 η"
#     },
#     "beta_axis": {
#       "symbol": "\\beta",
#       "name": "形状",
#       "meaning": "形状",
#       "axisLabel": "形状参数 β",
#       "code": "beta_axis"
#     },
#     "gamma_axis": {
#       "symbol": "\\gamma",
#       "name": "位置",
#       "meaning": "位置",
#       "axisLabel": "位置参数 γ",
#       "code": "gamma_axis"
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
#     "profile_likelihood": {
#       "symbol": "\\ell_p(\\gamma)",
#       "name": "剖面似然",
#       "meaning": "剖面似然",
#       "code": "likelihood_profile",
#       "axisLabel": "剖面对数似然 ℓₚ(γ)"
#     },
#     "shape_score": {
#       "symbol": "S_\\beta",
#       "name": "形状得分",
#       "meaning": "形状得分",
#       "axisLabel": "形状得分 Sβ",
#       "code": "shape_score"
#     },
#     "location_score": {
#       "symbol": "\\partial_\\gamma\\ell",
#       "name": "位置得分",
#       "meaning": "位置得分",
#       "axisLabel": "位置得分 ∂ℓ/∂γ",
#       "code": "location_score"
#     }
#   },
#   "chartBindings": {
#     "linked-shape-equation": {
#       "x": "beta_axis",
#       "y": "shape_score"
#     },
#     "profile-likelihood": {
#       "x": "gamma_axis",
#       "y": "profile_likelihood"
#     },
#     "location-score": {
#       "x": "gamma_axis",
#       "y": "location_score"
#     },
#     "conditional-shape-equation": {
#       "x": "beta_axis",
#       "y": "shape_score"
#     },
#     "scale-sample-contributions": {
#       "x": "sample_axis",
#       "y": "power"
#     }
#   }
# }
# @end-method-flow
