"""Study/02 P-Q 评价：held-out x0.95 相对 RMSE、配对差值、配对 bootstrap CI。

主指标（协议 §6）：rRMSE = sqrt(mean((x_hat-x)/x)^2)。
配对差值：逐样本 rel_err_sq_Q - rel_err_sq_P；bootstrap 对样本重采样。
加权规则：所有样本等权；缺失/非有限样本保留计数，不得静默删除。
"""

from __future__ import annotations

import numpy as np


def rrmse(rel_err_sq: np.ndarray) -> float:
    return float(np.sqrt(np.mean(rel_err_sq)))


def bootstrap_ci_paired(rel_sq_p: np.ndarray, rel_sq_q: np.ndarray,
                        n_boot: int = 2000, level: float = 0.95,
                        rng: np.random.Generator = None):
    """对样本重采样的配对 bootstrap。

    返回 dict：mean_diff（Q 指标 - P 指标，平方误差空间）、CI、P/Q 指标、n。
    """
    rel_sq_p = np.asarray(rel_sq_p, dtype=np.float64)
    rel_sq_q = np.asarray(rel_sq_q, dtype=np.float64)
    assert len(rel_sq_p) == len(rel_sq_q)
    n = len(rel_sq_p)
    d = rel_sq_q - rel_sq_p
    rng = rng if rng is not None else np.random.default_rng(20260805)
    boot_diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        boot_diffs[b] = d[idx].mean()
    alpha = 1.0 - level
    lo, hi = np.percentile(boot_diffs, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return {
        "n": int(n),
        "p_metric": float(np.mean(rel_sq_p)),      # 平方误差空间均值
        "q_metric": float(np.mean(rel_sq_q)),
        "p_rrmse": rrmse(rel_sq_p),
        "q_rrmse": rrmse(rel_sq_q),
        "mean_diff": float(np.mean(d)),            # Q - P
        "ci_lo": float(lo), "ci_hi": float(hi),
        "n_boot": int(n_boot),
    }


def summary_row(m, fit_id: str = "", n_val=None, seed=None, fold=None,
                group="") -> dict:
    return {
        "group": group, "n": n_val, "seed": seed, "fold": fold, "fit_id": fit_id,
        "n_test": m["n"], "p_rrmse": m["p_rrmse"], "q_rrmse": m["q_rrmse"],
        "p_metric": m["p_metric"], "q_metric": m["q_metric"],
        "mean_diff": m["mean_diff"], "ci_lo": m["ci_lo"], "ci_hi": m["ci_hi"],
        "rel_improve": (m["q_rrmse"] - m["p_rrmse"]) / m["p_rrmse"]
                       if m["p_rrmse"] > 0 else float("nan"),
    }


def paired_stats_by_cells(cells):
    """cells: list of (label_dict, rel_sq_p, rel_sq_q)。逐 cell 汇总。"""
    rows = []
    for label, rp, rq in cells:
        m = bootstrap_ci_paired(rp, rq)
        rows.append(summary_row(m, **label))
    return rows


def pooled_paired(rel_sq_p_all: np.ndarray, rel_sq_q_all: np.ndarray,
                  n_boot: int = 2000, level: float = 0.95):
    return bootstrap_ci_paired(rel_sq_p_all, rel_sq_q_all, n_boot, level)


def count_failures(meta_rows: list[dict]) -> dict:
    n_fit = len(meta_rows)
    n_nan = sum(1 for r in meta_rows if r.get("nan_flag"))
    n_nonconv = sum(1 for r in meta_rows if not r.get("converged"))
    n_nonfinite_pred = sum(1 for r in meta_rows if r.get("n_nonfinite", 0) > 0)
    n_illegal = sum(1 for r in meta_rows if r.get("n_illegal", 0) > 0)
    return {
        "n_fits": n_fit,
        "n_nan_train": n_nan,
        "n_nonconverged": n_nonconv,
        "n_with_nonfinite_pred": n_nonfinite_pred,
        "n_with_illegal_param": n_illegal,
    }
