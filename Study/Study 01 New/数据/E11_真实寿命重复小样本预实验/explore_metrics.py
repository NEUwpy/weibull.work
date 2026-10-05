"""Bounded exploratory audit of real-data utility and known-truth accuracy.

Metric grid and two literature cases are fixed before scoring. No tuning/retraining.
Observed-data score improvements are distinct from simulated parameter accuracy.
"""
from pathlib import Path
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
import sys,json
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
from scipy.special import gamma as gamma_fn,gammainc
from run_pilot import HERE,REPO,MODELDIR,NS,METHODS,fit,cdf,sha,write_json
sys.path.insert(0,str(HERE.parent/'E10_样本量扩展'))
from run_e10 import CachedMDM,predict_curve,DELTAS
from studies.common.sample import generate_sample

OUT=HERE/'指标与跨案例探索'
PS=np.array([.01,.05,.10,.20,.50,.80,.90,.95,.99])
NEW_REPEATS=1000
SIM_REPEATS=2000
BOOT=2000
CASES={
    'fatigue101':dict(values=pd.read_csv(HERE/'observations.csv').life_thousand_cycles.tolist(),
        unit='thousand cycles',source='NIST BIRNSAUN; existing transcribed source',
        thresholds=[800,1000,1200,1500,1800],ns=NS),
    'rotor20':dict(values=[87,98,110,128,210,244,275,295,303,320,346,465,513,598,661,760,860,891,1080,1290],
        unit='hours',source='182-047, section 4.1, 20 turbine bearing rotor lifetimes',
        thresholds=[100,200,500,800],ns=[7,10]),
    'bearing23':dict(values=[17.88,28.92,33.,41.52,42.12,45.60,48.48,51.84,51.96,54.12,55.56,67.80,68.64,68.64,68.88,84.12,93.12,98.64,105.12,105.84,127.92,128.04,173.40],
        unit='million revolutions',source='182-050, section 5.2, Table 9, 23 ball bearings',
        thresholds=[30,50,80,120],ns=[7,10])}
LIB=Path('D:/博士阶段/100科研文献管理/100科研文献管理/180_AI辅助参数估计/182_传统参数估计方法')


def quantiles(pars):
    a=np.asarray(pars,float)
    return a[:,2,None]+a[:,1,None]*(-np.log1p(-PS))**(1/a[:,0,None])


def crps_values(pars,ys):
    b,e,g=np.asarray(pars,float).T
    z=np.maximum((ys-g[:,None])/e[:,None],0)**b[:,None]
    F=-np.expm1(-z)
    return (ys-g[:,None])*(2*F-1)-2*e[:,None]*gamma_fn(1+1/b[:,None])*gammainc(1+1/b[:,None],z)+e[:,None]*gamma_fn(1+1/b[:,None])*2**(-1/b[:,None])


def real_metrics(pars,ys,thresholds):
    qs=quantiles(pars);errors=ys[:,:,None]-qs[:,None,:]
    losses=np.maximum(PS*errors,(PS-1)*errors).mean(axis=1)
    out={'crps':crps_values(pars,ys).mean(axis=1)}
    for j,p in enumerate(PS):out[f'pinball_{p:g}']=losses[:,j]
    # Calibration is descriptive, not an alternative loss to optimize after seeing results.
    for j,p in enumerate(PS):out[f'coverage_{p:g}']=(ys<=qs[:,j,None]).mean(axis=1)
    for alpha in [.1,.2]:
        lo=qs[:,np.flatnonzero(np.isclose(PS,alpha/2))[0],None]
        hi=qs[:,np.flatnonzero(np.isclose(PS,1-alpha/2))[0],None]
        out[f'interval_{1-alpha:g}']=(hi-lo+2/alpha*(np.maximum(lo-ys,0)+np.maximum(ys-hi,0))).mean(axis=1)
    b,e,g=np.asarray(pars,float).T
    for t in thresholds:
        pred=-np.expm1(-np.maximum((t-g)/e,0)**b)
        out[f'brier_{t:g}']=((pred[:,None]-(ys<=t))**2).mean(axis=1)
    return out


def prepare():
    OUT.mkdir(exist_ok=True);(OUT/'chunks').mkdir(exist_ok=True)
    original=json.loads((HERE/'留出预测评价/protocol.json').read_text(encoding='utf8'))
    assert json.loads((HERE/'留出预测评价/verification.json').read_text(encoding='utf8'))['status']=='passed'
    for p,h in original['hashes'].items(): assert sha(p)==h,p
    diag=json.loads((HERE/'扩展诊断/protocol.json').read_text(encoding='utf8'))
    for p,h in diag['hashes'].items(): assert sha(p)==h,p
    files=[Path(__file__),HERE/'run_pilot.py',HERE.parent/'E10_样本量扩展/run_e10.py',
           HERE/'留出预测评价/per_subsample.csv.gz',HERE/'留出预测评价/estimation_ids.csv.gz',
           HERE/'扩展诊断/per_sample.csv.gz',HERE/'reference_fits.csv',
           HERE/'参数轨迹/full101_estimates.csv',LIB/'182-047-pdf原文.md',LIB/'182-050-pdf原文.md']
    files += [MODELDIR/f'n{n}_final.json' for n in NS]
    files += [REPO/'python/methods'/f'{m}.py' for m in ['mdm','mle','wmle','lse','lre']]
    fixed=pd.read_csv(HERE/'参数轨迹/full101_estimates.csv').query("method=='MDM-0.1'")
    anchor=fixed[['beta_hat','eta_hat','gamma_hat']].iloc[0].tolist()
    protocol=dict(status='exploratory metric audit, fixed before results',cases=CASES,
        p=PS.tolist(),new_case_repeats=NEW_REPEATS,simulation_repeats=SIM_REPEATS,
        simulation_anchor_MDM=anchor,seed=2026092519,bootstrap=BOOT,
        metrics='CRPS, all nine pinball losses, 80/90% interval scores, fixed-threshold Brier; coverage diagnostic only',
        comparison='AMDM vs MDM-0.1 primary; all method tables retained; identical successful splits per pair',
        uncertainty='paired bootstrap over random subsets conditional on fixed empirical pool/model; not population CI',
        metric_selection='all prespecified metrics retained; pointwise CIs exploratory, no unadjusted significance claims',
        new_cases='external case sensitivity; smaller original datasets, not an independent population-wide validation',
        simulation='full-data MDM anchor plus existing MLE anchor; generating parameters are known only in simulation',
        scale='original physical units, existing E09 unit conversion for classical methods; no data-dependent scaling',
        claim='any selected promising target still needs separately designed independent confirmation',
        hashes={str(p):sha(p) for p in files})
    path=OUT/'protocol.json'
    if path.exists():assert json.loads(path.read_text(encoding='utf8'))==protocol,'Changed frozen inputs'
    else:write_json(path,protocol)
    write_json(OUT/'cases.json',CASES)
    for c,spec in CASES.items():
        if c=='fatigue101':continue
        for n in spec['ns']:
            rng=np.random.default_rng(np.random.SeedSequence([2026092519,list(CASES).index(c),n]))
            ids=np.array([np.sort(rng.choice(len(spec['values']),n,replace=False)) for _ in range(NEW_REPEATS)])
            np.savez_compressed(OUT/f'{c}_n{n}.npz',observation_ids=ids,values=spec['values'])
    return protocol


def batch(task):
    case,n,start,stop=task
    path=OUT/'chunks'/f'{case}_n{n}_{start:04d}.csv.gz'
    if path.exists():return
    model=json.loads((MODELDIR/f'n{n}_final.json').read_text(encoding='utf8'))
    is_sim=case=='sim_MDM_anchor'
    if is_sim:
        anchor=json.loads((OUT/'protocol.json').read_text(encoding='utf8'))['simulation_anchor_MDM']
        xs=[generate_sample(*anchor,n,r,seed=2026092519) for r in range(start,stop)]
    else:
        with np.load(OUT/f'{case}_n{n}.npz') as z:xs=np.sort(z['values'][z['observation_ids'][start:stop]],axis=1)
    rows=[]
    for rep,x in enumerate(xs,start):
        solver=CachedMDM(x)
        for method in (METHODS[:2] if is_sim else METHODS):
            try:
                if method in METHODS[:2]:
                    d=float(DELTAS[np.argmin(predict_curve(x,model))]) if method=='AMDM' else .1
                    pars,_=solver.fit(d)
                    valid=bool(np.isfinite(pars).all() and pars[0]>0 and pars[1]>0 and 0<=pars[2]<min(x));err=''
                else:pars,valid,d,err=fit(x,method)
                rows.append(dict(case=case,n=n,repeat=rep,method=method,valid=valid,delta=d,
                    beta_hat=pars[0],eta_hat=pars[1],gamma_hat=pars[2],failure=err))
            except Exception as e:
                rows.append(dict(case=case,n=n,repeat=rep,method=method,valid=False,failure=repr(e)))
    pd.DataFrame(rows).to_csv(path,index=False,compression='gzip')


def evaluate_real(df):
    outputs=[]
    for (case,n,method),part in df.groupby(['case','n','method']):
        g=part[part.valid].copy().sort_values('repeat')
        values=np.asarray(CASES[case]['values'],float)
        if case=='fatigue101':
            ids=pd.read_csv(HERE/'留出预测评价/estimation_ids.csv.gz').query('n==@n').observation_id.to_numpy().reshape(2000,n)
        else:
            with np.load(OUT/f'{case}_n{n}.npz') as z:ids=z['observation_ids']
        ys=np.array([values[np.setdiff1d(np.arange(len(values)),ids[r])] for r in g.repeat])
        vals=real_metrics(g[['beta_hat','eta_hat','gamma_hat']].to_numpy(),ys,CASES[case]['thresholds'])
        for metric,arr in vals.items():g[metric]=arr
        outputs.append(g)
    result=pd.concat(outputs,ignore_index=True)
    result.to_csv(OUT/'real_scores.csv.gz',index=False,compression='gzip')
    return result


def evaluate_sim(df):
    old=pd.read_csv(HERE/'扩展诊断/per_sample.csv.gz').query("regime=='matched_weibull'").copy()
    old['case']='sim_MLE_anchor'
    new=df.query("case=='sim_MDM_anchor'")
    sims=pd.concat([old,new],ignore_index=True)
    anchors={'sim_MLE_anchor':pd.read_csv(HERE/'reference_fits.csv')[['beta_hat','eta_hat','gamma_hat']].iloc[0].to_numpy(),
             'sim_MDM_anchor':np.array(json.loads((OUT/'protocol.json').read_text(encoding='utf8'))['simulation_anchor_MDM'])}
    outputs=[]
    for case,g0 in sims.groupby('case'):
        g=g0[g0.valid].copy();theta=anchors[case]
        p=g[['beta_hat','eta_hat','gamma_hat']].to_numpy()
        errors=(p-theta)/[theta[0],theta[1],theta[1]]
        for j,k in enumerate(['beta','eta','gamma']):g[f'mse_{k}']=errors[:,j]**2
        g['mse_joint']=np.sum(errors**2,axis=1)
        q=quantiles(p);qt=quantiles(theta[None,:])[0]
        for j,prob in enumerate(PS):g[f'mse_q{prob:g}']=((q[:,j]-qt[j])/theta[1])**2
        outputs.append(g)
    result=pd.concat(outputs,ignore_index=True)
    result.to_csv(OUT/'simulation_scores.csv.gz',index=False,compression='gzip')
    return result


def comparisons(scores,kind):
    metrics=([c for c in scores if c.startswith(('pinball_','brier_','interval_'))]+['crps']) if kind=='real' else [c for c in scores if c.startswith('mse_')]
    rows=[];details=[]
    for (case,n),g in scores.groupby(['case','n']):
        a=g[g.method=='AMDM'].set_index('repeat')
        for method in METHODS[1:]:
            b=g[g.method==method].set_index('repeat')
            ix=a.index.intersection(b.index)
            if len(ix)==0:continue
            av=a.loc[ix,metrics].to_numpy();bv=b.loc[ix,metrics].to_numpy()
            # Columns from other cases' threshold grid are absent (NaN); omit only those.
            keep=np.isfinite(av).all(axis=0)&np.isfinite(bv).all(axis=0)
            ms=np.array(metrics)[keep];av=av[:,keep];bv=bv[:,keep]
            power=.5 if kind=='sim' else 1.
            gains=100*(1-(av.mean(0)/bv.mean(0))**power)
            lo=np.full(len(ms),np.nan);hi=lo.copy()
            if method=='MDM-0.1':
                rng=np.random.default_rng(np.random.SeedSequence([2026092519,int(n),len(case)]))
                draws=[]
                for _ in range(BOOT//100):
                    counts=rng.multinomial(len(ix),np.full(len(ix),1/len(ix)),size=100)
                    draws.append(100*(1-((counts@av)/(counts@bv))**power))
                lo,hi=np.quantile(np.concatenate(draws),[.025,.975],axis=0)
            for j,m in enumerate(ms):
                half=len(ix)//2
                rows.append(dict(kind=kind,case=case,n=n,comparator=method,metric=m,count=len(ix),
                    amdm=av[:,j].mean()**power,baseline=bv[:,j].mean()**power,gain_percent=gains[j],
                    conditional_lo95=lo[j],conditional_hi95=hi[j],
                    first_half_gain=100*(1-(av[:half,j].mean()/bv[:half,j].mean())**power),
                    second_half_gain=100*(1-(av[half:,j].mean()/bv[half:,j].mean())**power)))
                if method=='MDM-0.1':
                    # Stability to deletion of any one observed specimen from evaluated splits.
                    if kind=='real':
                        if case=='fatigue101':
                            ids=pd.read_csv(HERE/'留出预测评价/estimation_ids.csv.gz').query('n==@n').observation_id.to_numpy().reshape(2000,n)
                        else:
                            with np.load(OUT/f'{case}_n{n}.npz') as z:ids=z['observation_ids']
                        # Not a refit/deletion diagnostic: estimate-subset inclusion sensitivity.
                        for obs in [int(np.argmin(CASES[case]['values'])),int(np.argmax(CASES[case]['values']))]:
                            included=(ids[ix]==obs).any(axis=1)
                            for flag in [False,True]:
                                mask=included==flag
                                if mask.sum():details.append(dict(case=case,n=n,metric=m,extreme_id=obs,in_estimation=flag,count=int(mask.sum()),gain_percent=100*(1-av[mask,j].mean()/bv[mask,j].mean())))
    pd.DataFrame(rows).to_csv(OUT/f'{kind}_comparison.csv',index=False)
    if details:pd.DataFrame(details).to_csv(OUT/'extreme_inclusion_sensitivity.csv',index=False)
    return pd.DataFrame(rows)


def verify(new,real,sim,protocol):
    assert len(new)==40000 and not new.duplicated(['case','n','repeat','method']).any()
    assert len(new.query("case!='sim_MDM_anchor'"))==24000
    source=pd.read_csv(HERE/'留出预测评价/per_subsample.csv.gz')
    joined=real.query("case=='fatigue101'").merge(source,on=['n','repeat','method'],suffixes=('_new','_old'))
    err=float(abs(joined.crps_new-joined.crps_old).max());assert err<1e-7
    # Quantile formula inverted through CDF, and interval score equals paired pinball identity.
    checked=0
    for (case,n,method),g in real.groupby(['case','n','method']):
        row=g.iloc[0];pars=row[['beta_hat','eta_hat','gamma_hat']].to_numpy(float)
        assert np.allclose(cdf(quantiles(pars[None,:])[0],pars),PS,atol=1e-10)
        assert np.isclose(row['interval_0.9'],20*(row['pinball_0.05']+row['pinball_0.95']))
        assert np.isclose(row['interval_0.8'],10*(row['pinball_0.1']+row['pinball_0.9']))
        checked+=1
    for case in ['rotor20','bearing23']:
        for n in [7,10]:
            with np.load(OUT/f'{case}_n{n}.npz') as z:x=np.sort(z['values'][z['observation_ids'][0]])
            for method in METHODS[:2]:
                pars,valid,_,_=fit(x,method)
                row=new.query('case==@case and n==@n and repeat==0 and method==@method').iloc[0]
                assert valid==row.valid and np.allclose(pars,row[['beta_hat','eta_hat','gamma_hat']].to_numpy(float),rtol=1e-8,atol=1e-6)
    assert all(sha(p)==h for p,h in protocol['hashes'].items())
    write_json(OUT/'verification.json',dict(status='passed',new_fit_rows=len(new),
        existing_CRPS_max_abs_difference=err,formula_checks=checked,source_hashes_unchanged=True,
        cached_vs_production_checks=8,all_metrics_reported=True,models_retrained=False))


def main():
    protocol=prepare()
    print('Metric grid, cases and simulation anchor frozen.',flush=True)
    tasks=[]
    for case in ['rotor20','bearing23','sim_MDM_anchor']:
        limit=SIM_REPEATS if case.startswith('sim') else NEW_REPEATS
        for n in NS if case.startswith('sim') else [7,10]:
            tasks.extend((case,n,start,min(start+25,limit)) for start in range(0,limit,25))
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(batch,t) for t in tasks]
        for i,f in enumerate(as_completed(jobs),1):
            f.result()
            if i%20==0:print(f'{i}/{len(tasks)} batches complete',flush=True)
    new=pd.concat([pd.read_csv(OUT/'chunks'/f'{c}_n{n}_{start:04d}.csv.gz') for c,n,start,_ in tasks],ignore_index=True)
    new.to_csv(OUT/'new_estimates.csv.gz',index=False,compression='gzip')
    old=pd.read_csv(HERE/'留出预测评价/per_subsample.csv.gz');old['case']='fatigue101'
    real=evaluate_real(pd.concat([old,new.query("case!='sim_MDM_anchor'")],ignore_index=True))
    sim=evaluate_sim(new)
    verify(new,real,sim,protocol)
    print('Scoring and formula verification complete; computing paired summaries.',flush=True)
    a=comparisons(real,'real');b=comparisons(sim,'sim')
    attempts=pd.concat([old,new],ignore_index=True)
    attempts.groupby(['case','n','method']).valid.agg(['size','sum']).rename(columns={'size':'attempts','sum':'successes'}).to_csv(OUT/'success_rates.csv')
    print(a.query("comparator=='MDM-0.1' and metric.str.startswith('pinball')")[['case','n','metric','gain_percent','conditional_lo95','conditional_hi95']].to_string(index=False),flush=True)


if __name__=='__main__':main()
