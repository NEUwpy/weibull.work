#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
mdm_offset_study.py
===================
三参数 Weibull · MDM 偏移量研究：逐样本数据生成 + 汇总分析 + 可预测性试点（线性/浅层探针）

实现依据《第六轮结果》附录的闭式实现：
  - Bernard 中位秩  F_i=(i-0.3)/(n+0.4),  x_i=-ln(1-F_i)
  - 伪尺度 η̂_i=(t_(i)-γ)·x_i^(-1/β)，σ²(β|γ)=Cuu-2γCuv+γ²Cvv（样本协方差, ddof=1）
  - 廓线 S(γ)=min_β σ(β|γ)；包络梯度 g=(γCvv-Cuv)/S（在内层最优 β 处取 C）
  - 对 g 取累计极大消除平坦区微小波动；解 g(γ̂)=δ 取最靠近 t_(1) 的根；γ̂ 不作非负截断
  - s_v(β,n)=std{x_i^(-1/β)} (ddof=1)；归一化偏移 c=δ/s_v
未在报告中写明、本脚本作为显式配置项（请与第六轮口径核对）：
  - β 搜索范围/网格：默认 log 均匀 [0.1, 20]，261 点（--beta-min/--beta-max/--nbeta）
  - η̂ 取法：默认 n 个伪估计量的均值（与谢里阳等2025原文式(6)一致；--eta-hat median 可切换）
  - γ 网格：t_(1)-gap，gap 在 [1e-6·R, 60·R] 几何分布（R=极差），左端自动扩展

子命令：
  verify    校验 s_v 与报告表2是否完全一致（实现对齐的硬门槛）
  simulate  生成逐样本数据（npz，留存在本地，亦是后续 NN 的训练数据底座）
  analyze   汇总分析 + 试点回归，输出 tables/*.csv 与 summary_report.json（回传用）
  all       simulate + analyze

示例：
  python mdm_offset_study.py verify
  python mdm_offset_study.py all --quick            # 冒烟测试（每格80次，约1-3分钟）
  python mdm_offset_study.py all --reps 800         # 正式运行（默认800，约10-40分钟）
"""

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

# ----------------------------- 全局配置 -----------------------------

BETAS = [1.0, 1.5, 2.0, 3.0, 5.0]
NS = [7, 10, 20, 30, 50]
ETA_TRUE = 100.0
GOE_MAIN = 0.1                      # 主网格 γ/η
GOE_EXTRA = [0.0, 0.5, 1.0]         # 不变性附加检验（β=2, n=10），1.0 对接原文设定
C_GRID = np.round(np.linspace(0.0, 0.75, 61), 6)   # 归一化偏移扫描网格（含0）
DELTA_BASE = 0.1                    # 文献基线
GLOBAL_C = 0.21                     # 报告的全局归一化偏移
R_LIFE = [0.99, 0.999]              # 寿命分位
LAW_BETA_MIN = 1.5                  # 标度律拟合的 β 下限（报告口径）

# 报告表2（用于 verify 的硬校验，2位小数）
REPORT_SV = {
    1.0: [3.40, 4.26, 6.47, 8.18, 10.91],
    1.5: [1.42, 1.63, 2.09, 2.38, 2.79],
    2.0: [0.87, 0.96, 1.15, 1.26, 1.39],
    3.0: [0.48, 0.52, 0.58, 0.62, 0.66],
    5.0: [0.25, 0.27, 0.29, 0.30, 0.32],
}

FEATURE_NAMES = [
    "ln_n",            # A 组
    "ln_beta0", "ln_sv0",                            # B 组追加（β̂₀ 来自 δ=0.1 初解）
    "r21", "r31", "rmed", "rmean", "skew",           # C 组追加（平移/尺度不变的次序统计量）
    "ln_gapvtx", "depth", "ln_wallwidth", "gmax",    # D 组追加（廓线形状描述子，部署期免费）
]
FEATURE_GROUPS = {
    "A_n_only": ["ln_n"],
    "B_plus_beta0": ["ln_n", "ln_beta0", "ln_sv0"],
    "C_plus_orderstats": ["ln_n", "ln_beta0", "ln_sv0", "r21", "r31", "rmed", "rmean", "skew"],
    "D_full": FEATURE_NAMES,
}

# ----------------------------- 基础构件 -----------------------------

def bernard_x(n: int) -> np.ndarray:
    """Bernard 中位秩对应的 x_i = -ln(1-F_i)。"""
    i = np.arange(1, n + 1)
    F = (i - 0.3) / (n + 0.4)
    return -np.log1p(-F)


def sv_value(beta, n) -> float:
    """s_v(β,n)：{x_i^(-1/β)} 的样本标准差（ddof=1）。"""
    x = bernard_x(int(n))
    return float(np.std(x ** (-1.0 / beta), ddof=1))


def make_beta_grid(bmin, bmax, nb) -> np.ndarray:
    return np.exp(np.linspace(np.log(bmin), np.log(bmax), nb))


class CellBasis:
    """对固定 n 与 β 网格可预计算的量：v、v 的均值/离差/方差。"""
    def __init__(self, n: int, beta_grid: np.ndarray):
        self.n = n
        self.beta_grid = beta_grid
        x = bernard_x(n)
        self.v = x[None, :] ** (-1.0 / beta_grid[:, None])      # (nb, n)
        self.vm = self.v.mean(axis=1)                            # (nb,)
        self.dv = self.v - self.vm[:, None]
        self.Cvv = (self.dv ** 2).sum(axis=1) / (n - 1)          # (nb,) = s_v²(β,n)
        self.sv = np.sqrt(self.Cvv)


class Profile:
    """单个样本的闭式廓线：S(γ)、包络梯度 g(γ)、累计极大 gm，及解根/回代。"""

    __slots__ = ("basis", "t", "t1", "R", "gamma", "S", "g", "gm", "bidx",
                 "um_all", "Cuv", "vtx_idx")

    def __init__(self, t_sorted: np.ndarray, basis: CellBasis,
                 ngamma: int, gap_lo_frac: float = 1e-6, gap_hi_frac: float = 60.0):
        self.basis = basis
        self.t = t_sorted
        self.t1 = t_sorted[0]
        self.R = max(t_sorted[-1] - t_sorted[0], 1e-12)
        n, nb = basis.n, basis.beta_grid.size

        u = t_sorted[None, :] * basis.v                          # (nb, n)
        um = u.mean(axis=1)
        du = u - um[:, None]
        Cuu = (du ** 2).sum(axis=1) / (n - 1)
        Cuv = (du * basis.dv).sum(axis=1) / (n - 1)
        self.um_all, self.Cuv = um, Cuv

        hi = gap_hi_frac
        for _ in range(3):  # 左端自动扩展，确保把谷顶包进来
            gaps = np.geomspace(gap_lo_frac * self.R, hi * self.R, ngamma)
            gamma = self.t1 - gaps[::-1]                         # 升序 γ
            sig2 = (Cuu[:, None]
                    - 2.0 * gamma[None, :] * Cuv[:, None]
                    + (gamma ** 2)[None, :] * basis.Cvv[:, None])  # (nb, ng)
            bidx = np.argmin(sig2, axis=0)
            S2 = sig2[bidx, np.arange(gamma.size)]
            S = np.sqrt(np.clip(S2, 1e-300, None))
            g = (gamma * basis.Cvv[bidx] - Cuv[bidx]) / S
            vtx = int(np.argmin(S))
            if vtx > 2 or hi > 1e5:
                break
            hi *= 20.0                                           # 谷顶贴左边界 → 扩展
        self.gamma, self.S, self.g, self.bidx, self.vtx_idx = gamma, S, g, bidx, vtx
        self.gm = np.maximum.accumulate(g)

    def solve(self, delta: float, eta_hat_mode: str = "mean"):
        """解 g(γ̂)=δ（累计极大版），回代 β̂、η̂。返回 (γ̂, β̂, η̂, flag)。
        flag: 0 正常根; 1 δ 超出右端（取墙位）; 2 根落在左端边界。"""
        gm, gamma = self.gm, self.gamma
        k = int(np.searchsorted(gm, delta, side="left"))
        flag = 0
        if k >= gamma.size:
            k, flag = gamma.size - 1, 1
            gam = gamma[-1]
        elif k == 0:
            flag = 2
            gam = gamma[0]
        else:
            g0, g1 = gm[k - 1], gm[k]
            gam = gamma[k] if g1 <= g0 else gamma[k - 1] + (delta - g0) * (gamma[k] - gamma[k - 1]) / (g1 - g0)
            if (g1 - delta) > (delta - g0):
                k = k - 1
        bi = int(self.bidx[k])
        beta_hat = float(self.basis.beta_grid[bi])
        eta_vec = self.t * self.basis.v[bi] - gam * self.basis.v[bi]
        eta_hat = float(np.median(eta_vec)) if eta_hat_mode == "median" else float(self.um_all[bi] - gam * self.basis.vm[bi])
        return float(gam), beta_hat, eta_hat, flag

    # ---- 廓线形状描述子（部署期可得）----
    def descriptors(self, sv0: float, eta_hat_mode: str):
        gapv = max(self.t1 - self.gamma[self.vtx_idx], 1e-12)
        iw = int(np.searchsorted(self.t1 - self.gamma[::-1], 1e-3 * self.R))  # gap≈1e-3R 处
        iw = self.gamma.size - 1 - min(max(iw, 0), self.gamma.size - 1)
        S_wall = self.S[min(max(iw, 0), self.S.size - 1)]
        depth = float(self.S[self.vtx_idx] / max(S_wall, 1e-300))
        glo, ghi = 0.1 * sv0, 0.4 * sv0
        gl, _, _, _ = self.solve(glo, eta_hat_mode)
        gh, _, _, _ = self.solve(ghi, eta_hat_mode)
        wall_w = max(gh - gl, 1e-12) / self.R if gh > gl else max(gl - gh, 1e-12) / self.R
        gmax = float(self.gm[-1] / max(sv0, 1e-300))
        return np.log(gapv / self.R), depth, np.log(wall_w), gmax


def metrics(gam, bh, eh, beta, eta, gamma_t):
    """各项误差度量。返回 dict。"""
    lnb = np.log(bh) - np.log(beta)
    lnh = np.log(max(eh, 1e-300)) - np.log(eta)
    dge = (gam - gamma_t) / eta
    comp = lnb * lnb + lnh * lnh + dge * dge
    out = {"comp": comp, "dg_eta": dge, "lnb": lnb, "lnh": lnh}
    for R in R_LIFE:
        q = (-np.log(R))
        xt = gamma_t + eta * q ** (1.0 / beta)
        xh = gam + eh * q ** (1.0 / bh)
        out[f"xr{str(R).replace('0.', '')}"] = (xh - xt) / xt
    return out


# ----------------------------- verify -----------------------------

def cmd_verify(args):
    print("校验 s_v(β,n) 与报告表2（Bernard 中位秩, ddof=1）...")
    rows, maxdiff = [], 0.0
    for b in BETAS:
        vals = [sv_value(b, n) for n in NS]
        diffs = [abs(round(v, 2) - r) for v, r in zip(vals, REPORT_SV[b])]
        maxdiff = max(maxdiff, max(diffs))
        rows.append([b] + [f"{v:.4f}" for v in vals])
        print(f"  β={b:<4}: " + "  ".join(f"{v:7.4f}" for v in vals)
              + ("   ✓" if max(diffs) < 0.005 else f"   ✗ 与表2偏差 {max(diffs):.3f}"))
    ok = maxdiff < 0.005
    print(f"\n结论：{'通过 —— 秩公式与归一化标尺和报告完全一致' if ok else '未通过 —— 请先排查秩公式/ddof 再继续'}")
    return {"sv_check_pass": bool(ok), "sv_max_abs_diff_2dp": round(float(maxdiff), 4)}


# ----------------------------- simulate -----------------------------

def build_cells():
    cells = []
    for b in BETAS:
        for n in NS:
            cells.append({"beta": b, "n": n, "goe": GOE_MAIN, "main": True})
    for goe in GOE_EXTRA:
        cells.append({"beta": 2.0, "n": 10, "goe": goe, "main": False})
    return cells


def cmd_simulate(args):
    t0 = time.time()
    outdir = Path(args.outdir); outdir.mkdir(parents=True, exist_ok=True)
    reps = args.reps
    beta_grid = make_beta_grid(args.beta_min, args.beta_max, args.nbeta)
    cells = build_cells()
    ncell, nC = len(cells), C_GRID.size
    N = ncell * reps
    nmax = max(NS)

    # 容器
    arr = {k: np.full((N, nC), np.nan, np.float32)
           for k in ["comp", "dg_eta", "lnb", "lnh", "xr99", "xr999"]}
    cflag = np.zeros((N, nC), np.int8)
    feats = np.full((N, len(FEATURE_NAMES)), np.nan, np.float32)
    base01 = np.full((N, 8), np.nan, np.float32)   # δ=0.1: γ̂,β̂,η̂,comp,dg_eta,lnb,lnh,xr999
    tmat = np.full((N, nmax), np.nan, np.float32)
    cell_id = np.zeros(N, np.int16)

    ss = np.random.SeedSequence(args.seed)
    child = ss.spawn(ncell)
    basis_cache = {}
    row = 0
    for ci, cell in enumerate(cells):
        b, n, goe = cell["beta"], cell["n"], cell["goe"]
        gamma_t, eta_t = goe * ETA_TRUE, ETA_TRUE
        if n not in basis_cache:
            basis_cache[n] = CellBasis(n, beta_grid)
        basis = basis_cache[n]
        sv_cell_exact = sv_value(b, n)              # 真 β 的归一化标尺
        deltas = C_GRID * sv_cell_exact
        rng = np.random.default_rng(child[ci])
        for r in range(reps):
            t = np.sort(gamma_t + eta_t * rng.weibull(b, n))
            prof = Profile(t, basis, args.ngamma)
            # δ=0.1 初解（基线 + 特征锚）
            g0, b0, e0, f0 = prof.solve(DELTA_BASE, args.eta_hat)
            m0 = metrics(g0, b0, e0, b, eta_t, gamma_t)
            base01[row] = [g0, b0, e0, m0["comp"], m0["dg_eta"], m0["lnb"], m0["lnh"], m0["xr999"]]
            # c 扫描
            for j, d in enumerate(deltas):
                gj, bj, ej, fj = prof.solve(float(d), args.eta_hat)
                mm = metrics(gj, bj, ej, b, eta_t, gamma_t)
                for k in arr:
                    arr[k][row, j] = mm[k]
                cflag[row, j] = fj
            # 特征
            sv0 = sv_value(b0, n)
            Rng_ = t[-1] - t[0]
            med = float(np.median(t)); mean = float(np.mean(t))
            sd = float(np.std(t, ddof=1)) + 1e-300
            skew = float(np.mean(((t - mean) / sd) ** 3))
            d1, d2, d3, d4 = prof.descriptors(sv0, args.eta_hat)
            feats[row] = [
                np.log(n),
                np.log(b0), np.log(sv0),
                (t[1] - t[0]) / Rng_, (t[2] - t[0]) / Rng_,
                (med - t[0]) / Rng_, (mean - t[0]) / Rng_, skew,
                d1, d2, d3, d4,
            ]
            tmat[row, :n] = t
            cell_id[row] = ci
            row += 1
        print(f"  [{ci+1:>2}/{ncell}] β={b:<4} n={n:<3} γ/η={goe:<4}"
              f"  done ({time.time()-t0:6.1f}s)", flush=True)

    cell_tab = pd.DataFrame(cells)
    cell_tab["sv"] = [sv_value(c["beta"], c["n"]) for c in cells]
    np.savez_compressed(
        outdir / "per_sample.npz",
        c_grid=C_GRID, cell_id=cell_id, t=tmat, features=feats,
        feature_names=np.array(FEATURE_NAMES), base01=base01, cflag=cflag,
        **arr,
    )
    cell_tab.to_csv(outdir / "cells.csv", index_label="cell_id")
    cfg = vars(args).copy(); cfg["command"] = "simulate"; cfg["n_samples"] = int(N)
    (outdir / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=2))
    print(f"simulate 完成：{N} 个样本，{time.time()-t0:.1f}s → {outdir}/per_sample.npz")


# ----------------------------- analyze -----------------------------

def _interp_rows(curves: np.ndarray, c_eval: np.ndarray) -> np.ndarray:
    """对每行曲线（定义在 C_GRID 上）在各自 c_eval 处线性插值。"""
    dc = C_GRID[1] - C_GRID[0]
    x = np.clip(c_eval, C_GRID[0], C_GRID[-1])
    pos = (x - C_GRID[0]) / dc
    k0 = np.clip(np.floor(pos).astype(int), 0, C_GRID.size - 2)
    w = pos - k0
    rows = np.arange(curves.shape[0])
    return curves[rows, k0] * (1 - w) + curves[rows, k0 + 1] * w


def _ridge_fit_predict(Xtr, ytr, Xte, lam=1.0):
    mu, sd = Xtr.mean(0), Xtr.std(0) + 1e-12
    Zr, Ze = (Xtr - mu) / sd, (Xte - mu) / sd
    Zr = np.hstack([Zr, np.ones((Zr.shape[0], 1))])
    Ze = np.hstack([Ze, np.ones((Ze.shape[0], 1))])
    A = Zr.T @ Zr + lam * np.eye(Zr.shape[1]); A[-1, -1] -= lam
    w = np.linalg.solve(A, Zr.T @ ytr)
    return Ze @ w


def _grid_ratio(med_by_cell: dict, base_by_cell: dict, main_cells: list) -> float:
    """各格中位复合误差相对固定0.1的比值，再取全网格中位（报告口径）。"""
    r = [med_by_cell[c] / base_by_cell[c] for c in main_cells]
    return float(np.median(r))


def cmd_analyze(args):
    t0 = time.time()
    outdir = Path(args.outdir)
    tabdir = outdir / "tables"; tabdir.mkdir(parents=True, exist_ok=True)
    z = np.load(outdir / "per_sample.npz", allow_pickle=False)
    cells = pd.read_csv(outdir / "cells.csv")
    comp, dg_eta, lnb, lnh = z["comp"], z["dg_eta"], z["lnb"], z["lnh"]
    xr99, xr999 = z["xr99"], z["xr999"]
    feats, base01, cid = z["features"].astype(np.float64), z["base01"], z["cell_id"]
    N, nC = comp.shape
    main_cells = cells.index[cells["main"]].tolist()
    rngB = np.random.default_rng(args.seed + 7)
    nboot = args.nboot

    cell_rows = {c: np.where(cid == c)[0] for c in cells.index}
    beta_c = cells["beta"].to_dict(); n_c = cells["n"].to_dict(); sv_c = cells["sv"].to_dict()
    goe_c = cells["goe"].to_dict()

    # ---------- 1) 误差–c 曲线 / c* / 平坦带 / 一致性 ----------
    rows_curve, rows_cstar, rows_cons = [], [], []
    for c in cells.index:
        idx = cell_rows[c]
        medc = np.median(comp[idx], axis=0)
        for j, cv in enumerate(C_GRID):
            rows_curve.append([c, beta_c[c], n_c[c], goe_c[c], cv, medc[j],
                               np.median(np.abs(dg_eta[idx, j])),
                               100 * np.median(dg_eta[idx, j]),
                               100 * np.median(dg_eta[idx, j] * ETA_TRUE / (goe_c[c] * ETA_TRUE)) if goe_c[c] > 0 else np.nan,
                               100 * np.median(xr999[idx, j]),
                               100 * np.quantile(dg_eta[idx, j] * ETA_TRUE / (goe_c[c] * ETA_TRUE), 0.10) if goe_c[c] > 0 else np.nan,
                               float(np.exp(np.median(lnb[idx, j])))])
        jstar = int(np.argmin(medc)); cstar = float(C_GRID[jstar])
        flat = C_GRID[medc <= 1.05 * medc[jstar]]
        # bootstrap CI for c*
        bs = []
        for _ in range(nboot):
            ii = rngB.choice(idx, idx.size, replace=True)
            bs.append(C_GRID[int(np.argmin(np.median(comp[ii], axis=0)))])
        lo, hi = np.quantile(bs, [0.025, 0.975])
        rows_cstar.append([c, beta_c[c], n_c[c], goe_c[c], cstar, lo, hi,
                           float(flat.min()), float(flat.max()),
                           cstar * sv_c[c], medc[jstar]])
        # 一致性：各度量自身的最优 c
        cons = {"composite": cstar,
                "gamma": float(C_GRID[int(np.argmin(np.median(np.abs(dg_eta[idx]), axis=0)))]),
                "beta": float(C_GRID[int(np.argmin(np.median(lnb[idx] ** 2, axis=0)))]),
                "eta": float(C_GRID[int(np.argmin(np.median(lnh[idx] ** 2, axis=0)))]),
                "xr999": float(C_GRID[int(np.argmin(np.median(np.abs(xr999[idx]), axis=0)))])}
        rows_cons.append([c, beta_c[c], n_c[c]] + list(cons.values())
                         + [max(cons.values()) - min(cons.values())])
    df_curve = pd.DataFrame(rows_curve, columns=["cell", "beta", "n", "goe", "c", "med_comp",
                                                 "mdae_gamma_over_eta", "med_dgam_over_eta_pct",
                                                 "med_dgam_rel_pct",
                                                 "med_xr999_pct", "q10_dgam_rel_pct",
                                                 "med_betahat_over_beta"])
    df_curve.to_csv(tabdir / "error_vs_c.csv", index=False)
    df_cstar = pd.DataFrame(rows_cstar, columns=["cell", "beta", "n", "goe", "c_star", "c_star_lo",
                                                 "c_star_hi", "flat_lo", "flat_hi", "delta_star", "med_comp_at_star"])
    df_cstar.to_csv(tabdir / "cstar_table.csv", index=False)
    df_cons = pd.DataFrame(rows_cons, columns=["cell", "beta", "n", "c_composite", "c_gamma",
                                               "c_beta", "c_eta", "c_xr999", "max_gap"])
    df_cons.to_csv(tabdir / "consistency.csv", index=False)

    # 标度律（β≥1.5 主网格）
    m = df_cstar["cell"].isin(main_cells) & (df_cstar["beta"] >= LAW_BETA_MIN)
    X = np.column_stack([np.ones(m.sum()), np.log(df_cstar.loc[m, "beta"]), np.log(df_cstar.loc[m, "n"])])
    y = np.log(df_cstar.loc[m, "c_star"])
    coef, *_ = np.linalg.lstsq(X, y, rcond=None)
    yhat = X @ coef
    law = {"a": float(coef[0]), "b_lnbeta": float(coef[1]), "d_lnn": float(coef[2]),
           "r2": float(1 - np.sum((y - yhat) ** 2) / np.sum((y - y.mean()) ** 2))}

    # ---------- 2) 方案比较（含两种协议）----------
    folds = np.zeros(N, np.int8)
    for c in cells.index:                       # 按格内分5折
        idx = cell_rows[c]
        folds[idx] = rngB.permutation(idx.size) % 5
    sv_cell_i_pre = cells["sv"].values[cid]

    # 固定 δ=0.1 基线：与所有策略共用同一插值算子（避免算子不对称）；
    # c 评估下限截到首个非零网格点，避开 c=0 灾难列对线性插值的污染
    C_EVAL_LO = float(C_GRID[1])
    Lbase = _interp_rows(comp, np.clip(DELTA_BASE / sv_cell_i_pre, C_EVAL_LO, C_GRID[-1]))
    base_med = {c: float(np.median(Lbase[cell_rows[c]])) for c in cells.index}

    sv0_i = np.exp(feats[:, FEATURE_NAMES.index("ln_sv0")])
    sv_cell_i = sv_cell_i_pre
    n_i = cells["n"].values[cid].astype(float)

    def eval_policy_ceval(c_eval):
        ce = np.clip(c_eval, C_EVAL_LO, C_GRID[-1])
        L = _interp_rows(comp, ce)
        X999 = _interp_rows(xr999, ce)
        DG = _interp_rows(dg_eta, ce)
        return L, X999, DG

    policies = {}
    # 全局 c —— 真β协议（报告口径，作参考线；部署期不可得）
    policies["global_c_truebeta"] = eval_policy_ceval(np.full(N, GLOBAL_C))
    # 全局 c —— 朴素部署（δ=0.21·s_v(β̂₀,n)；保留以量化"β̂–偏移纠缠"的代价）
    policies["global_c_deploy_naive"] = eval_policy_ceval(GLOBAL_C * sv0_i / sv_cell_i)
    # 最优固定 δ —— 零信息、完全可部署的基线（单一原始 δ，训练折调优）
    delta_cand = np.geomspace(0.02, 0.8, 40)
    c_eval = np.zeros(N)
    best_fixed = []
    for f in range(5):
        trm = folds != f
        base_tr = {c: float(np.median(Lbase[cell_rows[c][folds[cell_rows[c]] != f]]))
                   for c in main_cells}
        bestr, bestd = np.inf, float(delta_cand[0])
        for d in delta_cand:
            L = _interp_rows(comp, np.clip(d / sv_cell_i, C_EVAL_LO, C_GRID[-1]))
            med = {c: float(np.median(L[(cid == c) & trm])) for c in main_cells}
            r = _grid_ratio(med, base_tr, main_cells)
            if r < bestr:
                bestr, bestd = r, float(d)
        best_fixed.append(round(bestd, 4))
        c_eval[folds == f] = bestd / sv_cell_i[folds == f]
    policies["best_fixed_delta"] = eval_policy_ceval(c_eval)
    # 按 n 调优固定 δ（n 完全可观测；不依赖 β̂ 的最强简单部署）
    c_eval = np.zeros(N)
    bf_per_n = {}
    for f in range(5):
        for nval in sorted({int(n_c[c]) for c in main_cells}):
            cells_n = [c for c in main_cells if n_c[c] == nval]
            rows_n = np.concatenate([cell_rows[c] for c in cells_n])
            trn = rows_n[folds[rows_n] != f]
            base_tr = {c: float(np.median(Lbase[np.intersect1d(cell_rows[c], trn)]))
                       for c in cells_n}
            bestr, bestd = np.inf, DELTA_BASE
            for d in delta_cand:
                L = _interp_rows(comp[trn], np.clip(d / sv_cell_i[trn], C_EVAL_LO, C_GRID[-1]))
                med = {c: float(np.median(L[cid[trn] == c])) for c in cells_n}
                r = float(np.median([med[c] / base_tr[c] for c in cells_n]))
                if r < bestr:
                    bestr, bestd = r, float(d)
            sel = (folds == f) & np.isin(cid, cells_n)
            c_eval[sel] = bestd / sv_cell_i[sel]
            bf_per_n[f"fold{f}_n{nval}"] = round(bestd, 3)
    policies["fixed_delta_per_n"] = eval_policy_ceval(c_eval)
    # 按格调优（真(β,n)，交叉验证防自适应乐观；(β,n) 信息路线的上界参考）
    c_eval = np.zeros(N)
    for f in range(5):
        te = folds == f
        for c in cells.index:
            tr = cell_rows[c][folds[cell_rows[c]] != f]
            cs = C_GRID[int(np.argmin(np.median(comp[tr], axis=0)))]
            sel = te & (cid == c)
            c_eval[sel] = cs
    policies["table_true_cv"] = eval_policy_ceval(c_eval)
    # 逐样本 oracle（含运气成分的上界）
    jmin = np.argmin(comp, axis=1)
    policies["oracle"] = (comp[np.arange(N), jmin], xr999[np.arange(N), jmin],
                          dg_eta[np.arange(N), jmin])
    c_star_i = C_GRID[jmin].astype(np.float64)

    # ---------- 3) 试点：特征 → 原始偏移 δ（端到端，不经 s_v(β̂) 乘性换算）----------
    lmin = comp[np.arange(N), jmin]
    Temp = 0.25 * (np.percentile(comp, 40, axis=1) - lmin) + 1e-9
    Wt = np.exp(-(comp - lmin[:, None]) / Temp[:, None])
    c_soft_i = (Wt * C_GRID[None, :]).sum(1) / Wt.sum(1)
    DELTA_FLOOR = 0.004
    y_star = np.log(np.maximum(c_star_i * sv_cell_i, DELTA_FLOOR))   # 目标=ln δ*
    y_soft = np.log(np.maximum(c_soft_i * sv_cell_i, DELTA_FLOOR))   # 软目标（平坦谷稳健）

    have_skl = False
    if not args.no_tree:
        try:
            from sklearn.ensemble import HistGradientBoostingRegressor
            have_skl = True
        except Exception:
            have_skl = False

    def crossfit(cols, target, model="ridge", Xmat=None, names=None):
        if Xmat is None:
            Xmat, names = feats, FEATURE_NAMES
        Xall = Xmat if cols is None else Xmat[:, [names.index(f) for f in cols]]
        pred = np.zeros(N)
        for f in range(5):
            tr, te = folds != f, folds == f
            if model == "ridge":
                pred[te] = _ridge_fit_predict(Xall[tr], target[tr], Xall[te])
            else:
                gb = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08,
                                                   random_state=args.seed)
                gb.fit(Xall[tr], target[tr]); pred[te] = gb.predict(Xall[te])
        return pred

    def to_ceval(ln_delta_pred, guard=None):
        dhat = np.exp(ln_delta_pred)
        if guard is not None:               # 护栏：δ̂ 限到 [lo,hi]·s_v(β̂₀,n)（仅作截断，不作乘子）
            dhat = np.clip(dhat, guard[0] * sv0_i, guard[1] * sv0_i)
        return dhat / sv_cell_i             # 仅作为读取存档曲线的索引变换

    probe_runs = {}
    for gname, cols in FEATURE_GROUPS.items():
        probe_runs[f"ridge_{gname}"] = to_ceval(crossfit(cols, y_star, "ridge"))
    probe_runs["ridge_D_softtarget"] = to_ceval(crossfit(FEATURE_NAMES, y_soft, "ridge"))
    if have_skl:
        probe_runs["tree_D_full"] = to_ceval(crossfit(FEATURE_NAMES, y_star, "tree"))
        pred_soft = crossfit(FEATURE_NAMES, y_soft, "tree")
        probe_runs["tree_D_softtarget"] = to_ceval(pred_soft)
        probe_runs["tree_D_soft_guardrail"] = to_ceval(pred_soft, guard=(0.08, 0.45))
    # E 组：多偏移读出特征 —— 同一廓线上在多个原始 δ 处读 β̂ 与 γ̂（部署期免费的根查找），
    # 用 β̂(δ) 的衰减形态反推真 β，正面攻击"β̂–偏移纠缠"瓶颈
    READ_DELTAS = [0.05, 0.10, 0.20, 0.40]
    beta_true_i = cells["beta"].values[cid].astype(float)
    gamma_true_i = cells["goe"].values[cid].astype(float) * ETA_TRUE
    Rspan = np.nanmax(z["t"], axis=1) - np.nanmin(z["t"], axis=1)
    extE, namesE = [], []
    for dv in READ_DELTAS:
        cev = np.clip(dv / sv_cell_i, C_EVAL_LO, C_GRID[-1])
        extE.append(_interp_rows(lnb, cev) + np.log(beta_true_i))   # 可观测量 ln β̂(δ) 的重构
        namesE.append(f"ln_betahat_d{dv}")
    cev_lo = np.clip(READ_DELTAS[0] / sv_cell_i, C_EVAL_LO, C_GRID[-1])
    cev_hi = np.clip(READ_DELTAS[-1] / sv_cell_i, C_EVAL_LO, C_GRID[-1])
    g_lo = gamma_true_i + ETA_TRUE * _interp_rows(dg_eta, cev_lo)   # 可观测量 γ̂(δ) 的重构
    g_hi = gamma_true_i + ETA_TRUE * _interp_rows(dg_eta, cev_hi)
    extE.append(np.log(np.maximum((g_hi - g_lo) / np.maximum(Rspan, 1e-12), 1e-9)))
    namesE.append("ln_wallwidth_rawdelta")
    featsE = np.column_stack([feats] + extE)
    namesEall = FEATURE_NAMES + namesE
    probe_runs["ridge_E_multidelta"] = to_ceval(crossfit(None, y_soft, "ridge", featsE, namesEall))
    if have_skl:
        probe_runs["tree_E_multidelta_soft"] = to_ceval(crossfit(None, y_soft, "tree", featsE, namesEall))
        probe_runs["tree_E_multidelta_star"] = to_ceval(crossfit(None, y_star, "tree", featsE, namesEall))
    for k, ce in probe_runs.items():
        policies[f"probe_{k}"] = eval_policy_ceval(ce)
    # 诊断探针（作弊特征 ln β_true）：定位瓶颈在"特征信息量"还是"模型容量/目标噪声"；
    # 不参与方案选择与 ρ̂，仅作为学习化一节特征设计的依据
    if have_skl:
        feats_diag = np.column_stack([feats, np.log(cells["beta"].values[cid].astype(float))])
        pred = np.zeros(N)
        for f in range(5):
            tr, te = folds != f, folds == f
            gb = HistGradientBoostingRegressor(max_iter=300, learning_rate=0.08,
                                               random_state=args.seed)
            gb.fit(feats_diag[tr], y_soft[tr]); pred[te] = gb.predict(feats_diag[te])
        policies["probe_DIAG_tree_truebeta"] = eval_policy_ceval(np.exp(pred) / sv_cell_i)

    # ---------- 4) 比值汇总 + ρ̂ + bootstrap CI ----------
    def ratios_from(Lvec):
        med = {c: float(np.median(Lvec[cell_rows[c]])) for c in main_cells}
        return _grid_ratio(med, base_med, main_cells)

    summary_sch = {"fixed_0.1": 1.0}
    for k, (L, _, _) in policies.items():
        summary_sch[k] = round(ratios_from(L), 4)
    best_probe = min((k for k in summary_sch if k.startswith("probe_") and "DIAG" not in k),
                     key=lambda k: summary_sch[k])
    r_tab, r_orc, r_pro = summary_sch["table_true_cv"], summary_sch["oracle"], summary_sch[best_probe]
    rho = (r_tab - r_pro) / (r_tab - r_orc)
    r_dep = min(1.0, summary_sch["best_fixed_delta"], summary_sch["fixed_delta_per_n"])
    rho_dep = (r_dep - r_pro) / max(r_dep - r_orc, 1e-9)

    # 簇 bootstrap（格内重采样）—— ρ̂ 与关键比值的 CI
    keys_ci = ["best_fixed_delta", "fixed_delta_per_n", "global_c_truebeta",
               "table_true_cv", best_probe, "oracle"]
    boots = {k: [] for k in keys_ci}; boots["rho"] = []; boots["rho_deploy"] = []
    for _ in range(nboot):
        ridx = np.concatenate([rngB.choice(cell_rows[c], cell_rows[c].size, replace=True)
                               for c in main_cells])
        cid_b = cid[ridx]
        base_b = {c: float(np.median(Lbase[ridx[cid_b == c]])) for c in main_cells}
        vals = {}
        for k in keys_ci:
            L = policies[k][0][ridx]
            med = {c: float(np.median(L[cid_b == c])) for c in main_cells}
            vals[k] = _grid_ratio(med, base_b, main_cells)
            boots[k].append(vals[k])
        boots["rho"].append((vals["table_true_cv"] - vals[best_probe])
                            / max(vals["table_true_cv"] - vals["oracle"], 1e-9))
        rd = min(1.0, vals["best_fixed_delta"], vals["fixed_delta_per_n"])
        boots["rho_deploy"].append((rd - vals[best_probe]) / max(rd - vals["oracle"], 1e-9))
    ci = {k: [round(float(np.quantile(v, 0.025)), 4), round(float(np.quantile(v, 0.975)), 4)]
          for k, v in boots.items()}

    # ---------- 5) 安全边界 / 不变性 / 表格输出 ----------
    j021 = int(np.argmin(np.abs(C_GRID - GLOBAL_C)))
    main_idx = np.concatenate([cell_rows[c] for c in main_cells])
    gmt = cells["goe"].values[cid] * ETA_TRUE
    dgrel = dg_eta * ETA_TRUE / np.where(gmt[:, None] > 0, gmt[:, None], np.nan)
    safety = {
        "at_c0.21": {"med_dgam_rel_pct": round(100 * float(np.nanmedian(dgrel[main_idx, j021])), 2),
                     "med_dgam_over_eta_pct": round(100 * float(np.median(dg_eta[main_idx, j021])), 2),
                     "med_xr999_pct": round(100 * float(np.median(xr999[main_idx, j021])), 2),
                     "q10_dgam_rel_pct": round(100 * float(np.nanquantile(dgrel[main_idx, j021], 0.10)), 2)},
        "at_delta0.1": {"med_dgam_rel_pct": round(100 * float(np.nanmedian(base01[main_idx, 4] * ETA_TRUE / gmt[main_idx])), 2),
                        "med_dgam_over_eta_pct": round(100 * float(np.median(base01[main_idx, 4])), 2),
                        "med_xr999_pct": round(100 * float(np.median(base01[main_idx, 7])), 2)},
    }
    inv = df_curve[~df_curve["cell"].isin(main_cells) | ((df_curve["beta"] == 2.0) & (df_curve["n"] == 10))]
    inv.to_csv(tabdir / "invariance_goe.csv", index=False)

    sv_tab = pd.DataFrame({f"n={n}": [sv_value(b, n) for b in BETAS] for n in NS},
                          index=[f"beta={b}" for b in BETAS]).round(4)
    sv_tab.to_csv(tabdir / "sv_table.csv")
    dstar = df_cstar[df_cstar["cell"].isin(main_cells)].pivot(index="beta", columns="n", values="delta_star").round(3)
    dstar.to_csv(tabdir / "delta_star_table.csv")

    summary = {
        "config": json.loads((outdir / "config.json").read_text()),
        "sv_check": cmd_verify(argparse.Namespace()),
        "n_samples_main_grid": int(main_idx.size),
        "scheme_ratio_vs_fixed0.1_gridmedian": summary_sch,
        "scheme_ratio_CI95": ci,
        "rho_hat": {"definition": "(r_ref - r_bestProbe)/(r_ref - r_oracle)",
                    "best_probe": best_probe,
                    "vs_table_true": {"value": round(float(rho), 4), "CI95": ci["rho"]},
                    "vs_deployable_simple": {"value": round(float(rho_dep), 4),
                                             "CI95": ci["rho_deploy"],
                                             "ref_ratio": round(float(r_dep), 4)},
                    "all_probes": {k: v for k, v in summary_sch.items() if k.startswith("probe_")}},
        "cstar_summary": {"band_beta_ge_1.5": [round(float(df_cstar.loc[m, "c_star"].min()), 3),
                                               round(float(df_cstar.loc[m, "c_star"].max()), 3)],
                          "scaling_law": {k: round(v, 4) for k, v in law.items()}},
        "consistency_maxgap_gridmedian": round(float(df_cons.loc[df_cons["cell"].isin(main_cells), "max_gap"].median()), 4),
        "safety": safety,
        "entanglement_med_betahat_over_beta_at_c0.21": {
            f"beta={b}": round(float(np.exp(np.median(
                lnb[np.concatenate([cell_rows[c] for c in main_cells if beta_c[c] == b]), j021]))), 3)
            for b in BETAS},
        "best_fixed_delta_by_fold": best_fixed,
        "fixed_delta_per_n_choices": bf_per_n,
        "flags": {"wall_rate": round(float((z["cflag"] == 1).mean()), 4),
                  "left_edge_rate_at_c0": round(float((z["cflag"][:, 0] == 2).mean()), 4),
                  "interp_fidelity_fixed01_max_cell_relgap": round(max(
                      abs(float(np.median(Lbase[cell_rows[c]]))
                          / float(np.median(base01[cell_rows[c], 3])) - 1.0)
                      for c in main_cells), 4)},
        "runtime_analyze_sec": round(time.time() - t0, 1),
        "tree_probe_used": bool(have_skl),
    }
    (outdir / "summary_report.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2))
    print(json.dumps(summary["scheme_ratio_vs_fixed0.1_gridmedian"], indent=2, ensure_ascii=False))
    rh = summary["rho_hat"]
    print(f"\nρ̂(对按格调优) = {rh['vs_table_true']['value']}  CI95={rh['vs_table_true']['CI95']}")
    print(f"ρ̂(对可部署基线) = {rh['vs_deployable_simple']['value']}  "
          f"CI95={rh['vs_deployable_simple']['CI95']}  (best={best_probe})")
    print(f"analyze 完成（{time.time()-t0:.1f}s）→ {outdir}/summary_report.json 与 tables/*.csv")


# ----------------------------- main -----------------------------

def main():
    p = argparse.ArgumentParser(description="MDM 偏移量研究：数据生成 + 分析 + 试点")
    p.add_argument("command", choices=["verify", "simulate", "analyze", "all"])
    p.add_argument("--outdir", default="mdm_out")
    p.add_argument("--reps", type=int, default=800)
    p.add_argument("--seed", type=int, default=20260610)
    p.add_argument("--nbeta", type=int, default=261)
    p.add_argument("--beta-min", type=float, default=0.10)
    p.add_argument("--beta-max", type=float, default=20.0)
    p.add_argument("--ngamma", type=int, default=700)
    p.add_argument("--eta-hat", choices=["mean", "median"], default="mean")
    p.add_argument("--nboot", type=int, default=300)
    p.add_argument("--no-tree", action="store_true", help="禁用 sklearn 树探针")
    p.add_argument("--quick", action="store_true", help="冒烟测试：reps=80, nboot=100")
    args = p.parse_args()
    if args.quick:
        args.reps, args.nboot = 80, 100
    if args.command == "verify":
        cmd_verify(args)
    elif args.command == "simulate":
        cmd_simulate(args)
    elif args.command == "analyze":
        cmd_analyze(args)
    else:
        cmd_simulate(args); cmd_analyze(args)


if __name__ == "__main__":
    main()
