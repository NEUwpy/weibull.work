"""Fixed-truth comparison; extends the preceding shared-pipeline experiment."""
from __future__ import annotations
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from scipy.optimize import brentq
from scipy.special import gammaln, logsumexp

HERE=Path(__file__).resolve().parent
REPO=next(p for p in HERE.parents if (p/'python/methods/wmle.py').exists())
PRIOR=HERE.parent/'20261005-MMLEI与WMLE比较'
sys.path.insert(0,str(PRIOR))
import run as prior
from base import WeibullBase
from methods.registry import IMPLEMENTED
from studies.common.experiment import run_experiment
from studies.common.runner import run_method

CONFIG=json.loads((HERE/'config.json').read_text(encoding='utf-8'))
ROMAN=['I','II','III','IV','V']
LABELS={'mle_local':'MLE（有限局部解）','wmle_checked':'WMLE（含漏解复核）'}
LABELS.update({f'mmle_{r.lower()}':f'MMLE-{r}（非负位置）' for r in ROMAN})
LABELS.update({f'mmle_{r.lower()}_paper':f'MMLE-{r}（原文参数域）' for r in ROMAN})
LABELS.update({f'mme_{r.lower()}':f'MME-{r}（有效支持域）' for r in ROMAN[:3]})
METHODS=['mle_local']+[f'mmle_{r.lower()}' for r in ROMAN]+['wmle_checked']+[
         f'mme_{r.lower()}' for r in ROMAN[:3]]+[f'mmle_{r.lower()}_paper' for r in ROMAN]


def namespace(block):
    base=CONFIG['base_seed_namespace']
    return base if block==0 else f'{base}:research09-versions:block{block:02d}'


def moments(b):
    l1=float(gammaln(1+1/b))
    l2=float(gammaln(1+2/b))
    g1=np.exp(l1)
    variance=np.exp(2*l1)*np.expm1(l2-2*l1)
    return g1,float(variance)


def constraint(which,x,b,e,g):
    n=len(x)
    g1,var=moments(b)
    if which=='I':
        return b*np.log(x[0]-g)-b*np.log(e)-np.log(np.log1p(1/n))
    if which=='II':
        return np.log(e)+np.log(g1)-np.log(n)/b-np.log(x[0]-g)
    if which=='III':
        return (g+e*g1-x.mean())/x.std(ddof=1)
    if which=='IV':
        return 2*np.log(e)+np.log(var)-np.log(x.var(ddof=1))
    if which=='V':
        return (g+e*np.log(2)**(1/b)-np.median(x))/x.std(ddof=1)
    raise ValueError(which)


@lru_cache(maxsize=4)
def fit_mmle(values,paper_domain=False,grid_size=97):
    x=np.sort(np.array(values))
    xmin=float(x[0])
    lower=float(x.mean()-10*x.std(ddof=1)) if paper_domain else 0.0
    dmax=xmin-lower
    dmin=1e-7  # fixed1000 conversion of original-unit gap1e-4
    if dmax<=dmin:return {r:(None,{'status':'empty_location_domain'}) for r in ROMAN}
    delta=x-xmin
    @lru_cache(maxsize=512)
    def profile(logd):
        d=np.exp(logd)
        logs=np.log1p(delta/d)
        def first(b):
            p=np.exp(b*(logs-logs.max()))
            return b*(np.dot(p,logs)/p.sum()-logs.mean())-1
        hi=2.0
        while first(hi)<0 and hi<1e7:hi*=2
        if first(hi)<0:raise ArithmeticError('profile_numerical_range')
        b=brentq(first,1e-7,hi,xtol=1e-12,rtol=1e-12)
        g=xmin-d
        eta=float(np.exp((logsumexp(b*np.log(x-g))-np.log(len(x)))/b))
        residuals={r:float(constraint(r,x,b,eta,g)) for r in ROMAN}
        return b,eta,g,float(first(b)),residuals
    grid=np.linspace(np.log(dmin),np.log(dmax),grid_size)
    points=[profile(float(t)) for t in grid]
    output={}
    for r in ROMAN:
        roots=[]
        for i,(t,p) in enumerate(zip(grid,points)):
            if abs(p[4][r])<1e-11:roots.append((t,p))
            if i and points[i-1][4][r]*p[4][r]<0:
                troot=brentq(lambda z:profile(float(z))[4][r],grid[i-1],t,xtol=1e-12,rtol=1e-12)
                roots.append((troot,profile(float(troot))))
        if not roots:
            output[r]=(None,{'status':'no_root_in_declared_location_domain',
                            'variant':r,'grid_size':grid_size})
            continue
        hi=15.0 if paper_domain else 9.99
        admissible=[p for _,p in roots if .1<p[0]<hi]
        if not admissible:
            output[r]=(None,{'status':'shape_outside_declared_domain',
                            'candidate_shapes':[float(p[0]) for _,p in roots]})
            continue
        b,e,g,r1,rr=admissible[0]
        obj=r1*r1+rr[r]*rr[r]
        info={'status':'ok' if obj<=1e-12 else 'equation_residual','objective':obj,
              'roots_found':len(roots),'variant':r,'grid_size':grid_size,
              'strategy':'CW_profile_Brent','paper_domain':paper_domain}
        output[r]=((float(b),float(e),float(g)) if obj<=1e-12 else None,info)
    return output


def sample_skew(x):
    return float(np.mean((x-x.mean())**3)/x.std(ddof=1)**3)


def theoretical_skew(b):
    g1,v=moments(b)
    g2=np.exp(gammaln(1+2/b))
    g3=np.exp(gammaln(1+3/b))
    return float((g3-3*g2*g1+2*g1**3)/v**1.5)


@lru_cache(maxsize=4)
def fit_mme(values,grid_size=301):
    x=np.array(values)
    n=len(x);mean=x.mean();sd=x.std(ddof=1);c=np.log1p(1/n)
    target_skew=sample_skew(x)
    try:reference=brentq(lambda b:theoretical_skew(b)-target_skew,.100001,14.999999)
    except ValueError:reference=2.0
    grid=np.geomspace(.100001,14.999999,grid_size)
    output={}
    for r in ROMAN[:3]:
        def equation(b):
            g1,var=moments(b)
            if r=='I':q=c**(1/b);target=(mean-x.min())/sd
            elif r=='II':q=g1*n**(-1/b);target=(mean-x.min())/sd
            else:q=np.log(2)**(1/b);target=(mean-np.median(x))/sd
            return (g1-q)/np.sqrt(var)-target
        vals=[equation(b) for b in grid]
        roots=[]
        for i in range(1,len(grid)):
            if vals[i-1]*vals[i]<0:
                roots.append(brentq(equation,grid[i-1],grid[i],xtol=1e-12,rtol=1e-12))
        if not roots:
            output[r]=(None,{'status':'no_root_in_declared_shape_domain','variant':r})
            continue
        candidates=[]
        for b in roots:
            g1,var=moments(b);e=sd/np.sqrt(var);g=mean-e*g1
            candidates.append((float(b),float(e),float(g)))
        # Do not select with the true beta. Prefer model-valid solutions, then
        # closest to the sample-skew moment initializer (paper TableI guidance).
        valid=[p for p in candidates if 0<=p[2]<x.min()]
        selected=min(valid or candidates,key=lambda p:abs(np.log(p[0]/reference)))
        info={'status':'ok' if valid else 'location_outside_effective_support',
              'variant':r,'roots_found':len(roots),'candidate_estimates':candidates,
              'sample_moment_shape_initializer':float(reference),
              'criterion_residual':float(equation(selected[0])),
              'strategy':'CW_moment_Brent_valid_support_then_sample_skew_initializer'}
        output[r]=(selected,info)
    return output


class GenericMMLE(WeibullBase):
    which='II';paper_domain=False
    def run(self):
        fitted,self.last_solution_info=fit_mmle(tuple(self.data/1000),self.paper_domain)[self.which]
        if fitted is None:return [None,None,None,float('nan'),False]
        b,e,g=fitted
        return [b,e*1000,g*1000,float('nan'),True]


class GenericMME(WeibullBase):
    which='I'
    def run(self):
        fitted,self.last_solution_info=fit_mme(tuple(self.data/1000))[self.which]
        if fitted is None:return [None,None,None,float('nan'),False]
        b,e,g=fitted
        return [b,e*1000,g*1000,float('nan'),self.last_solution_info['status']=='ok']


class MLELocal(WeibullBase):
    def run(self):
        result=run_method('mle',self.data/1000)
        extra=result.get('extra') or {}
        self.last_solution_info=extra.get('solution_info',{}).copy()
        if not result['converged']:
            self.last_solution_info.setdefault('status',extra.get('raw_status','optimizer_failed'))
            return [result['beta_hat'],None,None,0.0,False] if result['beta_hat'] is None else [
                result['beta_hat'],(result['eta_hat'] or 0)*1000,(result['gamma_hat'] or 0)*1000,0.0,False]
        return [result['beta_hat'],result['eta_hat']*1000,result['gamma_hat']*1000,
                result['r_squared'],True]


def register():
    IMPLEMENTED.update(mle_local=MLELocal,wmle_checked=prior.WMLEChecked,
                       mmle_i=prior.CWNonnegative,mmle_i_paper=prior.CWPaperDomain)
    for r in ROMAN[1:]:
        IMPLEMENTED[f'mmle_{r.lower()}']=type(f'MMLE{r}',(GenericMMLE,),{'which':r})
        IMPLEMENTED[f'mmle_{r.lower()}_paper']=type(f'MMLE{r}Paper',(GenericMMLE,),{'which':r,'paper_domain':True})
    for r in ROMAN[:3]:
        IMPLEMENTED[f'mme_{r.lower()}']=type(f'MME{r}',(GenericMME,),{'which':r})


def source_hashes():
    paths=[HERE/'experiment.py',HERE/'config.json',PRIOR/'run.py',PRIOR/'config.json',
           REPO/'python/methods/mle.py',REPO/'python/methods/wmle.py',REPO/'python/methods/j3_weights.tsv',
           REPO/'python/studies/common/sample.py',REPO/'python/studies/common/runner.py',
           REPO/'python/studies/common/experiment.py',REPO/'python/studies/common/metrics.py',
           prior.E09/'wmle_solver.py']
    return {str(p.relative_to(REPO)).replace('\\','/'):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}


def run_block(args):
    n,block,out,hashes,commit=args
    dest=Path(out)/f'n{n:02d}_block{block:02d}'
    marker=dest/'manifest.json'
    if marker.exists():
        old=json.loads(marker.read_text(encoding='utf-8'))
        if old.get('source_sha256')!=hashes:raise RuntimeError(f'checkpoint mismatch {dest}')
        return n,block,'existing'
    register()
    run_experiment(METHODS,[tuple(CONFIG['truth'])],[n],CONFIG['repeats_per_block'],str(dest),
        seed_namespace=namespace(block),code_version=commit,run_label=f"{CONFIG['task_id']}:n{n}:block{block}")
    record=json.loads(marker.read_text(encoding='utf-8'))
    record.update(source_sha256=hashes,block=block,contract=CONFIG)
    marker.write_text(json.dumps(record,indent=2,ensure_ascii=False),encoding='utf-8')
    return n,block,'complete'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--n',type=int)
    parser.add_argument('--block',type=int)
    parser.add_argument('--output',type=Path,default=HERE/'blocks')
    args=parser.parse_args()
    hashes=source_hashes()
    commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=REPO,text=True).strip()
    jobs=[(n,b,str(args.output),hashes,commit) for n in CONFIG['n_values']
          for b in range(CONFIG['blocks']) if (args.n is None or args.n==n) and (args.block is None or args.block==b)]
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for count,future in enumerate(as_completed([pool.submit(run_block,j) for j in jobs]),1):
            print({'finished':count,'total':len(jobs),'block':future.result()},flush=True)
    if hashes!=source_hashes():raise RuntimeError('source changed during experiment')


if __name__=='__main__':main()
