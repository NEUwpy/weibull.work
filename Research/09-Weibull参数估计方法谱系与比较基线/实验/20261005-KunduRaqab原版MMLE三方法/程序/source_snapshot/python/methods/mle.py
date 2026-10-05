"""
极大似然估计 (MLE)
Maximum Likelihood Estimation

算法文档: ../../src/content/algorithms/mle.md
描述: 通过最大化对数似然函数来估计威布尔分布参数
"""

import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class MLE(WeibullBase):
    def run(self, trace=False):
        n = self.n
        arr = self.data

        # @step: 1 | 数据预处理 | 获取排序后的失效时间数据和样本数量
        # @formula: t_{(1)} \leq t_{(2)} \leq \cdots \leq t_{(n)}
        # @symbols: t|t|排序后的失效时间数组, n|n|样本数量
        # @inputs: data|t_i|原始失效时间样本
        # @outputs: arr|t|排序后数组, n|n|样本数量

        # @step: 2 | 计算中位秩 | 使用 Bernard 公式计算经验累积概率
        # @formula: F(t_i) = \frac{i - 0.3}{n + 0.4}
        # @symbols: F(t_i)|F(t_i)|第i个样本的经验累积概率
        # @inputs: n|n|样本数量
        # @outputs: F|F(t_i)|中位秩数组
        F = (np.arange(1, n + 1) - 0.3) / (n + 0.4)

        # @step: 3 | 线性变换与初值估计 | 对数线性化后通过线性回归获得参数初始估计
        # @formula: Y = \ln(-\ln(1-F)), \quad X = \ln(t), \quad \beta_0 = \text{slope}, \quad \eta_0 = e^{-\text{intercept}/\text{slope}}
        # @symbols: Y|Y|变换后的响应变量, X|X|对数化的失效时间, \beta_0|\beta_0|形状参数初始值, \eta_0|\eta_0|尺度参数初始值
        # @inputs: F|F(t_i)|中位秩数组, arr|t|失效时间数组
        # @outputs: beta_init|\beta_0|形状参数初始值, eta_init|\eta_0|尺度参数初始值, gamma_init|\gamma_0|位置参数初始值
        try:
            y = np.log(-np.log(1 - F))
            x = np.log(arr)
            slope, intercept = np.polyfit(x, y, 1)
            beta_init = max(0.5, slope)
            eta_init = np.exp(-intercept / slope)
            gamma_init = 0.0
        except:
            beta_init = 1.0
            eta_init = np.mean(arr)
            gamma_init = 0.0

        if trace:
            self.log_step({
                "phase": "init",
                "beta_guess": beta_init,
                "eta_guess": eta_init,
                "gamma_guess": gamma_init
            })

        # @step: 4 | 定义对数似然函数 | 构造三参数威布尔分布的对数似然函数
        # @formula: \ell(\beta,\eta,\gamma) = n\ln\beta - n\ln\eta + (\beta-1)\sum\ln z_i - \sum z_i^{\beta}
        # @symbols: \ell|\ell|对数似然函数值, z_i|z_i|标准化变量 z_i = (t_i-\gamma)/\eta
        # @inputs: beta|\beta|形状参数, eta|\eta|尺度参数, gamma|\gamma|位置参数
        # @outputs: neg_ll|- \ell|负对数似然值
        def neg_log_likelihood(params):
            beta, eta, gamma_val = params

            # 约束检查
            if beta <= 0.01 or eta <= 0.01:
                return 1e10
            if gamma_val < 0:
                return 1e10
            if gamma_val >= arr[0]:
                return 1e10

            try:
                x_adj = arr - gamma_val
                z = x_adj / eta
                ll = (n * np.log(beta) - n * np.log(eta) +
                      (beta - 1) * np.sum(np.log(z)) -
                      np.sum(z ** beta))
                if not np.isfinite(ll):
                    return 1e10
                return -ll
            except:
                return 1e10

        # 回调函数（记录优化过程）
        def callback(xk):
            if trace:
                val = neg_log_likelihood(xk)
                self.log_step({
                    "step": len(self.trace_data) + 1,
                    "beta": xk[0],
                    "eta": xk[1],
                    "gamma": xk[2],
                    "log_likelihood": -val if val < 1e9 else None
                })

        # @step: 5 | 数值优化 | 使用 Nelder-Mead 无导数优化算法搜索最优参数
        # @formula: \{\hat{\beta}, \hat{\eta}, \hat{\gamma}\} = \arg\max_{\beta, \eta, \gamma} \ell(\beta, \eta, \gamma)
        # @symbols: \hat{\beta}|\hat{\beta}|形状参数估计值, \hat{\eta}|\hat{\eta}|尺度参数估计值, \hat{\gamma}|\hat{\gamma}|位置参数估计值
        # @inputs: beta_init|\beta_0|初始形状参数, eta_init|\eta_0|初始尺度参数, gamma_init|\gamma_0|初始位置参数
        # @outputs: beta_hat|\hat{\beta}|最优形状参数, eta_hat|\hat{\eta}|最优尺度参数, gamma_hat|\hat{\gamma}|最优位置参数
        # @loop: ~15-30次迭代
        # γ=0 的单一起点在位置参数为数千时可能停在二维边界附近的较差局部解。
        # 对若干尺度归一化的 γ 起点分别线性化初始化 β、η，再选择似然最大的有限局部极大。
        start_gammas = [0.0, 0.25 * arr[0], 0.5 * arr[0], 0.75 * arr[0], 0.9 * arr[0]]
        starts = []
        for gamma_start in start_gammas:
            try:
                shifted = arr - gamma_start
                x_start = np.log(shifted)
                slope_start, intercept_start = np.polyfit(x_start, y, 1)
                beta_start = max(0.5, float(slope_start))
                eta_start = float(np.exp(-intercept_start / slope_start))
                if np.isfinite(beta_start) and np.isfinite(eta_start) and eta_start > 0:
                    starts.append(np.array([beta_start, eta_start, gamma_start]))
            except Exception:
                continue

        candidates = []
        saw_unbounded = False
        for start_index, start in enumerate(starts):
            result = minimize(
                neg_log_likelihood,
                start,
                method='Nelder-Mead',
                callback=callback if trace else None,
                options={'maxiter': 3000, 'xatol': 1e-7, 'fatol': 1e-10},
            )
            beta_candidate, eta_candidate, gamma_candidate = result.x
            final_ll_candidate = -float(result.fun)
            if (
                np.isfinite(final_ll_candidate)
                and final_ll_candidate > -1e10
                and eta_candidate > 0
                and 0 <= gamma_candidate < arr[0]
            ):
                if beta_candidate < 1.0:
                    saw_unbounded = True
                elif result.success:
                    candidates.append((result, start_index))

        if not candidates:
            status = "unbounded" if saw_unbounded else "optimizer_failed"
            if status == "optimizer_failed":
                self.last_solution_info = {
                    "status": status,
                    "strategy": "deterministic_multistart_likelihood",
                    "start_count": int(len(starts)),
                }
            if trace:
                self.log_step({
                    "phase": "failed",
                    "reason": status,
                })
            return [0, 0, 0, 0, status]

        result, selected_start = min(candidates, key=lambda item: float(item[0].fun))
        beta_hat, eta_hat, gamma_hat = result.x
        final_ll = -float(result.fun)

        # 成功
        if trace:
            self.log_step({
                "phase": "final",
                "beta": beta_hat,
                "eta": eta_hat,
                "gamma": gamma_hat,
                "log_likelihood": final_ll,
                "converged": True
            })

        # 如果 gamma 收敛到接近 0，固定为 0
        if gamma_hat < 1e-5:
            gamma_hat = 0.0

        self.last_solution_info = {
            "status": "ok",
            "strategy": "deterministic_multistart_likelihood",
            "start_count": int(len(starts)),
            "selected_start": int(selected_start),
            "log_likelihood": float(final_ll),
            "location_at_zero_boundary": bool(gamma_hat == 0.0),
        }

        # @step: 7 | 计算拟合优度 | 评估模型与数据的拟合程度
        # @formula: R^2 = 1 - \frac{\sum(F_i - \hat{F}_i)^2}{\sum(F_i - \bar{F})^2}
        # @symbols: R^2|R^2|决定系数, F_i|F_i|经验累积概率, \hat{F}_i|\hat{F}_i|模型预测概率
        # @inputs: beta_hat|\hat{\beta}|形状参数, eta_hat|\hat{\eta}|尺度参数, gamma_hat|\hat{\gamma}|位置参数
        # @outputs: r2|R^2|拟合优度
        r2 = self._calculate_r2(beta_hat, eta_hat, gamma_hat)

        return [beta_hat, eta_hat, gamma_hat, r2, True]
