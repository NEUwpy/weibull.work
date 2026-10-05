"""Paired descriptive opportunity analysis; no neural estimator is trained."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

STUDY=Path(__file__).resolve().parents[1]
OUT=STUDY/"results/j3_scan_v1"
KEYS=["cohort","beta","eta","gamma","sample_size"]
LABELS={"original":"原WMLE", "fixed_global":"全组最佳固定c（同数据）",
        "fixed_n":"按n最佳固定c（同数据）", "fixed_cell":"按真参数格最佳固定c（事后）",
        "oracle":"逐样本事后最优c", "cv_fixed_global":"五折固定c",
        "cv_fixed_n":"五折按n固定c"}


def summarize(g):
    v=g[g.valid]
    return dict(total=len(g),valid=len(v),failure_rate=1-len(v)/len(g),
                bad_rate=g.bad.mean(),extreme50_rate_valid=(v.E>=.5).mean(),
                extreme100_rate_valid=(v.E>=1.).mean(),
                mean_E_valid=v.E.mean(),median_E_valid=v.E.median(),
                p95_E_valid=v.E.quantile(.95),max_E_valid=v.E.max(),
                mean_capped_loss=g.capped_loss.mean(),
                beta_rmse_valid=np.sqrt((v.e_beta**2).mean()),
                eta_rmse_valid=np.sqrt((v.e_eta**2).mean()),
                gamma_rmse_valid=np.sqrt((v.e_gamma**2).mean()))


def grouped(d,keys):
    return pd.DataFrame([{**dict(zip(keys,k if isinstance(k,tuple) else (k,))),**summarize(g)}
                         for k,g in d.groupby(keys,sort=True)])


def choose_fixed(g):
    scores=g.groupby("c",as_index=False).agg(bad_rate=("bad","mean"),
                capped_loss=("capped_loss","mean"),valid_rate=("valid","mean"))
    scores["distance"]=(scores.c-1).abs()
    return float(scores.sort_values(["bad_rate","capped_loss","valid_rate","distance","c"],
                                    ascending=[True,True,False,True,True]).iloc[0].c)


def table(d,columns):
    lines=["| "+" | ".join(columns)+" |","|"+"---|"*len(columns)]
    for row in d[columns].itertuples(index=False,name=None):
        lines.append("| "+" | ".join(f"{v:.4g}" if isinstance(v,float) else str(v) for v in row)+" |")
    return "\n".join(lines)


def main():
    manifest=json.loads((OUT/"manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"]=="complete"
    index=pd.read_csv(OUT/"sample_index.csv")
    scan=pd.concat([pd.read_csv(OUT/r["path"]) for r in manifest["files"]],ignore_index=True)
    assert len(scan)==81000 and not scan.duplicated(["row_id","c"]).any()
    context=index[["row_id","cohort","beta","eta","gamma","sample_size","repeat_id","cell_id"]]
    d=scan.drop(columns="cell_id").merge(context,on="row_id",validate="many_to_one")
    for name,scale in [("beta","beta"),("eta","eta"),("gamma","eta")]:
        d["e_"+name]=((d[name+"_hat"]-d[name])/d[scale]).where(d.valid)
    d["E"]=d[["e_beta","e_eta","e_gamma"]].abs().max(axis=1,skipna=False)
    d["bad"]=~d.valid | (d.E>=.5)
    d["capped_loss"]=d.E.clip(upper=2).fillna(2)
    d["distance"]=(d.c-1).abs()
    d["fold"]=d.repeat_id%5
    base=d[d.c.eq(1)].sort_values("row_id")
    assert base.valid.to_numpy().tolist()==index.sort_values("row_id").valid.to_numpy().tolist()
    assert np.allclose(base[["beta_hat","eta_hat","gamma_hat"]],
                       index.sort_values("row_id")[["beta_hat","eta_hat","gamma_hat"]],equal_nan=True,atol=1e-6,rtol=1e-9)
    selections=[]
    chosen=[]
    for cohort,g in d.groupby("cohort"):
        c=choose_fixed(g)
        chosen.append(dict(cohort=cohort,scope="global",sample_size=None,cell_id=None,fold=None,c=c))
        selections.append(g[g.c.eq(1)].assign(policy="original"))
        selections.append(g[g.c.eq(c)].assign(policy="fixed_global"))
        for n,part in g.groupby("sample_size"):
            cn=choose_fixed(part)
            chosen.append(dict(cohort=cohort,scope="n",sample_size=n,cell_id=None,fold=None,c=cn))
            selections.append(part[part.c.eq(cn)].assign(policy="fixed_n"))
        for cell,part in g.groupby("cell_id"):
            cc=choose_fixed(part)
            chosen.append(dict(cohort=cohort,scope="cell",sample_size=part.sample_size.iloc[0],cell_id=cell,fold=None,c=cc))
            selections.append(part[part.c.eq(cc)].assign(policy="fixed_cell"))
        oracle=g.assign(order=g.E.fillna(np.inf)).sort_values(
            ["row_id","order","distance","c"]).drop_duplicates("row_id")
        selections.append(oracle.assign(policy="oracle").drop(columns="order"))
        for fold in range(5):
            train=g[g.fold.ne(fold)]
            test=g[g.fold.eq(fold)]
            cf=choose_fixed(train)
            chosen.append(dict(cohort=cohort,scope="cv_global",sample_size=None,cell_id=None,fold=fold,c=cf))
            selections.append(test[test.c.eq(cf)].assign(policy="cv_fixed_global"))
            for n,part in test.groupby("sample_size"):
                cn=choose_fixed(train[train.sample_size.eq(n)])
                chosen.append(dict(cohort=cohort,scope="cv_n",sample_size=n,cell_id=None,fold=fold,c=cn))
                selections.append(part[part.c.eq(cn)].assign(policy="cv_fixed_n"))
    selected=pd.concat(selections,ignore_index=True)
    assert len(selected)==4500*len(LABELS)
    assert not selected.duplicated(["row_id","policy"]).any()
    chosen=pd.DataFrame(chosen)
    chosen.to_csv(OUT/"selected_fixed_coefficients.csv",index=False,encoding="utf-8-sig")
    selected.drop(columns=["protocol_hash"]).to_csv(OUT/"selected_rows.csv.gz",index=False,compression="gzip")
    overall=grouped(selected,["cohort","policy"])
    by_n=grouped(selected,["cohort","sample_size","policy"])
    cells=grouped(selected,KEYS+["policy"])
    overall.to_csv(OUT/"policy_summary.csv",index=False,encoding="utf-8-sig")
    by_n.to_csv(OUT/"policy_by_n.csv",index=False,encoding="utf-8-sig")
    cells.to_csv(OUT/"policy_by_cell.csv",index=False,encoding="utf-8-sig")
    curve=grouped(d,["cohort","sample_size","c"])
    curve.to_csv(OUT/"coefficient_curves.csv",index=False,encoding="utf-8-sig")
    grouped(d,KEYS+["c"]).to_csv(OUT/"coefficient_curves_by_cell.csv",index=False,encoding="utf-8-sig")
    transitions=[]
    for (cohort,policy),g in selected.groupby(["cohort","policy"]):
        pair=g.merge(base[["row_id","valid","bad","E"]],on="row_id",suffixes=("","_original"),validate="one_to_one")
        transitions.append(dict(cohort=cohort,policy=policy,total=len(g),
             rescued_bad=int((pair.bad_original & ~pair.bad).sum()),
             harmed_good=int((~pair.bad_original & pair.bad).sum()),
             failures_rescued=int((~pair.valid_original & pair.valid).sum()),
             new_failures=int((pair.valid_original & ~pair.valid).sum()),
             good_E_worsened=int((~pair.bad_original & pair.valid & (pair.E>pair.E_original+1e-10)).sum())))
    trans=pd.DataFrame(transitions)
    trans.to_csv(OUT/"paired_transitions.csv",index=False,encoding="utf-8-sig")
    oracle=selected[selected.policy.eq("oracle")]
    assert trans.loc[trans.policy.eq("oracle"),"harmed_good"].eq(0).all()
    assert trans.loc[trans.policy.eq("oracle"),"good_E_worsened"].eq(0).all()
    oracle.groupby(["cohort","sample_size","c"]).size().rename("count").reset_index().to_csv(
        OUT/"oracle_coefficient_distribution.csv",index=False,encoding="utf-8-sig")
    edge=oracle.groupby("cohort").apply(lambda g:pd.Series(dict(
        lower_count=int((g.valid & g.c.eq(.7)).sum()),upper_count=int((g.valid & g.c.eq(1.5)).sum()),
        invalid_count=int((~g.valid).sum()),total=len(g))),include_groups=False).reset_index()
    edge.to_csv(OUT/"oracle_boundary_counts.csv",index=False,encoding="utf-8-sig")
    target=index[index.cohort.eq("historical_complete") & index.beta.eq(2) & index.eta.eq(1000) &
                 index.gamma.eq(500) & index.sample_size.eq(7) & index.repeat_id.eq(46)].iloc[0].row_id
    d[d.row_id.eq(target)].sort_values("c").to_csv(OUT/"motivating_sample47_curve.csv",index=False,encoding="utf-8-sig")
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    colors=["#0072B2","#D55E00","#009E73"]
    fig,axes=plt.subplots(1,2,figsize=(10,3.9))
    primary=curve[curve.cohort.eq("controlled_20260922")]
    for color,(n,part) in zip(colors,primary.groupby("sample_size")):
        part=part.sort_values("c")
        axes[0].plot(part.c,part.bad_rate,marker="o",ms=3,color=color,label=f"n={n}")
        axes[1].plot(part.c,part.failure_rate,marker="o",ms=3,color=color,label=f"n={n}")
    for ax in axes:
        ax.axvline(1,color="gray",ls="--",lw=.8)
        ax.set(xlabel="J3 multiplier c",ylim=(0,1.02))
        ax.legend(frameon=False);ax.grid(alpha=.18)
    axes[0].set_ylabel("Failure or E >= 0.5 / all draws")
    axes[1].set_ylabel("Failure / all draws")
    fig.suptitle("Controlled cohort: fixed-coefficient risk curves")
    fig.tight_layout()
    for ext in ["png","pdf"]:fig.savefig(OUT/f"fixed_coefficient_curves.{ext}",dpi=220)
    plt.close(fig)
    fig,ax=plt.subplots(figsize=(8,4.4))
    policies=["original","fixed_global","fixed_n","fixed_cell","oracle"]
    english=["Original","Global fixed","Fixed by n","Fixed by true cell","Sample oracle"]
    x=np.arange(3);width=.15
    for i,(policy,label) in enumerate(zip(policies,english)):
        part=by_n[by_n.cohort.eq("controlled_20260922") & by_n.policy.eq(policy)].sort_values("sample_size")
        ax.bar(x+(i-2)*width,part.bad_rate,width,label=label)
    ax.set(xticks=x,xticklabels=["n=7","n=15","n=30"],ylabel="Failure or E >= 0.5 / all draws",ylim=(0,1))
    ax.legend(frameon=False,fontsize=8,ncol=2)
    ax.grid(axis="y",alpha=.18)
    ax.set_title("J3 opportunity within the scanned grid (same-data descriptive)")
    fig.tight_layout()
    for ext in ["png","pdf"]:fig.savefig(OUT/f"opportunity_by_n.{ext}",dpi=220)
    plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,3.8))
    sample=d[d.row_id.eq(target)].sort_values("c")
    for name,color in zip(["e_beta","e_eta","e_gamma"],colors):
        axes[0].plot(sample.c,sample[name],marker="o",ms=3,label=name,color=color)
    axes[0].axhline(0,color="gray",lw=.8)
    axes[0].set(xlabel="J3 multiplier c",ylabel="Signed normalized parameter error",title="Historical sample 47")
    axes[0].legend(frameon=False,fontsize=8)
    for color,(n,g) in zip(colors,oracle[oracle.cohort.eq("controlled_20260922") & oracle.valid].groupby("sample_size")):
        p=g.c.value_counts(normalize=True).sort_index()
        axes[1].plot(p.index,p.values,marker="o",ms=3,label=f"n={n}",color=color)
    axes[1].set(xlabel="Selected c",ylabel="Proportion among valid oracle choices",title="Per-sample oracle choices")
    axes[1].legend(frameon=False,fontsize=8)
    for ax in axes:ax.grid(alpha=.18)
    fig.tight_layout()
    for ext in ["png","pdf"]:fig.savefig(OUT/f"sample_and_oracle_choices.{ext}",dpi=220)
    plt.close(fig)
    lines=["# J3 改善空间：完整统计", "",
           "口径：E为最大归一化分量误差；bad_rate为失败或E≥0.5的全样本比例。",
           "同数据最佳固定、真参数格固定、逐样本事后最优均属描述性机会参照，不能当作独立预测性能。", ""]
    cols=["policy","total","valid","failure_rate","bad_rate","extreme50_rate_valid","mean_E_valid","p95_E_valid"]
    for cohort,g in overall.groupby("cohort"):
        lines += [f"## {cohort}","",table(g,cols),""]
        n=by_n[by_n.cohort.eq(cohort)]
        lines += [table(n,["sample_size"]+cols),""]
    lines += ["## 同一真参数格内的比较","",table(cells,KEYS+["policy","bad_rate","failure_rate","mean_E_valid"]),""]
    (OUT/"完整统计.md").write_text("\n".join(lines),encoding="utf-8")
    (OUT/"analysis_status.json").write_text(json.dumps(dict(status="complete",rows=len(d),
        baseline_matches=4500,selected_rows=len(selected),policies=list(LABELS),
        no_oracle_harm_verified=True)),encoding="utf-8")
    print(overall.to_string(index=False))
    print("CHOICES",chosen[chosen.scope.eq("global")].to_dict("records"))
    print("BOUNDARIES",edge.to_dict("records"))
    print("CASE47",oracle[oracle.row_id.eq(target)][["c","beta_hat","eta_hat","gamma_hat","E"]].to_dict("records"))


if __name__=="__main__":main()
