"""SAM 2023 PDF equations 23--30 and initial adjustment, isolated audit."""
import json
from pathlib import Path
import numpy as np
from scipy.special import gammaln, logsumexp


def fit_sam(data, eps=1e-5, maxiter=10000, signed_stop=False):
    t=np.sort(np.asarray(data,dtype=float)); n=len(t)
    if n<3 or t[0]<=0 or np.ptp(t)==0:
        return {'status':'invalid_input'}
    z=np.log(-np.log1p(-(np.arange(1,n+1)-.3)/(n+.4)))
    def slope(g):
        x=np.log(t-g); xc=x-x.mean()
        return float(xc@(z-z.mean())/(xc@xc))
    b=slope(0); eta=np.exp(np.log(t).mean()-z.mean()/b); g=0.
    adjustment=0
    while t[0]-eta*np.exp(gammaln(1+1/b)-np.log(n)/b)<=0:
        eta*=.99; adjustment+=1
        if adjustment>=maxiter:return {'status':'initial_adjustment_budget'}
    decreases=0
    for it in range(1,maxiter+1):
        newg=t[0]-eta*np.exp(gammaln(1+1/b)-np.log(n)/b)
        if not 0<newg<t[0]:return {'status':'location_outside_domain','iterations':it,
            'attempted_gamma':float(newg),'last_gamma':float(g),
            'decreasing_updates':decreases,'initial_adjustments':adjustment}
        neweta=np.exp((logsumexp(b*np.log(t-newg))-np.log(n))/b)
        newb=slope(newg)
        delta=newg-g
        decreases+=int(delta<0)
        g,eta,b=newg,neweta,newb
        if (delta if signed_stop else abs(delta))<=eps:break
    else:
        return {'status':'iteration_budget','iterations':maxiter}
    fixed_g=t[0]-eta*np.exp(gammaln(1+1/b)-np.log(n)/b)
    return {'status':'converged' if abs(fixed_g-g)<=10*eps else 'stopped_without_fixed_point',
            'beta':b,'eta':eta,'gamma':g,'iterations':it,'initial_adjustments':adjustment,
            'decreasing_updates':decreases,'location_fixed_point_residual':float(fixed_g-g),
            'stop_rule':'signed_increment' if signed_stop else 'absolute_increment'}


def main():
    samples={'bearing':[152.7,172,172.5,173.3,193,204.7,216.5,234.9,262.6,422.6],
             'four':[3.1,4.6,5.6,6.8]}
    targets={'bearing':[1.251,87.709,139.731],'four':[2.202,4.159,1.137]}
    out={'source':'185-005, PDF pages 4-5, 11-12; DOI 10.1007/s12206-023-1019-z',
         'scope':'Independent formula implementation; not author code; examples and stopping-rule diagnostics only',
         'examples':{}}
    for name,t in samples.items():
        r=fit_sam(t); expected=targets[name]
        r.update(data=t,table_beta_eta_gamma=expected,
                 difference_from_table=(np.array([r['beta'],r['eta'],r['gamma']])-expected).tolist(),
                 within_rounding=bool(np.all(np.abs(np.array([r['beta'],r['eta'],r['gamma']])-expected)<.0005)))
        out['examples'][name]=r
    # Fixed exploratory sample, no method ranking and no replacement of failures.
    rng=np.random.default_rng(20260927); diagnostics=[]; failures=[]
    for b in [.5,1.5,3.]:
        for n in [5,10,20]:
            rows=[]
            for i in range(100):
                t=1+2*rng.weibull(b,n)
                absolute=fit_sam(t); signed=fit_sam(t,signed_stop=True)
                rows.append((absolute,signed))
                if absolute['status']!='converged' or signed['status']!='converged':
                    failures.append({'beta':b,'eta':2,'gamma':1,'n':n,'repeat_zero_based':i,
                                     'data':t.tolist(),'absolute':absolute,'signed':signed})
            diagnostics.append({'beta':b,'n':n,'repetitions':100,
                'absolute_status_counts':{s:sum(a['status']==s for a,_ in rows) for s in sorted({a['status'] for a,_ in rows})},
                'signed_status_counts':{s:sum(a['status']==s for _,a in rows) for s in sorted({a['status'] for _,a in rows})},
                'any_decreasing_update':sum(a.get('decreasing_updates',0)>0 for a,_ in rows)})
    out['stopping_diagnostics']=diagnostics
    out['diagnostic_design']={'seed':20260927,'eta':2,'gamma':1,'lr':.99,'eps':1e-5,
        'maxiter':10000,'interpretation':'adjust initial scale only; later domain exit recorded, not silently reset',
        'residual_gate':'absolute location fixed-point residual <= 10 * eps; local audit choice, not paper theorem'}
    out['diagnostic_failures']=failures
    p=Path(__file__).resolve().parents[1]/'evidence/sam_audit.json'
    p.write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(out,ensure_ascii=True,indent=2))


if __name__=='__main__':main()
