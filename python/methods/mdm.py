from base import WeibullBase
import numpy as np
from scipy.optimize import minimize_scalar

class MDM(WeibullBase):
    def run(self, trace=False, offset=0.1):
        """
        Run the Minimum Discrepancy Method.
        
        Args:
            trace (bool): Whether to record trace data.
            offset (float): Gradient offset target (default 0.1).
        
        Returns:
            (beta, eta, gamma, r_squared)
        """
        t = self.data
        n = self.n
        
        # 1. Median Ranks
        # F(ti) = (i - 0.3) / (n + 0.4)
        ranks = self._median_ranks()
        neg_ln_1_minus_F = -np.log(1 - ranks)

        def calculate_eta_std(beta, gamma, current_t):
            if beta <= 0: return float('inf')
            denom = np.power(neg_ln_1_minus_F, 1.0/beta)
            # Avoid division by zero or negative base issues if any
            # (current_t - gamma) should be > 0 checked before call
            etas = (current_t - gamma) / denom
            return np.std(etas, ddof=1)

        def find_best_beta_for_gamma(gamma):
            # Constraint: gamma < t_min
            if gamma >= t[0]:
                return None, float('inf')
            
            res = minimize_scalar(
                lambda b: calculate_eta_std(b, gamma, t),
                bounds=(0.1, 15.0),
                method='bounded'
            )
            return res.x, res.fun

        # Search range for gamma: [0, t_min)
        t_min = t[0]
        gamma_steps = 60 # Steps for gradient calculation
        # Stop slightly before t_min to avoid log(0)
        gammas = np.linspace(0, t_min * 0.99, gamma_steps)
        
        sigma_mins = []
        best_betas = []
        
        for g in gammas:
            b, sig = find_best_beta_for_gamma(g)
            sigma_mins.append(sig)
            best_betas.append(b)
            
        sigma_mins = np.array(sigma_mins)
        best_betas = np.array(best_betas)

        # Calculate Gradient
        grads = np.gradient(sigma_mins, gammas)
        
        # Criterion: Find gamma where Gradient = offset (0.1)
        diffs = grads - offset
        
        # Find intersection point
        sign_changes = np.where(np.diff(np.sign(diffs)))[0]
        
        found_gamma = 0.0
        found_beta = 1.0
        
        if len(sign_changes) > 0:
            # Pick the intersection closest to t_min (usually larger gamma is better for 3P fits if valid)
            # Or just the last one
            idx = sign_changes[-1]
            
            y1, y2 = diffs[idx], diffs[idx+1]
            x1, x2 = gammas[idx], gammas[idx+1]
            
            # Linear interpolation
            if y2 != y1:
                found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
            else:
                found_gamma = x1
            
            found_beta, _ = find_best_beta_for_gamma(found_gamma)
        else:
            # Fallback: Find point closest to offset
            min_diff_idx = np.argmin(np.abs(diffs))
            found_gamma = gammas[min_diff_idx]
            found_beta = best_betas[min_diff_idx]
            
        # Final Calculation
        denom = np.power(neg_ln_1_minus_F, 1.0/found_beta)
        etas = (t - found_gamma) / denom
        found_eta = np.mean(etas)
        
        # R^2
        r2 = self._calculate_r2(found_beta, found_eta, found_gamma)

        # Trace Data
        if trace:
            # 1. Sigma vs Beta curve (at optimal gamma)
            # Just generate some points around the optimal beta
            beta_scan = np.linspace(found_beta * 0.5, found_beta * 1.5, 50)
            sigma_beta_curve = []
            for b_val in beta_scan:
                s = calculate_eta_std(b_val, found_gamma, t)
                sigma_beta_curve.append({"beta": b_val, "sigma": s})
                
            # 2. Gradient vs Gamma curve
            grad_gamma_curve = []
            for i in range(len(gammas)):
                grad_gamma_curve.append({
                    "gamma": gammas[i],
                    "gradient": grads[i],
                    "sigma_min": sigma_mins[i]
                })

            # Since the frontend expects specific keys in the generic 'trace_data' list or object
            # We pack everything into a single "step" or object
            # Our visualizer expects: traceData = { sigma_beta_curve: [], grad_gamma_curve: [], ... }
            # But the backend returns `trace_data` as a list of dicts.
            # We can put this big object as the only item in the list, or modify the Visualizer to accept the raw object.
            # Base class appends to self.trace_data list.
            
            self.trace_data = {
                "sigma_beta_curve": sigma_beta_curve,
                "grad_gamma_curve": grad_gamma_curve,
                "target_offset": offset,
                "optimal_gamma": found_gamma,
                "optimal_beta": found_beta
            }

        return float(found_beta), float(found_eta), float(found_gamma), float(r2)