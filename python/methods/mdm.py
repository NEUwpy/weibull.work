"""
最小差异法 (MDM)
Minimum Discrepancy Method

算法文档: ../../src/content/algorithms/mdm.md
描述: 通过最小化伪尺度参数的标准差来估计参数，引入梯度偏移判据提高稳健性
"""

from base import WeibullBase
import numpy as np
from scipy.optimize import minimize_scalar
from .calculation_trace import plot_point, plot_series, plot_chart


def _json_float(value):
    """Convert numpy scalars to plain floats while preserving None."""
    if value is None:
        return None
    return float(value)


def _build_geometric_gamma_grid(t_min, gamma_steps):
    """Build a discrete gamma grid searched from t_min downward to 0."""
    steps = max(4, int(gamma_steps))
    min_gap = max(abs(float(t_min)) * 1e-9, 1e-12)
    gaps = np.geomspace(min_gap, float(t_min), steps)
    gammas = float(t_min) - gaps
    gammas[0] = float(t_min) - min_gap
    gammas[-1] = 0.0
    return gammas


def _find_offset_crossing(gammas, gradients, offset):
    """Interpolate the rightmost crossing between adjacent sampled gradients."""
    diffs = gradients - offset
    candidates = []

    for i in range(len(diffs) - 1):
        y1, y2 = diffs[i], diffs[i + 1]
        if not (np.isfinite(y1) and np.isfinite(y2)):
            continue
        if y1 == 0 or y2 == 0 or (y1 < 0) != (y2 < 0):
            candidates.append(i)

    if not candidates:
        return None

    idx = max(candidates, key=lambda i: max(gammas[i], gammas[i + 1]))
    left, right = sorted((idx, idx + 1), key=lambda i: gammas[i])
    y1, y2 = diffs[left], diffs[right]
    x1, x2 = gammas[left], gammas[right]

    if y2 == 0:
        gamma = x2
    else:
        gamma = x1 + (-y1 / (y2 - y1)) * (x2 - x1)

    bracket = {
        "left": {
            "gamma": _json_float(x1),
            "gradient": _json_float(gradients[left]),
            "diff": _json_float(y1),
        },
        "right": {
            "gamma": _json_float(x2),
            "gradient": _json_float(gradients[right]),
            "diff": _json_float(y2),
        },
    }
    return float(gamma), bracket


class MDM(WeibullBase):
    def run(self, trace=False, offset=None, gamma_steps=60, rank_method='bernard'):
        """
        Run the Minimum Discrepancy Method.

        Args:
            trace (bool): Whether to record trace data.
            offset (float): Gradient offset target (required, e.g., 0.1).
            gamma_steps (int): 几何 gamma 网格采样点数 / 搜索与可视化采样密度 (default 60).
            rank_method (str): Median rank method - 'bernard' or 'exact' (default 'bernard').

        Returns:
            (beta, eta, gamma, r_squared, status) where status is True for either
            a bracketed interpolation, gamma=0 truncation, or a right-edge
            fallback. If the grid has no crossing, probe near t_min for a bracket.
        """
        if offset is None:
            raise ValueError("offset parameter is required (e.g., offset=0.1)")
        self.calculation_trace = None

        original_rank_method = self.rank_method
        self.rank_method = rank_method
        t = self.data
        n = self.n

        # @flow-anchor ranks
        ranks = self._median_ranks()
        neg_ln_1_minus_F = -np.log(1 - ranks)

        # @flow-anchor pseudo-scale-helper
        def calculate_eta_std(beta, gamma, current_t):
            if beta <= 0: return float('inf')
            denom = np.power(neg_ln_1_minus_F, 1.0/beta)
            etas = (current_t - gamma) / denom
            return np.std(etas, ddof=1)

        beta_sigma_cache = {}
        profile_gradient_cache = {}
        beta_evaluations = {} if trace else None

        def find_best_beta_for_gamma(gamma):
            if gamma >= t[0]:
                return None, float('inf')
            cache_key = float(gamma)
            if cache_key in beta_sigma_cache:
                return beta_sigma_cache[cache_key]
            def beta_objective(beta):
                sigma = calculate_eta_std(beta, gamma, t)
                if trace:
                    beta_evaluations.setdefault(cache_key, []).append(
                        dict(beta=float(beta), sigma=float(sigma)))
                return sigma

            res = minimize_scalar(
                beta_objective,
                bounds=(0.1, 15.0),
                method='bounded'
            )
            beta_sigma_cache[cache_key] = (res.x, res.fun)
            return beta_sigma_cache[cache_key]

        def profile_sigma(gamma):
            _, sigma = find_best_beta_for_gamma(float(gamma))
            return float(sigma)

        def profile_gradient(gamma):
            """Finite-difference derivative of the profiled sigma curve."""
            gamma = float(gamma)
            cache_key = gamma
            if cache_key in profile_gradient_cache:
                return profile_gradient_cache[cache_key]
            t_min_float = float(t_min)
            scale = max(abs(t_min_float), 1.0)
            nominal_h = scale * 1e-5
            left_room = max(gamma, 0.0)
            right_room = max(t_min_float - gamma, 0.0)

            if right_room <= 0:
                return float("inf")

            if gamma <= 0.0 or left_room <= nominal_h:
                h = min(nominal_h, right_room * 0.25)
                h = max(h, np.finfo(float).eps * scale)
                gradient = (profile_sigma(gamma + h) - profile_sigma(gamma)) / h
                profile_gradient_cache[cache_key] = float(gradient)
                return profile_gradient_cache[cache_key]

            if right_room <= nominal_h:
                h = min(nominal_h, left_room * 0.25, right_room * 0.5)
                h = max(h, np.finfo(float).eps * scale)
                gradient = (profile_sigma(gamma) - profile_sigma(gamma - h)) / h
                profile_gradient_cache[cache_key] = float(gradient)
                return profile_gradient_cache[cache_key]

            h = min(nominal_h, left_room * 0.25, right_room * 0.25)
            h = max(h, np.finfo(float).eps * scale)
            gradient = (profile_sigma(gamma + h) - profile_sigma(gamma - h)) / (2.0 * h)
            profile_gradient_cache[cache_key] = float(gradient)
            return profile_gradient_cache[cache_key]

        def find_right_anchor():
            """Probe points increasingly close to t_min until g(gamma) exceeds offset."""
            t_min_float = float(t_min)
            min_gap = max(abs(t_min_float) * 1e-12, 1e-12)
            gaps = np.geomspace(max(abs(t_min_float) * 1e-3, min_gap), min_gap, 24)

            best_anchor = None
            for gap in gaps:
                gamma = max(0.0, t_min_float - float(gap))
                if gamma >= t_min_float:
                    gamma = t_min_float - min_gap
                grad = float(profile_gradient(gamma))
                if not np.isfinite(grad):
                    continue
                anchor = (gamma, grad)
                if best_anchor is None or gamma > best_anchor[0]:
                    best_anchor = anchor
                if grad >= offset:
                    return anchor

            if best_anchor is not None:
                return best_anchor

            gamma = max(0.0, t_min_float - min_gap)
            return gamma, float(profile_gradient(gamma))

        def refine_crossing(bracket):
            """Narrow the sampled bracket before estimating its crossing."""
            left, right = bracket["left"]["gamma"], bracket["right"]["gamma"]
            g_left, g_right = bracket["left"]["gradient"], bracket["right"]["gradient"]
            max_width = float(t_min) * 1e-5
            while right - left > max_width and g_left != offset and g_right != offset:
                midpoint = left + (right - left) / 2.0
                if not left < midpoint < right:
                    break
                g_midpoint = profile_gradient(midpoint)
                if not np.isfinite(g_midpoint):
                    break
                if g_midpoint == offset or (g_left < offset) != (g_midpoint < offset):
                    right, g_right = midpoint, g_midpoint
                else:
                    left, g_left = midpoint, g_midpoint
            return _find_offset_crossing(np.array([left, right]), np.array([g_left, g_right]), offset)

        def fit_right_edge_root(anchor_gamma, anchor_gradient):
            """Return an interior root estimate when the sampled right edge is still below offset."""
            t_min_float = float(t_min)
            virtual_gamma = float(np.nextafter(t_min_float, 0.0))
            if virtual_gamma <= anchor_gamma:
                gap = max(t_min_float - float(anchor_gamma), 0.0)
                fallback_gap = max(gap * 0.5, np.finfo(float).eps * max(abs(t_min_float), 1.0))
                virtual_gamma = min(t_min_float - fallback_gap, float(np.nextafter(t_min_float, 0.0)))
            virtual_gamma = min(max(float(virtual_gamma), 0.0), float(np.nextafter(t_min_float, 0.0)))

            return {
                "gamma": virtual_gamma,
                "anchor_gradient": float(anchor_gradient),
                "virtual_gradient": float(offset),
                "model": "right_endpoint_asymptote",
            }

        # @flow-anchor location-grid
        t_min = t[0]

        # @flow-anchor grid-scan
        # @loop: gamma_steps 次 (默认 60)
        gammas = _build_geometric_gamma_grid(t_min, gamma_steps)
        sigma_mins = []
        best_betas = []

        for g in gammas:
            b, sig = find_best_beta_for_gamma(g)
            sigma_mins.append(sig)
            best_betas.append(b)

        sigma_mins = np.array(sigma_mins, dtype=float)
        best_betas = np.array(best_betas, dtype=float)

        grads = np.array([profile_gradient(g) for g in gammas], dtype=float)

        # @flow-anchor crossing
        root_info = _find_offset_crossing(gammas, grads, offset)
        probe_gradient_at_zero = float(profile_gradient(0.0))
        at_zero = probe_gradient_at_zero >= offset
        legacy_grid_crossing = root_info is not None
        right_anchor_gamma = right_anchor_gradient = None

        if root_info is None and not at_zero:
            right_anchor_gamma, right_anchor_gradient = find_right_anchor()
            trial_points = sorted(profile_gradient_cache.items())
            trial_gammas, trial_gradients = map(np.asarray, zip(*trial_points))
            root_info = _find_offset_crossing(trial_gammas, trial_gradients, offset)

        if root_info is not None and not at_zero:
            _, coarse_bracket = root_info
            root_info = refine_crossing(coarse_bracket)

        # @flow-anchor position
        root_bracket = None
        root_solver = None
        right_edge_extrapolation = None

        if at_zero:
            found_gamma = 0.0
            solution_strategy = "truncated_at_zero"
        elif root_info is not None:
            found_gamma, root_bracket = root_info
            solution_strategy = "interpolated_crossing"
            root_solver = "linear_interpolation"
        else:
            right_edge_extrapolation = fit_right_edge_root(right_anchor_gamma, right_anchor_gradient)
            found_gamma = right_edge_extrapolation["gamma"]
            solution_strategy = root_solver = "right_edge_fit"
            root_bracket = {
                "left": {
                    "gamma": _json_float(right_anchor_gamma),
                    "gradient": _json_float(right_anchor_gradient),
                    "diff": _json_float(right_anchor_gradient - offset),
                },
                "right": {
                    "gamma": _json_float(found_gamma),
                    "gradient": _json_float(offset),
                    "diff": 0.0,
                    "virtual": True,
                },
            }

        found_beta, _ = find_best_beta_for_gamma(found_gamma)

        # @flow-anchor scale
        denom = np.power(neg_ln_1_minus_F, 1.0/found_beta)
        etas = (t - found_gamma) / denom
        found_eta = np.mean(etas)

        # @flow-anchor fit
        r2 = self._calculate_r2(found_beta, found_eta, found_gamma)

        self.last_solution_info = {
            "target_offset": offset,
            "search_strategy": "geometric_from_tmin",
            "solution_strategy": solution_strategy,
            "constraint": "gamma >= 0",
            "probe_gradient_at_zero": probe_gradient_at_zero,
            "root_bracket": root_bracket,
            "root_solver": root_solver,
            "right_anchor_gamma": right_anchor_gamma,
            "right_anchor_gradient": right_anchor_gradient,
            "root_solver_iterations": 0,
            "legacy_grid_crossing": legacy_grid_crossing,
            "right_edge_extrapolation": right_edge_extrapolation,
            "gamma_steps": len(gammas),
            "optimal_gamma": found_gamma,
            "optimal_beta": found_beta,
        }

        # @flow-anchor trace
        if trace:
            # Freeze actual solver evaluations. Plotting must not run additional
            # objective evaluations or create a separate sampling grid.
            solver_beta_evaluations = {g: list(values) for g, values in beta_evaluations.items()}
            solver_gradient_evaluations = {g: v for g, v in profile_gradient_cache.items()
                                           if np.isfinite(v)}
            selected_sigma = float(beta_sigma_cache[float(found_gamma)][1])
            beta_points = [plot_point(p['beta'], p['sigma'], beta=p['beta'],
                                      gamma=float(found_gamma), evaluation=i + 1)
                           for i, p in enumerate(beta_evaluations.get(float(found_gamma), []))]
            gradient_values = [
                dict(gamma=g, gradient=v, residual=v - offset, evaluation=i)
                for i, (g, v) in enumerate(solver_gradient_evaluations.items(), start=1)
            ]
            gradient_points = [plot_point(p['gamma'], p['gradient'], **p) for p in gradient_values]
            selected_gradient = profile_gradient_cache.get(float(found_gamma))
            approximate = root_solver == 'right_edge_fit'
            location_selection = []
            location_formula = None
            if solution_strategy == 'truncated_at_zero':
                selection_description = 'g(0)≥δ，按当前 γ≥0 工程约束选择 γ=0，再求对应 β 与 η。'
                location_selection = [plot_point(found_gamma, selected_gradient, label='零位置')]
            elif approximate:
                selection_description = '未找到夹住 δ 的相邻梯度点，按右端回退规则取靠近最小观测值的位置。'
            else:
                selection_description = '在夹住 δ 的两个相邻梯度点间线性插值取 γ，再求该位置的条件最优 β。'
                location_selection = [plot_point(found_gamma, offset, label='线性插值交点', source='linear_interpolation')]
                location_formula = r'\hat\gamma=\gamma_L+\frac{\delta-g_L}{g_R-g_L}(\gamma_R-\gamma_L)'
                if any(point['diff'] == 0 for point in root_bracket.values()):
                    location_formula = r'\hat\gamma=\gamma_i,\quad g_i=\delta'
            gradient_series = [plot_series('gradient', '实际梯度求值', gradient_points)]
            if approximate:
                gradient_series.append(plot_series(
                    'endpoint-fit', '端点外推目标（非函数值）',
                    [plot_point(found_gamma, offset, virtual=True)], role='virtual', kind='scatter'))
            self.calculation_trace = dict(
                schema_version=1, method='mdm',
                criterion=dict(description=selection_description),
                charts=[
                    plot_chart(
                        'shape-discrepancy', '固定最终位置后的形状搜索',
                        '形状参数 β', '伪尺度标准差 σ₍η₎',
                        [plot_series('sigma', '本次内层实际求值', beta_points)],
                        description='固定本次最终 γ，展示内层有界搜索实际计算的标准差；选中点直接使用求解器返回的最小值。',
                        selected=[plot_point(found_beta, selected_sigma, label='选中形状参数')]),
                    plot_chart(
                        'location-criterion', '位置参数的梯度偏移判据',
                        '位置参数 γ', '剖面标准差梯度 g(γ)', gradient_series,
                        description=selection_description + ' 曲线按 γ 排列，详细记录保留真实求值次序。',
                        formula=location_formula,
                        references=[dict(axis='y', value=float(offset), label='目标偏移量 δ')],
                        selected=location_selection),
                ],
                selection=dict(description=selection_description, beta=float(found_beta),
                               eta=float(found_eta), gamma=float(found_gamma),
                               sigma=selected_sigma, target_offset=float(offset),
                               gradient=float(selected_gradient) if selected_gradient is not None else None,
                               approximate=approximate, strategy=solution_strategy, solver=root_solver),
                details=dict(rank_method=rank_method, shape_search_bounds=[0.1, 15.0],
                             sigma_ddof=1, root_bracket=root_bracket,
                             root_solver_iterations=0,
                             root_evaluations=gradient_values,
                             gradient_scan=[dict(gamma=float(g), gradient=float(v))
                                            for g, v in zip(gammas, grads) if np.isfinite(v)],
                             pseudo_scales=[dict(observation=float(ti), rank=float(ri),
                                                 distance=float(ti-found_gamma),
                                                 rank_transform=float(xi), denominator=float(di),
                                                 eta=float(ei))
                                            for ti, ri, xi, di, ei in zip(t, ranks, neg_ln_1_minus_F, denom, etas)],
                             pseudo_scale_sum=float(np.sum(etas)),
                             boundary_rule='gamma >= 0',
                             supplementary_legacy_curves='旧 trace_data 曲线按横坐标排列本次实际求值，不额外补采样'),
            )
            # 1. Sigma vs Beta curve (at optimal gamma) - for backward compatibility
            sigma_beta_curve = [dict(p, source='solver_evaluation', evaluation=i+1)
                                for i, p in enumerate(solver_beta_evaluations.get(float(found_gamma), []))]
            sigma_beta_curve.sort(key=lambda point: point['beta'])

            # 2. Full 2D surface data: sigma_beta_gamma for 3D visualization
            num_gamma_samples = 20
            gamma_indices = np.linspace(0, len(gammas) - 1, num_gamma_samples, dtype=int)
            sampled_gammas = gammas[gamma_indices]
            sigma_beta_gamma = []

            for idx, g in enumerate(sampled_gammas):
                evaluated = [dict(p, evaluation=i+1)
                             for i, p in enumerate(solver_beta_evaluations.get(float(g), []))]
                ordered = sorted(evaluated, key=lambda point: point['beta'])

                sigma_beta_gamma.append({
                    "gamma": float(g),
                    "betas": [p['beta'] for p in ordered],
                    "sigmas": [p['sigma'] for p in ordered],
                    "solver_points": evaluated,
                })

            # 3. Gradient vs Gamma curve. This uses the same profile_gradient
            # function as the backend solver, so the visual trace and result match.
            grad_gamma_points = {}

            def add_gradient_point(gamma, gradient, source="trace_grid", virtual=False, evaluation=None):
                gamma = float(gamma)
                b, sig = beta_sigma_cache.get(gamma, (None, None))
                eta_mean = None
                if b is not None:
                    denom = np.power(neg_ln_1_minus_F, 1.0/b)
                    eta_mean = float(np.mean((t - gamma) / denom))
                point = {
                    "gamma": gamma,
                    "gradient": float(gradient),
                    "sigma_min": _json_float(sig),
                    "best_beta": _json_float(b),
                    "best_eta": eta_mean,
                    "source": source,
                }
                if virtual:
                    point["virtual"] = True
                if evaluation is not None:
                    point['evaluation'] = evaluation
                grad_gamma_points[gamma] = point

            for g, gradient in solver_gradient_evaluations.items():
                add_gradient_point(g, gradient, source='solver_evaluation')
            for i in range(len(gammas)):
                add_gradient_point(gammas[i], grads[i])
            for p in gradient_values:
                add_gradient_point(p['gamma'], p['gradient'], source='solver_evaluation',
                                   evaluation=p.get('evaluation'))

            if approximate:
                add_gradient_point(found_gamma, offset, source="solver_root", virtual=True)
            elif solution_strategy == "truncated_at_zero":
                add_gradient_point(0.0, probe_gradient_at_zero, source="solver_root")

            grad_gamma_curve = sorted(
                grad_gamma_points.values(),
                key=lambda point: point["gamma"],
                reverse=True,
            )

            self.trace_data = {
                "sigma_beta_curve": sigma_beta_curve,
                "grad_gamma_curve": grad_gamma_curve,
                "sigma_beta_gamma": sigma_beta_gamma,
                **self.last_solution_info,
            }

        return float(found_beta), float(found_eta), float(found_gamma), float(r2), True


# @method-flow
# {
#   "schemaVersion": 2,
#   "methodId": "mdm",
#   "methodName": "最小差异法 (MDM)",
#   "description": "伪尺度离散度 → 条件形状优化 → 梯度偏移定位 → 尺度恢复。",
#   "steps": [
#     {
#       "name": "准备样本",
#       "description": "校验并排序失效样本，计算经验概率及其变换。",
#       "formula": {
#         "equations": [
#           "F(t_i)=\\frac{i-0.3}{n+0.4}",
#           "x_i=-\\ln(1-F(t_i))"
#         ],
#         "variants": {
#           "exact": [
#             "F(t_i)=I^{-1}_{0.5}(i,n+1-i)",
#             "x_i=-\\ln(1-F(t_i))"
#           ]
#         },
#         "symbols": [
#           {
#             "symbol": "F(t_i)",
#             "meaning": "第i个样本点的经验累积概率"
#           },
#           {
#             "symbol": "x_i",
#             "meaning": "变换后的中位秩"
#           }
#         ],
#         "explanation": "使用 Bernard 公式计算经验累积分布函数值"
#       },
#       "inputs": [
#         {
#           "code": "self.data",
#           "symbol": "t_i",
#           "meaning": "已排序样本"
#         },
#         {
#           "code": "rank_method",
#           "symbol": "p",
#           "meaning": "本次绘图位置规则"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "t",
#           "symbol": "t",
#           "meaning": "排序后数组"
#         },
#         {
#           "code": "ranks",
#           "symbol": "F(t_i)",
#           "meaning": "中位秩数组"
#         },
#         {
#           "code": "neg_ln_1_minus_F",
#           "symbol": "x_i",
#           "meaning": "变换数组"
#         }
#       ],
#       "basis": "原文式(3)以秩概率构造伪尺度；当前默认Bernard近似秩，精确秩分支见同一步源码。",
#       "notes": "所示主公式为默认 Bernard；exact 分支使用 Beta 分布中位数，见绘图位置源码。",
#       "sources": [
#         {
#           "file": "python/base.py",
#           "symbol": "WeibullBase.__init__"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run",
#           "from": "if offset is None:",
#           "until": "# @flow-anchor pseudo-scale-helper",
#           "label": "读取样本并计算经验概率"
#         },
#         {
#           "file": "python/base.py",
#           "symbol": "WeibullBase._median_ranks"
#         }
#       ],
#       "id": 1,
#       "primarySource": 1
#     },
#     {
#       "name": "试算各位置的最小差异",
#       "description": "扫描位置网格，在每个试算位置上选出使伪尺度标准差最小的形状。",
#       "formula": {
#         "equations": [
#           "\\beta^*(\\gamma)=\\arg\\min_{0.1\\le\\beta\\le15}\\sigma_\\eta(\\beta,\\gamma)",
#           "s(\\gamma)=\\min_\\beta\\sigma_\\eta(\\beta,\\gamma)",
#           "\\eta_i=\\frac{t_i-\\gamma}{[-\\ln(1-p_i)]^{1/\\beta}}",
#           "\\sigma_\\eta=\\sqrt{\\frac{\\sum_i(\\eta_i-\\bar\\eta)^2}{n-1}}"
#         ],
#         "explanation": "每个试算位置的最小标准差组成 s(γ)，供下一步计算梯度。",
#         "symbols": [
#           {
#             "symbol": "\\beta",
#             "meaning": "横轴，形状参数"
#           },
#           {
#             "symbol": "\\sigma_\\eta",
#             "meaning": "纵轴，伪尺度的样本标准差"
#           },
#           {
#             "symbol": "\\eta_i",
#             "meaning": "第 i 个样本反算的伪尺度"
#           },
#           {
#             "symbol": "\\bar\\eta",
#             "meaning": "当前试算参数下的伪尺度均值"
#           },
#           {
#             "symbol": "\\gamma_j",
#             "meaning": "位置候选"
#           },
#           {
#             "symbol": "\\beta^*(\\gamma)",
#             "meaning": "给定γ时的最优β"
#           }
#         ]
#       },
#       "inputs": [
#         {
#           "code": "t",
#           "symbol": "t_i",
#           "meaning": "排序后的失效时间"
#         },
#         {
#           "code": "neg_ln_1_minus_F",
#           "symbol": "x_i",
#           "meaning": "经验概率变换"
#         },
#         {
#           "code": "gamma_steps",
#           "symbol": "N",
#           "meaning": "网格密度"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "gammas",
#           "symbol": "\\gamma_j",
#           "meaning": "试算位置"
#         },
#         {
#           "code": "best_betas",
#           "symbol": "\\beta^*(\\gamma_j)",
#           "meaning": "各试算位置的条件形状"
#         },
#         {
#           "code": "sigma_mins",
#           "symbol": "s(\\gamma_j)",
#           "meaning": "各试算位置的最小标准差"
#         }
#       ],
#       "basis": "数值策略：每个位置候选调用有界标量优化并缓存结果。",
#       "notes": "β∈[0.1,15]是当前工程搜索范围，不是所有MDM版本的普遍理论约束。",
#       "sources": [
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run",
#           "from": "# @flow-anchor location-grid",
#           "until": "grads = np.array",
#           "label": "建立网格并扫描"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "_build_geometric_gamma_grid"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run.find_best_beta_for_gamma"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run.calculate_eta_std"
#         }
#       ],
#       "id": 2,
#       "primarySource": 0
#     },
#     {
#       "name": "按梯度偏移求位置",
#       "description": "用最小标准差的梯度与目标 δ 定位交点，确定位置 γ̂。",
#       "formula": {
#         "equations": [
#           "g(\\hat\\gamma)=\\delta",
#           "g(\\gamma)=\\frac{ds(\\gamma)}{d\\gamma}"
#         ],
#         "variants": {
#           "zero": [
#             "g(0)\\ge\\delta,\\quad\\hat\\gamma=0",
#             "g(\\gamma)=\\frac{ds(\\gamma)}{d\\gamma}"
#           ],
#           "extrapolated": [
#             "\\hat\\gamma=t_{(1)}-\\varepsilon",
#             "\\varepsilon>0"
#           ]
#         },
#         "explanation": "常规情况取夹住 δ 的两个梯度点之间的线性插值位置。",
#         "symbols": [
#           {
#             "symbol": "\\gamma",
#             "meaning": "横轴，位置参数"
#           },
#           {
#             "symbol": "s(\\gamma)",
#             "meaning": "该位置下的最小标准差"
#           },
#           {
#             "symbol": "g(\\gamma)",
#             "meaning": "最小标准差的数值梯度"
#           },
#           {
#             "symbol": "\\delta",
#             "meaning": "目标梯度"
#           }
#         ]
#       },
#       "inputs": [
#         {
#           "code": "profile_sigma",
#           "symbol": "s(\\gamma)",
#           "meaning": "各位置的条件最小标准差"
#         },
#         {
#           "code": "offset",
#           "symbol": "\\delta",
#           "meaning": "偏移阈值"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "found_gamma",
#           "symbol": "\\hat\\gamma",
#           "meaning": "偏移判据选出的位置"
#         },
#         {
#           "code": "solution_strategy",
#           "symbol": "\\mathrm{strategy}",
#           "meaning": "位置采纳方式"
#         }
#       ],
#       "basis": "以梯度达到偏移量为取点判据。差分、缩小区间和线性插值可对照本步源码。",
#       "notes": "零位置梯度达到目标时取零。网格及补探仍缺少夹区间时，标记为右端回退。",
#       "sources": [
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run",
#           "from": "grads = np.array",
#           "until": "found_beta, _ = find_best_beta_for_gamma(found_gamma)",
#           "label": "确定位置"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run.profile_gradient"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run.profile_sigma"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run.refine_crossing"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "_find_offset_crossing"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run.find_right_anchor"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run.fit_right_edge_root"
#         }
#       ],
#       "id": 3,
#       "primarySource": 0
#     },
#     {
#       "name": "回代位置求形状",
#       "description": "固定已选出的 γ̂，采纳在此位置使伪尺度标准差最小的形状。",
#       "formula": {
#         "equations": [
#           "\\hat\\beta=\\beta^*(\\hat\\gamma)",
#           "\\beta^*(\\hat\\gamma)=\\arg\\min_{0.1\\le\\beta\\le15}\\sigma_\\eta(\\beta,\\hat\\gamma)"
#         ],
#         "symbols": [
#           {
#             "symbol": "\\beta",
#             "meaning": "横轴，形状参数"
#           },
#           {
#             "symbol": "\\hat\\gamma",
#             "meaning": "上一阶段采纳的位置"
#           },
#           {
#             "symbol": "\\sigma_\\eta",
#             "meaning": "伪尺度的样本标准差"
#           }
#         ],
#         "explanation": "在 γ̂ 对应的标准差曲线上取最低点。"
#       },
#       "inputs": [
#         {
#           "code": "found_gamma",
#           "symbol": "\\hat\\gamma",
#           "meaning": "偏移判据选出的位置"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "found_beta",
#           "symbol": "\\hat\\beta",
#           "meaning": "在选定位置下采纳的形状"
#         }
#       ],
#       "basis": "调用与试算阶段相同的条件形状寻优，位置固定为已采纳的 γ̂。",
#       "notes": "若已在该位置完成寻优，程序会复用缓存的最小值。",
#       "sources": [
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run",
#           "from": "found_beta, _ = find_best_beta_for_gamma(found_gamma)",
#           "until": "# @flow-anchor scale",
#           "label": "回代选定位置"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run.find_best_beta_for_gamma"
#         }
#       ],
#       "primarySource": 0,
#       "id": 4
#     },
#     {
#       "name": "反算尺度",
#       "description": "使用最优的 γ* 和 β* 计算所有伪尺度参数的均值",
#       "formula": {
#         "equations": [
#           "\\hat\\eta=\\frac1n\\sum_{i=1}^n\\eta_i",
#           "\\eta_i=\\frac{t_i-\\hat\\gamma}{x_i^{1/\\hat\\beta}}"
#         ],
#         "symbols": [
#           {
#             "symbol": "\\eta_i",
#             "meaning": "第 i 个样本反算的伪尺度"
#           },
#           {
#             "symbol": "x_i",
#             "meaning": "经验概率变换 −ln(1−pᵢ)"
#           },
#           {
#             "symbol": "n",
#             "meaning": "失效样本数"
#           },
#           {
#             "symbol": "\\hat{\\eta}",
#             "meaning": "尺度参数估计值"
#           }
#         ],
#         "explanation": "使用最优的 γ* 和 β* 计算所有伪尺度参数的均值"
#       },
#       "inputs": [
#         {
#           "code": "found_gamma",
#           "symbol": "\\hat{\\gamma}",
#           "meaning": "最优γ"
#         },
#         {
#           "code": "found_beta",
#           "symbol": "\\hat{\\beta}",
#           "meaning": "最优β"
#         },
#         {
#           "code": "t",
#           "symbol": "t",
#           "meaning": "失效时间数组"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "found_eta",
#           "symbol": "\\hat{\\eta}",
#           "meaning": "尺度参数估计值"
#         }
#       ],
#       "basis": "方法构造：在选定β、γ后，以伪尺度的均值恢复η。",
#       "notes": "",
#       "sources": [
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run",
#           "label": "本步实现",
#           "from": "# @flow-anchor scale",
#           "until": "# @flow-anchor fit"
#         }
#       ],
#       "id": 5,
#       "primarySource": 0
#     },
#     {
#       "name": "汇总结果",
#       "description": "汇总三个估计参数、概率图拟合优度和本次求解状态。",
#       "formula": {
#         "equations": [
#           "R^2=1-\\frac{\\sum_i(y_i-\\hat y_i)^2}{\\sum_i(y_i-\\bar y)^2}",
#           "y_i=\\ln[-\\ln(1-p_i)]",
#           "\\hat y_i=\\beta\\ln(t_i-\\gamma)-\\beta\\ln\\eta"
#         ],
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
#         ]
#       },
#       "inputs": [
#         {
#           "code": "found_gamma",
#           "symbol": "\\hat\\gamma",
#           "meaning": "偏移判据选出的位置"
#         },
#         {
#           "code": "found_beta",
#           "symbol": "\\hat\\beta",
#           "meaning": "在选定位置下采纳的形状"
#         },
#         {
#           "code": "found_eta",
#           "symbol": "\\hat{\\eta}",
#           "meaning": "尺度参数估计值"
#         }
#       ],
#       "outputs": [
#         {
#           "code": "return",
#           "symbol": "R^2",
#           "meaning": "概率图决定系数"
#         },
#         {
#           "code": "return",
#           "symbol": "(\\hat\\beta,\\hat\\eta,\\hat\\gamma,R^2)",
#           "meaning": "本次三参数、拟合优度和状态"
#         }
#       ],
#       "basis": "项目诊断：共用基础类的概率图 R²，不参与核心参数求解。",
#       "notes": "γ触及样本最小值或总平方和为零时返回0；普通情况下允许负R²。",
#       "sources": [
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run",
#           "from": "r2 = self._calculate_r2(",
#           "through": "r2 = self._calculate_r2("
#         },
#         {
#           "file": "python/base.py",
#           "symbol": "WeibullBase._calculate_r2"
#         },
#         {
#           "file": "python/methods/mdm.py",
#           "symbol": "MDM.run",
#           "from": "return float(found_beta)",
#           "through": "return float(found_beta)",
#           "label": "返回三参数与状态"
#         }
#       ],
#       "id": 6,
#       "primarySource": 1
#     }
#   ],
#   "presentation": "steps",
#   "workflow": {
#     "title": "MDM 计算流程",
#     "description": "准备样本，试算各位置的最小差异，按梯度偏移求位置，回代求形状，反算尺度，汇总结果。",
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
#       1,
#       2,
#       2,
#       3,
#       3,
#       3,
#       5,
#       6,
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
#                 "待输入"
#               ],
#               "ready": [
#                 "n = {count}"
#               ]
#             }
#           },
#           {
#             "kind": "port",
#             "anchor": "offset",
#             "target": "location",
#             "direction": "input",
#             "label": "梯度偏移 δ",
#             "text": {
#               "default": [
#                 "{offset}"
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
#             "step": 1,
#             "anchor": "prepare",
#             "target": "samples",
#             "text": {
#               "default": [
#                 "排序并计算经验概率"
#               ]
#             }
#           }
#         ]
#       },
#       {
#         "kind": "group",
#         "layout": "search",
#         "children": [
#           {
#             "kind": "group",
#             "layout": "searchContent",
#             "children": [
#               {
#                 "kind": "step",
#                 "step": 2,
#                 "anchor": "trial",
#                 "target": "trial",
#                 "text": {
#                   "default": [
#                     "固定各试算 γ 求最小差异"
#                   ]
#                 }
#               },
#               {
#                 "kind": "group",
#                 "layout": "module",
#                 "children": [
#                   {
#                     "kind": "step",
#                     "step": 3,
#                     "anchor": "location",
#                     "target": "location",
#                     "text": {
#                       "default": [
#                         "由梯度和 δ 定位"
#                       ],
#                       "ready": [
#                         "按梯度偏移采纳位置"
#                       ],
#                       "zero": [
#                         "g(0) ≥ δ，取零位置"
#                       ],
#                       "extrapolated": [
#                         "右端回退 · 近似"
#                       ]
#                     }
#                   },
#                   {
#                     "kind": "port",
#                     "anchor": "gamma",
#                     "target": "location",
#                     "direction": "output",
#                     "label": "位置 γ̂"
#                   }
#                 ]
#               }
#             ]
#           }
#         ],
#         "title": "位置搜索 · 2–3 步",
#         "sideLabel": "换 γ 求值"
#       },
#       {
#         "kind": "group",
#         "layout": "scale",
#         "children": [
#           {
#             "kind": "group",
#             "layout": "module",
#             "children": [
#               {
#                 "kind": "step",
#                 "step": 4,
#                 "anchor": "shape",
#                 "target": "shape",
#                 "text": {
#                   "default": [
#                     "固定 γ̂ 取条件最小点"
#                   ]
#                 }
#               },
#               {
#                 "kind": "port",
#                 "anchor": "beta",
#                 "target": "shape",
#                 "direction": "output",
#                 "label": "形状 β̂"
#               }
#             ]
#           },
#           {
#             "kind": "group",
#             "layout": "module",
#             "children": [
#               {
#                 "kind": "step",
#                 "step": 5,
#                 "anchor": "scale",
#                 "target": "scale",
#                 "text": {
#                   "default": [
#                     "用 tᵢ、xᵢ、γ̂、β̂ 反算并取均值"
#                   ]
#                 }
#               },
#               {
#                 "kind": "port",
#                 "anchor": "eta",
#                 "target": "scale",
#                 "direction": "output",
#                 "label": "尺度 η̂"
#               }
#             ]
#           },
#           {
#             "kind": "step",
#             "step": 6,
#             "anchor": "result",
#             "target": "result",
#             "text": {
#               "default": [
#                 "用 γ̂、β̂、η̂ 计算 R²"
#               ]
#             }
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
#         "to": "trial",
#         "label": "tᵢ、xᵢ"
#       },
#       {
#         "from": "trial",
#         "to": "location",
#         "label": "(γⱼ, s(γⱼ))"
#       },
#       {
#         "from": "offset",
#         "to": "location",
#         "route": "right-upper",
#         "dashed": true
#       },
#       {
#         "from": "location",
#         "to": "trial",
#         "route": "loop"
#       },
#       {
#         "from": "gamma",
#         "to": "shape"
#       },
#       {
#         "from": "beta",
#         "to": "scale"
#       },
#       {
#         "from": "eta",
#         "to": "result"
#       }
#     ]
#   }
# }
# @end-method-flow
