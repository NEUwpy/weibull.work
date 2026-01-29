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
                "eta_guess": eta_init
            })

        # 2. 对数似然函数
        def neg_log_likelihood(params):
            beta, eta, gamma_val = params
            
            # 严格约束
            if beta <= 0.01 or eta <= 0.01: return 1e10
            if gamma_val >= arr[0] - 1e-6: return 1e10
            if gamma_val < 0: return 1e10 # 通常假设gamma>=0，除非数据有负值

            try:
                x_adj = arr - gamma_val
                # 归一化以防止溢出: z = x_adj / eta
                z = x_adj / eta
                
                # LL = n*ln(beta) - n*ln(eta) + (beta-1)*sum(ln(z)) - sum(z^beta)
                # Neg LL = -LL
                term1 = n * np.log(beta)
                term2 = -n * np.log(eta)
                term3 = (beta - 1) * np.sum(np.log(z))
                term4 = -np.sum(z ** beta)
                
                ll = term1 + term2 + term3 + term4
                if not np.isfinite(ll): return 1e10
                return -ll
            except:
                return 1e10

        # 回调
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
        # Nelder-Mead 对初值不敏感且不需要梯度，适合这种非凸问题
        result = minimize(
            neg_log_likelihood, 
            [beta_init, eta_init, gamma_init], 
            method='Nelder-Mead',
            callback=callback if trace else None,
            options={'maxiter': 1000, 'xatol': 1e-4}
        )
        
        # 如果 gamma 收敛到负数，尝试固定 gamma=0 重跑 (2P-Weibull)
        if result.x[2] < 1e-5:
             result.x[2] = 0.0

        beta_hat, eta_hat, gamma_hat = result.x
        
        # 最终 R2
        r2 = self._calculate_r2(beta_hat, eta_hat, gamma_hat)
        
        return [beta_hat, eta_hat, gamma_hat, r2]
