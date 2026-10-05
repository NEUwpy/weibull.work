"""Fixed-count diagnostic: real subsampling versus matched Weibull simulation.

No retraining or selector changes. Original 100-repeat pilot is preserved.
Run directly; outputs live in 扩展诊断. Checkpoints are input-hash guarded.
"""
from pathlib import Path
import os
for k in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[k] = '1'
import sys, json, hashlib
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
from scipy.special import gamma as gamma_fn, gammainc

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'E10_样本量扩展'))
from run_e10 import CachedMDM, predict_curve, DELTAS
from run_pilot import fit, cdf, choose_delta, MODELDIR
OUT = HERE / '扩展诊断'
NS = [7, 10, 15, 20]
REGIMES = ['real_without_replacement', 'matched_weibull', 'real_with_replacement']
REPEATS = 2000
BOOT = 2000
SCAN = 100

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write_json(p, v): p.write_text(json.dumps(v, ensure_ascii=False, indent=2)+'\n', encoding='utf8')

def inputs():
    values = pd.read_csv(HERE/'observations.csv').life_thousand_cycles.to_numpy()
    theta = pd.read_csv(HERE/'reference_fits.csv')[['beta_hat','eta_hat','gamma_hat']].iloc[0].to_numpy(float)
    return values, theta

def make_samples(regime, n):
    values, theta = inputs()
    seed = [20260925, n] if regime == REGIMES[0] else [20260925, n, REGIMES.index(regime)]
    rng = np.random.default_rng(np.random.SeedSequence(seed))
    if regime == 'matched_weibull':
        x = theta[2]+theta[1]*rng.weibull(theta[0], (REPEATS,n))
        ids = np.full((REPEATS,n), -1, dtype=int)
    else:
        ids = np.array([np.sort(rng.choice(len(values), n, replace=regime==REGIMES[2])) for _ in range(REPEATS)])
        x = values[ids]
    return np.sort(x, axis=1), ids

def measurements(pars, ref, theta, grid, ecdf, truecdf):
    pred = cdf(grid, pars)
    b,e,g = pars
    z = np.maximum((ref-g)/e,0)**b
    F = -np.expm1(-z)
    crps = (ref-g)*(2*F-1)-2*e*gamma_fn(1+1/b)*gammainc(1+1/b,z)+e*gamma_fn(1+1/b)*2**(-1/b)
    err = (pars-theta)/[theta[0],theta[1],theta[1]]
    return dict(param_loss=float(np.sum(err**2)), beta_loss=err[0]**2, eta_loss=err[1]**2,
                gamma_loss=err[2]**2, cdf_empirical=np.trapezoid((pred-ecdf)**2,grid)/grid[-1],
                cdf_fitted=np.trapezoid((pred-truecdf)**2,grid)/grid[-1],
                crps_iqr=float(np.mean(crps)/(np.quantile(ref,.75)-np.quantile(ref,.25))))

def worker(task):
    regime,n,start,stop = task
    destination = OUT/'chunks'/f'{regime}_n{n}_{start:04d}.csv.gz'
    scan_path = OUT/'chunks'/f'{regime}_n{n}_{start:04d}_scan.csv.gz'
    if destination.exists(): return str(destination)
    ref,theta = inputs()
    with np.load(OUT/f'{regime}_n{n}_samples.npz') as data: xs=data['x'][start:stop]
    model=json.loads((MODELDIR/f'n{n}_final.json').read_text(encoding='utf8'))
    grid=np.linspace(0,max(ref),4001)
    ecdf=np.searchsorted(np.sort(ref),grid,side='right')/len(ref)
    truecdf=cdf(grid,theta)
    records=[];scans=[]
    for rep,x in enumerate(xs,start):
        curve=predict_curve(x,model);delta=float(DELTAS[np.argmin(curve)])
        solver=CachedMDM(x)
        z=(x/x.mean()-model['input_scaler_mean'])/model['input_scaler_std']
        common=dict(regime=regime,n=n,repeat=rep,feature_z_rms=float(np.sqrt(np.mean(z*z))))
        for method,d in [('AMDM',delta),('MDM-0.1',.1)]:
            try:
                pars,strategy=solver.fit(d)
                valid=bool(np.isfinite(pars).all() and pars[0]>0 and pars[1]>0 and 0<=pars[2]<min(x))
                scores=measurements(pars,ref,theta,grid,ecdf,truecdf) if valid else {}
                records.append(dict(**common,method=method,delta=d,valid=valid,beta_hat=pars[0],eta_hat=pars[1],gamma_hat=pars[2],strategy=strategy,**scores))
            except Exception as ex:
                records.append(dict(**common,method=method,delta=d,valid=False,failure=repr(ex)))
        if rep<SCAN and regime!=REGIMES[2]:
            for d in DELTAS:
                try:
                    pars,strategy=solver.fit(d)
                    scores=measurements(pars,ref,theta,grid,ecdf,truecdf)
                    scans.append(dict(**common,delta=float(d),**scores))
                except Exception as ex:
                    scans.append(dict(**common,delta=float(d),failure=repr(ex)))
    if scans: pd.DataFrame(scans).to_csv(scan_path,index=False,compression='gzip')
    pd.DataFrame(records).to_csv(destination,index=False,compression='gzip')
    return str(destination)

def verify_implementation():
    checks=[]
    for n in NS:
        x,_=make_samples(REGIMES[0],n)
        for rep in [0,17,53,99]:
            solver=CachedMDM(x[rep]);delta=choose_delta(x[rep],n)
            model=json.loads((MODELDIR/f'n{n}_final.json').read_text(encoding='utf8'))
            assert np.isclose(delta,DELTAS[np.argmin(predict_curve(x[rep],model))],rtol=0,atol=1e-15)
            for method,d in [('AMDM',delta),('MDM-0.1',.1)]:
                a,_=solver.fit(d);b,valid,_,_=fit(x[rep],method)
                assert valid and np.allclose(a,b,rtol=1e-8,atol=1e-6), (n,rep,a,b)
                checks.append(dict(n=n,repeat=rep,method=method,max_abs=float(np.max(np.abs(a-b)))))
    return checks

def summarize(df):
    rows=[];behavior=[]
    metrics=['param_loss','beta_loss','eta_loss','gamma_loss','cdf_empirical','cdf_fitted','crps_iqr']
    for (regime,n),g in df.groupby(['regime','n']):
        a=g[g.method=='AMDM'].set_index('repeat').sort_index()
        b=g[g.method=='MDM-0.1'].set_index('repeat').sort_index()
        good=a.valid & b.valid
        for metric in metrics:
            av=a.loc[good,metric].to_numpy();bv=b.loc[good,metric].to_numpy()
            power=.5 if metric.endswith('_loss') else 1.
            gain=100*(1-(av.mean()/bv.mean())**power)
            rng=np.random.default_rng(20260926)
            boot=[]
            for _ in range(BOOT//100):
                ix=rng.integers(0,len(av),(100,len(av)))
                boot.extend(100*(1-(av[ix].mean(1)/bv[ix].mean(1))**power))
            lo,hi=np.quantile(boot,[.025,.975])
            rows.append(dict(regime=regime,n=n,metric=metric,paired_valid=len(av),amdm=av.mean()**power,mdm=bv.mean()**power,gain_percent=gain,lo95=lo,hi95=hi,win_fraction=float(np.mean(av<bv))))
        behavior.append(dict(regime=regime,n=n,amdm_failures=int((~a.valid).sum()),mdm_failures=int((~b.valid).sum()),delta_mean=a.delta.mean(),delta_median=a.delta.median(),delta_q10=a.delta.quantile(.1),delta_q90=a.delta.quantile(.9),delta_at_01=np.isclose(a.delta,.1).mean(),amdm_gamma_zero=(a.gamma_hat==0).mean(),mdm_gamma_zero=(b.gamma_hat==0).mean(),feature_z_rms=a.feature_z_rms.mean()))
    pd.DataFrame(rows).to_csv(OUT/'paired_comparison.csv',index=False)
    pd.DataFrame(behavior).to_csv(OUT/'selector_behavior.csv',index=False)
    scan_files=list((OUT/'chunks').glob('*_scan.csv.gz'))
    scan=pd.concat([pd.read_csv(p) for p in scan_files],ignore_index=True)
    scan.to_csv(OUT/'candidate_scan.csv.gz',index=False,compression='gzip')
    oracle=[]
    for (regime,n,rep),g in scan.groupby(['regime','n','repeat']):
        base=g[np.isclose(g.delta,.1)].iloc[0]
        for metric in ['param_loss','cdf_empirical','cdf_fitted']:
            j=g[metric].idxmin();best=g.loc[j]
            oracle.append(dict(regime=regime,n=n,repeat=rep,metric=metric,best_delta=best.delta,best_loss=best[metric],fixed_loss=base[metric]))
    pd.DataFrame(oracle).to_csv(OUT/'oracle_diagnostic.csv',index=False)
    print(pd.DataFrame(rows).query("metric in ['param_loss','cdf_empirical','cdf_fitted']").to_string(index=False),flush=True)

def main():
    OUT.mkdir(exist_ok=True);(OUT/'chunks').mkdir(exist_ok=True)
    source_files=[HERE/'observations.csv',HERE/'reference_fits.csv',HERE/'per_subsample.csv',HERE/'subsample_ids.csv',HERE/'run_pilot.py',HERE.parent/'E10_样本量扩展/run_e10.py']+[MODELDIR/f'n{n}_final.json' for n in NS]
    source_files.append(Path(__file__))
    hashes={str(p):sha(p) for p in source_files}
    protocol=dict(repeats=REPEATS,ns=NS,regimes=REGIMES,bootstrap=BOOT,candidate_scan_first=SCAN,models='Frozen E09; no retuning',parameter_reference='Full101 MLE proxy for real samples; known generating truth only for matched simulation',interval='Paired Monte Carlo bootstrap, conditional on fixed model and finite real pool or fixed simulation parameters; not uncertainty across new datasets',hashes=hashes)
    if (OUT/'protocol.json').exists():
        assert json.loads((OUT/'protocol.json').read_text(encoding='utf8'))==protocol,'Inputs changed: do not reuse checkpoints'
    else: write_json(OUT/'protocol.json',protocol)
    oldids=pd.read_csv(HERE/'subsample_ids.csv')
    for regime in REGIMES:
        for n in NS:
            x,ids=make_samples(regime,n)
            if regime==REGIMES[0]:
                assert np.array_equal(ids[:100],oldids[oldids.n==n].observation_id.to_numpy().reshape(100,n))
            np.savez_compressed(OUT/f'{regime}_n{n}_samples.npz',x=x,observation_ids=ids)
    checks=verify_implementation()
    print('32 production/cached fits and selector checks passed; original 100 sample IDs preserved.',flush=True)
    tasks=[(r,n,start,min(start+100,REPEATS)) for r in REGIMES for n in NS for start in range(0,REPEATS,100)]
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(worker,t) for t in tasks]
        for i,f in enumerate(as_completed(jobs),1):
            f.result()
            if i%10==0: print(f'{i}/{len(tasks)} batches complete',flush=True)
    files=[p for p in (OUT/'chunks').glob('*.csv.gz') if not p.name.endswith('_scan.csv.gz')]
    df=pd.concat([pd.read_csv(p) for p in files],ignore_index=True).sort_values(['regime','n','repeat','method'])
    assert len(df)==len(REGIMES)*len(NS)*REPEATS*2 and not df.duplicated(['regime','n','repeat','method']).any()
    df.to_csv(OUT/'per_sample.csv.gz',index=False,compression='gzip')
    old=pd.read_csv(HERE/'per_subsample.csv').query("method in ['AMDM','MDM-0.1']")
    new=df.query("regime=='real_without_replacement' and repeat<100")
    joined=old.merge(new,on=['n','repeat','method'],suffixes=('_old','_new'))
    differences={k:float(np.max(np.abs(joined[k+'_old']-joined[k+'_new']))) for k in ['beta_hat','eta_hat','gamma_hat','delta']}
    assert len(joined)==800
    for k in differences: assert np.allclose(joined[k+'_old'],joined[k+'_new'],rtol=1e-8,atol=1e-6), (k,differences[k])
    assert all(sha(p)==h for p,h in hashes.items())
    write_json(OUT/'verification.json',dict(production_checks=checks,original100_max_abs=differences,rows=len(df),source_hashes_unchanged=True,original100_ids_preserved=True))
    summarize(df)

if __name__=='__main__': main()
