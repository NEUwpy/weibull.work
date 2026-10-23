"""将删点前后的观测、拟合和实际参数移动放在同一幅图中；复用已保存的嵌套路径。"""
from pathlib import Path
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
METHODS=[("K–R","#CC79A7"),("MDM","#0072B2"),("LSE","#009E73")]
plt.rcParams.update({"font.family":"Microsoft YaHei","font.size":11,"axes.spines.top":False,"axes.spines.right":False,"axes.unicode_minus":False})

def cdf(t,b,e,g):return -np.expm1(-np.maximum((t-g)/e,0)**b)

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
    rows=pd.read_csv(DATA,float_precision="round_trip")
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

if __name__=="__main__":main()
