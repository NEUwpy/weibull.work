"""3.2的理论关系图；不新增抽样，不运行估计器。"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/"reviewbyhtml/方法对比-v1.0/assets"
plt.rcParams.update({"font.family":"Microsoft YaHei","font.size":12,"axes.spines.top":False,"axes.spines.right":False,"axes.unicode_minus":False})

def main():
    b=np.linspace(1.5,5,300)
    fig,ax=plt.subplots(figsize=(9,4.8))
    for n,c in [(7,"#D55E00"),(20,"#009E73"),(50,"#0072B2")]:
        ax.plot(b,np.exp(-n*.5**b),label=f"n = {n}",color=c,lw=2.2)
    ax.set(xlabel="形状参数 β",ylabel="P[最小观测 > γ + 0.5η]",ylim=(0,1),xlim=(1.5,5))
    ax.legend(frameon=False)
    fig.tight_layout();fig.savefig(OUT/"机制_近起点观测缺失概率.png",dpi=200);plt.close(fig)

    fig,axs=plt.subplots(1,2,figsize=(12,4.8),sharey=True)
    t=np.linspace(0,2400,1600)
    for ax,beta in zip(axs,[1.5,5]):
        lo,hi=500+1000*(-np.log(1-np.array([.1,.9])))**(1/beta)
        ax.axvspan(lo,hi,color="#eeeeee",zorder=0)
        for gamma,c,ls in [(200,"#0072B2","-"),(500,"#333333","--"),(800,"#D55E00","-")]:
            eta=1500-gamma
            bp=eta*beta/1000
            y=-np.expm1(-np.maximum((t-gamma)/eta,0)**bp)
            ax.plot(t,y,color=c,ls=ls,lw=2,label=f"({bp:g}, {eta:g}, {gamma:g})")
        ax.set(xlabel="寿命 t",xlim=(0,2400),ylim=(0,1))
        ax.legend(title=f"基准 β = {beta:g}；(β, η, γ)",frameon=False,fontsize=10,loc="upper left")
    axs[0].set_ylabel("累计概率 F(t)")
    fig.tight_layout();fig.savefig(OUT/"机制_参数补偿与分布相容.png",dpi=200);plt.close(fig)

if __name__=="__main__": main()
