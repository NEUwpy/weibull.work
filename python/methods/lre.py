"""
线性回归法 (LRE)
Linear Regression Estimation

算法文档: ../../src/content/algorithms/lre.md
描述: 最基础的工程方法。对威布尔公式进行线性化变换，通过最小二乘法拟合直线。
公式: ln(-ln(1-F)) = beta * ln(t-gamma) - beta * ln(eta)
"""

import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class LRE(WeibullBase):
    def run(self):
        """
        LRE 参数估计
        策略：
        1. 遍历寻找最佳 gamma，使得线性相关系数 R^2 最大。
        2. 固定 gamma 后，通过最小二乘法求斜率(beta)和截距，进而求 eta。
        """
        n = self.n
        t = self.data
        
        # 中位秩 (Median Ranks)
        # y = ln(-ln(1 - F))
        F = self._median_ranks()
        y = np.log(-np.log(1 - F))
        
        # 目标函数：最大化 R^2 (即最小化 -R^2)
        def negative_r_squared(gamma_val):
            # Gamma 必须小于最小失效时间
            if gamma_val >= t[0] - 1e-5:
                return 1e10
            
            # x = ln(t - gamma)
            # 处理潜在的无效值
            try:
                x = np.log(t - gamma_val)
            except:
                return 1e10
                
            # 计算相关系数
            correlation = np.corrcoef(x, y)[0, 1]
            return -(correlation**2)

        # 优化寻找最佳 gamma
        # 初始猜测：0
        # 边界：[0, min(t))
        result = minimize(
            negative_r_squared, 
            x0=[0.0], 
            bounds=[(0, t[0] * 0.999)],
            method='L-BFGS-B'
        )
        
        gamma_hat = result.x[0] if result.success else 0.0
        
        # 使用最佳 gamma 计算最终的 beta, eta
        x = np.log(t - gamma_hat)
        
        # 线性回归: Y = A + B*X
        # B = beta
        # A = -beta * ln(eta)
        
        # 手动计算斜率和截距
        x_mean = np.mean(x)
        y_mean = np.mean(y)
        
        numerator = np.sum((x - x_mean) * (y - y_mean))
        denominator = np.sum((x - x_mean)**2)
        
        if denominator == 0:
            beta_hat = 1.0 # Fallback
        else:
            beta_hat = numerator / denominator
            
        intercept = y_mean - beta_hat * x_mean
        
        # eta = exp(-A/B)
        eta_hat = np.exp(-intercept / beta_hat)
        
        # 计算 R^2
        r_squared = -result.fun if result.success else self._calculate_r2(beta_hat, eta_hat, gamma_hat)
        
        return [beta_hat, eta_hat, gamma_hat, r_squared]