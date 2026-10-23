"""Section 3.1: information -> construction -> error on the existing path 474.

Restore only 15 diagnostic fits if the cache is absent. Formal Monte Carlo is
unchanged. The conditional recovery holds the seven observations/ranks fixed.
"""
from pathlib import Path
import hashlib
import json
import sys
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from scipy.special import gamma as gamma_function
from scipy.stats import weibull_min, binom
from scipy.integrate import trapezoid, quad

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
CORE=STUDY/"程序/计算实现-20261016"
LOCAL=STUDY/"结果呈现/分析数据/3.1机制链"
ASSETS=STUDY/"reviewbyhtml/方法对比-v1.0/assets"
sys.path.insert(0,str(CORE))
from studies.common.runner import run_method
from methods.lse import log_weibull_order_stat_means
from 绘制嵌套样本拟合 import nested_samples, NS
from 第三章机制候选图 import mdm_conditional, gradient, lse_values
from 绘制删点前后对照 import nested_gallery

SID=474
METHODS=[("mmle","MMLE",{},"#CC79A7"),("mdm","MDM",{"offset":.1},"#0072B2"),("lse","LSE",{},"#009E73")]
NC={50:"#0072B2",20:"#009E73",7:"#D55E00"}
PARAMETERS=["beta","eta","gamma"]
TRUTH=dict(beta=5.,eta=1000.,gamma=500.)


def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()


def dump(p,obj):
    p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+"\n",encoding="utf-8",newline="\n")


def save(fig,name):
    p=ASSETS/name;fig.savefig(p,dpi=220,facecolor="white");plt.close(fig);return p


def load():
    LOCAL.mkdir(parents=True,exist_ok=True)
    source=STUDY/"结果/W5,1000,500/估计结果/n50.csv"
    config=json.loads((STUDY/"程序/实验配置.json").read_text(encoding="utf-8"))
    for name,h in config["source_sha256"].items():assert sha(CORE/name)==h,name
    meta=json.loads((STUDY/"结果/数据说明.json").read_text(encoding="utf-8"))
    assert sha(source)==meta["file_sha256"][source.relative_to(STUDY/"结果").as_posix()]
    frame=pd.read_csv(source,float_precision="round_trip")
    xs={n:x for (_,n),x in nested_samples(frame,[SID]).items()}
    identity=dict(source=source.relative_to(STUDY).as_posix(),source_sha256=sha(source),source_id=SID,
                  seed_rule="20261023+source_id",sizes=NS,frozen_source_sha256=config["source_sha256"])
    cache=LOCAL/"路径估计.csv";stamp=LOCAL/"路径身份.json"
    if cache.exists():
        old=json.loads(stamp.read_text(encoding="utf-8"));assert old["identity"]==identity and old["cache_sha256"]==sha(cache)
        rows=pd.read_csv(cache,float_precision="round_trip")
    else:
        records=[]
        for n in NS:
            for mid,label,kwargs,_ in METHODS:
                r=run_method(mid,xs[n],variant=label,**kwargs);assert r["converged"]
                records.append(dict(source_id=SID,n=n,method=label,converged=True,beta=r["beta_hat"],eta=r["eta_hat"],gamma=r["gamma_hat"],observations=json.dumps(xs[n].tolist())))
        rows=pd.DataFrame(records);rows.to_csv(cache,index=False,encoding="utf-8-sig",float_format="%.17g")
        dump(stamp,dict(identity=identity,cache_sha256=sha(cache)))
    assert len(rows)==15
    estimates={};original=frame[frame["样本编号"].eq(SID)].iloc[0]
    labels={"MMLE":"MMLE(KR)","MDM":"MDM-0.1","LSE":"LSE"}
    for n in NS:
        for _,m,_,_ in METHODS:
            a=rows[rows.n.eq(n)&rows.method.eq(m)];assert len(a)==1;r=a.iloc[0]
            assert np.array_equal(json.loads(r.observations),xs[n])
            v=r[PARAMETERS].to_numpy(float);assert np.isfinite(v).all() and v[0]>0 and v[1]>0 and 0<=v[2]<=xs[n][0]
            if n==50:
                formal=original[[labels[m]+"_"+k+"估计" for k in ["形状","尺度","位置"]]].to_numpy(float)
                assert np.allclose(v,formal,rtol=1e-10,atol=1e-9)
            if m=="MMLE":
                assert v[2]==xs[n][0]
                y=xs[n][1:]-v[2];logs=np.log(y);weights=y**v[0]
                assert abs(1/v[0]+logs.mean()-np.dot(weights,logs)/weights.sum())<1e-7
                assert np.isclose(weights.mean()**(1/v[0]),v[1],rtol=1e-12)
            estimates[n,m]=dict(zip(PARAMETERS,v))
    assert xs[50][0]==xs[20][0] and xs[10][0]==xs[7][0]
    identity.update(cache_sha256=sha(cache),cache_scope="15 restored diagnostic fits on the existing nested path; not independent n7 Monte Carlo records")
    return source,rows,xs,estimates,identity


def recover(x,g,m):
    assert 0<=g<x[0];n=len(x)
    if m=="MDM":
        b,_=mdm_conditional(x,g);q=-np.log1p(-(np.arange(1,n+1)-.3)/(n+.4));a=(x-g)/q**(1/b)
        return dict(beta=float(b),eta=float(a.mean()),gamma=float(g),sd=float(a.std(ddof=1)))
    z=log_weibull_order_stat_means(n);y=np.log(x-g)
    b=float(np.dot(z-z.mean(),y-y.mean())/np.dot(z-z.mean(),z-z.mean()));a=float(y.mean()-b*z.mean())
    return dict(beta=1/b,eta=float(np.exp(a)),gamma=float(g),slope=b,intercept=a)


def coverage():
    """Reuse R00 figure 2's observations/minima/gap grammar with Study04 data.

    Three columns use archived samples, not a newly generated experiment. The
    last column uses the same analytic minimum density as R00's figure script.
    """
    fig,axs=plt.subplots(1,4,figsize=(16,7),gridspec_kw={"width_ratios":[1,1,1,1.06]})
    fig.subplots_adjust(left=.055,right=.99,bottom=.16,top=.84,wspace=.25)
    meta=json.loads((STUDY/"结果/数据说明.json").read_text(encoding="utf-8"))
    records=[];all_max=[]
    grid=np.linspace(500,3000,5001)
    for j,n in enumerate([50,20,7]):
        source=STUDY/f"结果/W5,1000,500/估计结果/n{n}.csv"
        digest=sha(source);assert digest==meta["file_sha256"][source.relative_to(STUDY/"结果").as_posix()]
        frame=pd.read_csv(source,float_precision="round_trip").sort_values("样本编号")
        x=np.sort(frame[[f"观测值{i}" for i in range(1,n+1)]].to_numpy(float),axis=1)
        assert x.shape==(1200,n) and np.isfinite(x).all() and (x>500).all()
        assert np.array_equal(frame["MMLE(KR)_位置估计"].to_numpy(float),x[:,0])
        shown=x[:50];order=np.argsort(shown[:,0],kind="stable");shown=shown[order]
        ax=axs[j];ranks=np.arange(1,51);xx=shown[:,1:].ravel();yy=np.repeat(ranks,n-1)
        ax.hlines(ranks,500,shown[:,0],color="#cbd4da",lw=.9,zorder=1)
        observations=ax.scatter(xx,yy,s=8,c="#426981",linewidths=0,zorder=3)
        minima=ax.scatter(shown[:,0],ranks,s=19,c="#C27F45",linewidths=0,zorder=4)
        assert np.array_equal(observations.get_offsets(),np.column_stack([xx,yy]))
        assert np.array_equal(minima.get_offsets()[:,0],shown[:,0])
        ax.set(ylim=(51,0),yticks=[1,25,50],title=f"({chr(97+j)}) $n={n}$",xlabel="寿命")
        ax.tick_params(labelleft=j==0);all_max.append(shown.max())
        # Same expression as Research00/报告1/20261010-导入样本起点图.py.
        d=np.maximum((grid-500)/1000,0)
        density=n*5/1000*d**4*np.exp(-n*d**5)
        assert np.allclose(density,weibull_min.pdf(grid,5,loc=500,scale=1000*n**(-.2)),atol=1e-14)
        assert abs(trapezoid(density,grid)-1)<1e-7
        axs[3].plot(grid,density,c=NC[n],ls={50:"-",20:"--",7:":"}[n],lw=2,label=f"$n={n}$")
        records.append(dict(n=n,source=source.relative_to(STUDY).as_posix(),source_sha256=digest,
                            shown_sample_ids=frame.iloc[:50].iloc[order]["样本编号"].astype(int).tolist(),
                            shown_observations_sha256=hashlib.sha256(shown.tobytes()).hexdigest(),
                            groups_shown=50,observations_shown=50*n,
                            theoretical_mean_minimum_distance=float(1000*n**(-.2)*gamma_function(1.2)),
                            theoretical_probability_no_observation_in_500_1000=float(np.exp(-n*.5**5)),
                            empirical_probability_no_observation_in_500_1000=float(np.mean(x[:,0]>1000)),
                            empirical_mean_minimum_distance=float(np.mean(x[:,0]-500)),
                            empirical_cdf_sd_at_population_median=float(np.sqrt(.25/n)),
                            mmle_gamma_is_minimum_all_1200=True))
        assert sha(source)==digest
    right=max(2200,float(np.ceil(max(all_max)/100)*100))
    for ax in axs[:3]:ax.set(xlim=(450,right),xticks=[500,1000,1500,2000]);ax.axvline(500,c="#555",ls="--",lw=1)
    axs[0].set_ylabel("样本组（按最小值排序）")
    axs[3].axvline(500,c="#555",ls="--",lw=1)
    axs[3].set(xlim=(450,1700),ylim=(0,None),xticks=[500,1000,1500],title="(d)",xlabel=r"$x_{(1)}$",ylabel="概率密度")
    axs[3].ticklabel_format(axis="y",style="sci",scilimits=(0,0),useMathText=True);axs[3].legend(frameon=False,loc="upper right",fontsize=11)
    handles=[Line2D([],[],marker="o",ls="",c="#426981",ms=4,label="观测"),Line2D([],[],marker="o",ls="",c="#C27F45",ms=5,label="最小观测"),Line2D([],[],c="#cbd4da",lw=2,label="起点至最小观测"),Line2D([],[],c="#555",ls="--",label=r"$\gamma_{\mathrm{true}}=500$")]
    fig.legend(handles=handles,loc="upper center",bbox_to_anchor=(.5,.965),ncol=4,frameon=False)
    assert all(records[i]["theoretical_mean_minimum_distance"]<records[i+1]["theoretical_mean_minimum_distance"] for i in [0,1])
    return save(fig,"31H_n减小与下端覆盖.png"),records


def information(xs):
    fig,axs=plt.subplots(1,3,figsize=(16,7),gridspec_kw={"width_ratios":[2.9,1,1]},sharey=True)
    fig.subplots_adjust(left=.065,right=.98,bottom=.17,top=.92,wspace=.24);records=[]
    for j,n in enumerate(NS):
        x=xs[n];k=int(np.argmax(np.diff(x)))
        axs[0].scatter(xs[50],np.full(50,j),marker="|",c="#d4dadd",s=170,linewidths=1)
        axs[0].scatter(x,np.full(n,j),marker="|",c="#26343d",s=230,linewidths=1.5)
        axs[0].plot([x[k],x[k+1]],[j+.16,j+.16],c="#D55E00",lw=3);axs[0].scatter(x[0],j,s=40,c="#0072B2",zorder=5)
        records.append(dict(n=n,sample_sha256=hashlib.sha256(x.tobytes()).hexdigest(),minimum=float(x[0]),minimum_minus_true_location=float(x[0]-500),maximum=float(x[-1]),max_adjacent_gap=float(np.diff(x).max()),count_below_1200=int((x<=1200).sum())))
    axs[0].axvline(500,c="#777",lw=1,ls="--")
    axs[0].set(xlim=(450,2050),xticks=[500,1000,1500,2000],yticks=range(5),yticklabels=[f"n = {n}" for n in NS],xlabel="寿命",title="(a)");axs[0].set_ylim(4.45,-.45)
    for ax,key,c,t in [(axs[1],"minimum_minus_true_location","#0072B2","(b)"),(axs[2],"max_adjacent_gap","#D55E00","(c)")]:
        values=[r[key] for r in records];ax.plot(values,range(5),"o-",c=c,ms=6,lw=1.6)
        for j,v in enumerate(values):ax.annotate(f"{v:.1f}",(v,j),xytext=(5,8),textcoords="offset points",fontsize=11)
        ax.set(title=t,xlim=(0,max(values)*1.25));ax.grid(axis="x",alpha=.15)
    axs[1].set_xlabel(r"$x_{(1)}-\gamma_{true}$");axs[2].set_xlabel("最大相邻间隔")
    return save(fig,"31C_样本信息变化_样本474.png"),records


def information_inputs(xs):
    fig,axs=plt.subplots(1,2,figsize=(16,7));fig.subplots_adjust(left=.07,right=.985,bottom=.20,top=.88,wspace=.23)
    records=[];first={}
    for n in [50,20,7]:
        x=xs[n];p=(np.arange(1,n+1)-.3)/(n+.4);q=-np.log1p(-p)
        a=(x-500)/q**.2;z=log_weibull_order_stat_means(n);y=np.log(x-500)
        c=NC[n];marker={50:"o",20:"s",7:"^"}[n]
        axs[0].scatter(p,a,c=c,marker=marker,s=26,alpha=.8)
        axs[1].scatter(z,y,c=c,marker=marker,s=26,alpha=.8)
        first[n]=(p[0],a[0],z[0],y[0])
        records.append(dict(n=n,minimum=float(x[0]),mdm_first_plotting_position=float(p[0]),mdm_first_pseudo_scale_at_true_beta_gamma=float(a[0]),lse_first_reference=float(z[0]),lse_first_log_distance_at_true_gamma=float(y[0])))
    for ax,ix,iy in [(axs[0],0,1),(axs[1],2,3)]:
        for n in [50,20]:ax.scatter(first[n][ix],first[n][iy],s=90,facecolors="none",edgecolors="black",linewidths=1,zorder=5)
        ax.annotate("",xy=(first[20][ix],first[20][iy]),xytext=(first[50][ix],first[50][iy]),arrowprops=dict(arrowstyle="->",color="black",lw=1.4),zorder=6)
    assert first[50][3]==first[20][3] and first[50][0]!=first[20][0] and first[50][2]!=first[20][2]
    axs[0].axhline(1000,c="#777",ls=":",lw=1)
    axs[0].set(xlabel=r"$p_i$",ylabel="伪尺度",title="(a) MDM")
    axs[1].set(xlabel=r"$z_i$",ylabel=r"$\ln(x_{(i)}-500)$",title="(b) LSE")
    fig.legend(handles=[Line2D([],[],c=NC[n],ls="",marker={50:"o",20:"s",7:"^"}[n],label=f"n = {n}") for n in [50,20,7]],loc="lower center",bbox_to_anchor=(.5,.025),ncol=3,frameon=False)
    return save(fig,"31G_样本进入构造_样本474.png"),records


def criteria(xs,est):
    fig,axs=plt.subplots(1,3,figsize=(16,7),gridspec_kw={"width_ratios":[.85,1.25,1.25]});fig.subplots_adjust(left=.07,right=.985,bottom=.20,top=.88,wspace=.34);records=[]
    for j,n in enumerate([50,20,7]):
        x=xs[n];c=NC[n];axs[0].plot([500,x[0]],[j,j],c=c,lw=2);axs[0].scatter(x[0],j,c=c,s=50)
        grid=np.unique(np.r_[np.linspace(0,x[0]*.995,360),est[n,"MDM"]["gamma"],est[n,"LSE"]["gamma"]])
        ls={50:"-",20:"--",7:":"}[n]
        axs[1].plot(grid,[gradient(x,g) for g in grid],c=c,lw=1.8,ls=ls)
        gm=est[n,"MDM"]["gamma"];grad=float(gradient(x,gm));assert abs(grad-.1)<2e-5
        axs[1].scatter(gm,grad,c=c,s=45,zorder=4)
        gl=est[n,"LSE"]["gamma"];_,loss=lse_values(x,grid);chosen=float(lse_values(x,[gl])[1][0]);assert chosen<=loss.min()+1e-8
        axs[2].plot(grid,loss,c=c,lw=1.8,ls=ls);axs[2].scatter(gl,chosen,c=c,s=45,zorder=4)
        z=log_weibull_order_stat_means(n);y=np.log(x-gl);r=recover(x,gl,"LSE");residual=y-(r["intercept"]+r["slope"]*z)
        f=float(np.var(y,ddof=1)/(np.sum(residual**2)/(n-2)));assert np.isclose(f,(n-2)/(n-1)/chosen,rtol=1e-10)
        records.append(dict(n=n,minimum=float(x[0]),mdm_gamma=gm,mdm_gradient=grad,lse_gamma=gl,lse_one_minus_r2=chosen,lse_F=f))
    for ax in axs:ax.axvline(500,c="#777",ls="--",lw=1);ax.set_xlabel(r"$\gamma$");ax.set_xlim(0,1280)
    axs[0].set(yticks=[0,1,2],yticklabels=["n = 50","n = 20","n = 7"],ylim=(2.5,-.5),title="(a) MMLE")
    axs[1].axhline(.1,c="#777",ls=":",lw=1.2);axs[1].set(ylim=(-.15,.4),ylabel="最小伪尺度标准差的梯度",title="(b) MDM")
    axs[2].set(ylim=(0,.28),ylabel=r"$1-R^2$",title="(c) LSE")
    fig.legend(handles=[Line2D([],[],color=NC[n],ls={50:"-",20:"--",7:":"}[n],label=f"n = {n}") for n in [50,20,7]]+[Line2D([],[],ls="--",color="#777",label=r"$\gamma_{true}=500$")],loc="lower center",bbox_to_anchor=(.5,.02),ncol=4,frameon=False)
    return save(fig,"31D_定位判据响应_样本474.png"),records


def errors(est):
    fig,axs=plt.subplots(1,3,figsize=(16,7));fig.subplots_adjust(left=.07,right=.985,bottom=.20,top=.88,wspace=.25);records=[]
    for ax,k,label in zip(axs,PARAMETERS,[r"$\hat\beta-\beta_{true}$",r"$\hat\eta-\eta_{true}$",r"$\hat\gamma-\gamma_{true}$"]):
        ax.axhline(0,c="#777",ls="--",lw=1)
        for _,m,_,c in METHODS:
            v=[est[n,m][k]-TRUTH[k] for n in NS];ax.plot(range(5),v,marker={"MMLE":"o","MDM":"s","LSE":"^"}[m],ls={"MMLE":":","MDM":"-","LSE":"--"}[m],c=c,lw=1.9,ms=6)
            records.extend(dict(n=n,method=m,parameter=k,estimate=est[n,m][k],signed_error=float(y)) for n,y in zip(NS,v))
        ax.set(xticks=range(5),xticklabels=NS,xlabel="样本量",ylabel=label);ax.grid(alpha=.12)
    fig.legend(handles=[Line2D([],[],c=c,marker={"MMLE":"o","MDM":"s","LSE":"^"}[m],ls={"MMLE":":","MDM":"-","LSE":"--"}[m],label=m) for _,m,_,c in METHODS],loc="lower center",bbox_to_anchor=(.5,.025),ncol=3,frameon=False)
    return save(fig,"31E_单次误差响应_样本474.png"),records


def conditional(xs,est):
    x=xs[7];q=-np.log1p(-(np.arange(1,8)-.3)/7.4);z=log_weibull_order_stat_means(7);outputs=[]
    for m in ["MDM","LSE"]:
        for name,n in [("gamma_from_n50",50),("gamma_from_n7",7)]:
            r=recover(x,est[n,m]["gamma"],m);r.update(method=m,location_source=name,n_fixed=7);outputs.append(r)
        assert np.allclose([r["beta"],r["eta"]],[est[7,m]["beta"],est[7,m]["eta"]],rtol=1e-10)
    fig,axs=plt.subplots(1,3,figsize=(16,7),gridspec_kw={"width_ratios":[1.15,1.15,.8]});fig.subplots_adjust(left=.065,right=.985,bottom=.20,top=.88,wspace=.30)
    colors=["#0072B2","#D55E00"];bs=np.linspace(.9,8,600)
    for r,c,ls in zip([r for r in outputs if r["method"]=="MDM"],colors,["-","--"]):
        sd=np.array([np.std((x-r["gamma"])/q**(1/b),ddof=1) for b in bs]);axs[0].plot(bs,sd,c=c,lw=1.8,ls=ls);axs[0].scatter(r["beta"],r["sd"],c=c,s=48,zorder=4)
    axs[0].set(xlim=(.9,8),ylim=(0,300),xlabel=r"$\beta$",ylabel="伪尺度标准差",title="(a) MDM")
    for r,c,ls in zip([r for r in outputs if r["method"]=="LSE"],colors,["-","--"]):
        y=np.log(x-r["gamma"]);axs[1].scatter(z,y,c=c,s=27);axs[1].plot(z,r["intercept"]+r["slope"]*z,c=c,lw=1.8,ls=ls)
    axs[1].set(xlabel=r"$z_i$",ylabel=r"$\ln(x_{(i)}-\gamma)$",title="(b) LSE")
    for j,m in enumerate(["MDM","LSE"]):
        a=[r for r in outputs if r["method"]==m];axs[2].plot([j,j],[r["eta"] for r in a],c="#7e898e",lw=1.3)
        for r,c in zip(a,colors):
            axs[2].scatter(j,r["eta"],c=c,s=50,zorder=4);axs[2].annotate(f"{r['eta']:.1f}",(j,r["eta"]),xytext=(8,0),textcoords="offset points",va="center",fontsize=11)
    axs[2].set(xlim=(-.35,1.55),xticks=[0,1],xticklabels=["MDM","LSE"],ylabel=r"$\eta(\gamma)$",title="(c)");axs[2].grid(axis="y",alpha=.15)
    fig.legend(handles=[Line2D([],[],c=c,ls=ls,label=t) for c,ls,t in zip(colors,["-","--"],["7点固定样本：代入50点时的位置","7点固定样本：代入7点时的位置"])],loc="lower center",bbox_to_anchor=(.5,.025),ncol=2,frameon=False)
    return save(fig,"31F_固定七点的位置条件对照_样本474.png"),outputs


def minimum_distribution_link(xs,conditional_outputs):
    """One figure joins lower-tail mass, conditional shape, and no-hit chance.

    Both distributions are LSE conditional recoveries on the same seven points.
    The n-curve is a fresh-draw probability under the FIXED blue candidate and
    fixed threshold m, not a fitted-model p-value or an estimation objective.
    """
    x=xs[7];m=float(x[0]);grid=np.unique(np.r_[np.linspace(450,2200,2001),m])
    selected=[r for r in conditional_outputs if r["method"]=="LSE"]
    assert len(selected)==2
    fig,axs=plt.subplots(1,3,figsize=(16,7),gridspec_kw={"width_ratios":[1.1,1.1,1]})
    fig.subplots_adjust(left=.065,right=.985,bottom=.21,top=.87,wspace=.32)
    records=[]
    for r,c,ls in zip(selected,["#0072B2","#D55E00"],["-","--"]):
        dist=weibull_min(r["beta"],loc=r["gamma"],scale=r["eta"])
        pdf=dist.pdf(grid);cdf=dist.cdf(grid);q=float(dist.cdf(m))
        area,error=quad(dist.pdf,r["gamma"],m,epsabs=1e-12)
        assert abs(area-q)<1e-10 and error<1e-9
        axs[0].plot(grid,pdf,c=c,ls=ls,lw=2)
        axs[1].plot(grid,cdf,c=c,ls=ls,lw=2)
        if not records:
            low=np.linspace(r["gamma"],m,500)
            axs[0].fill_between(low,0,dist.pdf(low),color=c,alpha=.23,linewidth=0)
            axs[1].hlines(q,450,m,color=c,ls=":",lw=1.2)
            axs[1].scatter(m,q,c=c,s=44,zorder=5)
            axs[1].annotate(r"$q$",(m,q),xytext=(10,5),textcoords="offset points",color=c,fontsize=14)
        records.append(dict(location_source=r["location_source"],gamma=r["gamma"],beta=r["beta"],eta=r["eta"],
                            cdf_at_minimum=q,pdf_area_below_minimum=area,
                            minimum_distance=float(m-r["gamma"]),maximum_distance=float(x[-1]-r["gamma"]),
                            maximum_to_minimum_distance_ratio=float((x[-1]-r["gamma"])/(m-r["gamma"]))))
    for ax in axs[:2]:
        ax.axvline(m,c="#333",ls=":",lw=1.3)
        ax.scatter(x,np.zeros(len(x)),marker="|",s=120,c="#222",clip_on=False,zorder=6)
        ax.set(xlim=(450,2200),xticks=[500,1000,1500,2000],xlabel="寿命")
    axs[0].set(title="(a) PDF",ylabel="概率密度",ylim=(0,None))
    axs[0].ticklabel_format(axis="y",style="sci",scilimits=(0,0),useMathText=True)
    axs[1].set(title="(b) CDF",ylabel="累计概率",ylim=(0,1))
    q=records[0]["cdf_at_minimum"];ns=np.arange(1,51);prob=np.exp(ns*np.log1p(-q))
    assert np.allclose(prob,binom.pmf(0,ns,q),rtol=1e-12,atol=1e-15)
    axs[2].plot(ns,prob,c="#0072B2",lw=2)
    probabilities=[]
    for n in [7,20,50]:
        p=float(np.exp(n*np.log1p(-q)));axs[2].scatter(n,p,c="#0072B2",s=43,zorder=4)
        axs[2].annotate(f"{p*100:.2f}%",(n,p),xytext=(-40,12) if n==50 else (6,8),textcoords="offset points",fontsize=11)
        probabilities.append(dict(n=n,no_observation_below_m_probability=p))
    axs[2].set(title="(c)",xlabel=r"$n$",ylabel=r"$P_{\theta_A}(X_{(1)}\geq m)$",xlim=(0,54),ylim=(0,1),xticks=[7,20,50])
    fig.legend(handles=[Line2D([],[],c=c,ls=ls,lw=2,label=rf"$\gamma={r['gamma']:.1f}$") for r,c,ls in zip(selected,["#0072B2","#D55E00"],["-","--"])]+[Line2D([],[],c="#333",ls=":",label=rf"$m={m:.1f}$")],loc="lower center",bbox_to_anchor=(.5,.025),ncol=3,frameon=False)
    record=dict(fixed_observations_n=7,minimum=m,maximum=float(x[-1]),candidates=records,
                fresh_draw_probabilities_under_fixed_blue_candidate=probabilities,
                zero_count_formula="P_theta(min(X_1,...,X_n)>=m) = (1-F_theta(m))**n, for fixed theta and m",
                minimum_density_formula="g_theta,n(m) = n*f_theta(m)*(1-F_theta(m))**(n-1)",
                scope="Conditional curves on the same seven observations. The n-curve holds blue parameters and threshold fixed for hypothetical new iid draws; not a p-value for the fitted data, not the full minimum density or any method's objective.")
    return save(fig,"31I_最小观测与整条分布.png"),record


def main():
    source,rows,xs,est,identity=load();before=sha(source)
    plt.rcParams.update({"font.family":["Times New Roman","Microsoft YaHei"],"font.size":13,"mathtext.fontset":"custom","mathtext.rm":"Times New Roman","mathtext.it":"Times New Roman:italic","mathtext.bf":"Times New Roman:bold","axes.spines.top":False,"axes.spines.right":False,"axes.unicode_minus":False})
    f0,population_coverage=coverage();f1,features=information(xs);f5,inputs=information_inputs(xs);f2,criterion=criteria(xs,est);f3,errs=errors(est);f4,cond=conditional(xs,est)
    f6,distribution_link=minimum_distribution_link(xs,cond)
    nested_gallery(rows,source_id=SID,source_path=LOCAL/"路径估计.csv")
    images=[f0,f6,f1,f5,f2,f3,f4]+[ASSETS/f"31_嵌套删点_样本474_n{n}.png" for n in NS]
    assert sha(source)==before
    result=dict(identity=identity,population_coverage=population_coverage,minimum_to_distribution=distribution_link,coverage_figure_grammar_source="Research/00-方法对比/交付/程序/报告1/20261010-导入样本起点图.py; adapted to Study04 n=50,20,7, with the same analytic minimum density; source not executed or changed.",features=features,input_coordinates_at_true_parameters=inputs,estimates=[dict(n=n,method=m,**est[n,m]) for n in NS for _,m,_,_ in METHODS],actual_criteria=criterion,signed_errors=errs,conditional_seven_point_recovery=cond,
        conditional_scope="Same seven observations and n=7 reference coordinates; gamma alone changes. Old-gamma conditional results are NOT original n50 estimates.",
        checks=dict(pdf_area_equals_cdf_at_minimum=True,no_hit_probability_matches_binomial=True,archived_coverage_samples=True,minimum_density_matches_scipy_and_integrates_to_one=True,mmle_gamma_minimum_all_3600_records=True,nested_subsets=True,same_observations_across_methods=True,formal_n50_estimates_match=True,shared_observation_reference_changes=True,mmle_positive_distance_likelihood=True,profile_gradient_target=True,lse_F_r2_identity=True,conditional_support=True,conditional_recovery_matches_n7=True,formal_source_unchanged=True),
        scope="Archived n=50/20/7 samples and analytic minimum distributions at beta=5; one nested path 474 and conditional recovery explain concrete responses, not all methods or total RMSE differences; no independent Monte Carlo added.",program_sha256=sha(Path(__file__)),images={p.relative_to(STUDY).as_posix():sha(p) for p in images})
    dump(HERE/"3.1机制链核验.json",result)
    print(json.dumps(dict(features=features,conditional=cond,checks=result["checks"]),ensure_ascii=False,indent=2),flush=True)


if __name__=="__main__":main()
