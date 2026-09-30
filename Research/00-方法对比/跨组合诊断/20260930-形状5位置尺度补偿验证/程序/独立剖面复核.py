"""Independent equation-root and stationary-point check; keep solver failures visible."""
import importlib.util
import json
from pathlib import Path
import numpy as np
from scipy.optimize import brentq
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('batch_analysis',HERE/'验证位置尺度补偿.py')
engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
DATA=engine.DATA
fits=json.loads((DATA/'实际估计.json').read_text(encoding='utf-8'))
audit=json.loads((DATA/'输入核验.json').read_text(encoding='utf-8'))
samples={(r['beta_true'],r['n'],r['sample_id']):np.array(r['observations']) for r in audit['samples']}
profiles={}
for r in engine.read_csv(DATA/'过程曲线.csv'):
    if r['method'] not in ('wmle','mle'):continue
    key=(int(r['beta_true']),int(r['n']),int(r['sample_id']),r['method'])
    profiles.setdefault(key,[]).append((float(r['gamma_candidate']),float(r['criterion']) if r['criterion'] else None))
records=[]
for r in fits:
    method=r['method']
    if method not in ('wmle','mle'):continue
    key=(r['beta'],r['n'],r['sample_id'],method);x=samples[key[:3]]
    pp=profiles[key];roots=[]
    for (g1,v1),(g2,v2) in zip(pp[:-1],pp[1:]):
        if v1 is None or v2 is None or v1*v2>=0:continue
        def score(g):
            p=engine.profile(x,method,g)
            if p is None:raise ValueError('profile outside supported domain')
            return p['value']
        try:root=float(brentq(score,g1,g2,xtol=1e-8))
        except ValueError:continue
        if any(abs(root-rr['gamma'])<1e-4 for rr in roots):continue
        p=engine.profile(x,method,root)
        residuals={}
        if method=='wmle':
            d=x-root;b=p['b'];logd=np.log(d);power=d**b
            t1=float(engine.get_weight_j2(len(x))/b+logd.mean()-np.sum(power*logd)/np.sum(power))
            t2=float(np.mean(1/d)*np.sum(power)/np.sum(d**(b-1))-engine.get_weight_j3(len(x),b))
            assert max(abs(t1),abs(t2))<1e-6
            residuals={'direct_T1':t1,'direct_T2':t2}
        roots.append({'gamma':root,'beta':p['b'],'eta':p['eta'],
            'positive_to_negative':bool(v1>0 and v2<0),'negative_to_positive':bool(v1<0 and v2>0),
            'finite_local_maximum':bool(method=='mle' and v1>0 and v2<0),
            'log_likelihood':p['ll'],'J3_clamped':p['clipped'],**residuals})
    zero=engine.profile(x,method,0.)
    boundary_max=bool(method=='mle' and zero and zero['value']<=1e-7)
    admissible=[p for p in roots if method=='wmle' or p['finite_local_maximum']]
    has_candidate=bool(admissible or boundary_max)
    fit_distance=min([abs(r['gamma_hat']-p['gamma']) for p in admissible]+([abs(r['gamma_hat'])] if boundary_max else [])) if r['converged'] and has_candidate else None
    records.append({'beta':r['beta'],'n':r['n'],'id':r['sample_id'],'method':method,'production_converged':r['converged'],
        'production_gamma':r['gamma_hat'] if r['converged'] else None,
        'zero_boundary_local_maximum':boundary_max,'profile_roots':roots,
        'admissible_candidates_found':len(admissible)+int(boundary_max),
        'production_failed_but_profile_has_candidate':bool(not r['converged'] and has_candidate),
        'distance_to_production_candidate':fit_distance})
missed=[r for r in records if r['production_failed_but_profile_has_candidate']]
unmatched=[r for r in records if r['production_converged'] and (r['distance_to_production_candidate'] is None or r['distance_to_production_candidate']>1e-2)]
result={'records':records,'failed_but_profile_candidate':missed,'successful_not_matched_to_profile_candidate':unmatched,
    'scope':'Finite grid sign-change root search within the frozen implementation domain; not a proof of no roots if none detected.'}
engine.dump(DATA/'独立剖面复核.json',result)
print(json.dumps({'records':len(records),'failed_with_profile_candidate':len(missed),'unmatched_successes':len(unmatched)},ensure_ascii=False))
