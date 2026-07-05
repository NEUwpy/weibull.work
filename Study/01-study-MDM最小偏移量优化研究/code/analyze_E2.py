"""
Study/01 — E2 分析：L3 + L4 + L5 + L6 Oracle 层级

从共用 MC 扫描数据按 oracle 条件聚合，回答：
- 真参数已知时，精度上限在哪？
- 从 L3 到 L6 逐级提升，每级能好多少？
- 边际递减点在哪一级？

输入：artifacts/formal/shared_data/mc_scan_raw.csv
输出：artifacts/formal/E2_oracle_layers/
  - manifest.json
  - summary.json
  - ladder_L1_L6.csv         — L1-L6 阶梯表（核心表）
  - L3_by_beta.csv            — L3 按真β的δ*查表
  - L4_by_beta_n.csv          — L4 按真β+n的δ*查表
  - L5_by_beta_goe_n.csv      — L5 按真β+γ/η+n的δ*查表
  - L6_per_sample_delta.csv   — L6 逐样本最优δ分布

层级定义：
  L3: 每个真β一个δ*（oracle，β不可知→需NN）
  L4: 每个真β+n一个δ*（oracle）
  L5: 每个真β+γ/η+n一个δ*（oracle）
  L6: 每个样本一个δ*（hindsight oracle，上限）

聚合逻辑：
  对每个层级，在该层级的分组内找最优δ*，然后用该δ*算J₁。
  层级越高，分组越细，J₁越低（精度越高）。

关键约束：
  L3-L5 的 δ* 是在 grid 上搜索的（grid search），不是连续优化。
  L6 的 δ* 是逐样本在 grid 上取 argmin。
"""

import os
import sys
import json
import math

import numpy as np
import pandas as pd

# ── 路径设置 ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, r"D:\weibull\python")

from config import (
    BETA_GRID, ETA_GRID, GAMMA_OVER_ETA_GRID, N_GRID,
    DELTA_GRID, DEFAULT_DELTA, R_MAIN,
    SHARED_DATA_DIR, E2_OUTPUT_DIR,
)
from metrics import compute_j1
from utils import get_git_info, now_iso, now_local


# ============================================================
# 辅助：逐样本 J₁ 贡献（不开方）
# ============================================================

def j1_contribution(bh, eh, gh, beta, eta, gamma):
    """单样本 J₁ 贡献（未开方）。"""
    r_beta = (bh - beta) / beta
    r_eta = (eh - eta) / eta
    r_gamma = (gh - gamma) / eta
    return r_beta**2 + r_eta**2 + r_gamma**2


# ============================================================
# L3: 按真β的δ*
# ============================================================

def compute_L3(df):
    """L3: 每个真β一个最优δ*。

    对每个β，在该β的所有(η,γ,n)组合上平均J₁(δ)，取argmin。

    Returns:
        (l3_table_df, l3_j1_per_combo_df)
    """
    # 先算 (组合,δ) 的 J₁
    group_cols = ["beta", "eta", "gamma", "gamma_over_eta", "n", "delta"]
    j1_by_combo = []
    for keys, group in df.groupby(group_cols):
        beta, eta, gamma, goe, n, delta = keys
        valid = group[group["converged"]]
        if len(valid) == 0:
            continue
        ests = [{"beta_hat": r.beta_hat, "eta_hat": r.eta_hat, "gamma_hat": r.gamma_hat}
                for r in valid.itertuples()]
        j1 = compute_j1(ests, beta, eta, gamma)
        j1_by_combo.append({"beta": beta, "eta": eta, "gamma": gamma,
                            "gamma_over_eta": goe, "n": n, "delta": delta, "J1": j1})
    j1_df = pd.DataFrame(j1_by_combo)

    # 对每个β，跨所有(η,γ,n)组合平均J₁(δ)，取argmin
    l3_table = []
    l3_map = {}  # beta -> delta_star
    for beta_val in BETA_GRID:
        sub = j1_df[j1_df["beta"] == beta_val]
        curve = sub.groupby("delta")["J1"].mean().reset_index()
        idx_min = curve["J1"].idxmin()
        ds = curve.loc[idx_min, "delta"]
        l3_map[beta_val] = ds
        l3_table.append({
            "beta": beta_val,
            "delta_star_L3": ds,
            "J1_at_L3": curve.loc[idx_min, "J1"],
        })

    # L3 应用于每个组合的 J₁
    l3_per_combo = []
    for beta_val, ds in l3_map.items():
        sub = j1_df[(j1_df["beta"] == beta_val) & (j1_df["delta"] == ds)]
        for _, row in sub.iterrows():
            l3_per_combo.append({
                "beta": row["beta"], "eta": row["eta"], "gamma": row["gamma"],
                "gamma_over_eta": row["gamma_over_eta"], "n": row["n"],
                "J1_L3": row["J1"],
            })

    return pd.DataFrame(l3_table), pd.DataFrame(l3_per_combo)


# ============================================================
# L4: 按真β+n的δ*
# ============================================================

def compute_L4(df):
    """L4: 每个真(β,n)一个最优δ*。"""
    group_cols = ["beta", "eta", "gamma", "gamma_over_eta", "n", "delta"]
    j1_by_combo = []
    for keys, group in df.groupby(group_cols):
        beta, eta, gamma, goe, n, delta = keys
        valid = group[group["converged"]]
        if len(valid) == 0:
            continue
        ests = [{"beta_hat": r.beta_hat, "eta_hat": r.eta_hat, "gamma_hat": r.gamma_hat}
                for r in valid.itertuples()]
        j1 = compute_j1(ests, beta, eta, gamma)
        j1_by_combo.append({"beta": beta, "eta": eta, "gamma": gamma,
                            "gamma_over_eta": goe, "n": n, "delta": delta, "J1": j1})
    j1_df = pd.DataFrame(j1_by_combo)

    l4_table = []
    l4_map = {}  # (beta, n) -> delta_star
    for beta_val in BETA_GRID:
        for n_val in N_GRID:
            sub = j1_df[(j1_df["beta"] == beta_val) & (j1_df["n"] == n_val)]
            curve = sub.groupby("delta")["J1"].mean().reset_index()
            idx_min = curve["J1"].idxmin()
            ds = curve.loc[idx_min, "delta"]
            l4_map[(beta_val, n_val)] = ds
            l4_table.append({
                "beta": beta_val, "n": n_val,
                "delta_star_L4": ds, "J1_at_L4": curve.loc[idx_min, "J1"],
            })

    l4_per_combo = []
    for (beta_val, n_val), ds in l4_map.items():
        sub = j1_df[(j1_df["beta"] == beta_val) & (j1_df["n"] == n_val) & (j1_df["delta"] == ds)]
        for _, row in sub.iterrows():
            l4_per_combo.append({
                "beta": row["beta"], "eta": row["eta"], "gamma": row["gamma"],
                "gamma_over_eta": row["gamma_over_eta"], "n": row["n"],
                "J1_L4": row["J1"],
            })

    return pd.DataFrame(l4_table), pd.DataFrame(l4_per_combo)


# ============================================================
# L5: 按真β+γ/η+n的δ*
# ============================================================

def compute_L5(df):
    """L5: 每个真(β,γ/η,n)一个最优δ*。"""
    group_cols = ["beta", "eta", "gamma", "gamma_over_eta", "n", "delta"]
    j1_by_combo = []
    for keys, group in df.groupby(group_cols):
        beta, eta, gamma, goe, n, delta = keys
        valid = group[group["converged"]]
        if len(valid) == 0:
            continue
        ests = [{"beta_hat": r.beta_hat, "eta_hat": r.eta_hat, "gamma_hat": r.gamma_hat}
                for r in valid.itertuples()]
        j1 = compute_j1(ests, beta, eta, gamma)
        j1_by_combo.append({"beta": beta, "eta": eta, "gamma": gamma,
                            "gamma_over_eta": goe, "n": n, "delta": delta, "J1": j1})
    j1_df = pd.DataFrame(j1_by_combo)

    # L5 的分组 = (β, γ/η, n) = 每个参数组合本身
    # 所以 L5 对每个组合独立取最优 δ*
    l5_per_combo = []
    l5_table = []
    combo_cols = ["beta", "eta", "gamma", "gamma_over_eta", "n"]
    for keys, group in j1_df.groupby(combo_cols):
        beta, eta, gamma, goe, n = keys
        idx_min = group["J1"].idxmin()
        best_row = group.loc[idx_min]
        l5_per_combo.append({
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n,
            "J1_L5": best_row["J1"],
        })
        l5_table.append({
            "beta": beta, "gamma_over_eta": goe, "n": n,
            "delta_star_L5": best_row["delta"], "J1_at_L5": best_row["J1"],
        })

    return pd.DataFrame(l5_table), pd.DataFrame(l5_per_combo)


# ============================================================
# L6: 逐样本最优δ（hindsight oracle）
# ============================================================

def compute_L6(df):
    """L6: 每个样本在 δ grid 上取 argmin。

    对每个样本(repeat_id)，遍历所有δ，找使该单样本J₁贡献最小的δ。
    然后用该δ*的估计值算J₁。

    Returns:
        (l6_j1_per_combo_df, l6_delta_dist_df)
    """
    # 对每个(组合, repeat_id)，遍历δ找最优
    l6_best_contributions = {}  # (beta,eta,gamma,goe,n,rid) -> min_contribution
    l6_best_deltas = {}         # (beta,eta,gamma,goe,n,rid) -> delta_star

    group_cols = ["beta", "eta", "gamma", "gamma_over_eta", "n", "repeat_id"]
    for keys, group in df.groupby(group_cols):
        beta, eta, gamma, goe, n, rid = keys

        best_contrib = float("inf")
        best_delta = None

        for _, row in group.iterrows():
            if not row["converged"]:
                continue
            contrib = j1_contribution(row["beta_hat"], row["eta_hat"],
                                      row["gamma_hat"], beta, eta, gamma)
            if contrib < best_contrib:
                best_contrib = contrib
                best_delta = row["delta"]

        if best_delta is not None:
            l6_best_contributions[(beta, eta, gamma, goe, n, rid)] = best_contrib
            l6_best_deltas[(beta, eta, gamma, goe, n, rid)] = best_delta

    # 聚合到组合级 J₁
    l6_per_combo = []
    l6_delta_list = []

    for (beta, eta, gamma, goe, n, rid), contrib in l6_best_contributions.items():
        l6_delta_list.append({
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n, "repeat_id": rid,
            "delta_star_L6": l6_best_deltas[(beta, eta, gamma, goe, n, rid)],
            "j1_contribution": contrib,
        })

    # 按组合聚合
    l6_df = pd.DataFrame(l6_delta_list)
    for keys, group in l6_df.groupby(["beta", "eta", "gamma", "gamma_over_eta", "n"]):
        beta, eta, gamma, goe, n = keys
        j1 = math.sqrt(group["j1_contribution"].mean())
        l6_per_combo.append({
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n,
            "J1_L6": j1,
        })

    return pd.DataFrame(l6_per_combo), l6_df


# ============================================================
# 主流程
# ============================================================

def run_e2_analysis():
    """E2 主分析流程。"""
    print(f"\n{'='*60}")
    print(f"E2 分析：L3 + L4 + L5 + L6 Oracle 层级")
    print(f"{'='*60}")
    print(f"[{now_local()}] 读取 MC 扫描数据...")

    csv_path = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
    df = pd.read_csv(csv_path)
    print(f"  数据行数: {len(df):,}")

    os.makedirs(E2_OUTPUT_DIR, exist_ok=True)

    # ── L3 ──
    print(f"\n[{now_local()}] L3 按真β...")
    l3_table, l3_per_combo = compute_L3(df)
    print(f"  L3 查表:")
    for _, row in l3_table.iterrows():
        print(f"    β={row['beta']:.1f}: δ*={row['delta_star_L3']:.2f}, J₁={row['J1_at_L3']:.4f}")
    j1_l3 = l3_per_combo["J1_L3"].mean()

    # ── L4 ──
    print(f"\n[{now_local()}] L4 按真β+n...")
    l4_table, l4_per_combo = compute_L4(df)
    j1_l4 = l4_per_combo["J1_L4"].mean()
    print(f"  L4 J₁(mean) = {j1_l4:.4f}")

    # ── L5 ──
    print(f"\n[{now_local()}] L5 按真β+γ/η+n...")
    l5_table, l5_per_combo = compute_L5(df)
    j1_l5 = l5_per_combo["J1_L5"].mean()
    print(f"  L5 J₁(mean) = {j1_l5:.4f}")

    # ── L6 ──
    print(f"\n[{now_local()}] L6 逐样本 hindsight...")
    l6_per_combo, l6_delta_dist = compute_L6(df)
    j1_l6 = l6_per_combo["J1_L6"].mean()
    print(f"  L6 J₁(mean) = {j1_l6:.4f}")
    print(f"  L6 δ*分布: mean={l6_delta_dist['delta_star_L6'].mean():.3f}, "
          f"median={l6_delta_dist['delta_star_L6'].median():.3f}, "
          f"std={l6_delta_dist['delta_star_L6'].std():.3f}")

    # ── 从 E1 获取 Default 和 L1 的值 ──
    e1_summary_path = os.path.join(os.path.dirname(E2_OUTPUT_DIR),
                                   "E1_baseline", "summary.json")
    j1_default = j1_l1 = None
    delta_star_l1 = DEFAULT_DELTA
    if os.path.isfile(e1_summary_path):
        with open(e1_summary_path, "r") as f:
            e1 = json.load(f)
        j1_default = e1["results"]["default"]["J1_global_mean"]
        j1_l1 = e1["results"]["L1"]["J1_global_mean"]
        delta_star_l1 = e1["results"]["L1"]["delta_star"]

    # ── 阶梯表 ──
    print(f"\n[{now_local()}] 构建阶梯表...")
    ladder = []
    layers = [
        ("Default", delta_star_l1 if delta_star_l1 else 0.1, j1_default, "基线"),
        ("L1", delta_star_l1, j1_l1, "全局最优常数"),
        ("L3", None, j1_l3, "按真β (oracle)"),
        ("L4", None, j1_l4, "按真β+n (oracle)"),
        ("L5", None, j1_l5, "按真β+γ/η+n (oracle)"),
        ("L6", None, j1_l6, "逐样本 (hindsight oracle)"),
    ]

    prev_j1 = None
    for name, ds, j1, desc in layers:
        entry = {"layer": name, "delta_star": ds, "J1_mean": j1, "description": desc}
        if j1 is not None:
            if prev_j1 is not None and prev_j1 > 0:
                entry["improvement_vs_prev_pct"] = (1 - j1 / prev_j1) * 100
            if j1_default is not None and j1_default > 0:
                entry["improvement_vs_default_pct"] = (1 - j1 / j1_default) * 100
            prev_j1 = j1
        ladder.append(entry)

    ladder_df = pd.DataFrame(ladder)
    print(f"\n{'='*60}")
    print(f"L1-L6 阶梯表")
    print(f"{'='*60}")
    print(ladder_df.to_string(index=False))

    # ── 写输出 ──
    print(f"\n[{now_local()}] 写输出文件...")

    ladder_df.to_csv(os.path.join(E2_OUTPUT_DIR, "ladder_L1_L6.csv"), index=False)
    l3_table.to_csv(os.path.join(E2_OUTPUT_DIR, "L3_by_beta.csv"), index=False)
    l4_table.to_csv(os.path.join(E2_OUTPUT_DIR, "L4_by_beta_n.csv"), index=False)
    l5_table.to_csv(os.path.join(E2_OUTPUT_DIR, "L5_by_beta_goe_n.csv"), index=False)
    l6_delta_dist[["beta", "eta", "gamma", "gamma_over_eta", "n",
                    "delta_star_L6"]].to_csv(
        os.path.join(E2_OUTPUT_DIR, "L6_per_sample_delta.csv"), index=False)

    # L6 δ*分布统计
    l6_dist_summary = {
        "mean": float(l6_delta_dist["delta_star_L6"].mean()),
        "median": float(l6_delta_dist["delta_star_L6"].median()),
        "std": float(l6_delta_dist["delta_star_L6"].std()),
        "q25": float(l6_delta_dist["delta_star_L6"].quantile(0.25)),
        "q75": float(l6_delta_dist["delta_star_L6"].quantile(0.75)),
        "distribution": l6_delta_dist["delta_star_L6"].value_counts().sort_index().to_dict(),
    }

    summary = {
        "experiment": "E2",
        "created_at": now_iso(),
        "git_commit": get_git_info(),
        "results": {
            "ladder": ladder,
            "L3_table": l3_table.to_dict(orient="records"),
            "L4_table": l4_table.to_dict(orient="records"),
            "L5_table": l5_table.to_dict(orient="records"),
            "L6_delta_distribution": l6_dist_summary,
        },
    }
    with open(os.path.join(E2_OUTPUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    manifest = {
        "experiment": "E2",
        "created_at": now_iso(),
        "code_entry": "code/analyze_E2.py",
        "git_commit": get_git_info(),
        "input_data": "artifacts/formal/shared_data/mc_scan_raw.csv",
        "output_files": [
            "summary.json", "ladder_L1_L6.csv",
            "L3_by_beta.csv", "L4_by_beta_n.csv", "L5_by_beta_goe_n.csv",
            "L6_per_sample_delta.csv",
        ],
    }
    with open(os.path.join(E2_OUTPUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"E2 分析完成！")
    print(f"{'='*60}")
    print(f"\n阶梯结论：")
    for entry in ladder:
        name = entry["layer"]
        j1 = entry["J1_mean"]
        imp = entry.get("improvement_vs_default_pct")
        if j1 is not None:
            imp_str = f"  (vs Default {imp:+.1f}%)" if imp is not None else ""
            print(f"  {name:8s}: J₁ = {j1:.4f}{imp_str}")
    print(f"\n输出: {E2_OUTPUT_DIR}")


if __name__ == "__main__":
    run_e2_analysis()
