"""Study01 WMLE root recovery, preserving the existing weights and constraints.

The shape equation is strictly decreasing at fixed location. Profile it out,
then bracket zeros of the remaining location equation. This fallback runs only
after the shared estimator rejects a candidate. It uses no true parameters.
"""
import numpy as np
from scipy.optimize import brentq, least_squares
from methods.wmle import get_weight_j1, get_weight_j2, get_weight_j3, SHAPE_UPPER
from studies.common.runner import run_method


def profile_recover(x, grid_size=513):
    x = np.sort(np.asarray(x, dtype=float))
    n, xmin = len(x), float(x.min())
    w2 = get_weight_j2(n)
    def residual(v):
        shape, loc = v
        z=x-loc
        logs=np.log(z)
        p=np.exp(shape*(logs-logs.max()))
        return [w2/shape+logs.mean()-np.dot(logs,p)/p.sum(),
                np.mean(1/z)*p.sum()/np.sum(p/z)-get_weight_j3(n,shape)]
    def at_location(loc):
        z = x-loc
        logs = np.log(z)
        def first(shape):
            p = np.exp(shape*(logs-logs.max()))
            return w2/shape + logs.mean()-np.dot(p,logs)/p.sum()
        if first(1e-4)*first(SHAPE_UPPER-.010001)>0:
            return None
        shape = brentq(first,1e-4,SHAPE_UPPER-.010001,xtol=1e-12)
        p = np.exp(shape*(logs-logs.max()))
        second = np.mean(1/z)*p.sum()/np.sum(p/z)-get_weight_j3(n,shape)
        return shape, float(second), float(first(shape))
    # Dense log-gap sweep includes gamma=0 and approaches the same open upper
    # support bound used in the production estimator.
    grid = xmin-np.geomspace(xmin, 1.00001e-6, grid_size)
    roots = []
    prev = None
    for loc in grid:
        point = at_location(loc)
        if point is None:
            prev = None
            continue
        if abs(point[1])<1e-10:
            roots.append((point[0],loc,point[1]**2+point[2]**2))
        if prev is not None and prev[1]*point[1]<0:
            root = brentq(lambda q: at_location(q)[1],prev[0],loc,xtol=1e-13)
            b,r2,r1 = at_location(root)
            roots.append((b,root,r1*r1+r2*r2))
        prev = (loc,point[1])
    # Tangent/near-zero minima may not produce a sign-changing bracket.
    if not roots:
        for b0,g0 in [(1.2,.8*xmin),(2,.3*xmin),(4,.9*xmin),(6,1e-10)]:
            fit=least_squares(residual,[b0,g0],bounds=([.01,0],[SHAPE_UPPER-.010001,xmin-1e-6]),
                              ftol=1e-12,xtol=1e-12,gtol=1e-12,max_nfev=2000)
            obj=float(np.sum(fit.fun**2))
            if obj<=1e-8:
                roots.append((fit.x[0],fit.x[1],obj))
                break
    roots = [p for p in roots if p[2]<=1e-8]
    if not roots:
        return None
    # Same sample-only proximity principle as the existing multistart solver.
    b,g,resid = min(roots,key=lambda p: np.log(p[0]/2)**2+((p[1]-.9*xmin)/max(xmin,1))**2)
    logz=np.log(x-g)
    logeta=(np.log(np.exp(b*(logz-logz.max())).mean()/get_weight_j1(n))/b+logz.max())
    return {'beta_hat':float(b),'eta_hat':float(np.exp(logeta)),'gamma_hat':float(g),
            'converged':True,'r_squared':None,'extra':{'solution_info':{
                'status':'ok','strategy':'profile_root_recovery','objective':float(resid),
                'roots_found':len(roots),'grid_size':grid_size}}}


def run_wmle_checked(x):
    result = run_method('wmle',x)
    if result['converged']:
        return result
    recovered = profile_recover(x)
    return recovered if recovered is not None else result
