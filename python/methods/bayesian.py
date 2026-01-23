import numpy as np
from scipy.optimize import minimize
from base import WeibullBase

class Bayesian(WeibullBase):
    def run(self):
        """7. Bayesian Method (MAP)"""
        def neg_posterior(params):
            beta, eta, gamma_val = params
            if beta <= 0 or eta <= 0 or gamma_val >= self.data[0]: return 1e15
            log_lik = self.n*np.log(beta) + (beta-1)*np.sum(np.log(self.data-gamma_val)) - self.n*beta*np.log(eta) - np.sum(((self.data-gamma_val)/eta)**beta)
            log_prior = -0.5 * ((beta - 2.0)/5.0)**2 # Weak prior
            return -(log_lik + log_prior)

        res = minimize(neg_posterior, [2.0, np.mean(self.data), 0], method='Nelder-Mead')
        beta, eta, gamma = res.x
        return [beta, eta, gamma, self._calculate_r2(beta, eta, gamma)]
