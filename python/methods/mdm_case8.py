"""
⚠ 历史复现实验，不是当前默认 MDM

MDM Case8 Variant - β使用固定步长0.05搜索
用于案例8: β搜索方式对比研究

与案例7的区别:
- 案例7: β 用 Brent 优化 (连续搜索)
- 案例8: β 用固定步长 0.05 遍历 (离散搜索)

S4.9 后默认 MDM 已重写（几何加密网格+约束边界规则），本文件仅用于历史案例复现。
"""

from base import WeibullBase
import numpy as np
from scipy.interpolate import interp1d, UnivariateSpline
from scipy.optimize import brentq

class MDMCase8(WeibullBase):
    def run(self, trace=False, offset=0.1, gamma_steps=60, discrete_gamma=False, beta_step=0.05):
        """
        Run the Minimum Discrepancy Method (Case8 Variant).

        Args:
            trace (bool): Whether to record trace data.
            offset (float): Gradient offset target (default 0.1).
            gamma_steps (int): Number of steps for gamma search (default 60).
            discrete_gamma (bool): If True, use discrete gamma values with interval 50 starting from 1430.
            beta_step (float): Step size for beta search (default 0.05).

        Returns:
            (beta, eta, gamma, r_squared, status)
        """
        t = self.data
        n = self.n

        # 1. Median Ranks
        ranks = self._median_ranks()
        neg_ln_1_minus_F = -np.log(1 - ranks)

        def calculate_eta_std(beta, gamma, current_t):
            if beta <= 0: return float('inf')
            denom = np.power(neg_ln_1_minus_F, 1.0/beta)
            etas = (current_t - gamma) / denom
            return np.std(etas, ddof=1)

        def find_best_beta_for_gamma_discrete(gamma):
            """使用固定步长遍历搜索最优β"""
            if gamma >= t[0]:
                return None, float('inf')

            # β范围: 以1为中心，步长 beta_step
            # 确保 β=1 总是在采样点中
            # 例如：步长0.05时，取值 0.05, 0.10, ..., 0.95, 1.00, 1.05, ...
            beta_values = np.arange(beta_step, 15.0 + beta_step, beta_step)
            min_sigma = float('inf')
            best_beta = beta_step

            for b in beta_values:
                sigma = calculate_eta_std(b, gamma, t)
                if sigma < min_sigma:
                    min_sigma = sigma
                    best_beta = b

            return best_beta, min_sigma

        # Search range for gamma: [0, t_min)
        t_min = t[0]

        # ========== Discrete gamma mode ==========
        if discrete_gamma:
            # 离散搜索：1430, 1400, 1350, 1300, ...
            gammas_list = [1430]
            g = 1400
            while g >= 0:
                gammas_list.append(g)
                g -= 50
            gammas1 = np.array(sorted(gammas_list))
        else:
            # 连续搜索
            gammas1 = np.linspace(0, t_min * 0.99, gamma_steps)

        # ========== Round 1: Search ==========
        sigma_mins1 = []
        best_betas1 = []

        for g in gammas1:
            b, sig = find_best_beta_for_gamma_discrete(g)
            sigma_mins1.append(sig)
            best_betas1.append(b)

        sigma_mins1 = np.array(sigma_mins1)
        best_betas1 = np.array(best_betas1)
        grads1 = np.gradient(sigma_mins1, gammas1)

        diffs1 = grads1 - offset
        sign_changes = np.where(np.diff(np.sign(diffs1)))[0]

        # ========== Round 2: Extended search if needed ==========
        if len(sign_changes) == 0 and not discrete_gamma:
            print(f"[MDMCase8] No intersection in round 1, extending search")
            gammas2 = np.linspace(t_min * 0.99, t_min * 0.999999, gamma_steps)
            sigma_mins2 = []
            best_betas2 = []

            for g in gammas2:
                b, sig = find_best_beta_for_gamma_discrete(g)
                sigma_mins2.append(sig)
                best_betas2.append(b)

            sigma_mins2 = np.array(sigma_mins2)
            best_betas2 = np.array(best_betas2)
            grads2 = np.gradient(sigma_mins2, gammas2)

            gammas = np.concatenate([gammas1, gammas2])
            sigma_mins = np.concatenate([sigma_mins1, sigma_mins2])
            best_betas = np.concatenate([best_betas1, best_betas2])
            grads = np.concatenate([grads1, grads2])

            diffs = grads - offset
            sign_changes = np.where(np.diff(np.sign(diffs)))[0]
        else:
            gammas = gammas1
            sigma_mins = sigma_mins1
            best_betas = best_betas1
            grads = grads1
            diffs = diffs1

        print(f"[MDMCase8] offset={offset:.4f}, steps={gamma_steps}, discrete={discrete_gamma}, beta_step={beta_step}")
        print(f"[MDMCase8] gradient range: [{grads.min():.6f}, {grads.max():.6f}]")

        # ========== Final: Find intersection point ==========
        found_gamma = 0.0
        found_beta = 1.0
        status = True

        if len(sign_changes) > 0:
            idx = sign_changes[-1]
            y1, y2 = diffs[idx], diffs[idx+1]
            x1, x2 = gammas[idx], gammas[idx+1]

            if y2 != y1:
                found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
            else:
                found_gamma = x1

            found_beta, _ = find_best_beta_for_gamma_discrete(found_gamma)
            print(f"[MDMCase8] Found intersection: gamma={found_gamma:.4f}, beta={found_beta:.4f}")
        elif discrete_gamma and len(gammas) >= 3:
            print(f"[MDMCase8] Discrete mode: using interpolation to find intersection")

            try:
                grad_interp = interp1d(gammas, grads, kind='cubic', fill_value='extrapolate')

                fine_gammas = np.linspace(gammas.min(), gammas.max(), 200)
                fine_grads = grad_interp(fine_gammas)
                fine_diffs = fine_grads - offset
                fine_sign_changes = np.where(np.diff(np.sign(fine_diffs)))[0]

                if len(fine_sign_changes) > 0:
                    idx = fine_sign_changes[-1]
                    y1, y2 = fine_diffs[idx], fine_diffs[idx+1]
                    x1, x2 = fine_gammas[idx], fine_gammas[idx+1]

                    if abs(y2 - y1) > 1e-10:
                        found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
                    else:
                        found_gamma = x1

                    found_beta, _ = find_best_beta_for_gamma_discrete(found_gamma)
                    print(f"[MDMCase8] Found intersection via interpolation: gamma={found_gamma:.4f}, beta={found_beta:.4f}")
                    status = "interpolated"
                else:
                    print(f"[MDMCase8] No intersection even with interpolation, using extrapolation")
                    status = "extrapolated"

                    if grads[-1] < offset:
                        slope = (grads[-1] - grads[-2]) / (gammas[-1] - gammas[-2])
                        if slope != 0:
                            found_gamma = gammas[-1] + (offset - grads[-1]) / slope
                            found_gamma = min(found_gamma, t_min * 0.999)
                            found_beta, _ = find_best_beta_for_gamma_discrete(found_gamma)
            except Exception as e:
                print(f"[MDMCase8] Interpolation failed: {e}")
                status = "interpolation_failed"
        else:
            print(f"[MDMCase8] No intersection found")
            status = "no_intersection"
            found_gamma = gammas[-1] if len(gammas) > 0 else 0.0
            found_beta = best_betas[-1] if len(best_betas) > 0 else 1.0

        # Final Calculation
        found_eta = None
        r2 = None
        if found_beta is not None and found_gamma is not None:
            denom = np.power(neg_ln_1_minus_F, 1.0/found_beta)
            etas = (t - found_gamma) / denom
            found_eta = np.mean(etas)
            r2 = self._calculate_r2(found_beta, found_eta, found_gamma)

        # Trace Data
        if trace:
            # β范围: 从beta_step开始，以1为中心
            beta_scan = np.arange(beta_step, 3 + beta_step, beta_step)
            sigma_beta_curve = []
            target_gamma = found_gamma if found_gamma is not None else gammas[-1] if len(gammas) > 0 else 0
            for b_val in beta_scan:
                s = calculate_eta_std(b_val, target_gamma, t)
                if np.isinf(s) or np.isnan(s):
                    s = None
                sigma_beta_curve.append({"beta": b_val, "sigma": s})

            num_gamma_samples = min(20, len(gammas))
            gamma_indices = np.linspace(0, len(gammas) - 1, num_gamma_samples, dtype=int)
            sampled_gammas = gammas[gamma_indices]

            beta_range = np.arange(beta_step, 3 + beta_step, beta_step)
            sigma_beta_gamma = []

            for g in sampled_gammas:
                sigma_curve = []
                for b_val in beta_range:
                    s = calculate_eta_std(b_val, g, t)
                    if np.isinf(s) or np.isnan(s):
                        sigma_curve.append(None)
                    else:
                        sigma_curve.append(float(s))

                sigma_beta_gamma.append({
                    "gamma": float(g),
                    "betas": [float(b) for b in beta_range],
                    "sigmas": sigma_curve
                })

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

            # 三次插值拟合
            try:
                unique_mask = np.concatenate([[True], np.diff(gammas) > 1e-10])
                unique_gammas = gammas[unique_mask]
                unique_grads = grads[unique_mask]

                if len(unique_gammas) < 4:
                    raise ValueError("Not enough unique points for cubic interpolation")

                # 三次插值
                interp_func = interp1d(unique_gammas, unique_grads, kind='cubic', fill_value='extrapolate')

                fit_gammas = np.linspace(gammas.min(), gammas.max(), 200)
                fit_grads = interp_func(fit_gammas)

                interp_shifted = lambda x: interp_func(x) - offset

                fit_gamma = None
                fit_method = "cubic_interp"

                fit_grads_all = interp_func(unique_gammas)
                if fit_grads_all.min() <= offset <= fit_grads_all.max():
                    for i in range(len(unique_gammas) - 1):
                        g1, g2 = unique_gammas[i], unique_gammas[i+1]
                        v1, v2 = float(interp_func(g1)) - offset, float(interp_func(g2)) - offset
                        if v1 * v2 < 0:
                            try:
                                fit_gamma = brentq(interp_shifted, g1, g2)
                                break
                            except:
                                pass

                poly_fit_data = {
                    "degree": 3,
                    "coefficients": [],
                    "formula": "Cubic Interpolation (interp1d)",
                    "fit_gammas": [float(g) for g in fit_gammas],
                    "fit_grads": [float(g) for g in fit_grads],
                    "fit_gamma": float(fit_gamma) if fit_gamma is not None else None,
                    "r_squared": 1.0,
                    "method": "cubic_interp"
                }

            except Exception as e:
                print(f"[MDMCase8] Cubic interpolation failed: {e}")
                poly_fit_data = {
                    "degree": 0,
                    "coefficients": [],
                    "formula": "Fit failed",
                    "fit_gammas": [],
                    "fit_grads": [],
                    "fit_gamma": None,
                    "r_squared": 0,
                    "method": "none"
                }

            self.trace_data = {
                "sigma_beta_curve": sigma_beta_curve,
                "grad_gamma_curve": grad_gamma_curve,
                "sigma_beta_gamma": sigma_beta_gamma,
                "target_offset": offset,
                "optimal_gamma": found_gamma,
                "optimal_beta": found_beta,
                "gamma_steps": gamma_steps,
                "discrete_gamma": discrete_gamma,
                "beta_step": beta_step,
                "poly_fit": poly_fit_data
            }

        return float(found_beta), float(found_eta), float(found_gamma), float(r2), True
