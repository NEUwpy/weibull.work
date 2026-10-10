"""Actual-method process checks and paired MDM/WMLE/MMLE mechanism panels.

Use archived samples and estimates. WMLE panels plot both equation-zero loci
in the shape/location plane; MMLE panels plot the construction on observations.
Only conditional calculations and plotting, without calling a formal run().
"""
from pathlib import Path
import csv
import importlib.util
import json
import re
import sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.special import logsumexp

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
IMAGES = HERE.parents[1]/"图片"


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


helper = load(HERE/"逐方法机制复核.py", "joint_helper")
plt.rcParams.update({"font.family":"sans-serif",
    "font.sans-serif":["Microsoft YaHei","Arial","DejaVu Sans"],
    "font.size":9,"axes.linewidth":.65,"axes.spines.top":False,
    "axes.spines.right":False,"legend.frameon":False,
    "axes.unicode_minus":False,"xtick.major.width":.65,"ytick.major.width":.65})
BLUE, BROWN = "#487A8B", "#B67550"


def main():
    full = json.loads((HERE/"全量流程定位.json").read_text(encoding="utf-8"))
    paired = json.loads((HERE/"逐方法机制复核.json").read_text(encoding="utf-8"))
    source_hashes = dict(full["source_sha256"])
    for f in [Path(__file__), HERE/"全量流程定位.csv", HERE/"全量流程定位.json",
              HERE/"逐方法机制复核.json"]:
        source_hashes[str(f)] = helper.digest(f)
    assert all(helper.digest(Path(f)) == h for f,h in source_hashes.items())
    records = list(csv.DictReader((HERE/"全量流程定位.csv").open(encoding="utf-8")))
    bad = [r for r in records if r["abnormal"] == "True"]
    checks = full["mechanism_checks"]
    assert len(bad) == 963
    assert checks["lse_selected_r2_above_true"] == 243
    assert checks["lre_selected_r2_above_true"] == 255
    assert checks["mle_selected_ll_not_below_true"] == 185
    assert checks["mle_true_ll_above_selected"] == 12
    assert checks["wmle_direction_matches_equation_sign"] == 84
    assert checks["wmle_max_squared_residual"] < 1e-8
    assert sum(r["archived_root_solver"] == "right_edge_fit" for r in bad if r["method"].startswith("MDM")) == 1
    assert all(float(r["gamma_hat"]) == float(r["sample_min"]) for r in bad if r["method"] == "MMLE")
    # Point-level source for the existing normal/abnormal pairs.
    point_records = []
    for label, record in paired["samples"].items():
        for method, row in record["archived_all_six"].items():
            point_records.append(dict(pair=label, combination=record["combination"],
                n=record["n"], group=record["group"], method=method,
                beta=row["beta_hat"], eta=row["eta_hat"], gamma=row["gamma_hat"]))
    with (HERE/"20261010-逐法配对结果.csv").open("w",encoding="utf-8",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=list(point_records[0]),lineterminator="\n")
        writer.writeheader();writer.writerows(point_records)

    program=ROOT/"W(5,100,500)/20261007-暂存样本补齐/程序"
    snapshot=program/"依赖快照/python"
    sys.path.insert(0,str(snapshot))
    wmle=helper.load_module(snapshot/"methods/wmle.py","joint_frozen_wmle")
    archive=json.loads((program/"中间数据/matrix.json").read_text(encoding="utf-8"))
    assert helper.digest(snapshot/"methods/wmle.py") == archive["config"]["dependency_hashes"]["methods/wmle.py"]
    curves, grids, pair_stats = [], {}, []
    fig,axes=plt.subplots(2,3,figsize=(9.1,5.6))
    for row,(label,color) in enumerate([("low_control",BLUE),("low",BROWN)]):
        rec=paired["samples"][label]
        x=np.asarray(rec["values"])
        n=len(x)
        # MDM: actual profile-gradient threshold, with the selected root marked.
        gamma=np.unique(np.r_[np.linspace(480,x[0]-.05,180),500,
            rec["methods"]["MDM"]["archived"]["gamma_hat"]])
        profiles=[helper.mdm_profile(x,float(g)) for g in gamma]
        ax=axes[row,0]
        ax.plot(gamma,[p["gradient"] for p in profiles],color=color,lw=1.1)
        ax.axhline(.2,color="#707070",ls="--",lw=.65)
        ax.axvline(500,color="#707070",ls="--",lw=.65)
        selected=rec["methods"]["MDM"]["archived"]
        root=helper.mdm_profile(x,selected["gamma_hat"])
        assert abs(root["gradient"]-.2)<1e-5
        ax.scatter([selected["gamma_hat"]],[root["gradient"]],s=27,color=color,
                   edgecolors="white",linewidths=.5,zorder=4)
        ax.set(xlim=(480,580),ylim=(-.1,.6),xticks=[480,500,520,540,560,580],
               yticks=[0,.2,.4,.6],xlabel=r"$\gamma$",ylabel=r"$g(\gamma)$")
        curves.extend(dict(method="MDM",group=rec["group"],gamma=float(g),
            gradient=p["gradient"],beta=p["beta"]) for g,p in zip(gamma,profiles))

        # WMLE: the two original residuals are evaluated across beta/gamma.
        gs=np.linspace(480,x[0]-.05,200)
        bs=np.linspace(.4,9,180)
        logs=np.log(x[None,:]-gs[:,None])
        z=logs-logs.mean(axis=1)[:,None]
        power=bs[None,:,None]*z[:,None,:]
        weights=np.exp(power-power.max(axis=2)[:,:,None])
        weights/=weights.sum(axis=2)[:,:,None]
        t1=wmle.get_weight_j2(n)/bs[None,:]-np.sum(weights*z[:,None,:],axis=2)
        logratio=logs.mean(axis=1)[:,None]+logsumexp(power,axis=2)-logsumexp((bs[None,:,None]-1)*z[:,None,:],axis=2)
        j3=np.asarray([wmle.get_weight_j3(n,float(b)) for b in bs])
        t2=np.mean(1/(x[None,:]-gs[:,None]),axis=1)[:,None]*np.exp(logratio)-j3[None,:]
        ax=axes[row,1]
        ax.contour(gs,bs,t1.T,levels=[0],colors=[BLUE],linewidths=1.1)
        ax.contour(gs,bs,t2.T,levels=[0],colors=[BROWN],linewidths=1.1)
        selected=rec["methods"]["WMLE"]["archived"]
        p=helper.wmle_profile(x,selected["gamma_hat"],wmle)
        assert abs(p["t1"])<1e-7 and abs(p["t2"])<1e-7
        assert abs(np.log(p["beta"]/selected["beta_hat"]))<2e-5
        ax.scatter([500],[5],marker="D",s=25,facecolors="white",edgecolors="#777777",lw=.7,zorder=4)
        ax.scatter([selected["gamma_hat"]],[selected["beta_hat"]],s=27,color="#333333",
                   edgecolors="white",linewidths=.5,zorder=4)
        ax.set(xlim=(480,580),ylim=(0,9),xticks=[480,500,520,540,560,580],
               yticks=[0,3,6,9],xlabel=r"$\gamma$",ylabel=r"$\beta$")
        if row==0:
            from matplotlib.lines import Line2D
            ax.legend(handles=[Line2D([0],[0],color=BLUE,lw=1,label=r"$T_1=0$"),
                               Line2D([0],[0],color=BROWN,lw=1,label=r"$T_2=0$")],
                      loc="upper right",fontsize=7)
        grids[f"group{rec['group']}_gamma"]=gs
        grids[f"group{rec['group']}_beta"]=bs
        grids[f"group{rec['group']}_T1"]=t1
        grids[f"group{rec['group']}_T2"]=t2

        # MMLE: observed distances before/after its minimum/deletion operation.
        ranks=np.arange(1,n+1)
        original=(x-500)/100
        shifted=(x-x[0])/100
        ax=axes[row,2]
        ax.plot(ranks,original,color="#888888",lw=.85,marker="o",ms=3.5,
                markerfacecolor="white",markeredgewidth=.7,label=r"$\gamma=500$")
        ax.plot(ranks[1:],shifted[1:],color=color,lw=1.1,marker="o",ms=3.5,
                label=r"$\gamma=x_{(1)}$")
        ax.scatter([1],[0],marker="x",s=19,color=color,lw=.85,zorder=4)
        ax.set(xlim=(.65,7.35),ylim=(-.04,1.5),xticks=ranks,yticks=[0,.5,1,1.5],
               xlabel=r"$i$",ylabel=r"$(x_{(i)}-\gamma)/100$")
        if row==0: ax.legend(loc="upper left",fontsize=7)
        curves.extend(dict(method="MMLE",group=rec["group"],rank=int(i),
                           original_distance=float(a),shifted_distance=float(b),
                           retained=bool(i>1)) for i,a,b in zip(ranks,original,shifted))
        for col,name in enumerate(["MDM","WMLE","MMLE"]):
            axes[row,col].text(-.15,1.06,chr(97+row*3+col),transform=axes[row,col].transAxes,
                               fontsize=11,fontweight="bold")
            if row==0: axes[row,col].set_title(name,loc="left",fontsize=9,pad=13)
        axes[row,0].text(.03,.90,f"第{rec['group']}组",transform=axes[row,0].transAxes,fontsize=8)
        pair_stats.append(dict(group=rec["group"],mdm=rec["methods"]["MDM"]["archived"],
            wmle=rec["methods"]["WMLE"]["archived"],mmle=rec["methods"]["MMLE"]["archived"],
            min_gap=float(x[0]-500), original_distance_cv=float(np.std(original[1:])/np.mean(original[1:])),
            retained_shifted_cv=float(np.std(shifted[1:])/np.mean(shifted[1:]))))
    from matplotlib.lines import Line2D
    fig.legend(handles=[Line2D([0],[0],marker="D",color="#777777",markerfacecolor="white",
        linestyle="none",markersize=4,label="真值"),
        Line2D([0],[0],marker="o",color="#333333",linestyle="none",markersize=4,label="所选解")],
        loc="lower center",ncol=2,bbox_to_anchor=(.54,.0),fontsize=8)
    fig.subplots_adjust(left=.08,right=.98,bottom=.13,top=.91,wspace=.43,hspace=.47)
    fig.savefig(IMAGES/"梯度联合方程与最小值构造.png",dpi=450,facecolor="white")
    plt.close(fig)
    np.savez_compressed(HERE/"20261010-WMLE联合方程网格.npz",**grids)
    keys=list(dict.fromkeys(k for r in curves for k in r))
    with (HERE/"20261010-构造过程图数据.csv").open("w",encoding="utf-8",newline="") as out:
        writer=csv.DictWriter(out,fieldnames=keys,lineterminator="\n")
        writer.writeheader();writer.writerows(curves)
    report=ROOT/"报告2：小样本情况下的明显异常估计.md"
    text=report.read_text(encoding="utf-8")
    appendix=(HERE.parent/"README.md").read_text(encoding="utf-8")
    first,body=text.split("\n## 2",1)
    import hashlib
    document_checks=dict(
        report_sha256=helper.digest(report),
        chapter1_unchanged=hashlib.sha256(first.encode()).hexdigest()=="97b9989c15030908053b7ef70859a191df224b05220ecdbdcf325e4d04ec76e5",
        figure_order=re.findall(r"\*\*图(\d+)｜",text)==["1","2","3","4","5"],
        causal_split_removed="固定γ，区分异常的作用环节" not in body and "退出异常组" not in body and "948条" not in body,
        prose_has_no_defensive_clauses=all(s not in body for s in ["不能","并不","不代表","不等于","仅用于","而不是","不意味着"]),
        chapter2_has_two_sections=re.findall(r"^### (2\.\d+)　(.+)$",body,re.M)==[
            ("2.1","各方法的异常形成机制"),("2.2","样本条件与方法差异")],
        method_counts_match=all(f"| {m} | {v['over']} | {v['under']} |" in appendix for m,v in full["methods"].items()),
        math_delimiters_paired=text.count("$$")%2==0)
    assert all(v for k,v in document_checks.items() if k!="report_sha256")
    qa=dict(method_checks=checks,method_counts=full["methods"],paired=pair_stats,document_checks=document_checks,
        sample_design="W(5,100,500), n=7, groups10/11; all three relevant original methods non-abnormal/abnormal",
        figure_contract="MDM threshold; WMLE joint zero-locus intersection; MMLE observed distance construction",
        axes=dict(gamma=[480,580],gradient=[-.1,.6],wmle_beta=[0,9],rank=[1,7],distance=[-.04,1.5]),
        equations="MDM envelope gradient; exact frozen WMLE T1,T2; MMLE subtract original minimum/delete rank1",
        source_sha256=source_hashes,sources_unchanged=all(helper.digest(Path(f))==h for f,h in source_hashes.items()),
        backend="Python",export="PNG only")
    assert qa["sources_unchanged"]
    (HERE/"20261010-逐法流程核验.json").write_text(json.dumps(qa,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print("PASS: all963 original-method checks; MDM threshold, joint WMLE equations and observed MMLE construction; sources unchanged")


if __name__=="__main__": main()
