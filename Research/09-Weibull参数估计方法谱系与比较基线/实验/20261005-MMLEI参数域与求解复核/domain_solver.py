"""Stable CW-I profile with dense grids, extrema checks and a negative-location limit."""
import json
from pathlib import Path
import numpy as np
from scipy.optimize import brentq,minimize_scalar
from scipy.special import logsumexp

HERE=Path(__file__).resolve().parent
CFG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))

def analyze(raw,detailed=False):
    x=np.sort(np.asarray(raw,float))/CFG['unit'];n=len(x);xmin=float(x[0]);delta=x-xmin
    spread=float(delta[-1]);c=np.log1p(1/n);logc=np.log(c)
    lower=float(x.mean()-10*x.std(ddof=1));dmin=CFG['raw_gap_floor']/CFG['unit']
    if spread<=0:raise ValueError('Degenerate sample')
    lo=np.log(dmin);main_hi=np.log(xmin);paper_hi=np.log(xmin-lower)
    hi=max(main_hi,paper_hi);cache={}

    def from_u(u,s,d):
        mean=float(u.mean())
        def score(k):
            w=np.exp(k*(u-1));return k*(float(w@u/w.sum())-mean)-1
        high=max(2.0,float(n))
        while score(high)<0:high*=2
        k=brentq(score,1e-8,high,xtol=1e-12,rtol=1e-12)
        w=np.exp(k*(u-1));w/=w.sum()
        b=k/s if s is not None else np.inf
        residual=float(logsumexp(k*u)-np.log(n)+logc)
        return b,residual,k,u,w,float(score(k)),d

    def profile(t):
        t=float(t)
        if t not in cache:
            d=float(np.exp(t));logs=np.log1p(delta/d);s=float(logs[-1]);u=logs/s
            cache[t]=from_u(u,s,d)
        return cache[t]

    def populate(ts):
        ds=np.exp(ts);logs=np.log1p(delta[None,:]/ds[:,None]);ss=logs[:,-1];us=logs/ss[:,None]
        means=us.mean(axis=1);left=np.zeros(len(ts));right=np.full(len(ts),float(max(2,n)))
        def vector_score(ks):
            ws=np.exp(ks[:,None]*(us-1));ws/=ws.sum(axis=1)[:,None]
            a=(ws*us).sum(axis=1)-means
            variance=(ws*(us-(ws*us).sum(axis=1)[:,None])**2).sum(axis=1)
            return ks*a-1,a+ks*variance,ws
        while True:
            scores,_,_=vector_score(right);bad=scores<0
            if not bad.any():break
            right[bad]*=2
        ks=(left+right)/2
        for _ in range(80):
            scores,derivative,ws=vector_score(ks)
            if np.max(np.abs(scores))<2e-12:break
            left=np.where(scores<0,ks,left);right=np.where(scores>=0,ks,right)
            proposed=ks-scores/derivative
            ks=np.where((proposed>left)&(proposed<right),proposed,(left+right)/2)
        residuals=logsumexp(ks[:,None]*us,axis=1)-np.log(n)+logc
        for j,t in enumerate(ts):
            cache[float(t)]=(float(ks[j]/ss[j]),float(residuals[j]),float(ks[j]),us[j],ws[j],float(scores[j]),float(ds[j]))

    step=CFG['failed_log_gap_step'] if detailed else CFG['base_log_gap_step']
    grid=np.linspace(lo,hi,int(np.ceil((hi-lo)/step))+1)
    if detailed:
        wide_hi=np.log(spread)+CFG['wide_log_gap_extension']
        if wide_hi>hi:
            extension=np.linspace(hi,wide_hi,int(np.ceil((wide_hi-hi)/.04))+1)
            grid=np.unique(np.r_[grid,extension])
    populate(grid)
    vals=np.array([profile(t)[1] for t in grid]);betas=np.array([profile(t)[0] for t in grid])
    roots=[];extrema=[]
    for i in range(len(grid)-1):
        if vals[i]*vals[i+1]<0:
            roots.append(brentq(lambda t:profile(t)[1],grid[i],grid[i+1],xtol=1e-12,rtol=1e-12))
        if abs(vals[i])<=1e-11:roots.append(float(grid[i]))
    # A same-sign paired crossing or tangent can be missed by sign checks alone.
    for i in range(1,len(grid)-1):
        if max(abs(vals[i]-vals[i-1]),abs(vals[i]-vals[i+1]))>1e-9 and (vals[i]<=vals[i-1] and vals[i]<=vals[i+1] or vals[i]>=vals[i-1] and vals[i]>=vals[i+1]):
            sign=1 if vals[i]<=vals[i-1] and vals[i]<=vals[i+1] else -1
            result=minimize_scalar(lambda t:sign*profile(t)[1],bounds=(grid[i-1],grid[i+1]),method='bounded',options={'xatol':1e-11})
            t=float(result.x);value=profile(t)[1];extrema.append((t,value))
            for edge in [grid[i-1],grid[i+1]]:
                if profile(edge)[1]*value<0:roots.append(brentq(lambda z:profile(z)[1],min(t,edge),max(t,edge),xtol=1e-12,rtol=1e-12))
            if abs(value)<=1e-10:roots.append(t)
    if abs(vals[-1])<=1e-11:roots.append(float(grid[-1]))
    distinct=[]
    for t in sorted(roots):
        if not distinct or abs(t-distinct[-1])>1e-7:distinct.append(t)
    candidates=[]
    for t in distinct:
        b,r,k,u,w,shape_res,d=profile(t);g=xmin-d
        logs=np.log(x-g);eta=float(np.exp((logsumexp(b*logs)-np.log(n))/b))
        objective=r*r+shape_res*shape_res
        if objective<=CFG['residual_squared_tolerance']:
            candidates.append(dict(log_gap=t,beta=b,eta=eta*1000,gamma=g*1000,objective=objective,raw_gap=d*1000))
    fits={}
    for name,upper,bounds in [('engineering',main_hi,CFG['shape_engineering']),('paper',paper_hi,CFG['shape_paper'])]:
        valid=[p for p in candidates if lo-1e-10<=p['log_gap']<=upper+1e-10 and bounds[0]<p['beta']<bounds[1]]
        selected=valid[0] if valid else None
        category='ok' if selected else 'outside_declared_domain_root' if candidates else 'no_root_after_dense_search'
        fits[name]=dict(status=category,estimate=selected,location_lower_raw=0.0 if name=='engineering' else lower*1000,
                       shape_bounds=bounds,roots_found=len(candidates))
    limit=from_u(delta/spread,None,None)[1]
    i=int(np.argmin(vals));minimum_t=float(grid[i]);minimum=float(vals[i])
    for t,v in extrema:
        if v<minimum:minimum_t,minimum=t,v
    min_gamma=(xmin-np.exp(minimum_t))*1000
    record=dict(fits=fits,candidates=candidates,log_gap_step=step,grid_points=len(grid),
                finite_minimum_residual=minimum,finite_minimum_gamma=min_gamma,limit_residual=limit,
                observed_monotone_decreasing=bool(np.all(np.diff(vals)<=1e-8)),
                observed_monotone_increasing=bool(np.all(np.diff(vals)>=-1e-8)),local_extrema=len(extrema),
                searched_gamma_low=float((xmin-np.exp(grid[-1]))*1000),searched_gamma_high=float((xmin-dmin)*1000),
                no_global_nonexistence_proof=True)
    return record,dict(log_gap=grid,gamma=(xmin-np.exp(grid))*1000,residual=vals,beta=betas)
