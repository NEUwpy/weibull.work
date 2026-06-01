"""
S4.5 MDM 调用配置校准实验

比较 offset × gamma_steps 小网格，输出 S2R 指标/失败率对比表。
"""

import sys
import os
import json
import time
from collections import Counter

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from studies.common.metrics import check_status, aggregate_param_metrics

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
                                    sample_min=float(min(sample)),
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
                                "sample_min": float(min(sample)),
                            })

            elapsed = time.time() - t_start
            agg = aggregate_param_metrics(all_results)
            results_by_config[variant] = {
                "offset": offset,
                "gamma_steps": gs,
                "mdape_beta": agg.get("mdape_beta", float("nan")),
                "mdape_eta": agg.get("mdape_eta", float("nan")),
                "mdape_gamma": agg.get("mdape_gamma", float("nan")),
                "mdape_x_r0p95": agg.get("mdape_x_r0p95", float("nan")),
                "p95_abs_beta": agg.get("p95_abs_beta", float("nan")),
                "failure_rate": agg.get("failure_rate", 0),
                "n_total": agg.get("n_total", 0),
                "n_valid": agg.get("n_valid", 0),
                "n_failure": agg.get("n_failure", 0),
                "failure_reasons": dict(failure_reasons),
                "wall_time": elapsed,
            }

    return results_by_config


def print_table(results_by_config):
    """输出对比表"""
    print()
    print(f"{'variant':<20} {'offset':>6} {'gs':>4} {'MdAPEβ':>8} {'MdAPEη':>8} "
          f"{'MdAPEγ':>8} {'x95Md':>8} {'fail%':>6} {'wall_s':>7}")
    print("-" * 95)

    for variant, d in sorted(results_by_config.items()):
        print(f"{variant:<20} {d['offset']:>6.2f} {d['gamma_steps']:>4d} "
              f"{d['mdape_beta']:>8.4f} {d['mdape_eta']:>8.4f} "
              f"{d['mdape_gamma']:>8.4f} {d['mdape_x_r0p95']:>8.4f} "
              f"{d['failure_rate']*100:>5.1f}% "
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
