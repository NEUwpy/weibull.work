"""Study/02 P-Q r4：修复 v2 evidence 的键 schema（不重训；源/目标显式锁定 v2）。

背景：v2 evidence 曾以 keys.astype(np.int32) 存储 (beta, gamma_over_eta, n, repeat_id)，
截断了分数 beta（1.5->1）与 gamma/eta（0.1->0）。本脚本从 v2 完整精度预测 CSV 重写
v2 evidence npz，采用精确 dtype。源/目标目录**显式硬编码为 artifacts/pq_v2**，
与活动 r4 primary 配置（artifacts/pq_v3）解耦，避免误修 r4 证据。

用法：
    python code/study02pq/repair_evidence.py [--verify]
"""

from __future__ import annotations

import os
import sys

import numpy as np
import pandas as pd

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

# 显式 v2 目录（与活动 CFG.ARTIFACT_DIR=pq_v3 解耦；Codex R4-04）
_V2_ARTIFACT = os.path.join(os.path.dirname(STUDY02_CODE_DIR), "artifacts", "pq_v2")
V2_PREDICTIONS_DIR = os.path.join(_V2_ARTIFACT, "predictions")
V2_EVIDENCE_DIR = os.path.join(_V2_ARTIFACT, "evidence")

PRED_COLS = ["beta_hat", "eta_hat", "gamma_hat", "x95_hat", "x95_true", "min_x",
             "rel_err", "rel_err_sq", "rel_b", "rel_e", "rel_g"]


def v2_prediction_csv_path(fit: str) -> str:
    return os.path.join(V2_PREDICTIONS_DIR, f"{fit}.csv")


def v2_evidence_npz_path(fit: str) -> str:
    return os.path.join(V2_EVIDENCE_DIR, f"{fit}.npz")


def repair_one_v2(fit: str, verify: bool = True) -> dict:
    csv_path = v2_prediction_csv_path(fit)
    npz_path = v2_evidence_npz_path(fit)
    if not os.path.isfile(csv_path):
        return {"fit": fit, "status": "no_csv"}
    df = pd.read_csv(csv_path)
    keys_beta = df["beta"].to_numpy(dtype=np.float64)
    keys_goe = df["gamma_over_eta"].to_numpy(dtype=np.float64)
    keys_n = df["n"].to_numpy().astype(np.int32)
    keys_rid = df["repeat_id"].to_numpy().astype(np.int32)
    assert np.all(keys_n >= 7) and np.all(keys_n <= 20)
    assert np.all(keys_rid >= 0)
    np.savez_compressed(
        npz_path,
        keys_beta=keys_beta, keys_gamma_over_eta=keys_goe,
        keys_n=keys_n, keys_repeat_id=keys_rid,
        **{c: df[c].to_numpy(dtype=np.float32) for c in PRED_COLS},
    )
    if verify:
        d = np.load(npz_path)
        ok = (np.array_equal(d["keys_beta"], keys_beta)
              and np.array_equal(d["keys_gamma_over_eta"], keys_goe)
              and np.array_equal(d["keys_n"], keys_n)
              and np.array_equal(d["keys_repeat_id"], keys_rid))
        assert ok, f"repair round-trip mismatch for {fit}"
    return {"fit": fit, "status": "repaired", "n": int(len(df))}


def main():
    verify = "--verify" in sys.argv
    if not os.path.isdir(V2_PREDICTIONS_DIR):
        print(f"v2 predictions dir missing: {V2_PREDICTIONS_DIR}")
        return
    fits = [f[:-4] for f in sorted(os.listdir(V2_PREDICTIONS_DIR)) if f.endswith(".csv")]
    repaired, missing = 0, 0
    for fit in fits:
        res = repair_one_v2(fit, verify=verify)
        if res["status"] == "repaired":
            repaired += 1
        else:
            missing += 1
    print(f"v2 repaired={repaired} missing_csv={missing} of {len(fits)}")
    print("EVIDENCE REPAIR DONE (target: v2)")


if __name__ == "__main__":
    main()
