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

        # Debug: Print gradient range
        print(f"[MDM] offset={offset:.4f}, gradient range: [{grads.min():.6f}, {grads.max():.6f}]")

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
            print(f"[MDM] Found intersection: gamma={found_gamma:.4f}, beta={found_beta:.4f}")
        else:
            # Fallback: Find point closest to offset
            min_diff_idx = np.argmin(np.abs(diffs))
            found_gamma = gammas[min_diff_idx]
            found_beta = best_betas[min_diff_idx]
            print(f"[MDM] No intersection, using closest: gamma={found_gamma:.4f}, beta={found_beta:.4f}, diff={diffs[min_diff_idx]:.6f}")
            
        # Final Calculation
        denom = np.power(neg_ln_1_minus_F, 1.0/found_beta)
        etas = (t - found_gamma) / denom
        found_eta = np.mean(etas)
        
        # R^2
        r2 = self._calculate_r2(found_beta, found_eta, found_gamma)

        # Trace Data
        if trace:
            # 1. Sigma vs Beta curve (at optimal gamma) - for backward compatibility
            # Use range [0.5, 5] to match frontend x-axis range
            beta_scan = np.linspace(0.5, 5, 100)
            sigma_beta_curve = []
            for b_val in beta_scan:
                s = calculate_eta_std(b_val, found_gamma, t)
                sigma_beta_curve.append({"beta": b_val, "sigma": s})

            # 2. Full 2D surface data: sigma_beta_gamma for 3D visualization
            # Select 20 gamma points to calculate full sigma(beta) curves
            num_gamma_samples = 20
            gamma_indices = np.linspace(0, len(gammas) - 1, num_gamma_samples, dtype=int)
            sampled_gammas = gammas[gamma_indices]

            # Beta scan range (same for all gamma values) - [0.5, 5] to match frontend
            beta_range = np.linspace(0.5, 5, 100)

            sigma_beta_gamma = []  # Full 2D surface data

            for idx, g in enumerate(sampled_gammas):
                # For each sampled gamma, calculate full sigma(beta) curve
                sigma_curve = []
                for b_val in beta_range:
                    s = calculate_eta_std(b_val, g, t)
                    sigma_curve.append(float(s))

                sigma_beta_gamma.append({
                    "gamma": float(g),
                    "betas": [float(b) for b in beta_range],
                    "sigmas": sigma_curve
                })

            # 3. Gradient vs Gamma curve
            grad_gamma_curve = []
            for i in range(len(gammas)):
                # Calculate eta for this gamma-beta pair
                g = gammas[i]
                b = best_betas[i]
                denom = np.power(neg_ln_1_minus_F, 1.0/b)
                etas_g = (t - g) / denom
                eta_mean = float(np.mean(etas_g))

                grad_gamma_curve.append({
                    "gamma": float(g),
                    "gradient": float(grads[i]),
                    "sigma_min": float(sigma_mins[i]),
                    "best_beta": float(b),
                    "best_eta": eta_mean  # Add eta for this gamma-beta pair
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
                "sigma_beta_gamma": sigma_beta_gamma,  # Full 2D surface for 3D visualization
                "target_offset": offset,
                "optimal_gamma": found_gamma,
                "optimal_beta": found_beta
            }

        return float(found_beta), float(found_eta), float(found_gamma), float(r2), True