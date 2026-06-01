"""
三参数 Weibull 核心库
- 分布函数 (pdf/cdf/logpdf/quantile)
- 估计器：gamma 剖面似然 + 两参数闭式 MLE（对 beta>1 行为良好、快速、可复现）
- 评价指标：参数视角 (bias/var/MSE/RMSE/RRMSE) 与工程视角 (分位点 x_R 误差)
"""
import numpy as np
from scipy.optimize import brentq, minimize_scalar

# ---------------------------------------------------------------------------
# 三参数 Weibull 分布函数
# F(x) = 1 - exp(-((x-gamma)/eta)^beta),  x >= gamma
# 可靠度 R(x) = exp(-((x-gamma)/eta)^beta)
# 给定可靠度 R 的寿命分位点: x_R = gamma + eta * (-ln R)^(1/beta)
# ---------------------------------------------------------------------------

def quantile_xR(beta, eta, gamma, R):
    """给定可靠度 R(>0,<1) 的寿命分位点 x_R（失效概率 p=1-R）。"""
    R = np.asarray(R, dtype=float)
    return gamma + eta * (-np.log(R)) ** (1.0 / beta)

def logpdf3(x, beta, eta, gamma):
    z = (x - gamma) / eta
    out = np.full_like(np.asarray(x, float), -np.inf, dtype=float)
    m = z > 0
    zz = z[m] if np.ndim(z) else (z if z > 0 else np.nan)
    if np.ndim(z):
        out[m] = (np.log(beta / eta) + (beta - 1.0) * np.log(z[m]) - z[m] ** beta)
        return out
    else:
        return (np.log(beta / eta) + (beta - 1.0) * np.log(z) - z ** beta) if z > 0 else -np.inf

# ---------------------------------------------------------------------------
# 两参数 Weibull 闭式 MLE（数据 y>0；位置已减去）
#   形状 k 解方程: sum(y^k ln y)/sum(y^k) - 1/k - mean(ln y) = 0
#   尺度 lam = ( mean(y^k) )^(1/k)
# ---------------------------------------------------------------------------

def weibull2_mle(y):
    y = np.asarray(y, dtype=float)
    lny = np.log(y)
    mean_lny = lny.mean()

    def g(k):
        # 用 log-sum-exp 稳定计算 sum(y^k ln y)/sum(y^k)，避免 y^k 溢出
        a = k * lny
        amax = a.max()
        w = np.exp(a - amax)          # 权重（未归一）
        ratio = (lny * w).sum() / w.sum()
        return ratio - 1.0 / k - mean_lny

    # g(k) 随 k 单调上升：k->0+ 为 -inf，k->inf 趋于 max(lny)-mean(lny)>0，根唯一
    klo, khi = 1e-3, 2e2
    k = brentq(g, klo, khi, maxiter=200)
    # 稳定计算 lam = (mean(y^k))^(1/k)
    a = k * lny
    amax = a.max()
    log_mean_yk = amax + np.log(np.mean(np.exp(a - amax)))
    lam = np.exp(log_mean_yk / k)
    return k, lam

# ---------------------------------------------------------------------------
# 三参数 Weibull MLE：对 gamma 做剖面似然
#   对固定 gamma，令 y=x-gamma，用两参数闭式 MLE 得 (beta,eta)，记录对数似然
#   在 [0, x_(1)) 上搜索使对数似然最大的 gamma（粗网格 + 局部精化）
# ---------------------------------------------------------------------------

def _profile_negll(gamma, x_sorted):
    y = x_sorted - gamma
    if y[0] <= 0:
        return np.inf
    k, lam = weibull2_mle(y)
    z = y / lam
    ll = np.sum(np.log(k / lam) + (k - 1.0) * np.log(z) - z ** k)
    return -ll

def fit_weibull3(x, ngrid=80, allow_zero_gamma=True):
    """返回 (beta_hat, eta_hat, gamma_hat)。gamma 限制在 [0, x_min)。"""
    x = np.sort(np.asarray(x, dtype=float))
    xmin = x[0]
    # gamma 上界稍微离开边界，避免似然在 y->0 处退化（beta>1 时内部解占优）
    hi = xmin * (1 - 1e-4) if xmin > 0 else 0.0
    if hi <= 0:
        # 数据含 0 或负（理论上不应发生），退回 gamma=0
        y = x - 0.0
        k, lam = weibull2_mle(np.where(y > 0, y, 1e-9))
        return k, lam, 0.0
    grid = np.linspace(0.0, hi, ngrid)
    vals = np.array([_profile_negll(g, x) for g in grid])
    j = int(np.argmin(vals))
    # 在最优网格点邻域做有界精化
    lo_b = grid[max(j - 1, 0)]
    hi_b = grid[min(j + 1, ngrid - 1)]
    if hi_b > lo_b:
        res = minimize_scalar(_profile_negll, bounds=(lo_b, hi_b),
                              args=(x,), method='bounded',
                              options={'xatol': hi * 1e-4})
        gamma_hat = float(res.x)
    else:
        gamma_hat = float(grid[j])
    y = x - gamma_hat
    beta_hat, eta_hat = weibull2_mle(y)
    return float(beta_hat), float(eta_hat), float(gamma_hat)

# ---------------------------------------------------------------------------
# 参数视角评价指标（已知真值，蒙特卡洛）
# 输入 est: shape (R,3) 的估计数组，列序 [beta, eta, gamma]
#       true: 长度 3 的真值
# ---------------------------------------------------------------------------

def param_metrics(est, true):
    est = np.asarray(est, float)
    true = np.asarray(true, float)
    mean = est.mean(axis=0)
    bias = mean - true
    var = est.var(axis=0, ddof=1)
    mse = bias ** 2 + var               # = E[(est-true)^2]（无偏方差近似）
    mse_exact = ((est - true) ** 2).mean(axis=0)
    rmse = np.sqrt(mse_exact)
    # 相对量：真值为 0 时返回 nan
    with np.errstate(divide='ignore', invalid='ignore'):
        rel_bias = np.where(true != 0, bias / true, np.nan)
        rrmse = np.where(true != 0, rmse / np.abs(true), np.nan)
        cv = np.where(mean != 0, np.sqrt(var) / mean, np.nan)
    return dict(mean=mean, bias=bias, var=var, mse=mse_exact, rmse=rmse,
               rel_bias=rel_bias, rrmse=rrmse, cv=cv)

# ---------------------------------------------------------------------------
# 工程视角评价指标：给定 R 的寿命分位点 x_R 估计误差
# 返回每个 R 下的 MAE / RMSE / MAPE / sMAPE / relative bias / RRMSE
# ---------------------------------------------------------------------------

def quantile_metrics(est, true, R_list):
    est = np.asarray(est, float)
    bt, et, gt = true
    out = {}
    for R in R_list:
        x_true = quantile_xR(bt, et, gt, R)
        x_hat = quantile_xR(est[:, 0], est[:, 1], est[:, 2], R)
        err = x_hat - x_true                      # 带符号误差
        ae = np.abs(err)
        mae = ae.mean()
        rmse = np.sqrt((err ** 2).mean())
        mape = np.mean(ae / np.abs(x_true)) * 100 if x_true != 0 else np.nan
        smape = np.mean(200 * ae / (np.abs(x_hat) + np.abs(x_true))) 
        rel_bias = err.mean() / x_true if x_true != 0 else np.nan
        rrmse = rmse / np.abs(x_true) if x_true != 0 else np.nan
        out[R] = dict(x_true=x_true, x_hat=x_hat, err=err,
                     mae=mae, rmse=rmse, mape=mape, smape=smape,
                     rel_bias=rel_bias, rrmse=rrmse,
                     rmse_over_mae=rmse / mae if mae > 0 else np.nan)
    return out
