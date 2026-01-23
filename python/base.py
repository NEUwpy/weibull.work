import numpy as np

class WeibullBase:
    def __init__(self, data):
        """
        Input: data (list or np.array) of failure times.
        Status is assumed to be Failure (F) for this mathematical implementation.
        """
        self.data = np.array(sorted([x for x in data if x > 0]))
        self.n = len(self.data)

    def _median_ranks(self):
        """Helper: Calculate Median Ranks"""
        return (np.arange(1, self.n + 1) - 0.3) / (self.n + 0.4)

    def _cdf_3p(self, t, beta, eta, gamma_val):
        """Helper: 3-Parameter Weibull CDF"""
        t = np.array(t)
        vals = np.zeros_like(t, dtype=float)
        mask = t > gamma_val
        if np.any(mask):
            vals[mask] = 1 - np.exp(-((t[mask] - gamma_val) / eta)**beta)
        return vals

    def _calculate_r2(self, beta, eta, gamma_val):
        """Helper to calculate R-squared for any method"""
        if gamma_val >= self.data[0]: return 0.0
        
        # Experimental
        x = np.log(self.data - gamma_val)
        y_exp = np.log(-np.log(1 - self._median_ranks()))
        
        # Theoretical / Predicted
        # y = beta * x - beta * ln(eta)
        y_pred = beta * x - beta * np.log(eta)
        
        # R^2 calculation
        ss_res = np.sum((y_exp - y_pred)**2)
        ss_tot = np.sum((y_exp - np.mean(y_exp))**2)
        
        if ss_tot == 0: return 0.0
        return 1 - (ss_res / ss_tot)
