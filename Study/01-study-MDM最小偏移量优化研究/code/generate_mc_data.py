"""
Study/01 — E1/E2 共用 MC 扫描数据生成

功能：
- 遍历参数网格 × n × repeats × δ_grid
- 对每个 (样本, δ) 调用 MDM 估计，记录 β̂/η̂/γ̂
- 同时对每个样本调用一次 MLE（锚点，无 δ 循环）
- 断点续跑：每个工作单元写独立分片文件，中断后重启自动跳过已完成分片
- 温和并行：multiprocessing Pool, N_WORKERS 个进程

输出结构（分片模式）：
    artifacts/formal/shared_data/
        chunks/
            chunk_0000_mdm.csv    — 工作单元0的MDM分片
            chunk_0000_mle.csv    — 工作单元0的MLE分片
            chunk_0001_mdm.csv    — 工作单元1的MDM分片
            ...
        mc_scan_raw.csv           — 最终合并的MDM结果（run结束后生成）
        mle_anchor.csv            — 最终合并的MLE结果
        manifest.json             — 实验溯源信息
        progress.json             — 运行进度

断点续跑机制：
- 每个工作单元 = 1个分片文件对 (chunk_XXXX_mdm.csv + chunk_XXXX_mle.csv)
- 分片文件含表头，可独立读取校验
- 重启时扫描 chunks/ 目录，跳过已存在的分片
- 所有分片完成后，自动合并为 mc_scan_raw.csv 和 mle_anchor.csv
- 如需强制重跑：删除 chunks/ 目录

用法：
    # 正式并行跑（默认）
    python generate_mc_data.py

    # 串行（调试/pilot 用）
    python generate_mc_data.py --serial

    # pilot 小规模验证
    python generate_mc_data.py --pilot

    # 只合并已有分片（不跑新的，用于分片已全部完成但合并失败的情况）
    python generate_mc_data.py --merge-only
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
    estimate_total,
)
from utils import get_git_info, now_iso, now_local
from studies.common.sample import generate_sample

# 分片输出目录
CHUNKS_DIR = os.path.join(SHARED_DATA_DIR, "chunks")

# CSV 列定义
MDM_FIELDS = [
    "beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id", "delta",
    "beta_hat", "eta_hat", "gamma_hat", "r_squared", "converged",
    "time_ms", "status",
]
MLE_FIELDS = [f for f in MDM_FIELDS if f != "delta"]


# ============================================================
# 工作单元定义
# ============================================================

def build_work_units():
    """构建所有工作单元。

    每个工作单元 = (beta, eta, gamma, gamma_over_eta, n)
    对应 R_MAIN 个样本 × len(DELTA_GRID) 个 δ。

    Returns:
        list of (index, unit_dict)
    """
    units = []
    idx = 0
    for eta in ETA_GRID:
        for goe in GAMMA_OVER_ETA_GRID:
            gamma = goe * eta
            for beta in BETA_GRID:
                for n in N_GRID:
                    units.append((idx, {
                        "beta": beta,
                        "eta": eta,
                        "gamma": gamma,
                        "gamma_over_eta": goe,
                        "n": n,
                    }))
                    idx += 1
    return units


# ============================================================
# 分片文件名 / 存在检查
# ============================================================

def chunk_paths(idx):
    """返回工作单元 idx 的分片文件路径。"""
    name = f"chunk_{idx:04d}"
    return (
        os.path.join(CHUNKS_DIR, f"{name}_mdm.csv"),
        os.path.join(CHUNKS_DIR, f"{name}_mle.csv"),
    )


def chunk_exists(idx):
    """检查工作单元 idx 的分片是否已存在（断点续跑用）。"""
    mdm_p, mle_p = chunk_paths(idx)
    return os.path.isfile(mdm_p) and os.path.isfile(mle_p)


def validate_chunk(idx, expected_mdm_rows, expected_mle_rows):
    """校验分片文件完整性（行数检查）。

    Returns:
        True 如果分片完整可用，False 如果需要重跑。
    """
    mdm_p, mle_p = chunk_paths(idx)
    try:
        with open(mdm_p, "r", encoding="utf-8") as f:
            mdm_lines = sum(1 for _ in f) - 1  # 减表头
        with open(mle_p, "r", encoding="utf-8") as f:
            mle_lines = sum(1 for _ in f) - 1
        return mdm_lines == expected_mdm_rows and mle_lines == expected_mle_rows
    except Exception:
        return False


# ============================================================
# 单个工作单元处理（子进程内执行）
# ============================================================

def process_and_save_unit(args):
    """处理一个工作单元并写入分片文件。

    子进程入口函数。接收 tuple 以兼容 multiprocessing pickle。

    Args:
        args: (idx, unit, repeats, delta_grid, seed_ns)

    Returns:
        (idx, n_mdm_rows, n_mle_rows, elapsed_sec) 或
        (idx, 0, 0, 0) 如果分片已存在（跳过）
    """
    idx, unit, repeats, delta_grid, seed_ns = args

    # 断点续跑：跳过已完成分片
    expected_mdm = repeats * len(delta_grid)
    expected_mle = repeats
    if chunk_exists(idx) and validate_chunk(idx, expected_mdm, expected_mle):
        return (idx, 0, 0, 0.0, "skipped")

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

    t_start = time.perf_counter()

    for rid in range(repeats):
        # 生成样本（同一份样本给 MDM 所有 δ 和 MLE）
        sample = generate_sample(beta, eta, gamma, n, rid, seed=seed_ns)

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

    elapsed = time.perf_counter() - t_start

    # 写分片文件（原子写入：先写临时文件再 rename）
    mdm_path, mle_path = chunk_paths(idx)
    mdm_tmp = mdm_path + ".tmp"
    mle_tmp = mle_path + ".tmp"

    with open(mdm_tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MDM_FIELDS)
        writer.writeheader()
        writer.writerows(mdm_rows)
    with open(mle_tmp, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MLE_FIELDS)
        writer.writeheader()
        writer.writerows(mle_rows)

    os.replace(mdm_tmp, mdm_path)  # Windows 上 os.replace 是原子操作
    os.replace(mle_tmp, mle_path)

    return (idx, len(mdm_rows), len(mle_rows), elapsed, "done")


# ============================================================
# 合并分片
# ============================================================

def merge_chunks(total_units):
    """将所有分片合并为最终 CSV 文件。

    Returns:
        (total_mdm_rows, total_mle_rows)
    """
    os.makedirs(SHARED_DATA_DIR, exist_ok=True)

    mdm_out = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
    mle_out = os.path.join(SHARED_DATA_DIR, "mle_anchor.csv")

    total_mdm = 0
    total_mle = 0

    with open(mdm_out, "w", newline="", encoding="utf-8") as f_mdm:
        writer_mdm = csv.DictWriter(f_mdm, fieldnames=MDM_FIELDS)
        writer_mdm.writeheader()

        with open(mle_out, "w", newline="", encoding="utf-8") as f_mle:
            writer_mle = csv.DictWriter(f_mle, fieldnames=MLE_FIELDS)
            writer_mle.writeheader()

            for idx in range(total_units):
                mdm_path, mle_path = chunk_paths(idx)
                if not os.path.isfile(mdm_path):
                    print(f"  警告: 分片 {idx} 缺失，跳过")
                    continue

                # 读 MDM 分片
                with open(mdm_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        writer_mdm.writerow(row)
                        total_mdm += 1

                # 读 MLE 分片
                with open(mle_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        writer_mle.writerow(row)
                        total_mle += 1

    return total_mdm, total_mle


# ============================================================
# 写 manifest
# ============================================================

def write_manifest(repeats, delta_grid, seed_ns, n_workers, total_mdm, total_mle,
                   elapsed_sec, unit_status_list):
    """写 manifest.json。"""
    manifest = {
        "run_id": "E1E2_mc_scan_v1",
        "created_at": now_iso(),
        "code_entry": "code/generate_mc_data.py",
        "git_commit": get_git_info(),
        "python_version": sys.version.split()[0],
        "method_versions": {
            "mdm": {
                "source": "python/methods/mdm.py",
                "class": "MDM",
                "run_signature": "run(offset: float, gamma_steps=60, rank_method='bernard')",
                "description": "Minimum Discrepancy Method, offset=delta gradient threshold",
            },
            "mle": {
                "source": "python/methods/mle.py",
                "class": "MLE",
                "run_signature": "run()",
                "description": "Standard MLE, gamma<x_(1) constraint, beta<1 => unbounded",
            },
            "sample": {
                "source": "python/studies/common/sample.py",
                "function": "generate_sample(beta, eta, gamma, n, repeat_id, seed)",
                "seed_scheme": "sha256(repr(seed)|repr(beta)|repr(eta)|repr(gamma)|n|repeat_id) -> 4 bytes -> np.random.default_rng",
            },
        },
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
        "total_mdm_estimates": total_mdm,
        "total_mle_estimates": total_mle,
        "elapsed_seconds": elapsed_sec,
        "unit_status": unit_status_list,
        "output_files": [
            "chunks/chunk_XXXX_mdm.csv (分片)",
            "chunks/chunk_XXXX_mle.csv (分片)",
            "mc_scan_raw.csv (合并后)",
            "mle_anchor.csv (合并后)",
            "manifest.json",
            "progress.json",
        ],
        "metrics_contract": {
            "primary": "J1 = sqrt(mean[(db/b)^2 + (de/e)^2 + (dg/e)^2])",
            "gamma_normalization": "divided by eta (scale parameter), not gamma itself",
            "weights": "equal (w_beta = w_eta = w_gamma = 1)",
            "auxiliary": ["bias_beta", "sd_beta", "bias_eta", "sd_eta", "bias_gamma", "sd_gamma"],
            "gate": "failure_rate",
        },
        "notes": (
            "E1/E2 共用 MC 扫描数据。"
            "每个(beta,eta,gamma,n)工作单元独立写入分片文件，支持断点续跑。"
            "断点续跑：删除 mc_scan_raw.csv 和 mle_anchor.csv 不会导致重跑，"
            "只有删除 chunks/ 目录下对应分片才会重跑该单元。"
            "E1 分析按 delta 聚合得 L1/L2，E2 按 (beta+n) 等聚合得 L3-L6 oracle。"
        ),
    }
    path = os.path.join(SHARED_DATA_DIR, "manifest.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


# ============================================================
# 并行执行器
# ============================================================

def run_parallel(repeats, delta_grid, seed_ns, n_workers):
    """并行执行所有工作单元。"""
    units = build_work_units()
    total_units = len(units)
    info = estimate_total()
    total_mdm_expected = info["total_mdm_estimates"]

    # 检查断点续跑状态
    os.makedirs(CHUNKS_DIR, exist_ok=True)
    skipped = sum(1 for idx, _ in units if chunk_exists(idx))
    fresh = total_units - skipped

    print(f"\n{'='*60}")
    print(f"Study/01 MC 扫描 — 并行模式（分片+断点续跑）")
    print(f"{'='*60}")
    print(f"工作单元: {total_units} 个")
    print(f"  已完成（跳过）: {skipped}")
    print(f"  待执行: {fresh}")
    print(f"每单元: {repeats} repeats × {len(delta_grid)} δ = {repeats*len(delta_grid)} MDM 估计")
    print(f"MDM 总估计: {total_mdm_expected:,}")
    print(f"并行进程: {n_workers}")
    if fresh > 0:
        print(f"预估时间(97ms/call): ~{fresh * repeats * len(delta_grid) * 97 / 1000 / 3600 / n_workers:.1f} 小时")
    print(f"启动时间: {now_local()}")
    print(f"{'='*60}\n")

    # 构建任务参数（只含未完成的单元）
    tasks = [
        (idx, unit, repeats, delta_grid, seed_ns)
        for idx, unit in units
        if not (chunk_exists(idx) and validate_chunk(idx, repeats * len(delta_grid), repeats))
    ]

    if not tasks:
        print("所有分片已完成，跳到合并步骤。")

    t_start = time.perf_counter()
    total_mdm = 0
    total_mle = 0
    completed_fresh = 0
    unit_status = []

    if tasks:
        with mp.Pool(n_workers) as pool:
            for idx, n_mdm, n_mle, elapsed, status in pool.imap_unordered(
                process_and_save_unit, tasks
            ):
                unit_status.append({"unit_idx": idx, "status": status,
                                    "mdm_rows": n_mdm, "mle_rows": n_mle,
                                    "elapsed": elapsed})
                if status == "done":
                    completed_fresh += 1
                    total_mdm += n_mdm
                    total_mle += n_mle
                elif status == "skipped":
                    pass  # 子进程内跳过（一般不会到这里，因为已在外层过滤）

                done = completed_fresh
                total_done_for_pct = skipped + completed_fresh
                pct = total_done_for_pct / total_units * 100
                elapsed_total = time.perf_counter() - t_start
                speed = total_mdm / elapsed_total if elapsed_total > 0 else 0
                remaining_units = len(tasks) - completed_fresh
                if speed > 0 and remaining_units > 0:
                    remaining_mdm = remaining_units * repeats * len(delta_grid)
                    eta_h = remaining_mdm / speed / 3600
                else:
                    eta_h = 0

                # 每5个单元或最后一个打印进度
                if done % 5 == 0 or done == len(tasks):
                    print(f"[{now_local()}] 完成 {total_done_for_pct}/{total_units} ({pct:.1f}%) | "
                          f"本轮跑了 {completed_fresh} | "
                          f"速度 {speed:.0f} est/s | ETA {eta_h:.1f}h")

                    # 更新 progress.json
                    progress = {
                        "updated_at": now_iso(),
                        "total_units": total_units,
                        "completed_units": total_done_for_pct,
                        "skipped_from_prev_run": skipped,
                        "completed_this_run": completed_fresh,
                        "total_mdm_this_run": total_mdm,
                        "total_mle_this_run": total_mle,
                        "elapsed_seconds": elapsed_total,
                        "eta_seconds": eta_h * 3600,
                    }
                    with open(os.path.join(SHARED_DATA_DIR, "progress.json"), "w") as f:
                        json.dump(progress, f, indent=2)

    total_elapsed = time.perf_counter() - t_start

    # ── 合并分片 ──
    print(f"\n[{now_local()}] 合并 {total_units} 个分片...")
    merged_mdm, merged_mle = merge_chunks(total_units)
    print(f"合并完成: MDM {merged_mdm:,} 行 | MLE {merged_mle:,} 行")

    # ── 写 manifest ──
    write_manifest(repeats, delta_grid, seed_ns, n_workers,
                   merged_mdm, merged_mle, total_elapsed, unit_status)

    print(f"\n{'='*60}")
    print(f"完成！")
    print(f"MDM 估计(合并): {merged_mdm:,} | MLE 估计: {merged_mle:,}")
    print(f"本轮耗时: {total_elapsed/3600:.2f} 小时 (跳过 {skipped} 个已有分片)")
    print(f"输出: {SHARED_DATA_DIR}")
    print(f"{'='*60}")


# ============================================================
# 串行执行器（调试/pilot 用）
# ============================================================

def run_serial(repeats, delta_grid, seed_ns):
    """串行执行（调试/pilot 用）。"""
    units = build_work_units()
    total_units = len(units)

    os.makedirs(CHUNKS_DIR, exist_ok=True)

    skipped = sum(1 for idx, _ in units if chunk_exists(idx))
    fresh = total_units - skipped

    print(f"\n{'='*60}")
    print(f"Study/01 MC 扫描 — 串行模式（分片+断点续跑）")
    print(f"{'='*60}")
    print(f"工作单元: {total_units} | repeats: {repeats} | δ: {len(delta_grid)}")
    print(f"已完成（跳过）: {skipped} | 待执行: {fresh}")
    print(f"启动时间: {now_local()}")
    print(f"{'='*60}\n")

    t_start = time.perf_counter()
    unit_status = []

    for idx, unit in units:
        if chunk_exists(idx) and validate_chunk(idx, repeats * len(delta_grid), repeats):
            print(f"[{now_local()}] 单元 {idx+1}/{total_units} 已存在，跳过")
            unit_status.append({"unit_idx": idx, "status": "skipped", "mdm_rows": 0, "mle_rows": 0})
            continue

        result = process_and_save_unit((idx, unit, repeats, delta_grid, seed_ns))
        _, n_mdm, n_mle, elapsed, status = result
        unit_status.append({"unit_idx": idx, "status": status,
                            "mdm_rows": n_mdm, "mle_rows": n_mle, "elapsed": elapsed})
        print(f"[{now_local()}] 单元 {idx+1}/{total_units} ({unit['beta']},γ/η={unit['gamma_over_eta']},n={unit['n']}) "
              f"| MDM {n_mdm} | {elapsed:.1f}s")

    total_elapsed = time.perf_counter() - t_start

    # 合并
    print(f"\n[{now_local()}] 合并分片...")
    merged_mdm, merged_mle = merge_chunks(total_units)
    write_manifest(repeats, delta_grid, seed_ns, 1, merged_mdm, merged_mle, total_elapsed, unit_status)

    print(f"\n完成！MDM {merged_mdm:,} | MLE {merged_mle:,} | {total_elapsed:.0f}s")


# ============================================================
# 主入口
# ============================================================

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Study/01 MC 扫描数据生成")
    parser.add_argument("--serial", action="store_true", help="串行模式（调试用）")
    parser.add_argument("--pilot", action="store_true", help="Pilot 模式（R=10 小规模验证）")
    parser.add_argument("--workers", type=int, default=None, help="并行进程数（覆盖 config）")
    parser.add_argument("--merge-only", action="store_true",
                        help="只合并已有分片，不跑新的（用于分片已完成但合并失败的情况）")
    args = parser.parse_args()

    # --merge-only 模式
    if args.merge_only:
        units = build_work_units()
        total_units = len(units)
        print(f"[{now_local()}] 只合并模式：合并 {total_units} 个分片...")
        merged_mdm, merged_mle = merge_chunks(total_units)
        write_manifest(R_MAIN, DELTA_GRID, SEED_NAMESPACE, 0,
                       merged_mdm, merged_mle, 0, [])
        print(f"完成: MDM {merged_mdm:,} | MLE {merged_mle:,}")
        sys.exit(0)

    if args.pilot:
        repeats = 10
        delta_grid = [0.0, 0.1, 0.2, 0.3]
        print("*** PILOT 模式: R=10, δ=[0.0,0.1,0.2,0.3] ***")
        # pilot 用独立目录避免覆盖正式数据
        os.environ["PILOT_MODE"] = "1"
    else:
        repeats = R_MAIN
        delta_grid = DELTA_GRID

    n_workers = args.workers if args.workers else N_WORKERS

    if args.serial or args.pilot:
        run_serial(repeats, delta_grid, SEED_NAMESPACE)
    else:
        run_parallel(repeats, delta_grid, SEED_NAMESPACE, n_workers)
