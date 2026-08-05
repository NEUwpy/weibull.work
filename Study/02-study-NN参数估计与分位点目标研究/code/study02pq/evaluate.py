"""Study/02 P-Q v2 评价与统计推断。

主指标（协议 v2 §6）：held-out x0.95 相对 RMSE = sqrt(mean((x_hat-x)/x)^2)。

推断层级（协议 v2 §6.2，Codex R1 REVISE 修正）：
- 主推断：设计单元 (n, fold) × seed 聚类。模型级配对差值 d_{n,f,s} =
  mean_样本(rel_sq_Q - rel_sq_P) 先在 cell 内求样本均值（每个模型 2400 个 held-out
  配对样本），再按 n 分层、对 fold 重采样、seed 块内保持（同一 fold 的三个 seed 不拆开），
  得到 pooled 效应与 95% CI。单元数 = 20（4 n × 5 fold）。
- 次要：逐样本 bootstrap 只在固定模型条件下给出 cell 内 Monte Carlo 区间，不作主推断。
- 不再报告未经多重校正的 60-cell "显著数量"。

加权规则：所有样本与 (n, fold, seed) 单元等权；失败/非有限项保留计数，不得静默删除。
"""

from __future__ import annotations

import numpy as np


def rrmse(rel_err_sq: np.ndarray) -> float:
    return float(np.sqrt(np.mean(rel_err_sq)))


# ----------------------------------------------------------------------
# cell 内指标（模型级）
# ----------------------------------------------------------------------

def cell_paired_diff(rel_sq_p: np.ndarray, rel_sq_q: np.ndarray) -> float:
    """一个 (n, fold, seed) 模型的模型级配对差值 = 该 cell 2400 个配对样本的均值。"""
    rel_sq_p = np.asarray(rel_sq_p, dtype=np.float64)
    rel_sq_q = np.asarray(rel_sq_q, dtype=np.float64)
    assert len(rel_sq_p) == len(rel_sq_q)
    return float(np.mean(rel_sq_q - rel_sq_p))


def cell_rrmse(rel_sq: np.ndarray) -> float:
    return rrmse(np.asarray(rel_sq, dtype=np.float64))


# ----------------------------------------------------------------------
# 主推断：(n, fold) 设计单元 × seed 聚类多路配对重采样
# ----------------------------------------------------------------------

def primary_design_bootstrap(cell_diffs_by_nfold, n_boot: int = 2000,
                             level: float = 0.95, rng: np.random.Generator = None):
    """主推断。cell_diffs_by_nfold: dict {n: {fold: [d_s1, d_s2, d_s3]}}。

    每轮：对每个 n，从 5 个 fold 有放回抽 5 个；对被抽中的 (n, fold) 保留其全部 seed 的
    模型级差值（块）；D* = 所有被抽中差值的均值。同时给出每 n 分层效应。
    """
    rng = rng if rng is not None else np.random.default_rng(20260805)
    n_values = sorted(cell_diffs_by_nfold.keys())
    # 预取：每个 (n, fold) 的 seed 差值数组
    folds = {n: sorted(cell_diffs_by_nfold[n].keys()) for n in n_values}
    diffs = {n: {f: np.asarray(cell_diffs_by_nfold[n][f], dtype=np.float64)
                 for f in folds[n]} for n in n_values}

    pooled_star = np.empty(n_boot)
    per_n_star = {n: np.empty(n_boot) for n in n_values}
    for b in range(n_boot):
        all_d, per_n_d = [], {}
        for n in n_values:
            # 有放回抽 5 个 fold（分层）
            sampled = rng.integers(0, len(folds[n]), size=len(folds[n]))
            n_d = []
            for fi in sampled:
                n_d.append(diffs[n][folds[n][fi]])
            n_arr = np.concatenate(n_d)
            all_d.append(n_arr)
            per_n_d[n] = n_arr
        pooled_star[b] = np.mean(np.concatenate(all_d))
        for n in n_values:
            per_n_star[n][b] = np.mean(per_n_d[n])

    alpha = 1.0 - level
    pooled_ci = np.percentile(pooled_star, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    per_n_ci = {n: np.percentile(per_n_star[n], [100 * alpha / 2, 100 * (1 - alpha / 2)])
                for n in n_values}
    return {
        "pooled_mean": float(np.mean(np.concatenate([
            np.concatenate([diffs[n][f] for f in folds[n]]) for n in n_values]))),
        "pooled_ci_lo": float(pooled_ci[0]), "pooled_ci_hi": float(pooled_ci[1]),
        "per_n_mean": {n: float(np.mean(np.concatenate([diffs[n][f] for f in folds[n]])))
                       for n in n_values},
        "per_n_ci_lo": {n: float(per_n_ci[n][0]) for n in n_values},
        "per_n_ci_hi": {n: float(per_n_ci[n][1]) for n in n_values},
        "n_boot": int(n_boot),
    }


def pooled_rrmse_pair(rel_sq_p_all: np.ndarray, rel_sq_q_all: np.ndarray):
    """pooled P/Q rRMSE（所有样本等权，描述性）。"""
    return rrmse(rel_sq_p_all), rrmse(rel_sq_q_all)


# ----------------------------------------------------------------------
# 次要：固定模型下的逐样本 Monte Carlo（不作主推断）
# ----------------------------------------------------------------------

def secondary_within_cell_mc(rel_sq_p: np.ndarray, rel_sq_q: np.ndarray,
                             n_boot: int = 2000, level: float = 0.95,
                             rng: np.random.Generator = None):
    """固定模型条件下的 cell 内逐样本重采样区间（次要）。"""
    rel_sq_p = np.asarray(rel_sq_p, dtype=np.float64)
    rel_sq_q = np.asarray(rel_sq_q, dtype=np.float64)
    n = len(rel_sq_p)
    d = rel_sq_q - rel_sq_p
    rng = rng if rng is not None else np.random.default_rng(20260805)
    boot = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot[b] = d[idx].mean()
    alpha = 1.0 - level
    lo, hi = np.percentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {"mean": float(d.mean()), "ci_lo": float(lo), "ci_hi": float(hi),
            "n": int(n), "n_boot": int(n_boot)}


def count_failures(meta_rows: list[dict]) -> dict:
    n_fit = len(meta_rows)
    n_nan = sum(1 for r in meta_rows if r.get("nan_flag"))
    n_nonconv = sum(1 for r in meta_rows if not r.get("converged"))
    n_nonfinite_pred = sum(1 for r in meta_rows if r.get("n_nonfinite", 0) > 0)
    n_illegal = sum(1 for r in meta_rows if r.get("n_illegal", 0) > 0)
    n_support_viol = sum(1 for r in meta_rows if r.get("n_support_viol", 0) > 0)
    return {
        "n_fits": n_fit,
        "n_nan_train": n_nan,
        "n_nonconverged": n_nonconv,
        "n_with_nonfinite_pred": n_nonfinite_pred,
        "n_with_illegal_param": n_illegal,
        "n_with_support_viol": n_support_viol,
    }
