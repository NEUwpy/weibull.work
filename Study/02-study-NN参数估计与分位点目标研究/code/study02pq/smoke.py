"""Study/02 P-Q production-path smoke（微型非证据数据）。

验证：确定性样本重建、折切分、P/Q 配对（初始参数/数据/batch/scaler SHA 一致）、
训练、held-out 评价、汇总。使用缩小设计，不产生正式证据。
"""

from __future__ import annotations

import os
import sys

import numpy as np

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

from study02pq import config as CFG  # noqa: E402
from study02pq import data as DATA  # noqa: E402
from study02pq import evaluate as EVAL  # noqa: E402
from study02pq import training as TR  # noqa: E402


def _smoke_design():
    # 保留完整 5 个 gamma/eta 水平以维持 Study01 折结构；缩小 beta/n/repeats
    return dict(beta_grid=[2.0, 3.0],
                gamma_grid=CFG.GAMMA_GRID,
                n_grid=[7, 10],
                repeats=8)


def run_smoke():
    d = _smoke_design()
    master = DATA.build_master(**d)
    n_combo = len(d["beta_grid"]) * len(d["gamma_grid"]) * len(d["n_grid"])
    n_samp = n_combo * d["repeats"]
    assert len(master.keys) == n_samp, (len(master.keys), n_samp)

    # 折切分：n=7, fold 0 → test = 1 goe x 2 beta x 8 = 16
    tr, va, te = DATA.split_fold(master, 7, 0)
    assert len(te) == len(d["beta_grid"]) * d["repeats"]  # 16
    assert len(tr) + len(va) == 4 * len(d["beta_grid"]) * d["repeats"]  # 64
    assert len(va) == int(round((len(tr) + len(va)) * 0.15))

    # P/Q 配对
    n, fold, seed = 7, 0, 42
    rp = TR.train_one_fit(n, fold, seed, "P", master, max_epochs=6, patience=3)
    rq = TR.train_one_fit(n, fold, seed, "Q", master, max_epochs=6, patience=3)
    mp, mq = rp["meta"], rq["meta"]
    for k in ["init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
              "train_rows_sha", "val_rows_sha", "test_rows_sha"]:
        assert mp[k] == mq[k], f"pairing mismatch {k}: {mp[k]} vs {mq[k]}"
    print("[smoke] P/Q pairing SHAs match")

    # 预测有限性与指标
    for res in (rp, rq):
        p = res["predictions"]
        assert np.all(np.isfinite(p["x95_hat"]))
        assert np.all(p["beta_hat"] > 0) and np.all(p["eta_hat"] > 0)
        rrmse = np.sqrt(np.mean(p["rel_err_sq"]))
        assert np.isclose(rrmse, res["meta"]["rrmse_x95"])
    print("[smoke] predictions finite; rrmse matches")

    # 配对 bootstrap CI
    rel_p = rp["predictions"]["rel_err_sq"]
    rel_q = rq["predictions"]["rel_err_sq"]
    m = EVAL.bootstrap_ci_paired(rel_p, rel_q, n_boot=50)
    assert m["ci_lo"] <= m["mean_diff"] <= m["ci_hi"]
    print("[smoke] paired bootstrap OK:", {k: round(v, 4) for k, v in m.items()
                                            if isinstance(v, float)})
    print(f"[smoke] P rRMSE={m['p_rrmse']:.4f}  Q rRMSE={m['q_rrmse']:.4f}")
    print("SMOKE PASS")


if __name__ == "__main__":
    run_smoke()
