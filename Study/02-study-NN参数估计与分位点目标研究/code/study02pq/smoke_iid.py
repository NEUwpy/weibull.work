"""Study/02 同分布主协议（iid-v1）生产路径 smoke（S1 前置；不产生正式证据）。

验证（生产路径，非单元测试）：
A. 完整 300 repeats 主表下 `run.write_splits_manifest`：每 (n,fold) 恰 180/60/60
   （train 7200 / val 2400 / test 2400），split_rule 为 repeat 规则，test 折互斥；
B. `run.run_fits_for_seeds` 经 run.py 生产路径训练（缩小设计）：
   - P/Q 配对（pairing_report all_match；init/batch/network/scaler/train/val/test SHA）；
   - 逐 fit 指标（n_test、converged、0 支撑违规/非有限/非法；split_strategy=repeat_stratified）；
   - 证据键精确 dtype（keys float64/int32、预测 float32）与 gamma_hat < min(X)；
   - scaler 只 fit train 行（spot 重算对比 params_sha）；
   - resumability（重跑全部 skipped）与 idempotence（--no-resume 重训后 evidence SHA 不变）；
   - `run.write_aggregates` → manifest / pairing / splits / SHA256SUMS 完整一致。

用法（iid 协议下运行；产物全部写入系统临时目录，绝不落入 artifacts/pq_iid_main）：
    PQ_PROTOCOL=iid-v1 python code/study02pq/smoke_iid.py
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from contextlib import redirect_stdout

import numpy as np

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))   # code/study02pq
sys.path.insert(0, STUDY02_CODE_DIR)
sys.path.insert(0, os.path.dirname(STUDY02_CODE_DIR))            # code/（study02pq 包根）

from study02pq import config as CFG  # noqa: E402
from study02pq import data as DATA  # noqa: E402
from study02pq import run as RUN  # noqa: E402
from study02pq import training as TR  # noqa: E402

assert CFG.PROTOCOL_VERSION == "iid-v1", "smoke_iid 必须在 PQ_PROTOCOL=iid-v1 下运行"


def _redirect_artifacts():
    """把全部产物路径改到系统临时目录，正式 pq_iid_main 绝不写入。"""
    root = tempfile.mkdtemp(prefix="pq_iid_smoke_")
    CFG.ARTIFACT_DIR = root
    CFG.PREDICTIONS_DIR = os.path.join(root, "predictions")
    CFG.CHECKPOINTS_DIR = os.path.join(root, "fit_metadata")
    CFG.EVIDENCE_DIR = os.path.join(root, "evidence")
    CFG.SPLITS_MANIFEST_PATH = os.path.join(root, "splits_manifest.json")
    print(f"[smoke] smoke artifacts -> {root}")
    return root


def part_a_full_scale_splits():
    """A. 完整 300 repeats：splits manifest 每 (n,fold) 恰 180/60/60。"""
    print("[smoke] A: full-scale split manifest (48,000 samples, 300 repeats)...", flush=True)
    master = DATA.build_master()
    DATA.verify_integrity(master)
    rec = RUN.write_splits_manifest(master)
    assert rec["split_strategy"] == "repeat_stratified"
    assert "repeat_id % 5" in rec["split_rule"]
    assert rec["validation"]["type"] is not None
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            f = rec["folds"][f"n{n}_f{fold_idx + 1}"]
            assert (f["n_train"], f["n_val"], f["n_test"]) == (7200, 2400, 2400), (n, fold_idx, f)
            assert f["test_sample_bytes_sha"]
    # test 折互斥且覆盖该 n 全部 repeat（用 n=7 抽查完整 300 行）
    n = 7
    n_mask = master.keys[:, 2].astype(np.int64) == n
    seen = set()
    for fold_idx in range(CFG.N_FOLDS):
        tr, va, te = DATA.split_repeat_fold(master, n, fold_idx)
        assert len(te) == 2400 and len(va) == 2400 and len(tr) == 7200
        assert not (set(te) & seen), f"repeat tested twice at fold {fold_idx}"
        seen |= set(te.tolist())
    assert len(seen) == 12000 and seen == set(np.flatnonzero(n_mask).tolist())
    print("[smoke] A PASS: 180/60/60 exact per (n,fold); test folds disjoint+cover")


def _small_master():
    # 缩小设计：beta x 5 gamma x n{7,10} x 15 repeats（15=5 的倍数 → 每 fold 每组合 9/3/3）
    return DATA.build_master(beta_grid=[2.0, 3.0], gamma_grid=CFG.GAMMA_GRID,
                             n_grid=[7, 10], repeats=15)


def _all_fits():
    return [TR.fit_id(n, fold_idx, 42, route)
            for n in CFG.N_GRID for fold_idx in range(CFG.N_FOLDS)
            for route in CFG.ROUTES]


def part_b_production_training():
    """B. 生产路径训练 + 配对/指标/证据/可续接/幂等。"""
    print("[smoke] B: production training path (small design, seeds=[42])...", flush=True)
    # 缩小训练预算，smoke 加速
    CFG.MAX_EPOCHS = 6
    CFG.PATIENCE = 3
    CFG.N_GRID = [7, 10]
    CFG.REPEATS = 15

    # smoke 用缩小设计（300 样本），verify_integrity 的全 48,000 规模断言不适用；
    # 以轻量自检代替（完整规模校验由 Part A 的 DATA.verify_integrity 覆盖）。
    def _light_verify(master):
        assert len(master.keys) > 0
        return {"n_samples": int(len(master.keys)), "n_combos": -1, "repeats_ok": True}

    RUN.DATA.verify_integrity = _light_verify

    master = _small_master()

    RUN.run_fits_for_seeds([42], master, resume=True)
    fits = _all_fits()
    assert len(fits) == len(CFG.N_GRID) * CFG.N_FOLDS * 1 * len(CFG.ROUTES)  # 2n x 5fold x 1seed x 2route
    assert all(RUN.fit_complete(f) for f in fits), "some fits incomplete"

    # ---- 配对报告：all_match ----
    pr = RUN.pairing_report([42], master)
    assert len(pr) == 2 * CFG.N_FOLDS  # 2n x 5fold
    assert bool(pr["all_match"].all()), "pairing mismatch"
    print(f"[smoke] B1 PASS: P/Q pairing all_match ({len(pr)} pairs)")

    # ---- 逐 fit 指标 ----
    pm = RUN.per_fit_metrics([42])
    assert len(pm) == len(fits)
    assert set(pm["split_strategy"]) == {"repeat_stratified"}
    assert (pm["n_test"] == 30).all(), pm["n_test"].unique()   # 10 combos x 3 repeats
    assert (pm["converged"] == True).all()  # noqa: E712
    assert (pm["n_support_viol"] == 0).all()
    assert (pm["n_nonfinite"] == 0).all()
    assert (pm["n_illegal"] == 0).all()
    print("[smoke] B2 PASS: per-fit metrics (n_test=30, 0 support/nonfinite/illegal)")

    # ---- 证据键 dtype + 支撑合法性 + scaler train-only spot 检查 ----
    fit = fits[0]
    ep = RUN.load_evidence(fit)
    assert ep["keys_beta"].dtype == np.float64
    assert ep["keys_gamma_over_eta"].dtype == np.float64
    assert ep["keys_n"].dtype == np.int32
    assert ep["keys_repeat_id"].dtype == np.int32
    for k in ("beta_hat", "eta_hat", "gamma_hat", "x95_hat", "x95_true", "min_x",
              "rel_err", "rel_err_sq"):
        assert ep[k].dtype == np.float32, (k, ep[k].dtype)
    assert np.all(ep["gamma_hat"] < ep["min_x"])           # 结构性支撑合法
    assert np.all(np.isfinite(ep["x95_hat"]))
    meta = RUN.load_fit_meta(fit)
    n, fold_idx, seed = meta["n"], meta["fold"] - 1, meta["seed"]
    tr, va, te = DATA.split_repeat_fold(master, n, fold_idx)
    X_tr, _, _ = DATA.make_arrays(master, tr)
    scaler = DATA.PerPositionScaler().fit(X_tr)             # 只 fit train 行
    assert scaler.params_sha() == meta["scaler_sha"], "scaler must fit train rows only"
    print(f"[smoke] B3 PASS: evidence dtypes, support legality, scaler train-only ({fit})")

    # ---- resumability：重跑全部 skipped ----
    buf = io.StringIO()
    with redirect_stdout(buf):
        RUN.run_fits_for_seeds([42], master, resume=True)
    out = buf.getvalue()
    assert "done=0" in out and f"skipped={len(fits)}" in out, out
    print(f"[smoke] B4 PASS: resumability (re-run -> done=0 skipped={len(fits)})")

    # ---- idempotence：--no-resume 重训后 evidence SHA 不变 ----
    sha_before = {f: RUN.load_fit_meta(f)["evidence_sha256"] for f in fits}
    RUN.run_fits_for_seeds([42], master, resume=False)
    sha_after = {f: RUN.load_fit_meta(f)["evidence_sha256"] for f in fits}
    assert sha_after == sha_before, "evidence not deterministic across retrain"
    print("[smoke] B5 PASS: idempotence (retrain -> evidence SHA identical)")

    # ---- write_aggregates → manifest / SHA256SUMS 完整一致 ----
    manifest = RUN.write_aggregates([42], master, run_label="smoke_iid")
    assert manifest["run_code_sha"] == RUN.RUN_CODE_SHA
    assert manifest["git_full_sha"] == RUN._git_full_head()
    assert manifest["n_fits_expected"] == len(fits)
    assert "summary_iid.json" in manifest["output_files"][4]
    # SHA256SUMS 自检：每行哈希与文件规范哈希一致
    # 行数 = 汇总（per_fit_metrics/pairing/splits/manifest 4 项；无 run_all_seeds.log）
    #         + fit_metadata（len） + evidence（len）；分析目录此时未生成
    sums_path = os.path.join(CFG.ARTIFACT_DIR, "SHA256SUMS")
    with open(sums_path, encoding="utf-8") as f:
        lines = [l for l in f.read().splitlines() if l.strip()]
    assert len(lines) >= 4 + 2 * len(fits), len(lines)
    for line in lines:
        h, rel = line.split("  ", 1)
        assert RUN.sha256_file_canonical(os.path.join(CFG.ARTIFACT_DIR, rel)) == h, rel
    print("[smoke] B6 PASS: write_aggregates manifest + SHA256SUMS self-consistent")


def main():
    print("[smoke] === iid-v1 production smoke (S1 preflight) ===", flush=True)
    _redirect_artifacts()
    part_a_full_scale_splits()
    part_b_production_training()
    print("[smoke] SMOKE PASS (iid-v1)")


if __name__ == "__main__":
    main()
