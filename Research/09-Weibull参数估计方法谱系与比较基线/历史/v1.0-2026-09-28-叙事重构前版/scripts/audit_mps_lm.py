"""Isolated complete-data 3P Weibull MPS and unbiased sample L-moments.

Research implementations, not platform registrations. MPS is a bounded,
multi-start numerical version; LM is unconstrained with domain flags.
"""
import json
from pathlib import Path
import numpy as np
from scipy.optimize import brentq, minimize
from scipy.special import gammaln
from scipy.integrate import quad


def tau3(k):
    return 3-2*np.expm1(-k*np.log(3))/np.expm1(-k*np.log(2))


def lm_from_moments(l1,l2,l3):
    tau=l3/l2
    lower=3-2*np.log(3)/np.log(2)
    if not lower<tau<1:
        return {'status':'no_finite_shape_for_sample_lskewness','lskewness':float(tau),'lower_bound':float(lower)}
    k=brentq(lambda k:tau3(k)-tau,1e-7,100,xtol=1e-13)
    eg=l2/(-np.expm1(-k*np.log(2)))
    eta=eg*np.exp(-gammaln(1+k)); gamma=l1-eg
    return {'status':'estimated','beta':1/k,'eta':float(eta),'gamma':float(gamma),'lskewness':float(tau)}


def fit_lm(data):
    x=np.sort(np.asarray(data,float)); n=len(x)
    if n<3 or not np.isfinite(x).all() or np.ptp(x)==0:return {'status':'invalid_input'}
    i=np.arange(n)
    b0=x.mean(); b1=np.mean(i/(n-1)*x); b2=np.mean(i*(i-1)/((n-1)*(n-2))*x)
    r=lm_from_moments(b0,2*b1-b0,6*b2-6*b1+b0)
    if r['status']=='estimated':
        r['nonnegative_location']=bool(r['gamma']>=0)
        r['all_observations_in_support']=bool(r['gamma']<x[0])
    return r


def spacing_loss(params,x):
    b,eta,g=params
    if b<=0 or eta<=0 or g>=x[0]:return 1e100
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        z=((x-g)/eta)**b
        logd=np.r_[np.log(-np.expm1(-z[0])), -z[:-1]+np.log(-np.expm1(-np.diff(z))),-z[-1]]
    return float(-logd.mean()) if np.isfinite(logd).all() else 1e100


def fit_mps(data):
    x=np.sort(np.asarray(data,float))
    if len(x)<3 or not np.isfinite(x).all() or x[0]<=0:return {'status':'invalid_input'}
    if np.any(np.diff(x)==0):return {'status':'ties_zero_spacing'}
    unit=np.median(x); u=x/unit
    bounds=[(np.log(.05),np.log(50)),(-8,8),(0,float(u[0]*(1-1e-10)))]
    def unpack(v):return np.array([np.exp(v[0]),np.exp(v[1]),v[2]])
    def objective(v):return spacing_loss(unpack(v),u)
    candidates=[]
    for b,gfrac in [(.5,.9),(1,.5),(2,0),(2,.8),(5,0),(5,.8)]:
        g=gfrac*u[0]; eta=(u.mean()-g)/np.exp(gammaln(1+1/b))
        start=np.array([np.log(b),np.clip(np.log(eta),-8,8),g])
        r=minimize(objective,start,method='Nelder-Mead',bounds=bounds,
                   options={'maxiter':2500,'xatol':1e-9,'fatol':1e-11})
        if r.success and np.isfinite(r.fun) and r.fun<1e90:candidates.append(r)
    if not candidates:return {'status':'search_failed'}
    best=min(candidates,key=lambda r:r.fun); b,e,g=unpack(best.x)
    artificial_boundary=bool(any(abs(best.x[j]-v)<1e-5 for j in [0,1] for v in bounds[j]) or abs(best.x[2]-bounds[2][1])<1e-8)
    return {'status':'numerical_boundary' if artificial_boundary else 'estimated',
            'beta':float(b),'eta':float(e*unit),'gamma':float(g*unit),
            'mean_negative_log_spacing':float(best.fun),'converged_starts':len(candidates),
            'near_best_starts':int(sum(abs(r.fun-best.fun)<1e-7 for r in candidates)),
            'gamma_zero_boundary':bool(g<1e-8),'unit':float(unit)}


def main():
    data={'example1':[90.4,94.2,97.8,101.8,104.6,113,118,154.9,181.3,186.2],
          'example2':[17.88,28.92,33,41.52,42.12,45.6,48.48,51.84,51.96,54.12,55.56,67.8,68.64,68.64,68.88,84.12,93.12,98.64,105.12,105.84,127.92,128.04,173.4]}
    targets={'example1':{'LM':[.95,37.96,85.34],'MPS':[.8,37.11,88.44]},
             'example2':{'LM':[1.44,60.13,17.65],'MPS':[1.61,72.87,8.65]}}
    out={'source':'182-096 section 3.1 and Table 10; 182-116 MPS definition',
         'protocol':{'MPS':'nonnegative gamma; median scaling; beta [.05,50]; eta/median [exp(-8),exp(8)]; gamma < min; six fixed starts; no jitter for ties',
                     'LM':'unbiased b0,b1,b2; solve exact L-skewness equation; retain unconstrained estimate and flag domain violations'},
         'examples':{},'checks':{}}
    for name,x in data.items():
        out['examples'][name]={'data':x,'paper_table_beta_eta_gamma':targets[name]}
        for method,fn in [('LM',fit_lm),('MPS',fit_mps)]:
            r=fn(x)
            if 'beta' in r:
                r['within_table_rounding']=bool(np.all(np.abs(np.array([r['beta'],r['eta'],r['gamma']])-targets[name][method])<.005))
            out['examples'][name][method]=r
    # Independent population quadrature checks the parameter reconstruction.
    errors=[]
    for b in [.5,1,2,5,9]:
        q=lambda f:3+2*(-np.log1p(-f))**(1/b)
        ls=[quad(lambda f:q(f)*poly(f),0,1,epsabs=1e-8)[0]
            for poly in [lambda f:1,lambda f:2*f-1,lambda f:6*f*f-6*f+1]]
        r=lm_from_moments(*ls)
        errors.append(float(np.max(np.abs(np.array([r['beta'],r['eta'],r['gamma']])-[b,2,3]))))
    out['checks']['LM_population_quadrature_max_parameter_error']=max(errors)
    pars=[1.7,2,1]; x=np.array([1.2,1.5,2,3,4])
    f=1-np.exp(-((x-1)/2)**1.7)
    out['checks']['MPS_log_formula_difference']=abs(spacing_loss(pars,x)+np.log(np.diff(np.r_[0,f,1])).mean())
    out['checks']['LM_no_finite_shape_example']={'data':[1,10,11],'result':fit_lm([1,10,11])}
    out['checks']['scale_equivariance']={}
    for name,fn in [('LM',fit_lm),('MPS',fit_mps)]:
        r=fn(np.array(data['example1'])*1000); a=out['examples']['example1'][name]
        out['checks']['scale_equivariance'][name]=float(np.max(np.abs(np.array([r['beta'],r['eta']/1000,r['gamma']/1000])-[a['beta'],a['eta'],a['gamma']])))
    dest=Path(__file__).resolve().parents[1]/'evidence/mps_lm_audit.json'
    dest.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
