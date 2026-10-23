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

def main():
    rows=pd.read_csv(DATA,float_precision="round_trip")
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
