"""B5: Boundary stress, contamination, P diagnostics, conformal, NIST holdout.

Reuses frozen P/D checkpoints, B4 inference patterns. No new NN fits.
Outputs to C:\\weibull-runs\\study02\\formal-b\\<B5-run-id>.
"""

from __future__ import annotations

import csv, hashlib, json, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from scipy.stats import qmc

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

_N_VALUES = [5, 7, 10, 15, 20]

def _git_tip():
    return subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,cwd=str(_REPO_ROOT)).stdout.strip() or "unknown"


# -- Model loading (reuse B4 pattern) --

def load_models():
    b3 = json.loads(_B3_MF.read_text(encoding="utf-8"))
    ts = b3.get("target_stats",{})
    p, d, dc = {}, {}, {}
    for e in b3["p_checkpoints"]["entries"]:
        nv,s=e["n"],e["seed"]; state=load_checkpoint(Path(e["path"]).read_bytes())
        m=build_mlp(nv,[256,128,64],"silu",0.1); m.load_state_dict(state); m.eval(); p[(nv,s)]=m
    for e in b3["d_checkpoints"]:
        nv,s,w=e["n"],e["seed"],e["widths"]; state=load_checkpoint(Path(e["path"]).read_bytes())
        m=build_d_mlp(nv,w,"silu",0.1); m.load_state_dict(state); m.eval()
        st_raw=ts.get(str(nv),{}); st=DTrainingStats(mean=st_raw.get("mean",0),sd=st_raw.get("sd",1))
        (d if e["group"]=="selected" else dc)[(nv,s)]=(m,st)
    return {"P":p,"D":d,"Dctrl":dc}


# -- Inference helpers --

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
    enc=unstandardize_d(np.array([raw]),st)[0]
    x=decode_d_target(enc,a); return x if np.isfinite(x) and x>0 else np.nan


# -- Stress domains --

def _gen_stress_data(domain, n_clusters, n_reps):
    """Generate stress-domain datasets."""
    sampler = qmc.Sobol(d=3, scramble=True, seed={"low":142,"high":242,"loc":342}[domain])
    pts = sampler.random_base2(m={"low":5,"high":5,"loc":5}[domain])  # 32
    if domain=="low": betas=0.6+pts[:,0]*0.6; etas=100+pts[:,1]*9900; gammas=pts[:,2]*etas
    elif domain=="high": betas=4.0+pts[:,0]*4.0; etas=100+pts[:,1]*9900; gammas=pts[:,2]*etas
    else: betas=1.2+pts[:,0]*2.8; etas=100+pts[:,1]*9900; gammas=(-0.5+pts[:,2]*2.5)*etas
    datasets = {}
    for ci,(b,e,g) in enumerate(zip(betas,etas,gammas)):
        for ri in range(n_reps):
            for n in _N_VALUES:
                s=generate_sample(float(b),float(e),float(g),n,ri,seed=6000+100*(list({"low":1,"high":2,"loc":3}.values())[0])+ci)
                datasets[(ci,ri,n)]={"sample":s,"beta":float(b),"eta":float(e),"gamma":float(g),"true_x095":quantile_true(float(b),float(e),float(g),0.95)}
    return datasets

def evaluate_stress(models, domain, n_clusters=32, n_reps=10):
    print(f"\n  Stress: {domain} ({n_clusters*len(_N_VALUES)*n_reps} datasets)")
    datasets = _gen_stress_data(domain, n_clusters, n_reps)
    # Evaluate P and D ensemble means
    p_errs,d_errs=[],[]
    for (ci,ri,n),td in datasets.items():
        p_seeds=[s for (ns,s) in models["P"] if ns==n]
        p_vals=[_infer_p(models["P"][(n,s)],td["sample"])[0] for s in p_seeds]
        p_mean=float(np.nanmean(p_vals))
        d_items=[(s,m,st) for (ns,s),(m,st) in models["D"].items() if ns==n]
        d_vals=[_infer_d(m,st,td["sample"]) for _,m,st in d_items]
        d_mean=float(np.nanmean(d_vals))
        if np.isfinite(p_mean): p_errs.append((p_mean-td["true_x095"])/td["true_x095"])
        if np.isfinite(d_mean): d_errs.append((d_mean-td["true_x095"])/td["true_x095"])
    ps=summarize_standard_errors(p_errs); ds=summarize_standard_errors(d_errs)
    i=(ps["rmse"]-ds["rmse"])/ps["rmse"] if ps["rmse"] and ps["rmse"]>0 else 0
    return {"domain":domain,"P":ps,"D":ds,"I":i}


# -- P-route diagnostics --

def evaluate_p_diagnostics(models, datasets):
    """P-route β/η/γ errors, legality, γ-support violations."""
    beta_errs,eta_errs,gamma_errs=[],[],[]
    n_legal,n_total=0,0
    gamma_violations=0
    for (ci,ri,n),td in datasets.items():
        p_seeds=[s for (ns,s) in models["P"] if ns==n]
        for s in p_seeds:
            sample = td.sample if hasattr(td, 'sample') else td["sample"]
            beta = td.beta if hasattr(td, 'beta') else td["beta"]
            eta = td.eta if hasattr(td, 'eta') else td["eta"]
            gamma = td.gamma if hasattr(td, 'gamma') else td["gamma"]
            _,bh,eh,gh,ok=_infer_p(models["P"][(n,s)],sample)
            n_total+=1
            if ok:
                n_legal+=1
                beta_errs.append((bh-beta)/beta)
                eta_errs.append((eh-eta)/eta)
                gamma_errs.append((gh-gamma)/eta)
                if gh>=sample.min(): gamma_violations+=1
    return {
        "beta":summarize_standard_errors(beta_errs),"eta":summarize_standard_errors(eta_errs),
        "gamma":summarize_standard_errors(gamma_errs),
        "legal_rate":n_legal/n_total if n_total>0 else 0,
        "gamma_violations":gamma_violations,"n_total":n_total,
    }


# -- Conformal calibration --

def evaluate_conformal(models, n_cal=5000):
    """Split-conformal 90%/95% calibration by n for P and D."""
    print("\n  Conformal calibration ...")
    results={}
    for n_val in _N_VALUES:
        # Generate calibration data
        rng=np.random.default_rng(7000+n_val)
        betas=rng.uniform(1.2,4.0,size=n_cal); etas=rng.uniform(100,10000,size=n_cal)
        gammas=rng.uniform(0,1,size=n_cal)*etas
        p_residuals,d_residuals=[],[]
        for i in range(n_cal):
            b,e,g=float(betas[i]),float(etas[i]),float(gammas[i])
            sample=generate_sample(b,e,g,n_val,i,seed=8000)
            x095=quantile_true(b,e,g,0.95)
            # P ensemble prediction
            p_seeds=[seed for (ns,seed) in models["P"] if ns==n_val]
            p_vals=[_infer_p(models["P"][(n_val,seed)],sample)[0] for seed in p_seeds]
            p_pred=float(np.nanmean(p_vals))
            if np.isfinite(p_pred): p_residuals.append(abs(p_pred-x095))
            # D ensemble prediction
            d_items=[(seed,m,st) for (ns,seed),(m,st) in models["D"].items() if ns==n_val]
            d_vals=[_infer_d(m,st,sample) for _,m,st in d_items]
            d_pred=float(np.nanmean(d_vals))
            if np.isfinite(d_pred): d_residuals.append(abs(d_pred-x095))
        # Conformal quantiles
        results[str(n_val)]={
            "P_q90":float(np.quantile(p_residuals,0.9)) if p_residuals else np.nan,
            "P_q95":float(np.quantile(p_residuals,0.95)) if p_residuals else np.nan,
            "D_q90":float(np.quantile(d_residuals,0.9)) if d_residuals else np.nan,
            "D_q95":float(np.quantile(d_residuals,0.95)) if d_residuals else np.nan,
            "n_cal_P":len(p_residuals),"n_cal_D":len(d_residuals),
        }
    return results


# -- NIST 6061-T6 --

def evaluate_nist(models):
    """NIST 6061-T6: 500 deterministic splits per n, pinball loss + exceedance."""
    print("\n  NIST 6061-T6 ...")
    # Load NIST data (101 lifetimes)
    nist_path = _REPO_ROOT / "data" / "NIST" / "6061-T6.csv"
    if not nist_path.exists():
        # Try alternative path
        alt = _REPO_ROOT / "public" / "data" / "nist_6061_t6.csv"
        if alt.exists(): nist_path = alt
        else:
            print("  WARNING: NIST data not found, skipping")
            return None
    data = np.loadtxt(nist_path, delimiter=",", skiprows=1, usecols=0)
    if data.ndim==0: data=np.array([float(data)])
    n_total=len(data)

    results={}
    for n_val in _N_VALUES:
        pinball_p,pinball_d,pinball_mdm=[],[],[]
        exceed_p,exceed_d,exceed_mdm=[],[],[]
        for split in range(500):
            rng=np.random.default_rng(9000+n_val*1000+split)
            idx=rng.choice(n_total,size=n_val,replace=False)
            train=data[idx]
            holdout=np.setdiff1d(data,train)
            if len(holdout)==0: continue
            # P prediction
            p_preds=[]; p_seeds=[s for (ns,s) in models["P"] if ns==n_val]
            for s in p_seeds:
                v=_infer_p(models["P"][(n_val,s)],train)[0]
                if np.isfinite(v): p_preds.append(v)
            p_pred=float(np.nanmean(p_preds)) if p_preds else np.nan
            # D prediction
            d_preds=[]; d_items=[(s,m,st) for (ns,s),(m,st) in models["D"].items() if ns==n_val]
            for _,m,st in d_items:
                v=_infer_d(m,st,train)
                if np.isfinite(v): d_preds.append(v)
            d_pred=float(np.nanmean(d_preds)) if d_preds else np.nan
            # MDM
            mdm_r=run_method("mdm",train,offset=0.1)
            if mdm_r["beta_hat"] and mdm_r["eta_hat"] and mdm_r["gamma_hat"]:
                mdm_pred=quantile_true(float(mdm_r["beta_hat"]),float(mdm_r["eta_hat"]),float(mdm_r["gamma_hat"]),0.95)
            else: mdm_pred=np.nan
            # Pinball loss τ=0.05
            for h in holdout:
                tau=0.05
                def pb(p,h): return (tau-1)*(h-p) if h<p else tau*(h-p)
                if np.isfinite(p_pred): pinball_p.append(pb(p_pred,h))
                if np.isfinite(d_pred): pinball_d.append(pb(d_pred,h))
                if np.isfinite(mdm_pred): pinball_mdm.append(pb(mdm_pred,h))
            # Exceedance
            if np.isfinite(p_pred): exceed_p.append(float(np.mean(holdout>p_pred)))
            if np.isfinite(d_pred): exceed_d.append(float(np.mean(holdout>d_pred)))
            if np.isfinite(mdm_pred): exceed_mdm.append(float(np.mean(holdout>mdm_pred)))
        results[str(n_val)]={
            "pinball_P":float(np.mean(pinball_p)) if pinball_p else np.nan,
            "pinball_D":float(np.mean(pinball_d)) if pinball_d else np.nan,
            "pinball_MDM":float(np.mean(pinball_mdm)) if pinball_mdm else np.nan,
            "exceedance_P":float(np.mean(exceed_p)) if exceed_p else np.nan,
            "exceedance_D":float(np.mean(exceed_d)) if exceed_d else np.nan,
            "exceedance_MDM":float(np.mean(exceed_mdm)) if exceed_mdm else np.nan,
        }
    return results


# -- Main --

def run_b5(output_dir=None):
    if output_dir is None:
        output_dir = str(_EXTERNAL_ROOT / f"B5-boundary-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    code_tip=_git_tip()
    print(f"=== B5 Boundary & Holdout ==="); print(f"Output: {out}")

    print("\n[1] Loading models ...")
    models=load_models()
    print(f"  P:{len(models['P'])} D:{len(models['D'])} Dctrl:{len(models['Dctrl'])}")

    # Stress domains
    print("\n[2] Stress domains ...")
    stress={}
    for dom in ["low","high","loc"]:
        stress[dom]=evaluate_stress(models,dom)
        print(f"  {dom}: P_rmse={stress[dom]['P'].get('rmse',np.nan):.4f} D_rmse={stress[dom]['D'].get('rmse',np.nan):.4f} I={stress[dom]['I']:.4f}")

    # P diagnostics on core data (reuse B4 core design)
    print("\n[3] P-route diagnostics on core ...")
    from study02b.evaluate_b4 import generate_test_data
    core_datasets=generate_test_data()
    p_diag=evaluate_p_diagnostics(models,core_datasets)
    print(f"  Legal: {p_diag['legal_rate']:.4f} ({p_diag['n_total']} estimates)")
    print(f"  Beta RMSE: {p_diag['beta'].get('rmse',np.nan):.4f}")
    print(f"  Eta RMSE: {p_diag['eta'].get('rmse',np.nan):.4f}")
    print(f"  Gamma violations: {p_diag['gamma_violations']}")

    # Conformal
    print("\n[4] Conformal calibration ...")
    conf=evaluate_conformal(models)
    for nv in _N_VALUES:
        c=conf[str(nv)]
        print(f"  n={nv}: P_q90={c['P_q90']:.2f} D_q90={c['D_q90']:.2f} P_q95={c['P_q95']:.2f} D_q95={c['D_q95']:.2f}")

    # NIST
    print("\n[5] NIST 6061-T6 ...")
    nist=evaluate_nist(models)

    # Manifest
    manifest={
        "version":"1.0","run_id":out.name,
        "generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status":"complete","code_tip":code_tip,
        "stress":stress,"p_diagnostics":p_diag,"conformal":conf,"nist":nist,
    }
    mf_path=out/"manifest.json"
    mf_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    mf_sha=hashlib.sha256(mf_path.read_bytes()).hexdigest()
    print(f"\n  Manifest: {mf_path}\n  SHA256: {mf_sha}")
    print(f"\n=== B5 complete ===")
    return manifest

if __name__=="__main__": run_b5()
