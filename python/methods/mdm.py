"""
最小差异法 (MDM)
Minimum Discrepancy Method

算法文档: ../../src/content/algorithms/mdm.md
描述: 通过最小化伪尺度参数的标准差来估计参数，引入梯度偏移判据提高稳健性
"""

from base import WeibullBase
import numpy as np
from scipy.optimize import minimize_scalar


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
            (beta, eta, gamma, r_squared, status) where status is True for a solved
            offset root or boundary truncation. "no_intersection" is retained only
            for extreme diagnostic cases where neither an in-domain root nor the
            gamma=0 truncation rule applies.
        """
        if offset is None:
            raise ValueError("offset parameter is required (e.g., offset=0.1)")

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
        def find_best_beta_for_gamma(gamma):
            if gamma >= t[0]:
                return None, float('inf')
            res = minimize_scalar(
                lambda b: calculate_eta_std(b, gamma, t),
                bounds=(0.1, 15.0),
                method='bounded'
            )
            return res.x, res.fun

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

        # @step: 7 | 计算离散梯度 | 计算 σ_min(γ) 关于 γ 的数值梯度
        # @formula: \nabla(\gamma) = \frac{\partial \sigma_{\min}(\gamma)}{\partial \gamma} \approx \frac{\Delta \sigma_{\min}}{\Delta \gamma}
        # @symbols: \nabla(\gamma)|\nabla|梯度值
        # @inputs: sigma_mins|\sigma_{min}|标准差数组, gammas|\gamma|γ数组
        # @outputs: grads|\nabla|梯度数组
        grads = np.gradient(sigma_mins, gammas)

        # @step: 8 | 检查 offset 交点 | 检查梯度曲线与偏移阈值是否有交点
        # @formula: \nabla(\gamma^*) = \delta
        # @symbols: \delta|\delta|偏移阈值(offset)
        # @inputs: grads|\nabla|梯度数组, offset|\delta|偏移阈值
        # @outputs: root_info|root|交点插值结果, diffs|\nabla-\delta|梯度差值数组
        root_info, diffs = _find_offset_crossing(gammas, grads, offset)

        # @step: 9 | 线性插值或边界截断 | 使用离散曲线交点确定 γ；若根被 γ>=0 约束切除，则取 γ=0
        # @formula: \gamma^* = \gamma_i - (\nabla_i - \delta) \cdot \frac{\gamma_{i+1} - \gamma_i}{\nabla_{i+1} - \nabla_i}
        # @symbols: \gamma^*|\gamma^*|最优位置参数
        # @inputs: root_info|root|交点结果, grads|\nabla|梯度数组, offset|\delta|偏移阈值
        # @outputs: found_gamma|\gamma^*|最优γ值, solution_strategy|strategy|求解策略
        zero_idx = int(np.argmin(np.abs(gammas)))
        probe_gradient_at_zero = float(grads[zero_idx])
        root_bracket = None

        if root_info is not None:
            found_gamma, root_bracket = root_info
            found_gamma = min(max(float(found_gamma), 0.0), float(t_min) - 1e-12)
            found_beta, _ = find_best_beta_for_gamma(found_gamma)
            solution_strategy = "offset_root"
        elif probe_gradient_at_zero >= offset:
            found_gamma = 0.0
            found_beta, _ = find_best_beta_for_gamma(found_gamma)
            solution_strategy = "truncated_at_zero"
        else:
            # 极端情形：默认 offset 下通常不会进入这里。保留显式状态，便于诊断过高 offset 或异常样本。
            if trace:
                self.trace_data = {
                    "grad_gamma_curve": [
                        {
                            "gamma": float(gammas[i]),
                            "gradient": float(grads[i]),
                            "sigma_min": float(sigma_mins[i]),
                            "best_beta": float(best_betas[i]),
                        }
                        for i in range(len(gammas))
                    ],
                    "target_offset": offset,
                    "search_strategy": "geometric_from_tmin",
                    "solution_strategy": "no_offset_root",
                    "constraint": "gamma >= 0",
                    "probe_gradient_at_zero": probe_gradient_at_zero,
                    "root_bracket": None,
                    "gamma_steps": int(max(4, int(gamma_steps))),
                    "optimal_gamma": None,
                    "optimal_beta": None,
                }
            return None, None, None, None, "no_intersection"

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

        # @step: 13 | 生成追踪数据 | 若启用 trace，生成用于可视化的详细数据
        # @inputs: found_gamma|\gamma^*|最优γ, found_beta|\beta^*|最优β, gammas|\gamma|γ数组, sigma_mins|\sigma_{min}|标准差数组, best_betas|\beta^*|最优β数组
        # @outputs: trace_data|trace_{data}|可视化数据（σ-β曲线、梯度-γ曲线、3D曲面等）
        if trace:
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

            # 3. Gradient vs Gamma curve
            grad_gamma_curve = []
            for i in range(len(gammas)):
                g = gammas[i]
                b = best_betas[i]
                denom = np.power(neg_ln_1_minus_F, 1.0/b)
                etas_g = (t - g) / denom
                eta_mean = float(np.mean(etas_g))

                grad_gamma_curve.append({
                    "gamma": float(g),
                    "gradient": float(grads[i]),
                    "sigma_min": float(sigma_mins[i]),
                    "best_beta": float(b),
                    "best_eta": eta_mean
                })

            self.trace_data = {
                "sigma_beta_curve": sigma_beta_curve,
                "grad_gamma_curve": grad_gamma_curve,
                "sigma_beta_gamma": sigma_beta_gamma,
                "target_offset": offset,
                "search_strategy": "geometric_from_tmin",
                "solution_strategy": solution_strategy,
                "constraint": "gamma >= 0",
                "probe_gradient_at_zero": probe_gradient_at_zero,
                "root_bracket": root_bracket,
                "gamma_steps": len(gammas),
                "optimal_gamma": found_gamma,
                "optimal_beta": found_beta
            }

        return float(found_beta), float(found_eta), float(found_gamma), float(r2), True
