import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class LSE(WeibullBase):
    def run(self):
        """3.1 Least Squares Estimation (LSE)"""
        ranks = self._median_ranks()
        def sse_func(params):
            beta, eta, gamma_val = params
            if beta <= 0 or eta <= 0 or gamma_val >= self.data[0]: return 1e15
            model_cdf = self._cdf_3p(self.data, beta, eta, gamma_val)
            return np.sum((ranks - model_cdf)**2)

        initial_guess = [2.0, np.mean(self.data), 0]
        res = minimize(sse_func, initial_guess, method='Nelder-Mead')
        beta, eta, gamma = res.x
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]
