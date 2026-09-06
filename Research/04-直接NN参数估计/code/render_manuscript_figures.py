"""Render Research04 v0.2 figures from frozen aggregate CSVs only.

Python/matplotlib quantitative grids, 180 mm width, 7.5 pt body text.
Adapted from the existing analyze_* plotting functions; no sampling, fitting,
metric recomputation or writes to artifacts. Run this file without arguments.
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.text import Text
import numpy as np
import pandas as pd
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "manuscript" / "figures-v0.2"
ART = ROOT / "artifacts"
BASE = "study01_aligned_generalization_v1/analysis/"
WIDTH = "training_domain_width_v1/analysis/"
CENTER = "training_domain_width_location_v1/analysis/"
METHODS = ["Direct-P", "Adaptive-MDM", "MDM-0.1"]
COLORS = dict(zip(METHODS, ["#0072B2", "#D55E00", "#009E73"]))
STYLES = dict(zip(METHODS, ["-", "--", ":"]))
MARKERS = dict(zip(METHODS, ["o", "s", "^"]))
LABELS = {"Direct-P": "Direct-P", "Adaptive-MDM": "自适应 MDM", "MDM-0.1": "固定 MDM-0.1"}
POLICIES = {"fixed_total": ("固定总量", "-", "o"), "fixed_density": ("固定密度", "--", "s")}
POLICY_COLORS = {"fixed_total": "#0072B2", "fixed_density": "#739db5"}
DOMAINS = ["narrow_2.0_3.0", "medium_1.5_3.5", "wide_1.5_5.0"]
SOURCES = {}
QA = {}

# Contract: each panel has a distinct evidential role; captions live in the manuscript.
CONTRACTS = {
    "fig1_domain_risk": "测试 beta 位置改变方法风险排序；A 点风险，B 条件于冻结模型的配对差及原有 95% CI。",
    "fig2_centered_width": "中心固定为 3 的训练域扩宽损失共同区间参数精度；A/B 双预算参数风险，C/D 各预算的三个寿命点，未提供 CI。",
    "fig3_parameter_rmse": "三参数标准化 RMSE 分解总体风险，位置误差明确以真实 eta 标准化。",
    "fig4_mdm_diagnostic": "参数偏差方向与寿命误差不同比例变化；A/B 为自适应 MDM 统计，C 为解析相对敏感度诊断，非因果识别。",
    "fig5_sample_size": "已见网格中样本量改变两类风险及配对差；C 使用原有条件 95% CI。",
    "figS1_n_by_beta": "共同纵轴比较四个样本量下的 beta 风险曲线。",
    "figS2_nested_tradeoff": "原嵌套训练域的共同区间参数与寿命风险权衡，保留原 CI；寿命面板局部纵轴。",
    "figS3_nested_extrapolation": "固定总量下三种原嵌套训练域的双侧外推风险；各行共用纵轴及相同 MDM 参照。",
    "figS4_input_geometry": "低 beta 下均值归一化输入的几何统计改变；中位数和四分位区间来自封存 CSV。",
}
FIGURE_SOURCES = {
    "fig1_domain_risk": [BASE+"beta_summary.csv", BASE+"paired_bootstrap_contrasts.csv"],
    "fig2_centered_width": [CENTER+"width_common_beta_summary.csv"],
    "fig3_parameter_rmse": [BASE+"beta_summary.csv"],
    "fig4_mdm_diagnostic": [BASE+"beta_summary.csv", BASE+"mdm_identifiability_sensitivity.csv"],
    "fig5_sample_size": [BASE+"n_domain_summary.csv", BASE+"paired_bootstrap_contrasts.csv"],
    "figS1_n_by_beta": [BASE+"n_beta_summary.csv"],
    "figS2_nested_tradeoff": [WIDTH+"common_core_bootstrap.csv"],
    "figS3_nested_extrapolation": [WIDTH+"beta_summary.csv", BASE+"beta_summary.csv"],
    "figS4_input_geometry": [BASE+"sample_geometry_summary.csv"],
}


def read(rel):
    path = ART / rel
    data = pd.read_csv(path)
    SOURCES[rel] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "rows": len(data)}
    return data


def setup():
    OUT.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["Microsoft YaHei", "DejaVu Sans"],
        "font.size": 7.5, "axes.labelsize": 7.5, "axes.titlesize": 8,
        "xtick.labelsize": 7, "ytick.labelsize": 7, "legend.fontsize": 7,
        "axes.unicode_minus": False, "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": .65, "lines.linewidth": 1.15, "lines.markersize": 3,
        "pdf.fonttype": 42, "ps.fonttype": 42, "svg.fonttype": "none", "savefig.dpi": 300,
    })


def grid(rows=1, cols=2, height=76, **kwargs):
    return plt.subplots(rows, cols, figsize=(180/25.4, height/25.4), layout="constrained", **kwargs)


def panel(ax, label, title, xlabel, ylabel):
    ax.set_title(f"{label}  {title}", loc="left", fontweight="bold", pad=7)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.grid(axis="y", color="#dddddd", linewidth=.45, zorder=0)


def domain(ax, low=1.5, high=5.0):
    ax.axvspan(low, high, color="#ededed", zorder=0)
    for x in [low, high]:
        ax.axvline(x, color="#aaaaaa", lw=.6, zorder=1)
    ax.set_xlim(.6, 5.9)
    ax.set_xticks([1, 2, 3, 4, 5])


def method_lines(ax, data, metric, x="beta", distinguish_seen=False):
    for method in METHODS:
        d = data[data.method.eq(method)].sort_values(x)
        ax.plot(d[x], d[metric], color=COLORS[method], ls=STYLES[method],
                marker=MARKERS[method], markerfacecolor="white" if distinguish_seen else COLORS[method],
                markeredgewidth=.7, label=LABELS[method])
        if distinguish_seen:
            seen = d[d.beta_group.eq("seen_grid")]
            ax.plot(seen[x], seen[metric], ls="none", color=COLORS[method], marker=MARKERS[method])


def legend(ax, **kwargs):
    ax.legend(**({"frameon": False, "handlelength": 2.4} | kwargs))


def save(fig, name):
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    bounds = fig.bbox
    outside = []
    # Matplotlib retains tick Text objects outside the view interval; these are
    # not rendered and must not be reported as clipped visible labels.
    unused_ticks = set()
    for ax in fig.axes:
        for axis in [ax.xaxis, ax.yaxis]:
            lo, hi = sorted(axis.get_view_interval())
            for tick in axis.get_major_ticks() + axis.get_minor_ticks():
                if not lo <= tick.get_loc() <= hi:
                    unused_ticks.update([tick.label1, tick.label2])
    for txt in fig.findobj(Text):
        if txt not in unused_ticks and txt.get_visible() and txt.get_text():
            bb = txt.get_window_extent(renderer)
            if bb.x0 < bounds.x0-1 or bb.y0 < bounds.y0-1 or bb.x1 > bounds.x1+1 or bb.y1 > bounds.y1+1:
                outside.append(txt.get_text())
    for ext in ("png", "pdf", "svg"):
        fig.savefig(OUT / f"{name}.{ext}", facecolor="white")
    pdf = PdfReader(OUT / f"{name}.pdf")
    fonts = []
    for font in pdf.pages[0]["/Resources"].get("/Font", {}).values():
        obj = font.get_object()
        desc = obj.get("/DescendantFonts", [])
        embedded = []
        for item in desc or [obj]:
            fd = item.get_object().get("/FontDescriptor")
            if fd:
                fd = fd.get_object()
                embedded.append(any(key in fd for key in ["/FontFile", "/FontFile2", "/FontFile3"]))
        fonts.append({"font": str(obj.get("/BaseFont")), "type": str(obj.get("/Subtype")), "embedded": all(embedded) if embedded else False})
    QA[name] = {"width_mm": round(float(pdf.pages[0].mediabox.width)*25.4/72, 2),
                "height_mm": round(float(pdf.pages[0].mediabox.height)*25.4/72, 2),
                "text_outside_canvas": outside, "fonts": fonts,
                "visual_review": "pending"}
    assert not outside, (name, outside)
    assert all(f["type"] != "/Type3" and f["embedded"] for f in fonts), (name, fonts)
    plt.close(fig)


def domain_risk(beta, ci):
    fig, axes = grid(height=84)
    method_lines(axes[0], beta, "J1", distinguish_seen=True)
    panel(axes[0], "A", "联合风险", r"真实形状参数 $\beta$", r"$J_1$")
    legend(axes[0], loc="upper right")
    extra = [Line2D([], [], color="#555555", marker="o", ls="none", label="训练点"),
             Line2D([], [], color="#555555", marker="o", mfc="white", ls="none", label=r"新增 $\beta$ 点")]
    axes[0].add_artist(axes[0].get_legend())
    axes[0].legend(handles=extra, loc="center", bbox_to_anchor=(.43, .70), frameon=False, fontsize=6.5)
    ax = axes[1]
    for offset, method in zip([-.025, .025], METHODS[1:]):
        d = ci[ci.scope.eq("beta") & ci.contrast.eq(f"Direct-P minus {method}")].copy()
        d["scope_value"] = pd.to_numeric(d.scope_value)
        d = d.sort_values("scope_value")
        y = d.delta_J1.to_numpy()
        ax.errorbar(d.scope_value+offset, y, yerr=[y-d.ci95_low, d.ci95_high-y],
                    color=COLORS[method], ls=STYLES[method], marker=MARKERS[method],
                    capsize=2, elinewidth=.8, label=f"Direct-P − {LABELS[method]}")
    panel(ax, "B", "配对风险差及 95% CI", r"真实形状参数 $\beta$", r"$\Delta J_1$")
    ax.axhline(0, color="#333333", lw=.8)
    legend(ax, loc="upper right", fontsize=6.5)
    for ax in axes:
        domain(ax)
    save(fig, "fig1_domain_risk")


def centered_width(data):
    fig, axes = grid(2, 2, height=122)
    fig.suptitle(r"Direct-P：共同评价区间 $\beta\in[2.5,3.5]$", fontsize=8.5)
    for index, metric in enumerate(["J1", "beta_rmse"]):
        ax = axes.flat[index]
        for policy, (label, style, marker) in POLICIES.items():
            d = data[data.budget_policy.eq(policy)].sort_values("train_beta_width")
            ax.plot(d.train_beta_width, d[metric], color=POLICY_COLORS[policy], ls=style, marker=marker,
                    mfc="white" if policy == "fixed_density" else COLORS["Direct-P"], label=label)
        panel(ax, chr(65+index), "共同区间参数精度" if index == 0 else "形状参数精度", "训练域宽度", r"$J_1$" if index == 0 else r"RMSE$[(\hat\beta-\beta)/\beta]$")
        ax.set_ylim(bottom=0)
        legend(ax, loc="upper left")
    for index, policy in enumerate(POLICIES):
        ax = axes[1, index]
        d = data[data.budget_policy.eq(policy)].sort_values("train_beta_width")
        for r, style, marker in zip(["0.90", "0.95", "0.99"], [":", "-", "--"], ["^", "o", "s"]):
            ax.plot(d.train_beta_width, d[f"x{r}_rmse"], color=COLORS["Direct-P"], ls=style,
                    marker=marker, label=fr"$x_{{{r}}}$")
        panel(ax, chr(67+index), POLICIES[policy][0]+"：寿命点精度", "训练域宽度", "寿命点相对 RMSE")
        ax.set_ylim(0, .30)
        legend(ax, loc="upper center", ncol=3, columnspacing=.8, handlelength=1.7)
    for ax in axes.flat:
        ax.set_xticks([1, 2, 4, 5])
    save(fig, "fig2_centered_width")


def parameter_rmse(beta):
    fig, axes = grid(cols=3, height=74)
    for i, (metric, symbol, denominator) in enumerate([("beta_rmse", "beta", "beta"), ("eta_rmse", "eta", "eta"), ("gamma_rmse", "gamma", "eta")]):
        ax = axes[i]
        method_lines(ax, beta, metric)
        domain(ax)
        panel(ax, chr(65+i), ["形状参数", "尺度参数", "位置参数"][i], r"真实 $\beta$", fr"RMSE$[(\hat\{symbol}-\{symbol})/\{denominator}]$")
        ax.set_ylim(bottom=0)
    legend(axes[0], loc="upper right", fontsize=6.5)
    save(fig, "fig3_parameter_rmse")


def mdm_diagnostic(beta, sensitivity):
    fig, axes = grid(cols=3, height=78)
    d = beta[beta.method.eq("Adaptive-MDM")].sort_values("beta")
    for field, label, style, marker in [("beta_bias", r"$e_\beta$", "-", "o"), ("eta_bias", r"$e_\eta$", "--", "s"), ("gamma_bias", r"$e_\gamma$", ":", "^")]:
        axes[0].plot(d.beta, d[field], color=COLORS["Adaptive-MDM"], ls=style, marker=marker, label=label)
    axes[0].axhline(0, color="#333333", lw=.7)
    panel(axes[0], "A", "自适应 MDM 参数偏差", r"真实 $\beta$", "标准化 Bias")
    legend(axes[0], ncol=3, loc="lower left", handlelength=1.5, columnspacing=.6)
    for field, label, style, marker in [("J1", r"$J_1$", "-", "s"), ("x0.95_rmse", r"$x_{0.95}$ 相对 RMSE", "--", "o")]:
        axes[1].plot(d.beta, d[field], color=COLORS["Adaptive-MDM"], ls=style, marker=marker, label=label)
    panel(axes[1], "B", "参数与寿命点误差", r"真实 $\beta$", "误差")
    legend(axes[1], loc="center right", fontsize=6.5)
    s = sensitivity[sensitivity.n.eq(sensitivity.n.min())].sort_values("beta")
    axes[2].plot(s.beta, s["relative_to_beta_1.5"], color="#666666", marker="o")
    panel(axes[2], "C", "对数伪尺度相对敏感度", r"真实 $\beta$", r"$S(\beta)/S(1.5)$")
    for ax in axes:
        ax.axvspan(4.5, 5.75, color="#f4edd0", zorder=0)
        ax.set_xlim(.6, 5.9)
        ax.set_xticks([1, 2, 3, 4, 5])
    save(fig, "fig4_mdm_diagnostic")


def sample_size(summary, ci):
    d = summary[summary.beta_group.eq("seen_grid")]
    fig, axes = grid(cols=3, height=76)
    for i, metric in enumerate(["J1", "x0.95_rmse"]):
        method_lines(axes[i], d, metric, "n")
        panel(axes[i], chr(65+i), ["参数联合风险", "寿命点精度"][i], r"样本量 $n$", r"$J_1$" if i == 0 else r"$x_{0.95}$ 相对 RMSE")
        axes[i].set_ylim(bottom=0)
    legend(axes[0], loc="upper right", fontsize=6.5)
    c = ci[ci.scope.eq("seen_grid_n") & ci.contrast.eq("Direct-P minus Adaptive-MDM")].copy()
    c["scope_value"] = pd.to_numeric(c.scope_value)
    c = c.sort_values("scope_value")
    y = c.delta_J1.to_numpy()
    axes[2].errorbar(c.scope_value, y, yerr=[y-c.ci95_low, c.ci95_high-y], color=COLORS["Adaptive-MDM"], marker="s", capsize=3)
    axes[2].axhline(0, color="#333333", lw=.7)
    panel(axes[2], "C", "Direct-P − 自适应 MDM", r"样本量 $n$", r"$\Delta J_1$（95% CI）")
    for ax in axes:
        ax.set_xticks(sorted(d.n.unique()))
    save(fig, "fig5_sample_size")


def n_by_beta(data):
    fig, axes = grid(2, 2, height=123, sharey=True)
    for i, n in enumerate(sorted(data.n.unique())):
        ax = axes.flat[i]
        method_lines(ax, data[data.n.eq(n)], "J1")
        domain(ax)
        panel(ax, chr(65+i), f"n = {n}", r"真实 $\beta$", r"$J_1$")
        ax.set_ylim(0, data.J1.max()*1.06)
    legend(axes[0, 0], loc="upper right")
    save(fig, "figS1_n_by_beta")


def nested_tradeoff(summary):
    fig, axes = grid(height=80)
    for index, metric in enumerate(["J1", "x0.95 RMSE"]):
        ax = axes[index]
        for offset, (policy, (label, style, marker)) in zip([-.04, .04], POLICIES.items()):
            d = summary[summary.metric.eq(metric) & summary.budget_policy.eq(policy)].set_index("domain_id").loc[DOMAINS]
            y = d.estimate.to_numpy()
            ax.errorbar(np.arange(3)+offset, y, yerr=[y-d.ci95_low, d.ci95_high-y], color=POLICY_COLORS[policy], ls=style, marker=marker,
                        mfc="white" if policy == "fixed_density" else COLORS["Direct-P"], capsize=3, label=label)
        panel(ax, chr(65+index), "共同区间参数精度" if index == 0 else "寿命点精度（局部纵轴）", r"训练 $\beta$ 区间", r"$J_1$" if index == 0 else r"$x_{0.95}$ 相对 RMSE")
        ax.set_xticks(range(3), ["[2, 3]", "[1.5, 3.5]", "[1.5, 5]"])
    axes[0].set_ylim(bottom=0)
    legend(axes[0], loc="lower right")
    save(fig, "figS2_nested_tradeoff")


def nested_extrapolation(data, base):
    fig, axes = grid(2, 3, height=122, sharey="row", sharex=True)
    for col, dom in enumerate(DOMAINS):
        d = data[data.budget_policy.eq("fixed_total") & data.domain_id.eq(dom)].sort_values("beta")
        low, high = d.train_beta_min.iloc[0], d.train_beta_max.iloc[0]
        for row, metric in enumerate(["J1", "x095_rmse"]):
            ax = axes[row, col]
            ax.plot(d.beta, d[metric], color=COLORS["Direct-P"], marker="o", label="Direct-P")
            base_metric = "J1" if row == 0 else "x0.95_rmse"
            for method in METHODS[1:]:
                b = base[base.method.eq(method)].sort_values("beta")
                ax.plot(b.beta, b[base_metric], color=COLORS[method], ls=STYLES[method], label=LABELS[method])
            domain(ax, low, high)
            panel(ax, chr(65+row*3+col), f"固定总量 [{low:g}, {high:g}]", r"真实 $\beta$" if row else "", (r"$J_1$" if row == 0 else r"$x_{0.95}$ 相对 RMSE") if col == 0 else "")
            ax.set_ylim(bottom=0)
    legend(axes[0, 0], loc="upper right", fontsize=6.5)
    save(fig, "figS3_nested_extrapolation")


def input_geometry(data):
    fig, axes = grid(height=76)
    d = data.sort_values("beta")
    for i, (field, label) in enumerate([("sample_cv", "样本变异系数"), ("max_over_mean", "最大值 / 样本均值")]):
        ax = axes[i]
        ax.fill_between(d.beta, d[f"{field}_q25"], d[f"{field}_q75"], color="#b6aed0", alpha=.45, label="四分位区间")
        ax.plot(d.beta, d[f"{field}_median"], color="#75658f", marker="o", label="中位数")
        domain(ax)
        panel(ax, chr(65+i), label, r"真实 $\beta$", label)
    legend(axes[0], loc="upper right")
    save(fig, "figS4_input_geometry")


def main():
    setup()
    beta = read(BASE+"beta_summary.csv")
    ci = read(BASE+"paired_bootstrap_contrasts.csv")
    centered = read(CENTER+"width_common_beta_summary.csv")
    domain_risk(beta, ci)
    centered_width(centered)
    parameter_rmse(beta)
    mdm_diagnostic(beta, read(BASE+"mdm_identifiability_sensitivity.csv"))
    sample_size(read(BASE+"n_domain_summary.csv"), ci)
    n_by_beta(read(BASE+"n_beta_summary.csv"))
    nested_tradeoff(read(WIDTH+"common_core_bootstrap.csv"))
    nested_extrapolation(read(WIDTH+"beta_summary.csv"), beta)
    input_geometry(read(BASE+"sample_geometry_summary.csv"))
    source_dir = OUT / "source-data"
    source_dir.mkdir(exist_ok=True)
    for rel, info in SOURCES.items():
        name = rel.replace("/analysis/", "__").replace("/", "__")
        shutil.copyfile(ART/rel, source_dir/name)
        info["copy"] = "source-data/"+name
    increases = {}
    for policy in POLICIES:
        d = centered[centered.budget_policy.eq(policy)].sort_values("train_beta_width")
        increases[policy] = (d.J1.iloc[-1]/d.J1.iloc[0]-1)*100
    manifest = {"backend": "Python/matplotlib", "archetype": "quantitative grid", "contracts": CONTRACTS,
                "figure_sources": FIGURE_SOURCES,
                "sources_relative_to_artifacts": SOURCES, "new_training": False, "new_monte_carlo": False,
                "new_confidence_intervals": False, "centered_width_J1_increase_percent": increases,
                "aggregation": "Frozen summaries unchanged: beta curves pool n and gamma/eta; n curves pool beta and gamma/eta; width contrasts use the common beta interval. No averaging of RMSEs.",
                "source_notes": "Joint risk includes failure penalty; parameter/lifetime RMSE uses valid estimates. CI is conditional on frozen fitted models. Geometry bands are IQR, not CI. See manuscript for design and formulas."}
    (OUT/"source-data-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT/"figure-qa.json").write_text(json.dumps(QA, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"figures": len(QA), "sources": len(SOURCES), "width_increase_percent": increases}, ensure_ascii=False))


if __name__ == "__main__":
    main()
