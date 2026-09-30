"""Check the saved WMLE tolerance-accepted candidate independently; never replace it."""
import json
import numpy as np
from scipy.optimize import brentq
from 连续形状实验 import mother, DATA

rows=json.loads((DATA/'实际估计.json').read_text(encoding='utf-8'))
samples=json.loads((DATA/'样本.json').read_text(encoding='utf-8'))
r=next(r for r in rows if r['beta']==3.5 and r['n']==7 and r['sample_id']==39 and r['method']=='wmle')
x=np.array(next(s['observations'] for s in samples if s['beta']==3.5 and s['n']==7 and s['sample_id']==39))
d=x-r['gamma_hat'];b=r['beta_hat'];logs=np.log(d);powers=d**b
t1=float(mother.get_weight_j2(7)/b+logs.mean()-np.sum(powers*logs)/powers.sum())
t2=float(np.mean(1/d)*powers.sum()/np.sum(d**(b-1))-mother.get_weight_j3(7,b))
root=float(brentq(lambda g:mother.profile(x,'wmle',g)['value'],650.,710.,xtol=1e-10))
p=mother.profile(x,'wmle',root)
out=dict(beta_true=3.5,n=7,sample_id=39,method='wmle',saved_beta=b,saved_gamma=r['gamma_hat'],
    saved_eta=r['eta_hat'],raw_T1=t1,raw_T2=t2,raw_squared_residual=t1*t1+t2*t2,
    optimizer_acceptance_threshold=1e-8,profile_T2_at_saved_gamma=mother.profile(x,'wmle',r['gamma_hat'])['value'],
    independently_refined_gamma=root,independently_refined_beta=p['b'],independently_refined_eta=p['eta'],
    gamma_difference=root-r['gamma_hat'],refined_T2=p['value'],
    interpretation='Tolerance-accepted approximate candidate. Small conditional beta/eta discrepancies do not prove a nearby position root. Original estimate and summaries preserved.')
assert out['raw_squared_residual']<out['optimizer_acceptance_threshold']
assert abs(p['value'])<1e-8
mother.dump(DATA/'WMLE近似解诊断.json',out)
print(json.dumps(out,ensure_ascii=False))
