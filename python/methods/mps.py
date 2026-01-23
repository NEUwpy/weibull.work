import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class MPS(WeibullBase):
    def run(self):
        """2.4 Maximum Product Spacing (MPS)"""
        def neg_mps_func(params):
            beta, eta, gamma_val = params
            if beta <= 0 or eta <= 0 or gamma_val >= self.data[0]: return 1e15
            cdf_vals = self._cdf_3p(self.data, beta, eta, gamma_val)
            aug_cdf = np.concatenate(([0], cdf_vals, [1]))
            diffs = np.diff(aug_cdf)
            diffs[diffs <= 0] = 1e-10
            return -np.sum(np.log(diffs))

        initial_guess = [2.0, np.mean(self.data), 0]
        res = minimize(neg_mps_func, initial_guess, method='Nelder-Mead')
        beta, eta, gamma = res.x
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]
