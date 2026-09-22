"""Recompute the MDM principle figure from equations, not from image tracing.

Run: python F01_MDM原理联图.py
Requires: numpy, matplotlib. All paths are relative to this script.

Sources: Xie et al., IJSSD 23 (2023), 2350085, and Xie et al.,
Journal of Northeastern University 46 (2025), 108–112.
The ideal rank-quantile sample is an algebraic illustration, not a Monte Carlo run.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import numpy as np


ROOT = Path(__file__).resolve().parents[1]
STEM = "F01_MDM原理联图"
N = 7
BETA, ETA, GAMMA = 2.0, 1000.0, 1000.0
GAMMA_LEVELS = (600.0, 800.0, 1000.0, 1200.0)
COLORS = ("#9B765A", "#73998D", "#2F6791", "#9B88AE")
MARKERS = ("s", "^", "o", "D")


def calculate():
    order = np.arange(1, N + 1)
    ranks = (order - 0.3) / (N + 0.4)
    sample = GAMMA + ETA * (-np.log1p(-ranks)) ** (1.0 / BETA)
    # Discrete searches keep the illustration aligned with the paper's beta_k,
    # gamma_j formulation. The true pair is explicitly included in both grids.
    beta_grid = np.round(np.arange(0.6, 6.0001, 0.005), 3)
    gamma_grid = np.arange(400.0, 1250.0001, 2.0)
    assert np.all(gamma_grid < sample.min())
    denominator = (-np.log1p(-ranks))[None, :] ** (1.0 / beta_grid[:, None])
    pseudo = (sample[None, None, :] - gamma_grid[:, None, None]) / denominator[None, :, :]
    sigma = np.std(pseudo, axis=2, ddof=1)
    beta_index = np.argmin(sigma, axis=1)
    profile = sigma[np.arange(len(gamma_grid)), beta_index]
    best_j = int(np.argmin(profile))
    best_k = int(beta_index[best_j])
    estimates = (beta_grid[best_k], pseudo[best_j, best_k].mean(), gamma_grid[best_j])
    np.testing.assert_allclose(estimates, [BETA, ETA, GAMMA], atol=1e-9)
    assert profile[best_j] < 1e-9
    rows = []
    # Each panel's x/y values are retained exactly as plotted, including minima.
    trials = ((BETA, GAMMA), (BETA, 800.0), (3.0, GAMMA))
    for beta, gamma in trials:
        etas = (sample - gamma) / (-np.log1p(-ranks)) ** (1.0 / beta)
        for i, value in zip(order, etas):
            rows.append(("a", f"beta={beta:g};gamma={gamma:g}", "curve", int(i), value, beta, gamma))
    for gamma in GAMMA_LEVELS:
        j = int(np.flatnonzero(gamma_grid == gamma)[0])
        for k, beta in enumerate(beta_grid):
            if 1.0 <= beta <= 5.0:
                rows.append(("b", f"gamma={gamma:g}", "curve", beta, sigma[j, k], beta, gamma))
        k = beta_index[j]
        rows.append(("b", f"gamma={gamma:g}", "minimum", beta_grid[k], profile[j], beta_grid[k], gamma))
        rows.append(("c", f"gamma={gamma:g}", "conditional_minimum", gamma, profile[j], beta_grid[k], gamma))
    for j, gamma in enumerate(gamma_grid):
        rows.append(("c", "profile", "curve", gamma, profile[j], beta_grid[beta_index[j]], gamma))
    rows.append(("c", "selected_pair", "minimum", estimates[2], profile[best_j], estimates[0], estimates[2]))
    return order, ranks, sample, beta_grid, gamma_grid, sigma, profile, beta_index, estimates, rows


def style():
    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next((n for n in ("Microsoft YaHei", "Noto Sans CJK SC", "SimHei") if n in available), None)
    if font is None:
        raise RuntimeError("A Chinese font is required: Microsoft YaHei, Noto Sans CJK SC, or SimHei.")
    plt.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": [font, "DejaVu Sans"],
        "font.size": 7.2, "axes.titlesize": 8.5, "axes.labelsize": 7.5,
        "xtick.labelsize": 6.7, "ytick.labelsize": 6.7,
        "legend.fontsize": 6.3, "legend.frameon": False,
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.linewidth": 0.65, "xtick.major.width": 0.65, "ytick.major.width": 0.65,
        "lines.linewidth": 1.5, "mathtext.fontset": "dejavusans",
        "svg.fonttype": "none", "pdf.fonttype": 42,
        "axes.unicode_minus": False, "savefig.facecolor": "white",
    })
    return font


def draw(values):
    order, ranks, sample, betas, gammas, sigma, profile, beta_index, estimates, _ = values
    fig, axes = plt.subplots(1, 3, figsize=(183 / 25.4, 86 / 25.4))
    fig.subplots_adjust(left=0.078, right=0.988, bottom=0.22, top=0.72, wspace=0.39)
    fig.text(0.078, 0.952, "MDM：由伪尺度差异确定三参数", fontsize=11, fontweight="bold", color="#263746")
    fig.text(0.078, 0.874, r"理想秩分位点样本  $W(2,1000,1000)$，$n=7$", fontsize=7.4, color="#64727E")
    titles = ["样本点给出伪尺度", "固定位置，搜索形状", "比较条件最小差异"]
    for label, title, ax in zip("abc", titles, axes):
        ax.text(0.0, 1.13, label, transform=ax.transAxes, fontweight="bold", fontsize=10, color="#263746")
        ax.text(0.105, 1.13, title, transform=ax.transAxes, fontsize=8, color="#263746")
        ax.grid(axis="y", color="#E6EBEF", linewidth=0.5, zorder=0)

    ax = axes[0]
    for beta, gamma, color, marker, ls in (
        (2.0, 1000.0, COLORS[2], "o", "-"),
        (2.0, 800.0, COLORS[1], "^", "--"),
        (3.0, 1000.0, COLORS[3], "s", "-."),
    ):
        eta_i = (sample - gamma) / (-np.log1p(-ranks)) ** (1.0 / beta)
        ax.plot(order, eta_i, color=color, marker=marker, markersize=3.8,
                linestyle=ls, label=rf"$\beta={beta:g},\;\gamma={gamma:g}$", zorder=3)
    ax.set(xlabel=r"样本序号 $i$", ylabel=r"伪尺度参数 $\hat{\eta}_i$", xlim=(0.8, 7.2), ylim=(580, 1820))
    ax.set_xticks([1, 2, 3, 4, 5, 6, 7])
    ax.set_yticks([600, 1000, 1400, 1800])
    ax.legend(loc="upper right", handlelength=2.1, labelspacing=0.35)
    ax.annotate(r"$\hat{\eta}_i=\eta=1000$", xy=(4.3, 1000), xytext=(2.5, 780),
                fontsize=7, color=COLORS[2], arrowprops={"arrowstyle": "-", "color": COLORS[2], "lw": 0.7})

    ax = axes[1]
    for gamma, color, marker, ls in zip(GAMMA_LEVELS, COLORS, MARKERS, ("--", "-.", "-", ":")):
        j = int(np.flatnonzero(gammas == gamma)[0])
        ax.plot(betas, sigma[j], color=color, linestyle=ls, label=rf"$\gamma_j={gamma:g}$")
        k = beta_index[j]
        ax.scatter(betas[k], profile[j], color=color, marker=marker, s=24, edgecolor="white", linewidth=0.5, zorder=4)
    ax.set(xlabel=r"形状参数 $\beta_k$", ylabel=r"伪尺度标准差 $\sigma_\eta(\gamma_j,\beta_k)$",
           xlim=(1, 5), ylim=(-20, 600), xticks=[1, 2, 3, 4, 5], yticks=[0, 200, 400, 600])
    ax.legend(loc="upper right", labelspacing=0.35, handlelength=2.3)

    ax = axes[2]
    ax.plot(gammas, profile, color="#56636E", linewidth=1.6, zorder=2)
    for gamma, color, marker in zip(GAMMA_LEVELS, COLORS, MARKERS):
        j = int(np.flatnonzero(gammas == gamma)[0])
        ax.scatter(gamma, profile[j], color=color, marker=marker, s=29, edgecolor="white", linewidth=0.55, zorder=4)
    ax.axvline(GAMMA, color=COLORS[2], linestyle="--", linewidth=0.85, alpha=0.8)
    ax.annotate(r"$\hat{\gamma}=1000,\;\hat{\beta}=2$", xy=(GAMMA, 0), xytext=(470, 102),
                fontsize=7, color=COLORS[2], arrowprops={"arrowstyle": "->", "color": COLORS[2], "lw": 0.8})
    ax.set(xlabel=r"位置参数 $\gamma_j$", ylabel=r"条件最小标准差 $\sigma_{\eta,\min}(\gamma_j)$",
           xlim=(400, 1280), ylim=(-2, max(profile) * 1.13), xticks=[400, 600, 800, 1000, 1200])
    fig.text(0.078, 0.066, r"选出 $(\hat{\beta},\hat{\gamma})$ 后，取伪尺度均值："
             r"$\hat{\eta}=\frac{1}{n}\sum_{i=1}^{n}\hat{\eta}_i(\hat{\gamma},\hat{\beta})$",
             fontsize=8.1, color="#263746")
    fig.text(0.988, 0.066, r"本例 $\hat{\eta}=1000$", ha="right", fontsize=8.1, color=COLORS[2])
    fig.canvas.draw()
    renderer = fig.canvas.get_renderer()
    # Export QA: visible text must remain on the canvas.
    canvas = fig.bbox
    clipped = []
    for text in fig.findobj(matplotlib.text.Text):
        if text.get_visible() and text.get_text():
            bb = text.get_window_extent(renderer)
            if bb.x0 < canvas.x0 - 1 or bb.y0 < canvas.y0 - 1 or bb.x1 > canvas.x1 + 1 or bb.y1 > canvas.y1 + 1:
                clipped.append(text.get_text())
    assert not clipped, f"Text outside figure: {clipped}"
    for suffix in ("svg", "pdf", "png"):
        fig.savefig(ROOT / f"{STEM}.{suffix}", dpi=400)
    plt.close(fig)


def main():
    font = style()
    values = calculate()
    data = ROOT / "数据"
    data.mkdir(exist_ok=True)
    csv_path = data / f"{STEM}.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["panel", "series", "kind", "x", "y", "beta", "gamma"])
        writer.writerows(values[-1])
    draw(values)
    metadata = {
        "figure": "F01", "description": "MDM principle, recomputed from equations",
        "sources_doi": ["10.1142/S0219455423500852", "10.12068/j.issn.1005-3026.2025.20240194"],
        "source_relation": "2023 approximate median ranks; 2025 notation and gamma-first conditional search",
        "sample_type": "deterministic ideal rank quantiles; not random observations or a performance experiment",
        "true_parameters": {"beta": BETA, "eta": ETA, "gamma": GAMMA}, "n": N,
        "rank_formula": "(i-0.3)/(n+0.4)", "ranks": values[1].tolist(), "sample": values[2].tolist(),
        "beta_grid": {"start": 0.6, "stop": 6.0, "step": 0.005},
        "gamma_grid": {"start": 400.0, "stop": 1250.0, "step": 2.0},
        "std_ddof": 1, "estimates_beta_eta_gamma": list(values[8]),
        "checks": {"ideal_sample_recovers_parameters": True, "text_inside_canvas": True},
        "size_mm": [183, 86], "font": font, "numpy": np.__version__, "matplotlib": matplotlib.__version__,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "data_sha256": hashlib.sha256(csv_path.read_bytes()).hexdigest(),
    }
    (data / f"{STEM}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"figure": STEM, "estimates": metadata["estimates_beta_eta_gamma"], "rows": len(values[-1])}, ensure_ascii=False))


if __name__ == "__main__":
    main()
