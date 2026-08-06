"""Study/02 同分布主协议（S0 冻结候选）测试。

覆盖：
- 冻结配置 `configs/pq-iid-protocol-v1.json` 可被选择加载（PQ_PROTOCOL=iid-v1），
  默认仍为 v3（r4 gamma-holdout），两者产物命名空间互不串扰；
- 冻结配置规模数字与实现/蓝图自洽（120 fits、180/60/60、每模型 2400 held-out）；
- 完整 300 repeats 下 repeat-stratified 五折平衡：每 (n, fold) 每组合恰 180/60/60，
  每折覆盖全部组合，每个 repeat 恰在一次折中作为测试；
- iid 策略下 P/Q 仍逐 fit 配对（仅 loss route 不同）且支持域合法性成立。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import pytest

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

from study02pq import config as CFG  # noqa: E402
from study02pq import data as DATA  # noqa: E402
from study02pq import training as TR  # noqa: E402


# ----------------------------------------------------------------------
# 冻结配置选择
# ----------------------------------------------------------------------

def _load_config_in_subprocess(env_extra: dict) -> list[str]:
    env = {k: v for k, v in os.environ.items() if k != "PQ_PROTOCOL"}
    # 包根是 STUDY02_CODE_DIR 的父目录（code/）；子进程用 PYTHONPATH 显式给出
    env["PYTHONPATH"] = os.path.dirname(STUDY02_CODE_DIR)
    env.update(env_extra)
    code = ("from study02pq import config as C; "
            "print(C.PROTOCOL_VERSION); print(C.CONFIG_PATH); "
            "print(C.ARTIFACT_DIR); print(C.SPLIT_STRATEGY)")
    out = subprocess.check_output(
        [sys.executable, "-c", code], cwd=STUDY02_CODE_DIR, env=env, text=True)
    return out.strip().splitlines()


def test_default_protocol_is_v3():
    lines = _load_config_in_subprocess({})
    assert lines[0] == "v3"
    assert "pq-protocol-v3.json" in lines[1]
    assert "pq_v3" in lines[2]
    assert lines[3] == "gamma_holdout"


def test_iid_protocol_selectable_and_isolated():
    lines = _load_config_in_subprocess({"PQ_PROTOCOL": "iid-v1"})
    assert lines[0] == "iid-v1"
    assert "pq-iid-protocol-v1.json" in lines[1]
    assert "pq_iid_main" in lines[2]
    assert lines[3] == "repeat_stratified"


def test_iid_frozen_config_integrity():
    """冻结配置的规模数字必须与实现/蓝图自洽。"""
    path = os.path.join(CFG.STUDY02_ROOT, "configs", "pq-iid-protocol-v1.json")
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    d = cfg["design"]
    assert len(d["beta_grid"]) == 8 and len(d["gamma_grid"]) == 5
    assert d["n_combos"] == 8 * 5 * len(d["n_grid"]) == 160
    assert d["n_samples"] == 160 * d["repeats_per_combo"] == 48000
    s = cfg["split"]
    assert s["n_folds"] == 5
    assert s["train_repeats_per_combo"] == 180
    assert s["val_repeats_per_combo"] == s["test_repeats_per_combo"] == 60
    assert s["train_repeats_per_combo"] + s["val_repeats_per_combo"] + \
        s["test_repeats_per_combo"] == d["repeats_per_combo"]
    ex = cfg["execution"]
    assert ex["n_fits"] == len(d["n_grid"]) * s["n_folds"] * len(cfg["seeds"]) * \
        len(cfg["routes"]) == 120
    inf = cfg["inference"]
    assert inf["n_design_units"] == len(d["n_grid"]) * s["n_folds"] == 20
    assert inf["n_model_level_contrasts"] == 20 * len(cfg["seeds"]) == 60
    assert inf["held_out_per_model"] == s["test_repeats_per_combo"] * 40 == 2400
    assert cfg["split_strategy"] == "repeat_stratified"


# ----------------------------------------------------------------------
# repeat-stratified 拆分（完整 300 repeats 规模）
# ----------------------------------------------------------------------

def test_repeat_stratified_full_scale_balance():
    """单个 (beta, gamma, n) 组合 × 300 repeats：每 fold 恰 180/60/60，且互补。"""
    master = DATA.build_master(beta_grid=[2.0], gamma_grid=[500.0],
                               n_grid=[7], repeats=300)
    n = 7
    n_mask = master.keys[:, 2].astype(np.int64) == n
    all_test = set()
    for fold_idx in range(CFG.N_FOLDS):
        tr, va, te = DATA.split_repeat_fold(master, n, fold_idx)
        assert (len(tr), len(va), len(te)) == (180, 60, 60), (fold_idx, len(tr), len(va), len(te))
        assert not set(tr) & set(va)
        assert not set(tr) & set(te)
        assert not set(va) & set(te)
        assert len(tr) + len(va) + len(te) == 300
        # 每个 repeat 恰作为测试一次（跨 5 折 test 集合互斥且覆盖全部）
        assert not (set(te) & all_test), f"repeat tested in multiple folds at fold {fold_idx}"
        all_test |= set(te)
    assert len(all_test) == 300
    assert set(all_test) == set(np.flatnonzero(n_mask).tolist())


def test_repeat_stratified_every_split_has_all_combos():
    """每 (n, fold) 的 train/val/test 都覆盖该 n 的全部 40 个 (beta, gamma) 组合。"""
    master = DATA.build_master(beta_grid=CFG.BETA_GRID, gamma_grid=CFG.GAMMA_GRID,
                               n_grid=[7], repeats=10)
    n = 7
    n_combos = len(CFG.BETA_GRID) * len(CFG.GAMMA_GRID)
    for fold_idx in range(CFG.N_FOLDS):
        for rows in DATA.split_repeat_fold(master, n, fold_idx):
            combos = {(master.keys[r][0], master.keys[r][1]) for r in rows}
            assert len(combos) == n_combos


def test_repeat_stratified_scaler_train_only():
    """iid 策略下 scaler 只 fit 训练行（不碰 val/test）。"""
    master = DATA.build_master(beta_grid=[2.0], gamma_grid=CFG.GAMMA_GRID,
                               n_grid=[7], repeats=20)
    tr, va, te = DATA.split_repeat_fold(master, 7, 0)
    X_tr, _, _ = DATA.make_arrays(master, tr)
    scaler = DATA.PerPositionScaler().fit(X_tr)
    assert np.allclose(scaler.mean_, X_tr.mean(axis=0))
    assert np.allclose(scaler.scale_, X_tr.std(axis=0))


# ----------------------------------------------------------------------
# iid 策略下 P/Q 配对
# ----------------------------------------------------------------------

def test_pq_pairing_iid_strategy():
    """repeat-stratified 拆分下 P/Q 仍逐 fit 配对，仅 loss route 不同。"""
    master = DATA.build_master(beta_grid=[2.0, 3.0], gamma_grid=CFG.GAMMA_GRID,
                               n_grid=[7, 10], repeats=6)
    n, fold_idx, seed = 7, 0, 42
    rp = TR.train_one_fit(n, fold_idx, seed, "P", master,
                          max_epochs=4, patience=2, split_strategy="repeat_stratified")
    rq = TR.train_one_fit(n, fold_idx, seed, "Q", master,
                          max_epochs=4, patience=2, split_strategy="repeat_stratified")
    for k in ["init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
              "train_rows_sha", "val_rows_sha", "test_rows_sha"]:
        assert rp["meta"][k] == rq["meta"][k], f"mismatch {k}"
    assert rp["meta"]["route"] == "P" and rq["meta"]["route"] == "Q"
    assert rp["meta"]["split_strategy"] == "repeat_stratified"
    assert rq["meta"]["split_strategy"] == "repeat_stratified"
    assert rp["meta"]["support_legality_ok"] is True
    assert rq["meta"]["support_legality_ok"] is True
