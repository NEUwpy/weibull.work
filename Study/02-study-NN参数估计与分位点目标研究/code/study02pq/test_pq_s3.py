"""Study/02 S3 可信性与边界测试（`11-PQ-可信性与边界协议.md`）。

覆盖：
- 目标特异 Q 路由（Q90/Q99）的损失与 y-目标（`build_route_loss(target_R=...)`、
  `training._xR_from_params`）——x_p 公式锁定（R(x_p)=p，RELIABILITY 寿命点）；
- E2 容量：`fit_id` 后缀 + `hidden` 传参 → fit meta 记录 hidden_layers / 网络结构签名；
- E1 target_R → fit meta 记录 target_R 与 fit_id（rQ90）；
- S3 配置自洽（336 授权 fits、产物根隔离、插值 n_samples=33600）；
- 插值主表确定性重建（命名空间 study01_nrmc_v1）与按 n 选择；
- E1 生产路径（redirect → save_fit → fit_complete 回环，临时根）。

默认环境不设 PQ_PROTOCOL（v3）；所有 s3_boundary/s3_analyze 模块级测试经
subprocess + PQ_PROTOCOL=iid-v1 隔离执行（模块断言 CFG.PROTOCOL_VERSION == iid-v1）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
import torch

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

from study02pq import config as CFG  # noqa: E402
from study02pq import data as DATA  # noqa: E402
from study02pq import losses as LOSS  # noqa: E402
from study02pq import model as MODEL  # noqa: E402
from study02pq import training as TR  # noqa: E402


def _subprocess_env(env_extra: dict, skip_master: bool = False) -> dict:
    env = {k: v for k, v in os.environ.items() if k != "PQ_PROTOCOL"}
    env["PYTHONPATH"] = os.path.dirname(STUDY02_CODE_DIR)
    env["PQ_PROTOCOL"] = "iid-v1"
    if skip_master:
        env["PQ_S3_SKIP_MASTER"] = "1"
    env.update(env_extra)
    return env


def _run_iid(code: str, tmp_path=None, env_extra=None, cwd=None) -> str:
    return subprocess.check_output(
        [sys.executable, "-c", code],
        cwd=cwd or STUDY02_CODE_DIR,
        env=_subprocess_env(env_extra or {}), text=True).strip()


# ----------------------------------------------------------------------
# 目标特异 Q 损失与 y-目标（x_p = gamma + eta*(-ln p)^(1/beta)，R(x_p)=p）
# ----------------------------------------------------------------------

def test_build_route_loss_target_R():
    """Q90/Q99 路由 + target_R → Q 损失在目标水平；缺省 Q → x0.95。"""
    o = torch.randn(6, 3, dtype=torch.float64)
    min_X = torch.tensor([3.0, 4.0, 5.0, 6.0, 7.0, 8.0], dtype=torch.float64)
    y = torch.randn(6, dtype=torch.float64) + 10.0
    b, e, g = LOSS.decode_params(o, min_X)
    for R in (0.90, 0.99):
        fn, kind = LOSS.build_route_loss(f"Q{int(round(R*100))}", target_R=R)
        assert kind == "x_R"
        xR = LOSS.weibull_quantile(b, e, g, R)
        want = torch.mean(((xR - y) / y) ** 2)
        assert torch.isclose(fn(o, y, min_X), want), f"Q loss at R={R} not at target"
    fn2, kind2 = LOSS.build_route_loss("Q")
    assert kind2 == "x_R"
    x95 = LOSS.weibull_quantile(b, e, g, CFG.X0_95_R)
    assert torch.isclose(fn2(o, y, min_X), torch.mean(((x95 - y) / y) ** 2))
    fn3, kind3 = LOSS.build_route_loss("P")
    assert kind3 == "params"


def test_xR_from_params_matches_formula():
    P = np.array([[2.0, 1000.0, 250.0], [3.0, 1000.0, 875.0],
                  [4.5, 1000.0, 100.0]], dtype=np.float64)
    for R in (0.90, 0.95, 0.99):
        want = P[:, 2] + P[:, 1] * (-np.log(R)) ** (1.0 / P[:, 0])
        got = TR._xR_from_params(P, R)
        assert np.allclose(got, want), f"R={R}"


def test_train_target_R_meta():
    """E1：route='Q90' + target_R=0.90 → fit_id rQ90、meta target_R=0.90、配对 SHA 与 P 相同。"""
    master = DATA.build_master(beta_grid=[2.0, 3.0], gamma_grid=CFG.GAMMA_GRID,
                               n_grid=[7, 10], repeats=6)
    r = TR.train_one_fit(7, 0, 42, "Q90", master, max_epochs=4, patience=2,
                         target_R=0.90, split_strategy="repeat_stratified")
    assert r["meta"]["fit_id"] == "n7_f1_s42_rQ90"
    assert r["meta"]["route"] == "Q90"
    assert r["meta"]["target_R"] == 0.90
    assert r["meta"]["split_strategy"] == "repeat_stratified"
    assert r["meta"]["support_legality_ok"] is True
    rp = TR.train_one_fit(7, 0, 42, "P", master, max_epochs=4, patience=2,
                          split_strategy="repeat_stratified")
    for k in ["init_param_sha", "batch_order_sha", "network_sha", "scaler_sha",
              "train_rows_sha", "val_rows_sha", "test_rows_sha"]:
        assert r["meta"][k] == rp["meta"][k], f"pairing mismatch {k}"


# ----------------------------------------------------------------------
# E2 容量：fit_id 后缀 + hidden
# ----------------------------------------------------------------------

def test_fit_id_suffix():
    assert TR.fit_id(7, 0, 42, "P", "_sm64") == "n7_f1_s42_rP_sm64"
    assert TR.fit_id(7, 0, 42, "Q", "_lg512") == "n7_f1_s42_rQ_lg512"
    assert TR.fit_id(7, 0, 42, "Q90") == "n7_f1_s42_rQ90"


def test_train_capacity_hidden_meta():
    """E2：hidden=(64,32) + fit_suffix → meta 记录 hidden_layers 与对应网络签名。"""
    master = DATA.build_master(beta_grid=[2.0, 3.0], gamma_grid=CFG.GAMMA_GRID,
                               n_grid=[7, 10], repeats=6)
    r = TR.train_one_fit(7, 0, 42, "Q", master, max_epochs=4, patience=2,
                         hidden=(64, 32), fit_suffix="_sm64",
                         split_strategy="repeat_stratified")
    assert r["meta"]["hidden_layers"] == [64, 32]
    assert r["meta"]["fit_id"] == "n7_f1_s42_rQ_sm64"
    assert r["meta"]["network_sha"] == MODEL.structure_signature(7, hidden=(64, 32))
    assert r["meta"]["network_sha"] != MODEL.structure_signature(7)
    assert r["meta"]["target_R"] is None
    assert r["meta"]["support_legality_ok"] is True


# ----------------------------------------------------------------------
# S3 配置自洽（subprocess，iid）
# ----------------------------------------------------------------------

def test_s3_config_fit_counts_and_roots():
    code = (
        "import json, os\n"
        "from study02pq import config as CFG\n"
        "with open(os.path.join(CFG.STUDY02_ROOT, 'configs', 'pq-s3-boundary-v1.json'), "
        "encoding='utf-8') as f: cfg = json.load(f)\n"
        "fc = cfg['fit_counts']\n"
        "assert fc['E1_target_levels'] == 120 and fc['E2_capacity'] == 96\n"
        "assert fc['E3_interpolation'] == 120 and fc['total_new_fits'] == 336\n"
        "roots = cfg['artifact_roots']\n"
        "assert 'pq_iid_main' not in roots['target'] and 'pq_iid_main' not in roots['capacity']\n"
        "assert 'pq_iid_main' not in roots['interp']\n"
        "assert cfg['interpolation']['n_samples'] == 33600\n"
        "assert cfg['interpolation']['namespace'] == 'study01_nrmc_v1'\n"
        "print('OK')\n"
    )
    assert _run_iid(code) == "OK"


# ----------------------------------------------------------------------
# 插值主表确定性（subprocess，iid；缩小 N_GRID 避免生成 33600 样本）
# ----------------------------------------------------------------------

def test_build_interp_master_deterministic():
    code = (
        "import sys, os\n"
        "sys.path.insert(0, os.getcwd())\n"
        "import numpy as np\n"
        "from study02pq import s3_boundary as S3, config as CFG\n"
        "CFG.N_GRID = [7]\n"
        "k1, X1 = S3.build_interp_master()\n"
        "k2, X2 = S3.build_interp_master()\n"
        "assert len(k1) == 7 * 4 * 1 * 300, len(k1)\n"
        "assert np.array_equal(k1, k2)\n"
        "assert all(np.array_equal(X1[i], X2[i]) for i in range(len(X1)))\n"
        "assert np.all(np.diff(X1[0]) >= 0)  # 升序样本\n"
        "idx, Xn, mn, msk = S3._interp_rows_for_n(k1, X1, 7)\n"
        "assert len(idx) == len(X1) and Xn.shape == (len(X1), 7)\n"
        "assert np.allclose(mn, [X1[r].min() for r in idx])\n"
        "print('OK')\n"
    )
    assert _run_iid(code, env_extra={"PQ_S3_SKIP_MASTER": "1"}) == "OK"


# ----------------------------------------------------------------------
# E1 生产路径（redirect → save_fit → fit_complete 回环；临时根，缩小设计）
# ----------------------------------------------------------------------

def test_e1_production_path_roundtrip(tmp_path):
    code = (
        "import sys, os, glob, json\n"
        "sys.path.insert(0, os.getcwd())\n"
        "from study02pq import s3_boundary as S3, config as CFG, data as DATA, run as RUN\n"
        "root = r%r\n"
        "S3.ART_ROOTS = {'target': root, 'capacity': root, 'interp': root}\n"
        "CFG.MAX_EPOCHS, CFG.PATIENCE, CFG.N_GRID, CFG.REPEATS = 3, 2, [7], 6\n"
        "S3.master = DATA.build_master(beta_grid=[2.0, 3.0], "
        "gamma_grid=CFG.GAMMA_GRID, n_grid=[7], repeats=6)\n"
        "S3.run_e1([42], resume=False)\n"
        "evs = sorted(glob.glob(os.path.join(root, 'evidence', '*.npz')))\n"
        "assert len(evs) == 2 * 1 * 5 * 1, len(evs)  # Q90+Q99 x 1n x 5fold x 1seed\n"
        "fit = os.path.basename(evs[0])[:-4]\n"
        "assert RUN.fit_complete(fit)\n"
        "with open(os.path.join(root, 'fit_metadata', fit + '.json'), "
        "encoding='utf-8') as f: m = json.load(f)\n"
        "assert m['target_R'] in (0.9, 0.99)\n"
        "print('OK')\n"
    ) % str(tmp_path / "target")
    out = _run_iid(code, env_extra={"PQ_S3_SKIP_MASTER": "1"})
    assert out.splitlines()[-1] == "OK", out


# ----------------------------------------------------------------------
# s3_analyze 全管道 smoke（合成证据，临时根，n_boot=50）
# ----------------------------------------------------------------------

def test_s3_analyze_pipeline_smoke(tmp_path):
    code = r'''
import sys, os, json
sys.path.insert(0, os.getcwd())
import numpy as np
from study02pq import s3_analyze as A, config as CFG, data as DATA, training as TR

root = r%r
s1 = os.path.join(root, 'pq_iid_main')
tgt = os.path.join(root, 'pq_s3_target')
cap = os.path.join(root, 'pq_s3_capacity')
ipr = os.path.join(root, 'pq_s3_interp')
for d in (s1, tgt, cap, ipr):
    for sub in ('evidence', 'fit_metadata', 'interp', 'analysis'):
        os.makedirs(os.path.join(d, sub), exist_ok=True)

E = CFG.ETA
n = 7
CFG.N_GRID = [7]  # 合成证据只覆盖 n=7；analyze_e1/e2/e3 遍历 CFG.N_GRID
master = DATA.build_master(beta_grid=[2.0, 3.0], gamma_grid=CFG.GAMMA_GRID,
                           n_grid=[7], repeats=10)

def ev_npz(route_root, fit, te):
    keys = master.keys[te]
    P = master.true_params[te]
    beta, eta, gamma = P[:, 0], P[:, 1], P[:, 2]
    x95 = gamma + eta * (-np.log(0.95)) ** (1.0 / beta)
    b_hat = beta * 1.01
    g_hat = gamma * 0.99
    xh = g_hat + eta * (-np.log(0.95)) ** (1.0 / b_hat)
    rel = (xh - x95) / x95
    np.savez_compressed(os.path.join(route_root, 'evidence', fit + '.npz'),
        keys_beta=keys[:, 0].astype(np.float64),
        keys_gamma_over_eta=keys[:, 1].astype(np.float64),
        keys_n=keys[:, 2].astype(np.int32), keys_repeat_id=keys[:, 3].astype(np.int32),
        beta_hat=b_hat.astype(np.float32), eta_hat=eta.astype(np.float32),
        gamma_hat=g_hat.astype(np.float32), x95_hat=xh.astype(np.float32),
        x95_true=x95.astype(np.float32),
        min_x=np.array([master.X[r].min() for r in te], dtype=np.float32),
        rel_err=rel.astype(np.float32), rel_err_sq=(rel ** 2).astype(np.float32))
    with open(os.path.join(route_root, 'fit_metadata', fit + '.json'), 'w',
              encoding='utf-8') as f:
        json.dump({'fit_id': fit, 'n': n, 'fold': int(fit.split('f')[1].split('_')[0]),
                   'seed': 42, 'route': fit.split('r')[-1].split('_')[0],
                   'converged': True, 'nan_flag': False, 'n_nonfinite': 0,
                   'n_illegal': 0, 'n_support_viol': 0}, f)

for fold_idx in range(5):
    tr, va, te = DATA.split_repeat_fold(master, n, fold_idx)
    for route in ('P', 'Q'):
        ev_npz(s1, TR.fit_id(n, fold_idx, 42, route), te)
    for route in ('Q90', 'Q99'):
        ev_npz(tgt, TR.fit_id(n, fold_idx, 42, route), te)
for suffix in ('_sm64', '_lg512'):
    for fold_idx in (0, 2):
        tr, va, te = DATA.split_repeat_fold(master, n, fold_idx)
        for route in ('P', 'Q'):
            ev_npz(cap, TR.fit_id(n, fold_idx, 42, route, suffix), te)

betas = [1.75, 2.25, 2.75, 3.25, 3.75, 4.25, 4.75]
goes = [0.175, 0.375, 0.625, 0.875]
rows = [(b, g, r) for b in betas for g in goes for r in range(3)]
ibeta = np.array([r[0] for r in rows], dtype=np.float64)
igoe = np.array([r[1] for r in rows], dtype=np.float64)
in_ = np.array([n] * len(rows), dtype=np.int32)
irid = np.arange(len(rows), dtype=np.int32)
gamma = igoe * E
xt = gamma + E * (-np.log(0.95)) ** (1.0 / ibeta)
g_hat = gamma * 0.99
xh = g_hat + E * (-np.log(0.95)) ** (1.0 / ibeta)
rel = (xh - xt) / xt
for fold_idx in range(5):
    tr, va, te = DATA.split_repeat_fold(master, n, fold_idx)
    for route in ('P', 'Q'):
        fit = TR.fit_id(n, fold_idx, 42, route)
        ev_npz(ipr, fit, te)
        np.savez_compressed(os.path.join(ipr, 'interp', fit + '.npz'),
            keys_beta=ibeta, keys_gamma_over_eta=igoe, keys_n=in_, keys_repeat_id=irid,
            beta_hat=ibeta.astype(np.float32), eta_hat=np.full(len(rows), E).astype(np.float32),
            gamma_hat=g_hat.astype(np.float32), min_x=np.full(len(rows), 100.0, dtype=np.float32),
            x95_hat=xh.astype(np.float32), x95_true=xt.astype(np.float32),
            rel_err=rel.astype(np.float32), rel_err_sq=(rel ** 2).astype(np.float32))

A.S1_ROOT, A.ROOT_TARGET, A.ROOT_CAP, A.ROOT_INTERP = s1, tgt, cap, ipr
A.analyze_e1([42], 50)
A.analyze_e2([42])
A.analyze_e3([42], 50)
for p in ('cross_target_matrix.json', 'target_summary.json',
          'sensitivity_by_target.json', 'mechanism_exact_by_target.json'):
    assert os.path.isfile(os.path.join(tgt, 'analysis', p)), p
assert os.path.isfile(os.path.join(cap, 'analysis', 'capacity_summary.json'))
assert os.path.isfile(os.path.join(ipr, 'analysis', 'interp_summary.json'))
with open(os.path.join(ipr, 'analysis', 'interp_summary.json'), encoding='utf-8') as f:
    s = json.load(f)
assert s['s1_evidence_identity']['pass'] is True
with open(os.path.join(tgt, 'analysis', 'cross_target_matrix.json'), encoding='utf-8') as f:
    m = json.load(f)
assert set(m['routes']) == {'P', 'Q95', 'Q90', 'Q99'}
assert len(m['targets']) == 3
print('OK')
''' % str(tmp_path)
    out = _run_iid(code, env_extra={"PQ_S3_SKIP_MASTER": "1"})
    assert out.splitlines()[-1] == "OK", out


# ----------------------------------------------------------------------
# R2 S3-001 回归：eval_interp 推理输入必须经过调用方传入的 (n, fold) scaler
# ----------------------------------------------------------------------

def test_eval_interp_applies_caller_scaler():
    """非恒等 scaler：eval_interp 喂给模型的输入必须 == scaler.transform(X_n)，
    且 != 原始插值样本。防止注释与实现再次分离（S3-001 blocking 回归）。"""
    code = r'''
import sys, os
sys.path.insert(0, os.getcwd())
import numpy as np
import torch
from torch import nn
from study02pq import s3_boundary as S3, config as CFG, data as DATA, model as MODEL

CFG.N_GRID = [7]
master = DATA.build_master(beta_grid=[2.0, 3.0], gamma_grid=CFG.GAMMA_GRID,
                           n_grid=[7], repeats=6)
tr, _, _ = DATA.split_repeat_fold(master, 7, 0)
X_tr, _, _ = DATA.make_arrays(master, tr)
scaler = DATA.PerPositionScaler().fit(X_tr)
# 非恒等断言：真实样本 ~eta 量级，mean/scale 不会退化为 (0, 1)
assert not np.allclose(scaler.mean_, 0.0), scaler.mean_
assert not np.allclose(scaler.scale_, 1.0), scaler.scale_

keys_i, X_i = S3.build_interp_master()
idx, X_n, min_x, _ = S3._interp_rows_for_n(keys_i, X_i, 7)
X_n_s = scaler.transform(X_n)
assert X_n_s.shape == X_n.shape
assert not np.allclose(X_n_s, X_n), "scaler must change the input"

class Spy(nn.Module):
    instances = []
    def __init__(self):
        super().__init__()
        self.last_input = None
        Spy.instances.append(self)
    def forward(self, x):
        self.last_input = x.detach().clone()
        return torch.zeros(x.shape[0], 3, dtype=x.dtype)

real_build = MODEL.build_model
MODEL.build_model = lambda n, seed: Spy()
try:
    S3.eval_interp({}, 7, 42, keys_i, X_i, scaler)
finally:
    MODEL.build_model = real_build
assert len(Spy.instances) == 1, len(Spy.instances)
got = Spy.instances[0].last_input
assert got is not None, "model was never called"
assert got.dtype == torch.float64 and got.shape == torch.Size(X_n_s.shape)
assert np.allclose(got.numpy(), X_n_s), "model input != scaler.transform(X_n)"
assert not np.allclose(got.numpy(), X_n), "model received RAW unscaled interp samples"
print('OK')
'''
    out = _run_iid(code, env_extra={"PQ_S3_SKIP_MASTER": "1"})
    assert out.splitlines()[-1] == "OK", out
