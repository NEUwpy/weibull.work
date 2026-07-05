"""
Study/01 — E1 分析：Default + L1 + L2

从共用 MC 扫描数据按 δ 聚合，回答：
- δ=0.1 是不是最优全局常数？（Default vs L1）
- 最优全局常数 L1 是多少？
- 按 n 分层 L2 相比 L1 收益多少？

输入：artifacts/formal/shared_data/mc_scan_raw.csv
输出：artifacts/formal/E1_baseline/
  - manifest.json
  - summary.json
  - results.csv               — 规范逐条结果（协议要求）
  - table_default_vs_L1.csv   — Default vs L1 对比表
  - table_L2_by_n.csv         — L2 按 n 查表
  - delta_risk_curve.csv      — δ-risk 曲线数据（全局 + 分 n）

J₁ 聚合规则（严格遵守 02-实验协议.md STOP 条件#3）：
  J₁ = √(mean_i[(Δβ/β)² + (Δη/η)² + (Δγ/η)²])
  
  层级聚合时：
  1. 收集该层级分组内所有样本的未开方贡献 j1_sq = (Δβ/β)² + (Δη/η)² + (Δγ/η)²
  2. 对这些 j1_sq 取均值
  3. 最后开方一次
  绝不平均已开方的 J₁ 值。
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
    DELTA_GRID, DEFAULT_DELTA, R_MAIN, SEED_NAMESPACE,
    SHARED_DATA_DIR, E1_OUTPUT_DIR, STUDY_ROOT,
)
from metrics import j1_single
from utils import get_git_info, now_iso, now_local

# 所有参数组合列
COMBO_COLS = ["beta", "eta", "gamma", "gamma_over_eta", "n"]


# ============================================================
# 核心步骤1：收集逐样本未开方贡献 j1_sq
# ============================================================

def build_j1_sq_table(df):
    """对每行（每次估计）计算未开方 J₁ 贡献 j1_sq。

    j1_sq = (Δβ/β)² + (Δη/η)² + (Δγ/η)²

    Returns:
        DataFrame: 原始列 + j1_sq 列（只含 success 行）
    """
    df = df[df["converged"]].copy()

    # 向量化计算
    df["j1_sq"] = (
        ((df["beta_hat"] - df["beta"]) / df["beta"]) ** 2
        + ((df["eta_hat"] - df["eta"]) / df["eta"]) ** 2
        + ((df["gamma_hat"] - df["gamma"]) / df["eta"]) ** 2
    )

    # 过滤无效值
    df = df[np.isfinite(df["j1_sq"])]
    return df


# ============================================================
# 核心步骤2：层级聚合（先 mean j1_sq，再 sqrt）
# ============================================================

def j1_at_grouping(j1_sq_df, group_cols, delta_col="delta"):
    """在任意分组粒度上，对每个 δ 算该分组的 J₁。

    流程：分组 → 对每组的 j1_sq 取 mean → sqrt

    Args:
        j1_sq_df: 含 j1_sq 列的 DataFrame
        group_cols: 分组列（不含 delta）+ [delta]
                    例如 ["beta", "n", "delta"] 表示按(β,n)分组
        或传 group_cols 不含 delta，函数会自动加 delta

    Returns:
        DataFrame: group_cols + ["J1"]
    """
    # 确保 delta 在分组列里
    cols = list(group_cols)
    if delta_col not in cols:
        cols = cols + [delta_col]

    grouped = j1_sq_df.groupby(cols)["j1_sq"].mean().reset_index()
    grouped["J1"] = np.sqrt(grouped["j1_sq"])
    grouped = grouped.drop(columns=["j1_sq"])
    return grouped


# ============================================================
# Default / L1 / L2
# ============================================================

def compute_default(j1_sq_df):
    """Default: δ=0.1，按每个参数组合的 J₁。

    Returns:
        DataFrame: COMBO_COLS + ["J1_default"]
    """
    sub = j1_sq_df[j1_sq_df["delta"] == DEFAULT_DELTA]
    result = j1_at_grouping(sub, COMBO_COLS)
    result = result.drop(columns=["delta"], errors="ignore")
    return result.rename(columns={"J1": "J1_default"})


def compute_L1(j1_sq_df):
    """L1: 全局最优常数 δ*。

    对每个 δ，收集所有样本的 j1_sq 取均值 → sqrt → 得到 J₁_global(δ)
    取 argmin 为 δ*_L1。

    Returns:
        (delta_star_L1, j1_at_L1, curve_df)
    """
    # 全局：不分任何参数列，只按 δ 分组
    curve = j1_sq_df.groupby("delta")["j1_sq"].mean().reset_index()
    curve["J1_global"] = np.sqrt(curve["j1_sq"])
    curve = curve.drop(columns=["j1_sq"])

    idx_min = curve["J1_global"].idxmin()
    delta_star = curve.loc[idx_min, "delta"]
    j1_at_star = curve.loc[idx_min, "J1_global"]

    return delta_star, j1_at_star, curve


def compute_L1_per_combo(j1_sq_df, delta_star):
    """L1 应用于每个组合的 J₁（用全局 δ* 查表）。

    Returns:
        DataFrame: COMBO_COLS + ["J1_L1"]
    """
    sub = j1_sq_df[j1_sq_df["delta"] == delta_star]
    result = j1_at_grouping(sub, COMBO_COLS)
    result = result.drop(columns=["delta"], errors="ignore")
    return result.rename(columns={"J1": "J1_L1"})


def compute_L2(j1_sq_df):
    """L2: 按 n 的最优 δ*。

    对每个 n，收集该 n 下所有样本的 j1_sq 按 δ 分组取均值 → sqrt
    取 argmin 为 δ*(n)。

    Returns:
        DataFrame: n, delta_star_L2, J1_at_L2
    """
    results = []
    for n_val in N_GRID:
        sub = j1_sq_df[j1_sq_df["n"] == n_val]
        curve = sub.groupby("delta")["j1_sq"].mean().reset_index()
        curve["J1"] = np.sqrt(curve["j1_sq"])
        idx_min = curve["J1"].idxmin()
        results.append({
            "n": n_val,
            "delta_star_L2": curve.loc[idx_min, "delta"],
            "J1_at_L2": curve.loc[idx_min, "J1"],
        })
    return pd.DataFrame(results)


def compute_L2_per_combo(j1_sq_df, l2_table):
    """L2 应用于每个组合的 J₁（用该 n 的 δ* 查表）。

    Returns:
        DataFrame: COMBO_COLS + ["J1_L2"]
    """
    parts = []
    for _, l2_row in l2_table.iterrows():
        n_val = l2_row["n"]
        delta_star = l2_row["delta_star_L2"]
        sub = j1_sq_df[(j1_sq_df["n"] == n_val) & (j1_sq_df["delta"] == delta_star)]
        result = j1_at_grouping(sub, COMBO_COLS)
        result = result.drop(columns=["delta"], errors="ignore")
        result = result.rename(columns={"J1": "J1_L2"})
        parts.append(result)
    return pd.concat(parts, ignore_index=True)


# ============================================================
# Bias & SD
# ============================================================

def compute_bias_sd_for_layer(df, delta_value):
    """对指定 δ 的所有组合计算 Bias 和 SD。"""
    sub = df[df["delta"] == delta_value]
    results = []
    for keys, group in sub.groupby(COMBO_COLS):
        beta, eta, gamma, goe, n = keys
        valid = group[group["converged"]]
        bh = valid["beta_hat"].values
        eh = valid["eta_hat"].values
        gh = valid["gamma_hat"].values
        results.append({
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n,
            "bias_beta": float(np.mean(bh) - beta),
            "sd_beta": float(np.std(bh, ddof=1)) if len(bh) > 1 else 0,
            "bias_eta": float(np.mean(eh) - eta),
            "sd_eta": float(np.std(eh, ddof=1)) if len(eh) > 1 else 0,
            "bias_gamma": float(np.mean(gh) - gamma),
            "sd_gamma": float(np.std(gh, ddof=1)) if len(gh) > 1 else 0,
        })
    return pd.DataFrame(results)


# ============================================================
# 主流程
# ============================================================

def run_e1_analysis():
    """E1 主分析流程。"""
    print(f"\n{'='*60}")
    print(f"E1 分析：Default + L1 + L2")
    print(f"{'='*60}")
    print(f"[{now_local()}] 读取 MC 扫描数据...")

    csv_path = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
    df = pd.read_csv(csv_path)
    print(f"  数据行数: {len(df):,}")
    print(f"  参数组合: {df.groupby(COMBO_COLS).ngroups}")
    print(f"  δ 点数: {df['delta'].nunique()}")

    # 核心步骤1：逐样本 j1_sq
    print(f"\n[{now_local()}] 计算逐样本 j1_sq 贡献...")
    j1_sq_df = build_j1_sq_table(df)
    print(f"  有效行数: {len(j1_sq_df):,}")
    print(f"  j1_sq 范围: [{j1_sq_df['j1_sq'].min():.6f}, {j1_sq_df['j1_sq'].max():.6f}]")

    os.makedirs(E1_OUTPUT_DIR, exist_ok=True)

    # ── Default ──
    print(f"\n[{now_local()}] Default (δ={DEFAULT_DELTA})...")
    default_df = compute_default(j1_sq_df)
    j1_default_mean = float(default_df["J1_default"].mean())  # 各组合J₁的算术平均（展示用）
    # 注意：全局J₁应该从j1_sq直接算，不是平均各组合的J₁
    global_default = j1_sq_df[j1_sq_df["delta"] == DEFAULT_DELTA]
    j1_default_global = math.sqrt(global_default["j1_sq"].mean())
    print(f"  Default J₁ (全局): {j1_default_global:.4f}")

    # ── L1 ──
    print(f"\n[{now_local()}] L1 全局最优常数...")
    delta_star_L1, j1_at_L1, l1_curve = compute_L1(j1_sq_df)
    print(f"  L1 最优 δ* = {delta_star_L1}")
    print(f"  L1 J₁(global) = {j1_at_L1:.4f}")
    if j1_default_global > 0:
        print(f"  Default→L1 提升: {(1 - j1_at_L1/j1_default_global)*100:.1f}%")

    l1_per_combo = compute_L1_per_combo(j1_sq_df, delta_star_L1)

    # ── L2 ──
    print(f"\n[{now_local()}] L2 按 n 最优...")
    l2_table = compute_L2(j1_sq_df)
    print(f"  L2 查表:")
    for _, row in l2_table.iterrows():
        print(f"    n={int(row['n']):2d}: δ*={row['delta_star_L2']:.2f}, J₁={row['J1_at_L2']:.4f}")

    l2_per_combo = compute_L2_per_combo(j1_sq_df, l2_table)

    # L2 全局 J₁（从 j1_sq 重算，不是平均组合级J₁）
    l2_global_parts = []
    for _, l2_row in l2_table.iterrows():
        n_val = l2_row["n"]
        ds = l2_row["delta_star_L2"]
        sub = j1_sq_df[(j1_sq_df["n"] == n_val) & (j1_sq_df["delta"] == ds)]
        l2_global_parts.append(sub)
    l2_global_df = pd.concat(l2_global_parts)
    j1_l2_global = math.sqrt(l2_global_df["j1_sq"].mean())
    print(f"  L2 J₁(global) = {j1_l2_global:.4f}")
    if j1_at_L1 > 0:
        print(f"  L1→L2 提升: {(1 - j1_l2_global/j1_at_L1)*100:.2f}%")

    # ── 输出表格 ──
    print(f"\n[{now_local()}] 写输出文件...")

    # Table: Default vs L1
    table_dl = default_df.merge(l1_per_combo, on=COMBO_COLS)
    table_dl["improvement_pct"] = (1 - table_dl["J1_L1"] / table_dl["J1_default"]) * 100
    table_dl.to_csv(os.path.join(E1_OUTPUT_DIR, "table_default_vs_L1.csv"), index=False)

    # Table: L2 by n
    l2_table.to_csv(os.path.join(E1_OUTPUT_DIR, "table_L2_by_n.csv"), index=False)

    # δ-risk curve（全局 + 分 n）
    risk_curve = l1_curve.copy()
    for n_val in N_GRID:
        sub = j1_sq_df[j1_sq_df["n"] == n_val]
        curve_n = sub.groupby("delta")["j1_sq"].mean().reset_index()
        curve_n[f"J1_n{int(n_val)}"] = np.sqrt(curve_n["j1_sq"])
        curve_n = curve_n.drop(columns=["j1_sq"])
        risk_curve = risk_curve.merge(curve_n, on="delta", how="left")
    risk_curve.to_csv(os.path.join(E1_OUTPUT_DIR, "delta_risk_curve.csv"), index=False)

    # Bias & SD
    bias_default = compute_bias_sd_for_layer(df, DEFAULT_DELTA)
    bias_l1 = compute_bias_sd_for_layer(df, delta_star_L1)
    bias_default.to_csv(os.path.join(E1_OUTPUT_DIR, "bias_sd_default.csv"), index=False)
    bias_l1.to_csv(os.path.join(E1_OUTPUT_DIR, "bias_sd_L1.csv"), index=False)

    # results.csv（规范逐条结果 — 显式列名，无 delta_x/delta_y）
    results_csv = pd.DataFrame({
        "beta": default_df["beta"],
        "eta": default_df["eta"],
        "gamma": default_df["gamma"],
        "gamma_over_eta": default_df["gamma_over_eta"],
        "n": default_df["n"],
        "delta_default": DEFAULT_DELTA,
        "J1_default": default_df["J1_default"],
        "delta_L1": delta_star_L1,
        "J1_L1": l1_per_combo["J1_L1"],
    })
    # L2 的 δ* 按 n 查表
    l2_delta_map = dict(zip(l2_table["n"], l2_table["delta_star_L2"]))
    results_csv["delta_L2"] = results_csv["n"].map(l2_delta_map)
    results_csv["J1_L2"] = l2_per_combo.set_index(COMBO_COLS).loc[
        results_csv.set_index(COMBO_COLS).index, "J1_L2"
    ].values
    results_csv["improvement_L1_vs_default_pct"] = (1 - results_csv["J1_L1"] / results_csv["J1_default"]) * 100
    results_csv["improvement_L2_vs_L1_pct"] = (1 - results_csv["J1_L2"] / results_csv["J1_L1"]) * 100
    results_csv.to_csv(os.path.join(E1_OUTPUT_DIR, "results.csv"), index=False)

    # Summary JSON
    summary = {
        "experiment": "E1",
        "created_at": now_iso(),
        "git_commit": get_git_info(),
        "delta_grid": DELTA_GRID,
        "default_delta": DEFAULT_DELTA,
        "j1_aggregation_rule": "层级聚合: 先收集所有样本的未开方j1_sq → mean → sqrt（不平均已开方J₁）",
        "results": {
            "default": {
                "delta": DEFAULT_DELTA,
                "J1_global": float(j1_default_global),
            },
            "L1": {
                "delta_star": float(delta_star_L1),
                "J1_global": float(j1_at_L1),
                "improvement_vs_default_pct": float((1 - j1_at_L1/j1_default_global)*100),
            },
            "L2": {
                "table": l2_table.to_dict(orient="records"),
                "J1_global": float(j1_l2_global),
                "improvement_vs_L1_pct": float((1 - j1_l2_global/j1_at_L1)*100),
            },
        },
    }
    with open(os.path.join(E1_OUTPUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Manifest（满足 02-实验协议.md 必填字段）
    manifest = {
        "run_id": "E1_baseline_v1",
        "experiment": "E1",
        "created_at": now_iso(),
        "code_entry": "code/analyze_E1.py",
        "git_commit": get_git_info(),
        "python_version": sys.version.split()[0],
        "method_versions": {
            "mdm": {"source": "python/methods/mdm.py", "git_commit": "e4ef9e9"},
            "mle": {"source": "python/methods/mle.py", "git_commit": "e4ef9e9"},
        },
        "input_data": "artifacts/formal/shared_data/mc_scan_raw.csv",
        "parameter_grid": {
            "beta": BETA_GRID,
            "eta": ETA_GRID,
            "gamma_over_eta": GAMMA_OVER_ETA_GRID,
            "n": N_GRID,
        },
        "delta_grid": DELTA_GRID,
        "default_delta": DEFAULT_DELTA,
        "repeats": R_MAIN,
        "seed_namespace": SEED_NAMESPACE,
        "metrics_contract": {
            "primary": "J1 = sqrt(mean[(db/b)^2 + (de/e)^2 + (dg/e)^2])",
            "aggregation_rule": "层级聚合: 先收集所有样本未开方j1_sq → mean → sqrt",
            "gamma_normalization": "divided by eta (scale parameter), not gamma itself",
            "weights": "equal (w_beta = w_eta = w_gamma = 1)",
            "auxiliary": ["bias_beta", "sd_beta", "bias_eta", "sd_eta", "bias_gamma", "sd_gamma"],
        },
        "output_files": [
            "summary.json", "results.csv", "manifest.json",
            "table_default_vs_L1.csv", "table_L2_by_n.csv",
            "delta_risk_curve.csv", "bias_sd_default.csv", "bias_sd_L1.csv",
        ],
        "notes": "E1 从 E1/E2 共用 MC 扫描数据按 δ 聚合，回答 Default/L1/L2 的精度。",
    }
    with open(os.path.join(E1_OUTPUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"E1 分析完成！")
    print(f"{'='*60}")
    print(f"\n核心结论：")
    print(f"  Default δ=0.1:  J₁ = {j1_default_global:.4f}")
    print(f"  L1 最优 δ*={delta_star_L1:.2f}:  J₁ = {j1_at_L1:.4f}  (提升 {(1-j1_at_L1/j1_default_global)*100:.1f}%)")
    print(f"  L2 按 n 查表:   J₁ = {j1_l2_global:.4f}  (提升 {(1-j1_l2_global/j1_at_L1)*100:.2f}%)")
    print(f"\n输出: {E1_OUTPUT_DIR}")


if __name__ == "__main__":
    run_e1_analysis()
