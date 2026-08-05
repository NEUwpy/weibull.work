"""Study/02 P-Q 单元 + 配对测试。

覆盖：样本契约确定性、参数合法化、x0.95 公式、Q 梯度经 Weibull 公式传播、
折切分、scaler 仅训练折、P/Q 严格配对、评价一致性。
"""

from __future__ import annotations

import hashlib
import os
import sys

import numpy as np
import pytest
import torch

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

from study02pq import config as CFG  # noqa: E402
from study02pq import data as DATA  # noqa: E402
from study02pq import evaluate as EVAL  # noqa: E402
from study02pq import losses as LOSS  # noqa: E402
from study02pq import model as MODEL  # noqa: E402
from study02pq import training as TR  # noqa: E402


def _small_master():
    return DATA.build_master(beta_grid=[2.0, 3.0], gamma_grid=CFG.GAMMA_GRID,
                             n_grid=[7, 10], repeats=6)


# ----------------------------------------------------------------------
# 样本契约
# ----------------------------------------------------------------------

def test_generate_sample_deterministic():
    from studies.common.sample import generate_sample
    s1 = generate_sample(2.0, 1000.0, 500.0, 10, 0, seed="study01_nrmc_v1")
    s2 = generate_sample(2.0, 1000.0, 500.0, 10, 0, seed="study01_nrmc_v1")
    assert np.array_equal(s1, s2)
    assert np.all(np.diff(np.sort(s1)) >= 0)
    # 与冻结的已知值一致（n=10, beta=2, gamma=500, repeat 0）
    assert np.isclose(s1[0], 517.7607, atol=1e-3)


def test_master_integrity():
    master = _small_master()
    assert len(master.keys) == 2 * 5 * 2 * 6
    for k in master.keys:
        n = int(k[2])
        i = master.idx_of(float(k[0]), float(k[1]), n, int(k[3]))
        assert len(master.X[i]) == n


# ----------------------------------------------------------------------
# 参数合法化与 x0.95 公式
# ----------------------------------------------------------------------

def test_decode_params_legal():
    min_x = torch.tensor([500.0, 1200.0], dtype=torch.float64)
    o = torch.tensor([[-10.0, -10.0, -5.0], [1.0, 7.0, 0.0]], dtype=torch.float64)
    b, e, g = LOSS.decode_params(o, min_x)
    assert torch.all(b > 0) and torch.all(e > 0)
    assert torch.all(torch.isfinite(g))
    # 支撑合法性：gamma_hat < min(X) 必须结构性成立
    assert torch.all(g < min_x)


def test_support_legality_gamma_lt_min_across_outputs():
    """任意 o1/o2/o3（含极大/极小）下 gamma_hat < min(X) 都成立。"""
    min_x = torch.tensor([517.0, 900.0, 300.0, 1500.0], dtype=torch.float64)
    o = torch.tensor([[-20.0, -20.0, 20.0],
                      [20.0, 20.0, -20.0],
                      [0.0, 0.0, 0.0],
                      [5.0, 12.0, 3.0]], dtype=torch.float64)
    b, e, g = LOSS.decode_params(o, min_x)
    assert torch.all(g < min_x), f"support violated: {g} >= {min_x}"


def test_weibull_quantile_known_value():
    # x0.95 for (beta=2, eta=1000, gamma=500) = 726.4802...
    b = torch.tensor([2.0]); e = torch.tensor([1000.0]); g = torch.tensor([500.0])
    x = LOSS.weibull_quantile(b, e, g)
    assert np.isclose(float(x[0]), 726.4802295732468, atol=1e-9)


def test_q_loss_gradient_flows_to_all_three_outputs():
    """Q 梯度必须真实经过 Weibull 公式到达三个原始输出（协议 §1.3）。"""
    min_x = torch.tensor([517.0], dtype=torch.float64)
    o = torch.tensor([[1.0, 7.0, -2.0]], dtype=torch.float64, requires_grad=True)
    x95 = torch.tensor([726.48], dtype=torch.float64)
    b, e, g = LOSS.decode_params(o, min_x)
    x_hat = LOSS.weibull_quantile(b, e, g)
    loss = LOSS.loss_q(x_hat, x95)
    loss.backward()
    grad = o.grad
    assert grad is not None
    # 三个原始输出梯度都必须非零（β、η、γ 都参与 x0.95）
    assert np.all(np.abs(grad.numpy()[0]) > 0), f"zero grad: {grad.numpy()}"


def test_p_loss_form():
    b = torch.tensor([2.1, 3.0]); e = torch.tensor([1050.0, 1000.0])
    g = torch.tensor([500.0, 1000.0])
    tb = torch.tensor([2.0, 3.0]); te = torch.tensor([1000.0, 1000.0])
    tg = torch.tensor([500.0, 1000.0])
    min_x = torch.tensor([510.0, 1005.0])  # 必须 > gamma
    lp = LOSS.loss_p(b, e, g, tb, te, tg, min_x)
    assert torch.isfinite(lp)


# ----------------------------------------------------------------------
# 折切分
# ----------------------------------------------------------------------

def test_fold_split_counts_and_disjoint():
    master = DATA.build_master(beta_grid=CFG.BETA_GRID, gamma_grid=CFG.GAMMA_GRID,
                               n_grid=CFG.N_GRID, repeats=10)
    for n in CFG.N_GRID:
        for fold in range(CFG.N_FOLDS):
            tr, va, te = DATA.split_fold(master, n, fold)
            assert len(te) == 8 * 10  # 1 goe x 8 beta x repeats
            assert len(tr) + len(va) == 8 * 4 * 10
            assert len(va) == int(round(len(tr) + len(va)) * CFG.VAL_FRACTION)
            assert not (set(tr.tolist()) & set(te.tolist()))
            assert not (set(va.tolist()) & set(te.tolist()))
            assert not (set(tr.tolist()) & set(va.tolist()))


def test_split_cover_all_combos():
    master = DATA.build_master(beta_grid=CFG.BETA_GRID, gamma_grid=CFG.GAMMA_GRID,
                               n_grid=CFG.N_GRID, repeats=5)
    for n in CFG.N_GRID:
        all_test = set()
        for fold in range(CFG.N_FOLDS):
            _, _, te = DATA.split_fold(master, n, fold)
            for r in te:
                k = (master.keys[r][0], master.keys[r][1])
                all_test.add(k)
        # 所有 goe x beta 组合都作为某折测试
        assert len(all_test) == 8 * 5


def test_fold_matches_study01_sealed_split():
    """对照 Study01 split_report.csv：每 (n, fold) 的测试 goe 水平。"""
    master = DATA.build_master(beta_grid=[1.5], gamma_grid=CFG.GAMMA_GRID,
                               n_grid=CFG.N_GRID, repeats=2)
    # 从 sealed split_report.csv 提取 (fold, goe, n)
    report = os.path.join(CFG.study01_abs_path(CFG.STUDY01_ALIGN["split_report_path"]))
    import pandas as pd
    df = pd.read_csv(report)
    sub = df[df["test_beta"] == 1.5]
    expected = {}
    for _, row in sub.iterrows():
        expected.setdefault(int(row["test_n"]), {})[row["fold"]] = row["test_gamma_over_eta"]
    for n in CFG.N_GRID:
        for fold in range(CFG.N_FOLDS):
            _, _, te = DATA.split_fold(master, n, fold)
            goe_set = {master.keys[r][1] for r in te}
            assert len(goe_set) == 1
            goe = goe_set.pop()
            assert np.isclose(goe, expected[n][f"combo_fold_{fold + 1}"]), \
                (n, fold, goe, expected[n][f"combo_fold_{fold + 1}"])


# ----------------------------------------------------------------------
# scaler 仅训练折
# ----------------------------------------------------------------------

def test_scaler_train_only():
    master = DATA.build_master(beta_grid=[2.0], gamma_grid=CFG.GAMMA_GRID,
                               n_grid=[7], repeats=20)
    tr, va, te = DATA.split_fold(master, 7, 0)
    X_tr, _, _ = DATA.make_arrays(master, tr)
    X_te, _, _ = DATA.make_arrays(master, te)
    scaler = DATA.PerPositionScaler().fit(X_tr)
    # 手动校验：mean/std 来自训练折
    assert np.allclose(scaler.mean_, X_tr.mean(axis=0))
    assert np.allclose(scaler.scale_, X_tr.std(axis=0))
    # transform 后测试折不在原尺度
    X_te_s = scaler.transform(X_te)
    assert X_te_s.shape == X_te.shape


# ----------------------------------------------------------------------
# P/Q 严格配对
# ----------------------------------------------------------------------

def test_pq_pairing_identical_except_loss():
    master = _small_master()
    n, fold, seed = 7, 0, 42
    rp = TR.train_one_fit(n, fold, seed, "P", master, max_epochs=4, patience=2)
    rq = TR.train_one_fit(n, fold, seed, "Q", master, max_epochs=4, patience=2)
    for k in ["init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
              "train_rows_sha", "val_rows_sha", "test_rows_sha"]:
        assert rp["meta"][k] == rq["meta"][k], f"mismatch {k}"
    assert rp["meta"]["route"] == "P" and rq["meta"]["route"] == "Q"


def test_initial_params_equal_across_route():
    """P/Q 初始参数张量字节级一致。"""
    torch.manual_seed(42)
    m1 = MODEL.build_model(7, 42)
    m2 = MODEL.build_model(7, 42)
    p1 = torch.cat([p.detach().float().ravel() for p in m1.parameters()])
    p2 = torch.cat([p.detach().float().ravel() for p in m2.parameters()])
    assert torch.equal(p1, p2)
    assert MODEL.params_sha(m1) == MODEL.params_sha(m2)


def test_training_outputs_support_legal():
    """P/Q 正式拟合的 held-out 输出必须全部满足 gamma_hat < min(X)（production test）。"""
    master = _small_master()
    for route in ("P", "Q"):
        r = TR.train_one_fit(7, 0, 42, route, master, max_epochs=6, patience=2)
        p = r["predictions"]
        assert np.all(p["gamma_hat"] < p["min_x"] - 1e-9)
        assert r["meta"]["n_support_viol"] == 0
        assert r["meta"]["support_legality_ok"] is True


def test_deterministic_rerun_same_fit():
    master = _small_master()
    r1 = TR.train_one_fit(7, 0, 42, "P", master, max_epochs=5, patience=2)
    r2 = TR.train_one_fit(7, 0, 42, "P", master, max_epochs=5, patience=2)
    assert r1["meta"]["rrmse_x95"] == r2["meta"]["rrmse_x95"]
    assert np.array_equal(r1["predictions"]["x95_hat"], r2["predictions"]["x95_hat"])
    assert r1["meta"]["best_epoch"] == r2["meta"]["best_epoch"]


# ----------------------------------------------------------------------
# 评价
# ----------------------------------------------------------------------

def test_rrmse_matches_manual():
    rel = np.array([0.1, 0.2, 0.3])
    assert np.isclose(EVAL.rrmse(rel ** 2), np.sqrt(np.mean(rel ** 2)))


def test_bootstrap_ci_bounds():
    rng = np.random.default_rng(0)
    rel_p = np.abs(rng.normal(0, 0.1, 500))
    rel_q = rel_p * 1.2
    m = EVAL.secondary_within_cell_mc(rel_p ** 2, rel_q ** 2, n_boot=100, rng=rng)
    assert m["ci_lo"] <= m["mean"] <= m["ci_hi"]
    assert m["mean"] > 0  # Q 更差


def test_primary_design_bootstrap_bounds():
    """主推断：20 设计单元 × 3 seed，CI 应含 pooled 均值。"""
    rng = np.random.default_rng(1)
    diffs = {n: {f: list(rng.normal(0.0, 0.01, 3)) for f in range(1, 6)}
             for n in [7, 10, 15, 20]}
    m = EVAL.primary_design_bootstrap(diffs, n_boot=200, rng=rng)
    assert m["pooled_ci_lo"] <= m["pooled_mean"] <= m["pooled_ci_hi"]
    assert set(m["per_n_mean"].keys()) == {7, 10, 15, 20}
    for n in [7, 10, 15, 20]:
        assert m["per_n_ci_lo"][n] <= m["per_n_mean"][n] <= m["per_n_ci_hi"][n]


if __name__ == "__main__":
    import pytest as _pt
    raise SystemExit(_pt.main([__file__, "-v"]))
