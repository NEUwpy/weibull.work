"""B5 v4: Derived analysis from frozen v3 CSVs + corrected split-conformal calibration.

Redoes calibration with finite-sample quantile rule, then derives stress/
contamination/NIST statistics from immutable v3 row-level artifacts.
"""

from __future__ import annotations

import csv, hashlib, json, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import torch
from scipy.stats import spearmanr

_STUDY_CODE = Path(__file__).resolve().parent.parent
_REPO_ROOT = Path(__file__).resolve().parents[4]
for p in [str(_STUDY_CODE), str(_REPO_ROOT/"python")]:
    if p not in sys.path: sys.path.insert(0, p)

from studies.common.sample import generate_sample
from studies.common.metrics import quantile_true
from study02a.models import build_mlp
from study02a.representations import anchor_sample
from study02a.training import load_checkpoint
from study02b.representations import DTrainingStats, unstandardize_d, decode_d_target
from study02b.training import build_d_mlp

_EXTERNAL_ROOT = Path("C:/weibull-runs/study02/formal-b")
_V3_DIR = _EXTERNAL_ROOT / "B5-v3-20260801-062647"
_B3_MF = Path("C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json")
_B4_NPZ = Path("C:/weibull-runs/study02/formal-b/B4-core-20260801-051119/per_seed_predictions.npz")
_B4_CSV = Path("C:/weibull-runs/study02/formal-b/B4-core-20260801-051119/results.csv")
_N_VALUES = [5,7,10,15,20]

def _git_tip():
    return subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,cwd=str(_REPO_ROOT)).stdout.strip() or "unknown"

# -- Finite-sample split-conformal quantile --

def split_conformal_quantile(residuals, alpha):
    """q = ceil((n+1)*(1-alpha)) / n quantile of calibration residuals.
    alpha=0.1 → 90% coverage; alpha=0.05 → 95% coverage."""
    residuals=np.sort(np.asarray(residuals,dtype=float))
    n=len(residuals)
    if n==0: return np.nan
    idx=int(np.ceil((n+1)*(1-alpha)))-1
    idx=min(idx,n-1); idx=max(idx,0)
    return float(residuals[idx])


# -- Reload models for calibration only --

def _load_models():
    b3=json.loads(_B3_MF.read_text(encoding="utf-8")); ts=b3.get("target_stats",{})
    p,d={},{}
    for e in b3["p_checkpoints"]["entries"]:
        nv,s=e["n"],e["seed"]; st=load_checkpoint(Path(e["path"]).read_bytes())
        m=build_mlp(nv,[256,128,64],"silu",0.1); m.load_state_dict(st); m.eval(); p[(nv,s)]=m
    for e in b3["d_checkpoints"]:
        if e["group"]!="selected": continue
        nv,s,w=e["n"],e["seed"],e["widths"]; st=load_checkpoint(Path(e["path"]).read_bytes())
        m=build_d_mlp(nv,w,"silu",0.1); m.load_state_dict(st); m.eval()
        sr=ts.get(str(nv),{}); stats=DTrainingStats(mean=sr.get("mean",0),sd=sr.get("sd",1))
        d[(nv,s)]=(m,stats)
    return p,d

def _infer_p(m,sample):
    a=anchor_sample(sample); z=torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
    with torch.no_grad(): raw=m(z)
    from study02a.models import decode_model_output
    dec=decode_model_output(raw,torch.tensor([a.location],dtype=torch.float32),torch.tensor([a.scale],dtype=torch.float32))
    bf,ef,gf=float(dec[0,0]),float(dec[0,1]),float(dec[0,2])
    ok=bf>0 and ef>0 and np.isfinite([bf,ef,gf]).all()
    return quantile_true(bf,ef,gf,0.95) if ok else np.nan

def _infer_d(m,st,sample):
    a=anchor_sample(sample); z=torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
    with torch.no_grad(): raw=float(m(z).item())
    enc=unstandardize_d(np.array([raw]),st)[0]; x=decode_d_target(enc,a)
    return x if np.isfinite(x) and x>0 else np.nan


# -- Corrected calibration --

def recalibrate_conformal(p_models, d_models):
    print("\n[Calibration] Corrected split-conformal ...")
    thresholds={}; cal_evidence={}
    rng=np.random.default_rng(7000)
    for n_val in _N_VALUES:
        betas=rng.uniform(1.2,4.0,size=5000); etas=rng.uniform(100,10000,size=5000)
        gammas=rng.uniform(0,1,size=5000)*etas
        p_res,d_res,p_invalid,d_invalid=[],[],0,0
        for i in range(5000):
            b,e,g=float(betas[i]),float(etas[i]),float(gammas[i])
            sample=generate_sample(b,e,g,n_val,i,seed=8000); x095=quantile_true(b,e,g,0.95)
            p_seeds=[seed for (ns,seed) in p_models if ns==n_val]
            p_vals=[_infer_p(p_models[(n_val,seed)],sample) for seed in p_seeds]
            pm=np.nanmean([x for x in p_vals if np.isfinite(x)]) if p_vals else np.nan
            if np.isfinite(pm): p_res.append(abs(pm-x095))
            else: p_invalid+=1
            d_items=[(seed,m,st) for (ns,seed),(m,st) in d_models.items() if ns==n_val]
            d_vals=[_infer_d(m,st,sample) for _,m,st in d_items]
            dm=np.nanmean([x for x in d_vals if np.isfinite(x)]) if d_vals else np.nan
            if np.isfinite(dm): d_res.append(abs(dm-x095))
            else: d_invalid+=1
        thresholds[str(n_val)]={
            "P_q90":split_conformal_quantile(p_res,0.1),"P_q95":split_conformal_quantile(p_res,0.05),
            "D_q90":split_conformal_quantile(d_res,0.1),"D_q95":split_conformal_quantile(d_res,0.05)}
        cal_evidence[str(n_val)]={"n_cal_total":5000,"P_n_valid":len(p_res),"P_n_invalid":p_invalid,
                                   "D_n_valid":len(d_res),"D_n_invalid":d_invalid}
    return thresholds,cal_evidence


# -- Derived analyses from CSVs --

def _load_csv(path):
    with open(path,newline="",encoding="utf-8") as f: return list(csv.DictReader(f))

def _paired_bootstrap_ci(paired_diffs, n_clusters, n_boot=2000):
    """Cluster bootstrap on paired differences. paired_diffs[cluster] = list of diffs."""
    rng=np.random.default_rng(42); ci_all=list(range(n_clusters))
    boot=[]
    for _ in range(n_boot):
        ci_b=list(rng.choice(ci_all,size=n_clusters,replace=True))
        vals=[d for ci in ci_b for d in paired_diffs.get(ci,[])]
        boot.append(np.mean(vals) if vals else np.nan)
    boot=np.array(boot); boot=boot[np.isfinite(boot)]
    return float(np.percentile(boot,2.5)),float(np.percentile(boot,97.5)),float(np.mean(boot))


def analyze_stress(stress_dir):
    print("\n[Stress analysis] ...")
    results={}
    for domain in ["low","high","loc"]:
        rows=_load_csv(stress_dir/f"stress_{domain}.csv")
        domain_results={}
        for n_val in _N_VALUES:
            subset=[r for r in rows if int(r["n"])==n_val]
            n_total=len(subset)
            for route in ["P","D"]:
                valid=[r for r in subset if int(r.get(f"{route}_valid","0"))==1]
                n_valid=len(valid); n_fail=n_total-n_valid
                rel_errs=[]
                for r in valid:
                    pred=float(r[f"{route}_pred"]); tv=float(r["true_x095"])
                    if tv!=0: rel_errs.append((pred-tv)/tv)
                from studies.common.metrics import summarize_standard_errors
                s=summarize_standard_errors(rel_errs); s["n_total"]=n_total; s["n_valid"]=n_valid; s["n_failure"]=n_fail
                domain_results[f"{route}_n{n_val}"]=s
            # Paired P vs D on common valid
            paired_diffs=defaultdict(list)
            for r in subset:
                if int(r.get("P_valid","0")) and int(r.get("D_valid","0")):
                    ci=int(r["cluster"]); tv=float(r["true_x095"])
                    if tv!=0:
                        de=(float(r["D_pred"])-tv)/tv; pe=(float(r["P_pred"])-tv)/tv
                        paired_diffs[ci].append(de-pe)  # negative = D better
            n_clusters=len(set(int(r["cluster"]) for r in subset))
            ci_lo,ci_hi,mean_diff=_paired_bootstrap_ci(paired_diffs,n_clusters)
            domain_results[f"P_vs_D_n{n_val}"]={"mean_diff":mean_diff,"ci_lo":ci_lo,"ci_hi":ci_hi,
                                                  "direction":"D better" if ci_hi<0 else ("P better" if ci_lo>0 else "no difference")}
        results[domain]=domain_results
    return results


def analyze_contamination(contam_path):
    print("\n[Contamination analysis] ...")
    rows=_load_csv(contam_path)
    conditions=["clean","high3","high10","low_end","two_sided"]
    results={}
    for cond in conditions:
        subset=[r for r in rows if r["condition"]==cond]
        for route in ["P","D"]:
            valid=[r for r in subset if int(r.get(f"{route}_valid","0"))==1]
            n_total=len(subset); n_valid=len(valid)
            rel_errs=[]
            for r in valid:
                pred=float(r[f"{route}_pred"]); tv=float(r["true_x095"])
                if tv!=0: rel_errs.append((pred-tv)/tv)
            from studies.common.metrics import summarize_standard_errors
            s=summarize_standard_errors(rel_errs); s["n_total"]=n_total; s["n_valid"]=n_valid; s["n_failure"]=n_total-n_valid
            results[f"{route}_{cond}"]=s
    return results


def analyze_conformal_coverage(thresholds, stress_dir):
    print("\n[Conformal coverage analysis] ...")
    # Core coverage from v3 conformal_core.csv
    core_rows=_load_csv(_V3_DIR/"conformal_core.csv")
    core_summary={}
    for n_val in _N_VALUES:
        for route in ["P","D"]:
            subset=[r for r in core_rows if int(r["n"])==n_val and r["route"]==route]
            if subset:
                cov90=np.mean([int(r["covered_90"]) for r in subset])
                cov95=np.mean([int(r["covered_95"]) for r in subset])
                widths=[float(r["q95"]) for r in subset]
                true_vals=[float(r["true_x095"]) for r in subset]
                mean_width=np.mean(widths); mean_true=np.mean(true_vals)
                std_width=mean_width/mean_true if mean_true>0 else np.nan
                core_summary[f"{route}_n{n_val}"]={"cov90":cov90,"cov95":cov95,"n":len(subset),
                                                     "mean_width":mean_width,"std_width":std_width,
                                                     "spearman":"undefined (constant per-n width)"}
    # Stress coverage degradation
    stress_cov={}
    for domain in ["low","high","loc"]:
        rows=_load_csv(stress_dir/f"stress_{domain}.csv")
        for n_val in _N_VALUES:
            for route in ["P","D"]:
                subset=[r for r in rows if int(r["n"])==n_val]
                th=thresholds[str(n_val)]; q95=th[f"{route}_q95"]
                covered=0; total=0
                for r in subset:
                    pred=float(r.get(f"{route}_pred",None) or np.nan)
                    tv=float(r.get("true_x095",None) or np.nan)
                    if np.isfinite(pred) and np.isfinite(tv):
                        total+=1
                        if abs(pred-tv)<=q95: covered+=1
                stress_cov[f"{domain}_{route}_n{n_val}"]={"cov95":covered/total if total else np.nan,"n":total}
    return {"core":core_summary,"stress_degradation":stress_cov}


def analyze_nist(nist_path):
    print("\n[NIST analysis] ...")
    rows=_load_csv(nist_path)
    results={}
    for n_val in _N_VALUES:
        subset=[r for r in rows if int(r["n"])==n_val]
        splits=set(int(r["split"]) for r in subset)
        n_splits=len(splits)
        route_results={}
        for route in ["P","D","MDM","MLE","LRE"]:
            valid=[r for r in subset if int(r.get(f"{route}_valid","0"))==1]
            n_total=len(subset); n_valid=len(valid); fail_rate=(n_total-n_valid)/n_total
            pb=[float(r[f"{route}_pinball"]) for r in valid if np.isfinite(float(r.get(f"{route}_pinball",np.nan)))]
            exc=[float(r[f"{route}_exceed"]) for r in valid if np.isfinite(float(r.get(f"{route}_exceed",np.nan)))]
            # Paired effects on common-valid splits
            paired_diffs=defaultdict(list)
            for other in ["P","D","MDM","MLE","LRE"]:
                if other<=route: continue
                common=[r for r in valid if int(r.get(f"{other}_valid","0"))==1]
                if not common: continue
                diffs=[]
                for r in common:
                    dp=float(r[f"{route}_pinball"]); op=float(r[f"{other}_pinball"])
                    if np.isfinite(dp) and np.isfinite(op): diffs.append(dp-op)
                ci_lo=np.nan; ci_hi=np.nan
                if len(diffs)>1:
                    boot=[]; rng=np.random.default_rng(42)
                    for _ in range(2000):
                        idx=rng.choice(len(diffs),size=len(diffs),replace=True)
                        boot.append(np.mean([diffs[i] for i in idx]))
                    boot=np.array(boot); ci_lo=float(np.percentile(boot,2.5)); ci_hi=float(np.percentile(boot,97.5))
                route_results[f"{route}_vs_{other}"]={"mean_pinball_diff":np.mean(diffs) if diffs else np.nan,
                                                        "ci_lo":ci_lo,"ci_hi":ci_hi,"n_common":len(common)}
            route_results[route]={"pinball_mean":np.mean(pb) if pb else np.nan,
                                  "exceedance_mean":np.mean(exc) if exc else np.nan,
                                  "n_valid":n_valid,"n_total_splits":n_total,"split_failure_rate":fail_rate,
                                  "n_unique_splits":n_splits}
        results[str(n_val)]=route_results
    return results


# -- Main --

def run_analyze(output_dir=None):
    if output_dir is None:
        output_dir=str(_EXTERNAL_ROOT/f"B5-v4-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    code_tip=_git_tip()
    print(f"=== B5 v4 Derived Analysis ===\nOutput: {out}")

    # Redo calibration with corrected quantile
    p_models,d_models=_load_models()
    thresholds,cal_evidence=recalibrate_conformal(p_models,d_models)
    for n_val in _N_VALUES:
        t=thresholds[str(n_val)]
        print(f"  n={n_val}: P_q95={t['P_q95']:.2f} D_q95={t['D_q95']:.2f}")

    # Derive statistics from v3 CSVs
    stress_results=analyze_stress(_V3_DIR)
    contam_results=analyze_contamination(_V3_DIR/"contamination.csv")
    conf_results=analyze_conformal_coverage(thresholds, _V3_DIR)
    nist_results=analyze_nist(_V3_DIR/"nist_splits.csv")

    # Show key findings
    print("\n  Stress low n=5 D validity:", stress_results["low"].get("D_n5",{}).get("n_valid","?"),"/",stress_results["low"].get("D_n5",{}).get("n_total","?"))
    pd=stress_results["low"].get("P_vs_D_n5",{})
    print(f"  Stress low n=5 P vs D diff: {pd.get('mean_diff',np.nan):.4f} [{pd.get('ci_lo',np.nan):.4f},{pd.get('ci_hi',np.nan):.4f}] → {pd.get('direction','?')}")

    # Manifest
    v3_mf_sha=hashlib.sha256((_V3_DIR/"manifest.json").read_bytes()).hexdigest()
    v3_csvs={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(_V3_DIR.glob("*.csv"))}
    manifest={
        "version":"4.0","run_id":out.name,"generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status":"complete","code_tip":code_tip,
        "input_hashes":{"b5_v3_manifest":v3_mf_sha,"b5_v3_csvs":v3_csvs},
        "conformal":{"thresholds":thresholds,"calibration_evidence":cal_evidence,
                     "core_coverage":conf_results["core"],
                     "stress_degradation":conf_results["stress_degradation"]},
        "stress":stress_results,"contamination":contam_results,"nist":nist_results,
    }
    mf_path=out/"manifest.json"
    mf_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    mf_sha=hashlib.sha256(mf_path.read_bytes()).hexdigest()
    print(f"\n  Manifest: {mf_path}\n  SHA256: {mf_sha}")
    print(f"\n=== B5 v4 complete ===")
    return manifest

if __name__=="__main__": run_analyze()
