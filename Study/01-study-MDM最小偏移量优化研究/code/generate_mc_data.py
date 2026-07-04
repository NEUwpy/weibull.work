"""
Study/01 — E1/E2 共用 MC 扫描数据生成

功能：
- 遍历参数网格 × n × repeats × δ_grid
- 对每个 (样本, δ) 调用 MDM 估计，记录 β̂/η̂/γ̂
- 同时对每个样本调用一次 MLE（锚点，无 δ 循环）
- 支持断点续跑
- 支持温和并行（multiprocessing, N_WORKERS 个进程）

输出结构：
    artifacts/formal/shared_data/
        mc_scan_raw.csv      — MDM 逐条结果
        mle_anchor.csv       — MLE 锚点逐条结果
        manifest.json        — 实验溯源信息
        progress.json        — 断点续跑进度

CSV 列（mc_scan_raw.csv）：
    beta, eta, gamma, gamma_over_eta, n, repeat_id, delta,
    beta_hat, eta_hat, gamma_hat, r_squared, converged, time_ms, status

设计原则：
- 每个 (beta, eta, gamma, n) 块独立处理 → 断点续跑 + 并行分配的最小单元
- 同一个样本只生成一次，跑所有 δ → 避免重复采样
- 绕过 runner.py，直接实例化 MDM 类 → 减少 inspect 开销

用法：
    # 串行（调试/pilot 用）
    python generate_mc_data.py --serial

    # 并行（正式跑用，默认）
    python generate_mc_data.py

    # pilot 小规模验证
    python generate_mc_data.py --pilot
"""

import os
import sys
import csv
import json
import time
import argparse
import multiprocessing as mp
from functools import partial

# ── 路径设置 ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"D:\weibull\python")

from config import (
    BETA_GRID, ETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID,
    DELTA_GRID, R_MAIN, SEED_NAMESPACE, N_WORKERS,
    SHARED_DATA_DIR, STUDY_ROOT,
    estimate_total, build_param_grid,
)
from utils import get_git_info, now_iso, now_local
from studies.common.sample import generate_sample


# ============================================================
# 工作单元定义
# ============================================================

def build_work_units():
    """构建所有工作单元。

    每个工作单元 = (beta, eta, gamma, gamma_over_eta, n)
    对应 R_MAIN 个样本 × len(DELTA_GRID) 个 δ。

    Returns:
        List of dict: [{beta, eta, gamma, gamma_over_eta, n}, ...]
    """
    units = []
    for eta in ETA_GRID:
        for goe in GAMMA_OVER_ETA_GRID:
            gamma = goe * eta
            for beta in BETA_GRID:
                for n in N_GRID:
                    units.append({
                        "beta": beta,
                        "eta": eta,
                        "gamma": gamma,
                        "gamma_over_eta": goe,
                        "n": n,
                    })
    return units


# ============================================================
# 单个工作单元处理（子进程内执行）
# ============================================================

def process_unit(unit, repeats=None, delta_grid=None, seed_ns=None):
    """处理一个工作单元：生成 R 个样本，每个样本跑所有 δ。

    Args:
        unit: {beta, eta, gamma, gamma_over_eta, n}
        repeats: MC 重复次数（None → 用 config.R_MAIN）
        delta_grid: δ 列表（None → 用 config.DELTA_GRID）
        seed_ns: 种子命名空间

    Returns:
        (mdm_rows, mle_rows): 两个列表，每元素是一行 dict
    """
    if repeats is None:
        repeats = R_MAIN
    if delta_grid is None:
        delta_grid = DELTA_GRID
    if seed_ns is None:
        seed_ns = SEED_NAMESPACE

    beta = unit["beta"]
    eta = unit["eta"]
    gamma = unit["gamma"]
    goe = unit["gamma_over_eta"]
    n = unit["n"]

    # 延迟 import（子进程需要）
    from methods.mdm import MDM
    from methods.mle import MLE

    mdm_rows = []
    mle_rows = []

    for rid in range(repeats):
        # 生成样本（同一份样本给 MDM 所有 δ 和 MLE）
        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_ns)
        sample_min = float(sample[0])

        # ── MDM: 每个样本跑所有 δ ──
        for delta in delta_grid:
            row = {
                "beta": beta, "eta": eta, "gamma": gamma,
                "gamma_over_eta": goe, "n": n, "repeat_id": rid,
                "delta": delta,
                "beta_hat": None, "eta_hat": None, "gamma_hat": None,
                "r_squared": None, "converged": False,
                "time_ms": 0.0, "status": "failure",
            }
            try:
                mdm = MDM(sample)
                t0 = time.perf_counter()
                result = mdm.run(offset=delta)
                elapsed_ms = (time.perf_counter() - t0) * 1000

                bh, eh, gh, r2, conv = result
                row["beta_hat"] = bh
                row["eta_hat"] = eh
                row["gamma_hat"] = gh
                row["r_squared"] = r2
                row["converged"] = bool(conv)
                row["time_ms"] = elapsed_ms
                row["status"] = "success" if conv and bh > 0 and eh > 0 else "failure"
            except Exception as e:
                row["status"] = f"error:{type(e).__name__}"
            mdm_rows.append(row)

        # ── MLE: 每个样本跑一次（锚点，无 δ 循环）──
        mle_row = {
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n, "repeat_id": rid,
            "beta_hat": None, "eta_hat": None, "gamma_hat": None,
            "r_squared": None, "converged": False,
            "time_ms": 0.0, "status": "failure",
        }
        try:
            mle = MLE(sample)
            t0 = time.perf_counter()
            result = mle.run()
            elapsed_ms = (time.perf_counter() - t0) * 1000

            bh, eh, gh, r2, conv = result
            mle_row["beta_hat"] = bh
            mle_row["eta_hat"] = eh
            mle_row["gamma_hat"] = gh
            mle_row["r_squared"] = r2
            mle_row["converged"] = bool(conv) and conv != "unbounded"
            mle_row["time_ms"] = elapsed_ms
            mle_row["status"] = "success" if mle_row["converged"] else "failure"
        except Exception as e:
            mle_row["status"] = f"error:{type(e).__name__}"
        mle_rows.append(mle_row)

    return mdm_rows, mle_rows


# ============================================================
# 并行执行器
# ============================================================

def run_parallel(repeats, delta_grid, seed_ns, n_workers):
    """并行执行所有工作单元。

    - 将工作单元分配给 n_workers 个进程
    - 每个进程独立处理，返回结果列表
    - 主进程负责写入 CSV
    """
    units = build_work_units()
    total_units = len(units)
    info = estimate_total()
    total_mdm_expected = info["total_mdm_estimates"]

    print(f"\n{'='*60}")
    print(f"Study/01 MC 扫描 — 并行模式")
    print(f"{'='*60}")
    print(f"工作单元: {total_units} 个 (参数组合×n)")
    print(f"每单元: {repeats} repeats × {len(delta_grid)} δ = {repeats*len(delta_grid)} MDM 估计")
    print(f"MDM 总估计: {total_mdm_expected:,}")
    print(f"并行进程: {n_workers}")
    print(f"预估时间(97ms/call): ~{total_mdm_expected * 97 / 1000 / 3600 / n_workers:.1f} 小时")
    print(f"启动时间: {now_local()}")
    print(f"{'='*60}\n")

    os.makedirs(SHARED_DATA_DIR, exist_ok=True)

    mdm_path = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
    mle_path = os.path.join(SHARED_DATA_DIR, "mle_anchor.csv")

    mdm_fields = [
        "beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id", "delta",
        "beta_hat", "eta_hat", "gamma_hat", "r_squared", "converged",
        "time_ms", "status",
    ]
    mle_fields = [f for f in mdm_fields if f != "delta"]

    # 写表头
    with open(mdm_path, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=mdm_fields).writeheader()
    with open(mle_path, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=mle_fields).writeheader()

    # 进度追踪
    progress = {
        "started_at": now_iso(),
        "total_units": total_units,
        "completed_units": 0,
        "total_mdm_rows": 0,
        "total_mle_rows": 0,
    }

    worker_fn = partial(
        process_unit,
        repeats=repeats,
        delta_grid=delta_grid,
        seed_ns=seed_ns,
    )

    t_start = time.perf_counter()
    mdm_total = 0
    mle_total = 0

    with mp.Pool(n_workers) as pool:
        for i, (mdm_rows, mle_rows) in enumerate(pool.imap_unordered(worker_fn, units)):
            # 追加写入 CSV
            with open(mdm_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=mdm_fields)
                writer.writerows(mdm_rows)
            with open(mle_path, "a", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=mle_fields)
                writer.writerows(mle_rows)

            mdm_total += len(mdm_rows)
            mle_total += len(mle_rows)
            completed = i + 1
            elapsed = time.perf_counter() - t_start
            speed = mdm_total / elapsed if elapsed > 0 else 0
            eta_sec = (total_mdm_expected - mdm_total) / speed if speed > 0 else 0

            # 每 5 个单元打印进度
            if completed % 5 == 0 or completed == total_units:
                pct = mdm_total / total_mdm_expected * 100
                eta_h = eta_sec / 3600
                print(f"[{now_local()}] 单元 {completed}/{total_units} | "
                      f"MDM {mdm_total:,}/{total_mdm_expected:,} ({pct:.1f}%) | "
                      f"速度 {speed:.0f} est/s | ETA {eta_h:.1f}h")

                # 更新 progress.json
                progress["completed_units"] = completed
                progress["total_mdm_rows"] = mdm_total
                progress["total_mle_rows"] = mle_total
                progress["elapsed_seconds"] = elapsed
                progress["eta_seconds"] = eta_sec
                with open(os.path.join(SHARED_DATA_DIR, "progress.json"), "w") as f:
                    json.dump(progress, f, indent=2)

    total_elapsed = time.perf_counter() - t_start

    # 写 manifest
    manifest = {
        "run_id": "E1E2_mc_scan_v1",
        "created_at": now_iso(),
        "code_entry": "code/generate_mc_data.py",
        "git_commit": get_git_info(),
        "python_version": sys.version.split()[0],
        "parameter_grid": {
            "beta": BETA_GRID,
            "eta": ETA_GRID,
            "gamma_over_eta": GAMMA_OVER_ETA_GRID,
            "n": N_GRID,
        },
        "delta_grid": delta_grid,
        "repeats": repeats,
        "seed_namespace": seed_ns,
        "n_workers": n_workers,
        "total_mdm_estimates": mdm_total,
        "total_mle_estimates": mle_total,
        "elapsed_seconds": total_elapsed,
        "output_files": ["mc_scan_raw.csv", "mle_anchor.csv", "manifest.json", "progress.json"],
        "metrics_contract": {
            "primary": "J1 = sqrt(mean[(db/b)^2 + (de/e)^2 + (dg/e)^2])",
            "gamma_normalization": "divided by eta (scale parameter), not gamma itself",
            "weights": "equal (w_beta = w_eta = w_gamma = 1)",
            "auxiliary": ["bias_beta", "sd_beta", "bias_eta", "sd_eta", "bias_gamma", "sd_gamma"],
            "gate": "failure_rate",
        },
        "notes": "E1/E2 共用 MC 扫描数据。E1 分析按 (delta) 聚合得 L1/L2，E2 按 (beta+n) 等聚合得 L3-L6 oracle。",
    }
    with open(os.path.join(SHARED_DATA_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"完成！")
    print(f"MDM 估计: {mdm_total:,} | MLE 估计: {mle_total:,}")
    print(f"总耗时: {total_elapsed/3600:.2f} 小时")
    print(f"输出: {SHARED_DATA_DIR}")
    print(f"{'='*60}")


# ============================================================
# 串行执行器（调试/pilot 用）
# ============================================================

def run_serial(repeats, delta_grid, seed_ns):
    """串行执行（调试/pilot 用）。"""
    units = build_work_units()
    total_units = len(units)

    print(f"\n{'='*60}")
    print(f"Study/01 MC 扫描 — 串行模式")
    print(f"{'='*60}")
    print(f"工作单元: {total_units} | repeats: {repeats} | δ: {len(delta_grid)}")
    print(f"启动时间: {now_local()}")
    print(f"{'='*60}\n")

    os.makedirs(SHARED_DATA_DIR, exist_ok=True)

    mdm_path = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
    mle_path = os.path.join(SHARED_DATA_DIR, "mle_anchor.csv")

    mdm_fields = [
        "beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id", "delta",
        "beta_hat", "eta_hat", "gamma_hat", "r_squared", "converged",
        "time_ms", "status",
    ]
    mle_fields = [f for f in mdm_fields if f != "delta"]

    with open(mdm_path, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=mdm_fields).writeheader()
    with open(mle_path, "w", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=mle_fields).writeheader()

    mdm_total = 0
    mle_total = 0
    t_start = time.perf_counter()

    for ui, unit in enumerate(units):
        mdm_rows, mle_rows = process_unit(
            unit, repeats=repeats, delta_grid=delta_grid, seed_ns=seed_ns
        )

        with open(mdm_path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=mdm_fields).writerows(mdm_rows)
        with open(mle_path, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=mle_fields).writerows(mle_rows)

        mdm_total += len(mdm_rows)
        mle_total += len(mle_rows)

        elapsed = time.perf_counter() - t_start
        print(f"[{now_local()}] 单元 {ui+1}/{total_units} ({unit['beta']},γ/η={unit['gamma_over_eta']},n={unit['n']}) "
              f"| MDM {mdm_total:,} | {elapsed:.0f}s")

    print(f"\n完成！MDM {mdm_total:,} | MLE {mle_total:,} | {time.perf_counter()-t_start:.0f}s")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Study/01 MC 扫描数据生成")
    parser.add_argument("--serial", action="store_true", help="串行模式（调试用）")
    parser.add_argument("--pilot", action="store_true", help="Pilot 模式（R=10 小规模验证）")
    parser.add_argument("--workers", type=int, default=None, help="并行进程数（覆盖 config）")
    args = parser.parse_args()

    if args.pilot:
        repeats = 10
        delta_grid = [0.0, 0.1, 0.2, 0.3]  # pilot 只跑 4 个 δ
        print("*** PILOT 模式: R=10, δ=[0.0,0.1,0.2,0.3] ***")
    else:
        repeats = R_MAIN
        delta_grid = DELTA_GRID

    n_workers = args.workers if args.workers else N_WORKERS

    if args.serial or args.pilot:
        run_serial(repeats, delta_grid, SEED_NAMESPACE)
    else:
        run_parallel(repeats, delta_grid, SEED_NAMESPACE, n_workers)
