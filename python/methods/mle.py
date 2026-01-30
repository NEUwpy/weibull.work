"""
极大似然估计 (MLE)
Maximum Likelihood Estimation

算法文档: ../../src/content/algorithms/mle.md
描述: 通过最大化对数似然函数来估计参数。
"""

import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class MLE(WeibullBase):
    def run(self, trace=False):
        n = self.n
        arr = self.data

        # 1. 更稳健的初始猜测 (使用 LRE 逻辑快速估算)
        # y = ln(-ln(1-F)) = beta*ln(x) - beta*ln(eta) (假设 gamma=0)
        try:
            F = (np.arange(1, n + 1) - 0.3) / (n + 0.4)
            y = np.log(-np.log(1 - F))
            x = np.log(arr)
            # 简单的线性回归求斜率(beta)
            slope, intercept = np.polyfit(x, y, 1)
            beta_init = max(0.5, slope)
            eta_init = np.exp(-intercept / slope)
            gamma_init = 0.0
        except:
            # Fallback if fit fails
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

        # 2. 对数似然函数（三参数威布尔）
        def neg_log_likelihood(params):
            beta, eta, gamma_val = params

            # 标准约束
            if beta <= 0.01 or eta <= 0.01:
                return 1e10
            if gamma_val < 0:
                return 1e10
            # Smith (1985): gamma 必须严格小于最小数据点
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

        # 3. 优化
        result = minimize(
            neg_log_likelihood,
            [beta_init, eta_init, gamma_init],
            method='Nelder-Mead',
            callback=callback if trace else None,
            options={'maxiter': 1000, 'xatol': 1e-4, 'fatol': 1e-8}
        )

        beta_hat, eta_hat, gamma_hat = result.x
        final_ll = -result.fun

        # 检查对数似然值是否有效
        if not np.isfinite(final_ll) or final_ll <= -1e10:
            if trace:
                self.log_step({
                    "phase": "failed",
                    "reason": "invalid_likelihood",
                    "log_likelihood": final_ll
                })
            return [0, 0, 0, 0, False]

        # 检测 Smith (1985) 无界问题
        # 当 beta < 1 时，似然函数在参数空间内无界（趋向 +∞）
        # 因此不存在最大似然估计，无解
        if beta_hat < 1.0:
            if trace:
                self.log_step({
                    "phase": "failed",
                    "reason": "unbounded_problem",
                    "message": "Smith (1985): beta < 1, likelihood function is unbounded, no MLE solution exists",
                    "beta": beta_hat
                })
            # 无界问题：不返回任何有效参数
            return [0, 0, 0, 0, "unbounded"]

        # 检查收敛状态
        if not result.success:
            if trace:
                self.log_step({
                    "phase": "failed",
                    "reason": "optimization_failed",
                    "message": result.message
                })
            return [0, 0, 0, 0, False]

        # 5. 成功
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

        # 最终 R2
        r2 = self._calculate_r2(beta_hat, eta_hat, gamma_hat)

        return [beta_hat, eta_hat, gamma_hat, r2, True]
