"""从存档50点样本固定随机删点，展示同一路径n减少时各方法拟合；不并入正式Monte Carlo。"""
from pathlib import Path
import sys,json,hashlib,csv
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STUDY=Path(__file__).resolve().parents[2]
CORE=STUDY/"程序/计算实现-20261016"
sys.path.insert(0,str(CORE))
from studies.common.runner import run_method
METHODS=[("mdm","MDM",{"offset":.1}), ("wmle","WMLE",{}),("lse","LSE",{}),("mmle","K–R",{})]
COLORS=["#0072B2","#D55E00","#009E73","#CC79A7"]
NS=[50,20,15,10,7]
IDS=[1055,474]
OUT=STUDY/"结果呈现/分析数据"
ASSETS=STUDY/"reviewbyhtml/方法对比-v1.0/assets"

def cdf(t,b,e,g):return -np.expm1(-np.maximum((t-g)/e,0)**b)

def nested_samples(frame, source_ids=IDS):
    """Restore the existing fixed-permutation paths without new sampling."""
    samples = {}
    for sid in source_ids:
        row = frame.loc[frame["样本编号"].eq(sid)].iloc[0]
        x = row[[f"观测值{i}" for i in range(1,51)]].to_numpy(float)
        order = np.random.default_rng(20261023+sid).permutation(50)
        for k, n in enumerate(NS):
            y = np.sort(x[order[:n]])
            if k:
                assert np.isin(y, samples[sid,NS[k-1]]).all()
            samples[sid,n] = y
    return samples


def main():
    source=STUDY/"结果/W5,1000,500/估计结果/n50.csv"
    before=hashlib.sha256(source.read_bytes()).hexdigest()
    frame=pd.read_csv(source,float_precision="round_trip")
    cache=OUT/"嵌套样本拟合.csv"
    samples=nested_samples(frame); rows=[]
    if cache.exists():
        rows=list(csv.DictReader(cache.open(encoding="utf-8-sig",newline="")))
        for r in rows:
            sid,n=int(r["source_id"]),int(r["n"])
            assert json.loads(r["observations"])==samples[sid,n].tolist()
    else:
        for sid in IDS:
            for n in NS:
                y=samples[sid,n]
                for mid,label,kwargs in METHODS:
                    result=run_method(mid,y,**kwargs)
                    r=dict(source_id=sid,n=n,method=label,converged=result["converged"],beta=result["beta_hat"],eta=result["eta_hat"],gamma=result["gamma_hat"],observations=json.dumps(y.tolist()),diagnostics=json.dumps(result.get("extra"),ensure_ascii=False))
                    rows.append(r)
                    print(sid,n,label,result["converged"],flush=True)
        with cache.open("w",encoding="utf-8-sig",newline="") as f:
            writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    assert len(rows)==40
    lookup={(int(r["source_id"]),int(r["n"]),r["method"]):r for r in rows}
    plt.rcParams.update({"font.family":"Microsoft YaHei","font.size":12,"axes.spines.top":False,"axes.spines.right":False,"axes.unicode_minus":False})
    diagnostics=[]
    t=np.linspace(400,2100,1200)
    for n in NS:
        fig,axes=plt.subplots(1,2,figsize=(12,4.8),sharex=True,sharey=True)
        fig.subplots_adjust(left=.075,right=.985,bottom=.16,top=.80,wspace=.1)
        for ax,sid in zip(axes,IDS):
            y=samples[sid,n]
            ax.plot(t,cdf(t,5,1000,500),"--",color="#333333",lw=2,label="真实分布")
            ax.scatter(y,(np.arange(1,n+1)-.5)/n,s=23,c="#333333",zorder=5,label="样本点")
            ax.plot(y,np.full(n,-.025),"|",color="#333333",ms=9)
            curves=[]
            for (mid,label,kwargs),color in zip(METHODS,COLORS):
                r=lookup[sid,n,label]
                valid=str(r["converged"]).lower()=="true" and all(r[k] not in (None,"") for k in ["beta","eta","gamma"])
                if valid:
                    p=[float(r[k]) for k in ["beta","eta","gamma"]]
                    fit=cdf(t,*p);curves.append(fit)
                    ax.plot(t,fit,color=color,lw=1.9,label=label)
                else: ax.plot([],[],color=color,label=label+"（未收敛）")
            ax.set(xlim=(400,2100),ylim=(-.06,1.02),xlabel="寿命 t",title=f"样本 {sid}，n = {n}")
            if len(curves)>1:diagnostics.append(dict(sid=sid,n=n,max_cdf_spread=float(np.ptp(np.array(curves),axis=0).max())))
        axes[0].set_ylabel("累计概率")
        fig.legend(*axes[0].get_legend_handles_labels(),ncol=6,loc="upper center",frameon=False,fontsize=11)
        fig.savefig(ASSETS/f"嵌套样本拟合_n{n}.png",dpi=200,facecolor="white");plt.close(fig)
    assert hashlib.sha256(source.read_bytes()).hexdigest()==before
    manifest=dict(source=str(source.relative_to(STUDY)),source_sha256=before,ids=IDS,n=NS,seed_rule="20261023+source_id",selection="沿用前一轮编号1055与474；从n50表取其观测，不按拟合好坏筛选；与此前n7表同编号不是同组观测。",construction="固定随机排列，保留前n个，排序后拟合；严禁只留排序最小的n个。",scope="两条嵌套删点路径，仅用于过程示例，不并入原1200次独立条件统计。",diagnostics=diagnostics)
    (OUT/"嵌套样本拟合核对.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(diagnostics,ensure_ascii=False))

if __name__=="__main__":main()
