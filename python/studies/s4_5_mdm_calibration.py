"""
S4.5 MDM 调用配置校准实验

比较 offset × gamma_steps 小网格，输出精度/耗时/失败率对比表。
"""

import sys
import os
import json
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from studies.common.metrics import ne, check_status, aggregate_param_metrics

# 验证参数空间
BETAS = [1.5, 2.0, 3.0]
ETA = 100.0
GAMMA_ETAS = [0.0, 0.10]
NS = [10, 30]
N_REPEATS = 100

# MDM 配置网格
OFFSETS = [0.05, 0.1, 0.2]
GAMMA_STEPS = [20, 40, 60]


def run_calibration():
    results_by_config = {}

    for offset in OFFSETS:
        for gs in GAMMA_STEPS:
            variant = f"mdm_o{offset}_gs{gs}"
            print(f"Running {variant}...")
            t_start = time.time()

            all_results = []
            failure_reasons = Counter()

            for beta in BETAS:
                for gamma_eta in GAMMA_ETAS:
                    gamma = gamma_eta * ETA
                    for n in NS:
                        for rid in range(N_REPEATS):
                            sample = generate_sample(beta, ETA, gamma, n, rid)
                            r = run_method("mdm", sample, variant=variant,
                                           offset=offset, gamma_steps=gs)

                            beta_hat = r["beta_hat"]
                            eta_hat = r["eta_hat"]
                            gamma_hat = r["gamma_hat"]
                            converged = r["converged"]

                            if beta_hat is None or eta_hat is None or gamma_hat is None:
                                status = "failure"
                                # 记录失败原因
                                if r["extra"] and "raw_status" in r["extra"]:
                                    failure_reasons[r["extra"]["raw_status"]] += 1
                                elif r["extra"] and "error" in r["extra"]:
                                    failure_reasons[f"error: {r['extra']['error'][:50]}"] += 1
                                else:
                                    failure_reasons["unknown"] += 1
                            else:
                                status = check_status(
                                    beta_hat, eta_hat, gamma_hat,
                                    beta, ETA, gamma,
                                    converged=converged,
                                )

                            all_results.append({
                                "beta_hat": beta_hat,
                                "eta_hat": eta_hat,
                                "gamma_hat": gamma_hat,
                                "beta": beta,
                                "eta": ETA,
                                "gamma": gamma,
                                "time": r["time"],
                                "converged": converged,
                            })

            elapsed = time.time() - t_start
            agg = aggregate_param_metrics(all_results)
            results_by_config[variant] = {
                "offset": offset,
                "gamma_steps": gs,
                "ne_mean": agg.get("ne_mean", float("nan")),
                "nqe_r_mean": _avg_nqe(agg),
                "failure_rate": agg.get("failure_rate", 0),
                "outlier_rate": agg.get("outlier_rate", 0),
                "time_mean": agg.get("time_mean", 0),
                "time_p95": agg.get("time_p95", 0),
                "n_total": agg.get("n_total", 0),
                "n_success": agg.get("n_success", 0),
                "n_failure": agg.get("n_failure", 0),
                "n_outlier": agg.get("n_outlier", 0),
                "failure_reasons": dict(failure_reasons),
                "wall_time": elapsed,
            }

    return results_by_config


def _avg_nqe(agg):
    """从聚合结果中提取 NQE_R 均值（取 R=0.950 作为代表）"""
    q = agg.get("quantile", {})
    r95 = q.get(0.950, {})
    return r95.get("nqe_mean", float("nan"))


def print_table(results_by_config):
    """输出对比表"""
    print()
    print(f"{'variant':<20} {'offset':>6} {'gs':>4} {'NE_mean':>8} {'NQE_R':>8} "
          f"{'fail%':>6} {'out%':>6} {'t_mean':>8} {'t_p95':>8} {'wall_s':>7}")
    print("-" * 95)

    for variant, d in sorted(results_by_config.items()):
        print(f"{variant:<20} {d['offset']:>6.2f} {d['gamma_steps']:>4d} "
              f"{d['ne_mean']:>8.4f} {d['nqe_r_mean']:>8.4f} "
              f"{d['failure_rate']*100:>5.1f}% {d['outlier_rate']*100:>5.1f}% "
              f"{d['time_mean']*1000:>7.1f}ms {d['time_p95']*1000:>7.1f}ms "
              f"{d['wall_time']:>6.1f}s")

    print()
    print("Failure reasons by config:")
    for variant, d in sorted(results_by_config.items()):
        if d["failure_reasons"]:
            print(f"  {variant}: {d['failure_reasons']}")


if __name__ == "__main__":
    results = run_calibration()
    print_table(results)

    # 保存详细结果
    out_path = os.path.join(os.path.dirname(__file__), "..", "..",
                            "output", "s4_5_mdm_calibration.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False, default=str)
    print(f"\nDetailed results saved to {out_path}")
