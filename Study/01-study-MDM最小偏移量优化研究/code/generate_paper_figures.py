"""
Study/01 — current-route paper figures and supplementary tables.

Reads only sealed E6 artifacts plus the new B1/B2/B3 support evidence and
regenerates the paper's minimal figure set and supplementary tables for the
Dimensional-RAW route.  Every figure/table records its source mapping in the
paper README index.  Old feature-route G5 figures are NOT reused.

Figures:
  fig1_method_structure.png   sorted raw sample -> per-n MLP -> 26-pt loss
                              curve -> argmin delta -> MDM (schematic)
  fig2_overall_delta_risk.png pooled J1 over the 26-delta grid (delta 0.1 in
                              the flat low-risk region)
  fig3_per_n_J1.png           Dimensional-RAW / Default / L6 J1 by n
  supp_fig_seed_stability.png three-seed spread of Dimensional-RAW by n
  supp_fig_unseen_beta.png    unseen-beta hold-out J1 by held-out beta (B1)
  supp_fig_traditional_per_n.png  WMLE / LSE / DIM-RAW / Default / L6 J1 by n
  supp_fig_quantile_rmse.png  relative RMSE of x_0.90/x_0.95/x_0.99 by method

Tables (markdown + CSV):
  table1_l1_l6.md             L1-L6 selection layers and pooled J1
  table2_main_results.md      Dimensional-RAW / Default / L6 main results
  table3_support_verification.md  compact support-verification summary
  supp_table_unseen_beta.md   B1 per held-out beta J1
  supp_table_traditional.md   B2 WMLE/LSE pooled/per-n J1 + parameter metrics
  supp_table_quantiles.md     B3 relative metrics per quantile per method

Output: artifacts/formal/E6_dimensional_raw/paper/
  (figures, tables, README.md index, manifest.json, SHA256SUMS)

Run:  python code/generate_paper_figures.py
"""

import json
import math
import os
import sys
import time
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch  # noqa: E402

# CJK-capable font stack (SimHei/Microsoft YaHei ship with Windows).
plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "SimSun",
                                   "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

STUDY_CODE_DIR = os.path.dirname(os.path.abspath(__file__))
PYTHON_DIR = os.path.join(os.path.dirname(os.path.dirname(STUDY_CODE_DIR)),
                          "python")
for p in (STUDY_CODE_DIR, PYTHON_DIR):
    if p not in sys.path:
        sys.path.insert(0, p)

import dim_raw_config as CFG
import paper_support as PS

OUT_DIR = PS.PAPER_DIR
SPECIALIST = os.path.join(PS.E6_DIR, "specialist")

# Validated categorical palette (first five slots; CVD-safe adjacent pairs).
COLORS = {
    "Dimensional-RAW": "#2a78d6",
    "Default": "#eb6834",
    "L6": "#1baf7a",
    "WMLE": "#e87ba4",
    "LSE": "#008300",
}
INK = "#0b0b0b"
MUTED = "#898781"
GRID = "#e1e0d9"

METHOD_ORDER = ["Dimensional-RAW", "Default", "L6", "WMLE", "LSE"]


def style_ax(ax):
    ax.set_facecolor("white")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    for s in ("left", "bottom"):
        ax.spines[s].set_color("#c3c2b7")
    ax.tick_params(colors=INK)
    ax.yaxis.grid(True, color=GRID, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="y", length=0)


def save_fig(fig, name):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    fig.savefig(path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [fig] {name}")
    return name


# ============================================================
# Figure 1 — method structure (schematic)
# ============================================================

def fig1_method_structure():
    fig, ax = plt.subplots(figsize=(9.0, 5.0))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 6)
    ax.axis("off")

    def box(x, y, w, h, text, fc="#eef3fb", ec="#2a78d6", fs=9.5):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                                    boxstyle="round,pad=0.06",
                                    linewidth=1.4, edgecolor=ec,
                                    facecolor=fc))
        ax.text(x, y, text, ha="center", va="center", fontsize=fs,
                color=INK)

    def arrow(x1, y1, x2, y2):
        ax.add_patch(FancyArrowPatch((x1, y1), (x2, y2),
                                     arrowstyle="-|>", mutation_scale=16,
                                     linewidth=1.6, color="#52514e"))

    # Training lane (top) vs application (bottom)
    ax.text(0.35, 5.55, "训练时（Monte Carlo 真值提供标签）", fontsize=9,
            color=MUTED, ha="left", style="italic")
    ax.text(0.35, 1.10, "应用时（只输入当前样本）", fontsize=9,
            color=MUTED, ha="left", style="italic")

    # Row 1 (training): label from MC
    box(1.6, 4.5, 2.6, 0.9, "已知真参数\n(β, η, γ)", fc="#f5f5f4", ec="#c3c2b7")
    arrow(2.9, 4.05, 2.9, 3.35)
    box(2.9, 2.9, 2.6, 0.9, "蒙特卡洛抽样\n生成排序原始样本 X_n", fc="#f5f5f4",
        ec="#c3c2b7")
    arrow(2.9, 2.45, 5.3, 2.45)
    box(5.3, 2.9, 2.6, 0.9, "MDM 在 26 个候选 δ\n计算损失曲线（标签）",
        fc="#f5f5f4", ec="#c3c2b7")

    # Main pipeline (application row)
    box(1.6, 1.9, 2.6, 0.9, "X_n = sort(x₁…x_n)\n（有量纲排序原始样本）",
        fc="#eef3fb", ec="#2a78d6")
    arrow(2.9, 1.45, 2.9, 0.75)
    box(2.9, 0.3, 2.6, 0.9, "per-n MLP\n(256–128–64, ReLU)", fc="#eef3fb",
        ec="#2a78d6")
    arrow(4.2, 0.75, 4.9, 0.75)
    box(5.3, 0.3, 2.6, 0.9, "预测 26 点损失曲线\nℓ̂(δ₁…δ₂₆ | X_n)",
        fc="#eef3fb", ec="#2a78d6")
    arrow(6.6, 0.75, 7.3, 0.75)
    box(8.0, 0.3, 1.7, 0.9, "δ̂ = argmin ℓ̂", fc="#eef3fb", ec="#2a78d6")
    arrow(8.0, 0.75, 8.0, 1.45)
    box(8.0, 1.9, 2.6, 0.9, "MDM(β̂, η̂, γ̂ | δ̂)", fc="#eef3fb", ec="#2a78d6")

    # label link: training label feeds MLP target
    arrow(5.3, 2.45, 5.3, 0.75)
    ax.text(5.45, 1.6, "26 维损失标签", fontsize=8, color=MUTED, rotation=90,
            va="center")

    ax.set_title("方法结构：按样本量分别训练 MLP，以排序原始样本选择偏移量 δ",
                 fontsize=11, color=INK, pad=12)
    return save_fig(fig, "fig1_method_structure.png")


# ============================================================
# Figure 2 — overall delta-risk curve
# ============================================================

def fig2_overall_delta_risk(df_full):
    d = df_full.copy()
    d["loss"] = d["loss"].astype(float)
    curve = (d.groupby("delta")["loss"].mean()
             .apply(math.sqrt).sort_index())
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    ax.plot(curve.index, curve.values, color=COLORS["Dimensional-RAW"],
            lw=2.0, marker="o", ms=4)
    ax.set_xlabel("偏移量 δ")
    ax.set_ylabel("pooled $J_1$")
    ax.set_xticks([0.0, 0.1, 0.2, 0.3, 0.4, 0.5])
    style_ax(ax)

    d_min = float(curve.idxmin())
    j_min = float(curve.min())
    j_10 = float(curve.loc[0.10])
    ax.scatter([d_min], [j_min], s=46, zorder=5, color=INK, marker="x")
    ax.annotate(f"最小值 δ={d_min:.2f}\n$J_1$={j_min:.4f}",
                xy=(d_min, j_min), xytext=(d_min + 0.06, j_min + 0.006),
                fontsize=8, color=INK,
                arrowprops=dict(arrowstyle="->", lw=0.9, color=MUTED))
    ax.scatter([0.10], [j_10], s=46, zorder=5, color=COLORS["Default"],
               marker="s")
    ax.annotate("经验值 δ=0.10\n$J_1$=0.6304", xy=(0.10, j_10),
                xytext=(0.12, j_10 - 0.010), fontsize=8, color=INK,
                arrowprops=dict(arrowstyle="->", lw=0.9, color=MUTED))
    ax.set_title("整体 δ–风险曲线（160 组合，48,000 样本）", fontsize=10.5,
                 color=INK)
    return save_fig(fig, "fig2_overall_delta_risk.png")


# ============================================================
# Figure 3 — per-n J1 for the three main methods
# ============================================================

def fig3_per_n_J1(e6_summary):
    comp = pd.DataFrame(e6_summary["model_comparison"])
    ns = list(CFG.N_GRID)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for method, color in (("Dimensional-RAW-MLP", COLORS["Dimensional-RAW"]),
                          ("Default", COLORS["Default"]),
                          ("L6-hindsight", COLORS["L6"])):
        sub = comp[comp["model"] == method]
        y = [float(sub[f"J1_n{n}"].mean()) for n in ns]
        ax.plot(ns, y, color=color, lw=2.0, marker="o", ms=6,
                label={"Dimensional-RAW-MLP": "Dimensional-RAW",
                       "Default": "Default ($\\delta=0.1$)",
                       "L6-hindsight": "L6 (hindsight)"}[method])
    ax.set_xlabel("样本量 $n$")
    ax.set_ylabel("pooled $J_1$")
    ax.set_xticks(ns)
    ax.set_ylim(0.35, 0.80)
    ax.legend(frameon=False, fontsize=9)
    style_ax(ax)
    ax.set_title("三方法按样本量的 $J_1$（四个已训练 $n$）", fontsize=10.5,
                 color=INK)
    return save_fig(fig, "fig3_per_n_J1.png")


# ============================================================
# Supplementary: seed stability
# ============================================================

def supp_fig_seed_stability(e6_summary):
    seeds = pd.DataFrame(e6_summary["seed_table"])
    ns = list(CFG.N_GRID)
    fig, ax = plt.subplots(figsize=(6.4, 4.2))
    for _, r in seeds.iterrows():
        y = [float(r[f"J1_n{n}"]) for n in ns]
        ax.plot(ns, y, color=COLORS["Dimensional-RAW"], lw=1.1, alpha=0.45,
                label=f"seed {int(r['seed'])}")
    mean_y = [float(seeds[f"J1_n{n}"].mean()) for n in ns]
    ax.plot(ns, mean_y, color=COLORS["Dimensional-RAW"], lw=2.4, marker="o",
            ms=7, label="三 seed 均值")
    ax.set_xlabel("样本量 $n$")
    ax.set_ylabel("$J_1$")
    ax.set_xticks(ns)
    ax.legend(frameon=False, fontsize=9)
    style_ax(ax)
    ax.set_title("Dimensional-RAW 三 seed 稳定性（按 $n$）", fontsize=10.5,
                 color=INK)
    return save_fig(fig, "supp_fig_seed_stability.png")


# ============================================================
# Supplementary: unseen beta (B1)
# ============================================================

def supp_fig_unseen_beta(b1_summary_path):
    if not os.path.exists(b1_summary_path):
        print("  [skip] supp_fig_unseen_beta: B1 summary missing")
        return None
    with open(b1_summary_path, encoding="utf-8") as f:
        s = json.load(f)
    per_beta = s["per_beta"]
    betas = [float(b) for b in per_beta]
    fig, ax = plt.subplots(figsize=(6.8, 4.2))
    for model, color in (("Dimensional-RAW", COLORS["Dimensional-RAW"]),
                         ("Default", COLORS["Default"]),
                         ("L6", COLORS["L6"])):
        y = [per_beta[str(b)][model]["J1"] for b in betas]
        ax.plot(betas, y, color=color, lw=2.0, marker="o", ms=6,
                label=model if model != "Default" else "Default ($\\delta=0.1$)")
    ax.set_xlabel("留出的形状参数 $\\beta$")
    ax.set_ylabel("pooled $J_1$")
    ax.legend(frameon=False, fontsize=9)
    style_ax(ax)
    ax.set_title("未见 $\\beta$ 留出验证：每个留出 $\\beta$ 的 $J_1$（B1）",
                 fontsize=10.5, color=INK)
    return save_fig(fig, "supp_fig_unseen_beta.png")


# ============================================================
# Supplementary: traditional per-n (B2)
# ============================================================

def supp_fig_traditional_per_n(b2_summary_path, e6_summary):
    if not os.path.exists(b2_summary_path):
        print("  [skip] supp_fig_traditional_per_n: B2 summary missing")
        return None
    b2 = pd.read_csv(b2_summary_path)
    ns = list(CFG.N_GRID)
    comp = pd.DataFrame(e6_summary["model_comparison"])
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    series = []
    for m in ("Dimensional-RAW-MLP", "Default", "L6-hindsight"):
        sub = comp[comp["model"] == m]
        series.append(({"Dimensional-RAW-MLP": "Dimensional-RAW",
                        "Default": "Default", "L6-hindsight": "L6"}[m],
                       [float(sub[f"J1_n{n}"].mean()) for n in ns]))
    for m in ("WMLE", "LSE"):
        row = b2[b2["method"] == m].iloc[0]
        series.append((m, [float(row[f"J1_n{n}"]) for n in ns]))
    for name, y in series:
        ax.plot(ns, y, color=COLORS[name], lw=2.0, marker="o", ms=6, label=name)
    ax.set_xlabel("样本量 $n$")
    ax.set_ylabel("pooled $J_1$")
    ax.set_xticks(ns)
    ax.legend(frameon=False, fontsize=9, ncol=2)
    style_ax(ax)
    ax.set_title("传统方法参照：WMLE / LSE 与当前路线按 $n$ 的 $J_1$",
                 fontsize=10.5, color=INK)
    return save_fig(fig, "supp_fig_traditional_per_n.png")


# ============================================================
# Supplementary: quantile RMSE (B3)
# ============================================================

def supp_fig_quantile_rmse(b3_summary_path):
    if not os.path.exists(b3_summary_path):
        print("  [skip] supp_fig_quantile_rmse: B3 summary missing")
        return None
    b3 = pd.read_csv(b3_summary_path)
    fig, ax = plt.subplots(figsize=(6.8, 4.4))
    qmap = {"x0.90": 0.90, "x0.95": 0.95, "x0.99": 0.99}
    for method in METHOD_ORDER:
        m = "Dimensional-RAW" if method == "Dimensional-RAW" else method
        sub = b3[b3["method"] == m]
        # aggregate over seeds (mean of per-seed RMSE; deterministic -1 too)
        agg = sub.groupby("quantile")["rmse"].mean()
        xs = [qmap[q] for q in agg.index]
        ax.plot(xs, agg.values, color=COLORS[method], lw=2.0, marker="o",
                ms=6, label=method)
    ax.set_xlabel("生存概率 $R$")
    ax.set_ylabel("相对 RMSE")
    ax.set_xticks([0.90, 0.95, 0.99])
    ax.legend(frameon=False, fontsize=8.5)
    style_ax(ax)
    ax.set_title("工程寿命分位点 $x_R$ 的相对 RMSE（B3）", fontsize=10.5,
                 color=INK)
    return save_fig(fig, "supp_fig_quantile_rmse.png")


# ============================================================
# Tables (markdown + CSV)
# ============================================================

def md_table(df, col_fmt=None, caption=None):
    cols = list(df.columns)
    lines = []
    if caption:
        lines.append(f"**{caption}**\n")
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "---|" * len(cols))
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if isinstance(v, float):
                fmt = (col_fmt or {}).get(c, "{:.6f}")
                cells.append(fmt.format(v))
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines) + "\n"


def write_table(name, md, csv_df=None):
    os.makedirs(OUT_DIR, exist_ok=True)
    with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as f:
        f.write(md)
    if csv_df is not None:
        csv_df.to_csv(os.path.join(OUT_DIR, name.replace(".md", ".csv")),
                      index=False)
    print(f"  [table] {name}")


def table1_l1_l6():
    df = pd.read_csv(os.path.join(SPECIALIST, "crossfit_layers.csv"))
    role = {"Default": "经验基线", "L1": "全局统一", "L2": "按 $n$",
            "L3": "按 $\\beta$（oracle 参照）", "L4": "按 $\\beta,n$（oracle 参照）",
            "L5": "按 $\\beta,\\gamma/\\eta,n$（oracle 参照）",
            "L6": "逐样本 hindsight 参照"}
    out = df.copy()
    out["role"] = out["layer"].map(role)
    out = out[["layer", "role", "J1", "J1_n7", "J1_n10", "J1_n15", "J1_n20"]]
    out.columns = ["规则", "选择信息", "$J_1$", "$n=7$", "$n=10$", "$n=15$",
                   "$n=20$"]
    md = md_table(out, col_fmt={c: "{:.4f}" for c in out.columns[2:]},
                  caption="表 1：偏移量选择层级（L1–L5 为 repeat-id 五折交叉评价；"
                          "L6 为固定候选网格内 hindsight）")
    write_table("table1_l1_l6.md", md, out)
    return out


def table2_main_results(e6_summary):
    comp = pd.DataFrame(e6_summary["model_comparison"])
    rows = []
    for model, label in (("Dimensional-RAW-MLP", "Dimensional-RAW"),
                         ("Default", "Default ($\\delta=0.1$)"),
                         ("L6-hindsight", "L6 (hindsight)")):
        sub = comp[comp["model"] == model]
        rows.append({
            "方法": label,
            "$J_1$ pooled": float(sub["J1"].mean()),
            "$n=7$": float(sub["J1_n7"].mean()),
            "$n=10$": float(sub["J1_n10"].mean()),
            "$n=15$": float(sub["J1_n15"].mean()),
            "$n=20$": float(sub["J1_n20"].mean()),
            "失败率": float(sub["failure_rate"].mean()),
        })
    out = pd.DataFrame(rows)
    md = md_table(out, col_fmt={c: "{:.4f}" for c in out.columns[1:6]} |
                  {"失败率": "{:.2%}"},
                  caption="表 2：主方法比较（同一留出协议、同一测试样本）")
    write_table("table2_main_results.md", md, out)
    return out


def table3_support_verification(e6_summary, b1_path, b2_path, b3_path):
    rows = []
    dim_pooled = None

    seeds = pd.DataFrame(e6_summary["seed_table"])
    rows.append({
        "问题": "是否依赖一次随机初始化",
        "证据": "三 seed、60 个 fold×seed 模型",
        "结论": (f"pooled $J_1$ = {seeds['pooled_J1'].mean():.4f} "
                 f"± {seeds['pooled_J1'].std():.4f}，结果稳定"),
    })

    if os.path.exists(b1_path):
        with open(b1_path, encoding="utf-8") as f:
            b1 = json.load(f)
        dim = b1["pooled"]["Dimensional_RAW_3seed"]
        dim_pooled = dim["pooled_J1_mean"]
        dflt = b1["pooled"]["Default_J1"]
        rows.append({
            "问题": "未见参数值能否保持收益",
            "证据": "B1 按 $\\beta$ 水平留出（8 折）",
            "结论": (f"未见 $\\beta$ 时 pooled $J_1$ = {dim_pooled:.4f} "
                     f"（Default {dflt:.4f}），失败率 0%，收益保留"),
        })

    if os.path.exists(b2_path):
        b2 = json.load(open(b2_path, encoding="utf-8"))
        s = {r["method"]: r for r in b2["summary"]}
        # same-protocol comparison: E6 combo-holdout DIM-RAW pooled J1 on the
        # same 48,000 samples as WMLE/LSE (B1's beta-holdout is a different
        # evaluation protocol and is reported in the unseen-beta row instead)
        e6_dim = float(e6_summary["dimensional_raw_3seed"]["pooled_J1_mean"])
        rows.append({
            "问题": "与传统方法相比位于什么水平",
            "证据": "B2 WMLE/LSE 同条件参照（同一 48,000 样本）",
            "结论": (f"Dimensional-RAW pooled $J_1$ = {e6_dim:.4f}"
                     f"；WMLE {s['WMLE']['J1']:.4f}、LSE {s['LSE']['J1']:.4f}（参数层面）"),
        })

    if os.path.exists(b3_path):
        b3 = json.load(open(b3_path, encoding="utf-8"))
        d95 = b3["per_method"]["Default"]["per_seed"]["-1"]["x0.95"]
        r95 = b3["per_method"]["Dimensional-RAW"]["per_seed"]["42"]["x0.95"]
        w95 = b3["per_method"]["WMLE"]["per_seed"]["-1"]["x0.95"]
        rows.append({
            "问题": "参数收益能否传递到工程寿命",
            "证据": "B3 $x_{0.90},x_{0.95},x_{0.99}$ 派生",
            "结论": (f"传递有限：$x_{{0.95}}$ 相对 RMSE "
                     f"Dimensional-RAW {r95['rmse']:.4f} ≈ Default "
                     f"{d95['rmse']:.4f}，WMLE {w95['rmse']:.4f} 最低"),
        })

    out = pd.DataFrame(rows)
    out.columns = ["问题", "证据", "结论"]
    md = md_table(out, caption="表 3：支撑验证摘要（细节见补充材料）")
    write_table("table3_support_verification.md", md, out)
    return out


def supp_table_unseen_beta(b1_path):
    if not os.path.exists(b1_path):
        return None
    b1 = json.load(open(b1_path, encoding="utf-8"))
    rows = []
    for beta, models in b1["per_beta"].items():
        rows.append({"留出 $\\beta$": float(beta),
                     "Dimensional-RAW $J_1$": models["Dimensional-RAW"]["J1"],
                     "Default $J_1$": models["Default"]["J1"],
                     "L6 $J_1$": models["L6"]["J1"]})
    out = pd.DataFrame(rows).sort_values("留出 $\\beta$")
    md = md_table(out, col_fmt={c: "{:.4f}" for c in out.columns[1:]},
                  caption="补充表：未见 $\\beta$ 留出验证——每个留出 $\\beta$ 的 pooled $J_1$")
    write_table("supp_table_unseen_beta.md", md, out)
    return out


def supp_table_traditional(b2_path):
    if not os.path.exists(b2_path):
        return None
    b2 = json.load(open(b2_path, encoding="utf-8"))
    sdf = pd.DataFrame(b2["summary"])
    p = pd.DataFrame(b2["param_metrics"])
    rows = []
    for _, r in sdf.iterrows():
        pm = p[p["method"] == r["method"]].iloc[0]
        rows.append({
            "方法": r["method"], "pooled $J_1$": r["J1"],
            "失败率": r["failure_rate"],
            "bias $\\beta$": pm["bias_beta"], "bias $\\eta$": pm["bias_eta"],
            "bias $\\gamma$": pm["bias_gamma"],
            "RMSE $\\beta$": pm["rmse_beta"], "RMSE $\\eta$": pm["rmse_eta"],
            "RMSE $\\gamma$": pm["rmse_gamma"],
        })
    out = pd.DataFrame(rows)
    fmt = {c: "{:.4f}" for c in out.columns if c != "方法"}
    fmt["失败率"] = "{:.3%}"
    md = md_table(out, col_fmt=fmt,
                  caption="补充表：WMLE/LSE 同条件参照（完整样本 Bias/RMSE）")
    write_table("supp_table_traditional.md", md, out)
    return out


def supp_table_quantiles(b3_path):
    if not os.path.exists(b3_path):
        return None
    b3 = pd.read_csv(b3_path)
    rows = []
    for method in METHOD_ORDER:
        m = "Dimensional-RAW" if method == "Dimensional-RAW" else method
        sub = b3[b3["method"] == m]
        for q in ("x0.90", "x0.95", "x0.99"):
            agg = sub[sub["quantile"] == q]
            rows.append({
                "方法": method, "分位点": q,
                "相对 Bias": float(agg["bias"].mean()),
                "相对 RMSE": float(agg["rmse"].mean()),
                "相对 MAE": float(agg["mae"].mean()),
                "P95(|相对误差|)": float(agg["p95_abs_rel"].mean()),
                "失败率": float(agg["failure_rate"].mean()),
            })
    out = pd.DataFrame(rows)
    fmt = {c: "{:.4f}" for c in out.columns[2:6]}
    fmt["失败率"] = "{:.3%}"
    md = md_table(out, col_fmt=fmt,
                  caption="补充表：工程寿命分位点 $x_{0.90}/x_{0.95}/x_{0.99}$ 相对误差指标")
    write_table("supp_table_quantiles.md", md, out)
    return out


# ============================================================
# Index + manifest
# ============================================================

def write_index():
    lines = [
        "# Study01 论文图表与补充材料索引（Dimensional-RAW 当前路线）",
        "",
        "> 生成脚本：`code/generate_paper_figures.py`；所有数值均回指封存产物，"
        "图表可重新生成。旧 G5 特征路线图不在此列。",
        "",
        "## 正文图表",
        "",
        "| 文件 | 内容 | 来源 |",
        "|---|---|---|",
        "| `fig1_method_structure.png` | 方法结构图：排序原始样本→per-n MLP→26 点损失曲线→选 δ→MDM | 03-论文骨架 2.3；本脚本绘制 |",
        "| `fig2_overall_delta_risk.png` | 整体 δ–风险曲线（160 组合 pooled J1） | E5 `shared_data` 26 点损失 |",
        "| `fig3_per_n_J1.png` | Dimensional-RAW / Default / L6 按 n 的 J1 | E6 `specialist/summary.json` |",
        "| `table1_l1_l6.md` | L1–L6 规则/协议/结果 | E6 `specialist/crossfit_layers.csv` |",
        "| `table2_main_results.md` | 主方法比较 | E6 `specialist/summary.json` |",
        "| `table3_support_verification.md` | 支撑验证摘要（四问） | E6 + B1 + B2 + B3 汇总 |",
        "",
        "## 补充材料",
        "",
        "| 文件 | 内容 | 来源 |",
        "|---|---|---|",
        "| `supp_fig_seed_stability.png` | 三 seed 稳定性按 n | E6 `specialist/seed_stability.csv` |",
        "| `supp_fig_unseen_beta.png` | 未见 β 留出验证 | B1 `unseen_beta/summary.json` |",
        "| `supp_fig_traditional_per_n.png` | 传统方法参照按 n | B2 `traditional_ref/summary.csv` + E6 |",
        "| `supp_fig_quantile_rmse.png` | 分位点相对 RMSE | B3 `quantiles/summary.csv` |",
        "| `supp_table_unseen_beta.md` | 每个留出 β 的 J1 | B1 `unseen_beta/beta_holdout.csv` |",
        "| `supp_table_traditional.md` | WMLE/LSE Bias/RMSE | B2 `traditional_ref/summary.json` |",
        "| `supp_table_quantiles.md` | 分位点相对误差指标 | B3 `quantiles/summary.csv` |",
        "",
        "## 复现命令",
        "",
        "```bash",
        "python code/run_b1_unseen_beta.py",
        "python code/run_b2_traditional_ref.py --workers 8",
        "python code/run_b3_quantiles.py",
        "python code/generate_paper_figures.py",
        "```",
        "",
    ]
    with open(os.path.join(OUT_DIR, "README.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))


def main():
    t_start = time.time()
    log = lambda msg: print(msg, flush=True)   # noqa: E731
    os.makedirs(OUT_DIR, exist_ok=True)
    log("=" * 72)
    log("Study/01 paper figures + supplementary tables")
    log(f"Output: {OUT_DIR}")
    log("=" * 72)

    with open(os.path.join(SPECIALIST, "summary.json"), encoding="utf-8") as f:
        e6_summary = json.load(f)

    log("\n[1/7] Method structure schematic...")
    fig1_method_structure()

    log("\n[2/7] Overall delta-risk curve...")
    _mc, df_full, _raw = PS.load_scan(verbose=False)
    fig2_overall_delta_risk(df_full)

    log("\n[3/7] Main results + L1-L6 + support tables...")
    fig3_per_n_J1(e6_summary)
    table1_l1_l6()
    table2_main_results(e6_summary)

    b1_path = os.path.join(PS.UNSEEN_BETA_DIR, "summary.json")
    b2_path = os.path.join(PS.TRADITIONAL_REF_DIR, "summary.json")
    b3_csv = os.path.join(PS.QUANTILES_DIR, "summary.csv")
    b3_json = os.path.join(PS.QUANTILES_DIR, "summary.json")
    table3_support_verification(e6_summary, b1_path, b2_path, b3_json)

    log("\n[4/7] Supplementary figures...")
    supp_fig_seed_stability(e6_summary)
    supp_fig_unseen_beta(b1_path)
    supp_fig_traditional_per_n(os.path.join(PS.TRADITIONAL_REF_DIR,
                                            "summary.csv"), e6_summary)
    supp_fig_quantile_rmse(b3_csv)

    log("\n[5/7] Supplementary tables...")
    supp_table_unseen_beta(b1_path)
    supp_table_traditional(b2_path)
    supp_table_quantiles(b3_csv)

    log("\n[6/7] Index + provenance...")
    write_index()
    manifest = {
        "generator": "code/generate_paper_figures.py",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "code_sha256": PS.code_sha256(PS),
        "matplotlib": matplotlib.__version__,
        "palette": "validated categorical slots (light): "
                   "blue/orange/aqua/magenta/green",
        "sources": {
            "e6_specialist": "artifacts/formal/E6_dimensional_raw/specialist",
            "b1": "artifacts/formal/E6_dimensional_raw/unseen_beta",
            "b2": "artifacts/formal/E6_dimensional_raw/traditional_ref",
            "b3": "artifacts/formal/E6_dimensional_raw/quantiles",
        },
        "output_files": ["README.md", "manifest.json", "SHA256SUMS"] + sorted(
            f for f in os.listdir(OUT_DIR)
            if f.endswith((".png", ".md")) or f.endswith(".csv")),
        "elapsed_s": float(time.time() - t_start),
        **PS.git_meta(),
    }
    PS.atomic_write_json(manifest, os.path.join(OUT_DIR, "manifest.json"))
    for p in (os.path.join(OUT_DIR, "README.md"),
              os.path.join(OUT_DIR, "manifest.json")):
        PS.lf_normalize(p)
    n_entries = PS.write_sha256sums(OUT_DIR)
    log(f"\nDone in {time.time()-t_start:.1f}s. Outputs in {OUT_DIR} "
        f"(SHA256SUMS: {n_entries} entries)")


if __name__ == "__main__":
    main()
