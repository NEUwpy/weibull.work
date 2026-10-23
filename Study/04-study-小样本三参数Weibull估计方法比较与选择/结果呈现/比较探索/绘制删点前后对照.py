"""将删点前后的观测、拟合和实际参数移动放在同一幅图中；复用已保存的嵌套路径。"""
from pathlib import Path
import argparse
import hashlib
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parents[2]
ASSETS=ROOT/"reviewbyhtml/方法对比-v1.0/assets"
DATA=ROOT/"结果呈现/分析数据/嵌套样本拟合.csv"
METHODS=[("MMLE","#CC79A7"),("MDM","#0072B2"),("LSE","#009E73")]
plt.rcParams.update({"font.family":"Microsoft YaHei","font.size":11,"axes.spines.top":False,"axes.spines.right":False,"axes.unicode_minus":False})

def cdf(t,b,e,g):return -np.expm1(-np.maximum((t-g)/e,0)**b)


def read_rows():
    rows = pd.read_csv(DATA, float_precision="round_trip")
    rows["method"] = rows["method"].replace({"K–R": "MMLE"})
    return rows



def nested_gallery(rows, source_id=474, source_path=DATA):
    """同一嵌套样本下，比较三法的CDF拟合和单次带符号参数误差。

    每个n一张2×3定量组图：上排每法独占一列，下排每参数独占一列。
    读取既有估计，不再抽样或求解；跨n固定坐标，仅输出PNG。
    """
    sizes = [50, 20, 15, 10, 7]
    parameters = [("beta", "形状 β", 5.), ("eta", "尺度 η", 1000.), ("gamma", "位置 γ", 500.)]
    selected = rows[rows.source_id.eq(source_id)]
    samples, estimates = {}, {}
    previous = None
    for n in sizes:
        part = selected[selected.n.eq(n)]
        sample_rows = [np.array(json.loads(v), dtype=float) for v in part.observations]
        x = sample_rows[0]
        assert all(np.array_equal(x, v) for v in sample_rows)
        assert len(x) == n and np.all(np.diff(x) >= 0)
        assert previous is None or np.isin(x, previous).all()
        samples[n] = x
        previous = x
        for method, _ in METHODS:
            record = part[part.method.eq(method)]
            assert len(record) == 1 and bool(record.iloc[0].converged)
            estimates[n, method] = record.iloc[0]

    limits = {}
    for parameter, _, truth in parameters:
        errors = [float(estimates[n, method][parameter]) - truth
                  for n in sizes for method, _ in METHODS]
        low, high = min(0., min(errors)), max(0., max(errors))
        span = high - low
        limits[parameter] = (low - .18 * span, high + .22 * span)

    t = np.linspace(400., 2100., 1000)
    assert all(x.min() > t.min() and x.max() < t.max() for x in samples.values())
    records = []
    for n in sizes:
        fig, axes = plt.subplots(2, 3, figsize=(13, 7.8))
        fig.subplots_adjust(left=.075, right=.98, top=.87, bottom=.10,
                            hspace=.50, wspace=.36)
        x = samples[n]
        positions = (np.arange(1, n + 1) - .5) / n
        for j, (method, color) in enumerate(METHODS):
            ax = axes[0, j]
            row = estimates[n, method]
            ax.plot(t, cdf(t, 5., 1000., 500.), ls="--", c="#6d7277", lw=1.4)
            ax.plot(t, cdf(t, row.beta, row.eta, row.gamma), c=color, lw=2.0)
            ax.scatter(x, positions, c="#252a2d", s=24, zorder=4)
            ax.plot(x, np.full(n, -.025), "|", c="#62666a", ms=6)
            ax.set(xlim=(400, 2100), ylim=(-.06, 1.04), xticks=[500, 1000, 1500, 2000],
                   yticks=[0, .25, .5, .75, 1], xlabel="寿命 t", ylabel="累计概率",
                   title=f"({chr(97+j)}) {method}")
            ax.grid(axis="y", color="#ededed", lw=.7)

        for j, (parameter, title, truth) in enumerate(parameters):
            ax = axes[1, j]
            errors = [float(estimates[n, method][parameter]) - truth for method, _ in METHODS]
            ax.bar(range(3), errors, width=.52, color=[color for _, color in METHODS], zorder=3)
            ax.axhline(0, c="#62666a", lw=1.0)
            ax.set(xticks=range(3), xticklabels=[method for method, _ in METHODS],
                   xlim=(-.65, 2.65), ylim=limits[parameter], ylabel="估计值 − 真值",
                   title=f"({chr(100+j)}) {title}")
            ax.grid(axis="y", color="#ededed", lw=.7)
            for k, ((method, _), error) in enumerate(zip(METHODS, errors)):
                label = f"{error:+.2f}" if parameter == "beta" else f"{error:+.1f}"
                ax.annotate(label, (k, error), xytext=(0, -6 if error < 0 else 5),
                            textcoords="offset points", ha="center",
                            va="top" if error < 0 else "bottom", fontsize=10)
                records.append({"n": n, "method": method, "parameter": parameter,
                                "estimate": float(estimates[n, method][parameter]),
                                "truth": truth, "signed_error": error})

        handles = [Line2D([], [], color=color, lw=2, label=method) for method, color in METHODS]
        handles += [Line2D([], [], color="#6d7277", ls="--", label="真实分布"),
                    Line2D([], [], color="#252a2d", ls="", marker="o", ms=5, label="本组观测")]
        fig.legend(handles=handles, ncol=5, loc="upper center", frameon=False, fontsize=10.5)
        fig.text(.975, .975, f"n = {n}", ha="right", va="top", fontsize=12)
        fig.savefig(ASSETS/f"31_嵌套删点_样本{source_id}_n{n}.png", dpi=200, facecolor="white")
        plt.close(fig)

    qa = {"source_id": source_id, "sizes": sizes,
          "source_sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
          "nested_subsets_checked": True, "same_observations_across_methods_checked": True,
          "statistic": "single-sample signed error: estimate minus truth",
          "cdf_limits": {"x": [400, 2100], "y": [-.06, 1.04]},
          "parameter_limits": limits, "values": records}
    (DATA.parent/"嵌套删点组图核验.json").write_text(
        json.dumps(qa, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(json.dumps({"source_id": source_id, "sizes": sizes,
                      "panels": 30, "parameter_values": len(records),
                      "nested_subsets_checked": True}, ensure_ascii=False))

def recovery_figures(rows):
    import sys
    sys.path.insert(0,str(ROOT/"程序/计算实现-20261016"))
    from methods.lse import log_weibull_order_stat_means
    from scipy.optimize import minimize_scalar
    records=[]
    for sid in [1055,474]:
        fig,axs=plt.subplots(1,2,figsize=(12,4.8))
        fig.subplots_adjust(left=.085,right=.985,bottom=.17,top=.80,wspace=.28)
        minimum_spreads=[]
        selected_beta=rows[(rows.source_id==sid)&rows.n.isin([50,7])&rows.method.eq("MDM")].beta.to_numpy()
        for n,c in [(50,"#0072B2"),(7,"#D55E00")]:
            part=rows[(rows.source_id==sid)&(rows.n==n)]
            x=np.array(json.loads(part.iloc[0].observations))
            mdm=part[part.method.eq("MDM")].iloc[0]
            p=(np.arange(1,n+1)-.3)/(n+.4);q=-np.log1p(-p)
            beta_grid=np.linspace(float(selected_beta.min())*.6,float(selected_beta.max())*1.6,500)
            spread=np.array([np.std((x-mdm.gamma)/q**(1/b),ddof=1) for b in beta_grid])
            f=lambda b:np.std((x-mdm.gamma)/q**(1/b),ddof=1)
            res=minimize_scalar(f,bounds=(.1,15),method="bounded")
            assert np.isclose(res.x,mdm.beta,rtol=1e-10)
            eta=float(np.mean((x-mdm.gamma)/q**(1/res.x)))
            assert np.isclose(eta,mdm.eta,rtol=1e-10)
            axs[0].plot(beta_grid,spread,c=c,lw=1.8,label=f"n = {n}")
            axs[0].scatter(mdm.beta,f(mdm.beta),c=c,s=45)
            minimum_spreads.append(float(f(mdm.beta)))
            lse=part[part.method.eq("LSE")].iloc[0]
            z=log_weibull_order_stat_means(n);y=np.log(x-lse.gamma)
            slope=float(np.dot(z-z.mean(),y-y.mean())/np.dot(z-z.mean(),z-z.mean()))
            intercept=float(y.mean()-slope*z.mean())
            assert np.allclose([1/slope,np.exp(intercept)],[lse.beta,lse.eta],rtol=1e-12)
            axs[1].scatter(z,y,c=c,s=26)
            grid=np.linspace(z.min(),z.max(),100)
            axs[1].plot(grid,intercept+slope*grid,c=c,lw=1.8)
            records.append(dict(sid=sid,n=n,mdm_beta_from_minimum=float(res.x),mdm_eta_from_mean=eta,lse_slope=slope,lse_beta_from_slope=1/slope,lse_eta_from_intercept=float(np.exp(intercept))))
        axs[0].set_ylim(0,max(minimum_spreads)*3)
        axs[0].set(xlabel="候选形状 β",ylabel="伪尺度标准差",title="MDM：选定位置后，取标准差最小的形状")
        axs[1].set(xlabel="顺序统计量参考坐标 z",ylabel="ln(观测值 − 估计位置)",title="LSE：β = 1 / 回归斜率")
        fig.legend(*axs[0].get_legend_handles_labels(),ncol=2,loc="upper center",frameon=False)
        fig.savefig(ASSETS/f"31_参数恢复过程_样本{sid}.png",dpi=200,facecolor="white");plt.close(fig)
    (DATA.parent/"删点定位与参数恢复核对.json").write_text(json.dumps(records,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")


def main():
    rows=read_rows()
    recovery_figures(rows)
    t=np.linspace(400,2100,1000)
    changes=[]
    for sid in [1055,474]:
        fig=plt.figure(figsize=(13,8.2))
        grid=fig.add_gridspec(2,6,height_ratios=[1.15,1],hspace=.60,wspace=.90)
        top=[fig.add_subplot(grid[0,:3]),fig.add_subplot(grid[0,3:])]
        bottom=[fig.add_subplot(grid[1,2*i:2*i+2]) for i in range(3)]
        fig.subplots_adjust(left=.085,right=.98,top=.87,bottom=.10)
        d=rows[rows.source_id.eq(sid)]
        retained=np.array(json.loads(d[d.n.eq(7)].iloc[0].observations))
        original=np.array(json.loads(d[d.n.eq(50)].iloc[0].observations))
        assert set(retained).issubset(original)
        for ax,n in zip(top,[50,7]):
            part=d[d.n.eq(n)];x=np.array(json.loads(part.iloc[0].observations))
            positions=(np.arange(1,n+1)-.5)/n
            kept=np.isin(x,retained)
            ax.scatter(x[~kept],positions[~kept],c="#bbc1c5",s=21,zorder=4)
            ax.scatter(x[kept],positions[kept],c="#252a2d",s=32,zorder=5)
            ax.plot(x,np.full(n,-.025),"|",c="#555555",ms=7)
            ax.plot(t,cdf(t,5,1000,500),ls="--",c="#555555",lw=1.6)
            for m,c in METHODS:
                r=part[part.method.eq(m)].iloc[0]
                ax.plot(t,cdf(t,r.beta,r.eta,r.gamma),c=c,lw=1.7)
            ax.set(xlim=(400,2100),ylim=(-.06,1.02),xlabel="寿命 t",ylabel="累计概率",title=f"删点前 n = {n}" if n==50 else "删点后 n = 7")
        handles=[Line2D([],[],color="#555555",ls="--",label="真实分布")]+[Line2D([],[],color=c,label=m) for m,c in METHODS]+[Line2D([],[],color="#252a2d",ls="",marker="o",label="保留的7点"),Line2D([],[],color="#bbc1c5",ls="",marker="o",label="删除的43点")]
        fig.legend(handles=handles,ncol=6,loc="upper center",frameon=False,fontsize=11)
        for ax,param,title,truth in zip(bottom,["beta","eta","gamma"],["形状 β","尺度 η","位置 γ"],[5,1000,500]):
            for j,(m,c) in enumerate(METHODS):
                before=float(d[(d.n==50)&(d.method==m)].iloc[0][param]);after=float(d[(d.n==7)&(d.method==m)].iloc[0][param])
                ax.plot([before,after],[j,j],color=c,lw=1.8)
                ax.scatter(before,j,s=64,facecolors="white",edgecolors=c,lw=1.6,zorder=4)
                ax.scatter(after,j,s=35,c=c,zorder=5)
                if abs(after-before)>1e-8:
                    ax.annotate("",(after,j),(before,j),arrowprops=dict(arrowstyle="->",color=c,lw=1.4),zorder=3)
                changes.append(dict(sid=sid,method=m,parameter=param,before=before,after=after,change=after-before))
            ax.axvline(truth,c="#777777",ls="--",lw=1)
            ax.set(yticks=range(3),yticklabels=[m for m,c in METHODS],ylim=(2.65,-.65),xlabel="参数估计值",title=title)
            ax.grid(axis="x",color="#ededed",lw=.7)
        legend=[Line2D([],[],color="#555555",ls="",marker="o",mfc="white",ms=7,label="删点前"),Line2D([],[],color="#555555",ls="",marker="o",ms=5,label="删点后")]
        fig.legend(handles=legend,loc="center",bbox_to_anchor=(.52,.465),ncol=2,frameon=False,fontsize=10)
        fig.savefig(ASSETS/f"31_删点前后_样本{sid}.png",dpi=200,facecolor="white");plt.close(fig)
    (DATA.parent/"删点前后参数移动.json").write_text(json.dumps(changes,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(changes,ensure_ascii=False))

if __name__=="__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--nested-gallery", action="store_true", help="仅生成按n切换的三法CDF与参数偏差组图")
    args = parser.parse_args()
    if args.nested_gallery:
        nested_gallery(read_rows())
    else:
        main()
