"""Check all 62 WMLE failures with scalar elimination; identical weights and constraints."""
import json
from pathlib import Path
import sys

import numpy as np
from scipy.optimize import brentq
from scipy.special import logsumexp

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'程序/复核与LRE对比'
sys.path.insert(0,str(ROOT/'程序/W(5,1000,500)/依赖快照/python'))
from methods.wmle import get_weight_j1,get_weight_j2,get_weight_j3


def diagnose(t,n):
    w1,w2=get_weight_j1(n),get_weight_j2(n)
    def conditional(g):
        x=t-g;logs=np.log(x)
        def shape_score(b):
            weights=np.exp(b*logs-logsumexp(b*logs))
            return w2/b+logs.mean()-np.dot(weights,logs)
        lo,hi=1e-4,9.989999
        if shape_score(lo)*shape_score(hi)>0:return None
        b=brentq(shape_score,lo,hi,xtol=1e-12)
        second=float(np.mean(1/x)*np.exp(logsumexp(b*logs)-logsumexp((b-1)*logs))-get_weight_j3(n,b))
        return b,second,float(shape_score(b))
    minimum=float(t[0]);gap=1.0001e-6
    grid=np.unique(np.concatenate([np.linspace(0,minimum-gap,201),minimum-np.geomspace(gap,minimum,301)]))
    values=[conditional(float(g)) for g in grid]
    roots=[]
    for i in range(len(grid)-1):
        a,z=values[i],values[i+1]
        if a is None or z is None or a[1]*z[1]>0:continue
        root=brentq(lambda g:conditional(g)[1],float(grid[i]),float(grid[i+1]),xtol=1e-10)
        b,term2,term1=conditional(root)
        residual=term1**2+term2**2
        e=float(np.exp((logsumexp(b*np.log(t-root))-np.log(n*w1))/b))
        if residual<=1e-12 and 0<b<9.99 and 0<=root<minimum-1e-6:
            raw_x=t-root; raw_power=raw_x**b
            direct1=w2/b+np.log(raw_x).mean()-np.sum(np.log(raw_x)*raw_power)/np.sum(raw_power)
            direct2=np.mean(1/raw_x)*np.sum(raw_power)/np.sum(raw_x**(b-1))-get_weight_j3(n,b)
            direct_residual=float(direct1**2+direct2**2)
            assert direct_residual<=1e-12
            roots.append(dict(beta=b,eta=e,gamma=root,squared_residual=residual,term1=term1,term2=term2,
                              direct_production_formula_squared_residual=direct_residual))
    return roots


if __name__=='__main__':
    records=[]
    for case in sorted((ROOT/'程序').glob('W(*)')):
        raw=json.loads((case/'中间数据/results.json').read_text(encoding='utf-8'))
        samples={(s['n'],s['id']):np.asarray(s['values']) for s in raw['samples']}
        for r in raw['results']:
            if r['method_id']!='wmle' or r['converged']:continue
            roots=diagnose(samples[r['n'],r['id']],r['n'])
            records.append(dict(distribution=case.name,n=r['n'],id=r['id'],
                                original_solution_info=r['extra']['solution_info'],admissible_roots=roots))
        print(case.name,'checked',len(records),'roots found',sum(bool(r['admissible_roots']) for r in records),flush=True)
    assert len(records)==62
    (OUT/'WMLE失败根核查.json').write_text(json.dumps(dict(method='eliminate shape score then bracket location equation',
       beta_range=[.0001,9.989999],minimum_location_gap=1.0001e-6,grid_points_before_deduplication=502,
       failure_records_checked=62,admissible_roots_found=sum(bool(r['admissible_roots']) for r in records),records=records),
       ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
