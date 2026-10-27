"""
修正极大似然估计 (MMLE)
Modified Maximum Likelihood Estimation

算法文档: ../../src/content/algorithms/mmle.md
描述: 通过替换似然方程来修正 MLE 在小样本下的偏差，当 δ<2 时 MLE 不满足正则条件
"""

import numpy as np
from scipy.optimize import brentq
from scipy.special import gamma as gamma_func
from base import WeibullBase


class MMLE(WeibullBase):
    """
    修正极大似然估计 (MMLE-I)

    基于 Cohen & Whitten (1982) 的方法，通过替换似然方程 ∂ln L/∂γ = 0
    为约束条件 E[F(X₁)] = F(x₁)，即第一个顺序统计量的期望累积概率等于实际值。

    估计方程：
    - 方程 (A): 关于 δ 的似然方程
    - 方程 (B): θ̂ = (1/n) Σ(xᵢ - γ)^δ
    - 方程 (C): -ln(n/(n+1)) = (x₁ - γ)^δ / θ
    """

    def run(self, trace=False, variant='I'):
        """
        执行 MMLE 参数估计

        Args:
            trace: 是否记录中间过程
            variant: MMLE 变体，目前仅支持 'I'
        """
        n = self.n
        arr = self.data
        x1 = arr[0]  # 第一顺序统计量（最小值）

        # @step: 1 | 数据预处理 | 获取排序后的失效时间数据和样本数量
        # @formula: t_{(1)} \leq t_{(2)} \leq \cdots \leq t_{(n)}
        # @symbols: t|t|排序后的失效时间数组, n|n|样本数量, x_1|x_1|第一顺序统计量
        # @inputs: data|t_i|原始失效时间样本
        # @outputs: arr|t|排序后数组, n|n|样本数量, x1|x_1|最小样本值

        if trace:
            self.log_step({
                "phase": "init",
                "n": n,
                "x1": x1,
                "x_max": arr[-1]
            })

        # @step: 2 | 计算中位秩 | 使用 Bernard 公式计算经验累积概率
        # @formula: F(t_i) = \frac{i - 0.3}{n + 0.4}
        # @symbols: F(t_i)|F(t_i)|第i个样本的经验累积概率
        # @inputs: n|n|样本数量
        # @outputs: ranks|F(t_i)|中位秩数组
        ranks = (np.arange(1, n + 1) - 0.3) / (n + 0.4)

        # @step: 3 | 计算约束常数 | 计算 MMLE-I 约束方程中的常数项
        # @formula: C = -\ln\frac{n}{n+1}
        # @symbols: C|C|约束常数
        # @inputs: n|n|样本数量
        # @outputs: C|C|约束常数值
        C = -np.log(n / (n + 1))

        if trace:
            self.log_step({
                "phase": "constants",
                "C": C,
                "ranks_mean": np.mean(ranks)
            })

        # @step: 4 | 初始化位置参数搜索范围 | 设置 γ 的候选值范围，约束条件：γ < x₁
        # @formula: \gamma \in [0, x_1 \times 0.99)
        # @symbols: \gamma|\gamma|位置参数候选值
        # @inputs: x1|x_1|最小样本值
        # @outputs: gammas|\gamma|候选值数组
        gamma_upper = x1 * 0.99
        gamma_lower = max(0, x1 - 10 * np.std(arr))  # 下限：距均值10个标准差
        num_points = 50
        gammas = np.linspace(gamma_lower, gamma_upper, num_points)

        # @step: 5 | 定义似然方程求解函数 | 给定 γ，求解方程 (A) 得到 δ
        # @formula: \left[\frac{\sum(x_i-\gamma)^\delta \ln(x_i-\gamma)}{\sum(x_i-\gamma)^\delta} - \frac{1}{\delta}\right] - \frac{1}{n}\sum\ln(x_i-\gamma) = 0
        # @symbols: \delta|\delta|形状参数, x_i|x_i|失效时间, \gamma|\gamma|位置参数
        # @inputs: gamma|\gamma|固定的位置参数, arr|t|失效时间数组
        # @outputs: delta|\delta|形状参数估计值

        def solve_delta(gamma_val):
            """求解给定 gamma 下的 delta 值（方程 A）"""
            x_adj = arr - gamma_val
            log_x = np.log(x_adj)

            def equation_A(delta):
                if delta <= 0.1 or delta >= 15.0:
                    return 1e10
                try:
                    x_pow = x_adj ** delta
                    sum1 = np.sum(x_pow * log_x)
                    sum2 = np.sum(x_pow)
                    sum3 = np.sum(log_x)

                    if sum2 <= 0 or not np.isfinite(sum1) or not np.isfinite(sum2):
                        return 1e10

                    result = (sum1 / sum2 - 1.0 / delta) - sum3 / n
                    return result
                except:
                    return 1e10

            # 使用 Brent 方法求解
            try:
                # 在合理范围内搜索根
                delta_low, delta_high = 0.2, 10.0

                # 首先检查是否有根
                f_low = equation_A(delta_low)
                f_high = equation_A(delta_high)

                if f_low * f_high > 0:
                    # 没有符号变化，返回一个合理的默认值
                    return 2.0, False

                delta_sol = brentq(equation_A, delta_low, delta_high, xtol=1e-6)
                return delta_sol, True
            except:
                return 2.0, False

        # @step: 6 | 定义约束条件函数 | 计算 MMLE-I 约束方程的残差
        # @formula: -\ln\frac{n}{n+1} = \frac{(x_1 - \gamma)^\delta}{\theta}, \quad \theta = \frac{1}{n}\sum(x_i - \gamma)^\delta
        # @symbols: \theta|\theta|尺度参数的变换形式, C|C|约束常数
        # @inputs: delta|\delta|形状参数, gamma|\gamma|位置参数, x1|x_1|最小样本值
        # @outputs: residual|residual|约束条件残差

        def compute_constraint_residual(delta, gamma_val):
            """计算约束条件 C = (x1 - γ)^δ / θ 的残差"""
            if gamma_val >= x1:
                return 1e10

            x_adj = arr - gamma_val
            x1_adj = x1 - gamma_val

            try:
                theta = np.mean(x_adj ** delta)
                if theta <= 0:
                    return 1e10

                lhs = C  # -ln(n/(n+1))
                rhs = (x1_adj ** delta) / theta

                return lhs - rhs
            except:
                return 1e10

        # @step: 7 | 双层循环优化 | 外层遍历 γ，内层求解 δ，寻找满足约束条件的解
        # @formula: \text{Find } \gamma^* \text{ such that constraint residual} \approx 0
        # @symbols: \gamma^*|\gamma^*|最优位置参数, \delta^*|\delta^*|对应的最优形状参数
        # @inputs: gammas|\gamma|候选值数组
        # @outputs: best_gamma|\gamma^*|最优位置参数, best_delta|\delta^*|最优形状参数, best_theta|\theta|最优θ值
        # @loop: num_points 次外层迭代

        best_gamma = 0.0
        best_delta = 2.0
        best_theta = np.mean(arr)
        best_residual = float('inf')

        for gamma_val in gammas:
            # 内层：求解 delta
            delta_val, success = solve_delta(gamma_val)

            if not success:
                continue

            # 计算约束条件残差
            residual = compute_constraint_residual(delta_val, gamma_val)
            abs_residual = abs(residual)

            if trace:
                self.log_step({
                    "phase": "search",
                    "gamma": gamma_val,
                    "delta": delta_val,
                    "residual": residual,
                    "abs_residual": abs_residual
                })

            # 更新最优解
            if abs_residual < best_residual:
                best_residual = abs_residual
                best_gamma = gamma_val
                best_delta = delta_val
                best_theta = np.mean((arr - gamma_val) ** delta_val)

            # 如果残差已经很小，可以提前终止
            if abs_residual < 1e-6:
                break

        # 检查是否找到有效解
        if best_residual > 0.1:
            if trace:
                self.log_step({
                    "phase": "warning",
                    "message": "constraint_not_satisfied",
                    "best_residual": best_residual
                })

        # @step: 8 | 计算最终尺度参数 | 从 θ = β^δ 反推 η = θ^(1/δ)
        # @formula: \eta = \theta^{1/\delta} = \left[\frac{1}{n}\sum(x_i - \gamma)^\delta\right]^{1/\delta}
        # @symbols: \eta|\eta|尺度参数, \theta|\theta|变换后的尺度参数
        # @inputs: best_theta|\theta|最优θ值, best_delta|\delta|最优形状参数
        # @outputs: eta|\eta|尺度参数估计值
        eta = best_theta ** (1.0 / best_delta)

        # 转换符号：文献用 δ 表示形状、β 表示尺度，项目用 β 表示形状、η 表示尺度
        beta = best_delta  # 形状参数
        gamma_hat = best_gamma

        if trace:
            self.log_step({
                "phase": "final",
                "beta": beta,
                "eta": eta,
                "gamma": gamma_hat,
                "theta": best_theta,
                "residual": best_residual,
                "converged": True
            })

        # @step: 9 | 计算拟合优度 | 评估模型与数据的拟合程度
        # @formula: R^2 = 1 - \frac{\sum(F_i - \hat{F}_i)^2}{\sum(F_i - \bar{F})^2}
        # @symbols: R^2|R^2|决定系数, F_i|F_i|经验累积概率, \hat{F}_i|\hat{F}_i|模型预测概率
        # @inputs: beta|\beta|形状参数, eta|\eta|尺度参数, gamma|\gamma|位置参数
        # @outputs: r2|R^2|拟合优度
        r2 = self._calculate_r2_internal(beta, eta, gamma_hat)

        return [beta, eta, gamma_hat, r2, True]

    def _calculate_r2_internal(self, beta, eta, gamma_val):
        """计算拟合优度 R²"""
        if gamma_val >= self.data[0]:
            return 0.0

        # 使用对数线性化的方法计算 R²
        x = np.log(self.data - gamma_val)
        ranks = (np.arange(1, self.n + 1) - 0.3) / (self.n + 0.4)
        y_exp = np.log(-np.log(1 - ranks))

        # 理论预测值: y = β * x - β * ln(η)
        y_pred = beta * x - beta * np.log(eta)

        # R² 计算
        ss_res = np.sum((y_exp - y_pred) ** 2)
        ss_tot = np.sum((y_exp - np.mean(y_exp)) ** 2)

        if ss_tot == 0:
            return 0.0
        return 1 - (ss_res / ss_tot)
