"""
S4.7 MDM 约束边界处理研究（修正版）

修正内容（相对初版）：
1. 扩展参数空间：gamma/eta ∈ {0, 0.1, 0.5, 1.0}，新增 n=7
2. 保存逐样本诊断：sigma_monotone, min_location, grad_min/max, offset_crossing
3. min_sigma 使用独立完整搜索（不复用 _compute_mdm_search 的两段逻辑）

比较四种 MDM 变体 + MLE：
1. mdm_offset_strict: 严格交点法
2. mdm_offset_constrained: 约束交点法
3. mdm_min_sigma: 最小 sigma（独立完整搜索）
4. mdm_allow_negative_gamma: 允许负 gamma（仅诊断）
5. MLE: 作为参考
"""

import sys
import os
import json
import time

import numpy as np
from collections import defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from studies.common.metrics import aggregate_param_metrics, ne, check_status
from methods.mdm_variants import (
    _compute_mdm_search,
    _compute_sigma_curve,
)

# 扩展参数空间
BETAS = [1.5, 2.0, 3.0]
ETA = 100.0
GAMMA_ETAS = [0.0, 0.10, 0.50, 1.00]  # 扩展：加入 0.5 和 1.0
NS = [7, 10, 30]  # 扩展：加入 n=7
N_REPEATS = 100
OFFSET = 0.1
GAMMA_STEPS = 20

VARIANTS = [
    ("mle", "MLE (reference)", {}),
    ("mdm_offset_strict", "MDM strict", {"offset": OFFSET, "gamma_steps": GAMMA_STEPS}),
    ("mdm_offset_constrained", "MDM constrained", {"offset": OFFSET, "gamma_steps": GAMMA_STEPS}),
    ("mdm_min_sigma", "MDM min_sigma", {"offset": OFFSET, "gamma_steps": GAMMA_STEPS}),
    ("mdm_allow_negative_gamma", "MDM neg_gamma", {"offset": OFFSET, "gamma_steps": GAMMA_STEPS}),
]


def diagnose_sample(sample):
    """对单个样本做 MDM 搜索诊断。

    Returns:
        dict with keys:
        - sigma_monotone: bool, sigma 曲线是否单调非降
        - min_location: str, "boundary" (gamma≈0) 或 "interior"
        - grad_min: float, 梯度最小值
        - grad_max: float, 梯度最大值
        - offset_crossing: bool, gradient-offset 是否有符号变化
        - min_sigma_gamma: float, 最小 sigma 对应的 gamma
    """
    result = _compute_mdm_search(sample, OFFSET, GAMMA_STEPS)
    (gammas, sigma_mins, best_betas, grads, diffs, sign_changes,
     t_min, neg_ln_1_minus_F, find_best_beta_for_gamma) = result

    # 检查 sigma 曲线单调性（离散意义上是否非降）
    sigma_diffs = np.diff(sigma_mins)
    is_monotone = bool(np.all(sigma_diffs >= -1e-12))  # 允许数值噪声

    # 最小 sigma 的位置
    min_idx = int(np.argmin(sigma_mins))
    # boundary 判据：最小值在第一个采样点（gamma≈0）
    is_boundary = (min_idx == 0)
    # 也检查 gamma 值是否接近 0
    min_gamma = float(gammas[min_idx])
    if min_gamma < gammas[1] * 0.5:  # 小于第二个采样点的一半
        is_boundary = True

    return {
        "sigma_monotone": is_monotone,
        "min_location": "boundary" if is_boundary else "interior",
        "grad_min": float(np.min(grads)),
        "grad_max": float(np.max(grads)),
        "offset_crossing": len(sign_changes) > 0,
        "min_sigma_gamma": min_gamma,
        "t_min": float(t_min),
    }


def run_variant_with_diagnostics(method_variant, kwargs):
    """在扩展参数空间上运行单个变体，保存逐样本诊断。"""
    results = []
    diagnostics = []
    wall_start = time.time()

    for beta in BETAS:
        for gamma_eta in GAMMA_ETAS:
            gamma = gamma_eta * ETA
            for n in NS:
                for rid in range(N_REPEATS):
                    sample = generate_sample(beta, ETA, gamma, n, rid)
                    r = run_method(method_variant, sample, **kwargs)

                    ne_val = None
                    status = "failure"
                    if r["converged"] and r["beta_hat"] is not None:
                        ne_val = ne(r["beta_hat"], r["eta_hat"], r["gamma_hat"],
                                    beta, ETA, gamma)
                        status = check_status(
                            r["beta_hat"], r["eta_hat"], r["gamma_hat"],
                            beta, ETA, gamma, r["converged"]
                        )

                    row = {
                        "beta": beta,
                        "eta": ETA,
                        "gamma": gamma,
                        "gamma_eta": gamma_eta,
                        "n": n,
                        "repeat_id": rid,
                        "method_variant": method_variant,
                        "beta_hat": r["beta_hat"],
                        "eta_hat": r["eta_hat"],
                        "gamma_hat": r["gamma_hat"],
                        "converged": r["converged"],
                        "time": r["time"],
                        "ne": ne_val,
                        "status": status,
                    }
                    results.append(row)

                    # 对 MDM 变体做逐样本诊断（MLE 跳过）
                    if method_variant != "mle" and "neg_gamma" not in method_variant:
                        try:
                            diag = diagnose_sample(sample)
                            diag.update({
                                "beta": beta,
                                "gamma": gamma,
                                "gamma_eta": gamma_eta,
                                "n": n,
                                "repeat_id": rid,
                                "method_variant": method_variant,
                                "status": status,
                            })
                            diagnostics.append(diag)
                        except Exception as e:
                            pass  # 诊断失败不影响主流程

    wall_time = time.time() - wall_start
    agg = aggregate_param_metrics(results)
    q95 = agg.get("quantile", {}).get(0.950, {})

    return {
        "variant": method_variant,
        "ne_mean": agg.get("ne_mean"),
        "ne_std": agg.get("ne_std"),
        "nqe_r95": q95.get("nqe_mean"),
        "failure_rate": agg.get("failure_rate"),
        "outlier_rate": agg.get("outlier_rate"),
        "time_mean_ms": agg.get("time_mean", 0) * 1000,
        "time_p95_ms": agg.get("time_p95", 0) * 1000,
        "wall_time_s": wall_time,
        "n_total": agg.get("n_total"),
        "n_success": agg.get("n_success"),
        "n_failure": agg.get("n_failure"),
        "n_outlier": agg.get("n_outlier"),
        "diagnostics": diagnostics,
        "per_row": results,
    }


def analyze_diagnostics(diagnostics):
    """分析逐样本诊断数据，输出分类统计。"""
    if not diagnostics:
        return {}

    total = len(diagnostics)
    monotone = sum(1 for d in diagnostics if d["sigma_monotone"])
    boundary = sum(1 for d in diagnostics if d["min_location"] == "boundary")
    interior = total - boundary
    crossing = sum(1 for d in diagnostics if d["offset_crossing"])

    # failure 样本的诊断
    failure_diags = [d for d in diagnostics if d["status"] == "failure"]
    success_diags = [d for d in diagnostics if d["status"] == "success"]

    result = {
        "total_samples": total,
        "sigma_monotone_count": monotone,
        "sigma_monotone_pct": round(monotone / total * 100, 1),
        "min_at_boundary_count": boundary,
        "min_at_boundary_pct": round(boundary / total * 100, 1),
        "min_at_interior_count": interior,
        "min_at_interior_pct": round(interior / total * 100, 1),
        "offset_crossing_count": crossing,
        "offset_crossing_pct": round(crossing / total * 100, 1),
    }

    if failure_diags:
        f_monotone = sum(1 for d in failure_diags if d["sigma_monotone"])
        f_boundary = sum(1 for d in failure_diags if d["min_location"] == "boundary")
        f_grad_min = [d["grad_min"] for d in failure_diags]
        result["failure_analysis"] = {
            "count": len(failure_diags),
            "sigma_monotone_pct": round(f_monotone / len(failure_diags) * 100, 1),
            "min_at_boundary_pct": round(f_boundary / len(failure_diags) * 100, 1),
            "grad_min_mean": round(float(np.mean(f_grad_min)), 4),
            "grad_min_min": round(float(np.min(f_grad_min)), 4),
        }

    if success_diags:
        s_monotone = sum(1 for d in success_diags if d["sigma_monotone"])
        s_boundary = sum(1 for d in success_diags if d["min_location"] == "boundary")
        result["success_analysis"] = {
            "count": len(success_diags),
            "sigma_monotone_pct": round(s_monotone / len(success_diags) * 100, 1),
            "min_at_boundary_pct": round(s_boundary / len(success_diags) * 100, 1),
        }

    return result


def main():
    total_combos = len(BETAS) * len(GAMMA_ETAS) * len(NS) * N_REPEATS
    print("S4.7 MDM Constrained Boundary Study (修正版)")
    print(f"参数空间: beta={BETAS}, eta={ETA}, gamma/eta={GAMMA_ETAS}, "
          f"n={NS}, repeats={N_REPEATS}")
    print(f"每个变体: {total_combos} 样本")
    print()

    all_results = []
    results_by_variant = {}
    for method_variant, name, kwargs in VARIANTS:
        print(f"运行 {name} ({method_variant})...", end=" ", flush=True)
        r = run_variant_with_diagnostics(method_variant, kwargs)
        results_by_variant[method_variant] = r.pop("per_row")
        all_results.append(r)
        print(f"完成 ({r['wall_time_s']:.1f}s)")

    # 打印对比表
    print()
    print(f"{'变体':<30} {'NE':>7} {'NE_std':>7} {'NQE95':>7} "
          f"{'fail%':>6} {'out%':>6} {'t_ms':>7} {'succ':>5} {'fail':>5}")
    print("-" * 95)
    for r in all_results:
        ne_val = r['ne_mean'] or 0
        ne_s = r['ne_std'] or 0
        nqe = r['nqe_r95'] or 0
        fr = (r['failure_rate'] or 0) * 100
        outr = (r['outlier_rate'] or 0) * 100
        t = r['time_mean_ms']
        print(f"{r['variant']:<30} {ne_val:>7.4f} {ne_s:>7.4f} {nqe:>7.4f} "
              f"{fr:>5.1f}% {outr:>5.1f}% {t:>6.1f}ms "
              f"{r['n_success']:>5} {r['n_failure']:>5}")

    # 分析诊断数据
    print()
    print("=" * 70)
    print("逐样本诊断分析")
    print("=" * 70)
    for r in all_results:
        if r["diagnostics"]:
            print(f"\n--- {r['variant']} ---")
            analysis = analyze_diagnostics(r["diagnostics"])
            r["diagnostic_analysis"] = analysis
            print(f"  总样本: {analysis['total_samples']}")
            print(f"  sigma 单调: {analysis['sigma_monotone_count']} "
                  f"({analysis['sigma_monotone_pct']}%)")
            print(f"  最小值在边界(gamma≈0): {analysis['min_at_boundary_count']} "
                  f"({analysis['min_at_boundary_pct']}%)")
            print(f"  最小值在内部: {analysis['min_at_interior_count']} "
                  f"({analysis['min_at_interior_pct']}%)")
            print(f"  有 offset 交点: {analysis['offset_crossing_count']} "
                  f"({analysis['offset_crossing_pct']}%)")
            if "failure_analysis" in analysis:
                fa = analysis["failure_analysis"]
                print(f"  [failure 样本] sigma 单调: {fa['sigma_monotone_pct']}%")
                print(f"  [failure 样本] 最小值在边界: {fa['min_at_boundary_pct']}%")
                print(f"  [failure 样本] grad_min 均值: {fa['grad_min_mean']}")
            if "success_analysis" in analysis:
                sa = analysis["success_analysis"]
                print(f"  [success 样本] sigma 单调: {sa['sigma_monotone_pct']}%")
                print(f"  [success 样本] 最小值在边界: {sa['min_at_boundary_pct']}%")

    # 按 gamma/eta 分组统计
    print()
    print("=" * 70)
    print("按 gamma/eta 分组统计")
    print("=" * 70)
    for r in all_results:
        print(f"\n--- {r['variant']} ---")
        diag_by_ge = {}
        for d in r.get("diagnostics", []):
            ge = d["gamma_eta"]
            if ge not in diag_by_ge:
                diag_by_ge[ge] = {"total": 0, "failure": 0, "monotone": 0,
                                   "boundary": 0}
            diag_by_ge[ge]["total"] += 1
            if d["status"] == "failure":
                diag_by_ge[ge]["failure"] += 1
            if d["sigma_monotone"]:
                diag_by_ge[ge]["monotone"] += 1
            if d["min_location"] == "boundary":
                diag_by_ge[ge]["boundary"] += 1

        for ge in sorted(diag_by_ge.keys()):
            s = diag_by_ge[ge]
            f_pct = s["failure"] / s["total"] * 100 if s["total"] > 0 else 0
            m_pct = s["monotone"] / s["total"] * 100 if s["total"] > 0 else 0
            b_pct = s["boundary"] / s["total"] * 100 if s["total"] > 0 else 0
            print(f"  gamma/eta={ge:.1f}: total={s['total']}, "
                  f"fail={s['failure']}({f_pct:.1f}%), "
                  f"monotone={s['monotone']}({m_pct:.1f}%), "
                  f"boundary={s['boundary']}({b_pct:.1f}%)")

    # 保存结果
    out_path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "output", "s4_7_mdm_constrained_study_v2.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # 保存：聚合结果 + 逐样本诊断
    output = {
        "config": {
            "betas": BETAS,
            "eta": ETA,
            "gamma_etas": GAMMA_ETAS,
            "ns": NS,
            "n_repeats": N_REPEATS,
            "offset": OFFSET,
            "gamma_steps": GAMMA_STEPS,
            "total_per_variant": total_combos,
        },
        "aggregate": [],
        "diagnostics": {},
    }

    # 按 gamma/eta 分组统计 NE/outlier/failure
    output["grouped_by_gamma_eta"] = {}
    for r in all_results:
        variant = r["variant"]
        by_ge = defaultdict(lambda: {"nes": [], "statuses": []})
        for row in results_by_variant.get(variant, []):
            ge = row["gamma_eta"]
            by_ge[ge]["nes"].append(row["ne"])
            by_ge[ge]["statuses"].append(row["status"])

        grouped = {}
        for ge in sorted(by_ge.keys()):
            d = by_ge[ge]
            total = len(d["statuses"])
            n_failure = sum(1 for s in d["statuses"] if s == "failure")
            n_outlier = sum(1 for s in d["statuses"] if s == "outlier")
            n_success = sum(1 for s in d["statuses"] if s == "success")
            success_nes = [v for v, s in zip(d["nes"], d["statuses"])
                           if s == "success" and v is not None]
            grouped[str(ge)] = {
                "total": total,
                "failure": n_failure,
                "failure_pct": round(n_failure / total * 100, 1),
                "outlier": n_outlier,
                "outlier_pct": round(n_outlier / total * 100, 1),
                "success": n_success,
                "ne_mean": round(float(np.mean(success_nes)), 4) if success_nes else None,
            }
        output["grouped_by_gamma_eta"][variant] = grouped

    for r in all_results:
        agg_row = {k: v for k, v in r.items()
                   if k not in ("diagnostics", "diagnostic_analysis")}
        output["aggregate"].append(agg_row)
        if "diagnostic_analysis" in r:
            output["diagnostics"][r["variant"]] = {
                "summary": r["diagnostic_analysis"],
                "per_sample": r["diagnostics"],
            }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False, default=str)
    print(f"\n结果保存到 {out_path}")

    return output


if __name__ == "__main__":
    main()
