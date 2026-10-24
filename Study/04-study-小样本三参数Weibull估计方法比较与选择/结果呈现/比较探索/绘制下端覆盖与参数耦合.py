"""Illustrate support, parameter compensation, and MDM's selection rule.

Reuse archived path 474 and the formal summary. No sampling, method calls, or
changes to formal estimates. A zero-gradient point is a profile reference only.
"""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import numpy as np
import pandas as pd
from scipy.optimize import brentq
from scipy.stats import weibull_min

from 第三章机制候选图 import mdm_conditional, gradient

HERE = Path(__file__).resolve().parent
STUDY = HERE.parents[1]
ASSETS = STUDY / "reviewbyhtml/方法对比-v1.0/assets"
BLUE, ORANGE, GRAY = "#0072B2", "#D55E00", "#687784"
plt.rcParams.update({
    "font.family": ["Times New Roman", "Microsoft YaHei"],
    "font.size": 15, "axes.spines.top": False, "axes.spines.right": False,
    "axes.unicode_minus": False, "mathtext.fontset": "custom",
    "mathtext.rm": "Times New Roman", "mathtext.it": "Times New Roman:italic",
    "mathtext.bf": "Times New Roman:bold", "mathtext.fallback": "stix",
})


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(fig, name):
    path = ASSETS / name
    fig.savefig(path, dpi=220, facecolor="white")
    plt.close(fig)
    return {"path": path.relative_to(STUDY).as_posix(), "sha256": sha(path)}


def inputs():
    local = STUDY / "结果呈现/分析数据/3.1机制链"
    cache, stamp = local / "路径估计.csv", local / "路径身份.json"
    provenance = json.loads(stamp.read_text(encoding="utf-8"))
    assert sha(cache) == provenance["cache_sha256"]
    source = STUDY / provenance["identity"]["source"]
    assert sha(source) == provenance["identity"]["source_sha256"]
    config = json.loads((STUDY / "程序/实验配置.json").read_text(encoding="utf-8"))
    core = STUDY / "程序/计算实现-20261016"
    for name, digest in config["source_sha256"].items():
        assert sha(core / name) == digest
    frame = pd.read_csv(cache, float_precision="round_trip")
    assert len(frame) == 15 and frame.source_id.eq(474).all()
    selected = frame[frame.method.eq("MDM")].set_index("n")
    xs = {n: np.array(json.loads(selected.loc[n, "observations"])) for n in [50, 7]}
    assert np.isin(xs[7], xs[50]).all()
    return xs, selected.loc[7], {
        "cache": cache.relative_to(STUDY).as_posix(), "cache_sha256": sha(cache),
        "source": source.relative_to(STUDY).as_posix(), "source_sha256": sha(source),
        "frozen_method_sha256": config["source_sha256"],
    }


def support_figure(xs):
    truth = dict(beta=5.0, eta=1000.0, gamma=500.0)
    candidate = dict(beta=2.0, eta=500.0, gamma=1000.0)
    grid = np.linspace(450, 2150, 2401)
    curves = [weibull_min.pdf(grid, p["beta"], loc=p["gamma"], scale=p["eta"])
              for p in [truth, candidate]]
    fig, axes = plt.subplots(1, 2, figsize=(16, 7), sharex=True, sharey=True)
    fig.subplots_adjust(left=.075, right=.985, bottom=.16, top=.80, wspace=.16)
    records = []
    for ax, n, letter in zip(axes, [50, 7], ["a", "b"]):
        x = xs[n]
        excluded = x <= candidate["gamma"]
        ax.axvspan(500, 1000, color="#f8e8de", zorder=0)
        ax.plot(grid, curves[0], color=BLUE, lw=2.5)
        ax.plot(grid, curves[1], color=ORANGE, lw=2.5, ls="--")
        ax.axvline(500, color=BLUE, lw=1, ls=":", alpha=.65)
        ax.axvline(1000, color=ORANGE, lw=1, ls=":", alpha=.65)
        ax.scatter(x[~excluded], np.full((~excluded).sum(), -.00012),
                   marker="|", s=210, lw=1.4, color=GRAY, clip_on=False)
        if excluded.any():
            ax.scatter(x[excluded], np.full(excluded.sum(), -.00012),
                       marker="x", s=75, lw=2, color=ORANGE, clip_on=False)
        ax.set(xlim=(450, 2150), ylim=(-.00024, .0023),
               xticks=[500, 1000, 1500, 2000], xlabel="寿命",
               title=rf"({letter})  $n={n}$")
        ax.set_yticks([0, .0005, .001, .0015, .002])
        ax.ticklabel_format(axis="y", style="sci", scilimits=(0, 0), useMathText=True)
        records.append(dict(n=n, observations=x.tolist(), minimum=float(x[0]),
                            outside_candidate_support=int(excluded.sum()),
                            candidate_support_compatible=bool(not excluded.any())))
    axes[0].set_ylabel("概率密度")
    handles = [Line2D([], [], color=BLUE, lw=2.5, label=r"$W(5,1000,500)$"),
               Line2D([], [], color=ORANGE, lw=2.5, ls="--", label=r"$W(2,500,1000)$"),
               Line2D([], [], color=GRAY, marker="|", ms=12, ls="", label="观测"),
               Line2D([], [], color=ORANGE, marker="x", ms=7, ls="", label="候选支持范围外的观测")]
    fig.legend(handles=handles, ncol=2, loc="upper center", bbox_to_anchor=(.53, .98), frameon=False)
    assert records[0]["outside_candidate_support"] > 0
    assert records[1]["outside_candidate_support"] == 0
    return save(fig, "31K_下端观测与参数组合.png"), {
        "truth": truth, "fixed_illustrative_candidate": candidate, "samples": records,
        "candidate_is_method_estimate": False,
        "meaning": "Support exclusion disappears for this retained subset; similarity is limited to the observed range, not proof of identical fit or selection by any method.",
    }


def mdm_figure(x, archived):
    grid = np.linspace(0, float(x[0]) * .976, 280)
    sigma = np.array([mdm_conditional(x, g)[1] for g in grid])
    gradients = np.array([gradient(x, g) for g in grid])
    brackets = [(a, b) for a, b, ga, gb in zip(grid[:-1], grid[1:], gradients[:-1], gradients[1:])
                if ga < 0 < gb]
    assert len(brackets) == 1
    zero = brentq(lambda g: gradient(x, g), *brackets[0])
    offset = float(archived.gamma)
    sigma_zero = float(mdm_conditional(x, zero)[1])
    sigma_offset = float(mdm_conditional(x, offset)[1])
    assert abs(gradient(x, zero)) < 1e-6
    assert abs(gradient(x, offset) - .1) < 1e-6
    assert np.isclose(mdm_conditional(x, offset)[0], archived.beta, rtol=1e-8)
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.subplots_adjust(left=.075, right=.985, bottom=.17, top=.86, wspace=.28)
    axes[0].plot(grid, sigma, color=BLUE, lw=2.5)
    axes[0].scatter(zero, sigma_zero, s=65, color=GRAY, zorder=5)
    axes[0].scatter(offset, sigma_offset, s=80, color=ORANGE, zorder=6)
    tangent = np.linspace(offset - 55, offset + 30, 50)
    axes[0].plot(tangent, sigma_offset + .1 * (tangent - offset), color=ORANGE, ls="--", lw=1.6)
    axes[0].set(xlabel=r"$\gamma$", ylabel=r"$S(\gamma)=\min_{\beta}s_{\eta}(\beta,\gamma)$",
                title="(a)", ylim=(80, 117))
    axes[1].plot(grid, gradients, color=BLUE, lw=2.5)
    axes[1].axhline(0, color=GRAY, lw=1)
    axes[1].axhline(.1, color=ORANGE, ls="--", lw=1.5)
    axes[1].scatter([zero, offset], [0, .1], color=[GRAY, ORANGE], s=[65, 80], zorder=6)
    axes[1].set(xlabel=r"$\gamma$", ylabel=r"$g(\gamma)=\mathrm{d}S(\gamma)/\mathrm{d}\gamma$",
                title="(b)", ylim=(-.065, .23), yticks=[-.05, 0, .1, .2])
    for ax in axes:
        ax.set_xlim(0, 1200)
        ax.axvline(500, color="#92999f", ls=":", lw=1.2)
    handles = [Line2D([], [], color=GRAY, marker="o", ls="", ms=7, label=r"$g(\gamma)=0$"),
               Line2D([], [], color=ORANGE, marker="o", ls="", ms=8, label=r"$g(\hat\gamma)=0.1$"),
               Line2D([], [], color="#92999f", ls=":", label=r"$\gamma_{\mathrm{true}}=500$")]
    fig.legend(handles=handles, loc="upper center", bbox_to_anchor=(.53, .99), ncol=3, frameon=False)
    return save(fig, "31L_MDM条件廓线与偏移判据.png"), dict(
        zero_gradient_reference_gamma=float(zero), zero_gradient_reference_sigma=sigma_zero,
        archived_offset_gamma=offset, archived_offset_sigma=sigma_offset,
        archived_offset_gradient=float(gradient(x, offset)),
        archived_parameters={k: float(archived[k]) for k in ["beta", "eta", "gamma"]},
        zero_gradient_reference_is_formal_method_estimate=False,
        profile_gamma_grid=grid.tolist(), profile_sigma=sigma.tolist(), profile_gradient=gradients.tolist(),
        meaning="One sample's rule contrast; it does not establish a sampling variance or the causal effect of changing delta.",
    )


def summary_check():
    source = STUDY / "结果/W5,1000,500/条件汇总.csv"
    meta = json.loads((STUDY / "结果/数据说明.json").read_text(encoding="utf-8"))
    digest = sha(source)
    assert digest == meta["file_sha256"][source.relative_to(STUDY / "结果").as_posix()]
    frame = pd.read_csv(source)
    chosen = frame[frame.n.isin([7, 50]) & frame.method.isin(["MDM-0.1", "LSE"])].copy()
    assert len(chosen) == 4 and chosen.success.eq(1200).all() and chosen.failure.eq(0).all()
    for _, row in chosen.iterrows():
        for p in ["beta", "eta", "gamma"]:
            expected = row[p + "_bias"] ** 2 + (row.success - 1) / row.success * row[p + "_sd"] ** 2
            assert np.isclose(expected, row[p + "_rmse"] ** 2, rtol=1e-10)
    cols = ["n", "method", "total", "success", "failure", "beta_bias", "beta_sd", "beta_rmse"]
    return dict(source=source.relative_to(STUDY).as_posix(), source_sha256=digest,
                shape_metrics=chosen[cols].to_dict("records"),
                sd_ddof=1, finite_mse_identity="RMSE^2=Bias^2+(R-1)/R*SD^2",
                comparison="Both methods use all 1200 samples at each n; not a same-method delta intervention.")


def main():
    xs, archived, identity = inputs()
    support, support_record = support_figure(xs)
    mdm, mdm_record = mdm_figure(xs[7], archived)
    record = dict(source_id=474, identity=identity, new_random_samples=0,
                  method_calls=0, formal_results_modified=False,
                  support_example=support_record, mdm_rule_example=mdm_record,
                  formal_summary=summary_check(), figures=[support, mdm])
    path = HERE / "3.1耦合与MDM核对.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                    encoding="utf-8", newline="\n")
    print(json.dumps({"figures": record["figures"], "new_samples": 0, "method_calls": 0}, ensure_ascii=False))


if __name__ == "__main__":
    main()
