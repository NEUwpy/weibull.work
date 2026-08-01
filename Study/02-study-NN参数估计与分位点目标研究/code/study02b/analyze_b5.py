"""B5 v5: Derived analysis from frozen v3 CSVs + accepted v4 calibration manifest.

Analysis-only correction. No new fit and no rerun of stress, contamination,
NIST, P/D inference, or calibration. Reads the frozen v3 row-level CSVs and the
accepted v4 calibration manifest (corrected split-conformal thresholds), and
re-derives the preregistered statistics with corrected estimands:

- stress: paired squared-relative-error loss difference on common-valid rows,
  cluster-bootstrapped (implied RMSE effect reported); signed bias kept
  descriptive only; BH-adjusted secondary support across domain x n;
- contamination: each contaminated condition versus its exact paired clean row
  (cluster + replicate), per-route validity changes and paired cluster-bootstrap
  effect CIs; P-vs-D degradation only on an explicit common-valid paired
  estimand; no MDM claim (CSV contains only P/D);
- conformal: core coverage recomputed from pred / true_x095 and the v4
  thresholds (90% and 95%), absolute + standardized width, total/valid/invalid;
  stress reports conditional-on-valid 90/95 coverage plus availability, never
  as unconditional; Spearman explicitly undefined (constant per-route x n width);
- NIST: paired pinball and paired exceedance-effect CIs on common-valid splits;
  exactly 500 unique splits per n and per-route failure rates; interpretation
  (exceedance < 0.95 is optimistic/anti-conservative) and known-truth limitation.
"""

from __future__ import annotations

import csv, hashlib, json, subprocess, sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
import numpy as np

_STUDY_CODE = Path(__file__).resolve().parent.parent
_REPO_ROOT = Path(__file__).resolve().parents[4]
for p in [str(_STUDY_CODE), str(_REPO_ROOT/"python")]:
    if p not in sys.path: sys.path.insert(0, p)

from studies.common.metrics import summarize_standard_errors

_EXTERNAL_ROOT = Path("C:/weibull-runs/study02/formal-b")
_V3_DIR = _EXTERNAL_ROOT / "B5-v3-20260801-062647"
_V4_DIR = _EXTERNAL_ROOT / "B5-v4-20260801-063558"
_V4_MANIFEST = _V4_DIR / "manifest.json"
_N_VALUES = [5, 7, 10, 15, 20]

def _git_tip():
    return subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,cwd=str(_REPO_ROOT)).stdout.strip() or "unknown"

# -- Finite-sample split-conformal quantile (kept for reference/tests) --

def split_conformal_quantile(residuals, alpha):
    """q = ceil((n+1)*(1-alpha)) / n quantile of calibration residuals.
    alpha=0.1 → 90% coverage; alpha=0.05 → 95% coverage."""
    residuals=np.sort(np.asarray(residuals,dtype=float))
    n=len(residuals)
    if n==0: return np.nan
    idx=int(np.ceil((n+1)*(1-alpha)))-1
    idx=min(idx,n-1); idx=max(idx,0)
    return float(residuals[idx])


# -- Small bootstrap / inference helpers --

def _load_csv(path):
    with open(path,newline="",encoding="utf-8") as f: return list(csv.DictReader(f))


def _cluster_bootstrap_paired(paired_diffs, n_clusters, n_boot=2000, seed=42):
    """Cluster bootstrap on paired differences (cluster -> list of floats).

    Resamples clusters with replacement and pools the rows of the resampled
    clusters each replicate. Returns the observed mean, bootstrap mean, 95% CI,
    and a two-sided bootstrap p-value for H0: mean difference = 0.
    """
    rng=np.random.default_rng(seed)
    ci_all=list(range(n_clusters))
    all_vals=[v for lst in paired_diffs.values() for v in lst]
    obs=float(np.mean(all_vals)) if all_vals else np.nan
    boot=[]
    for _ in range(n_boot):
        ci_b=list(rng.choice(ci_all,size=n_clusters,replace=True))
        vals=[d for ci in ci_b for d in paired_diffs.get(ci,[])]
        boot.append(np.mean(vals) if vals else np.nan)
    boot=np.array(boot); boot=boot[np.isfinite(boot)]
    if boot.size==0:
        return {"mean":obs,"boot_mean":np.nan,"ci_lo":np.nan,"ci_hi":np.nan,"p":np.nan}
    p=2.0*min(float(np.mean(boot<=0)),float(np.mean(boot>=0)))
    return {"mean":obs,"boot_mean":float(np.mean(boot)),
            "ci_lo":float(np.percentile(boot,2.5)),"ci_hi":float(np.percentile(boot,97.5)),
            "p":min(p,1.0)}


def _split_bootstrap_ci(diffs, n_boot=2000, seed=42):
    """Non-clustered bootstrap CI over split-level differences."""
    diffs=[d for d in diffs if np.isfinite(d)]
    if not diffs: return {"mean":np.nan,"ci_lo":np.nan,"ci_hi":np.nan}
    rng=np.random.default_rng(seed)
    boot=[]
    for _ in range(n_boot):
        idx=rng.choice(len(diffs),size=len(diffs),replace=True)
        boot.append(np.mean([diffs[i] for i in idx]))
    boot=np.array(boot)
    return {"mean":float(np.mean(diffs)),"ci_lo":float(np.percentile(boot,2.5)),
            "ci_hi":float(np.percentile(boot,97.5))}


def _bh_qvalues(pvals):
    """Benjamini-Hochberg adjusted q-values (monotone), skipping NaN."""
    finite={k:v for k,v in pvals.items() if v==v}
    keys=sorted(finite,key=lambda k:finite[k])
    m=len(keys)
    q={}; prev=1.0
    for i,k in enumerate(keys,1):
        qv=min(prev,finite[k]*m/i)
        q[k]=qv; prev=qv
    return q


# -- Derived analyses from CSVs --

def analyze_stress(stress_dir):
    print("\n[Stress analysis] ...")
    results={}
    bh_pvals={}
    for domain in ["low","high","loc"]:
        rows=_load_csv(stress_dir/f"stress_{domain}.csv")
        n_vals=sorted({int(r["n"]) for r in rows} & set(_N_VALUES))
        domain_results={}
        for n_val in n_vals:
            subset=[r for r in rows if int(r["n"])==n_val]
            n_total=len(subset)
            route_stats={}
            for route in ["P","D"]:
                valid=[r for r in subset if int(r.get(f"{route}_valid","0"))==1]
                n_valid=len(valid); n_fail=n_total-n_valid
                rel_errs=[]
                for r in valid:
                    pred=float(r[f"{route}_pred"]); tv=float(r["true_x095"])
                    if tv!=0 and np.isfinite(pred): rel_errs.append((pred-tv)/tv)
                s=summarize_standard_errors(rel_errs)
                route_stats[route]={**s,"n_total":n_total,"n_valid":n_valid,
                                    "n_failure":n_fail,
                                    "failure_rate":n_fail/n_total if n_total else np.nan}
            # Paired squared-relative-error loss on common-valid rows
            paired=defaultdict(list); bias_paired=defaultdict(list)
            d_sqres=[]; p_sqres=[]
            for r in subset:
                if int(r.get("P_valid","0")) and int(r.get("D_valid","0")):
                    tv=float(r["true_x095"])
                    if tv==0: continue
                    dp=float(r["D_pred"]); pp=float(r["P_pred"])
                    if not (np.isfinite(dp) and np.isfinite(pp)): continue
                    d_sqre=((dp-tv)/tv)**2; p_sqre=((pp-tv)/tv)**2
                    paired[int(r["cluster"])].append(d_sqre-p_sqre)
                    bias_paired[int(r["cluster"])].append((dp-tv)/tv-(pp-tv)/tv)
                    d_sqres.append(d_sqre); p_sqres.append(p_sqre)
            n_clusters=len(set(int(r["cluster"]) for r in subset))
            boot=_cluster_bootstrap_paired(paired,n_clusters)
            bias_boot=_cluster_bootstrap_paired(bias_paired,n_clusters)
            d_rmse=float(np.sqrt(np.mean(d_sqres))) if d_sqres else np.nan
            p_rmse=float(np.sqrt(np.mean(p_sqres))) if p_sqres else np.nan
            if boot["ci_hi"]<0: direction="D better"
            elif boot["ci_lo"]>0: direction="P better"
            else: direction="no difference"
            domain_results[f"n{n_val}"]={
                "route_stats":route_stats,
                "common_valid":{"n_rows":len(d_sqres),"n_clusters":n_clusters},
                "paired_loss":{"mean_sqre_diff":boot["mean"],"boot_mean":boot["boot_mean"],
                               "ci_lo":boot["ci_lo"],"ci_hi":boot["ci_hi"],"p":boot["p"],
                               "rmse_D":d_rmse,"rmse_P":p_rmse,
                               "rmse_effect_D_minus_P":(d_rmse-p_rmse) if (d_rmse==d_rmse and p_rmse==p_rmse) else np.nan,
                               "direction":direction},
                "signed_bias_diff":{"mean":bias_boot["mean"],"ci_lo":bias_boot["ci_lo"],
                                    "ci_hi":bias_boot["ci_hi"],
                                    "note":"descriptive only; not an accuracy difference"},
            }
            bh_pvals[f"{domain}_n{n_val}"]=boot["p"]
        results[domain]=domain_results
    # BH across domain x n secondary family
    qvals=_bh_qvalues(bh_pvals)
    support={}
    for key,q in qvals.items():
        dom,nv=key.rsplit("_n",1)
        cell=results[dom][f"n{nv}"]
        direction=cell["paired_loss"]["direction"]
        marker="supported (BH)" if q<=0.05 else "not significant (BH)"
        support[key]=marker
        cell["bh"]={"p":bh_pvals[key],"q":q,"support":marker,"direction":direction}
    # cells with no common-valid rows (NaN p) get explicit marker
    for key,p in bh_pvals.items():
        if p!=p:
            dom,nv=key.rsplit("_n",1)
            results[dom][f"n{nv}"]["bh"]={"p":np.nan,"q":np.nan,
                "support":"not computable (no common-valid rows)","direction":"n/a"}
    results["_bh"]={"method":"Benjamini-Hochberg","alpha":0.05,"m":len(qvals),
                    "p_values":{k:float(v) for k,v in bh_pvals.items()},
                    "q_values":{k:float(v) for k,v in qvals.items()},"support":support}
    return results


def analyze_contamination(contam_path):
    print("\n[Contamination analysis] ...")
    rows=_load_csv(contam_path)
    clean_rows=[r for r in rows if r["condition"]=="clean"]
    clean_by_key={(int(r["cluster"]),int(r["replicate"])):r for r in clean_rows}
    conditions=[c for c in ["high3","high10","low_end","two_sided"]
                if any(r["condition"]==c for r in rows)]
    results={}
    for cond in conditions:
        cond_rows=[r for r in rows if r["condition"]==cond]
        cond_result={}
        for route in ["P","D"]:
            diffs=defaultdict(list); clean_sqre=defaultdict(list); cond_sqre=defaultdict(list)
            validity={"clean_valid_cond_valid":0,"clean_valid_cond_invalid":0,
                      "clean_invalid_cond_valid":0,"both_invalid":0,"no_clean_row":0}
            for r in cond_rows:
                key=(int(r["cluster"]),int(r["replicate"]))
                c=clean_by_key.get(key)
                if c is None:
                    validity["no_clean_row"]+=1; continue
                c_valid=int(c.get(f"{route}_valid","0"))==1
                k_valid=int(r.get(f"{route}_valid","0"))==1
                tv=float(r["true_x095"])
                if c_valid and k_valid:
                    validity["clean_valid_cond_valid"]+=1
                    if tv!=0:
                        cs=((float(c[f"{route}_pred"])-tv)/tv)**2
                        ks=((float(r[f"{route}_pred"])-tv)/tv)**2
                        diffs[int(r["cluster"])].append(ks-cs)
                        clean_sqre[int(r["cluster"])].append(cs)
                        cond_sqre[int(r["cluster"])].append(ks)
                elif c_valid and not k_valid: validity["clean_valid_cond_invalid"]+=1
                elif k_valid and not c_valid: validity["clean_invalid_cond_valid"]+=1
                else: validity["both_invalid"]+=1
            n_clusters=len(set(int(r["cluster"]) for r in cond_rows))
            boot=_cluster_bootstrap_paired(diffs,n_clusters)
            c_all=[v for lst in clean_sqre.values() for v in lst]
            k_all=[v for lst in cond_sqre.values() for v in lst]
            cond_result[route]={
                "validity_changes":validity,
                "common_valid":{"n_rows":len(c_all),"n_clusters":n_clusters},
                "paired_sqre_change":boot,
                "clean_rmse":float(np.sqrt(np.mean(c_all))) if c_all else np.nan,
                "cond_rmse":float(np.sqrt(np.mean(k_all))) if k_all else np.nan,
            }
        # P vs D degradation on explicit common-valid paired estimand (4-way valid)
        pd_diff=defaultdict(list); n_4way=0
        for r in cond_rows:
            key=(int(r["cluster"]),int(r["replicate"]))
            c=clean_by_key.get(key)
            if c is None: continue
            tv=float(r["true_x095"])
            ok=all(int(c.get(f"{x}_valid","0"))==1 and int(r.get(f"{x}_valid","0"))==1 for x in ["P","D"])
            if not ok or tv==0: continue
            d_deg=((float(r["D_pred"])-tv)/tv)**2-((float(c["D_pred"])-tv)/tv)**2
            p_deg=((float(r["P_pred"])-tv)/tv)**2-((float(c["P_pred"])-tv)/tv)**2
            pd_diff[int(r["cluster"])].append(d_deg-p_deg)
            n_4way+=1
        n_clusters=len(set(int(r["cluster"]) for r in cond_rows))
        pd_boot=_cluster_bootstrap_paired(pd_diff,n_clusters)
        if pd_boot["ci_hi"]<0: direction="D degrades less"
        elif pd_boot["ci_lo"]>0: direction="P degrades less"
        else: direction="no significant difference"
        cond_result["P_vs_D_degradation"]={
            "common_valid_4way":n_4way,
            "paired_diff_D_minus_P":pd_boot,
            "direction":direction,
            "note":"negative = D degrades less, on common-valid 4-way rows"}
        results[cond]=cond_result
    return results


def analyze_conformal_coverage(thresholds, stress_dir, core_path=None):
    print("\n[Conformal coverage analysis] ...")
    if core_path is None: core_path=_V3_DIR/"conformal_core.csv"
    core_rows=_load_csv(core_path)
    core_summary={}
    n_vals=sorted({int(r["n"]) for r in core_rows} & set(_N_VALUES))
    for n_val in n_vals:
        for route in ["P","D"]:
            subset=[r for r in core_rows if int(r["n"])==n_val and r["route"]==route]
            total=len(subset)
            valid=[r for r in subset if np.isfinite(float(r["pred"])) and np.isfinite(float(r["true_x095"]))]
            n_valid=len(valid); n_invalid=total-n_valid
            th=thresholds[str(n_val)]; q90=th[f"{route}_q90"]; q95=th[f"{route}_q95"]
            cov90=np.mean([abs(float(r["pred"])-float(r["true_x095"]))<=q90 for r in valid]) if valid else np.nan
            cov95=np.mean([abs(float(r["pred"])-float(r["true_x095"]))<=q95 for r in valid]) if valid else np.nan
            mean_true=float(np.mean([abs(float(r["true_x095"])) for r in valid])) if valid else np.nan
            core_summary[f"{route}_n{n_val}"]={
                "cov90":cov90,"cov95":cov95,
                "abs_width90":2*q90,"abs_width95":2*q95,
                "std_width90":(2*q90/mean_true) if mean_true else np.nan,
                "std_width95":(2*q95/mean_true) if mean_true else np.nan,
                "n_total":total,"n_valid":n_valid,"n_invalid":n_invalid,
                "spearman":"undefined (constant width per route x n)"}
    # Stress: conditional-on-valid coverage + availability (never unconditional)
    stress_cov={}
    for domain in ["low","high","loc"]:
        rows=_load_csv(stress_dir/f"stress_{domain}.csv")
        n_vals=sorted({int(r["n"]) for r in rows} & set(_N_VALUES))
        for n_val in n_vals:
            subset=[r for r in rows if int(r["n"])==n_val]
            total=len(subset)
            for route in ["P","D"]:
                th=thresholds[str(n_val)]; q90=th[f"{route}_q90"]; q95=th[f"{route}_q95"]
                valid=[r for r in subset if int(r.get(f"{route}_valid","0"))==1
                       and np.isfinite(float(r.get(f"{route}_pred",np.nan)))
                       and np.isfinite(float(r["true_x095"]))]
                n_valid=len(valid)
                cov90=np.mean([abs(float(r[f"{route}_pred"])-float(r["true_x095"]))<=q90 for r in valid]) if valid else np.nan
                cov95=np.mean([abs(float(r[f"{route}_pred"])-float(r["true_x095"]))<=q95 for r in valid]) if valid else np.nan
                stress_cov[f"{domain}_{route}_n{n_val}"]={
                    "cov90_cond_valid":cov90,"cov95_cond_valid":cov95,
                    "n_valid":n_valid,"n_total":total,
                    "availability":(n_valid/total if total else np.nan),
                    "note":"conditional on valid rows; not an unconditional guarantee"}
    return {"core":core_summary,"stress_degradation":stress_cov}


def analyze_nist(nist_path):
    print("\n[NIST analysis] ...")
    rows=_load_csv(nist_path)
    routes=["P","D","MDM","MLE","LRE"]
    results={}
    n_vals=sorted({int(r["n"]) for r in rows} & set(_N_VALUES))
    for n_val in n_vals:
        subset=[r for r in rows if int(r["n"])==n_val]
        splits=set(int(r["split"]) for r in subset)
        n_splits=len(splits)
        route_stats={}
        for route in routes:
            valid=[r for r in subset if int(r.get(f"{route}_valid","0"))==1]
            n_total=len(subset); n_valid=len(valid)
            pb=[float(r[f"{route}_pinball"]) for r in valid if np.isfinite(float(r.get(f"{route}_pinball",np.nan)))]
            exc=[float(r[f"{route}_exceed"]) for r in valid if np.isfinite(float(r.get(f"{route}_exceed",np.nan)))]
            route_stats[route]={"pinball_mean":np.mean(pb) if pb else np.nan,
                                "exceedance_mean":np.mean(exc) if exc else np.nan,
                                "n_valid":n_valid,"n_total_splits":n_total,
                                "split_failure_rate":(n_total-n_valid)/n_total if n_total else np.nan}
        paired={}
        for i,a in enumerate(routes):
            for b in routes[i+1:]:
                common=[r for r in subset if int(r.get(f"{a}_valid","0"))==1 and int(r.get(f"{b}_valid","0"))==1]
                pb_diffs=[float(r[f"{a}_pinball"])-float(r[f"{b}_pinball"]) for r in common
                          if np.isfinite(float(r.get(f"{a}_pinball",np.nan))) and np.isfinite(float(r.get(f"{b}_pinball",np.nan)))]
                ex_diffs=[float(r[f"{a}_exceed"])-float(r[f"{b}_exceed"]) for r in common
                          if np.isfinite(float(r.get(f"{a}_exceed",np.nan))) and np.isfinite(float(r.get(f"{b}_exceed",np.nan)))]
                paired[f"{a}_vs_{b}"]={"n_common_splits":len(common),
                                       "pinball_effect":_split_bootstrap_ci(pb_diffs),
                                       "exceedance_effect":_split_bootstrap_ci(ex_diffs)}
        results[str(n_val)]={"n_unique_splits":n_splits,"exact_500":n_splits==500,
                             "route_stats":route_stats,"paired":paired}
    results["_interpretation"]=(
        "exceedance below 0.95 means the predicted x0.95 is too high "
        "(optimistic / anti-conservative). This real dataset has no known true "
        "x0.95, so paired effects are comparative only and not a generalization proof.")
    return results


# -- Main --

def run_analyze(output_dir=None):
    if output_dir is None:
        output_dir=str(_EXTERNAL_ROOT/f"B5-v5-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    out=Path(output_dir); out.mkdir(parents=True,exist_ok=True)
    code_tip=_git_tip()
    print(f"=== B5 v5 Derived Analysis (analysis-only) ===\nOutput: {out}")

    # Accepted v4 calibration manifest (corrected thresholds) — no recalibration
    v4_mf=json.loads(_V4_MANIFEST.read_text(encoding="utf-8"))
    thresholds=v4_mf["conformal"]["thresholds"]
    cal_evidence=v4_mf["conformal"]["calibration_evidence"]
    v4_mf_sha=hashlib.sha256(_V4_MANIFEST.read_bytes()).hexdigest()

    stress_results=analyze_stress(_V3_DIR)
    contam_results=analyze_contamination(_V3_DIR/"contamination.csv")
    conf_results=analyze_conformal_coverage(thresholds,_V3_DIR)
    nist_results=analyze_nist(_V3_DIR/"nist_splits.csv")

    v3_mf_sha=hashlib.sha256((_V3_DIR/"manifest.json").read_bytes()).hexdigest()
    v3_csvs={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(_V3_DIR.glob("*.csv"))}
    manifest={
        "version":"5.0","run_id":out.name,
        "generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status":"complete","code_tip":code_tip,
        "analysis_type":"derived analysis only — no new fit, no rerun of stress/contamination/NIST/P-D inference or calibration",
        "input_hashes":{
            "b5_v3_manifest":v3_mf_sha,
            "b5_v3_csvs":v3_csvs,
            "b5_v4_calibration_manifest":{"path":str(_V4_MANIFEST),"sha256":v4_mf_sha},
        },
        "conformal":{"thresholds":thresholds,"calibration_evidence":cal_evidence,
                     "core_coverage":conf_results["core"],
                     "stress_degradation":conf_results["stress_degradation"]},
        "stress":stress_results,
        "contamination":contam_results,
        "nist":nist_results,
    }
    mf_path=out/"manifest.json"
    mf_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False,default=str),encoding="utf-8")
    mf_sha=hashlib.sha256(mf_path.read_bytes()).hexdigest()
    print(f"\n  Manifest: {mf_path}\n  SHA256: {mf_sha}")
    print("\n=== B5 v5 complete ===")
    return manifest

if __name__=="__main__": run_analyze()
