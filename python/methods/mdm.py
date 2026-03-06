"""
最小差异法 (MDM)
Minimum Discrepancy Method

算法文档: ../../src/content/algorithms/mdm.md
描述: 通过最小化伪尺度参数的标准差来估计参数，引入梯度偏移判据提高稳健性
"""

from base import WeibullBase
import numpy as np
from scipy.optimize import minimize_scalar

class MDM(WeibullBase):
    def run(self, trace=False, offset=None, gamma_steps=60, rank_method='bernard'):
        """
        Run the Minimum Discrepancy Method.

        Args:
            trace (bool): Whether to record trace data.
            offset (float): Gradient offset target (required, e.g., 0.1).
            gamma_steps (int): Number of steps per round for gamma search (default 60).
            rank_method (str): Median rank method - 'bernard' or 'exact' (default 'bernard').

        Returns:
            (beta, eta, gamma, r_squared, status) where status is True or "no_intersection"
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

        # @step: 5 | 初始化搜索范围 | 设置 γ 的候选值范围，约束条件：γ < t_min
        # @formula: \gamma \in [0, t_{\min} \times 0.99)
        # @symbols: t_{\min}|t_{\min}|最小失效时间, gamma_steps|N|搜索步数
        # @inputs: t|t|失效时间数组
        # @outputs: t_min|t_{\min}|最小失效时间
        t_min = t[0]

        # @step: 6 | 第一轮搜索 | 在 [0, 0.99*t_min] 范围内遍历 γ，记录每个 γ 对应的最小标准差和最优 β
        # @formula: \sigma_{\min}(\gamma) = \min_\beta \sigma_\eta(\beta, \gamma)
        # @loop: gamma_steps 次 (默认 60)
        # @inputs: t_min|t_{\min}|最小失效时间, gamma_steps|N|搜索步数
        # @outputs: gammas1|\gamma|γ候选值数组, sigma_mins1|\sigma_{min}|最小标准差数组, best_betas1|\beta^*|最优β数组
        gammas1 = np.linspace(0, t_min * 0.99, gamma_steps)
        sigma_mins1 = []
        best_betas1 = []

        for g in gammas1:
            b, sig = find_best_beta_for_gamma(g)
            sigma_mins1.append(sig)
            best_betas1.append(b)

        sigma_mins1 = np.array(sigma_mins1)
        best_betas1 = np.array(best_betas1)

        # @step: 7 | 计算第一轮梯度 | 计算 σ_min(γ) 关于 γ 的数值梯度
        # @formula: \nabla(\gamma) = \frac{\partial \sigma_{\min}(\gamma)}{\partial \gamma} \approx \frac{\Delta \sigma_{\min}}{\Delta \gamma}
        # @symbols: \nabla(\gamma)|\nabla|梯度值
        # @inputs: sigma_mins1|\sigma_{min}|标准差数组, gammas1|\gamma|γ数组
        # @outputs: grads1|\nabla|梯度数组
        grads1 = np.gradient(sigma_mins1, gammas1)

        # @step: 8 | 检查第一轮交点 | 检查梯度曲线与偏移阈值是否有交点
        # @formula: \text{sign\_changes} = \{i : \text{sign}(\nabla_i - \delta) \neq \text{sign}(\nabla_{i+1} - \delta)\}
        # @symbols: \delta|\delta|偏移阈值(offset)
        # @inputs: grads1|\nabla|梯度数组, offset|\delta|偏移阈值
        # @outputs: sign_changes|I|交点索引数组
        diffs1 = grads1 - offset
        sign_changes = np.where(np.diff(np.sign(diffs1)))[0]

        # @step: 9 | 第二轮搜索 | 若第一轮无交点，在 [0.99*t_min, 0.999999*t_min] 范围内继续搜索
        # @formula: \gamma \in [0.99 t_{\min}, 0.999999 t_{\min})
        # @loop: gamma_steps 次
        # @inputs: t_min|t_{\min}|最小失效时间, sign_changes|I|交点索引
        # @outputs: gammas|\gamma|合并后的γ数组, sigma_mins|\sigma_{min}|合并后的标准差数组, best_betas|\beta^*|合并后的β数组, grads|\nabla|合并后的梯度数组
        if len(sign_changes) == 0:
            gammas2 = np.linspace(t_min * 0.99, t_min * 0.999999, gamma_steps)
            sigma_mins2 = []
            best_betas2 = []

            for g in gammas2:
                b, sig = find_best_beta_for_gamma(g)
                sigma_mins2.append(sig)
                best_betas2.append(b)

            sigma_mins2 = np.array(sigma_mins2)
            best_betas2 = np.array(best_betas2)
            grads2 = np.gradient(sigma_mins2, gammas2)

            # 合并两轮数据
            gammas = np.concatenate([gammas1, gammas2])
            sigma_mins = np.concatenate([sigma_mins1, sigma_mins2])
            best_betas = np.concatenate([best_betas1, best_betas2])
            grads = np.concatenate([grads1, grads2])

            # 重新检查交点
            diffs = grads - offset
            sign_changes = np.where(np.diff(np.sign(diffs)))[0]
        else:
            # 使用第一轮数据
            gammas = gammas1
            sigma_mins = sigma_mins1
            best_betas = best_betas1
            grads = grads1
            diffs = diffs1

        # @step: 10 | 线性插值求交点 | 使用线性插值找到梯度等于偏移值的精确 γ 值
        # @formula: \gamma^* = \gamma_i - (\nabla_i - \delta) \cdot \frac{\gamma_{i+1} - \gamma_i}{\nabla_{i+1} - \nabla_i}
        # @symbols: \gamma^*|\gamma^*|最优位置参数
        # @inputs: gammas|\gamma|γ数组, diffs|\nabla-\delta|梯度差值数组, sign_changes|I|交点索引
        # @outputs: found_gamma|\gamma^*|最优γ值
        found_gamma = 0.0
        found_beta = 1.0

        if len(sign_changes) > 0:
            # 选择最接近 t_min 的交点（通常更大的 gamma 更适合 3P 拟合）
            idx = sign_changes[-1]
            y1, y2 = diffs[idx], diffs[idx+1]
            x1, x2 = gammas[idx], gammas[idx+1]

            # 线性插值
            if y2 != y1:
                found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
            else:
                found_gamma = x1

            found_beta, _ = find_best_beta_for_gamma(found_gamma)
        else:
            # 两轮搜索后仍未找到交点 - 返回无解
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
                "optimal_gamma": found_gamma,
                "optimal_beta": found_beta
            }

        return float(found_beta), float(found_eta), float(found_gamma), float(r2), True
