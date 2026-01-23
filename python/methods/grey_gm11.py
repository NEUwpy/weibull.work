import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class GreyGM11(WeibullBase):
    def run(self):
        """5. Grey Estimation (GM 1,1)"""
        F = self._median_ranks()
        xt = np.log(-np.log(1 - F))
        tt = self.data
        idx = np.argsort(xt)
        xt_s, tt_s = xt[idx], tt[idx]
        
        def grey_fit(params):
            c, a, b = params
            return np.sum((tt_s - (c * np.exp(-a * xt_s) + b))**2)
            
        res = minimize(grey_fit, [100, 1, 0])
        c, a, b = res.x
        beta, eta, gamma = -1.0/a, c, b
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]
