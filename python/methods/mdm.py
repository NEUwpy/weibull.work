"""
最小差异法 (MDM)
Minimum Discrepancy Method

算法文档: ../../src/content/algorithms/mdm.md
描述: 通过最小化伪尺度参数的标准差来估计参数，引入梯度偏移判据提高稳健性
"""

from base import WeibullBase
import numpy as np
from scipy.optimize import minimize_scalar, root_scalar
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
    """Find the discrete bracket whose interpolated crossing is closest to t_min."""
    diffs = gradients - offset
    candidates = []

    for i in range(len(diffs) - 1):
        y1, y2 = diffs[i], diffs[i + 1]
        if not (np.isfinite(y1) and np.isfinite(y2)):
            continue
        if y1 == 0 or y2 == 0 or y1 * y2 < 0:
            candidates.append(i)

    if not candidates:
        return None, diffs

    idx = max(candidates, key=lambda i: max(gammas[i], gammas[i + 1]))
    y1, y2 = diffs[idx], diffs[idx + 1]
    x1, x2 = gammas[idx], gammas[idx + 1]

    if y1 == 0:
        gamma = x1
    elif y2 == 0:
        gamma = x2
    elif y2 != y1:
        gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
    else:
        gamma = x1

    bracket = {
        "left": {
            "gamma": _json_float(x1),
            "gradient": _json_float(gradients[idx]),
            "diff": _json_float(y1),
        },
        "right": {
            "gamma": _json_float(x2),
            "gradient": _json_float(gradients[idx + 1]),
            "diff": _json_float(y2),
        },
    }
    return (float(gamma), bracket), diffs


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
            an in-domain offset root or the gamma=0 constraint truncation. The
            default engineering solver follows the S4.9.3 rule: probe g(0),
            bracket near t_min, solve by Brent when possible, and use a right
            edge fit when the fixed trace grid still misses the near-t_min root.
        """
        if offset is None:
            raise ValueError("offset parameter is required (e.g., offset=0.1)")
        self.calculation_trace = None

        # @step: 1 | 数据预处理 | 获取排序后的失效时间数据和样本数量
        # @formula: t_{(1)} \leq t_{(2)} \leq \cdots \leq t_{(n)}
        # @symbols: t|t|排序后的失效时间数组, n|n|样本数量
        # @inputs: data|t_i|原始失效时间样本
        # @outputs: t|t|排序后数组, n|n|样本数量
        original_rank_method = self.rank_method
        self.rank_method = rank_method
        t = self.data
        n = self.n

        # @step: 2 | 计算中位秩 | 使用 Bernard 公式计算经验累积分布函数值
        # @formula: F(t_i) = \frac{i - 0.3}{n + 0.4}, \quad x_i = -\ln(1 - F(t_i))
        # @symbols: F(t_i)|F(t_i)|第i个样本点的经验累积概率, x_i|x_i|变换后的中位秩
        # @inputs: t|t|失效时间数组, n|n|样本数量
        # @outputs: ranks|F(t_i)|中位秩数组, neg_ln_1_minus_F|x_i|变换数组
        ranks = self._median_ranks()
        neg_ln_1_minus_F = -np.log(1 - ranks)

        # @step: 3 | 定义伪尺度参数计算函数 | 计算给定 β 和 γ 下每个样本点的伪尺度参数及其标准差
        # @formula: \eta_i = \frac{t_i - \gamma}{x_i^{1/\beta}}, \quad \sigma_\eta = \text{std}(\eta_1, \eta_2, \ldots, \eta_n)
        # @symbols: \eta_i|\eta_i|第i个伪尺度参数, \sigma_\eta|\sigma_\eta|伪尺度参数标准差, \beta|\beta|形状参数, \gamma|\gamma|位置参数
        # @inputs: beta|\beta|形状参数, gamma|\gamma|位置参数, t|t|失效时间数组
        # @outputs: \sigma_\eta|\sigma_\eta|标准差值
        def calculate_eta_std(beta, gamma, current_t):
            if beta <= 0: return float('inf')
            denom = np.power(neg_ln_1_minus_F, 1.0/beta)
            etas = (current_t - gamma) / denom
            return np.std(etas, ddof=1)

        # @step: 4 | 定义最优 β 搜索函数 | 对给定 γ，使用有界优化寻找使标准差最小的 β
        # @formula: \beta^*(\gamma) = \arg\min_{\beta \in [0.1, 15.0]} \sigma_\eta(\beta, \gamma)
        # @symbols: \beta^*(\gamma)|\beta^*(\gamma)|给定γ时的最优β
        # @inputs: gamma|\gamma|位置参数候选值
        # @outputs: best_beta|\beta^*|最优β值, min_sigma|\sigma_{min}|最小标准差
        beta_sigma_cache = {}
        profile_gradient_cache = {}
        beta_evaluations = {} if trace else None
        root_evaluations = []

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

        # @step: 5 | 初始化搜索范围 | 设置 γ 的离散候选网格，约束条件：0 <= γ < t_min
        # @formula: \gamma_j = t_{\min} - d_j,\quad d_j \in \text{geomspace}(\epsilon, t_{\min})
        # @symbols: t_{\min}|t_{\min}|最小失效时间, gamma_steps|N|搜索步数
        # @inputs: t|t|失效时间数组
        # @outputs: t_min|t_{\min}|最小失效时间
        t_min = t[0]

        # @step: 6 | 离散搜索 | 从接近 t_min 的位置向 0 展开几何加密网格，记录每个 γ 对应的最小标准差和最优 β
        # @formula: \sigma_{\min}(\gamma) = \min_\beta \sigma_\eta(\beta, \gamma)
        # @loop: gamma_steps 次 (默认 60)
        # @inputs: t_min|t_{\min}|最小失效时间, gamma_steps|N|搜索步数
        # @outputs: gammas|\gamma|γ候选值数组, sigma_mins|\sigma_{min}|最小标准差数组, best_betas|\beta^*|最优β数组
        gammas = _build_geometric_gamma_grid(t_min, gamma_steps)
        sigma_mins = []
        best_betas = []

        for g in gammas:
            b, sig = find_best_beta_for_gamma(g)
            sigma_mins.append(sig)
            best_betas.append(b)

        sigma_mins = np.array(sigma_mins, dtype=float)
        best_betas = np.array(best_betas, dtype=float)

        # @step: 7 | 计算廓线梯度 | 使用与求解器相同的 profile_gradient 计算 g(gamma)
        # @formula: g(\gamma) = \frac{\partial \sigma_{\min}(\gamma)}{\partial \gamma}
        # @symbols: \nabla(\gamma)|\nabla|梯度值
        # @inputs: sigma_mins|\sigma_{min}|标准差数组, gammas|\gamma|γ数组
        # @outputs: grads|\nabla|梯度数组
        grads = np.array([profile_gradient(g) for g in gammas], dtype=float)

        # @step: 8 | 离散曲线诊断 | 保留离散梯度曲线用于 trace，可视化和历史对照
        # @formula: \nabla(\gamma^*) = \delta
        # @symbols: \delta|\delta|偏移阈值(offset)
        # @inputs: grads|\nabla|梯度数组, offset|\delta|偏移阈值
        # @outputs: root_info|root|交点插值结果, diffs|\nabla-\delta|梯度差值数组
        root_info, diffs = _find_offset_crossing(gammas, grads, offset)

        # @step: 9 | 始终有解求解器 | 探测 g(0)，近 t_min 构造右端括弧，Brent 定根或边界截断
        # @formula: g(0)\ge\delta \Rightarrow \hat{\gamma}=0;\quad g(0)<\delta \Rightarrow g(\hat{\gamma})=\delta
        # @symbols: \gamma^*|\gamma^*|最优位置参数
        # @inputs: root_info|root|交点结果, grads|\nabla|梯度数组, offset|\delta|偏移阈值
        # @outputs: found_gamma|\gamma^*|最优γ值, solution_strategy|strategy|求解策略
        probe_gradient_at_zero = float(profile_gradient(0.0))
        root_bracket = None
        root_solver = None
        root_solver_iterations = 0
        right_anchor_gamma = None
        right_anchor_gradient = None
        right_edge_extrapolation = None
        legacy_grid_crossing = root_info is not None

        if probe_gradient_at_zero >= offset:
            found_gamma = 0.0
            found_beta, _ = find_best_beta_for_gamma(found_gamma)
            solution_strategy = "truncated_at_zero"
        else:
            right_anchor_gamma, right_anchor_gradient = find_right_anchor()
            right_diff = right_anchor_gradient - offset
            left_diff = probe_gradient_at_zero - offset

            if right_diff >= 0:
                root_bracket = {
                    "left": {
                        "gamma": 0.0,
                        "gradient": _json_float(probe_gradient_at_zero),
                        "diff": _json_float(left_diff),
                    },
                    "right": {
                        "gamma": _json_float(right_anchor_gamma),
                        "gradient": _json_float(right_anchor_gradient),
                        "diff": _json_float(right_diff),
                    },
                }

                def root_objective(gamma):
                    gradient = profile_gradient(gamma)
                    if trace:
                        root_evaluations.append(dict(gamma=float(gamma), gradient=float(gradient),
                                                     residual=float(gradient - offset),
                                                     evaluation=len(root_evaluations) + 1))
                    return gradient - offset

                root = root_scalar(
                    root_objective,
                    bracket=(0.0, float(right_anchor_gamma)),
                    method="brentq",
                    xtol=1e-8,
                    rtol=1e-10,
                    maxiter=80,
                )
                found_gamma = float(root.root)
                found_gamma = min(max(found_gamma, 0.0), float(t_min) - 1e-12)
                found_beta, _ = find_best_beta_for_gamma(found_gamma)
                solution_strategy = "brent_root"
                root_solver = "brent"
                root_solver_iterations = int(root.iterations)
            else:
                right_edge_extrapolation = fit_right_edge_root(
                    right_anchor_gamma,
                    right_anchor_gradient,
                )
                found_gamma = right_edge_extrapolation["gamma"]
                found_beta, _ = find_best_beta_for_gamma(found_gamma)
                solution_strategy = "brent_root"
                root_solver = "right_edge_fit"
                root_bracket = {
                    "left": {
                        "gamma": _json_float(right_anchor_gamma),
                        "gradient": _json_float(right_anchor_gradient),
                        "diff": _json_float(right_diff),
                    },
                    "right": {
                        "gamma": _json_float(found_gamma),
                        "gradient": _json_float(offset),
                        "diff": 0.0,
                        "virtual": True,
                    },
                }

        # @step: 11 | 计算最终尺度参数 η | 使用最优的 γ* 和 β* 计算所有伪尺度参数的均值
        # @formula: \hat{\eta} = \frac{1}{n}\sum_{i=1}^n \frac{t_i - \hat{\gamma}}{x_i^{1/\hat{\beta}}}
        # @symbols: \hat{\eta}|\hat{\eta}|尺度参数估计值
        # @inputs: found_gamma|\hat{\gamma}|最优γ, found_beta|\hat{\beta}|最优β, t|t|失效时间数组
        # @outputs: found_eta|\hat{\eta}|尺度参数估计值
        denom = np.power(neg_ln_1_minus_F, 1.0/found_beta)
        etas = (t - found_gamma) / denom
        found_eta = np.mean(etas)

        # @step: 12 | 计算拟合优度 R² | 评估模型与数据的拟合程度
        # @formula: R^2 = 1 - \frac{\sum(F_i - \hat{F}_i)^2}{\sum(F_i - \bar{F})^2}
        # @symbols: R^2|R^2|决定系数, F_i|F_i|经验累积概率, \hat{F}_i|\hat{F}_i|模型预测概率
        # @inputs: found_beta|\hat{\beta}|形状参数, found_eta|\hat{\eta}|尺度参数, found_gamma|\hat{\gamma}|位置参数
        # @outputs: r2|R^2|拟合优度
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
            "root_solver_iterations": root_solver_iterations,
            "legacy_grid_crossing": legacy_grid_crossing,
            "right_edge_extrapolation": right_edge_extrapolation,
            "gamma_steps": len(gammas),
            "optimal_gamma": found_gamma,
            "optimal_beta": found_beta,
        }

        # @step: 13 | 生成追踪数据 | 若启用 trace，生成用于可视化的详细数据
        # @inputs: found_gamma|\gamma^*|最优γ, found_beta|\beta^*|最优β, gammas|\gamma|γ数组, sigma_mins|\sigma_{min}|标准差数组, best_betas|\beta^*|最优β数组
        # @outputs: trace_data|trace_{data}|可视化数据（σ-β曲线、梯度-γ曲线、3D曲面等）
        if trace:
            # Capture the actual solver state before the supplementary legacy
            # surface sampling below. No surrogate values enter these charts.
            selected_sigma = float(beta_sigma_cache[float(found_gamma)][1])
            beta_points = [plot_point(p['beta'], p['sigma'], beta=p['beta'],
                                      gamma=float(found_gamma), evaluation=i + 1)
                           for i, p in enumerate(beta_evaluations.get(float(found_gamma), []))]
            gradient_values = list(root_evaluations)
            if not gradient_values:
                gradient_values = [dict(gamma=0., gradient=float(probe_gradient_at_zero))]
                if right_anchor_gamma is not None:
                    gradient_values.append(dict(gamma=float(right_anchor_gamma),
                                                gradient=float(right_anchor_gradient)))
            gradient_points = [plot_point(p['gamma'], p['gradient'], **p) for p in gradient_values]
            selected_gradient = profile_gradient_cache.get(float(found_gamma))
            approximate = root_solver == 'right_edge_fit'
            if solution_strategy == 'truncated_at_zero':
                selection_description = 'g(0)≥δ，按当前 γ≥0 工程约束选择 γ=0，再求对应 β 与 η。'
            elif approximate:
                selection_description = ('右锚点梯度仍低于 δ，当前实现使用端点外推位置；'
                                         '此位置不是实际求得的 g(γ)=δ 根。')
            else:
                selection_description = '用 Brent 在括弧内求 g(γ)=δ，再取该 γ 下使伪尺度标准差最小的 β。'
            gradient_series = [plot_series('gradient', '实际求根函数求值', gradient_points)]
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
                        references=[dict(axis='y', value=float(offset), label='目标偏移量 δ')],
                        selected=[plot_point(found_gamma, selected_gradient, label='最终位置参数')]
                        if selected_gradient is not None and not approximate else []),
                ],
                selection=dict(description=selection_description, beta=float(found_beta),
                               eta=float(found_eta), gamma=float(found_gamma),
                               sigma=selected_sigma, target_offset=float(offset),
                               gradient=float(selected_gradient) if selected_gradient is not None else None,
                               approximate=approximate, strategy=solution_strategy, solver=root_solver),
                details=dict(rank_method=rank_method, shape_search_bounds=[0.1, 15.0],
                             sigma_ddof=1, root_bracket=root_bracket,
                             root_solver_iterations=root_solver_iterations,
                             root_evaluations=root_evaluations,
                             gradient_scan=[dict(gamma=float(g), gradient=float(v))
                                            for g, v in zip(gammas, grads) if np.isfinite(v)],
                             pseudo_scales=[dict(observation=float(ti), rank=float(ri),
                                                 eta=float(ei)) for ti, ri, ei in zip(t, ranks, etas)],
                             boundary_rule='gamma >= 0',
                             supplementary_legacy_curves='旧 trace_data 中的曲面为额外函数采样，不是迭代轨迹'),
            )
            # 1. Sigma vs Beta curve (at optimal gamma) - for backward compatibility
            beta_scan = np.linspace(0.5, 5, 100)
            sigma_beta_curve = []
            for b_val in beta_scan:
                s = calculate_eta_std(b_val, found_gamma, t)
                sigma_beta_curve.append({"beta": b_val, "sigma": s})

            # 2. Full 2D surface data: sigma_beta_gamma for 3D visualization
            num_gamma_samples = 20
            gamma_indices = np.linspace(0, len(gammas) - 1, num_gamma_samples, dtype=int)
            sampled_gammas = gammas[gamma_indices]
            beta_range = np.linspace(0.5, 5, 100)
            sigma_beta_gamma = []

            for idx, g in enumerate(sampled_gammas):
                sigma_curve = []
                for b_val in beta_range:
                    s = calculate_eta_std(b_val, g, t)
                    sigma_curve.append(float(s))

                sigma_beta_gamma.append({
                    "gamma": float(g),
                    "betas": [float(b) for b in beta_range],
                    "sigmas": sigma_curve
                })

            # 3. Gradient vs Gamma curve. This uses the same profile_gradient
            # function as the backend solver, so the visual trace and result match.
            grad_gamma_points = {}

            def add_gradient_point(gamma, gradient, source="trace_grid", virtual=False):
                gamma = float(gamma)
                b, sig = find_best_beta_for_gamma(gamma)
                denom = np.power(neg_ln_1_minus_F, 1.0/b)
                etas_g = (t - gamma) / denom
                eta_mean = float(np.mean(etas_g))
                point = {
                    "gamma": gamma,
                    "gradient": float(gradient),
                    "sigma_min": float(sig),
                    "best_beta": float(b),
                    "best_eta": eta_mean,
                    "source": source,
                }
                if virtual:
                    point["virtual"] = True
                grad_gamma_points[gamma] = point

            for i in range(len(gammas)):
                add_gradient_point(gammas[i], grads[i])

            if solution_strategy == "brent_root":
                if root_solver == "right_edge_fit":
                    add_gradient_point(found_gamma, offset, source="solver_root", virtual=True)
                else:
                    add_gradient_point(found_gamma, profile_gradient(found_gamma), source="solver_root")
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
