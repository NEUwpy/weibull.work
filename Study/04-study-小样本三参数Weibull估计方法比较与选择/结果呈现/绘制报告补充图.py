"""复用已有结果绘制误差容限曲线；不抽样、不拟合。"""

import hashlib
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.ticker import MaxNLocator
import numpy as np
import pandas as pd


HERE = Path(__file__).resolve().parent
STUDY = HERE.parent
BETA = 5.0
NS = [7, 50]
PARAMETERS = [("beta", "β", "形状估计", BETA, 5.),
              ("eta", "η", "尺度估计", 1000., 1000.),
              ("gamma", "γ", "位置估计", 500., 1000.)]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    config_path = HERE / "绘图配置.json"
    metric_path = HERE / "分析数据/参数指标.csv"
    config = json.loads(config_path.read_text(encoding="utf-8-sig"))
    methods = config["methods"]
    metrics = pd.read_csv(metric_path, float_precision="round_trip")
    sources = {str(p.relative_to(STUDY)): digest(p) for p in [config_path, metric_path]}
    records, probes = {}, []
    for n in NS:
        p = STUDY / "结果/W5,1000,500/估计结果" / f"n{n}.csv"
        sources[str(p.relative_to(STUDY))] = digest(p)
        frame = pd.read_csv(p, float_precision="round_trip")
        assert frame["样本编号"].tolist() == list(range(1200))
        for method in methods:
            name = method["id"]
            status = frame[f"{name}_状态"]
            assert set(status) <= {"success", "failure"}
            valid = status.eq("success").to_numpy()
            stored = metrics[(metrics.beta == BETA) & (metrics.n == n)
                             & (metrics.method == name) & (metrics.subset == "own")]
            assert len(stored) == 1
            row = stored.iloc[0]
            assert valid.sum() == row.effective_count
            for param, _, field, truth, maximum in PARAMETERS:
                values = frame.loc[valid, f"{name}_{field}"].to_numpy(dtype=float)
                assert np.isfinite(values).all()
                errors = values - truth
                # Independent arithmetic check of the saved Bias and sample SD.
                assert np.isclose(errors.mean(), row[f"{param}_bias"], rtol=1e-11, atol=1e-10)
                assert np.isclose(errors.std(ddof=1), row[f"{param}_sd"], rtol=1e-11, atol=1e-10)
                absolute = np.sort(np.abs(errors))
                records[(n, name, param)] = (absolute, row)
                for tolerance in ([.5, 1., 2., 3., 5.] if param == "beta" else [100., 200., 500., 1000.]):
                    count = int(np.searchsorted(absolute, tolerance, side="right"))
                    direct = int(np.count_nonzero(valid & (np.abs(frame[f"{name}_{field}"].to_numpy()-truth) <= tolerance)))
                    assert count == direct
                    probes.append(dict(beta=BETA, n=n, method=name, parameter=param,
                        tolerance=tolerance, total=len(frame), count=count, rate=count/len(frame)))

    plt.rcParams.update({"font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "Arial", "DejaVu Sans"],
        "font.size": 11, "axes.unicode_minus": False,
        "axes.spines.top": False, "axes.spines.right": False})
    output = HERE / "图片"
    written = []

    fig, axes = plt.subplots(2, 3, figsize=(15.2, 7.8))
    for row_index, n in enumerate(NS):
        for col, (param, symbol, _, _, maximum) in enumerate(PARAMETERS):
            ax = axes[row_index, col]
            for method in methods:
                absolute, _ = records[(n, method["id"], param)]
                xs = np.unique(np.r_[0., absolute[absolute <= maximum], maximum])
                rates = np.searchsorted(absolute, xs, side="right")/1200*100
                assert np.all(np.diff(rates) >= 0)
                assert rates.max() <= len(absolute)/1200*100 + 1e-10
                ax.step(xs, rates, where="post", color=method["color"],
                        linestyle=method["linestyle"], lw=1.7)
            ax.set(xlim=(0, maximum), ylim=(0, 100), xlabel=f"{symbol} 绝对误差容限")
            ax.set_yticks([0, 25, 50, 75, 100])
            ax.xaxis.set_major_locator(MaxNLocator(5))
            if col == 0:
                ax.set_ylabel("累计比例（%）")
            ax.grid(color="#EEEEEE", lw=.6)
            ax.text(.97, .08, f"n={n}", transform=ax.transAxes, ha="right", va="bottom")
    handles = [Line2D([], [], color=m["color"], linestyle=m["linestyle"], lw=1.8,
                     label=m["label"]) for m in methods]
    fig.legend(handles=handles, loc="upper center", ncol=4, frameon=False,
               bbox_to_anchor=(.5, 1.0), columnspacing=1.6)
    fig.subplots_adjust(left=.065, right=.985, bottom=.09, top=.86, wspace=.25, hspace=.35)
    path = output / "13_误差容限曲线_β5.png"
    fig.savefig(path, dpi=config["dpi"], facecolor="white")
    plt.close(fig)
    written.append(path)

    assert all(digest(STUDY/p) == sha for p, sha in sources.items())
    pd.DataFrame(probes).to_csv(HERE / "分析数据/误差容限核对点.csv", index=False,
                                encoding="utf-8-sig", float_format="%.17g")
    audit = dict(result="passed", beta=BETA, ns=NS,
        bias_sd_crosschecks=2*7*3*2, tolerance_checks=len(probes),
        rule="success and absolute_error <= tolerance; denominator = all 1200 attempts",
        sources=sources, outputs={p.name:digest(p) for p in written})
    (HERE/"分析数据/补充绘图核验.json").write_text(
        json.dumps(audit, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({k:v for k,v in audit.items() if k not in ["sources", "outputs"]}, ensure_ascii=False))
    probe_frame = pd.DataFrame(probes)
    print(probe_frame[(probe_frame.parameter == "beta") & probe_frame.tolerance.isin([.5, 2.])]
          [["n", "method", "tolerance", "count", "total", "rate"]].to_string(index=False))


if __name__ == "__main__":
    main()
