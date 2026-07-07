"""
Figure diagnostics: Ch1-Ch5 图像解释链补齐

4 张图：
  Fig A (fig_offset_mechanism): δ 机制/波动诊断三子图（Ch2 §4，Figure 1）
    - 三 panel 共享代表配置 β=2.0, η=1000, γ=1000, n=7（贴近 182-046 语境）
    - Panel A：真实 MDM γ profile / 梯度判据图
      - 用 generate_sample(β=2.0, η=1000, γ=1000, n=7) + MDM(trace=True) 计算
      - 横轴 γ，纵轴 ∂σ_η,min(γ)/∂γ（真实计算值）
      - 两条水平判据线：y=0（zero-gradient）与 y=0.1（offset δ）
      - 3 条真实 grad_gamma_curve，按可复现规则从 100 样本中选出
      - zero marker = curve-derived；offset marker = solver root
      - 视觉语境参考 182-046 图4，但非原图复刻
    - Panel B：δ=0 与 δ=0.1 的 γ̂ 分布（MC R=1000，数据源 mc_scan_raw.csv）
    - Panel C：同上的归一化误差 (γ̂-γ)/η 分布

  Fig B (fig_l2_n_heterogeneity): L2/n 双 panel 诊断
    - Panel A: pooled δ-risk by n (n=7/10/20)，标 δ*
    - Panel B: within each n, δ-risk curves split by β
    - 数据源：delta_risk_curve.csv (Panel A) + mc_scan_raw.csv (Panel B)
    - 目标：Ch4 §2

  Fig C (fig_l4_beta_n_heatmap): β×n δ* heatmap
    - 数据源：L4_by_beta_n.csv
    - 目标：Ch5 §3

  Fig D (fig_l5_heatmap): L5 β×γ/η×n heatmap (supplementary)
    - 数据源：L5_by_beta_goe_n.csv
    - 目标：附录

聚合规则与 analyze_E1.py / plot_fig2.py 完全一致：
  j1_sq = (Δβ/β)² + (Δη/η)² + (Δγ/η)²，先 mean(j1_sq) 再 sqrt

可复现性：若 mc_scan_raw.csv 缺失，脚本会打印明确指令，不会自动运行
generate_mc_data.py。请用户手动执行：
  python code/generate_mc_data.py --merge-only

输出: artifacts/formal/figures/fig_*.{svg,pdf,png}
"""

import os
import sys
import json

import matplotlib as mpl
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import numpy as np
import pandas as pd

# ── MDM 方法路径（真实 trace 计算）──
# __file__ = .../Study/01-.../code/plot_fig_diagnostics.py
# STUDY_DIR = dirname(dirname(__file__)) = .../Study/01-.../
# 需要到 D:\weibull\python，即 STUDY_DIR 往上两层
_STUDY_PARENT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_REPO_ROOT = os.path.dirname(_STUDY_PARENT)
_PYTHON_DIR = os.path.join(_REPO_ROOT, "python")
if _PYTHON_DIR not in sys.path:
    sys.path.insert(0, _PYTHON_DIR)
from studies.common.sample import generate_sample
from methods.mdm import MDM

# ── 路径 ──
STUDY_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
E1_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "E1_baseline")
E2_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "E2_oracle_layers")
SHARED_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "shared_data")
FIG_DIR = os.path.join(STUDY_DIR, "artifacts", "formal", "figures")
os.makedirs(FIG_DIR, exist_ok=True)

# ── 出版级 rcParams（与 plot_fig2.py 一致）──
mpl.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans", "sans-serif"],
    "svg.fonttype": "none",
    "pdf.fonttype": 42,
    "font.size": 7,
    "axes.labelsize": 8,
    "axes.titlesize": 8,
    "xtick.labelsize": 6,
    "ytick.labelsize": 6,
    "legend.fontsize": 6,
    "axes.spines.right": False,
    "axes.spines.top": False,
    "axes.linewidth": 0.8,
    "legend.frameon": False,
    "xtick.major.size": 3,
    "ytick.major.size": 3,
    "xtick.major.width": 0.8,
    "ytick.major.width": 0.8,
})

# Okabe-Ito 色盲安全调色板（与 plot_fig2.py 一致）
OKABE_ITO = {
    1.5: "#E69F00",
    2.0: "#56B4E9",
    2.5: "#009E73",
    4.0: "#0072B2",
    5.0: "#D55E00",
}

# n 值调色板（灰阶递进，n 大 = 深）
N_COLORS = {7: "#9ecae1", 10: "#4292c6", 20: "#08519c"}


def save_three_formats(fig, out_base):
    """保存 SVG + PDF + PNG 三格式。"""
    fig.savefig(f"{out_base}.svg", bbox_inches="tight")
    fig.savefig(f"{out_base}.pdf", bbox_inches="tight")
    fig.savefig(f"{out_base}.png", dpi=300, bbox_inches="tight")
    print(f"  Saved: {os.path.basename(out_base)}.{{svg,pdf,png}}")


def ensure_mc_scan_raw():
    """检查 mc_scan_raw.csv 是否存在。

    若缺失，打印明确指令让用户手动运行 merge，返回 False。
    本脚本不会自动运行 generate_mc_data.py。
    """
    csv_path = os.path.join(SHARED_DIR, "mc_scan_raw.csv")
    if os.path.exists(csv_path):
        return True
    print("\n" + "=" * 60)
    print("ERROR: mc_scan_raw.csv not found at:")
    print(f"  {csv_path}")
    print("\nThis file is excluded from git (too large). To rebuild it")
    print("from the tracked chunks, run from the Study/01 directory:")
    print()
    print("  python code/generate_mc_data.py --merge-only")
    print()
    print("Do NOT run the full generate_mc_data.py without --merge-only,")
    print("as that would regenerate MC data (not needed for figures).")
    print("=" * 60 + "\n")
    return False


# ============================================================
# Fig A: δ mechanism schematic (概念图)
# ============================================================

def _scan_mdm_samples(beta, eta, gamma_true, n, delta, n_repeats=100,
                      gamma_steps=200, cache_path=None):
    """扫描 n_repeats 个样本，对每个样本计算 curve-derived zero marker
    和 offset solver root。

    可复现性：seed=None（项目默认 namespace），种子由
    generate_sample(beta, eta, gamma, n, repeat_id) 内部 sha256 确定。

    Returns:
        list of dict, 每个 dict 含 rid/sample/gamma_zero_curve/
        gamma_offset_solver/err_zero/err_offset/grad_curve(offset run)
    """
    results = []
    for rid in range(n_repeats):
        sample = generate_sample(beta, eta, gamma_true, n, rid, seed=None)
        sample_list = sample.tolist()

        mdm = MDM(sample_list)
        beta_h, eta_h, gamma_off, r2, conv = mdm.run(
            trace=True, offset=delta, gamma_steps=gamma_steps
        )
        grad_curve = mdm.trace_data.get("grad_gamma_curve", [])

        gs = np.array([p["gamma"] for p in grad_curve])
        grads = np.array([p["gradient"] for p in grad_curve])

        # curve-derived zero marker：找 sign change 插值，否则取最接近 0 的点
        zero_interp = False
        gamma_zero = None
        sign_changes = []
        for i in range(len(grads) - 1):
            if grads[i] * grads[i + 1] < 0:
                t = grads[i] / (grads[i] - grads[i + 1])
                g_interp = gs[i] + t * (gs[i + 1] - gs[i])
                sign_changes.append(g_interp)
        if sign_changes:
            gamma_zero = min(sign_changes, key=lambda g: abs(g - gamma_true))
            zero_interp = True
        elif len(grads) > 0:
            idx = int(np.argmin(np.abs(grads)))
            gamma_zero = float(gs[idx])

        results.append({
            "rid": rid,
            "sample": sample_list,
            "gamma_zero_curve": float(gamma_zero) if gamma_zero is not None else None,
            "zero_interp": zero_interp,
            "gamma_offset_solver": float(gamma_off),
            "err_zero_curve": (gamma_zero - gamma_true) / gamma_true * 100
                              if gamma_zero is not None else None,
            "err_offset": (gamma_off - gamma_true) / gamma_true * 100,
            "grad_curve": grad_curve,
        })
    return results


def _select_representative_samples(results, gamma_true):
    """按可复现规则从扫描结果选 3 个代表样本。

    选择规则（不手工挑图）：
      - closest: |err_zero| 最小
      - largest_improvement: |err_zero|-|err_offset| 最大
      - mild_worsening: 从 worsening 样本（|err_offset|>|err_zero|）中，
        按 worsening 增量（|err_offset|-|err_zero|）取中位数附近的样本，
        避免极端样本拉满 y 轴。若没有 worsening 样本，返回 None。
    """
    valid = [r for r in results if r["gamma_zero_curve"] is not None]

    closest = min(valid, key=lambda r: abs(r["err_zero_curve"]))

    improvers = sorted(
        valid,
        key=lambda r: -(abs(r["err_zero_curve"]) - abs(r["err_offset"])),
    )
    best_imp = improvers[0]

    # worsening 池：只保留真正变差的样本
    worseners = [r for r in valid
                 if abs(r["err_offset"]) > abs(r["err_zero_curve"])]
    if not worseners:
        best_worsen = None
    else:
        # 按 worsening 增量排序，取中位数附近的样本
        worseners_sorted = sorted(
            worseners,
            key=lambda r: (abs(r["err_offset"]) - abs(r["err_zero_curve"])),
        )
        mid_idx = len(worseners_sorted) // 2
        best_worsen = worseners_sorted[mid_idx]

    return closest, best_imp, best_worsen

def plot_fig_offset_mechanism():
    """δ 机制/波动诊断三子图（Figure 1）。

    三 panel 共享代表配置 β=2.0, η=1000, γ=1000, n=7（贴近 182-046 语境）。
      - Panel A：真实 MDM γ profile / 梯度判据图。扫描 repeat_id=0-99，
        按可复现规则选 3 个代表样本（closest-to-true / largest-improvement /
        mild-worsening），从 grad_gamma_curve 绘制 y=0 与 y=δ=0.1 两条
        判据线及对应搜索位置。每条曲线是真实计算结果，不是 stylized schematic。
      - Panel B：δ=0 与 δ=0.1 的 γ̂ 分布（n=7，MC R=1000）。
        数据来自正式 mc_scan_raw.csv（与 Panel A 等价配置 eta=1.0/gamma=1.0，
        显示时乘 1000 以对齐 Panel A 的 γ=1000 语境）。
      - Panel C：同上的归一化误差 (γ̂-γ)/η 分布。
    """
    print("\n[Fig A] δ gradient-criterion (real MDM trace) ...")

    beta, eta, gamma_true, n, delta = 2.0, 1000.0, 1000.0, 7, 0.1

    cache_path = os.path.join(STUDY_DIR, "code", "_mdm_scan_cache.json")
    # 扫描（有缓存则读缓存，避免每次重跑 30 秒）
    if os.path.exists(cache_path):
        print(f"  Loading cached scan from {os.path.basename(cache_path)}")
        with open(cache_path) as f:
            results = json.load(f)
    else:
        print(f"  Scanning {100} samples (β={beta}, n={n}) ...")
        results = _scan_mdm_samples(beta, eta, gamma_true, n, delta,
                                    n_repeats=100, gamma_steps=200)
        with open(cache_path, "w") as f:
            json.dump(results, f)
        print(f"  Cached scan to {os.path.basename(cache_path)}")

    closest, best_imp, best_worsen = _select_representative_samples(
        results, gamma_true
    )

    # 构建绘图数据
    plot_items = [
        (f"rid={closest['rid']} (closest)", closest, "#009E73", "o"),
        (f"rid={best_imp['rid']} (δ improves)", best_imp, "#D55E00", "s"),
    ]
    if best_worsen is not None:
        plot_items.append(
            (f"rid={best_worsen['rid']} (mild worsening)", best_worsen, "#0072B2", "^")
        )

    print(f"  Selected samples:")
    for label, r, _, _ in plot_items:
        print(f"    {label}: γ_zero={r['gamma_zero_curve']:.1f} "
              f"(err {r['err_zero_curve']:+.1f}%) -> "
              f"γ_offset={r['gamma_offset_solver']:.1f} "
              f"(err {r['err_offset']:+.1f}%)")

    fig = plt.figure(figsize=(13.5, 4.2))
    gs = gridspec.GridSpec(1, 3, width_ratios=[1.0, 1.0, 1.0],
                            wspace=0.32, figure=fig)
    ax_a = fig.add_subplot(gs[0, 0])
    ax_b = fig.add_subplot(gs[0, 1])
    ax_c = fig.add_subplot(gs[0, 2])

    # 先固定轴范围，避免后续 text/marker 放置位置不确定
    ax_a.set_xlim(-20, 1900)
    ax_a.set_ylim(-0.2, 0.6)

    # ── 绘制真实 grad_gamma_curve ──
    for label, r, color, marker in plot_items:
        curve = r["grad_curve"]
        gs = np.array([p["gamma"] for p in curve])
        grads = np.array([p["gradient"] for p in curve])
        ax_a.plot(gs, grads, color=color, linewidth=0.9, alpha=0.8,
                zorder=3, label=label)

    # ── 两条水平判据线 ──
    ax_a.axhline(0.0, color="#333333", linewidth=0.8, linestyle="--", zorder=2)
    ax_a.axhline(delta, color="#333333", linewidth=0.8, linestyle="-.", zorder=2)
    # 判据线标签贴近对应 data y 值，避免视觉上脱离水平线
    label_x = 1860
    ax_a.text(label_x, 0.012, r"$\nabla\gamma=0$ (zero-grad)",
            fontsize=5.5, color="#333333", ha="right", va="bottom")
    ax_a.text(label_x, delta + 0.012, r"$\nabla\gamma=\delta=0.1$ (offset)",
            fontsize=5.5, color="#333333", ha="right", va="bottom")

    # ── 真实 γ 参考线 ──
    ax_a.axvline(gamma_true, color="#999999", linewidth=0.6,
               linestyle=":", zorder=1)
    ax_a.text(0.53, 0.95, r"True $\gamma$",
            transform=ax_a.transAxes, fontsize=5.5, color="#666666",
            ha="center", va="top")

    # ── marker ──
    for label, r, color, marker in plot_items:
        # zero marker：curve-derived
        g_zero = r["gamma_zero_curve"]
        # 找曲线在 g_zero 处的 gradient 值
        curve = r["grad_curve"]
        gs = np.array([p["gamma"] for p in curve])
        grads = np.array([p["gradient"] for p in curve])
        if r["zero_interp"]:
            grad_at_zero = 0.0
        else:
            idx = int(np.argmin(np.abs(gs - g_zero)))
            grad_at_zero = float(grads[idx])
        ax_a.scatter([g_zero], [grad_at_zero], color=color, s=30,
                   marker=marker, zorder=5, clip_on=False,
                   edgecolors="white", linewidths=0.4)

        # offset marker：solver root，gradient=delta（solver 定义）
        g_off = r["gamma_offset_solver"]
        ax_a.scatter([g_off], [delta], color=color, s=30,
                   marker=marker, zorder=5, clip_on=False,
                   edgecolors="white", linewidths=0.4)

        # 连接线（同一曲线两个 marker）
        ax_a.annotate("", xy=(g_off, delta), xytext=(g_zero, grad_at_zero),
                    arrowprops=dict(arrowstyle="->", lw=0.6,
                                    color=color, alpha=0.5,
                                    connectionstyle="arc3,rad=0.1"))

    # ── 核心机制标注：判据线从 y=0 移到 y=δ ──
    # 在 true γ 附近画双向竖箭头，从 y=0 到 y=0.1
    arrow_x = gamma_true + 60  # 略偏右，不挡参考线
    ax_a.annotate("", xy=(arrow_x, delta), xytext=(arrow_x, 0.0),
                arrowprops=dict(arrowstyle="<->", lw=1.0, color="#D55E00",
                                shrinkA=0, shrinkB=0))
    ax_a.text(arrow_x + 25, delta / 2, r"criterion offset $\delta=0.1$",
            fontsize=5.5, color="#D55E00", ha="left", va="center",
            fontweight="bold")

    # ── 对 largest-improvement 样本（rid=77）标出水平位移 ──
    imp_item = next((it for it in plot_items if "improves" in it[0]), None)
    if imp_item is not None:
        _, imp_r, imp_color, _ = imp_item
        g_z = imp_r["gamma_zero_curve"]
        g_o = imp_r["gamma_offset_solver"]
        # zero criterion 标注（在 zero marker 附近）
        ax_a.annotate("zero: boundary /\nnear-flat point",
                    xy=(g_z, 0.0087 if not imp_r["zero_interp"] else 0.0),
                    xytext=(g_z + 250, -0.125),
                    fontsize=4.8, color=imp_color, ha="left", va="top",
                    arrowprops=dict(arrowstyle="->", lw=0.5,
                                    color=imp_color, alpha=0.7))
        # offset criterion 标注（在 offset marker 附近）
        ax_a.annotate(r"offset: $\gamma$ near true $\gamma$",
                    xy=(g_o, delta),
                    xytext=(g_o + 105, 0.32),
                    fontsize=4.8, color=imp_color, ha="left", va="bottom",
                    arrowprops=dict(arrowstyle="->", lw=0.5,
                                    color=imp_color, alpha=0.7))

    # ── 轴 ──
    ax_a.set_xlabel(r"Location parameter $\gamma$")
    ax_a.set_ylabel(
        r"Profile gradient $\partial\sigma_{\eta,\min}(\gamma)/\partial\gamma$"
    )
    # y 轴聚焦判据区间 [-0.2, 0.6]（已在绘图前设置），裁切 γ→t_min 的梯度尖峰
    ax_a.legend(loc="upper right", fontsize=5.5, framealpha=0.85,
              edgecolor="#cccccc")


    # ── Panel B：δ=0 vs δ=0.1 的 γ̂ 分布 ──
    if not ensure_mc_scan_raw():
        raise RuntimeError("mc_scan_raw.csv 缺失，无法绘制 Panel B/C")
    mc_path = os.path.join(SHARED_DIR, "mc_scan_raw.csv")
    mc = pd.read_csv(mc_path)
    # 筛选与 Panel A 等价的配置：β=2.0, η=1.0, γ/η=1.0, n=7（尺度等价 W(2,1000,1000),n=7）
    sub = mc[(mc["beta"] == 2.0) & (mc["eta"] == 1.0) &
             (mc["gamma_over_eta"] == 1.0) & (mc["n"] == 7) &
             (mc["delta"].isin([0.0, 0.1])) & (mc["converged"] == True)].copy()
    d0 = sub[sub["delta"] == 0.0]
    d1 = sub[sub["delta"] == 0.1]
    # eta=1 数据乘 1000 对齐 Panel A 的 γ=1000 语境
    gh0 = d0["gamma_hat"].values * 1000.0
    gh1 = d1["gamma_hat"].values * 1000.0

    bins_b = np.linspace(min(gh0.min(), gh1.min()),
                         max(gh0.max(), gh1.max()), 45)
    ax_b.hist(gh0, bins=bins_b, density=True, alpha=0.55,
              color="#0072B2", edgecolor="white", linewidth=0.3,
              label=r"$\delta=0$ (zero-grad)")
    ax_b.hist(gh1, bins=bins_b, density=True, alpha=0.55,
              color="#D55E00", edgecolor="white", linewidth=0.3,
              label=r"$\delta=0.1$ (offset)")
    ax_b.axvline(1000.0, color="#999999", linewidth=0.8,
                 linestyle=":", zorder=2)
    ax_b.text(0.04, 0.95, "True $\\gamma=1000$",
              transform=ax_b.transAxes, fontsize=6, color="#666666",
              ha="left", va="top")
    ax_b.set_xlabel(r"Location estimate $\hat{\gamma}$")
    ax_b.set_ylabel("Density")
    ax_b.set_title(r"Panel B: $\hat{\gamma}$ distribution",
                   fontweight="bold", loc="left", fontsize=7)
    ax_b.legend(loc="upper right", fontsize=5.5, framealpha=0.85,
                edgecolor="#cccccc")

    # ── Panel C：归一化误差 (γ̂-γ)/η 分布 ──
    # eta=1, gamma=1，所以 (gamma_hat - gamma)/eta = gamma_hat - 1
    err0 = (d0["gamma_hat"].values - 1.0) / 1.0
    err1 = (d1["gamma_hat"].values - 1.0) / 1.0
    bins_c = np.linspace(min(err0.min(), err1.min()),
                         max(err0.max(), err1.max()), 45)
    ax_c.hist(err0, bins=bins_c, density=True, alpha=0.55,
              color="#0072B2", edgecolor="white", linewidth=0.3,
              label=r"$\delta=0$ (zero-grad)")
    ax_c.hist(err1, bins=bins_c, density=True, alpha=0.55,
              color="#D55E00", edgecolor="white", linewidth=0.3,
              label=r"$\delta=0.1$ (offset)")
    ax_c.axvline(0.0, color="#999999", linewidth=0.8,
                 linestyle=":", zorder=2)
    ax_c.text(0.04, 0.95, "Zero error",
              transform=ax_c.transAxes, fontsize=6, color="#666666",
              ha="left", va="top")
    ax_c.set_xlabel(r"Normalized error $(\hat{\gamma}-\gamma)/\eta$")
    ax_c.set_ylabel("Density")
    ax_c.set_title(r"Panel C: normalized $\hat{\gamma}$ error",
                   fontweight="bold", loc="left", fontsize=7)
    ax_c.legend(loc="upper right", fontsize=5.5, framealpha=0.85,
                edgecolor="#cccccc")

    # Panel A 标题
    ax_a.set_title(
        r"Panel A: $\delta$ shifts gradient criterion (real MDM trace)"
        "\n(per-sample effect varies)",
        fontweight="bold", loc="left", fontsize=7,
    )

    # ── Panel B/C 诊断数字 ──
    print(f"  Panel B/C (mc_scan_raw.csv筛选 n={len(d0)}+{len(d1)}):")
    print(f"    δ=0:   γ̂ median={np.median(gh0):.1f}, "
          f"|err| median={np.median(np.abs(err0)):.3f}")
    print(f"    δ=0.1: γ̂ median={np.median(gh1):.1f}, "
          f"|err| median={np.median(np.abs(err1)):.3f}")

    out_base = os.path.join(FIG_DIR, "fig_offset_mechanism")
    fig.tight_layout(pad=0.5)
    save_three_formats(fig, out_base)
    plt.close(fig)

    # QA
    print(f"  True γ = {gamma_true}")
    print(f"  Curve points per sample: {len(plot_items[0][1]['grad_curve'])}")
    for label, r, _, _ in plot_items:
        print(f"    {label}: sample={[f'{v:.1f}' for v in r['sample'][:3]]}...")
        print(f"      γ_zero(curve)={r['gamma_zero_curve']:.1f} "
              f"(err {r['err_zero_curve']:+.1f}%, interp={r['zero_interp']})")
        print(f"      γ_offset(solver δ=0.1)={r['gamma_offset_solver']:.1f} "
              f"(err {r['err_offset']:+.1f}%)")


# ============================================================
# Fig B: L2/n heterogeneity (GridSpec 布局，无重叠)
# ============================================================
def plot_fig_l2_n_heterogeneity(by_nb=None):
    """
    使用 GridSpec 2列布局：
      左列（1个大子图）：Panel A，pooled δ-risk by n
      右列（3个小子图纵向排列）：Panel B，每个 n 内 split by β

    Args:
        by_nb: 预聚合的 (n, β, δ) → J1 DataFrame。
               若为 None，则从 mc_scan_raw.csv 聚合。
               若 mc_scan_raw 缺失，打印指令并返回。
    """
    print("\n[Fig B] L2/n heterogeneity diagnostic ...")

    # Panel A 数据（已聚合，总是可用）
    curve = pd.read_csv(os.path.join(E1_DIR, "delta_risk_curve.csv"))

    # Panel B 数据
    if by_nb is None:
        if not ensure_mc_scan_raw():
            print("  [SKIP] fig_l2_n_heterogeneity: mc_scan_raw.csv missing")
            return
        print("  Reading mc_scan_raw.csv for Panel B ...")
        df_raw = pd.read_csv(os.path.join(SHARED_DIR, "mc_scan_raw.csv"))
        df = df_raw[df_raw["converged"]].copy()
        df["j1_sq"] = (
            ((df["beta_hat"] - df["beta"]) / df["beta"]) ** 2
            + ((df["eta_hat"] - df["eta"]) / df["eta"]) ** 2
            + ((df["gamma_hat"] - df["gamma"]) / df["eta"]) ** 2
        )
        df = df[np.isfinite(df["j1_sq"])]
        by_nb = df.groupby(["n", "beta", "delta"])["j1_sq"].mean().reset_index()
        by_nb["J1"] = np.sqrt(by_nb["j1_sq"])
    print(f"  Panel B aggregation: {len(by_nb)} rows")

    # ── GridSpec 布局：左1大 + 右3小 ──
    fig = plt.figure(figsize=(7.5, 3.5))
    gs = gridspec.GridSpec(3, 2, width_ratios=[1, 1.1], height_ratios=[1, 1, 1],
                           hspace=0.45, wspace=0.25,
                           left=0.08, right=0.96, top=0.88, bottom=0.16)

    ax_a = fig.add_subplot(gs[:, 0])  # 左侧整列
    sub_axes = [fig.add_subplot(gs[i, 1]) for i in range(3)]  # 右侧3行

    n_vals = [7, 10, 20]
    beta_vals = [1.5, 2.0, 2.5, 4.0, 5.0]

    # ──────────── Panel A: pooled by n ────────────
    delta_stars_by_n = {}
    for n_val in n_vals:
        col = f"J1_n{n_val}"
        yvals = curve[col].values
        color = N_COLORS[n_val]
        ax_a.plot(curve["delta"], yvals, color=color, linewidth=1.1,
                  label=f"n = {n_val}")
        idx_min = np.argmin(yvals)
        ds = curve["delta"].iloc[idx_min]
        delta_stars_by_n[n_val] = ds
        j1_min = yvals[idx_min]
        ax_a.scatter([ds], [j1_min], color=color, s=12, zorder=5, clip_on=False)

    for n_val in [7, 20]:
        ds = delta_stars_by_n[n_val]
        ax_a.annotate(f"$\\delta^*$={ds:.2f}",
                      xy=(ds, curve[f"J1_n{n_val}"].min()),
                      xytext=(ds + 0.04 if n_val == 7 else ds - 0.18,
                              curve[f"J1_n{n_val}"].min() + 0.02),
                      fontsize=5.5, color=N_COLORS[n_val])

    ax_a.axvline(0.10, color="#666666", linewidth=0.5, linestyle=":", zorder=2)
    ax_a.text(0.105, ax_a.get_ylim()[0] + 0.01, "Default", fontsize=5,
              color="#666666")

    ax_a.set_xlabel(r"Offset $\delta$")
    ax_a.set_ylabel(r"$J_1$ (pooled by $n$)")
    ax_a.set_xlim(-0.01, 0.52)
    ax_a.legend(loc="upper left", handlelength=1.2)
    ax_a.set_title("(a) $\\delta$-risk pooled by $n$\n(all $\\beta$ combined)",
                    fontweight="bold", loc="left", fontsize=7)

    # ──────────── Panel B: within each n, split by β ────────────
    for i, n_val in enumerate(n_vals):
        ax_sub = sub_axes[i]
        for beta_val in beta_vals:
            sub = by_nb[(by_nb["n"] == n_val) & (by_nb["beta"] == beta_val)]
            sub = sub.sort_values("delta")
            color = OKABE_ITO[beta_val]
            ax_sub.plot(sub["delta"], sub["J1"], color=color, linewidth=0.8,
                        label=f"β={beta_val}")
            if beta_val in (1.5, 5.0):
                idx_min = sub["J1"].idxmin()
                ds = sub.loc[idx_min, "delta"]
                ax_sub.scatter([ds], [sub.loc[idx_min, "J1"]], color=color,
                               s=8, zorder=5, clip_on=False)

        ax_sub.axvline(0.10, color="#666666", linewidth=0.4, linestyle=":", zorder=1)
        ax_sub.set_title(f"(b{i+1}) n = {n_val}", fontsize=6.5, fontweight="bold",
                         loc="left")
        ax_sub.set_xlim(-0.01, 0.52)
        if i == 0:
            ax_sub.set_ylabel(r"$J_1$")
            ax_sub.legend(loc="upper left", fontsize=4.5, handlelength=0.8,
                          columnspacing=0.3)
        if i == 2:
            ax_sub.set_xlabel(r"Offset $\delta$")
        ax_sub.tick_params(labelsize=5)

    # Panel B 整体说明（用 figtext 放在右侧顶部）
    fig.text(0.55, 0.93,
             "(b) Within each $n$: $\\delta$-risk split by $\\beta$\n"
             "same $n$, different $\\beta$ → opposite $\\delta^*$",
             fontsize=6.5, fontweight="bold", ha="left", va="bottom")

    out_base = os.path.join(FIG_DIR, "fig_l2_n_heterogeneity")
    save_three_formats(fig, out_base)
    plt.close(fig)

    # QA
    print("  Panel A δ* by n:")
    for n_val in n_vals:
        print(f"    n={n_val}: δ*={delta_stars_by_n[n_val]:.2f}, "
              f"J1_min={curve[f'J1_n{n_val}'].min():.4f}")
    print("  Panel B δ* by (n, β):")
    for n_val in n_vals:
        for beta_val in [1.5, 5.0]:
            sub = by_nb[(by_nb["n"] == n_val) & (by_nb["beta"] == beta_val)]
            idx_min = sub["J1"].idxmin()
            ds = sub.loc[idx_min, "delta"]
            print(f"    n={n_val}, β={beta_val}: δ*={ds:.2f}")


# ============================================================
# Fig C: β×n δ* heatmap (L4)
# ============================================================

def plot_fig_l4_beta_n_heatmap():
    print("\n[Fig C] β×n δ* heatmap (L4) ...")
    df = pd.read_csv(os.path.join(E2_DIR, "L4_by_beta_n.csv"))

    pivot = df.pivot(index="beta", columns="n", values="delta_star_L4")
    beta_order = [1.5, 2.0, 2.5, 4.0, 5.0]
    n_order = [7, 10, 20]
    pivot = pivot.reindex(index=beta_order, columns=n_order)

    fig, ax = plt.subplots(figsize=(3.2, 3.0))
    im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto",
                   vmin=0, vmax=0.55)

    for i in range(len(beta_order)):
        for j in range(len(n_order)):
            val = pivot.values[i, j]
            color = "white" if val > 0.3 else "#333333"
            ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                    fontsize=7, fontweight="bold", color=color)

    ax.set_xticks(range(len(n_order)))
    ax.set_xticklabels([f"n = {n}" for n in n_order])
    ax.set_yticks(range(len(beta_order)))
    ax.set_yticklabels([f"β = {b}" for b in beta_order])

    cbar = fig.colorbar(im, ax=ax, shrink=0.8, pad=0.02)
    cbar.set_label(r"Optimal $\delta^*$ (L4)", fontsize=6)
    cbar.ax.tick_params(labelsize=5)

    ax.set_title(r"$\delta^*$ by $\beta$ (rows) and $n$ (columns)"
                 "\n" + r"$\beta$ = main effect, $n$ = modifier",
                 fontweight="bold", loc="left", fontsize=7)

    ax.spines["right"].set_visible(True)
    ax.spines["top"].set_visible(True)

    out_base = os.path.join(FIG_DIR, "fig_l4_beta_n_heatmap")
    fig.tight_layout(pad=0.5)
    save_three_formats(fig, out_base)
    plt.close(fig)

    print("  Heatmap values:")
    print(pivot.to_string())
    row_range = pivot.max(axis=1) - pivot.min(axis=1)
    col_range = pivot.max(axis=0) - pivot.min(axis=0)
    print(f"  β主效应 (列方向range, per n): {col_range.to_dict()}")
    print(f"  n调节项 (行方向range, per β): {row_range.to_dict()}")
    print(f"  β平均跨度: {col_range.mean():.3f}, n平均跨度: {row_range.mean():.3f}")


# ============================================================
# Fig D: L5 β×γ/η×n heatmap (supplementary)
# ============================================================

def plot_fig_l5_heatmap():
    print("\n[Fig D] L5 β×γ/η×n heatmap (supplementary) ...")
    df = pd.read_csv(os.path.join(E2_DIR, "L5_by_beta_goe_n.csv"))

    beta_order = [1.5, 2.0, 2.5, 4.0, 5.0]
    goe_order = [0.1, 0.5, 1.0]
    n_order = [7, 10, 20]

    fig, axes = plt.subplots(1, 3, figsize=(6.5, 2.8), sharey=True)

    for idx, n_val in enumerate(n_order):
        ax = axes[idx]
        sub = df[df["n"] == n_val]
        pivot = sub.pivot(index="beta", columns="gamma_over_eta",
                          values="delta_star_L5")
        pivot = pivot.reindex(index=beta_order, columns=goe_order)

        im = ax.imshow(pivot.values, cmap="YlOrRd", aspect="auto",
                       vmin=0, vmax=0.55)

        for i in range(len(beta_order)):
            for j in range(len(goe_order)):
                val = pivot.values[i, j]
                color = "white" if val > 0.3 else "#333333"
                ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                        fontsize=6, fontweight="bold", color=color)

        ax.set_xticks(range(len(goe_order)))
        ax.set_xticklabels([f"{g}" for g in goe_order])
        ax.set_xlabel(r"$\gamma/\eta$", fontsize=6)
        if idx == 0:
            ax.set_yticks(range(len(beta_order)))
            ax.set_yticklabels([f"{b}" for b in beta_order])
            ax.set_ylabel(r"$\beta$", fontsize=7)
        ax.set_title(f"n = {n_val}", fontsize=7, fontweight="bold")
        ax.tick_params(labelsize=5)

    cbar = fig.colorbar(im, ax=axes, shrink=0.8, pad=0.02)
    cbar.set_label(r"$\delta^*$ (L5)", fontsize=6)
    cbar.ax.tick_params(labelsize=5)

    fig.suptitle(r"L5 $\delta^*$: $\beta$ (main) × $\gamma/\eta$ × $n$"
                 "  — γ/η detail effect, small margin",
                 fontsize=7, fontweight="bold", x=0.02, ha="left")

    out_base = os.path.join(FIG_DIR, "fig_l5_heatmap")
    save_three_formats(fig, out_base)
    plt.close(fig)

    l4 = pd.read_csv(os.path.join(E2_DIR, "L4_by_beta_n.csv"))
    l5_grouped = df.groupby(["beta", "n"]).agg({"J1_at_L5": "mean"}).reset_index()
    l4_grouped = l4.groupby(["beta", "n"]).agg({"J1_at_L4": "mean"}).reset_index()
    merged = l4_grouped.merge(l5_grouped, on=["beta", "n"])
    merged["improvement_pct"] = (1 - merged["J1_at_L5"] / merged["J1_at_L4"]) * 100
    print(f"  L4→L5 mean improvement: {merged['improvement_pct'].mean():.2f}% "
          f"(range {merged['improvement_pct'].min():.2f}%-{merged['improvement_pct'].max():.2f}%)")


# ============================================================
# Main
# ============================================================

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Figure diagnostics plotting")
    parser.add_argument("--only", type=str, default="A",
                        help="Which figure to generate: A (default), B, C, D, or all")
    args = parser.parse_args()

    print("=" * 60)
    print("Figure diagnostics: Ch1-Ch5 图像解释链补齐")
    print(f"  Generating: {args.only}")
    print("=" * 60)

    if args.only in ("A", "all"):
        plot_fig_offset_mechanism()
    if args.only in ("C", "all"):
        plot_fig_l4_beta_n_heatmap()
    if args.only in ("D", "all"):
        plot_fig_l5_heatmap()
    if args.only in ("B", "all"):
        plot_fig_l2_n_heterogeneity()

    print("\n" + "=" * 60)
    print("Done. Output:", FIG_DIR)
    print("=" * 60)
