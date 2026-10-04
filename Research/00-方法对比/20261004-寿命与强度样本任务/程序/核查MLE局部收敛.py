"""Profile-likelihood diagnosis of the one returned fit with a nonzero interior location score."""
import json
from pathlib import Path
import numpy as np
from scipy.optimize import minimize_scalar

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'程序/复核与LRE对比'
case='W(5,1000,500)';n=7;sid=31
data=json.loads((ROOT/'程序'/case/'中间数据/results.json').read_text(encoding='utf-8'))
row=next(r for r in data['results'] if (r['n'],r['id'],r['method_id'])==(n,sid,'mle'))
t=np.asarray(next(s for s in data['samples'] if (s['n'],s['id'])==(n,sid))['values'])
def loglik(b,e,g):
    v=(t-g)/e
    return float(len(t)*np.log(b/e)+(b-1)*np.log(v).sum()-(v**b).sum())
def conditional(g):
    z=np.log(t-g)
    def fit(b):
        # logsumexp avoids scale overflow in the profiled scale calculation.
        from scipy.special import logsumexp
        log_e=(logsumexp(b*z)-np.log(len(t)))/b
        return -(len(t)*(np.log(b)-log_e)+(b-1)*(z-log_e).sum()-np.exp(b*(z-log_e)).sum())
    res=minimize_scalar(fit,bounds=(1,200),method='bounded',options={'xatol':1e-10})
    from scipy.special import logsumexp
    b=float(res.x);e=float(np.exp((logsumexp(b*z)-np.log(len(t)))/b))
    return b,e,loglik(b,e,g)
upper=float(t[0]-1e-7)
grid=np.linspace(0,upper,401)
ll=np.array([conditional(g)[2] for g in grid])
candidates=[(float(grid[int(ll.argmax())]),float(ll.max()))]
for i in range(1,len(grid)-1):
    if ll[i]>=ll[i-1] and ll[i]>=ll[i+1]:
        result=minimize_scalar(lambda g:-conditional(g)[2],bounds=(grid[i-1],grid[i+1]),method='bounded',options={'xatol':1e-8})
        candidates.append((float(result.x),float(-result.fun)))
g,_=max(candidates,key=lambda r:r[1]);b,e,new_ll=conditional(g)
old={k:row[k] for k in ('beta_hat','eta_hat','gamma_hat')}
old_ll=loglik(old['beta_hat'],old['eta_hat'],old['gamma_hat'])
interior_g=float(.9*t[0]); interior_b,interior_e,interior_ll=conditional(interior_g)
record=dict(distribution=case,n=n,id=sid,diagnostic_constraint='1 <= beta <= 200, 0 <= gamma < sample minimum',
            grid_points=401,original=old,original_loglik=old_ll,
            diagnostic=dict(beta=b,eta=e,gamma=g,loglik=new_ll),loglik_increase=new_ll-old_ll,
            admissible_interior_example=dict(beta=interior_b,eta=interior_e,gamma=interior_g,
                gap=float(t[0]-interior_g),loglik=interior_ll,loglik_increase=interior_ll-old_ll),
            small_location_step=.01,
            small_location_step_loglik_increase=loglik(old['beta_hat'],old['eta_hat'],old['gamma_hat']+.01)-old_ll)
(OUT/'MLE局部收敛核查.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(record,ensure_ascii=False,indent=2))
