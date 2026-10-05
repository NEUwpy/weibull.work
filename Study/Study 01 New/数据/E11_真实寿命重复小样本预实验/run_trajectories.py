"""Real-data parameter trajectories; no consensus target is assumed.

500 shared subsets per n<=80, exact 101 leave-one-out subsets at n=100,
one full-data fit at n=101. Frozen AMDM is available only at supported n.
"""
from pathlib import Path
import os
for key in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[key]='1'
import sys,json,hashlib,time
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
from run_pilot import fit,MODELDIR

HERE=Path(__file__).resolve().parent
OUT=HERE/'参数轨迹'
E10=HERE.parent/'E10_样本量扩展'
sys.path.insert(0,str(E10))
from run_e10 import CachedMDM,predict_curve,DELTAS
NS=[7,10,15,20,30,50,80,100,101]
METHODS=['AMDM','MDM-0.1','WMLE','MLE','LSE','LRE']
MODEL_PATHS={n:(MODELDIR if n<=20 else E10/'models')/f'n{n}_final.json' for n in [7,10,15,20,30,50,100]}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p,v): p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

def make_ids(n):
    if n==101:return np.arange(101)[None,:]
    if n==100:return np.array([np.delete(np.arange(101),i) for i in range(101)])
    rng=np.random.default_rng(np.random.SeedSequence([20260925,n]))
    return np.array([np.sort(rng.choice(101,n,replace=False)) for _ in range(500)])

def run_batch(task):
    n,start,stop=task
    path=OUT/'chunks'/f'n{n}_{start:04d}.csv.gz'
    if path.exists():return str(path)
    with np.load(OUT/f'n{n}_samples.npz') as z:xs=z['x'][start:stop]
    reuse=pd.read_csv(OUT/'reused_rows.csv.gz')
    reuse=reuse[reuse.n==n].set_index(['repeat','method'])
    model=json.loads(MODEL_PATHS[n].read_text(encoding='utf8')) if n in MODEL_PATHS else None
    rows=[]
    for rep,x in enumerate(xs,start):
        solver=None
        for method in METHODS:
            if method=='AMDM' and model is None:continue
            if (rep,method) in reuse.index:
                row=reuse.loc[(rep,method)].to_dict();row.update(repeat=rep,method=method)
                rows.append(row);continue
            begin=time.perf_counter()
            try:
                if method in ['AMDM','MDM-0.1']:
                    delta=float(DELTAS[np.argmin(predict_curve(x,model))]) if method=='AMDM' else .1
                    if solver is None:solver=CachedMDM(x)
                    pars,strategy=solver.fit(delta)
                    valid=bool(np.isfinite(pars).all() and pars[0]>0 and pars[1]>0 and 0<=pars[2]<min(x))
                    failure='' if valid else 'invalid_parameter'
                else:
                    pars,valid,delta,failure=fit(x,method)
                rows.append(dict(n=n,repeat=rep,method=method,delta=delta,valid=valid,beta_hat=pars[0],eta_hat=pars[1],gamma_hat=pars[2],failure=failure,source='new_frozen_fit',runtime_seconds=time.perf_counter()-begin))
            except Exception as ex:
                rows.append(dict(n=n,repeat=rep,method=method,valid=False,failure=repr(ex),source='new_frozen_fit',runtime_seconds=time.perf_counter()-begin))
    pd.DataFrame(rows).to_csv(path,index=False,compression='gzip')
    return str(path)

def summarize(df):
    rows=[];coverage=[];common_rows=[]
    for n,g in df.groupby('n'):
        active=[m for m in METHODS if m!='AMDM' or n in MODEL_PATHS]
        pivot=g.pivot(index='repeat',columns='method',values='valid')
        joint=pivot[active].fillna(False).all(axis=1)
        for method in active:
            v=g[(g.method==method)&g.valid]
            coverage.append(dict(n=n,method=method,attempted=len(pivot),valid=len(v),failed=len(pivot)-len(v),common_valid=int(joint.sum())))
            for param in ['beta','eta','gamma']:
                a=v[param+'_hat'].to_numpy()
                row=dict(n=n,method=method,parameter=param,count=len(a),mean=np.mean(a),median=np.median(a),sd=np.std(a,ddof=1) if len(a)>1 else np.nan,min=np.min(a),max=np.max(a))
                row.update({f'q{int(q*1000):03d}':np.quantile(a,q) for q in [.025,.25,.75,.975]})
                rows.append(row)
                c=v[v.repeat.isin(joint[joint].index)][param+'_hat'].to_numpy()
                common_rows.append(dict(n=n,method=method,parameter=param,count=len(c),mean=np.mean(c),median=np.median(c)))
    pd.DataFrame(rows).to_csv(OUT/'trajectory_summary.csv',index=False)
    pd.DataFrame(coverage).to_csv(OUT/'fit_coverage.csv',index=False)
    pd.DataFrame(common_rows).to_csv(OUT/'common_valid_summary.csv',index=False)
    df[df.n==101].to_csv(OUT/'full101_estimates.csv',index=False)

def main():
    OUT.mkdir(exist_ok=True);(OUT/'chunks').mkdir(exist_ok=True)
    ref=pd.read_csv(HERE/'observations.csv').life_thousand_cycles.to_numpy()
    sources=[HERE/'observations.csv',HERE/'per_subsample.csv',HERE/'扩展诊断/per_sample.csv.gz',HERE/'run_pilot.py',E10/'run_e10.py',HERE.parent/'E09_六方法共同测试/wmle_solver.py',Path(__file__)]+list(MODEL_PATHS.values())
    repo=HERE.parents[3]
    sources += [repo/'python/methods'/f'{m}.py' for m in ['mdm','mle','wmle','lse','lre']]
    hashes={str(p):sha(p) for p in sources}
    protocol=dict(ns=NS,methods=METHODS,amdm_supported_n=list(MODEL_PATHS),repeats='500 per n<=80; all 101 distinct leave-one-out subsets at n=100; full sample once at n=101',seed='SeedSequence([20260925,n])',sampling='Shared subsets across methods; independently drawn across n; trajectories summarize repeated subsets, not a single nested sample path',center='median of valid fits; mean and common-valid checks also saved',band='interquartile range; detailed panels additionally show 2.5-97.5 percentiles; conditional subsample spread, not confidence interval',full101='One finite data set; no within-subset band. Not known truth, not a convergence proof',amdm_note='Frozen n-specific models; n80 and n101 unsupported, no retraining or interpolation of model weights',source_hashes=hashes)
    if (OUT/'protocol.json').exists():assert json.loads((OUT/'protocol.json').read_text(encoding='utf8'))==protocol,'Source hashes changed'
    else:write_json(OUT/'protocol.json',protocol)
    diag=pd.read_csv(HERE/'扩展诊断/per_sample.csv.gz').query("regime=='real_without_replacement' and repeat<500").copy();diag['source']='E11_expanded_first500'
    old=pd.read_csv(HERE/'per_subsample.csv').query("method not in ['AMDM','MDM-0.1']").copy();old['source']='E11_initial100'
    columns=['n','repeat','method','delta','valid','beta_hat','eta_hat','gamma_hat','source']
    reuse=pd.concat([diag[columns],old[columns]],ignore_index=True)
    assert len(reuse)==5600
    reuse.to_csv(OUT/'reused_rows.csv.gz',index=False,compression='gzip')
    for n in NS:
        ids=make_ids(n);x=np.sort(ref[ids],axis=1)
        if n<=20:
            with np.load(HERE/f'扩展诊断/real_without_replacement_n{n}_samples.npz') as z:assert np.array_equal(x,z['x'][:500])
        np.savez_compressed(OUT/f'n{n}_samples.npz',x=x,observation_ids=ids)
    tasks=[(n,start,min(start+25,len(make_ids(n)))) for n in NS for start in range(0,len(make_ids(n)),25)]
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(run_batch,t) for t in tasks]
        for i,f in enumerate(as_completed(jobs),1):
            f.result()
            if i%10==0:print(f'{i}/{len(tasks)} batches finished',flush=True)
    df=pd.concat([pd.read_csv(p) for p in (OUT/'chunks').glob('*.csv.gz')],ignore_index=True).sort_values(['n','repeat','method'])
    expected=sum(len(make_ids(n))*(6 if n in MODEL_PATHS else 5) for n in NS)
    assert len(df)==expected and not df.duplicated(['n','repeat','method']).any()
    df.to_csv(OUT/'per_subsample.csv.gz',index=False,compression='gzip')
    summarize(df)
    verify=[]
    for n in [30,50,100]:
        x=np.sort(ref[make_ids(n)[0]])
        model=json.loads(MODEL_PATHS[n].read_text(encoding='utf8'))
        delta=float(DELTAS[np.argmin(predict_curve(x,model))])
        from studies.common.runner import run_method
        for d in [.1,delta]:
            production=run_method('mdm',x,offset=d,gamma_steps=60)
            a=np.array([production[k] for k in ['beta_hat','eta_hat','gamma_hat']]);b,_=CachedMDM(x).fit(d)
            assert np.allclose(a,b,rtol=1e-8,atol=1e-6)
            verify.append(dict(n=n,delta=d,max_abs=float(abs(a-b).max())))
    assert all(sha(p)==h for p,h in hashes.items())
    write_json(OUT/'verification.json',dict(rows=len(df),reused_rows=len(reuse),source_hashes_unchanged=True,small_n_samples_match_expanded=True,cached_production_checks=verify,models_retrained=False))
    print(df[df.n==101][['method','valid','beta_hat','eta_hat','gamma_hat']].to_string(index=False),flush=True)

if __name__=='__main__':main()
