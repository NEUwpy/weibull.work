"""Split archived abnormalities before explaining their distinct processes.

Reproduce the existing classification/LSE figures, add likelihood and fixed-
location contrasts. All output is derived from archived samples/conditional
checks; no method run(), resampling, original-result or failure-state edits.
"""
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path
DATA_DIR = RESULT / "报告2" / "数据"
from pathlib import Path
import csv
import importlib.util
import json
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

HERE = Path(__file__).resolve().parent
IMAGES = RESULT / "报告2"


def module(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


helper = module(HERE/"逐方法机制复核.py", "split_helper")
BLUE, BROWN = "#487A8B", "#B67550"
plt.rcParams.update({"font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
    "font.size": 9, "axes.linewidth": .65, "axes.spines.top": False,
    "axes.spines.right": False, "legend.frameon": False,
    "axes.unicode_minus": False, "xtick.major.width": .65,
    "ytick.major.width": .65})


def source(combination, sources):
    entry = next(s for s in sources if s["combination"] == combination)
    base = PROGRAM/entry["program"]
    matrix = matrix_path(entry)
    return entry, base, matrix, json.loads(matrix.read_text(encoding="utf-8"))


def sample(data, n, group):
    return np.sort(np.asarray(next(s["values"] for s in data["samples"]
                                  if (s["n"], s["id"]) == (n, group)), float))


def write_csv(path, rows):
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=keys, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def identify(ax, letter):
    ax.text(-.15, 1.06, letter, transform=ax.transAxes,
            fontsize=11, fontweight="bold")


def layout(fig):
    fig.subplots_adjust(left=.08, right=.98, bottom=.13, top=.91,
                        wspace=.43, hspace=.47)


def references(fig):
    from matplotlib.lines import Line2D
    fig.legend(handles=[
        Line2D([0], [0], color="#707070", linestyle="--", linewidth=.7, label="真值"),
        Line2D([0], [0], marker="o", color="#555555", linestyle="none",
               markersize=4, label="条件解")],
        loc="lower center", ncol=2, bbox_to_anchor=(.53, 0.0), fontsize=8)


def fixed_figure():
    sources = json.loads((PROGRAM/"跨参数对比/13组合取数.json").read_text(encoding="utf-8"))["sources"]
    rows = list(csv.DictReader((DATA_DIR/"全量流程定位.csv").open(encoding="utf-8-sig")))
    curves, fixed_evidence = [], []
    # Fixed-location residual branch: match a control inside the same design.
    entry, base, path, data = source("W(5,1000,500)", sources)
    candidates = []
    for group in range(1, 51):
        rr = [r for r in rows if r["combination"] == entry["combination"] and r["n"] == "7"
              and int(r["group"]) == group and r["method"] in ("LSE", "LRE", "MLE")]
        if len(rr) == 3 and all(r["fixed_true_abnormal"] == "False" for r in rr):
            candidates.append(group)
    control = min(candidates, key=lambda i: (abs(i-29), i))
    assert control == 28
    snapshot = base/"依赖快照/python"
    sys.path.insert(0, str(snapshot))
    lse = helper.load_module(snapshot/"methods/lse.py", "conditional_frozen_lse")
    n = 7
    ranks = np.arange(1, n+1)
    p = (ranks-.3)/(n+.4)  # Protocol is historical-eight: frozen Bernard LRE.
    assert entry["protocol"] == "historical-eight"
    z_lse = lse.log_weibull_order_stat_means(n)
    z_lre = np.log(-np.log1p(-p))
    fig, axes = plt.subplots(2, 3, figsize=(9.1, 5.6))
    fixed_evidence = []
    for row, (group, color) in enumerate([(control, BLUE), (29, BROWN)]):
        x = sample(data, n, group)
        y = np.log(x-500)
        yc = y-y.mean()
        fits = {"LSE": helper.regression(x, 500., z_lse, "LSE"),
                "LRE": helper.regression(x, 500., z_lre, "LRE"),
                "MLE": helper.mle_profile(x, 500.)}
        for col, (name, z) in enumerate([("LSE", z_lse), ("LRE", z_lre)]):
            zc = z-z.mean()
            b = fits[name]["beta"]
            xx, yy = (zc, yc) if name == "LSE" else (yc, zc)
            fitted_y = zc/b if name == "LSE" else yc*b
            ax = axes[row, col]
            ax.plot(xx, fitted_y, color=color, linewidth=1.1)
            ax.scatter(xx, yy, s=19, color=color, edgecolors="white", linewidths=.4, zorder=3)
            for i, (xi, yi) in enumerate(zip(xx, yy), 1):
                ax.annotate(str(i), (xi, yi), xytext=(5 if name == "LRE" else 0, 5 if i%2 else -11),
                            textcoords="offset points", ha="center", fontsize=6, color="#515151")
            if name == "LSE":
                ax.set(xlim=(-2.8, 1.5), ylim=(-.8, .4), xticks=[-2, -1, 0, 1],
                       yticks=[-.8, -.4, 0, .4], xlabel=r"$z_i-\bar z$", ylabel=r"$y_i-\bar y$")
            else:
                ax.set(xlim=(-.8, .4), ylim=(-2.8, 1.5), xticks=[-.8, -.4, 0, .4],
                       yticks=[-2, -1, 0, 1], xlabel=r"$y_i-\bar y$", ylabel=r"$z_i-\bar z$")
            if row == 0:
                ax.set_title(name, loc="left", fontsize=9, pad=13)
            curves.extend(dict(figure="fixed_gamma_"+name, group=group, point=i,
                               x=float(xi), y=float(yi), fitted_y=float(fi))
                          for i, (xi, yi, fi) in enumerate(zip(xx, yy, fitted_y), 1))
        bs = np.linspace(.5, 65, 550)
        t = y-y.mean()
        def score(b):
            weights = np.exp(b*(t-t.max()))
            weights /= weights.sum()
            return float(1/b-weights@t)
        scores = np.asarray([score(b) for b in bs])
        beta = fits["MLE"]["beta"]
        assert abs(score(beta)) < 1e-10
        ax = axes[row, 2]
        ax.plot(bs, scores, color=color, linewidth=1.1)
        ax.axhline(0, color="#707070", linewidth=.65)
        ax.axvline(5, color="#707070", linestyle="--", linewidth=.65)
        ax.scatter([beta], [0], s=27, color=color, edgecolors="white", linewidths=.5, zorder=4)
        ax.set(xlim=(0, 65), ylim=(-.22, .24), xticks=[0, 15, 30, 45, 60],
               yticks=[-.2, -.1, 0, .1, .2], xlabel=r"$\beta$", ylabel=r"$U_\beta(\beta;500)$")
        if row == 0:
            ax.set_title("MLE", loc="left", fontsize=9, pad=13)
        for col, ax in enumerate(axes[row]):
            identify(ax, chr(97+row*3+col))
        axes[row, 0].text(.02, .9, f"第{group}组", transform=axes[row, 0].transAxes, fontsize=8)
        curves.extend(dict(figure="fixed_gamma_MLE", group=group, beta=float(b), shape_score=float(s))
                      for b, s in zip(bs, scores))
        fixed_evidence.append(dict(group=group, values=x.tolist(),
            y_centered=yc.tolist(), sd_log_true_distance=float(y.std(ddof=1)),
            beta_lower_bound=float(1/(y.max()-y.mean())), fits=fits))
    references(fig)
    layout(fig)
    fig.savefig(IMAGES/"固定位置的回归与形状得分.png", dpi=450, facecolor="white")
    plt.close(fig)
