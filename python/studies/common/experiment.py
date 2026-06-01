"""
统一蒙特卡洛调度模块

遍历参数网格 × 样本量，生成共享样本，调用所有方法，
用 S2R 指标模块计算状态和指标，保存逐条 CSV + 聚合 JSON。

规范来源：AI辅助三参数威布尔参数估计S4统一蒙特卡洛框架规划 第 3.4 节
"""

import csv
import json
import math
import os
from typing import List, Dict, Tuple, Any, Union

from studies.common.sample import generate_sample
from studies.common.runner import run_method
from studies.common.metrics import (
    check_status, aggregate_param_metrics, DEFAULT_R_LEVELS, param_relative_errors,
)


def _parse_method_spec(spec: Union[str, Tuple]) -> Tuple[str, dict, str]:
    """解析方法规格，返回 (method_id, kwargs, variant)。

    支持：
        "mle"                              → ("mle", {}, "mle")
        ("mdm", {"offset": 0.5})           → ("mdm", {"offset": 0.5}, "mdm")
        ("mdm", {"offset": 0.5, "variant": "mdm_o0.5"}) → ("mdm", {"offset": 0.5}, "mdm_o0.5")
    """
    if isinstance(spec, str):
        return spec, {}, spec

    method_id = spec[0]
    kwargs = dict(spec[1]) if len(spec) > 1 and spec[1] else {}
    variant = kwargs.pop("variant", method_id)
    return method_id, kwargs, variant


def run_experiment(
    methods: List[Union[str, Tuple]],
    param_grid: List[Tuple[float, float, float]],
    n_values: List[int],
    n_repeats: int,
    output_dir: str,
    R_levels: Tuple[float, ...] = DEFAULT_R_LEVELS,
) -> Dict[str, Any]:
    """运行完整蒙特卡洛实验。

    Args:
        methods: 方法列表，元素为 str 或 (str, dict) 元组
        param_grid: [(beta, eta, gamma), ...] 参数组合
        n_values: [10, 20, 30, ...] 样本量列表
        n_repeats: 每组重复次数
        output_dir: 结果保存目录
        R_levels: 可靠度水平

    Returns:
        汇总字典，按 method_variant × (beta, eta, gamma) × n 分组
    """
    os.makedirs(output_dir, exist_ok=True)
    csv_path = os.path.join(output_dir, "results.csv")
    json_path = os.path.join(output_dir, "summary.json")

    parsed_methods = [_parse_method_spec(s) for s in methods]

    csv_rows = []
    agg_inputs: Dict[str, List[Dict]] = {}

    for beta, eta, gamma in param_grid:
        for n in n_values:
            for rid in range(n_repeats):
                sample = generate_sample(beta, eta, gamma, n, rid)

                for method_id, kwargs, variant in parsed_methods:
                    m_result = run_method(method_id, sample, variant=variant, **kwargs)

                    beta_hat = m_result["beta_hat"]
                    eta_hat = m_result["eta_hat"]
                    gamma_hat = m_result["gamma_hat"]
                    converged = m_result["converged"]

                    sample_min = float(min(sample))

                    # 计算状态和逐行误差
                    if beta_hat is None or eta_hat is None or gamma_hat is None:
                        status = "failure"
                        rel_errors = {"beta": float("nan"), "eta": float("nan"), "gamma": float("nan")}
                    else:
                        status = check_status(
                            beta_hat, eta_hat, gamma_hat,
                            beta, eta, gamma,
                            converged=converged,
                            sample_min=sample_min,
                        )
                        rel_errors = param_relative_errors(
                            beta_hat, eta_hat, gamma_hat,
                            beta, eta, gamma,
                        ) if status == "success" else {"beta": float("nan"), "eta": float("nan"), "gamma": float("nan")}

                    row = {
                        "beta": beta,
                        "eta": eta,
                        "gamma": gamma,
                        "n": n,
                        "repeat_id": rid,
                        "method_id": method_id,
                        "method_variant": variant,
                        "beta_hat": beta_hat,
                        "eta_hat": eta_hat,
                        "gamma_hat": gamma_hat,
                        "r_squared": m_result["r_squared"],
                        "converged": converged,
                        "time": m_result["time"],
                        "status": status,
                        "beta_rel_error": rel_errors["beta"],
                        "eta_rel_error": rel_errors["eta"],
                        "gamma_rel_error": rel_errors["gamma"],
                        "extra": json.dumps(m_result["extra"]) if m_result["extra"] is not None else None,
                    }
                    csv_rows.append(row)

                    # 收集聚合输入
                    agg_key = (variant, beta, eta, gamma, n)
                    if agg_key not in agg_inputs:
                        agg_inputs[agg_key] = []
                    agg_inputs[agg_key].append({
                        "beta_hat": beta_hat,
                        "eta_hat": eta_hat,
                        "gamma_hat": gamma_hat,
                        "beta": beta,
                        "eta": eta,
                        "gamma": gamma,
                        "time": m_result["time"],
                        "converged": converged,
                        "sample_min": sample_min,
                    })

    # 写 CSV
    _write_csv(csv_path, csv_rows)

    # 聚合并写 JSON
    summary = {}
    for (variant, beta, eta, gamma, n), results in agg_inputs.items():
        agg = aggregate_param_metrics(results, R_levels=R_levels)
        group_key = f"{variant}|b{beta}_e{eta}_g{gamma}_n{n}"
        summary[group_key] = {
            "method_variant": variant,
            "beta": beta,
            "eta": eta,
            "gamma": gamma,
            "n": n,
            **agg,
        }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    return summary


def _write_csv(path: str, rows: List[Dict]):
    """写逐条结果到 CSV。"""
    if not rows:
        return

    fieldnames = [
        "beta", "eta", "gamma", "n", "repeat_id",
        "method_id", "method_variant",
        "beta_hat", "eta_hat", "gamma_hat",
        "r_squared", "converged", "time",
        "status", "beta_rel_error", "eta_rel_error", "gamma_rel_error", "extra",
    ]

    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
