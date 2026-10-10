"""PNG mechanism panels for every report2 abnormal case on preserved samples.

Use the already reported examples, without choosing new favorable samples or
running official estimators. Existing matrices, dependencies, labels and PNGs
stay unchanged. Curves, fitted observations and equation grids are saved here.
"""
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
from matplotlib.ticker import StrMethodFormatter
import numpy as np
from scipy.special import logsumexp
from scipy.optimize import brentq, minimize_scalar

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IMAGES = HERE.parents[1] / "图片"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load(HERE / "逐方法机制复核.py", "typical_plot_helper")
BLUE, BROWN, GRAY = "#487A8B", "#B67550", "#858585"
plt.rcParams.update({"font.family":"sans-serif", "font.sans-serif":["Microsoft YaHei","Arial","DejaVu Sans"],
    "font.size":9, "axes.linewidth":.65, "axes.spines.top":False, "axes.spines.right":False,
    "legend.frameon":False, "axes.unicode_minus":False, "xtick.major.width":.65, "ytick.major.width":.65})


def main():
    process_path = HERE / "20261010-异常各情形过程核验.json"
    data = json.loads(process_path.read_text(encoding="utf-8"))
    cases = data["cases"]
    hashes = dict(data["source_sha256"])
    hashes.update({str(p):helper.digest(p) for p in [process_path, Path(__file__)]})
    old_png = {str(p):helper.digest(p) for p in HERE.parents[1].rglob("*.png")
               if not p.name.startswith("典型情形_")}
    assert all(helper.digest(Path(p)) == h for p,h in hashes.items())
    assert all(helper.digest(Path(p)) == h for p,h in data["protected_png_sha256"].items())
    rows, grids, figures = [], {}, {}
    wmle_path = ROOT / "W(5,100,500)/20261007-暂存样本补齐/程序/依赖快照/python"
    sys.path.insert(0,str(wmle_path))
    wmle = load(wmle_path / "methods/wmle.py", "typical_frozen_wmle")
    mdm_path = ROOT / "W(2,1000,3000)/20260825/程序/依赖快照/python/methods/mdm.py"
    hashes[str(mdm_path)] = helper.digest(mdm_path)
    mdm_diagnostics = {}

    def context(label):
        c=cases[label]
        x=np.asarray(c["values"],float)
        eta=float(c["combination"].removeprefix("W(").removesuffix(")").split(",")[1])
        return c,x,eta,c["true_gamma"]

    def canvas():
        return plt.subplots(2,3,figsize=(9.6,5.7))

    def gamma_grid(c,x,start=0,end=None,count=600):
        g0=c["true_gamma"]
        lower=start*g0
        upper=min(x[0]-max(.02,1e-8*x[0]), (end*g0 if end else x[0]))
        selected=c["archived_gamma"]
        extras=[g0,selected] if selected <= upper else [g0]
        return np.unique(np.r_[np.linspace(lower,upper,count),
                              x[0]-np.geomspace(max(.02,1e-8*x[0]),x[0]-lower,180),extras])

    def position_axis(ax,limits,ticks,ylabel,ylim,yticks):
        ax.set(xlim=limits,xticks=ticks,ylim=ylim,yticks=yticks,xlabel=r"$\gamma/\gamma_0$",ylabel=ylabel)
        ax.xaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
        ax.axvline(1,color=GRAY,lw=.7,ls="--",zorder=0)

    def star(ax,x,y):
        ax.scatter([x],[y],marker="*",s=58,color=BROWN,edgecolors="white",linewidths=.5,zorder=6,clip_on=False)

    def observations(ax,a,b,fit_a,fit_b,reverse=False):
        for xx,yy,fitted,color in [(a[0],a[1],fit_a,GRAY),(b[0],b[1],fit_b,BROWN)]:
            order=np.argsort(xx)
            ax.plot(np.asarray(xx)[order],np.asarray(fitted)[order],color=color,lw=1.1)
            ax.scatter(xx,yy,s=17,color=color,edgecolors="white",lw=.35,zorder=4)
        for rank,(xx,yy) in enumerate(zip(*b),1):
            offset=(8 if rank%2 else -8,0) if reverse else (0,5 if rank%2 else -10)
            alignment=("left" if rank%2 else "right") if reverse else "center"
            ax.annotate(str(rank),(xx,yy),xytext=offset,textcoords="offset points",
                        fontsize=6,ha=alignment,va="center",color="#515151")

    fit_legend=[Line2D([0],[0],color=GRAY,marker="o",ms=3,lw=1,label="真位置拟合"),
                Line2D([0],[0],color=BROWN,marker="o",ms=3,lw=1,label="原位置拟合"),
                Line2D([0],[0],marker="*",color=BROWN,ls="none",ms=7,label="原估计")]
    result_legend=[Line2D([0],[0],color=GRAY,ls="--",lw=.7,label="真值"),
                   Line2D([0],[0],marker="*",color=BROWN,ls="none",ms=7,label="原估计")]

    def finish(fig,axes,name,labels,contract,legend=None):
        for index,ax in enumerate(axes.ravel()):
            ax.text(-.16,1.04,chr(97+index),transform=ax.transAxes,fontweight="bold",fontsize=11)
        if legend:
            fig.legend(handles=legend,loc="lower center",bbox_to_anchor=(.52,.015),ncol=len(legend),fontsize=8)
        fig.subplots_adjust(left=.08,right=.985,bottom=.14,top=.91,wspace=.39,hspace=.48)
        fig.canvas.draw()
        extent=fig.bbox
        for text in fig.findobj(matplotlib.text.Text):
            if text.get_visible() and text.get_text():
                box=text.get_window_extent(fig.canvas.get_renderer())
                assert box.x0 >= extent.x0-1 and box.y0 >= extent.y0-1 and box.x1 <= extent.x1+1 and box.y1 <= extent.y1+1,(name,text.get_text())
        assert len(fig.axes)==6
        axes_meta=[dict(xlim=list(ax.get_xlim()),ylim=list(ax.get_ylim()),xticks=ax.get_xticks().tolist(),
                       yticks=ax.get_yticks().tolist(),xlabel=ax.get_xlabel(),ylabel=ax.get_ylabel(),
                       title=ax.get_title(loc="left")) for ax in axes.ravel()]
        path=IMAGES/("典型情形_"+name+".png")
        fig.savefig(path,dpi=400,facecolor="white")
        plt.close(fig)
        figures[name]=dict(file=str(path),sha256=helper.digest(path),sample_labels=labels,
            conclusion=contract,panels=6,axes=axes_meta,
            samples={label:{key:cases[label][key] for key in ["combination","n","group","values","case","archived_beta","archived_gamma"]} for label in labels})

    def fitted_panel(ax,label):
        c,x,eta,g0=context(label)
        z=np.asarray(c["at_true_location"]["reference_values"])
        coordinate=[]
        for stage in ["at_true_location","at_selected_location"]:
            info=c[stage]
            y=np.log((x-info["gamma"])/eta)
            if c["method"]=="LSE":
                xx,yy=z,y
            else:
                xx,yy=y,z
            fitted=yy.mean()+info["slope"]*(xx-xx.mean())
            coordinate.append((xx,yy,fitted))
            rows.extend(dict(figure=c["method"],example=label,panel="fitting",kind=stage,rank=i,
                             horizontal=float(u),vertical=float(v),fitted=float(f))
                        for i,(u,v,f) in enumerate(zip(xx,yy,fitted),1))
        observations(ax,(coordinate[0][0],coordinate[0][1]),(coordinate[1][0],coordinate[1][1]),coordinate[0][2],coordinate[1][2],c["method"]=="LRE")
        if c["method"]=="LSE":
            ax.set(xlim=(-3.6,1.3),xticks=[-3,-2,-1,0,1],ylim=(-6,2),yticks=[-6,-4,-2,0,2],xlabel=r"$z_i$",ylabel=r"$\ln(d_i/\eta_0)$")
        else:
            ax.set(xlim=(-6,2),xticks=[-6,-4,-2,0,2],ylim=(-4.2,1.5),yticks=[-4,-3,-2,-1,0,1],xlabel=r"$\ln(d_i/\eta_0)$",ylabel=r"$z_i$")

    # LSE supplements the retained normal/zero-boundary figure with both interior cases.
    fig,axes=canvas()
    for row,(label,title) in enumerate([("LSE_left","内部左侧高估"),("LSE_right","内部右侧低估")]):
        c,x,eta,g0=context(label)
        fitted_panel(axes[row,0],label)
        axes[row,0].set_title(title+f" · 第{c['group']}组",loc="left",pad=14,fontsize=9)
        z=np.asarray(c["at_true_location"]["reference_values"])
        gs=gamma_grid(c,x)
        profiles=[helper.regression(x,float(g),z,"LSE") for g in gs]
        losses=[p["relative_residual"] for p in profiles]
        betas=[p["beta"] for p in profiles]
        for col,values,ylabel,ylim,yticks in [(1,losses,r"$1-R^2(\gamma)$",(0,.30),[0,.1,.2,.3]),
                (2,betas,r"$\hat\beta(\gamma)$",(0,16),[0,4,8,12,16])]:
            ax=axes[row,col]
            position_axis(ax,(0,1.65),[0,.5,1,1.5],ylabel,ylim,yticks)
            ax.plot(gs/g0,values,color=BLUE,lw=1.15)
            selected=c["at_selected_location"]
            star(ax,c["archived_gamma"]/g0,selected["relative_residual"] if col==1 else c["archived_beta"])
            if col==2:ax.axhline(c["true_beta"],color=GRAY,lw=.7,ls="--")
        rows.extend(dict(figure="LSE内部",example=label,panel="criterion",gamma=float(g),gamma_ratio=float(g/g0),loss=float(l),beta=float(b)) for g,l,b in zip(gs,losses,betas))
    finish(fig,axes,"LSE内部",["LSE_left","LSE_right"],"Two interior criterion minima produce opposite slope changes and shape abnormalities.",fit_legend)

    fig,axes=canvas()
    lre_labels=["LRE_zero","LRE_left","LRE_right"]
    for col,(label,title) in enumerate(zip(lre_labels,["零边界高估","内部左侧高估","内部右侧低估"])):
        c,x,eta,g0=context(label)
        fitted_panel(axes[0,col],label)
        axes[0,col].set_title(title+f" · 第{c['group']}组",loc="left",pad=14,fontsize=9)
        z=np.asarray(c["at_true_location"]["reference_values"])
        gs=gamma_grid(c,x)
        profiles=[helper.regression(x,float(g),z,"LRE") for g in gs]
        loss=[p["relative_residual"] for p in profiles]
        ax=axes[1,col]
        position_axis(ax,(0,1.65),[0,.5,1,1.5],r"$1-R^2(\gamma)$",(0,.4),[0,.1,.2,.3,.4])
        ax.plot(gs/g0,loss,color=BLUE,lw=1.15)
        star(ax,c["archived_gamma"]/g0,c["at_selected_location"]["relative_residual"])
        rows.extend(dict(figure="LRE",example=label,panel="criterion",gamma=float(g),gamma_ratio=float(g/g0),loss=float(p["relative_residual"]),beta=float(p["beta"])) for g,p in zip(gs,profiles))
    finish(fig,axes,"LRE",lre_labels,"Boundary/left minima increase the reverse-regression slope; a right minimum decreases it.",fit_legend)

    fig,axes=canvas()
    mle_labels=["MLE_high","MLE_low","MLE_stop"]
    for col,(label,title) in enumerate(zip(mle_labels,["似然支持的高估","似然支持的低估","搜索停点高估"])):
        c,x,eta,g0=context(label)
        gs=gamma_grid(c,x)
        profiles=[helper.shape_profile(x,float(g)) for g in gs]
        ll0=c["at_true_location"]["ll"]
        loss=[p["ll"]-ll0 for p in profiles]
        beta=[p["beta"] for p in profiles]
        for row,values,ylabel,ylim,yticks in [(0,loss,r"$\ell_p(\gamma)-\ell_p(\gamma_0)$",(-2,2),[-2,-1,0,1,2]),
                (1,beta,r"$\hat\beta(\gamma)$",(0,30),[0,10,20,30])]:
            ax=axes[row,col]
            position_axis(ax,(0,2.3),[0,.5,1,1.5,2],ylabel,ylim,yticks)
            ax.plot(gs/g0,values,color=BLUE,lw=1.15)
            star(ax,c["archived_gamma"]/g0,c["at_selected_location"]["ll"]-ll0 if row==0 else c["archived_beta"])
            ax.axhline(0 if row==0 else c["true_beta"],color=GRAY,lw=.7,ls="--")
        axes[0,col].set_title(title+f" · 第{c['group']}组",loc="left",pad=14,fontsize=9)
        rows.extend(dict(figure="MLE",example=label,panel="profile",gamma=float(g),gamma_ratio=float(g/g0),ll_difference=float(p["ll"]-ll0),beta=float(p["beta"])) for g,p in zip(gs,profiles))
    finish(fig,axes,"MLE",mle_labels,"Criterion-supported high/low cases differ from a stop with a higher feasible likelihood.",result_legend)

    fig,axes=canvas()
    mdm_labels=["MDM_low","MDM_edge"]
    for row,(label,title) in enumerate(zip(mdm_labels,["阈值交点低估","右端回退高估"])):
        c,x,eta,g0=context(label)
        u=-np.log1p(-(np.arange(1,len(x)+1)-.3)/(len(x)+.4))
        profile_cache={}

        def frozen_profile(gamma):
            gamma=float(gamma)
            if gamma not in profile_cache:
                result=minimize_scalar(lambda b:np.std((x-gamma)/np.power(u,1/b),ddof=1),
                                       bounds=(.1,15),method="bounded")
                profile_cache[gamma]=(float(result.x),float(result.fun))
            return profile_cache[gamma]

        def frozen_gradient(gamma):
            # Exact finite-difference branches of the preserved MDM implementation.
            scale=max(abs(float(x[0])),1.)
            nominal_h=scale*1e-5
            left=max(float(gamma),0.)
            right=max(float(x[0]-gamma),0.)
            if right<=0:return float("inf")
            if gamma<=0 or left<=nominal_h:
                h=max(min(nominal_h,right*.25),np.finfo(float).eps*scale)
                return (frozen_profile(gamma+h)[1]-frozen_profile(gamma)[1])/h
            if right<=nominal_h:
                h=max(min(nominal_h,left*.25,right*.5),np.finfo(float).eps*scale)
                return (frozen_profile(gamma)[1]-frozen_profile(gamma-h)[1])/h
            h=max(min(nominal_h,left*.25,right*.25),np.finfo(float).eps*scale)
            return (frozen_profile(gamma+h)[1]-frozen_profile(gamma-h)[1])/(2*h)

        gs=gamma_grid(c,x,start=.95,end=1.16,count=240)
        gradients=np.asarray([frozen_gradient(g) for g in gs])
        profiles=[dict(beta=frozen_profile(g)[0],finite_gradient=float(v)) for g,v in zip(gs,gradients)]
        crossing_indices=np.flatnonzero((gradients[:-1]-.2)*(gradients[1:]-.2)<0)
        roots=[brentq(lambda g:frozen_gradient(g)-.2,gs[i],gs[i+1],xtol=1e-8) for i in crossing_indices]
        root_records=[dict(gamma=float(g),gradient=float(frozen_gradient(g)),beta=frozen_profile(g)[0]) for g in roots]
        ax=axes[row,0]
        position_axis(ax,(.95,1.16),[.95,1,1.05,1.1,1.15],r"$g(\gamma)$",(-.1,.3),[-.1,0,.1,.2,.3])
        ax.plot(gs/g0,gradients,color=BLUE,lw=1.15)
        ax.axhline(.2,color=GRAY,lw=.7,ls=":")
        if label=="MDM_low":star(ax,c["archived_gamma"]/g0,c["at_selected_location"]["finite_gradient"])
        else:
            ax.axvline(c["archived_gamma"]/g0,color=BROWN,lw=1.1)
            min_gap=max(abs(float(x[0]))*1e-12,1e-12)
            anchor_gaps=np.geomspace(max(abs(float(x[0]))*1e-3,min_gap),min_gap,24)
            anchors=[dict(gamma=float(max(0,x[0]-gap)),gradient=float(frozen_gradient(max(0,x[0]-gap)))) for gap in anchor_gaps]
            assert len(roots)==2
            assert all(a["gamma"]>roots[-1] and a["gradient"]<.2 for a in anchors)
            assert np.nextafter(x[0],0)==c["archived_gamma"]
            ax.scatter(np.asarray(roots)/g0,[.2]*len(roots),facecolors="white",edgecolors=BLUE,s=25,lw=.9,zorder=5)
            ax.scatter([a["gamma"]/g0 for a in anchors],[a["gradient"] for a in anchors],s=7,color="#444444",zorder=4)
            rows.extend(dict(figure="MDM",example=label,panel="right_anchor",gamma=a["gamma"],gamma_ratio=a["gamma"]/g0,gradient=a["gradient"]) for a in anchors)
            mdm_diagnostics["right_anchor_probes"]=anchors
        mdm_diagnostics[label]=dict(roots=root_records,max_grid_gradient=float(gradients.max()))
        rows.extend(dict(figure="MDM",example=label,panel="threshold_root",gamma=r["gamma"],gamma_ratio=r["gamma"]/g0,gradient=r["gradient"],beta=r["beta"]) for r in root_records)
        axes[row,0].set_title(title+f" · 第{c['group']}组",loc="left",pad=14,fontsize=9)
        selected_g=c["at_selected_location"]["gamma"]
        p=(np.arange(1,len(x)+1)-.3)/(len(x)+.4)
        u=-np.log1p(-p)
        bs=np.unique(np.r_[np.linspace(.3,15,600),c["archived_beta"],c["true_beta"]])
        sigma=[np.std((x-selected_g)*u**(-1/b),ddof=1)/eta for b in bs]
        ax=axes[row,1]
        ax.plot(bs,sigma,color=BLUE,lw=1.15)
        ax.set(xlim=(0,16),xticks=[0,4,8,12,16],ylim=(0,.6),yticks=[0,.2,.4,.6],xlabel=r"$\beta$",ylabel=r"$\sigma(\beta,\hat\gamma)/\eta_0$")
        ax.axvline(c["true_beta"],color=GRAY,lw=.7,ls="--")
        star(ax,c["archived_beta"],c["at_selected_location"]["sigma"]/eta)
        ax=axes[row,2]
        for b,color in [(c["true_beta"],GRAY),(c["archived_beta"],BROWN)]:
            values=(x-selected_g)*u**(-1/b)/eta
            ax.plot(np.arange(1,len(x)+1),values,color=color,lw=1,marker="o",ms=3.8)
            rows.extend(dict(figure="MDM",example=label,panel="pseudo_scale",rank=i,beta=float(b),value=float(v)) for i,v in enumerate(values,1))
        ax.set(xlim=(.6,7.4),xticks=list(range(1,8)),ylim=(0,1.6),yticks=[0,.4,.8,1.2,1.6],xlabel=r"$i$",ylabel=r"$\eta_i/\eta_0$")
        rows.extend(dict(figure="MDM",example=label,panel="gradient",gamma=float(g),gamma_ratio=float(g/g0),gradient=float(v["finite_gradient"]),beta=float(v["beta"])) for g,v in zip(gs,profiles))
        rows.extend(dict(figure="MDM",example=label,panel="conditional_sigma",beta=float(b),sigma_ratio=float(s)) for b,s in zip(bs,sigma))
    pseudo_legend=[Line2D([0],[0],color=GRAY,marker="o",ms=3,lw=1,label="真β的伪尺度"),
                   Line2D([0],[0],color=BROWN,marker="o",ms=3,lw=1,label="原β的伪尺度"),result_legend[1],
                   Line2D([0],[0],marker="o",mfc="white",mec=BLUE,ls="none",ms=4,label="梯度交点"),
                   Line2D([0],[0],marker="o",color="#444444",ls="none",ms=3,label="右端探测")]
    finish(fig,axes,"MDM",mdm_labels,"A right threshold root lowers shape; near-edge anchor probes miss two interior crossings and trigger the archived endpoint fallback.",pseudo_legend)

    fig,axes=canvas()
    wmle_labels=["WMLE_low","WMLE_high"]
    for row,(label,title) in enumerate(zip(wmle_labels,["右侧交点低估","左侧交点高估"])):
        c,x,eta,g0=context(label)
        ranks=np.arange(1,len(x)+1)
        ax=axes[row,0]
        for gamma,color in [(g0,GRAY),(c["archived_gamma"],BROWN)]:
            values=(x-gamma)/eta
            ax.plot(ranks,values,color=color,lw=1,marker="o",ms=3.8)
            rows.extend(dict(figure="WMLE",example=label,panel="distance",rank=int(i),gamma=float(gamma),value=float(v)) for i,v in zip(ranks,values))
        ax.set(xlim=(.6,7.4),xticks=ranks,ylim=(0,2),yticks=[0,.5,1,1.5,2],xlabel=r"$i$",ylabel=r"$d_i/\eta_0$")
        ax.set_title(title+f" · 第{c['group']}组",loc="left",pad=14,fontsize=9)
        gs=gamma_grid(c,x,start=.9,end=1.17,count=220)
        bs=np.linspace(.4,9,190)
        logs=np.log(x[None,:]-gs[:,None])
        centered=logs-logs.mean(axis=1)[:,None]
        power=bs[None,:,None]*centered[:,None,:]
        weights=np.exp(power-power.max(axis=2)[:,:,None])
        weights/=weights.sum(axis=2)[:,:,None]
        t1=wmle.get_weight_j2(len(x))/bs[None,:]-np.sum(weights*centered[:,None,:],axis=2)
        logratio=logs.mean(axis=1)[:,None]+logsumexp(power,axis=2)-logsumexp((bs[None,:,None]-1)*centered[:,None,:],axis=2)
        j3=np.asarray([wmle.get_weight_j3(len(x),float(b)) for b in bs])
        t2=np.mean(1/(x[None,:]-gs[:,None]),axis=1)[:,None]*np.exp(logratio)-j3[None,:]
        ax=axes[row,1]
        ax.contour(gs/g0,bs,t1.T,levels=[0],colors=[BLUE],linewidths=1.2)
        ax.contour(gs/g0,bs,t2.T,levels=[0],colors=[BROWN],linewidths=1.2)
        ax.scatter([1],[c["true_beta"]],marker="D",facecolors="white",edgecolors=GRAY,s=25,lw=.8,zorder=5)
        star(ax,c["archived_gamma"]/g0,c["archived_beta"])
        ax.set(xlim=(.9,1.17),xticks=[.9,1,1.1,1.15],ylim=(0,9),yticks=[0,3,6,9],xlabel=r"$\gamma/\gamma_0$",ylabel=r"$\beta$")
        ax.xaxis.set_major_formatter(StrMethodFormatter("{x:g}"))
        if row==0:ax.legend(handles=[Line2D([0],[0],color=BLUE,lw=1.2,label=r"$T_1=0$"),Line2D([0],[0],color=BROWN,lw=1.2,label=r"$T_2=0$")],loc="upper right",fontsize=7)
        profiles=[helper.wmle_profile(x,float(g),wmle) for g in gs]
        ax=axes[row,2]
        position_axis(ax,(.9,1.17),[.9,1,1.1,1.15],r"$T_2[\hat\beta(\gamma),\gamma]$",(-.08,.08),[-.08,-.04,0,.04,.08])
        ax.plot(gs/g0,[p["t2"] for p in profiles],color="#444444",lw=1.15)
        ax.axhline(0,color=GRAY,lw=.7,ls=":")
        star(ax,c["archived_gamma"]/g0,c["at_selected_location"]["t2"])
        for key,value in [("gamma",gs),("beta",bs),("T1",t1),("T2",t2)]:grids[label+"_"+key]=value
        rows.extend(dict(figure="WMLE",example=label,panel="shape_zero_branch",gamma=float(g),gamma_ratio=float(g/g0),beta=float(p["beta"]),t1=float(p["t1"]),t2=float(p["t2"])) for g,p in zip(gs,profiles))
    distance_legend=[Line2D([0],[0],color=GRAY,marker="o",ms=3,lw=1,label="真位置距离"),
                     Line2D([0],[0],color=BROWN,marker="o",ms=3,lw=1,label="原位置距离"),result_legend[1],
                     Line2D([0],[0],marker="D",mfc="white",mec=GRAY,ls="none",ms=4,label="真参数")]
    finish(fig,axes,"WMLE",wmle_labels,"The two original calibration equations intersect on opposite sides and support opposite shape deviations.",distance_legend)

    fig,axes=canvas()
    mmle_labels=["MMLE_low","MMLE_high_deletion","MMLE_high_concentrated"]
    for col,(label,title) in enumerate(zip(mmle_labels,["最小值平移低估","删点后形状高估","完整样本已集中"])):
        c,x,eta,g0=context(label)
        ranks=np.arange(1,len(x)+1)
        ax=axes[0,col]
        ax.plot(ranks,(x-g0)/eta,color=BLUE,lw=1,marker="o",ms=3.8)
        ax.plot(ranks[1:],(x[1:]-x[0])/eta,color=BROWN,lw=1,marker="o",ms=3.8)
        ax.scatter([1],[0],marker="x",s=23,color=BROWN,lw=1)
        ax.set(xlim=(.6,7.4),xticks=ranks,ylim=(0,1.8),yticks=[0,.6,1.2,1.8],xlabel=r"$i$",ylabel=r"$d_i/\eta_0$")
        ax.set_title(title+f" · 第{c['group']}组",loc="left",pad=14,fontsize=9)
        bs=np.unique(np.r_[np.linspace(.3,16,650),c["archived_beta"],c["at_true_location"]["beta"],c["complete_sample_at_true_location"]["beta"]])
        ax=axes[1,col]
        for stage,values,gamma,color in [("complete_true",x,g0,BLUE),("retained_true",x[1:],g0,GRAY),("retained_shifted",x[1:],x[0],BROWN)]:
            logs=np.log(values-gamma)
            centered=logs-logs.mean()
            powers=bs[:,None]*centered[None,:]
            weights=np.exp(powers-powers.max(axis=1)[:,None]);weights/=weights.sum(axis=1)[:,None]
            score=1/bs-np.sum(weights*centered[None,:],axis=1)
            ax.plot(bs,score,color=color,lw=1.15)
            rows.extend(dict(figure="MMLE",example=label,panel="shape_score",kind=stage,beta=float(b),score=float(s)) for b,s in zip(bs,score))
        ax.axhline(0,color="#555555",lw=.65,ls=":")
        ax.axvline(c["true_beta"],color="#AAAAAA",lw=.65,ls="--")
        star(ax,c["archived_beta"],0)
        ax.set(xlim=(0,16),xticks=[0,4,8,12,16],ylim=(-.3,.6),yticks=[-.3,0,.3,.6],xlabel=r"$\beta$",ylabel=r"$U_\beta(\beta;\gamma)$")
        rows.extend(dict(figure="MMLE",example=label,panel="distance",rank=int(i),original_distance=float((v-g0)/eta),shifted_distance=float((v-x[0])/eta),retained=bool(i>1)) for i,v in zip(ranks,x))
    mmle_legend=[Line2D([0],[0],color=BLUE,lw=1,label="完整样本·真位置"),Line2D([0],[0],color=GRAY,lw=1,label="删点·真位置"),Line2D([0],[0],color=BROWN,lw=1,label="删点·最小值平移"),result_legend[1]]
    finish(fig,axes,"MMLE",mmle_labels,"Minimum shifting lowers shape; deletion or pre-existing concentration keeps some shapes above the high criterion.",mmle_legend)

    csv_path=HERE/"20261010-典型情形图数据.csv"
    names=list(dict.fromkeys(key for row in rows for key in row))
    with csv_path.open("w",encoding="utf-8",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=names,lineterminator="\n")
        writer.writeheader();writer.writerows(rows)
    np.savez_compressed(HERE/"20261010-典型情形WMLE网格.npz",**grids)
    report_path=ROOT/"报告2：小样本情况下的明显异常估计.md"
    report=report_path.read_text(encoding="utf-8")
    first=report.split("\n## 2",1)[0]
    figure_names=["图1_明显异常估计频率.png","图2_位置左移与参数补偿.png",
                  "典型情形_LSE内部.png","典型情形_LRE.png","典型情形_MLE.png",
                  "典型情形_MDM.png","典型情形_WMLE.png","典型情形_MMLE.png",
                  "固定位置的回归与形状得分.png"]
    plotted_cases={(cases[label]["method"],cases[label]["case"])
                   for figure in figures.values() for label in figure["sample_labels"]}
    plotted_cases.add((cases["LSE_zero"]["method"],cases["LSE_zero"]["case"]))
    expected_cases={(c["method"],c["case"]) for c in cases.values()}
    comparable_axes={}
    for name,figure in figures.items():
        grouped={}
        for axis in figure["axes"]:
            key=(axis["xlabel"],axis["ylabel"])
            signature={k:axis[k] for k in ["xlim","ylim","xticks","yticks"]}
            assert key not in grouped or grouped[key]==signature,(name,key)
            grouped[key]=signature
        comparable_axes[name]=True
    image_links=re.findall(r"!\[[^\]]*\]\(([^)]+)\)",report)
    document_checks=dict(report_sha256=helper.digest(report_path),
        chapter1_unchanged=hashlib.sha256(first.encode()).hexdigest()=="97b9989c15030908053b7ef70859a191df224b05220ecdbdcf325e4d04ec76e5",
        figure_order=re.findall(r"\*\*图(\d+)｜",report)==list(map(str,range(1,10))),
        image_order=[Path(p).name for p in image_links]==figure_names,
        image_links_exist=all((report_path.parent/p).is_file() for p in image_links),
        all_15_original_cases_illustrated=plotted_cases==expected_cases and len(plotted_cases)==15,
        same_quantity_axes=comparable_axes,
        six_method_sections=len(re.findall(r"^#### 2\.1\.\d+　",report,re.M))==6,
        math_delimiters_paired=report.count("$$")%2==0)
    assert all(v for k,v in document_checks.items() if k!="report_sha256")
    output=dict(backend="Python",export="PNG only",archetype="quantitative grid",figures=figures,
        sample_rule="Keep the examples already analyzed in the report; no new sample selection or resampling.",
        units="gamma/gamma_true and distances/eta_true for cross-combination comparison; physical gamma and all observations retained in source data.",
        equations="Frozen regression reference points; conditional likelihood score; MDM finite gradient/sigma/pseudo-scales; original WMLE joint equations and shape-zero branch; MMLE complete/retained shape scores.",
        source_sha256=hashes,old_png_sha256=old_png,
        sources_unchanged=all(helper.digest(Path(p))==h for p,h in hashes.items()),
        previous_png_unchanged=all(helper.digest(Path(p))==h for p,h in old_png.items()),
        wmle_grid_file="20261010-典型情形WMLE网格.npz",curve_rows=len(rows),
        mdm_exact_frozen_gradient=mdm_diagnostics,
        document_checks=document_checks,
        endpoint_gradient_note="MDM right-edge fallback is shown by a vertical position line, not a fabricated threshold intersection.")
    assert output["sources_unchanged"] and output["previous_png_unchanged"]
    (HERE/"20261010-典型情形制图核验.json").write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding="utf-8")
    print("PASS: six PNGs, every missing case illustrated with the reported original sample; original data/dependencies and prior PNG unchanged")


if __name__=="__main__":main()
