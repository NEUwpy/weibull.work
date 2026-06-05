"""
S4.5 MDM failure 深度诊断

目标：区分 MDM failure 的四种可能原因：
1. 理论失败：梯度范围不含 offset（算法在此参数下确实无解）
2. 配置失败：梯度范围含 offset 但 gamma_steps 太粗未检测到
3. 实现失败：数值噪声导致符号变化检测失败
4. 判定口径失败：有合理解但被 check_status 判为 failure

对 failure 样本做抽样复核 + 替代策略测试。
"""

import sys
import os
import json
import numpy as np
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample
from studies.common.metrics import param_relative_errors, summarize_relative_errors
from base import WeibullBase


def diagnose_single_sample(sample, offset, gamma_steps):
    """对单个样本做 MDM 全流程诊断。

    返回诊断字典，包含梯度范围、是否有交点、替代策略结果等。
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

    from scipy.optimize import minimize_scalar

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

    # 检查第一轮
    diffs1 = grads1 - offset
    sign_changes1 = np.where(np.diff(np.sign(diffs1)))[0]

    # 第二轮搜索（如果第一轮无交点）
    if len(sign_changes1) == 0:
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
        sign_changes = sign_changes1

    # 诊断信息
    grad_min = float(np.min(grads))
    grad_max = float(np.max(grads))
    offset_in_range = grad_min <= offset <= grad_max
    has_intersection = len(sign_changes) > 0

    diag = {
        "t_min": float(t_min),
        "n": n,
        "offset": offset,
        "gamma_steps": gamma_steps,
        "grad_min": grad_min,
        "grad_max": grad_max,
        "offset_in_range": offset_in_range,
        "has_intersection": has_intersection,
        "n_sign_changes": len(sign_changes),
    }

    # 替代策略 1：使用最小 sigma 对应的 gamma（忽略 offset 判据）
    min_sigma_idx = np.argmin(sigma_mins)
    fallback_gamma = float(gammas[min_sigma_idx])
    fallback_beta = float(best_betas[min_sigma_idx])
    denom = np.power(neg_ln_1_minus_F, 1.0 / fallback_beta)
    etas = (t - fallback_gamma) / denom
    fallback_eta = float(np.mean(etas))

    diag["fallback_min_sigma"] = {
        "gamma": fallback_gamma,
        "beta": fallback_beta,
        "eta": fallback_eta,
    }

    # 替代策略 2：如果 offset 在梯度范围内但未检测到交点，
    # 用更细的 gamma_steps 重试
    if offset_in_range and not has_intersection:
        finer_steps = gamma_steps * 5
        gammas_fine = np.linspace(0, t_min * 0.999999, finer_steps)
        sigma_fine = []
        betas_fine = []
        for g in gammas_fine:
            b, sig = find_best_beta_for_gamma(g)
            sigma_fine.append(sig)
            betas_fine.append(b)
        sigma_fine = np.array(sigma_fine)
        betas_fine = np.array(betas_fine)
        grads_fine = np.gradient(sigma_fine, gammas_fine)
        diffs_fine = grads_fine - offset
        sign_changes_fine = np.where(np.diff(np.sign(diffs_fine)))[0]

        diag["finer_grid_test"] = {
            "steps": finer_steps,
            "has_intersection": len(sign_changes_fine) > 0,
            "n_sign_changes": len(sign_changes_fine),
        }

        if len(sign_changes_fine) > 0:
            idx = sign_changes_fine[-1]
            y1, y2 = diffs_fine[idx], diffs_fine[idx + 1]
            x1, x2 = gammas_fine[idx], gammas_fine[idx + 1]
            if y2 != y1:
                recovered_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
            else:
                recovered_gamma = x1
            recovered_beta, _ = find_best_beta_for_gamma(recovered_gamma)
            denom = np.power(neg_ln_1_minus_F, 1.0 / recovered_beta)
            etas = (t - recovered_gamma) / denom
            recovered_eta = float(np.mean(etas))
            diag["finer_grid_test"]["recovered"] = {
                "gamma": float(recovered_gamma),
                "beta": float(recovered_beta),
                "eta": recovered_eta,
            }

    return diag


def run_diagnosis():
    """在验证参数空间上对 failure 样本做诊断。"""
    BETAS = [1.5, 2.0, 3.0]
    ETA = 100.0
    GAMMA_ETAS = [0.0, 0.10]
    NS = [10, 30]
    N_REPEATS = 100
    OFFSET = 0.1
    GAMMA_STEPS = 20

    # 收集所有 failure 样本
    failure_samples = []
    total = 0

    for beta in BETAS:
        for gamma_eta in GAMMA_ETAS:
            gamma = gamma_eta * ETA
            for n in NS:
                for rid in range(N_REPEATS):
                    total += 1
                    sample = generate_sample(beta, ETA, gamma, n, rid)
                    diag = diagnose_single_sample(sample, OFFSET, GAMMA_STEPS)
                    if not diag["has_intersection"]:
                        diag["beta"] = beta
                        diag["eta"] = ETA
                        diag["gamma"] = gamma
                        diag["repeat_id"] = rid
                        failure_samples.append(diag)

    print(f"Total samples: {total}")
    print(f"Failure samples: {len(failure_samples)} ({len(failure_samples)/total*100:.1f}%)")
    print()

    # 分类 failure 原因
    offset_not_in_range = [s for s in failure_samples if not s["offset_in_range"]]
    offset_in_range = [s for s in failure_samples if s["offset_in_range"]]

    print("=== Failure 原因分类 ===")
    print(f"  梯度范围不含 offset（理论无交点）: {len(offset_not_in_range)} ({len(offset_not_in_range)/len(failure_samples)*100:.1f}%)")
    print(f"  梯度范围含 offset 但未检测到交点:  {len(offset_in_range)} ({len(offset_in_range)/len(failure_samples)*100:.1f}%)")
    print()

    # 对"梯度范围含 offset"的样本，检查更细网格能否恢复
    if offset_in_range:
        recovered = 0
        for s in offset_in_range:
            if "finer_grid_test" in s and s["finer_grid_test"].get("has_intersection"):
                recovered += 1
        print(f"  其中 {recovered}/{len(offset_in_range)} 个样本用更细网格可恢复交点")
        print()

    # failure 样本的参数分布
    print("=== Failure 样本参数分布 ===")
    beta_dist = Counter(s["beta"] for s in failure_samples)
    gamma_dist = Counter(s["gamma"] for s in failure_samples)
    n_dist = Counter(s["n"] for s in failure_samples)
    print(f"  beta: {dict(sorted(beta_dist.items()))}")
    print(f"  gamma: {dict(sorted(gamma_dist.items()))}")
    print(f"  n: {dict(sorted(n_dist.items()))}")
    print()

    # 梯度范围统计
    print("=== 梯度范围统计（failure 样本）===")
    grad_mins = [s["grad_min"] for s in failure_samples]
    grad_maxs = [s["grad_max"] for s in failure_samples]
    print(f"  grad_min: min={min(grad_mins):.4f}, max={max(grad_mins):.4f}, mean={np.mean(grad_mins):.4f}")
    print(f"  grad_max: min={min(grad_maxs):.4f}, max={max(grad_maxs):.4f}, mean={np.mean(grad_maxs):.4f}")
    print(f"  offset={OFFSET}")
    print()

    # 替代策略评估：对 failure 样本用 fallback_min_sigma 计算 S2R 参数误差
    print("=== 替代策略：fallback_min_sigma（忽略 offset，用最小 sigma 的 gamma）===")
    fallback_beta_errors = []
    fallback_eta_errors = []
    fallback_gamma_errors = []
    for s in failure_samples:
        fb = s["fallback_min_sigma"]
        if fb["beta"] > 0 and fb["eta"] > 0 and np.isfinite(fb["eta"]):
            errors = param_relative_errors(
                fb["beta"], fb["eta"], fb["gamma"],
                s["beta"], s["eta"], s["gamma"],
            )
            fallback_beta_errors.append(errors["beta"])
            fallback_eta_errors.append(errors["eta"])
            fallback_gamma_errors.append(errors["gamma"])

    if fallback_beta_errors:
        beta_summary = summarize_relative_errors(fallback_beta_errors)
        eta_summary = summarize_relative_errors(fallback_eta_errors)
        gamma_summary = summarize_relative_errors(fallback_gamma_errors)
        print(f"  n={len(fallback_beta_errors)}")
        print(f"  beta MdAPE={beta_summary['mdape']:.4f}, P95(|e|)={beta_summary['p95_abs']:.4f}")
        print(f"  eta  MdAPE={eta_summary['mdape']:.4f}, P95(|e|)={eta_summary['p95_abs']:.4f}")
        print(f"  gamma MdAE/eta={gamma_summary['mdape']:.4f}, P95(|e|)={gamma_summary['p95_abs']:.4f}")
    print()

    # 抽样输出前 5 个 failure 样本的详细诊断
    print("=== 前 5 个 failure 样本详细诊断 ===")
    for i, s in enumerate(failure_samples[:5]):
        print(f"\n--- Sample {i+1} ---")
        print(f"  beta={s['beta']}, eta={s['eta']}, gamma={s['gamma']}, n={s['n']}, rid={s['repeat_id']}")
        print(f"  t_min={s['t_min']:.4f}")
        print(f"  grad_min={s['grad_min']:.6f}, grad_max={s['grad_max']:.6f}")
        print(f"  offset={s['offset']}, offset_in_range={s['offset_in_range']}")
        fb = s['fallback_min_sigma']
        print(f"  fallback: gamma={fb['gamma']:.4f}, beta={fb['beta']:.4f}, eta={fb['eta']:.4f}")
        if "finer_grid_test" in s:
            fg = s["finer_grid_test"]
            print(f"  finer_grid({fg['steps']}): has_intersection={fg['has_intersection']}")
            if "recovered" in fg:
                r = fg["recovered"]
                print(f"    recovered: gamma={r['gamma']:.4f}, beta={r['beta']:.4f}, eta={r['eta']:.4f}")

    return failure_samples


if __name__ == "__main__":
    samples = run_diagnosis()
