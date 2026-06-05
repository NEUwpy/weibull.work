"""
S4.5 MDM fallback 策略评估

比较三种策略在同一参数空间上的表现：
1. MDM 标准（no_intersection → failure）
2. MDM + fallback_min_sigma（no_intersection → 用最小 sigma 的 gamma）
3. MLE（作为参考）

评估维度：S2R 分布指标、failure_rate
"""

import sys
import os
import json
import time
import numpy as np
from scipy.optimize import minimize_scalar

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample
from studies.common.metrics import aggregate_param_metrics
from base import WeibullBase


BETAS = [1.5, 2.0, 3.0]
ETA = 100.0
GAMMA_ETAS = [0.0, 0.10]
NS = [10, 30]
N_REPEATS = 100
OFFSET = 0.1
GAMMA_STEPS = 20


def mdm_with_fallback(sample, offset=OFFSET, gamma_steps=GAMMA_STEPS):
    """MDM + fallback_min_sigma：无交点时用最小 sigma 的 gamma。"""
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

    # 搜索
    gammas1 = np.linspace(0, t_min * 0.99, gamma_steps)
    sigma_mins1, best_betas1 = [], []
    for g in gammas1:
        b, sig = find_best_beta_for_gamma(g)
        sigma_mins1.append(sig)
        best_betas1.append(b)
    sigma_mins1 = np.array(sigma_mins1)
    best_betas1 = np.array(best_betas1)
    grads1 = np.gradient(sigma_mins1, gammas1)

    diffs1 = grads1 - offset
    sign_changes1 = np.where(np.diff(np.sign(diffs1)))[0]

    if len(sign_changes1) == 0:
        gammas2 = np.linspace(t_min * 0.99, t_min * 0.999999, gamma_steps)
        sigma_mins2, best_betas2 = [], []
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
        diffs = diffs1
        sign_changes = sign_changes1

    if len(sign_changes) > 0:
        # 标准 MDM 路径
        idx = sign_changes[-1]
        y1, y2 = diffs[idx], diffs[idx + 1]
        x1, x2 = gammas[idx], gammas[idx + 1]
        if y2 != y1:
            found_gamma = x1 - y1 * (x2 - x1) / (y2 - y1)
        else:
            found_gamma = x1
        found_beta, _ = find_best_beta_for_gamma(found_gamma)
    else:
        # Fallback: 最小 sigma 的 gamma
        min_idx = np.argmin(sigma_mins)
        found_gamma = float(gammas[min_idx])
        found_beta = float(best_betas[min_idx])

    denom = np.power(neg_ln_1_minus_F, 1.0 / found_beta)
    etas = (t - found_gamma) / denom
    found_eta = float(np.mean(etas))

    return found_beta, found_eta, found_gamma


def evaluate_strategy(name, method_fn, **kwargs):
    """评估某个策略在验证参数空间上的表现。"""
    results = []
    t_start = time.time()

    for beta in BETAS:
        for gamma_eta in GAMMA_ETAS:
            gamma = gamma_eta * ETA
            for n in NS:
                for rid in range(N_REPEATS):
                    sample = generate_sample(beta, ETA, gamma, n, rid)
                    t0 = time.perf_counter()
                    try:
                        beta_hat, eta_hat, gamma_hat = method_fn(sample, **kwargs)
                        elapsed = time.perf_counter() - t0
                        if not (np.isfinite(beta_hat) and np.isfinite(eta_hat) and np.isfinite(gamma_hat)):
                            beta_hat, eta_hat, gamma_hat = None, None, None
                    except Exception:
                        beta_hat, eta_hat, gamma_hat = None, None, None
                        elapsed = time.perf_counter() - t0

                    results.append({
                        "beta_hat": beta_hat,
                        "eta_hat": eta_hat,
                        "gamma_hat": gamma_hat,
                        "beta": beta,
                        "eta": ETA,
                        "gamma": gamma,
                        "time": elapsed,
                        "converged": beta_hat is not None,
                        "sample_min": float(min(sample)),
                    })

    wall_time = time.time() - t_start
    agg = aggregate_param_metrics(results)

    return {
        "name": name,
        "mdape_beta": agg.get("mdape_beta", float("nan")),
        "mdape_eta": agg.get("mdape_eta", float("nan")),
        "mdape_gamma": agg.get("mdape_gamma", float("nan")),
        "mdape_x_r0p95": agg.get("mdape_x_r0p95", float("nan")),
        "p95_abs_beta": agg.get("p95_abs_beta", float("nan")),
        "failure_rate": agg.get("failure_rate", 0),
        "wall_time": wall_time,
        "n_total": agg.get("n_total", 0),
        "n_valid": agg.get("n_valid", 0),
        "n_failure": agg.get("n_failure", 0),
    }


def mle_method(sample):
    """MLE 作为参考。"""
    from methods.mle import MLE
    wb = MLE(sample)
    result = wb.run()
    return result[0], result[1], result[2]


if __name__ == "__main__":
    print("Evaluating strategies...")
    print()

    strategies = [
        ("MLE (reference)", mle_method),
        ("MDM standard", lambda s: mdm_with_fallback(s, offset=OFFSET, gamma_steps=GAMMA_STEPS)),
        ("MDM + fallback", lambda s: mdm_with_fallback(s, offset=OFFSET, gamma_steps=GAMMA_STEPS)),
    ]

    # 实际上 MDM standard 和 MDM + fallback 用的是同一个函数，
    # 因为 fallback 已内置。需要分开统计：标准版遇到 no_intersection 应返回 None。

    # 重新定义标准版
    def mdm_standard(sample):
        from methods.mdm import MDM
        wb = MDM(sample)
        result = wb.run(offset=OFFSET, gamma_steps=GAMMA_STEPS)
        if isinstance(result, tuple) and len(result) >= 5:
            if result[0] is None:
                return None, None, None
            return result[0], result[1], result[2]
        return None, None, None

    strategies = [
        ("MLE (reference)", mle_method),
        ("MDM standard (offset=0.1, gs=20)", mdm_standard),
        ("MDM + fallback_min_sigma", lambda s: mdm_with_fallback(s)),
    ]

    all_results = []
    for name, fn in strategies:
        print(f"Running {name}...")
        r = evaluate_strategy(name, fn)
        all_results.append(r)

    # 输出对比表
    print()
    print(f"{'Strategy':<35} {'MdAPEβ':>8} {'MdAPEη':>8} {'MdAPEγ':>8} "
          f"{'x95Md':>8} {'fail%':>6} {'wall':>6}")
    print("-" * 90)
    for r in all_results:
        print(f"{r['name']:<35} {r['mdape_beta']:>8.4f} {r['mdape_eta']:>8.4f} "
              f"{r['mdape_gamma']:>8.4f} {r['mdape_x_r0p95']:>8.4f} "
              f"{r['failure_rate']*100:>5.1f}% "
              f"{r['wall_time']:>5.1f}s")

    # 保存
    out_path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "output", "s4_5_mdm_fallback_eval.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved to {out_path}")
