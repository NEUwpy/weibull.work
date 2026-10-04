"""Independent envelope derivative and smaller-step checks; never replaces saved estimates."""
import json
from pathlib import Path

import numpy as np
from scipy.optimize import minimize_scalar, brentq

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'程序/复核与LRE对比'


def one(row):
    data=json.loads((ROOT/'程序'/row['distribution']/'中间数据/results.json').read_text(encoding='utf-8'))
    sample=next(s for s in data['samples'] if (s['n'],s['id'])==(row['n'],row['id']))
    fit=next(s for s in data['results'] if (s['n'],s['id'],s['method_id'])==(row['n'],row['id'],'mdm'))
    t=np.asarray(sample['values'])
    p=(np.arange(1,len(t)+1)-.3)/(len(t)+.4)
    q=-np.log1p(-p)
    def conditional(g):
        optimum=minimize_scalar(lambda b:np.std((t-g)/q**(1/b),ddof=1),bounds=(.1,15),method='bounded',options={'xatol':1e-12})
        w=q**(-1/optimum.x)
        scales=(t-g)*w
        gradient=-np.dot(scales-scales.mean(),w-w.mean())/((len(t)-1)*scales.std(ddof=1))
        return float(optimum.x),float(optimum.fun),float(gradient),float(scales.mean())
    g=fit['gamma_hat']
    gap=float(t[0]-g)
    b,sigma,gradient,eta=conditional(g)
    record=dict(**row,original_beta=fit['beta_hat'],original_eta=fit['eta_hat'],original_gamma=g,
                sample_min=float(t[0]),gap=gap,refined_conditional_beta=b,
                refined_partial_gradient=gradient,finite_difference_checks=[])
    if row['status']=='success':
        for fraction in (.01,.001,.0001):
            h=gap*fraction
            derivative=(conditional(g+h)[1]-conditional(g-h)[1])/(2*h)
            record['finite_difference_checks'].append(dict(h=h,gradient=float(derivative)))
        lo=max(0.,g-gap)
        hi=g+gap*.9
        if (conditional(lo)[2]-.2)*(conditional(hi)[2]-.2)<0:
            root=brentq(lambda value:conditional(value)[2]-.2,lo,hi,xtol=1e-10)
            new_b,_,_,new_e=conditional(root)
            record['smaller_step_diagnostic_estimate']=dict(beta=new_b,eta=new_e,gamma=root,
                beta_change=new_b-fit['beta_hat'],eta_change=new_e-fit['eta_hat'],gamma_change=root-g)
    return record


if __name__=='__main__':
    summary=json.loads((OUT/'差异与异常汇总.json').read_text(encoding='utf-8'))
    selected=[r for r in summary['mdm_analytic_gradients'] if r['status']=='failure' or abs(r['analytic_partial_gradient']-.2)>.001]
    records=[one(r) for r in selected]
    (OUT/'MDM梯度独立核查.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    for r in records:
        if r['status']=='success':print(json.dumps(r,ensure_ascii=False))
