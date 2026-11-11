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
        self.last_solution_info = {k: v for k, v in info.items() if k not in ('profile_trace', 'selected_shape_evaluations', 'profile_shape_evaluations', 'prepared_samples')}
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
#   "presentation": "steps",
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
#         {
#           "code": "data",
#           "symbol": "t_i",
#           "meaning": "本次完整失效样本"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "n",
#           "symbol": "n",
#           "meaning": "样本数"
#         },
#         {
#           "code": "unit",
#           "symbol": "u",
#           "meaning": "归一化单位"
#         }
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
#       "notes": "当前实现使用 β≥1、γ≥0 的接受域。Hirose（1996）提供数值基准，当前程序不是其完整 GEV 求解流程。"
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
#         {
#           "code": "viewed_gamma",
#           "symbol": "\\gamma",
#           "meaning": "当前试算位置"
#         },
#         {
#           "code": "n",
#           "symbol": "n",
#           "meaning": "样本数"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "viewed_beta",
#           "symbol": "\\beta^*(\\gamma)",
#           "meaning": "当前条件形状"
#         },
#         {
#           "code": "viewed_eta",
#           "symbol": "\\eta^*(\\gamma)",
#           "meaning": "当前条件尺度"
#         },
#         {
#           "code": "viewed_ll",
#           "symbol": "\\ell_p(\\gamma)",
#           "meaning": "当前剖面似然"
#         }
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
#       "notes": "图中只读取本次求解的形状求值。β=1 下界得分≤0时按约束采纳；内层数值求根沿用Brent。尺度与似然在程序中使用中心化对数及logsumexp稳定计算。"
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
#         {
#           "code": "candidate_count",
#           "symbol": "|\\mathcal C|",
#           "meaning": "合格候选数"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "gamma",
#           "symbol": "\\hat\\gamma",
#           "meaning": "按似然采纳的位置"
#         },
#         {
#           "code": "log_likelihood",
#           "symbol": "\\ell_p(\\hat\\gamma)",
#           "meaning": "采纳候选的似然"
#         }
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
#       "notes": "扫描、括根、窄谷及峰值精化属于同一位置决策。候选不是迭代轨迹。支持边界 γ=t₍₁₎ 仅记极限诊断，不作可达有限解；有限网格与局部精化不构成全局证明。"
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
#         {
#           "code": "gamma",
#           "symbol": "\\hat\\gamma",
#           "meaning": "已采纳位置"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "beta",
#           "symbol": "\\hat\\beta",
#           "meaning": "采纳候选的条件形状"
#         }
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
#       "notes": "图读该候选在原求解过程中已记录的形状方程求值；β=1边界不要求得分为零。"
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
#         {
#           "code": "gamma",
#           "symbol": "\\hat\\gamma",
#           "meaning": "采纳位置"
#         },
#         {
#           "code": "beta",
#           "symbol": "\\hat\\beta",
#           "meaning": "采纳形状"
#         },
#         {
#           "code": "n",
#           "symbol": "n",
#           "meaning": "样本数"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "eta",
#           "symbol": "\\hat\\eta",
#           "meaning": "采纳尺度"
#         }
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
#       "notes": "尺度已在该候选的条件求解中算出，这里展开其计算。若原始幂和溢出，展示同次记录的归一化幂及稳定计算关系。"
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
#         {
#           "code": "beta",
#           "symbol": "\\hat\\beta",
#           "meaning": "采纳形状"
#         },
#         {
#           "code": "eta",
#           "symbol": "\\hat\\eta",
#           "meaning": "采纳尺度"
#         },
#         {
#           "code": "gamma",
#           "symbol": "\\hat\\gamma",
#           "meaning": "采纳位置"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "r_squared",
#           "symbol": "R^2",
#           "meaning": "概率图拟合优度"
#         }
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
#       "notes": "未找到有限候选或求解失败时保留真实状态，不填默认参数。"
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
#     "legacySourceSteps": [
#       1,
#       2,
#       2,
#       3,
#       3,
#       6
#     ],
#     "items": [
#       {
#         "kind": "group",
#         "layout": "inputs",
#         "children": [
#           {
#             "kind": "port",
#             "anchor": "sample",
#             "target": "samples",
#             "direction": "input",
#             "label": "失效样本 tᵢ",
#             "text": {
#               "default": [
#                 "排序并建立支持范围"
#               ],
#               "ready": [
#                 "n = {count}"
#               ]
#             }
#           }
#         ]
#       },
#       {
#         "kind": "group",
#         "layout": "prepare",
#         "children": [
#           {
#             "kind": "step",
#             "anchor": "prepare",
#             "step": 1,
#             "target": "samples"
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
#             "layout": "searchContent",
#             "children": [
#               {
#                 "kind": "step",
#                 "anchor": "trial",
#                 "step": 2,
#                 "target": "trial",
#                 "text": {
#                   "default": [
#                     "条件形状 → 尺度 → 似然"
#                   ],
#                   "ready": [
#                     "γ = {viewedGamma}"
#                   ]
#                 }
#               },
#               {
#                 "kind": "step",
#                 "anchor": "location",
#                 "step": 3,
#                 "target": "location",
#                 "text": {
#                   "default": [
#                     "精化候选并比较似然"
#                   ],
#                   "ready": [
#                     "γ̂ = {gamma}"
#                   ],
#                   "zero": [
#                     "γ̂ = 0"
#                   ],
#                   "failed": [
#                     "未找到有限候选"
#                   ]
#                 }
#               }
#             ]
#           }
#         ],
#         "sideLabel": "换位置"
#       },
#       {
#         "kind": "group",
#         "layout": "scale",
#         "children": [
#           {
#             "kind": "step",
#             "anchor": "shape",
#             "step": 4,
#             "target": "shape",
#             "text": {
#               "ready": [
#                 "β̂ = {beta}"
#               ],
#               "failed": [
#                 "不返回估计值"
#               ]
#             }
#           },
#           {
#             "kind": "step",
#             "anchor": "scale",
#             "step": 5,
#             "target": "scale",
#             "text": {
#               "ready": [
#                 "η̂ = {eta}"
#               ],
#               "failed": [
#                 "不返回估计值"
#               ]
#             }
#           },
#           {
#             "kind": "step",
#             "anchor": "result",
#             "step": 6,
#             "target": "result"
#           }
#         ]
#       }
#     ],
#     "connections": [
#       {
#         "from": "sample",
#         "to": "prepare"
#       },
#       {
#         "from": "prepare",
#         "to": "trial"
#       },
#       {
#         "from": "trial",
#         "to": "location"
#       },
#       {
#         "from": "location",
#         "to": "shape"
#       },
#       {
#         "from": "shape",
#         "to": "scale"
#       },
#       {
#         "from": "scale",
#         "to": "result"
#       },
#       {
#         "from": "location",
#         "to": "trial",
#         "route": "loop",
#         "dashed": true
#       }
#     ]
#   }
# }
# @end-method-flow
