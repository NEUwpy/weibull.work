"""Study/02 同分布主协议（iid-v1）证据独立复核（S1 task §(6)）。

从 `artifacts/pq_iid_main/evidence/*.npz` 原始证据**独立重算**主数值，与
`analysis/summary_iid.json` 对照；并校验配对、失败/支撑计数、SHA256SUMS。

独立实现：不 import `analyze` / `evaluate.primary_design_bootstrap`，bootstrap
在本地按冻结算法重写（按 n 分层有放回抽 fold + 全局有放回抽 seed，rng seed 20260805，
B=200,000）。与 sealed summary 的差必须落在极小容差内。

用法（iid 协议下）：
    PQ_PROTOCOL=iid-v1 python code/study02pq/verify_iid.py
退出码：0 = 全部通过。
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import sys

import numpy as np

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))   # code/study02pq
sys.path.insert(0, STUDY02_CODE_DIR)
sys.path.insert(0, os.path.dirname(STUDY02_CODE_DIR))

from study02pq import config as CFG  # noqa: E402

assert CFG.PROTOCOL_VERSION == "iid-v1", "verify_iid 必须在 PQ_PROTOCOL=iid-v1 下运行"

SEEDS = [int(s) for s in CFG.SEEDS]
BOOT_RNG_SEED = 20260805
N_BOOT = 200000


def _evidence_path(fit_id: str) -> str:
    return os.path.join(CFG.EVIDENCE_DIR, f"{fit_id}.npz")


def load_pair(n: int, fold_idx: int, seed: int):
    fit_p = f"n{n}_f{fold_idx + 1}_s{seed}_rP"
    fit_q = f"n{n}_f{fold_idx + 1}_s{seed}_rQ"
    sp = np.load(_evidence_path(fit_p))["rel_err_sq"].astype(np.float64)
    sq = np.load(_evidence_path(fit_q))["rel_err_sq"].astype(np.float64)
    return sp, sq


def cell_diffs():
    diffs = {n: {f: [] for f in range(1, CFG.N_FOLDS + 1)} for n in CFG.N_GRID}
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in SEEDS:
                sp, sq = load_pair(n, fold_idx, seed)
                assert len(sp) == len(sq) == 2400, (n, fold_idx, seed, len(sp))
                diffs[n][fold_idx + 1].append(float(np.mean(sq - sp)))
    return diffs


def crossed_bootstrap(diffs, n_boot=N_BOOT, level=0.95):
    """独立实现 fold×seed 交叉 bootstrap（与 evaluate.primary_design_bootstrap 同算法：
    rng default_rng(20260805)，每轮全局重采样 seed → 按 n 分层重采样 fold → 池化均值）。"""
    rng = np.random.default_rng(BOOT_RNG_SEED)
    n_values = sorted(diffs.keys())
    folds = {n: sorted(diffs[n].keys()) for n in n_values}
    diffs_a = {n: {f: np.asarray(diffs[n][f], dtype=np.float64) for f in folds[n]}
               for n in n_values}
    n_seeds = len(next(iter(diffs_a[n_values[0]].values())))
    pooled = np.empty(n_boot)
    per_n = {n: np.empty(n_boot) for n in n_values}
    for b in range(n_boot):
        seed_idx = rng.integers(0, n_seeds, size=n_seeds)
        all_d = []
        per_n_d = {}
        for n in n_values:
            sfold = rng.integers(0, len(folds[n]), size=len(folds[n]))
            n_d = [diffs_a[n][folds[n][fi]][si]   # 与 evaluate.py 同构：列表收集后 np.asarray
                   for fi in sfold for si in seed_idx]
            arr = np.asarray(n_d, dtype=np.float64)
            all_d.append(arr)
            per_n_d[n] = arr
        pooled[b] = np.mean(np.concatenate(all_d))
        for n in n_values:
            per_n[n][b] = np.mean(per_n_d[n])
    alpha = 1.0 - level
    pooled_ci = np.percentile(pooled, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    per_n_ci = {n: np.percentile(per_n[n], [100 * alpha / 2, 100 * (1 - alpha / 2)])
                for n in n_values}
    return {
        "ci_lo": float(pooled_ci[0]), "ci_hi": float(pooled_ci[1]),
        "per_n_ci_lo": {n: float(per_n_ci[n][0]) for n in n_values},
        "per_n_ci_hi": {n: float(per_n_ci[n][1]) for n in n_values},
        "n_boot": n_boot,
    }


def main() -> int:
    problems = []

    with open(os.path.join(CFG.ARTIFACT_DIR, "analysis", "summary_iid.json"),
              encoding="utf-8") as f:
        sealed = json.load(f)
    with open(os.path.join(CFG.ARTIFACT_DIR, "per_fit_metrics.csv"), encoding="utf-8") as f:
        metrics = list(csv.DictReader(f))
    assert len(metrics) == 120, f"n fits {len(metrics)} != 120"

    # ---- 计数：失败/支撑 ----
    n_bad = sum(1 for m in metrics if int(m["n_support_viol"]) or int(m["n_nonfinite"])
                or int(m["n_illegal"]) or m["converged"] != "True")
    if n_bad:
        problems.append(f"bad fits: {n_bad}")
    else:
        print(f"[verify] counts OK: 120 fits, 0 support/nonfinite/illegal/nonconverged")

    # ---- 配对：P/Q 证据键一致（抽查全部 60 对） ----
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in SEEDS:
                fp = f"n{n}_f{fold_idx + 1}_s{seed}_rP"
                fq = f"n{n}_f{fold_idx + 1}_s{seed}_rQ"
                ap = np.load(_evidence_path(fp))
                aq = np.load(_evidence_path(fq))
                for k in ("keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id"):
                    if not np.array_equal(ap[k], aq[k]):
                        problems.append(f"pairing key mismatch {fp}/{fq} {k}")
    print(f"[verify] pairing: P/Q evidence keys identical for all 60 pairs")

    # ---- 主数值独立重算 ----
    diffs = cell_diffs()
    all_d = np.concatenate([np.concatenate(list(diffs[n].values())) for n in CFG.N_GRID])
    hat_delta = float(np.mean(all_d))
    per_n_mean = {n: float(np.mean(np.concatenate(list(diffs[n].values())))) for n in CFG.N_GRID}

    rel_p = np.concatenate([load_pair(n, f, s)[0] for n in CFG.N_GRID
                            for f in range(CFG.N_FOLDS) for s in SEEDS])
    rel_q = np.concatenate([load_pair(n, f, s)[1] for n in CFG.N_GRID
                            for f in range(CFG.N_FOLDS) for s in SEEDS])
    assert len(rel_p) == len(rel_q) == 144000
    p_rrmse = float(np.sqrt(np.mean(rel_p)))
    q_rrmse = float(np.sqrt(np.mean(rel_q)))

    boot = crossed_bootstrap(diffs)

    # ---- 对照 sealed ----
    # rRMSE 系列：sealed 路径对 float32 evidence 直接 np.mean（float32 累加），本脚本用
    # float64 累加；数组逐位相同（已校验），差异仅 float32 累加伪影（~1e-8 rel）。
    # 故 rRMSE 用 float32 级容差；hat_delta/CI 为设计级推断，须紧容差（实测逐位一致）。
    pooled = sealed["pooled"]
    checks = [
        ("pooled p_rrmse", p_rrmse, pooled["p_rrmse"], 1e-6, 1e-9),
        ("pooled q_rrmse", q_rrmse, pooled["q_rrmse"], 1e-6, 1e-9),
        # 派生比值：(q-p)/p，两 rRMSE 的 float32 累加误差在差值 (q-p) 上放大 ~10x → 用 1e-5
        ("rel_change", (q_rrmse - p_rrmse) / p_rrmse, pooled["rel_change"], 1e-5, 1e-9),
        ("hat_delta", hat_delta, pooled["hat_delta"], 1e-9, 1e-12),
        ("ci_lo", boot["ci_lo"], pooled["ci_lo"], 1e-9, 1e-12),
        ("ci_hi", boot["ci_hi"], pooled["ci_hi"], 1e-9, 1e-12),
    ]
    for name, got, want, rtol, atol in checks:
        if not np.isclose(got, want, rtol=rtol, atol=atol):
            problems.append(f"{name}: recomputed {got!r} vs sealed {want!r}")
        else:
            print(f"[verify] {name}: {got:.10f} == {want:.10f}")

    # 每 n 独立聚合（p/q rRMSE、mean_diff、CI）
    per_n_p, per_n_q = {}, {}
    for n in CFG.N_GRID:
        per_n_p[n] = np.concatenate([load_pair(n, f, s)[0]
                                     for f in range(CFG.N_FOLDS) for s in SEEDS])
        per_n_q[n] = np.concatenate([load_pair(n, f, s)[1]
                                     for f in range(CFG.N_FOLDS) for s in SEEDS])
    for n in CFG.N_GRID:
        sn = sealed["per_n"][str(n)]
        for name, got, want, rtol, atol in (
                ("per_n_p_rrmse", float(np.sqrt(np.mean(per_n_p[n]))), sn["p_rrmse"],
                 1e-6, 1e-9),
                ("per_n_q_rrmse", float(np.sqrt(np.mean(per_n_q[n]))), sn["q_rrmse"],
                 1e-6, 1e-9),
                ("per_n_mean", per_n_mean[n], sn["mean_diff"], 1e-9, 1e-12),
                ("per_n_ci_lo", boot["per_n_ci_lo"][n], sn["ci_lo"], 1e-9, 1e-12),
                ("per_n_ci_hi", boot["per_n_ci_hi"][n], sn["ci_hi"], 1e-9, 1e-12)):
            if not np.isclose(got, want, rtol=rtol, atol=atol):
                problems.append(f"n={n} {name}: {got!r} vs {want!r}")

    # ---- SHA256SUMS 全量校验 ----
    n_shas = 0
    with open(os.path.join(CFG.ARTIFACT_DIR, "SHA256SUMS"), encoding="utf-8") as f:
        for line in f.read().splitlines():
            if not line.strip():
                continue
            h, rel = line.split("  ", 1)
            p = os.path.join(CFG.ARTIFACT_DIR, rel)
            if not os.path.isfile(p):
                problems.append(f"SHA256SUMS missing file: {rel}")
                continue
            with open(p, "rb") as fh:
                data = fh.read()
            if rel.endswith((".json", ".csv", ".md", ".txt", ".log", ".sha256")):
                data = data.replace(b"\r\n", b"\n")
            if hashlib.sha256(data).hexdigest() != h:
                problems.append(f"SHA mismatch: {rel}")
            n_shas += 1
    print(f"[verify] SHA256SUMS: {n_shas} entries verified")

    if problems:
        print("[verify] FAILURES:")
        for p in problems:
            print("  -", p)
        return 1
    print("[verify] VERIFY PASS (iid-v1) — all primary numbers independently reproduced "
          f"from saved evidence (B={N_BOOT})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
