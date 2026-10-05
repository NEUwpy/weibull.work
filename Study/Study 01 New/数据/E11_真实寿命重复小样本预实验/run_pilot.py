"""Frozen-model real-data pilot; choose protocol before inspecting outcomes.

NIST BIRNSAUN: 101 complete fatigue lives, thousand cycles, 6061-T6.
All 101 observations are reference and sampling pool, 100 subsets per n.
Repeated subsets quantify conditional subsampling variation, not new specimens.
"""
from pathlib import Path
import os
for name in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[name]='1'
import sys, json, hashlib, re, urllib.request, time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
from scipy.special import gamma as gamma_function, gammainc

HERE=Path(__file__).resolve().parent
STUDY=HERE.parents[1]
REPO=STUDY.parents[1]
sys.path.insert(0,str(REPO/'python'))
sys.path.insert(0,str(HERE.parent/'E09_六方法共同测试'))
from studies.common.runner import run_method
from wmle_solver import run_wmle_checked

NS=[7,10,15,20]
METHODS=['AMDM','MDM-0.1','WMLE','MLE','LSE','LRE']
SEED=20260925
REPEATS=100
URL='https://www.itl.nist.gov/div898/handbook/datasets/BIRNSAUN.DAT'
MODELDIR=HERE.parent/'E09_六方法共同测试/models'

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def prepare():
    raw=HERE/'BIRNSAUN_transcribed.txt'
    if not raw.exists():
        raw.write_bytes(urllib.request.urlopen(URL,timeout=60).read())
    text=raw.read_text()
    values=np.array([float(line.strip()) for line in text.splitlines() if re.fullmatch(r'\s*\d+(?:\.\d+)?\s*',line)])
    assert len(values)==101 and min(values)==370 and max(values)==2440
    ref_ids=pool_ids=np.arange(len(values))
    roles=np.full(101,'reference_and_pool',dtype=object)
    pd.DataFrame(dict(observation_id=np.arange(101),life_thousand_cycles=values,role=roles)).to_csv(HERE/'observations.csv',index=False)
    records=[]
    for n in NS:
        rng=np.random.default_rng(np.random.SeedSequence([SEED,n]))
        for repeat in range(REPEATS):
            chosen=np.sort(rng.choice(pool_ids,n,replace=False))
            records.extend(dict(n=n,repeat=repeat,observation_id=int(i)) for i in chosen)
    pd.DataFrame(records).to_csv(HERE/'subsample_ids.csv',index=False)
    protocol=dict(status='pilot; not manuscript evidence yet',source_url=URL,
        source_context='https://www.itl.nist.gov/div898/handbook/eda/section4/eda4291.htm',
        source_model_comparison='https://www.itl.nist.gov/div898/handbook/eda/section4/eda4292.htm',
        source_note='NIST considers three-parameter Weibull plausible; its AIC/BIC comparison favors Gaussian. Do not claim known Weibull truth.',
        observations=101,reference=101,pool=101,seed=SEED,repeats=REPEATS,sample_sizes=NS,methods=METHODS,
        split='No split: full 101-observation empirical distribution is the finite-data reference and sampling population, per user instruction',
        sampling='without replacement within each subset; reuse across replicates; same subset for all methods',
        normalization='Original unit is thousand cycles. MDM uses original unit; traditional solvers use life/1000 and outputs are converted back, matching E09 fixed conversion.',
        primary='Normalized integral (F_method-F_reference_ECDF)^2 over [0,max(reference)], numerical trapezoid with 4001 fixed points; lower better.',
        secondary='Mean CRPS on all 101 reference observations (overlap with subsample; not independent prediction), divided by reference IQR; lower better; covers predictive tails.',
        comparisons='AMDM paired with each comparator on jointly valid subsets; failures reported separately; all-six-valid plot for comparable distributions.',
        reference_parameters='MLE fitted to all 101 observations, descriptive reference only, not true parameters; compare reported NIST fit as a numerical check.',
        uncertainty='Quantiles of repeated-subset scores describe variability conditional on this finite pool and reference, not population confidence intervals.',
        source_capture='Numeric lines transcribed in source order from NIST text via web retrieval; direct Python HTTP download returned 403. Hash describes saved transcription, not remote bytes.',source_sha256=sha(raw),models={str(n):sha(MODELDIR/f'n{n}_final.json') for n in NS},
        solver_hashes={name:sha(REPO/'python/methods'/f'{name}.py') for name in ['mdm','mle','lse','lre','wmle']},
        wmle_wrapper_sha256=sha(HERE.parent/'E09_六方法共同测试/wmle_solver.py'))
    write_json(HERE/'protocol.json',protocol)
    return values,ref_ids,pool_ids

def choose_delta(x,n):
    model=json.loads((MODELDIR/f'n{n}_final.json').read_text(encoding='utf8'))
    a=(np.sort(x)/np.mean(x)-model['input_scaler_mean'])/model['input_scaler_std']
    w=model['mlp_weights']
    for i,(coef,intercept) in enumerate(zip(w['coefs_'],w['intercepts_'])):
        a=a@np.asarray(coef)+np.asarray(intercept)
        if i<len(w['coefs_'])-1:a=np.maximum(a,0)
    loss=np.maximum(a*model['target_scaler_std']+model['target_scaler_mean'],0)
    return float(np.arange(26)[np.argmin(loss)]*.02)

def fit(x,method):
    delta=choose_delta(x,len(x)) if method=='AMDM' else (.1 if method=='MDM-0.1' else None)
    if delta is not None:
        out=run_method('mdm',x,offset=delta,gamma_steps=60);scale=1.
    else:
        out=run_wmle_checked(x/1000) if method=='WMLE' else run_method(method.lower(),x/1000)
        scale=1000.
    vals=[out.get(k) for k in ['beta_hat','eta_hat','gamma_hat']]
    valid=bool(out.get('converged')) and all(v is not None and np.isfinite(v) for v in vals)
    if valid:
        vals=np.array(vals)*[1,scale,scale]
        valid=vals[0]>0 and vals[1]>0 and 0<=vals[2]<min(x)
    return vals,bool(valid),delta,str(out.get('extra','')) if not valid else ''

def cdf(t,pars):
    b,e,g=pars
    with np.errstate(over='ignore',invalid='ignore'):
        return -np.expm1(-np.maximum((np.asarray(t)-g)/e,0)**b)

def scores(pars,ref,points=4001):
    grid=np.linspace(0,max(ref),points)
    ecdf=np.searchsorted(np.sort(ref),grid,side='right')/len(ref)
    l2=np.trapezoid((cdf(grid,pars)-ecdf)**2,grid)/max(ref)
    b,e,g=pars;z=np.maximum((ref-g)/e,0)**b;F=-np.expm1(-z)
    crps=(ref-g)*(2*F-1)-2*e*gamma_function(1+1/b)*gammainc(1+1/b,z)+e*gamma_function(1+1/b)*2**(-1/b)
    return float(l2),float(np.mean(crps)/(np.quantile(ref,.75)-np.quantile(ref,.25)))

def worker(task):
    n,repeat,ids,values,ref=task
    x=np.sort(values[ids]);rows=[]
    for method in METHODS:
        start=time.perf_counter();pars,valid,delta,error=fit(x,method)
        l2,crps=scores(pars,ref) if valid else (np.nan,np.nan)
        rows.append(dict(n=n,repeat=repeat,method=method,delta=delta,valid=valid,
            beta_hat=pars[0],eta_hat=pars[1],gamma_hat=pars[2],cdf_l2=l2,crps_iqr=crps,
            runtime_seconds=time.perf_counter()-start,failure=error))
    return rows

def run():
    values,ref_ids,pool_ids=prepare();ref=values[ref_ids]
    references=[]
    for label,ids in [('full101_reference',ref_ids)]:
        pars,valid,_,error=fit(values[ids],'MLE')
        references.append(dict(scope=label,n=len(ids),beta_hat=pars[0],eta_hat=pars[1],gamma_hat=pars[2],valid=valid,error=error))
    pd.DataFrame(references).to_csv(HERE/'reference_fits.csv',index=False)
    ids=pd.read_csv(HERE/'subsample_ids.csv')
    tasks=[(int(n),int(rep),g.observation_id.to_numpy(),values,ref) for (n,rep),g in ids.groupby(['n','repeat'])]
    rows=[]
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(worker,t) for t in tasks]
        for i,f in enumerate(as_completed(jobs),1):
            rows.extend(f.result())
            if i%25==0:
                pd.DataFrame(rows).to_csv(HERE/'in_progress.csv',index=False)
                print(f'{i}/{len(tasks)} subsets finished',flush=True)
    df=pd.DataFrame(rows).sort_values(['n','repeat','method'])
    df.to_csv(HERE/'per_subsample.csv',index=False)
    (HERE/'in_progress.csv').unlink(missing_ok=True)
    summary=[];pairs=[]
    for (n,m),g in df.groupby(['n','method']):
        v=g[g.valid]
        summary.append(dict(n=n,method=m,valid=len(v),failures=len(g)-len(v),
            mean_cdf_l2=v.cdf_l2.mean(),median_cdf_l2=v.cdf_l2.median(),mean_crps_iqr=v.crps_iqr.mean()))
    for n,g in df.groupby('n'):
        am=g[g.method=='AMDM'].set_index('repeat')
        for method in METHODS[1:]:
            base=g[g.method==method].set_index('repeat');keep=am.valid & base.valid
            for metric in ['cdf_l2','crps_iqr']:
                a=am.loc[keep,metric];b=base.loc[keep,metric]
                pairs.append(dict(n=n,comparator=method,metric=metric,paired_valid=int(keep.sum()),
                    amdm_mean=a.mean(),baseline_mean=b.mean(),gain_percent=100*(1-a.mean()/b.mean()),
                    win_fraction=float((a<b).mean())))
    pd.DataFrame(summary).to_csv(HERE/'summary.csv',index=False)
    pd.DataFrame(pairs).to_csv(HERE/'paired_comparison.csv',index=False)
    assert len(df)==2400 and not df.duplicated(['n','repeat','method']).any()
    assert all(set(g.observation_id)<=set(ref_ids) for _,g in ids.groupby(['n','repeat']))
    # Independent numerical CRPS check over a wide integration interval.
    errors=[];quadrature=[]
    for row in df[df.valid].groupby(['n','method']).head(1).itertuples():
        pars=(row.beta_hat,row.eta_hat,row.gamma_hat)
        b,e,g=pars;upper=max(max(ref),g+e*(-np.log(1e-10))**(1/b))
        grid=np.linspace(0,upper,40001);pred=cdf(grid,pars)
        score=np.mean([np.trapezoid((pred-(grid>=y))**2,grid) for y in ref])/(np.quantile(ref,.75)-np.quantile(ref,.25))
        errors.append(abs(score-row.crps_iqr))
        quadrature.append(abs(scores(pars,ref,16001)[0]-row.cdf_l2))
    assert max(errors)<.002 and max(quadrature)<.0001
    write_json(HERE/'verification.json',dict(status='passed',rows=len(df),subsets=len(tasks),
        disjoint_reference=False,reference_and_pool_identical=True,duplicate_subsets=ids.groupby(['n','repeat']).observation_id.apply(lambda s:len(s)!=len(set(s))).sum().item(),
        crps_numerical_check_max_abs=max(errors),cdf_grid_check_max_abs=max(quadrature),
        model_hashes_unchanged=all(sha(MODELDIR/f'n{n}_final.json')==json.loads((HERE/'protocol.json').read_text(encoding='utf8'))['models'][str(n)] for n in NS)))
    print(pd.DataFrame(pairs).query("metric=='cdf_l2'").to_string(index=False),flush=True)

if __name__=='__main__':run()
