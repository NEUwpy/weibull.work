"""Study01风格的RMSE玫瑰图；只读取原40条件，不抽样、不调用估计器。

参考 Study/Study 01 New/图片/绘图程序/F03_方法三参数玫瑰图.py。
主视图为六法常规量级，另存七法完整范围；所有n共用线性半径。
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
NS = [50, 20, 15, 10, 7]
METHODS = ["MDM-0.1", "WMLE", "LSE", "LRE(Park)", "MLE", "MMLE(KR)", "MM"]
LABELS = {"MDM-0.1": "MDM-0.1", "LRE(Park)": "LRE (Park)",
          "MMLE(KR)": "MMLE"}
PARAMS = [("beta", "形状估计", 5., 5.),
          ("eta", "尺度估计", 1000., 1000.),
          ("gamma", "位置估计", 500., 1000.)]
COLORS = ["#648BB0", "#DEA273", "#88B5A4"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compute_data():
    sources, rows, groups = {}, [], []
    saved_path = HERE / "分析数据/参数指标.csv"
    saved = pd.read_csv(saved_path, float_precision="round_trip")
    sources[str(saved_path.relative_to(STUDY))] = digest(saved_path)
    for n in NS:
        base = STUDY / "结果/W5,1000,500"
        sample_path = base / "原始样本" / f"n{n}.csv"
        result_path = base / "估计结果" / f"n{n}.csv"
        for path in (sample_path, result_path):
            sources[str(path.relative_to(STUDY))] = digest(path)
        samples = pd.read_csv(sample_path, float_precision="round_trip")
        estimates = pd.read_csv(result_path, float_precision="round_trip")
        assert samples["样本编号"].tolist() == estimates["样本编号"].tolist() == list(range(1200))
        assert np.array_equal(samples.to_numpy(), estimates[samples.columns].to_numpy())
        masks = {m: estimates[f"{m}_状态"].eq("success").to_numpy() for m in METHODS}
        assert all(set(estimates[f"{m}_状态"]) <= {"success", "failure"} for m in METHODS)
        common = np.logical_and.reduce(list(masks.values()))
        groups.append(dict(n=n, total=1200, common=int(common.sum()),
                           success={m:int(mask.sum()) for m, mask in masks.items()}))
        for method in METHODS:
            for subset, mask in [("own", masks[method]), ("common", common)]:
                stored = saved[(saved.beta == 5) & (saved.n == n)
                    & (saved.method == method) & (saved.subset == subset)]
                assert len(stored) == 1
                stored = stored.iloc[0]
                assert int(mask.sum()) == int(stored.effective_count)
                for param, suffix, truth, denominator in PARAMS:
                    values = estimates.loc[mask, f"{method}_{suffix}"].to_numpy(dtype=float)
                    assert np.isfinite(values).all()
                    error = values - truth
                    rmse = float(np.sqrt(np.mean(error**2)))
                    assert np.isclose(rmse, stored[f"{param}_rmse"], rtol=1e-12, atol=1e-10)
                    rows.append(dict(n=n, method=method, subset=subset, parameter=param,
                        count=len(values), rmse=rmse, denominator=denominator,
                        normalized_rmse=rmse/denominator))
    return pd.DataFrame(rows), groups, sources


def radial_scale(maximum):
    ticks = MaxNLocator(nbins=5, steps=[1, 2, 2.5, 5, 10]).tick_values(0, maximum*1.04)
    return float(ticks[-1]), [float(t) for t in ticks[1:]]


def panel(ax, data, methods, extent, ticks, *, label_size=8):
    ax.set_theta_zero_location("N")
    ax.set_theta_direction(-1)
    ax.set_ylim(0, extent*1.24)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["polar"].set_visible(False)
    angle = np.linspace(0, 2*np.pi, 720)
    step = 360/len(methods)
    for i in range(len(methods)):
        center = np.deg2rad(step/2+step*i)
        ax.bar(center, extent, width=np.deg2rad(step-4), color="#F4F7F9",
               edgecolor="none", zorder=0)
    for tick in ticks:
        ax.plot(angle, np.full_like(angle, tick), color="#D8E0E6", lw=.65, zorder=1)
        ax.text(0, tick, f"{tick:g}", ha="center", va="center", fontsize=8,
                color="#77828C", bbox=dict(facecolor="white", edgecolor="none", pad=.4), zorder=5)
    for i, method in enumerate(methods):
        center = np.deg2rad(step/2+step*i)
        for j, (param, _, _, _) in enumerate(PARAMS):
            theta = center+np.deg2rad((j-1)*step*.265)
            value = float(data.loc[(data.method == method) & (data.parameter == param),
                                   "normalized_rmse"].iloc[0])
            assert value <= extent
            ax.bar(theta, value, width=np.deg2rad(step*.235), color=COLORS[j],
                   edgecolor="white", linewidth=1, zorder=3)
            label_r = max(value+extent*.045, extent*.64)
            if label_r > value+extent*.06:
                ax.plot([theta, theta], [value+extent*.01, label_r-extent*.035],
                        color=COLORS[j], lw=.65, zorder=4)
            ax.text(theta, label_r, f"{value:.3f}", ha="center", va="center",
                    fontsize=label_size, color="#2D3C49", zorder=6)
        ax.text(center, extent*1.13, LABELS.get(method, method), ha="center", va="center",
                fontsize=10, fontweight="bold", color="#304C63")


def legend(fig, y=.055):
    handles = [Patch(facecolor=c, label=t) for c, t in zip(COLORS,
                ["β 形状", "η 尺度", "γ 位置"])]
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(.5,y), ncol=3,
               frameon=False, handlelength=1.1, columnspacing=2.4, fontsize=10)


def main():
    audit_path = HERE / "图片/绘图核验.json"
    original = json.loads(audit_path.read_text(encoding="utf-8-sig"))
    assert len(original["sources"]) == 88
    assert all(digest(STUDY/p) == sha for p, sha in original["sources"].items())
    data, groups, sources = compute_data()
    selected = data[data.subset == "common"]
    plt.rcParams.update({"font.family":"sans-serif", "font.sans-serif":["Microsoft YaHei", "DejaVu Sans"],
                         "font.size":10, "axes.unicode_minus":False})
    image_dir = HERE / "图片"
    written = []

    def export(fig, name):
        path = image_dir / name
        fig.savefig(path, dpi=260, facecolor="white")
        plt.close(fig)
        written.append(path)

    core = METHODS[:-1]
    extent, ticks = radial_scale(selected[selected.method.isin(core)].normalized_rmse.max())
    full_extent, full_ticks = radial_scale(selected[selected.n.isin([50,7])].normalized_rmse.max())
    for n in NS:
        fig = plt.figure(figsize=(7.2,7.2), facecolor="white")
        ax = fig.add_axes([.08,.14,.84,.79], projection="polar")
        panel(ax, selected[selected.n == n], core, extent, ticks)
        fig.text(.5,.965,f"n = {n}",ha="center",fontsize=14,fontweight="bold",color="#304C63")
        legend(fig)
        export(fig, f"12_RMSE玫瑰图_β5_n{n}.png")

    for methods, limit, scale_ticks, stem in [
            (core, extent, ticks, "14_RMSE玫瑰图_β5_n50与n7.png"),
            (METHODS, full_extent, full_ticks, "15_RMSE玫瑰图_β5_七法完整范围.png")]:
        fig = plt.figure(figsize=(13.8,7.1), facecolor="white")
        for i,n in enumerate([50,7]):
            ax = fig.add_axes([.025+.50*i,.14,.45,.79], projection="polar")
            panel(ax, selected[selected.n == n], methods, limit, scale_ticks)
            fig.text(.25+.5*i,.965,f"n = {n}",ha="center",fontsize=14,fontweight="bold",color="#304C63")
        legend(fig)
        export(fig, stem)

    # One continuous row follows decreasing n without changing its scale.
    fig = plt.figure(figsize=(28.,6.2), facecolor="white")
    for i,n in enumerate(NS):
        ax = fig.add_axes([.006+.20*i,.14,.188,.78], projection="polar")
        panel(ax, selected[selected.n == n], core, extent, ticks, label_size=8)
        fig.text(.10+.20*i,.955,f"n = {n}",ha="center",fontsize=17,
                 fontweight="bold",color="#304C63")
    legend(fig, .025)
    export(fig, "16_RMSE玫瑰图_β5_样本量序列.png")

    gaps = []
    for subset in ["own", "common"]:
        for n in NS:
            for param, *_ in PARAMS:
                part = data[(data.subset == subset) & (data.n == n)
                            & (data.parameter == param) & data.method.isin(core)]
                low, high = part.loc[part.normalized_rmse.idxmin()], part.loc[part.normalized_rmse.idxmax()]
                gaps.append(dict(subset=subset, n=n, parameter=param,
                    low_method=low.method, low=float(low.normalized_rmse),
                    high_method=high.method, high=float(high.normalized_rmse),
                    span=float(high.normalized_rmse-low.normalized_rmse)))
    gap_frame = pd.DataFrame(gaps)
    data.to_csv(HERE/"分析数据/RMSE玫瑰图数据.csv",index=False,encoding="utf-8-sig",float_format="%.17g")
    gap_frame.to_csv(HERE/"分析数据/RMSE玫瑰图方法差距.csv",index=False,encoding="utf-8-sig",float_format="%.17g")
    assert all(digest(STUDY/p) == sha for p,sha in original["sources"].items())
    assert all(digest(HERE/"图片"/p) == v["sha256"] for p,v in original["outputs"].items())
    audit = dict(result="passed", beta=5, eta=1000, gamma=500, sample_sizes=NS,
        groups=groups, displayed_methods=core, full_range_methods=METHODS,
        normalization={"beta":"true beta", "eta":"true eta", "gamma":"true eta"},
        geometry="Equal angular sectors; linear zero-origin radius = normalized RMSE; area is not RMSE",
        sequence_layout="One row, left to right: n=50,20,15,10,7; shared legend and radial scale",
        main_extent=extent, main_ticks=ticks, full_extent=full_extent, full_ticks=full_ticks,
        population="Seven-method common-success intersection separately within each n",
        limits="Point estimates; conditional on success; different n can have different selected populations. MM has a separate full-range view.",
        checked_metrics=len(data), original_csvs_unchanged=88, original_pngs_unchanged=len(original["outputs"]),
        sources=sources, outputs={p.name:digest(p) for p in written})
    (HERE/"分析数据/玫瑰图核验.json").write_text(json.dumps(audit,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({k:v for k,v in audit.items() if k not in ["sources","outputs"]},ensure_ascii=False))
    print(gap_frame[gap_frame.n.isin([50,7])].to_string(index=False))


if __name__ == "__main__":
    main()
