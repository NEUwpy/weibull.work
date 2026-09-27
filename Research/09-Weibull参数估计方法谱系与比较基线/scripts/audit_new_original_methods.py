"""Targeted numerical audit, not a performance benchmark or production estimator.

Run with python/.venv/Scripts/python.exe. DMMLE input is the pinned author
notebook downloaded separately; its R code is read as data, never executed.
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.stats import weibull_min


def park():
    x = np.sort([30.94,18.51,16.62,51.56,22.85,22.38,19.08,49.56,
                 17.12,10.67,25.43,10.24,27.47,14.70,14.10,29.93,
                 27.98,36.02,19.40,14.97,22.57,12.26,18.14,18.84])
    z = np.log(-np.log1p(-(np.arange(1,25)-.5)/24))
    fit = minimize_scalar(lambda g: -np.corrcoef(np.log(x-g),z)[0,1],
                          bounds=(0, np.nextafter(x[0],0)), method='bounded',
                          options={'xatol':1e-12})
    g = fit.x
    b,a = np.polyfit(np.log(x-g),z,1)
    beta,_,eta = weibull_min.fit(x-g, floc=0)
    estimates = {'Plot':[g,b,np.exp(-a/b)], 'MLE2':[g,beta,eta]}
    target = {'Plot':[9.198,1.363,15.116], 'MLE2':[9.198,1.359,15.076]}
    return {'data':x.tolist(), 'parameter_order':['gamma','beta','eta'],
            'estimates':estimates, 'table1':target,
            'within_printed_rounding':{k:bool(np.all(np.abs(np.array(v)-target[k])<.0005)) for k,v in estimates.items()},
            'correlation':-fit.fun}


def dm_quantities(p, y):
    a,s = p
    m = len(y)
    l = np.log(y)
    sums = [np.sum(y**a*l**k) for k in range(4)]
    q,q1,q2,q3 = sums
    score = np.array([m/a+l.sum()-q1/s, -m/s+q/s**2])
    info = np.array([[m/a**2+q2/s,-q1/s**2],[-q1/s**2,2*q/s**3-m/s**2]])
    ia = np.array([[q3/s-2*m/a**3,-q2/s**2],[-q2/s**2,2*q1/s**3]])
    iss = np.array([[-q2/s**2,2*q1/s**3],[2*q1/s**3,2*m/s**3-6*q/s**4]])
    adjusted = score + .5*np.array([np.trace(np.linalg.solve(info,d)) for d in [ia,iss]])
    return adjusted, info, [ia,iss]


def dmmle(x, maxiter=20):
    g = min(x)
    y = np.delete(x,np.argmin(x))-g
    if np.any(y<=0):
        return {'status':'nonpositive_shift_after_removing_one_minimum'}
    p = np.ones(2)
    for iteration in range(1,maxiter+1):
        if np.any(p<=0):
            return {'status':'nonpositive_iterate','iterations':iteration}
        u,info,_ = dm_quantities(p,y)
        new = p+np.linalg.solve(info,u)
        tolerance = np.sum(np.abs(new-p)/np.abs(p))
        p = new
        if tolerance<1e-8:
            break
    u,info,derivatives = dm_quantities(p,y)
    errors=[]
    for j in range(2):
        h=1e-5*max(1,abs(p[j]))
        step=np.eye(2)[j]*h
        numeric=(dm_quantities(p+step,y)[1]-dm_quantities(p-step,y)[1])/(2*h)
        errors.append(float(np.max(np.abs(numeric-derivatives[j]))))
    return {'status':'converged' if tolerance<1e-8 and np.max(np.abs(u))<1e-6 else 'not_verified_converged',
            'gamma':float(g),'alpha':p[0],'sigma':p[1],'eta':p[1]**(1/p[0]),
            'iterations':iteration,'adjusted_score_max_abs':float(np.max(np.abs(u))),
            'information_derivative_max_abs_errors':errors}


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('notebook',type=Path)
    args=parser.parse_args()
    raw=args.notebook.read_bytes()
    digest=hashlib.sha256(raw).hexdigest()
    assert digest=='a50f5424d8db6da37335fc1c79e261861fdb80d1b934be696576b6e7a191cca3'
    cells=json.loads(raw)['cells']
    source='\n'.join(''.join(c['source']) for c in cells)
    out={'scope':'Independent Python transcription compared with stored author R outputs; R not executed; not Monte Carlo validation',
         'author_commit':'e733f90ee86351915037130deefa9d39e7e7506c','notebook_sha256':digest,
         'author_url':'https://github.com/FSQuintino/dmmle_Weibull/tree/e733f90ee86351915037130deefa9d39e7e7506c',
         'park2017':park(), 'dmmle2025':{}}
    for name,expected in [('invest',[.5653819,1.4984826,5.012]),('gauge',[2.342260,1.714474,1.312])]:
        match=re.search(r'data_'+name+r'\s*=\s*c\((.*?)\)',source,re.S)
        x=np.array([float(v) for v in match.group(1).split(',')])
        result=dmmle(x)
        result.update(n=len(x),data=x.tolist(),author_output_alpha_sigma_gamma=expected,
                      matches_stored_output=bool(np.allclose([result['alpha'],result['sigma'],result['gamma']],expected,atol=5e-7,rtol=0)))
        out['dmmle2025'][name]=result
    out['dmmle2025']['tied_minimum_check']=dmmle(np.array([1.,1.,2.,3.]))
    destination=Path(__file__).resolve().parents[1]/'evidence/new_original_methods_audit.json'
    destination.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in out.items() if k not in ['park2017','dmmle2025']}))
    print('Park:',out['park2017']['estimates'],out['park2017']['within_printed_rounding'])
    print('DMMLE:',{k:{a:b for a,b in v.items() if a!='data'} for k,v in out['dmmle2025'].items()})


if __name__=='__main__':
    main()
