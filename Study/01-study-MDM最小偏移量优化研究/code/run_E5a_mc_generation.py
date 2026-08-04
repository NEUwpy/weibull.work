"""
Study/01 Formal E5a — Normalized-RAW 新设计 MC 数据生成

为最终样本自适应方法（归一化排序样本 -> 分 n MLP -> 损失曲线 -> 偏移量 -> MDM）
生成冻结参数设计的 MDM 损失数据：

  - beta     = {1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0}
  - eta      = 1000
  - gamma/eta= {0.10, 0.25, 0.50, 0.75, 1.00}
  - n        = {7, 10, 15, 20}
  - repeats  = 300
  - combos   = 160，样本 = 48,000，MDM 估计 = 1,248,000

结构（复用 E4 的 subprocess 并行 + 断点续跑 + fail-closed 校验）：
  - 每个组合一个分片 chunk_{idx:04d}_mdm.csv（300 样本 x 26 delta）+ meta json。
  - 编排器按组合索引轮询分配给 N_WORKERS 个 worker 子进程。
  - 全部完成后 merge 为 mc_scan_raw.csv 并写 manifest。
  - 任意校验失败即中止，不产生不完整正式数据。

用法：
    python run_E5a_mc_generation.py                 # 编排器：启动全部 worker + merge
    python run_E5a_mc_generation.py --worker 0      # 仅作为 worker 0
    python run_E5a_mc_generation.py --merge-only    # 已有分片时只合并

输出：
    artifacts/formal/E5_normalized_raw/shared_data/
      chunks/chunk_0000_mdm.csv ... chunk_0159_mdm.csv  (正式数据源，纳入 git)
      chunks/chunk_0000_meta.json ...                   (分片元数据)
      manifest.json                                     (正式 manifest)
      mc_scan_raw.csv                                   (合并后大文件，gitignore)
"""

import sys
import os
import csv
import json
import time
import argparse
import subprocess
from datetime import datetime, timezone
from itertools import product

# 路径设置 —— 模块级，供子进程导入
STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
STUDY_ROOT = os.path.dirname(STUDY_CODE_DIR)
PROJECT_ROOT = os.path.dirname(os.path.dirname(STUDY_ROOT))
PYTHON_DIR = os.path.join(PROJECT_ROOT, "python")

sys.path.insert(0, STUDY_CODE_DIR)
sys.path.insert(0, PYTHON_DIR)

import nrmc_config as CFG
from studies.common.sample import generate_sample
from methods.mdm import MDM

# ============================================================
# 并行规模
# ============================================================

# 默认 10 个 worker（i5-14400F：6P + 4E，~8.5 P-核当量）。
# 可用环境变量 NRMC_N_WORKERS 覆盖。
N_WORKERS = int(os.environ.get("NRMC_N_WORKERS", "10"))


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


def _git_commit():
    import subprocess
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=PROJECT_ROOT, stderr=subprocess.DEVNULL).decode().strip()
    except Exception:
        return "unknown"


FIELDS = [
    "beta", "eta", "gamma", "gamma_over_eta", "n",
    "repeat_id", "delta",
    "beta_hat", "eta_hat", "gamma_hat", "r_squared", "converged",
    "time_ms", "status",
]


def build_combos():
    """组合枚举顺序与五折留出的组合划分一致（product: beta, goe, n）。"""
    return list(product(CFG.BETA_GRID, CFG.GAMMA_OVER_ETA_GRID, CFG.N_GRID))


def combo_unit(idx):
    beta, goe, n = build_combos()[idx]
    gamma = goe * CFG.ETA
    return {
        "combo_idx": idx,
        "beta": beta, "eta": CFG.ETA, "gamma": gamma,
        "gamma_over_eta": goe, "n": n,
    }


def chunk_paths(idx):
    name = f"chunk_{idx:04d}"
    return (
        os.path.join(CFG.CHUNKS_DIR, f"{name}_mdm.csv"),
        os.path.join(CFG.CHUNKS_DIR, f"{name}_meta.json"),
    )


def chunk_exists(idx):
    mdm_p, meta_p = chunk_paths(idx)
    return os.path.isfile(mdm_p) and os.path.isfile(meta_p)


def write_chunk_meta(idx):
    mdm_p, meta_p = chunk_paths(idx)
    unit = combo_unit(idx)
    meta = {
        "run_id": "E5a_normalized_raw_mc_v1",
        "combo_idx": idx,
        "unit": {
            "beta": unit["beta"], "eta": unit["eta"], "gamma": unit["gamma"],
            "gamma_over_eta": unit["gamma_over_eta"], "n": unit["n"],
        },
        "repeats": CFG.REPEATS,
        "delta_grid": list(CFG.DELTA_GRID),
        "seed_namespace": CFG.SEED_NAMESPACE,
        "git_commit": _git_commit(),
        "created_at": _now_iso(),
    }
    with open(meta_p, "w", encoding="utf-8", newline="\n") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)


def process_combo_serial(idx, repeats):
    """对一个组合生成全部 (样本 x delta) 行。"""
    unit = combo_unit(idx)
    beta, eta, gamma, goe, n = unit["beta"], unit["eta"], unit["gamma"], \
        unit["gamma_over_eta"], unit["n"]
    rows = []
    for rid in range(repeats):
        sample = generate_sample(beta, eta, gamma, n, rid, seed=CFG.SEED_NAMESPACE)
        mdm = MDM(sample)
        for delta in CFG.DELTA_GRID:
            row = {
                "beta": beta, "eta": eta, "gamma": gamma,
                "gamma_over_eta": goe, "n": n,
                "repeat_id": rid, "delta": delta,
                "beta_hat": None, "eta_hat": None, "gamma_hat": None,
                "r_squared": None, "converged": False,
                "time_ms": 0.0, "status": "failure",
            }
            try:
                t0 = time.perf_counter()
                bh, eh, gh, r2, conv = mdm.run(offset=delta)
                elapsed_ms = (time.perf_counter() - t0) * 1000
                row["beta_hat"] = bh
                row["eta_hat"] = eh
                row["gamma_hat"] = gh
                row["r_squared"] = r2
                row["converged"] = bool(conv)
                row["time_ms"] = elapsed_ms
                row["status"] = "success" if conv and bh > 0 and eh > 0 else "failure"
            except Exception as e:
                row["status"] = f"error:{type(e).__name__}"
            rows.append(row)
    return rows


class ChunkValidationError(Exception):
    pass


def validate_chunk(df, idx):
    """校验一个分片：行数、组合键唯一性、repeat 与 delta 覆盖、元数据匹配。"""
    import pandas as pd
    unit = combo_unit(idx)
    expected_rows = CFG.REPEATS * len(CFG.DELTA_GRID)
    if len(df) != expected_rows:
        raise ChunkValidationError(
            f"chunk_{idx:04d}: {len(df)} rows != expected {expected_rows}")
    # 组合键全部一致
    bad_keys = df[['beta', 'eta', 'gamma', 'gamma_over_eta', 'n']].apply(
        lambda r: not (float(r['beta']) == unit['beta']
                       and float(r['eta']) == unit['eta']
                       and float(r['gamma']) == unit['gamma']
                       and float(r['gamma_over_eta']) == unit['gamma_over_eta']
                       and int(r['n']) == unit['n']), axis=1).sum()
    if bad_keys:
        raise ChunkValidationError(f"chunk_{idx:04d}: {bad_keys} rows with wrong combo keys")
    # repeat / delta 覆盖
    if df['repeat_id'].nunique() != CFG.REPEATS:
        raise ChunkValidationError(f"chunk_{idx:04d}: repeat coverage wrong")
    if sorted(df['delta'].unique()) != CFG.DELTA_GRID:
        raise ChunkValidationError(f"chunk_{idx:04d}: delta coverage wrong")
    # 无重复键
    dups = df.duplicated(subset=['repeat_id', 'delta']).sum()
    if dups:
        raise ChunkValidationError(f"chunk_{idx:04d}: {dups} duplicate (repeat_id, delta) keys")
    # 元数据匹配
    _mdm_p, meta_p = chunk_paths(idx)
    if os.path.isfile(meta_p):
        meta = json.load(open(meta_p, encoding="utf-8"))
        if meta["unit"] != unit:
            raise ChunkValidationError(f"chunk_{idx:04d}: meta unit mismatch")
        if meta["repeats"] != CFG.REPEATS:
            raise ChunkValidationError(f"chunk_{idx:04d}: meta repeats mismatch")
    return True


def worker_main(worker_id):
    os.makedirs(CFG.CHUNKS_DIR, exist_ok=True)
    combos = build_combos()
    my_indices = [i for i in range(len(combos)) if i % N_WORKERS == worker_id]
    total_calls = len(my_indices) * CFG.REPEATS * len(CFG.DELTA_GRID)
    print(f"[Worker {worker_id}] {len(my_indices)} combos, ~{total_calls:,} calls", flush=True)
    t0 = time.time()
    for ci, idx in enumerate(my_indices):
        if chunk_exists(idx):
            print(f"[Worker {worker_id}] chunk_{idx:04d} exists, skip", flush=True)
            continue
        combo_t0 = time.time()
        rows = process_combo_serial(idx, CFG.REPEATS)
        mdm_p, _ = chunk_paths(idx)
        with open(mdm_p, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=FIELDS)
            writer.writeheader()
            writer.writerows(rows)
        write_chunk_meta(idx)
        combo_elapsed = time.time() - combo_t0
        print(f"[Worker {worker_id}] chunk_{idx:04d} "
              f"(beta={combo_unit(idx)['beta']}, "
              f"goe={combo_unit(idx)['gamma_over_eta']}, "
              f"n={combo_unit(idx)['n']}) done in {combo_elapsed:.1f}s "
              f"({ci+1}/{len(my_indices)}, total {time.time()-t0:.0f}s)", flush=True)
    print(f"[Worker {worker_id}] COMPLETE in {time.time()-t0:.1f}s", flush=True)


def merge_chunks():
    import pandas as pd
    combos = build_combos()
    frames = []
    for idx in range(len(combos)):
        mdm_p, _ = chunk_paths(idx)
        if not os.path.isfile(mdm_p):
            print(f"*** ABORTING: chunk_{idx:04d} missing, cannot merge ***")
            sys.exit(1)
        df = pd.read_csv(mdm_p)
        try:
            validate_chunk(df, idx)
        except ChunkValidationError as e:
            print(f"*** ABORTING: {e} ***")
            sys.exit(1)
        frames.append(df)
    df_all = pd.concat(frames, ignore_index=True)
    expected = len(combos) * CFG.REPEATS * len(CFG.DELTA_GRID)
    if len(df_all) != expected:
        print(f"*** ABORTING: merged rows {len(df_all)} != expected {expected} ***")
        sys.exit(1)
    dup = df_all.duplicated(
        subset=['beta', 'gamma_over_eta', 'n', 'repeat_id', 'delta']).sum()
    if dup:
        print(f"*** ABORTING: {dup} duplicate keys in merged data ***")
        sys.exit(1)
    # 原子写
    tmp = CFG.MC_SCAN_PATH + ".tmp"
    df_all.to_csv(tmp, index=False)
    os.replace(tmp, CFG.MC_SCAN_PATH)
    print(f"Merged {len(df_all):,} rows -> {CFG.MC_SCAN_PATH}")
    print(f"Non-success rate: {(df_all['status'] != 'success').mean():.4f}")
    return df_all


def write_manifest(elapsed_s):
    unit_status = []
    for idx in range(len(build_combos())):
        mdm_p, _ = chunk_paths(idx)
        meta_p = chunk_paths(idx)[1]
        unit_status.append({
            "combo_idx": idx,
            "status": "done" if os.path.isfile(mdm_p) else "missing",
            "mdm_rows": CFG.REPEATS * len(CFG.DELTA_GRID),
            "git_commit": json.load(open(meta_p, encoding="utf-8"))["git_commit"]
            if os.path.isfile(meta_p) else None,
        })
    manifest = {
        "run_id": "E5a_normalized_raw_mc_v1",
        "created_at": _now_iso(),
        "code_entry": "code/run_E5a_mc_generation.py",
        "git_commit": _git_commit(),
        "python_version": sys.version.split()[0],
        "method_versions": {
            "mdm": {"source": "python/methods/mdm.py", "class": "MDM",
                    "run_signature": "run(offset, gamma_steps=60, rank_method='bernard')"},
            "sample": {"source": "python/studies/common/sample.py",
                       "function": "generate_sample(beta, eta, gamma, n, repeat_id, seed)"},
        },
        "design": CFG.design_summary(),
        "must_include_combo": {"beta": 2.0, "eta": 1000.0, "gamma": 1000.0},
        "n_workers": N_WORKERS,
        "elapsed_seconds": elapsed_s,
        "unit_status": unit_status,
        "output_files": [
            "chunks/chunk_XXXX_mdm.csv (分片，正式数据源)",
            "chunks/chunk_XXXX_meta.json (分片元数据)",
            "manifest.json",
            "mc_scan_raw.csv (合并后，gitignore)",
        ],
        "loss_contract": ("((beta_hat-beta)/beta)^2 + ((eta_hat-eta)/eta)^2 + "
                          "((gamma_hat-gamma)/eta)^2 ; 失败候选由训练失败合同处理"),
    }
    with open(CFG.MC_MANIFEST_PATH, "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"Wrote {CFG.MC_MANIFEST_PATH}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", type=int, default=None)
    parser.add_argument("--merge-only", action="store_true")
    args = parser.parse_args()

    if args.worker is not None:
        worker_main(args.worker)
        return

    if args.merge_only:
        merge_chunks()
        return

    os.makedirs(CFG.CHUNKS_DIR, exist_ok=True)
    combos = build_combos()
    total_calls = len(combos) * CFG.REPEATS * len(CFG.DELTA_GRID)
    print("=" * 70)
    print("Study/01 Formal E5a — Normalized-RAW MC generation")
    print(f"Started: {_now_iso()}")
    print(f"Workers: {N_WORKERS} | Combos: {len(combos)} | MDM calls: {total_calls:,}")
    print(f"Output: {CFG.CHUNKS_DIR}")
    print("=" * 70)

    script_path = os.path.abspath(__file__)
    t0 = time.time()
    procs = []
    for wid in range(N_WORKERS):
        p = subprocess.Popen(
            [sys.executable, script_path, "--worker", str(wid)],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=PROJECT_ROOT,
        )
        procs.append(p)
        print(f"Started worker {wid} (PID {p.pid})")

    worker_failures = []
    for wid, p in enumerate(procs):
        p.wait()
        elapsed = time.time() - t0
        if p.returncode != 0:
            worker_failures.append(wid)
        print(f"Worker {wid} finished (exit={p.returncode}, {elapsed:.0f}s elapsed)")
        if p.stdout:
            output = p.stdout.read().decode("utf-8", errors="replace")
            for line in output.strip().split("\n")[-5:]:
                print(f"  [W{wid}] {line}")
    if worker_failures:
        print(f"\n*** ABORTING: workers {worker_failures} failed ***")
        sys.exit(1)

    total_elapsed = time.time() - t0
    print(f"\nAll workers done in {total_elapsed:.1f}s ({total_elapsed/60:.1f} min)")

    # Fail-closed: every chunk present + valid
    missing = [i for i in range(len(combos)) if not chunk_exists(i)]
    if missing:
        print(f"\n*** ABORTING: missing chunks {missing[:20]}... ***")
        sys.exit(1)
    import pandas as pd
    for idx in range(len(combos)):
        mdm_p, _ = chunk_paths(idx)
        df = pd.read_csv(mdm_p)
        try:
            validate_chunk(df, idx)
        except ChunkValidationError as e:
            print(f"\n*** ABORTING: {e} ***")
            sys.exit(1)
    print("All 160 chunks present and validated.")

    merge_chunks()
    write_manifest(total_elapsed)
    print(f"\n{'='*70}\nMC GENERATION COMPLETE in {total_elapsed:.0f}s\n{'='*70}")


if __name__ == "__main__":
    main()
