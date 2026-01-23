import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class LRE(WeibullBase):
    def run(self):
        """3.2 Linear Regression Estimation (LRE)"""
        y = np.log(-np.log(1 - self._median_ranks()))
        
        def negative_r_squared(gamma_val):
            if gamma_val >= self.data[0]: return 1e15
            x = np.log(self.data - gamma_val)
            return -(np.corrcoef(x, y)[0, 1]**2)

        res_gamma = minimize(negative_r_squared, [0], bounds=[(0, self.data[0]-1e-5)])
        gamma = res_gamma.x[0]
        x = np.log(self.data - gamma)
        beta = (np.sum(x * y) - self.n * np.mean(x) * np.mean(y)) / (np.sum(x**2) - self.n * np.mean(x)**2)
        eta = np.exp(-(np.mean(y) - beta * np.mean(x)) / beta)
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]
