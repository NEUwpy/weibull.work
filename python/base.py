import numpy as np
from scipy.special import betaincinv

class WeibullBase:
    def __init__(self, data, rank_method='bernard'):
        """
        Input: data (list or np.array) of failure times.
        Status is assumed to be Failure (F) for this mathematical implementation.
        rank_method: 'bernard' or 'exact' - method for calculating median ranks
        """
        self.data = np.array(sorted([x for x in data if x > 0]))
        self.n = len(self.data)
        self.trace_data = [] # Store process data for visualization
        self.rank_method = rank_method

    def log_step(self, step_info: dict):
        """Helper: Log a step for visualization"""
        # Add iteration number automatically if not present
        if "step" not in step_info:
            step_info["step"] = len(self.trace_data) + 1

        # Convert numpy types to native python types for JSON serialization
        clean_info = {}
        for k, v in step_info.items():
            if isinstance(v, (np.intc, np.intp, np.int8,
                np.int16, np.int32, np.int64, np.uint8,
                np.uint16, np.uint32, np.uint64)):
                clean_info[k] = int(v)
            elif isinstance(v, (np.float16, np.float32, np.float64)):
                clean_info[k] = float(v)
            elif isinstance(v, (np.ndarray,)):
                clean_info[k] = v.tolist()
            else:
                clean_info[k] = v

        self.trace_data.append(clean_info)

    def _median_ranks(self):
        """
        Helper: Calculate Median Ranks using configured method.
        - 'bernard': Bernard's approximation (i - 0.3) / (n + 0.4)
        - 'exact': Exact median rank using inverse incomplete beta function
        """
        i = np.arange(1, self.n + 1)
        if self.rank_method == 'exact':
            return betaincinv(i, self.n - i + 1, 0.5)
        else:  # bernard
            return (i - 0.3) / (self.n + 0.4)

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