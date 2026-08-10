"""Study/02 P-Q 分析：主推断（设计单元×seed 聚类）+ 分层报告。

读取当前协议（CFG.PROTOCOL_VERSION）的 evidence/*.npz，计算模型级配对差值，
按协议做主推断（按 n 分层重采样 fold，并全局重采样 seed），输出
per-n/seed/fold/region/pooled 报告。

- v3（r4，gamma-holdout OOD 补充）：`summary_v3.json` + `boundary_diagnostic.json`，
  与 r4 完全一致（回归安全）。
- iid-v1（同分布主协议 S0 冻结候选）：`summary_iid.json` + `by_region.csv`。
  效应量按 `protocols/09-PQ-同分布主协议冻结.md` §3.3：hat_Delta（模型级配对差值等权均值）+
  rel_change=(rRMSE_Q-rRMSE_P)/rRMSE_P（分母显式）。主推断区间是设计级经验不确定性
  近似，随报告须附覆盖限制（训练折重叠、仅 3 seeds、单元内 MC 噪声被吸收）。

不再输出未经多重校正的逐 cell "显著数量"。
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

import numpy as np
import pandas as pd

STUDY02_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STUDY02_CODE_DIR)

from study02pq import config as CFG  # noqa: E402
from study02pq import evaluate as EVAL  # noqa: E402
from study02pq import run as RUN  # noqa: E402
from study02pq import training as TR  # noqa: E402


def cell_rel_sq(n, fold_idx, seed):
    rp, rq = RUN.load_rel_sq_from_evidence(
        TR.fit_id(n, fold_idx, seed, "P"), TR.fit_id(n, fold_idx, seed, "Q"))
    return rp, rq


def _per_combo_stats(seeds) -> pd.DataFrame:
    """每 (beta, gamma_over_eta, n) 组合的 pooled 统计（跨 fold×seed，描述性方向）。

    完全平衡设计下每组合 300 个 test 样本（5 folds × 60 repeats）。
    """
    acc = defaultdict(lambda: {"se_p": 0.0, "se_q": 0.0, "diff": 0.0, "n": 0})
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                ep = RUN.load_evidence(TR.fit_id(n, fold_idx, seed, "P"))
                eq = RUN.load_evidence(TR.fit_id(n, fold_idx, seed, "Q"))
                sp = np.asarray(ep["rel_err_sq"], dtype=np.float64)
                sq = np.asarray(eq["rel_err_sq"], dtype=np.float64)
                betas = np.asarray(ep["keys_beta"], dtype=np.float64)
                goes = np.asarray(ep["keys_gamma_over_eta"], dtype=np.float64)
                for b, g in set(zip(betas.tolist(), goes.tolist())):
                    m = (betas == b) & (goes == g)
                    key = (b, g, n)
                    acc[key]["se_p"] += float(np.sum(sp[m]))
                    acc[key]["se_q"] += float(np.sum(sq[m]))
                    acc[key]["diff"] += float(np.sum(sq[m] - sp[m]))
                    acc[key]["n"] += int(np.sum(m))
    rows = []
    for (b, g, nn), a in sorted(acc.items()):
        n_s = a["n"]
        rows.append({
            "beta": float(b), "gamma_over_eta": float(g), "n": int(nn),
            "p_rrmse": float(np.sqrt(a["se_p"] / n_s)),
            "q_rrmse": float(np.sqrt(a["se_q"] / n_s)),
            "mean_diff": float(a["diff"] / n_s),
            "n_samples": n_s,
        })
    return pd.DataFrame(rows)


def _write_v3_outputs(out, seeds, primary, p_rrmse, q_rrmse,
                      seed_means, per_n_rel, failures, n_boot):
    """r4/v3（gamma-holdout）输出：summary_v3.json + boundary_diagnostic.json（回归安全）。"""
    # 效应量分母显式（Codex R4-03）：论文主描述用 P 相对 Q 的误差下降
    p_error_reduction_vs_q = (q_rrmse - p_rrmse) / q_rrmse   # (Q-P)/Q，≈0.0807
    q_error_excess_vs_p = (q_rrmse - p_rrmse) / p_rrmse       # (Q-P)/P，≈0.0877

    summary = {
        "protocol": "v3_r4",
        "pooled": {
            "p_rrmse": float(p_rrmse), "q_rrmse": float(q_rrmse),
            "p_error_reduction_vs_q": float(p_error_reduction_vs_q),  # (Q-P)/Q
            "q_error_excess_vs_p": float(q_error_excess_vs_p),        # (Q-P)/P
            "mean_diff": primary["pooled_mean"],
            "ci_lo": primary["pooled_ci_lo"], "ci_hi": primary["pooled_ci_hi"],
            "n_design_units": 20,
        },
        "per_n": {
            str(n): {
                "p_rrmse": float(EVAL.rrmse(per_n_rel[n][0])),
                "q_rrmse": float(EVAL.rrmse(per_n_rel[n][1])),
                "mean_diff": primary["per_n_mean"][n],
                "ci_lo": primary["per_n_ci_lo"][n],
                "ci_hi": primary["per_n_ci_hi"][n],
            } for n in CFG.N_GRID
        },
        "per_seed_descriptive": {str(s): seed_means[s] for s in seeds},
        "n_boot": n_boot,
    }
    with open(os.path.join(out, "summary_v3.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    # R4-05 边界诊断：gamma_hat/min_x >= 阈值（解码器上边缘行为，非支撑违规）。
    # 对每个 cell 计 P/Q 边缘行数、误差占比；配对敏感性（移除 Q 边缘配对行后描述性重算）。
    threshold = 0.9999
    cell_rows = []
    clean_p, clean_q = [], []   # 配对移除 Q 边缘行后的样本（两侧同去）
    total_se_p = total_se_q = 0.0
    edge_se_p = edge_se_q = 0.0
    n_total = 0
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                ep = RUN.load_evidence(TR.fit_id(n, fold_idx, seed, "P"))
                eq = RUN.load_evidence(TR.fit_id(n, fold_idx, seed, "Q"))
                p_edge = (ep["gamma_hat"] / ep["min_x"]) >= threshold
                q_edge = (eq["gamma_hat"] / eq["min_x"]) >= threshold
                n_p = int(np.sum(p_edge)); n_q = int(np.sum(q_edge))
                keep = ~q_edge   # 配对敏感性：移除 Q 边缘行（P 同去）
                cell_rows.append({"n": n, "fold": fold_idx + 1, "seed": seed,
                                  "p_edge_rows": n_p, "q_edge_rows": n_q,
                                  "n_test": int(len(ep["rel_err_sq"]))})
                n_total += int(len(ep["rel_err_sq"]))
                total_se_p += float(np.sum(ep["rel_err_sq"]))
                total_se_q += float(np.sum(eq["rel_err_sq"]))
                edge_se_p += float(np.sum(ep["rel_err_sq"][p_edge]))
                edge_se_q += float(np.sum(eq["rel_err_sq"][q_edge]))
                clean_p.append(ep["rel_err_sq"][keep]); clean_q.append(eq["rel_err_sq"][keep])
    n_edge_q = int(sum(r["q_edge_rows"] for r in cell_rows))
    n_edge_p = int(sum(r["p_edge_rows"] for r in cell_rows))
    c_p = np.concatenate(clean_p); c_q = np.concatenate(clean_q)
    clean_prrmse = EVAL.rrmse(c_p); clean_qrrmse = EVAL.rrmse(c_q)
    # 完整配对证据总行数 = 144,000；保留行 = 总行 - Q 边缘配对行（143,955）
    n_retained = int(len(c_p))
    assert n_total == 144000, f"n_total_rows {n_total} != 144000"
    assert n_retained == n_total - n_edge_q, \
        f"n_retained {n_retained} != n_total {n_total} - n_edge_q {n_edge_q}"
    boundary_diag = {
        "threshold": threshold,
        "desc": "gamma_hat/min_x >= threshold at decoder upper edge; Q quantile-only objective "
                "parameter-boundary behavior, NOT an illegal fit (0 < gamma_hat < min(X) still holds)",
        "n_edge_rows_q": n_edge_q, "n_edge_rows_p": n_edge_p,
        "n_total_rows": n_total,
        "n_retained_rows_after_pairwise_exclusion": n_retained,
        "q_edge_error_share": float(edge_se_q / total_se_q) if total_se_q > 0 else None,
        "p_edge_error_share": float(edge_se_p / total_se_p) if total_se_p > 0 else None,
        "cells_with_q_edge": [r for r in cell_rows if r["q_edge_rows"] > 0],
        "paired_sensitivity_removing_q_edge_rows": {
            "p_rrmse": float(clean_prrmse), "q_rrmse": float(clean_qrrmse),
            "p_error_reduction_vs_q": float((clean_qrrmse - clean_prrmse) / clean_qrrmse)
                                      if clean_qrrmse > 0 else None,
        },
    }
    with open(os.path.join(out, "boundary_diagnostic.json"), "w", encoding="utf-8") as f:
        json.dump(boundary_diag, f, ensure_ascii=False, indent=1)

    print("=== v3/r4 summary (primary: (n,fold)xseed crossed) ===")
    print(f"pooled: P rRMSE={p_rrmse:.4f}  Q rRMSE={q_rrmse:.4f}  "
          f"p_error_reduction_vs_q={(q_rrmse - p_rrmse) / q_rrmse:.4f} "
          f"q_error_excess_vs_p={(q_rrmse - p_rrmse) / p_rrmse:.4f}")
    print(f"  mean_diff={primary['pooled_mean']:.5f}  CI=[{primary['pooled_ci_lo']:.5f},"
          f"{primary['pooled_ci_hi']:.5f}]")
    for n in CFG.N_GRID:
        print(f"  n={n}: mean_diff={primary['per_n_mean'][n]:.5f} "
              f"CI=[{primary['per_n_ci_lo'][n]:.5f},{primary['per_n_ci_hi'][n]:.5f}]")
    print("per-seed descriptive mean_diff:", {s: round(seed_means[s], 5) for s in seeds})
    print("failures:", failures)
    print("analysis written to", out)


def _write_iid_outputs(out, diffs, seeds, primary, p_rrmse, q_rrmse,
                       seed_means, per_n_rel, failures, n_boot):
    """同分布主协议（iid-v1）输出：summary_iid.json + by_region.csv。

    效应量按 `protocols/09-PQ-同分布主协议冻结.md` §3.3：hat_Delta + rel_change=(Q-P)/P（分母显式）；
    主推断区间是设计级经验不确定性近似。
    """
    # 每 fold 描述（方向；设计级只作描述，不作 CI）
    per_fold = {}
    for f in range(1, CFG.N_FOLDS + 1):
        vals = [diffs[n][f][si]
                for n in CFG.N_GRID for si in range(len(seeds))]
        rp_f = np.concatenate([cell_rel_sq(n, f - 1, seeds[si])[0]
                               for n in CFG.N_GRID for si in range(len(seeds))])
        rq_f = np.concatenate([cell_rel_sq(n, f - 1, seeds[si])[1]
                               for n in CFG.N_GRID for si in range(len(seeds))])
        per_fold[str(f)] = {
            "mean_diff": float(np.mean(vals)),
            "p_rrmse": EVAL.rrmse(rp_f), "q_rrmse": EVAL.rrmse(rq_f),
        }

    # 每 (beta, goe, n) 组合聚合 → by_region.csv 与方向
    combo = _per_combo_stats(seeds)
    region_rows = []
    region_dir = {"by_beta": {}, "by_gamma_over_eta": {}}
    for rtype, rcol in (("beta", "beta"), ("gamma_over_eta", "gamma_over_eta")):
        target = "by_beta" if rtype == "beta" else "by_gamma_over_eta"
        for value in sorted(combo[rcol].unique()):
            sub = combo[combo[rcol] == value]
            n_cells = int(len(sub))
            n_samp = int(sub["n_samples"].sum())
            p_r = float(np.sqrt((sub["p_rrmse"] ** 2 * sub["n_samples"]).sum() / n_samp))
            q_r = float(np.sqrt((sub["q_rrmse"] ** 2 * sub["n_samples"]).sum() / n_samp))
            md = float((sub["mean_diff"] * sub["n_samples"]).sum() / n_samp)
            q_better = int((sub["mean_diff"] < 0).sum())
            region_rows.append({
                "region": rtype, "value": float(value), "n_cells": n_cells,
                "n_samples": n_samp, "p_rrmse": p_r, "q_rrmse": q_r,
                "mean_diff": md, "q_better_cells": q_better,
            })
            region_dir[target][str(float(value))] = {
                "mean_diff": md, "q_better_cells": q_better, "n_cells": n_cells,
            }
    pd.DataFrame(region_rows).to_csv(os.path.join(out, "by_region.csv"), index=False)

    n_held_out = int(sum(len(per_n_rel[n][0]) for n in CFG.N_GRID))
    summary = {
        "protocol": "iid-v1",
        "estimand": ("Delta* = equal-weight superpopulation algorithmic performance gap over "
                     "the frozen parameter domain (each n, each cell within n) of "
                     "E[theta_Q(c) - theta_P(c)], expectation over independent fresh held-out "
                     "repeated samples AND training randomness under the frozen 180/60/60 "
                     "protocol (protocols/09-PQ-同分布主协议冻结.md §3.3)"),
        "finite_estimate": {
            "hat_delta": primary["pooled_mean"],
            "n_folds": CFG.N_FOLDS,
            "n_seeds": len(seeds),
            "n_design_units": len(CFG.N_GRID) * CFG.N_FOLDS,
            "n_model_level_contrasts": len(CFG.N_GRID) * CFG.N_FOLDS * len(seeds),
            "held_out_per_model": 2400,
            "n_held_out_samples": n_held_out,
            "resampling": "fold (stratified by n) x seed (global, with replacement)",
        },
        "pooled": {
            "p_rrmse": float(p_rrmse), "q_rrmse": float(q_rrmse),
            "rel_change": float((q_rrmse - p_rrmse) / p_rrmse),
            "rel_change_formula": "(rRMSE_Q - rRMSE_P) / rRMSE_P "
                                  "(09 §3.3; negative => Q better)",
            "q_improvement_vs_p": float((p_rrmse - q_rrmse) / p_rrmse),
            "q_improvement_formula": "(rRMSE_P - rRMSE_Q) / rRMSE_P "
                                     "(positive => Q better; descriptive)",
            "hat_delta": primary["pooled_mean"],
            "ci_lo": primary["pooled_ci_lo"], "ci_hi": primary["pooled_ci_hi"],
            "ci_level": 0.95,
        },
        "per_n": {
            str(n): {
                "p_rrmse": float(EVAL.rrmse(per_n_rel[n][0])),
                "q_rrmse": float(EVAL.rrmse(per_n_rel[n][1])),
                "mean_diff": primary["per_n_mean"][n],
                "ci_lo": primary["per_n_ci_lo"][n],
                "ci_hi": primary["per_n_ci_hi"][n],
            } for n in CFG.N_GRID
        },
        "per_seed_descriptive": {str(s): seed_means[s] for s in seeds},
        "per_fold_descriptive": per_fold,
        "by_region": region_dir,
        "coverage_limitations": [
            "overlapping training folds (each repeat trains in 3 of 5 folds)",
            "only 3 seeds (seed dimension severely undersampled)",
            "within-unit per-sample MC noise absorbed (design-level resamples unit means only)",
        ],
        "decision_rule": ("primary conclusion direction by whether hat_Delta CI contains 0; "
                          "by-n/seed/fold/region directions are descriptive support only"),
        "n_boot": n_boot,
    }
    with open(os.path.join(out, "summary_iid.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=1)

    print("=== iid-v1 summary (primary: fold x seed crossed, design-level) ===")
    print(f"pooled: P rRMSE={p_rrmse:.4f}  Q rRMSE={q_rrmse:.4f}  "
          f"rel_change=(Q-P)/P={(q_rrmse - p_rrmse) / p_rrmse:.4f}  "
          f"q_improvement=(P-Q)/P={(p_rrmse - q_rrmse) / p_rrmse:.4f}")
    print(f"  hat_delta={primary['pooled_mean']:.5f}  CI=[{primary['pooled_ci_lo']:.5f},"
          f"{primary['pooled_ci_hi']:.5f}]")
    for n in CFG.N_GRID:
        print(f"  n={n}: mean_diff={primary['per_n_mean'][n]:.5f} "
              f"CI=[{primary['per_n_ci_lo'][n]:.5f},{primary['per_n_ci_hi'][n]:.5f}]")
    print("per-seed descriptive mean_diff:",
          {s: round(seed_means[s], 5) for s in seeds})
    print("per-fold descriptive mean_diff:",
          {f: round(per_fold[str(f)]["mean_diff"], 5) for f in range(1, CFG.N_FOLDS + 1)})
    print("failures:", failures)
    print("analysis written to", out)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="append", type=int, default=None)
    ap.add_argument("--n-boot", type=int, default=2000)
    args = ap.parse_args()
    seeds = [int(s) for s in args.seed] if args.seed else [int(s) for s in CFG.SEEDS]
    out = os.path.join(CFG.ARTIFACT_DIR, "analysis")
    os.makedirs(out, exist_ok=True)

    # 模型级配对差值 d_{n,f,s}
    diffs = {n: {f: [] for f in range(1, CFG.N_FOLDS + 1)} for n in CFG.N_GRID}
    rel_sq_p_all, rel_sq_q_all = [], []
    for n in CFG.N_GRID:
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                rp, rq = cell_rel_sq(n, fold_idx, seed)
                diffs[n][fold_idx + 1].append(EVAL.cell_paired_diff(rp, rq))
                rel_sq_p_all.append(rp)
                rel_sq_q_all.append(rq)

    # 主推断
    primary = EVAL.primary_design_bootstrap(diffs, n_boot=args.n_boot)
    p_rrmse, q_rrmse = EVAL.pooled_rrmse_pair(
        np.concatenate(rel_sq_p_all), np.concatenate(rel_sq_q_all))

    # 每 seed 描述（3 seed 太少，不作 CI，只作变异报告）
    seed_means = {}
    for si, seed in enumerate(seeds):
        vals = [diffs[n][f][si]
                for n in CFG.N_GRID for f in range(1, CFG.N_FOLDS + 1)]
        seed_means[seed] = float(np.mean(vals))

    # 每 n 的 rel_sq 聚合（按 cell 收集）
    per_n_rel = {}
    for n in CFG.N_GRID:
        rp_n, rq_n = [], []
        for fold_idx in range(CFG.N_FOLDS):
            for seed in seeds:
                rp, rq = cell_rel_sq(n, fold_idx, seed)
                rp_n.append(rp); rq_n.append(rq)
        per_n_rel[n] = (np.concatenate(rp_n), np.concatenate(rq_n))

    # ---- 共享：by_n_seed 描述表 + 失败计数 ----
    n_seed_rows = []
    for n in CFG.N_GRID:
        for seed in seeds:
            vals = [diffs[n][f][seeds.index(seed)] for f in range(1, CFG.N_FOLDS + 1)]
            rp_all = np.concatenate(
                [cell_rel_sq(n, f - 1, seed)[0] for f in range(1, CFG.N_FOLDS + 1)])
            rq_all = np.concatenate(
                [cell_rel_sq(n, f - 1, seed)[1] for f in range(1, CFG.N_FOLDS + 1)])
            n_seed_rows.append({
                "n": n, "seed": seed,
                "p_rrmse": EVAL.rrmse(rp_all), "q_rrmse": EVAL.rrmse(rq_all),
                "mean_diff": float(np.mean(vals)),
            })
    pd.DataFrame(n_seed_rows).to_csv(
        os.path.join(out, "by_n_seed_descriptive.csv"), index=False)

    meta = RUN.per_fit_metrics(seeds)
    failures = EVAL.count_failures(meta.to_dict("records"))
    with open(os.path.join(out, "failure_counts.json"), "w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=1)

    # ---- 协议分派 ----
    if CFG.PROTOCOL_VERSION == "iid-v1":
        _write_iid_outputs(out, diffs, seeds, primary, p_rrmse, q_rrmse,
                           seed_means, per_n_rel, failures, args.n_boot)
    else:
        _write_v3_outputs(out, seeds, primary, p_rrmse, q_rrmse,
                          seed_means, per_n_rel, failures, args.n_boot)


if __name__ == "__main__":
    main()
