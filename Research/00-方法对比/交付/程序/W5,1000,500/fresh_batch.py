"""Fresh paired-method batch, production sampling and runner, no source overwrite."""
import csv, hashlib, json, sys
from pathlib import Path
import numpy as np
PROGRAM_DIR=Path(__file__).resolve().parent
ROOT=PROGRAM_DIR/'依赖快照'
BETA, ETA, GAMMA = 5.0, 1000.0, 500.0
sys.path.insert(0,str(ROOT/'python'))
from studies.common.sample import generate_sample
from studies.common.runner import run_method

sizes=[30] if '--n30' in sys.argv else [7,15]
OUT=PROGRAM_DIR.parent/'结果'/'复算输出'/('n30' if sizes==[30] else 'n7-n15')
OUT.mkdir(parents=True,exist_ok=False)
seed=2026092903
samples=[];results=[]
for n in sizes:
    for sid in range(1,51):
        x=generate_sample(BETA,ETA,GAMMA,n,sid-1,seed=seed)
        seedtext=f'{seed}|5.0|1000.0|500.0|{n}|{sid-1}'
        rng=np.random.default_rng(int.from_bytes(hashlib.sha256(seedtext.encode()).digest()[:4],'big'))
        u=rng.uniform(size=n)
        expected=np.sort(500.0+1000.0*(-np.log(1-u))**.2)
        assert np.array_equal(x,expected)
        samples.append({'n':n,'id':sid,'values':x.tolist()})
        for method,delta in [('mdm',.1),('mdm',.15),('mdm',.2),('lse',None),('lre',None),('wmle',None),('mle',None)]:
            kw={'offset':delta,'gamma_steps':240} if method=='mdm' else {}
            r=run_method(method,x,**kw)
            if r['converged']:
                assert r['beta_hat']>0 and r['eta_hat']>0 and 0<=r['gamma_hat']<x[0]
                assert all(np.isfinite(r[k]) for k in ['beta_hat','eta_hat','gamma_hat'])
            results.append({'n':n,'id':sid,'delta':delta,**r})
        if sid%10==0:print('PROGRESS',n,sid,flush=True)
summary=[]
for n in sizes:
    for method,delta in [('mdm',.1),('mdm',.15),('mdm',.2),('lse',None),('lre',None),('wmle',None),('mle',None)]:
        rr=[r for r in results if r['n']==n and r['method_id']==method and r['delta']==delta]
        valid=[r for r in rr if r['converged']]
        a=np.array([[r[k] for k in ['beta_hat','eta_hat','gamma_hat']] for r in valid])
        entry={'n':n,'method':method,'delta':delta,'valid':len(valid),'means':a.mean(axis=0).tolist() if len(a) else None,
               'medians':np.median(a,axis=0).tolist() if len(a) else None,'gamma_gt500':sum(r['gamma_hat']>500 for r in valid),
               'gamma_zero':sum(r['gamma_hat']==0 for r in valid)}
        summary.append(entry);print('SUMMARY',json.dumps(entry),flush=True)
payload={'seed':seed,'truth':[5.,1000.,500.],'samples':samples,'results':results,'summary':summary,
         'implementation_note':'当前平台实现；LRE为2026-09-29更新的Park(2017) Proposed+Plot，与历史Bernard版本不同；WMLE沿用原J权重和求解器，不使用临时试验权重。',
         'code_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in ['python/studies/common/sample.py','python/methods/mdm.py','python/methods/wmle.py','python/methods/j3_weights.tsv','python/methods/lre.py','python/methods/lse.py','python/methods/mle.py']}}
(OUT/'results.json').write_text(json.dumps(payload,ensure_ascii=False,allow_nan=False),encoding='utf-8')
print('SAVED',OUT,flush=True)
