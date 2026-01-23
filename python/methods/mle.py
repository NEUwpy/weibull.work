import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class MLE(WeibullBase):
    def run(self):
        """2.1 Maximum Likelihood Estimation (MLE)"""
        def neg_log_likelihood(params):
            beta, eta, gamma_val = params
            if beta <= 0 or eta <= 0 or gamma_val >= self.data[0]: return 1e15
            term1 = self.n * np.log(beta)
            term2 = (beta - 1) * np.sum(np.log(self.data - gamma_val))
            term3 = -self.n * beta * np.log(eta)
            term4 = -np.sum(((self.data - gamma_val) / eta)**beta)
            return -(term1 + term2 + term3 + term4)

        initial_guess = [2.0, np.mean(self.data), 0]
        res = minimize(neg_log_likelihood, initial_guess, method='Nelder-Mead')
        beta, eta, gamma = res.x
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]
