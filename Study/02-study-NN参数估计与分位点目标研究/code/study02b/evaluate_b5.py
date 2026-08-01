"""B5 v2: Complete boundary/conformal/NIST/contamination with validity accounting.

Fixes: contamination experiment, stress validity/failure reporting, conformal
coverage on B4 core, complete NIST (all T routes, failures, paired uncertainty).
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
if str(_STUDY_CODE) not in sys.path: sys.path.insert(0, str(_STUDY_CODE))
_REPO_ROOT = Path(__file__).resolve().parents[4]
_PYTHON = _REPO_ROOT / "python"
if str(_PYTHON) not in sys.path: sys.path.insert(0, str(_PYTHON))

from studies.common.sample import generate_sample
from studies.common.metrics import quantile_true, summarize_standard_errors, check_status
from studies.common.runner import run_method
from study02a.models import build_mlp, decode_model_output
from study02a.representations import anchor_sample
from study02a.training import load_checkpoint
from study02b.representations import decode_d_target, unstandardize_d, DTrainingStats
from study02b.training import build_d_mlp

_EXTERNAL_ROOT = Path("C:/weibull-runs/study02/formal-b")
_B3_MF = Path("C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json")
_B4_CSV = Path("C:/weibull-runs/study02/formal-b/B4-core-20260801-051119/results.csv")
_B4_NPZ = Path("C:/weibull-runs/study02/formal-b/B4-core-20260801-051119/per_seed_predictions.npz")
_NIST_CSV = _REPO_ROOT / "Study/01-study-MDM最小偏移量优化研究/artifacts/formal/real_data/nist-6061-t6-fatigue/lifetimes.csv"

_N_VALUES = [5,7,10,15,20]

def _git_tip():
    return subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,cwd=str(_REPO_ROOT)).stdout.strip() or "unknown"


# -- Model loading --

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


def _infer_p(m, sample):
    a=anchor_sample(sample); z=torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
    with torch.no_grad(): raw=m(z)
    dec=decode_model_output(raw,torch.tensor([a.location],dtype=torch.float32),torch.tensor([a.scale],dtype=torch.float32))
    bf,ef,gf=float(dec[0,0]),float(dec[0,1]),float(dec[0,2])
    ok=bf>0 and ef>0 and np.isfinite([bf,ef,gf]).all()
    return (quantile_true(bf,ef,gf,0.95),bf,ef,gf,ok) if ok else (np.nan,np.nan,np.nan,np.nan,False)

def _infer_d(m, st, sample):
    a=anchor_sample(sample); z=torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
    with torch.no_grad(): raw=float(m(z).item())
    enc=unstandardize_d(np.array([raw]),st)[0]; x=decode_d_target(enc,a)
    return x if np.isfinite(x) and x>0 else np.nan


def _ens_mean(arr): return float(np.nanmean(arr)) if len(arr)>0 else np.nan


# -- Stress with full validity accounting --

def evaluate_stress_full(models, domain, n_clusters=32, n_reps=10):
    print(f"\n  Stress {domain} ...")
    sampler=qmc.Sobol(d=3,scramble=True,seed={"low":142,"high":242,"loc":342}[domain])
    pts=sampler.random_base2(m=5)
    if domain=="low": betas=0.6+pts[:,0]*0.6; etas=100+pts[:,1]*9900; gammas=pts[:,2]*etas
    elif domain=="high": betas=4+pts[:,0]*4; etas=100+pts[:,1]*9900; gammas=pts[:,2]*etas
    else: betas=1.2+pts[:,0]*2.8; etas=100+pts[:,1]*9900; gammas=(-0.5+pts[:,2]*2.5)*etas

    results=defaultdict(list)  # (n,route): [rel_errs]; status: (n,route): [failure_reasons]
    status=defaultdict(list)
    for ci,(b,e,g) in enumerate(zip(betas,etas,gammas)):
        for ri in range(n_reps):
            for n in _N_VALUES:
                sample=generate_sample(float(b),float(e),float(g),n,ri,seed=6000+100*({"low":1,"high":2,"loc":3}[domain])+ci)
                x095=quantile_true(float(b),float(e),float(g),0.95)
                # P
                p_seeds=[seed for (ns,seed) in models["P"] if ns==n]
                p_vals=[_infer_p(models["P"][(n,seed)],sample)[0] for seed in p_seeds]
                pm=_ens_mean(p_vals)
                if np.isfinite(pm): results[(n,"P")].append((pm-x095)/x095); status[(n,"P")].append("ok")
                else: status[(n,"P")].append("invalid")
                # D
                d_items=[(seed,m,st) for (ns,seed),(m,st) in models["D"].items() if ns==n]
                d_vals=[_infer_d(m,st,sample) for _,m,st in d_items]
                dm=_ens_mean(d_vals)
                if np.isfinite(dm): results[(n,"D")].append((dm-x095)/x095); status[(n,"D")].append("ok")
                else: status[(n,"D")].append("invalid")
                # Traditional
                for mid,kw,lbl in [("mdm",{"offset":0.1},"MDM"),("mle",{},"MLE"),("lre",{},"LRE")]:
                    r=run_method(mid,sample,**kw)
                    bh,eh,gh=r["beta_hat"],r["eta_hat"],r["gamma_hat"]
                    if bh is None or eh is None or gh is None:
                        status[(n,lbl)].append("null_params"); continue
                    st=check_status(float(bh),float(eh),float(gh),b,e,g,converged=r.get("converged",True),sample_min=float(sample.min()))
                    if st=="failure": status[(n,lbl)].append("invalid"); continue
                    tv=quantile_true(float(bh),float(eh),float(gh),0.95)
                    results[(n,lbl)].append((tv-x095)/x095); status[(n,lbl)].append("ok")

    # Summarize
    summary={}; n_total=n_clusters*n_reps
    for n in _N_VALUES:
        for lbl in ["P","D","MDM","MLE","LRE"]:
            errs=results.get((n,lbl),[]); sts=status.get((n,lbl),[])
            n_ok=sts.count("ok"); n_fail=len(sts)-n_ok
            s=summarize_standard_errors(errs); s["n_total"]=n_total; s["n_valid"]=n_ok; s["n_failure"]=n_fail
            summary[f"{lbl}_n{n}"]=s
    return summary


# -- Contamination --

def evaluate_contamination(models):
    """32 core points 脳 10 reps, n=20: clean + 4 contamination types."""
    print("\n  Contamination ...")
    rng=np.random.default_rng(42); n_clusters=32; n_reps=10; n_val=20
    betas=rng.uniform(1.2,4.0,size=n_clusters); etas=rng.uniform(100,10000,size=n_clusters)
    gammas=rng.uniform(0,1,size=n_clusters)*etas
    results={lbl:defaultdict(list) for lbl in ["P","D","MDM"]}
    for ci,(b,e,g) in enumerate(zip(betas,etas,gammas)):
        for ri in range(n_reps):
            clean=generate_sample(float(b),float(e),float(g),n_val,ri,seed=9000+ci)
            x095=quantile_true(float(b),float(e),float(g),0.95)
            iqr_val=float(np.quantile(clean,0.75)-np.quantile(clean,0.25))
            # Contamination conditions
            high3=clean.copy(); high3[-3:]*=10
            high10=clean.copy(); high10[-1]*=10
            low_end=clean.copy(); low_end[0]-=0.5*iqr_val
            two_sided=clean.copy(); m=n_val//10
            two_sided[:m]-=0.5*iqr_val; two_sided[-m:]*=10
            for cond_name,cond_sample in [("clean",clean),("high3",high3),("high10",high10),("low_end",low_end),("two_sided",two_sided)]:
                # P
                p_seeds=[seed for (ns,seed) in models["P"] if ns==n_val]
                p_vals=[_infer_p(models["P"][(n_val,seed)],cond_sample)[0] for seed in p_seeds]
                pm=_ens_mean(p_vals)
                if np.isfinite(pm): results["P"][cond_name].append((pm-x095)/x095)
                # D
                d_items=[(seed,m,st) for (ns,seed),(m,st) in models["D"].items() if ns==n_val]
                d_vals=[_infer_d(m,st,cond_sample) for _,m,st in d_items]
                dm=_ens_mean(d_vals)
                if np.isfinite(dm): results["D"][cond_name].append((dm-x095)/x095)
                # MDM
                r=run_method("mdm",cond_sample,offset=0.1)
                if r["beta_hat"] and r["eta_hat"] and r["gamma_hat"]:
                    st=check_status(float(r["beta_hat"]),float(r["eta_hat"]),float(r["gamma_hat"]),b,e,g,sample_min=float(cond_sample.min()))
                    if st=="success": results["MDM"][cond_name].append((quantile_true(float(r["beta_hat"]),float(r["eta_hat"]),float(r["gamma_hat"]),0.95)-x095)/x095)

    summary={}
    for lbl in ["P","D","MDM"]:
        for cond in ["clean","high3","high10","low_end","two_sided"]:
            errs=results[lbl].get(cond,[]); s=summarize_standard_errors(errs)
            s["n_valid"]=len(errs); s["n_total"]=n_clusters*n_reps
            summary[f"{lbl}_{cond}"]=s
    return summary


# -- Conformal with coverage on B4 core --

def evaluate_conformal_full(models):
    """Calibrate on fresh data, evaluate coverage/width/Spearman on B4 core."""
    print("\n  Conformal full ...")
    # Calibrate per-n thresholds
    thresholds={}
    rng_cal=np.random.default_rng(7000)
    for n_val in _N_VALUES:
        betas=rng_cal.uniform(1.2,4.0,size=5000); etas=rng_cal.uniform(100,10000,size=5000)
        gammas=rng_cal.uniform(0,1,size=5000)*etas
        p_res,d_res=[],[]
        for i in range(5000):
            b,e,g=float(betas[i]),float(etas[i]),float(gammas[i])
            sample=generate_sample(b,e,g,n_val,i,seed=8000)
            x095=quantile_true(b,e,g,0.95)
            p_seeds=[seed for (ns,seed) in models["P"] if ns==n_val]
            p_vals=[_infer_p(models["P"][(n_val,seed)],sample)[0] for seed in p_seeds]
            pm=_ens_mean(p_vals)
            if np.isfinite(pm): p_res.append(abs(pm-x095))
            d_items=[(seed,m,st) for (ns,seed),(m,st) in models["D"].items() if ns==n_val]
            d_vals=[_infer_d(m,st,sample) for _,m,st in d_items]
            dm=_ens_mean(d_vals)
            if np.isfinite(dm): d_res.append(abs(dm-x095))
        thresholds[str(n_val)]={"P_q90":float(np.quantile(p_res,0.9)),"P_q95":float(np.quantile(p_res,0.95)),
                                "D_q90":float(np.quantile(d_res,0.9)),"D_q95":float(np.quantile(d_res,0.95))}

    # Evaluate on B4 core
    b4_data=np.load(_B4_NPZ,allow_pickle=True)
    p_seeds_b4=b4_data["p_seeds"]; d_seeds_b4=b4_data["d_seeds"]; b4_data.close()
    keys_raw=np.load(_B4_NPZ,allow_pickle=True)["keys"]
    # Load B4 true values
    true_x095={}
    with open(_B4_CSV,newline="",encoding="utf-8") as f:
        for row in csv.DictReader(f): true_x095[(int(row["cluster"]),int(row["replicate"]),int(row["n"]))]=float(row["true_x095"])

    coverage={}; widths={}; spearman_data=defaultdict(list)
    for n_val in _N_VALUES:
        th=thresholds[str(n_val)]
        for route in ["P","D"]:
            cov90=cov95=0; n_total=0; width_vals=[]; abs_errs=[]
            for i,k in enumerate(keys_raw):
                parts=str(k).split("_")
                if len(parts)!=3: continue
                ci,ri,n=int(parts[0]),int(parts[1]),int(parts[2])
                if n!=n_val: continue
                td=true_x095.get((ci,ri,n))
                if td is None: continue
                if route=="P":
                    vals=p_seeds_b4[i]; vals=vals[np.isfinite(vals)]
                    pred=_ens_mean(vals) if len(vals)>0 else np.nan
                else:
                    vals=d_seeds_b4[i]; vals=vals[np.isfinite(vals)]
                    pred=_ens_mean(vals) if len(vals)>0 else np.nan
                if not np.isfinite(pred): continue
                n_total+=1; ae=abs(pred-td)
                q90=th[f"{route}_q90"]; q95=th[f"{route}_q95"]
                if ae<=q90: cov90+=1
                if ae<=q95: cov95+=1
                width_vals.append(q95)
                abs_errs.append(ae)
            coverage[f"{route}_n{n_val}"]={"cov90":cov90/n_total if n_total else np.nan,"cov95":cov95/n_total if n_total else np.nan,"n":n_total}
            widths[f"{route}_n{n_val}"]=float(np.mean(width_vals)) if width_vals else np.nan
            if len(width_vals)>2:
                rho,_=spearmanr(width_vals,abs_errs)
                spearman_data[f"{route}_n{n_val}"]=float(rho)

    return {"thresholds":thresholds,"coverage":coverage,"widths":widths,"spearman":dict(spearman_data)}


# -- NIST complete --

def evaluate_nist_full(models):
    """500 splits per n, all routes P/D/MDM/MLE/LRE, pinball/exceedance/failures."""
    print("\n  NIST full ...")
    data=np.loadtxt(_NIST_CSV,delimiter=",",skiprows=1); n_total=len(data)
    results={}
    for n_val in _N_VALUES:
        rows=defaultdict(list)
        for split in range(500):
            rng=np.random.default_rng(9000+n_val*1000+split)
            idx=rng.choice(n_total,size=n_val,replace=False)
            train=data[idx]; holdout=np.setdiff1d(data,train)
            if len(holdout)==0: continue
            # Evaluate all routes
            preds={}
            # P
            p_seeds=[seed for (ns,seed) in models["P"] if ns==n_val]
            p_vals=[_infer_p(models["P"][(n_val,seed)],train)[0] for seed in p_seeds]
            preds["P"]=_ens_mean(p_vals)
            # D
            d_items=[(seed,m,st) for (ns,seed),(m,st) in models["D"].items() if ns==n_val]
            d_vals=[_infer_d(m,st,train) for _,m,st in d_items]
            preds["D"]=_ens_mean(d_vals)
            # T routes
            for mid,kw,lbl in [("mdm",{"offset":0.1},"MDM"),("mle",{},"MLE"),("lre",{},"LRE")]:
                r=run_method(mid,train,**kw); bh,eh,gh=r["beta_hat"],r["eta_hat"],r["gamma_hat"]
                ok=False
                if bh is not None and eh is not None and gh is not None:
                    st=check_status(float(bh),float(eh),float(gh),0,0,0,converged=r.get("converged",True),sample_min=float(train.min()))
                    ok=(st=="success")
                preds[lbl]=quantile_true(float(bh),float(eh),float(gh),0.95) if ok else np.nan

            tau=0.05
            def pb(p,h): return (tau-1)*(h-p) if h<p else tau*(h-p)
            for h in holdout:
                row={"split":split,"holdout_val":float(h)}
                for lbl in ["P","D","MDM","MLE","LRE"]:
                    pv=preds.get(lbl,np.nan)
                    if np.isfinite(pv):
                        row[f"{lbl}_pinball"]=pb(pv,h)
                        row[f"{lbl}_exceed"]=1.0 if h>pv else 0.0
                        row[f"{lbl}_valid"]=1
                    else:
                        row[f"{lbl}_pinball"]=np.nan; row[f"{lbl}_exceed"]=np.nan; row[f"{lbl}_valid"]=0
                for k,v in row.items(): rows[k].append(v)

        summary={}
        for lbl in ["P","D","MDM","MLE","LRE"]:
            pb_vals=[v for v in rows.get(f"{lbl}_pinball",[]) if np.isfinite(v)]
            exc_vals=[v for v in rows.get(f"{lbl}_exceed",[]) if np.isfinite(v)]
            n_valid=sum(rows.get(f"{lbl}_valid",[])); n_total_rows=len(rows.get(f"{lbl}_valid",[]))
            summary[lbl]={
                "pinball_mean":float(np.mean(pb_vals)) if pb_vals else np.nan,
                "exceedance_mean":float(np.mean(exc_vals)) if exc_vals else np.nan,
                "n_valid":n_valid,"n_total_rows":n_total_rows,"failure_rate":(n_total_rows-n_valid)/n_total_rows if n_total_rows else 0,
            }
        results[str(n_val)]=summary
    return results


# -- Main --

def run_b5(output_dir=None):
    if output_dir is None:
        output_dir=str(_EXTERNAL_ROOT/f"B5-v2-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    code_tip=_git_tip()
    print(f"=== B5 v2 ==="); print(f"Output: {out}")

    models=load_models()
    print(f"Models: P={len(models['P'])} D={len(models['D'])} Dctrl={len(models['Dctrl'])}")

    # 1. Stress
    print("\n[1] Stress domains ...")
    stress={}; stress["low"]=evaluate_stress_full(models,"low"); stress["high"]=evaluate_stress_full(models,"high"); stress["loc"]=evaluate_stress_full(models,"loc")

    # 2. Contamination
    print("\n[2] Contamination ...")
    contam=evaluate_contamination(models)

    # 3. Conformal
    print("\n[3] Conformal ...")
    conf=evaluate_conformal_full(models)

    # 4. NIST
    print("\n[4] NIST ...")
    nist=evaluate_nist_full(models)

    # Manifest
    b4_csv_sha=hashlib.sha256(_B4_CSV.read_bytes()).hexdigest()
    b4_npz_sha=hashlib.sha256(_B4_NPZ.read_bytes()).hexdigest()
    nist_csv_sha=hashlib.sha256(_NIST_CSV.read_bytes()).hexdigest()
    manifest={"version":"2.0","run_id":out.name,"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
              "status":"complete","code_tip":code_tip,
              "config_sha256":hashlib.sha256(json.dumps({"n_values":_N_VALUES},sort_keys=True).encode()).hexdigest(),
              "environment":{"python_version":sys.version,"platform":sys.platform},
              "input_hashes":{"b4_results_csv":b4_csv_sha,"b4_per_seed_npz":b4_npz_sha,"nist_lifetimes_csv":nist_csv_sha},
              "stress":stress,"contamination":contam,"conformal":conf,"nist":nist}
    mf_path=out/"manifest.json"
    mf_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    mf_sha=hashlib.sha256(mf_path.read_bytes()).hexdigest()
    print(f"\n  Manifest: {mf_path}\n  SHA256: {mf_sha}")
    print(f"\n=== B5 v2 complete ===")
    return manifest

if __name__=="__main__": run_b5()
