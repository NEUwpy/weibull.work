"""Fresh-seed paired evaluation after frozen model selection."""
from pathlib import Path
import json
import joblib
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import run_j3_learning as exp
from sklearn.tree import export_text

OUT=exp.OUT


def metrics(g):
    v=g[g.valid]
    return dict(total=len(g),bad_count=int(g.bad.sum()),bad_rate=g.bad.mean(),
                failure_rate=(~g.valid).mean(),mean_E_valid=v.E.mean(),
                p95_E_valid=v.E.quantile(.95),cap_loss=g.cap.mean(),
                fallback_count=int(g.fallback.sum()),mean_solver_calls=g.solver_calls.mean(),
                beta_rmse=np.sqrt(np.mean(v.e_beta**2)),
                eta_rmse=np.sqrt(np.mean(v.e_eta**2)),
                gamma_rmse=np.sqrt(np.mean(v.e_gamma**2)))


def groups(d,keys):
    return pd.DataFrame([{**dict(zip(keys,k if isinstance(k,tuple) else (k,))),**metrics(g)}
                         for k,g in d.groupby(keys)])


def main():
    manifest=json.loads((OUT/"test_manifest.json").read_text(encoding="utf-8"))
    frozen=json.loads((OUT/"frozen_model.json").read_text(encoding="utf-8"))
    assert manifest["freeze_hash"]==exp.sha(OUT/"frozen_model.json")
    assert manifest["predictions_sha256"]==exp.sha(OUT/"test_choices_before_labels.csv")
    assert frozen["models_sha256"]==exp.sha(OUT/"models.joblib")
    names=["log_n","log1p_min_over_range"]+[f"normalized_q{q:02d}" for q in range(5,100,5)]+[
        "normalized_mean","normalized_sd","normalized_skew","gap1_over_range",
        "gap2_over_range","max_gap_over_range","top2_gaps_over_range"]
    assert len(names)==28
    exp.write_json(OUT/"feature_schema.json",names)
    saved_models=joblib.load(OUT/"models.joblib")
    tree=saved_models["tree4"][0]
    (OUT/"tree_rules.txt").write_text(export_text(tree,feature_names=names),encoding="utf-8")
    pd.DataFrame({"feature":names,"training_impurity_importance":tree.feature_importances_}).sort_values(
        "training_impurity_importance",ascending=False).to_csv(OUT/"tree_feature_importance.csv",index=False)
    exp.write_json(OUT/"network_fit_diagnostics.json",[
        dict(seed=p.steps[-1][1].random_state,iterations=int(p.steps[-1][1].n_iter_),
             best_internal_validation_score=float(p.steps[-1][1].best_validation_score_),
             final_loss=float(p.steps[-1][1].loss_)) for p in saved_models["mlp32_ensemble"]])
    idx=pd.read_csv(OUT/"test_index.csv")
    rows=pd.concat([pd.read_csv(OUT/r["path"]) for r in manifest["files"]],ignore_index=True)
    idx,d,v,e,ev,ee,bad,cap=exp.matrix(idx,rows)
    choices=pd.read_csv(OUT/"test_choices_before_labels.csv").sort_values("row_id")
    assert np.array_equal(choices.row_id,idx.row_id)
    policies={"original":np.full(len(idx),exp.BASE),
              "fixed_fallback":np.full(len(idx),frozen["fixed_index"]),
              "n_fixed_fallback":np.array([frozen["by_n_indices"][str(int(n))] for n in idx.sample_size])}
    for name in exp.NAMES:policies[name]=choices[name].to_numpy(int)
    # Raw counterparts are attribution diagnostics, not new model selection.
    policies["primary_no_fallback"]=choices[frozen["primary"]["model"]].to_numpy(int)
    policies["fixed_no_fallback"]=np.full(len(idx),frozen["fixed_index"])
    order=np.argsort(abs(exp.GRID-1),kind="stable")
    oracle=order[np.argmin(np.nan_to_num(e[:,order],nan=np.inf),axis=1)]
    policies["oracle"]=oracle
    # Historical direct fixed-c baseline preserved for comparison with scan protocol.
    policies["legacy_c1.02_no_fallback"]=np.full(len(idx),int(np.where(exp.GRID==1.02)[0][0]))
    rawkeys=["row_id","c","beta_hat","eta_hat","gamma_hat","valid","status"]
    selected=[]
    for name,j in policies.items():
        ii=np.arange(len(j))
        use_fallback=name not in ["primary_no_fallback","fixed_no_fallback","legacy_c1.02_no_fallback","oracle","original"]
        fallback=use_fallback & (~v[ii,j]) & (j!=exp.BASE)
        effective=np.where(fallback,exp.BASE,j)
        info=idx.copy()
        info["policy"]=name
        info["requested_c"]=exp.GRID[j]
        info["c"]=exp.GRID[effective]
        info["fallback"]=fallback
        info["solver_calls"]=18 if name=="oracle" else 1+fallback.astype(int)
        info=info.merge(d[rawkeys],on=["row_id","c"],validate="one_to_one")
        for param,scale in [("beta","beta"),("eta","eta"),("gamma","eta")]:
            info["e_"+param]=((info[param+"_hat"]-info[param])/info[scale]).where(info.valid)
        info["E"]=info[["e_beta","e_eta","e_gamma"]].abs().max(axis=1,skipna=False)
        info["bad"]=~info.valid | info.E.ge(.5)
        info["cap"]=info.E.clip(upper=2).fillna(2)
        selected.append(info)
    selected=pd.concat(selected,ignore_index=True)
    selected.to_csv(OUT/"test_selected_rows.csv.gz",index=False,compression="gzip")
    summary=groups(selected,["policy"])
    by_n=groups(selected,["sample_size","policy"])
    cells=groups(selected,["beta","eta","gamma","sample_size","policy"])
    summary.to_csv(OUT/"test_summary.csv",index=False,encoding="utf-8-sig")
    by_n.to_csv(OUT/"test_by_n.csv",index=False,encoding="utf-8-sig")
    cells.to_csv(OUT/"test_by_cell.csv",index=False,encoding="utf-8-sig")
    base=selected[selected.policy.eq("original")].set_index("row_id").sort_index()
    transitions=[]
    for name,g in selected.groupby("policy"):
        g=g.set_index("row_id").sort_index()
        transitions.append(dict(policy=name,
            rescued_bad=int((base.bad & ~g.bad).sum()),harmed_good=int((~base.bad & g.bad).sum()),
            new_failures=int((base.valid & ~g.valid).sum()),
            rescued_failures=int((~base.valid & g.valid).sum()),
            good_E_worsened=int((~base.bad & g.valid & g.E.gt(base.E+1e-10)).sum())))
    pd.DataFrame(transitions).to_csv(OUT/"test_paired_transitions.csv",index=False,encoding="utf-8-sig")
    primary=frozen["primary"]["model"]
    primary_rows=selected[selected.policy.eq(primary)].sort_values("row_id")
    sensitivity=[]
    for (name,n),g in selected.groupby(["policy","sample_size"]):
        for threshold in [.25,.5,1.,2.]:
            sensitivity.append(dict(policy=name,sample_size=n,threshold=threshold,
                total=len(g),failure_or_above_rate=(~g.valid|g.E.ge(threshold)).mean(),
                above_rate_valid=g.loc[g.valid,"E"].ge(threshold).mean()))
    pd.DataFrame(sensitivity).to_csv(OUT/"threshold_sensitivity.csv",index=False,encoding="utf-8-sig")
    matched=primary_rows.merge(base.reset_index()[["row_id","valid","E"]],on="row_id",
                              suffixes=("_nn","_base"))
    matched=matched[matched.valid_nn & matched.valid_base]
    paired_tails=[]
    for n,g in matched.groupby("sample_size"):
        paired_tails.append(dict(sample_size=n,total=len(g),
             original_p95=g.E_base.quantile(.95),primary_p95=g.E_nn.quantile(.95),
             original_mean=g.E_base.mean(),primary_mean=g.E_nn.mean(),
             original_ge1=int(g.E_base.ge(1).sum()),primary_ge1=int(g.E_nn.ge(1).sum())))
    pd.DataFrame(paired_tails).to_csv(OUT/"matched_valid_tails.csv",index=False,encoding="utf-8-sig")
    # Paired, stratified within true-parameter/n cell; uncertainty over test draws,
    # conditional on this fitted model and finite design. No training reruns.
    rng=np.random.default_rng(2026092304)
    row_blocks=[g.index.to_numpy() for _,g in idx.groupby("cell_id")]
    bootstrap_indices=np.concatenate([rng.choice(block,size=(1000,len(block)),replace=True)
                                      for block in row_blocks],axis=1)
    primary_bad=primary_rows.bad.to_numpy(float)
    comparisons=[]
    for ref in ["original","fixed_fallback","n_fixed_fallback","tree4","ridge"]:
        r=selected[selected.policy.eq(ref)].sort_values("row_id")
        delta=r.bad.to_numpy(float)-primary_bad
        draws=delta[bootstrap_indices].mean(axis=1)
        comparisons.append(dict(primary=primary,reference=ref,
             risk_reduction=float(delta.mean()),ci_low=float(np.quantile(draws,.025)),
             ci_high=float(np.quantile(draws,.975)),resamples=1000))
    pd.DataFrame(comparisons).to_csv(OUT/"paired_bootstrap.csv",index=False,encoding="utf-8-sig")
    lookup=summary.set_index("policy")
    recovery=(lookup.loc["original","bad_rate"]-lookup.loc[primary,"bad_rate"])/(
        lookup.loc["original","bad_rate"]-lookup.loc["oracle","bad_rate"])
    selected.groupby(["policy","requested_c"]).size().rename("count").reset_index().to_csv(
        OUT/"test_choice_distribution.csv",index=False,encoding="utf-8-sig")
    # Freeze-selected primary is marked without selecting by test ranking.
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False})
    display=["original","fixed_fallback","n_fixed_fallback","ridge","tree4","mlp32_ensemble","oracle"]
    labels=["Original","Fixed + fallback","n-fixed + fallback","Ridge","Tree depth 4","MLP ensemble","Oracle"]
    fig,axes=plt.subplots(1,2,figsize=(11,4.8))
    vals=lookup.loc[display]
    axes[0].barh(labels,vals.bad_rate,color=["#777777","#999999","#BBBBBB","#E69F00","#56B4E9","#0072B2","#009E73"])
    axes[0].invert_yaxis();axes[0].set(xlabel="Failure or E >= 0.5 / all test draws",xlim=(0,.65))
    for i,y in enumerate(vals.bad_rate):axes[0].text(y+.008,i,f"{y:.1%}",va="center",fontsize=9)
    for name,label,color in [("original","Original","#777777"),("fixed_fallback","Fixed + fallback","#D55E00"),
                             ("tree4","Tree depth 4","#56B4E9"),("mlp32_ensemble","MLP ensemble","#0072B2"),
                             ("oracle","Oracle","#009E73")]:
        part=by_n[by_n.policy.eq(name)].sort_values("sample_size")
        axes[1].plot(part.sample_size,part.bad_rate,marker="o",label=label,color=color)
    axes[1].set(xlabel="Sample size",ylabel="Failure or E >= 0.5",xticks=[7,15,30],ylim=(0,.7))
    axes[1].legend(frameon=False,fontsize=8);axes[1].grid(alpha=.18)
    fig.suptitle("Fresh-seed test: 1,650 draws; MLP selected before test")
    fig.tight_layout()
    for ext in ["png","pdf"]:fig.savefig(OUT/f"fresh_test_comparison.{ext}",dpi=220)
    plt.close(fig)
    output=dict(status="complete",primary=primary,gate=frozen["primary"]["gate"],
       test_samples=len(idx),test_candidates=len(rows),policies=len(policies),
       oracle_risk_recovery=float(recovery),comparisons=comparisons)
    exp.write_json(OUT/"analysis.json",output)
    print(summary.to_string(index=False))
    print("RECOVERY",recovery)
    print("PAIRED",comparisons)
    print("TRANSITIONS",transitions)


if __name__=="__main__":main()
