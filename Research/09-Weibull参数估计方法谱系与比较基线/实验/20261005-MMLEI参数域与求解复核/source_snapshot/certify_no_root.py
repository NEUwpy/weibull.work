"""Data-specific positive-residual certificates, including both infinite tails.

The profile H(k,u)=k(E_k u-mean(u))-1 has a unique positive zero.
If H_upper(k0)<0, its zero k*>k0. Therefore C>=log(mean(exp(k0*u_lower)))+log(c).
For each interval in d=x_min-gamma, u_i(d)=log(1+delta_i/d)/log(1+delta_max/d)
decreases with d; its endpoint values enclose the entire interval.
All final inequalities are rechecked with mpmath interval arithmetic at 40 digits.
"""
import argparse,json,math
from concurrent.futures import ProcessPoolExecutor,as_completed
from pathlib import Path
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from scipy.optimize import brentq
from mpmath import iv
HERE=Path(__file__).resolve().parent

def certificate(args):
    sha,n=args;dest=HERE/'无根区间证书';dest.mkdir(exist_ok=True);target=dest/f'{sha}.json'
    if target.exists():return json.loads(target.read_text(encoding='utf-8'))['summary']
    raw=np.load(HERE/'逐样本曲线'/f'{sha}.npz')['sample'];delta=(raw-raw[0])/1000;spread=delta[-1]
    logdelta=np.full(n,-np.inf);logdelta[delta>0]=np.log(delta[delta>0]);logspread=np.log(spread)
    c=np.log1p(1/n);logc=np.log(c)
    def u_at(t):
        if t==-np.inf:return np.r_[0.,np.ones(n-1)]
        if t==np.inf:return delta/spread
        logs=np.logaddexp(logdelta,t)-t;return logs/logs[-1]
    def bounds(a,b):
        high=u_at(a);low=u_at(b)
        def hup(k):
            numerator=logsumexp(k*high[1:]+np.log(high[1:]));denominator=logsumexp(k*low)
            return k*(np.exp(min(710.,numerator-denominator))-low.mean())-1
        left=0.;right=float(2*n)
        while hup(right)<0:right*=2
        for _ in range(45):
            mid=(left+right)/2
            if hup(mid)<-1e-9:left=mid
            else:right=mid
        residual=float(logsumexp(left*low)-np.log(n)+logc)
        return left,float(hup(left)),residual
    pending=[(-np.inf,np.inf,0)];parts=[]
    while pending:
        a,b,depth=pending.pop();k,h,r=bounds(a,b)
        if r>1e-9 and h<-5e-10:parts.append((a,b,k,h,r));continue
        if depth>50:return dict(sha=sha,n=n,certified=False,reason='subdivision limit',intervals=len(parts))
        mid=logspread if not np.isfinite(a) and not np.isfinite(b) else b-2 if not np.isfinite(a) else a+2 if not np.isfinite(b) else (a+b)/2
        pending.extend([(mid,b,depth+1),(a,mid,depth+1)])
    parts.sort(key=lambda p:p[0])
    assert parts[0][0]==-np.inf and parts[-1][1]==np.inf
    assert all(parts[j][1]==parts[j+1][0] for j in range(len(parts)-1))
    iv.dps=40
    rawiv=[iv.mpf(float(v)) for v in raw];div=[v-rawiv[0] for v in rawiv];scale=iv.mpf(1000)
    def exact_u(t):
        if t==-np.inf:return [iv.mpf(0)]+[iv.mpf(1)]*(n-1)
        if t==np.inf:return [v/div[-1] for v in div]
        d=iv.exp(iv.mpf(float(t)))*scale
        logs=[iv.log(1+v/d) for v in div];return [v/logs[-1] for v in logs]
    cache={};saved=[]
    for a,b,k,_,_ in parts:
        if a not in cache:cache[a]=exact_u(a)
        if b not in cache:cache[b]=exact_u(b)
        high=[v.b for v in cache[a]];low=[v.a for v in cache[b]];kiv=iv.mpf(float(k))
        hup=kiv*(sum(v*iv.exp(kiv*v) for v in high)/sum(iv.exp(kiv*v) for v in low)-sum(low)/n)-1
        rlow=iv.log(sum(iv.exp(kiv*v) for v in low)/n)+iv.log(iv.log(1+iv.mpf(1)/n))
        assert hup.b<0 and rlow.a>0,(sha,a,b,str(hup),str(rlow))
        saved.append(dict(log_gap_lower='-inf' if not np.isfinite(a) else a,
                          log_gap_upper='inf' if not np.isfinite(b) else b,k_lower=k,
                          H_upper=str(hup),C_lower=str(rlow),C_lower_float=float(rlow.a)))
    summary=dict(sha=sha,n=n,certified=True,intervals=len(parts),minimum_C_lower=min(v['C_lower_float'] for v in saved),
                 scope='All finite d>0, hence all gamma<x_min; beta>0 unconstrained',arithmetic='mpmath.iv,40 decimal digits')
    target.write_text(json.dumps(dict(summary=summary,intervals=saved),ensure_ascii=False,indent=2),encoding='utf-8')
    return summary

def main():
    p=argparse.ArgumentParser();p.add_argument('--workers',type=int,default=6);p.add_argument('--limit',type=int);args=p.parse_args()
    d=pd.read_csv(HERE/'per_sample.csv.gz');d=d[d.method_variant=='cw_engineering']
    jobs=[(row.sample_sha256,int(row.n)) for row in d.itertuples() if not json.loads(row.extra)['solution_info']['diagnostic']['candidates']]
    if args.limit:jobs=jobs[:args.limit]
    results=[]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(certificate,j) for j in jobs]),1):
            results.append(f.result())
            if i%50==0:print(dict(finished=i,total=len(jobs)),flush=True)
    pd.DataFrame(results).to_csv(HERE/'无根证书索引.csv',index=False)
    print(pd.DataFrame(results).groupby(['n','certified']).agg(cases=('sha','size'),intervals=('intervals','sum'),min_bound=('minimum_C_lower','min')).to_string())

if __name__=='__main__':main()
