"""Study/02 S3 分析：跨目标矩阵 / 目标摘要 / 每目标敏感度与精确补偿 / 容量 / 插值。

只读证据（不训练）。输入：
  - S1 封存：artifacts/pq_iid_main/evidence（P + Q0.95，各 60 fits）+ analysis/summary_iid.json
  - E1：artifacts/pq_s3_target/evidence（Q0.90 + Q0.99，各 60 fits）
  - E2：artifacts/pq_s3_capacity/evidence（P/Q × sm64/lg512，folds {1,3}）
  - E3：artifacts/pq_s3_interp/evidence（120 基线重训）+ interp/*.npz（中点样本评价）

输出（各根 analysis/）：
  target:  cross_target_matrix.json / target_summary.json / sensitivity_by_target.json
           / mechanism_exact_by_target.json
  capacity: capacity_summary.json
  interp:   interp_summary.json

estimand（E1/E3 与 S1 相同）：配对模型级平方相对误差 d_{n,f,s} = mean_样本(rel_sq_Q − rel_sq_P)，
设计级 fold×seed 交叉 bootstrap（evaluate.primary_design_bootstrap，rng 20260805 与 S1/S2 同源）。
E2 为两折设计：只报效应量与分层描述方向，不做正式显著性主张。

用法（PQ_PROTOCOL=iid-v1，cwd=code/）：
    python -m study02pq.s3_analyze --n-boot 200000
    python -m study02pq.s3_analyze --n-boot 2000        # smoke/测试
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

import numpy as np

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

from study02pq import config as CFG  # noqa: E402
from study02pq import evaluate as EVAL  # noqa: E402
from study02pq import mechanism as MECH  # noqa: E402

assert CFG.PROTOCOL_VERSION == "iid-v1", "s3_analyze 必须在 PQ_PROTOCOL=iid-v1 下运行"

S1_ROOT = os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_iid_main")
ROOT_TARGET = os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_s3_target")
ROOT_CAP = os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_s3_capacity")
ROOT_INTERP = os.path.join(CFG.STUDY02_ROOT, "artifacts", "pq_s3_interp")

TARGETS = [float(p) for p in (0.90, 0.95, 0.99)]
BOUNDARY_THRESHOLD = 0.9999
BOOT_RNG = np.random.default_rng(20260805)  # 与 S1 主推断 / S2 描述性区间同源 rng

S3_CFG_PATH = os.path.join(CFG.STUDY02_ROOT, "configs", "pq-s3-boundary-v1.json")
with open(S3_CFG_PATH, encoding="utf-8") as _f:
    S3CFG = json.load(_f)


def fit_id(n, fold_idx, seed, route, suffix=""):
    return f"n{n}_f{fold_idx + 1}_s{seed}_r{route}{suffix}"


def _npz(root: str, fit: str) -> dict:
    d = np.load(os.path.join(root, "evidence", f"{fit}.npz"))
    return {k: d[k] for k in d.files}


def _keys(ev: dict) -> dict:
    return {k: ev[k] for k in ("keys_beta", "keys_gamma_over_eta", "keys_n",
                               "keys_repeat_id")}


def _keys_equal(a: dict, b: dict) -> bool:
    for k in ("keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id"):
        if not np.array_equal(a[k], b[k]):
            return False
    return True


def _x_p_hat(ev: dict, p: float, eta_true: float = CFG.ETA) -> np.ndarray:
    b = ev["beta_hat"].astype(np.float64)
    e = ev["eta_hat"].astype(np.float64)
    g = ev["gamma_hat"].astype(np.float64)
    return g + e * (-np.log(float(p))) ** (1.0 / b)


def _x_p_true(ev: dict, p: float, eta_true: float = CFG.ETA) -> np.ndarray:
    b = ev["keys_beta"].astype(np.float64)
    goe = ev["keys_gamma_over_eta"].astype(np.float64)
    g = goe * eta_true
    return g + eta_true * (-np.log(float(p))) ** (1.0 / b)


def rel_err_at_p(ev: dict, p: float) -> np.ndarray:
    xh = _x_p_hat(ev, p)
    xt = _x_p_true(ev, p)
    return (xh - xt) / xt


def rel_sq_at_p(ev: dict, p: float) -> np.ndarray:
    return rel_err_at_p(ev, p) ** 2


def rrmse_of(rel_sq: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(rel_sq, dtype=np.float64))))


def _load_meta_row(root: str, fit: str) -> dict:
    with open(os.path.join(root, "fit_metadata", f"{fit}.json"), encoding="utf-8") as f:
        return json.load(f)


def _failures(root: str, fits: list[str]) -> dict:
    return EVAL.count_failures([_load_meta_row(root, f) for f in fits])


def _boundary_counts(evs: list[dict]) -> dict:
    n_rows, n_b = 0, 0
    for ev in evs:
        g = ev["gamma_hat"].astype(np.float64)
        m = ev["min_x"].astype(np.float64)
        n_rows += int(len(g))
        n_b += int(np.sum(g / m >= BOUNDARY_THRESHOLD))
    return {"n_rows": n_rows, "n_boundary": n_b,
            "boundary_share": float(n_b / n_rows) if n_rows else 0.0}


def _cells(evs_by_route: dict, p: float, seeds: list[int]) -> dict:
    """{n: {fold_idx: [d_s ...]}}：Qp vs P 在目标 p 的模型级配对差值。"""
    rq = f"Q{int(round(p*100))}"
    out = {}
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            arr = []
            for seed in seeds:
                k = (n, fold_idx, seed)
                ep, eq = evs_by_route["P"][k], evs_by_route[rq][k]
                assert _keys_equal(ep, eq), f"keys mismatch at p={p} {k}"
                arr.append(float(np.mean(rel_sq_at_p(eq, p) - rel_sq_at_p(ep, p))))
            out.setdefault(n, {})[fold_idx] = arr
    return out


def _bootstrap(cell_diffs: dict, n_boot: int) -> dict:
    prim = EVAL.primary_design_bootstrap(cell_diffs, n_boot=n_boot, level=0.95,
                                         rng=BOOT_RNG)
    return {
        "pooled_mean": prim["pooled_mean"],
        "ci_lo": prim["pooled_ci_lo"], "ci_hi": prim["pooled_ci_hi"],
        "per_n_mean": {str(n): prim["per_n_mean"][n] for n in prim["per_n_mean"]},
        "per_n_ci_lo": {str(n): prim["per_n_ci_lo"][n] for n in prim["per_n_ci_lo"]},
        "per_n_ci_hi": {str(n): prim["per_n_ci_hi"][n] for n in prim["per_n_ci_hi"]},
        "n_boot": int(n_boot), "level": 0.95,
        "resampling": prim["resampling"],
    }


def _cell_direction(evs_by_route: dict, p: float, seeds: list[int]) -> dict:
    rq = f"Q{int(round(p*100))}"
    pos = neg = zero = 0
    per_n = {}
    for n in CFG.N_GRID:
        pn = nn = 0
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                k = (n, fold_idx, seed)
                ep, eq = evs_by_route["P"][k], evs_by_route[rq][k]
                d = float(np.mean(rel_sq_at_p(eq, p) - rel_sq_at_p(ep, p)))
                if d > 0:
                    pos += 1; pn += 1
                elif d < 0:
                    neg += 1; nn += 1
                else:
                    zero += 1
        per_n[str(n)] = {"n_pos": pn, "n_neg": nn}
    return {"n_pos_cells": pos, "n_neg_cells": neg, "n_zero_cells": zero,
            "per_n": per_n}


# ----------------------------------------------------------------------
# E1 目标分析（写入 ROOT_TARGET/analysis）
# ----------------------------------------------------------------------

def load_e1(seeds) -> dict:
    """routes = {P, Q95(S1), Q90, Q99(target)} → {route: {(n,f,s): ev}}。"""
    evs = {"P": {}, "Q95": {}, "Q90": {}, "Q99": {}}
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                k = (n, fold_idx, seed)
                evs["P"][k] = _npz(S1_ROOT, fit_id(n, fold_idx, seed, "P"))
                evs["Q95"][k] = _npz(S1_ROOT, fit_id(n, fold_idx, seed, "Q"))
                evs["Q90"][k] = _npz(ROOT_TARGET, fit_id(n, fold_idx, seed, "Q90"))
                evs["Q99"][k] = _npz(ROOT_TARGET, fit_id(n, fold_idx, seed, "Q99"))
                for r2 in ("Q95", "Q90", "Q99"):
                    assert _keys_equal(evs["P"][k], evs[r2][k]), f"E1 keys mismatch {k} {r2}"
    return evs


def analyze_e1(seeds, n_boot):
    evs = load_e1(seeds)

    # ---- 交叉目标矩阵：pooled rRMSE per (route, p) ----
    routes = ["P", "Q95", "Q90", "Q99"]
    pooled = {r: {} for r in routes}
    for r in routes:
        for p in TARGETS:
            rel_sq = np.concatenate([rel_sq_at_p(ev, p) for ev in evs[r].values()])
            pooled[r][str(p)] = rrmse_of(rel_sq)
    matrix = {
        "routes": routes, "targets": [str(p) for p in TARGETS],
        "pooled_rrmse": pooled,
        "rel_change_vs_P_percent": {
            r: {str(p): (pooled[r][str(p)] - pooled["P"][str(p)])
                / pooled["P"][str(p)] * 100.0 for p in TARGETS}
            for r in routes if r != "P"},
        "x_p_definition": "x_p = gamma + eta*(-ln p)^(1/beta) with R(x_p)=p RELIABILITY "
                          "(survival); not a CDF p-quantile",
        "note": "all routes evaluated at all three levels analytically from stored hats + "
                "true keys; Q routes trained only at their own level",
    }

    # ---- 目标摘要：Qp vs P at p ----
    target_summary = {}
    sealed = {}
    sealed_path = os.path.join(S1_ROOT, "analysis", "summary_iid.json")
    if os.path.isfile(sealed_path):
        with open(sealed_path, encoding="utf-8") as f:
            sealed = json.load(f)
    for p in TARGETS:
        rq = f"Q{int(round(p*100))}"
        cell_diffs = _cells(evs, p, seeds)
        bs = _bootstrap(cell_diffs, n_boot)
        p_rr = rrmse_of(np.concatenate([rel_sq_at_p(ev, p) for ev in evs["P"].values()]))
        q_rr = rrmse_of(np.concatenate([rel_sq_at_p(ev, p) for ev in evs[rq].values()]))
        entry = {
            "target_level": p,
            "confirmatory_note": ("x0.95 reproduces the sealed S1 main result (consistency "
                                  "check); x0.90/x0.99 are prespecified robustness results "
                                  "with effect sizes and design-level intervals, NOT a "
                                  "familywise significance claim"),
            "pooled_rrmse": {"P": p_rr, rq: q_rr},
            "rel_change_percent": (q_rr - p_rr) / p_rr * 100.0,
            "bootstrap": bs,
            "direction_by_cell": _cell_direction(evs, p, seeds),
            "failures_target_route": _failures(
                # Q95 证据封存在 S1（pq_iid_main，fit_id rQ）；Q90/Q99 在 target 根（rQ90/rQ99）
                S1_ROOT if rq == "Q95" else ROOT_TARGET,
                [fit_id(n, f, s, "Q" if rq == "Q95" else rq)
                 for n in CFG.N_GRID for f in range(CFG.N_FOLDS)
                 for s in seeds]),
            "boundary_counts": _boundary_counts(list(evs[rq].values())),
        }
        if p == 0.95 and sealed:
            s1p = sealed.get("pooled", {})
            entry["s1_sealed_cross_check"] = {
                "sealed_p_rrmse": s1p.get("p_rrmse"), "sealed_q_rrmse": s1p.get("q_rrmse"),
                "recomputed_p_rrmse": p_rr, "recomputed_q_rrmse": q_rr,
                "match_within_1e6": bool(np.isclose(p_rr, s1p.get("p_rrmse"),
                                                    rtol=1e-6, atol=1e-9)
                                         and np.isclose(q_rr, s1p.get("q_rrmse"),
                                                        rtol=1e-6, atol=1e-9)),
            }
        target_summary[str(p)] = entry

    # ---- 每目标敏感度范数 ||s|| 与区域 Q-P 目标误差差（探索性） ----
    sens = {}
    for p in TARGETS:
        rq = f"Q{int(round(p*100))}"
        # 区域 mean ||s||（只依赖真值参数 → P/Q 同值；逐行掩码平均）
        sp_all = [MECH.row_mechanism(ev, R=p) for ev in evs["P"].values()]
        s_beta, s_goe = {}, {}
        for r in sp_all:
            for b in np.unique(r["beta"]):
                m = r["beta"] == b
                s_beta.setdefault(float(b), []).extend(r["s_norm"][m].tolist())
            for g in np.unique(r["goe"]):
                m = r["goe"] == g
                s_goe.setdefault(float(g), []).extend(r["s_norm"][m].tolist())
        s_beta = {b: float(np.mean(v)) for b, v in s_beta.items()}
        s_goe = {g: float(np.mean(v)) for g, v in s_goe.items()}
        # 区域 rms 差（Qp 在 p 处 − P 在 p 处）
        values_beta = sorted(s_beta)
        values_goe = sorted(s_goe)
        region_delta = {"beta": {}, "gamma_over_eta": {}, "n": {}}
        for rtype, col, values in (
                ("beta", "keys_beta", values_beta),
                ("gamma_over_eta", "keys_gamma_over_eta", values_goe),
                ("n", "keys_n", [float(n) for n in CFG.N_GRID])):
            for v in values:
                rp_all, rq_all = [], []
                for k in evs["P"]:
                    ep, eq = evs["P"][k], evs[rq][k]
                    mp = ep[col].astype(np.float64) == v
                    assert np.array_equal(mp, eq[col].astype(np.float64) == v)
                    rp_all.append(rel_sq_at_p(ep, p)[mp])
                    rq_all.append(rel_sq_at_p(eq, p)[mp])
                region_delta[rtype][v] = (rrmse_of(np.concatenate(rq_all))
                                          - rrmse_of(np.concatenate(rp_all)))
        corr = {"beta": MECH._corr([s_beta[v] for v in values_beta],
                                   [region_delta["beta"][v] for v in values_beta]),
                "gamma_over_eta": MECH._corr([s_goe[v] for v in values_goe],
                                             [region_delta["gamma_over_eta"][v]
                                              for v in values_goe]),
                "n": None}
        sens[str(p)] = {
            "target_level": p,
            "mean_s_norm_by_region": {"beta": s_beta, "gamma_over_eta": s_goe},
            "delta_rms_actual_at_p_by_region": region_delta,
            "corr_mean_s_norm_delta_rms_actual": corr,
            "note": ("exploratory association over a handful of bins (8 beta, 5 goe, 4 n); "
                     "||s|| depends only on true params so the n-correlation is undefined "
                     "by construction; no causal claim"),
        }

    # ---- 每目标精确补偿 + 离目标退化（S2 精确分解，R=p） ----
    mech = {}
    for p in TARGETS:
        rq = f"Q{int(round(p*100))}"
        sp_rows = [MECH.row_mechanism(ev, R=p) for ev in evs["P"].values()]
        sq_rows = [MECH.row_mechanism(ev, R=p) for ev in evs[rq].values()]
        sp_pool = MECH.pooled_stats(sp_rows)
        sq_pool = MECH.pooled_stats(sq_rows)

        def _ident_at_p(rows, evs_):
            c_sum = np.concatenate([r["C_beta"] + r["C_eta"] + r["C_gamma"]
                                    for r in rows])
            act = np.concatenate([rel_err_at_p(ev, p) for ev in evs_])
            return float(np.max(np.abs(act - c_sum)))

        stats_p, stats_q = {}, {}
        idx = 0
        for n in CFG.N_GRID:
            for fold_idx in range(CFG.N_FOLDS):
                for seed in seeds:
                    k = (n, fold_idx, seed)
                    stats_p[k] = MECH.cell_stats(sp_rows[idx])
                    stats_q[k] = MECH.cell_stats(sq_rows[idx])
                    idx += 1
        design = MECH.design_pair_deltas(stats_p, stats_q,
                                         ["mean_cancel_exact", "mean_s_norm"],
                                         n_boot=n_boot)
        off = {str(p2): rrmse_of(np.concatenate(
            [rel_sq_at_p(ev, p2) for ev in evs[rq].values()])) for p2 in TARGETS}
        diag = off[str(p)]
        mech[str(p)] = {
            "target_level": p,
            "pooled": {
                "P": {"mean_cancel_exact": sp_pool["mean_cancel_exact"],
                      "mean_s_norm": sp_pool["mean_s_norm"]},
                rq: {"mean_cancel_exact": sq_pool["mean_cancel_exact"],
                     "mean_s_norm": sq_pool["mean_s_norm"]},
            },
            "exact_identity_at_p": {"max_abs_err_P": _ident_at_p(sp_rows,
                                                                  evs["P"].values()),
                                    "max_abs_err_Q": _ident_at_p(sq_rows,
                                                                 evs[rq].values())},
            "design_pair_deltas": design,
            "off_target_degradation": {
                "rrmse_at_each_level": off,
                "diagonal_target": p,
                "off_minus_diag_percent": {
                    str(p2): (off[str(p2)] - diag) / diag * 100.0 for p2 in TARGETS},
            },
        }

    out = os.path.join(ROOT_TARGET, "analysis")
    os.makedirs(out, exist_ok=True)
    for name, obj in (("cross_target_matrix.json", matrix),
                      ("target_summary.json", target_summary),
                      ("sensitivity_by_target.json", sens),
                      ("mechanism_exact_by_target.json", mech)):
        with open(os.path.join(out, name), "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False, indent=1)
    return matrix, target_summary


# ----------------------------------------------------------------------
# E2 容量分析（写入 ROOT_CAP/analysis）——两折设计，只报方向
# ----------------------------------------------------------------------

def _count_params(hidden: tuple, n: int) -> int:
    prev, total = n, 0
    for h in hidden:
        total += prev * h + h
        prev = h
    total += prev * 3 + 3
    return total


def analyze_e2(seeds):
    caps = {"sm64": tuple(S3CFG["capacity"]["small"]),
            "lg512": tuple(S3CFG["capacity"]["large"]),
            "baseline": tuple(S3CFG["capacity"]["baseline"])}
    folds = [int(f) - 1 for f in S3CFG["capacity"]["folds_1based"]]
    out = {}
    for label, hidden in caps.items():
        root = S1_ROOT if label == "baseline" else ROOT_CAP
        suffix = "" if label == "baseline" else f"_{label}"
        evs_p, evs_q = {}, {}
        fits = []
        for n in CFG.N_GRID:
            for fold_idx in folds:
                for seed in seeds:
                    fp = fit_id(n, fold_idx, seed, "P", suffix)
                    fq = fit_id(n, fold_idx, seed, "Q", suffix)
                    ep, eq = _npz(root, fp), _npz(root, fq)
                    assert _keys_equal(ep, eq), f"E2 keys mismatch {fp}/{fq}"
                    evs_p[(n, fold_idx, seed)] = ep
                    evs_q[(n, fold_idx, seed)] = eq
                    fits += [fp, fq]
        p_rr = rrmse_of(np.concatenate([rel_sq_at_p(ev, 0.95) for ev in evs_p.values()]))
        q_rr = rrmse_of(np.concatenate([rel_sq_at_p(ev, 0.95) for ev in evs_q.values()]))
        per_n = {}
        for n in CFG.N_GRID:
            rp = np.concatenate([rel_sq_at_p(ev, 0.95) for (nn, f, s), ev in evs_p.items()
                                 if nn == n])
            rq = np.concatenate([rel_sq_at_p(ev, 0.95) for (nn, f, s), ev in evs_q.items()
                                 if nn == n])
            pr, qr = rrmse_of(rp), rrmse_of(rq)
            per_n[str(n)] = {"P": pr, "Q": qr,
                             "rel_change_percent": (qr - pr) / pr * 100.0}
        out[label] = {
            "hidden_layers": list(hidden),
            "n_params": {str(n): _count_params(hidden, n) for n in CFG.N_GRID},
            "folds_1based": [f + 1 for f in folds],
            "n_fits_each_route": len(evs_p),
            "pooled_rrmse": {"P": p_rr, "Q": q_rr},
            "rel_change_percent": (q_rr - p_rr) / p_rr * 100.0,
            "per_n": per_n,
            "n_pos_cells": sum(1 for (n, f, s), ep in evs_p.items()
                               if np.mean(rel_sq_at_p(evs_q[(n, f, s)], 0.95)
                                          - rel_sq_at_p(ep, 0.95)) > 0),
            "n_cells": len(evs_p),
            "failures": _failures(root, fits),
            "boundary_counts": _boundary_counts(list(evs_p.values())
                                                + list(evs_q.values())),
            "note": ("limited-fold robustness check (folds {1,3}); effect sizes and "
                     "direction only; no formal significance claim"),
        }
    adir = os.path.join(ROOT_CAP, "analysis")
    os.makedirs(adir, exist_ok=True)
    with open(os.path.join(adir, "capacity_summary.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


# ----------------------------------------------------------------------
# E3 插值分析（写入 ROOT_INTERP/analysis）
# ----------------------------------------------------------------------

def analyze_e3(seeds, n_boot):
    fits = [fit_id(n, f, s, r) for n in CFG.N_GRID
            for f in range(CFG.N_FOLDS) for s in seeds for r in ("P", "Q")]
    evs_p, evs_q = {}, {}
    ip_p, ip_q = {}, {}
    n_ident = 0
    for fit in fits:
        route = fit.rsplit("_", 1)[-1].lstrip("r").upper()
        sha_a = hashlib.sha256(open(os.path.join(ROOT_INTERP, "evidence", f"{fit}.npz"),
                                    "rb").read()).hexdigest()
        sha_b = hashlib.sha256(open(os.path.join(S1_ROOT, "evidence", f"{fit}.npz"),
                                    "rb").read()).hexdigest()
        n_ident += int(sha_a == sha_b)
        n = int(fit.split("n")[1].split("_")[0])
        fold_idx = int(fit.split("f")[1].split("_")[0]) - 1
        seed = int(fit.split("s")[1].split("_")[0])
        k = (n, fold_idx, seed)
        ev = _npz(ROOT_INTERP, fit)
        ip = np.load(os.path.join(ROOT_INTERP, "interp", f"{fit}.npz"))
        if route == "P":
            evs_p[k] = ev; ip_p[k] = ip
        else:
            evs_q[k] = ev; ip_q[k] = ip
    for k in evs_p:
        assert _keys_equal(evs_p[k], evs_q[k])
        for kk in ("keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id"):
            assert np.array_equal(ip_p[k][kk], ip_q[k][kk]), f"interp keys mismatch {k}"

    cell = {}
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            arr = []
            for seed in seeds:
                k = (n, fold_idx, seed)
                arr.append(float(np.mean(ip_q[k]["rel_err_sq"]
                                         - ip_p[k]["rel_err_sq"])))
            cell.setdefault(n, {})[fold_idx] = arr
    bs = _bootstrap(cell, n_boot)
    rel_p = np.concatenate([ip_p[k]["rel_err_sq"] for k in ip_p])
    rel_q = np.concatenate([ip_q[k]["rel_err_sq"] for k in ip_q])
    p_rr, q_rr = rrmse_of(rel_p), rrmse_of(rel_q)
    # 插值 evidence 的 gamma_hat/min_x 解码器边界（interp 行）
    gb = np.concatenate([(ip_p[k]["gamma_hat"].astype(float)
                          / ip_p[k]["min_x"].astype(float)) for k in ip_p])
    n_bnd = int(np.sum(gb >= BOUNDARY_THRESHOLD))

    per_beta, per_goe, per_n = {}, {}, {}
    for k in ip_p:
        b = ip_p[k]["keys_beta"].astype(float)
        g = ip_p[k]["keys_gamma_over_eta"].astype(float)
        nv = ip_p[k]["keys_n"].astype(float)
        rp = ip_p[k]["rel_err_sq"].astype(float)
        rq = ip_q[k]["rel_err_sq"].astype(float)
        for bb in np.unique(b):
            m = b == bb
            acc = per_beta.setdefault(float(bb), [0.0, 0.0, 0])
            acc[0] += float(np.sum(rp[m])); acc[1] += float(np.sum(rq[m]))
            acc[2] += int(np.sum(m))
        for gg in np.unique(g):
            m = g == gg
            acc = per_goe.setdefault(float(gg), [0.0, 0.0, 0])
            acc[0] += float(np.sum(rp[m])); acc[1] += float(np.sum(rq[m]))
            acc[2] += int(np.sum(m))
        for nn_ in np.unique(nv):
            m = nv == nn_
            acc = per_n.setdefault(float(nn_), [0.0, 0.0, 0])
            acc[0] += float(np.sum(rp[m])); acc[1] += float(np.sum(rq[m]))
            acc[2] += int(np.sum(m))

    def _fmt(acc):
        pr = float(np.sqrt(acc[0] / acc[2]))
        qr = float(np.sqrt(acc[1] / acc[2]))
        return {"P": pr, "Q": qr, "rel_change_percent": (qr - pr) / pr * 100.0,
                "n_rows": int(acc[2])}

    summary = {
        "estimand_note": ("paired model-level squared-relative-error on fresh within-domain "
                          "midpoint samples at x0.95; beta midpoints {1.75..4.75 step 0.5}, "
                          "gamma/eta midpoints {0.175,0.375,0.625,0.875}, eta=1000, 300 "
                          "repeats, namespace study01_nrmc_v1; retrained baseline P/Q fits "
                          "in pq_s3_interp (model states were not saved for S1)"),
        "n_interp_samples_per_fit": int(len(ip_p[next(iter(ip_p))]["x95_true"])),
        "s1_evidence_identity": {"n_checked": len(fits), "n_identical": n_ident,
                                 "pass": bool(n_ident == len(fits))},
        "pooled_rrmse": {"P": p_rr, "Q": q_rr},
        "rel_change_percent": (q_rr - p_rr) / p_rr * 100.0,
        "bootstrap": bs,
        "per_beta_midpoint": {str(k): _fmt(v) for k, v in sorted(per_beta.items())},
        "per_goe_midpoint": {str(k): _fmt(v) for k, v in sorted(per_goe.items())},
        "per_n": {str(k): _fmt(v) for k, v in sorted(per_n.items())},
        "failures": _failures(ROOT_INTERP, fits),
        "boundary_counts": {"n_rows": int(len(gb)), "n_boundary": n_bnd,
                            "boundary_share": float(n_bnd / len(gb)) if len(gb) else 0.0},
    }
    adir = os.path.join(ROOT_INTERP, "analysis")
    os.makedirs(adir, exist_ok=True)
    with open(os.path.join(adir, "interp_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)
    return summary


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=200000)
    ap.add_argument("--seed", action="append", type=int, default=None)
    args = ap.parse_args()
    seeds = [int(s) for s in args.seed] if args.seed else [int(s) for s in CFG.SEEDS]
    matrix, ts = analyze_e1(seeds, args.n_boot)
    analyze_e2(seeds)
    analyze_e3(seeds, args.n_boot)
    print("=== S3 analysis ===")
    print("cross-target pooled rRMSE:")
    for r in matrix["routes"]:
        print(f"  {r}: " + ", ".join(f"p{p}={matrix['pooled_rrmse'][r][p]:.6f}"
                                     for p in matrix["targets"]))
    for p in sorted(ts, key=float):
        t = ts[p]
        b = t["bootstrap"]
        rq = next(k for k in t["pooled_rrmse"] if k != "P")
        print(f"  target {p}: P={t['pooled_rrmse']['P']:.6f} Q={t['pooled_rrmse'][rq]:.6f} "
              f"delta={b['pooled_mean']:.6f} CI=[{b['ci_lo']:.6f},{b['ci_hi']:.6f}]")
    print("analysis written to all three roots")


if __name__ == "__main__":
    main()
