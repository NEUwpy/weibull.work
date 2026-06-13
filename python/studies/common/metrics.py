"""
统一评价指标模块

当前默认主口径遵循第七轮报告：
- 参数视角：Bias、SD、RMSE、MAE；beta/eta 可附相对 Bias/RMSE，gamma 不输出相对指标。
- 工程寿命视角：x_R 的 Bias、SD、RMSE、MAE 与相对 Bias/RMSE。
- S2R 中位数族与尾部指标保留为 diagnostics，用于风险诊断，不再作为唯一主口径。

维护约定：
- 本模块是指标规范页面 `/help/metrics` 的可执行实现。
- `/help/metrics` 是本模块的可读规范说明。
- 修改本模块任一公式、字段名或判定口径时，必须同步修改
  `src/app/help/metrics/page.tsx`；反过来，页面规范变更也必须同步本模块。
"""

import math
from typing import Dict, List, Optional, Tuple

import numpy as np


DEFAULT_R_LEVELS = (0.50, 0.90, 0.95, 0.99, 0.999)
DEFAULT_STANDARD_R_LEVELS = (0.95, 0.99)


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


def param_absolute_errors(
    beta_hat: float,
    eta_hat: float,
    gamma_hat: float,
    beta: float,
    eta: float,
    gamma: float,
) -> Dict[str, float]:
    """返回参数视角的原始尺度带符号误差。"""
    return {
        "beta": beta_hat - beta,
        "eta": eta_hat - eta,
        "gamma": gamma_hat - gamma,
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

    返回字段用于 S2R diagnostics：
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


def _empty_standard_summary() -> Dict[str, Optional[float]]:
    return {
        "n": 0,
        "bias": None,
        "sd": None,
        "mse": None,
        "rmse": None,
        "mae": None,
    }


def summarize_standard_errors(errors: List[float] | np.ndarray) -> Dict[str, Optional[float]]:
    """汇总第七轮常用指标族。

    输入必须是带符号误差：
    - 原始尺度误差：theta_hat - theta
    - 或相对误差：(theta_hat - theta) / theta

    SD 使用样本标准差 ddof=1；只有 1 个有效值时 SD 记为 0。
    """
    arr = np.asarray(errors, dtype=float)
    arr = arr[np.isfinite(arr)]

    if arr.size == 0:
        return _empty_standard_summary()

    mse = float(np.mean(arr ** 2))
    return {
        "n": int(arr.size),
        "bias": float(np.mean(arr)),
        "sd": float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0,
        "mse": mse,
        "rmse": float(math.sqrt(mse)),
        "mae": float(np.mean(np.abs(arr))),
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
    """批量计算 S2R 诊断指标。

    该函数保留给 diagnostics 使用；默认主评价聚合请调用
    `aggregate_standard_metrics()`。

    Args:
        results: 每个元素包含 beta_hat/eta_hat/gamma_hat、beta/eta/gamma、
            converged，可选 time、sample_min。
        R_levels: S2R 诊断层需要报告的可靠度分位点。

    Returns:
        S2R 诊断汇总。参数视角位于 `param_distribution`，工程分位点视角位于
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


def aggregate_standard_metrics(
    results: List[Dict],
    R_levels: Tuple[float, ...] = DEFAULT_STANDARD_R_LEVELS,
    diagnostic_R_levels: Tuple[float, ...] = DEFAULT_R_LEVELS,
    include_diagnostics: bool = True,
) -> Dict:
    """批量计算第七轮常用指标，并嵌入 S2R diagnostics。

    gamma 不输出相对指标；beta/eta 与 x_R 输出相对指标。
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

    if include_diagnostics:
        output["diagnostics"] = aggregate_param_metrics(
            results,
            R_levels=diagnostic_R_levels,
        )

    if n_valid == 0:
        return output

    param_abs_errors = {"beta": [], "eta": [], "gamma": []}
    param_rel_errors = {"beta": [], "eta": []}
    quantile_abs_errors = {R: [] for R in R_levels}
    quantile_rel_errors = {R: [] for R in R_levels}

    for row in valid_rows:
        abs_errors = param_absolute_errors(
            row["beta_hat"],
            row["eta_hat"],
            row["gamma_hat"],
            row["beta"],
            row["eta"],
            row["gamma"],
        )
        rel_errors = param_relative_errors(
            row["beta_hat"],
            row["eta_hat"],
            row["gamma_hat"],
            row["beta"],
            row["eta"],
            row["gamma"],
        )

        for name in ("beta", "eta", "gamma"):
            param_abs_errors[name].append(abs_errors[name])
        for name in ("beta", "eta"):
            param_rel_errors[name].append(rel_errors[name])

        for R in R_levels:
            x_true = quantile_true(row["beta"], row["eta"], row["gamma"], R)
            x_hat = quantile_est(row["beta_hat"], row["eta_hat"], row["gamma_hat"], R)
            abs_error = x_hat - x_true
            quantile_abs_errors[R].append(abs_error)
            quantile_rel_errors[R].append(abs_error / x_true)

    param_standard = {}
    for name in ("beta", "eta", "gamma"):
        param_standard[name] = {
            "absolute": summarize_standard_errors(param_abs_errors[name]),
        }
        if name in param_rel_errors:
            param_standard[name]["relative"] = summarize_standard_errors(param_rel_errors[name])

    quantile_standard = {
        R: {
            "absolute": summarize_standard_errors(quantile_abs_errors[R]),
            "relative": summarize_standard_errors(quantile_rel_errors[R]),
        }
        for R in R_levels
    }

    output["param_standard"] = param_standard
    output["quantile_standard"] = quantile_standard

    for name, group in param_standard.items():
        for key, value in group["absolute"].items():
            output[f"{key}_{name}"] = value
        if "relative" in group:
            for key, value in group["relative"].items():
                output[f"rel_{key}_{name}"] = value

    for R, group in quantile_standard.items():
        r_key = str(R).replace(".", "p")
        for key, value in group["absolute"].items():
            output[f"{key}_x_r{r_key}"] = value
        for key, value in group["relative"].items():
            output[f"rel_{key}_x_r{r_key}"] = value

    return output
