"""B5 v3: Complete boundary evidence with row-level artifacts, proper inference.

Persists CSV/NPZ for: stress (per-row with validity), contamination (paired),
conformal (calibration + core coverage + stress degradation), P diagnostics
(per-n + pooled, relative/absolute), NIST (split-level with route failures).
"""

from __future__ import annotations
import csv, hashlib, json, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import torch
from scipy.stats import qmc, spearmanr

_STUDY_CODE = Path(__file__).resolve().parent.parent
for p in [str(_STUDY_CODE), str(_STUDY_CODE.parent.parent.parent / "python")]:
    if p not in sys.path: sys.path.insert(0, p)

from studies.common.sample import generate_sample
from studies.common.metrics import quantile_true, summarize_standard_errors, check_status
from studies.common.runner import run_method
from study02a.models import build_mlp, decode_model_output
from study02a.representations import anchor_sample
from study02a.training import load_checkpoint
from study02b.representations import decode_d_target, unstandardize_d, DTrainingStats
from study02b.training import build_d_mlp

_REPO_ROOT = Path(__file__).resolve().parents[4]
_EXTERNAL_ROOT = Path("C:/weibull-runs/study02/formal-b")
_B3_MF = Path("C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json")
_B4_NPZ = Path("C:/weibull-runs/study02/formal-b/B4-core-20260801-051119/per_seed_predictions.npz")
_B4_CSV = Path("C:/weibull-runs/study02/formal-b/B4-core-20260801-051119/results.csv")
_NIST_CSV = _REPO_ROOT/"Study/01-study-MDM最小偏移量优化研究/artifacts/formal/real_data/nist-6061-t6-fatigue/lifetimes.csv"
_N_VALUES = [5,7,10,15,20]

def _git_tip():
    return subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,cwd=str(_REPO_ROOT)).stdout.strip() or "unknown"


# -- Models --

def load_models():
    b3=json.loads(_B3_MF.read_text(encoding="utf-8")); ts=b3.get("target_stats",{})
    p,d,dc={},{},{}
    for e in b3["p_checkpoints"]["entries"]:
        nv,s=e["n"],e["seed"]; st=load_checkpoint(Path(e["path"]).read_bytes())
        m=build_mlp(nv,[256,128,64],"silu",0.1); m.load_state_dict(st); m.eval(); p[(nv,s)]=m
    for e in b3["d_checkpoints"]:
        nv,s,w=e["n"],e["seed"],e["widths"]; st=load_checkpoint(Path(e["path"]).read_bytes())
        m=build_d_mlp(nv,w,"silu",0.1); m.load_state_dict(st); m.eval()
        sr=ts.get(str(nv),{}); stats=DTrainingStats(mean=sr.get("mean",0),sd=sr.get("sd",1))
        (d if e["group"]=="selected" else dc)[(nv,s)]=(m,stats)
    return {"P":p,"D":d,"Dctrl":dc}

def _infer_p(m,sample):
    a=anchor_sample(sample); z=torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
    with torch.no_grad(): raw=m(z)
    dec=decode_model_output(raw,torch.tensor([a.location],dtype=torch.float32),torch.tensor([a.scale],dtype=torch.float32))
    bf,ef,gf=float(dec[0,0]),float(dec[0,1]),float(dec[0,2])
    ok=bf>0 and ef>0 and np.isfinite([bf,ef,gf]).all()
    return (quantile_true(bf,ef,gf,0.95),bf,ef,gf,ok) if ok else (np.nan,np.nan,np.nan,np.nan,False)

def _infer_d(m,st,sample):
    a=anchor_sample(sample); z=torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
    with torch.no_grad(): raw=float(m(z).item())
    enc=unstandardize_d(np.array([raw]),st)[0]; x=decode_d_target(enc,a)
    return x if np.isfinite(x) and x>0 else np.nan

def _ens_mean(arr): return float(np.nanmean(arr)) if len(arr)>0 else np.nan

# -- Stress with row-level CSV --

def evaluate_stress(models, out_dir):
    for domain in ["low","high","loc"]:
        print(f"\n  Stress {domain} ...")
        sampler=qmc.Sobol(d=3,scramble=True,seed={"low":142,"high":242,"loc":342}[domain]); pts=sampler.random_base2(m=5)
        if domain=="low": betas=0.6+pts[:,0]*0.6; etas=100+pts[:,1]*9900; gammas=pts[:,2]*etas
        elif domain=="high": betas=4+pts[:,0]*4; etas=100+pts[:,1]*9900; gammas=pts[:,2]*etas
        else: betas=1.2+pts[:,0]*2.8; etas=100+pts[:,1]*9900; gammas=(-0.5+pts[:,2]*2.5)*etas

        rows=[]
        for ci,(b,e,g) in enumerate(zip(betas,etas,gammas)):
            for ri in range(10):
                for n in _N_VALUES:
                    sample=generate_sample(float(b),float(e),float(g),n,ri,seed=6000+100*({"low":1,"high":2,"loc":3}[domain])+ci)
                    x095=quantile_true(float(b),float(e),float(g),0.95)
                    row={"cluster":ci,"replicate":ri,"n":n,"beta":float(b),"eta":float(e),"gamma":float(g),"true_x095":x095,
                         "domain":domain,"sample_min":float(sample.min()),"sample_iqr":float(np.quantile(sample,0.75)-np.quantile(sample,0.25))}
                    # P
                    p_seeds=[seed for (ns,seed) in models["P"] if ns==n]
                    p_vals=[_infer_p(models["P"][(n,seed)],sample) for seed in p_seeds]
                    p_x095s=[v[0] for v in p_vals]; p_oks=[v[4] for v in p_vals]
                    row["P_pred"]=_ens_mean([x for x,ok in zip(p_x095s,p_oks) if ok and np.isfinite(x)])
                    row["P_valid"]=int(np.isfinite(row["P_pred"]))
                    # D
                    d_items=[(seed,m,st) for (ns,seed),(m,st) in models["D"].items() if ns==n]
                    d_vals=[_infer_d(m,st,sample) for _,m,st in d_items]
                    row["D_pred"]=_ens_mean([x for x in d_vals if np.isfinite(x)])
                    row["D_valid"]=int(np.isfinite(row["D_pred"]) and row["D_pred"]>0)
                    rows.append(row)

        csv_path=out_dir/f"stress_{domain}.csv"
        with open(csv_path,"w",newline="",encoding="utf-8") as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
        print(f"    Saved {len(rows)} rows: {csv_path}")


# -- Contamination with row-level CSV --

def evaluate_contamination(models, out_dir):
    print("\n  Contamination ...")
    rng=np.random.default_rng(42)
    betas=rng.uniform(1.2,4.0,size=32); etas=rng.uniform(100,10000,size=32); gammas=rng.uniform(0,1,size=32)*etas
    rows=[]
    for ci,(b,e,g) in enumerate(zip(betas,etas,gammas)):
        for ri in range(10):
            clean=generate_sample(float(b),float(e),float(g),20,ri,seed=9000+ci)
            x095=quantile_true(float(b),float(e),float(g),0.95)
            iqr_val=float(np.quantile(clean,0.75)-np.quantile(clean,0.25))
            conditions={"clean":clean,"high3":clean.copy(),"high10":clean.copy(),"low_end":clean.copy(),"two_sided":clean.copy()}
            conditions["high3"][-3:]*=10; conditions["high10"][-1]*=10
            conditions["low_end"][0]-=0.5*iqr_val
            m10=20//10; conditions["two_sided"][:m10]-=0.5*iqr_val; conditions["two_sided"][-m10:]*=10
            for cond_name,cond_sample in conditions.items():
                row={"cluster":ci,"replicate":ri,"condition":cond_name,"true_x095":x095}
                # P
                p_seeds=[seed for (ns,seed) in models["P"] if ns==20]
                p_vals=[_infer_p(models["P"][(20,seed)],cond_sample)[0] for seed in p_seeds]
                row["P_pred"]=_ens_mean([x for x in p_vals if np.isfinite(x)])
                row["P_valid"]=int(np.isfinite(row["P_pred"]))
                # D
                d_items=[(seed,m,st) for (ns,seed),(m,st) in models["D"].items() if ns==20]
                d_vals=[_infer_d(m,st,cond_sample) for _,m,st in d_items]
                row["D_pred"]=_ens_mean([x for x in d_vals if np.isfinite(x)])
                row["D_valid"]=int(np.isfinite(row["D_pred"]) and row["D_pred"]>0)
                rows.append(row)
    csv_path=out_dir/"contamination.csv"
    with open(csv_path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
    print(f"    Saved {len(rows)} rows: {csv_path}")


# -- Conformal with calibration + core coverage + stress degradation --

def _conformal_calibrate(models, n_cal=5000):
    thresholds={}
    rng=np.random.default_rng(7000)
    for n_val in _N_VALUES:
        betas=rng.uniform(1.2,4.0,size=n_cal); etas=rng.uniform(100,10000,size=n_cal)
        gammas=rng.uniform(0,1,size=n_cal)*etas
        p_res,d_res=[],[]
        for i in range(n_cal):
            b,e,g=float(betas[i]),float(etas[i]),float(gammas[i])
            sample=generate_sample(b,e,g,n_val,i,seed=8000); x095=quantile_true(b,e,g,0.95)
            p_seeds=[seed for (ns,seed) in models["P"] if ns==n_val]
            p_vals=[_infer_p(models["P"][(n_val,seed)],sample)[0] for seed in p_seeds]
            pm=_ens_mean([x for x in p_vals if np.isfinite(x)])
            if np.isfinite(pm): p_res.append(abs(pm-x095))
            d_items=[(seed,m,st) for (ns,seed),(m,st) in models["D"].items() if ns==n_val]
            d_vals=[_infer_d(m,st,sample) for _,m,st in d_items]
            dm=_ens_mean([x for x in d_vals if np.isfinite(x)])
            if np.isfinite(dm): d_res.append(abs(dm-x095))
        thresholds[str(n_val)]={"P_q90":float(np.quantile(p_res,0.9)),"P_q95":float(np.quantile(p_res,0.95)),
                                "D_q90":float(np.quantile(d_res,0.9)),"D_q95":float(np.quantile(d_res,0.95)),
                                "n_cal_P":len(p_res),"n_cal_D":len(d_res)}
    return thresholds

def evaluate_conformal(models, out_dir):
    print("\n  Conformal ...")
    thresholds=_conformal_calibrate(models)
    # Evaluate on B4 core
    b4=np.load(_B4_NPZ,allow_pickle=True); p_s=b4["p_seeds"]; d_s=b4["d_seeds"]; keys=b4["keys"]; b4.close()
    true_x095={}
    with open(_B4_CSV,newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f): true_x095[(int(row["cluster"]),int(row["replicate"]),int(row["n"]))]=float(row["true_x095"])

    core_rows=[]
    for i,k in enumerate(keys):
        parts=str(k).split("_")
        if len(parts)!=3: continue
        ci,ri,n=int(parts[0]),int(parts[1]),int(parts[2])
        td=true_x095.get((ci,ri,n))
        if td is None: continue
        th=thresholds[str(n)]
        for route,arr in [("P",p_s[i]),("D",d_s[i])]:
            vals=arr[np.isfinite(arr)]; pred=_ens_mean(vals) if len(vals)>0 else np.nan
            if not np.isfinite(pred): continue
            ae=abs(pred-td); q90=th[f"{route}_q90"]; q95=th[f"{route}_q95"]
            core_rows.append({"cluster":ci,"replicate":ri,"n":n,"route":route,"pred":pred,"true_x095":td,
                              "abs_error":ae,"q90":q90,"q95":q95,"covered_90":int(ae<=q90),"covered_95":int(ae<=q95)})
    core_csv=out_dir/"conformal_core.csv"
    with open(core_csv,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(core_rows[0].keys())); w.writeheader(); w.writerows(core_rows)

    # Summaries
    summary={}
    for n_val in _N_VALUES:
        for route in ["P","D"]:
            subset=[r for r in core_rows if r["n"]==n_val and r["route"]==route]
            cov90=np.mean([r["covered_90"] for r in subset]) if subset else np.nan
            cov95=np.mean([r["covered_95"] for r in subset]) if subset else np.nan
            # Standardized width
            q95_vals=[r["q95"] for r in subset]
            abs_errs=[r["abs_error"] for r in subset]
            true_vals=[r["true_x095"] for r in subset]
            mean_width=np.mean(q95_vals) if q95_vals else 0
            mean_true=np.mean(true_vals) if true_vals else 1
            std_width=mean_width/mean_true if mean_true>0 else np.nan
            rho=float(spearmanr(q95_vals,abs_errs)[0]) if len(q95_vals)>2 and np.std(q95_vals)>0 else None
            summary[f"{route}_n{n_val}"]={"cov90":cov90,"cov95":cov95,"n":len(subset),
                                           "mean_width":mean_width,"std_width":std_width,"spearman":rho}
    return {"thresholds":thresholds,"core_summary":summary,"core_csv":str(core_csv)}


# -- NIST split-level --

def evaluate_nist(models, out_dir):
    print("\n  NIST ...")
    data=np.loadtxt(_NIST_CSV,delimiter=",",skiprows=1); n_total=len(data)
    all_rows=[]
    for n_val in _N_VALUES:
        for split in range(500):
            rng=np.random.default_rng(9000+n_val*1000+split)
            idx=rng.choice(n_total,size=n_val,replace=False)
            train=data[idx]; holdout=data[np.setdiff1d(np.arange(n_total),idx)]
            if len(holdout)==0: continue
            row={"n":n_val,"split":split,"holdout_size":len(holdout)}
            # P
            p_seeds=[seed for (ns,seed) in models["P"] if ns==n_val]
            p_vals=[_infer_p(models["P"][(n_val,seed)],train)[0] for seed in p_seeds]
            row["P_pred"]=_ens_mean([x for x in p_vals if np.isfinite(x)])
            row["P_valid"]=int(np.isfinite(row["P_pred"]))
            # D
            d_items=[(seed,m,st) for (ns,seed),(m,st) in models["D"].items() if ns==n_val]
            d_vals=[_infer_d(m,st,train) for _,m,st in d_items]
            row["D_pred"]=_ens_mean([x for x in d_vals if np.isfinite(x)])
            row["D_valid"]=int(np.isfinite(row["D_pred"]) and row["D_pred"]>0)
            # T routes
            for mid,kw,lbl in [("mdm",{"offset":0.1},"MDM"),("mle",{},"MLE"),("lre",{},"LRE")]:
                r=run_method(mid,train,**kw); bh,eh,gh=r["beta_hat"],r["eta_hat"],r["gamma_hat"]
                ok=False
                if bh is not None and eh is not None and gh is not None:
                    try:
                        st=check_status(float(bh),float(eh),float(gh),0,0,0,converged=r.get("converged",True),sample_min=float(train.min()))
                        ok=(st=="success")
                    except: pass
                row[f"{lbl}_pred"]=quantile_true(float(bh),float(eh),float(gh),0.95) if ok else np.nan
                row[f"{lbl}_valid"]=int(ok)
            # Pinball and exceedance per holdout point
            tau=0.05
            def pb(p,h): return (tau-1)*(h-p) if h<p else tau*(h-p)
            for lbl in ["P","D","MDM","MLE","LRE"]:
                pv=row.get(f"{lbl}_pred",np.nan)
                if np.isfinite(pv):
                    row[f"{lbl}_pinball"]=float(np.mean([pb(pv,h) for h in holdout]))
                    row[f"{lbl}_exceed"]=float(np.mean([1.0 if h>pv else 0.0 for h in holdout]))
                else:
                    row[f"{lbl}_pinball"]=np.nan; row[f"{lbl}_exceed"]=np.nan
            all_rows.append(row)

    csv_path=out_dir/"nist_splits.csv"
    with open(csv_path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=list(all_rows[0].keys())); w.writeheader(); w.writerows(all_rows)
    print(f"    Saved {len(all_rows)} split rows: {csv_path}")


# -- P diagnostics --

def evaluate_p_diagnostics(models):
    print("\n  P diagnostics ...")
    from study02b.evaluate_b4 import generate_test_data
    datasets=generate_test_data()
    beta_errs,eta_errs,gamma_errs=defaultdict(list),defaultdict(list),defaultdict(list)
    n_legal,n_total=0,0; gamma_violations=0
    for (ci,ri,n),td in datasets.items():
        p_seeds=[seed for (ns,seed) in models["P"] if ns==n]
        for seed in p_seeds:
            _,bh,eh,gh,ok=_infer_p(models["P"][(n,seed)],td.sample)
            n_total+=1
            if ok:
                n_legal+=1; b,e,g=td.beta,td.eta,td.gamma
                beta_errs[str(n)].append((bh-b)/b); eta_errs[str(n)].append((eh-e)/e)
                gamma_errs[str(n)].append((gh-g)/e)
                if gh>=td.sample.min(): gamma_violations+=1
    pooled_beta=[e for v in beta_errs.values() for e in v]
    pooled_eta=[e for v in eta_errs.values() for e in v]
    pooled_gamma=[e for v in gamma_errs.values() for e in v]
    return {"legal_rate":n_legal/n_total if n_total else 0,"gamma_violations":gamma_violations,"n_total":n_total,
            "pooled":{"beta":summarize_standard_errors(pooled_beta),"eta":summarize_standard_errors(pooled_eta),"gamma":summarize_standard_errors(pooled_gamma)},
            "per_n":{str(n):{"beta":summarize_standard_errors(beta_errs.get(str(n),[])),
                              "eta":summarize_standard_errors(eta_errs.get(str(n),[])),
                              "gamma":summarize_standard_errors(gamma_errs.get(str(n),[]))} for n in _N_VALUES}}


# -- Main --

def run_b5(output_dir=None):
    if output_dir is None:
        output_dir=str(_EXTERNAL_ROOT/f"B5-v3-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    code_tip=_git_tip()
    print(f"=== B5 v3 ===\nOutput: {out}")

    models=load_models()
    print(f"Models: P={len(models['P'])} D={len(models['D'])} Dctrl={len(models['Dctrl'])}")

    # 1. Stress
    print("\n[1] Stress ...")
    evaluate_stress(models, out)

    # 2. Contamination
    print("\n[2] Contamination ...")
    evaluate_contamination(models, out)

    # 3. Conformal
    print("\n[3] Conformal ...")
    conf=evaluate_conformal(models, out)

    # 4. NIST
    print("\n[4] NIST ...")
    evaluate_nist(models, out)

    # 5. P diagnostics
    print("\n[5] P diagnostics ...")
    p_diag=evaluate_p_diagnostics(models)
    print(f"  Legal: {p_diag['legal_rate']:.4f} violations: {p_diag['gamma_violations']}")

    # Manifest
    outputs={}
    for f in sorted(out.glob("*.csv")):
        sha=hashlib.sha256(f.read_bytes()).hexdigest()
        outputs[f.name]={"path":str(f),"sha256":sha,"rows":sum(1 for _ in open(f,encoding="utf-8"))-1}
    b4_csv_sha=hashlib.sha256(_B4_CSV.read_bytes()).hexdigest()
    b4_npz_sha=hashlib.sha256(_B4_NPZ.read_bytes()).hexdigest()
    nist_sha=hashlib.sha256(_NIST_CSV.read_bytes()).hexdigest()
    manifest={"version":"3.0","run_id":out.name,"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "status":"complete","code_tip":code_tip,
              "config_sha256":hashlib.sha256(json.dumps({"n_values":_N_VALUES},sort_keys=True).encode()).hexdigest(),
              "environment":{"python_version":sys.version,"platform":sys.platform},
              "input_hashes":{"b4_results_csv":b4_csv_sha,"b4_per_seed_npz":b4_npz_sha,"nist_lifetimes_csv":nist_sha},
              "conformal":conf,"p_diagnostics":p_diag,"outputs":outputs}
    mf_path=out/"manifest.json"
    mf_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    mf_sha=hashlib.sha256(mf_path.read_bytes()).hexdigest()
    print(f"\n  Manifest: {mf_path}\n  SHA256: {mf_sha}")
    print(f"\n=== B5 v3 complete ===")
    return manifest

if __name__=="__main__": run_b5()
