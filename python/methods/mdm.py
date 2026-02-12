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
        gamma_steps = 60  # Steps for gradient calculation per round

        # ========== Round 1: Search in [0, 0.99*t_min] ==========
        gammas1 = np.linspace(0, t_min * 0.99, gamma_steps)
        sigma_mins1 = []
        best_betas1 = []

        for g in gammas1:
            b, sig = find_best_beta_for_gamma(g)
            sigma_mins1.append(sig)
            best_betas1.append(b)

        sigma_mins1 = np.array(sigma_mins1)
        best_betas1 = np.array(best_betas1)
        grads1 = np.gradient(sigma_mins1, gammas1)

        # Check for intersection in round 1
        diffs1 = grads1 - offset
        sign_changes = np.where(np.diff(np.sign(diffs1)))[0]

        # ========== Round 2: Search in [0.99*t_min, 0.999999*t_min] if needed ==========
        if len(sign_changes) == 0:
            print(f"[MDM] No intersection in round 1, extending search to [0.99*t_min, 0.999999*t_min]")
            gammas2 = np.linspace(t_min * 0.99, t_min * 0.999999, gamma_steps)
            sigma_mins2 = []
            best_betas2 = []

            for g in gammas2:
                b, sig = find_best_beta_for_gamma(g)
                sigma_mins2.append(sig)
                best_betas2.append(b)

            sigma_mins2 = np.array(sigma_mins2)
            best_betas2 = np.array(best_betas2)
            grads2 = np.gradient(sigma_mins2, gammas2)

            # Merge round 1 and round 2 data
            gammas = np.concatenate([gammas1, gammas2])
            sigma_mins = np.concatenate([sigma_mins1, sigma_mins2])
            best_betas = np.concatenate([best_betas1, best_betas2])
            grads = np.concatenate([grads1, grads2])

            # Re-check for intersection
            diffs = grads - offset
            sign_changes = np.where(np.diff(np.sign(diffs)))[0]
            print(f"[MDM] Round 2 gradient range: [{grads.min():.6f}, {grads.max():.6f}]")
        else:
            # Use round 1 data only
            gammas = gammas1
            sigma_mins = sigma_mins1
            best_betas = best_betas1
            grads = grads1
            diffs = diffs1

        # Debug: Print gradient range
        print(f"[MDM] offset={offset:.4f}, gradient range: [{grads.min():.6f}, {grads.max():.6f}]")

        # ========== Final: Find intersection point ==========
        found_gamma = 0.0
        found_beta = 1.0

        if len(sign_changes) > 0:
            # Pick the intersection closest to t_min (usually larger gamma is better for 3P fits if valid)
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
            # No intersection even after two rounds - return no solution
            print(f"[MDM] No intersection found after two rounds, returning no_solution")
            return None, None, None, None, "no_intersection"
            
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