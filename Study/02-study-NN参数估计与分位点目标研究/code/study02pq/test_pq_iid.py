"""Study/02 同分布主协议（S0 冻结候选）测试。

覆盖：
- 冻结配置 `configs/pq-iid-protocol-v1.json` 可被选择加载（PQ_PROTOCOL=iid-v1），
  默认仍为 v3（r4 gamma-holdout），两者产物命名空间互不串扰；
- **未知 PQ_PROTOCOL 必须显式失败**（R1 S0-004），绝不静默回落到 v3；
- 冻结配置规模数字与实现/蓝图自洽（120 fits、180/60/60、每模型 2400 held-out）；
- x_p 显式定义为可靠度寿命点 R(x_p)=p（R1 S0-001），公式锁定 -ln(0.95)；
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

_PROTOCOL_CODE = ("from study02pq import config as C; "
                  "print(C.PROTOCOL_VERSION); print(C.CONFIG_PATH); "
                  "print(C.ARTIFACT_DIR); print(C.SPLIT_STRATEGY)")


def _subprocess_env(env_extra: dict) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "PQ_PROTOCOL"}
    # 包根是 STUDY02_CODE_DIR 的父目录（code/）；子进程用 PYTHONPATH 显式给出
    env["PYTHONPATH"] = os.path.dirname(STUDY02_CODE_DIR)
    env.update(env_extra)
    return env


def _load_config_in_subprocess(env_extra: dict) -> list[str]:
    out = subprocess.check_output(
        [sys.executable, "-c", _PROTOCOL_CODE], cwd=STUDY02_CODE_DIR,
        env=_subprocess_env(env_extra), text=True)
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


@pytest.mark.parametrize("bad", ["iid", "IID", "v4", "r4", "", " iid-v1 x", "v3.1"])
def test_unknown_protocol_rejected(bad):
    """任何未知 PQ_PROTOCOL 必须显式失败，绝不静默回落（R1 S0-004）。"""
    proc = subprocess.run(
        [sys.executable, "-c", _PROTOCOL_CODE], cwd=STUDY02_CODE_DIR,
        env=_subprocess_env({"PQ_PROTOCOL": bad}), text=True, capture_output=True)
    assert proc.returncode != 0, f"expected failure for {bad!r}, got rc=0"
    assert "PQ_PROTOCOL" in (proc.stderr + proc.stdout)


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
    # R1 S0-001：x_p 显式定义为可靠度寿命点（R(x_p)=p），不是 CDF p-分位点；公式锁定 -ln p。
    xp = cfg["x_p_definition"]
    assert xp["p_value"] == 0.95
    assert "reliability" in xp["meaning"].lower() and "CDF" in xp["meaning"]
    assert "-ln p" in xp["formula"].replace("(−", "(-") and "1/beta" in xp["formula"]
    assert xp["m3_levels"] == [0.90, 0.95, 0.99]


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


# ----------------------------------------------------------------------
# run.py 接入 iid（S1）：split_strategy 传递与 splits manifest 分派（不启动训练）
# ----------------------------------------------------------------------

def test_run_forwards_split_strategy_v3(monkeypatch):
    """run.run_fits_for_seeds 必须把 CFG.SPLIT_STRATEGY 传给 train_one_fit（v3 默认回归安全）。"""
    import study02pq.run as RUN
    seen = []

    def fake_train(n, fold_idx, seed, route, master, **kw):
        seen.append(kw.get("split_strategy"))
        raise SystemExit  # 只验证传递，不真的训练

    monkeypatch.setattr(RUN, "ensure_dirs", lambda: None)
    monkeypatch.setattr(RUN.TR, "train_one_fit", fake_train)
    master = DATA.build_master(beta_grid=[2.0], gamma_grid=[500.0],
                               n_grid=[7], repeats=5)
    with pytest.raises(SystemExit):
        RUN.run_fits_for_seeds([42], master, resume=False)
    assert seen == ["gamma_holdout"]


def test_iid_run_forwards_split_strategy_subprocess():
    """iid 模式：run_fits_for_seeds 传递 split_strategy=repeat_stratified（subprocess 隔离）。"""
    code = (
        "import sys, os\n"
        "sys.path.insert(0, os.getcwd())\n"
        "from study02pq import run as RUN, data as DATA, config as CFG\n"
        "seen = []\n"
        "def fake(n, fold_idx, seed, route, master, **kw):\n"
        "    seen.append(kw.get('split_strategy'))\n"
        "    raise SystemExit\n"
        "RUN.ensure_dirs = lambda: None\n"
        "RUN.TR.train_one_fit = fake\n"
        "m = DATA.build_master(beta_grid=[2.0], gamma_grid=[500.0], "
        "n_grid=[7], repeats=5)\n"
        "try:\n"
        "    RUN.run_fits_for_seeds([42], m, resume=False)\n"
        "except SystemExit:\n"
        "    pass\n"
        "print(CFG.SPLIT_STRATEGY)\n"
        "print(seen[0])\n"
    )
    out = subprocess.check_output(
        [sys.executable, "-c", code], cwd=STUDY02_CODE_DIR,
        env=_subprocess_env({"PQ_PROTOCOL": "iid-v1"}), text=True)
    lines = out.strip().splitlines()
    # 末尾两行 = CFG.SPLIT_STRATEGY 与 fake 收到的 split_strategy（前面是训练进度行）
    assert lines[-2:] == ["repeat_stratified", "repeat_stratified"], lines


def test_write_splits_manifest_repeat_stratified(tmp_path):
    """iid 模式：splits manifest 用 split_repeat_fold + repeat 规则（subprocess 隔离）。"""
    code = (
        "import sys, os, json; "
        "sys.path.insert(0, os.getcwd()); "
        "from study02pq import run as RUN, data as DATA, config as CFG; "
        "CFG.SPLITS_MANIFEST_PATH = %r; "
        "CFG.N_GRID = [7]; "
        "m = DATA.build_master(beta_grid=CFG.BETA_GRID, gamma_grid=CFG.GAMMA_GRID, "
        "n_grid=[7], repeats=10); "
        "rec = RUN.write_splits_manifest(m); "
        "print(json.dumps(rec, ensure_ascii=False))" % (str(tmp_path / "s.json"))
    )
    out = subprocess.check_output(
        [sys.executable, "-c", code], cwd=STUDY02_CODE_DIR,
        env=_subprocess_env({"PQ_PROTOCOL": "iid-v1"}), text=True)
    rec = json.loads(out.strip())
    assert rec["split_strategy"] == "repeat_stratified"
    assert "repeat_id % 5" in rec["split_rule"]
    assert rec["validation"]["type"] is not None
    f = rec["folds"]["n7_f1"]
    # repeats=10 → 每组合 test 2、val 2、train 6；40 组合 → 80/80/240
    assert (f["n_train"], f["n_val"], f["n_test"]) == (240, 80, 80), f
    assert f["n_train"] + f["n_val"] + f["n_test"] == 400
    assert f["test_sample_bytes_sha"]


def test_write_splits_manifest_gamma_holdout(monkeypatch, tmp_path):
    """v3 默认：splits manifest 仍用 split_fold + combo 规则（回归安全）。"""
    import study02pq.run as RUN
    monkeypatch.setattr(CFG, "SPLITS_MANIFEST_PATH", str(tmp_path / "s.json"))
    monkeypatch.setattr(CFG, "N_GRID", [7])
    master = DATA.build_master(beta_grid=CFG.BETA_GRID, gamma_grid=CFG.GAMMA_GRID,
                               n_grid=[7], repeats=6)
    rec = RUN.write_splits_manifest(master)
    assert rec["split_strategy"] == "gamma_holdout"
    assert "combo_idx % 5" in rec["split_rule"]
    f = rec["folds"]["n7_f1"]
    # split_fold：test = 1 goe 水平 x 8 beta x 6 = 48；train+val = 4 goe x 8 beta x 6 = 192
    assert f["n_test"] == 48
    assert f["n_train"] + f["n_val"] == 192


def _meta_base(fit_id, n, fold, seed, route):
    return {
        "fit_id": fit_id, "n": n, "fold": fold, "seed": seed, "route": route,
        "converged": True, "nan_flag": False, "best_epoch": 1, "stopped_epoch": 2,
        "best_val_loss": 0.1, "last_train_loss": 0.2, "rrmse_x95": 0.3,
        "n_test": 2400, "n_nonfinite": 0, "n_illegal": 0, "n_support_viol": 0,
        "support_legality_ok": True, "sample_bytes_sha": "a", "evidence_sha256": "b",
        "runtime_s": 1.0, "init_param_sha": "i", "batch_order_sha": "bo",
        "network_sha": "n", "scaler_sha": "s", "train_rows_sha": "tr",
        "val_rows_sha": "va", "test_rows_sha": "te",
    }


def test_per_fit_metrics_split_strategy_column(monkeypatch, tmp_path):
    """iid 正式运行元数据含 split_strategy 时，per_fit_metrics 输出该列。"""
    import study02pq.run as RUN
    ckpt = tmp_path / "meta"
    ckpt.mkdir()
    for route in ("P", "Q"):
        fit = TR.fit_id(7, 0, 42, route)
        m = _meta_base(fit, 7, 1, 42, route)
        m["split_strategy"] = "repeat_stratified"
        (ckpt / f"{fit}.json").write_text(json.dumps(m), encoding="utf-8")
    monkeypatch.setattr(CFG, "CHECKPOINTS_DIR", str(ckpt))
    monkeypatch.setattr(CFG, "N_GRID", [7])
    monkeypatch.setattr(CFG, "N_FOLDS", 1)
    df = RUN.per_fit_metrics([42])
    assert "split_strategy" in df.columns
    assert set(df["split_strategy"]) == {"repeat_stratified"}
    assert len(df) == 2


def test_per_fit_metrics_old_meta_without_split_strategy(monkeypatch, tmp_path):
    """r4/v3 旧元数据（无 split_strategy 键）不破坏 v3 聚合（回归安全）。"""
    import study02pq.run as RUN
    ckpt = tmp_path / "meta"
    ckpt.mkdir()
    for route in ("P", "Q"):
        fit = TR.fit_id(7, 0, 42, route)
        (ckpt / f"{fit}.json").write_text(
            json.dumps(_meta_base(fit, 7, 1, 42, route)), encoding="utf-8")
    monkeypatch.setattr(CFG, "CHECKPOINTS_DIR", str(ckpt))
    monkeypatch.setattr(CFG, "N_GRID", [7])
    monkeypatch.setattr(CFG, "N_FOLDS", 1)
    df = RUN.per_fit_metrics([42])
    assert "split_strategy" not in df.columns
    assert len(df) == 2
