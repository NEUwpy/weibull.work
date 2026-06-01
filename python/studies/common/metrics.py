"""
S2R 唯一评价指标模块

维护约定：
- 本模块是指标规范页面 `/help/metrics` 的可执行实现。
- `/help/metrics` 是本模块的可读规范说明。
- 修改本模块任一公式、字段名或判定口径时，必须同步修改
  `src/app/help/metrics/page.tsx`；反过来，页面规范变更也必须同步本模块。

当前唯一指标体系：
- 参数视角和工程分位点视角都先形成带符号相对误差分布。
- 主指标为 MdAPE；并列报告方向、稳定性、尾部和有效估计率。
- beta/eta 用自身归一化，gamma 用 eta 归一化。
- NE、NQE_R、RE_R、Outlier Rate 等旧体系指标已废止，不再输出。
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np


DEFAULT_R_LEVELS = (0.50, 0.90, 0.95, 0.99, 0.999)


def quantile_true(beta: float, eta: float, gamma: float, R: float) -> float:
    """真实可靠度寿命分位点 x_R = gamma + eta * (-ln R)^(1/beta)。"""
    return gamma + eta * (-math.log(R)) ** (1.0 / beta)


def quantile_est(beta_hat: float, eta_hat: float, gamma_hat: float, R: float) -> float:
    """估计可靠度寿命分位点 x_hat_R。"""
    return gamma_hat + eta_hat * (-math.log(R)) ** (1.0 / beta_hat)


def param_relative_errors(
    beta_hat: float,
    eta_hat: float,
    gamma_hat: float,
    beta: float,
    eta: float,
    gamma: float,
) -> Dict[str, float]:
    """返回参数视角的带符号相对误差。

    gamma 可能为 0，且工程上与寿命尺度同量纲，因此统一用 eta 归一化。
    """
    return {
        "beta": (beta_hat - beta) / beta,
        "eta": (eta_hat - eta) / eta,
        "gamma": (gamma_hat - gamma) / eta,
    }


def quantile_relative_error(
    beta_hat: float,
    eta_hat: float,
    gamma_hat: float,
    beta: float,
    eta: float,
    gamma: float,
    R: float,
) -> float:
    """返回工程分位点视角的带符号相对误差。"""
    x_r = quantile_true(beta, eta, gamma, R)
    x_hat_r = quantile_est(beta_hat, eta_hat, gamma_hat, R)
    return (x_hat_r - x_r) / x_r


def summarize_relative_errors(errors: List[float] | np.ndarray) -> Dict[str, Optional[float]]:
    """汇总带符号相对误差分布。

    返回字段即当前唯一指标族：
    - mdape: median(|e|)
    - med_rel: median(e)
    - p25_rel/p75_rel/reliqr: 稳定性
    - p5_rel/p95_rel/p95_abs/p99_abs: 尾部
    """
    arr = np.asarray(errors, dtype=float)
    arr = arr[np.isfinite(arr)]

    empty = {
        "mdape": None,
        "med_rel": None,
        "p25_rel": None,
        "p75_rel": None,
        "reliqr": None,
        "p5_rel": None,
        "p95_rel": None,
        "p95_abs": None,
        "p99_abs": None,
    }
    if arr.size == 0:
        return empty

    abs_arr = np.abs(arr)
    p25 = float(np.percentile(arr, 25))
    p75 = float(np.percentile(arr, 75))

    return {
        "mdape": float(np.median(abs_arr)),
        "med_rel": float(np.median(arr)),
        "p25_rel": p25,
        "p75_rel": p75,
        "reliqr": p75 - p25,
        "p5_rel": float(np.percentile(arr, 5)),
        "p95_rel": float(np.percentile(arr, 95)),
        "p95_abs": float(np.percentile(abs_arr, 95)),
        "p99_abs": float(np.percentile(abs_arr, 99)),
    }


def check_status(
    beta_hat: float,
    eta_hat: float,
    gamma_hat: float,
    beta: float,
    eta: float,
    gamma: float,
    converged: bool = True,
    sample_min: Optional[float] = None,
    boundary_tol: float = 1e-10,
) -> str:
    """判定估计是否有效。

    S2R 不再按误差大小判 outlier。误差很大但数值有效的样本必须进入
    尾部统计；只有不收敛、数值非法、物理非法或边界病态才判 failure。
    """
    if not converged:
        return "failure"
    if not math.isfinite(beta_hat) or beta_hat <= 0:
        return "failure"
    if not math.isfinite(eta_hat) or eta_hat <= 0:
        return "failure"
    if not math.isfinite(gamma_hat):
        return "failure"

    if sample_min is not None and math.isfinite(sample_min):
        tol = boundary_tol * max(abs(sample_min), abs(eta), 1.0)
        if gamma_hat >= sample_min - tol:
            return "failure"

    return "success"


def aggregate_param_metrics(
    results: List[Dict],
    R_levels: Tuple[float, ...] = DEFAULT_R_LEVELS,
) -> Dict:
    """批量计算当前唯一指标体系。

    Args:
        results: 每个元素包含 beta_hat/eta_hat/gamma_hat、beta/eta/gamma、
            converged，可选 time、sample_min。
        R_levels: 需要报告的可靠度分位点。

    Returns:
        汇总结果。参数视角位于 `param_distribution`，工程分位点视角位于
        `quantile_distribution`，并提供常用 flat key 便于表格输出。
    """
    n_total = len(results)
    if n_total == 0:
        return {"n_total": 0}

    valid_rows = []
    n_failure = 0

    for row in results:
        beta_hat = row.get("beta_hat")
        eta_hat = row.get("eta_hat")
        gamma_hat = row.get("gamma_hat")

        if beta_hat is None or eta_hat is None or gamma_hat is None:
            n_failure += 1
            continue

        status = check_status(
            beta_hat,
            eta_hat,
            gamma_hat,
            row["beta"],
            row["eta"],
            row["gamma"],
            converged=row.get("converged", True),
            sample_min=row.get("sample_min"),
        )

        if status == "failure":
            n_failure += 1
        else:
            valid_rows.append(row)

    n_valid = len(valid_rows)
    output = {
        "n_total": n_total,
        "n_valid": n_valid,
        "n_failure": n_failure,
        "valid_rate": n_valid / n_total,
        "failure_rate": n_failure / n_total,
    }

    if n_valid == 0:
        return output

    param_errors = {"beta": [], "eta": [], "gamma": []}
    quantile_errors = {R: [] for R in R_levels}

    for row in valid_rows:
        errors = param_relative_errors(
            row["beta_hat"],
            row["eta_hat"],
            row["gamma_hat"],
            row["beta"],
            row["eta"],
            row["gamma"],
        )
        for name, value in errors.items():
            param_errors[name].append(value)

        for R in R_levels:
            quantile_errors[R].append(
                quantile_relative_error(
                    row["beta_hat"],
                    row["eta_hat"],
                    row["gamma_hat"],
                    row["beta"],
                    row["eta"],
                    row["gamma"],
                    R,
                )
            )

    param_distribution = {
        name: summarize_relative_errors(values)
        for name, values in param_errors.items()
    }
    quantile_distribution = {
        R: summarize_relative_errors(values)
        for R, values in quantile_errors.items()
    }

    output["param_distribution"] = param_distribution
    output["quantile_distribution"] = quantile_distribution

    for name, summary in param_distribution.items():
        for key, value in summary.items():
            output[f"{key}_{name}"] = value

    for R, summary in quantile_distribution.items():
        r_key = str(R).replace(".", "p")
        for key, value in summary.items():
            output[f"{key}_x_r{r_key}"] = value

    return output
