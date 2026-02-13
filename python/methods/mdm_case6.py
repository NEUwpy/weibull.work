"""
MDM Case6 Variant - 支持自定义迭代次数和离散搜索
用于案例6: 搜索步长对结果的影响

复制自 mdm.py，添加以下参数:
- gamma_steps: 迭代次数 (默认60)
- discrete_gamma: 离散搜索模式 (间隔100)
"""

from base import WeibullBase
import numpy as np
from scipy.optimize import minimize_scalar
from scipy.interpolate import interp1d

class MDMCase6(WeibullBase):
    def run(self, trace=False, offset=0.1, gamma_steps=60, discrete_gamma=False):
        """
        Run the Minimum Discrepancy Method (Case6 Variant).

        Args:
            trace (bool): Whether to record trace data.
            offset (float): Gradient offset target (default 0.1).
            gamma_steps (int): Number of steps for gamma search (default 60).
            discrete_gamma (bool): If True, use discrete gamma values with interval 100.

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
            if beta <= 0: return float('inf')
            denom = np.power(neg_ln_1_minus_F, 1.0/beta)
            etas = (current_t - gamma) / denom
            return np.std(etas, ddof=1)

        def find_best_beta_for_gamma(gamma):
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

        # ========== Discrete gamma mode ==========
        if discrete_gamma:
            max_gamma = int(t_min * 0.99)
            gammas1 = np.array([g for g in range(0, max_gamma + 1, 100)])
            if len(gammas1) == 0:
                gammas1 = np.array([0])
        else:
            gammas1 = np.linspace(0, t_min * 0.99, gamma_steps)

        # ========== Round 1: Search ==========
        sigma_mins1 = []
        best_betas1 = []

        for g in gammas1:
            b, sig = find_best_beta_for_gamma(g)
            sigma_mins1.append(sig)
            best_betas1.append(b)

        sigma_mins1 = np.array(sigma_mins1)
        best_betas1 = np.array(best_betas1)
        grads1 = np.gradient(sigma_mins1, gammas1)

        diffs1 = grads1 - offset
        sign_changes = np.where(np.diff(np.sign(diffs1)))[0]

        # ========== Round 2: Extended search if needed (skip for discrete mode) ==========
        if len(sign_changes) == 0 and not discrete_gamma:
            print(f"[MDMCase6] No intersection in round 1, extending search")
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

        print(f"[MDMCase6] offset={offset:.4f}, steps={gamma_steps}, discrete={discrete_gamma}")
        print(f"[MDMCase6] gradient range: [{grads.min():.6f}, {grads.max():.6f}]")

        # ========== Final: Find intersection point ==========
        found_gamma = 0.0
        found_beta = 1.0
        status = True

        if len(sign_changes) > 0:
            # 直接在离散点之间找到交点
            idx = sign_changes[-1]
            y1, y2 = diffs[idx], diffs[idx+1]
            x1, x2 = gammas[idx], gammas[idx+1]

            if y2 != y1:
                found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
            else:
                found_gamma = x1

            found_beta, _ = find_best_beta_for_gamma(found_gamma)
            print(f"[MDMCase6] Found intersection: gamma={found_gamma:.4f}, beta={found_beta:.4f}")
        elif discrete_gamma and len(gammas) >= 3:
            # 离散模式：使用插值拟合曲线来找交点
            print(f"[MDMCase6] Discrete mode: using interpolation to find intersection")

            # 使用三次样条插值
            try:
                grad_interp = interp1d(gammas, grads, kind='cubic', fill_value='extrapolate')

                # 在更细的网格上搜索交点
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

                    found_beta, _ = find_best_beta_for_gamma(found_gamma)
                    print(f"[MDMCase6] Found intersection via interpolation: gamma={found_gamma:.4f}, beta={found_beta:.4f}")
                    status = "interpolated"
                else:
                    # 如果还是没有交点，使用外推
                    print(f"[MDMCase6] No intersection even with interpolation, using extrapolation")
                    status = "extrapolated"

                    # 线性外推
                    if grads[-1] < offset:
                        # 梯度在下降，向右外推
                        slope = (grads[-1] - grads[-2]) / (gammas[-1] - gammas[-2])
                        if slope != 0:
                            found_gamma = gammas[-1] + (offset - grads[-1]) / slope
                            found_gamma = min(found_gamma, t_min * 0.999)
                            found_beta, _ = find_best_beta_for_gamma(found_gamma)
            except Exception as e:
                print(f"[MDMCase6] Interpolation failed: {e}")
                status = "interpolation_failed"
        else:
            print(f"[MDMCase6] No intersection found")
            status = "no_intersection"
            found_gamma = gammas[-1] if len(gammas) > 0 else 0.0
            found_beta = best_betas[-1] if len(best_betas) > 0 else 1.0

        # Final Calculation (only if we have valid estimates)
        found_eta = None
        r2 = None
        if found_beta is not None and found_gamma is not None:
            denom = np.power(neg_ln_1_minus_F, 1.0/found_beta)
            etas = (t - found_gamma) / denom
            found_eta = np.mean(etas)
            r2 = self._calculate_r2(found_beta, found_eta, found_gamma)

        # Trace Data - 始终生成，用于可视化
        if trace:
            beta_scan = np.linspace(0.5, 5, 100)
            sigma_beta_curve = []
            target_gamma = found_gamma if found_gamma is not None else gammas[-1] if len(gammas) > 0 else 0
            for b_val in beta_scan:
                s = calculate_eta_std(b_val, target_gamma, t)
                sigma_beta_curve.append({"beta": b_val, "sigma": s})

            num_gamma_samples = min(20, len(gammas))
            gamma_indices = np.linspace(0, len(gammas) - 1, num_gamma_samples, dtype=int)
            sampled_gammas = gammas[gamma_indices]

            beta_range = np.linspace(0.5, 5, 100)
            sigma_beta_gamma = []

            for g in sampled_gammas:
                sigma_curve = []
                for b_val in beta_range:
                    s = calculate_eta_std(b_val, g, t)
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

            self.trace_data = {
                "sigma_beta_curve": sigma_beta_curve,
                "grad_gamma_curve": grad_gamma_curve,
                "sigma_beta_gamma": sigma_beta_gamma,
                "target_offset": offset,
                "optimal_gamma": found_gamma,
                "optimal_beta": found_beta,
                "gamma_steps": gamma_steps,
                "discrete_gamma": discrete_gamma
            }

        return float(found_beta), float(found_eta), float(found_gamma), float(r2), True
