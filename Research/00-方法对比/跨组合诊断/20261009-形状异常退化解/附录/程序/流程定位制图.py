"""PNG-only method-flow figures from archived samples and all-record checks.

Contract: Fig2 follows matched LSE samples through fixed-location regression,
actual location criterion, and conditional shape. Fig3 follows every original
anomaly through the retrospective true-location intervention. Python quantitative
grids, fixed linear axes per quantity, no prose boxes or simulated curves.
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
IMAGES = HERE.parents[1]/"图片"
spec = importlib.util.spec_from_file_location("checks", HERE/"逐方法机制复核.py")
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)
plt.rcParams.update({"font.family":"sans-serif", "font.sans-serif":["Microsoft YaHei", "Arial", "DejaVu Sans"],
                     "font.size":9, "axes.linewidth":.65, "axes.spines.top":False,
                     "axes.spines.right":False, "xtick.major.width":.65, "ytick.major.width":.65,
                     "legend.frameon":False, "axes.unicode_minus":False})


def main():
    summary = json.loads((HERE/"全量流程定位.json").read_text(encoding="utf-8"))
    paired = json.loads((HERE/"逐方法机制复核.json").read_text(encoding="utf-8"))
    program = ROOT/"W(2,100,500)/20261007-暂存样本补齐/程序"
    snapshot = program/"依赖快照/python"
    sys.path.insert(0, str(snapshot))
    lse = helper.load_module(snapshot/"methods/lse.py", "plot_frozen_lse")
    z = lse.log_weibull_order_stat_means(15)
    fig, axs = plt.subplots(2, 3, figsize=(9.1, 5.6))
    curves, fitted = [], []
    for row, (key, color) in enumerate((("high_control", "#487A8B"), ("high", "#B67550"))):
        record = paired["samples"][key]
        x = np.asarray(record["values"])
        original = record["methods"]["LSE"]["archived"]
        true_fit = helper.regression(x, 500., z, "LSE")
        y = np.log(x-500)
        yfit = y.mean()+(z-z.mean())/true_fit["beta"]
        ax = axs[row, 0]
        ax.plot(z, yfit, color=color, linewidth=1.1)
        ax.scatter(z, y, s=15, color=color, edgecolors="white", linewidths=.35, zorder=3)
        for i, (zi, yi) in enumerate(zip(z, y), 1):
            ax.annotate(str(i), (zi, yi), xytext=(0, 5 if i%2 else -10), textcoords="offset points", ha="center", fontsize=6, color="#515151")
        ax.set(xlim=(-3.6, 1.5), ylim=(2.6, 5.7), xticks=[-3,-2,-1,0,1], yticks=[3,4,5], xlabel=r"$z_i$", ylabel=r"$y_i$ ($\gamma=500$)")
        grid = np.unique(np.r_[np.linspace(0, x[0]-1e-3, 550), np.linspace(490, x[0]-1e-3, 200), original["gamma_hat"], 500.])
        profiles = [helper.regression(x, float(g), z, "LSE") for g in grid]
        loss = np.array([p["relative_residual"] for p in profiles])
        beta = np.array([p["beta"] for p in profiles])
        sel = helper.regression(x, original["gamma_hat"], z, "LSE")
        assert abs(sel["beta"]-original["beta_hat"])<1e-7
        for ax in axs[row, 1:]:
            ax.set(xlim=(0,550), xticks=[0,100,200,300,400,500], xlabel=r"$\gamma$")
            ax.axvline(500, color="#707070", linestyle="--", linewidth=.65)
        ax = axs[row, 1]
        ax.plot(grid, loss, color=color, linewidth=1.1)
        ax.scatter([original["gamma_hat"]], [sel["relative_residual"]], s=27, color=color, edgecolors="white", linewidths=.5, zorder=4, clip_on=False)
        ax.set(ylim=(0,.25), yticks=[0,.05,.10,.15,.20,.25], ylabel=r"$1-R^2(\gamma)$")
        ax = axs[row, 2]
        ax.plot(grid, beta, color=color, linewidth=1.1)
        ax.axhline(2, color="#707070", linestyle="--", linewidth=.65)
        ax.scatter([original["gamma_hat"]], [sel["beta"]], s=27, color=color, edgecolors="white", linewidths=.5, zorder=4, clip_on=False)
        ax.set(ylim=(0,30), yticks=[0,5,10,15,20,25,30], ylabel=r"$\hat\beta(\gamma)$")
        for col, ax in enumerate(axs[row]):
            ax.text(-.15, 1.06, chr(97+row*3+col), transform=ax.transAxes, fontsize=11, fontweight="bold")
        axs[row,0].set_title(f"第{record['group']}组", loc="left", fontsize=9, pad=13)
        curves.extend(dict(group=record["group"], gamma=float(g), relative_residual=float(l), beta=float(b)) for g,l,b in zip(grid,loss,beta))
        fitted.append(dict(group=record["group"], z=z.tolist(), y=y.tolist(), fitted_y=yfit.tolist(), selected_gamma=original["gamma_hat"], selected_beta=sel["beta"]))
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([0],[0],color="#707070",linestyle="--",linewidth=.7,label="真值"),
                        Line2D([0],[0],marker="o",color="#555555",linestyle="none",markersize=4,label="所选位置")],
               loc="lower center", ncol=2, bbox_to_anchor=(.53,0.0), fontsize=8)
    fig.subplots_adjust(left=.075,right=.98,bottom=.13,top=.91,wspace=.40,hspace=.47)
    fig.savefig(IMAGES/"图2_位置左移与参数补偿.png",dpi=450,facecolor="white")
    plt.close(fig)
    with (HERE/"流程定位图数据.csv").open("w",encoding="utf-8",newline="") as stream:
        writer=csv.DictWriter(stream,fieldnames=list(curves[0]),lineterminator="\n")
        writer.writeheader();writer.writerows(curves)
    methods=list(summary["methods"])
    resolved=np.array([summary["methods"][m]["removed_at_true_location"] for m in methods])
    total=np.array([summary["methods"][m]["abnormal"] for m in methods])
    remaining=total-resolved
    assert resolved.sum()==948 and remaining.sum()==15 and total.sum()==963
    fig, ax=plt.subplots(figsize=(7.1,3.8))
    pos=np.arange(len(methods))
    ax.barh(pos,resolved/total*100,color="#8CAEB1",height=.52,label="未达判据")
    ax.barh(pos,remaining/total*100,left=resolved/total*100,color="#BF8764",height=.52,label="仍达判据")
    for y,a,b in zip(pos,resolved,total):ax.text(50,y,f"{a}/{b}",ha="center",va="center",fontsize=9,color="#203C43")
    ax.set(yticks=pos,yticklabels=["MDM", "LSE", "LRE", "MLE", "WMLE", "MMLE"],xlim=(0,100),xticks=[0,20,40,60,80,100],xlabel="原异常中占比 (%)")
    ax.invert_yaxis()
    ax.legend(loc="lower center",bbox_to_anchor=(.5,-.32),ncol=2,fontsize=9)
    fig.subplots_adjust(left=.13,right=.98,bottom=.26,top=.95)
    fig.savefig(IMAGES/"图3_原异常的位置环节复核.png",dpi=450,facecolor="white")
    plt.close(fig)
    qa=dict(figure2=dict(combination="W(2,100,500)",n=15,groups=[35,36],
                         selection="chapter1 anomaly group36; nearest group id35 with LSE/LRE/MLE all non-abnormal",
                         fixed_axes={"gamma":[0,550],"relative_residual":[0,.25],"beta":[0,30],"z":[-3.6,1.5],"y":[2.6,5.7]},
                         fitting_points=fitted, evidence="actual conditional formulas; data-file points preserved; all original point ids shown"),
            figure3=dict(scope="original 963 anomalies only",removed=948,remaining=15,
                         no_claim="This diagnostic is not an implementable repair or exclusive causal attribution.",counts=summary["methods"]),
            backend="Python",export="PNG only",source_hashes=summary["source_sha256"])
    (HERE/"流程定位制图核对.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS: matched LSE flow, all963 anomaly tracking, fixed axes, PNG only")


if __name__=="__main__":main()
