"""Post-discovery sensitivity: refit after excluding one extreme observation.

Both low and high endpoints, all four n, and the full quantile grid are retained.
This is exploratory robustness, not independent confirmation of a selected metric.
"""
from pathlib import Path
import os
for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS'):
    os.environ[k]='1'
import json
from concurrent.futures import ProcessPoolExecutor,as_completed
import numpy as np
import pandas as pd
from explore_metrics import OUT,CASES,NS,MODELDIR,PS,real_metrics,CachedMDM,predict_curve,DELTAS,sha,write_json

HERE=Path(__file__).resolve().parent
DEST=OUT/'极端观测敏感性'
REPEATS=1000


def batch(task):
    drop,n,start,stop=task
    path=DEST/'chunks'/f'{drop}_n{n}_{start:04d}.csv.gz'
    if path.exists():return
    obs=np.array(CASES['fatigue101']['values'])
    omitted=np.argmin(obs) if drop=='drop_min' else np.argmax(obs)
    values=np.delete(obs,omitted)
    with np.load(DEST/f'{drop}_n{n}.npz') as z:ids=z['ids'][start:stop]
    model=json.loads((MODELDIR/f'n{n}_final.json').read_text(encoding='utf8'))
    rows=[]
    for rep,chosen in enumerate(ids,start):
        x=np.sort(values[chosen]);heldout=values[np.setdiff1d(np.arange(100),chosen)]
        solver=CachedMDM(x)
        for method in ['AMDM','MDM-0.1']:
            delta=float(DELTAS[np.argmin(predict_curve(x,model))]) if method=='AMDM' else .1
            try:
                pars,_=solver.fit(delta)
                valid=bool(np.isfinite(pars).all() and pars[0]>0 and pars[1]>0 and 0<=pars[2]<min(x))
                metrics=real_metrics(np.array(pars)[None,:],heldout[None,:],CASES['fatigue101']['thresholds']) if valid else {}
                rows.append(dict(drop=drop,n=n,repeat=rep,method=method,valid=valid,delta=delta,
                    **{k:float(v[0]) for k,v in metrics.items()}))
            except Exception as ex:rows.append(dict(drop=drop,n=n,repeat=rep,method=method,valid=False,failure=repr(ex)))
    pd.DataFrame(rows).to_csv(path,index=False,compression='gzip')


def main():
    DEST.mkdir(exist_ok=True);(DEST/'chunks').mkdir(exist_ok=True)
    sources=[Path(__file__),HERE/'explore_metrics.py',HERE/'observations.csv']+[MODELDIR/f'n{n}_final.json' for n in NS]
    protocol=dict(status='post-discovery exploratory endpoint sensitivity',repeats=REPEATS,
        exclusions=['minimum observation 370','maximum observation 2440'],sample_sizes=NS,
        quantiles=PS.tolist(),seed=2026092520,retuning=False,
        purpose='check low-quantile gains after refitting on a 100-observation pool with an extreme removed',
        hashes={str(p):sha(p) for p in sources})
    if (DEST/'protocol.json').exists():assert json.loads((DEST/'protocol.json').read_text(encoding='utf8'))==protocol
    else:write_json(DEST/'protocol.json',protocol)
    tasks=[]
    for d,drop in enumerate(['drop_min','drop_max']):
        for n in NS:
            rng=np.random.default_rng(np.random.SeedSequence([2026092520,d,n]))
            ids=np.array([np.sort(rng.choice(100,n,replace=False)) for _ in range(REPEATS)])
            np.savez_compressed(DEST/f'{drop}_n{n}.npz',ids=ids)
            tasks.extend((drop,n,i,i+25) for i in range(0,REPEATS,25))
    with ProcessPoolExecutor(max_workers=2) as pool:
        jobs=[pool.submit(batch,t) for t in tasks]
        for i,f in enumerate(as_completed(jobs),1):
            f.result()
            if i%40==0:print(f'endpoint sensitivity {i}/{len(tasks)}',flush=True)
    df=pd.concat([pd.read_csv(DEST/'chunks'/f'{d}_n{n}_{i:04d}.csv.gz') for d,n,i,_ in tasks],ignore_index=True)
    assert len(df)==16000 and not df.duplicated(['drop','n','repeat','method']).any()
    df.to_csv(DEST/'scores.csv.gz',index=False,compression='gzip')
    rows=[]
    for (drop,n),g in df.groupby(['drop','n']):
        a=g[g.method=='AMDM'].set_index('repeat');b=g[g.method=='MDM-0.1'].set_index('repeat')
        keep=a.valid & b.valid
        for m in ['crps']+[f'pinball_{p:g}' for p in PS]:
            av=a.loc[keep,m];bv=b.loc[keep,m]
            rows.append(dict(drop=drop,n=n,metric=m,count=int(keep.sum()),amdm=av.mean(),mdm=bv.mean(),gain_percent=100*(1-av.mean()/bv.mean())))
    pd.DataFrame(rows).to_csv(DEST/'comparison.csv',index=False)
    assert all(sha(p)==h for p,h in protocol['hashes'].items())
    write_json(DEST/'verification.json',dict(status='passed',rows=len(df),all_valid=bool(df.valid.all()),hashes_unchanged=True))
    print('Endpoint sensitivity completed.',flush=True)


if __name__=='__main__':main()
