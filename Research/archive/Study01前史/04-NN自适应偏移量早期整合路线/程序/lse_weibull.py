"""
三参数 Weibull 概率图最小二乘估计 (LSE)

原理：
  中位秩 F_i = (i-0.3)/(n+0.4)
  变换：Y_i = ln(-ln(1-F_i)),  X_i = ln(t_i - γ)
  线性回归：Y = a + b·X  →  β̂ = b,  η̂ = exp(-a/b)
  γ 在 [0, t_(1)) 上搜索使 R² 最大的值

不修改 weibull 文件夹，独立实现。
"""

import numpy as np
from scipy.optimize import minimize_scalar


def bernard_F(n):
    """中位秩 (Bernard)"""
    i = np.arange(1, n + 1)
    return (i - 0.3) / (n + 0.4)


def _lse_at_gamma(t_sorted, gamma, F):
    """给定 γ，做概率图线性回归，返回 (beta_hat, eta_hat, r2)。"""
    diff = t_sorted - gamma
    if np.any(diff <= 0):
        return None, None, -np.inf

    Y = np.log(-np.log(1 - F))
    X = np.log(diff)

    # 简单线性回归
    n = len(X)
    sx = X.sum()
    sy = Y.sum()
    sxx = (X * X).sum()
    sxy = (X * Y).sum()

    denom = n * sxx - sx * sx
    if abs(denom) < 1e-30:
        return None, None, -np.inf

    b = (n * sxy - sx * sy) / denom       # slope = beta_hat
    a = (sy - b * sx) / n                  # intercept

    if b <= 0:
        return None, None, -np.inf

    beta_hat = b
    eta_hat = np.exp(-a / b)

    # R²
    ss_res = ((Y - (a + b * X)) ** 2).sum()
    ss_tot = ((Y - Y.mean()) ** 2).sum()
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0

    return beta_hat, eta_hat, r2


def fit_weibull3_lse(data):
    """
    三参数 Weibull 最小二乘估计。

    Parameters
    ----------
    data : array-like  原始失效时间（无需排序）

    Returns
    -------
    dict : beta_hat, eta_hat, gamma_hat, r_squared
    """
    t = np.sort(np.asarray(data, dtype=float))
    n = len(t)
    t_min = t[0]
    F = bernard_F(n)

    # γ 搜索：[0, t_min) 上几何加密网格
    eps = max(t_min * 1e-6, 1e-12)
    n_grid = 80
    gaps = np.geomspace(eps, t_min * 0.999, n_grid)
    gamma_grid = t_min - gaps
    gamma_grid = np.clip(gamma_grid, 0, t_min - eps)
    gamma_grid = np.sort(np.unique(gamma_grid))

    best_r2 = -np.inf
    best_gamma = 0.0
    best_beta = 1.0
    best_eta = 1.0

    for g in gamma_grid:
        beta, eta, r2 = _lse_at_gamma(t, g, F)
        if r2 > best_r2:
            best_r2 = r2
            best_gamma = g
            best_beta = beta
            best_eta = eta

    # 局部精化
    lo = max(0, best_gamma - (t_min * 0.01))
    hi = min(t_min - eps, best_gamma + (t_min * 0.01))
    if hi > lo:
        def neg_r2(g):
            _, _, r2 = _lse_at_gamma(t, g, F)
            return -r2

        res = minimize_scalar(neg_r2, bounds=(lo, hi), method='bounded',
                              options={'xatol': t_min * 1e-6})
        g_opt = res.x
        beta_opt, eta_opt, r2_opt = _lse_at_gamma(t, g_opt, F)
        if r2_opt > best_r2:
            best_gamma = g_opt
            best_beta = beta_opt
            best_eta = eta_opt
            best_r2 = r2_opt

    return {
        'beta_hat': float(best_beta),
        'eta_hat': float(best_eta),
        'gamma_hat': float(best_gamma),
        'r_squared': float(best_r2),
    }


if __name__ == '__main__':
    # 快速测试
    rng = np.random.default_rng(42)
    beta_true, eta_true, gamma_true = 2.5, 1000, 100
    u = rng.uniform(0, 1, 30)
    t = gamma_true + eta_true * (-np.log(1 - u)) ** (1 / beta_true)
    t = np.sort(t)

    result = fit_weibull3_lse(t)
    print(f"True:  beta={beta_true}, eta={eta_true}, gamma={gamma_true}")
    print(f"LSE:   beta={result['beta_hat']:.3f}, eta={result['eta_hat']:.1f}, "
          f"gamma={result['gamma_hat']:.1f}, R²={result['r_squared']:.4f}")
