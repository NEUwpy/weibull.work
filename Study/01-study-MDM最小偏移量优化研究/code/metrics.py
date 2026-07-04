"""
Study/01 指标计算模块

核心指标：
- J₁ = √(mean_i[(Δβ/β)² + (Δη/η)² + (Δγ/η)²])  — 主指标（D1 决策）
- Bias_θ = mean(θ̂ - θ)                              — 辅助诊断
- SD_θ = std(θ̂)                                     — 辅助诊断
- 失败率 = n_failure / n_total                        — gate 条件

设计依据：
- J₁ 逐样本计算后开方（NOT 先开方再平均）
- γ 归一化除 η（尺度参数真值），不除 γ 自身
- 等权 w_β = w_η = w_γ = 1
- 文献先例：182-050 / 182-097 的 Joint RMSE；J₁ 为相对误差变体
"""

import math
import numpy as np
from typing import Dict, List, Optional, Tuple


# ============================================================
# 单样本 J₁ 贡献
# ============================================================

def j1_single(
    beta_hat: float, eta_hat: float, gamma_hat: float,
    beta: float, eta: float, gamma: float,
) -> float:
    """计算单个样本对 J₁ 的贡献（未开方）。

    返回 (Δβ/β)² + (Δη/η)² + (Δγ/η)²
    最终 J₁ 是对所有样本取均值后再开方。
    """
    r_beta = (beta_hat - beta) / beta
    r_eta = (eta_hat - eta) / eta
    r_gamma = (gamma_hat - gamma) / eta   # γ 除 η，不除 γ 自身
    return r_beta**2 + r_eta**2 + r_gamma**2


# ============================================================
# 聚合 J₁
# ============================================================

def compute_j1(
    estimates: List[Dict],
    beta: float, eta: float, gamma: float,
) -> Optional[float]:
    """计算一组估计的 J₁ 值。

    Args:
        estimates: [{"beta_hat":..., "eta_hat":..., "gamma_hat":...}, ...]
                   只含成功收敛的估计
        beta, eta, gamma: 真值

    Returns:
        J₁ = √(mean_i[...])，或 None（若无有效估计）
    """
    if not estimates:
        return None

    contributions = []
    for est in estimates:
        bh = est["beta_hat"]
        eh = est["eta_hat"]
        gh = est["gamma_hat"]
        if bh is None or eh is None or gh is None:
            continue
        if not all(math.isfinite(v) for v in [bh, eh, gh]):
            continue
        contributions.append(j1_single(bh, eh, gh, beta, eta, gamma))

    if not contributions:
        return None

    return math.sqrt(np.mean(contributions))


# ============================================================
# 完整指标聚合（J₁ + Bias + SD + 失败率）
# ============================================================

def aggregate_metrics(
    results: List[Dict],
    beta: float, eta: float, gamma: float,
) -> Dict:
    """计算一组 MC 重复的完整指标。

    Args:
        results: 每个元素含 beta_hat/eta_hat/gamma_hat/converged 字段
        beta, eta, gamma: 真值

    Returns:
        {
            "n_total": int,
            "n_valid": int,
            "n_failure": int,
            "failure_rate": float,
            "J1": float | None,
            "bias_beta": float, "sd_beta": float,
            "bias_eta": float, "sd_eta": float,
            "bias_gamma": float, "sd_gamma": float,
        }
    """
    n_total = len(results)
    if n_total == 0:
        return {"n_total": 0, "n_valid": 0, "n_failure": 0, "failure_rate": 0.0,
                "J1": None}

    valid = []
    n_failure = 0

    for row in results:
        bh = row.get("beta_hat")
        eh = row.get("eta_hat")
        gh = row.get("gamma_hat")
        conv = row.get("converged", True)

        if bh is None or eh is None or gh is None or not conv:
            n_failure += 1
            continue
        if not all(math.isfinite(v) for v in [bh, eh, gh]):
            n_failure += 1
            continue
        # 物理约束检查
        if bh <= 0 or eh <= 0:
            n_failure += 1
            continue
        valid.append(row)

    n_valid = len(valid)
    output = {
        "n_total": n_total,
        "n_valid": n_valid,
        "n_failure": n_failure,
        "failure_rate": n_failure / n_total if n_total > 0 else 0.0,
    }

    if n_valid == 0:
        output["J1"] = None
        for name in ("beta", "eta", "gamma"):
            output[f"bias_{name}"] = None
            output[f"sd_{name}"] = None
        return output

    # J₁
    output["J1"] = compute_j1(valid, beta, eta, gamma)

    # Bias & SD
    for name, true_val in [("beta", beta), ("eta", eta), ("gamma", gamma)]:
        hats = np.array([row[f"{name}_hat"] for row in valid])
        output[f"bias_{name}"] = float(np.mean(hats) - true_val)
        output[f"sd_{name}"] = float(np.std(hats, ddof=1)) if n_valid > 1 else 0.0

    return output
