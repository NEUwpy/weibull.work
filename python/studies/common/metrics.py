"""
统一评价指标模块

供蒙特卡洛框架和 AI 训练脚本共同调用。
三态互斥：success / failure / outlier。

规范来源：AI辅助三参数威布尔参数估计重构与实验设计总纲 第 4 节
"""

import math
import numpy as np
from typing import List, Dict, Optional, Tuple


# ============================================================
# 默认参数
# ============================================================

DEFAULT_R_LEVELS = (0.995, 0.990, 0.950, 0.900)
DEFAULT_NE_THRESHOLD = 1.0


# ============================================================
# 层 1：单样本基础指标
# ============================================================

def ne(beta_hat: float, eta_hat: float, gamma_hat: float,
       beta: float, eta: float, gamma: float) -> float:
    """归一化综合误差 NE

    NE = sqrt(
        ((beta_hat - beta) / beta)^2
      + ((eta_hat - eta) / eta)^2
      + ((gamma_hat - gamma) / eta)^2
    )

    gamma 使用 eta 归一化，避免 gamma=0 时的分母问题。
    """
    return math.sqrt(
        ((beta_hat - beta) / beta) ** 2
        + ((eta_hat - eta) / eta) ** 2
        + ((gamma_hat - gamma) / eta) ** 2
    )


def quantile_true(beta: float, eta: float, gamma: float, R: float) -> float:
    """真实分位点 x_R = gamma + eta * (-ln(R))^(1/beta)"""
    return gamma + eta * (-math.log(R)) ** (1.0 / beta)


def quantile_est(beta_hat: float, eta_hat: float, gamma_hat: float, R: float) -> float:
    """估计分位点 x_hat_R = gamma_hat + eta_hat * (-ln(R))^(1/beta_hat)"""
    return gamma_hat + eta_hat * (-math.log(R)) ** (1.0 / beta_hat)


def nqe_R(beta_hat: float, eta_hat: float, gamma_hat: float,
          beta: float, eta: float, gamma: float, R: float) -> float:
    """归一化分位点误差 |x̂_R - x_R| / eta

    NQE_R 用 eta 归一化，比 RE_QR（用 x_R 归一化）更稳健，
    适合 x_R 较小或接近边界时作为主参考。
    """
    x_r = quantile_true(beta, eta, gamma, R)
    x_hat_r = quantile_est(beta_hat, eta_hat, gamma_hat, R)
    return abs(x_hat_r - x_r) / eta


def re_R(beta_hat: float, eta_hat: float, gamma_hat: float,
         beta: float, eta: float, gamma: float, R: float) -> float:
    """相对分位点误差 |x̂_R - x_R| / x_R"""
    x_r = quantile_true(beta, eta, gamma, R)
    x_hat_r = quantile_est(beta_hat, eta_hat, gamma_hat, R)
    return abs(x_hat_r - x_r) / x_r


# ============================================================
# 层 2：状态判定
# ============================================================

def check_status(
    beta_hat: float, eta_hat: float, gamma_hat: float,
    beta: float, eta: float, gamma: float,
    converged: bool = True,
    ne_threshold: float = DEFAULT_NE_THRESHOLD
) -> str:
    """判定单样本状态：success / failure / outlier

    判定顺序：
    1. beta_hat 或 eta_hat 非有限或 <= 0 → failure
    2. gamma_hat 非有限 → failure（不要求 >0，但必须 finite）
    3. converged 为 False → failure
    4. NE > ne_threshold → outlier
    5. 其余 → success

    Args:
        beta_hat, eta_hat, gamma_hat: 估计值
        beta, eta, gamma: 真值（用于计算 NE）
        converged: 方法自身报告是否成功
        ne_threshold: outlier 判定阈值，默认 1.0

    Returns:
        "success" | "failure" | "outlier"
    """
    # 检查 beta_hat
    if not math.isfinite(beta_hat) or beta_hat <= 0:
        return "failure"

    # 检查 eta_hat
    if not math.isfinite(eta_hat) or eta_hat <= 0:
        return "failure"

    # 检查 gamma_hat（不要求 >0，但必须 finite）
    if not math.isfinite(gamma_hat):
        return "failure"

    # 检查方法自身报告
    if not converged:
        return "failure"

    # 计算 NE 并判定 outlier
    ne_value = ne(beta_hat, eta_hat, gamma_hat, beta, eta, gamma)
    if ne_value > ne_threshold:
        return "outlier"

    return "success"


# ============================================================
# 层 3：批量聚合
# ============================================================

def aggregate_param_metrics(
    results: List[Dict],
    R_levels: Tuple[float, ...] = DEFAULT_R_LEVELS,
    ne_threshold: float = DEFAULT_NE_THRESHOLD
) -> Dict:
    """批量计算全部指标

    Args:
        results: 每个元素为字典，包含：
            - beta_hat, eta_hat, gamma_hat: 估计值（failure 时为 None）
            - beta, eta, gamma: 真值
            - time: 运行时间（秒）
            - converged: 方法自身报告是否成功
        R_levels: 可靠度水平，默认 (0.995, 0.990, 0.950, 0.900)
        ne_threshold: outlier 判定阈值，默认 1.0，与 check_status() 一致

    Returns:
        汇总字典，包含参数视角、分位点视角和可用性视角的全部指标。
        三态互斥：failure_count + outlier_count + success_count = n_total。
        精度指标仅统计 success 样本。
    """
    n_total = len(results)
    if n_total == 0:
        return {"n_total": 0}

    # 分类
    successes = []
    failures = 0
    outliers = 0

    for r in results:
        beta_hat = r.get("beta_hat")
        eta_hat = r.get("eta_hat")
        gamma_hat = r.get("gamma_hat")
        converged = r.get("converged", True)

        # failure 情况：None 或非法值
        if (beta_hat is None or eta_hat is None or gamma_hat is None):
            failures += 1
            continue

        status = check_status(
            beta_hat, eta_hat, gamma_hat,
            r["beta"], r["eta"], r["gamma"],
            converged=converged,
            ne_threshold=ne_threshold
        )

        if status == "failure":
            failures += 1
        elif status == "outlier":
            outliers += 1
        else:
            successes.append(r)

    n_success = len(successes)
    n_failure = failures
    n_outlier = outliers

    result = {
        "n_total": n_total,
        "n_success": n_success,
        "n_failure": n_failure,
        "n_outlier": n_outlier,
        "failure_rate": n_failure / n_total,
        "outlier_rate": n_outlier / n_total,
        "success_rate": n_success / n_total,
    }

    if n_success == 0:
        return result

    # --- 参数视角（仅 success 样本）---
    beta_hats = np.array([r["beta_hat"] for r in successes])
    eta_hats = np.array([r["eta_hat"] for r in successes])
    gamma_hats = np.array([r["gamma_hat"] for r in successes])
    betas = np.array([r["beta"] for r in successes])
    etas = np.array([r["eta"] for r in successes])
    gammas = np.array([r["gamma"] for r in successes])
    times = np.array([r.get("time", 0) for r in successes])

    # NE
    ne_values = np.array([
        ne(bh, eh, gh, b, e, g)
        for bh, eh, gh, b, e, g in zip(beta_hats, eta_hats, gamma_hats, betas, etas, gammas)
    ])
    result["ne_mean"] = float(np.mean(ne_values))
    result["ne_std"] = float(np.std(ne_values))

    # Bias（按参数）
    result["bias_beta"] = float(np.mean(beta_hats - betas))
    result["bias_eta"] = float(np.mean(eta_hats - etas))
    result["bias_gamma"] = float(np.mean(gamma_hats - gammas))

    # MAE（按参数）
    result["mae_beta"] = float(np.mean(np.abs(beta_hats - betas)))
    result["mae_eta"] = float(np.mean(np.abs(eta_hats - etas)))
    result["mae_gamma"] = float(np.mean(np.abs(gamma_hats - gammas)))

    # RMSE（按参数）
    result["rmse_beta"] = float(np.sqrt(np.mean((beta_hats - betas) ** 2)))
    result["rmse_eta"] = float(np.sqrt(np.mean((eta_hats - etas) ** 2)))
    result["rmse_gamma"] = float(np.sqrt(np.mean((gamma_hats - gammas) ** 2)))

    # Time
    result["time_mean"] = float(np.mean(times))
    result["time_p50"] = float(np.percentile(times, 50))
    result["time_p95"] = float(np.percentile(times, 95))

    # --- 分位点视角（仅 success 样本）---
    quantile_results = {}
    for R in R_levels:
        nqe_values = []
        re_values = []
        bias_qr_values = []

        for r in successes:
            x_r = quantile_true(r["beta"], r["eta"], r["gamma"], R)
            x_hat_r = quantile_est(r["beta_hat"], r["eta_hat"], r["gamma_hat"], R)
            bias_qr_values.append(x_hat_r - x_r)
            nqe_values.append(abs(x_hat_r - x_r) / r["eta"])
            re_values.append(abs(x_hat_r - x_r) / x_r)

        nqe_arr = np.array(nqe_values)
        re_arr = np.array(re_values)
        bias_arr = np.array(bias_qr_values)

        quantile_results[R] = {
            "bias": float(np.mean(bias_arr)),
            "mae": float(np.mean(np.abs(bias_arr))),
            "rmse": float(np.sqrt(np.mean(bias_arr ** 2))),
            "nqe_mean": float(np.mean(nqe_arr)),
            "nqe_std": float(np.std(nqe_arr)),
            "re_mean": float(np.mean(re_arr)),
        }

    result["quantile"] = quantile_results

    return result
