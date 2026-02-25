"""
精细步长MDM (Minimum Discrepancy Method)

与标准MDM的区别：
- β搜索：使用离散步长搜索而非连续优化
- γ搜索：使用固定步长（预估位置参数的1%）而非固定步数

参数：
- beta_step: β搜索步长，默认0.01
- gamma_step: γ搜索步长，默认10（当estimated_gamma=1000时为1%）
"""

from base import WeibullBase
import numpy as np

class MDMFine(WeibullBase):
    def run(self, trace=False, offset=0.1, beta_step=0.01, gamma_step=10):
        """
        Run the Minimum Discrepancy Method with fine step sizes.

        Args:
            trace (bool): Whether to record trace data.
            offset (float): Gradient offset target (default 0.1).
            beta_step (float): Step size for beta search (default 0.01).
            gamma_step (float): Step size for gamma search (default 10).

        Returns:
            (beta, eta, gamma, r_squared, status)
        """
        t = self.data
        n = self.n

        # 1. Median Ranks
        # F(ti) = (i - 0.3) / (n + 0.4)
        ranks = self._median_ranks()
        neg_ln_1_minus_F = -np.log(1 - ranks)

        def calculate_eta_std(beta, gamma, current_t):
            if beta <= 0:
                return float('inf')
            denom = np.power(neg_ln_1_minus_F, 1.0/beta)
            etas = (current_t - gamma) / denom
            return np.std(etas, ddof=1)

        def find_best_beta_for_gamma_fine(gamma):
            """
            使用离散步长搜索最佳β值
            """
            if gamma >= t[0]:
                return None, float('inf')

            # β搜索范围：0.1 到 15.0，步长为 beta_step
            beta_min = beta_step  # 从步长开始，避免0
            beta_max = 15.0
            best_beta = beta_min
            best_sigma = float('inf')

            beta = beta_min
            while beta <= beta_max:
                sigma = calculate_eta_std(beta, gamma, t)
                if sigma < best_sigma:
                    best_sigma = sigma
                    best_beta = beta
                beta += beta_step

            return best_beta, best_sigma

        # Search range for gamma: [0, t_min)
        t_min = t[0]

        # 计算gamma搜索的点数：从0到0.99*t_min，步长为gamma_step
        gamma_max_1 = t_min * 0.99
        num_gamma_steps_1 = max(2, int(gamma_max_1 / gamma_step) + 1)
        gammas1 = np.linspace(0, gamma_max_1, num_gamma_steps_1)

        sigma_mins1 = []
        best_betas1 = []

        for g in gammas1:
            b, sig = find_best_beta_for_gamma_fine(g)
            sigma_mins1.append(sig)
            best_betas1.append(b)

        sigma_mins1 = np.array(sigma_mins1)
        best_betas1 = np.array(best_betas1)
        grads1 = np.gradient(sigma_mins1, gammas1)

        # Check for intersection in round 1
        diffs1 = grads1 - offset
        sign_changes = np.where(np.diff(np.sign(diffs1)))[0]

        # Round 2: Search in [0.99*t_min, 0.999999*t_min] if needed
        if len(sign_changes) == 0:
            print(f"[MDMFine] No intersection in round 1, extending search to [0.99*t_min, 0.999999*t_min]")
            gamma_max_2 = t_min * 0.999999
            num_gamma_steps_2 = max(2, int((gamma_max_2 - gamma_max_1) / gamma_step) + 1)
            gammas2 = np.linspace(t_min * 0.99, gamma_max_2, num_gamma_steps_2)

            sigma_mins2 = []
            best_betas2 = []

            for g in gammas2:
                b, sig = find_best_beta_for_gamma_fine(g)
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
            print(f"[MDMFine] Round 2 gradient range: [{grads.min():.6f}, {grads.max():.6f}]")
        else:
            # Use round 1 data only
            gammas = gammas1
            sigma_mins = sigma_mins1
            best_betas = best_betas1
            grads = grads1
            diffs = diffs1

        # Debug: Print gradient range
        print(f"[MDMFine] offset={offset:.4f}, beta_step={beta_step}, gamma_step={gamma_step}")
        print(f"[MDMFine] gradient range: [{grads.min():.6f}, {grads.max():.6f}]")

        # Find intersection point
        found_gamma = 0.0
        found_beta = 1.0

        if len(sign_changes) > 0:
            # Pick the intersection closest to t_min
            idx = sign_changes[-1]

            y1, y2 = diffs[idx], diffs[idx+1]
            x1, x2 = gammas[idx], gammas[idx+1]

            # Linear interpolation
            if y2 != y1:
                found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
            else:
                found_gamma = x1

            found_beta, _ = find_best_beta_for_gamma_fine(found_gamma)
            print(f"[MDMFine] Found intersection: gamma={found_gamma:.4f}, beta={found_beta:.4f}")
        else:
            # No intersection even after two rounds
            print(f"[MDMFine] No intersection found after two rounds, returning no_solution")
            return None, None, None, None, "no_intersection"

        # Final Calculation
        denom = np.power(neg_ln_1_minus_F, 1.0/found_beta)
        etas = (t - found_gamma) / denom
        found_eta = np.mean(etas)

        # R^2
        r2 = self._calculate_r2(found_beta, found_eta, found_gamma)

        # Trace Data
        if trace:
            # Sigma vs Beta curve (at optimal gamma)
            beta_scan = np.arange(beta_step, 5.0 + beta_step, beta_step)
            sigma_beta_curve = []
            for b_val in beta_scan:
                s = calculate_eta_std(b_val, found_gamma, t)
                sigma_beta_curve.append({"beta": float(b_val), "sigma": float(s)})

            # Gradient vs Gamma curve
            grad_gamma_curve = []
            for i in range(len(gammas)):
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
                    "best_eta": eta_mean
                })

            self.trace_data = {
                "sigma_beta_curve": sigma_beta_curve,
                "grad_gamma_curve": grad_gamma_curve,
                "target_offset": offset,
                "optimal_gamma": found_gamma,
                "optimal_beta": found_beta,
                "beta_step": beta_step,
                "gamma_step": gamma_step
            }

        return float(found_beta), float(found_eta), float(found_gamma), float(r2), True
