"""Study/02 同分布主协议（iid-v1）S2 机制分析模块。

**阶段性质**：纯分析。复用 S1 冻结证据 `artifacts/pq_iid_main/evidence/*.npz`
（120 fits，60 个 P/Q 配对），**不训练、不重训、不生成任何新 fit**（S2 任务边界）。

按 `09-PQ-同分布主协议冻结.md` §8 M2 与 S2 任务消息实现的最小充分分析，对每个
held-out 预测（P 与 Q 各 144,000 行）构造：

1. **无量纲参数误差**（与 P 损失同形，`losses.loss_p`）：
   `u = ((beta_hat-beta)/beta, (eta_hat-eta)/eta, (gamma_hat-gamma)/eta)`；
2. **相对寿命误差的无量纲敏感度向量** `s`（真值处解析梯度，协议 §8 M2）：
   `x_p = gamma + eta*(-ln p)^(1/beta)`（`p=0.95`），
   `dx/dbeta = -eta*a^(1/beta)*ln(a)/beta^2`、`dx/deta = a^(1/beta)`、
   `dx/dgamma = 1`（`a=-ln p`），`s_j = (dx/dtheta_j)*(Delta theta_j 对应因子)/x`，
   即 `s_beta = dx_dbeta*beta/x`、`s_eta = dx_deta*eta/x`、`s_gamma = eta/x`，
   使一阶投影 `proj = s.u = (x_hat-x)/x` 的一阶展开；
3. **分解**：`actual = rel_err`（= 冻结 S1 证据的 (x_hat-x)/x），
   `first_order = proj`，`nonlinear_remainder = actual - proj`；
4. **目标对齐 vs 等分位点切向（nuisance）幅值**（协议 M2.3）：
   `u_par = u.s_hat = proj/|s|`（沿敏感度方向的带符号分量），
   `u_perp = sqrt(|u|^2 - u_par^2)`（等分位点曲面切向/零空间分量），
   `align = |u_par|/|u|`（对齐比，0=正交，1=完全对齐）；
5. **组件抵消指数**（协议 M2.3 "抵消" 的可操作定义，零分母显式处理）：
   对贡献 `c_j = s_j*u_j`，`A = |c_beta|+|c_eta|+|c_gamma|`，
   `B = |c_beta+c_eta+c_gamma|`，`cancel = (A-B)/A`（`A>0`），`A=0` 时取 0。
   `0` = 无抵消（各贡献同向），`1` = 完全抵消（投影=0）。
6. **参数误差幅值与解码器边界诊断**：逐分量 RMS |u|；`gamma_hat/min_x` 阈值
   `>= 0.9999` 的行计数与误差占比（解码器上边缘行为，非支撑违规）。

聚合输出（`artifacts/pq_iid_main/analysis/`，紧凑、无逐行 dump）：
- `mechanism_summary.json`：pooled 机制量 + 设计级配对差值（fold×seed 交叉
  95% CI，B 参数化）+ 区域翻转检验（描述性相关）；
- `mechanism_by_region.csv`：按 β / γ/η / n 分层的 P/Q 机制量描述表；
- `mechanism_cell_pairs.csv`：60 个 (n,fold,seed) cell 的 P/Q 机制量与配对差
  （供设计级复核）。

用法（iid 协议下，cwd = code/）：
    PQ_PROTOCOL=iid-v1 python -m study02pq.mechanism --n-boot 20000
"""

from __future__ import annotations

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

from study02pq import config as CFG  # noqa: E402
from study02pq import evaluate as EVAL  # noqa: E402
from study02pq import run as RUN  # noqa: E402
from study02pq import training as TR  # noqa: E402

# 解码器上边缘诊断阈值（与 v3 boundary_diagnostic 一致）
BOUNDARY_THRESHOLD = 0.9999

# 用于机制量设计级配对差值的交叉 bootstrap rng（与主推断同方案，独立标注为描述性）
BOOT_RNG_SEED = 20260805


# ----------------------------------------------------------------------
# 解析敏感度（协议 §8 M2，真值处）
# ----------------------------------------------------------------------

def analytic_sensitivity(beta: float, eta: float, gamma: float,
                         R: float = CFG.X0_95_R):
    """真值 (beta, eta, gamma) 处的寿命点与解析梯度 + 无量纲敏感度。

    返回 (x, dx_dbeta, dx_deta, dx_dgamma, s_beta, s_eta, s_gamma)。
    x = gamma + eta*(-ln R)^(1/beta)；s_j 使一阶相对寿命误差 = s.u。
    """
    a = -np.log(R)
    t = a ** (1.0 / beta)
    x = gamma + eta * t
    dx_dbeta = -eta * t * np.log(a) / beta ** 2
    dx_deta = t
    dx_dgamma = 1.0
    s_beta = dx_dbeta * beta / x
    s_eta = dx_deta * eta / x
    s_gamma = dx_dgamma * eta / x
    return x, dx_dbeta, dx_deta, dx_dgamma, s_beta, s_eta, s_gamma


# ----------------------------------------------------------------------
# 逐行机制量（一个 fit 的 evidence npz → 2400 行数组）
# ----------------------------------------------------------------------

def row_mechanism(ev: dict, eta_true: float = CFG.ETA, R: float = CFG.X0_95_R) -> dict:
    """把一个 fit 的 evidence 变成逐行机制量（全部 float64；hat 来自 float32 存储）。

    actual 采用冻结证据的 `rel_err`（= (x95_hat - x95_true)/x95_true，S1 sealed 定义）；
    一阶投影 proj 与非线性残差 rem 由存储 hat + 精确真值键重算。
    """
    beta = ev["keys_beta"].astype(np.float64)
    goe = ev["keys_gamma_over_eta"].astype(np.float64)
    gamma = goe * eta_true
    b_hat = ev["beta_hat"].astype(np.float64)
    e_hat = ev["eta_hat"].astype(np.float64)
    g_hat = ev["gamma_hat"].astype(np.float64)
    min_x = ev["min_x"].astype(np.float64)
    actual = ev["rel_err"].astype(np.float64)

    a = -np.log(R)
    ln_a = np.log(a)
    t = a ** (1.0 / beta)
    x = gamma + eta_true * t
    dx_dbeta = -eta_true * t * ln_a / beta ** 2
    dx_deta = t

    # 无量纲敏感度（相对寿命误差）
    s_beta = dx_dbeta * beta / x
    s_eta = dx_deta * eta_true / x
    s_gamma = eta_true / x

    # 无量纲参数误差（P 损失同形）
    u_beta = (b_hat - beta) / beta
    u_eta = (e_hat - eta_true) / eta_true
    u_gamma = (g_hat - gamma) / eta_true

    # 一阶投影 + 非线性残差
    proj = s_beta * u_beta + s_eta * u_eta + s_gamma * u_gamma
    rem = actual - proj

    # 目标对齐 vs 等分位点切向（nuisance）
    s_norm = np.sqrt(s_beta ** 2 + s_eta ** 2 + s_gamma ** 2)
    u_par = proj / s_norm  # 带符号沿 s 分量（u.s_hat）
    u_norm = np.sqrt(u_beta ** 2 + u_eta ** 2 + u_gamma ** 2)
    u_perp = np.sqrt(np.maximum(u_norm ** 2 - u_par ** 2, 0.0))
    align = np.divide(np.abs(u_par), u_norm, out=np.zeros_like(u_par),
                      where=u_norm > 0.0)

    # 组件抵消指数（零分母显式处理）
    c_beta = s_beta * u_beta
    c_eta = s_eta * u_eta
    c_gamma = s_gamma * u_gamma
    A = np.abs(c_beta) + np.abs(c_eta) + np.abs(c_gamma)
    B = np.abs(proj)
    cancel = np.divide(A - B, A, out=np.zeros_like(A), where=A > 0.0)

    # 解码器边界诊断
    g_over_minx = g_hat / min_x
    boundary = (g_over_minx >= BOUNDARY_THRESHOLD).astype(np.int64)

    return {
        "beta": beta, "goe": goe, "n": ev["keys_n"].astype(np.int64),
        "actual": actual, "proj": proj, "rem": rem,
        "u_beta": u_beta, "u_eta": u_eta, "u_gamma": u_gamma,
        "s_beta": s_beta, "s_eta": s_eta, "s_gamma": s_gamma,
        "u_par": u_par, "u_perp": u_perp, "u_norm": u_norm, "align": align,
        "cancel": cancel, "g_over_minx": g_over_minx, "boundary": boundary,
    }


# ----------------------------------------------------------------------
# cell（模型级）与 pooled/分层聚合
# ----------------------------------------------------------------------

def _rms(a: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.asarray(a, dtype=np.float64) ** 2)))


def _corr_or_none(a: np.ndarray, b: np.ndarray) -> float | None:
    """Pearson 相关；退化输入（<2 点或常值）返回 None（避免 NaN 进 JSON）。"""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    if len(a) < 2 or np.std(a) == 0.0 or np.std(b) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def cell_stats(r: dict) -> dict:
    """一个 (n,fold,seed,route) fit 的模型级机制量（2400 行聚合）。"""
    return {
        "n": int(len(r["actual"])),
        "rms_actual": _rms(r["actual"]),
        "rms_proj": _rms(r["proj"]),
        "rms_rem": _rms(r["rem"]),
        "mean_align": float(np.mean(r["align"])),
        "mean_cancel": float(np.mean(r["cancel"])),
        "rms_u_par": _rms(r["u_par"]),
        "rms_u_perp": _rms(r["u_perp"]),
        "rms_u_beta": _rms(r["u_beta"]),
        "rms_u_eta": _rms(r["u_eta"]),
        "rms_u_gamma": _rms(r["u_gamma"]),
        "n_boundary": int(np.sum(r["boundary"])),
        "corr_proj_actual": _corr_or_none(r["proj"], r["actual"]),
    }


def pooled_stats(rows: list[dict]) -> dict:
    """跨给定行集合的 pooled 机制量（全部样本等权）。"""
    concat = {k: np.concatenate([r[k] for r in rows]) for k in (
        "actual", "proj", "rem", "align", "cancel",
        "u_par", "u_perp", "u_norm", "u_beta", "u_eta", "u_gamma",
        "boundary", "g_over_minx", "beta", "goe", "n")}
    a = concat["actual"]
    p = concat["proj"]
    rem = concat["rem"]
    return {
        "n_rows": int(len(a)),
        "rms_actual": _rms(a),
        "rms_proj": _rms(p),
        "rms_rem": _rms(rem),
        "mean_proj_times_rem": float(np.mean(p * rem)),
        "r2_explained": float(1.0 - np.mean(rem ** 2) / np.mean(a ** 2)),
        "corr_proj_actual": _corr_or_none(p, a),
        "corr_proj_rem": _corr_or_none(p, rem),
        "mean_align": float(np.mean(concat["align"])),
        "mean_cancel": float(np.mean(concat["cancel"])),
        "rms_u_par": _rms(concat["u_par"]),
        "rms_u_perp": _rms(concat["u_perp"]),
        "rms_u_norm": _rms(concat["u_norm"]),
        "rms_u_beta": _rms(concat["u_beta"]),
        "rms_u_eta": _rms(concat["u_eta"]),
        "rms_u_gamma": _rms(concat["u_gamma"]),
        "n_boundary": int(np.sum(concat["boundary"])),
        "boundary_share": float(np.mean(concat["boundary"])),
    }


# ----------------------------------------------------------------------
# 设计级配对差值 + fold×seed 交叉 bootstrap（描述性）
# ----------------------------------------------------------------------

def design_pair_deltas(stats_p: dict, stats_q: dict, keys: list[str],
                       n_boot: int = 20000, level: float = 0.95) -> dict:
    """对 60 个 (n,fold,seed) 模型对的 P/Q 机制量做配对差值 + 交叉 bootstrap CI。

    stats_p/stats_q: {(n, fold_idx, seed): {metric: value}}（route 各自的单 fit 统计）。
    直接复用冻结主推断 `EVAL.primary_design_bootstrap`（按 n 分层重采样 fold + 全局
    重采样 seed，同一 rng 20260805 种子使各 metric 的 CI 自洽）；区间为设计级经验
    不确定性近似（描述性支持，非主推断）。
    """
    n_values = sorted({n for (n, f, s) in stats_p})
    folds = {n: sorted({f for (nn, f, s) in stats_p if nn == n}) for n in n_values}
    out = {}
    for m in keys:
        diffs = {n: {f: [] for f in folds[n]} for n in n_values}
        for (n, f, s) in stats_p:
            diffs[n][f].append(stats_q[(n, f, s)][m] - stats_p[(n, f, s)][m])
        prim = EVAL.primary_design_bootstrap(diffs, n_boot=n_boot, level=level)
        out[m] = {"mean_delta": prim["pooled_mean"],
                  "ci_lo": prim["pooled_ci_lo"], "ci_hi": prim["pooled_ci_hi"],
                  "n_boot": int(n_boot), "level": level}
    return out


# ----------------------------------------------------------------------
# 数据加载与区域汇总
# ----------------------------------------------------------------------

def load_all_rows(seeds) -> tuple[dict, dict, dict, dict]:
    """加载 60 对 P/Q evidence 并计算逐行机制量与单 fit 统计。

    返回 (rows_p, rows_q, stats_p, stats_q)；rows_*: {(n,fold_idx,seed): row_mechanism}，
    stats_*: {(n, fold_idx, seed): cell_stats}。P/Q 配对键一致性全量校验。
    """
    rows_p, rows_q = {}, {}
    stats_p, stats_q = {}, {}
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                ep = RUN.load_evidence(TR.fit_id(n, fold_idx, seed, "P"))
                eq = RUN.load_evidence(TR.fit_id(n, fold_idx, seed, "Q"))
                for k in ("keys_beta", "keys_gamma_over_eta", "keys_n", "keys_repeat_id"):
                    if not np.array_equal(ep[k], eq[k]):
                        raise AssertionError(f"pairing key mismatch n{n} f{fold_idx+1} s{seed} {k}")
                key = (n, fold_idx, seed)
                rp = row_mechanism(ep)
                rq = row_mechanism(eq)
                rows_p[key] = rp
                rows_q[key] = rq
                stats_p[key] = cell_stats(rp)
                stats_q[key] = cell_stats(rq)
    # 每 (n, fold) 应有 3 个 seed（主推断结构一致）
    per_cell = {}
    for (n, f, s) in stats_p:
        per_cell.setdefault((n, f), []).append(s)
    assert all(len(v) == len(seeds) for v in per_cell.values()), "seed 数不一致"
    return rows_p, rows_q, stats_p, stats_q


def _region_agg(rows: dict, col: str, value: float) -> list[dict]:
    """返回 rows 中 col == value 的**逐行掩码子集**（iid 测试折覆盖全部组合，
    故 β/γ 在 cell 内变化，不能按整 cell 过滤）；各键同掩码对齐，供 pooled_stats。"""
    out = []
    for r in rows.values():
        m = r[col] == value
        if not np.any(m):
            continue
        out.append({k: v[m] for k, v in r.items()})
    return out


def region_table(rows_p: dict, rows_q: dict, s1_mean_diff: dict) -> pd.DataFrame:
    """按 (region_type, value) 分层的 P/Q 机制量 + Q-P 差值 + S1 区域 mean_diff。"""
    rec = []
    for rtype, col in (("beta", "beta"), ("gamma_over_eta", "goe"), ("n", "n")):
        values = sorted(set(float(v) for r in rows_p.values() for v in r[col]))
        for v in values:
            rp = _region_agg(rows_p, col, v)
            rq = _region_agg(rows_q, col, v)
            sp, sq = pooled_stats(rp), pooled_stats(rq)
            rec.append({
                "region": rtype, "value": v,
                "n_rows": sp["n_rows"],
                "p_rms_actual": sp["rms_actual"], "q_rms_actual": sq["rms_actual"],
                "p_rms_proj": sp["rms_proj"], "q_rms_proj": sq["rms_proj"],
                "p_rms_rem": sp["rms_rem"], "q_rms_rem": sq["rms_rem"],
                "p_mean_align": sp["mean_align"], "q_mean_align": sq["mean_align"],
                "p_mean_cancel": sp["mean_cancel"], "q_mean_cancel": sq["mean_cancel"],
                "p_rms_u_par": sp["rms_u_par"], "q_rms_u_par": sq["rms_u_par"],
                "p_rms_u_perp": sp["rms_u_perp"], "q_rms_u_perp": sq["rms_u_perp"],
                "delta_rms_actual": sq["rms_actual"] - sp["rms_actual"],
                "delta_rms_proj": sq["rms_proj"] - sp["rms_proj"],
                "delta_rms_rem": sq["rms_rem"] - sp["rms_rem"],
                "delta_mean_align": sq["mean_align"] - sp["mean_align"],
                "delta_mean_cancel": sq["mean_cancel"] - sp["mean_cancel"],
                "delta_rms_u_par": sq["rms_u_par"] - sp["rms_u_par"],
                "delta_rms_u_perp": sq["rms_u_perp"] - sp["rms_u_perp"],
                "s1_mean_diff": s1_mean_diff.get((rtype, v)),
            })
    return pd.DataFrame(rec)


# ----------------------------------------------------------------------
# 主入口
# ----------------------------------------------------------------------

def _corr(a: list[float], b: list[float]) -> float | None:
    a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
    if len(a) < 3 or np.std(a) == 0.0 or np.std(b) == 0.0:
        return None
    return float(np.corrcoef(a, b)[0, 1])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=20000)
    ap.add_argument("--seed", action="append", type=int, default=None)
    args = ap.parse_args()
    seeds = [int(s) for s in args.seed] if args.seed else [int(s) for s in CFG.SEEDS]
    out = os.path.join(CFG.ARTIFACT_DIR, "analysis")
    os.makedirs(out, exist_ok=True)

    rows_p, rows_q, stats_p, stats_q = load_all_rows(seeds)
    n_pairs = len(rows_p)
    n_per_row = len(next(iter(rows_p.values()))["actual"])
    n_rows = n_pairs * n_per_row
    assert n_pairs == 60 and n_per_row == 2400 and n_rows == 144000, \
        (n_pairs, n_per_row, n_rows)

    sp = pooled_stats(list(rows_p.values()))
    sq = pooled_stats(list(rows_q.values()))

    # 与 S1 sealed 主数值交叉核对（rRMSE 系列 float32 级容差）
    with open(os.path.join(out, "summary_iid.json"), encoding="utf-8") as f:
        sealed = json.load(f)
    p0, q0 = sealed["pooled"]["p_rrmse"], sealed["pooled"]["q_rrmse"]
    for got, want, name in ((sp["rms_actual"], p0, "pooled P rRMSE"),
                            (sq["rms_actual"], q0, "pooled Q rRMSE")):
        if not np.isclose(got, want, rtol=1e-6, atol=1e-9):
            print(f"[mechanism] WARN cross-check {name}: {got:.10f} vs sealed {want:.10f}")

    # S1 区域 mean_diff（描述，跨 cell 样本等权重算；与 by_region.csv 同源）
    s1_mean_diff = {}
    acc = {}
    # 只用 rel_sq 差值，float64 累加
    for (n, fold_idx, seed), rp in rows_p.items():
        rq = rows_q[(n, fold_idx, seed)]
        for b, g in set(zip(rp["beta"].tolist(), rp["goe"].tolist())):
            m = (rp["beta"] == b) & (rp["goe"] == g)
            d = (rq["actual"][m] ** 2 - rp["actual"][m] ** 2)
            for rtype, col, val in (("beta", "beta", b), ("gamma_over_eta", "goe", g),
                                    ("n", "n", int(n))):
                acc.setdefault((rtype, val), [0.0, 0])
                acc[(rtype, val)][0] += float(np.sum(d))
                acc[(rtype, val)][1] += int(np.sum(m))
    for (rtype, val), (s, cnt) in acc.items():
        s1_mean_diff[(rtype, val)] = float(s / cnt)

    # 分层表
    region_df = region_table(rows_p, rows_q, s1_mean_diff)
    region_df.to_csv(os.path.join(out, "mechanism_by_region.csv"), index=False)

    # cell 配对表（60 个 (n,fold,seed) 模型对）
    pair_rec = []
    metrics = ("rms_actual", "rms_proj", "rms_rem", "mean_align", "mean_cancel",
               "rms_u_par", "rms_u_perp", "rms_u_beta", "rms_u_eta", "rms_u_gamma",
               "n_boundary", "corr_proj_actual")
    for (n, fold_idx, seed) in sorted(stats_p):
        row = {"n": n, "fold": fold_idx + 1, "seed": seed}
        for m in metrics:
            row[f"p_{m}"] = stats_p[(n, fold_idx, seed)][m]
            row[f"q_{m}"] = stats_q[(n, fold_idx, seed)][m]
            row[f"delta_{m}"] = stats_q[(n, fold_idx, seed)][m] \
                - stats_p[(n, fold_idx, seed)][m]
        pair_rec.append(row)
    pd.DataFrame(pair_rec).to_csv(
        os.path.join(out, "mechanism_cell_pairs.csv"), index=False)

    # 设计级配对差值 + CI（关键机制量）
    design_keys = ("rms_actual", "rms_proj", "rms_rem", "mean_align",
                   "mean_cancel", "rms_u_par", "rms_u_perp")
    design = design_pair_deltas(stats_p, stats_q, design_keys, n_boot=args.n_boot)

    # 区域翻转检验（描述性相关：S1 区域 mean_diff vs 机制量差值）
    reversal = {}
    for rtype in ("beta", "gamma_over_eta", "n"):
        sub = region_df[region_df["region"] == rtype].sort_values("value")
        rows = sub.to_dict("records")
        md = [r["s1_mean_diff"] for r in rows if r["s1_mean_diff"] is not None]
        rev = {}
        for mech in ("delta_rms_proj", "delta_rms_rem", "delta_rms_actual",
                     "delta_mean_align", "delta_mean_cancel",
                     "delta_rms_u_par", "delta_rms_u_perp"):
            mech_v = [r[mech] for r in rows if r["s1_mean_diff"] is not None]
            rev[mech] = _corr(md, mech_v)
        reversal[rtype] = rev

    summary = {
        "protocol": "iid-v1",
        "stage": "S2 mechanism (analysis-only; reuses frozen S1 evidence, no training)",
        "estimand_note": ("decomposition of actual relative x_0.95 error into "
                          "first-order sensitivity projection proj=s.u and nonlinear "
                          "remainder; target-aligned vs isoquantile-tangent magnitudes; "
                          "component-cancellation index; all per held-out prediction"),
        "formulas": {
            "x_p": "gamma + eta*(-ln p)^(1/beta), p=0.95",
            "u": "((beta_hat-beta)/beta, (eta_hat-eta)/eta, (gamma_hat-gamma)/eta)",
            "dx_dbeta": "-eta*a^(1/beta)*ln(a)/beta^2",
            "dx_deta": "a^(1/beta)",
            "dx_dgamma": "1",
            "s_beta": "dx_dbeta*beta/x", "s_eta": "dx_deta*eta/x",
            "s_gamma": "eta/x",
            "proj": "s_beta*u_beta + s_eta*u_eta + s_gamma*u_gamma",
            "nonlinear_remainder": "actual - proj",
            "align": "|u_par|/|u|, u_par = u.s_hat = proj/|s|",
            "cancel": "(|c_beta|+|c_eta|+|c_gamma| - |proj|) / (|c_beta|+|c_eta|+|c_gamma|), "
                      "0 if denominator 0",
        },
        "evidence": {
            "n_fits": 120, "n_pairs": n_pairs, "n_rows_per_route": n_rows,
            "evidence_dir": "artifacts/pq_iid_main/evidence",
            "baseline_tip": "928497b9",
        },
        "s1_cross_check": {
            "pooled_p_rrmse_sealed": p0, "pooled_q_rrmse_sealed": q0,
            "rms_actual_recomputed_P": sp["rms_actual"],
            "rms_actual_recomputed_Q": sq["rms_actual"],
        },
        "pooled": {
            "P": sp, "Q": sq,
            "delta_Q_minus_P": {
                "rms_actual": sq["rms_actual"] - sp["rms_actual"],
                "rms_proj": sq["rms_proj"] - sp["rms_proj"],
                "rms_rem": sq["rms_rem"] - sp["rms_rem"],
                "mean_align": sq["mean_align"] - sp["mean_align"],
                "mean_cancel": sq["mean_cancel"] - sp["mean_cancel"],
                "rms_u_par": sq["rms_u_par"] - sp["rms_u_par"],
                "rms_u_perp": sq["rms_u_perp"] - sp["rms_u_perp"],
                "rms_u_norm": sq["rms_u_norm"] - sp["rms_u_norm"],
            },
        },
        "design_pair_deltas": design,
        "reversal_correlation_descriptive": reversal,
        "limits": [
            "analysis-only decomposition; observed association, not causal proof",
            "design-level paired CIs are descriptive secondary support, not the primary inference",
            "3 seeds only; training-fold overlap under repeat-stratified splitting",
            "first-order projection uses sensitivity at true parameters; remainder absorbs "
            "second-order and finite-parameter effects and float32 storage of hats",
            "region-level correlation is over a handful of bins (8 beta, 5 goe, 4 n), "
            "unweighted, exploratory",
        ],
        "n_boot_design_pairs": args.n_boot,
    }
    with open(os.path.join(out, "mechanism_summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    print("=== S2 mechanism (iid-v1) ===")
    print(f"rows: {n_pairs} pairs x 2400 = {n_rows} per route")
    print(f"pooled rms_actual: P={sp['rms_actual']:.6f}  Q={sq['rms_actual']:.6f}"
          f"  (sealed P={p0:.6f} Q={q0:.6f})")
    print(f"pooled rms_proj:  P={sp['rms_proj']:.6f}  Q={sq['rms_proj']:.6f}  "
          f"delta={sq['rms_proj']-sp['rms_proj']:.6f}")
    print(f"pooled rms_rem:   P={sp['rms_rem']:.6f}  Q={sq['rms_rem']:.6f}  "
          f"delta={sq['rms_rem']-sp['rms_rem']:.6f}")
    print(f"pooled mean_align:P={sp['mean_align']:.5f}  Q={sq['mean_align']:.5f}")
    print(f"pooled mean_cancel:P={sp['mean_cancel']:.5f}  Q={sq['mean_cancel']:.5f}")
    for m in design_keys:
        d = design[m]
        print(f"  design pair {m}: delta={d['mean_delta']:.6f} "
              f"CI=[{d['ci_lo']:.6f},{d['ci_hi']:.6f}]")
    print("reversal corr (descriptive):")
    for rtype, rev in reversal.items():
        print(f"  {rtype}: " + ", ".join(f"{k}={v:.2f}" if v is not None else f"{k}=NA"
                                         for k, v in rev.items()))
    print("analysis written to", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
