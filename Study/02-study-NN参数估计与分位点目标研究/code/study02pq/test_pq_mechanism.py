"""Study/02 同分布主协议 S2 机制分析测试。

覆盖（S2 任务 Deliverables "focused tests for analytic derivatives, decomposition
identities, pairing and finite outputs"）：
- 解析敏感度 dx/dbeta, dx/deta, dx/dgamma 与数值差分一致（真值处，多区域）；
- 分解恒等式：proj = s.u（一阶投影）且 rem = actual - proj（非线性残差定义）；
- 目标对齐 vs 等分位点切向几何：u 沿 s → u_perp=0、align=1；u 正交 → u_par=0、align=0；
- 组件抵消指数：零贡献（A=0）→ 0；完全抵消（投影=0）→ 1；无抵消 → 0；
- 真实 S1 证据配对与有限性（subprocess 隔离，PQ_PROTOCOL=iid-v1）：一对其余全部
  60 对在机制运行中同样校验（本测试抽查一对 n7_f1_s42）。
纯函数测试在默认 v3 配置下即可运行（不触碰 artifact 目录）；真实证据测试
用 subprocess 隔离协议选择。
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

from study02pq import mechanism as M  # noqa: E402

ETA = 1000.0
R = 0.95


# ----------------------------------------------------------------------
# 解析敏感度 vs 数值差分
# ----------------------------------------------------------------------

@pytest.mark.parametrize("beta,goe", [
    (1.5, 0.1), (2.0, 0.25), (3.0, 0.5), (4.0, 0.75), (5.0, 1.0),
])
def test_analytic_derivatives_match_finite_difference(beta, goe):
    eta, gamma = ETA, goe * ETA
    h = 1e-5
    x, db, de, dg, *_ = M.analytic_sensitivity(beta, eta, gamma)
    fd_b = (M.analytic_sensitivity(beta + h, eta, gamma)[0]
            - M.analytic_sensitivity(beta - h, eta, gamma)[0]) / (2 * h)
    fd_e = (M.analytic_sensitivity(beta, eta + h, gamma)[0]
            - M.analytic_sensitivity(beta, eta - h, gamma)[0]) / (2 * h)
    fd_g = (M.analytic_sensitivity(beta, eta, gamma + h)[0]
            - M.analytic_sensitivity(beta, eta, gamma - h)[0]) / (2 * h)
    for name, got, want in (("dx_dbeta", db, fd_b), ("dx_deta", de, fd_e),
                            ("dx_dgamma", dg, fd_g)):
        assert np.isclose(got, want, rtol=1e-6, atol=1e-12), (name, got, want)
    # 符号：ln(-ln 0.95) < 0 → dx_dbeta > 0
    assert db > 0 and de > 0 and dg > 0


# ----------------------------------------------------------------------
# 合成 evidence 构造（由 u 反推 hat）
# ----------------------------------------------------------------------

def _make_evidence(beta, goe, u_rows, rel_err=None):
    """按逐行无量纲误差 u 构造 evidence 状 dict（hat = 真值 + u*归一）。

    hat 保持 float64 使几何/抵消测试在机器精度下成立；float32 存储的截断行为
    由真实证据测试单独覆盖。
    """
    n = len(u_rows)
    beta_a = np.full(n, beta)
    goe_a = np.full(n, goe)
    gamma = goe * ETA
    _, _, _, _, sb, se, sg = M.analytic_sensitivity(beta, ETA, gamma)
    u = np.asarray(u_rows, dtype=np.float64)
    b_hat = beta_a * (1.0 + u[:, 0])
    e_hat = ETA * (1.0 + u[:, 1])
    g_hat = gamma + ETA * u[:, 2]
    proj = sb * u[:, 0] + se * u[:, 1] + sg * u[:, 2]
    if rel_err is None:
        rel_err = proj  # actual = proj → rem = 0（identity 场景）
    return {
        "keys_beta": beta_a, "keys_gamma_over_eta": goe_a,
        "keys_n": np.full(n, 7, dtype=np.int32),
        "keys_repeat_id": np.arange(n, dtype=np.int32),
        "beta_hat": b_hat,
        "eta_hat": e_hat,
        "gamma_hat": g_hat,
        "x95_hat": g_hat + e_hat * (-np.log(R)) ** (1.0 / b_hat),
        "x95_true": gamma + ETA * (-np.log(R)) ** (1.0 / beta),
        "min_x": np.full(n, gamma + 300.0),  # > gamma：支撑合法
        "rel_err": np.asarray(rel_err),
        "rel_err_sq": np.asarray(rel_err) ** 2,
    }


# ----------------------------------------------------------------------
# 分解恒等式
# ----------------------------------------------------------------------

def test_first_order_projection_equals_s_dot_u():
    ev = _make_evidence(2.0, 0.5, [(0.02, -0.01, 0.03), (-0.05, 0.04, 0.01)])
    r = M.row_mechanism(ev)
    sb, se, sg = r["s_beta"], r["s_eta"], r["s_gamma"]
    want = sb * r["u_beta"] + se * r["u_eta"] + sg * r["u_gamma"]
    np.testing.assert_allclose(r["proj"], want, rtol=1e-9, atol=1e-12)
    # rem = actual - proj（identity）
    np.testing.assert_allclose(r["rem"], r["actual"] - r["proj"], atol=1e-12)
    # 本场景 rel_err = proj → rem ≈ 0
    np.testing.assert_allclose(r["rem"], 0.0, atol=1e-6)


def test_decomposition_reproducible_from_true_x():
    """u_par = proj/|s| 且 |u|^2 = u_par^2 + u_perp^2（Pythagoras）。"""
    ev = _make_evidence(3.0, 0.75, [(0.03, -0.02, 0.01)])
    r = M.row_mechanism(ev)
    np.testing.assert_allclose(r["u_par"], r["proj"] / np.sqrt(
        r["s_beta"] ** 2 + r["s_eta"] ** 2 + r["s_gamma"] ** 2), rtol=1e-9, atol=1e-12)
    np.testing.assert_allclose(
        r["u_norm"] ** 2, r["u_par"] ** 2 + r["u_perp"] ** 2, rtol=1e-9, atol=1e-12)


# ----------------------------------------------------------------------
# 目标对齐 vs 等分位点切向
# ----------------------------------------------------------------------

def test_align_geometry_along_and_orthogonal():
    beta, goe = 2.0, 0.5
    _, _, _, _, sb, se, sg = M.analytic_sensitivity(beta, ETA, goe * ETA)
    s = np.array([sb, se, sg])
    s_hat = s / np.linalg.norm(s)
    # u 沿 s → u_perp=0, align=1
    u_along = (0.05 * s_hat).tolist()
    r = M.row_mechanism(_make_evidence(beta, goe, [u_along]))
    np.testing.assert_allclose(r["u_perp"], 0.0, atol=1e-10)
    np.testing.assert_allclose(r["align"], 1.0, atol=1e-9)
    # u 正交于 s（构造一个正交向量）
    t = np.array([-s_hat[1], s_hat[0], 0.0])  # 与 s_hat 点积为 0
    t = t / np.linalg.norm(t)
    u_orth = (0.05 * t).tolist()
    r2 = M.row_mechanism(_make_evidence(beta, goe, [u_orth]))
    np.testing.assert_allclose(r2["u_par"], 0.0, atol=1e-10)
    np.testing.assert_allclose(r2["align"], 0.0, atol=1e-9)
    np.testing.assert_allclose(r2["proj"], 0.0, atol=1e-10)


# ----------------------------------------------------------------------
# 组件抵消指数
# ----------------------------------------------------------------------

def test_cancellation_index_zero_denominator_and_extremes():
    beta, goe = 2.0, 0.5
    _, _, _, _, sb, se, _ = M.analytic_sensitivity(beta, ETA, goe * ETA)
    # 全零 u：A=0 → cancel=0（零分母显式处理，不产生 NaN）
    r0 = M.row_mechanism(_make_evidence(beta, goe, [(0.0, 0.0, 0.0)]))
    assert np.all(np.isfinite(r0["cancel"]))
    np.testing.assert_allclose(r0["cancel"], 0.0, atol=1e-12)
    # 完全抵消：c_beta + c_eta = 0 → B=0, A>0 → cancel=1
    t = 0.3
    u_cancel = (-se / sb * t, t, 0.0)
    rc = M.row_mechanism(_make_evidence(beta, goe, [u_cancel]))
    np.testing.assert_allclose(rc["proj"], 0.0, atol=1e-12)
    np.testing.assert_allclose(rc["cancel"], 1.0, atol=1e-12)
    # 无抵消：三贡献同号 → cancel=0
    rn = M.row_mechanism(_make_evidence(beta, goe, [(t, t, t)]))
    np.testing.assert_allclose(rn["cancel"], 0.0, atol=1e-12)


# ----------------------------------------------------------------------
# 真实 S1 证据：配对与有限性（subprocess 隔离，抽查一对）
# ----------------------------------------------------------------------

def _iid_evidence_path(fit_id):
    study_root = os.path.dirname(os.path.dirname(STUDY02_CODE_DIR))
    return os.path.join(study_root, "artifacts", "pq_iid_main", "evidence", f"{fit_id}.npz")


def test_real_evidence_pairing_and_finite_subprocess():
    fit_p = "n7_f1_s42_rP"
    fit_q = "n7_f1_s42_rQ"
    if not (os.path.isfile(_iid_evidence_path(fit_p))
            and os.path.isfile(_iid_evidence_path(fit_q))):
        pytest.skip("S1 iid evidence not present; run S1 first")
    code = r"""
import sys, os
sys.path.insert(0, os.getcwd())
import numpy as np
from study02pq import mechanism as M, run as RUN, training as TR
ep = RUN.load_evidence(TR.fit_id(7, 0, 42, "P"))
eq = RUN.load_evidence(TR.fit_id(7, 0, 42, "Q"))
for k in ("keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id"):
    assert (ep[k] == eq[k]).all(), k
rp = M.row_mechanism(ep)
rq = M.row_mechanism(eq)
assert len(rp["actual"]) == 2400, len(rp["actual"])
for k in ("actual", "proj", "rem", "u_beta", "u_eta", "u_gamma", "u_par",
          "u_perp", "align", "cancel", "s_beta", "s_eta", "s_gamma"):
    assert np.all(np.isfinite(rp[k])) and np.all(np.isfinite(rq[k])), k
assert np.all((rp["g_over_minx"] > 0) & (rp["g_over_minx"] < 1))
print("OK", len(rp["actual"]))
"""
    env = {k: v for k, v in os.environ.items() if k != "PQ_PROTOCOL"}
    env["PYTHONPATH"] = os.path.dirname(STUDY02_CODE_DIR)
    env["PQ_PROTOCOL"] = "iid-v1"
    out = subprocess.check_output([sys.executable, "-c", code],
                                  cwd=STUDY02_CODE_DIR, env=env, text=True)
    assert out.strip().endswith("OK 2400")


# ----------------------------------------------------------------------
# 聚合器（小规模合成数据）
# ----------------------------------------------------------------------

def test_pooled_stats_and_region_table_smoke():
    evs_p = [_make_evidence(2.0, 0.5, [(0.02, -0.01, 0.03)]),
             _make_evidence(4.0, 1.0, [(-0.03, 0.02, 0.01)])]
    evs_q = [_make_evidence(2.0, 0.5, [(0.01, -0.01, 0.02)]),
             _make_evidence(4.0, 1.0, [(0.01, 0.02, 0.03)])]
    rows_p = {(7, 0, 42): M.row_mechanism(evs_p[0]),
              (7, 1, 42): M.row_mechanism(evs_p[1])}
    rows_q = {(7, 0, 42): M.row_mechanism(evs_q[0]),
              (7, 1, 42): M.row_mechanism(evs_q[1])}
    sp = M.pooled_stats(list(rows_p.values()))
    assert sp["n_rows"] == 2 and sp["rms_actual"] > 0
    assert 0.0 <= sp["mean_align"] <= 1.0 and 0.0 <= sp["mean_cancel"] <= 1.0
    s1 = {(("beta", 2.0)): -0.01, (("beta", 4.0)): 0.01,
          ("gamma_over_eta", 0.5): -0.01, ("gamma_over_eta", 1.0): 0.01,
          ("n", 7): 0.0}
    df = M.region_table(rows_p, rows_q, s1)
    assert set(df["region"]) == {"beta", "gamma_over_eta", "n"}
    assert (df["s1_mean_diff"] > 0).sum() >= 1


def test_design_pair_deltas_runs_and_finite():
    base = {"rms_actual": 0.1, "rms_proj": 0.05, "rms_rem": 0.02,
            "mean_align": 0.4, "mean_cancel": 0.2, "rms_u_par": 0.05,
            "rms_u_perp": 0.06}
    stats_p = {}
    for n in (7, 10):
        for f in range(5):
            for s in (42, 2026, 3407):
                stats_p[(n, f, s)] = {m: float(v) * (1.0 + 0.1 * f)
                                      for m, v in base.items()}
    stats_q = {k: {m: 0.7 * v for m, v in vv.items()}
               for k, vv in stats_p.items()}
    out = M.design_pair_deltas(stats_p, stats_q,
                               ("rms_actual", "rms_proj", "rms_rem"),
                               n_boot=2000)
    assert set(out) == {"rms_actual", "rms_proj", "rms_rem"}
    for m, d in out.items():
        assert d["ci_lo"] <= d["mean_delta"] <= d["ci_hi"]
        assert d["n_boot"] == 2000
