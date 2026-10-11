"""Simplify reference overlays in the current paired mechanism figures.

Read frozen R00 samples and estimates, compute conditional relations only,
and save six-panel PNGs, full source data and a reproducible pairing record.
No resampling, official estimator calls, estimate/status replacement.
Regression panels show only the actual selected fit. MLE/WMLE distances use
the archived selected position. Keep criterion references and the distinct
MDM shape and MMLE deletion/shift contrasts needed for their explanations.
"""
from 共用 import ROOT, PROGRAM, RESULT, matrix_path, snapshot_path
DATA_DIR = RESULT / "报告2" / "数据"
from pathlib import Path
import csv
import hashlib
import importlib.util
import json
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.collections import PathCollection
from matplotlib.ticker import MaxNLocator, StrMethodFormatter
import numpy as np
from scipy.optimize import brentq, minimize_scalar
from scipy.special import logsumexp

HERE=Path(__file__).resolve().parent
IMAGES = RESULT / "报告2"
BLUE,BROWN,GRAY="#487A8B","#B67550","#858585"

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

helper=load(HERE/"逐方法机制复核.py","case_pair_helper")
plt.rcParams.update({"font.family":"sans-serif","font.sans-serif":["Microsoft YaHei","Arial","DejaVu Sans"],
    "font.size":9,"axes.linewidth":.65,"axes.spines.top":False,"axes.spines.right":False,
    "legend.frameon":False,"axes.unicode_minus":False,"xtick.major.width":.65,"ytick.major.width":.65})

LABELS=["LSE_zero","LSE_left","LSE_right","LRE_zero","LRE_left","LRE_right",
        "MLE_high","MLE_low","MLE_stop","MDM_low","MDM_edge","WMLE_low","WMLE_high",
        "MMLE_low","MMLE_high_deletion","MMLE_high_concentrated"]
TITLES=["零边界高估","内部左侧高估","内部右侧低估","零边界高估","内部左侧高估","内部右侧低估",
        "较高似然的高估","较高似然的低估","搜索停点高估","阈值交点低估","右端回退高估",
        "右侧交点低估","左侧交点高估","最小值平移低估","删点后高估","完整样本已集中"]

def mdm_functions(x):
    u=-np.log1p(-(np.arange(1,len(x)+1)-.3)/(len(x)+.4))
    cache={}
    def profile(g):
        g=float(g)
        if g not in cache:
            result=minimize_scalar(lambda b:np.std((x-g)/np.power(u,1/b),ddof=1),bounds=(.1,15),method="bounded")
            cache[g]=dict(beta=float(result.x),sigma=float(result.fun),eta=float(np.mean((x-g)/np.power(u,1/result.x))))
        return cache[g]
    def gradient(g):
        scale=max(abs(float(x[0])),1.);nominal=scale*1e-5
        left=max(float(g),0.);right=max(float(x[0]-g),0.)
        if right<=0:return float("inf")
        if g<=0 or left<=nominal:
            h=max(min(nominal,right*.25),np.finfo(float).eps*scale)
            return (profile(g+h)["sigma"]-profile(g)["sigma"])/h
        if right<=nominal:
            h=max(min(nominal,left*.25,right*.5),np.finfo(float).eps*scale)
            return (profile(g)["sigma"]-profile(g-h)["sigma"])/h
        h=max(min(nominal,left*.25,right*.25),np.finfo(float).eps*scale)
        return (profile(g+h)["sigma"]-profile(g-h)["sigma"])/(2*h)
    return profile,gradient,u

def main(labels=None):
    selected_labels = set(LABELS if labels is None else labels)
    if not selected_labels <= set(LABELS):
        raise ValueError('Unknown paired figure label')
    target = DATA_DIR/'20261010-配对图参照线精简核验.json'
    current = json.loads(target.read_text(encoding='utf-8'))
    previous_path=DATA_DIR/'20261010-各情形正常异常配对核验.json'
    previous=json.loads(previous_path.read_text(encoding='utf-8'))
    unchanged_labels=[label for label in LABELS if label.startswith(('MDM_','MMLE_'))]
    unchanged_png={label:previous['figures'][label]['sha256'] for label in unchanged_labels}
    process_path=DATA_DIR/"20261010-异常各情形过程核验.json"
    process=json.loads(process_path.read_text(encoding="utf-8"))
    cases=process["cases"]
    flow_path=DATA_DIR/"全量流程定位.csv"
    flow=list(csv.DictReader(flow_path.open(encoding="utf-8-sig")))
    catalog_path=PROGRAM/"跨参数对比/13组合取数.json"
    catalog={s["combination"]:s for s in json.loads(catalog_path.read_text(encoding="utf-8"))["sources"]}
    sources=dict(process["source_sha256"])
    sources.update({str(p):helper.digest(p) for p in [process_path,flow_path,catalog_path,previous_path,Path(__file__)]})
    old_png={str(p):helper.digest(p) for p in IMAGES.glob("*.png") if not p.name.startswith("配对情形_")}
    cache = {}
    pairs = dict(current['pairs']) if labels is not None else {}
    figures = dict(current['figures']) if labels is not None else {}
    rows = ([r for r in csv.DictReader((DATA_DIR/'20261010-参照线精简图数据.csv').open(encoding='utf-8-sig'))
             if r['example'] not in selected_labels] if labels is not None else [])
    with np.load(DATA_DIR/'20261010-参照线精简WMLE网格.npz') as saved:
        grids = {key:saved[key] for key in saved.files} if labels is not None else {}

    def source(combo):
        if combo not in cache:
            entry=catalog[combo]
            saved_matrix=matrix_path(entry)
            assert helper.digest(saved_matrix)==entry["matrix_sha256"]
            matrix=json.loads(saved_matrix.read_text(encoding="utf-8"))
            snapshot=snapshot_path(entry);sys.path.insert(0,str(snapshot))
            lse=load(snapshot/"methods/lse.py","pair_lse_"+str(len(cache)))
            wmle=load(snapshot/"methods/wmle.py","pair_wmle_"+str(len(cache)))
            cache[combo]=(matrix,lse,wmle)
        return cache[combo]

    def record(c,group,role):
        method="MDM δ=0.20" if c["method"]=="MDM" else c["method"]
        r=next(r for r in flow if r["combination"]==c["combination"] and int(r["n"])==c["n"] and int(r["group"])==group and r["method"]==method)
        matrix,lse,wmle=source(c["combination"])
        x=np.sort(np.asarray(next(s["values"] for s in matrix["samples"] if s["n"]==c["n"] and s["id"]==group),float))
        truth=np.asarray(matrix["config"]["truth"],float)
        g=float(r["gamma_hat"]);beta=float(r["beta_hat"])
        z=None
        if c["method"]=="LSE":z=lse.log_weibull_order_stat_means(c["n"])
        elif c["method"]=="LRE":
            ranks=np.arange(1,c["n"]+1)
            p=(ranks-.3)/(c["n"]+.4) if catalog[c["combination"]]["protocol"]=="historical-eight" else ((ranks-3/8)/(c["n"]+1/4) if c["n"]<=10 else (ranks-.5)/c["n"])
            z=np.log(-np.log1p(-p))
        if c["method"] in ("LSE","LRE"):
            at_true=helper.regression(x,truth[2],z,c["method"])
            at_original=helper.regression(x,g,z,c["method"])
        elif c["method"].startswith("MDM"):
            f,grad,u=mdm_functions(x)
            at_true=f(truth[2]).copy();at_true["gradient"]=float(grad(truth[2]))
            at_original=f(g).copy()
            if g<x[0]-1e-8*x[0]:at_original["gradient"]=float(grad(g))
        elif c["method"]=="WMLE":
            at_true=helper.wmle_profile(x,truth[2],wmle);at_original=helper.wmle_profile(x,g,wmle)
        else:
            retained=x[1:] if c["method"]=="MMLE" else x
            conditional = helper.mle_profile if c['method']=='MLE' else helper.shape_profile
            at_true=conditional(retained,truth[2]);at_original=conditional(retained,g)
        assert abs(np.log(at_original["beta"]/beta))<2e-5,(c["method"],c["combination"],group,role,beta,at_original["beta"],r["conditional_beta_log_error"])
        assert abs(np.log(at_original["eta"]/float(r["eta_hat"])))<2e-5,(c["method"],group,role)
        for stage,gamma in [(at_true,float(truth[2])),(at_original,g)]:
            values=x[1:] if c["method"]=="MMLE" else x
            logs=np.log(values-gamma)
            stage.update(gamma=gamma,log_range=float(np.ptp(logs)),log_sd=float(np.std(logs,ddof=1)))
        obj=dict(role=role,combination=c["combination"],n=c["n"],group=group,method=c["method"],
            beta_true=float(truth[0]),eta_true=float(truth[1]),gamma_true=float(truth[2]),
            beta_hat=beta,eta_hat=float(r["eta_hat"]),gamma_hat=g,values=x.tolist(),version=r["version"],
            abnormal=r["abnormal"]=="True",root_solver=r["archived_root_solver"],
            at_true=at_true,at_original=at_original)
        if c["method"]=="MMLE":obj["complete_true"]=helper.shape_profile(x,truth[2])
        return obj,z,wmle

    for label,title in zip(LABELS,TITLES):
        if label not in selected_labels: continue
        c=cases[label];method="MDM δ=0.20" if c["method"]=="MDM" else c["method"]
        pool=[r for r in flow if r["combination"]==c["combination"] and int(r["n"])==c["n"] and r["method"]==method and r["abnormal"]=="False"]
        selected=min(pool,key=lambda r:(abs(int(r["group"])-c["group"]),int(r["group"])))
        normal,z,wmle=record(c,int(selected["group"]),"正常")
        abnormal,_,_=record(c,c["group"],"异常")
        assert normal["version"]==abnormal["version"] and not normal["abnormal"] and abnormal["abnormal"]
        pairs[label]=dict(title=title,case=c["case"],pool_size=len(pool),pool_group_ids=[int(r["group"]) for r in pool],normal=normal,abnormal=abnormal)
        if "--prepare" in sys.argv:continue
        pair=[normal,abnormal];eta=normal["eta_true"];g0=normal["gamma_true"]
        fig,axes=plt.subplots(2,3,figsize=(9.6,5.7))

        def star(ax,xx,yy):ax.scatter([xx],[yy],marker="*",s=58,color=BROWN,edgecolors="white",lw=.5,zorder=6,clip_on=False)
        def shared(column,limits,ticks,ylim,yticks,xlabel,ylabel):
            for ax in axes[:,column]:
                ax.set(xlim=limits,xticks=ticks,ylim=ylim,yticks=yticks,xlabel=xlabel,ylabel=ylabel)
                ax.xaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
        def position(column,xlim,ylabel,ylim,yticks):
            ticks=MaxNLocator(nbins=4).tick_values(*xlim)
            ticks=ticks[(ticks>=xlim[0]-1e-9)&(ticks<=xlim[1]+1e-9)]
            shared(column,xlim,ticks,ylim,yticks,r"$\gamma/\gamma_0$",ylabel)
            for ax in axes[:,column]:ax.axvline(1,color=GRAY,lw=.7,ls="--",zorder=0)
        def gs_for(obj,start=0,end=None):
            x=np.asarray(obj["values"]);lower=start*g0
            gap=max(.02,1e-8*x[0]);upper=x[0]-gap
            if end is not None:upper=min(upper,end*g0)
            return np.unique(np.r_[np.linspace(lower,upper,340),x[0]-np.geomspace(gap,x[0]-lower,150),g0,obj["gamma_hat"] if obj["gamma_hat"]<=upper else g0])
        def save_curve(obj,panel,**columns):
            count=len(next(iter(columns.values())))
            rows.extend(dict(example=label,role=obj["role"],group=obj["group"],panel=panel,
                             **{key:float(value[i]) for key,value in columns.items()}) for i in range(count))
        fit_legend=[Line2D([0],[0],color=BROWN,marker="o",ms=3,ls="none",label="样本点"),
                    Line2D([0],[0],color=BROWN,lw=1,label="拟合直线"),
                    Line2D([0],[0],marker="*",color=BROWN,ls="none",ms=7,label="原估计")]
        legend=fit_legend

        if c["method"] in ("LSE","LRE"):
            xmax=float(np.ceil(max(o["values"][0]/g0 for o in pair)*10)/10)
            position(1,(0,xmax),r"$1-R^2(\gamma)$",(0,.4),[0,.1,.2,.3,.4])
            bmax=max(16,np.ceil(max(o["beta_hat"] for o in pair)/5)*5)
            position(2,(0,xmax),r"$\hat\beta(\gamma)$",(0,bmax),MaxNLocator(nbins=4).tick_values(0,bmax))
            reverse=c["method"]=="LRE"
            shared(0,(-6,2) if reverse else (-3.6,1.3),[-6,-4,-2,0,2] if reverse else [-3,-2,-1,0,1],
                   (-4.2,1.5) if reverse else (-6,2),[-4,-3,-2,-1,0,1] if reverse else [-6,-4,-2,0,2],
                   r"$\ln[(x_{(i)}-\hat\gamma)/\eta_0]$" if reverse else r"$z_i$",r"$z_i$" if reverse else r"$\ln[(x_{(i)}-\hat\gamma)/\eta_0]$")
            for row,obj in enumerate(pair):
                x=np.asarray(obj["values"]);ax=axes[row,0]
                for gamma,color,stage in [(obj["gamma_hat"],BROWN,"estimated")]:
                    y=np.log((x-gamma)/eta);xx,yy=(y,z) if reverse else (z,y)
                    p=helper.regression(x,gamma,z,c["method"]);slope=p["beta"] if reverse else 1/p["beta"]
                    fit=yy.mean()+slope*(xx-xx.mean())
                    ax.plot(xx,fit,color=color,lw=1.1);ax.scatter(xx,yy,s=17,color=color,edgecolors="white",lw=.35,zorder=4)
                    if stage=="estimated":
                        for i,(u,v) in enumerate(zip(xx,yy),1):
                            offset=(8 if i%2 else -8,0) if reverse else (0,6 if i%2 else -10)
                            ax.annotate(str(i),(u,v),xytext=offset,textcoords="offset points",fontsize=6,
                                        ha=("left" if i%2 else "right") if reverse else "center",va="center",color="#515151")
                    save_curve(obj,"fit_"+stage,rank=np.arange(1,len(x)+1),horizontal=xx,vertical=yy,fitted=fit)
                gs=gs_for(obj);p=[helper.regression(x,float(g),z,c["method"]) for g in gs]
                axes[row,1].plot(gs/g0,[q["relative_residual"] for q in p],color=BLUE,lw=1.15)
                star(axes[row,1],obj["gamma_hat"]/g0,obj["at_original"]["relative_residual"])
                axes[row,2].plot(gs/g0,[q["beta"] for q in p],color=BLUE,lw=1.15)
                axes[row,2].axhline(obj["beta_true"],color=GRAY,lw=.7,ls="--")
                star(axes[row,2],obj["gamma_hat"]/g0,obj["beta_hat"])
                save_curve(obj,"criterion",gamma=gs,gamma_ratio=gs/g0,loss=np.array([q["relative_residual"] for q in p]),beta=np.array([q["beta"] for q in p]))
        elif c["method"]=="MLE":
            xmax=float(np.ceil(max(o["values"][0]/g0 for o in pair)*10)/10)
            position(0,(0,xmax),r"$\ell_p(\gamma)-\ell_p(\gamma_0)$",(-2,2),[-2,-1,0,1,2])
            bmax=max(16,np.ceil(max(o["beta_hat"] for o in pair)/5)*5)
            position(1,(0,xmax),r"$\hat\beta(\gamma)$",(0,bmax),MaxNLocator(nbins=4).tick_values(0,bmax))
            dmax=max(2.5,np.ceil(max((max(o["values"])-o["gamma_hat"])/eta for o in pair)*2)/2)
            dticks=MaxNLocator(nbins=5).tick_values(0,dmax);dticks=dticks[dticks<=dmax+1e-9]
            ranks=np.arange(1,c["n"]+1,2 if c["n"]>10 else 1)
            shared(2,(.5,c["n"]+.5),ranks,(0,dmax),dticks,r"$i$",r"$(x_{(i)}-\hat\gamma)/\eta_0$")
            for row,obj in enumerate(pair):
                x=np.asarray(obj["values"]);gs=gs_for(obj);p=[helper.mle_profile(x,float(g)) for g in gs]
                axes[row,0].plot(gs/g0,[q["ll"]-obj["at_true"]["ll"] for q in p],color=BLUE,lw=1.15)
                axes[row,0].axhline(0,color=GRAY,lw=.7,ls="--")
                star(axes[row,0],obj["gamma_hat"]/g0,obj["at_original"]["ll"]-obj["at_true"]["ll"])
                axes[row,1].plot(gs/g0,[q["beta"] for q in p],color=BLUE,lw=1.15)
                axes[row,1].axhline(obj["beta_true"],color=GRAY,lw=.7,ls="--")
                star(axes[row,1],obj["gamma_hat"]/g0,obj["beta_hat"])
                for gamma,color,stage in [(obj["gamma_hat"],BROWN,"estimated")]:
                    values=(x-gamma)/eta;axes[row,2].plot(np.arange(1,len(x)+1),values,color=color,lw=1,marker="o",ms=3.5)
                    save_curve(obj,"distance_"+stage,rank=np.arange(1,len(x)+1),distance_ratio=values)
                save_curve(obj,"profile",gamma=gs,gamma_ratio=gs/g0,ll_difference=np.array([q["ll"]-obj["at_true"]["ll"] for q in p]),beta=np.array([q["beta"] for q in p]))
            legend=[Line2D([0],[0],color=BROWN,marker="o",ms=3,lw=1,label="样本距离"),fit_legend[2]]
        elif c["method"].startswith("MDM"):
            xmin=min(.95,min(o["gamma_hat"]/g0 for o in pair)-.04);xmax=max(1.16,max(o["gamma_hat"]/g0 for o in pair)+.02)
            position(0,(xmin,xmax),r"$g(\gamma)$",(-.1,.3),[-.1,0,.1,.2,.3])
            shared(1,(0,16),[0,4,8,12,16],(0,.6),[0,.2,.4,.6],r"$\beta$",r"$\sigma(\beta,\hat\gamma)/\eta_0$")
            umax=-np.log1p(-(np.arange(1,8)-.3)/(7+.4))
            pmax=max(1.6,np.ceil(max(np.max((np.asarray(o["values"])-o["gamma_hat"])/np.power(umax,1/b)/eta)
                                    for o in pair for b in [o["beta_true"],o["beta_hat"]])*5)/5)
            pticks=MaxNLocator(nbins=4).tick_values(0,pmax);pticks=pticks[pticks<=pmax+1e-9]
            shared(2,(.6,7.4),np.arange(1,8),(0,pmax),pticks,r"$i$",r"$\eta_i/\eta_0$")
            for row,obj in enumerate(pair):
                x=np.asarray(obj["values"]);profile,grad,u=mdm_functions(x);gs=gs_for(obj,xmin,xmax)
                gradients=np.array([grad(g) for g in gs]);ax=axes[row,0]
                ax.plot(gs/g0,gradients,color=BLUE,lw=1.15);ax.axhline(.2,color=GRAY,lw=.7,ls=":")
                crossings=np.flatnonzero((gradients[:-1]-.2)*(gradients[1:]-.2)<0)
                roots=[float(brentq(lambda g:grad(g)-.2,gs[i],gs[i+1],xtol=1e-8)) for i in crossings]
                obj["gradient_roots"]=roots
                if obj["root_solver"]=="right_edge_fit":
                    min_gap=max(abs(float(x[0]))*1e-12,1e-12)
                    anchor_g=x[0]-np.geomspace(max(abs(float(x[0]))*1e-3,min_gap),min_gap,24)
                    anchor_v=np.array([grad(g) for g in anchor_g])
                    assert len(roots)==2 and np.all(anchor_g>roots[-1]) and np.all(anchor_v<.2)
                    ax.axvline(obj["gamma_hat"]/g0,color=BROWN,lw=1.1)
                    ax.scatter(np.array(roots)/g0,[.2]*len(roots),facecolors="white",edgecolors=BLUE,s=25,lw=.9,zorder=5)
                    ax.scatter(anchor_g/g0,anchor_v,s=7,color="#444444",zorder=4)
                    obj["right_anchor_probes"]=[dict(gamma=float(g),gradient=float(v)) for g,v in zip(anchor_g,anchor_v)]
                    save_curve(obj,"right_anchor",gamma=anchor_g,gamma_ratio=anchor_g/g0,gradient=anchor_v)
                else:star(ax,obj["gamma_hat"]/g0,grad(obj["gamma_hat"]))
                bs=np.unique(np.r_[np.linspace(.3,15,520),obj["beta_hat"],obj["beta_true"]])
                sigmas=np.array([np.std((x-obj["gamma_hat"])/np.power(u,1/b),ddof=1)/eta for b in bs])
                axes[row,1].plot(bs,sigmas,color=BLUE,lw=1.15);axes[row,1].axvline(obj["beta_true"],color=GRAY,lw=.7,ls="--")
                star(axes[row,1],obj["beta_hat"],obj["at_original"]["sigma"]/eta)
                for b,color,stage in [(obj["beta_true"],GRAY,"true_beta"),(obj["beta_hat"],BROWN,"estimated_beta")]:
                    values=(x-obj["gamma_hat"])/np.power(u,1/b)/eta
                    axes[row,2].plot(np.arange(1,len(x)+1),values,color=color,lw=1,marker="o",ms=3.8)
                    save_curve(obj,"pseudo_scale_"+stage,rank=np.arange(1,len(x)+1),scale_ratio=values)
                save_curve(obj,"gradient",gamma=gs,gamma_ratio=gs/g0,gradient=gradients)
                save_curve(obj,"conditional_sigma",beta=bs,sigma_ratio=sigmas)
            legend=[Line2D([0],[0],color=GRAY,marker="o",ms=3,lw=1,label="真β的伪尺度"),Line2D([0],[0],color=BROWN,marker="o",ms=3,lw=1,label="估计β的伪尺度"),fit_legend[2]]
            if label=="MDM_edge":legend += [Line2D([0],[0],marker="o",mfc="white",mec=BLUE,ls="none",ms=4,label="梯度交点"),Line2D([0],[0],marker="o",color="#444444",ls="none",ms=3,label="右端探测")]
        elif c["method"]=="WMLE":
            xmin=min(.9,min(o["gamma_hat"]/g0 for o in pair)-.03);xmax=max(1.17,max(o["gamma_hat"]/g0 for o in pair)+.02)
            bmax=min(wmle.SHAPE_UPPER, max(9,np.ceil(max(o["beta_hat"] for o in pair))))
            shared(0,(.6,7.4),np.arange(1,8),(0,2.5),[0,.5,1,1.5,2,2.5],r"$i$",r"$(x_{(i)}-\hat\gamma)/\eta_0$")
            position(1,(xmin,xmax),r"$\beta$",(0,bmax),[0,3,6,9] if bmax==9 else MaxNLocator(nbins=4).tick_values(0,bmax))
            position(2,(xmin,xmax),r"$T_2[\hat\beta(\gamma),\gamma]$",(-.08,.08),[-.08,-.04,0,.04,.08])
            for row,obj in enumerate(pair):
                x=np.asarray(obj["values"]);gs=gs_for(obj,xmin,xmax);bs=np.linspace(.4,bmax,190)
                for gamma,color,stage in [(obj["gamma_hat"],BROWN,"estimated")]:
                    values=(x-gamma)/eta;axes[row,0].plot(np.arange(1,8),values,color=color,lw=1,marker="o",ms=3.8)
                    save_curve(obj,"distance_"+stage,rank=np.arange(1,8),distance_ratio=values)
                t1,t2 = helper.conditional_profiles.wmle_residuals(
                    x, bs[None,:], gs[:,None], wmle)
                axes[row,1].contour(gs/g0,bs,t1.T,levels=[0],colors=[BLUE],linewidths=1.2)
                axes[row,1].contour(gs/g0,bs,t2.T,levels=[0],colors=[BROWN],linewidths=1.2)
                axes[row,1].scatter([1],[obj["beta_true"]],marker="D",facecolors="white",edgecolors=GRAY,s=25,lw=.8,zorder=5)
                star(axes[row,1],obj["gamma_hat"]/g0,obj["beta_hat"])
                if row==0:axes[row,1].legend(handles=[Line2D([0],[0],color=BLUE,lw=1.2,label=r"$T_1=0$"),Line2D([0],[0],color=BROWN,lw=1.2,label=r"$T_2=0$")],loc="upper right",fontsize=7)
                p=[helper.wmle_profile(x,float(g),wmle) for g in gs]
                axes[row,2].plot(gs/g0,[q["t2"] if q is not None else np.nan for q in p],color="#444444",lw=1.15);axes[row,2].axhline(0,color=GRAY,lw=.7,ls=":")
                star(axes[row,2],obj["gamma_hat"]/g0,obj["at_original"]["t2"])
                save_curve(obj,"shape_zero_branch",gamma=gs,gamma_ratio=gs/g0,beta=np.array([q["beta"] if q is not None else np.nan for q in p]),t2=np.array([q["t2"] if q is not None else np.nan for q in p]),conditional_defined=np.array([q is not None for q in p]))
                for key,value in [("gamma",gs),("beta",bs),("T1",t1),("T2",t2)]:grids[label+"_"+obj["role"]+"_"+key]=value
            legend=[Line2D([0],[0],color=BROWN,marker="o",ms=3,lw=1,label="样本距离"),fit_legend[2],
                    Line2D([0],[0],marker="D",mfc="white",mec=GRAY,ls="none",ms=4,label="真参数")]
        else:
            shared(0,(.6,7.4),np.arange(1,8),(0,2),[0,.5,1,1.5,2],r"$i$",r"$(x_{(i)}-\gamma)/\eta_0$")
            shared(1,(0,16),[0,4,8,12,16],(-.3,.6),[-.3,0,.3,.6],r"$\beta$",r"$U_\beta(\beta;\gamma)$")
            shared(2,(.6,7.4),np.arange(1,8),(-7,1.5),[-6,-4,-2,0,1],r"$i$",r"$\ln[(x_{(i)}-\gamma)/\eta_0]$")
            for row,obj in enumerate(pair):
                x=np.asarray(obj["values"]);ranks=np.arange(1,8)
                axes[row,0].plot(ranks,(x-g0)/eta,color=BLUE,lw=1,marker="o",ms=3.8)
                axes[row,0].plot(ranks[1:],(x[1:]-x[0])/eta,color=BROWN,lw=1,marker="o",ms=3.8)
                axes[row,0].scatter([1],[0],marker="x",s=23,color=BROWN,lw=1)
                bs=np.unique(np.r_[np.linspace(.3,16,540),obj["beta_hat"],obj["complete_true"]["beta"],obj["at_true"]["beta"]])
                for stage,values,gamma,color in [("complete_true",x,g0,BLUE),("retained_true",x[1:],g0,GRAY),("retained_shifted",x[1:],x[0],BROWN)]:
                    logs=np.log(values-gamma);centered=logs-logs.mean();power=bs[:,None]*centered[None,:]
                    weights=np.exp(power-power.max(axis=1)[:,None]);weights/=weights.sum(axis=1)[:,None]
                    score=1/bs-np.sum(weights*centered[None,:],axis=1)
                    axes[row,1].plot(bs,score,color=color,lw=1.15)
                    save_curve(obj,"score_"+stage,beta=bs,score=score)
                    point_ranks=ranks if stage=="complete_true" else ranks[1:]
                    axes[row,2].plot(point_ranks,np.log((values-gamma)/eta),color=color,lw=1,marker="o",ms=3.5)
                    save_curve(obj,"log_distance_"+stage,rank=point_ranks,log_distance=np.log((values-gamma)/eta))
                axes[row,1].axhline(0,color="#555555",lw=.65,ls=":");axes[row,1].axvline(obj["beta_true"],color="#AAAAAA",lw=.65,ls="--")
                star(axes[row,1],obj["beta_hat"],0)
            legend=[Line2D([0],[0],color=BLUE,lw=1,label="完整样本·真位置"),Line2D([0],[0],color=GRAY,lw=1,label="删点·真位置"),Line2D([0],[0],color=BROWN,lw=1,label="删点·最小值平移"),fit_legend[2]]

        for row,obj in enumerate(pair):axes[row,0].set_title(obj["role"]+f" · 第{obj['group']}组",loc="left",pad=14,fontsize=9)
        for index,ax in enumerate(axes.ravel()):ax.text(-.16,1.04,chr(97+index),transform=ax.transAxes,fontweight="bold",fontsize=11)
        fig.legend(handles=legend,loc="lower center",bbox_to_anchor=(.52,.015),ncol=len(legend),fontsize=8)
        fig.subplots_adjust(left=.08,right=.985,bottom=.14,top=.91,wspace=.39,hspace=.48)
        fig.canvas.draw();extent=fig.bbox
        for text in fig.findobj(matplotlib.text.Text):
            if text.get_visible() and text.get_text():
                box=text.get_window_extent(fig.canvas.get_renderer())
                assert box.x0>=extent.x0-1 and box.y0>=extent.y0-1 and box.x1<=extent.x1+1 and box.y1<=extent.y1+1,(label,text.get_text())
        axes_meta=[{k:getattr(ax,'get_'+k)().tolist() if k in ('xticks','yticks') else list(getattr(ax,'get_'+k)()) for k in ['xlim','ylim','xticks','yticks']} for ax in axes.ravel()]
        assert all(axes_meta[col]==axes_meta[col+3] for col in range(3))
        for ax in axes.ravel():
            xlo,xhi=ax.get_xlim();ylo,yhi=ax.get_ylim()
            point_series=[np.asarray(collection.get_offsets(),float) for collection in ax.collections if isinstance(collection,PathCollection)]
            point_series += [np.column_stack([line.get_xdata(),line.get_ydata()]) for line in ax.lines if line.get_marker() not in [None,"None","",' ']]
            for values in point_series:
                assert np.all((values[:,0]>=xlo-1e-9)&(values[:,0]<=xhi+1e-9)&(values[:,1]>=ylo-1e-9)&(values[:,1]<=yhi+1e-9)),(label,ax.get_ylabel(),values.tolist())
        path=IMAGES/("配对情形_"+label+".png")
        temporary=path.with_suffix(".tmp.png")
        fig.savefig(temporary,dpi=400,facecolor="white");plt.close(fig)
        temporary.replace(path)
        figures[label]=dict(path=str(path),sha256=helper.digest(path),panels=6,axes=axes_meta,all_observation_points_visible=True,
            selected_fit_only=c['method'] in ('LSE','LRE'),
            distances_at_selected_position_only=c['method'] in ('MLE','WMLE'),
            legend_labels=[entry.get_label() for entry in legend],
            conclusion=title+": compare archived non-abnormal and abnormal cases within the same method/condition.")

    for label,pair in pairs.items():
        for role in ['normal','abnormal']:
            old=previous['pairs'][label][role]
            for key in ['group','combination','n','method','version','values','beta_hat','eta_hat','gamma_hat','abnormal']:
                assert pair[role][key]==old[key],(label,role,key)
    assert not any(row['panel'] in ['fit_true','distance_true'] for row in rows)
    assert all('真位置' not in figures[label]['legend_labels'] for label in LABELS[:9]+LABELS[11:13])

    if "--prepare" not in sys.argv:
        names=list(dict.fromkeys(k for row in rows for k in row))
        curve_path = DATA_DIR/"20261010-参照线精简图数据.csv"
        curve_temporary = curve_path.with_suffix(".tmp.csv")
        with curve_temporary.open("w",encoding="utf-8",newline="") as h:
            writer=csv.DictWriter(h,fieldnames=names,lineterminator="\n");writer.writeheader();writer.writerows(rows)
        curve_temporary.replace(curve_path)
        if labels is None or any(label.startswith('WMLE_') for label in selected_labels):
            np.savez_compressed(DATA_DIR/"20261010-参照线精简WMLE网格.npz",**grids)
        current.update(pairs=pairs, figures=figures, source_sha256=sources,
                       conditional_domains=dict(MLE='beta>=1, eta>0, 0<=gamma<min(X)',
                                                WMLE='T1=T2=0, 0<beta<10; no T1 zero means undefined'),
                       shared_profile_sha256=helper.digest(Path(helper.conditional_profiles.__file__)))
        temporary = target.with_suffix('.tmp.json')
        temporary.write_text(json.dumps(current,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
        temporary.replace(target)
    print(f'Generated {len(selected_labels)} paired mechanism figures from archived samples and estimates')

if __name__=="__main__":main()
