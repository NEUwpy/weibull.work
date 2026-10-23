"""第三章候选：固定β的判据路径、真位置条件对照和机制关系图。"""
from pathlib import Path
import sys,json,hashlib
import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

STUDY=Path(__file__).resolve().parents[2]
DATA=STUDY/"结果呈现/分析数据"
OUT=STUDY/"reviewbyhtml/方法对比-v1.0/assets"
CORE=STUDY/"程序/计算实现-20261016"
sys.path.insert(0,str(CORE))
from methods.lse import log_weibull_order_stat_means
COLORS={50:"#0072B2",20:"#009E73",7:"#D55E00"}
plt.rcParams.update({"font.family":"Microsoft YaHei","font.size":11,"axes.spines.top":False,"axes.spines.right":False,"axes.unicode_minus":False})

def mdm_conditional(x,gamma):
    p=(np.arange(1,len(x)+1)-.3)/(len(x)+.4)
    q=-np.log1p(-p)
    res=minimize_scalar(lambda beta:np.std((x-gamma)/q**(1/beta),ddof=1),bounds=(.1,15),method="bounded")
    return res.x,res.fun

def gradient(x,g):
    scale=max(float(x[0]),1.);h=scale*1e-5
    if g<=h:
        h=min(h,(x[0]-g)*.25)
        return (mdm_conditional(x,g+h)[1]-mdm_conditional(x,g)[1])/h
    h=min(h,g*.25,(x[0]-g)*.25)
    return (mdm_conditional(x,g+h)[1]-mdm_conditional(x,g-h)[1])/(2*h)

def lse_values(x,gammas):
    z=log_weibull_order_stat_means(len(x));z=z-z.mean()
    y=np.log(x[None,:]-np.array(gammas)[:,None]);yc=y-y.mean(axis=1,keepdims=True)
    slope=yc@z/(z@z)
    rho2=(yc@z)**2/((z@z)*np.sum(yc**2,axis=1))
    return 1/slope,1-rho2

def criterion_figures():
    rows=pd.read_csv(DATA/"嵌套样本拟合.csv")
    records=[]
    for sid in [1055,474]:
        fig,axs=plt.subplots(1,3,figsize=(13,4.6),gridspec_kw={"width_ratios":[.9,1.2,1.2]})
        fig.subplots_adjust(left=.075,right=.985,bottom=.17,top=.80,wspace=.38)
        for j,n in enumerate([50,20,7]):
            d=rows[(rows.source_id==sid)&(rows.n==n)]
            x=np.array(json.loads(d.iloc[0].observations))
            grid=np.linspace(0,float(x[0])*.995,210)
            c=COLORS[n]
            axs[0].plot([500,x[0]],[j,j],color=c,lw=2)
            axs[0].scatter(x[0],j,c=c,s=42)
            grad=np.array([gradient(x,g) for g in grid]);axs[1].plot(grid,grad,c=c,label=f"n = {n}",lw=1.8)
            r=d[d.method.eq("MDM")].iloc[0]
            axs[1].scatter(r.gamma,gradient(x,r.gamma),c=c,s=38)
            _,loss=lse_values(x,grid);axs[2].plot(grid,loss,c=c,label=f"n = {n}",lw=1.8)
            r=d[d.method.eq("LSE")].iloc[0]
            axs[2].scatter(r.gamma,lse_values(x,[r.gamma])[1][0],c=c,s=38)
            records.append(dict(source_id=sid,n=n,minimum=float(x[0]),mdm_gamma=float(d[d.method.eq("MDM")].iloc[0].gamma),lse_gamma=float(r.gamma)))
        for ax in axs:
            ax.axvline(500,c="#666666",ls="--",lw=1)
            ax.set_xlabel("候选位置 γ")
        axs[0].set(yticks=[0,1,2],yticklabels=["n = 50","n = 20","n = 7"],ylim=(2.5,-.5),title="K–R：直接取最小值")
        axs[1].axhline(.1,c="#777777",ls=":",lw=1.5)
        axs[1].set(ylim=(-.3,.5),ylabel="伪尺度标准差梯度",title="MDM：取阈值交点")
        axs[2].set(ylabel="1 − R²（越低越好）",title="LSE：取最佳匹配位置")
        fig.legend(*axs[1].get_legend_handles_labels(),loc="upper center",ncol=3,frameon=False)
        fig.savefig(OUT/f"31A_固定形状定位判据_样本{sid}.png",dpi=200,facecolor="white");plt.close(fig)
    return records

def fixed_position():
    cache=DATA/"第三章固定真位置对照.csv"
    sources={}
    if cache.exists(): df=pd.read_csv(cache)
    else:
        records=[]
        for n in [50,20,15,10,7]:
            p=STUDY/f"结果/W5,1000,500/估计结果/n{n}.csv"
            d=pd.read_csv(p,float_precision="round_trip")
            x=d[[f"观测值{i}" for i in range(1,n+1)]].to_numpy(float)
            for method,column in [("MDM","MDM-0.1"),("LSE","LSE")]:
                if method=="MDM": cond=np.array([mdm_conditional(a,500)[0] for a in x])
                else:
                    z=log_weibull_order_stat_means(n);z=z-z.mean()
                    y=np.log(x-500);cond=(z@z)/((y-y.mean(axis=1,keepdims=True))@z)
                full=d[column+"_形状估计"].to_numpy(float)
                assert d[column+"_状态"].eq("success").all()
                for rid,(a,c) in enumerate(zip(full,cond)):
                    records.append(dict(n=n,method=method,repeat_id=rid,full_shape=a,fixed_gamma_shape=c))
            print("fixed position",n,flush=True)
        df=pd.DataFrame(records);df.to_csv(cache,index=False,encoding="utf-8-sig")
    summary=[]
    fig,axs=plt.subplots(1,2,figsize=(11,4.6),sharex=True,sharey=True)
    fig.subplots_adjust(top=.82,bottom=.17,wspace=.15)
    for ax,method in zip(axs,["MDM","LSE"]):
        d=df[df.method.eq(method)];ns=[50,20,15,10,7]
        means={}
        for k,c,marker,label in [("fixed_gamma_shape","#0072B2","o","固定真位置，只估形状"),("full_shape","#D55E00","s","按原方法估位置与形状")]:
            vals=[d[d.n.eq(n)][k].mean() for n in ns];means[k]=vals
            ax.plot(range(5),vals,marker=marker,c=c,lw=1.8,label=label)
        for j,n in enumerate(ns):
            ax.annotate("",(j,means["full_shape"][j]),(j,means["fixed_gamma_shape"][j]),arrowprops=dict(arrowstyle="->",color="#888888",lw=1))
            summary.append(dict(method=method,n=n,fixed_mean=means["fixed_gamma_shape"][j],full_mean=means["full_shape"][j]))
        ax.axhline(5,c="#555555",ls="--",lw=1.2,label="真实形状 β = 5")
        ax.set(xticks=range(5),xticklabels=ns,xlabel="样本量 n",title=method)
    axs[0].set_ylabel("形状估计均值")
    fig.legend(*axs[0].get_legend_handles_labels(),ncol=3,loc="upper center",frameon=False,fontsize=10)
    fig.savefig(OUT/"31B_固定真位置与原定位.png",dpi=200,facecolor="white");plt.close(fig)
    for n in [50,20,15,10,7]:
        p=STUDY/f"结果/W5,1000,500/估计结果/n{n}.csv";sources[str(p.relative_to(STUDY))]=hashlib.sha256(p.read_bytes()).hexdigest()
    return summary,sources

def box(ax,x,y,w,h,text,color="#eaf1f5",fontsize=12):
    ax.add_patch(FancyBboxPatch((x,y),w,h,boxstyle="round,pad=.012,rounding_size=.015",fc=color,ec="#b7c5cc",lw=1))
    ax.text(x+w/2,y+h/2,text,ha="center",va="center",fontsize=fontsize)

def arrow(ax,start,end):ax.annotate("",xy=end,xytext=start,arrowprops=dict(arrowstyle="->",color="#58666e",lw=1.6))

def route_figure():
    fig,ax=plt.subplots(figsize=(12,5.5));ax.set(xlim=(0,1),ylim=(0,1));ax.axis("off")
    box(ax,.04,.76,.9,.15,"n 减小 → 观测覆盖与局部间距更容易受少数点影响",fontsize=14)
    rows=[(.53,"K–R","最小值直接定位","下端空缺直接进入位置误差"),(.30,"MDM","伪尺度梯度与固定阈值相交","间距改变 → 交点改变 → 参数联动"),(.07,"LSE","移动位置，比较线性匹配","间距改变 → 最优位置改变 → 斜率改变")]
    for y,m,rule,consequence in rows:
        box(ax,.04,y,.15,.14,m);box(ax,.25,y,.32,.14,rule);box(ax,.64,y,.30,.14,consequence,fontsize=11)
        arrow(ax,(.19,y+.07),(.25,y+.07));arrow(ax,(.57,y+.07),(.64,y+.07))
    fig.tight_layout();fig.savefig(OUT/"31C_样本到定位的分路.png",dpi=200,facecolor="white");plt.close(fig)

def boundary_figure():
    source=STUDY/"结果/W5,1000,500/估计结果/n7.csv"
    d=pd.read_csv(source,float_precision="round_trip")
    pool=[]
    for rid in np.flatnonzero(d["LSE_位置估计"].eq(0)):
        x=d.iloc[rid][[f"观测值{i}" for i in range(1,8)]].to_numpy(float)
        loss=lse_values(x,[-600,0])[1]
        pool.append((int(rid),float(loss[1]-loss[0])))
    median=float(np.median([v for _,v in pool]))
    boundary=min(pool,key=lambda item:(abs(item[1]-median),item[0]))[0]
    ids=[0,boundary]
    fig,axs=plt.subplots(1,2,figsize=(11.5,4.6))
    fig.subplots_adjust(left=.08,right=.98,bottom=.17,top=.84,wspace=.25)
    details=[]
    for ax,rid,label in zip(axs,ids,["内部偏移","零边界"]):
        row=d.iloc[rid];x=row[[f"观测值{i}" for i in range(1,8)]].to_numpy(float)
        upper=float(x[0])*.998 if rid==0 else 650.
        grid=np.linspace(-600,upper,1000)
        shape,loss=lse_values(x,grid)
        ax.axvspan(-600,0,color="#eeeeee")
        ax.plot(grid,loss,c="#0072B2",lw=2)
        gamma=float(row["LSE_位置估计"])
        y=lse_values(x,[gamma])[1][0]
        ax.scatter(gamma,y,c="#D55E00",s=55,zorder=5,label="原估计位置")
        ax.axvline(500,c="#666666",ls="--",lw=1.2,label="真位置")
        ax.axvline(0,c="#999999",lw=.8)
        ax.set(xlabel="候选位置 γ",ylabel="1 − R²（越低越好）",title=f"样本 {rid}：{label}",xlim=(-600,upper))
        ax.legend(frameon=False,fontsize=10)
        details.append(dict(sample_id=rid,parameters=[float(row[f"LSE_{k}估计"]) for k in ["形状","尺度","位置"]],criterion_true=float(lse_values(x,[500])[1][0]),criterion_returned=float(y),criterion_negative=float(lse_values(x,[-600])[1][0])))
    fig.savefig(OUT/"32B_内部偏移与边界选择.png",dpi=200,facecolor="white");plt.close(fig)
    return details

def high_shape_routes():
    fig,ax=plt.subplots(figsize=(12,6));ax.set(xlim=(0,1),ylim=(0,1));ax.axis("off")
    box(ax,.05,.78,.9,.14,"β 较大、样本较少 → 最小观测远离起点 → 中部参数组合难区分",fontsize=13)
    box(ax,.05,.46,.41,.19,"定位判据在内部选中偏右位置\n\n位置增大 → 对数距离比例改变",color="#eaf1f5",fontsize=12)
    box(ax,.54,.46,.41,.19,"最佳匹配倾向于更低位置\n\n允许范围要求 γ ≥ 0",color="#f5eee6",fontsize=12)
    arrow(ax,(.32,.78),(.25,.65));arrow(ax,(.68,.78),(.75,.65))
    box(ax,.05,.12,.41,.19,"参数联合偏移\n\n典型例：γ 偏大，β、η 偏小",fontsize=12)
    box(ax,.54,.12,.41,.19,"零边界聚集\n\n不同样本都可返回 γ = 0",color="#f5eee6",fontsize=12)
    arrow(ax,(.25,.46),(.25,.31));arrow(ax,(.75,.46),(.75,.31))
    fig.tight_layout();fig.savefig(OUT/"32C_偏移与边界两条路径.png",dpi=200,facecolor="white");plt.close(fig)


def main():
    paths=[STUDY/f"结果/W5,1000,500/估计结果/n{n}.csv" for n in [50,20,15,10,7]]
    before={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    criterion=criterion_figures();summary,sources=fixed_position();route_figure();boundary=boundary_figure();high_shape_routes()
    assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==h for p,h in before.items())
    (DATA/"第三章机制候选核验.json").write_text(json.dumps(dict(criterion=criterion,fixed_position=summary,boundary=boundary,sources=sources,scope="固定β=5、η=1000、γ=500；固定真位置仅为诊断，不是可部署方法；两条定位路径不代替重复抽样结论。"),ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(summary,ensure_ascii=False),flush=True)

if __name__=="__main__":main()
