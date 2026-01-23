import numpy as np
from scipy.optimize import minimize
from scipy.special import gamma as gamma_func
from base import WeibullBase

class MM(WeibullBase):
    def run(self):
        """4.1 Method of Moments (MM)"""
        mean_t = np.mean(self.data)
        var_t = np.var(self.data, ddof=1)
        skew_t = (np.sum((self.data - mean_t)**3) / self.n) / (var_t**1.5)
        
        def skew_eq(beta):
            if beta <= 0: return 1e15
            g1 = gamma_func(1 + 1/beta)
            g2 = gamma_func(1 + 2/beta)
            g3 = gamma_func(1 + 3/beta)
            return ((g3 - 3*g2*g1 + 2*(g1**3)) / ((g2 - g1**2)**1.5) - skew_t)**2

        res_beta = minimize(skew_eq, [2.0], bounds=[(0.1, 10)])
        beta = res_beta.x[0]
        g1 = gamma_func(1 + 1/beta)
        g2 = gamma_func(1 + 2/beta)
        eta = np.sqrt(var_t / (g2 - g1**2))
        gamma = mean_t - eta * g1
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]
