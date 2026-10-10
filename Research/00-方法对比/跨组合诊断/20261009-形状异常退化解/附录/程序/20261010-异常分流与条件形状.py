"""Split archived abnormalities before explaining their distinct processes.

Reproduce the existing classification/LSE figures, add likelihood and fixed-
location contrasts. All output is derived from archived samples/conditional
checks; no method run(), resampling, original-result or failure-state edits.
"""
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
ROOT = HERE.parents[3]
IMAGES = HERE.parents[1] / "图片"


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
    p = Path(entry["program"])
    base = p if p.name == "程序" else p.parent
    matrix = base / ("中间数据/matrix.json" if p.name == "程序" else "完整矩阵/数据/matrix.json")
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


def main():
    full = json.loads((HERE/"全量流程定位.json").read_text(encoding="utf-8"))
    sources = json.loads((ROOT/"跨组合汇总/程序/20261007-新增五组合/13组合取数.json").read_text(encoding="utf-8"))["sources"]
    hashes = dict(full["source_sha256"])
    for name in [Path(__file__), HERE/"全量流程定位.json", HERE/"全量流程定位.csv",
                 HERE/"逐方法机制复核.json", HERE/"流程定位制图.py"]:
        hashes[str(name)] = helper.digest(name)
    assert all(helper.digest(Path(name)) == digest for name, digest in hashes.items())
    rows = list(csv.DictReader((HERE/"全量流程定位.csv").open(encoding="utf-8")))
    bad = [r for r in rows if r["abnormal"] == "True"]
    split = [dict(r, fixed_location_class="固定真位置后仍异常" if r["fixed_true_abnormal"] == "True"
                  else "固定真位置后退出异常") for r in bad]
    assert len(split) == 963 and sum(r["fixed_true_abnormal"] == "True" for r in split) == 15
    write_csv(HERE/"20261010-原异常分流.csv", split)
    remaining, by_method = [], {}
    for r in split:
        name = r["method"]
        counts = by_method.setdefault(name, dict(original=0, exited=0, remaining=0))
        counts["original"] += 1
        counts["remaining" if r["fixed_true_abnormal"] == "True" else "exited"] += 1
        if r["fixed_true_abnormal"] != "True":
            continue
        entry, base, path, data = source(r["combination"], sources)
        x = sample(data, int(r["n"]), int(r["group"]))
        if name == "MMLE":
            x = x[1:]
        y = np.log(x-float(r["gamma_true"]))
        if name in ("MLE", "MMLE"):
            q = helper.shape_profile(x, float(r["gamma_true"]))
            assert abs(np.log(q["beta"]/float(r["beta_fixed_true_location"]))) < 2e-5
            assert q["beta"] >= 1/(y.max()-y.mean())-1e-8
        else:
            snapshot = base/"依赖快照/python"
            sys.path.insert(0, str(snapshot))
            frozen = helper.load_module(snapshot/"methods/lse.py", "remaining_lse_"+str(len(remaining)))
            n = len(x)
            if name == "LSE":
                z = frozen.log_weibull_order_stat_means(n)
            else:
                rank = np.arange(1, n+1)
                p = (rank-.3)/(n+.4) if entry["protocol"] == "historical-eight" else (rank-3/8)/(n+1/4)
                z = np.log(-np.log1p(-p))
            q = helper.regression(x, float(r["gamma_true"]), z, name)
            assert abs(np.log(q["beta"]/float(r["beta_fixed_true_location"]))) < 2e-5
        remaining.append(dict(r, sd_log_true_distance=float(y.std(ddof=1)),
                              max_log_minus_mean=float(y.max()-y.mean()),
                              mle_shape_lower_bound=float(1/(y.max()-y.mean()))))
    assert len(remaining) == 15
    write_csv(HERE/"20261010-固定位置仍异常.csv", remaining)
    mmle_remaining = [r for r in remaining if r["method"] == "MMLE"]
    delete_only = [r for r in mmle_remaining if r["full_sample_fixed_true_abnormal"] == "False"]
    assert len(mmle_remaining) == 5 and len(delete_only) == 2
    exited = [r for r in split if r["fixed_true_abnormal"] == "False"]
    exited_mle = [r for r in exited if r["method"] == "MLE"]
    mle_exit_criterion_counts = dict(
        not_below_true=sum(float(r["selected_minus_true"]) >= -1e-8 for r in exited_mle),
        below_true=sum(float(r["selected_minus_true"]) < -1e-8 for r in exited_mle))
    assert mle_exit_criterion_counts == dict(not_below_true=178, below_true=12)

    # Existing mother script draws actual LSE fitting points and classification.
    module(HERE/"流程定位制图.py", "mother_plot").main()
    paired = json.loads((HERE/"逐方法机制复核.json").read_text(encoding="utf-8"))
    curves, plotted = [], []
    fig, axes = plt.subplots(2, 3, figsize=(9.1, 5.6))
    for row, (key, color) in enumerate([("high_control", BLUE), ("high", BROWN)]):
        record = paired["samples"][key]
        x = np.asarray(record["values"])
        old = record["methods"]["MLE"]["archived"]
        selected = helper.shape_profile(x, old["gamma_hat"])
        at_truth = helper.shape_profile(x, 500.)
        grid = np.unique(np.r_[np.linspace(0, x[0]-1e-3, 550),
            np.linspace(490, x[0]-1e-3, 200), 500., old["gamma_hat"]])
        p = [helper.shape_profile(x, float(g)) for g in grid]
        delta_ll = np.asarray([v["ll"]-at_truth["ll"] for v in p])
        beta = np.asarray([v["beta"] for v in p])
        eta = np.asarray([v["eta"] for v in p])
        assert abs(np.log(selected["beta"]/old["beta_hat"])) < 2e-5
        assert abs(np.log(selected["eta"]/old["eta_hat"])) < 2e-5
        ys = [delta_ll, beta, eta]
        vals = [selected["ll"]-at_truth["ll"], selected["beta"], selected["eta"]]
        for col, (ax, yy, val) in enumerate(zip(axes[row], ys, vals)):
            ax.plot(grid, yy, color=color, linewidth=1.1)
            ax.scatter([old["gamma_hat"]], [val], s=27, color=color,
                       edgecolors="white", linewidths=.5, zorder=4, clip_on=False)
            ax.axvline(500, color="#707070", linestyle="--", linewidth=.65)
            ax.set(xlim=(0, 550), xticks=[0, 100, 200, 300, 400, 500], xlabel=r"$\gamma$")
            identify(ax, chr(97+row*3+col))
        axes[row, 0].axhline(0, color="#b0b0b0", linewidth=.5)
        axes[row, 0].set(ylim=(-2, 1), yticks=[-2, -1, 0, 1], ylabel=r"$\ell_p(\gamma)-\ell_p(500)$")
        axes[row, 1].axhline(2, color="#707070", linestyle="--", linewidth=.65)
        axes[row, 1].set(ylim=(0, 30), yticks=[0, 5, 10, 15, 20, 25, 30], ylabel=r"$\hat\beta(\gamma)$")
        axes[row, 2].axhline(100, color="#707070", linestyle="--", linewidth=.65)
        axes[row, 2].set(ylim=(0, 650), yticks=[0, 100, 200, 300, 400, 500, 600], ylabel=r"$\hat\eta(\gamma)$")
        axes[row, 0].set_title(f"第{record['group']}组", loc="left", fontsize=9, pad=13)
        curves.extend(dict(figure="MLE", group=record["group"], gamma=float(g),
                           ll_difference=float(l), beta=float(b), eta=float(e))
                      for g, l, b, e in zip(grid, delta_ll, beta, eta))
        plotted.append(dict(group=record["group"], selected_gamma=old["gamma_hat"],
            selected=selected, at_true=at_truth))
    references(fig)
    layout(fig)
    fig.savefig(IMAGES/"MLE位置选择与条件参数.png", dpi=450, facecolor="white")
    plt.close(fig)

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
                "MLE": helper.shape_profile(x, 500.)}
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
    write_csv(HERE/"20261010-异常分流图数据.csv", curves)
    result = dict(classification=by_method, removed=948, remaining=15,
        classification_limit="True gamma intervention; not exclusive attribution and not a deployable estimator.",
        fixed_true_remaining_counts={m: c["remaining"] for m, c in by_method.items()},
        fixed_true_remaining_all_n7=all(r["n"] == "7" for r in remaining),
        mle_exit_criterion_counts=mle_exit_criterion_counts,
        mmle_remaining=5, mmle_remaining_also_full_sample_abnormal=3,
        mmle_remaining_delete_changes_flag=2,
        mle_example=plotted, conditional_example=fixed_evidence,
        conditional_control="Same design/n; nearest group id with all three fixed-gamma shapes within criterion; lower id breaks ties.",
        plot_axes={"MLE_gamma":[0,550], "MLE_ll_difference":[-2,1], "MLE_beta":[0,30], "MLE_eta":[0,650],
                   "centered_y":[-.8,.4], "centered_z":[-2.8,1.5], "fixed_gamma_shape":[0,65], "fixed_gamma_score":[-.22,.24]},
        equations="Actual frozen regression coordinates; conditional MLE score and profile likelihood. No common criterion is imposed across methods.",
        backend="Python", export="PNG only", source_sha256=hashes,
        sources_unchanged=all(helper.digest(Path(name))==digest for name,digest in hashes.items()))
    assert result["sources_unchanged"]
    (HERE/"20261010-异常分流核验.json").write_text(json.dumps(result, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print("PASS: original963 split948/15; four fixed-location method branches; independent MLE figures; frozen sources unchanged")


if __name__ == "__main__":
    main()
