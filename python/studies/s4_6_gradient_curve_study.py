"""
S4.6 梯度-位置参数曲线性质探究

核心问题：MDM failure 是真的无解，还是解在 t_min 附近被搜索网格跳过？

研究内容：
1. 对 failure 样本用极高分辨率（1000+ 点）重算梯度曲线
2. 检查梯度曲线在 t_min 附近是否有陡降或非单调行为
3. 测试不同 gamma_steps 能否恢复交点
4. 分析梯度曲线的数学性质
"""

import sys
import os
import json
import numpy as np
from scipy.optimize import minimize_scalar
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample
from base import WeibullBase


def compute_gradient_curve(sample, n_points=1000, gamma_max_ratio=0.999999):
    """对单个样本计算完整梯度曲线。

    返回: gammas, sigma_mins, best_betas, grads
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

    gammas = np.linspace(0, t_min * gamma_max_ratio, n_points)
    sigma_mins = np.zeros(n_points)
    best_betas = np.zeros(n_points)

    for i, g in enumerate(gammas):
        b, sig = find_best_beta_for_gamma(g)
        sigma_mins[i] = sig
        best_betas[i] = b

    grads = np.gradient(sigma_mins, gammas)

    return gammas, sigma_mins, best_betas, grads


def find_intersections(grads, gammas, offset):
    """找到梯度曲线与 offset 的所有交点。"""
    diffs = grads - offset
    sign_changes = np.where(np.diff(np.sign(diffs)))[0]

    intersections = []
    for idx in sign_changes:
        y1, y2 = diffs[idx], diffs[idx + 1]
        x1, x2 = gammas[idx], gammas[idx + 1]
        if y2 != y1:
            gamma_star = x1 - y1 * (x2 - x1) / (y2 - y1)
        else:
            gamma_star = x1
        intersections.append(float(gamma_star))

    return intersections


def analyze_single_sample(sample, offset=0.1, n_points=2000):
    """对单个样本做完整梯度曲线分析。"""
    wb = WeibullBase(sample)
    t = wb.data
    t_min = t[0]

    gammas, sigma_mins, best_betas, grads = compute_gradient_curve(
        sample, n_points=n_points
    )

    intersections = find_intersections(grads, gammas, offset)

    # 梯度曲线特征
    grad_min = float(np.min(grads))
    grad_max = float(np.max(grads))
    grad_min_idx = int(np.argmin(grads))
    grad_min_gamma = float(gammas[grad_min_idx])

    # 检查梯度曲线的单调性
    grad_diffs = np.diff(grads)
    n_decreasing = np.sum(grad_diffs < 0)
    n_increasing = np.sum(grad_diffs > 0)

    # 检查 t_min 附近的梯度行为（最后 10% 的 gamma 范围）
    near_tmin_mask = gammas > t_min * 0.9
    near_grads = grads[near_tmin_mask]
    near_gammas = gammas[near_tmin_mask]
    near_grad_min = float(np.min(near_grads))
    near_grad_max = float(np.max(near_grads))

    # 检查梯度曲线是否有"尖锐下降"
    # 计算梯度的变化率（二阶导数）
    grad2 = np.gradient(grads, gammas)
    max_grad2_idx = int(np.argmax(np.abs(grad2)))
    max_grad2_gamma = float(gammas[max_grad2_idx])
    max_grad2_val = float(grad2[max_grad2_idx])

    result = {
        "t_min": float(t_min),
        "n_points": n_points,
        "offset": offset,
        "grad_min": grad_min,
        "grad_max": grad_max,
        "grad_min_gamma": grad_min_gamma,
        "grad_min_gamma_ratio": grad_min_gamma / t_min,
        "n_intersections": len(intersections),
        "intersections": intersections,
        "offset_in_range": grad_min <= offset <= grad_max,
        "monotonicity": {
            "n_decreasing": int(n_decreasing),
            "n_increasing": int(n_increasing),
            "ratio_decreasing": float(n_decreasing / len(grad_diffs)),
        },
        "near_tmin_behavior": {
            "gamma_range": [float(near_gammas[0]), float(near_gammas[-1])],
            "grad_min": near_grad_min,
            "grad_max": near_grad_max,
        },
        "max_curvature": {
            "gamma": max_grad2_gamma,
            "value": max_grad2_val,
            "gamma_ratio": max_grad2_gamma / t_min,
        },
    }

    # 如果有交点，记录交点附近的梯度值
    if intersections:
        for gamma_star in intersections:
            idx = np.searchsorted(gammas, gamma_star)
            if idx > 0 and idx < len(gammas):
                result["intersection_detail"] = {
                    "gamma": gamma_star,
                    "gamma_ratio": gamma_star / t_min,
                    "grad_at_intersection": float(
                        grads[idx - 1] + (grads[idx] - grads[idx - 1]) *
                        (gamma_star - gammas[idx - 1]) / (gammas[idx] - gammas[idx - 1])
                    ),
                }

    return result


def run_sensitivity_test(sample, offset=0.1):
    """测试不同 gamma_steps 能否找到交点。"""
    steps_list = [20, 40, 80, 160, 320, 640, 1280]
    results = []

    wb = WeibullBase(sample)
    t = wb.data
    t_min = t[0]
    n = wb.n
    ranks = wb._median_ranks()
    neg_ln_1_minus_F = -np.log(1 - ranks)

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

    for steps in steps_list:
        gammas1 = np.linspace(0, t_min * 0.99, steps)
        sigma_mins1 = []
        for g in gammas1:
            _, sig = find_best_beta_for_gamma(g)
            sigma_mins1.append(sig)
        sigma_mins1 = np.array(sigma_mins1)
        grads1 = np.gradient(sigma_mins1, gammas1)
        diffs1 = grads1 - offset
        sc1 = np.where(np.diff(np.sign(diffs1)))[0]

        if len(sc1) == 0:
            gammas2 = np.linspace(t_min * 0.99, t_min * 0.999999, steps)
            sigma_mins2 = []
            for g in gammas2:
                _, sig = find_best_beta_for_gamma(g)
                sigma_mins2.append(sig)
            sigma_mins2 = np.array(sigma_mins2)
            grads2 = np.gradient(sigma_mins2, gammas2)
            gammas_all = np.concatenate([gammas1, gammas2])
            grads_all = np.concatenate([grads1, grads2])
            diffs_all = grads_all - offset
            sc_all = np.where(np.diff(np.sign(diffs_all)))[0]
            has_intersection = len(sc_all) > 0
        else:
            has_intersection = True

        results.append({
            "steps": steps,
            "has_intersection": has_intersection,
        })

    return results


def run_study():
    """主研究流程。"""
    BETAS = [1.5, 2.0, 3.0]
    ETA = 100.0
    GAMMA_ETAS = [0.0, 0.10]
    NS = [10, 30]
    N_REPEATS = 50  # 减少重复数以加速
    OFFSET = 0.1

    # 收集 failure 样本
    print("=== 第一步：识别 failure 样本 ===")
    failure_cases = []
    total = 0

    for beta in BETAS:
        for gamma_eta in GAMMA_ETAS:
            gamma = gamma_eta * ETA
            for n in NS:
                for rid in range(N_REPEATS):
                    total += 1
                    sample = generate_sample(beta, ETA, gamma, n, rid)
                    wb = WeibullBase(sample)
                    t = wb.data
                    t_min = t[0]

                    # 用标准 MDM 检查
                    from methods.mdm import MDM
                    mdm = MDM(sample)
                    result = mdm.run(offset=OFFSET, gamma_steps=20)
                    if result[0] is None:
                        failure_cases.append({
                            "beta": beta, "eta": ETA, "gamma": gamma,
                            "n": n, "rid": rid, "t_min": float(t_min),
                        })

    print(f"Total: {total}, Failure: {len(failure_cases)} ({len(failure_cases)/total*100:.1f}%)")
    print()

    if not failure_cases:
        print("No failure cases found. Exiting.")
        return

    # 第二步：对 failure 样本做高分辨率梯度曲线分析
    print("=== 第二步：高分辨率梯度曲线分析 ===")
    detailed_results = []

    for i, case in enumerate(failure_cases[:20]):  # 先分析前 20 个
        sample = generate_sample(case["beta"], case["eta"], case["gamma"],
                                  case["n"], case["rid"])
        result = analyze_single_sample(sample, offset=OFFSET, n_points=2000)
        result.update(case)
        detailed_results.append(result)

        if i < 5:
            print(f"\nSample {i+1}: beta={case['beta']}, gamma={case['gamma']}, n={case['n']}, rid={case['rid']}")
            print(f"  t_min={result['t_min']:.4f}")
            print(f"  grad_min={result['grad_min']:.6f} at gamma={result['grad_min_gamma']:.4f} (ratio={result['grad_min_gamma_ratio']:.4f})")
            print(f"  grad_max={result['grad_max']:.6f}")
            print(f"  offset={OFFSET}, in_range={result['offset_in_range']}")
            print(f"  n_intersections={result['n_intersections']}")
            print(f"  monotonicity: {result['monotonicity']['n_decreasing']} decreasing, {result['monotonicity']['n_increasing']} increasing")
            print(f"  near t_min: grad_min={result['near_tmin_behavior']['grad_min']:.6f}, grad_max={result['near_tmin_behavior']['grad_max']:.6f}")
            print(f"  max curvature at gamma={result['max_curvature']['gamma']:.4f} (ratio={result['max_curvature']['gamma_ratio']:.4f})")

    # 第三步：灵敏度测试
    print("\n=== 第三步：gamma_steps 灵敏度测试 ===")
    sensitivity_results = []
    recovered_count = 0

    for i, case in enumerate(failure_cases[:10]):  # 测试前 10 个
        sample = generate_sample(case["beta"], case["eta"], case["gamma"],
                                  case["n"], case["rid"])
        sens = run_sensitivity_test(sample, offset=OFFSET)
        sensitivity_results.append(sens)

        # 检查最大 steps 是否能恢复
        if sens[-1]["has_intersection"]:
            recovered_count += 1

        if i < 5:
            print(f"\nSample {i+1}: beta={case['beta']}, gamma={case['gamma']}, n={case['n']}, rid={case['rid']}")
            for s in sens:
                status = "YES" if s["has_intersection"] else "no"
                print(f"  steps={s['steps']:>5}: {status}")

    print(f"\n灵敏度测试总结：{recovered_count}/{min(10, len(failure_cases))} 个样本用 1280 steps 可恢复交点")

    # 汇总
    print("\n=== 汇总 ===")
    grad_mins = [r["grad_min"] for r in detailed_results]
    grad_min_gammas = [r["grad_min_gamma_ratio"] for r in detailed_results]
    print(f"grad_min 范围: [{min(grad_mins):.4f}, {max(grad_mins):.4f}], 均值={np.mean(grad_mins):.4f}")
    print(f"grad_min 所在 gamma/t_min 比值: [{min(grad_min_gammas):.4f}, {max(grad_min_gammas):.4f}]")

    # 保存结果
    out_path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "output", "s4_6_gradient_study.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    save_data = {
        "failure_count": len(failure_cases),
        "analyzed_count": len(detailed_results),
        "detailed_results": detailed_results,
        "sensitivity_results": [
            [{"steps": s["steps"], "has_intersection": s["has_intersection"]}
             for s in sens]
            for sens in sensitivity_results
        ],
        "summary": {
            "grad_min_range": [float(min(grad_mins)), float(max(grad_mins))],
            "grad_min_mean": float(np.mean(grad_mins)),
            "recovered_by_1280_steps": recovered_count,
            "analyzed_in_sensitivity": min(10, len(failure_cases)),
        },
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(save_data, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nResults saved to {out_path}")

    return save_data


if __name__ == "__main__":
    run_study()
