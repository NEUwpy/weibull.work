"""B4 v4: Core test with hierarchical seed bootstrap, per-seed artifact, traditional CIs.

Key corrections:
- Seed-level bootstrap: one paired seed multiset per rep, applied to all rows
- Per-seed predictions persisted as .npz
- D-vs-traditional paired cluster bootstrap CIs
- Per-n heterogeneity with uncertainty
"""

from __future__ import annotations

import csv, hashlib, json, subprocess, sys
from datetime import datetime, timezone
from dataclasses import dataclass
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
_B3_MANIFEST_PATH = Path("C:/weibull-runs/study02/formal-b/B3-training-20260731-121958/manifest.json")
_CONFIG_DIR = _REPO_ROOT / "Study/02-study-NN参数估计与分位点目标研究/configs"

_N_CLUSTERS, _N_REPLICATES = 64, 20
_N_VALUES = [5, 7, 10, 15, 20]
_N_BOOTSTRAP = 2000
_SEED_TEST_NS = 6000

def _git_tip(): return subprocess.run(["git","rev-parse","HEAD"],capture_output=True,text=True,cwd=str(_REPO_ROOT)).stdout.strip() or "unknown"


@dataclass
class TestDataset:
    sample: np.ndarray; beta: float; eta: float; gamma: float; true_x095: float


def generate_test_data():
    sampler = qmc.Sobol(d=3, scramble=True, seed=42)
    pts = sampler.random_base2(m=6)
    betas = 1.2 + pts[:,0]*(4.0-1.2); etas = 100.0 + pts[:,1]*(10000.0-100.0)
    gammas = pts[:,2]*etas
    datasets = {}
    total = _N_CLUSTERS*_N_REPLICATES*len(_N_VALUES); count = 0
    for ci,(b,e,g) in enumerate(zip(betas,etas,gammas)):
        for ri in range(_N_REPLICATES):
            for n in _N_VALUES:
                s = generate_sample(float(b),float(e),float(g),n,ri,seed=_SEED_TEST_NS+ci)
                x = quantile_true(float(b),float(e),float(g),0.95)
                datasets[(ci,ri,n)] = TestDataset(sample=s,beta=float(b),eta=float(e),gamma=float(g),true_x095=x)
                count+=1
                if count%1000==0: print(f"  Generated {count}/{total}")
    return datasets


# -- Model loading --

def load_all_models(b3):
    ts = b3.get("target_stats",{})
    p = {}; [p.update({(e["n"],e["seed"]):_l(e["path"],lambda n=e["n"]:build_mlp(n,[256,128,64],"silu",0.1))}) for e in b3["p_checkpoints"]["entries"]]
    def _g(grp):
        m={}
        for e in b3["d_checkpoints"]:
            if e["group"]!=grp: continue
            s=ts.get(str(e["n"]),{})
            st=DTrainingStats(mean=s.get("mean",0),sd=s.get("sd",1))
            m[(e["n"],e["seed"])]=(_l(e["path"],lambda n=e["n"],w=e["widths"]:build_d_mlp(n,w,"silu",0.1)),st)
        return m
    return {"P":p,"D":_g("selected"),"Dctrl":_g("controlled")}

def _l(path,f): state=load_checkpoint(Path(path).read_bytes()); m=f(); m.load_state_dict(state); m.eval(); return m


# -- Inference (per-seed arrays) --

def _infer_p_all(models, n, sample):
    seeds=[s for (ns,s) in models if ns==n]
    a=anchor_sample(sample); z=torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0)
    vals=[]
    for s in seeds:
        with torch.no_grad(): raw=models[(n,s)](z)
        dec=decode_model_output(raw,torch.tensor([a.location],dtype=torch.float32),torch.tensor([a.scale],dtype=torch.float32))
        bf,ef,gf=float(dec[0,0]),float(dec[0,1]),float(dec[0,2])
        vals.append(quantile_true(bf,ef,gf,0.95) if (bf>0 and ef>0 and np.isfinite([bf,ef,gf]).all()) else np.nan)
    return np.array(vals)

def _infer_d_all(models, n, sample):
    items=[(s,m,st) for (ns,s),(m,st) in models.items() if ns==n]
    a=anchor_sample(sample); z=torch.from_numpy(a.z.astype(np.float32)).unsqueeze(0); vals=[]
    for _,m,st in items:
        with torch.no_grad(): raw=float(m(z).item())
        vals.append(decode_d_target(unstandardize_d(np.array([raw]),st)[0],a))
    return np.array(vals)

def _infer_trad(mid, kw, sample, beta, eta, gamma):
    r=run_method(mid,sample,**kw)
    bh,eh,gh=r["beta_hat"],r["eta_hat"],r["gamma_hat"]
    if bh is None or eh is None or gh is None: return np.nan,"failure"
    st=check_status(float(bh),float(eh),float(gh),beta,eta,gamma,converged=r.get("converged",True),sample_min=float(sample.min()))
    if st=="failure": return np.nan,"failure"
    return quantile_true(float(bh),float(eh),float(gh),0.95),"success"


# -- Bootstrap helpers --

def _paired_cluster_bootstrap(d_errs, p_errs, cluster_ids, rng):
    """One bootstrap replicate: resample clusters, aggregate per-row relative errors."""
    ci_b = list(rng.choice(cluster_ids, size=len(cluster_ids), replace=True))
    de,pe=[],[]
    for ci in ci_b:
        de.extend(d_errs.get(ci,[])); pe.extend(p_errs.get(ci,[]))
    dr=np.sqrt(np.mean(np.array(de)**2)) if de else np.nan
    pr=np.sqrt(np.mean(np.array(pe)**2)) if pe else np.nan
    return dr,pr


def _hierarchical_bootstrap_d_vs_p(route_errs_d, route_errs_p, datasets, d_seed_dict, p_seed_dict, rng):
    """Hierarchical: cluster resample + seed multiset (one draw per replicate, applied to all rows)."""
    ci_all = list(range(_N_CLUSTERS))
    ci_b = list(rng.choice(ci_all, size=_N_CLUSTERS, replace=True))
    # Draw ONE paired seed multiset for this bootstrap replicate
    n_seeds_p = 10; n_seeds_d = 10
    p_seed_idx = rng.choice(n_seeds_p, size=n_seeds_p, replace=True)
    d_seed_idx = rng.choice(n_seeds_d, size=n_seeds_d, replace=True)

    per_n_vals = []
    for n_val in _N_VALUES:
        d_errs_n = []; p_errs_n = []
        for ci in ci_b:
            for ri in range(_N_REPLICATES):
                key = (ci, ri, n_val)
                td = datasets.get(key)
                if td is None or td.true_x095 == 0: continue
                d_arr = d_seed_dict.get(key, np.array([np.nan]))
                p_arr = p_seed_dict.get(key, np.array([np.nan]))
                if len(d_arr) == 0 or len(p_arr) == 0: continue
                # Apply the SAME seed multiset to all rows
                d_mean = float(np.nanmean(d_arr[d_seed_idx[:len(d_arr)]]))
                p_mean = float(np.nanmean(p_arr[p_seed_idx[:len(p_arr)]]))
                if np.isfinite(d_mean):
                    d_errs_n.append((d_mean - td.true_x095) / td.true_x095)
                if np.isfinite(p_mean):
                    p_errs_n.append((p_mean - td.true_x095) / td.true_x095)
        dr_n = float(np.sqrt(np.mean(np.array(d_errs_n)**2))) if d_errs_n else np.nan
        pr_n = float(np.sqrt(np.mean(np.array(p_errs_n)**2))) if p_errs_n else np.nan
        if np.isfinite(dr_n) and np.isfinite(pr_n):
            per_n_vals.append((dr_n, pr_n))
    if not per_n_vals: return np.nan
    bd = float(np.mean([v[0] for v in per_n_vals]))
    bp = float(np.mean([v[1] for v in per_n_vals]))
    return (bp - bd) / bp if bp > 0 else np.nan


# -- Main --

def run_b4(output_dir=None):
    if output_dir is None:
        output_dir = str(_EXTERNAL_ROOT / f"B4-core-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}")
    out = Path(output_dir); out.mkdir(parents=True, exist_ok=True)
    code_tip = _git_tip()
    print(f"=== B4 Core Test v4 ===")
    print(f"Output: {out}"); print(f"Code tip: {code_tip}")

    # Config hash
    config = {"n_clusters":_N_CLUSTERS,"n_replicates":_N_REPLICATES,"n_values":_N_VALUES,
              "n_bootstrap":_N_BOOTSTRAP,"seed_test_ns":_SEED_TEST_NS}
    config_sha = hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()

    print("\n[1/5] Loading models ...")
    b3 = json.loads(_B3_MANIFEST_PATH.read_text(encoding="utf-8"))
    b3_sha = hashlib.sha256(_B3_MANIFEST_PATH.read_bytes()).hexdigest()
    models = load_all_models(b3)

    print(f"\n[2/5] Generating test data ...")
    datasets = generate_test_data()

    print(f"\n[3/5] Evaluating routes (per-seed) ...")
    p_seed, d_seed, dctrl_seed = {}, {}, {}
    trad_preds = {n:{} for n in ["MDM","MLE","LRE"]}
    trad_status = {n:{} for n in ["MDM","MLE","LRE"]}
    total = len(datasets); count = 0
    for (ci,ri,n),td in datasets.items():
        p_seed[(ci,ri,n)] = _infer_p_all(models["P"], n, td.sample)
        d_seed[(ci,ri,n)] = _infer_d_all(models["D"], n, td.sample)
        dctrl_seed[(ci,ri,n)] = _infer_d_all(models["Dctrl"], n, td.sample)
        for mid,kw,lbl in [("mdm",{"offset":0.1},"MDM"),("mle",{},"MLE"),("lre",{},"LRE")]:
            pv,st = _infer_trad(mid,kw,td.sample,td.beta,td.eta,td.gamma)
            trad_preds[lbl][(ci,ri,n)] = pv; trad_status[lbl][(ci,ri,n)] = st
        count+=1
        if count%1000==0: print(f"  {count}/{total}")

    # Save per-seed predictions artifact
    print("\n[3b] Saving per-seed predictions ...")
    seed_keys = sorted(p_seed.keys())
    p_arr = np.array([p_seed[k] for k in seed_keys], dtype=object)
    d_arr = np.array([d_seed[k] for k in seed_keys], dtype=object)
    dc_arr = np.array([dctrl_seed[k] for k in seed_keys], dtype=object)
    seed_path = out / "per_seed_predictions.npz"
    np.savez_compressed(seed_path,
                        keys=np.array([f"{c}_{r}_{n}" for c,r,n in seed_keys]),
                        p_seeds=np.array([np.pad(v,(0,10-len(v)),constant_values=np.nan) for v in p_arr],dtype=np.float32),
                        d_seeds=np.array([np.pad(v,(0,10-len(v)),constant_values=np.nan) for v in d_arr],dtype=np.float32),
                        dctrl_seeds=np.array([np.pad(v,(0,5-len(v)),constant_values=np.nan) for v in dc_arr],dtype=np.float32))
    seed_sha = hashlib.sha256(seed_path.read_bytes()).hexdigest()
    print(f"  Saved: {seed_path} (SHA256: {seed_sha[:16]}...)")

    # Ensemble-mean relative errors
    def _em(d,k): return float(np.nanmean(d[k]))
    route_names = ["P","D","Dctrl","MDM","MLE","LRE"]
    route_errs = {n:{} for n in route_names}
    for (ci,ri,n),td in datasets.items():
        route_errs["P"][(ci,ri,n)] = (_em(p_seed,(ci,ri,n))-td.true_x095)/td.true_x095
        route_errs["D"][(ci,ri,n)] = (_em(d_seed,(ci,ri,n))-td.true_x095)/td.true_x095
        route_errs["Dctrl"][(ci,ri,n)] = (_em(dctrl_seed,(ci,ri,n))-td.true_x095)/td.true_x095
        for lbl in ["MDM","MLE","LRE"]:
            pv=trad_preds[lbl].get((ci,ri,n),np.nan)
            route_errs[lbl][(ci,ri,n)] = (pv-td.true_x095)/td.true_x095 if np.isfinite(pv) else np.nan

    # CSV
    csv_path = out / "results.csv"
    with open(csv_path,"w",newline="",encoding="utf-8") as f:
        cols=["cluster","replicate","n","beta","eta","gamma","true_x095"]
        for lbl in route_names: cols.extend([f"{lbl}_mean",f"{lbl}_rel_err"])
        w=csv.DictWriter(f,fieldnames=cols); w.writeheader()
        for (ci,ri,n),td in datasets.items():
            row={"cluster":ci,"replicate":ri,"n":n,"beta":td.beta,"eta":td.eta,"gamma":td.gamma,"true_x095":td.true_x095}
            row["P_mean"]=_em(p_seed,(ci,ri,n)); row["P_rel_err"]=route_errs["P"].get((ci,ri,n),np.nan)
            row["D_mean"]=_em(d_seed,(ci,ri,n)); row["D_rel_err"]=route_errs["D"].get((ci,ri,n),np.nan)
            row["Dctrl_mean"]=_em(dctrl_seed,(ci,ri,n)); row["Dctrl_rel_err"]=route_errs["Dctrl"].get((ci,ri,n),np.nan)
            for lbl in ["MDM","MLE","LRE"]:
                row[f"{lbl}_mean"]=trad_preds[lbl].get((ci,ri,n),np.nan)
                row[f"{lbl}_rel_err"]=route_errs[lbl].get((ci,ri,n),np.nan)
            w.writerow(row)
    csv_sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()

    # Per-route summaries
    print("\n[4/5] Computing metrics ...")
    summaries = {}
    for lbl in route_names:
        errs=[v for v in route_errs[lbl].values() if np.isfinite(v)]
        nf=sum(1 for v in route_errs[lbl].values() if not np.isfinite(v))
        s=summarize_standard_errors(errs); s["n_failure"]=nf; summaries[lbl]=s
        print(f"  {lbl}: n={s.get('n',0)} rmse={s.get('rmse',np.nan):.6f} failures={nf}")

    # Per-n detail
    per_n = {}
    for lbl in route_names:
        per_n[lbl] = {}
        for nv in _N_VALUES:
            errs=[route_errs[lbl].get((ci,ri,nv),np.nan) for ci in range(_N_CLUSTERS) for ri in range(_N_REPLICATES)]
            valid=[e for e in errs if np.isfinite(e)]
            s=summarize_standard_errors(valid); s["n_failure"]=len(errs)-len(valid)
            per_n[lbl][str(nv)]=s

    # --- Hierarchical bootstrap D vs P ---
    print(f"\n[5/5] Bootstrap ({_N_BOOTSTRAP} reps) ...")
    rng = np.random.default_rng(42)

    # Point estimate: equal 5-n weight, per-row relative errors
    point_per_n = {}
    for nv in _N_VALUES:
        de=[route_errs["D"].get((ci,ri,nv),np.nan) for ci in range(_N_CLUSTERS) for ri in range(_N_REPLICATES)]
        pe=[route_errs["P"].get((ci,ri,nv),np.nan) for ci in range(_N_CLUSTERS) for ri in range(_N_REPLICATES)]
        dv=[e for e in de if np.isfinite(e)]; pv=[e for e in pe if np.isfinite(e)]
        point_per_n[nv]={"d_rmse":float(np.sqrt(np.mean(np.array(dv)**2))),"p_rmse":float(np.sqrt(np.mean(np.array(pv)**2)))}
    pooled_d = float(np.mean([point_per_n[n]["d_rmse"] for n in _N_VALUES]))
    pooled_p = float(np.mean([point_per_n[n]["p_rmse"] for n in _N_VALUES]))
    point_i = (pooled_p - pooled_d)/pooled_p if pooled_p>0 else 0.0

    # D vs P bootstrap
    boot_i = []
    for b in range(_N_BOOTSTRAP):
        val = _hierarchical_bootstrap_d_vs_p(route_errs["D"],route_errs["P"],datasets,d_seed,p_seed,rng)
        if np.isfinite(val): boot_i.append(val)
    boot_i = np.array(boot_i)
    ci_lo_pd = float(np.percentile(boot_i,2.5)); ci_hi_pd = float(np.percentile(boot_i,97.5))

    verdict = "no confirmed difference"
    if ci_lo_pd>0 and point_i>=0.05: verdict="supported and material"
    elif ci_lo_pd>0 and point_i<0.05: verdict="supported but small"
    elif ci_hi_pd<0: verdict="parameter route better"

    print(f"  Pooled: P={pooled_p:.6f} D={pooled_d:.6f}")
    print(f"  I = {point_i:.4f} [{ci_lo_pd:.4f}, {ci_hi_pd:.4f}]")
    print(f"  Verdict: {verdict}")

    # --- D vs traditional: paired cluster bootstrap on shared valid rows ---
    # Pre-compute per-cluster paired errors for D-vs-traditional
    d_vs_trad = {}
    for lbl in ["MDM","MLE","LRE"]:
        # Build per-cluster lists of paired errors (shared valid rows only)
        cluster_d_errs = {ci:[] for ci in range(_N_CLUSTERS)}
        cluster_t_errs = {ci:[] for ci in range(_N_CLUSTERS)}
        for (ci,ri,n),td in datasets.items():
            de = route_errs["D"].get((ci,ri,n),np.nan)
            te = route_errs[lbl].get((ci,ri,n),np.nan)
            if np.isfinite(de) and np.isfinite(te):
                cluster_d_errs[ci].append(de)
                cluster_t_errs[ci].append(te)

        n_shared = sum(len(v) for v in cluster_d_errs.values())
        all_de = [e for v in cluster_d_errs.values() for e in v]
        all_te = [e for v in cluster_t_errs.values() for e in v]
        d_rmse_point = float(np.sqrt(np.mean(np.array(all_de)**2))) if all_de else np.nan
        t_rmse_point = float(np.sqrt(np.mean(np.array(all_te)**2))) if all_te else np.nan

        # Bootstrap CI for D - Trad RMSE difference
        boot_diff = []
        ci_all = list(range(_N_CLUSTERS))
        for b in range(_N_BOOTSTRAP):
            ci_b = list(rng.choice(ci_all, size=_N_CLUSTERS, replace=True))
            de_b = [e for ci in ci_b for e in cluster_d_errs[ci]]
            te_b = [e for ci in ci_b for e in cluster_t_errs[ci]]
            dr_b = np.sqrt(np.mean(np.array(de_b)**2)) if de_b else np.nan
            tr_b = np.sqrt(np.mean(np.array(te_b)**2)) if te_b else np.nan
            if np.isfinite(dr_b) and np.isfinite(tr_b):
                boot_diff.append(dr_b - tr_b)
        boot_diff = np.array(boot_diff)
        trad_ci_lo = float(np.percentile(boot_diff,2.5))
        trad_ci_hi = float(np.percentile(boot_diff,97.5))

        d_vs_trad[lbl] = {
            "n_shared": n_shared,
            "d_rmse": d_rmse_point, "t_rmse": t_rmse_point,
            "d_minus_t_rmse": d_rmse_point - t_rmse_point,
            "ci_95_lower": trad_ci_lo, "ci_95_upper": trad_ci_hi,
            "d_better": trad_ci_hi < 0,
            "t_better": trad_ci_lo > 0,
        }
        direction = "D better" if d_vs_trad[lbl]["d_better"] else ("Trad better" if d_vs_trad[lbl]["t_better"] else "no confirmed difference")
        print(f"  {lbl}: shared={n_shared} D_rmse={d_rmse_point:.4f} T_rmse={t_rmse_point:.4f} diff={d_rmse_point-t_rmse_point:.4f} [{trad_ci_lo:.4f},{trad_ci_hi:.4f}] → {direction}")

    # --- Per-n heterogeneity ---
    per_n_boot = {}
    # Simple per-n CI: bootstrap cluster resampling within each n
    for nv in _N_VALUES:
        cluster_d = {ci:[] for ci in range(_N_CLUSTERS)}
        cluster_p = {ci:[] for ci in range(_N_CLUSTERS)}
        for ci in range(_N_CLUSTERS):
            for ri in range(_N_REPLICATES):
                de = route_errs["D"].get((ci,ri,nv),np.nan)
                pe = route_errs["P"].get((ci,ri,nv),np.nan)
                if np.isfinite(de): cluster_d[ci].append(de)
                if np.isfinite(pe): cluster_p[ci].append(pe)
        boot_n = []
        for b in range(_N_BOOTSTRAP):
            ci_b = list(rng.choice(range(_N_CLUSTERS),size=_N_CLUSTERS,replace=True))
            de_b = [e for ci in ci_b for e in cluster_d[ci]]
            pe_b = [e for ci in ci_b for e in cluster_p[ci]]
            dr = np.sqrt(np.mean(np.array(de_b)**2)) if de_b else np.nan
            pr = np.sqrt(np.mean(np.array(pe_b)**2)) if pe_b else np.nan
            if np.isfinite(dr) and np.isfinite(pr) and pr>0:
                boot_n.append((pr-dr)/pr)
        boot_n = np.array(boot_n)
        per_n_boot[str(nv)] = {
            "d_rmse": point_per_n[nv]["d_rmse"], "p_rmse": point_per_n[nv]["p_rmse"],
            "I": (point_per_n[nv]["p_rmse"]-point_per_n[nv]["d_rmse"])/point_per_n[nv]["p_rmse"] if point_per_n[nv]["p_rmse"]>0 else 0,
            "ci_lo": float(np.percentile(boot_n,2.5)), "ci_hi": float(np.percentile(boot_n,97.5)),
        }

    # Manifest
    manifest = {
        "version":"4.0","run_id":out.name,
        "generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "status":"complete","code_tip":code_tip,
        "config_sha256":config_sha,"b3_manifest_sha256":b3_sha,
        "environment":{"python_version":sys.version,"platform":sys.platform},
        "design":config,
        "primary":{"improvement_I":point_i,"ci_95_lower":ci_lo_pd,"ci_95_upper":ci_hi_pd,
                   "pooled_rmse_P":pooled_p,"pooled_rmse_D":pooled_d,"verdict":verdict},
        "per_n":per_n_boot,
        "per_route":summaries,
        "per_n_detail":per_n,
        "d_vs_traditional":d_vs_trad,
        "outputs":{
            "results.csv":{"path":str(csv_path),"sha256":csv_sha,"rows":len(datasets)},
            "per_seed_predictions.npz":{"path":str(seed_path),"sha256":seed_sha},
        },
    }
    mf_path = out / "manifest.json"
    mf_path.write_text(json.dumps(manifest,indent=2,ensure_ascii=False),encoding="utf-8")
    mf_sha = hashlib.sha256(mf_path.read_bytes()).hexdigest()
    print(f"\n  Manifest: {mf_path}\n  SHA256: {mf_sha}")
    print(f"\n=== B4 v4 complete ===")
    return manifest


if __name__=="__main__": run_b4()
