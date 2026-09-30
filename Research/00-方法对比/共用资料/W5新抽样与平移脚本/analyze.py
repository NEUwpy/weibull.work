"""Read-only diagnostic on historical W5 workbooks; no workbook changes."""
import json
import math
import sys
from pathlib import Path
import numpy as np
from openpyxl import load_workbook

ROOT = Path('D:/weibull')
SOURCE = ROOT / 'docs/临时任务/临时任务-W2-1000-3000-MDM偏移量估计-20260825/260906-W5参数估计案例'

def golden(f, lo=.1, hi=15., tol=1e-7):
    q = (math.sqrt(5)-1)/2
    c, d = hi-q*(hi-lo), lo+q*(hi-lo)
    fc, fd = f(c), f(d)
    while hi-lo > tol:
        if fc < fd:
            hi,d,fd=d,c,fc
            c=hi-q*(hi-lo); fc=f(c)
        else:
            lo,c,fc=c,d,fd
            d=lo+q*(hi-lo); fd=f(d)
    x=(lo+hi)/2
    return x, f(x)

def bisect(f, lo, hi, steps=55):
    fl=f(lo)
    assert fl*f(hi) <= 0
    for _ in range(steps):
        m=(lo+hi)/2; fm=f(m)
        if fl*fm<=0: hi=m
        else: lo=m; fl=fm
    return (lo+hi)/2

def mdm_profile(x,g):
    n=len(x); z=-np.log1p(-(np.arange(1,n+1)-.3)/(n+.4))
    a,s=golden(lambda a: float(np.std((x-g)/z**(1/a),ddof=1)))
    return a,float(np.mean((x-g)/z**(1/a))),s

def shape_eq(x,g,j2):
    l=np.log(x-g); l=l-l.max()
    def f(a):
        w=np.exp(a*l)
        return float(a*(np.dot(w,l)/w.sum()-l.mean())-j2)
    return bisect(f,.01,100)

j3raw=np.loadtxt(ROOT/'python/methods/j3_weights.tsv')
def j3(n,a):
    vals=j3raw[j3raw[:,0]==n]
    return float(np.interp(a,vals[:,1],vals[:,2]))

def second_eq(x,g,a):
    y=x-g; z=y/y.max()
    return float(np.mean(1/z)*np.sum(z**a)/np.sum(z**(a-1))-j3(len(x),a))

def roots(x,j2):
    # Dense deterministic independent 1D scan, shape eliminated with its unique root.
    grid=np.unique(np.r_[np.linspace(0,x[0]*(1-1e-8),401),x[0]*(1-np.geomspace(1e-10,1,150))])
    def f(g): return second_eq(x,g,shape_eq(x,g,j2))
    fs=[f(g) for g in grid]
    out=[]
    for i in range(len(grid)-1):
        if fs[i]*fs[i+1]<0:
            g=bisect(f,grid[i],grid[i+1],40); a=shape_eq(x,g,j2)
            if .1<a<9.99 and (not out or abs(g-out[-1][1])>1e-3): out.append([a,g])
    return out

def stats(v):
    return {'mean':float(np.mean(v)),'median':float(np.median(v)),'min':float(np.min(v)),'max':float(np.max(v))}

for truth in [500,3000]:
    path=SOURCE/f'W(5,1000,{truth})'/f'5,1000,{truth}.xlsx'
    wb=load_workbook(path,read_only=True,data_only=True)
    for n in [7,15]:
        sx=wb[f'生成样本_n{n}']; sr=wb[f'估计结果_n{n}']
        # Materialize read-only sheets once; avoid repeated streaming cell access.
        xr=list(sx.values); rr=list(sr.values)
        print('HEADERS',truth,n,xr[0],rr[2],rr[3],flush=True)
        xs=[np.array(r[1:n+1],float) for r in xr[1:51]]
        assert len(xs)==50 and all(len(x)==n and np.all(np.diff(x)>=0) for x in xs)
        old_mdm=np.array([r[1:4] for r in rr[4:54]],float)
        fixed=np.array([mdm_profile(x,truth) for x in xs])
        j2={7:.792,15:.901}[n]
        inds=[i for i in range(50) if isinstance(rr[i+4][10],(int,float)) and rr[i+4][10]>0]
        old_w=np.array([rr[i+4][10:13] for i in inds],float)
        fixed_w=[shape_eq(xs[i],truth,j2) for i in inds]
        out={'truth':truth,'n':n,'min_sample_mean':np.mean([x[0] for x in xs]),
             'MDM_joint_shape':stats(old_mdm[:,0]),'MDM_fixed_shape':stats(fixed[:,0]),
             'WMLE_count':len(inds),'WMLE_joint_shape':stats(old_w[:,0]),'WMLE_fixed_shape':stats(fixed_w),
             'WMLE_fixed_unweighted_shape':stats([shape_eq(xs[i],truth,1.) for i in inds]),
             'MDM_profile_at_stored_gamma_max_shape_error':max(abs(mdm_profile(x,g)[0]-a) for x,(a,b,g) in zip(xs,old_mdm)),
             'WMLE_stored_max_first_residual':max(abs(shape_eq(xs[i],g,j2)-a) for i,(a,b,g) in zip(inds,old_w))}
        true_grad=[]
        for x in xs:
            h=x[0]*1e-5
            true_grad.append((mdm_profile(x,truth+h)[2]-mdm_profile(x,truth-h)[2])/(2*h))
        out['gradient_at_true_location']=stats(true_grad)
        out['gradient_at_true_location_below_0.1']=int(sum(g<.1 for g in true_grad))
        out['WMLE_stored_max_second_residual']=max(abs(second_eq(xs[i],g,a)) for i,(a,b,g) in zip(inds,old_w))
        for offset,row0 in [(.1,4),(.15,62),(.2,120)]:
            out[f'MDM_{offset}']=np.mean(np.array([r[1:4] for r in rr[row0:row0+50]],float),axis=0).tolist()
        print('SUMMARY',json.dumps(out),flush=True)
        if '--summary' in sys.argv:
            continue
        # Representative first five, plus locations closest to median stored MDM shape.
        ii=list(dict.fromkeys([0,1,2,3,4,int(np.argmin(abs(old_mdm[:,0]-np.median(old_mdm[:,0]))))]))
        for i in ii:
            x=xs[i]; h=x[0]*1e-5
            grad=lambda g:(mdm_profile(x,g+h)[2]-mdm_profile(x,max(0,g-h))[2])/(h if g==0 else 2*h)
            stationary=None
            if grad(0)<0 and grad(x[0]*.999)>0:
                g0=bisect(grad,0,x[0]*.999,35)
                stationary=[*mdm_profile(x,g0)[:2],g0]
            print('EXAMPLE',json.dumps({'truth':truth,'n':n,'id':i+1,'samples':x.tolist(),
                'mdm':old_mdm[i].tolist(),'stationary_delta0':stationary,
                'profile_truth':mdm_profile(x,truth),'gradient_truth':grad(truth),
                'wmle_stored':list(rr[i+4][10:13]),'wmle_roots':roots(x,j2)}),flush=True)
    wb.close()
print('EXPECTED_MIN',[(n,500+1000*math.gamma(1.2)/n**.2) for n in [7,15]])
