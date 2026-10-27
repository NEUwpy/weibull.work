"""
MDM 方法变体
Minimum Discrepancy Method Variants

提供四种 MDM 实现，用于研究约束边界处理对 MDM 估计的影响：
- mdm_offset_strict: 严格交点法，无交点返回 failure（当前默认行为）
- mdm_offset_constrained: 有交点用交点；无交点返回约束域最优解
- mdm_min_sigma: 网格搜索下的最小 sigma 解，不使用 offset 判据
- mdm_allow_negative_gamma: 允许负 gamma 的严格交点法（仅诊断用）
"""

import numpy as np
from scipy.optimize import minimize_scalar

from base import WeibullBase


def _compute_mdm_search(sample, offset, gamma_steps, gamma_min=0.0,
                        gamma_max_ratio=0.999999):
    """MDM 核心搜索逻辑，所有变体共享。

    Args:
        sample: 排序后的样本
        offset: 梯度偏移阈值
        gamma_steps: 每轮搜索步数
        gamma_min: gamma 搜索下界（默认 0.0）
        gamma_max_ratio: gamma 搜索上界相对于 t_min 的比例

    Returns:
        (gammas, sigma_mins, best_betas, grads, diffs, sign_changes, t_min,
         neg_ln_1_minus_F)
    """
    wb = WeibullBase(sample)
    t = wb.data
    n = wb.n
    ranks = wb._median_ranks()
    neg_ln_1_minus_F = -np.log(1 - ranks)
    t_min = t[0]

    def calculate_eta_std(beta, gamma, current_t):
        if beta <= 0:
            return float('inf')
        denom = np.power(neg_ln_1_minus_F, 1.0 / beta)
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

    # 第一轮搜索
    gammas1 = np.linspace(gamma_min, t_min * 0.99, gamma_steps)
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

    # 第二轮搜索（仅在第一轮无交点时）
    if len(sign_changes) == 0:
        gammas2 = np.linspace(t_min * 0.99, t_min * gamma_max_ratio,
                              gamma_steps)
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
        diffs = np.concatenate([diffs1, grads2 - offset])
        sign_changes = np.where(np.diff(np.sign(diffs)))[0]
    else:
        gammas = gammas1
        sigma_mins = sigma_mins1
        best_betas = best_betas1
        grads = grads1
        diffs = diffs1

    return (gammas, sigma_mins, best_betas, grads, diffs, sign_changes,
            t_min, neg_ln_1_minus_F, find_best_beta_for_gamma)


def _find_intersection(gammas, diffs, sign_changes, find_best_beta_for_gamma):
    """从交点列表中选取最优交点，返回 (gamma, beta)。"""
    idx = sign_changes[-1]  # 最接近 t_min 的交点
    y1, y2 = diffs[idx], diffs[idx + 1]
    x1, x2 = gammas[idx], gammas[idx + 1]
    if y2 != y1:
        found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
    else:
        found_gamma = x1
    found_beta, _ = find_best_beta_for_gamma(found_gamma)
    return found_gamma, found_beta


def _compute_eta(sample, found_beta, found_gamma, neg_ln_1_minus_F):
    """给定 beta 和 gamma，计算 eta 均值。"""
    wb = WeibullBase(sample)
    t = wb.data
    denom = np.power(neg_ln_1_minus_F, 1.0 / found_beta)
    etas = (t - found_gamma) / denom
    return float(np.mean(etas))


def mdm_offset_strict(sample, offset=0.1, gamma_steps=20, **kwargs):
    """严格交点法：无交点返回 failure。

    这是 S4.5 之前的默认行为。保留用于诊断和对比。
    """
    result = _compute_mdm_search(sample, offset, gamma_steps)
    (gammas, sigma_mins, best_betas, grads, diffs, sign_changes,
     t_min, neg_ln_1_minus_F, find_best_beta_for_gamma) = result

    if len(sign_changes) > 0:
        found_gamma, found_beta = _find_intersection(
            gammas, diffs, sign_changes, find_best_beta_for_gamma)
        found_eta = _compute_eta(sample, found_beta, found_gamma,
                                 neg_ln_1_minus_F)
        return float(found_beta), float(found_eta), float(found_gamma)
    else:
        return None, None, None


def mdm_offset_constrained(sample, offset=0.1, gamma_steps=20, **kwargs):
    """约束交点法：有交点用交点；无交点返回约束域最优解。

    无交点时的策略（基于采样点上的 diff 值，不假设曲线单调性）：
    - diff 全正（采样点上梯度均高于 offset）→ gamma=0 处的解（boundary_left）
    - diff 全负（采样点上梯度均低于 offset）→ 最小 sigma 处的解（boundary_right）
    - 其他情况（有正有负但未检测到符号变化，可能是数值噪声）→ 最接近 offset 的点

    Returns:
        (beta_hat, eta_hat, gamma_hat) — 不返回 None

    Side effects:
        mdm_offset_constrained.last_fallback_reason — 本次调用的解来源：
            "root": 找到 offset 交点
            "boundary_left": 无交点，梯度均高于 offset，选 gamma≈0
            "boundary_right": 无交点，梯度均低于 offset，选最小 sigma
            "closest_offset": 无交点，有正有负但无符号变化，选最接近 offset 的点
    """
    result = _compute_mdm_search(sample, offset, gamma_steps)
    (gammas, sigma_mins, best_betas, grads, diffs, sign_changes,
     t_min, neg_ln_1_minus_F, find_best_beta_for_gamma) = result

    if len(sign_changes) > 0:
        found_gamma, found_beta = _find_intersection(
            gammas, diffs, sign_changes, find_best_beta_for_gamma)
        mdm_offset_constrained.last_fallback_reason = "root"
    else:
        # 约束域内无交点，返回最优边界解
        min_idx = int(np.argmin(sigma_mins))
        if np.all(diffs >= 0):
            # 采样点上梯度均高于 offset → 选 gamma 最小端
            found_gamma = float(gammas[0])
            found_beta = float(best_betas[0])
            mdm_offset_constrained.last_fallback_reason = "boundary_left"
        elif np.all(diffs <= 0):
            # 采样点上梯度均低于 offset → 选最小 sigma
            found_gamma = float(gammas[min_idx])
            found_beta = float(best_betas[min_idx])
            mdm_offset_constrained.last_fallback_reason = "boundary_right"
        else:
            # 有正有负但未检测到交点（数值噪声）→ 最接近 offset 的点
            closest_idx = int(np.argmin(np.abs(diffs)))
            found_gamma = float(gammas[closest_idx])
            found_beta = float(best_betas[closest_idx])
            mdm_offset_constrained.last_fallback_reason = "closest_offset"

    found_eta = _compute_eta(sample, found_beta, found_gamma,
                             neg_ln_1_minus_F)
    return float(found_beta), float(found_eta), float(found_gamma)


def _compute_sigma_curve(sample, gamma_steps, gamma_min=0.0,
                         gamma_max_ratio=0.999999):
    """独立的 sigma 曲线搜索，覆盖完整 [gamma_min, t_min) 范围。

    不依赖 offset 判据，不做两段分割。始终搜索完整连续区间。
    供 mdm_min_sigma 使用。

    Returns:
        (gammas, sigma_mins, best_betas, t_min, neg_ln_1_minus_F,
         find_best_beta_for_gamma)
    """
    wb = WeibullBase(sample)
    t = wb.data
    n = wb.n
    ranks = wb._median_ranks()
    neg_ln_1_minus_F = -np.log(1 - ranks)
    t_min = t[0]

    def calculate_eta_std(beta, gamma, current_t):
        if beta <= 0:
            return float('inf')
        denom = np.power(neg_ln_1_minus_F, 1.0 / beta)
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

    gammas = np.linspace(gamma_min, t_min * gamma_max_ratio, gamma_steps)
    sigma_mins = []
    best_betas = []
    for g in gammas:
        b, sig = find_best_beta_for_gamma(g)
        sigma_mins.append(sig)
        best_betas.append(b)
    sigma_mins = np.array(sigma_mins)
    best_betas = np.array(best_betas)

    return (gammas, sigma_mins, best_betas, t_min, neg_ln_1_minus_F,
            find_best_beta_for_gamma)


def mdm_min_sigma(sample, offset=0.1, gamma_steps=20, **kwargs):
    """网格搜索下的最小 sigma 解：返回离散采样点中使伪尺度参数标准差最小的 gamma。

    使用独立的完整区间搜索（不做两段分割），在 gamma_steps 个等距采样点上
    找到 sigma 最小的位置。结果是离散网格上的最优解，不是连续意义上的全局最小值。
    offset 参数仅用于兼容统一调用接口。
    """
    result = _compute_sigma_curve(sample, gamma_steps)
    (gammas, sigma_mins, best_betas, t_min, neg_ln_1_minus_F,
     find_best_beta_for_gamma) = result

    min_idx = int(np.argmin(sigma_mins))
    found_gamma = float(gammas[min_idx])
    found_beta = float(best_betas[min_idx])
    found_eta = _compute_eta(sample, found_beta, found_gamma,
                             neg_ln_1_minus_F)
    return float(found_beta), float(found_eta), float(found_gamma)


def mdm_allow_negative_gamma(sample, offset=0.1, gamma_steps=20, **kwargs):
    """允许负 gamma 的严格交点法（仅诊断用）。

    搜索范围扩展到 [-eta, t_min)，在更大域内寻找 offset 交点。
    无交点时返回 None。
    """
    wb = WeibullBase(sample)
    t = wb.data
    eta_approx = np.mean(t)  # 粗略估计 eta 作为搜索下界

    result = _compute_mdm_search(
        sample, offset, gamma_steps,
        gamma_min=-eta_approx,
        gamma_max_ratio=0.999999
    )
    (gammas, sigma_mins, best_betas, grads, diffs, sign_changes,
     t_min, neg_ln_1_minus_F, find_best_beta_for_gamma) = result

    if len(sign_changes) > 0:
        found_gamma, found_beta = _find_intersection(
            gammas, diffs, sign_changes, find_best_beta_for_gamma)
        found_eta = _compute_eta(sample, found_beta, found_gamma,
                                 neg_ln_1_minus_F)
        return float(found_beta), float(found_eta), float(found_gamma)
    else:
        return None, None, None
