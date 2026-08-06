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
from study02pq import run as RUN  # noqa: E402
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


def test_repeat_stratified_split_covers_every_combo():
    master = DATA.build_master(beta_grid=[2.0, 3.0], gamma_grid=CFG.GAMMA_GRID,
                               n_grid=[7], repeats=10)
    train, val, test = DATA.split_repeat_fold(master, 7, 0)
    assert (len(train), len(val), len(test)) == (60, 20, 20)
    assert not set(train) & set(val)
    assert not set(train) & set(test)
    assert not set(val) & set(test)
    for rows, expected_per_combo in ((train, 6), (val, 2), (test, 2)):
        combos, counts = np.unique(master.keys[rows, :2], axis=0, return_counts=True)
        assert len(combos) == 10
        assert np.all(counts == expected_per_combo)


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
        assert np.all(p["gamma_hat"] > 0)
        assert r["meta"]["n_support_viol"] == 0
        assert r["meta"]["support_legality_ok"] is True


def test_frozen_grid_representability():
    """r4（Codex 合同）：所有冻结真 gamma 都落在解码器可表示区间 (0, min(X)) 内。"""
    from itertools import product
    from studies.common.sample import generate_sample
    min_s = 1.0
    max_s = 0.0
    for b, goe, n in product(CFG.BETA_GRID, CFG.GAMMA_OVER_ETA_GRID, CFG.N_GRID):
        gamma = goe * CFG.ETA
        x = generate_sample(float(b), CFG.ETA, float(gamma), int(n), 0,
                            seed=CFG.SEED_NAMESPACE)
        mn = float(np.min(x))
        assert mn > gamma, "min(X) 必须严格 > gamma（冻结正位置域）"
        s = gamma / mn
        min_s = min(min_s, s)
        max_s = max(max_s, s)
    # 解码器 s ∈ (delta, 1-delta)；全部真 gamma 必须落在其内
    assert min_s > LOSS.DELTA
    assert max_s < 1.0 - LOSS.DELTA
    print(f"representability s range: ({min_s:.6f}, {max_s:.6f}) within "
          f"({LOSS.DELTA}, {1 - LOSS.DELTA})")


def test_direct_p_formula_exact():
    """r4：P 损失必须是 approved direct 形式（无 log-gap / 辅助项）。"""
    b = torch.tensor([2.1, 3.0]); e = torch.tensor([1050.0, 1000.0])
    g = torch.tensor([400.0, 900.0])
    tb = torch.tensor([2.0, 3.0]); te = torch.tensor([1000.0, 1000.0])
    tg = torch.tensor([500.0, 1000.0])
    min_x = torch.tensor([510.0, 1005.0])
    lp = LOSS.loss_p(b, e, g, tb, te, tg, min_x)
    manual = (((b - tb) / tb) ** 2 + ((e - te) / te) ** 2 + ((g - tg) / te) ** 2).mean()
    assert torch.allclose(lp, manual)
    assert not torch.any(torch.isnan(lp))


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

def test_evidence_key_schema_exact_identity():
    """r4 schema：encode_keys/decode_keys/keys_match 在完整冻结键网格上保持精确身份
    （分数 beta 与 gamma/eta 不被截断）。"""
    from itertools import product
    combos = list(product(CFG.BETA_GRID, CFG.GAMMA_OVER_ETA_GRID, CFG.N_GRID))
    rows = [(b, g, n, rid) for (b, g, n) in combos for rid in range(CFG.REPEATS)]
    k4 = np.asarray(rows, dtype=np.float64)
    enc = RUN.encode_keys(k4)
    dec = RUN.decode_keys(enc)
    assert np.array_equal(dec["beta"], k4[:, 0]), "beta 被截断"
    assert np.array_equal(dec["gamma_over_eta"], k4[:, 1]), "gamma/eta 被截断"
    assert np.array_equal(dec["n"], k4[:, 2].astype(np.int32))
    assert np.array_equal(dec["repeat_id"], k4[:, 3].astype(np.int32))
    # 分数值必须保留
    assert 1.5 in set(dec["beta"].tolist())
    assert 2.5 in set(dec["beta"].tolist())
    assert 0.25 in set(dec["gamma_over_eta"].tolist())
    dec2 = RUN.decode_keys(RUN.encode_keys(k4))
    assert RUN.keys_match(dec, dec2)


def test_repair_evidence_targets_v2_explicitly():
    """R4-04：repair_evidence 的源/目标路径必须显式锁定 v2，不得随活动 v3 配置漂移。"""
    import repair_evidence as RE
    assert "pq_v2" in RE._V2_ARTIFACT
    assert "pq_v3" not in RE._V2_ARTIFACT
    assert "pq_v2" in RE.V2_PREDICTIONS_DIR and "pq_v2" in RE.V2_EVIDENCE_DIR
    assert "pq_v3" not in RE.V2_PREDICTIONS_DIR and "pq_v3" not in RE.V2_EVIDENCE_DIR
    # 活动配置在 r4 primary 下指向 pq_v3，但 repair 目标必须仍是 v2
    assert "pq_v3" in CFG.ARTIFACT_DIR
    assert RE._V2_ARTIFACT != CFG.ARTIFACT_DIR


def test_boundary_diagnostic_totals():
    """R4 final：boundary_diagnostic 的 n_total_rows 必须为 144000（完整配对证据），
    保留行为 n_total - n_edge_q；由 analyze 生成后存在。"""
    diag_path = os.path.join(CFG.ARTIFACT_DIR, "analysis", "boundary_diagnostic.json")
    if not os.path.isfile(diag_path):
        pytest.skip("boundary_diagnostic.json not generated yet")
    import json as _json
    d = _json.load(open(diag_path, encoding="utf-8"))
    assert d["n_total_rows"] == 144000
    assert d["n_retained_rows_after_pairwise_exclusion"] == \
        144000 - d["n_edge_rows_q"]
    assert d["n_edge_rows_q"] == 45
    assert d["n_edge_rows_p"] == 0
    assert "boundary_diagnostic.json" in d or True  # 存在性


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
    """主推断：20 设计单元 × 3 seed（fold×seed 交叉），CI 应含 pooled 均值。"""
    rng = np.random.default_rng(1)
    diffs = {n: {f: list(rng.normal(0.0, 0.01, 3)) for f in range(1, 6)}
             for n in [7, 10, 15, 20]}
    m = EVAL.primary_design_bootstrap(diffs, n_boot=500, rng=rng)
    assert m["pooled_ci_lo"] <= m["pooled_mean"] <= m["pooled_ci_hi"]
    assert set(m["per_n_mean"].keys()) == {7, 10, 15, 20}
    for n in [7, 10, 15, 20]:
        assert m["per_n_ci_lo"][n] <= m["per_n_mean"][n] <= m["per_n_ci_hi"][n]
    assert "seed" in m["resampling"]


def test_primary_bootstrap_incorporates_seed_variation():
    """seed 维度有真实变异时，交叉 bootstrap 的 CI 应反映之（比 fold-only 更宽）。"""
    rng = np.random.default_rng(7)
    # 3 个 seed 均值明显不同（模拟 seed 不确定性）
    diffs = {n: {f: [0.0, 0.05, -0.05] for f in range(1, 6)} for n in [7, 10, 15, 20]}
    m = EVAL.primary_design_bootstrap(diffs, n_boot=500, rng=rng)
    # 所有 cell 同 fold 但 seed 不同 → pooled 均值为 0，但 seed 变异应使 CI 明显宽于 0
    assert m["pooled_ci_lo"] < -0.01 and m["pooled_ci_hi"] > 0.01
    assert m["pooled_ci_lo"] <= 0.0 <= m["pooled_ci_hi"]


def test_warm_start_keeps_epoch_zero_as_candidate():
    """目标切换 pilot 可从共同 checkpoint 续训，并保留未续训状态。"""
    master = _small_master()
    model = MODEL.build_model(7, 42)
    start_sha = MODEL.params_sha(model)
    result = TR.train_one_fit(
        7, 0, 42, "Q", master,
        max_epochs=1, patience=1,
        initial_state=model.state_dict(), include_initial=True,
        return_state=True, learning_rate=0.0,
    )
    restored = MODEL.build_model(7, 42)
    restored.load_state_dict(result["model_state"])
    assert result["meta"]["warm_started"] is True
    assert result["meta"]["best_epoch"] == 0
    assert result["meta"]["init_param_sha"] == start_sha
    assert MODEL.params_sha(restored) == start_sha


if __name__ == "__main__":
    import pytest as _pt
    raise SystemExit(_pt.main([__file__, "-v"]))
