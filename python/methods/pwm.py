import numpy as np
from scipy.optimize import minimize
from scipy.special import gamma as gamma_func
from base import WeibullBase

class PWM(WeibullBase):
    def run(self):
        """4.4 Probability Weighted Moments (PWM)"""
        M = {k: np.mean(self.data * (1 - (np.arange(1, self.n + 1) - 0.35) / self.n)**k) for k in [0, 1, 2]}
        def equations(params):
            beta, eta, gamma_val = params
            if beta <= 0 or eta <= 0: return [1e5]*3
            diffs = []
            for k in [0, 1, 2]:
                diffs.append(gamma_val/(1+k) + (eta * gamma_func(1 + 1/beta))/((1+k)**(1+1/beta)) - M[k])
            return diffs

        res = minimize(lambda p: np.sum(np.array(equations(p))**2), [2.0, np.mean(self.data), 0], method='Nelder-Mead')
        beta, eta, gamma = res.x
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]
