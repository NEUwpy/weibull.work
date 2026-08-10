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
3. **一阶分解（局部线性诊断）**：`actual = rel_err`（= 冻结 S1 证据的 (x_hat-x)/x），
   `proj = s.u` 为一阶投影，`rem = actual - proj` 为非线性余项。**注意**：当
   `|proj| >> |actual|` 时 `corr(proj,rem) ~ -1` 是代数上近乎必然的（余项 ≈ -proj），
   故 proj-rem 反相只诊断「真值处一阶 Taylor 远离真值」，本身不构成因果；机制主张
   需配合精确分解（见 4）与敏感度范数（见 6）。
4. **精确无余项分解**（对称形式，机器精度内 exact）：
   `t0 = a^(1/beta)`、`t1 = a^(1/beta_hat)`，
   `C_gamma = (gamma_hat - gamma)/x`、`C_eta = 0.5*(eta_hat-eta)*(t0+t1)/x`、
   `C_beta = 0.5*(eta+eta_hat)*(t1-t0)/x`，**exact `actual = C_beta+C_eta+C_gamma`**
   （up to floating precision）；据此定义**精确分量抵消指数**
   `cancel_exact = (|C_beta|+|C_eta|+|C_gamma| - |actual|) / (|C_beta|+|C_eta|+|C_gamma|)`
   （分母 0 时取 0；度量维持目标 x_0.95 所需的参数补偿量，非一阶分量抵消）。
5. **目标对齐 vs 真值点局部切向分量**（协议 M2.3）：
   `u_par = proj/|s|`（沿敏感度方向的带符号分量），
   `u_perp = sqrt(|u|^2 - u_par^2)`（真值点**局部切空间**内正交分量；Q 远离真值时
   **不是**到弯曲等分位点流形的全局距离，仅为真值点局部切向近似），
   `align = |u_par|/|u|`（对齐比，0=正交，1=完全对齐）。
6. **真值点无量纲敏感度范数** `|s| = sqrt(s_beta^2+s_eta^2+s_gamma^2)`（目标误差对参数
   误差的放大系数；只依赖真值参数，故跨 n 构造性相同）。
7. **参数误差幅值与解码器边界诊断**：逐分量 RMS |u| 与分位点分布；`gamma_hat/min_x` 阈值
   `>= 0.9999` 的行计数与误差占比（解码器上边缘行为，非支撑违规）。

聚合输出（`artifacts/pq_iid_main/analysis/`，紧凑、无逐行 dump）：
- `mechanism_summary.json`：pooled 机制量 + 设计级配对差值（fold×seed 交叉
  95% CI，B 参数化）+ 区域翻转检验（描述性相关）；
- `mechanism_by_region.csv`：按 β / γ/η / n 分层的 P/Q 机制量描述表；
- `mechanism_cell_pairs.csv`：60 个 (n,fold,seed) cell 的 P/Q 机制量与配对差
  （供设计级复核）。

另由 ``--paper-core-only`` 写入 `artifacts/pq_paper_core/analysis/`：
- `mechanism_sensitivity_grid.csv`：40 个冻结参数点在 P 归一化坐标下的逐参数
  `x_0.95` 敏感度；
- `mechanism_paper_regions.csv` / `mechanism_paper_cells.csv` /
  `mechanism_paper_core.json`：当前论文 Fig2 的10-seed最小派生数据（区域收益 +
  精确补偿），不含多目标或外推合同。

用法（iid 协议下，cwd = code/）：
    PQ_PROTOCOL=iid-v1 python -m study02pq.mechanism --n-boot 20000

只生成当前论文10-seed核心机制派生物（不改写 S2 sealed analysis）：
    PQ_PROTOCOL=iid-v1 python -m study02pq.mechanism --paper-core-only
"""

from __future__ import annotations

import argparse
import hashlib
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


def sha256_file(path: str, canonical_text: bool = True) -> str:
    """项目证据约定：文本按 LF 规范化哈希，二进制按原始字节。"""
    with open(path, "rb") as f:
        data = f.read()
    if canonical_text:
        data = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    return hashlib.sha256(data).hexdigest()


def _study_rel(path: str) -> str:
    return os.path.relpath(path, CFG.STUDY02_ROOT).replace("\\", "/")


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


def sensitivity_grid_table(beta_grid=None, gamma_over_eta_grid=None,
                           eta: float = CFG.ETA,
                           R: float = CFG.X0_95_R) -> pd.DataFrame:
    """冻结参数网格上的逐参数目标敏感度（P 归一化坐标）。

    ``u=((beta_hat-beta)/beta, (eta_hat-eta)/eta,
    (gamma_hat-gamma)/eta)`` 与 P 损失坐标一致；在真值处，目标相对误差的一阶项
    为 ``s.u``。因此 ``s_beta/s_eta/s_gamma`` 是 Q 在该坐标下的局部目标权重，
    不是人为指定的参数重要性。L1 share 仅用于展示方向组成，不能替代原始幅值。
    """
    beta_grid = CFG.BETA_GRID if beta_grid is None else beta_grid
    gamma_over_eta_grid = (CFG.GAMMA_OVER_ETA_GRID if gamma_over_eta_grid is None
                           else gamma_over_eta_grid)
    records = []
    for beta in beta_grid:
        for goe in gamma_over_eta_grid:
            x, _, _, _, sb, se, sg = analytic_sensitivity(
                float(beta), float(eta), float(goe) * float(eta), R=float(R))
            vec = np.asarray([sb, se, sg], dtype=np.float64)
            norm = float(np.linalg.norm(vec))
            l1 = float(np.sum(np.abs(vec)))
            records.append({
                "beta": float(beta),
                "gamma_over_eta": float(goe),
                "x_R_over_eta": float(x / eta),
                "s_beta": float(sb),
                "s_eta": float(se),
                "s_gamma": float(sg),
                "s_norm": norm,
                "unit_beta": float(sb / norm),
                "unit_eta": float(se / norm),
                "unit_gamma": float(sg / norm),
                "l1_share_beta": float(abs(sb) / l1),
                "l1_share_eta": float(abs(se) / l1),
                "l1_share_gamma": float(abs(sg) / l1),
            })
    return pd.DataFrame.from_records(records)


def paper_core_diagnostics(sensitivity_df: pd.DataFrame,
                           region_df: pd.DataFrame,
                           cell_df: pd.DataFrame,
                           pooled_p: dict, pooled_q: dict) -> dict:
    """把现有机制证据收口为当前论文 Fig2 使用的最小派生统计。

    这只描述 (i) 解析目标敏感度、(ii) 区域相关、(iii) 精确恒等式下的补偿；
    不把区域相关或补偿结果解释为已识别的训练动力学因果效应。
    """
    vec = sensitivity_df[["s_beta", "s_eta", "s_gamma"]].to_numpy(float)
    unit = vec / np.linalg.norm(vec, axis=1, keepdims=True)
    cosine = np.clip(unit @ unit.T, -1.0, 1.0)
    max_angle = float(np.degrees(np.max(np.arccos(cosine))))

    component_ranges = {}
    for name in ("s_beta", "s_eta", "s_gamma", "s_norm"):
        values = sensitivity_df[name].to_numpy(float)
        component_ranges[name] = {
            "min": float(np.min(values)),
            "max": float(np.max(values)),
            "max_over_min": float(np.max(values) / np.min(values)),
        }

    region_records = []
    correlations = {}
    for region in ("beta", "gamma_over_eta"):
        sub = region_df[region_df["region"] == region].copy().sort_values("value")
        sub["q_advantage_abs"] = sub["p_rms_actual"] - sub["q_rms_actual"]
        sub["q_advantage_relative"] = (
            sub["q_advantage_abs"] / sub["p_rms_actual"])
        corr_abs = _corr_or_none(sub["p_mean_s_norm"].to_numpy(float),
                                 sub["q_advantage_abs"].to_numpy(float))
        corr_rel = _corr_or_none(sub["p_mean_s_norm"].to_numpy(float),
                                 sub["q_advantage_relative"].to_numpy(float))
        correlations[region] = {
            "pearson_r_s_norm_vs_q_advantage_abs": corr_abs,
            "pearson_r_s_norm_vs_q_advantage_relative": corr_rel,
            "n_regions": int(len(sub)),
        }
        for row in sub.to_dict("records"):
            region_records.append({
                "region": region,
                "value": float(row["value"]),
                "n_rows": int(row["n_rows"]),
                "mean_s_norm": float(row["p_mean_s_norm"]),
                "p_rms_actual": float(row["p_rms_actual"]),
                "q_rms_actual": float(row["q_rms_actual"]),
                "q_advantage_abs": float(row["q_advantage_abs"]),
                "q_advantage_relative": float(row["q_advantage_relative"]),
            })

    n_q_more_cancel = int(np.sum(
        cell_df["q_mean_cancel_exact"] > cell_df["p_mean_cancel_exact"]))
    return {
        "protocol": "iid-v1",
        "stage": "paper-core mechanism derivation (analysis only; no training)",
        "target": {"R": float(CFG.X0_95_R), "label": "x_0.95"},
        "sensitivity_coordinate": (
            "u=((beta_hat-beta)/beta,(eta_hat-eta)/eta,"
            "(gamma_hat-gamma)/eta); local relative target error = s.u"),
        "sensitivity_formula": {
            "s_beta": "(dx_R/dbeta)*beta/x_R",
            "s_eta": "(dx_R/deta)*eta/x_R",
            "s_gamma": "(dx_R/dgamma)*eta/x_R",
            "q_gradient": (
                "for L_Q=mean(e_i^2), per-sample contribution "
                "dL_Q/du_ij=(2/m)*e_i*s_ij at truth; e_i=(xhat_R-x_R)/x_R"),
            "p_gradient": (
                "for L_P=mean(sum_j u_ij^2), per-sample contribution "
                "dL_P/du_ij=(2/m)*u_ij"),
            "local_curvature": (
                "around truth: H_Q=(2/m)*s_i*s_i^T whereas H_P=(2/m)*I; "
                "Q includes target-induced cross-parameter terms"),
        },
        "pooled_frozen_grid": {
            "p_rrmse": float(pooled_p["rms_actual"]),
            "q_rrmse": float(pooled_q["rms_actual"]),
            "q_relative_improvement": float(
                (pooled_p["rms_actual"] - pooled_q["rms_actual"])
                / pooled_p["rms_actual"]),
        },
        "sensitivity_grid": {
            "n_points": int(len(sensitivity_df)),
            "n_beta": int(sensitivity_df["beta"].nunique()),
            "n_gamma_over_eta": int(sensitivity_df["gamma_over_eta"].nunique()),
            "component_ranges": component_ranges,
            "max_pairwise_direction_angle_degrees": max_angle,
            "n_distinct_directions": int(sensitivity_df["beta"].nunique()),
            "fixed_weight_implication": (
                "Even at one grid point a diagonal weighted-parameter loss lacks Q's "
                "cross-parameter curvature s*s^T; additionally, both sensitivity "
                "magnitude and direction vary on the frozen grid. Therefore no single "
                "fixed diagonal parameter-weight vector exactly reproduces local Q "
                "geometry over all grid points. This is an algebraic loss-geometry "
                "statement, not an empirical training-cause estimate."),
        },
        "regional_association_exploratory": {
            "definition": "Q advantage = P rRMSE - Q rRMSE within each region",
            "correlations": correlations,
            "records": region_records,
            "limit": (
                "Unweighted Pearson association over 8 beta and 5 gamma/eta bins; "
                "descriptive, not a causal or necessary/sufficient-condition test."),
        },
        "exact_compensation_x_0.95": {
            "identity": "actual=C_beta+C_eta+C_gamma (up to float32 evidence storage)",
            "mean_cancel_exact_P": float(pooled_p["mean_cancel_exact"]),
            "mean_cancel_exact_Q": float(pooled_q["mean_cancel_exact"]),
            "delta_Q_minus_P": float(
                pooled_q["mean_cancel_exact"] - pooled_p["mean_cancel_exact"]),
            "n_cell_pairs_Q_gt_P": n_q_more_cancel,
            "n_cell_pairs": int(len(cell_df)),
            "identity_max_abs_err_P": float(pooled_p["identity_max_abs_err"]),
            "identity_max_abs_err_Q": float(pooled_q["identity_max_abs_err"]),
            "limit": (
                "The exact identity establishes the result-space compensation pattern; "
                "it does not by itself identify why optimization reached that solution."),
        },
    }


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

    # 一阶投影 + 非线性余项（局部线性诊断；proj-rem 反相不单独构成因果）
    proj = s_beta * u_beta + s_eta * u_eta + s_gamma * u_gamma
    rem = actual - proj

    # 精确无余项分解（对称；actual = C_beta + C_eta + C_gamma up to floating precision）
    t1 = a ** (1.0 / b_hat)
    C_gamma = (g_hat - gamma) / x
    C_eta = 0.5 * (e_hat - eta_true) * (t + t1) / x
    C_beta = 0.5 * (eta_true + e_hat) * (t1 - t) / x
    # cancel_exact 在分解自身 float64 算术内自洽（B_exact = |sum C| = |actual| up to
    # storage）；用 |sum C| 而非 float32 存储的 |actual|，使指数在机器精度内非负。
    A_exact = np.abs(C_beta) + np.abs(C_eta) + np.abs(C_gamma)
    B_exact = np.abs(C_beta + C_eta + C_gamma)
    cancel_exact = np.divide(A_exact - B_exact, A_exact,
                             out=np.zeros_like(A_exact), where=A_exact > 0.0)

    # 目标对齐 vs 真值点局部切向分量（u_perp 为局部切空间近似，非全局流形距离）
    s_norm = np.sqrt(s_beta ** 2 + s_eta ** 2 + s_gamma ** 2)
    u_par = proj / s_norm  # 带符号沿 s 分量（u.s_hat）
    u_norm = np.sqrt(u_beta ** 2 + u_eta ** 2 + u_gamma ** 2)
    u_perp = np.sqrt(np.maximum(u_norm ** 2 - u_par ** 2, 0.0))
    align = np.divide(np.abs(u_par), u_norm, out=np.zeros_like(u_par),
                      where=u_norm > 0.0)

    # 一阶分量抵消指数（零分母显式处理）
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
        "s_beta": s_beta, "s_eta": s_eta, "s_gamma": s_gamma, "s_norm": s_norm,
        "C_beta": C_beta, "C_eta": C_eta, "C_gamma": C_gamma,
        "cancel_exact": cancel_exact,
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
        "mean_cancel_exact": float(np.mean(r["cancel_exact"])),
        "mean_s_norm": float(np.mean(r["s_norm"])),
        "rms_u_par": _rms(r["u_par"]),
        "rms_u_perp": _rms(r["u_perp"]),
        "rms_u_beta": _rms(r["u_beta"]),
        "rms_u_eta": _rms(r["u_eta"]),
        "rms_u_gamma": _rms(r["u_gamma"]),
        "n_boundary": int(np.sum(r["boundary"])),
        "corr_proj_actual": _corr_or_none(r["proj"], r["actual"]),
        "identity_max_abs_err": float(np.max(
            np.abs(r["actual"] - (r["C_beta"] + r["C_eta"] + r["C_gamma"])))),
    }


def pooled_stats(rows: list[dict]) -> dict:
    """跨给定行集合的 pooled 机制量（全部样本等权）。"""
    concat = {k: np.concatenate([r[k] for r in rows]) for k in (
        "actual", "proj", "rem", "align", "cancel", "cancel_exact", "s_norm",
        "u_par", "u_perp", "u_norm", "u_beta", "u_eta", "u_gamma",
        "C_beta", "C_eta", "C_gamma",
        "boundary", "g_over_minx", "beta", "goe", "n")}
    a = concat["actual"]
    p = concat["proj"]
    rem = concat["rem"]
    c_sum = concat["C_beta"] + concat["C_eta"] + concat["C_gamma"]
    return {
        "n_rows": int(len(a)),
        "rms_actual": _rms(a),
        "rms_proj": _rms(p),
        "rms_rem": _rms(rem),
        "mean_proj_times_rem": float(np.mean(p * rem)),
        # 原点到锚定的均方"解释"份额；只作局部线性诊断，不作因果量（见 limits）。
        # 非方差版 R^2：仅当 mean(actual)=0 时才与 1-var(rem)/var(actual) 相等。
        "r2_origin": float(1.0 - np.mean(rem ** 2) / np.mean(a ** 2)),
        "corr_proj_actual": _corr_or_none(p, a),
        "corr_proj_rem": _corr_or_none(p, rem),
        "mean_align": float(np.mean(concat["align"])),
        "mean_cancel": float(np.mean(concat["cancel"])),
        "mean_cancel_exact": float(np.mean(concat["cancel_exact"])),
        "rms_c_beta": _rms(concat["C_beta"]),
        "rms_c_eta": _rms(concat["C_eta"]),
        "rms_c_gamma": _rms(concat["C_gamma"]),
        "mean_s_norm": float(np.mean(concat["s_norm"])),
        "rms_u_par": _rms(concat["u_par"]),
        "rms_u_perp": _rms(concat["u_perp"]),
        "rms_u_norm": _rms(concat["u_norm"]),
        "rms_u_beta": _rms(concat["u_beta"]),
        "rms_u_eta": _rms(concat["u_eta"]),
        "rms_u_gamma": _rms(concat["u_gamma"]),
        "n_boundary": int(np.sum(concat["boundary"])),
        "boundary_share": float(np.mean(concat["boundary"])),
        "identity_max_abs_err": float(np.max(np.abs(a - c_sum))),
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


def load_s5b_grid_rows() -> tuple[dict, dict, dict, dict, dict]:
    """只读加载 S5B 冻结网格的 10-seed P/Q evidence（200 个配对单元）。

    前 3 个 seed 复用 ``pq_iid_main``，后 7 个 seed 读取 ``pq_s5b_revision/grid_extra``；
    路径解析复用 S5B 已冻结实现。该函数只做派生分析，不写 evidence/metadata。
    """
    from study02pq import s5b_revision as S5B  # 本地导入，避免常规 S2 路径耦合

    protocol = S5B.load_protocol()
    seeds = [int(v) for v in protocol["seeds"]["all"]]
    n_grid = [int(v) for v in protocol["study01_domain"]["n_grid"]]
    rows_p, rows_q, stats_p, stats_q = {}, {}, {}, {}
    audit = {
        "key_identity": {
            "pairs_checked": 0,
            "mismatch_pairs": 0,
            "fields": ["beta", "gamma_over_eta", "n", "point_or_repeat_id"],
            "comparison": "exact array equality between paired P and Q evidence",
        },
        "finite_prediction": {
            "rows_checked_P": 0, "rows_checked_Q": 0,
            "nonfinite_prediction_rows_P": 0,
            "nonfinite_prediction_rows_Q": 0,
            "nonfinite_mechanism_input_rows_P": 0,
            "nonfinite_mechanism_input_rows_Q": 0,
        },
        "support_legality": {
            "rule": "beta_hat>0, eta_hat>0, gamma_hat<min_x",
            "rows_checked_P": 0, "rows_checked_Q": 0,
            "nonpositive_beta_or_eta_rows_P": 0,
            "nonpositive_beta_or_eta_rows_Q": 0,
            "gamma_hat_ge_min_x_rows_P": 0,
            "gamma_hat_ge_min_x_rows_Q": 0,
        },
    }

    def point_id(ev: dict) -> np.ndarray:
        name = ("keys_point_or_repeat_id" if "keys_point_or_repeat_id" in ev
                else "keys_repeat_id")
        return ev[name]

    def update_route_audit(ev: dict, route: str) -> None:
        x_key = "xR_hat" if "xR_hat" in ev else "x95_hat"
        n_rows = len(ev[x_key])
        prediction = np.column_stack([
            ev[x_key], ev["rel_err"], ev["rel_err_sq"]])
        mechanism_inputs = np.column_stack([
            ev[x_key], ev["rel_err"], ev["rel_err_sq"], ev["beta_hat"],
            ev["eta_hat"], ev["gamma_hat"], ev["min_x"]])
        audit["finite_prediction"][f"rows_checked_{route}"] += int(n_rows)
        audit["finite_prediction"][f"nonfinite_prediction_rows_{route}"] += int(
            np.sum(~np.all(np.isfinite(prediction), axis=1)))
        audit["finite_prediction"][f"nonfinite_mechanism_input_rows_{route}"] += int(
            np.sum(~np.all(np.isfinite(mechanism_inputs), axis=1)))
        audit["support_legality"][f"rows_checked_{route}"] += int(n_rows)
        audit["support_legality"][f"nonpositive_beta_or_eta_rows_{route}"] += int(
            np.sum((ev["beta_hat"] <= 0.0) | (ev["eta_hat"] <= 0.0)))
        audit["support_legality"][f"gamma_hat_ge_min_x_rows_{route}"] += int(
            np.sum(ev["gamma_hat"] >= ev["min_x"]))

    for n in n_grid:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                ev = {}
                for route in ("P", "Q"):
                    path = S5B._evidence_path("grid", n, fold_idx, seed, route)
                    with np.load(path) as archive:
                        ev[route] = {k: archive[k] for k in archive.files}
                ep, eq = ev["P"], ev["Q"]
                audit["key_identity"]["pairs_checked"] += 1
                paired = all(np.array_equal(a, b) for a, b in (
                    (ep["keys_beta"], eq["keys_beta"]),
                    (ep["keys_gamma_over_eta"], eq["keys_gamma_over_eta"]),
                    (ep["keys_n"], eq["keys_n"]),
                    (point_id(ep), point_id(eq)),
                ))
                if not paired:
                    audit["key_identity"]["mismatch_pairs"] += 1
                update_route_audit(ep, "P")
                update_route_audit(eq, "Q")
                key = (n, fold_idx, seed)
                rp, rq = row_mechanism(ep), row_mechanism(eq)
                rows_p[key], rows_q[key] = rp, rq
                stats_p[key], stats_q[key] = cell_stats(rp), cell_stats(rq)
    if len(rows_p) != 200 or len(rows_q) != 200:
        raise AssertionError(f"expected 200 S5B grid pairs, got {len(rows_p)}")
    audit["key_identity"]["all_pair_keys_identical"] = (
        audit["key_identity"]["mismatch_pairs"] == 0)
    failure_counts = [
        audit["key_identity"]["mismatch_pairs"],
        *[audit["finite_prediction"][f"nonfinite_prediction_rows_{r}"]
          for r in ("P", "Q")],
        *[audit["finite_prediction"][f"nonfinite_mechanism_input_rows_{r}"]
          for r in ("P", "Q")],
        *[audit["support_legality"][f"nonpositive_beta_or_eta_rows_{r}"]
          for r in ("P", "Q")],
        *[audit["support_legality"][f"gamma_hat_ge_min_x_rows_{r}"]
          for r in ("P", "Q")],
    ]
    audit["all_pass"] = all(v == 0 for v in failure_counts)
    if not audit["all_pass"]:
        raise AssertionError(f"S5B paper-core evidence audit failed: {audit}")
    return rows_p, rows_q, stats_p, stats_q, audit


def write_paper_core_outputs(out: str) -> dict:
    """从10-seed冻结网格生成当前论文机制派生物，不触碰任何 sealed 输入。"""
    os.makedirs(out, exist_ok=True)
    sensitivity_df = sensitivity_grid_table()
    rows_p, rows_q, stats_p, stats_q, audit = load_s5b_grid_rows()
    pooled_p = pooled_stats(list(rows_p.values()))
    pooled_q = pooled_stats(list(rows_q.values()))
    region_df = region_table(rows_p, rows_q, {})
    region_df = region_df[region_df["region"].isin(
        ["beta", "gamma_over_eta"])]
    cells = []
    for (n, fold_idx, seed) in sorted(stats_p):
        cells.append({
            "n": int(n), "fold": int(fold_idx + 1), "seed": int(seed),
            "p_rms_actual": float(stats_p[(n, fold_idx, seed)]["rms_actual"]),
            "q_rms_actual": float(stats_q[(n, fold_idx, seed)]["rms_actual"]),
            "p_mean_cancel_exact": float(
                stats_p[(n, fold_idx, seed)]["mean_cancel_exact"]),
            "q_mean_cancel_exact": float(
                stats_q[(n, fold_idx, seed)]["mean_cancel_exact"]),
        })
    cell_df = pd.DataFrame(cells)
    cell_df["delta_rms_actual"] = (
        cell_df["q_rms_actual"] - cell_df["p_rms_actual"])
    cell_df["delta_mean_cancel_exact"] = (
        cell_df["q_mean_cancel_exact"] - cell_df["p_mean_cancel_exact"])
    core = paper_core_diagnostics(
        sensitivity_df, region_df, cell_df, pooled_p, pooled_q)
    core["evidence"] = {
        "source": "S5B frozen-grid P_equal/Q_param evidence only",
        "n_training_seeds": 10,
        "n_cell_pairs": 200,
        "n_fits": 400,
        "n_rows_per_route": int(sum(len(r["actual"]) for r in rows_p.values())),
        "existing_three_seed_dir": "artifacts/pq_iid_main/evidence",
        "additional_seven_seed_dir": "artifacts/pq_s5b_revision/grid_extra/evidence",
        "sealed_inputs_modified": False,
        "training_or_retraining": False,
    }
    core["evidence_audit"] = audit
    output_paths = {
        "mechanism_sensitivity_grid.csv": os.path.join(
            out, "mechanism_sensitivity_grid.csv"),
        "mechanism_paper_regions.csv": os.path.join(
            out, "mechanism_paper_regions.csv"),
        "mechanism_paper_cells.csv": os.path.join(
            out, "mechanism_paper_cells.csv"),
        "mechanism_paper_core.json": os.path.join(
            out, "mechanism_paper_core.json"),
    }
    sensitivity_df.to_csv(output_paths["mechanism_sensitivity_grid.csv"], index=False)
    pd.DataFrame(
        core["regional_association_exploratory"]["records"]
    ).to_csv(output_paths["mechanism_paper_regions.csv"], index=False)
    cell_df.to_csv(output_paths["mechanism_paper_cells.csv"], index=False)
    with open(output_paths["mechanism_paper_core.json"], "w", encoding="utf-8") as f:
        json.dump(core, f, ensure_ascii=False, indent=1)

    source_paths = {
        "generation_code": os.path.abspath(__file__),
        "s5b_protocol_config": os.path.join(
            CFG.STUDY02_ROOT, "configs", "pq-s5b-revision-v1.json"),
        "environment_lock": os.path.join(
            CFG.STUDY02_ROOT, "configs", "pq-environment-v2.json"),
        "iid_three_seed_manifest": os.path.join(
            CFG.STUDY02_ROOT, "artifacts", "pq_iid_main", "manifest.json"),
        "s5b_revision_manifest": os.path.join(
            CFG.STUDY02_ROOT, "artifacts", "pq_s5b_revision", "manifest.json"),
    }
    derived_sha = {name: sha256_file(path) for name, path in output_paths.items()}
    source_sha = {
        name: {"path": _study_rel(path), "sha256": sha256_file(path)}
        for name, path in source_paths.items()
    }
    manifest = {
        "schema_version": 1,
        "analysis": "Study02 x_0.95 paper-core mechanism derivation",
        "protocol": "iid-v1 + study02-pq-s5b-revision-v1 grid extension",
        "generation_command": (
            "PQ_PROTOCOL=iid-v1 python -m study02pq.mechanism --paper-core-only"),
        "sha256_rule": "text files canonicalized to LF before SHA256",
        "bound_sources": source_sha,
        "derived_outputs_sha256": derived_sha,
        "evidence_audit": audit,
        "immutability": {
            "sealed_inputs_modified": False,
            "training_or_retraining": False,
        },
    }
    manifest_path = os.path.join(out, "manifest.json")
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=1)

    sha_paths = [*source_paths.values(), *output_paths.values(), manifest_path]
    with open(os.path.join(out, "SHA256SUMS"), "w", encoding="utf-8", newline="\n") as f:
        for path in sorted(sha_paths, key=_study_rel):
            f.write(f"{sha256_file(path)}  {_study_rel(path)}\n")
    return core


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
                "p_mean_cancel_exact": sp["mean_cancel_exact"],
                "q_mean_cancel_exact": sq["mean_cancel_exact"],
                "p_mean_s_norm": sp["mean_s_norm"], "q_mean_s_norm": sq["mean_s_norm"],
                "p_rms_u_par": sp["rms_u_par"], "q_rms_u_par": sq["rms_u_par"],
                "p_rms_u_perp": sp["rms_u_perp"], "q_rms_u_perp": sq["rms_u_perp"],
                "delta_rms_actual": sq["rms_actual"] - sp["rms_actual"],
                "delta_rms_proj": sq["rms_proj"] - sp["rms_proj"],
                "delta_rms_rem": sq["rms_rem"] - sp["rms_rem"],
                "delta_mean_align": sq["mean_align"] - sp["mean_align"],
                "delta_mean_cancel": sq["mean_cancel"] - sp["mean_cancel"],
                "delta_mean_cancel_exact": sq["mean_cancel_exact"]
                - sp["mean_cancel_exact"],
                "delta_mean_s_norm": sq["mean_s_norm"] - sp["mean_s_norm"],
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


def _quantiles(arr: np.ndarray, qs: tuple = (0.10, 0.25, 0.50, 0.75, 0.90, 0.99)) -> dict:
    """参数误差分位点（机器可读，供 10-PQ §2.2 引用）。"""
    qv = np.quantile(np.asarray(arr, dtype=np.float64), qs)
    return {f"p{int(100 * v)}": float(qv[i]) for i, v in enumerate(qs)}


def _cat(rows: dict, key: str) -> np.ndarray:
    return np.concatenate([r[key] for r in rows.values()])


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-boot", type=int, default=20000)
    ap.add_argument("--seed", action="append", type=int, default=None)
    ap.add_argument(
        "--paper-core-only", action="store_true",
        help="write 10-seed x0.95 paper-core derivatives without rewriting sealed S2 analysis")
    args = ap.parse_args()
    if args.paper_core_only:
        paper_out = os.path.join(
            os.path.dirname(CFG.ARTIFACT_DIR), "pq_paper_core", "analysis")
        core = write_paper_core_outputs(paper_out)
        sens = core["sensitivity_grid"]
        assoc = core["regional_association_exploratory"]["correlations"]
        comp = core["exact_compensation_x_0.95"]
        print("=== paper-core mechanism (10-seed frozen grid; analysis only) ===")
        print(f"sensitivity points={sens['n_points']}  "
              f"||s|| max/min={sens['component_ranges']['s_norm']['max_over_min']:.4f}  "
              f"max angle={sens['max_pairwise_direction_angle_degrees']:.4f} deg")
        print("regional Pearson r (||s|| vs P-Q rRMSE): "
              f"beta={assoc['beta']['pearson_r_s_norm_vs_q_advantage_abs']:.4f}  "
              f"gamma/eta={assoc['gamma_over_eta']['pearson_r_s_norm_vs_q_advantage_abs']:.4f}")
        print(f"exact cancellation means P={comp['mean_cancel_exact_P']:.6f}  "
              f"Q={comp['mean_cancel_exact_Q']:.6f}; "
              f"Q>P cells={comp['n_cell_pairs_Q_gt_P']}/{comp['n_cell_pairs']}")
        print("paper-core analysis written to", paper_out)
        return 0
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
               "mean_cancel_exact", "mean_s_norm",
               "rms_u_par", "rms_u_perp", "rms_u_beta", "rms_u_eta", "rms_u_gamma",
               "n_boundary", "corr_proj_actual", "identity_max_abs_err")
    for (n, fold_idx, seed) in sorted(stats_p):
        row = {"n": n, "fold": fold_idx + 1, "seed": seed}
        for m in metrics:
            row[f"p_{m}"] = stats_p[(n, fold_idx, seed)][m]
            row[f"q_{m}"] = stats_q[(n, fold_idx, seed)][m]
            row[f"delta_{m}"] = stats_q[(n, fold_idx, seed)][m] \
                - stats_p[(n, fold_idx, seed)][m]
        pair_rec.append(row)
    cell_df = pd.DataFrame(pair_rec)
    cell_df.to_csv(os.path.join(out, "mechanism_cell_pairs.csv"), index=False)

    # 设计级配对差值 + CI（关键机制量）
    design_keys = ("rms_actual", "rms_proj", "rms_rem", "mean_align",
                   "mean_cancel", "mean_cancel_exact", "mean_s_norm",
                   "rms_u_par", "rms_u_perp")
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
                     "delta_mean_cancel_exact", "delta_rms_u_par",
                     "delta_rms_u_perp"):
            mech_v = [r[mech] for r in rows if r["s1_mean_diff"] is not None]
            rev[mech] = _corr(md, mech_v)
        reversal[rtype] = rev

    # S2-002：真值点敏感度范数 ||s|| 与区域 Q-P 目标误差差的相关（探索性）
    sens = {}
    for rtype in ("beta", "gamma_over_eta", "n"):
        sub = region_df[region_df["region"] == rtype].sort_values("value")
        s_vals = sub["p_mean_s_norm"].tolist()  # P/Q 共享真值 → 相同
        d_vals = sub["delta_rms_actual"].tolist()
        sens[rtype] = {
            "mean_s_norm_by_region": {str(v): s for v, s in
                                      zip(sub["value"], s_vals)},
            "corr_mean_s_norm_delta_rms_actual": _corr(s_vals, d_vals),
        }
    sens["n"]["note"] = ("||s|| depends only on true params (not n); correlation "
                         "undefined by construction (constant across n)")

    # S2-004：参数误差分位点（机器可读，供 10-PQ §2.2 引用）
    u_quantiles = {
        name: {
            "u_beta": _quantiles(_cat(rows, "u_beta")),
            "u_eta": _quantiles(_cat(rows, "u_eta")),
            "u_gamma": _quantiles(_cat(rows, "u_gamma")),
            "frac_abs_u_beta_gt_1": float(
                np.mean(np.abs(_cat(rows, "u_beta")) > 1.0)),
        }
        for name, rows in (("P", rows_p), ("Q", rows_q))
    }

    summary = {
        "protocol": "iid-v1",
        "stage": "S2 mechanism (analysis-only; reuses frozen S1 evidence, no training)",
        "estimand_note": ("per held-out prediction: first-order projection proj=s.u and "
                          "nonlinear remainder rem (local-linearity diagnostic only); "
                          "exact no-remainder decomposition actual=C_beta+C_eta+C_gamma "
                          "with exact cancellation index; target-aligned vs true-point "
                          "local-tangent magnitudes; true-param sensitivity norm ||s||"),
        "formulas": {
            "x_p": "gamma + eta*(-ln p)^(1/beta), p=0.95",
            "u": "((beta_hat-beta)/beta, (eta_hat-eta)/eta, (gamma_hat-gamma)/eta)",
            "dx_dbeta": "-eta*a^(1/beta)*ln(a)/beta^2",
            "dx_deta": "a^(1/beta)",
            "dx_dgamma": "1",
            "s_beta": "dx_dbeta*beta/x", "s_eta": "dx_deta*eta/x",
            "s_gamma": "eta/x",
            "s_norm": "sqrt(s_beta^2 + s_eta^2 + s_gamma^2)",
            "proj": "s_beta*u_beta + s_eta*u_eta + s_gamma*u_gamma",
            "nonlinear_remainder": "actual - proj",
            "r2_origin": "1 - mean(rem^2)/mean(actual^2); origin-anchored, NOT "
                         "variance-based R^2 (equals var-R^2 only if mean(actual)=0)",
            "C_gamma": "(gamma_hat - gamma)/x",
            "C_eta": "0.5*(eta_hat-eta)*(t0+t1)/x",
            "C_beta": "0.5*(eta+eta_hat)*(t1-t0)/x",
            "exact_identity": "actual == C_beta + C_eta + C_gamma (up to floating precision)",
            "align": "|u_par|/|u|, u_par = u.s_hat = proj/|s|",
            "cancel": "(|c_beta|+|c_eta|+|c_gamma| - |proj|) / (|c_beta|+|c_eta|+|c_gamma|), "
                      "0 if denominator 0",
            "cancel_exact": "(|C_beta|+|C_eta|+|C_gamma| - |C_beta+C_eta+C_gamma|) / "
                            "(|C_beta|+|C_eta|+|C_gamma|), 0 if denominator 0 "
                            "(self-consistent within exact decomposition; "
                            "|C_beta+C_eta+C_gamma| == |actual| up to storage)",
        },
        "evidence": {
            "n_fits": 120, "n_pairs": n_pairs, "n_rows_per_route": n_rows,
            "evidence_dir": "artifacts/pq_iid_main/evidence",
            "baseline_tip": "928497b9",
            "s1_evidence_reused_as_is": True,
            "no_training": True,
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
                "mean_cancel_exact": sq["mean_cancel_exact"]
                - sp["mean_cancel_exact"],
                "mean_s_norm": sq["mean_s_norm"] - sp["mean_s_norm"],
                "rms_u_par": sq["rms_u_par"] - sp["rms_u_par"],
                "rms_u_perp": sq["rms_u_perp"] - sp["rms_u_perp"],
                "rms_u_norm": sq["rms_u_norm"] - sp["rms_u_norm"],
            },
        },
        "u_quantiles": u_quantiles,
        "sensitivity_norm_regional": sens,
        "exact_identity_check": {
            "identity_max_abs_err_P": sp["identity_max_abs_err"],
            "identity_max_abs_err_Q": sq["identity_max_abs_err"],
            "identity_max_abs_err_cell_max_P": max(
                s["identity_max_abs_err"] for s in stats_p.values()),
            "identity_max_abs_err_cell_max_Q": max(
                s["identity_max_abs_err"] for s in stats_q.values()),
            "note": ("max |actual - (C_beta+C_eta+C_gamma)|; float32-stored hats/rel_err "
                     "dominate the residual (exact identity holds to float precision on "
                     "float64 geometry)"),
        },
        "design_pair_deltas": design,
        "reversal_correlation_descriptive": reversal,
        "limits": [
            "analysis-only decomposition; observed association, not causal proof",
            "corr(proj,rem)~-1 is nearly forced algebraically when |proj|>>|actual|; "
            "it is a local-linearity diagnostic, not evidence of curvature-caused gain",
            "exact decomposition is an identity (up to float32 storage); cancel_exact "
            "quantifies compensating parameter changes, does not by itself prove causality",
            "mean ||s|| vs regional delta correlation is exploratory association over a "
            "handful of bins (8 beta, 5 goe, 4 n), unweighted; ||s|| is identical across n "
            "by construction so the n-correlation is undefined",
            "u_perp is a true-point local tangent-space approximation, not a global "
            "distance to the curved isoquantile manifold (Q is far from truth)",
            "design-level paired CIs are descriptive secondary support, not the primary inference",
            "3 seeds only; training-fold overlap under repeat-stratified splitting",
            "first-order projection uses sensitivity at true parameters; remainder absorbs "
            "second-order and finite-parameter effects and float32 storage of hats",
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
    print(f"r2_origin:        P={sp['r2_origin']:.4f}  Q={sq['r2_origin']:.4f}"
          f"  (origin-anchored, not var-R^2)")
    print(f"pooled mean_align:P={sp['mean_align']:.5f}  Q={sq['mean_align']:.5f}")
    print(f"pooled mean_cancel:P={sp['mean_cancel']:.5f}  Q={sq['mean_cancel']:.5f}")
    print(f"pooled mean_cancel_exact:P={sp['mean_cancel_exact']:.5f}  "
          f"Q={sq['mean_cancel_exact']:.5f}")
    print(f"pooled mean_s_norm:P={sp['mean_s_norm']:.4f}  Q={sq['mean_s_norm']:.4f}")
    print(f"exact identity max|actual-(C_b+C_e+C_g)|: P={sp['identity_max_abs_err']:.3e}  "
          f"Q={sq['identity_max_abs_err']:.3e}")
    for m in design_keys:
        d = design[m]
        print(f"  design pair {m}: delta={d['mean_delta']:.6f} "
              f"CI=[{d['ci_lo']:.6f},{d['ci_hi']:.6f}]")
    print("reversal corr (descriptive):")
    for rtype, rev in reversal.items():
        print(f"  {rtype}: " + ", ".join(f"{k}={v:.2f}" if v is not None else f"{k}=NA"
                                         for k, v in rev.items()))
    print("sensitivity-norm ||s|| vs regional delta_rms_actual (exploratory):")
    for rtype, d in sens.items():
        print(f"  {rtype}: corr={d['corr_mean_s_norm_delta_rms_actual']}")
    print("analysis written to", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
