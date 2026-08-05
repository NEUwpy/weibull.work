"""Study/02 P-Q 结果分析：分层配对汇总、失败计数、方向一致性。

读取 artifacts/pq 的预测/指标，输出 per-n、per-seed、per-fold、pooled 配对汇总
与失败/方向统计，写入 artifacts/pq/analysis/。用于 `04-PQ-结果报告.md`。
"""

from __future__ import annotations

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

KEY_COLS = ["beta", "gamma_over_eta", "n", "repeat_id"]


def load_pair(n, fold_idx, seed):
    ps = pd.read_csv(RUN.prediction_csv_path(TR.fit_id(n, fold_idx, seed, "P")))
    qs = pd.read_csv(RUN.prediction_csv_path(TR.fit_id(n, fold_idx, seed, "Q")))
    m = ps.merge(qs, on=KEY_COLS, suffixes=("_p", "_q"))
    return m["rel_err_sq_p"].to_numpy(), m["rel_err_sq_q"].to_numpy()


def concat_pairs(pairs):
    return np.concatenate([p[0] for p in pairs]), np.concatenate([p[1] for p in pairs])


def grouped_summary(group_pairs, label) -> dict:
    rp, rq = concat_pairs(group_pairs)
    m = EVAL.bootstrap_ci_paired(rp, rq)
    return EVAL.summary_row(m, group=label)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", action="append", type=int, default=None)
    args = ap.parse_args()
    seeds = [int(s) for s in args.seed] if args.seed else [int(s) for s in CFG.SEEDS]
    out = os.path.join(CFG.ARTIFACT_DIR, "analysis")
    os.makedirs(out, exist_ok=True)

    # 每个 (n, fold, seed) 的配对样本
    cell = {}
    for n in CFG.N_GRID:
        for fold in range(CFG.N_FOLDS):
            for seed in seeds:
                cell[(n, fold + 1, seed)] = load_pair(n, fold, seed)

    rows = []
    # 逐 cell
    for (n, fold, seed), (rp, rq) in cell.items():
        m = EVAL.bootstrap_ci_paired(rp, rq)
        rows.append(EVAL.summary_row(m, group="cell", n_val=n, fold=fold, seed=seed))
    # 每 seed（跨 n、fold）
    for seed in seeds:
        sub = {k: v for k, v in cell.items() if k[2] == seed}
        rows.append(grouped_summary(list(sub.values()), f"seed_{seed}"))
    # 每 n（跨 fold、seed）
    for n in CFG.N_GRID:
        sub = {k: v for k, v in cell.items() if k[0] == n}
        rows.append(grouped_summary(list(sub.values()), f"n_{n}"))
    # 每 fold（跨 n、seed）
    for fold in range(1, CFG.N_FOLDS + 1):
        sub = {k: v for k, v in cell.items() if k[1] == fold}
        rows.append(grouped_summary(list(sub.values()), f"fold_{fold}"))
    # pooled（全部）
    rows.append(grouped_summary(list(cell.values()), "pooled"))

    summary = pd.DataFrame(rows)
    summary.to_csv(os.path.join(out, "paired_summary_by_group.csv"), index=False)

    # 失败计数
    meta = RUN.per_fit_metrics(seeds)
    failures = EVAL.count_failures(meta.to_dict("records"))
    with open(os.path.join(out, "failure_counts.json"), "w", encoding="utf-8") as f:
        json.dump(failures, f, ensure_ascii=False, indent=1)

    # 方向一致性：每个 cell 的 mean_diff 符号
    dir_rows = []
    for (n, fold, seed), (rp, rq) in cell.items():
        m = EVAL.bootstrap_ci_paired(rp, rq)
        dir_rows.append({"n": n, "fold": fold, "seed": seed,
                         "mean_diff": m["mean_diff"],
                         "ci_lo": m["ci_lo"], "ci_hi": m["ci_hi"],
                         "q_better": m["mean_diff"] < 0,
                         "signif": (m["ci_lo"] < 0 < m["ci_hi"]) is False})
    pd.DataFrame(dir_rows).to_csv(os.path.join(out, "direction_by_cell.csv"), index=False)

    # 每 seed 方向
    seed_dir = []
    for seed in seeds:
        sub = [r for r in dir_rows if r["seed"] == seed]
        q_wins = sum(1 for r in sub if r["q_better"])
        p_wins = len(sub) - q_wins
        seed_dir.append({"seed": seed, "n_cells": len(sub),
                         "q_better_cells": q_wins, "p_better_cells": p_wins})
    pd.DataFrame(seed_dir).to_csv(os.path.join(out, "direction_by_seed.csv"), index=False)

    # 配对一致性与合法输出（诊断）
    print("analysis written to", out)
    print(summary[["group", "n_test", "p_rrmse", "q_rrmse", "mean_diff",
                   "ci_lo", "ci_hi", "rel_improve"]].to_string(index=False))
    print("failures:", failures)


if __name__ == "__main__":
    main()
