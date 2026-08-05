"""Study/02 P-Q r4：修复 v2 evidence 的键 schema（不重训）。

v2 evidence 曾以 keys.astype(np.int32) 存储 (beta, gamma_over_eta, n, repeat_id)，
截断了分数 beta（1.5→1）与 gamma/eta（0.1→0）。本脚本从完整精度预测 CSV
（artifacts/pq_v2/predictions/<fit>.csv，键为 float64/int64 精确值）重写
artifacts/pq_v2/evidence/<fit>.npz，采用精确 dtype：
  keys_beta / keys_gamma_over_eta = float64
  keys_n / keys_repeat_id = int32
预测数组保持 float32。不训练、不改模型、不碰原始 CSV。

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

from study02pq import run as RUN  # noqa: E402
from study02pq import training as TR  # noqa: E402
from study02pq import config as CFG  # noqa: E402

PRED_COLS = ["beta_hat", "eta_hat", "gamma_hat", "x95_hat", "x95_true", "min_x",
             "rel_err", "rel_err_sq", "rel_b", "rel_e", "rel_g"]


def repair_one(fit: str, verify: bool = True) -> dict:
    csv_path = RUN.prediction_csv_path(fit)
    npz_path = RUN.evidence_npz_path(fit)
    if not os.path.isfile(csv_path):
        return {"fit": fit, "status": "no_csv"}
    df = pd.read_csv(csv_path)
    # 精确键（CSV 已保留 float64 分数键；n/repeat_id 为整数值）
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
    fits = [f[:-4] for f in sorted(os.listdir(CFG.PREDICTIONS_DIR)) if f.endswith(".csv")]
    # 只修复 v2 的 120 个 fit（P 与 Q 各自）
    repaired, missing = 0, 0
    for fit in fits:
        res = repair_one(fit, verify=verify)
        if res["status"] == "repaired":
            repaired += 1
        else:
            missing += 1
    print(f"repaired={repaired} missing_csv={missing} of {len(fits)}")
    print("EVIDENCE REPAIR DONE")


if __name__ == "__main__":
    main()
