from __future__ import annotations

import importlib
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
from matplotlib.text import Text
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / 'scripts/documents'))
from panel_labels import normalize_panel_labels
STUDY = ROOT / r"Study\02-study-NN参数估计与分位点目标研究"
TOOLS = STUDY / "manuscript" / "tools"
OUT = STUDY / "manuscript" / "figures" / "word"
INTERMEDIATE = OUT / "derived"
WORD_WIDTH_IN = 17.49 / 2.54
MAIN_PT = 10.5

sys.path.insert(0, str(TOOLS))
base = importlib.import_module("figures_v260")
v270 = importlib.import_module("figures_v270")

SIZES = {
    # Keep the full four-panel figure and caption on one Word page.  The
    # physical text size stays 10.5 pt; only panel height and inter-row space
    # are reduced from the earlier 20.58 cm canvas.
    "fig2_parameter_compensation": (WORD_WIDTH_IN, 18.5 / 2.54),
    "fig3_cross_life_performance": (WORD_WIDTH_IN, 4.15),
    "fig4_cell_heterogeneity": (WORD_WIDTH_IN, 4.25),
    "figB1_common_budget_results": (WORD_WIDTH_IN, 3.8),
    "figB2_sample_size_equivalence": (WORD_WIDTH_IN, 3.8),
    "figB3_extended_reliability": (WORD_WIDTH_IN, 3.9),
    "figB4_regional_gains": (WORD_WIDTH_IN, 7.0),
    "figC1_target_sensitivity_mechanism": (WORD_WIDTH_IN, 7.1),
    "figD1_error_distribution": (WORD_WIDTH_IN, 7.6),
}


def style_text(fig):
    for item in fig.findobj(Text):
        if "x_{0.95}" in item.get_text() and "局部放大" in item.get_text():
            item.set_text("局部放大")
        if "$" not in item.get_text():
            item.set_fontfamily(["Times New Roman", "SimSun"])
        item.set_fontsize(MAIN_PT)
        item.set_fontweight("normal")
        item.set_fontstyle("normal")


def arrange_historical(fig, name):
    axes = [ax for ax in fig.axes if ax.get_visible()]
    if name == "figC1_target_sensitivity_mechanism" and len(axes) >= 3:
        fig.set_layout_engine(None)
        boxes = [(0.14, 0.72, 0.80, 0.20), (0.14, 0.42, 0.80, 0.19), (0.14, 0.07, 0.80, 0.20)]
        for ax, box in zip(axes[:3], boxes):
            ax.set_position(box)
        for ax in axes[3:]:
            ax.set_visible(False)
    elif name == "figD1_error_distribution" and len(axes) >= 4:
        fig.set_layout_engine(None)
        boxes = [(0.12, 0.57, 0.35, 0.33), (0.60, 0.57, 0.35, 0.33),
                 (0.12, 0.10, 0.35, 0.33), (0.60, 0.10, 0.35, 0.33)]
        for ax, box in zip(axes[:4], boxes):
            ax.set_position(box)


def tune_figure(fig, name):
    fig.set_size_inches(*SIZES[name], forward=True)
    style_text(fig)
    if name.startswith("figC") or name.startswith("figD"):
        arrange_historical(fig, name)
    else:
        try:
            fig.set_layout_engine("constrained", w_pad=0.08, h_pad=0.10, wspace=0.10, hspace=0.12)
        except Exception:
            pass
    if name == "fig2_parameter_compensation":
        # One label object gives Matplotlib one baseline and one bounding box;
        # the CJK face handles prose while custom mathtext supplies the TNR
        # symbols and true subscripts.
        def all_titles(ax):
            return " ".join(ax.get_title(loc=loc) for loc in ("left", "center", "right"))
        parameter_axes = [ax for ax in fig.axes
                          if all_titles(ax).strip().startswith(("A  同一寿命点", "B  参数约束"))]
        for ax in parameter_axes:
            ax.set_xlabel(r"形状相对误差 $u_\beta$", labelpad=8,
                          fontfamily="SimSun", fontsize=MAIN_PT)
            ax.set_ylabel(r"尺度相对误差 $u_\eta$", labelpad=8,
                          fontfamily="SimSun", fontsize=MAIN_PT)
        constraint_ax = next((ax for ax in fig.axes
                              if all_titles(ax).strip().startswith("B  实际 QCP")), None)
        if constraint_ax is not None:
            ax = constraint_ax
            ax.set_xlabel(r"$L_P/\tau_j$", labelpad=27)
            ax.text(0.5, -0.105, "验证集平均", transform=ax.transAxes,
                    ha="center", va="top", fontfamily="SimSun", fontsize=MAIN_PT)
        # Move legends inside free corners and give the lower-right inset its own readable area.
        for ax in fig.axes[:4]:
            legend = ax.get_legend()
            if legend is not None:
                legend.set_bbox_to_anchor(None)
                legend.set_loc("best")
        if len(fig.axes) > 4:
            inset = fig.axes[-1]
            inset.set_position([0.70, 0.22, 0.22, 0.15])
        constraint_ax = next((ax for ax in fig.axes
                              if all_titles(ax).strip().startswith("B  实际 QCP")), None)
        if constraint_ax is not None and constraint_ax.get_legend() is not None:
            constraint_ax.get_legend().set_loc("center left")
            constraint_ax.get_legend().set_bbox_to_anchor((0.02, 0.40))
        d_ax = next((ax for ax in fig.axes
                     if all_titles(ax).strip().startswith("D  同一预测")), None)
        if d_ax is not None and d_ax.child_axes:
            if d_ax.get_legend() is not None:
                d_ax.get_legend().set_loc("lower right")
                d_ax.get_legend().set_bbox_to_anchor((.98, .01))
            for item in d_ax.texts:
                if item.get_text() == "n=20":
                    item.set_transform(d_ax.transAxes)
                    item.set_position((.98, .40))
                    item.set_ha("right")
            for child in d_ax.child_axes:
                child.set_title("")
                child.text(.03, .95, "P/QCP 局部等比例", transform=child.transAxes,
                           ha="left", va="top", fontfamily="SimSun",
                           bbox={"facecolor": "white", "edgecolor": "none", "alpha": .8, "pad": 1})
    if name == "fig3_cross_life_performance" and len(fig.axes) > 2:
        inset = next((child for parent in fig.axes for child in parent.child_axes
                      if child.get_title() == "局部放大"), None)
        if inset is None:
            inset = fig.axes[-1]
            parent = fig.axes[1]
        else:
            parent = next(p for p in fig.axes if inset in p.child_axes)
        inset.set_axes_locator(None)
        pb = parent.get_position()
        inset.set_position([pb.x0 + .42 * pb.width, pb.y0 + .68 * pb.height,
                            .38 * pb.width, .23 * pb.height])
        inset.set_title("局部放大", fontfamily="SimSun", fontsize=MAIN_PT, pad=18)
        inset.text(0.5, 1.12, r"$x_{0.95}$", transform=inset.transAxes,
                   ha="center", va="bottom", fontsize=MAIN_PT, clip_on=False)
        inset.set_xticks(range(3), ["Q/P", "QCP/\nQ", "QCP/\nP"])
    if name == "figB4_regional_gains":
        for ax in fig.axes[:4]:
            ax.set_xlabel("形状参数 β")
            ax.set_ylabel("位置比 γ/η")
    if name == "figC1_target_sensitivity_mechanism" and len(fig.axes) >= 3:
        # Re-typeset the two gradient rules; the historical figure combined
        # Chinese and math in a single mathtext string, which loses glyphs.
        top = fig.axes[0]
        for item in list(top.texts):
            item.set_visible(False)
        top.text(0.03, 0.78, "P", transform=top.transAxes, color="#666666",
                 va="center", fontfamily="Times New Roman", fontsize=MAIN_PT)
        top.text(0.09, 0.78, r"$\nabla_u L_P=2u$", transform=top.transAxes,
                 va="center", fontsize=MAIN_PT)
        top.text(0.09, 0.64, "固定的归一化参数损失", transform=top.transAxes,
                 va="center", fontfamily="SimSun", fontsize=MAIN_PT)
        top.text(0.03, 0.32, "Q", transform=top.transAxes, color="#0072B2",
                 va="center", fontfamily="Times New Roman", fontsize=MAIN_PT)
        top.text(0.09, 0.32, r"$\nabla_u L_Q=2e(u)\nabla_u e(u)$", transform=top.transAxes,
                 va="center", fontsize=MAIN_PT)
        top.text(0.09, 0.18, "目标敏感度随预测参数改变", transform=top.transAxes,
                 va="center", fontfamily="SimSun", fontsize=MAIN_PT)
        fig.axes[1].set_ylabel("目标点 RMSRE（24模型单元等权）")
        fig.axes[1].set_ylim(top=0.23)
        fig.axes[2].set_ylabel("M95−P 的目标点相对均方误差")
        fig.axes[2].set_ylim(top=0.027)
    if name == "figD1_error_distribution" and len(fig.axes) >= 4:
        fig.axes[3].set_ylabel("Q−P 的配对 MSE 贡献差（×10⁻³）")
    for ax in fig.axes:
        ax.tick_params(labelsize=MAIN_PT)
        legend = ax.get_legend()
        if legend is not None:
            for text in legend.get_texts():
                text.set_fontsize(MAIN_PT)
                text.set_fontweight("normal")
                text.set_fontstyle("normal")


def save_candidate(fig, name, appendix=False):
    tune_figure(fig, name)
    normalize_panel_labels(fig)
    folder = OUT / ("appendix" if appendix else "main")
    folder.mkdir(parents=True, exist_ok=True)
    fig.canvas.draw()
    for ext in ("svg", "png"):
        fig.savefig(folder / f"{name}.{ext}", dpi=600, facecolor="white", bbox_inches=None)
    plt.close(fig)


def draw_performance(summary):
    fig, axs = plt.subplots(1, 2, figsize=SIZES["fig3_cross_life_performance"],
                            constrained_layout=True)
    levels = (.90, .95, .99)
    for i, route in enumerate(base.COL):
        vals = [summary["pooled_metrics"][f"{r:.2f}"][route]["rmsre"] * 100
                for r in levels]
        axs[0].scatter(np.arange(3) + (i - 1) * .12, vals,
                       marker=base.MARK[route], s=45, color=base.COL[route], label=route)
    axs[0].set_xticks(range(3), [r"$x_{0.90}$", r"$x_{0.95}$", r"$x_{0.99}$"])
    axs[0].set(xlabel="评估寿命点", ylabel="总体 RMSRE（%）",
               title="A  三个预设寿命点的误差", ylim=(0, 40))
    axs[0].legend(frameon=False, ncol=3)
    specs = [("Q_vs_P", base.COL["Q"], "^", "Q 相对 P"),
             ("QCP_vs_Q", base.COL["QCP"], "s", "QCP 相对 Q"),
             ("QCP_vs_P", "#D55E00", "o", "QCP 相对 P")]
    for i, (key, color, marker, label) in enumerate(specs):
        rows = [summary["pairwise_comparisons"][f"x_{r:.2f}"][key] for r in levels]
        effects = np.array([row["relative_rmsre_improvement"] for row in rows]) * 100
        ci = np.array([row["relative_rmsre_improvement_95ci"] for row in rows]) * 100
        axs[1].errorbar(np.arange(3) + (i - 1) * .15, effects,
                        yerr=[effects - ci[:, 0], ci[:, 1] - effects], fmt=marker,
                        markersize=4, color=color, capsize=4, elinewidth=1.2, label=label)
    axs[1].axhline(0, color="#888888", ls="--", lw=.8)
    axs[1].set_xticks(range(3), [r"$x_{0.90}$", r"$x_{0.95}$", r"$x_{0.99}$"])
    axs[1].set(ylabel="RMSRE 相对改善（%）", title="B  配对比较及 95% 区间")
    axs[1].legend(frameon=False, loc="lower center")
    inset = axs[1].inset_axes([.38, .67, .48, .26])
    for i, (key, color, marker, _) in enumerate(specs):
        row = summary["pairwise_comparisons"]["x_0.95"][key]
        value = 100 * row["relative_rmsre_improvement"]
        ci = np.array(row["relative_rmsre_improvement_95ci"]) * 100
        inset.errorbar([i], [value], yerr=[[value-ci[0]], [ci[1]-value]],
                       fmt=marker, color=color, capsize=3, markersize=4)
    inset.set_ylim(0, 5)
    inset.set_xlim(-.3, 2.3)
    inset.set_xticks([])
    for x, label in enumerate(("Q/P", "QCP/Q", "QCP/P")):
        inset.text(x, .10, label, ha="center", va="bottom", fontfamily="Times New Roman")
    inset.text(.03, .96, r"$x_{0.95}$", transform=inset.transAxes, ha="left", va="top")
    inset.text(.58, .96, "局部放大", transform=inset.transAxes, ha="center", va="top",
               fontfamily="SimSun")
    for ax in axs:
        ax.grid(axis="y", alpha=.15)
    save_candidate(fig, "fig3_cross_life_performance")


def draw_framework():
    fig, ax = plt.subplots(figsize=(WORD_WIDTH_IN, 7.45))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def box(x, y, w, h, text, edge="#666666", fill="#F7F7F7"):
        patch = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.012",
                               edgecolor=edge, facecolor=fill, linewidth=1.2)
        ax.add_patch(patch)
        ax.text(x + w / 2, y + h / 2, text, ha="center", va="center")

    def arrow(x1, y1, x2, y2, color="#666666"):
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1),
                    arrowprops={"arrowstyle": "->", "color": color, "lw": 1.2})

    ax.text(0.02, 0.990, "a  三参数输出神经网络与寿命点计算", va="top")
    box(0.025, 0.815, 0.15, 0.10, "")
    ax.text(0.10, 0.880, "排序寿命样本", ha="center", va="center")
    ax.text(0.10, 0.845, r"$x_{(1)},\ldots,x_{(n)}$", ha="center", va="center")
    # Explicit neurons preserve the meaning described in the caption.
    layer_x = [0.245, 0.335, 0.425, 0.515]
    layer_n = [5, 4, 4, 3]
    centers = []
    for li, (x, count) in enumerate(zip(layer_x, layer_n)):
        ys = np.linspace(0.825, 0.895, count)
        centers.append([(x, y) for y in ys])
        for x0, y0 in centers[-1]:
            ax.add_patch(plt.Circle((x0, y0), 0.008, facecolor="white", edgecolor="#657785", lw=0.8))
        if li:
            for x0, y0 in centers[li - 1]:
                for x1, y1 in centers[li]:
                    ax.plot([x0 + 0.008, x1 - 0.008], [y0, y1], color="#C8D0D5", lw=0.35, zorder=0)
    ax.text(0.38, 0.925, r"$n$–256–128–64–3", ha="center")
    ax.text(0.38, 0.790, "全连接隐藏层  ReLU", ha="center")
    arrow(0.175, 0.865, 0.235, 0.865)
    box(0.54, 0.790, 0.245, 0.150, "")
    ax.text(0.6625, 0.925, "参数解码", ha="center", va="top")
    ax.text(0.6625, 0.875, r"$\hat\beta=0.1+\mathrm{softplus}(o_1)$", ha="center")
    ax.text(0.6625, 0.835, r"$\hat\eta=\mathrm{softplus}(o_2)$", ha="center")
    ax.text(0.6625, 0.800, r"$\hat\gamma=\min(X)\,s(o_3)$", ha="center")
    box(0.805, 0.805, 0.18, 0.125, "")
    ax.text(0.895, 0.915, "寿命点", ha="center", va="top")
    ax.text(0.895, 0.865, r"$\hat x_R=\hat\gamma+$", ha="center")
    ax.text(0.895, 0.825, r"$\hat\eta(-\ln R)^{1/\hat\beta}$", ha="center")
    arrow(0.525, 0.865, 0.54, 0.865); arrow(0.785, 0.865, 0.805, 0.865)
    ax.text(0.6625, 0.755, r"$s$", ha="right")
    ax.text(0.6675, 0.755, "为保留边界余量的 sigmoid", ha="left")

    ax.text(0.02, 0.755, "b  P、Q 与 QCP 的监督路径", va="top")
    rows = [
        (0.565, "P", "逐参数误差", r"$L_P=\mathrm{mean}\!\left[\sum u^2\right]$", "验证集最低", r"$L_P$", "#777777"),
        (0.380, "Q", "目标寿命点误差", r"$L_Q=\mathrm{mean}\!\left[((\hat x_{0.95}-x_{0.95})/x_{0.95})^2\right]$", "验证集最低", r"$L_Q$", "#0072B2"),
        (0.220, "QCP", "目标误差与参数约束", r"$L_{AL,b}=L_{Q,b}+\Psi(L_{P,b}-\tau)$", "可行点中最低", r"$L_Q$", "#178064"),
    ]
    for y, route, target, train, select, select_math, color in rows:
        ax.text(0.025, y + 0.065, route, color=color, ha="left", va="center")
        box(0.105, y, 0.22, 0.13, "", edge=color, fill="white")
        if route == "QCP":
            target = "目标误差与\n参数约束"
        ax.text(0.215, y + 0.085, target, ha="center", va="center")
        target_math = (r"$L_P$" if route == "P" else
                       (r"$L_Q$" if route == "Q" else r"$L_Q,\ L_P\leq1.5L_{P,\mathrm{ref}}$"))
        ax.text(0.215, y + 0.045, target_math, ha="center", va="center")
        box(0.37, y, 0.37, 0.13, train, edge=color, fill="white")
        box(0.79, y, 0.19, 0.13, "", edge=color, fill="white")
        ax.text(0.885, y + 0.085, select, ha="center", va="center")
        ax.text(0.885, y + 0.045, select_math, ha="center", va="center")
        arrow(0.325, y + 0.065, 0.37, y + 0.065, color)
        arrow(0.74, y + 0.065, 0.79, y + 0.065, color)
        ax.annotate("反向传播", xy=(0.105, y + 0.025), xytext=(0.72, y + 0.025),
                    ha="right", color=color,
                    arrowprops={"arrowstyle": "->", "color": color,
                                "lw": 0.8, "linestyle": "--"})
        if route == "QCP":
            ax.text(0.555, y + 0.105, "Ψ 仅惩罚参数约束违反",
                    ha="center", color=color, fontfamily=["Times New Roman", "SimSun"])
    ax.text(0.02, 0.198, "c  验证检查点选择（示意）", va="top")
    ax.text(0.50, 0.140, "相同数据划分、网络结构和训练预算；分别训练并配对评价", ha="center")

    # Restore the three checkpoint-selection sketches carried by the original
    # figure.  The open green circle is the QCP-selected feasible checkpoint.
    def mini_axes(x0, x1, color, ylabel):
        y0, y1 = 0.006, 0.062
        ax.plot([x0, x0, x1], [y1, y0, y0], color="#7A858C", lw=.7)
        ax.text(x0 - .012, (y0 + y1) / 2, ylabel, rotation=90,
                ha="center", va="center", color=color)
        return y0, y1

    ax.text(0.18, 0.100, "P", ha="center", color="#777777")
    y0, y1 = mini_axes(.055, .305, "#777777", r"$L_P$")
    xp = np.linspace(.075, .285, 7)
    yp = np.array([.088, .070, .050, .038, .031, .041, .047])
    ax.plot(xp, yp, color="#777777", lw=1.1)
    ax.scatter([xp[4]], [yp[4]], s=20, color="#777777", zorder=4)
    ax.text(.18, .076, "验证集最低", ha="center", color="#777777")

    ax.text(0.50, 0.100, "Q", ha="center", color="#0072B2")
    y0, y1 = mini_axes(.375, .625, "#0072B2", r"$L_Q$")
    xq = np.linspace(.395, .605, 7)
    yq = np.array([.091, .070, .046, .052, .038, .049, .060])
    ax.plot(xq, yq, color="#0072B2", lw=1.1)
    ax.scatter([xq[4]], [yq[4]], s=20, color="#0072B2", zorder=4)
    ax.text(.50, .076, "验证集最低", ha="center", color="#0072B2")

    ax.text(0.82, 0.100, "QCP", ha="center", color="#178064")
    y0, y1 = mini_axes(.695, .945, "#178064", r"$L_Q$")
    threshold = .855
    ax.plot([threshold, threshold], [y0, y1], color="#AAB4BA", lw=.8, ls="--")
    ax.text(threshold, y0 - .004, "1", ha="center", va="top", color="#4F5A60")
    ax.text(.907, y0 - .004, r"$L_P/\tau$", ha="center", va="top", color="#4F5A60")
    feasible_x = np.array([.715, .750, .790, .830])
    feasible_y = np.array([.076, .061, .047, .032])
    ax.scatter(feasible_x, feasible_y, s=15, color="#178064", zorder=4)
    ax.scatter([.830], [.032], s=66, facecolors="white", edgecolors="#178064",
               linewidths=1.0, zorder=5)
    ax.scatter([.885, .915], [.025, .035], s=15, color="#B8C2C7", zorder=3)
    ax.text(.735, .076, "可行", ha="center", color="#178064")
    ax.text(.900, .076, "○ 选中", ha="center", color="#178064")
    style_text(fig)
    normalize_panel_labels(fig)
    folder = OUT / "main"; folder.mkdir(parents=True, exist_ok=True)
    for ext in ("svg", "png"):
        fig.savefig(folder / f"fig1_research_design.{ext}", dpi=600, facecolor="white", bbox_inches=None)
    plt.close(fig)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    INTERMEDIATE.mkdir(parents=True, exist_ok=True)
    base.OUT = INTERMEDIATE
    v270.OUT = INTERMEDIATE
    v270.save = save_candidate
    plt.rcParams.update({
        "font.family": ["Times New Roman", "SimSun"],
        "font.size": MAIN_PT,
        "font.weight": "normal",
        "font.style": "normal",
        "axes.titleweight": "normal",
        "axes.labelweight": "normal",
        "mathtext.default": "regular",
        "mathtext.fontset": "custom",
        "mathtext.rm": "Times New Roman",
        "mathtext.it": "Times New Roman:italic",
        "mathtext.bf": "Times New Roman:bold",
        "axes.unicode_minus": False,
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })
    draw_framework()
    summary = v270.read("artifacts/qcp_cross_quantile_recovery/analysis/summary.json")
    cells = pd.read_csv(base.source(STUDY / "artifacts/qcp_cross_quantile_recovery/analysis/truth_cell_effects.csv"))
    blocks, models, _ = base.contribution_data()
    v270.mechanism(blocks, models)
    draw_performance(summary)
    v270.heterogeneity(cells)
    v270.appendix(summary)
    v270.historical()
    rows = []
    for folder, doc in [("main", "Study02论文正文.docx"), ("appendix", "Study02论文附录.docx")]:
        for i, png in enumerate(sorted((OUT / folder).glob("*.png")), 1):
            svg = png.with_suffix(".svg")
            rows.append({"stem": png.stem, "png": str(png), "svg": str(svg),
                         "width_mm": 174.9, "font_pt": 10.5,
                         "output_png_sha256": hashlib.sha256(png.read_bytes()).hexdigest(),
                         "output_svg_sha256": hashlib.sha256(svg.read_bytes()).hexdigest(),
                         "source_identity": {"document": doc, "image_index": i,
                         "source_svg": str(STUDY / "manuscript" / "figures" / folder / svg.name)}})
    (OUT / "assembly-manifest.json").write_text(json.dumps({"count": len(rows), "figures": rows}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"main": sorted(p.name for p in (OUT / "main").glob("*.svg")),
                      "appendix": sorted(p.name for p in (OUT / "appendix").glob("*.svg"))}, ensure_ascii=False))


if __name__ == "__main__":
    main()
