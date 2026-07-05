"""
Study/01 — E1 分析：Default + L1 + L2

从共用 MC 扫描数据按 δ 聚合，回答：
- δ=0.1 是不是最优全局常数？（Default vs L1）
- 最优全局常数 L1 是多少？
- 按 n 分层 L2 相比 L1 收益多少？

输入：artifacts/formal/shared_data/mc_scan_raw.csv
输出：artifacts/formal/E1_baseline/
  - manifest.json
  - summary.json          — 所有聚合结果的 JSON
  - table_default_vs_L1.csv   — Default vs L1 对比表
  - table_L2_by_n.csv         — L2 按 n 查表
  - delta_risk_curve.csv      — δ-risk 曲线数据（全局 + 分 n）

聚合逻辑：
  对每个参数组合 (β, η, γ, n)：
    1. 对每个 δ ∈ grid，用该 (组合, δ) 的 R=1000 次估计算 J₁(δ)
    2. Default = J₁(δ=0.1)
    3. L1 全局最优 = argmin_δ J₁(δ)，对所有组合取同一 δ*
       - 先按 (组合) 算各 δ 的 J₁，再全局平均得到 J₁_global(δ)，取最优 δ*
    4. L2 按 n 最优 = 对每个 n，在该 n 的所有组合上平均 J₁，取最优 δ*(n)
"""

import os
import sys
import json
import time
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
from metrics import compute_j1, aggregate_metrics
from utils import get_git_info, now_iso, now_local


# ============================================================
# 核心聚合：按 (参数组合, δ) 计算 J₁
# ============================================================

def compute_j1_by_combo_delta(df):
    """对每个 (β,η,γ,n,δ) 组合计算 J₁。

    Args:
        df: mc_scan_raw.csv 的 DataFrame（只含 success 行）

    Returns:
        DataFrame: 每行 = (beta, eta, gamma, gamma_over_eta, n, delta, J1, n_valid, n_total, failure_rate)
    """
    results = []

    # 按 (组合, δ) 分组
    group_cols = ["beta", "eta", "gamma", "gamma_over_eta", "n", "delta"]
    for keys, group in df.groupby(group_cols):
        beta, eta, gamma, goe, n, delta = keys

        estimates = []
        n_total = len(group)
        n_failure = 0

        for _, row in group.iterrows():
            if not row["converged"]:
                n_failure += 1
                continue
            bh = row["beta_hat"]
            eh = row["eta_hat"]
            gh = row["gamma_hat"]
            if not all(math.isfinite(v) for v in [bh, eh, gh]):
                n_failure += 1
                continue
            estimates.append({"beta_hat": bh, "eta_hat": eh, "gamma_hat": gh})

        j1 = compute_j1(estimates, beta, eta, gamma)
        n_valid = len(estimates)

        results.append({
            "beta": beta,
            "eta": eta,
            "gamma": gamma,
            "gamma_over_eta": goe,
            "n": n,
            "delta": delta,
            "J1": j1,
            "n_valid": n_valid,
            "n_total": n_total,
            "failure_rate": n_failure / n_total if n_total > 0 else 0.0,
        })

    return pd.DataFrame(results)


# ============================================================
# 层级聚合
# ============================================================

def compute_default(j1_df):
    """Default: δ=0.1 的 J₁。

    Returns:
        DataFrame: 每行 = (beta, eta, gamma, gamma_over_eta, n, J1_default)
    """
    sub = j1_df[j1_df["delta"] == DEFAULT_DELTA].copy()
    return sub[["beta", "eta", "gamma", "gamma_over_eta", "n", "J1"]].rename(
        columns={"J1": "J1_default"}
    )


def compute_L1(j1_df):
    """L1: 全局最优常数 δ*。

    对每个 δ，先按所有参数组合取 J₁ 的均值（跨组合平均），
    得到 J₁_global(δ)，取 argmin 为 δ*_L1。

    Returns:
        (delta_star_L1, j1_at_L1, curve_df)
        curve_df: 每行 = (delta, J1_global_mean)
    """
    # 对每个 δ，跨所有组合取 J₁ 均值
    curve = j1_df.groupby("delta")["J1"].mean().reset_index()
    curve.columns = ["delta", "J1_global_mean"]

    idx_min = curve["J1_global_mean"].idxmin()
    delta_star = curve.loc[idx_min, "delta"]
    j1_at_star = curve.loc[idx_min, "J1_global_mean"]

    return delta_star, j1_at_star, curve


def compute_L1_per_combo(j1_df, delta_star):
    """L1 应用于每个组合的 J₁（用全局 δ* 查表）。

    Returns:
        DataFrame: 每行 = (beta,...,n, J1_L1)
    """
    sub = j1_df[j1_df["delta"] == delta_star].copy()
    return sub[["beta", "eta", "gamma", "gamma_over_eta", "n", "J1"]].rename(
        columns={"J1": "J1_L1"}
    )


def compute_L2(j1_df):
    """L2: 按 n 的最优 δ*。

    对每个 n，在该 n 的所有 (β,η,γ) 组合上平均 J₁ 得到 J₁_n(δ)，
    取 argmin 为 δ*(n)。

    Returns:
        DataFrame: 每行 = (n, delta_star_L2, J1_at_L2)
    """
    results = []
    for n_val in N_GRID:
        sub = j1_df[j1_df["n"] == n_val]
        curve = sub.groupby("delta")["J1"].mean().reset_index()
        idx_min = curve["J1"].idxmin()
        results.append({
            "n": n_val,
            "delta_star_L2": curve.loc[idx_min, "delta"],
            "J1_at_L2": curve.loc[idx_min, "J1"],
        })
    return pd.DataFrame(results)


def compute_L2_per_combo(j1_df, l2_table):
    """L2 应用于每个组合的 J₁（用该 n 的 δ* 查表）。

    Returns:
        DataFrame: 每行 = (beta,...,n, J1_L2)
    """
    results = []
    for _, l2_row in l2_table.iterrows():
        n_val = l2_row["n"]
        delta_star = l2_row["delta_star_L2"]
        sub = j1_df[(j1_df["n"] == n_val) & (j1_df["delta"] == delta_star)].copy()
        for _, row in sub.iterrows():
            results.append({
                "beta": row["beta"], "eta": row["eta"], "gamma": row["gamma"],
                "gamma_over_eta": row["gamma_over_eta"], "n": n_val,
                "J1_L2": row["J1"],
            })
    return pd.DataFrame(results)


# ============================================================
# 辅助：Bias & SD 提取
# ============================================================

def compute_bias_sd_for_layer(df, delta_value):
    """对指定 δ 的所有组合计算 Bias 和 SD。

    Returns:
        DataFrame: 每行 = (beta,...,n, bias_beta, sd_beta, ...)
    """
    sub = df[df["delta"] == delta_value]
    results = []
    group_cols = ["beta", "eta", "gamma", "gamma_over_eta", "n"]
    for keys, group in sub.groupby(group_cols):
        beta, eta, gamma, goe, n = keys
        valid = group[group["converged"]]
        bh = valid["beta_hat"].values
        eh = valid["eta_hat"].values
        gh = valid["gamma_hat"].values
        results.append({
            "beta": beta, "eta": eta, "gamma": gamma,
            "gamma_over_eta": goe, "n": n,
            "bias_beta": np.mean(bh) - beta,
            "sd_beta": np.std(bh, ddof=1) if len(bh) > 1 else 0,
            "bias_eta": np.mean(eh) - eta,
            "sd_eta": np.std(eh, ddof=1) if len(eh) > 1 else 0,
            "bias_gamma": np.mean(gh) - gamma,
            "sd_gamma": np.std(gh, ddof=1) if len(gh) > 1 else 0,
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

    # 读取数据
    csv_path = os.path.join(SHARED_DATA_DIR, "mc_scan_raw.csv")
    df = pd.read_csv(csv_path)
    print(f"  数据行数: {len(df):,}")
    print(f"  参数组合: {df.groupby(['beta','eta','gamma','n']).ngroups}")
    print(f"  δ 点数: {df['delta'].nunique()}")
    print(f"  status: {df['status'].value_counts().to_dict()}")

    # 核心聚合：按 (组合, δ) 算 J₁
    print(f"\n[{now_local()}] 计算 J₁(组合, δ)...")
    j1_df = compute_j1_by_combo_delta(df)
    print(f"  J₁ 表行数: {len(j1_df)} (期望 {45*26}={45*26})")
    print(f"  J₁ 范围: [{j1_df['J1'].min():.4f}, {j1_df['J1'].max():.4f}]")

    os.makedirs(E1_OUTPUT_DIR, exist_ok=True)

    # ── Default ──
    print(f"\n[{now_local()}] Default (δ={DEFAULT_DELTA})...")
    default_df = compute_default(j1_df)
    j1_default_mean = default_df["J1_default"].mean()
    print(f"  Default J₁ (跨组合平均): {j1_default_mean:.4f}")

    # ── L1 ──
    print(f"\n[{now_local()}] L1 全局最优常数...")
    delta_star_L1, j1_at_L1, l1_curve = compute_L1(j1_df)
    print(f"  L1 最优 δ* = {delta_star_L1}")
    print(f"  L1 J₁(global mean) = {j1_at_L1:.4f}")
    print(f"  Default→L1 提升: {(1 - j1_at_L1/j1_default_mean)*100:.1f}%")

    l1_per_combo = compute_L1_per_combo(j1_df, delta_star_L1)

    # ── L2 ──
    print(f"\n[{now_local()}] L2 按 n 最优...")
    l2_table = compute_L2(j1_df)
    print(f"  L2 查表:")
    for _, row in l2_table.iterrows():
        print(f"    n={int(row['n']):2d}: δ*={row['delta_star_L2']:.2f}, J₁={row['J1_at_L2']:.4f}")

    l2_per_combo = compute_L2_per_combo(j1_df, l2_table)
    j1_l2_mean = l2_per_combo["J1_L2"].mean()
    print(f"  L2 J₁(跨组合平均) = {j1_l2_mean:.4f}")
    print(f"  L1→L2 提升: {(1 - j1_l2_mean/j1_at_L1)*100:.2f}%")

    # ── 输出表格 ──
    print(f"\n[{now_local()}] 写输出文件...")

    # Table: Default vs L1
    table_dl = default_df.merge(l1_per_combo, on=["beta","eta","gamma","gamma_over_eta","n"])
    table_dl["improvement_pct"] = (1 - table_dl["J1_L1"] / table_dl["J1_default"]) * 100
    table_dl.to_csv(os.path.join(E1_OUTPUT_DIR, "table_default_vs_L1.csv"), index=False)

    # Table: L2 by n
    l2_table.to_csv(os.path.join(E1_OUTPUT_DIR, "table_L2_by_n.csv"), index=False)

    # δ-risk curve（全局 + 分 n）
    risk_curve = l1_curve.rename(columns={"J1_global_mean": "J1_global"})
    for n_val in N_GRID:
        sub = j1_df[j1_df["n"] == n_val]
        curve_n = sub.groupby("delta")["J1"].mean().reset_index()
        risk_curve = risk_curve.merge(
            curve_n.rename(columns={"delta": "delta", "J1": f"J1_n{int(n_val)}"}),
            on="delta", how="left"
        )
    risk_curve.to_csv(os.path.join(E1_OUTPUT_DIR, "delta_risk_curve.csv"), index=False)

    # Bias & SD for Default 和 L1
    bias_default = compute_bias_sd_for_layer(df, DEFAULT_DELTA)
    bias_l1 = compute_bias_sd_for_layer(df, delta_star_L1)
    bias_default.to_csv(os.path.join(E1_OUTPUT_DIR, "bias_sd_default.csv"), index=False)
    bias_l1.to_csv(os.path.join(E1_OUTPUT_DIR, "bias_sd_L1.csv"), index=False)

    # Summary JSON
    summary = {
        "experiment": "E1",
        "created_at": now_iso(),
        "git_commit": get_git_info(),
        "delta_grid": DELTA_GRID,
        "default_delta": DEFAULT_DELTA,
        "results": {
            "default": {
                "delta": DEFAULT_DELTA,
                "J1_global_mean": float(j1_default_mean),
            },
            "L1": {
                "delta_star": float(delta_star_L1),
                "J1_global_mean": float(j1_at_L1),
                "improvement_vs_default_pct": float((1 - j1_at_L1/j1_default_mean)*100),
            },
            "L2": {
                "table": l2_table.to_dict(orient="records"),
                "J1_global_mean": float(j1_l2_mean),
                "improvement_vs_L1_pct": float((1 - j1_l2_mean/j1_at_L1)*100),
            },
        },
    }
    with open(os.path.join(E1_OUTPUT_DIR, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    # Manifest
    manifest = {
        "experiment": "E1",
        "created_at": now_iso(),
        "code_entry": "code/analyze_E1.py",
        "git_commit": get_git_info(),
        "input_data": "artifacts/formal/shared_data/mc_scan_raw.csv",
        "output_files": [
            "summary.json", "table_default_vs_L1.csv", "table_L2_by_n.csv",
            "delta_risk_curve.csv", "bias_sd_default.csv", "bias_sd_L1.csv",
        ],
    }
    with open(os.path.join(E1_OUTPUT_DIR, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print(f"\n{'='*60}")
    print(f"E1 分析完成！")
    print(f"{'='*60}")
    print(f"\n核心结论：")
    print(f"  Default δ=0.1:  J₁ = {j1_default_mean:.4f}")
    print(f"  L1 最优 δ*={delta_star_L1:.2f}:  J₁ = {j1_at_L1:.4f}  (提升 {(1-j1_at_L1/j1_default_mean)*100:.1f}%)")
    print(f"  L2 按 n 查表:   J₁ = {j1_l2_mean:.4f}  (提升 {(1-j1_l2_mean/j1_at_L1)*100:.2f}%)")
    print(f"\n输出: {E1_OUTPUT_DIR}")


if __name__ == "__main__":
    run_e1_analysis()
