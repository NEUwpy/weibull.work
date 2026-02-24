"""
案例10: 中位秩方法对比研究
支持两种中位秩计算方法:
1. Bernard's approximation: F(t_i) = (i - 0.3) / (n + 0.4)
2. 精确中位秩 (基于F分布): F(t_i) = i / (i + (n + 1 - i) * F_median)
   其中 F_median = F_{2(n+1-i), 2i}(0.5) 是F分布的中位数
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np
from scipy.stats import f
from scipy.optimize import minimize_scalar
from base import WeibullBase


def median_rank_exact(i: int, n: int, alpha: float = 0.5) -> float:
    """
    精确中位秩估计 - 基于F分布

    公式: F(t_{(i)}) = i / (i + (n + 1 - i) * F_{2(n+1-i), 2i}(alpha))

    当 alpha = 0.5 时，取F分布的中位数作为中位秩估计

    Args:
        i: 次序统计量的秩 (1-indexed)
        n: 样本量
        alpha: 分位数水平，默认0.5表示中位数

    Returns:
        中位秩估计值
    """
    dfn = 2 * (n + 1 - i)  # 分子自由度
    dfd = 2 * i             # 分母自由度
    f_quantile = f.ppf(alpha, dfn, dfd)  # F分布的alpha分位数
    return i / (i + (n + 1 - i) * f_quantile)


def median_rank_bernard(i: int, n: int) -> float:
    """
    Bernard近似中位秩

    公式: F(t_{(i)}) = (i - 0.3) / (n + 0.4)

    Args:
        i: 次序统计量的秩 (1-indexed)
        n: 样本量

    Returns:
        中位秩估计值
    """
    return (i - 0.3) / (n + 0.4)


class MDMCase10(WeibullBase):
    """
    案例10: 中位秩方法对比研究的MDM实现

    支持 rank_method 参数选择中位秩计算方法:
    - 'bernard': Bernard's approximation (默认)
    - 'exact': 精确中位秩 (基于F分布)
    """

    def __init__(self, data, rank_method: str = 'bernard'):
        """
        Args:
            data: 故障时间数据
            rank_method: 中位秩计算方法，'bernard' 或 'exact'
        """
        super().__init__(data)
        self.rank_method = rank_method

    def _median_ranks(self):
        """
        根据rank_method选择的中位秩计算方法计算中位秩

        Returns:
            中位秩数组
        """
        if self.rank_method == 'exact':
            ranks = np.array([median_rank_exact(i, self.n) for i in range(1, self.n + 1)])
        else:  # 'bernard' 或其他默认值
            ranks = super()._median_ranks()
        return ranks

    def run(self, trace=False, offset=0.1, gamma_steps=60):
        """
        Run the Minimum Discrepancy Method.

        Args:
            trace (bool): Whether to record trace data.
            offset (float): Gradient offset target (default 0.1).
            gamma_steps (int): Number of gamma search steps (default 60).

        Returns:
            (beta, eta, gamma, r_squared, status)
        """
        t = self.data
        n = self.n

        # 1. Median Ranks - 根据rank_method选择计算方法
        ranks = self._median_ranks()
        neg_ln_1_minus_F = -np.log(1 - ranks)

        def calculate_eta_std(beta, gamma, current_t):
            if beta <= 0:
                return float('inf')
            denom = np.power(neg_ln_1_minus_F, 1.0 / beta)
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
            print(f"[MDMCase10-{self.rank_method}] No intersection in round 1, extending search to [0.99*t_min, 0.999999*t_min]")
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
            print(f"[MDMCase10-{self.rank_method}] Round 2 gradient range: [{grads.min():.6f}, {grads.max():.6f}]")
        else:
            # Use round 1 data only
            gammas = gammas1
            sigma_mins = sigma_mins1
            best_betas = best_betas1
            grads = grads1
            diffs = diffs1

        # Debug: Print gradient range
        print(f"[MDMCase10-{self.rank_method}] offset={offset:.4f}, gradient range: [{grads.min():.6f}, {grads.max():.6f}]")

        # ========== Final: Find intersection point ==========
        found_gamma = 0.0
        found_beta = 1.0

        if len(sign_changes) > 0:
            # Pick the intersection closest to t_min (usually larger gamma is better for 3P fits if valid)
            idx = sign_changes[-1]

            y1, y2 = diffs[idx], diffs[idx + 1]
            x1, x2 = gammas[idx], gammas[idx + 1]

            # Linear interpolation
            if y2 != y1:
                found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
            else:
                found_gamma = x1

            found_beta, _ = find_best_beta_for_gamma(found_gamma)
            print(f"[MDMCase10-{self.rank_method}] Found intersection: gamma={found_gamma:.4f}, beta={found_beta:.4f}")
        else:
            # No intersection even after two rounds - return no solution
            print(f"[MDMCase10-{self.rank_method}] No intersection found after two rounds, returning no_solution")
            return None, None, None, None, "no_intersection"

        # Final Calculation
        denom = np.power(neg_ln_1_minus_F, 1.0 / found_beta)
        etas = (t - found_gamma) / denom
        found_eta = np.mean(etas)

        # R^2
        r2 = self._calculate_r2(found_beta, found_eta, found_gamma)

        # Trace Data
        if trace:
            # 1. Sigma vs Beta curve (at optimal gamma)
            beta_scan = np.linspace(0.5, 5, 100)
            sigma_beta_curve = []
            for b_val in beta_scan:
                s = calculate_eta_std(b_val, found_gamma, t)
                sigma_beta_curve.append({"beta": b_val, "sigma": s})

            # 2. Gradient vs Gamma curve
            grad_gamma_curve = []
            for i in range(len(gammas)):
                g = gammas[i]
                b = best_betas[i]
                denom = np.power(neg_ln_1_minus_F, 1.0 / b)
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
                "optimal_beta": found_beta
            }

        return float(found_beta), float(found_eta), float(found_gamma), float(r2), True


# 测试代码
if __name__ == "__main__":
    # 测试数据
    test_data = [1430.724077, 2632.924529, 1463.409269, 1469.488488, 2019.967671, 1620.885368, 1811.277248]

    print("=" * 60)
    print("中位秩方法对比测试")
    print("=" * 60)

    # Bernard's approximation
    print("\n1. Bernard's approximation:")
    mdm_bernard = MDMCase10(test_data, rank_method='bernard')
    beta_b, eta_b, gamma_b, r2_b, status_b = mdm_bernard.run(offset=0.1)
    print(f"   β = {beta_b:.6f}, η = {eta_b:.2f}, γ = {gamma_b:.2f}, R² = {r2_b:.4f}")

    # 精确中位秩
    print("\n2. 精确中位秩 (基于F分布):")
    mdm_exact = MDMCase10(test_data, rank_method='exact')
    beta_e, eta_e, gamma_e, r2_e, status_e = mdm_exact.run(offset=0.1)
    print(f"   β = {beta_e:.6f}, η = {eta_e:.2f}, γ = {gamma_e:.2f}, R² = {r2_e:.4f}")

    # 对比中位秩值
    print("\n3. 中位秩值对比:")
    print(f"   {'i':<5} {'Bernard':<15} {'Exact':<15} {'差异':<15}")
    print("   " + "-" * 50)
    n = len(test_data)
    for i in range(1, n + 1):
        bernard_val = median_rank_bernard(i, n)
        exact_val = median_rank_exact(i, n)
        diff = exact_val - bernard_val
        print(f"   {i:<5} {bernard_val:<15.8f} {exact_val:<15.8f} {diff:+.8f}")
