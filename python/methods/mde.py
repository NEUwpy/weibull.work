import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class MDE(WeibullBase):
    def run(self):
        """3.3 Minimum Discrepancy Estimation (MDE)"""
        F = self._median_ranks()
        K = (-np.log(1 - F))
        def discrepancy_func(params):
            beta, gamma_val = params
            if beta <= 0 or gamma_val >= self.data[0]: return 1e15
            etas = (self.data - gamma_val) / (K**(1/beta))
            return np.std(etas)

        res = minimize(discrepancy_func, [2.0, 0], method='Nelder-Mead')
        beta, gamma = res.x
        eta = np.mean((self.data - gamma) / (K**(1/beta)))
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]
