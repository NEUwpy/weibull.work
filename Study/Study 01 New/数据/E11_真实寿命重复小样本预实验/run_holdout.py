"""E11: paired rotating holdout evaluation on the fixed 101-life dataset.

Reuse only hash-verified frozen estimates on identical observation IDs.
All scores are recomputed on the complement of each estimation subset.
"""
from pathlib import Path
import os
for key in ('OPENBLAS_NUM_THREADS', 'OMP_NUM_THREADS', 'MKL_NUM_THREADS'):
    os.environ[key] = '1'
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
import numpy as np
import pandas as pd
from scipy.integrate import quad
from run_pilot import HERE, REPO, MODELDIR, NS, METHODS, fit, scores, cdf, sha, write_json

OUT = HERE / '留出预测评价'
REPEATS = 2000


def score(pars, heldout):
    # Reuse the previously quadrature-checked Weibull CRPS implementation.
    # Undo its reference-IQR normalization to report original lifetime units.
    return scores(pars, heldout)[1] * (np.quantile(heldout, .75)-np.quantile(heldout, .25))


def prepare():
    OUT.mkdir(exist_ok=True)
    (OUT/'chunks').mkdir(exist_ok=True)
    diag = HERE/'扩展诊断'
    traj = HERE/'参数轨迹'
    # Verify provenance before accepting cached estimates, including solvers/models.
    for directory, field in [(diag, 'hashes'), (traj, 'source_hashes')]:
        protocol = json.loads((directory/'protocol.json').read_text(encoding='utf8'))
        assert json.loads((directory/'verification.json').read_text(encoding='utf8'))['source_hashes_unchanged']
        for path, expected in protocol[field].items():
            assert sha(path) == expected, f'Cached provenance changed: {path}'
    src = [HERE/'observations.csv', HERE/'run_pilot.py', Path(__file__),
           diag/'per_sample.csv.gz', traj/'per_subsample.csv.gz',
           diag/'protocol.json', traj/'protocol.json',
           HERE.parent/'E09_六方法共同测试/wmle_solver.py']
    src += [MODELDIR/f'n{n}_final.json' for n in NS]
    src += [REPO/'python/methods'/f'{m}.py' for m in ['mdm','wmle','mle','lse','lre']]
    src += [diag/f'real_without_replacement_n{n}_samples.npz' for n in NS]
    src += [traj/f'n{n}_samples.npz' for n in NS]
    protocol = dict(status='frozen before scoring; exploratory case evaluation',
        ns=NS, repeats=REPEATS, methods=METHODS, seed='SeedSequence([20260925,n])',
        estimation='n observations sampled without replacement from the 101-life pool',
        evaluation='remaining 101-n observations only; no overlap within a split',
        primary='mean holdout CRPS, original unit: thousand cycles; lower is better',
        main_comparison='same all-six-successful splits for table and distribution figure',
        additional_comparison='AMDM vs each method on pairwise-successful splits; explicit paired counts',
        failures='all failed attempts retained, no fallback, success rates use all 2000 splits',
        variability='conditional split variability; not population confidence intervals',
        data_status='dataset already used in exploration; not a new independent confirmation dataset',
        reuse='existing frozen estimates only, matched by observation IDs; holdout scores recomputed',
        hashes={str(p):sha(p) for p in src})
    if (OUT/'protocol.json').exists():
        assert json.loads((OUT/'protocol.json').read_text(encoding='utf8')) == protocol, 'Frozen inputs changed'
    else:
        write_json(OUT/'protocol.json', protocol)
    values = pd.read_csv(HERE/'observations.csv').life_thousand_cycles.to_numpy()
    assert len(values) == 101
    allids = []
    for n in NS:
        with np.load(diag/f'real_without_replacement_n{n}_samples.npz') as z:
            ids, xs = z['observation_ids'], z['x']
        rng = np.random.default_rng(np.random.SeedSequence([20260925,n]))
        expected = np.array([np.sort(rng.choice(101,n,replace=False)) for _ in range(REPEATS)])
        assert np.array_equal(ids,expected) and np.array_equal(np.sort(values[ids],axis=1),xs)
        with np.load(traj/f'n{n}_samples.npz') as z:
            assert np.array_equal(ids[:500],z['observation_ids'])
        for rep, chosen in enumerate(ids):
            assert len(set(chosen)) == n
            allids.extend(dict(n=n,repeat=rep,observation_id=int(i)) for i in chosen)
    pd.DataFrame(allids).to_csv(OUT/'estimation_ids.csv.gz',index=False,compression='gzip')
    a = pd.read_csv(diag/'per_sample.csv.gz').query("regime=='real_without_replacement'").copy()
    a['fit_source'] = 'expanded_diagnostic'
    b = pd.read_csv(traj/'per_subsample.csv.gz')
    b = b[b.n.isin(NS) & ~b.method.isin(['AMDM','MDM-0.1'])].copy()
    b['fit_source'] = 'parameter_trajectory'
    reused = pd.concat([a,b],ignore_index=True)
    assert len(reused)==24000 and not reused.duplicated(['n','repeat','method']).any()
    reused.to_csv(OUT/'reused_fits.csv.gz',index=False,compression='gzip')
    return values, protocol


def run_batch(task):
    n,start,stop = task
    path = OUT/'chunks'/f'n{n}_{start:04d}.csv.gz'
    if path.exists(): return str(path)
    values = pd.read_csv(HERE/'observations.csv').life_thousand_cycles.to_numpy()
    ids = pd.read_csv(OUT/'estimation_ids.csv.gz').query('n==@n')
    ids = ids.observation_id.to_numpy().reshape(REPEATS,n)
    old = pd.read_csv(OUT/'reused_fits.csv.gz').query('n==@n').set_index(['repeat','method'])
    rows=[]
    for rep in range(start,stop):
        chosen=ids[rep]
        mask=np.ones(101,dtype=bool); mask[chosen]=False
        heldout=values[mask]; x=np.sort(values[chosen])
        assert len(heldout)==101-n and not np.intersect1d(chosen,np.flatnonzero(mask)).size
        for method in METHODS:
            begin=time.perf_counter()
            try:
                if (rep,method) in old.index:
                    row=old.loc[(rep,method)]
                    pars=row[['beta_hat','eta_hat','gamma_hat']].to_numpy(float)
                    valid=bool(row.valid);delta=row.get('delta',np.nan)
                    failure=row.get('failure','')
                    if pd.isna(failure):failure=''
                    source=row.fit_source
                else:
                    pars,valid,delta,failure=fit(x,method)
                    source='new_frozen_fit'
                if not valid and not failure: failure='invalid_or_nonconverged_cached_fit'
                value=score(pars,heldout) if valid else np.nan
                if valid: assert np.isfinite(value) and value>=0
                rows.append(dict(n=n,repeat=rep,method=method,valid=valid,delta=delta,
                    beta_hat=pars[0],eta_hat=pars[1],gamma_hat=pars[2],crps=value,
                    holdout_count=len(heldout),fit_source=source,failure=failure,
                    scoring_and_new_fit_seconds=time.perf_counter()-begin))
            except Exception as ex:
                # Exceptions remain explicit unsuccessful attempts, never omitted.
                rows.append(dict(n=n,repeat=rep,method=method,valid=False,crps=np.nan,
                    holdout_count=len(heldout),fit_source='exception',failure=repr(ex)))
    pd.DataFrame(rows).to_csv(path,index=False,compression='gzip')
    return str(path)


def summarize(df):
    common=[]; summary=[]; paired=[]; counts=[]
    for n,g in df.groupby('n'):
        valid=g.pivot(index='repeat',columns='method',values='valid')[METHODS]
        mask=valid.all(axis=1)
        c=g[g.repeat.isin(mask[mask].index)].copy();common.append(c)
        counts.append(dict(n=int(n),all_six_valid=int(mask.sum()),attempted=REPEATS))
        am=c[c.method=='AMDM'].crps.mean()
        for method in METHODS:
            total=g[g.method==method];v=total[total.valid];s=c[c.method==method].crps
            summary.append(dict(n=n,method=method,attempted=len(total),successes=len(v),
                success_percent=100*len(v)/len(total),common_valid=len(s),
                common_mean_crps=s.mean(),common_median_crps=s.median(),common_sd_crps=s.std(),
                common_q25=s.quantile(.25),common_q75=s.quantile(.75),
                amdm_gain_percent=100*(1-am/s.mean()),all_valid_mean_crps=v.crps.mean()))
        a=g[g.method=='AMDM'].set_index('repeat')
        for method in METHODS[1:]:
            b=g[g.method==method].set_index('repeat');keep=a.valid & b.valid
            av=a.loc[keep,'crps'];bv=b.loc[keep,'crps']
            paired.append(dict(n=n,comparator=method,paired_valid=int(keep.sum()),
                amdm_crps=av.mean(),baseline_crps=bv.mean(),
                gain_percent=100*(1-av.mean()/bv.mean()),mean_difference=(av-bv).mean(),
                amdm_win_fraction=(av<bv).mean()))
    pd.concat(common).to_csv(OUT/'common_scores.csv.gz',index=False,compression='gzip')
    pd.DataFrame(summary).to_csv(OUT/'summary.csv',index=False)
    pd.DataFrame(paired).to_csv(OUT/'paired_comparison.csv',index=False)
    pd.DataFrame(counts).to_csv(OUT/'common_counts.csv',index=False)


def verify(df,values,protocol):
    assert len(df)==48000 and not df.duplicated(['n','repeat','method']).any()
    assert df.groupby(['n','method']).size().eq(REPEATS).all()
    assert not df.loc[~df.valid,'crps'].notna().any()
    ids=pd.read_csv(OUT/'estimation_ids.csv.gz')
    errors=[]
    for row in df[df.valid].groupby(['n','method']).head(1).itertuples():
        chosen=ids[(ids.n==row.n)&(ids.repeat==row.repeat)].observation_id.to_numpy()
        heldout=values[np.setdiff1d(np.arange(101),chosen)]
        pars=np.array([row.beta_hat,row.eta_hat,row.gamma_hat])
        b,e,g=pars
        # Independent integral in standard Weibull coordinates, split at observation.
        integrals=[]
        for y in heldout:
            z=max((y-g)/e,0)
            f=lambda u: float(-np.expm1(-u**b))
            left=quad(lambda u:f(u)**2,0,z,epsabs=1e-10)[0]
            right=quad(lambda u:np.exp(-2*u**b),z,np.inf,epsabs=1e-10)[0]
            integrals.append(e*(left+right)+max(g-y,0))
        error=abs(float(np.mean(integrals))-row.crps)
        assert error<1e-5,(row.n,row.method,error)
        errors.append(error)
    for p,h in protocol['hashes'].items(): assert sha(p)==h,p
    old=pd.read_csv(OUT/'reused_fits.csv.gz')
    joined=df.merge(old,on=['n','repeat','method'],suffixes=('_new','_old'))
    assert len(joined)==24000 and (joined.valid_new==joined.valid_old).all()
    for k in ['beta_hat','eta_hat','gamma_hat','delta']:
        assert np.allclose(joined[k+'_new'],joined[k+'_old'],equal_nan=True,rtol=1e-12,atol=1e-10)
    write_json(OUT/'verification.json',dict(status='passed',rows=len(df),subsets=8000,
        reused_estimates=24000,new_estimates=24000,no_within_split_overlap=True,
        source_hashes_unchanged=True,cached_estimates_unchanged=True,
        independent_crps_quadrature_cases=len(errors),max_crps_abs_difference=max(errors),
        model_retraining=False,population_confidence_intervals=False))


def main():
    values,protocol=prepare()
    print('Frozen protocol saved; sample IDs and cached provenance verified.',flush=True)
    tasks=[(n,start,min(start+25,REPEATS)) for n in NS for start in range(0,REPEATS,25)]
    with ProcessPoolExecutor(max_workers=4) as pool:
        jobs=[pool.submit(run_batch,t) for t in tasks]
        for i,f in enumerate(as_completed(jobs),1):
            f.result()
            if i%10==0:print(f'{i}/{len(tasks)} batches complete',flush=True)
    df=pd.concat([pd.read_csv(OUT/'chunks'/f'n{n}_{start:04d}.csv.gz') for n,start,_ in tasks],ignore_index=True)
    df=df.sort_values(['n','repeat','method'])
    df.to_csv(OUT/'per_subsample.csv.gz',index=False,compression='gzip')
    verify(df,values,protocol)
    summarize(df)
    print('Verified and summarized 48,000 predictions.',flush=True)


if __name__=='__main__':main()
