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
  - results.csv               — 规范逐条结果
  - ladder_L1_L6.csv          — L1-L6 阶梯表（核心表）
  - L3_by_beta.csv            — L3 按真β的δ*查表
  - L4_by_beta_n.csv          — L4 按真β+n的δ*查表
  - L5_by_beta_goe_n.csv      — L5 按真β+γ/η+n的δ*查表
  - L6_per_sample_delta.csv   — L6 逐样本最优δ分布

J₁ 聚合规则（严格遵守 02-实验协议.md STOP 条件#3）：
  层级聚合时：先收集分组内所有样本的未开方 j1_sq → mean → sqrt
  绝不平均已开方的 J₁ 值。

层级定义：
  L3: 每个真β一个δ*（oracle，β不可知→需NN）
  L4: 每个真β+n一个δ*（oracle）
  L5: 每个真β+γ/η+n一个δ*（oracle）
  L6: 每个样本一个δ*（hindsight oracle，上限）
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
from metrics import j1_single
from utils import get_git_info, now_iso, now_local

COMBO_COLS = ["beta", "eta", "gamma", "gamma_over_eta", "n"]


# ============================================================
# 步骤1：逐样本未开方贡献 j1_sq
# ============================================================

def build_j1_sq_table(df):
    """对每行计算未开方 J₁ 贡献。"""
    df = df[df["converged"]].copy()
    df["j1_sq"] = (
        ((df["beta_hat"] - df["beta"]) / df["beta"]) ** 2
        + ((df["eta_hat"] - df["eta"]) / df["eta"]) ** 2
        + ((df["gamma_hat"] - df["gamma"]) / df["eta"]) ** 2
    )
    df = df[np.isfinite(df["j1_sq"])]
    return df


# ============================================================
# 通用层级聚合：在分组上找最优δ，用正确J₁聚合
# ============================================================

def find_best_delta_for_group(j1_sq_df, group_filter, group_cols):
    """对给定分组，在 δ grid 上找最优 δ*。

    正确流程：
    1. 该分组内，按 δ 分组，对 j1_sq 取 mean → sqrt → 得 J₁(δ)
    2. 取 argmin(δ)

    Args:
        j1_sq_df: 全局 j1_sq 表
        group_filter: 布尔Series，标记属于该分组的行
        group_cols: 该分组的参数列（用于输出）

    Returns:
        (delta_star, J1_at_star) — 该分组的最优δ和对应J₁
    """
    sub = j1_sq_df[group_filter]
    if len(sub) == 0:
        return None, None

    curve = sub.groupby("delta")["j1_sq"].mean().reset_index()
    curve["J1"] = np.sqrt(curve["j1_sq"])
    idx_min = curve["J1"].idxmin()
    return curve.loc[idx_min, "delta"], curve.loc[idx_min, "J1"]


def apply_layer_to_combos(j1_sq_df, delta_map, group_keys):
    """将层级的 δ* 映射应用到每个组合，返回逐组合 J₁。

    正确流程：对每个组合，用该分组的 δ*，收集该组合所有样本的 j1_sq → mean → sqrt

    Args:
        j1_sq_df: 全局 j1_sq 表
        delta_map: dict, group_key_tuple -> delta_star
        group_keys: list of str, delta_map 的 key 对应的列名

    Returns:
        DataFrame: COMBO_COLS + ["J1_layer"]
    """
    results = []
    for gkey_tuple, ds in delta_map.items():
        # 构建该分组的过滤条件
        mask = pd.Series([True] * len(j1_sq_df), index=j1_sq_df.index)
        for col, val in zip(group_keys, gkey_tuple):
            mask &= (j1_sq_df[col] == val)

        # 该分组下每个组合，用 ds 算 J₁
        sub = j1_sq_df[mask & (j1_sq_df["delta"] == ds)]
        for combo_keys, combo_group in sub.groupby(COMBO_COLS):
            j1 = math.sqrt(combo_group["j1_sq"].mean())
            beta, eta, gamma, goe, n = combo_keys
            results.append({
                "beta": beta, "eta": eta, "gamma": gamma,
                "gamma_over_eta": goe, "n": n,
                "J1_layer": j1,
            })

    return pd.DataFrame(results)


def compute_layer_global_j1(j1_sq_df, delta_map, group_keys):
    """计算层级的全局 J₁（正确聚合）。

    对每个分组用其 δ*，收集该分组所有样本的 j1_sq，
    然后跨所有分组汇总，取总 mean(j1_sq) → sqrt。

    Args:
        j1_sq_df: 全局 j1_sq 表
        delta_map: dict, group_key_tuple -> delta_star
        group_keys: list of str

    Returns:
        float: 全局 J₁
    """
    parts = []
    for gkey_tuple, ds in delta_map.items():
        mask = pd.Series([True] * len(j1_sq_df), index=j1_sq_df.index)
        for col, val in zip(group_keys, gkey_tuple):
            mask &= (j1_sq_df[col] == val)
        sub = j1_sq_df[mask & (j1_sq_df["delta"] == ds)]
        parts.append(sub)

    all_sub = pd.concat(parts)
    return math.sqrt(all_sub["j1_sq"].mean())


# ============================================================
# L3: 按真β
# ============================================================

def compute_L3(j1_sq_df):
    """L3: 每个真β一个最优δ*。"""
    l3_table = []
    delta_map = {}
    for beta_val in BETA_GRID:
        mask = (j1_sq_df["beta"] == beta_val)
        ds, j1 = find_best_delta_for_group(j1_sq_df, mask, ["beta"])
        delta_map[(beta_val,)] = ds
        l3_table.append({"beta": beta_val, "delta_star_L3": ds, "J1_at_L3": j1})

    per_combo = apply_layer_to_combos(j1_sq_df, delta_map, ["beta"])
    global_j1 = compute_layer_global_j1(j1_sq_df, delta_map, ["beta"])
    return pd.DataFrame(l3_table), per_combo, global_j1


# ============================================================
# L4: 按真β+n
# ============================================================

def compute_L4(j1_sq_df):
    """L4: 每个真(β,n)一个最优δ*。"""
    l4_table = []
    delta_map = {}
    for beta_val in BETA_GRID:
        for n_val in N_GRID:
            mask = (j1_sq_df["beta"] == beta_val) & (j1_sq_df["n"] == n_val)
            ds, j1 = find_best_delta_for_group(j1_sq_df, mask, ["beta", "n"])
            delta_map[(beta_val, n_val)] = ds
            l4_table.append({"beta": beta_val, "n": n_val,
                             "delta_star_L4": ds, "J1_at_L4": j1})

    per_combo = apply_layer_to_combos(j1_sq_df, delta_map, ["beta", "n"])
    global_j1 = compute_layer_global_j1(j1_sq_df, delta_map, ["beta", "n"])
    return pd.DataFrame(l4_table), per_combo, global_j1


# ============================================================
# L5: 按真β+γ/η+n（= 每个组合独立最优）
# ============================================================

def compute_L5(j1_sq_df):
    """L5: 每个真(β,γ/η,n)组合一个最优δ*。

    L5 的分组粒度 = 参数组合本身（因为 η 固定=1.0）。
    """
    l5_table = []
    delta_map = {}
    for beta_val in BETA_GRID:
        for goe in GAMMA_OVER_ETA_GRID:
            for n_val in N_GRID:
                mask = ((j1_sq_df["beta"] == beta_val) &
                        (j1_sq_df["gamma_over_eta"] == goe) &
                        (j1_sq_df["n"] == n_val))
                ds, j1 = find_best_delta_for_group(j1_sq_df, mask,
                                                    ["beta", "gamma_over_eta", "n"])
                delta_map[(beta_val, goe, n_val)] = ds
                l5_table.append({"beta": beta_val, "gamma_over_eta": goe,
                                 "n": n_val, "delta_star_L5": ds, "J1_at_L5": j1})

    per_combo = apply_layer_to_combos(j1_sq_df, delta_map,
                                       ["beta", "gamma_over_eta", "n"])
    global_j1 = compute_layer_global_j1(j1_sq_df, delta_map,
                                         ["beta", "gamma_over_eta", "n"])
    return pd.DataFrame(l5_table), per_combo, global_j1


# ============================================================
# L6: 逐样本 hindsight oracle
# ============================================================

def compute_L6(j1_sq_df):
    """L6: 每个样本在 δ grid 上取 argmin j1_sq。

    正确流程：
    1. 对每个(组合, repeat_id)，遍历δ找最小 j1_sq 的那个δ
    2. 收集所有样本的最小 j1_sq
    3. 跨所有样本取 mean(j1_sq) → sqrt
    """
    sample_cols = COMBO_COLS + ["repeat_id"]

    best_records = []
    for keys, group in j1_sq_df.groupby(sample_cols):
        idx_min = group["j1_sq"].idxmin()
        best_row = group.loc[idx_min]
        best_records.append({
            "beta": best_row["beta"], "eta": best_row["eta"],
            "gamma": best_row["gamma"], "gamma_over_eta": best_row["gamma_over_eta"],
            "n": best_row["n"], "repeat_id": best_row["repeat_id"],
            "delta_star_L6": best_row["delta"],
            "j1_sq_best": best_row["j1_sq"],
        })

    l6_df = pd.DataFrame(best_records)

    # 全局 J₁：所有样本的最优 j1_sq 取 mean → sqrt
    j1_l6_global = math.sqrt(l6_df["j1_sq_best"].mean())

    # 逐组合 J₁（展示用）
    per_combo = []
    for keys, group in l6_df.groupby(COMBO_COLS):
        beta, eta, gamma, goe, n = keys
        j1 = math.sqrt(group["j1_sq_best"].mean())
        per_combo.append({
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n, "J1_L6": j1,
        })

    return pd.DataFrame(per_combo), l6_df, j1_l6_global


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

    print(f"\n[{now_local()}] 计算逐样本 j1_sq...")
    j1_sq_df = build_j1_sq_table(df)
    print(f"  有效行数: {len(j1_sq_df):,}")

    os.makedirs(E2_OUTPUT_DIR, exist_ok=True)

    # ── L3 ──
    print(f"\n[{now_local()}] L3 按真β...")
    l3_table, l3_per_combo, j1_l3 = compute_L3(j1_sq_df)
    print(f"  L3 查表:")
    for _, row in l3_table.iterrows():
        print(f"    β={row['beta']:.1f}: δ*={row['delta_star_L3']:.2f}, J₁={row['J1_at_L3']:.4f}")
    print(f"  L3 全局 J₁ = {j1_l3:.4f}")

    # ── L4 ──
    print(f"\n[{now_local()}] L4 按真β+n...")
    l4_table, l4_per_combo, j1_l4 = compute_L4(j1_sq_df)
    print(f"  L4 全局 J₁ = {j1_l4:.4f}")

    # ── L5 ──
    print(f"\n[{now_local()}] L5 按真β+γ/η+n...")
    l5_table, l5_per_combo, j1_l5 = compute_L5(j1_sq_df)
    print(f"  L5 全局 J₁ = {j1_l5:.4f}")

    # ── L6 ──
    print(f"\n[{now_local()}] L6 逐样本 hindsight...")
    l6_per_combo, l6_delta_dist, j1_l6 = compute_L6(j1_sq_df)
    print(f"  L6 全局 J₁ = {j1_l6:.4f}")
    print(f"  L6 δ*分布: mean={l6_delta_dist['delta_star_L6'].mean():.3f}, "
          f"median={l6_delta_dist['delta_star_L6'].median():.3f}, "
          f"std={l6_delta_dist['delta_star_L6'].std():.3f}")

    # ── 从 E1 获取 Default 和 L1 ──
    e1_summary_path = os.path.join(os.path.dirname(E2_OUTPUT_DIR),
                                   "E1_baseline", "summary.json")
    j1_default = j1_l1 = None
    delta_star_l1 = DEFAULT_DELTA
    if os.path.isfile(e1_summary_path):
        with open(e1_summary_path, "r") as f:
            e1 = json.load(f)
        j1_default = e1["results"]["default"]["J1_global"]
        j1_l1 = e1["results"]["L1"]["J1_global"]
        delta_star_l1 = e1["results"]["L1"]["delta_star"]

    # ── 阶梯表 ──
    print(f"\n[{now_local()}] 构建阶梯表...")
    ladder = []
    layers = [
        ("Default", delta_star_l1, j1_default, "基线"),
        ("L1", delta_star_l1, j1_l1, "全局最优常数"),
        ("L3", None, j1_l3, "按真β (oracle)"),
        ("L4", None, j1_l4, "按真β+n (oracle)"),
        ("L5", None, j1_l5, "按真β+γ/η+n (oracle)"),
        ("L6", None, j1_l6, "逐样本 (hindsight oracle)"),
    ]

    prev_j1 = None
    for name, ds, j1, desc in layers:
        entry = {"layer": name, "delta_star": ds, "J1_global": j1, "description": desc}
        if j1 is not None:
            if prev_j1 is not None and prev_j1 > 0:
                entry["improvement_vs_prev_pct"] = float((1 - j1 / prev_j1) * 100)
            if j1_default is not None and j1_default > 0:
                entry["improvement_vs_default_pct"] = float((1 - j1 / j1_default) * 100)
            prev_j1 = j1
        ladder.append(entry)

    ladder_df = pd.DataFrame(ladder)
    print(f"\n{'='*60}")
    print(f"L1-L6 阶梯表（正确 J₁ 聚合）")
    print(f"{'='*60}")
    print(ladder_df.to_string(index=False))

    # ── 写输出 ──
    print(f"\n[{now_local()}] 写输出文件...")

    ladder_df.to_csv(os.path.join(E2_OUTPUT_DIR, "ladder_L1_L6.csv"), index=False)
    l3_table.to_csv(os.path.join(E2_OUTPUT_DIR, "L3_by_beta.csv"), index=False)
    l4_table.to_csv(os.path.join(E2_OUTPUT_DIR, "L4_by_beta_n.csv"), index=False)
    l5_table.to_csv(os.path.join(E2_OUTPUT_DIR, "L5_by_beta_goe_n.csv"), index=False)
    l6_delta_dist[["beta", "eta", "gamma", "gamma_over_eta", "n",
                    "repeat_id", "delta_star_L6"]].to_csv(
        os.path.join(E2_OUTPUT_DIR, "L6_per_sample_delta.csv"), index=False)

    # results.csv（逐组合 J₁ 各层级）
    results = l3_per_combo.rename(columns={"J1_layer": "J1_L3"})
    results = results.merge(
        l4_per_combo.rename(columns={"J1_layer": "J1_L4"}), on=COMBO_COLS)
    results = results.merge(
        l5_per_combo.rename(columns={"J1_layer": "J1_L5"}), on=COMBO_COLS)
    results = results.merge(l6_per_combo, on=COMBO_COLS)
    results.to_csv(os.path.join(E2_OUTPUT_DIR, "results.csv"), index=False)

    # L6 δ*分布统计
    l6_dist_summary = {
        "mean": float(l6_delta_dist["delta_star_L6"].mean()),
        "median": float(l6_delta_dist["delta_star_L6"].median()),
        "std": float(l6_delta_dist["delta_star_L6"].std()),
        "q25": float(l6_delta_dist["delta_star_L6"].quantile(0.25)),
        "q75": float(l6_delta_dist["delta_star_L6"].quantile(0.75)),
        "distribution": {str(k): int(v) for k, v in
                         l6_delta_dist["delta_star_L6"].value_counts().sort_index().items()},
    }

    summary = {
        "experiment": "E2",
        "created_at": now_iso(),
        "git_commit": get_git_info(),
        "j1_aggregation_rule": "层级聚合: 先收集所有样本的未开方j1_sq → mean → sqrt（不平均已开方J₁）",
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
            "summary.json", "results.csv", "manifest.json",
            "ladder_L1_L6.csv",
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
        j1 = entry["J1_global"]
        imp = entry.get("improvement_vs_default_pct")
        if j1 is not None:
            imp_str = f"  (vs Default {imp:+.1f}%)" if imp is not None else ""
            print(f"  {name:8s}: J₁ = {j1:.4f}{imp_str}")
    print(f"\n输出: {E2_OUTPUT_DIR}")


if __name__ == "__main__":
    run_e2_analysis()
