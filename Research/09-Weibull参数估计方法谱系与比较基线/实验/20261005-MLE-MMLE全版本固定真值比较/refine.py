"""Repair narrow paired-root omissions; preserve the initial MC checkpoints."""
import argparse
from concurrent.futures import ProcessPoolExecutor,as_completed
from functools import lru_cache
import hashlib,json
from pathlib import Path
import numpy as np
from scipy.optimize import brentq,minimize_scalar
from scipy.special import logsumexp
import experiment as e
from studies.common.experiment import run_experiment

METHODS=[m for m in e.METHODS if (m.startswith('mmle_') and m not in ['mmle_i','mmle_i_paper']) or m.startswith('mme_')]

def roots_with_extrema(fun,grid,extra=()):
    points=list(grid)+list(extra);vals=[fun(float(t)) for t in grid]
    for i in range(1,len(grid)-1):
        is_min=vals[i]<min(vals[i-1],vals[i+1]);is_max=vals[i]>max(vals[i-1],vals[i+1])
        if is_min or is_max:
            sign=1 if is_min else -1
            optimized=minimize_scalar(lambda t:sign*fun(float(t)),bounds=(grid[i-1],grid[i+1]),
                                      method='bounded',options={'xatol':1e-11,'maxiter':100})
            if optimized.success:points.append(float(optimized.x))
    points=sorted(set(float(t) for t in points));values=[fun(t) for t in points];roots=[]
    for i,t in enumerate(points):
        if abs(values[i])<1e-11:roots.append(t)
        if i and values[i-1]*values[i]<0:
            roots.append(brentq(fun,points[i-1],t,xtol=1e-12,rtol=1e-12))
    unique=[]
    for root in sorted(roots):
        if not unique or abs(root-unique[-1])>1e-8:unique.append(float(root))
    return unique

@lru_cache(maxsize=4)
def fit_mmle(values,paper_domain=False,grid_size=97):
    x=np.sort(np.array(values));xmin=float(x[0]);sd=x.std(ddof=1)
    lower=float(x.mean()-10*sd) if paper_domain else 0.0
    dmax=xmin-lower;dmin=1e-7
    if dmax<=dmin:return {r:(None,{'status':'empty_location_domain'}) for r in e.ROMAN}
    delta=x-xmin
    @lru_cache(maxsize=2048)
    def profile(t):
        d=np.exp(t);logs=np.log1p(delta/d)
        def first(b):
            p=np.exp(b*(logs-logs.max()))
            return b*(np.dot(p,logs)/p.sum()-logs.mean())-1
        hi=2.0
        while first(hi)<0 and hi<1e7:hi*=2
        if first(hi)<0:raise ArithmeticError('profile_numerical_range')
        b=brentq(first,1e-7,hi,xtol=1e-12,rtol=1e-12);g=xmin-d
        eta=float(np.exp((logsumexp(b*np.log(x-g))-np.log(len(x)))/b))
        return b,eta,g,float(first(b)),{r:float(e.constraint(r,x,b,eta,g)) for r in e.ROMAN}
    grid=np.linspace(np.log(dmin),np.log(dmax),grid_size)
    p0=profile(float(grid[0]));p1=profile(float(grid[-1]));special=[]
    if (p0[0]-1)*(p1[0]-1)<0:
        special=[brentq(lambda t:profile(float(t))[0]-1,grid[0],grid[-1],xtol=1e-12,rtol=1e-12)]
    output={}
    for variant in e.ROMAN:
        fun=lambda t:profile(float(t))[4][variant]
        roots=roots_with_extrema(fun,grid,special if variant=='III' else ())
        if not roots:
            output[variant]=(None,{'status':'no_root_in_declared_location_domain','variant':variant,
                                  'strategy':'profile_Brent_extrema_special_root','grid_size':grid_size})
            continue
        hi=15.0 if paper_domain else 9.99
        candidates=[profile(t) for t in roots];valid=[p for p in candidates if .1<p[0]<hi]
        if not valid:
            output[variant]=(None,{'status':'shape_outside_declared_domain',
                'candidate_shapes':[float(p[0]) for p in candidates],'roots_found':len(roots)})
            continue
        b,eta,g,r1,rr=valid[0];obj=float(r1*r1+rr[variant]*rr[variant])
        info=dict(status='ok' if obj<=1e-12 else 'equation_residual',objective=obj,
                  roots_found=len(roots),variant=variant,grid_size=grid_size,paper_domain=paper_domain,
                  strategy='profile_Brent_extrema_special_root')
        output[variant]=((float(b),float(eta),float(g)) if obj<=1e-12 else None,info)
    return output

@lru_cache(maxsize=4)
def fit_mme(values,grid_size=301):
    x=np.array(values);n=len(x);mean=x.mean();sd=x.std(ddof=1);c=np.log1p(1/n)
    try:reference=brentq(lambda b:e.theoretical_skew(b)-e.sample_skew(x),.100001,14.999999)
    except ValueError:reference=2.0
    grid=np.linspace(np.log(.100001),np.log(14.999999),grid_size);output={}
    for variant in e.ROMAN[:3]:
        def equation(logb):
            b=np.exp(logb);g1,var=e.moments(b)
            if variant=='I':q=c**(1/b);target=(mean-x.min())/sd
            elif variant=='II':q=g1*n**(-1/b);target=(mean-x.min())/sd
            else:q=np.log(2)**(1/b);target=(mean-np.median(x))/sd
            return (g1-q)/np.sqrt(var)-target
        roots=roots_with_extrema(equation,grid)
        if not roots:
            output[variant]=(None,{'status':'no_root_in_declared_shape_domain','variant':variant})
            continue
        candidates=[]
        for logb in roots:
            b=np.exp(logb);g1,var=e.moments(b);eta=sd/np.sqrt(var);g=mean-eta*g1
            candidates.append((float(b),float(eta),float(g)))
        valid=[p for p in candidates if 0<=p[2]<x.min()]
        selected=min(valid or candidates,key=lambda p:abs(np.log(p[0]/reference)))
        info=dict(status='ok' if valid else 'location_outside_effective_support',variant=variant,
            roots_found=len(roots),candidate_estimates=candidates,sample_moment_shape_initializer=float(reference),
            criterion_residual=float(equation(np.log(selected[0]))),
            strategy='moment_Brent_extrema_valid_support_then_sample_skew_initializer')
        output[variant]=(selected,info)
    return output

def activate():
    e.fit_mmle=fit_mmle;e.fit_mme=fit_mme;e.register()

def refinement_hash():return hashlib.sha256(Path(__file__).read_bytes()).hexdigest()

def run_block(args):
    n,block=args;dest=e.HERE/'refined_blocks'/f'n{n:02d}_block{block:02d}'
    original=json.loads((e.HERE/'blocks'/dest.name/'manifest.json').read_text(encoding='utf-8'))
    assert original['source_sha256']==e.source_hashes()
    marker=dest/'manifest.json';code_hash=refinement_hash()
    if marker.exists():
        previous=json.loads(marker.read_text(encoding='utf-8'))
        assert previous['refinement_sha256']==code_hash and previous['source_sha256']==e.source_hashes()
        return n,block,'existing'
    activate()
    run_experiment(METHODS,[tuple(e.CONFIG['truth'])],[n],100,str(dest),seed_namespace=e.namespace(block),
                   code_version=original['code_version'],run_label=f"{e.CONFIG['task_id']}:refined:n{n}:block{block}")
    record=json.loads(marker.read_text(encoding='utf-8'))
    record.update(source_sha256=e.source_hashes(),refinement_sha256=code_hash,block=block,
                  refinement='97/301point scan plus bounded local extrema; MMLE-III beta1 special root')
    marker.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
    return n,block,'complete'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--workers',type=int,default=6);args=parser.parse_args()
    jobs=[(n,b) for n in e.CONFIG['n_values'] for b in range(12)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for i,f in enumerate(as_completed([pool.submit(run_block,j) for j in jobs]),1):
            print(dict(finished=i,total=len(jobs),block=f.result()),flush=True)

if __name__=='__main__':main()
